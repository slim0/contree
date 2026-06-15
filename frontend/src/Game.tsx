import { useState, useEffect, useRef } from 'react'
import type { GameData, CardData, LegalBidActions, RoundData, RoundResult } from './types'

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
const TEAM_LABEL: Record<string, string> = { NS: 'NOUS', EW: 'EUX' }

function formatMsg(msg: string): string {
  return msg
    .replace(/ à ([HDCS])\b/g, (_, s) => ` à ${SUIT_SYM[s]}`)
    .replace(/\b([RD])([HDCS])\b/g, (_, r, s) => `${r}${SUIT_SYM[s]}`)
    .replace(/\bNS\b/g, 'NOUS')
    .replace(/\bEW\b/g, 'EUX')
}

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
    suitOrder = [trump, ...alternateColors(rest, isRedTrump)]
  } else {
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

function PlayingCard({ card, playable, onClick, style, compact, winner }: {
  card: CardData; playable?: boolean; onClick?: () => void
  style?: React.CSSProperties; compact?: boolean; winner?: boolean
}) {
  const sym = SUIT_SYM[card.suit] ?? card.suit
  const isRed = card.suit === 'H' || card.suit === 'D'
  const cls = ['playing-card', isRed ? 'red' : 'black',
    playable ? 'playable' : '', compact ? 'compact' : '', winner ? 'winner' : '']
    .filter(Boolean).join(' ')
  return (
    <div className={cls} onClick={onClick} style={style}
      title={playable ? 'Cliquer pour jouer' : undefined}>
      <div className="pc-tl"><div className="pc-rank">{card.rank}</div><div className="pc-sym">{sym}</div></div>
      <div className="pc-center">{sym}</div>
      <div className="pc-br"><div className="pc-rank">{card.rank}</div><div className="pc-sym">{sym}</div></div>
    </div>
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

  const n = sortedHand.length
  const cardW = 46
  const spacing = n > 1 ? Math.min(cardW, Math.floor(260 / (n - 1))) : 0
  const maxAngle = Math.min(24, n * 2.8)
  const fanW = n > 0 ? spacing * (n - 1) + cardW : cardW

  let slotClass = 'player-slot'
  if (isBidder) slotClass += ' active-bidder'
  else if (isPlayer) slotClass += ' active-player'
  else if (isDealer) slotClass += ' dealer'

  return (
    <div className={slotClass}>
      <div className="player-pos">
        <span className={teamClass}>{TEAM_LABEL[team] ?? team}</span>
        {isDealer && <span className="badge-dealer" title="Donneur"> 🃏</span>}
        {isBidder && <span className="badge-action" title="À enchérir"> 💬</span>}
        {isPlayer && <span className="badge-action" title="À jouer"> ▶</span>}
      </div>
      <div className="player-name">{name ?? pos}{isMe ? ' (moi)' : ''}</div>
      {isMe ? (
        <div className="hand-fan-wrap">
          <div className="hand-fan" style={{width: fanW}}>
            {sortedHand.map((c, i) => {
              const key = `${c.rank}${c.suit}`
              const playable = isPlayer && legalSet.has(key)
              const k = n > 1 ? i / (n - 1) : 0.5
              const angle = n > 1 ? maxAngle * (2 * k - 1) : 0
              return (
                <div key={i} style={{position:'absolute', left: i * spacing, bottom: 0,
                  transform:`rotate(${angle}deg)`, transformOrigin:'center bottom', zIndex: i}}>
                  <PlayingCard card={c} playable={playable}
                    onClick={playable ? () => onPlay?.(c) : undefined} />
                </div>
              )
            })}
            {sortedHand.length === 0 && r?.phase === 'PLAYING' && <span style={{color:'#666', position:'absolute', bottom: 4}}>—</span>}
          </div>
        </div>
      ) : (
        <div className="card-backs-row">
          {hand.length > 0
            ? Array.from({length: Math.min(hand.length, 6)}).map((_, i) => <div key={i} className="card-back" />)
            : <span style={{color:'#555'}}>—</span>}
          {hand.length > 6 && <span className="card-backs-count">+{hand.length - 6}</span>}
        </div>
      )}
    </div>
  )
}

function TrickArea({ r, lastTrick, me }: { r: RoundData | null; lastTrick?: ReturnType<typeof getLastTrick>; me: string }) {
  const [showLast, setShowLast] = useState(false)
  const phase = r?.phase
  const trick = r?.current_trick

  const cardAt = (pos: string): CardData | null => {
    const tc = trick?.cards.find(c => c.position === pos)
    return tc?.card ?? null
  }

  const viewing = showLast && !!lastTrick

  const isWinner = (pos: string) => {
    if (viewing) return lastTrick!.winner === pos
    if (trick?.winner) return trick.winner === pos
    return false
  }

  const displayCard = (pos: string): CardData | null => {
    if (viewing) return lastTrick!.cardAt(pos)
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
          {viewing
            ? <span style={{color:'#888'}}>Pli {tricksCount}/8</span>
            : phase === 'PLAYING' ? `Pli ${tricksCount + 1}/8` : phase === 'BIDDING' ? 'Enchères' : ''}
        </div>
        {phase === 'PLAYING' && lastTrick && (
          <button
            style={{marginTop:4, fontSize:'0.65em', padding:'2px 5px'}}
            onClick={() => setShowLast(v => !v)}
            title={showLast ? 'Voir pli en cours' : 'Voir dernier pli'}
          >
            {showLast ? '▶ En cours' : '↩ Dernier'}
          </button>
        )}
      </div>
      <div className="trick-pos-right">{renderTrickCard(posRight, displayCard(posRight), isWinner(posRight))}</div>
      <div className="trick-pos-bottom">{renderTrickCard(posBottom, displayCard(posBottom), isWinner(posBottom))}</div>
    </div>
  )
}

function renderTrickCard(pos: string, card: CardData | null, winner: boolean) {
  if (!card) return <span style={{color:'#444',fontSize:'0.7em'}}>{pos}</span>
  return <PlayingCard card={card} compact winner={winner} />
}

function getLastTrick(r: RoundData | null) {
  if (!r || r.tricks.length === 0) return null
  const t = r.tricks[r.tricks.length - 1]
  return {
    winner: t.winner,
    cardAt: (pos: string) => t.cards.find(c => c.position === pos)?.card ?? null,
  }
}

function BidPanel({ r, game, send }: { r: RoundData; game: GameData; send: (m: object) => void }) {
  const actions = r.legal_bid_actions
  if (!actions) return null

  const [bidVal, setBidVal] = useState<number>(actions.min_bid_value ?? 80)
  const [trump, setTrump] = useState('H')

  const validVals = [80, 90, 100, 110, 120, 130, 140, 150, 160].filter(
    v => actions.min_bid_value !== null && v >= (actions.min_bid_value ?? 80)
  )

  return (
    <div className="panel bid-panel-wrap">
      <h3>Enchères <span className="my-turn">— À VOUS</span></h3>
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

// ─── Round Result Overlay ─────────────────────────────────────────────────────

export function RoundResultOverlay({ lastResult, scores, targetScore }: {
  lastResult: RoundResult | null
  scores: Record<string, number>
  targetScore: number
}) {
  const [visible, setVisible] = useState(false)
  const [snap, setSnap] = useState<{ result: RoundResult; scores: Record<string, number> } | null>(null)
  const seenRound = useRef<number | null>(null)

  useEffect(() => {
    if (!lastResult) return
    if (lastResult.round_number === seenRound.current) return
    seenRound.current = lastResult.round_number
    setSnap({ result: lastResult, scores: { ...scores } })
    setVisible(true)
    const timer = setTimeout(() => setVisible(false), 4000)
    return () => clearTimeout(timer)
  }, [lastResult, scores])

  if (!visible || !snap) return null

  const { result: lr, scores: s } = snap
  const made = lr.contract_made
  const { bid, double: dbl, bidding_team } = lr.contract

  return (
    <div className="rr-overlay">
      <div className="rr-box">
        <div className="rr-round">Manche {lr.round_number}</div>
        <div className={`rr-title ${made ? 'rr-made' : 'rr-chute'}`}>
          {made ? 'CONTRAT RÉUSSI !' : 'CHUTE !'}
        </div>
        <div className="rr-contract">
          <span className={bidding_team === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
            {TEAM_LABEL[bidding_team] ?? bidding_team}
          </span>
          {' · '}{bid.is_capot ? 'Capot' : bid.value}{' '}{TRUMP_LABELS[bid.trump] ?? bid.trump}
          {dbl !== 'NONE' && <strong style={{ color: '#f96' }}> {dbl}</strong>}
          {lr.belote_team && (
            <span style={{ color: '#ff4' }}> · Belote {TEAM_LABEL[lr.belote_team] ?? lr.belote_team}</span>
          )}
        </div>
        <div className="rr-scores">
          <div className="rr-score-col">
            <div className="player-team-ns">NOUS</div>
            <div className="rr-pts">{lr.score_ns > 0 ? `+${lr.score_ns}` : lr.score_ns}</div>
            <div className="rr-total">{s['NS'] ?? 0} / {targetScore}</div>
          </div>
          <div className="rr-score-sep">·</div>
          <div className="rr-score-col">
            <div className="player-team-ew">EUX</div>
            <div className="rr-pts">{lr.score_ew > 0 ? `+${lr.score_ew}` : lr.score_ew}</div>
            <div className="rr-total">{s['EW'] ?? 0} / {targetScore}</div>
          </div>
        </div>
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

  const myHand = r?.hands[me] ?? []
  const trump  = r ? getCurrentTrump(r) : null
  const shouldSort = trump !== null && r !== null && r.bid_history.some(e => e.action === 'bid')
  const sortedHand = shouldSort ? sortHand(myHand, trump!) : myHand
  const legalSet = new Set((r?.legal_plays ?? []).map(c => `${c.rank}${c.suit}`))

  const fanN = sortedHand.length
  const fanCardW = 46
  const fanSpacing = fanN > 1 ? Math.min(fanCardW, Math.floor(260 / (fanN - 1))) : 0
  const fanMaxAngle = Math.min(24, fanN * 2.8)
  const fanW = fanN > 0 ? fanSpacing * (fanN - 1) + fanCardW : fanCardW

  const contract = r?.contract
  const ns = game.scores['NS'] ?? 0
  const ew = game.scores['EW'] ?? 0
  const lr = game.last_result

  if (game.phase === 'WAITING') {
    const joined = Object.values(game.players)
    const missing = 4 - joined.length
    return (
      <div className="lp-root">
        <div className="lp-card">
          {game.room_name && (
            <div className="lp-title" style={{ fontSize: 20, marginBottom: 4 }}>{game.room_name}</div>
          )}
          <div style={{ color: '#aaa', fontSize: 13, marginBottom: 20 }}>#{game.room_id}</div>
          <p className="lp-subtitle" style={{ marginBottom: 20 }}>
            {missing === 0 ? 'Démarrage…' : `En attente de ${missing} joueur${missing > 1 ? 's' : ''}…`}
          </p>
          <ul className="lp-room-list">
            {joined.map(name => (
              <li key={name} className="lp-room-item" style={{ cursor: 'default' }}>
                <span className="lp-room-item-name">{name}</span>
                <span style={{ color: '#27ae60', fontSize: 13 }}>✓ connecté</span>
              </li>
            ))}
            {Array.from({ length: missing }).map((_, i) => (
              <li key={`empty-${i}`} className="lp-room-item" style={{ cursor: 'default', opacity: 0.4 }}>
                <span className="lp-room-item-name">—</span>
                <span style={{ fontSize: 13, color: '#aaa' }}>en attente</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="game-wrap">

      <RoundResultOverlay lastResult={lr} scores={game.scores} targetScore={game.target_score} />

      {/* ── Header compact : room + scores + contrat ── */}
      <div className="game-header">
        <div className="header-room">
          <strong>{game.room_name || game.room_id}</strong>
          {game.room_name && <span className="header-code"> #{game.room_id}</span>}
          <span className="header-player"> {me} · {game.players[me] ?? '?'}</span>
          {game.phase === 'FINISHED' && (
            <span style={{color:'#f96'}}> 🏆 {TEAM_LABEL[game.winner ?? ''] ?? game.winner}</span>
          )}
        </div>

        <div className="header-scores">
          <span className="player-team-ns">NOUS</span>
          <strong className="score-num">{ns}</strong>
          <span className="score-sep"> · </span>
          <span className="player-team-ew">EUX</span>
          <strong className="score-num">{ew}</strong>
          <span className="score-limit"> /{game.target_score}</span>
          {lr && (
            <span className={`last-inline ${lr.contract_made ? 'result-made' : 'result-chute'}`}
              title={formatMsg(lr.message)}>
              {' '}{lr.contract_made ? '✓' : '✗'}M{lr.round_number}
            </span>
          )}
        </div>

        <div className="header-contract">
          {contract ? (
            <>
              <span className={contract.bidding_team === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
                {TEAM_LABEL[contract.bidding_team] ?? contract.bidding_team}
              </span>
              {' '}{contract.bid.is_capot ? 'Capot' : contract.bid.value}
              {' '}{TRUMP_LABELS[contract.bid.trump] ?? contract.bid.trump}
              {contract.double !== 'NONE' && <strong style={{color:'#f96'}}> {contract.double}</strong>}
              {r?.belote_team && <span style={{color:'#ff4'}}> · Belote {TEAM_LABEL[r.belote_team] ?? r.belote_team}</span>}
            </>
          ) : r?.phase === 'BIDDING' ? (
            <span style={{color:'#888'}}>Enchères en cours…</span>
          ) : null}
        </div>
      </div>


      {/* ── Table losange ── */}
      <div className="table-wrap">
        <div className="table-grid">
          <div className="slot-top">
            <PlayerSlot pos={top} game={game} r={r} />
          </div>
          <div className="slot-left">
            <PlayerSlot pos={left} game={game} r={r} />
          </div>
          <div className="slot-center">
            <TrickArea r={r} lastTrick={lastTrick ?? undefined} me={me} />
          </div>
          <div className="slot-right">
            <PlayerSlot pos={right} game={game} r={r} />
          </div>
          <div className="slot-bottom">
            <div className="player-slot" style={{
              borderColor: isMyTurnBid ? '#fa6' : isMyTurnPlay ? '#4d9' : '#333'
            }}>
              <div className="player-pos">
                <span className={TEAM[me] === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
                  {TEAM_LABEL[TEAM[me]] ?? TEAM[me]}
                </span>
                {r?.dealer === me && <span className="badge-dealer" title="Donneur"> 🃏</span>}
                {isMyTurnPlay && <span className="badge-action my-turn"> ▶ À JOUER</span>}
                {isMyTurnBid  && <span className="badge-action" style={{color:'#fa6'}}> 💬 À ENCHÉRIR</span>}
              </div>
              <div className="player-name">{game.players[me] ?? me} (moi)</div>
              <div className="hand-fan-wrap">
                <div className="hand-fan" style={{width: fanW}}>
                  {sortedHand.map((c, i) => {
                    const key = `${c.rank}${c.suit}`
                    const playable = isMyTurnPlay && legalSet.has(key)
                    const k = fanN > 1 ? i / (fanN - 1) : 0.5
                    const angle = fanN > 1 ? fanMaxAngle * (2 * k - 1) : 0
                    return (
                      <div key={i} style={{position:'absolute', left: i * fanSpacing, bottom: 0,
                        transform:`rotate(${angle}deg)`, transformOrigin:'center bottom', zIndex: i}}>
                        <PlayingCard card={c} playable={playable}
                          onClick={playable ? () => send({ type: 'play', suit: c.suit, rank: c.rank }) : undefined} />
                      </div>
                    )
                  })}
                  {sortedHand.length === 0 && <span style={{color:'#555', fontSize:'0.85em', position:'absolute', bottom: 4}}>—</span>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Historique enchères (phase BIDDING seulement) ── */}
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

      {/* ── Panel enchères (quand c'est mon tour) ── */}
      {isMyTurnBid && r && <BidPanel r={r} game={game} send={send} />}

      {/* ── Erreur ── */}
      {error && <p className="error">⚠ {error}</p>}

    </div>
  )
}
