import { useState, useEffect } from 'react'

interface UserRecord {
  id: string
  username: string
  is_admin: boolean
  must_change_password: boolean
  is_approved: boolean
  created_at: string
  games_played: number
  games_won: number
  games_lost: number
  win_rate: number | null
  capots_won: number
  generales_won: number
  contracts_taken: number
  contracts_made: number
  contract_success_rate: number | null
}

interface RoomRecord {
  room_id: string
  room_name: string
  creator: string
  phase: string
  player_count: number
  players: string[]
  target_score: number
}

const PHASE_LABEL: Record<string, string> = {
  WAITING: 'En attente',
  BIDDING: 'Enchères',
  PLAYING: 'En jeu',
  SCORING: 'Décompte',
  FINISHED: 'Terminée',
}

interface Props {
  onClose?: () => void
  backLabel?: string
  onShowStats?: () => void
  onLogout?: () => void
}

export default function AdminPanel({ onClose, backLabel = '← Retour au jeu', onShowStats, onLogout }: Props) {
  const [users, setUsers] = useState<UserRecord[]>([])
  const [rooms, setRooms] = useState<RoomRecord[]>([])
  const [newUsername, setNewUsername] = useState('')
  const [tempPassword, setTempPassword] = useState<string | null>(null)
  const [copiedPassword, setCopiedPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function fetchUsers() {
    try {
      const r = await fetch('/api/admin/users', { credentials: 'include' })
      if (r.ok) setUsers(await r.json())
    } catch {
      setError('Impossible de charger la liste des utilisateurs')
    }
  }

  async function fetchRooms() {
    try {
      const r = await fetch('/api/admin/rooms', { credentials: 'include' })
      if (r.ok) setRooms((await r.json()).rooms ?? [])
    } catch {
      setError('Impossible de charger la liste des salons')
    }
  }

  useEffect(() => { fetchUsers(); fetchRooms() }, [])

  async function handleDeleteRoom(room: RoomRecord) {
    if (!confirm(`Supprimer le salon "${room.room_name || room.room_id}" ?`)) return
    setError(null)
    try {
      const r = await fetch(`/api/rooms/${encodeURIComponent(room.room_id)}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? 'Erreur lors de la suppression du salon')
        return
      }
      await fetchRooms()
    } catch {
      setError('Impossible de contacter le serveur')
    }
  }

  async function handleCreate() {
    if (!newUsername.trim()) return
    setLoading(true)
    setError(null)
    setTempPassword(null)
    try {
      const r = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username: newUsername.trim() }),
      })
      const body = await r.json()
      if (!r.ok) {
        setError(body.detail ?? 'Erreur lors de la création')
        return
      }
      setTempPassword(body.temp_password)
      setNewUsername('')
      await fetchUsers()
    } catch {
      setError('Impossible de contacter le serveur')
    } finally {
      setLoading(false)
    }
  }

  async function handleApprove(username: string) {
    setError(null)
    try {
      const r = await fetch(`/api/admin/users/${encodeURIComponent(username)}/approve`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? "Erreur lors de l'approbation")
        return
      }
      await fetchUsers()
    } catch {
      setError('Impossible de contacter le serveur')
    }
  }

  async function handleDelete(username: string) {
    if (!confirm(`Supprimer l'utilisateur "${username}" ?`)) return
    setError(null)
    try {
      const r = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? 'Erreur lors de la suppression')
        return
      }
      await fetchUsers()
    } catch {
      setError('Impossible de contacter le serveur')
    }
  }

  function handleCopyPassword() {
    if (!tempPassword) return
    navigator.clipboard.writeText(tempPassword)
    setCopiedPassword(true)
    setTimeout(() => setCopiedPassword(false), 2000)
  }

  return (
    <div className="lp-root" style={{ zIndex: 100 }}>
      <div className="lp-card" style={{ maxWidth: 520 }}>
        {onClose && <button className="lp-back" onClick={onClose}>{backLabel}</button>}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h1 className="lp-title" style={{ textAlign: 'left', marginBottom: 0 }}>Gestion des joueurs</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {onShowStats && (
              <button className="lp-back-inline" style={{ marginBottom: 0 }} onClick={onShowStats}>
                Mes statistiques
              </button>
            )}
            {onLogout && (
              <button className="lp-back-inline" style={{ marginBottom: 0, color: '#b3261e' }} onClick={onLogout}>
                Quitter
              </button>
            )}
          </div>
        </div>

        {/* Créer un joueur */}
        <div style={{ marginBottom: 24 }}>
          <label className="lp-label">Nouvel utilisateur</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 0 }}>
            <input
              className="lp-input"
              value={newUsername}
              placeholder="Identifiant"
              onChange={e => setNewUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
            />
            <button
              className="lp-btn-primary"
              style={{ width: 'auto', marginTop: 0, flexShrink: 0 }}
              disabled={!newUsername.trim() || loading}
              onClick={handleCreate}
            >
              Créer
            </button>
          </div>
        </div>

        {/* Mot de passe temporaire */}
        {tempPassword && (
          <div className="lp-code-box" style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: '#62625b', marginBottom: 6 }}>
              Mot de passe temporaire (visible une seule fois)
            </div>
            <div className="lp-code" style={{ letterSpacing: 2, fontSize: 20 }}>{tempPassword}</div>
            <button className="lp-btn-copy" onClick={handleCopyPassword} style={{ marginTop: 8 }}>
              {copiedPassword ? '✓ Copié !' : 'Copier'}
            </button>
          </div>
        )}

        {error && <p className="lp-error">{error}</p>}

        {/* Comptes en attente d'approbation */}
        {users.some(u => !u.is_approved) && (
          <div style={{ marginTop: 8, marginBottom: 16 }}>
            <label className="lp-label">
              En attente d'approbation ({users.filter(u => !u.is_approved).length})
            </label>
            <ul className="lp-room-list" style={{ marginTop: 8 }}>
              {users.filter(u => !u.is_approved).map(u => (
                <li key={u.id} className="lp-room-item" style={{ cursor: 'default' }}>
                  <span className="lp-room-item-name">{u.username}</span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      style={{
                        background: 'none', border: '1.5px solid #1a7a3a',
                        borderRadius: 8, padding: '4px 10px',
                        fontSize: 12, color: '#1a7a3a', cursor: 'pointer', margin: 0,
                      }}
                      onClick={() => handleApprove(u.username)}
                    >
                      Approuver
                    </button>
                    <button
                      style={{
                        background: 'none', border: '1.5px solid #e0e0e0',
                        borderRadius: 8, padding: '4px 10px',
                        fontSize: 12, color: '#9e0a0a', cursor: 'pointer', margin: 0,
                      }}
                      onClick={() => handleDelete(u.username)}
                    >
                      Rejeter
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Liste */}
        <div style={{ marginTop: 8 }}>
          <label className="lp-label">Joueurs ({users.filter(u => u.is_approved).length})</label>
          <ul className="lp-room-list" style={{ marginTop: 8 }}>
            {users.filter(u => u.is_approved).map(u => (
              <li key={u.id} className="lp-room-item" style={{ cursor: 'default', flexDirection: 'column', alignItems: 'stretch' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span className="lp-room-item-name">
                    {u.username}
                    {u.is_admin && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: '#91918c', fontWeight: 400 }}>
                        admin
                      </span>
                    )}
                    {u.must_change_password && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: '#e60023', fontWeight: 400 }}>
                        mdp temp
                      </span>
                    )}
                  </span>
                  {!u.is_admin && (
                    <button
                      style={{
                        background: 'none', border: '1.5px solid #e0e0e0',
                        borderRadius: 8, padding: '4px 10px',
                        fontSize: 12, color: '#9e0a0a', cursor: 'pointer',
                        margin: 0,
                      }}
                      onClick={() => handleDelete(u.username)}
                    >
                      Supprimer
                    </button>
                  )}
                </div>
                <div className="lp-stats-line">
                  P: {u.games_played} · V: {u.games_won} · D: {u.games_lost} ·{' '}
                  {u.win_rate !== null ? `${Math.round(u.win_rate * 100)}%` : '—'}
                  {(u.capots_won > 0 || u.generales_won > 0) && (
                    <> · Capots: {u.capots_won} · Générales: {u.generales_won}</>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Salons en cours */}
        <div style={{ marginTop: 24 }}>
          <label className="lp-label">Salons ({rooms.length})</label>
          {rooms.length === 0 ? (
            <p className="lp-no-rooms">Aucun salon en cours.</p>
          ) : (
            <ul className="lp-room-list" style={{ marginTop: 8 }}>
              {rooms.map(r => (
                <li
                  key={r.room_id}
                  className="lp-room-item"
                  style={{ cursor: 'default', flexDirection: 'column', alignItems: 'stretch' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span className="lp-room-item-name">
                      {r.room_name || r.room_id}
                      <span className="lp-room-item-code" style={{ marginLeft: 6 }}>#{r.room_id}</span>
                    </span>
                    <button
                      aria-label={`Supprimer le salon ${r.room_name || r.room_id}`}
                      style={{
                        background: 'none', border: '1.5px solid #e0e0e0',
                        borderRadius: 8, padding: '4px 10px',
                        fontSize: 12, color: '#9e0a0a', cursor: 'pointer', margin: 0,
                      }}
                      onClick={() => handleDeleteRoom(r)}
                    >
                      Supprimer
                    </button>
                  </div>
                  <div className="lp-stats-line">
                    {r.creator || '—'} · {PHASE_LABEL[r.phase] ?? r.phase} · {r.player_count}/4 joueurs
                    {r.players.length > 0 && <> · {r.players.join(', ')}</>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
