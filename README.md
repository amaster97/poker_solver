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

- **Latest tagged release:** v1.6.0 (GUI Gate 2 surfaces — PR 24a + PR 24b). The
  v1.0 → v1.6.0 trajectory is documented in [`CHANGELOG.md`](CHANGELOG.md).
  v1.7.0 (aggregator→vector wiring + CLI subcommands) is in flight;
  v1.6.1 (engine bundle, deep-cap investigation) is held pending the
  A83 acceptance test resolution.
- **License:** MIT.
- **Platforms:** macOS (Apple Silicon primary), Linux. Intel Mac is
  source-build only.
- **Python:** 3.9+. Rust toolchain required (stable channel).
- **Working install path:** source build (`pip install -e .`).
- **`.dmg` installer:** experimental — see "macOS install (.dmg,
  experimental)" below and Known issues. The CLI from source is the
  recommended path today.

### macOS install (.dmg, experimental)

Apple silicon (arm64) only. See [`docs/dmg_install_guide.md`](docs/dmg_install_guide.md)
for download, SHA256 verification, and first-launch Gatekeeper bypass
instructions (adhoc-signed; not notarized).

## Install (from source)

A Rust toolchain is required because the project ships a PyO3 extension
module via `maturin`.

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build + install the Python package (compiles the Rust extension via maturin):
pip install -e .

# Optional dev tools (pytest, ruff, black, maturin):
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
    HUNLConfig, HUNLPoker, Range, solve, solve_range_vs_range,
)

# Node locking — pin a strategy at one or more infosets:
locked = {"<infoset_key>": [0.6, 0.4]}
r = solve(HUNLPoker(HUNLConfig(starting_stack=10000)),
          iterations=2000, locked_strategies=locked)

# Range-vs-range (aggregator — fast per-combo blueprint pooling):
hero, villain = Range("AA, KK, AKs"), Range("QQ-99, AKo")
agg = solve_range_vs_range(template_config, hero, villain, iterations=200)

# Range-vs-range (vector form — joint range Nash via the Rust tier):
from poker_solver._rust import solve_range_vs_range_rust
vec = solve_range_vs_range_rust(template_json, iters=200,
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

- **`.dmg` installer does not currently work.** The v1.4.0 universal2
  `.dmg` ships on the GitHub Release, but on a clean Mac the launched
  app exits at `ui/app.py:362` with `ModuleNotFoundError: No module
  named 'nicegui'` — the GUI dependency is missing from the PyInstaller
  bundle. Additional defects: adhoc-signed (not notarized; Gatekeeper
  will block by default), `arm64`-only despite the `universal2` label
  (Intel Macs can't run it at all), and the `Info.plist` version stamp
  reads `0.6.0` on a v1.4.0 tag. A packaging-fix PR is queued. **Use
  the source install above** until that lands. Full smoke-verification
  report: [`docs/dmg_v1_4_0_smoke_verification.md`](docs/dmg_v1_4_0_smoke_verification.md).
- **v1.5.0 Brown acceptance test currently FAILS — v1.6.1 ship HELD
  pending investigation.** Three code reviews verified the Rust
  vector-form CFR is structurally faithful to Brown's
  `cpp/src/trainer.cpp:138-240` (iteration loop, DCFR weights, regret
  matching all match line-by-line). PR 40 confirmed and fixed three
  test-side encoding artifacts (action-axis column ordering,
  range-to-player-slot inversion, hand-string suit-order). **But a
  v1.6.1-bundle dry-run (PR 33+34+35-A+B+40 composed, 2000-DCFR-iter)
  empirically re-confirms a residual algorithmic divergence at
  deep-cap facing-raise** (not yet localized): on A83 at `b1000r3000`,
  bottom-pair-Ace cells (3sAs, 3cAc) show 33-pp call-frequency
  divergence (Brown ~0.36, Rust ~0.69), max |diff| 0.33. K72 max
  |diff| ~0.07. Affected: deep-cap facing-raise on bottom-pair-Ace at
  large raise sizes. Unaffected: river single-shot, shallow-cap
  postflop, push/fold preflop. The structural reviews verified CODE
  matches Brown's algorithm; they did not verify the algorithm
  produces Brown's empirical OUTPUT at this scenario — a
  label-vs-semantics gap. Investigation in flight: best-response
  cross-check + iteration sweep + facing-raise path re-read. Full
  report: [`docs/v1_6_1_dryrun_verification.md`](docs/v1_6_1_dryrun_verification.md).
- **`Range` fractional frequencies** (e.g. `AKo:0.25` syntax) not yet
  supported — `Range` has no `weight` field. Set-membership operations
  (`Range.diff`) work today; mixed-frequency operations require a
  refactor scoped for v1.8+ (was previously tracked as W2.2).
- **CLI ergonomic gaps.** Push/fold has no dedicated `poker-solver
  pushfold` subcommand — use the library API in Quick start. River
  hero-vs-range and parity-check CLI subcommands are also not wired;
  drop to the Python API in the meantime.
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
