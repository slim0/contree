import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import Game from '../Game'
import type { GameData } from '../types'

const makeWaitingGame = (overrides: Partial<GameData> = {}): GameData => ({
  room_id: 'TEST',
  room_name: 'Salon Test',
  players: {},
  scores: { NS: 0, EW: 0 },
  target_score: 1000,
  round: null,
  phase: 'WAITING',
  winner: null,
  last_result: null,
  messages: [],
  my_position: 'N',
  team_choices: {},
  ready_to_start: false,
  ...overrides,
})

describe('WaitingRoom', () => {
  it('affiche le nom du salon', () => {
    render(<Game game={makeWaitingGame()} error={null} send={vi.fn()} />)
    expect(screen.getByText('Salon Test')).toBeInTheDocument()
  })

  it('affiche le message d\'attente si des joueurs manquent', () => {
    render(<Game game={makeWaitingGame({ players: { N: 'Alice' } })} error={null} send={vi.fn()} />)
    expect(screen.getByText(/En attente de 3 joueurs/)).toBeInTheDocument()
  })

  it('affiche le message de sélection d\'équipe quand 4 joueurs sont là', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob', S: 'Carol', W: 'Dave' },
    })
    render(<Game game={game} error={null} send={vi.fn()} />)
    expect(screen.getByText(/Choisissez vos équipes/)).toBeInTheDocument()
  })

  it('affiche un bouton toggle pour mon slot', () => {
    const game = makeWaitingGame({ players: { N: 'Alice' }, my_position: 'N' })
    const { container } = render(<Game game={game} error={null} send={vi.fn()} />)
    expect(container.querySelector('.wr-toggle')).not.toBeNull()
  })

  it('le toggle est gris si aucune équipe choisie', () => {
    const game = makeWaitingGame({ players: { N: 'Alice' }, my_position: 'N' })
    const { container } = render(<Game game={game} error={null} send={vi.fn()} />)
    const toggle = container.querySelector('.wr-toggle')
    expect(toggle?.classList.contains('red')).toBe(false)
    expect(toggle?.classList.contains('blue')).toBe(false)
  })

  it('le toggle est rouge quand NS est choisi', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice' },
      my_position: 'N',
      team_choices: { N: 'NS' },
    })
    const { container } = render(<Game game={game} error={null} send={vi.fn()} />)
    expect(container.querySelector('.wr-toggle.red')).not.toBeNull()
  })

  it('le toggle est bleu quand EW est choisi', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice' },
      my_position: 'N',
      team_choices: { N: 'EW' },
    })
    const { container } = render(<Game game={game} error={null} send={vi.fn()} />)
    expect(container.querySelector('.wr-toggle.blue')).not.toBeNull()
  })

  it('envoie choose_team NS (premier clic — bascule de rien vers NS)', () => {
    const send = vi.fn()
    const game = makeWaitingGame({ players: { N: 'Alice' }, my_position: 'N' })
    const { container } = render(<Game game={game} error={null} send={send} />)
    fireEvent.click(container.querySelector('.wr-toggle')!)
    expect(send).toHaveBeenCalledWith({ type: 'choose_team', team: 'NS' })
  })

  it('envoie choose_team EW quand le toggle est déjà rouge (bascule NS → EW)', () => {
    const send = vi.fn()
    const game = makeWaitingGame({
      players: { N: 'Alice' },
      my_position: 'N',
      team_choices: { N: 'NS' },
    })
    const { container } = render(<Game game={game} error={null} send={send} />)
    fireEvent.click(container.querySelector('.wr-toggle')!)
    expect(send).toHaveBeenCalledWith({ type: 'choose_team', team: 'EW' })
  })

  it('n\'envoie rien quand on clique sur le toggle d\'un autre joueur', () => {
    const send = vi.fn()
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob' },
      my_position: 'N',
    })
    const { container } = render(<Game game={game} error={null} send={send} />)
    const toggles = container.querySelectorAll('.wr-toggle')
    fireEvent.click(toggles[1]) // Bob's toggle (E)
    expect(send).not.toHaveBeenCalled()
  })

  it('le bouton GO est désactivé si pas 4 joueurs', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob' },
      team_choices: { N: 'NS', E: 'EW' },
    })
    render(<Game game={game} error={null} send={vi.fn()} />)
    expect(screen.getByText('GO !')).toBeDisabled()
  })

  it('le bouton GO est désactivé si déséquilibre 3+1', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob', S: 'Carol', W: 'Dave' },
      team_choices: { N: 'NS', E: 'NS', S: 'NS', W: 'EW' },
    })
    render(<Game game={game} error={null} send={vi.fn()} />)
    expect(screen.getByText('GO !')).toBeDisabled()
  })

  it('le bouton GO est actif avec exactement 2 rouge et 2 bleu', () => {
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob', S: 'Carol', W: 'Dave' },
      team_choices: { N: 'NS', E: 'EW', S: 'NS', W: 'EW' },
    })
    render(<Game game={game} error={null} send={vi.fn()} />)
    expect(screen.getByText('GO !')).not.toBeDisabled()
  })

  it('envoie start_game quand GO est cliqué avec 2+2', () => {
    const send = vi.fn()
    const game = makeWaitingGame({
      players: { N: 'Alice', E: 'Bob', S: 'Carol', W: 'Dave' },
      team_choices: { N: 'NS', E: 'EW', S: 'NS', W: 'EW' },
    })
    render(<Game game={game} error={null} send={send} />)
    fireEvent.click(screen.getByText('GO !'))
    expect(send).toHaveBeenCalledWith({ type: 'start_game' })
  })

  it('affiche les tirets pour les emplacements vides', () => {
    const game = makeWaitingGame({ players: { N: 'Alice' } })
    render(<Game game={game} error={null} send={vi.fn()} />)
    expect(screen.getAllByText('en attente').length).toBe(3)
  })
})
