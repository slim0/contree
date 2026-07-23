"""Traduit un GameState/RoundResult terminé en incréments de compteurs joueur.

Volontairement hors de backend/game/* (moteur pur, zéro I/O — voir CLAUDE.md) et
hors de backend/api/websocket.py (pour ne pas alourdir le dispatcher). Chaque
échec ici est loggé, jamais levé : les stats sont un effet de bord non-critique
qui ne doit jamais casser une partie en cours pour les joueurs.
"""

from __future__ import annotations

import logging

from backend.game.models import TEAM_OF, GamePhase, GameState, RoundResult
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.repository import UserRepository

log = logging.getLogger(__name__)


def _round_increments(game: GameState, result: RoundResult) -> dict[str, dict[str, int]]:
    """Incréments contrat pour le preneur de cette manche uniquement."""
    taker = game.players.get(result.contract.bid.position)
    if not taker:
        return {}
    incr = {"contracts_taken": 1}
    if result.contract_made:
        incr["contracts_made"] = 1
        if result.contract.bid.is_capot:
            incr["capots_won"] = 1
        elif result.contract.bid.is_generale:
            incr["generales_won"] = 1
    return {taker: incr}


def _game_end_increments(game: GameState) -> dict[str, dict[str, int]]:
    """Incréments games_played/won/lost pour les 4 joueurs, une fois la partie FINISHED."""
    if game.phase != GamePhase.FINISHED or game.winner is None:
        return {}
    out: dict[str, dict[str, int]] = {}
    for pos, username in game.players.items():
        entry = out.setdefault(username, {"games_played": 1})
        entry["games_won" if TEAM_OF[pos] == game.winner else "games_lost"] = 1
    return out


def record_round_and_game_stats(game: GameState, pb: PocketBaseClient | None = None) -> None:
    """Appelé une fois par manche terminée (depuis websocket._log_round_result)."""
    result = game.last_result
    if result is None:
        return

    merged: dict[str, dict[str, int]] = {}
    for username, incr in _round_increments(game, result).items():
        merged.setdefault(username, {}).update(incr)
    for username, incr in _game_end_increments(game).items():
        target = merged.setdefault(username, {})
        for field, amount in incr.items():
            target[field] = target.get(field, 0) + amount

    if not merged:
        return

    repo = UserRepository(pb or get_pb_client())
    for username, increments in merged.items():
        try:
            user = repo.get_by_username(username)
            if user is None:
                log.warning(
                    "Stats : utilisateur '%s' introuvable, incrément ignoré", username
                )
                continue
            repo.increment_stats(user.id, increments)
        except Exception:
            log.exception(
                "Stats : échec de l'incrément pour '%s' (%s)", username, increments
            )
