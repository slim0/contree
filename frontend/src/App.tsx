import { useState, useEffect, useRef, useCallback } from 'react'
import type { GameData } from './types'
import Game from './Game'

const STORAGE_ROOM = 'contree_room'
const STORAGE_NAME = 'contree_name'

export default function App() {
  const [roomId, setRoomId] = useState(() => sessionStorage.getItem(STORAGE_ROOM) ?? 'salon1')
  const [playerName, setPlayerName] = useState(() => sessionStorage.getItem(STORAGE_NAME) ?? '')
  const [game, setGame] = useState<GameData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const shouldReconnect = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback((room: string, name: string) => {
    if (!name.trim() || !room.trim()) return
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }

    const url = `ws://${location.hostname}:8000/ws/${room}/${encodeURIComponent(name)}`
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
        // Errors that mean we should not auto-reconnect
        if (msg.message === 'Partie terminée.' || msg.message === 'Ce pseudo est déjà en jeu.') {
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

  if (reconnecting) {
    return <p style={{ color: '#4af', padding: 16 }}>Reconnexion en cours…</p>
  }

  if (!connected) {
    return (
      <div className="section">
        <h3>Belote Contrée — Rejoindre une partie</h3>
        <div>
          <label>Salon : </label>
          <input value={roomId} onChange={e => setRoomId(e.target.value)} />
        </div>
        <div style={{ marginTop: 8 }}>
          <label>Pseudo : </label>
          <input value={playerName} onChange={e => setPlayerName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && connect(roomId, playerName)} />
        </div>
        <div style={{ marginTop: 8 }}>
          <button className="action" onClick={() => connect(roomId, playerName)}>Rejoindre</button>
        </div>
        {error && <p className="error">{error}</p>}
        <p style={{ color: '#666', fontSize: '0.8em' }}>
          Ouvre 4 onglets, même salon, 4 pseudos différents.
        </p>
      </div>
    )
  }

  return <Game game={game} error={error} send={send} />
}
