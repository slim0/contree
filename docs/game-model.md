# Modèle de Jeu — Belote Contrée

> Ce document est la référence pour l'implémentation du moteur de jeu.  
> Toute divergence entre ce document et le code est un bug.

---

## 1. Entités du domaine

### Enumerations

```python
class Suit(Enum):
    SPADE   = "spade"    # Pique
    HEART   = "heart"    # Cœur
    DIAMOND = "diamond"  # Carreau
    CLUB    = "club"     # Trèfle

class Trump(Enum):
    SPADE    = "spade"
    HEART    = "heart"
    DIAMOND  = "diamond"
    CLUB     = "club"
    NO_TRUMP = "no_trump"   # Sans Atout
    ALL_TRUMP = "all_trump" # Tout Atout

class Rank(Enum):
    SEVEN = "7"
    EIGHT = "8"
    NINE  = "9"
    TEN   = "10"
    JACK  = "J"   # Valet
    QUEEN = "Q"   # Dame
    KING  = "K"   # Roi
    ACE   = "A"   # As

class Position(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST  = "east"
    WEST  = "west"

class Team(Enum):
    NORTH_SOUTH = "north_south"
    EAST_WEST   = "east_west"

class BidValue(Enum):
    V80    = 80
    V90    = 90
    V100   = 100
    V110   = 110
    V120   = 120
    V130   = 130
    V140   = 140
    V150   = 150
    V160   = 160
    CAPOT  = "capot"

class Double(Enum):
    NONE        = "none"
    CONTRE      = "contre"
    SURCONTRE   = "surcontre"

class GamePhase(Enum):
    WAITING     = "waiting"    # salle d'attente, joueurs pas encore tous connectés
    DEALING     = "dealing"    # distribution en cours
    BIDDING     = "bidding"    # enchères
    PLAYING     = "playing"    # jeu de la carte
    SCORING     = "scoring"    # calcul du score
    FINISHED    = "finished"   # partie terminée
```

---

### Structures de données

```python
@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

@dataclass
class Bid:
    value: BidValue
    trump: Trump
    team: Team
    player: Position

@dataclass
class Contract:
    bid: Bid
    double: Double = Double.NONE

    @property
    def multiplier(self) -> int:
        return {Double.NONE: 1, Double.CONTRE: 2, Double.SURCONTRE: 4}[self.double]

@dataclass
class TrickCard:
    player: Position
    card: Card

@dataclass
class Trick:
    cards: list[TrickCard]      # dans l'ordre de jeu
    winner: Position | None     # None tant que le pli n'est pas complet
    led_suit: Suit | None       # couleur de l'entame

    @property
    def is_complete(self) -> bool:
        return len(self.cards) == 4

@dataclass
class BeloteAnnounce:
    team: Team
    player: Position

@dataclass
class RoundResult:
    contract: Contract
    points: dict[Team, int]     # points bruts (avant arrondi)
    final_scores: dict[Team, int]  # après arrondi et résolution chute/réussite
    contract_made: bool
    is_capot: bool

@dataclass
class RoundState:
    dealer: Position
    hands: dict[Position, list[Card]]
    contract: Contract | None
    tricks: list[Trick]
    current_trick: Trick | None
    belote: BeloteAnnounce | None
    phase: GamePhase
    # Tour de parole
    current_player: Position
    bid_history: list[tuple[Position, BidValue | None]]  # None = passe

@dataclass
class GameState:
    players: dict[Position, str]   # position → player_id
    scores: dict[Team, int]
    target_score: int
    rounds: list[RoundResult]
    current_round: RoundState | None
    phase: GamePhase
    winner: Team | None
```

---

## 2. Machine à états

### États de la partie (GamePhase)

```
WAITING
  │  (4 joueurs connectés)
  ▼
DEALING  ←──────────────────────────────────────────┐
  │  (distribution terminée)                         │
  ▼                                                  │
BIDDING                                              │
  │  (3 passes après enchère, ou surcontre)          │
  ├── contrat fixé ──────────────────────────────►  PLAYING
  │                                                   │
  └── 4 passes sans enchère ──────────────────────►  DEALING (nouveau donneur)
                                                      │
                                                      │ (8 plis joués)
                                                      ▼
                                                    SCORING
                                                      │
                                                      ├── score cible non atteint ──► DEALING
                                                      │
                                                      └── score cible atteint ──────► FINISHED
```

### États d'un pli (dans PLAYING)

```
TRICK_START
  │  (entame : joueur courant joue une carte)
  ▼
WAITING_FOR_CARD (joueur 2)
  ▼
WAITING_FOR_CARD (joueur 3)
  ▼
WAITING_FOR_CARD (joueur 4)
  ▼
TRICK_COMPLETE
  │  (calcul du gagnant)
  ▼
TRICK_START (gagnant entame) | SCORING (si c'était le 8e pli)
```

---

## 3. Règles de validité d'une carte

Fonction centrale du moteur : `is_legal(card, player, round_state) -> bool`

```
Entrées :
  card         : Card tentée
  player       : Position du joueur
  round_state  : RoundState courant

Logique (dans l'ordre) :

1. Si le pli est vide (entame) → LÉGAL

2. Récupérer led_suit = couleur de l'entame du pli courant
   trump = round_state.contract.bid.trump

3. Si trump == ALL_TRUMP :
   → toutes les couleurs sont atout
   → la carte doit battre la meilleure carte en place si le joueur le peut
   → voir règle de montée (§ 3.1)

4. Si trump == NO_TRUMP :
   → pas d'atout, pas de coupe possible
   → si joueur possède led_suit : doit jouer led_suit
   → sinon : défausse libre

5. Cas normal (trump = une couleur) :

   a. Si joueur possède led_suit ET led_suit != trump :
      → doit jouer led_suit

   b. Si joueur ne possède pas led_suit :
      - partner_winning = partenaire maître du pli courant
      - Si partner_winning : défausse libre (y compris atout)
      - Sinon :
        - Si joueur possède atout :
          - doit jouer atout
          - voir règle de montée (§ 3.1)
        - Sinon : défausse libre

   c. Si led_suit == trump :
      → joueur doit fournir atout
      → voir règle de montée (§ 3.1)

§ 3.1 Règle de montée à l'atout
  best_trump_in_trick = meilleur atout actuellement en jeu
  
  Si best_trump_in_trick est joué par le PARTENAIRE et que le joueur
  n'a QUE de l'atout → pas d'obligation de monter (jouer atout inférieur OK)
  
  Sinon :
    Si joueur possède un atout > best_trump_in_trick :
      → doit jouer un atout supérieur
    Sinon :
      → peut jouer n'importe quel atout (inférieur)
```

---

## 4. Calcul du score d'une donne

### Points des cartes

```python
TRUMP_POINTS = {
    Rank.JACK:  20,
    Rank.NINE:  14,
    Rank.ACE:   11,
    Rank.TEN:   10,
    Rank.KING:   4,
    Rank.QUEEN:  3,
    Rank.EIGHT:  0,
    Rank.SEVEN:  0,
}

NORMAL_POINTS = {
    Rank.ACE:   11,
    Rank.TEN:   10,
    Rank.KING:   4,
    Rank.QUEEN:  3,
    Rank.JACK:   2,
    Rank.NINE:   0,
    Rank.EIGHT:  0,
    Rank.SEVEN:  0,
}

NO_TRUMP_POINTS = {
    Rank.ACE:   19,   # différence clé
    Rank.TEN:   10,
    Rank.KING:   4,
    Rank.QUEEN:  3,
    Rank.JACK:   2,
    Rank.NINE:   0,
    Rank.EIGHT:  0,
    Rank.SEVEN:  0,
}

ALL_TRUMP_POINTS = {
    Rank.JACK:  13,
    Rank.NINE:   9,
    Rank.ACE:    6,
    Rank.TEN:    5,
    Rank.KING:   3,
    Rank.QUEEN:  2,
    Rank.EIGHT:  0,
    Rank.SEVEN:  0,
}
```

### Invariants de score

| Contrat | Total points | Dix de der |
|---------|-------------|------------|
| Normal  | 162         | 10         |
| Capot   | 252         | 100        |

### Algorithme de score (points faits)

```
1. Calculer raw_points[team] pour chaque équipe :
   = somme des cartes dans les plis
   + dix de der (10 ou 100)
   + belote si annoncée par cette équipe

2. Déterminer contract_made :
   - Capot : les preneurs ont tous les 8 plis
   - Normal : raw_points[preneurs] >= contract.bid.value

3. Si contract_made :
   final_score[preneurs]   = round_to_ten(raw_points[preneurs])
   final_score[défenseurs] = round_to_ten(raw_points[défenseurs])

4. Si chute :
   final_score[preneurs]   = 0
   # la belote des preneurs change de camp
   belote_bonus = 20 if belote annoncée by preneurs else 0
   total = round_to_ten(162 ou 252) + belote_bonus
   final_score[défenseurs] = total * contract.multiplier
   # Note : belote_bonus NON multipliée

5. round_to_ten(x) = round(x / 10) * 10
   # Python : round(85/10)*10 = 90, round(84/10)*10 = 80 ✓
```

---

## 5. Ordre de force des cartes

Fonction : `card_strength(card, trump, led_suit) -> int`  
Retourne un entier comparable : plus grand = plus fort.

```
Si trump est une couleur :
  Si card.suit == trump :
    ordre atout : J(7) > 9(6) > A(5) > 10(4) > K(3) > Q(2) > 8(1) > 7(0)
  Sinon si card.suit == led_suit :
    ordre normal : A(7) > 10(6) > K(5) > Q(4) > J(3) > 9(2) > 8(1) > 7(0)
  Sinon :
    force = 0 (ne peut pas gagner)

Si trump == NO_TRUMP :
  Si card.suit == led_suit :
    ordre SA : A(7) > 10(6) > K(5) > Q(4) > J(3) > 9(2) > 8(1) > 7(0)
  Sinon : force = 0

Si trump == ALL_TRUMP :
  ordre TA : J(7) > 9(6) > A(5) > 10(4) > K(3) > Q(2) > 8(1) > 7(0)
  (toutes couleurs — les cartes de led_suit battent les autres à égalité de rang)
  → en pratique : même rang, led_suit gagne sur les autres couleurs
```

---

## 6. Événements WebSocket

### Serveur → Client

| Événement | Payload | Déclencheur |
|-----------|---------|-------------|
| `game.state` | `GameState` partiel (main cachée des adversaires) | connexion / reconnexion |
| `round.started` | `dealer`, `hand` du joueur | nouvelle donne |
| `bidding.update` | `bids[]`, `current_player` | après chaque action d'enchère |
| `contract.set` | `Contract` | fin du tour d'enchères |
| `card.played` | `player`, `card`, `trick_state` | après chaque carte jouée |
| `trick.complete` | `winner`, `points_in_trick` | fin d'un pli |
| `round.scored` | `RoundResult` | fin de la donne |
| `game.over` | `winner`, `final_scores` | fin de partie |
| `error` | `code`, `message` | action illégale |

### Client → Serveur

| Événement | Payload | Contexte |
|-----------|---------|----------|
| `bid.place` | `value`, `trump` | phase BIDDING |
| `bid.pass` | — | phase BIDDING |
| `bid.contre` | — | phase BIDDING |
| `bid.surcontre` | — | phase BIDDING |
| `card.play` | `card` (rank + suit) | phase PLAYING |
| `belote.announce` | `type` ("belote"\|"rebelote") | phase PLAYING |

---

## 7. Questions ouvertes / décisions à prendre

- [x] **Carrés SA/TA en POC ?** — Les carrés bonus (4 As = 200 pts) sont-ils inclus dès le POC ? Complexité non négligeable.
Je ne souhaite pas jouer avec les annonces (carrés, suites, etc.). Excepté pour le belote.
- [x] **Score cible par défaut** — 1000 pts ? 500 pts ? À configurer à la création de la room.
Commençons avec 1000 pts. Nous verrons plus tard si besoin de rendre cela configurable.
- [x] **Reconnexion** — Comportement si un joueur se déconnecte en cours de partie ?
La partie est en attente que le joueur se reconnecte.
- [x] **Timeout de jeu** — Délai maximum pour jouer une carte en POC ?
Pour le moment nous ne mettrons un délai très long (10 minutes) et nous verrons plus tard pour le réduire.
