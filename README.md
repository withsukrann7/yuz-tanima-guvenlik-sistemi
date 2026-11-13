# Kamera Tabanlı Yüz Tanıma ve Güvenlik Sistemi

Zonguldak Bülent Ecevit Üniversitesi için geliştirilen bu masaüstü prototipi, güvenlik kameralarının izlediği alanlarda kişileri pasif olarak tespit eder. OpenCV ve MediaPipe yüz algılar; DeepFace, görüntüyü kayıtlı yetkili yüzlerle karşılaştırır. Sonuçlar PostgreSQL'e kaydedilir ve uygulama arayüzünde gösterilir.

Bu yazılım bir kapı kilidi veya geçiş kontrol cihazı değildir. Kamera görüntüsünü izler, şüpheli durumlarda uyarı verir ve olay geçmişi tutar. Sesli alarm üretmez.

## Özellikler

- PyQt5 masaüstü arayüzü: Genel Bakış, Yüz Kaydı, Kullanıcı Listesi, Canlı Kamera İzleme ve Giriş/Çıkış Kayıtları.
- MediaPipe ile kamera karelerinde ve kayıt fotoğraflarında yüz algılama.
- DeepFace VGG-Face ile yetkili yüz eşleştirme; bilinmeyen kişi tespitinde uyarı ve görüntü kaydı.
- Kamera görüntüsünün örtülmesi, kararması, donması veya kameradan kare alınamaması için pasif kamera sağlığı izlemesi.
- Genel Bakış'ta kamera kesintisi bildirimi ve günlük kesinti geçmişi. Başlangıç, bitiş ve toplam süre mevcut kamera olay kayıtlarından hesaplanır. Kamera elle durdurulursa açık kesintiler durdurma anında kapatılır.
- PostgreSQL erişim kayıtları ve Excel'e aktarma.

## Gereksinimler

- Python 3.10–3.12
- PostgreSQL
- Kamera ile canlı izleme için erişilebilir bir kamera
- İlk DeepFace tanımasında VGG-Face ağırlıklarının indirilmesi için internet bağlantısı

Python paketleri `requirements.txt` içinde listelenmiştir. Projede MediaPipe'ın BlazeFace modeli `models/blaze_face_short_range.tflite` yolunda bulunur.

## Kurulum

Komutlar Windows PowerShell içindir. Linux/macOS için sanal ortamı etkinleştirme ve dosya kopyalama komutları parantez içinde verilmiştir.

1. Projeyi indirin veya klonlayın ve proje klasörüne geçin.

2. Sanal ortam oluşturup bağımlılıkları yükleyin:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Linux/macOS etkinleştirme komutu: `source .venv/bin/activate`.

3. PostgreSQL'de `yuz_tanima` adlı veritabanı oluşturun:

   ```powershell
   createdb -U postgres yuz_tanima
   ```

   `createdb` komutu bulunamazsa PostgreSQL'in `psql` aracından `CREATE DATABASE yuz_tanima;` çalıştırın.

4. Ortam ayarlarını oluşturun ve düzenleyin:

   ```powershell
   Copy-Item .env.example .env
   ```

   Linux/macOS: `cp .env.example .env`. `.env` içindeki PostgreSQL parolasını ve yönetici giriş bilgilerini kendi ortamınıza göre değiştirin. `.env` dosyasını Git'e eklemeyin.

5. Tabloları hazırlayıp bağlantıyı doğrulayın:

   ```powershell
   python -m yuz_tanima_app.veritabani kur
   python -m yuz_tanima_app.veritabani test
   ```

6. Uygulamayı başlatın:

   ```powershell
   python main.py
   ```

Uygulama yolları çalışma klasörüne değil, proje köküne göre çözer; `main.py` dosyasını proje kökünden başlatın.

## Yapılandırma

Uygulama proje kökündeki `.env` dosyasını veya işletim sistemi ortam değişkenlerini kullanır.

| Değişken | Açıklama | Varsayılan |
| --- | --- | --- |
| `YUZ_DB_HOST` | PostgreSQL sunucusu | `localhost` |
| `YUZ_DB_PORT` | PostgreSQL portu | `5432` |
| `YUZ_DB_NAME` | Veritabanı adı | `yuz_tanima` |
| `YUZ_DB_USER` | PostgreSQL kullanıcısı | `postgres` |
| `YUZ_DB_PASSWORD` | PostgreSQL parolası | Tanımsız |
| `YUZ_DB_TIMEOUT` | Bağlantı zaman aşımı (saniye) | `5` |
| `YUZ_ADMIN_USER` | Demo arayüz yöneticisi | Tanımsız |
| `YUZ_ADMIN_PASSWORD` | Demo arayüz parolası | Tanımsız |
| `YUZ_KAMERA_INDEKSI` | OpenCV kamera indeksi | `0` |

Yönetici hesabı `.env.example` içinde yalnızca örnek değerlerle gelir. Kendi değerlerinizi belirleyin. Bu tek hesaplı giriş mekanizması deneme sınırı veya parola hash'i sağlamaz; üretim kimlik doğrulaması olarak kullanılmamalıdır.

## Kullanım akışı

1. Giriş penceresi, `YUZ_ADMIN_USER` ve `YUZ_ADMIN_PASSWORD` değerlerini doğrular.
2. Yüz Kaydı sayfasından yetkili kişi ve fotoğraf eklenir. Fotoğraf `yuzler/` klasörüne alınır; kullanıcı bilgileri `yetkili_kisiler` tablosunda tutulur.
3. Canlı Kamera İzleme başlatıldığında kamera kareleri MediaPipe ile taranır. Yüz eşleştirmesi, arka plan iş parçacığında DeepFace ile yapılır.
4. Yetkili eşleşmeleri giriş kayıtlarına yazılır. Bilinmeyen kişi için kare görüntüsü `snapshots/` altına kaydedilir; olay `yetkisiz_kayitlar` tablosuna ve `security_log.json` dosyasına eklenir.
5. Genel Bakış ve Giriş/Çıkış Kayıtları, veritabanındaki kişi ve kamera olaylarını gösterir. Geçmiş kayıtları Excel'e aktarılabilir.

Tanıma tekrar bildirim aralığı `BILDIRIM_BEKLEME_SN` ile belirlenir. Yüz kararında tek karelik eşleşmeye dayanılmaz; `KARAR_MIN_ORNEK` art arda örnek kullanılır. Diğer kamera ve tanıma eşikleri `yuz_tanima_app/config.py` içindedir.

## Kamera kesintisi takibi

Kamera sağlığı izlemesi, kareleri küçülterek analiz eder; ham kamera görüntülerini kamera olayı kaydı olarak saklamaz.

- Görüntü önceki sahneye göre belirgin biçimde değişip uzun süre düşük ayrıntılı kalırsa örtülme şüphesi oluşturur. Varsayılan eşik 2,5 saniyedir.
- Neredeyse siyah veya değişmeyen kareler 8 saniye sürerse ayrı olay oluşturur.
- Kameradan kare okunamazsa erişim kesintisi olayı başlatılır; görüntü geri geldiğinde kapatılır.
- Her olayın aktif ve çözüldü geçişleri mevcut `giris_kayitlari` tablosuna yazılır. Yeni tablo veya şema değişikliği gerekmez. Kamera durum kodları `VARCHAR(20)` ile uyumlu ve `CAMERA_` önekini korur.
- Genel Bakış bu geçişleri eşleştirip başlangıç, bitiş ve süreyi gösterir. Operatör kamerayı durdurduğunda açık olaylar o anda kapatılır; elle durdurma sonrası süre artmaya devam etmez.

Bu kontroller kamera görüntüsündeki şüpheli değişimleri gösterir; kasıtlı müdahalenin kesin kanıtı değildir. Sistem pasif izleme yapar, canlılık (liveness) veya göz kırpma zorunluluğu içermez.

## Veriler ve günlükler

| Konum | İçerik |
| --- | --- |
| `veritabani/schema.sql` | PostgreSQL tablo tanımları |
| `known_faces/`, `yuzler/` | Yetkili kişilerin yerel yüz fotoğrafları |
| `snapshots/` | Bilinmeyen kişi tespitlerinde alınan görüntüler |
| `security_log.json` | Yerel tanıma olay günlüğü |
| `security_system.log` | Uygulama, kamera, veritabanı ve hata günlükleri |
| `arsiv/silinen_yuzler/` | Silinen kullanıcıların arşivlenen yüz dosyaları |

Yüz görüntüleri, `.env` ve günlük dosyaları hassas veri içerir. Bunlar depoya eklenmemelidir; kişisel veri saklama ve silme politikalarını uygulama ortamınıza göre belirleyin. `schema.sql` mevcut tabloları `CREATE TABLE IF NOT EXISTS` ile oluşturur; var olan tabloları otomatik olarak dönüştürmez.

## Proje yapısı

```text
main.py                         Uygulama başlangıcı ve günlükleme
yuz_tanima_app/
  giris.py                      Yönetici giriş penceresi
  dashboard.py                  Uygulama sayfaları ve kullanıcı etkileşimi
  kamera.py                     Kamera iş parçacığı ve tanıma akışı
  camera_health.py              Kamera karelerindeki anormalliklerin tespiti
  yuz_bulucu.py                 MediaPipe yüz algılama
  yuz_tanima.py                 DeepFace eşleştirme ve yüz kaynağı yönetimi
  veritabani.py                 PostgreSQL erişimi ve kamera olayları
  config.py                     Ortam ayarları, dosya yolları ve eşikler
  arayuz_ortak.py                Ortak renkler ve arayüz bileşenleri
models/                         MediaPipe BlazeFace modeli
ui/login.ui                     Qt Designer giriş arayüzü
veritabani/schema.sql           Veritabanı şeması
tests/                          Otomatik testler
arsiv/                          Kullanılmayan eski sürümler
```

## Testler

Temel test bağımlılıklarını yükleyin ve proje kökünde çalıştırın:

```powershell
pip install -r requirements-dev.txt
pytest
```

PostgreSQL entegrasyon testleri yalnızca `YUZ_TEST_DB_NAME` tanımlandığında çalışır. Testler bu veritabanındaki tabloları silip yeniden oluşturur. **Üretim veya kişisel veritabanınız için bu değişkeni tanımlamayın; yalnızca ayrılmış bir test veritabanı kullanın.** DeepFace uçtan uca testi ayrıca `YUZ_TEST_DEEPFACE=1` ile isteğe bağlı olarak etkinleştirilir ve model ağırlıklarını indirebilir.

## Sınırlamalar

- Prototip belirli kamera, ışık, mesafe ve ortam koşullarında ayrıca değerlendirilmelidir.
- Yüz tanıma hatasız kimlik doğrulaması veya canlı kişi garantisi vermez; fotoğraf/maske saldırılarına karşı liveness kontrolü yoktur.
- Demo yönetici girişi üretim güvenliği sağlamaz.
- Biyometrik dosyalar uygulama tarafından şifrelenmez. Depolama erişimini ve yedekleri koruyun.
- Kayıtlı yüz sayısı arttıkça tanıma süresi uzayabilir.
