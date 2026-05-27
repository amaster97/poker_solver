# PR 24b — Implementer Prompt (paste-ready)

**PR scope:** Node-locking editor + asymmetric `initial_contributions` UI input + range editor polish (per-hand frequency dialog + preset library) + swap in measured slider tier defaults from the post-PR-10b measurement pass.

**Closes:** v1.4.0–v1.4.1 GUI surface gaps + §3.1 range-editor polish + §5 measured tier swap (per `docs/pr_proposals/v1_5_gui_surface_gaps.md` §3.5, §3.6, §3.1, §5).

**Dependencies — HARD BLOCKERS:**
1. **v1.4.1 engine merge must land first.** §3.6 asymmetric `initial_contributions` depends on the v1.4.1 engine PR (asymmetric contributions design at `docs/pr_proposals/v1_4_asymmetric_contributions.md`). 24b MUST NOT start until v1.4.1 is merged to main.
2. **Slider tier measurement pass must produce `docs/pr_proposals/v1_5_slider_tier_defaults_measured.md`** before §5 swap can complete. If measurement pass is incomplete, 24b can still ship §3.5 + §3.6 + §3.1 with the §5 swap deferred to a fast follow-up.
3. **PR 24a must be merged first** (24b assumes the slider widget + RvR toggle + hero_player selector + chart labels are present and stable).

**Expected ship version:** v1.5.1.

**Smoke tests expected:** ~9 (per spec §6 PR 24b sub-section).

**Conflict surface:** Touches `ui/views/run_panel.py`, `ui/views/spot_input.py`, `ui/views/tree_browser.py`, `ui/state.py`, and adds `ui/views/node_lock_editor.py`. Does NOT touch `_rust.so`, no Rust changes; clippy not gated.

---

## A. Paste-ready agent prompt body

```
You are implementing PR 24b (GUI v1.4.0+ surface gaps — node-locking + asymmetric contributions + range editor polish + measured slider swap) for the poker_solver project.

REQUIRED READING BEFORE WRITING ANY CODE:
1. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_gui_surface_gaps.md — full spec; you implement §3.5, §3.6, §3.1, and the §5 measured-defaults swap (the 24b bundle per §6).
2. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_4_asymmetric_contributions.md — engine design for v1.4.1; confirms Fix A semantics so the UI passes correct `initial_contributions`.
3. /Users/ashen/Desktop/poker_solver/poker_solver/solver.py — confirm `locked_strategies` kwarg at line 36 and the ≤15 BB push/fold ValueError + `force_tree_solve` escape at lines 74-86.
4. /Users/ashen/Desktop/poker_solver/poker_solver/hunl.py — confirm `HUNLConfig.initial_contributions` plumbing at lines 105-148 (post-v1.4.1 honors asymmetric).
5. /Users/ashen/Desktop/poker_solver/poker_solver/charts/ — list existing chart JSON files; if dir is empty or only has scaffolding, you ship the first preset library files as part of this PR (see §C below for required minimum set).
6. /Users/ashen/Desktop/poker_solver/ui/state.py — Spot fields (332-487), to_hunl_config (lines 425-453), SolveRunner.start (567-606).
7. /Users/ashen/Desktop/poker_solver/ui/views/spot_input.py — _render_blinds_section (~438-483), _cycle_cell_frequency (~330-362), matrix-input cell binding (248-263).
8. /Users/ashen/Desktop/poker_solver/ui/views/tree_browser.py — node row rendering to find a hook for right-click / [Lock] button.
9. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_slider_tier_defaults_measured.md — the measurement pass output (orchestrator will confirm this file exists before kicking off 24b; if not present, you ship without §5 swap).
10. /Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py and /Users/ashen/Desktop/poker_solver/tests/test_ui_pr24a.py — smoke patterns.

WORKTREE & BRANCH:
- Worktree: /Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-node-lock-asymmetric
- Branch: feature/pr-24b-gui-node-lock-asymmetric
- Base: main HEAD AFTER v1.4.1 + PR 24a have both merged. Confirm with orchestrator before starting; do not start from origin/main if v1.4.1 hasn't landed.

IMPLEMENTATION SCOPE (4 features):

(1) Node-locking editor (spec §3.5):
    - New file ui/views/node_lock_editor.py — `ui.dialog`-hosted editor.
    - Dialog contents: label "Lock infoset {key} to fixed strategy"; one `ui.slider(0, 100)` per legal action (initial value = current avg strategy); a "must sum to 100%" validator with live readback; Save / Cancel.
    - Modify ui/views/tree_browser.py: add a "Lock this node" affordance on each tree node row.
        - PREFERRED: right-click via `btn.on('contextmenu', ...)`.
        - ORCHESTRATOR FLAGGED THIS: VERIFY NiceGUI 3.x exposes the `contextmenu` event. If unsupported, fall back to a small `[Lock]` button per row. Document the choice in the PR report.
    - Add `Spot.locked_strategies: dict[str, list[float]] = field(default_factory=dict)` in ui/state.py. Persist via state.json (the existing AppState serialization pattern).
    - In ui/state.py `SolveRunner.start`: pass `locked_strategies=spot.locked_strategies` to `solve(...)`. The kwarg threading scaffold exists per spec §3.5; add the dict.
    - Locked nodes: yellow padlock icon in tree (`tree_browser.py` cell render). Hover shows the locked distribution.
    - Add "Locked strategies" expansion in run_panel.py listing all locks with per-lock unlock buttons.
    - Error handling: solver.py:74-86 raises ValueError if locks + ≤15 BB preflop. Catch in `SolveRunner.start`, surface as `ui.notify(..., type='negative')` with a "Use tree-builder mode" remediation button that flips `force_tree_solve=True` and retries.

(2) Asymmetric initial_contributions (facing-bet input) (spec §3.6):
    - Add to Spot in ui/state.py:
        - `pot_so_far_bb: float = 0.0`
        - `villain_bet_bb: float = 0.0`
        - `bettor_is_p0: bool = True` (or equivalent; mirrors which seat faces the bet)
    - Modify `Spot.to_hunl_config()` (lines 425-453): when `villain_bet_bb > 0`, set
        - `initial_pot = (pot_so_far_bb + villain_bet_bb) * bb_blind_cents`
        - `initial_contributions = (pot_half + villain_bet_cents, pot_half)` with the bettor side getting the larger contribution (order determined by `bettor_is_p0`).
        - Per spec §3.6 + v1_4_asymmetric_contributions.md Fix A: the engine assumes lower-contribution side acts first.
    - Modify ui/views/spot_input.py `_render_blinds_section` (~438-483): add a new `ui.expansion("Facing bet (postflop subgame)", icon="trending_up", value=False)` containing:
        - `ui.number("Pot so far (BB)")` mark `pot-so-far-input`.
        - `ui.number("Villain's bet (BB)")` mark `villain-bet-input`.
        - `ui.toggle(["P0 faces bet", "P1 faces bet"])` mark `bettor-seat-toggle`.
    - Validation: `villain_bet_bb` must be ≤ effective stack of the bettor. Surface via `ui.notify(..., type='negative')`.

(3) Range editor polish (spec §3.1):
    - Modify ui/views/spot_input.py matrix cell binding (lines 248-263): add a right-click handler (or long-press fallback) that opens a per-hand frequency dialog.
    - New dialog (can live in spot_input.py or new ui/views/range_freq_editor.py):
        - 4×4 suit sub-grid showing the up-to-16 combos for the clicked hand class (e.g. AKo has 12 combos rendered as 4×3).
        - Per-combo `ui.slider(0, 100)` for frequency.
        - "Set all" master slider that propagates to every combo slider.
        - Save / Cancel.
        - On save, call `RangeWithFreqs.set_frequency(combo, freq)` per combo (ui/state.py:269-280).
    - Preset dropdown: add a `ui.select` above the player tabs (ui/views/spot_input.py ~200) populated by globbing `poker_solver/charts/chart_*.json`. On selection, parse via `RangeWithFreqs.from_string(...)` and write to `state.current_spot.ranges[spot.hero_player]`.
    - "Save current as preset" button: write the active range to `~/.poker_solver/charts/` via `RangeWithFreqs.to_string()` (ui/state.py:283-291). Create the directory if absent.
    - MINIMUM CHART LIBRARY (ship as part of 24b in `poker_solver/charts/`):
        - `chart_100bb_sb_open.json`
        - `chart_100bb_bb_defend.json`
        - `chart_100bb_btn_3bet.json`
        - `chart_30bb_sb_jam.json`
      Format per spec §4: `{"name": "<label>", "format": "pio_range_string", "data": "AA,KK,..."}`.
      If you cannot source authoritative ranges, ship 1-2 minimal placeholder presets with a README explaining the schema and leave the others as TODO. Be honest in the PR report.

(4) Swap in measured slider tier defaults (spec §5):
    - Read /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_slider_tier_defaults_measured.md (produced by the measurement pass).
    - Replace the 24a stub defaults (10.0 / 5.0 / 2.5 / 1.0 mBB/pot) in ui/views/run_panel.py with the measured values from the doc.
    - Remove the "(preliminary)" qualifier from the tooltip; replace with "Measured against the 12 PR 10a preset fixtures (see v1_5_slider_tier_defaults_measured.md)."
    - IF the measurement doc is not present when 24b starts: skip this sub-task, leave the stub defaults + preliminary tooltip in place, and flag in the PR report. Orchestrator will fast-follow with a swap PR.

ORCHESTRATOR-FLAGGED ITEMS (resolve, don't ask):
- (a) NiceGUI 3.x `contextmenu` event support: VERIFY before §3.5 dialog implementation. Fallback is `[Lock]` button per tree row. Document the choice.
- (b) range_matrix.py hero_player row-swap: confirm PR 24a landed this correctly; if not, no-op (24a's responsibility). Do not re-do it.
- (c) Push/fold + node-locking interaction: surface solver.py:74-86 ValueError + `force_tree_solve` escape in a user-readable notify. The escape button MUST set `force_tree_solve=True` and retry — do not just close the notify.

CONSTRAINTS:
- READ-ONLY anywhere outside ui/, tests/, and the chart-library JSON files. Do not modify poker_solver/* Python or Rust code.
- Do not touch the _rust.so binary. No clippy run.
- Do not touch other worktrees; do not pull in changes from sibling agents.
- Per user memory feedback_no_extrapolate: when swapping in measured slider defaults, use ONLY the per-tier values written in v1_5_slider_tier_defaults_measured.md. Do not interpolate, smooth, or "round to a nice number."
- Per user memory feedback_continuous_pruning: spec calls out NiceGUI contextmenu as unverified — your PR report must explicitly state which path you took (right-click vs button fallback).

TEST PLAN (~9 smoke tests in a new tests/test_ui_pr24b.py):
1. Open node-lock dialog from tree_browser, set river bluff freq to 0, run solve, assert `result.average_strategy[locked_key] == [0.0, ...]` bit-identically (per solver.py:60-61 semantics). Use a small fixture.
2. Lock + ≤15 BB preflop → assert UI shows ValueError as notify with "Use tree-builder mode" remediation button visible.
3. Click the remediation button → assert next solve call has `force_tree_solve=True`.
4. Set villain_bet_bb=0.5 (half-pot) with bettor=P0, assert `HUNLConfig.initial_contributions == (150, 100)` for a 1 BB pot baseline.
5. Set villain_bet_bb > effective stack → assert validation notify fires; solve does not start.
6. Open per-hand frequency dialog for AKo, set 0.42, assert `state.current_spot.ranges[player].frequency_of(<one combo>) == 0.42`.
7. Load preset chart_100bb_sb_open.json, assert range counter matches expected combo count (within ±2 combos of canonical SB open).
8. Save current range as user preset, assert file written to `~/.poker_solver/charts/`; reload, assert round-trip equality via to_string/from_string.
9. (IF §5 swap landed) Click "Standard" tier, assert `state.current_solve.target_exploitability` matches the measured Standard value from v1_5_slider_tier_defaults_measured.md.

Use NiceGUI `User` fixture. Mock the solver where wall-clock would exceed 30 s.

DELIVERABLE:
- Branch feature/pr-24b-gui-node-lock-asymmetric on the worktree.
- All new smoke tests pass.
- `scripts/check_pr.sh` clean (mypy + ruff).
- A PR-description draft committed under /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_pr_24b_report.md covering: contextmenu vs button fallback decision, §5 swap status (done vs deferred), chart library coverage (full vs placeholder), and any spec deviations.

DO NOT push to origin or open a PR. Hand the branch to orchestrator for audit + cherry-pick.

When done, report: (a) commit SHA, (b) smoke test count + names, (c) contextmenu vs button decision, (d) §5 swap status, (e) chart library coverage, (f) any spec deviations.
```

---

## B. Implementation notes (orchestrator-supplied)

### B.1 Hard sequencing (do NOT start 24b early)

24b MUST start AFTER all three of:
- v1.4.1 engine PR merged to main.
- PR 24a merged to main.
- `docs/pr_proposals/v1_5_slider_tier_defaults_measured.md` exists (or orchestrator explicitly authorizes 24b without §5 swap).

Orchestrator confirms each gate before pasting this prompt into an Agent() call.

### B.2 Orchestrator-flagged blockers (must resolve in-prompt; not asked back)

- **NiceGUI 3.x contextmenu:** Per spec §8 Q4. Verify in `references/` or by quick NiceGUI docs lookup. If unsupported, the `[Lock]` button-per-row fallback is fine; document the choice and move on.
- **range_matrix.py hero_player swap:** Per spec §8 Q5. 24a should have landed this. 24b does NOT redo it; if 24a missed it, flag for orchestrator and skip — do NOT silently re-implement.

### B.3 Files to modify / add (extracted from spec)

**Modify:**
- `ui/state.py` — add `locked_strategies`, `pot_so_far_bb`, `villain_bet_bb`, `bettor_is_p0` to Spot; modify `to_hunl_config()`; thread `locked_strategies` in `SolveRunner.start`.
- `ui/views/spot_input.py` — facing-bet expansion; preset dropdown; per-hand frequency dialog hook.
- `ui/views/tree_browser.py` — "Lock this node" affordance + padlock icon.
- `ui/views/run_panel.py` — "Locked strategies" expansion + per-lock unlock buttons; §5 measured defaults swap.

**Add:**
- `ui/views/node_lock_editor.py` — new dialog.
- `ui/views/range_freq_editor.py` (optional) — per-hand frequency dialog if too large for spot_input.py.
- `poker_solver/charts/chart_*.json` — minimum 4-file preset library (or fewer + TODO per honesty rule).
- `tests/test_ui_pr24b.py` — 9 smokes.

### B.4 Honest framing (per memory feedback_no_extrapolate + research_first_failure_protocol)

- If the chart library is incomplete, ship placeholders + README + honest TODO. Do NOT fabricate range strings.
- §5 measured-defaults swap uses ONLY the per-tier values from the measurement doc. Do not interpolate.
- If contextmenu doesn't work and the button fallback is uglier, ship the button — no UX gold-plating that delays the PR.

---

## C. Audit / check chain

1. `bash scripts/check_pr.sh` — mypy + ruff. Must pass.
2. Smoke tests: `pytest tests/test_ui_pr24b.py -v`. Must pass.
3. Manual quick check (agent's call): `poker-solver ui` → open a postflop spot → open node-lock editor → confirm dialog renders.
4. No Rust changes → clippy not gated.
5. Orchestrator audit: spec compliance + persona retest readiness (W1.2, W2.3, W3.1, W3.3, W3.4 per spec §7).

---

## D. Ready-to-fan-out signal

This prompt is BLOCKED until orchestrator confirms (a) v1.4.1 merged to main and (b) PR 24a merged to main. The §5 measured-defaults swap is also blocked on the measurement pass; if that doc is missing when the prompt is fanned out, the swap deferral path is pre-resolved in the prompt body.

Orchestrator green-light checklist (paste into agent kickoff):
- [ ] v1.4.1 engine PR merged
- [ ] PR 24a merged
- [ ] `v1_5_slider_tier_defaults_measured.md` exists (else acknowledge deferral path)
- [ ] Worktree `pr-24b-gui-node-lock-asymmetric` created from latest main
