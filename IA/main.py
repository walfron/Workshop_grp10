import json
import logging
import os
import threading
import time
import cv2
import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify

from anomaly.anomaly_service import AnomalyDetector
from api_client import AlertApiClient
from vision.vision_service import VisionDetector

# --- Configuration Réseau ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.41.123")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "ia")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "U0l3V5h-rSw0Mm4OkpeBXv5mNgJnrktf")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sentinel/+/telemetry")

API_URL = os.getenv("API_URL", "http://192.168.41.124:3000/api/v1/alerts")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

alert_client = AlertApiClient(api_url=API_URL)
anomaly_detector = AnomalyDetector()
vision_detector = VisionDetector(confidence_threshold=0.55, cooldown_sec=10)

# Buffer vidéo partagé
output_frame = None
frame_lock = threading.Lock()

# Initialisation Flask
app = Flask(__name__)

# En-têtes CORS automatiques sur TOUTES les réponses
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

def generate_frames():
    global output_frame, frame_lock
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.04)
                continue
            ret, buffer = cv2.imencode(".jpg", output_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                continue
            frame_bytes = buffer.tobytes()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.04)

# Route accessible sur '/' ET '/video_feed', acceptant GET et OPTIONS
@app.route("/", methods=["GET", "OPTIONS"])
@app.route("/video_feed", methods=["GET", "OPTIONS"])
def video_feed():
    from flask import request
    if request.method == "OPTIONS":
        return Response(status=200)
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

# Route de santé au cas où son frontend ferait un check API
@app.route("/health", methods=["GET", "OPTIONS"])
@app.route("/status", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "ok", "service": "webcam"}), 200

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True, use_reloader=False)


# --- Analyse spécifique du capteur anormal (BONUS) ---
def identify_anomaly_causes(payload: dict) -> list[str]:
    causes = []
    temp = payload.get("temperature")
    hum = payload.get("humidity")
    gas = payload.get("gas_ppm")

    if temp is not None:
        if temp > 35.0:
            causes.append(f"Température critique ({temp:.1f}°C)")
        elif temp < 15.0:
            causes.append(f"Température anormalement basse ({temp:.1f}°C)")

    if hum is not None:
        if hum > 75.0:
            causes.append(f"Humidité trop élevée ({hum:.1f}%)")
        elif hum < 25.0:
            causes.append(f"Humidité anormalement basse ({hum:.1f}%)")

    if gas is not None and gas > 200.0:
        causes.append(f"Concentration de gaz anormale ({gas:.0f} ppm)")

    if not causes:
        causes.append("Dérive anormale multivariée")

    return causes


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"Connecté avec succès au broker MQTT ({MQTT_BROKER}) en tant que '{MQTT_USER}'")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error(f"Échec authentification MQTT (code {rc})")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        # Normalisation des données
        if "motion" not in payload:
            payload["motion"] = int(payload.get("pir", payload.get("presence", 0)))

        if "gas_ppm" not in payload:
            payload["gas_ppm"] = float(payload.get("gas", payload.get("mq2", 100.0)))

        if "temperature" not in payload and "temp" in payload:
            payload["temperature"] = float(payload["temp"])

        if "humidity" not in payload and "hum" in payload:
            payload["humidity"] = float(payload["hum"])

        # Évaluation par le modèle IA
        is_anomaly, score = anomaly_detector.evaluate(payload)

        if is_anomaly:
            # Identification des causes spécifiques
            causes = identify_anomaly_causes(payload)
            causes_str = ", ".join(causes)
            alert_msg = f"Anomalie détectée sur : {causes_str} (score: {score:.2f})"

            logging.warning(f"ANOMALIE CAPTEUR DÉTECTÉE ! -> {causes_str}")

            alert_client.send_alert(
                source="AI_SENSORS",
                alert_type="SENSOR_ANOMALY",
                severity="warning",
                message=alert_msg,
                details={
                    "score": score,
                    "causes": causes,
                    "raw_data": payload,
                    "topic": msg.topic
                }
            )
        else:
            logging.info(f"Télémétrie conforme (score : {score:.3f})")

    except Exception as err:
        logging.error(f"Erreur traitement télémétrie : {err}")

def start_mqtt_loop():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception:
            time.sleep(5)

def run_vision_loop(camera_index: int = CAMERA_INDEX, target_fps: int = 5):
    global output_frame, frame_lock
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        logging.error(f"Impossible d'ouvrir la caméra {camera_index}.")
        return

    frame_delay = 1.0 / target_fps
    logging.info(f"Vision démarrée sur caméra {camera_index} ({target_fps} FPS)")

    try:
        while True:
            start_time = time.perf_counter()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.04)
                continue

            h, w, _ = frame.shape
            is_present, should_alert, conf, box = vision_detector.detect_person(frame)

            if is_present:
                status_text = f"INTRUSION ({conf:.2f})"
                color = (0, 0, 255)
                if box:
                    cx, cy, bw, bh = box
                    x1 = int((cx - bw / 2) * (w / 640.0))
                    y1 = int((cy - bh / 2) * (h / 640.0))
                    x2 = int((cx + bw / 2) * (w / 640.0))
                    y2 = int((cy + bh / 2) * (h / 640.0))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            else:
                status_text = f"NOMINAL ({conf:.2f})"
                color = (0, 255, 0)

            cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            with frame_lock:
                output_frame = frame.copy()

            cv2.imshow("Sentinel-X - Direct (Local)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            if should_alert:
                msg = f"Intrusion détectée par vision IA (confiance : {conf:.2f})"
                logging.warning(f"INTRUSION CONFIRMÉE ({conf:.2f}) -> Alerte envoyée à l'API")
                alert_client.send_alert(
                    source="AI_VISION",
                    alert_type="HUMAN_INTRUSION",
                    severity="critical",
                    message=msg,
                    details={"confidence": conf, "box": box}
                )

            elapsed = time.perf_counter() - start_time
            time.sleep(max(0.0, frame_delay - elapsed))
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    threading.Thread(target=start_mqtt_loop, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    run_vision_loop()