import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import AdminPanel from '../components/admin/AdminPanel'

const mockFetch = vi.fn()
global.fetch = mockFetch

const mockUsers = [
  { id: 1, username: 'admin', is_admin: true, must_change_password: false, created_at: '2024-01-01T00:00:00Z' },
  { id: 2, username: 'alice', is_admin: false, must_change_password: false, created_at: '2024-01-02T00:00:00Z' },
  { id: 3, username: 'bob', is_admin: false, must_change_password: true, created_at: '2024-01-03T00:00:00Z' },
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

  it('appelle onClose au clic sur Retour', async () => {
    render(<AdminPanel onClose={onClose} />)
    fireEvent.click(screen.getByText(/Retour au jeu/i))
    expect(onClose).toHaveBeenCalled()
  })

  it('crée un utilisateur et affiche le mot de passe temporaire', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers }) // GET initial
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

  it('affiche une erreur si le nom d\'utilisateur est déjà pris', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => mockUsers }) // GET initial
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
})
