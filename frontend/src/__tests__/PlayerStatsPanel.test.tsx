import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import PlayerStatsPanel from '../components/stats/PlayerStatsPanel'

const mockFetch = vi.fn()
global.fetch = mockFetch

const mockStats = {
  username: 'testuser',
  games_played: 5,
  games_won: 3,
  games_lost: 2,
  win_rate: 0.6,
  capots_won: 1,
  generales_won: 0,
  contracts_taken: 4,
  contracts_made: 3,
  contract_success_rate: 0.75,
}

describe('PlayerStatsPanel', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    onClose.mockReset()
    mockFetch.mockResolvedValue({ ok: true, json: async () => mockStats })
  })

  it('affiche les statistiques du joueur connecté', async () => {
    render(<PlayerStatsPanel onClose={onClose} />)
    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument() // games_played
    })
    expect(screen.getByText('60%')).toBeInTheDocument() // win_rate
    expect(screen.getByText('3')).toBeInTheDocument() // games_won
    expect(screen.getByText('2')).toBeInTheDocument() // games_lost
    expect(screen.getByText('1')).toBeInTheDocument() // capots_won
    expect(screen.getByText('75%')).toBeInTheDocument() // contract_success_rate
  })

  it('affiche "—" quand aucun taux n\'est calculable (0 partie jouée)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        username: 'brandnew',
        games_played: 0,
        games_won: 0,
        games_lost: 0,
        win_rate: null,
        capots_won: 0,
        generales_won: 0,
        contracts_taken: 0,
        contracts_made: 0,
        contract_success_rate: null,
      }),
    })
    render(<PlayerStatsPanel onClose={onClose} />)
    await waitFor(() => {
      expect(screen.getAllByText('—').length).toBe(2)
    })
    expect(screen.queryByText('NaN%')).not.toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('affiche une erreur si le fetch échoue', async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({}) })
    render(<PlayerStatsPanel onClose={onClose} />)
    await waitFor(() => {
      expect(screen.getByText('Impossible de charger vos statistiques')).toBeInTheDocument()
    })
  })

  it('appelle onClose au clic sur Retour', () => {
    render(<PlayerStatsPanel onClose={onClose} />)
    fireEvent.click(screen.getByText(/Retour au jeu/i))
    expect(onClose).toHaveBeenCalled()
  })
})
