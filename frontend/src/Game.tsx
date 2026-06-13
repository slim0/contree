import { useState } from 'react'
import type { GameData, CardData, LegalBidActions, RoundData } from './types'

// ─── Constants ────────────────────────────────────────────────────────────────

const SUIT_SYM: Record<string, string> = { H: '♥', D: '♦', C: '♣', S: '♠' }
const TRUMP_LABELS: Record<string, string> = {
  H: '♥ Cœur', D: '♦ Carreau', C: '♣ Trèfle', S: '♠ Pique',
  NT: 'Sans Atout', AT: 'Tout Atout',
}
const ALL_TRUMPS = ['H', 'D', 'C', 'S', 'NT', 'AT']
const PARTNER: Record<string, string> = { N: 'S', S: 'N', E: 'W', W: 'E' }
// Screen layout: me=bottom → who appears on left/right of screen
const SCREEN_LEFT: Record<string, string>  = { S: 'W', N: 'E', E: 'N', W: 'S' }
const SCREEN_RIGHT: Record<string, string> = { S: 'E', N: 'W', E: 'S', W: 'N' }
const TEAM: Record<string, string> = { N: 'NS', S: 'NS', E: 'EW', W: 'EW' }

// ─── Card sorting ─────────────────────────────────────────────────────────────

const TRUMP_STR: Record<string, number>  = { J:7, '9':6, A:5, '10':4, K:3, Q:2, '8':1, '7':0 }
const NORMAL_STR: Record<string, number> = { A:7, '10':6, K:5, Q:4, J:3, '9':2, '8':1, '7':0 }

function cardStrength(rank: string, suit: string, trump: string): number {
  if (trump === 'AT') return TRUMP_STR[rank] ?? 0
  if (trump === 'NT') return NORMAL_STR[rank] ?? 0
  return suit === trump ? (TRUMP_STR[rank] ?? 0) : (NORMAL_STR[rank] ?? 0)
}

function alternateColors(suits: string[], startBlack: boolean): string[] {
  const red   = suits.filter(s => s === 'H' || s === 'D')
  const black = suits.filter(s => s === 'C' || s === 'S')
  const out: string[] = []
  let ri = 0, bi = 0, wantBlack = startBlack
  while (ri < red.length || bi < black.length) {
    if (wantBlack && bi < black.length)       { out.push(black[bi++]); wantBlack = false }
    else if (!wantBlack && ri < red.length)   { out.push(red[ri++]);   wantBlack = true  }
    else if (ri < red.length)                 { out.push(red[ri++]) }
    else                                       { out.push(black[bi++]) }
  }
  return out
}

function sortHand(cards: CardData[], trump: string): CardData[] {
  const bySuit: Record<string, CardData[]> = {}
  for (const c of cards) {
    bySuit[c.suit] = bySuit[c.suit] ?? []
    bySuit[c.suit].push(c)
  }
  for (const suit in bySuit) {
    bySuit[suit].sort((a, b) => cardStrength(b.rank, suit, trump) - cardStrength(a.rank, suit, trump))
  }

  const present = Object.keys(bySuit)
  let suitOrder: string[]

  if (trump !== 'NT' && trump !== 'AT' && present.includes(trump)) {
    const isRedTrump = trump === 'H' || trump === 'D'
    const rest = present.filter(s => s !== trump)
    suitOrder = [trump, ...alternateColors(rest, isRedTrump)] // after trump alternate starting opposite color
  } else {
    // Alternate H,C,D,S (no trump)
    suitOrder = alternateColors(present, false)
  }

  return suitOrder.flatMap(s => bySuit[s] ?? [])
}

function getCurrentTrump(r: RoundData): string | null {
  if (r.contract) return r.contract.bid.trump
  const lastBid = [...r.bid_history].reverse().find(e => e.action === 'bid')
  return lastBid?.bid?.trump ?? null
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function CardChip({ card, playable, onClick }: {
  card: CardData; playable?: boolean; onClick?: () => void
}) {
  const sym = SUIT_SYM[card.suit] ?? card.suit
  return (
    <span
      className={`card ${card.suit}${playable ? ' playable' : ''}`}
      onClick={onClick}
      title={playable ? 'Cliquer pour jouer' : undefined}
    >
      {card.rank}{sym}
    </span>
  )
}

function PlayerSlot({ pos, game, r, onPlay }: {
  pos: string; game: GameData; r: RoundData | null
  onPlay?: (card: CardData) => void
}) {
  const name = game.players[pos]
  const isMe = pos === game.my_position
  const team = TEAM[pos]
  const teamClass = team === 'NS' ? 'player-team-ns' : 'player-team-ew'
  const isDealer = r?.dealer === pos
  const isBidder = r?.phase === 'BIDDING' && r?.current_bidder === pos
  const isPlayer = r?.phase === 'PLAYING' && r?.current_player === pos
  const hand = r?.hands[pos] ?? []
  const trump = r ? getCurrentTrump(r) : null
  const shouldSort = trump !== null && r !== null && (r.bid_history.some(e => e.action === 'bid'))
  const sortedHand = shouldSort ? sortHand(hand, trump!) : hand

  const legalSet = new Set((r?.legal_plays ?? []).map(c => `${c.rank}${c.suit}`))

  let slotClass = 'player-slot'
  if (isBidder) slotClass += ' active-bidder'
  else if (isPlayer) slotClass += ' active-player'
  else if (isDealer) slotClass += ' dealer'

  return (
    <div className={slotClass}>
      <div className="player-pos">
        <span className={teamClass}>{team}</span>
        {isDealer && <span title="Donneur"> 🃏</span>}
        {isBidder && <span title="À enchérir"> 💬</span>}
        {isPlayer && <span title="À jouer"> ▶</span>}
      </div>
      <div className="player-name">{name ?? pos}{isMe ? ' (moi)' : ''}</div>
      {isMe ? (
        <div className="hand-row">
          {sortedHand.map((c, i) => {
            const key = `${c.rank}${c.suit}`
            const playable = isPlayer && legalSet.has(key)
            return (
              <CardChip key={i} card={c} playable={playable}
                onClick={playable ? () => onPlay?.(c) : undefined}
              />
            )
          })}
          {sortedHand.length === 0 && r?.phase === 'PLAYING' && <span style={{color:'#666'}}>—</span>}
        </div>
      ) : (
        <div className="card-backs">
          {hand.length > 0
            ? '🂠'.repeat(Math.min(hand.length, 8))
            : <span style={{color:'#555'}}>—</span>}
          {hand.length > 0 && <span style={{color:'#666',marginLeft:4}}>×{hand.length}</span>}
        </div>
      )}
    </div>
  )
}

function TrickArea({ r, lastTrick, me }: { r: RoundData | null; lastTrick?: ReturnType<typeof getLastTrick>; me: string }) {
  const phase = r?.phase
  const trick = r?.current_trick

  const cardAt = (pos: string): CardData | null => {
    const tc = trick?.cards.find(c => c.position === pos)
    return tc?.card ?? null
  }

  const isWinner = (pos: string) => {
    if (trick?.winner) return trick.winner === pos
    if (lastTrick?.winner) return lastTrick.winner === pos
    return false
  }

  const displayCard = (pos: string): CardData | null => {
    if (phase === 'PLAYING') return cardAt(pos)
    if (phase === 'BIDDING') return null
    return lastTrick?.cardAt(pos) ?? null
  }

  const tricksCount = r?.tricks?.length ?? 0

  const posTop    = PARTNER[me]
  const posLeft   = SCREEN_LEFT[me]
  const posRight  = SCREEN_RIGHT[me]
  const posBottom = me

  return (
    <div className="trick-grid">
      <div className="trick-pos-top">{renderTrickCard(posTop, displayCard(posTop), isWinner(posTop))}</div>
      <div className="trick-pos-left">{renderTrickCard(posLeft, displayCard(posLeft), isWinner(posLeft))}</div>
      <div className="trick-pos-center">
        <div style={{textAlign:'center', color:'#555', fontSize:'0.7em'}}>
          {phase === 'PLAYING' ? `Pli ${tricksCount + 1}/8` : phase === 'BIDDING' ? 'Enchères' : ''}
        </div>
      </div>
      <div className="trick-pos-right">{renderTrickCard(posRight, displayCard(posRight), isWinner(posRight))}</div>
      <div className="trick-pos-bottom">{renderTrickCard(posBottom, displayCard(posBottom), isWinner(posBottom))}</div>
    </div>
  )
}

function renderTrickCard(pos: string, card: CardData | null, winner: boolean) {
  if (!card) return <span style={{color:'#444',fontSize:'0.7em'}}>{pos}</span>
  const sym = SUIT_SYM[card.suit] ?? card.suit
  return (
    <span className={`trick-card ${card.suit}${winner ? ' winner' : ''}`}>
      {card.rank}{sym}
    </span>
  )
}

function getLastTrick(r: RoundData | null) {
  if (!r || r.tricks.length === 0) return null
  const t = r.tricks[r.tricks.length - 1]
  return {
    winner: t.winner,
    cardAt: (pos: string) => t.cards.find(c => c.position === pos)?.card ?? null,
  }
}

function ScoreSummary({ game }: { game: GameData }) {
  const ns = game.scores['NS'] ?? 0
  const ew = game.scores['EW'] ?? 0
  const target = game.target_score
  const lr = game.last_result

  return (
    <div className="panel">
      <h3>Scores — cible {target} pts</h3>
      <div className="score-bar">
        <div className="score-team ns">
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
            <span className="player-team-ns" style={{fontWeight:'bold'}}>NS</span>
            <span className="score-value">{ns}</span>
          </div>
          <div className="score-progress">
            <div className="score-fill-ns" style={{width: `${Math.min(100, ns / target * 100)}%`}} />
          </div>
          <div className="score-target">{target - ns > 0 ? `${target - ns} pts restants` : '🏆 Objectif atteint'}</div>
        </div>
        <div className="score-team ew">
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
            <span className="player-team-ew" style={{fontWeight:'bold'}}>EW</span>
            <span className="score-value">{ew}</span>
          </div>
          <div className="score-progress">
            <div className="score-fill-ew" style={{width: `${Math.min(100, ew / target * 100)}%`}} />
          </div>
          <div className="score-target">{target - ew > 0 ? `${target - ew} pts restants` : '🏆 Objectif atteint'}</div>
        </div>
        {lr && (
          <div className="last-result">
            <div style={{color:'#666', fontSize:'0.85em', marginBottom:3}}>Dernier résultat (manche {lr.round_number})</div>
            <div className={lr.contract_made ? 'result-made' : 'result-chute'}>
              {lr.contract_made ? '✓ Contrat réussi' : '✗ Chute'}
            </div>
            <div style={{marginTop:3}}>{lr.message}</div>
          </div>
        )}
      </div>
    </div>
  )
}

function BidPanel({ r, game, send }: { r: RoundData; game: GameData; send: (m: object) => void }) {
  const actions = r.legal_bid_actions
  if (!actions) return null

  const [bidVal, setBidVal] = useState<number>(actions.min_bid_value ?? 80)
  const [trump, setTrump] = useState('H')

  const validVals = [80, 90, 100, 110, 120, 130, 140, 150, 160].filter(
    v => actions.min_bid_value !== null && v >= (actions.min_bid_value ?? 80)
  )

  const myTeam = TEAM[game.my_position]
  const contract = r.contract

  return (
    <div className="panel">
      <h3>Vos enchères <span className="my-turn">— À VOUS</span></h3>
      <div className="bid-panel">
        {actions.can_pass && (
          <button className="action" onClick={() => send({ type: 'pass' })}>Passer</button>
        )}
        {actions.can_contre && (
          <button className="action" onClick={() => send({ type: 'contre' })}>Contre !</button>
        )}
        {actions.can_surcontre && (
          <button className="action" onClick={() => send({ type: 'surcontre' })}>Surcontre !</button>
        )}
        {(actions.min_bid_value !== null || actions.can_bid_capot) && (
          <>
            <select
              value={bidVal}
              onChange={e => setBidVal(+e.target.value)}
              disabled={actions.min_bid_value === null}
            >
              {validVals.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            <select value={trump} onChange={e => setTrump(e.target.value)}>
              {ALL_TRUMPS.map(t => <option key={t} value={t}>{TRUMP_LABELS[t]}</option>)}
            </select>
            {actions.min_bid_value !== null && (
              <button className="action"
                onClick={() => send({ type: 'bid', value: bidVal, trump, is_capot: false })}>
                Annoncer {bidVal}
              </button>
            )}
            {actions.can_bid_capot && (
              <button className="action"
                onClick={() => send({ type: 'bid', value: 0, trump, is_capot: true })}>
                Capot
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main Game component ───────────────────────────────────────────────────────

export default function Game({ game, error, send }: {
  game: GameData | null
  error: string | null
  send: (msg: object) => void
}) {
  if (!game) return <p style={{color:'#4af'}}>Connexion en cours…</p>

  const r = game.round
  const me = game.my_position
  const top    = PARTNER[me]
  const left   = SCREEN_LEFT[me]
  const right  = SCREEN_RIGHT[me]
  const lastTrick = getLastTrick(r)

  const isMyTurnBid  = r?.phase === 'BIDDING'  && r?.current_bidder  === me
  const isMyTurnPlay = r?.phase === 'PLAYING'   && r?.current_player  === me

  // Wire up card clicks for my hand — send play action
  const myHand = r?.hands[me] ?? []
  const trump  = r ? getCurrentTrump(r) : null
  const shouldSort = trump !== null && r !== null && r.bid_history.some(e => e.action === 'bid')
  const sortedHand = shouldSort ? sortHand(myHand, trump!) : myHand
  const legalSet = new Set((r?.legal_plays ?? []).map(c => `${c.rank}${c.suit}`))

  const contract = r?.contract

  return (
    <div>
      {/* Top bar */}
      <div className="top-bar">
        <div>
          <strong>Salon {game.room_id}</strong>
          <span className="room-info"> · {me} ({game.players[me] ?? '?'})</span>
          {game.phase === 'FINISHED' && (
            <span style={{color:'#f96', marginLeft:10}}>🏆 Vainqueur : {game.winner}</span>
          )}
        </div>
        {contract && (
          <div style={{fontSize:'0.85em'}}>
            Contrat : <span className={contract.bidding_team === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
              {contract.bidding_team}
            </span>
            {' '}{contract.bid.is_capot ? 'Capot' : contract.bid.value}
            {' '}à {TRUMP_LABELS[contract.bid.trump] ?? contract.bid.trump}
            {contract.double !== 'NONE' && <strong style={{color:'#f96'}}> {contract.double}</strong>}
            {r?.belote_team && <span style={{color:'#ff4'}}> | Belote {r.belote_team}</span>}
          </div>
        )}
        {r?.phase === 'BIDDING' && !contract && (
          <span style={{fontSize:'0.8em', color:'#888'}}>Enchères en cours…</span>
        )}
      </div>

      {/* Scores */}
      <ScoreSummary game={game} />

      {/* Table losange */}
      <div className="table-wrap">
        <div className="table-grid">
          {/* Top = partner */}
          <div className="slot-top">
            <PlayerSlot pos={top} game={game} r={r} />
          </div>

          {/* Left opponent */}
          <div className="slot-left">
            <PlayerSlot pos={left} game={game} r={r} />
          </div>

          {/* Center = current trick */}
          <div className="slot-center">
            <TrickArea r={r} lastTrick={lastTrick ?? undefined} me={me} />
          </div>

          {/* Right opponent */}
          <div className="slot-right">
            <PlayerSlot pos={right} game={game} r={r} />
          </div>

          {/* Bottom = me */}
          <div className="slot-bottom">
            <div className="player-slot" style={{
              borderColor: isMyTurnBid ? '#fa6' : isMyTurnPlay ? '#4d9' : '#333'
            }}>
              <div className="player-pos">
                <span className={TEAM[me] === 'NS' ? 'player-team-ns' : 'player-team-ew'}>{TEAM[me]}</span>
                {r?.dealer === me && <span> 🃏</span>}
                {isMyTurnPlay && <span className="my-turn"> ▶ À JOUER</span>}
                {isMyTurnBid  && <span style={{color:'#fa6'}}> 💬 À ENCHÉRIR</span>}
              </div>
              <div className="player-name">{game.players[me] ?? me} (moi)</div>
              <div className="hand-row">
                {sortedHand.map((c, i) => {
                  const key = `${c.rank}${c.suit}`
                  const playable = isMyTurnPlay && legalSet.has(key)
                  return (
                    <CardChip key={i} card={c} playable={playable}
                      onClick={playable ? () => send({ type: 'play', suit: c.suit, rank: c.rank }) : undefined}
                    />
                  )
                })}
                {sortedHand.length === 0 && <span style={{color:'#555', fontSize:'0.85em'}}>—</span>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bid history (compact) */}
      {r?.phase === 'BIDDING' && r.bid_history.length > 0 && (
        <div className="panel">
          <h3>Enchères</h3>
          <div style={{display:'flex', flexWrap:'wrap', gap:8}}>
            {r.bid_history.map((e, i) => (
              <span key={i} style={{fontSize:'0.85em', color: e.action === 'pass' ? '#666' : '#ccc'}}>
                <span style={{color:'#888'}}>{e.position}:</span>{' '}
                {e.action === 'bid' && e.bid
                  ? <>{e.bid.is_capot ? 'Capot' : e.bid.value} {TRUMP_LABELS[e.bid.trump] ?? e.bid.trump}</>
                  : e.action}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Bidding actions */}
      {isMyTurnBid && r && <BidPanel r={r} game={game} send={send} />}

      {/* Error */}
      {error && <p className="error">⚠ {error}</p>}

      {/* Log */}
      <div className="panel">
        <h3>Journal</h3>
        <div className="log">
          {[...game.messages].reverse().map((m, i) => <p key={i}>{m}</p>)}
        </div>
      </div>
    </div>
  )
}
