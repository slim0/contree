"""Tests sur le calcul du score (compute_round_result)."""

from __future__ import annotations

from backend.game.models import (
    Bid,
    Card,
    Contract,
    Double,
    GamePhase,
    Position,
    Rank,
    RoundState,
    Suit,
    Team,
    Trick,
    TrickCard,
    Trump,
)
from backend.game.scoring import compute_round_result, running_points


def _make_round(*, bidding_team: Team, belote_team: Team | None) -> RoundState:
    """Un contrat NS/EW à coeur, valeur 20, réussi via un seul pli + dix de der."""
    bid = Bid(
        position=Position.NORTH if bidding_team == Team.NORTH_SOUTH else Position.EAST,
        value=20,
        is_capot=False,
        trump=Trump.HEARTS,
    )
    contract = Contract(bid, Double.NONE, bidding_team)

    # Pli remporté par NORTH (équipe NOUS) : As+10+Roi+Dame de trèfle = 28 pts
    trick = Trick(
        cards=[
            TrickCard(Position.NORTH, Card(Suit.CLUBS, Rank.ACE)),
            TrickCard(Position.EAST, Card(Suit.CLUBS, Rank.TEN)),
            TrickCard(Position.SOUTH, Card(Suit.CLUBS, Rank.KING)),
            TrickCard(Position.WEST, Card(Suit.CLUBS, Rank.QUEEN)),
        ],
        winner=Position.NORTH,
    )

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
        tricks=[trick],
        current_trick=Trick(),
        belote_team=belote_team,
        belote_king_played=belote_team is not None,
        belote_queen_played=belote_team is not None,
    )


def test_belote_never_scores_points_for_the_defending_team():
    """La défense (EUX) détient la belote mais NE doit rien marquer pour ça."""
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=Team.EAST_WEST)
    result = compute_round_result(r)
    # NS = preneurs (score_ns), EW = défenseurs (score_ew)
    assert result.score_ew == 0
    assert result.score_ns == 20  # valeur du contrat, inchangée


def test_belote_of_bidding_team_does_not_add_extra_points_to_defense():
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=Team.NORTH_SOUTH)
    result = compute_round_result(r)
    assert result.score_ew == 0
    assert result.score_ns == 20


def test_no_belote_at_all_defense_still_scores_zero_on_contract_made():
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=None)
    result = compute_round_result(r)
    assert result.score_ew == 0
    assert result.score_ns == 20


# ---------------------------------------------------------------------------
# Score en temps réel (points faits de la manche en cours)
# ---------------------------------------------------------------------------


def test_running_points_before_any_trick_is_zero_zero():
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=None)
    r.tricks = []
    assert running_points(r) == {"NS": 0, "EW": 0}


def test_running_points_reflects_completed_tricks_only():
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=None)
    # Un pli remporté par NORTH (NS) : As+10+Roi+Dame de trèfle = 11+10+4+3 = 28
    assert running_points(r) == {"NS": 28, "EW": 0}

    # Un second pli, en cours (pas encore de gagnant), ne doit pas être compté
    r.tricks.append(
        Trick(
            cards=[
                TrickCard(Position.EAST, Card(Suit.SPADES, Rank.ACE)),
            ],
            winner=None,
        )
    )
    assert running_points(r) == {"NS": 28, "EW": 0}


def test_running_points_ignores_dix_de_der():
    """running_points ne doit pas ajouter les 10 points de dix de der : la manche n'est pas finie."""
    r = _make_round(bidding_team=Team.NORTH_SOUTH, belote_team=None)
    result = compute_round_result(r)  # avec dix de der
    assert (
        result.preneurs_eval == 28 + 10
    )  # 38, dix de der inclus dans le résultat final
    assert running_points(r) == {"NS": 28, "EW": 0}  # mais pas dans le suivi temps réel


# ---------------------------------------------------------------------------
# Capot
# ---------------------------------------------------------------------------


def _make_capot_round(*, tricks_go_to: Team) -> RoundState:
    bid = Bid(Position.NORTH, 0, is_capot=True, trump=Trump.HEARTS)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    winner = Position.NORTH if tricks_go_to == Team.NORTH_SOUTH else Position.EAST
    tricks = [Trick(winner=winner) for _ in range(8)]
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


def test_capot_made_scores_250_points():
    r = _make_capot_round(tricks_go_to=Team.NORTH_SOUTH)
    result = compute_round_result(r)
    assert result.contract_made is True
    assert result.score_ns == 250
    assert result.score_ew == 0


def test_capot_failed_scores_250_points_times_multiplier_for_defense():
    r = _make_capot_round(tricks_go_to=Team.EAST_WEST)
    assert r.contract is not None
    r.contract.double = Double.CONTRE
    result = compute_round_result(r)
    assert result.contract_made is False
    assert result.score_ew == 500
