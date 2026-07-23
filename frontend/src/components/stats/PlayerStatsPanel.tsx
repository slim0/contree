import { useState, useEffect } from 'react'

interface StatsData {
  username: string
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

interface Props {
  onClose: () => void
  backLabel?: string
}

function formatPercent(rate: number | null): string {
  return rate !== null ? `${Math.round(rate * 100)}%` : '—'
}

export default function PlayerStatsPanel({ onClose, backLabel = '← Retour au jeu' }: Props) {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function fetchStats() {
      try {
        const r = await fetch('/api/users/me/stats', { credentials: 'include' })
        if (!r.ok) {
          if (!cancelled) setError('Impossible de charger vos statistiques')
          return
        }
        const body = await r.json()
        if (!cancelled) setStats(body)
      } catch {
        if (!cancelled) setError('Impossible de contacter le serveur')
      }
    }
    fetchStats()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="lp-root" style={{ zIndex: 100 }}>
      <div className="lp-card" style={{ maxWidth: 480 }}>
        <button className="lp-back" onClick={onClose}>{backLabel}</button>
        <h1 className="lp-title" style={{ textAlign: 'left' }}>Mes statistiques</h1>

        {error && <p className="lp-error">{error}</p>}

        {stats && (
            <div className="ps-grid">
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.games_played}</div>
                <div className="ps-tile-label">Parties jouées</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{formatPercent(stats.win_rate)}</div>
                <div className="ps-tile-label">Taux de victoire</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.games_won}</div>
                <div className="ps-tile-label">Victoires</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.games_lost}</div>
                <div className="ps-tile-label">Défaites</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.capots_won}</div>
                <div className="ps-tile-label">Capots réussis</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.generales_won}</div>
                <div className="ps-tile-label">Générales réussies</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{stats.contracts_taken}</div>
                <div className="ps-tile-label">Contrats pris</div>
              </div>
              <div className="ps-tile">
                <div className="ps-tile-value">{formatPercent(stats.contract_success_rate)}</div>
                <div className="ps-tile-label">Contrats réussis</div>
              </div>
            </div>
        )}
      </div>
    </div>
  )
}
