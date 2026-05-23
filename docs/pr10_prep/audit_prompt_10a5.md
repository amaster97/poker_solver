# PR 10a.5 audit agent prompt — UI conformance pass

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `pr10a5_conformance_backlog.md` §4: READY (~70%) > READY-WITH-PATCHES (~25%) > NOT-READY (~5%). Narrow conformance pass, low surface area, low risk.
> - Conformance scope: 5 hard failures (F1-F5) + 7 xfailed tests (X1-X7). Audit MUST touch each with file:line evidence.
> - Hard-forbidden file: `ui/views/library_browser.py` (PR 11 owns). Any edit here is must-fix scope leak.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-10a5-ui-conformance` branch and you have not seen the design discussions. Your job is to audit the PR 10a.5 implementation (UI smoke-test conformance pass) against the scope freeze and report findings in a structured Markdown report.

Treat the scope-freeze document as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 10a.5 is a **conformance pass**, not a feature PR. It fixes 5 hard failures introduced by Agent B's multi-tag `data-marker` drift in PR 10a, and wires up 7 surfaces that were `@pytest.mark.xfail`-decorated in v0.6.0. Acceptance gate: all 20 smoke tests pass (no `xfail`, no `fail`). Target version: **v0.6.1 PATCH**.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Worktree under audit:** `/private/tmp/poker_pr10a5` (branch `pr-10a5-ui-conformance`, branched from `integration` tip `b880032` — the PR 10a merge commit).
- **Scope freeze:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a5_conformance_backlog.md` — read end-to-end first.
- **Originating audit:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a.md` — the should-fix items #1, #2, #3 are what PR 10a.5 closes.
- **Parallel branch:** `pr-11-library-and-packaging` (in the shared tree). File-overlap zero; conflict surface only `ui/views/library_browser.py` which PR 10a.5 must NOT touch.

## Inputs to read (in order)

1. **The scope freeze:** `pr10a5_conformance_backlog.md`. Internalize §2 (F1-F5 table — root cause + file:line), §3 (X1-X7 table — anchor markers / constants), §4 (recommended scope — six numbered steps), §6 (out of scope — Q-locks, fixtures, mock signature, engine, version bump beyond v0.6.1 all frozen).
2. **The originating audit:** `audit_report_10a.md`. Should-fix items #1, #2, #3.
3. **The smoke-test file:** `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py`. Confirm: pre-PR-10a.5 baseline showed `@pytest.mark.xfail` decorators at lines 452, 498, 531, 580, 620, 659, 683; PR 10a.5 must have removed all 7.
4. **The branch diff:** in worktree `/private/tmp/poker_pr10a5`, run `git diff integration...HEAD` and `git log integration..HEAD --oneline`. Confirm net LOC ~150-250 across the five UI files + test-file decorator removal.
5. **The actual modified files:**
   - `ui/views/range_matrix.py` (marker fix + adapter + constants + blocker class)
   - `ui/views/spot_input.py` (preset marker cross-check + `INPUT_PALETTE` + pushfold toast wire)
   - `ui/views/run_panel.py` (log-scale toggle marker + OOM remediation button + progress-eta marker)
   - `ui/state.py` (`SolveRunner.compute_eta()` method)
   - `ui/app.py` (pushfold toast button wire)
   - `tests/test_ui_smoke.py` (xfail decorator removal only)

Do not actually run the UI server. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **F1-F5: multi-tag `data-marker` drift fixed.** [must-fix on silent test failure]
   - The committed PR 10a.5 must replace the comma-separated `data-marker=foo,bar-baz` pattern at `ui/views/range_matrix.py:735` and `:844` with single-value form (two separate `.props()` chains OR `.mark(name)` shorthand).
   - **Probe:** `grep -nE 'data-marker=[a-z0-9-]+,[a-z0-9-]+' ui/views/range_matrix.py` — expected empty.
   - **Probe:** confirm `User.find(marker="matrix-cell").elements` resolves 169 cells (smoke 6 passes, smoke 7 passes, smoke 1 passes).
   - **Evidence stub:** `ui/views/range_matrix.py:?` (marker form); `tests/test_ui_smoke.py:?` (smoke 1, 6, 7 results).

2. **F4: spot-input preset markers match 12 fixture IDs.** [must-fix on drift]
   - `ui/views/spot_input.py` must emit preset markers byte-identical to the 12 fixture IDs from `ui/mock_solver_fixtures.py:611-625` (`_FIXTURE_BUILDERS` dict keys). Common drift: truncated form (e.g., `preset-flop-k72r` instead of `preset-flop-k72r-100bb`).
   - **Probe:** diff the marker strings in `spot_input.py` against the 12 keys in `_FIXTURE_BUILDERS`.
   - **Evidence stub:** `ui/views/spot_input.py:?` (preset emission); `ui/mock_solver_fixtures.py:611-625` (canonical IDs).

3. **X1: `cell_rgb_for_action_freqs(fold, call, raise_) -> (r, g, b)` added with pure Pio anchors.** [must-fix on convention drift]
   - Function exists in `ui/views/range_matrix.py`.
   - Anchors are **pure**: `(255, 0, 0)` for pure-fold, `(255, 255, 0)` for pure-call, `(0, 255, 0)` for pure-raise. NOT the existing `(220, 40, 40)` fade.
   - `cell_color()` unchanged for CSS-string consumers.
   - **Probe:** `python -c "from ui.views.range_matrix import cell_rgb_for_action_freqs; assert cell_rgb_for_action_freqs(1,0,0) == (255,0,0); assert cell_rgb_for_action_freqs(0,0,1) == (0,255,0)"`.
   - **Evidence stub:** `ui/views/range_matrix.py:?` (new function).

4. **X3: `DISPLAY_PALETTE` and `INPUT_PALETTE` module-level constants exist.** [must-fix on test failure]
   - `ui/views/range_matrix.py` exposes `DISPLAY_PALETTE` (or `STRATEGY_PALETTE`).
   - `ui/views/spot_input.py` exposes `INPUT_PALETTE` (or `RANGE_INPUT_PALETTE`).
   - Both are `tuple[tuple[int, int, int], ...]` form. Smoke 16 asserts disjointness (no shared `(r, g, b)` triple).
   - **Evidence stub:** `ui/views/range_matrix.py:?`; `ui/views/spot_input.py:?`.

5. **X2: `blocker-overlay` CSS class on blocked matrix cells.** [should-fix on missing class]
   - When `summary.blocked` is truthy in `_cell_tag`, the cell carries `.classes("blocker-overlay")` (or equivalent class assignment).
   - Smoke 15 (`test_blocker_cells_show_slashed_overlay`) asserts class presence.
   - **Evidence stub:** `ui/views/range_matrix.py:?` (`_cell_tag` block).

6. **X4: `expl-chart-linear-toggle` marker on log-scale checkbox.** [should-fix]
   - `ui/views/run_panel.py:221-224` (the `Log scale` checkbox) carries `.mark("expl-chart-linear-toggle")` (or `.props("data-marker=expl-chart-linear-toggle")`).
   - **Evidence stub:** `ui/views/run_panel.py:?`.

7. **X5: `oom-reduce-bet-sizes-button` in `_show_error`.** [should-fix]
   - `ui/views/run_panel.py:506` (`_show_error`) surfaces a marked button when `isinstance(runner.error, MemoryError)`.
   - Smoke 18 asserts marker presence; behavior can be a no-op or a state mutation.
   - **Evidence stub:** `ui/views/run_panel.py:?` (`_show_error` body).

8. **X6: `pushfold-switch-button` in ≤15 BB toast.** [should-fix]
   - `ui/app.py:294-302` or `ui/views/spot_input.py:373-380` (the ≤15 BB warning toast) carries a button with `.mark("pushfold-switch-button")`.
   - Behavior can be a stub `ui.notify(...)` linking to PR 11.
   - **Evidence stub:** `ui/app.py:?` or `ui/views/spot_input.py:?`.

9. **X7: `progress-eta` marker + `SolveRunner.compute_eta()` method.** [should-fix]
   - `ui/views/run_panel.py:469` (the ETA label) carries `.mark("progress-eta")`.
   - `ui/state.py` exposes a `compute_eta(self) -> float | None` method on `SolveRunner` matching the inline calculation.
   - **Evidence stub:** `ui/views/run_panel.py:?`; `ui/state.py:?` (method body).

10. **All 7 `@pytest.mark.xfail` decorators removed.** [must-fix on baseline regression]
    - `tests/test_ui_smoke.py` lines 452, 498, 531, 580, 620, 659, 683 — each decorator removed.
    - **Probe:** `grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py` — expected empty output.
    - Test bodies unchanged (only decorators removed).
    - **Evidence stub:** `tests/test_ui_smoke.py:?`.

11. **No scope creep into `ui/views/library_browser.py`.** [must-fix on scope leak]
    - PR 11 owns this file. PR 10a.5 must not touch it.
    - **Probe:** `git diff --stat HEAD -- ui/views/library_browser.py` — expected empty.
    - **Evidence stub:** `git diff --stat` output.

12. **No engine diff (`poker_solver/`).** [must-fix on scope leak]
    - PR 10a.5 is 100% UI-side.
    - **Probe:** `git diff --stat HEAD -- poker_solver/` — expected empty.
    - **Evidence stub:** `git diff --stat` output.

13. **No `pyproject.toml` diff.** [must-fix on scope leak]
    - No new deps, no version bump in-file (the v0.6.1 tag happens at commit/tag time).
    - **Probe:** `git diff --stat HEAD -- pyproject.toml` — expected empty.
    - **Evidence stub:** `git diff --stat` output.

14. **No new smoke tests (20-test count locked).** [must-fix on count drift]
    - The smoke-test count in `tests/test_ui_smoke.py` is unchanged.
    - **Probe:** `grep -c "^def test_" tests/test_ui_smoke.py` — same count as pre-PR-10a.5 (22 functions per audit_report_10a.md item 14).
    - Decorators removed; no new test functions added.
    - **Evidence stub:** `tests/test_ui_smoke.py:?`.

15. **All 20 smoke tests pass (the acceptance gate).** [must-fix on green-board regression]
    - `pytest tests/test_ui_smoke.py -v` shows **20 passed, 0 failed, 0 xfail**.
    - Green-board count rises from 8 / 20 (pre-PR-10a.5 baseline) to 20 / 20.
    - If `nicegui` is not installed in your audit env, that's fine — confirm tests are NOT xfail-decorated in source. Run-time confirmation may not be available.
    - **Evidence stub:** static read of `tests/test_ui_smoke.py` (decorator absence); pytest output if available.

16. **Code size within budget.** [should-fix on bloat]
    - Net LOC across the five UI files + test-file decorator removal: ~150-250 LOC.
    - **Probe:** `git diff --stat integration...HEAD` — sum the line changes.
    - Over-runs (>300 LOC) indicate scope creep; flag for review.
    - **Evidence stub:** `git diff --stat` output.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a5.md` with this exact structure:

```markdown
# PR 10a.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10a5-ui-conformance (worktree /private/tmp/poker_pr10a5)
**Diff size:** [N modified files = ±X LoC total]

**Test status:** [pytest tests/test_ui_smoke.py — pass/fail; xfail count; full suite delta]

## Must-fix

[F1-F5 marker drift not fixed; library_browser.py touched; engine diff non-empty; pyproject.toml touched; xfail decorators not all removed; 20-smoke-test gate fails; pure Pio anchors drifted. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[X2-X7 wire-ups incomplete or marker drift; code size over budget; convention drift in palette constants. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Scope items implemented but not tested. Each: backlog section reference + what's missing + suggested follow-up.]

## License compliance

[Explicit statement: zero new third-party deps; zero new code from competitor UIs; conformance pass adds only standard library + already-declared deps.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** F1-F5 marker drift not resolved (smoke tests fail); xfail decorators not all removed (baseline regression); `ui/views/library_browser.py` touched (scope leak — PR 11 territory); engine diff non-empty (scope leak); `pyproject.toml` touched (scope leak); pure Pio anchors drifted to fade values (convention break); 20 / 20 smoke-test gate fails. Blocks PR.
- **should-fix:** X2-X7 wire-ups incomplete (marker missing, button missing, method missing); palette constants named off-spec; code size over budget (>300 LOC); X4-X7 markers slightly drifted from test expectation. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that breaks the smoke-test green-board gate (20 / 20), leaks scope into PR 11 territory, or regresses the convention (pure Pio anchors → fade) → must-fix. The conformance pass has a narrow surface; a single must-fix should be rare.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote scope-freeze section numbers, especially §2 (F1-F5), §3 (X1-X7), §4 (recommended scope), §6 (out of scope).
- Scope-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr10_prep/audit_report_10a5.md`.
- If `nicegui` isn't installed in your audit environment, that's fine — the audit covers code structure + decorator removal + dependency declaration, not actually running the UI smoke tests.
- The conformance pass is narrow by design; if you find multiple must-fixes, that's a signal something went wrong in execution, not a normal audit outcome.

Begin by reading the scope freeze (`pr10a5_conformance_backlog.md`), then the originating audit's should-fix section, then the diff, then the modified files. Then write the report.
