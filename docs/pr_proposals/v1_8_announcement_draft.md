# v1.8 Release Announcement — Draft

**Status:** Pre-staging draft. v1.8 has NOT shipped. Do NOT publish.
**Date drafted:** 2026-05-23
**Trigger to publish:** v1.8 ships with NEON vector kernels + notarized universal `.dmg` (Apple Developer enrollment dependent).
**Source references:**
- `docs/oss_competitor_comparison_2026-05-23.md` §6 (positioning)
- `docs/v1_7_0_nash_path_perf_profile.md` (measured Nash path perf)
- `docs/v1_8_neon_implementation_roadmap.md` (4 phases, 7-12 dev days)
- `docs/pr_proposals/v1_8_neon_vector_kernels_spec.md` (spec)

---

## 1. Twitter / X thread (3 tweets)

**Tweet 1 — hook**

> poker_solver v1.8 is out. Notarized universal .dmg + NEON vector kernels — turn-fixture Nash solves now 4-8× faster on M-series. 🃏

**Tweet 2 — technical "how"**

> Four NEON kernels (discount / regret-update / strategy-sum / regret-matching) over the vector-shape DCFR hot loops. Bit-parity diff tests vs scalar fallback. Universal binary signed + notarized — double-click install, no Gatekeeper warning.

**Tweet 3 — install + link**

> `pip install -e .` from source or grab the .dmg from the release page. MIT-licensed, Python+Rust, HUNL postflop range-vs-range with both aggregator and joint-Nash entry points.
>
> github.com/[REPO]/releases/tag/v1.8.0

---

## 2. Hacker News post

**Title** (≤80 chars):

> poker_solver v1.8: NEON kernels, notarized .dmg, HUNL Nash 4-8× faster on M-series

**Body** (3 paragraphs):

poker_solver is an MIT-licensed HUNL postflop solver written in Python + Rust (PyO3). v1.8 ships two changes: (1) NEON SIMD kernels over the vector-form DCFR hot loops — `discount`, regret-update, strategy-sum update, and regret-matching — bringing turn-fixture range-vs-range Nash solves from ~10+ min down to under 5 min on an M-series Mac, and (2) a notarized universal `.dmg` so install is a double-click on both Intel and Apple Silicon, no Gatekeeper friction.

The kernel work follows the PR 8 pattern from v1.2.0: per-kernel scalar fallbacks, bit-parity diff tests at `to_bits()` equality (or ≤1 ULP where the math allows), sequential `f64` reduction (no FMA, no pairwise sums) to keep the differential test bar at `STRATEGY_ATOL = 1e-4` against the Python reference. The vector shape is `hand_count × action_count` row-major; the regret-update kernel does a one-shot transpose of action-major action-values once per traverse to enable contiguous SIMD loads.

What v1.8 does not fix: the flop interactive Nash budget. Per the v1.7.0 perf profile, street depth dominates cost — chance-node enumeration over turn × river runouts at every flop action node, multiplicatively, on top of an O(N²) per-leaf blocker check. SIMD shaves the per-iter constant but doesn't change the asymptotics. For flop spots under an interactive budget, use the aggregator path (`solve_range_vs_range`); the Nash path on flop is still research-grade / overnight. v1.9 candidate is EMD bucketing in the vector form (hand-dim 1081 → 64-256), which actually addresses the per-leaf cost. Repo + .dmg + USAGE.md: [link].

---

## 3. GitHub release notes (~500 words)

### What's new

- **NEON vector-shape SIMD kernels.** Four kernels in `crates/cfr_core/src/dcfr_vector_simd.rs` covering the `hand_count × action_count` row-major DCFR hot loops: `discount` (sign-conditional regret rescale + strategy-sum rescale), regret-update (`regret[h,a] += action_v[a,h] - node_v[h]` over a transposed action-values view), strategy-sum update (`strategy_sum[h,a] += reach_p[h] * strategy[h,a]`), and `compute_strategy` (per-hand positive-clamp + normalize). Bit-parity diff tests at sizes from `1×2` to `1081×14`. Scalar fallback retained on non-aarch64.
- **Notarized universal `.dmg`.** Apple-signed and notarized; universal2 binary (Intel x86_64 + Apple Silicon arm64). Double-click install on any Mac; no `xattr -d com.apple.quarantine` workaround needed. Replaces the prior arm64-only experimental build.
- **USAGE.md envelope update.** Performance envelope tables now reflect v1.8 measured numbers for `solve_range_vs_range_nash` on the Nash path.

### Performance

Measured on Apple M-series, K-Q-7 two-tone fixture, symmetric 750/750 pot, bet sizes (0.33, 0.75), raise_cap=2. Wall-clock per `solve_range_vs_range_nash` call:

| Fixture | v1.7.0 | v1.8.0 | Speedup |
|---|---|---|---|
| Turn, 8 classes × 500 iter | ~21 min (W2.1 Type D timeout, projected from 100-iter scaling) | **≤ 5 min** (W2.1 PASS target) | ~4-8× target |
| Turn, 4 classes × 100 iter | 92 s | (TBD per-bench) | per-bench measured |
| River, 8 classes × 500 iter | 3.8 s | (TBD per-bench) | smaller absolute gain |

Per-kernel criterion benchmarks (in `crates/cfr_core/benches/bench_dcfr_vector_simd.rs`) gate the speedup claim per phase. The four kernels' geometric-mean target is 4-8×; division-bound `compute_strategy` is the floor lane at 2-4×, contiguous strategy-sum and regret-update are the ceiling at 3-6×.

### Known issues

- **Flop on the Nash path is still not interactive.** Street depth dominates cost (chance-node enumeration multiplies across turn × river runouts at every flop action node). v1.8 SIMD shaves the per-iter constant; it does not change asymptotics. For flop spots under a ~5 min budget, use the aggregator path (`solve_range_vs_range`). The Nash path on flop is research-grade / overnight runs only at v1.8.
- **x86_64 SSE/AVX kernels not implemented.** M-series target only. Intel Macs run via the universal .dmg but fall back to the scalar Rust path for the four hot loops.
- **`compute_strategy` speedup ceiling.** `vdivq_f64` is not pipelined and ~6-8× slower than `vmulq_f64`. Per-lane normalize is the bottleneck on small `action_count` (2-3); SIMD utilization saturates only at action_count ≥ 8.

### What's next

- **v1.9 candidate (HIGH):** EMD bucketing in the vector form. Compresses hand dimension from 1081 → 64-256, brings the per-leaf O(N²) blocker check down by ~50×. This is the actual flop interactive viability work; SIMD alone does not get there.
- **v1.9+ candidates (LOWER):** PioSolver-format range parser (interop), compressed int16 regret storage with per-node f32 scale (~2-4× RAM cut), disk-backed checkpointing (slumbot pattern), bet-size DSL akin to postflop-solver's.
- **Explicitly not on the roadmap:** Deep CFR / NN value-net warm-start (training-corpus economics), multiway preflop (3-9p), GPU kernels.

---

## 4. Repo description one-liner

> MIT-licensed Python + Rust HUNL postflop solver. Range-vs-range aggregator + joint Nash, node locking, PySide6 GUI, NEON kernels, notarized universal .dmg.
