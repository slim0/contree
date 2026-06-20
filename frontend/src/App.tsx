import { useState, useEffect, useRef, useCallback } from 'react'
import type { GameData } from './types'
import type { AuthUser } from './store/authStore'
import { useAuthStore } from './store/authStore'
import Game from './Game'
import LoginPage from './components/auth/LoginPage'
import ChangePasswordPage from './components/auth/ChangePasswordPage'
import AdminPanel from './components/admin/AdminPanel'

const STORAGE_ROOM = 'contree_room'

interface RoomSummary {
  room_id: string
  room_name: string
  player_count: number
  phase: string
}

function genRoomCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  return Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

export default function App() {
  const { user, loading, setUser, setLoading } = useAuthStore()
  const [showAdmin, setShowAdmin] = useState(false)
  const [roomId, setRoomId] = useState(() => sessionStorage.getItem(STORAGE_ROOM) ?? '')
  const [step, setStep] = useState<'lobby'>('lobby')
  const [joinMode, setJoinMode] = useState(false)
  const [joinCodeMode, setJoinCodeMode] = useState(false)
  const [rooms, setRooms] = useState<RoomSummary[]>([])
  const [createdRoom, setCreatedRoom] = useState<string | null>(null)
  const [roomName, setRoomName] = useState('')
  const [targetScore, setTargetScore] = useState(1000)
  const [copied, setCopied] = useState(false)
  const [game, setGame] = useState<GameData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [startingGame, setStartingGame] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const shouldReconnect = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Vérification de session au montage
  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then((data: AuthUser | null) => {
        setUser(data)
        setLoading(false)
      })
      .catch(() => {
        setUser(null)
        setLoading(false)
      })
  }, [setUser, setLoading])

  const connect = useCallback((room: string, score: number = 1000, rName: string = '') => {
    if (!room.trim()) return
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    if (wsRef.current) {
      const stale = wsRef.current
      stale.onopen = null
      stale.onmessage = null
      stale.onclose = null
      stale.onerror = null
      if (stale.readyState < WebSocket.CLOSING) stale.close()
    }

    const params = new URLSearchParams({ target_score: String(score) })
    if (rName.trim()) params.set('room_name', rName.trim())
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}/ws/${room}?${params}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      shouldReconnect.current = true
      setConnected(true)
      setReconnecting(false)
      setStartingGame(false)
      setError(null)
      sessionStorage.setItem(STORAGE_ROOM, room)
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'state') {
        setGame(msg.data)
      } else if (msg.type === 'restarting') {
        setStartingGame(true)
      } else if (msg.type === 'error') {
        setError(msg.message)
        if (msg.message === 'Partie terminée.') {
          shouldReconnect.current = false
          sessionStorage.removeItem(STORAGE_ROOM)
        }
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (shouldReconnect.current) {
        setReconnecting(true)
        reconnectTimer.current = setTimeout(() => connect(room, score, rName), 2000)
      } else {
        setReconnecting(false)
      }
    }

    ws.onerror = () => {}
  }, [])

  // Auto-reconnexion si une room est sauvegardée en session
  useEffect(() => {
    if (!user || user.must_change_password) return
    const savedRoom = sessionStorage.getItem(STORAGE_ROOM)
    if (savedRoom) connect(savedRoom)
    return () => {
      shouldReconnect.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [user, connect])

  // Fetch room list when join panel opens
  useEffect(() => {
    if (!joinMode) return
    fetch('/api/rooms', { credentials: 'include' })
      .then(r => r.json())
      .then(data => setRooms(data.rooms ?? []))
      .catch(() => setRooms([]))
  }, [joinMode])

  const send = useCallback((msg: object) => {
    wsRef.current?.send(JSON.stringify(msg))
    setError(null)
  }, [])

  async function handleLogout() {
    shouldReconnect.current = false
    wsRef.current?.close()
    sessionStorage.removeItem(STORAGE_ROOM)
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    setUser(null)
    setGame(null)
    setConnected(false)
  }

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

  function handleSelectRoom() {
    setJoinCodeMode(true)
  }

  function handleJoinBack() {
    setJoinCodeMode(false)
    setRoomId('')
  }

  // ── États de chargement / auth ─────────────────────────────────────────────

  if (loading) {
    return <div className="lp-reconnect">Chargement…</div>
  }

  if (!user) {
    return <LoginPage onLogin={user => setUser(user)} />
  }

  if (user.must_change_password) {
    return (
      <ChangePasswordPage
        username={user.username}
        onChanged={updated => setUser(updated)}
      />
    )
  }

  if (user.is_admin) {
    return <AdminPanel onClose={handleLogout} backLabel="Déconnexion" />
  }

  if (showAdmin) {
    return <AdminPanel onClose={() => setShowAdmin(false)} />
  }

  // ── Reconnexion en cours ───────────────────────────────────────────────────

  if (reconnecting) {
    return <div className="lp-reconnect">{startingGame ? 'Démarrage de la partie…' : 'Reconnexion en cours…'}</div>
  }

  // ── Lobby ──────────────────────────────────────────────────────────────────

  if (!connected) {
    return (
      <div className="lp-root">
        <div className="lp-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <div>
              <span style={{ fontSize: 14, color: '#62625b' }}>Connecté en tant que </span>
              <strong style={{ fontSize: 14 }}>{user.username}</strong>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {user.is_admin && (
                <button className="lp-btn-copy" style={{ width: 'auto', marginTop: 0 }} onClick={() => setShowAdmin(true)}>
                  Admin
                </button>
              )}
              <button className="lp-btn-copy" style={{ width: 'auto', marginTop: 0 }} onClick={handleLogout}>
                Déconnexion
              </button>
            </div>
          </div>

          <div className="lp-logo">
            <img src="/ace.webp" alt="As de cœur" className="lp-logo-img" />
          </div>
          <h1 className="lp-title">Belote Contrée</h1>
          <p className="lp-subtitle">Créez un salon et partagez le code, ou rejoignez une partie existante.</p>

          {createdRoom ? (
            <>
              <label className="lp-label" htmlFor="lp-room-name">Nom du salon</label>
              <input
                id="lp-room-name"
                className="lp-input"
                value={roomName}
                placeholder="Ex. Coinche de malade"
                autoFocus
                onChange={e => setRoomName(e.target.value)}
              />
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
              <button
                className="lp-btn-primary"
                disabled={!roomName.trim()}
                onClick={() => connect(createdRoom, targetScore, roomName)}
              >
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
                joinCodeMode ? (
                  <>
                    <button className="lp-back-inline" onClick={handleJoinBack}>← Salons</button>
                    <label className="lp-label" htmlFor="lp-room">Code du salon</label>
                    <input
                      id="lp-room"
                      className="lp-input"
                      value={roomId}
                      placeholder="Ex. A3BX"
                      autoFocus
                      onChange={e => setRoomId(e.target.value.toUpperCase())}
                      onKeyDown={e => e.key === 'Enter' && roomId.trim() && connect(roomId)}
                    />
                    <button
                      className="lp-btn-secondary"
                      disabled={!roomId.trim()}
                      onClick={() => connect(roomId)}
                    >
                      Rejoindre
                    </button>
                  </>
                ) : (
                  <>
                    {rooms.length === 0 ? (
                      <p className="lp-no-rooms">Aucun salon disponible.</p>
                    ) : (
                      <ul className="lp-room-list">
                        {rooms.map(r => (
                          <li key={r.room_id} className="lp-room-item" onClick={handleSelectRoom}>
                            <span className="lp-room-item-name">{r.room_name || r.room_id}</span>
                            <span className="lp-room-item-players">{r.player_count}/4</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <button className="lp-btn-secondary" onClick={() => setJoinCodeMode(true)}>
                      Entrer un code manuellement
                    </button>
                  </>
                )
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
