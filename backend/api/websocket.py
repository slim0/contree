"""WebSocket connection manager and message dispatcher."""
from __future__ import annotations
import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.game.models import (
    Card, Suit, Rank, Trump, Position, GamePhase,
    GameState,
)
from backend.game import rules
from backend.store import memory_store as store


# room_id -> {position_str -> WebSocket}
_connections: dict[str, dict[str, WebSocket]] = {}
_conn_lock = asyncio.Lock()


async def _register(room_id: str, position: Position, ws: WebSocket) -> None:
    async with _conn_lock:
        _connections.setdefault(room_id, {})[position.value] = ws


async def _unregister(room_id: str, position: Position) -> None:
    async with _conn_lock:
        room = _connections.get(room_id, {})
        room.pop(position.value, None)


async def broadcast(room_id: str, game: GameState, viewer: Optional[Position] = None) -> None:
    """Send game state to all connected players (hiding opponents' hands)."""
    async with _conn_lock:
        sockets = dict(_connections.get(room_id, {}))

    for pos_str, ws in sockets.items():
        pos = Position(pos_str)
        payload = _state_for_player(game, pos)
        try:
            await ws.send_text(json.dumps({"type": "state", "data": payload}))
        except Exception:
            pass


def _state_for_player(game: GameState, player: Position) -> dict:
    """Serialize game state, hiding other players' cards."""
    d = game.to_dict()
    if d.get("round"):
        r = d["round"]
        # Hide other players' hands
        hidden_hands = {}
        for pos_str, hand in r["hands"].items():
            if pos_str == player.value:
                hidden_hands[pos_str] = hand
            else:
                hidden_hands[pos_str] = [{"suit": "?", "rank": "?"}] * len(hand)
        r["hands"] = hidden_hands

        # Add legal actions for this player
        round_obj = game.round
        if round_obj:
            if round_obj.phase == GamePhase.BIDDING and round_obj.current_bidder == player:
                r["legal_bid_actions"] = rules.get_legal_bid_actions(round_obj, player)
            elif round_obj.phase == GamePhase.PLAYING and round_obj.current_player == player:
                legal = rules.get_legal_plays(round_obj)
                r["legal_plays"] = [c.to_dict() for c in legal]

    d["my_position"] = player.value
    return d


async def handle_connection(ws: WebSocket, room_id: str, player_name: str) -> None:
    await ws.accept()

    # Join room (create if needed)
    game = await store.get_game(room_id)
    if game is None:
        game = await store.create_room(room_id)

    if game.phase == GamePhase.FINISHED:
        await ws.send_text(json.dumps({"type": "error", "message": "Partie terminée."}))
        await ws.close()
        return

    game, position = await store.join_room(room_id, player_name)
    if position is None:
        await ws.send_text(json.dumps({"type": "error", "message": "Salon plein."}))
        await ws.close()
        return

    await _register(room_id, position, ws)

    # Start game when 4 players connected
    if len(game.players) == 4 and game.phase == GamePhase.WAITING:
        game = rules.start_new_round(game)
        game.phase = GamePhase.BIDDING
        await store.set_game(game)

    await broadcast(room_id, game)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            game = await store.get_game(room_id)
            if game is None:
                break

            game, error = await _dispatch(game, position, msg)
            await store.set_game(game)
            await broadcast(room_id, game)

            if error:
                await ws.send_text(json.dumps({"type": "error", "message": error}))

    except WebSocketDisconnect:
        await _unregister(room_id, position)
        game = await store.get_game(room_id)
        if game:
            game.messages.append(f"{player_name} ({position.value}) s'est déconnecté")
            await store.set_game(game)
            await broadcast(room_id, game)


async def _dispatch(game: GameState, player: Position, msg: dict) -> tuple[GameState, Optional[str]]:
    action = msg.get("type")
    r = game.round

    if not r:
        return game, "Pas de manche en cours"

    if r.phase == GamePhase.BIDDING:
        if r.current_bidder != player:
            return game, "Ce n'est pas votre tour d'enchérir"

        if action == "pass":
            game, _ = rules.apply_pass(game)

        elif action == "bid":
            try:
                value = int(msg["value"])
                trump = Trump(msg["trump"])
                is_capot = msg.get("is_capot", False)
            except (KeyError, ValueError):
                return game, "Format d'enchère invalide"

            bid_info = rules.get_legal_bid_actions(r, player)
            if is_capot and not bid_info["can_bid_capot"]:
                return game, "Capot non autorisé"
            if not is_capot:
                min_val = bid_info.get("min_bid_value")
                if min_val is None or value < min_val or value > 160 or value % 10 != 0:
                    return game, f"Valeur d'enchère invalide (min {min_val})"
            game, _ = rules.apply_bid(game, value, is_capot, trump)

        elif action == "contre":
            bid_info = rules.get_legal_bid_actions(r, player)
            if not bid_info["can_contre"]:
                return game, "Contre non autorisé"
            game, _ = rules.apply_contre(game)

        elif action == "surcontre":
            bid_info = rules.get_legal_bid_actions(r, player)
            if not bid_info["can_surcontre"]:
                return game, "Surcontre non autorisé"
            game, _ = rules.apply_surcontre(game)

        else:
            return game, f"Action inconnue : {action}"

    elif r.phase == GamePhase.PLAYING:
        if r.current_player != player:
            return game, "Ce n'est pas votre tour de jouer"

        if action == "play":
            try:
                card = Card(Suit(msg["suit"]), Rank(msg["rank"]))
            except (KeyError, ValueError):
                return game, "Carte invalide"
            game, err = rules.apply_play(game, card)
            if err not in ("ok", "round_end"):
                return game, err
        else:
            return game, f"Action inconnue en phase jeu : {action}"

    else:
        return game, f"Phase incorrecte : {r.phase}"

    return game, None
