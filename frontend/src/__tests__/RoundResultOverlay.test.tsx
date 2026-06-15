import { render, screen, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { RoundResultOverlay } from '../Game'
import type { RoundResult } from '../types'

const makeResult = (overrides: Partial<RoundResult> = {}): RoundResult => ({
  round_number: 1,
  contract: {
    bid: { position: 'N', value: 80, is_capot: false, trump: 'H' },
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

describe('RoundResultOverlay', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it("n'affiche rien quand last_result est null", () => {
    const { container } = render(
      <RoundResultOverlay lastResult={null} scores={{ NS: 0, EW: 0 }} targetScore={500} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('affiche l\'overlay quand un résultat arrive', () => {
    const result = makeResult({ contract_made: true, score_ns: 80, score_ew: 0 })
    render(
      <RoundResultOverlay lastResult={result} scores={{ NS: 80, EW: 0 }} targetScore={500} />
    )
    expect(screen.getByText('CONTRAT RÉUSSI !')).toBeInTheDocument()
    expect(screen.getByText('+80')).toBeInTheDocument()
    expect(screen.getByText('80 / 500')).toBeInTheDocument()
  })

  it('affiche CHUTE ! quand le contrat est raté', () => {
    const result = makeResult({ contract_made: false, score_ns: 0, score_ew: 80 })
    render(
      <RoundResultOverlay lastResult={result} scores={{ NS: 0, EW: 80 }} targetScore={500} />
    )
    expect(screen.getByText('CHUTE !')).toBeInTheDocument()
    expect(screen.getByText('+80')).toBeInTheDocument()
  })

  it('disparaît automatiquement après 4 secondes', async () => {
    const result = makeResult()
    render(
      <RoundResultOverlay lastResult={result} scores={{ NS: 80, EW: 0 }} targetScore={500} />
    )
    expect(screen.getByText('CONTRAT RÉUSSI !')).toBeInTheDocument()

    await act(async () => { vi.advanceTimersByTime(4000) })

    expect(screen.queryByText('CONTRAT RÉUSSI !')).not.toBeInTheDocument()
  })

  it('se ré-affiche quand un nouveau résultat arrive (round différent)', async () => {
    const result1 = makeResult({ round_number: 1, score_ns: 80, score_ew: 0 })
    const { rerender } = render(
      <RoundResultOverlay lastResult={result1} scores={{ NS: 80, EW: 0 }} targetScore={500} />
    )
    expect(screen.getByText('CONTRAT RÉUSSI !')).toBeInTheDocument()

    await act(async () => { vi.advanceTimersByTime(4000) })
    expect(screen.queryByText('CONTRAT RÉUSSI !')).not.toBeInTheDocument()

    const result2 = makeResult({ round_number: 2, contract_made: false, score_ns: 0, score_ew: 80 })
    rerender(
      <RoundResultOverlay lastResult={result2} scores={{ NS: 80, EW: 80 }} targetScore={500} />
    )
    expect(screen.getByText('CHUTE !')).toBeInTheDocument()
  })

  it('affiche le numéro de manche', () => {
    const result = makeResult({ round_number: 3 })
    render(
      <RoundResultOverlay lastResult={result} scores={{ NS: 0, EW: 0 }} targetScore={500} />
    )
    expect(screen.getByText('Manche 3')).toBeInTheDocument()
  })

  it('affiche la belote quand présente', () => {
    const result = makeResult({ belote_team: 'NS' })
    render(
      <RoundResultOverlay lastResult={result} scores={{ NS: 0, EW: 0 }} targetScore={500} />
    )
    expect(screen.getByText(/Belote NOUS/)).toBeInTheDocument()
  })
})
