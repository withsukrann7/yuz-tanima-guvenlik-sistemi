"""Ana pencere (dashboard): ana sayfa, yüz kaydı, kullanıcı listesi, canlı izleme, geçmiş."""
import logging
import os
import shutil
from datetime import datetime, timedelta

import cv2
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from . import config, veritabani, yuz_tanima
from .yuz_bulucu import YuzBulucu
from .arayuz_ortak import *
from .kamera import KameraThread

logger = logging.getLogger(__name__)

CAMERA_EVENT_LABELS = {
    "CAMERA_BLK_ACTIVE": "Kamera görüntüsü engellenmiş olabilir",
    "CAMERA_BLK_RESOLVED": "Kamera görüntüsü normale döndü",
    "CAMERA_OCC_ACTIVE": "Kamera görüntüsü kapatılmış olabilir",
    "CAMERA_OCC_RESOLVED": "Kamera görüntüsü yeniden açıldı",
    "CAMERA_FRZ_ACTIVE": "Kamera görüntüsü donmuş olabilir",
    "CAMERA_FRZ_RESOLVED": "Kamera görüntüsü yeniden değişiyor",
    "CAMERA_READ_ACTIVE": "Kameradan görüntü karesi alınamadı",
    "CAMERA_READ_RESOLVED": "Kamera görüntüsü yeniden alınıyor",
}


def camera_event_label(status):
    return CAMERA_EVENT_LABELS.get(status)


class CameraWarningDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Şüpheli Kamera Durumu")
        self.setMinimumWidth(440)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet("QDialog{background:#FFFFFF;} QLabel{font-family:'Segoe UI';}")

        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        stripe = QFrame(); stripe.setFixedHeight(7); stripe.setStyleSheet("background:#B4232F;border:none;")
        layout.addWidget(stripe)
        content = QVBoxLayout(); content.setContentsMargins(24,20,24,20); content.setSpacing(14)
        layout.addLayout(content)

        heading = QHBoxLayout(); heading.setSpacing(12)
        icon = QLabel("!"); icon.setFixedSize(42,42); icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background:#FCE8E9;color:#B4232F;border-radius:21px;font-size:23px;font-weight:700;")
        heading.addWidget(icon)
        text_column = QVBoxLayout(); text_column.setSpacing(4)
        title = QLabel("Şüpheli kamera durumu")
        title.setStyleSheet("color:#252B36;font-size:17px;font-weight:700;")
        text_column.addWidget(title)
        severity = QLabel("YÜKSEK ÖNEM")
        severity.setStyleSheet("background:#B4232F;color:#FFFFFF;border-radius:8px;padding:4px 8px;font-size:10px;font-weight:700;")
        severity.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        text_column.addWidget(severity); heading.addLayout(text_column); heading.addStretch()
        content.addLayout(heading)

        description = QLabel(message)
        description.setWordWrap(True)
        description.setStyleSheet("background:#FFF5F5;color:#5C252A;border:1px solid #F2C7CA;border-radius:10px;padding:13px;font-size:13px;")
        content.addWidget(description)

        buttons = QHBoxLayout(); buttons.addStretch()
        close_button = QPushButton("Kapat"); close_button.setMinimumSize(100,36)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setStyleSheet("QPushButton{background:#FFFFFF;color:#5B6472;border:1px solid #D5D9E0;border-radius:8px;padding:0 16px;font-size:12px;font-weight:600;} QPushButton:hover{background:#F4F5F7;}")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button); content.addLayout(buttons)


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Güvenlik Operasyonları")
        self.setMinimumSize(1200, 750)
        self.setFont(QFont("Segoe UI", 10, QFont.Normal))
        self.setStyleSheet("QMainWindow{background:#D9E8F3;} QToolTip{background:#29445C;color:#FFFFFF;border:1px solid #86A8C1;padding:6px 8px;border-radius:7px;} QScrollBar:vertical{background:transparent;width:9px;margin:2px;} QScrollBar::handle:vertical{background:#9FB8CA;border-radius:4px;min-height:28px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")

        self._kamera_thread = None
        self._takili_threadler = []     # zamanında durmayan thread'ler (GC'den korunur)
        self._db_hata_metni = ""
        self._kamera_bildirim_kapananlar = set()
        self._kamera_bildirimleri = {}

        # DeepFace'i ana thread'de önceden yükle (thread'de DLL sorunu olur).
        # Başarısızlık _baslangic_kontrolleri içinde kullanıcıya bildirilir.
        yuz_tanima.deepface_yukle()
        merkez = QWidget()
        merkez.setObjectName("appCanvas")
        merkez.setStyleSheet("QWidget#appCanvas{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #D9E8F3,stop:0.52 #BBD3E3,stop:1 #E5EEF3);}")
        self.setCentralWidget(merkez)
        ana = QHBoxLayout(merkez); ana.setContentsMargins(0,0,0,0); ana.setSpacing(0)
        ana.addWidget(self._sol_menu())

        self.stack = QStackedWidget(); self.stack.setStyleSheet("background:transparent;border:0;")
        ana.addWidget(self.stack)

        self.stack.addWidget(self._dashboard_sayfasi())    # 0
        self.stack.addWidget(self._yuz_kayit_sayfasi())    # 1
        self.stack.addWidget(self._kullanici_sayfasi())    # 2
        self.stack.addWidget(self._canli_izleme_sayfasi()) # 3
        self.stack.addWidget(self._gecmis_sayfasi())       # 4
        self.stack.setCurrentIndex(0)

        self._dashboard_yenile()
        yt = QTimer(self); yt.timeout.connect(self._dashboard_yenile); yt.start(30000)
        QTimer.singleShot(400, self._baslangic_kontrolleri)

    def closeEvent(self, event):
        """Pencere kapanırken kamera thread'ini düzgün durdur."""
        self._kamera_durdur()
        event.accept()

    # ──────────────────────────────────────
    #  SOL MENÜ
    # ──────────────────────────────────────
    def _sol_menu(self):
        w = QWidget(); w.setFixedWidth(242); w.setStyleSheet("background:rgba(31,58,79,240);border-top-right-radius:20px;border-bottom-right-radius:20px;")
        lay = QVBoxLayout(w); lay.setContentsMargins(18,25,18,20); lay.setSpacing(4)

        logo = QLabel("Güvenlik Merkezi")
        logo.setStyleSheet("color:#F6FAFD;font-size:16px;font-weight:500;font-family:'Segoe UI';border:none;padding-bottom:4px;")
        lay.addWidget(logo)
        alt = QLabel("ERİŞİM VE İZLEME")
        alt.setStyleSheet("color:rgba(232,242,249,158);font-size:10px;font-family:'Segoe UI';border:none;padding-bottom:4px;letter-spacing:1px;")
        lay.addWidget(alt)

        br = QHBoxLayout()
        bl = QLabel("Uyarılar"); bl.setStyleSheet("color:rgba(241,247,251,184);font-size:11px;border:none;")
        br.addWidget(bl); br.addStretch()
        self.rozet = QLabel("0"); self.rozet.setFixedSize(20,20); self.rozet.setAlignment(Qt.AlignCenter)
        self.rozet.setStyleSheet("background:#C86770;color:white;border-radius:10px;font-size:11px;font-weight:500;border:none;")
        self.rozet.hide(); br.addWidget(self.rozet); lay.addLayout(br)

        self._db_uyari = QLabel("⚠  Veritabanı bağlantısı yok")
        self._db_uyari.setWordWrap(True)
        self._db_uyari.setStyleSheet("background:#A94F5A;color:white;border-radius:8px;padding:7px 9px;font-size:11px;font-weight:500;")
        self._db_uyari.hide(); lay.addWidget(self._db_uyari)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:rgba(255,255,255,31);margin:8px 0;"); lay.addWidget(sep)

        self._menu_btns = []
        for ikon, isim, idx in [("01","Ana Sayfa",0),("02","Yüz Kaydı",1),("03","Kullanıcı Listesi",2),("04","Canlı İzleme",3),("05","Geçmiş Kayıtları",4)]:
            btn = QPushButton(f"  {ikon}  {isim}"); btn.setFixedHeight(44); btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._menu_stili(False))
            btn.clicked.connect(lambda _, i=idx: self._git(i))
            lay.addWidget(btn); self._menu_btns.append(btn)

        lay.addStretch()
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:rgba(255,255,255,31);margin-bottom:8px;"); lay.addWidget(sep2)

        cikis = QPushButton("  Oturumu Kapat"); cikis.setFixedHeight(44); cikis.setCursor(Qt.PointingHandCursor)
        cikis.setStyleSheet("QPushButton{background:rgba(255,255,255,10);color:#F0C6C9;border:1px solid rgba(240,198,201,71);border-radius:10px;font-size:13px;font-family:'Segoe UI';text-align:left;padding-left:8px;}"
                            "QPushButton:hover{background:rgba(255,255,255,26);}")
        cikis.clicked.connect(self._cikis); lay.addWidget(cikis)
        self._menu_btns[0].setStyleSheet(self._menu_stili(True))
        return w

    def _menu_stili(self, aktif):
        if aktif:
            return "QPushButton{background:rgba(224,239,248,46);color:#FFFFFF;border:1px solid rgba(255,255,255,46);border-left:3px solid #B5D6EA;border-radius:10px;font-size:13px;font-weight:500;font-family:'Segoe UI';text-align:left;padding-left:8px;}"
        return ("QPushButton{background:transparent;color:rgba(238,246,251,199);border:1px solid transparent;border-radius:10px;font-size:13px;font-family:'Segoe UI';text-align:left;padding-left:8px;}"
                "QPushButton:hover{background:rgba(255,255,255,23);color:white;border-color:rgba(255,255,255,26);}")

    def _git(self, idx):
        for i, b in enumerate(self._menu_btns): b.setStyleSheet(self._menu_stili(i == idx))
        self.stack.setCurrentIndex(idx)
        # Veriler başka yerlerden değişmiş olabilir; sayfaya girerken tazele
        if idx == 0: self._dashboard_yenile()
        elif idx == 2: self._kullanicilari_yukle()
        elif idx == 3: self._canli_paneli_yenile()
        elif idx == 4: self._gecmis_yukle()

    def _cikis(self):
        r = QMessageBox.question(self,"Çıkış","Çıkmak istediğinize emin misiniz?",QMessageBox.Yes|QMessageBox.No)
        if r == QMessageBox.Yes:
            self._kamera_durdur()
            QApplication.quit()

    # ──────────────────────────────────────
    #  VERİTABANI YARDIMCILARI
    # ──────────────────────────────────────
    def _db_durumu_ayarla(self, mesaj: str):
        self._db_hata_metni = mesaj
        self._db_uyari.setVisible(bool(mesaj))
        self._db_uyari.setToolTip(mesaj)

    def _db(self, sorgu, parametreler=(), *, getir=True):
        """Sorgu çalıştırır. Hata YUTULMAZ: loglanır ve kenar çubuğunda
        kalıcı uyarı gösterilir; okuma için [] / yazma için False döner."""
        try:
            sonuc = veritabani.calistir(sorgu, parametreler, getir=getir)
        except veritabani.VeritabaniHatasi as e:
            logger.error("Veritabanı hatası: %s", e)
            self._db_durumu_ayarla(str(e))
            return [] if getir else False
        self._db_durumu_ayarla("")
        return sonuc if getir else True

    def _db_kaydet(self, islem, *args) -> bool:
        try:
            islem(*args)
        except veritabani.VeritabaniHatasi as e:
            logger.error("Veritabanı kayıt hatası: %s", e)
            self._db_durumu_ayarla(str(e))
            return False
        self._db_durumu_ayarla("")
        return True

    def _baslangic_kontrolleri(self):
        ok, mesaj = veritabani.durum_kontrolu()
        if not ok:
            self._db_durumu_ayarla(mesaj)
            QMessageBox.warning(
                self, "Veritabanı",
                "Veritabanına erişilemedi veya tablolar eksik:\n\n" + mesaj +
                "\n\nUygulama SINIRLI MODDA çalışacak: giriş kayıtları saklanmaz, "
                "kullanıcı listesi/kaydı ve geçmiş çalışmaz.\n\n"
                "Çözüm: .env dosyasındaki YUZ_DB_* ayarlarını kontrol edin; tablolar için\n"
                "python -m yuz_tanima_app.veritabani kur")
        if not yuz_tanima.deepface_hazir():
            QMessageBox.warning(
                self, "DeepFace",
                "DeepFace yüklenemedi; canlı yüz tanıma başlatılamaz.\n"
                "pip install -r requirements.txt komutunu çalıştırın. Ayrıntı: security_system.log")

    # ──────────────────────────────────────
    #  KAMERA THREAD YÖNETİMİ
    # ──────────────────────────────────────
    def _kamera_aktif_mi(self) -> bool:
        th = self._kamera_thread
        return th is not None and th.isRunning()

    def _kamera_baslat(self) -> bool:
        if self._kamera_aktif_mi():
            return True
        if not yuz_tanima.deepface_hazir():
            QMessageBox.critical(self, "DeepFace yok",
                "DeepFace yüklenemediği için yüz tanıma başlatılamıyor.\n"
                "pip install -r requirements.txt komutunu çalıştırıp uygulamayı yeniden başlatın.")
            return False
        try:
            th = KameraThread()
        except Exception as e:
            logger.exception("Kamera başlatılamadı")
            QMessageBox.critical(self, "Kamera başlatılamadı", str(e))
            return False
        for u in th.recognizer.uyarilar:
            logger.warning(u)
        # Kayıtlı yüz yoksa her yüz 'BİLİNMEYEN' sayılır; bu beklenen davranıştır, uyarı gösterilmez.
        th.yeni_frame.connect(self._frame_guncelle)
        th.yetkili_giris.connect(self._yetkili_islemi)
        th.yetkisiz_giris.connect(self._yetkisiz_olay)
        th.camera_event_changed.connect(self._kamera_olayi_guncellendi)
        th.hata.connect(self._kamera_hatasi)
        th.finished.connect(lambda t=th: self._kamera_bitti(t))
        self._kamera_thread = th
        th.start()
        logger.info("Kamera başlatıldı.")
        return True

    def _kamera_durdur(self):
        th, self._kamera_thread = self._kamera_thread, None
        if th is None:
            return
        camera_name = f"Kamera {th.camera_index + 1}"
        for event_type in veritabani.CAMERA_EVENT_STATUSES:
            try:
                # Operator stop closes any open incident at the stop action.
                veritabani.enqueue_camera_event_transition(camera_name, event_type, False)
            except Exception:
                logger.exception(
                    "Kamera durdurulurken açık olay kapatılamadı: camera=%s type=%s",
                    camera_name, event_type,
                )
        th.blockSignals(True)            # durma sırasında gelen eski sinyalleri yok say
        if not th.stop():
            logger.error("Kamera thread'i zamanında durmadı; arka planda bitmesi bekleniyor.")
            self._takili_threadler.append(th)
        logger.info("Kamera durduruldu.")
        QTimer.singleShot(350, self._dashboard_yenile)
        QTimer.singleShot(1000, self._dashboard_yenile)

    def _kamera_bitti(self, th):
        """Thread kullanıcı istemeden sonlandıysa (kamera yok/bağlantı koptu) arayüzü sıfırla."""
        if th is not self._kamera_thread:
            return
        self._kamera_thread = None
        self._kamera_ui_ayarla(False)

    @pyqtSlot(str)
    def _kamera_hatasi(self, mesaj: str):
        if mesaj.startswith("Şüpheli kamera durumu:"):
            CameraWarningDialog(mesaj, self).exec_()
            QTimer.singleShot(500, self._dashboard_yenile)
            return
        QMessageBox.warning(self, "Kamera / Analiz Hatası", mesaj)

    def _kamera_olayi_guncellendi(self, camera_name, event_type, active):
        """Refresh the overview after the queued camera transition reaches the DB."""
        QTimer.singleShot(350, self._dashboard_yenile)
        QTimer.singleShot(1000, self._dashboard_yenile)

    def _kamera_ui_ayarla(self, aktif: bool):
        if aktif:
            self.kamera_ac_btn.setText("⏹  Kamerayı Durdur")
            self.kamera_ac_btn.setStyleSheet("QPushButton{background:#B95B65;color:white;border:none;border-radius:10px;font-size:13px;font-weight:500;}QPushButton:hover{background:#A64C56;}")
            self.kamera_label.setText("")
            self.kamera_label.setStyleSheet("background:#0f172a;border:none;border-radius:8px;")
            self._fps_dot.setStyleSheet(f"color:{YESIL};font-size:12px;border:none;")
            self._fps_lbl.setText("Aktif  •  en çok ~30 FPS")
            self._kamera_durum_lbl.setText("Aktif Kamera")
            self._kamera_durum_lbl.setStyleSheet(f"background:{ANA_MAVI};color:white;border-radius:9px;padding:4px 12px;font-size:11px;font-weight:500;border:none;")
        else:
            self.kamera_ac_btn.setText("▶  Kamerayı Başlat")
            self.kamera_ac_btn.setStyleSheet(f"QPushButton{{background:{ANA_MAVI};color:white;border:none;border-radius:10px;font-size:13px;font-weight:500;}}QPushButton:hover{{background:#416B8A;}}")
            self.kamera_label.clear()
            self.kamera_label.setText("📷\n\nKamera 1 — Ana Giriş\n\nKamerayı başlatmak için\naşağıdaki butona basın")
            self.kamera_label.setStyleSheet("background:#0f172a;color:#6b7280;font-size:14px;border:none;margin:0 14px;")
            self._fps_dot.setStyleSheet(f"color:{YAZI_GRI};font-size:12px;border:none;")
            self._fps_lbl.setText("Pasif  •  —")
            self._kamera_durum_lbl.setText("Pasif Kamera")
            self._kamera_durum_lbl.setStyleSheet("background:#70899B;color:white;border-radius:9px;padding:4px 12px;font-size:11px;font-weight:500;border:none;")
        self._dashboard_yenile()
        self._canli_paneli_yenile()

    # ──────────────────────────────────────
    #  SİNYAL ALICILAR
    # ──────────────────────────────────────
    @pyqtSlot(QImage)
    def _frame_guncelle(self, qimage: QImage):
        """Her kare buraya gelir → kamera_label güncellenir."""
        if self._kamera_thread is None:
            return
        pix = QPixmap.fromImage(qimage)
        scaled = pix.scaled(
            self.kamera_label.width(),
            self.kamera_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.kamera_label.setPixmap(scaled)

    @pyqtSlot(str, float)
    def _yetkili_islemi(self, isim: str, guven: float):
        """Yetkili tespit → DB'ye kaydet + paneller yenile."""
        if self._db_kaydet(veritabani.yetkili_giris_kaydet, isim):
            logger.info("✅ Yetkili giriş kaydedildi: %s (%.0f%%)", isim, guven * 100)
        else:
            logger.error("Yetkili giriş veritabanına YAZILAMADI: %s", isim)
        self._dashboard_yenile()
        self._canli_paneli_yenile()

    @pyqtSlot(str, str)
    def _yetkisiz_olay(self, foto_yolu: str, saat_str: str):
        """Kameradan gelen YENİ yetkisiz tespit → DB kaydı + rozet + uyarı penceresi."""
        if not self._db_kaydet(veritabani.yetkisiz_giris_kaydet, foto_yolu):
            logger.error("Yetkisiz giriş veritabanına YAZILAMADI: %s", foto_yolu)
        try:
            mevcut = int(self.rozet.text())
        except Exception:
            mevcut = 0
        self.rozet.setText(str(mevcut + 1)); self.rozet.show()
        self._yetkisiz_foto_goster(foto_yolu, saat_str)
        self._dashboard_yenile()
        self._canli_paneli_yenile()

    def _yetkisiz_foto_goster(self, foto_yolu: str, saat_str: str):
        """Var olan bir yetkisiz kaydın fotoğrafını göster (yeni kayıt OLUŞTURMAZ)."""
        if foto_yolu:
            foto_yolu = str(config.yol_coz(foto_yolu))
        YetkisizUyariDiyalog(foto_yolu, saat_str, self).exec_()

    # ──────────────────────────────────────
    #  YARDIMCILAR
    # ──────────────────────────────────────
    def _sayfa_wrap(self, baslik_txt, alt_txt):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w); lay.setContentsMargins(34,30,34,30); lay.setSpacing(0)
        lay.addWidget(baslik_label(baslik_txt))
        sub = alt_baslik_label(alt_txt); sub.setContentsMargins(0,4,0,20); lay.addWidget(sub)
        return w, lay

    def _stat_kart(self, sayi, etiket, ikon, bg, fg):
        f = kart_frame()
        fl = QVBoxLayout(f); fl.setContentsMargins(18,16,18,16); fl.setSpacing(4)
        ust = QHBoxLayout()
        ik = QLabel(ikon); ik.setFixedSize(44,44); ik.setAlignment(Qt.AlignCenter)
        ik.setStyleSheet(f"background:{bg};border-radius:12px;border:none;font-size:20px;")
        ust.addWidget(ik); ust.addStretch()
        tr = QLabel("↗"); tr.setStyleSheet(f"font-size:18px;color:{fg};border:none;")
        ust.addWidget(tr); fl.addLayout(ust); fl.addSpacing(8)
        n = QLabel(str(sayi)); n.setStyleSheet(f"font-size:28px;font-weight:500;color:{YAZI_KOYU};font-family:'Segoe UI';border:none;")
        fl.addWidget(n)
        e = QLabel(etiket); e.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        fl.addWidget(e)
        return f

    # ══════════════════════════════════════
    #  SAYFA 0 — DASHBOARD
    # ══════════════════════════════════════
    def _dashboard_sayfasi(self):
        self._dash_w = QWidget(); self._dash_w.setStyleSheet("background:transparent;")
        ml = QVBoxLayout(self._dash_w); ml.setContentsMargins(34,30,34,30); ml.setSpacing(0)
        ml.addWidget(baslik_label("Genel Bakış"))
        sub = alt_baslik_label("Güvenlik sisteminizin güncel durumu ve erişim kayıtları"); sub.setContentsMargins(0,4,0,20); ml.addWidget(sub)
        self._dash_icerik = QWidget(); self._dash_icerik_lay = QVBoxLayout(self._dash_icerik); self._dash_icerik_lay.setSpacing(16)
        ml.addWidget(self._dash_icerik); ml.addStretch()
        return self._dash_w

    def _dashboard_yenile(self):
        while self._dash_icerik_lay.count():
            item = self._dash_icerik_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()

        bugun = datetime.now().date()

        def q0(sql, p=None): r = self._db(sql, p); return r[0][0] if r else 0
        toplam_k = q0("SELECT COUNT(*) FROM yetkili_kisiler")
        bugun_g  = q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        t_den    = q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND LEFT(durum, 7) <> %s",(bugun,"CAMERA_"))
        y_say    = q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        basari   = round(bugun_g/t_den*100,1) if t_den>0 else 0

        krow = QHBoxLayout(); krow.setSpacing(16)
        for sayi, etiket, ikon, bg, fg in [
            (toplam_k,"Toplam Kullanıcı","ID","#EEF0FF","#5141B8"),
            (bugun_g,"Bugünkü Giriş","✓","#E8F5F0","#16846D"),
            (1 if self._kamera_aktif_mi() else 0,"Aktif Kamera","◉","#F0EDFA","#7156B8"),
            (f"%{basari}","Başarı Oranı","%","#F8F0E4","#A96C22"),
        ]:
            krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))
        self._dash_icerik_lay.addLayout(krow)

        uyarilar = self._db("SELECT foto_yolu,tarih,saat FROM yetkisiz_kayitlar WHERE tarih=%s ORDER BY saat DESC LIMIT 5",(bugun,))
        if uyarilar:
            uk = QFrame(); uk.setStyleSheet("background:rgba(255,246,247,235);border-radius:16px;border:1px solid #E9C5C9;")
            ukl = QVBoxLayout(uk); ukl.setContentsMargins(18,14,18,14); ukl.setSpacing(8)
            ur = QHBoxLayout()
            bu = QLabel("Yetkisiz Erişim Uyarıları"); bu.setStyleSheet("font-size:14px;font-weight:500;color:#A94F5A;border:none;")
            ur.addWidget(bu); ur.addStretch()
            sb = QLabel(f"{len(uyarilar)} Uyarı"); sb.setStyleSheet("background:#C86770;color:white;border-radius:9px;padding:4px 10px;font-size:11px;font-weight:500;border:none;")
            ur.addWidget(sb); ukl.addLayout(ur)
            for foto, tarih, saat in uyarilar:
                sr = QHBoxLayout(); sr.setSpacing(12)
                zl = QLabel(str(saat)[:8]); zl.setStyleSheet("font-size:12px;color:#A94F5A;font-weight:500;border:none;min-width:65px;")
                sr.addWidget(zl)
                ml2 = QLabel("Tanımlanamayan kişi tespit edildi — Kamera 1"); ml2.setStyleSheet("font-size:13px;color:#6E4B51;border:none;")
                sr.addWidget(ml2); sr.addStretch()
                fb = QPushButton("Fotoğrafı Gör"); fb.setFixedHeight(28); fb.setCursor(Qt.PointingHandCursor)
                fb.setStyleSheet("QPushButton{background:#B95B65;color:white;border:none;border-radius:9px;font-size:11px;padding:0 12px;}QPushButton:hover{background:#A64C56;}")
                fb.clicked.connect(lambda _,f=foto or "",s=str(saat)[:8]: self._yetkisiz_foto_goster(f,s))
                sr.addWidget(fb); ukl.addLayout(sr); ukl.addWidget(sep_cizgi("#E9C5C9"))
            self.rozet.setText(str(len(uyarilar))); self.rozet.show()
            self._dash_icerik_lay.addWidget(uk)

        arow = QHBoxLayout(); arow.setSpacing(16)

        sol = kart_frame()
        sl = QVBoxLayout(sol); sl.setContentsMargins(18,16,18,16); sl.setSpacing(0)
        br2 = QHBoxLayout(); br2.addWidget(baslik_label("Son Aktiviteler",14)); br2.addStretch()
        tg = QLabel("Tümünü Gör →"); tg.setStyleSheet(f"font-size:12px;color:{ANA_MAVI};border:none;"); tg.setCursor(Qt.PointingHandCursor)
        tg.mousePressEvent = lambda e: self._git(4); br2.addWidget(tg); sl.addLayout(br2); sl.addSpacing(12)

        aktiviteler = self._db("SELECT isim,durum,tarih,saat FROM giris_kayitlari ORDER BY tarih DESC,saat DESC LIMIT 5")
        for row in (aktiviteler or []):
            isim, durum, tarih, saat = row; ok = durum == "Basarili"
            event_label = camera_event_label(durum)
            resolved_event = event_label and durum.endswith("_RESOLVED")
            r = QHBoxLayout(); r.setSpacing(10)
            ic = QLabel("✓" if ok or resolved_event else ("!" if event_label else "✗")); ic.setFixedSize(28,28); ic.setAlignment(Qt.AlignCenter)
            bg = "#dcfce7" if ok or resolved_event else ("#fef3c7" if event_label else "#fee2e2")
            fg = "#15803d" if ok or resolved_event else ("#d97706" if event_label else "#dc2626")
            ic.setStyleSheet(f"background:{bg};border-radius:14px;color:{fg};font-size:13px;border:none;")
            r.addWidget(ic)
            col = QVBoxLayout(); col.setSpacing(1)
            al = QLabel(isim); al.setStyleSheet(f"font-size:12px;font-weight:500;color:{YAZI_KOYU};border:none;")
            cl2 = QLabel(event_label or durum); cl2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            col.addWidget(al); col.addWidget(cl2); r.addLayout(col); r.addStretch()
            sl2 = QLabel(str(saat)[:8] if saat else "-"); sl2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;"); r.addWidget(sl2)
            sl.addLayout(r); sl.addWidget(sep_cizgi())
        arow.addWidget(sol, 3)

        sag = kart_frame()
        sgl = QVBoxLayout(sag); sgl.setContentsMargins(18,16,18,16); sgl.setSpacing(0)
        sgl.addWidget(baslik_label("Sistem Durumu",14)); sgl.addSpacing(12)
        kamera_aktif = self._kamera_aktif_mi()
        for et, dg, rk in [
            ("Kamera Durumu", "🟢 Aktif" if kamera_aktif else "🔴 Pasif", YESIL if kamera_aktif else KIRMIZI),
            ("Bugünkü Tespit", str(t_den), YAZI_KOYU),
            ("Başarı Oranı", f"%{basari}", TURUNCU),
            ("Bilinmeyen", str(y_say), KIRMIZI)
        ]:
            r = QHBoxLayout(); e = QLabel(et); e.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};border:none;"); r.addWidget(e); r.addStretch()
            d = QLabel(dg); d.setStyleSheet(f"font-size:13px;font-weight:500;color:{rk};border:none;"); r.addWidget(d)
            sgl.addLayout(r); sgl.addWidget(sep_cizgi())
        arow.addWidget(sag, 2)
        self._dash_icerik_lay.addLayout(arow)

        camera_rows = self._db(
            "SELECT isim,tarih,saat,durum FROM giris_kayitlari "
            "WHERE LEFT(durum, 7) = %s ORDER BY id ASC",
            ("CAMERA_",),
        )
        camera_intervals = veritabani.camera_access_intervals(
            camera_rows, today=bugun, now=datetime.now()
        )
        for interval in camera_intervals:
            key = (interval["camera_name"], interval["event_type"], interval["start"])
            if interval["ongoing"] and key not in self._kamera_bildirim_kapananlar:
                self._kamera_bildirimleri[key] = interval
            elif key in self._kamera_bildirimleri:
                self._kamera_bildirimleri[key] = interval
        if self._kamera_bildirimleri:
            notice = QFrame(); notice.setStyleSheet("background:#FFF5F5;border:1px solid #E9AEB3;border-left:5px solid #B4232F;border-radius:12px;")
            nl = QVBoxLayout(notice); nl.setContentsMargins(16,12,16,12); nl.setSpacing(8)
            notice_title = QLabel("YÜKSEK ÖNEM  ·  Şüpheli kamera durumu")
            notice_title.setStyleSheet("font-size:13px;font-weight:700;color:#A21D29;border:none;")
            nl.addWidget(notice_title)
            for key, interval in list(self._kamera_bildirimleri.items()):
                detail_row = QHBoxLayout(); detail_row.setSpacing(10)
                state = "Kesinti sürüyor" if interval["ongoing"] else "Kesinti sona erdi"
                started = QLabel(f"{interval['camera_name']} · {state} · Başlangıç {interval['start'].strftime('%H:%M:%S')}")
                started.setStyleSheet("font-size:12px;color:#5C252A;border:none;")
                detail_row.addWidget(started); detail_row.addStretch()
                details_button = QPushButton("Saat ve süreyi gör")
                details_button.setCursor(Qt.PointingHandCursor); details_button.setFixedHeight(30)
                details_button.setStyleSheet("QPushButton{background:#B4232F;color:white;border:none;border-radius:8px;padding:0 12px;font-size:11px;font-weight:600;} QPushButton:hover{background:#8F1C26;}")
                details_button.clicked.connect(
                    lambda _, item=interval, notification_key=key:
                    self._kamera_kesinti_detayi_goster(item, notification_key)
                )
                detail_row.addWidget(details_button); nl.addLayout(detail_row)
            if nl.count() > 1:
                self._dash_icerik_lay.addWidget(notice)
        history = kart_frame()
        hl = QVBoxLayout(history); hl.setContentsMargins(18,16,18,16); hl.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(baslik_label("Kamera Erişim Geçmişi",14)); header.addStretch()
        count_label = QLabel(f"{len(camera_intervals)} kesinti")
        count_label.setStyleSheet("background:#EEF0FF;color:#5141B8;border-radius:9px;padding:4px 10px;font-size:11px;font-weight:500;border:none;")
        header.addWidget(count_label); hl.addLayout(header)
        if not camera_intervals:
            empty = QLabel("Bugün kamera erişim kesintisi kaydedilmedi.")
            empty.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;padding:4px 0;")
            hl.addWidget(empty)
        else:
            event_names = {
                "blocked": "Kamera görüntüsü engellendi",
                "occluded": "Kamera görüntüsü kapatıldı",
                "frozen": "Kamera görüntüsü dondu",
                "read_failure": "Kameraya erişim kesildi",
            }
            for interval in camera_intervals:
                row = QHBoxLayout(); row.setSpacing(12)
                start = interval["start"]
                start_label = QLabel(start.strftime("%d.%m %H:%M:%S"))
                start_label.setStyleSheet("font-size:12px;color:#A96C22;font-weight:500;border:none;min-width:120px;")
                row.addWidget(start_label)
                detail = QLabel(f"{interval['camera_name']} · {event_names.get(interval['event_type'], 'Kamera erişim kesintisi')}")
                detail.setStyleSheet(f"font-size:12px;color:{YAZI_KOYU};border:none;")
                row.addWidget(detail); row.addStretch()
                end_text = interval["end"].strftime("%H:%M:%S") if interval["end"] else "Devam ediyor"
                duration = interval["duration_seconds"]
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_text = f"{hours} sa {minutes} dk {seconds} sn" if hours else f"{minutes} dk {seconds} sn"
                tail = QLabel(f"{end_text} · {duration_text}")
                tail.setStyleSheet(f"font-size:11px;color:{KIRMIZI if interval['ongoing'] else YAZI_GRI};font-weight:500;border:none;")
                row.addWidget(tail)
                detail_button = QPushButton("Ayrıntı")
                detail_button.setCursor(Qt.PointingHandCursor); detail_button.setFixedHeight(27)
                detail_button.setStyleSheet("QPushButton{background:#FFFFFF;color:#A21D29;border:1px solid #E9AEB3;border-radius:7px;padding:0 9px;font-size:10px;font-weight:600;} QPushButton:hover{background:#FFF0F1;}")
                detail_button.clicked.connect(
                    lambda _, item=interval: self._kamera_kesinti_detayi_goster(item)
                )
                row.addWidget(detail_button)
                hl.addLayout(row)
                if interval is not camera_intervals[-1]:
                    hl.addWidget(sep_cizgi())
        self._dash_icerik_lay.addWidget(history)

    def _kamera_kesinti_detayi_goster(self, interval, notification_key=None):
        if notification_key is not None:
            self._kamera_bildirim_kapananlar.add(notification_key)
            self._kamera_bildirimleri.pop(notification_key, None)
            QTimer.singleShot(0, self._dashboard_yenile)
        start = interval["start"].strftime("%d.%m.%Y %H:%M:%S")
        end = interval["end"].strftime("%d.%m.%Y %H:%M:%S") if interval["end"] else "Devam ediyor"
        seconds = interval["duration_seconds"]
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        duration = f"{hours} sa {minutes} dk {secs} sn" if hours else f"{minutes} dk {secs} sn"
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Kamera Kesinti Ayrıntısı")
        dialog.setIcon(QMessageBox.Warning if interval["ongoing"] else QMessageBox.Information)
        dialog.setTextFormat(Qt.RichText)
        dialog.setText(
            f"<b>{interval['camera_name']}</b><br><br>"
            f"<b>Başlangıç:</b> {start}<br>"
            f"<b>Bitiş:</b> {end}<br>"
            f"<b>Toplam kapalı kalma:</b> {duration}"
        )
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.setStyleSheet("QMessageBox{background:white;} QLabel{color:#303744;font-family:'Segoe UI';font-size:13px;min-width:330px;} QPushButton{background:#B4232F;color:white;border:none;border-radius:7px;padding:7px 20px;font-weight:600;}")
        dialog.exec_()

    # ══════════════════════════════════════
    #  SAYFA 1 — YÜZ KAYIT
    # ══════════════════════════════════════
    def _yuz_kayit_sayfasi(self):
        w, lay = self._sayfa_wrap("Yüz Kaydı","Yeni yetkili kişi ekleyin")
        icerik = QHBoxLayout(); icerik.setSpacing(24)

        sol = kart_frame(); sl = QVBoxLayout(sol); sl.setContentsMargins(24,24,24,24); sl.setSpacing(14)
        sl.addWidget(baslik_label("Kişi Bilgileri",15))

        for attr, ph in [("_kayit_ad","Ad"),("_kayit_soyad","Soyad"),
                          ("_kayit_eposta","E-posta"),("_kayit_tel","Telefon"),("_kayit_cid","Çalışan ID")]:
            le = QLineEdit(); le.setPlaceholderText(ph); le.setFixedHeight(40); le.setStyleSheet(input_stili())
            setattr(self, attr, le); sl.addWidget(le)

        self._kayit_dep = QComboBox(); self._kayit_dep.setFixedHeight(40); self._kayit_dep.setStyleSheet(combobox_stili())
        self._kayit_dep.addItems(["Departman Seçin","Bilgi Teknolojileri","İnsan Kaynakları","Finans","Satış","Mühendislik","Güvenlik"])
        sl.addWidget(self._kayit_dep); sl.addStretch()
        icerik.addWidget(sol,2)

        sag = kart_frame(); sgl = QVBoxLayout(sag); sgl.setContentsMargins(24,24,24,24); sgl.setSpacing(14)
        sgl.addWidget(baslik_label("Fotoğraf",15))
        self.foto_onizleme = QLabel("📷\n\nFotoğraf Burada\nGörünecek"); self.foto_onizleme.setFixedSize(280,280)
        self.foto_onizleme.setAlignment(Qt.AlignCenter)
        self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px dashed #374151;color:#6b7280;font-size:14px;")
        self._yuklenen_foto = None
        sgl.addWidget(self.foto_onizleme, alignment=Qt.AlignCenter)
        foto_btn = mavi_btn("📁  Fotoğraf Seç",40); foto_btn.clicked.connect(self._foto_yukle); sgl.addWidget(foto_btn)
        kaydet_btn = mavi_btn("✅  Kaydet",44); kaydet_btn.clicked.connect(self._kullanici_kaydet); sgl.addWidget(kaydet_btn)
        sgl.addStretch(); icerik.addWidget(sag,1)

        lay.addLayout(icerik); lay.addStretch()
        return w

    def _foto_yukle(self):
        dosya, _ = QFileDialog.getOpenFileName(self,"Fotoğraf Seç","","Resim Dosyaları (*.jpg *.jpeg *.png *.bmp)")
        if dosya:
            ham = pixmap_yukle(dosya)
            if ham.isNull():
                QMessageBox.warning(self,"Geçersiz Fotoğraf","Seçilen dosya bir resim olarak açılamadı."); return
            pix = ham.scaled(self.foto_onizleme.width()-10,self.foto_onizleme.height()-10,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self.foto_onizleme.setPixmap(pix)
            self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px solid #4A3FC7;")
            self._yuklenen_foto = dosya

    def _yuz_say(self, goruntu) -> int:
        """Fotoğraftaki yüz sayısını MediaPipe ile bulur (kayıt öncesi kontrol)."""
        with YuzBulucu(video=False) as bulucu:
            return len(bulucu.tespit_et(goruntu))

    def _kullanici_kaydet(self):
        ad = self._kayit_ad.text().strip(); soyad = self._kayit_soyad.text().strip()
        eposta = self._kayit_eposta.text().strip(); tel = self._kayit_tel.text().strip()
        cid = self._kayit_cid.text().strip(); dep = self._kayit_dep.currentText()
        if not ad or not soyad: QMessageBox.warning(self,"Eksik","Ad ve soyad zorunludur!"); return
        if dep == "Departman Seçin": QMessageBox.warning(self,"Eksik","Lütfen departman seçin!"); return
        if not self._yuklenen_foto: QMessageBox.warning(self,"Fotoğraf Eksik","Lütfen fotoğraf yükleyin!"); return
        tam_ad = f"{ad} {soyad}"

        goruntu = yuz_tanima.gorsel_oku(self._yuklenen_foto)
        if goruntu is None:
            QMessageBox.warning(self,"Geçersiz Fotoğraf","Dosya okunamadı veya geçerli bir resim değil."); return
        try:
            yuz_sayisi = self._yuz_say(goruntu)
        except Exception as e:                     # yüz bulucu yoksa kayıt engellenmesin
            logger.warning("Kayıt öncesi yüz kontrolü yapılamadı: %s", e)
            yuz_sayisi = None
        if yuz_sayisi == 0:
            r = QMessageBox.question(self,"Yüz bulunamadı",
                "Bu fotoğrafta yüz algılanamadı; tanıma çalışmayabilir.\nYine de kaydedilsin mi?",
                QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes: return

        # Dosya adı: çalışan ID/ad (yol ayırıcı vb. karakterler temizlenir), çakışmada numara eklenir
        config.YUZLER_DIZINI.mkdir(parents=True, exist_ok=True)
        uzanti = os.path.splitext(self._yuklenen_foto)[1].lower() or ".jpg"
        temel = yuz_tanima.guvenli_dosya_adi(cid or tam_ad)
        hedef = config.YUZLER_DIZINI / f"{temel}{uzanti}"
        n = 2
        while hedef.exists():
            hedef = config.YUZLER_DIZINI / f"{temel}_{n}{uzanti}"; n += 1
        try:
            shutil.copy2(self._yuklenen_foto, hedef)
        except OSError as e:
            QMessageBox.critical(self,"Hata",f"Fotoğraf kopyalanamadı:\n{e}"); return

        basari = self._db(
            "INSERT INTO yetkili_kisiler (isim,departman,telefon,calisan_id,eposta,foto_yolu,durum) VALUES (%s,%s,%s,%s,%s,%s,'Aktif')",
            (tam_ad, dep, tel, cid, eposta, config.proje_goreli(hedef)), getir=False)

        if basari:
            if self._kamera_thread:
                self._kamera_thread.recognizer.reload()
            QMessageBox.information(self,"Başarılı",f"✅ {tam_ad} sisteme kaydedildi!")
            for wg in [self._kayit_ad,self._kayit_soyad,self._kayit_eposta,self._kayit_tel,self._kayit_cid]: wg.clear()
            self._kayit_dep.setCurrentIndex(0)
            self.foto_onizleme.setPixmap(QPixmap()); self.foto_onizleme.setText("📷\n\nFotoğraf Burada\nGörünecek")
            self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px dashed #374151;color:#6b7280;font-size:14px;")
            self._yuklenen_foto = None; self._kullanicilari_yukle()
        else:
            try: hedef.unlink()          # az önce oluşturduğumuz kopya; DB kaydı olmadan sahipsiz kalmasın
            except OSError: pass
            QMessageBox.critical(self,"Hata",f"Kayıt veritabanına yazılamadı:\n{self._db_hata_metni or 'bilinmeyen hata'}")

    # ══════════════════════════════════════
    #  SAYFA 2 — KULLANICI LİSTESİ
    # ══════════════════════════════════════
    def _kullanici_sayfasi(self):
        w, lay = self._sayfa_wrap("Kullanıcı Listesi","Sisteme kayıtlı tüm kullanıcıları görüntüleyin ve yönetin")
        self._kul_krow = QHBoxLayout(); self._kul_krow.setSpacing(14); lay.addLayout(self._kul_krow); lay.addSpacing(16)

        ar = QHBoxLayout(); ar.setSpacing(10)
        self._kullanici_arama = QLineEdit(); self._kullanici_arama.setPlaceholderText("🔍  İsim, e-posta veya ID ile ara..."); self._kullanici_arama.setFixedHeight(40); self._kullanici_arama.setStyleSheet(input_stili())
        self._kullanici_arama.textChanged.connect(self._kullanici_filtrele); ar.addWidget(self._kullanici_arama,3)
        self._kullanici_dep_filtre = QComboBox(); self._kullanici_dep_filtre.setFixedHeight(40); self._kullanici_dep_filtre.setStyleSheet(combobox_stili())
        self._kullanici_dep_filtre.addItems(["Tüm Departmanlar","Bilgi Teknolojileri","İnsan Kaynakları","Finans","Satış","Mühendislik","Güvenlik"])
        self._kullanici_dep_filtre.currentTextChanged.connect(self._kullanici_filtrele); ar.addWidget(self._kullanici_dep_filtre,1)
        yb = mavi_btn("+ Yeni Kullanıcı",40); yb.setFixedWidth(150); yb.clicked.connect(lambda: self._git(1)); ar.addWidget(yb)
        lay.addLayout(ar); lay.addSpacing(14)

        self.kullanici_tablosu = QTableWidget(); self.kullanici_tablosu.setColumnCount(7)
        self.kullanici_tablosu.setHorizontalHeaderLabels(["KULLANICI","ID","DEPARTMAN","TELEFON","SON ERİŞİM","DURUM","İŞLEMLER"])
        hh = self.kullanici_tablosu.horizontalHeader()
        for i, mod in enumerate([QHeaderView.Stretch,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents]):
            hh.setSectionResizeMode(i, mod)
        self.kullanici_tablosu.setStyleSheet(f"""
            QTableWidget{{background:rgba(250,253,255,240);border-radius:14px;border:1px solid rgba(255,255,255,220);gridline-color:#E8EFF4;font-family:'Segoe UI';}}
            QHeaderView::section{{background:rgba(231,241,248,245);padding:10px 8px;font-size:11px;font-weight:500;color:{YAZI_GRI};border:none;border-bottom:1px solid {SINIR};}}
            QTableWidget::item{{padding:8px;font-size:13px;color:{YAZI_KOYU};}}
            QTableWidget::item:selected{{background:#D8E7F1;color:{YAZI_KOYU};}}""")
        self.kullanici_tablosu.setEditTriggers(QTableWidget.NoEditTriggers)
        self.kullanici_tablosu.setSelectionBehavior(QTableWidget.SelectRows)
        self.kullanici_tablosu.verticalHeader().setVisible(False)
        self.kullanici_tablosu.setShowGrid(False)
        self._kullanici_verileri = []; self._kullanicilari_yukle()
        lay.addWidget(self.kullanici_tablosu)
        return w

    def _kullanicilari_yukle(self):
        while self._kul_krow.count():
            item = self._kul_krow.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        def q0(sql,p=None): r=self._db(sql,p); return r[0][0] if r else 0
        toplam = q0("SELECT COUNT(*) FROM yetkili_kisiler")
        aktif  = q0("SELECT COUNT(*) FROM yetkili_kisiler WHERE durum='Aktif'")
        pasif  = toplam - aktif
        dep_s  = q0("SELECT COUNT(DISTINCT departman) FROM yetkili_kisiler")
        for sayi, etiket, ikon, bg, fg in [(toplam,"Toplam Kullanıcı","👥","#dbeafe","#1d4ed8"),(aktif,"Aktif","✅","#dcfce7","#15803d"),(pasif,"Pasif","🔴","#fee2e2","#dc2626"),(dep_s,"Departman","🏢","#ede9fe","#7c3aed")]:
            self._kul_krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))

        rows = self._db("SELECT isim,calisan_id,departman,telefon,eposta,durum,foto_yolu FROM yetkili_kisiler ORDER BY isim") or []
        self._kullanici_verileri = []
        for r in rows:
            isim, kid, dep, tel, eposta, durum, foto = r
            gk = self._db("SELECT tarih,saat FROM giris_kayitlari WHERE isim=%s ORDER BY tarih DESC,saat DESC LIMIT 1",(isim,))
            son_str = sure_metni(datetime.combine(gk[0][0],gk[0][1])) if gk else "Hiç giriş yok"
            self._kullanici_verileri.append((isim, eposta or "-", kid or "-", dep or "-", tel or "-", son_str, durum or "Aktif", foto or ""))
        self._tablo_doldur()
        self._kullanici_filtrele()

    def _tablo_doldur(self):
        t = self.kullanici_tablosu; t.setRowCount(len(self._kullanici_verileri))
        for i, (ad, eposta, kid, dep, tel, son, durum, foto) in enumerate(self._kullanici_verileri):
            t.setRowHeight(i,52)
            kw = QWidget(); kw.setStyleSheet("background:transparent;")
            kl = QHBoxLayout(kw); kl.setContentsMargins(8,4,8,4); kl.setSpacing(10)
            kl.addWidget(avatar_widget(get_initials(ad),AVATAR_RENKLER[i%len(AVATAR_RENKLER)],34))
            ic = QVBoxLayout(); ic.setSpacing(0)
            nl = QLabel(ad); nl.setStyleSheet(f"font-size:13px;font-weight:500;color:{YAZI_KOYU};border:none;")
            ml2 = QLabel(eposta); ml2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            ic.addWidget(nl); ic.addWidget(ml2); kl.addLayout(ic); kl.addStretch(); t.setCellWidget(i,0,kw)
            for col, val in [(1,kid),(2,dep),(3,tel),(4,son)]:
                item = QTableWidgetItem(val); item.setTextAlignment(Qt.AlignCenter); t.setItem(i,col,item)
            dw = QWidget(); dw.setStyleSheet("background:transparent;")
            dl = QHBoxLayout(dw); dl.setContentsMargins(8,0,8,0); dl.setAlignment(Qt.AlignCenter)
            dlbl = QLabel(durum); dlbl.setStyleSheet(("background:#E4F2ED;color:#277763;" if durum=="Aktif" else "background:#F8E9EA;color:#A94F5A;")+"border-radius:10px;padding:3px 10px;font-size:11px;font-weight:500;")
            dl.addWidget(dlbl); t.setCellWidget(i,5,dw)
            iw = QWidget(); iw.setStyleSheet("background:transparent;")
            il = QHBoxLayout(iw); il.setContentsMargins(6,4,6,4); il.setSpacing(6); il.setAlignment(Qt.AlignCenter)
            for emoji, tip, stil, fn in [("✏️","Düzenle","background:#eff6ff;",None),("🗑️","Sil","background:#fff1f2;",lambda _,r=i:self._kullanici_sil(r)),("🖼️","Fotoğraf","background:#f0fdf4;",lambda _,a=ad,f=foto:self._foto_goster(a,f))]:
                b = QPushButton(emoji); b.setFixedSize(30,30); b.setToolTip(tip); b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"QPushButton{{{stil}border:none;border-radius:6px;font-size:14px;}}"); 
                if fn: b.clicked.connect(fn)
                il.addWidget(b)
            t.setCellWidget(i,6,iw)

    def _kullanici_filtrele(self):
        arama = self._kullanici_arama.text().lower().strip()
        dep = self._kullanici_dep_filtre.currentText()
        for i, (ad, eposta, kid, d, tel, son, durum, foto) in enumerate(self._kullanici_verileri):
            a_ok = arama=="" or arama in ad.lower() or arama in kid.lower() or arama in tel.lower()
            d_ok = dep=="Tüm Departmanlar" or dep==d
            self.kullanici_tablosu.setRowHidden(i, not (a_ok and d_ok))

    def _yuz_dosyalarini_arsivle(self, kid, foto):
        """Silinen kullanıcının yüz dosyalarını tanıma klasörlerinden arsiv/silinen_yuzler/ altına
        TAŞIR (silmez). Aksi halde silinen kişi known_faces/ üzerinden hâlâ tanınırdı."""
        yonetilen = (config.YUZLER_DIZINI.resolve(), config.BILINEN_YUZLER_DIZINI.resolve())
        adaylar = []
        p = config.yol_coz(foto) if foto else None
        if p is not None and p.exists():
            adaylar.append(p)
        if kid and kid != "-":
            anahtar = yuz_tanima.normalize(kid)
            for klasor in (config.YUZLER_DIZINI, config.BILINEN_YUZLER_DIZINI):
                if klasor.exists():
                    adaylar += [f for f in klasor.iterdir()
                                if f.is_file() and yuz_tanima.normalize(f.stem) == anahtar]
        damga = datetime.now().strftime("%Y%m%d_%H%M%S")
        for f in dict.fromkeys(adaylar):
            if f.resolve().parent not in yonetilen:
                continue                     # yönetilen klasörler dışındaki dosyalara dokunma
            try:
                config.ARSIV_SILINEN_YUZLER.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(config.ARSIV_SILINEN_YUZLER / f"{damga}_{f.name}"))
            except OSError as e:
                logger.error("Yüz dosyası arşivlenemedi (%s): %s", f, e)

    def _kullanici_sil(self, row):
        ad, _eposta, kid, _dep, _tel, _son, _durum, foto = self._kullanici_verileri[row]
        r = QMessageBox.question(self,"Kullanıcı Sil",f"<b>{ad}</b> adlı kullanıcıyı silmek istediğinize emin misiniz?",QMessageBox.Yes|QMessageBox.No)
        if r == QMessageBox.Yes:
            cid = "" if kid == "-" else kid
            if not self._db("DELETE FROM yetkili_kisiler WHERE isim=%s AND COALESCE(calisan_id,'')=%s",(ad,cid),getir=False):
                QMessageBox.critical(self,"Hata",f"Kullanıcı silinemedi:\n{self._db_hata_metni}")
                return
            self._yuz_dosyalarini_arsivle(kid, foto)
            if self._kamera_thread:
                self._kamera_thread.recognizer.reload()
            self._kullanicilari_yukle()

    def _foto_goster(self, ad, foto_yol):
        # Veritabanındaki yol göreli olabilir ("yuzler/ali.jpg"); proje köküne göre çöz
        foto_yol = str(config.yol_coz(foto_yol)) if foto_yol else ""
        if not foto_yol or not os.path.exists(foto_yol):
            foto_yol, _ = QFileDialog.getOpenFileName(self,f"{ad} — Fotoğraf Seç","","Resim Dosyaları (*.jpg *.jpeg *.png *.bmp)")
            if not foto_yol: return
        FotoDiyalog(ad, foto_yol, self).exec_()

    # ══════════════════════════════════════
    #  SAYFA 3 — CANLI İZLEME (OpenCV entegre)
    # ══════════════════════════════════════
    def _canli_izleme_sayfasi(self):
        w, lay = self._sayfa_wrap("Canlı Kamera İzleme","Gerçek zamanlı yüz tanıma ve izleme sistemi")
        icerik = QHBoxLayout(); icerik.setSpacing(16)
        sol = QVBoxLayout(); sol.setSpacing(12)

        kk_frame = kart_frame(); kk = QVBoxLayout(kk_frame); kk.setContentsMargins(14,12,14,12); kk.setSpacing(8)
        ust = QHBoxLayout(); ust.setSpacing(10)
        canli_c = QFrame(); canli_c.setStyleSheet("background:rgba(239,68,68,31);border-radius:10px;border:1px solid rgba(239,68,68,89);")
        ccl = QHBoxLayout(canli_c); ccl.setContentsMargins(10,5,10,5); ccl.setSpacing(6)
        cdot = QLabel("●"); cdot.setStyleSheet("color:#ef4444;font-size:10px;border:none;")
        ctxt = QLabel("CANLI"); ctxt.setStyleSheet("color:#B95B65;font-size:12px;font-weight:500;font-family:'Segoe UI';border:none;letter-spacing:1px;")
        ccl.addWidget(cdot); ccl.addWidget(ctxt); ust.addWidget(canli_c)
        self._saat_lbl = QLabel("--:--:--"); self._saat_lbl.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};border:none;"); ust.addWidget(self._saat_lbl); ust.addStretch()
        kk.addLayout(ust)

        # ── Kamera görüntüsü buraya gelir ──
        self.kamera_label = QLabel()
        self.kamera_label.setMinimumSize(560, 360)
        self.kamera_label.setAlignment(Qt.AlignCenter)
        self.kamera_label.setText("📷\n\nKamera 1 — Ana Giriş\n\nKamerayı başlatmak için\naşağıdaki butona basın")
        self.kamera_label.setStyleSheet("background:#0f172a;color:#6b7280;font-size:14px;border-radius:8px;border:none;")
        kk.addWidget(self.kamera_label)

        kad = QLabel("Kamera 1 — Ana Giriş"); kad.setAlignment(Qt.AlignCenter); kad.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;padding:4px 0;"); kk.addWidget(kad)
        sol.addWidget(kk_frame)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        kayit_btn = QPushButton("● Kayıt Başlat"); kayit_btn.setFixedHeight(38); kayit_btn.setCursor(Qt.PointingHandCursor)
        kayit_btn.setStyleSheet("QPushButton{background:#B95B65;color:white;border:none;border-radius:10px;font-size:13px;font-weight:500;padding:0 16px;}QPushButton:hover{background:#A64C56;}")
        btn_row.addWidget(kayit_btn)
        ekran_btn = QPushButton("📸  Ekran Görüntüsü"); ekran_btn.setFixedHeight(38); ekran_btn.setCursor(Qt.PointingHandCursor)
        ekran_btn.setStyleSheet(f"QPushButton{{background:rgba(250,253,255,210);color:{YAZI_KOYU};border:1px solid rgba(255,255,255,220);border-radius:10px;font-size:13px;padding:0 16px;}}QPushButton:hover{{background:#FFFFFF;}}")
        ekran_btn.clicked.connect(self._ekran_goruntusu); btn_row.addWidget(ekran_btn)
        btn_row.addStretch()

        self.kamera_ac_btn = mavi_btn("▶  Kamerayı Başlat", 38)
        self.kamera_ac_btn.setFixedWidth(165)
        self.kamera_ac_btn.clicked.connect(self._kamera_toggle)
        btn_row.addWidget(self.kamera_ac_btn)
        sol.addLayout(btn_row)

        alt_kart = kart_frame(); alt_kart.setFixedHeight(110)
        alt_kart.setStyleSheet("background:rgba(249,252,254,214);border-radius:14px;border:1px solid rgba(255,255,255,235);")
        ak = QHBoxLayout(alt_kart); ak.setContentsMargins(14,10,14,10); ak.setSpacing(14)
        mini = QLabel("📷"); mini.setFixedSize(100,70); mini.setAlignment(Qt.AlignCenter); mini.setStyleSheet("background:#0f172a;border-radius:6px;border:none;font-size:18px;"); ak.addWidget(mini)
        bilgi = QVBoxLayout(); bilgi.setSpacing(4)
        ki = QLabel("Kamera 1"); ki.setStyleSheet(f"font-size:14px;font-weight:500;color:{YAZI_KOYU};border:none;")
        ky = QLabel("Ana Giriş"); ky.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        bilgi.addWidget(ki); bilgi.addWidget(ky)
        fps_row = QHBoxLayout(); fps_row.setSpacing(6)
        self._fps_dot = QLabel("●"); self._fps_dot.setStyleSheet(f"color:{YAZI_GRI};font-size:12px;border:none;")
        self._fps_lbl = QLabel("Pasif  •  —"); self._fps_lbl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        fps_row.addWidget(self._fps_dot); fps_row.addWidget(self._fps_lbl); fps_row.addStretch(); bilgi.addLayout(fps_row)
        ak.addLayout(bilgi); ak.addStretch()
        self._kamera_durum_lbl = QLabel("Pasif Kamera")
        self._kamera_durum_lbl.setStyleSheet("background:#70899B;color:white;border-radius:9px;padding:4px 12px;font-size:11px;font-weight:500;border:none;")
        ak.addWidget(self._kamera_durum_lbl)
        sol.addWidget(alt_kart); icerik.addLayout(sol,3)

        # Sağ panel — istatistikler + son tespitler (_canli_paneli_yenile doldurur)
        self._canli_sag = QVBoxLayout(); self._canli_sag.setSpacing(12)
        icerik.addLayout(self._canli_sag,1); lay.addLayout(icerik)
        self._canli_paneli_yenile()

        # Saat timer
        timer = QTimer(self); timer.timeout.connect(self._saat_guncelle); timer.start(1000)
        return w

    def _canli_paneli_yenile(self):
        sag = self._canli_sag
        while sag.count():
            item = sag.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        ist = kart_frame(); ikl = QVBoxLayout(ist); ikl.setContentsMargins(18,16,18,16); ikl.setSpacing(10)
        ikl.addWidget(baslik_label("Anlık İstatistikler",14))
        bugun = datetime.now().date()
        def q0(sql,p=None): r=self._db(sql,p); return r[0][0] if r else 0
        t_t=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND LEFT(durum, 7) <> %s",(bugun,"CAMERA_"))
        b_s=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        y_s=q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        bas=round(b_s/t_t*100,1) if t_t>0 else 0
        for et,dg,rk in [("Aktif Kamera","1" if self._kamera_aktif_mi() else "0",ANA_MAVI),("Bugünkü Tespit",str(t_t),YAZI_KOYU),("Başarı Oranı",f"%{bas}",TURUNCU),("Bilinmeyen",str(y_s),KIRMIZI)]:
            r = QHBoxLayout(); e=QLabel(et); e.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};border:none;"); r.addWidget(e); r.addStretch()
            d=QLabel(dg); d.setStyleSheet(f"font-size:14px;font-weight:500;color:{rk};border:none;"); r.addWidget(d); ikl.addLayout(r); ikl.addWidget(sep_cizgi())
        sag.addWidget(ist)

        tp = kart_frame(); tkl = QVBoxLayout(tp); tkl.setContentsMargins(18,16,18,16); tkl.setSpacing(0)
        br_t = QHBoxLayout(); br_t.addWidget(baslik_label("Son Tespitler",14)); br_t.addStretch()
        tumu = QLabel("Tümü →"); tumu.setStyleSheet(f"font-size:12px;color:{ANA_MAVI};border:none;"); tumu.setCursor(Qt.PointingHandCursor); tumu.mousePressEvent=lambda e:self._git(4)
        br_t.addWidget(tumu); tkl.addLayout(br_t); tkl.addSpacing(10)
        son_t = self._db("SELECT isim,durum,saat FROM giris_kayitlari WHERE tarih=%s ORDER BY saat DESC LIMIT 5",(bugun,)) or []
        for row in son_t:
            isim, durum, saat = row; ok = durum=="Basarili"
            r = QHBoxLayout(); r.setSpacing(10)
            ic=QLabel("✓" if ok else "⚠"); ic.setFixedSize(26,26); ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{'#dcfce7' if ok else '#fef3c7'};border-radius:13px;color:{'#15803d' if ok else '#d97706'};font-size:12px;border:none;"); r.addWidget(ic)
            col=QVBoxLayout(); col.setSpacing(1)
            al=QLabel(isim); al.setStyleSheet(f"font-size:12px;font-weight:500;color:{YAZI_KOYU};border:none;")
            cl2=QLabel(camera_event_label(durum) or "Kamera 1"); cl2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            col.addWidget(al); col.addWidget(cl2); r.addLayout(col); r.addStretch()
            sl=QLabel(str(saat)[:8] if saat else "-"); sl.setAlignment(Qt.AlignRight); sl.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;"); r.addWidget(sl)
            tkl.addLayout(r); tkl.addWidget(sep_cizgi())
        sag.addWidget(tp); sag.addStretch()

    def _saat_guncelle(self):
        self._saat_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _kamera_toggle(self):
        """Başlat/Durdur toggle."""
        if not self._kamera_aktif_mi():
            if self._kamera_baslat():
                self._kamera_ui_ayarla(True)
        else:
            self._kamera_durdur()
            self._kamera_ui_ayarla(False)

    def _ekran_goruntusu(self):
        if not self._kamera_aktif_mi() or self.kamera_label.pixmap() is None:
            QMessageBox.information(self,"Ekran Görüntüsü","Önce kamerayı başlatın."); return
        hedef_dizin = ""
        for konum in (QStandardPaths.DesktopLocation, QStandardPaths.PicturesLocation, QStandardPaths.HomeLocation):
            d = QStandardPaths.writableLocation(konum)
            if d and os.path.isdir(d):
                hedef_dizin = d; break
        dosya_adi = f"kamera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        tam_yol = os.path.join(hedef_dizin, dosya_adi)
        if self.kamera_label.grab().save(tam_yol): QMessageBox.information(self,"Ekran Görüntüsü",f"✅ Kaydedildi:\n{tam_yol}")
        else: QMessageBox.warning(self,"Hata",f"Kaydedilemedi:\n{tam_yol}")

    # ══════════════════════════════════════
    #  SAYFA 4 — GEÇMİŞ KAYITLARI
    # ══════════════════════════════════════
    def _gecmis_sayfasi(self):
        w, lay = self._sayfa_wrap("Giriş/Çıkış Kayıtları","Geçmiş erişim kayıtlarını görüntüleyin ve analiz edin")
        self._gec_krow = QHBoxLayout(); self._gec_krow.setSpacing(14); lay.addLayout(self._gec_krow); lay.addSpacing(16)

        f_row = QHBoxLayout(); f_row.setSpacing(10)
        self._gecmis_arama = QLineEdit(); self._gecmis_arama.setPlaceholderText("🔍  İsim ile ara..."); self._gecmis_arama.setFixedHeight(40); self._gecmis_arama.setStyleSheet(input_stili())
        self._gecmis_arama.textChanged.connect(self._gecmis_filtrele); f_row.addWidget(self._gecmis_arama,2)
        self._gecmis_tip = QComboBox(); self._gecmis_tip.setFixedHeight(40); self._gecmis_tip.setStyleSheet(combobox_stili())
        self._gecmis_tip.addItems(["Tüm Kayıtlar","Giriş","Çıkış","Bilinmeyen","Şüpheli Kamera","Kamera Çözüldü"]); self._gecmis_tip.currentTextChanged.connect(self._gecmis_filtrele); f_row.addWidget(self._gecmis_tip,1)
        self._gecmis_tarih = QComboBox(); self._gecmis_tarih.setFixedHeight(40); self._gecmis_tarih.setStyleSheet(combobox_stili())
        self._gecmis_tarih.addItems(["Bugün","Dün","Bu Hafta","Bu Ay"]); self._gecmis_tarih.currentTextChanged.connect(self._gecmis_filtrele); f_row.addWidget(self._gecmis_tarih,1)
        eb = mavi_btn("📊  Excel'e Aktar",40); eb.setFixedWidth(150); eb.clicked.connect(self._excele_aktar); f_row.addWidget(eb)
        lay.addLayout(f_row); lay.addSpacing(14)

        self.gecmis_tablosu = QTableWidget(); self.gecmis_tablosu.setColumnCount(8)
        self.gecmis_tablosu.setHorizontalHeaderLabels(["ID","KİŞİ","TİP","TARİH","SAAT","KAMERA","GÜVEN","İŞLEMLER"])
        hh = self.gecmis_tablosu.horizontalHeader()
        for i, mod in enumerate([QHeaderView.ResizeToContents,QHeaderView.Stretch,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents,QHeaderView.ResizeToContents]):
            hh.setSectionResizeMode(i,mod)
        self.gecmis_tablosu.setStyleSheet(f"""
            QTableWidget{{background:rgba(250,253,255,240);border-radius:14px;border:1px solid rgba(255,255,255,220);gridline-color:#E8EFF4;font-family:'Segoe UI';}}
            QHeaderView::section{{background:rgba(231,241,248,245);padding:10px 8px;font-size:11px;font-weight:500;color:{YAZI_GRI};border:none;border-bottom:1px solid {SINIR};}}
            QTableWidget::item{{padding:6px 8px;font-size:13px;color:{YAZI_KOYU};}}
            QTableWidget::item:selected{{background:#D8E7F1;}}""")
        self.gecmis_tablosu.setEditTriggers(QTableWidget.NoEditTriggers)
        self.gecmis_tablosu.setSelectionBehavior(QTableWidget.SelectRows)
        self.gecmis_tablosu.verticalHeader().setVisible(False); self.gecmis_tablosu.setShowGrid(False)
        self._gecmis_verileri = []; self._gecmis_yukle()
        lay.addWidget(self.gecmis_tablosu)
        return w

    def _gecmis_yukle(self):
        while self._gec_krow.count():
            item = self._gec_krow.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        bugun = datetime.now().date()
        def q0(sql,p=None): r=self._db(sql,p); return r[0][0] if r else 0
        t=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND LEFT(durum, 7) <> %s",(bugun,"CAMERA_"))
        g=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        y=q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        for sayi, etiket, ikon, bg, fg in [(t,"Toplam Kayıt","📋","#dbeafe","#1d4ed8"),(g,"Giriş","✅","#dcfce7","#15803d"),(t-g,"Diğer","🔄","#fef3c7","#d97706"),(y,"Bilinmeyen","⚠️","#fee2e2","#dc2626")]:
            self._gec_krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))

        giris_rows = self._db("SELECT isim,durum,tarih,saat FROM giris_kayitlari ORDER BY tarih DESC,saat DESC LIMIT 100") or []
        yt_rows = self._db("SELECT foto_yolu,tarih,saat FROM yetkisiz_kayitlar ORDER BY tarih DESC,saat DESC LIMIT 50") or []
        self._gecmis_verileri = []
        idx = 1
        for isim, durum, tarih, saat in giris_rows:
            event_label = camera_event_label(durum)
            if event_label:
                tip = "Şüpheli Kamera" if durum.endswith("_ACTIVE") else "Kamera Çözüldü"
                ad = event_label
                kamera = isim
                ok = False
            else:
                tip = "Giriş" if durum=="Basarili" else "Çıkış"
                ad = isim
                kamera = "Kamera 1"
                ok = durum=="Basarili"
            self._gecmis_verileri.append((f"#{idx:04d}",ad,tip,tarih.strftime("%d.%m.%Y") if hasattr(tarih,'strftime') else str(tarih),str(saat)[:8] if saat else "-",kamera,"—",ok))
            idx+=1
        for foto, tarih, saat in yt_rows:
            self._gecmis_verileri.append((f"#{idx:04d}","Bilinmeyen Kişi","Bilinmeyen",tarih.strftime("%d.%m.%Y") if hasattr(tarih,'strftime') else str(tarih),str(saat)[:8] if saat else "-","Kamera 1","—",False))
            idx+=1
        self._gecmis_tablo_doldur()
        self._gecmis_filtrele()

    def _gecmis_tablo_doldur(self):
        t = self.gecmis_tablosu; t.setRowCount(len(self._gecmis_verileri))
        for i, (lid, ad, tip, tarih, saat, kamera, guven, ok) in enumerate(self._gecmis_verileri):
            t.setRowHeight(i,52); t.setItem(i,0,QTableWidgetItem(lid))
            kw = QWidget(); kw.setStyleSheet("background:transparent;")
            kl = QHBoxLayout(kw); kl.setContentsMargins(6,4,6,4); kl.setSpacing(8)
            kl.addWidget(avatar_widget(get_initials(ad) if ad!="Bilinmeyen Kişi" else "?", AVATAR_RENKLER[i%len(AVATAR_RENKLER)] if ok else "#9ca3af",30))
            kl.addWidget(QLabel(ad)); kl.itemAt(1).widget().setStyleSheet(f"font-size:13px;color:{YAZI_KOYU};border:none;"); kl.addStretch(); t.setCellWidget(i,1,kw)
            tw = QWidget(); tw.setStyleSheet("background:transparent;")
            tl = QHBoxLayout(tw); tl.setContentsMargins(6,0,6,0); tl.setAlignment(Qt.AlignCenter)
            tlbl = QLabel(tip); tlbl.setStyleSheet({"Giriş":"background:#E4F2ED;color:#277763;","Çıkış":"background:#F6EFE3;color:#A97638;","Bilinmeyen":"background:#F8E9EA;color:#A94F5A;","Şüpheli Kamera":"background:#FEF3C7;color:#A16207;","Kamera Çözüldü":"background:#E4F2ED;color:#277763;"}.get(tip,"")+"border-radius:8px;padding:2px 8px;font-size:11px;font-weight:500;")
            tl.addWidget(tlbl); t.setCellWidget(i,2,tw)
            for col, val in [(3,tarih),(4,saat),(5,kamera),(6,guven)]:
                item=QTableWidgetItem(val); item.setTextAlignment(Qt.AlignCenter); t.setItem(i,col,item)
            iw=QWidget(); iw.setStyleSheet("background:transparent;")
            il=QHBoxLayout(iw); il.setContentsMargins(4,4,4,4); il.setSpacing(4); il.setAlignment(Qt.AlignCenter)
            for emoji,tip2,stil in [("👁","Görüntüle","background:#eff6ff;"),("🎬","Video","background:#f0fdf4;"),("📄","Rapor","background:#fefce8;")]:
                b=QPushButton(emoji); b.setFixedSize(28,28); b.setToolTip(tip2); b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"QPushButton{{{stil}border:none;border-radius:6px;font-size:13px;}}"); il.addWidget(b)
            t.setCellWidget(i,7,iw)

    def _gecmis_filtrele(self):
        arama = self._gecmis_arama.text().lower().strip()
        s_tip = self._gecmis_tip.currentText()
        s_tarih = self._gecmis_tarih.currentText()
        bugun = datetime.now().strftime("%d.%m.%Y")
        dun = (datetime.now()-timedelta(days=1)).strftime("%d.%m.%Y")
        bu_hafta = [(datetime.now()-timedelta(days=i)).strftime("%d.%m.%Y") for i in range(7)]
        bu_ay = datetime.now().strftime("%m.%Y")
        for i, (lid, ad, tip, tarih, saat, kamera, guven, ok) in enumerate(self._gecmis_verileri):
            a_ok = arama=="" or arama in ad.lower() or arama in lid.lower()
            t_ok = s_tip=="Tüm Kayıtlar" or s_tip==tip
            d_ok = True
            if s_tarih=="Bugün": d_ok = tarih==bugun
            elif s_tarih=="Dün": d_ok = tarih==dun
            elif s_tarih=="Bu Hafta": d_ok = tarih in bu_hafta
            elif s_tarih=="Bu Ay": d_ok = tarih.endswith(bu_ay)
            self.gecmis_tablosu.setRowHidden(i, not (a_ok and t_ok and d_ok))

    def _excele_aktar(self):
        try: import openpyxl
        except ImportError:
            QMessageBox.warning(self,"Eksik Kütüphane","Excel aktarımı için:\npip install openpyxl"); return
        dosya, _ = QFileDialog.getSaveFileName(self,"Excel Kaydet","giris_kayitlari.xlsx","Excel (*.xlsx)")
        if not dosya: return
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Kayıtlar"
        ws.append(["ID","Kişi","Tip","Tarih","Saat","Kamera","Güven"])
        for lid,ad,tip,tarih,saat,kamera,guven,ok in self._gecmis_verileri: ws.append([lid,ad,tip,tarih,saat,kamera,guven])
        try:
            wb.save(dosya)
        except OSError as e:
            QMessageBox.critical(self,"Hata",f"Dosya kaydedilemedi (başka bir programda açık olabilir):\n{e}"); return
        QMessageBox.information(self,"Başarılı",f"✅ Kaydedildi:\n{dosya}")
