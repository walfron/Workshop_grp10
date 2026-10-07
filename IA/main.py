import json
import logging
import threading
import time
import cv2
import paho.mqtt.client as mqtt

from anomaly.anomaly_service import AnomalyDetector
from api_client import AlertApiClient
from vision.vision_service import VisionDetector

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "sentinel/sensors/data"
API_URL = "http://127.0.0.1:8000/api/v1/alerts"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

alert_client = AlertApiClient(api_url=API_URL)
anomaly_detector = AnomalyDetector()
vision_detector = VisionDetector(confidence_threshold=0.60, cooldown_sec=15)


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"Connecté au broker MQTT (code: {rc})")
    client.subscribe(MQTT_TOPIC)


def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        is_anomaly, score = anomaly_detector.evaluate(payload)

        if is_anomaly:
            logging.warning(f"Anomalie capteurs détectée ! Score: {score:.3f}")
            alert_client.send_alert(
                source="AI_SENSORS",
                alert_type="SENSOR_ANOMALY",
                severity="WARNING",
                details={"score": score, "raw_data": payload}
            )
    except Exception as err:
        logging.error(f"Erreur traitement trame MQTT : {err}")


def start_mqtt_loop():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    # En phase TLS avec INFRA, décommenter la ligne suivante :
    # client.tls_set(ca_certs="/etc/ssl/certs/sentinel_ca.crt")

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as err:
            logging.error(f"Déconnexion du broker MQTT ({err}), reconnexion dans 5s...")
            time.sleep(5)


def run_vision_loop(camera_index: int = 0, target_fps: int = 3):
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        logging.error("Impossible d'accéder à la webcam.")
        return

    frame_delay = 1.0 / target_fps
    logging.info(f"Boucle de vision démarrée (limite fixée à {target_fps} FPS)")

    try:
        while True:
            start_time = time.perf_counter()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            detected, conf, box = vision_detector.detect_person(frame)
            if detected:
                logging.warning(f"Intrusion humaine détectée (confiance: {conf:.2f})")
                alert_client.send_alert(
                    source="AI_VISION",
                    alert_type="HUMAN_INTRUSION",
                    severity="CRITICAL",
                    details={"confidence": conf, "box": box}
                )

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.0, frame_delay - elapsed)
            time.sleep(sleep_time)

    finally:
        cap.release()


if __name__ == "__main__":
    mqtt_thread = threading.Thread(target=start_mqtt_loop, daemon=True)
    mqtt_thread.start()

    run_vision_loop()