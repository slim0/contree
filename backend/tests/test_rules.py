"""Tests sur l'ordre de jeu (sens horaire N -> E -> S -> W -> N)."""

from __future__ import annotations

from backend.game.models import (
    NEXT_DEALER,
    NEXT_PLAYER,
    RIGHT_OF,
    GamePhase,
    GameState,
    Position,
    Team,
)
from backend.game.rules import apply_pass, start_new_round

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
