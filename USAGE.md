# Using poker_solver — End-User Guide (v1.10.0)

For people who want to **use** the solver to improve their poker game,
not develop it. You should be comfortable in a terminal and editing a
config file; you do not need to read Python or Rust source. The README
is the developer-facing overview; this is the "what can I do with this
today" companion.

Document baseline: v1.0.0. Updates through v1.8.x layered in §5.3
(node-locking), §5.4 (asymmetric contributions), §5.5 (range
utilities), §5.6 (aggregator vs. true-Nash range-vs-range, v1.7.0+),
§5.7 (off-path filtering, v1.8.2), §5.8 (DCFR α-guard, v1.8.2), §7a
(ergonomic subcommands), §7b (known perf cliffs).

**v1.10.0 (this ship)** adds §5.9 (Preflop blueprint — instant lookup
+ interpolation + postflop subgame chaining), §5.10 (CLI
BB-normalization — canonical `--pot N --stack M` flags), and updates
§7b with the v1.10 postflop optimization stream (live flop subgame
now completes — was OOM/jetsam-killed — though full-range flop
memory still exceeds budget, deferred to v1.11). v1.9.0 was drafted
but never tagged — the
Premium-A blueprint feature train (PRs #149/#154/#158/#160 B10
per-combo train; PRs #163/#167/#171/#173/#174/#175/#176/#177/#178/#181/#182
Premium-A blueprint chain; PRs #165/#170 engine fixes; PR #152 CLI
BB-normalization) and the v1.10 postflop optimization PRs (arena
allocator, vector-form turn + flop forward walks, opt-in rayon, perf
harness + profiler — PRs #186/#187/#188/#189/#190 plus PR-1 + PR-3)
fold into the v1.10.0 MINOR bump. See README "What's new in v1.10.0"
for the consolidated list; per-stream detail in
`docs/v1_9_0_release_notes_DRAFT.md` and
`docs/v1_10_postflop_optimization_plan.md`.

---

## 1. What this is

`poker_solver` is an open-source (MIT) Heads-Up No-Limit Hold'em
solver. It computes Nash-equilibrium ("GTO") strategies for HU postflop
spots and short-stack push/fold play, alongside a fast equity
calculator. The engine is a Python reference backed by a Rust
performance tier (~24x faster on the postflop solver), diff-tested to
stay bit-exact.

On scope this beats every open-source HUNL solver we benchmarked. On HU
local solving it aims at PioSolver-class quality on a MacBook;
short-stack push/fold is exploitability-zero today, and the river
subgame solver has been externally validated against
`noambrown/poker_solver` (MIT). It is not trying to be a multiway,
cloud-hosted library service like GTO Wizard.

v1.0.0 (2026-05-22) is the first end-user-shippable artifact. CLI and
Python library are stable; the NiceGUI desktop app ships alongside in
mock mode (see §4).

---

## 2. Installing on macOS

### Path A: `.dmg` (v1.10.0)

The v1.10.0 `.dmg` is launchable from Finder — the v1.6.0 fork-bomb
defect was resolved in v1.8.0 (PR #42, `728206e` — added
`multiprocessing.freeze_support()` at module level in the PyInstaller
entry point so NiceGUI workers no longer re-exec the frozen app
recursively). The v1.10.0 bundle additionally ships the 27 preflop
blueprint shards (~21 MB compressed) so the chart widget works
offline.

The shipped artifact (`Poker-Solver-1.10.0-arm64.dmg`) is ad-hoc
signed (**not notarized**) and arm64-only. First launch requires the
macOS Gatekeeper override: right-click the `.app` → **Open** →
confirm. (Double-clicking from Finder will refuse the launch with a
"developer unverified" dialog; the right-click flow bypasses it
explicitly per user consent.) The "universal2" claim from earlier
labeling was retired in PR 44 (DMG filename now matches the actual
arch) and reinforced in PR 86 (build script enforces
`lipo -info architecture: arm64` post-build).

Intel Mac users: source-build via Path B below. See
[`docs/dmg_install_guide.md`](docs/dmg_install_guide.md) for the full
install + launch flow.

### Path B: pip + cargo (power users)

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

pip install -e .            # Build and install Python + Rust
pip install -e ".[ui]"      # Optional UI extra (quote for zsh)
```

Gives you the `poker-solver` CLI and the `poker_solver` Python package.

---

## 3. What you can actually do today

These are the workflows that produce **real GTO strategies**, not
placeholders. Everything in this section runs through the CLI or the
Python API.

### 3a. Short-stack push/fold (2–15 BB)

Use this when you are short and want to know whether to jam or call a
jam. Charts are fully converged (residual exploitability essentially
zero) and cover every integer stack depth in `[2, 15]` BB, both
positions.

There is no dedicated `pushfold` CLI subcommand; lookup auto-dispatches
inside `solve` for short HUNL configs, and is also exposed as a Python
function:

```bash
# Frequency that SB jams AKs at 10 BB:
python -c "from poker_solver import get_pushfold_strategy; \
    print(get_pushfold_strategy(stack_bb=10, position='sb_jam', hand='AKs'))"

# Full 169-cell chart for one (depth, position) cell:
python -c "from poker_solver import get_full_range; import json; \
    print(json.dumps(get_full_range(8, 'bb_call_vs_jam'), indent=2))"
```

Positions: `sb_jam` (SB jam frequency) and `bb_call_vs_jam` (BB call
vs. SB jam). Hand classes: standard notation (`AA`, `AKs`, `AKo`).
Output is a frequency in `[0, 1]`.

A full HUNL configuration also auto-routes to the chart when it lands
in range — `result.backend` returns `"pushfold_chart"`.

**v1.8.2: EV alongside the frequency.** Pass `return_ev=True` to
`get_pushfold_strategy` to receive a `{"strategy": prob, "ev_bb": ev}`
dict (EV in big blinds) instead of a bare frequency. Useful for
push/fold UIs that want to surface "what does the deviation cost?"
next to the chart cell:

```python
from poker_solver import get_pushfold_strategy
cell = get_pushfold_strategy(stack_bb=10, position="sb_jam",
                             hand="AKs", return_ev=True)
print(cell)   # {"strategy": 1.0, "ev_bb": 1.62}
```

### 3b. River subgame solve

Use this for a concrete river spot. This is the only full HUNL solve
that is end-to-end production-validated in v1.0.0 — diff-tested against
`noambrown/poker_solver` (MIT) on shared seeds (see
`tests/test_river_diff.py`).

```bash
# Default river fixture (AhKc vs QdQh on As 7c 2d Kh 5s, 500 iters):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500

# Same spot, Rust backend (~24x faster):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust
```

Reading the output: `Game value` is **P0's EV in BB per hand** (positive
= P0 winning). The `solver._game_value` returns `ev[0]`, i.e. P0's EV;
`HUNLPoker.utility` divides by big blind. `Exploitability (final)` is
the residual distance from Nash; smaller is better. `Average strategy`
lists each infoset with a probability vector across its legal actions.

To solve your own river spot, build a custom `HUNLConfig` in Python
(see §5).

**Postflop bet-size flags (`--hunl-mode postflop`, v1.11).** The ad-hoc
postflop solve path accepts a configurable bet menu:

```bash
poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" \
    --bet-sizes "33,75,150" \
    --flop-bet-sizes "33" --turn-bet-sizes "75,150" \
    --raise-sizes "2.5,3"
```

- `--bet-sizes` — comma-separated pot-fraction **percentages**; the
  flat/fallback opening-bet menu for any street without an override.
- `--flop-bet-sizes` / `--turn-bet-sizes` / `--river-bet-sizes` —
  per-street pot-fraction % overrides (omit to inherit `--bet-sizes`).
- `--raise-sizes` — comma-separated raise **multipliers** of the bet faced
  (e.g. `2.5,3` = 2.5x / 3x), NOT pot-fraction percentages. Default `3.0`;
  at most 5.

### 3c. Equity calculations

Use this for any preflop, flop, turn, or river all-in equity question.
Concrete hands with a small remaining board space (e.g. a flop with 990
runouts) auto-enumerate exactly in tens of milliseconds; range vs.
range falls back to Monte Carlo at 250k iterations by default
(~0.1% SE per hand).

```bash
# Hand vs hand on a flop (exact enumeration, ~60 ms):
poker-solver equity AhKh QdQc --board 2h7h9d

# Range vs hand (Monte Carlo, 250k iters):
poker-solver equity "AA,KK,AKs" QdQc

# Bump precision (1M iters, deterministic):
poker-solver equity AhKh QdQc -n 1000000 --seed 0
```

Output is `win / tie / equity` per hand. The `Iterations` header tells
you whether the exact path or MC fired.

---

## 4. The UI (currently mock mode)

```bash
poker-solver ui
# Then open http://127.0.0.1:8080
```

What you see: a 13x13 range matrix with hand-class labels (PioSolver
palette), a board picker, a solver controls panel (iterations,
bet-size menu, target-exploitability mode), a live exploitability
curve, a decision-tree browser with a reach-frequency filter, and a
per-combo inspector strip below the matrix.

**Mock-mode banner — plain terms.** When you click **Solve**, the
results panel is populated from a fixture, not from a real solve. All
the visuals, frequencies, and EV numbers are placeholders for UI
development. A banner across the top makes this explicit. v1.0.0
deliberately built the UX against this mock surface so v1.0.0 could
ship now; a future PR swaps in the real solver, expected with v1.1.

Still useful in v1.0.0 for: getting familiar with the workflow,
planning analysis sessions, giving feedback. For real strategies
today, drop down to the CLI in §3.

---

## 5. Building a custom range-vs-range solve

§3b runs the bundled `default_tiny_subgame` fixture (one hand vs one
hand). For real range-vs-range analysis on a board of your choice you
have two options:

- **§5.1** — Build a `HUNLConfig` with `initial_hole_cards=()` and call
  `solve` directly. This is the "true" range-vs-range path used by
  `test_river_diff.py` for the diff vs Brown's solver, but it is **not**
  practical for interactive analysis (see the perf caveat in §5.1).
- **§5.2** — Use `solve_range_vs_range` (v1.3.0+), the blueprint
  aggregator. This runs one per-hand 1v1 subgame per hero class
  representative and aggregates by combo count. The recommended path
  for interactive range queries today.

### 5.1 Direct full-range solve via `solve` (diff-test path; slow)

Construct a `HUNLConfig` directly. Leaving `initial_hole_cards=()` tells
the solver to enumerate the full range; the engine handles the chance
node over hole-card pairs.

```python
from poker_solver import Card, HUNLPoker, solve
from poker_solver.hunl import HUNLConfig, Street

board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))

cfg = HUNLConfig(
    starting_stack=10_000,          # integer cents; 10_000 = 100 BB
    starting_street=Street.RIVER,
    initial_board=board,
    initial_pot=1_000,
    initial_contributions=(500, 500),
    initial_hole_cards=(),          # empty -> enumerate full range
)

result = solve(HUNLPoker(cfg), iterations=500, backend="rust")

print(f"game value (BB):       {result.game_value:+.4f}")
print(f"final exploitability:  {result.exploitability_history[-1]:.6f}")
print(f"infosets in strategy:  {len(result.average_strategy)}")
```

Field notes (from `poker_solver.hunl.HUNLConfig`):

- `starting_stack` — integer cents; `10_000` is 100 BB (1 BB = 100 cents).
  Floating-point chip arithmetic is forbidden in the engine.
- `starting_street` — `Street.FLOP`, `Street.TURN`, or `Street.RIVER` for
  postflop subgames. Preflop full solves are not yet shipped (§7).
- `initial_board` — tuple of `Card`s matching the chosen street (3 for
  flop, 4 for turn, 5 for river).
- `initial_pot` / `initial_contributions` — chips already in the pot at
  subgame start. Either `contributions` sums to `initial_pot`, or
  `(0, 0)` for a dead-money subgame.
- `initial_hole_cards` — leave as `()` for range vs. range; pass a
  `((c0, c1), (c2, c3))` tuple to pin both hands (this is what
  `default_tiny_subgame` does).
- `bet_size_fractions` — pot fractions for opening bets; flat/fallback menu.
  Default `(0.33, 0.75, 1.00, 1.50, 2.00)`.
- `flop_bet_fractions` / `turn_bet_fractions` / `river_bet_fractions`
  (v1.11) — optional per-street bet menus; `None` (default) falls back to
  `bet_size_fractions` for that street.
- `raise_size_xs` (v1.11) — raise sizes as **multipliers of the bet faced**
  (default `(3.0,)`), NOT pot fractions; raises no longer use
  `bet_size_fractions`.
- `rake_rate` / `rake_cap` — must remain `0.0` / `0` in v1.0.0;
  non-zero values raise `ValueError` (rake lands in PR 9).

Result fields:

- `game_value` — P0's EV in BB per hand (positive = P0 winning). The
  solver returns `ev[0]`; `HUNLPoker.utility` divides by big blind.
- `exploitability_history` — exploitability sample at each `log_every`
  iteration, plus a final entry.
- `average_strategy` — `{infoset_key: [prob, ...]}` over the legal
  actions at that infoset.

**Honest caveats.** Only `default_tiny_subgame` (the river hand-vs-hand
fixture in §3b) is production-validated against `noambrown/poker_solver`
via `tests/test_river_diff.py`. Custom range-vs-range solves run
bit-exact between the Python reference tier and the Rust backend on toy
ranges, but a full standard-flop / standard-range solve has not yet been
run to convergence on this engine (see §6 known limitations).

**⚠️ Honest perf caveat (v1.x.y):** The `initial_hole_cards=()` "full range
enumeration" path exists in the code (used by `test_river_diff.py` for
diff-testing against Brown's solver), but is NOT practical for interactive
analysis as of v1.1.0:

- Empirically tested: 500 Rust iters + 2 bet sizes ran >10 minutes without
  completing the post-solve `exploitability()` walk (~1M combo lossless tree).
- Stripped-down test (1 bet size, no raises, 50 iters) still ran >5 minutes
  without finishing.
- The bottleneck is the Python-tier exploitability walk, not the Rust solve
  itself; the solver gets the strategy, but the exploitability number takes
  forever.

**For interactive range-vs-range analysis, use the per-hand subgame pattern:**
1. Solve the spot for each hand class you care about (16-169 solves)
2. Aggregate per-hand frequencies weighted by combo counts
3. Sum into a range-level frequency (the "Pluribus blueprint" pattern)

This is the v1.3+ planned work; the per-hand path runs in seconds per hand.

For now: build configs with FIXED hole cards (e.g., `(Card.from_str("As"), Card.from_str("Kh"))`)
for ad-hoc spots, or use the push/fold charts (≤15 BB) and equity calculator
(any street). The river subgame fixture solves in seconds.

### 5.2 Range-vs-range API via the blueprint aggregator (v1.3.0+)

v1.3.0 shipped `solve_range_vs_range` as the production-safe range-level
workaround for the "full chance-enum range-vs-range solve" gap (Option A,
deferred). The aggregator runs one per-hand 1v1 subgame per hero-class
representative, then averages frequencies weighted by combo count
(`AA = 6`, `AKs = 4`, `AKo = 12`).

```python
from poker_solver import (
    Card,
    HUNLConfig,
    Street,
    solve_range_vs_range,
)

cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.TURN,        # see perf caveat below
    initial_board=tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh")),
    initial_pot=200,
    initial_contributions=(100, 100),
    bet_size_fractions=(0.75,),
    include_all_in=False,
    postflop_raise_cap=2,
)

# Aggressor query (default; hero opens / c-bets):
result = solve_range_vs_range(
    config_template=cfg,
    hero_range=["AA", "KK", "AKs", "AKo", "QQ"],
    villain_range=["QQ", "JJ", "TT", "AQs"],
    iterations=200,
    backend="rust",
    # hero_player=0 (default) -> hero is aggressor (P0)
)
print(result.position)              # "aggressor"
print(result.range_aggregate)       # {"check": ..., "bet_75": ...}

# Defender query (new in v1.3.1; hero faces villain's lead):
result_def = solve_range_vs_range(
    config_template=cfg,
    hero_range=["AA", "KK", "QQ"],
    villain_range=["AA", "KK"],
    iterations=200,
    backend="rust",
    hero_player=1,                  # hero is defender (P1)
)
print(result_def.position)          # "defender"
print(result_def.range_aggregate)   # frequencies are P1's first-decision mass
```

#### `hero_player` parameter (v1.3.1)

- `hero_player=0` (default) — Hero occupies engine slot 0 (postflop IP /
  the player who acts AFTER P1's lead). Returned frequencies are hero's
  response to villain's modal opening action. `result.position ==
  "aggressor"`.
- `hero_player=1` — Hero occupies engine slot 1 (postflop OOP / first to
  act postflop in HUNL). Returned frequencies are hero's FIRST decision
  (open / lead vs. check). `result.position == "defender"`.

**Always check `result.position` before labeling the output**: the
range-aggregate dict mixes `"check"` / `"bet_*"` (aggressor side) with
`"fold"` / `"call"` / `"raise_*"` (defender side) only when the input
spot has unmatched contributions; in the dominant matched-pot postflop
case, the dict you get back is from hero's perspective at hero's first
decision.

**Bug history.** v1.3.0 hardcoded `hero_player=0` and the extraction
walker silently passed through P1's modal action before grabbing P0's
frequencies. On no-history defending spots (river bluff-catchers, MDF
queries) P1 modally checked, so P0 had no bet to face and the API
returned ~100% check no matter what hero was. Caught by the Option B
pre-ship stress test S4 (internal mirror).

#### Honest perf caveat — 100 BB flop-start is minutes, not seconds

v1.3.0 ships with a 30 s ceiling per per-hand solve (`time_budget_per_solve_s`).
A 100 BB flop-start spot at full lossless tree size exceeds this budget
for most hero classes:

- A minimal AA-vs-QQ flop solve (As-Ks-7h, 100 BB, 2 bet sizes) ran
  **146 s** during the pre-ship stress test — about 5x the per-solve
  budget. Most hero classes hit `partial_misses` and the aggregator
  drops them.
- Turn-start at 100 BB completes per-hand in 1-3 s on the Rust backend;
  a 6x5 query finishes in ~25-30 s end-to-end.
- River subgame solves are sub-second.

For 100 BB flop-start range queries today, either:

1. Use the turn-start path (`starting_street=Street.TURN`) with a 4-card
   board — this is what the smoke test in
   `tests/test_range_vs_range_aggregator.py` exercises and is the
   currently-recommended path.
2. Drop to a shorter stack (e.g. 25-50 BB) where the lossless flop tree
   is small enough to finish per-hand inside the budget.

A Rust port of the post-solve exploitability walk (Option A) is in
flight and will lift the per-solve budget high enough to make 100 BB
flop-start range queries practical.

#### Other caveats (already in v1.3.0)

- **1v1 collapse.** Each per-hand solve is a 1-combo-vs-1-combo Nash.
  Hero's bet-size mix can flip entirely based on `bet_size_fractions`
  (e.g. AA bets 100% under `(0.75,)` but checks 100% under
  `(0.33, 0.75)` on some boards). This is a structural property of the
  workaround, not a bug — caveated in `range_aggregator.py:19-32`.
- **Bet-size frequencies are 1v1 outputs**, not GTO range-vs-range
  mixed sizing. Use Option A (when it ships) for true Nash range-mix
  sizing.
- **Combo-weighted, not suit-aware.** AA's 6 combos all contribute the
  same dict; we don't distinguish AhAd vs AsAh on suit-isomorphic
  boards.

### 5.3 Node-locking via `locked_strategies` (v1.4.0)

v1.4.0 shipped node-locking on `solve_hunl_postflop`. Pass a
`locked_strategies` mapping of `{infoset_key: [prob, ...]}` to pin one
or more infosets to a fixed action distribution; the solver computes
the best response against the locked strategy. Useful for exploiting a
specific population leak ("villain over-folds the turn") or for
diagnosing whether a board favors aggressor or defender under a
hypothetical line.

```python
from poker_solver import Card, HUNLConfig, Street, solve_hunl_postflop

# Worked example pins hero + villain combos so the snippet completes in
# under a second. Range-vs-range node-locking requires the per-hand
# aggregate pattern (see §5.2); leaving `initial_hole_cards=()` triggers
# the full-range chance-enum + post-solve exploitability walk, which is
# minutes-to-hours wall-clock (see §7b honest perf cliffs).
board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))
cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.RIVER,
    initial_board=board,
    initial_pot=1_000,
    initial_contributions=(500, 500),
    initial_hole_cards=(
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Qd"), Card.from_str("Qh")),
    ),
)

# Pin one infoset to a fixed fold/call/raise mix. Replace the placeholder
# key with a real one from `result.average_strategy.keys()`; unmatched
# keys are silently ignored.
locked = {
    "<infoset_key_str>": [1.0, 0.0, 0.0, 0.0],  # 100% fold at that node
}
result = solve_hunl_postflop(cfg, iterations=500, locked_strategies=locked)
```

Empty / `None` is bit-identical to v1.3 behavior (the lock-check
fast-path returns immediately). See `tests/test_node_locking.py` for
worked examples that cover both Python and Rust backends and the
infoset-key format the solver expects.

### 5.4 Asymmetric initial contributions (v1.4.1)

v1.4.1 lifted the symmetric `initial_contributions=(c, c)` constraint
for facing-bet postflop subgames. Now you can set up a spot where one
player has already led and the other faces the lead — useful for "I
defended OOP, villain c-bet 2/3, what's my response?" queries.

```python
from poker_solver import Card, HUNLConfig, Street, solve_hunl_postflop

board = tuple(Card.from_str(c) for c in ("As", "7c", "2d"))
# Pot = 200; P0 contributed 100, P1 contributed 150 (P1 led 50 into 200).
# P1's lead lands on the table; P0 faces the bet.
cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.FLOP,
    initial_board=board,
    initial_pot=250,
    initial_contributions=(100, 150),  # asymmetric: P1 has the larger contribution
    initial_hole_cards=(
        (Card.from_str("Ah"), Card.from_str("Kd")),
        (Card.from_str("Qc"), Card.from_str("Qd")),
    ),
)
result = solve_hunl_postflop(cfg, iterations=500)
```

Invariants enforced (`poker_solver/hunl.py` validation):

- `initial_contributions` must be non-negative and not exceed
  `starting_stack`.
- When asymmetric, `sum(initial_contributions)` must equal
  `initial_pot` (or both be `(0, 0)` for a dead-money subgame).
- The player with the smaller contribution acts first (they face the
  bet); the engine threads this through the action ordering and the
  hole-deal routing.

See `tests/test_asymmetric_contributions.py` for the full set of
worked configurations.

### 5.5 Range utilities

`Range` (in `poker_solver.range`) accepts standard PioSolver notation
(`"AA,KK,AKs,AKo"`) and exposes set-membership operations for
range-arithmetic in scripts and notebooks. `Range.diff(other)` (available
since v1.4.3) returns a new `Range` containing the combos in `self` that
are not in `other`, with strict set-membership semantics — useful for
computing range intersections / complements without rebuilding combo
lists by hand.

### 5.6 Aggregator vs. true-Nash range-vs-range (v1.7.0+)

v1.7.0 ships `solve_range_vs_range_nash` (in
`poker_solver/range_aggregator.py`) as a true joint-Nash range-vs-range
entry, alongside the existing `solve_range_vs_range` aggregator. Both
are now first-class; pick the right one for the question you're asking.
See `docs/aggregator_vs_true_nash_explainer.md` for the long-form
distinction.

#### When to use `solve_range_vs_range` (aggregator)

- Population-level frequency reads where a per-combo perfect-info
  approximation is good enough.
- Production-scale fixtures (8+ classes × multi-street) under Sarah-grade
  interactive budgets (≤5 min).
- Blueprint-style strategy development; fast 13×13 matrix displays.
- **Caveat:** not true joint Nash. Per-combo perfect-info aggregation can
  inflate aggressive frequencies on selected baskets (especially tight
  pot-odds bluff-catch spots and polarized monotone-board decisions —
  see W1.2 / W3.5 below).

#### When to use `solve_range_vs_range_nash` (true Nash via PR 23 vector-form CFR)

- True joint range-Nash equilibrium needed; bluff-catching frequencies
  driven by full-range pot odds.
- Tight pot-odds bluff-catch decisions on the river.
- Polarization analysis on monotone / draw-heavy boards.
- River single-shot solves (sub-second on Rust).
- Brown / commercial-solver parity comparisons.
- Smaller fixtures (≤6 hero classes, river or shallow flop).
- **Caveats:** slower than the aggregator on larger fixtures (8-class × flop
  multi-street × 500 iter has measured >20 min — beyond Sarah's ≤5 min
  budget). Polarization signal narrows on narrow ranges; use ≥15 hero
  classes for a tight verdict on monotone-board pure-check questions.

#### Worked examples

- **W1.2-style river bluff-catch** (e.g. JJ facing a pot bet on a draw-heavy
  river): use Nash. The aggregator path produced a ~7.7% fold artifact
  that Nash correctly resolves to ~0% on the same inputs.
- **W3.5-style monotone polarization** (AA on a monotone river, deciding
  pure-check vs polarized bet): use Nash with ≥15 hero classes. At 6
  classes the signal is partial (AA check ~0.94 vs target ≥0.99).
- **W2.1-style production RvR chart** (8+ classes × multi-street, building
  a population-frequency reference): use the aggregator. Nash is correct
  but slower than Sarah's interactive budget allows today.

```python
from poker_solver import (
    Card, HUNLConfig, Street, solve_range_vs_range_nash,
)

cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.RIVER,
    initial_board=tuple(Card.from_str(c) for c in ("As","7c","2d","Kh","5s")),
    initial_pot=1_000,
    initial_contributions=(500, 500),
)
result = solve_range_vs_range_nash(
    config_template=cfg,
    hero_range=["AA","KK","QQ","JJ","TT"],
    villain_range=["AA","KK","AKs","AKo"],
    iterations=500,
    hero_player=1,                    # bluff-catcher / defender
)
print(result.range_aggregate)         # combo-weighted root frequencies
print(result.per_class_strategy)      # per-class root projection
print(f"exploitability: {result.exploitability:.4f}")
```

#### Class-label vs combo-level inputs (v1.7.0+)

`solve_range_vs_range_nash` accepts both class labels (e.g., `AA`, `KK`, `AKs`)
and 4-char specific combo labels (e.g., `AhAd`, `KhKd`). Internally, the
wrapper expands each class label to its full combo set:
- Pocket pair (e.g., `AA`): 6 combos (AhAd, AhAc, AhAs, AdAc, AdAs, AcAs)
- Suited (e.g., `AKs`): 4 combos (AhKh, AdKd, AcKc, AsKs)
- Offsuit (e.g., `AKo`): 12 combos (AhKd, AhKc, AhKs, ...)

A class-expanded range can have a Nash equilibrium that differs meaningfully
from a hand-curated combo subset of the same classes. For example, on a
monotone board, the full class-expansion of {AA, KK, ..., AKo} may not
produce AA's pure-check that a 15-combo curated subset would — because in
the wider range, AA dominates more of villain's range AND blocks more of
villain's bluff candidates.

Both are valid Nash equilibria. If you want the curated-subset Nash, pass
specific 4-char combo labels. If you want the full class-expanded Nash,
pass class labels.

```python
# Hand-curated 15-combo input (selected suit combos per class)
hero = ["AhAd", "KhKd", "QhQd", ..., "AhKh"]  # 15 combos

# Full class-expansion (~79 combos)
hero = ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44",
        "33", "22", "AKs", "AKo"]
```

#### When to use blueprint vs true Nash — bench numbers (v1.8.2)

After PR #114's TerminalCache landed, the river joint-Nash path is
fast enough to use interactively; turn is workable; flop remains
governed by tree size. Bench numbers below are sec/iteration on a 3-class
hero range against a 3-class villain range, Apple Silicon (M-series),
Rust backend.

| Street | Aggregator (§5.2) | True Nash (§5.6) | Recommendation |
|---|---|---|---|
| **River** | 0.44 s/iter | 0.09 s/iter | True Nash is now faster *and* correct on bluff-catch / polarized spots. Default to `solve_range_vs_range_nash` for river. |
| **Turn**  | 0.92 s/iter | 25.43 s/iter | Aggregator remains the interactive path; Nash only for offline / batch. |
| **Flop**  | impractical (>27 min CPU on a 3-class range; still running) | n/a at production scale | Use the aggregator for population-frequency reads; expect minutes-to-hours per query, not interactive. |

Practical decision rule:

- **River, any range size:** prefer `solve_range_vs_range_nash` (true
  joint Nash, sub-second per iter after PR #114).
- **Turn, ≤6 classes:** either path works; aggregator is faster for
  interactive use, Nash for tight bluff-catch / polarization decisions.
- **Turn, 7+ classes or flop:** aggregator only at interactive
  budgets; Nash for offline batch runs.
- **Multi-street / production-scale charts:** aggregator (the Sarah
  interactive budget governs).

### 5.7 Off-path infoset filtering (v1.8.2)

Deep HUNL trees accumulate strategies at infosets that are never
actually reached under the equilibrium — phantom probability mass that
can confuse downstream consumers ("why does my chart say hero raises
100% here?"). v1.8.2 (PR #129) annotates this directly on `SolveResult`:

- `result.reach_probability` — `{infoset_key: float}` mapping each
  infoset to its reach probability under the average strategy. Off-path
  nodes have reach `0.0` (or numerically close).
- `result.off_path_keys` — a `set[str]` of infoset keys whose reach
  probability is below the off-path threshold; equivalent to
  `{k for k, p in result.reach_probability.items() if p == 0.0}`.

```python
from poker_solver import HUNLConfig, solve_hunl_postflop

result = solve_hunl_postflop(cfg, iterations=500)

# Discrete filter — drop unreachable nodes outright:
on_path_strategy = {
    k: v
    for k, v in result.average_strategy.items()
    if k not in result.off_path_keys
}

# Continuous filter — pair each strategy with its reach mass:
weighted_strategy = {
    k: (v, result.reach_probability[k])
    for k, v in result.average_strategy.items()
}

# Diagnostics — what fraction of infosets are phantom?
total = len(result.average_strategy)
off = len(result.off_path_keys)
print(f"{off}/{total} infosets off-path ({100*off/total:.1f}%)")
```

Off-path filtering is opt-in (the raw `average_strategy` is
unchanged); downstream tooling that displays full strategy dumps
should filter before rendering to avoid surfacing strategies at nodes
that the solver never visits under the equilibrium.

### 5.8 DCFR α-guard (v1.8.2)

v1.8.2 (PR #113) hard-fails `solve(..., alpha=0)` — previously this
silently produced a non-Nash strategy because DCFR's regret-discount
weighting collapses with `alpha=0`. Behavior matrix:

- `alpha=0` → raises `ValueError` (was silent bug).
- `alpha` in `(0, 0.5)` → emits a `DeprecationWarning` and proceeds.
- `alpha >= 0.5` → proceeds normally. Brown & Sandholm 2019 paper
  default is `alpha=1.5` (the project default).

If you previously relied on `alpha=0` to disable DCFR's positive-regret
discount, switch to the linear-CFR setting (`alpha=1.0, beta=1.0,
gamma=1.0`) or vanilla CFR (`alpha=None` → routes to the CFR+ path).

```python
from poker_solver import solve, HUNLPoker

# OK — Brown & Sandholm paper default.
result = solve(HUNLPoker(cfg), iterations=500, alpha=1.5, beta=0.0, gamma=2.0)

# Warn — alpha in deprecated range.
result = solve(HUNLPoker(cfg), iterations=500, alpha=0.3)  # DeprecationWarning

# Error — alpha=0 now hard-fails.
result = solve(HUNLPoker(cfg), iterations=500, alpha=0)    # ValueError
```

### 5.9 Preflop blueprint — instant lookup for standard HU spots

The repo ships a precomputed Nash-equilibrium preflop chart in
`assets/blueprints/` — 9 stack depths × 3 ante configurations × all
169 starting-hand classes, solved offline at 25,000 DCFR iterations
per cell. Lookup is effectively instant; the alternative is running
the full HUNL preflop range-vs-range solve from scratch at query time
(minutes per cell). The loader (`poker_solver.blueprint_loader`,
Phase 2 / PR #174) is lazy + cached: the manifest is parsed once at
construction; shards are gzip-decompressed and parsed on first lookup
and held in memory afterward.

```python
from poker_solver.blueprint_loader import BlueprintLoader

loader = BlueprintLoader.from_dir("assets/blueprints/")
print(loader.available_depths())   # [20, 30, 40, 60, 80, 100, 150, 175, 200]

# SB root decision for AA at 100 BB, no ante:
probs = loader.lookup(stack_bb=100, ante="none", hand="AA", action_history="")
labels = loader.actions(stack_bb=100, ante="none", action_history="")
print(dict(zip(labels, probs)))    # {'fold': 0.0, 'call': 0.05, ...}

# BB's response after SB opens to 300:
probs = loader.lookup(stack_bb=100, ante="none", hand="AKs",
                      action_history="b300")

# Miss handling — lookup() returns None on absent shard / infoset / class.
# Use blueprint_interp (below) for off-anchor depths.
```

For off-anchor depths (e.g. 67 BB between the 60 and 80 BB anchors),
the Phase 3 interpolation module
(`poker_solver.blueprint_interp`, PR #173) blends per-cell across the
two flanking depths:

```python
from poker_solver.blueprint_interp import interpolate_strategy

strategies = {
    60: loader.lookup(stack_bb=60, ante="none", hand="AKs", action_history=""),
    80: loader.lookup(stack_bb=80, ante="none", hand="AKs", action_history=""),
}
probs_67 = interpolate_strategy(target_bb=67, strategies=strategies)
```

Depth-clamping (target below 20 BB or above 200 BB) is handled by
`interpolate_strategy` — values outside the supplied grid range fall
back to the nearest neighbor.

**Coverage.**

- Stack depths: 20, 30, 40, 60, 80, 100, 150, 175, 200 BB.
- Ante configs: `none` (0 BB), `half` (0.5 BB), `full` (1.0 BB).
- Action menu: `fold`, `call`, open sizes {2.0, 3.0, 4.0, 5.0} BB,
  3/4/5-bet multipliers {2.0, 3.0, 4.0, 5.0} of the previous bet,
  `all_in`. Raise cap 4 per preflop street.

  **Multiplier convention (important).** Action labels of the form
  `raise_to_X` mean **X is the TOTAL bet** the player puts in, including
  chips already committed in the pot. The engine's reraise multiplier
  is applied to the *last raise increment*, not the opponent's total bet:

  ```text
  bet_to = opp_total_contribution + multiplier × last_raise_increment
  ```

  where `last_raise_increment = previous_raise_to − contribution_before_that_raise`.
  It is NOT `multiplier × opponent_total_bet`.

  *Worked example.* SB opens to 2.5 BB (raise_to = 250 chips). The BB
  already has the 100-chip big blind in, so
  `last_raise_increment = 250 − 100 = 150`. With reraise multiplier
  `4.0`, the BB's 3-bet is:

  ```text
  bet_to = 250 + 4.0 × 150 = 850 chips = 8.5 BB total
  ```

  NOT `4.0 × 2.5 BB = 10 BB`. The source of truth is the
  `_build_action_labels` helper in `poker_solver/blueprint.py`
  (see `raise_to = opp_contrib + round(mult * prev_bet)` on the reraise
  branch).
- Hand resolution: 169 Pio-style canonical classes (pairs, suited,
  offsuit). The True Path B Rust kernel solves natively at this
  resolution; see
  [`docs/blueprint_developer_guide.md`](docs/blueprint_developer_guide.md)
  §"169-class vs 1326-combo paths" for why this is lossless for
  preflop.

**When the blueprint applies vs when it doesn't.**

| Spot                                              | Path                              |
|---------------------------------------------------|-----------------------------------|
| Standard HU preflop, on-anchor depth + ante       | Blueprint (instant)               |
| Standard HU preflop, off-anchor depth (e.g. 67 BB)| Blueprint, interpolated           |
| Postflop spot anchored on standard preflop history| Blueprint preflop + subgame solve via `poker_solver/chained.py` |
| Custom range, custom ante, depth < 20 or > 200 BB | Live solve (`solve_hunl_preflop` / `solve_range_vs_range`) |
| Stack ≤ 15 BB                                     | Push/fold chart (§3a)             |

**Regenerating the blueprint.** The driver script is idempotent and
re-running with the same `--output` directory skips completed cells.
Wall time for the full 27-cell grid is ~30-40 h on M-series silicon at
25k iterations.

```bash
caffeinate -i python scripts/generate_preflop_blueprint.py \
  --all-depths --all-antes --iterations 25000 \
  --output assets/blueprints/ \
  --verbose
```

See [`docs/blueprint_user_guide.md`](docs/blueprint_user_guide.md)
for the end-user "what / when / why" explainer (including why
specific cells may not match GTO Wizard or PokerCoaching exactly — Nash
multiplicity + action-menu differences). The engineering reference is
[`docs/blueprint_developer_guide.md`](docs/blueprint_developer_guide.md).

**Caveat — Nash multiplicity.** HUNL has multiple Nash equilibria
particularly at deeper stacks, so the blueprint output may diverge from
specific published charts even when both are valid GTO. The 100 BB
apples-to-apples validation in
[`docs/preflop_100bb_chart_validation_v2_2026-05-28.md`](docs/preflop_100bb_chart_validation_v2_2026-05-28.md)
reports 75.7% per-cell match against a public chart; the remaining
24.3% is explained by Nash multiplicity or sizing-menu differences.

**Chained postflop subgame (v1.10.0).** `solve_postflop_from_blueprint`
(PR #177) chains the blueprint preflop history into a live postflop
solve: it looks up the per-player 169-class strategy → expands to
1326-combo reach via suit-symmetric weighting → live-solves the
postflop street with the expanded reaches as priors via the
vector-form CFR backend. v1.10's arena allocator + vector-form turn /
flop forward walks + opt-in rayon (task #70) take the live **flop**
path from OOM/jetsam-killed (~5 min) to a solve that **completes**
and is bit-identical to the reference — a real wall-time +
reliability win. **However, full-range flop is still memory-bound:
RSS is ~6.7 GB at top_k=4 and ~7.7 GB+ at top_k=169 (where it does
NOT finish). The "flop top_k=169 in <120 s AND ≤ 1 GB RSS" gate is
NOT met.** PR-3 shipped the wall-time half (scratch-buffer reuse);
the board-tree memory collapse is deferred to v1.11. Use the flop
path for small-`top_k` / small-range spots that fit in memory. Turn
and river live-solves are real interactive wins (sub-second to
seconds on the Rust tier; exact measured wall/RSS at top_k 4/15/50:
[PENDING bench — fill from docs/v1_10_perf_bench_results.jsonl]).

```python
from poker_solver.blueprint_subgame import solve_postflop_from_blueprint

# v1.10.0 — chained flop solve, blueprint preflop priors.
# Turn / river were live-solvable in v1.9.0; the flop path completes
# in v1.10.0 for small-top_k / small-range spots (full-range flop is
# memory-bound — see honest framing below).
result = solve_postflop_from_blueprint(
    loader=loader,
    stack_bb=40, ante="none", action_history="b300c",
    board="Ad 8h 9d",   # flop (3-card)
    iterations=200,
)
print(result.backend)   # "postflop-subgame"
```

**Top-level router (v1.10.0).** `SolverRouter` (PR #181) is the
production-recommended front-door if you don't want to dispatch by
hand. It picks one of four backends per request:

- `lookup` — preflop, anchor depth + anchor ante, blueprint hit.
- `interp` — preflop, non-anchor depth in [20, 200] BB, anchor ante,
  blueprint hit on both bracket depths.
- `live` — out-of-envelope (non-standard ante, depth outside
  [20, 200] BB, action history not in the blueprint).
- `postflop-subgame` — postflop street (flop / turn / river); chains
  via `solve_postflop_from_blueprint`.

The selected backend is exposed on `SolveResult.backend` so callers
can introspect.

```python
from poker_solver.solver_router import SolverRouter

router = SolverRouter(loader=loader)
result = router.solve(stack_bb=67, ante="none", hand="AKs",
                      action_history="")
print(result.backend)   # "interp" (67 BB is between 60 and 80 anchors)
```

**Honest perf framing.** The v1.10.0 flop subgame now **completes**
(was OOM/jetsam-killed at ~5 min) and the result is bit-identical to
the reference — that is the correctness + wall-time win PR-3
(`cda3eeb`) delivered. **The original "flop top_k=169 in <120 s AND
≤ 1 GB RSS" headline gate is NOT achieved and is not claimed.**
Measured: full-range flop solve uses **~6.7 GB RSS at top_k=4** and
spikes to **~7.7 GB+ at top_k=169, where it does NOT finish**.
Flop-solve memory is dominated by the materialized board chance tree
(45 turn × 44 river betting subtrees) + per-node infoset storage at
full combo width — **independent of `top_k`**, so lowering `top_k`
does not bring it under budget. The board-tree memory collapse was
scaffolded but deferred (`RunoutCache::runout_values` allocated but
never read; audit S-4); full-range flop memory optimization is
deferred to v1.11
([`docs/v1_11_postflop_deeper_optimization_research.md`](docs/v1_11_postflop_deeper_optimization_research.md)).
Turn / river live-solves are real interactive wins (exact measured
wall/RSS at top_k 4/15/50:
[PENDING bench — fill from docs/v1_10_perf_bench_results.jsonl]).
Full honest narrative:
[`docs/v1_10_perf_benchmark_2026-05-28.md`](docs/v1_10_perf_benchmark_2026-05-28.md).

---

### 5.10 CLI BB-normalization (v1.9.0; canonical in v1.10.0)

Pre-v1.9.0, some CLI surfaces accepted chip values and others accepted
BB, which was an ongoing source of confusion. **PR #152** ships
canonical BB-implicit flags across `solve`, `pushfold`, `river`,
`parity`, and `subgame`:

```bash
# v1.10.0 canonical — BB units, no -bb suffix.
poker-solver river --board "As 7c 2d Kh 5s" --hero AdQd \
    --villain-range "QQ,JJ,AKs" --pot 12 --stack 95 --iters 200

poker-solver subgame --street turn --board "As 7c 2d Kh" \
    --hero AdQd --villain-range "QQ,JJ,AKs" --pot 8 --stack 100 \
    --iters 200
```

The legacy `--pot-bb` / `--stack-bb` aliases remain functional with
a one-shot deprecation warning emitted to stderr on first use:

```bash
# Legacy — still works, but emits a deprecation warning.
poker-solver river --board "As 7c 2d Kh 5s" --hero AdQd \
    --villain-range "QQ,JJ,AKs" --pot-bb 12 --stack-bb 95 --iters 200
# DeprecationWarning: --pot-bb is deprecated since v1.9.0; use --pot.
```

Resolution order if both forms are passed: canonical `--pot` /
`--stack` win; legacy `--pot-bb` / `--stack-bb` warn-and-use only when
the canonical form is absent. Defaults are `--pot=10` (BB) and
`--stack=100` (BB).

**Migration guidance.** New scripts and tutorials should use
`--pot N --stack M`. Scripted call sites that pass `--pot-bb` /
`--stack-bb` can be migrated by removing the `-bb` suffix; numeric
values are unchanged.

Tracking: task #70 plan in
[`docs/v1_10_postflop_optimization_plan.md`](docs/v1_10_postflop_optimization_plan.md);
v1.10 cumulative optimization ledger in
[`docs/rust_optimization_ledger.md`](docs/rust_optimization_ledger.md).

---

## 6. Library mode (caching solves)

For re-examining the same spots over time, library mode stores solve
results in a local SQLite file. Default location is
`~/.poker_solver/library.db`; override with `--library-path` on any
`library` subcommand, or set `$POKER_SOLVER_LIBRARY_PATH`.

```bash
poker-solver library list --table                         # recent spots
poker-solver library export <spot_id> ./my_spot.json      # portable JSON
poker-solver library import ./my_spot.json                # on another machine
```

```python
from pathlib import Path
from poker_solver import Library, default_tiny_subgame, solve, HUNLPoker
from poker_solver.library import SpotDescription

cfg = default_tiny_subgame()
result = solve(HUNLPoker(cfg), iterations=500)

spot = SpotDescription(config=cfg, label="river-AhKc-vs-QdQh")
with Library.open(Path.home() / ".poker_solver" / "library.db") as lib:
    spot_id = lib.put(spot, result)
    cached = lib.get(spot_id)
```

The `.db` is a single SQLite file you can copy, version, or open with
any SQLite tool. Spot IDs are deterministic sha256 of the canonical
description, so the same configuration always resolves to the same row.

---

## 7. Known limitations (v1.10.0)

- **UI standalone tab is mock mode; chart widget + chained tab are
  real (v1.10.0).** The PR #178 wiring landed for the chart widget
  (`blueprint` / `interpolated` / `live` source badges) and the
  chained postflop tab (consumes the blueprint preflop range + runs
  a live postflop subgame). The ad-hoc **Solve** button on the
  standalone tab still uses the PR 10a mock fixtures; real-solver
  swap there is tracked as PR 10b. For real preflop, use the chart
  widget; for real postflop, use the chained tab or the CLI / Python
  API.
- **No full-tree HUNL solving above 15 BB yet.** `--hunl-mode full`
  raises `NotImplementedError`. Fixed-hole-card preflop shipped in
  v1.1.0 (`solve_hunl_preflop`); full-tree preflop with the chance node
  over hole cards is still pending. Working paths today: the river
  subgame solver (`--hunl-mode tiny_subgame`) and
  ad-hoc postflop subgames (`--hunl-mode postflop`). Short stacks: use
  the charts in §3a. Note: `--hunl-mode postflop` enumerates the full
  hole-card chance node, so tree construction dominates wall-time —
  expect multi-minute runs on a flop and tens of seconds on a river,
  largely independent of `--iterations` or `--backend`. Use
  `--hunl-mode tiny_subgame` (or the `poker-solver river` subcommand
  in §7a) for fast hand-vs-hand or fixed-hero-vs-range exploration.
- **Production-scale flop/turn solves not validated end-to-end.** The
  postflop solver works on toy ranges and is bit-exact between Python
  and Rust, but a full standard-flop / standard-range solve has not
  been run to convergence. The Rust tier targets ~200K iterations in
  roughly 10 hours wall-clock on Apple Silicon — a projection, not an
  observation.
- **Apple Silicon is the primary target.** Intel Mac is untested in
  v1.0.0; Linux works for CLI and library mode but has no `.dmg`.
- **`--backend rust` is opt-in on postflop.** Python is the default
  because the reference implementation drives behavior; pass
  `--backend rust` explicitly for the performance tier.
- **`pyenv` arch hazard on Apple Silicon (dev-env quirk).** A pyenv
  Python built x86_64-only (notably `3.13-dev`) silently SKIPs Rust
  diff-tests instead of running them — the arm64 `.so` won't load.
  Check with `python -c "import platform; print(platform.machine())"`
  (must be `arm64`); see [`CONTRIBUTING.md`](CONTRIBUTING.md)
  §"Known development environment hazard" for the full fix.
- **`poker-solver` shim may resolve to a broken Python env.** After
  `pip install -e .` in temporary build dirs, the PATH shim
  (`~/.pyenv/shims/poker-solver` on pyenv systems) can resolve to a
  Python where `poker_solver` is no longer installed. Workarounds: use
  `./.venv/bin/poker-solver ...` from the project root, or run
  `python -m poker_solver.cli ...` with `.venv` activated. Full
  diagnostic:
  [`docs/poker_solver_shim_fix_2026-05-26.md`](docs/poker_solver_shim_fix_2026-05-26.md).

---

## 7a. Ergonomic subcommands (v1.7.0+)

v1.7.0 ships three CLI shortcuts that previously required dropping down
to one-line Python invocations: `pushfold`, `river`, and `parity`. Each
is a thin wrapper around an existing library API; zero engine changes.

- **`poker-solver pushfold`** — look up a short-stack push/fold chart
  cell. Wraps `poker_solver.pushfold.get_pushfold_strategy`.

  ```bash
  # Single cell:
  poker-solver pushfold --stack 10 --position sb_jam --hand AKs

  # Full 169-cell chart (JSON):
  poker-solver pushfold --stack 8 --position bb_call_vs_jam \
      --full-range --json
  ```

  Flags: `--stack` (int 2–15 BB), `--position` (`sb_jam` or
  `bb_call_vs_jam`), `--hand` (Pio notation; required unless
  `--full-range`), `--full-range`, `--json`.

- **`poker-solver river`** — solve a river spot with fixed hero hole
  cards vs. a villain range. Wraps `solve_hunl_postflop` with
  `initial_hole_cards` pinned to the hero combo and the villain combo
  enumerated from `--villain-range`; aggregates the hero first-decision
  frequencies across the villain range by combo weight.

  ```bash
  poker-solver river --board "As 7c 2d Kh 5s" --hero AdQd \
      --villain-range "QQ,JJ,AKs" --iters 200
  ```

  (Hero cards must not overlap any board card — e.g. `--hero AhKh` on
  this board would error because `Kh` is on the board.)

  Flags: `--board` (5 cards), `--hero` (2-card hole), `--villain-range`
  (Pio notation), `--iters` (default 200), `--pot-bb` (default 10),
  `--stack-bb` (default 100). For full joint-Nash range-vs-range
  semantics, use `solve_range_vs_range_nash` (§5.6).

- **`poker-solver parity`** — diff our river solve against Noam Brown's
  binary on a fixture spot. Wraps the differential-test machinery from
  `tests/test_river_diff.py` for ad-hoc sanity checks.

  ```bash
  poker-solver parity --fixture dry_K72_rainbow --iters 2000
  ```

  Flags: `--fixture` (spot id from `tests/data/river_spots.json`),
  `--fixture-path` (override fixture JSON), `--iters` (default 2000).
  Requires Brown's binary built via `scripts/build_noambrown.sh`; exits
  2 with a hint when the binary is missing.

### v1.8.2 CLI additions

- **`poker-solver subgame --street flop|turn|river` (PR #127).**
  Generalizes the v1.7.0 `poker-solver river` command to flop and turn
  boards. `--street` selects the starting street; `--board` accepts
  the matching card count (3 for flop, 4 for turn, 5 for river). The
  rest of the flag surface mirrors `river`. The legacy `river`
  subcommand remains for backwards compatibility (it now delegates to
  `subgame --street river`).

  ```bash
  # Flop subgame:
  poker-solver subgame --street flop --board "As 7c 2d" \
      --hero AdQd --villain-range "QQ,JJ,AKs" --iters 200

  # Turn subgame:
  poker-solver subgame --street turn --board "As 7c 2d Kh" \
      --hero AdQd --villain-range "QQ,JJ,AKs" --iters 200

  # River subgame (equivalent to `poker-solver river ...`):
  poker-solver subgame --street river --board "As 7c 2d Kh 5s" \
      --hero AdQd --villain-range "QQ,JJ,AKs" --iters 200
  ```

  Honest framing: flop and turn solves are bounded by the perf cliffs
  in §7b — expect minutes on a flop with default flags. For interactive
  flop range queries, use the §5.2 aggregator. The `subgame` CLI is the
  right tool for ad-hoc fixed-hero-vs-range sanity checks on flop/turn
  spots, not for production-scale chart generation.

- **`--walk-tree`, `--node`, `--format` (PR #123).** Available on
  `solve`, `river`, and `subgame`. Replace the default
  first-decision-only aggregate output with the full decision tree (or
  a drill-down at a specific node). Pair with `--format` to emit JSON
  or CSV for downstream tooling.

  ```bash
  # Walk the full decision tree, JSON to stdout:
  poker-solver subgame --street river --board "As 7c 2d Kh 5s" \
      --hero AdQd --villain-range "QQ,JJ,AKs" --iters 200 \
      --walk-tree --format json > river_tree.json

  # Drill into one specific infoset (csv for spreadsheet use):
  poker-solver subgame --street river --board "As 7c 2d Kh 5s" \
      --hero AdQd --villain-range "QQ,JJ,AKs" --iters 200 \
      --node "P0:RIVER:Ad Qd|As 7c 2d Kh 5s|" --format csv
  ```

  - `--walk-tree` — emit the full tree; mutually exclusive with
    `--node` (passing both errors out).
  - `--node <key>` — drill into one infoset (the key format is the
    same as `result.average_strategy.keys()`; copy from a previous
    `--walk-tree` JSON dump if you don't know the exact string).
  - `--format json|csv` — output encoding. Default is the legacy
    human-readable summary; `json` is structured for tooling, `csv` is
    flat for spreadsheets. Both filter `off_path_keys` automatically
    (see §5.7).

  Example abbreviated JSON output for `--walk-tree --format json`:

  ```json
  {
    "infosets": [
      {
        "key": "P0:RIVER:Ad Qd|As 7c 2d Kh 5s|",
        "reach_probability": 1.0,
        "strategy": {"check": 0.62, "bet_75": 0.38}
      },
      ...
    ],
    "off_path_count": 4,
    "exploitability_final": 0.0021
  }
  ```

- **`poker-solver --version` (PR #116).** Prints the package version
  string (e.g. `poker-solver 1.10.0`) and exits. Resolves the
  HIGH-deferred ergonomic gap from the PR #107 README/quickstart drift
  audit. Output tracks `poker_solver.__version__`.

  ```bash
  $ poker-solver --version
  poker-solver 1.10.0
  ```

### Still missing from the CLI

- **`poker-solver batch-solve` CSV quoting.** The `bet_sizes` column is
  comma-separated within a single CSV cell, so multi-value entries must
  be CSV-quoted: write `"0.5,1.0"` (with quotes), not `0.5;1.0` or
  bare-comma in an unquoted cell. The CSV schema also does not include
  hole-cards columns; per-row fixed-cards configs require the library
  path (`solve_hunl_postflop` with `initial_hole_cards=...`) rather
  than batch-solve.

---

## 7b. Known perf cliffs (v1.10.0 update)

The honest framing: the Python solver targets two regimes well —
short pushfold (§3a) and fixed-cards postflop subgames (§3b). The
v1.10 postflop optimization stream (task #70 — arena allocator,
vector-form turn + flop forward walks, opt-in rayon, perf harness)
materially improves the third regime (full-range postflop subgame on
the vector-form Nash path): turn and river are real interactive
wins, and the live **flop** subgame now **completes** (was
OOM/jetsam-killed at ~5 min) for small-`top_k` / small-range spots.
**Full-range flop, however, remains memory-bound (~6.7 GB+ RSS;
does not finish at top_k=169) — full-range optimization is deferred
to v1.11.** The §5.2 aggregator remains the production-safe
workaround for full-range flop charts and for cases where wall-time
matters more than joint-Nash semantics.

Regime guidance at a glance (v1.10.0):

- **Push/fold (≤ 15 BB):** instant; chart lookup, no solve (§3a).
- **Preflop (16-200 BB):** instant if the depth + ante hits the
  blueprint envelope (anchor or interpolated); seconds to live-solve
  out-of-envelope (§5.9). The `SolverRouter` (PR #181) dispatches.
- **River subgame spots:** fast (sub-second to seconds on the Rust
  tier — PR #114's terminal-leaf hand-strength caching ships in
  v1.8.2 and is unchanged in v1.10.0); good for interactive use.
- **Turn subgame spots:** seconds to tens of seconds on the
  vector-form Nash path (PR #114 + PR #170 vector-form BR walk +
  PR #190 vector-form turn forward walk). Interactive on the Rust
  tier today.
- **Flop subgame spots:** **completes in v1.10.0 (small ranges),
  but full-range remains memory-bound.** The pre-v1.10 flop path was
  OOM/jetsam-killed at the ~5-min mark on the J7o A♦8♥9♦ 40 BB
  reference fixture; v1.10's task #70 PR train (arena allocator,
  vector-form flop forward walk `cda3eeb`, opt-in rayon) makes the
  flop solve **complete** and bit-identical to the reference — a
  real wall-time + reliability win. **The original "flop top_k=169
  in <120 s AND ≤ 1 GB RSS" gate is NOT met.** Measured: full-range
  flop solve uses ~6.7 GB RSS at top_k=4 and ~7.7 GB+ at top_k=169
  (where it does NOT finish). Flop-solve memory is dominated by the
  materialized board chance tree (45 turn × 44 river betting
  subtrees) + per-node infoset storage at full combo width —
  **independent of `top_k`**, so lowering `top_k` does not bring it
  under budget. PR-3 shipped the wall-time half (scratch-buffer
  reuse); the board-tree memory collapse was scaffolded but deferred
  to v1.11 (`docs/v1_11_postflop_deeper_optimization_research.md`).
  The opt-in `CFR_RAYON_CHANCE=1` env var enables rayon-parallel
  chance branches; PR #189's microbench reported ~4.79× on flop
  top_k=169 (14-core M-series), but treat that as a TARGET until the
  formal 12-cell bench run confirms it. **For full-range flop charts
  today, use the §5.2 aggregator** — the live flop Nash path is only
  usable for small-`top_k` / small-range spots that fit in memory.
  Full honest narrative: `docs/v1_10_perf_benchmark_2026-05-28.md`.

- **`initial_hole_cards=()` on flop / turn / river is slow.** The
  full-range chance-enum path (§5.1) walks the lossless combo tree at
  the root, which scales poorly even with the Rust backend. Empirical
  observation: a 500-iter Rust solve on a standard river spot stalled
  >10 minutes in the post-solve exploitability walk (see §5.1 honest
  perf caveat). Not practical for interactive analysis as of v1.4.2.

- **Workaround today.** Use the scoped-per-class fixed-cards substitute
  pattern: pick representative hero combos per hand class (the same
  pattern the §5.2 aggregator uses internally), pin them via
  `initial_hole_cards`, solve each in seconds, then aggregate by combo
  weight. This is the pattern that worked for the W2.5 / W2.1
  retest-acceptance flows; the per-hand solves are fast and the
  aggregate is honest about being a blueprint approximation rather
  than joint Nash.

- **For full Nash range-vs-range, use `solve_range_vs_range_nash`
  (v1.7.0+).** v1.7.0 ships the vector-form CFR entry built on PR 23's
  Rust binding (per Brown's `cpp/trainer.cpp` vector path; see
  `DEVELOPER.md` §1 for the two-tier honesty note). This is the
  recommended path for tight bluff-catching / polarization decisions
  (§5.6). The aggregator (§5.2) remains the recommended path for
  production-scale charts and population-frequency reads under
  interactive budgets.

---

## 8. What's coming

The three items most likely to matter for users beyond v1.10.0:

- **PR 9 — HUNL preflop solve.** Shipped in v1.1.0 for fixed hole
  cards (`solve_hunl_preflop` is exported from the top-level package).
  v1.10.0's Premium-A blueprint feature train (§5.9) ships the
  precomputed-Nash lookup path for the 27-cell envelope and the
  chained postflop subgame. Full-tree preflop with the chance node
  over hole cards on out-of-envelope configs is still pending —
  `--hunl-mode full` continues to raise `NotImplementedError`.
- **PR 10b — real solver bindings in the UI standalone tab.** v1.10.0
  ships the chart widget + chained postflop tab on real solver output
  (PR #178), but the ad-hoc **Solve** button on the standalone tab
  still uses the PR 10a mock fixtures. Mechanical swap of
  `ui/mock_solver.py` for the real solver call pending.
- **v1.10 turn/river perf benchmark publication.** All four v1.10
  perf PRs are merged: PR-1 (arena+LTO, `eb5b4d0`/#197), PR-2
  (vector turn, `7fa4d73`/#190), PR-3 (vector flop, `cda3eeb`), and
  PR-4 (rayon, `f5ec665`/#189). The turn/river half of the 12-cell
  wall + RSS matrix (top_k ∈ {4, 15, 50} × {turn, river}) on the
  J7o A♦8♥9♦ 40 BB reference fixture is **PENDING a bench run** and
  will land in `docs/v1_10_perf_bench_results.jsonl`. The flop rows
  are already measured and **honest**: the flop solve completes but
  full-range RSS is ~6.7 GB+ (does not finish at top_k=169); the
  "<120 s AND ≤ 1 GB" gate is NOT met and full-range memory
  optimization is deferred to v1.11. See
  `docs/v1_10_perf_benchmark_2026-05-28.md` for the honest narrative.
  Per-PR re-runs of the canonical diff-test scaffold (PR #188)
  HARD-FAIL on bit-identity regressions.

Further out: 3-handed postflop (PR 12) is a post-v1 stretch goal;
CFR has no convergence guarantee for ≥3 players, so it would ship as
an explicitly-approximate mode.

---

## 9. Getting help

- Bug reports / feature requests: GitHub issues.
- Release notes: see [`CHANGELOG.md`](CHANGELOG.md) and the v1.0.0
  GitHub Release.
- License: MIT, see [`LICENSE`](LICENSE).
