# Chat Vocal Temps Réel

## Architecture

Le chat vocal utilise **WebRTC en P2P** pour permettre aux joueurs de parler pendant la partie. La signalisation WebRTC passe par le serveur WebSocket existant.

### Flux de connexion

```mermaid
sequenceDiagram
    participant J1 as Joueur N
    participant J2 as Joueur E
    participant S as Serveur WS
    participant J3 as Joueur S
    participant J4 as Joueur O

    Note over J1,J4: Tous les joueurs rejoignent la room
    J1->>S: WebSocket connect
    J2->>S: WebSocket connect
    J3->>S: WebSocket connect
    J4->>S: WebSocket connect

    Note over J1,J4: Initialisation voix (micro activé)
    J1->>S: webrtc-offer -> J2
    S->>J2: voice-webrtc-offer (from=J1)
    J2->>S: webrtc-answer -> J1
    S->>J1: voice-webrtc-answer (from=J2)
    
    Note over J1,J2: Connexion P2P établie
    Note over J1,J4: Même processus pour tous les pairs
    
    Note over J1,J4: Échange audio P2P direct
    J1<->J2: WebRTC audio stream
    J1<->J3: WebRTC audio stream
    J1<->J4: WebRTC audio stream
```

### Messages WebSocket

| Type | Direction | Format | Description |
|------|-----------|--------|-------------|
| `webrtc-offer` | Client → Serveur | `{type, peer_position, data: {sdp}}` | Créer connexion vers un pair |
| `voice-webrtc-offer` | Serveur → Client | `{type, from, data: {sdp}}` | Recevoir offre d'un pair |
| `webrtc-answer` | Client → Serveur | `{type, peer_position, data: {sdp}}` | Répondre à une offre |
| `voice-webrtc-answer` | Serveur → Client | `{type, from, data: {sdp}}` | Recevoir réponse |
| `webrtc-ice-candidate` | Client → Serveur | `{type, peer_position, data: {candidate}}` | Échanger ICE candidates |
| `voice-webrtc-ice-candidate` | Serveur → Client | `{type, from, data: {candidate}}` | Recevoir candidate |

## Implémentation Frontend

### Structure

```
frontend/src/voice/
├── VoiceManager.ts      # Gestion WebRTC P2P
├── useVoiceChat.ts      # Hook React
├── VoiceIndicator.tsx   # Composants UI
└── index.ts             # Exports
```

### VoiceManager

Classe principale qui gère :
- Initialisation du micro
- Création des connexions P2P vers tous les autres joueurs
- Traitement des messages de signalisation
- Détection de parole (voice activity detection)
- Contrôles mute/unmute

**Fonctions clés :**
```typescript
// Initialiser le micro et détecter la parole
await voiceManager.init()

// Créer une connexion P2P vers un joueur
await voiceManager.createPeerConnection('E')

// Gérer les messages reçus du serveur
voiceManager.handleOffer('S', sdp)
voiceManager.handleAnswer('S', sdp)
voiceManager.handleIceCandidate('S', candidate)

// Contrôler le micro
voiceManager.toggleMute()
const muted = voiceManager.isMuted()

// État des pairs
const peers = voiceManager.getPeers()
const speaking = voiceManager.isSpeaking('E')
```

### Détection de parole

Le système utilise un `AudioContext` avec un analyseur fréquentiel pour détecter qui parle :

- **Local** : Analyse du stream sortant (seuil : 20)
- **Distant** : Analyse du stream entrant (seuil : 15)

Cela permet d'afficher en temps réel quel joueur parle pendant la partie.

## Intégration dans Game.tsx

Le chat vocal s'affiche dans :
1. **Phase WAITING** : Barre complète avec indicateur pour tous les joueurs
2. **Phase de jeu** : Indicateurs compacts pour N/E/S/O

### Raccourci clavier

Appuyer sur **M** (sans majuscule) pour couper/réactiver le micro.

## Configuration

### Serveurs STUN

Par défaut, le système utilise les serveurs STUN publics de Google :
```typescript
[
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
]
```

Pour une production à plus grande échelle, configurer un serveur TURN pour gérer les NAT restrictifs.

### Qualité audio

Config par défaut :
```typescript
{
  echoCancellation: true,  // Écho
  noiseSuppression: true,  // Réduction bruit
  autoGainControl: true,   // Gain automatique
  sampleRate: 48000        // Haute qualité
}
```

## Limitations actuelles

1. **Pas de TURN** : Les connexions peuvent échouer derrière certains NAT
2. **Pas de bande passante** : Limitation à 4 joueurs maximum
3. **Pas de gestion d'échos** : Écho potentiel si plusieurs micros sont proches
4. **Pas de mixage** : Chaque stream est joué séparément

## Futures améliorations

- [ ] Ajouter un serveur TURN
- [ ] Gestion des déconnexions/reconnexions P2P
- [ ] Indicateurs de qualité de connexion
- [ ] Options de configuration (qualité audio, volume individuel)
- [ ] Support pour plus de 4 joueurs (si besoin)
- [ ] Chat texte pendant la partie
