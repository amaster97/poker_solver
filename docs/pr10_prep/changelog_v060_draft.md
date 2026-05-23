## [0.6.0] - 2026-05-22

PR 10a: NiceGUI browser UI scaffold backed by a mock solver layer. Ships
the full v1 user-facing UI artifact — two-pane layout, 13×13 range matrix
with Pio-convention color blend, tree browser, run panel, combo inspector,
12 hand-crafted fixture spots — wired to `ui/mock_solver.py` rather than
the real `solve_hunl_postflop`. PR 10b is a one-line import swap in
`ui/state.py` (mock → real). MINOR bump per SemVer: introduces a new
public entry point (`poker-solver ui`) and a new top-level `ui/` package
sibling to `poker_solver/`, but no changes to the `poker_solver` Python
API surface and zero behavior change to PRs 1-9 (NiceGUI gated under the
new optional `[ui]` extra). Three-agent fan-out (A: app shell + state +
spot input + run panel; B: range matrix + tree browser; C: mock_solver +
library stub + 20 smoke tests + CLI + pyproject) plus a post-implementation
audit pass per `docs/pr10_prep/launch_kickoff_10a.md`.

### Added

- **`ui/` package** (sibling of `poker_solver/` and `crates/`; NOT
  inside `poker_solver/` so the engine has zero NiceGUI import cost):
  - `ui/app.py` — NiceGUI entrypoint, two-pane layout (matrix center +
    one collapsible right sidebar with three `ui.expansion` panels:
    spot input / run panel / tree browser), yellow dismissible
    "Mock mode" banner, Auto-default theme toggle, hamburger menu.
  - `ui/state.py` — shared state, `SolveRunner` (threading-based
    worker per spec §6.1 + §11 #1; `threading.Event` cancellation flag
    checked once per mock-iter), `RangeWithFreqs` (WRAPS
    `poker_solver.Range`, never modifies), atomic `state.json`
    persistence at `~/.poker_solver_ui/state.json` (tmp + fsync + rename;
    `.bak` fallback on corrupt-load; 0.5s debounce), onboarding flag.
  - `ui/views/spot_input.py` — board picker (4×13 suit-by-rank grid +
    chip strip), range input with matrix-mode + live string preview +
    combo counter, stacks with push/fold warning toast at ≤15 BB,
    blinds + ante collapsed expansion, preset dropdown.
  - `ui/views/run_panel.py` — bet-size checkboxes (Q4 LOCKED 4-of-6
    default: 33/75/100/all-in + custom-size text field), raise caps,
    iterations (Q3 LOCKED default 1000 + target-exploitability opt-in),
    backend selector, color-coded Solve/Pause/Stop buttons,
    `ui.echart` log-scale exploitability chart with linear toggle
    (500ms update cadence).
  - `ui/views/range_matrix.py` — 13×13 matrix with Pio additive RGB
    color blend + `R xx%`/`C xx%`/`F xx%`/`MIX`/`BLK` on-cell tag,
    hand-class shorthand upper-left (Q2 LOCKED), hover tooltip,
    click-strip combo inspector BELOW matrix (Q5 LOCKED) with
    horizontal stacked bar + per-combo EV + reach + infoset-key copy
    icon, slashed-diagonal blocker overlay, input-matrix palette
    (white→saturated blue) DISJOINT from RYG strategy palette.
  - `ui/views/tree_browser.py` — chevron expand/collapse, inline
    per-node action stats, reach filter slider above (Q6 LOCKED
    default 0.01), lazy expansion, performance cap (100 children per
    node + 2000 total nodes), node-click re-renders matrix.
  - `ui/views/library_browser.py` — PR 11 stub (disabled button,
    placeholder rows, toast on click).
  - `ui/views/onboarding.py` — 3-step modal gated on
    `ui_prefs.onboarding_completed`; teaches R/Y/G legend before close.
- **`ui/mock_solver.py`** — `mock_solve` first-8-params byte-locked
  to PR 5's `solve_hunl_postflop` (and PR 9's `solve_hunl_preflop`):
  `(config, iterations, *, log_every, memory_budget_gb,
  target_exploitability, seed, dcfr_kwargs, on_progress)`. Returns
  real `HUNLSolveResult` with fabricated `MemoryReport`
  (`total_gb` / `per_street` / `river_ratio` /
  `rss_calibration_error` / `wallclock_per_iter_sec`). Module-level
  `_CANCEL_FLAG` (`threading.Event`) is the SAME flag PR 10b's real
  solver uses unchanged.
- **6 mock failure modes** (`'oom'`, `'not_implemented'`,
  `'cancelled'`, `'long_latency'`, `'rapid_iteration'`, unset) per
  spec §7.2; OOM raises `MemoryError` with partial report surfacing
  §6.5 remediation.
- **12 hand-crafted fixture spots** passing the poker-player eye test
  (`tests/data/mock_fixtures/*.json`): `river_tiny_subgame`,
  `flop_k72r_100bb`, `flop_t87s_100bb`, `flop_monotone_hhh`,
  `flop_paired_q9q`, `turn_kqj9_4_flush`, `turn_t872_brick`,
  `river_axxs_polar`, `preflop_btn_vs_bb`, `river_blocker_heavy`,
  `shortstack_25bb`, `deepstack_200bb`. MDF-obeying river bluff
  frequencies, river polarization, flop linear ranges, correct
  blocker effects.
- **CLI `ui` subcommand** (`poker_solver/cli.py`): `poker-solver ui
  --port 8080 --host 127.0.0.1 --dark-mode auto`. Lazy-imports
  `ui.app` only at invocation; clean `ImportError` path with
  remediation message ("Install with `pip install poker-solver[ui]`")
  and exit code 2 when NiceGUI is missing.
- **20 smoke tests** (`tests/test_ui_smoke.py`, `@pytest.mark.ui` +
  module-level `pytest.importorskip('nicegui')`):
  - 8 UI smoke (§10.1): page renders, board picker, range input,
    solve start/stop, 169-cell matrix render, combo→cell mapping
    property test, library dialog.
  - 5 mock-solver coverage (§10.2, PR 10b deletes): real
    `HUNLSolveResult` shape, progress callbacks, OOM partial report,
    cancellation partial result, import-discipline assertion.
  - 4 UX-grounded (§10.3): Pio color blend RGB ±2 channel tolerance,
    blocker overlay, palette disjointness lock, chart default log.
  - 3 edge-case (§10.4): OOM remediation, push/fold toast at 15 BB,
    long-solve ETA after 30s.
- **`ui` pytest marker** registered in `pyproject.toml` (clean-skip
  on hosts without NiceGUI).
- **Optional extra** `[project.optional-dependencies] ui =
  ["nicegui>=2.0,<3.0"]`. Engine `pip install poker-solver` works
  without `[ui]`.

### Changed

- **`poker_solver/cli.py`** — additive `ui` subcommand. Existing
  `equity`, `solve`, `precompute-abstraction` subcommands unchanged.
- **`README.md`** — new UI section with two-pane screenshot,
  `poker-solver ui` invocation, yellow "Mock mode" banner caveat,
  and the "(mock)" → "(real)" PR 10b downgrade note.

### Spec amendments

- **Layout: 4-pane → 2-pane** (resolves anti-pattern §3.1 from
  `docs/pr10_prep/ui_design_principles.md`; cross-confirmed by
  `competitor_ui_deep_dive.md` + Shark README's clutter-reduction
  commitment).
- **Seven UX Q-locks** (§0.1 synthesis from
  `competitor_ui_deep_dive.md` + `ui_design_principles.md` +
  `ui_mockups_and_debates.md`): Q1 two-pane; Q2 hand-class labels
  in cells; Q3 default 1000 iterations (target-exploitability
  opt-in); Q4 4-of-6 bet sizes (33/75/100/all-in); Q5 combo
  inspector BELOW matrix; Q6 reach filter default 0.01; Q7 yellow
  dismissible "Mock mode" banner.
- **Smoke test count: 8 → 20** (original PR 10 §10.C scope expanded
  to §10.1 + §10.2 + §10.3 + §10.4).
- **Q3 coin-flip flag**: 1000 vs 2000 iterations — if PR 10a manual
  testing surfaces under-converged matrices on common spots, bump
  to 2000 in PR 10b.

### Internal

- `__version__` bumped to `0.6.0` (MINOR).
- Server binds `127.0.0.1` by default (no `0.0.0.0`, no auth, no TLS).
- NiceGUI `native=True` (pywebview) explicitly NOT used; browser-served
  only. `.dmg` packaging deferred to PR 11.
- Three-agent fan-out with non-overlapping file ownership; post-
  implementation audit pass per `docs/pr10_prep/audit_prompt_final_10a.md`.
- Import-discipline asserted by
  `test_ui_never_imports_mock_specific_symbols`: `ui/` outside
  `ui/state.py` contains zero `mock_solver` references.
- Engine pollution check: `git diff integration -- poker_solver/range.py`
  returns EMPTY (`RangeWithFreqs` wraps, never modifies).

### Out of scope (deferred)

- Real solver wiring (PR 10b's one-line import swap in `ui/state.py`).
- `.dmg` packaging + native-desktop wrapper (PR 11).
- Library persistence beyond the stub dialog (PR 11).
- Mobile-responsive layout; additional languages (English-only).
- New engine tests; modifying `poker_solver/range.py`
  (`RangeWithFreqs` WRAPS — does not modify).
- NN warm-start opacity; GTOW-style cloud library.

### Dependencies

- **Optional**: `nicegui>=2.0,<3.0` under `[project.optional-dependencies] ui`.
  Not added to base `dependencies`; engine loads with zero UI overhead.

### License compliance

- NiceGUI is MIT (declared as optional extra).
- No code copied from competitor UI projects (Pio, GTOW, Monker,
  DeepSolver — only architectural patterns).
- R/Y/G color triad is widely-used poker-industry standard, not
  copyrightable expression. `competitor_ui_deep_dive.md` cites
  competitor sources verbatim for design-pattern attribution
  without code copy.
