# Journal INFRA — Sentinel-X (G10)

Journal de bord de la filière INFRA/sécurité : commandes lancées, choix techniques, problèmes rencontrés.
Il alimente le schéma réseau, la matrice de sécurité et le rapport d'audit du dossier final.

- Serveur : Raspberry Pi 5 (8 Go), nom d'hôte `sentinel`, embarqué dans le boîtier (Option A)
- Responsable : Anne-Lou Delage-Davies (INFRA)
- Aucun secret dans ce fichier (dépôt public).

---

## 2026-10-06 — État initial du serveur

### Système

```
$ grep PRETTY_NAME /etc/os-release
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"      # Raspberry Pi OS Lite 64 bits
$ uname -r
6.18.50+rpt-rpi-2712
```

- Installé avec Raspberry Pi Imager : utilisateur non-root `sentinel`, SSH par clé publique uniquement.
- Réseau : Ethernet, IP en DHCP pour l'installation (IP fixe 192.168.10.10 prévue, voir `infra/network.md`).
- Heure : `timedatectl` → fuseau Europe/Paris, `System clock synchronized: yes`, service NTP actif.

### Alimentation et température

```
$ vcgencmd get_throttled
throttled=0x0
$ vcgencmd measure_temp
temp=64.8'C
```

- `0x0` : aucune sous-tension ni bridage détecté, l'alimentation est suffisante.
- 64,8 °C au repos, avant le démarrage des conteneurs : à surveiller une fois le Pi dans le boîtier fermé et avec la charge YOLO (le bridage commence vers 80-85 °C). Un dissipateur ou un ventilateur et des aérations dans la CAO sont à prévoir.

### Docker

Installé depuis le dépôt officiel Docker (apt `download.docker.com`) :

```
$ docker --version
Docker version 29.8.2, build 7fc2dff
$ docker compose version
Docker Compose version v5.6.0
containerd.io 2.3.6-1~debian.13~trixie
```

Configuration du démon, `/etc/docker/daemon.json` :

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "no-new-privileges": true,
  "live-restore": true
}
```

Justification :

| Option | Rôle | Pourquoi |
|---|---|---|
| `log-driver: json-file` + `max-size 10m` / `max-file 3` | Rotation des logs des conteneurs (30 Mo max par conteneur) | La carte SD est petite : on évite qu'elle se remplisse (logs MQTT, IA). C'est aussi une protection contre un DoS par saturation des logs. |
| `no-new-privileges: true` | Interdit l'élévation de privilèges (setuid/setgid) dans tous les conteneurs | Limite l'impact d'une compromission d'un conteneur (exigence « daemons Docker avec privilèges isolés »). |
| `live-restore: true` | Les conteneurs continuent de tourner si le démon Docker redémarre | Continuité de la surveillance (MCO) pendant une mise à jour de Docker. |

### Décision : utilisateur `sentinel` dans le groupe `docker`

- Être membre du groupe `docker` revient à avoir les droits root : le socket `/var/run/docker.sock` permet de lancer un conteneur qui monte `/`.
- **Risque accepté** : l'accès au Pi se fait uniquement en SSH par clé (pas de mot de passe), par les postes d'admin. Cela évite d'utiliser `sudo` pour chaque commande Docker.
- Mesures compensatoires : SSH par clé uniquement (en place) ; port 22 limité aux IP d'admin par UFW et socket Docker jamais monté dans un conteneur (prévus).
- → À reporter dans la **matrice de sécurité**.
- Remarque : après l'ajout au groupe, la session SSH ouverte n'avait pas le groupe (`permission denied` sur `docker.sock`). Il faut se déconnecter puis se reconnecter.

### Dépôt Git

- Cloné dans `~/Workshop_grp10`. Le Pi fait uniquement `git pull` (aucun identifiant GitHub dessus).
- Dossiers créés hors Git : `infra/mosquitto/{certs,data,log}`.
- Contrôle `git check-ignore -v` : `.env`, `*.key`, `*.pem` et `infra/mosquitto/passwd` sont ignorés. **Manquants** : `*.csr`, `*.srl`, `pki/`, `infra/mosquitto/certs/`, `infra/mosquitto/data/`, `infra/mosquitto/log/` (à ajouter depuis le PC d'admin).

---

## 2026-10-06 — Stack Docker Compose, Mosquitto (phase intégration) et webcam

### Correction : RAM

`free -h` → `Mem: total 7.9Gi` : le Pi 5 a **8 Go** de RAM (et non 4 Go).

### Réseau constaté

```
$ ip -br addr
eth0   UP  192.168.41.123/24
wlan0  UP  192.168.41.70/24
```

- Le Pi n'est pas encore sur le plan cible 192.168.10.0/24 : **eth0 et wlan0 sont sur le même réseau 192.168.41.0/24** (réseau de la salle). wlan0 est actif : à désactiver plus tard (décision commune avec l'admin).
- **Les ports publiés par Docker contournent UFW** (Docker insère ses propres règles iptables avant celles d'UFW) : un `ports: "1883:1883"` est exposé sur toutes les interfaces même si UFW le bloque. Contre-mesure : lier chaque port publié à une IP précise.

### Exception temporaire : MQTT 1883 en clair

- **Validée explicitement par l'admin** : Mosquitto écoute en 1883 **en clair, avec authentification et ACL**, pour que DEV et IA puissent s'intégrer pendant que la PKI est reportée.
- Port lié à l'IP d'eth0 uniquement : `"192.168.41.123:1883:1883"` (pas d'exposition sur wlan0).
- **La protection actuelle repose uniquement sur l'authentification** : les identifiants et les messages circulent en clair (risque d'écoute/MitM sur le réseau de la salle).
- **À supprimer au passage en TLS (avant jeudi)** : listener 8883 (TLS 1.2 min), port lié à `192.168.10.10:8883:8883`, suppression du listener 1883.
- → À reporter dans la **matrice de sécurité** (risque temporaire accepté, date de fin : passage en TLS).

### Mosquitto (`infra/mosquitto/`)

- `mosquitto.conf` : `allow_anonymous false`, `password_file`, `acl_file`, limites anti-DoS (`max_connections 50`, `max_packet_size 65536`, `max_inflight_messages 20`, `max_queued_messages 1000`), persistance dans `data/`.
- Logs : **stdout uniquement** (`log_dest file` supprimé), `log_type` error/warning/notice/information. La rotation est assurée par Docker (`json-file` 10m × 3, `daemon.json`) → pas de logrotate ni de dossier `log/` (plus monté dans le compose). Consultation : `docker compose logs mosquitto`.
- ACL (`acl`, versionné, sans secret) :

| Compte | Écrit | Lit |
|---|---|---|
| `sentinel` (ESP8266) | `sentinel/+/telemetry`, `sentinel/+/alerts` | `sentinel/+/cmd` |
| `backend` (API/dashboard) | `sentinel/+/cmd` | `sentinel/+/telemetry`, `sentinel/+/alerts` |
| `ia` (YOLO + Isolation Forest) | `sentinel/+/alerts` | `sentinel/+/telemetry` |

- Variables ajoutées : `MQTT_IA_USER` / `MQTT_IA_PASSWORD` (`.env.example` avec valeur factice ; valeur aléatoire dans `.env`, généré par `secrets.token_urlsafe(24)`).

#### Génération du fichier `passwd` (haché, non versionné)

Dans un conteneur jetable, **sans réseau**, sans capabilities ; les mots de passe sont lus dans `.env` et passés par variables d'environnement (jamais affichés) :

```
set -a; . ./.env; set +a; umask 077
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  -e MQTT_USER -e MQTT_PASSWORD ... eclipse-mosquitto:2.0.22 sh -c '
    mosquitto_passwd -c -b /tmp/p "$MQTT_USER" "$MQTT_PASSWORD"; ...; cat /tmp/p' > infra/mosquitto/passwd
chmod 600 infra/mosquitto/passwd
# chown 1883:1883 du passwd et de data/ via un conteneur jetable (--cap-add CHOWN uniquement)
```

- Résultat : 3 comptes (`sentinel`, `backend`, `ia`), hachage PBKDF2-SHA512 (`$7$`), fichier `600 1883:1883`, ignoré par Git (`git check-ignore` OK).
- Les messages `chown: Operation not permitted` au lancement sont normaux : l'entrypoint de l'image tente un chown alors que les capabilities sont retirées.
- `data/` passé en `1883:1883` (sinon Mosquitto, non-root, ne peut pas écrire sa persistance).

### Démarrage de la stack

```
$ docker compose config --quiet && docker compose up -d
$ docker compose ps
sentinel-api-1         traefik/whoami:v1.11.0     Up            127.0.0.1:8080->8080/tcp
sentinel-db-1          postgres:16-alpine         Up (healthy)  5432/tcp
sentinel-mosquitto-1   eclipse-mosquitto:2.0.22   Up            192.168.41.123:1883->1883/tcp
```

- `db` n'a aucun port publié (réseau interne `db`), l'API placeholder n'écoute qu'en local.
- `docker stats --no-stream` : CPU ≈ 0 %, 1 à 6 PIDs par conteneur, mais `MEM USAGE / LIMIT = 0B / 0B`.

#### Problème : limites mémoire ignorées

```
mosquitto Your kernel does not support memory limit capabilities or the cgroup is not mounted. Limitation discarded.
$ cat /proc/cmdline | grep -o 'cgroup[^ ]*'
cgroup_disable=memory
```

- Raspberry Pi OS désactive le contrôleur cgroup mémoire par défaut : **les `memory:` du compose ne sont pas appliqués** (risque : YOLO ou un DoS peut consommer toute la RAM). Les limites CPU et PIDs, elles, fonctionnent.
- Correctif proposé (à valider, nécessite sudo + redémarrage) : ajouter `cgroup_enable=memory` en fin de l'unique ligne de `/boot/firmware/cmdline.txt`, redémarrer, puis vérifier avec `docker stats`.

#### Avertissement Mosquitto sur l'ACL

```
Warning: File /mosquitto/config/acl has world readable permissions. Future versions will refuse to load this file.
Warning: File /mosquitto/config/acl owner is not mosquitto.
```

Sans effet en 2.0.22 (fichier sans secret). À traiter si on monte de version : copie hors Git en `600 1883:1883`.

### Test de bout en bout MQTT

Conteneur jetable `eclipse-mosquitto:2.0.22` (`mosquitto_pub` / `mosquitto_sub`) contre `192.168.41.123:1883`, topic `sentinel/1/telemetry` :

| Test | Attendu | Résultat |
|---|---|---|
| pub `sentinel` avec login, sub `backend` | message reçu | ✅ `sentinel/1/telemetry {"temp":22.5,"hum":41}` |
| pub sans login | refusé | ✅ `Connection Refused: not authorised` (rc=5) |
| pub `sentinel` avec mauvais mot de passe | refusé | ✅ `not authorised` (rc=5) |
| pub `ia` sur `telemetry` (interdit par l'ACL) | ignoré | ✅ rien reçu (`Timed out`) |

### Webcam USB

```
$ lsusb | grep -i logi
Bus 001 Device 003: ID 046d:0825 Logitech, Inc. Webcam C270
$ v4l2-ctl --list-devices
pispbe (platform:1000880000.pisp_be):          /dev/video20 à /dev/video35, /dev/media1, /dev/media2
rpi-hevc-dec (platform:rpi-hevc-dec):          /dev/video19, /dev/media0
Logi C270 HD WebCam: Logi C270 (usb-xhci-hcd.0-2): /dev/video0, /dev/video1, /dev/media3
```

- `v4l-utils` était déjà installé (aucune installation).
- `/dev/video19` à `/dev/video35` appartiennent au SoC (décodeur HEVC et PiSP Backend, le processeur d'image du Pi 5) : **à ne pas utiliser**.
- Webcam (driver `uvcvideo`) :
  - **`/dev/video0` : capture vidéo** → MJPG ou YUYV, 1280x720, 800x600, 640x480, 640x360, 320x240. MJPG conseillé (moins de bande passante USB et de CPU).
  - `/dev/video1` : métadonnées UVC uniquement (pas d'image).
- Chemin stable recommandé pour le conteneur IA (le numéro `videoN` peut changer au rebranchement) :
  `/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._Logi_C270_HD_WebCam_Logi_C270_HD_WebCam-video-index0`
- Droits : `crw-rw---- root:video` (gid 44) → le conteneur IA devra avoir `devices:` sur ce seul périphérique et `group_add: ["44"]`, sans `privileged`.

#### Correctif : droits de l'ACL

```
chmod 640 infra/mosquitto/acl
docker run --rm --network none --cap-drop ALL --cap-add CHOWN --entrypoint chown \
  -v "$PWD/infra/mosquitto/acl:/w/acl" eclipse-mosquitto:2.0.22 1883:1883 /w/acl
docker compose restart mosquitto
```

- `acl` passé en `640 1883:1883` : les avertissements Mosquitto ont disparu (`mosquitto version 2.0.22 running` seul).
- Conséquence : l'utilisateur `sentinel` ne peut plus lire ni modifier ce fichier directement. Un `git pull` qui le met à jour le recrée avec les droits par défaut : il faudra refaire le `chmod`/`chown` après chaque mise à jour de l'ACL.

#### Correctif : activation du cgroup mémoire

- `/boot/firmware/cmdline.txt` ne contient pas `cgroup_disable=memory` : il est ajouté par le firmware/noyau de Raspberry Pi OS. Ajouter `cgroup_enable=memory` en fin de ligne le surcharge.
- Le fichier tient sur **une seule ligne, sans saut de ligne final** (`wc -l` → 0) : il doit le rester.
- `sudo` demande un mot de passe : les commandes sont lancées par l'admin depuis son terminal SSH :

```
sudo cp -p /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
grep -q cgroup_enable=memory /boot/firmware/cmdline.txt || \
  sudo sed -i '1 s/$/ cgroup_enable=memory/' /boot/firmware/cmdline.txt
cat -A /boot/firmware/cmdline.txt; wc -l /boot/firmware/cmdline.txt
sudo reboot
```

- Retour arrière si le Pi ne démarre plus : remettre `cmdline.txt.bak` à la place de `cmdline.txt` en lisant la carte SD depuis un PC.

##### Vérification après redémarrage (2026-10-06)

- `cat /proc/cmdline` : `cgroup_disable=memory` (injecté par le firmware) **puis** `cgroup_enable=memory` en fin de ligne : le second l'emporte.
- `/sys/fs/cgroup/cgroup.controllers` → `cpuset cpu io memory pids` : contrôleur `memory` actif ; plus d'avertissement dans `docker info` (cgroup v2, driver systemd).
- `vcgencmd get_throttled` → `throttled=0x0` ; `vcgencmd measure_temp` → `57.1'C`.

**Problème rencontré** : après le reboot, les 3 conteneurs étaient revenus (db `healthy`), mais `docker stats` affichait encore `7.873GiB` comme limite et `docker inspect` donnait `Memory=0`. Les conteneurs avaient été **créés avant** l'activation du cgroup : Docker avait alors abandonné la limite mémoire à la création, et un simple redémarrage ne la réapplique pas (les limites CPU, elles, étaient bien présentes).

Correction : recréation des conteneurs (données Postgres conservées dans le volume nommé `sentinel_db-data`) :

```
docker compose up -d --force-recreate
docker inspect -f '{{.Name}} Memory={{.HostConfig.Memory}}' $(docker compose ps -q)
```

```
NAME                   CPU %   MEM USAGE / LIMIT
sentinel-api-1         0.00%   2MiB / 64MiB
sentinel-mosquitto-1   0.01%   1.312MiB / 128MiB
sentinel-db-1          0.01%   21.08MiB / 512MiB
```

✅ Limites 64M / 128M / 512M effectives, db `healthy`.

**Re-test MQTT** (même protocole que ci-dessus, identifiants passés au conteneur jetable par `--env-file .env`, jamais affichés) : les 4 cas sont conformes (message reçu avec login ; `not authorised` rc=5 sans login et avec mauvais mot de passe ; publication de `ia` sur `telemetry` ignorée par l'ACL).

### Reste à faire

- [x] Activer le cgroup mémoire (`cgroup_enable=memory`, sudo + reboot) et vérifier les limites.
- [ ] Logs Mosquitto : `/mosquitto/log` est actuellement un volume anonyme Docker (pas de bind sur `infra/mosquitto/log/`) → à corriger pour le monitoring de la taille des logs.
- [ ] PKI : passage en 8883/TLS, suppression de 1883 et de cette exception.
- [ ] IP fixe 192.168.10.10, désactivation de wlan0.
- [ ] `.gitignore` : ajouter `*.csr`, `*.srl`, `pki/`, `infra/mosquitto/certs/`, `infra/mosquitto/data/`, `infra/mosquitto/log/`.
- [ ] Hardening UFW / SSH, monitoring.
