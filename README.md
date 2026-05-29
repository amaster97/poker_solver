# poker_solver

A Texas Hold'em equity calculator and GTO solver, written in Python with
a Rust performance tier. Ships an exact / Monte Carlo equity engine, a
hand evaluator and range parser, closed-form-verified Kuhn and Leduc
solvers, a Heads-Up No-Limit Hold'em (HUNL) game tree with a 14-action
abstraction, DCFR-generated push/fold charts for 2-15 BB short stacks,
HUNL preflop + postflop solvers (Python + Rust), a range-vs-range API
in two forms (per-combo aggregator and joint vector-form CFR), and node
locking. Goalpost: PioSolver-class HU local solving on a MacBook.

## Status

- **Latest tagged release:** v1.10.0 (2026-05-28) — combined v1.9.0
  Premium-A blueprint feature train + v1.10 postflop optimization
  stream. Three user-visible capabilities ship together: (1) instant
  27-cell precomputed preflop blueprint lookup, (2) postflop subgame
  solving across all three streets — turn and river are interactive;
  the live **flop** path now **completes** (was OOM/jetsam-killed at
  ~5 min) via v1.10's arena allocator + vector-form chance
  compaction, though **full-range flop memory still exceeds budget**
  (~6.7 GB+ RSS; full-range optimization deferred to v1.11) — and
  (3) the W2.3 Sarah deep-stack turn workflow at strict-PASS via the
  vector-form best-response walk.
  Persona table: **17/0/0/0**. The v1.0 → v1.10.0 trajectory is
  documented in [`CHANGELOG.md`](CHANGELOG.md); v1.9.0 was drafted but
  never tagged (folded into the v1.10.0 MINOR bump). See "What's new
  in v1.10.0" below.
- **License:** MIT.
- **Platforms:** macOS (Apple Silicon primary), Linux. Intel Mac is
  source-build only.
- **Python:** 3.9+. Rust toolchain required (stable channel).
- **Working install path:** source build (`pip install -e .`).
- **`.dmg` installer:** v1.8.0's packaging fix
  (PR #42, `728206e` — `multiprocessing.freeze_support()` at module
  level in the PyInstaller entry point) resolved the v1.6.0 fork-bomb
  on Finder launch. The v1.10.0 `.dmg` bundles the 27 preflop
  blueprint shards (~21 MB) so the chart widget works offline. Apple
  silicon (arm64) only; ad-hoc signed (not notarized). See
  [`docs/dmg_install_guide.md`](docs/dmg_install_guide.md).

## Preflop blueprint mode (v1.10.0 — Premium-A)

The repo ships a precomputed Nash-equilibrium preflop blueprint in
`assets/blueprints/` — 9 stack depths (20, 30, 40, 60, 80, 100, 150,
175, 200 BB) × 3 ante configurations (`none` / `half` / `full` BB) ×
all 169 starting-hand classes, solved offline at 25,000 DCFR iterations
per cell. Lookups are effectively instant compared to the
minutes-per-cell live solve path. Custom ranges, non-standard antes,
and out-of-envelope depths still drop to the live solver.

**Python API.** Four entry points are now public:

- `poker_solver.blueprint.BlueprintLoader` (PR #174) — lazy loader +
  manifest sha256 validation + `lookup` / `actions` /
  `available_depths` methods.
- `poker_solver.blueprint_interp.interpolate_strategy` (PR #173) —
  convex linear blend across the two bracketing anchor depths for
  any depth in [20, 200] BB; `method="nearest"` snaps to nearest
  anchor.
- `poker_solver.blueprint_subgame.solve_postflop_from_blueprint`
  (PR #177) — chains the blueprint preflop history into a live
  postflop subgame (turn / river default; the **flop** path now
  **completes** in v1.10 for small-`top_k` / small-range spots, but
  full-range flop is memory-bound — see the honest framing below).
- `poker_solver.solver_router.SolverRouter` (PR #181) — top-level
  front-door that picks `lookup` / `interp` / `live` /
  `postflop-subgame` per request. Active backend exposed on
  `SolveResult.backend`.

**UI integration (v1.10.0, PR #178).** The NiceGUI app (`poker-solver
ui`) now consumes the blueprint:

- **13×13 chart widget** displays a `blueprint` / `interpolated` /
  `live` **source-indicator badge** in each cell tooltip. Anchor
  depth + ante combinations are instant lookups; off-anchor depths
  route through the interpolation path with `interpolated` badging;
  out-of-envelope cells fall through to a fresh live solve.
- **Chained postflop tab** surfaces the blueprint preflop range
  source per player at the top of the result panel and runs the
  postflop street live-solve with the blueprint-derived reaches as
  priors.
- **Live-solve confirmation modal** gates the fall-through to a
  fresh solve on out-of-envelope cells so users know they're about
  to spend wall-time, not hit a cache.

**B10 per-combo editor (v1.10.0, PRs #149 / #154 / #158 / #160).**
`Range` now stores per-combo fractional weights (`range["AKs"] = 0.6`).
The aggregator and vector-form CFR backend respect those weights in
the prior reach distribution, and the GUI range builder exposes a
per-combo intensity editor. Closes Sarah W2.2 (`Range.diff`) at
empirical PASS.

**Honest framing on postflop wall-times (v1.10.0).** v1.10's arena
allocator + vector-form turn/flop forward walks + opt-in rayon
(PR-1 arena+LTO `eb5b4d0`/#197 + PR-2 vector turn `7fa4d73`/#190 +
PR-3 vector flop `cda3eeb` + PR-4 rayon `f5ec665`/#189, all on
task #70) take the live flop subgame from OOM/jetsam-killed
(~5 min wall) to a solve that **completes** and is bit-identical to
the reference. That is a real wall-time + reliability win. **But
the original headline gate — "flop top_k=169 in <120 s AND ≤ 1 GB
RSS" — is NOT met and is not claimed.** PR-3 shipped the wall-time
half (scratch-buffer reuse), not the memory half (board-tree
collapse, deferred to v1.11). Measured: full-range flop solve uses
**~6.7 GB RSS at top_k=4** and spikes to **~7.7 GB+ at top_k=169,
where it does NOT finish**. Flop-solve memory is dominated by the
materialized board chance tree (45 turn × 44 river betting
subtrees) + per-node infoset storage at full combo width, which is
**independent of `top_k`** — lowering `top_k` does not bring it
under budget. Turn / river live-solves are real interactive wins
(exact measured wall/RSS at top_k 4/15/50:
[PENDING bench — fill from docs/v1_10_perf_bench_results.jsonl]).
**Net: the live flop path is usable for small-`top_k` /
small-range spots that fit in memory; full 169-class flop charts
remain memory-bound until v1.11.** Full honest narrative:
[`docs/v1_10_perf_benchmark_2026-05-28.md`](docs/v1_10_perf_benchmark_2026-05-28.md);
deferred work: [`docs/v1_11_postflop_deeper_optimization_research.md`](docs/v1_11_postflop_deeper_optimization_research.md).

Format and coverage are documented in
[`docs/blueprint_user_guide.md`](docs/blueprint_user_guide.md);
generation pipeline and engine-internals reference live in
[`docs/blueprint_developer_guide.md`](docs/blueprint_developer_guide.md).
Tracking: task #68 (Premium-A). PRs of record: #163 (subplan),
#167 (Phase 1 hybrid pipeline), #171 (Phase 1.5 True Path B
169-class kernel — measured 178× / 406× / 448× solve speedup at 15 /
40 / 100 BB), #173 (Phase 3 stack-depth interpolation), #174 (Phase 2
lazy loader), #175 (Phase 7 reference inventory + diff-test seed),
#176 (Phase 8 user + developer guides), #177 (Phase 4 postflop
subgame chaining), #178 (Phase 6 UI wiring — chart widget badges +
chained tab + live-solve modal), #181 (Phase 5 top-level
`SolverRouter`), #182 (preflop boundary `b`/`r` token-equivalence
fix), asset commit `1783bef` (27 shards + manifest, ~21 MB).

## What's new in v1.10.0

User-visible additions consolidated from the v1.9.0 Premium-A draft
(never tagged) and the v1.10 postflop optimization stream. All merged
on `origin/main` ahead of the v1.10.0 tag.

**Premium-A blueprint feature train (task #68)** — see "Preflop
blueprint mode" above for the full breakdown. Headline:

- **27 precomputed Nash-equilibrium preflop shards** (PR #171 + asset
  commit `1783bef`) — 9 stack depths × 3 ante configs, ~21 MB
  compressed in `assets/blueprints/`. Instant lookup; 38.5 min total
  compute on M-series silicon (vs 17-40 h hybrid-path projection).
- **Loader / interpolation / subgame / router public API** (PRs #173,
  #174, #177, #181, #182).
- **GUI consumes the blueprint** (PR #178) — chart widget
  source-indicator badges, chained postflop tab, live-solve
  confirmation modal.
- **User + developer guides** (PR #176) — `docs/blueprint_user_guide.md`,
  `docs/blueprint_developer_guide.md`.
- **Reference inventory + diff-test seed** (PR #175).

**v1.10 postflop optimization (task #70)** — flop subgame now
completes (correctness + wall-time win); full-range flop memory
optimization deferred to v1.11.

- **Thread-local arena allocator + LTO** (PR-1, merge `eb5b4d0`,
  PR #197) — new `arena.rs` `BumpArena` replaces per-call
  `vec![0.0; N]` allocations in the `dcfr_vector.rs` vector-form
  traverse path; `Cargo.toml` adds `lto = "fat"` + `codegen-units = 1`.
  Bit-identical at 1e-12 strategy / 1e-9 EV. Target: 3-5× flop wall
  reduction (measured numbers pending the formal bench run).
- **Vector-form turn forward walk** (PR-2, merge `7fa4d73`, PR #190)
  — chance-template extraction at tree-build time + specialized
  `traverse_turn_chance` dispatch. Bit-identical to main at 1e-12
  strategy tolerance.
- **Vector-form flop forward walk** (PR-3, merge `cda3eeb`) —
  extends PR #190's template framework to double chance compaction
  (turn × river) with per-solve scratch-buffer reuse. **The flop
  subgame now completes** (was OOM/jetsam-killed at ~5 min);
  bit-identical to the reference (F4_synth canary `max_diff=0.0`,
  4 Rust unit tests, two independent validators MATH-PRESERVED).
  **Known limitation:** the board-tree memory collapse was
  scaffolded but deferred (`RunoutCache::runout_values` allocated
  but never read; audit S-4). Full-range flop RSS is still ~6.7 GB
  at top_k=4 and ~7.7 GB+ at top_k=169 (does not finish); the
  "<120 s AND ≤ 1 GB" gate is **NOT met**. Full-range memory
  optimization is deferred to v1.11
  (`docs/v1_11_postflop_deeper_optimization_research.md`). See
  `docs/v1_10_perf_benchmark_2026-05-28.md`.
- **Opt-in rayon parallel chance branches** (PR-4, merge `f5ec665`,
  PR #189) — opt-in via `CFR_RAYON_CHANCE=1`; canonical
  single-threaded path is bit-identical at Δ=0.000e+00 across all 25
  existing diff tests + 9 new rayon-path fixtures. PR #189's
  microbench reported ~4.79× on flop top_k=169 (14-core M-series) —
  TARGET-grade pending the formal 12-cell bench run; not yet the
  production headline.
- **Perf benchmark harness + profiler + canonical diff-test scaffold**
  (PRs #186, #187, #188) — 12-cell wall + RSS matrix
  (top_k ∈ {4, 15, 50, 169} × {flop, turn, river}) on the canonical
  J7o A♦8♥9♦ 40 BB fixture. Each v1.10 implementer PR re-runs the
  harness; mismatches HARD-FAIL.

**Engine fixes folded in from the v1.9.0 stream:**

- **Preflop `State::initial` honors `config.initial_contributions`**
  (PR #165) — long-standing preflop engine bug where non-default
  initial contributions silently regressed to `(0, 0)`. Default
  `(0.5, 1.0)` path is bit-unchanged.
- **Vector-form best-response walk** (PR #170) — per-combo 202.43 s →
  vector **32.30 s** (6.27×) on the W2.3 fixture. Closes W2.3 Sarah
  at strict-PASS (PR #184 status snapshot).
- **CLI BB-normalization** (PR #152) — `--pot N --stack M` are the
  canonical flags (BB implicit); `--pot-bb` / `--stack-bb` remain
  functional with a one-shot deprecation warning. Resolves the
  v1.8.x friction where some surfaces accepted chips and others BB.
  See USAGE.md §5.10.

**B10 per-combo frequency feature train (task #60)** — see
"Preflop blueprint mode" above for the train summary (PRs #149,
#154, #158, #160).

Carried forward from v1.8.x (still applies, listed here for
discoverability): `--walk-tree` / `--node` / `--format` (PR #123),
`poker-solver subgame --street flop|turn|river` (PR #127),
`poker-solver --version` (PR #116), DCFR α-guard (PR #113),
TerminalCache 213× river RvR speedup (PR #114), Marcus EV display
(PR #125), `SolveResult.reach_probability` + `off_path_keys`
(PR #129). See USAGE.md §5, §7a for usage.

## Install (from source)

A Rust toolchain is required because the project ships a PyO3 extension
module via `maturin`.

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build + install the Python package (compiles the Rust extension via maturin):
pip install -e .

# Optional dev tools (pytest, ruff, mypy, maturin):
pip install -e ".[dev]"

# Optional UI extra (NiceGUI):
pip install -e ".[ui]"
```

If you prefer building the Rust crate standalone (e.g. for benchmarks
that don't need the Python wrapper):

```bash
cargo build --release --manifest-path crates/cfr_core/Cargo.toml
```

After install, the `poker-solver` CLI is on your PATH, and the
`poker_solver` package is importable from Python.

## Quick start

```bash
# Equity — exact enumeration (auto, ~60 ms on a flop):
poker-solver equity AhKh QdQc --board 2h7h9d

# Equity — Monte Carlo (range vs hand, 250k iter default):
poker-solver equity "AA,KK,AKs" QdQc

# Custom precision:
poker-solver equity AhKh QdQc -n 1000000 --seed 0

# Kuhn poker — closed-form Nash value -1/18:
poker-solver solve --game kuhn --iterations 50000 --backend python

# Leduc poker — both backends; Rust is faster:
poker-solver solve --game leduc --iterations 5000 --backend rust

# HUNL river subgame (deterministic AhKc vs QdQh on As 7c 2d Kh 5s):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500

# Same river subgame on the Rust tier (~24x faster):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust
```

**Ad-hoc postflop subgames (`--hunl-mode postflop`)** run the full
range-vs-range enumeration over the hole-card chance node, and that
tree dominates wall-time regardless of iteration count or backend.
Expect **multi-minute** runs on a flop (3-card board), and tens of
seconds even on a river (5-card board) with a 1-size bet menu. Example
form (not a Quick-start; budget time accordingly):

```bash
# Postflop ad-hoc subgame — expect minutes on a flop, even with --iterations 500.
# Python backend only: --backend rust requires fixed hole cards; for
# range-vs-range Nash on a postflop board use solve_range_vs_range_nash
# (see Python API + USAGE §5.6). For fast exploration use --hunl-mode
# tiny_subgame above.
poker-solver solve --game hunl --hunl-mode postflop \
    --board "As 7c 2d" --stacks 100 --bet-sizes "33,75,150" \
    --iterations 500 --backend python
```

Short-stack push/fold has both a CLI subcommand (v1.7.0+) and a library
entry point:

```bash
# CLI: single cell or full 169-class chart
poker-solver pushfold --stack 10 --position sb_jam --hand AKs
poker-solver pushfold --stack 8 --position bb_call_vs_jam --full-range --json
```

```python
from poker_solver import get_pushfold_strategy, get_full_range
print(get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs"))

# v1.8.2+: pass return_ev=True to get jam EV alongside the frequency.
# Returned dict is {"strategy": prob, "ev_bb": ev_in_big_blinds}.
print(get_pushfold_strategy(stack_bb=10, position="sb_jam",
                            hand="AKs", return_ev=True))

chart = get_full_range(stack_bb=8, position="bb_call_vs_jam")
```

A full HUNL config under 15 BB effective auto-routes to the chart
through `solve()` — `result.backend == "pushfold_chart"`.

## Python API

The engine is usable as a library — `equity`, `solve`,
`solve_hunl_postflop`, `solve_hunl_preflop`, `solve_range_vs_range`,
`get_pushfold_strategy`, `HUNLConfig`, `HUNLPoker`, `Range`, etc. are
all importable from the top-level `poker_solver`. A few patterns beyond
what the CLI exposes:

```python
from poker_solver import (
    Card, HUNLConfig, Street, parse_range,
    solve_hunl_postflop, solve_range_vs_range,
)

# Node locking — pin a strategy at one or more infosets. Requires a
# postflop config (preflop full-tree is still NotImplementedError above
# 15 BB; see Known issues). Replace "<infoset_key>" with a real key
# discovered via `result.average_strategy.keys()`; unmatched keys are
# silently ignored. See USAGE.md §5.3 and tests/test_node_locking.py for
# the canonical key format.
#
# `initial_hole_cards=()` (full-range chance enum) is NOT practical for
# interactive use — the post-solve exploitability walk runs for minutes.
# Pin hero + villain combos for a fast worked example (sub-second on
# Rust). For range-vs-range node-locking, build per-hand fixed-card
# configs and aggregate (see §5.2 in USAGE.md).
board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))
cfg = HUNLConfig(
    starting_stack=10_000, starting_street=Street.RIVER,
    initial_board=board, initial_pot=1_000,
    initial_contributions=(500, 500),
    initial_hole_cards=(
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Qd"), Card.from_str("Qh")),
    ),
)
locked = {"<infoset_key>": [1.0, 0.0, 0.0, 0.0]}  # 100% fold at that node
r = solve_hunl_postflop(cfg, iterations=500, locked_strategies=locked)

# Range-vs-range (aggregator — fast per-combo blueprint pooling).
# `parse_range` turns Pio-style strings into a Range; passing a list of
# combo strings (e.g. ["AA","KK","AKs"]) also works.
hero, villain = parse_range("AA, KK, AKs"), parse_range("QQ-99, AKo")
agg = solve_range_vs_range(template_config, hero, villain, iterations=200)

# Range-vs-range (vector form — joint range Nash via the Rust tier):
from poker_solver._rust import solve_range_vs_range_rust
vec = solve_range_vs_range_rust(template_json, iterations=200,
                                alpha=1.5, beta=0.0, gamma=2.0,
                                p0_holes=p0_combos, p1_holes=p1_combos)
```

The two range-vs-range entry points solve **different objects**:

- **`solve_range_vs_range`** (aggregator;
  `poker_solver/range_aggregator.py`) — runs a 1v1 full-info Nash per
  (hero combo, villain combo) pair and pools by combo weight. Fast
  (~5 s for a 14×14 query) but produces basket-selection strategies
  that diverge from true range Nash on polarized spots.
- **`solve_range_vs_range_rust`** (vector form, v1.5.0;
  `crates/cfr_core/src/dcfr_vector.rs` via PyO3) — joint range Nash via
  Brown's vector-form CFR. Structurally a port of `noambrown/poker_solver`'s
  `cpp/src/trainer.cpp:138-240` per three independent code reviews.
  The 33-pp Brown apples-to-apples divergence on the A83 deep-cap
  `b1000r3000` spot is now empirically explained as Nash multiplicity
  on the indifference manifold (both solvers within Brown's 0.06-chip
  exploitability margin); shallow-cap behavior matches strictly. See
  Known issues and
  [`docs/a83_nash_multiplicity_confirmed_2026-05-26.md`](docs/a83_nash_multiplicity_confirmed_2026-05-26.md).

See [`docs/aggregator_vs_true_nash_explainer.md`](docs/aggregator_vs_true_nash_explainer.md)
for when to use which, and [`USAGE.md`](USAGE.md) for custom subgames,
library mode, and asymmetric-contribution examples.

**Filtering off-path infosets (v1.8.2+).** Deep trees accumulate
strategies at infosets that are never actually reached under the
equilibrium — phantom mass that can confuse downstream consumers.
`SolveResult` now exposes the reach annotation directly:

```python
result = solve_hunl_postflop(cfg, iterations=500)

# Drop unreachable nodes before consuming the strategy:
on_path = {
    k: v for k, v in result.average_strategy.items()
    if k not in result.off_path_keys
}

# Or weight by reach probability if you want a continuous filter:
weighted = {
    k: (v, result.reach_probability[k])
    for k, v in result.average_strategy.items()
}
```

**DCFR α-guard (v1.8.2+).** `solve(..., alpha=0)` now raises `ValueError`
(was a silent non-Nash bug). Values in `(0, 0.5)` emit a deprecation
warning; the Brown & Sandholm 2019 paper default `alpha=1.5` remains
recommended.

## UI

```bash
pip install -e ".[ui]"
poker-solver ui
```

Launches NiceGUI on `http://127.0.0.1:8080` with a 13x13 range matrix,
board picker, solver controls, and a decision-tree browser.

**v1.10.0:** the chart widget and chained postflop tab now consume the
**real** preflop blueprint (PR #178 — Phase 6 UI wiring). Cells show
`blueprint` / `interpolated` / `live` source badges in the tooltip;
the chained tab surfaces the active postflop backend at the top of
the result panel; a live-solve confirmation modal gates the
fall-through to a fresh solve on out-of-envelope spots. Standalone
postflop subgame solves from the **Solve** button on the ad-hoc tab
still use the PR 10a mock fixtures (real bindings land in PR 10b);
the yellow banner is retained on that surface only. **For real
preflop strategies, use the chart widget. For real postflop, use the
chained tab or the CLI / Python API.**

## Architecture (brief)

Two-tier with differential testing. The Python package `poker_solver/`
is the readable spec / ground truth; the Rust crate `crates/cfr_core/`
(exposed as `poker_solver._rust` via PyO3 / maturin) is the workhorse.
Every algorithm lands in Python first, ports to Rust, and is gated by
diff tests (`tests/test_dcfr_diff.py`, `tests/test_leduc_diff.py`,
`tests/test_preflop_diff.py`, `tests/test_range_vs_range_rust_diff.py`)
before the Rust tier is trusted. The scalar algorithm is tabular DCFR
(Brown & Sandholm 2019) with paper defaults (`alpha=1.5`, `beta=0`,
`gamma=2.0`). See [`DEVELOPER.md`](DEVELOPER.md) for the full breakdown
including the EMD card abstraction and HUNL solver layout.

## Development

```bash
# Full test suite (Python + Rust):
pytest
cargo test --all --manifest-path crates/cfr_core/Cargo.toml

# Lint + format:
ruff check
ruff format --check
cargo clippy --all-targets --manifest-path crates/cfr_core/Cargo.toml -- -D warnings

# Pre-PR check battery (tests, lint, types, diff-tests, perf gate, etc.):
sh scripts/check_pr.sh
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the PR-flow contract.

## Known issues

- **`.dmg` is ad-hoc signed (not notarized) + arm64-only.** v1.10.0
  `.dmg` is launchable from Finder (the v1.6.0 fork-bomb was resolved
  in v1.8.0 — PR #42, `728206e` — and the v1.10.0 bundle includes the
  27 preflop blueprint shards). First launch requires the macOS
  Gatekeeper override (right-click → Open → confirm). Universal2
  binaries are not yet published; Intel Mac users should source-build
  per the "Install (from source)" section. See
  [`docs/dmg_install_guide.md`](docs/dmg_install_guide.md).
- **Deep-cap RvR acceptance vs Brown: Nash-multiplicity on indifference
  manifold (resolved); v1.6.1 ship HOLD lifted.** Investigation closed.
  The v1.5 Brown acceptance test PASSES under the reframed 4-layer gate
  (structural + shallow-strict + deep max-L1 ≤ 1.9 + top-action ≥ 60%);
  both A83 and K72 PASS, and the v1.8 SIMD landing did not perturb the
  output (see
  [`docs/v1_5_brown_current_state_2026-05-26.md`](docs/v1_5_brown_current_state_2026-05-26.md)).
  The earlier 33-pp K72/A83 deep-cap divergence traced to two compound
  causes, both resolved: (1) test-side wrapper bugs (suit-encoding,
  P0/P1 player convention, hand-string sort order) — fixed in the
  v1.7.1 bundle (PR 52/55/56); (2) Nash-multiplicity at depth ≥ 11
  facing-all-in `(c,f)` AA leaves — both solvers are within the
  indifference manifold (Brown exploitability 0.06 chips at 2000 iters
  = 0.006% of pot). The residual 33-pp deep-cap divergence is acceptable
  per the Nash-multiplicity acceptance framework (see
  [`docs/a83_validation_2026-05-26.md`](docs/a83_validation_2026-05-26.md)).
  v1.6.1 ship HOLD lifted per
  [`docs/v1_6_1_ship_hold_review_2026-05-26.md`](docs/v1_6_1_ship_hold_review_2026-05-26.md);
  the engine bundle (PR 50, 51, 52, 54, 55, 56, 53b, 53c) has shipped
  piecewise on `origin/main`. Investigation details:
  [`docs/a83_deep_cap_root_cause_investigation.md`](docs/a83_deep_cap_root_cause_investigation.md).
- **`Range` fractional frequencies** (e.g. `AKo:0.25` syntax) not yet
  supported — `Range` has no `weight` field. Set-membership operations
  (`Range.diff`) work today; mixed-frequency operations require a
  refactor scoped for v1.8+ (was previously tracked as W2.2).
- **CLI subcommand caveats (v1.7.0).** `poker-solver pushfold`,
  `poker-solver river`, and `poker-solver parity` all ship in v1.7.0
  (see USAGE §7a for flags and examples). Caveats: `parity` requires
  Brown's binary built via `scripts/build_noambrown.sh` and exits 2
  with a hint if it is missing; `river` and `parity` are slow at high
  `--iters` (the documented `parity --iters 2000` runs several
  minutes — start with smaller values to smoke-test).
- **CLI batch-solve on chance-enum-at-root is slow.** The chance-node
  enumeration at the betting-tree root dominates for full flop/turn
  range-on-both-sides queries (W2.4). Mitigations: use the aggregator
  for interactive queries; the vector-form path for production-grade
  joint range Nash.
- **`poker-solver batch-solve` CSV quoting.** Multi-value `bet_sizes`
  cells must be CSV-quoted (`"0.5,1.0"`), and the CSV schema has no
  hole-cards columns — use `solve_hunl_postflop` directly for
  fixed-hole-card spots.
- **`pyenv` arch hazard on Apple Silicon (dev-env quirk).** A pyenv
  Python built x86_64-only (notably `3.13-dev`) silently SKIPs Rust
  diff-tests instead of running them — the arm64 `.so` won't load.
  Verify with `python -c "import platform; print(platform.machine())"`
  (must be `arm64`) and `python -c "import poker_solver._rust"` (must
  succeed) before running the test suite. Full guidance:
  [`CONTRIBUTING.md`](CONTRIBUTING.md) §"Known development environment
  hazard".
- **`poker-solver` shim may resolve to a broken Python env.** After
  `pip install -e .` in temporary build dirs, the PATH shim
  (`~/.pyenv/shims/poker-solver` on pyenv systems) can resolve to a
  Python where `poker_solver` is no longer installed. Workarounds: use
  `./.venv/bin/poker-solver ...` from the project root, or run
  `python -m poker_solver.cli ...` with `.venv` activated. Full
  diagnostic:
  [`docs/poker_solver_shim_fix_2026-05-26.md`](docs/poker_solver_shim_fix_2026-05-26.md).

## References

The CFR / DCFR / HUNL literature and competitor codebases live under
`references/` (gitignored; not redistributed). To clone the public
references for your own study: `sh scripts/setup_references.sh`.

Algorithmic foundations: DCFR (Brown & Sandholm 2019); CFR+ (Tammelin
2014); vanilla CFR (Zinkevich, Johanson, Bowling, Piccione 2007);
Libratus (Brown & Sandholm 2017); Pluribus (Brown & Sandholm 2019).
Correctness oracles: DeepMind's `open_spiel` (Apache 2.0) for Kuhn /
Leduc; `noambrown/poker_solver` (MIT) for river spots and the
vector-form CFR algorithm port.

## Notation

- Ranks: `2 3 4 5 6 7 8 9 T J Q K A`
- Suits: `s h d c` (spades, hearts, diamonds, clubs)
- Card: rank+suit, e.g. `Ah`, `Ts`, `2c`
- Range: `AA`, `AKs`, `AKo`, `AK` (both), `KK-TT`, `76s+`, comma-combined

## License

MIT. AGPL solvers in `references/` are read-only inspiration; no
AGPL-licensed code is copied in. See [`LICENSE`](LICENSE).
