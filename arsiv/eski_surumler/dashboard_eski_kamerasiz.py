# ARŞİV: yeniden yapılandırma öncesi özgün dosya (çalıştırılmaz). Gizli değerler kaldırıldı.
import sys
import os
import psycopg2
from datetime import datetime, timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

# ══════════════════════════════════════════
#  VERİTABANI
# ══════════════════════════════════════════
DB_CONFIG = {
    "host": "localhost",
    "database": "yuz_tanima",
    "user": "postgres",
    "password": "<GIZLI-KALDIRILDI>",
    "port": "5432"
}

def db_baglan():
    return psycopg2.connect(**DB_CONFIG)

def db_sorgula(sorgu, parametreler=None, geri_don=True):
    try:
        conn = db_baglan()
        cur = conn.cursor()
        cur.execute(sorgu, parametreler or ())
        if geri_don:
            sonuc = cur.fetchall()
            cur.close(); conn.close()
            return sonuc
        else:
            conn.commit(); cur.close(); conn.close()
            return True
    except Exception as e:
        print(f"DB Hata: {e}")
        return [] if geri_don else False

# ══════════════════════════════════════════
#  RENKLER
# ══════════════════════════════════════════
KOYU_BG   = "#1a1a2e"
ANA_MAVI  = "#4A3FC7"
SAYFA_BG  = "#f0f2f5"
YAZI_KOYU = "#1a1a2e"
YAZI_GRI  = "#6b7280"
SINIR     = "#e5e7eb"
YESIL     = "#22c55e"
KIRMIZI   = "#ef4444"
TURUNCU   = "#f59e0b"
AVATAR_RENKLER = ["#4A3FC7","#059669","#d97706","#dc2626","#7c3aed","#0891b2","#be185d"]

# ══════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════
def kart_frame(parent=None, radius=12):
    f = QFrame(parent)
    f.setStyleSheet(f"background: white; border-radius: {radius}px; border: 1px solid {SINIR};")
    return f

def baslik_label(metin, boyut=22):
    l = QLabel(metin)
    l.setStyleSheet(f"font-size:{boyut}px;font-weight:bold;color:{YAZI_KOYU};"
                    f"font-family:'Segoe UI';background:transparent;border:none;")
    return l

def alt_baslik_label(metin):
    l = QLabel(metin)
    l.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};font-family:'Segoe UI';"
                    f"background:transparent;border:none;")
    return l

def input_stili():
    return (f"QLineEdit{{border:1.5px solid {SINIR};border-radius:8px;padding:0 12px;"
            f"font-size:13px;color:{YAZI_KOYU};background:white;}}"
            f"QLineEdit:focus{{border-color:{ANA_MAVI};}}")

def combobox_stili():
    return (f"QComboBox{{border:1.5px solid {SINIR};border-radius:8px;padding:0 12px;"
            f"font-size:13px;color:{YAZI_KOYU};background:white;}}"
            f"QComboBox:focus{{border-color:{ANA_MAVI};}}"
            f"QComboBox::drop-down{{border:none;width:24px;}}")

def mavi_btn(metin, yukseklik=42):
    b = QPushButton(metin); b.setFixedHeight(yukseklik); b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton{{background:{ANA_MAVI};color:white;border:none;"
                    f"border-radius:8px;font-size:13px;font-weight:bold;}}"
                    f"QPushButton:hover{{background:#3a30a8;}}"
                    f"QPushButton:pressed{{background:#2d2580;}}")
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
        self.setStyleSheet("background:#fff1f2;")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        lay = QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(16)

        uyari = QLabel("⚠️  YETKİSİZ ERİŞİM TESPİT EDİLDİ!")
        uyari.setAlignment(Qt.AlignCenter)
        uyari.setStyleSheet("font-size:18px;font-weight:bold;color:#dc2626;background:transparent;border:none;")
        lay.addWidget(uyari)

        alt = QLabel(f"Saat: {saat_str}\nTanımlanamayan kişi tespit edildi!")
        alt.setAlignment(Qt.AlignCenter)
        alt.setStyleSheet("font-size:13px;color:#7f1d1d;border:none;background:transparent;")
        lay.addWidget(alt)

        cerceve = QFrame(); cerceve.setFixedSize(340,280)
        cerceve.setStyleSheet("background:#111827;border-radius:12px;border:3px solid #dc2626;")
        fl = QVBoxLayout(cerceve)
        foto_lbl = QLabel(); foto_lbl.setAlignment(Qt.AlignCenter)
        foto_lbl.setStyleSheet("border:none;background:transparent;")
        if foto_yolu and os.path.exists(foto_yolu):
            pix = QPixmap(foto_yolu).scaled(320,260,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            foto_lbl.setPixmap(pix)
        else:
            foto_lbl.setText("📷\n\nFotoğraf\nMevcut Değil")
            foto_lbl.setStyleSheet("color:#6b7280;font-size:14px;border:none;background:transparent;")
        fl.addWidget(foto_lbl)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(cerceve); h.addStretch()
        lay.addLayout(h)

        kapat = QPushButton("✓  Anladım, Kapat"); kapat.setFixedHeight(44); kapat.setCursor(Qt.PointingHandCursor)
        kapat.setStyleSheet("QPushButton{background:#dc2626;color:white;border:none;border-radius:10px;font-size:14px;font-weight:bold;}"
                            "QPushButton:hover{background:#b91c1c;}")
        kapat.clicked.connect(self.accept); lay.addWidget(kapat)

# ══════════════════════════════════════════
#  FOTOĞRAF DİYALOGU
# ══════════════════════════════════════════
class FotoDiyalog(QDialog):
    def __init__(self, ad, foto_yol, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{ad} — Fotoğraf"); self.setFixedSize(420,480)
        self.setStyleSheet(f"background:{SAYFA_BG};")
        lay = QVBoxLayout(self); lay.setContentsMargins(24,24,24,24); lay.setSpacing(16)
        b = baslik_label(ad, 16); b.setAlignment(Qt.AlignCenter); lay.addWidget(b)
        cerceve = QFrame(); cerceve.setFixedSize(340,340)
        cerceve.setStyleSheet(f"background:#111827;border-radius:12px;border:2px solid {ANA_MAVI};")
        fl = QVBoxLayout(cerceve)
        foto_lbl = QLabel(); foto_lbl.setAlignment(Qt.AlignCenter)
        foto_lbl.setStyleSheet("border:none;background:transparent;")
        if foto_yol and os.path.exists(foto_yol):
            pix = QPixmap(foto_yol).scaled(320,320,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            foto_lbl.setPixmap(pix)
        else:
            foto_lbl.setText("📷\n\nFotoğraf\nBulunamadı")
            foto_lbl.setStyleSheet("color:#6b7280;font-size:14px;border:none;background:transparent;")
        fl.addWidget(foto_lbl)
        h = QHBoxLayout(); h.addStretch(); h.addWidget(cerceve); h.addStretch(); lay.addLayout(h)
        kapat = mavi_btn("Kapat", 40); kapat.clicked.connect(self.accept); lay.addWidget(kapat)

# ══════════════════════════════════════════
#  ANA DASHBOARD
# ══════════════════════════════════════════
class Dashboard(QMainWindow):
    yetkisiz_sinyal = pyqtSignal(str, str)  # foto_yolu, saat — OpenCV'den çağrılır

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yüz Tanıma Güvenlik Sistemi")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(f"background:{SAYFA_BG};")
        self.yetkisiz_sinyal.connect(self._yetkisiz_popup)

        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana = QHBoxLayout(merkez); ana.setContentsMargins(0,0,0,0); ana.setSpacing(0)
        ana.addWidget(self._sol_menu())

        self.stack = QStackedWidget(); self.stack.setStyleSheet(f"background:{SAYFA_BG};")
        ana.addWidget(self.stack)

        self.stack.addWidget(self._dashboard_sayfasi())    # 0
        self.stack.addWidget(self._yuz_kayit_sayfasi())    # 1
        self.stack.addWidget(self._kullanici_sayfasi())    # 2
        self.stack.addWidget(self._canli_izleme_sayfasi()) # 3
        self.stack.addWidget(self._gecmis_sayfasi())       # 4
        self.stack.setCurrentIndex(0)

        self._dashboard_yenile()
        yt = QTimer(self); yt.timeout.connect(self._dashboard_yenile); yt.start(30000)

    # ──────────────────────────────────────
    #  SOL MENÜ
    # ──────────────────────────────────────
    def _sol_menu(self):
        w = QWidget(); w.setFixedWidth(225); w.setStyleSheet(f"background:{KOYU_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14,24,14,20); lay.setSpacing(2)

        logo = QLabel("Yüz Tanıma\nSistemi")
        logo.setStyleSheet("color:white;font-size:17px;font-weight:bold;font-family:'Segoe UI';border:none;padding-bottom:4px;")
        lay.addWidget(logo)
        alt = QLabel("Güvenlik Yönetimi")
        alt.setStyleSheet("color:rgba(255,255,255,0.4);font-size:11px;font-family:'Segoe UI';border:none;padding-bottom:4px;")
        lay.addWidget(alt)

        # Uyarı rozeti
        br = QHBoxLayout()
        bl = QLabel("🔔  Uyarılar"); bl.setStyleSheet("color:rgba(255,255,255,0.5);font-size:11px;border:none;")
        br.addWidget(bl); br.addStretch()
        self.rozet = QLabel("0"); self.rozet.setFixedSize(20,20); self.rozet.setAlignment(Qt.AlignCenter)
        self.rozet.setStyleSheet("background:#dc2626;color:white;border-radius:10px;font-size:11px;font-weight:bold;border:none;")
        self.rozet.hide(); br.addWidget(self.rozet); lay.addLayout(br)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:rgba(255,255,255,0.12);margin:8px 0;"); lay.addWidget(sep)

        self._menu_btns = []
        for ikon, isim, idx in [("🏠","Ana Sayfa",0),("👤","Yüz Kaydı",1),("📋","Kullanıcı Listesi",2),("📷","Canlı İzleme",3),("🕐","Geçmiş Kayıtları",4)]:
            btn = QPushButton(f"  {ikon}  {isim}"); btn.setFixedHeight(44); btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._menu_stili(False))
            btn.clicked.connect(lambda _, i=idx: self._git(i))
            lay.addWidget(btn); self._menu_btns.append(btn)

        lay.addStretch()
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:rgba(255,255,255,0.12);margin-bottom:8px;"); lay.addWidget(sep2)

        cikis = QPushButton("  🚪  Çıkış Yap"); cikis.setFixedHeight(44); cikis.setCursor(Qt.PointingHandCursor)
        cikis.setStyleSheet("QPushButton{background:transparent;color:#ff4d4d;border:1px solid rgba(255,77,77,0.35);border-radius:8px;font-size:13px;font-family:'Segoe UI';text-align:left;padding-left:8px;}"
                            "QPushButton:hover{background:rgba(255,77,77,0.12);}")
        cikis.clicked.connect(self._cikis); lay.addWidget(cikis)
        self._menu_btns[0].setStyleSheet(self._menu_stili(True))
        return w

    def _menu_stili(self, aktif):
        if aktif:
            return f"QPushButton{{background:{ANA_MAVI};color:white;border:none;border-radius:8px;font-size:13px;font-family:'Segoe UI';text-align:left;padding-left:8px;}}"
        return ("QPushButton{background:transparent;color:rgba(255,255,255,0.6);border:none;border-radius:8px;font-size:13px;font-family:'Segoe UI';text-align:left;padding-left:8px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.08);color:white;}")

    def _git(self, idx):
        for i, b in enumerate(self._menu_btns): b.setStyleSheet(self._menu_stili(i == idx))
        self.stack.setCurrentIndex(idx)

    def _cikis(self):
        r = QMessageBox.question(self,"Çıkış","Çıkmak istediğinize emin misiniz?",QMessageBox.Yes|QMessageBox.No)
        if r == QMessageBox.Yes: QApplication.quit()

    def _yetkisiz_popup(self, foto_yolu, saat_str):
        try: mevcut = int(self.rozet.text())
        except: mevcut = 0
        self.rozet.setText(str(mevcut+1)); self.rozet.show()
        YetkisizUyariDiyalog(foto_yolu, saat_str, self).exec_()
        self._dashboard_yenile()

    # ──────────────────────────────────────
    #  YARDIMCILAR
    # ──────────────────────────────────────
    def _sayfa_wrap(self, baslik_txt, alt_txt):
        w = QWidget(); w.setStyleSheet(f"background:{SAYFA_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(32,28,32,28); lay.setSpacing(0)
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
        n = QLabel(str(sayi)); n.setStyleSheet(f"font-size:28px;font-weight:bold;color:{YAZI_KOYU};font-family:'Segoe UI';border:none;")
        fl.addWidget(n)
        e = QLabel(etiket); e.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        fl.addWidget(e)
        return f

    # ══════════════════════════════════════
    #  SAYFA 0 — DASHBOARD
    # ══════════════════════════════════════
    def _dashboard_sayfasi(self):
        self._dash_w = QWidget(); self._dash_w.setStyleSheet(f"background:{SAYFA_BG};")
        ml = QVBoxLayout(self._dash_w); ml.setContentsMargins(32,28,32,28); ml.setSpacing(0)
        ml.addWidget(baslik_label("Ana Dashboard"))
        sub = alt_baslik_label("Yüz tanıma sistemi genel görünüm ve istatistikler"); sub.setContentsMargins(0,4,0,20); ml.addWidget(sub)
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

        # DB istatistikleri
        def q0(sql, p=None): r = db_sorgula(sql, p); return r[0][0] if r else 0
        toplam_k = q0("SELECT COUNT(*) FROM yetkili_kisiler")
        bugun_g  = q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        t_den    = q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s",(bugun,))
        y_say    = q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        basari   = round(bugun_g/t_den*100,1) if t_den>0 else 0

        # Stat kartları
        krow = QHBoxLayout(); krow.setSpacing(16)
        for sayi, etiket, ikon, bg, fg in [
            (toplam_k,"Toplam Kullanıcı","👥","#dbeafe","#1d4ed8"),
            (bugun_g,"Bugünkü Giriş","✅","#dcfce7","#15803d"),
            (1,"Aktif Kamera","📷","#ede9fe","#7c3aed"),
            (f"%{basari}","Başarı Oranı","🎯","#fef3c7","#d97706"),
        ]:
            krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))
        self._dash_icerik_lay.addLayout(krow)

        # Yetkisiz uyarı kartı
        uyarilar = db_sorgula("SELECT foto_yolu,tarih,saat FROM yetkisiz_kayitlar WHERE tarih=%s ORDER BY saat DESC LIMIT 5",(bugun,))
        if uyarilar:
            uk = QFrame(); uk.setStyleSheet("background:#fff1f2;border-radius:12px;border:1.5px solid #fca5a5;")
            ukl = QVBoxLayout(uk); ukl.setContentsMargins(18,14,18,14); ukl.setSpacing(8)
            ur = QHBoxLayout()
            bu = QLabel("⚠️  Yetkisiz Erişim Uyarıları"); bu.setStyleSheet("font-size:14px;font-weight:bold;color:#dc2626;border:none;")
            ur.addWidget(bu); ur.addStretch()
            sb = QLabel(f"{len(uyarilar)} Uyarı"); sb.setStyleSheet("background:#dc2626;color:white;border-radius:8px;padding:3px 10px;font-size:11px;font-weight:bold;border:none;")
            ur.addWidget(sb); ukl.addLayout(ur)
            for foto, tarih, saat in uyarilar:
                sr = QHBoxLayout(); sr.setSpacing(12)
                zl = QLabel(str(saat)[:8]); zl.setStyleSheet("font-size:12px;color:#dc2626;font-weight:bold;border:none;min-width:65px;")
                sr.addWidget(zl)
                ml2 = QLabel("🔴  Tanımlanamayan kişi tespit edildi — Kamera 1"); ml2.setStyleSheet("font-size:13px;color:#7f1d1d;border:none;")
                sr.addWidget(ml2); sr.addStretch()
                fb = QPushButton("Fotoğrafı Gör"); fb.setFixedHeight(28); fb.setCursor(Qt.PointingHandCursor)
                fb.setStyleSheet("QPushButton{background:#dc2626;color:white;border:none;border-radius:6px;font-size:11px;padding:0 10px;}QPushButton:hover{background:#b91c1c;}")
                fb.clicked.connect(lambda _,f=foto or "",s=str(saat)[:8]: self._yetkisiz_popup(f,s))
                sr.addWidget(fb); ukl.addLayout(sr); ukl.addWidget(sep_cizgi("#fca5a5"))
            self.rozet.setText(str(len(uyarilar))); self.rozet.show()
            self._dash_icerik_lay.addWidget(uk)

        # Alt iki panel
        arow = QHBoxLayout(); arow.setSpacing(16)

        # Son Aktiviteler
        sol = kart_frame()
        sl = QVBoxLayout(sol); sl.setContentsMargins(18,16,18,16); sl.setSpacing(0)
        br2 = QHBoxLayout(); br2.addWidget(baslik_label("Son Aktiviteler",14)); br2.addStretch()
        tg = QLabel("Tümünü Gör →"); tg.setStyleSheet(f"font-size:12px;color:{ANA_MAVI};border:none;"); tg.setCursor(Qt.PointingHandCursor)
        tg.mousePressEvent = lambda e: self._git(4); br2.addWidget(tg); sl.addLayout(br2); sl.addSpacing(12)

        aktiviteler = db_sorgula("SELECT isim,durum,tarih,saat FROM giris_kayitlari ORDER BY tarih DESC,saat DESC LIMIT 5")
        for row in (aktiviteler or []):
            isim, durum, tarih, saat = row
            ok = durum == "Basarili"
            try: dt = datetime.combine(tarih, saat); zaman_str = sure_metni(dt)
            except: zaman_str = str(saat)
            r = QHBoxLayout(); r.setSpacing(12)
            ic = QLabel("✅" if ok else "❌"); ic.setFixedSize(32,32); ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{'#dcfce7' if ok else '#fee2e2'};border-radius:16px;border:none;font-size:14px;")
            r.addWidget(ic)
            col = QVBoxLayout(); col.setSpacing(1)
            al = QLabel(isim); al.setStyleSheet(f"font-size:13px;font-weight:bold;color:{YAZI_KOYU};border:none;")
            il = QLabel("Giriş Yaptı" if ok else "Reddedildi"); il.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            col.addWidget(al); col.addWidget(il); r.addLayout(col); r.addStretch()
            zl = QLabel(zaman_str); zl.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;"); r.addWidget(zl)
            sl.addLayout(r); sl.addWidget(sep_cizgi())
        arow.addWidget(sol)

        # Kamera durumu
        sag = kart_frame()
        saglay = QVBoxLayout(sag); saglay.setContentsMargins(18,16,18,16); saglay.setSpacing(0)
        br3 = QHBoxLayout(); br3.addWidget(baslik_label("Kamera Durumu",14)); br3.addStretch()
        ab = QLabel("1/1 Aktif"); ab.setStyleSheet("background:#dcfce7;color:#15803d;border-radius:8px;padding:3px 8px;font-size:11px;font-weight:bold;border:none;")
        br3.addWidget(ab); saglay.addLayout(br3); saglay.addSpacing(16)
        kk = QFrame(); kk.setStyleSheet(f"background:#f9fafb;border-radius:10px;border:1px solid {SINIR};")
        kkl = QVBoxLayout(kk); kkl.setContentsMargins(14,12,14,12); kkl.setSpacing(8)
        ur2 = QHBoxLayout()
        dl = QLabel("●"); dl.setStyleSheet(f"color:{YESIL};font-size:16px;border:none;"); ur2.addWidget(dl)
        cn = QLabel("Kamera 1"); cn.setStyleSheet(f"font-size:14px;font-weight:bold;color:{YAZI_KOYU};border:none;"); ur2.addWidget(cn); ur2.addStretch()
        fb2 = QLabel("30 FPS"); fb2.setStyleSheet(f"background:#dcfce7;color:#15803d;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:bold;border:none;"); ur2.addWidget(fb2)
        kkl.addLayout(ur2)
        cy = QLabel("📍  Ana Giriş"); cy.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;"); kkl.addWidget(cy)
        saglay.addWidget(kk); saglay.addSpacing(12)
        saglay.addWidget(baslik_label("Sistem Durumu",13)); saglay.addSpacing(8)
        for et, dg, yp, rk in [("CPU Kullanımı","%45",45,ANA_MAVI),("Başarı Oranı",f"%{basari}",int(min(basari,100)),YESIL)]:
            rw = QHBoxLayout()
            el = QLabel(et); el.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;"); rw.addWidget(el); rw.addStretch()
            dl2 = QLabel(dg); dl2.setStyleSheet(f"font-size:12px;font-weight:bold;color:{rk};border:none;"); rw.addWidget(dl2); saglay.addLayout(rw)
            bar = QProgressBar(); bar.setValue(yp); bar.setFixedHeight(6); bar.setTextVisible(False)
            bar.setStyleSheet(f"QProgressBar{{background:#f3f4f6;border-radius:3px;border:none;}}QProgressBar::chunk{{background:{rk};border-radius:3px;}}")
            saglay.addWidget(bar); saglay.addSpacing(6)
        saglay.addStretch(); arow.addWidget(sag)
        self._dash_icerik_lay.addLayout(arow)

    # ══════════════════════════════════════
    #  SAYFA 1 — YÜZ KAYDI
    # ══════════════════════════════════════
    def _yuz_kayit_sayfasi(self):
        w, lay = self._sayfa_wrap("Yeni Kullanıcı Kaydı","Sisteme yeni kullanıcı yüz verisi ekleyin")
        icerik = QHBoxLayout(); icerik.setSpacing(20)

        sol = kart_frame(); sol.setMinimumWidth(420)
        sk = QVBoxLayout(sol); sk.setContentsMargins(24,24,24,24); sk.setSpacing(10)
        bh = QLabel("Kişisel Bilgiler"); bh.setStyleSheet(f"font-size:15px;font-weight:bold;color:{YAZI_KOYU};border:none;margin-bottom:8px;"); sk.addWidget(bh)

        ad_row = QHBoxLayout(); ad_row.setSpacing(12)
        self._kayit_ad = QLineEdit(); self._kayit_ad.setPlaceholderText("Ad"); self._kayit_ad.setFixedHeight(38); self._kayit_ad.setStyleSheet(input_stili())
        self._kayit_soyad = QLineEdit(); self._kayit_soyad.setPlaceholderText("Soyad"); self._kayit_soyad.setFixedHeight(38); self._kayit_soyad.setStyleSheet(input_stili())
        for lbl_txt, widget in [("Ad",self._kayit_ad),("Soyad",self._kayit_soyad)]:
            col = QVBoxLayout(); lbl = QLabel(lbl_txt); lbl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
            col.addWidget(lbl); col.addWidget(widget); ad_row.addLayout(col)
        sk.addLayout(ad_row)

        self._kayit_eposta = QLineEdit(); self._kayit_eposta.setPlaceholderText("ornek@email.com"); self._kayit_eposta.setFixedHeight(38); self._kayit_eposta.setStyleSheet(input_stili())
        self._kayit_tel = QLineEdit(); self._kayit_tel.setPlaceholderText("+90 555 123 4567"); self._kayit_tel.setFixedHeight(38); self._kayit_tel.setStyleSheet(input_stili())
        self._kayit_cid = QLineEdit(); self._kayit_cid.setPlaceholderText("EMP-12345"); self._kayit_cid.setFixedHeight(38); self._kayit_cid.setStyleSheet(input_stili())
        for et, wg in [("E-posta",self._kayit_eposta),("Telefon",self._kayit_tel),("Çalışan ID",self._kayit_cid)]:
            lbl = QLabel(et); lbl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;"); sk.addWidget(lbl); sk.addWidget(wg)

        lbl_d = QLabel("Departman"); lbl_d.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;"); sk.addWidget(lbl_d)
        self._kayit_dep = QComboBox(); self._kayit_dep.setFixedHeight(38); self._kayit_dep.setStyleSheet(combobox_stili())
        self._kayit_dep.addItems(["Departman Seçin","Bilgi Teknolojileri","İnsan Kaynakları","Finans","Satış","Mühendislik","Güvenlik"])
        sk.addWidget(self._kayit_dep); sk.addStretch(); icerik.addWidget(sol)

        sag = kart_frame()
        sagk = QVBoxLayout(sag); sagk.setContentsMargins(24,24,24,24); sagk.setSpacing(12)
        bh2 = QLabel("Yüz Fotoğrafı"); bh2.setStyleSheet(f"font-size:15px;font-weight:bold;color:{YAZI_KOYU};border:none;"); sagk.addWidget(bh2)
        self.foto_onizleme = QLabel(); self.foto_onizleme.setFixedHeight(260); self.foto_onizleme.setAlignment(Qt.AlignCenter)
        self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px dashed #374151;color:#6b7280;font-size:14px;")
        self.foto_onizleme.setText("📷\n\nFotoğraf Burada\nGörünecek"); self._yuklenen_foto = None; sagk.addWidget(self.foto_onizleme)
        yb = mavi_btn("📂  Fotoğraf Seç / Yükle",44); yb.clicked.connect(self._foto_yukle); sagk.addWidget(yb)
        nl = QLabel("💡  JPG, PNG veya BMP formatı desteklenir.\nYüzün net ve aydınlık görünmesi önerilir.")
        nl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};background:#f9fafb;border-radius:8px;border:1px solid {SINIR};padding:10px;"); nl.setWordWrap(True); sagk.addWidget(nl)
        sagk.addStretch()
        kb = QPushButton("✅  Kaydı Tamamla"); kb.setFixedHeight(46); kb.setCursor(Qt.PointingHandCursor)
        kb.setStyleSheet("QPushButton{background:#059669;color:white;border:none;border-radius:10px;font-size:14px;font-weight:bold;}QPushButton:hover{background:#047857;}")
        kb.clicked.connect(self._kullanici_kaydet); sagk.addWidget(kb); icerik.addWidget(sag)
        lay.addLayout(icerik); lay.addStretch()
        return w

    def _foto_yukle(self):
        dosya, _ = QFileDialog.getOpenFileName(self,"Fotoğraf Seç","","Resim Dosyaları (*.jpg *.jpeg *.png *.bmp)")
        if dosya:
            pix = QPixmap(dosya).scaled(self.foto_onizleme.width()-10,self.foto_onizleme.height()-10,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self.foto_onizleme.setPixmap(pix)
            self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px solid #4A3FC7;")
            self._yuklenen_foto = dosya

    def _kullanici_kaydet(self):
        ad = self._kayit_ad.text().strip(); soyad = self._kayit_soyad.text().strip()
        eposta = self._kayit_eposta.text().strip(); tel = self._kayit_tel.text().strip()
        cid = self._kayit_cid.text().strip(); dep = self._kayit_dep.currentText()
        if not ad or not soyad: QMessageBox.warning(self,"Eksik","Ad ve soyad zorunludur!"); return
        if dep == "Departman Seçin": QMessageBox.warning(self,"Eksik","Lütfen departman seçin!"); return
        if not self._yuklenen_foto: QMessageBox.warning(self,"Fotoğraf Eksik","Lütfen fotoğraf yükleyin!"); return
        tam_ad = f"{ad} {soyad}"

        # Fotoğrafı kopyala
        foto_klasor = "yuzler"; os.makedirs(foto_klasor, exist_ok=True)
        uzanti = os.path.splitext(self._yuklenen_foto)[1]
        hedef = os.path.join(foto_klasor, f"{cid or tam_ad.replace(' ','_')}{uzanti}")
        import shutil; shutil.copy2(self._yuklenen_foto, hedef)

        basari = db_sorgula(
            "INSERT INTO yetkili_kisiler (isim,departman,telefon,calisan_id,eposta,foto_yolu,durum) VALUES (%s,%s,%s,%s,%s,%s,'Aktif')",
            (tam_ad, dep, tel, cid, eposta, hedef), geri_don=False)

        if basari:
            QMessageBox.information(self,"Başarılı",f"✅ {tam_ad} sisteme kaydedildi!")
            for wg in [self._kayit_ad,self._kayit_soyad,self._kayit_eposta,self._kayit_tel,self._kayit_cid]: wg.clear()
            self._kayit_dep.setCurrentIndex(0)
            self.foto_onizleme.setPixmap(QPixmap()); self.foto_onizleme.setText("📷\n\nFotoğraf Burada\nGörünecek")
            self.foto_onizleme.setStyleSheet("background:#111827;border-radius:10px;border:2px dashed #374151;color:#6b7280;font-size:14px;")
            self._yuklenen_foto = None; self._kullanicilari_yukle()
        else:
            QMessageBox.critical(self,"Hata","Kayıt sırasında hata oluştu!")

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
            QTableWidget{{background:white;border-radius:12px;border:1px solid {SINIR};gridline-color:#f3f4f6;font-family:'Segoe UI';}}
            QHeaderView::section{{background:#f9fafb;padding:10px 8px;font-size:11px;font-weight:bold;color:{YAZI_GRI};border:none;border-bottom:1px solid {SINIR};}}
            QTableWidget::item{{padding:8px;font-size:13px;color:{YAZI_KOYU};}}
            QTableWidget::item:selected{{background:#ede9fe;color:{ANA_MAVI};}}""")
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

        def q0(sql,p=None): r=db_sorgula(sql,p); return r[0][0] if r else 0
        toplam = q0("SELECT COUNT(*) FROM yetkili_kisiler")
        aktif  = q0("SELECT COUNT(*) FROM yetkili_kisiler WHERE durum='Aktif'")
        pasif  = toplam - aktif
        dep_s  = q0("SELECT COUNT(DISTINCT departman) FROM yetkili_kisiler")
        for sayi, etiket, ikon, bg, fg in [(toplam,"Toplam Kullanıcı","👥","#dbeafe","#1d4ed8"),(aktif,"Aktif","✅","#dcfce7","#15803d"),(pasif,"Pasif","🔴","#fee2e2","#dc2626"),(dep_s,"Departman","🏢","#ede9fe","#7c3aed")]:
            self._kul_krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))

        rows = db_sorgula("SELECT isim,calisan_id,departman,telefon,eposta,durum,foto_yolu FROM yetkili_kisiler ORDER BY isim") or []
        self._kullanici_verileri = []
        for r in rows:
            isim, kid, dep, tel,eposta, durum, foto = r
            gk = db_sorgula("SELECT tarih,saat FROM giris_kayitlari WHERE isim=%s ORDER BY tarih DESC,saat DESC LIMIT 1",(isim,))
            son_str = sure_metni(datetime.combine(gk[0][0],gk[0][1])) if gk else "Hiç giriş yok"
            self._kullanici_verileri.append((isim, eposta  or "-", kid or "-" , dep or "-", tel or "-", son_str, durum or "Aktif", foto or ""))
        self._tablo_doldur()

    def _tablo_doldur(self):
        t = self.kullanici_tablosu; t.setRowCount(len(self._kullanici_verileri))
        for i, (ad, eposta, kid, dep, tel, son, durum, foto) in enumerate(self._kullanici_verileri):
            t.setRowHeight(i,52)
            kw = QWidget(); kw.setStyleSheet("background:transparent;")
            kl = QHBoxLayout(kw); kl.setContentsMargins(8,4,8,4); kl.setSpacing(10)
            kl.addWidget(avatar_widget(get_initials(ad),AVATAR_RENKLER[i%len(AVATAR_RENKLER)],34))
            ic = QVBoxLayout(); ic.setSpacing(0)
            nl = QLabel(ad); nl.setStyleSheet(f"font-size:13px;font-weight:bold;color:{YAZI_KOYU};border:none;")
            ml2 = QLabel(eposta); ml2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            ic.addWidget(nl); ic.addWidget(ml2); kl.addLayout(ic); kl.addStretch(); t.setCellWidget(i,0,kw)
            for col, val in [(1,kid),(2,dep),(3,tel),(4,son)]:
                item = QTableWidgetItem(val); item.setTextAlignment(Qt.AlignCenter); t.setItem(i,col,item)
            dw = QWidget(); dw.setStyleSheet("background:transparent;")
            dl = QHBoxLayout(dw); dl.setContentsMargins(8,0,8,0); dl.setAlignment(Qt.AlignCenter)
            dlbl = QLabel(durum); dlbl.setStyleSheet(("background:#dcfce7;color:#15803d;" if durum=="Aktif" else "background:#fee2e2;color:#dc2626;")+"border-radius:10px;padding:3px 10px;font-size:11px;font-weight:bold;")
            dl.addWidget(dlbl); t.setCellWidget(i,5,dw)
            iw = QWidget(); iw.setStyleSheet("background:transparent;")
            il = QHBoxLayout(iw); il.setContentsMargins(6,4,6,4); il.setSpacing(6); il.setAlignment(Qt.AlignCenter)
            for emoji, tip, stil, fn in [("✏️","Düzenle","background:#eff6ff;",None),("🗑️","Sil","background:#fff1f2;",lambda _,r=i:self._kullanici_sil(r)),("🖼️","Fotoğraf","background:#f0fdf4;",lambda _,a=ad,f=foto:self._foto_goster(a,f))]:
                b = QPushButton(emoji); b.setFixedSize(30,30); b.setToolTip(tip); b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"QPushButton{{{stil}border:none;border-radius:6px;font-size:14px;}}QPushButton:hover{{opacity:0.8;}}")
                if fn: b.clicked.connect(fn)
                il.addWidget(b)
            t.setCellWidget(i,6,iw)

    def _kullanici_filtrele(self):
        arama = self._kullanici_arama.text().lower().strip()
        dep = self._kullanici_dep_filtre.currentText()
        for i, (ad, kid, d, tel, son, durum, foto) in enumerate(self._kullanici_verileri):
            a_ok = arama=="" or arama in ad.lower() or arama in kid.lower() or arama in tel.lower()
            d_ok = dep=="Tüm Departmanlar" or dep==d
            self.kullanici_tablosu.setRowHidden(i, not (a_ok and d_ok))

    def _kullanici_sil(self, row):
        ad = self._kullanici_verileri[row][0]
        r = QMessageBox.question(self,"Kullanıcı Sil",f"<b>{ad}</b> adlı kullanıcıyı silmek istediğinize emin misiniz?",QMessageBox.Yes|QMessageBox.No)
        if r == QMessageBox.Yes:
            db_sorgula("DELETE FROM yetkili_kisiler WHERE isim=%s",(ad,),geri_don=False)
            self._kullanicilari_yukle()

    def _foto_goster(self, ad, foto_yol):
        if not foto_yol or not os.path.exists(foto_yol):
            foto_yol, _ = QFileDialog.getOpenFileName(self,f"{ad} — Fotoğraf Seç","","Resim Dosyaları (*.jpg *.jpeg *.png *.bmp)")
            if not foto_yol: return
        FotoDiyalog(ad, foto_yol, self).exec_()

    # ══════════════════════════════════════
    #  SAYFA 3 — CANLI İZLEME
    # ══════════════════════════════════════
    def _canli_izleme_sayfasi(self):
        w, lay = self._sayfa_wrap("Canlı Kamera İzleme","Gerçek zamanlı yüz tanıma ve izleme sistemi")
        icerik = QHBoxLayout(); icerik.setSpacing(16)
        sol = QVBoxLayout(); sol.setSpacing(12)

        kk_frame = kart_frame(); kk = QVBoxLayout(kk_frame); kk.setContentsMargins(14,12,14,12); kk.setSpacing(8)
        ust = QHBoxLayout(); ust.setSpacing(10)
        canli_c = QFrame(); canli_c.setStyleSheet("background:rgba(239,68,68,0.12);border-radius:8px;border:1px solid rgba(239,68,68,0.35);")
        ccl = QHBoxLayout(canli_c); ccl.setContentsMargins(10,5,10,5); ccl.setSpacing(6)
        cdot = QLabel("●"); cdot.setStyleSheet("color:#ef4444;font-size:10px;border:none;")
        ctxt = QLabel("CANLI"); ctxt.setStyleSheet("color:#ef4444;font-size:12px;font-weight:bold;font-family:'Segoe UI';border:none;letter-spacing:1px;")
        ccl.addWidget(cdot); ccl.addWidget(ctxt); ust.addWidget(canli_c)
        self._saat_lbl = QLabel("--:--:--"); self._saat_lbl.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};border:none;"); ust.addWidget(self._saat_lbl); ust.addStretch()
        for ikon in ["🔍","⛶"]:
            ib = QPushButton(ikon); ib.setFixedSize(32,32); ib.setCursor(Qt.PointingHandCursor)
            ib.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,0.08);border:none;border-radius:6px;font-size:15px;}}QPushButton:hover{{background:rgba(0,0,0,0.06);}}")
            ust.addWidget(ib)
        kk.addLayout(ust)

        self.kamera_label = QLabel(); self.kamera_label.setMinimumSize(560,360); self.kamera_label.setAlignment(Qt.AlignCenter)
        self.kamera_label.setText("📷\n\nKamera 1 — Ana Giriş\n\nKamerayı başlatmak için\naşağıdaki butona basın")
        self.kamera_label.setStyleSheet("background:#0f172a;color:#6b7280;font-size:14px;border-radius:8px;border:none;")
        kk.addWidget(self.kamera_label)
        kad = QLabel("Kamera 1 — Ana Giriş"); kad.setAlignment(Qt.AlignCenter); kad.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;padding:4px 0;"); kk.addWidget(kad)
        sol.addWidget(kk_frame)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        kayit_btn = QPushButton("● Kayıt Başlat"); kayit_btn.setFixedHeight(38); kayit_btn.setCursor(Qt.PointingHandCursor)
        kayit_btn.setStyleSheet("QPushButton{background:#dc2626;color:white;border:none;border-radius:8px;font-size:13px;font-weight:bold;padding:0 16px;}QPushButton:hover{background:#b91c1c;}")
        btn_row.addWidget(kayit_btn)
        ekran_btn = QPushButton("📸  Ekran Görüntüsü"); ekran_btn.setFixedHeight(38); ekran_btn.setCursor(Qt.PointingHandCursor)
        ekran_btn.setStyleSheet(f"QPushButton{{background:white;color:{YAZI_KOYU};border:1px solid {SINIR};border-radius:8px;font-size:13px;padding:0 16px;}}QPushButton:hover{{background:#f9fafb;}}")
        ekran_btn.clicked.connect(self._ekran_goruntusu); btn_row.addWidget(ekran_btn)
        btn_row.addStretch()
        self.kamera_ac_btn = mavi_btn("▶  Kamerayı Başlat",38); self.kamera_ac_btn.setFixedWidth(165); self.kamera_ac_btn.clicked.connect(self._kamera_toggle); btn_row.addWidget(self.kamera_ac_btn)
        sol.addLayout(btn_row)

        alt_kart = kart_frame(); alt_kart.setFixedHeight(110)
        alt_kart.setStyleSheet(f"background:white;border-radius:10px;border:2px solid {ANA_MAVI};")
        ak = QHBoxLayout(alt_kart); ak.setContentsMargins(14,10,14,10); ak.setSpacing(14)
        mini = QLabel("📷"); mini.setFixedSize(100,70); mini.setAlignment(Qt.AlignCenter); mini.setStyleSheet("background:#0f172a;border-radius:6px;border:none;font-size:18px;"); ak.addWidget(mini)
        bilgi = QVBoxLayout(); bilgi.setSpacing(4)
        ki = QLabel("Kamera 1"); ki.setStyleSheet(f"font-size:14px;font-weight:bold;color:{YAZI_KOYU};border:none;")
        ky = QLabel("Ana Giriş"); ky.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        bilgi.addWidget(ki); bilgi.addWidget(ky)
        fps_row = QHBoxLayout(); fps_row.setSpacing(6)
        dot2 = QLabel("●"); dot2.setStyleSheet(f"color:{YESIL};font-size:12px;border:none;")
        fpsl = QLabel("Aktif  •  30 FPS"); fpsl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;")
        fps_row.addWidget(dot2); fps_row.addWidget(fpsl); fps_row.addStretch(); bilgi.addLayout(fps_row)
        ak.addLayout(bilgi); ak.addStretch()
        secili = QLabel("Aktif Kamera"); secili.setStyleSheet(f"background:{ANA_MAVI};color:white;border-radius:8px;padding:4px 12px;font-size:11px;font-weight:bold;border:none;"); ak.addWidget(secili)
        sol.addWidget(alt_kart); icerik.addLayout(sol,3)

        # Sağ panel
        sag = QVBoxLayout(); sag.setSpacing(12)
        ist = kart_frame(); ikl = QVBoxLayout(ist); ikl.setContentsMargins(18,16,18,16); ikl.setSpacing(10)
        ikl.addWidget(baslik_label("Anlık İstatistikler",14))
        bugun = datetime.now().date()
        def q0(sql,p=None): r=db_sorgula(sql,p); return r[0][0] if r else 0
        t_t=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s",(bugun,))
        b_s=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        y_s=q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        bas=round(b_s/t_t*100,1) if t_t>0 else 0
        for et,dg,rk in [("Aktif Kamera","1",ANA_MAVI),("Bugünkü Tespit",str(t_t),YAZI_KOYU),("Başarı Oranı",f"%{bas}",TURUNCU),("Bilinmeyen",str(y_s),KIRMIZI)]:
            r = QHBoxLayout(); e=QLabel(et); e.setStyleSheet(f"font-size:13px;color:{YAZI_GRI};border:none;"); r.addWidget(e); r.addStretch()
            d=QLabel(dg); d.setStyleSheet(f"font-size:14px;font-weight:bold;color:{rk};border:none;"); r.addWidget(d); ikl.addLayout(r); ikl.addWidget(sep_cizgi())
        cpu_r=QHBoxLayout(); cl=QLabel("CPU Kullanımı"); cl.setStyleSheet(f"font-size:12px;color:{YAZI_GRI};border:none;"); cpu_r.addWidget(cl); cpu_r.addStretch()
        cv=QLabel("%45"); cv.setStyleSheet(f"font-size:12px;font-weight:bold;color:{YAZI_KOYU};border:none;"); cpu_r.addWidget(cv); ikl.addLayout(cpu_r)
        cbar=QProgressBar(); cbar.setValue(45); cbar.setFixedHeight(6); cbar.setTextVisible(False)
        cbar.setStyleSheet(f"QProgressBar{{background:#f3f4f6;border-radius:3px;border:none;}}QProgressBar::chunk{{background:{ANA_MAVI};border-radius:3px;}}"); ikl.addWidget(cbar)
        sag.addWidget(ist)

        tp = kart_frame(); tkl = QVBoxLayout(tp); tkl.setContentsMargins(18,16,18,16); tkl.setSpacing(0)
        br_t = QHBoxLayout(); br_t.addWidget(baslik_label("Son Tespitler",14)); br_t.addStretch()
        tumu = QLabel("Tümü →"); tumu.setStyleSheet(f"font-size:12px;color:{ANA_MAVI};border:none;"); tumu.setCursor(Qt.PointingHandCursor); tumu.mousePressEvent=lambda e:self._git(4)
        br_t.addWidget(tumu); tkl.addLayout(br_t); tkl.addSpacing(10)
        son_t = db_sorgula("SELECT isim,durum,saat FROM giris_kayitlari WHERE tarih=%s ORDER BY saat DESC LIMIT 5",(bugun,)) or []
        for row in son_t:
            isim, durum, saat = row; ok = durum=="Basarili"
            r = QHBoxLayout(); r.setSpacing(10)
            ic=QLabel("✓" if ok else "⚠"); ic.setFixedSize(26,26); ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"background:{'#dcfce7' if ok else '#fef3c7'};border-radius:13px;color:{'#15803d' if ok else '#d97706'};font-size:12px;border:none;"); r.addWidget(ic)
            col=QVBoxLayout(); col.setSpacing(1)
            al=QLabel(isim); al.setStyleSheet(f"font-size:12px;font-weight:bold;color:{YAZI_KOYU};border:none;")
            cl2=QLabel("Kamera 1"); cl2.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;")
            col.addWidget(al); col.addWidget(cl2); r.addLayout(col); r.addStretch()
            sl=QLabel(str(saat)[:8] if saat else "-"); sl.setAlignment(Qt.AlignRight); sl.setStyleSheet(f"font-size:11px;color:{YAZI_GRI};border:none;"); r.addWidget(sl)
            tkl.addLayout(r); tkl.addWidget(sep_cizgi())
        sag.addWidget(tp); sag.addStretch(); icerik.addLayout(sag,1); lay.addLayout(icerik)

        self._kamera_aktif = False
        timer = QTimer(self); timer.timeout.connect(self._saat_guncelle); timer.start(1000)
        return w

    def _saat_guncelle(self):
        self._saat_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _kamera_toggle(self):
        if not self._kamera_aktif:
            self._kamera_aktif = True
            self.kamera_ac_btn.setText("⏹  Kamerayı Durdur")
            self.kamera_ac_btn.setStyleSheet("QPushButton{background:#dc2626;color:white;border:none;border-radius:8px;font-size:13px;font-weight:bold;}QPushButton:hover{background:#b91c1c;}")
            self.kamera_label.setText("🟢\n\nKamera Aktif\n\nOpenCV entegrasyonu\nburada çalışacak")
            self.kamera_label.setStyleSheet("background:#0f172a;color:#22c55e;font-size:14px;border:none;margin:0 14px;")
        else:
            self._kamera_aktif = False
            self.kamera_ac_btn.setText("▶  Kamerayı Başlat")
            self.kamera_ac_btn.setStyleSheet(f"QPushButton{{background:{ANA_MAVI};color:white;border:none;border-radius:8px;font-size:13px;font-weight:bold;}}QPushButton:hover{{background:#3a30a8;}}")
            self.kamera_label.setText("📷\n\nKamera 1 — Ana Giriş\n\nKamerayı başlatmak için\naşağıdaki butona basın")
            self.kamera_label.setStyleSheet("background:#0f172a;color:#6b7280;font-size:14px;border:none;margin:0 14px;")

    def _ekran_goruntusu(self):
        masa_ustu = os.path.join(os.path.expanduser("~"),"Desktop")
        dosya_adi = f"kamera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        tam_yol = os.path.join(masa_ustu, dosya_adi)
        pixmap = self.kamera_label.grab()
        if pixmap.save(tam_yol): QMessageBox.information(self,"Ekran Görüntüsü",f"✅ Masaüstüne kaydedildi:\n{dosya_adi}")
        else: QMessageBox.warning(self,"Hata","Kaydedilemedi.")

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
        self._gecmis_tip.addItems(["Tüm Kayıtlar","Giriş","Çıkış","Bilinmeyen"]); self._gecmis_tip.currentTextChanged.connect(self._gecmis_filtrele); f_row.addWidget(self._gecmis_tip,1)
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
            QTableWidget{{background:white;border-radius:12px;border:1px solid {SINIR};gridline-color:#f3f4f6;font-family:'Segoe UI';}}
            QHeaderView::section{{background:#f9fafb;padding:10px 8px;font-size:11px;font-weight:bold;color:{YAZI_GRI};border:none;border-bottom:1px solid {SINIR};}}
            QTableWidget::item{{padding:6px 8px;font-size:13px;color:{YAZI_KOYU};}}
            QTableWidget::item:selected{{background:#ede9fe;}}""")
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
        def q0(sql,p=None): r=db_sorgula(sql,p); return r[0][0] if r else 0
        t=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s",(bugun,))
        g=q0("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s AND durum='Basarili'",(bugun,))
        y=q0("SELECT COUNT(*) FROM yetkisiz_kayitlar WHERE tarih=%s",(bugun,))
        for sayi, etiket, ikon, bg, fg in [(t,"Toplam Kayıt","📋","#dbeafe","#1d4ed8"),(g,"Giriş","✅","#dcfce7","#15803d"),(t-g,"Diğer","🔄","#fef3c7","#d97706"),(y,"Bilinmeyen","⚠️","#fee2e2","#dc2626")]:
            self._gec_krow.addWidget(self._stat_kart(sayi,etiket,ikon,bg,fg))

        giris_rows = db_sorgula("SELECT isim,durum,tarih,saat FROM giris_kayitlari ORDER BY tarih DESC,saat DESC LIMIT 100") or []
        yt_rows = db_sorgula("SELECT foto_yolu,tarih,saat FROM yetkisiz_kayitlar ORDER BY tarih DESC,saat DESC LIMIT 50") or []
        self._gecmis_verileri = []
        idx = 1
        for isim, durum, tarih, saat in giris_rows:
            tip = "Giriş" if durum=="Basarili" else "Çıkış"; ok = durum=="Basarili"
            self._gecmis_verileri.append((f"#{idx:04d}",isim,tip,tarih.strftime("%d.%m.%Y") if hasattr(tarih,'strftime') else str(tarih),str(saat)[:8] if saat else "-","Kamera 1","—",ok))
            idx+=1
        for foto, tarih, saat in yt_rows:
            self._gecmis_verileri.append((f"#{idx:04d}","Bilinmeyen Kişi","Bilinmeyen",tarih.strftime("%d.%m.%Y") if hasattr(tarih,'strftime') else str(tarih),str(saat)[:8] if saat else "-","Kamera 1","—",False))
            idx+=1
        self._gecmis_tablo_doldur()

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
            tlbl = QLabel(tip); tlbl.setStyleSheet({"Giriş":"background:#dcfce7;color:#15803d;","Çıkış":"background:#fef3c7;color:#d97706;","Bilinmeyen":"background:#fee2e2;color:#dc2626;"}.get(tip,"")+"border-radius:8px;padding:2px 8px;font-size:11px;font-weight:bold;")
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
        wb.save(dosya); QMessageBox.information(self,"Başarılı",f"✅ Kaydedildi:\n{dosya}")


# ══════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    pencere = Dashboard()
    pencere.showMaximized()
    sys.exit(app.exec_())
