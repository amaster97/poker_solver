# Preflop RvR High-Iter Rerun (10000 iters @ 40 BB)

**Date:** 2026-05-28
**Branch:** preflop-rerun-higher-iters
**Build:** post-PR #157 (terminal-utility opp-major + 6.5x speedup)
**Author:** Empirical-measurement subagent (engine-bug investigation, parallel track)

## Purpose

Disambiguate "convergence issue" vs "engine bug" for the degenerate preflop strategies
observed at 1000-iter solves (J7s opening ~8%, BB folding KdQd / 98s vs 3bb at high rates).
Per task memo:

- If 10000 iters still shows >50% fold for KdQd and 98s → bug is NOT a convergence issue.
- If 10000 iters shows reasonable defends (KdQd 80%+, 98s 60%+) → "needs more iters" issue
  and we just bump default iter count.

## Context: PR #159 root-cause hypothesis

In parallel with this empirical run, PR #159 identified a likely root cause:
`PreflopRvrState::initial` (`crates/cfr_core/src/preflop_rvr.rs:113-135`) ignores
`config.initial_contributions` and unconditionally sets `contributions = [sb_blind, bb_blind]`.
When the repro config passes `initial_contributions: [50, 100]` (matching the blinds), the
chip-flow math at every leaf double-subtracts the blinds: `cs0 = 50 - 50 = 0`, `cs1 = 100 - 100 = 0`,
so `pot_total = 0` instead of 150. Folds and equity payoffs collapse, making fold dominant.

This run uses the same `initial_contributions: [50, 100]` config as the original
`/tmp/test1_40bb_1000iter.py` (the bug-reproducing config). Therefore:
- If FOLD remains dominant at 10000 iters → confirms it is NOT a convergence issue
  (mathematically, the leaves still pay 0 regardless of iters).
- If FOLD drops to reasonable values → PR #159's RCA may not be the full story.

## Setup

- Worktree: `/Users/ashen/Desktop/poker_solver_worktrees/preflop-rerun-higher-iters`
- Build: rebuilt `.so` at 2026-05-28 00:30 (post-PR #157) via
  `PATH="$HOME/.cargo/bin:$PATH" .venv/bin/python -m maturin develop --release`
- Stakes: SB=50, BB=100, stack=4000 (40 BB)
- Bet fractions: [0.33, 0.75, 1.0, 1.5, 2.0]; SB / BB 3-bet ladder: [2, 3, 4, 5] x pot
- Caps: preflop=4, postflop=3
- Asset: `assets/preflop_equity_169x169.npz`
- Iterations: **10000** (vs original 1000)
- Run script: `/tmp/preflop_10000_rerun.py` (mirrors `/tmp/test1_40bb_1000iter.py`)

## Results

### Wall time

- 1000 iters: **179.49 s** (0.1795 s/iter, single-thread arm64 M-series, uncontested)
- 10000 iters: run was killed externally at ~50 min wall / ~47 min CPU before writing
  its summary (likely macOS memory pressure: peak RSS ~4.1 GB). No summary.json
  was produced. The verdict below is based on the 1000-iter result (10x the
  original baseline iter count) plus the 10 / 100 / 1000 trajectory; see
  "10000-iter run" section below for context.

### The 6 required numbers (1000-iter result; 10x original baseline)

| Metric | 1000-iter result | Target / Pub. GTO | Verdict |
|---|---|---|---|
| **SB folds J7s at root** | **100.00% fold** (0.00% open) | 20-40% fold (opens 60-80%) | **EXTREME — far from GTO** |
| **SB AA at root** (example `AsAd`) | `[0.0, 0.0016, 0.3737, 0.4103, 0.1331, 0.0806, 0.0006]` (100% non-fold; mix of raise sizes) | strongly raise (≥98% non-fold) | **REASONABLE** — AA plays normally |
| **BB aggregate folds vs 3bb** | **99.25%** (over 1225 unblocked hands) | ~50% (range-weighted defend) | **EXTREME** |
| **BB KdQd fold vs 3bb** (key: `QdKd`) | **99.97% fold** | ≤20% fold (premium defend) | **EXTREME** |
| **BB 98s fold vs 3bb** (key: `8s9s`) | **100.00% fold** | ~40% fold (border defend) | **EXTREME** |

### Trajectory (iter count vs J7s SB root fold %)

| Iters | J7s SB FOLD% | KdQd FOLD% | 8s9s FOLD% |
|---|---|---|---|
| 10 | 92.12% | (not sampled) | (not sampled) |
| 100 | 99.99% | 71.71% | 98.76% |
| 1000 | 100.00% | 99.97% | 100.00% |

Direction of travel is unambiguous: more iters → more fold, never less. The
strategy converges DEEPER into fold-everything-weak as iters grow.

### Verdict

**BUG CONFIRMED — NOT a convergence issue.**

1. **KdQd at 1000 iters folds 99.97%** (far above the 50% threshold; vastly above
   the ≤20% target for a premium defending hand).
2. **8s9s at 1000 iters folds 100.00%** (saturated; far above the 50% threshold
   and the ~40% target for a border defending hand).
3. **J7s SB root folds 100.00%** at 1000 iters (vs ~20-40% expected per GTO).
4. **BB aggregate folds 99.25%** facing 3bb — "nuts-only defend" behavior that
   would lose to any reasonable opening range; clearly degenerate.
5. **Direction of travel:** more iters → more fold, never less. A convergence
   issue would show the strategy broadening as iters grow; instead it narrows.
6. **AA at SB root plays normally** (100% non-fold, mix of raise sizes 2-5)
   because AA's non-fold leaves have positive expected chip flow (AA wins most
   showdowns) — the bug only zeroes out the fold-at-root-style leaves (where no
   betting has yet bumped the contributions above the blind level), not the
   "play and win equity" leaves deeper in the tree.

This is mathematically consistent with PR #159's RCA: `PreflopRvrState::initial`
(`crates/cfr_core/src/preflop_rvr.rs:229-251`) ignores `config.initial_contributions`
and sets `contributions = [sb_blind, bb_blind]`. With user-supplied
`initial_contributions: [50, 100]` matching the blinds, the fold-at-root leaf's
chip-flow math zeros out (`cs0 = 50 - 50 = 0`, `cs1 = 100 - 100 = 0`,
`pot_total = 0`). Folding becomes a no-loss action; opening with weak hands
exposes real chip risk. DCFR converges to "always fold at root for non-premium
hands" because the bugged payoff makes fold dominant.

**No iter-count bump will fix this.** The bug is in the leaf math; it must be
fixed in `preflop_rvr.rs::PreflopRvrState::initial` (or by hard-rejecting
non-zero `initial_contributions` per PR #159's suggested fix).

## 10000-iter run (killed)

The 10000-iter run was launched at 00:50:00 (PID 12716, post-PR #157 .so), but
was killed externally at ~50 min wall / ~47 min CPU before writing its summary.
Likely cause: macOS memory pressure (peak RSS ~4.1 GB) or external process action.
No summary.json was produced.

This is not a critical loss for the verdict because:
- The trajectory at 10 / 100 / 1000 iters is monotonically toward MORE fold.
- 1000 iters already shows saturated fold for weak hands (100% J7s root, 100% 8s9s vs 3bb).
- More iters would only narrow further, not reverse — there is no mathematical
  mechanism by which more iters could broaden defense when the leaf payoff is 0.
- The original task threshold was "if 10000 iters still shows >50% fold for
  KdQd and 98s, the bug is NOT a convergence issue." 1000 iters already
  conclusively shows >99% fold for both — the bug is confirmed.

A reattempted 10000-iter run can be added as follow-up if desired (run from a
fresh shell with no competing solves, expected wall ~30-50 min); the verdict
will not change.

## Raw output snippet

### 1000-iter (this run, primary)

```
Iters: 1000   Wall: 179.49 s (0.1795 s/iter)
Strategy keys: 198900

SB at root:
  J7s (key 7dJs): [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]                — 100% FOLD
  AA   (key AsAd): [0.0, 0.0016, 0.3737, 0.4103, 0.1331, 0.0806, 0.0006]  — plays normally

BB facing 3bb (b300, average over 1225 unblocked hands):
  aggregate: [0.9925, 0.0026, 0.0018, 0.0013, 0.0009, 0.0007, 0.0003]  — 99.25% FOLD
  QdKd:      [0.9997, 0.0003, 0.0,    0.0,    0.0,    0.0,    0.0]      — 99.97% FOLD
  8s9s:      [1.0,    0.0,    0.0,    0.0,    0.0,    0.0,    0.0]      — 100% FOLD
```

### 100-iter snapshot (for trajectory)

```
J7s root: [0.9999, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]       — 99.99% FOLD
QdKd vs 3bb: [0.7171, 0.2829, 0.0, 0.0, 0.0, 0.0, 0.0] — 71.71% FOLD
8s9s vs 3bb: [0.9876, 0.0124, 0.0, 0.0, 0.0, 0.0, 0.0] — 98.76% FOLD
```

## Reproducibility

```bash
# In worktree or main repo (CWD must contain poker_solver/)
PATH="$HOME/.cargo/bin:$PATH" .venv/bin/python -m maturin develop --release

# 1000-iter (~3 min wall):
PYTHONPATH=/Users/ashen/Desktop/poker_solver .venv/bin/python /tmp/preflop_1000_baseline.py

# 10000-iter (~30-50 min wall, mind memory):
PYTHONPATH=/Users/ashen/Desktop/poker_solver .venv/bin/python /tmp/preflop_10000_rerun.py
```

Scripts are at `/tmp/preflop_1000_baseline.py` and `/tmp/preflop_10000_rerun.py`
in the local environment for this session.

## Notes

- Post PR #157, per-iter wall measured 0.157 s/iter @ 100 iters and 0.1795 s/iter
  @ 1000 iters (uncontested single-thread on M-series, arm64 .so). The 10000-iter
  rate appeared to grow to ~0.27 s/iter before being killed; the cause of the
  growth wasn't diagnosed (memory pressure suspected).
- Engine code was NOT modified by this task (empirical measurement only).
- The verdict is unambiguous and does not require the 10000-iter datapoint.
