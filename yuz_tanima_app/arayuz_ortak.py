"""Ortak arayüz parçaları: renkler, yardımcı widget üreticiler ve diyaloglar."""
import os
from datetime import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from .yuz_tanima import gorsel_oku

# ══════════════════════════════════════════
#  RENKLER
# ══════════════════════════════════════════
KOYU_BG   = "#24415B"
ANA_MAVI  = "#527D9C"
SAYFA_BG  = "transparent"
YAZI_KOYU = "#20364B"
YAZI_GRI  = "#60758A"
SINIR     = "#D5E0E9"
YESIL     = "#278A78"
KIRMIZI   = "#CC6670"
TURUNCU   = "#B67A3F"
AVATAR_RENKLER = ["#527D9C","#278A78","#B67A3F","#CC6670","#657FA5","#438DA1","#A66E8B"]

# ══════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════
def pixmap_yukle(yol):
    """Görseli QPixmap olarak yükler; yüklenemezse boş (null) QPixmap döner.

    Windows'ta yolda ASCII olmayan karakter (ü, ı...) varsa Qt'nin JPEG eklentisi
    bulunamayabilir ve QPixmap(yol) JPG'yi açamaz. Bu durumda dosya OpenCV ile
    okunup dönüştürülür.
    """
    pix = QPixmap(str(yol))
    if not pix.isNull():
        return pix
    goruntu = gorsel_oku(yol)
    if goruntu is None:
        return QPixmap()
    import cv2
    rgb = cv2.cvtColor(goruntu, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy())


def kart_frame(parent=None, radius=12):
    f = QFrame(parent)
    f.setStyleSheet(f"background: rgba(250,253,255,210); border-radius: {radius}px; border: 1px solid rgba(255,255,255,220);")
    return f

def baslik_label(metin, boyut=22):
    l = QLabel(metin)
    l.setStyleSheet(f"font-size:{boyut}px;font-weight:500;color:{YAZI_KOYU};"
                    f"font-family:'Segoe UI';background:transparent;border:none;")
    return l

def alt_baslik_label(metin):
    l = QLabel(metin)
    l.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};font-family:'Segoe UI';"
                    f"background:transparent;border:none;")
    return l

def input_stili():
    return (f"QLineEdit{{border:1px solid {SINIR};border-radius:11px;padding:0 12px;"
            f"font-size:13px;color:{YAZI_KOYU};background:rgba(255,255,255,210);}}"
            f"QLineEdit:focus{{border-color:{ANA_MAVI};}}")

def combobox_stili():
    return (f"QComboBox{{border:1px solid {SINIR};border-radius:11px;padding:0 12px;"
            f"font-size:13px;color:{YAZI_KOYU};background:rgba(255,255,255,210);}}"
            f"QComboBox:focus{{border-color:{ANA_MAVI};}}"
            f"QComboBox::drop-down{{border:none;width:24px;}}")

def mavi_btn(metin, yukseklik=42):
    b = QPushButton(metin); b.setFixedHeight(yukseklik); b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton{{background:{ANA_MAVI};color:white;border:none;"
                    f"border-radius:10px;font-size:13px;font-weight:500;}}"
                    f"QPushButton:hover{{background:#416B8A;}}"
                    f"QPushButton:pressed{{background:#345A77;}}")
    return b

def avatar_widget(initials, renk="#4A3FC7", boyut=36):
    lbl = QLabel(initials); lbl.setFixedSize(boyut, boyut); lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"background:{renk};color:white;border-radius:{boyut//2}px;"
                      f"font-size:{boyut//3}px;font-weight:bold;border:none;")
    return lbl

def get_initials(ad):
    if not ad or ad.strip() == "": return "?"
    p = ad.strip().split()
    return (p[0][0] + p[1][0]).upper() if len(p) >= 2 else ad[:2].upper()

def sure_metni(dt):
    if not dt: return "-"
    try:
        fark = datetime.now() - dt
        s = int(fark.total_seconds())
        if s < 60: return "az önce"
        elif s < 3600: return f"{s//60} dakika önce"
        elif s < 86400: return f"{s//3600} saat önce"
        else: return f"{fark.days} gün önce"
    except:
        return str(dt)

def sep_cizgi(renk=None):
    s = QFrame(); s.setFrameShape(QFrame.HLine)
    s.setStyleSheet(f"color:{renk or SINIR};margin:5px 0;")
    return s

# ══════════════════════════════════════════
#  YETKİSİZ UYARI DİYALOGU
# ══════════════════════════════════════════
class YetkisizUyariDiyalog(QDialog):
    def __init__(self, foto_yolu, saat_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ YETKİSİZ ERİŞİM!")
        self.setFixedSize(420, 500)
        self.setStyleSheet("background:#F9ECEE;")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        lay = QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(16)

        uyari = QLabel("⚠️  YETKİSİZ ERİŞİM TESPİT EDİLDİ!")
        uyari.setAlignment(Qt.AlignCenter)
        uyari.setStyleSheet("font-size:18px;font-weight:500;color:#A94F5A;background:transparent;border:none;")
        lay.addWidget(uyari)

        alt = QLabel(f"Saat: {saat_str}\nTanımlanamayan kişi tespit edildi!")
        alt.setAlignment(Qt.AlignCenter)
        alt.setStyleSheet("font-size:13px;color:#6E4B51;border:none;background:transparent;")
        lay.addWidget(alt)

        cerceve = QFrame(); cerceve.setFixedSize(340,280)
        cerceve.setStyleSheet("background:#111827;border-radius:12px;border:3px solid #dc2626;")
        fl = QVBoxLayout(cerceve)
        foto_lbl = QLabel(); foto_lbl.setAlignment(Qt.AlignCenter)
        foto_lbl.setStyleSheet("border:none;background:transparent;")
        pix = pixmap_yukle(foto_yolu) if foto_yolu and os.path.exists(foto_yolu) else QPixmap()
        if not pix.isNull():
            foto_lbl.setPixmap(pix.scaled(320,260,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            foto_lbl.setText("📷\n\nFotoğraf\nMevcut Değil")
            foto_lbl.setStyleSheet("color:#6b7280;font-size:14px;border:none;background:transparent;")
        fl.addWidget(foto_lbl)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(cerceve); h.addStretch()
        lay.addLayout(h)

        kapat = QPushButton("✓  Anladım, Kapat"); kapat.setFixedHeight(44); kapat.setCursor(Qt.PointingHandCursor)
        kapat.setStyleSheet("QPushButton{background:#B95B65;color:white;border:none;border-radius:11px;font-size:14px;font-weight:500;}"
                            "QPushButton:hover{background:#A64C56;}")
        kapat.clicked.connect(self.accept); lay.addWidget(kapat)

# ══════════════════════════════════════════
#  FOTOĞRAF DİYALOGU
# ══════════════════════════════════════════
class FotoDiyalog(QDialog):
    def __init__(self, ad, foto_yol, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{ad} — Fotoğraf"); self.setFixedSize(420,480)
        self.setStyleSheet("background:#D9E8F3;")
        lay = QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(16)
        b = baslik_label(ad, 16); b.setAlignment(Qt.AlignCenter); lay.addWidget(b)
        cerceve = QFrame(); cerceve.setFixedSize(340,340)
        cerceve.setStyleSheet(f"background:#111827;border-radius:12px;border:2px solid {ANA_MAVI};")
        fl = QVBoxLayout(cerceve)
        foto_lbl = QLabel(); foto_lbl.setAlignment(Qt.AlignCenter)
        foto_lbl.setStyleSheet("border:none;background:transparent;")
        pix = pixmap_yukle(foto_yol) if foto_yol and os.path.exists(foto_yol) else QPixmap()
        if not pix.isNull():
            foto_lbl.setPixmap(pix.scaled(320,320,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            foto_lbl.setText("📷\n\nFotoğraf\nBulunamadı")
            foto_lbl.setStyleSheet("color:#6b7280;font-size:14px;border:none;background:transparent;")
        fl.addWidget(foto_lbl)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(cerceve); h.addStretch(); lay.addLayout(h)
        kapat = mavi_btn("Kapat", 40); kapat.clicked.connect(self.accept); lay.addWidget(kapat)
