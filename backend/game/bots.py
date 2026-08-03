"""Joueurs contrôlés par l'IA (bots).

Module pur — aucune I/O. Le seul contrat que les niveaux futurs (MediumBot avec
fonction d'évaluation, HardBot en Monte Carlo, self-play) devront respecter est le
protocole `Bot` : `choose_bid` et `choose_card`. La pompe côté WebSocket
(`backend/api/websocket.py`) et l'intégration ne changent pas quand on ajoute un niveau.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from . import rules
from .models import (
    ALL_TRUMP_POINTS,
    NO_TRUMP_POINTS,
    NORMAL_POINTS,
    PARTNER_OF,
    TRUMP_POINTS,
    Card,
    Position,
    Rank,
    RoundState,
    Suit,
    Trump,
)


@dataclass
class BidDecision:
    kind: Literal["pass", "bid", "contre", "surcontre"]
    value: int | None = None
    trump: Trump | None = None
    is_capot: bool = False
    is_generale: bool = False


class Bot(Protocol):
    def choose_bid(self, r: RoundState, me: Position) -> BidDecision: ...
    def choose_card(self, r: RoundState, me: Position) -> Card: ...


def _card_points(card: Card, trump: Trump) -> int:
    """Valeur en points d'une carte selon l'atout — sert à jouer/défausser la moins chère."""
    if trump == Trump.NO_TRUMP:
        return NO_TRUMP_POINTS[card.rank]
    if trump == Trump.ALL_TRUMP:
        return ALL_TRUMP_POINTS[card.rank]
    ts = Suit(trump.value)
    return TRUMP_POINTS[card.rank] if card.suit == ts else NORMAL_POINTS[card.rank]


# Seuil de force de main (somme des points d'atout d'une couleur + as latéraux)
# à partir duquel l'EasyBot ouvre les enchères. Conservateur pour éviter les chutes.
EASY_BID_THRESHOLD = 45


class EasyBot:
    """IA à règles simples. Volontairement faible mais toujours légale.

    ponytail: heuristiques minimales (n'ouvre qu'à 80, entame la carte la moins chère,
    ne coinche pas). Upgrade → MediumBot (fonction d'évaluation + relance + contre).
    """

    def choose_bid(self, r: RoundState, me: Position) -> BidDecision:
        actions = rules.get_legal_bid_actions(r, me)
        # N'ouvre qu'à 80 (contrat vierge). Ne relance jamais, ne coinche jamais.
        if actions["min_bid_value"] != 80:
            return BidDecision("pass")

        hand = r.hands[me]
        best_suit: Suit | None = None
        best_score = -1
        for suit in rules.ALL_SUITS:
            score = sum(TRUMP_POINTS[c.rank] for c in hand if c.suit == suit)
            score += sum(11 for c in hand if c.rank == Rank.ACE and c.suit != suit)
            if score > best_score:
                best_score, best_suit = score, suit

        if best_score >= EASY_BID_THRESHOLD and best_suit is not None:
            return BidDecision("bid", value=80, trump=Trump(best_suit.value))
        return BidDecision("pass")

    def choose_card(self, r: RoundState, me: Position) -> Card:
        legal = rules.get_legal_plays(r)
        if len(legal) == 1:
            return legal[0]

        assert r.contract is not None
        trump = r.contract.bid.trump
        trick = r.current_trick

        # Entame : carte la moins chère (passif — MediumBot cashera les maîtres).
        if not trick.cards:
            return min(legal, key=lambda c: _card_points(c, trump))

        led = trick.led_suit
        assert led is not None
        best = max(rules.card_strength(tc.card, trump, led) for tc in trick.cards)

        # Partenaire déjà maître → petite carte, on ne gaspille pas.
        if rules.current_trick_winner(trick, trump) == PARTNER_OF[me]:
            return min(legal, key=lambda c: _card_points(c, trump))

        # Gagner avec la carte la plus faible qui suffit, sinon défausser la moins chère.
        winning = [c for c in legal if rules.card_strength(c, trump, led) > best]
        if winning:
            return min(winning, key=lambda c: rules.card_strength(c, trump, led))
        return min(legal, key=lambda c: _card_points(c, trump))


def make_bot(level: str = "easy") -> Bot:
    """Registry des niveaux — ajouter medium/hard ici sans toucher l'intégration."""
    return {"easy": EasyBot}[level]()
