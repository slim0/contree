"""In-memory game state store with asyncio lock."""

from __future__ import annotations

import asyncio

from backend.game.models import GamePhase, GameState, Position, Team

_rooms: dict[str, GameState] = {}
_lock = asyncio.Lock()


async def get_game(room_id: str) -> GameState | None:
    async with _lock:
        return _rooms.get(room_id)


async def set_game(game: GameState) -> None:
    async with _lock:
        _rooms[game.room_id] = game


async def create_room(
    room_id: str, target_score: int = 1000, room_name: str = ""
) -> GameState:
    async with _lock:
        game = GameState(
            room_id=room_id,
            players={},
            scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
            target_score=target_score,
            round=None,
            phase=GamePhase.WAITING,
            winner=None,
            last_result=None,
            messages=[f"Salon {room_id} créé. Score cible : {target_score}"],
            room_name=room_name,
        )
        _rooms[room_id] = game
        return game


async def join_room(
    room_id: str, player_name: str
) -> tuple[GameState | None, Position | None]:
    """Add a player to the room. Returns (game, assigned_position) or (None, None) if full."""
    async with _lock:
        game = _rooms.get(room_id)
        if game is None:
            return None, None

        taken = set(game.players.keys())
        for pos in [Position.NORTH, Position.EAST, Position.SOUTH, Position.WEST]:
            if pos not in taken:
                game.players[pos] = player_name
                game.messages.append(
                    f"{player_name} rejoint la partie en position {pos.value}"
                )
                return game, pos

        return game, None  # room full


async def delete_room(room_id: str) -> None:
    async with _lock:
        _rooms.pop(room_id, None)


async def list_rooms() -> list[dict]:
    async with _lock:
        result = []
        for game in _rooms.values():
            if game.phase.value == "FINISHED":
                continue
            result.append(
                {
                    "room_id": game.room_id,
                    "room_name": game.room_name,
                    "player_count": len(game.players),
                    "phase": game.phase.value,
                }
            )
        return result
