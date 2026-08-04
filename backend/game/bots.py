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
    NORMAL_STRENGTH,
    PARTNER_OF,
    TEAM_OF,
    TRUMP_POINTS,
    TRUMP_STRENGTH,
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


def _round10(x: float) -> int:
    return int(round(x / 10.0) * 10)


def _suit_strength(card: Card, trump: Trump) -> int:
    """Force d'une carte au sein de sa propre couleur (pour détecter les maîtres)."""
    if trump == Trump.ALL_TRUMP:
        return TRUMP_STRENGTH[card.rank]
    if trump == Trump.NO_TRUMP:
        return NORMAL_STRENGTH[card.rank]
    ts = Suit(trump.value)
    return TRUMP_STRENGTH[card.rank] if card.suit == ts else NORMAL_STRENGTH[card.rank]


def _seen_cards(r: RoundState, me: Position) -> set[Card]:
    """Cartes déjà connues : ma main + tous les plis joués + le pli en cours."""
    seen = set(r.hands[me])
    for t in r.tricks:
        seen.update(tc.card for tc in t.cards)
    seen.update(tc.card for tc in r.current_trick.cards)
    return seen


def _is_master(card: Card, trump: Trump, seen: set[Card]) -> bool:
    """Vrai si aucune carte non vue de la même couleur ne bat `card`.

    Approximation : ignore la coupe adverse (une couleur maîtresse peut être coupée).
    """
    my_str = _suit_strength(card, trump)
    for rank in rules.ALL_RANKS:
        other = Card(card.suit, rank)
        if (
            other != card
            and other not in seen
            and _suit_strength(other, trump) > my_str
        ):
            return False
    return True


class MediumBot:
    """IA à fonction d'évaluation : enchère proportionnée à la main, contre/surcontre,
    jeu avec mémoire des cartes tombées et du partenaire. Tempérament équilibré.

    ponytail: heuristiques calibrées à la main (constantes ci-dessous), pas une
    résolution exacte. Upgrade → HardBot (Monte Carlo).
    """

    BID_MARGIN = 0  # équilibré : annonce à hauteur de l'estimation, sans marge
    PARTNER_ALLOWANCE = 25  # un contrat est un pari d'équipe : le partenaire apporte
    #   des points que ma seule main ne voit pas. Sans ça le bot n'ouvre quasi jamais.
    NT_SCALE = 0.6  # Sans/Tout Atout : on rabote l'estimation (surestimation facile)
    CONTRE_MIN_CONTRACT = 110  # valeur adverse minimale pour envisager un contre
    CONTRE_HAND = 55  # force minimale de ma main dans leur atout pour contrer
    SURCONTRE_HAND = 100  # force minimale pour surcontrer notre propre contrat

    # ── Évaluation ────────────────────────────────────────────────────────────
    def _estimate_points(self, hand: list[Card], trump: Trump) -> int:
        if trump == Trump.NO_TRUMP:
            return int(sum(NO_TRUMP_POINTS[c.rank] for c in hand) * self.NT_SCALE)
        if trump == Trump.ALL_TRUMP:
            return int(sum(ALL_TRUMP_POINTS[c.rank] for c in hand) * self.NT_SCALE)

        ts = Suit(trump.value)
        trumps = [c for c in hand if c.suit == ts]
        pts = sum(TRUMP_POINTS[c.rank] for c in trumps)
        pts += 5 * sum(1 for c in trumps if c.rank in (Rank.JACK, Rank.NINE))  # maîtres
        pts += max(0, len(trumps) - 4) * 5  # longueur → coupes
        if Card(ts, Rank.KING) in hand and Card(ts, Rank.QUEEN) in hand:
            pts += 20  # belote
        for suit in rules.ALL_SUITS:
            if suit == ts:
                continue
            sc = [c for c in hand if c.suit == suit]
            has_ace = any(c.rank == Rank.ACE for c in sc)
            has_ten = any(c.rank == Rank.TEN for c in sc)
            if has_ace:
                pts += 11 + (10 if has_ten else 0)  # 10 protégé par l'as
            elif has_ten and len(sc) >= 2:
                pts += 5  # 10 semi-protégé
        return pts

    # ── Enchères ──────────────────────────────────────────────────────────────
    def choose_bid(self, r: RoundState, me: Position) -> BidDecision:
        actions = rules.get_legal_bid_actions(r, me)
        hand = r.hands[me]

        if (
            actions["can_surcontre"]
            and r.contract is not None
            and self._estimate_points(hand, r.contract.bid.trump) >= self.SURCONTRE_HAND
        ):
            return BidDecision("surcontre")

        if actions["can_contre"] and r.contract is not None:
            their = r.contract
            if (
                their.contract_value() >= self.CONTRE_MIN_CONTRACT
                and self._estimate_points(hand, their.bid.trump) >= self.CONTRE_HAND
            ):
                return BidDecision("contre")

        best_trump: Trump | None = None
        best_est = -1
        for t in rules.ALL_TRUMPS:
            e = self._estimate_points(hand, t)
            if e > best_est:
                best_est, best_trump = e, t

        min_val = actions["min_bid_value"]
        if min_val is not None and best_trump is not None:
            target = _round10(best_est + self.PARTNER_ALLOWANCE - self.BID_MARGIN)
            if target >= min_val:
                return BidDecision("bid", value=min(target, 160), trump=best_trump)
        return BidDecision("pass")

    # ── Jeu ───────────────────────────────────────────────────────────────────
    def choose_card(self, r: RoundState, me: Position) -> Card:
        legal = rules.get_legal_plays(r)
        if len(legal) == 1:
            return legal[0]

        assert r.contract is not None
        trump = r.contract.bid.trump
        trick = r.current_trick
        seen = _seen_cards(r, me)
        ts = None if trump in (Trump.NO_TRUMP, Trump.ALL_TRUMP) else Suit(trump.value)

        if not trick.cards:
            return self._lead(legal, trump, ts, seen, me, r)

        led = trick.led_suit
        assert led is not None
        best = max(rules.card_strength(tc.card, trump, led) for tc in trick.cards)
        partner_winning = rules.current_trick_winner(trick, trump) == PARTNER_OF[me]

        # Partenaire maître et je suis dernier à jouer → nourrir (gros points).
        if partner_winning and len(trick.cards) == 3:
            return max(legal, key=lambda c: _card_points(c, trump))
        # Partenaire maître mais un adversaire joue encore après moi → petite carte.
        if partner_winning:
            return min(legal, key=lambda c: _card_points(c, trump))

        # Gagner au moins cher, sinon défausser la moins chère en préservant mes maîtres.
        winning = [c for c in legal if rules.card_strength(c, trump, led) > best]
        if winning:
            return min(winning, key=lambda c: rules.card_strength(c, trump, led))
        non_masters = [c for c in legal if not _is_master(c, trump, seen)]
        pool = non_masters or legal
        return min(pool, key=lambda c: _card_points(c, trump))

    def _lead(
        self,
        legal: list[Card],
        trump: Trump,
        ts: Suit | None,
        seen: set[Card],
        me: Position,
        r: RoundState,
    ) -> Card:
        assert r.contract is not None
        # Déclarant avec un gros atout et des atouts adverses dehors → tire atout.
        if ts is not None and TEAM_OF[me] == r.contract.bidding_team:
            my_trumps = [c for c in legal if c.suit == ts]
            has_top = any(c.rank in (Rank.JACK, Rank.NINE) for c in my_trumps)
            outstanding = any(Card(ts, rank) not in seen for rank in rules.ALL_RANKS)
            if my_trumps and has_top and outstanding:
                return max(my_trumps, key=lambda c: _suit_strength(c, trump))

        # Encaisse un maître (préférer un maître latéral pour garder les atouts).
        masters = [c for c in legal if _is_master(c, trump, seen)]
        if masters:
            side = [c for c in masters if ts is None or c.suit != ts]
            return max(side or masters, key=lambda c: _card_points(c, trump))

        # Rien de sûr → entame la carte la moins chère.
        return min(legal, key=lambda c: _card_points(c, trump))


def make_bot(level: str = "easy") -> Bot:
    """Registry des niveaux — ajouter hard ici sans toucher l'intégration."""
    return {"easy": EasyBot, "medium": MediumBot}[level]()
