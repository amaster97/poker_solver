# PR 3 spec — HUNL tree builder + action abstraction (Python tier)

## Goal

Implement an unabstracted Heads-Up No-Limit Hold'em (HUNL) game tree builder in the Python reference tier, plumbed through the existing `Game` protocol, with a reusable bet-size action-abstraction module that produces a fixed 6-size action menu (33% / 75% / 100% / 150% / 200% pot + all-in) under a preflop 4-cap / postflop 3-cap raise policy. The tree is *cards-unabstracted* (PR 4 lands card abstraction) and *unsolved at full scale* (PR 5 solves it); PR 3 lands the data structures, the rules engine, and enough partial enumeration / tiny-subtree exercise to prove the tree is well-formed.

## What PR 3 does NOT do

- **Card abstraction** — PR 4. Private/public cards are stored as raw `Card` objects on each state; the infoset key is the lossless string form. PR 4 will plug in a bucket layer behind the same `infoset_key` interface.
- **Rust port** — PR 6 (and only after PR 5's Python solve lands). No Rust code touched in PR 3.
- **Solving full HUNL** — PR 5. The tree is too big for the Python DCFR loop in `dcfr.py` (~10^14 unabstracted infosets); we only exercise it on tiny subtrees (river-only HUNL, all-in-only preflop, or a fixed flop with stacks pre-shoved). Whole-tree enumeration tests use **node counts**, not full traversal.
- **UI** — PR 10.
- **Public chance sampling, NEON SIMD, perf work** — PR 7+.
- **Continuous bet sizes / merging close bets** — fixed menu only; postflop-solver's `merging_threshold` and dynamic `add_allin_threshold` / `force_allin_threshold` are intentionally *not* ported in PR 3 (keep the abstraction simple and inspectable).
- **Rake** — set to 0 in PR 3. The `HUNLConfig` schema accepts a rake field but the tree builder asserts `rake_rate == 0.0` and `rake_cap == 0.0` for now; PR 9 can wire it through.
- **Donk-bet menus / per-street size overrides** — postflop-solver allows different bet menus on flop / turn / river and a separate donk menu; PR 3 uses the single 6-size menu uniformly on every postflop street and every position. Per-street tuning is deferred to PR 9 when preflop lands.

## Files to create

- `poker_solver/hunl.py` — `HUNLState` dataclass + `HUNLPoker` class implementing the `Game` protocol. Also exposes the `HUNLConfig` dataclass used to parameterize a tree (stacks, blinds, starting street, board cards if any, rake placeholders).
- `poker_solver/action_abstraction.py` — pure-functional bet-size menu + raise-cap helpers. Stateless, no `Game` coupling. Tested independently.
- `tests/test_hunl_core.py` — rules invariants for `HUNLPoker` (15–20 tests).
- `tests/test_hunl_tree.py` — tree structure invariants (depth, branching, terminal coverage, blind/pot arithmetic across a deep walk).
- `tests/test_action_abstraction.py` — bet-size menu and raise-cap correctness in isolation (no `HUNLPoker` import).

## Files to modify

- `poker_solver/__init__.py` — re-export `HUNLPoker`, `HUNLState`, `HUNLConfig`, and the public action-abstraction symbols (`ActionAbstractionConfig`, `enumerate_legal_actions`, `BetSizing`).
- `poker_solver/cli.py` — extend `_GAMES` mapping to include `"hunl"`; instantiate `HUNLPoker` with a default `HUNLConfig` (100 BB, river-only with a fixed flop, see "CLI behavior" below). Solve attempts on `--game hunl` with default iterations and the unabstracted tree raise `NotImplementedError("HUNL full-game solve lands in PR 5; use --hunl-mode river_subgame for a tiny exercise.")`. The `--hunl-mode` flag is **added in PR 3** with two values: `tiny_subgame` (solve a hand-picked tiny subtree) and `full` (raise `NotImplementedError`). Default is `tiny_subgame`.
- `tests/test_leduc_dcfr.py`, `tests/test_kuhn_dcfr.py` — **not modified.** Existing 97 tests must pass unchanged.

## HUNLState fields

| Field | Type | Purpose |
|---|---|---|
| `hole_cards` | `tuple[tuple[Card, Card], tuple[Card, Card]] \| tuple[()]` | P0 + P1 hole cards. Empty tuple until dealt; populated by chance nodes preflop. |
| `board` | `tuple[Card, ...]` | Community cards (0 preflop, 3 flop, 4 turn, 5 river). Mutable across street transitions via chance nodes. |
| `street` | `Street` (IntEnum: PREFLOP=0, FLOP=1, TURN=2, RIVER=3, SHOWDOWN=4) | Current street. |
| `contributions` | `tuple[int, int]` | Total chips put in pot by each player across all streets, in units of *cents* (integer scaled chips — see "Units" below). Updated on every action that adds chips. |
| `stacks` | `tuple[int, int]` | Remaining chips behind for each player. `stacks[i] = starting_stack[i] - contributions[i]`. Maintained explicitly to keep traversal O(1) (rather than re-derived from `starting_stack - contributions`). Asserted consistent in tests. |
| `street_history` | `tuple[ActionId, ...]` | Sequence of *action ids* (see "Action encoding") on the current street. Reset to `()` on each street transition. Used to compute infoset keys and raise-cap state. |
| `street_aggressor` | `int` | The player who made the last aggressive action (bet/raise) on the current street, or `-1` if the street is still in the check / chance phase. |
| `street_num_raises` | `int` | Number of bets+raises on the current street so far (the cap is checked against this). |
| `to_call` | `int` | Chips the current player must add to call, i.e. `contributions[street_aggressor] - contributions[current_player]` if `street_aggressor >= 0`, else 0. |
| `cur_player` | `int` | Player to act, or `-1` for chance / terminal. |
| `folded` | `tuple[bool, bool]` | Per-player folded flag. Tied to terminality via fold path. |
| `all_in` | `tuple[bool, bool]` | Per-player all-in flag. A player is all-in when `stacks[i] == 0`. When both all-in (or one all-in and the other called), remaining streets run out as chance nodes only — see "All-in run-out". |
| `config` | `HUNLConfig` | Frozen reference to the immutable tree configuration. Stored on the state so `HUNLPoker.utility / current_player / legal_actions` are pure functions of the state without needing to traverse back to the root config. |

All fields are immutable; `apply()` returns a new state via `dataclasses.replace` (matches the existing Kuhn/Leduc style).

### Units

All chip values are stored as **integer cents** scaled from big blinds. Convention: **1 BB = 100 cents.** SB = 50 cents, BB = 100 cents. Default 100 BB starting stack = 10000 cents. This is integer-only arithmetic for the entire tree so raise amounts, pot fractions, and all-in calculations remain deterministic and hashable. Output displays divide by 100 to show fractional BBs. *No floating-point chip arithmetic anywhere in `hunl.py` or `action_abstraction.py`.*

### `HUNLConfig` dataclass (frozen)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `starting_stack` | `int` | `10_000` (= 100 BB) | Symmetric for both players. (Asymmetric stacks supported by passing a tuple; default symmetric.) |
| `small_blind` | `int` | `50` | In cents. P0 = SB, P1 = BB (heads-up convention). |
| `big_blind` | `int` | `100` | In cents. |
| `ante` | `int` | `0` | Per-player ante in cents (each player posts this in addition to their blind). Default 0 disables. When non-zero, initial contributions become `(small_blind + ante, big_blind + ante)` and starting pot = `small_blind + big_blind + 2*ante`. Tree shape, branching, and infoset count are **unchanged** by ante — only the absolute pot/bet amounts shift. |
| `starting_street` | `Street` | `Street.PREFLOP` | Allows trees starting flop / turn / river for solving subgames (matches postflop-solver's `initial_state` field). |
| `initial_board` | `tuple[Card, ...]` | `()` | Required-non-empty when `starting_street > PREFLOP`. e.g. 3-card flop for `Street.FLOP`. |
| `initial_pot` | `int` | `0` | When `starting_street > PREFLOP`, the pot already invested before the subgame begins (e.g. preflop went check-call so pot = 2 BB). When `starting_street == PREFLOP`, must be 0 (blinds are posted by the tree). |
| `initial_contributions` | `tuple[int, int]` | `(0, 0)` | For subgame starts: how much each player has contributed pre-subgame. Must sum to `initial_pot`. |
| `preflop_raise_cap` | `int` | `4` | Per "Action menu locked" — preflop allows 4 raises (bet/3-bet/4-bet/5-bet); the 5th aggression force-jams. |
| `postflop_raise_cap` | `int` | `3` | Postflop allows 3 raises (bet/raise/3-bet); the 4th aggression force-jams. |
| `bet_size_fractions` | `tuple[float, ...]` | `(0.33, 0.75, 1.00, 1.50, 2.00)` | Pot fractions, in order. All-in is a separate menu item appended last. |
| `include_all_in` | `bool` | `True` | Whether all-in is always available as a 6th option. |
| `rake_rate` | `float` | `0.0` | Placeholder; **must be 0.0 in PR 3** (asserted). |
| `rake_cap` | `int` | `0` | Placeholder; **must be 0 in PR 3** (asserted). |
| `force_allin_threshold` | `int` | `1` | If remaining stack after the proposed bet/raise is `<= force_allin_threshold * big_blind`, snap to all-in. Set to `1` BB in PR 3; postflop-solver uses a pot-relative threshold but a simple stack-absolute threshold is sufficient here. |
| `min_bet_bb` | `int` | `1` | Minimum legal opening bet on a street = 1 BB (NLHE rule). |

The config is hashable (`frozen=True, eq=True`) so it can serve as a dict key and is safely shared across infoset traversal.

## Action encoding

Action IDs are integers (matching the `Action = int` type used by Kuhn/Leduc), but with a richer payload:

```
ACTION_FOLD     = 0
ACTION_CHECK    = 1   # only legal when to_call == 0
ACTION_CALL     = 2   # only legal when to_call > 0
ACTION_BET_33   = 3   # pot-fractional, only when to_call == 0
ACTION_BET_75   = 4
ACTION_BET_100  = 5
ACTION_BET_150  = 6
ACTION_BET_200  = 7
ACTION_RAISE_33 = 8   # pot-fractional on top of call, only when to_call > 0
ACTION_RAISE_75 = 9
ACTION_RAISE_100 = 10
ACTION_RAISE_150 = 11
ACTION_RAISE_200 = 12
ACTION_ALL_IN   = 13
```

This is a flat enum so a `legal_actions(state) -> list[int]` call returns a subset of the 14 IDs above. The `Game` protocol's `Action = int` contract is satisfied without modification.

### How bet sizes map to action ids

Two action *families* (Bet and Raise) share the same five pot fractions but compute their chip amounts differently:

- **Bet (opening a street, `to_call == 0`):** `bet_amount = round_to_chip(pot * fraction)`, where `pot = sum(contributions) + initial_pot_for_subgame`. The full contribution becomes `contributions[player] + bet_amount` (the player pays the whole `bet_amount`; opponent owes that as `to_call`).
- **Raise (facing a bet/raise, `to_call > 0`):** `raise_to = max_bet_in_pot + round_to_chip(pot_after_call * fraction)`, where `max_bet_in_pot = contributions[street_aggressor]` and `pot_after_call = pot + to_call`. This is the same convention as `postflop-solver/src/action_tree.rs:633` (pot-relative raise on top of a call). The player's new total contribution becomes `raise_to`; the chips they add to the pot this action = `raise_to - contributions[player]`.

Rounding: `round_to_chip(x) = round(x)` (banker's rounding via Python's built-in `round`, since `x` is already integer-arithmetic from integer pot × float fraction). Documented in the function docstring.

### Min-bet / min-raise rules

NLHE legal rules (enforced by `action_abstraction.enumerate_legal_actions`):

1. **Minimum opening bet:** 1 BB (`config.min_bet_bb * config.big_blind`). If a pot-fractional bet rounds below this, it's clamped up to 1 BB. If two bet fractions clamp to the same chip amount, **the duplicate is dropped** (deduped — never two abstracted actions with identical chip outcomes).
2. **Minimum raise:** raise amount (chips added to last bet/raise) must be at least as large as the last bet/raise increment. If a pot-fractional raise rounds below this, it's clamped up. Same dedup rule.
3. **Maximum bet/raise:** the player's stack. If the abstracted amount exceeds stack-remaining, it's replaced by `ACTION_ALL_IN`.
4. **All-in absorption:** if after clamping a `ACTION_BET_X` or `ACTION_RAISE_X` ends up equal to the player's max (full stack), it is *replaced* by `ACTION_ALL_IN` (not also listed separately). This guarantees `ACTION_ALL_IN` appears at most once in the legal-action list.
5. **Force-all-in threshold:** if the player's remaining stack *after* a proposed bet/raise is `<= config.force_allin_threshold * big_blind` (default 1 BB), the action is snapped to all-in (replacing the original). This collapses near-shove abstractions onto the canonical all-in node.

### Raise cap enforcement

Per the locked decision in PLAN.md: **preflop 4-cap, postflop 3-cap.**

Definition of "raise count" on a street:

- `street_num_raises = 0` at street start.
- `ACTION_BET_*` and `ACTION_ALL_IN` (when `to_call == 0`) each increment by 1 (these are *opening bets*; they count toward the cap).
- `ACTION_RAISE_*` and `ACTION_ALL_IN` (when `to_call > 0`) each increment by 1.
- `ACTION_CHECK`, `ACTION_CALL`, `ACTION_FOLD` do not increment.

Cap behavior at `street_num_raises == cap`:
- The acting player **cannot raise** (no `ACTION_RAISE_*` actions emitted). They may only fold or call.
- **All-in is still legal** at the cap (so a 4-cap preflop allows a 5-bet jam). This matches postflop-solver's pattern: the cap restricts intermediate raise sizes but all-in is always a terminal action option. *(Decision note: this differs from a strict "cap = no more aggression at all." The user's PLAN.md text "After cap, next aggressive action forces all-in" implies all-in remains legal post-cap; we encode that as: at-cap → no raises, but `ACTION_ALL_IN` available.)*

The cap counter is per-street (resets to 0 on chance node street transitions). Cap = preflop 4 or postflop 3 chosen by `state.street`.

## Street transitions

After both players have acted and matched contributions (or one has folded), the street transitions:

- **Preflop → Flop:** chance node deals 3 community cards. Action transitions to the **out-of-position** player (P1 = BB = OOP postflop in HU). `street_history` resets; `street_num_raises` resets; `street_aggressor` resets to `-1`.
- **Flop → Turn:** chance node deals 1 community card. OOP acts first.
- **Turn → River:** chance node deals 1 community card. OOP acts first.
- **River end → Showdown:** terminal.

**Heads-up positional convention** (locked): **P0 = small blind = button (acts first preflop, last postflop). P1 = big blind (acts last preflop, first postflop).** Matches the convention in `noambrown_poker_solver/cpp/src/river_game.cpp` and standard HUNL.

### All-in run-out

When one or both players are all-in *and* the betting on the current street is matched, remaining streets are dealt as chance-only run-outs (no more player decisions). Concretely: after the all-in is called or a check-down ends the street, future "street start" emits chance outcomes (deal next card), then immediately re-enters another chance node until the river is dealt, then transitions to showdown. No `cur_player >= 0` state is reached during run-out.

## Chance outcomes

- **Preflop hole-card dealing:** the tree's chance node at the root deals **both players' hands simultaneously** as a single chance outcome over `C(52, 2) * C(50, 2) = 1,624,350` ordered combinations. This is too large to enumerate; we represent it lazily.
  - `chance_outcomes(state)` returns the full list only when called; tests use small fixed samples.
  - For PR 3 we expose the chance outcomes as `list[tuple[Action, float]]` where `Action` is encoded as a packed integer `(card0_p0 << 24) | (card1_p0 << 16) | (card0_p1 << 8) | card1_p1` and each outcome has uniform probability. **This is intentionally clunky** — PR 4's card abstraction will replace it with bucket-pair chance outcomes.
  - A helper `enumerate_preflop_chance(state)` is provided that yields outcomes lazily as a generator; `chance_outcomes` materializes to a list for `Game`-protocol conformance.
- **Postflop board cards:** each remaining card in the deck (excluding hole cards + already-dealt board) with uniform probability. Action encoding: card id as integer `(rank << 4) | suit` matching `Card`'s natural integer form.
- **All-in run-out:** when the next chance node is a board card after an all-in, the same uniform-board mechanic applies.

The chance-outcome lists for postflop are small (50 cards on turn, 49 on river) so they materialize fully.

### Card → integer mapping

`Card(rank, suit)` → `card_int = (rank * 4) + suit`, range `[8, 59]` since rank ∈ [2, 14] and suit ∈ [0, 3]. (`rank=2 → 8`, `rank=14, suit=3 → 59`.) This mapping is also added as a top-level helper `card_to_int(card) -> int` / `int_to_card(card_int) -> Card` in `poker_solver/card.py` (a 5-line addition, not a new file). The mapping is **stable** across PRs so the Rust port in PR 6 can reuse it.

## Terminal states + utility

Three terminal categories:

1. **Fold:** one player folds. The non-folding player wins the pot. `utility = (winner_gain_in_BB, -winner_gain_in_BB)` from P0's perspective, where `winner_gain` = opponent's total contribution (not pot, since the winner gets their own chips back). Stored as float in big blinds.
2. **Showdown after river:** evaluate via `poker_solver.evaluator.evaluate(player_hand + board)`. Higher rank wins, ties split. `utility = (P0_gain_BB, -P0_gain_BB)`.
3. **All-in showdown** (both all-in, run-out complete): same as showdown after river — the run-out completes the board to 5 cards then standard evaluator runs.

Utility is in **big-blind units** (floats), to match the Kuhn/Leduc convention (`KuhnPoker.utility` returns floats in ante units). Internal accounting is integer cents; we divide by `config.big_blind` to convert to BB-floats at the terminal.

## Infoset key

Format: `f"{player_hole}|{board}|{street_token}|{betting_history}"`, where:

- `player_hole` = sorted two-card hand string e.g. `"AhKh"` (uppercase rank, lowercase suit, sorted by `(rank, suit)` ascending). Sorting canonicalizes `AhKh` and `KhAh` to the same key — necessary because the player's two cards are unordered.
- `board` = community-card string, e.g. `"7d2c9h"`, sorted by `(rank, suit)` ascending. Empty for preflop infosets.
- `street_token` = `"p"` / `"f"` / `"t"` / `"r"` for preflop/flop/turn/river.
- `betting_history` = compact action-token stream across all streets, `|` separating streets. Tokens:
  - `f` = fold
  - `x` = check
  - `c` = call
  - `b<amount>` = bet, e.g. `b300` for 3 BB (amount in cents, no separator — same convention as `noambrown_poker_solver`'s action token).
  - `r<amount>` = raise (raise-to amount in cents)
  - `A` = all-in
  - Street boundaries marked with `/` (matches postflop-solver style).

Example: `"AhKh||p|b300/x/x/x"` = P0 with AhKh preflop bets 3 BB, called, then checked down on flop/turn/river. (For HUNL we'd actually have board appended; this example is preflop-only-history for illustration.)

**Card hiding:** the infoset for player `p` includes `p`'s hole cards but *not* the opponent's. The board is public so it appears for both players post-flop.

## CLI behavior

`poker-solver solve --game hunl [--hunl-mode {tiny_subgame,full}] [--iterations N]`:

- `--hunl-mode tiny_subgame` (default): construct a hand-picked tiny tree (see "tiny subgame fixture" below) and run the existing Python DCFR for `--iterations` iterations. Print the same output format as the existing Kuhn/Leduc solve (game value, exploitability, average strategy table).
- `--hunl-mode full`: instantiate `HUNLPoker(HUNLConfig())` (100 BB preflop start, no board), then raise `NotImplementedError` with a message pointing to PR 5: `"Full HUNL solve requires card abstraction (PR 4) + scalable solver (PR 5). Use --hunl-mode tiny_subgame for a small exercise."`

### Tiny subgame fixture (default)

Constructed in `hunl.py` as `default_tiny_subgame() -> HUNLConfig` and consumed by the CLI:

- Starting street: river.
- Board: `[Card('A',s), Card('7',c), Card('2',d), Card('K',h), Card('5',s)]` (a dry, paint-heavy, no-straight, no-flush board).
- Initial pot: 1000 cents (10 BB).
- Initial contributions: (500, 500).
- Starting stacks: 1000 cents each (the remaining 10 BB; SPR=1).
- Hole cards: **fixed** at P0=`AhKc`, P1=`Qd Qh` (so it is an effectively cardless game — one hand each, no chance node at the root since hole cards are pre-dealt).
- Bet sizes: full 6-option menu, postflop 3-cap.

This subgame has a single street (river), no chance nodes, and a small number of histories: ~6 opening choices × ~6 raises × cap-limited follow-ups. Estimated infoset count: under 200. Solvable in well under 1 minute with the Python DCFR.

## Critical correctness items

1. **Blinds posted correctly at start.** P0 posts 50, P1 posts 100. `contributions = (50, 100)`, `stacks = (9950, 9900)`. `to_call = 50` for P0 (the SB acts first preflop). `street_num_raises = 1` (the BB counts as the opening "bet" — this is the standard convention and means a preflop limp = call, raise = raise-over-BB, putting the cap at preflop_raise_cap = 4 raises total over the BB).
1b. **Antes posted correctly when `config.ante > 0`.** Both players contribute the ante on top of their blinds: `contributions = (small_blind + ante, big_blind + ante)`, `stacks = (starting_stack - small_blind - ante, starting_stack - big_blind - ante)`. Starting pot = `small_blind + big_blind + 2 * ante`. `to_call` for P0 = `big_blind - small_blind` (the ante portion is symmetric and doesn't affect call amount). All subsequent pot-fraction bet sizes compute relative to this larger pot. **Tree shape, depth, and branching are unchanged from the no-ante case.**
2. **Pot calculation always matches `sum(contributions) + initial_pot`.** Invariant tested at every node in a tree walk.
3. **Stack equation always holds:** `stacks[i] + contributions[i] - initial_contributions[i] == config.starting_stack`. Invariant tested.
4. **`to_call` correctness:** when `street_aggressor >= 0`, `to_call == contributions[street_aggressor] - contributions[cur_player]`; when `street_aggressor == -1`, `to_call == 0`. Invariant tested.
5. **Fold leaves the folding player at the *contribution* loss, not the pot loss.** A SB-fold preflop loses 0.5 BB, not 1.5 BB.
6. **Showdown splits ties to 0.0 utility.** Half-pot per player; for equal contributions this nets to 0.
7. **All-in run-out deals exactly the right number of remaining board cards.** Preflop all-in run-out deals 5 cards via 5 chance outcomes in sequence (or equivalently dealt as a single 5-card outcome — PR 3 uses **sequential single-card chance nodes** to keep the tree depth predictable and the chance branching factor low).
8. **Raise cap enforcement: at-cap, only fold/call/all-in legal.** Tested explicitly.
9. **Dedup invariant: `legal_actions(state)` returns a list with no duplicate chip-amount actions.** Tested by constructing a low-pot state where multiple fractions round to identical chips.
10. **All-in is unique:** `ACTION_ALL_IN` appears at most once per legal-actions list; `ACTION_BET_X` / `ACTION_RAISE_X` are never simultaneously emitted with the same chip amount as `ACTION_ALL_IN`.
11. **Street transitions reset history but preserve `contributions` and `stacks`.** Tested by walking preflop → flop and asserting fields.
12. **Postflop OOP acts first.** Specifically, after the chance node deals the flop, `current_player == 1` (P1 = BB = OOP). Tested.
13. **Preflop SB acts first.** After blinds posted, `current_player == 0`. Tested.
14. **Hole cards are blocking** — chance outcomes never deal a board card already held in a player's hand or already on the board. Tested.
15. **Infoset key canonicalization:** `AhKh` and `KhAh` produce the same infoset key. Tested.
16. **Infoset key hides opponent's hole cards.** Tested by constructing two states differing only in opponent hole cards and asserting `infoset_key(state, player)` is identical.

## Test plan

### `tests/test_hunl_core.py` (~18 tests)

Game-rules invariants. Each test < 0.5s; total file < 5s.

1. `test_hunl_initial_state_blinds_posted` — contributions == (50, 100), stacks == (9950, 9900), pot == 150, to_call == 50, cur_player == 0.
1b. `test_hunl_initial_state_with_ante` — `HUNLConfig(ante=25)`: contributions == (75, 125), stacks == (9925, 9875), pot == 200, to_call == 50, cur_player == 0. `street_num_raises == 1` (still — BB still counts as opening bet; ante is just symmetric chips into pot).
2. `test_hunl_preflop_sb_acts_first`
3. `test_hunl_postflop_bb_acts_first` — walk to start of flop; cur_player == 1.
4. `test_hunl_fold_terminates_hand_correctly` — SB folds preflop; utility == (-0.5, +0.5) in BB.
5. `test_hunl_call_preflop_advances_to_flop` — SB calls, BB checks → chance node deals flop.
6. `test_hunl_bet_amount_uses_pot_fractions` — at start of flop with pot=2 BB, ACTION_BET_75 = bet 1.5 BB (150 cents).
7. `test_hunl_raise_amount_uses_pot_after_call` — after BB bets 1 BB on flop (pot becomes 3 BB after SB calls), ACTION_RAISE_100 raises by 3 BB on top of the 1 BB call → raise-to = 4 BB.
8. `test_hunl_min_bet_is_one_bb` — at any state with to_call == 0, smallest legal opening bet ≥ 1 BB.
9. `test_hunl_min_raise_enforced` — facing a 1-BB bet, the minimum raise increment is 1 BB (raise-to ≥ 2 BB).
10. `test_hunl_force_allin_threshold_snaps_short_shoves` — construct a state with stacks=120 cents, fraction-200% bet computes 200 cents > stack; snaps to ACTION_ALL_IN, not ACTION_BET_200.
11. `test_hunl_preflop_4_raise_cap` — walk preflop with 4 raises (bet/3bet/4bet/5bet); legal actions at the 5th are [FOLD, CALL, ALL_IN], no raises.
12. `test_hunl_postflop_3_raise_cap` — same on flop with 3-cap.
13. `test_hunl_showdown_higher_hand_wins` — deal both hands deterministically (via direct state construction), set board, walk to showdown, check utility.
14. `test_hunl_showdown_tie_splits_pot` — both players hold the same effective hand on a board (e.g. board plays all 5 cards), utility == (0.0, 0.0).
15. `test_hunl_all_in_runs_out_remaining_streets` — preflop all-in and call; verify state walks through 5 chance nodes to reach showdown.
16. `test_hunl_infoset_key_hides_opponent_cards` — two states differ only in P1's hole cards; `infoset_key(_, 0)` identical.
17. `test_hunl_infoset_key_canonicalizes_hole_order` — `AhKh` vs `KhAh` produce same key.
18. `test_hunl_chance_outcomes_exclude_held_cards` — at flop chance, neither player's hole card appears as a possible flop card.

### `tests/test_hunl_tree.py` (~10 tests)

Tree-structure invariants. Use a `_walk_tree(game, state, max_depth)` helper that traverses to a depth limit, calling assertions at each node. Full HUNL tree is too big — these tests use **small configs** (e.g. starting_stack=400 cents = 4 BB; raise cap intentionally caps the depth).

1. `test_hunl_tiny_tree_pot_invariant` — for a 4-BB starting stack, walk every state and assert `sum(contributions) - sum(initial_contributions) == sum(starting_stack - stacks)`.
2. `test_hunl_tiny_tree_legal_actions_never_empty_until_terminal` — at every non-terminal state, `legal_actions(state)` is non-empty.
3. `test_hunl_tiny_tree_terminal_count_in_expected_range` — count terminal states in a 4-BB tree; assert in `[100, 5000]` range (loose bound — see "Decisions deferred" if we need a tighter answer).
4. `test_hunl_river_subgame_no_chance_nodes` — when `starting_street == RIVER` and hole cards pre-dealt, the tree contains zero `cur_player == -1` nodes.
5. `test_hunl_default_tiny_subgame_solvable_in_one_minute` — instantiate `default_tiny_subgame()`, run DCFR for 500 iterations, assert `exploitability_history[-1] < 0.1` BB. Wall-clock target: <30s on the CI runner.
6. `test_hunl_max_tree_depth_bounded` — for postflop, depth ≤ `(postflop_raise_cap + 2) * 4 streets` (raise cap + check + call + chance per street).
7. `test_hunl_branching_factor_bounded` — at any non-chance node, `len(legal_actions) <= 8` (the 6-size menu + fold + call; check or fold-and-call-only at cap).
8. `test_hunl_terminal_utility_zero_sum` — for every terminal walked in the tiny tree, `utility[0] + utility[1] == 0.0` (no rake).
9. `test_hunl_infoset_count_smoke` — distinct infoset keys gathered across a 4-BB tree walk; assert count > 50 and < 100_000 (sanity bounds — see "Decisions deferred" if tighter needed).
10. `test_hunl_chance_outcome_probabilities_sum_to_one` — at every chance node visited in the walk, `sum(p for _, p in chance_outcomes(state)) == pytest.approx(1.0)`.

### `tests/test_action_abstraction.py` (~12 tests)

Bet-size menu correctness in isolation. No `HUNLPoker` import — these test `action_abstraction.enumerate_legal_actions(state_context)` where `state_context` is a simple dataclass (`ActionContext`) containing only the fields the abstraction needs: `pot`, `to_call`, `stacks`, `contributions`, `cur_player`, `street`, `street_num_raises`, `street_aggressor`, `big_blind`, `bet_size_fractions`, `preflop_raise_cap`, `postflop_raise_cap`, `force_allin_threshold_bb`, `min_bet_bb`, `include_all_in`. `HUNLPoker.legal_actions` constructs this context from its own state and delegates.

1. `test_abstraction_bet_actions_when_to_call_zero` — given pot=200, to_call=0, returns CHECK + 5 BET_X + ALL_IN.
2. `test_abstraction_raise_actions_when_to_call_positive` — given to_call=100, returns FOLD + CALL + 5 RAISE_X + ALL_IN.
3. `test_abstraction_no_raise_at_cap` — `street_num_raises == cap` → no RAISE_X actions, only FOLD/CALL/ALL_IN.
4. `test_abstraction_bet_pot_fractions_compute_correctly` — pot=200, ACTION_BET_75 → 150, ACTION_BET_100 → 200, ACTION_BET_150 → 300, ACTION_BET_200 → 400.
5. `test_abstraction_raise_uses_pot_after_call` — to_call=100, pot before call = 300, ACTION_RAISE_100 → raise-to = `contributions[aggressor] + (300 + 100) * 1.00 = aggressor_contrib + 400`.
6. `test_abstraction_min_bet_clamping` — pot=50 (small), ACTION_BET_33 would compute 16 cents but min_bet=100 cents; clamped to 100; dedup with other small fractions that also clamp.
7. `test_abstraction_all_in_replaces_oversize` — stack=200, pot=200, ACTION_BET_200 would compute 400 > stack; replaced with ACTION_ALL_IN.
8. `test_abstraction_all_in_dedup` — ACTION_BET_X clamped to all-in chip amount → no separate ACTION_ALL_IN, just the one all-in.
9. `test_abstraction_force_allin_threshold_snaps_short` — stack-after-bet = 50 cents (< 1 BB = 100), action snaps to all-in.
10. `test_abstraction_fold_unavailable_when_to_call_zero` — to_call=0 → FOLD not in legal actions.
11. `test_abstraction_check_unavailable_when_to_call_positive` — to_call>0 → CHECK not in legal actions.
12. `test_abstraction_returns_sorted_list` — output is in ascending action-id order so diff tests can compare without re-sorting.

### Convergence smoke test (in `test_hunl_tree.py`, but called out separately)

`test_hunl_default_tiny_subgame_solvable_in_one_minute` (see above) is the "river-only HUNL subset solves within 5 minutes" success criterion. Target: 500 iterations of the existing Python DCFR converges to exploitability < 0.1 BB on the dry-board AhKc-vs-QdQh fixture. (User can adjust the threshold if reality reveals slower convergence.)

## Implementation parallelism (fan-out)

Per the "Parallelization workflow" in PLAN.md, PR 3 launches three concurrent implementation agents with strict file ownership:

### Agent A — HUNLState + HUNLPoker rules (game tree)

**Owns:** `poker_solver/hunl.py` (entire file).

**Does NOT touch:** `action_abstraction.py`, `cli.py`, any test file.

**Deliverables:**
- `HUNLState` frozen dataclass with all fields per "HUNLState fields" above.
- `HUNLConfig` frozen dataclass.
- `HUNLPoker(Game)` class with `initial_state`, `is_terminal`, `utility`, `current_player`, `chance_outcomes`, `legal_actions`, `apply`, `infoset_key`.
- `Street` IntEnum.
- `default_tiny_subgame() -> HUNLConfig` factory for the CLI default.
- `legal_actions` delegates to `action_abstraction.enumerate_legal_actions(ctx)` (Agent B's contract).
- Type hints throughout; module passes `mypy --strict` on the new file.
- Imports `from poker_solver.action_abstraction import ActionContext, enumerate_legal_actions, ...` — Agent B owns this surface.

**Success gate:** Agent A's deliverable, plus Agent B's deliverable, plus Agent C's tests, all pass.

### Agent B — action abstraction

**Owns:** `poker_solver/action_abstraction.py` (entire file).

**Does NOT touch:** `hunl.py`, `cli.py`, any test file.

**Deliverables:**
- `ActionContext` frozen dataclass (small struct, just the fields needed for the bet-size decision — see test plan).
- `ActionAbstractionConfig` frozen dataclass (re-exporting `bet_size_fractions`, raise caps, etc. — Agent A constructs this from `HUNLConfig`).
- `enumerate_legal_actions(ctx: ActionContext) -> list[int]` — main entry point.
- `compute_bet_amount(action_id, ctx) -> int` — returns the chip *amount put in this action* for a given action id and context. (Used by `HUNLPoker.apply` to update contributions and stacks.)
- `compute_raise_to(action_id, ctx) -> int` — returns the new `contributions[player]` value after a raise.
- `BetSizing` enum or constants for the action ids (the 14 constants listed in "Action encoding").
- Pure functions; no class state. Module-level constants for action ids.
- Type hints throughout; passes `mypy --strict`.

**Interface lock-in:** Agent A and Agent B both work against the function signatures in this spec. No call-site changes mid-PR. If Agent A discovers an awkward signature, they file an "interface adjustment" note for the orchestrator (me) to approve before the change lands.

### Agent C — tests (written from spec alone)

**Owns:** `tests/test_hunl_core.py`, `tests/test_hunl_tree.py`, `tests/test_action_abstraction.py`.

**Does NOT touch:** `hunl.py`, `action_abstraction.py`, `cli.py`, `__init__.py`.

**Deliverables:**
- All test files per the test plan above.
- Each test self-contained; matches the style of `tests/test_leduc_core.py` (function-level tests, `pytest.approx` for floats, no test classes).
- Uses **only the public API** from `poker_solver/__init__.py` (`HUNLPoker`, `HUNLState`, `HUNLConfig`, `ActionContext`, `enumerate_legal_actions`, plus the 14 action-id constants).
- Agent C does NOT see Agent A's or Agent B's code while writing the tests. They write strictly from this spec.

**Parallelism rationale:** Agent C runs concurrently with A+B because the spec is the interface lock. By the time A+B return, C has a test file ready; we run pytest as the integration check.

**Edge-case allowance:** Agent C may write tests that are *correct per spec* but reveal genuine ambiguities in this document. If a test fails because the spec was ambiguous, the **spec is the source of truth** — we update the impl or update the spec, not silently tweak the test. This is by design and is the key dividend of the fan-out pattern.

## Modifications to existing files (Agent A's scope, but listed here for visibility)

After A+B+C all return clean:

- `poker_solver/__init__.py`: add to `__all__` and to the re-export block:
  ```python
  from poker_solver.hunl import HUNLPoker, HUNLState, HUNLConfig, Street, default_tiny_subgame
  from poker_solver.action_abstraction import (
      ActionContext, ActionAbstractionConfig, enumerate_legal_actions,
      compute_bet_amount, compute_raise_to,
      ACTION_FOLD, ACTION_CHECK, ACTION_CALL,
      ACTION_BET_33, ACTION_BET_75, ACTION_BET_100, ACTION_BET_150, ACTION_BET_200,
      ACTION_RAISE_33, ACTION_RAISE_75, ACTION_RAISE_100, ACTION_RAISE_150, ACTION_RAISE_200,
      ACTION_ALL_IN,
  )
  ```
- `poker_solver/cli.py`:
  - Extend `_GAMES` (no, actually: `_GAMES` returns the game class; HUNL needs config so we need a `_GAMES` lookup that returns a factory function. Refactor `_GAMES = {"kuhn": KuhnPoker, "leduc": LeducPoker, "hunl": _build_hunl_with_args}`).
  - Add `--hunl-mode` arg to the `solve` subparser; default `tiny_subgame`. Only meaningful when `--game hunl`; ignored otherwise.
  - `_build_hunl_with_args(args)` constructs `HUNLPoker(default_tiny_subgame())` for `tiny_subgame` mode; raises `NotImplementedError` for `full` mode.

These modifications are small and Agent A folds them into their PR. No separate "polish track" agent for this PR (the polish is too entangled with `hunl.py`'s public surface).

## Post-implementation audit

Per PLAN.md "Code + test audit (mandatory from PR 3 onward)": after A+B+C land, a fresh `general-purpose` audit agent runs with **no prior context** and reviews:

- The full diff (Agent A's `hunl.py`, Agent B's `action_abstraction.py`, Agent C's three test files, plus `__init__.py` + `cli.py` deltas).
- Against this spec only — not the implementation discussion / debugging.
- Output: `docs/pr3_prep/audit_report.md` with structured sections (must-fix / should-fix / nice-to-fix / looks-good).
- User reads alongside `pr_report.md` before commit OK.

Focus areas the audit must touch:
- Integer-only arithmetic discipline (no f64 chip values).
- Dedup correctness on edge bet sizes.
- Min-bet / min-raise enforcement.
- Raise-cap counter never miscounts (checks vs. calls vs. opening-bets vs. raises).
- All-in absorption isn't accidentally double-counted.
- No leak of opponent's hole cards into `infoset_key`.
- Card mapping helpers don't conflict with existing `card.py` exports.
- License: any code copy-pasted from postflop-solver (AGPL) → must be flagged.

## Success criteria

- All new tests pass (~40 new tests across the 3 test files).
- All 97 existing tests still pass (Kuhn + Leduc unchanged; the existing infoset count, exploitability convergence, and intuition gauntlet still hold).
- `ruff check poker_solver tests` clean (no new warnings).
- `ruff format --check` clean.
- `mypy poker_solver/hunl.py poker_solver/action_abstraction.py` strict-clean (new code held to strict standard).
- `mypy poker_solver` overall: no new errors (existing files unchanged).
- `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500` runs in under 60 seconds and prints a valid strategy table with exploitability < 0.1 BB.
- `poker-solver solve --game hunl --hunl-mode full` raises a clear `NotImplementedError` pointing the user at PR 5.
- The HUNL tree can be **partially enumerated** via the tiny-tree fixture (`starting_stack=400`, river-only or short-stack preflop) with all invariants holding.
- The default 100-BB preflop tree is **not** enumerated in tests (too big); a smoke test asserts `HUNLPoker(HUNLConfig())` can produce an initial state and 5 legal actions without crashing.

## Decisions deferred to user

These are choices where the spec makes a reasonable call but the user may want to override before implementation begins. Each one is **locked to the listed default unless the user redirects**; the implementing agents proceed with the default.

1. **All-in legality at the raise cap.** Spec assumes: at the cap, no raises but all-in is legal. PLAN.md says "after cap, next aggressive action forces all-in" which is consistent. Decision: at-cap → fold/call/all-in only. *(Confirm if user disagrees.)*
2. **Preflop all-in run-out branching.** Spec uses *sequential* single-card chance nodes for the flop/turn/river deal during a preflop all-in run-out (so tree depth is predictable and each chance node has 48–50 outcomes). Alternative: a single combined chance node with `C(48, 5)` outcomes. Sequential is friendlier for traversal; combined is more compact in memory. **Default: sequential** — matches the existing Kuhn/Leduc pattern where chance is one card at a time.
3. **Asymmetric stacks.** Spec accepts symmetric `starting_stack` only in the default `HUNLConfig`; a tuple value is permitted but tests only cover symmetric. **Default: symmetric.** Asymmetric-stack tests added in PR 9 when preflop is parameterized.
4. **Tiny subgame fixture composition.** Default is river-only, AhKc vs QdQh, board `As7c2dKh5s`, SPR 1. Alternative: shorter-stack preflop subgame (e.g. 20 BB push/fold). Default chosen because it's deterministic (no chance nodes), small, and exercises bet/raise/cap mechanics. **Override candidates:** push/fold preflop, or a flop-only subgame.
5. **Tree-count bounds in `test_hunl_tiny_tree_terminal_count_in_expected_range`.** Spec uses a loose `[100, 5000]` bound for the 4-BB starting stack tree. A precise count would require either (a) hand-enumeration in the spec or (b) deferring this test to a post-impl exact-count measurement that's then frozen as a regression guard. **Default: ship with loose bounds**; tighten in a follow-up if the in-flight `hunl_tree_size_estimate.md` produces a calibrated number.
6. **Infoset count smoke bounds in `test_hunl_infoset_count_smoke`.** Same as #5: loose bounds `[50, 100_000]`; tighten post-impl if the size-estimate report has data.
7. **Card-int mapping placement.** Spec adds `card_to_int` / `int_to_card` to `poker_solver/card.py` (5-line touch). Alternative: live in `hunl.py`. **Default: card.py** because the Rust port (PR 6) will need it too, and it's a card-domain helper.
8. **Whether `chance_outcomes` for the preflop hole-card deal returns the full ~1.6M outcome list.** Spec returns a `list` (per `Game` protocol) but the orchestration path that calls this in PR 3 only goes through subgames with pre-dealt hole cards. Materializing the 1.6M list once per query is slow but acceptable for the smoke test that doesn't actually call it. **Default: materialize lazily** via a generator-backed `__iter__` if the list grows huge; or just return the list. The default `HUNLConfig` (100 BB preflop) is never solved in PR 3, so this is mostly cosmetic. *(Implementation note: Agent A picks the simpler one if the in-flight `hunl_tree_size_estimate.md` doesn't surface a constraint here.)*
9. **Force-all-in threshold semantics.** Spec uses a stack-absolute threshold (`stack_after_bet <= 1 BB → snap all-in`). postflop-solver uses a pot-relative threshold. Default: stack-absolute (simpler, deterministic). User can swap to pot-relative in PR 9.
10. **`merging_threshold` (close-bet collapse).** postflop-solver collapses bets within 10% of each other. PR 3 intentionally does not — the fixed-fraction menu is small enough that dedup-only is sufficient. **Default: no merging.** PR 4 or PR 9 may add merging if the menu grows.

### Decisions to revisit based on in-flight prep reports

Three prep reports were launched in parallel with this spec draft and may surface findings that modify the above:

- **`docs/pr3_prep/postflop_solver_tree_notes.md`** — could surface a tighter `merging_threshold` behavior we should match, or a specific pot-relative force-all-in formula. If it does, the implementing agents should be redirected to that formula instead of the stack-absolute default in #9.
- **`docs/pr3_prep/open_spiel_noambrown_notes.md`** — could surface a different action-id encoding or infoset-key format we should match for the cross-validation tests in PR 7. If it does, decision #6 above (infoset key format) may need adjustment.
- **`docs/pr3_prep/hunl_tree_size_estimate.md`** — produces calibrated bounds for the tiny-tree node counts. If it lands before implementation starts, tighten decisions #5 and #6 above. If after, file a follow-up to tighten the test bounds.

If any of these reports complete and contain a "must adjust PR 3 spec" finding, the orchestrator (me) updates this spec before launching A/B/C.

## Risk log

- **The `Game` protocol may need a `replace` of the `chance_outcomes` return type to accommodate the ~1.6M preflop deal.** Mitigation: defer the full preflop deal until PR 5; PR 3's tiny subgame is river-only, so this never triggers.
- **`infoset_key` becomes a memory hotspot at 10^14 unabstracted infosets.** Mitigation: PR 4 replaces hole-card strings with bucket ids; PR 3 only enumerates tiny subgames so the string keys are fine.
- **Dedup logic may have rounding-edge bugs.** Mitigation: `test_abstraction_min_bet_clamping` and `test_abstraction_all_in_dedup` cover the two known boundary cases. The audit agent gets explicit "dedup correctness" as a focus area.
- **Heads-up positional convention mistake (SB-acts-first-preflop / BB-acts-first-postflop).** Mitigation: explicit tests `test_hunl_preflop_sb_acts_first` and `test_hunl_postflop_bb_acts_first`. Also documented in the docstring of `HUNLPoker`.
- **Integer-arithmetic discipline drift** (someone introduces a float chip value). Mitigation: audit agent has explicit focus area; the cents-based config is documented at the top of `hunl.py`.

## Out-of-scope follow-up tickets (after PR 3 merges)

- PR 4: card abstraction layer that plugs in behind `infoset_key`.
- PR 5: scalable Python solver for HUNL (using card abstraction).
- PR 6: Rust port of `HUNLPoker` + abstraction.
- PR 9: rake support, preflop bet-size menu tuning, asymmetric stacks.
- A potential PR 3.5 if the in-flight prep reports surface a meaningful merging_threshold change.
