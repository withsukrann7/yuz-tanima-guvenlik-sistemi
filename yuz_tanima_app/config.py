"""Merkezi yapılandırma: dosya yolları, ortam değişkenleri ve sabitler.

Tüm yollar proje köküne göre hesaplanır; uygulama hangi klasörden
başlatılırsa başlatılsın aynı dosyalar bulunur. Gizli bilgiler (veritabanı
parolası, giriş bilgileri) koda yazılmaz, ortam değişkenlerinden veya
proje kökündeki `.env` dosyasından okunur (bkz. `.env.example`).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv yoksa yalnızca gerçek ortam değişkenleri kullanılır
    load_dotenv = None

PROJE_KOKU = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(PROJE_KOKU / ".env")

# ── Dosya / klasör yolları (mevcut klasör adları korunmuştur) ──────────
BILINEN_YUZLER_DIZINI = PROJE_KOKU / "known_faces"   # eski tarz yetkili fotoğrafları
YUZLER_DIZINI         = PROJE_KOKU / "yuzler"        # kayıt ekranının yüklediği fotoğraflar
SNAPSHOT_DIZINI       = PROJE_KOKU / "snapshots"     # bilinmeyen kişi görüntüleri
GUVENLIK_LOG_DOSYASI  = PROJE_KOKU / "security_log.json"
UYGULAMA_LOG_DOSYASI  = PROJE_KOKU / "security_system.log"
ARSIV_SILINEN_YUZLER  = PROJE_KOKU / "arsiv" / "silinen_yuzler"
UI_DIZINI             = PROJE_KOKU / "ui"
LOGIN_UI              = UI_DIZINI / "login.ui"
LOGO_DOSYASI          = PROJE_KOKU / "logo.png"
LOGIN_ARKAPLAN        = PROJE_KOKU / "login_bg.png"

DESTEKLENEN_UZANTILAR = (".jpg", ".jpeg", ".png", ".bmp")
MEDIAPIPE_MODEL       = PROJE_KOKU / "models" / "blaze_face_short_range.tflite"


def yol_coz(yol):
    """Veritabanında saklı bir dosya yolunu gerçek yola çevirir.

    Mutlak yol olduğu gibi döner; göreli yollar proje köküne göre çözülür
    (eski kayıtlarda `yuzler/ali.jpg` gibi göreli yollar vardı).
    """
    if not yol:
        return None
    p = Path(yol)
    return p if p.is_absolute() else PROJE_KOKU / p


def proje_goreli(yol):
    """Proje kökü altındaki bir yolu göreli (posix) metin olarak döndürür."""
    p = Path(yol).resolve()
    try:
        return p.relative_to(PROJE_KOKU).as_posix()
    except ValueError:
        return str(p)


# ── Veritabanı (PostgreSQL) ────────────────────────────────────────────
def veritabani_ayarlari() -> dict:
    ayar = {
        "host": os.getenv("YUZ_DB_HOST", "localhost"),
        "dbname": os.getenv("YUZ_DB_NAME", "yuz_tanima"),
        "user": os.getenv("YUZ_DB_USER", "postgres"),
        "port": os.getenv("YUZ_DB_PORT", "5432"),
        "connect_timeout": int(os.getenv("YUZ_DB_TIMEOUT", "5")),
    }
    parola = os.getenv("YUZ_DB_PASSWORD")
    if parola:
        ayar["password"] = parola
    return ayar


# ── Yönetici girişi (DEMO amaçlı tek kullanıcı) ────────────────────────
def yonetici_bilgileri():
    """(kullanici, parola) döndürür; tanımlı değilse (None, None)."""
    return os.getenv("YUZ_ADMIN_USER"), os.getenv("YUZ_ADMIN_PASSWORD")


# ── Yüz tanıma / kamera sabitleri (özgün değerler korunmuştur) ─────────
BILDIRIM_BEKLEME_SN = 10          # aynı kişi için tekrar kayıt/bildirim aralığı
MODEL_ADI           = "VGG-Face"
MESAFE_METRIGI      = "cosine"
# DeepFace verification uses OpenCV's detector internally. Live camera face
# localization is handled separately by our MediaPipe Tasks detector in
# kamera.py, avoiding DeepFace's legacy MediaPipe graph asset requirement.
DEDEKTOR            = "opencv"
KARE_ATLAMA         = 20          # her N karede bir analiz
KAMERA_INDEKSI      = int(os.getenv("YUZ_KAMERA_INDEKSI", "0"))
MEDIAPIPE_MIN_GUVEN = 0.5
