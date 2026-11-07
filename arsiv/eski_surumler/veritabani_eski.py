# ARŞİV: yeniden yapılandırma öncesi özgün dosya (çalıştırılmaz). Gizli değerler kaldırıldı.
import psycopg2
from datetime import datetime

# Veritabanı bağlantı ayarların
DB_CONFIG = {
    "host": "localhost",
    "database": "yuz_tanima",
    "user": "postgres",
    "password": "<GIZLI-KALDIRILDI>",
    "port": "5432"
}

def baglanti_getir():
    return psycopg2.connect(**DB_CONFIG)

def yetkili_giris_kaydet(isim, durum="Basarili"):
    """giris_kayitlari tablosuna veri ekler"""
    try:
        conn = baglanti_getir()
        cur = conn.cursor()
        simdi = datetime.now()
        
        sorgu = "INSERT INTO giris_kayitlari (isim, tarih, saat, durum) VALUES (%s, %s, %s, %s)"
        veriler = (isim, simdi.date(), simdi.time(), durum)
        
        cur.execute(sorgu, veriler)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Sisteme giriş kaydedildi: {isim}")
    except Exception as e:
        print(f"Veritabanı hatası (Yetkili): {e}")

def yetkisiz_giris_kaydet(foto_yolu):
    """yetkisiz_kayitlar tablosuna veri ekler"""
    try:
        conn = baglanti_getir()
        cur = conn.cursor()
        simdi = datetime.now()
        
        sorgu = "INSERT INTO yetkisiz_kayitlar (foto_yolu, tarih, saat) VALUES (%s, %s, %s)"
        veriler = (foto_yolu, simdi.date(), simdi.time())
        
        cur.execute(sorgu, veriler)
        conn.commit()
        cur.close()
        conn.close()
        print("Yetkisiz giriş denemesi kaydedildi!")
    except Exception as e:
        print(f"Veritabanı hatası (Yetkisiz): {e}")

# Test etmek istersen burayı çalıştırabilirsin
