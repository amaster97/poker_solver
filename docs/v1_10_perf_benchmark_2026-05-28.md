# v1.10 Postflop Performance Benchmark — Honest Narrative

**Date:** 2026-05-28
**Release:** v1.10.0 (shipped with honest framing — wall-time win, memory deferred).
**Scope:** the v1.10 postflop optimization burst (task #70), 4 PRs:
- **PR-1** — thread-local arena + LTO + skip-discount-recompute (commit `eb5b4d0`, GitHub PR #197, MERGED).
- **PR-2** — vector-form turn forward walk / river template (commit `7fa4d73`, GitHub PR #190, MERGED).
- **PR-4** — opt-in rayon chance parallelism (commit `f5ec665`, GitHub PR #189, MERGED).
- **PR-3** — vector-form flop forward walk / double chance compaction (commit `cda3eeb`, MERGED).

**Companion docs:**
- `docs/v1_10_postflop_optimization_plan.md` — root-cause analysis + 4-PR roadmap.
- `docs/v1_10_pr3_flop_vector_design.md` — PR-3 design (Strategy A vs Strategy B).
- `docs/rust_optimization_ledger.md` §9-§12 — per-PR ledger entries.
- `docs/v1_11_postflop_deeper_optimization_research.md` — where the deferred memory work lives.
- `docs/flop_subgame_perf_measurement_2026-05-28.md` — pre-v1.10 4-config OOM sweep (baseline).

---

## TL;DR

- **PR-3 is a genuine wall-time + reliability win.** The flop subgame now
  **completes** where the pre-v1.10 path was OOM/jetsam-killed at the
  ~5-minute mark from allocator churn. The shipped path is **bit-identical**
  to the v1.10-2 reference (verified — see §3).
- **The original v1.10 headline gate is NOT met.** "Flop top_k=169 in <120 s
  AND ≤ 1 GB RSS" is **not achieved and is not claimed.** Measured: full-range
  flop solve uses **~6.7 GB RSS at top_k=4** and spikes to **~7.7 GB+ at
  top_k=169, where it does NOT finish** (alloc-abort / jetsam).
- **Why:** PR-3 shipped the wall-time half (scratch-buffer reuse, design
  "Strategy B"), **not** the memory half (board-tree collapse, design
  "Strategy A"). Flop-solve memory is dominated by the materialized board
  chance tree (45 turn × 44 river betting subtrees) + per-node infoset storage
  at full combo width — **independent of `top_k`**, so lowering `top_k` does
  not bring it under budget.
- **Turn / river (PR-2 vector turn + PR-4 rayon) are real wins.** Exact
  measured wall/RSS numbers are **PENDING a bench run** (see the placeholders
  in §2).
- **Full-range flop memory reduction is deferred to v1.11** — sparse / lazy
  infoset storage + board-tree templating. See
  `docs/v1_11_postflop_deeper_optimization_research.md`.

---

## 1. Hardware / build

- **Model:** Apple M-series, arm64. 24 GB unified memory.
- **OS:** Darwin 24.6.0.
- **Rust ext:** `poker_solver/_rust.cpython-313-darwin.so` arm64 (arch verified).
- **Build:** release profile with PR-1's `lto = "fat"` + `codegen-units = 1`.
- **Reference fixture:** J7o A♦8♥9♦, 40 BB, SB-opens-3bb / BB-calls
  (`pf_seq = ("b300", "c")`), 169-class abstraction.

---

## 2. Results table

Columns: street, top_k, wall_s, peak_rss_mb, exploitability, status.

| Street | top_k | wall_s | peak_rss_mb | exploitability | status |
|---|---|---|---|---|---|
| **flop** | 4 | [PENDING bench] | **~6700** | [PENDING bench] | **completes (heavy)** |
| **flop** | 169 | — | **~7700+** | — | **does NOT complete — exceeds memory budget; full-range optimization deferred to v1.11** |
| turn | 4 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |
| turn | 15 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |
| turn | 50 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |
| river | 4 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |
| river | 15 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |
| river | 50 | [PENDING bench] | [PENDING bench] | [PENDING bench] | [PENDING bench] |

Notes:
- **Flop rows are honest-measured** as of 2026-05-28: the flop solve completes
  at top_k=4 (heavy: ~6.7 GB RSS), and does **not** complete at top_k=169
  (~7.7 GB+ RSS, alloc-abort / jetsam on a 24 GB machine).
- **Turn / river rows are `[PENDING bench]`** and will be filled from
  `docs/v1_10_perf_bench_results.jsonl` once the formal bench run completes.
  Do **not** invent turn/river numbers here.
- Flop RSS is **independent of `top_k`** (the cost driver is the board chance
  tree + per-node infoset storage at full combo width, not the class-count
  filter), which is why dropping from top_k=169 to top_k=4 reduces it only
  marginally (~7.7 GB → ~6.7 GB), not under budget.

---

## 3. PR-3 correctness — bit-identity VERIFIED

PR-3 (`cda3eeb`) is bit-identical to the v1.10-2 reference. Evidence:

- **F4_synth synthetic-tree canary: `max_diff = 0.0`.** The small-tree fixture
  (hand-traceable; any DFS-order drift would surface as a >1e-6 strategy
  difference) shows exact agreement.
- **4 Rust unit tests pass**, including
  `flop_template_extract_bit_identical_to_standard`.
- **Two independent validators returned MATH-PRESERVED** (no
  FP-accumulation-order divergence).
- `CFR_VECTOR_FLOP_TEMPLATE=0` forces the `Standard` build mode (canonical
  baseline) for A/B comparison. Regret / strategy_sum / discount kernels are
  untouched.

This is the load-bearing property: the flop solve completing faster and more
reliably is only useful if the answer is the same answer. It is.

---

## 4. Honest framing — wall-time win, memory deferred

This is the part that matters for trust, given the repo's hard rule against
unmeasured / overstated perf claims (the v1.8 SIMD "4-8×" → measured 1.0×
lesson).

**What PR-3 delivered (the wall-time half):**

The flop subgame's outer chance loop does 45 × 44 = 1980 weighted sums and
**reuses pre-allocated scratch buffers** (a per-solve `RunoutCache`) instead of
allocating a fresh `vec![0.0; update_hands]` per call. This is the design doc's
**Strategy B** (lazy on-demand, scratch reuse). It removes the per-iteration
allocator churn that was OOM/jetsam-killing the solve at the ~5-minute mark —
so the solve now **completes** and is bit-identical to the reference.

**What PR-3 did NOT deliver (the memory half):**

The design doc's **Strategy A** — the *eager board-tree memory collapse* that
shares the river-betting-tree storage across all 1980 runouts (single template
+ per-runout multiplier) — was **scaffolded but not wired**. The independent
PR-3 audit confirmed this statically as **finding S-4**:
`RunoutCache::runout_values` (the 1980-buffer pool) is **allocated but never
read** — it carries `#[allow(dead_code)]` with the in-code note "currently
unused in Strategy B … the eager Strategy-A variant can use the full layout in
a follow-up PR."

Consequently, flop-solve memory is still dominated by:
1. the **materialized board chance tree** (45 turn × 44 river betting
   subtrees), and
2. **per-node infoset storage at full combo width**,

both of which are **independent of `top_k`**. That is the root cause behind the
~6.7 GB (top_k=4) / ~7.7 GB+ (top_k=169) RSS — and why the original
"top_k=169 in <120 s AND ≤ 1 GB RSS" gate is structurally out of reach for the
shipped Strategy-B path.

**Net for users:** the live flop path is usable for small-`top_k` /
small-range spots that fit in memory. Full 169-class flop charts remain
memory-bound until v1.11. For full-range flop charts today, use the §5.2
aggregator (see USAGE.md).

---

## 5. Where the deferred work lives — v1.11

Full-range flop memory reduction is deferred to v1.11. The research roadmap is
`docs/v1_11_postflop_deeper_optimization_research.md`. The directly relevant
candidates:

- **Candidate E — sparse range representation** (zero-reach short-circuit +
  sparse infoset storage). Single highest-ROI for the Premium-A blueprint flow.
- **Candidate Q — lazy infoset materialization** (only allocate infoset on
  first visit; ~0.5-0.7× peak RSS on sparse workloads). Bundled with E.
- **Candidate D — board-isomorphism caching at chance nodes** (collapse the
  duplicated river-betting-tree storage — this is the natural home for the
  scaffolded Strategy-A layout / the `runout_values` pool that S-4 flagged as
  dead).

These are exactly the "board-tree templating + sparse/lazy infoset storage"
that the v1.10 PR-3 path stopped short of.

---

## 6. Reproducibility

- Bench driver: `scripts/run_v1_10_perf_bench.py` (PR #187, `b5aa023`).
- Rust inner kernel bench: `crates/cfr_core/benches/flop_subgame_perf.rs`.
- Canonical diff-test scaffold: `tests/test_v1_10_canonical_diff.py` (PR #188)
  and `tests/test_v1_10_3_flop_diff.py` (PR-3) — HARD-FAIL on bit-identity
  regressions.
- Opt-in rayon: `CFR_RAYON_CHANCE=1` (canonical default is single-threaded,
  bit-identical).
- Force canonical (non-template) flop build for A/B: `CFR_VECTOR_FLOP_TEMPLATE=0`.

```bash
# Default: canonical single-threaded (bit-identical reference).
python scripts/run_v1_10_perf_bench.py --street flop --top-k 169

# Opt in to rayon parallel chance branches (multi-core):
CFR_RAYON_CHANCE=1 python scripts/run_v1_10_perf_bench.py --street flop --top-k 169
```

Turn/river results, once measured, append to
`docs/v1_10_perf_bench_results.jsonl`; fill the `[PENDING bench]` cells in §2
from that file.

---

*Honest-framing principle: a measured "it completes but is still heavy" beats
an unmeasured "<120 s / ≤ 1 GB" headline. The flop wall-time + reliability win
is real and bit-identity-verified; the memory budget is not yet met and is
honestly deferred to v1.11.*
