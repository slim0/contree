import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import Game from '../Game'
import type { GameData, RoundResult } from '../types'

const PLAYERS = { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' }

const makeResult = (overrides: Partial<RoundResult> = {}): RoundResult => ({
  round_number: 1,
  contract: {
    bid: { position: 'N', value: 80, is_capot: false, is_generale: false, trump: 'H' },
    double: 'NONE',
    bidding_team: 'NS',
  },
  preneurs_eval: 95,
  contract_made: true,
  score_ns: 80,
  score_ew: 0,
  belote_team: null,
  message: 'Contrat réussi NS 80 à H (95 pts)',
  ...overrides,
})

const makeGame = (overrides: Partial<GameData> = {}): GameData => ({
  room_id: 'TEST',
  room_name: 'Salon Test',
  players: PLAYERS,
  scores: { NS: 80, EW: 0 },
  target_score: 1000,
  round: null,
  phase: 'BIDDING',
  winner: null,
  last_result: null,
  round_history: [],
  messages: [],
  my_position: 'N',
  team_choices: {},
  ready_to_start: false,
  ...overrides,
})

describe('Bouton scores de la partie', () => {
  it("ouvre le récapitulatif des scores au clic sur le bouton d'en-tête", async () => {
    render(<Game game={makeGame()} error={null} send={vi.fn()} />)

    expect(screen.queryByText('Scores de la partie')).not.toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Scores de la partie'))

    expect(screen.getByText('Scores de la partie')).toBeInTheDocument()
  })

  it("affiche un message quand aucune manche n'est terminée", async () => {
    render(<Game game={makeGame({ round_history: [] })} error={null} send={vi.fn()} />)

    await userEvent.click(screen.getByLabelText('Scores de la partie'))

    expect(screen.getByText('Aucune manche terminée pour l’instant.')).toBeInTheDocument()
  })

  it('liste chaque manche terminée avec son contrat et son résultat', async () => {
    const history = [
      makeResult({ round_number: 1, contract_made: true, score_ns: 80, score_ew: 0 }),
      makeResult({
        round_number: 2,
        contract_made: false,
        score_ns: 0,
        score_ew: 90,
        contract: {
          bid: { position: 'E', value: 90, is_capot: false, is_generale: false, trump: 'D' },
          double: 'NONE',
          bidding_team: 'EW',
        },
      }),
    ]
    render(
      <Game
        game={makeGame({ round_history: history, scores: { NS: 80, EW: 90 } })}
        error={null}
        send={vi.fn()}
      />
    )

    await userEvent.click(screen.getByLabelText('Scores de la partie'))

    expect(screen.getByText('✓ Réussi')).toBeInTheDocument()
    expect(screen.getByText('✗ Chuté')).toBeInTheDocument()
    expect(screen.getByText('+80')).toBeInTheDocument()
    expect(screen.getByText('+90')).toBeInTheDocument()
    // Ligne de total = score cumulé de la partie (game.scores, pas la somme des manches)
    const totalRow = screen.getByText('Total').closest('tr')
    expect(totalRow).not.toBeNull()
    expect(totalRow!.textContent).toContain('80')
    expect(totalRow!.textContent).toContain('90')
  })

  it('se referme au clic sur le bouton de fermeture', async () => {
    render(
      <Game
        game={makeGame({ round_history: [makeResult()] })}
        error={null}
        send={vi.fn()}
      />
    )

    await userEvent.click(screen.getByLabelText('Scores de la partie'))
    expect(screen.getByText('Scores de la partie')).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('Fermer'))
    expect(screen.queryByText('Scores de la partie')).not.toBeInTheDocument()
  })
})
