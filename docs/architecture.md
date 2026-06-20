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
│    ┌────────────────┐  ┌─────────────────────────┐  │
│    │     Redis      │  │  SQLite (SQLAlchemy)    │  │
│    │ state rooms/   │  │  utilisateurs + auth    │  │
│    │ sessions jeu   │  │  (swappable via env)    │  │
│    └────────────────┘  └─────────────────────────┘  │
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
├── db/
│   ├── database.py     # engine + SessionLocal + Base (SQLAlchemy, piloté par DATABASE_URL)
│   └── models.py       # Modèles ORM SQLAlchemy (User)
├── users/
│   ├── repository.py   # UserRepository — seul point d'accès à la DB utilisateurs
│   └── schemas.py      # Pydantic : UserCreate, UserResponse
├── auth/
│   ├── service.py      # hash_password, verify_password, create_token, decode_token
│   ├── dependencies.py # Dépendances FastAPI : get_current_user, require_admin
│   └── schemas.py      # LoginRequest, TokenResponse, ChangePasswordRequest
├── api/
│   ├── websocket.py    # ConnectionManager, handlers WS par événement
│   ├── routes.py       # POST /rooms, GET /rooms/{id}
│   ├── auth_routes.py  # POST /auth/login, POST /auth/change-password
│   ├── admin_routes.py # POST/GET/DELETE /admin/users
│   └── schemas.py      # Pydantic models pour les payloads WS et HTTP
├── store/
│   └── redis.py        # Lecture/écriture du GameState dans Redis
├── tests/
│   ├── test_rules.py
│   ├── test_scoring.py
│   ├── test_websocket.py
│   ├── test_auth.py
│   └── test_users.py
└── main.py
```

### État du jeu
- **Redis** pour stocker le `GameState` sérialisé (JSON) par room
- Clé Redis : `room:{room_id}:state`
- L'état de jeu n'est **pas** persisté en base de données relationnelle (scope POC)

### Base de données (utilisateurs)
- **SQLAlchemy** comme ORM — abstraction DB complète
- **SQLite** par défaut (`DATABASE_URL=sqlite:///./contree.db`)
- Passer sur PostgreSQL : changer uniquement `DATABASE_URL` dans l'environnement
- **Repository pattern** : `UserRepository` isole toutes les requêtes SQL. Changer d'ORM ou de DB = modifier uniquement ce fichier, le reste du code ne sait pas ce qui se passe dessous.

### Authentification
- **JWT** (PyJWT) — tokens stateless 8h, pas de refresh token (POC)
- Payload JWT : `{ user_id, username, is_admin, must_change_password }`
- **bcrypt** via passlib pour le hash des mots de passe
- **Cookie HttpOnly** : le JWT est stocké dans un cookie `access_token` (HttpOnly, Secure, SameSite=Lax) — jamais exposé au JavaScript
- Routes HTTP : cookie envoyé automatiquement par le navigateur
- WebSocket : le navigateur envoie le cookie automatiquement lors du handshake — le serveur le lit depuis les headers de la requête d'upgrade
- CORS : `allow_credentials=True` + origines explicites (pas de wildcard `*`)
- Le frontend ne stocke pas le JWT — il stocke uniquement les infos utilisateur (`username`, `is_admin`, `must_change_password`) reçues dans le corps de la réponse de login ou via `GET /auth/me`

### Communication temps réel
- **WebSocket natif** FastAPI/Starlette — pas de Socket.io
- Un handler WebSocket par room : `ws://host/ws/{room_id}/{player_id}`
- `ConnectionManager` : gère les connexions actives et le broadcast par room

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
- **Tailwind CSS** — utilitaires, pas de design system custom pour le POC

### State Management
- **Zustand** — simple, pas de boilerplate Redux
- Un store `useGameStore` : état du jeu reçu du serveur
- Un store `useConnectionStore` : état de la connexion WebSocket

### Client WebSocket
- WebSocket natif (pas Socket.io)
- Module `src/websocket/client.ts` : connexion, envoi, réception d'événements typés
- Reconnexion automatique avec backoff exponentiel

### Structure

```
frontend/src/
├── components/
│   ├── game/           # Table, Hand, Card, Trick, Scoreboard
│   ├── lobby/          # Room creation, join
│   └── ui/             # Boutons, modals génériques
├── store/
│   ├── gameStore.ts
│   └── connectionStore.ts
├── websocket/
│   ├── client.ts       # Connexion WS
│   └── events.ts       # Types des événements (miroir du back)
├── types/
│   └── game.ts         # Miroir TypeScript des modèles Python
└── App.tsx
```

---

## Flux d'une action joueur (exemple : jouer une carte)

```
1. Joueur clique sur une carte
   → composant Card.tsx appelle gameStore.playCard(card)

2. gameStore envoie via WS : { type: "card.play", card: { rank, suit } }

3. Serveur reçoit l'événement
   → vérifie is_legal(card, player, round_state)
   → si illégal : envoie { type: "error", code: "ILLEGAL_CARD" } au joueur
   → si légal :
     new_state, events = apply_action(state, PlayCardAction(...))
     → sauvegarde new_state dans Redis
     → broadcast events à tous les joueurs de la room

4. Tous les clients reçoivent { type: "card.played", player, card, trick_state }
   → gameStore met à jour le state local
   → React re-render
```

---

## Déploiement (POC)

Pour le POC entre amis, déploiement minimal :

| Composant | Option |
|-----------|--------|
| Serveur back | VPS OVH/Hetzner, ou Railway.app |
| Redis | Redis Cloud free tier, ou Redis sur le même VPS |
| Front | Vercel (gratuit) ou servi par FastAPI (static files) |
| HTTPS/WSS | Caddy (reverse proxy + TLS automatique) |

Pas de CI/CD complexe pour le POC — un `docker-compose.yml` suffit.

---

## Flux d'authentification

```
1. Premier démarrage
   → aucun utilisateur en DB → bootstrap automatique
   → admin / <mot de passe temporaire> affiché dans les logs serveur

2. Création d'un utilisateur (admin)
   POST /admin/users { username }
   → mot de passe aléatoire 12 chars généré + haché en DB
   → mot de passe en clair retourné une seule fois dans la réponse

3. Login
   POST /auth/login { username, password }
   → vérification bcrypt
   → JWT signé (8h) placé dans un cookie HttpOnly + Secure + SameSite=Lax
   → corps de réponse : { username, is_admin, must_change_password }
   → si must_change_password=True → frontend bloque l'accès au jeu

4. Changement de mot de passe obligatoire
   POST /auth/change-password { old_password, new_password }
   → cookie présent → authentifié automatiquement
   → must_change_password passé à False en DB
   → nouveau cookie émis (JWT mis à jour)

5. Connexion WebSocket
   ws://host/ws/{room_id}/{player_id}
   → le navigateur envoie le cookie automatiquement lors du handshake HTTP
   → serveur lit le cookie dans les headers de l'upgrade request
   → rejet 403 si cookie absent/invalide/must_change_password=True

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
