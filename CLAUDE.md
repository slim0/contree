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
