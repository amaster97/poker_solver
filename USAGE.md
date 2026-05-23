# Using poker_solver — End-User Guide (v1.4.x)

For people who want to **use** the solver to improve their poker game,
not develop it. You should be comfortable in a terminal and editing a
config file; you do not need to read Python or Rust source. The README
is the developer-facing overview; this is the "what can I do with this
today" companion.

Document baseline: v1.0.0. Updates through v1.4.3 are layered in §5.3
(node-locking), §5.4 (asymmetric contributions), §5.5 (range utilities),
plus the new §7a (known CLI gaps) and §7b (known perf cliffs) sections.

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

### Path A: `.dmg` (recommended for non-developers)

A codesigned and notarized `.dmg` is the v1.0.0 distribution format.
A prebuilt `.dmg` is attached to the v1.0.0 GitHub Release; to build
your own:

```bash
sh scripts/build_macos_dmg.sh
```

Then double-click the `.dmg` in `dist/`, drag **Poker Solver** to
**Applications**, launch from there. The first launch triggers
Gatekeeper's quarantine prompt; because the artifact is signed and
notarized, click through without `xattr` workarounds.

Primary target: Apple Silicon (M-series). Intel Mac support is present
but untested in v1.0.0.

### Path B: pip + cargo (power users)

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

pip install -e .            # Build and install Python + Rust
pip install -e .[ui]        # Optional UI extra
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
pre-ship stress test S4 (see `docs/pr16_prep/stress_test_results.md`).

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

board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))
cfg = HUNLConfig(
    starting_stack=10_000,
    starting_street=Street.RIVER,
    initial_board=board,
    initial_pot=1_000,
    initial_contributions=(500, 500),
)

# Pin one infoset to a fixed fold/call/raise mix:
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

## 7. Known limitations (v1.0.0)

- **UI is mock mode.** Clicking **Solve** returns fixture data, not
  real strategies. Wait for PR 10b (expected v1.1) or use the CLI.
- **No HUNL solving above 15 BB yet.** `--hunl-mode full` raises
  `NotImplementedError`; full preflop is shipping in v1.1.0. Working
  paths today: the river subgame solver (`--hunl-mode tiny_subgame`) and
  ad-hoc postflop subgames (`--hunl-mode postflop`). Short stacks: use
  the charts in §3a.
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

---

## 7a. Ergonomic subcommands (v1.5.2+)

PR 39 added three thin CLI wrappers for workflows that previously
required Python one-liners. Library APIs are unchanged; these are pure
convenience shortcuts.

### `poker-solver pushfold` — short-stack chart lookup

Look up a single (depth, position, hand) cell or dump the full 169-cell
chart for one (depth, position) cell.

```bash
# Frequency that SB jams 88 at 9 BB:
poker-solver pushfold --stack 9 --position sb_jam --hand 88

# BB call frequency vs SB jam, JSON form:
poker-solver pushfold --stack 8 --position bb_call_vs_jam --hand AKs --json

# Full 13x13 chart for one cell:
poker-solver pushfold --stack 10 --position sb_jam --full-range
```

Flags:

- `--stack <BB>` — effective stack in BB (integer, 2-15 inclusive).
- `--position <sb_jam|bb_call_vs_jam>` — chart side.
- `--hand <CLASS>` — hand-class string (`AA`, `AKs`, `AKo`). Required
  unless `--full-range` is set.
- `--full-range` — emit all 169 cells instead of one lookup.
- `--json` — JSON output instead of human-readable.

Out-of-range stack depths (>15 BB) exit with code 2 and a message
pointing at the tree-builder solver.

### `poker-solver river` — fixed hero vs villain range, river-only

Solve a river spot with a fixed hero combo against a villain range, then
aggregate hero's first-decision frequencies across the villain combos
(weighted equally per combo; matches the §5.2 aggregator pattern but
with hero pinned).

```bash
poker-solver river \
    --board "As 7c 2d Kh 5s" \
    --hero AhKh \
    --villain-range "QQ,JJ,AKs" \
    --iters 200
```

Flags:

- `--board <CARDS>` — exactly 5 river cards.
- `--hero <HOLE>` — hero's 2-card hole (e.g. `AhKh`).
- `--villain-range <RANGE>` — PioSolver-notation range (e.g. `QQ,JJ,AKs`).
  Combos that share a card with `--hero` or `--board` are filtered out
  automatically.
- `--iters <N>` — DCFR iterations per per-combo solve (default 200).
- `--pot-bb <BB>` / `--stack-bb <BB>` — starting pot and per-player
  effective stack in BB (defaults: pot 10 BB, stack 100 BB).

Output: per-combo solve, then hero's averaged action distribution at
the first decision (`action_0` is fold, `action_1` is call/check, etc.,
in the order the engine's action abstraction emits them). The Mean
game value line is hero's EV in BB averaged over the villain combos.

### `poker-solver parity` — diff against Noam Brown's binary

Surfaces the river-spot parity machinery from
`tests/test_river_diff.py` (PR 7) as a one-shot CLI for ad-hoc sanity
checks.

```bash
# Diff against the bundled dry-board fixture:
poker-solver parity --fixture dry_K72_rainbow --iters 2000

# Custom fixture path:
poker-solver parity --fixture my_spot --fixture-path ./my_spots.json
```

Flags:

- `--fixture <ID>` — fixture id from `tests/data/river_spots.json`.
  Unknown ids exit code 2 with the available-id list.
- `--fixture-path <PATH>` — override the fixture JSON location.
- `--iters <N>` — DCFR iterations on both engines (default 2000, matches
  PR 7).

Brown's binary must already be built (`scripts/build_noambrown.sh`);
when it isn't, the command exits 2 with a build hint — same protocol
as the diff-test harness.

Output: per-side infoset-key counts, the overlap percentage, our
game-value, and (when Brown's stdout exposes it) the game-value diff.
Per-action numeric diff stays delegated to `test_river_diff.py`.

### Still missing from the CLI

- **`poker-solver batch-solve` CSV quoting.** The `bet_sizes` column is
  comma-separated within a single CSV cell, so multi-value entries must
  be CSV-quoted: write `"0.5,1.0"` (with quotes), not `0.5;1.0` or
  bare-comma in an unquoted cell. The CSV schema also does not include
  hole-cards columns; per-row fixed-cards configs require the library
  path (`solve_hunl_postflop` with `initial_hole_cards=...`) rather
  than batch-solve.

---

## 7b. Known perf cliffs (v1.4.x)

The honest framing: the v1.4.x Python solver targets two regimes
well — short pushfold (§3a) and fixed-cards postflop subgames (§3b).
Outside those regimes, performance is bounded by the
chance-enum-at-root architecture and the post-solve exploitability
walk. The §5.2 aggregator is the production-safe workaround today.

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

- **For full Nash range-vs-range, wait for v1.5.0.** PR 23 ships a
  vector-form CFR in the Rust tier (per Brown's `cpp/trainer.cpp`
  vector path; see `DEVELOPER.md` §1 for the two-tier honesty note).
  That closes the ~100x DCFR slowdown observed in v1.4.1 W2b
  benchmarks on range-on-both-sides flop / turn queries. Until then,
  the aggregator (§5.2) is the recommended interactive path.

---

## 8. What's coming

The three items most likely to matter:

- **PR 9 — full HUNL preflop solve.** Replaces the `NotImplementedError`
  above 15 BB. Shipping in v1.1.0.
- **PR 10b — real solver bindings in the UI.** Mechanical swap of
  `ui/mock_solver.py` for the real `solve_hunl_postflop` (and PR 9's
  preflop solver). ~1 week, lands after PR 9. Makes the UI produce real
  strategies.
- **PR 8 — NEON SIMD and public chance sampling.** Rust tier perf work;
  brings standard-flop solve time well below the 10-hour projection.

3-handed postflop (PR 12) is a post-v1 stretch goal; CFR has no
convergence guarantee for ≥3 players, so it would ship as an
explicitly-approximate mode.

---

## 9. Getting help

- Bug reports / feature requests: GitHub issues.
- Release notes: see [`CHANGELOG.md`](CHANGELOG.md) and the v1.0.0
  GitHub Release.
- License: MIT, see [`LICENSE`](LICENSE).
