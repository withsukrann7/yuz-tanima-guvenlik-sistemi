"""PostgreSQL erişim katmanı.

Eski sürümdeki `db_sorgula` hataları yutup boş liste döndürüyordu; bu yüzden
bağlantı yokken sistem "başarılıymış gibi" sürüyordu. Burada hatalar
`VeritabaniHatasi` olarak yükseltilir, çağıran taraf (arayüz) kullanıcıya
gösterir.

İlk kurulum için:  python -m yuz_tanima_app.veritabani kur
"""
import logging
import sys
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
