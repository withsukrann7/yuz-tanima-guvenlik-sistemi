-- Yüz Tanıma Güvenlik Sistemi — veritabanı şeması
--
-- DİKKAT: Orijinal projede şema dosyası yoktu. Aşağıdaki tablolar ve sütunlar,
-- kodun kullandığı SQL sorgularından ÇIKARILMIŞTIR. Mevcut bir veritabanınız
-- varsa `CREATE TABLE IF NOT EXISTS` onu değiştirmez.
--
-- Önce veritabanını oluşturun:   createdb -U postgres yuz_tanima
-- Sonra tabloları kurun:         python -m yuz_tanima_app.veritabani kur

CREATE TABLE IF NOT EXISTS yetkili_kisiler (
    id          SERIAL PRIMARY KEY,
    isim        VARCHAR(150) NOT NULL,
    departman   VARCHAR(100),
    telefon     VARCHAR(50),
    calisan_id  VARCHAR(50),
    eposta      VARCHAR(150),
    foto_yolu   TEXT,
    durum       VARCHAR(20) NOT NULL DEFAULT 'Aktif'
);

CREATE TABLE IF NOT EXISTS giris_kayitlari (
    id      SERIAL PRIMARY KEY,
    isim    VARCHAR(150) NOT NULL,
    tarih   DATE NOT NULL DEFAULT CURRENT_DATE,
    saat    TIME NOT NULL DEFAULT CURRENT_TIME,
    durum   VARCHAR(30) NOT NULL DEFAULT 'Basarili'
);

CREATE TABLE IF NOT EXISTS yetkisiz_kayitlar (
    id        SERIAL PRIMARY KEY,
    foto_yolu TEXT,
    tarih     DATE NOT NULL DEFAULT CURRENT_DATE,
    saat      TIME NOT NULL DEFAULT CURRENT_TIME
);

CREATE INDEX IF NOT EXISTS idx_giris_tarih    ON giris_kayitlari (tarih);
CREATE INDEX IF NOT EXISTS idx_yetkisiz_tarih ON yetkisiz_kayitlar (tarih);
