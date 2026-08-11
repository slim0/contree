import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import AdminPanel from '../components/admin/AdminPanel'

const mockFetch = vi.fn()
global.fetch = mockFetch

const baseStats = {
  games_played: 0,
  games_won: 0,
  games_lost: 0,
  win_rate: null,
  capots_won: 0,
  generales_won: 0,
  contracts_taken: 0,
  contracts_made: 0,
  contract_success_rate: null,
}

const mockUsers = [
  { id: 1, username: 'admin', is_admin: true, must_change_password: false, is_approved: true, created_at: '2024-01-01T00:00:00Z', ...baseStats },
  {
    id: 2, username: 'alice', is_admin: false, must_change_password: false, is_approved: true, created_at: '2024-01-02T00:00:00Z',
    ...baseStats, games_played: 10, games_won: 6, games_lost: 4, win_rate: 0.6,
  },
  { id: 3, username: 'bob', is_admin: false, must_change_password: true, is_approved: true, created_at: '2024-01-03T00:00:00Z', ...baseStats },
]

describe('AdminPanel', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    onClose.mockReset()
    mockFetch.mockResolvedValue({ ok: true, json: async () => mockUsers })
  })

  it('affiche la liste des utilisateurs', async () => {
    render(<AdminPanel onClose={onClose} />)
    // alice et bob sont uniques dans le DOM
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument()
      expect(screen.getByText('bob')).toBeInTheDocument()
    })
    // admin apparaît deux fois (username + badge rôle) — getAllByText évite l'ambiguïté
    expect(screen.getAllByText('admin').length).toBeGreaterThanOrEqual(1)
  })

  it('indique les utilisateurs avec mdp temporaire', async () => {
    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => {
      expect(screen.getByText('mdp temp')).toBeInTheDocument()
    })
  })

  it('n\'affiche pas le bouton Supprimer pour l\'admin', async () => {
    render(<AdminPanel onClose={onClose} />)
    // attendre que la liste soit chargée (alice est unique)
    await waitFor(() => screen.getByText('alice'))
    // 2 boutons supprimer pour alice et bob, pas pour admin
    const deleteButtons = screen.getAllByText('Supprimer')
    expect(deleteButtons).toHaveLength(2)
  })

  it('affiche les statistiques par joueur', async () => {
    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => screen.getByText('alice'))
    expect(screen.getByText(/P: 10 · V: 6 · D: 4 · 60%/)).toBeInTheDocument()
    // admin et bob n'ont jamais joué : taux de victoire affiché comme "—", pas "NaN%" ni "0%"
    expect(screen.getAllByText(/P: 0 · V: 0 · D: 0 · —/)).toHaveLength(2)
  })

  it('appelle onClose au clic sur Retour', async () => {
    render(<AdminPanel onClose={onClose} />)
    fireEvent.click(screen.getByText(/Retour au jeu/i))
    expect(onClose).toHaveBeenCalled()
  })

  it('affiche un label personnalisé pour le bouton retour', async () => {
    render(<AdminPanel onClose={onClose} backLabel="Déconnexion" />)
    expect(screen.getByText('Déconnexion')).toBeInTheDocument()
    expect(screen.queryByText(/Retour au jeu/i)).not.toBeInTheDocument()
  })

  it('crée un utilisateur et affiche le mot de passe temporaire', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers }) // GET users initial
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [] }) }) // GET rooms initial
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          user: { id: 4, username: 'nouveau', is_admin: false, must_change_password: true, created_at: '2024-01-04T00:00:00Z' },
          temp_password: 'MotDePasseTemp',
        }),
      }) // POST create
    // GET après création utilise le default (mockUsers)

    render(<AdminPanel onClose={onClose} />)
    // attendre le chargement initial
    await waitFor(() => screen.getByText('alice'))

    fireEvent.change(screen.getByPlaceholderText('Identifiant'), { target: { value: 'nouveau' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer/i }))

    await waitFor(() => {
      expect(screen.getByText('MotDePasseTemp')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('affiche un lien "Mes statistiques" quand onShowStats est fourni', async () => {
    const onShowStats = vi.fn()
    render(<AdminPanel onClose={onClose} onShowStats={onShowStats} />)
    fireEvent.click(screen.getByText('Mes statistiques'))
    expect(onShowStats).toHaveBeenCalled()
  })

  it('n\'affiche pas de lien "Mes statistiques" sans onShowStats', async () => {
    render(<AdminPanel onClose={onClose} />)
    expect(screen.queryByText('Mes statistiques')).not.toBeInTheDocument()
  })

  it('affiche les comptes en attente avec un bouton Approuver et déclenche l\'approbation', async () => {
    const pending = { id: 5, username: 'newbie', is_admin: false, must_change_password: false, is_approved: false, created_at: '2024-01-05T00:00:00Z', ...baseStats }
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => [...mockUsers, pending] }) // GET users initial
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [] }) }) // GET rooms initial
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...pending, is_approved: true }) }) // POST approve
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers }) // GET refresh

    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => screen.getByText('newbie'))
    expect(screen.getByText(/En attente d'approbation/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Approuver/i }))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/admin/users/newbie/approve',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('affiche une erreur si le nom d\'utilisateur est déjà pris', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers }) // GET users initial
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [] }) }) // GET rooms initial
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Ce nom d\'utilisateur est déjà pris' }),
      }) // POST → 409

    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => screen.getByText('alice'))

    fireEvent.change(screen.getByPlaceholderText('Identifiant'), { target: { value: 'admin' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer/i }))

    await waitFor(() => {
      expect(screen.getByText('Ce nom d\'utilisateur est déjà pris')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  // ── Gestion des salons ──────────────────────────────────────────────────────

  const mockRooms = [
    {
      room_id: 'AB3X', room_name: 'Salon de Simon', creator: 'alice',
      phase: 'PLAYING', player_count: 4, players: ['alice', 'bob', 'carol', 'dan'],
      target_score: 1000,
    },
  ]

  it('affiche les salons en cours', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: mockRooms }) })

    render(<AdminPanel onClose={onClose} />)

    await waitFor(() => expect(screen.getByText(/Salons \(1\)/)).toBeInTheDocument())
    expect(screen.getByText('Salon de Simon')).toBeInTheDocument()
    expect(screen.getByText('#AB3X')).toBeInTheDocument()
    expect(screen.getByText(/alice · En jeu · 4\/4 joueurs/)).toBeInTheDocument()
  })

  it('supprime un salon après confirmation et recharge la liste', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: mockRooms }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) }) // DELETE
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [] }) }) // GET rooms refresh

    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => screen.getByText('Salon de Simon'))

    fireEvent.click(screen.getByRole('button', { name: 'Supprimer le salon Salon de Simon' }))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/rooms/AB3X',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
    await waitFor(() => {
      expect(screen.queryByText('Salon de Simon')).not.toBeInTheDocument()
      expect(screen.getByText('Aucun salon en cours.')).toBeInTheDocument()
    })
  })

  it('ne supprime pas le salon si la confirmation est refusée', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: mockRooms }) })

    render(<AdminPanel onClose={onClose} />)
    await waitFor(() => screen.getByText('Salon de Simon'))

    fireEvent.click(screen.getByRole('button', { name: 'Supprimer le salon Salon de Simon' }))

    expect(mockFetch).not.toHaveBeenCalledWith(
      '/api/rooms/AB3X',
      expect.objectContaining({ method: 'DELETE' }),
    )
    expect(screen.getByText('Salon de Simon')).toBeInTheDocument()
  })
})
