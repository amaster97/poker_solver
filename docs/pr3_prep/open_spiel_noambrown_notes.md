# open_spiel + noambrown HUNL representation — notes

## Summary (3 sentences)

`open_spiel/universal_poker` is the kitchen-sink reference: a full ACPC wrapper that models 2-10 player no-limit HE with chance nodes, multiple betting abstractions (FC / FCPA / FCHPA / FULLGAME), explicit pot/spent vectors, and a tensor-encoded info state — but ~95% of the state-machine logic is delegated to the opaque ACPC C library, which we cannot port directly and which leaks a `mutable` API throughout. `noambrown_poker_solver` is the polar opposite: a *river-only* (one-street) subgame representation with a tiny ~25-field state, public-history-only infoset keys, pot-fraction bet sizing, and the entire tree pre-built at construction — exactly the shape we want for PR3 minus the four-street logic. For our HUNL state we should mostly follow Brown's River shape (contrib vector + pot + bet-size list + public history string), borrow open_spiel's *round transition* and *first-to-act* rules from leduc_poker.cc, and adopt Brown's tree-pre-builder pattern but stretch the State to carry a `round_index` + `board_cards` slot.

## State struct fields (from each repo)

### open_spiel universal_poker

The class `UniversalPokerState` (universal_poker.h:104-212) is a thin shell — almost everything lives in `acpc_state_`.

| Field | open_spiel name | noambrown name | Our planned name | Purpose |
|---|---|---|---|---|
| Pot / spent per player | `acpc_state_.spent[p]` (RawACPCState; see CurrentSpent at acpc_game.cc:245-248) | `contrib: Tuple[int,int]` (river_holdem.py:121) | `contrib: [u32; 2]` | Per-player money committed this hand |
| Stacks | game-level `acpc_game_.stack[p]` (acpc_game.cc:160-164) | game-level `stacks: Tuple[int,int]` (river_holdem.py:151) | game-level `starting_stacks: [u32; 2]` | Starting stacks; remaining = stack - contrib |
| Pot base (rake-free starting pot) | derived `MaxSpend() * (numPlayers - NumFolded())` (universal_poker.cc:548-549) | `base_pot: int` (river_holdem.py:150) | `base_pot: u32` | For river subgames: chips already in pot from earlier streets |
| Current player | `acpc_state_.CurrentPlayer()` -> uint8 (acpc_game.cc:208-210) | `player: int \| None` (river_holdem.py:122) | `cur_player: i8` (-1 = terminal, -2 = chance) | Whose turn |
| Round / street | `acpc_state_.round` (raw struct field, see GetRound() at acpc_game.h:143) | `round_index: int` (leduc.py:18; river doesn't have one — it's single-street) | `round: u8` (0=preflop, 1=flop, 2=turn, 3=river) | Which street we're on |
| Folded flag per player | `acpc_state_.playerFolded[p]` (universal_poker.cc:1168) | `terminal_winner: int \| None` (river_holdem.py:125) | `folded: [bool; 2]` | Did this player fold |
| Terminal winner | derived (NumFolded == N-1, else showdown) | `terminal_winner: int \| None` (river_holdem.py:125) | `terminal_winner: Option<u8>` | Set on fold; `None` means showdown |
| Hole cards | `acpc_state_.holeCards[p][c]` (raw, in RawACPCState; see HoleCards() at universal_poker.cc:782-817) | game-level `hands[player]: List[Hand]` (river_holdem.py:162-173) — state carries an *index* into the range | `hole_cards: [[u8; 2]; 2]` or `hand_index: [u16; 2]` (range-style) | Each player's private cards |
| Board cards | `acpc_state_.boardCards[c]` (RawACPCState; see board_cards() at acpc_game.h:113-116) | game-level `board: List[int]` (river_holdem.py:149) — fixed at construction (river-only) | `board: [u8; 5]` with `board_cards_dealt: u8` | Community cards |
| Action history | `actionSequence_: std::string` (universal_poker.h:196) — chars 'd','f','c','p','a' indexed by `actions[]` at universal_poker.cc:1561; plus `actionSequenceSizings_: vector<int>` (universal_poker.h:197) | `history: Tuple[str,...]` (river_holdem.py:120) — strings like `"c"`, `"b500"`, `"r200"` | `history: SmallVec<ActionToken; 16>` (one per round, or a flat Vec) | Full betting record |
| Per-round history (alternate) | `acpc_state_.action[round][i]`, `acpc_state_.numActions[round]` (BettingSequence at acpc_game.cc:265-272) | n/a (river is one round) | `round_history: [Vec<ActionToken>; 4]` (Leduc-style — see leduc_poker.h:200-201) | Per-round action list, easier infoset key |
| Num calls / raises this round | computed each call from raw state | `checks: int`, `raises: int` (river_holdem.py:123-124) — note: river `raises` includes opening bet | `num_raises_this_round: u8`, `num_calls_this_round: u8` | Round-transition trigger |
| Hole/board cards dealt counter | `hole_cards_dealt_: int`, `board_cards_dealt_: int` (universal_poker.h:186-187) | n/a (river: all cards pre-dealt) | `hole_cards_dealt: u8`, `board_cards_dealt: u8` | For chance-node sequencing |
| Possible-actions bitmask | `possibleActions_: uint32_t` (universal_poker.h:195) with `StateActionType` flags (universal_poker.h:64-70) | n/a — recomputed each call by `legal_actions()` (river_holdem.py:211-275) | `possible_actions: u8` bitmask | Caches `_CalculateActionsAndNodeType()` result |
| Betting abstraction tag | `betting_abstraction_` (universal_poker.h:199) — enum `BettingAbstraction` | game-level (`bet_sizes`, `include_all_in`, `max_raises`) | game-level — same | Which abstraction we're solving |
| Deck (remaining cards) | `deck_: logic::CardSet` (universal_poker.h:185) | game-level `_legal_cache` / hands pre-filtered by board (river_holdem.py:175-192) | `deck: u64` (52-bit) or computed from `board ∪ holes` | Cards still available to chance |
| Cached legal actions | n/a (recomputed) | `_legal_cache: Dict[history, List[Action]]`, `_next_cache: Dict[(history,action), RiverState]` (river_holdem.py:164-165) | Optional — only if hot path | Memoizes the action-enumeration |
| Subgame reach probabilities | `handReaches_: vector<double>` (universal_poker.h:206) — 2×1326 = 2652 floats for HUNL | game-level `hand_weights[player]: List[float]` (river_holdem.py:163) | game-level `range_weights: [Vec<f32>; 2]` | For continual-resolving / subgame solving |

### noambrown_poker_solver Python (`RiverState`, river_holdem.py:118-126)

```python
@dataclass(frozen=True)
class RiverState:
    history: Tuple[str, ...]      # ("c", "b500", "r1000", ...)
    contrib: Tuple[int, int]      # per-player chips committed
    player: int | None            # None = terminal
    checks: int                   # consecutive checks (->terminal at 2)
    raises: int                   # raise count (for max_raises cap)
    terminal_winner: int | None   # set on fold; None on showdown
```

Frozen dataclass → hashable → cacheable. Total ~7 fields. Compare to open_spiel's `UniversalPokerState` whose state lives in an opaque `RawACPCState` struct with ~14 array fields (holeCards, boardCards, spent[], maxSpent, action[round][n], numActions[round], playerFolded[], round, plus more).

### noambrown_poker_solver C++ tree node (`TreeNode`, river_game.h:19-26)

```cpp
struct TreeNode {
    int player = -1;           // -1 = terminal
    int terminal_winner = -1;  // -1 = showdown or non-fold terminal
    int contrib0 = 0;
    int contrib1 = 0;
    int action_count = 0;
    std::vector<int> next;     // child node indices, indexed by action
};
```

This is the *fully pre-built tree* form. Every reachable state in the betting tree gets one `TreeNode`. The internal `State` struct used during the BFS build (river_game.cpp:9-16) carries `{player, terminal_winner, checks, raises, contrib0, contrib1}` — 6 ints, no card info (cards are decoupled).

**Key insight:** Brown's River separates the *betting tree* (TreeNode shape) from the *card distribution* (`hands[player]: Vec<Hand>` with weights). The CFR traverser iterates the betting tree and at each terminal node consults the card-strength tables. Our HUNL state could borrow this — track contributions in the state, leave card payoff calc to a separate evaluator.

### Minimum sufficient encoding for our HUNL state

```rust
struct HunlState {
    // Money
    contrib: [u32; 2],            // chips committed by each player this hand
    // Cards
    hole_cards: [[u8; 2]; 2],     // 0..51 ids, sentinel 0xff = not dealt
    board_cards: [u8; 5],         // first board_cards_dealt entries valid
    hole_cards_dealt: u8,
    board_cards_dealt: u8,
    // Round/turn state
    round: u8,                    // 0=preflop, 1=flop, 2=turn, 3=river
    cur_player: i8,               // 0/1, -1 terminal, -2 chance
    num_calls_this_round: u8,
    num_raises_this_round: u8,
    folded: [bool; 2],
    // Showdown bookkeeping
    terminal_winner: Option<u8>,  // Some(p) on fold-out, None on showdown
}
```

Estimated size: ~30 bytes packed (cf. open_spiel ~100+ bytes via ACPC struct, Brown's River ~40 bytes Python dataclass / ~28 bytes C++ TreeNode).

## Action encoding comparison

### open_spiel: multi-mode

Three coexisting schemes (universal_poker.h:56, 62):

1. **kFCPA (default abstraction)**: 4 action ids — `{0=Fold, 1=Call, 2=Bet (=pot), 3=AllIn}`. Bet means "pot-size bet". (universal_poker.cc:1010-1027)
2. **kFCHPA**: 5 ids — adds `kHalfPot=4`. Plus the implementation accepts *arbitrary* integer bet sizes treated as raise-to amounts. (universal_poker.cc:1028-1033)
3. **kFULLGAME**: integer-valued actions; action id N (where N ≥ 2) means "raise to N chips total" — so the action space size = max stack + 1. (universal_poker.cc:1042-1046, universal_poker.cc:1428-1432)

Translation point: `ApplyChoiceAction(action_type, size)` (universal_poker.cc:1563-1585) sends `{type, size}` to ACPC. Size is **absolute total commitment** for raise-to.

### noambrown: pot-fraction list

Brown uses pot-fraction sizing (river_holdem.py:131-139, 211-275):

```python
bet_sizes: Sequence[float] = (0.5, 1.0)   # 50% pot, pot
include_all_in: bool = True               # always add all-in
max_raises: int = 1000
```

Per-call expansion (river_holdem.py:231-243):
```python
for size in sizes:
    bet_amount = int(round(pot_total * size))
    bet_amount = min(bet_amount, remaining)
    amounts.append(bet_amount)
if include_all_in and remaining > 0:
    amounts.append(remaining)
```

Action representation is a `(label, amount)` pair (river_holdem.py:112-115):
```python
@dataclass(frozen=True)
class Action:
    label: str            # "c" check/call, "f" fold, "b" bet (no-call), "r" raise (after a call)
    amount: int = 0
```

Stored in history as strings like `"c"`, `"f"`, `"b500"`, `"r1000"` (river_holdem.py:346-348). Critically, for raises the `amount` is the *extra beyond the call* (river_holdem.py:259-269); contribution is updated as `contrib[player] += to_call + raise_amount` (river_holdem.py:342). Bets (no prior call needed) just add `amount`.

Per-player, per-spot raise-size overrides exist (river_holdem.py:133-139):
- `oop_first_bets`, `ip_first_bets`, `oop_first_raises`, `ip_first_raises`, `oop_next_raises`, `ip_next_raises`

These allow the solver to use a coarser sizing for higher-raise spots — a standard solver pruning move.

### Recommendation for our HUNL

Adopt Brown's `(label, amount)` action with pot-fraction *generation* but **store absolute commitment** internally (open_spiel style) — pot-fractions drift through float rounding across rounds and we don't want to recompute. Concretely:

```rust
enum Action {
    Fold,
    CheckCall,
    Raise { to_total: u32 },     // absolute "raise-to-N" commitment
}
```

Generate the set of raise targets via `bet_sizes: &[f32]` × pot at the call site (i.e., during `legal_actions()`), but freeze the integer amount into the Action variant so transitions are deterministic.

## Infoset key encoding

### open_spiel (universal_poker.cc:545-568)

```cpp
return absl::StrFormat(
    "[Round %i][Player: %i][Pot: %i][Money: %s][Private: %s][Public: %s][Sequences: %s]",
    acpc_state_.GetRound(),       // round 0..3
    CurrentPlayer(),              // acting player
    pot,                          // computed: maxSpend * (N - folded)
    money,                        // space-joined remaining stacks
    HoleCards(player).ToString(), // private cards visible to `player` only
    BoardCards().ToString(),      // public board
    sequences);                   // "/" joined per-round betting strings, e.g. "cc/r200c/cc/"
```

Per-round betting strings come from `acpc_state_.BettingSequence(r)` (acpc_game.cc:265-272), e.g. `"cr200c"`.

The *tensor* infoset (universal_poker.cc:411-499) is layered: player one-hot + private one-hot over deck + board one-hot over deck + abstracted action sequence (2 bits/action) + integer sizings.

### noambrown river (river_holdem.py:206-209)

```python
def infoset_key(self, state: RiverState, player: int) -> str:
    if not state.history:
        return "root"
    return "/".join(state.history)
```

The infoset key is **public history alone**. Private cards are handled separately via a per-hand strategy table — the MCCFR trainer combines them at lookup (river_mccfr.py:119):

```python
hand_key = self._hand_key(self.game.hands[player][hand_index].cards)
key = f"p{player}:{hand_key}|{self.game.infoset_key(state, player)}"
```

So the *full* infoset key is `player:hand|history` — but `infoset_key()` on the game only returns the history piece. The split lets you reuse the public game tree across many hand pairs.

### noambrown leduc (leduc.py:205-209)

```python
def infoset_key(self, state: LeducState, player: int) -> str:
    card_rank = state.cards[player][0]
    board_rank = state.board[0] if state.board is not None else -1
    board_str = RANK_TO_STR[board_rank] if board_rank >= 0 else "-"
    return f"{RANK_TO_STR[card_rank]}{board_str}|{state.history}"
```

Leduc bakes both private and public cards directly into the key. Compact for a 6-card deck; not feasible for HUNL where private is 1326 hands × 4-board permutations.

### open_spiel leduc (leduc_poker.cc:517-520 + observer at leduc_poker.cc:198-239)

The observer-based infostate string:
```
[Observer: <pid>][Private: <card>][Round <r>][Player: <pid>][Pot: <pot>][Money: ...]
[Public: <card>][Round1: <a1 a2 ...>][Round2: <a1 a2 ...>]
```

So they also key on `(private, public, history)` with separators between rounds.

### Recommendation

Follow **Brown's split**: `infoset_key(state, player) -> public_only_string` and let the solver combine `(hand_idx, public_key)` at lookup. This:
- enables shared betting-tree traversal across all hand pairs (key for vectorized CFR)
- matches our existing Leduc shape in `poker_solver/games/leduc.py` (or wherever we have it)
- keeps the key small enough for `HashMap<String, InfosetData>` to stay cheap

Format:
```
"R<round>/<round0_history>|<round1_history>|<round2_history>|<round3_history>"
```
e.g. `"R2/cc|r200c|c"` for "preflop check-check, flop raise-200 call, turn check".

## Round transition rules

### open_spiel: delegated to ACPC + leduc reference

The ACPC server handles all of this opaquely; we can only read the surface:

- **First-to-act per round** is configurable via `firstPlayer` array (e.g., `"2 1 1 1"` for HUNL — SB acts first preflop, BB acts first postflop). See HUNL config at universal_poker_test.cc:179-183.
- **Round transitions** happen automatically inside `acpc_state_.DoAction()` (universal_poker.cc:1582), then `_CalculateActionsAndNodeType()` (universal_poker.cc:1587-1662) checks if a board card needs dealing → sets `cur_player_ = kChancePlayerId` and `possibleActions_ = ACTION_DEAL`.

The leduc reference (which we can read) at leduc_poker.cc:680-691 is much clearer:

```cpp
bool LeducState::ReadyForNextRound() const {
  return ((num_raises_ == 0 && num_calls_ == remaining_players_) ||
          (num_raises_ > 0 && num_calls_ == (remaining_players_ - 1)));
}

void LeducState::NewRound() {
  SPIEL_CHECK_EQ(round_, 1);
  round_++;
  num_raises_ = 0;
  num_calls_ = 0;
  cur_player_ = kChancePlayerId;  // Public card.
}
```

First-to-act on a new round is determined by `NextPlayer()` (leduc_poker.cc:573-591) starting from `starting_player_ - 1`:

```cpp
player_to_start_search_from = (starting_player_ + num_players_ - 1) % num_players_;
// ... then loop forward to find first non-folded player.
```

For HUNL postflop, the "starting player" is the BB (out of position) — so we hardcode: preflop SB acts first; postflop BB acts first.

### noambrown river: single round (terminates within one street)

River-only state machine (river_holdem.py:299-336):

- **Check-check terminal**: `checks >= 2` → `player = None`, `terminal_winner = None` (showdown).
- **Bet/call terminal**: after a bet, opponent calls → `player = None`, `terminal_winner = None` (showdown).
- **Fold**: → `player = None`, `terminal_winner = 1 - player`.

No multi-street transitions; this is a subgame solver. The pot-base is given at construction.

### Leduc-style state machine we should adopt for HUNL

```
Round-end condition (per round):
  (num_raises == 0 AND both players checked)
  OR
  (num_raises > 0 AND the non-raiser called).

On round end:
  if round < 3:   // preflop, flop, turn
    round += 1
    num_calls = num_raises = 0
    cur_player = CHANCE   // deal 1 or 3 board cards
  else:           // river complete -> showdown
    cur_player = TERMINAL
```

**Postflop first-to-act = BB (player 1 in HUNL convention).** Preflop first-to-act = SB (player 0, the button in heads-up). Blinds are posted at game start before any decision — SB posts small_blind, BB posts big_blind, both into `contrib[]`.

## Showdown logic

### open_spiel universal_poker (CalculateOdds at universal_poker.cc:1162-1263 for chance-deal-out + universal_poker.cc:1051-1055 for terminal)

Terminal payoffs in open_spiel come from ACPC's `valueOfState`, which we don't have source for here. But `CalculateOdds()` shows the algorithm:

1. For each active (non-folded) player, build a 7-card set `{hole ∪ board}`.
2. Call `hand_plus_board.RankCards()` (CardSet method) to get an integer rank.
3. Highest rank wins; ties split.
4. Pot split: winner gets full pot; ties split evenly (universal_poker.cc:1242-1248).

### open_spiel leduc (leduc_poker.cc:628-678)

```cpp
void LeducState::ResolveWinner() {
  if (remaining_players_ == 1) {
    // Walkover: only non-folded player gets pot
    for (Player p = 0; p < num_players_; p++) {
      if (!folded_[p]) {
        winner_[p] = true;
        money_[p] += pot_;
        return;
      }
    }
  } else {
    // Showdown: rank each non-folded hand, find best, split among ties
    int best_hand_rank = -1;
    for (Player p = 0; p < num_players_; p++) {
      if (!folded_[p]) {
        int rank = RankHand(p);
        if (rank > best_hand_rank) {
          best_hand_rank = rank;
          // ... clear winners, set p as sole winner
        } else if (rank == best_hand_rank) {
          // ... add p as co-winner
        }
      }
    }
    for (Player p = 0; p < num_players_; p++) {
      if (winner_[p]) money_[p] += pot_ / num_winners_;
    }
  }
}
```

### noambrown river (river_holdem.py:361-367, river_mccfr.py:86-100)

```python
def terminal_payout(self, state: RiverState, player: int) -> float:
    pot_total = self.pot_total(state)
    if state.terminal_winner is not None:
        # Fold case: winner is set, opponent loses contrib
        if state.terminal_winner == player:
            return float(pot_total - state.contrib[player])
        return float(-state.contrib[player])
    # Showdown case: caller resolves via hand strengths
    return float(pot_total / 2.0 - state.contrib[player])  # default = chop
```

Then the trainer (river_mccfr.py:94-100) overrides with hand-strength comparison:

```python
p0_strength = self.game.hands[0][p0_index].strength
p1_strength = self.game.hands[1][p1_index].strength
if p0_strength == p1_strength:
    return float(pot_total / 2.0 - contrib)
if (p0_strength > p1_strength) == (player == 0):
    return float(pot_total - contrib)
return float(-contrib)
```

The `Strength` is a 6-tuple `(category, kicker1, kicker2, ...)` computed by `evaluate_7` (river_holdem.py:94-102 Python; cards.cpp:168-187 C++). Categories: 0=high card, 1=pair, 2=two-pair, ..., 8=straight flush. Lexicographic comparison gives correct ordering.

### Recommendation

- Adopt Brown's `Strength` tuple = `(category: u8, kicker1..5: u8)` for the river evaluator.
- Net payoff convention: `payoff(player) = pot - contrib[player]` if player wins, `-contrib[player]` if loses, `pot/2 - contrib[player]` on chop. (Zero-sum holds: `payoff(0) + payoff(1) == 0`.)
- We can copy `evaluate_5` and `evaluate_7` from `cards.cpp:66-187` essentially verbatim (MIT license — see attribution section).

## Memory footprint per state object

| Repo | Per-state size (approx) | Notes |
|---|---|---|
| open_spiel `UniversalPokerState` | ~150-200 bytes object + heap (`actionSequence_` string, `actionSequenceSizings_` vector, `deck_` 64-bit, `handReaches_` vector if subgame) | Plus the entire `RawACPCState` (~200 bytes — holeCards[10][3] + boardCards[7] + spent[10] + action[4][N] + numActions[4] + playerFolded[10] + round, etc.) |
| open_spiel `LeducState` | ~80 bytes object + ~3 small vectors | private_cards_ (~16B), money_ (~16B Vec<double>), ante_ (~16B), round1/2_sequence_ (small Vec) |
| noambrown Python `RiverState` (frozen dataclass) | ~250 bytes (Python overhead) but logically ~50 bytes of data | `history: Tuple[str,...]` is the dominant cost as it grows |
| noambrown C++ `TreeNode` | 24 bytes + `vector<int> next` (~24B overhead + 4B/child) | Pre-built tree: one node per reachable history |

For a Rust HUNL state with the minimum encoding suggested above:
- Packed: ~28-32 bytes for the fixed fields, plus `Vec<ActionToken>` history (4B/entry × max ~8 actions/round × 4 rounds = ~128B worst case).
- Total: ~150 bytes typical.

If we pre-build the tree (Brown's approach), per-node is ~32B + child pointer list. For HUNL with 4 streets, all-in shoves only, and 2-3 bet sizings per spot, the tree is on the order of 10^4-10^5 nodes — easily fits in RAM.

## Specific patterns / code to port (with attribution headers we'd add)

The license terms permit code reuse with attribution. Both repos (noambrown MIT @ `noambrown_poker_solver/LICENSE:1-21`; open_spiel Apache 2.0 @ `open_spiel/LICENSE`) require:
1. Including the license text or a copyright notice in derivative files.
2. Stating any changes we made.

Suggested attribution header for any ported file:

```rust
// Copyright 2025 Noam Brown (MIT License).
// Adapted from noambrown/poker_solver, river_holdem.py / river_game.cpp.
// Modifications: ported Python/C++ -> Rust; extended to 4-street HUNL; ...
// See references/code/noambrown_poker_solver/LICENSE for original terms.
```

```rust
// Portions adapted from DeepMind OpenSpiel (Apache License 2.0).
// Source: open_spiel/games/leduc_poker/leduc_poker.cc lines NNN-MMM.
// See https://github.com/google-deepmind/open_spiel for the original.
```

### Patterns worth porting

1. **Brown's `RiverState` dataclass shape** — river_holdem.py:118-126 (license: MIT)
   - Frozen 7-field record: `history`, `contrib`, `player`, `checks`, `raises`, `terminal_winner`.
   - We extend with `round`, `board_cards`, `hole_cards_dealt`, `board_cards_dealt`, `folded` for multi-street HUNL.
   - Why: minimal, hashable, no opaque pointers — ideal for Rust port.

2. **Brown's pot-fraction action generator** — river_holdem.py:211-275, river_game.cpp:31-107 (license: MIT)
   - Code to port verbatim (translated to Rust):
     ```python
     # river_holdem.py:231-243 — the bet-sizing block
     for size in sizes:
         bet_amount = int(round(pot_total * size))
         if bet_amount <= 0: continue
         bet_amount = min(bet_amount, remaining)
         if bet_amount > 0: amounts.append(bet_amount)
     if self.include_all_in and remaining > 0:
         amounts.append(remaining)
     for amount in sorted(set(amounts)):
         if amount > 0: actions.append(Action("b", amount))
     ```
   - And the raise variant at river_holdem.py:257-273.
   - Why: this is the exact pattern we need for sizing discretization.

3. **Brown's `Strength` tuple + `evaluate_5`/`evaluate_7`** — cards.cpp:66-187 (license: MIT)
   - 6-element array, lexicographic ordering, category-then-kicker.
   - C++ implementation is straightforward and we can port to Rust line-by-line.
   - Why: avoids a heavyweight dependency on a hand evaluator crate for the first pass.

4. **Brown's tree-pre-builder** — river_game.cpp:253-303 (license: MIT)
   - BFS over states, building `TreeNode { player, terminal_winner, contrib0, contrib1, next: Vec<NodeId> }`.
   - Tracks `max_depth` and `max_actions` to size scratch buffers.
   - Why: vectorized CFR wants a flat array of nodes; this is the canonical build.

5. **open_spiel Leduc's round-end check + new-round** — leduc_poker.cc:680-691 (license: Apache 2.0)
   - The `ReadyForNextRound` predicate is the cleanest expression of round closure.
   - Direct copy with attribution; tighten to 2-player HUNL.
   - Why: open_spiel's universal_poker delegates to ACPC; Leduc has the readable canonical form.

6. **open_spiel Leduc's `NextPlayer` with `starting_player_` parameter** — leduc_poker.cc:573-591 (license: Apache 2.0)
   - Generic "skip folded players starting from configured starting player" loop.
   - Why: lets us configure preflop = SB-first, postflop = BB-first without a switch statement everywhere.

7. **open_spiel Leduc's `ResolveWinner` showdown algorithm** — leduc_poker.cc:628-678 (license: Apache 2.0)
   - Walkover case (one non-folded player) + multi-way showdown with co-winner detection.
   - Why: handles ties and split pots correctly; our river evaluator drops into the rank() slot.

8. **Brown's split infoset key** — river_holdem.py:206-209 + river_mccfr.py:119 (license: MIT)
   - `infoset_key(state, player) -> public_string`; private key composed at solver call site.
   - Why: enables vectorized "all hands sharing the same betting node" CFR — the core optimization for large games.

9. **Brown's first-bets/raises per-street sizing overrides** — river_holdem.py:131-139 (license: MIT)
   - Optional `oop_first_bets`, `ip_first_bets`, etc. that fall back to a default `bet_sizes`.
   - Why: standard solver tuning knob — coarser sizing on later raises.

10. **open_spiel's `firstPlayer` per-round array idea** — universal_poker.cc:170 ACPC param (license: Apache 2.0)
    - In HUNL: `"firstPlayer": "2 1 1 1"` means SB acts first preflop (acpc 1-indexed: player 2 = SB after the button posts), BB acts first on flop/turn/river.
    - Why: clean way to encode the SB/BB-first asymmetry without ad-hoc round branches.

## What our HUNL state needs that's NOT in these refs

1. **Multi-street rake/blind handling.** Neither repo computes rake. Brown's river starts with a pre-set `base_pot`; open_spiel handles blinds via the ACPC `blind[]` array but the blind-posting itself is opaque inside ACPC. We need to model "SB posts X, BB posts Y" explicitly at hand start — a 4-line `start_hand()` that fills `contrib[]` and sets `cur_player = 0` (SB acts first preflop).

2. **Side pots.** Neither HUNL ref needs side pots (Brown is 2p subgame, open_spiel handles N-player via ACPC). For 2-player HUNL with one player short-stack going all-in, we technically need to cap the side pot at the smaller stack. Both refs implicitly assume equal effective stacks — Brown via single `stack` field (river_game.h:38), open_spiel via the ACPC `valueOfState` we don't have visibility into. We should write our own side-pot logic.

3. **All-in semantics on a partial call.** When P0 shoves $500 but P1 only has $300, P1's all-in call ≠ $500 raise; only $300 enters the matched pot. None of the refs model this for our case — we need it.

4. **Card abstraction / bucketing.** Brown stores the full 1326-hand range per player as `hands[player]: Vec<Hand>` with strength tuples (river_holdem.py:162-173). For multi-street HUNL we need a bucketing scheme (e.g., k-means on hand-strength distribution). Out of scope for PR3 but worth a flag.

5. **Action abstraction transitions.** Both Brown and open_spiel pick *one* abstraction at game creation and stick with it. Real-world HUNL solvers often use coarser sizing in deep nodes and finer near terminals. The leaf abstraction logic we want isn't in either ref.

6. **Continual resolving / re-solving entry points.** open_spiel has `handReaches_` (universal_poker.h:206) for entering at a subgame — that's their nod toward continual resolving. Brown's `RiverHoldemGame` IS effectively a subgame solver but doesn't expose re-entry. PR3 doesn't need this but the state should be re-enterable from arbitrary contrib/board configs.

7. **Deterministic state hash for caching.** Brown's `RiverState` is a frozen Python dataclass with auto-derived `__hash__`. In Rust we'd implement `Hash` manually over the structured fields — neither ref shows this explicitly.

8. **Per-round `Vec<Action>` rather than one flat history string.** Brown uses a single tuple; open_spiel uses both flat (`actionSequence_`) and per-round (`acpcState_.action[round][i]`). For HUNL infoset keys per-round is much cleaner — we should adopt the leduc shape (leduc_poker.h:200-201).

## Open questions

1. **Action representation as enum-with-amount vs flat `u32` action id?** Brown uses `(label, amount)`; open_spiel uses a flat integer (which is 0/1 for fold/call and the raise-to size for everything else in FULLGAME mode). Rust idiom favors the enum but the flat form is faster for hashing if we end up needing to use the action as a HashMap key. Default: enum.

2. **Where does the deck live — state or game?** Brown has hand sets at the game level (no chance nodes during play because river is single-street, all cards pre-dealt). Open_spiel keeps `deck_` per-state because it needs chance nodes for the flop/turn/river cards. For multi-street HUNL we need chance nodes, so deck must be in state — but it's just `52 - len(hole_cards ∪ board)`, so we can compute it lazily from cards instead of storing.

3. **Do we need the open_spiel `ObservationTensor` shape?** Universal_poker emits an observation tensor (universal_poker.cc:501-543) that's a function of `(player, cards, board, contributions)`. We don't need this for a tabular CFR core but if we ever go neural we'll want it. Probably defer to a later PR.

4. **Should we follow Brown's *pre-built tree* pattern or open_spiel's *recursive state* pattern?** Brown's tree builder (river_game.cpp:253-303) creates every reachable state up front, indexes by `NodeId`. Open_spiel recreates the state by replaying history. Pre-built is faster for repeated traversal (CFR is many traversals); recursive is more memory-efficient and simpler. For PR3 I'd recommend recursive (mirror leduc), then a `Tree::build()` helper as an optimization in PR4+.

5. **What's our showdown evaluator floor?** Brown's `evaluate_7` is O(21 × evaluate_5) ≈ 21 × O(few hundred ops) = ~thousands of ops per terminal eval. For ~10^4 terminals × 10^4 iterations × 10^3 hand pairs that's expensive — we may want a precomputed lookup table à la 2+2 evaluator (not in either ref).

6. **Folded-player encoding for HUNL.** With 2 players, "one folded ⇒ terminal" — so we never have a folded player AND a betting round in progress at the same time. We could drop the `folded` field entirely and just set `terminal_winner = 1 - p` on fold. Brown does this (river_holdem.py:287-296); leduc keeps `folded_[]` because it generalizes to N players. For pure HUNL Brown's shape is tighter.

7. **Where does our `Strength` evaluator live — state or evaluator service?** Brown computes strengths *eagerly* at game-construction time for all hands in range (river_holdem.py:190-191). For PR3 multi-street, the board isn't known at game-time (only at river dealt), so we evaluate lazily. Question: cache evaluated strengths in state, or compute fresh on each showdown? Likely lazy + per-call (matches our state-immutable design).

8. **Stack tracking — net or per-player remaining?** Open_spiel stores `money[p] = stack - spent[p]` and updates both (leduc_poker.cc:702-706). Brown stores only `contrib[]` and lets `remaining = stack - contrib[player]` be derived (river_holdem.py:219). Derived is cleaner — adopt Brown's.
