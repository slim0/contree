import { useState, useEffect, useCallback, useRef } from 'react';
import type { VoicePeer } from './VoiceManager';
import { VoiceManager } from './VoiceManager';

interface UseVoiceChatOptions {
  ws: WebSocket | null;
  myPosition: string | null;
  enabled: boolean;
}

interface UseVoiceChatReturn {
  peers: Map<string, VoicePeer>;
  localIsSpeaking: boolean;
  isMuted: boolean;
  toggleMute: () => void;
  error: string | null;
  init: () => Promise<void>;
}

/**
 * Hook React pour gérer le chat vocal
 */
export function useVoiceChat(options: UseVoiceChatOptions): UseVoiceChatReturn {
  const { ws, myPosition, enabled } = options;
  const voiceManagerRef = useRef<VoiceManager | null>(null);
  const [peers, setPeers] = useState<Map<string, VoicePeer>>(new Map());
  const [localIsSpeaking, setLocalIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Initialiser le VoiceManager
  useEffect(() => {
    if (!enabled || !myPosition || !ws || initialized) return;

    const manager = new VoiceManager({
      ws,
      myPosition,
    });

    voiceManagerRef.current = manager;

    manager.setOnSpeakingChange((position, speaking) => {
      if (position === 'local') {
        setLocalIsSpeaking(speaking);
      } else {
        setPeers(prev => {
          const peer = prev.get(position);
          if (!peer) return prev;
          const updated = new Map(prev);
          updated.set(position, { ...peer, isSpeaking: speaking });
          return updated;
        });
      }
    });

    manager.setOnPeerConnect((position, connected) => {
      setPeers(prev => {
        const peer = prev.get(position);
        if (!peer) return prev;
        const updated = new Map(prev);
        updated.set(position, {
          ...peer,
          connectionState: connected ? 'connected' : 'disconnected',
        });
        return updated;
      });
    });

    // Initialiser l'accès micro
    manager.init().then(() => {
      setIsMuted(false);
      setError(null);
      setInitialized(true);
    }).catch(err => {
      setError(err instanceof Error ? err.message : 'Erreur voix');
    });

    return () => {
      manager.disconnectAll();
    };
  }, [enabled, myPosition, ws, initialized]);

  // Gérer les messages WebRTC du serveur
  useEffect(() => {
    if (!ws || !voiceManagerRef.current) return;

    const handler = (event: MessageEvent) => {
      const msg = JSON.parse(event.data);
      const manager = voiceManagerRef.current!;

      if (msg.type === 'voice-webrtc-offer') {
        const peerPos = msg.from;
        manager.handleOffer(peerPos, msg.data.sdp);
      } else if (msg.type === 'voice-webrtc-answer') {
        const peerPos = msg.from;
        manager.handleAnswer(peerPos, msg.data.sdp);
      } else if (msg.type === 'voice-webrtc-ice-candidate') {
        const peerPos = msg.from;
        manager.handleIceCandidate(peerPos, msg.data.candidate);
      }
    };

    ws.addEventListener('message', handler);
    return () => ws.removeEventListener('message', handler);
  }, [ws]);

  // Créer les connexions P2P quand les joueurs rejoignent
  useEffect(() => {
    if (!enabled || !myPosition || !ws || !voiceManagerRef.current) return;

    const positions = ['N', 'E', 'S', 'W'];
    const manager = voiceManagerRef.current;

    positions.forEach(pos => {
      if (pos !== myPosition) {
        manager.createPeerConnection(pos).catch(err => {
          console.error('[Voice] Connexion P2P échouée:', err);
        });
      }
    });
  }, [enabled, myPosition, ws]);

  const toggleMute = useCallback(() => {
    if (voiceManagerRef.current) {
      const muted = voiceManagerRef.current.toggleMute();
      setIsMuted(muted);
    }
  }, []);

  // Mettre à jour les peers périodiquement
  useEffect(() => {
    if (!voiceManagerRef.current) return;

    const interval = setInterval(() => {
      setPeers(new Map(voiceManagerRef.current!.getPeers()));
    }, 200);

    return () => clearInterval(interval);
  }, []);

  const init = useCallback(async () => {
    if (voiceManagerRef.current) {
      try {
        await voiceManagerRef.current.init();
        setIsMuted(false);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erreur voix');
      }
    }
  }, []);

  return {
    peers,
    localIsSpeaking,
    isMuted,
    toggleMute,
    error,
    init,
  };
}
