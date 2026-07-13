"""Routes de développement — enregistrées uniquement si DEVELOPMENT=true dans main.py."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from backend.api.limiter import limiter
from backend.auth.service import create_token, set_auth_cookie
from backend.game import rules
from backend.game.models import GamePhase, Position
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.store import memory_store as store
from backend.users.repository import UserRepository

router = APIRouter(prefix="/dev", tags=["dev"])

DEFAULT_QUICKSTART_PLAYERS = "alice,bob,charlie,diana"


@router.get("/autologin/{username}")
@limiter.limit("10/minute")
async def dev_autologin(
    request: Request,
    username: str,
    room: str | None = None,
    pb: PocketBaseClient = Depends(get_pb_client),
) -> RedirectResponse:
    repo = UserRepository(pb)
    user = repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Utilisateur '{username}' introuvable — lancez d'abord le seed",
        )
    token = create_token(
        user.id, user.username, user.is_admin, user.must_change_password
    )
    target = f"/?room={room}" if room else "/"
    response = RedirectResponse(url=target, status_code=302)
    set_auth_cookie(response, token)
    return response


@router.post("/quickstart/{room_id}")
@limiter.limit("10/minute")
async def dev_quickstart(
    request: Request,
    room_id: str,
    players: str = DEFAULT_QUICKSTART_PLAYERS,
    target_score: int = 1000,
) -> dict:
    """Crée un salon de test, assigne 4 joueurs (2 équipes) et démarre la 1re manche
    directement — sans passer par la salle d'attente ni le choix des équipes.

    `players` est une liste de 4 noms séparés par des virgules : les deux premiers
    forment l'équipe NOUS (N/S), les deux derniers l'équipe EUX (E/W).
    """
    names = [n.strip() for n in players.split(",") if n.strip()]
    if len(names) != 4:
        raise HTTPException(
            status_code=400,
            detail="Il faut exactement 4 joueurs (séparés par des virgules)",
        )

    game = await store.create_room(room_id, target_score, room_name="Salon de test")
    game.players = {
        Position.NORTH: names[0],
        Position.SOUTH: names[1],
        Position.EAST: names[2],
        Position.WEST: names[3],
    }
    game = rules.start_new_round(game)
    game.phase = GamePhase.BIDDING
    await store.set_game(game)

    return {
        "room_id": room_id,
        "players": {pos.value: name for pos, name in game.players.items()},
        "target_score": target_score,
    }
