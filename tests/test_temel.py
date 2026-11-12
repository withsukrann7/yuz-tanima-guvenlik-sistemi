"""Harici bağımlılık gerektirmeyen temel testler (kamera/PostgreSQL/DeepFace yok)."""
import numpy as np
import pytest

from yuz_tanima_app import config, yuz_tanima
from yuz_tanima_app.kamera import ascii_cevir, erisim_karari
from yuz_tanima_app.yuz_bulucu import yuz_kirp


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


def test_yuz_kirpma_payi_kenarda_kesilir():
    """%25 pay eklenir; görüntü dışına taşan kısım kesilir, kutu büyütülerek ezilmez."""
    img = np.zeros((100, 120, 3), np.uint8)
    kirp = yuz_kirp(img, (0, 0, 40, 20), 0.25)
    assert kirp.shape == (25, 50, 3)
    assert yuz_kirp(img, (5, 5, 0, 10), 0.25) is None
    assert yuz_kirp(None, (0, 0, 10, 10), 0.25) is None


def test_tek_kare_ne_kapi_acar_ne_alarm_verir():
    assert config.KARAR_MIN_ORNEK >= 2
    assert config.DEDEKTOR == "skip"
    assert config.MODEL_ADI == "VGG-Face" and config.MESAFE_METRIGI == "cosine"
    assert erisim_karari([(True, "Ali")], 2) == ("bekliyor", None)
    assert erisim_karari([(False, None)], 2) == ("bekliyor", None)
    assert erisim_karari([(True, "Ali"), (True, "Ali")], 2) == ("yetkili", "Ali")
    assert erisim_karari([(False, None), (False, None)], 2) == ("yetkisiz", None)
    assert erisim_karari([(True, "Ali"), (False, None)], 2) == ("bekliyor", None)
    assert erisim_karari([(True, "Ali"), (True, "Veli")], 2) == ("bekliyor", None)
    assert erisim_karari([(False, None), (True, "Ali"), (True, "Ali")], 2) == ("yetkili", "Ali")


def test_esik_okunamazsa_resmi_varsayilan_kalir(monkeypatch):
    monkeypatch.setattr(yuz_tanima, "_ESIK", None)
    monkeypatch.setattr(yuz_tanima, "_deepface_esigi", lambda: None)
    assert yuz_tanima.model_esigi() == 0.68
    yuz_tanima._ESIK = None


def test_kosinus_ayni_vektor_sifir_mesafe():
    v = np.array([0.0, 3.0, 4.0])
    assert yuz_tanima.kosinus_mesafesi(v, v) == pytest.approx(0.0)
    assert yuz_tanima.kosinus_mesafesi(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(1.0)
    assert yuz_tanima.kosinus_mesafesi(np.array([0.0, 0.0]), np.array([1.0, 0.0])) == 1.0


def _sahte_tanici(monkeypatch, isimler):
    img = np.zeros((6, 6, 3), np.uint8)
    yuzler = {ad: img for ad in isimler}
    monkeypatch.setattr(yuz_tanima, "bilinen_yuzleri_yukle", lambda: (dict(yuzler), []))
    monkeypatch.setattr(
        yuz_tanima, "referanslari_kirp",
        lambda gelen: (dict(gelen), {ad: "skip" for ad in gelen}, []),
    )
    monkeypatch.setattr(yuz_tanima, "DeepFace", object())
    monkeypatch.setattr(yuz_tanima, "model_esigi", lambda: 0.68)
    return yuz_tanima.FaceRecognizer()


def test_esige_en_yakin_olan_kisi_secilir_esik_ustu_reddedilir(monkeypatch):
    """0.68 aşılmaz. İki aday da altındaysa daha yakın olan alınır; ikisi de üstündeyse ret."""
    tanici = _sahte_tanici(monkeypatch, ["Ali", "Veli"])
    tanici._embeddings = {
        "Ali": np.array([1.0, 0.0, 0.0]),
        "Veli": np.array([0.0, 1.0, 0.0]),
    }
    tanici._embed_kaynak = tanici.known_faces
    z = np.sqrt(0.15)
    # Ali'ye kosinüs 0.6 (mesafe 0.4), Veli'ye 0.7 (mesafe 0.3): ikisi de eşiğin altında
    probe = np.array([0.6, 0.7, z])
    monkeypatch.setattr(tanici, "_vektor", lambda goruntu, backend="skip": probe)
    isim, yetkili, _guven = tanici.identify(np.zeros((6, 6, 3), np.uint8))
    assert yetkili and isim == "Veli"

    # Ali 0.8, Veli 0.7: Veli daha yakın ama ikisi de 0.68'in üstünde
    probe_ret = np.array([0.2, 0.3, np.sqrt(0.87)])
    monkeypatch.setattr(tanici, "_vektor", lambda goruntu, backend="skip": probe_ret)
    isim, yetkili, _guven = tanici.identify(np.zeros((6, 6, 3), np.uint8))
    assert yetkili is False and isim == yuz_tanima.BILINMEYEN


class _SabitBulucu:
    def __init__(self, *, video=False):
        pass

    def tespit_et(self, goruntu):
        return [(10, 10, 30, 40)]

    def close(self):
        pass


class _BosBulucu(_SabitBulucu):
    def tespit_et(self, goruntu):
        return []


def test_referans_kirpma_canli_akisla_ayni_payi_kullanir(monkeypatch):
    monkeypatch.setattr(yuz_tanima, "YuzBulucu", _SabitBulucu)
    img = np.zeros((100, 120, 3), np.uint8)
    hazir, backend, uyarilar = yuz_tanima.referanslari_kirp({"Ali": img})
    assert backend["Ali"] == "skip" and uyarilar == []
    assert hazir["Ali"].shape == yuz_kirp(img, (10, 10, 30, 40), config.YUZ_KIRPMA_PAYI).shape


def test_yuz_ayrilamazsa_kisi_silinmez_opencv_yedegi_kalir(monkeypatch):
    monkeypatch.setattr(yuz_tanima, "YuzBulucu", _BosBulucu)
    img = np.full((12, 12, 3), 4, np.uint8)
    hazir, backend, uyarilar = yuz_tanima.referanslari_kirp({"Ali": img})
    assert backend["Ali"] == "opencv"
    assert np.array_equal(hazir["Ali"], img)
    assert any("Ali" in u for u in uyarilar)
