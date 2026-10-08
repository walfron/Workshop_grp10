# Procédure d'intégration de la pile (Pi autonome au démarrage)

Statut : **préparé, non appliqué** (branche `infra/integration`, 2026-10-08). À appliquer **après le pentest**.
Toutes les commandes se lancent dans `~/Workshop_grp10` (dossier de production), sauf mention contraire.

## 0. Prérequis (bloquants)

| # | Prérequis | Qui |
|---|---|---|
| P1 | **ESP en MQTTS 8883** validé (`ca.crt`, heure NTP) : le 1883 ne sera plus publié | DEV |
| P2 | ESP : publie l'état des actionneurs sur `sentinel/<id>/state` (ACL ajoutée) ; préfixe `sentinel/g10` attendu par le backend | DEV |
| P3 | Script IA poussé dans `IA/` : MQTTS `192.168.10.10:8883` + `ca.crt`, compte `ia`, topic `sentinel/+/telemetry` (et non `sentinel/sensors/data`), variables lues dans l'environnement (`infra/ia/ia.env.example`), aucun mot de passe en dur | IA |
| P4 | Script IA : alertes au format de l'API : `{"level": "info"\|"warning"\|"critical", "message": "...", "source": "ia"}` + en-tête `X-API-Key`, vers `http://127.0.0.1:3000/api/v1/alerts` (aujourd'hui : `127.0.0.1:8000`, champs `severity` / `type` / `details` → **rejet 400**) | IA |
| P5 | PR `infra/integration` fusionnée dans `main` ; `Dockerfile` validé par DEV | Admin, DEV |

## 1. Sauvegarde (point de retour)

```bash
git rev-parse HEAD > ~/avant-integration.commit     # commit actuel de la prod
install -m 600 .env ~/.env.avant-integration         # .env actuel
docker compose ps > ~/avant-integration.ps
```

## 2. Récupération et secrets

```bash
git pull                                             # hook post-merge : acl 640 1883:1883 + SIGHUP Mosquitto
openssl rand -base64 24 | tr '+/' '-_'               # -> API_KEY
docker run --rm -it caddy:2.10.2-alpine caddy hash-password   # -> DASHBOARD_PASSWORD_HASH
nano .env      # ajouter API_KEY, DASHBOARD_USER, DASHBOARD_PASSWORD_HASH='...' (apostrophes)
               # retirer POSTGRES_USER, POSTGRES_DB, DB_PASSWORD
docker compose config --quiet && echo CONFIG_OK      # ne rien afficher d'autre (secrets)
```
Transmettre `API_KEY` à l'IA (hors Git), et l'identifiant / mot de passe du dashboard à l'équipe.

## 3. Build de l'image API

```bash
docker compose build api            # Vite + npm ci : quelques minutes, ~1 Go de RAM pendant le build
docker image ls sentinel-api:local
```

## 4. Redémarrage de la pile (coupure MQTT ~1 min)

Les réseaux changent (`mqtt` devient interne) : Compose doit les recréer.
```bash
docker compose down                 # SANS -v : volumes conservés
docker compose up -d --remove-orphans
docker compose ps                   # mosquitto Up, api et caddy (healthy)
ss -tln | grep -E ':(443|1883|8883|3000) '
```
Attendu : `192.168.10.10:443`, `192.168.41.123:443`, `127.0.0.1:3000`, `8883` ×2, **aucun 1883**.

## 5. Pare-feu (sudo)

```bash
sudo install -m 755 infra/hardening/docker-user-mqtt.sh /usr/local/sbin/
sudo install -m 644 infra/hardening/sentinel-docker-user.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart sentinel-docker-user
sudo iptables -L DOCKER-USER -n --line-numbers      # 3 sauts : 443, 8883, 1883
sudo ufw allow in on br-sentinel-edge from 172.30.0.0/24 to 172.30.0.1 port 8080 proto tcp comment 'Caddy -> flux webcam'
```

## 6. Service IA (sudo)

```bash
sudo install -o root -g sentinel -m 640 /dev/null /etc/sentinel/ia.env
sudoedit /etc/sentinel/ia.env      # d'après infra/ia/ia.env.example, valeurs du .env
sudo install -m 644 infra/ia/sentinel-ia.service /etc/systemd/system/
sudo systemctl edit sentinel-ia    # [Service] Environment=IA_SCRIPT=/home/sentinel/Workshop_grp10/IA/<script>.py
# arrêter le script lancé à la main (session SSH / tmux de l'IA), puis :
sudo systemctl daemon-reload && sudo systemctl enable --now sentinel-ia
systemctl status sentinel-ia --no-pager ; journalctl -u sentinel-ia -n 30 --no-pager
systemd-analyze security sentinel-ia | tail -1
```

## 7. Tests

| Test | Attendu |
|---|---|
| `https://192.168.10.10/` (client Wi-Fi) | avertissement si `ca.crt` non installé, puis **demande d'identifiant**, dashboard |
| Sans identifiant : `curl -sk -o /dev/null -w '%{http_code}' https://192.168.10.10/api/v1/health` | `401` |
| Avec identifiant : idem `-u user:mdp` | `200`, `"mqtt":true` |
| Dashboard : mesures en direct (WebSocket `/ws`) | mises à jour sans recharger |
| Webcam dans le dashboard (`/webcam/video_feed`) | image ; pas d'erreur « contenu mixte » |
| Commande buzzer / LED depuis le dashboard | ESP réagit ; `sentinel/g10/state` reçu |
| Alerte IA | apparaît dans le dashboard (`source: ia`) |
| `curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:3000/api/v1/alerts` (sans clé) | `401` |
| `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/api/v1/telemetry` | `404` (seule la route alertes passe) |
| Téléphone hors liste sur eth0 : `https://192.168.41.123/` | timeout ; `SENTINEL-MQTT-DROP DPT=443` dans `journalctl -k` |
| `nmap -Pn -p 1883 192.168.41.123` depuis `.52` | `filtered` / `closed` (plus publié) |
| `nmap --script ssl-enum-ciphers -p 443,8883 192.168.10.10` | TLS 1.2 / 1.3 uniquement |
| `docker stats --no-stream` ; `systemctl show sentinel-ia -p MemoryCurrent` ; `free -h` | sous les limites, marge mémoire |
| `docker exec sentinel-api-1 id` | `uid=10001` |

## 8. Retour arrière

```bash
sudo systemctl disable --now sentinel-ia             # l'IA relance son script à la main
docker compose down
git switch --detach "$(cat ~/avant-integration.commit)"
install -m 600 ~/.env.avant-integration .env
.git/hooks/post-merge                                # droits de l'acl + SIGHUP (le switch ne lance pas le hook)
docker compose up -d --remove-orphans                # ancienne pile (whoami, db, 1883 publié)
```
Le saut DOCKER-USER sur 443 et la règle UFW `br-sentinel-edge` sont sans effet sur l'ancienne pile (peuvent rester).
Revenir ensuite sur `main` : `git switch main`.

## 9. Nettoyage (après validation, avec accord)

- Volume PostgreSQL inutilisé : `docker volume rm sentinel_db-data` (**destructif**).
- Images : `docker image rm traefik/whoami:v1.11.0 postgres:16-alpine`.
- Quand le dashboard passe par `/webcam/` : retirer les 3 règles UFW 8080 directes (`ufw status numbered`, `ufw delete <n>`), et lier Flask à `172.30.0.1` ou garder `0.0.0.0` (UFW).

## 10. Checklist : test d'autonomie à froid, sans eth0

Préparation : eth0 **débranché**, un PC et un téléphone prêts sur le Wi-Fi de la table, ESP alimenté.
Coupure secteur ≥ 10 s, puis rallumage. Chronométrer.

- [ ] Wi-Fi de la table visible < 1 min ; bail DHCP `192.168.10.100–199` sur le PC
- [ ] SSH par clé depuis le PC (`192.168.10.10`, wlan0)
- [ ] Heure correcte : `date`, `chronyc tracking` (fake-hwclock + `local stratum 10`), pas de date 1970 / passée
- [ ] `vcgencmd get_throttled` = `0x0` ; `vcgencmd measure_temp`
- [ ] `docker compose ps` : mosquitto Up, api et caddy `healthy` (ports `192.168.41.123` publiés malgré eth0 absent : `ip_nonlocal_bind`)
- [ ] `systemctl is-active sentinel-isolation sentinel-docker-user ufw chrony sentinel-monitor sentinel-ia` → tous `active`
- [ ] `sudo iptables -L DOCKER-USER -n` : 3 sauts ; `sudo ufw status` : actif
- [ ] ESP connecté en MQTTS (logs Mosquitto : `New client connected ... sentinel`), mesures toutes les N s
- [ ] `https://192.168.10.10/` : identifiant demandé, mesures en direct, webcam, alertes
- [ ] Commande buzzer / LED → ESP ; état remonté
- [ ] Alerte IA (présence devant la webcam) visible dans le dashboard
- [ ] Données système (`sentinel/1/system`) dans la page Serveur
- [ ] Aucun service graphique : `systemctl get-default` = `multi-user.target`, `lightdm` inactif
- [ ] `ss -tuln` : uniquement 22, 67/udp, 123/udp, 443, 8883, 8080, 127.0.0.1:3000
- [ ] `journalctl -b -p err --no-pager` : pas d'erreur bloquante
- [ ] Mémoire après 10 min : `free -h`, `docker stats --no-stream`
- [ ] Rebrancher eth0 : accès SSH `.52` rétabli, `chronyc sources` NTS joignable
