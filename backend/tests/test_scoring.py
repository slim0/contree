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
from backend.game.scoring import compute_round_result


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
