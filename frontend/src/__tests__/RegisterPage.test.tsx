import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import RegisterPage from '../components/auth/RegisterPage'

const mockFetch = vi.fn()
global.fetch = mockFetch

describe('RegisterPage', () => {
  const onBack = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    onBack.mockReset()
  })

  function fill(username: string, password: string, confirm: string) {
    fireEvent.change(screen.getByLabelText('Identifiant'), { target: { value: username } })
    fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: password } })
    fireEvent.change(screen.getByLabelText('Confirmer le mot de passe'), { target: { value: confirm } })
  }

  it('affiche le formulaire d\'inscription', () => {
    render(<RegisterPage onBack={onBack} />)
    expect(screen.getByLabelText('Identifiant')).toBeInTheDocument()
    expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirmer le mot de passe')).toBeInTheDocument()
  })

  it('refuse si les mots de passe ne correspondent pas', async () => {
    render(<RegisterPage onBack={onBack} />)
    fill('alice', 'password1', 'password2')
    fireEvent.click(screen.getByRole('button', { name: /Créer le compte/i }))
    await waitFor(() => {
      expect(screen.getByText(/ne correspondent pas/i)).toBeInTheDocument()
    })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('refuse un mot de passe trop court', async () => {
    render(<RegisterPage onBack={onBack} />)
    fill('alice', 'court', 'court')
    fireEvent.click(screen.getByRole('button', { name: /Créer le compte/i }))
    await waitFor(() => {
      expect(screen.getByText(/au moins 8 caractères/i)).toBeInTheDocument()
    })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('affiche le message d\'attente de validation en cas de succès', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ detail: 'Compte créé, en attente de validation par l\'administrateur' }),
    })
    render(<RegisterPage onBack={onBack} />)
    fill('alice', 'password123', 'password123')
    fireEvent.click(screen.getByRole('button', { name: /Créer le compte/i }))
    await waitFor(() => {
      expect(screen.getByText(/en attente de validation/i)).toBeInTheDocument()
    })
  })

  it('affiche l\'erreur backend (username déjà pris)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Ce nom d\'utilisateur est déjà pris' }),
    })
    render(<RegisterPage onBack={onBack} />)
    fill('admin', 'password123', 'password123')
    fireEvent.click(screen.getByRole('button', { name: /Créer le compte/i }))
    await waitFor(() => {
      expect(screen.getByText('Ce nom d\'utilisateur est déjà pris')).toBeInTheDocument()
    })
  })
})
