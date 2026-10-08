import datetime
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AlertApiClient:
    def __init__(self, api_url: str = "http://192.168.41.124:3000/api/v1/alerts", timeout: float = 3.0):
        self.api_url = api_url
        self.timeout = timeout

    def send_alert(self, source: str, alert_type: str, severity: str, details: dict, message: str | None = None) -> bool:
        level = severity.lower()

        # Construction automatique du message obligatoire (1 à 200 caractères)
        if not message:
            if alert_type == "HUMAN_INTRUSION":
                conf = details.get("confidence", 0.0)
                message = f"Intrusion détectée par vision IA (confiance : {conf:.2f})"
            elif alert_type == "SENSOR_ANOMALY":
                score = details.get("score", 0.0)
                message = f"Anomalie capteurs détectée par IA (score : {score:.2f})"
            else:
                message = f"Alerte {alert_type} émise par {source}"

        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": source,
            "type": alert_type,
            "level": level,
            "severity": level,
            "message": message[:200],  # Tronqué à 200 caractères max par sécurité
            "details": details
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            if response.status_code in (200, 201):
                logging.info(f"Alerte validée par l'API ({alert_type}) : code {response.status_code}")
                return True
            logging.warning(f"Rejet de l'alerte par l'API ({response.status_code}) : {response.text}")
            return False
        except requests.exceptions.RequestException as err:
            logging.error(f"Échec de liaison avec l'API DEV ({self.api_url}) : {err}")
            return False