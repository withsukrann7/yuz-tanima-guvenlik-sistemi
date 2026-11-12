"""Yüz tanıma: yetkili yüzlerin yüklenmesi ve DeepFace ile doğrulama.

Karşılaştırma VGG-Face kosinüs mesafesidir. Eşik DeepFace'in kendi varsayılanıdır
(0.68); bu dosya o sayıyı düşürmez. identify tek kare karar verir. Kapı ve alarm
için art arda iki aynı sonuç kamera thread'inde aranır.

Tanınan kişi adı mümkün olduğunca `yetkili_kisiler.isim` ile aynıdır; böylece
giriş kayıtları ile kullanıcı listesi eşleşir. Yetkili listesinin kaynağı:
  1. Veritabanındaki 'Aktif' kullanıcılar (foto_yolu veya known_faces/<çalışan id>.*)
  2. Veritabanında karşılığı olmayan eski `known_faces/` dosyaları (uyarı ile)
Pasif veya silinmiş kullanıcılar tanınmaz.
"""
import logging
import re

import cv2
import numpy as np

from . import config, veritabani
from .yuz_bulucu import YuzBulucu, yuz_kirp

logger = logging.getLogger(__name__)

BILINMEYEN = "Bilinmeyen Kisi"

DeepFace = None          # deepface_yukle() ile doldurulur


# ── DeepFace yükleme ────────────────────────────────────────────────────
def deepface_yukle() -> bool:
    """DeepFace'i (ana thread'de) içe aktarır. Başarılıysa True."""
    global DeepFace
    if DeepFace is not None:
        return True
    try:
        from deepface import DeepFace as _DF
        DeepFace = _DF
        logger.info("DeepFace yüklendi.")
        return True
    except Exception as e:
        logger.error("DeepFace yüklenemedi: %s", e)
        return False


def deepface_hazir() -> bool:
    return DeepFace is not None


# ── Dosya / görsel yardımcıları (Unicode yol güvenli) ──────────────────
def gorsel_oku(yol):
    """Görseli BGR numpy dizisi olarak okur; okunamazsa None.

    cv2.imread Windows'ta ASCII olmayan yollarda (ör. 'Masaüstü') None
    döndürür; bu yüzden np.fromfile + imdecode kullanılır.
    """
    try:
        veri = np.fromfile(str(yol), dtype=np.uint8)
        if veri.size == 0:
            return None
        return cv2.imdecode(veri, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.warning("Görsel okunamadı (%s): %s", yol, e)
        return None


def gorsel_yaz(yol, goruntu) -> bool:
    """cv2.imwrite'ın Unicode yol güvenli karşılığı."""
    try:
        uzanti = str(yol).rsplit(".", 1)[-1].lower()
        basari, tampon = cv2.imencode("." + uzanti, goruntu)
        if not basari:
            return False
        tampon.tofile(str(yol))
        return True
    except Exception as e:
        logger.error("Görsel yazılamadı (%s): %s", yol, e)
        return False


def guvenli_dosya_adi(metin: str) -> str:
    """Dosya adında sakıncalı karakterleri ('/', '..', boşluk vb.) temizler."""
    temiz = re.sub(r"[^\w\-]+", "_", str(metin), flags=re.UNICODE).strip("_")
    return temiz or "kisi"


def normalize(metin) -> str:
    """Türkçe harfe duyarlı, boşluk/alt çizgi farkını yok sayan karşılaştırma anahtarı."""
    if metin is None:
        return ""
    s = str(metin).replace("_", " ").replace("İ", "i").replace("I", "ı").lower()
    return " ".join(s.split())


# ── Yetkili yüzlerin yüklenmesi ─────────────────────────────────────────
def bilinen_dizin_dosyalari():
    d = config.BILINEN_YUZLER_DIZINI
    if not d.exists():
        return []
    return sorted(
        p for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in config.DESTEKLENEN_UZANTILAR
    )


def bilinen_yuzleri_yukle():
    """(yuzler: {isim: BGR görüntü}, uyarilar: [metin]) döndürür."""
    yuzler, uyarilar = {}, []
    dizin_dosyalari = bilinen_dizin_dosyalari()
    db_anahtarlari = set()

    # 1) Veritabanı
    try:
        satirlar = veritabani.calistir(
            "SELECT isim, calisan_id, foto_yolu, durum FROM yetkili_kisiler", getir=True
        )
    except veritabani.VeritabaniHatasi as e:
        uyarilar.append(f"Veritabanına ulaşılamadı, yalnızca known_faces/ kullanılıyor: {e}")
        logger.error(uyarilar[-1])
        satirlar = []

    for isim, cid, foto, durum in satirlar:
        db_anahtarlari.add(normalize(isim))
        if cid:
            db_anahtarlari.add(normalize(cid))
        if (durum or "Aktif") != "Aktif":
            continue
        adaylar = []
        if foto:
            adaylar.append(config.yol_coz(foto))
        if cid:
            ck = normalize(cid)
            adaylar += [p for p in dizin_dosyalari if normalize(p.stem) == ck]
        goruntu = None
        for aday in adaylar:
            if aday and aday.exists():
                goruntu = gorsel_oku(aday)
                if goruntu is not None:
                    break
        if goruntu is None:
            uyarilar.append(f"'{isim}' için okunabilir fotoğraf bulunamadı; tanınmayacak.")
            logger.warning(uyarilar[-1])
            continue
        yuzler[isim] = goruntu

    # 2) Eski known_faces/ dosyaları (veritabanında karşılığı olmayanlar)
    for p in dizin_dosyalari:
        if normalize(p.stem) in db_anahtarlari:
            continue
        goruntu = gorsel_oku(p)
        if goruntu is None:
            uyarilar.append(f"known_faces/{p.name} okunamadı, atlandı.")
            logger.warning(uyarilar[-1])
            continue
        isim = p.stem.replace("_", " ").title()    # özgün adlandırma davranışı
        yuzler.setdefault(isim, goruntu)
        logger.warning("known_faces/%s veritabanında kayıtlı değil; eski kayıt olarak yüklendi (%s).", p.name, isim)

    return yuzler, uyarilar


def referanslari_kirp(yuzler):
    """Kayıtlı fotoğraflardan canlı akışla aynı payla en büyük yüzü ayırır.

    (hazir_yuzler, backendler, ek_uyarilar) döner. Yüz bulunursa backend
    "skip" olur: DeepFace bu karede yeniden yüz aramaz. Bulunamazsa özgün
    fotoğraf kalır ve bir kez OpenCV ile taranır; kişi listeden düşmez.
    """
    if not yuzler:
        return {}, {}, []
    uyarilar = []
    hazir, backend = {}, {}
    try:
        bulucu = YuzBulucu(video=False)
    except Exception as e:
        logger.warning("Referans kırpması için yüz bulucu açılamadı: %s", e)
        for isim, goruntu in yuzler.items():
            hazir[isim] = goruntu
            backend[isim] = "opencv"
            uyarilar.append(
                f"'{isim}' fotoğrafı ayrılamadı; özgün kare OpenCV ile taranacak."
            )
        return hazir, backend, uyarilar

    try:
        for isim, goruntu in yuzler.items():
            try:
                kutular = bulucu.tespit_et(goruntu)
            except Exception as e:
                logger.warning("%s yüzü ayrılamadı: %s", isim, e)
                kutular = []
            if len(kutular) > 1:
                uyarilar.append(
                    f"'{isim}' fotoğrafında {len(kutular)} yüz var; en büyük yüz kullanılacak."
                )
            if not kutular:
                hazir[isim] = goruntu
                backend[isim] = "opencv"
                uyarilar.append(
                    f"'{isim}' fotoğrafında yüz ayrılmadı; özgün kare OpenCV ile taranacak."
                )
                continue
            kutu = max(kutular, key=lambda f: f[2] * f[3])
            kirp = yuz_kirp(goruntu, kutu, config.YUZ_KIRPMA_PAYI)
            if kirp is None or min(kirp.shape[:2]) < 20:
                hazir[isim] = goruntu
                backend[isim] = "opencv"
                uyarilar.append(
                    f"'{isim}' kırpımı geçersiz; özgün kare OpenCV ile taranacak."
                )
                continue
            hazir[isim] = kirp
            backend[isim] = "skip"
    finally:
        bulucu.close()
    return hazir, backend, uyarilar


# ── Mesafe (DeepFace ile aynı kosinüs; eşik gevşetilmez) ────────────────
_ESIK = None


def _deepface_esigi():
    """Kurulu DeepFace'in model eşiği. Okunamazsa None."""
    try:
        from deepface.modules.verification import find_threshold
        return float(find_threshold(config.MODEL_ADI, config.MESAFE_METRIGI))
    except Exception:
        try:
            from deepface.commons.distance import findThreshold # type: ignore
            return float(findThreshold(config.MODEL_ADI, config.MESAFE_METRIGI))
        except Exception:
            return None


def model_esigi():
    """VGG-Face + cosine için DeepFace varsayılanı 0.68. Daha düşüğe çekilmez."""
    global _ESIK
    if _ESIK is not None:
        return _ESIK
    esik = _deepface_esigi()
    if esik is None:
        if (config.MODEL_ADI, config.MESAFE_METRIGI) != ("VGG-Face", "cosine"):
            raise RuntimeError("DeepFace eşiği okunamadı")
        esik = 0.68
    _ESIK = esik
    return _ESIK


def kosinus_mesafesi(a, b) -> float:
    """DeepFace find_cosine_distance ile aynı: 0 aynı yön, 1 dik, büyüdükçe uzak."""
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if a.size == 0 or a.size != b.size:
        return 1.0
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 1.0
    return float(1.0 - np.dot(a, b) / (na * nb))


def _temsil_et(goruntu, backend):
    """Yüz vektörlerini ister. skip: gelen kare zaten yüzdür, yeniden arama yok."""
    ortak = dict(
        img_path=goruntu,
        model_name=config.MODEL_ADI,
        detector_backend=backend,
        enforce_detection=False,
    )
    # align=False kırpılmış yüzde: göz noktası titremesi her karede vektörü oynatır.
    # OpenCV yedeğinde DeepFace'in kendi hizalaması durur; o yol kayıt anında bir kez çalışır.
    denemeler = (
        {**ortak, "align": backend != "skip", "normalization": "base"},
        {**ortak, "align": backend != "skip"},
        ortak,
    )
    son_hata = None
    for kwargs in denemeler:
        try:
            return DeepFace.represent(**kwargs)
        except TypeError as e:
            son_hata = e
    raise son_hata if son_hata is not None else RuntimeError("yüz vektörü alınamadı")


def _vektor_sec(sonuc):
    if isinstance(sonuc, dict):
        sonuc = [sonuc]
    if not sonuc:
        raise RuntimeError("boş yüz vektörü")

    def alan(oge):
        bolge = oge.get("facial_area") or {}
        return int(bolge.get("w", 0)) * int(bolge.get("h", 0))

    oge = max(sonuc, key=alan)
    vektor = np.asarray(oge["embedding"], dtype=np.float64).ravel()
    if vektor.size == 0 or not np.isfinite(vektor).all():
        raise RuntimeError("geçersiz yüz vektörü")
    return vektor


# ── Tanıyıcı ────────────────────────────────────────────────────────────
class FaceRecognizer:
    def __init__(self):
        self.known_faces = {}
        self.uyarilar = []
        self._embeddings = {}
        self._embed_kaynak = None
        self._backend = {}
        self.reload()

    def reload(self):
        """Yetkili listesini yeniden yükler (kayıt/silme sonrası çağrılır).

        Sözlük tek seferde atanır; analiz thread'i eski ya da yeni listeyi
        tutarlı biçimde görür. Vektörler bir sonraki tanımada, sabit referans
        için bir kez hesaplanır.
        """
        yuzler, uyarilar = bilinen_yuzleri_yukle()
        yuzler, backend, ek = referanslari_kirp(yuzler)
        self._embeddings = {}
        self._embed_kaynak = None
        self._backend = backend
        self.known_faces = yuzler
        self.uyarilar = list(uyarilar) + ek
        logger.info("%d yetkili yüz yüklendi: %s", len(yuzler), list(yuzler))

    def _vektor(self, goruntu, backend):
        return _vektor_sec(_temsil_et(goruntu, backend))

    def _hazir_vektorler(self, yuzler):
        if self._embed_kaynak is yuzler and self._embeddings:
            return self._embeddings
        uretilen = {}
        hatalar = 0
        for isim, goruntu in yuzler.items():
            try:
                uretilen[isim] = self._vektor(goruntu, self._backend.get(isim, "skip"))
            except Exception as e:
                hatalar += 1
                logger.warning("%s vektörü çıkarılamadı: %s", isim, e)
        if yuzler and hatalar == len(yuzler):
            raise RuntimeError("Tüm yüz vektörleri çıkarılamadı")
        self._embeddings = uretilen
        self._embed_kaynak = yuzler
        return uretilen

    def identify(self, yuz_goruntusu):
        """(isim, yetkili_mi, güven) döndürür.

        `yuz_goruntusu` MediaPipe ile kırpılmış bir yüz olmalıdır. Karar tek
        örnektir; kapı veya alarm için art arda iki örnek kamera tarafında gerekir.

        DeepFace yoksa ya da tüm karşılaştırmalar hata verirse RuntimeError
        yükseltir; böylece teknik arıza "bilinmeyen kişi alarmı" olarak
        yanlış raporlanmaz. Kabul, yalnızca en yakın kişinin mesafesi DeepFace
        eşiğinin altında kaldığında verilir.
        """
        if DeepFace is None:
            raise RuntimeError("DeepFace yüklü değil")
        yuzler = self.known_faces
        if not yuzler:
            return BILINMEYEN, False, 0.0

        vektorler = self._hazir_vektorler(yuzler)
        if not vektorler:
            raise RuntimeError("Tüm yüz vektörleri çıkarılamadı")
        try:
            canli = self._vektor(yuz_goruntusu, "skip")
        except Exception as e:
            raise RuntimeError(f"Canlı yüz vektörü çıkarılamadı: {e}") from e

        esik = model_esigi()
        en_iyi, en_iyi_mesafe, hata_sayisi = None, float("inf"), 0
        for isim, referans in vektorler.items():
            try:
                mesafe = kosinus_mesafesi(canli, referans)
            except Exception as e:
                hata_sayisi += 1
                logger.warning("%s karşılaştırma hatası: %s", isim, e)
                continue
            if not np.isfinite(mesafe):
                hata_sayisi += 1
                continue
            if mesafe < en_iyi_mesafe:
                en_iyi_mesafe, en_iyi = mesafe, isim

        if en_iyi is None or hata_sayisi == len(vektorler):
            raise RuntimeError("Tüm yüz karşılaştırmaları başarısız oldu")

        yetkili = en_iyi_mesafe <= esik
        logger.info(
            "Tanıma: en yakın=%s mesafe=%.3f eşik=%.3f sonuç=%s",
            en_iyi, en_iyi_mesafe, esik, "yetkili" if yetkili else "ret",
        )
        if yetkili:
            return en_iyi, True, max(0.0, 1.0 - en_iyi_mesafe)
        return BILINMEYEN, False, 0.0
