# ADR-003 : State des parties — Redis

**Date** : 2026-06-12  
**Statut** : **Superseded** par un dict Python en mémoire (`backend/store/memory_store.py`)

> **Note de pivot** : cette décision n'a finalement pas été implémentée. Le POC tourne en
> single-worker et n'a pas eu besoin de partager l'état entre process ni de le faire
> survivre à un redémarrage — l'alternative "in-memory Python dict", listée ci-dessous
> comme rejetée, est celle réellement en place. Voir `backend/store/memory_store.py`
> (dict protégé par `asyncio.Lock`) et CLAUDE.md ("State en mémoire"). Aucune dépendance
> Redis n'existe dans le code ou `pyproject.toml`. Si le besoin de partage multi-worker
> ou de persistance au redémarrage redevient réel, réévaluer Redis à ce moment-là plutôt
> que de le réintroduire par anticipation.

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
