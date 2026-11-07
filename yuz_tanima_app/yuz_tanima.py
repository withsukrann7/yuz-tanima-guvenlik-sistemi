"""Yüz tanıma: yetkili yüzlerin yüklenmesi ve DeepFace ile doğrulama.

Tanınan kişi adı mümkün olduğunca `yetkili_kisiler.isim` ile aynıdır; böylece
giriş kayıtları ile kullanıcı listesi eşleşir. Yetkili listesinin kaynağı:
  1. Veritabanındaki 'Aktif' kullanıcılar (foto_yolu veya known_faces/<çalışan id>.*)
  2. Veritabanında karşılığı olmayan eski `known_faces/` dosyaları (uyarı ile)
Pasif veya silinmiş kullanıcılar tanınmaz.
"""
import logging
import os
import re

import cv2
import numpy as np

from . import config, veritabani

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


def yuz_dedektoru_yukle():
    """Haar yüz bulucuyu güvenle yükler.

    - OpenCV 5.x paketi Haar XML dosyalarını İÇERMEZ; dosya yoksa çözümü söyleyen
      açık bir hata verilir.
    - Windows'ta yolda ASCII olmayan karakter (ü, ı, ş...) varsa CascadeClassifier(yol)
      dosyayı açamaz; bu durumda dosya Python ile okunup bellekten yüklenir.
    """
    yol = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    if not os.path.exists(yol):
        raise RuntimeError(
            f"Yüz bulma dosyası bulunamadı: {yol}\n"
            "OpenCV 5.x bu dosyayı içermiyor. Çözüm:\n"
            'pip install "opencv-python>=4.8,<5"')
    dedektor = cv2.CascadeClassifier(yol)
    if not dedektor.empty():
        return dedektor
    try:
        with open(yol, "rb") as f:
            xml = f.read().decode("utf-8")
        fs = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
        dedektor = cv2.CascadeClassifier()
        if fs.isOpened() and dedektor.read(fs.getFirstTopLevelNode()) and not dedektor.empty():
            logger.info("Haar dosyası yoldan açılamadı; bellekten yüklendi.")
            return dedektor
    except Exception as e:
        logger.warning("Bellekten Haar yükleme başarısız: %s", e)
    raise RuntimeError(f"Yüz bulma dosyası yüklenemedi: {yol}")


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


# ── Tanıyıcı ────────────────────────────────────────────────────────────
class FaceRecognizer:
    def __init__(self):
        self.known_faces = {}
        self.uyarilar = []
        self.reload()

    def reload(self):
        """Yetkili listesini yeniden yükler (kayıt/silme sonrası çağrılır).

        Sözlük tek seferde atanır; analiz thread'i eski ya da yeni listeyi
        tutarlı biçimde görür.
        """
        yuzler, uyarilar = bilinen_yuzleri_yukle()
        self.known_faces = yuzler
        self.uyarilar = uyarilar
        logger.info("%d yetkili yüz yüklendi: %s", len(yuzler), list(yuzler))

    def identify(self, yuz_goruntusu):
        """(isim, yetkili_mi, güven) döndürür.

        DeepFace yoksa ya da tüm karşılaştırmalar hata verirse RuntimeError
        yükseltir; böylece teknik arıza "bilinmeyen kişi alarmı" olarak
        yanlış raporlanmaz.
        """
        if DeepFace is None:
            raise RuntimeError("DeepFace yüklü değil")
        yuzler = self.known_faces
        if not yuzler:
            return BILINMEYEN, False, 0.0

        en_iyi, en_iyi_mesafe, dogrulandi, hata_sayisi = None, float("inf"), False, 0
        for isim, referans in yuzler.items():
            try:
                sonuc = DeepFace.verify(
                    img1_path=yuz_goruntusu,
                    img2_path=referans,
                    model_name=config.MODEL_ADI,
                    distance_metric=config.MESAFE_METRIGI,
                    detector_backend=config.DEDEKTOR,
                    enforce_detection=False,
                )
                mesafe = sonuc.get("distance", 1.0)
                if mesafe < en_iyi_mesafe:
                    en_iyi_mesafe, en_iyi = mesafe, isim
                    dogrulandi = sonuc.get("verified", False)
            except Exception as e:
                hata_sayisi += 1
                logger.warning("%s karşılaştırma hatası: %s", isim, e)

        if hata_sayisi == len(yuzler):
            raise RuntimeError("Tüm yüz karşılaştırmaları başarısız oldu")
        if en_iyi and dogrulandi:
            return en_iyi, True, max(0.0, 1.0 - en_iyi_mesafe)
        return BILINMEYEN, False, 0.0
