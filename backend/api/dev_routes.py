"""Routes de développement — enregistrées uniquement si DEVELOPMENT=true dans main.py."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from backend.auth.service import create_token
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.repository import UserRepository

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/autologin/{username}")
async def dev_autologin(
    username: str, pb: PocketBaseClient = Depends(get_pb_client)
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
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=28800,
        path="/",
    )
    return response
