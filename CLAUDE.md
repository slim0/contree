# Belote Contrée — Contexte Projet pour Claude Code

## Vue d'ensemble

Application web multijoueur de **belote contrée** (4 joueurs, 2 équipes).
Objectif actuel : Focus sur le fonctionnel, puis polish UI.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Back-end | Python 3.12+ / FastAPI / WebSocket |
| State en mémoire | Dict Python asyncio (rooms, sessions de jeu) |
| Base de données | PocketBase (collection `users`) — le backend y accède en superuser via `httpx` |
| Auth | PyJWT (cookie de session) + PocketBase (stockage + hachage des mots de passe) |
| Rate limiting | slowapi (en mémoire, par IP) |
| Type checking | ty (via uv) |
| Linter/formatter | ruff (via uv) |
| Front-end | React + TypeScript (Vite) |
| State management | Zustand (auth uniquement — le reste, dont l'état de partie, est en `useState` local dans `App.tsx`/`Game.tsx`) |
| CSS | CSS custom (`frontend/index.html`) + styles inline — pas de Tailwind installé |
| Voix | WebRTC P2P (signaling relayé via le WebSocket de jeu) |
| Conteneurisation | Docker + Docker Compose |

## Structure du repo

```
contree
├── CLAUDE.md                   ← tu es ici
├── Dockerfile.backend          ← image Python (targets: dev, prod)
├── Dockerfile.pocketbase       ← image PocketBase (binaire + migrations)
├── docker-compose.yml          ← dev local (hot-reload)
├── docker-compose.prod.yml     ← déploiement (nginx + uvicorn)
├── .dockerignore
├── pyproject.toml              ← dépendances Python (uv)
├── pocketbase/
│   ├── pb_migrations/          ← migrations JS (schéma de la collection "users")
│   └── docker-entrypoint.sh    ← upsert du superuser puis `pocketbase serve`
├── backend/
│   ├── game/                   ← moteur de jeu pur (pas d'I/O)
│   │   ├── models.py           ← entités : Card, Trick, Round, GameState...
│   │   ├── rules.py            ← is_legal(), logique de jeu
│   │   └── scoring.py          ← calcul du score
│   ├── pocketbase/
│   │   └── client.py           ← PocketBaseClient : auth superuser + REST vers la collection users
│   ├── users/
│   │   ├── models.py           ← dataclass User (id str, username, is_admin, must_change_password...)
│   │   ├── repository.py       ← UserRepository : SEUL point d'accès aux comptes (proxie PocketBaseClient)
│   │   └── schemas.py          ← Pydantic : UserCreate, UserResponse
│   ├── auth/
│   │   ├── service.py          ← create/decode JWT (JWT_SECRET_KEY), generate_temp_password
│   │   ├── dependencies.py     ← FastAPI deps : get_current_user, require_admin
│   │   └── schemas.py          ← LoginRequest, TokenResponse, ChangePasswordRequest
│   ├── api/
│   │   ├── websocket.py        ← handlers WebSocket (jeu + signaling WebRTC voix)
│   │   ├── routes.py           ← routes HTTP (créer room, rejoindre...)
│   │   ├── auth_routes.py      ← POST /auth/login, POST /auth/change-password
│   │   ├── admin_routes.py     ← POST/GET/DELETE /admin/users
│   │   ├── dev_routes.py       ← routes de dev (autologin, quickstart), montées seulement si DEVELOPMENT=true
│   │   └── limiter.py          ← instance slowapi partagée
│   ├── store/
│   │   └── memory_store.py     ← état des rooms en mémoire (dict asyncio)
│   └── tests/
│       ├── test_rules.py
│       ├── test_scoring.py
│       ├── test_belote.py
│       ├── test_bidding_volee.py
│       ├── test_auth.py
│       ├── test_users.py
│       ├── test_dev_routes.py
│       ├── test_leave_room.py
│       ├── test_rate_limiting.py
│       ├── test_team_selection.py
│       └── test_websocket_reconnect.py
└── frontend/
    ├── Dockerfile              ← image Node (targets: dev, builder, prod)
    ├── nginx.conf              ← config nginx pour le target prod
    ├── .dockerignore
    ├── vite.config.ts          ← proxy /api et /ws vers BACKEND_URL
    ├── src/
    │   ├── App.tsx             ← lobby + client WebSocket (connect/reconnect/dispatch inline, pas de module websocket/ dédié)
    │   ├── Game.tsx            ← table, cartes, enchères, plis, scores (fichier unique)
    │   ├── components/
    │   │   ├── auth/           ← LoginPage, ChangePasswordPage
    │   │   └── admin/          ← AdminPanel (gestion utilisateurs)
    │   ├── voice/              ← VoiceManager (WebRTC P2P chat vocal)
    │   └── store/              ← Zustand stores
    │       └── authStore.ts    ← user courant (username, is_admin, must_change_password) — pas de JWT
    └── ...
```

## Lancer l'application avec Docker

### Dev (hot-reload)

```bash
docker compose up --build
```

- Backend : http://localhost:8000 (rechargement automatique sur modif Python)
- Frontend : http://localhost:3000 (hot-reload Vite sur modif TypeScript/React)
- PocketBase : http://localhost:8090 (dashboard admin sur `/_/`)
- Les données PocketBase sont persistées dans le volume `pocketbase_data`

### Prod

```bash
JWT_SECRET_KEY=<clé-longue-aléatoire> docker compose -f docker-compose.prod.yml up --build -d
```

- Un seul port exposé : http://localhost:80
- nginx sert le build statique React et proxie `/api` et `/ws` vers le backend

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `PB_URL` | `http://localhost:8090` | URL de l'instance PocketBase vue du backend |
| `PB_SUPERUSER_EMAIL` | — | Email du superuser PocketBase (service account backend) — **obligatoire en prod** |
| `PB_SUPERUSER_PASSWORD` | — | Mot de passe du superuser PocketBase — **obligatoire en prod** |
| `JWT_SECRET_KEY` | `change-me-in-production…` | Clé de signature JWT (cookie de session) — **obligatoire en prod** |
| `BACKEND_URL` | `http://localhost:8000` | URL backend vue du container frontend (dev only) |

## Règles métier critiques — NE JAMAIS VIOLER

1. **Montée obligatoire à l'atout** : quand on joue atout (couleur demandée ou coupe), on doit toujours jouer plus fort que l'atout en place, sauf si impossible ("ne pisse pas").
2. **Belote** : détectée **automatiquement par le jeu**, à condition que le **roi ET la dame d'atout soient dans la main d'un seul et même joueur** — si les deux cartes sont réparties entre les deux partenaires, ça ne compte pas. Ne compte **que pour l'équipe qui a pris l'annonce (les preneurs)** : jamais pour la défense, même si la défense la détient. Compte dans l'évaluation du contrat pour les preneurs uniquement (+20 sur les points faits pour juger si le contrat est réussi). En chute, aucune belote n'est comptabilisée pour personne. Jamais multipliée par le contre/surcontre. **Révélation aux joueurs** : le camp détenteur n'est connu du moteur de jeu dès le début du tour de jeu, mais n'est communiqué aux clients (et affiché en haut de l'écran) qu'au moment où le roi **ou** la dame d'atout est effectivement joué·e — jamais avant.
3. **Dix de der** : toujours **10 pts**, y compris en cas de capot.
4. **Total des points** : toujours **162 pts** (152 cartes + 10 dix de der).
5. **4 passes sans enchère** : la donne est annulée, les cartes repassent au donneur suivant.
6. **Surcontre** : termine immédiatement le tour d'enchères.
7. **Variante Sans Atout** : As vaut 19 pts (au lieu de 11). Pas de belote/rebelote possible. Carrés bonus applicables.
8. **Variante Tout Atout** : montée obligatoire s'applique *toujours* (toutes couleurs sont atout). Pas de belote possible.

## Méthode de comptage

**Points annoncés** (valeur du contrat, pas les points faits).

```
Contrat réussi :
  preneurs   → valeur_annoncée × multiplicateur
  défenseurs → 0 (+ 20 si leur belote annoncée)

Chute :
  preneurs   → 0
  défenseurs → valeur_annoncée × multiplicateur
```

Multiplicateur contre/surcontre s'applique sur la valeur annoncée en cas de chute.
Capot comme contrat = 160 pts.

## Ordre de priorité de développement

1. Moteur de jeu Python pur (models + rules + scoring) avec tests
2. API WebSocket FastAPI
3. Front React
4. Amélioration UI/UX (phase post-POC)

## Conventions de code

- **Python** : type hints partout, dataclasses ou Pydantic, pas de magic strings → utiliser les enums
- **TypeScript** : strict mode activé, pas de `any`
- **Tests** : chaque règle de jeu a au moins un test unitaire avant son implémentation (TDD)
- **Nommage** : anglais pour le code, français pour les commentaires métier complexes

## Contraintes front-end — à respecter impérativement

- **Mobile paysage uniquement** : le front doit être jouable sur mobile en orientation **paysage** (landscape). Portrait toléré mais pas prioritaire. Cible : ~667×375px (iPhone SE landscape).
- **Pas de journal** : les joueurs ne voient pas l'historique des actions. La seule rétrospective autorisée est le **dernier pli** (bouton toggle dans la zone de pli).
- **Symboles de couleur** : toujours utiliser ♥ ♦ ♣ ♠, jamais les lettres H/D/C/S dans les textes affichés.
- **Noms d'équipe** : NS → **TEAM RED**, EW → **TEAM BLUE** dans toute l'interface (`frontend/src/Game.tsx` — `TEAM_LABEL`).
- **Layout** : header compact (scores + contrat sur une ligne), table losange, panel enchères. Pas d'éléments verticalement trop hauts qui empêchent le jeu en paysage.

## Contexte pour la génération de code

- Le moteur de jeu (`backend/game/`) doit être **pur** : aucune dépendance externe, aucun I/O, testable seul
- Les WebSockets transportent des événements typés (voir `docs/architecture.md`)
- Ne pas utiliser Socket.io — WebSocket natif côté front

## Chat vocal (WebRTC)

- **Signaling relayé via le WebSocket de jeu existant** — pas de serveur de signaling dédié. Messages `webrtc-offer`/`webrtc-answer`/`webrtc-ice-candidate` (client → serveur → autres clients de la room) gérés dans `backend/api/websocket.py` (`_voice_peers`, `_broadcast_voice`, dispatch dans `handle_connection`). Accepté à toute phase de partie, y compris `WAITING` (chat avant le début de la manche).
- **P2P audio réel** : `frontend/src/voice/VoiceManager.ts` ouvre une connexion `RTCPeerConnection` par pair (4 joueurs max), avec détection de parole via `AudioContext`/`AnalyserNode`. STUN public Google par défaut, **pas de serveur TURN** — la connexion peut échouer derrière certains NAT stricts.
- **Pas de belote/rebelote concernée** — feature indépendante des règles de jeu.
- **Limites connues** : pas de TURN, pas de tests automatisés sur `VoiceManager.ts` (seul le bouton mute est testé côté UI), pas de gestion de mixage audio multi-pairs.

## Système d'authentification

### Principes fondamentaux

- **PocketBase = source de vérité des comptes** : stockage des utilisateurs, hachage et vérification des mots de passe sont entièrement délégués à PocketBase (collection `users`, voir `pocketbase/pb_migrations/`). Le backend ne hache ni ne compare jamais de mot de passe lui-même.
- **Backend = superuser PocketBase** : le backend s'authentifie auprès de PocketBase comme superuser (`PB_SUPERUSER_EMAIL`/`PB_SUPERUSER_PASSWORD`, compte de service distinct des comptes métier) et proxie tout accès via `PocketBaseClient` (`backend/pocketbase/client.py`). Aucune règle d'API PocketBase n'est ouverte au public — pas d'inscription ni d'accès direct depuis le frontend.
- **Repository pattern** : toutes les opérations sur les comptes passent par `UserRepository` (`backend/users/repository.py`), qui enveloppe `PocketBaseClient`. C'est le seul endroit à modifier pour changer de backend de stockage.
- **État de jeu séparé** : PocketBase ne stocke que les utilisateurs. Le `GameState` reste en mémoire (`backend/store/memory_store.py`).
- **Cookie de session propre au backend** : malgré PocketBase, le backend continue d'émettre son propre JWT stateless (8h, pas de refresh token) dans le cookie `access_token` — ni le frontend ni le WebSocket ne voient jamais de token PocketBase. Payload : `sub` (id PocketBase, string), `username`, `is_admin`, `must_change_password`.
- **Cookie HttpOnly** : le JWT n'est jamais exposé au JavaScript. Il transite uniquement dans un cookie `access_token` (HttpOnly, Secure, SameSite=Lax) posé par le serveur à la connexion.
- **CORS** : `allow_credentials=True` avec origines explicites — jamais de wildcard `*` quand les cookies sont en jeu.

### Modèle User (`backend/users/models.py`)

```python
id: str                 # id de record PocketBase (15 caractères), pas un entier
username: str            # unique, pas d'email — champ custom ajouté à la collection users
is_admin: bool
must_change_password: bool   # True à la création, False après premier changement
created_at: datetime
```

Le mot de passe n'apparaît jamais dans ce modèle côté backend : il est écrit en clair
une seule fois vers PocketBase à la création/au changement (PocketBase le hache),
et vérifié via `PocketBaseClient.verify_credentials()` (délègue à l'endpoint
`auth-with-password` de PocketBase).

### Flux d'authentification

1. **Bootstrap** : au démarrage, le backend attend que PocketBase soit joignable (`_wait_for_pocketbase`), puis si aucun utilisateur n'existe → création automatique d'un compte `admin` avec mot de passe temporaire affiché dans les logs serveur (une seule fois).
2. **Création** : `POST /admin/users` (admin only) → mot de passe aléatoire 12 chars généré par le backend, transmis en clair à PocketBase (qui le hache), retourné dans la réponse HTTP (une seule fois, non re-consultable).
3. **Login** : `POST /auth/login` → `UserRepository.verify_credentials()` délègue la vérification à PocketBase → cookie HttpOnly `access_token` (JWT du backend) posé + corps `{ username, is_admin, must_change_password }`. Si `must_change_password=True` → le frontend bloque l'accès au jeu.
4. **Changement de mot de passe** : `POST /auth/change-password` → l'ancien mot de passe est vérifié via `verify_credentials()` (un appel PocketBase), le nouveau est écrit via `UserRepository.update_password()` → flag `must_change_password` passé à `False` côté PocketBase → nouveau cookie émis.
5. **Connexion WebSocket** : le navigateur envoie le cookie automatiquement lors du handshake — pas de token dans l'URL. Le serveur le lit depuis les headers de l'upgrade request (JWT du backend, jamais PocketBase).
6. **Logout** : `POST /auth/logout` → cookie supprimé (max_age=0).

### Conventions auth

- Ne jamais hacher ou comparer de mot de passe côté backend — c'est le rôle de PocketBase
- Le mot de passe temporaire n'est retourné qu'une seule fois (à la création) — aucune route de consultation
- Les routes `/admin/*` vérifient `is_admin=True` via la dépendance `require_admin`
- Les routes de jeu (rooms, WebSocket) vérifient l'auth via `get_current_user`
- Le frontend ne stocke **jamais** de JWT (ni backend ni PocketBase) — `authStore` contient uniquement `{ username, is_admin, must_change_password }` reçus dans le corps des réponses
- Le fetch frontend doit toujours inclure `credentials: 'include'` pour que le cookie parte avec les requêtes cross-origin
- La collection PocketBase `users` n'a aucune règle d'API publique (`listRule`/`viewRule`/`createRule`/`updateRule`/`deleteRule` = `null`) — accès superuser uniquement, via le backend


## Rate limiting

Tous les endpoints HTTP utilisent `slowapi` avec le rate limiter par IP (`get_remote_address`).

### Règle : tout nouvel endpoint doit avoir un `@limiter.limit(...)`

```python
from backend.api.limiter import limiter
from fastapi import Request

@router.post("/mon-endpoint")
@limiter.limit("10/minute")  # ← obligatoire
async def mon_endpoint(request: Request, ...):
    ...
```

Le paramètre `request: Request` est **obligatoire** pour que slowapi fonctionne.

Cette règle s'applique aussi à `backend/api/dev_routes.py`, bien que ces routes ne soient montées que si `DEVELOPMENT=true` — aucune exception "dev" au rate limiting.

### Rates de référence par catégorie

| Catégorie | Rate | Exemples |
|-----------|------|----------|
| Credential (login, change-password) | **5/minute** | POST /auth/login, POST /auth/change-password |
| Écriture légère | **10/minute** | logout, create_user, delete_user, create_room |
| Lecture admin / modération | **30/minute** | GET /admin/users |
| Lecture fréquente (polling, me) | **60/minute** | GET /auth/me, GET /rooms, GET /rooms/{id} |

### Tests

Chaque nouvel endpoint limité doit avoir un test dans `backend/tests/test_rate_limiting.py` qui vérifie que le (N+1)e appel retourne `429`. Le limiter est réinitialisé automatiquement entre chaque test via la fixture `reset_rate_limiter` dans `conftest.py`.

---

## Type checking (ty)

Le projet utilise **ty** (Astral) comme type checker Python, lancé via `uv run ty check backend`.

### Règles

- `ty` vérifie uniquement le dossier `backend/` — le dossier `.venv` est exclu
- Tout nouveau code Python doit passer `ty check` sans nouvelle erreur
- Les `assert x is not None` sont la méthode préférée pour narrower les `Optional` — ils documentent les invariants et lèvent une `AssertionError` visible en runtime
- Éviter les `# type: ignore` sauf pour des limitations de typage de bibliothèques tierces (slowapi, starlette) — utiliser `# ty: ignore[rule-name]` dans ce cas
- La configuration est dans `pyproject.toml` sous `[tool.ty]`

### Lancer ty

```bash
uv run ty check backend
```

---

## Linter / Formatter (ruff)

Le projet utilise **ruff** pour le linting et le formatting Python.

### Règles

- Configuration dans `pyproject.toml` sous `[tool.ruff]`
- Règles actives : E, W, F (pycodestyle/pyflakes), I (isort), UP (pyupgrade), B (bugbear), SIM (simplify)
- `B008` ignoré (pattern FastAPI `Depends()`)
- `E501` ignoré (longueur de ligne gérée par le formatter)
- Le hook Claude applique automatiquement ruff sur chaque fichier `.py` modifié

### Lancer ruff

```bash
uv run ruff check backend/        # lint
uv run ruff check --fix backend/  # lint + auto-fix
uv run ruff format backend/       # format
```

---

## Stratégie de tests

### Règle absolue
Tout changement de code — nouvelle feature OU correction de bug — doit être
accompagné de ses tests dans le même commit. Pas de code sans tests.

Pour une correction de bug en particulier : écrire d'abord un test qui
**reproduit le bug** (il doit échouer avant le fix, passer après).
Ce test sert de régression pour éviter que le bug ne réapparaisse.

### Backend (FastAPI + pytest)

Stack :
- pytest pour les tests unitaires
- httpx + pytest-asyncio pour les routes FastAPI
- pytest-cov pour la couverture de code

Emplacement : backend/tests/
Convention de nommage : test_<module_testé>.py

**Prérequis** : les tests d'auth/users tournent contre une vraie instance PocketBase,
démarrée automatiquement par `conftest.py` (fixture `pb_server`, session-scoped) sur un
port libre avec un data-dir temporaire. Le binaire `pocketbase` doit être sur le `PATH`
(ou `POCKETBASE_BIN` pointer dessus) pour lancer les tests backend en local.

Pour chaque feature back, tu dois écrire :
1. Tests unitaires sur la logique métier pure (indépendants de FastAPI)
   → Ex : logique de jeu, calcul de score, validation des règles belote
2. Tests d'intégration sur les routes HTTP / WebSocket si concernées
3. Couvrir les cas nominaux ET les cas d'erreur / edge cases

Commande pour lancer les tests back :
cd backend && pytest --cov=. --cov-report=term-missing

### Frontend (Vitest + React Testing Library)

Stack :
- vitest comme test runner (natif Vite, pas de config webpack)
- @testing-library/react pour tester les composants
- @testing-library/user-event pour simuler les interactions
- jsdom comme environnement DOM

Emplacement : frontend/src/__tests__/ ou colocalisé ComponentName.test.tsx
Convention de nommage : <NomComposant>.test.tsx

Pour chaque feature front, tu dois écrire :
1. Tests sur le comportement utilisateur (ce que l'utilisateur voit et fait)
   → Ne pas tester les détails d'implémentation (state interne, noms de fonctions)
2. Tester le rendu conditionnel, les interactions (clic, saisie), les états d'erreur
3. Mocker les appels API/WebSocket — ne jamais appeler le vrai backend en test

Commande pour lancer les tests front :
cd frontend && npm run test

### Priorités de test pour ce projet

La logique métier belote est complexe et critique. Ordre de priorité :
1. Logique de jeu — ordre des cartes, obligation de monter, couper, défausser
2. Calcul du score — points faits, contre/surcontre, belote/rebelote, dix de der
3. Enchères — validation des enchères, contre, surcontre, capot
4. Routes API / WebSocket — connexion, déconnexion, synchronisation d'état
5. Composants UI — affichage des cartes, phase de jeu active, scores

## Structure du monorepo

belote-contree/
├── backend/   # FastAPI
└── frontend/  # Vite + React

## Checklist obligatoire avant toute implémentation de feature

⚠ Avant d'écrire la moindre ligne de code, tu dois répondre explicitement
à ces deux questions dans ton plan :

1. Est-ce que cette feature nécessite un changement backend ?
   → Nouvelle route, modification de logique métier, nouveau message WebSocket,
     changement de modèle de données, nouveau calcul de score, etc.

2. Est-ce que cette feature nécessite un changement frontend ?
   → Nouveau composant, appel API, affichage d'un nouvel état, interaction utilisateur, etc.

Si la réponse est oui des deux côtés : tu implémentes les deux dans la même tâche.
Ne jamais livrer une feature à moitié — un front sans back (ou l'inverse) n'est pas
une feature, c'est du code mort.

## Ordre d'implémentation

Toujours dans cet ordre :
1. Backend — logique métier + route/WebSocket + tests
2. Frontend — appel API/WebSocket + composant + tests
3. Vérification end-to-end — le flux complet fonctionne de bout en bout

## Cas particuliers acceptables

Les seuls cas où une implémentation mono-côté est légitime :
- Feature purement visuelle sans aucun échange avec le backend
  (ex : animation, refactoring de composant, thème)
- Feature purement backend sans surface utilisateur
  (ex : tâche de maintenance, optimisation interne)

Dans ces cas, tu dois explicitement justifier pourquoi l'autre côté
n'est pas impacté avant de commencer.
