import { useState, useEffect, useRef, useCallback } from 'react'
import type { GameData } from './types'
import Game from './Game'

const STORAGE_ROOM = 'contree_room'
const STORAGE_NAME = 'contree_name'

function genRoomCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  return Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

export default function App() {
  const [roomId, setRoomId] = useState(() => sessionStorage.getItem(STORAGE_ROOM) ?? '')
  const [playerName, setPlayerName] = useState(() => sessionStorage.getItem(STORAGE_NAME) ?? '')
  const [step, setStep] = useState<'name' | 'lobby'>('name')
  const [joinMode, setJoinMode] = useState(false)
  const [createdRoom, setCreatedRoom] = useState<string | null>(null)
  const [targetScore, setTargetScore] = useState(1000)
  const [copied, setCopied] = useState(false)
  const [game, setGame] = useState<GameData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const shouldReconnect = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback((room: string, name: string, score: number = 1000) => {
    if (!name.trim() || !room.trim()) return
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    // Neutralise stale handlers before replacing the connection (guards against
    // React StrictMode double-effect and rapid reconnect races).
    if (wsRef.current) {
      const stale = wsRef.current
      stale.onopen = null
      stale.onmessage = null
      stale.onclose = null
      stale.onerror = null
      if (stale.readyState < WebSocket.CLOSING) stale.close()
    }

    const url = `ws://${location.hostname}:8000/ws/${room}/${encodeURIComponent(name)}?target_score=${score}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      shouldReconnect.current = true
      setConnected(true)
      setReconnecting(false)
      setError(null)
      sessionStorage.setItem(STORAGE_ROOM, room)
      sessionStorage.setItem(STORAGE_NAME, name)
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'state') {
        setGame(msg.data)
      } else if (msg.type === 'error') {
        setError(msg.message)
        // Only a finished game permanently blocks reconnection
        if (msg.message === 'Partie terminée.') {
          shouldReconnect.current = false
          sessionStorage.removeItem(STORAGE_ROOM)
          sessionStorage.removeItem(STORAGE_NAME)
        }
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (shouldReconnect.current) {
        setReconnecting(true)
        reconnectTimer.current = setTimeout(() => connect(room, name), 2000)
      } else {
        setReconnecting(false)
      }
    }

    ws.onerror = () => {} // onclose fires after onerror and handles reconnect
  }, [])

  // On mount: auto-connect if credentials are saved in sessionStorage
  useEffect(() => {
    const savedRoom = sessionStorage.getItem(STORAGE_ROOM)
    const savedName = sessionStorage.getItem(STORAGE_NAME)
    if (savedRoom && savedName) {
      connect(savedRoom, savedName)
    }
    return () => {
      shouldReconnect.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((msg: object) => {
    wsRef.current?.send(JSON.stringify(msg))
    setError(null)
  }, [])

  function handleCreate() {
    const code = genRoomCode()
    setCreatedRoom(code)
    setRoomId(code)
    setJoinMode(false)
  }

  function handleCopy() {
    navigator.clipboard.writeText(createdRoom ?? '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (reconnecting) {
    return <div className="lp-reconnect">Reconnexion en cours…</div>
  }

  if (!connected) {
    if (step === 'name') {
      return (
        <div className="lp-root">
          <div className="lp-card">
            <div className="lp-logo">
              <img src="/ace.webp" alt="As de cœur" className="lp-logo-img" />
            </div>
            <h1 className="lp-title">Belote Contrée</h1>
            <p className="lp-subtitle">Joue avec tes potes en live !</p>
            <label className="lp-label" htmlFor="lp-name">Ton pseudo</label>
            <input
              id="lp-name"
              className="lp-input"
              value={playerName}
              placeholder="Ex. Alice"
              autoFocus
              onChange={e => setPlayerName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && playerName.trim() && setStep('lobby')}
            />
            <button
              className="lp-btn-primary"
              disabled={!playerName.trim()}
              onClick={() => setStep('lobby')}
            >
              Continuer
            </button>
            {error && <p className="lp-error">{error}</p>}
          </div>
        </div>
      )
    }

    return (
      <div className="lp-root">
        <div className="lp-card">
          <button className="lp-back" onClick={() => { setStep('name'); setJoinMode(false); setCreatedRoom(null) }}>
            ← Retour
          </button>
          <h1 className="lp-title">Bonjour, {playerName}&nbsp;!</h1>
          <p className="lp-subtitle">Créez un salon et partagez le code, ou rejoignez une partie existante.</p>

          {createdRoom ? (
            <>
              <div className="lp-code-box">
                <div className="lp-code">{createdRoom}</div>
                <div className="lp-code-hint">Partagez ce code avec vos 3 amis</div>
              </div>
              <button className="lp-btn-copy" onClick={handleCopy}>
                {copied ? '✓ Code copié !' : 'Copier le code'}
              </button>
              <div className="lp-score-selector">
                <label className="lp-label">Score cible</label>
                <div className="lp-score-options">
                  {[500, 1000, 2000].map(s => (
                    <button
                      key={s}
                      className={`lp-score-btn${targetScore === s ? ' active' : ''}`}
                      onClick={() => setTargetScore(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <button className="lp-btn-primary" onClick={() => connect(createdRoom, playerName, targetScore)}>
                Entrer dans le salon
              </button>
              <button className="lp-btn-secondary" onClick={() => setCreatedRoom(null)}>
                Générer un autre code
              </button>
            </>
          ) : (
            <>
              <button className="lp-btn-primary" style={{ marginTop: 0 }} onClick={handleCreate}>
                Créer un salon
              </button>
              <div className="lp-divider">ou</div>
              {joinMode ? (
                <>
                  <label className="lp-label" htmlFor="lp-room">Code du salon</label>
                  <input
                    id="lp-room"
                    className="lp-input"
                    value={roomId}
                    placeholder="Ex. A3BX"
                    autoFocus
                    onChange={e => setRoomId(e.target.value.toUpperCase())}
                    onKeyDown={e => e.key === 'Enter' && roomId.trim() && connect(roomId, playerName)}
                  />
                  <button
                    className="lp-btn-secondary"
                    disabled={!roomId.trim()}
                    onClick={() => connect(roomId, playerName)}
                  >
                    Rejoindre
                  </button>
                </>
              ) : (
                <button className="lp-btn-secondary" onClick={() => setJoinMode(true)}>
                  Rejoindre un salon existant
                </button>
              )}
            </>
          )}

          {error && <p className="lp-error">{error}</p>}
        </div>
      </div>
    )
  }

  return <Game game={game} error={error} send={send} />
}
