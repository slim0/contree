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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_waiting_room(room_id: str, players: dict[Position, str]) -> GameState:
    """Build a minimal GameState in WAITING phase (no round started yet)."""
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
    """Isolate tests by clearing shared module-level state before each test."""
    ws_module._connections.clear()
    store._rooms.clear()
    yield
    ws_module._connections.clear()
    store._rooms.clear()


# ── 1. Unit tests: conn_id guard ──────────────────────────────────────────────

async def test_register_returns_unique_conn_ids():
    """Each _register call must produce a distinct ID."""
    ws_a = AsyncMock()
    ws_b = AsyncMock()
    id_a = await ws_module._register("r", Position.NORTH, ws_a)
    id_b = await ws_module._register("r", Position.SOUTH, ws_b)
    assert id_a != id_b


async def test_unregister_with_correct_id_removes_entry():
    """_unregister removes the connection when the conn_id matches."""
    ws = AsyncMock()
    conn_id = await ws_module._register("r", Position.NORTH, ws)
    await ws_module._unregister("r", Position.NORTH, conn_id)

    async with ws_module._conn_lock:
        assert Position.NORTH.value not in ws_module._connections.get("r", {})


async def test_unregister_with_stale_id_does_not_evict_new_connection():
    """A stale disconnect handler (old conn_id) must NOT evict the newer connection.

    This is the core regression guard: without conn_id tracking, the old WS
    handler's _unregister call would remove the new connection from _connections,
    making the game invisible to the reconnected player.
    """
    ws_old = AsyncMock()
    ws_new = AsyncMock()

    old_id = await ws_module._register("r", Position.NORTH, ws_old)
    new_id = await ws_module._register("r", Position.NORTH, ws_new)  # overwrites

    # Simulate the old handler finally receiving WebSocketDisconnect and calling
    # _unregister with its (now stale) conn_id.
    await ws_module._unregister("r", Position.NORTH, old_id)

    async with ws_module._conn_lock:
        entry = ws_module._connections.get("r", {}).get(Position.NORTH.value)

    assert entry is not None, "New connection must survive stale _unregister"
    assert entry[0] is ws_new
    assert entry[1] == new_id


# ── 2. Integration: clean reconnect ──────────────────────────────────────────

def test_player_can_reconnect_after_clean_disconnect():
    """Player connects, disconnects cleanly, then reconnects — must succeed."""
    client = TestClient(app)

    with client.websocket_connect("/ws/room-rc/Alice") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["data"]["players"]["N"] == "Alice"
    # WS is now closed; _unregister was called inside WebSocketDisconnect handler

    with client.websocket_connect("/ws/room-rc/Alice") as ws2:
        msg2 = ws2.receive_json()
        assert msg2["type"] == "state"
        assert msg2["data"]["players"]["N"] == "Alice"


# ── 3. Integration: zombie kick ───────────────────────────────────────────────

def test_zombie_connection_is_kicked_on_reconnect():
    """When a zombie WS is still in _connections, a new connection kicks it.

    This reproduces the original bug: after a network drop (no clean close frame),
    the backend kept the stale connection in _connections. Any reconnect attempt
    was rejected. Now the backend closes the old WS and accepts the new one.
    """
    zombie_ws = MagicMock()
    zombie_ws.close = AsyncMock()

    # Plant a zombie directly (simulates a stale connection after a network drop)
    room_id = "room-zombie"
    store._rooms[room_id] = _make_waiting_room(room_id, {Position.NORTH: "Bob"})
    ws_module._connections[room_id] = {Position.NORTH.value: (zombie_ws, 99)}

    client = TestClient(app)
    with client.websocket_connect(f"/ws/{room_id}/Bob") as ws:
        msg = ws.receive_json()
        # New connection must be accepted — no "Ce pseudo est déjà en jeu." error
        assert msg["type"] == "state"
        assert msg["data"]["players"]["N"] == "Bob"

    zombie_ws.close.assert_awaited_once()
