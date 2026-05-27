# v1.8 NEON Vector Kernels — Implementation Roadmap

**Status:** Pre-implementation source-code scan (read-only).
**Date:** 2026-05-23
**Companion to:** `docs/pr_proposals/v1_8_neon_vector_kernels_spec.md`
**Source files scanned:** `crates/cfr_core/src/dcfr_vector.rs`, `crates/cfr_core/src/simd.rs`, `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240`.

This doc concretizes the four hot loops by quoting the actual scalar code, identifying the data layout, and mapping each to an existing PR 8 NEON pattern. Per `feedback_no_extrapolate`, speedup numbers are *targets per PR 8 calibration*, not locked deltas.

---

## Layout primer

`VectorInfosetData` (dcfr_vector.rs:78-87):
- `regret: Vec<f64>` — row-major `hand_count × action_count`, indexed `[h * action_count + a]`
- `strategy_sum: Vec<f64>` — same shape

`traverse` locals (dcfr_vector.rs:400, 420):
- `action_values: Vec<f64>` — **action-major** `[a * update_hands + h]` (matches Brown trainer.cpp:197)
- `node_values: Vec<f64>` — length `update_hands`
- `strategy: Vec<f64>` — **hand-major** `[h * action_count + a]` (matches trainer.cpp:188)

The shape mismatch between `action_values` (action-major) and `regret` (hand-major) is the load-bearing complication for Phases 2-3.

---

## Phase 1 — `VectorDCFR::discount` (lines 266-289)

### Scalar hot loop (dcfr_vector.rs:277-286)

```rust
for r in &mut info.regret {
    if *r > 0.0 {
        *r *= pos_scale;
    } else if *r < 0.0 {
        *r *= neg_scale;
    }
}
for s in &mut info.strategy_sum {
    *s *= strat_scale;
}
```

### Layout & op
Pure elementwise over flat `hand_count × action_count` buffer. Shape is irrelevant — both ops are 1D over `len = hand_count * action_count`. The outer `for tt in last_discount_iter+1..=t` (line 270) just recomputes scales per missed iter; the inner loops are the cost.

### SIMD strategy
**Direct delegation.** Both `simd::discount_regrets` (simd.rs:395-405) and `simd::discount_strategy_sum` (simd.rs:408-417) already implement the exact per-element semantics with the NaN-preserving sign-conditional mask (simd.rs:221-250 `discount_regrets_neon` via `vcgtq_f64` + `vbslq_f64`). No new intrinsics needed — just call the existing public dispatches on the flat slices.

### Expected speedup
**3-5×** on the inner kernel — matches PR 8's measured win on the scalar-shape `discount_regrets`. The vector buffer is *larger* (`hand × action` vs `action`), so lane utilization stays saturated.

### Complexity / risk
**Lowest — trivial.** Two call-site swaps. Bit-parity is preserved because the existing kernels are already bit-exact diff-tested (simd.rs:482-502). No new test scaffolding beyond reusing existing parity tests on larger sizes.

### Estimated dev time
**0.5-1 day** including extending the parity test fixture to `hand_count × action_count` sizes (1×2, 8×3, 64×4, 1081×14).

---

## Phase 2 — Regret update block (dcfr_vector.rs:444-450)

### Scalar hot loop

```rust
for h in 0..update_hands {
    let offset = h * action_count;
    let base = node_values[h];
    for a in 0..action_count {
        let delta = (action_values[a * update_hands + h] - base) * regret_weight;
        info.regret[offset + a] += delta;
    }
}
```

### Layout & op
- `regret[h * action_count + a]` — hand-major, contiguous on inner loop `a`.
- `action_values[a * update_hands + h]` — **action-major**, *strided* on inner loop `a` (stride = `update_hands`).
- `base = node_values[h]` — scalar broadcast per outer iter.

### SIMD strategy
**Pre-transpose + delegate** (spec §5 option (b), preferred over strided gather since NEON lacks native gather).

1. Allocate `action_values_T: Vec<f64>` of size `update_hands * action_count` (hand-major).
2. Transpose `action_values[a * update_hands + h] → action_values_T[h * action_count + a]` once, before the per-hand loop. Transpose can itself be vectorized in 2×2 blocks via `vld2q_f64` / `vst2q_f64` or `vtrn1q_f64` / `vtrn2q_f64`.
3. Per-hand: call `simd::update_regret_sum(row_regret, row_av_T, node_values[h], regret_weight)` (simd.rs:446-459). PR 8's two-rounding (vmul + vadd, no FMA) is already bit-exact diff-tested (simd.rs:539-550).

Note: `regret_weight = 1.0` in DCFR (line 438), so the `update_regret_sum` call collapses to `regret += (av - node)` exactly matching Brown's trainer.cpp:216-217 semantics.

### Expected speedup
**3-6×** on the inner kernel. Per-hand row width = `action_count` (2-14); SIMD utilization is moderate on action_count=2 (1 NEON load), excellent on action_count ≥ 8. Transpose overhead amortizes since the regret update + strategy-sum update both consume the transposed view (Phase 3 reuses it).

### Complexity / risk
**MEDIUM.** Two failure modes:
- **Transpose correctness.** Pre-transpose adds an `O(hand × action)` pass; verify index math with unit tests before wiring.
- **Bit-parity.** The transpose itself is a memcpy — no rounding. The regret update reuses the bit-exact PR 8 kernel. Diff test should pass at `to_bits()` equality.

### Estimated dev time
**2-3 days** — transpose helper, per-hand call-site rewrite, parity test extension.

---

## Phase 3 — Strategy-sum update block (dcfr_vector.rs:454-463)

### Scalar hot loop

```rust
for h in 0..update_hands {
    let weight = reach_p[h] * avg_weight;
    if weight == 0.0 {
        continue;
    }
    let offset = h * action_count;
    for a in 0..action_count {
        info.strategy_sum[offset + a] += weight * strategy[offset + a];
    }
}
```

### Layout & op
- `strategy_sum[h * action_count + a]` — hand-major, contiguous on inner loop.
- `strategy[h * action_count + a]` — same shape, contiguous.
- `weight = reach_p[h] * avg_weight` — scalar broadcast per outer iter; `avg_weight = 1.0` in DCFR (line 439).

**No layout mismatch — already aligned for SIMD.** This is the cleanest of the three update kernels.

### SIMD strategy
**Direct delegation.** Per-hand row already contiguous: `simd::update_strategy_sum(row_strategy_sum, row_strategy, weight)` (simd.rs:463-471) maps exactly. Bit-parity guaranteed by PR 8's two-rounding semantics (simd.rs:553-562).

The `weight == 0.0` short-circuit at line 456-458 is worth preserving (skip the call entirely) — it's a meaningful pruning when `reach_p[h] == 0` (impossible hand combos after blocker exclusion).

### Expected speedup
**3-6×** on the inner kernel. Same width as Phase 2; bit-exact.

### Complexity / risk
**LOW.** No transpose, no shape change. Just thread the existing kernel through a per-hand loop. The `weight == 0` short-circuit is one branch outside the SIMD path.

### Estimated dev time
**1-1.5 days** — call-site rewrite + parity test extension.

---

## Phase 4 — `compute_strategy` (lines 207-232)

### Scalar hot loop

```rust
for h in 0..hand_count {
    let offset = h * action_count;
    let mut normalizing = 0.0_f64;
    for a in 0..action_count {
        let r = info.regret[offset + a];
        if r > 0.0 { normalizing += r; }
    }
    if normalizing > 0.0 {
        for a in 0..action_count {
            let r = info.regret[offset + a];
            out[offset + a] = if r > 0.0 { r / normalizing } else { 0.0 };
        }
    } else {
        let prob = 1.0 / action_count as f64;
        for a in 0..action_count { out[offset + a] = prob; }
    }
}
```

### Layout & op
Per-hand row (`action_count` wide):
1. Positive-clamp + sum: `out[a] = max(regret[a], 0)`, `total = Σ out[a]`.
2. Normalize: `out[a] /= total` if `total > 0`, else uniform `1/action_count`.

### SIMD strategy
**Direct delegation** — the per-hand row is already exactly the input shape PR 8's regret-matching kernels expect:
- `simd::positive_regrets_and_total(row_regret, row_out)` (simd.rs:421-429) does the clamp + sequential sum (bit-exact total; simd.rs:565-577).
- `simd::normalize(row_out, total)` (simd.rs:434-442) does the per-lane `vdivq_f64` (bit-exact, not multiply-by-reciprocal).

The "sequential sum, not horizontal SIMD sum" discipline at simd.rs:155-168 is critical: pairwise reduction would drift ULP and the converged strategy diverges past `STRATEGY_ATOL=1e-4`. The existing kernel already handles this.

### Expected speedup
**2-4×** on the inner kernel — *the slowest lane of the four*. Two factors limit gain:
- `vdivq_f64` (NEON division) is ~6-8× slower than `vmulq_f64` and not pipelined. Per-lane normalize is the bottleneck.
- `action_count` (2-14) is small; SIMD utilization is moderate, especially at action_count=2 (one 2-lane load).

Brown's reference at trainer.cpp uses the same regret-matching shape; we are not deviating from the math.

### Complexity / risk
**LOW-MEDIUM.** Same dispatch pattern as Phase 3. Risk is in the speedup ceiling, not correctness.

### Estimated dev time
**1-2 days** — call-site rewrite + parity test extension. Add a microbench at action_count ∈ {2, 3, 8, 14} to verify the speedup actually materializes (per `feedback_no_extrapolate`, the 2-4× projection needs measurement).

---

## Cross-phase: validation strategy

Inherited from PR 8 (simd.rs:482-577):

1. **In-source bit-parity tests** — each kernel has a `*_matches_scalar` test using `to_bits()` equality (or ULP ≤ 1 where the spec explicitly allows it, e.g. clamp-sum total). Extend the existing tests in `simd.rs` to cover the new vector-shape sizes.

2. **New integration test** — `crates/cfr_core/tests/test_dcfr_vector_simd.rs` (spec §6): randomized `hand_count × action_count ∈ {1×2, 8×3, 64×4, 1081×14}`, scalar vs SIMD path, `to_bits()` parity on per-lane outputs.

3. **End-to-end diff test** — `tests/test_range_vs_range_rust_diff.py` must still pass at `STRATEGY_ATOL = 1e-4` after wiring.

4. **W2.1 retest** — turn 8-class × 500-iter Nash solve in ≤ 5 min wall-clock (Sarah's persona budget; spec §4 acceptance criterion #3).

5. **Per-phase criterion bench** — `crates/cfr_core/benches/bench_dcfr_vector_simd.rs` at sizes 64×3, 256×3, 1081×3, 1081×14. Per-phase measurement gates the speedup claim.

---

## Risk areas summary

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1 (discount) | None — direct delegation | Existing parity tests cover it |
| 2 (regret) | Transpose correctness; alloc cost | Unit-test transpose; amortize over Phase 3 |
| 3 (strat_sum) | None | Reuse Phase 2's transposed view |
| 4 (compute_strategy) | Speedup ceiling (`vdivq_f64`) | Bench-first; accept 2-4× as floor |

**Universal:** bit-parity drift past `STRATEGY_ATOL=1e-4`. PR 8 already pinned this — sequential sum (simd.rs:202-207), two-rounding vmul+vadd (no FMA; simd.rs:274-283), per-lane vdiv (not reciprocal; simd.rs:344-346). Adhere to all three.

---

## Total dev time estimate

- Phase 1: **0.5-1 day**
- Phase 2: **2-3 days** (transpose is the swing factor)
- Phase 3: **1-1.5 days**
- Phase 4: **1-2 days**
- Validation + bench scaffolding (shared): **1-2 days**
- W2.1 retest + parity-test runs + any debugging: **1-2 days**

**Total: ~7-12 dev days (1-2 weeks focused).** Matches spec §7 estimate of "1-2 weeks of focused work."

---

## Confidence in 4-8× speedup target

**MED-HIGH for the geometric-mean across kernels.** Per-phase calibration:
- Phase 1: 3-5× (high confidence — direct PR 8 reuse)
- Phase 2: 3-6× (medium — transpose overhead is the variable)
- Phase 3: 3-6× (high — direct PR 8 reuse, contiguous layout)
- Phase 4: 2-4× (medium-low — division-bound)

The 4× floor is plausible across all kernels. The 8× ceiling requires the vector-shape working-set advantage (larger `hand × action` buffers → better lane utilization than PR 8's `action`-only buffers) to compound favorably. **Lock the final number only after the per-phase benches land (per `feedback_no_extrapolate`).**
