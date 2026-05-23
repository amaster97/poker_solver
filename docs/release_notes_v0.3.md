# poker_solver v0.3 release notes

**Release date:** 2026-05-21
**Codename:** "HUNL substrate"

This release closes the small-game phase of the project (Kuhn + Leduc) and
stands up the full Heads-Up No-Limit Hold'em (HUNL) substrate. The engine
can now represent any HUNL spot, enumerate the legal action set under a
discretized betting abstraction, and play short-stack push/fold optimally
via lookup. Equity calculations also got faster and more precise.

This is not yet a working full-tree solver — that lands in PR 5. But every
moving part that PR 5 needs to plug into is now in place and tested.

---

## What's new

### 1. HUNL game tree + 14-action abstraction (PR 3)

The third game in the `Game` protocol family, alongside Kuhn and Leduc.

- **Heads-Up No-Limit Hold'em**: full state machine across preflop, flop,
  turn, river, and showdown, with chance nodes for hole-card and board
  deals.
- **14-action enum**: `FOLD`, `CHECK`, `CALL`, five opening bet sizes
  (33% / 75% / 100% / 150% / 200% of pot), five raise sizes (same
  fractions), and `ALL_IN`.
- **Raise caps**: preflop 4 (enough for the 4-bet/5-bet ladder), postflop
  3. After cap, the next aggressive action forces all-in.
- **Ante support**: built in from the start (default 0).
- **Integer-cents chip arithmetic**: 1 BB = 100 cents internally; no
  floating-point chip math anywhere in the tree code. Floats only
  appear at terminal states for compatibility with the `Game` protocol.

### 2. Push/fold charts for short stacks (PR 3.5)

When stacks are short enough, the optimal HUNL preflop game collapses to
shove-or-fold. Running the full tree builder + DCFR there is pure waste.

- **Coverage**: every integer stack depth from **2 to 15 BB**, both
  positions (`sb_jam` and `bb_call_vs_jam`).
- **Method**: real DCFR-generated Nash equilibrium per depth. We solve
  the suit-symmetric abstracted matrix game (169 x 169 hand classes) with
  card-removal-aware compat weighting. Mathematically equivalent to
  solving the full HUNL preflop tree, ~100x faster.
- **Action set**: pure jam/fold. No minraise or limp lines in v1
  (see "Known limitations" below).
- **Quality**: exploitability < 0.0001 BB/100 at every depth; spec
  target was < 0.05 BB/100.
- **Automatic dispatch**: `solve(HUNLPoker(config))` routes to chart
  lookup whenever the effective stack lands in `[2, 15]` BB. Callers
  don't have to know which mode they're in.

### 3. Hybrid exact + Monte Carlo equity calculator

`equity()` now picks the right code path automatically.

- **Exact enumeration** when all hands are concrete and the remaining
  board space is small. A flop hand-vs-hand evaluates all 990 runouts
  in ~60 ms; turn and river are even cheaper. No sampling noise.
- **Monte Carlo** for ranges, multiway-with-range, and any state where
  the runout space exceeds `enum_threshold` (default 100,000).
- **Default precision raised**: 250,000 MC iterations by default
  (was 10,000). Standard error per hand: ~0.1% instead of ~0.5%.

### 4. Tests and tooling

- **150+ tests** across 15 test modules, all passing on Python 3.13 and
  the Rust crate.
- **Differential testing** between Python reference and Rust production
  tiers on Kuhn and Leduc; Rust matches Python within 1e-4 per action
  probability.
- **Mandatory PR audit** from PR 3 onward: a fresh agent with no
  implementation context reviews the diff before the user sees it.
  PR 3's audit returned READY with 0 must-fix items.

---

## How to use it

### Compute equity

```bash
# Exact (auto-enumerated, ~60 ms):
poker-solver equity AhKh QdQc --board 2h7h9d

# Monte Carlo (range vs hand, 250k iter default):
poker-solver equity "AA,KK,AKs" QdQc

# Custom precision:
poker-solver equity AhKh QdQc -n 1000000
```

### Solve Kuhn or Leduc (small-game validation)

```bash
poker-solver solve --game kuhn  --iterations 50000
poker-solver solve --game leduc --iterations 5000
poker-solver solve --game kuhn  --iterations 50000 --backend rust
```

### Solve a tiny HUNL river subgame

```bash
poker-solver solve --game hunl --hunl-mode tiny_subgame
```

Solves a deterministic AhKc-vs-QdQh river fixture (board As7c2dKh5s,
pot 1000, stacks 1000). Useful as a sanity check that the HUNL substrate
plumbs end-to-end through the existing DCFR loop.

### Look up a push/fold strategy

```python
from poker_solver import get_pushfold_strategy, get_full_range

# Single hand:
freq = get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs")
# -> 1.0  (jam 100% with AKs at 10BB)

# Whole range:
chart = get_full_range(stack_bb=8, position="bb_call_vs_jam")
# -> {"AA": 1.0, "KK": 1.0, ..., "32o": 0.0}  (169 hand classes)
```

Or let `solve()` dispatch automatically:

```python
from poker_solver import HUNLConfig, HUNLPoker, solve

# 10 BB effective; solve() routes to chart lookup, returns instantly.
game = HUNLPoker(HUNLConfig(starting_stack=1000))  # 10 BB at default blinds
result = solve(game, iterations=0)
# result.backend == "pushfold"
```

### Use the library directly

```python
from poker_solver import HUNLPoker, HUNLConfig, default_tiny_subgame, solve

# Tiny river subgame:
game = HUNLPoker(default_tiny_subgame())
result = solve(game, iterations=10_000)
print(f"Game value: {result.game_value:+.4f} BB (P0 perspective)")
```

---

## What's coming

The next three PRs together unlock full-tree HUNL solving on a MacBook.

- **PR 4 — Card abstraction.** Imperfect-recall EMD bucketing across all
  three postflop streets. Targets: 256 flop / 128 turn / 64 river buckets.
  Suit-isomorphism included. This is the lever that makes HUNL fit in
  10-14 GB instead of OOM'ing the laptop.

- **PR 5 — HUNL postflop solve (Python reference).** The first PR that
  actually solves a real postflop spot end-to-end. Also ships a per-street
  memory profiler so we can re-tune PR 4's abstraction with measured data
  instead of estimates.

- **PR 6 — HUNL postflop port to Rust.** Mechanical port of the PR 5
  Python reference. License-aware: we only copy from MIT / Apache 2.0
  sources. After this PR, differential tests between Python and Rust on
  real HUNL spots become routine.

Further out: NEON SIMD vectorization (PR 8), HUNL preflop (PR 9),
NiceGUI scaffold (PR 10), macOS packaging with codesign + notarize + .dmg
(PR 11).

---

## Known limitations

We are not yet PioSolver. Be honest about what works in v0.3 and what
doesn't.

- **No full HUNL solve yet.** `poker-solver solve --game hunl
  --hunl-mode full` deliberately raises `NotImplementedError`. The tree
  and action abstraction are in place; the solver loop that walks them
  at scale is PR 5 (Python) and PR 6 (Rust). Until then, only the
  tiny single-street fixture and push/fold lookup work end-to-end.

- **Push/fold charts: pure jam/fold only.** No minraise / limp / 3-bet
  lines in v1. At 12-15 BB this is slightly suboptimal vs. the
  Nash-with-minraise solution (estimated ~5 BB/100 EV loss in the
  borderline regime per published references). Users wanting tighter
  charts at the top of the range should fall back to the full tree
  solver once PR 5 lands. Equity matrix in the generator uses 4 combo
  pairs and 350 boards per (h_sb, h_bb) class pair; per-pair standard
  error is ~1%, propagating to <0.5% strategy noise except on
  borderline mixed combos.

- **Push/fold charts: single ante config (= 0).** Tournament play often
  uses 12.5% or 25% antes; those shift jam ranges materially. v1 is
  no-ante only. v2 chart pack could add `pushfold_v1_ante*.json` files
  without breaking the lookup API.

- **Push/fold charts: symmetric stacks only.** Both players have
  `starting_stack = depth * BB`. The chart cannot answer "what does SB
  jam at 5 BB when BB has 100 BB?" (vanishingly rare HU spot in practice.)

- **Rust backend doesn't yet cover HUNL.** Rust handles Kuhn and Leduc
  today. HUNL Rust port lands in PR 6, gated on PR 5 Python reference
  being correct.

- **No GPU. No cloud.** This is a MacBook-only project. CPU-only with
  ARM NEON 128-bit SIMD coming in PR 8.

- **`__version__` lag**: package metadata still reports `0.2.0` while
  the release tag is `0.3.0`; a sync PR will reconcile this.

---

## Migration notes

Existing callers of `equity()` from v0.2 see two behavior changes worth
double-checking:

1. **Default iterations bumped to 250,000.** If you were relying on the
   default and have tight latency budgets, pass `iterations=10_000`
   explicitly. Otherwise, free precision.
2. **Exact enumeration on concrete hands with small board spaces.** The
   return type is unchanged (`list[EquityResult]`), but `iterations` on
   the result now reflects the number of runouts enumerated (e.g. 990
   for a flop) rather than the requested MC count. Tests that pin a
   specific `iterations` value need updating.

No `solve()` API breaks for existing Kuhn / Leduc callers. The new
short-stack-HUNL dispatch only activates when the input game is a
`HUNLPoker` with effective stack in `[2, 15]` BB; it's invisible to
existing callers.

---

## Acknowledgments

- **DCFR** (Brown & Sandholm 2019, *Solving Imperfect-Information Games
  via Discounted Regret Minimization*) — the algorithm we use.
- **`open_spiel`** (Apache 2.0, DeepMind) — Kuhn / Leduc rules reference
  and correctness oracle.
- **`noambrown/poker_solver`** (MIT, Noam Brown) — two-tier C++/Python
  pattern that validated our architecture choice; will be the
  river-spot diff oracle in PR 7.
- **Sklansky & Miller** (*No Limit Hold'em Theory and Practice*, 2006) —
  Sklansky-Chubukov push/fold table anchors used for cross-checking
  short-stack charts.

---

## License

MIT. No AGPL-licensed code is copied into this repository.

For the full plan, decision log, and roadmap, see `PLAN.md`.
