"""Harici bağımlılık gerektirmeyen temel testler (kamera/PostgreSQL/DeepFace yok)."""
import numpy as np
import pytest

from yuz_tanima_app import config, yuz_tanima
from yuz_tanima_app.kamera import ascii_cevir


def test_guvenli_dosya_adi_yol_kacisini_engeller():
    assert "/" not in yuz_tanima.guvenli_dosya_adi("../../etc/passwd")
    assert ".." not in yuz_tanima.guvenli_dosya_adi("..\\..\\x")
    assert yuz_tanima.guvenli_dosya_adi("EMP-12345") == "EMP-12345"
    assert yuz_tanima.guvenli_dosya_adi("///") == "kisi"


def test_normalize_turkce_buyuk_kucuk():
    assert yuz_tanima.normalize("IŞIK_Yılmaz") == yuz_tanima.normalize("ışık yılmaz")
    assert yuz_tanima.normalize("İlker") == yuz_tanima.normalize("ilker")


def test_ascii_cevir():
    assert ascii_cevir("Şükran Yılmaz") == "Sukran Yilmaz"


def test_yol_coz_goreli_ve_mutlak(tmp_path):
    assert config.yol_coz("yuzler/a.jpg") == config.PROJE_KOKU / "yuzler" / "a.jpg"
    assert config.yol_coz(str(tmp_path)) == tmp_path
    assert config.yol_coz("") is None


def test_gorsel_yaz_oku_unicode_yol(tmp_path):
    klasor = tmp_path / "Masaüstü şğ"
    klasor.mkdir()
    yol = klasor / "yüz.jpg"
    img = np.full((40, 40, 3), 127, np.uint8)
    assert yuz_tanima.gorsel_yaz(yol, img)
    okunan = yuz_tanima.gorsel_oku(yol)
    assert okunan is not None and okunan.shape == (40, 40, 3)


def test_gorsel_oku_bozuk_dosya(tmp_path):
    bozuk = tmp_path / "bozuk.jpg"
    bozuk.write_bytes(b"bu bir resim degil")
    assert yuz_tanima.gorsel_oku(bozuk) is None
    assert yuz_tanima.gorsel_oku(tmp_path / "yok.jpg") is None


def test_kimlik_dogrulama_yapilandirma_yoksa_reddeder(monkeypatch):
    from yuz_tanima_app.giris import kimlik_dogru_mu
    monkeypatch.delenv("YUZ_ADMIN_USER", raising=False)
    monkeypatch.delenv("YUZ_ADMIN_PASSWORD", raising=False)
    assert kimlik_dogru_mu("admin", "") is False
    assert kimlik_dogru_mu("", "") is False


def test_kimlik_dogrulama(monkeypatch):
    from yuz_tanima_app.giris import kimlik_dogru_mu
    monkeypatch.setenv("YUZ_ADMIN_USER", "yonetici")
    monkeypatch.setenv("YUZ_ADMIN_PASSWORD", "test-parolasi")
    assert kimlik_dogru_mu("yonetici", "test-parolasi")
    assert not kimlik_dogru_mu("yonetici", "yanlis")
    assert not kimlik_dogru_mu("baska", "test-parolasi")


def test_db_ayarlari_ortamdan(monkeypatch):
    monkeypatch.setenv("YUZ_DB_HOST", "db.ornek")
    monkeypatch.setenv("YUZ_DB_PASSWORD", "x")
    a = config.veritabani_ayarlari()
    assert a["host"] == "db.ornek" and a["password"] == "x"
    monkeypatch.delenv("YUZ_DB_PASSWORD")
    assert "password" not in config.veritabani_ayarlari()


def test_veritabani_erisilemezse_hata_yukseltir(monkeypatch):
    from yuz_tanima_app import veritabani
    monkeypatch.setenv("YUZ_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("YUZ_DB_PORT", "1")          # dinleyen yok
    monkeypatch.setenv("YUZ_DB_TIMEOUT", "2")
    with pytest.raises(veritabani.VeritabaniHatasi):
        veritabani.calistir("SELECT 1", getir=True)
    ok, mesaj = veritabani.durum_kontrolu()
    assert ok is False and mesaj


def test_tanima_kaynagi_db_yokken_known_faces_kullanir(monkeypatch, tmp_path):
    """DB erişilemezse hata yutulmaz: uyarı üretilir, known_faces/ yedek olarak yüklenir."""
    from yuz_tanima_app import veritabani
    kf = tmp_path / "known_faces"; kf.mkdir()
    img = np.full((50, 50, 3), 90, np.uint8)
    assert yuz_tanima.gorsel_yaz(kf / "ali_veli.jpg", img)
    (kf / "bozuk.png").write_bytes(b"x")
    monkeypatch.setattr(config, "BILINEN_YUZLER_DIZINI", kf)

    def patla(*a, **k):
        raise veritabani.VeritabaniHatasi("baglanti reddedildi")
    monkeypatch.setattr(veritabani, "calistir", patla)

    yuzler, uyarilar = yuz_tanima.bilinen_yuzleri_yukle()
    assert list(yuzler) == ["Ali Veli"]
    assert any("Veritabanına ulaşılamadı" in u for u in uyarilar)
    assert any("bozuk.png" in u for u in uyarilar)


def test_identify_deepface_yoksa_alarm_vermez_hata_yukseltir(monkeypatch):
    monkeypatch.setattr(yuz_tanima, "DeepFace", None)
    monkeypatch.setattr(yuz_tanima, "bilinen_yuzleri_yukle", lambda: ({}, []))
    tanici = yuz_tanima.FaceRecognizer()
    with pytest.raises(RuntimeError):
        tanici.identify(np.zeros((10, 10, 3), np.uint8))


def test_baglanti_hatasindan_sonra_kisa_sure_yeniden_denemez(monkeypatch):
    """Ulaşılamayan DB için her sorguda zaman aşımı beklenip arayüz donmasın."""
    import psycopg2
    from yuz_tanima_app import veritabani
    cagri = []

    def patla(**kw):
        cagri.append(1)
        raise psycopg2.OperationalError("baglanti zaman asimi")
    monkeypatch.setattr(veritabani.psycopg2, "connect", patla)
    for _ in range(5):
        with pytest.raises(veritabani.VeritabaniHatasi, match="zaman asimi"):
            veritabani.calistir("SELECT 1", getir=True)
    assert len(cagri) == 1                      # 5 sorgu, 1 gerçek deneme
    veritabani.hata_durumunu_sifirla()
    with pytest.raises(veritabani.VeritabaniHatasi):
        veritabani.calistir("SELECT 1", getir=True)
    assert len(cagri) == 2
