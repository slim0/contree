import os
import secrets
import string
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "change-me-in-production-use-a-long-random-string"
)
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8
COOKIE_MAX_AGE = TOKEN_EXPIRE_HOURS * 3600
# En dev (DEVELOPMENT=true), le front tourne en http:// — un cookie Secure
# serait alors silencieusement ignoré par le navigateur.
_COOKIE_SECURE = os.getenv("DEVELOPMENT", "false").lower() != "true"


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_token(
    user_id: str, username: str, is_admin: bool, must_change_password: bool
) -> str:
    expire = datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "must_change_password": must_change_password,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )
