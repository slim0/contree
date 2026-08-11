import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import App from '../App'

// Références stables pour éviter que useEffect se re-déclenche à chaque render
const mockSetUser = vi.fn()
const mockSetLoading = vi.fn()

vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({
    user: { username: 'alice', is_admin: false, must_change_password: false },
    loading: false,
    setUser: mockSetUser,
    setLoading: mockSetLoading,
  }),
}))

const mockFetch = vi.fn()
global.fetch = mockFetch

// WebSocket mock sous forme de classe pour être utilisable avec `new`
let lastWsInstance: MockWebSocketInstance | null = null

class MockWebSocketInstance {
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  readyState = 1
  send = vi.fn()
  close = vi.fn()
  url: string
  constructor(url: string) {
    this.url = url
    lastWsInstance = this
  }
}
// @ts-expect-error
global.WebSocket = MockWebSocketInstance
// @ts-expect-error
global.WebSocket.CLOSING = 2

describe('App — rejoindre un salon', () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
    })
    lastWsInstance = null
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null)
    vi.spyOn(Storage.prototype, 'setItem').mockReturnValue(undefined)
    vi.spyOn(Storage.prototype, 'removeItem').mockReturnValue(undefined)
  })

  it('cliquer sur un salon bascule en saisie de code sans pré-remplir le champ', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          rooms: [
            { room_id: 'AB3X', room_name: 'Salon de Simon', player_count: 1, phase: 'WAITING' },
          ],
        }),
      })

    render(<App />)

    fireEvent.click(screen.getByText(/Rejoindre un salon existant/i))

    await waitFor(() => {
      expect(screen.getByText('Salon de Simon')).toBeInTheDocument()
    })

    // Clic sur le salon → affiche le champ de saisie du code
    fireEvent.click(screen.getByText('Salon de Simon'))

    const input = screen.getByLabelText('Code du salon') as HTMLInputElement
    // Le champ doit être vide — l'utilisateur doit saisir le code lui-même
    expect(input.value).toBe('')
  })

  // Régression : un mauvais code ne doit pas bloquer l'utilisateur sur "reconnexion en cours".
  // Le backend rejette avec {"type":"error","message":"Salon introuvable."} et le frontend
  // doit stopper la reconnexion automatique et afficher l'erreur dans le lobby.
  it('revient au lobby avec un message d\'erreur si le salon est introuvable (pas de boucle de reconnexion)', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ rooms: [] }),
      })

    render(<App />)

    // Naviguer jusqu'au champ de saisie manuelle
    fireEvent.click(screen.getByText(/Rejoindre un salon existant/i))
    await waitFor(() => screen.getByText(/Entrer un code manuellement/i))
    fireEvent.click(screen.getByText(/Entrer un code manuellement/i))

    const input = screen.getByLabelText('Code du salon')
    fireEvent.change(input, { target: { value: 'XXXX' } })
    fireEvent.click(screen.getByText('Rejoindre'))

    // Simuler l'ouverture de la connexion WebSocket (onopen → shouldReconnect = true)
    await waitFor(() => expect(lastWsInstance).not.toBeNull())
    act(() => { lastWsInstance!.onopen?.(new Event('open')) })

    // Simuler la réception de l'erreur "Salon introuvable."
    act(() => {
      lastWsInstance!.onmessage?.({ data: JSON.stringify({ type: 'error', message: 'Salon introuvable.' }) })
    })

    // Simuler la fermeture de la connexion par le backend
    act(() => { lastWsInstance!.onclose?.() })

    // L'utilisateur doit voir l'erreur dans le lobby — pas la page "reconnexion en cours"
    await waitFor(() => {
      expect(screen.getByText('Salon introuvable.')).toBeInTheDocument()
    })
    expect(screen.queryByText(/Reconnexion en cours/i)).not.toBeInTheDocument()
  })

  // Scripts DEV/init*.sh --quick : le salon est déjà créé côté backend (dev quickstart),
  // le front doit s'y connecter directement sans passer par le lobby.
  it('affiche le panel "Mes statistiques" au clic sur le bouton du lobby', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [] }) })

    render(<App />)

    const statsButton = await screen.findByText('Mes statistiques')
    fireEvent.click(statsButton)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mes statistiques' })).toBeInTheDocument()
    })
  })

  it('se connecte automatiquement au salon donné par ?room=CODE dans l\'URL', async () => {
    window.history.pushState({}, '', '/?room=test')
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
    })

    render(<App />)

    await waitFor(() => expect(lastWsInstance).not.toBeNull())
    expect(lastWsInstance!.url).toContain('/ws/TEST?')

    window.history.pushState({}, '', '/')
  })

  // Bouton "Quitter" en cours de partie : retour à l'accueil sans envoyer "leave"
  // (le siège reste réservé) et sans boucle de reconnexion.
  it('revient au lobby quand on quitte la partie depuis la table', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValue({ ok: true, json: async () => ({ rooms: [] }) })

    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('AB3X')

    render(<App />)

    await waitFor(() => expect(lastWsInstance).not.toBeNull())
    act(() => { lastWsInstance!.onopen?.(new Event('open')) })
    act(() => {
      lastWsInstance!.onmessage?.({
        data: JSON.stringify({
          type: 'state',
          data: {
            room_id: 'AB3X',
            room_name: 'Salon de Simon',
            players: { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' },
            scores: { NS: 0, EW: 0 },
            target_score: 1000,
            round: null,
            phase: 'BIDDING',
            winner: null,
            last_result: null,
            messages: [],
            my_position: 'N',
            team_choices: {},
            ready_to_start: false,
          },
        }),
      })
    })

    // La connexion courante (le hook peut en avoir recréé une depuis le montage)
    const ws = lastWsInstance!

    fireEvent.click(await screen.findByLabelText('Quitter la partie'))
    fireEvent.click(screen.getByRole('button', { name: 'Quitter' }))

    // Le backend n'est pas notifié : quitter en cours de partie = déconnexion simple
    expect(ws.send).not.toHaveBeenCalled()
    expect(ws.close).toHaveBeenCalled()
    expect(Storage.prototype.removeItem).toHaveBeenCalledWith('contree_room')

    // La fermeture qui suit ne doit pas relancer une reconnexion
    act(() => { ws.onclose?.() })

    await waitFor(() => {
      expect(screen.getByText(/Créer un salon/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/Reconnexion en cours/i)).not.toBeInTheDocument()
  })

  // ── Suppression d'un salon par son créateur ─────────────────────────────────

  const roomsWithMine = [
    { room_id: 'AB3X', room_name: 'Salon de Simon', creator: 'bob', player_count: 1, phase: 'WAITING' },
    { room_id: 'CD9Z', room_name: 'Mon salon', creator: 'alice', player_count: 2, phase: 'WAITING' },
  ]

  function mockLobbyWithRooms(rooms: unknown[]) {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms }) })
  }

  it('n\'affiche le bouton de suppression que sur les salons dont je suis le créateur', async () => {
    mockLobbyWithRooms(roomsWithMine)

    render(<App />)
    fireEvent.click(screen.getByText(/Rejoindre un salon existant/i))

    await waitFor(() => expect(screen.getByText('Mon salon')).toBeInTheDocument())
    expect(screen.getByLabelText('Supprimer le salon Mon salon')).toBeInTheDocument()
    expect(screen.queryByLabelText('Supprimer le salon Salon de Simon')).not.toBeInTheDocument()
  })

  it('supprime mon salon après confirmation et recharge la liste', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockLobbyWithRooms(roomsWithMine)
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) }) // DELETE
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rooms: [roomsWithMine[0]] }) })

    render(<App />)
    fireEvent.click(screen.getByText(/Rejoindre un salon existant/i))
    await waitFor(() => screen.getByText('Mon salon'))

    fireEvent.click(screen.getByLabelText('Supprimer le salon Mon salon'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/rooms/CD9Z',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
    await waitFor(() => {
      expect(screen.queryByText('Mon salon')).not.toBeInTheDocument()
    })
    // Le clic sur ✕ ne doit pas basculer sur la saisie de code
    expect(screen.queryByLabelText('Code du salon')).not.toBeInTheDocument()
  })

  it('affiche une erreur si la suppression est refusée par le backend', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockLobbyWithRooms(roomsWithMine)
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Seul le créateur du salon peut le supprimer' }),
    })

    render(<App />)
    fireEvent.click(screen.getByText(/Rejoindre un salon existant/i))
    await waitFor(() => screen.getByText('Mon salon'))

    fireEvent.click(screen.getByLabelText('Supprimer le salon Mon salon'))

    await waitFor(() => {
      expect(screen.getByText('Seul le créateur du salon peut le supprimer')).toBeInTheDocument()
    })
    expect(screen.getByText('Mon salon')).toBeInTheDocument()
  })

  // Un joueur assis dans un salon supprimé par son créateur (ou un admin) est
  // renvoyé au lobby avec la raison, sans boucle de reconnexion.
  it('revient au lobby quand le salon est supprimé pendant la partie', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: 'alice', is_admin: false, must_change_password: false }),
      })
      .mockResolvedValue({ ok: true, json: async () => ({ rooms: [] }) })

    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('AB3X')

    render(<App />)

    await waitFor(() => expect(lastWsInstance).not.toBeNull())
    act(() => { lastWsInstance!.onopen?.(new Event('open')) })

    // lastWsInstance est relu à chaque étape : le hook peut avoir recréé la connexion
    act(() => {
      lastWsInstance!.onmessage?.({
        data: JSON.stringify({ type: 'room_closed', message: 'Le salon a été supprimé.' }),
      })
    })
    act(() => { lastWsInstance!.onclose?.() })

    await waitFor(() => {
      expect(screen.getByText('Le salon a été supprimé.')).toBeInTheDocument()
    })
    expect(screen.queryByText(/Reconnexion en cours/i)).not.toBeInTheDocument()
    expect(Storage.prototype.removeItem).toHaveBeenCalledWith('contree_room')
  })
})
