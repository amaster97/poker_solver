# EV-Invariance Gauntlet — Phase 1 Baseline (2026-05-27)

**Status:** Implementation landed. Baseline numbers below; gates calibrated per `tests/test_ev_invariance_gauntlet.py`.

**Cross-refs:** `docs/ev_invariance_sanity_gauntlet_design_2026-05-27.md` (design), `feedback_nash_multiplicity_acceptance.md` (deep-cap multiplicity), `feedback_reframed_gate_masks_bugs.md` (layer-disaggregated reporting), `feedback_brown_convention_adopt.md` (canonical convention this gauntlet validates).

---

## TL;DR

At 2000 DCFR iters with matched hyperparameters on the canonical multiplicity fixtures (dry_K72_rainbow, dry_A83_rainbow), the EV-of-action invariance check **PASSES at depth=0 (true root)** with substantial headroom on both gates:

| Fixture | depth=0 p75 \|Δ\| | depth=0 max \|Δ\| | depth ≥ 1 max \|Δ\| | Verdict |
|---|---|---|---|---|
| dry_K72_rainbow | 0.018 BB (gate: ≤ 0.10) | 1.04 BB (gate: ≤ 1.50) | 29.6 BB (informational) | PASS |
| dry_A83_rainbow | 0.012 BB (gate: ≤ 0.10) | 0.38 BB (gate: ≤ 1.50) | 27.3 BB (informational) | PASS |

This confirms the design doc's central claim: **EV-of-action is invariant at the load-bearing depth=0 layer where strict per-cell σ parity FAILS** on the same fixtures (PR 50 documented σ p75 ≈ 0.4 — 0.6 on these spots).

---

## What the gauntlet asserts

For each (player, hand, action) cell at depth=0 (true root, history=""), compute:

```
Q_solver(I, a) = E[u_p | take action a at infoset I, then play σ_solver thereafter,
                       averaged over opponent's hand under spot's range]
```

The check: |Q_brown(I, a) − Q_ours(I, a)| should be small per Nash invariance (Brown 2019 Thm 2). Two gates:

- **p75 ≤ 0.10 BB** — load-bearing aggregate gate. Catches convention bugs (which would produce >> 0.10 BB at p75 because every cell's terminal utility would shift).
- **max ≤ 1.50 BB** — outer sanity bound. Allows Nash-multiplicity propagation on a small number of outlier cells; convention bugs would push max to 5-20+ BB.

Both EVs are computed by walking the SAME Python game tree under each solver's σ — the only source of divergence is σ at decision nodes.

---

## Depth-disaggregated empirical numbers (2000 iters, 2026-05-27)

### dry_K72_rainbow

```
Q-table sizes: brown=4730, ours=4730, intersection=4730 (100.0%)
depth=0 cells: 220
  |Δ| max:    1.0413 BB (gate: <= 1.50 BB)  → PASS
  |Δ| p95:    0.4519 BB
  |Δ| p75:    0.0183 BB (gate: <= 0.10 BB) → PASS
  |Δ| median: 0.0026 BB
  Top 5 worst:
    |Δ|=1.0413 BB infoset='5cAc|...|r|' action_idx=0   (A5s, check action)
    |Δ|=0.9930 BB infoset='5hAh|...|r|' action_idx=0
    |Δ|=0.9234 BB infoset='9cKc|...|r|' action_idx=3   (K9s, all-in)
    |Δ|=0.9145 BB infoset='9hKh|...|r|' action_idx=3
    |Δ|=0.9139 BB infoset='9dKd|...|r|' action_idx=3

depth ≥ 1 cells: 4510 (informational, not gated)
  |Δ| max:    29.5657 BB
  |Δ| p75:    0.1854 BB
  |Δ| median: 0.0000 BB
```

### dry_A83_rainbow

```
Q-table sizes: brown=6039, ours=6039, intersection=6039 (100.0%)
depth=0 cells: 196
  |Δ| max:    0.3830 BB (gate: <= 1.50 BB)  → PASS
  |Δ| p95:    0.1404 BB
  |Δ| p75:    0.0115 BB (gate: <= 0.10 BB) → PASS
  |Δ| median: 0.0032 BB
  Top 5 worst:
    |Δ|=0.3830 BB infoset='8s8d|...|r|' action_idx=0   (88, check)
    |Δ|=0.3299 BB infoset='KsKc|...|r|' action_idx=1   (KK, bet-0.5x)
    |Δ|=0.3299 BB infoset='KdKc|...|r|' action_idx=1
    |Δ|=0.3291 BB infoset='KhKc|...|r|' action_idx=1
    |Δ|=0.2543 BB infoset='KsKh|...|r|' action_idx=1

depth ≥ 1 cells: 5843 (informational, not gated)
  |Δ| max:    27.2663 BB
  |Δ| p75:    0.8941 BB
  |Δ| median: 0.0000 BB
```

---

## Why depth ≥ 1 isn't gated (Phase 1)

Empirically, depth=1+ EV deltas reach 9-30 BB even at 2000 iters. This is **NOT a Nash-invariance violation** but a manifestation of imperfect deep-cap convergence:

1. At deep facing-bet nodes (depth 2-3+), neither solver has fully converged at 2000 iters — Brown's σ at e.g. `5h5d|...|r|xb1500A` is `[0.5, 0.5]` (50/50 call/fold), ours is `[0.148, 0.852]` (mostly call). Both are NOT-YET-Nash (calling 50% with 5-pair facing all-in on K72J4 board is a clear mistake by Brown's solver at 2000 iters; calling 85% by ours is also too loose).
2. When we compute Q at depth=1 by walking the tree under σ, the depth=2-3 σ differences propagate up because the EV at depth=1 averages over downstream paths weighted by σ.
3. The TRUE root (depth=0) is shielded from this effect by the (P0 hand, P1 hand) aggregation: averaging Q across thousands of valid pairs smooths out per-cell deep-cap noise.

**Interpretation:** Phase 1 of the gauntlet validates the canonical convention + Brown ↔ ours tree-construction agreement at the root. Deep-cap convergence is a separate axis (best diagnosed via exploitability vs iters), out of scope for this gauntlet.

---

## What this gauntlet catches that strict-σ misses

Per `feedback_nash_multiplicity_acceptance.md`: strict per-cell σ parity fails on K72/A83 because Brown and ours land on different points of the deep-cap indifference manifold (both Nash, just non-unique). The σ gate flags this as a FALSE POSITIVE.

The EV gauntlet at depth=0 correctly identifies these as PASS (both solvers reached the SAME Nash value at the root, regardless of which point on the manifold they picked). At the same time, it would FAIL on:

- **Convention bug** — e.g., legacy "rust" convention would shift terminal utility by a constant per leaf, producing p75 |Δ| ≈ 5-20 BB across the board (well above the 0.10 BB gate).
- **Regret update bug** — would distort σ early, propagating to Q.
- **Wrong tree** — e.g., missing an action at root would produce systematic Q shifts.

So the gauntlet is genuinely orthogonal to strict-σ: it accepts Nash-multiplicity divergence (false-positive-clean) but catches algorithmic / game-definition bugs (true-positive-intact).

---

## Runtime

- Brown solve: ~30 s per spot (2000 iters, M-series Mac)
- Rust solve: ~30 s per spot (2000 iters)
- Q aggregation (2 strategies × ~2500 hand-pairs × ~30-node tree per pair): ~30-60 s per spot
- **Total**: ~2-3 minutes per spot; ~5 minutes for both fixtures

Marked `@pytest.mark.slow` + `@pytest.mark.parity_noambrown` (per `pyproject.toml` opt-in markers).

---

## Phase 2 (proposed, not in this PR)

1. **Add Q52 + clean low-depth fixture** for sanity-on-the-gauntlet (depth=0 should agree to 0.01 BB on a converged shallow fixture).
2. **Relative-tolerance band** (design doc Q1c): `EV_TOL = max(0.1 BB, 0.01 × pot_size_bb)` to make the gauntlet scale-invariant for non-stack=9500 fixtures.
3. **Deep-layer convergence study**: at what iter count does depth=1+ EV agree to 0.5 BB? Should be tractable at 10-50k iters; documents the gap between "PR 53 4-layer σ gate" convergence and "true Nash" convergence.
