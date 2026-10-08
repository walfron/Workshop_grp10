import numpy as np
import pandas as pd

np.random.seed(42)

N_SAMPLES = 5000
N_ANOMALIES = int(N_SAMPLES * 0.05)
N_NORMAL = N_SAMPLES - N_ANOMALIES

temp_normal = np.random.normal(loc=22.0, scale=2.5, size=N_NORMAL)
hum_normal = 55.0 - (temp_normal - 22.0) * 1.5 + np.random.normal(loc=0.0, scale=3.0, size=N_NORMAL)
hum_normal = np.clip(hum_normal, 30.0, 70.0)

gas_normal = np.random.exponential(scale=25.0, size=N_NORMAL) + 40.0
gas_normal = np.clip(gas_normal, 20.0, 150.0)

motion_normal = np.random.choice([0, 1], size=N_NORMAL, p=[0.8, 0.2])

df_normal = pd.DataFrame({
    "temperature": np.round(temp_normal, 2),
    "humidity": np.round(hum_normal, 2),
    "gas": np.round(gas_normal, 2),
    "motion": motion_normal,
    "label": 1  # 1 = Nominal
})

n_a = N_ANOMALIES // 3
temp_a = np.random.normal(22.0, 2.0, n_a)
hum_a = np.random.normal(50.0, 5.0, n_a)
gas_a = np.random.uniform(250.0, 600.0, n_a)
motion_a = np.zeros(n_a, dtype=int)

n_b = N_ANOMALIES // 3
temp_b = np.random.uniform(38.0, 55.0, n_b)
hum_b = np.random.uniform(15.0, 25.0, n_b)
gas_b = np.random.normal(70.0, 15.0, n_b)
motion_b = np.random.choice([0, 1], size=n_b, p=[0.7, 0.3])

n_c = N_ANOMALIES - (n_a + n_b)
temp_c = np.random.uniform(32.0, 42.0, n_c)
hum_c = np.random.uniform(85.0, 98.0, n_c)
gas_c = np.random.normal(80.0, 20.0, n_c)
motion_c = np.zeros(n_c, dtype=int)

df_anomalies = pd.DataFrame({
    "temperature": np.round(np.concatenate([temp_a, temp_b, temp_c]), 2),
    "humidity": np.round(np.concatenate([hum_a, hum_b, hum_c]), 2),
    "gas": np.round(np.concatenate([gas_a, gas_b, gas_c]), 2),
    "motion": np.concatenate([motion_a, motion_b, motion_c]),
    "label": -1  # -1 = Anomalie
})

dataset = pd.concat([df_normal, df_anomalies], ignore_index=True)
dataset = dataset.sample(frac=1.0, random_state=42).reset_index(drop=True)

dataset.to_csv("telemetry_dataset.csv", index=False)
print(f"Jeu de données exporté avec succès ({len(dataset)} lignes, dont {N_ANOMALIES} anomalies).")