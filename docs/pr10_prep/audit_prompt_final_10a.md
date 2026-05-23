# PR 10a audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep_10a.md` §3: READY-WITH-PATCHES (~60%) > clean READY (~25%) > NOT-READY (~15%).
> - Top three pre-flagged risk surfaces (audit MUST touch with file:line evidence): UI threading correctness (`audit_preprep_10a.md` §1.1), mock interface contract (§1.5), state.json atomicity (§1.2).
> - 7 design Q-locks per `pr10a_spec.md` §0.1: Q1 two-pane + right-sidebar; Q2 hand-class labels in cells, numeric freq on hover; Q3 default iters = 1000; Q4 4-of-6 bet sizes checked (33/75/100/all-in); Q5 combo inspector below matrix; Q6 reach filter 0.01 default; Q7 yellow "Mock mode" banner top, dismissible.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-10a-ui-mock-first` branch and you have not seen the design discussions. Your job is to audit the PR 10a implementation (NiceGUI browser UI with mock solver backend) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 10a is **mock-first by design**: the UI must consume an `ui.mock_solver` module that returns shape-locked `HUNLSolveResult` objects. PR 10b is a one-line import swap to the real `poker_solver.hunl_solver`. Any drift in the mock-vs-real interface contract → must-fix.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-10a-ui-mock-first` (branched from `integration`; verified via `fanout_ready_10a.md`).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 10a entries.
- **Locked Q1-Q7:** `pr10a_spec.md` §0.1 — the seven UX decisions agents must NOT deviate from.

## Inputs to read (in order)

1. **The spec:** internalize §0.1 (locked Q1-Q7), §1 (goal + non-goals — NOT desktop, NOT real solver, NOT new engine tests), §2 (design philosophy — range matrix is centerpiece), §3 (views + 12 fixtures), §4 (files + smoke tests), §5 (modifications), §6 (async solve handling — load-bearing threading model), §7 (range matrix mapping), §9 (state persistence), §11 (critical correctness), §12 (risks).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-10a-ui-mock-first`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 10a entries.
4. **The actual new / modified files:** at minimum
   - `ui/__init__.py`
   - `ui/app.py` (worker thread + `ui.timer` polling)
   - `ui/state.py` (state + `RangeWithFreqs` wrapper)
   - `ui/mock_solver.py` (shape-locked mock backend)
   - `ui/views/spot_input.py`
   - `ui/views/run_panel.py`
   - `ui/views/range_matrix.py`
   - `ui/views/tree_browser.py`
   - `ui/views/library_browser.py` (STUB for PR 11)
   - `poker_solver/cli.py` (`ui` subcommand added)
   - `pyproject.toml` (`[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`)
   - `README.md` (UI section added)
   - `tests/test_ui_smoke.py` (8 tests, `@pytest.mark.ui`)
   - `tests/data/mock_fixtures/*.json` (12 fixtures)
   - any other touched files

Do not actually run the UI server. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.1, §1.5 per `audit_preprep_10a.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **UI threading correctness — worker thread + `ui.timer` polling.** [HIGH-PROB must-fix per `audit_preprep_10a.md` §1.1]
   - Per spec §6.1 + §11 #1: solver runs in `threading.Thread` (NOT `asyncio.to_thread` — interruptible + GIL release in NumPy). The UI event loop is never directly called from worker code.
   - **Pre-flagged failure modes** (auditor MUST probe each per `audit_preprep_10a.md` §1.1):
     - (a) **Worker writes to UI primitives** — `grep -r "ui\." ui/mock_solver.py` for `ui.notify(...)`, `progress_bar.set_value(...)`, etc. inside worker context. Causes silent races, NiceGUI "element not bound to a client" errors. Must-fix.
     - (b) **Missing `ui.timer(0.5, update_ui)` polling** — spec mandates worker writes to `state.runner` dataclass; UI timer polls every 500ms. If `asyncio.to_thread` is used instead, NumPy GIL-release windows may still block the loop. Must-fix.
     - (c) **Stop-button latency** — `_stop_event.is_set()` checked at iter boundary. Test: `iterations=100_000`, click Solve, wait 0.5s, click Stop, wait 0.5s, assert `status in ('stopped', 'done')` AND `iteration < 50_000`. Must-fix if >1 iter delay.
   - **Evidence stub:** `ui/app.py:?` (worker thread spawn); `ui/mock_solver.py:?` (no `ui.*` calls); `ui/views/run_panel.py:?` (timer setup).

2. **Stop button cancellation flag works (halts within 1 iteration).**
   - Per spec §6.3 + §11 #3: worker checks `self._stop_event.is_set()` once per mock-iteration boundary. Max delay = one mock-iter's wall-clock.
   - Tested: `test_stop_button_halts_within_one_iteration` (§4 smoke test 5).
   - Pause is a separate flag (`_pause_event`); resume clears it.
   - **Evidence stub:** `ui/mock_solver.py:?` (iter loop with stop check); `tests/test_ui_smoke.py:?`.

3. **Matrix aggregator off-by-one (combo → 13×13 grid).** [must-fix on silent corruption]
   - Per spec §3.3 + §7.1 + §11 #2: `(row, col)` where `row = max(rank1, rank2)`, `col = min(rank1, rank2)`. Pairs on diagonal; suited above; offsuit below.
   - Hand-class ordering ASCII grid in §3.3 is the canonical reference.
   - Total combos: 13 pairs × 6 + 78 suited × 4 + 78 offsuit × 12 = **1326 distinct combos**.
   - Tested: `test_combo_to_cell_mapping_no_off_by_one` (§4 smoke test 7) — every hand class yields right count (6/4/12) + cell at `(row, col)` has expected label. Property test per §11 #2: `classify_combo(*combo) == hand_class` for every combo in `enumerate_combos(hand_class)`.
   - **Evidence stub:** `ui/views/range_matrix.py:?` — `combo_to_cell()` + tests.

4. **State.json atomicity (tmp + fsync + rename).** [pre-flagged should-fix per `audit_preprep_10a.md` §1.2]
   - Per spec §9.2 + `audit_preprep_10a.md` §1.2: atomic write pattern — write to `state.json.tmp`, `fsync()`, `os.rename()` to `state.json`. The rename is atomic on POSIX.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Non-atomic write** — direct `open(path, 'w').write(json.dumps(...))` corrupts on mid-write crash. Should-fix (user-home file, not engine).
     - (b) **No corrupt-load fallback** — malformed JSON (old version) → log warning, back up to `state.json.bak`, start from defaults. Don't crash on launch.
     - (c) **Save debounce missing** — required: `ui.timer(0.5, ...)` debounce with coalesced writes; saving on every keystroke thrashes disk.
   - **Evidence stub:** `ui/state.py:?` — `save_state()` + `load_state()` paths.

5. **Mock interface contract matches real solver shape.** [HIGH-PROB must-fix per `audit_preprep_10a.md` §1.5]
   - The whole point of PR 10a's mock-first design: PR 10b is a one-line import swap. Mock MUST return `HUNLSolveResult` byte-locked to PR 5 output shape.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **Field-name drift** — mock returns `{"strategy": ..., "ev": ...}` but real returns `{"final_strategy": ..., "exploitability": ...}`. PR 10b breaks on swap. Must-fix.
     - (b) **Missing fields** — `MemoryReport`, `StreetMemoryEntry`, per-iteration progress callbacks. Per `fanout_ready_10a.md`: "UI consumes only `HUNLSolveResult`, `MemoryReport`, `HUNLConfig`, `Range`/`Combo` — all shape-locked by PR 5."
     - (c) **`RangeWithFreqs` modifies `poker_solver.Range`** — Per spec §12 risk 6 + `audit_prompt.md` focus area 9: UI must WRAP `Range`, not modify it. Verify `git diff integration -- poker_solver/range.py` is empty.
   - Test: `python -c "from poker_solver.hunl_solver import HUNLSolveResult; from ui.mock_solver import solve_mock; assert isinstance(solve_mock(...), HUNLSolveResult)"`.
   - **Evidence stub:** `ui/mock_solver.py:?` — return type signature; `ui/state.py:?` — `RangeWithFreqs` definition.

6. **12 mock fixture spots are mathematically plausible.** [pre-flagged should-fix per `audit_preprep_10a.md` §1.3]
   - Per `pr10a_spec.md` lines 614, 657-670: 12 fixtures (4 preflop + 4 flop + 4 river per spec §3 fixture-design).
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **MDF violation** — river bluff freq must not exceed MDF cap. For bet-size B (fraction of pot), MDF_cap(B) = B/(1+B) of value combos. E.g., pot-sized bet (B=1.0) → 50% MDF cap. Any fixture violating this is implausibly mocked. Should-fix.
     - (b) **NaN/empty cells** — rendered matrix has missing frequencies or all-zero combos. Should-fix.
     - (c) **Blocker overlay missing on `flop_k72r_100bb`** — slashed-diagonal `╳╳╳` per spec §3.3 + line 397.
   - **Evidence stub:** `tests/data/mock_fixtures/*.json` — count + spot-check MDF math.

7. **Seven design Q-locks per `pr10a_spec.md` §0.1.** [pre-flagged should-fix per `audit_preprep_10a.md` §1.4]
   - **Q1 (must-verify):** Two-pane layout + right-sidebar inspector. Layout test: `test_page_renders` confirms layout markers.
   - **Q2 (must-verify):** Hand-class labels in cells (text rendered AA, KK, AKs, ...); numeric frequency on hover only.
   - **Q3 (must-verify):** Default iterations = 1000. Should-fix if drifted to 2000.
   - **Q4 (must-verify):** 4-of-6 bet sizes checked by default (33%, 75%, 100%, all-in). Should-fix if different default subset.
   - **Q5 (must-verify):** Combo inspector strip placed BELOW matrix (not right-sidebar).
   - **Q6 (must-verify):** Reach filter default 0.01. Should-fix if drifted.
   - **Q7 (must-fix candidate):** Yellow "Mock mode" banner at top, dismissible by user click. Banner is the safety rail — without it, user thinks PR 10a produces real solver output. Must-fix if absent or non-dismissible.
   - **Evidence stub:** `ui/app.py:?` (Q1 layout); `ui/views/range_matrix.py:?` (Q2, Q5); `ui/views/run_panel.py:?` (Q3, Q4, Q6); `ui/app.py:?` or `ui/views/banner.py` (Q7).

8. **NiceGUI dependency declared as optional extra.**
   - Per spec §5 + §1 non-goals: `pyproject.toml` adds `[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`.
   - **NOT added to base `dependencies`** (per spec §4 "Why split into `ui/` package outside `poker_solver/`": NiceGUI is heavyweight; engine must load with zero UI overhead).
   - The pytest marker `ui` is declared in `[tool.pytest.ini_options]` so tests can skip when nicegui isn't installed.
   - **Evidence stub:** `pyproject.toml:?` — optional-dependencies + markers blocks.

9. **CLI `ui` subcommand wired correctly.**
   - Per spec §5 + §10.C: `poker-solver ui --port 8080 --host 127.0.0.1 --dark-mode auto`.
   - **Lazy-imports** `ui.app` (only at command invocation time) so the rest of the CLI works without NiceGUI installed.
   - If NiceGUI not installed → catch `ImportError`, print "UI support not installed. Install with `pip install poker-solver[ui]`." Return exit code 2.
   - **Evidence stub:** `poker_solver/cli.py:?` — `ui` subcommand registration.

10. **Browser-served only (NOT a native desktop wrapper).**
    - Per spec §1 non-goals: "No native desktop wrapper. Packaging into `.dmg` with codesign+notarize is **PR 11**."
    - NiceGUI's `native=True` mode (pywebview) is explicitly **not** used in PR 10a.
    - Server binds to `127.0.0.1` by default (no `0.0.0.0`, no auth, no TLS).
    - Flag if `native=True` is used or if pywebview is added to deps.
    - **Evidence stub:** `ui/app.py:?` — `ui.run(...)` call; `pyproject.toml:?` — no pywebview.

11. **`RangeWithFreqs` wraps `poker_solver.Range` (does NOT modify it).** [must-fix on engine pollution]
    - Per spec §12 risk 6: PR 10a needs per-combo float frequencies; `poker_solver.Range` is membership-only (PR 1).
    - **`ui/state.py::RangeWithFreqs` wraps `Range`** + adds `dict[Combo, float]` frequency layer.
    - **Does NOT modify `poker_solver/range.py`** — verify `git diff integration -- poker_solver/range.py` returns empty diff. Must-fix if non-empty.
    - **Evidence stub:** `ui/state.py:?` — `RangeWithFreqs` class.

12. **No new tests in `poker_solver/` test surface.**
    - Per spec §1 non-goals: "No new solver tests. PR 10a's tests cover *the UI*."
    - `tests/test_ui_smoke.py` is the ONLY new test file.
    - All PR 1-9 tests still pass unchanged.
    - **Evidence stub:** `git diff integration -- tests/` excluding `tests/test_ui_smoke.py` and `tests/data/mock_fixtures/` should be empty.

13. **Library viewer is a STUB (PR 11 wiring point).**
    - Per spec §3.5: `ui/views/library_browser.py` contains header label "Solve library (PR 11)", placeholder text, disabled "Load from disk" button, three faked rows.
    - Clicking faked rows → toast "PR 11 — load from disk is not yet wired".
    - Tested: `test_library_dialog_opens` (§4 smoke test 8).
    - **Evidence stub:** `ui/views/library_browser.py:?` — stub structure.

14. **Smoke test count.**
    - Per spec §4 / §10.C: **8 smoke tests** in `tests/test_ui_smoke.py`. Each marked `@pytest.mark.ui` so they skip cleanly when nicegui isn't installed.
    - Tests use NiceGUI's `User` fixture (async, in-process, no real browser).
    - Spec §10.C list: page renders, board picker accepts 3 cards, range input via string, solve button starts worker, stop button halts within 1 iter, matrix renders 169 cells, combo-to-cell mapping no off-by-one, library dialog opens.
    - **Evidence stub:** `tests/test_ui_smoke.py:?` — count test functions.

15. **`ui/` package is OUTSIDE `poker_solver/`.**
    - Per spec §4 "Why split": `ui/` is a sibling of `poker_solver/` and `crates/`.
    - Verify: `ls /Users/ashen/Desktop/poker_solver/ui/` exists as sibling directory, not under `poker_solver/`.
    - **Evidence stub:** `ls /Users/ashen/Desktop/poker_solver/ui/` listing.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a.md` with this exact structure:

```markdown
# PR 10a audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10a-ui-mock-first
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_ui_smoke.py — pass/fail (note skip count if nicegui not installed); full suite delta]

## Must-fix

[Worker thread calls UI directly; `asyncio.to_thread` used instead of `threading.Thread`; stop latency >1 iter; matrix off-by-one (corrupts strategy display); mock interface drift from `HUNLSolveResult`; `poker_solver/range.py` modified (engine pollution); Q7 banner missing or non-dismissible; `native=True` used; nicegui in base dependencies; `ui/` placed inside `poker_solver/`. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[State.json non-atomic; fixture MDF violations; Q3/Q4/Q6 default drift; combo inspector mis-placed; missing corrupt-load fallback; test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-15 matching the 15 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: NiceGUI is MIT (third-party dep declared as optional extra); no other new deps; no code copied from competitor UI projects (Pio, GTOW); colour convention is widely-used poker-industry standard (not copyrightable expression).]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** worker thread calls UI directly, `asyncio.to_thread` blocks loop, stop-button latency >1 iter, matrix off-by-one (silent strategy corruption), mock returns wrong shape (breaks PR 10b swap), `poker_solver/range.py` modified, Q7 banner missing/non-dismissible (user thinks mocks are real), `native=True` (premature PR 11), nicegui in base deps, `ui/` in wrong location. Blocks PR.
- **should-fix:** state.json not atomic, fixture MDF violations, Q3/Q4/Q6 default drift, combo inspector mis-placed, missing corrupt-load fallback, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently corrupts strategy display (off-by-one), shows mocks-as-real (Q7 missing), or breaks the PR 10b swap (mock shape drift) → must-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §0.1 (Q1-Q7 locks), §6 (threading), §9.2 (state persistence), §11 (correctness), §12 (risks).
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr10_prep/audit_report_10a.md`.
- HIGH-PROB risk surfaces (focus areas 1, 5 — and the three sub-probes in each) MUST get paragraph-level discussion even with no defect found.
- If `nicegui` isn't installed in your audit environment, that's fine — the audit covers code structure + tests + dependency declaration, not actually running the UI.

Begin by reading the spec (especially §0.1 Q-locks + §6 threading), then the diff, then the new files. Then write the report.
