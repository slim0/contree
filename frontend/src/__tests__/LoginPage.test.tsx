import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import LoginPage from '../components/auth/LoginPage'

const mockFetch = vi.fn()
global.fetch = mockFetch

describe('LoginPage', () => {
  const onLogin = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    onLogin.mockReset()
  })

  it('affiche le formulaire de connexion', () => {
    render(<LoginPage onLogin={onLogin} />)
    expect(screen.getByLabelText('Identifiant')).toBeInTheDocument()
    expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Se connecter/i })).toBeInTheDocument()
  })

  it('le bouton est désactivé si les champs sont vides', () => {
    render(<LoginPage onLogin={onLogin} />)
    expect(screen.getByRole('button', { name: /Se connecter/i })).toBeDisabled()
  })

  it('le bouton est actif quand les deux champs sont remplis', () => {
    render(<LoginPage onLogin={onLogin} />)
    fireEvent.change(screen.getByLabelText('Identifiant'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'password' } })
    expect(screen.getByRole('button', { name: /Se connecter/i })).not.toBeDisabled()
  })

  it('appelle onLogin avec les données utilisateur en cas de succès', async () => {
    const userData = { username: 'alice', is_admin: false, must_change_password: false }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => userData,
    })

    render(<LoginPage onLogin={onLogin} />)
    fireEvent.change(screen.getByLabelText('Identifiant'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: /Se connecter/i }))

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith(userData)
    })
  })

  it('affiche un message d\'erreur en cas d\'identifiants invalides', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Identifiants invalides' }),
    })

    render(<LoginPage onLogin={onLogin} />)
    fireEvent.change(screen.getByLabelText('Identifiant'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'mauvais' } })
    fireEvent.click(screen.getByRole('button', { name: /Se connecter/i }))

    await waitFor(() => {
      expect(screen.getByText('Identifiants invalides')).toBeInTheDocument()
    })
    expect(onLogin).not.toHaveBeenCalled()
  })

  it('affiche une erreur réseau si le serveur est injoignable', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))

    render(<LoginPage onLogin={onLogin} />)
    fireEvent.change(screen.getByLabelText('Identifiant'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'password' } })
    fireEvent.click(screen.getByRole('button', { name: /Se connecter/i }))

    await waitFor(() => {
      expect(screen.getByText('Impossible de contacter le serveur')).toBeInTheDocument()
    })
  })
})
