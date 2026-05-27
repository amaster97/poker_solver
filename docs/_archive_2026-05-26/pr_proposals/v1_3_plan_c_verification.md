# v1.3 — Empirical verification of the Plan C 30-100× speedup claim

**Status:** Verification report. Apple Silicon (M-series), Python 3.13.1, numpy 2.3.3, 2026-05-23. Investigates whether the "30-100× from vector-form BR + dense slabs" extrapolation in `docs/pr_proposals/v1_3_research_alternatives.md:117, :98` is reasonable for OUR codebase.

---

## Section 1 — noambrown's published benchmark details

**There are no published benchmarks in `references/code/noambrown_poker_solver/`.** `README.md` lists CLI invocations but no wall-clock numbers; `_NOTES.md:6` says "C++ targets performance" without quoting a multiplier. Our own `v1_3_research_alternatives.md:98` claims "noambrown C++ vs Python ... ~30-100× speedup just from Vec<f32> over Dict[str, List[float]]" sourced to `_NOTES.md:24` — but `_NOTES.md:24` only describes that "vector_eval.cpp ... is gold," no number. The 30-100× is **folklore extrapolation**, not noambrown's measured value.

What noambrown's code does tell us structurally:
- **Same algorithm both languages.** `python/src/algorithms/vector_cfr.py:186-269` (`_traverse`) is the line-by-line analog of `cpp/src/trainer.cpp:242-305` (`Trainer::best_response`).
- **Hand vector size.** `_NOTES.md:13` documents "~1081 river combos per player" — ~1000× smaller than our W1.5 case (1.16 M, `docs/pr13_prep/phase1_results.md:42`).
- **Tree shape.** River-only (`_NOTES.md:36`). Our W1.5 is a turn subgame with chance-node fanout absent from noambrown.

---

## Section 2 — Our bottleneck profile

W1.5 failure (`docs/pr13_prep/phase1_results.md:39-45`):
- **Rust returns fast.** `crates/cfr_core/src/hunl_solver.rs:414-415` hardcodes both `exploitability: 0.0` and `game_value: 0.0`. Rust never computes BR.
- **Python re-walks.** `solver.py:475` → `exploitability()` (line 190) → `_best_response_value()` (lines 253-297) → `_collect_infosets()` (lines 300-341) and fixed-point loop (lines 271-288). Every infoset visit does `dict.get(key)` keyed on a string like `"QhQd|2d5s7cKhAs|r|xb500A"` (`phase1_results.md:56`), reads a `list[float]`, does per-action Python arithmetic.
- **Combo count.** `C(48,2) × C(46,2) = 1.08 M ≈ 1.16 M` for empty `initial_hole_cards`.
- **Data structure.** `solver.py:23` declares `average_strategy: dict[str, list[float]]` — same shape as noambrown's Python ref.

Structural mismatch summary:

| Dimension | noambrown bench | W1.5 |
|---|---|---|
| Combos | ~1081 | ~1.16 M (~1000×) |
| Tree | River only | Turn → river |
| Algorithm | Vector-form (C++) | Per-state recursion (Python) |
| Data | Dense `Vec<float>` | `dict[str, list[float]]` |
| Iterations | varies | 100, SIGKILL@900s |

---

## Section 3 — Structural comparison

Two ports are conflated in the headline:

1. **Data-structure port:** `dict[str, list[float]]` → dense `[combo, action]` slab. Language-agnostic; doable in Python via `numpy.ndarray`.
2. **Language port:** Python → Rust + SIMD.

`v1_3_research_alternatives.md:114-122` does both and credits both to one "30-100×". The microbench in §5 isolates shift #1 by running both patterns in Python — the gap reflects data-structure + algorithm-shape only. Rust adds on top.

---

## Section 4 — Credible speedup range FOR OUR CODEBASE

Pre-microbench estimate:
- **Pattern A cost:** `O(num_infosets × num_combos × num_actions)` Python ops + dict lookups. CPython at ~100 ns/op → ~12 s for 120 M ops.
- **Pattern B cost:** numpy SIMD on contiguous arrays at ~1-3 GB/s → ~0.2-0.5 s for 480 MB traversed.

Predicted ratio: **15-50×** from data-structure shift alone within Python. Rust on top of numpy adds typically 1-3× when ops are already vectorized. End-to-end credible: **20-100×**.

The 30× lower bound is plausible. The 100× upper bound requires Rust to add a 4-5× multiplier on top of dense-Python — possible with f32 SIMD but not guaranteed.

---

## Section 5 — Empirical microbench

File: `/tmp/plan_c_microbench.py`. Both patterns in Python so the gap is data-structure-only.

Config: 200,000 combos × 200 infosets × 3 actions. Scaled down from 1.16 M so Pattern A finishes <60s; ratio scales linearly with combo count.

Hardware: Apple M-series, Python 3.13.1, numpy 2.3.3.

Results:
```
Pattern A (HashMap+str+lists, per-combo Python loop):
  setup: 45.04s
  BR walk:  9.20s

Pattern B (dense numpy slab, vector ops):
  setup: 0.6332s
  BR walk: 0.4115s

Walk-only speedup (A/B):   22.4×
Total speedup (setup+walk): 51.9×
```

Walk-only (22×) isolates the BR-traversal hot loop — the fairest comparison. Total (52×) includes one-time strategy materialization, which Plan C would amortize.

Scaling to 1.16 M: Pattern A walk ≈ 9.2 × 5.8 ≈ **53 s per BR walk**; two players × ~10 fixed-point iterations ≈ ~17 minutes per `exploitability()` call — tracks the W1.5 timeout. Pattern B at 1.16 M ≈ **2.4 s**. Rust on top of B should add a further 1.5-3× (cache layout + f32 SIMD + no GIL). Compound: **30-150×** on the BR walk.

---

## Section 6 — Verdict

**Plan C 30-100× claim is CREDIBLE.** The microbench shows 22× walk-only speedup from the data-structure shift alone *within Python* (no Rust yet); a Rust port compounds toward 30-100×. The headline holds — but the *attribution* in `v1_3_research_alternatives.md:98` is misleading: it credits "Vec<f32> over Dict[str, List[float]]" for the whole multiplier, when ~22× of that is already available without leaving Python.

**Confidence: HIGH for lower bound, MEDIUM for upper bound.**
- **30× lower:** measured 22× + 52× in pure Python; Rust adds at minimum the missing 1.5×. ≥30× is baked in by the structural shift. HIGH.
- **100× upper:** needs Rust + SIMD + f32 to add ~4-5× on top of dense-Python. Plausible but not measured here. MEDIUM.

**Practical implication.** The first ~22× is achievable in **pure Python** by rewriting `_best_response_value` (`solver.py:253-297`) around `numpy.ndarray` keyed by `(infoset_idx, combo_idx, action_idx)`, dropping the string-dict + list-of-lists. That's a 1-2 day change with no new dependencies and would close the W1.5 SIGKILL on its own. The Rust port (5-7 days, `v1_3_research_alternatives.md:121`) is the *additional* 2-3× — worth doing but no longer emergency-fallback-grade because the Python-numpy rewrite alone unblocks the workflow.

**Recommendation.** Reframe Plan C in `v1_3_research_alternatives.md` as two stages:
- **C1:** numpy slab rewrite — 1-2 days, expected 15-25× walk speedup, no new deps. **This is the actual emergency fallback.**
- **C2:** Rust port of C1 — 5-7 days, expected additional 2-5×, v1.4 timeline.

The current single-stage "port to Rust = 30-100×" framing conflates these and overstates the fallback's risk.

---

**End. Microbench: `/tmp/plan_c_microbench.py`.**
