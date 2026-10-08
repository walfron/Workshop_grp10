#!/usr/bin/env bash
# Pare-feu UFW du Pi Sentinel-X (filière INFRA). À lancer avec sudo.
# Filet de sécurité : UFW est désactivé automatiquement au bout de 5 min,
# sauf si l'admin confirme avec :  sudo systemctl stop ufw-deadman.timer
#
# Rappel : les ports publiés par Docker (1883, 8883) passent par FORWARD
# et ne sont PAS filtrés par ces règles (INPUT) : voir chaîne DOCKER-USER.
set -euo pipefail

ADMIN=192.168.41.52   # poste admin (eth0, réseau de l'école)
DEV=192.168.41.124    # poste DEV
IA=192.168.41.125     # poste IA

# Politique par défaut
ufw default deny incoming
ufw default allow outgoing
ufw default deny routed
ufw logging low

# SSH (clé uniquement), limité en débit (6 connexions / 30 s par IP)
for ip in "$ADMIN" "$DEV" "$IA"; do
  ufw limit in on eth0 from "$ip" to 192.168.41.123 port 22 proto tcp comment 'SSH equipe (eth0)'
done
# Wi-Fi de la table : postes d'admin en DHCP 192.168.10.100 à .199
for net in 192.168.10.100/30 192.168.10.104/29 192.168.10.112/28 192.168.10.128/26 192.168.10.192/29; do
  ufw limit in on wlan0 from "$net" to 192.168.10.10 port 22 proto tcp comment 'SSH admin (wlan0)'
done

# Dashboard / API (HTTPS), quand il sera servi
ufw allow in on wlan0 from 192.168.10.0/24 to 192.168.10.10 port 443 proto tcp comment 'HTTPS table'
for ip in "$ADMIN" "$DEV" "$IA"; do
  ufw allow in on eth0 from "$ip" to 192.168.41.123 port 443 proto tcp comment 'HTTPS equipe (eth0)'
done

# Flux webcam du script IA (Flask :8080 sur l'hôte, R22). Accès direct de l'équipe
# (règles ajoutées le 2026-10-08) : à retirer quand le dashboard passe par Caddy (/webcam/).
ufw allow in on eth0 from "$DEV" to 192.168.41.123 port 8080 proto tcp comment 'Flux webcam -> dashboard DEV'
ufw allow in on eth0 from "$ADMIN" to 192.168.41.123 port 8080 proto tcp comment 'Flux webcam -> admin'
ufw allow in on wlan0 from 192.168.10.0/24 to 192.168.10.10 port 8080 proto tcp comment 'Flux webcam -> Wi-Fi table'
# Caddy (réseau Docker « edge », 172.30.0.0/24) -> hôte : flux webcam via https://.../webcam/
ufw allow in on br-sentinel-edge from 172.30.0.0/24 to 172.30.0.1 port 8080 proto tcp comment 'Caddy -> flux webcam'

# Services réseau du point d'accès (wlan0 uniquement)
ufw allow in on wlan0 to any port 67 proto udp comment 'DHCP AP'
ufw allow in on wlan0 from 192.168.10.0/24 to 192.168.10.10 port 123 proto udp comment 'NTP local'

# Filet de sécurité, armé AVANT l'activation
systemctl stop ufw-deadman.timer 2>/dev/null || true
systemd-run --unit=ufw-deadman --on-active=5min /usr/sbin/ufw disable

ufw --force enable
ufw status verbose
echo ">>> UFW actif. Désactivation auto dans 5 min."
echo ">>> Testez SSH depuis un SECOND terminal, puis : sudo systemctl stop ufw-deadman.timer"
