#!/bin/sh
# Sentinel-X : restreint le MQTT publié sur eth0 (1883 en clair, exception
# temporaire R2, et 8883 MQTTS) aux machines de l'équipe. Les ports publiés par
# Docker passent par FORWARD (après DNAT) et contournent UFW : le filtrage se
# fait dans DOCKER-USER. Le 8883 sur wlan0 (Wi-Fi de la table) n'est pas concerné.
# Idempotent. Installé dans /usr/local/sbin/, lancé par sentinel-docker-user.service.
# Usage : docker-user-mqtt.sh [start|stop]
set -eu

IPT=/usr/sbin/iptables
CHAIN=SENTINEL-MQTT-ETH0
ETH0_IP=192.168.41.123
PORTS="1883 8883"
TEAM="192.168.41.121 192.168.41.124 192.168.41.125 192.168.41.52"  # ESP, DEV, IA, admin

# Retire les sauts DOCKER-USER -> $CHAIN (autant de fois que présents)
unhook() {
  for port in $PORTS; do
    while $IPT -D DOCKER-USER -i eth0 -p tcp -m conntrack \
        --ctorigdst "$ETH0_IP" --ctorigdstport "$port" -j "$CHAIN" 2>/dev/null; do :; done
  done
}

if [ "${1:-start}" = stop ]; then
  unhook
  $IPT -F "$CHAIN" 2>/dev/null || true
  $IPT -X "$CHAIN" 2>/dev/null || true
  exit 0
fi

# Chaîne dédiée : RETURN pour l'équipe, journal (limité) puis DROP pour le reste
$IPT -N "$CHAIN" 2>/dev/null || $IPT -F "$CHAIN"
for ip in $TEAM; do
  $IPT -A "$CHAIN" -s "$ip" -j RETURN
done
$IPT -A "$CHAIN" -m limit --limit 6/min -j LOG --log-prefix "SENTINEL-MQTT-DROP "
$IPT -A "$CHAIN" -j DROP

# Sauts depuis DOCKER-USER (en tête), sur la destination d'origine avant DNAT
unhook
for port in $PORTS; do
  $IPT -I DOCKER-USER 1 -i eth0 -p tcp -m conntrack \
    --ctorigdst "$ETH0_IP" --ctorigdstport "$port" -j "$CHAIN"
done
