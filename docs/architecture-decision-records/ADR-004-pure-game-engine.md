# ADR-004 : Moteur de jeu — module pur sans I/O

**Date** : 2026-06-12  
**Statut** : Accepté

## Contexte

La logique de la belote contrée est complexe et dense en règles interdépendantes. Choix de l'organisation du code du moteur.

## Décision

Le moteur de jeu (`backend/game/`) est un module Python **pur** : aucune dépendance externe, aucun I/O, aucune connaissance de FastAPI, Redis, ou WebSocket.

Toutes les fonctions du moteur sont des **fonctions pures** : même entrée → même sortie, pas d'effets de bord.

```python
# Pattern imposé :
new_state, events = apply_action(current_state, action)
```

## Justification

- Testabilité maximale : chaque règle peut être testée sans serveur, sans Redis, sans front
- Isolation des bugs : si une règle est fausse, le test échoue immédiatement
- Facilite la collaboration avec Claude Code : les prompts de génération de code sont ciblés sur une fonction précise avec des entrées/sorties claires
- L'immutabilité évite les bugs de state partagé dans un contexte async

## Conséquences

- TDD obligatoire : chaque règle a un test avant son implémentation
- `GameState` et les entités du domaine doivent être immutables (dataclasses frozen ou reconstruction)
- Le serveur FastAPI appelle le moteur et gère la persistance — pas l'inverse
- Les `events` retournés par `apply_action` sont broadcastés aux clients par la couche WebSocket

## Pattern de développement recommandé

1. Écrire le test (cas nominal + cas limite)
2. Implémenter la fonction dans le moteur
3. Vérifier que le test passe
4. Exposer via l'API WebSocket
