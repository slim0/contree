"""Tests des statistiques joueur (backend/api/stats.py)."""

from __future__ import annotations

from backend.api.stats import (
    _game_end_increments,
    _round_increments,
    record_round_and_game_stats,
)
from backend.game.models import (
    Bid,
    Contract,
    Double,
    GamePhase,
    GameState,
    Position,
    RoundResult,
    RoundState,
    Team,
    Trick,
    Trump,
)
from backend.game.scoring import compute_round_result
from backend.users.repository import UserRepository

PLAYERS = {
    Position.NORTH: "alice",
    Position.EAST: "bob",
    Position.SOUTH: "carol",
    Position.WEST: "dave",
}


def _game(*, phase=GamePhase.SCORING, winner=None, last_result=None) -> GameState:
    return GameState(
        room_id="room-1",
        players=dict(PLAYERS),
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=phase,
        winner=winner,
        last_result=last_result,
        messages=[],
    )


def _normal_result(*, made: bool) -> RoundResult:
    bid = Bid(Position.NORTH, 80, is_capot=False, trump=Trump.HEARTS)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    return RoundResult(
        round_number=1,
        contract=contract,
        preneurs_eval=80 if made else 40,
        contract_made=made,
        score_ns=80 if made else 0,
        score_ew=0 if made else 160,
        belote_team=None,
        message="",
    )


def _capot_result(*, made: bool) -> RoundResult:
    bid = Bid(Position.NORTH, 0, is_capot=True, trump=Trump.HEARTS)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    winner = Position.NORTH if made else Position.EAST
    tricks = [Trick(winner=winner) for _ in range(8)]
    r = RoundState(
        number=1,
        dealer=Position.WEST,
        hands={},
        phase=GamePhase.SCORING,
        current_bidder=None,
        pass_count=0,
        bid_history=[],
        contract=contract,
        current_player=None,
        tricks=tricks,
        current_trick=Trick(),
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )
    return compute_round_result(r)


def _generale_result(*, made: bool) -> RoundResult:
    bid = Bid(Position.NORTH, 0, is_capot=False, trump=Trump.HEARTS, is_generale=True)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    # Générale réussie : NORTH seul remporte les 8 plis. Ratée : un partenaire en gagne un.
    winners = [Position.NORTH] * 8
    if not made:
        winners[0] = Position.SOUTH
    tricks = [Trick(winner=w) for w in winners]
    r = RoundState(
        number=1,
        dealer=Position.WEST,
        hands={},
        phase=GamePhase.SCORING,
        current_bidder=None,
        pass_count=0,
        bid_history=[],
        contract=contract,
        current_player=None,
        tricks=tricks,
        current_trick=Trick(),
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )
    return compute_round_result(r)


# ── _round_increments ──────────────────────────────────────────────────────────


def test_round_increments_on_chute_only_counts_contract_taken():
    game = _game()
    result = _normal_result(made=False)
    incr = _round_increments(game, result)
    assert incr == {"alice": {"contracts_taken": 1}}


def test_round_increments_on_normal_contract_made_no_capot_generale_bonus():
    game = _game()
    result = _normal_result(made=True)
    incr = _round_increments(game, result)
    assert incr == {"alice": {"contracts_taken": 1, "contracts_made": 1}}


def test_round_increments_capot_made_adds_capots_won():
    game = _game()
    result = _capot_result(made=True)
    incr = _round_increments(game, result)
    assert incr == {
        "alice": {"contracts_taken": 1, "contracts_made": 1, "capots_won": 1}
    }


def test_round_increments_capot_failed_no_bonus():
    game = _game()
    result = _capot_result(made=False)
    incr = _round_increments(game, result)
    assert incr == {"alice": {"contracts_taken": 1}}


def test_round_increments_generale_made_adds_generales_won():
    game = _game()
    result = _generale_result(made=True)
    incr = _round_increments(game, result)
    assert incr == {
        "alice": {"contracts_taken": 1, "contracts_made": 1, "generales_won": 1}
    }


def test_round_increments_generale_failed_no_bonus():
    game = _game()
    result = _generale_result(made=False)
    incr = _round_increments(game, result)
    assert incr == {"alice": {"contracts_taken": 1}}


def test_round_increments_unknown_taker_position_returns_empty():
    game = _game()
    game.players = {}
    result = _normal_result(made=True)
    assert _round_increments(game, result) == {}


# ── _game_end_increments ────────────────────────────────────────────────────────


def test_game_end_increments_empty_when_not_finished():
    game = _game(phase=GamePhase.SCORING, winner=None)
    assert _game_end_increments(game) == {}


def test_game_end_increments_empty_when_finished_without_winner():
    game = _game(phase=GamePhase.FINISHED, winner=None)
    assert _game_end_increments(game) == {}


def test_game_end_increments_splits_won_lost_by_team():
    game = _game(phase=GamePhase.FINISHED, winner=Team.NORTH_SOUTH)
    incr = _game_end_increments(game)
    assert incr == {
        "alice": {"games_played": 1, "games_won": 1},
        "carol": {"games_played": 1, "games_won": 1},
        "bob": {"games_played": 1, "games_lost": 1},
        "dave": {"games_played": 1, "games_lost": 1},
    }


# ── record_round_and_game_stats (via vraie instance PocketBase) ────────────────


def test_record_round_and_game_stats_merges_round_and_game_end(pb_client):
    repo = UserRepository(pb_client)
    repo.create("fourthplayer", "pass12345", must_change_password=False)
    game = _game(
        phase=GamePhase.FINISHED,
        winner=Team.NORTH_SOUTH,
        last_result=_capot_result(made=True),
    )
    game.players = {
        Position.NORTH: "testuser",
        Position.EAST: "testuser2",
        Position.SOUTH: "admin",
        Position.WEST: "fourthplayer",
    }

    record_round_and_game_stats(game, pb_client)

    taker = repo.get_by_username("testuser")
    assert taker is not None
    assert taker.contracts_taken == 1
    assert taker.contracts_made == 1
    assert taker.capots_won == 1
    assert taker.games_played == 1
    assert taker.games_won == 1

    # SOUTH (admin) est dans la même équipe (NORTH_SOUTH) que le preneur : gagnant aussi.
    partner = repo.get_by_username("admin")
    assert partner is not None
    assert partner.contracts_taken == 0
    assert partner.games_played == 1
    assert partner.games_won == 1

    # EAST/WEST (testuser2/fourthplayer) forment l'équipe EAST_WEST : perdants.
    defender = repo.get_by_username("fourthplayer")
    assert defender is not None
    assert defender.contracts_taken == 0
    assert defender.games_played == 1
    assert defender.games_lost == 1


def test_record_round_and_game_stats_unknown_username_is_skipped(pb_client):
    game = _game(last_result=_normal_result(made=True))
    game.players = {Position.NORTH: "ghost-user"}
    # Ne doit pas lever, même si l'utilisateur n'existe pas côté PocketBase.
    record_round_and_game_stats(game, pb_client)


def test_record_round_and_game_stats_no_op_without_last_result(pb_client):
    game = _game(last_result=None)
    # Ne doit rien faire (et ne pas lever) quand aucune manche n'a encore été jouée.
    record_round_and_game_stats(game, pb_client)
