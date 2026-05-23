# poker_solver

A Texas Hold'em equity calculator and GTO solver, written in Python with
a Rust performance tier. Ships a hybrid exact / Monte Carlo equity
engine, a hand evaluator, a range parser, closed-form-verified Kuhn and
Leduc solvers, a Heads-Up No-Limit Hold'em (HUNL) game tree with a
14-action abstraction, DCFR-generated push/fold charts for 2-15 BB
short-stack play, and a full HUNL postflop solver (Python + Rust).
Goalpost: PioSolver-class HU local solving on a MacBook.

**v1.0.0 released 2026-05-22 — GA milestone.** HUNL postflop solver
(Python + Rust tiers, ~24x speedup, bit-exact parity), mock-first
NiceGUI scaffold, library mode, EMD card abstraction, external Nash
validation vs `noambrown/poker_solver`, macOS `.dmg` packaging.

## Status

- **Current version:** 1.0.0 (GA) — see [`CHANGELOG.md`](CHANGELOG.md).
- **License:** MIT.
- **Platform:** macOS / Linux; M-series MacBook is the primary target.
- **Python:** 3.9+ (developed on 3.13). Rust toolchain required for the
  perf-tier extension.

## Features (v1.0)

- **Texas Hold'em equity calculator** — hybrid exact-enumeration +
  Monte Carlo. Concrete-hand spots with a small remaining-board space
  auto-enumerate (e.g. 990 flop runouts in ~60 ms, no sampling noise);
  ranges and large state spaces fall back to MC at 250k iterations
  by default (~0.1% SE/hand). See `poker_solver/equity.py` and
  `tests/test_equity.py`.
- **Hand evaluator** — 5- to 7-card hands ranked into the nine standard
  categories with kickers. See `poker_solver/evaluator.py` and
  `tests/test_evaluator.py`.
- **Range parser** — standard notation (`AA`, `AKs`, `AKo`, `KK-TT`,
  `76s+`, comma-combined). See `poker_solver/range.py` and
  `tests/test_range.py`.
- **Kuhn poker solver** — DCFR (Brown & Sandholm 2019) converges to the
  closed-form Nash value of -1/18. Python and Rust backends agree within
  1e-4 per action probability. See `poker_solver/dcfr.py`,
  `crates/cfr_core/src/kuhn.rs`, and `tests/test_dcfr_diff.py`.
- **Leduc poker solver** — 288 infosets, multi-round with mid-game
  chance node. Both Python and Rust backends ship and are diff-tested.
  See `poker_solver/games.py::LeducPoker`, `crates/cfr_core/src/leduc.rs`,
  and `tests/test_leduc_diff.py`.
- **HUNL game state + tree** — full state machine across preflop, flop,
  turn, river, showdown. 14-action abstraction (fold / check / call /
  five bet sizes / five raise sizes / all-in) with raise caps
  (preflop 4, postflop 3) and ante support. Integer-cents chip
  arithmetic throughout. See `poker_solver/hunl.py`,
  `poker_solver/action_abstraction.py`, and the 41 tests in
  `tests/test_hunl_core.py`, `tests/test_hunl_tree.py`, and
  `tests/test_action_abstraction.py`. A tiny river-only fixture
  (`default_tiny_subgame()`) is solvable end-to-end today.
- **Push/fold charts (2-15 BB)** — real DCFR-generated Nash equilibria
  for every integer stack depth in `[2, 15]` BB, both `sb_jam` and
  `bb_call_vs_jam` positions, 169 hand classes per cell.
  Exploitability after convergence is essentially 0 BB/100 (spec target
  was < 0.05). `solve()` auto-dispatches to chart lookup when the
  effective stack lands in this range. See `poker_solver/pushfold.py`,
  `poker_solver/charts/pushfold_v1.json`, and `tests/test_pushfold.py`.
- **Card abstraction (EMD bucketing)** — imperfect-recall EMD-based
  clustering at 256/128/64 buckets (flop/turn/river) with
  suit-isomorphism canonicalization. Slumbot-MIT inspired kmeans++ +
  1-D EMD via cumulative-sum closed form. Persisted as a `.npz`
  artifact and looked up via `AbstractionRef`. See
  `poker_solver/abstraction/`, the `poker-solver precompute-abstraction`
  CLI, and `tests/test_abstraction_*.py`.
- **HUNL postflop solver (Python + Rust)** — Python reference plus a
  Rust port at ~24x speedup (3.88 s Rust vs 92.9 s Python at 100k iters,
  Apple M4 Pro), bit-exact diff-tested on shared seeds. Selectable via
  `--backend rust` on the `solve` CLI.
- **External Nash validation** — river-spot diff test against
  third-party `noambrown/poker_solver` (MIT) confirms strategy agreement
  on shared seeds. See `tests/test_noambrown_diff.py`.
- **NiceGUI app (mock-first scaffold)** — browser UI with 13x13 range
  matrix, board picker, solver controls, and decision-tree browser.
  Ships against a fixture-backed mock solver behind a banner; a future
  PR swaps in the real solver via a single DI point.
- **Library mode** — clean Python API surface (`equity`, `solve`,
  `get_pushfold_strategy`, `HUNLPoker`, `HUNLConfig`, ...) so the engine
  is usable as a dependency, not just a CLI.
- **macOS packaging** — codesigned + notarized `.dmg` for M-series
  MacBooks; double-click installs the CLI and launches the UI. See the
  v1.0.0 release artifacts.

## What's coming next

**v1.x (post-GA):** spec-conformance audit (PR 10a.5), NEON SIMD +
cache-blocking + public chance sampling (PR 8), HUNL preflop full solve
(PR 9, replacing the push/fold lookup above 15 BB), mock -> real solver
swap in the UI (PR 10b, one-line DI flip once PR 9 lands).

**Stretch (post-v1):** 3-handed postflop (PR 12), explicitly approximate
since CFR has no convergence guarantee for >=3 players.

`poker-solver solve --game hunl --hunl-mode full` above 15 BB still
raises `NotImplementedError` today, pointing at PR 9.

## Installation

A Rust toolchain is required because the project ships a PyO3 extension
module via `maturin`.

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build and install (compiles both Python and Rust):
pip install -e .

# With dev tools (pytest, ruff, black, maturin):
pip install -e ".[dev]"
```

## Quick start

```bash
# Equity — exact enumeration (auto, ~60 ms for a flop):
poker-solver equity AhKh QdQc --board 2h7h9d

# Equity — Monte Carlo (range vs hand, 250k iter default):
poker-solver equity "AA,KK,AKs" QdQc

# Custom precision:
poker-solver equity AhKh QdQc -n 1000000 --seed 0

# Kuhn poker (closed-form Nash):
poker-solver solve --game kuhn --iterations 50000 --backend python

# Leduc poker (both backends; rust is faster):
poker-solver solve --game leduc --iterations 5000 --backend rust

# HUNL tiny river subgame (deterministic AhKc vs QdQh, board As7c2dKh5s):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500

# Same river subgame on the Rust tier (v1.0.0):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust

# Perf demo (M4 Pro, 10k iters): python ~9 s vs rust ~0.4 s (~23x).
# Short-stack push/fold lookup is automatic inside solve():
#   solve(HUNLPoker(HUNLConfig(starting_stack=1000)))  -> backend="pushfold"

# Card abstraction — build once, reuse from --abstraction:
poker-solver precompute-abstraction --bucket-counts 256,128,64 \
    --mc-iterations 200000 --output abstraction_v1.npz
```

Python API:

```python
from poker_solver import (
    HUNLConfig, HUNLPoker, default_tiny_subgame,
    equity, get_full_range, get_pushfold_strategy,
    KuhnPoker, parse_board, parse_hand, solve,
)

# Equity (exact when feasible, MC otherwise):
hands = [parse_hand("AhKh"), parse_hand("QdQc")]
board = parse_board("2h7h9d")
for i, r in enumerate(equity(hands, board=board)):
    print(f"hand {i}: equity = {r.equity:.2%}")

# Kuhn -> closed-form Nash value -1/18:
r = solve(KuhnPoker(), iterations=50_000, backend="rust")
print(f"Game value: {r.game_value:+.6f}")

# Push/fold lookup:
freq = get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs")
chart = get_full_range(stack_bb=8, position="bb_call_vs_jam")

# Automatic short-stack dispatch (10 BB effective -> chart lookup):
short = HUNLPoker(HUNLConfig(starting_stack=1000))
r = solve(short, iterations=0)
assert r.backend == "pushfold"
```

## UI (mock)

```bash
pip install -e .[ui]
poker-solver ui
```

Launches NiceGUI on `http://127.0.0.1:8080` with a 13x13 range matrix
(Pio palette), board picker, solver controls with live exploitability,
and a decision-tree browser. v1 ships behind a "Mock mode" banner
(fixture-backed) which will downgrade to a subtle `(mock)` chip when a
future PR swaps in the real solver.

## Architecture (brief)

Two-tier with differential testing: the Python package `poker_solver/` is
the readable spec / ground truth; the Rust crate `crates/cfr_core/`
(exposed as `poker_solver._rust` via PyO3 / maturin) is the workhorse.
Every algorithm lands in Python first, ports to Rust, and is gated by
diff tests in `tests/test_dcfr_diff.py` / `tests/test_leduc_diff.py`
before the Rust side is trusted. The algorithm is tabular DCFR
(Brown & Sandholm 2019) with paper-default hyperparameters
(alpha=1.5, beta=0, gamma=2.0). See [`DEVELOPER.md`](DEVELOPER.md) for
the full architectural breakdown including the bucketed card
abstraction and HUNL solver layout.

## Development

```bash
# Full test suite (Python + Rust):
pytest
cargo test --all --manifest-path crates/cfr_core/Cargo.toml

# Lint + format checks:
ruff check
ruff format --check
cargo clippy --all-targets --manifest-path crates/cfr_core/Cargo.toml -- -D warnings

# Pre-PR check battery (tests, lint, types, diff-tests, license audit,
# perf gate, references integrity; writes pr_report.md):
sh scripts/check_pr.sh
```

From PR 3 onward every change ships on its own feature branch
(`pr-N-<title>`), passes `scripts/check_pr.sh`, and receives a fresh-agent
audit reviewing the diff with no implementation context. Both
`pr_report.md` and `audit_report.md` must be clean before merge.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the dev-environment, test,
and PR-flow contract. The TL;DR: this is a personal solo build right
now; the surface area is small and the design choices are deliberately
load-bearing. Before opening a PR, please review the locked design
decisions (algorithm, abstraction, stack range, license posture) and
skim the per-PR audit pattern in `CONTRIBUTING.md`. Reference-first
rule: every technical claim in this repo cites a paper, a competitor
repo, or a test — please match the norm.

## References

The CFR / DCFR / HUNL literature and competitor codebases are kept
local under `references/` (the entire `references/` tree is gitignored)
— papers are not redistributed, AGPL repos are read-only inspiration
only, and MIT / Apache 2.0 repos are eligible for porting with
attribution. To clone the public references for your own study:

```bash
sh scripts/setup_references.sh
```

Algorithmic foundations: DCFR (Brown & Sandholm 2019, *Solving
Imperfect-Information Games via Discounted Regret Minimization*);
CFR+ (Tammelin 2014); vanilla CFR (Zinkevich, Johanson, Bowling,
Piccione 2007); Libratus (Brown & Sandholm 2017, *Science*); Pluribus
(Brown & Sandholm 2019, *Science*). Correctness oracles: DeepMind's
`open_spiel` (Apache 2.0) for Kuhn / Leduc; `noambrown/poker_solver`
(MIT) for river spots (PR 7).

## Notation

- Ranks: `2 3 4 5 6 7 8 9 T J Q K A`
- Suits: `s h d c` (spades, hearts, diamonds, clubs)
- A card is two characters, rank then suit (e.g. `Ah`, `Ts`, `2c`)
- Range notation:
  - `AA` — pocket aces
  - `AKs` — ace-king suited
  - `AKo` — ace-king offsuit
  - `AK` — both suited and offsuit
  - `KK-TT` — pocket pairs from KK down to TT
  - `76s+` — suited connectors at or above 76s (76s, 87s, ..., KQs)
  - Comma-combined: `AA, KK-TT, AKs, AKo`

## License

MIT. No AGPL-licensed code is copied into this repository; AGPL solvers
in `references/` are read-only inspiration. See [`LICENSE`](LICENSE).
</content>
</invoke>