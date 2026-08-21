import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData, RoundData, LegalBidActions } from '../types'

const PLAYERS = { N: 'alice', E: 'bob', S: 'charlie', W: 'diana' }

const makeRound = (legalBidActions: LegalBidActions | undefined, overrides: Partial<RoundData> = {}): RoundData => ({
  number: 1,
  dealer: 'W',
  hands: { N: [], E: [], S: [], W: [] },
  phase: 'BIDDING',
  current_bidder: 'N',
  pass_count: 0,
  bid_history: [],
  contract: null,
  current_player: null,
  tricks: [],
  current_trick: { cards: [], winner: null },
  belote_team: null,
  belote_king_played: false,
  belote_queen_played: false,
  running_points: { NS: 0, EW: 0 },
  legal_bid_actions: legalBidActions,
  ...overrides,
})

const makeGame = (round: RoundData, overrides: Partial<GameData> = {}): GameData => ({
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
  ...overrides,
})

describe('BidCenter — enchères par boutons', () => {
  it("n'affiche aucun menu déroulant pendant les enchères", () => {
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    const { container } = render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    expect(container.querySelectorAll('select').length).toBe(0)
  })

  it('la valeur minimale légale est présélectionnée par défaut dans le sélecteur', () => {
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    expect(screen.getByText('80')).toBeInTheDocument()
  })

  it('les flèches du sélecteur changent la valeur affichée', async () => {
    const user = userEvent.setup()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)

    await user.click(screen.getByLabelText('Valeur suivante'))
    expect(screen.getByText('90')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Valeur précédente'))
    expect(screen.getByText('80')).toBeInTheDocument()
  })

  it('un clic sur une couleur la sélectionne sans envoyer l’enchère, seul "Prendre" l’envoie', async () => {
    const user = userEvent.setup()
    const send = vi.fn()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={send} />)

    await user.click(screen.getByLabelText('Valeur suivante')) // 90
    await user.click(screen.getByText('♥'))
    expect(screen.getByText('♥')).toHaveClass('selected')
    expect(send).not.toHaveBeenCalled()

    await user.click(screen.getByText('Prendre'))
    expect(send).toHaveBeenCalledWith({ type: 'bid', value: 90, trump: 'H', is_capot: false })
  })

  it('"Prendre" est toujours affiché mais désactivé tant qu’aucune couleur n’est sélectionnée', () => {
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    expect(screen.getByText('Prendre')).toBeInTheDocument()
    expect(screen.getByText('Prendre')).toBeDisabled()
  })

  it('Passer envoie {type: "pass"}', async () => {
    const user = userEvent.setup()
    const send = vi.fn()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={send} />)

    await user.click(screen.getByText('Passer'))
    expect(send).toHaveBeenCalledWith({ type: 'pass' })
  })

  it('Coinche et Surcoinche n’apparaissent que si les actions légales le permettent', () => {
    const roundNone = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    const { unmount } = render(<Game game={makeGame(roundNone)} error={null} send={vi.fn()} />)
    expect(screen.queryByText('Coinche !')).toBeNull()
    expect(screen.queryByText('Surcoinche !')).toBeNull()
    unmount()

    const roundBoth = makeRound({ can_pass: true, can_contre: true, can_surcontre: true, min_bid_value: null, can_bid_capot: false, can_bid_generale: false })
    render(<Game game={makeGame(roundBoth)} error={null} send={vi.fn()} />)
    expect(screen.getByText('Coinche !')).toBeInTheDocument()
    expect(screen.getByText('Surcoinche !')).toBeInTheDocument()
    // Sans valeur de relance possible, Passer doit tout de même rester accessible.
    expect(screen.getByText('Passer')).toBeInTheDocument()
  })

  it('une enchère Capot sélectionnée puis "Prendre" envoie l’enchère capot', async () => {
    const user = userEvent.setup()
    const send = vi.fn()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: null, can_bid_capot: true, can_bid_generale: false })
    render(<Game game={makeGame(round)} error={null} send={send} />)

    expect(screen.getByText('Capot')).toBeInTheDocument()
    await user.click(screen.getByText('♠'))
    await user.click(screen.getByText('Prendre'))
    expect(send).toHaveBeenCalledWith({ type: 'bid', value: 0, trump: 'S', is_capot: true })
  })

  it('une enchère Générale sélectionnée puis "Prendre" envoie l’enchère générale', async () => {
    const user = userEvent.setup()
    const send = vi.fn()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: null, can_bid_capot: false, can_bid_generale: true })
    render(<Game game={makeGame(round)} error={null} send={send} />)

    expect(screen.getByText('Générale')).toBeInTheDocument()
    await user.click(screen.getByText('♠'))
    await user.click(screen.getByText('Prendre'))
    expect(send).toHaveBeenCalledWith({ type: 'bid', value: 0, trump: 'S', is_capot: false, is_generale: true })
  })

  it('changer de bidder réinitialise la couleur sélectionnée (désactive à nouveau "Prendre")', async () => {
    const user = userEvent.setup()
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    const { rerender } = render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)

    await user.click(screen.getByText('♥'))
    expect(screen.getByText('Prendre')).not.toBeDisabled()

    const nextRound = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false }, { current_bidder: 'E' })
    rerender(<Game game={makeGame(nextRound)} error={null} send={vi.fn()} />)
    expect(screen.getByText('Prendre')).toBeDisabled()
  })

  it('affiche un bouton "Coinche à la volée !" à un adversaire hors tour et envoie {type: "contre"} au clic', async () => {
    const user = userEvent.setup()
    const send = vi.fn()
    // Ce n'est pas le tour de N (current_bidder = S) : le back n'envoie donc pas
    // legal_bid_actions, uniquement can_contre_volee.
    const round = makeRound(undefined, { current_bidder: 'S', can_contre_volee: true })
    render(<Game game={makeGame(round)} error={null} send={send} />)

    const btn = screen.getByText('Coinche !')
    expect(btn).toBeInTheDocument()
    await user.click(btn)
    expect(send).toHaveBeenCalledWith({ type: 'contre' })
  })

  it('n’affiche pas de bouton "Coinche à la volée !" quand can_contre_volee est faux', () => {
    const round = makeRound(undefined, { current_bidder: 'S', can_contre_volee: false })
    render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    expect(screen.queryByText('Coinche !')).toBeNull()
  })

  it("affiche l'enchère à battre reconstituée depuis le bid_history", () => {
    const round = makeRound(
      { can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 100, can_bid_capot: false, can_bid_generale: false },
      { bid_history: [{ position: 'W', action: 'bid', bid: { position: 'W', value: 90, is_capot: false, is_generale: false, trump: 'H' } }] }
    )
    const { container } = render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    const toBeat = container.querySelector('.bid-to-beat')
    expect(toBeat).not.toBeNull()
    expect(toBeat?.textContent).toContain('À battre')
    expect(toBeat?.textContent).toContain('90')
    expect(toBeat?.textContent).toContain('Cœur')
  })

  it("n'affiche pas d'enchère à battre tant qu'aucune enchère n'a été posée", () => {
    const round = makeRound({ can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 80, can_bid_capot: false, can_bid_generale: false })
    const { container } = render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)
    expect(container.querySelector('.bid-to-beat')).toBeNull()
  })

  it("affiche la dernière enchère de chaque joueur en badge, pas dans une liste centrale", () => {
    const round = makeRound(
      { can_pass: true, can_contre: false, can_surcontre: false, min_bid_value: 90, can_bid_capot: false, can_bid_generale: false },
      { bid_history: [{ position: 'W', action: 'bid', bid: { position: 'W', value: 80, is_capot: false, is_generale: false, trump: 'H' } }] }
    )
    const { container } = render(<Game game={makeGame(round)} error={null} send={vi.fn()} />)

    expect(container.querySelector('.bid-center-history')).toBeNull()
    const badge = container.querySelector('.slot-left .bid-entry-row, .slot-right .bid-entry-row, .slot-top .bid-entry-row')
    expect(badge?.textContent).toContain('80')
  })
})
