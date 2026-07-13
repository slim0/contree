# Architecture — Belote Contrée

> Document vivant. Toute décision structurante doit être reflétée ici et dans un ADR.

---

## Vue d'ensemble

Application web multijoueur temps réel. Architecture simple et pragmatique pour le POC — pas de micro-services, pas de Kubernetes, pas de sur-ingénierie.

```
┌─────────────────────────────────────────────────────┐
│                     CLIENT                          │
│         React + TypeScript (Vite)                   │
│         WebSocket natif + Zustand                   │
│         authStore (user info) + LoginPage + AdminPanel │
└───────────────────┬─────────────────────────────────┘
                    │ WebSocket (ws://) — cookie envoyé automatiquement
                    │ HTTP (REST) — cookie HttpOnly envoyé automatiquement
┌───────────────────▼─────────────────────────────────┐
│                    SERVEUR                          │
│              FastAPI (Python 3.12+)                 │
│    WebSocket handlers + Routes HTTP + Auth routes   │
│                                                     │
│    ┌────────────────────────────────────────┐       │
│    │         Moteur de jeu (pur Python)     │       │
│    │   models.py / rules.py / scoring.py   │       │
│    └────────────────────────────────────────┘       │
│                                                     │
│    ┌────────────────────────┐                       │
│    │  memory_store.py       │                       │
│    │  dict Python asyncio   │                       │
│    │  rooms / sessions jeu  │                       │
│    └────────────────────────┘                       │
└───────────────────┬─────────────────────────────────┘
                    │ REST (httpx, auth superuser)
┌───────────────────▼─────────────────────────────────┐
│                  PocketBase                          │
│         collection "users" (comptes, mots de passe)  │
└─────────────────────────────────────────────────────┘
```

---

## Back-end

### Langage & Framework
- **Python 3.12+** — langage natif du dev, pas de coût d'apprentissage
- **FastAPI** — async natif, WebSocket intégré via Starlette, validation Pydantic, doc auto

### Structure des modules

```
backend/
├── game/               # Moteur de jeu PUR — zéro dépendance externe
│   ├── models.py       # Dataclasses, enums : Card, Trick, RoundState, GameState...
│   ├── rules.py        # is_legal(), is_partner_winning(), card_strength()
│   └── scoring.py      # score_round(), round_to_ten()
├── pocketbase/
│   └── client.py        # PocketBaseClient — auth superuser + REST vers la collection users
├── users/
│   ├── models.py        # dataclass User (id str, username, is_admin, must_change_password...)
│   ├── repository.py    # UserRepository — seul point d'accès aux comptes (proxie PocketBaseClient)
│   └── schemas.py       # Pydantic : UserCreate, UserResponse
├── auth/
│   ├── service.py      # generate_temp_password, create_token, decode_token
│   ├── dependencies.py # Dépendances FastAPI : get_current_user, require_admin
│   └── schemas.py      # LoginRequest, TokenResponse, ChangePasswordRequest
├── api/
│   ├── websocket.py    # handlers WS par événement (jeu + signaling WebRTC voix)
│   ├── routes.py       # POST /rooms, GET /rooms/{id}
│   ├── auth_routes.py  # POST /auth/login, POST /auth/change-password
│   ├── admin_routes.py # POST/GET/DELETE /admin/users
│   ├── dev_routes.py   # routes de dev (autologin, quickstart) — montées seulement si DEVELOPMENT=true
│   └── limiter.py       # instance slowapi partagée
├── store/
│   └── memory_store.py  # Lecture/écriture du GameState dans un dict Python (asyncio.Lock)
├── tests/
│   ├── test_rules.py
│   ├── test_scoring.py
│   ├── test_belote.py
│   ├── test_bidding_volee.py
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_dev_routes.py
│   ├── test_leave_room.py
│   ├── test_rate_limiting.py
│   ├── test_team_selection.py
│   └── test_websocket_reconnect.py
└── main.py
```

### État du jeu
- **Dict Python asyncio** (`memory_store.py`) — stocke les objets `GameState` en mémoire par room
- Clé : `room_id` → `GameState`
- Accès protégé par un `asyncio.Lock` pour éviter les races conditions entre coroutines
- L'état n'est **pas** persisté : une relance du serveur remet toutes les rooms à zéro (acceptable pour le POC)
- En cas de montée en charge future, Redis peut remplacer ce dict sans toucher au moteur de jeu

### Base de données (utilisateurs)
- **PocketBase** — service séparé (conteneur Docker dédié), collection `users` étendue avec les champs custom `is_admin` / `must_change_password` (voir `pocketbase/pb_migrations/`)
- PocketBase gère lui-même le stockage **et** le hachage/vérification des mots de passe — le backend ne fait jamais de bcrypt
- Le backend s'authentifie auprès de PocketBase comme **superuser** (`PB_SUPERUSER_EMAIL`/`PB_SUPERUSER_PASSWORD`, compte de service) et proxie toutes les opérations via `PocketBaseClient` (`backend/pocketbase/client.py`, REST/httpx)
- Aucune règle d'API PocketBase publique sur `users` (`listRule`/`viewRule`/`createRule`/`updateRule`/`deleteRule` = `null`) — accès superuser uniquement
- **Repository pattern** : `UserRepository` isole tout accès aux comptes. Changer de backend de stockage = modifier uniquement ce fichier (et `PocketBaseClient`), le reste du code ne sait pas ce qui se passe dessous.

### Authentification
- **JWT** (PyJWT) — tokens stateless 8h, pas de refresh token (POC). Ce JWT est propre au backend : ni le frontend ni PocketBase ne le voient l'un l'autre.
- Payload JWT : `{ sub (id PocketBase, string), username, is_admin, must_change_password }`
- Vérification du mot de passe déléguée à PocketBase (`auth-with-password`) — le backend ne hache ni ne compare rien lui-même
- **Cookie HttpOnly** : le JWT est stocké dans un cookie `access_token` (HttpOnly, Secure, SameSite=Lax) — jamais exposé au JavaScript
- Routes HTTP : cookie envoyé automatiquement par le navigateur
- WebSocket : le navigateur envoie le cookie automatiquement lors du handshake — le serveur le lit depuis les headers de la requête d'upgrade
- CORS : `allow_credentials=True` + origines explicites (pas de wildcard `*`)
- Le frontend ne stocke pas le JWT — il stocke uniquement les infos utilisateur (`username`, `is_admin`, `must_change_password`) reçues dans le corps de la réponse de login ou via `GET /auth/me`

### Communication temps réel
- **WebSocket natif** FastAPI/Starlette — pas de Socket.io
- Un handler WebSocket par room : `ws://host/ws/{room_id}` — le joueur est identifié via le cookie JWT (`access_token`), pas via l'URL
- `backend/api/websocket.py` gère les connexions actives (registre en mémoire + verrou) et le broadcast par room

### Principe d'immuabilité du moteur
Le moteur de jeu (`game/`) ne modifie jamais l'état en place.  
Chaque action retourne un **nouvel état** :

```python
new_state, events = apply_action(current_state, action)
```

Cela facilite les tests et évite les effets de bord.

---

## Front-end

### Framework & Outillage
- **React 18 + TypeScript** (strict mode)
- **Vite** — bundler, pas CRA
- **CSS custom** (`frontend/index.html`) + styles inline — pas de Tailwind installé

### State Management
- **Zustand** — un seul store, `authStore` (user courant : username/is_admin/must_change_password)
- L'état de partie (jeu, connexion WS, chat vocal) vit en `useState` local dans `App.tsx`/`Game.tsx`, pas dans un store dédié

### Client WebSocket
- WebSocket natif (pas Socket.io)
- Connexion/reconnexion/dispatch des messages gérés inline dans `App.tsx` (pas de module `websocket/` dédié)
- Reconnexion automatique à intervalle fixe (2s) — pas de backoff exponentiel
- Messages non typés côté client (`JSON.parse` + switch sur `msg.type` en chaîne)

### Structure

```
frontend/src/
├── App.tsx              # Lobby + client WebSocket (connect/reconnect/dispatch)
├── Game.tsx              # Table, cartes, enchères, plis, scores (fichier unique)
├── types.ts              # Miroir TypeScript des modèles Python
├── components/
│   ├── auth/            # LoginPage, ChangePasswordPage
│   └── admin/           # AdminPanel
├── voice/                # VoiceManager (WebRTC P2P chat vocal)
└── store/
    └── authStore.ts      # user courant — pas de JWT
```

---

## Flux d'une action joueur (exemple : jouer une carte)

```
1. Joueur clique sur une carte
   → Game.tsx envoie via WS : { type: "play", suit, rank }

2. Serveur reçoit l'événement (backend/api/websocket.py)
   → vérifie la légalité du coup (backend/game/rules.py)
   → si illégal : envoie { type: "error", message: "..." } au joueur
   → si légal :
     new_state = rules.apply_play(state, ...)
     → sauvegarde new_state dans memory_store (dict Python asyncio)
     → broadcast { type: "state", data: new_state } à tous les joueurs de la room

3. Tous les clients reçoivent le nouvel état complet
   → App.tsx met à jour son state local (setGame)
   → React re-render
```

---

## Déploiement

### Dev local — hot-reload

```bash
docker compose up --build
```

| Service | URL locale | Description |
|---------|-----------|-------------|
| backend | http://localhost:8000 | FastAPI, rechargement sur modif Python |
| frontend | http://localhost:3000 | Vite, hot-reload React/TypeScript |
| pocketbase | http://localhost:8090 | Dashboard admin PocketBase sur `/_/` |

Les sources sont montées en volumes : aucun rebuild nécessaire pour voir les changements.  
Les données PocketBase sont persistées dans le volume Docker `pocketbase_data`.

### Prod — VPS

```bash
JWT_SECRET_KEY=<clé-longue-aléatoire> docker compose -f docker-compose.prod.yml up --build -d
```

```
┌──────────────────────────────────┐
│  VPS (Hetzner / OVH)            │
│                                  │
│  nginx (port 80)                 │
│   /          → React build       │
│   /api/      → backend:8000      │
│   /ws        → backend:8000 (WS) │
│                                  │
│  backend (interne :8000)         │
│  pocketbase (interne :8090)      │
│  volume pocketbase_data          │
└──────────────────────────────────┘
```

Nginx proxie `/api` et `/ws` vers le backend — le frontend et l'API partagent la même origine, pas de problème CORS en prod.

Pour HTTPS : placer Caddy ou Traefik devant Docker Compose (reverse proxy + TLS automatique Let's Encrypt).

### Variables d'environnement

| Variable | Défaut | Requis en prod |
|----------|--------|---------------|
| `PB_URL` | `http://localhost:8090` | non (surchargé en Docker) |
| `PB_SUPERUSER_EMAIL` | — | **oui** |
| `PB_SUPERUSER_PASSWORD` | — | **oui** |
| `JWT_SECRET_KEY` | `change-me-in-production…` | **oui** |
| `BACKEND_URL` | `http://localhost:8000` | non (dev uniquement) |

---

## Flux d'authentification

```
1. Premier démarrage
   → backend attend que PocketBase soit joignable, puis :
   → aucun utilisateur dans PocketBase → bootstrap automatique
   → admin / <mot de passe temporaire> affiché dans les logs serveur

2. Création d'un utilisateur (admin)
   POST /admin/users { username }
   → mot de passe aléatoire 12 chars généré par le backend
   → transmis en clair à PocketBase, qui le hache et stocke le compte
   → mot de passe en clair retourné une seule fois dans la réponse HTTP

3. Login
   POST /auth/login { username, password }
   → vérification déléguée à PocketBase (auth-with-password)
   → JWT signé par le backend (8h) placé dans un cookie HttpOnly + Secure + SameSite=Lax
   → corps de réponse : { username, is_admin, must_change_password }
   → si must_change_password=True → frontend bloque l'accès au jeu

4. Changement de mot de passe obligatoire
   POST /auth/change-password { old_password, new_password }
   → cookie présent → authentifié automatiquement
   → ancien mot de passe revérifié auprès de PocketBase
   → nouveau mot de passe écrit dans PocketBase, must_change_password passé à False
   → nouveau cookie émis (JWT mis à jour)

5. Connexion WebSocket
   ws://host/ws/{room_id}
   → le navigateur envoie le cookie automatiquement lors du handshake HTTP
   → serveur lit le cookie dans les headers de l'upgrade request
   → fermeture de la connexion (code WS_1008_POLICY_VIOLATION) si cookie absent/invalide/
     must_change_password=True/is_admin=True (les comptes admin ne jouent pas)

6. Logout
   POST /auth/logout
   → cookie supprimé côté serveur (max_age=0)
```

---

## Ce que cette architecture ne fait PAS (intentionnellement)

- Pas d'historique des parties en base de données
- Pas de spectateurs
- Pas de matchmaking
- Pas de rooms publiques
- Pas de refresh tokens (JWT 8h en cookie suffisants pour une session de jeu)
- Pas d'email / récupération de mot de passe

Ces features ne sont pas dans le scope du POC. Les ajouter plus tard ne nécessite pas de refonte architecturale.
