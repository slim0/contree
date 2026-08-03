"""Tests sur l'ordre de jeu (sens horaire N -> E -> S -> W -> N)."""

from __future__ import annotations

from backend.game.models import (
    NEXT_DEALER,
    NEXT_PLAYER,
    RIGHT_OF,
    Card,
    GamePhase,
    GameState,
    Position,
    Rank,
    Suit,
    Team,
    Trick,
    TrickCard,
    Trump,
)
from backend.game.rules import apply_pass, restart_game, start_new_round, trick_winner

CLOCKWISE_ORDER = [Position.NORTH, Position.EAST, Position.SOUTH, Position.WEST]


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


def test_next_player_follows_clockwise_table_order():
    """E suit N, S suit E, W suit S, N suit W (comme autour d'une vraie table)."""
    for i, pos in enumerate(CLOCKWISE_ORDER):
        expected_next = CLOCKWISE_ORDER[(i + 1) % len(CLOCKWISE_ORDER)]
        assert NEXT_PLAYER[pos] == expected_next
        assert NEXT_DEALER[pos] == expected_next
        assert RIGHT_OF[pos] == expected_next


def test_first_bidder_is_to_the_right_of_the_dealer():
    game = _new_game()
    game = start_new_round(game)
    assert game.round is not None
    assert game.round.dealer == Position.NORTH
    assert game.round.current_bidder == Position.EAST


def test_bidding_order_passes_clockwise_around_the_table():
    game = _new_game()
    game = start_new_round(game)
    assert game.round is not None

    seen_order = [game.round.current_bidder]
    for _ in range(3):
        game, status = apply_pass(game)
        assert status == "ok"
        assert game.round is not None
        seen_order.append(game.round.current_bidder)

    assert seen_order == [
        Position.EAST,
        Position.SOUTH,
        Position.WEST,
        Position.NORTH,
    ]


def _trick(*plays: tuple[Position, Card]) -> Trick:
    return Trick(cards=[TrickCard(pos, card) for pos, card in plays])


def test_all_trump_off_suit_discard_never_wins():
    """Bug repro: en tout atout, une défausse hors couleur ne doit jamais gagner,
    même avec un rang atout plus fort que la carte de couleur demandée."""
    trick = _trick(
        (Position.NORTH, Card(Suit.HEARTS, Rank.KING)),
        (Position.EAST, Card(Suit.DIAMONDS, Rank.JACK)),
    )
    assert trick_winner(trick, Trump.ALL_TRUMP) == Position.NORTH


def test_all_trump_higher_card_of_led_suit_wins():
    trick = _trick(
        (Position.NORTH, Card(Suit.HEARTS, Rank.KING)),
        (Position.EAST, Card(Suit.HEARTS, Rank.JACK)),
    )
    assert trick_winner(trick, Trump.ALL_TRUMP) == Position.EAST


def test_normal_trump_always_beats_led_suit():
    trick = _trick(
        (Position.NORTH, Card(Suit.HEARTS, Rank.ACE)),
        (Position.EAST, Card(Suit.SPADES, Rank.SEVEN)),
    )
    assert trick_winner(trick, Trump.SPADES) == Position.EAST


def test_no_trump_off_suit_card_never_wins():
    trick = _trick(
        (Position.NORTH, Card(Suit.HEARTS, Rank.SEVEN)),
        (Position.EAST, Card(Suit.SPADES, Rank.ACE)),
    )
    assert trick_winner(trick, Trump.NO_TRUMP) == Position.NORTH


def test_dealer_rotates_clockwise_after_a_void_deal():
    game = _new_game()
    game = start_new_round(game)
    assert game.round is not None
    assert game.round.dealer == Position.NORTH

    for _ in range(4):
        game, status = apply_pass(game)

    assert status == "redeal"
    assert game.round is not None
    assert game.round.dealer == Position.EAST


def test_restart_game_resets_scores_and_deals_fresh_round():
    game = _new_game()
    game.bots = {"dave"}
    game = start_new_round(game)  # manche 1
    game = start_new_round(game)  # manche 2 — pour vérifier le retour à 1
    # Simule une partie terminée
    game.scores = {Team.NORTH_SOUTH: 520, Team.EAST_WEST: 310}
    game.winner = Team.NORTH_SOUTH
    game.phase = GamePhase.FINISHED

    restarted = restart_game(game)

    assert restarted.scores == {Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0}
    assert restarted.winner is None
    assert restarted.last_result is None
    assert restarted.phase == GamePhase.BIDDING
    assert restarted.round is not None
    assert restarted.round.number == 1
    assert restarted.round.phase == GamePhase.BIDDING
    # joueurs, équipes et bots conservés
    assert restarted.players == game.players
    assert restarted.bots == {"dave"}
