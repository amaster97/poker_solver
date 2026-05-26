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

- **Latest tagged release:** v1.7.0 (aggregator→vector wiring + CLI
  subcommands — PR 43 + PR 44). The v1.0 → v1.7.0 trajectory is
  documented in [`CHANGELOG.md`](CHANGELOG.md). **Next release:
  v1.8.0** (cross-platform SIMD + .dmg fork-bomb fix + v1.6.1 engine
  bundle + v1.7.2 CI hardening, all merged on `main`; tag pending).
  v1.6.1 engine bundle has shipped piecewise on `origin/main` and is
  folded into v1.8.0 (see
  [`docs/v1_7_1_tag_decision_2026-05-26.md`](docs/v1_7_1_tag_decision_2026-05-26.md)
  for the tag-strategy decision).
- **License:** MIT.
- **Platforms:** macOS (Apple Silicon primary), Linux. Intel Mac is
  source-build only.
- **Python:** 3.9+. Rust toolchain required (stable channel).
- **Working install path:** source build (`pip install -e .`).
- **`.dmg` installer:** **v1.6.0 `.dmg` has a critical fork-bomb bug on
  Finder launch — DO NOT use until the v1.8.0 packaging fix lands.**
  See Known issues. Use the CLI source install (below) instead.

### macOS install (.dmg — NOT RECOMMENDED until v1.8.0)

> ⚠️ **CRITICAL:** the v1.6.0 `.dmg` currently spawns processes
> uncontrollably on Finder launch and can freeze your Mac. Root cause
> identified (missing `multiprocessing.freeze_support()` in the
> PyInstaller entry point); fix merged on `main` (PR #42, commit
> `728206e`) and ships in v1.8.0. Until v1.8.0 is tagged + released,
> use the source install below. Full RCA:
> [`docs/dmg_spawn_loop_rca_2026-05-26.md`](docs/dmg_spawn_loop_rca_2026-05-26.md).

Apple silicon (arm64) only. See
[`docs/dmg_install_guide.md`](docs/dmg_install_guide.md) (relevant once
the .dmg is safe to launch again).

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

# Ad-hoc postflop subgame from CLI flags (100 BB flop, custom bet menu):
poker-solver solve --game hunl --hunl-mode postflop \
    --board "As 7c 2d" --stacks 100 --bet-sizes "33,75,150" \
    --iterations 500 --backend rust
```

Short-stack push/fold is invoked through the library (no dedicated CLI
subcommand — see Known issues):

```python
from poker_solver import get_pushfold_strategy, get_full_range
print(get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs"))
chart = get_full_range(stack_bb=8, position="bb_call_vs_jam")
```

A full HUNL config under 15 BB effective auto-routes to the chart
through `solve()` — `result.backend == "pushfold"`.

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
# discovered via `result.strategy.keys()`; unmatched keys are silently
# ignored. See USAGE.md §5.3 and tests/test_node_locking.py for the
# canonical key format.
board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))
cfg = HUNLConfig(
    starting_stack=10_000, starting_street=Street.RIVER,
    initial_board=board, initial_pot=1_000,
    initial_contributions=(500, 500),
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
  `cpp/src/trainer.cpp:138-240` per three independent code reviews,
  but empirical acceptance against Brown's binary still diverges on
  deep-cap facing-raise spots (33-pp on bottom-pair-Ace cells in the
  A83 spot at `b1000r3000`); shallow-cap behavior matches — see Known
  issues.

See [`docs/aggregator_vs_true_nash_explainer.md`](docs/aggregator_vs_true_nash_explainer.md)
for when to use which, and [`USAGE.md`](USAGE.md) for custom subgames,
library mode, and asymmetric-contribution examples.

## UI

```bash
pip install -e ".[ui]"
poker-solver ui
```

Launches NiceGUI on `http://127.0.0.1:8080` with a 13x13 range matrix,
board picker, solver controls, and a decision-tree browser. As of
v1.2.0 the UI drives the real solver. The packaged `.dmg` GUI does not
currently work — see Known issues. **Use the CLI / Python API for now.**

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

- **`.dmg` installer crashes Mac on Finder launch (CRITICAL).** The
  v1.6.0 `.dmg` ships on the GitHub Release, but launching the `.app`
  from Finder causes uncontrolled process spawning (PyInstaller +
  macOS-multiprocessing fork-bomb) and can freeze the machine. Root
  cause: `scripts/pyinstaller_entry.py` did not call
  `multiprocessing.freeze_support()` at module level, so each NiceGUI
  worker spawned by uvicorn re-execs the entire frozen app, recursively.
  The fix is merged on `main` (PR #42, commit `728206e`); re-packaged
  `.dmg` ships in v1.8.0. **Use the source install above** until then.
  Full RCA:
  [`docs/dmg_spawn_loop_rca_2026-05-26.md`](docs/dmg_spawn_loop_rca_2026-05-26.md).
  Earlier v1.4.0 `.dmg` had a different defect (nicegui missing from
  bundle), fixed in PR 44; the current v1.6.0 fork-bomb issue is
  separate.
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
