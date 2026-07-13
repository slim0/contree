"""Tests pour les routes de développement (backend/api/dev_routes.py)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.testclient import TestClient

from backend.api.dev_routes import router as dev_router
from backend.api.limiter import limiter
from backend.game.models import GamePhase, Position
from backend.pocketbase.client import get_pb_client
from backend.store import memory_store as store
from backend.tests.conftest import TEST_USER

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # ty: ignore[invalid-argument-type]
_app.add_middleware(SlowAPIMiddleware)
_app.include_router(dev_router, prefix="/api")


@pytest.fixture(autouse=True)
def reset_store():
    store._rooms.clear()
    yield
    store._rooms.clear()


@pytest.fixture
def dev_client(pb_client):
    _app.dependency_overrides[get_pb_client] = lambda: pb_client
    with TestClient(_app, follow_redirects=False) as c:
        yield c
    _app.dependency_overrides.pop(get_pb_client, None)


# ── /dev/quickstart ──────────────────────────────────────────────────────────


async def test_quickstart_creates_room_and_starts_first_round(dev_client):
    resp = dev_client.post("/api/dev/quickstart/TEST")
    assert resp.status_code == 200
    body = resp.json()
    assert body["room_id"] == "TEST"
    assert body["players"] == {"N": "alice", "S": "bob", "E": "charlie", "W": "diana"}

    game = await store.get_game("TEST")
    assert game is not None
    assert game.phase == GamePhase.BIDDING
    assert game.round is not None
    assert game.round.current_bidder is not None
    assert game.players[Position.NORTH] == "alice"
    assert game.players[Position.WEST] == "diana"


def test_quickstart_rejects_wrong_player_count(dev_client):
    resp = dev_client.post("/api/dev/quickstart/TEST?players=alice,bob,charlie")
    assert resp.status_code == 400


def test_quickstart_accepts_custom_players_and_score(dev_client):
    resp = dev_client.post("/api/dev/quickstart/TEST?players=a,b,c,d&target_score=500")
    assert resp.status_code == 200
    body = resp.json()
    assert body["players"] == {"N": "a", "S": "b", "E": "c", "W": "d"}
    assert body["target_score"] == 500


# ── /dev/autologin ───────────────────────────────────────────────────────────


def test_autologin_redirects_to_root_without_room(dev_client):
    resp = dev_client.get(f"/api/dev/autologin/{TEST_USER}")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
    assert "access_token" in resp.cookies


def test_autologin_redirects_with_room_param(dev_client):
    resp = dev_client.get(f"/api/dev/autologin/{TEST_USER}?room=TEST")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/?room=TEST"
    assert "access_token" in resp.cookies


def test_autologin_unknown_user_404(dev_client):
    resp = dev_client.get("/api/dev/autologin/nobody")
    assert resp.status_code == 404


# ── Rate limiting ────────────────────────────────────────────────────────────


def test_autologin_rate_limit(dev_client):
    for _ in range(10):
        dev_client.get(f"/api/dev/autologin/{TEST_USER}")
    resp = dev_client.get(f"/api/dev/autologin/{TEST_USER}")
    assert resp.status_code == 429


def test_quickstart_rate_limit(dev_client):
    for _ in range(10):
        dev_client.post("/api/dev/quickstart/TEST")
    resp = dev_client.post("/api/dev/quickstart/TEST")
    assert resp.status_code == 429
