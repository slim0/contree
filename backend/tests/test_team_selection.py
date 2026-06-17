"""Tests for team selection (choose_team / start_game) in the waiting room."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.game.models import GameState, GamePhase, Position, Team
from backend.api import websocket as ws_module
from backend.store import memory_store as store
from backend.main import app


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
    game2, error, close_all = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "choose_team", "team": "NS"}, "r"
    )
    assert error is None
    assert not close_all
    assert game2.team_choices["N"] == "NS"


async def test_choose_team_stores_ew():
    game = _waiting_game()
    game2, error, close_all = await ws_module._dispatch_waiting(
        game, Position.EAST, {"type": "choose_team", "team": "EW"}, "r"
    )
    assert error is None
    assert not close_all
    assert game2.team_choices["E"] == "EW"


async def test_choose_team_invalid_value_returns_error():
    game = _waiting_game()
    _, error, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "choose_team", "team": "BLEU"}, "r"
    )
    assert error is not None


async def test_start_game_requires_4_players():
    game = _waiting_game(n_players=3)
    game.team_choices = {"N": "NS", "E": "EW", "S": "NS"}
    _, error, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None
    assert "4 joueurs" in error


async def test_start_game_requires_balanced_teams_3_1():
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "NS", "S": "NS", "W": "EW"}
    _, error, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None


async def test_start_game_requires_all_players_to_have_chosen():
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "EW"}  # S et W n'ont pas choisi
    _, error, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )
    assert error is not None


async def test_start_game_valid_sets_ready_to_start_and_reassigns():
    """Avec 2 NS et 2 EW, le GO réassigne les positions et retourne close_all=True."""
    game = _waiting_game()
    # N=Player1 (EW), E=Player2 (NS), S=Player3 (NS), W=Player4 (EW)
    game.team_choices = {"N": "EW", "E": "NS", "S": "NS", "W": "EW"}

    game2, error, close_all = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )

    assert error is None
    assert close_all is True
    assert game2.ready_to_start is True
    assert game2.team_choices == {}

    ns_names = {game2.players[Position.NORTH], game2.players[Position.SOUTH]}
    ew_names = {game2.players[Position.EAST], game2.players[Position.WEST]}
    assert ns_names == {"Player2", "Player3"}
    assert ew_names == {"Player1", "Player4"}


async def test_start_game_already_balanced_default_positions():
    """Cas nominal : N,S → NOUS ; E,W → EUX (positions inchangées)."""
    game = _waiting_game()
    game.team_choices = {"N": "NS", "E": "EW", "S": "NS", "W": "EW"}

    game2, error, close_all = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "start_game"}, "r"
    )

    assert error is None
    assert close_all is True
    ns_names = {game2.players[Position.NORTH], game2.players[Position.SOUTH]}
    ew_names = {game2.players[Position.EAST], game2.players[Position.WEST]}
    assert ns_names == {"Player1", "Player3"}
    assert ew_names == {"Player2", "Player4"}


async def test_unknown_action_returns_error():
    game = _waiting_game()
    _, error, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "play", "suit": "H", "rank": "A"}, "r"
    )
    assert error is not None


# ── Integration tests ─────────────────────────────────────────────────────────

def test_choose_team_broadcast_to_all():
    """Après choose_team, tous les joueurs connectés reçoivent team_choices mis à jour."""
    client = TestClient(app)
    with client.websocket_connect("/ws/room-ct/Alice") as ws_alice:
        ws_alice.receive_json()  # state initial

        with client.websocket_connect("/ws/room-ct/Bob") as ws_bob:
            ws_bob.receive_json()   # state initial Bob
            ws_alice.receive_json() # broadcast Alice (Bob vient d'arriver)

            ws_alice.send_json({"type": "choose_team", "team": "NS"})

            # Les deux reçoivent l'état mis à jour
            state_alice = ws_alice.receive_json()
            state_bob = ws_bob.receive_json()

    assert state_alice["type"] == "state"
    assert state_alice["data"]["team_choices"]["N"] == "NS"
    assert state_bob["type"] == "state"
    assert state_bob["data"]["team_choices"]["N"] == "NS"


def test_start_game_rejected_without_balance():
    """start_game avec déséquilibre d'équipes retourne une erreur WS."""
    client = TestClient(app)
    with client.websocket_connect("/ws/room-sg/Alice") as ws:
        ws.receive_json()  # state initial
        ws.send_json({"type": "start_game"})
        ws.receive_json()  # broadcast state (pas de changement)
        err = ws.receive_json()  # message d'erreur
    assert err["type"] == "error"
    assert "4 joueurs" in err["message"]
