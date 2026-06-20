import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import ChangePasswordPage from '../components/auth/ChangePasswordPage'

const mockFetch = vi.fn()
global.fetch = mockFetch

describe('ChangePasswordPage', () => {
  const onChanged = vi.fn()

  beforeEach(() => {
    mockFetch.mockReset()
    onChanged.mockReset()
  })

  it('affiche le nom de l\'utilisateur', () => {
    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    expect(screen.getByText('alice')).toBeInTheDocument()
  })

  it('affiche les trois champs de formulaire', () => {
    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    expect(screen.getByLabelText('Mot de passe temporaire')).toBeInTheDocument()
    expect(screen.getByLabelText('Nouveau mot de passe')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirmer')).toBeInTheDocument()
  })

  it('le bouton est désactivé si les champs sont vides', () => {
    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeDisabled()
  })

  it('affiche une erreur si les mots de passe ne correspondent pas', async () => {
    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    fireEvent.change(screen.getByLabelText('Mot de passe temporaire'), { target: { value: 'oldpass' } })
    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'newpass1!' } })
    fireEvent.change(screen.getByLabelText('Confirmer'), { target: { value: 'different' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))
    expect(screen.getByText('Les mots de passe ne correspondent pas')).toBeInTheDocument()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('affiche une erreur si le nouveau mot de passe est trop court', async () => {
    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    fireEvent.change(screen.getByLabelText('Mot de passe temporaire'), { target: { value: 'oldpass' } })
    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'court' } })
    fireEvent.change(screen.getByLabelText('Confirmer'), { target: { value: 'court' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))
    expect(screen.getByText(/au moins 8 caractères/i)).toBeInTheDocument()
  })

  it('appelle onChanged avec les données mises à jour en cas de succès', async () => {
    const updatedUser = { username: 'alice', is_admin: false, must_change_password: false }
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => updatedUser })

    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    fireEvent.change(screen.getByLabelText('Mot de passe temporaire'), { target: { value: 'oldpass' } })
    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'nouveauPass1!' } })
    fireEvent.change(screen.getByLabelText('Confirmer'), { target: { value: 'nouveauPass1!' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(updatedUser)
    })
  })

  it('affiche une erreur en cas de mauvais ancien mot de passe', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Ancien mot de passe incorrect' }),
    })

    render(<ChangePasswordPage username="alice" onChanged={onChanged} />)
    fireEvent.change(screen.getByLabelText('Mot de passe temporaire'), { target: { value: 'mauvais' } })
    fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'nouveauPass1!' } })
    fireEvent.change(screen.getByLabelText('Confirmer'), { target: { value: 'nouveauPass1!' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => {
      expect(screen.getByText('Ancien mot de passe incorrect')).toBeInTheDocument()
    })
  })
})
