import datetime
import json
import logging
import os
import ssl
import threading
import time
from pathlib import Path

import cv2
import joblib
import numpy as np
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv
from flask import Flask, Response

# --- 1. Chargement de l'environnement ---
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env" if (SCRIPT_DIR / ".env").exists() else SCRIPT_DIR.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DEV_API_URL = os.getenv("DEV_API_URL", "http://192.168.10.195:3000/api/v1/alerts")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sentinel/+/telemetry")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() == "true"

YOLO_PATH = Path(os.getenv("YOLO_MODEL_PATH", "/home/sentinel/yolov8n.onnx"))
MODEL_JOBLIB_PATH = Path(os.getenv("ANOMALY_MODEL_PATH", "/home/sentinel/isolation_forest.joblib"))

ALERT_COOLDOWN_SEC = float(os.getenv("ALERT_COOLDOWN_SEC", 10.0))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.55))

# Seuils physiques de diagnostic
BASELINE = {
    "temperature": {"min": 15.0, "max": 35.0},
    "humidity": {"min": 25.0, "max": 75.0},
    "gas": {"max": 200.0}
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# --- 2. Chargement du modèle Isolation Forest (.joblib) ---
anomaly_model = None
if MODEL_JOBLIB_PATH.exists():
    try:
        anomaly_model = joblib.load(str(MODEL_JOBLIB_PATH))
        logging.info(f"Modèle Isolation Forest (.joblib) chargé depuis : {MODEL_JOBLIB_PATH}")
    except Exception as err:
        logging.error(f"Échec du chargement du fichier .joblib : {err}")
else:
    logging.warning(f"Fichier {MODEL_JOBLIB_PATH} introuvable. Mode repli par seuils activé.")

# --- 3. Serveur Vidéo Flask (Streaming MJPEG pour le Dashboard) ---
app = Flask(__name__)
output_frame = None
frame_lock = threading.Lock()

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
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

@app.route("/")
@app.route("/video_feed", methods=["GET", "OPTIONS"])
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/health")
def health():
    return {"status": "ok"}, 200

def run_flask():
    app.run(host="0.0.0.0", port=8080, threaded=True, debug=False, use_reloader=False)

# --- 4. Envoi HTTP d'alertes à DEV (192.168.10.195) ---
def send_http_alert(source: str, alert_type: str, severity: str, message: str, details: dict):
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
        "type": alert_type,
        "level": severity.lower(),
        "severity": severity.lower(),
        "message": message[:200],
        "details": details
    }
    try:
        resp = requests.post(DEV_API_URL, json=payload, timeout=2.0)
        if resp.status_code in (200, 201):
            logging.info(f"Alerte transmise avec succès au DEV ({alert_type}) : code {resp.status_code}")
        else:
            logging.warning(f"Rejet API DEV ({resp.status_code}) : {resp.text}")
    except Exception as err:
        logging.error(f"Impossible de joindre l'API DEV ({DEV_API_URL}) : {err}")

# --- 5. Inférence Isolation Forest & Détection d'Anomalies ---
last_sensor_alert_time = 0.0

def evaluate_sensor_payload(payload: dict, topic: str):
    global last_sensor_alert_time

    raw_temp = payload.get("temperature", payload.get("temp", 22.0))
    raw_hum = payload.get("humidity", payload.get("hum", 50.0))
    raw_gas = payload.get("gas_ppm", payload.get("gas", payload.get("mq2", 100.0)))
    raw_mot = payload.get("motion", payload.get("pir", payload.get("presence", 0)))

    try:
        temp = float(raw_temp)
        hum = float(raw_hum)
        gas = float(raw_gas)
        motion = int(raw_mot)
    except ValueError as err:
        logging.error(f"Valeur invalide dans le payload MQTT : {err}")
        return

    is_anomaly = False
    score = 0.0

    # Inférence Machine Learning (Ordre strict : [temperature, humidity, gas, motion])
    if anomaly_model is not None:
        features = np.array([[temp, hum, gas, motion]])
        pred = anomaly_model.predict(features)[0]  # -1 = anomalie, 1 = normal
        score = float(anomaly_model.decision_function(features)[0])
        if pred == -1:
            is_anomaly = True
    else:
        if (temp < BASELINE["temperature"]["min"] or temp > BASELINE["temperature"]["max"] or
            hum < BASELINE["humidity"]["min"] or hum > BASELINE["humidity"]["max"] or
            gas > BASELINE["gas"]["max"]):
            is_anomaly = True

    if is_anomaly:
        anomalous_fields = []
        descriptions = []

        if temp > BASELINE["temperature"]["max"] or temp < BASELINE["temperature"]["min"]:
            anomalous_fields.append("temperature")
            descriptions.append(f"temperature ({temp:.1f} °C)")

        if hum > BASELINE["humidity"]["max"] or hum < BASELINE["humidity"]["min"]:
            anomalous_fields.append("humidity")
            descriptions.append(f"humidity ({hum:.1f} %)")

        if gas > BASELINE["gas"]["max"]:
            anomalous_fields.append("gas")
            descriptions.append(f"gas ({gas:.0f} ppm)")

        # Cas d'anomalie multidimensionnelle sans dépassement univarié isolé
        if not anomalous_fields:
            anomalous_fields = ["temperature", "humidity", "gas"]
            descriptions.append(f"dérive conjointe (score: {score:.2f})")

        fields_str = ", ".join(anomalous_fields)
        full_msg = f"Anomalie détectée sur : {fields_str} ({', '.join(descriptions)})"
        logging.warning(f"ANOMALIE CAPTEUR -> {full_msg}")

        now = time.time()
        if now - last_sensor_alert_time >= ALERT_COOLDOWN_SEC:
            last_sensor_alert_time = now
            send_http_alert(
                source="AI_SENSORS",
                alert_type="SENSOR_ANOMALY",
                severity="warning",
                message=full_msg,
                details={
                    "anomalous_fields": anomalous_fields,  # Contrat attendu par le frontend
                    "anomalies": anomalous_fields,
                    "temperature": temp,
                    "humidity": hum,
                    "gas": gas,
                    "motion": motion,
                    "score": score,
                    "raw_data": payload,
                    "topic": topic
                }
            )
    else:
        logging.info(f"Télémétrie nominale | Temp: {temp:.1f}°C, Hum: {hum:.1f}%, Gaz: {gas:.0f} ppm (score: {score:.3f})")

# --- 6. Client MQTT ---
def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"Connecté au broker MQTT ({MQTT_BROKER}:{MQTT_PORT})")
        client.subscribe(MQTT_TOPIC)
        logging.info(f"Abonnement actif : {MQTT_TOPIC}")
    else:
        logging.error(f"Échec connexion MQTT (code {rc})")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        evaluate_sensor_payload(payload, msg.topic)
    except Exception as err:
        logging.error(f"Erreur parsing message MQTT : {err}")

def start_mqtt_loop():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()

    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    if MQTT_USE_TLS:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as conn_err:
            logging.error(f"Connexion MQTT impossible ({conn_err}). Nouvelle tentative dans 5 secondes...")
            time.sleep(5)

# --- 7. Modèle YOLOv8 ONNX ---
session = None
input_name = None
if YOLO_PATH.exists():
    try:
        import onnxruntime as ort
        session = ort.InferenceSession(str(YOLO_PATH), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        logging.info("Modèle YOLOv8n ONNX initialisé.")
    except Exception as err:
        logging.warning(f"Erreur initialisation YOLO : {err}")

def detect_yolo(frame):
    img = cv2.resize(frame, (640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.transpose((2, 0, 1)).astype(np.float32) / 255.0
    input_tensor = np.expand_dims(img, axis=0)

    outputs = session.run(None, {input_name: input_tensor})[0]
    preds = np.transpose(outputs[0])
    boxes = preds[:, :4]
    scores = preds[:, 4:]

    person_scores = scores[:, 0]
    best_idx = np.argmax(person_scores)
    best_score = float(person_scores[best_idx])

    if best_score >= CONFIDENCE_THRESHOLD:
        return True, best_score, boxes[best_idx].tolist()
    return False, best_score, None

# --- 8. Boucle Vidéo Caméra ---
def run_vision_loop():
    global output_frame, frame_lock

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    if not cap.isOpened():
        logging.error("Périphérique caméra /dev/video0 introuvable.")
        return

    logging.info("Flux vidéo webcam actif sur /dev/video0.")
    last_vision_alert = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.04)
                continue

            h, w, _ = frame.shape
            is_person = False
            best_conf = 0.0
            box = None

            if session is not None:
                is_person, best_conf, box = detect_yolo(frame)
                if is_person and box:
                    cx, cy, bw, bh = box
                    x1 = int((cx - bw / 2) * (w / 640.0))
                    y1 = int((cy - bh / 2) * (h / 640.0))
                    x2 = int((cx + bw / 2) * (w / 640.0))
                    y2 = int((cy + bh / 2) * (h / 640.0))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            if is_person:
                cv2.putText(frame, f"INTRUSION ({best_conf:.2f})", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                now = time.time()
                if now - last_vision_alert >= ALERT_COOLDOWN_SEC:
                    last_vision_alert = now
                    send_http_alert(
                        source="AI_VISION_PI",
                        alert_type="HUMAN_INTRUSION",
                        severity="critical",
                        message=f"Intrusion détectée par vision IA (confiance: {best_conf:.2f})",
                        details={"confidence": float(best_conf), "box": box}
                    )
            else:
                cv2.putText(frame, "NOMINAL", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            with frame_lock:
                output_frame = frame.copy()

            time.sleep(0.04)
    finally:
        cap.release()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=start_mqtt_loop, daemon=True).start()
    run_vision_loop()