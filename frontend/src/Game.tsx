import { useState } from 'react'
import type { GameData, CardData, LegalBidActions } from './types'

const SUIT_SYMBOLS: Record<string, string> = { H: '♥', D: '♦', C: '♣', S: '♠' }
const TRUMP_LABELS: Record<string, string> = {
  H: '♥ Cœur', D: '♦ Carreau', C: '♣ Trèfle', S: '♠ Pique',
  NT: 'Sans Atout', AT: 'Tout Atout',
}
const ALL_TRUMPS = ['H', 'D', 'C', 'S', 'NT', 'AT']

function CardBtn({ card, onClick, highlight }: {
  card: CardData; onClick?: () => void; highlight?: boolean
}) {
  const suit = card.suit
  const sym = SUIT_SYMBOLS[suit] ?? suit
  const label = `${card.rank}${sym}`
  return (
    <button className={`card ${suit} ${highlight ? 'legal' : ''}`} onClick={onClick}>
      {label}
    </button>
  )
}

function BiddingPanel({ actions, onBid }: {
  actions: LegalBidActions
  onBid: (msg: object) => void
}) {
  const [bidVal, setBidVal] = useState(actions.min_bid_value ?? 80)
  const [trump, setTrump] = useState('H')

  const validBidVals = [80, 90, 100, 110, 120, 130, 140, 150, 160].filter(
    v => actions.min_bid_value !== null && v >= actions.min_bid_value
  )

  return (
    <div className="section">
      <h3>Vos enchères</h3>
      {actions.can_pass && (
        <button className="action" onClick={() => onBid({ type: 'pass' })}>Passer</button>
      )}
      {actions.can_contre && (
        <button className="action" onClick={() => onBid({ type: 'contre' })}>Contre !</button>
      )}
      {actions.can_surcontre && (
        <button className="action" onClick={() => onBid({ type: 'surcontre' })}>Surcontre !</button>
      )}
      {(actions.min_bid_value !== null || actions.can_bid_capot) && (
        <div style={{ marginTop: 8 }}>
          <select value={bidVal} onChange={e => setBidVal(+e.target.value)}>
            {validBidVals.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
          <select value={trump} onChange={e => setTrump(e.target.value)} style={{ marginLeft: 6 }}>
            {ALL_TRUMPS.map(t => <option key={t} value={t}>{TRUMP_LABELS[t]}</option>)}
          </select>
          <button className="action" style={{ marginLeft: 6 }}
            onClick={() => onBid({ type: 'bid', value: bidVal, trump, is_capot: false })}>
            Annoncer
          </button>
          {actions.can_bid_capot && (
            <button className="action" style={{ marginLeft: 4 }}
              onClick={() => onBid({ type: 'bid', value: 0, trump, is_capot: true })}>
              Capot à {TRUMP_LABELS[trump]}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function Game({ game, error, send }: {
  game: GameData | null
  error: string | null
  send: (msg: object) => void
}) {
  if (!game) return <p className="info">Connexion en cours…</p>

  const r = game.round
  const me = game.my_position
  const myHand = r?.hands[me] ?? []
  const legalPlays = r?.legal_plays ?? []
  const legalBids = r?.legal_bid_actions

  const isMyTurnBid = r?.phase === 'BIDDING' && r?.current_bidder === me
  const isMyTurnPlay = r?.phase === 'PLAYING' && r?.current_player === me

  const legalSet = new Set(legalPlays.map(c => `${c.rank}${c.suit}`))
  const isLegal = (c: CardData) => legalSet.has(`${c.rank}${c.suit}`)

  return (
    <div>
      {/* Header */}
      <div className="section">
        <strong>Salon {game.room_id}</strong> — Je suis <strong>{me}</strong> ({game.players[me] ?? '?'})
        {game.phase === 'FINISHED' && (
          <span style={{ color: '#f84', marginLeft: 12 }}>🏆 Vainqueur : {game.winner}</span>
        )}
      </div>

      {/* Scores */}
      <div className="section">
        <h3>Scores (cible : {game.target_score})</h3>
        <div className="scores">
          <div className="score-item">NS : {game.scores['NS']}</div>
          <div className="score-item">EW : {game.scores['EW']}</div>
        </div>
      </div>

      {/* Players */}
      <div className="section">
        <h3>Joueurs</h3>
        {Object.entries(game.players).map(([pos, name]) => (
          <span key={pos} style={{ marginRight: 16, color: pos === me ? '#4a9' : '#aaa' }}>
            {pos}: {name}{r?.dealer === pos ? ' 🃏' : ''}{r?.current_player === pos ? ' ◀' : ''}{r?.current_bidder === pos ? ' 💬' : ''}
          </span>
        ))}
      </div>

      {/* Contract */}
      {r?.contract && (
        <div className="section">
          <h3>Contrat</h3>
          <span>
            {r.contract.bidding_team} joue {r.contract.bid.is_capot ? 'Capot' : r.contract.bid.value}
            {' '}à {TRUMP_LABELS[r.contract.bid.trump] ?? r.contract.bid.trump}
            {r.contract.double !== 'NONE' && <strong style={{ color: '#f84' }}> {r.contract.double}</strong>}
            {r.belote_team && <span style={{ color: '#ff4' }}> | Belote : {r.belote_team}</span>}
          </span>
        </div>
      )}

      {/* Current trick */}
      {r?.phase === 'PLAYING' && (
        <div className="section">
          <h3>Pli en cours ({r.tricks.length}/8 plis terminés)</h3>
          {r.current_trick.cards.length === 0
            ? <span style={{ color: '#666' }}>Vide</span>
            : r.current_trick.cards.map(tc => (
              <span key={tc.position} style={{ marginRight: 10 }}>
                {tc.position}: <CardBtn card={tc.card} />
              </span>
            ))
          }
        </div>
      )}

      {/* Bid history */}
      {r?.phase === 'BIDDING' && r.bid_history.length > 0 && (
        <div className="section">
          <h3>Enchères</h3>
          {r.bid_history.map((e, i) => (
            <span key={i} style={{ marginRight: 12, color: '#aaa' }}>
              {e.position}: {e.action === 'bid' && e.bid
                ? `${e.bid.is_capot ? 'Capot' : e.bid.value} ${TRUMP_LABELS[e.bid.trump] ?? e.bid.trump}`
                : e.action}
            </span>
          ))}
        </div>
      )}

      {/* My hand */}
      <div className="section">
        <h3>Ma main {isMyTurnPlay ? <span className="my-turn">— À VOUS DE JOUER</span> : ''}</h3>
        {myHand.map((c, i) => (
          <CardBtn key={i} card={c}
            highlight={isMyTurnPlay && isLegal(c)}
            onClick={isMyTurnPlay && isLegal(c) ? () => send({ type: 'play', suit: c.suit, rank: c.rank }) : undefined}
          />
        ))}
        {isMyTurnPlay && legalPlays.length > 0 && (
          <div style={{ marginTop: 6, fontSize: '0.8em', color: '#888' }}>
            Cartes jouables en vert
          </div>
        )}
      </div>

      {/* Bidding actions */}
      {isMyTurnBid && legalBids && (
        <BiddingPanel actions={legalBids} onBid={send} />
      )}

      {/* Last round result */}
      {game.last_result && (
        <div className="section">
          <h3>Dernier résultat</h3>
          <p>{game.last_result.message}</p>
        </div>
      )}

      {/* Error */}
      {error && <p className="error">⚠ {error}</p>}

      {/* Log */}
      <div className="section">
        <h3>Journal</h3>
        <div className="log">
          {[...game.messages].reverse().map((m, i) => <p key={i}>{m}</p>)}
        </div>
      </div>
    </div>
  )
}
