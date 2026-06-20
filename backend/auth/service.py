import os
import secrets
import string
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "change-me-in-production-use-a-long-random-string"
)
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_token(
    user_id: int, username: str, is_admin: bool, must_change_password: bool
) -> str:
    expire = datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "is_admin": is_admin,
        "must_change_password": must_change_password,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
