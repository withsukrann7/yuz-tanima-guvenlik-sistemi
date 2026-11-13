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

from . import config, veritabani
from .camera_health import CameraHealthMonitor
from .yuz_tanima import FaceRecognizer, gorsel_yaz
from .yuz_bulucu import YuzBulucu, yuz_kirp

logger = logging.getLogger(__name__)


def ascii_cevir(metin: str) -> str:
    """cv2.putText Türkçe/aksanlı harfleri çizemez ('?' görünür); ASCII'ye çevirir."""
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = str(metin).translate(tr)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def erisim_karari(son_sonuclar, min_ornek):
    """Tek karelik tanıma sonucundan kapı veya alarm üretmez.

    son_sonuclar: en yeni sonda, (yetkili mi, isim veya None).
    Yetkili: son `min_ornek` örnek art arda aynı kişi ve hepsi eşiğin altında.
    Yetkisiz: son `min_ornek` örnek art arda ret.
    Karışık sonuç beklemede kalır; bu, eşiği düşürmeden yanlış alarmı keser
    ve tek tesadüfi eşleşmenin içeri almasını da engeller.
    """
    if min_ornek < 1:
        raise ValueError("min_ornek en az 1 olmalıdır")
    if len(son_sonuclar) < min_ornek:
        return "bekliyor", None
    pencere = son_sonuclar[-min_ornek:]
    if all(ok for ok, _isim in pencere):
        isimler = [isim for _ok, isim in pencere]
        if isimler[0] and all(isim == isimler[0] for isim in isimler):
            return "yetkili", isimler[0]
        return "bekliyor", None
    if all(not ok for ok, _isim in pencere):
        return "yetkisiz", None
    return "bekliyor", None


class KameraThread(QThread):
    yeni_frame     = pyqtSignal(QImage)        # her kare → kamera_label
    yetkili_giris  = pyqtSignal(str, float)    # isim, güven
    yetkisiz_giris = pyqtSignal(str, str)      # snapshot yolu, saat metni
    hata           = pyqtSignal(str)           # kullanıcıya gösterilecek hata
    camera_event_changed = pyqtSignal(str, str, bool)  # camera, event type, active

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
        self._oylar = []
        self._yuzsuz_kare = 0
        self._video_t0 = None
        self._son_video_ms = 0

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

    def _camera_health_transitions(self, transitions):
        camera_name = f"Kamera {self.camera_index + 1}"
        descriptions = {
            "blocked": "Kamera görüntüsü engellenmiş olabilir",
            "occluded": "Kamera görüntüsü kapatılmış olabilir",
            "frozen": "Kamera görüntüsü donmuş olabilir",
            "read_failure": "Kamera açılamadı veya görüntü karesi alınamadı",
        }
        for event_type, active in transitions:
            self.camera_event_changed.emit(camera_name, event_type, bool(active))
            if active and self._should_notify(f"camera:{event_type}"):
                self.hata.emit(f"Şüpheli kamera durumu: {descriptions[event_type]}.")
            try:
                veritabani.enqueue_camera_event_transition(camera_name, event_type, active)
            except Exception:
                logger.exception(
                    "Kamera olayı veritabanına yazılamadı: camera=%s type=%s active=%s",
                    camera_name, event_type, active,
                )

    def _video_ms(self) -> int:
        """MediaPipe video modu milisaniye ister; kare numarası zaman değildir."""
        simdi = time.monotonic()
        if self._video_t0 is None:
            self._video_t0 = simdi
            self._son_video_ms = 0
        ms = int((simdi - self._video_t0) * 1000)
        if ms <= self._son_video_ms:
            ms = self._son_video_ms + 1
        self._son_video_ms = ms
        return ms

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
            with self._lock:
                self._oylar.append((bool(authorized), name if authorized else None))
                fazla = len(self._oylar) - config.KARAR_MIN_ORNEK
                if fazla > 0:
                    del self._oylar[:fazla]
                karar, karar_isim = erisim_karari(list(self._oylar), config.KARAR_MIN_ORNEK)
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            saat_str = now.strftime("%H:%M:%S")

            if karar == "yetkili":
                label = f"YETKILI: {ascii_cevir(karar_isim)} ({confidence:.0%})"
                color_bgr = (0, 220, 0)
                if self._should_notify(karar_isim):
                    self._log_json(karar_isim, True, timestamp)
                    self.yetkili_giris.emit(karar_isim, confidence)
            elif karar == "yetkisiz":
                label = "BILINMEYEN KISI"
                color_bgr = (0, 0, 220)
                if self._should_notify("UNKNOWN"):
                    snap = self._save_snapshot(full_frame, timestamp)
                    self._log_json("Bilinmeyen", False, timestamp)
                    self.yetkisiz_giris.emit(snap, saat_str)
            else:
                label = "Dogrulaniyor..."
                color_bgr = (0, 180, 255)
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
        health_monitor = CameraHealthMonitor()
        try:
            if not cap.isOpened():
                msg = f"Kamera açılamadı (indeks {self.camera_index}). Bağlantıyı ve başka bir uygulamanın kullanıp kullanmadığını kontrol edin."
                logger.error(msg)
                self._camera_health_transitions(health_monitor.frame_unavailable())
                return
            yuz_bulucu = YuzBulucu(video=True)
            logger.info("Kamera thread'i başlatıldı.")

            while not self._stop_flag:
                ret, frame = cap.read()
                if not ret or frame is None or frame.size == 0:
                    msg = "Kamera karesi alınamadı; kamera bağlantısı kesilmiş olabilir."
                    logger.error(msg)
                    if not self._stop_flag:
                        self._camera_health_transitions(health_monitor.frame_unavailable())
                    break

                self._camera_health_transitions(health_monitor.frame_recovered())
                self._camera_health_transitions(health_monitor.observe(frame))
                self.frame_count += 1
                yuzler = yuz_bulucu.tespit_et(frame, self._video_ms())

                if len(yuzler) == 0:
                    self._yuzsuz_kare += 1
                    with self._lock:
                        self.current_label = "Yuz Algilanmadi"
                        self.current_color_bgr = (128, 128, 128)
                        if self._yuzsuz_kare >= config.YUZSUZ_SIFIRLAMA_KARE:
                            self._oylar.clear()
                else:
                    self._yuzsuz_kare = 0
                    if (not self._analysis_running
                            and self.frame_count % config.KARE_ATLAMA == 0):
                        x, y, w, h = max(yuzler, key=lambda f: f[2] * f[3])
                        if min(w, h) < config.MIN_YUZ_KENARI:
                            with self._lock:
                                self.current_label = "Yuz cok kucuk - yaklasin"
                                self.current_color_bgr = (0, 180, 255)
                        else:
                            face_crop = yuz_kirp(frame, (x, y, w, h), config.YUZ_KIRPMA_PAYI)
                            if face_crop is not None:
                                full_frame_copy = frame.copy()
                                with self._lock:
                                    self._analysis_running = True
                                self._analysis_thread = threading.Thread(
                                    target=self._analyze_async,
                                    args=(face_crop, full_frame_copy),
                                    daemon=True,
                                )
                                self._analysis_thread.start()

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
