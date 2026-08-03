"""Tests pour les joueurs IA (EasyBot) et la pompe de tours `_run_bots`."""

from __future__ import annotations

import random

import pytest

from backend.api import websocket as ws_module
from backend.game import rules
from backend.game.bots import EasyBot, make_bot
from backend.game.models import (
    GamePhase,
    GameState,
    Position,
    Team,
    Trump,
)


def _new_game(players: dict[Position, str], bots: set[str]) -> GameState:
    return GameState(
        room_id="room-bots",
        players=dict(players),
        scores={Team.NORTH_SOUTH: 0, Team.EAST_WEST: 0},
        target_score=500,
        round=None,
        phase=GamePhase.BIDDING,
        winner=None,
        last_result=None,
        messages=[],
        bots=set(bots),
    )


ALL_BOTS = {
    Position.NORTH: "🤖 Bot 1",
    Position.EAST: "🤖 Bot 2",
    Position.SOUTH: "🤖 Bot 3",
    Position.WEST: "🤖 Bot 4",
}


def _round_in_play(seed: int) -> GameState:
    """Manche avec un contrat forcé à 80 ♥, prête à jouer."""
    random.seed(seed)
    game = _new_game(ALL_BOTS, set(ALL_BOTS.values()))
    game = rules.start_new_round(game)
    game, _ = rules.apply_bid(game, 80, False, Trump.HEARTS)
    game, _ = rules.apply_pass(game)
    game, _ = rules.apply_pass(game)
    game, _ = rules.apply_pass(game)
    assert game.round is not None
    assert game.round.phase == GamePhase.PLAYING
    return game


def test_easybot_choose_card_is_always_legal_full_round():
    """Sur plusieurs donnes, chaque carte choisie est légale et la manche se joue
    entièrement (8 plis) sans coup illégal."""
    bot = EasyBot()
    for seed in range(40):
        game = _round_in_play(seed)
        plays = 0
        while game.round is not None and game.round.phase == GamePhase.PLAYING:
            r = game.round
            legal = rules.get_legal_plays(r)
            assert r.current_player is not None
            card = bot.choose_card(r, r.current_player)
            assert card in legal, f"seed={seed}: {card} pas dans {legal}"
            game, err = rules.apply_play(game, card)
            assert err in ("ok", "round_end")
            plays += 1
            assert plays <= 32
        assert plays == 32  # 8 plis × 4 joueurs


def test_easybot_choose_bid_respects_legality():
    """L'enchère du bot est toujours légale : soit passe, soit ouvre à 80 sur une
    couleur normale quand le contrat est vierge."""
    bot = EasyBot()
    for seed in range(60):
        random.seed(seed)
        game = _new_game(ALL_BOTS, set(ALL_BOTS.values()))
        game = rules.start_new_round(game)
        r = game.round
        assert r is not None and r.current_bidder is not None
        actions = rules.get_legal_bid_actions(r, r.current_bidder)
        decision = bot.choose_bid(r, r.current_bidder)
        if decision.kind == "bid":
            assert decision.value == 80
            assert actions["min_bid_value"] == 80
            assert decision.trump in (
                Trump.HEARTS,
                Trump.DIAMONDS,
                Trump.CLUBS,
                Trump.SPADES,
            )
        else:
            assert decision.kind == "pass"
            assert actions["can_pass"] is True


def test_easybot_bids_on_a_strong_hand():
    """Une main très forte à ♥ (J,9,A,10 d'atout + as latéraux) doit déclencher une
    ouverture, pas un passe."""
    from backend.game.models import Card, Rank, Suit, Trick

    strong = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    game = _new_game(ALL_BOTS, set(ALL_BOTS.values()))
    game = rules.start_new_round(game)
    r = game.round
    assert r is not None and r.current_bidder is not None
    r.hands[r.current_bidder] = strong
    # remet un tour d'enchères vierge (start_new_round n'a pas de contrat)
    r.current_trick = Trick()
    decision = EasyBot().choose_bid(r, r.current_bidder)
    assert decision.kind == "bid"
    assert decision.trump == Trump.HEARTS


def test_make_bot_returns_easybot():
    assert isinstance(make_bot("easy"), EasyBot)
    with pytest.raises(KeyError):
        make_bot("nope")


@pytest.mark.asyncio
async def test_run_bots_advances_turn_until_human(monkeypatch):
    """Avec 2 humains (N,S) et 2 bots (E,W), quand c'est au tour d'un bot d'enchérir,
    `_run_bots` joue son coup et rend la main à un humain."""
    from backend.store import memory_store as store

    monkeypatch.setattr(ws_module, "BOT_MOVE_DELAY", 0)

    players = {
        Position.NORTH: "alice",
        Position.EAST: "🤖 Bot 2",
        Position.SOUTH: "carol",
        Position.WEST: "🤖 Bot 4",
    }
    game = _new_game(players, {"🤖 Bot 2", "🤖 Bot 4"})
    game = rules.start_new_round(game)
    r = game.round
    assert r is not None
    r.current_bidder = Position.EAST  # au tour du bot
    await store.set_game(game)

    await ws_module._run_bots(game.room_id)

    updated = await store.get_game(game.room_id)
    assert updated is not None and updated.round is not None
    # Le bot Est a agi (historique non vide) et le tour est revenu à un humain.
    assert len(updated.round.bid_history) >= 1
    assert updated.round.current_bidder in (Position.NORTH, Position.SOUTH)
    await store.delete_room(game.room_id)
