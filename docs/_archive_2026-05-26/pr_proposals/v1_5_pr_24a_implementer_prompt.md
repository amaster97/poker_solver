# PR 24a — Implementer Prompt (paste-ready)

**PR scope:** RvR solve mode + `hero_player` selector + 4-tier exploitability slider (stub defaults) + "true Nash" vs "blueprint" chart subtitle labels.

**Closes:** v1.3.0–v1.3.2 GUI surface gaps (per `docs/pr_proposals/v1_5_gui_surface_gaps.md` §3.2, §3.3, §3.4, §3.7).

**Dependencies:** None outside engine. Engine code (v1.3.0–v1.3.2) already shipped 2026-05-23. Does **NOT** depend on v1.4.1 in flight.

**Expected ship version:** v1.5.0.

**Smoke tests expected:** ~6 (per spec §6 PR 24a sub-section).

**Conflict surface:** Touches `ui/views/run_panel.py`, `ui/views/spot_input.py`, `ui/views/range_matrix.py`, `ui/state.py`. Does NOT touch `_rust.so`, no Rust changes; clippy not gated.

---

## A. Paste-ready agent prompt body

```
You are implementing PR 24a (GUI v1.3.0+ surface gaps — RvR + hero_player + slider + chart labels) for the poker_solver project.

REQUIRED READING BEFORE WRITING ANY CODE:
1. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_gui_surface_gaps.md — full spec; you implement §3.2, §3.3, §3.4, §3.7 (the 24a bundle per §6).
2. /Users/ashen/Desktop/poker_solver/PLAN.md §1 — locked exploitability-tier semantics + industry-standard guesses for stub defaults.
3. /Users/ashen/Desktop/poker_solver/poker_solver/range_aggregator.py — confirm `solve_range_vs_range` signature at line 208 and `hero_player` default at line 217.
4. /Users/ashen/Desktop/poker_solver/ui/state.py — read `Spot` (332-487) and `SolveRunner.start` (567-606) to understand how the worker dispatches.
5. /Users/ashen/Desktop/poker_solver/ui/views/run_panel.py — read 130-180 (iterations + target-expl block) and 415-451 (`_chart_options`).
6. /Users/ashen/Desktop/poker_solver/ui/views/spot_input.py — read 195-263 (player tabs + matrix input).
7. /Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py — read top of file to confirm whether `_snapshot_player` reads `spot.hero_player` (orchestrator flagged as suspect NOT).
8. /Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py — reuse the NiceGUI `User` fixture pattern for new smokes.

WORKTREE & BRANCH:
- Worktree: /Users/ashen/Desktop/poker_solver_worktrees/pr-24a-gui-rvr-slider
  (create via `git worktree add` from your worktree management; do NOT branch-switch in the main working tree — see user memory feedback_no_concurrent_branch_ops).
- Branch: feature/pr-24a-gui-rvr-slider
- Base: origin/main at the most recent main HEAD when you start. (24a is independent of v1.4.1.)

IMPLEMENTATION SCOPE (4 features):

(1) RvR solve mode (spec §3.2):
    - Add `Spot.rvr_mode: bool = False` to ui/state.py (in the Spot dataclass region, lines 332-487).
    - Add `Spot.to_rvr_call_args() -> tuple[HUNLConfig, list[HandClass], list[HandClass]]` that extracts hand-class lists from `self.ranges[0]` and `self.ranges[1]`.
    - In ui/views/run_panel.py add `ui.toggle(["Concrete", "Range-vs-range"], value="Concrete")` near the backend toggle (line 174). Mark it `rvr-mode-toggle`. Tooltip per spec §3.2: "Slower aggregator pass; honest framing — see Plan C Stage C1."
    - In ui/state.py `SolveRunner.start` (lines 567-606): branch on `spot.rvr_mode`. When True call `poker_solver.solve_range_vs_range(config, hero_range, villain_range, iterations=N, backend=..., hero_player=spot.hero_player, on_progress=...)`. When False keep existing `solve(...)` path. Suppress the point-pair fallback warning (state.py:474-487) when RvR mode is on.
    - In ui/views/range_matrix.py: when `spot.rvr_mode`, render against `RangeVsRangeResult.per_class_frequencies` instead of point-pair output. Add a tab strip "P0 (aggressor) | P1 (defender)" in the matrix region. If integrating this is large, document in the PR description and gate the matrix re-render behind a follow-up if-and-only-if necessary — but prefer to ship it.

(2) hero_player selector (spec §3.3):
    - Add `Spot.hero_player: int = 0` field in ui/state.py.
    - In ui/views/spot_input.py between line 209 (tab strip) and 210 (tab panels): add `ui.toggle(["P0", "P1"], value="P0")` labeled "Hero seat:" with tooltip per spec §3.3.
    - Wire its on_value_change to set `state.current_spot.hero_player`.
    - In ui/views/range_matrix.py: when `spot.hero_player == 1`, swap rendered rows so Hero is shown on the front tab.

(3) Chart subtitle "true Nash" vs "blueprint" (spec §3.4):
    - Modify `_chart_options` in ui/views/run_panel.py (lines 417-451): accept a `quality_label: str` argument and render it as the echarts `subtext` field (alongside the existing `text` "Exploitability (mBB/pot)").
    - At `_redraw_chart` call sites (around line 453+), read `state.current_spot.rvr_mode` + `state.current_solve.backend` and pass the right label per spec §3.4 mapping:
        - concrete + Rust: "true Nash (Rust best-response walk, v1.3.2)"
        - concrete + Python: "true Nash (Python best-response walk, slow)"
        - RvR (any backend): "blueprint approximation (Pluribus-style aggregator, v1.3.0; not Nash)"

(4) Exploitability slider with 4 tiers (spec §3.7) — STUB DEFAULTS:
    - Replace the existing target-exploitability checkbox + number widget in ui/views/run_panel.py (lines 150-170) with:
        - `ui.toggle(["Draft", "Standard", "Tight", "Library"], value="Standard")` mark `tier-slider`.
        - Read-only `ui.label(f"Target: {tier_target_mBB} mBB/pot")` reflecting the active tier.
        - Keep the existing single-number `ui.number` as a "Custom..." override under an `ui.expansion` (advanced users).
    - STUB DEFAULTS (per spec §5 industry-standard guesses; tooltip "(preliminary; final values measured in PR 24b)"):
        - Draft = 10.0 mBB/pot (1% pot)
        - Standard = 5.0 mBB/pot (0.5% pot)
        - Tight = 2.5 mBB/pot (0.25% pot)
        - Library = 1.0 mBB/pot (0.1% pot)
    - On tier change, set `state.current_solve.target_exploitability = tier_target_mBB / 1000.0`.
    - Tooltip on the toggle: "Preliminary tier defaults; final measured values land in PR 24b."

ORCHESTRATOR-FLAGGED ITEM (resolve, don't ask):
- range_matrix.py "swap rows on hero_player change" — orchestrator flagged that the existing `_snapshot_player` likely does NOT consult `spot.hero_player`. Verify this when you read the file. If absent, add the swap. If present, no-op and note in the PR description.

CONSTRAINTS:
- READ-ONLY anywhere outside ui/ and tests/. Do not modify poker_solver/* code.
- Do not touch the _rust.so binary or any Rust source. No clippy run needed.
- Do not touch other worktrees or pull in changes from in-flight v1.4.1.
- Per user memory feedback_no_extrapolate: do NOT claim measured exploitability deltas anywhere. The slider tooltip MUST contain "preliminary."

TEST PLAN (~6 smoke tests in tests/test_ui_smoke.py or a new tests/test_ui_pr24a.py):
1. Toggle RvR on, click Solve, assert the worker called `solve_range_vs_range` (mock it).
2. Toggle RvR on + run small RvR spot, assert matrix renders a 169-cell strategy from RangeVsRangeResult (use the existing aggregator fixture if available; else mock).
3. Set hero_player=1 via toggle, assert `state.current_spot.hero_player == 1`.
4. Set hero_player=1 + RvR on, assert `RangeVsRangeResult.position == "defender"` (per range_aggregator.py:183-186).
5. Click "Draft" tier, assert `state.current_solve.target_exploitability == 0.010`. Repeat for Library → 0.001.
6. Toggle RvR on, redraw chart, assert echarts options dict subtext contains "blueprint approximation."

Use NiceGUI `User` fixture (pattern from tests/test_ui_smoke.py). If a smoke needs the engine, prefer mocking solve_range_vs_range to keep wall-clock low.

DELIVERABLE:
- Branch feature/pr-24a-gui-rvr-slider on the worktree.
- All new smoke tests pass.
- `scripts/check_pr.sh` clean (mypy + ruff at minimum; clippy not gated since no Rust touched).
- A PR-description draft committed under /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_pr_24a_report.md summarizing what was done + any deviations from the spec + confirmation of the range_matrix.py hero_player swap status.

DO NOT push to origin or open a PR. Hand the branch to orchestrator for audit + cherry-pick.

When done, report: (a) commit SHA, (b) smoke test count + names, (c) any spec deviations, (d) range_matrix.py hero_player swap status (added vs already-present).
```

---

## B. Implementation notes (orchestrator-supplied)

### B.1 Stub slider defaults (preliminary; final in 24b)

Per spec §5 and `PLAN.md` §1 industry-standard guesses:

| Tier | mBB/pot | % of pot | Source |
|------|---------|----------|--------|
| Draft | 10.0 | 1.0% | `PLAN.md` §1 |
| Standard | 5.0 | 0.5% | `postflop-solver` default |
| Tight | 2.5 | 0.25% | `PLAN.md` §1 |
| Library | 1.0 | 0.1% | GTOW Library tier |

**Tooltip text (verbatim):** "Preliminary tier defaults; final measured values land in PR 24b after the post-PR-10b measurement pass."

### B.2 Files to modify (extracted from spec)

- `ui/state.py` — add `rvr_mode`, `hero_player` fields to `Spot`; add `to_rvr_call_args()`; branch `SolveRunner.start` on `rvr_mode`.
- `ui/views/run_panel.py` — RvR toggle, slider widget, chart subtitle.
- `ui/views/spot_input.py` — Hero seat toggle above tab panels.
- `ui/views/range_matrix.py` — RvR rendering + hero_player row swap.
- `tests/test_ui_pr24a.py` (new) or extend `tests/test_ui_smoke.py`.

### B.3 Honest framing (per memory feedback_no_extrapolate)

- Slider tooltip MUST say "preliminary." Do not claim measured deltas.
- Chart subtitle labels MUST distinguish "true Nash" (concrete + Rust BR) from "blueprint approximation" (RvR aggregator). No fudging.

---

## C. Audit / check chain

1. `bash scripts/check_pr.sh` — mypy + ruff at minimum. Must pass.
2. Smoke tests: `pytest tests/test_ui_pr24a.py -v` (or `tests/test_ui_smoke.py -v` if extended). Must pass.
3. Manual quick check (optional, agent's call): `poker-solver ui` launches without crash, slider visible, RvR toggle visible.
4. No Rust changes → clippy not gated.
5. Orchestrator audit: spec compliance, no engine modifications, hero_player swap status documented.

---

## D. Ready-to-fan-out signal

This prompt is ready to paste into an `Agent()` call as soon as orchestrator decides 24a kicks off. No further orchestrator decisions required to start 24a — slider stub defaults are pre-resolved; 24a does not need the measurement pass.
