import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.limiter import limiter
from backend.api.websocket import close_room
from backend.auth.dependencies import get_current_user
from backend.store import memory_store as store
from backend.users.models import User

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/rooms/{room_id}")
@limiter.limit("10/minute")
async def create_room(request: Request, room_id: str, target_score: int = 1000):
    game = await store.get_game(room_id)
    if game:
        return {"room_id": room_id, "status": "exists", "players": len(game.players)}
    game = await store.create_room(room_id, target_score)
    return {"room_id": room_id, "status": "created", "target_score": target_score}


@router.get("/rooms")
@limiter.limit("60/minute")
async def list_rooms(request: Request):
    return {"rooms": await store.list_rooms()}


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_room(
    request: Request,
    room_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Supprime un salon : réservé à son créateur et aux admins.

    Autorisé à toute phase, partie en cours comprise — les joueurs connectés
    sont éjectés vers le lobby avec un message `room_closed`.
    """
    game = await store.get_game(room_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Salon introuvable"
        )
    if not current_user.is_admin and game.creator != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le créateur du salon peut le supprimer",
        )
    log.info("Salon '%s' — suppression demandée par %s", room_id, current_user.username)
    await close_room(room_id)


@router.get("/rooms/{room_id}")
@limiter.limit("60/minute")
async def get_room(request: Request, room_id: str):
    game = await store.get_game(room_id)
    if not game:
        return {"error": "Salon introuvable"}
    return {
        "room_id": room_id,
        "phase": game.phase.value,
        "players": {p.value: n for p, n in game.players.items()},
        "scores": {t.value: s for t, s in game.scores.items()},
    }
