# Supervision du Pi (MCO) — Sentinel-X

Agent Python léger, sur l'**hôte** (service systemd, utilisateur `sentinel`, non root, pas de conteneur), qui publie l'état du Pi en **MQTTS** sur `192.168.10.10:8883`. Il n'ouvre **aucun port**.

| Fichier | Rôle | Installé dans |
|---|---|---|
| `sentinel_monitor.py` | agent | lancé depuis le dépôt |
| `sentinel-monitor.service` | service systemd durci (64 Mo, 10 % CPU) | `/etc/systemd/system/` |
| `journald-90-sentinel.conf` | journald limité à 100 Mo | `/etc/systemd/journald.conf.d/90-sentinel.conf` |

Dépendance : `python3-paho-mqtt` (paquet Debian). Secrets : `MQTT_MONITOR_USER` / `MQTT_MONITOR_PASSWORD` dans `.env` (non versionné). L'agent ne lit dans `.env` que les clés `MQTT_MONITOR_*` et `MONITOR_*`.

## Topics

| Topic | Quand | QoS / retain |
|---|---|---|
| `sentinel/1/system` | toutes les 30 s | 0 / **retenu** (le dashboard a le dernier état dès l'abonnement) |
| `sentinel/1/alerts` | au franchissement d'un seuil (`state: "alert"`) et au retour à la normale (`state: "ok"`) | 1 / non retenu |

Compte MQTT `monitor` : écriture sur `sentinel/+/system` et `sentinel/+/alerts`, lecture de `$SYS/broker/clients/#`. Le compte `backend` lit `sentinel/+/system`.

Le topic `alerts` est partagé avec l'ESP et l'IA : **filtrer sur `"source": "monitor"`**.

### `sentinel/1/system`

```json
{
  "ts": "2026-10-07T10:07:29+02:00", "node": "1", "source": "monitor", "host": "sentinel",
  "uptime_s": 2381, "cpu_pct": 2.8, "load1": 0.18,
  "mem_pct": 11.0, "mem_used_mb": 885, "mem_total_mb": 8062,
  "temp_c": 59.0, "throttled": "0x0", "disk_pct": 29.0, "disk_free_gb": 20.1,
  "containers": [
    {"name": "db", "state": "running", "health": "healthy", "restarts": 0, "log_rotation": true, "log_max_mb": 30.0}
  ],
  "logs": {"journald_mb": 8.0, "docker_max_mb": 90.0, "docker_rotation_ok": true},
  "mqtt_clients": 4
}
```

`docker_max_mb` est la taille **maximale** des logs Docker (`max-size` × `max-file`) : les fichiers eux-mêmes (`/var/lib/docker`) ne sont lisibles que par root. `null` = mesure indisponible.

### `sentinel/1/alerts`

```json
{"ts": "2026-10-07T10:07:30+02:00", "node": "1", "source": "monitor",
 "check": "temp", "state": "alert", "value": 76.2, "threshold": 75.0,
 "message": "Température 76.2 °C > 75 °C"}
```

`check` : `cpu`, `mem`, `temp`, `throttled`, `disk`, `logs`, `docker`, `container:<service>`, `monitor`. Si l'agent disparaît (crash, arrêt), le broker publie son testament : `check: "monitor"`, `state: "alert"` ; à la reconnexion, `state: "ok"`.

## Seuils (surchargeables par `MONITOR_<NOM>` dans `.env`)

| Contrôle | Alerte si | Variable (défaut) |
|---|---|---|
| CPU | > 90 % pendant 2 min | `MONITOR_CPU_MAX` (90), `MONITOR_CPU_DURATION` (120 s) |
| RAM | > 85 % (hors cache) | `MONITOR_MEM_MAX` (85) |
| Température | > 75 °C | `MONITOR_TEMP_MAX` (75) |
| Alimentation | `get_throttled` ≠ `0x0` | — |
| Disque `/` | > 85 % | `MONITOR_DISK_MAX` (85) |
| Logs | journald > 200 Mo, ou un conteneur sans rotation | `MONITOR_LOGS_MAX_MB` (200) |
| Conteneurs | arrêté, `unhealthy`, ou ≥ 3 redémarrages en 10 min | `MONITOR_RESTARTS_MAX` (3), `MONITOR_RESTARTS_WINDOW` (600 s) |
| Docker | `docker ps` en échec | — |

Une alerte n'est émise qu'au **changement d'état** (pas de répétition toutes les 30 s).

## Installation (sudo, sur le Pi)

```
sudo apt-get install --no-install-recommends python3-paho-mqtt
sudo install -m 644 infra/monitoring/sentinel-monitor.service /etc/systemd/system/
sudo install -D -m 644 infra/monitoring/journald-90-sentinel.conf /etc/systemd/journald.conf.d/90-sentinel.conf
sudo systemctl restart systemd-journald
sudo systemctl daemon-reload && sudo systemctl enable --now sentinel-monitor
journalctl -u sentinel-monitor -f
```

Prérequis : compte `monitor` dans `infra/mosquitto/config/passwd` (non versionné) et dans `infra/mosquitto/config/acl` (voir `docs/journal-infra.md`).

## Tests

```
# Un cycle, affiché à l'écran
python3 -I infra/monitoring/sentinel_monitor.py --once
# Simulation d'alerte : seuil abaissé pour ce seul lancement
MONITOR_TEMP_MAX=40 python3 -I infra/monitoring/sentinel_monitor.py --once
```
