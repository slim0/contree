"""Pure scoring logic — no I/O."""

from __future__ import annotations

from .models import (
    ALL_TRUMP_POINTS,
    NO_TRUMP_POINTS,
    NORMAL_POINTS,
    TEAM_OF,
    TRUMP_POINTS,
    Card,
    Double,
    RoundResult,
    RoundState,
    Suit,
    Team,
    Trump,
)


def card_points(card: Card, trump: Trump) -> int:
    if trump == Trump.NO_TRUMP:
        return NO_TRUMP_POINTS[card.rank]
    if trump == Trump.ALL_TRUMP:
        return ALL_TRUMP_POINTS[card.rank]
    trump_suit = Suit(trump.value)
    if card.suit == trump_suit:
        return TRUMP_POINTS[card.rank]
    return NORMAL_POINTS[card.rank]


def compute_round_result(r: RoundState) -> RoundResult:
    assert r.contract is not None
    trump = r.contract.bid.trump
    bidding_team = r.contract.bidding_team
    defending_team = (
        Team.EAST_WEST if bidding_team == Team.NORTH_SOUTH else Team.NORTH_SOUTH
    )

    # Sum card points per team
    card_points_ns = 0
    card_points_ew = 0
    for trick in r.tricks:
        assert trick.winner is not None
        winner_team = TEAM_OF[trick.winner]
        pts = sum(card_points(tc.card, trump) for tc in trick.cards)
        if winner_team == Team.NORTH_SOUTH:
            card_points_ns += pts
        else:
            card_points_ew += pts

    # Dix de der: always 10 pts for the team that won the last trick
    last_winner = r.tricks[-1].winner
    assert last_winner is not None
    if TEAM_OF[last_winner] == Team.NORTH_SOUTH:
        card_points_ns += 10
    else:
        card_points_ew += 10

    # Preneurs evaluation points (for contract check)
    preneurs_card_pts = (
        card_points_ns if bidding_team == Team.NORTH_SOUTH else card_points_ew
    )

    # Check capot
    if r.contract.bid.is_capot:
        tricks_by_bidders = sum(
            1
            for t in r.tricks
            if t.winner is not None and TEAM_OF[t.winner] == bidding_team
        )
        contract_made = tricks_by_bidders == 8
    else:
        # Belote of preneurs counts toward contract evaluation
        belote_bonus_for_preneurs = 20 if r.belote_team == bidding_team else 0
        preneurs_eval = preneurs_card_pts + belote_bonus_for_preneurs
        contract_made = preneurs_eval >= r.contract.bid.value

    preneurs_eval_display = preneurs_card_pts + (
        20 if r.belote_team == bidding_team else 0
    )

    contract_value = r.contract.contract_value()
    multiplier = {Double.NONE: 1, Double.CONTRE: 2, Double.SURCONTRE: 4}[
        r.contract.double
    ]

    if contract_made:
        # Preneurs score the announced value
        preneurs_score = contract_value
        # Defenders score 0, except their own belote
        defenders_belote = 20 if r.belote_team == defending_team else 0
        defenders_score = defenders_belote

        if bidding_team == Team.NORTH_SOUTH:
            score_ns, score_ew = preneurs_score, defenders_score
        else:
            score_ns, score_ew = defenders_score, preneurs_score

        belote_msg = ""
        if r.belote_team == bidding_team:
            belote_msg = " (belote preneurs : non comptée dans score final)"
        if r.belote_team == defending_team:
            belote_msg = " (belote défense +20)"

        msg = (
            f"Contrat RÉUSSI — {bidding_team.value} marque {preneurs_score}, "
            f"{defending_team.value} marque {defenders_score}{belote_msg}"
        )
    else:
        # Chute: defenders score the announced value × multiplier
        defenders_score = contract_value * multiplier
        preneurs_score = 0

        if bidding_team == Team.NORTH_SOUTH:
            score_ns, score_ew = preneurs_score, defenders_score
        else:
            score_ns, score_ew = defenders_score, preneurs_score

        mult_msg = f" ×{multiplier}" if multiplier > 1 else ""
        msg = (
            f"CHUTE — {bidding_team.value} chute ({preneurs_eval_display} pts / "
            f"contrat {contract_value}). "
            f"{defending_team.value} marque {contract_value}{mult_msg} = {defenders_score}"
        )

    return RoundResult(
        round_number=r.number,
        contract=r.contract,
        preneurs_eval=preneurs_eval_display,
        contract_made=contract_made,
        score_ns=score_ns,
        score_ew=score_ew,
        belote_team=r.belote_team,
        message=msg,
    )
