import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
TRAIN_PATH = DATA_DIR / "sensors_train.csv"
TEST_PATH = DATA_DIR / "sensors_test.csv"


def generate_normal_data(n_samples: int = 5000) -> pd.DataFrame:
    np.random.seed(42)
    time_steps = np.linspace(0, 50, n_samples)

    temperature = 21.0 + 2.5 * np.sin(time_steps) + np.random.normal(0, 0.4, n_samples)
    humidity = 50.0 + 8.0 * np.cos(time_steps) + np.random.normal(0, 1.0, n_samples)
    gas_ppm = 120.0 + 15.0 * np.sin(time_steps * 0.5) + np.random.normal(0, 5.0, n_samples)
    motion = np.random.choice([0, 1], size=n_samples, p=[0.85, 0.15])

    return pd.DataFrame({
        "temperature": np.round(temperature, 2),
        "humidity": np.round(humidity, 2),
        "gas_ppm": np.round(np.clip(gas_ppm, 50, 400), 2),
        "motion": motion
    })


def generate_test_data_with_anomalies(n_samples: int = 1500) -> pd.DataFrame:
    np.random.seed(99)
    df = generate_normal_data(n_samples)
    df["label"] = 1

    df.loc[300:450, "temperature"] += np.linspace(0, 18, 151)
    df.loc[300:450, "label"] = -1

    df.loc[800:870, "gas_ppm"] += np.random.uniform(250, 450, 71)
    df.loc[800:870, "motion"] = 0
    df.loc[800:870, "label"] = -1

    df.loc[1200:1260, "temperature"] = -40.0
    df.loc[1200:1260, "humidity"] = 0.0
    df.loc[1200:1260, "label"] = -1

    return df


if __name__ == "__main__":
    train_df = generate_normal_data()
    test_df = generate_test_data_with_anomalies()

    train_df.to_csv(TRAIN_PATH, index=False)
    test_df.to_csv(TEST_PATH, index=False)
    print(f"Datasets générés : {TRAIN_PATH} ({len(train_df)} lignes), {TEST_PATH} ({len(test_df)} lignes)")