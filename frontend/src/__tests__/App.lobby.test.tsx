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
})
