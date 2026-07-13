"""Tests pour backend/store/memory_store.py — GC des rooms abandonnées."""

from __future__ import annotations

import pytest

from backend.store import memory_store as store


@pytest.fixture(autouse=True)
def reset_store():
    store._rooms.clear()
    yield
    store._rooms.clear()


async def test_reap_stale_rooms_removes_old_room():
    game = await store.create_room("OLD")
    game.last_activity -= 7 * 3600  # plus vieux que le TTL de test (6h)

    reaped = await store.reap_stale_rooms(max_age_seconds=6 * 3600)

    assert reaped == 1
    assert await store.get_game("OLD") is None


async def test_reap_stale_rooms_keeps_recent_room():
    await store.create_room("FRESH")

    reaped = await store.reap_stale_rooms(max_age_seconds=6 * 3600)

    assert reaped == 0
    assert await store.get_game("FRESH") is not None
