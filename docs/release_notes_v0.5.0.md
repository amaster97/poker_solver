# poker_solver v0.5.0 release notes

**Release date:** 2026-05-22
**Codename:** "Rust HUNL goes live"

This release lights up the Rust tier on HUNL postflop. The Python reference
solver from PR 5 has been mechanically ported to Rust under
`crates/cfr_core/`, exposed through PyO3, and gated by a bit-exact
differential test against the Python tier on a river-only subgame fixture.
Day-to-day postflop solves now finish ~24x faster end-to-end with the same
DCFR semantics and the same abstraction artifacts loaded under both tiers.

External Nash validation against a third solver is still pending (PR 7);
this release locks the internal-parity half of the validation chain.

---

## What's new

### 1. HUNL postflop solver — Rust tier (PR 6)

The mechanical port of PR 5's Python reference into `crates/cfr_core/`.

- **~24x speedup over Python** on a 100k-iter river-subgame solve
  (3.88 s Rust vs 92.87 s Python; Apple M4 Pro, median of 3 trials).
  Ratio asymptotes to ~24x by 10k iters; lower iteration counts see
  ~17-23x as fixed Python-side tree-build and exploitability-recompute
  overhead masks part of the per-iter DCFR speedup. Inside the 10-50x
  PLAN.md target. PR 8 SIMD + cache-blocking + slumbot lookup table
  closes the rest of the gap.
- **Bit-exact diff-tested** against the Python tier on the river-only
  fixture. `max_abs_diff = 0.0` across the full strategy table at 1000
  iters; exploitability matches to the last digit of scientific format
  (`4.1793e-07`) across 500 / 1k / 10k / 100k iterations. Exceeds the
  PR 6 spec's 1e-3 river tolerance by six orders of magnitude.
- **Same DCFR semantics** as the Python tier: α=1.5, β=0, γ=2.0. Same
  action menu, same bucket lookups, same chance enumeration. The port
  is mechanical — no algorithmic divergence between tiers.
- **Loads the same PR 4 abstraction artifacts.** Rust parses the
  `.npz` layout from PR 4 directly (`abstraction.rs`); no separate
  Rust-side abstraction build step, no duplicated cluster tables.
- **GIL released during the solve** (`py.allow_threads`), so other
  Python threads remain responsive while the Rust DCFR loop runs.

### 2. `--backend rust` CLI flag on `solve --hunl-mode postflop`

The existing `solve` subcommand learns one new flag.

- **`--backend rust`** routes the HUNL postflop solve through the new
  Rust path. Default remains `python` (PR 5 behavior unchanged).
- **Kuhn / Leduc** already had `--backend rust` from earlier PRs; the
  flag is now consistent across all three games.
- **HUNL push/fold short-circuit (PR 3.5) still takes precedence.** If
  the effective stack lands in `[2, 15]` BB on the preflop path, the
  chart lookup wins before either backend dispatches. Documented in
  the dispatch order: push/fold short-circuit → HUNL postflop Rust →
  HUNL postflop Python fallback → HUNL preflop `NotImplementedError`
  (PR 9) → Kuhn / Leduc.

### 3. PyO3 export: `poker_solver._rust.solve_hunl_postflop`

The new Rust entry point, exposed for library callers who want to
skip the CLI.

- **Signature:** `solve_hunl_postflop(config_json, abstraction_path,
  iterations, alpha, beta, gamma, target_exploitability, seed)`.
  Returns `HUNLSolveOutput` (strategy, value, exploitability,
  iteration metadata).
- **JSON-string config marshalling** at the PyO3 boundary. Single
  ingress point, easy to log, easy to diff against the Python
  serializer's output.
- **`target_exploitability` early-exit forwarded.** Same convergence
  hook the Python tier exposes.

### 4. Tests

- **20+ new tests** across the Rust crate and the Python diff suite,
  all passing. 12 new Rust unit tests in
  `crates/cfr_core/tests/test_hunl_rust.rs` and 8 Python diff tests in
  `tests/test_hunl_diff.py`, plus one cross-tier smoke test.
- **`test_hunl_river_subgame_diff_python_vs_rust`** is the gate: 1000
  iters at 1e-3 tolerance, currently passing at bit-exact.
- **`test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction`**
  covers the flop path on a synthetic abstraction: 200 iters at
  5e-3 tolerance, passing.
- **Threaded test** confirms `py.allow_threads` releases the GIL
  cleanly during the DCFR loop.

---

## Honest caveats

### 1. Bit-exact parity verified on the river-only subgame (16 infosets)

The bit-exact result is on the locked tiny river fixture: board
`As 7c 2d Kh 5s`, P0 `AhKc` vs P1 `QdQh`, pot 1000, stacks 1000.
This is a 16-infoset tree — small enough that DCFR converges to
near-zero exploitability inside 1000 iterations, and small enough
that float reductions in both tiers happen in the same order.
Larger trees may see small float drift (within the 1e-3 / 5e-3
diff tolerance documented in PR 6).

### 2. Full-spot flop solves still inherit PR 4's abstraction coverage gap

PR 4 shipped 256 flop / 128 turn / 64 river buckets, but turn
coverage is the known-weak link in the abstraction pipeline. PR 6
does not touch the abstraction — it consumes whatever PR 4 wrote
to disk. Real flop spots that traverse the turn will inherit any
PR 4 imprecision; the Rust tier accelerates the solve but does
not correct the abstraction.

### 3. External Nash validation is deferred to PR 7

Bit-exact Python ↔ Rust agreement proves the two tiers compute the
**same** answer; it does not prove that answer is the **Nash**
equilibrium. The PR 7 `noambrown` diff harness will be the first
place an external solver enters the validation chain. Plausibility
checks on the v0.5.0 fixture pass (game value positive for P0 who
holds the nut, exploitability ≤ 1e-9 at 1000 iters, P1 folds the
river to most bet sizes as theory predicts), but those are smell
tests — not external Nash agreement.

If your application requires third-party Nash validation, wait for
PR 7 before using the v0.5.0 Rust tier in production.

---

## How to use it

### Solve a tiny HUNL river subgame on the Rust tier

```bash
poker-solver solve --game hunl --hunl-mode tiny_subgame \
  --backend rust --iterations 10000
```

Runs the locked river fixture (board `As 7c 2d Kh 5s`, P0 `AhKc`,
P1 `QdQh`) through the new Rust dispatch. Returns the same strategy
table the Python tier produces, ~24x faster.

### Compare backends side-by-side

```bash
# Python tier (reference; PR 5 path):
poker-solver solve --game hunl --hunl-mode tiny_subgame \
  --backend python --iterations 100000

# Rust tier (new; this release):
poker-solver solve --game hunl --hunl-mode tiny_subgame \
  --backend rust --iterations 100000
```

Both runs print the same strategy table to the last digit of the
printed scientific format on this fixture; the Rust run finishes
in ~3.9 s, the Python run in ~93 s.

### Library API

```python
from poker_solver import HUNLPoker, default_tiny_subgame, solve

game = HUNLPoker(default_tiny_subgame())
result = solve(game, iterations=10_000, backend="rust")
print(f"Game value: {result.game_value:+.4f} BB (P0 perspective)")
print(f"Exploitability: {result.exploitability:.2e}")
```

The `backend` kwarg routes through the same dispatch the CLI uses;
push/fold short-circuit still takes precedence on short stacks.

---

## What's still coming

- **PR 7 — External Nash validation.** Wire the noambrown C++ solver
  (Brown 2026, MIT) into a river-spot diff harness against PR 6's
  fixture. First external anchor in the validation chain.
- **PR 8 — NEON SIMD + cache-blocking + PCS.** ARM 128-bit SIMD on
  the per-iter regret update, cache-blocked traversal, and Slumbot's
  7-card-eval lookup table. Targets 10-50x more speedup *on top of*
  PR 6's ~24x.
- **PR 9 — HUNL preflop (full game).** Removes the
  `NotImplementedError` on `--hunl-mode preflop`. End-to-end full-tree
  HUNL solve, Python and Rust tiers in parallel.
- **PR 10a / 10b — UI.** NiceGUI scaffold (10a) and full strategy
  browser (10b).
- **PR 11 — macOS .dmg.** Codesign + notarize + .dmg packaging.
- **PR 12 — 3-handed stretch.** Post-v1 scope; not on the v1
  critical path.

---

## Acknowledgments

- **Noam Brown** (`noambrown/poker_solver`, MIT) — the two-tier
  C++/Python port pattern that PR 6's Rust tier follows. PR 7's
  external diff harness will use the same repo as its oracle.
- **Slumbot 2019** (MIT) — k-means clustering and 7-card-eval lookup
  pattern that informed PR 4's abstraction and the PR 8 perf roadmap.
- **NO postflop-solver** (AGPL) — read-only inspiration; **nothing
  copied**. Every new `.rs` file in PR 6 ships the standard "NEVER
  copy from postflop-solver or TexasSolver" disclaimer, and
  `check_pr.sh`'s license audit confirms zero AGPL/GPL deps.

---

## License

MIT. No AGPL-licensed code is copied into this repository.

For the full plan, decision log, and roadmap, see `PLAN.md`.
