import { render } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData, RoundData } from '../types'

const PLAYERS = { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' }

const finishedTrick = {
  cards: [
    { position: 'N', card: { suit: 'H', rank: 'A' } },
    { position: 'E', card: { suit: 'H', rank: 'K' } },
    { position: 'S', card: { suit: 'H', rank: 'Q' } },
    { position: 'W', card: { suit: 'H', rank: 'J' } },
  ],
  winner: 'N',
}

const makeRound = (overrides: Partial<RoundData> = {}): RoundData => ({
  number: 1,
  dealer: 'N',
  hands: { N: [], E: [], S: [], W: [] },
  phase: 'PLAYING',
  current_bidder: null,
  pass_count: 0,
  bid_history: [],
  contract: { bid: { position: 'N', value: 80, is_capot: false, is_generale: false, trump: 'H' }, double: 'NONE', bidding_team: 'NS' },
  current_player: 'E',
  tricks: [finishedTrick],
  current_trick: { cards: [], winner: null },
  belote_team: null,
  belote_king_played: false,
  belote_queen_played: false,
  running_points: {},
  ...overrides,
})

const makeGame = (round: RoundData): GameData => ({
  room_id: 'TEST',
  room_name: 'Salon Test',
  players: PLAYERS,
  scores: { NS: 0, EW: 0 },
  target_score: 1000,
  round,
  phase: 'PLAYING',
  winner: null,
  last_result: null,
  messages: [],
  my_position: 'N',
  team_choices: {},
  ready_to_start: false,
})

describe('Affichage du pli terminé', () => {
  it('reste affiché tant que personne n’a joué dans le pli suivant', () => {
    const round = makeRound()
    const { container } = render(
      <Game game={makeGame(round)} error={null} send={vi.fn()} />
    )

    // Le pli terminé (N a gagné avec l'as de ♥) est affiché.
    expect(container.querySelector('.trick-pos-bottom')?.textContent).toContain('A')
    // E est à gauche du point de vue de N.
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('K')
  })

  it('bascule immédiatement sur le pli suivant dès que le joueur qui doit jouer y joue une carte', () => {
    const round1 = makeRound()
    const { container, rerender } = render(
      <Game game={makeGame(round1)} error={null} send={vi.fn()} />
    )
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('K')

    // E (à gauche) joue sa carte du pli suivant : on doit basculer tout de suite,
    // sans attendre un quelconque délai.
    const round2 = makeRound({
      current_trick: { cards: [{ position: 'E', card: { suit: 'D', rank: '9' } }], winner: null },
    })
    rerender(<Game game={makeGame(round2)} error={null} send={vi.fn()} />)

    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('9')
    expect(container.querySelector('.trick-pos-left')?.textContent).not.toContain('K')
  })

  it('affiche le dernier pli pendant la phase SCORING (avant la donne suivante)', () => {
    const round = makeRound({
      phase: 'SCORING',
      current_player: null,
      current_trick: { cards: [], winner: null },
    })
    const { container } = render(
      <Game game={makeGame(round)} error={null} send={vi.fn()} />
    )

    expect(container.querySelector('.trick-pos-bottom')?.textContent).toContain('A')
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('K')
  })
})
