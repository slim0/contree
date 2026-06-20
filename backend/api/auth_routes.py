from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.api.limiter import limiter
from backend.auth.dependencies import get_current_user
from backend.auth.schemas import ChangePasswordRequest, LoginRequest, UserInfo
from backend.auth.service import TOKEN_EXPIRE_HOURS, create_token, hash_password, verify_password
from backend.db.database import get_db
from backend.db.models import User
from backend.users.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_MAX_AGE = TOKEN_EXPIRE_HOURS * 3600


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/login", response_model=UserInfo)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserInfo:
    repo = UserRepository(db)
    user = repo.get_by_username(body.username)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    token = create_token(user.id, user.username, user.is_admin, user.must_change_password)
    _set_auth_cookie(response, token)
    return UserInfo(username=user.username, is_admin=user.is_admin, must_change_password=user.must_change_password)


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response) -> dict:
    response.delete_cookie(key="access_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserInfo)
@limiter.limit("60/minute")
async def me(request: Request, current_user: User = Depends(get_current_user)) -> UserInfo:
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
    db: Session = Depends(get_db),
) -> UserInfo:
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ancien mot de passe incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit contenir au moins 8 caractères",
        )
    repo = UserRepository(db)
    user = repo.update_password(current_user, hash_password(body.new_password))
    token = create_token(user.id, user.username, user.is_admin, user.must_change_password)
    _set_auth_cookie(response, token)
    return UserInfo(username=user.username, is_admin=user.is_admin, must_change_password=user.must_change_password)
