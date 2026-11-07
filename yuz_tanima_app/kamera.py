"""Kamera thread'i: görüntü alma, yüz bulma, arka planda tanıma ve olay sinyalleri."""
import json
import logging
import os
import threading
import time
import unicodedata
from datetime import datetime

import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from . import config
from .yuz_tanima import FaceRecognizer, gorsel_yaz
from .yuz_bulucu import YuzBulucu

logger = logging.getLogger(__name__)


def ascii_cevir(metin: str) -> str:
    """cv2.putText Türkçe/aksanlı harfleri çizemez ('?' görünür); ASCII'ye çevirir."""
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = str(metin).translate(tr)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


class KameraThread(QThread):
    yeni_frame     = pyqtSignal(QImage)        # her kare → kamera_label
    yetkili_giris  = pyqtSignal(str, float)    # isim, güven
    yetkisiz_giris = pyqtSignal(str, str)      # snapshot yolu, saat metni
    hata           = pyqtSignal(str)           # kullanıcıya gösterilecek hata

    def __init__(self, camera_index=None):
        super().__init__()
        self.camera_index = config.KAMERA_INDEKSI if camera_index is None else camera_index
        self.recognizer = FaceRecognizer()
        self._stop_flag = False
        self._last_notify = {}
        self._analysis_running = False
        self._analysis_thread = None
        self._lock = threading.Lock()
        self.current_label = "Bekleniyor..."
        self.current_color_bgr = (128, 128, 128)
        self.frame_count = 0
        self._analiz_hatasi_bildirildi = False

    # ── Durdur ──────────────────────────────
    def stop(self) -> bool:
        """Thread'i güvenle durdurur. Tamamen durduysa True."""
        self._stop_flag = True
        durdu = self.wait(5000) if self.isRunning() else True
        at = self._analysis_thread
        if at is not None and at.is_alive():
            at.join(timeout=15)           # DeepFace çağrısının bitmesini bekle
            durdu = durdu and not at.is_alive()
        return durdu

    # ── Bekleme süresi ──────────────────────
    def _should_notify(self, person_id: str) -> bool:
        now = time.time()
        if now - self._last_notify.get(person_id, 0) >= config.BILDIRIM_BEKLEME_SN:
            self._last_notify[person_id] = now
            return True
        return False

    # ── Snapshot ────────────────────────────
    def _save_snapshot(self, frame, timestamp: str) -> str:
        config.SNAPSHOT_DIZINI.mkdir(parents=True, exist_ok=True)
        safe = timestamp.replace(":", "-").replace(" ", "_")
        yol = config.SNAPSHOT_DIZINI / f"BILINMEYEN_{safe}.jpg"
        if not gorsel_yaz(yol, frame):
            raise OSError(f"Snapshot yazılamadı: {yol}")
        return str(yol)

    # ── JSON log ────────────────────────────
    def _log_json(self, person: str, authorized: bool, timestamp: str):
        entry = {
            "timestamp": timestamp,
            "person": person,
            "authorized": authorized,
            "status": "authorized" if authorized else "unauthorized",
        }
        dosya = config.GUVENLIK_LOG_DOSYASI
        logs = []
        if dosya.exists():
            try:
                with open(dosya, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception as e:
                # Bozuk dosyayı ezmek yerine yedekle
                yedek = dosya.with_suffix(".bozuk.json")
                logger.error("security_log.json okunamadı (%s); %s olarak yedeklendi.", e, yedek.name)
                try:
                    os.replace(dosya, yedek)
                except OSError:
                    pass
                logs = []
        logs.append(entry)
        gecici = dosya.with_suffix(".tmp")
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        os.replace(gecici, dosya)

    # ── Arka plan analizi ───────────────────
    def _analyze_async(self, face_crop, full_frame):
        label, color_bgr = None, None
        try:
            name, authorized, confidence = self.recognizer.identify(face_crop)
            if self._stop_flag:
                return
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            saat_str = now.strftime("%H:%M:%S")

            if authorized:
                label = f"YETKILI: {ascii_cevir(name)} ({confidence:.0%})"
                color_bgr = (0, 220, 0)
                if self._should_notify(name):
                    self._log_json(name, True, timestamp)
                    self.yetkili_giris.emit(name, confidence)
            else:
                label = "BILINMEYEN KISI"
                color_bgr = (0, 0, 220)
                if self._should_notify("UNKNOWN"):
                    snap = self._save_snapshot(full_frame, timestamp)
                    self._log_json("Bilinmeyen", False, timestamp)
                    self.yetkisiz_giris.emit(snap, saat_str)
        except Exception as e:
            logger.exception("Yüz analizi başarısız")
            label, color_bgr = "ANALIZ HATASI", (0, 140, 255)
            if not self._stop_flag and not self._analiz_hatasi_bildirildi:
                self._analiz_hatasi_bildirildi = True      # her kare için pencere açma
                self.hata.emit(f"Yüz analizi sırasında hata (ayrıntı: security_system.log): {e}")
        finally:
            with self._lock:
                if label is not None:
                    self.current_label = label
                    self.current_color_bgr = color_bgr
                self._analysis_running = False

    # ── Overlay ─────────────────────────────
    def _draw_overlay(self, frame, faces):
        with self._lock:
            label = self.current_label
            color_bgr = self.current_color_bgr
            running = self._analysis_running

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color_bgr, 2)

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        cv2.putText(frame, label, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.85, color_bgr, 2)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (frame.shape[1] - 225, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        if running:
            cv2.putText(frame, "Analiz ediliyor...", (10, frame.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1)
        return frame

    # ── Ana döngü ───────────────────────────
    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        yuz_bulucu = None
        try:
            if not cap.isOpened():
                msg = f"Kamera açılamadı (indeks {self.camera_index}). Bağlantıyı ve başka bir uygulamanın kullanıp kullanmadığını kontrol edin."
                logger.error(msg)
                self.hata.emit(msg)
                return
            yuz_bulucu = YuzBulucu(video=True)
            logger.info("Kamera thread'i başlatıldı.")

            while not self._stop_flag:
                ret, frame = cap.read()
                if not ret:
                    msg = "Kamera karesi alınamadı; kamera bağlantısı kesilmiş olabilir."
                    logger.error(msg)
                    self.hata.emit(msg)
                    break

                self.frame_count += 1
                yuzler = yuz_bulucu.tespit_et(frame, self.frame_count)

                if (len(yuzler) > 0 and not self._analysis_running
                        and self.frame_count % config.KARE_ATLAMA == 0):
                    x, y, w, h = max(yuzler, key=lambda f: f[2] * f[3])
                    face_crop = frame[y:y + h, x:x + w].copy()
                    full_frame_copy = frame.copy()
                    with self._lock:
                        self._analysis_running = True
                    self._analysis_thread = threading.Thread(
                        target=self._analyze_async, args=(face_crop, full_frame_copy), daemon=True
                    )
                    self._analysis_thread.start()
                elif len(yuzler) == 0:
                    with self._lock:
                        self.current_label = "Yuz Algilanmadi"
                        self.current_color_bgr = (128, 128, 128)

                frame = self._draw_overlay(frame, yuzler)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h_px, w_px, ch = rgb.shape
                qimg = QImage(rgb.data, w_px, h_px, ch * w_px, QImage.Format_RGB888)
                self.yeni_frame.emit(qimg.copy())
                self.msleep(33)               # ~30 FPS üst sınır
        except Exception as e:
            logger.exception("Kamera döngüsü beklenmedik şekilde durdu")
            self.hata.emit(f"Kamera beklenmedik şekilde durdu: {e}")
        finally:
            if yuz_bulucu is not None:
                yuz_bulucu.close()
            cap.release()
            logger.info("Kamera thread'i durduruldu.")
