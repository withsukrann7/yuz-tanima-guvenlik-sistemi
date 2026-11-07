# Arşiv

Yeniden düzenleme öncesindeki özgün dosyalar. Silinmedi; yalnızca başvuru için saklanıyor. **Çalıştırılmaz** (import yolları ve yapılandırma artık farklı). Özgün dosyalardaki veritabanı parolaları ve demo giriş parolası `<GIZLI-KALDIRILDI>` ile değiştirildi.

| Dosya | Neden arşivlendi | Yerine geçen |
|---|---|---|
| `eski_surumler/dashboard_integrated_orijinal.py` | Gerçek ana uygulamaydı; 1200 satırlık tek dosya | `yuz_tanima_app/` paketi |
| `eski_surumler/dashboard_eski_kamerasiz.py` | Kamera entegrasyonu olmayan önceki arayüz sürümü; `main.py` kullanmıyordu | `yuz_tanima_app/dashboard.py` |
| `eski_surumler/main_orijinal.py` | Sabit kullanıcı/parola, ölü kod (`_ekran_goruntusu`) | `main.py`, `yuz_tanima_app/giris.py` |
| `eski_surumler/FaceAnalysis_bagimsiz_prototip.py` | Arayüzsüz, OpenCV penceresiyle çalışan ilk prototip; hiçbir yerden import edilmiyordu | `yuz_tanima_app/yuz_tanima.py` + `kamera.py` |
| `eski_surumler/veritabani_eski.py` | Hiçbir yerden import edilmiyordu | `yuz_tanima_app/veritabani.py` |
