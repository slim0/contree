"""Tests de suppression d'un salon par son créateur ou par un admin."""

from __future__ import annotations

import json

import pytest

from backend.api import websocket as ws_module
from backend.game.models import GamePhase, GameState, Position, Team
from backend.store import memory_store as store
from backend.tests.conftest import TEST_USER, TEST_USER2


def _make_room(
    room_id: str,
    creator: str,
    players: dict[Position, str] | None = None,
    phase: GamePhase = GamePhase.WAITING,
) -> GameState:
    game = GameState(
        room_id=room_id,
        players=dict(players or {Position.NORTH: creator}),
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=phase,
        winner=None,
        last_result=None,
        messages=[],
        room_name=f"Salon de {creator}",
    )
    game.creator = creator
    return game


@pytest.fixture(autouse=True)
def reset_global_state():
    ws_module._connections.clear()
    ws_module._voice_peers.clear()
    store._rooms.clear()
    yield
    ws_module._connections.clear()
    ws_module._voice_peers.clear()
    store._rooms.clear()


class _FakeWebSocket:
    """Socket minimale pour tester `close_room` sans passer par le réseau."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self) -> None:
        self.closed = True


# ── Unit : close_room ─────────────────────────────────────────────────────────


async def test_close_room_ejects_clients_and_deletes_state():
    room_id = "room-close"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)
    fake_ws = _FakeWebSocket()
    await ws_module._register(room_id, Position.NORTH, fake_ws)  # ty: ignore[invalid-argument-type]
    await ws_module._init_voice_peers(room_id, Position.NORTH)

    await ws_module.close_room(room_id)

    assert room_id not in store._rooms
    assert fake_ws.sent == [
        {"type": "room_closed", "message": "Le salon a été supprimé."}
    ]
    assert fake_ws.closed is True
    assert room_id not in ws_module._connections
    assert room_id not in ws_module._voice_peers


async def test_close_room_on_unknown_room_is_noop():
    await ws_module.close_room("room-inconnue")  # ne doit pas lever


# ── HTTP : DELETE /api/rooms/{room_id} ────────────────────────────────────────


def test_creator_can_delete_own_room(auth_client):
    room_id = "room-del-creator"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)

    r = auth_client.delete(f"/api/rooms/{room_id}")

    assert r.status_code == 204
    assert room_id not in store._rooms


def test_non_creator_cannot_delete_room(auth_client2):
    room_id = "room-del-forbidden"
    store._rooms[room_id] = _make_room(
        room_id, TEST_USER, {Position.NORTH: TEST_USER, Position.EAST: TEST_USER2}
    )

    r = auth_client2.delete(f"/api/rooms/{room_id}")

    assert r.status_code == 403
    assert room_id in store._rooms


def test_admin_can_delete_any_room(admin_client):
    room_id = "room-del-admin"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)

    r = admin_client.delete(f"/api/rooms/{room_id}")

    assert r.status_code == 204
    assert room_id not in store._rooms


def test_delete_unknown_room_returns_404(auth_client):
    r = auth_client.delete("/api/rooms/room-inexistante")
    assert r.status_code == 404


def test_delete_requires_authentication(client):
    room_id = "room-del-anon"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)

    r = client.delete(f"/api/rooms/{room_id}")

    assert r.status_code == 401
    assert room_id in store._rooms


def test_creator_can_delete_room_during_game(auth_client):
    """Choix produit : la suppression est autorisée même partie en cours."""
    room_id = "room-del-playing"
    store._rooms[room_id] = _make_room(room_id, TEST_USER, phase=GamePhase.PLAYING)

    r = auth_client.delete(f"/api/rooms/{room_id}")

    assert r.status_code == 204
    assert room_id not in store._rooms


def test_deleted_room_disappears_from_lobby_list(auth_client):
    room_id = "room-del-lobby"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)

    listed = auth_client.get("/api/rooms").json()["rooms"]
    assert [room["room_id"] for room in listed] == [room_id]
    assert listed[0]["creator"] == TEST_USER

    auth_client.delete(f"/api/rooms/{room_id}")

    assert auth_client.get("/api/rooms").json()["rooms"] == []


def test_connected_player_is_ejected_on_delete(auth_client):
    """Bout en bout : socket réelle ouverte → suppression → message room_closed."""
    room_id = "room-del-ws"
    store._rooms[room_id] = _make_room(room_id, TEST_USER)

    with auth_client.websocket_connect(f"/ws/{room_id}") as ws:
        assert ws.receive_json()["type"] == "state"

        assert auth_client.delete(f"/api/rooms/{room_id}").status_code == 204

        msg = ws.receive_json()
        assert msg["type"] == "room_closed"
        assert msg["message"] == "Le salon a été supprimé."

    assert room_id not in store._rooms
    assert room_id not in ws_module._connections


# ── HTTP : GET /api/admin/rooms ───────────────────────────────────────────────


def test_admin_lists_all_rooms_including_finished(admin_client):
    store._rooms["room-a"] = _make_room("room-a", TEST_USER)
    store._rooms["room-b"] = _make_room(
        "room-b",
        TEST_USER2,
        {Position.NORTH: TEST_USER2, Position.SOUTH: TEST_USER},
        phase=GamePhase.FINISHED,
    )

    r = admin_client.get("/api/admin/rooms")

    assert r.status_code == 200
    rooms = {room["room_id"]: room for room in r.json()["rooms"]}
    assert set(rooms) == {"room-a", "room-b"}
    assert rooms["room-a"]["creator"] == TEST_USER
    assert rooms["room-b"]["phase"] == "FINISHED"
    assert rooms["room-b"]["player_count"] == 2
    assert rooms["room-b"]["players"] == [TEST_USER2, TEST_USER]


def test_admin_rooms_forbidden_for_regular_user(auth_client):
    r = auth_client.get("/api/admin/rooms")
    assert r.status_code == 403
