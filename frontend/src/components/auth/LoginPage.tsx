import { useState, FormEvent } from 'react'
import type { AuthUser } from '../../store/authStore'

interface Props {
  onLogin: (user: AuthUser) => void
}

export default function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username: username.trim(), password }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? 'Identifiants invalides')
        return
      }
      const user: AuthUser = await r.json()
      onLogin(user)
    } catch {
      setError('Impossible de contacter le serveur')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="lp-root">
      <div className="lp-card">
        <div className="lp-logo">
          <img src="/ace.webp" alt="As de cœur" className="lp-logo-img" />
        </div>
        <h1 className="lp-title">Belote Contrée</h1>
        <p className="lp-subtitle">Connectez-vous pour rejoindre une partie</p>
        <form onSubmit={handleSubmit} noValidate>
          <label className="lp-label" htmlFor="login-username">Identifiant</label>
          <input
            id="login-username"
            className="lp-input"
            value={username}
            placeholder="Votre identifiant"
            autoFocus
            autoComplete="username"
            onChange={e => setUsername(e.target.value)}
          />
          <label className="lp-label" htmlFor="login-password" style={{ marginTop: 16 }}>
            Mot de passe
          </label>
          <input
            id="login-password"
            className="lp-input"
            type="password"
            value={password}
            placeholder="Votre mot de passe"
            autoComplete="current-password"
            onChange={e => setPassword(e.target.value)}
          />
          <button
            type="submit"
            className="lp-btn-primary"
            disabled={!username.trim() || !password || loading}
          >
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
        {error && <p className="lp-error">{error}</p>}
      </div>
    </div>
  )
}
