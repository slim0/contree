from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.api.websocket import handle_connection

app = FastAPI(title="Belote Contrée")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(ws: WebSocket, room_id: str, player_name: str):
    await handle_connection(ws, room_id, player_name)
