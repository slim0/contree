import jwt
from fastapi import Cookie, Depends, HTTPException, status

from backend.auth.service import decode_token
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.models import User
from backend.users.repository import UserRepository


def _payload_from_cookie(access_token: str | None) -> dict:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié"
        )
    try:
        return decode_token(access_token)
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée"
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide"
        ) from err


def get_current_user(
    access_token: str | None = Cookie(default=None),
    pb: PocketBaseClient = Depends(get_pb_client),
) -> User:
    payload = _payload_from_cookie(access_token)
    repo = UserRepository(pb)
    user = repo.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable"
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user
