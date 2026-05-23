# Using poker_solver — End-User Guide (v1.0.0)

For people who want to **use** the solver to improve their poker game,
not develop it. You should be comfortable in a terminal and editing a
config file; you do not need to read Python or Rust source. The README
is the developer-facing overview; this is the "what can I do with this
today" companion.

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
mock mode (see §4). Roadmap: [`PLAN.md`](PLAN.md).

---

## 2. Installing on macOS

### Path A: `.dmg` (recommended for non-developers)

A codesigned and notarized `.dmg` is the v1.0.0 distribution format.
Distribution channel (web download vs GitHub Release) is TBD; for now,
build it locally:

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

Reading the output: `Game value` is P1's EV in chips per hand (positive
= P1 winning). `Exploitability (final)` is the residual distance from
Nash; smaller is better. `Average strategy` lists each infoset with a
probability vector across its legal actions.

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
development. A banner across the top makes this explicit. PR 10a
(shipped in v1.0.0) deliberately built the UX against this mock surface
so v1.0.0 could ship now; PR 10b swaps in the real solver, expected
with v1.1. See [`docs/pr10_prep/pr10a_spec.md`](docs/pr10_prep/pr10a_spec.md)
and [`docs/pr10_prep/pr10b_spec.md`](docs/pr10_prep/pr10b_spec.md).

Still useful in v1.0.0 for: getting familiar with the workflow,
planning analysis sessions, giving feedback. For real strategies
today, drop down to the CLI in §3.

---

## 5. Library mode (caching solves)

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

## 6. Known limitations (v1.0.0)

- **UI is mock mode.** Clicking **Solve** returns fixture data, not
  real strategies. Wait for PR 10b (expected v1.1) or use the CLI.
- **No HUNL solving above 15 BB yet.** `--hunl-mode full` raises
  `NotImplementedError`, pointing at PR 9. Working paths today: the
  river subgame solver (`--hunl-mode tiny_subgame`) and ad-hoc postflop
  subgames (`--hunl-mode postflop`). Short stacks: use the charts in
  §3a.
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

## 7. What's coming

Tracked in [`PLAN.md`](PLAN.md). The three items most likely to matter:

- **PR 9 — full HUNL preflop solve.** Replaces the `NotImplementedError`
  above 15 BB. ~2 weeks.
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

## 8. Getting help

- Bug reports / feature requests: GitHub issues.
- Roadmap context: [`PLAN.md`](PLAN.md).
- Release notes: [`docs/release_notes_v1.0.0.md`](docs/release_notes_v1.0.0.md).
- License: MIT, see [`LICENSE`](LICENSE).
