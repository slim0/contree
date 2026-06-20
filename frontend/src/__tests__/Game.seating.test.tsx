import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData } from '../types'

// Scénario rapporté : bob+diana (EW) et alice+charlie (NS) sont partenaires,
// donc bob/diana occupent forcément E/W et alice/charlie occupent forcément N/S.
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

function namesAt(container: HTMLElement, slotClass: string): string | null {
  return container.querySelector(`.${slotClass} .player-name`)?.textContent ?? null
}

describe('Positionnement relatif des joueurs autour de la table', () => {
  it("du point de vue de charlie (S), bob (E) est à droite et diana (W) à gauche", () => {
    const { container } = render(
      <Game game={makeGame({ my_position: 'S' })} error={null} send={vi.fn()} />
    )
    expect(namesAt(container, 'slot-right')).toBe('bob')
    expect(namesAt(container, 'slot-left')).toBe('diana')
  })

  it("du point de vue de diana (W), charlie (S) doit être à droite (pas à gauche)", () => {
    const { container } = render(
      <Game game={makeGame({ my_position: 'W' })} error={null} send={vi.fn()} />
    )
    expect(namesAt(container, 'slot-right')).toBe('charlie')
    expect(namesAt(container, 'slot-left')).toBe('alice')
  })

  it('la relation gauche/droite est symétrique entre deux voisins (N et E)', () => {
    const { container: fromN } = render(
      <Game game={makeGame({ my_position: 'N' })} error={null} send={vi.fn()} />
    )
    // alice (N) voit bob (E) à sa gauche
    expect(namesAt(fromN, 'slot-left')).toBe('bob')

    const { container: fromE } = render(
      <Game game={makeGame({ my_position: 'E' })} error={null} send={vi.fn()} />
    )
    // donc bob (E) doit voir alice (N) à sa droite
    expect(namesAt(fromE, 'slot-right')).toBe('alice')
  })
})
