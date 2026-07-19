"""Tests pour le contrat spécial Générale (un seul joueur remporte les 8 plis, 500 pts)."""

from __future__ import annotations

from backend.game.models import (
    Bid,
    Contract,
    Double,
    GamePhase,
    GameState,
    Position,
    RoundState,
    Team,
    Trick,
    Trump,
)
from backend.game.rules import apply_bid, get_legal_bid_actions, start_new_round
from backend.game.scoring import compute_round_result


def _new_game() -> GameState:
    return GameState(
        room_id="room-1",
        players={
            Position.NORTH: "alice",
            Position.EAST: "bob",
            Position.SOUTH: "carol",
            Position.WEST: "dave",
        },
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=GamePhase.WAITING,
        winner=None,
        last_result=None,
        messages=[],
    )


# ── Enchères ─────────────────────────────────────────────────────────────────


def test_can_bid_generale_when_no_contract_yet():
    game = start_new_round(_new_game())
    assert game.round is not None
    bidder = game.round.current_bidder
    assert bidder is not None
    actions = get_legal_bid_actions(game.round, bidder)
    assert actions["can_bid_generale"] is True


def test_generale_still_biddable_over_an_existing_capot():
    """La Générale surclasse le Capot : elle reste proposable même une fois un Capot annoncé."""
    game = start_new_round(_new_game())
    assert game.round is not None
    bidder = game.round.current_bidder
    assert bidder is not None
    game, status = apply_bid(game, 0, True, Trump.HEARTS)  # Capot
    assert status == "ok"
    assert game.round is not None
    next_bidder = game.round.current_bidder
    assert next_bidder is not None
    actions = get_legal_bid_actions(game.round, next_bidder)
    assert actions["can_bid_generale"] is True
    # Mais on ne peut plus enchérir un montant normal ni un nouveau Capot
    assert actions["min_bid_value"] is None
    assert actions["can_bid_capot"] is False


def test_cannot_bid_generale_once_already_the_contract():
    game = start_new_round(_new_game())
    assert game.round is not None
    bidder = game.round.current_bidder
    assert bidder is not None
    game, status = apply_bid(game, 0, False, Trump.HEARTS, is_generale=True)
    assert status == "ok"
    assert game.round is not None
    next_bidder = game.round.current_bidder
    assert next_bidder is not None
    actions = get_legal_bid_actions(game.round, next_bidder)
    assert actions["can_bid_generale"] is False
    assert actions["can_bid_capot"] is False
    assert actions["min_bid_value"] is None


def test_apply_bid_generale_sets_flag_and_contract_value():
    game = start_new_round(_new_game())
    assert game.round is not None
    game, status = apply_bid(game, 0, False, Trump.SPADES, is_generale=True)
    assert status == "ok"
    assert game.round is not None
    contract = game.round.contract
    assert contract is not None
    assert contract.bid.is_generale is True
    assert contract.contract_value() == 500


# ── Score ────────────────────────────────────────────────────────────────────


def _make_generale_round(*, sole_winner: Position, all_tricks_to: Position) -> RoundState:
    bid = Bid(sole_winner, 0, False, Trump.HEARTS, is_generale=True)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    tricks = [Trick(winner=all_tricks_to) for _ in range(8)]
    return RoundState(
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


def test_generale_made_when_the_announcing_player_wins_all_8_tricks_alone():
    r = _make_generale_round(sole_winner=Position.NORTH, all_tricks_to=Position.NORTH)
    result = compute_round_result(r)
    assert result.contract_made is True
    assert result.score_ns == 500
    assert result.score_ew == 0


def test_generale_fails_if_partner_wins_a_trick_even_though_the_team_swept():
    """Le partenaire (même équipe) remporte un pli : la Générale exige le joueur SEUL."""
    r = _make_generale_round(sole_winner=Position.NORTH, all_tricks_to=Position.SOUTH)
    result = compute_round_result(r)
    assert result.contract_made is False
    assert result.score_ns == 0
    assert result.score_ew == 500


def test_generale_failed_score_is_multiplied_on_contre():
    r = _make_generale_round(sole_winner=Position.NORTH, all_tricks_to=Position.SOUTH)
    assert r.contract is not None
    r.contract.double = Double.CONTRE
    result = compute_round_result(r)
    assert result.contract_made is False
    assert result.score_ew == 1000
