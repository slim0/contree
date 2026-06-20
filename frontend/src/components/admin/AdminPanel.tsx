import { useState, useEffect } from 'react'

interface UserRecord {
  id: number
  username: string
  is_admin: boolean
  must_change_password: boolean
  created_at: string
}

interface Props {
  onClose: () => void
  backLabel?: string
}

export default function AdminPanel({ onClose, backLabel = '← Retour au jeu' }: Props) {
  const [users, setUsers] = useState<UserRecord[]>([])
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

  useEffect(() => { fetchUsers() }, [])

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
        <button className="lp-back" onClick={onClose}>{backLabel}</button>
        <h1 className="lp-title" style={{ textAlign: 'left' }}>Gestion des joueurs</h1>

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

        {/* Liste */}
        <div style={{ marginTop: 8 }}>
          <label className="lp-label">Joueurs ({users.length})</label>
          <ul className="lp-room-list" style={{ marginTop: 8 }}>
            {users.map(u => (
              <li key={u.id} className="lp-room-item" style={{ cursor: 'default' }}>
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
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
