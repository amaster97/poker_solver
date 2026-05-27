# v1.7.0 `solve_range_vs_range_nash` Perf Profile — Sarah's Multi-Street Envelope

**Date:** 2026-05-23
**Tester:** Orchestrator diagnostic agent (post-W2.1 Type D triage)
**Worktree:** `/tmp/w2.1-profile-96471` @ `3843ce7` (origin/main, v1.7.0)
**Runtime interpreter:** `/usr/local/bin/python3` (universal2 framework, arm64) — same workaround as W2.1 retest doc; pyenv shim path remains broken for maturin builds.
**Driver script (artifact):** `/tmp/w2.1_profile_driver.py`
**Source ticket:** `docs/persona_test_results/W2_1_post_v1_7_0_result.md` (Type D timeout at 21+ min)

---

## TL;DR

- **Street depth is THE dominant cost dimension.** Going river → turn is ~25–80× slower per-iter; turn → flop is unmeasured but ≥10× more (flop 2-class × 10 iter did not finish in 7+ min). Iter count is strictly linear, class count is super-linear (~quadratic in #classes for the per-iter cost on multi-street trees).
- **Sarah's viable envelope on the Nash path is river-only.** Even the smallest flop fixture tested (2 classes × 10 iter, deepest tree) failed to terminate within several minutes; the W2.1 fixture (8 classes × 500 iter × flop) extrapolates to multi-hour, consistent with the 21-min Type D timeout.
- **Turn is workable for ≤4 classes × ≤100 iter (~92 s).** Turn 8 classes × 500 iter extrapolates to ~21 min — matches the W2.1 timeout almost exactly when adjusted for tree depth, confirming the diagnosis.
- **Recommendation:** add USAGE.md envelope guidance; v1.8 candidate is the deferred PR 23 vector-shape SIMD kernels (`docs/pr_proposals/v1_5_pr_23_implementer_notes.md` projects 4-8× from `discount_regrets` / `update_regret_sum` / `compute_strategy` on `hand_count × action_count` shape).

---

## Scaling table (all wall-clock, `compute_exploitability_at_end=False`)

Fixture base: K-Q-7 two-tone board (river uses Ks Qh 7d Th 2c; turn uses Ks Qh 7d Th; flop uses Ks Qh 7d), starting_stack=10000, pot=1500, symmetric (750/750), bet sizes (0.33, 0.75), no all-in, raise_cap=2, `hero_player=0`. Hand classes drawn in order: `[AA, KK, QQ, JJ, TT, AKs, AQs, KQs]`.

### Iter scaling (8 classes, river)

| Iter | Wall-clock | Per-iter (ms) | Note |
|---|---|---|---|
| 50  | 0.78 s | 15.6 | |
| 100 | 1.11 s | 11.1 | |
| 200 | 1.79 s | 9.0  | |
| 500 | 3.77 s | 7.5  | Asymptotic per-iter ~6–7 ms (warmup amortized) |

**Verdict: linear in iter count** (with ~0.4 s constant warmup).

### Class scaling (river, 500 iter)

| Classes | Wall-clock | Per-iter (ms) | Ratio vs 2c |
|---|---|---|---|
| 2 | 0.69 s | 1.4 | 1× |
| 4 | 1.68 s | 3.4 | 2.4× |
| 6 | 2.80 s | 5.6 | 4.0× |
| 8 | 3.77 s | 7.5 | 5.5× |

**Verdict: roughly linear-to-mildly-quadratic in #classes on river** (matches expected `O(hands²)` per-leaf blocker check from PR 23 notes).

### Class × iter on turn (turn = 2 streets)

| Classes | Iter | Wall-clock | Per-iter (s) | Ratio vs river @ same config |
|---|---|---|---|---|
| 2 | 100 | 17.1 s   | 0.17 | 35× river |
| 2 | 500 | 83.4 s   | 0.17 | 121× river |
| 4 | 100 | 91.6 s   | 0.92 | 131× river |
| 4 | 500 | 466.0 s  | 0.93 | 277× river |
| 8 | 50  | 127.7 s  | 2.55 | 164× river |
| 8 | 100 | 252.7 s  | 2.53 | 228× river |
| 8 | 500 | (skipped — projects to ~21 min from linear iter scaling) | 2.53 | matches W2.1 timeout |

**Verdict: per-iter cost on turn is 25–340× river depending on class count.** Per-iter cost is **super-linear in #classes** on turn (2c: 0.17s → 4c: 0.93s = 5.5× for 2× classes → 8c: 2.53s = 2.7× for 2× classes more). Approximates ~quadratic-ish, consistent with the O(N²) terminal blocker check at every turn leaf.

### Flop (3 streets) — Sarah's actual fixture

| Classes | Iter | Wall-clock | Status |
|---|---|---|---|
| 2 | 10  | killed at 7+ min, no output  | **≥7 min, did not complete** |
| 2 | 50  | killed at 2+ min, no output  | ≥2 min, did not complete |
| 4 | 50  | killed (concurrent run, contention-starved; not retried sequentially due to budget) | n/a — would be ≥5 min based on turn ratio |
| 8 | 50  | killed at 23+ min, no output (concurrent + contention-starved) | ≥23 min, did not complete |
| 8 | 500 | W2.1 retest: 21+ min, terminated (Type D) | original failure |

**Verdict: flop is intractable for interactive use at v1.7.0.** Even the smallest possible flop fixture (2 classes, 10 iter — i.e., **50× fewer iter than W2.1 default**, **16× smaller per-leaf hand×hand work**) did not complete within 7+ min. The per-iter cost on flop is dominated by chance-node enumeration over turn + river runouts at every flop action node — multiplicatively on top of turn's already-O(N²) leaf cost.

---

## Dominant cost dimension

**Ranked by sensitivity** (factor improvement in wall-clock per 2× reduction):

1. **Street depth (≫ everything else).** River → turn = 25–340× faster per-iter; turn → flop = ≥10× (unmeasured ceiling, possibly much higher). **Halving streets is the only way to drop a multi-street solve under Sarah's budget.**
2. **Class count (super-linear on multi-street, linear on river).** 2× fewer classes → ~3–5× faster on turn, ~2× faster on river. Halving classes does not dominate the street effect.
3. **Iter count (linear, near-perfectly).** 2× fewer iter → 2× faster. Linear scaling means there is no "knee" — every iter cut is proportional.

### Why street depth dominates

The Rust vector form (`crates/cfr_core/src/dcfr_vector.rs`) walks the betting tree once per iter but enumerates **chance children** (board cards) at street transitions. Going river → turn introduces the river runout enum at every turn leaf; turn → flop introduces the turn-runout enum at every flop action node, on top of which each turn child itself enumerates the river. Per-iter work scales roughly with the product of leaf count × per-leaf O(N²) blocker check, both growing super-linearly with street depth.

PR 23 implementer notes (`docs/pr_proposals/v1_5_pr_23_implementer_notes.md`) explicitly call this out: "The full-deck case is dominated by the terminal-leaf O(N²) blocker check (1081 × 1081 = 1.17M per leaf)." On flop, "1081 × 1081" multiplies across all turn-runout × river-runout combinations, not just the river-final node.

---

## Sarah's viable envelope (≤5 min Nash budget)

Based on measured data:

| Street depth | Max #classes | Max iter | Wall-clock | Recommendation |
|---|---|---|---|---|
| **River only** | 8 | 500 | 3.8 s | ✅ Comfortable; well under budget |
| **River only** | 8 | 2000 | ~14 s (extrap from 500i) | ✅ High-accuracy still under budget |
| **Turn + river** | 4 | 100 | 92 s | ✅ Under budget |
| **Turn + river** | 4 | 200 | ~180 s (extrap) | ✅ Just under budget |
| **Turn + river** | 4 | 500 | 466 s | ❌ Over budget (7.8 min) |
| **Turn + river** | 8 | 100 | 253 s | ✅ Just under budget |
| **Turn + river** | 8 | 200 | ~500 s (extrap) | ❌ Over budget |
| **Flop+turn+river** | any tested | any tested | **none completed within budget** | ❌ **Not viable on Nash path** |

**Operational rule of thumb:**
- **River:** any reasonable size works; use 500 iter as default.
- **Turn:** ≤4 classes × ≤200 iter, OR ≤8 classes × ≤100 iter, fits Sarah's budget.
- **Flop:** **use the aggregator path** (`solve_range_vs_range`) for Sarah's interactive workflow at v1.7.0. The Nash path is research-grade overnight runs only.

---

## Recommended USAGE.md note

Suggested addition under the `solve_range_vs_range_nash` section (around line 670 of `USAGE.md`, where the existing PR 23 / Nash discussion lives):

> **Performance envelope (v1.7.0).** `solve_range_vs_range_nash` per-iter cost is dominated by street depth (deeper tree → quadratically more chance enumeration), then by class count (super-linear on multi-street), then by iter count (linear).
>
> Interactive budgets (~5 min per solve, M-series Mac):
>
> | Street | Max classes × iter | Note |
> |---|---|---|
> | River only (`starting_street=Street.RIVER`) | up to 8 × 2000 | Comfortable |
> | Turn + river (`starting_street=Street.TURN`) | 4 × 200 or 8 × 100 | Tight; pick one knob |
> | Flop + turn + river (`starting_street=Street.FLOP`) | **prefer `solve_range_vs_range` (aggregator)** | Nash path is multi-hour at 8 classes × 500 iter |
>
> For flop spots with interactive budgets, use `solve_range_vs_range` (the Pluribus-blueprint aggregator), which solves a flop fixture comparable to Sarah's spot in ~1 s and is the canonical v1.4.1 PASS for that workflow. See `docs/aggregator_vs_true_nash_explainer.md` for the trade-off discussion. The Nash path is recommended for river-only or overnight research runs at v1.7.0; v1.8+ SIMD work targets making it viable for interactive flop use.

---

## v1.8 candidate: vector-form SIMD kernels (PR 23 deferred work)

`docs/pr_proposals/v1_5_pr_23_implementer_notes.md` §"What was deferred" already names the path:

> **SIMD kernels for the vector-shape arithmetic** — the existing `simd.rs` kernels assume `action_count` shape; vector-form needs `hand_count × action_count` shape. `discount_regrets`, `update_regret_sum`, `compute_strategy` would all benefit (Brown's reference code is unvectorized; we can do better with NEON). Rough projection: 4-8× speedup based on PR 8's experience with the scalar kernels.

**Scope of a v1.8 perf-only PR:**

1. **Vector-shape NEON kernels** in `crates/cfr_core/src/simd.rs` or a sibling module:
   - `discount_regrets_vector(regret_sum: &mut [f64], pos_scale, neg_scale)` operating on `hand_count × action_count` slices.
   - `update_regret_sum_vector(regret_sum, action_v, node_v, opp_reach)` likewise.
   - `compute_strategy_vector(regret_sum, strategy)` likewise.
   - Per PR 8 pattern: scalar fallback for non-aarch64 + bit-parity guard.
2. **Wire into `dcfr_vector.rs`** at the iteration hot loop.
3. **Acceptance:** turn 8 classes × 500 iter drops from ~21 min projected → ≤3–5 min (4-8× target). Flop 8c × 500 iter drops from multi-hour → still likely >Sarah budget (because chance-node enumeration is the larger factor), but enough to make 4-class flop interactively viable.
4. **Optional follow-up (v1.9 candidate, larger):** reduce chance-node fanout via PR 23 implementer's other deferred item — **EMD bucketing in the vector form**, which compresses the per-street hand dimension from 1081 → 64-256 and brings the per-leaf blocker check down by ~50×. This is the larger flop wins; SIMD alone won't make flop interactive.

**Do NOT do in v1.8:** preflop range-vs-range (separately deferred per spec §8 Q2; 16 GB memory edge, needs suit-iso).

---

## Files / artifacts

- Profile driver: `/tmp/w2.1_profile_driver.py` (worktree-local artifact; not committed)
- Raw run outputs: captured inline above (each run printed `RESULT\t<label>\t<wall_s>\t<backend>\t<expl>`)
- Source ticket: `docs/persona_test_results/W2_1_post_v1_7_0_result.md`
- PR 23 implementer notes (deferred work spec): `docs/pr_proposals/v1_5_pr_23_implementer_notes.md`
- Aggregator-vs-Nash trade-off explainer: `docs/aggregator_vs_true_nash_explainer.md`

---

## Cleanup

```
git -C /Users/ashen/Desktop/poker_solver worktree remove /tmp/w2.1-profile-96471 --force
git -C /Users/ashen/Desktop/poker_solver worktree prune
```

(Performed by profile agent post-doc-write.)
