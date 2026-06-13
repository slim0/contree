import { useState, useEffect, useRef, useCallback } from 'react'
import type { GameData } from './types'
import Game from './Game'

export default function App() {
  const [roomId, setRoomId] = useState('salon1')
  const [playerName, setPlayerName] = useState('')
  const [game, setGame] = useState<GameData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    if (!playerName.trim() || !roomId.trim()) return
    const url = `ws://${location.hostname}:8000/ws/${roomId}/${encodeURIComponent(playerName)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'state') setGame(msg.data)
      else if (msg.type === 'error') setError(msg.message)
    }
    ws.onclose = () => { setConnected(false); setError('Connexion perdue') }
    ws.onerror = () => setError('Erreur WebSocket')
  }, [roomId, playerName])

  const send = useCallback((msg: object) => {
    wsRef.current?.send(JSON.stringify(msg))
    setError(null)
  }, [])

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
            onKeyDown={e => e.key === 'Enter' && connect()} />
        </div>
        <div style={{ marginTop: 8 }}>
          <button className="action" onClick={connect}>Rejoindre</button>
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
