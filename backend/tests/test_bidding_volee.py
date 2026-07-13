"""Tests pour le coinche "à la volée" : un adversaire peut coincher l'enchère
en cours à tout moment, même hors tour, tant qu'elle n'est pas déjà coinchée."""

from __future__ import annotations

from backend.api import websocket as ws_module
from backend.game.models import (
    Double,
    GamePhase,
    GameState,
    Position,
    Team,
    Trump,
)
from backend.game.rules import (
    apply_bid,
    apply_contre,
    get_legal_bid_actions,
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


def _game_with_open_bid() -> GameState:
    """Donneur NORTH, EAST (EW) annonce 80 à Cœur → tour passe à SOUTH."""
    game = _new_game()
    game = start_new_round(game)
    game, status = apply_bid(game, 80, False, Trump.HEARTS)
    assert status == "ok"
    assert game.round is not None
    assert game.round.current_bidder == Position.SOUTH
    return game


# ── game/rules.py — logique pure ────────────────────────────────────────────


def test_can_contre_true_for_opposing_team_even_out_of_turn():
    game = _game_with_open_bid()
    assert game.round is not None
    actions_north = get_legal_bid_actions(game.round, Position.NORTH)
    assert actions_north["can_contre"] is True


def test_cannot_contre_own_teams_bid_even_out_of_turn():
    game = _game_with_open_bid()
    assert game.round is not None
    actions_west = get_legal_bid_actions(game.round, Position.WEST)
    assert actions_west["can_contre"] is False


def test_apply_contre_by_out_of_turn_player_sets_double_and_history():
    game = _game_with_open_bid()
    game, status = apply_contre(game, Position.NORTH)
    assert status == "ok"
    assert game.round is not None
    assert game.round.contract is not None
    assert game.round.contract.double == Double.CONTRE
    assert game.round.bid_history[-1].position == Position.NORTH
    assert game.round.bid_history[-1].action == "contre"


def test_apply_contre_out_of_turn_resumes_bidding_after_the_actor():
    game = _game_with_open_bid()
    game, _ = apply_contre(game, Position.NORTH)
    assert game.round is not None
    assert game.round.current_bidder == Position.EAST


def test_can_contre_closes_once_already_contred():
    game = _game_with_open_bid()
    game, _ = apply_contre(game, Position.NORTH)
    assert game.round is not None
    actions_south = get_legal_bid_actions(game.round, Position.SOUTH)
    assert actions_south["can_contre"] is False


# ── api/websocket.py — dispatch (bypass du tour) ────────────────────────────


async def test_dispatch_allows_contre_out_of_turn():
    game = _game_with_open_bid()
    game, error = await ws_module._dispatch(
        game, Position.NORTH, {"type": "contre"}, "room-1"
    )
    assert error is None
    assert game.round is not None
    assert game.round.contract is not None
    assert game.round.contract.double == Double.CONTRE


async def test_dispatch_rejects_contre_from_bidding_team_out_of_turn():
    game = _game_with_open_bid()
    game, error = await ws_module._dispatch(
        game, Position.WEST, {"type": "contre"}, "room-1"
    )
    assert error == "Contre non autorisé"
    assert game.round is not None
    assert game.round.contract is not None
    assert game.round.contract.double == Double.NONE


def test_state_for_player_exposes_can_contre_volee_to_opponent():
    game = _game_with_open_bid()
    state = ws_module._state_for_player(game, Position.NORTH)
    assert state["round"]["can_contre_volee"] is True
    assert "legal_bid_actions" not in state["round"]


def test_state_for_player_hides_can_contre_volee_from_bidding_team():
    game = _game_with_open_bid()
    state = ws_module._state_for_player(game, Position.WEST)
    assert state["round"].get("can_contre_volee") is False


def test_state_for_player_current_bidder_keeps_normal_legal_bid_actions():
    game = _game_with_open_bid()
    state = ws_module._state_for_player(game, Position.SOUTH)
    assert state["round"]["legal_bid_actions"]["can_contre"] is True
    assert "can_contre_volee" not in state["round"]
