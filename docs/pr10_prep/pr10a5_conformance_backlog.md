# PR 10a.5 conformance backlog

**Date:** 2026-05-22
**Owner:** orchestrator (PR 10a.5 scope freeze)
**Status:** queued; runs parallel with PR 11.
**Source artifacts:** `docs/pr10_prep/audit_report_10a.md` (must-fix + should-fix tables); `tests/test_ui_smoke.py`; `docs/release_notes_v0.6.0.md` §"Honest caveats" item #5.

---

## 1. Background

PR 10a (`v0.6.0`, "Mock-first UI") shipped on 2026-05-22 with the
three Must-fix audit items resolved (Mock signature drift; library
header button marker; board picker card-int marker). Per the release
notes' fifth caveat, the **Should-fix audit gaps** were deferred to a
follow-up "conformance pass" labeled PR 10a.5.

The total backlog is **12 smoke-test items** across two buckets:

- **5 hard failures** introduced by Agent B's view-side marker
  enumeration not matching the audit-prompt contract (caught at Agent
  C's smoke-test integration run); these tests fail outright, not via
  `xfail`.
- **7 `xfail`-decorated tests** (tests 14-20 in `test_ui_smoke.py`)
  representing UX surfaces the spec promises but no Agent ever wired
  up: blocker-overlay class, log-scale chart toggle, OOM remediation
  button, push/fold dispatch button, ETA banner, and two missing
  module-level constants (`cell_rgb_for_action_freqs`,
  `DISPLAY_PALETTE` / `INPUT_PALETTE`).

The 5 failures + 7 xfails do NOT block v0.6.0 (the audit verdict was
"READY post-must-fix"), but the smoke-test green-board count today is
**8 of 20** (test 1 plus the 5 §10.2 mock-coverage tests plus
`test_all_12_fixtures_load` and a couple unaffected §10.1 items).

---

## 2. Five hard failures (Agent B marker drift)

Caught at Agent C's smoke-test integration run after the must-fix
follow-up commits landed. Audit anchor: `audit_report_10a.md`
Should-fix #3 first bullet ("Static grep confirms the following test-
required markers are **not** present...").

| # | Smoke test | File:line | Failure mode | Audit anchor |
|---|------------|-----------|--------------|--------------|
| F1 | `test_page_renders_without_exception` (smoke 1) | `tests/test_ui_smoke.py:92-107` | Multi-tag `data-marker=matrix-cell,matrix-cell-AKs` pattern at `ui/views/range_matrix.py:844` does not match NiceGUI's `User.find(marker=...)` single-tag lookup; matrix cells may also fail to be found by tests 7, 15. | Should-fix #3 bullet 1 |
| F2 | `test_combo_to_cell_mapping_no_off_by_one` (smoke 7) | `tests/test_ui_smoke.py` §10.1 item 7 | Same multi-tag pattern — `user.find(marker="matrix-cell")` won't resolve the comma-separated `data-marker` props string. | Should-fix #3 bullet 1 |
| F3 | `test_range_matrix_renders_169_cells` (§10.1 item 6) | smoke 6 | Same root cause — the per-cell marker enumeration uses the multi-tag pattern; `len(user.find(marker="matrix-cell").elements) == 169` returns 0. | Should-fix #3 bullet 1 |
| F4 | spot-input preset marker mismatch (smoke 5 / one of the §10.2 group) | `ui/views/spot_input.py` preset markers | Agent B / Agent A preset marker enumeration drifts from the 12 fixture IDs Agent C generates; e.g., `preset-flop-k72r-100bb` is in test, but spot_input may emit `preset-flop-k72r` truncated form. | Should-fix #3 bullet 1 |
| F5 | A second per-cell marker / inspector strip drift (`combo-inspector-row-AA` etc.) | `ui/views/range_matrix.py:735` | Inspector-strip per-row marker uses the same multi-tag-in-props pattern; click-to-inspect smoke step won't resolve a single row. | Should-fix #3 bullet 1 |

**Likely cause (per prompt hypothesis):** Agent B treated `data-marker`
as a comma-separated taglist (CSS-class style) rather than NiceGUI's
single-marker prop. The fix is two-line in `ui/views/range_matrix.py`
(emit two separate `.props("data-marker=...")` chains, or use the
NiceGUI `.mark(...)` shorthand which writes a single-value attribute).

Note: the audit prompt characterized the cause as "Agent B used
`matrix-region` instead of `range-matrix-display`" — direct grep
confirms both `range-matrix-display` (`ui/views/range_matrix.py:828`)
and `tree-browser` (`ui/views/tree_browser.py:608`) markers ARE
present. The actual surface-level drift is the comma-separated
multi-tag pattern at lines 735, 844 — not a top-level marker name
switch. Documenting both possibilities so the PR 10a.5 agent can
verify on first smoke run.

---

## 3. Seven xfailed tests (`@pytest.mark.xfail` decorators)

All seven carry the reason string `"PR 10a.5 conformance pass: missing
marker/constant per audit_report_10a.md should-fix N (...)"`. Source
listing for the decorators: `tests/test_ui_smoke.py:452, 498, 531,
580, 620, 659, 683`.

| # | Smoke test | xfail reason | Audit anchor | Spec anchor |
|---|------------|--------------|--------------|-------------|
| X1 (smoke 14) | `test_range_matrix_color_blend_matches_pio_convention` | Missing `cell_rgb_for_action_freqs(fold, call, raise_) -> (r, g, b)` adapter in `ui/views/range_matrix.py`; existing `cell_color()` returns a CSS string with anchors `(220, 40, 40)` not `(255, 0, 0)`. | Should-fix #1 | §10.3 item 14; §7.3 Pio RYG anchors |
| X2 (smoke 15) | `test_blocker_cells_show_slashed_overlay` | Missing `blocker-overlay` CSS class on blocked matrix cells; `cell_color()` returns faded-grey but emits no element-level class. Also depends on F1/F2 marker-drift fix. | Should-fix #3 bullet 2; §spec coverage gap §4.4 | §10.3 item 15 |
| X3 (smoke 16) | `test_input_matrix_palette_disjoint_from_display_palette` | Missing module-level `DISPLAY_PALETTE` / `STRATEGY_PALETTE` constant in `ui/views/range_matrix.py`; missing `INPUT_PALETTE` / `RANGE_INPUT_PALETTE` in `ui/views/spot_input.py`. | Should-fix #2 | §10.3 item 16; principle 4 (color minimalism, palettes disjoint) |
| X4 (smoke 17) | `test_chart_default_log_scale` | Missing `expl-chart-linear-toggle` marker on the `Log scale` checkbox at `ui/views/run_panel.py:221-224`; one-line marker addition. | Should-fix #3 bullet 3; spec coverage gap §7.3 | §10.3 item 17 |
| X5 (smoke 18) | `test_oom_failure_shows_remediation_notification` | Missing `oom-reduce-bet-sizes-button` marker; `_show_error` in `ui/views/run_panel.py:506` doesn't surface a §6.5 "Reduce bet sizes" remediation button when `runner.error` is `MemoryError`. | Should-fix #3 bullet 4; spec coverage gap §6.5 | §10.4 item 18; §6 edge #5 |
| X6 (smoke 19) | `test_pushfold_dispatch_at_15bb` | Missing `pushfold-switch-button` marker on the ≤15 BB warning toast at `ui/app.py:294-302` / `ui/views/spot_input.py:373-380`. | Should-fix #3 bullet 5; spec coverage gap §6.4 | §10.4 item 19; §6 edge #4 |
| X7 (smoke 20) | `test_long_solve_eta_appears_after_30s` | Missing `progress-eta` marker on the ETA label in `ui/views/run_panel.py:469` (ETA is computed but never marked); also missing `SolveRunner.compute_eta()` method for the fast-path branch of the test. | Should-fix #3 bullets 6-7 | §10.4 item 20; §6 edge #1 |

---

## 4. Recommended PR 10a.5 scope

Strict scope cap: this is a **conformance pass**, not a feature PR. No
new fixtures, no new tests, no Q-lock revisions.

1. **Fix Agent B marker enumeration to single-value form.** Replace
   the comma-separated `data-marker=foo,bar-baz` pattern at
   `ui/views/range_matrix.py:735` and `:844` with two separate
   `.props("data-marker=...")` chains, or use NiceGUI's `.mark(name)`
   shorthand. Verify via `User.find(marker="matrix-cell").elements`
   returning 169 cells. Confirm preset-marker IDs in `spot_input.py`
   match the 12 fixture IDs from `ui/mock_solver_fixtures.py`
   exactly (the F4 hypothesis above).
2. **Add `cell_rgb_for_action_freqs(fold, call, raise_) -> (r, g, b)`
   adapter** in `ui/views/range_matrix.py` using the **pure** Pio
   anchors (255 / 0 / 0 for red, 255 / 255 / 0 for yellow, 0 / 255
   / 0 for green) — NOT the existing `(220, 40, 40)` fade values.
   Keep `cell_color()` unchanged for CSS-string consumers.
3. **Add `DISPLAY_PALETTE` / `INPUT_PALETTE` module-level constants**
   to `ui/views/range_matrix.py` and `ui/views/spot_input.py`
   respectively. Both expose `(r, g, b)` triples; display = RYG,
   input = white→blue gradient. Audit-prompt suggests deriving the
   per-cell formula from the constants rather than the reverse.
4. **Wire the four UX surfaces** that audit Should-fix #3 enumerates:
   - `blocker-overlay` CSS class on blocked matrix cells (`.classes
     ("blocker-overlay")` when `summary.blocked` in `_cell_tag`).
   - `expl-chart-linear-toggle` marker on the `Log scale` checkbox.
   - `oom-reduce-bet-sizes-button` button in `run_panel._show_error`
     when `isinstance(runner.error, MemoryError)`.
   - `pushfold-switch-button` button in the ≤15 BB warning toast
     (PR 10a stub: emit a toast linking to PR 11 push/fold view).
   - `progress-eta` marker on the existing ETA label at
     `run_panel.py:469`.
   - `SolveRunner.compute_eta()` method exposing the same
     calculation for the smoke 20 fast-path.
5. **Remove the 7 `@pytest.mark.xfail` decorators** from
   `tests/test_ui_smoke.py:452, 498, 531, 580, 620, 659, 683` after
   the four wire-ups land.
6. **Confirm all 20 smoke tests pass** on a clean
   `pip install poker-solver[ui]` run. Acceptance gate: green-board
   count rises from 8 / 20 to 20 / 20.

**Estimated effort:** ~150-250 LOC across `ui/views/range_matrix.py`
(~80 LOC), `ui/views/spot_input.py` (~30 LOC), `ui/views/run_panel.py`
(~50 LOC), `ui/state.py` (~30 LOC for `compute_eta`), `ui/app.py`
(~15 LOC for the pushfold toast). Single-agent task; ~4-6 hours.

---

## 5. Sequencing: parallel with PR 11

**PR 10a.5 and PR 11 can run concurrently.** File-scope inspection:

| Scope | PR 10a.5 | PR 11 |
|-------|----------|-------|
| `ui/views/range_matrix.py` | edits | none expected |
| `ui/views/spot_input.py` | edits | none expected |
| `ui/views/run_panel.py` | edits | none expected |
| `ui/state.py` | small `compute_eta` add | none expected |
| `ui/app.py` | ~15-line pushfold toast wire | none expected |
| `ui/views/library_browser.py` | none | rewritten (PR 11 library mode) |
| `crates/`, `pyproject.toml` packaging | none | PyInstaller + DMG bundling |
| `poker_solver/library/` (new package) | none | new |
| `tests/test_ui_smoke.py` | xfail decorator removal only | none expected |
| `tests/test_library_*.py` | none | new |

Conflict surface is **only** `ui/views/library_browser.py` (PR 10a.5
does not touch it; PR 11 rewrites it from scratch — clean rename or
overwrite, zero merge risk). Recommendation: spawn PR 10a.5 on
its own feature branch (`pr-10a5-ui-conformance`) in parallel with
PR 11's three-agent fan-out. Merge order: whichever lands first; the
second merger does a no-op rebase.

**Risk on parallel run:** zero observed. The smoke-test xfail
removals do not gate PR 11's smoke tests (PR 11 adds its own
`test_library_*.py` set per `pr11_prep/pr11_spec.md` §10).

---

## 6. Out of scope for PR 10a.5

Listed for clarity so the agent doesn't drift:

- No Q-lock revisits (Q1-Q7 stay locked per `pr10a_spec.md` §0.1).
- No fixture changes (12 named spots stay frozen).
- No mock-solver signature changes (locked at v0.6.0 per
  `release_notes_v0.6.0.md` §1 caveat #2).
- No new smoke tests (the 20-test count is locked).
- No engine-side changes (`poker_solver/` zero diff; this PR is
  100% UI-side).
- No version bump beyond v0.6.1 patch (PR 10a.5 ships as v0.6.1; if
  scope creeps add a "scope review" gate).
