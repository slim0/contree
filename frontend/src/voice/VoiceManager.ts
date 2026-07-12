/**
 * WebRTC Voice Chat Module
 * Gère les connexions P2P audio entre les joueurs via signalisation WebSocket
 */

export interface VoicePeer {
  position: string;
  peerConnection: RTCPeerConnection;
  isMuted: boolean;
  isSpeaking: boolean;
  connectionState: RTCPeerConnectionState;
  remoteStream: MediaStream | null;
}

export interface VoiceManagerConfig {
  ws: WebSocket;
  myPosition: string;
  iceServers?: RTCConfiguration['iceServers'];
}

// Config STUN par défaut (public, gratuit)
const DEFAULT_ICE_SERVERS: RTCConfiguration['iceServers'] = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
];

export class VoiceManager {
  private config: VoiceManagerConfig;
  private peers: Map<string, VoicePeer> = new Map();
  private localStream: MediaStream | null = null;
  private onSpeakingChange: ((position: string, isSpeaking: boolean) => void) | null = null;
  private onPeerConnect: ((position: string, connected: boolean) => void) | null = null;
  private rafHandles: number[] = [];
  private audioElements: HTMLAudioElement[] = [];

  constructor(config: VoiceManagerConfig) {
    this.config = config;
  }

  /**
   * Initialiser le chat vocal : demander l'accès au micro et créer les connexions P2P
   */
  async init(): Promise<void> {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 48000,
        },
        video: false,
      });
      console.log('[Voice] Micro activé');
    } catch (err) {
      console.error('[Voice] Impossible d\'accéder au micro:', err);
      throw new Error('Accès au micro refusé');
    }

    // Configurer l'analyseur de voix pour détecter qui parle
    this.setupVoiceDetection();
  }

  /**
   * Configurer la détection de parole sur le stream local
   */
  private setupVoiceDetection(): void {
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    const source = audioContext.createMediaStreamSource(this.localStream!);
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const checkVoice = () => {
      analyser.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      const isSpeaking = average > 20; // Seuil de détection

      if (isSpeaking !== this.peers.get('local')?.isSpeaking) {
        this.peers.set('local', {
          position: 'local',
          peerConnection: null as any,
          isMuted: false,
          isSpeaking,
          connectionState: 'connected',
          remoteStream: null,
        });
        this.onSpeakingChange?.('local', isSpeaking);
      }

      this.rafHandles.push(requestAnimationFrame(checkVoice));
    };

    this.rafHandles.push(requestAnimationFrame(checkVoice));
  }

  /**
   * Créer une connexion P2P vers un joueur distant
   */
  async createPeerConnection(peerPosition: string): Promise<void> {
    if (this.peers.has(peerPosition)) {
      return; // Déjà connecté
    }

    const config: RTCConfiguration = {
      iceServers: this.config.iceServers ?? DEFAULT_ICE_SERVERS,
    };

    const pc = new RTCPeerConnection(config);

    // Ajouter les pistes audio locales
    this.localStream?.getTracks().forEach(track => {
      pc.addTrack(track, this.localStream!);
    });

    // Gérer le stream distant
    pc.ontrack = (event) => {
      const stream = event.streams[0];
      this.peers.set(peerPosition, {
        ...this.peers.get(peerPosition)!,
        remoteStream: stream,
      });

      // Lire le stream distant pour détecter la parole
      this.setupRemoteVoiceDetection(peerPosition, stream);
    };

    // Gérer les changements d'état
    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      this.peers.set(peerPosition, {
        ...this.peers.get(peerPosition)!,
        connectionState: state,
      });
      this.onPeerConnect?.(peerPosition, state === 'connected');

      if (state === 'failed' || state === 'closed') {
        this.cleanupPeer(peerPosition);
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.config.ws.send(JSON.stringify({
          type: 'webrtc-ice-candidate',
          peer_position: peerPosition,
          data: { candidate: event.candidate },
        }));
      }
    };

    // Créer et envoyer l'offre
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    this.peers.set(peerPosition, {
      position: peerPosition,
      peerConnection: pc,
      isMuted: false,
      isSpeaking: false,
      connectionState: pc.connectionState,
      remoteStream: null,
    });

    this.config.ws.send(JSON.stringify({
      type: 'webrtc-offer',
      peer_position: peerPosition,
      data: { sdp: pc.localDescription },
    }));
  }

  /**
   * Traiter une offre reçue d'un pair distant
   */
  async handleOffer(peerPosition: string, sdp: RTCSessionDescriptionInit): Promise<void> {
    if (this.peers.has(peerPosition)) {
      return;
    }

    const config: RTCConfiguration = {
      iceServers: this.config.iceServers ?? DEFAULT_ICE_SERVERS,
    };

    const pc = new RTCPeerConnection(config);

    // Ajouter les pistes locales pour que l'offreur nous entende aussi
    this.localStream?.getTracks().forEach(track => {
      pc.addTrack(track, this.localStream!);
    });

    pc.ontrack = (event) => {
      const stream = event.streams[0];
      this.peers.set(peerPosition, {
        ...this.peers.get(peerPosition)!,
        remoteStream: stream,
      });
      this.setupRemoteVoiceDetection(peerPosition, stream);
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      this.peers.set(peerPosition, {
        ...this.peers.get(peerPosition)!,
        connectionState: state,
      });
      this.onPeerConnect?.(peerPosition, state === 'connected');

      if (state === 'failed' || state === 'closed') {
        this.cleanupPeer(peerPosition);
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.config.ws.send(JSON.stringify({
          type: 'webrtc-ice-candidate',
          peer_position: peerPosition,
          data: { candidate: event.candidate },
        }));
      }
    };

    await pc.setRemoteDescription(new RTCSessionDescription(sdp));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    this.peers.set(peerPosition, {
      position: peerPosition,
      peerConnection: pc,
      isMuted: false,
      isSpeaking: false,
      connectionState: pc.connectionState,
      remoteStream: null,
    });

    this.config.ws.send(JSON.stringify({
      type: 'webrtc-answer',
      peer_position: peerPosition,
      data: { sdp: pc.localDescription },
    }));
  }

  /**
   * Traiter une réponse reçue
   */
  async handleAnswer(peerPosition: string, sdp: RTCSessionDescriptionInit): Promise<void> {
    const peer = this.peers.get(peerPosition);
    if (!peer) return;

    await peer.peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
  }

  /**
   * Traiter un candidat ICE reçu
   */
  async handleIceCandidate(peerPosition: string, candidate: RTCIceCandidateInit): Promise<void> {
    const peer = this.peers.get(peerPosition);
    if (!peer) return;

    try {
      await peer.peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (err) {
      console.error('[Voice] Erreur ajout ICE candidate:', err);
    }
  }

  /**
   * Configurer la détection de voix pour un stream distant et le jouer
   */
  private setupRemoteVoiceDetection(peerPosition: string, stream: MediaStream): void {
    // Lire l'audio distant via un élément <audio> — seule façon fiable de l'envoyer aux hauts-parleurs
    const audio = new Audio();
    audio.srcObject = stream;
    audio.autoplay = true;
    audio.play().catch(() => {/* autoplay peut être bloqué avant interaction utilisateur */});
    this.audioElements.push(audio);

    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const checkVoice = () => {
      analyser.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      const isSpeaking = average > 15;

      const peer = this.peers.get(peerPosition);
      if (peer && isSpeaking !== peer.isSpeaking) {
        this.peers.set(peerPosition, { ...peer, isSpeaking });
        this.onSpeakingChange?.(peerPosition, isSpeaking);
      }

      this.rafHandles.push(requestAnimationFrame(checkVoice));
    };

    this.rafHandles.push(requestAnimationFrame(checkVoice));
  }

  /**
   * Activer/désactiver le micro
   */
  toggleMute(): boolean {
    if (!this.localStream) return false;

    // track.muted est en lecture seule (géré par le navigateur/OS)
    // track.enabled est ce qu'on contrôle pour couper le micro
    const currentlyMuted = this.localStream.getAudioTracks().some(t => !t.enabled);
    this.localStream.getAudioTracks().forEach(t => { t.enabled = currentlyMuted; });

    return !currentlyMuted; // retourne le nouvel état muted
  }

  /**
   * État actuel du micro
   */
  isMuted(): boolean {
    return this.localStream?.getAudioTracks().some(t => !t.enabled) ?? true;
  }

  /**
   * Nettoyer une connexion pair
   */
  private cleanupPeer(position: string): void {
    const peer = this.peers.get(position);
    if (peer) {
      peer.peerConnection.close();
      this.peers.delete(position);
      this.onPeerConnect?.(position, false);
    }
  }

  /**
   * Déconnecter tous les pairs
   */
  disconnectAll(): void {
    this.peers.forEach((_, position) => this.cleanupPeer(position));

    // Stopper les boucles RAF
    this.rafHandles.forEach(id => cancelAnimationFrame(id));
    this.rafHandles = [];

    // Libérer les éléments audio distants
    this.audioElements.forEach(audio => {
      audio.srcObject = null;
      audio.pause();
    });
    this.audioElements = [];

    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }
  }

  /**
   * Getters pour l'état
   */
  getPeers(): Map<string, VoicePeer> {
    return new Map(this.peers);
  }

  isSpeaking(position: string): boolean {
    return this.peers.get(position)?.isSpeaking ?? false;
  }

  isConnected(position: string): boolean {
    return this.peers.get(position)?.connectionState === 'connected';
  }

  isMutedByPeer(position: string): boolean {
    return this.peers.get(position)?.isMuted ?? true;
  }

  getRemoteStream(position: string): MediaStream | null {
    return this.peers.get(position)?.remoteStream ?? null;
  }

  /**
   * Callbacks
   */
  setOnSpeakingChange(callback: (position: string, isSpeaking: boolean) => void): void {
    this.onSpeakingChange = callback;
  }

  setOnPeerConnect(callback: (position: string, connected: boolean) => void): void {
    this.onPeerConnect = callback;
  }
}
