# PR 10b pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the PR 10b audit verdict clears. Every gate
MUST pass (or carry an explicit waiver with rationale) before `git
commit`. PR 10b is a deletion-heavy delete-and-replace swap; gate
focus is **completeness of deletion** and **signature/contract lock**
with PR 9 / PR 5, NOT new-code correctness.

## Build + lint gates

- [ ] **G1 — pytest UI smoke clean.** `pytest tests/test_ui_smoke.py -v` returns 0.
  - 10 tests total: 8 retained from PR 10a (UNMODIFIED) + 2 new (`test_real_solve_completes_river_subgame`, `test_real_solve_progress_callback_fires`). 5 mock-specific tests deleted.
  - Skip rationale: real-solve tests carry no `@pytest.mark.slow` (use `default_tiny_subgame` which is <2 s on M-series).
  - If `nicegui` not installed, all 10 may skip; that's acceptable.

- [ ] **G2 — pytest fast tier clean (full regression).** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - All PR 1-10a tests pass / skip / xfail. NO failures, NO timeouts.
  - Critical: PR 5/6/7/8 callers of `solve_hunl_postflop` (which now has the new `on_progress` kwarg, defaulted to `None`) must remain unaffected.

- [ ] **G3 — ruff + black + mypy clean on PR 10b changes.** `ruff check ui poker_solver tests`, `black --check ui poker_solver tests`, and `mypy --strict ui/state.py ui/app.py poker_solver/hunl_solver.py` all return 0.
  - Per-file mypy check, not whole-tree.
  - Watch for: `Callable[[int, float, MemoryReport], None] | None` import path consistency (`from collections.abc import Callable`; `MemoryReport` from `poker_solver.profiler.memory`).

## Correctness gates (signature + dispatch lock)

- [ ] **G4 — `on_progress` signature BYTE-identical across PR 9 + PR 5.** `inspect.signature(solve_hunl_preflop) == inspect.signature(solve_hunl_postflop)` for the `on_progress` parameter. Default value is `None`, NOT `lambda *a: None`. [HIGH-PROB must-fix per `audit_preprep_10b.md` §1.2.]
  - Failure mode (a) — default drift: PR 9 shipped `= None` (per PR 9 audit); PR 10b's hunl_solver.py kwarg add MUST match.
  - Failure mode (b) — signature drift: `Callable[[int, float], None]` (missing `MemoryReport`) or extra kwarg → must-fix.
  - Failure mode (c) — worker-thread invariant broken: callback invoked on main UI thread → blocks event loop during NumPy work → must-fix.
  - Test: `test_on_progress_signature_matches_across_solvers` asserts BYTE-identical parameter spec.

- [ ] **G5 — Dispatch wrapper routes by starting_street.** `ui/state.py::_solve_postflop_impl` branches on `config.starting_street == Street.PREFLOP` → `solve_hunl_preflop`; else → `solve_hunl_postflop`.
  - Push/fold short-circuit at ≤15 BB lives inside `poker_solver.solver.solve` (per PR 9 §6 canonical dispatch); reached transparently via either branch.
  - `SolveRunner.start` body UNCHANGED — same args; only `_solve_postflop_impl` symbol resolution changes.

## Correctness gates (UI structure FROZEN — PR 10a regression)

- [ ] **G6 — `git diff integration -- ui/views/` is EMPTY.** [HIGH-PROB must-fix per `audit_preprep_10b.md` §1.1] Marker contracts `matrix-cell`, `preset-*`, `combo-inspector`, `bet-size-*`, `library-row-stub`, etc. intact across all view files.
  - Sole permitted exception: the file that hosts the Q7 banner (e.g., `ui/views/banner.py` or `ui/app.py`'s header), which downgrades banner → chip and renames marker `mock-mode-banner` → `mock-mode-chip`. ONE marker swap; ALL OTHER markers untouched.
  - Failure mode (a) — agent "cleans up" a view file: marker contract silently broken; smoke tests pass (markers are structural) but PR 11 library loading breaks downstream. Must-fix.
  - Failure mode (b) — Q1-Q6 layout drift (two-pane → single-pane, combo inspector relocated, bet-size defaults bumped). Must-fix.

- [ ] **G7 — Retained 8 smoke tests UNMODIFIED.** `git diff integration -- tests/test_ui_smoke.py | grep '^[-+]'` shows ONLY 5 mock-deletes + 2 real-solve-adds (and any test-block rearrangement). NO assertion-string edits "for clarity" on the 8 retained tests (page renders, board picker, range input, solve button, stop button, matrix renders 169 cells, combo-to-cell mapping, library dialog opens).
  - Anti-pattern check: any diff inside a retained `test_*` body → must-fix.

- [ ] **G8 — Q7 downgrade compliant; chip marker `mock-mode-chip`.** Chip rendering logic: `if not state.has_completed_real_solve: render chip else: hide`. Marker name VERBATIM `mock-mode-chip` (breaks PR 11 introspection otherwise → must-fix).
  - Should-fix watch: chip persists post-real-solve (state not threaded); chip still bright yellow / banner-sized (downgrade in spirit only).

## Correctness gates (deletion completeness)

- [ ] **G9 — `ui/mock_solver.py` deleted (not renamed, not archived).** `git ls-files | grep -i mock_solver` returns EMPTY. `git status --porcelain` shows `D ui/mock_solver.py` (and conditionally `D ui/mock_solver_fixtures.py` if PR 10a split it out).
  - No archival copy under `tests/fixtures/` or anywhere else. Mock module is gone.

- [ ] **G10 — No orphan imports or callsites.** `grep -ri 'from ui.mock_solver\|import mock_solver\|mock_solve\|mock_progress_callback' poker_solver/ ui/ tests/` returns EMPTY.
  - Failure mode (a) — orphan import: `from ui.mock_solver import ...` survives import-resolution dead-code path; CI passes; runtime `ImportError` on first UI launch. Must-fix.
  - Failure mode (c) — `mock_progress_callback` symbol leaked: defined elsewhere and re-imported. Must-fix.
  - Should-fix watch: stale comments / docstrings referencing `mock_solver`.

## Correctness gates (library viewer stub preserved)

- [ ] **G11 — `ui/views/library_browser.py` UNTOUCHED.** `git diff integration -- ui/views/library_browser.py` returns EMPTY. `test_library_dialog_opens` (one of PR 10a's retained 8 smoke tests) unmodified.
  - Failure mode (a) — agent "helpfully" wires a real row-click handler (premature PR 11 work; PR 11 spec diverges). Must-fix.
  - Failure mode (b) — stub disabled-button flipped to enabled. Must-fix.

## Dependency + license gates

- [ ] **G12 — No new third-party dependencies.** `git diff integration -- pyproject.toml` shows ONLY the version bump (0.7.0 → 0.7.1). `[project.dependencies]` and `[project.optional-dependencies] ui` UNCHANGED.
  - PR 10b is a delete-and-replace swap. No new packages. No new Rust crates.

- [ ] **G13 — `check_pr.sh` license audit clean.** PLAN.md §4 step 6 — confirms no new AGPL/GPL deps. PR 10b is purely a deletion + import swap; no code copied. The one new engine-side kwarg (`on_progress` on `solve_hunl_postflop`) is original glue.

## Branch + integration gates

- [ ] **G14 — All branches synced.** `git fetch --all` then verify:
  - `main`: unchanged.
  - `integration`: PR 9 + PR 10a tips both landed and SHA stable (confirm both before PR 10b commit; PR 10b sits ON TOP of both).
  - `pr-10b-ui-real-solver`: contains all single-agent diffs; no merge conflicts against integration.
  - If integration shifted (e.g., a PR 9 or PR 10a hotfix landed), PR 10b must rebase before commit.

- [ ] **G15 — No accidental edits to unrelated files.** `git diff integration..pr-10b-ui-real-solver --stat` shows ~8-12 files staged, scoped to:
  - 2 file deletions: `ui/mock_solver.py` (+ optional `ui/mock_solver_fixtures.py`).
  - Modified: `ui/state.py` (dispatch wrapper), `ui/app.py` (imports + preset dropdown), `ui/views/banner.py` or equivalent (Q7 downgrade), `poker_solver/hunl_solver.py` (on_progress kwarg only), `tests/test_ui_smoke.py` (5 dels + 2 adds; 8 retained UNMODIFIED), `README.md` ("UI (mock)" → "UI"), `pyproject.toml` (version), `poker_solver/__init__.py` (version), `CHANGELOG.md` (new [0.7.1] section).
  - NO edits to: any other `ui/views/*.py` file (FROZEN); `dcfr.py`, `evaluator.py`, `abstraction/`, PR 4 abstraction artifacts; PR 5's `hunl_solver.py` orchestration BEYOND the single kwarg add; PR 9's `preflop_solver.py`, `blueprint.py`, `subgame_refiner.py`; any Rust file; PR 3.5 `pushfold.py`; Kuhn/Leduc test files.

## Audit gate

- [ ] **G16 — PR 10b audit verdict.** `docs/pr10_prep/audit_report_10b.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → commit.
  - READY-WITH-PATCHES → apply patches, re-run G1-G15 on patched code, commit.
  - NOT-READY → abort; orchestrator escalates with audit's must-fix list.
  - Audit focus areas (per `audit_prompt_final_10b.md` 7-area brief): UI structure regression vs PR 10a (HIGH-PROB); `on_progress` signature compat (HIGH-PROB); mock module deletion completeness; Q7 chip downgrade; library viewer stub stays a stub; no new third-party deps; all PR 1-10a tests still pass.

## Biggest gate

**G6 (UI views FROZEN diff empty)** + **G4 (`on_progress` signature BYTE-identical)** + **G10 (no orphan mock imports)** are the three highest-risk HIGH-PROB must-fix bands. G6 is the silent-corruption mode where Agent "cleans up" markers and PR 11 breaks downstream; G4 is the silent-corruption mode where dispatch wrapper trips at first preflop solve due to default drift; G10 is the runtime-ImportError trap where CI passes but `poker-solver ui` crashes on first launch.

Secondary biggest gate: **G7 (retained smoke tests unmodified)** — silent assertion-string edits "for clarity" mask future regressions.

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-10b-ui-real-solver` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check; verify ~8-12 file scope.
3. `git commit -F docs/pr10_prep/commit_message_draft_10b.md` (or paste via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-10b-ui-real-solver`.

## Non-commits in this round

- Do NOT auto-merge `pr-10b-ui-real-solver` into `integration`. Wait for orchestrator coordination (PR 10b lands as a pair with PR 9 if not already merged; otherwise solo).
- Do NOT close any GitHub PRs yet.
- Do NOT touch any `ui/views/*.py` file beyond the Q7 banner host (FROZEN at PR 10a).
- Do NOT modify PR 5's `hunl_solver.py` beyond the single `on_progress` kwarg + 3-line threading block.
- Do NOT modify PR 9's `preflop_solver.py` / `blueprint.py` / `subgame_refiner.py` (consumed read-only).
- Do NOT wire `ui/views/library_browser.py` (PR 11 work).
- Do NOT add any new third-party dependency to `pyproject.toml`.
- Do NOT archive `ui/mock_solver.py` anywhere — it is fully deleted.
