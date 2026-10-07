#!/usr/bin/env python3
"""Sentinel-X — agent de supervision du Pi (filière INFRA).

Publie l'état du Pi en MQTTS (aucun port ouvert) :
  - sentinel/<node>/system : JSON horodaté toutes les MONITOR_INTERVAL secondes (retenu)
  - sentinel/<node>/alerts : uniquement au franchissement d'un seuil, puis au retour à la normale

Tourne sur l'HÔTE sous l'utilisateur sentinel (service systemd), pas en conteneur.
Ne lit dans .env QUE les variables MQTT_MONITOR_* et MONITOR_* (les autres secrets
ne sont jamais chargés). Dépendance : python3-paho-mqtt (paquet Debian).

Usage : sentinel_monitor.py [--env FICHIER] [--once]
  --once : un seul cycle (mesure, publication, alertes) puis sortie, pour les tests.
"""

import argparse
import json
import os
import shutil
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Seuils par défaut (surchargeables par MONITOR_<NOM> dans .env ou l'environnement)
DEFAULTS = {
    "MONITOR_NODE_ID": "1",
    "MONITOR_HOST": "192.168.10.10",
    "MONITOR_PORT": "8883",
    "MONITOR_CAFILE": os.path.join(REPO, "infra/mosquitto/certs/ca.crt"),
    "MONITOR_INTERVAL": "30",          # secondes
    "MONITOR_CPU_MAX": "90",           # %
    "MONITOR_CPU_DURATION": "120",     # secondes au-dessus du seuil avant alerte
    "MONITOR_MEM_MAX": "85",           # %
    "MONITOR_TEMP_MAX": "75",          # °C
    "MONITOR_DISK_MAX": "85",          # % de /
    "MONITOR_LOGS_MAX_MB": "200",      # Mo (journald)
    "MONITOR_RESTARTS_MAX": "3",       # redémarrages d'un conteneur ...
    "MONITOR_RESTARTS_WINDOW": "600",  # ... sur cette fenêtre (s) = boucle
}


def load_env(path):
    """Lit KEY=VALUE dans .env, sans l'exécuter, en ne gardant que les clés utiles."""
    conf = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.startswith(("MQTT_MONITOR_", "MONITOR_")):
                    conf[key] = value
    except OSError as e:
        sys.exit(f"Lecture impossible de {path} : {e.strerror}")
    # L'environnement (ex. test avec seuil abaissé) a priorité sur .env
    for key in list(conf) + ["MQTT_MONITOR_USER", "MQTT_MONITOR_PASSWORD"]:
        if key in os.environ:
            conf[key] = os.environ[key]
    for key in ("MQTT_MONITOR_USER", "MQTT_MONITOR_PASSWORD"):
        if not conf.get(key):
            sys.exit(f"{key} manquant dans {path}")
    return conf


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(cmd, timeout=10):
    """Lance une commande (sans shell) et renvoie sa sortie, ou None en cas d'échec."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------- mesures

class Collector:
    def __init__(self):
        self._cpu_prev = self._read_cpu()

    @staticmethod
    def _read_cpu():
        with open("/proc/stat") as f:
            vals = [int(v) for v in f.readline().split()[1:]]
        idle = vals[3] + vals[4]          # idle + iowait
        return sum(vals), idle

    def cpu_pct(self):
        total, idle = self._read_cpu()
        dt, di = total - self._cpu_prev[0], idle - self._cpu_prev[1]
        self._cpu_prev = (total, idle)
        return round(100.0 * (dt - di) / dt, 1) if dt > 0 else 0.0

    @staticmethod
    def memory():
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])       # kB
        total, avail = info["MemTotal"], info["MemAvailable"]
        return round(100.0 * (total - avail) / total, 1), (total - avail) // 1024, total // 1024

    @staticmethod
    def temp_c():
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read()) / 1000.0, 1)
        except OSError:
            return None

    @staticmethod
    def throttled():
        out = run(["vcgencmd", "get_throttled"])
        return out.strip().split("=", 1)[1] if out and "=" in out else None

    @staticmethod
    def disk():
        u = shutil.disk_usage("/")
        return round(100.0 * u.used / u.total, 1), round(u.free / 1e9, 1)

    @staticmethod
    def uptime_s():
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))

    @staticmethod
    def containers():
        """Conteneurs du projet compose 'sentinel' (via le CLI Docker, groupe docker)."""
        ids = run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=sentinel"])
        if ids is None:
            return None
        ids = ids.split()
        if not ids:
            return []
        out = run(["docker", "inspect"] + ids)
        if out is None:
            return None
        res = []
        for c in json.loads(out):
            log_cfg = c["HostConfig"].get("LogConfig") or {}
            res.append({
                "name": c["Config"]["Labels"].get("com.docker.compose.service", c["Name"].lstrip("/")),
                "state": c["State"]["Status"],
                "health": (c["State"].get("Health") or {}).get("Status"),
                "restarts": c.get("RestartCount", 0),
                "log_rotation": bool((log_cfg.get("Config") or {}).get("max-size")),
                "log_max_mb": _docker_log_max_mb(log_cfg),
            })
        return sorted(res, key=lambda x: x["name"])

    @staticmethod
    def journald_mb():
        out = run(["journalctl", "--disk-usage"])
        # "Archived and active journals take up 8M in the file system."
        if not out:
            return None
        for word in out.split():
            unit = word[-1:]
            if unit in "KMGT" and word[:-1].replace(".", "", 1).isdigit():
                return round(float(word[:-1]) * {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1048576}[unit], 1)
        return None


def _docker_log_max_mb(log_cfg):
    """Taille maximale théorique des logs d'un conteneur (max-size x max-file).
    Les fichiers eux-mêmes (/var/lib/docker) ne sont lisibles que par root."""
    cfg = log_cfg.get("Config") or {}
    size = cfg.get("max-size")
    if not size:
        return None
    mult = {"k": 1 / 1024, "m": 1, "g": 1024}.get(size[-1].lower(), 1 / 1048576)
    num = float(size[:-1]) if size[-1].isalpha() else float(size)
    return round(num * mult * int(cfg.get("max-file", "1")), 1)


# ---------------------------------------------------------------- alertes

class Check:
    """Seuil avec mémoire d'état : n'émet qu'aux changements (alerte / retour à la normale)."""

    def __init__(self, name, threshold, unit="", hold_s=0):
        self.name, self.threshold, self.unit, self.hold_s = name, threshold, unit, hold_s
        self.active = None          # None = inconnu (démarrage)
        self.since = None           # début du dépassement (pour hold_s)

    def update(self, breached, value, message):
        """Renvoie un message d'alerte / de retour, ou None si pas de changement."""
        t = time.monotonic()
        if breached:
            if self.since is None:
                self.since = t
            effective = t - self.since >= self.hold_s     # dépassement maintenu assez longtemps
        else:
            self.since = None
            effective = False
        previous, self.active = self.active, effective
        if effective == previous or (previous is None and not effective):
            return None                 # pas de changement (ou « ok » au démarrage : silence)
        return {
            "check": self.name,
            "state": "alert" if effective else "ok",
            "value": value,
            "threshold": self.threshold,
            "message": message if effective else f"{self.name} : retour à la normale",
        }


class Monitor:
    def __init__(self, conf, once=False):
        self.c = conf
        self.node = conf["MONITOR_NODE_ID"]
        self.t_system = f"sentinel/{self.node}/system"
        self.t_alerts = f"sentinel/{self.node}/alerts"
        f = lambda k: float(conf[k])
        self.checks = {
            "cpu": Check("cpu", f("MONITOR_CPU_MAX"), "%", hold_s=f("MONITOR_CPU_DURATION")),
            "mem": Check("mem", f("MONITOR_MEM_MAX"), "%"),
            "temp": Check("temp", f("MONITOR_TEMP_MAX"), "°C"),
            "throttled": Check("throttled", "0x0"),
            "disk": Check("disk", f("MONITOR_DISK_MAX"), "%"),
            "logs": Check("logs", f("MONITOR_LOGS_MAX_MB"), "Mo"),
            "docker": Check("docker", "accessible"),
        }
        self.container_checks = {}
        self.restart_hist = {}      # nom -> [(t, restarts)]
        self.mqtt_clients = None
        self.connected = threading.Event()
        self.was_connected = False
        self.collector = Collector()

        self.cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                               client_id=f"sentinel-monitor-{self.node}" + ("-test" if once else ""),
                               clean_session=True)
        self.cli.username_pw_set(conf["MQTT_MONITOR_USER"], conf["MQTT_MONITOR_PASSWORD"])
        # Vérifie la chaîne (ca.crt) et le nom / l'IP du serveur (SAN), TLS 1.2 minimum
        tls = ssl.create_default_context(cafile=conf["MONITOR_CAFILE"])
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        self.cli.tls_set_context(tls)
        self.cli.will_set(self.t_alerts, json.dumps({
            "ts": None, "node": self.node, "source": "monitor", "check": "monitor",
            "state": "alert", "message": "agent de supervision déconnecté"}), qos=1)
        self.cli.reconnect_delay_set(min_delay=2, max_delay=60)
        self.cli.on_connect = self._on_connect
        self.cli.on_disconnect = self._on_disconnect
        self.cli.on_message = self._on_message

    # -- MQTT
    def _on_connect(self, cli, userdata, flags, reason, props):
        if reason.is_failure:
            print(f"MQTT : connexion refusée ({reason})", flush=True)
            return
        print(f"MQTT : connecté à {self.c['MONITOR_HOST']}:{self.c['MONITOR_PORT']}", flush=True)
        cli.subscribe("$SYS/broker/clients/connected", qos=0)
        if self.was_connected:      # le testament (LWT) a pu partir : on signale le retour
            self._publish_alert({"check": "monitor", "state": "ok", "value": None, "threshold": None,
                                 "message": "agent de supervision reconnecté"})
        self.was_connected = True
        self.connected.set()

    def _on_disconnect(self, cli, userdata, flags, reason, props):
        self.connected.clear()
        print(f"MQTT : déconnecté ({reason})", flush=True)

    def _on_message(self, cli, userdata, msg):
        try:
            self.mqtt_clients = int(msg.payload)
        except ValueError:
            pass

    def _publish_alert(self, alert):
        alert = {"ts": now_iso(), "node": self.node, "source": "monitor", **alert}
        self.cli.publish(self.t_alerts, json.dumps(alert, ensure_ascii=False), qos=1)
        print(f"ALERTE {alert['state']} : {alert['message']}", flush=True)

    # -- cycle
    def measure(self):
        mem_pct, mem_used, mem_total = Collector.memory()
        disk_pct, disk_free = Collector.disk()
        containers = Collector.containers()
        docker_max = None
        if containers:
            docker_max = round(sum(c["log_max_mb"] or 0 for c in containers), 1)
        return {
            "ts": now_iso(),
            "node": self.node,
            "source": "monitor",
            "host": os.uname().nodename,
            "uptime_s": Collector.uptime_s(),
            "cpu_pct": self.collector.cpu_pct(),
            "load1": round(os.getloadavg()[0], 2),
            "mem_pct": mem_pct,
            "mem_used_mb": mem_used,
            "mem_total_mb": mem_total,
            "temp_c": Collector.temp_c(),
            "throttled": Collector.throttled(),
            "disk_pct": disk_pct,
            "disk_free_gb": disk_free,
            "containers": containers,
            "logs": {
                "journald_mb": Collector.journald_mb(),
                "docker_max_mb": docker_max,
                "docker_rotation_ok": all(c["log_rotation"] for c in containers) if containers else None,
            },
            "mqtt_clients": self.mqtt_clients,
        }

    def evaluate(self, m):
        k, out = self.checks, []
        add = lambda a: a and out.append(a)
        add(k["cpu"].update(m["cpu_pct"] > k["cpu"].threshold, m["cpu_pct"],
                            f"CPU {m['cpu_pct']} % > {k['cpu'].threshold:g} % depuis {k['cpu'].hold_s:g} s"))
        add(k["mem"].update(m["mem_pct"] > k["mem"].threshold, m["mem_pct"],
                            f"RAM {m['mem_pct']} % > {k['mem'].threshold:g} %"))
        if m["temp_c"] is not None:
            add(k["temp"].update(m["temp_c"] > k["temp"].threshold, m["temp_c"],
                                 f"Température {m['temp_c']} °C > {k['temp'].threshold:g} °C"))
        if m["throttled"] is not None:
            add(k["throttled"].update(m["throttled"] != "0x0", m["throttled"],
                                      f"Alimentation / bridage : throttled={m['throttled']}"))
        add(k["disk"].update(m["disk_pct"] > k["disk"].threshold, m["disk_pct"],
                             f"Disque / {m['disk_pct']} % > {k['disk'].threshold:g} %"))
        j, rot = m["logs"]["journald_mb"], m["logs"]["docker_rotation_ok"]
        if j is not None:
            bad = j > k["logs"].threshold or rot is False
            add(k["logs"].update(bad, j, f"Logs : journald {j} Mo (seuil {k['logs'].threshold:g} Mo)"
                                 + ("" if rot is not False else ", rotation Docker absente sur un conteneur")))
        add(k["docker"].update(m["containers"] is None, None, "Docker injoignable (docker ps a échoué)"))
        for c in m["containers"] or []:
            out.extend(self._eval_container(c))
        return out

    def _eval_container(self, c):
        name, t = c["name"], time.monotonic()
        chk = self.container_checks.setdefault(
            name, Check(f"container:{name}", f"running, non unhealthy, < {self.c['MONITOR_RESTARTS_MAX']} redémarrages"))
        hist = self.restart_hist.setdefault(name, [])
        hist.append((t, c["restarts"]))
        window = float(self.c["MONITOR_RESTARTS_WINDOW"])
        while hist and t - hist[0][0] > window:
            hist.pop(0)
        loop = hist[-1][1] - hist[0][1] >= int(self.c["MONITOR_RESTARTS_MAX"])
        bad = c["state"] != "running" or c["health"] == "unhealthy" or loop
        why = (f"état {c['state']}" if c["state"] != "running" else
               "unhealthy" if c["health"] == "unhealthy" else
               f"redémarrages en boucle ({hist[-1][1] - hist[0][1]} en {window:g} s)")
        a = chk.update(bad, c["state"], f"Conteneur {name} : {why}")
        return [a] if a else []

    def cycle(self):
        m = self.measure()
        self.cli.publish(self.t_system, json.dumps(m, ensure_ascii=False), qos=0, retain=True)
        for a in self.evaluate(m):
            self._publish_alert(a)
        return m

    def run(self, once=False):
        self.cli.connect_async(self.c["MONITOR_HOST"], int(self.c["MONITOR_PORT"]), keepalive=60)
        self.cli.loop_start()
        if not self.connected.wait(20):
            print("MQTT : pas de connexion après 20 s, nouvel essai en arrière-plan", flush=True)
            if once:
                sys.exit(1)
        if once:
            time.sleep(min(12.0, float(self.c["MONITOR_INTERVAL"])))   # laisse arriver $SYS (10 s)
            print(json.dumps(self.cycle(), ensure_ascii=False, indent=1), flush=True)
            time.sleep(1)
            self.cli.disconnect()   # déconnexion propre : pas de testament
            self.cli.loop_stop()
            return
        interval = float(self.c["MONITOR_INTERVAL"])
        while True:
            start = time.monotonic()
            try:
                self.cycle()
            except Exception as e:      # une mesure en échec ne doit pas tuer l'agent
                print(f"Erreur de cycle : {e!r}", flush=True)
            time.sleep(max(1.0, interval - (time.monotonic() - start)))


def main():
    ap = argparse.ArgumentParser(description="Agent de supervision Sentinel-X")
    ap.add_argument("--env", default=os.path.join(REPO, ".env"))
    ap.add_argument("--once", action="store_true", help="un seul cycle puis sortie (tests)")
    args = ap.parse_args()
    Monitor(load_env(args.env), once=args.once).run(once=args.once)


if __name__ == "__main__":
    main()
