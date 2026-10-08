import joblib
import pandas as pd
from pathlib import Path


class AnomalyDetector:
    def __init__(self, model_path: Path | None = None):
        if model_path is None:
            model_path = Path(__file__).resolve().parents[2] / "Models" / "Isolation_Forest.joblib"

        if not model_path.exists():
            raise FileNotFoundError(f"Modèle introuvable : {model_path}. Lance train_model.py d'abord.")

        self.model = joblib.load(model_path)
        self.features = ["temperature", "humidity", "gas", "motion"]

    def evaluate(self, payload: dict) -> tuple[bool, float]:
        """
        Retourne (is_anomaly: bool, anomaly_score: float).
        Score négatif = plus l'anomalie est marquée.
        """
        try:
            row = pd.DataFrame([{
                "temperature": float(payload["temperature"]),
                "humidity": float(payload["humidity"]),
                "gas": float(payload["gas"]),
                "motion": int(payload["motion"])
            }])[self.features]

            prediction = self.model.predict(row)[0]
            score = float(self.model.score_samples(row)[0])
            is_anomaly = (prediction == -1)
            return is_anomaly, score
        except KeyError as err:
            raise ValueError(f"Payload capteur incomplet : clé manquante {err}")