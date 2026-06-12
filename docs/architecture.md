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
└───────────────────┬─────────────────────────────────┘
                    │ WebSocket (ws://)
                    │ HTTP (REST minimal)
┌───────────────────▼─────────────────────────────────┐
│                    SERVEUR                          │
│              FastAPI (Python 3.12+)                 │
│         WebSocket handlers + Routes HTTP            │
│                                                     │
│    ┌────────────────────────────────────────┐       │
│    │         Moteur de jeu (pur Python)     │       │
│    │   models.py / rules.py / scoring.py   │       │
│    └────────────────────────────────────────┘       │
│                                                     │
│    ┌────────────────┐                               │
│    │     Redis      │  ← state des rooms/sessions   │
│    └────────────────┘                               │
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
├── api/
│   ├── websocket.py    # ConnectionManager, handlers WS par événement
│   ├── routes.py       # POST /rooms, GET /rooms/{id}
│   └── schemas.py      # Pydantic models pour les payloads WS et HTTP
├── store/
│   └── redis.py        # Lecture/écriture du GameState dans Redis
├── tests/
│   ├── test_rules.py
│   ├── test_scoring.py
│   └── test_websocket.py
└── main.py
```

### État du jeu
- **Redis** pour stocker le `GameState` sérialisé (JSON) par room
- Pas de base de données relationnelle pour le POC (pas d'historique persistant)
- Clé Redis : `room:{room_id}:state`

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

## Ce que cette architecture ne fait PAS (intentionnellement)

- Pas d'auth réelle (un `player_id` généré côté client suffit pour jouer entre amis)
- Pas d'historique des parties en base de données
- Pas de spectateurs
- Pas de matchmaking
- Pas de rooms publiques

Ces features ne sont pas dans le scope du POC. Les ajouter plus tard ne nécessite pas de refonte architecturale.
