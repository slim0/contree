# ADR-003 : State des parties — Redis

**Date** : 2026-06-12  
**Statut** : Accepté

## Contexte

Le serveur WebSocket est stateful par nature : il doit conserver l'état des parties en cours. Choix du mécanisme de persistance.

## Décision

Redis comme store de l'état des rooms et parties en cours.

## Justification

- L'état d'une partie de belote tient en quelques Ko de JSON
- Redis offre des lectures/écritures en mémoire en < 1ms — largement suffisant
- Simple à opérer : un seul process, pas de schéma, pas de migrations
- Permet une reconnexion des joueurs (l'état survit au redémarrage du serveur si Redis persiste)
- Free tier Redis Cloud suffisant pour le POC

## Alternatives rejetées

- **In-memory Python dict** : état perdu au redémarrage, non partageable entre workers
- **PostgreSQL** : sur-dimensionné pour un état éphémère, latence inutile pour chaque coup joué
- **SQLite** : pas adapté aux écritures concurrentes WebSocket

## Conséquences

- `GameState` doit être sérialisable en JSON (pas d'objets Python non-sérialisables dans le state)
- Le module `store/redis.py` est la seule couche qui touche Redis — le moteur de jeu n'en sait rien
- En cas de crash Redis, les parties en cours sont perdues (acceptable pour le POC)

## Évolution future

Si besoin d'historique des parties → ajouter PostgreSQL pour les `RoundResult` finalisés, sans changer l'architecture temps réel.
