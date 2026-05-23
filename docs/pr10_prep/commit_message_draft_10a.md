PR 10a: NiceGUI scaffold + mock solver layer (v0.6.0 MINOR on PR 9)

Ships the full NiceGUI browser UI scaffold exercising every feature
of the eventual v1 product, backed by a MOCK solver module rather than
the real `solve_hunl_postflop`. The UI is the EXACT same artifact PR
10b will ship — only the contents of `ui/mock_solver.py` change
between PR 10a and PR 10b. Three-agent fan-out (A: app shell +
state + spot input + run panel; B: range matrix + tree browser;
C: mock_solver + library stub + 20 smoke tests + CLI + pyproject)
plus a post-implementation audit pass. The mock returns realistic
`HUNLSolveResult` instances byte-locked to PR 5's output shape (and
PR 9's `solve_hunl_preflop` extension on the preflop side), so PR
10b can do a one-line import swap in `ui/state.py`.

Bumps __version__ to 0.6.0 per semver (MINOR release — introduces
the `ui/` package as a new user-visible entry point alongside the
engine). MINOR bump (not PATCH) because: (a) the `ui/` sibling
package + `poker-solver ui` CLI subcommand together constitute a new
public surface area, even though no new public functions are added
to `poker_solver/` itself; (b) NiceGUI is optional via the new
`[ui]` extra — `pip install poker-solver` still works without it;
(c) zero behavior change to PRs 1-9 internals. This commit bundles
the v0.6.0 release artifacts together with the implementation so the
merge tip is releasable as-is:
- poker_solver/__init__.py: __version__ bumped to "0.6.0".
- pyproject.toml [project] version bumped to "0.6.0"; new
  `[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`.
- CHANGELOG.md: new [0.6.0] - 2026-05-22 section above prior entry,
  populated with the PR 10a entry from [Unreleased] (Mock-mode UI
  scaffold; 12 fixture spots; 20 smoke tests).
- README.md: version bumped to 0.6.0; new UI section with "(mock)"
  tagline + the `poker-solver ui` invocation + the yellow Mock-mode
  banner caveat ("downgrades to subtle `(mock)` chip in PR 10b").

Final line count: ~6,424 LOC total = ~5,535 LOC ui/ package
(app.py, state.py, mock_solver.py, views/*) + 821 LOC
tests/test_ui_smoke.py + ~68 LOC of edits to existing files
(poker_solver/__init__.py, poker_solver/cli.py, pyproject.toml,
README.md, CHANGELOG.md).

Scope (spec §0.1, §1, §3, §4.1-§4.6, §7, §10):
- Two-pane layout (Q1 LOCKED, resolves anti-pattern §3.1): matrix
  center + ONE collapsible right sidebar stacking three
  `ui.expansion` panels (spot input / run panel / tree browser,
  top-to-bottom; spot input open by default; others collapsed).
  The original PR 10 spec §3 four-pane layout is REPLACED based on
  the cross-document anti-pattern flag in `competitor_ui_deep_dive.md`
  + `ui_design_principles.md` §3.1 + Shark README's explicit
  clutter-reduction commitment.
- Seven UX Q-locks per §0.1 (citations to `competitor_ui_deep_dive.md`,
  `ui_design_principles.md`, `ui_mockups_and_debates.md`):
  Q1 two-pane; Q2 hand-class labels visible in cells (numbers on
  hover); Q3 default 1000 iterations (target-exploitability opt-in);
  Q4 4-of-6 bet sizes checked (33/75/100/all-in); Q5 combo inspector
  BELOW matrix (full-width horizontal strip); Q6 reach filter
  default 0.01; Q7 yellow "Mock mode" banner top, dismissible.
- Worker threading per spec §6.1 + §11 #1: solver runs in
  `threading.Thread` (NOT `asyncio.to_thread` — interruptible + GIL
  release in NumPy). UI loop never directly called from worker code;
  worker writes to `state.runner` dataclass; UI timer polls every
  500ms (`ui.timer(0.5, update_ui)`). Stop-button cancellation flag
  (`_stop_event`) checked once per mock-iter boundary; max delay =
  one mock-iter's wall-clock.
- Mock solver public surface byte-locked to PR 5's `solve_hunl_postflop`
  (and PR 9's `solve_hunl_preflop`): first 8 parameters of `mock_solve`
  are `(config, iterations, *, log_every, memory_budget_gb,
  target_exploitability, seed, dcfr_kwargs, on_progress)` — identical
  signature. Returns `HUNLSolveResult` with `MemoryReport` + per-
  iteration progress callbacks. Trailing `mock_*` knobs (mock_latency_ms,
  mock_failure_mode) have defaults and are NOT part of the real surface.
- Cancellation contract: module-level `_CANCEL_FLAG` (`threading.Event`)
  set by `SolveRunner.stop()` and checked by `mock_solve()` once per
  snapshot. SAME flag as the real solver in PR 10b — final-form in
  PR 10a; PR 10b uses it unchanged.
- 12 hand-crafted fixture spots passing the poker-player eye test:
  `river_tiny_subgame`, `flop_k72r_100bb`, `flop_t87s_100bb`,
  `flop_monotone_hhh`, `flop_paired_q9q`, `turn_kqj9_4_flush`,
  `turn_t872_brick`, `river_axxs_polar`, `preflop_btn_vs_bb`,
  `river_blocker_heavy`, `shortstack_25bb`, `deepstack_200bb`. MDF-
  obeying river bluff frequencies, polarization on rivers + linear
  on flops, correct blocker effects.
- 6 mock failure modes per spec §7.2: `'oom'` (raises MemoryError with
  partial_report after ~10% latency, surfaces §6.5 remediation),
  `'not_implemented'` (raises NotImplementedError), `'cancelled'`
  (returns HUNLSolveResult with iterations < requested),
  `'long_latency'` (sleeps 10 min with progress callbacks),
  `'rapid_iteration'` (latency 100 ms; tests chart-flooding guard),
  unset (normal run).
- State persistence at `~/.poker_solver_ui/state.json` with atomic
  write (tmp + fsync + rename), corrupt-load fallback (`.bak`
  backup, start from defaults), 0.5s debounce on the save path.
  Onboarding flag (`state.json::ui_prefs.onboarding_completed`) gates
  the 3-step modal independent of file presence.
- `RangeWithFreqs` in `ui/state.py` WRAPS `poker_solver.Range` (does
  NOT modify it). Adds the per-combo `dict[Combo, float]` frequency
  layer needed for the input matrix; engine's `Range` stays
  membership-only per PR 1.
- All 8 anti-patterns actively avoided (no modal for routine settings,
  no acronym without tooltip, no destructive confirmation on undoable
  actions, no Windows-95 layouts beyond the 2-pane, no >10-item
  dropdowns, no <24px clickable areas, no hiding required inputs,
  no dense-numbers-without-color tables).

New files (ui/ sibling package — OUTSIDE poker_solver/):
- ui/__init__.py: empty package init.
- ui/app.py (~150 LOC): NiceGUI entrypoint + header + 2-pane layout
  + yellow Mock-mode banner (dismissible) + theme toggle (Auto
  default per `ui_design_principles.md` §5) + hamburger menu.
- ui/state.py (~400 LOC): shared state + `SolveRunner` + `RangeWithFreqs`
  + state.json atomic load/save + onboarding flag + cancellation
  Event. Imports `mock_solve as _solve_postflop_impl` — the
  ONE single-named symbol PR 10b swaps to the real solver.
- ui/views/spot_input.py (~200 LOC): board picker (4×13 suit-by-rank
  grid + chip strip), range input (player tabs P0/P1, matrix mode
  default with live string preview, combo counter), stacks (push/fold
  warning toast at ≤15 BB per edge §6.4), position locked, blinds +
  ante collapsed expansion, preset dropdown.
- ui/views/run_panel.py (~200 LOC): bet-size checkboxes (Q4 LOCKED
  4-of-6 default + custom-size text field), raise caps, iteration
  count input (Q3 LOCKED default 1000 + target-exploitability opt-in),
  backend selector, three distinct Solve/Pause/Stop buttons color-
  coded green/yellow/red, status word color-coded per state
  (running/paused/done/stopped/error), `ui.echart` log-scale
  exploitability chart with linear toggle (chart updates every 500ms
  per design principle 8).
- ui/views/range_matrix.py (~400 LOC): 13×13 matrix with two on-cell
  signals (Pio additive RGB color blend + `R 78%`/`C 50%`/`F xx%`/
  `MIX`/`BLK` tag), hand-class shorthand in upper-left (Q2 LOCKED),
  hover-tooltip with cell-aggregate frequencies + combo count + EV,
  click-strip combo inspector BELOW matrix (Q5 LOCKED) with horizontal
  stacked bar + per-combo EV + reach + infoset-key copy-icon,
  slashed-diagonal blocker overlay (`╳╳╳`), input-matrix palette
  white→saturated blue (DISJOINT from RYG strategy display palette
  per principle 4).
- ui/views/tree_browser.py (~250 LOC): file-tree indentation,
  expand/collapse chevrons (▾/▸), inline per-node action stats
  ("fold 8% call 24% raise 68%"), selected-node highlight, reach
  filter slider above (Q6 LOCKED default 0.01), lazy expansion,
  performance cap (100 children visible per node + 2000 total
  nodes). Click tree node → re-render matrix conditioned on history.
- ui/views/library_browser.py (~80 LOC): STUB (PR 11 wiring point) —
  header label "Solve library (PR 11)", placeholder text, disabled
  "Load from disk" button, three faked rows, toast on row click
  ("PR 11 — load from disk is not yet wired").
- ui/views/onboarding.py (~120 LOC): 3-step modal triggered when
  `state.json` absent OR `ui_prefs.onboarding_completed=False`. Each
  step is one action; final step teaches the R/Y/G color legend
  before closing.
- ui/mock_solver.py (~400 LOC): `mock_solve` (byte-locked first-8-
  params surface), `list_fixture_presets`, `load_fixture`, 6 failure
  modes, `_CANCEL_FLAG`, `MemoryReport` fabrication populating
  `total_gb` / `per_street` / `river_ratio` /
  `rss_calibration_error` / `wallclock_per_iter_sec`.
- ui/mock_solver_fixtures.py (optional split if `mock_solver.py`
  exceeds 400 LOC): the 12 fixture spots as constant dicts.

New tests:
- tests/test_ui_smoke.py (~400 LOC, 20 tests, `@pytest.mark.ui` +
  module-level `pytest.importorskip('nicegui')`):
  §10.1 (8 UI smoke): page renders, board picker accepts 3 cards,
  range input via string, solve button starts worker, stop button
  halts within 1 iteration, matrix renders 169 cells, combo→cell
  mapping no off-by-one (CRITICAL CORRECTNESS — property test that
  classify_combo(*combo) == hand_class for every combo in
  enumerate_combos(hand_class)), library dialog opens.
  §10.2 (5 mock-solver coverage — PR 10b deletes these): mock returns
  real HUNLSolveResult, mock streams progress callbacks, mock 'oom'
  raises MemoryError with partial report, mock 'cancelled' returns
  partial result, UI never imports mock-specific symbols outside
  ui/state.py.
  §10.3 (4 UX-grounded): matrix color blend matches Pio convention
  (RGB within ±2 per channel on fixture), blocker cells show slashed
  overlay, input-matrix palette disjoint from display palette (locks
  principle 4 + Test #16), chart default log scale.
  §10.4 (3 edge-case): OOM failure shows remediation notification,
  push/fold dispatch toast at 15 BB, long-solve ETA appears after
  30s.
- tests/data/mock_fixtures/*.json: 12 fixture JSON files (one per
  fixture spot), bundled into the package.

Modified:
- poker_solver/cli.py: new `ui` subcommand with `--port 8080
  --host 127.0.0.1 --dark-mode auto` flags. Lazy-imports `ui.app`
  only at command invocation time so the rest of the CLI works
  without NiceGUI installed. If NiceGUI missing → catch ImportError,
  print "UI support not installed. Install with `pip install
  poker-solver[ui]`." Return exit code 2.
- pyproject.toml: `[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`
  added; NOT added to base `dependencies` (NiceGUI is heavyweight;
  engine loads with zero UI overhead). `[tool.pytest.ini_options]`
  declares the `ui` marker so tests skip cleanly when nicegui is
  uninstalled.
- README.md: new UI section with two-pane screenshot, the
  `poker-solver ui` invocation, the yellow Mock-mode banner caveat,
  and the "(mock)" → "(real)" PR 10b downgrade note.

Spec amendments locked this round (3 items, per §0.1 synthesis):
- Q1-Q7 locked from three landed UX research docs
  (`competitor_ui_deep_dive.md`, `ui_design_principles.md`,
  `ui_mockups_and_debates.md`); all 7 Q-locks intact post-audit
  (no Q-lock regressed during implementation); coin-flip flag on
  Q3 (1000 vs 2000 iter) — if PR 10a manual testing shows under-
  converged matrices on common spots, bump to 2000 in PR 10b.
- Smoke test count expanded from 8 (original PR 10 §10.C) to 20:
  §10.1 (8 UI smoke from PR 10) + §10.2 (5 mock-coverage, deleted
  in PR 10b) + §10.3 (4 UX-grounded) + §10.4 (3 edge-case).
- Layout amendment locked: 4-pane → 2-pane (resolves anti-pattern
  §3.1 from `ui_design_principles.md`).

Post-implementation audit (3 must-fix patches applied, 7 should-fix
deferred to PR 10b):
- M1 (must-fix, applied): mock_solve signature aligned with PR 5's
  `solve_hunl_postflop` via Option A (in-place reshape) — first 8
  positional/keyword params byte-identical to the real surface so PR
  10b's one-line import swap stays mechanical.
- M2 (must-fix, applied): library-browser header now renders as a
  disabled `ui.button` ("Load from disk (PR 11)") rather than a bare
  label, matching the disabled-control convention used elsewhere and
  giving the row-click toast a consistent affordance to point at.
- M3 (must-fix, applied): board-picker selection state stored as
  string ID ("Ah", "Kd", ...) rather than card-object reference —
  fixes a state.json round-trip bug where reloaded boards lost
  identity equality with the matrix's combo dictionary keys.
- 7 should-fix items DEFERRED to PR 10b (documented in
  `docs/pr10_prep/audit_followups.md`): non-blocking polish (e.g.
  hover-tooltip animation jitter, theme-toggle ripple, range-string
  parser whitespace tolerance) that do not affect correctness, the
  Q-locks, or PR 10b's mock→real swap surface.

Notable contract decisions (defaults per spec §11):
- Browser-served only; NO native desktop wrapper. `.dmg` packaging is
  PR 11. NiceGUI's `native=True` mode (pywebview) explicitly NOT used.
- Server binds to `127.0.0.1` by default (no `0.0.0.0`, no auth,
  no TLS).
- `ui/` is a sibling of `poker_solver/` and `crates/` (NOT inside
  `poker_solver/`) so the engine has zero NiceGUI import cost.
- Mock fixture spots are hand-crafted (NOT solver-generated) and
  carry the yellow "Mock mode" banner as the auditability rail.

Out of scope (per spec §1 non-goals): real solver wiring (PR 10b's
one-line import swap), `.dmg` packaging (PR 11), library persistence
beyond the stub dialog (PR 11), mobile-responsive layout, additional
languages (English-only), new engine tests, modifying
`poker_solver/range.py` (`RangeWithFreqs` WRAPS — does not modify),
NN warm-start opacity, GTOW-style cloud library.

Verification:
- pytest tests/test_ui_smoke.py -v: 20 tests pass with nicegui
  installed; 20 skipped (not errored) without nicegui (gated by
  module-level `pytest.importorskip`).
- pytest -m "not slow and not very_slow" --tb=line: all pass /
  skip; no failures. PR 1-9 regression: all green unchanged.
- ruff check + ruff format + black --check + mypy --strict on
  ui/ + tests/test_ui_smoke.py + poker_solver/cli.py: clean.
- `pip install -e .` (without `[ui]`): engine works; CLI's `ui`
  subcommand exits with code 2 and remediation message.
- `pip install -e .[ui]`: `poker-solver ui` launches the page on
  http://127.0.0.1:8080; yellow Mock-mode banner visible at top;
  dismissible after first solve.
- Manual smoke: walk all 12 fixtures via the preset dropdown;
  no `—` or `[empty]` on populated cells; live exploitability chart
  log-scale decays; Stop button halts within one simulated iteration;
  cancel preserves partial strategy; OOM dark-red status + remediation
  notification surfaces; 15 BB stacks trigger push/fold warning toast.
- Import-discipline grep: `ui/` outside `ui/state.py` contains zero
  `mock_solver` references (`test_ui_never_imports_mock_specific_symbols`
  asserts this).
- `git diff integration -- poker_solver/range.py` returns EMPTY
  (engine pollution check; `RangeWithFreqs` wraps, never modifies).

License compliance: NiceGUI is MIT (third-party dep declared as
optional extra in `[project.optional-dependencies] ui`); no other
new deps; no code copied from competitor UI projects (Pio, GTOW,
Monker, DeepSolver — only architectural patterns); color convention
is widely-used poker-industry standard (R/Y/G triad, NOT copyrightable
expression). The `competitor_ui_deep_dive.md` synthesis cites
competitor sources verbatim for design pattern attribution without
code copy.

Branch: pr-10a-ui-mock-first (off integration tip post-PR-9). Awaits
PR 10b (mechanical mock→real swap) for end-to-end real-solver UI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
