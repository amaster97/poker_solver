# PR 10 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-10a-ui-mock-first` branch and you have not seen the design discussions. Your job is to audit the PR 10 implementation (NiceGUI browser UI for the poker solver) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-10a-ui-mock-first` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 10 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + non-goals — NOT a desktop wrapper; that's PR 11), §2 (design philosophy — range matrix is the centerpiece), §3 (five core views), §4 (files to create), §5 (files to modify), §6 (async solve handling — load-bearing complexity), §7 (range matrix details), §8 (decision tree browser), §9 (state persistence), §11 (critical correctness items), §12 (risks).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-10a-ui-mock-first`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 10 entries.
4. **The actual new / modified files:** at minimum
   - `ui/__init__.py`
   - `ui/app.py`
   - `ui/state.py`
   - `ui/views/spot_input.py`
   - `ui/views/run_panel.py`
   - `ui/views/range_matrix.py`
   - `ui/views/tree_browser.py`
   - `ui/views/library_browser.py` (stub for PR 11)
   - `poker_solver/cli.py` (`ui` subcommand added)
   - `pyproject.toml` (`[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`)
   - `README.md` (UI section added)
   - `tests/test_ui_smoke.py`
   - any other touched files

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **Async solve never blocks UI thread.**
   - Per spec §6.1 + §11 #1: solver runs in a `threading.Thread` (not asyncio.to_thread because we need interruptibility AND resumability — per §6.4). The UI event loop is never directly called from worker code.
   - Progress updates via `ui.timer(0.5, update_ui)` polling pattern (NOT direct calls from worker thread).
   - NumPy operations inside DCFR release the GIL (~70% of solve time); UI remains responsive.
   - Tested: `test_solve_button_starts_worker` (§4 smoke test 4) — clicks Solve, asserts `state.runner.status == 'running'` within 200ms, asserts worker thread alive.

2. **Stop button cancellation flag works (halts within 1 iteration).**
   - Per spec §6.3 + §11 #3: worker checks `self._stop_event.is_set()` once per iteration boundary. Max delay = one DCFR iteration's wall-clock.
   - Tested: `test_stop_button_halts_within_one_iteration` (§4 smoke test 5) — sets `iterations=100_000`, clicks Solve, waits 0.5s, clicks Stop, waits 0.5s, asserts `status in ('stopped', 'done')` AND `iteration < 50_000`.
   - Pause is a separate flag (`_pause_event`); resume clears it.

3. **Matrix aggregator off-by-one (combo → 13×13 grid).**
   - Per spec §3.3 + §7.1 + §11 #2: the 13×13 grid uses `(row, col)` where `row = max(rank1, rank2)`, `col = min(rank1, rank2)`. Pairs on diagonal; suited above (or by convention, above the diagonal reading left-to-right); offsuit below.
   - Hand-class ordering ASCII grid in §3.3 is the canonical reference.
   - Total combos: 13 pairs × 6 + 78 suited × 4 + 78 offsuit × 12 = **1326 distinct combos**.
   - Tested: `test_combo_to_cell_mapping_no_off_by_one` (§4 smoke test 7) — for every hand class, `enumerate_combos(class)` yields right count (6/4/12) + cell at `(row, col)` has expected `hand-class` label.
   - Property test: `classify_combo(*combo) == hand_class` for every combo in `enumerate_combos(hand_class)`. Per §11 #2.

4. **Tree browser performance (DOM cap).**
   - Per spec §3.4 + §8.5: visible tree nodes capped at **2000** by trimming deepest branches first.
   - Per-node cap: if expansion yields >500 children, render top 100 by reach probability + "...N more nodes hidden" placeholder.
   - Reach-prob slider (default 0; 0.01 hides ~95% of low-reach branches).
   - Lazy expansion: children computed only on first expansion, cached until spot/solve changes.
   - Tested: `test_tree_root_expansion_bounded` (§11 #6) and/or `test_tree_visible_nodes_under_cap` (§12 risk 3).

5. **No leak of opponent hole cards in tooltips.**
   - The combo inspector strip (§3.3) shows per-combo strategy for the **player-to-act** at the current tree node — not the opponent.
   - Tooltips on cells display: combo count, weighted fold/call/raise % FOR THE PLAYER-TO-ACT. Not the opponent's hole cards.
   - Per spec §3.3 + §13 open decision 9: "the matrix displays the player-to-act's strategy ... PR 10 hard-codes it; a future v2 could add an opponent-view toggle for nodelocking analysis."
   - **Flag if any tooltip/inspector exposes the opponent's specific hole cards or strategy** (would be an information leak for legitimate solver use cases like vs-opponent analysis).

6. **NiceGUI dependency declared as optional extra.**
   - Per spec §5 + §1 non-goals: `pyproject.toml` adds:
     ```toml
     [project.optional-dependencies]
     ui = ["nicegui>=2.0,<3.0"]
     ```
   - **NOT added to base `dependencies`** (per §4 "Why split into `ui/` package outside `poker_solver/`": NiceGUI is heavyweight; engine must load with zero UI overhead).
   - The pytest marker `ui` is declared in `[tool.pytest.ini_options]` so tests can skip when nicegui isn't installed.

7. **CLI `ui` subcommand wired correctly.**
   - Per spec §5 + §10.C: `poker-solver ui --port 8080 --host 127.0.0.1 --dark-mode auto`.
   - Lazy-imports `ui.app` (only at command invocation time) so the rest of the CLI works without NiceGUI installed.
   - If NiceGUI not installed → catch `ImportError` (NOT `ModuleNotFoundError` per NiceGUI llms.md style), print: "UI support not installed. Install with `pip install poker-solver[ui]`." Return exit code 2.

8. **UI is browser-served only (NOT a native desktop wrapper).**
   - Per spec §1 non-goals: "No native desktop wrapper. Packaging into `.dmg` with codesign+notarize is **PR 11**." NiceGUI's `native=True` mode (pywebview) is explicitly **not** used in PR 10.
   - Server binds to `127.0.0.1` by default (no `0.0.0.0`, no auth, no TLS).
   - Flag if `native=True` is used or if pywebview is added.

9. **`RangeWithFreqs` wraps `poker_solver.Range` (does NOT modify it).**
   - Per spec §12 risk 6: PR 10 needs per-combo float frequencies, but `poker_solver.Range` (PR 1) is membership-only.
   - **`ui/state.py::RangeWithFreqs` wraps `Range`** and adds a `dict[Combo, float]` frequency layer.
   - **Does NOT modify `poker_solver/range.py`** — verify via `git diff integration -- poker_solver/range.py` (should be empty).
   - This is the right separation (UI feature, not engine feature).

10. **No new tests in `poker_solver/` test surface.**
    - Per spec §1 non-goals: "No new solver tests. PR 10's tests cover *the UI*."
    - `tests/test_ui_smoke.py` is the ONLY new test file. Engine tests are untouched.
    - All PR 1-9 tests still pass unchanged.

11. **Color blend formula (Pio convention).**
    - Per spec §3.3 + §7.3: red=fold (220, 40, 40), yellow=call/check (220, 200, 40), green=raise/bet (40, 180, 60). RGB blend weighted by `freq_fold`, `freq_call`, `freq_raise`.
    - Distinct from the range-input color palette (white-to-blue gradient) so users can't confuse "what's in my range" with "what does the solver want this combo to do."
    - Numeric frequencies shown on hover (always) — color alone is perceptually misleading at extreme mixings.

12. **State persistence safety.**
    - Per spec §9.2: `~/.poker_solver_ui/state.json` is loaded on startup, saved on significant changes.
    - **Atomic write pattern**: write to `state.json.tmp`, `fsync`, then `rename` to `state.json`. Avoids corruption on crash mid-write.
    - **Load failure handling**: corrupt/version-mismatched JSON → log warning, back up to `state.json.bak`, start from defaults. Don't crash.
    - Debounced save (coalesce writes within 500ms window via `ui.timer(0.5, ...)`).

13. **Library viewer is a STUB (PR 11 wiring point).**
    - Per spec §3.5: `ui/views/library_browser.py` contains a header label "Solve library (PR 11)", placeholder text, disabled "Load from disk" button, three faked rows.
    - Clicking faked rows → toast "PR 11 — load from disk is not yet wired".
    - The dialog opens from the header button.
    - Tested: `test_library_dialog_opens` (§4 smoke test 8).

14. **Smoke test count.**
    - Per spec §4 / §10.C: 8 smoke tests in `tests/test_ui_smoke.py`. Each marked `@pytest.mark.ui` so they skip cleanly when nicegui isn't installed.
    - Tests use NiceGUI's `User` fixture (async, in-process, no real browser).
    - List from spec §10.C: page renders, board picker accepts 3 cards, range input via string, solve button starts worker, stop button halts within 1 iter, matrix renders 169 cells, combo-to-cell mapping no off-by-one, library dialog opens.

15. **`ui/` package is OUTSIDE `poker_solver/`.**
    - Per spec §4 "Why split": `ui/` is a sibling of `poker_solver/` and `crates/`. PLAN.md prefigured this.
    - Verify: `ls /Users/ashen/Desktop/poker_solver/ui/` exists as a sibling directory, not under `poker_solver/`.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report.md` with this exact structure:

```markdown
# PR 10 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-10a-ui-mock-first
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_ui_smoke.py — pass/fail (note skip count if nicegui not installed); full suite delta]

## Must-fix

[UI blocks on solver (no worker thread, or worker calls UI directly); stop button doesn't halt within 1 iter; off-by-one in matrix combo → cell mapping; opponent hole-card leak in tooltips; nicegui in base dependencies (forces install on engine-only users); `ui/` placed inside `poker_solver/` (wrong location); modifies `poker_solver/range.py` (should wrap, not modify); library viewer isn't a stub (premature PR 11 work). Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, awkward APIs, missing assertions, test holes (e.g., missing tree-cap test), state persistence not atomic. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-15 matching the 15 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: NiceGUI is MIT (third-party dep declared as optional extra); no other new deps; no code copied from competitor UI projects (Pio, GTOW); colour convention is widely-used poker-industry standard (not copyrightable expression). Cite specific files.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** UI blocks on solver (event loop freeze), stop button doesn't halt, matrix off-by-one (corrupts strategy display), opponent info leak, NiceGUI in base dependencies, `ui/` in wrong location, `poker_solver/range.py` modified, library viewer isn't a stub. Blocks PR.
- **should-fix:** missing tree-cap test, state.json save not atomic, awkward APIs, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently corrupts strategy display (off-by-one) or leaks opponent information → must-fix. Performance / UX issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr10_prep/audit_report.md`.
- If `nicegui` isn't installed in your audit environment, that's fine — the audit covers code structure + tests + dependency declaration, not actually running the UI. Tests should skip cleanly.

Begin by reading the spec, then the diff, then the new files. Then write the report.
