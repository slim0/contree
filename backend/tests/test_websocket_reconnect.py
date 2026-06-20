"""Tests for WebSocket reconnection behaviour.

Three scenarios:
  1. conn_id guard — stale disconnect handler must not evict a newer connection.
  2. Clean reconnect — player disconnects cleanly and reconnects successfully.
  3. Zombie reconnect — old WS still active; new connection kicks it and succeeds.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient

from backend.game.models import GameState, GamePhase, Position, Team
from backend.api import websocket as ws_module
from backend.store import memory_store as store
from backend.main import app
from backend.tests.conftest import TEST_USER


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_waiting_room(room_id: str, players: dict[Position, str]) -> GameState:
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


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_global_state():
    """Isole les tests en vidant l'état partagé des modules."""
    ws_module._connections.clear()
    store._rooms.clear()
    yield
    ws_module._connections.clear()
    store._rooms.clear()


# ── 1. Unit tests: conn_id guard ──────────────────────────────────────────────

async def test_register_returns_unique_conn_ids():
    ws_a = AsyncMock()
    ws_b = AsyncMock()
    id_a = await ws_module._register("r", Position.NORTH, ws_a)
    id_b = await ws_module._register("r", Position.SOUTH, ws_b)
    assert id_a != id_b


async def test_unregister_with_correct_id_removes_entry():
    ws = AsyncMock()
    conn_id = await ws_module._register("r", Position.NORTH, ws)
    await ws_module._unregister("r", Position.NORTH, conn_id)

    async with ws_module._conn_lock:
        assert Position.NORTH.value not in ws_module._connections.get("r", {})


async def test_unregister_with_stale_id_does_not_evict_new_connection():
    ws_old = AsyncMock()
    ws_new = AsyncMock()

    old_id = await ws_module._register("r", Position.NORTH, ws_old)
    new_id = await ws_module._register("r", Position.NORTH, ws_new)

    await ws_module._unregister("r", Position.NORTH, old_id)

    async with ws_module._conn_lock:
        entry = ws_module._connections.get("r", {}).get(Position.NORTH.value)

    assert entry is not None, "New connection must survive stale _unregister"
    assert entry[0] is ws_new
    assert entry[1] == new_id


# ── 2. Integration: clean reconnect ──────────────────────────────────────────

def test_player_can_reconnect_after_clean_disconnect(auth_client):
    # Pré-peupler la room pour ne pas dépendre de la création via WS
    room_id = "room-rc"
    store._rooms[room_id] = _make_waiting_room(room_id, {Position.NORTH: TEST_USER})

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["data"]["players"]["N"] == TEST_USER

    # Après déconnexion propre, la room est supprimée (WAITING sans ready_to_start).
    # On la recrée pour simuler un vrai scénario de reconnexion post-partie.
    store._rooms[room_id] = _make_waiting_room(room_id, {Position.NORTH: TEST_USER})

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws2:
        msg2 = ws2.receive_json()
        assert msg2["type"] == "state"
        assert msg2["data"]["players"]["N"] == TEST_USER


# ── 3. Integration: zombie kick ───────────────────────────────────────────────

def test_zombie_connection_is_kicked_on_reconnect(auth_client):
    zombie_ws = MagicMock()
    zombie_ws.close = AsyncMock()

    room_id = "room-zombie"
    store._rooms[room_id] = _make_waiting_room(room_id, {Position.NORTH: TEST_USER})
    ws_module._connections[room_id] = {Position.NORTH.value: (zombie_ws, 99)}

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["data"]["players"]["N"] == TEST_USER

    zombie_ws.close.assert_awaited_once()


# ── 4. Unauthenticated WS is rejected ────────────────────────────────────────

def test_unauthenticated_ws_is_rejected(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/room-unauth") as ws:
            ws.receive_json()


# ── 5. Admin WS is rejected ───────────────────────────────────────────────────

def test_admin_ws_is_rejected(admin_client):
    with pytest.raises(Exception):
        with admin_client.websocket_connect("/ws/room-admin") as ws:
            ws.receive_json()


# ── 6. Regression: joining a non-existent room without room_name returns error ─
# Bug: connecting to an unknown room_id with no room_name was silently creating
# a new room instead of returning an error.

def test_joining_nonexistent_room_without_room_name_returns_error(auth_client):
    """Connecting to an unknown room without providing room_name must fail."""
    with auth_client.websocket_connect("/ws/UNKNOWN") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "introuvable" in msg["message"].lower()

    # The phantom room must NOT have been created
    assert "UNKNOWN" not in store._rooms


def test_joining_nonexistent_room_with_room_name_creates_it(auth_client):
    """Connecting to an unknown room WITH room_name must create the room (creator flow)."""
    with auth_client.websocket_connect("/ws/NEWRM?room_name=Ma+partie") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        # La room doit exister pendant la connexion
        assert "NEWRM" in store._rooms
        assert store._rooms["NEWRM"].room_name == "Ma partie"
