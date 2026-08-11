import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData } from '../types'

const PLAYERS = { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' }

const makeGame = (overrides: Partial<GameData> = {}): GameData => ({
  room_id: 'TEST',
  room_name: 'Salon Test',
  players: PLAYERS,
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
  ...overrides,
})

describe('Bouton Quitter en cours de partie', () => {
  it('demande confirmation avant de quitter', async () => {
    const onQuit = vi.fn()
    render(<Game game={makeGame()} error={null} send={vi.fn()} onQuit={onQuit} />)

    await userEvent.click(screen.getByLabelText('Quitter la partie'))

    expect(screen.getByText('Quitter la partie ?')).toBeInTheDocument()
    expect(onQuit).not.toHaveBeenCalled()
  })

  it('appelle onQuit après confirmation', async () => {
    const onQuit = vi.fn()
    const send = vi.fn()
    render(<Game game={makeGame()} error={null} send={send} onQuit={onQuit} />)

    await userEvent.click(screen.getByLabelText('Quitter la partie'))
    await userEvent.click(screen.getByRole('button', { name: 'Quitter' }))

    expect(onQuit).toHaveBeenCalledTimes(1)
    // On ne notifie pas le serveur : le siège reste réservé pour la reconnexion.
    expect(send).not.toHaveBeenCalled()
  })

  it('referme la confirmation sur Annuler sans quitter', async () => {
    const onQuit = vi.fn()
    render(<Game game={makeGame()} error={null} send={vi.fn()} onQuit={onQuit} />)

    await userEvent.click(screen.getByLabelText('Quitter la partie'))
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))

    expect(screen.queryByText('Quitter la partie ?')).not.toBeInTheDocument()
    expect(onQuit).not.toHaveBeenCalled()
  })
})
