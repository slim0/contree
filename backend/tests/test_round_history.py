"""L'historique des scores (round_history) accumule le résultat de chaque manche
terminée de la partie en cours — distinct du journal d'actions (jamais exposé
aux joueurs), il sert au récapitulatif des scores affiché côté front."""

from __future__ import annotations

from backend.game.models import (
    Bid,
    Card,
    Contract,
    Double,
    GamePhase,
    GameState,
    Position,
    Rank,
    RoundState,
    Suit,
    Team,
    Trick,
    TrickCard,
    Trump,
)
from backend.game.rules import apply_pass, apply_play, restart_game, start_new_round

PLAYERS = {
    Position.NORTH: "alice",
    Position.EAST: "bob",
    Position.SOUTH: "carol",
    Position.WEST: "dave",
}


def _make_game_one_card_from_round_end(
    round_number: int, dealer: Position, bidding_team: Team
) -> tuple[GameState, Card]:
    """Manche à 7 plis déjà joués (tous remportés par NORTH), il ne reste que la
    carte de WEST à jouer pour compléter le 8e et dernier pli."""
    bid = Bid(Position.NORTH, 80, is_capot=False, trump=Trump.NO_TRUMP)
    contract = Contract(bid, Double.NONE, bidding_team)
    last_card = Card(Suit.SPADES, Rank.SEVEN)
    current_trick = Trick(
        cards=[
            TrickCard(Position.NORTH, Card(Suit.HEARTS, Rank.ACE)),
            TrickCard(Position.EAST, Card(Suit.HEARTS, Rank.KING)),
            TrickCard(Position.SOUTH, Card(Suit.HEARTS, Rank.QUEEN)),
        ]
    )
    round_state = RoundState(
        number=round_number,
        dealer=dealer,
        hands={
            Position.NORTH: [],
            Position.EAST: [],
            Position.SOUTH: [],
            Position.WEST: [last_card],
        },
        phase=GamePhase.PLAYING,
        current_bidder=None,
        pass_count=0,
        bid_history=[],
        contract=contract,
        current_player=Position.WEST,
        tricks=[Trick(winner=Position.NORTH) for _ in range(7)],
        current_trick=current_trick,
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )
    game = GameState(
        room_id="room-1",
        players=PLAYERS,
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=round_state,
        phase=GamePhase.PLAYING,
        winner=None,
        last_result=None,
        messages=[],
    )
    return game, last_card


def test_round_history_starts_empty():
    game, _ = _make_game_one_card_from_round_end(1, Position.WEST, Team.NORTH_SOUTH)
    assert game.round_history == []


def test_completed_round_is_appended_to_round_history():
    game, last_card = _make_game_one_card_from_round_end(
        1, Position.WEST, Team.NORTH_SOUTH
    )
    game, status = apply_play(game, last_card)
    assert status == "round_end"
    assert len(game.round_history) == 1
    assert game.round_history[0] == game.last_result
    assert game.round_history[0].round_number == 1


def test_round_history_accumulates_across_multiple_rounds_in_order():
    game, last_card = _make_game_one_card_from_round_end(
        1, Position.WEST, Team.NORTH_SOUTH
    )
    game, _ = apply_play(game, last_card)
    assert [r.round_number for r in game.round_history] == [1]

    game = start_new_round(game)  # manche 2
    assert game.round is not None
    game.round.contract = Contract(
        Bid(Position.EAST, 90, is_capot=False, trump=Trump.NO_TRUMP),
        Double.NONE,
        Team.EAST_WEST,
    )
    game.round.hands = {
        Position.NORTH: [],
        Position.EAST: [],
        Position.SOUTH: [],
        Position.WEST: [Card(Suit.CLUBS, Rank.SEVEN)],
    }
    game.round.tricks = [Trick(winner=Position.EAST) for _ in range(7)]
    game.round.current_trick = Trick(
        cards=[
            TrickCard(Position.NORTH, Card(Suit.DIAMONDS, Rank.ACE)),
            TrickCard(Position.EAST, Card(Suit.DIAMONDS, Rank.KING)),
            TrickCard(Position.SOUTH, Card(Suit.DIAMONDS, Rank.QUEEN)),
        ]
    )
    game.round.current_player = Position.WEST
    game.round.phase = GamePhase.PLAYING

    game, status = apply_play(game, Card(Suit.CLUBS, Rank.SEVEN))
    assert status == "round_end"
    assert [r.round_number for r in game.round_history] == [1, 2]
    assert game.round_history[-1] == game.last_result


def test_voided_deal_does_not_add_a_round_history_entry():
    game = GameState(
        room_id="room-1",
        players=PLAYERS,
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=None,
        phase=GamePhase.WAITING,
        winner=None,
        last_result=None,
        messages=[],
    )
    game = start_new_round(game)
    for _ in range(4):
        game, status = apply_pass(game)
    assert status == "redeal"
    assert game.round_history == []


def test_restart_game_clears_round_history():
    game, last_card = _make_game_one_card_from_round_end(
        1, Position.WEST, Team.NORTH_SOUTH
    )
    game, _ = apply_play(game, last_card)
    assert len(game.round_history) == 1

    restarted = restart_game(game)

    assert restarted.round_history == []
