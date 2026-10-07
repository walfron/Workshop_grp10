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
| `frontend/` | Dashboard web de supervision (React) | DEV |
| `scripts/` | Scripts d'installation, de lancement et d'arrêt | DEV |
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

## Lancer le backend et le dashboard

### 1. Installer Node.js (première fois uniquement)

Il faut **Node.js 22.13 ou plus récent** (version LTS recommandée). npm est installé avec Node.js.

- **Windows** : installer la version LTS, puis rouvrir le terminal.
  ```bash
  winget install OpenJS.NodeJS.LTS
  ```
  Ou télécharger l'installeur LTS sur [nodejs.org](https://nodejs.org).
- **Linux / Raspberry Pi / macOS** : installer [nvm](https://github.com/nvm-sh/nvm), puis Node.js.
  ```bash
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  nvm install 24
  ```

Vérifier l'installation avec `node --version`.

### 2. Installer le projet

À la racine du projet, la première fois puis après un `git pull` qui modifie des dépendances :

```bash
npm run setup
```

Cette commande vérifie la version de Node.js, installe les dépendances du backend et du frontend, et crée `backend/.env` et `frontend/.env.local` à partir des modèles `.env.example`.

Renseigner ensuite dans `backend/.env` le mot de passe du compte MQTT `backend` (`MQTT_PASSWORD`, transmis en privé par l'Infra).

### 3. Lancer

```bash
npm start
```

- Dashboard : <http://localhost:5173>
- API : <http://localhost:3000/api/v1/health>
- Arrêter : `Ctrl+C` dans le terminal, ou `npm run stop` depuis un autre terminal.

Le PC doit être sur le même réseau que le broker MQTT (Wi-Fi myDiL, broker `192.168.41.123`). `npm start` refuse de démarrer si les ports 3000 ou 5173 sont déjà utilisés : lancer `npm run stop` d'abord.

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
