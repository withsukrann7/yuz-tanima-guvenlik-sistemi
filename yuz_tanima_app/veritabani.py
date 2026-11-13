"""PostgreSQL erişim katmanı.

Eski sürümdeki `db_sorgula` hataları yutup boş liste döndürüyordu; bu yüzden
bağlantı yokken sistem "başarılıymış gibi" sürüyordu. Burada hatalar
`VeritabaniHatasi` olarak yükseltilir, çağıran taraf (arayüz) kullanıcıya
gösterir.

İlk kurulum için:  python -m yuz_tanima_app.veritabani kur
"""
import logging
import queue
import sys
import threading
import time
from datetime import datetime

import psycopg2

from . import config

logger = logging.getLogger(__name__)

SEMA_DOSYASI = config.PROJE_KOKU / "veritabani" / "schema.sql"


class VeritabaniHatasi(Exception):
    """Bağlantı veya sorgu hatası (kullanıcıya gösterilebilir mesaj taşır)."""


# Bağlantı kurulamadığında kısa süre yeniden denemeyi bırak: arayüz her yenilemede
# ~10 sorgu çalıştırır; veritabanı ulaşılamazken her biri zaman aşımını beklerse
# pencere dakikalarca donardı.
YENIDEN_DENEME_BEKLEME_SN = 15
_son_hata = {"ayar": None, "zaman": 0.0, "mesaj": ""}


def hata_durumunu_sifirla():
    _son_hata.update(ayar=None, zaman=0.0, mesaj="")


def baglan():
    ayar = config.veritabani_ayarlari()
    anahtar = tuple(sorted(ayar.items()))
    if (_son_hata["ayar"] == anahtar
            and time.monotonic() - _son_hata["zaman"] < YENIDEN_DENEME_BEKLEME_SN):
        raise VeritabaniHatasi(_son_hata["mesaj"])
    try:
        conn = psycopg2.connect(**ayar)
    except psycopg2.Error as e:
        _son_hata.update(ayar=anahtar, zaman=time.monotonic(), mesaj=_mesaj(e))
        raise VeritabaniHatasi(_mesaj(e)) from e
    hata_durumunu_sifirla()
    return conn


def _mesaj(e: Exception) -> str:
    ilk = str(e).strip().splitlines()
    return ilk[0] if ilk else e.__class__.__name__


def calistir(sorgu, parametreler=(), *, getir=False):
    """Tek sorguyu kendi bağlantısı ve işlemi içinde çalıştırır.

    getir=True ise satır listesi döner. Hata olursa VeritabaniHatasi yükselir.
    """
    conn = baglan()
    try:
        with conn:                       # başarıda commit, hatada rollback
            with conn.cursor() as cur:
                cur.execute(sorgu, parametreler or ())
                return cur.fetchall() if getir else None
    except psycopg2.Error as e:
        raise VeritabaniHatasi(_mesaj(e)) from e
    finally:
        conn.close()


def tek_deger(sorgu, parametreler=()):
    satirlar = calistir(sorgu, parametreler, getir=True)
    return satirlar[0][0] if satirlar else 0


def baglanti_testi():
    """(True, '') veya (False, hata_mesajı) döndürür."""
    try:
        calistir("SELECT 1", getir=True)
        return True, ""
    except VeritabaniHatasi as e:
        return False, str(e)


TABLOLAR = ("yetkili_kisiler", "giris_kayitlari", "yetkisiz_kayitlar")


def durum_kontrolu():
    """Bağlantıyı ve gerekli tabloların varlığını denetler: (ok, mesaj)."""
    try:
        for tablo in TABLOLAR:                      # sabit adlar; kullanıcı girdisi yok
            calistir(f"SELECT 1 FROM {tablo} LIMIT 1", getir=True)
        return True, ""
    except VeritabaniHatasi as e:
        return False, str(e)


def sema_olustur():
    """schema.sql dosyasını çalıştırır (idempotent: IF NOT EXISTS)."""
    sql = SEMA_DOSYASI.read_text(encoding="utf-8")
    calistir(sql)


# ── Olay kayıtları ─────────────────────────────────────────────────────
def yetkili_giris_kaydet(isim, durum="Basarili"):
    simdi = datetime.now()
    calistir(
        "INSERT INTO giris_kayitlari (isim, durum, tarih, saat) VALUES (%s, %s, %s, %s)",
        (isim, durum, simdi.date(), simdi.time()),
    )


def yetkisiz_giris_kaydet(foto_yolu):
    simdi = datetime.now()
    calistir(
        "INSERT INTO yetkisiz_kayitlar (foto_yolu, tarih, saat) VALUES (%s, %s, %s)",
        (foto_yolu, simdi.date(), simdi.time()),
    )


CAMERA_EVENT_STATUSES = {
    # Keep CAMERA_ for existing filters and fit the live VARCHAR(20) column.
    "blocked": ("CAMERA_BLK_ACTIVE", "CAMERA_BLK_RESOLVED"),
    "occluded": ("CAMERA_OCC_ACTIVE", "CAMERA_OCC_RESOLVED"),
    "frozen": ("CAMERA_FRZ_ACTIVE", "CAMERA_FRZ_RESOLVED"),
    "read_failure": ("CAMERA_READ_ACTIVE", "CAMERA_READ_RESOLVED"),
}


def camera_access_intervals(rows, today=None, now=None):
    """Build today's camera downtime intervals from existing transition rows.

    Rows are `(camera_name, date, time, status)` tuples ordered by database id.
    An unresolved event is returned as ongoing, including when it began before
    today, so a continuing outage remains visible in the daily overview.
    """
    today = today or datetime.now().date()
    now = now or datetime.now()
    status_types = {
        status: (event_type, active)
        for event_type, statuses in CAMERA_EVENT_STATUSES.items()
        for status, active in ((statuses[0], True), (statuses[1], False))
    }
    open_events = {}
    intervals = []

    for camera_name, event_date, event_time, status in rows or ():
        event_info = status_types.get(status)
        if not event_info:
            continue
        event_type, active = event_info
        key = (camera_name, event_type)
        occurred_at = datetime.combine(event_date, event_time)
        if active:
            open_events[key] = occurred_at
            continue

        started_at = open_events.pop(key, None)
        if started_at is not None and started_at.date() == today:
            intervals.append({
                "camera_name": camera_name,
                "event_type": event_type,
                "start": started_at,
                "end": occurred_at,
                "duration_seconds": max(0, int((occurred_at - started_at).total_seconds())),
                "ongoing": False,
            })

    for (camera_name, event_type), started_at in open_events.items():
        intervals.append({
            "camera_name": camera_name,
            "event_type": event_type,
            "start": started_at,
            "end": None,
            "duration_seconds": max(0, int((now - started_at).total_seconds())),
            "ongoing": True,
        })

    return sorted(intervals, key=lambda interval: interval["start"], reverse=True)


def record_camera_event_transition(camera_name, event_type, active):
    """Persist camera-event state changes using the existing access-log schema.

    Returns True only when a new active/resolved row was inserted. Reserved
    CAMERA_* statuses keep camera events distinct from person entry counts.
    """
    if event_type not in CAMERA_EVENT_STATUSES:
        raise ValueError(f"Unsupported camera event type: {event_type}")
    if not isinstance(camera_name, str) or not camera_name.strip() or len(camera_name) > 150:
        raise ValueError("camera_name must be a non-empty string of at most 150 characters")

    active_status, resolved_status = CAMERA_EVENT_STATUSES[event_type]
    latest = calistir(
        "SELECT durum FROM giris_kayitlari "
        "WHERE isim=%s AND durum IN (%s, %s) "
        "ORDER BY id DESC LIMIT 1",
        (camera_name, active_status, resolved_status),
        getir=True,
    )
    currently_active = bool(latest and latest[0][0] == active_status)
    if currently_active == bool(active):
        return False

    status = active_status if active else resolved_status
    occurred_at = datetime.now()
    calistir(
        "INSERT INTO giris_kayitlari (isim, durum, tarih, saat) VALUES (%s, %s, %s, %s)",
        (camera_name, status, occurred_at.date(), occurred_at.time()),
    )
    return True


_camera_event_queue = queue.Queue()
_camera_event_queue_lock = threading.Lock()
_camera_event_worker = None


def _write_camera_event_queue():
    while True:
        camera_name, event_type, active = _camera_event_queue.get()
        try:
            record_camera_event_transition(camera_name, event_type, active)
        except Exception:
            logger.exception(
                "Queued camera event could not be saved: camera=%s type=%s active=%s",
                camera_name, event_type, active,
            )
        finally:
            _camera_event_queue.task_done()


def enqueue_camera_event_transition(camera_name, event_type, active):
    """Queue camera event persistence so camera/UI control threads never wait on PostgreSQL."""
    if event_type not in CAMERA_EVENT_STATUSES:
        raise ValueError(f"Unsupported camera event type: {event_type}")
    if not isinstance(camera_name, str) or not camera_name.strip() or len(camera_name) > 150:
        raise ValueError("camera_name must be a non-empty string of at most 150 characters")

    global _camera_event_worker
    with _camera_event_queue_lock:
        _camera_event_queue.put((camera_name, event_type, bool(active)))
        if _camera_event_worker is None or not _camera_event_worker.is_alive():
            _camera_event_worker = threading.Thread(
                target=_write_camera_event_queue,
                name="camera-event-writer",
                daemon=True,
            )
            _camera_event_worker.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "kur":
        try:
            sema_olustur()
            print("Tablolar hazır (yetkili_kisiler, giris_kayitlari, yetkisiz_kayitlar).")
        except VeritabaniHatasi as e:
            print(f"Veritabanı hatası: {e}")
            sys.exit(1)
    elif komut == "test":
        ok, mesaj = baglanti_testi()
        print("Bağlantı başarılı." if ok else f"Bağlantı kurulamadı: {mesaj}")
        sys.exit(0 if ok else 1)
    else:
        print("Kullanım: python -m yuz_tanima_app.veritabani [kur|test]")
        sys.exit(2)
