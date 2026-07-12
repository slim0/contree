"""Pure game logic — no I/O, no external dependencies."""

from __future__ import annotations

import copy
import random

from .models import (
    NEXT_DEALER,
    NEXT_PLAYER,
    NORMAL_STRENGTH,
    PARTNER_OF,
    RIGHT_OF,
    TEAM_OF,
    TRUMP_STRENGTH,
    Bid,
    BidHistoryEntry,
    Card,
    Contract,
    Double,
    GamePhase,
    GameState,
    Position,
    Rank,
    RoundState,
    Suit,
    Team,
    Trick,
    TrickCard,
    Trump,
)

# ---------------------------------------------------------------------------
# Deck helpers
# ---------------------------------------------------------------------------

ALL_RANKS = [
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
]
ALL_SUITS = [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]


def create_deck() -> list[Card]:
    return [Card(suit, rank) for suit in ALL_SUITS for rank in ALL_RANKS]


def deal_cards(dealer: Position) -> dict[Position, list[Card]]:
    deck = create_deck()
    random.shuffle(deck)
    first = RIGHT_OF[dealer]
    order = [first]
    p = NEXT_PLAYER[first]
    while p != first:
        order.append(p)
        p = NEXT_PLAYER[p]
    return {order[i]: deck[i * 8 : (i + 1) * 8] for i in range(4)}


# ---------------------------------------------------------------------------
# Card strength (for trick winner)
# ---------------------------------------------------------------------------


def card_strength(card: Card, trump: Trump, led_suit: Suit) -> int:
    """Higher = stronger. -1 = cannot win."""
    if trump == Trump.ALL_TRUMP:
        base = TRUMP_STRENGTH[card.rank] * 10
        return base + 1 if card.suit == led_suit else base

    if trump == Trump.NO_TRUMP:
        return NORMAL_STRENGTH[card.rank] if card.suit == led_suit else -1

    trump_suit = Suit(trump.value)
    if card.suit == trump_suit:
        return TRUMP_STRENGTH[card.rank] + 100  # trumps always beat non-trumps
    if card.suit == led_suit:
        return NORMAL_STRENGTH[card.rank]
    return -1


def trick_winner(trick: Trick, trump: Trump) -> Position:
    assert trick.led_suit is not None
    led_suit = trick.led_suit
    best_tc = max(trick.cards, key=lambda tc: card_strength(tc.card, trump, led_suit))
    return best_tc.position


def current_trick_winner(trick: Trick, trump: Trump) -> Position | None:
    if not trick.cards:
        return None
    return trick_winner(trick, trump)


# ---------------------------------------------------------------------------
# Belote detection
# ---------------------------------------------------------------------------


def detect_belote_team(hands: dict[Position, list[Card]], trump: Trump) -> Team | None:
    """Returns the team of the single player holding both K and Q of trump, or None.

    La belote exige que le roi ET la dame d'atout soient dans la MEME main —
    si les deux cartes sont réparties entre les deux partenaires, ça ne compte pas.
    """
    if trump in (Trump.NO_TRUMP, Trump.ALL_TRUMP):
        return None
    trump_suit = Suit(trump.value)
    king = Card(trump_suit, Rank.KING)
    queen = Card(trump_suit, Rank.QUEEN)
    for pos, hand in hands.items():
        if king in hand and queen in hand:
            return TEAM_OF[pos]
    return None


def _trump_suit(trump: Trump) -> Suit | None:
    if trump in (Trump.NO_TRUMP, Trump.ALL_TRUMP):
        return None
    return Suit(trump.value)


# ---------------------------------------------------------------------------
# Legal plays
# ---------------------------------------------------------------------------


def _trump_strength_of_card(card: Card, trump: Trump) -> int:
    """Strength within trump suit only (for escalation check)."""
    if trump == Trump.ALL_TRUMP:
        return TRUMP_STRENGTH[card.rank]
    ts = _trump_suit(trump)
    if ts and card.suit == ts:
        return TRUMP_STRENGTH[card.rank]
    return -1


def _best_trump_in_trick(trick: Trick, trump: Trump) -> int:
    """Highest trump strength currently in the trick. -1 if no trump played."""
    if trump == Trump.ALL_TRUMP:
        # In ALL_TRUMP, "trump" for escalation purposes = led suit
        if not trick.led_suit:
            return -1
        led = trick.led_suit
        suits = [tc for tc in trick.cards if tc.card.suit == led]
        return max((TRUMP_STRENGTH[tc.card.rank] for tc in suits), default=-1)
    ts = _trump_suit(trump)
    if not ts:
        return -1
    trumps = [tc for tc in trick.cards if tc.card.suit == ts]
    return max((TRUMP_STRENGTH[tc.card.rank] for tc in trumps), default=-1)


def get_legal_plays(round_state: RoundState) -> list[Card]:
    """Returns all cards the current player may legally play."""
    player = round_state.current_player
    assert player is not None
    hand = round_state.hands[player]
    assert round_state.contract is not None
    trump = round_state.contract.bid.trump
    trick = round_state.current_trick

    # Opening a new trick: any card
    if not trick.cards:
        return list(hand)

    led_suit = trick.led_suit
    assert led_suit is not None

    # --- Sans Atout: must follow suit or free discard ---
    if trump == Trump.NO_TRUMP:
        suit_cards = [c for c in hand if c.suit == led_suit]
        return suit_cards if suit_cards else list(hand)

    # --- Tout Atout: must follow led suit and escalate ---
    if trump == Trump.ALL_TRUMP:
        suit_cards = [c for c in hand if c.suit == led_suit]
        if not suit_cards:
            return list(hand)
        best = _best_trump_in_trick(trick, trump)
        higher = [c for c in suit_cards if TRUMP_STRENGTH[c.rank] > best]
        return higher if higher else suit_cards

    # --- Normal trump ---
    trump_suit = _trump_suit(trump)
    assert trump_suit is not None
    suit_cards = [c for c in hand if c.suit == led_suit]
    trump_cards = [c for c in hand if c.suit == trump_suit]

    # Rule 1: must follow led suit
    if suit_cards:
        if led_suit == trump_suit:
            # Led suit IS trump → Rule 4: must escalate
            best = _best_trump_in_trick(trick, trump)
            higher = [c for c in suit_cards if TRUMP_STRENGTH[c.rank] > best]
            return higher if higher else suit_cards
        return suit_cards

    # Can't follow suit
    partner = PARTNER_OF[player]
    winner_so_far = current_trick_winner(trick, trump)
    partner_winning = winner_so_far == partner

    # Rule 2: partner winning → free discard
    if partner_winning:
        return list(hand)

    # Rule 3: must cut with trump if possible
    if not trump_cards:
        return list(hand)

    # Rule 4: must escalate trump if possible
    best = _best_trump_in_trick(trick, trump)
    higher = [c for c in trump_cards if TRUMP_STRENGTH[c.rank] > best]
    return higher if higher else trump_cards


# ---------------------------------------------------------------------------
# Legal bids
# ---------------------------------------------------------------------------

BID_VALUES = [80, 90, 100, 110, 120, 130, 140, 150, 160]
ALL_TRUMPS = [
    Trump.HEARTS,
    Trump.DIAMONDS,
    Trump.CLUBS,
    Trump.SPADES,
    Trump.NO_TRUMP,
    Trump.ALL_TRUMP,
]


def get_legal_bid_actions(round_state: RoundState, player: Position) -> dict:
    """
    Returns dict:
      can_pass: bool
      can_contre: bool
      can_surcontre: bool
      min_bid_value: int | None  (None if can't bid)
      can_bid_capot: bool
    """
    contract = round_state.contract
    result = {
        "can_pass": True,
        "can_contre": False,
        "can_surcontre": False,
        "min_bid_value": None,
        "can_bid_capot": False,
    }

    if contract is None:
        result["min_bid_value"] = 80
        result["can_bid_capot"] = True
        return result

    double = contract.double
    bidding_team = contract.bidding_team
    player_team = TEAM_OF[player]

    if double == Double.SURCONTRE:
        # Bidding already ended
        result["can_pass"] = True
        return result

    if double == Double.NONE:
        # Opposing team can contre
        if player_team != bidding_team:
            result["can_contre"] = True
        # Anyone can raise (if value > current)
        current_val = contract.bid.value
        if not contract.bid.is_capot and contract.bid.position != player:
            next_val = current_val + 10
            if next_val <= 160:
                result["min_bid_value"] = next_val
            result["can_bid_capot"] = True
        return result

    if double == Double.CONTRE:
        # Only bidding team can surcontre
        if player_team == bidding_team:
            result["can_surcontre"] = True
        return result

    return result


# ---------------------------------------------------------------------------
# Game actions
# ---------------------------------------------------------------------------


def start_new_round(game: GameState) -> GameState:
    game = copy.deepcopy(game)
    round_num = (game.round.number + 1) if game.round else 1
    dealer = NEXT_DEALER[game.round.dealer] if game.round else Position.NORTH

    hands = deal_cards(dealer)
    first_bidder = RIGHT_OF[dealer]

    # belote is detected after contract is set (trump unknown during bidding)
    from .models import RoundState

    game.round = RoundState(
        number=round_num,
        dealer=dealer,
        hands=hands,
        phase=GamePhase.BIDDING,
        current_bidder=first_bidder,
        pass_count=0,
        bid_history=[],
        contract=None,
        current_player=None,
        tricks=[],
        current_trick=Trick(),
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )
    game.messages.append(f"Manche {round_num} — Donneur : {dealer.value}")
    game.messages.append(
        f"Tour d'enchères — premier enchérisseur : {first_bidder.value}"
    )
    return game


def apply_pass(game: GameState) -> tuple[GameState, str]:
    game = copy.deepcopy(game)
    r = game.round
    assert r and r.phase == GamePhase.BIDDING
    player = r.current_bidder
    assert player is not None

    r.bid_history.append(BidHistoryEntry(player, "pass"))
    r.pass_count += 1

    msg = f"{player.value} passe"

    # 4 passes with no contract → deal void
    if r.pass_count >= 4 and r.contract is None:
        game.messages.append(msg)
        game.messages.append("4 passes sans enchère — donne annulée")
        return start_new_round(game), "redeal"

    # 3 consecutive passes after contract → bidding ends
    if r.pass_count >= 3 and r.contract is not None:
        game.messages.append(msg)
        return _start_playing(game), "playing"

    r.current_bidder = NEXT_PLAYER[player]
    game.messages.append(msg)
    return game, "ok"


def apply_bid(
    game: GameState, value: int, is_capot: bool, trump: Trump
) -> tuple[GameState, str]:
    game = copy.deepcopy(game)
    r = game.round
    assert r and r.phase == GamePhase.BIDDING
    player = r.current_bidder
    assert player is not None

    bid = Bid(player, value, is_capot, trump)
    r.contract = Contract(bid, Double.NONE, TEAM_OF[player])
    r.pass_count = 0
    r.bid_history.append(BidHistoryEntry(player, "bid", bid))
    r.current_bidder = NEXT_PLAYER[player]

    val_str = "Capot" if is_capot else str(value)
    game.messages.append(f"{player.value} annonce {val_str} à {trump.value}")
    return game, "ok"


def apply_contre(game: GameState) -> tuple[GameState, str]:
    game = copy.deepcopy(game)
    r = game.round
    assert r and r.contract and r.phase == GamePhase.BIDDING
    player = r.current_bidder
    assert player is not None

    r.contract.double = Double.CONTRE
    r.pass_count = 0
    r.bid_history.append(BidHistoryEntry(player, "contre"))
    r.current_bidder = NEXT_PLAYER[player]
    game.messages.append(f"{player.value} contre !")
    return game, "ok"


def apply_surcontre(game: GameState) -> tuple[GameState, str]:
    game = copy.deepcopy(game)
    r = game.round
    assert r and r.contract and r.phase == GamePhase.BIDDING
    player = r.current_bidder
    assert player is not None

    r.contract.double = Double.SURCONTRE
    r.bid_history.append(BidHistoryEntry(player, "surcontre"))
    game.messages.append(f"{player.value} surcontre !")
    # Surcontre ends bidding immediately
    return _start_playing(game), "playing"


def _start_playing(game: GameState) -> GameState:
    r = game.round
    assert r and r.contract
    trump = r.contract.bid.trump
    # Detect belote now that trump is known — gardé secret tant qu'aucune des
    # deux cartes (roi/dame d'atout) n'a été jouée (cf. RoundState.to_dict).
    r.belote_team = detect_belote_team(r.hands, trump)

    r.phase = GamePhase.PLAYING
    first = RIGHT_OF[r.dealer]
    r.current_player = first
    r.current_trick = Trick()

    c = r.contract
    val_str = "Capot" if c.bid.is_capot else str(c.bid.value)
    double_str = f" ({c.double.value})" if c.double != Double.NONE else ""
    game.messages.append(
        f"Contrat : {c.bidding_team.value} joue {val_str} à {c.bid.trump.value}{double_str}"
    )
    game.messages.append(f"Premier joueur : {first.value}")
    return game


def apply_play(game: GameState, card: Card) -> tuple[GameState, str]:
    game = copy.deepcopy(game)
    r = game.round
    assert r and r.phase == GamePhase.PLAYING
    player = r.current_player
    assert player is not None

    # Validate legal play
    legal = get_legal_plays(r)
    if card not in legal:
        return game, f"Carte illégale : {card}. Légales : {legal}"

    # Remove card from hand
    r.hands[player] = [c for c in r.hands[player] if c != card]

    # Check for belote announcement (auto)
    assert r.contract is not None
    trump = r.contract.bid.trump
    if trump not in (Trump.NO_TRUMP, Trump.ALL_TRUMP):
        ts = Suit(trump.value)
        if r.belote_team and TEAM_OF[player] == r.belote_team:
            if card == Card(ts, Rank.KING):
                r.belote_king_played = True
                game.messages.append(f"Belote ! ({player.value} joue R{ts.value})")
            elif card == Card(ts, Rank.QUEEN):
                r.belote_queen_played = True
                if r.belote_king_played:
                    game.messages.append(
                        f"Rebelote ! ({player.value} joue D{ts.value})"
                    )
                else:
                    game.messages.append(
                        f"Rebelote ! ({player.value} joue D{ts.value})"
                    )

    # Add to current trick
    r.current_trick.cards.append(TrickCard(player, card))
    game.messages.append(f"{player.value} joue {card}")

    # If trick complete (4 cards)
    if len(r.current_trick.cards) == 4:
        winner = trick_winner(r.current_trick, trump)
        r.current_trick.winner = winner
        r.tricks.append(r.current_trick)
        r.current_trick = Trick()
        game.messages.append(f"Pli remporté par {winner.value}")

        # Check if all 8 tricks done
        if len(r.tricks) == 8:
            return _end_round(game), "round_end"

        r.current_player = winner
    else:
        r.current_player = NEXT_PLAYER[player]

    return game, "ok"


def _end_round(game: GameState) -> GameState:
    from .scoring import compute_round_result

    assert game.round is not None
    result = compute_round_result(game.round)
    game.last_result = result

    game.scores[Team.NORTH_SOUTH] += result.score_ns
    game.scores[Team.EAST_WEST] += result.score_ew
    game.messages.append(result.message)
    game.messages.append(
        f"Scores : NS={game.scores[Team.NORTH_SOUTH]}  EW={game.scores[Team.EAST_WEST]}"
    )

    target = game.target_score
    ns_win = game.scores[Team.NORTH_SOUTH] >= target
    ew_win = game.scores[Team.EAST_WEST] >= target

    if ns_win or ew_win:
        if ns_win and ew_win:
            winner = (
                Team.NORTH_SOUTH
                if game.scores[Team.NORTH_SOUTH] > game.scores[Team.EAST_WEST]
                else Team.EAST_WEST
            )
        else:
            winner = Team.NORTH_SOUTH if ns_win else Team.EAST_WEST
        game.winner = winner
        game.phase = GamePhase.FINISHED
        game.messages.append(f"Partie terminée ! Vainqueur : {winner.value}")
    else:
        game = start_new_round(game)

    return game
