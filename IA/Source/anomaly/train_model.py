import joblib
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

# 1. Résolution dynamique des chemins relatifs
# SCRIPT_DIR = IA/source/anomaly
SCRIPT_DIR = Path(__file__).resolve().parent

# IA_DIR = IA/ (on remonte de deux niveaux : anomaly -> source -> IA)
IA_DIR = SCRIPT_DIR.parent.parent

# Définition des chemins vers data/ et models/
CSV_PATH = IA_DIR / "Data" / "telemetry_dataset.csv"
MODELS_DIR = IA_DIR / "Models"
OUTPUT_MODEL_PATH = MODELS_DIR / "Isolation_Forest.joblib"

# Création automatique du dossier models/ s'il n'existe pas encore
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print(f"[INFO] Chargement du jeu de données depuis : {CSV_PATH}")

# 2. Chargement des données
if not CSV_PATH.exists():
    raise FileNotFoundError(f"Le fichier {CSV_PATH} est introuvable. Vérifie son emplacement.")

df = pd.read_csv(CSV_PATH)

# Ordre strict des features
FEATURES = ["temperature", "humidity", "gas", "motion"]
X = df[FEATURES]
y_true = df["label"] if "label" in df.columns else None

# 3. Entraînement de l'Isolation Forest
print("[INFO] Entraînement de l'Isolation Forest en cours...")
model = IsolationForest(
    n_estimators=100,
    contamination=0.05,
    max_samples="auto",
    random_state=42,
    n_jobs=-1
)

model.fit(X)

# 4. Rapport de performance (si les labels sont présents dans le CSV)
if y_true is not None:
    y_pred = model.predict(X)
    print("\n--- Rapport de performance ---")
    print(classification_report(y_true, y_pred, target_names=["Anomalie (-1)", "Nominal (1)"]))

# 5. Sauvegarde du modèle dans IA/models/
joblib.dump(model, OUTPUT_MODEL_PATH)
print(f"\n[SUCCÈS] Modèle sauvegardé avec succès dans : {OUTPUT_MODEL_PATH}")