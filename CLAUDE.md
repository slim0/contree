# Belote Contrée — Contexte Projet pour Claude Code

## Vue d'ensemble

Application web multijoueur de **belote contrée** (4 joueurs, 2 équipes).
Objectif actuel : **POC jouable entre amis** — fonctionnel avant tout, pas de polish UI.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Back-end | Python 3.12+ / FastAPI / WebSocket |
| State en mémoire | Dict Python asyncio (rooms, sessions de jeu) |
| Base de données | SQLite (via SQLAlchemy — swappable via `DATABASE_URL`) |
| Auth | PyJWT + bcrypt |
| Rate limiting | slowapi (en mémoire, par IP) |
| Type checking | ty (via uv) |
| Linter/formatter | ruff (via uv) |
| Front-end | React + TypeScript (Vite) |
| State management | Zustand |
| CSS | Tailwind CSS |
| Conteneurisation | Docker + Docker Compose |

## Structure du repo

```
contree
├── CLAUDE.md                   ← tu es ici
├── Dockerfile.backend          ← image Python (targets: dev, prod)
├── docker-compose.yml          ← dev local (hot-reload)
├── docker-compose.prod.yml     ← déploiement (nginx + uvicorn)
├── .dockerignore
├── pyproject.toml              ← dépendances Python (uv)
├── backend/
│   ├── game/                   ← moteur de jeu pur (pas d'I/O)
│   │   ├── models.py           ← entités : Card, Trick, Round, GameState...
│   │   ├── rules.py            ← is_legal(), logique de jeu
│   │   └── scoring.py          ← calcul du score
│   ├── db/
│   │   ├── database.py         ← engine SQLAlchemy + session factory (DATABASE_URL)
│   │   └── models.py           ← modèles ORM (User...)
│   ├── users/
│   │   ├── repository.py       ← UserRepository : SEUL point d'accès DB
│   │   └── schemas.py          ← Pydantic : UserCreate, UserResponse
│   ├── auth/
│   │   ├── service.py          ← hash/verify password, create/decode JWT (JWT_SECRET_KEY)
│   │   ├── dependencies.py     ← FastAPI deps : get_current_user, require_admin
│   │   └── schemas.py          ← LoginRequest, TokenResponse, ChangePasswordRequest
│   ├── api/
│   │   ├── websocket.py        ← handlers WebSocket
│   │   ├── routes.py           ← routes HTTP (créer room, rejoindre...)
│   │   ├── auth_routes.py      ← POST /auth/login, POST /auth/change-password
│   │   └── admin_routes.py     ← POST/GET/DELETE /admin/users
│   ├── store/
│   │   └── memory_store.py     ← état des rooms en mémoire (dict asyncio)
│   └── tests/
│       ├── test_rules.py
│       ├── test_scoring.py
│       ├── test_auth.py
│       └── test_users.py
└── frontend/
    ├── Dockerfile              ← image Node (targets: dev, builder, prod)
    ├── nginx.conf              ← config nginx pour le target prod
    ├── .dockerignore
    ├── vite.config.ts          ← proxy /api et /ws vers BACKEND_URL
    ├── src/
    │   ├── components/
    │   │   ├── auth/           ← LoginPage, ChangePasswordPage
    │   │   └── admin/          ← AdminPanel (gestion utilisateurs)
    │   ├── store/              ← Zustand stores
    │   │   └── authStore.ts    ← user courant (username, is_admin, must_change_password) — pas de JWT
    │   └── websocket/          ← client WS
    └── ...
```

## Lancer l'application avec Docker

### Dev (hot-reload)

```bash
docker compose up --build
```

- Backend : http://localhost:8000 (rechargement automatique sur modif Python)
- Frontend : http://localhost:3000 (hot-reload Vite sur modif TypeScript/React)
- La base SQLite est persistée dans le volume `sqlite_data`

### Prod

```bash
JWT_SECRET_KEY=<clé-longue-aléatoire> docker compose -f docker-compose.prod.yml up --build -d
```

- Un seul port exposé : http://localhost:80
- nginx sert le build statique React et proxie `/api` et `/ws` vers le backend

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | `sqlite:////app/data/contree.db` | URI SQLAlchemy |
| `JWT_SECRET_KEY` | `change-me-in-production…` | Clé de signature JWT — **obligatoire en prod** |
| `BACKEND_URL` | `http://localhost:8000` | URL backend vue du container frontend (dev only) |

## Règles métier critiques — NE JAMAIS VIOLER

1. **Montée obligatoire à l'atout** : quand on joue atout (couleur demandée ou coupe), on doit toujours jouer plus fort que l'atout en place, sauf si impossible ("ne pisse pas").
2. **Belote** : annoncée **automatiquement par le jeu**. Compte dans l'évaluation du contrat pour les preneurs uniquement. En contrat réussi, les défenseurs marquent leur belote (+20) si annoncée. En chute, aucune belote n'est comptabilisée. Jamais multipliée par le contre/surcontre.
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
3. Front React minimaliste (jouable, pas beau)
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
- **Noms d'équipe** : NS → **NOUS**, EW → **EUX** dans toute l'interface.
- **Layout** : header compact (scores + contrat sur une ligne), table losange, panel enchères. Pas d'éléments verticalement trop hauts qui empêchent le jeu en paysage.

## Contexte pour la génération de code

- Le moteur de jeu (`backend/game/`) doit être **pur** : aucune dépendance externe, aucun I/O, testable seul
- Les WebSockets transportent des événements typés (voir `docs/architecture.md`)
- Ne pas utiliser Socket.io — WebSocket natif côté front

## Système d'authentification

### Principes fondamentaux

- **Repository pattern** : toutes les requêtes DB passent par `UserRepository`. C'est le seul endroit à modifier pour changer de base de données.
- **DB-agnostic** : SQLAlchemy comme ORM. Passer de SQLite à PostgreSQL = changer uniquement la variable d'environnement `DATABASE_URL`.
- **État de jeu séparé** : la DB ne stocke que les utilisateurs. Le `GameState` reste dans Redis.
- **JWT stateless** : tokens 8h, pas de refresh token pour le POC. Payload : `user_id`, `username`, `is_admin`, `must_change_password`.
- **Cookie HttpOnly** : le JWT n'est jamais exposé au JavaScript. Il transite uniquement dans un cookie `access_token` (HttpOnly, Secure, SameSite=Lax) posé par le serveur à la connexion.
- **CORS** : `allow_credentials=True` avec origines explicites — jamais de wildcard `*` quand les cookies sont en jeu.

### Modèle User

```python
id: int
username: str          # unique, pas d'email
hashed_password: str   # bcrypt via passlib
is_admin: bool
must_change_password: bool   # True à la création, False après premier changement
created_at: datetime
```

### Flux d'authentification

1. **Bootstrap** : au démarrage, si aucun utilisateur n'existe → création automatique d'un compte `admin` avec mot de passe temporaire affiché dans les logs serveur (une seule fois).
2. **Création** : `POST /admin/users` (admin only) → mot de passe aléatoire 12 chars retourné dans la réponse (une seule fois, non re-consultable).
3. **Login** : `POST /auth/login` → cookie HttpOnly `access_token` posé + corps `{ username, is_admin, must_change_password }`. Si `must_change_password=True` → le frontend bloque l'accès au jeu.
4. **Changement de mot de passe** : `POST /auth/change-password` → cookie présent, authentifié automatiquement → flag `must_change_password` passé à `False` en DB → nouveau cookie émis.
5. **Connexion WebSocket** : le navigateur envoie le cookie automatiquement lors du handshake — pas de token dans l'URL. Le serveur le lit depuis les headers de l'upgrade request.
6. **Logout** : `POST /auth/logout` → cookie supprimé (max_age=0).

### Conventions auth

- Ne jamais stocker le mot de passe en clair, même temporairement
- Le mot de passe temporaire n'est retourné qu'une seule fois (à la création) — aucune route de consultation
- Les routes `/admin/*` vérifient `is_admin=True` via la dépendance `require_admin`
- Les routes de jeu (rooms, WebSocket) vérifient l'auth via `get_current_user`
- Le frontend ne stocke **jamais** le JWT — `authStore` contient uniquement `{ username, is_admin, must_change_password }` reçus dans le corps des réponses
- Le fetch frontend doit toujours inclure `credentials: 'include'` pour que le cookie parte avec les requêtes cross-origin


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