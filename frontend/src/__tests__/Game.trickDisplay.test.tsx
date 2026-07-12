import { render, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
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
  contract: { bid: { position: 'N', value: 80, is_capot: false, trump: 'H' }, double: 'NONE', bidding_team: 'NS' },
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

describe('Affichage du pli terminé pendant 4 secondes', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('garde les cartes du pli terminé affichées même si la carte suivante est jouée avant 4s', () => {
    const round1 = makeRound()
    const { container, rerender } = render(
      <Game game={makeGame(round1)} error={null} send={vi.fn()} />
    )

    // Le pli terminé (N a gagné avec l'as de ♥) est affiché immédiatement.
    expect(container.querySelector('.trick-pos-bottom')?.textContent).toContain('A')
    // E est à gauche du point de vue de N.
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('K')

    // Le joueur suivant (E) joue déjà une carte du pli suivant, moins de 4s après.
    act(() => vi.advanceTimersByTime(1000))
    const round2 = makeRound({
      current_trick: { cards: [{ position: 'E', card: { suit: 'D', rank: '9' } }], winner: null },
    })
    rerender(<Game game={makeGame(round2)} error={null} send={vi.fn()} />)

    // Le pli précédent doit rester affiché : la nouvelle carte de E (9♦) ne doit pas encore apparaître.
    expect(container.querySelector('.trick-pos-bottom')?.textContent).toContain('A')
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('K')
    expect(container.querySelector('.trick-pos-left')?.textContent).not.toContain('9')
  })

  it("bascule sur le pli en cours une fois les 4 secondes écoulées", () => {
    const round1 = makeRound()
    const { container, rerender } = render(
      <Game game={makeGame(round1)} error={null} send={vi.fn()} />
    )

    const round2 = makeRound({
      current_trick: { cards: [{ position: 'E', card: { suit: 'D', rank: '9' } }], winner: null },
    })
    rerender(<Game game={makeGame(round2)} error={null} send={vi.fn()} />)

    act(() => vi.advanceTimersByTime(4100))
    rerender(<Game game={makeGame(round2)} error={null} send={vi.fn()} />)

    // Passé le délai de 4s, la carte du nouveau pli en cours (9♦ pour E) doit être visible.
    expect(container.querySelector('.trick-pos-left')?.textContent).toContain('9')
  })
})
