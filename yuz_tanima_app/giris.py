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

        # Keep the Designer object names and authentication flow intact while
        # presenting an enterprise-oriented composition.
        self.setWindowTitle("Güvenli Erişim")
        self.setFixedSize(1100, 700)
        self.setStyleSheet("QMainWindow{background:#111827;} QStatusBar,QMenuBar{background:transparent;border:0;}")

        # The supplied logo contains a visible stock watermark; avoid showing it.
        self.logoLabel.hide()

        arka = self._pixmap_yukle(config.LOGIN_ARKAPLAN)
        if arka is not None:
            self.backgroundLabel.setPixmap(arka)
        self.backgroundLabel.setGeometry(0, 0, 1100, 700)
        self.backgroundLabel.setScaledContents(True)
        self.backgroundLabel.lower()

        self.sloganLabel.setGeometry(72, 190, 510, 210)
        self.sloganLabel.setText(
            '<span style="font-size:38px;font-weight:500;color:#FFFFFF;">Güvenli erişim.<br>Tek merkezden kontrol.</span>'
            '<br><br><span style="font-size:15px;font-weight:400;color:#E2EAF2;">Yüz doğrulama ve erişim kayıtları<br>bir arayüzde.</span>'
        )
        self.sloganLabel.setStyleSheet("background:transparent;border:0;font-family:'Segoe UI';")
        self.sloganLabel.raise_()

        self.loginFrame.setGeometry(665, 90, 365, 520)
        self.loginFrame.setStyleSheet("QFrame#loginFrame{background:rgba(245,249,252,224);border:1px solid rgba(255,255,255,199);border-radius:22px;}")
        self.titlelabel.setGeometry(34, 72, 295, 48)
        self.titlelabel.setText("Yönetici girişi")
        self.titlelabel.setStyleSheet("color:#20364B;font-size:25px;font-weight:500;font-family:'Segoe UI';background:transparent;border:0;")
        self.usernamelabel.setGeometry(34, 160, 295, 24)
        self.passwordLabel.setGeometry(34, 260, 295, 24)
        for label in (self.usernamelabel, self.passwordLabel):
            label.setStyleSheet("color:#60758A;font-size:12px;font-weight:500;font-family:'Segoe UI';background:transparent;border:0;padding:0;")
        self.usernamenput.setGeometry(34, 188, 297, 46)
        self.usernamenput.setPlaceholderText("Kullanıcı adınızı girin")
        self.passwordInput.setGeometry(34, 288, 297, 46)
        self.passwordInput.setPlaceholderText("Parolanızı girin")
        field_style = "QLineEdit{background:rgba(255,255,255,199);color:#20364B;border:1px solid #D5E0E9;border-radius:12px;padding:0 14px;font-size:13px;} QLineEdit:focus{background:#FFFFFF;border:1px solid #789DB8;}"
        self.usernamenput.setStyleSheet(field_style)
        self.passwordInput.setStyleSheet(field_style)
        self.loginButton.setGeometry(34, 370, 297, 48)
        self.loginButton.setText("Güvenli giriş   →")
        self.loginButton.setStyleSheet("QPushButton{background:#507A99;color:#FFFFFF;border:0;border-radius:12px;font-size:14px;font-weight:500;font-family:'Segoe UI';} QPushButton:hover{background:#416B8A;} QPushButton:pressed{background:#345A77;}")
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
