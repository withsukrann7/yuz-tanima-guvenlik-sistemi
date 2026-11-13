"""Yüz Tanıma Güvenlik Sistemi — başlatma noktası.
Çalıştırma:   python main.py
"""
import logging
import sys
import os
import importlib.util

# Windows'ta yolda Türkçe karakter varsa Qt eklenti klasörünü bulamayabiliyor
if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    _spec = importlib.util.find_spec("PyQt5")
    if _spec and _spec.submodule_search_locations:
        _p = os.path.join(list(_spec.submodule_search_locations)[0], "Qt5", "plugins", "platforms")
        if os.path.isdir(_p):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _p

# TensorFlow, PyQt5'ten ÖNCE ve ana thread'de yüklenmeli (Windows DLL çakışması
# için özgün projedeki çözüm korunmuştur). Yoksa uygulama yine açılır; kamera
# başlatılırken DeepFace eksikliği kullanıcıya bildirilir.
try:
    import tensorflow as _tf
    print(f"TensorFlow {_tf.__version__} yüklendi.")
except Exception as e:                      # noqa: BLE001
    print(f"UYARI: TensorFlow yüklenemedi: {e}")

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

from yuz_tanima_app import config 


def _logging_kur():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.UYGULAMA_LOG_DOSYASI, encoding="utf-8"),
        ],
    )


def main() -> int:
    _logging_kur()
    log = logging.getLogger("main")
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    try:
        from yuz_tanima_app.giris import LoginWindow
        pencere = LoginWindow()
    except Exception as e:                  # noqa: BLE001
        log.exception("Giriş penceresi açılamadı")
        QMessageBox.critical(None, "Başlatılamadı", str(e))
        return 1

    if not all(config.yonetici_bilgileri()):
        log.warning("YUZ_ADMIN_USER / YUZ_ADMIN_PASSWORD tanımlı değil; giriş yapılamaz (.env.example'a bakın).")
    log.warning("DEMO giriş doğrulaması kullanılıyor; üretim güvenliği sağlamaz.")

    pencere.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
