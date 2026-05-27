# Full-Tree Preflop Range-vs-Range (RvR) Solver — Plan

**Date:** 2026-05-27
**Status:** Phase 1 design plan — NOT YET IMPLEMENTED
**Priority:** P0 (user-flagged) — GTO Wizard / PioSolver-style preflop chart generation, the missing v1 deliverable closing the public OSS preflop gap.

---

## 1. Problem statement

**Input:** stack depth + blind structure + two ranges (e.g. BTN open range, BB defense range) + action menu (open / 3-bet / 4-bet / 5-bet / call / fold / all-in).

**Output:** per-`(hand_class, decision_point)` action-frequency table — the GTO chart. 169 hand classes (78 suited, 78 offsuit, 13 pairs). NO fixed hole cards anywhere — solver works over the cross-product of the two ranges.

## 2. Where the current solver assumes fixed hole cards

1. `crates/cfr_core/src/preflop.rs:506` (`solve_hunl_preflop`) — `if config.initial_hole_cards.is_none() { return Err(MissingHoleCards) }`.
2. `poker_solver/preflop.py:419` (`_validate_preflop_config`) — Python entry mirrors the rejection.
3. `crates/cfr_core/src/dcfr_vector.rs:1219` — explicit "preflop range-vs-range is deferred to v1.5.1."

The kernel itself (`HUNLState::initial_preflop` → `BettingTree::build_from`) **already supports** the empty-holes preflop root. The blocker is the solver caller, not the state machine.

## 3. Algorithm choice

**Architecture A — Vector-form DCFR with full 1326-hand vector (RECOMMENDED).** Mirrors postflop RvR (`dcfr_vector.rs`): per-decision-node `(hand_count × action_count)` regret + strategy_sum tables; walk tree once per iter; alternate updates. Lossless preflop (matches Pluribus, Libratus, PLAN.md decision).

**Architecture B (REJECTED)** — Bucketed (169 class × suit reps). Pluribus paper explicitly says "no information abstraction on the betting round it is actually in." Revisit only if 16 GB OOMs.

**Algorithm:** Discounted CFR (α=1.5, β=0, γ=2.0) per PLAN.md lock + Brown & Sandholm 2019. NOT MCCFR (deterministic walk has tighter iter-count convergence on small preflop trees).

## 4. Memory budget — M-series 16 GB

```
hand_count per player = 1326 (lossless preflop)
action_count avg      = 5
bytes/infoset         = 2 × 1326 × 5 × 8 = 106,080 ≈ 104 KB
infosets              = ~300 decision nodes (raise_cap=4, 6 bet sizes)
total                 = 300 × 104 KB ≈ 31 MB
```

**Tractable in storage.** Perf wall is in **terminal-leaf evaluation**: 1326×1326 ≈ 1.76M (hp, ho) pairs × ~50 terminal leaves = ~88M pair evaluations/iter.

**Dominant cost — one-time equity precomputation:**
- 169×169 = 28,561 class-pair equities × ~12 suit-overlap micro-variants ≈ ~85K table entries
- Each entry = expected equity over C(48,5) = 1.71M runouts
- Total: ~145 trillion 7-card evals → **multi-hour CPU work, ONCE**

**MUST be shipped as a committed `.npz` asset** (~1 MB on disk). Without disk caching, plan is impractical. With it, runtime per-iter ≈ 5.3s single-threaded; Rayon-parallelized across action children → **8-10 min for 500 iters on M4 Pro 8-core.**

## 5. Phased plan

### Phase A — Rust engine (~3-4 days)
- **A.1:** `preflop_equity.rs` (~200 LOC) — 169×169 equity table loader + precompute binary that emits `assets/preflop_equity_169x169.npz`
- **A.2:** New `solve_hunl_preflop_rvr` in `preflop.rs` (don't modify existing scalar entry)
- **A.3:** New `solve_preflop_rvr_vector` driver (~400 LOC) with new `PreflopTerminalCache` (mirrors PR #114's `TerminalCache` for equity-leaf substitution)
- **A.4:** PyO3 wiring in `lib.rs` (~50 LOC)
- **A.5:** Rust tests (~150 LOC) — smoke + AA-only / KK-only closed-form

### Phase B — Python wrapper (~2 days)
- `solve_full_tree_preflop_rvr` in `poker_solver/preflop_rvr.py` (~200 LOC)
- `PreflopRvRResult` dataclass with per-history + per-class strategy projections

### Phase C — Differential tests (~2 days)
- **Pushfold chart diff** (cleanest): at 15 BB with degenerate action menu, full-tree solve MUST converge to the pushfold chart. Tolerance: ≤1% on combo frequency.
- AA-only vs KK-only sanity
- Aggregator vs full-tree diff on premium-only fixtures (≤5pp drift per cell expected)
- GTO Wizard public chart sanity (visual only — action menu differs)

### Phase D — CLI + GUI (~2 days)
- `poker-solver --hunl-mode preflop-rvr` with `--hero-range` / `--villain-range` flags
- GUI tab "Preflop Chart" with 13×13 matrix — OUT OF SCOPE for Phase A-C (defer to PR 10c+)

## 6. Open questions for user (TOP 3 — BLOCKING)

1. **Action menu defaults.** Our locked default is 6 bet sizes (33/75/100/150/200% + all-in) + fold + call/check, raise_cap=4. GTO Wizard's published HU charts typically use 5 sizes (2bb/2.5bb/3bb/4bb open + all-in). Keep our 6-size menu (and document drift from public charts) or ship a preflop-specific 5-size menu?
2. **Ship precomputed equity table in repo, or build at install time?** Committed `.npz` = ~1 MB repo bloat but instant user setup. Install-time = no bloat but multi-hour one-shot build on user's machine. **Recommend committed asset.**
3. **Phase D GUI scope.** Include the 13×13 chart visualization widget (~3-5 days NiceGUI work), or just expose JSON download + table view and defer chart widget to a later PR?

## 7. Top 3 risks

1. **Equity-table precomputation MUST be cached on disk.** Without the `.npz` asset, plan is impractical (user's machine doesn't have multi-hour CPU budget). Risk: validating the bucketed-by-class-pair equity is lossless enough — blocker effects (`AhAd vs KsKc` blocks shared K differently than `AhAd vs JsJc`). Mitigation: store 2-3 micro-bucket variants per class pair (~85K entries, still <1 MB).
2. **Equity-leaf approximation drift at non-all-in lines.** The FLOP-frontier equity-leaf is **exact for all-in** but bakes in "check-down postflop" for ~60% of strategy weight at 100 BB. Diff against pushfold (all-in only) will be clean; diff against full preflop+postflop solves will show systematic drift that's NOT a bug. Mitigation: document clearly + offer Phase E (post-v1) chained orchestrator (#31) that calls real `solve_hunl_postflop` at each preflop terminal.
3. **Convergence speed.** GTO Wizard's "1% HU charts in 30 min on compute farm" implies cluster-level parallelism. M-series single-machine may need 500-2000 iters for 1% exploit. At ~10s/iter post-Rayon: 2000 iters = ~5.5 hours. Mitigation: ship 1000-iter default (~3% exploit, "Standard tier"); allow bump to "Library tier" (0.1% target).

## 8. Surface area

| Area | New files | Modified | LOC |
|---|---|---|---|
| Rust engine | `preflop_rvr.rs`, `preflop_equity.rs`, `examples/build_preflop_equity.rs` | `dcfr_vector.rs`, `lib.rs`, `Cargo.toml` | ~800 |
| Python | `preflop_rvr.py` | `solver.py`, `__init__.py` | ~250 |
| Tests | 3 new test files | — | ~400 |
| CLI | — | `cli.py` | ~100 |
| Assets | `assets/preflop_equity_169x169.npz` (~1 MB binary) | — | — |
| Docs | `preflop_rvr_v1_design.md`, CHANGELOG | — | ~150 |
| **Total** | **8 new files** | **5 modified** | **~1700 LOC + 1 MB asset** |

## 9. Critical files

- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs` — TerminalCache pattern from PR #114 + traverse refactor
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/preflop.rs` — fixed-hole path; new RvR path added in parallel
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs` — `enumerate_hole_card_pairs`, `BettingTree`
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` — `HUNLState::initial_preflop` already supports empty holes
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — PyO3 entry point

## 10. Paper citations

- **DCFR algorithm:** Brown & Sandholm 2019, AAAI. `references/papers/dcfr_brown_2019.pdf`. α=1.5/β=0/γ=2.0 defaults.
- **Vector-form CFR:** Brown's MIT reference at `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`.
- **Depth-limited solving (equity-leaf):** Brown & Sandholm 2018, NeurIPS. `references/papers/depth_limited_brown_2018.pdf`.
- **Pluribus (lossless preflop):** Brown & Sandholm 2019, Science 365. `references/papers/pluribus_brown_2019_science.pdf` p3 col2.

---

**Status:** PLAN COMPLETE. Phase A implementation NOT STARTED (Plan agent operates read-only). Next: user picks the 3 blocking decisions in §6, then implementation agent consumes this plan.
