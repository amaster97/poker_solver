# PR 10a pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the audit verdict clears. Every gate MUST
pass (or carry an explicit waiver with rationale) before `git commit`.

## Snapshot (real LOC + file counts)

- 12 UI Python files under `ui/`: ~5,465 LOC.
- `tests/test_ui_smoke.py`: 792 LOC.
- Edits: `README.md` +26, `poker_solver/cli.py` +40, `pyproject.toml` +2 — 68 LOC of edits.
- **Total: ~6,325 LOC across 13+ files** (12 UI modules + 1 new test file + 3 edited files; fixtures counted as one tree).

## Pre-known issues (flag before commit)

- **Mock signature drift** — `ui/mock_solver.py::mock_solve` parameter order/names have drifted from `solve_hunl_postflop`'s post-PR 9 surface; **MUST-FIX before PR 10b integration** (G16 silent-failure mode). Track as the first PR 10b patch.
- **License header gap** — new `ui/` Python files lack the project SPDX/license header preamble carried by `poker_solver/` modules; **SHOULD-FIX**, non-blocking for PR 10a commit but flag in audit report.

## Build + lint gates

- [ ] **G1 — pytest UI smoke clean with nicegui installed.** `pytest tests/test_ui_smoke.py -v --tb=line` returns 0; all 20 tests pass.
  - Expected count: §10.1 (8 UI smoke) + §10.2 (5 mock-coverage, PR 10b deletes) + §10.3 (4 UX-grounded) + §10.4 (3 edge-case) = 20.
  - All marked `@pytest.mark.ui` + module-level `pytest.importorskip('nicegui')`.
  - Critical correctness: `test_combo_to_cell_mapping_no_off_by_one` (smoke #7) — property test that `classify_combo(*combo) == hand_class` for every combo in `enumerate_combos(hand_class)`. Total combos: 13 pairs × 6 + 78 suited × 4 + 78 offsuit × 12 = 1326.

- [ ] **G2 — pytest UI smoke skips cleanly without nicegui.** Temporary `pip uninstall nicegui`; rerun `pytest tests/test_ui_smoke.py -v`; expect 20 skipped (NOT errored). Reinstall via `pip install -e .[ui]` after the check.
  - Verifies module-level `pytest.importorskip('nicegui')` correctly gates collection.

- [ ] **G3 — pytest fast tier clean.** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - PR 1-9 regression: all green unchanged.
  - Engine tests do NOT import NiceGUI — verifies the optional-dep isolation.

- [ ] **G4 — ruff + black clean.** `ruff check ui tests/test_ui_smoke.py poker_solver/cli.py` and `black --check ui tests/test_ui_smoke.py poker_solver/cli.py` return 0.
  - Format-only nits acceptable; logical lints are not.

- [ ] **G5 — mypy strict clean on new code.** `mypy --strict ui/ tests/test_ui_smoke.py poker_solver/cli.py` returns 0.
  - Per-directory check, not whole-tree.
  - Watch for: `SolveRunner` state field types (especially `expl_history: list[tuple[int, float]]`), `RangeWithFreqs` generic typing over `poker_solver.Range`, NiceGUI `User` fixture return type in tests.

## UI correctness gates (Q1-Q7 locks per spec §0.1)

- [ ] **G6 — Q1 LOCKED two-pane layout.** `ui/app.py::build_page()` renders matrix center + ONE collapsible right sidebar stacking three `ui.expansion` panels (spot input / run panel / tree browser, top-to-bottom; spot input open by default; others collapsed).
  - The 4-pane layout from the original PR 10 spec §3 is REPLACED.
  - `test_page_renders_without_exception` (smoke #1) confirms layout markers.

- [ ] **G7 — Q2 LOCKED hand-class labels in cells.** `ui/views/range_matrix.py` renders the hand-class shorthand ("AKs", "QQ", "72o") in upper-left of every cell; numeric frequencies revealed on hover only.
  - Anti-pattern guard: text labels are always present; numbers (frequency percentages) are hover-only per `ui_design_principles.md` §2.5 numbers-on-hover rule.

- [ ] **G8 — Q3 LOCKED default 1000 iterations.** `ui/views/run_panel.py` iteration count input defaults to 1000 (NOT 2000). Target-exploitability mode is the opt-in alternative toggle.
  - Coin-flip flag: if Q3 produces under-converged matrices on common spots during PR 10a manual testing, bump to 2000 in PR 10b. PR 10a ships with 1000.

- [ ] **G9 — Q4 LOCKED 4-of-6 bet sizes default.** `ui/views/run_panel.py` bet-size checkboxes default to 33% / 75% / 100% / all-in checked; 150% / 200% unchecked.
  - Custom-size text field still present (Pio bet-size DSL: comma-separated pot fractions).

- [ ] **G10 — Q5 LOCKED combo inspector BELOW matrix.** `ui/views/range_matrix.py` renders the combo inspector strip as a separate slot directly below the 13×13 grid (NOT to the right; the right sidebar is reserved for the Q1 expansion panels).
  - Inspector contents: horizontal stacked bar (`▰▰▰▰▰▰▰▰▱▱`), per-combo action probabilities, EV, reach, infoset-key copy-icon. BLOCKED row for cells removed by board.

- [ ] **G11 — Q6 LOCKED reach filter default 0.01.** `ui/views/tree_browser.py` reach-filter slider's initial value is `0.01` (NOT 0.0). Visible above the tree; tooltip explains threshold semantics.
  - Power users can drag to 0.0 in one motion.

- [ ] **G12 — Q7 LOCKED yellow "Mock mode" banner.** `ui/app.py` header renders a yellow banner at the top labelled "Mock mode" with a dismissible-after-first-solve close button (ElementFilter markers: `'mock-mode-banner'`, `'mock-mode-banner-dismiss'`).
  - Banner is the safety rail — without it, user thinks PR 10a produces real solver output. Must-fix candidate if absent or non-dismissible.
  - Downgrades to subtle `(mock)` chip in PR 10b once outputs are real.

## Threading + cancellation gates

- [ ] **G13 — Worker thread, NOT `asyncio.to_thread`.** `ui/app.py` (or `ui/state.py::SolveRunner.start`) spawns `threading.Thread`, NOT `asyncio.to_thread`. UI event loop is never directly called from worker context.
  - Anti-pattern grep: `grep -r "ui\." ui/mock_solver.py` returns ZERO `ui.notify(...)`, `progress_bar.set_value(...)`, etc. calls inside worker context. Worker writes only to `state.runner` dataclass.
  - UI updates via `ui.timer(0.5, update_ui)` polling every 500ms.

- [ ] **G14 — Stop-button halts within 1 mock-iter.** `_stop_event.is_set()` checked at every mock-iter boundary in `mock_solve()`. Test: `iterations=100_000`, click Solve, wait 0.5s, click Stop, wait 0.5s, assert `status in ('stopped', 'done')` AND `iteration < 50_000`.
  - `test_stop_button_halts_within_one_iteration` (smoke #5) locks this.

- [ ] **G15 — Cancellation contract is the SAME flag as PR 10b.** Module-level `_CANCEL_FLAG` (`threading.Event`) in `ui/state.py` set by `SolveRunner.stop()` and checked by `mock_solve()`. PR 10b uses this flag without modification.

## Mock interface contract gate (load-bearing for PR 10b swap)

- [ ] **G16 — Mock interface matches real solver shape byte-identically.** `ui/mock_solver.py::mock_solve` first 8 parameters are `(config: HUNLConfig, iterations: int, *, log_every: int | None, memory_budget_gb: float, target_exploitability: float | None, seed: int | None, dcfr_kwargs: dict | None, on_progress: Callable[[int, float, MemoryReport], None] | None)` — IDENTICAL to PR 5's `solve_hunl_postflop` post-PR 9 + PR 10b engine-side additions.
  - Return type: `HUNLSolveResult` (imported from `poker_solver.hunl_solver`).
  - `MemoryReport` populated with `total_gb`, `per_street`, `river_ratio`, `rss_calibration_error`, `wallclock_per_iter_sec` (every field the UI reads per spec §7.3).
  - Anti-pattern: NO field-name drift (`{"strategy": ..., "ev": ...}` instead of `{"final_strategy": ..., "exploitability": ...}`); NO missing fields. PR 10b's one-line import swap breaks silently on either.
  - Test: `python -c "from poker_solver.hunl_solver import HUNLSolveResult; from ui.mock_solver import mock_solve; assert isinstance(mock_solve(...), HUNLSolveResult)"`.

- [ ] **G17 — Trailing `mock_*` knobs default to safe values.** `mock_latency_ms: int = 30_000` and `mock_failure_mode: str | None = None`. NOT part of the real surface; defaults make production callers indistinguishable from PR 10b's real solver.

## Engine isolation gate

- [ ] **G18 — `RangeWithFreqs` WRAPS, does NOT modify `poker_solver/range.py`.** `ui/state.py::RangeWithFreqs` wraps `poker_solver.Range` and adds the per-combo `dict[Combo, float]` frequency layer.
  - `git diff integration -- poker_solver/range.py` returns EMPTY diff. Must-fix if non-empty (engine pollution).
  - Engine's `Range` stays membership-only per PR 1.

- [ ] **G19 — NiceGUI is optional, NOT in base dependencies.** `pyproject.toml` `[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`. Base `[project.dependencies]` unchanged.
  - `pip install poker-solver` (without `[ui]`) succeeds; engine works; CLI `ui` subcommand exits with code 2 and remediation message.
  - `[tool.pytest.ini_options]` declares `ui` marker so tests skip cleanly when nicegui is uninstalled.

- [ ] **G20 — `ui/` is OUTSIDE `poker_solver/`.** `ls /Users/ashen/Desktop/poker_solver/ui/` exists as a sibling directory to `poker_solver/` and `crates/`, NOT under `poker_solver/`.
  - Engine has zero NiceGUI import cost; the optional-dep isolation is structural, not just by convention.

## State persistence gates

- [ ] **G21 — state.json atomic write (tmp + fsync + rename).** `ui/state.py::save_state()` writes to `state.json.tmp`, `fsync()`, then `os.rename()` to `state.json`. POSIX rename is atomic.
  - Anti-pattern: direct `open(path, 'w').write(json.dumps(...))` corrupts on mid-write crash. Should-fix per `audit_preprep_10a.md` §1.2.

- [ ] **G22 — Corrupt-load fallback in place.** `ui/state.py::load_state()` catches malformed JSON, logs a warning, backs up to `state.json.bak`, and starts from defaults. Does NOT crash on launch.
  - Onboarding flag (`state.json::ui_prefs.onboarding_completed`) gates the modal independent of file presence.

- [ ] **G23 — Save debounce.** `ui.timer(0.5, ...)` debounce with coalesced writes; saving on every keystroke would thrash disk.

## Fixture quality gates

- [ ] **G24 — 12 fixture spots load + render meaningfully.** Preset dropdown surfaces all 12: `river_tiny_subgame`, `flop_k72r_100bb`, `flop_t87s_100bb`, `flop_monotone_hhh`, `flop_paired_q9q`, `turn_kqj9_4_flush`, `turn_t872_brick`, `river_axxs_polar`, `preflop_btn_vs_bb`, `river_blocker_heavy`, `shortstack_25bb`, `deepstack_200bb`. No `—` or `[empty]` on populated cells.
  - Manual walk via the UI (acceptance criterion #3 per spec §11).

- [ ] **G25 — Fixtures are mathematically plausible.** For bet-size B (fraction of pot), MDF_cap(B) = B/(1+B) of value combos. Pot-sized bet (B=1.0) → 50% MDF cap. Spot-check the 4 river fixtures (`river_tiny_subgame`, `river_axxs_polar`, `river_blocker_heavy`, and the river entries in `turn_*`) for MDF compliance.
  - Polarization on rivers (mix of strong value + bluff). Linear-leaning on flops.
  - Blocker overlay on `flop_k72r_100bb` for the `AhKh`-only class (test #15 locks this).

## Edge-case gates

- [ ] **G26 — Push/fold dispatch warning at 15 BB.** `test_pushfold_dispatch_at_15bb` (smoke #19): set stacks to 15 BB; assert yellow warning toast appears with "Switch to push/fold view" button.
  - Per spec edge case §6.4; matches PR 9 §6 canonical dispatch (chart wins at ≤15 BB regardless of `starting_street`).

- [ ] **G27 — OOM remediation notification.** `test_oom_failure_shows_remediation_notification` (smoke #18): `mock_failure_mode='oom'` surfaces the §6.5 notification with "Reduce bet sizes" quick-action button + system-protective framing ("Solve aborted to protect your system").

- [ ] **G28 — Long-solve ETA after 30s.** `test_long_solve_eta_appears_after_30s` (smoke #20): with `mock_latency_ms=60_000` and `mock_failure_mode='long_latency'`, ETA text appears in status readout after 30s.

## Browser-only gate

- [ ] **G29 — Browser-served, NOT native.** `ui/app.py::ui.run(...)` does NOT pass `native=True`. PyWebView is NOT a dependency. `.dmg` packaging is PR 11.
  - Server binds to `127.0.0.1` by default (no `0.0.0.0`, no auth, no TLS).

## Audit gate

- [ ] **G30 — PR 10a audit verdict.** `docs/pr10_prep/audit_report_10a.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → commit.
  - READY-WITH-PATCHES → apply patches in-place, re-run G1-G29 on the patched code, then commit.
  - NOT-READY → abort commit; orchestrator escalates to the user with the audit-report's must-fix list.
  - Audit focus areas (per `audit_prompt_final_10a.md` 15-area brief): UI threading correctness (HIGH-PROB); stop-button latency; matrix off-by-one (silent corruption); state.json atomicity; mock interface contract (HIGH-PROB); 12 fixtures MDF-plausible; Q1-Q7 design locks; NiceGUI as optional extra; CLI `ui` subcommand; browser-served only; `RangeWithFreqs` wraps not modifies; no engine test changes; library viewer stub; smoke test count (20); `ui/` location.

## Branch + integration gates

- [ ] **G31 — Branch synced.** `git fetch --all`; verify integration baseline (PR 9 tip) unchanged. `pr-10a-ui-mock-first` contains all Agent A/B/C diffs, no merge conflicts.

- [ ] **G32 — File scope contained.** `git diff integration..pr-10a-ui-mock-first --stat` shows ~14-16 files:
  - 10-11 new files in `ui/`: `__init__.py`, `app.py`, `state.py`, `mock_solver.py` (+ optional `mock_solver_fixtures.py`), `views/__init__.py`, `views/spot_input.py`, `views/run_panel.py`, `views/range_matrix.py`, `views/tree_browser.py`, `views/library_browser.py`, `views/onboarding.py`.
  - 1 new test file: `tests/test_ui_smoke.py`.
  - 12 fixture JSON files: `tests/data/mock_fixtures/*.json` (counted as one tree).
  - Modifications: `poker_solver/cli.py` (new `ui` subcommand), `pyproject.toml` (optional `[ui]` extra + pytest marker), `README.md` (UI section).
  - v0.7.1 bump + docs touch-ups: `poker_solver/__init__.py`, `pyproject.toml` version, `CHANGELOG.md`.
  - No edits to: `poker_solver/range.py` (engine pollution guard), `poker_solver/hunl.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`, `poker_solver/preflop_solver.py`, `dcfr.py`, any test file other than `test_ui_smoke.py`, any Rust file.

## Biggest gate

**G16 (mock interface contract)** + **G12 (Q7 yellow Mock banner)** + **G18 (engine pollution guard on Range)** are the three highest-impact must-fix bands.
- G16 silent failure mode: shape drift breaks PR 10b's one-line import swap at UI dispatch — the next PR misfires entirely.
- G12: without the banner the user thinks PR 10a's hand-crafted fixtures are real solver output (auditability rail).
- G18: any line of diff in `poker_solver/range.py` makes UI changes a Python-API surface change rather than a UI-only change.

Secondary biggest gate: **G13/G14 (threading correctness)** — `asyncio.to_thread` or worker → UI direct calls produce silent races + NiceGUI "element not bound to a client" errors.

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-10a-ui-mock-first` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check; verify ~14-16 file scope.
3. `git commit -F docs/pr10_prep/commit_message_draft_10a.md` (or paste via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-10a-ui-mock-first`.

## Non-commits in this round

- Do NOT auto-merge `pr-10a-ui-mock-first` into `integration`. Wait for PR 10b's mock→real swap to land as a coordinated pair.
- Do NOT close any GitHub PRs yet.
- Do NOT modify `poker_solver/range.py` (engine pollution guard).
- Do NOT add `nicegui` to base `[project.dependencies]` — optional-extra ONLY.
- Do NOT enable `native=True` in NiceGUI — browser-served only; `.dmg` is PR 11.
- Do NOT modify any test file other than `tests/test_ui_smoke.py` (spec §1 non-goals "no new solver tests").
- Do NOT touch any Rust file — PR 10a is browser UI scaffold, not engine code.
