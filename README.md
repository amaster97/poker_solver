# poker_solver

A heads-up no-limit Texas Hold'em (HUNL) GTO solver, with a desktop-style
web GUI. It computes game-theory-optimal (GTO / Nash) strategies for HUNL
spots — preflop ranges, push/fold charts, and postflop range-vs-range
subgames — plus exact and Monte Carlo equity, a hand evaluator, and a
Pio-style range parser.

The project is built in two tiers: a readable **Python reference**
implementation that serves as the spec / ground truth, and a fast **Rust
core** (`crates/cfr_core`, exposed to Python as `poker_solver._rust` via
PyO3 / maturin) that does the heavy solving. Both implement the same
algorithm — tabular Discounted CFR (Brown & Sandholm 2019) with the paper's
default discounting (`alpha=1.5`, `beta=0`, `gamma=2.0`) — and the Rust tier
is gated against the Python tier by differential tests before it is trusted.

- **License:** MIT.
- **Platforms:** macOS (Apple Silicon primary) and Linux. Intel Mac is
  source-build only.
- **Python:** 3.9+. A Rust toolchain (stable channel) is required to build
  the extension module.

## The GUI

The repository ships a [NiceGUI](https://nicegui.io/) web app (under `ui/`)
that runs locally in your browser. After installing the optional `ui` extra,
launch it with:

```bash
poker-solver ui
```

This serves the app on `http://127.0.0.1:8080` (it binds only to localhost;
if 8080 is busy it falls back to the next free port up to 8090). Flags:
`--port`, `--host`, and `--dark-mode {auto,light,dark}` (default `auto`
follows your OS theme).

What the GUI offers:

- **Preflop charts / ranges** — a 13×13 hand-class matrix showing GTO action
  frequencies, backed by the precomputed preflop blueprint with a fall-through
  to a live solve for out-of-envelope spots.
- **Range editor** — build and edit ranges three ways: clicking cells on the
  13×13 matrix, typing Pio-style range strings (`AA, KK, AKs, 76s+`), and a
  per-hand frequency editor for finer control. Suited / offsuit cells are
  handled distinctly.
- **Postflop range-vs-range solving** — set a board and two ranges and solve
  the postflop subgame, including a guided hole-card walkthrough that chains a
  preflop blueprint range into a postflop street.
- **Solve library** — a local store of solved spots you can list, search,
  load, and delete.
- **Tree browser + strategy matrix** — walk the post-solve decision tree and
  inspect the strategy at each node, with a combo inspector and node-lock
  editor.
- **Card graphics** — suit-colored card rendering for boards and specific
  combos.

## The engine (v1.11)

The Rust core is the production solver. Highlights of the current engine:

- **Discounted CFR (DCFR).** Tabular DCFR with the Brown & Sandholm 2019
  defaults (`alpha=1.5`, `beta=0`, `gamma=2.0`), in both scalar and
  vector (joint-range) forms.
- **Fast postflop solving.** The vector-form postflop path layers several
  optimizations that are on by default:
  - **Chance-parallelism** — board-runout chance branches are solved across
    cores with [rayon](https://crates.io/crates/rayon).
  - **Suit isomorphism** — strategically equivalent suit permutations are
    collapsed so the solver does the work once and expands members on output.
  - **Inclusion-exclusion terminal evaluation** — showdown / fold leaf values
    are computed in O(N) per hand rather than pairwise, using card-blocker
    inclusion-exclusion.

  Each of these can be force-disabled via an environment variable
  (`CFR_RAYON_CHANCE`, `CFR_SUIT_ISO`, `CFR_TERMINAL_IE`), in which case the
  solver falls back to a bit-identical reference path — the mechanism the diff
  tests rely on.
- **Bet-size abstraction.** Per-street pot-fraction opening menus (separate
  flop / turn / river menus), all-in always offered, and raises modeled as a
  lean multiplier of the prior bet up to a per-street raise cap. There is also
  an optional flop "no-donk" constraint that removes the out-of-position
  player's first-to-act flop open.
- **Preflop blueprint.** A precomputed set of Nash-equilibrium preflop
  strategies (multiple stack depths × ante configurations × all 169
  starting-hand classes), so common preflop lookups are effectively instant
  versus a live solve. Custom ranges, off-anchor depths (via interpolation),
  and out-of-envelope spots fall through to the live solver.

**What it can and can't do (honest capability):** River and turn subgames, and
shallow / medium-depth flop spots, solve well and are practical to run
interactively. **Deep-stack (e.g. 100BB) full-range flop solves are
compute-intensive — expect minutes, not instant results** — because the flop
introduces a large two-street board-chance tree. This is not an interactive
"deep-flop in real time" solver; budget wall-clock time accordingly for the
heaviest spots.

## Install (from source)

A Rust toolchain is required because the project builds a PyO3 extension
module with `maturin` (see `pyproject.toml` `[build-system]` and
`crates/cfr_core/Cargo.toml`).

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build + install the Python package (compiles the Rust extension):
pip install -e .

# Optional: developer tooling (pytest, ruff, mypy, maturin):
pip install -e ".[dev]"

# Optional: the GUI (NiceGUI):
pip install -e ".[ui]"
```

For an explicit Rust-extension rebuild during development you can use maturin
directly:

```bash
maturin develop --release
```

To build the Rust crate standalone (e.g. for benchmarks that don't need the
Python wrapper):

```bash
cargo build --release --manifest-path crates/cfr_core/Cargo.toml
```

After install, the `poker-solver` CLI is on your PATH and the `poker_solver`
package is importable from Python.

## Quick start (CLI)

```bash
# Equity — exact enumeration (auto on a flop):
poker-solver equity AhKh QdQc --board 2h7h9d

# Equity — Monte Carlo (range vs hand):
poker-solver equity "AA,KK,AKs" QdQc

# Kuhn poker — closed-form Nash value -1/18 (sanity check):
poker-solver solve --game kuhn --iterations 50000 --backend python

# Leduc poker — both backends available; Rust is faster:
poker-solver solve --game leduc --iterations 5000 --backend rust

# HUNL river subgame (deterministic, fixed hole cards):
poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust

# Short-stack push/fold — single cell or full 169-class chart:
poker-solver pushfold --stack 10 --position sb_jam --hand AKs
poker-solver pushfold --stack 8 --position bb_call_vs_jam --full-range --json
```

Ad-hoc postflop subgames (`--hunl-mode postflop`) enumerate the hole-card
chance node, and that tree dominates wall-time regardless of iteration count.
Expect multi-minute runs on a flop and tens of seconds on a river with a
small bet menu — budget time accordingly.

See [`USAGE.md`](USAGE.md) for the full CLI reference, custom subgames, and
asymmetric-contribution examples.

## Quick start (Python)

The engine is usable as a library. `equity`, `solve`, `solve_hunl_postflop`,
`solve_hunl_preflop`, `solve_range_vs_range`, `get_pushfold_strategy`,
`HUNLConfig`, `Range`, `parse_range`, and more are importable from the
top-level `poker_solver` package.

```python
from poker_solver import parse_range, get_pushfold_strategy

# Short-stack push/fold lookup:
print(get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs"))

# Parse a Pio-style range string into a Range:
hero = parse_range("AA, KK, AKs, 76s+")
```

There are two range-vs-range entry points that solve **different objects**:

- **`solve_range_vs_range`** (aggregator, `poker_solver/range_aggregator.py`)
  — runs a per-(hero combo, villain combo) full-information Nash and pools by
  combo weight. Fast, but produces basket-selection strategies that diverge
  from true range Nash on polarized spots.
- **`solve_range_vs_range_rust`** (vector form, `poker_solver._rust`) — the
  joint range-vs-range Nash via vector-form DCFR in the Rust core. This is the
  production-grade path for true range Nash.

See [`docs/aggregator_vs_true_nash_explainer.md`](docs/aggregator_vs_true_nash_explainer.md)
for when to use which, and [`USAGE.md`](USAGE.md) for the full library API,
including node locking and off-path filtering.

## Architecture (brief)

Two tiers, kept honest by differential testing. The Python package
`poker_solver/` is the readable spec / ground truth; the Rust crate
`crates/cfr_core/` (built as `poker_solver._rust` via PyO3 / maturin) is the
workhorse. Every algorithm lands in Python first, ports to Rust, and is gated
by diff tests before the Rust tier is trusted. See [`DEVELOPER.md`](DEVELOPER.md)
for the full breakdown, including the card abstraction and HUNL solver layout.

## Development

```bash
# Tests (Python + Rust):
pytest
cargo test --all --manifest-path crates/cfr_core/Cargo.toml

# Lint + format:
ruff check
ruff format --check
cargo clippy --all-targets --manifest-path crates/cfr_core/Cargo.toml -- -D warnings
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the PR-flow contract.

## References

The CFR / DCFR / HUNL literature and reference codebases used for study and
correctness checks live under `references/` (not redistributed here).

Algorithmic foundations: DCFR (Brown & Sandholm 2019); CFR+ (Tammelin 2014);
vanilla CFR (Zinkevich, Johanson, Bowling, Piccione 2007); Libratus (Brown &
Sandholm 2017); Pluribus (Brown & Sandholm 2019). Correctness oracles:
DeepMind's `open_spiel` (Apache 2.0) for Kuhn / Leduc, and Noam Brown's
`noambrown/poker_solver` (MIT) for river spots and the vector-form CFR port.

## Notation

- Ranks: `2 3 4 5 6 7 8 9 T J Q K A`
- Suits: `s h d c` (spades, hearts, diamonds, clubs)
- Card: rank + suit, e.g. `Ah`, `Ts`, `2c`
- Range: `AA`, `AKs`, `AKo`, `AK` (both), `KK-TT`, `76s+`, comma-combined

## License

MIT. See [`LICENSE`](LICENSE).
