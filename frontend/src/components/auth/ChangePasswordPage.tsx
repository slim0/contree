import { useState, FormEvent } from 'react'
import type { AuthUser } from '../../store/authStore'

interface Props {
  username: string
  onChanged: (user: AuthUser) => void
}

export default function ChangePasswordPage({ username, onChanged }: Props) {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (newPassword !== confirm) {
      setError('Les mots de passe ne correspondent pas')
      return
    }
    if (newPassword.length < 8) {
      setError('Le nouveau mot de passe doit contenir au moins 8 caractères')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? 'Erreur lors du changement de mot de passe')
        return
      }
      const user: AuthUser = await r.json()
      onChanged(user)
    } catch {
      setError('Impossible de contacter le serveur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="lp-root">
      <div className="lp-card">
        <h1 className="lp-title">Nouveau mot de passe</h1>
        <p className="lp-subtitle">
          Bonjour <strong>{username}</strong>, vous devez définir un mot de passe personnel avant de continuer.
        </p>
        <form onSubmit={handleSubmit} noValidate>
          <label className="lp-label" htmlFor="cp-old">Mot de passe temporaire</label>
          <input
            id="cp-old"
            className="lp-input"
            type="password"
            value={oldPassword}
            placeholder="Mot de passe reçu de l'admin"
            autoFocus
            autoComplete="current-password"
            onChange={e => setOldPassword(e.target.value)}
          />
          <label className="lp-label" htmlFor="cp-new" style={{ marginTop: 16 }}>Nouveau mot de passe</label>
          <input
            id="cp-new"
            className="lp-input"
            type="password"
            value={newPassword}
            placeholder="Au moins 8 caractères"
            autoComplete="new-password"
            onChange={e => setNewPassword(e.target.value)}
          />
          <label className="lp-label" htmlFor="cp-confirm" style={{ marginTop: 16 }}>Confirmer</label>
          <input
            id="cp-confirm"
            className="lp-input"
            type="password"
            value={confirm}
            placeholder="Répétez le nouveau mot de passe"
            autoComplete="new-password"
            onChange={e => setConfirm(e.target.value)}
          />
          <button
            type="submit"
            className="lp-btn-primary"
            disabled={!oldPassword || !newPassword || !confirm || loading}
          >
            {loading ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </form>
        {error && <p className="lp-error">{error}</p>}
      </div>
    </div>
  )
}
