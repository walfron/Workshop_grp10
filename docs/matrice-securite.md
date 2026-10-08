# Matrice des risques — Sentinel-X (G10, filière INFRA)

Mise à jour : 2026-10-08. Source : `docs/journal-infra.md`.
Gravité / probabilité : F (faible), M (moyenne), É (élevée). Aucun secret dans ce fichier (dépôt public).

## Risques acceptés ou réduits

| # | Risque | Menace / scénario | Mesures en place | Résiduel | Statut |
|---|---|---|---|---|---|
| R1 | Utilisateur `sentinel` dans le groupe `docker` (équivalent root) | Compromission du compte → root sur le Pi | Accès uniquement en SSH par clé : mot de passe SSH **refusé depuis le 2026-10-08 10:21** (R19 ; auparavant actif) ; 3 clés autorisées, ajoutées par l'admin seule (R20) | M | Accepté (décision admin) |
| R2 | MQTT 1883 en clair (temporaire) | Écoute / MitM des identifiants MQTT sur le réseau de l'école (**utilisé le 2026-10-06 par 4 machines de l'école avec `sentinel` et `backend`**) | Auth + ACL, lié à `192.168.41.123` (eth0) seulement, **jamais publié sur le Wi-Fi** ; **`DOCKER-USER` (2026-10-08)** : seules `.121` (ESP), `.124` (DEV), `.125` (IA), `.52` (admin) atteignent le 1883, le reste est journalisé et rejeté (testé : téléphone `.82` en timeout, 6 SYN rejetés journalisés ; `.124` et `.52` passent) | É | **À supprimer avant jeudi** (après validation TLS ESP) |
| R3 | Ports publiés par Docker contournent UFW | Exposition involontaire d'un service | Ports liés à des IP précises (`192.168.10.10`, `192.168.41.123`), API sur `127.0.0.1`, DB sans port publié ; MQTT sur eth0 filtré par IP dans `DOCKER-USER` (`sentinel-docker-user.service`, persistant, relancé avec Docker) | F | Réduit |
| R4 | `net.ipv4.ip_nonlocal_bind = 1` (global) | Un processus local se lie à une IP non configurée | Nécessaire pour publier `192.168.10.10:8883` et le NTP avant que l'AP ne monte ; seul l'admin exécute des services | F | Accepté |
| R5 | Mot de passe Wi-Fi (PSK) passé en argument de `nmcli` lors de la création de l'AP | Lecture via `ps` pendant l'exécution | Opération ponctuelle ; seuls `sentinel` et root sur le Pi ; PSK stocké en root 600 et dans `.env` (600, non versionné) | F | Accepté |
| R6 | Diffusion du PSK hors de l'équipe | Client inconnu sur le Wi-Fi de la table (un appareil non identifié vu le 2026-10-06) | `ap-isolation` (clients isolés entre eux), isolation nftables (aucun accès école / internet), auth MQTT | M | **À vérifier** ; rotation du PSK si l'appareil reste inconnu |
| R7 | Routage / NAT du Wi-Fi vers le réseau de l'école | Le Pi sert de pont entre le Wi-Fi de la table et l'école / internet | `firewall-backend=none` (NetworkManager), table `inet sentinel_isolation` chargée avant le réseau ; testé : plus de `masquerade` 192.168.10.0/24 après redémarrage | F | Réduit |
| R8 | Falsification de l'heure en amont (NTP) | Décalage de l'heure du Pi puis des ESP → certificat refusé (DoS) | Sources **NTS** authentifiées (Cloudflare, PTB) ; pool non authentifié non sélectionné (`authselectmode mix`) | F | Réduit |
| R9 | `makestep 1 -1` : saut d'horloge autorisé à tout moment | Si seul le pool non authentifié répond (NTS bloqué), une réponse forgée peut faire sauter l'heure | Nécessaire pour recaler une heure fausse quand eth0 revient après le boot ; NTS joignable aujourd'hui | F | Accepté |
| R10 | **Pas de pile RTC** | Après coupure d'alimentation sans eth0 : heure fausse → ESP refuse le certificat (`notBefore`) | fake-hwclock (dernière heure sauvegardée, horaire + arrêt), chargement « avance seulement » ; `local stratum 10` sert l'heure sans internet ; `rtcsync` | M : heure **en retard** de la durée de coupure (+ ≤ 1 h si coupure brutale) → horodatages faux | Réduit ; pile ML-2020 si achetable |
| R11 | Bug fake-hwclock 0.14 (`load` recule l'horloge) | Heure exacte de la RTC remplacée par une sauvegarde plus ancienne au boot | Drop-in `forward-only.conf` (n'avance que l'horloge), testé à chaud | F | Corrigé |
| R12 | Accès au serveur NTP | DoS / amplification NTP au pentest | Écoute sur `192.168.10.10` seulement, `allow 192.168.10.0/24`, `ratelimit`, `cmdport 0` (pas de contrôle réseau) | F | Réduit |
| R13 | ESP connecté par IP : vérification du nom du serveur par BearSSL **non confirmée** | Certificat valide de la même CA pour un autre hôte accepté | CA privée (seuls nos certificats sont signés), CA hors du Pi | F | À confirmer par DEV |
| R14 | SSH joignable depuis le Wi-Fi de la table | Attaque SSH par un client Wi-Fi | Clé uniquement (effectif depuis le 2026-10-08, R19) ; à restreindre par UFW à `192.168.10.100–199` sur wlan0 (nécessaire : pas d'eth0 à la démo) | M | **À faire (hardening)** |
| R15 | Compte MQTT `monitor` (nouveau, 2026-10-07) | Vol du mot de passe → fausses mesures système / fausses alertes, lecture du nombre de clients | Droits minimaux : écriture `sentinel/+/system` et `sentinel/+/alerts`, lecture `$SYS/broker/clients/#` seulement (testé : `telemetry` et `cmd` refusés) ; mot de passe aléatoire 32 car. dans `.env` (600) ; MQTTS uniquement | F | Réduit |
| R16 | Service `sentinel-monitor` (hôte) dans le groupe `docker` (équivalent root) | Compromission de l'agent → root via le socket Docker | Aucun port ouvert (client MQTTS sortant local) ; seul message reçu : un entier (`$SYS`) ; `docker ps`/`inspect` en lecture ; durcissement systemd (`ProtectSystem=strict`, `ProtectHome=read-only`, aucune capability, `SystemCallFilter=@system-service`, `MemoryMax=64M`) : `systemd-analyze security` = 2.0 OK | F | Accepté (lié à R1) |
| R17 | Faux positifs / négatifs de supervision | Alerte manquée (logs Docker non mesurables par `sentinel`) ou alerte usurpée sur `alerts` (topic partagé ESP / IA / monitor) | Taille max Docker bornée par la rotation (10 Mo × 3, vérifiée par l'agent) ; champ `source` ; ACL par compte | F | Accepté |
| R18 | `sentinel` membre du groupe hôte `mosquitto-ct` (GID 1883 = groupe du conteneur Mosquitto, 2026-10-07) | Compte `sentinel` compromis → lecture de la config Mosquitto | Effet réel limité : **lecture** de `acl` (640, aucun secret) ; `passwd`, `server.key` et `data/mosquitto.db` en **600** restent illisibles ; écriture dans le **dossier** `data/` (775 : création / suppression de fichiers). Permet à Git de lire `acl` (`git status` propre, `pull` non bloqué) tout en gardant `640 1883:1883` (aucun avertissement Mosquitto). Rien de plus que R1 (`sentinel` déjà dans `docker`) | F | Accepté |
| R19 | Authentification SSH par **mot de passe** active depuis l'installation (au moins du 2026-10-05 au 2026-10-08 ; `PasswordAuthentication yes` par défaut, aucune clé admin avant le 2026-10-07 14:54) ; dernière connexion par mot de passe le 2026-10-08 09:38 depuis `192.168.41.125` (poste IA, légitime) | Bruteforce / vol du mot de passe de `sentinel` (groupe `docker` = root, R1) depuis le réseau de l'école | `/etc/ssh/sshd_config.d/10-sentinel.conf` (copie : `infra/hardening/`, lu avant `50-cloud-init.conf`) : `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitRootLogin no`, `AllowUsers sentinel`, `MaxAuthTries 3`, `LoginGraceTime 30`, `X11Forwarding no` ; vérifié par `sshd -T` ; testé 2026-10-08 : clé acceptée (PC admin), mot de passe **refusé** (`Permission denied (publickey)`, depuis le PC admin et en local) ; mot de passe de `sentinel` changé (reste utilisé pour `sudo`) | F | **Corrigé** (2026-10-08) |
| R20 | Clés SSH autorisées pour `sentinel` (`~/.ssh/authorized_keys`, 600) | Clé ajoutée par un tiers → accès permanent au compte (= root, R1) ; le 2026-10-08 10:17, une clé (`dev-sentinel`) a été ajoutée depuis une session ouverte sans passer par l'admin | 3 clés ED25519, empreintes vérifiées : `admin-sentinel` `SHA256:ebi4BQWBXvWV7Oi72poeyJ4BHwQWq8NvSWNV3VcnBQ8` (poste admin `.52`) ; `ia-sentinel` `SHA256:RWHWVVHk1oSz8vuI7Qm4Sz++3nyxynO7rvcl4V40fEU` (poste IA `.125`) ; `dev-sentinel` `SHA256:DtPRl+4njTt5mf/flQ5PUxNzHxboF+jp+zQTVhXxwIY` (poste DEV `.124`, vérifiée sur son PC). **Règle : seule l'admin ajoute une clé, après vérification de l'empreinte avec son propriétaire** ; contrôle par `ssh-keygen -lf ~/.ssh/authorized_keys` et journal `Accepted publickey` | F | Accepté |
| R21 | Filtrage `DOCKER-USER` par **IP source** | Une autre table du réseau de l'école usurpe l'IP d'un poste de l'équipe (`.124`, `.125`…) pour atteindre le MQTT | Authentification + ACL Mosquitto (le filtrage IP n'est qu'une couche) ; rejets journalisés (`SENTINEL-*-DROP`, `journalctl -k`) ; suppression du 1883 prévue (R2) | M | Accepté |
| R22 | Script de vision IA lancé sur l'**hôte** (hors Docker, hors dépôt) : Flask `0.0.0.0:8080` sans authentification (flux webcam), MQTT en clair vers `127.0.0.1:1883`, mot de passe MQTT `ia` écrit en dur dans le script (`~/`, non versionné) | Fuite du flux vidéo si le pare-feu change ; mot de passe copié dans le dépôt public ; pas de limites CPU / RAM | Flux 8080 nécessaire (webcam du dashboard) : UFW limite le 8080 à `.124`, `.52` (eth0) et `192.168.10.0/24` (wlan0) ; aucun mot de passe trouvé dans `ai/` (toutes branches) ; correction en cours par IA : MQTTS 8883 + `ca.crt`, mot de passe hors du code | M | **Réduit** : accès limité à l'équipe par UFW ; authentification à ajouter |

## Incidents

| Date | Incident | Impact | Action |
|---|---|---|---|
| 2026-10-06 | Identifiants du **Wi-Fi de l'école** en clair dans `firmware/src/main.cpp` (branche `feature/add-esp-logique`, dépôt public) | Secret d'un tiers exposé publiquement | Retrait du code + réécriture de l'historique, `secrets.h` ignoré par Git ; prévenir le responsable du réseau de l'école |
| 2026-10-06 | **Mot de passe MQTT du compte `sentinel` publié** dans `firmware/src/credentials.h` (branche `feature/add-esp-logique`, dépôt public). Exposé de 15:58:25 (commit `0872da2`) à 16:12:18 (rotation effective) ≈ 14 min ; le commit `0f8f448` (« fix », 16:11:31) ne le retire pas de l'historique | Accès MQTT au broker avec le compte des capteurs (publication de fausses mesures / alertes sur `sentinel/+/telemetry` et `alerts`) | Voir le détail ci-dessous |
| 2026-10-07 | Rechargement Mosquitto (SIGHUP) sans effet sur l'ACL : montage de **fichier** figé sur l'inode du démarrage, remplacé par un `git pull` ; 1ʳᵉ réécriture en échec (`acl` remis en `664 1000:1000` par le pull) et SIGHUP envoyé quand même (commande sans `set -e`) | Aucun : règles et mots de passe inchangés pendant les rechargements, clients non coupés ; nouvelle ACL appliquée après `docker compose restart` (coupure 1–2 s, feu vert admin) | Étapes chaînées en `set -e` ; montage par **dossier** `infra/mosquitto/config/` ; hook `post-merge` local (droits `640 1883:1883` + SIGHUP) |
| 2026-10-06 | NAT ajouté par NetworkManager malgré `firewall-backend=none` (reload insuffisant) | Aucun : routage déjà bloqué par `sentinel_isolation` (défense en profondeur) | Redémarrage ; vérifié absent ensuite |
| 2026-10-06 | Route parasite (commande de test client lancée sur le Pi) | Réseau de l'école détourné vers wlan0 temporairement | Route supprimée ; commandes client désormais signalées explicitement |

### Détail : fuite du mot de passe MQTT `sentinel` (2026-10-06)

**Détection** : signalée par l'admin INFRA (fichier `firmware/src/credentials.h` sur la branche `feature/add-esp-logique` du dépôt public), ~16:10.

**Rotation (16:11–16:12)**, sans afficher aucun secret :
1. Nouveau `MQTT_PASSWORD` (32 caractères, `secrets.token_urlsafe(24)`) écrit dans `.env` (600) par un script, sans passer par la ligne de commande ; ancien conservé le temps du test dans un fichier temporaire 600 hors dépôt, puis détruit (`shred -u`).
2. `infra/mosquitto/passwd` régénéré (conteneur jetable `--network none --cap-drop ALL`, mots de passe passés par variables d'environnement) : 3 comptes, hachage `$7$` (PBKDF2-SHA512) ; seul `sentinel` change. Fichier `600 1883:1883`, ignoré par Git.
3. `docker compose restart mosquitto` puis tests en MQTTS (8883) :

| Test | Résultat |
|---|---|
| `sentinel` + ancien mot de passe | ✅ refusé (`not authorised`, rc=5) |
| `sentinel` + nouveau mot de passe → reçu par `backend` | ✅ |
| `ia` (inchangé) sur `sentinel/1/alerts` | ✅ |

**Constat dans les logs Mosquitto (depuis 12:24 UTC)** : 5 couples machine/compte du **réseau de l'école** se sont connectés **en clair sur 1883** : `192.168.41.121` (`sentinel`), `.124` (`backend` + `sentinel`), `.125` (`sentinel`), `.52` (`backend`, MQTT Explorer). Après la rotation, `.125` (et des clients `mqttjs`) sont refusés en boucle. **Identification (admin, 2026-10-07)** : toutes ces machines appartiennent à l'équipe.

| Machine | Rôle | Compte attendu | Comptes vus dans les logs |
|---|---|---|---|
| `192.168.41.121` | ESP8266 (client `sentinelx-g10`) | `sentinel` | `sentinel` ✅ |
| `192.168.41.124` | poste DEV (backend / dashboard, `mqttjs`) | `backend` | `backend` ✅, et `sentinel` le 2026-10-06 (outil de diagnostic `diag-p-*`) ⚠️ |
| `192.168.41.125` | poste IA | `ia` | `ia` ✅ (2026-10-07), et `sentinel` le 2026-10-06 ⚠️ |
| `192.168.41.52` | poste admin (MQTT Explorer) | `backend` (lecture) | `backend` ✅ |

Aucune connexion d'une machine inconnue : pas d'exploitation constatée du mot de passe publié. Écart au moindre privilège : DEV et IA ont utilisé le compte des capteurs (`sentinel`) pour leurs tests → chacun utilise désormais son propre compte (`backend`, `ia`), ce que confirment les logs du 2026-10-07.
→ Le 1883 en clair (R2) a exposé les mots de passe `sentinel` **et `backend`** à toute écoute sur le réseau de l'école : `backend` est à considérer comme potentiellement compromis (rotation proposée).

**Mesures préventives** :
- Firmware : identifiants dans `firmware/include/secrets.h` **ignoré par Git** (+ `secrets.h.example` versionné) ; à ajouter au `.gitignore` (`firmware/include/secrets.h`, `**/credentials.h`), absent à ce jour.
- Réécriture de l'historique de la branche (ou suppression / recréation) : un commit de suppression laisse le secret dans l'historique public.
- GitHub : activer **Secret scanning + Push protection** (gratuit sur un dépôt public) ; option : hook `pre-commit` gitleaks.
- Nouveau mot de passe transmis à DEV / IA hors Git (canal privé), jamais dans le code versionné.
- Supprimer le 1883 en clair dès que possible (R2) : la fuite par le dépôt et l'écoute réseau visent le même secret.

## À traiter

- Supprimer le listener 1883 (R2).
- Authentification sur le flux webcam 8080 (R22).
- **Lancer le script IA comme service au démarrage** (autonomie pour la démo), avec limites CPU / RAM.
- Scans nmap eth0 + TLS + méthodes SSH à reporter (wlan0 fait et conforme, cf. journal 2026-10-08).

## Contrôles effectués (2026-10-08)

- UFW actif (entrant refusé, 22 / 443 / 8080 / 67 / 123 limités par interface et source), `DOCKER-USER` (1883 et 8883 sur eth0 limités à l'équipe), services inutiles désactivés / masqués (`rpcbind`, `avahi`, `cups`, `bluetooth`, `wayvnc`, `lightdm`), `chromium-sandbox` purgé, sysctl durcis (`rp_filter = 1` effectif sur eth0 / wlan0).
- Scan nmap depuis le Wi-Fi de la table : 22 et 8883 open ; 443 closed ; 8080 closed (script IA arrêté pendant le scan, relancé depuis) ; 1883 et le reste filtered. Conforme.
