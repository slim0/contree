export interface CardData { suit: string; rank: string }

export interface BidData {
  position: string; value: number; is_capot: boolean; trump: string
}

export interface ContractData {
  bid: BidData; double: string; bidding_team: string
}

export interface TrickCardData { position: string; card: CardData }

export interface TrickData {
  cards: TrickCardData[]; winner: string | null
}

export interface BidHistoryEntry {
  position: string; action: string; bid: BidData | null
}

export interface RoundData {
  number: number
  dealer: string
  hands: Record<string, CardData[]>
  phase: string
  current_bidder: string | null
  pass_count: number
  bid_history: BidHistoryEntry[]
  contract: ContractData | null
  current_player: string | null
  tricks: TrickData[]
  current_trick: TrickData
  belote_team: string | null
  belote_king_played: boolean
  belote_queen_played: boolean
  running_points: Record<string, number>
  legal_plays?: CardData[]
  legal_bid_actions?: LegalBidActions
  can_contre_volee?: boolean
}

export interface LegalBidActions {
  can_pass: boolean
  can_contre: boolean
  can_surcontre: boolean
  min_bid_value: number | null
  can_bid_capot: boolean
}

export interface RoundResult {
  round_number: number
  contract: ContractData
  preneurs_eval: number
  contract_made: boolean
  score_ns: number
  score_ew: number
  belote_team: string | null
  message: string
}

export interface GameData {
  room_id: string
  room_name: string
  players: Record<string, string>
  scores: Record<string, number>
  target_score: number
  round: RoundData | null
  phase: string
  winner: string | null
  last_result: RoundResult | null
  messages: string[]
  my_position: string
  team_choices: Record<string, string>
  ready_to_start: boolean
}
