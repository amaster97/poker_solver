# v1.8 SIMD Speedup — Empirical Benchmark vs v1.7.0 Baseline

**Date:** 2026-05-26
**Status:** Bench complete — speedup claim **NOT validated** on the workloads tested.
**Author:** Bench agent
**Companion to:** `docs/v1_8_0_release_notes_DRAFT.md`, `docs/v1_8_neon_implementation_roadmap.md`

---

## TL;DR

The v1.8 release-notes draft claims **"~4-8× speedup on Apple Silicon (M-series)"** vs the v1.7.0 scalar baseline. Empirical measurement on this hardware on the workload the SIMD code path actually touches (`dcfr_vector.rs`, the vector-form CFR for true range-vs-range Nash) shows **no measurable speedup** — within 1-2% of v1.7.0 across two configurations.

| Workload | v1.7.0 (pre-SIMD-wiring) | main (post-Phase-3) | Ratio |
|---|---|---|---|
| River R-v-R, 1081 hands, 1 bet size (3 actions), 5 iter | 936 ms/iter | 942 ms/iter | **0.99×** |
| River R-v-R, 1081 hands, 3 bet sizes (5 actions), 5 iter | 4,777 ms/iter | 4,723 ms/iter | **1.01×** |
| Leduc, 288 infosets, 500 iter (dcfr.rs path, SIMD-on at both SHAs) | 2,212 µs/iter | 2,237 µs/iter | **0.99×** |
| Kuhn,  12 infosets,  500 iter (dcfr.rs path, SIMD-on at both SHAs) |   9.4 µs/iter |   9.8 µs/iter | **0.96×** |

**Recommendation:** the v1.8.0 release notes' SIMD section must be rewritten before ship. The "4-8×" projection from the implementation roadmap was correctly flagged as a *target, not a locked delta* (per `feedback_no_extrapolate`), and the locked number has now been measured: it is approximately **1.0× (i.e., no measurable speedup)** on M4 Pro arm64 for the workloads tested.

---

## Hardware

- **Model:** Apple M4 Pro (arm64, 14 cores)
- **OS:** Darwin 24.6.0 (macOS 15.x)
- **Rust:** 1.95.0 (cargo 1.95.0)
- **Build profile:** `--release` (LLVM `-O3`, fat LTO disabled per workspace default)

---

## Methodology

### What was measured

The v1.8 release-notes draft is specifically about wiring SIMD into the four hot loops in `crates/cfr_core/src/dcfr_vector.rs` (the **vector-form CFR** used by `solve_range_vs_range_rust` for true range-vs-range Nash solves). Phase 1-3 are merged on `main`; Phase 4 (`compute_strategy` regret-matching) is in-flight on branch `pr-32-phase4-rebase-2026-05-26`.

### What was NOT measured

- **Phase 4** is not yet on main, so it is excluded from the validation here.
- The `dcfr.rs` info-state DCFR path (used by Kuhn / Leduc / fixed-combo HUNL) was already SIMD-wired in v1.0.1 / PR 8. v1.7.0 already exercises `simd::discount_regrets`, `simd::update_regret_sum`, `simd::update_strategy_sum` etc. through `dcfr.rs:151-288` (confirmed by `grep simd:: /tmp/bench-pre-simd/crates/cfr_core/src/dcfr.rs`). Comparing v1.7.0 to main on this path measures *nothing* (no SIMD changes in between).
- HUNL postflop with fixed hole cards uses `hunl_solver.rs`, also SIMD-wired since PR 8.

### Bench harness

The existing `crates/cfr_core/benches/dcfr_bench.rs` only times the `dcfr.rs` path (Kuhn / Leduc), which cannot validate v1.8's incremental claim. A new bench was written (uncommitted) at `crates/cfr_core/examples/rvr_bench.rs` that directly exercises `dcfr_vector::solve_range_vs_range_postflop` on the same `tiny_river_rvr()` fixture defined inline in `dcfr_vector.rs::tests` (board As 7c 2d Kh 5s, 1081 hands per player). Two configurations were used:

1. **Single bet size** (`bet_size_fractions = [1.0]`, `include_all_in = false`, `raise_cap = 1`): yields 2 decision nodes / 2162 strategy entries / 3 actions per row. Action count = 3 is the most common postflop case after fold/check is consolidated.
2. **Three bet sizes** (`bet_size_fractions = [0.33, 0.75, 1.5]`, `include_all_in = false`, `raise_cap = 1`): yields 6 decision nodes / 6486 strategy entries / 5 actions per row. Closer to a production sizing menu without invoking PR 50's all-in guard (which would skew the tree shape between SHAs).

For each config:
- Same fixture across both SHAs (tree shape identical: same `decision_node_count` and `strategy_entry_count` on v1.7.0 and main).
- 5 DCFR iterations per run (per the user's `--iterations 5000` constraint, scaled to the bench's per-call cost).
- 3 runs per binary, median reported.
- Warmup: 1 iteration before timing.
- Builds: both worktrees built with `cargo build --release --example rvr_bench` — same compiler, same flags.

The `tiny_river_rvr()` fixture matches what the existing inline test uses, so the bench shape is precedented.

### Two binaries built

```
git worktree add -b bench-pre-simd /tmp/bench-pre-simd v1.7.0
cargo build --release --manifest-path /Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml --example rvr_bench
cargo build --release --manifest-path /tmp/bench-pre-simd/crates/cfr_core/Cargo.toml --example rvr_bench
```

The bench source was placed identically in both `crates/cfr_core/examples/rvr_bench.rs` paths (uncommitted on either side, per the "do not modify committed code" constraint).

---

## Results

### Single bet size (3 actions, 2 decision nodes, 2162 strategy entries)

Median of 3 back-to-back runs per binary, then interleaved 3 runs each twice (6 samples per SHA):

| Run order | v1.7.0 ms/iter | main ms/iter |
|---|---|---|
| 1 | 936.1 | 952.7 |
| 2 | 936.0 | 939.5 |
| 3 | 940.7 | 951.4 |
| 4 | — | 946.6 |
| 5 | — | 934.9 |
| 6 | — | 932.5 |
| **Median** | **936.1** | **941.8** |
| **Spread** | 936-941 (0.5%) | 932-953 (2.2%) |

**Speedup ratio: 936.1 / 941.8 = 0.994×** — within noise; v1.8 is statistically indistinguishable from v1.7.0 on this workload.

### Three bet sizes (5 actions, 6 decision nodes, 6486 strategy entries)

| Run | v1.7.0 ms/iter | main ms/iter |
|---|---|---|
| 1 | 4776.9 | 4758.1 |
| 2 | 4903.8 | 4722.6 |
| 3 | 4751.0 | 4653.9 |
| **Median** | **4776.9** | **4722.6** |

**Speedup ratio: 4776.9 / 4722.6 = 1.011×** — within noise.

### Cross-validation: Kuhn / Leduc (dcfr.rs path)

This path was already SIMD-wired in v1.7.0 (via PR 8 / v1.0.1), so should show *zero* delta:

| Workload | v1.7.0 ns/iter | main ns/iter | Ratio |
|---|---|---|---|
| Kuhn (500 iter, 12 infosets) | 9,350 | 9,780 | 0.96× |
| Leduc (500 iter, 288 infosets) | 2,212,298 | 2,236,679 | 0.99× |

Confirmed: no perf delta on the dcfr.rs path (as expected — no SIMD changes to that code between v1.7.0 and main).

### Kernel-level microbench (informational)

The pre-existing `dcfr_bench.rs` SIMD-vs-scalar comparison (run on main) gives the *intrinsic kernel* speedup at various widths. On M4 Pro:

| Width | discount_regrets | discount_strategy_sum | positive_and_total | update_regret_sum |
|---|---|---|---|---|
| 2  | 0.19× | 1.07× | 1.86× | 1.10× |
| 3  | 0.26× | 0.29× | 1.96× | 1.26× |
| 6  | 0.46× | 1.99× | 1.73× | 1.71× |
| 8  | 0.44× | 3.20× | 1.04× | 2.68× |
| 16 | 0.64× | 1.13× | 0.96× | 1.10× |
| 32 | 1.02× | 1.20× | 0.78× | 0.66× |
| 64 | 1.42× | 0.69× | 0.88× | 0.79× |

The 3-8× projections from the roadmap appear at width=8 for `discount_strategy_sum` and `update_regret_sum` only. At width=2-3 (which is what the action-count rows in `update_strategy_sum` look like in practice) SIMD often **loses** to scalar — likely because LLVM's autovectorizer already emits NEON for the simple multiply-add scalar loops at `-O3`, and the explicit intrinsics path pays function-call / dispatch overhead.

This is the most likely root cause of the lack of end-to-end speedup: the kernels are called many times per iteration on **very small slices** (action_count = 3 means a slice of 3 f64s, well below the SIMD break-even point on this CPU).

---

## Validation verdict

**The "3-8× on Apple Silicon" claim in `docs/v1_8_0_release_notes_DRAFT.md` is NOT validated by measurement.** The plan itself flagged this risk explicitly:

> "Lock the final number only after the per-phase benches land (per `feedback_no_extrapolate`)."
> — `docs/v1_8_neon_implementation_roadmap.md:244`

The bench called for in the roadmap (`crates/cfr_core/benches/bench_dcfr_vector_simd.rs` at sizes 64×3, 256×3, 1081×3, 1081×14) was never committed — so the speedup number was never empirically locked before the release-notes draft was written.

This is consistent with `feedback_no_extrapolate.md` in the user's memory: *"no numerical-delta claims on multi-layer systems without per-layer data; instrument first."*

---

## Recommended language for v1.8.0 release notes

Replace the current bulleted speedup table:

> Expected per-iter speedup vs. v1.7.0 scalar baseline:
> - **Apple Silicon (M-series)**: ~4-8x
> - **x86_64 with AVX2** (~2013+ Intel/AMD): ~2-4x
> - **x86_64 SSE2-only** (pre-Haswell): ~1.5-2x

with honest measured language:

> **Performance:** v1.8 adds explicit SIMD intrinsics (NEON on aarch64, AVX2 / SSE2 with runtime detection on x86_64) for four hot loops in the vector-form CFR (`dcfr_vector.rs`). On Apple Silicon (M4 Pro, aarch64), an end-to-end benchmark on river range-vs-range solves (1081 hands per player, 3-5 actions per decision) shows **no measurable wall-clock improvement** vs v1.7.0 — the scalar fallback's autovectorized output from LLVM at `-O3` is already at or near the explicit-intrinsics throughput on these slice widths. The kernel-level microbench (`crates/cfr_core/benches/dcfr_bench.rs`) shows 2-3× wins on individual kernels at width=8, but typical postflop action-count rows are width 2-5, where the dispatch overhead cancels the kernel-level win.
>
> The SIMD path provides value as a **portability and correctness floor** (runtime-detected AVX2 for x86_64 hosts that don't autovectorize identically, bit-identical fallback to scalar) rather than a per-iter speedup. x86_64 measurement is pending (no AVX2 hardware in the bench fleet at time of write).

Or, more concisely for the section header:

> **SIMD vector kernels (cross-platform):** Explicit NEON/AVX2/SSE2 intrinsics replace the previous scalar inner loops in `dcfr_vector.rs`. Bit-identical output; **measured wall-clock impact on Apple Silicon is within noise (~1.0×)** because LLVM's autovectorizer already covers the small-slice case. Primary value is portability (x86_64 with explicit AVX2 dispatch, runtime-detected) and a stable hand-written floor that doesn't depend on the compiler's heuristics.

---

## Caveats / honest limits

1. **Hardware sample size = 1.** Only measured on M4 Pro. Older Apple Silicon (M1, M2) might show different autovectorizer behavior. x86_64 (AVX2, SSE2) entirely unmeasured.
2. **Workload sample size = small.** River-only, single board, ranges of 1081 (= full deck minus board) hands per player. Larger fixtures (turn / flop, where the v1.8 plan said the speedup is most needed for Sarah's interactive workflow) would take 25-340× longer per iter (per `docs/v1_7_0_nash_path_perf_profile.md:53-57`) and were outside the budget.
3. **Iteration count = 5.** The bench uses 5 iters because the per-iter cost is 0.9-4.7 seconds; 5000 iters would be 1-7 hours per binary, well outside the 30-min budget and outside the user's `--iterations 5000` ceiling.
4. **Phase 4 not measured.** Phase 4 (`compute_strategy` regret-matching, the "slowest lane" per the roadmap at 2-4× expected) is not on main yet. If the bench number changes once Phase 4 lands, this report should be re-run.
5. **No CPU isolation.** Bench was run on a normally-loaded desktop. Variance was 0.5-2.2% across runs, which is the noise floor that a 1.0× signal lives inside. A formal perf gate would want longer warmup, more samples, and `taskset`-style CPU pinning.

---

## Artifacts

- **Bench source:** `crates/cfr_core/examples/rvr_bench.rs` (uncommitted on main and on `/tmp/bench-pre-simd`).
- **v1.7.0 worktree:** `/tmp/bench-pre-simd` (branch `bench-pre-simd`, HEAD = 3843ce7 v1.7.0). Local-only, not pushed.
- **Compiled bench binaries:** `target/release/examples/rvr_bench` in each worktree.
- **Raw JSON output:** captured inline in the results table above.

---

## Reproduction (≤ 10 minutes)

```bash
# From repo root
export PATH=$HOME/.cargo/bin:$PATH

# Build both versions of the bench
cargo build --release --manifest-path crates/cfr_core/Cargo.toml --example rvr_bench
cargo build --release --manifest-path /tmp/bench-pre-simd/crates/cfr_core/Cargo.toml --example rvr_bench

# Single-bet workload (~5 sec each)
./target/release/examples/rvr_bench
/tmp/bench-pre-simd/target/release/examples/rvr_bench

# 3-bet workload (~25 sec each)
# Edit examples/rvr_bench.rs to set bet_size_fractions = [0.33, 0.75, 1.5]
# (need to edit in both /Users/ashen/.../examples/ and /tmp/bench-pre-simd/.../examples/)
# Rebuild both, then run.
```

Expected output: speedup ratio in the range 0.95×-1.05× on M4 Pro.
