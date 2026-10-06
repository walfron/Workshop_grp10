import time
import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path


class VisionDetector:
    def __init__(self, model_path: Path | None = None, confidence_threshold: float = 0.55, cooldown_sec: int = 15):
        if model_path is None:
            model_path = Path(__file__).resolve().parents[2] / "models" / "yolov8n.onnx"

        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.confidence_threshold = confidence_threshold
        self.cooldown_sec = cooldown_sec
        self.last_alert_time = 0.0

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        img = cv2.resize(frame, (640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.transpose((2, 0, 1)).astype(np.float32) / 255.0
        return np.expand_dims(img, axis=0)

    def detect_person(self, frame: np.ndarray) -> tuple[bool, float, list[int] | None]:
        """
        Détecte la présence d'une personne (classe 0 sur COCO).
        Retourne : (intrusion_detectee, confiance, bounding_box)
        """
        input_tensor = self.preprocess(frame)
        outputs = self.session.run(None, {self.input_name: input_tensor})[0]

        # Format de sortie YOLOv8 : [1, 84, 8400] -> transpose en [8400, 84]
        predictions = np.transpose(outputs[0])

        boxes = predictions[:, :4]
        scores = predictions[:, 4:]

        # Classe 0 = 'person'
        person_scores = scores[:, 0]
        max_idx = np.argmax(person_scores)
        best_score = float(person_scores[max_idx])

        current_time = time.time()
        if best_score >= self.confidence_threshold:
            if current_time - self.last_alert_time >= self.cooldown_sec:
                self.last_alert_time = current_time
                box = boxes[max_idx].astype(int).tolist()
                return True, best_score, box

        return False, best_score, None