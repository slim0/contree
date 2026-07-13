from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.api.limiter import limiter
from backend.auth.dependencies import get_current_user
from backend.auth.schemas import ChangePasswordRequest, LoginRequest, UserInfo
from backend.auth.service import create_token, set_auth_cookie
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.models import User
from backend.users.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserInfo)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    pb: PocketBaseClient = Depends(get_pb_client),
) -> UserInfo:
    repo = UserRepository(pb)
    user = repo.verify_credentials(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides"
        )
    token = create_token(
        user.id, user.username, user.is_admin, user.must_change_password
    )
    set_auth_cookie(response, token)
    return UserInfo(
        username=user.username,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
    )


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response) -> dict:
    response.delete_cookie(key="access_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserInfo)
@limiter.limit("60/minute")
async def me(
    request: Request, current_user: User = Depends(get_current_user)
) -> UserInfo:
    return UserInfo(
        username=current_user.username,
        is_admin=current_user.is_admin,
        must_change_password=current_user.must_change_password,
    )


@router.post("/change-password", response_model=UserInfo)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    pb: PocketBaseClient = Depends(get_pb_client),
) -> UserInfo:
    repo = UserRepository(pb)
    if not repo.verify_credentials(current_user.username, body.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ancien mot de passe incorrect",
        )
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit contenir au moins 8 caractères",
        )
    user = repo.update_password(current_user, body.new_password)
    token = create_token(
        user.id, user.username, user.is_admin, user.must_change_password
    )
    set_auth_cookie(response, token)
    return UserInfo(
        username=user.username,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
    )
