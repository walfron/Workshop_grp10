import datetime
import json
import logging
import os
import time
from pathlib import Path
import joblib
import numpy as np
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv

# --- 1. Chargement de la configuration via .env ---
# Recherche du fichier .env dans le dossier du script ou à la racine du projet
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env" if (SCRIPT_DIR / ".env").exists() else SCRIPT_DIR.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sentinel/+/telemetry")
DEV_API_URL = os.getenv("DEV_API_URL", "http://192.168.10.195:3000/api/v1/alerts")
ALERT_COOLDOWN_SEC = float(os.getenv("ALERT_COOLDOWN_SEC", 10.0))

# Vérification stricte des variables critiques
if not all([MQTT_BROKER, MQTT_USER, MQTT_PASSWORD]):
    raise ValueError(
        "Erreur critique : MQTT_BROKER, MQTT_USER et MQTT_PASSWORD doivent être définis dans le fichier .env !"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)

# --- 2. Recherche et chargement du modèle Isolation Forest ---
CANDIDATE_MODEL_PATHS = [
    Path(os.getenv("MODEL_PATH", "")),
    SCRIPT_DIR / "Isolation_Forest.joblib",
    SCRIPT_DIR.parent / "Models" / "Isolation_Forest.joblib",
    SCRIPT_DIR.parent.parent / "Models" / "Isolation_Forest.joblib"
]

model_path = next((p for p in CANDIDATE_MODEL_PATHS if p.is_file()), None)
model = None

if model_path:
    try:
        model = joblib.load(str(model_path))
        logging.info(f"Modèle Isolation Forest (.joblib) chargé depuis : {model_path}")
    except Exception as e:
        logging.error(f"Échec du chargement du fichier joblib ({model_path}) : {e}")
else:
    logging.warning("Aucun modèle isolation_forest.joblib trouvé. Mode seuillage heuristique activé.")

# Plages physiques de référence pour identifier les grandeurs déviantes
BASELINE = {
    "temperature": {"min": 15.0, "max": 35.0},
    "humidity": {"min": 25.0, "max": 75.0},
    "gas": {"max": 200.0}
}

last_alert_time = 0.0

# --- 3. Transmission HTTP à l'API du Frontend ---
def send_http_alert(anomalous_fields: list, payload_data: dict, score: float, topic: str):
    fields_str = ", ".join(anomalous_fields)
    summary_message = f"Anomalie détectée sur : {fields_str} (score: {score:.2f})"

    alert_body = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "AI_ANOMALY_ENGINE",
        "type": "SENSOR_ANOMALY",
        "level": "warning",
        "severity": "warning",
        "message": summary_message[:200],
        "details": {
            "anomalous_fields": anomalous_fields,  # Contrat attendu par le frontend React
            "anomalies": anomalous_fields,
            "temperature": payload_data.get("temperature"),
            "humidity": payload_data.get("humidity"),
            "gas": payload_data.get("gas"),
            "motion": payload_data.get("motion"),
            "score": float(score),
            "topic": topic
        }
    }

    try:
        res = requests.post(DEV_API_URL, json=alert_body, timeout=2.0)
        if res.status_code in (200, 201):
            logging.info(f"Alerte validée par le serveur DEV (code {res.status_code}) pour : {fields_str}")
        else:
            logging.warning(f"Rejet API DEV ({res.status_code}) : {res.text}")
    except Exception as err:
        logging.error(f"Impossible de contacter l'API DEV ({DEV_API_URL}) : {err}")

# --- 4. Traitement des flux de télémétrie ---
def process_telemetry(payload: dict, topic: str):
    global last_alert_time

    # Extraction et standardisation des mesures
    raw_temp = payload.get("temperature", payload.get("temp", 22.0))
    raw_hum = payload.get("humidity", payload.get("hum", 50.0))
    raw_gas = payload.get("gas", payload.get("gas", payload.get("mq2", 100.0)))
    raw_mot = payload.get("motion", payload.get("pir", payload.get("presence", 0)))

    try:
        temp = float(raw_temp)
        hum = float(raw_hum)
        gas = float(raw_gas)
        motion = int(raw_mot)
    except ValueError as e:
        logging.error(f"Format numérique invalide dans le message MQTT : {e}")
        return

    is_anomaly = False
    score = 0.0

    # Inférence Machine Learning (Ordre strict des features du dataset)
    if model is not None:
        features = np.array([[temp, hum, gas, motion]])
        prediction = model.predict(features)[0]  # -1 = anomalie, 1 = normal
        score = float(model.decision_function(features)[0])
        if prediction == -1:
            is_anomaly = True
    else:
        # Repli sur les seuils absolus si le modèle n'est pas chargé
        if temp < BASELINE["temperature"]["min"] or temp > BASELINE["temperature"]["max"]:
            is_anomaly = True
        elif hum < BASELINE["humidity"]["min"] or hum > BASELINE["humidity"]["max"]:
            is_anomaly = True
        elif gas > BASELINE["gas"]["max"]:
            is_anomaly = True

    # Détection précise des variables responsables
    if is_anomaly:
        anomalous_fields = []

        if temp < BASELINE["temperature"]["min"] or temp > BASELINE["temperature"]["max"]:
            anomalous_fields.append("temperature")

        if hum < BASELINE["humidity"]["min"] or hum > BASELINE["humidity"]["max"]:
            anomalous_fields.append("humidity")

        if gas > BASELINE["gas"]["max"]:
            anomalous_fields.append("gas")

        # Dérive multivariée sans dépassement d'un seuil simple
        if not anomalous_fields:
            anomalous_fields = ["temperature", "humidity", "gas"]

        logging.warning(
            f"ANOMALIE DÉTECTÉE sur {anomalous_fields} | Temp={temp}°C, Hum={hum}%, Gaz={gas} ppm (score={score:.3f})"
        )

        now = time.time()
        if now - last_alert_time >= ALERT_COOLDOWN_SEC:
            last_alert_time = now
            current_data = {"temperature": temp, "humidity": hum, "gas": gas, "motion": motion}
            send_http_alert(anomalous_fields, current_data, score, topic)
    else:
        logging.info(
            f"Télémétrie conforme | Temp: {temp:.1f}°C, Hum: {hum:.1f}%, Gaz: {gas:.0f} ppm (score: {score:.3f})"
        )

# --- 5. Écoute MQTT ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"Connecté avec succès au broker MQTT ({MQTT_BROKER}:{MQTT_PORT})")
        client.subscribe(MQTT_TOPIC)
        logging.info(f"Abonnement actif sur le topic : {MQTT_TOPIC}")
    else:
        logging.error(f"Échec de connexion au broker MQTT (code d'erreur: {rc})")

def on_message(client, userdata, msg):
    try:
        decoded_payload = json.loads(msg.payload.decode("utf-8"))
        process_telemetry(decoded_payload, msg.topic)
    except json.JSONDecodeError:
        logging.error(f"Payload reçu non-JSON sur {msg.topic} : {msg.payload}")
    except Exception as e:
        logging.error(f"Erreur lors du traitement du message : {e}")

def main():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # Rétrocompatibilité avec paho-mqtt < 2.0.0
        client = mqtt.Client()

    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    logging.info(f"Connexion au broker MQTT {MQTT_BROKER}...")
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except KeyboardInterrupt:
            logging.info("Arrêt manuel du programme demandé.")
            client.disconnect()
            break
        except Exception as conn_err:
            logging.error(f"Connexion MQTT interrompue ({conn_err}). Nouvelle tentative dans 5 secondes...")
            time.sleep(5)

if __name__ == "__main__":
    main()