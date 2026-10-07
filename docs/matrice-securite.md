# Matrice des risques — Sentinel-X (G10, filière INFRA)

Mise à jour : 2026-10-07. Source : `docs/journal-infra.md`.
Gravité / probabilité : F (faible), M (moyenne), É (élevée). Aucun secret dans ce fichier (dépôt public).

## Risques acceptés ou réduits

| # | Risque | Menace / scénario | Mesures en place | Résiduel | Statut |
|---|---|---|---|---|---|
| R1 | Utilisateur `sentinel` dans le groupe `docker` (équivalent root) | Compromission du compte → root sur le Pi | Accès uniquement en SSH par clé, mot de passe SSH interdit | M | Accepté (décision admin) |
| R2 | MQTT 1883 en clair (temporaire) | Écoute / MitM des identifiants MQTT sur le réseau de l'école (**utilisé le 2026-10-06 par 4 machines de l'école avec `sentinel` et `backend`**) | Auth + ACL, lié à `192.168.41.123` (eth0) seulement, **jamais publié sur le Wi-Fi** | É | **À supprimer avant jeudi** (après validation TLS ESP) |
| R3 | Ports publiés par Docker contournent UFW | Exposition involontaire d'un service | Ports liés à des IP précises (`192.168.10.10`, `192.168.41.123`), API sur `127.0.0.1`, DB sans port publié | F | Réduit |
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
| R14 | SSH joignable depuis le Wi-Fi de la table | Attaque SSH par un client Wi-Fi | Clé uniquement ; à restreindre par UFW à `192.168.10.100–199` sur wlan0 (nécessaire : pas d'eth0 à la démo) | M | **À faire (hardening)** |
| R15 | Compte MQTT `monitor` (nouveau, 2026-10-07) | Vol du mot de passe → fausses mesures système / fausses alertes, lecture du nombre de clients | Droits minimaux : écriture `sentinel/+/system` et `sentinel/+/alerts`, lecture `$SYS/broker/clients/#` seulement (testé : `telemetry` et `cmd` refusés) ; mot de passe aléatoire 32 car. dans `.env` (600) ; MQTTS uniquement | F | Réduit |
| R16 | Service `sentinel-monitor` (hôte) dans le groupe `docker` (équivalent root) | Compromission de l'agent → root via le socket Docker | Aucun port ouvert (client MQTTS sortant local) ; seul message reçu : un entier (`$SYS`) ; `docker ps`/`inspect` en lecture ; durcissement systemd (`ProtectSystem=strict`, `ProtectHome=read-only`, aucune capability, `SystemCallFilter=@system-service`, `MemoryMax=64M`) : `systemd-analyze security` = 2.0 OK | F | Accepté (lié à R1) |
| R17 | Faux positifs / négatifs de supervision | Alerte manquée (logs Docker non mesurables par `sentinel`) ou alerte usurpée sur `alerts` (topic partagé ESP / IA / monitor) | Taille max Docker bornée par la rotation (10 Mo × 3, vérifiée par l'agent) ; champ `source` ; ACL par compte | F | Accepté |

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

**Constat dans les logs Mosquitto (depuis 12:24 UTC)** : 5 couples machine/compte du **réseau de l'école** se sont connectés **en clair sur 1883** : `192.168.41.121` (`sentinel`), `.124` (`backend` + `sentinel`), `.125` (`sentinel`), `.52` (`backend`, MQTT Explorer). Après la rotation, `.125` (et des clients `mqttjs`) sont refusés en boucle. Machines à identifier (membres de l'équipe ?).
→ Le 1883 en clair (R2) a exposé les mots de passe `sentinel` **et `backend`** à toute écoute sur le réseau de l'école : `backend` est à considérer comme potentiellement compromis (rotation proposée).

**Mesures préventives** :
- Firmware : identifiants dans `firmware/include/secrets.h` **ignoré par Git** (+ `secrets.h.example` versionné) ; à ajouter au `.gitignore` (`firmware/include/secrets.h`, `**/credentials.h`), absent à ce jour.
- Réécriture de l'historique de la branche (ou suppression / recréation) : un commit de suppression laisse le secret dans l'historique public.
- GitHub : activer **Secret scanning + Push protection** (gratuit sur un dépôt public) ; option : hook `pre-commit` gitleaks.
- Nouveau mot de passe transmis à DEV / IA hors Git (canal privé), jamais dans le code versionné.
- Supprimer le 1883 en clair dès que possible (R2) : la fuite par le dépôt et l'écoute réseau visent le même secret.

## À traiter

- UFW : tout fermé sauf 8883 (Wi-Fi + eth0), 443, 22 (admin), 67/udp et 123/udp sur wlan0.
- Supprimer le listener 1883 (R2).
- Paquets inutiles (`chromium-sandbox`) : `apt autoremove`.
