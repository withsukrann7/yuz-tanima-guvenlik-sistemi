"""MediaPipe Tasks ile kare veya fotoğrafta yüz kutularını bulur."""
from pathlib import Path

import cv2

from . import config


class YuzBulucu:
    """BGR OpenCV görüntülerini MediaPipe Face Detector ile işler."""

    def __init__(self, *, video=False):
        import mediapipe as mp

        model = config.MEDIAPIPE_MODEL
        if not Path(model).is_file():
            raise FileNotFoundError(f"MediaPipe yüz modeli bulunamadı: {model}")

        self._mp = mp
        self._video = video
        mode = mp.tasks.vision.RunningMode.VIDEO if video else mp.tasks.vision.RunningMode.IMAGE
        options = mp.tasks.vision.FaceDetectorOptions(
            # Pass bytes rather than a Windows path: MediaPipe's native loader
            # can fail when a user profile contains non-ASCII characters
            # (for example, "Masaüstü").
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model.read_bytes()),
            running_mode=mode,
            min_detection_confidence=config.MEDIAPIPE_MIN_GUVEN,
        )
        self._detector = mp.tasks.vision.FaceDetector.create_from_options(options)

    def tespit_et(self, goruntu_bgr, zaman_damgasi_ms=None):
        """Görüntüdeki yüzleri (x, y, genişlik, yükseklik) listesi olarak döndürür."""
        rgb = cv2.cvtColor(goruntu_bgr, cv2.COLOR_BGR2RGB)
        mp_goruntu = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

        if self._video:
            if zaman_damgasi_ms is None:
                raise ValueError("Video modunda artan zaman damgası gereklidir")
            sonuc = self._detector.detect_for_video(mp_goruntu, int(zaman_damgasi_ms))
        else:
            sonuc = self._detector.detect(mp_goruntu)

        yukseklik, genislik = goruntu_bgr.shape[:2]
        yuzler = []
        for tespit in sonuc.detections:
            kutu = tespit.bounding_box
            x1 = max(0, int(kutu.origin_x))
            y1 = max(0, int(kutu.origin_y))
            x2 = min(genislik, int(kutu.origin_x + kutu.width))
            y2 = min(yukseklik, int(kutu.origin_y + kutu.height))
            if x2 > x1 and y2 > y1:
                yuzler.append((x1, y1, x2 - x1, y2 - y1))
        return yuzler

    def close(self):
        self._detector.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
