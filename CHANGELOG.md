# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

In-flight on feature branches; not yet merged to `main`.

### In progress
- PR 8+: NEON SIMD; macOS packaging; PR 10b mock→real solver swap.

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

## [0.5.2] - 2026-05-22

PR 4.5: Audit-debt sweep. Bundles 13 should-fix / nice-to-fix items from
the PR 3 / 3.5 / 4 / 5 audit reports into one mechanical cleanup PR.
No behavior changes; no spec amendments; no new tests. PATCH bump per
SemVer: backward-compatible fixes only. Three-agent fan-out (A: PR 3/3.5;
B: PR 4; C: PR 5) per `docs/pr4_5_audit_debt/launch_kickoff.md` sec 2.
Audit verdict READY-WITH-PATCHES per
`docs/pr4_5_audit_debt/audit_report.md`; must-fix patches landed before
this commit.

### Added

- **License-posture headers** on three modules (no third-party derivation;
  original implementation): `poker_solver/hunl.py` (3-A),
  `poker_solver/action_abstraction.py` (3-B),
  `poker_solver/abstraction/equity_features.py` (4-A).
- **`max_boards_per_street` kwarg** on `build_abstraction(...)` (4-D;
  `poker_solver/abstraction/precompute.py`). Opt-in sentinel:
  `None` = autosize (existing default behavior preserved); `-1` = no cap;
  `int > 0` = fixed cap. Surface-only; internal 5000-iteration autosize
  threshold unchanged. Named constants replace prior magic numbers.
- **Named byte / iteration constants** in `poker_solver/profiler/memory.py`
  (5-A) replacing literal magic numbers; clarifies units at call sites.

### Changed

- **SHOWDOWN predicate tightened** at `poker_solver/hunl.py:326` from
  `state.street >= Street.FLOP` to explicit `{FLOP, TURN, RIVER}`
  membership (4-B). Latent fix; solver's `_is_terminal` guard masks it
  currently, but the explicit set future-proofs against new `Street`
  enum members.
- **Unreachable-branch annotations** added to
  `enumerate_legal_actions` stack<=0 branch (3-E,
  `poker_solver/action_abstraction.py`), `_kmeans_plusplus_init`
  empty-cluster fallback (4-C,
  `poker_solver/abstraction/emd_clustering.py`), and a misc HUNL branch
  (`poker_solver/hunl.py`). All upstream-guarded paths; asserts do not
  trip in CI.
- **`pushfold.py` documentation/header tightening** (3.5 docs;
  `poker_solver/pushfold.py`). Docstring + module-header polish only;
  no API change.
- **Dropped unused `numpy` import** in `poker_solver/profiler/memory.py`
  (5-A); the `_ = np` suppression was vestigial.

### Internal

- `__version__` bumped to `0.5.2` (PATCH).
- Three-agent fan-out with non-overlapping file ownership; `hunl.py`
  edited by both Agent A (header + low-line unreachable annotation) and
  Agent B (`:326` SHOWDOWN predicate); line ranges disjoint and
  auto-merged trivially. No manual conflict-resolution commits.

### Out of scope (deferred)

- K-means quality tuning (post-PR-6 Rust port enables full enumeration).
- `save_abstraction` byte-determinism design (no current consumer).
- 6 skip-marked PR 5 TURN tests (PR 6 Rust `lookup_bucket` resolves).
- Spec-amendment items (`HUNLState.config` source-of-truth; `d=2` jam
  landmark; strategic-equivalence collapse).
- `_canonicalize` rename, CLI integration items, test coverage adds.

## [0.5.1] - 2026-05-22

PR 7: River-spot diff vs Noam Brown's MIT-licensed `noambrown/poker_solver`
(C++ reference). First external-Nash agreement gate in the project. PR 6's
parity check was internal Python ↔ Rust; this PR closes the loop with an
independent oracle. PATCH bump per semver — no public API change, no new
runtime deps, validation-only addition.

### Added

- **Parity wrapper package** (`poker_solver/parity/`): internal test
  infrastructure for invoking Brown's `river_solver_optimized` binary as a
  subprocess, parsing its JSON `--dump-strategy` output, and canonicalizing
  histories between Brown's raise-as-delta and our raise-to-total conventions.
  Original Python (no C++ copied); license attribution in
  `noambrown_wrapper.py` header.
- **River-spot fixture** (`tests/data/river_spots.json`, schema_version=1):
  15 spots × 5 board categories (dry rainbow, wet rainbow, monotone, paired,
  broadway-heavy). Per-spot range/board non-overlap validated at load.
- **Build script** (`scripts/build_noambrown.sh`): idempotent
  out-of-tree build; soft-fails (exit 0) on hosts without cmake/c++ so CI
  on missing-Xcode-CLT macOS hosts skips cleanly.
- **River diff harness** (`tests/test_river_diff.py`, ~491 LOC,
  `@pytest.mark.parity_noambrown` opt-in): subprocess driver with
  `tempfile.NamedTemporaryFile(suffix=".json", delete=False)` for
  xdist-worker safety; per-action tolerance `5e-3`, per-spot game-value
  tolerance `1e-3 * pot`; 80% history-coverage assertion.
- **Self-sanity smoke** (`tests/test_river_diff_self_sanity.py`, ~487 LOC,
  9 tests): Brown-binary-free; fixture loaders, history canonicalization
  round-trip, strategy-matrix shape, iterations override, binary finder
  returns Path-or-None.
- **`parity_noambrown` pytest marker** registered in `pyproject.toml`.

### Changed

- **`tests/test_hunl_diff.py`** (+21/-6): hardened the PR 6 stale-`.so`
  import-fallback path. The previous silent skip masked Rust-tier
  regressions after `cargo build` without `maturin develop`. Now raises
  `RuntimeError` pointing at `maturin develop --release`.

### Internal

- DCFR triple `(alpha=1.5, beta=0, gamma=2)` and `--iters 2000` passed
  explicitly to Brown — same hyperparameters as our Rust tier; explicit
  `--seed 7` matches Brown default but enforced per spec §11 #1.
- Brown binary path resolved via repo-anchored
  `Path(__file__).resolve().parents[2] / "references" / ...` (not
  cwd-anchored).
- `__version__` bumped to `0.5.1`.

## [0.5.0] - 2026-05-22

PR 6: Rust HUNL postflop port (~24x speedup, bit-exact diff at 100k iters);
`--backend rust` flag; PyO3 `_rust.solve_hunl_postflop` export.

### Added

- **Rust HUNL postflop solver** (`crates/cfr_core/src/hunl.rs`,
  `hunl_tree.rs`, `hunl_eval.rs`, `abstraction.rs`, `hunl_solver.rs`;
  exposed via PyO3 as `poker_solver._rust.solve_hunl_postflop`).
  Same DCFR (alpha=1.5, beta=0, gamma=2.0), same action menu, same
  bucket lookups as the PR 5 Python tier. Bit-exact parity at 100k
  iterations on the tiny river-subgame fixture; 5e-3 parity on the
  flop fixture. ~24x speedup vs Python (3.88 s Rust vs 92.9 s Python
  at 100k iters, Apple M4 Pro, median of 3 trials).
- **CLI**: `--backend rust` flag on `solve --game hunl --hunl-mode
  postflop`. Default stays `python`.
- **New Rust deps** (all MIT/Apache 2.0 dual-licensed): `ndarray = "0.16"`,
  `ndarray-npy = "0.9"` for `.npz` abstraction loading.

### Changed

- `solver.py` dispatch: HUNL postflop Rust branch composes AFTER the
  PR 3.5 push/fold short-circuit and BEFORE the Python fallback
  (PR 9 §6 canonical ordering).
- Python recomputes exploitability + game_value from the Rust-returned
  strategy (Kuhn/Leduc precedent; removes cross-tier float drift).

## [0.4.0] - 2026-05-22

PR 4 + PR 5 milestone: card abstraction and HUNL postflop solve land on
`integration`. Adds the bucketing infrastructure required for tractable
postflop CFR, the Python reference postflop solver orchestrator, and a
per-street memory profiler that surfaces the river-ratio trigger for the
PR 4 revisit.

### Added

- **Card abstraction package** (`poker_solver/abstraction/`, PR 4;
  commit `6565b84`). EMD-based equity-distribution bucketing with
  Slumbot-inspired k-means; default bucket counts 256/128/64 for
  flop/turn/river respectively. Suit-isomorphism canonicalization
  built-in. Public API: `AbstractionTables`, `AbstractionRef`,
  `build_abstraction`, `load_abstraction`, `save_abstraction`,
  `lookup_bucket`, `resolve_abstraction_ref`,
  `canonicalize_for_suit_iso`. Methodology notes under `docs/pr4_prep/`.
- **HUNL postflop solve orchestrator** (`poker_solver/hunl_solver.py`,
  PR 5; commit `a9d02ca`). `solve_hunl_postflop(...)` + `HUNLSolveResult`
  dataclass wire the abstraction tables, DCFR core, and HUNL tree into
  a single entrypoint for flop/turn/river subgames.
- **Per-street memory profiler** (`poker_solver/profiler/memory.py`,
  PR 5). `MemoryProbe` (sampler), `MemoryReport` (per-street rollup
  with `.river_ratio` PR-4-revisit trigger), `StreetMemoryEntry`
  (per-street record). `psutil>=5.9` runtime dep.
- **CLI**: `precompute-abstraction` subcommand + `solve --hunl-mode postflop`
  with new `--board`, `--stacks`, `--bet-sizes`, `--max-memory-gb`,
  `--abstraction PATH` flags.
- **Test fixtures**: `tests/fixtures/hunl_solve_fixtures.py` for the
  postflop solve battery.

### Changed

- **`HUNLConfig.abstraction`** field added (additive, default `None` —
  preserves PR 3 lossless behavior when omitted).
- **`solve()` dispatch**: HUNLPoker postflop routing branch added after
  the push/fold short-circuit; non-HUNL games unaffected.
- **CLI `--hunl-mode full`**: retargeted from PR 5 to PR 9.

### Fixed

- Per-PR audit must-fix patches applied and verified for PR 4 and PR 5
  (audits in `docs/pr4_prep/audit_report.md` and PR 5 equivalent).
- PR 5 audit must-fix #1 — `hunl_solver.py` exploitability guard
  against zero-iteration solves.

### Dependencies

- `psutil>=5.9` added as a runtime dep (memory profiler).
- `pytest-timeout>=2.3` added as a dev dep; pytest-timeout wiring under
  `[tool.pytest.ini_options]` (90s default, slow/very_slow markers).

### Internal

- `__version__` bumped to `0.4.0` (lag from v0.3.0 fully reconciled).

## [0.3.1] - 2026-05-21

PR 3.5 audit follow-up + sparse JSON fill. Two correctness fixes caught
during the PR 3.5 ready-to-commit verification chain. No new public API;
no schema changes. v0.3.0 was tagged but never distributed before these
fixes landed, so v0.3.1 is effectively the first public v0.3 release.

### Fixed

- **`get_full_range` returns all 169 canonical hand classes**
  (`poker_solver/pushfold.py`). The DCFR chart generator writes cells in
  sparse form (zero-frequency entries omitted), so the previous
  `get_full_range` returned 113 keys at 10 BB SB jam instead of 169.
  Now explicitly fills every canonical class via `_all_hand_classes()`
  helper, defaulting absent hands to `0.0`. Silent-data-loss class of
  bug; surfaced when Agent B's DCFR chart regeneration changed the
  sparse pattern.
- **Push/fold dispatch requires `starting_street == PREFLOP`**
  (`poker_solver/solver.py`). The PR 3.5 dispatch checked only stack
  depth, which silently misfired on HUNL subgames starting on a postflop
  street (e.g. `default_tiny_subgame()` at 10 BB river). Added the
  `starting_street` guard so river/turn/flop subgames always run through
  the tree solver. Regression test:
  `test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack`.

### Internal

- Both bugs caught by the parallel-agents + cross-check discipline (one
  agent writing `docs/architecture.md` surfaced the dispatch gap; the
  chart-generation agent surfaced the sparse-JSON gap). Sequential
  single-agent execution would likely have shipped both bugs.

## [0.3.0] - 2026-05-21

The HUNL milestone. This release closes out the small-game phase (Kuhn +
Leduc) and stands up the full Heads-Up No-Limit Hold'em substrate: game tree,
14-action abstraction with raise caps, ante support, and integer-cents chip
arithmetic. It also ships push/fold charts for short-stack play (2-15 BB)
and a hybrid exact / Monte Carlo equity calculator.

### Added

- **HUNL (Heads-Up No-Limit Hold'em) tree builder + action abstraction**
  (PR 3, Python tier; Rust port in PR 6).
  - `poker_solver/hunl.py`: `HUNLState` + `HUNLPoker` + `HUNLConfig` +
    `Street` IntEnum + `default_tiny_subgame()`. Implements the `Game`
    protocol alongside Kuhn and Leduc.
  - Integer-cents chip arithmetic (1 BB = 100 cents); floating-point chip
    math is forbidden in this module. Utilities only convert to BB-floats
    at terminal states.
  - `poker_solver/action_abstraction.py`: 14-action enum
    (`FOLD`, `CHECK`, `CALL`, 5x `BET_X`, 5x `RAISE_X`, `ALL_IN`).
  - Bet sizes: 33% / 75% / 100% / 150% / 200% pot, plus all-in.
  - Raise caps: preflop 4 (allows the 4-bet/5-bet ladder), postflop 3.
    After cap, the next aggressive action forces all-in.
  - Ante support: `HUNLConfig(ante=N)` initializes contributions to
    `(SB+ante, BB+ante)`; tree shape unchanged by ante (default 0).
  - `poker_solver/card.py`: `card_to_int` / `int_to_card` helpers used by
    HUNL chance-outcome encoding (and the upcoming Rust port).
  - CLI: `poker-solver solve --game hunl --hunl-mode {tiny_subgame, full}`.
    `tiny_subgame` solves the deterministic AhKc-vs-QdQh river fixture;
    `full` raises `NotImplementedError` pointing at PR 5.

- **Push/fold chart mode for 2-15 BB short stacks** (PR 3.5).
  - `poker_solver/pushfold.py`: chart lookup API
    (`get_pushfold_strategy`, `get_full_range`, `is_pushfold_mode`,
    `PushFoldChartUnavailable`).
  - `poker_solver/charts/pushfold_v1.json`: real DCFR-generated Nash
    equilibrium charts for each stack depth in `{2, 3, ..., 15}` BB,
    both `sb_jam` and `bb_call_vs_jam` positions, 169 hand classes per
    cell. Action set is pure jam/fold (no minraise / limp lines).
  - Generated by `scripts/generate_pushfold_charts.py` via a
    card-removal-aware compat-weighted 169x169 matrix-game DCFR solve.
    See `docs/pushfold_v1_generation_notes.md` for the full methodology.
  - Exploitability after convergence (BB/100): essentially 0.0 at every
    depth; spec target was < 0.05 BB/100.
  - Automatic dispatch: when `solve()` receives a `HUNLPoker` whose
    effective stack falls in `[2, 15]` BB, it routes to chart lookup
    (O(1)) instead of running the tree solver. Public-API change:
    `SolveResult.backend == "pushfold"` for the lookup path.

- **Hybrid exact-enumeration + Monte Carlo equity calculator**
  (user-authored, merged via PR #1 on `main`).
  - `equity()` now auto-enumerates all remaining board runouts when all
    hands are concrete and the runout count is `<= enum_threshold`
    (default 100,000). Flop hand-vs-hand is exact and instant
    (e.g. 990 runouts in ~60 ms).
  - Range inputs and large preflop state spaces still fall back to
    Monte Carlo sampling.
  - Default MC iteration count bumped from 10,000 to 250,000.
    Standard error per hand: ~0.1% (down from ~0.5%).
  - `enum_threshold` exposed as a public parameter on `equity()`.

- **Tests:** 53 new tests across PR 3 (41) and PR 3.5 (12).
  - `tests/test_hunl_core.py` (19 tests): rules, ante, all-in, street
    transitions, integer chip arithmetic.
  - `tests/test_hunl_tree.py` (10 tests): tree shape, tiny subgame solve,
    raise-cap enforcement.
  - `tests/test_action_abstraction.py` (12 tests): bet-size enumeration,
    legal-action sets, raise cap, dedup, force-all-in threshold.
  - `tests/test_pushfold.py` (12 tests): per-hand lookup, full-range,
    out-of-range errors, premium / trash anchors, range monotonicity vs.
    stack depth, solve() dispatch.

### Changed

- **`equity()` default `iterations`:** `10_000` -> `250_000`. Existing
  callers that pass `iterations=` explicitly are unaffected; callers
  relying on the default will see longer runtimes (still seconds for
  postflop, minutes for full ranges) in exchange for ~5x precision.
- **`equity()` dispatch:** previously always Monte Carlo; now auto-picks
  exact enumeration for concrete hands when the runout space is small.
  Behavior is strictly better (exact when feasible, MC otherwise); no
  API break.
- **`poker-solver equity --iterations` help text:** clarified that the
  flag is ignored on the exact-enumeration path.
- **`solve()` dispatch:** new `HUNLPoker` short-stack branch routes to
  pushfold lookup before the DCFR path. Non-HUNL games and HUNL configs
  outside `[2, 15]` BB are unaffected.
- **`__version__`:** `0.1.0` -> `0.2.0` in package metadata (note:
  release tag is `0.3.0`; `__version__` lag will be reconciled in a
  later PR).

### Fixed

- **Best-response fixed-point iteration** (`poker_solver/solver.py`):
  single-pass DFS best-response silently used action 0 for unset deeper
  infosets. Kuhn worked by luck (single decision path); Leduc and HUNL
  exposed the bug. Fix: iterate BR to fixed point. Discovered during
  PR 2 (Leduc); kept on the changelog here because it surfaced again
  while validating HUNL.
- **ALL-IN-CALL street completion** (`poker_solver/hunl.py`): when a
  player calls all-in, the street did not advance correctly. 1-line
  fix in `_street_complete`; caught by Agent A during PR 3
  implementation.

### Documentation

- `docs/pushfold_v1_generation_notes.md`: generator methodology, runtime
  breakdown, landmark frequencies, Sklansky-Chubukov cross-check,
  convergence diagnostics, known limitations.
- `docs/pr3_prep/audit_report.md`: PR 3 mandatory audit
  (READY, 0 must-fix, 7 should-fix, 7 nice-to-fix).
- `docs/release_notes_v0.3.md`: user-facing release notes for this
  release.

### Internal

- Per-PR feature branches enforced from PR 3 onward (`pr-N-<title>`).
- Mandatory PR audit from PR 3 onward: a fresh `general-purpose` agent
  with no implementation context reviews the diff and writes
  `audit_report.md`.
- `integration` branch ("pseudo-main") autonomously accumulates merged
  PR branches; `main` merges still require explicit user OK.

## [0.2.0] - 2026-05-20

### Added

- **Leduc poker** (PR 2, both tiers).
  - `LeducPoker` + `LeducState` in `poker_solver/games.py` (rules per
    `open_spiel/leduc_poker.cc`, Apache 2.0). 288 infosets total.
  - Multi-round mechanics: chance nodes mid-game (public card revealed
    between betting rounds).
  - DCFR convergence at 600 iterations: game_value = -0.0854 (matches
    literature ~-0.085); exploitability 0.026.
- **Game trait abstraction** in the Rust crate (`crates/cfr_core/src/game.rs`).
  Single CFR core, multiple games via trait dispatch. `KuhnState` and
  `LeducState` both implement `Game`.
- **Rust port of Leduc** (`crates/cfr_core/src/leduc.rs`); Python <-> Rust
  strategies agree within 1e-4 per action probability.
- CLI: `poker-solver solve --game {kuhn, leduc} --backend {python, rust}`.
- 4 new test modules (31 tests): `test_leduc_core` (14), `test_leduc_dcfr`
  (5), `test_leduc_diff` (5), `test_leduc_intuition` (7).

### Changed

- Internal repo hygiene: `PLAN.md` and `docs/` untracked (kept local as
  decision log / author-specific notes; not appropriate for an external
  contributor's clone).

### Fixed

- Best-response single-pass DFS bug (initial fix; revisited in 0.3.0
  context as well).

## [0.1.0] - 2026-05-20

### Added

- **Kuhn poker + DCFR** (PR 1, both tiers).
  - `KuhnPoker` + `KuhnState` in `poker_solver/games.py`.
  - `DCFRSolver` in `poker_solver/dcfr.py` (Brown & Sandholm 2019).
    Hyperparameters: alpha=1.5, beta=0, gamma=2.0 (paper defaults).
  - `solve()` orchestration in `poker_solver/solver.py`.
  - Rust port (`crates/cfr_core/src/kuhn.rs` + `dcfr.rs`); converges to
    Nash value `-1/18`.
- **Two-tier architecture** — Python reference (`poker_solver/`) is the
  spec; Rust production (`crates/cfr_core/`) is the perf tier.
- **maturin / PyO3 build foundation** — `crates/cfr_core` exposed as
  `poker_solver._rust`.
- **Differential testing harness** (`tests/test_dcfr_diff.py`): Rust
  output must match Python within float tolerance on shared inputs.
- **CLI scaffold** (`poker-solver equity`, `poker-solver solve`).
- **References infrastructure**: `references/` directory, license audit,
  `scripts/setup_references.sh` for local clones.
- Hand evaluator (5-7 cards, 9 categories), Monte Carlo equity
  calculator, range parser (`AA, KK-TT, AKs, AKo, 76s+`).

## [0.0.1] - earlier

### Added

- Initial Texas Hold'em equity solver scaffold (`023956e`):
  hand evaluator, Monte Carlo equity, range parser, CLI.

[Unreleased]: https://github.com/amaster97/poker_solver/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.6.0
[0.5.2]: https://github.com/amaster97/poker_solver/releases/tag/v0.5.2
[0.5.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.5.1
[0.5.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.5.0
[0.4.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.4.0
[0.3.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.3.1
[0.3.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.3.0
[0.2.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.2.0
[0.1.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.1.0
[0.0.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.0.1
