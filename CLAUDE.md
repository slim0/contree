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