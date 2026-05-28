# v1.11 Postflop Deeper Optimization Research Roadmap

**Date:** 2026-05-28
**Status:** Research deliverable (read-only exploration).
**Source agent:** `abf2ced6405f24594` (Plan architect).
**Scope:** Optimizations deferred from v1.10 + new candidates surfaced during research.

## TL;DR

- **11 candidates evaluated** (5 deferred from v1.10 + 6 new).
- **Top 3 v1.11 picks**: Candidate E (sparse range, 2-10×), Candidate K (ε-reach tree pruning, 1.5-3×), Candidate D (board-iso chance caching, 1.5-3×). Bundled sweetener: H1 LTO + H2 PGO (1.15-1.30×, ~1-2 days).
- **Combined headline**: **6-25× over v1.10** on Premium-A flop top_k=169. Projects flop top_k=169 from v1.10's ~30-60s down to **5-15s** (conservative).
- **With opt-in f32**: another 1.5-2× kernel → **3-7s**. Bit-identical NOT preserved.
- **Highest risk**: Candidate I1 (f64 → f32). Mitigation: opt-in `CFR_F32_VECTOR=1` dual-path.
- **Total v1.11.0 engineering**: 18-25 days (top-3 + LTO/PGO); +7-10 days for f32 opt-in.

## Re-evaluation of v1.10 deferred candidates

### Candidate D — Board-isomorphism caching at chance nodes
- **v1.11 estimate**: 1.5-3× combined (less than v1.10 plan's 2-4× on subtree alone).
- Canonicalization machinery already shipped: `crates/cfr_core/src/abstraction.rs::canonicalize_board` + `poker_solver/abstraction/equity_features.py::canonicalize_for_suit_iso`.
- `from_suit_iso` stub at `crates/cfr_core/src/dcfr_vector.rs:981` was forward-declared.
- Effort: 5-7 days. Risk: MEDIUM (suit-asymmetric range fallback).

### Candidate E — Sparse range representation
- **v1.11 estimate**: 1.3-2.5× on Premium-A blueprint flows (sparse) — single highest-ROI for user-facing flow.
- Two variants:
  1. **Zero-reach short-circuit** (1 day, bit-identical) — extend skip-on-zero to `compute_strategy`, `update_regret_sum_vector`, `terminal_value_vector_cached` inner loops.
  2. **Sparse infoset storage** (5-7 days) — allocate regret/strategy_sum only for active combos.
- Ship #1 in v1.11.0; defer #2 to v1.11.x.

### Candidate H1+H2 — LTO + PGO
- **v1.11 estimate**: 15-30% combined on inner kernel.
- Cargo.toml currently has NO release profile customization.
- Effort: 1-2 days. Risk: LOW. **Ship as v1.10.1 patch** if reasonable.

### Candidate H3 — BLAS-backed kernels
- **DROP from v1.11.** Hot kernels are not GEMM-shaped (K=3-8 actions, BLAS overhead dominates).

### Candidate I1 — f64 → f32 (opt-in)
- **v1.11 estimate**: 1.5-2× kernel + 0.5× memory.
- Breaks every existing diff test → opt-in flag `CFR_F32_VECTOR=1`, separate test suite at 1e-5 EV tolerance.
- Effort: 7-10 days. Risk: HIGH.

## New candidates surfaced

### Candidate J — Public Chance Sampling (PCS)
- Already implemented at `crates/cfr_core/src/pcs.rs` but NOT wired into `dcfr_vector.rs`.
- **3-10× wall** at same exploitability target (after iter-count compensation).
- Forces β=0.5 (silently overrides user); bit-identical not preserved.
- Effort: 4-6 days. Risk: MEDIUM. **TIER 2 PICK** (defer to v1.11.x).

### Candidate K — ε-reach tree pruning at solve start
- Skip Decision nodes with multiplicative reach < ε before iterations begin.
- **1.5-3× on Premium-A** (concentrated blueprint reach).
- Slumbot 2019 does similar (prunes on regret, not reach).
- Effort: 4-6 days. Risk: MEDIUM. **TOP-3 PICK.**

### Candidate L — Bucket-based action abstraction
- Collapse near-identical bet sizes (33% vs 40% pot).
- **1.5-2× on production 5-bet menu.**
- Politically sensitive (user wary of action abstraction for postflop fidelity).
- **DEFER to v1.12.**

### Candidate M — Streaming chance enumeration
- **DROP.** Already implemented — Rust recursion does emit-and-fold; no RunoutCache stores all entries.

### Candidate N — Iteration-parallel CFR (Pluribus-style)
- Run K independent DCFR threads, periodically merge regret tables.
- Stacks multiplicatively with PR-4 rayon: 2-4× on top.
- Memory: K× working set (4 GB at K=4, top_k=169).
- Effort: 6-8 days. Risk: HIGH. **TIER 2 PICK.**

### Candidate O — GPU offload via Metal Performance Shaders
- 3-5× if dispatch overhead can be amortized, 0× if not.
- Effort: 3-4 weeks POC + 6-8 weeks shippable. Risk: VERY HIGH.
- **DROP from v1.11.** Revisit only after CPU-side exhausted.

### Candidate P — Hand-class abstraction at postflop
- User explicitly rejected (suit-blocker fidelity loss). **DROP.**

### Candidate Q — Lazy infoset materialization
- Only allocate infoset on first visit.
- 0.5-0.7× peak RSS on sparse workloads + ~5-10% wall.
- **BUNDLE with Candidate E.**

## Prioritized v1.11 roadmap

| Stage | Candidate | Expected speedup | Effort | Risk |
|---|---|---|---|---|
| **v1.11-0** | H1 LTO + H2 PGO | 1.15-1.30× | 1-2 days | LOW |
| **v1.11-1** | E (sparse, variant 1) + Q (lazy infoset) | 1.3-2.5× on Premium-A | 4-5 days | LOW |
| **v1.11-2** | K (ε-reach tree pruning) | 1.5-3× on Premium-A | 4-6 days | MEDIUM |
| **v1.11-3** | D (board-iso caching at chance) | 1.5-3× on flop | 5-7 days | MEDIUM |
| **v1.11-4 opt-in** | I1 (f32 dual-path) | 1.5-2× kernel + 0.5× memory | 7-10 days | HIGH |

**Combined headline on Premium-A flop top_k=169**: 6-25× over v1.10. Projects 30-60s (v1.10) → 5-15s (v1.11 conservative) → 3-7s (with opt-in f32).

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Sparse range zero-reach miscounts active combos | MEDIUM | Bit-identical 1e-12 diff vs dense |
| Tree pruning ε drifts under strategy update | MEDIUM | Periodic re-eval every 100 iters; ε=1e-12 conservative |
| Board-iso wrong on asymmetric ranges | HIGH | Runtime `is_range_suit_symmetric` check + fallback |
| f32 NaN/Inf escapes | HIGH | Per-iter `is_finite` guard |
| f32 silently produces non-Nash | HIGH | Loose-tolerance EV diff (1e-5), opt-in flag with advisory |

## Open questions for v1.11 planning

1. **v1.10 stack measurement.** All v1.11 estimates anchored to projected v1.10 baseline. Re-validate once v1.10 perf table published.
2. **PCS as alternative.** If user accepts sampled equilibrium, PCS could displace D + K entirely.
3. **Premium-A sparsity profile.** "30-80 combos with reach > 1e-6" estimate — measure before committing to Candidate E.
4. **f32 opt-in worth the cost?** 7-10 days for 1.5-2× behind opt-in flag.
5. **v1.11 hardware target.** Laptop tier (8-core) vs Mac Pro / cloud (16+ cores)?
6. **v1.10.1 patch with LTO+PGO?** Trivial speedup before starting v1.11.
7. **f32 risk after v1.11-1/-2?** Shorter regret accumulation = numerically safer for f32.

## Honest framing on what we don't know

- v1.10 hasn't shipped; all estimates anchored to projected baseline.
- Premium-A blueprint sparsity is assumed, not measured.
- Board-iso reuse rate depends on flop diversity per user workflow.
- PGO numbers are typical (10-20%), not measured on Apple Silicon NEON-saturated kernels.
- f32 convergence demonstrated by Pluribus at different hyperparams; our (1.5, 0, 2) may interact differently.

## v1.11 engineering estimate

| PR | Days | Cumulative |
|---|---|---|
| v1.11-0 (LTO + PGO) | 1-2 | 2 |
| v1.11-1 (sparse + lazy infoset) | 4-5 | 7 |
| v1.11-2 (tree pruning) | 4-6 | 13 |
| v1.11-3 (board-iso chance caching) | 5-7 | 20 |
| Bench + diff-tests + ledger update | 4-5 | 25 |
| **v1.11.0 core** | **18-25 days (~4-5 weeks)** | |
| v1.11-4 (f32 opt-in, optional) | 7-10 | 35 |

Realistic ship date: **6-8 weeks after v1.10 lands**.

## Critical files for implementation

- `crates/cfr_core/src/dcfr_vector.rs` — hot traverse path
- `crates/cfr_core/src/simd.rs` — kernels needing sparse-aware variants
- `Cargo.toml` (root + crates/cfr_core) — LTO/PGO config
- `crates/cfr_core/src/abstraction.rs` — `canonicalize_board` building block for D
- `poker_solver/blueprint_subgame.py` — Premium-A entry point defining production workload

---

*Research source: agent `abf2ced6405f24594`, 2026-05-28.*
