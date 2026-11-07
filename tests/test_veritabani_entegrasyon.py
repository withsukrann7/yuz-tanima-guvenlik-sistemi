"""Gerçek PostgreSQL gerektirir. YUZ_TEST_DB_* tanımlı değilse atlanır.

Örnek:  YUZ_TEST_DB_NAME=yuz_tanima_test YUZ_TEST_DB_PORT=5433 pytest
(Test veritabanındaki tablolar test sırasında oluşturulur/temizlenir; ASIL
veritabanınıza karşı ÇALIŞTIRMAYIN.)
"""
import os
from datetime import date

import numpy as np
import pytest

from yuz_tanima_app import config, veritabani, yuz_tanima

if not os.getenv("YUZ_TEST_DB_NAME"):
    pytest.skip("YUZ_TEST_DB_NAME tanımlı değil", allow_module_level=True)


@pytest.fixture(autouse=True)
def test_db(monkeypatch):
    monkeypatch.setenv("YUZ_DB_NAME", os.environ["YUZ_TEST_DB_NAME"])
    for k in ("HOST", "PORT", "USER", "PASSWORD"):
        if os.getenv(f"YUZ_TEST_DB_{k}"):
            monkeypatch.setenv(f"YUZ_DB_{k}", os.environ[f"YUZ_TEST_DB_{k}"])
    veritabani.calistir("DROP TABLE IF EXISTS yetkili_kisiler, giris_kayitlari, yetkisiz_kayitlar")
    veritabani.sema_olustur()
    yield


def test_sema_idempotent_ve_durum_kontrolu():
    veritabani.sema_olustur()
    assert veritabani.durum_kontrolu() == (True, "")


def test_eksik_tablo_durum_kontrolunde_gorunur():
    veritabani.calistir("DROP TABLE giris_kayitlari")
    ok, mesaj = veritabani.durum_kontrolu()
    assert not ok and "giris_kayitlari" in mesaj


def test_kayit_fonksiyonlari():
    veritabani.yetkili_giris_kaydet("Ali Veli")
    veritabani.yetkisiz_giris_kaydet("/tmp/x.jpg")
    assert veritabani.tek_deger("SELECT COUNT(*) FROM giris_kayitlari WHERE tarih=%s", (date.today(),)) == 1
    assert veritabani.tek_deger("SELECT COUNT(*) FROM yetkisiz_kayitlar") == 1


def test_sorgu_hatasi_yukselir():
    with pytest.raises(veritabani.VeritabaniHatasi):
        veritabani.calistir("SELECT * FROM olmayan_tablo", getir=True)


def test_tanima_kaynagi_db_aktif_pasif_ve_legacy(monkeypatch, tmp_path):
    kf = tmp_path / "known_faces"; kf.mkdir()
    yz = tmp_path / "yuzler"; yz.mkdir()
    monkeypatch.setattr(config, "BILINEN_YUZLER_DIZINI", kf)
    monkeypatch.setattr(config, "YUZLER_DIZINI", yz)
    monkeypatch.setattr(config, "PROJE_KOKU", tmp_path)

    img = lambda v: np.full((50, 50, 3), v, np.uint8)
    yuz_tanima.gorsel_yaz(yz / "EMP-1.jpg", img(10))       # aktif kullanıcı (DB foto_yolu)
    yuz_tanima.gorsel_yaz(yz / "EMP-2.jpg", img(20))       # pasif kullanıcı
    yuz_tanima.gorsel_yaz(kf / "EMP-3.jpg", img(30))       # aktif; foto_yolu bozuk → known_faces/<cid> yedeği
    yuz_tanima.gorsel_yaz(kf / "eski_kisi.jpg", img(40))   # DB'de yok → eski kayıt
    yuz_tanima.gorsel_yaz(kf / "EMP-2.png", img(50))       # pasif kullanıcının known_faces kopyası → tanınmamalı

    veritabani.calistir(
        "INSERT INTO yetkili_kisiler (isim,calisan_id,foto_yolu,durum) VALUES "
        "('Ayşe Kaya','EMP-1','yuzler/EMP-1.jpg','Aktif'),"
        "('Pasif Kişi','EMP-2','yuzler/EMP-2.jpg','Pasif'),"
        "('Mehmet Demir','EMP-3','yuzler/yok.jpg','Aktif')")

    yuzler, uyarilar = yuz_tanima.bilinen_yuzleri_yukle()
    assert set(yuzler) == {"Ayşe Kaya", "Mehmet Demir", "Eski Kisi"}
    assert "Pasif Kişi" not in yuzler
