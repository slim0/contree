import { useState, FormEvent } from 'react'

interface Props {
  onBack: () => void
}

export default function RegisterPage({ onBack }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) return
    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas')
      return
    }
    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username: username.trim(), password }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        setError(body.detail ?? 'Erreur lors de la création du compte')
        return
      }
      setDone(true)
    } catch {
      setError('Impossible de contacter le serveur')
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="lp-root">
        <div className="lp-card">
          <div className="lp-logo">
            <img src="/ace.webp" alt="As de cœur" className="lp-logo-img" />
          </div>
          <h1 className="lp-title">Compte créé</h1>
          <p className="lp-subtitle">
            Votre compte est en attente de validation par l'administrateur. Vous
            pourrez vous connecter une fois qu'il l'aura approuvé.
          </p>
          <button className="lp-btn-primary" onClick={onBack}>
            Retour à la connexion
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="lp-root">
      <div className="lp-card">
        <div className="lp-logo">
          <img src="/ace.webp" alt="As de cœur" className="lp-logo-img" />
        </div>
        <h1 className="lp-title">Créer un compte</h1>
        <p className="lp-subtitle">Un administrateur devra valider votre inscription</p>
        <form onSubmit={handleSubmit} noValidate>
          <label className="lp-label" htmlFor="register-username">Identifiant</label>
          <input
            id="register-username"
            className="lp-input"
            value={username}
            placeholder="Choisissez un identifiant"
            autoFocus
            autoComplete="username"
            onChange={e => setUsername(e.target.value)}
          />
          <label className="lp-label" htmlFor="register-password" style={{ marginTop: 16 }}>
            Mot de passe
          </label>
          <input
            id="register-password"
            className="lp-input"
            type="password"
            value={password}
            placeholder="Au moins 8 caractères"
            autoComplete="new-password"
            onChange={e => setPassword(e.target.value)}
          />
          <label className="lp-label" htmlFor="register-confirm" style={{ marginTop: 16 }}>
            Confirmer le mot de passe
          </label>
          <input
            id="register-confirm"
            className="lp-input"
            type="password"
            value={confirm}
            placeholder="Répétez le mot de passe"
            autoComplete="new-password"
            onChange={e => setConfirm(e.target.value)}
          />
          <button
            type="submit"
            className="lp-btn-primary"
            disabled={!username.trim() || !password || !confirm || loading}
          >
            {loading ? 'Création…' : 'Créer le compte'}
          </button>
        </form>
        {error && <p className="lp-error">{error}</p>}
        <button className="lp-back-inline" style={{ marginTop: 16 }} onClick={onBack}>
          ← Déjà un compte ? Se connecter
        </button>
      </div>
    </div>
  )
}
