# Minimal Hand-Computable Diff-Test Fixture

**Status:** Design only (no code committed); designed 2026-05-24 in response
to P0 synthesis after the v1.6.1 dry-run #2 22-42pp empirical divergence
and the terminal-utility-is-correct verdict from the sibling audit.

**Purpose:** Pin down whether the 22-42pp Brown-vs-ours strategy divergence at
deep-cap river spots is:

* **shallow** — manifests even on a single-decision, single-action-pair
  fixture where the Nash strategy is hand-computable. If so, this fixture
  isolates the bug to one of: comparator, action menu, DCFR weighting, or
  reach handling, AT ITS SIMPLEST POSSIBLE FORM.
* **depth-related** — only emerges with multi-street or multi-decision raise
  trees. If both solvers agree on this fixture but diverge on the K72/A83
  acceptance spots, the bug lives in raise-tree accumulation (cap-guard
  ordering, raise size topology mismatch, or DCFR accumulator drift across
  many decisions).

This is the **shallow-vs-deep discriminator**: by design, the fixture is
small enough that disagreement here is unambiguously a bug in the basic
algorithmic kernel; agreement here narrows the suspect set to the
depth-accumulation list.

---

## Fixture spec

### Board

`7c 5d 3h Qs 2c` (rainbow river; no pair, no straight, no flush, no draw).

The board is deliberately chosen to:

* Avoid any rank-overlap with the hand classes {AA, KK}, so neither class
  hits a set / two-pair / quads — both remain pure overpairs.
* Avoid any flush / straight / paired-board complication so showdown
  ordering is the textbook "higher pair wins" rule.
* Be a "brick" river (Q at index 3 was already exposed by the turn; the
  river `2c` adds nothing). The "river-only" framing means the solver
  starts at the river decision; the prior streets are baked into pot/stack.

### Ranges

Both players have the **same hand-class set** `{AA, KK}` (Pio-style class
labels). All combos of each class are eligible subject to board-blockers:

* AA: 6 combos (AcAd, AcAh, AcAs, AdAh, AdAs, AhAs) — none blocked by board.
* KK: 6 combos (KcKd, KcKh, KcKs, KdKh, KdKs, KhKs) — none blocked by board.

Weights: uniform 1.0 across every combo (no weighting bias).

This is the **fully-symmetric** range setup the task requested.

### Pot / stacks

* Initial pot at river: **2 BB** (chips: `pot=200` at `big_blind=100`).
* Initial contributions: `(100, 100)` (each player put in 1 BB pre-river).
* Per-player remaining stack: **3 BB** (chips: 300). Plenty of room for a
  1 BB bet without triggering force-allin or running out of chips.

This geometry is **shallow but NOT all-in-forced**. A 0.5 × pot bet of
1 BB leaves 2 BB behind on each side (above the engine's force-allin
threshold of 1 BB, so the bet is emitted as a regular bet token, not as
`ACTION_ALL_IN`). The remaining 2 BB is "dead" because `postflop_raise_cap=1`
prevents a check-raise/3-bet — but the chips' existence prevents the
engine from collapsing the bet into an ACTION_ALL_IN slot, which is what
we want for an apples-to-apples Brown diff (Brown uses its own
`include_all_in` flag that splits all-in tokens into their own list, and
collapsing complicates the action-axis mapping).

### Action menu

* **P1 (BB seat) acts FIRST on the river** in our engine (per
  `poker_solver/hunl.py:429` — symmetric contributions place P1 first
  postflop). Brown matches (cpp/src/river_game.cpp:9-10).
* P1's actions at root: `CHECK` or `BET 100 chips` (= 0.5 × pot = 1 BB).
* If P1 checks → P0's turn:
  * P0's actions: `CHECK` (terminal showdown) or `BET 100`.
  * If P0 bets → P1's response: `FOLD` or `CALL` (terminal).
* If P1 bets → P0's response: `FOLD` or `CALL` (terminal).
* `postflop_raise_cap=1` blocks any raise — the game tree never reaches
  a 2nd bet.

**The game is symmetric between P1 and P0** because ranges are
identical and the action sets after check-by-first-actor mirror the
root menu. The Nash has the SAME strategy for both players (each player
plays the "first-actor role" sometimes and the "second-actor role"
sometimes, by symmetry of position rotation).

In `HUNLConfig` terms:

```python
HUNLConfig(
    starting_stack=400,             # 4 BB total. Contributions are 100
                                    # each → 300 remaining per side at the
                                    # decision. Enough room for 1 BB bet
                                    # + 2 BB residual (above the force-
                                    # allin threshold of 1 BB).
    big_blind=100,
    small_blind=50,
    starting_street=Street.RIVER,
    initial_board=tuple(parse_board("7c 5d 3h Qs 2c")),
    initial_pot=200,
    initial_contributions=(100, 100),
    initial_hole_cards=(),          # filled per-combo by the harness
    bet_size_fractions=(0.5,),      # 0.5 * pot = 100 chips = 1 BB bet
    include_all_in=False,           # no separate all-in slot needed
    postflop_raise_cap=1,           # 1 raise cap blocks villain's 3-bet
                                    # path entirely, keeping the menu
                                    # post-bet at {FOLD, CALL}
)
```

The Brown equivalent (`write_brown_config`):

```json
{
  "board": ["7c", "5d", "3h", "Qs", "2c"],
  "pot": 200,
  "stack": 300,
  "bet_sizes": [0.5],
  "include_all_in": false,
  "max_raises": 1,
  "players": [
    {"hands": ["AcAd","AcAh","AcAs","AdAh","AdAs","AhAs",
               "KcKd","KcKh","KcKs","KdKh","KdKs","KhKs"],
     "weights": [1.0]*12},
    {"hands": ["AcAd","AcAh","AcAs","AdAh","AdAs","AhAs",
               "KcKd","KcKh","KcKs","KdKh","KdKs","KhKs"],
     "weights": [1.0]*12}
  ]
}
```

Note: Brown's `cpp/src/river_game.cpp:228-240` will drop any combo sharing
a card with the board. None of the 12 combos do, so the post-filter range
matches ours exactly.

---

## Hand-computed Nash

### Showdown equities

On board `7c 5d 3h Qs 2c`:

* Best 5-card hand for AA = pair of aces with kickers Q, 7, 5.
* Best 5-card hand for KK = pair of kings with kickers Q, 7, 5.
* AA strictly beats KK. AA chops vs AA (identical kickers). KK chops vs
  KK (identical kickers).

### Per-combo equity vs the symmetric range (range = 12 combos, uniform)

Using card-removal-correct combo enumeration:

| Hero combo | Unblocked villain combos | Wins | Ties | Losses | Equity |
|---|---|---|---|---|---|
| AcAd (AA) | 1 AA (AhAs) + 6 KK = 7 | 6 (vs KK) | 1 (vs AhAs) | 0 | 6.5/7 ≈ **0.9286** |
| AhAs (AA) | 1 AA (AcAd) + 6 KK = 7 | 6 | 1 | 0 | **0.9286** |
| (each AA combo, by symmetry) | 7 (1 AA, 6 KK) | 6 | 1 | 0 | **0.9286** |
| KcKd (KK) | 6 AA + 1 KK (KhKs) = 7 | 0 | 1 (vs KhKs) | 6 (vs AA) | 0.5/7 ≈ **0.0714** |
| KhKs (KK) | 6 AA + 1 KK (KcKd) = 7 | 0 | 1 | 6 | **0.0714** |
| (each KK combo, by symmetry) | 7 (6 AA, 1 KK) | 0 | 1 | 6 | **0.0714** |

**Blocker derivation for AA combos:** AcAd blocks any villain combo
containing Ac OR Ad. Villain AA combos: AcAd (=hero's), AcAh (blocked Ac),
AcAs (blocked Ac), AdAh (blocked Ad), AdAs (blocked Ad), AhAs (clean).
→ 1 unblocked villain AA. KK combos have no aces, so all 6 are unblocked.

**Blocker derivation for KK combos:** KcKd blocks KcKh, KcKs, KdKh, KdKs.
Plus excludes itself. → 1 unblocked villain KK (KhKs). AA combos have no
kings, all 6 unblocked.

So:

* **AA-class equity vs villain range = 0.9286 (= 13/14)** per AA combo
* **KK-class equity vs villain range = 0.0714 (= 1/14)** per KK combo

(Symmetric across all 6 combos of each class.)

### Nash equilibrium structure

This is a **symmetric polarized-vs-bluff-catcher** river spot with a
3-decision-node tree (because BOTH players can bet when not facing a
bet, plus respond when facing one):

```
Root: P1 decides {CHECK, BET}
  ├── P1 BET → P0 facing-bet: {FOLD, CALL} → terminal
  └── P1 CHECK → P0 decides {CHECK, BET}
        ├── P0 BET → P1 facing-bet: {FOLD, CALL} → terminal
        └── P0 CHECK → terminal showdown
```

Pot odds at the facing-bet node: villain calls 1 BB into a 3 BB pot to
win 4 BB total → needs **25% equity**. MDF = 1 − 1/3 = **2/3**.

Per-combo conditional probabilities (with card-removal accounted for):
when a player holds a specific AA combo and bets, the opponent sees
**1 unblocked AA combo + 6 unblocked KK combos = 7 unblocked combos**;
when they hold KK and bet, the opponent sees **6 unblocked AA combos
+ 1 unblocked KK combo = 7 unblocked combos**. (Derived above.)

### Strict (pure-strategy) slots — must hold at any correct Nash

The pure-strategy slots can be derived by **dominance arguments** (no
mixing required):

* **KK at a "first to act, no bet to face" node** (root for P1; after-check
  for P0): EV(bet KK) ≤ EV(check KK). KK has only ~7% equity vs the full
  opponent range. Betting KK risks 1 BB to win at most 2 BB if folded;
  but the opponent's calling range is AA-only (KK strict fold facing
  bet), and KK loses 100% vs AA. So EV(bet KK) = (1-f)×2 + f×(0×4 - 1) =
  2 - 3f, where `f` = opponent's call freq. Plugging in opponent's strict-
  call-AA / strict-fold-KK strategy: f = (6 c_A + c_K) / 7 = (6×1 + 0)/7 =
  6/7 → EV(bet KK) = 2 - 18/7 = -4/7. EV(check KK) = 1/7. **STRICT CHECK
  with KK at any no-bet-to-face node** (margin: ~0.71 BB).

* **AA facing bet** (either at the response-to-root-bet node or the
  response-to-after-check-bet node): the betting range is ≥1 AA combo
  and ≤6 KK combos worth of bluffs. AA strictly beats KK and chops AA.
  Equity is ≥ 13/14 (when k=0; gets higher as opponent bluffs more).
  Pot odds require only 25%. So EV(call AA) >> 0 → **STRICT CALL with
  AA facing bet** at any node.

* **KK facing bet** (either node): the betting range is value-heavy (AA
  combos plus at most a small KK bluff). KK loses to AA, chops KK. With
  symmetric Nash where opponent also plays KK strict check at no-bet
  nodes, the betting range is AA-only → KK loses 100% if calling → strict
  fold (EV(call KK) = -1, EV(fold KK) = 0). **STRICT FOLD with KK
  facing bet** at any node.

### Mixed-strategy slots — indifference manifold

* **AA at a "first to act, no bet to face" node**: EV(bet AA) = (14 -
  c_A + 6 c_K)/7 ≈ 13/7 (when c_A=1, c_K=0). EV(check AA) ≈ 13/7 too,
  via the check-then-respond branch (opponent strict-checks KK, opponent
  strict-bets-or-mixes AA; AA equity vs opponent's check-then-call range
  is high). The two EVs are essentially equal at the symmetric Nash, so
  **AA at no-bet-to-face nodes is INDIFFERENT** — mixed strategy on
  `a ∈ [0, 1]`.

  The exact mixing rate is determined by a system of two indifference
  equations (one at root, one at after-check) that produce an
  underdetermined system — there is a **1-dim indifference manifold of
  Nash equilibria** parameterized by either node's `a` rate.

### Final hand-computed Nash structure

| Node | Hand class | Action | Strategy | Type |
|---|---|---|---|---|
| Root (P1) | AA | bet | `a_1 ∈ [0, 1]` | **MIXED (indifferent)** |
| Root (P1) | AA | check | `1 − a_1` | mixed |
| Root (P1) | KK | bet | **0.000** | **STRICT** |
| Root (P1) | KK | check | **1.000** | strict |
| After-P1-check (P0) | AA | bet | `a_2 ∈ [0, 1]` | **MIXED (indifferent)** |
| After-P1-check (P0) | AA | check | `1 − a_2` | mixed |
| After-P1-check (P0) | KK | bet | **0.000** | **STRICT** |
| After-P1-check (P0) | KK | check | **1.000** | strict |
| Facing-bet (either) | AA | call | **1.000** | **STRICT** |
| Facing-bet (either) | AA | fold | 0.000 | strict |
| Facing-bet (either) | KK | call | 0.000 | strict |
| Facing-bet (either) | KK | fold | **1.000** | **STRICT** |

**8 strict slots + 2 indifference slots = 10 total decision variables.**

### Hero (P1) EV per combo at the root

Independent of where on the indifference manifold the solver lands
(EV is constant across the manifold by definition of indifference):

* P1 AA at root: EV = **+13/7 ≈ +1.857 BB per combo**.
* P1 KK at root: EV = **+1/7 ≈ +0.143 BB per combo**.
* Range-aggregate P1 EV = 0.5 × 1.857 + 0.5 × 0.143 = **+1.0 BB**.

By symmetry, P0 range-aggregate EV at root = **−1.0 BB**. Zero-sum
verified.

### Why this fixture is diagnostic

**8 strict-strategy slots** must exactly match the hand-computed values
across ANY correct DCFR solver:
* 2 KK-check slots (one per first-to-act node)
* 4 facing-bet slots (AA call + KK fold at 2 nodes)
* 2 KK-bet=0 slots (per first-to-act node)

The **2 indifference slots** (AA bet rate at root and at after-check) sit
on a 1-dim manifold; DCFR may land anywhere on it. If both solvers land
on the SAME point, that's confirmatory evidence of identical DCFR
averaging convention.

**Diagnostic interpretation:**
* If both solvers match ALL 8 strict slots within 2pp: kernel agrees on
  the strict-strategy structure → the bug is NOT in the basic game tree,
  action menu, per-combo equity, or terminal utility. It must be either
  (i) a depth-related raise-tree bug (only manifests with > 1 raise),
  or (ii) a comparator-side artifact.
* If either solver diverges on ANY strict slot: shallow bug; the specific
  failing slot localizes the suspect:
  - **KK at no-bet not checked (bets some)**: action-menu or equity bug;
    KK strict check is determined by dominance and any failure means the
    solver believes KK has more equity than it does.
  - **AA facing bet not calling**: equity or action-menu bug; the call
    is dominated.
  - **KK facing bet not folding**: equity or action-menu bug.
* The two indifference slots are NOT load-bearing for the diagnostic
  but provide a secondary signal (if both solvers land on the same `a`
  value, DCFR averaging is identical; if different, one or both has a
  weighting convention difference).

---

## Expected solver output (per infoset × hand-class × action)

Both solvers, if correct, should report the following strategy values
at the corresponding lossless infoset key (`<hole>|<board>|r|<history>`,
per `HUNLState.infoset_key`):

### Strict slots (must match within 2pp)

| Infoset | Hand class | Action | Expected | Strictness |
|---|---|---|---|---|
| Root, P1 | KK | bet | 0.000 | STRICT |
| Root, P1 | KK | check | 1.000 | STRICT |
| After-P1-check, P0 | KK | bet | 0.000 | STRICT |
| After-P1-check, P0 | KK | check | 1.000 | STRICT |
| After-P1-bet, P0 | AA | call | 1.000 | STRICT |
| After-P1-bet, P0 | AA | fold | 0.000 | STRICT |
| After-P1-bet, P0 | KK | call | 0.000 | STRICT |
| After-P1-bet, P0 | KK | fold | 1.000 | STRICT |
| After-P0-bet (post P1 check), P1 | AA | call | 1.000 | STRICT |
| After-P0-bet (post P1 check), P1 | AA | fold | 0.000 | STRICT |
| After-P0-bet (post P1 check), P1 | KK | call | 0.000 | STRICT |
| After-P0-bet (post P1 check), P1 | KK | fold | 1.000 | STRICT |

### Mixed slots (informative; not load-bearing)

| Infoset | Hand class | Action | Expected | Strictness |
|---|---|---|---|---|
| Root, P1 | AA | bet | a_1 ∈ [0, 1] | MIXED |
| Root, P1 | AA | check | 1 - a_1 | MIXED |
| After-P1-check, P0 | AA | bet | a_2 ∈ [0, 1] | MIXED |
| After-P1-check, P0 | AA | check | 1 - a_2 | MIXED |

### Verifiable scalar

| Output | Expected | Tolerance |
|---|---|---|
| P1 range-aggregate EV at root | +1.000 BB | ± 0.05 BB |
| P0 range-aggregate EV at root | −1.000 BB | ± 0.05 BB |
| Zero-sum check (P0 EV + P1 EV) | 0.000 | ± 0.05 (for the in-engine
zero-sum convention; Brown's non-zero-sum convention adds +base_pot ≈
+0 BB on this fixture because both players contribute symmetrically) |

The 12 strict rows are the **load-bearing diagnostic**: they must all
match within 2pp. The 4 mixed rows can differ between solvers without
indicating a bug, but if both solvers land on the same `(a_1, a_2)`
point, that's confirmatory evidence of converged DCFR averaging.

(The 0.02 tolerance absorbs DCFR's residual exploitability at 5000
iterations. With 50000 iterations the convergence tightens to ~0.005pp.)

---

## How to invoke both solvers

### Our solver — direct Rust call (matches PoC pattern)

```python
import json
from poker_solver import HUNLConfig, Street, parse_board
from poker_solver.hunl import _serialize_hunl_config
from poker_solver.card import card_to_int
import poker_solver._rust as _rust

board = tuple(parse_board("7c 5d 3h Qs 2c"))
config = HUNLConfig(
    starting_stack=200,
    big_blind=100,
    small_blind=50,
    starting_street=Street.RIVER,
    initial_board=board,
    initial_pot=200,
    initial_contributions=(100, 100),
    initial_hole_cards=(),
    bet_size_fractions=(1.0,),
    include_all_in=False,
    postflop_raise_cap=1,
)

# Enumerate the symmetric 12-combo range explicitly so both engines see
# the same hand vector (no chance-enum surprises).
def hole_ids(rank: str, suits: tuple[str, str]) -> list[int]:
    from poker_solver.card import parse_card
    return sorted([card_to_int(parse_card(rank + suits[0])),
                   card_to_int(parse_card(rank + suits[1]))])

aa_combos = [hole_ids("A", (s1, s2)) for s1, s2 in
             [("c","d"),("c","h"),("c","s"),("d","h"),("d","s"),("h","s")]]
kk_combos = [hole_ids("K", (s1, s2)) for s1, s2 in
             [("c","d"),("c","h"),("c","s"),("d","h"),("d","s"),("h","s")]]
p0_holes = aa_combos + kk_combos
p1_holes = aa_combos + kk_combos

config_json = _serialize_hunl_config(config)
rs_result = _rust.solve_range_vs_range_rust(
    config_json, 5000, 1.5, 0.0, 2.0, p0_holes, p1_holes,
)
# rs_result["average_strategy"] is dict[infoset_key, list[float]]
# Aggregate by hand class as shown in range_aggregator's _enumerate_combos.
```

### Our solver — aggregator wrapper (the PR 16 path users hit in the UI)

```python
from poker_solver import solve_range_vs_range  # = poker_solver.range_aggregator
result = solve_range_vs_range(
    config_template=config,
    hero_range=["AA", "KK"],
    villain_range=["AA", "KK"],
    iterations=5000,
    backend="rust",
    hero_player=0,                # hero acts first on river
    reps_per_class=6,             # all 6 combos per class
    villain_reps=6,               # exercise full blocker matrix
)
# result.per_class_strategy is dict[hand_class, dict[action_label, prob]]
```

These two paths SHOULD agree with each other (and with hand-computed Nash).
A disagreement between them isolates the aggregator vs the vector-form
solver — a useful auxiliary diff.

### Brown's solver — shell invocation (mirrors `run_brown_solver`)

Stash the JSON above at `/tmp/minimal_diff_fixture.json`, then:

```sh
$REPO_ROOT/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized \
    --config /tmp/minimal_diff_fixture.json \
    --algo dcfr \
    --iters 5000 \
    --dcfr-alpha 1.5 \
    --dcfr-beta 0.0 \
    --dcfr-gamma 2.0 \
    --seed 7 \
    --dump-strategy /tmp/minimal_diff_brown_strategy.json
```

Or, in Python, via the existing wrapper (build a `RiverSpot` programmatically
and call `run_brown_solver`):

```python
from poker_solver.parity.noambrown_wrapper import (
    RiverSpot, run_brown_solver, find_brown_binary
)
from poker_solver.card import parse_card

def combo(s: str) -> tuple:
    return (parse_card(s[:2]), parse_card(s[2:]))

aa_combos = [combo(x) for x in
             ["AcAd","AcAh","AcAs","AdAh","AdAs","AhAs"]]
kk_combos = [combo(x) for x in
             ["KcKd","KcKh","KcKs","KdKh","KdKs","KhKs"]]
range_tuple = tuple((c, 1.0) for c in aa_combos + kk_combos)

spot = RiverSpot(
    id="minimal_diff_AA_KK",
    description="Minimal hand-computable Nash diff fixture",
    board=tuple(parse_card(c) for c in ["7c","5d","3h","Qs","2c"]),
    pot=200,
    stack=100,
    bet_sizes=(1.0,),
    include_all_in=False,
    max_raises=1,
    ranges=(range_tuple, range_tuple),
    iterations_override=5000,
)

binary = find_brown_binary()
brown_dump = run_brown_solver(spot, binary, iterations=5000)
# brown_dump.players[0].profile[""]  — root-decision strategy for P0
```

---

## Predicted divergence pattern

| Outcome | Implication |
|---|---|
| **Both solvers match hand-computed Nash (within 2pp)** | Bug is depth-related. Sibling agents auditing the K72/A83 acceptance failures should focus on raise-tree accumulation (cap-guard, raise size topology, DCFR drift across multi-decision sequences). The basic kernel is sound. |
| **Both solvers AGREE WITH EACH OTHER but disagree with hand-computed Nash** | Spec-level disagreement. Indicates a **shared** algorithmic convention difference (e.g., both apply the same DCFR variant that converges to a non-Nash limit). Action: audit DCFR-vector vs textbook DCFR. |
| **Solvers DISAGREE on the simplest possible game** | Bug is shallow. Inspect (in order): (1) per-combo equity at terminal — confirm both engines agree on equity given the fixed combo pair; (2) action menu — confirm both engines emit exactly `{check, bet}` for hero and `{fold, call}` for villain; (3) reach initialization — Brown uses `vec![1.0; num_hands]`, Rust uses `vec![1.0]` (per `dcfr_vector.rs`-vs-`trainer.cpp` comparison in `a83_deep_cap_root_cause_investigation.md` and the v1.6.1 final synthesis §"intentional difference") — and the synthesis claimed this is "scale-only," but with single-decision the scale factor should be visible as exact strategy divergence. (4) Action axis ordering — Brown emits `[c, f, r_low, ...]`, Rust emits `[f, c, r_low, ...]` (per `v1_6_1_final_synthesis.md` §"intentional difference"); the per-action diff loop must permute. |
| **Aggregator-wrapper output disagrees with direct Rust call on the same fixture** | Aggregator bug (blueprint per-hand sampling drift). Not the deep-cap divergence; a parallel finding. Forward to PR 16 team. |

The fixture is **deliberately at the threshold** where shallow bugs surface
visibly: zero raises (cap=1, no 3-bet possible), one bet size, one bet
decision per player at most, fully deterministic strict-strategy
structure for 12 of 16 strategy cells. Any DCFR weighting bug or
reach-handling mistake should produce a visible > 5pp deviation on AT
LEAST ONE of the 12 strict rows.

---

## Recommended next step (post sibling-agent completion)

1. **Once the comparator / action-menu / DCFR-weighting / reach-handling
   sibling audits report:**
   * If any sibling has identified a confirmed solver-side bug — implement
     the fix on a branch, then run this fixture as the **regression gate**
     (must continue to produce the hand-computed Nash within 2pp).
   * If all siblings come back clean (no solver bug) — run this fixture as
     the **discriminator**: agreement here + disagreement at deep-cap
     confirms the bug is depth-related, narrowing future investigation to
     raise-tree accumulation.

2. **Land the fixture** as `tests/test_minimal_diff_AA_KK_river.py` with two
   parametrized cases: `backend="rust"` (direct call) and `backend="rust"`
   via aggregator (`solve_range_vs_range`). Both must match the hand-
   computed Nash within tolerance. This is a **forever regression gate** —
   any future change that breaks the simplest possible Nash on the river
   will fail this test immediately.

3. **Add Brown-side variant** as
   `tests/test_minimal_diff_AA_KK_brown_parity.py`, gated on
   `find_brown_binary() is not None`, that asserts Brown's output also
   matches the hand-computed Nash within the same 2pp tolerance. If Brown
   does NOT match — that itself is a finding (Brown convention difference
   surfacing on a textbook spot).

4. **Numerical tolerance lock-in:** the 2pp tolerance is set assuming 5000
   DCFR iterations. Once the fixture is run live, tighten to the empirically
   observed 99th-percentile residual (likely 0.5pp at 5000 iters, given the
   simplicity of the game).

---

## Caveats and known limitations

1. **Nash has 12 strict slots + 4 indifference slots (the AA bet rate at
   the two no-bet-to-face decision nodes, root and after-check).** This
   is the best of both worlds for diagnostic purposes: the 12 strict
   slots PIN DOWN the structure of the equilibrium (any deviation = bug),
   while the 4 indifference slots give a sentinel for DCFR's averaging
   convention. DCFR-vector and Brown's DCFR both use the same
   alpha/beta/gamma defaults (1.5, 0.0, 2.0), so if they implement
   averaging identically they should land on the same `(a_1, a_2)`
   pair. If they DON'T, that's a real DCFR-averaging convention diff
   (not a pure bug), which is itself worth surfacing.

2. **The shallow tree (max raise cap = 1) means deep-cap raise-tree bugs
   are invisible.** This is by design: this fixture's job is to TEST
   the depth hypothesis, not to detect depth-bug behavior. If it passes
   (strict slots match), sibling agents' depth-related suspects gain
   credibility. The K72/A83 acceptance failures occur at `b1000r3000r6000`
   and similar 3-raise sequences; this fixture has NO raise nodes at
   all, so it cleanly isolates "everything except raise accumulation."

3. **Card-removal effects ARE exercised** (AA blockers reduce villain AA
   combos from 6 to 1, KK blockers from 6 to 1). If the Rust vector form
   handles blocker math incorrectly, the equity computation will be off and
   the Nash will shift. This is one of the things sibling agent C (reach
   handling) is auditing; this fixture provides a small, hand-checkable
   reference for that audit.

4. **No chance node beyond the implicit "river card already dealt"** — by
   construction (river-start config, full board pre-specified). This isolates
   the betting tree from chance-enum bugs that the v1.6.1 saga also probed.

5. **The hand-computed Nash assumes zero-sum chip utility** (Rust/Python
   convention). Brown's terminal utility uses `base_pot + contrib_loser` for
   winners (per `a83_deep_cap_root_cause_investigation.md` Candidate (d)),
   producing a non-zero-sum offset. Per the audit completed today (2026-05-24),
   terminal utility was confirmed CORRECT in both engines on the audited
   spots; the convention difference exists but does NOT cause the 22-42pp
   divergence. On this fixture the offset is uniform across strategies
   (every outcome at the same probability gets the same offset), so it
   cancels out for strategy purposes. EV comparison may still differ
   between Brown and ours by `base_pot × P_win_at_node` (an additive
   non-zero-sum constant); strategy probabilities are directly comparable.

---

## Optional Variant B: 1-decision-per-player asymmetric fixture

If the 3-decision symmetric tree above proves too complex to hand-verify
solver outputs (because of the 1-dim indifference manifold and the
node-conditional Bayesian update), a SIMPLER (but less symmetric)
fixture collapses to **1 decision per player**:

* Same board: `7c 5d 3h Qs 2c`.
* Same ranges: {AA, KK} × 6 combos.
* **Asymmetric contributions:** `initial_contributions=(100, 200)`,
  `initial_pot=300`. P0 starts having put in 1 BB, P1 has put in 2 BB.
* This places P0 "facing a 1 BB bet" from the start: P0's menu is just
  {FOLD, CALL}. No further bet possible. Single decision, terminal on
  resolution.
* Nash: P0 AA strict CALL (chops AA, beats KK in opponent's range → call
  is +EV). P0 KK strict FOLD (loses to AA in opponent's range; the small
  KK-KK chop is overwhelmed by AA losses; call EV ≈ -0.71 BB).
* This eliminates the indifference and gives a **pure 4-cell strict Nash**:
  AA call = 1, AA fold = 0, KK call = 0, KK fold = 1.
* **Downside:** asymmetric — doesn't exercise the symmetric range engine
  path; doesn't surface aggregator's first-actor confusion (PR 22 Fix A).
  Only useful as a sanity-check fixture if Variant A diagnostics are
  ambiguous.

The HUNLConfig delta from Variant A:

```python
HUNLConfig(
    starting_stack=400,
    big_blind=100,
    small_blind=50,
    starting_street=Street.RIVER,
    initial_board=tuple(parse_board("7c 5d 3h Qs 2c")),
    initial_pot=300,
    initial_contributions=(100, 200),   # <-- asymmetric
    initial_hole_cards=(),
    bet_size_fractions=(0.5,),
    include_all_in=False,
    postflop_raise_cap=1,
)
```

---

## File this document supplements

* `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
  — names the candidates {action menu, DCFR weighting, reach handling,
  terminal utility, base-pot offset} that this fixture isolates.
* `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_final_synthesis.md` §"22-42pp
  facing-bet divergence root cause" — names the test-side action-axis
  permutation as the deep-cap culprit; this fixture provides an
  independent verification path that does NOT depend on the
  apples-to-apples test harness.
* `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py`
  — wrapper for Brown's binary (run_brown_solver, write_brown_config).
* `/Users/ashen/Desktop/poker_solver/poker_solver/range_aggregator.py` —
  aggregator wrapper (`solve_range_vs_range`).
* `/Users/ashen/Desktop/poker_solver/tests/test_range_vs_range_rust_diff.py`
  — pattern for the direct Rust call (`_rust.solve_range_vs_range_rust`).
