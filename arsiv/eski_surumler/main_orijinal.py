# ARŞİV: yeniden yapılandırma öncesi özgün dosya (çalıştırılmaz). Gizli değerler kaldırıldı.
import os
import sys

# Dosyaların bulunduğu dizin (chdir yapmadan)
_BASE = os.path.dirname(os.path.abspath(__file__))

# TensorFlow'u en başta ana thread'de yükle
try:
    import tensorflow as _tf
    print(f"TensorFlow {_tf.__version__} yüklendi.")
except Exception as e:
    print(f"TensorFlow yüklenemedi: {e}")

from PyQt5.QtCore import Qt 
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.uic import loadUi
from dashboard_integrated import Dashboard

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi(os.path.join(_BASE, "ui", "login.ui"), self)
        logo_pixmap = QPixmap(os.path.join(_BASE, "logo.png"))
        scaled_logo = logo_pixmap.scaled(100,50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logoLabel.setPixmap(scaled_logo)
        self.logoLabel.setAlignment(Qt.AlignCenter)

        # Arka plan görselini ata
        pixmap = QPixmap(os.path.join(_BASE, "login_bg.png"))
        self.backgroundLabel.setPixmap(pixmap)
        self.backgroundLabel.lower()

        # Buton olaylarını bağla
        self.loginButton.clicked.connect(self.giris_yap)
        # Arka plan labelını tam pencere boyutuna getir
        self.backgroundLabel.setGeometry(0, 0, 1100, 700)
        self.backgroundLabel.setScaledContents(True)
        self.backgroundLabel.lower()  # En alta gönder

        # Login kartını arka planın üstüne taşı
        self.loginFrame.setGeometry(620, 80, 360, 520)
        self.loginFrame.raise_()  # En üste getir

        

    def giris_yap(self):
        kullanici_adi = self.usernamenput.text()
        sifre = self.passwordInput.text()
        if kullanici_adi == "admin" and sifre == "<GIZLI-KALDIRILDI>":
            self.dashboard = Dashboard()
            self.dashboard.showMaximized()
            self.close() #giriş ekranını kapat.
        else:
            QMessageBox.warning(self,"Hata","Kullanıcı adı veya Şifre yanlış!")
    def _ekran_goruntusu(self):
        from datetime import datetime
        masa_ustu = os.path.join(os.path.expanduser("~"), "Desktop")
        dosya_adi = f"kamera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        tam_yol = os.path.join(masa_ustu, dosya_adi)
        pixmap = self.kamera_label.grab()
        if pixmap.save(tam_yol):
            QMessageBox.information(self, "Ekran Görüntüsü", f"✅ Masaüstüne kaydedildi:\n{dosya_adi}")
        else:
            QMessageBox.warning(self, "Hata", "Kaydedilemedi.")
        

    

app = QApplication(sys.argv)
pencere = LoginWindow()
pencere.show()
sys.exit(app.exec_())
