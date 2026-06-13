"""In-memory game state store with asyncio lock."""
from __future__ import annotations
import asyncio
from typing import Optional
from backend.game.models import GameState, GamePhase, Team, Position


_rooms: dict[str, GameState] = {}
_lock = asyncio.Lock()


async def get_game(room_id: str) -> Optional[GameState]:
    async with _lock:
        return _rooms.get(room_id)


async def set_game(game: GameState) -> None:
    async with _lock:
        _rooms[game.room_id] = game


async def create_room(room_id: str, target_score: int = 1000) -> GameState:
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
        )
        _rooms[room_id] = game
        return game


async def join_room(room_id: str, player_name: str) -> tuple[Optional[GameState], Optional[Position]]:
    """Add a player to the room. Returns (game, assigned_position) or (None, None) if full."""
    async with _lock:
        game = _rooms.get(room_id)
        if game is None:
            return None, None

        taken = set(game.players.keys())
        for pos in [Position.NORTH, Position.EAST, Position.SOUTH, Position.WEST]:
            if pos not in taken:
                game.players[pos] = player_name
                game.messages.append(f"{player_name} rejoint la partie en position {pos.value}")
                return game, pos

        return game, None  # room full


async def list_rooms() -> list[str]:
    async with _lock:
        return list(_rooms.keys())
