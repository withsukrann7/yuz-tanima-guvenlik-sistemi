"""Arayüz duman testleri (Qt 'offscreen'; kamera yok, gerçek PostgreSQL gerekir).

YUZ_TEST_DB_NAME tanımlı değilse atlanır. Giriş penceresi testi, orijinal
ui/login.ui dosyası depoda olmadığı için, aynı nesne adlarını taşıyan SENTETİK
bir .ui ile yapılır (yalnızca kodun bağlantılarını doğrular).
"""
import os
import time
from datetime import date

import numpy as np
import pytest

if not os.getenv("YUZ_TEST_DB_NAME"):
    pytest.skip("YUZ_TEST_DB_NAME tanımlı değil", allow_module_level=True)

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication, QMessageBox

from yuz_tanima_app import config, veritabani, yuz_tanima


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ortam(monkeypatch, tmp_path, qapp):
    monkeypatch.setenv("YUZ_DB_NAME", os.environ["YUZ_TEST_DB_NAME"])
    for k in ("HOST", "PORT", "USER", "PASSWORD"):
        if os.getenv(f"YUZ_TEST_DB_{k}"):
            monkeypatch.setenv(f"YUZ_DB_{k}", os.environ[f"YUZ_TEST_DB_{k}"])
    veritabani.calistir("DROP TABLE IF EXISTS yetkili_kisiler, giris_kayitlari, yetkisiz_kayitlar")
    veritabani.sema_olustur()

    for ad in ("known_faces", "yuzler", "snapshots", "arsiv/silinen_yuzler"):
        (tmp_path / ad).mkdir(parents=True)
    monkeypatch.setattr(config, "PROJE_KOKU", tmp_path)
    monkeypatch.setattr(config, "BILINEN_YUZLER_DIZINI", tmp_path / "known_faces")
    monkeypatch.setattr(config, "YUZLER_DIZINI", tmp_path / "yuzler")
    monkeypatch.setattr(config, "SNAPSHOT_DIZINI", tmp_path / "snapshots")
    monkeypatch.setattr(config, "ARSIV_SILINEN_YUZLER", tmp_path / "arsiv" / "silinen_yuzler")
    monkeypatch.setattr(config, "GUVENLIK_LOG_DOSYASI", tmp_path / "security_log.json")

    mesajlar = []
    for ad in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, ad, staticmethod(lambda *a, _ad=ad, **k: mesajlar.append((_ad, a[1:3])) or QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    from yuz_tanima_app import dashboard as d
    monkeypatch.setattr(d.YetkisizUyariDiyalog, "exec_", lambda self: 0)
    return tmp_path, mesajlar


def bekle(kosul, sn=15):
    son = time.time() + sn
    while time.time() < son:
        QCoreApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.02)
    return False


def sayi(sql):
    return veritabani.tek_deger(sql)


def test_dashboard_acilir_db_uyarisi_yok(ortam):
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    assert d.stack.count() == 5
    assert d._db_uyari.isHidden()
    for i in range(5):                       # her sayfaya geçiş hatasız
        d._git(i)


def test_db_yokken_acilir_ve_uyarir(ortam, monkeypatch):
    monkeypatch.setenv("YUZ_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("YUZ_DB_PORT", "1")
    monkeypatch.setenv("YUZ_DB_TIMEOUT", "2")
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    assert not d._db_uyari.isHidden()        # kalıcı uyarı görünür
    d._baslangic_kontrolleri()
    _, mesajlar = ortam
    assert any(t == "warning" and "Veritabanı" in a[0] for t, a in mesajlar)
    d._yetkisiz_olay("/x.jpg", "10:00:00")   # DB yok: çökmeden devam etmeli
    assert not d._db_uyari.isHidden()


def test_yetkisiz_olay_bir_kez_kaydeder_foto_goster_kaydetmez(ortam):
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    d._yetkisiz_olay("/tmp/a.jpg", "10:00:00")
    assert sayi("SELECT COUNT(*) FROM yetkisiz_kayitlar") == 1
    d._yetkisiz_foto_goster("/tmp/a.jpg", "10:00:00")   # "Fotoğrafı Gör" düğmesi
    d._yetkisiz_foto_goster("/tmp/a.jpg", "10:00:00")
    assert sayi("SELECT COUNT(*) FROM yetkisiz_kayitlar") == 1


def test_yetkili_olay_kaydeder(ortam):
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    d._yetkili_islemi("Ali Veli", 0.9)
    assert sayi(f"SELECT COUNT(*) FROM giris_kayitlari WHERE isim='Ali Veli' AND tarih='{date.today()}'") == 1


def test_kayit_ve_silme_akisi(ortam, tmp_path):
    kok, mesajlar = ortam
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()

    foto = tmp_path / "kaynak şğ.jpg"
    assert yuz_tanima.gorsel_yaz(foto, np.full((120, 120, 3), 128, np.uint8))
    d._kayit_ad.setText("Ayşe"); d._kayit_soyad.setText("Kaya")
    d._kayit_cid.setText("../EMP/7")                     # yol kaçışı denemesi
    d._kayit_dep.setCurrentIndex(1)
    d._yuklenen_foto = str(foto)
    d._kullanici_kaydet()                                # yüz yok → question(Yes) ile devam

    satir = veritabani.calistir("SELECT isim,calisan_id,foto_yolu,durum FROM yetkili_kisiler", getir=True)
    assert len(satir) == 1 and satir[0][0] == "Ayşe Kaya" and satir[0][3] == "Aktif"
    foto_yolu = satir[0][2]
    assert not foto_yolu.startswith(("/", "..")) and foto_yolu.startswith("yuzler/")
    assert (kok / foto_yolu).exists()
    assert (kok / "yuzler").resolve() == (kok / foto_yolu).resolve().parent   # klasör dışına yazılmadı

    # kayıtlı kişi tanıma listesine girer
    yuzler, _ = yuz_tanima.bilinen_yuzleri_yukle()
    assert "Ayşe Kaya" in yuzler

    # silme: DB satırı gider, dosya SİLİNMEZ, arşive taşınır, tanıma listesinden çıkar
    d._git(2)
    d._kullanici_sil(0)
    assert sayi("SELECT COUNT(*) FROM yetkili_kisiler") == 0
    assert not (kok / foto_yolu).exists()
    assert len(list((kok / "arsiv" / "silinen_yuzler").iterdir())) == 1
    yuzler, _ = yuz_tanima.bilinen_yuzleri_yukle()
    assert "Ayşe Kaya" not in yuzler


def test_kayit_gecersiz_foto_reddedilir(ortam, tmp_path):
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    bozuk = tmp_path / "bozuk.jpg"; bozuk.write_bytes(b"resim degil")
    d._kayit_ad.setText("A"); d._kayit_soyad.setText("B"); d._kayit_dep.setCurrentIndex(1)
    d._yuklenen_foto = str(bozuk)
    d._kullanici_kaydet()
    assert sayi("SELECT COUNT(*) FROM yetkili_kisiler") == 0
    assert list((config.YUZLER_DIZINI).iterdir()) == []


def test_kayit_db_hatasinda_dosya_temizlenir(ortam, tmp_path):
    from yuz_tanima_app.dashboard import Dashboard
    d = Dashboard()
    veritabani.calistir("DROP TABLE yetkili_kisiler")        # INSERT başarısız olsun
    foto = tmp_path / "f.jpg"
    yuz_tanima.gorsel_yaz(foto, np.full((120, 120, 3), 99, np.uint8))
    d._kayit_ad.setText("A"); d._kayit_soyad.setText("B"); d._kayit_dep.setCurrentIndex(1)
    d._yuklenen_foto = str(foto)
    d._kullanici_kaydet()
    assert list(config.YUZLER_DIZINI.iterdir()) == []         # sahipsiz kopya kalmadı
    assert not d._db_uyari.isHidden()


def test_kamera_yoksa_hata_gosterir_ve_arayuz_sifirlanir(ortam, monkeypatch):
    _, mesajlar = ortam
    from yuz_tanima_app.dashboard import Dashboard
    monkeypatch.setattr(config, "KAMERA_INDEKSI", 99)        # olmayan kamera
    d = Dashboard()
    if not yuz_tanima.deepface_hazir():
        pytest.skip("DeepFace yüklü değil")
    d._kamera_toggle()
    assert bekle(lambda: d._kamera_thread is None), "thread kendiliğinden sonlanmadı"
    assert d.kamera_ac_btn.text().startswith("▶")
    assert any(t == "warning" and "Kamera açılamadı" in a[1] for t, a in mesajlar)


SENTETIK_UI = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0"><class>MainWindow</class>
<widget class="QMainWindow" name="MainWindow">
 <widget class="QWidget" name="centralwidget">
  <widget class="QLabel" name="backgroundLabel"/>
  <widget class="QFrame" name="loginFrame">
   <widget class="QLabel" name="logoLabel"/>
   <widget class="QLineEdit" name="usernamenput"/>
   <widget class="QLineEdit" name="passwordInput"/>
   <widget class="QPushButton" name="loginButton"/>
  </widget>
 </widget>
</widget></ui>"""


def test_login_penceresi_sentetik_ui(ortam, monkeypatch, tmp_path):
    _, mesajlar = ortam
    ui = tmp_path / "login.ui"; ui.write_text(SENTETIK_UI, encoding="utf-8")
    monkeypatch.setattr(config, "LOGIN_UI", ui)
    monkeypatch.setenv("YUZ_ADMIN_USER", "u"); monkeypatch.setenv("YUZ_ADMIN_PASSWORD", "p")
    from yuz_tanima_app.giris import LoginWindow
    w = LoginWindow()
    w.usernamenput.setText("u"); w.passwordInput.setText("yanlis"); w.loginButton.click()
    assert any(t == "warning" and a[0] == "Hata" for t, a in mesajlar)
    assert not hasattr(w, "dashboard")
    w.passwordInput.setText("p"); w.loginButton.click()
    assert hasattr(w, "dashboard")


def test_login_ui_dosyasi_yoksa_acik_hata(monkeypatch, tmp_path, qapp):
    monkeypatch.setattr(config, "LOGIN_UI", tmp_path / "yok.ui")
    from yuz_tanima_app.giris import LoginWindow
    with pytest.raises(FileNotFoundError, match="login.ui"):
        LoginWindow()
