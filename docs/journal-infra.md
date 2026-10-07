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

## 2026-10-06 — MQTTS : listener 8883 en TLS

### Certificats (`infra/mosquitto/certs/`, non versionné)

Générés sur le PC de l'admin (la CA et `ca.key` n'y quittent pas), copiés sur le Pi : `ca.crt`, `server.crt` (644) et `server.key` (**600, 1883:1883**). `server.key` n'est jamais affiché.

```
openssl verify -CAfile ca.crt server.crt
openssl x509 -in server.crt -noout -subject -issuer -dates -ext subjectAltName,extendedKeyUsage,keyUsage
openssl x509 -in server.crt -noout -pubkey | openssl sha256
sudo openssl pkey -in server.key -pubout | openssl sha256     # lancé par l'admin (clé lisible par 1883 seulement)
```

| Contrôle | Résultat |
|---|---|
| Chaîne | ✅ `server.crt: OK`, émis par `CN=Sentinel-X CA G10` |
| Sujet / SAN | ✅ `CN=sentinel.local` ; `IP:192.168.10.10`, `IP:192.168.41.123`, `DNS:sentinel.local` |
| Validité | ✅ serveur et CA : du 2026-10-06 au 2027-10-06 |
| Usages | ✅ `TLS Web Server Authentication` ; `Digital Signature, Key Encipherment` |
| Clé ↔ certificat | ✅ empreintes SHA-256 de la clé publique identiques (`6620e431…5f471238`) |
| Git | ✅ `infra/mosquitto/certs/` ignoré (`git check-ignore`) |

`IP:192.168.41.123` (IP DHCP actuelle d'eth0) a été ajoutée au SAN pour pouvoir tester le TLS avant le passage en IP fixe.

### Configuration

- `mosquitto.conf` : `listener 8883` + `cafile` / `certfile` / `keyfile` dans `/mosquitto/certs/`, `tls_version tlsv1.2` (= **minimum** TLS 1.2 en Mosquitto 2.0, TLS 1.3 accepté), `require_certificate false` (authentification par login/mot de passe dans le tunnel TLS, pas de certificat client sur l'ESP).
- Authentification et ACL **communes** aux deux listeners grâce à `per_listener_settings false` (rien à dupliquer).
- `docker-compose.yml` : port `192.168.41.123:8883:8883` publié, `./infra/mosquitto/certs:/mosquitto/certs:ro` monté en lecture seule.
- **Listener 1883 conservé temporairement** (décision de l'admin) jusqu'à validation du TLS sur l'ESP par DEV ; commentaires TEMPORAIRE mis à jour dans les deux fichiers.

```
docker compose up -d     # recrée uniquement mosquitto
```

Logs : `Opening ipv4 listen socket on port 8883` puis `1883`, `mosquitto version 2.0.22 running`, sans erreur (la clé en 600 est bien lue par l'utilisateur 1883). Mémoire : `2.3MiB / 128MiB`.

### Tests TLS

```
openssl s_client -connect 192.168.41.123:8883 -CAfile infra/mosquitto/certs/ca.crt -verify_ip 192.168.41.123
```

| Test | Attendu | Résultat |
|---|---|---|
| `s_client` avec `ca.crt` (+ vérification de l'IP dans le SAN) | `Verify return code: 0` | ✅ `0 (ok)`, TLSv1.3, `TLS_AES_256_GCM_SHA384` |
| `s_client -tls1_2` | accepté | ✅ TLSv1.2, `ECDHE-RSA-AES256-GCM-SHA384`, `0 (ok)` |
| `s_client -tls1_1` (client forcé en `@SECLEVEL=0`) | refusé par le serveur | ✅ `tlsv1 alert protocol version` (alerte 70) |
| `s_client` sans `ca.crt` | non approuvé | ✅ `Verify return code: 19` |
| MQTTS : pub `sentinel` avec login + `--cafile`, sub `backend` | message reçu | ✅ `sentinel/1/telemetry {"temp":23.1,"hum":40}` |
| MQTTS : pub sans login | refusé | ✅ `Connection Refused: not authorised` (rc=5) |
| MQTTS : pub sans la CA | refusé côté client | ✅ `Protocol error` (rc=14) |

Sans `@SECLEVEL=0`, c'est le client OpenSSL 3 du Pi qui refuse TLS 1.1 (`no protocols available`) : ce premier test ne prouvait rien sur le serveur, d'où le second.

Tests MQTT lancés dans un conteneur jetable `eclipse-mosquitto:2.0.22` (`--network host --cap-drop ALL`, `ca.crt` monté en lecture seule, identifiants passés par `--env-file .env`, jamais affichés).

**À transmettre à DEV (ESP8266)** : `ca.crt` uniquement (certificat public, aucun secret), port 8883, hôte `192.168.10.10` ou `sentinel.local` ; l'ESP doit avoir l'heure (NTP) pour valider le certificat.

### Correction : logs Mosquitto

L'entrée « `/mosquitto/log` en volume anonyme » était erronée : `log_dest stdout` envoie les logs au driver Docker `json-file` (rotation 10 Mo × 3 via `daemon.json`, consultation par `docker compose logs mosquitto`). Le volume anonyme vient de la directive `VOLUME` de l'image et reste vide. Pour le monitoring : taille de `docker inspect -f '{{.LogPath}}' sentinel-mosquitto-1` (lecture root).

#### Incident : TLS absent après `git reset --hard origin/main`

La branche `infra/mqtts` n'était pas encore fusionnée : le reset a remis la version 1883 seule (Mosquitto recréé sans 8883). Après fusion de la PR #2 (`db7d224`) et `git pull` : `192.168.41.123:8883` de nouveau actif, `openssl s_client` → TLSv1.3, `Verify return code: 0 (ok)`. Leçon : vérifier `git log origin/main` avant un reset.

## 2026-10-06 — Point d'accès Wi-Fi isolé de la table

Pas de routeur disponible : le Pi devient l'AP de la table sur wlan0 (`192.168.10.10/24`). eth0 (`192.168.41.123`, session SSH d'admin) n'est jamais modifié. SSID et mot de passe : uniquement dans `.env` (`WIFI_AP_SSID`, `WIFI_AP_PSK`, non versionné) et dans le profil NetworkManager (`/etc/NetworkManager/system-connections/sentinel-ap.nmconnection`, root 600 : `nmcli con add` crée un keyfile, pas un fichier netplan) ; jamais dans le dépôt.

### État des lieux

| Élément | Constat |
|---|---|
| NetworkManager | 1.52.1, connexions existantes stockées via netplan (`/etc/netplan/90-NM-*.yaml`, root 600) ; un profil créé par `nmcli con add` est un keyfile dans `/etc/NetworkManager/system-connections/` |
| `ipv4.shared-dhcp-range` | ✅ supporté ; `ipv4.forwarding` (par connexion) : ❌ absent de la 1.52 |
| wlan0 | client du Wi-Fi de l'école (`netplan-wlan0-myDiL`, `192.168.41.70/24`, 2ᵉ route par défaut metric 600) ; mode AP supporté (`iw list`) |
| Pays Wi-Fi | ✅ `iw reg get` → `country FR: DFS-ETSI` (`cfg80211.ieee80211_regdom=FR` dans cmdline) |
| `ip_forward` | `1` (requis par Docker, conservé) ; `ip_nonlocal_bind = 0` |
| Pare-feu | Docker 29.8.2, backend iptables-nft ; `FORWARD` IPv4 en `policy drop`, IPv6 en `policy accept` ; `masquerade` uniquement pour `172.17.0.0/16` et `172.19.0.0/16` (Docker) ; table `ip raw` de Docker (anti-accès direct aux conteneurs) ; `nftables.service` désactivé ; UFW non installé |
| dnsmasq | `dnsmasq-base` présent (utilisé par le mode `shared`) ; avahi actif (`sentinel.local`) |

Sauvegarde des règles avant modification : `sudo nft list ruleset > ~/nft-avant-ap.txt`.

### Choix (validés par l'admin)

- **AP NetworkManager** `ipv4.method shared`, 2,4 GHz (`band bg`), canal 6 (à ajuster selon les tables voisines), **WPA2-PSK seul** (`proto rsn`, CCMP) car l'ESP8266 ne gère pas WPA3, **PMF désactivé** (non géré par l'ESP8266), **`ap-isolation yes`** (les clients ne se voient pas entre eux : limite le MitM ARP au pentest), IPv6 désactivé, DHCP limité à `192.168.10.100`–`.199` (ESP en IP fixe `.21` / `.22`).
- **Aucun routage ni NAT** : le mode `shared` ajoute normalement un `masquerade` et des règles de forwarding → `firewall-backend=none` (`infra/network/nm-90-sentinel.conf`). `ip_forward` n'est **pas** coupé (Docker en a besoin).
- **dnsmasq en DHCP seul** (`infra/network/dnsmasq-sentinel-ap.conf`) : `port=0` (pas de DNS : pas de tunnel DNS vers internet), pas de passerelle ni de DNS annoncés (un PC d'admin garde son internet par son autre interface).
- **Isolation nftables** dans une table dédiée `inet sentinel_isolation` (`infra/network/isolation.nft`) : en `prerouting` (priorité raw, avant le DNAT Docker), tout paquet venant de wlan0 vers une destination hors `192.168.10.0/24` (et IPv6) est rejeté, ce qui bloque aussi l'accès aux IP du Pi côté école (SSH, 1883) ; en `forward`, `wlan0 → eth0/wlan0` et `eth0 → wlan0` rejetés. `wlan0 → br-*` (DNAT vers Mosquitto 8883) reste permis. Défense en profondeur : indépendante de la politique `FORWARD` de Docker et couvre IPv6.
- Chargement au boot par `sentinel-isolation.service` (avant `network-pre.target`). **Pas** `nftables.service` : `/etc/nftables.conf` commence par `flush ruleset` et effacerait les règles de Docker.
- **Mosquitto sur `192.168.10.10:8883`** : Docker démarre avant l'AP et échoue sans réessayer (`cannot assign requested address`) → `net.ipv4.ip_nonlocal_bind=1` (`infra/network/sysctl-90-sentinel.conf`). Risque accepté (un processus local peut se lier à une IP absente) → matrice de sécurité. Le 1883 temporaire n'est **pas** publié sur le Wi-Fi.
- Wi-Fi de l'école : autoconnect désactivé, profil **conservé** (retour arrière).
- Mot de passe généré sur le Pi (24 caractères alphanumériques, ~143 bits) : `tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24`, écrit directement dans `.env` sans affichage. Il transite brièvement en argument de `nmcli` (visible par `ps` pendant l'exécution) : risque faible (seuls `sentinel` et root sur le Pi) → matrice de sécurité.

### Application (commandes lancées par l'admin)

- Bloc A (contrôle) : sauvegarde du ruleset, `sudo nft -c -f infra/network/isolation.nft` → syntaxe OK.
- Bloc B : `sentinel-isolation.service` installé, `enabled` (lien dans `sysinit.target.wants`) et `active` ; `nft list table inet sentinel_isolation` conforme ; `dnsmasq-shared.d/sentinel-ap.conf` installé ; `net.ipv4.ip_nonlocal_bind = 1`.
  - **Problème** : le fichier NetworkManager a été installé sous un nom tronqué, `/etc/NetworkManager/conf.d/90-sent`. NetworkManager ne lit que les fichiers `*.conf` de `conf.d/` → `firewall-backend=none` non pris en compte (le mode `shared` aurait ajouté un NAT vers eth0). Corrigé avant la création de l'AP (`--print-config` → `firewall-backend=none`) :
    ```
    sudo mv /etc/NetworkManager/conf.d/90-sent /etc/NetworkManager/conf.d/90-sentinel.conf
    sudo systemctl reload NetworkManager
    sudo NetworkManager --print-config | grep firewall-backend
    ```
  - Remarque : dès le chargement de l'isolation, wlan0 encore client du Wi-Fi de l'école ne reçoit plus rien (destinations hors `192.168.10.0/24` rejetées en entrée de wlan0) ; sans effet sur SSH (eth0).
- Blocs C et D : profil `sentinel-ap` créé (`autoconnect no` en attendant les tests), Wi-Fi de l'école désactivé (`autoconnect no`, profil conservé, persisté dans son fichier netplan), `nmcli con up sentinel-ap`.
  - `iw dev wlan0 info` → `type AP`, `channel 6 (2437 MHz), width: 20 MHz` ; `nmcli dev status` → `wlan0 connected sentinel-ap`, eth0 inchangé ; `ip -br addr` → `wlan0 192.168.10.10/24`.
  - `nmcli con show sentinel-ap` : `band bg`, `ap-isolation 1 (true)`, `key-mgmt wpa-psk`, `proto rsn`, `pairwise/group ccmp`, `pmf 1 (disable)`, `ipv4.method shared`, `shared-dhcp-range 192.168.10.100,192.168.10.199`, `ipv6.method disabled`.
  - dnsmasq lancé par NetworkManager sous `nobody`, `--listen-address=192.168.10.10 --dhcp-range=192.168.10.100,192.168.10.199,3600`, `--conf-dir=/etc/NetworkManager/dnsmasq-shared.d` ; `ss` : UDP 67 seul, **rien sur le port 53** (`port=0` effectif).
  - Routes : une seule route par défaut (eth0) ; `192.168.10.0/24 dev wlan0` ; la 2ᵉ route par défaut via le Wi-Fi de l'école a disparu.
  - Depuis le Pi : `openssl s_client -connect 192.168.10.10:8883 -verify_ip 192.168.10.10` → TLSv1.3, `Verify return code: 0 (ok)`.
- **Incident : NAT ajouté par NetworkManager malgré `firewall-backend=none`.** `sudo nft list ruleset | grep masquerade` montre, en plus des 2 règles Docker, `ip saddr 192.168.10.0/24 ip daddr != 192.168.10.0/24 masquerade` dans une table `ip nm-shared-wlan0` :
  ```
  table ip nm-shared-wlan0 {
    chain nat_postrouting { ... ip saddr 192.168.10.0/24 ip daddr != 192.168.10.0/24 masquerade }
    chain filter_forward  { ... ip saddr 192.168.10.0/24 iifname "wlan0" accept ; iifname "wlan0" oifname "wlan0" accept ; ... reject }
  }
  ```
  - Cause : `systemctl reload NetworkManager` n'a pas appliqué `firewall-backend` au démon en cours ; `NetworkManager --print-config` relit les fichiers, pas l'état du démon. Le démon était donc encore en détection automatique lors du `nmcli con up sentinel-ap`.
  - Impact : **isolation maintenue**. Un `accept` dans une table n'annule pas un `drop` d'une autre : `sentinel_isolation` rejette déjà en `prerouting` (priorité raw, avant tout NAT) tout ce qui vient de wlan0 hors `192.168.10.0/24`, et en `forward` (priorité -10, avant `filter_forward`) `wlan0 → eth0`. La chaîne `FORWARD` IPv4 de Docker est en plus en `policy drop`. La défense en profondeur a joué son rôle.
  - Correction retenue : redémarrage (NetworkManager démarre avec `firewall-backend=none`, les règles nft non persistantes disparaissent) plutôt qu'un `systemctl restart NetworkManager` à chaud, qui gère aussi eth0 (risque de coupure SSH). Vérification après redémarrage : `sudo nft list tables` sans `nm-shared-wlan0`.
- **Incident : route parasite.** Une commande destinée au **client** de test (`ip route add 192.168.41.0/24 via 192.168.10.10`, pour forcer le passage par le Pi) a été lancée par erreur sur le Pi : elle détournait le réseau de l'école vers wlan0. Supprimée par l'admin ; `ip route` vérifié propre (une seule route par défaut via eth0, `192.168.41.0/24 dev eth0`, `192.168.10.0/24 dev wlan0`). Leçon : préfixer les commandes destinées au client par l'hôte où les lancer.
- Contrôles après incident : `ip route get 192.168.41.52` → `dev eth0 src 192.168.41.123` ✅ ; `openssl s_client` sur `192.168.10.10:8883` et `192.168.41.123:8883` → TLSv1.3, `Verify return code: 0 (ok)` ✅ ; 3 conteneurs actifs, db `healthy`.
- Mosquitto recréé (`docker compose up -d mosquitto`) : publie `192.168.10.10:8883` **avant** que l'IP existe (`ss -ltn` → `LISTEN 192.168.10.10:8883`), grâce à `ip_nonlocal_bind` ; `192.168.41.123:8883` → `Verify return code: 0 (ok)`.

- Bloc E : `sudo nmcli con modify sentinel-ap connection.autoconnect yes`, puis `sudo reboot` (redémarrage de contrôle, qui corrige aussi la table `nm-shared-wlan0`).

### Vérification après redémarrage (démarrage 15:21:19)

| Contrôle | Résultat |
|---|---|
| Tables nft (`sudo nft list tables`) | ✅ `inet sentinel_isolation` + tables Docker, **plus de `nm-shared-wlan0`** |
| `masquerade` | ✅ uniquement `172.17.0.0/16` et `172.19.0.0/16` (Docker), rien pour `192.168.10.0/24` |
| Ordre de démarrage | ✅ `sentinel-isolation` 15:21:22 → `NetworkManager` 15:21:27 → `docker` 15:21:38 |
| AP | ✅ `type AP`, canal 6, 20 MHz ; `wlan0 connected sentinel-ap` (autoconnect `yes`) ; dnsmasq actif |
| Routes | ✅ une seule route par défaut (eth0), pas de route parasite ; `ip route get 192.168.41.52` → `dev eth0` |
| sysctl | ✅ `ip_nonlocal_bind = 1`, `ip_forward = 1` (Docker) |
| Conteneurs | ✅ 3 actifs, db `healthy` ; Mosquitto publie `192.168.10.10:8883`, `192.168.41.123:8883`, `192.168.41.123:1883` ; limites 128M / 64M / 512M |
| MQTTS | ✅ `openssl s_client` sur `192.168.10.10:8883` et `192.168.41.123:8883` → `Verify return code: 0 (ok)` |
| Alimentation | ✅ `throttled=0x0`, `57.1'C` |

Reste à faire côté client (admin) : connexion d'un téléphone/PC au Wi-Fi, bail dans `.100`–`.199` sans passerelle ni DNS, `s_client` sur `192.168.10.10:8883`, 1883 injoignable, échec vers le réseau de l'école, `192.168.41.123:22` et internet (avec routes forcées **sur le client** via `192.168.10.10`).

### Retour arrière

```
sudo nmcli con down sentinel-ap; sudo nmcli con modify sentinel-ap connection.autoconnect no
sudo nmcli con modify netplan-wlan0-myDiL connection.autoconnect yes; sudo nmcli con up netplan-wlan0-myDiL
sudo systemctl disable --now sentinel-isolation; sudo nft delete table inet sentinel_isolation
sudo rm /etc/NetworkManager/conf.d/90-sentinel.conf /etc/NetworkManager/dnsmasq-shared.d/sentinel-ap.conf /etc/sysctl.d/90-sentinel.conf
sudo systemctl reload NetworkManager; sudo sysctl -w net.ipv4.ip_nonlocal_bind=0
```

## 2026-10-06 — Serveur NTP local (chrony) pour les ESP

Le Wi-Fi de la table n'a pas internet ; sans heure valide, l'ESP8266 refuse le certificat du broker (`notBefore` = 2026-10-06 09:58:54 UTC = `1791280734`).

### État des lieux

- `systemd-timesyncd` actif (pool Debian) ; chrony absent (candidat `4.6.1-3+deb13u2`, dépôt Debian) ; aucun autre démon de temps.
- DHCP de l'école : **pas de serveur NTP fourni** (`requested_ntp_servers` sans réponse ; DNS 8.8.8.8 / 8.8.4.4 seulement).
- RTC intégrée du Pi 5 (`/dev/rtc0`, `rpi-rtc`, `hctosys=1` : heure système fixée par la RTC au boot). **Pas de pile sur J5** ; `charging_voltage=0` (charge désactivée).
- NTS (TCP 4460) joignable depuis eth0 : `time.cloudflare.com`, `ptbtime1.ptb.de` ✅ ; `nts.netnod.se` ❌.
- 123/udp wlan0 → 192.168.10.10 : autorisé (`sentinel_isolation` ne filtre que les destinations hors `192.168.10.0/24`, pas de chaîne `input`). À ouvrir dans UFW plus tard.

### Configuration (`infra/ntp/chrony.conf` → `/etc/chrony/chrony.conf`)

- Amont via eth0 : 2 serveurs **NTS** (NTP authentifié, contre la falsification de l'heure depuis le réseau de l'école) + repli `2.debian.pool.ntp.org` en `authselectmode mix` + `sourcedir /run/chrony-dhcp` (NTP du DHCP si l'école en fournit un).
- Sans pile : `nocerttimecheck 1` (1ʳᵉ synchro NTS possible avec une horloge fausse), `makestep 1 -1` (saut autorisé à tout moment, ex. eth0 branché après le boot), `rtcsync`.
- Service : `bindaddress 192.168.10.10` (grâce à `ip_nonlocal_bind=1`), `allow 192.168.10.0/24`, `local stratum 10` (heure servie sans internet), `ratelimit interval 3 burst 8 leak 2` (DoS).
- `cmdport 0` : pas de port de commande réseau ; `chronyc` via le socket Unix (root / `_chrony` uniquement).

```
sudo apt-get install --no-install-recommends chrony      # retire systemd-timesyncd (conflit time-daemon)
sudo cp -p /etc/chrony/chrony.conf /etc/chrony/chrony.conf.debian
sudo install -m 644 infra/ntp/chrony.conf /etc/chrony/chrony.conf
sudo chronyd -p -f /etc/chrony/chrony.conf >/dev/null    # syntaxe OK
sudo systemctl restart chrony                            # active
```

- Avertissement `dpkg-statoverride: /var/log/chrony does not exist` : sans effet (aucune directive `log`, journal système).
- apt signale `chromium-sandbox` devenu inutile : à retirer au hardening (installation minimale avant le pentest).
- Retour arrière : `sudo apt-get purge chrony && sudo apt-get install systemd-timesyncd`.

### Tests

| Test | Résultat |
|---|---|
| `ss -ulpn` | ✅ `192.168.10.10:123` seul ; rien sur `192.168.41.123`, pas de 323 |
| `chronyc` sans sudo | ✅ `506 Cannot talk to daemon` (pas d'accès réseau ni non-root au contrôle) |
| Requête NTP vers 192.168.10.10 < 1 min après le restart | ✅ `stratum 10`, refid `127.127.1.1` (`local stratum 10` actif avant synchro) |
| Même requête ~1 min plus tard | ✅ `stratum 4`, refid `162.159.200.123` |
| `sudo chronyc tracking` | ✅ stratum 4, `System time 0.000001206 s slow`, `Leap status : Normal` |
| `sudo chronyc sources` | ✅ `^*` 162.159.200.123 (Cloudflare NTS), `^-` 192.53.103.108 (PTB NTS) ; sources du pool en `^?` (non sélectionnées : non authentifiées) |
| `sudo chronyc -N authdata` | ✅ `time.cloudflare.com` et `ptbtime1.ptb.de` en mode `NTS`, 0 NAK, cookies 8 et 7 |
| Client Windows du Wi-Fi : `w32tm /stripchart /computer:192.168.10.10 /dataonly /samples:5` | ✅ 5/5 réponses, écart stable −24 à −29 ms (horloge du PC) |

## 2026-10-06 — Heure sans pile RTC : fake-hwclock (système autonome, sans eth0 à la démo)

Contrainte : le Pi doit fonctionner **sans câble Ethernet** le jour de la démo, y compris après extinction / rallumage. Pas de pile sur J5 : après une coupure d'alimentation, la RTC du Pi 5 perd l'heure → sans eth0, chrony servirait une heure fausse et l'ESP refuserait le certificat (`notBefore` 2026-10-06 09:58:54 UTC).

### Installation

```
sudo apt-get install --no-install-recommends fake-hwclock     # 0.14, Debian, aucune dépendance, rien de supprimé
sudo fake-hwclock save                                         # /etc/fake-hwclock.data : 2026-10-06 14:05:16 (UTC)
```

Unités créées : `fake-hwclock-load.service` (sysinit, avant `systemd-fsck-root`), `fake-hwclock-save.service` (arrêt), `fake-hwclock-save.timer` (horaire, timer systemd et non cron). `fake-hwclock` (ancien script init) est `masked` : normal.

### Problème : fake-hwclock 0.14 fait reculer l'horloge

Le manuel indique que `load` sans `force` n'avance que l'horloge. Le script (`/usr/sbin/fake-hwclock`) fait l'inverse : `FORCE=false` puis `if [ "$FORCE"x = "false"x ] || [ $NOW_SEC -le $SAVED_SEC ]; then date -u -s "$SAVED"` → sans `force`, l'heure est **toujours** remplacée par la sauvegarde, même plus ancienne. Au boot à chaud (RTC exacte), l'heure aurait reculé de quelques secondes (arrêt propre) à 1 h (plantage, dernière sauvegarde horaire).

Correction : drop-in `infra/ntp/fake-hwclock-load-forward.conf` → `/etc/systemd/system/fake-hwclock-load.service.d/forward-only.conf`, qui remplace la commande par un chargement **qui n'avance que** l'horloge, indépendant du bug (et d'une future correction où `force` signifierait « avant ou arrière »).

```
sudo install -D -m 644 infra/ntp/fake-hwclock-load-forward.conf /etc/systemd/system/fake-hwclock-load.service.d/forward-only.conf
sudo systemctl daemon-reload
sudo systemctl start fake-hwclock-load.service
```

Test à chaud : `date -u` avant/après = `14:07:03` / `14:07:03`, journal : `fake-hwclock: horloge déjà plus récente que la sauvegarde, inchangée` ✅. **Ne jamais lancer `sudo fake-hwclock load` à la main.**

- `rtcsync` (chrony) déjà actif : la RTC est recopiée depuis l'heure système tant que le Pi est synchronisé.
- Avant une coupure volontaire : `sudo poweroff` (sauvegarde à l'arrêt), sinon jusqu'à 1 h de retard.

### Reste à faire

- [x] Activer le cgroup mémoire (`cgroup_enable=memory`, sudo + reboot) et vérifier les limites.
- [x] PKI : listener 8883/TLS en place et testé.
- [ ] Supprimer le listener 1883 (conf + compose) dès que DEV a validé le TLS sur l'ESP, avant le pentest de jeudi.
- [ ] Remettre `ca.crt` à DEV ; proposer un serveur NTP local si le réseau de la table n'a pas d'internet.
- [x] Point d'accès Wi-Fi isolé (blocs A à E, redémarrage de contrôle).
- [ ] Tests depuis un client Wi-Fi (bail DHCP, 8883, isolation vers l'école et internet).
- [ ] Matrice de sécurité : `ip_nonlocal_bind=1`, PSK transitoire en argument de `nmcli`, groupe `docker`, `makestep 1 -1` (saut forgé possible si seul le pool non authentifié répond), pas de pile RTC.
- [x] Heure sans pile RTC : fake-hwclock installé, chargement « avance seulement » (drop-in).
- [ ] Test autonome : démarrage à froid sans eth0 (heure, AP, conteneurs, MQTTS, NTP).
- [ ] Hardening SSH : autoriser 22/tcp sur wlan0 depuis 192.168.10.100–199 uniquement (eth0 absent à la démo) ; garder l'accès eth0 hors démo.
- [ ] Pile RTC officielle (ML-2020) si achetable : heure exacte sans réseau.
- [ ] UFW : autoriser `123/udp` sur wlan0 vers 192.168.10.10 (NTP).
- [ ] Hardening : `apt autoremove` (`chromium-sandbox`).
- [ ] UFW : autoriser le DHCP sur wlan0 (`udp/67`), NetworkManager ne le fait plus (`firewall-backend=none`).
- [x] `.gitignore` : `*.csr`, `*.srl`, `pki/`, `infra/mosquitto/certs/`, `infra/mosquitto/data/`, `infra/mosquitto/log/` couverts (`git check-ignore`).
- [ ] Hardening UFW / SSH, monitoring.
