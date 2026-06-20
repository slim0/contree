import logging
import sys
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.websocket import handle_connection
from backend.api.auth_routes import router as auth_router
from backend.api.admin_routes import router as admin_router
from backend.auth.service import decode_token, generate_temp_password, hash_password
from backend.db.database import SessionLocal, init_db
from backend.users.repository import UserRepository

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)-30s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
log = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost",         # nginx prod
]


def _bootstrap_admin() -> None:
    """Si aucun utilisateur n'existe, crée un compte admin avec un mot de passe temporaire."""
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        if repo.count() == 0:
            temp = generate_temp_password()
            repo.create("admin", hash_password(temp), is_admin=True, must_change_password=True)
            log.warning("━" * 60)
            log.warning("PREMIER DÉMARRAGE — Compte administrateur créé")
            log.warning("  Identifiant       : admin")
            log.warning("  Mot de passe temp : %s", temp)
            log.warning("  Changez-le dès la première connexion !")
            log.warning("━" * 60)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _bootstrap_admin()
    yield


app = FastAPI(title="Belote Contrée", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    ws: WebSocket,
    room_id: str,
    target_score: int = 1000,
    room_name: str = "",
) -> None:
    token = ws.cookies.get("access_token")
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if payload.get("must_change_password"):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    player_name: str = payload["username"]
    await handle_connection(ws, room_id, player_name, target_score, room_name)
