"""Tests pour la signalisation WebRTC (chat vocal) en salle d'attente."""

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


def test_webrtc_offer_relayed_while_waiting(auth_client, auth_client2):
    """Le salon (phase WAITING) doit relayer la signalisation WebRTC au pair visé."""
    room_id = "room-voice"
    store._rooms[room_id] = _make_waiting_room(
        room_id,
        {Position.NORTH: TEST_USER, Position.EAST: TEST_USER2},
    )

    with auth_client2.websocket_connect(f"/ws/{room_id}") as ws2:
        ws2.receive_json()  # state initial pour ws2

        with auth_client.websocket_connect(f"/ws/{room_id}") as ws1:
            ws1.receive_json()  # state initial pour ws1
            ws2.receive_json()  # broadcast envoyé à ws2 lors de la connexion de ws1

            ws1.send_text(
                json.dumps(
                    {
                        "type": "webrtc-offer",
                        "peer_position": "E",
                        "data": {"sdp": "fake-sdp"},
                    }
                )
            )

            relayed = ws2.receive_json()
            assert relayed["type"] == "voice-webrtc-offer"
            assert relayed["from"] == "N"
            assert relayed["data"] == {"sdp": "fake-sdp"}
