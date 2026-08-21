import { useState, useEffect, useRef, useCallback } from 'react'
import type { GameData, CardData, LegalBidActions, RoundData, RoundResult } from './types'
import { VoiceManager, type VoicePeer } from './voice/VoiceManager'

// ─── Constants ────────────────────────────────────────────────────────────────

const SUIT_SYM: Record<string, string> = { H: '♥', D: '♦', C: '♣', S: '♠' }
const TRUMP_LABELS: Record<string, string> = {
  H: '♥ Cœur', D: '♦ Carreau', C: '♣ Trèfle', S: '♠ Pique',
  NT: 'Sans Atout', AT: 'Tout Atout',
}
const PARTNER: Record<string, string> = { N: 'S', S: 'N', E: 'W', W: 'E' }
// Screen layout: me=bottom → who appears on left/right of screen
// Each player faces the table center, so my right-hand neighbor sits in the
// seat *before* mine in the clockwise N→E→S→W→N order, and my left-hand
// neighbor sits in the seat *after* mine — same convention as around a real table.
const SCREEN_LEFT: Record<string, string>  = { N: 'E', E: 'S', S: 'W', W: 'N' }
const SCREEN_RIGHT: Record<string, string> = { N: 'W', E: 'N', S: 'E', W: 'S' }
const TEAM: Record<string, string> = { N: 'NS', S: 'NS', E: 'EW', W: 'EW' }
const TEAM_LABEL: Record<string, string> = { NS: 'TEAM RED', EW: 'TEAM BLUE' }

function formatMsg(msg: string): string {
  return msg
    .replace(/ à ([HDCS])\b/g, (_, s) => ` à ${SUIT_SYM[s]}`)
    .replace(/\b([RD])([HDCS])\b/g, (_, r, s) => `${r}${SUIT_SYM[s]}`)
    .replace(/\bNS\b/g, TEAM_LABEL['NS'])
    .replace(/\bEW\b/g, TEAM_LABEL['EW'])
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

function fanLayout(n: number, cardW: number, fanBudget: number) {
  const spacing = n > 1 ? Math.min(cardW, Math.floor(fanBudget / (n - 1))) : 0
  const maxAngle = Math.min(24, n * 2.8)
  const fanW = n > 0 ? spacing * (n - 1) + cardW : cardW
  return { spacing, maxAngle, fanW }
}

// ─── Responsive card sizing ───────────────────────────────────────────────────
// Mirrors the breakpoints of the `.playing-card` media queries in index.html so the
// JS fan-spacing math always matches the actually-rendered card size.
// Any new CSS breakpoint added under the tablet media queries in index.html must
// get a matching entry here with the identical px thresholds — check both together.

interface CardSizes { mine: number; opponent: number; fanBudget: number; oppFanBudget: number }

const CARD_SIZES: Record<
  'default' | 'landscapeMobile' | 'portraitMobile' | 'landscapeTablet' | 'portraitTablet',
  CardSizes
> = {
  default:         { mine: 78, opponent: 40, fanBudget: 360, oppFanBudget: 130 },
  landscapeTablet: { mine: 74, opponent: 36, fanBudget: 380, oppFanBudget: 120 },
  portraitTablet:  { mine: 76, opponent: 36, fanBudget: 400, oppFanBudget: 130 },
  landscapeMobile: { mine: 64, opponent: 28, fanBudget: 320, oppFanBudget: 90 },
  portraitMobile:  { mine: 72, opponent: 36, fanBudget: 310, oppFanBudget: 110 },
}

function getCardBreakpoint(): keyof typeof CARD_SIZES {
  if (typeof window === 'undefined') return 'default'
  const isLandscape = window.matchMedia('(orientation: landscape)').matches
  if (isLandscape) {
    if (window.innerHeight <= 520) return 'landscapeMobile'
    if (window.innerHeight <= 900) return 'landscapeTablet'
    return 'default'
  }
  if (window.innerWidth <= 640) return 'portraitMobile'
  if (window.innerWidth <= 1080) return 'portraitTablet'
  return 'default'
}

function useCardSizes(): CardSizes {
  const [bp, setBp] = useState(getCardBreakpoint)
  useEffect(() => {
    const onChange = () => setBp(getCardBreakpoint())
    window.addEventListener('resize', onChange)
    window.addEventListener('orientationchange', onChange)
    return () => {
      window.removeEventListener('resize', onChange)
      window.removeEventListener('orientationchange', onChange)
    }
  }, [])
  return CARD_SIZES[bp]
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function CardBack({ compact }: { compact?: boolean }) {
  return (
    <div className={`card-back${compact ? ' compact' : ''}`}>
      <div className="cb-pattern" />
    </div>
  )
}

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

function PlayerSlot({ pos, game, r, cardSizes }: {
  pos: string; game: GameData; r: RoundData | null; cardSizes: CardSizes
}) {
  const name = game.players[pos]
  const team = TEAM[pos]
  const teamClass = team === 'NS' ? 'player-team-ns' : 'player-team-ew'
  const isDealer = r?.dealer === pos
  const isBidder = r?.phase === 'BIDDING' && r?.current_bidder === pos
  const isPlayer = r?.phase === 'PLAYING' && r?.current_player === pos
  const n = (r?.hands[pos] ?? []).length

  const { spacing: oppSpacing, maxAngle, fanW: oppFanW } = fanLayout(n, cardSizes.opponent, cardSizes.oppFanBudget)

  let slotClass = 'player-slot'
  if (isBidder) slotClass += ' active-bidder'
  else if (isPlayer) slotClass += ' active-player'

  const lastBid = r?.phase === 'BIDDING'
    ? [...r.bid_history].reverse().find(e => e.position === pos)
    : undefined

  return (
    <div className={slotClass}>
      <div className="player-marker">▼</div>
      <div className="player-pos">
        <span className={teamClass}>{TEAM_LABEL[team] ?? team}</span>
        {isDealer && <span className="badge-dealer" title="Donneur"> 🃏</span>}
        {isBidder && <span className="badge-action" title="À enchérir"> 💬</span>}
        {isPlayer && <span className="badge-action" title="À jouer"> ▶</span>}
      </div>
      <div className="player-name">{name ?? pos}</div>
      {lastBid && (
        <div className={`bid-entry-row ${lastBid.action === 'pass' ? 'bid-pass' : 'bid-bid'}`}>
          <span className="bid-entry-value">{bidActionLabel(lastBid)}</span>
        </div>
      )}
      <div className="hand-fan-wrap">
        {n > 0 && (
          <div className="hand-fan hand-fan-opp" style={{width: oppFanW}}>
            {Array.from({ length: n }).map((_, i) => {
              const k = n > 1 ? i / (n - 1) : 0.5
              const angle = n > 1 ? maxAngle * (2 * k - 1) : 0
              return (
                <div key={i} style={{position:'absolute', left: i * oppSpacing, bottom: 0,
                  transform:`rotate(${angle}deg)`, transformOrigin:'center bottom', zIndex: i}}>
                  <CardBack compact />
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function TrickArea({ r, lastTrick, me }: { r: RoundData | null; lastTrick?: ReturnType<typeof getLastTrick>; me: string }) {
  const [showLast, setShowLast] = useState(false)
  const phase = r?.phase
  const trick = r?.current_trick
  const tricksCount = r?.tricks?.length ?? 0

  const cardAt = (pos: string): CardData | null => {
    const tc = trick?.cards.find(c => c.position === pos)
    return tc?.card ?? null
  }

  const viewing = showLast && !!lastTrick
  // Le pli qui vient d'être remporté reste affiché tant que personne n'a joué
  // dans le nouveau pli — dès qu'une carte y apparaît, on bascule dessus.
  const autoShowLast = !viewing && trick?.cards.length === 0 && !!lastTrick

  const isWinner = (pos: string) => {
    if (viewing || autoShowLast) return lastTrick!.winner === pos
    if (trick?.winner) return trick.winner === pos
    return false
  }

  const displayCard = (pos: string): CardData | null => {
    if (viewing || autoShowLast) return lastTrick!.cardAt(pos)
    if (phase === 'PLAYING') return cardAt(pos)
    if (phase === 'BIDDING') return null
    return lastTrick?.cardAt(pos) ?? null
  }

  const posTop    = PARTNER[me]
  const posLeft   = SCREEN_LEFT[me]
  const posRight  = SCREEN_RIGHT[me]
  const posBottom = me

  return (
    <div className="trick-grid">
      <div className="trick-pos-top">{renderTrickCard(posTop, displayCard(posTop), isWinner(posTop), 'top')}</div>
      <div className="trick-pos-left">{renderTrickCard(posLeft, displayCard(posLeft), isWinner(posLeft), 'left')}</div>
      <div className="trick-pos-center">
        <div style={{textAlign:'center', color:'#555', fontSize:'0.7em'}}>
          {viewing
            ? <span style={{color:'#888'}}>Pli {tricksCount}/8</span>
            : phase === 'PLAYING' ? `Pli ${tricksCount + 1}/8`
            : phase === 'SCORING' ? `Pli ${tricksCount}/8`
            : phase === 'BIDDING' ? 'Enchères' : ''}
        </div>
        {phase === 'PLAYING' && lastTrick && (
          <button
            className="trick-toggle-btn"
            onClick={() => setShowLast(v => !v)}
            title={showLast ? 'pli en cours' : 'dernier pli'}
          >
            {showLast ? 'Pli en cours' : 'Dernier pli'}
          </button>
        )}
      </div>
      <div className="trick-pos-right">{renderTrickCard(posRight, displayCard(posRight), isWinner(posRight), 'right')}</div>
      <div className="trick-pos-bottom">{renderTrickCard(posBottom, displayCard(posBottom), isWinner(posBottom), 'bottom')}</div>
    </div>
  )
}

function renderTrickCard(pos: string, card: CardData | null, winner: boolean, dir: 'top' | 'left' | 'right' | 'bottom') {
  if (!card) return <span style={{color:'#444',fontSize:'0.7em'}}>{pos}</span>
  return (
    <div key={`${card.rank}${card.suit}`} className={`card-arrive-${dir}`}>
      <PlayingCard card={card} compact winner={winner} />
    </div>
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

const BID_SUIT_GRID = ['H', 'C', 'D', 'S', 'NT', 'AT']
const BID_SUIT_BTN_LABEL: Record<string, string> = { ...SUIT_SYM, NT: 'SA', AT: 'TA' }
const BID_SUIT_COLOR_CLASS: Record<string, string> = { H: ' suit-red', D: ' suit-red', C: ' suit-black', S: ' suit-black' }

function bidValueLabel(bid: { is_capot: boolean; is_generale?: boolean; value: number }) {
  if (bid.is_generale) return 'Générale'
  return bid.is_capot ? 'Capot' : String(bid.value)
}

function bidActionLabel(e: { action: string; bid?: { is_capot: boolean; is_generale?: boolean; value: number; trump: string } | null }) {
  if (e.action === 'bid' && e.bid)
    return `${bidValueLabel(e.bid)} ${TRUMP_LABELS[e.bid.trump] ?? e.bid.trump}`
  if (e.action === 'contre')    return 'Coinche !'
  if (e.action === 'surcontre') return 'Surcoinche !'
  return 'Passe'
}

function BidCenter({ r, game, send }: { r: RoundData; game: GameData; send: (m: object) => void }) {
  const actions = r.legal_bid_actions

  const validVals = actions ? [80, 90, 100, 110, 120, 130, 140, 150, 160].filter(
    v => actions.min_bid_value !== null && v >= (actions.min_bid_value ?? 80)
  ) : []

  // Capot et Générale sont intégrés au slider de valeurs, juste après 160.
  const sliderItems: ('CAPOT' | 'GENERALE' | number)[] = [
    ...validVals,
    ...(actions?.can_bid_capot ? ['CAPOT' as const] : []),
    ...(actions?.can_bid_generale ? ['GENERALE' as const] : []),
  ]

  const [selectedIndex, setSelectedIndex] = useState(0)
  const [selectedSuit, setSelectedSuit] = useState<string | null>(null)

  useEffect(() => {
    setSelectedIndex(0)
    setSelectedSuit(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actions?.min_bid_value, r.current_bidder])

  const selectedItem = sliderItems[selectedIndex] ?? null
  const mode = selectedItem === 'CAPOT' ? 'capot' : selectedItem === 'GENERALE' ? 'generale' : 'value'
  const bidVal = typeof selectedItem === 'number' ? selectedItem : null

  const currentBidder = r.current_bidder ? (game.players[r.current_bidder] ?? r.current_bidder) : null
  const currentTeam   = r.current_bidder ? TEAM[r.current_bidder] : null

  // Enchère en tête à dépasser (même pattern que getCurrentTrump).
  const lead = [...r.bid_history].reverse().find(e => e.action === 'bid')

  // Choisir une couleur ne fait que la sélectionner : l'enchère n'est envoyée
  // qu'au clic explicite sur "Prendre", pour éviter toute annonce accidentelle.
  const confirmBid = () => {
    if (selectedSuit === null) return
    if (mode === 'capot') send({ type: 'bid', value: 0, trump: selectedSuit, is_capot: true })
    else if (mode === 'generale') send({ type: 'bid', value: 0, trump: selectedSuit, is_capot: false, is_generale: true })
    else if (bidVal !== null) send({ type: 'bid', value: bidVal, trump: selectedSuit, is_capot: false })
  }

  return (
    <div className="bid-center">
      <div className="bid-center-label">Enchères</div>
      {lead?.bid && (
        <div className="bid-to-beat">
          À battre ·{' '}
          <span className={TEAM[lead.position] === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
            {TEAM_LABEL[TEAM[lead.position]] ?? TEAM[lead.position]}
          </span>{' '}
          {bidValueLabel(lead.bid)} {TRUMP_LABELS[lead.bid.trump] ?? lead.bid.trump}
        </div>
      )}

      {actions ? (
        <div className="bid-center-controls">
          {(actions.can_contre || actions.can_surcontre) && (
            <div className="bid-double-row">
              {actions.can_contre && (
                <button className="bid-double-btn" onClick={() => send({ type: 'contre' })}>Coinche !</button>
              )}
              {actions.can_surcontre && (
                <button className="bid-double-btn" onClick={() => send({ type: 'surcontre' })}>Surcoinche !</button>
              )}
            </div>
          )}

          {sliderItems.length > 0 && (
            <div className="bid-value-spinner">
              <button className="bid-page-arrow" disabled={selectedIndex === 0}
                onClick={() => setSelectedIndex(i => Math.max(0, i - 1))} aria-label="Valeur précédente">‹</button>
              <span className="bid-spinner-value">
                {selectedItem === 'CAPOT' ? 'Capot' : selectedItem === 'GENERALE' ? 'Générale' : String(selectedItem)}
              </span>
              <button className="bid-page-arrow" disabled={selectedIndex >= sliderItems.length - 1}
                onClick={() => setSelectedIndex(i => Math.min(sliderItems.length - 1, i + 1))} aria-label="Valeur suivante">›</button>
            </div>
          )}

          {(actions.min_bid_value !== null || actions.can_bid_capot || actions.can_bid_generale) && (
            <div className="bid-suit-grid">
              {BID_SUIT_GRID.map(t => (
                <button key={t}
                  className={`bid-suit-btn${BID_SUIT_COLOR_CLASS[t] ?? ''}${t === selectedSuit ? ' selected' : ''}`}
                  onClick={() => setSelectedSuit(t)}
                  disabled={mode === 'value' && (actions.min_bid_value === null || bidVal === null)}>
                  {BID_SUIT_BTN_LABEL[t]}
                </button>
              ))}
            </div>
          )}

          <div className="bid-action-row">
            <button className="bid-suit-btn bid-confirm-btn" onClick={confirmBid}
              disabled={selectedSuit === null || (mode === 'value' && bidVal === null)}>Prendre</button>
            {actions.can_pass && (
              <button className="bid-suit-btn bid-pass-btn" onClick={() => send({ type: 'pass' })}>Passer</button>
            )}
          </div>
        </div>
      ) : currentBidder ? (
        <div className="bid-center-waiting">
          <div className="bid-waiting-text">
            <span className={currentTeam === 'NS' ? 'player-team-ns' : 'player-team-ew'}>{currentBidder}</span>
            {' '}réfléchit…
          </div>
          {r.can_contre_volee && (
            <button className="bid-double-btn bid-volee-btn" onClick={() => send({ type: 'contre' })}>
              Coinche !
            </button>
          )}
        </div>
      ) : null}
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
  // scores est un nouvel objet à chaque message WS : on le lit via ref au moment
  // du tir du timer plutôt que de le mettre en dépendance (sinon un update pendant
  // la fenêtre de 3s ré-exécute l'effet, annule le timer et le résultat n'est jamais affiché).
  const scoresRef = useRef(scores)
  scoresRef.current = scores

  useEffect(() => {
    const rn = lastResult?.round_number
    if (rn == null || rn === seenRound.current) return
    seenRound.current = rn
    const result = lastResult!
    // Laisser le dernier pli visible (phase SCORING) avant d'afficher le score —
    // même délai que le backend (websocket.SCORING_DISPLAY_SECONDS) avant de
    // distribuer la donne suivante.
    const showTimer = setTimeout(() => {
      setSnap({ result, scores: { ...scoresRef.current } })
      setVisible(true)
    }, 3000)
    return () => clearTimeout(showTimer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastResult?.round_number])

  useEffect(() => {
    if (!visible) return
    const hideTimer = setTimeout(() => setVisible(false), 4000)
    return () => clearTimeout(hideTimer)
  }, [visible])

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
          {' · '}{bidValueLabel(bid)}{' '}{TRUMP_LABELS[bid.trump] ?? bid.trump}
          {dbl !== 'NONE' && <strong style={{ color: '#f96' }}> {dbl}</strong>}
          {lr.belote_team && (
            <span style={{ color: '#ff4' }}> · Belote {TEAM_LABEL[lr.belote_team] ?? lr.belote_team}</span>
          )}
        </div>
        <div className="rr-scores">
          <div className="rr-score-col">
            <div className="player-team-ns">{TEAM_LABEL['NS']}</div>
            <div className="rr-pts">{lr.score_ns > 0 ? `+${lr.score_ns}` : lr.score_ns}</div>
            <div className="rr-total">{s['NS'] ?? 0} / {targetScore}</div>
          </div>
          <div className="rr-score-sep">·</div>
          <div className="rr-score-col">
            <div className="player-team-ew">{TEAM_LABEL['EW']}</div>
            <div className="rr-pts">{lr.score_ew > 0 ? `+${lr.score_ew}` : lr.score_ew}</div>
            <div className="rr-total">{s['EW'] ?? 0} / {targetScore}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Main Game component ───────────────────────────────────────────────────────

export default function Game({ game, error, send, onQuit }: {
  game: GameData | null
  error: string | null
  send: (msg: object) => void
  onQuit?: () => void
}) {
  if (!game) return <p style={{color:'#4af'}}>Connexion en cours…</p>

  // ─── Chat vocal ─────────────────────────────────────────────────────────────
  const wsRef = useRef<WebSocket | null>(null)
  const voiceManagerRef = useRef<VoiceManager | null>(null)
  const [voicePeers, setVoicePeers] = useState<Map<string, VoicePeer>>(new Map())
  const [localIsSpeaking, setLocalIsSpeaking] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const voiceInitializedRef = useRef(false)
  const [confirmQuit, setConfirmQuit] = useState(false)

  const me = game.my_position

  // Créer un WebSocket interne pour la signalisation WebRTC (même connexion)
  // On réutilise le WebSocket existant via les événements custom
  useEffect(() => {
    // Ré-exécuté à chaque changement de game.players (ex: joueur rejoignant le
    // salon d'attente après nous) — createPeerConnection est un no-op si le
    // peer existe déjà.
    const connectToPeers = () => {
      Object.keys(game.players).forEach(p => {
        if (p !== me && me < p) {
          voiceManagerRef.current?.createPeerConnection(p).catch(err => {
            console.error('[Voice] P2P failed:', p, err)
          })
        }
      })
    }

    // Initialiser le VoiceManager
    if (!voiceInitializedRef.current && game.players[me]) {
      // Créer un manager de voix
      const initVoice = async () => {
        try {
          voiceManagerRef.current = new VoiceManager({
            ws: {
              send: (data: string) => {
                // Intercepter l'envoi et transformer les messages voice-XX en type original
                const msg = JSON.parse(data)
                if (msg.type === 'webrtc-offer') msg.type = 'webrtc-offer'
                if (msg.type === 'webrtc-answer') msg.type = 'webrtc-answer'
                if (msg.type === 'webrtc-ice-candidate') msg.type = 'webrtc-ice-candidate'
                send(msg)
              },
            } as WebSocket,
            myPosition: me,
          })

          // Configurer callbacks
          voiceManagerRef.current.setOnSpeakingChange((position, speaking) => {
            if (position === 'local') {
              setLocalIsSpeaking(speaking)
            } else {
              setVoicePeers(prev => {
                const peer = prev.get(position)
                if (!peer) return prev
                const updated = new Map(prev)
                updated.set(position, { ...peer, isSpeaking: speaking })
                return updated
              })
            }
          })

          voiceManagerRef.current.setOnPeerConnect((position, connected) => {
            setVoicePeers(prev => {
              const peer = prev.get(position)
              if (!peer) return prev
              const updated = new Map(prev)
              updated.set(position, {
                ...peer,
                connectionState: connected ? 'connected' : 'disconnected',
              })
              return updated
            })
          })

          await voiceManagerRef.current.init()
          setIsMuted(false)
          voiceInitializedRef.current = true
          connectToPeers()
        } catch (err) {
          console.error('[Voice] Init failed:', err)
          setVoiceError(err instanceof Error ? err.message : 'Erreur voix')
        }
      }

      initVoice()
    } else if (voiceInitializedRef.current) {
      connectToPeers()
    }

    // Gérer les événements custom pour la signalisation
    const offerHandler = (e: CustomEvent) => {
      const msg = e.detail
      const from = msg.from
      voiceManagerRef.current?.handleOffer(from, msg.data.sdp)
    }
    const answerHandler = (e: CustomEvent) => {
      const msg = e.detail
      const from = msg.from
      voiceManagerRef.current?.handleAnswer(from, msg.data.sdp)
    }
    const iceHandler = (e: CustomEvent) => {
      const msg = e.detail
      const from = msg.from
      voiceManagerRef.current?.handleIceCandidate(from, msg.data.candidate)
    }

    window.addEventListener('voice-offer', offerHandler as EventListener)
    window.addEventListener('voice-answer', answerHandler as EventListener)
    window.addEventListener('voice-ice', iceHandler as EventListener)

    // Mettre à jour les peers
    const interval = setInterval(() => {
      if (voiceManagerRef.current) {
        setVoicePeers(new Map(voiceManagerRef.current.getPeers()))
      }
    }, 200)

    return () => {
      window.removeEventListener('voice-offer', offerHandler as EventListener)
      window.removeEventListener('voice-answer', answerHandler as EventListener)
      window.removeEventListener('voice-ice', iceHandler as EventListener)
      clearInterval(interval)
    }
  }, [game.players, me])

  const toggleMute = () => {
    if (voiceManagerRef.current) {
      const muted = voiceManagerRef.current.toggleMute()
      setIsMuted(muted)
    }
  }

  // Raccourci clavier pour couper le micro
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'm' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        toggleMute()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const r = game.round
  const top    = PARTNER[me]
  const left   = SCREEN_LEFT[me]
  const right  = SCREEN_RIGHT[me]
  const lastTrick = getLastTrick(r)

  const isMyTurnBid  = r?.phase === 'BIDDING'  && r?.current_bidder  === me
  const isMyTurnPlay = r?.phase === 'PLAYING'   && r?.current_player  === me
  const myLastBid = r?.phase === 'BIDDING'
    ? [...r.bid_history].reverse().find(e => e.position === me)
    : undefined

  const myHand = r?.hands[me] ?? []
  const trump  = r ? getCurrentTrump(r) : null
  const sortedHand = r ? sortHand(myHand, trump ?? 'NT') : myHand
  const legalSet = new Set((r?.legal_plays ?? []).map(c => `${c.rank}${c.suit}`))

  const cardSizes = useCardSizes()
  const fanN = sortedHand.length
  const { spacing: fanSpacing, maxAngle: fanMaxAngle, fanW } = fanLayout(fanN, cardSizes.mine, cardSizes.fanBudget)

  const contract = r?.contract
  const ns = game.scores['NS'] ?? 0
  const ew = game.scores['EW'] ?? 0
  const lr = game.last_result

  if (game.phase === 'FINISHED') {
    const won = game.winner === TEAM[game.my_position]
    const isCreator = game.players[game.my_position] === game.creator
    return (
      <div className="eog-overlay">
        <div className={`eog-box ${won ? 'eog-win' : 'eog-lose'}`}>
          {won && (
            <div className="eog-confetti" aria-hidden="true">
              {Array.from({ length: 12 }).map((_, i) => (
                <span key={i} className={`eog-confetti-piece p${i}`} />
              ))}
            </div>
          )}
          <div className="eog-title">{won ? 'VICTOIRE !' : 'DÉFAITE'}</div>
          <div className="eog-scores">
            <div className="eog-team">
              <span className="player-team-ns">{TEAM_LABEL['NS']}</span>
              <strong>{ns}</strong>
            </div>
            <div className="eog-team">
              <span className="player-team-ew">{TEAM_LABEL['EW']}</span>
              <strong>{ew}</strong>
            </div>
          </div>
          <div className="eog-actions">
            {isCreator ? (
              <button className="lp-btn-primary" onClick={() => send({ type: 'rematch' })}>
                Rejouer
              </button>
            ) : (
              <div style={{ color: '#aaa', fontSize: 14 }}>
                En attente du créateur du salon…
              </div>
            )}
            <button className="lp-btn-secondary" onClick={() => send({ type: 'leave' })}>
              Quitter
            </button>
          </div>
          {error && <p className="lp-error">{error}</p>}
        </div>
      </div>
    )
  }

  if (game.phase === 'WAITING') {
    const slots = ['N', 'E', 'S', 'W']
    const joined = Object.keys(game.players).length
    const missing = 4 - joined

    const nsCount = slots.filter(p => game.team_choices[p] === 'NS').length
    const ewCount = slots.filter(p => game.team_choices[p] === 'EW').length
    const isCreator = game.players[game.my_position] === game.creator
    const canGo = joined === 4 && nsCount === 2 && ewCount === 2 && isCreator

    return (
      <div className="lp-root">
        <div className="lp-card">
          {game.room_name && (
            <div className="lp-title" style={{ fontSize: 20, marginBottom: 4 }}>{game.room_name}</div>
          )}
          <div style={{ color: '#aaa', fontSize: 13, marginBottom: 16 }}>#{game.room_id}</div>
          <p className="lp-subtitle" style={{ marginBottom: 16 }}>
            {missing > 0
              ? `En attente de ${missing} joueur${missing > 1 ? 's' : ''}…`
              : 'Choisissez vos équipes puis appuyez sur GO'}
          </p>

          {/* ─── Chat vocal ── */}
          <div style={{ marginBottom: 16 }}>
            <div className="wr-voice">
              {voiceError && <span className="wr-voice-error">{voiceError}</span>}

              {/* Indicateur pour moi */}
              <span className={`wr-voice-chip${localIsSpeaking ? ' speaking' : ''}`}>
                <span className={`wr-voice-dot${isMuted ? ' off' : ''}`}
                  title={isMuted ? 'Micro coupé' : 'Micro activé'} />
                <span className="wr-voice-name me">{game.players[me] ?? me}</span>
                <span className={`wr-voice-badge${localIsSpeaking ? ' speaking' : ''}`}>{me}</span>
              </span>

              {/* Indicateurs pour les autres joueurs */}
              {Array.from(voicePeers.entries()).map(([position, peer]) => (
                <span key={position} className={`wr-voice-chip${peer.isSpeaking ? ' speaking' : ''}`}>
                  <span className={`wr-voice-dot${peer.connectionState === 'connected' ? '' : ' off'}`} />
                  <span className="wr-voice-name">{game.players[position] ?? position}</span>
                  <span className={`wr-voice-badge${peer.isSpeaking ? ' speaking' : ''}`}>{position}</span>
                </span>
              ))}

              <button
                className={`wr-voice-btn${isMuted || voiceError ? ' off' : ''}`}
                onClick={toggleMute}
                disabled={!!voiceError}
                title={voiceError ? voiceError : isMuted ? 'Désactiver le micro (touche M)' : 'Activer le micro'}
              >
                {isMuted ? 'MICRO MUTE' : 'MICRO ON'}
              </button>
            </div>
          </div>

          <div className="wr-player-list">
            {slots.map(pos => {
              const name = game.players[pos]
              const team = game.team_choices[pos]
              const isMe = pos === me
              const isBot = name != null && (game.bots ?? []).includes(name)
              return (
                <div key={pos} className={`wr-player-row${isMe ? ' me' : ''}`}>
                  <span className="wr-player-name">
                    {name != null
                      ? name
                      : <span style={{ color: '#bbb' }}>—</span>}
                  </span>
                  {name != null ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isBot && isCreator && (
                        <button
                          aria-label="Retirer le bot"
                          className="wr-toggle readonly"
                          style={{ width: 'auto', padding: '0 8px', fontSize: 12 }}
                          onClick={() => send({ type: 'remove_bot', position: pos })}
                        >
                          ✕
                        </button>
                      )}
                      <button
                        aria-label={team === 'NS' ? 'TEAM RED' : team === 'EW' ? 'TEAM BLUE' : 'Choisir équipe'}
                        className={`wr-toggle${team === 'NS' ? ' red' : team === 'EW' ? ' blue' : ''}${!isMe || isBot ? ' readonly' : ''}`}
                        onClick={() => isMe && !isBot && send({ type: 'choose_team', team: team === 'NS' ? 'EW' : 'NS' })}
                      />
                    </span>
                  ) : isCreator ? (
                    <span style={{ display: 'flex', gap: 6 }}>
                      <button
                        aria-label="Ajouter un bot TEAM RED"
                        className="wr-toggle red"
                        style={{ width: 'auto', padding: '0 8px', fontSize: 12 }}
                        onClick={() => send({ type: 'add_bot', team: 'NS' })}
                      >
                        + 🤖
                      </button>
                      <button
                        aria-label="Ajouter un bot TEAM BLUE"
                        className="wr-toggle blue"
                        style={{ width: 'auto', padding: '0 8px', fontSize: 12 }}
                        onClick={() => send({ type: 'add_bot', team: 'EW' })}
                      >
                        + 🤖
                      </button>
                    </span>
                  ) : (
                    <span style={{ fontSize: 13, color: '#aaa' }}>en attente</span>
                  )}
                </div>
              )
            })}
          </div>

          {isCreator ? (
            <button
              className="lp-btn-primary"
              disabled={!canGo}
              style={{ marginTop: 20 }}
              onClick={() => canGo && send({ type: 'start_game' })}
            >
              GO !
            </button>
          ) : (
            <div style={{ marginTop: 20, color: '#aaa', fontSize: 14 }}>
              En attente du créateur du salon…
            </div>
          )}

          <button
            className="lp-btn-secondary"
            style={{ marginTop: 8 }}
            onClick={() => send({ type: 'leave' })}
          >
            Quitter le salon
          </button>

          {error && <p className="lp-error">{error}</p>}
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
          <span className="player-team-ns">{TEAM_LABEL['NS']}</span>
          <strong className="score-num">{ns}</strong>
          {r?.phase === 'PLAYING' && (
            <span className="running-points">({r.running_points['NS'] ?? 0})</span>
          )}
          <span className="score-sep"> · </span>
          <span className="player-team-ew">{TEAM_LABEL['EW']}</span>
          <strong className="score-num">{ew}</strong>
          {r?.phase === 'PLAYING' && (
            <span className="running-points">({r.running_points['EW'] ?? 0})</span>
          )}
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
              {' '}{bidValueLabel(contract.bid)}
              {' '}{TRUMP_LABELS[contract.bid.trump] ?? contract.bid.trump}
              {contract.double !== 'NONE' && <strong style={{color:'#f96'}}> {contract.double}</strong>}
              {r?.belote_team && <span style={{color:'#ff4'}}> · Belote {TEAM_LABEL[r.belote_team] ?? r.belote_team}</span>}
            </>
          ) : r?.phase === 'BIDDING' ? (
            <span style={{color:'#888'}}>Enchères en cours…</span>
          ) : null}
        </div>

        {/* ─── Chat vocal (compact, ancré à droite de la barre) ── */}
        <div className="header-voice">
          {voiceError && <span className="header-voice-error">{voiceError}</span>}
          <span
            className={`header-voice-dot${isMuted ? ' off' : ''}${localIsSpeaking ? ' speaking' : ''}`}
            title={`${game.players[me] ?? me} (${me}) — ${isMuted ? 'micro coupé' : 'micro activé'}`}
          >
            {me}
          </span>
          {Array.from(voicePeers.entries()).map(([position, peer]) => (
            <span
              key={position}
              className={`header-voice-dot${peer.connectionState !== 'connected' ? ' off' : ''}${peer.isSpeaking ? ' speaking' : ''}`}
              title={`${game.players[position] ?? position} (${position})`}
            >
              {position}
            </span>
          ))}
          <button
            className={`header-voice-btn${isMuted ? ' off' : ''}`}
            onClick={toggleMute}
            disabled={!!voiceError}
            title={voiceError ? voiceError : isMuted ? 'Désactiver le micro (touche M)' : 'Activer le micro'}
          >
            {isMuted ? '🔇' : '🎤'}
          </button>
          {onQuit && (
            <button
              className="header-quit-btn"
              onClick={() => setConfirmQuit(true)}
              title="Quitter la partie"
              aria-label="Quitter la partie"
            >
              🚪
            </button>
          )}
        </div>
      </div>

      {confirmQuit && onQuit && (
        <div className="eog-overlay">
          <div className="eog-box">
            <div className="quit-title">Quitter la partie ?</div>
            <p className="quit-text">
              Vous retournez à l’accueil. Votre place est conservée : rejoignez le salon
              #{game.room_id} pour reprendre la partie.
            </p>
            <div className="eog-actions">
              <button className="lp-btn-primary" onClick={onQuit}>
                Quitter
              </button>
              <button className="lp-btn-secondary" onClick={() => setConfirmQuit(false)}>
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}


      {/* ── Table losange ── */}
      <div className="table-wrap">
        <div className={`table-grid${r?.phase === 'BIDDING' ? ' table-grid--bidding' : ''}`}>
          <div className="slot-top">
            <PlayerSlot pos={top} game={game} r={r} cardSizes={cardSizes} />
          </div>
          <div className="slot-left">
            <PlayerSlot pos={left} game={game} r={r} cardSizes={cardSizes} />
          </div>
          <div className="slot-center">
            {r?.phase === 'BIDDING'
              ? <BidCenter r={r} game={game} send={send} />
              : <TrickArea r={r} lastTrick={lastTrick ?? undefined} me={me} />}
          </div>
          <div className="slot-right">
            <PlayerSlot pos={right} game={game} r={r} cardSizes={cardSizes} />
          </div>
          <div className="slot-bottom">
            <div className={`player-slot${isMyTurnBid ? ' active-bidder' : isMyTurnPlay ? ' active-player' : ''}`}>
              <div className="player-marker">▼</div>
              <div className="player-pos">
                <span className={TEAM[me] === 'NS' ? 'player-team-ns' : 'player-team-ew'}>
                  {TEAM_LABEL[TEAM[me]] ?? TEAM[me]}
                </span>
                {r?.dealer === me && <span className="badge-dealer" title="Donneur"> 🃏</span>}
                {isMyTurnPlay && <span className="badge-action my-turn"> ▶ À JOUER</span>}
                {isMyTurnBid  && <span className="badge-action" style={{color:'#fa6'}}> 💬 À ENCHÉRIR</span>}
              </div>
              <div className="player-name">{game.players[me] ?? me}</div>
              {myLastBid && (
                <div className={`bid-entry-row ${myLastBid.action === 'pass' ? 'bid-pass' : 'bid-bid'}`}>
                  <span className="bid-entry-value">{bidActionLabel(myLastBid)}</span>
                </div>
              )}
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

      {/* ── Erreur ── */}
      {error && <p className="error">⚠ {error}</p>}

    </div>
  )
}
