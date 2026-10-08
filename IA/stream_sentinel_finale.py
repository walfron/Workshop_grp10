import datetime
import json
import logging
import threading
import time
from pathlib import Path

import cv2
import joblib
import numpy as np
import paho.mqtt.client as mqtt
import requests
from flask import Flask, Response

# --- Configuration Réseau & Endpoints ---
DEV_API_URL = "http://192.168.41.124:3000/api/v1/alerts"
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USER = "ia"
MQTT_PASSWORD = "U0l3V5h-rSw0Mm4OkpeBXv5mNgJnrktf"
MQTT_TOPIC = "sentinel/+/telemetry"

YOLO_PATH = Path("/home/sentinel/yolov8n.onnx")
MODEL_JOBLIB_PATH = Path("/home/sentinel/isolation_forest.joblib")

ALERT_COOLDOWN_SEC = 10.0
CONFIDENCE_THRESHOLD = 0.55

# Seuils physiques de référence pour nommer la variable anormale
BASELINE = {
    "temperature": {"min": 15.0, "max": 35.0},
    "humidity": {"min": 25.0, "max": 75.0},
    "gas": {"max": 200.0}
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# --- Chargement du modèle Isolation Forest Joblib ---
anomaly_model = None
if MODEL_JOBLIB_PATH.exists():
    try:
        anomaly_model = joblib.load(str(MODEL_JOBLIB_PATH))
        logging.info("Modèle Isolation Forest (.joblib) chargé avec succès sur le Raspberry Pi !")
    except Exception as e:
        logging.error(f"Erreur chargement modèle joblib : {e}")
else:
    logging.warning(f"Fichier {MODEL_JOBLIB_PATH} introuvable sur le Pi.")

# --- Serveur Vidéo Flask ---
app = Flask(__name__)
output_frame = None
frame_lock = threading.Lock()

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
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

# --- Fonction d'envoi HTTP API DEV ---
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
            logging.info(f"Alerte envoyée au dashboard DEV (code {resp.status_code}) : {alert_type}")
        else:
            logging.warning(f"Rejet API DEV ({resp.status_code}) : {resp.text}")
    except Exception as err:
        logging.error(f"Erreur contact API DEV : {err}")

# --- Évaluation Isolation Forest & Détermination des champs anormaux ---
last_sensor_alert_time = 0.0

def evaluate_sensor_payload(payload: dict, topic: str):
    global last_sensor_alert_time

    # 1. Extraction et normalisation des valeurs
    raw_temp = payload.get("temperature", payload.get("temp", 22.0))
    raw_hum = payload.get("humidity", payload.get("hum", 50.0))
    raw_gas = payload.get("gas_ppm", payload.get("gas", payload.get("mq2", 100.0)))
    raw_motion = payload.get("motion", payload.get("pir", payload.get("presence", 0)))

    temp = float(raw_temp)
    hum = float(raw_hum)
    gas = float(raw_gas)
    motion = int(raw_motion)

    is_anomaly = False
    score = 0.0

    # 2. Prédiction par le modèle Isolation Forest
    if anomaly_model is not None:
        features = np.array([[temp, hum, gas, motion]])
        pred = anomaly_model.predict(features)[0]  # -1 = anomalie, 1 = normal
        score = float(anomaly_model.decision_function(features)[0])
        if pred == -1:
            is_anomaly = True
    else:
        # Secours si le fichier joblib n'est pas chargé
        if temp > BASELINE["temperature"]["max"] or hum > BASELINE["humidity"]["max"] or gas > BASELINE["gas"]["max"]:
            is_anomaly = True

    # 3. Si anomalie, identifier quelles variables ('temperature', 'humidity', 'gas') sont en cause
    if is_anomaly:
        anomalous_fields = []

        if temp > BASELINE["temperature"]["max"] or temp < BASELINE["temperature"]["min"]:
            anomalous_fields.append("temperature")

        if hum > BASELINE["humidity"]["max"] or hum < BASELINE["humidity"]["min"]:
            anomalous_fields.append("humidity")

        if gas > BASELINE["gas"]["max"]:
            anomalous_fields.append("gas")

        # Cas de dérive combinée : si aucun ne dépasse individuellement son seuil extrême
        if not anomalous_fields:
            anomalous_fields = ["temperature", "humidity", "gas"]

        fields_str = ", ".join(anomalous_fields)
        full_msg = f"Anomalie capteur détectée sur : {fields_str} (score: {score:.2f})"
        logging.warning(f"ANOMALIE JOBLIB DÉTECTÉE -> {full_msg}")

        now = time.time()
        if now - last_sensor_alert_time >= ALERT_COOLDOWN_SEC:
            last_sensor_alert_time = now
            send_http_alert(
                source="AI_SENSORS",
                alert_type="SENSOR_ANOMALY",
                severity="warning",
                message=full_msg,
                details={
                    "anomalous_fields": anomalous_fields,  # ['temperature'], ['gas'], etc.
                    "temperature": temp,
                    "humidity": hum,
                    "gas": gas,
                    "score": score,
                    "raw_data": payload,
                    "topic": topic
                }
            )
    else:
        logging.info(f"Télémétrie conforme | Temp: {temp}°C, Hum: {hum}%, Gaz: {gas} ppm (score: {score:.3f})")

# --- MQTT Loop ---
def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"Connecté au broker MQTT ({MQTT_BROKER})")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error(f"Échec connexion MQTT code: {rc}")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        logging.info(f"Message reçu sur {msg.topic} : {payload}")
        evaluate_sensor_payload(payload, msg.topic)
    except Exception as e:
        logging.error(f"Erreur parsing MQTT : {e}")

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

# --- Initialisation YOLOv8 & Caméra ---
session = None
input_name = None
if YOLO_PATH.exists():
    try:
        import onnxruntime as ort
        session = ort.InferenceSession(str(YOLO_PATH), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
    except Exception as e:
        logging.warning(f"Erreur YOLO ONNX : {e}")

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

def run_vision_loop():
    global output_frame, frame_lock
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    if not cap.isOpened():
        logging.error("Périphérique caméra /dev/video0 introuvable.")
        return

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