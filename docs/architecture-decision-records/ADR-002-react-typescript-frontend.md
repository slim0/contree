# ADR-002 : Framework front-end — React + TypeScript

**Date** : 2026-06-12  
**Statut** : Accepté

## Contexte

Choix du framework front-end pour l'interface du jeu.

## Décision

React 18 + TypeScript strict, bundlé avec Vite.

## Justification

- Le développeur a déjà une expérience TypeScript et est convaincu du typage fort
- React est le framework le mieux documenté et le plus outillé — pas de temps perdu à apprendre un écosystème
- TypeScript strict garantit la cohérence des types entre les événements WebSocket et l'UI
- Vite remplace Create React App (déprécié) : démarrage rapide, HMR fiable
- Compatible avec ce que Claude Code génère par défaut

## Alternatives rejetées

- **Next.js** : SSR inutile pour un jeu de cartes temps réel. Complexité ajoutée sans bénéfice
- **Vue / Svelte** : pas de raison de découvrir un nouveau framework sur un POC à livrer vite
- **Vanilla TypeScript** : trop de boilerplate pour gérer le state d'un jeu

## Conséquences

- Les types des événements WebSocket (`src/types/game.ts`) doivent rester en miroir des modèles Python
- Zustand comme state manager — pas Redux (over-engineering pour ce scope)
- WebSocket natif — pas Socket.io (dépendance inutile)
