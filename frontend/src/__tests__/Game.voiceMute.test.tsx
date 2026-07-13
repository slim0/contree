import { render, screen, waitFor } from '@testing-library/react'
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

describe("Bouton mute quand le micro n'a pas pu être initialisé", () => {
  it('est désactivé au lieu de rester cliquable sans effet (jsdom ne fournit pas navigator.mediaDevices)', async () => {
    render(<Game game={makeGame()} error={null} send={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByTitle('Accès au micro refusé')).toBeDisabled()
    })
  })
})
