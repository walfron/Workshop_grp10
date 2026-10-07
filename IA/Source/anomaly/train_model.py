import joblib
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

BASE_DIR = Path(__file__).resolve().parents[2]
TRAIN_CSV = BASE_DIR / "data" / "sensors_train.csv"
TEST_CSV = BASE_DIR / "data" / "sensors_test.csv"
MODEL_PATH = BASE_DIR / "models" / "isolation_forest.joblib"

def train():
    df_train = pd.read_csv(TRAIN_CSV)
    df_test = pd.read_csv(TEST_CSV)

    features = ["temperature", "humidity", "gas_ppm", "motion"]
    X_train = df_train[features]
    X_test = df_test[features]
    y_test = df_test["label"]

    model = IsolationForest(
        n_estimators=100,
        contamination=0.03,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train)

    y_pred = model.predict(X_test)
    print("Évaluation sur le jeu de test avec anomalies injectées :")
    print(classification_report(y_test, y_pred, target_names=["Anomalie (-1)", "Nominal (1)"]))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Modèle sauvegardé dans {MODEL_PATH}")

if __name__ == "__main__":
    train()