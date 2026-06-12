# Belote Contrée — Contexte Projet pour Claude Code

## Vue d'ensemble

Application web multijoueur de **belote contrée** (4 joueurs, 2 équipes).
Objectif actuel : **POC jouable entre amis** — fonctionnel avant tout, pas de polish UI.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Back-end | Python 3.12+ / FastAPI / WebSocket |
| State en mémoire | Redis (rooms, sessions de jeu) |
| Front-end | React + TypeScript (Vite) |
| State management | Zustand |
| CSS | Tailwind CSS |

## Structure du repo

```
contree
├── CLAUDE.md                   ← tu es ici
├── backend/
│   ├── game/                   ← moteur de jeu pur (pas d'I/O)
│   │   ├── models.py           ← entités : Card, Trick, Round, GameState...
│   │   ├── rules.py            ← is_legal(), logique de jeu
│   │   └── scoring.py          ← calcul du score
│   ├── api/
│   │   ├── websocket.py        ← handlers WebSocket
│   │   └── routes.py           ← routes HTTP (créer room, rejoindre...)
│   └── tests/
│       ├── test_rules.py
│       └── test_scoring.py
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── store/              ← Zustand stores
    │   └── websocket/          ← client WS
    └── ...
```

## Règles métier critiques — NE JAMAIS VIOLER

1. **Montée obligatoire à l'atout** : quand on joue atout (couleur demandée ou coupe), on doit toujours jouer plus fort que l'atout en place, sauf si impossible ("ne pisse pas").
2. **Belote et camp** : la belote (20 pts) appartient toujours à l'équipe qui l'annonce — SAUF si cette équipe chute, auquel cas elle va aux adversaires. Elle n'est jamais multipliée par le contre/surcontre.
3. **Dix de der** : 10 pts en jeu normal, 100 pts en cas de capot. Inclus dans les points faits.
4. **Total des points** : 162 pts en jeu normal (152 cartes + 10 dix de der), 252 pts en capot.
5. **Arrondi** : à la dizaine la plus proche — 85 → 90, 84 → 80.
6. **4 passes sans enchère** : la donne est annulée, les cartes repassent au donneur suivant.
7. **Surcontre** : termine immédiatement le tour d'enchères.
8. **Variante Sans Atout** : As vaut 19 pts (au lieu de 11). Pas de belote/rebelote possible. Carrés bonus applicables.
9. **Variante Tout Atout** : montée obligatoire s'applique *toujours* (toutes couleurs sont atout). Jusqu'à 4 belotes possibles.

## Méthode de comptage

**Points faits uniquement** (pas de points demandés ajoutés au score).

```
Contrat réussi :
  preneurs  → points_faits (arrondis)
  défenseurs → points_faits (arrondis)

Chute :
  preneurs  → 0
  défenseurs → totalité des points (162 arrondis, ou 252 si capot)
  + belote des preneurs va aux défenseurs
```

Multiplicateur contre/surcontre s'applique sur les points faits des défenseurs en cas de chute.

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

## Contexte pour la génération de code

- Le moteur de jeu (`backend/game/`) doit être **pur** : aucune dépendance externe, aucun I/O, testable seul
- Les WebSockets transportent des événements typés (voir `docs/architecture.md`)
- Ne pas utiliser Socket.io — WebSocket natif côté front
