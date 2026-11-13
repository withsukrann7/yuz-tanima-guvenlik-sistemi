"""MediaPipe Face Landmarker tabanli temel goz kirpma kontrolu."""
import math
import time

import cv2

from . import config


class LivenessDetector:
    """Kameradaki kisiden gozlerini acip kapatmasini ister.

    Bu kontrol basit fotoğraf gösterme girişimlerini zorlaştırır; tek başına
    gelişmiş video tekrarlarını veya diğer sahtecilik yöntemlerini engellemez.
    """

    _EYE_LANDMARKS = (
        (33, 160, 158, 133, 153, 144),
        (362, 385, 387, 263, 373, 380),
    )

    def __init__(self):
        import mediapipe as mp

        model = config.MEDIAPIPE_FACE_LANDMARKER_MODEL
        if not model.is_file():
            raise FileNotFoundError(f"MediaPipe yuz noktasi modeli bulunamadi: {model}")
        with model.open("rb") as model_file:
            model_bytes = model_file.read()

        self._mp = mp
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self.reset()

    @staticmethod
    def _mesafe(a, b):
        return math.hypot(a.x - b.x, a.y - b.y)

    @classmethod
    def _eye_aspect_ratio(cls, landmarks, indices):
        p1, p2, p3, p4, p5, p6 = (landmarks[i] for i in indices)
        yatay = cls._mesafe(p1, p4)
        if yatay <= 1e-6:
            return 0.0
        return (cls._mesafe(p2, p6) + cls._mesafe(p3, p5)) / (2.0 * yatay)

    def reset(self):
        self._stage = "waiting_for_open_eyes"
        self._closed_frames = 0
        self._started_at = time.monotonic()
        self._passed = False

    def update(self, image_bgr, timestamp_ms):
        """Process one frame; return True after a complete blink."""
        if self._passed:
            return True
        if time.monotonic() - self._started_at > config.LIVENESS_TIMEOUT_SECONDS:
            self.reset()

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_goruntu = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_goruntu, int(timestamp_ms))
        if not result.face_landmarks:
            return False

        landmarks = result.face_landmarks[0]
        ratios = [self._eye_aspect_ratio(landmarks, ids) for ids in self._EYE_LANDMARKS]
        eye_ratio = sum(ratios) / len(ratios)
        if self._stage == "waiting_for_open_eyes":
            if eye_ratio >= config.LIVENESS_EYE_OPEN_THRESHOLD:
                self._stage = "waiting_for_blink"
        elif self._stage == "waiting_for_blink":
            if eye_ratio < config.LIVENESS_EYE_CLOSED_THRESHOLD:
                self._closed_frames += 1
                if self._closed_frames >= config.LIVENESS_CLOSED_MIN_FRAMES:
                    self._stage = "waiting_for_reopen"
            else:
                self._closed_frames = 0
        elif (self._stage == "waiting_for_reopen"
                and eye_ratio >= config.LIVENESS_EYE_OPEN_THRESHOLD):
            self._passed = True
        return self._passed

    def close(self):
        self._landmarker.close()
