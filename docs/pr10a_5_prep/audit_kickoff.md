# PR 10a.5 audit kickoff (pre-staged, fire-on-implementer-completion)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **When to fire:** after the PR 10a.5 implementer agent returns and reports `pr_report.md` is complete. The branch under audit is `pr-10a.5-conformance` (already exists; implementer is committing onto it). DO NOT fire while the implementer is still in flight — the diff will be incomplete and the audit will mis-classify.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `docs/pr10_prep/pr10a5_conformance_backlog.md` §4 + the existing `docs/pr10_prep/audit_prompt_10a5.md` framing: **READY** (~70%) > READY-WITH-PATCHES (~25%) > NOT-READY (~5%). Narrow conformance pass, low surface area, low risk.
> - Conformance scope: 5 hard failures (F1-F5) + 7 xfailed tests (X1-X7). Audit MUST touch each with file:line evidence.
> - Hard-forbidden files: `ui/views/library_browser.py` (PR 11 owns), any `poker_solver/*`, any `crates/*`, `pyproject.toml`. Any edit there is must-fix scope leak.
> - Production-code touches ARE allowed per the implementer's `pr_report.md` §4 (conformance plumbing only — `cell_rgb_for_action_freqs`, palette constants, blocker class, ETA method, OOM/pushfold buttons, marker rewrites). Audit must verify these are **plumbing, not semantics** — the existing `cell_color()` fade formula and `SolveRunner._worker` must be byte-unchanged.
> - This kickoff doc was pre-staged while the implementer was in flight; if the implementer's `pr_report.md` already exists at `docs/pr10a_5_prep/pr_report.md`, treat that as truth-of-record for the diff scope.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-10a.5-conformance` branch and you have not seen the design discussions. Your job is to audit the PR 10a.5 implementation (UI smoke-test conformance pass) against the scope freeze and report findings in a structured Markdown report.

Treat the scope-freeze document and the implementer's `pr_report.md` as the sources of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 10a.5 is a **conformance pass**, not a feature PR. It fixes 5 hard failures introduced by Agent B's multi-tag `data-marker` drift in PR 10a, and wires up 7 surfaces that were `@pytest.mark.xfail`-decorated in v0.6.0. Acceptance gate: all 22 smoke tests pass (no `xfail`, no `fail`) on `tests/test_ui_smoke.py`. Target version: **v0.6.1 PATCH** (tag deferred to release time).

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-10a.5-conformance`. Branched from `integration` tip `62c75d5` (Integration: merge PR 11 followup v3 — nicegui pin bump). Verify via `git log integration..HEAD --oneline` from the repo root.
- **Scope freeze (authoritative):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a5_conformance_backlog.md` — read end-to-end first.
- **Originating audit (PR 10a):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a.md` — should-fix items #1, #2, #3 are what PR 10a.5 closes.
- **Implementer report:** `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/pr_report.md` — read end-to-end. §1 lists the acceptance gates and the diff scope; §2 has the per-test F1-F5 / X1-X7 changelog; §4 lists every production-code change with justification; §5 enumerates out-of-scope checks.
- **Previous-PR audit-prompt precedent:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt_10a5.md` (pre-implementer version of this doc — useful for cross-reference but the implementer's report is now the more accurate snapshot of what landed). And `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_prompt_final.md` for the analogous "narrow-scope mechanical-fix audit" pattern.

## Inputs to read (in order)

1. **The scope freeze:** `pr10a5_conformance_backlog.md`. Internalize §2 (F1-F5 table — root cause + file:line), §3 (X1-X7 table — anchor markers / constants), §4 (recommended scope — six numbered steps), §6 (out of scope — Q-locks, fixtures, mock signature, engine, version bump beyond v0.6.1 all frozen).
2. **The originating PR-10a audit:** `audit_report_10a.md`. Should-fix items #1, #2, #3.
3. **The implementer's report:** `docs/pr10a_5_prep/pr_report.md`. Especially §1 acceptance gates, §2.1 (F1-F5 changelog), §2.2 (X1-X7 changelog), §2.3 (test-wiring micro-fixes), §3 (spec/solver contract untouched), §4 (production-code justification), §5 (out-of-scope confirmations).
4. **The smoke-test file:** `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py`. Confirm: pre-PR-10a.5 baseline had 7 `@pytest.mark.xfail` decorators; PR 10a.5 must have removed all 7. Also confirm `def test_` count is unchanged from PR-10a's 22.
5. **The branch diff:** from the repo root, run `git diff integration...HEAD` and `git log integration..HEAD --oneline`. Confirm 7 modified files (the implementer's report lists them in §7). Cross-check the file list against the §1 `git diff --stat` block in `pr_report.md`. Confirm LOC delta ~150-300 net.
6. **The actual modified files (7 expected):**
   - `tests/test_ui_smoke.py` (xfail decorator removal + 3 test-wiring micro-fixes per §2.3)
   - `ui/app.py` (render-pane wiring + `__mp_main__` guard)
   - `ui/state.py` (`SolveRunner.compute_eta` + fixture-id repr fix)
   - `ui/views/range_matrix.py` (DISPLAY_PALETTE + `cell_rgb_for_action_freqs` + `.mark()` migrations + `has_blocker` + `blocker-overlay` class)
   - `ui/views/run_panel.py` (`expl-chart-linear-toggle` + `progress-eta` + `oom-reduce-bet-sizes-button` + `EChart.options` in-place mutation)
   - `ui/views/spot_input.py` (INPUT_PALETTE + `pushfold-switch-button` + ≤15 BB warning toast button)
   - `ui/views/tree_browser.py` (`.mark()` migrations: `tree-browser`, `tree-reach-slider`, `tree-truncation-badge`, `tree-widget`)
7. **Out-of-scope confirmation files (expected ZERO diff):** `poker_solver/*`, `crates/*`, `pyproject.toml`, `ui/views/library_browser.py`, all spec docs (`pr10a_spec.md`, `pr10b_spec.md`, `pr11_spec.md`), all fixture files (`ui/mock_solver_fixtures.py`, `ui/mock_solver.py`).

Do not actually run the UI server. Audit the *committed* code + tests. If `nicegui` is installed in your audit env you may run `pytest tests/test_ui_smoke.py -v` to confirm the 22 / 22 acceptance gate; if not, confirm gate compliance from source (decorator absence + marker presence + constant exports).

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. HIGH-PROB items (1, 10, 11-14 — the marker-drift cluster + scope-leak guards) MUST receive paragraph-level discussion even if no defect is found.

1. **F1-F5: multi-tag `data-marker` drift fixed** (HIGH-PROB; this was the originating defect class). [must-fix on silent test failure]
   - The committed PR 10a.5 must replace the comma-separated `data-marker=foo,bar-baz` pattern at `ui/views/range_matrix.py:735` and `:844` (PR-10a-as-shipped baseline) with single-value form via NiceGUI's `.mark(name)` shorthand or two separate `.props()` chains. Per `pr_report.md` §2.1 F1/F3/F5 + §2.2, the implementer chose `.mark()` migration with whitespace-delimited multi-token values per NiceGUI 3.x `element.py:342` semantics.
   - **Probe:** `grep -nE 'data-marker=[a-z0-9-]+,[a-z0-9-]+' ui/views/range_matrix.py ui/views/spot_input.py ui/views/run_panel.py ui/views/tree_browser.py ui/app.py` — expected empty.
   - **Probe:** confirm cell markers resolve via `User.find(marker="matrix-cell")` to 169 elements (smoke 6 / 7 / 1 pass).
   - **Cross-check:** `pr_report.md` §2.1 cites `range_matrix.py:870 .mark("range-matrix-display")` and `range_matrix.py:888 .mark(f"matrix-cell matrix-cell-{cell.hand_class}")`. Verify those line numbers (or the equivalent predicate if drifted).
   - **Evidence stub:** `ui/views/range_matrix.py:?` (post-fix line); `tests/test_ui_smoke.py:?` (smoke 1/6/7 assertion lines).

2. **F4: spot-input preset markers match 12 fixture IDs.** [must-fix on drift]
   - Per `pr_report.md` §2.1 F4: `state.list_fixture_preset_ids` now reads `getattr(p, "id", getattr(p, "preset_id", p))` — the FixturePreset dataclass exposes `.id`, not `.preset_id`. Verify the 12 fixture IDs from `ui/mock_solver_fixtures.py` `_FIXTURE_BUILDERS` dict keys match the markers emitted in `spot_input.py`.
   - **Probe:** diff the marker strings in `spot_input.py` against the 12 keys in `_FIXTURE_BUILDERS`. Common drift to watch for: truncated form (e.g., `preset-flop-k72r` instead of `preset-flop-k72r-100bb`).
   - **Evidence stub:** `ui/state.py:976` (per pr_report); `ui/views/spot_input.py:?` (preset emission); `ui/mock_solver_fixtures.py:611-625` (canonical IDs).

3. **X1: `cell_rgb_for_action_freqs(fold, call, raise_) -> (r, g, b)` added with pure Pio anchors.** [must-fix on convention drift]
   - Function exists in `ui/views/range_matrix.py`.
   - Anchors are **pure**: `(255, 0, 0)` for pure-fold, `(255, 255, 0)` for pure-call, `(0, 255, 0)` for pure-raise. NOT the existing `(220, 40, 40)` fade. Per `pr_report.md` §2.2 X1 and `pr10a5_conformance_backlog.md` §3 X1.
   - `cell_color()` unchanged for CSS-string consumers — diff the function definition vs `integration`'s version.
   - **Probe (if nicegui is importable):** `python -c "from ui.views.range_matrix import cell_rgb_for_action_freqs; assert cell_rgb_for_action_freqs(1,0,0) == (255,0,0); assert cell_rgb_for_action_freqs(0,0,1) == (0,255,0); assert cell_rgb_for_action_freqs(0,1,0) == (255,255,0)"`.
   - **Evidence stub:** `ui/views/range_matrix.py:?` (new function with pure anchors).

4. **X3: `DISPLAY_PALETTE` and `INPUT_PALETTE` module-level constants exist and are disjoint.** [must-fix on test failure]
   - `ui/views/range_matrix.py` exposes `DISPLAY_PALETTE` (or `STRATEGY_PALETTE`) per `pr_report.md` §2.2 X3.
   - `ui/views/spot_input.py` exposes `INPUT_PALETTE` (or `RANGE_INPUT_PALETTE`).
   - Both expose `(r, g, b)` triples. Smoke 16 (`test_input_matrix_palette_disjoint_from_display_palette`) asserts no shared triple. Per `pr_report.md` §2.2 X3, INPUT_PALETTE = `((248,250,252,"#f8fafc"),(30,100,220,"#1e64dc"))` — the 4-tuple form includes a CSS string but the first 3 elements form the RGB triple; verify the smoke test's disjointness assertion handles this shape correctly.
   - **Evidence stub:** `ui/views/range_matrix.py:?` (DISPLAY_PALETTE); `ui/views/spot_input.py:?` (INPUT_PALETTE); `tests/test_ui_smoke.py:531-557` or wherever smoke 16 lives.

5. **X2: `blocker-overlay` CSS class on blocked matrix cells + `CellSummary.has_blocker`.** [should-fix on missing class; must-fix if smoke 15 still fails]
   - Per `pr_report.md` §2.2 X2: `CellSummary.has_blocker: bool` added; `.classes("blocker-overlay")` applied when `summary.blocked or summary.has_blocker`. Cited at `range_matrix.py:900-907`.
   - Smoke 15 (`test_blocker_cells_show_slashed_overlay`) asserts class presence.
   - **Verify:** the `has_blocker` derivation in `cell_strategy_summary` is correct — flags ANY combo blocking (not a no-op). If the derivation is a no-op (e.g., always False), the smoke test passes by accident on cells that happen to be already-blocked; flag as should-fix.
   - **Evidence stub:** `ui/views/range_matrix.py:?` (CellSummary class definition); `ui/views/range_matrix.py:?` (_cell_tag / overlay application).

6. **X4: `expl-chart-linear-toggle` marker on log-scale checkbox + EChart.options mutation pattern.** [should-fix on marker miss; nice-to-fix on patterns]
   - Per `pr_report.md` §2.2 X4: `run_panel.py:225 log_toggle.mark("expl-chart-linear-toggle")`. Also `_redraw_chart` uses `chart.options.clear(); chart.options.update(new_options)` because NiceGUI 3.x makes `EChart.options` read-only.
   - **Probe:** `grep -n 'expl-chart-linear-toggle' ui/views/run_panel.py` — expected one hit.
   - **Probe:** `grep -nE 'chart\.options\s*=' ui/views/run_panel.py` — expected ZERO direct reassignments (read-only in 3.x); only `.clear()` + `.update()`.
   - **Evidence stub:** `ui/views/run_panel.py:?` (mark line); `ui/views/run_panel.py:?` (`_redraw_chart` body).

7. **X5: `oom-reduce-bet-sizes-button` in `_show_error` when error is MemoryError.** [should-fix]
   - Per `pr_report.md` §2.2 X5: button surfaced when `isinstance(err, MemoryError)`, marked `oom-reduce-bet-sizes-button`. On click, prunes bet sizes >100% pot from `state.current_spot.bet_sizes_checked` and emits a follow-up toast.
   - **Verify:** the button is gated by `isinstance` check, not unconditional. If unconditional → should-fix (visible on non-OOM errors → UX confusion).
   - **Verify:** the pruning logic is bounded (doesn't remove ALL bet sizes leaving a degenerate spot). If unbounded → should-fix.
   - **Evidence stub:** `ui/views/run_panel.py:?` (`_show_error` body with isinstance gate + button creation).

8. **X6: `pushfold-switch-button` in ≤15 BB toast + 100→15 BB test-wiring fix.** [should-fix]
   - Per `pr_report.md` §2.2 X6: button alongside the ≤15 BB warning toast at `spot_input.py:401-410`, marked `pushfold-switch-button`. On click, emits CLI-pointer toast.
   - Per `pr_report.md` §2.3 item 3: the test itself was rewired to drive `stack-input-p0/p1` via `element.value = 15` because NiceGUI 3.x `User.type()` APPENDS to current value (so `.type("15")` on 100 BB produced 10015 — see `nicegui/user_interaction.py:70`).
   - **Verify this is the only change to the test body** (the §2.3 changelog says it is — confirm via `git diff integration -- tests/test_ui_smoke.py | grep -E '^[+-]' | grep -v 'xfail'`).
   - **Evidence stub:** `ui/views/spot_input.py:?` (button + handler); `tests/test_ui_smoke.py:?` (test-wiring fix).

9. **X7: `progress-eta` marker + `SolveRunner.compute_eta()` method.** [should-fix]
   - Per `pr_report.md` §2.2 X7: `SolveRunner.compute_eta() -> float | None` added at `state.py:603-637`; ETA label at `run_panel.py:257-259` gained `progress-eta` mark. Fast-path branch exposes `start_time_monotonic` / `current_time_monotonic` / `target_iterations` for tests to populate directly.
   - **Verify:** `compute_eta` is pure arithmetic on existing iteration/timing fields (no side effects on `SolveRunner._worker`). If it mutates state or calls into the worker thread → must-fix (concurrency hazard).
   - **Verify:** the linear extrapolation formula is `(target_iterations - iteration) / (iters/sec)`. Spec-silent edge cases (zero iters/sec, iteration > target) should return `None` or a sentinel — confirm.
   - **Evidence stub:** `ui/state.py:603-637` (per pr_report); `ui/views/run_panel.py:257-259` (mark line).

10. **All 7 `@pytest.mark.xfail` decorators removed.** [must-fix on baseline regression]
    - `tests/test_ui_smoke.py` baseline lines 452, 498, 531, 580, 620, 656, 683 (X1-X7 per `pr_report.md` §2.2; line numbers may have drifted slightly post-edit) — each decorator removed.
    - **Probe:** `grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py` — expected empty output.
    - Test bodies should be unchanged EXCEPT the three micro-wiring fixes documented in `pr_report.md` §2.3 (test_stop_button_halts_within_one_iteration, test_library_dialog_opens, test_pushfold_dispatch_at_15bb).
    - **Verify:** the §2.3 wiring fixes are minimal-touch (no assertions changed, no new test branches added).
    - **Evidence stub:** `tests/test_ui_smoke.py:?` (grep output); `git diff integration...HEAD -- tests/test_ui_smoke.py | wc -l`.

11. **No scope creep into `ui/views/library_browser.py`.** [must-fix on scope leak]
    - PR 11 owns this file (just landed on integration tip `62c75d5`). PR 10a.5 must not touch it.
    - **Probe:** `git diff --stat integration...HEAD -- ui/views/library_browser.py` — expected empty.
    - **Note:** `pr_report.md` §2.3 item 2 mentions that `test_library_dialog_opens` was modified to drop a `library-stub-row-0` assertion (because PR 11 wired the real library, so stub-row markers only appear when the library module is unimportable). This is a TEST change, NOT a `library_browser.py` change. Verify the production file is untouched.
    - **Evidence stub:** `git diff --stat` output.

12. **No engine diff (`poker_solver/`, `crates/`).** [must-fix on scope leak]
    - PR 10a.5 is 100% UI-side per `pr_report.md` §3.
    - **Probe:** `git diff --stat integration...HEAD -- poker_solver/ crates/` — expected empty.
    - **Evidence stub:** `git diff --stat` output.

13. **No `pyproject.toml` diff.** [must-fix on scope leak]
    - No new deps, no version bump in-file. The v0.6.1 tag happens at commit/tag time, not in `pyproject.toml`.
    - **Probe:** `git diff --stat integration...HEAD -- pyproject.toml` — expected empty.
    - **Evidence stub:** `git diff --stat` output.

14. **No new smoke tests (22-test count locked).** [must-fix on count drift]
    - The smoke-test count in `tests/test_ui_smoke.py` is unchanged from PR 10a's 22.
    - **Probe:** `grep -c "^def test_" tests/test_ui_smoke.py` — expected 22.
    - Decorators removed; test-bodies micro-edited (3 places); no new test functions added.
    - **Evidence stub:** `tests/test_ui_smoke.py:?` (count); `git diff integration...HEAD -- tests/test_ui_smoke.py | grep '^+def test_'` (expected zero).

15. **All 22 smoke tests pass (the acceptance gate).** [must-fix on green-board regression]
    - `pytest tests/test_ui_smoke.py -v` shows **22 passed, 0 failed, 0 xfail**.
    - Green-board count rises from 8 / 22 (pre-PR-10a.5 baseline per `pr_report.md` §1) to 22 / 22.
    - If `nicegui` is not installed in your audit env, that's fine — confirm tests are NOT xfail-decorated in source AND the markers/constants/methods the tests anchor to exist in the modified files. Run-time confirmation is preferred but not blocking.
    - The implementer's `pr_report.md` §1 cites `/tmp/pytest_run1.log` for the 22/22 result. If that file exists, read it; otherwise rely on static verification.
    - **Evidence stub:** static read of `tests/test_ui_smoke.py` (decorator absence + marker anchor presence in views); pytest output if available.

16. **Production-code touches are plumbing, not semantics.** [must-fix on semantic drift]
    - Per `pr_report.md` §4: every production diff must be "conformance plumbing." Verify the following are byte-unchanged on the audit branch vs `integration`:
      - `cell_color()` in `range_matrix.py` (existing fade formula `(220, 40, 40)` etc.)
      - `SolveRunner._worker` in `state.py` (no logic changes; `compute_eta` is additive)
      - All solver call sites (`poker_solver/dcfr.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`)
    - **Probe:** `git diff integration -- poker_solver/ crates/` empty; `git diff integration -- ui/views/range_matrix.py | grep -E '^[+-].*cell_color'` should show NO lines except imports.
    - **Failure mode:** if `cell_color()` was rewritten or `SolveRunner._worker` got new branches, flag as must-fix + revert.
    - **Evidence stub:** `git diff` output for each cited file.

17. **Code size within budget.** [should-fix on bloat]
    - Per `pr_report.md` §1: 7 files changed, +245 / -76 LoC (~169 net). Within the conformance backlog's 150-250 LOC estimate (§4 "Estimated effort").
    - **Probe:** `git diff --stat integration...HEAD` — sum the line changes; expect net <300 LoC.
    - Over-runs (>300 LOC) indicate scope creep; flag for review.
    - **Evidence stub:** `git diff --stat` output.

18. **Implementer report (`pr_report.md`) is accurate.** [should-fix on discrepancy]
    - The implementer's `docs/pr10a_5_prep/pr_report.md` must match the actual diff. Common drift:
      - File list in §1 / §7 doesn't match `git diff --stat`.
      - LOC numbers in §1 don't match `git diff --shortstat`.
      - F-table line citations in §2.1 don't match current source line numbers (post-edit drift is OK if the predicate is correct; re-grep if unsure).
      - X-table line citations in §2.2 don't match.
      - §3's "spec / solver contract untouched" claim is contradicted by a diff (e.g., a sneaky `poker_solver/*` edit).
      - §5 out-of-scope confirmations contradicted by diffs.
    - **For each discrepancy:** flag as should-fix + recommend the implementer regenerate the report from the final diff.
    - **Evidence stub:** specific section in `pr_report.md` + corresponding `git diff` output.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/audit_report.md` with this exact structure:

```markdown
# PR 10a.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10a.5-conformance
**Branched-from:** integration tip 62c75d5 (Integration: merge PR 11 followup v3)
**Diff size:** [N modified files = ±X LoC total — expect 7 files, ~245 / -76 ≈ +169 net]

**Test status:** [pytest tests/test_ui_smoke.py — pass/fail; xfail count expected 0; full suite delta]

**Implementer report:** [reviewed `docs/pr10a_5_prep/pr_report.md` — accurate / discrepancies noted]

## Item-by-item F-table verification (F1-F5)

[5 hard failures from pr10a5_conformance_backlog.md §2. Each: PASS/FAIL + file:line evidence + verification note.]

## Item-by-item X-table verification (X1-X7)

[7 xfail items from pr10a5_conformance_backlog.md §3. Each: PASS/FAIL + file:line evidence + verification note.]

## Must-fix

[F1-F5 marker drift not fixed; library_browser.py touched; engine diff non-empty; pyproject.toml touched; xfail decorators not all removed; 22-smoke-test gate fails; pure Pio anchors drifted; production-code touch crossed into semantics (cell_color, _worker mutated). Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[X2-X7 wire-ups incomplete or marker drift; code size over budget; convention drift in palette constants; pr_report.md discrepancies; has_blocker derivation a no-op; oom button not gated by isinstance; compute_eta edge cases unhandled. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-18 matching the 18 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Scope items implemented but not tested. Each: backlog section reference + what's missing + suggested follow-up. Note: per scope §6, no NEW smoke tests are allowed — gaps go to a future PR.]

## License compliance

[Explicit statement: zero new third-party deps; zero new code from competitor UIs; conformance pass adds only standard library + already-declared deps. Cite specific files.]

## Implementer-report accuracy audit

[Cross-check `docs/pr10a_5_prep/pr_report.md` against the actual diff. Any discrepancies (file list, LOC, line citations, scope claims) listed here with severity.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification. **Expected verdict given the narrow conformance scope: READY**, with at most should-fix items around `pr_report.md` drift or palette-constant naming. NOT-READY would be a surprise (scope leak, marker drift unfixed, decorators not all removed) and warrants escalation back to the orchestrator before writing the report.]
```

## Severity rules

- **must-fix:** F1-F5 marker drift not resolved (smoke tests fail); xfail decorators not all removed (baseline regression); `ui/views/library_browser.py` production code touched (scope leak — PR 11 territory); engine diff non-empty (`poker_solver/`, `crates/` — scope leak); `pyproject.toml` touched (scope leak); pure Pio anchors drifted to fade values (convention break); 22 / 22 smoke-test gate fails; production-code touch crossed into semantics (e.g., `cell_color()` formula changed, `SolveRunner._worker` got new branches). Blocks PR.
- **should-fix:** X2-X7 wire-ups incomplete (marker missing, button missing, method missing); palette constants named off-spec; code size over budget (>300 LOC); `pr_report.md` discrepancies vs actual diff; `has_blocker` derivation is a no-op; OOM button not gated by `isinstance(err, MemoryError)`; `compute_eta` edge cases (zero iters/sec, iteration > target) unhandled; X4 EChart `chart.options =` direct reassignment instead of `.clear() + .update()` mutation. Doesn't block.
- **nice-to-fix:** style, naming, comments. Pure polish.

When in doubt: anything that breaks the smoke-test green-board gate (22 / 22), leaks scope into PR 11 / engine / pyproject territory, or regresses the convention (pure Pio anchors → fade) → must-fix. The conformance pass has a narrow surface; multiple must-fixes signal something went wrong in execution, not a normal audit outcome.

## Procedural notes

- **READ-ONLY DIFF REVIEW.** Cite **file paths and line numbers** for every finding. **Do NOT commit, push, or modify any code on `pr-10a.5-conformance`.** The only write allowed is `docs/pr10a_5_prep/audit_report.md`.
- Quote scope-freeze section numbers, especially §2 (F1-F5), §3 (X1-X7), §4 (recommended scope), §6 (out of scope).
- Quote implementer-report section numbers when cross-checking claims (`pr_report.md` §1 / §2 / §3 / §4 / §5).
- Scope-silent behavior → "Spec coverage gaps".
- If `nicegui` isn't installed in your audit environment, that's fine — the audit covers code structure + decorator removal + dependency declaration, not actually running the UI smoke tests. Static verification of marker presence + decorator absence + constant exports is sufficient.
- HIGH-PROB risk surfaces (focus areas 1, 10, 11-14) MUST get paragraph-level discussion even with no defect found.
- For scope-leak enumeration: `git diff integration...HEAD --stat` then verify each touched file is in the 7-file allow-list (the §7 file list in `pr_report.md`).
- **No branch switches.** Stay on `pr-10a.5-conformance` for the entire audit. If you need to compare against `integration`, use `git diff integration...HEAD -- <file>` from within the audit branch — do NOT `git checkout integration`. (Per `feedback_no_concurrent_branch_ops` discipline: parallel agents may be active in the shared working tree.)

Begin by reading the scope freeze (`pr10a5_conformance_backlog.md`), then `audit_report_10a.md` should-fix items #1/2/3, then the implementer's report (`docs/pr10a_5_prep/pr_report.md`), then the diff. Then write the report.

**Expected verdict given the narrow conformance scope + curated 12-item F+X list + the implementer's already-self-checked production touches: READY**, with at most a few should-fix items on `pr_report.md` accuracy or palette-constant naming. NOT-READY would indicate scope leak (engine / pyproject / library_browser touched), marker drift unfixed, or decorators not all removed — all surprising; warrant escalation back to the orchestrator before writing the report.
