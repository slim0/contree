from fastapi import APIRouter
from backend.store import memory_store as store

router = APIRouter()


@router.post("/rooms/{room_id}")
async def create_room(room_id: str, target_score: int = 1000):
    game = await store.get_game(room_id)
    if game:
        return {"room_id": room_id, "status": "exists", "players": len(game.players)}
    game = await store.create_room(room_id, target_score)
    return {"room_id": room_id, "status": "created", "target_score": target_score}


@router.get("/rooms")
async def list_rooms():
    return {"rooms": await store.list_rooms()}


@router.get("/rooms/{room_id}")
async def get_room(room_id: str):
    game = await store.get_game(room_id)
    if not game:
        return {"error": "Salon introuvable"}
    return {
        "room_id": room_id,
        "phase": game.phase.value,
        "players": {p.value: n for p, n in game.players.items()},
        "scores": {t.value: s for t, s in game.scores.items()},
    }
