import { useEffect, useRef } from 'react';

interface VoiceIndicatorProps {
  position: string;
  playerName: string;
  isSpeaking: boolean;
  isConnected: boolean;
  isMuted?: boolean;
  myPosition: string;
}

/**
 * Composant pour afficher un indicateur vocal pour un joueur
 */
export function VoiceIndicator({
  position,
  playerName,
  isSpeaking,
  isConnected,
  isMuted = false,
  myPosition,
}: VoiceIndicatorProps) {
  const isMe = position === myPosition;

  // Animation du pulse quand quelqu'un parle
  const pulseRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pulseRef.current) {
      pulseRef.current.style.opacity = isSpeaking ? '1' : '0';
      pulseRef.current.style.transform = isSpeaking ? 'scale(1.5)' : 'scale(1)';
    }
  }, [isSpeaking]);

  if (!isConnected) return null;

  let statusColor = '#4a4';
  if (isMuted) statusColor = '#999';
  else if (!isConnected) statusColor = '#944';

  return (
    <div
      className="voice-indicator"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 8px',
        borderRadius: 12,
        backgroundColor: isSpeaking ? '#2a2' : '#222',
        transition: 'background-color 0.15s ease',
        marginLeft: isMe ? 8 : 0,
      }}
    >
      {/* Icône micro */}
      <div
        style={{
          position: 'relative',
          width: 24,
          height: 24,
        }}
      >
        {/* Anneau de parole animé */}
        <div
          ref={pulseRef}
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            width: 28,
            height: 28,
            borderRadius: '50%',
            backgroundColor: isSpeaking ? 'rgba(74, 255, 74, 0.3)' : 'transparent',
            transform: 'translate(-50%, -50%) scale(1)',
            opacity: 0,
            transition: 'all 0.15s ease',
            pointerEvents: 'none',
          }}
        />

        {/* Icône micro */}
        <svg
          width={isMuted ? 16 : 14}
          height={isMuted ? 16 : 14}
          viewBox="0 0 24 24"
          fill="none"
          stroke={isMuted ? '#666' : '#fff'}
          strokeWidth={2}
          style={{
            zIndex: 2,
            position: 'relative',
          }}
        >
          {isMuted ? (
            <>
              <line x1={1} y1={1} x2={23} y2={23} />
              <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
              <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
              <line x1={12} y1={19} x2={12} y2={23} />
              <line x1={8} y1={23} x2={16} y2={23} />
            </>
          ) : (
            <>
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1={12} y1={19} x2={12} y2={23} />
              <line x1={8} y1={23} x2={16} y2={23} />
            </>
          )}
        </svg>
      </div>

      {/* Nom du joueur */}
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: isMe ? '#ffa' : '#ccc',
          textTransform: 'uppercase',
        }}
      >
        {playerName}
      </span>

      {/* Badge de position */}
      <span
        style={{
          fontSize: 10,
          padding: '2px 5px',
          borderRadius: 6,
          backgroundColor: isSpeaking ? '#383' : '#444',
          color: '#fff',
          fontWeight: 700,
          transition: 'all 0.15s ease',
        }}
      >
        {position}
      </span>
    </div>
  );
}

/**
 * Composant pour afficher le bandeau vocal complet
 */
interface VoiceBarProps {
  peers: Map<string, {
    position: string;
    isSpeaking: boolean;
    isConnected: boolean;
    isMuted: boolean;
  }>;
  localIsSpeaking: boolean;
  isMuted: boolean;
  myPosition: string | null;
  playerName: string;
  onToggleMute: () => void;
  enabled: boolean;
}

export function VoiceBar({
  peers,
  localIsSpeaking,
  isMuted,
  myPosition,
  playerName,
  onToggleMute,
  enabled,
}: VoiceBarProps) {
  if (!myPosition || !enabled) return null;

  const speakingCount = [
    ...peers.values(),
    { position: 'local', isSpeaking: localIsSpeaking },
  ].filter(p => p.isSpeaking).length;

  return (
    <div
      className="voice-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 8,
        padding: '8px 12px',
        backgroundColor: '#1a1a1a',
        borderRadius: 16,
        margin: '0 auto',
        maxWidth: '100%',
      }}
    >
      {/* Indicateur de nombre de joueurs qui parlent */}
      {speakingCount > 0 && (
        <div
          style={{
            fontSize: 11,
            color: '#8f8',
            marginRight: 8,
          }}
        >
          {speakingCount} joueur{speakingCount > 1 ? 's' : ''} parle{speakingCount > 1 ? 'nt' : ''}
        </div>
      )}

      {/* Indicateur pour moi */}
      <VoiceIndicator
        position={myPosition}
        playerName={playerName}
        isSpeaking={localIsSpeaking}
        isConnected={true}
        isMuted={isMuted}
        myPosition={myPosition}
      />

      {/* Indicateurs pour les autres joueurs */}
      {Array.from(peers.entries()).map(([position, peer]) => (
        <VoiceIndicator
          key={position}
          position={peer.position}
          playerName={`${position}`}
          isSpeaking={peer.isSpeaking}
          isConnected={peer.isConnected}
          isMuted={peer.isMuted}
          myPosition={myPosition}
        />
      ))}

      {/* Bouton mute */}
      <button
        onClick={onToggleMute}
        style={{
          background: isMuted ? '#333' : '#2a2',
          border: 'none',
          borderRadius: 8,
          padding: '6px 12px',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 600,
          color: isMuted ? '#888' : '#fff',
          marginLeft: 8,
          transition: 'background 0.15s ease',
        }}
        title={isMuted ? 'Désactiver le micro (touche M)' : 'Activer le micro'}
      >
        {isMuted ? 'MICRO MUTE' : 'MICRO ON'}
      </button>
    </div>
  );
}
