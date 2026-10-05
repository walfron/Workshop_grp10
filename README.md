# Sentinel-X — Workshop M1 2026

Boîtier de surveillance autonome (ESP8266) pour les micro-centrales AetherCorp : détection d'intrus par vision (webcam) et détection d'anomalies température/gaz par IA, le tout chiffré et supervisé depuis un dashboard.

**Équipe G10** : Prénom Nom (DEV), Prénom Nom (IA), Anne-Lou Delage-Davies (INFRA)

## Architecture

```
[ESP8266 + DHT22 / MQ-2 / PIR / OLED / buzzer]
        │  Wi-Fi + MQTTS (TLS)
        ▼
[Raspberry Pi 5 = PC Serveur Local]  ◄── webcam USB
   ├─ Mosquitto (broker MQTT)
   ├─ Backend API (REST / WebSocket)
   ├─ Base de données
   ├─ IA : vision (YOLO) + anomalies (Isolation Forest)
   └─ Dashboard web
```

Variante retenue : **Option A (Raspberry Pi 5 embarqué)**.

## Structure du repo

| Dossier | Contenu | Responsable |
|---|---|---|
| `firmware/` | Code C++ de l'ESP8266 (PlatformIO) | DEV |
| `backend/` | API REST/WebSocket (`POST /api/v1/alerts`) | DEV |
| `dashboard/` | Interface web de supervision | DEV |
| `ai/` | Détection d'intrus (webcam) + détection d'anomalies | IA |
| `infra/` | Config Mosquitto, plan réseau, hardening | INFRA |
| `cad/` | Fichiers Fusion360 du boîtier + gravure laser | Toute l'équipe |
| `docs/` | Schémas, rapport, poster A3 | Toute l'équipe |

## Démarrage rapide (sur le Raspberry Pi)

```bash
git clone https://github.com/walfron/Workshop_grp10
cd sentinel-x
cp .env.example .env     # puis modifier les mots de passe
docker compose up -d --build
```

Le dashboard est accessible sur `http://<IP-du-Pi>:<port>`.

## Réseau

Plan d'adressage et configuration du Wi-Fi dédié : voir [infra/network.md](infra/network.md).

## Workflow Git

- Branches par filière : `dev/...`, `ia/...`, `infra/...`, fusion dans `main` via pull request.
- Commits sémantiques : `feat:`, `fix:`, `infra:`, `docs:`.
- On développe sur PC, on récupère sur le Pi avec `git pull`.
- `git pull` avant chaque session de travail.

## Sécurité

- **Aucun secret dans le repo** : mots de passe, clés et certificats restent en local (`.env`, `*.key`, `*.pem` sont ignorés par Git).
- Chiffrement des flux ESP8266 → serveur en TLS (MQTTS).
- Hardening du serveur : UFW, SSH par clés uniquement, privilèges Docker limités.

## Livrables

- [ ] Dossier technique PDF (`Workshop2026-M1-G<n>-Dossier.pdf`)
- [ ] Support de présentation (`Workshop2026-M1-G<n>-Pres.pptx`)
- [ ] Vidéo « Sentinel Drop » (`Workshop2026-M1-G<n>-VidDrop.mp4`)
- [ ] Archive du code (`Workshop2026-M1-G<n>-Code.zip`)
- [ ] Prototype fonctionnel déposé au myDiL le vendredi matin
