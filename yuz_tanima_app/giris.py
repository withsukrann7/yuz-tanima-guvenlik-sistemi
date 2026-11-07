"""Giriş (login) penceresi.

NOT: Kimlik doğrulama tek bir DEMO yönetici hesabına dayanır ve üretim
güvenliği sağlamaz (parola düz metin, deneme sınırı yok). Bilgiler koda
gömülü değildir; YUZ_ADMIN_USER / YUZ_ADMIN_PASSWORD ortam değişkenlerinden
(.env) okunur.
"""
import hmac
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.uic import loadUi

from . import config

logger = logging.getLogger(__name__)


def kimlik_dogru_mu(kullanici: str, parola: str) -> bool:
    """Girilen bilgileri yapılandırmadaki bilgilerle (sabit zamanlı) karşılaştırır.

    Yapılandırma eksikse her zaman False döner (varsayılan parola YOKTUR).
    """
    beklenen_k, beklenen_p = config.yonetici_bilgileri()
    if not beklenen_k or not beklenen_p:
        return False
    k_ok = hmac.compare_digest(kullanici.encode("utf-8"), beklenen_k.encode("utf-8"))
    p_ok = hmac.compare_digest(parola.encode("utf-8"), beklenen_p.encode("utf-8"))
    return k_ok and p_ok


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if not config.LOGIN_UI.exists():
            raise FileNotFoundError(
                f"Arayüz dosyası bulunamadı: {config.LOGIN_UI}\n"
                "ui/login.ui dosyasını proje köküne (ui/ klasörü) kopyalayın.")
        loadUi(str(config.LOGIN_UI), self)

        logo = self._pixmap_yukle(config.LOGO_DOSYASI)
        if logo is not None:
            self.logoLabel.setPixmap(logo.scaled(100, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logoLabel.setAlignment(Qt.AlignCenter)

        arka = self._pixmap_yukle(config.LOGIN_ARKAPLAN)
        if arka is not None:
            self.backgroundLabel.setPixmap(arka)
        self.backgroundLabel.setGeometry(0, 0, 1100, 700)
        self.backgroundLabel.setScaledContents(True)
        self.backgroundLabel.lower()

        self.loginFrame.setGeometry(620, 80, 360, 520)
        self.loginFrame.raise_()

        self.loginButton.clicked.connect(self.giris_yap)

    @staticmethod
    def _pixmap_yukle(yol):
        pix = QPixmap(str(yol))
        if pix.isNull():
            logger.warning("Görsel yüklenemedi veya bulunamadı: %s", yol)
            return None
        return pix

    def giris_yap(self):
        # 'usernamenput' yazım hatası ui/login.ui içindeki nesne adıdır; değiştirilmemiştir.
        kullanici_adi = self.usernamenput.text()
        sifre = self.passwordInput.text()

        k, p = config.yonetici_bilgileri()
        if not k or not p:
            QMessageBox.critical(
                self, "Yapılandırma eksik",
                "Yönetici giriş bilgileri tanımlı değil.\n"
                ".env.example dosyasını .env olarak kopyalayıp YUZ_ADMIN_USER ve "
                "YUZ_ADMIN_PASSWORD değerlerini doldurun.")
            return

        if kimlik_dogru_mu(kullanici_adi, sifre):
            from .dashboard import Dashboard     # ağır modüller giriş sonrası yüklenir
            self.dashboard = Dashboard()
            self.dashboard.showMaximized()
            self.close()
        else:
            QMessageBox.warning(self, "Hata", "Kullanıcı adı veya Şifre yanlış!")
