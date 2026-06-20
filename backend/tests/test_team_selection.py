"""Tests for team selection (choose_team / start_game) in the waiting room."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.game.models import GameState, GamePhase, Position, Team
from backend.api import websocket as ws_module
from backend.store import memory_store as store
from backend.main import app
from backend.tests.conftest import TEST_ADMIN, TEST_USER


# ── Helpers ───────────────────────────────────────────────────────────────────

def _waiting_game(room_id: str = "r", n_players: int = 4) -> GameState:
    positions = [Position.NORTH, Position.EAST, Position.SOUTH, Position.WEST]
    players = {positions[i]: f"Player{i + 1}" for i in range(n_players)}
    return GameState(
        room_id=room_id,
        players=players,
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=GamePhase.WAITING,
        winner=None,
        last_result=None,
        messages=[],
    )


@pytest.fixture(autouse=True)
def reset_state():
    ws_module._connections.clear()
    ws_module._closing_for_start.clear()
    store._rooms.clear()
    yield
    ws_module._connections.clear()
    ws_module._closing_for_start.clear()
    store._rooms.clear()


# ── Unit tests: _dispatch_waiting ─────────────────────────────────────────────

async def test_choose_team_stores_ns():
    game = _waiting_game()
    game2, error, close_all, leave_self = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "choose_team", "team": "NS"}, "r"
    )
    assert error is None
    assert not close_all
    assert not leave_self
    assert game2.team_choices["N"] == "NS"


async def test_choose_team_stores_ew():
    game = _waiting_game()
    game2, error, close_all, leave_self = await ws_module._dispatch_waiting(
        game, Position.EAST, {"type": "choose_team", "team": "EW"}, "r"
    )
    assert error is None
    assert not close_all
    assert not leave_self
    assert game2.team_choices["E"] == "EW"


async def test_choose_team_invalid_value_returns_error():
    game = _waiting_game()
    _, error, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "choose_team", "team": "BLEU"}, "r"
    )
    assert error is not None


async def test_start_game_requires_4_players():
    game = _waiting_game(n_players=3)
    game.team_choices = {"N": "NS", "E": "EW", "S": "NS"}
    _, error, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None
    assert "4 joueurs" in error


async def test_start_game_requires_balanced_teams_3_1():
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "NS", "S": "NS", "W": "EW"}
    _, error, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None


async def test_start_game_requires_all_players_to_have_chosen():
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "EW"}
    _, error, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None


async def test_start_game_valid_sets_ready_to_start_and_reassigns():
    game = _waiting_game()
    game.team_choices = {"N": "EW", "E": "NS", "S": "NS", "W": "EW"}

    game2, error, close_all, leave_self = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )

    assert error is None
    assert close_all is True
    assert leave_self is False
    assert game2.ready_to_start is True
    assert game2.team_choices == {}

    ns_names = {game2.players[Position.NORTH], game2.players[Position.SOUTH]}
    ew_names = {game2.players[Position.EAST], game2.players[Position.WEST]}
    assert ns_names == {"Player2", "Player3"}
    assert ew_names == {"Player1", "Player4"}


async def test_start_game_already_balanced_default_positions():
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "EW", "S": "NS", "W": "EW"}

    game2, error, close_all, leave_self = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )

    assert error is None
    assert close_all is True
    assert leave_self is False
    ns_names = {game2.players[Position.NORTH], game2.players[Position.SOUTH]}
    ew_names = {game2.players[Position.EAST], game2.players[Position.WEST]}
    assert ns_names == {"Player1", "Player3"}
    assert ew_names == {"Player2", "Player4"}


async def test_unknown_action_returns_error():
    game = _waiting_game()
    _, error, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "play", "suit": "H", "rank": "A"}, "r"
    )
    assert error is not None


# ── Integration tests ─────────────────────────────────────────────────────────

def test_choose_team_broadcast_to_all(auth_client, auth_client2):
    """Après choose_team, les deux joueurs connectés reçoivent team_choices mis à jour."""
    from backend.tests.conftest import TEST_USER, TEST_USER2
    room_id = "room-ct"
    store._rooms[room_id] = _waiting_game(room_id, n_players=0)
    store._rooms[room_id].players = {}

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws1:
        ws1.receive_json()  # état initial testuser
        with auth_client2.websocket_connect(f"/ws/{room_id}") as ws2:
            ws2.receive_json()   # état initial testuser2
            ws1.receive_json()   # broadcast testuser (testuser2 vient d'arriver)

            ws1.send_json({"type": "choose_team", "team": "NS"})

            state1 = ws1.receive_json()
            state2 = ws2.receive_json()

    assert state1["type"] == "state"
    assert state2["type"] == "state"
    # testuser est en position N (premier arrivé), vérifie son choix d'équipe
    pos1 = state1["data"]["my_position"]
    assert state1["data"]["team_choices"][pos1] == "NS"
    assert state2["data"]["team_choices"][pos1] == "NS"


def test_start_game_rejected_without_balance(auth_client):
    """start_game avec déséquilibre d'équipes retourne une erreur WS."""
    room_id = "room-sg"
    store._rooms[room_id] = _waiting_game(room_id, n_players=0)
    store._rooms[room_id].players = {}

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws:
        ws.receive_json()  # état initial
        ws.send_json({"type": "start_game"})
        ws.receive_json()  # broadcast state
        err = ws.receive_json()  # message d'erreur
    assert err["type"] == "error"
    assert "4 joueurs" in err["message"]
