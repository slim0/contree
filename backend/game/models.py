from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class Suit(StrEnum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"


class Rank(StrEnum):
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class Trump(StrEnum):
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"
    NO_TRUMP = "NT"
    ALL_TRUMP = "AT"


class Position(StrEnum):
    NORTH = "N"
    EAST = "E"
    SOUTH = "S"
    WEST = "W"


class Team(StrEnum):
    NORTH_SOUTH = "NS"
    EAST_WEST = "EW"


class Double(StrEnum):
    NONE = "NONE"
    CONTRE = "CONTRE"
    SURCONTRE = "SURCONTRE"


class GamePhase(StrEnum):
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

# Clockwise play order: N→E→S→W→N
# When dealer is NORTH, first to act is EAST (dealer's right)
NEXT_PLAYER: dict[Position, Position] = {
    Position.NORTH: Position.EAST,
    Position.EAST: Position.SOUTH,
    Position.SOUTH: Position.WEST,
    Position.WEST: Position.NORTH,
}

# Clockwise = physical "right" of each player (first to act after dealer deals)
RIGHT_OF: dict[Position, Position] = {
    Position.NORTH: Position.EAST,
    Position.EAST: Position.SOUTH,
    Position.SOUTH: Position.WEST,
    Position.WEST: Position.NORTH,
}

# Dealer rotates clockwise
NEXT_DEALER = NEXT_PLAYER

# Card strength tables
TRUMP_STRENGTH: dict[Rank, int] = {
    Rank.JACK: 7,
    Rank.NINE: 6,
    Rank.ACE: 5,
    Rank.TEN: 4,
    Rank.KING: 3,
    Rank.QUEEN: 2,
    Rank.EIGHT: 1,
    Rank.SEVEN: 0,
}

NORMAL_STRENGTH: dict[Rank, int] = {
    Rank.ACE: 7,
    Rank.TEN: 6,
    Rank.KING: 5,
    Rank.QUEEN: 4,
    Rank.JACK: 3,
    Rank.NINE: 2,
    Rank.EIGHT: 1,
    Rank.SEVEN: 0,
}

# Card points tables
TRUMP_POINTS: dict[Rank, int] = {
    Rank.JACK: 20,
    Rank.NINE: 14,
    Rank.ACE: 11,
    Rank.TEN: 10,
    Rank.KING: 4,
    Rank.QUEEN: 3,
    Rank.EIGHT: 0,
    Rank.SEVEN: 0,
}

NORMAL_POINTS: dict[Rank, int] = {
    Rank.ACE: 11,
    Rank.TEN: 10,
    Rank.KING: 4,
    Rank.QUEEN: 3,
    Rank.JACK: 2,
    Rank.NINE: 0,
    Rank.EIGHT: 0,
    Rank.SEVEN: 0,
}

NO_TRUMP_POINTS: dict[Rank, int] = {
    Rank.ACE: 19,
    Rank.TEN: 10,
    Rank.KING: 4,
    Rank.QUEEN: 3,
    Rank.JACK: 2,
    Rank.NINE: 0,
    Rank.EIGHT: 0,
    Rank.SEVEN: 0,
}

ALL_TRUMP_POINTS: dict[Rank, int] = {
    Rank.JACK: 13,
    Rank.NINE: 9,
    Rank.ACE: 6,
    Rank.TEN: 5,
    Rank.KING: 3,
    Rank.QUEEN: 2,
    Rank.EIGHT: 0,
    Rank.SEVEN: 0,
}

SUIT_SYMBOLS = {Suit.HEARTS: "♥", Suit.DIAMONDS: "♦", Suit.CLUBS: "♣", Suit.SPADES: "♠"}


@dataclass(unsafe_hash=True)
class Card:
    suit: Suit
    rank: Rank

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
    value: int  # 80-160, or 0 for capot/générale
    is_capot: bool
    trump: Trump
    is_generale: bool = False  # un seul joueur remporte les 8 plis — 500 pts

    def display_value(self) -> str:
        if self.is_generale:
            return "Générale"
        return "Capot" if self.is_capot else str(self.value)

    def to_dict(self) -> dict:
        return {
            "position": self.position.value,
            "value": self.value,
            "is_capot": self.is_capot,
            "trump": self.trump.value,
            "is_generale": self.is_generale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Bid:
        return cls(
            Position(d["position"]),
            d["value"],
            d["is_capot"],
            Trump(d["trump"]),
            d.get("is_generale", False),
        )


@dataclass
class Contract:
    bid: Bid
    double: Double
    bidding_team: Team

    def contract_value(self) -> int:
        """Point value of this contract (for scoring)."""
        if self.bid.is_generale:
            return 500
        return 250 if self.bid.is_capot else self.bid.value

    def to_dict(self) -> dict:
        return {
            "bid": self.bid.to_dict(),
            "double": self.double.value,
            "bidding_team": self.bidding_team.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Contract:
        return cls(
            Bid.from_dict(d["bid"]), Double(d["double"]), Team(d["bidding_team"])
        )


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
    winner: Position | None = None

    @property
    def led_suit(self) -> Suit | None:
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
    bid: Bid | None = None

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
    current_bidder: Position | None
    pass_count: int
    bid_history: list[BidHistoryEntry]
    contract: Contract | None

    # Playing
    current_player: Position | None
    tricks: list[Trick]
    current_trick: Trick

    # Belote (auto-detected, announced when K or Q of trump is played)
    belote_team: Team | None
    belote_king_played: bool
    belote_queen_played: bool

    def to_dict(self) -> dict:
        # La belote n'est révélée aux joueurs qu'une fois le roi ou la dame
        # d'atout effectivement joué·e — pas dès qu'elle est détectée en interne.
        belote_revealed = self.belote_king_played or self.belote_queen_played
        return {
            "number": self.number,
            "dealer": self.dealer.value,
            "hands": {
                p.value: [c.to_dict() for c in cs] for p, cs in self.hands.items()
            },
            "phase": self.phase.value,
            "current_bidder": self.current_bidder.value
            if self.current_bidder
            else None,
            "pass_count": self.pass_count,
            "bid_history": [e.to_dict() for e in self.bid_history],
            "contract": self.contract.to_dict() if self.contract else None,
            "current_player": self.current_player.value
            if self.current_player
            else None,
            "tricks": [t.to_dict() for t in self.tricks],
            "current_trick": self.current_trick.to_dict(),
            "belote_team": self.belote_team.value
            if (self.belote_team and belote_revealed)
            else None,
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
    belote_team: Team | None
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
    round: RoundState | None
    phase: GamePhase
    winner: Team | None
    last_result: RoundResult | None
    messages: list[str]
    room_name: str = ""
    # team_choices: position_str → "NS"|"EW", set during WAITING phase
    team_choices: dict[str, str] = field(default_factory=dict)
    ready_to_start: bool = False
    # horodatage de la dernière écriture, utilisé par memory_store.reap_stale_rooms
    # pour nettoyer les rooms abandonnées ; jamais envoyé aux clients
    last_activity: float = field(default_factory=time.time)

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
