"""Tests pour l'action 'leave' en salle d'attente."""

from __future__ import annotations

import json

import pytest

from backend.api import websocket as ws_module
from backend.game.models import GamePhase, GameState, Position, Team
from backend.store import memory_store as store
from backend.tests.conftest import TEST_USER, TEST_USER2


def _make_waiting_room(room_id: str, players: dict[Position, str]) -> GameState:
    return GameState(
        room_id=room_id,
        players=dict(players),
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=GamePhase.WAITING,
        winner=None,
        last_result=None,
        messages=[],
    )


@pytest.fixture(autouse=True)
def reset_global_state():
    ws_module._connections.clear()
    store._rooms.clear()
    yield
    ws_module._connections.clear()
    store._rooms.clear()


# ── Unit: _dispatch_waiting avec action "leave" ────────────────────────────────


async def test_leave_removes_player_from_game():
    game = _make_waiting_room("r", {Position.NORTH: "Alice", Position.EAST: "Bob"})
    game.team_choices = {"N": "NS", "E": "EW"}

    result_game, error, close_all, leave_self = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "leave"}, "r"
    )

    assert error is None
    assert close_all is False
    assert leave_self is True
    assert Position.NORTH not in result_game.players
    assert "N" not in result_game.team_choices
    assert Position.EAST in result_game.players


async def test_leave_adds_message_to_game():
    game = _make_waiting_room("r", {Position.NORTH: "Alice"})

    result_game, _, _, _ = await ws_module._dispatch_waiting(
        game, Position.NORTH, {"type": "leave"}, "r"
    )

    assert any("Alice" in m and "quitté" in m for m in result_game.messages)


# ── Integration: leave via WebSocket ──────────────────────────────────────────


def test_player_can_leave_waiting_room(auth_client):
    """Le joueur reçoit 'left' et sa connexion est fermée proprement."""
    room_id = "room-leave"
    store._rooms[room_id] = _make_waiting_room(room_id, {Position.NORTH: TEST_USER})

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws:
        state_msg = ws.receive_json()
        assert state_msg["type"] == "state"

        ws.send_text(json.dumps({"type": "leave"}))
        left_msg = ws.receive_json()
        assert left_msg["type"] == "left"

    # La room doit être supprimée car plus aucun joueur
    assert room_id not in store._rooms


def test_leave_frees_slot_for_other_players(auth_client, auth_client2):
    """Après le départ d'un joueur, les joueurs restants reçoivent l'état mis à jour."""
    room_id = "room-leave2"
    store._rooms[room_id] = _make_waiting_room(
        room_id,
        {Position.NORTH: TEST_USER, Position.EAST: TEST_USER2},
    )

    with auth_client2.websocket_connect(f"/ws/{room_id}") as ws2:
        ws2.receive_json()  # state initial pour ws2

        with auth_client.websocket_connect(f"/ws/{room_id}") as ws1:
            ws1.receive_json()  # state initial pour ws1
            ws2.receive_json()  # broadcast envoyé à ws2 lors de la connexion de ws1

            ws1.send_text(json.dumps({"type": "leave"}))

            left_msg = ws1.receive_json()
            assert left_msg["type"] == "left"

            # ws2 doit avoir reçu un broadcast avec le joueur retiré
            updated_msg = ws2.receive_json()
            assert updated_msg["type"] == "state"
            assert TEST_USER not in updated_msg["data"]["players"].values()
            assert TEST_USER2 in updated_msg["data"]["players"].values()

        # La room doit toujours exister (ws2 est encore connecté)
        assert room_id in store._rooms
