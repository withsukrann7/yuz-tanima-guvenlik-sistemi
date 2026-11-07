"""İsteğe bağlı uçtan uca tanıma testi (gerçek DeepFace + VGG-Face ağırlıkları, ~580 MB indirir).

Çalıştırmak için:  YUZ_TEST_DEEPFACE=1 pytest tests/test_deepface_opsiyonel.py
Test yüzü olarak scikit-image'in paketli örnek portresi kullanılır (pip install scikit-image).
"""
import os

import cv2
import numpy as np
import pytest

if os.getenv("YUZ_TEST_DEEPFACE") != "1":
    pytest.skip("YUZ_TEST_DEEPFACE=1 değil", allow_module_level=True)
skimage_data = pytest.importorskip("skimage.data")

from PyQt5.QtWidgets import QApplication

from yuz_tanima_app import config, veritabani, yuz_tanima
from yuz_tanima_app.kamera import KameraThread


@pytest.fixture
def kamera(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    assert yuz_tanima.deepface_yukle()
    monkeypatch.setattr(config, "BILINEN_YUZLER_DIZINI", tmp_path / "known_faces")
    monkeypatch.setattr(config, "SNAPSHOT_DIZINI", tmp_path / "snapshots")
    monkeypatch.setattr(config, "GUVENLIK_LOG_DOSYASI", tmp_path / "security_log.json")
    (tmp_path / "known_faces").mkdir()
    # DB kullanmadan yalnızca known_faces/ ile çalış
    def db_yok(*a, **k):
        raise veritabani.VeritabaniHatasi("test: DB yok")
    monkeypatch.setattr(veritabani, "calistir", db_yok)

    astronot = cv2.cvtColor(skimage_data.astronaut(), cv2.COLOR_RGB2BGR)
    siniflandirici = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    yuzler = siniflandirici.detectMultiScale(cv2.cvtColor(astronot, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(60, 60))
    assert len(yuzler) >= 1, "test görüntüsünde yüz bulunamadı"
    x, y, w, h = max(yuzler, key=lambda f: f[2] * f[3])
    yuz = astronot[y:y + h, x:x + w]
    yuz_tanima.gorsel_yaz(tmp_path / "known_faces" / "eileen_collins.jpg", yuz)
    return KameraThread(), astronot, yuz


def test_yetkili_yuz_taninir_ve_olay_uretir(kamera):
    th, tam, yuz = kamera
    yetkili, yetkisiz = [], []
    th.yetkili_giris.connect(lambda ad, g: yetkili.append((ad, g)))
    th.yetkisiz_giris.connect(lambda yol, s: yetkisiz.append(yol))
    # biraz farklı bir kırpma/ölçek: gerçek kameradaki varyasyonu taklit eder
    farkli = cv2.resize(yuz, None, fx=0.8, fy=0.8)
    th._analyze_async(farkli, tam.copy())
    assert yetkili and yetkili[0][0] == "Eileen Collins" and not yetkisiz
    assert (config.GUVENLIK_LOG_DOSYASI).exists()


def test_yabanci_goruntu_bilinmeyen_ve_snapshot(kamera):
    th, tam, _ = kamera
    yetkili, yetkisiz = [], []
    th.yetkili_giris.connect(lambda ad, g: yetkili.append(ad))
    th.yetkisiz_giris.connect(lambda yol, s: yetkisiz.append(yol))
    gurultu = np.random.default_rng(1).integers(0, 255, (150, 150, 3), dtype=np.uint8)
    th._analyze_async(gurultu, tam.copy())
    assert not yetkili and len(yetkisiz) == 1
    assert os.path.exists(yetkisiz[0])
    assert th._analysis_running is False
