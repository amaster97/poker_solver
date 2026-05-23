PR 10b: UI real-solver integration (mock → real swap) (v0.7.1)

Swaps the NiceGUI UI scaffold (PR 10a) from `ui/mock_solver.py` to the
real solver dispatch landed by PR 9 (preflop) and PR 5 (postflop). PR
10b is the smallest PR in the v1 roadmap by code surface (~150-300 LOC
net, mostly deletes) and the first end-to-end real-DCFR experience the
user can launch via `poker-solver ui`. Single-agent execution per
`fanout_ready_10b.md` §5 (delete-and-replace mechanical swap; no
parallel split warranted).

Bumps __version__ to 0.7.1 per semver. PATCH bump (NOT minor) because
the PR adds NO new public API surface; the only contract addition was
already specified by PR 9's `on_progress` kwarg (v0.7.0). PR 10b
deletes `ui/mock_solver.py` and `ui.mock_solver.mock_solve`, but
neither symbol was ever in the public `poker_solver` namespace (the
mock was UI-internal scaffolding only — never re-exported from
`poker_solver/__init__.py`, never documented in README's API table).
Net public-surface delta: zero. PATCH per the project's PR 4 / PR 7 /
PR 10a precedent for net-zero-API releases. The merge tip is
releasable as-is:
- poker_solver/__init__.py: __version__ "0.7.0" -> "0.7.1".
- pyproject.toml [project] version "0.7.0" -> "0.7.1".
- CHANGELOG.md: new [0.7.1] - 2026-05-22 section above [0.7.0],
  populated with the PR 10b entry moved out of [Unreleased].
- README.md: "Current version: 0.7.0" -> "Current version: 0.7.1";
  "## UI (mock)" -> "## UI"; PR 10a mock-mode paragraph removed.

Scope (spec §1, §2, §3, §4, §5, §6, §7):
- UI structure FROZEN at PR 10a (spec §0 line 21). All seven Q-locks
  from `pr10a_spec.md` §0.1 preserved EXCEPT Q7. Q7 downgrades: the
  yellow "Mock mode" banner shrinks to a subtle `(mock)` chip in the
  header, and the chip hides entirely once `state.has_completed_real_solve`
  flips true (first real solve completion). Marker `mock-mode-banner`
  renames to `mock-mode-chip` (the ONE permitted marker change).
- Dispatch wrapper in `ui/state.py` routes by `HUNLConfig.starting_street`:
  PREFLOP → PR 9's `solve_hunl_preflop`; FLOP/TURN/RIVER → PR 5's
  `solve_hunl_postflop`. Push/fold short-circuit (≤15 BB) lives inside
  `poker_solver.solver.solve` from PR 3.5 / PR 9 §6 and is reached via
  either branch transparently.
- `on_progress` kwarg signature locked at
  `Callable[[int, float, MemoryReport], None] | None = None`. BYTE-identical
  default and signature across `solve_hunl_preflop` (PR 9) and
  `solve_hunl_postflop` (PR 5 + PR 10b kwarg add). Default `None` (NOT
  `lambda *a: None`) per `audit_preprep_10b.md` §1.2 — the dispatch
  wrapper assumes identical shape per spec §4 and tripping at the
  default would silently break the first preflop solve.
- Callback fires on the worker thread (`SolveRunner.start`'s worker),
  NOT the main UI thread (per spec §6 threading + PR 10a `audit_prompt.md`
  §1). UI side polls `SolveRunner.expl_history` via `ui.timer(0.5, ...)`
  unchanged; callback's only job is to push `(iter, expl, report)` into
  the runner's protected state.

Deleted files (ui/):
- `ui/mock_solver.py` (~400 LOC). Entire mock module removed; no
  rename, no archival copy under `tests/fixtures/`.
- `ui/mock_solver_fixtures.py` (if PR 10a created it; conditional).

Deleted tests (tests/test_ui_smoke.py):
- `test_mock_solve_returns_real_hunl_solve_result`
- `test_mock_solve_streams_progress_callbacks`
- `test_mock_solve_failure_oom_raises_memory_error_with_partial_report`
- `test_mock_solve_failure_cancelled_returns_partial_result`
- `test_ui_never_imports_mock_specific_symbols`

Added tests (tests/test_ui_smoke.py):
- `test_real_solve_completes_river_subgame` (smoke #14): loads PR 3
  `default_tiny_subgame` preset, sets `iterations=500`, clicks Solve,
  waits for `SolveRunner.status == 'done'`, asserts non-empty
  `average_strategy` AND matrix renders 169 cells with ≥1 non-grey
  cell. Expected wall-clock <2 s.
- `test_real_solve_progress_callback_fires` (smoke #15): mocks
  `on_progress`, asserts ≥1 invocation during a 500-iteration solve
  with `log_every=100`.

Modified (ui/):
- `ui/state.py`: replaces `from ui.mock_solver import mock_solve as
  _solve_postflop_impl` with a thin dispatch wrapper that branches on
  `config.starting_street == Street.PREFLOP` and delegates to
  `solve_hunl_preflop` / `solve_hunl_postflop`. Three lines deleted (mock
  import + `mock_*` kwarg threading through `SolveRunner.start`); ~15
  lines added (dispatch wrapper + imports). `SolveRunner.start` body
  UNCHANGED — same args; only the symbol resolution changes.
- `ui/app.py`: imports `poker_solver.hunl_solver` instead of
  `ui.mock_solver`; preset dropdown loads real-spot configs for the
  12 fixture categories from PR 10a (configs unchanged; only solver
  path differs).
- `ui/views/banner.py` (or wherever the Q7 banner lives): conditional
  gate `if not state.has_completed_real_solve: render chip else: hide`;
  marker swap `mock-mode-banner` → `mock-mode-chip`.

Modified (poker_solver/):
- `poker_solver/hunl_solver.py`: adds `on_progress: Callable[[int,
  float, MemoryReport], None] | None = None` kwarg to
  `solve_hunl_postflop`. Threaded into `_run_with_probe` after the
  existing `log_every` snapshot block: when `log_every is not None`
  AND `on_progress is not None`, invoke `on_progress(done, expl,
  final_report)`. This is the ONE engine-side change PR 10b makes;
  default `None` ensures PR 5/6/7/8 existing callers unaffected.

Out of scope (per spec §2): library viewer wiring (PR 11), native
PyInstaller packaging (PR 11), any UI restructuring (FROZEN at PR
10a), any new solver math, real-time depth-limited search, 3-handed
display (PR 12), node-locking, ICM. All deferred.

Verification:
- pytest tests/test_ui_smoke.py -v: 10 tests pass (8 retained
  unmodified + 2 new). 5 mock-tests deleted.
- pytest -m "not slow and not very_slow" --tb=line: PR 1-10a regression
  all green; engine tests unchanged.
- ruff check + black --check + mypy --strict on `ui/state.py`,
  `ui/app.py`, `poker_solver/hunl_solver.py`: clean.
- `inspect.signature(solve_hunl_preflop) == inspect.signature(solve_hunl_postflop)`
  byte-identical for the `on_progress` parameter (test:
  `test_on_progress_signature_matches_across_solvers`).
- `git ls-files | grep -i mock_solver`: empty.
- `grep -ri 'from ui.mock_solver\|import mock_solver\|mock_solve\|
  mock_progress_callback' poker_solver/ ui/ tests/`: empty (no orphan
  imports or callsites; spec §5 + §7 lock).
- check_pr.sh license audit: clean; no new third-party deps.
- Manual CLI smoke: `poker-solver ui` launches; `default_tiny_subgame`
  preset solves end-to-end with real DCFR output rendered in the
  matrix (~<2 s); `flop_k72r_100bb` preset solves (multi-min;
  pause/resume/stop work); `MemoryError` exceeded-budget path shows
  partial `MemoryReport` (not a stack trace).

License compliance: zero AGPL code. PR 10b is purely a deletion +
import swap; no new code copied from any reference. The one new
engine-side kwarg (`on_progress` on `solve_hunl_postflop`) is original
glue between PR 5's existing `log_every` history append and PR 10b's
worker-thread callback. No new third-party dependencies; existing
`[project.dependencies]` and `[project.optional-dependencies] ui`
unchanged.

Branch: pr-10b-ui-real-solver (off integration tip AFTER both PR 9
and PR 10a have landed). PR 10b unblocks PR 11 (library viewer wires
through `ui/state.py`'s dispatch wrapper unchanged).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
