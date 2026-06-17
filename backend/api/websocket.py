"""WebSocket connection manager and message dispatcher."""
from __future__ import annotations
import json
import logging
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.game.models import (
    Card, Suit, Rank, Trump, Position, GamePhase,
    GameState,
)
from backend.game import rules
from backend.store import memory_store as store

log = logging.getLogger(__name__)

# room_id -> {position_str -> (WebSocket, conn_id)}
# conn_id prevents stale disconnect handlers from unregistering a newer connection.
_connections: dict[str, dict[str, tuple[WebSocket, int]]] = {}
_conn_lock = asyncio.Lock()
_conn_serial: int = 0

# Rooms currently closing all connections for team reassignment; do not delete them.
_closing_for_start: set[str] = set()


async def _register(room_id: str, position: Position, ws: WebSocket) -> int:
    global _conn_serial
    async with _conn_lock:
        _conn_serial += 1
        conn_id = _conn_serial
        _connections.setdefault(room_id, {})[position.value] = (ws, conn_id)
        _closing_for_start.discard(room_id)
        return conn_id


async def _unregister(room_id: str, position: Position, conn_id: int) -> None:
    """Only remove the connection if it still belongs to conn_id (guards against stale handlers)."""
    async with _conn_lock:
        room = _connections.get(room_id, {})
        entry = room.get(position.value)
        if entry is not None and entry[1] == conn_id:
            room.pop(position.value)


async def broadcast(room_id: str, game: GameState, viewer: Optional[Position] = None) -> None:
    """Send game state to all connected players (hiding opponents' hands)."""
    async with _conn_lock:
        sockets = {pos: ws for pos, (ws, _) in _connections.get(room_id, {}).items()}

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
        hidden_hands = {}
        for pos_str, hand in r["hands"].items():
            if pos_str == player.value:
                hidden_hands[pos_str] = hand
            else:
                hidden_hands[pos_str] = [{"suit": "?", "rank": "?"}] * len(hand)
        r["hands"] = hidden_hands

        round_obj = game.round
        if round_obj:
            if round_obj.phase == GamePhase.BIDDING and round_obj.current_bidder == player:
                r["legal_bid_actions"] = rules.get_legal_bid_actions(round_obj, player)
            elif round_obj.phase == GamePhase.PLAYING and round_obj.current_player == player:
                legal = rules.get_legal_plays(round_obj)
                r["legal_plays"] = [c.to_dict() for c in legal]

    d["my_position"] = player.value
    return d


def _player_tag(game: GameState, position: Position) -> str:
    """Returns 'Prénom (POS)' for log messages."""
    name = game.players.get(position, "?")
    return f"{name} ({position.value})"


async def _close_all_connections(room_id: str) -> None:
    """Notify all players that the game is starting, then close their connections."""
    _closing_for_start.add(room_id)
    async with _conn_lock:
        entries = list(_connections.get(room_id, {}).values())
        _connections.pop(room_id, None)
    for ws, _ in entries:
        try:
            await ws.send_text(json.dumps({"type": "restarting"}))
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass


async def _dispatch_waiting(
    game: GameState, player: Position, msg: dict, room_id: str
) -> tuple[GameState, Optional[str], bool]:
    """Handle WAITING-phase messages. Returns (game, error, close_all_connections)."""
    action = msg.get("type")
    tag = _player_tag(game, player)

    if action == "choose_team":
        team = msg.get("team")
        if team not in ("NS", "EW"):
            return game, "Équipe invalide (NS ou EW attendu)", False
        game.team_choices[player.value] = team
        log.info("Salon '%s' — %s choisit l'équipe %s", room_id, tag, team)
        return game, None, False

    elif action == "start_game":
        if len(game.players) != 4:
            return game, "Il faut 4 joueurs pour démarrer", False

        ns_pos = [p for p, t in game.team_choices.items() if t == "NS"]
        ew_pos = [p for p, t in game.team_choices.items() if t == "EW"]

        if len(ns_pos) != 2 or len(ew_pos) != 2:
            return game, "Il faut exactement 2 joueurs NOUS et 2 joueurs EUX", False

        # Réassignation : NOUS → N,S ; EUX → E,W
        ns_names = [game.players[Position(p)] for p in ns_pos]
        ew_names = [game.players[Position(p)] for p in ew_pos]

        game.players = {
            Position.NORTH: ns_names[0],
            Position.SOUTH: ns_names[1],
            Position.EAST: ew_names[0],
            Position.WEST: ew_names[1],
        }
        game.team_choices = {}
        game.ready_to_start = True

        log.info(
            "Salon '%s' — GO ! NOUS (NS) : %s | EUX (EW) : %s",
            room_id, ns_names, ew_names,
        )
        return game, None, True  # close_all = True → fermer toutes les connexions

    return game, f"Action inconnue en salle d'attente : {action}", False


async def handle_connection(ws: WebSocket, room_id: str, player_name: str, target_score: int = 1000, room_name: str = "") -> None:
    await ws.accept()
    log.info("── CONNEXION  %s  →  salon '%s'", player_name, room_id)

    game = await store.get_game(room_id)
    if game is None:
        log.info("Salon '%s' créé (score cible : %d)", room_id, target_score)
        game = await store.create_room(room_id, target_score, room_name)

    if game.phase == GamePhase.FINISHED:
        log.warning("Salon '%s' terminé — %s refusé", room_id, player_name)
        await ws.send_text(json.dumps({"type": "error", "message": "Partie terminée."}))
        await ws.close()
        return

    # Identify if this player already has a slot (reconnection case).
    # If the old connection is still "active" (possible zombie or race), kick it
    # and let the new connection take over. A conn_id guards against the old
    # handler accidentally unregistering the new connection.
    position: Optional[Position] = None
    old_ws_to_close: Optional[WebSocket] = None

    for pos, name in game.players.items():
        if name == player_name:
            async with _conn_lock:
                room_conns = _connections.get(room_id, {})
                entry = room_conns.pop(pos.value, None)
                if entry is not None:
                    old_ws_to_close, _ = entry
                    log.warning(
                        "Salon '%s' — %s reconnecte avec ancienne connexion active (zombie ?), kick en cours",
                        room_id, player_name,
                    )
            position = pos
            break

    if old_ws_to_close is not None:
        try:
            await old_ws_to_close.close()
        except Exception:
            pass

    if position is not None:
        log.info("Salon '%s' — %s se reconnecte en position %s", room_id, player_name, position.value)
        game.messages.append(f"{player_name} ({position.value}) s'est reconnecté")
        await store.set_game(game)
    else:
        game, position = await store.join_room(room_id, player_name)
        if position is None:
            log.warning("Salon '%s' plein — %s refusé", room_id, player_name)
            await ws.send_text(json.dumps({"type": "error", "message": "Salon plein."}))
            await ws.close()
            return
        log.info("Salon '%s' — %s rejoint en position %s  [%d/4]",
                 room_id, player_name, position.value, len(game.players))

    conn_id = await _register(room_id, position, ws)

    # Démarrage après GO : quand les 4 joueurs se sont reconnectés suite à la réassignation
    if game.ready_to_start and game.phase == GamePhase.WAITING and len(game.players) == 4:
        async with _conn_lock:
            n_connected = len(_connections.get(room_id, {}))
        if n_connected == 4:
            log.info("Salon '%s' — 4 reconnexions après GO, démarrage", room_id)
            log.debug("  Joueurs : %s", {p.value: n for p, n in game.players.items()})
            game = rules.start_new_round(game)
            game.phase = GamePhase.BIDDING
            game.ready_to_start = False
            log.info("Salon '%s' — Manche 1 démarrée, donneur=%s, premier enchérisseur=%s",
                     room_id, game.round.dealer.value, game.round.current_bidder.value)
            await store.set_game(game)

    await broadcast(room_id, game)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            game = await store.get_game(room_id)
            if game is None:
                break

            # Phase d'attente : choix d'équipe et démarrage
            if game.phase == GamePhase.WAITING:
                game, error, close_all = await _dispatch_waiting(game, position, msg, room_id)
                await store.set_game(game)
                if close_all:
                    await _close_all_connections(room_id)
                    break
                await broadcast(room_id, game)
                if error:
                    log.warning("Salon '%s' — Erreur pour %s : %s", room_id, player_name, error)
                    await ws.send_text(json.dumps({"type": "error", "message": error}))
                continue

            game, error = await _dispatch(game, position, msg, room_id)
            await store.set_game(game)
            await broadcast(room_id, game)

            if error:
                log.warning("Salon '%s' — Erreur pour %s : %s", room_id, player_name, error)
                await ws.send_text(json.dumps({"type": "error", "message": error}))

    except WebSocketDisconnect:
        await _unregister(room_id, position, conn_id)
        log.info("── DÉCONNEXION  %s (%s)  ←  salon '%s'", player_name, position.value, room_id)

        async with _conn_lock:
            no_connections_left = not _connections.get(room_id)

        if no_connections_left:
            # Conserver le salon si une réassignation d'équipes est en cours
            if room_id in _closing_for_start:
                log.info("Salon '%s' — fermeture temporaire pour réassignation d'équipes", room_id)
            else:
                game = await store.get_game(room_id)
                if game and game.ready_to_start and game.phase == GamePhase.WAITING:
                    log.info("Salon '%s' — pas de suppression (attente reconnexions post-GO)", room_id)
                else:
                    log.info("Salon '%s' — plus aucune connexion active, suppression", room_id)
                    await store.delete_room(room_id)
        else:
            game = await store.get_game(room_id)
            if game:
                game.messages.append(f"{player_name} ({position.value}) s'est déconnecté")
                await store.set_game(game)
                await broadcast(room_id, game)


async def _dispatch(
    game: GameState, player: Position, msg: dict, room_id: str
) -> tuple[GameState, Optional[str]]:
    action = msg.get("type")
    r = game.round
    tag = _player_tag(game, player)

    if not r:
        return game, "Pas de manche en cours"

    # ── Enchères ──────────────────────────────────────────────────────────────
    if r.phase == GamePhase.BIDDING:
        if r.current_bidder != player:
            log.debug("Salon '%s' — %s tente d'enchérir hors tour", room_id, tag)
            return game, "Ce n'est pas votre tour d'enchérir"

        if action == "pass":
            log.info("Salon '%s' — %s  PASSE  (passes consécutives : %d)",
                     room_id, tag, r.pass_count + 1)
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

            val_str = "Capot" if is_capot else str(value)
            log.info("Salon '%s' — %s  ANNONCE  %s à %s", room_id, tag, val_str, trump.value)
            game, _ = rules.apply_bid(game, value, is_capot, trump)

            # Log if bidding ended
            if game.round and game.round.phase == GamePhase.PLAYING:
                _log_contract(game, room_id)

        elif action == "contre":
            bid_info = rules.get_legal_bid_actions(r, player)
            if not bid_info["can_contre"]:
                return game, "Contre non autorisé"
            log.info("Salon '%s' — %s  CONTRE !", room_id, tag)
            game, _ = rules.apply_contre(game)

        elif action == "surcontre":
            bid_info = rules.get_legal_bid_actions(r, player)
            if not bid_info["can_surcontre"]:
                return game, "Surcontre non autorisé"
            log.info("Salon '%s' — %s  SURCONTRE !", room_id, tag)
            game, _ = rules.apply_surcontre(game)
            if game.round and game.round.phase == GamePhase.PLAYING:
                _log_contract(game, room_id)

        else:
            return game, f"Action inconnue : {action}"

        # Log bidding→playing transition when triggered by pass
        if action == "pass" and game.round and game.round.phase == GamePhase.PLAYING:
            _log_contract(game, room_id)

        # Log deal void
        if action == "pass" and (not game.round or (game.round and game.round.number != r.number)):
            log.info("Salon '%s' — Donne annulée (4 passes)", room_id)

    # ── Jeu ───────────────────────────────────────────────────────────────────
    elif r.phase == GamePhase.PLAYING:
        if r.current_player != player:
            log.debug("Salon '%s' — %s tente de jouer hors tour", room_id, tag)
            return game, "Ce n'est pas votre tour de jouer"

        if action == "play":
            try:
                card = Card(Suit(msg["suit"]), Rank(msg["rank"]))
            except (KeyError, ValueError):
                return game, "Carte invalide"

            log.info("Salon '%s' — %s  JOUE  %s  (pli %d/8)",
                     room_id, tag, card, len(r.tricks) + 1)

            game, err = rules.apply_play(game, card)
            if err not in ("ok", "round_end"):
                log.warning("Salon '%s' — Carte illégale pour %s : %s", room_id, tag, err)
                return game, err

            # Log trick completion
            prev_round = game.round
            if prev_round and len(prev_round.tricks) > len(r.tricks):
                last = prev_round.tricks[-1]
                winner_name = game.players.get(last.winner, "?") if last.winner else "?"
                winner_tag = f"{winner_name} ({last.winner.value})" if last.winner else "?"
                log.info("Salon '%s' — Pli %d remporté par %s",
                         room_id, len(prev_round.tricks), winner_tag)

            # Log round completion
            if err == "round_end" or (game.round and game.round.number != r.number) or game.phase == GamePhase.FINISHED:
                _log_round_result(game, room_id)
        else:
            return game, f"Action inconnue en phase jeu : {action}"

    else:
        return game, f"Phase incorrecte : {r.phase}"

    return game, None


def _log_contract(game: GameState, room_id: str) -> None:
    r = game.round
    if not r or not r.contract:
        return
    c = r.contract
    val = "Capot" if c.bid.is_capot else str(c.bid.value)
    double_str = f" [{c.double.value}]" if c.double.value != "NONE" else ""
    bidder_name = game.players.get(c.bid.position, "?")
    log.info(
        "Salon '%s' — ✦ CONTRAT FIXÉ : %s (%s) joue %s à %s%s  |  premier joueur : %s",
        room_id,
        bidder_name, c.bidding_team.value,
        val, c.bid.trump.value,
        double_str,
        r.current_player.value if r.current_player else "?",
    )
    if r.belote_team:
        log.info("Salon '%s' — Belote détectée pour l'équipe %s", room_id, r.belote_team.value)


def _log_round_result(game: GameState, room_id: str) -> None:
    from backend.game.models import Team
    lr = game.last_result
    if not lr:
        return
    status = "RÉUSSI ✓" if lr.contract_made else "CHUTE ✗"
    log.info(
        "Salon '%s' — ═══ Manche %d %s │ NS +%d (total %d)  EW +%d (total %d)",
        room_id, lr.round_number, status,
        lr.score_ns, game.scores[Team.NORTH_SOUTH],
        lr.score_ew, game.scores[Team.EAST_WEST],
    )
    log.debug("Salon '%s' — Détail : %s", room_id, lr.message)
    if game.phase == GamePhase.FINISHED:
        log.info("Salon '%s' — 🏆 PARTIE TERMINÉE — Vainqueur : %s", room_id, game.winner)
