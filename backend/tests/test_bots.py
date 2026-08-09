"""Tests pour les joueurs IA (Easy/MediumBot) et la pompe de tours `_run_bots`."""

from __future__ import annotations

import random

import pytest

from backend.api import websocket as ws_module
from backend.game import rules
from backend.game.bots import EasyBot, MediumBot, make_bot
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


def test_make_bot_returns_expected_level():
    assert isinstance(make_bot("easy"), EasyBot)
    assert isinstance(make_bot("medium"), MediumBot)
    with pytest.raises(KeyError):
        make_bot("nope")


# ─── MediumBot ──────────────────────────────────────────────────────────────


def _bidding_round(contract: Contract | None, current_bidder: Position) -> RoundState:
    """RoundState minimal en phase BIDDING (mains vides — surchargées par le test)."""
    return RoundState(
        number=1,
        dealer=Position.NORTH,
        hands={p: [] for p in Position},
        phase=GamePhase.BIDDING,
        current_bidder=current_bidder,
        pass_count=0,
        bid_history=[],
        contract=contract,
        current_player=None,
        tricks=[],
        current_trick=Trick(),
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )


def _playing_round(
    trump: Trump,
    bidding_team: Team,
    hands: dict[Position, list[Card]],
    current_trick: Trick,
    current_player: Position,
) -> RoundState:
    contract = Contract(
        Bid(Position.NORTH, 80, False, trump), Double.NONE, bidding_team
    )
    return RoundState(
        number=1,
        dealer=Position.NORTH,
        hands=hands,
        phase=GamePhase.PLAYING,
        current_bidder=None,
        pass_count=0,
        bid_history=[],
        contract=contract,
        current_player=current_player,
        tricks=[],
        current_trick=current_trick,
        belote_team=None,
        belote_king_played=False,
        belote_queen_played=False,
    )


def test_mediumbot_choose_card_always_legal_full_round():
    bot = MediumBot()
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
        assert plays == 32


def test_mediumbot_choose_bid_respects_legality():
    bot = MediumBot()
    for seed in range(80):
        random.seed(seed)
        game = _new_game(ALL_BOTS, set(ALL_BOTS.values()))
        game = rules.start_new_round(game)
        r = game.round
        assert r is not None and r.current_bidder is not None
        actions = rules.get_legal_bid_actions(r, r.current_bidder)
        d = bot.choose_bid(r, r.current_bidder)
        if d.kind == "bid":
            assert d.value is not None and 80 <= d.value <= 160 and d.value % 10 == 0
            assert actions["min_bid_value"] is not None
            assert d.value >= actions["min_bid_value"]
        elif d.kind == "contre":
            assert actions["can_contre"] is True
        elif d.kind == "surcontre":
            assert actions["can_surcontre"] is True
        else:
            assert d.kind == "pass"


def test_mediumbot_bids_proportionally_on_strong_hand():
    """Main forte (J,9,A,10 ♥ + 2 as latéraux) → ouvre au-dessus de 80 à ♥."""
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
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = strong
    d = MediumBot().choose_bid(r, Position.EAST)
    assert d.kind == "bid"
    assert d.trump == Trump.HEARTS
    assert d.value is not None and d.value > 80


def test_mediumbot_opens_on_a_decent_hand():
    """Main correcte sans être monstre (9,A ♥ + 2 as latéraux ≈ 52 pts en main) :
    trop faible seule pour 80, mais l'apport partenaire doit la faire ouvrir.
    Régression : avant PARTNER_ALLOWANCE le bot ne prenait quasi jamais."""
    decent = [
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.EIGHT),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = decent
    d = MediumBot().choose_bid(r, Position.EAST)
    assert d.kind == "bid"
    assert d.value == 80


def test_mediumbot_passes_on_weak_hand():
    weak = [
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.EIGHT),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
        Card(Suit.CLUBS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.EIGHT),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.SPADES, Rank.EIGHT),
    ]
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = weak
    assert MediumBot().choose_bid(r, Position.EAST).kind == "pass"


def test_mediumbot_feeds_partner_when_last_to_play():
    """Partenaire (NORD) maître du pli, SUD 4e à jouer et ne peut pas fournir →
    défausse libre : SUD balance sa carte la plus chère à son partenaire."""
    trick = Trick(
        cards=[
            TrickCard(Position.WEST, Card(Suit.HEARTS, Rank.SEVEN)),
            TrickCard(Position.NORTH, Card(Suit.HEARTS, Rank.ACE)),  # partenaire maître
            TrickCard(Position.EAST, Card(Suit.HEARTS, Rank.EIGHT)),
        ]
    )
    south_hand = [
        Card(Suit.SPADES, Rank.TEN),  # 10 pts
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    hands = {
        Position.NORTH: [],
        Position.EAST: [],
        Position.WEST: [],
        Position.SOUTH: south_hand,
    }
    r = _playing_round(Trump.CLUBS, Team.EAST_WEST, hands, trick, Position.SOUTH)
    assert rules.current_trick_winner(trick, Trump.CLUBS) == Position.NORTH
    card = MediumBot().choose_card(r, Position.SOUTH)
    assert card == Card(Suit.SPADES, Rank.TEN)


def test_mediumbot_opens_100_on_ladder_tier():
    """4 atouts, 2 honneurs (V,9), 1 as latéral protégé (♠ A,7) → palier 100 de la
    grille (ne remplit pas la condition ``protected_aces >= 2`` du palier 110)."""
    hand = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.EIGHT),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.EIGHT),
    ]
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = hand
    d = MediumBot().choose_bid(r, Position.EAST)
    assert d.kind == "bid"
    assert d.trump == Trump.HEARTS
    assert d.value == 100


def test_mediumbot_opens_130_on_ladder_tier():
    """5 atouts, 2 honneurs, belote, 1 as latéral protégé → palier 130 de la grille."""
    hand = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.SEVEN),
    ]
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = hand
    d = MediumBot().choose_bid(r, Position.EAST)
    assert d.kind == "bid"
    assert d.trump == Trump.HEARTS
    assert d.value == 130


def test_mediumbot_picks_highest_ladder_tier_between_suits():
    """♠ (4 atouts, 2 honneurs → palier 90) doit l'emporter sur ♦ (3 atouts, 2
    honneurs → palier 80) : la grille choisit la couleur au palier le plus élevé."""
    hand = [
        Card(Suit.SPADES, Rank.JACK),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.SPADES, Rank.EIGHT),
        Card(Suit.DIAMONDS, Rank.JACK),
        Card(Suit.DIAMONDS, Rank.NINE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.SEVEN),
    ]
    r = _bidding_round(None, Position.EAST)
    r.hands[Position.EAST] = hand
    d = MediumBot().choose_bid(r, Position.EAST)
    assert d.kind == "bid"
    assert d.trump == Trump.SPADES
    assert d.value == 90


def test_mediumbot_contres_strong_defense_on_high_contract():
    """Contrat adverse élevé (130 ♥ par NORD/NS) + EST tient une main forte à ♥ →
    EST (défense) coinche."""
    contract = Contract(
        Bid(Position.NORTH, 130, False, Trump.HEARTS), Double.NONE, Team.NORTH_SOUTH
    )
    r = _bidding_round(contract, Position.EAST)
    r.hands[Position.EAST] = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    actions = rules.get_legal_bid_actions(r, Position.EAST)
    assert actions["can_contre"] is True
    assert MediumBot().choose_bid(r, Position.EAST).kind == "contre"


@pytest.mark.asyncio
async def test_run_bots_applies_contre(monkeypatch):
    """Un bot défenseur dont c'est le tour coinche un gros contrat adverse via la pompe."""
    from backend.store import memory_store as store

    monkeypatch.setattr(ws_module, "BOT_MOVE_DELAY", 0)

    players = {
        Position.NORTH: "alice",
        Position.EAST: "🤖 Bot 2",
        Position.SOUTH: "carol",
        Position.WEST: "🤖 Bot 4",
    }
    game = _new_game(players, {"🤖 Bot 2", "🤖 Bot 4"})
    contract = Contract(
        Bid(Position.NORTH, 130, False, Trump.HEARTS), Double.NONE, Team.NORTH_SOUTH
    )
    game.round = _bidding_round(contract, Position.EAST)
    game.round.hands[Position.EAST] = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    await store.set_game(game)

    await ws_module._run_bots(game.room_id)

    updated = await store.get_game(game.room_id)
    assert updated is not None and updated.round is not None
    assert updated.round.contract is not None
    assert updated.round.contract.double == Double.CONTRE
    await store.delete_room(game.room_id)


@pytest.mark.asyncio
async def test_run_bots_applies_volee_contre_out_of_turn(monkeypatch):
    """OUEST (bot, défense) tient une main assassine à ♥ mais ce n'est pas son tour
    (c'est au tour d'EST, humain, de parler juste après l'annonce de NORD) : le bot
    doit contrer "à la volée" tout de suite, sans attendre que la rotation lui
    revienne — comme un humain peut déjà le faire (cf. `_dispatch`)."""
    from backend.store import memory_store as store

    monkeypatch.setattr(ws_module, "BOT_MOVE_DELAY", 0)

    players = {
        Position.NORTH: "alice",
        Position.EAST: "carol",
        Position.SOUTH: "dave",
        Position.WEST: "🤖 Bot 4",
    }
    game = _new_game(players, {"🤖 Bot 4"})
    contract = Contract(
        Bid(Position.NORTH, 130, False, Trump.HEARTS), Double.NONE, Team.NORTH_SOUTH
    )
    game.round = _bidding_round(contract, Position.EAST)  # tour d'EST, humain
    game.round.hands[Position.WEST] = [
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.HEARTS, Rank.TEN),
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
    ]
    await store.set_game(game)

    await ws_module._run_bots(game.room_id)

    updated = await store.get_game(game.room_id)
    assert updated is not None and updated.round is not None
    assert updated.round.contract is not None
    assert updated.round.contract.double == Double.CONTRE
    # EST (humain, tour normal) n'a rien joué entre-temps : OUEST a coinché
    # immédiatement, avant que la rotation ne lui revienne naturellement.
    assert len(updated.round.bid_history) == 1
    assert updated.round.bid_history[0].position == Position.WEST
    assert updated.round.bid_history[0].action == "contre"
    assert updated.round.current_bidder == Position.NORTH  # NEXT_PLAYER[WEST]
    await store.delete_room(game.room_id)


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
