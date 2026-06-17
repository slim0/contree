from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Suit(str, Enum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"


class Rank(str, Enum):
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class Trump(str, Enum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"
    NO_TRUMP = "NT"
    ALL_TRUMP = "AT"


class Position(str, Enum):
    NORTH = "N"
    EAST = "E"
    SOUTH = "S"
    WEST = "W"


class Team(str, Enum):
    NORTH_SOUTH = "NS"
    EAST_WEST = "EW"


class Double(str, Enum):
    NONE = "NONE"
    CONTRE = "CONTRE"
    SURCONTRE = "SURCONTRE"


class GamePhase(str, Enum):
    WAITING = "WAITING"
    BIDDING = "BIDDING"
    PLAYING = "PLAYING"
    SCORING = "SCORING"
    FINISHED = "FINISHED"


TEAM_OF: dict[Position, Team] = {
    Position.NORTH: Team.NORTH_SOUTH,
    Position.SOUTH: Team.NORTH_SOUTH,
    Position.EAST: Team.EAST_WEST,
    Position.WEST: Team.EAST_WEST,
}

PARTNER_OF: dict[Position, Position] = {
    Position.NORTH: Position.SOUTH,
    Position.SOUTH: Position.NORTH,
    Position.EAST: Position.WEST,
    Position.WEST: Position.EAST,
}

# Anti-clockwise play order: E→N→W→S→E
# When dealer is NORTH, first to act is EAST (dealer's right)
NEXT_PLAYER: dict[Position, Position] = {
    Position.EAST: Position.NORTH,
    Position.NORTH: Position.WEST,
    Position.WEST: Position.SOUTH,
    Position.SOUTH: Position.EAST,
}

# Clockwise = physical "right" of each player (first to act after dealer deals)
RIGHT_OF: dict[Position, Position] = {
    Position.NORTH: Position.EAST,
    Position.EAST: Position.SOUTH,
    Position.SOUTH: Position.WEST,
    Position.WEST: Position.NORTH,
}

# Dealer rotates anti-clockwise
NEXT_DEALER = NEXT_PLAYER

# Card strength tables
TRUMP_STRENGTH: dict[Rank, int] = {
    Rank.JACK: 7, Rank.NINE: 6, Rank.ACE: 5, Rank.TEN: 4,
    Rank.KING: 3, Rank.QUEEN: 2, Rank.EIGHT: 1, Rank.SEVEN: 0,
}

NORMAL_STRENGTH: dict[Rank, int] = {
    Rank.ACE: 7, Rank.TEN: 6, Rank.KING: 5, Rank.QUEEN: 4,
    Rank.JACK: 3, Rank.NINE: 2, Rank.EIGHT: 1, Rank.SEVEN: 0,
}

# Card points tables
TRUMP_POINTS: dict[Rank, int] = {
    Rank.JACK: 20, Rank.NINE: 14, Rank.ACE: 11, Rank.TEN: 10,
    Rank.KING: 4, Rank.QUEEN: 3, Rank.EIGHT: 0, Rank.SEVEN: 0,
}

NORMAL_POINTS: dict[Rank, int] = {
    Rank.ACE: 11, Rank.TEN: 10, Rank.KING: 4, Rank.QUEEN: 3,
    Rank.JACK: 2, Rank.NINE: 0, Rank.EIGHT: 0, Rank.SEVEN: 0,
}

NO_TRUMP_POINTS: dict[Rank, int] = {
    Rank.ACE: 19, Rank.TEN: 10, Rank.KING: 4, Rank.QUEEN: 3,
    Rank.JACK: 2, Rank.NINE: 0, Rank.EIGHT: 0, Rank.SEVEN: 0,
}

ALL_TRUMP_POINTS: dict[Rank, int] = {
    Rank.JACK: 13, Rank.NINE: 9, Rank.ACE: 6, Rank.TEN: 5,
    Rank.KING: 3, Rank.QUEEN: 2, Rank.EIGHT: 0, Rank.SEVEN: 0,
}

SUIT_SYMBOLS = {Suit.HEARTS: "♥", Suit.DIAMONDS: "♦", Suit.CLUBS: "♣", Suit.SPADES: "♠"}


@dataclass
class Card:
    suit: Suit
    rank: Rank

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    def __repr__(self) -> str:
        return f"{self.rank.value}{SUIT_SYMBOLS[self.suit]}"

    def to_dict(self) -> dict:
        return {"suit": self.suit.value, "rank": self.rank.value}

    @classmethod
    def from_dict(cls, d: dict) -> Card:
        return cls(Suit(d["suit"]), Rank(d["rank"]))


@dataclass
class Bid:
    position: Position
    value: int      # 80-160 or 0 for capot
    is_capot: bool
    trump: Trump

    def display_value(self) -> str:
        return "Capot" if self.is_capot else str(self.value)

    def to_dict(self) -> dict:
        return {
            "position": self.position.value,
            "value": self.value,
            "is_capot": self.is_capot,
            "trump": self.trump.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Bid:
        return cls(Position(d["position"]), d["value"], d["is_capot"], Trump(d["trump"]))


@dataclass
class Contract:
    bid: Bid
    double: Double
    bidding_team: Team

    def contract_value(self) -> int:
        """Point value of this contract (for scoring)."""
        return 160 if self.bid.is_capot else self.bid.value

    def to_dict(self) -> dict:
        return {
            "bid": self.bid.to_dict(),
            "double": self.double.value,
            "bidding_team": self.bidding_team.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Contract:
        return cls(Bid.from_dict(d["bid"]), Double(d["double"]), Team(d["bidding_team"]))


@dataclass
class TrickCard:
    position: Position
    card: Card

    def to_dict(self) -> dict:
        return {"position": self.position.value, "card": self.card.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> TrickCard:
        return cls(Position(d["position"]), Card.from_dict(d["card"]))


@dataclass
class Trick:
    cards: list[TrickCard] = field(default_factory=list)
    winner: Optional[Position] = None

    @property
    def led_suit(self) -> Optional[Suit]:
        return self.cards[0].card.suit if self.cards else None

    def to_dict(self) -> dict:
        return {
            "cards": [c.to_dict() for c in self.cards],
            "winner": self.winner.value if self.winner else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Trick:
        t = cls([TrickCard.from_dict(c) for c in d["cards"]])
        t.winner = Position(d["winner"]) if d.get("winner") else None
        return t


@dataclass
class BidHistoryEntry:
    position: Position
    action: str  # "bid", "pass", "contre", "surcontre"
    bid: Optional[Bid] = None

    def to_dict(self) -> dict:
        return {
            "position": self.position.value,
            "action": self.action,
            "bid": self.bid.to_dict() if self.bid else None,
        }


@dataclass
class RoundState:
    number: int
    dealer: Position
    hands: dict[Position, list[Card]]
    phase: GamePhase

    # Bidding
    current_bidder: Optional[Position]
    pass_count: int
    bid_history: list[BidHistoryEntry]
    contract: Optional[Contract]

    # Playing
    current_player: Optional[Position]
    tricks: list[Trick]
    current_trick: Trick

    # Belote (auto-detected, announced when K or Q of trump is played)
    belote_team: Optional[Team]
    belote_king_played: bool
    belote_queen_played: bool

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "dealer": self.dealer.value,
            "hands": {p.value: [c.to_dict() for c in cs] for p, cs in self.hands.items()},
            "phase": self.phase.value,
            "current_bidder": self.current_bidder.value if self.current_bidder else None,
            "pass_count": self.pass_count,
            "bid_history": [e.to_dict() for e in self.bid_history],
            "contract": self.contract.to_dict() if self.contract else None,
            "current_player": self.current_player.value if self.current_player else None,
            "tricks": [t.to_dict() for t in self.tricks],
            "current_trick": self.current_trick.to_dict(),
            "belote_team": self.belote_team.value if self.belote_team else None,
            "belote_king_played": self.belote_king_played,
            "belote_queen_played": self.belote_queen_played,
        }


@dataclass
class RoundResult:
    round_number: int
    contract: Contract
    preneurs_eval: int
    contract_made: bool
    score_ns: int
    score_ew: int
    belote_team: Optional[Team]
    message: str

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "contract": self.contract.to_dict(),
            "preneurs_eval": self.preneurs_eval,
            "contract_made": self.contract_made,
            "score_ns": self.score_ns,
            "score_ew": self.score_ew,
            "belote_team": self.belote_team.value if self.belote_team else None,
            "message": self.message,
        }


@dataclass
class GameState:
    room_id: str
    players: dict[Position, str]
    scores: dict[Team, int]
    target_score: int
    round: Optional[RoundState]
    phase: GamePhase
    winner: Optional[Team]
    last_result: Optional[RoundResult]
    messages: list[str]
    room_name: str = ""
    # team_choices: position_str → "NS"|"EW", set during WAITING phase
    team_choices: dict[str, str] = field(default_factory=dict)
    ready_to_start: bool = False

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "room_name": self.room_name,
            "players": {p.value: n for p, n in self.players.items()},
            "scores": {t.value: s for t, s in self.scores.items()},
            "target_score": self.target_score,
            "round": self.round.to_dict() if self.round else None,
            "phase": self.phase.value,
            "winner": self.winner.value if self.winner else None,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "messages": self.messages[-30:],
            "team_choices": self.team_choices,
            "ready_to_start": self.ready_to_start,
        }
