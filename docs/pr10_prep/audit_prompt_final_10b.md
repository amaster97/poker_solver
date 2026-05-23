# PR 10b audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep_10b.md` §3: READY-WITH-PATCHES (~60%) > clean READY (~30%) > NOT-READY (~10%).
> - Top two pre-flagged risk surfaces (audit MUST touch with file:line evidence): UI structure regression vs PR 10a (`audit_preprep_10b.md` §1.1), `on_progress` signature compat with PR 9 (§1.2).
> - PR 10b scope: single-agent, delete-and-replace swap (~150-300 LOC net, mostly deletes). The 4 focus areas reflect the narrow scope per `fanout_ready_10b.md` §5.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-10b-ui-real-solver` branch and you have not seen the design discussions. Your job is to audit the PR 10b implementation (UI mock → real solver swap) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 10b is **the smallest PR in the v1 roadmap** by code surface, but the regression surface against PR 10a's marker contracts and the cross-PR `on_progress` signature lock with PR 9 are sharp. The UI structure is FROZEN at PR 10a; only the solver backend changes. Any drift in UI surfaces beyond the locked Q7 downgrade → must-fix.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-10b-ui-real-solver` (branched from `integration` AFTER both PR 9 and PR 10a have landed).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` — read end-to-end first.
- **PR 10a spec:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` (the structure being preserved).
- **PR 9 spec:** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` (for `on_progress` signature lock).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 10b entries.

## Inputs to read (in order)

1. **PR 10b spec:** internalize §0 (UI structure FROZEN at PR 10a), §1 (goal — mock → real swap), §2 (out-of-scope — PR 11 library wiring), §3 (`on_progress` signature locked at `Callable[[int, float, MemoryReport], None] | None = None`), §4 (`ui/state.py` dispatch wrapper assumes identical signature for preflop AND postflop), §5 (mock deletion completeness), §7 (test contract — 8 retained smoke tests).
2. **PR 10a spec §0.1:** the 7 Q-locks. Q7 (yellow "Mock mode" banner) is the ONLY one that can change in PR 10b — banner downgrades to a subtle `(mock)` chip that hides after first real solve.
3. **PR 9 spec §3:** confirm `solve_hunl_preflop` exposes `on_progress` kwarg with locked signature.
4. **The branch diff:** `git diff integration...HEAD` while on `pr-10b-ui-real-solver`. Also `git log integration..HEAD --oneline`.
5. **The autonomous log:** PR 10b entries.
6. **The actual new / modified files:** at minimum
   - `ui/app.py` (modified — imports `poker_solver.hunl_solver` instead of `ui.mock_solver`)
   - `ui/state.py` (modified — dispatch wrapper for preflop vs postflop solve, banner → chip state)
   - `ui/mock_solver.py` (**DELETED**)
   - `tests/test_ui_smoke.py` (modified — 5 mock-specific tests deleted, 2 real-solve tests added; 8 retained tests UNMODIFIED)
   - `README.md` (modified — "UI (mock)" → "UI" header, mock-mode paragraph removed)
   - any other touched files

Do not actually run the UI server. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.1, §1.2 per `audit_preprep_10b.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **UI structure regression vs PR 10a (Q1-Q6 FROZEN).** [HIGH-PROB must-fix per `audit_preprep_10b.md` §1.1]
   - Per `pr10b_spec.md` §0 line 21: "UI structure FROZEN at PR 10a" + `fanout_ready_10b.md` §3 forbidden list.
   - **Verification gates:**
     - `git diff integration -- ui/views/` should be **empty** (marker contracts `matrix-cell`, `preset-*`, etc. intact across all view files).
     - `git diff integration -- tests/test_ui_smoke.py | grep '^[-+]'` should show ONLY 5 mock-deletes + 2 real-solve-adds. The 8 retained smoke tests (page renders, board picker, range input, solve button, stop button, matrix renders 169 cells, combo-to-cell mapping, library dialog opens) must pass UNMODIFIED.
     - 7 of 7 Q-locks from `pr10a_spec.md` §0.1 preserved EXCEPT Q7 (which downgrades).
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Agent "cleans up" a view file** — marker contract silently broken; smoke tests pass (markers are structural) but PR 11 library loading breaks downstream. Must-fix on any `ui/views/*.py` edit.
     - (b) **Q1-Q6 layout drift** — two-pane → single-pane; combo inspector relocated; bet-size defaults bumped. Must-fix.
     - (c) **Retained smoke test modified** — assertion strings rewritten "for clarity". Must-fix.
   - **Evidence stub:** `git diff integration -- ui/views/` (expect empty); `git diff integration -- tests/test_ui_smoke.py` (expect 5 dels + 2 adds, no edits to retained).

2. **`on_progress` kwarg signature compat with PR 9 preflop + PR 5 postflop.** [HIGH-PROB must-fix per `audit_preprep_10b.md` §1.2]
   - Per `pr10b_spec.md` §3 lines 100-113 + §3 lines 136-137 + `fanout_ready_10b.md` §1c pre-flight gate.
   - Locked signature: `Callable[[int, float, MemoryReport], None] | None = None` (with default `None`, NOT `lambda *a: None`).
   - **Verification gates:**
     - `inspect.signature(solve_hunl_preflop) == inspect.signature(solve_hunl_postflop)` BYTE-identical for the `on_progress` parameter.
     - Callback fires on **worker thread**, NOT main UI thread (per PR 10a `audit_prompt.md` §1 + spec §6 threading).
     - PR 5/6/7 existing callers unaffected (default `None`).
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Default drift** — PR 9 ships `= lambda *a: None`; PR 10b ships `None`. Dispatch wrapper in `ui/state.py` (which ASSUMES identical shape per spec §4) trips at first preflop solve. Must-fix.
     - (b) **Signature drift** — `Callable[[int, float], None]` (missing `MemoryReport`) or extra kwarg. Must-fix.
     - (c) **Worker-thread invariant broken** — callback invoked on main UI thread, blocking event loop during NumPy work. Must-fix.
   - **Evidence stub:** `poker_solver/hunl_solver/__init__.py` or wherever `solve_hunl_preflop` and `solve_hunl_postflop` live — verify signatures match byte-for-byte.

3. **Mock module deletion completeness.** [pre-flagged must-fix per `audit_preprep_10b.md` §1.3]
   - Per `pr10b_spec.md` §5 lines 177-183 + §7 line 221 + `fanout_ready_10b.md` §5 line 108.
   - **Verification gates:**
     - `git ls-files | grep -i mock_solver` returns **empty** (file deleted, not renamed).
     - `grep -ri 'from ui.mock_solver\|import mock_solver\|mock_solve\|mock_progress_callback' poker_solver/ ui/ tests/` returns **empty** (no orphan imports or callsites).
     - `tests/test_ui_smoke.py` has no `mock_*` kwarg refs.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Orphan import** — `from ui.mock_solver import ...` survives import-resolution dead-code path; CI passes; runtime `ImportError` on first UI launch. Must-fix.
     - (b) **Stale comment / docstring** — references to `mock_solver` in comments. Should-fix.
     - (c) **`mock_progress_callback` symbol leaked** — defined elsewhere and re-imported. Must-fix.
   - **Evidence stub:** `git status --porcelain` showing `D ui/mock_solver.py`; grep results.

4. **Yellow banner → subtle `(mock)` chip (Q7 downgrade).** [pre-flagged should-fix per `audit_preprep_10b.md` §1.4]
   - Per `pr10b_spec.md` §0 lines 22-26 + `fanout_ready_10b.md` §3 line 86: the ONLY permitted UX delta is Q7's downgrade. Banner becomes a chip; chip hides after first real solve completes.
   - **Verification gates:**
     - Conditional gate: `if not state.has_completed_real_solve: render chip else: hide`.
     - Marker swap: `mock-mode-banner` → `mock-mode-chip` (ONE permitted marker change).
     - README: `## UI (mock)` → `## UI`; PR 10a mock-mode paragraph removed.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Chip persists post-real-solve** — state not threaded; chip stays forever. Should-fix.
     - (b) **Chip still bright yellow / banner-sized** — downgrade in spirit only. Should-fix.
     - (c) **Marker name diverges from `mock-mode-chip`** — breaks PR 11 introspection. Must-fix.
   - **Evidence stub:** `ui/app.py:?` or `ui/views/banner.py:?` — chip rendering logic.

5. **Library viewer stub stays a stub.**
   - Per `pr10b_spec.md` §2 line 86 (out-of-scope: PR 11 wiring) + PR 10a `audit_prompt.md` §13.
   - **Verification gates:**
     - `git diff integration -- ui/views/library_browser.py` returns **empty** (untouched).
     - `test_library_dialog_opens` (one of PR 10a's retained 8 smoke tests) unmodified.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Agent "helpfully" wires a real row-click handler** — premature PR 11 work; PR 11 spec diverges. Must-fix.
     - (b) **Stub disabled-button flipped to enabled** — must-fix.
   - **Evidence stub:** `git diff integration -- ui/views/library_browser.py` listing.

6. **No new third-party dependencies.**
   - PR 10b is a delete-and-replace swap. No new packages should appear in `pyproject.toml`.
   - `[project.dependencies]` and `[project.optional-dependencies] ui` unchanged.
   - **Evidence stub:** `git diff integration -- pyproject.toml` listing.

7. **All PR 1-10a tests still pass unchanged.**
   - Per spec §7 + the strictly-additive contract: the diff is mechanical and small. Engine tests are untouched.
   - Specifically: `test_ui_smoke.py` 8 retained tests pass UNMODIFIED; 5 mock-tests deleted; 2 new real-solve tests added.
   - **Evidence stub:** `git diff integration -- tests/` listing; pytest full-suite delta.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10b.md` with this exact structure:

```markdown
# PR 10b audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10b-ui-real-solver
**Diff size:** [N modified + M new files + K deleted files = ±X LoC total]

**Test status:** [pytest tests/test_ui_smoke.py — pass/fail (note skip count if nicegui not installed); full suite delta]

## Must-fix

[`ui/views/*.py` edited (marker contract broken); retained smoke test modified; `on_progress` signature drift (default or shape); orphan `mock_solver` import; chip marker not `mock-mode-chip`; library_browser.py touched (premature PR 11). Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Stale mock_solver comments; chip persists post-real-solve; chip still banner-sized; README polish gaps. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-7 matching the 7 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: no new third-party deps; no code copied; PR 10b is purely a deletion + import swap. Cite specific files.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** `ui/views/*.py` edited (Q1-Q6 drift), retained smoke test modified, `on_progress` signature drift, orphan `mock_solver` import, `library_browser.py` touched (premature PR 11), chip marker name diverged from `mock-mode-chip`. Blocks PR.
- **should-fix:** stale mock_solver comments, chip persists post-real-solve, chip still banner-sized, README polish. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that drifts UI structure beyond Q7 downgrade, or breaks the `on_progress` signature compatibility → must-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially `pr10b_spec.md` §0 (FROZEN structure), §3 (`on_progress` lock), §5 (mock deletion), §7 (test contract).
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr10_prep/audit_report_10b.md`.
- HIGH-PROB risk surfaces (focus areas 1, 2 — and the three sub-probes in each) MUST get paragraph-level discussion even with no defect found.
- This is a deletion-heavy PR. Verify deletions are *complete*: no orphans, no stale comments, no dead code paths.

Begin by reading the PR 10b spec (especially §0 FROZEN constraint + §3 signature lock), then PR 10a §0.1 Q-locks, then the diff, then the modified files. Then write the report.
