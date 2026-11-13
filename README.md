# Görüntü İşleme ile Yüz Tanıma ve Güvenlik Sistemi

![Python](https://img.shields.io/badge/Python-3.10--3.12-blue?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![DeepFace](https://img.shields.io/badge/AI-DeepFace-green?style=for-the-badge)
![PyQt5](https://img.shields.io/badge/Desktop-PyQt5-orange?style=for-the-badge)

🎓 **Zonguldak Bülent Ecevit Üniversitesi** (akademik amaçlı prototip)

Gerçek zamanlı kamera görüntüsünde yüz algılar (OpenCV), DeepFace (VGG-Face) ile kayıtlı yetkili kişilerle karşılaştırır, sonucu PostgreSQL'e yazar ve yetkisiz kişi tespitinde masaüstü arayüzünde uyarı penceresi gösterir (sesli alarm yoktur).

## Hızlı başlangıç

```bash
# 1) Ortam (Python 3.10 – 3.12)
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 2) PostgreSQL: veritabanını oluşturun (PostgreSQL kurulu ve çalışıyor olmalı)
createdb -U postgres yuz_tanima

# 3) Yapılandırma: örneği kopyalayıp doldurun (DB parolası, yönetici girişi)
copy .env.example .env            # Linux/macOS: cp .env.example .env

# 4) Tabloları kurun ve bağlantıyı deneyin
python -m yuz_tanima_app.veritabani kur
python -m yuz_tanima_app.veritabani test

# 5) Uygulamayı başlatın (herhangi bir klasörden çalışır)
python main.py
```

İlk kamera analizinde DeepFace VGG-Face ağırlıklarını (~580 MB) internetten indirir; bu bir kez olur.
MediaPipe'ın BlazeFace kısa mesafe modeli `models/blaze_face_short_range.tflite` olarak depoya eklenmiştir.

### Proje kökünde bulunması gereken dosyalar
Depoda bulunmayan (veya `.gitignore` ile dışarıda tutulan) şu öğeleri proje köküne koyun:

| Öğe | Zorunlu mu? |
|---|---|
| `ui/login.ui` (nesne adları: `logoLabel`, `backgroundLabel`, `loginFrame`, `loginButton`, `usernamenput`, `passwordInput`) | **Evet** — yoksa açık bir hata mesajı verilir |
| `logo.png`, `login_bg.png` | Hayır — yoksa uyarı loglanır, pencere görselsiz açılır |
| `known_faces/`, `yuzler/` | Hayır — mevcut yüz fotoğraflarınız; aşağıya bakın |
| `main_window.ui` | Hiçbir kod kullanmıyor; yalnızca saklanıyor |

> `usernamenput` bir yazım hatası gibi görünür ama `login.ui` içindeki gerçek nesne adıdır; kodda bilerek aynen bırakılmıştır.

## Yapılandırma (`.env`)

| Değişken | Anlamı |
|---|---|
| `YUZ_DB_HOST`, `YUZ_DB_PORT`, `YUZ_DB_NAME`, `YUZ_DB_USER`, `YUZ_DB_PASSWORD` | PostgreSQL bağlantısı |
| `YUZ_ADMIN_USER`, `YUZ_ADMIN_PASSWORD` | Giriş ekranı kullanıcısı. **Varsayılan yoktur**; tanımlı değilse giriş yapılamaz ve neden belirtilir |
| `YUZ_KAMERA_INDEKSI` | Kamera numarası (varsayılan 0) |

## Klasör yapısı

```
.
├── main.py                      # tek başlatma noktası
├── yuz_tanima_app/
│   ├── config.py                # yollar, ortam değişkenleri, sabitler
│   ├── veritabani.py            # PostgreSQL katmanı (hataları yutmaz)
│   ├── yuz_tanima.py            # yetkili yüzlerin yüklenmesi + DeepFace doğrulama
│   ├── kamera.py                # kamera thread'i, algılama, olay sinyalleri
│   ├── giris.py                 # giriş penceresi (ui/login.ui)
│   ├── dashboard.py             # ana pencere ve 5 sayfa
│   └── arayuz_ortak.py          # renkler, widget yardımcıları, diyaloglar
├── models/blaze_face_short_range.tflite # MediaPipe yüz algılama modeli
├── veritabani/schema.sql        # tablolar (kodun sorgularından çıkarıldı)
├── tests/                       # pytest
├── arsiv/                       # eski sürümler (çalıştırılmaz) — arsiv/README.md
├── ui/, logo.png, login_bg.png  # (sizin dosyalarınız)
├── known_faces/, yuzler/        # yetkili yüz fotoğrafları (git'e girmez)
├── snapshots/                   # bilinmeyen kişi görüntüleri (git'e girmez)
├── .env.example  requirements.txt  requirements-dev.txt  pytest.ini
```

## Nasıl çalışır

1. **Giriş** → `ui/login.ui`; bilgiler `.env`'den doğrulanır.
2. **Yüz Kaydı** → fotoğraf `yuzler/` altına kopyalanır, kişi `yetkili_kisiler` tablosuna eklenir.
3. **Canlı İzleme** → kamera thread'i MediaPipe Face Detector ile karelerde yüz bulur; her `KARE_ATLAMA` karede bir, arka plan thread'inde DeepFace ile tüm yetkili yüzlerle karşılaştırır.
4. **Sonuç** → yetkili: `giris_kayitlari` + `security_log.json`; yetkisiz: `snapshots/` görüntüsü + `yetkisiz_kayitlar` + uyarı penceresi. Aynı kişi için kayıt/bildirim `BILDIRIM_BEKLEME_SN` (10 sn) aralıklıdır.
5. **Yetkili listesi** = veritabanındaki **Aktif** kullanıcılar + (veritabanında karşılığı olmayan) eski `known_faces/` dosyaları. Pasif/silinmiş kullanıcılar tanınmaz. Kullanıcı silindiğinde fotoğrafları **silinmez**, `arsiv/silinen_yuzler/` altına taşınır.

### Canlılık kontrolü

Kamera akışı, yüz tanımadan önce MediaPipe Face Landmarker ile göz kırpma kontrolü yapar. Ekranda `Goz kirpin` yönlendirmesi görünür; gözlerin açık olduğu, kapandığı ve yeniden açıldığı kare dizisi algılanınca mevcut DeepFace tanıma akışı başlar. Yüz kaybolursa kontrol sıfırlanır. Model dosyası `models/face_landmarker.task` olarak depoda bulunmalıdır; yeni Python paketi gerekmez. Bu temel kontrol fotoğraf gösterimini zorlaştırır, ancak video tekrarına veya gelişmiş sahteciliğe karşı güvence sağlamaz.

## Veritabanı yokken davranış

Açılışta bağlantı ve tablolar denetlenir. Sorun varsa açıklayıcı bir uyarı gösterilir, sol menüde kalıcı **"⚠ Veritabanı bağlantısı yok"** etiketi çıkar (üzerine gelince ayrıntı) ve uygulama sınırlı modda sürer: kamera/tanıma çalışır, olay logu `security_log.json`'a yazılır, ama veritabanı kayıtları yazılamaz ve kullanıcı listesi/kaydı çalışmaz. Hatalar `security_system.log`'a yazılır; başarılı gibi gösterilmez.

## Testler

```bash
pip install -r requirements-dev.txt
pytest                                           # PostgreSQL/kamera gerektirmeyen testler
# Gerçek PostgreSQL ile (ASIL veritabanınızı kullanmayın; tablolar silinip yeniden yaratılır):
set YUZ_TEST_DB_NAME=yuz_tanima_test             # + isteğe bağlı YUZ_TEST_DB_HOST/PORT/USER/PASSWORD
pytest
# DeepFace ile uçtan uca (ağırlıkları indirir, scikit-image gerekir):
set YUZ_TEST_DEEPFACE=1 & pytest tests/test_deepface_opsiyonel.py
```

## Bilinen sınırlamalar

- Giriş doğrulaması **demo** niteliğindedir (tek hesap, düz metin parola, deneme sınırı yok); üretim güvenliği sağlamaz.
- Yüz tanıma canlı fotoğraf/maske saldırılarına (liveness) karşı korumasızdır; biyometrik veriler diskte şifrelenmeden saklanır.
- Her analizde tüm yetkili yüzlerle tek tek karşılaştırma yapılır; kayıt sayısı arttıkça yavaşlar.
- Arayüzdeki "Kayıt Başlat", "Düzenle", geçmiş tablosundaki 👁/🎬/📄 düğmeleri ve "Güven" sütunu orijinalde de uygulanmamıştı; olduğu gibi bırakıldı.
- Kullanıcı silme `isim + çalışan ID` ile yapılır (şemada benzersiz anahtar yoktu).
- MediaPipe yüz algılaması farklı kamera, mesafe ve ışık koşullarında ayrıca ölçülmelidir; yüz algılama, kimlik eşleştirme doğruluğunu tek başına garanti etmez.


