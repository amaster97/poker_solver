# EV Invariance Gauntlet — Local PASS Confirmation (2026-05-27)

**Status**: PASS on both fixtures, post-merge of PR #98 at SHA `3cc5eba`.

## Result

Running `tests/test_ev_invariance_gauntlet.py` locally under
`STRICT_ACCEPTANCE=1 .venv/bin/pytest -v --tb=short -s` reproduces the PR #98
baseline within numerical noise on both deep-cap multiplicity fixtures. Total
wall time **345.03 s (5:45)** for 2 parametrizations; both PASSED at the
load-bearing depth=0 gate (`p75 |Δ| ≤ 0.10 BB`, `max |Δ| ≤ 1.50 BB`):

| Fixture          | depth=0 cells | p75 \|Δ\| BB | max \|Δ\| BB | depth=0 verdict | depth≥1 max \|Δ\| BB (informational) |
| ---------------- | ------------- | ------------ | ------------ | --------------- | ------------------------------------ |
| dry_K72_rainbow  | 220           | 0.0183       | 1.0413       | PASS            | 29.57                                |
| dry_A83_rainbow  | 196           | 0.0115       | 0.3830       | PASS            | 27.27                                |

Q-table coverage was 100% intersection on both fixtures (no history /
hand-string conversion misses); the gauntlet evaluated every cell both Brown
and our Rust DCFR visited.

## Verdict

The gauntlet correctly verifies the Nash-invariance hypothesis: at the
load-bearing depth=0 layer EV(action) agrees to within `0.02 BB at p75` and
`~1 BB at max` between Brown and our Rust DCFR, while strict per-cell σ parity
on these same fixtures FAILS at deep-cap indifference manifolds (documented in
PR 50 and `docs/v1_6_1_*`). This is exactly the falsification-safe layer
that Nash-multiplicity acceptance
(`feedback_nash_multiplicity_acceptance.md`) predicts must hold: per Brown
2019 Thm 2 the EV of every action at every reachable infoset is unique across
all Nash of a 2-player constant-sum game, even when strategy probabilities
are not.

The test exercises the real engines on both sides — `_rust.solve_range_vs_range_rust`
at 2000 iters with `(α, β, γ) = (1.5, 0.0, 2.0)` against the Brown
`river_solver_optimized` C++ binary (x86_64 under Rosetta) at the same iter
count and matched hyperparameters. Not a mock. Both Q-walks share the same
Python HUNL tree under the canonical Brown utility convention (PR #78), so any
EV gap is purely σ-driven.

Numbers match the PR #98 commit message baseline within noise (K72 p75 0.018,
max 1.04; A83 p75 0.012, max 0.38) — confirming the gauntlet is repeatable on
a fresh local run.

## Reproduction

```bash
STRICT_ACCEPTANCE=1 .venv/bin/pytest tests/test_ev_invariance_gauntlet.py \
    -v --tb=short -s
```

Wall time ~6 min on M-series arm64 host with the Brown binary running x86_64
through Rosetta. Iteration count and tolerances are pinned in the test
module; no override flags needed.
