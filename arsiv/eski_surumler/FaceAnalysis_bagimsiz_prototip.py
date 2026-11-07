# ARŞİV: yeniden yapılandırma öncesi özgün dosya (çalıştırılmaz). Gizli değerler kaldırıldı.
"""
Güvenlik Sistemi - Yüz Tanıma Modülü
DeepFace + OpenCV kullanarak yetkili/yetkisiz kişi tespiti
"""

import cv2
import os
import time
import json
import logging
import threading
from datetime import datetime
from deepface import DeepFace

# ──────────────────────────────────────────────
# AYARLAR
# ──────────────────────────────────────────────
KNOWN_FACES_DIR       = "known_faces"       # Yetkili kişi fotoğrafları
LOG_FILE              = "security_log.json" # Kayıt dosyası
NOTIFICATION_COOLDOWN = 10                  # Aynı kişi için bildirim aralığı (saniye)
MODEL_NAME            = "VGG-Face"          # DeepFace modeli
DISTANCE_METRIC       = "cosine"            # Benzerlik metriği
DETECTOR_BACKEND      = "opencv"            # Yüz dedektörü
FRAME_SKIP            = 20                  # Her N karede bir analiz (↑ = daha az kasma)

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("security_system.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# BİLDİRİM SİSTEMİ
# ──────────────────────────────────────────────
class NotificationManager:
    def __init__(self):
        self.last_notifications = {}

    def should_notify(self, person_id: str) -> bool:
        now = time.time()
        last = self.last_notifications.get(person_id, 0)
        if now - last >= NOTIFICATION_COOLDOWN:
            self.last_notifications[person_id] = now
            return True
        return False

    def send(self, person_name: str, is_authorized: bool, frame=None):
        if not self.should_notify(person_name):
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "YETKİLİ GİRİŞ ✅" if is_authorized else "YETKİSİZ GİRİŞ ⚠️  BİLİNMEYEN KİŞİ"

        border = "=" * 50
        print(f"\n{border}")
        print(f"  {status}")
        print(f"  Kişi   : {person_name}")
        print(f"  Zaman  : {timestamp}")
        print(f"{border}\n")

        self._log_to_file(person_name, is_authorized, timestamp)

        # Sadece bilinmeyen kişilerde snapshot al
        if not is_authorized and frame is not None:
            self._save_snapshot(frame, timestamp)

    def _log_to_file(self, person_name: str, is_authorized: bool, timestamp: str):
        entry = {
            "timestamp": timestamp,
            "person": person_name,
            "authorized": is_authorized,
            "status": "authorized" if is_authorized else "unauthorized"
        }
        logs = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        logs.append(entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    def _save_snapshot(self, frame, timestamp: str):
        os.makedirs("snapshots", exist_ok=True)
        safe_time = timestamp.replace(":", "-").replace(" ", "_")
        filename = f"snapshots/BILINMEYEN_{safe_time}.jpg"
        cv2.imwrite(filename, frame)
        logger.info(f"⚠️  Bilinmeyen kişi snapshot kaydedildi: {filename}")


# ──────────────────────────────────────────────
# YÜZ TANIMA
# ──────────────────────────────────────────────
class FaceRecognizer:
    def __init__(self):
        self.known_faces = self._load_known_faces()
        logger.info(f"{len(self.known_faces)} yetkili kişi yüklendi: {list(self.known_faces.keys())}")

    def _load_known_faces(self) -> dict:
        faces = {}
        if not os.path.exists(KNOWN_FACES_DIR):
            os.makedirs(KNOWN_FACES_DIR)
            logger.warning(f"'{KNOWN_FACES_DIR}' klasörü oluşturuldu. Fotoğrafları ekleyin.")
            return faces

        for filename in os.listdir(KNOWN_FACES_DIR):
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                name = os.path.splitext(filename)[0].replace("_", " ").title()
                path = os.path.join(KNOWN_FACES_DIR, filename)
                faces[name] = path
                logger.info(f"Yüklendi: {name} ({path})")
        return faces

    def identify(self, frame) -> tuple[str, bool, float]:
        if not self.known_faces:
            return "Bilinmeyen Kisi", False, 0.0

        temp_path = f"temp_frame_{threading.get_ident()}.jpg"
        cv2.imwrite(temp_path, frame)

        best_match = None
        best_distance = float("inf")
        is_verified = False

        for name, face_path in self.known_faces.items():
            try:
                result = DeepFace.verify(
                    img1_path=temp_path,
                    img2_path=face_path,
                    model_name=MODEL_NAME,
                    distance_metric=DISTANCE_METRIC,
                    detector_backend=DETECTOR_BACKEND,
                    enforce_detection=False
                )
                distance = result.get("distance", 1.0)
                if distance < best_distance:
                    best_distance = distance
                    best_match = name
                    is_verified = result.get("verified", False)
            except Exception as e:
                logger.debug(f"{name} karşılaştırma hatası: {e}")
                continue

        if os.path.exists(temp_path):
            os.remove(temp_path)

        if best_match and is_verified:
            return best_match, True, max(0.0, 1.0 - best_distance)
        return "Bilinmeyen Kisi", False, 0.0


# ──────────────────────────────────────────────
# ANA KAMERA DÖNGÜSÜ
# ──────────────────────────────────────────────
class SecurityCamera:
    def __init__(self, camera_index: int = 0):
        self.cap = cv2.VideoCapture(camera_index)
        self.recognizer = FaceRecognizer()
        self.notifier = NotificationManager()
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Durum değişkenleri (ana thread ile analiz thread'i paylaşır)
        self.current_label = "Bekleniyor..."
        self.current_color = (128, 128, 128)
        self.frame_count = 0

        # Thread kontrolü
        self._analysis_running = False   # Şu an analiz yapılıyor mu?
        self._lock = threading.Lock()    # Durum güncellemesi için kilit
        self._last_frame_for_analysis = None

        if not self.cap.isOpened():
            raise RuntimeError("Kamera açılamadı!")
        logger.info("Kamera başlatıldı. Çıkmak için 'q' tuşuna bas.")

    # ── Arka plan analiz thread'i ──────────────
    def _analyze_async(self, face_crop, full_frame):
        """DeepFace analizini ayrı thread'de çalıştırır → kamera donmaz."""
        name, authorized, confidence = self.recognizer.identify(face_crop)

        if authorized:
            label = f"YETKILI: {name} ({confidence:.0%})"
            color = (0, 220, 0)
        else:
            label = "BILINMEYEN KISI"
            color = (0, 0, 220)

        with self._lock:
            self.current_label = label
            self.current_color = color
            self._analysis_running = False   # Analiz bitti, yeni analiz alınabilir

        self.notifier.send(name, authorized, full_frame)

    # ── Overlay çizimi ─────────────────────────
    def _draw_overlay(self, frame, faces):
        with self._lock:
            label = self.current_label
            color = self.current_color

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Üst şeffaf bant
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        cv2.putText(frame, label, (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (frame.shape[1] - 225, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Analiz devam ediyor göstergesi
        with self._lock:
            running = self._analysis_running
        if running:
            cv2.putText(frame, "Analiz ediliyor...", (10, frame.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1)
        return frame

    # ── Ana döngü ──────────────────────────────
    def run(self):
        logger.info("Güvenlik sistemi aktif.")
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("Kamera karesi alınamadı.")
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                )

                self.frame_count += 1

                # Yüz varsa ve analiz meşgul değilse ve frame_skip dolmuşsa → yeni analiz başlat
                if (len(faces) > 0
                        and not self._analysis_running
                        and self.frame_count % FRAME_SKIP == 0):

                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    face_crop = frame[y:y+h, x:x+w].copy()
                    full_frame_copy = frame.copy()

                    with self._lock:
                        self._analysis_running = True

                    t = threading.Thread(
                        target=self._analyze_async,
                        args=(face_crop, full_frame_copy),
                        daemon=True
                    )
                    t.start()

                elif len(faces) == 0:
                    with self._lock:
                        self.current_label = "Yuz Algilanmadi"
                        self.current_color = (128, 128, 128)

                frame = self._draw_overlay(frame, faces)
                cv2.imshow("Guvenlik Kamerasi", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Sistem kapatılıyor...")
                    break

        finally:
            self.cap.release()
            cv2.destroyAllWindows()


# ──────────────────────────────────────────────
# BAŞLAT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════╗
║        GÜVENLİK SİSTEMİ v1.0            ║
║   DeepFace + OpenCV Yüz Tanıma          ║
╚══════════════════════════════════════════╝
    """)
    camera = SecurityCamera(camera_index=0)
    camera.run()
