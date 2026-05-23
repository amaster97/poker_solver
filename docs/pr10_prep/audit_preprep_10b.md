# PR 10b audit pre-prep — anticipated findings & pre-patches

**Date:** 2026-05-22
**Author:** orchestrator pre-stage (audit-anticipation)
**Branch under (future) audit:** `pr-10b-ui-real-solver`
**Mirror of:** `pr7_prep/audit_preprep.md` + `pr8_prep/audit_preprep.md` pattern.
**Scope:** anticipate likely audit findings for PR 10b (UI mock → real solver swap) BEFORE PR 10b fires; pre-stage any viable patches; record sequencing.

PR 10b is a **single-agent, delete-and-replace** swap (per `fanout_ready_10b.md` §0): ~150–300 LOC net (mostly deletes). It is **the smallest PR in the v1 roadmap** by code surface, but the regression surface against PR 10a's marker contracts and the cross-PR `on_progress` signature lock with PR 9 are sharp. Audit is intentionally lighter than 10a's (4 focus areas vs. 15) per `fanout_ready_10b.md` §5.

---

## 1. Likely audit findings (5 user-flagged risks)

### 1.1 UI structure regression vs PR 10a — **HIGH / must-fix on any Q1-Q6 drift**

Spec: `pr10b_spec.md` §0 line 21 ("UI structure FROZEN at PR 10a"); `fanout_ready_10b.md` §3 forbidden list.

- 8 retained PR 10a smoke tests must pass UNMODIFIED. Grep: `git diff integration -- tests/test_ui_smoke.py | grep '^[-+]'` should show ONLY 5 mock-deletes + 2 real-solve adds.
- `git diff integration -- ui/views/` empty (marker contracts `matrix-cell`, `preset-*` intact).
- ONLY allowed UX delta: Q7 banner → `(mock)` chip.

**Failure mode:** Agent "cleans up" a view file → marker contract silently broken → smoke tests pass (markers are structural) but PR 11 library loading breaks downstream. **Severity:** must-fix on any `ui/views/*.py` edit or retained-smoke-test failure.

### 1.2 `on_progress` kwarg signature compat (PR 9 preflop + PR 5 postflop) — **HIGH / must-fix if drifted**

Spec: `pr10b_spec.md` §3 lines 100-113 (locked signature `Callable[[int, float, MemoryReport], None] | None = None`); §3 lines 136-137; `fanout_ready_10b.md` §1c pre-flight gate.

- `inspect.signature` byte-identical between `solve_hunl_preflop` and `solve_hunl_postflop`.
- Callback fires on **worker thread** not main UI thread (per `audit_prompt.md` §1 — UI never blocks).
- PR 5/6/7 existing callers unaffected (default `None`).

**Failure mode:** PR 9 ships `= lambda *a: None` while PR 10b ships `None`; dispatch wrapper in `ui/state.py` (which ASSUMES identical shape per spec §4) trips at first preflop solve. **Severity:** must-fix on any signature divergence.

### 1.3 Mock module deletion completeness — **MEDIUM / must-fix on orphan imports**

Spec: `pr10b_spec.md` §5 lines 177-183; §7 line 221; `fanout_ready_10b.md` §5 line 108.

- `git ls-files | grep -i mock_solver` empty.
- `grep -ri 'from ui.mock_solver\|import mock_solver\|mock_solve' poker_solver/ ui/ tests/` empty.
- `mock_progress_callback` symbol gone; `tests/test_ui_smoke.py` no `mock_*` kwarg refs.

**Failure mode:** Orphan `from ui.mock_solver import ...` survives import-resolution dead-code path; CI passes; runtime `ImportError` on first UI launch. **Severity:** must-fix on any orphan import; should-fix on stale comment.

### 1.4 Yellow banner → subtle `(mock)` chip — **MEDIUM / should-fix band**

Spec: `pr10b_spec.md` §0 lines 22-26 (Q7 downgrade); `fanout_ready_10b.md` §3 line 86.

- Conditional gate: `if not state.has_completed_real_solve: render chip else: hide`.
- Marker swap: `mock-mode-banner` → `mock-mode-chip` (ONE permitted marker change).
- README: `## UI (mock)` → `## UI`; PR 10a mock-mode paragraph removed.

**Failure mode:** Chip persists post-real-solve (state not threaded); or chip still bright yellow / banner-sized (downgrade in spirit only). **Severity:** should-fix (UX polish). Becomes must-fix only if marker name diverges from `mock-mode-chip` (would break PR 11 introspection).

### 1.5 Library viewer stub stays a stub — **LOW / must-fix if grown**

Spec: `pr10b_spec.md` §2 line 86 (out-of-scope: PR 11); `audit_prompt.md` §13.

- `git diff integration -- ui/views/library_browser.py` empty.
- `test_library_dialog_opens` (PR 10a #8) unmodified.

**Failure mode:** Agent "helpfully" wires a real row-click handler → premature PR 11 work; PR 11 spec diverges. **Severity:** must-fix on ANY touch of `library_browser.py`.

---

## 2. Pre-patches viable BEFORE PR 10b fires

**Effectively none.** PR 10b has not started; the branch `pr-10b-ui-real-solver` does not exist yet and is gated on BOTH PR 9 AND PR 10a landing on `integration` (per `fanout_ready_10b.md` §1a). There is no diff to patch.

Pre-stage actions already complete:
- **PR 9 derived requirement:** `solve_hunl_preflop` exposes `on_progress` kwarg with the locked signature (per `pr10b_spec.md` §3 lines 136-137 + `fanout_ready_10b.md` §1c gate). If PR 9 lands without this, halt and fix PR 9 on integration first.
- **PR 10a marker contracts frozen:** `pr10a_spec.md` §0.1 locks Q1-Q7; Q7's downgrade is the ONLY allowed delta in 10b.
- **Single-agent prompt:** no fan-out, no inter-agent reconciliation surface to pre-patch.

The audit is intentionally lighter than 10a's (4 focus areas listed in `fanout_ready_10b.md` §5 vs 15 for PR 10) because the scope is so narrow. Any pre-patch effort beyond the existing locks is over-engineering.

---

## 3. Expected audit verdict

**Forecast: READY for commit AFTER must-fix items resolved** (~60% probability) OR **READY for commit** (~30% probability).

Rationale:
- The diff is mechanical and small (~150-300 LOC net, mostly deletes).
- The 4 audit focus areas in `fanout_ready_10b.md` §5 are well-anchored.
- Most likely must-fix finding: §1.2 (`on_progress` signature drift if PR 9 lands first with a slightly-different default).
- Likely should-fix findings: §1.4 (chip downgrade UX polish), maybe §1.3 (a stale comment grep miss).
- Low-probability findings: §1.1 (Agent strictly forbidden from touching `ui/views/*.py`), §1.5 (no incentive to grow the library stub).

**Expected severity counts at audit:** 0-1 must-fix (most likely 0 or 1 on signature drift); 1-2 should-fix; 1-3 nice-to-fix.

**P(clean READY-no-patches verdict):** ~30%.
**P(READY-with-must-fix verdict):** ~60%.
**P(NOT-READY verdict):** ~10% (only if PR 9 ships with a drifted `on_progress` default that propagates).

---

## 4. Sequencing

**Trigger:** Audit fires after the single agent returns AND `scripts/check_pr.sh` passes. Per `fanout_ready_10b.md` §5: ~45-90 min agent runtime → 7 deliverable files validated → check_pr.sh → audit agent (4 focus areas) → compare findings vs §1 forecasts → resolve must-fix → `--no-ff` merge to integration.

**Read order:** `audit_prompt.md` (brief) → this file (calibrate expectations) → `pr10b_spec.md` (source of truth) → `audit_report.md` (compare vs §1).

**Per memory `feedback_no_extrapolate`:** even with a small diff, do NOT assume zero must-fix findings pre-audit. The `on_progress` signature compatibility (§1.2) is genuinely cross-PR and can fail in ways the single-PR audit won't catch alone.
