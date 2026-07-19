"""Le dernier pli d'une manche doit rester affiché quelques secondes (phase
SCORING) avant que la donne suivante ne soit distribuée, pour que les joueurs
aient le temps de le voir avant l'écran de score."""

from __future__ import annotations

import pytest

from backend.api import websocket as ws_module
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
from backend.game.rules import apply_play
from backend.store import memory_store as store


@pytest.fixture(autouse=True)
def reset_store():
    store._rooms.clear()
    yield
    store._rooms.clear()


def _make_final_trick_game() -> tuple[GameState, Card]:
    """Manche NS/Cœur 80, 7 plis déjà joués, il ne reste que la carte de WEST
    à jouer pour compléter le 8e et dernier pli."""
    bid = Bid(Position.NORTH, 80, is_capot=False, trump=Trump.NO_TRUMP)
    contract = Contract(bid, Double.NONE, Team.NORTH_SOUTH)
    last_card = Card(Suit.SPADES, Rank.SEVEN)
    current_trick = Trick(
        cards=[
            TrickCard(Position.NORTH, Card(Suit.HEARTS, Rank.ACE)),
            TrickCard(Position.EAST, Card(Suit.HEARTS, Rank.KING)),
            TrickCard(Position.SOUTH, Card(Suit.HEARTS, Rank.QUEEN)),
        ]
    )
    round_state = RoundState(
        number=1,
        dealer=Position.WEST,
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
        players={
            Position.NORTH: "alice",
            Position.EAST: "bob",
            Position.SOUTH: "carol",
            Position.WEST: "dave",
        },
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=1000,
        round=round_state,
        phase=GamePhase.BIDDING,
        winner=None,
        last_result=None,
        messages=[],
    )
    return game, last_card


def test_last_trick_completes_the_round_into_scoring_phase_not_a_new_deal():
    game, last_card = _make_final_trick_game()
    game, status = apply_play(game, last_card)
    assert status == "round_end"
    assert game.round is not None
    # Toujours la manche 1 : la manche suivante n'a pas encore été distribuée.
    assert game.round.number == 1
    assert game.round.phase == GamePhase.SCORING
    assert game.round.current_player is None
    # Le dernier pli (4 cartes + gagnant) reste intact et consultable.
    assert len(game.round.tricks) == 8
    assert len(game.round.tricks[-1].cards) == 4
    assert game.round.tricks[-1].winner is not None
    assert game.last_result is not None


async def test_advance_after_scoring_deals_the_next_round_after_the_delay(monkeypatch):
    monkeypatch.setattr(ws_module, "SCORING_DISPLAY_SECONDS", 0)
    game, last_card = _make_final_trick_game()
    game, _ = apply_play(game, last_card)
    await store.set_game(game)

    await ws_module._advance_after_scoring(game.room_id)

    updated = await store.get_game(game.room_id)
    assert updated is not None
    assert updated.round is not None
    assert updated.round.phase == GamePhase.BIDDING
    assert updated.round.number == 2


async def test_advance_after_scoring_is_a_noop_if_the_round_already_moved_on(monkeypatch):
    monkeypatch.setattr(ws_module, "SCORING_DISPLAY_SECONDS", 0)
    game, last_card = _make_final_trick_game()
    game, _ = apply_play(game, last_card)
    assert game.round is not None
    game.round.phase = GamePhase.BIDDING  # déjà avancée par ailleurs
    await store.set_game(game)

    await ws_module._advance_after_scoring(game.room_id)

    updated = await store.get_game(game.room_id)
    assert updated is not None and updated.round is not None
    assert updated.round.number == 1  # pas de double avance
