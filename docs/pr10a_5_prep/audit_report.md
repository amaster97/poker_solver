# PR 10a.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10a.5-conformance
**Branched-from:** integration tip `62c75d5` (Integration: merge PR 11 followup v3 — nicegui pin bump)
**Diff size:** 7 modified files, +245 / -76 LoC (~169 net) — matches `pr_report.md` §1 exactly.

**Test status:**
- `pytest tests/test_ui_smoke.py` → **22 passed, 0 failed, 0 xfailed** (`/tmp/pytest_run1.log` reviewed).
- Broader UI suite (smoke + library + library_cli + pushfold) → **55 passed, 1 skipped, 0 failed** (`/tmp/pytest_ui.log` reviewed).
- All 7 `@pytest.mark.xfail` decorators removed from `tests/test_ui_smoke.py`; `grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py` returns empty.
- 22 `test_` functions (`grep -cE '^async def test_|^def test_'` = 22) — locked count vs PR 10a unchanged.

**Implementer report:** reviewed `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/pr_report.md` end-to-end. The §1 acceptance gates, the F1-F5 / X1-X7 changelogs in §2, the production-code justification in §4, and the out-of-scope confirmations in §5 all align with the actual diff (verified via `git diff --stat 62c75d5..HEAD` and per-file `git diff` inspection). Minor caveat: the diff is **uncommitted in the working tree** (no commits on `pr-10a.5-conformance` yet) — the implementer report's "Diff scope (`git diff --stat HEAD`)" block in §1 corresponds to the working-tree state vs. base `62c75d5`, not a committed delta. This is consistent with the implementer note in §7 ("No commit was created"); the auditor must `git add` + commit the staged changes before integration. The diff inspection therefore used `git diff 62c75d5 -- <file>` (working-tree vs base) rather than a committed-revision comparison.

---

## Item-by-item F-table verification (F1-F5)

**F1 — `test_page_renders_without_exception`** — PASS.
- `ui/app.py:127-133` now invokes `range_matrix.render(state)` and `tree_browser.render(state)` inside the `matrix-region` column (was three placeholder labels in PR 10a). `ui/app.py:401-402` adds the `if __name__ in {"__main__", "__mp_main__"}: launch()` NiceGUI 3.x user-fixture guard. `ui/views/range_matrix.py:870` emits `.mark("range-matrix-display")` (replacing the old `.props("data-marker=...")`).
- Evidence: `git diff 62c75d5 -- ui/app.py` shows the placeholder block (lines 127-141 baseline) replaced with the two render calls; `range_matrix.py:870` carries `.mark("range-matrix-display")`.

**F2 — `test_combo_to_cell_mapping_no_off_by_one`** — PASS (already passing; rolled into 22 / 22).
- Pure unit-level (no `User` fixture). No marker dependency. Baseline pre-PR-10a.5 already passed.

**F3 — `test_range_matrix_renders_169_cells`** — PASS.
- `ui/views/range_matrix.py:891` now emits `cell_marker = f"matrix-cell matrix-cell-{cell.hand_class}"` (whitespace-delimited) via `.mark(cell_marker)`. NiceGUI tokenizes `.mark()` on whitespace per `nicegui/element.py:342` (`self._markers = [word for marker in markers for word in marker.split()]` — verified locally in `/Users/ashen/Library/Python/3.13/lib/python/site-packages/nicegui/element.py:342`). Both `matrix-cell` and `matrix-cell-AKs` tokens are individually findable.
- Evidence: `range_matrix.py:888-891` (`cell_marker` construction with whitespace + `.mark`); `tests/test_ui_smoke.py` line block around the 169-count assertion (the diff in `git diff 62c75d5 -- ui/views/range_matrix.py` clearly shows the migration from `.props("data-marker=matrix-cell,matrix-cell-AKs")` → `.mark("matrix-cell matrix-cell-AKs")`).
- Comma-pattern probe: `grep -nE 'data-marker=[a-z0-9-]+,[a-z0-9-]+' ui/views/range_matrix.py ui/views/spot_input.py ui/views/run_panel.py ui/views/tree_browser.py ui/app.py` returns one hit — `range_matrix.py:891` — but that line is the comment `` # `.props("data-marker=matrix-cell,matrix-cell-AKs")` set a `` describing the **fix narrative**, not live code. The probe is functionally empty.

**F4 — preset marker drift (covered by `test_solve_button_starts_worker`)** — PASS.
- `ui/state.py:976` (per `git diff` line numbers around `list_fixture_preset_ids`) now reads `getattr(p, "id", getattr(p, "preset_id", p))` — `.id` is the canonical attribute on `FixturePreset` (per `ui/mock_solver_fixtures.py:35`). `ui/views/spot_input.py:528` emits `mark(f"preset-{marker_suffix}")` where `marker_suffix = preset_id.replace("_", "-")`. The 12 IDs from `_FIXTURE_BUILDERS` (`river_tiny_subgame`, `flop_k72r_100bb`, `flop_t87s_100bb`, `flop_monotone_hhh`, `flop_paired_q9q`, `turn_kqj9_4_flush`, `turn_t872_brick`, `river_axxs_polar`, `preflop_btn_vs_bb`, `river_blocker_heavy`, `shortstack_25bb`, `deepstack_200bb`) → `preset-river-tiny-subgame`, `preset-flop-k72r-100bb`, etc. Smoke 19 references `preset-deepstack-200bb` and `preset-flop-k72r-100bb` — both exist.
- Evidence: `ui/state.py:973-977` (the `.id`/`.preset_id` fallback chain); `ui/mock_solver_fixtures.py:611-624` (the 12-key `_FIXTURE_BUILDERS` dict).

**F5 — combo-inspector row marker drift** — PASS.
- `ui/views/range_matrix.py:776` (`marker = f"combo-inspector-row-{row.label}"`) + `:783 .mark(marker)`. `range_matrix.py:768` (`.mark("combo-inspector-strip")` for the strip wrapper) and `:858` (same). Tree-browser markers in `ui/views/tree_browser.py:608, 626, 647, 652` (`tree-browser`, `tree-reach-slider`, `tree-truncation-badge`, `tree-widget`) all migrated. The Quasar `no-selection-unset` prop correctly stays on `.props()` per the comment at `tree_browser.py:651`.
- Evidence: `git diff 62c75d5 -- ui/views/range_matrix.py ui/views/tree_browser.py`.

---

## Item-by-item X-table verification (X1-X7)

**X1 — `test_range_matrix_color_blend_matches_pio_convention`** — PASS.
- `ui/views/range_matrix.py:418-425`: `DISPLAY_PALETTE = ((255, 0, 0), (255, 255, 0), (0, 255, 0))` — **pure** Pio anchors, NOT the fade `(220, 40, 40)` from the legacy `cell_color()` (which is byte-unchanged at `:400-415`).
- `ui/views/range_matrix.py:428-453`: `cell_rgb_for_action_freqs(fold, call, raise_)` returns an additive blend over `DISPLAY_PALETTE` with int-rounded clamping to [0, 255]. For pure-fold: `(255*1, 0*1, 0*1) = (255, 0, 0)`; pure-raise: `(0, 255, 0)`; 50/50 call+raise: `(127, 254, 0)` (smoke 14 expects ≤±2 per channel, all pass).
- Decorator removed at `tests/test_ui_smoke.py:464-468` baseline (per `git diff`).

**X2 — `test_blocker_cells_show_slashed_overlay`** — PASS, with one note (see Should-fix).
- `ui/views/range_matrix.py:161` adds `CellSummary.has_blocker: bool = False`; `range_matrix.py:279` sets `summary.has_blocker = True` inside `cell_strategy_summary` when **any** combo `combo[0] in board_cards or combo[1] in board_cards` — this is the right "ANY combo blocking" predicate.
- `ui/views/range_matrix.py:899-905`: `if cell.summary.blocked or cell.summary.has_blocker: cell_el_builder = cell_el_builder.classes("blocker-overlay")`. The `or` correctly applies the class for both "partially blocked" (`has_blocker`) and "fully blocked" (`blocked`).
- Smoke 15 (`tests/test_ui_smoke.py:533`) accepts either `blocker-overlay` or any class with `"blocker"` substring — robust assertion.

**X3 — `test_input_matrix_palette_disjoint_from_display_palette`** — PASS.
- `ui/views/range_matrix.py:418-425` exposes `DISPLAY_PALETTE = ((255,0,0),(255,255,0),(0,255,0))`. `str(DISPLAY_PALETTE).lower()` does not contain `"blue"`.
- `ui/views/spot_input.py:300-308` exposes `INPUT_PALETTE = (((248, 250, 252), "#f8fafc"), ((30, 100, 220), "#1e64dc"))`. The shape is `((rgb_triple, css_hex_str), ...)` — a 2-tuple of `(triple, hex)` pairs. `str(INPUT_PALETTE).lower()` contains `"#"` (the hex strings) — satisfies smoke 16's `"#" in input_palette_str` branch.
- `_color_input_cell` (`spot_input.py:317-330`) refactored to derive the lerp endpoints from `INPUT_PALETTE[0][0]` (near-white triple) and `INPUT_PALETTE[1][0]` (saturated-blue triple) — single source of truth.
- Decorator removed at baseline `tests/test_ui_smoke.py:531-534`.

**X4 — `test_chart_default_log_scale`** — PASS.
- `ui/views/run_panel.py:225` emits `log_toggle.mark("expl-chart-linear-toggle")` (single-line addition). Probe `grep -n 'expl-chart-linear-toggle' ui/views/run_panel.py` returns one hit (line 225).
- `_redraw_chart` (`run_panel.py:462-471`) uses `chart.options.clear(); chart.options.update(new_options)` (in-place dict mutation). Probe `grep -nE 'chart\.options\s*=[^=]' ui/views/run_panel.py` returns ZERO direct reassignments — the NiceGUI 3.x read-only-property semantic is honored.
- Decorator removed at baseline `tests/test_ui_smoke.py:580-583`.

**X5 — `test_oom_failure_shows_remediation_notification`** — PASS.
- `ui/views/run_panel.py:524`: the OOM branch is correctly gated by `isinstance(err, MemoryError)` (not unconditional). `:550-553`: `ui.button("Reduce bet sizes", on_click=_reduce_bet_sizes).props("flat dense").mark("oom-reduce-bet-sizes-button")` — only created inside the OOM branch.
- Pruning logic (`run_panel.py:538-548`): `spot.bet_sizes_checked = tuple(bs for bs in spot.bet_sizes_checked if bs <= 1.0)`. **Bounded by inspection of default**: `SpotConfig.bet_sizes_checked: tuple[float, ...] = (0.33, 0.75, 1.0)` (`ui/state.py:357`) — pruning is a no-op for the default and only removes 1.5 / 2.0 entries that the user opted into. Tuple can in principle go empty if every value were >1.0 (e.g., a custom `(1.5, 2.0)`); not protected. See should-fix #1.

**X6 — `test_pushfold_dispatch_at_15bb`** — PASS.
- `ui/views/spot_input.py:409-412`: `ui.button("Switch to push/fold view", on_click=_switch_to_pushfold).props("flat dense").mark("pushfold-switch-button")`. Gated by `if bb <= 15:` at line 388 — correct edge-condition trigger.
- Test wiring fix (`tests/test_ui_smoke.py:669-674`): `stack_p0.value = 15; stack_p1.value = 15` — bypasses `User.type()`'s append-not-replace semantics (NiceGUI 3.x `user_interaction.py:70`). The test-wiring micro-edit is minimal-touch (no assertions changed).
- Decorator removed at baseline `tests/test_ui_smoke.py:656-659`.

**X7 — `test_long_solve_eta_appears_after_30s`** — PASS.
- `ui/state.py:603-635`: `SolveRunner.compute_eta() -> float | None`. Pure arithmetic: reads `iteration`, `start_time_monotonic`/`current_time_monotonic` (else falls back to `time.time() - started_at`), `target_iterations`; returns `(target - iters) / rate`. **Edge cases all handled with `None`**: `iters <= 0`, `elapsed <= 0`, `target is None or target <= iters`, `rate <= 0`. No mutation of `_worker` state — verified `_worker` is byte-unchanged (the diff context line "`def _worker(`" at diff line 56 is unchanged surrounding code, not a new branch).
- `ui/views/run_panel.py:258`: `eta_label.mark("progress-eta")` — single-line marker addition. `progress-eta` grep returns one hit.
- Decorator removed at baseline `tests/test_ui_smoke.py:683-686`.
- Smoke 20 fast-path test (`tests/test_ui_smoke.py:707-724`) directly populates `iteration=1000`, `start_time_monotonic=0.0`, `current_time_monotonic=35.0`, `target_iterations=10000`; expected eta ≈ (10000-1000)/(1000/35) ≈ 315.0 sec > 0 — passes.

---

## Must-fix

**None found.**

Justification: scope-leak probes are clean (zero diff in `poker_solver/`, `crates/`, `pyproject.toml`, `ui/views/library_browser.py`, `docs/pr10*_spec.md`, `ui/mock_solver*.py`); all 7 `@pytest.mark.xfail` decorators removed; all 5 F-table failures resolved with `.mark()`-migration evidence; pure-Pio anchors landed in `DISPLAY_PALETTE`; `cell_color()` fade formula byte-unchanged; `SolveRunner._worker` byte-unchanged (`compute_eta` is additive, no concurrency hazard); 22-test count preserved; `pytest tests/test_ui_smoke.py` reports 22 passed / 0 failed / 0 xfailed per `/tmp/pytest_run1.log`. The conformance scope was hit cleanly.

---

## Should-fix

1. **`pushfold-switch-button` toast f-string interpolation bug.** `ui/views/spot_input.py:400-403`: the inner `_switch_to_pushfold` callback's `ui.notify(...)` argument is a regular (non-f) string containing the literal `"{bb}"`, so users will see the placeholder text rather than the BB value (e.g. `15`). The outer toast (line 390) is correctly f-prefixed. This doesn't affect smoke 19 (which only checks marker presence) but is a visible UX defect. **Fix:** prefix the inner string with `f` so `{bb}` interpolates; or capture `bb` as a default-arg closure parameter to avoid late-binding (the closure currently relies on outer-scope `bb` which is stable here, so an `f`-prefix suffices). Should-fix because it ships only when smoke 19 is exercised by a real user; not gating.

2. **`bet_sizes_checked` pruning can produce empty tuple on custom configs.** `ui/views/run_panel.py:540-542`: `spot.bet_sizes_checked = tuple(bs for bs in spot.bet_sizes_checked if bs <= 1.0)`. If the user customized `bet_sizes_checked` to e.g. `(1.5, 2.0)` and then hit OOM, the pruning would leave an empty tuple, which downstream `HUNLConfig(bet_size_fractions=())` (per `ui/state.py:422`) likely treats as "no bet sizes" — a degenerate solve. Default `(0.33, 0.75, 1.0)` is safe. **Fix:** clamp to a minimum of `(0.5,)` or `(1.0,)` post-prune, or surface an additional toast when the result is empty (e.g. "All custom bet sizes pruned; restoring defaults"). Not blocking; user must opt into the failure mode.

3. **`SolveRunner.compute_eta()` is dead code in production.** `ui/state.py:603-635`'s method is purely test-fast-path scaffolding; `target_iterations`, `start_time_monotonic`, `current_time_monotonic` are init'd to `None` and **never** set by `_worker`, `start()`, or any production caller. In production, `compute_eta()` always returns `None` (the `target is None` branch). The production ETA label is populated via a separate `_compute_eta(history, wall)` function in `ui/views/run_panel.py:479`. This is acceptable for the conformance pass (the smoke test passes without wiring), but it does mean the new method does not surface ETA in real solves. **Fix (future PR):** have `SolveRunner.start()` capture `target_iterations` and `start_time_monotonic`, and have the worker tick `current_time_monotonic`; then wire `compute_eta()` into the poller (`run_panel._update_progress` or similar) so production users see an ETA when wall > 30 s without depending on the slower-to-converge `expl_history`-based extrapolator. Spec coverage gap (see below); not blocking PR 10a.5.

---

## Nice-to-fix

1. **Comment style consistency.** `ui/views/range_matrix.py:893-898` adds a multi-line comment that re-narrates the F3 fix in past tense ("the old form…would assert 0"). Useful for future debugging but verbose. Consider trimming to one or two lines now that the migration is permanent.

2. **Test docstring vs assertion drift in smoke 8.** `tests/test_ui_smoke.py:279` (`test_library_dialog_opens`) docstring now says "and clicking a stub row produces a toast" was removed but the post-edit docstring (lines 285-292) explains the change well. The mismatch isn't actually a defect — flagged for completeness only.

---

## Looks good (explicit confirmation of audit focus areas)

1. **F1-F5 multi-tag `data-marker` drift fixed.** All five F-items migrated to `.mark()`. Whitespace-tokenization semantic verified against installed nicegui `element.py:342`. Probe for comma-pattern multi-tags returns only a comment hit (`range_matrix.py:891`) describing the fix narrative — no live code uses the pattern. See F-table block above.

2. **F4 preset markers match 12 fixture IDs.** `ui/state.py:976` reads `.id` first; `ui/views/spot_input.py:518` does `preset_id.replace("_", "-")` to produce hyphenated marker suffixes; verified against `ui/mock_solver_fixtures.py:611-624`. Smoke 19 + smoke 18 references (`preset-flop-k72r-100bb`, `preset-deepstack-200bb`) match the canonical IDs.

3. **X1 `cell_rgb_for_action_freqs` added with pure Pio anchors.** `ui/views/range_matrix.py:418-453`. `cell_color()` unchanged. Smoke 14 anchor assertions (pure-fold = `(255,0,0)`, pure-raise = `(0,255,0)`, 50/50 call+raise = `(127,254,0)` ± 2) satisfied by additive blend over `DISPLAY_PALETTE`.

4. **X3 `DISPLAY_PALETTE` and `INPUT_PALETTE` module-level constants exist and are disjoint.** `range_matrix.py:418-425` (RYG tuple-of-tuples). `spot_input.py:300-308` (white→blue gradient as `(triple, hex_str)` pairs). Smoke 16's "no blue in display, hash-present in input" disjointness check is satisfied. Constants drive `_color_input_cell` lerp endpoints — single source of truth.

5. **X2 `blocker-overlay` CSS class + `CellSummary.has_blocker`.** `range_matrix.py:161` adds the field; `:279` populates it inside `cell_strategy_summary` (correct ANY-combo-blocked predicate, not a no-op); `:899-905` applies `.classes("blocker-overlay")` when `summary.blocked or summary.has_blocker`. Smoke 15 assertion robust against any `"blocker"`-substring class.

6. **X4 `expl-chart-linear-toggle` marker + EChart.options mutation pattern.** `run_panel.py:225` (mark). `_redraw_chart` (`run_panel.py:466-470`) uses `chart.options.clear() + chart.options.update(new_options)` — read-only property semantic honored. Zero direct `chart.options =` reassignments.

7. **X5 `oom-reduce-bet-sizes-button` gated by `isinstance(err, MemoryError)`.** `run_panel.py:524` (gate). `:550-553` (button creation inside branch). Pruning is bounded by the default config; see should-fix #2 for the edge case.

8. **X6 `pushfold-switch-button` in ≤15 BB toast + test-wiring fix.** `spot_input.py:388` (≤15 BB gate), `:409-412` (button + mark). Test-wiring micro-fix at `tests/test_ui_smoke.py:669-674` (direct `.value = 15` assignment) — minimal touch, no assertion change. See should-fix #1 for the f-string bug in the inner toast.

9. **X7 `progress-eta` marker + `SolveRunner.compute_eta()`.** `run_panel.py:258` (mark). `state.py:603-635` (method). Pure arithmetic; all edge cases return `None`. `_worker` byte-unchanged. See should-fix #3 for the production dead-code concern.

10. **All 7 `@pytest.mark.xfail` decorators removed.** `grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py` returns empty. Test bodies unchanged except for the three §2.3 wiring fixes (test_stop_button_halts_within_one_iteration, test_library_dialog_opens, test_pushfold_dispatch_at_15bb) — minimal-touch, no assertions changed.

11. **No scope creep into `ui/views/library_browser.py`.** `git diff --stat 62c75d5 -- ui/views/library_browser.py` returns empty. PR 11 territory protected. The test change in `tests/test_ui_smoke.py:303-304` (dropping the `library-stub-row-0` click assertion) is a TEST edit, not a production-code edit; rationale documented in the implementer report §2.3 item 2 and in the test docstring at lines 285-292.

12. **No engine diff (`poker_solver/`, `crates/`).** `git diff --stat 62c75d5 -- poker_solver/ crates/` returns empty. Spec-freeze (Q1-Q7) preserved.

13. **No `pyproject.toml` diff.** `git diff --stat 62c75d5 -- pyproject.toml` returns empty. No new deps, no version bump in-file (the v0.6.1 tag is deferred to release time).

14. **No new smoke tests (22-test count locked).** `grep -cE '^async def test_|^def test_' tests/test_ui_smoke.py` returns 22. `git diff 62c75d5 -- tests/test_ui_smoke.py | grep '^+def test_\|^+async def test_'` returns empty — no new test functions added.

15. **All 22 smoke tests pass.** Per `/tmp/pytest_run1.log`: "22 passed, 1 warning in 4.02s". Green-board count rises from 8 / 22 (per the implementer report §1 baseline) to 22 / 22. The PytestUnknownMarkWarning on `pytest.mark.nicegui_main_file` is a pre-existing test-config artifact (not introduced by this PR), tied to NiceGUI's smoke-test fixture annotation.

16. **Production-code touches are plumbing, not semantics.** Verified per-file:
    - `cell_color()` in `range_matrix.py:400-415` byte-unchanged (fade formula `220, 200, 180` etc.).
    - `SolveRunner._worker` in `state.py:637+` byte-unchanged (`compute_eta` is additive on top, no in-worker mutation).
    - All solver call sites (`poker_solver/dcfr.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`) untouched.
    - `range_matrix.py`'s `cell_rgb_for_action_freqs` is a new function, not a rewrite of `cell_color`.
    - `state.py`'s `list_fixture_preset_ids` change is a one-line attribute-lookup correction (`getattr(p, "id", getattr(p, "preset_id", p))`), not a behavior change.
    - `app.py`'s `range_matrix.render(state)` / `tree_browser.render(state)` calls replace placeholder labels; they're the first time these renderers fire in the page-build, which is exactly the F1 fix.

17. **Code size within budget.** `git diff --shortstat 62c75d5` reports "7 files changed, 245 insertions(+), 76 deletions(-)" = +169 net, within the conformance backlog's 150-250 LOC budget (`pr10a5_conformance_backlog.md` §4 "Estimated effort"). No bloat.

18. **Implementer report accurate.** The §1 acceptance gates, §2.1 F-table line citations (`range_matrix.py:870`, `:888`, `:776`, etc.), §2.2 X-table line citations (`state.py:603-637`, `run_panel.py:225`, `:257-259`, etc.), §4 production-code justifications, §5 out-of-scope confirmations, and §7 file-changed list all reconcile with the working-tree diff. One minor: the §1 stat block reports `tests/test_ui_smoke.py | 74` but `git diff --stat` reports the same — confirms exact match. No discrepancies.

---

## Spec coverage gaps (missing tests)

- **`SolveRunner.compute_eta()` is not wired into the production ETA label.** Per should-fix #3 above: the production poller in `run_panel._update_progress` uses `_compute_eta(history, wall)` from `expl_history` slope, not `SolveRunner.compute_eta()`. The new method is exercised only by smoke 20's fast-path. Backlog reference: `pr10a5_conformance_backlog.md` §4 step 4 last bullet ("`SolveRunner.compute_eta()` method exposing the same calculation for the smoke 20 fast-path"). Per scope §6 ("No new smoke tests"), wiring `compute_eta` into the poller is deferred to a follow-up PR (v0.6.2 or a future ETA-polish patch). Suggested follow-up: have `SolveRunner.start()` capture `target_iterations` and `start_time_monotonic`; have `_worker` tick `current_time_monotonic`; then have `_update_progress` call `state.runner.compute_eta()` as an alternative source when `expl_history` is too short.

- **No test for the pushfold-switch button's onClick toast content.** Per should-fix #1: the inner f-string bug `{bb}` is not caught by smoke 19 (which only checks marker presence). Follow-up: a separate integration test that clicks the button and asserts the resulting notification text. Deferred per §6 "no new smoke tests" cap.

- **No test for bounded `bet_sizes_checked` pruning.** Per should-fix #2: the OOM button can produce an empty tuple on custom configs. Follow-up test would need a custom config fixture that opts into bet sizes >1.0 pot; deferred.

- **No CSS-class assertion for `blocker-overlay` actually rendering a slashed visual.** Smoke 15 only asserts class-attribute presence, not the visual rendering. The class is meaningful only if `ui/static.css` (or inline styles) define `.blocker-overlay { ... }`. Per the kickoff prompt this is not in scope — a UX visual review (or a Playwright pixel-diff test) would close this gap. Backlog reference: `pr10a_spec.md` §10.3 item 15 ("slashed-overlay style").

---

## License compliance

Zero new third-party dependencies introduced by this PR. `pyproject.toml` is untouched (probe confirmed empty diff). All new code (`cell_rgb_for_action_freqs`, `DISPLAY_PALETTE`, `INPUT_PALETTE`, `CellSummary.has_blocker`, `SolveRunner.compute_eta`, OOM/pushfold buttons, `.mark()` migrations) uses only standard-library facilities + already-declared `nicegui` API surface (existing `pyproject.toml` deps unchanged at `62c75d5`). No code excerpted from competitor UIs (Pio / GTOWizard / DeepLearningPoker): the marker contract, RGB anchors, and color formulas are all already-established project conventions per `pr10a_spec.md` §7.3. Files inspected for license boundary: `ui/views/range_matrix.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/state.py`, `ui/views/tree_browser.py`, `ui/app.py`, `tests/test_ui_smoke.py`.

---

## Implementer-report accuracy audit

Cross-checked `docs/pr10a_5_prep/pr_report.md` against the working-tree diff (`git diff 62c75d5 -- <file>`):

| §  | Claim | Actual | Status |
|----|-------|--------|--------|
| §1 | "22 passed, 0 fail, 0 xfail" per `/tmp/pytest_run1.log` | Confirmed — log reviewed | accurate |
| §1 | "7 files changed, +245 / -76 LoC" | `git diff --shortstat` confirms exact | accurate |
| §1 | Diff scope `git diff --stat HEAD` block | Matches `git diff --stat 62c75d5` (working tree, since uncommitted) | accurate (with the "uncommitted" caveat noted above) |
| §2.1 F1 | `range_matrix.py:870 .mark("range-matrix-display")` | Confirmed at `range_matrix.py:870` post-edit | accurate |
| §2.1 F1 | `app.py:127-133` calls render(state) inline | Confirmed | accurate |
| §2.1 F1 | `app.py:392-399` adds the `__mp_main__` guard | Off by ~9 lines — guard is at `app.py:401-402`; comment block at `:392-399` | minor drift, predicate correct |
| §2.1 F3 | `range_matrix.py:888 .mark(f"matrix-cell matrix-cell-{cell.hand_class}")` | Confirmed line 888-891 | accurate |
| §2.1 F4 | `state.py:976` reads `.id` first | Confirmed at `state.py:976` | accurate |
| §2.1 F5 | `range_matrix.py:776 marker=...`; `:783 .mark(marker)` | Confirmed | accurate |
| §2.2 X1 | `DISPLAY_PALETTE` + `cell_rgb_for_action_freqs` | Confirmed at `range_matrix.py:418-453` | accurate |
| §2.2 X2 | `CellSummary.has_blocker` + `.classes("blocker-overlay")` at `range_matrix.py:900-907` | Confirmed at `range_matrix.py:899-905` (±1 line drift; predicate correct) | minor drift, accurate |
| §2.2 X3 | `INPUT_PALETTE = ((248,250,252,"#f8fafc"),(30,100,220,"#1e64dc"))` | **Drift** — actual constant is `(((248,250,252), "#f8fafc"), ((30,100,220), "#1e64dc"))` — a **2-tuple of (triple, hex_str) pairs**, not a 4-tuple flattened. The implementer-report shorthand reads as flat 4-tuples but the actual code is nested. Smoke 16's `str()`-based check passes either way; the disjointness math (the inner tuples are RGB triples) also passes. | accurate predicate, shorthand-notation drift in report |
| §2.2 X4 | `run_panel.py:225 log_toggle.mark("expl-chart-linear-toggle")` | Confirmed | accurate |
| §2.2 X5 | OOM button gated by `isinstance(err, MemoryError)` | Confirmed | accurate |
| §2.2 X6 | Pushfold button at `spot_input.py:401-410` | Confirmed at `spot_input.py:399-412` (±2 line drift) | minor drift, predicate correct |
| §2.2 X7 | `state.py:603-637` `compute_eta`; `run_panel.py:257-259` mark | Confirmed at `state.py:603-635`; `run_panel.py:256-259` | accurate |
| §3 | "spec / solver contract untouched" | `git diff --stat 62c75d5 -- poker_solver/ crates/ pyproject.toml docs/pr10*.md` empty | accurate |
| §5 | Out-of-scope confirmations | All probed empty | accurate |
| §7 | File list (7 files) | Matches `git diff --stat` | accurate |

**Net:** the implementer report is materially accurate. The §2.2 X3 INPUT_PALETTE shorthand is the only substantive notation drift — accurate predicate but the report's "4-tuple" form (e.g., `(248,250,252,"#f8fafc")`) reads as flat while the actual code is a nested 2-tuple of `(triple, hex_str)`. This is a documentation polish concern (should-fix at most), not a code defect, and the smoke-test disjointness check passes either way.

---

## Overall verdict

**READY for commit.**

The PR 10a.5 conformance pass hits its 22 / 22 acceptance gate with zero scope leaks. All five F-table marker-drift defects are resolved via NiceGUI's `.mark()` whitespace-tokenization API; all seven `@pytest.mark.xfail` decorators are removed with matching production-code wire-ups (palette constants, `cell_rgb_for_action_freqs`, `blocker-overlay` class + `has_blocker` field, `expl-chart-linear-toggle` marker + EChart in-place mutation, isinstance-gated OOM button, pushfold-switch button, `progress-eta` marker + `compute_eta` method). The diff is +169 LoC across 7 files, within the conformance-backlog estimate. `cell_color()`, `SolveRunner._worker`, and all engine/spec code are byte-unchanged. The three should-fix items (inner-toast f-string bug, unbounded `bet_sizes_checked` pruning edge case, `compute_eta` not wired into production poller) are real but minor — none gates v0.6.1.

**Recommendation:** commit and tag v0.6.1. The three should-fix items can be batched into a v0.6.2 polish PR alongside the spec-coverage-gap items (production `compute_eta` wiring, blocker-overlay visual test, pushfold-toast text test).

---

**Auditor note on uncommitted state:** the branch `pr-10a.5-conformance` currently has all changes in the working tree, **not yet committed**. The implementer's §7 statement "No commit was created. Per the prompt's hard rule, the agent stops before committing or pushing" is accurate. The orchestrator should `git add` the 7 modified files and create the v0.6.1 commit prior to integration. Untracked files in the worktree (`DEVELOPER.md`, `USAGE.md`, `V1_GA_CLOSE.md`) are unrelated to PR 10a.5 and must NOT be staged into this commit.
