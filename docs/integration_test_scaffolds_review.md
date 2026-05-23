# Integration Test Scaffolds — Post-PR-5 Alignment Review

**Reviewed against:** `poker_solver/__init__.py`, `hunl_solver.py`,
`profiler/memory.py`, `solver.py`, `pushfold.py`, `hunl.py` on the integration
branch as of 2026-05-22.
**Scope:** the 18 scaffolds in `docs/integration_test_scaffolds.md`.
**Verdict (TL;DR):** 18 total · 0 fully runnable today · 18 still gated · 6 of
those have premise drift worth pencilling into the next prune wave; the rest
are still correctly shaped. Recommendation: **leave the scaffolds doc alone
for now, fold each scaffold into its PR-specific test file when the gating PR
lands.** No standalone update commit required.

---

## 1. Per-test status

| # | Test | File | Gate | Status | Note |
|---|---|---|---|---|---|
| 1 | `test_dispatch_short_stack_5bb_lands_on_pushfold_chart` | dispatch | PR 9 | pending; premise OK but assertion drift | backend literal is `"pushfold_chart"`, the `"pushfold"` fallback no longer exists |
| 2 | `test_dispatch_50bb_lands_on_tree_builder_solver` | dispatch | PR 9 | pending; premise OK | preflop branch still missing |
| 3 | `test_dispatch_over_250bb_raises_clear_error` | dispatch | PR 9 | pending; premise OK | 250 BB ceiling not yet wired |
| 4 | `test_dispatch_12bb_hard_cliff_to_pushfold_no_interpolation` | dispatch | PR 9 | pending; assertion drift | same `"pushfold"` literal issue as #1 |
| 5 | `test_dispatch_ante_does_not_tilt_boundary_at_15bb` | dispatch | PR 9 | pending; assertion drift | same `"pushfold"` literal issue |
| 6 | `test_abstraction_lossless_when_no_artifact_loaded` | abstraction | PR 4 | pending — but PR 4 IS landed; runnable in principle | imports `AbstractionRef` & `build_abstraction` (both exist on `__init__`); see §3 |
| 7 | `test_abstraction_bucketed_key_when_artifact_loaded` | abstraction | PR 4 | pending — but PR 4 IS landed; runnable in principle | same as #6; see §3 |
| 8 | `test_abstraction_bucket_id_matches_python_and_rust_tiers` | abstraction | PR 6 | pending | Rust binding (`poker_solver._rust`) not on integration |
| 9 | `test_full_chain_python_rust_agree_within_tolerance_no_abstraction` | full_chain | PR 6 | pending | Python half is now runnable but Rust half blocks |
| 10 | `test_full_chain_python_rust_agree_with_card_abstraction` | full_chain | PR 6 | pending | same as #9 |
| 11 | `test_preflop_blueprint_produces_strategy_at_100bb` | handoff | PR 9 | pending; premise OK | `build_blueprint` not exported yet |
| 12 | `test_subgame_refinement_uses_blueprint_as_warm_start` | handoff | PR 9 | pending; premise OK | `SubgameKey`, `refine_subgame` not exported yet |
| 13 | `test_pushfold_at_8bb_does_not_invoke_preflop_solver` | handoff | PR 9 | pending; assertion drift | `"pushfold"` literal |
| 14 | `test_ui_solve_runner_cancellation_halts_within_one_iteration` | ui_engine | PR 10 | pending; premise OK | `ui.state.SolveRunner` does not exist on integration |
| 15 | `test_ui_tree_browser_does_not_leak_opponent_hole_cards` | ui_engine | PR 10 | pending; premise OK | `ui.state.SolveTree` does not exist on integration |
| 16 | `test_ui_range_matrix_aggregates_per_combo_strategies_correctly` | ui_engine | PR 10 | pending; premise OK | `ui.views.range_matrix.compute_cell_frequencies` does not exist |
| 17 | `test_library_roundtrip_solve_save_reload_returns_same_strategies` | library | PR 11 | pending; premise OK | `poker_solver.library` does not exist |
| 18 | `test_library_spot_id_is_deterministic_across_runs` | library | PR 11 | pending; premise OK | same as #17 |

---

## 2. Public-surface changes since scaffolds were drafted

The scaffolds were written before PR 5 finalized. The integration tree now
exports (per `poker_solver/__init__.py`):

**New since drafting (PR 5 surface):**
- `HUNLSolveResult` (subclass of `SolveResult` with `memory_report` field —
  scaffolds Files 3/6 already cite it accurately).
- `solve_hunl_postflop`
- `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`
- `default_tiny_subgame` is exported (Files 3 & 6 use it; correct).

**Already there before scaffolds (no drift):**
- `AbstractionRef`, `build_abstraction`, `load_abstraction`, `lookup_bucket`
  (used by Files 2 & 3; all importable today).
- `Card`, `HUNLConfig`, `HUNLPoker`, `Street`, `solve` (used everywhere; all
  importable).
- `PUSHFOLD_MIN_BB`, `PUSHFOLD_MAX_BB` constants exist; `is_pushfold_mode`,
  `solve_pushfold` exist. Scaffolds don't import them by name; they only
  inspect `result.backend`, which is fine.

**Drift items the scaffolds get wrong (low-cost to fix when ungating):**
- Files 1 & 4 assert `result.backend in {"pushfold_chart", "pushfold"}`. The
  shipped surface only emits `"pushfold_chart"` (see `pushfold.py:228` and
  `solver.py:67-74`). The bare `"pushfold"` token is not produced by any code
  path on integration. The set-membership assertion is harmless but the OR
  variant in test 1 (`== "pushfold_chart" or == "pushfold"`) is dead-branch.
- Scaffold 13's `dispatched_to_pushfold` attribute is a PR 9 forward
  reference; the current `SolveResult` does not have that field. The
  scaffold already guards via `getattr(..., None)` so this is intentionally
  forward-compatible — no fix needed.

**No drift in:**
- `solve_hunl_postflop` signature (`config`, `abstraction`, `iterations`,
  positional + keyword) matches Files 3 & 6's call shape.
- `HUNLSolveResult.average_strategy` / `game_value` fields match Files 3 & 6.

---

## 3. Tests that COULD be ungated now

Strictly speaking, two scaffolds in `test_integration_abstraction.py` (#6 and
#7) target PR 4 surface that has been shipped:

- `AbstractionRef` is exported.
- `build_abstraction` is exported.
- `HUNLConfig.abstraction` field exists (`hunl.py:115`).
- `HUNLPoker.infoset_key(state, player)` exists.

**However**, ungating them today is the wrong call because:
1. `tests/test_abstraction_buckets.py`, `test_abstraction_emd.py`, and
   `test_abstraction_integration.py` already cover the lossless / bucketed key
   flip and disk roundtrip at finer granularity. The integration scaffolds
   would be a duplicate of weaker coverage.
2. `_flop_state_for_test()` walks chance outcomes deterministically; this is
   PR 3 idiom but the actual tree builder may yield a different node depth
   than the scaffold assumes. Worth verifying against the live tree before
   ungating.
3. The scaffolds were drafted as "cross-PR seam" tests, and the PR 4 seam is
   already locked by existing tests — there is no remaining cross-PR signal
   to extract by promoting them.

**Recommendation:** leave #6 and #7 gated. They are absorbed by existing
PR 4 tests.

Tests #9 and #10 each have a runnable Python half (the `solve_hunl_postflop`
+ `default_tiny_subgame` chain) but cannot run without the Rust binding;
their value is the Python↔Rust differential, so split-running the Python
half is non-informative.

---

## 4. Tests that still wait for PR 6+

- **PR 6 (Rust port):** tests 8, 9, 10 — all require `poker_solver._rust`.
- **PR 9 (preflop solver + dispatch):** tests 1, 2, 3, 4, 5, 11, 12, 13.
- **PR 10 (UI):** tests 14, 15, 16 — require the `ui` package, which does
  not exist on integration.
- **PR 11 (library):** tests 17, 18 — require `poker_solver.library`, which
  does not exist on integration.

That accounts for 16 of 18 (after subtracting the two PR 4 scaffolds discussed
in §3). All 18 stay gated for at least one more PR landing.

---

## 5. Recommended action

**Do NOT update `docs/integration_test_scaffolds.md` in a standalone commit.**

Reasoning:
- Zero scaffolds are runnable today, so no test is being kept dark by the
  drift.
- The most material drift (the `"pushfold"` literal in the dispatch
  assertions) is one search-and-replace and is more naturally fixed when the
  scaffold is moved into a real test file as part of PR 9.
- The scaffolds doc is a **spec artifact, not test code** — touching it costs
  another review pass. Better to refactor each scaffold into its PR-owned
  test file at PR-landing time:
  - At PR 6 landing: copy tests 8/9/10 into `tests/test_rust_postflop_diff.py`
    or similar, fix Rust-binding imports.
  - At PR 9 landing: copy tests 1-5 + 11-13 into `tests/test_dispatch.py`
    and `tests/test_preflop_handoff.py`, drop the `"pushfold"` literal, wire
    `dispatched_to_pushfold`.
  - At PR 10 / 11: same pattern.
- Once the scaffolds are absorbed, `docs/integration_test_scaffolds.md` can
  be either deleted or downgraded to a one-line "see tests/" pointer. Mark
  this in the next prune sweep.

**Defer-to-natural-absorption** is consistent with the continuous-pruning
rule: the doc only earns its keep until the gated PRs land; refactoring it
in place adds churn for zero coverage benefit.

If the team wants a tiny defensive fix right now without refactoring, the
only worthwhile change is the assertion-set drift on tests 1/4/5/13 (drop
the `"pushfold"` alternative). That is a 4-line edit and would be the only
warranted "update the doc" commit before PR 6/9 lands. Even that is
optional.

---

## 6. Open questions for the next prune wave

- Is `test_full_chain_python_rust_agree_with_card_abstraction` worth keeping
  given that PR 4's existing tests + PR 6's planned Python↔Rust differential
  tests likely subsume it? Re-evaluate after PR 6 spec is final.
- Tests 14-16 lock UI surface that PR 10 has not yet specified; if PR 10
  spec lands without `ui.state.SolveRunner` (or with a different name), the
  scaffolds will need wholesale rewriting, not just import fixes. Worth a
  cross-check at PR 10 design freeze.
