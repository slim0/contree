# ADR-001 : Langage back-end — Python

**Date** : 2026-06-12  
**Statut** : Accepté

## Contexte

Choix du langage pour le back-end, notamment le moteur de jeu et l'API WebSocket.

## Décision

Python 3.12+ avec FastAPI.

## Justification

- Le développeur principal est dev Python back-end — zéro coût d'apprentissage
- La logique métier de la belote est complexe ; changer de langage aurait un coût d'opportunité élevé sur un POC
- FastAPI offre le WebSocket natif, le typage via Pydantic, et les performances async suffisantes pour un jeu à 4 joueurs
- L'écosystème Python est suffisant pour toutes les phases du projet

## Alternatives rejetées

- **Node.js / TypeScript full-stack** : pertinent si le dev était front-end, pas ici
- **Go** : performances inutiles pour le POC, courbe d'apprentissage

## Conséquences

- Le moteur de jeu est en Python pur, testable sans serveur
- Le typage est assuré via `dataclasses`, `Enum`, et `Pydantic` — pas de dict non typés
