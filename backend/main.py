import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import FastAPI, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.admin_routes import router as admin_router
from backend.api.auth_routes import router as auth_router
from backend.api.dev_routes import router as dev_router
from backend.api.limiter import limiter
from backend.api.routes import router
from backend.api.users_routes import router as users_router
from backend.api.websocket import handle_connection
from backend.auth.service import decode_token, generate_temp_password
from backend.pocketbase.client import PB_URL, get_pb_client
from backend.store import memory_store
from backend.users.repository import UserRepository

# Rooms sans activité depuis plus longtemps que ça sont considérées abandonnées.
_STALE_ROOM_MAX_AGE_SECONDS = 6 * 3600
_STALE_ROOM_SWEEP_INTERVAL_SECONDS = 30 * 60

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
    "http://localhost",  # nginx prod
]


def _wait_for_pocketbase(timeout: float = 30.0) -> None:
    """Attend que PocketBase réponde avant de démarrer (utile au cold-start Docker)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{PB_URL}/api/health", timeout=2.0)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    log.warning(
        "PocketBase (%s) injoignable après %.0fs — démarrage quand même", PB_URL, timeout
    )


def _bootstrap_admin() -> None:
    """Si aucun utilisateur n'existe, crée un compte admin avec un mot de passe temporaire."""
    repo = UserRepository(get_pb_client())
    if repo.count() == 0:
        temp = generate_temp_password()
        repo.create("admin", temp, is_admin=True, must_change_password=True)
        log.warning("━" * 60)
        log.warning("PREMIER DÉMARRAGE — Compte administrateur créé")
        log.warning("  Identifiant       : admin")
        log.warning("  Mot de passe temp : %s", temp)
        log.warning("  Changez-le dès la première connexion !")
        log.warning("━" * 60)


async def _reap_stale_rooms_periodically() -> None:
    while True:
        await asyncio.sleep(_STALE_ROOM_SWEEP_INTERVAL_SECONDS)
        reaped = await memory_store.reap_stale_rooms(_STALE_ROOM_MAX_AGE_SECONDS)
        if reaped:
            log.info("Nettoyage : %d room(s) abandonnée(s) supprimée(s)", reaped)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_pocketbase()
    _bootstrap_admin()
    reaper_task = asyncio.create_task(_reap_stale_rooms_periodically())
    yield
    reaper_task.cancel()


app = FastAPI(title="Belote Contrée", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # ty: ignore[invalid-argument-type]
app.add_middleware(SlowAPIMiddleware)
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
app.include_router(users_router, prefix="/api")
if os.getenv("DEVELOPMENT", "false").lower() == "true":
    app.include_router(dev_router, prefix="/api")


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
    if payload.get("is_admin"):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    player_name: str = payload["username"]
    await handle_connection(ws, room_id, player_name, target_score, room_name)
