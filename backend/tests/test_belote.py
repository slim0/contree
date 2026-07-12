"""Tests sur la détection et l'annonce de la belote (roi + dame d'atout)."""

from __future__ import annotations

from backend.game.models import (
    Card,
    GamePhase,
    GameState,
    Position,
    Rank,
    RoundState,
    Suit,
    Team,
    Trick,
    Trump,
)
from backend.game.rules import (
    apply_bid,
    apply_pass,
    apply_play,
    detect_belote_team,
    start_new_round,
)


def _new_game() -> GameState:
    return GameState(
        room_id="room-1",
        players={
            Position.NORTH: "alice",
            Position.EAST: "bob",
            Position.SOUTH: "carol",
            Position.WEST: "dave",
        },
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=500,
        round=None,
        phase=GamePhase.WAITING,
        winner=None,
        last_result=None,
        messages=[],
    )


def _full_deck() -> list[Card]:
    return [Card(s, r) for s in Suit for r in Rank]


def _rigged_hands_north_has_belote() -> dict[Position, list[Card]]:
    """North gets K+Q of hearts (trump) in the same hand; the rest is dealt arbitrarily."""
    deck = _full_deck()
    king_h = Card(Suit.HEARTS, Rank.KING)
    queen_h = Card(Suit.HEARTS, Rank.QUEEN)
    deck.remove(king_h)
    deck.remove(queen_h)
    north = [king_h, queen_h, *deck[:6]]
    south = deck[6:14]
    east = deck[14:22]
    west = deck[22:30]
    return {
        Position.NORTH: north,
        Position.SOUTH: south,
        Position.EAST: east,
        Position.WEST: west,
    }


def _make_round(hands: dict[Position, list[Card]]) -> RoundState:
    return RoundState(
        number=1,
        dealer=Position.WEST,
        hands=hands,
        phase=GamePhase.BIDDING,
        current_bidder=Position.NORTH,
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


# ---------------------------------------------------------------------------
# Bug 1 — la belote exige que K+Q d'atout soient dans la MEME main
# ---------------------------------------------------------------------------


def test_detect_belote_team_same_player_holds_both_cards():
    hands = {
        Position.NORTH: [Card(Suit.HEARTS, Rank.KING), Card(Suit.HEARTS, Rank.QUEEN)],
        Position.SOUTH: [],
        Position.EAST: [],
        Position.WEST: [],
    }
    assert detect_belote_team(hands, Trump.HEARTS) == Team.NORTH_SOUTH


def test_detect_belote_team_split_between_partners_does_not_count():
    """Roi chez North, Dame chez South (son partenaire) : pas de belote."""
    hands = {
        Position.NORTH: [Card(Suit.HEARTS, Rank.KING)],
        Position.SOUTH: [Card(Suit.HEARTS, Rank.QUEEN)],
        Position.EAST: [],
        Position.WEST: [],
    }
    assert detect_belote_team(hands, Trump.HEARTS) is None


def test_detect_belote_team_cross_team_does_not_count():
    hands = {
        Position.NORTH: [Card(Suit.HEARTS, Rank.KING)],
        Position.SOUTH: [],
        Position.EAST: [],
        Position.WEST: [Card(Suit.HEARTS, Rank.QUEEN)],
    }
    assert detect_belote_team(hands, Trump.HEARTS) is None


def test_detect_belote_team_none_for_no_trump_and_all_trump():
    hands = {
        Position.NORTH: [Card(Suit.HEARTS, Rank.KING), Card(Suit.HEARTS, Rank.QUEEN)],
        Position.SOUTH: [],
        Position.EAST: [],
        Position.WEST: [],
    }
    assert detect_belote_team(hands, Trump.NO_TRUMP) is None
    assert detect_belote_team(hands, Trump.ALL_TRUMP) is None


# ---------------------------------------------------------------------------
# Bug 2 — la belote ne doit être révélée qu'au moment où R ou D est jouée
# ---------------------------------------------------------------------------


def test_belote_team_hidden_in_to_dict_before_any_card_played():
    r = _make_round({})
    r.belote_team = Team.NORTH_SOUTH
    r.belote_king_played = False
    r.belote_queen_played = False
    assert r.to_dict()["belote_team"] is None


def test_belote_team_revealed_once_king_played():
    r = _make_round({})
    r.belote_team = Team.NORTH_SOUTH
    r.belote_king_played = True
    assert r.to_dict()["belote_team"] == "NS"


def test_belote_team_revealed_once_queen_played():
    r = _make_round({})
    r.belote_team = Team.EAST_WEST
    r.belote_queen_played = True
    assert r.to_dict()["belote_team"] == "EW"


def test_start_playing_does_not_leak_belote_before_any_card_is_played():
    game = _new_game()
    game = start_new_round(game)
    assert game.round is not None
    game.round.hands = _rigged_hands_north_has_belote()

    # EAST est le premier enchérisseur (donneur = NORTH) ; il prend à coeur
    game, msg = apply_bid(game, 80, False, Trump.HEARTS)
    assert msg == "ok"
    game, _ = apply_pass(game)
    game, _ = apply_pass(game)
    game, status = apply_pass(game)
    assert status == "playing"

    r = game.round
    assert r is not None
    # Détecté en interne...
    assert r.belote_team == Team.NORTH_SOUTH
    # ...mais pas encore révélé aux clients
    assert r.to_dict()["belote_team"] is None
    assert not any("belote" in m.lower() for m in game.messages)


def test_apply_play_reveals_belote_only_once_a_card_is_played():
    game = _new_game()
    game = start_new_round(game)
    assert game.round is not None
    game.round.hands = _rigged_hands_north_has_belote()
    game, _ = apply_bid(game, 80, False, Trump.HEARTS)
    game, _ = apply_pass(game)
    game, _ = apply_pass(game)
    game, status = apply_pass(game)
    assert status == "playing"

    r = game.round
    assert r is not None
    # Force North à entamer le pli (ouverture de pli : toute carte est légale)
    r.current_player = Position.NORTH
    r.current_trick = Trick()

    game, status = apply_play(game, Card(Suit.HEARTS, Rank.KING))
    assert status == "ok"
    r = game.round
    assert r is not None
    assert r.belote_king_played is True
    assert r.to_dict()["belote_team"] == "NS"
    assert any("Belote" in m for m in game.messages[-3:])
