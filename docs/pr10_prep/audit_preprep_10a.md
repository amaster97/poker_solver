# PR 10a audit pre-prep — anticipated findings & pre-patches

**Status:** Pre-PR-10a reference. Read this BEFORE the audit agent fires post-implementation.
**Date:** 2026-05-22
**Scope:** Forecast the five highest-probability audit findings for PR 10a (UI mock-first), document pre-patches that can land before the audit, and set an expected verdict.

This doc complements `fanout_ready_10a.md` (fire-when-PR-5-lands shortlist), `launch_kickoff_10a.md` (full pipeline), and `audit_prompt.md` (the audit agent's 15-focus-area brief). It runs read-only — no source files touched.

---

## 1. Likely audit findings

Numbered to match the five user-flagged risk surfaces. Each: probability, severity-band the audit will likely assign, evidence anchor, and mitigation status.

### 1.1 UI threading correctness (worker thread + `ui.timer` polling) — **HIGH probability / must-fix band if violated**

**Risk:** The single most load-bearing surface in PR 10a. NiceGUI requires that worker code never call UI elements directly — all UI mutation must happen on the asyncio event loop. Three failure modes the audit will probe:
- (a) **Worker thread writes to UI primitives** — e.g., a `solver_thread` that calls `progress_bar.set_value(...)` or `ui.notify(...)` directly. Causes silent races, occasional segfaults, or NiceGUI's "element not bound to a client" error.
- (b) **Missing `ui.timer(0.5, update_ui)` polling pattern** — the spec mandates that the worker writes status to a shared dataclass (`state.runner`); a UI timer polls it every 500ms and re-renders. If the implementation uses `asyncio.to_thread` instead of `threading.Thread`, the GIL release inside NumPy may still block the loop for long stretches.
- (c) **Stop-button latency** — `_stop_event` is checked once per DCFR iter boundary. Audit will set `iterations=100_000`, click Solve, wait 0.5s, click Stop, and assert `status in ('stopped', 'done')` AND `iteration < 50_000` within 0.5s.

**Audit probability:** auditor will `grep -r "ui\." ui/mock_solver.py` for any UI calls inside the worker, then verify the polling timer exists in `ui/app.py` or `ui/views/run_panel.py`. Per `audit_prompt.md` focus areas 1+2 (lines 42-52). If a worker calls UI directly → must-fix; if timer is missing → must-fix; if stop latency >1 mock-iter → must-fix.

### 1.2 Browser-state persistence atomicity (`~/.poker_solver_ui/state.json`) — **MEDIUM probability / should-fix band**

**Risk:** Per spec §9.2 + `audit_prompt.md` focus area 12 (lines 108-112). The state file is loaded on startup and saved on significant changes (spot edits, view toggles, theme). Three slip-ups:
- (a) **Non-atomic write** — direct `open(path, 'w').write(json.dumps(...))` corrupts the file if the process dies mid-write. Required pattern: write to `state.json.tmp`, `fsync()`, then `os.rename()` to `state.json`. The rename is atomic on POSIX.
- (b) **No corrupt-load fallback** — if JSON is malformed (e.g., from an old version), the UI should log a warning, back up to `state.json.bak`, and start from defaults. Don't crash on launch.
- (c) **Save debounce missing** — saving on every keystroke thrashes disk. Required: `ui.timer(0.5, ...)` debounce with coalesced writes.

**Audit probability:** auditor will read `ui/state.py` save path. If the tmp-fsync-rename trio is absent → should-fix (not must-fix because the file lives in user home, not the engine). If corrupt-load crashes → should-fix.

### 1.3 Mock-data fidelity (12 fixture spots, MDF / polarization / blocker checks) — **MEDIUM probability / should-fix band**

**Risk:** Per `pr10a_spec.md` lines 614, 657-670 + audit focus area implicit in §3 view rendering. The 12 fixtures must demonstrate plausible solver-shaped output (no dominated actions, MDF-obeying bluff freq on rivers, polarization on river spots, more linear on flops, blocker effects visible on `flop_k72r_100bb` and similar). Failure modes:
- (a) **Fixture values mathematically implausible** — e.g., river bluff freq exceeds MDF cap (audit can spot this by inspection: if bet-size 100% pot, MDF cap is 1/(1+1) = 50% — defender must call 50%, so bluffer can bluff at most 50% of value combos).
- (b) **Range matrix off-by-one** — `(row, col)` for `row = max(rank1, rank2)`, `col = min(rank1, rank2)`. Pairs on diagonal; suited above; offsuit below. Total 1326 combos. Per `audit_prompt.md` focus area 3 (lines 53-58) — auditor runs `test_combo_to_cell_mapping_no_off_by_one`.
- (c) **Blocker overlay missing on `flop_k72r_100bb`** — slashed-diagonal `╳╳╳` per spec §3.3 + line 397.

**Audit probability:** auditor will load all 12 fixtures via the preset dropdown and spot-check. If any fixture renders with empty cells, NaN frequencies, or implausible MDF → should-fix. If matrix off-by-one is present → must-fix (silent strategy display corruption).

### 1.4 Locked 7 design decisions cited in agent prompts — **LOW probability / should-fix band**

**Risk:** Per `fanout_ready_10a.md` §3 "Seven Q-locks (`pr10a_spec.md` §0.1)": Q1 two-pane + right-sidebar; Q2 hand-class labels in cells, numeric freq on hover; Q3 default iters = 1000; Q4 4-of-6 bet sizes checked (33/75/100/all-in); Q5 combo inspector below matrix; Q6 reach filter 0.01 default; Q7 yellow "Mock mode" banner top, dismissible. Failure modes:
- (a) **Banner missing or non-dismissible** — Q7 is the safety rail against shipping mocks as real solves. If absent → user runs PR 10a thinking they have real solver output.
- (b) **Default iters drifted** — Q3 weakly-held lock; agent might bump to 2000 unilaterally.
- (c) **Combo inspector misplaced** — e.g., right sidebar instead of below matrix.

**Audit probability:** auditor will eyeball the 7 locks against rendered UI. Banner is the only must-fix candidate (others are layout taste — should-fix at worst).

### 1.5 Mock interface contract matches real solver shape — **HIGH probability / must-fix band if mismatched**

**Risk:** The whole point of PR 10a's mock-first design is that PR 10b is a one-line import swap from `ui.mock_solver` to `poker_solver.hunl_solver`. The mock must return `HUNLSolveResult` byte-locked to the real PR 5 output shape. Failure modes:
- (a) **Field-name drift** — mock returns `{"strategy": ..., "ev": ...}` but real solver returns `{"final_strategy": ..., "exploitability": ...}`. PR 10b breaks on swap.
- (b) **Missing fields** — `MemoryReport`, `StreetMemoryEntry`, per-iteration progress callbacks. Per `fanout_ready_10a.md` line 9: "UI consumes only `HUNLSolveResult`, `MemoryReport`, `HUNLConfig`, `Range`/`Combo` — all shape-locked by PR 5."
- (c) **`RangeWithFreqs` modifies `poker_solver.Range`** — per `audit_prompt.md` focus area 9 (lines 92-96): UI must wrap `Range`, not modify `poker_solver/range.py`. Verify `git diff integration -- poker_solver/range.py` is empty.

**Audit probability:** auditor will run `python -c "from poker_solver.hunl_solver import HUNLSolveResult; from ui.mock_solver import solve_mock; r = solve_mock(...); assert isinstance(r, HUNLSolveResult)"`. If the assert fails → must-fix. If `poker_solver/range.py` was modified → must-fix.

---

## 2. Pre-patches that could land BEFORE PR 10a audit

Pre-stage is already strong (`launch_kickoff_10a.md` lists three agents with locked ownership, seven Q-locks; `pr10a_polish_report.md` verdict "Prompts ready"). The candidate pre-patches below would tighten the audit surface further; all touch spec/prompt docs only, not source files (per the read-only constraint).

### Pre-patch A: tighten Agent A's threading checklist — **optional, low cost**

Add an explicit subsection in `agent_a_prompt.md` for `ui/app.py` covering:
1. Worker MUST use `threading.Thread` (NOT `asyncio.to_thread`).
2. Worker MUST NOT call any `ui.*` element. Writes only to `state.runner` dataclass.
3. `ui.timer(0.5, update_ui)` polls `state.runner` and re-renders.
4. `_stop_event.is_set()` checked at iter boundary.

**Why defer:** `audit_prompt.md` focus areas 1+2 already cover this; the audit catches it regardless. Adding to Agent A's prompt risks bloat.

### Pre-patch B: add explicit MDF assertion to fixture-design notes — **optional, low cost**

Extend `pr10a_spec.md` §fixture-design with a one-line assertion: "for every fixture with bet-size B, bluff_freq <= MDF_cap(B) = B/(1+B) of value combos." Catches Agent C's hand-crafted fixtures if any violate.

**Why defer:** Auditor's eyeball check during fixture walkthrough catches plausibility issues. A spec-level MDF reminder is belt-and-suspenders.

**Recommendation:** Neither pre-patch is required. The pre-stage is sufficient. If launching with extra paranoia, Pre-patch A is the higher-value addition (threading is the highest-risk surface).

---

## 3. Expected audit verdict given current prep quality

**Forecast: READY for commit AFTER must-fix items resolved** (per `audit_prompt.md` line 170 verdict taxonomy).

Rationale:
- `pr10a_polish_report.md` verdict is "Prompts ready (post-polish)" per `fanout_ready_10a.md` line 5.
- 15 audit focus areas in `audit_prompt.md` map to well-documented surfaces with anchored spec sections.
- Most-likely must-fix findings are 1.1 (worker thread calls UI directly OR stop latency >1 iter) and 1.5 (mock interface drift). Either is a single-file fix.
- Likely should-fix findings: 1.2 (state.json atomic write missing) and 1.3 (one or two fixtures with implausible MDF).
- Low-probability findings (1.4 Q-locks) are pre-verified READY in the prompts.

**Expected severity counts at audit:** 0-2 must-fix (most likely 1, on threading correctness or mock shape mismatch); 2-4 should-fix; 3-6 nice-to-fix.

**P(clean READY-no-patches verdict):** ~25%.
**P(READY-with-must-fix verdict):** ~60%.
**P(NOT-READY verdict):** ~15% (only if Agent A botches threading model so badly the UI deadlocks).

---

## 4. Sequencing: when this doc fires

**Trigger:** This file becomes the audit-prep reference the moment PR 10a audit agent is dispatched per `fanout_ready_10a.md` §6.

**Read order at audit time:**
1. `audit_prompt.md` (the audit brief — primary input).
2. This file (anticipated findings — calibrate expectations).
3. `pr10a_polish_report.md` (proves the pre-stage prompts passed).
4. `audit_report.md` (the audit agent's output — compare against §1 forecasts here).

**Post-audit action:**
- If audit finds <=2 must-fix items matching §1.1/1.5 forecast → apply patches per audit, re-test, commit.
- If audit finds must-fix items NOT in §1 → those are blind spots; root-cause and update this doc for PR 10b.
- If audit reports NOT-READY → halt, escalate to user, do not merge.

**This doc is reference-only.** Do NOT modify source files based on §1 forecasts before the audit runs — the audit is what catches the actual bugs. Use this only to (a) prime expectations and (b) accelerate post-audit triage.

---

## Anchors

- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10a.md`
- Launch kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`
- Polish report: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_polish_report.md`
- Locked Q1-Q7: `pr10a_spec.md` §0.1
