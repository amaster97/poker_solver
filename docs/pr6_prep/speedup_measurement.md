# PR 6 speedup verification — measured

Verification of the PR 6 commit-message draft claim:

> "HUNL postflop solve on the river fixture runs in ~3 s in Rust vs ~95 s
> in Python (~30x speedup, on track for the 10-50x PLAN.md target;
> measured pending, recheck before commit)."

This run replaces the "measured pending" caveat with hard numbers.

## Fixture

`default_tiny_subgame()` from `poker_solver.hunl` — river-only, 16 infosets.
- Board: As 7c 2d Kh 5s (river complete)
- Hole cards: P0 AhKc vs P1 QdQh
- No abstraction (lossless mode, both tiers)
- DCFR α=1.5, β=0, γ=2.0 (default)

Game is wrapped through the unified API: `solve(HUNLPoker(cfg), iterations=N, backend=...)`.
Both tiers run end-to-end through `solver.py` dispatch, so the comparison is
apples-to-apples: same fixture, same hyperparameters, same exploitability
recompute path. Rust dispatch was confirmed live (`_rust.solve_hunl_postflop`
is wired and returns bit-exact strategy on the river fixture).

## Environment

- Hardware: Apple M4 Pro (arm64), macOS 15.6.1
- Python: 3.13.1
- Rust: rustc 1.95.0 / cargo 1.95.0
- Rust extension: `poker_solver/_rust.cpython-313-darwin.so` (1.31 MB),
  built today in release mode
- Single-threaded; no concurrent load on the box during measurements

## Measurements

Each (iters, backend) pair below is wall-clock from `time.perf_counter()`
around the full `solve(...)` call (which includes Python-side tree build,
Rust solve via `py.allow_threads`, and Python-side exploitability recompute
on the returned strategy). Imports done once before timing — they are not
in the measured window.

### 1,000 iterations (PR 6 differential-test count)

| Trial | Python (s) | Rust (s) | Ratio |
|-------|-----------:|---------:|------:|
| 1     |     0.916  |   0.044  | 20.7x |
| 2     |     0.905  |   0.044  | 20.6x |
| 3     |     0.905  |   0.042  | 21.3x |
| **Median** | **0.905** | **0.044** | **20.6x** |

Exploitability (final): Python `4.1793e-07`, Rust `4.1793e-07` — bit-exact.

### 10,000 iterations

| Trial | Python (s) | Rust (s) | Ratio |
|-------|-----------:|---------:|------:|
| 1     |     8.953  |   0.375  | 23.8x |
| 2     |     8.954  |   0.383  | 23.4x |
| 3     |     8.954  |   0.383  | 23.4x |
| **Median** | **8.954** | **0.383** | **23.4x** |

Exploitability (final): Python `4.1962e-10`, Rust `4.1962e-10` — bit-exact.

### 100,000 iterations (matches commit message's "~95 s / ~3 s" claim)

| Python (s) | Rust (s) | Ratio |
|-----------:|---------:|------:|
|     92.867 |    3.877 | 24.0x |

Exploitability (final): Python `4.2011e-13`, Rust `4.2011e-13` — bit-exact.

## Verdict

The commit message's two coupled claims:

1. **"~3 s in Rust vs ~95 s in Python"** — accurate. Measured at 100k iters:
   Python 92.9 s, Rust 3.9 s. Matches the prose to 2 significant figures.
2. **"~30x speedup"** — slightly optimistic. Measured ratio asymptotes to
   ~24x as iteration count grows (20.6x at 1k, 23.4x at 10k, 24.0x at 100k).
   The 30x figure overstates by ~25%, but it is within the user's 0.5x–2x
   honesty band and inside the PLAN.md 10-50x target window. The trend is
   convergent — adding iterations is not going to push it to 30x; it
   asymptotes near 24x because Rust scales linearly with iters while
   Python's per-iter cost is also dominated by tree-walk work (the same
   work Rust accelerates), so the ratio just inverts to a constant.

The "10-50x PLAN.md target" framing is correctly satisfied either way.

### Iteration-count sensitivity (addresses the agent prompt's caveat)

The agent prompt flagged that "Python's import-and-setup overhead may
drown actual compute time" on a 16-infoset river subgame. The data
shows this is NOT the dominant artifact:
- 500 iters: 17.3x  (Python 0.460s / Rust 0.027s)
- 1000 iters: 20.6x  (Python 0.905s / Rust 0.044s)
- 10000 iters: 23.4x  (Python 8.95s / Rust 0.383s)
- 100000 iters: 24.0x  (Python 92.9s / Rust 3.88s)

The ratio does increase with iters (17.3 → 20.6 → 23.4 → 24.0), which
confirms there is a small constant-overhead component in Python — but
it stabilizes near 24x by 10k iters and barely moves between 10k and
100k. The river subgame is small enough that per-call Python tree-build
and exploitability-recompute add a fixed cost on top of the per-iter
DCFR loop; both backends pay this Python-side cost, so the ratio is
slightly suppressed at small iteration counts. By 10k iters the per-iter
DCFR loop dominates and we see the true tier ratio.

### Bit-exact agreement preserved

Across all four iteration counts (500 / 1k / 10k / 100k), the final
exploitability matches between Python and Rust to the last digit of the
printed scientific format. This is the same bit-exact pattern the PR 6
draft cites for the 1000-iter river-fixture differential test, and it
confirms the parity gate holds at much longer runs than the spec
tolerance test exercises.

## Recommended commit-message edit

The current draft says:

> ~3 s in Rust vs ~95 s in Python (~30x speedup, on track for the 10-50x
> PLAN.md target; measured pending, recheck before commit).

Replace with the measured form. Two viable rewrites:

**Option A (preserve current prose, just delete the caveat):**

> ~3.9 s in Rust vs ~93 s in Python at 100k iters (~24x speedup, inside the
> 10-50x PLAN.md target). Lower iteration counts see ~17-23x as the
> Python-side tree-build and exploitability-recompute overhead masks part
> of the per-iter DCFR speedup.

**Option B (defensible, slightly hedged, current style):**

> ~4 s in Rust vs ~93 s in Python on a 100k-iter river-subgame solve
> (~24x speedup; inside the 10-50x PLAN.md target). PR 8 SIMD +
> cache-blocking + slumbot lookup table closes the rest of the gap.

The CLI smoke claim ("<3 s for 500 iters via --backend rust") is
**conservatively accurate** — measured 500-iter Rust solve runs in
0.027 s, two orders of magnitude under the "<3 s" ceiling. The bound
is honest but no longer tight; consider tightening it to "<0.1 s" or
leaving as-is since "<3 s" is also true.

## Files exercised

- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `default_tiny_subgame()`
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `solve()` dispatch (incl. Rust branch)
- `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` — Rust extension
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs` — `solve_hunl_postflop` entry
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/commit_message_draft.md` — original claim text

No code modified during this verification run.
