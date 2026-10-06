import datetime
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AlertApiClient:
    def __init__(self, api_url: str = "http://127.0.0.1:8000/api/v1/alerts", timeout: float = 3.0):
        self.api_url = api_url
        self.timeout = timeout

    def send_alert(self, source: str, alert_type: str, severity: str, details: dict) -> bool:
        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": source,
            "type": alert_type,
            "severity": severity,
            "details": details
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            if response.status_code in (200, 201):
                logging.info(f"Alerte envoyée avec succès ({alert_type}) : {response.status_code}")
                return True
            logging.warning(f"Rejet de l'alerte par l'API ({response.status_code}) : {response.text}")
            return False
        except requests.exceptions.RequestException as err:
            logging.error(f"Échec de liaison avec l'API DEV ({self.api_url}) : {err}")
            return False