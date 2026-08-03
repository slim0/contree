import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData } from '../types'

const PLAYERS = { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' }

const makeFinished = (overrides: Partial<GameData> = {}): GameData => ({
  room_id: 'TEST',
  room_name: 'Salon Test',
  players: PLAYERS,
  creator: 'alice',
  scores: { NS: 510, EW: 320 },
  target_score: 500,
  round: null,
  phase: 'FINISHED',
  winner: 'NS', // TEAM RED gagne
  last_result: null,
  messages: [],
  my_position: 'N',
  team_choices: {},
  ready_to_start: false,
  ...overrides,
})

describe('Écran de fin de partie', () => {
  it('affiche VICTOIRE au joueur de l\'équipe gagnante (NS)', () => {
    render(<Game game={makeFinished({ my_position: 'N' })} error={null} send={vi.fn()} />)
    expect(screen.getByText('VICTOIRE !')).toBeInTheDocument()
  })

  it('affiche DÉFAITE au joueur de l\'équipe perdante (EW)', () => {
    render(<Game game={makeFinished({ my_position: 'E' })} error={null} send={vi.fn()} />)
    expect(screen.getByText('DÉFAITE')).toBeInTheDocument()
  })

  it('le créateur voit Rejouer et le clic envoie rematch', async () => {
    const send = vi.fn()
    // alice (N) est le créateur
    render(<Game game={makeFinished({ my_position: 'N' })} error={null} send={send} />)
    await userEvent.click(screen.getByText('Rejouer'))
    expect(send).toHaveBeenCalledWith({ type: 'rematch' })
  })

  it('un non-créateur ne voit pas Rejouer mais un message d\'attente', () => {
    // bob (E) n'est pas créateur
    render(<Game game={makeFinished({ my_position: 'E' })} error={null} send={vi.fn()} />)
    expect(screen.queryByText('Rejouer')).not.toBeInTheDocument()
    expect(screen.getByText(/En attente du créateur/)).toBeInTheDocument()
  })

  it('le clic sur Quitter envoie leave', async () => {
    const send = vi.fn()
    render(<Game game={makeFinished({ my_position: 'E' })} error={null} send={send} />)
    await userEvent.click(screen.getByText('Quitter'))
    expect(send).toHaveBeenCalledWith({ type: 'leave' })
  })
})
