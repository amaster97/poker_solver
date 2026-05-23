# PR 24a — Implementer Notes (GUI Gate 2, first half)

**Branch:** `feature/pr-24a-gui-rvr-slider`
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-24a-gui-rvr-slider`
**Base:** `origin/main` at `dc3df6c` (v1.5.0)
**Commit count:** 4 commits on top of v1.5.0
**Date:** 2026-05-23

---

## 1. What landed

Per the spec at `docs/pr_proposals/v1_5_pr_24a_implementer_prompt.md` §A:

### §3.2 Range-vs-range solve mode (`rvr-mode-toggle`)
- `Spot.rvr_mode: bool = False` field added (`ui/state.py`).
- `Spot.to_rvr_call_args() -> tuple[HUNLConfig, list[HandClass], list[HandClass]]`
  built; returns `initial_hole_cards=()` config plus deduplicated hand-class
  lists derived from `RangeWithFreqs.base_range` combos (frequency > 0
  filter; first-seen ordering for determinism).
- `SolveRunner.start(...)` gained `rvr_mode`, `rvr_hero_range`,
  `rvr_villain_range`, `rvr_hero_player` kwargs; routes through a new
  `_run_rvr_path` worker that calls `poker_solver.range_aggregator.solve_range_vs_range`
  and writes the result to `SolveRunner.rvr_result: RangeVsRangeResult | None`.
- `ui/app.py:_on_solve` branches on `spot.rvr_mode` and dispatches through
  `Spot.to_rvr_call_args()`.
- `ui/views/run_panel.py` adds the `rvr-mode-toggle` (Concrete /
  Range-vs-range) widget with the spec's tooltip text.
- `ui/views/range_matrix.py` adds `_build_grid_summaries_rvr` that
  renders `RangeVsRangeResult.per_class_strategy` directly onto the 13×13
  grid using the Pio R/Y/G bucketing convention (`fold` → fold;
  `check`/`call` → call; `bet_*`/`raise_*`/`all_in` → raise). Classes
  absent from the result but present in the input range render as
  blocked; classes absent from the input range render as out-of-range.

### §3.3 `hero_player` selector (`hero-seat-toggle`)
- `Spot.hero_player: int = 0` field added.
- `ui/views/spot_input.py:_render_ranges_section` emits a `hero-seat-toggle`
  (P0 / P1) above the existing P0/P1 tab strip with the spec's tooltip.
- `ui/views/range_matrix.py:_selected_player` extended to swap rows when
  `hero_player == 1` (see §3 below for the swap-status finding).

### §3.4 "True Nash" vs "blueprint" chart subtitle
- `_chart_options(quality_label=...)` renders the label as the echarts
  `subtext` field with reduced top padding to accommodate the subtitle.
- `_chart_quality_label(state)` maps `(rvr_mode, backend)` to the three
  labels per spec §3.4:
  - concrete + Rust: `"true Nash (Rust best-response walk, v1.3.2)"`
  - concrete + Python: `"true Nash (Python best-response walk, slow)"`
  - RvR (any backend): `"blueprint approximation (Pluribus-style aggregator, v1.3.0; not Nash)"`
- `_redraw_chart` now takes `state=...` and recomputes the label every
  refresh so mid-session RvR-toggle flips immediately update the chart.

### §3.7 Exploitability slider with 4 tiers (`tier-slider`)
- 4-tier toggle (Draft / Standard / Tight / Library) with the measured
  iter ladder from `docs/v1_5_slider_tier_defaults_measured.md` §1:
  - Draft: 200 iters, 10.0 mBB/pot target (1% pot)
  - Standard: 500 iters, 5.0 mBB/pot target (0.5% pot)
  - Tight: 1000 iters, 2.5 mBB/pot target (0.25% pot)
  - Library: 2000 iters, 1.0 mBB/pot target (0.1% pot)
- Read-only `tier-target-label` ("Standard: 500 iters / target 5.0
  mBB/pot") tracks the active tier.
- `Custom (advanced)` `ui.expansion` retains the legacy
  `iterations-input` + `target-exploitability-input` widgets as
  override. Tier changes auto-populate these so the bare Solve click
  uses the tier's recommended values.
- `_wrap_solve` converts the tier mBB/pot target to BB/pot units
  (`/1000.0`) before passing through `state.runner._pending_target_expl`
  to `SolveRunner.start(..., target_exploitability=...)`.
- Tooltip text is the spec's "Preliminary tier defaults; final
  measured values land in PR 24b." (no extrapolated claims; the
  measured iter ladder is recorded in the measurement doc, not the
  tooltip).

### Smoke tests (`tests/test_ui_pr24a.py`)
**7 smokes — verdict GREEN (7/7 pass; 5.89s combined with existing 28
UI smokes).**

1. `test_rvr_toggle_routes_to_aggregator` — sets `rvr_mode`, clicks
   Solve, monkey-patches `solve_range_vs_range`, asserts the patched
   stub was called exactly once and the runner finished.
2. `test_rvr_result_renders_169_cells` — populates a synthetic
   `RangeVsRangeResult` on `runner.rvr_result`, status="done", and
   asserts the matrix re-renders 169 cells.
3. `test_hero_seat_toggle_writes_state` — verifies the toggle marker is
   present and flipping `state.current_spot.hero_player` is observable.
4. `test_rvr_hero_player_one_yields_defender_position` —
   `Spot.to_rvr_call_args()` with `hero_player=1` returns swapped hero
   /villain ranges; locks the `RangeVsRangeResult.position` defender
   convention.
5. `test_tier_slider_defaults_match_measurement_doc` — locks the
   `_TIER_INDEX` dict against the measurement doc §1 numeric outputs
   and the mBB→BB conversion table.
6. `test_chart_subtitle_says_blueprint_in_rvr_mode` — asserts the four
   label paths per spec §3.4 and that the echarts `subtext` field is
   populated.
7. `test_to_rvr_call_args_swaps_hero_villain_on_hero_player_change` —
   additional UI-side defensive lock on the §3.3 hero/villain swap
   contract.

Existing 28 UI smokes (`tests/test_ui_smoke.py`) all green; no
regression.

---

## 2. Sequencing / commit cadence

4 commits on `feature/pr-24a-gui-rvr-slider`:

| # | SHA | Subject |
|---|-----|---------|
| 1 | `5d54d0c` | PR 24a (1/4): wire range-vs-range + hero_player into ui.state |
| 2 | `52f07a0` | PR 24a (2/4): add RvR toggle + 4-tier slider + chart subtitle |
| 3 | `9ba6c4e` | PR 24a (3/4): hero seat selector + RvR matrix render + hero swap |
| 4 | (this commit) | PR 24a (4/4): smoke tests + implementer notes |

---

## 3. Deviations from spec / orchestrator-flagged items resolved

### 3.1 §8 Q5 — `range_matrix.py:_snapshot_player` / `_selected_player` hero swap status

**Orchestrator flag:** "the existing `_snapshot_player` likely does NOT
consult `spot.hero_player`."

**Status on read: CONFIRMED — swap was NOT present in the v1.5.0
baseline.**

The two relevant functions on the v1.5.0 baseline:

- `_snapshot_player(snapshot)` reads `snapshot.player_to_act` or
  `state.cur_player` — game-state derived, unaware of `spot.hero_player`.
- `_selected_player(state)` returned `state.selected_player_for_input`
  directly — unaware of `spot.hero_player`.

**Fix applied in PR 24a (commit 3, `range_matrix.py`):** Extended
`_selected_player` to swap when `hero_player == 1`. `_snapshot_player`
is left alone because it operates on game-state semantics (which engine
slot is to act), not display-tab semantics (which side the user wants
to see). The matrix's `_build_grid_summaries` consumes
`_selected_player` (not `_snapshot_player`), so the front-tab swap
lands correctly.

`hero_player == 0` is a no-op, preserving every existing smoke test.

### 3.2 Tier slider defaults — iter ladder vs mBB/pot interpretation

The task brief calls out the measured iter ladder
(`200/500/1000/2000`) from the measurement doc as the authoritative
defaults, while the spec body still references the mBB/pot stub values
(`10/5/2.5/1`). The measurement doc §8 itself notes both should ship:
the iter ladder is the operative wall-clock differentiator (the DCFR
stack converges much faster than the mBB/pot targets imply on every
measured fixture), and the mBB/pot labels are kept as nominal targets
per PLAN.md §1.

**Implementation:** Both are encoded in `_TIER_INDEX`. The tier's iters
populate the custom iterations input; the mBB/pot value populates the
target-expl input. The `tier-target-label` shows both:
`"Standard: 500 iters / target 5.0 mBB/pot"`. Honest framing — the user
sees the actual wall-clock dimension (iters) and the nominal accuracy
dimension (mBB/pot) without either being hidden.

The "preliminary" framing is retained in the tooltip per the
no-extrapolate rule because PR 24b is expected to fold in the
measurement doc's §8 Open Question 1 decision (Option A vs Option B
relabel).

### 3.3 RvR rendering trigger — status-gated, not live

The renderer only consumes `runner.rvr_result` when
`runner.status in ("done", "stopped")`. Showing partial mid-class output
during a live RvR solve would produce a "matrix that fills in as classes
finish" UX which is jittery — half the grid blank, half populated. The
status gate makes the matrix flip atomically once the aggregator returns.

This is a minor scope-tightening from the spec's bullet "render against
`RangeVsRangeResult.per_class_frequencies`" — same render path, but
guarded behind a finished-solve check. The chart still shows live
class-completion progress via the aggregator's `on_progress` callback
(see `_run_rvr_path`); only the matrix waits for the final result.

### 3.4 `_pending_target_expl` plumbing — runner attribute vs SolveSession field

To avoid widening `SolveSession` for a single PR 24a-scoped field, the
tier slider's mBB/pot target is stored on a runner-side attribute
(`SolveRunner._pending_target_expl: float | None`) that
`ui/app.py:_on_solve` reads. This kept the diff narrow and avoided
cross-cutting changes to PR 11's library-serialized `SolveSession`.

---

## 4. Known issues / blockers

- **None UI-side.** All 35 UI smokes (28 existing + 7 new) green.
- **Pre-existing baseline failures (not introduced by PR 24a):** 5
  `tests/test_range_vs_range_aggregator.py` tests fail because the
  worktree doesn't have a built `poker_solver._rust` module. Confirmed
  against `origin/main` baseline (same 5 failures). Out of scope for
  this PR.
- **Pre-existing mypy errors:** 6 errors in `poker_solver/*` and
  `ui/views/library_browser.py` exist on `origin/main`; none added by
  PR 24a. Audited by stashing the PR 24a diff and re-running mypy.
- **ruff baseline:** 5 files had pre-existing format drift on `origin/main`
  (run-panel, range-matrix, spot-input, app, library-browser); PR 24a
  files were formatted before commit. `ruff check ui tests/test_ui_pr24a.py`
  returns clean.

---

## 5. Sequencing notes for PR 24b

PR 24b should:

1. **Swap `tier-slider` tooltip wording** away from "preliminary" once
   the measurement doc §8 Open Question 1 resolves (Option A / B
   labels). The widget structure is final; only the tooltip text needs
   updating.
2. **Add node-locking editor** (spec §3.5). The
   `SolveRunner._pending_target_expl` attribute pattern from PR 24a is a
   reusable scaffold for `_pending_locked_strategies`; alternatively,
   PR 24b can widen `SolveSession` once two such fields exist (clean
   threshold).
3. **Add asymmetric `initial_contributions`** (spec §3.6). Touches
   `Spot.to_hunl_config()` lines 425-437; coordinate with v1.4.1 merge
   ordering per spec §8 Q2.
4. **Range editor polish** (spec §3.1). Independent of the above.

The PR 24a `hero-seat-toggle` + `Spot.hero_player` are stable surfaces
PR 24b can build on without modification.
