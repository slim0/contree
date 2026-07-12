# Objectif

Je souhaite ajouter un chat vocal temps réel à mon application de coinche.

Avant de modifier le code, analyse complètement le projet afin de comprendre son architecture.

## Phase 1 : Analyse

Explique-moi :

* comment est organisée l'application
* comment les joueurs rejoignent une partie
* comment les WebSockets sont utilisés
* où sont gérées les parties
* où se trouve le code frontend
* où se trouve le backend
* quels fichiers devront être modifiés

Ne modifie encore aucun fichier.

## Phase 2 : Proposition d'architecture

Je veux une solution :

* utilisant WebRTC
* sans serveur média (P2P uniquement)
* avec uniquement 4 joueurs maximum par table
* utilisant le serveur existant uniquement pour la signalisation WebRTC
* sans dépendance inutile
* compatible avec les navigateurs modernes

Explique :

* le flux complet de connexion
* les messages WebSocket à ajouter
* les objets échangés
* les changements côté backend
* les changements côté frontend
* les éventuels problèmes NAT/STUN
* comment gérer la reconnexion d'un joueur
* comment gérer l'arrivée ou le départ d'un joueur

Dessine également un schéma Mermaid de l'architecture.

Ne code toujours rien.

## Phase 3 : Plan d'implémentation

Découpe le développement en petites étapes indépendantes.

Pour chaque étape, indique :

* les fichiers à modifier
* les nouveaux fichiers
* la raison des modifications
* les tests à effectuer

Chaque étape doit être compilable et fonctionnelle avant de passer à la suivante.

## Phase 4 : Implémentation

Lorsque le plan est validé, implémente les étapes une par une.

Contraintes :

* ne jamais casser les fonctionnalités existantes
* conserver le style de code du projet
* privilégier la simplicité
* ajouter des commentaires uniquement lorsque c'est réellement utile
* éviter la duplication de code
* créer des abstractions seulement lorsqu'elles apportent une vraie valeur

## Fonctionnalités attendues

Les joueurs doivent pouvoir :

* autoriser l'accès au microphone
* parler librement pendant toute la partie
* couper/réactiver leur micro
* voir quels joueurs ont leur micro activé
* voir quel joueur est actuellement en train de parler (voice activity)
* rejoindre automatiquement le salon vocal lorsqu'ils rejoignent une table
* quitter automatiquement le salon lorsqu'ils quittent la table

## Qualité

À chaque étape :

* vérifie qu'il n'y a pas de régression
* recherche les bugs potentiels
* simplifie le code lorsque c'est possible
* signale les améliorations possibles avant de continuer

Si tu détectes une mauvaise architecture existante, explique-la avant de proposer une amélioration.

