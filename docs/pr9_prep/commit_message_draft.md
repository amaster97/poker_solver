PR 9: HUNL preflop (Python + Rust tiers, blueprint + subgame refinement) (v0.7.0)

Ships the first end-to-end HUNL preflop → river solve in both tiers
(Python reference + Rust production), completing the v1 deliverable
PLAN.md §1 commits to: "HUNL postflop + preflop together." Three-agent
fan-out (A: Python blueprint + preflop_solver + dispatch; B: Python
subgame_refiner; C: Rust port + PyO3 + all Python tests) plus a
post-implementation audit pass. Solves at every supported stack depth
(15 < stacks ≤ 250 BB; the 2-15 BB short-stack regime continues to
dispatch to PR 3.5's push/fold charts), produces a strategy table
covering every preflop infoset, and refines reached postflop subgames
with the full PR 3 action menu using PR 5's `solve_hunl_postflop` as
the kernel.

Bumps __version__ to 0.7.0 per semver (new public API: `solve_hunl_preflop`,
`build_blueprint`, `refine_subgame`, `PreflopSolveResult`, `BlueprintResult`,
`SubgameRefinementResult`, `SubgameKey` re-exported from `poker_solver`,
plus the `on_progress` kwarg threaded across all three Python entrypoints
+ three Rust entrypoints for PR 10b UI dispatch). MINOR bump per the
project's PR 2 / PR 3 / PR 5 / PR 6 / PR 8 precedent; net-additive surface
(no breaking changes to PRs 1-8). This commit bundles the v0.7.0 release
artifacts together with the implementation so the merge tip is releasable
as-is:
- poker_solver/__init__.py: __version__ "0.6.0" -> "0.7.0".
- pyproject.toml [project] version "0.6.0" -> "0.7.0".
- CHANGELOG.md: new [0.7.0] - 2026-05-22 section above [0.6.0],
  populated with the PR 9 entry moved out of [Unreleased].
- README.md: "Current version: 0.6.0" -> "Current version: 0.7.0",
  with the feature-line caption updated to the v0.7 line ("HUNL
  preflop solve via blueprint + subgame refinement, Python + Rust").

Scope (spec §1, §3, §4, §5, §6, §7, §8, §10):
- Two-stage solve per Pluribus pattern (Brown & Sandholm 2019): coarse
  blueprint pass over preflop+postflop at tight card abstraction +
  restricted postflop action menu (1 size + all-in, 1-cap), then
  per-subgame refinement at the full PR 3 menu (6 sizes + all-in,
  3-cap) for every preflop leaf above `reach_threshold` (default 1e-3).
- Stack-depth dispatch composition (PR 9 §6 CANONICAL; PR 3.5 §6 and
  PR 5 §6 cross-reference this section): push/fold short-circuit at
  ≤15 BB → `pushfold.solve_pushfold` (PR 3.5); ValueError at >250 BB;
  postflop branch at `starting_street >= Street.FLOP` → PR 5; preflop
  branch at `starting_street == Street.PREFLOP` → PR 9. Push/fold
  short-circuit fires BEFORE postflop and preflop branches regardless
  of starting_street.
- Card abstraction tier per stack depth (PLAN.md §1 table): 256/128/64
  default (15-150 BB); 128/64/32 (150-200 BB); 64/32/16 (200-250 BB);
  preflop stays lossless (169 strategically-unique classes via
  suit-iso, per PR 4 §7.12).
- Canonical-class preflop chance generator in `hunl.py`: yields the
  169×169 unique hand-class chance outcomes with combinatorial weights
  (pairs 6 / suited 4 / offsuit 12) AND blocker-aware opponent class
  enumeration (hero AA → villain AA = 1 combo, not 6; hero AKs →
  villain AKs = 3 combos). Default 1.6M-combo generator preserved
  unchanged (per §14 #8 decision); `BlueprintResult` builder
  auto-opts in via `chance_strategy="canonical_classes"`.
- `on_progress: Callable[[int, float, MemoryReport], None] | None`
  kwarg threaded through all three Python entrypoints
  (`solve_hunl_preflop`, `build_blueprint`, `refine_subgame`) AND
  three Rust entrypoints (`solve_hunl_preflop_rust`,
  `build_blueprint_rust`, `refine_subgame_rust` via Python::with_gil
  + callable.call1). Refiner forwards to PR 5's `solve_hunl_postflop`
  unchanged. Cancellation is NOT part of this contract — PR 10a
  handles via a separate flag.
- CLI: `--hunl-mode preflop` plus `--stacks`, `--ante`,
  `--blueprint-iterations`, `--refine-iterations`, `--reach-threshold`,
  `--abstraction`, `--max-memory-gb`. The `--hunl-mode full` path
  (which raised NotImplementedError pointing at PR 9 since PR 5) now
  wires to the preflop solver directly; `full` is a deprecated synonym
  for `preflop` (per §14 #9 decision).
- DCFR algorithm + hyperparameters unchanged (α=1.5, β=0, γ=2.0). No
  `--alpha` / `--beta` / `--gamma` CLI flags. `dcfr.py`, `abstraction/`,
  and PR 5's `hunl_solver.py` all consumed read-only.

New files (poker_solver/):
- preflop_solver.py (~300 LOC): `solve_hunl_preflop` orchestrator.
  Validates config + dispatches push/fold short-circuit + stack ceiling
  + builds blueprint + identifies reachable subgames + refines each +
  assembles `PreflopSolveResult`. Threads `on_progress` to both
  `build_blueprint` and `refine_subgame` calls.
- blueprint.py (~250 LOC): `build_blueprint` coarse preflop solver.
  Constructs the coarse `HUNLConfig` (1-size 0.75-pot postflop menu,
  1-cap, full preflop menu), runs DCFR for 50k default iterations,
  walks the result to compute reach probabilities + leaf values per
  preflop terminal, returns `BlueprintResult`. Memory probe instrumented
  with 10% RSS calibration tolerance (PR 5 §7.6 inheritance).
- subgame_refiner.py (~350 LOC): `refine_subgame` postflop refinement.
  Extracts per-player ranges from the blueprint's posteriors (NOT 1/169
  priors — load-bearing; range[hand_class] computed via CFR reach
  recurrence under blueprint.strategy, weighted by canonical-class
  blocker-aware combos), constructs a refinement `HUNLConfig` with
  full PR 3 menu + 3-cap, warm-starts the regret tables from the
  blueprint where infoset keys overlap, calls
  `hunl_solver.solve_hunl_postflop(refinement_config, abstraction,
  iterations=refine_iterations, on_progress=on_progress)`, returns
  `SubgameRefinementResult` keyed by `SubgameKey`.

Modified (poker_solver/):
- solver.py: extends `solve()` with the canonical §6 dispatch — push/fold
  short-circuit at eff_stack_bb <=15 (regardless of starting_street),
  ValueError at eff_stack_bb >250, postflop branch at starting_street
  >= FLOP, preflop branch at starting_street == PREFLOP. Existing PR
  1-8 routing (Kuhn/Leduc/HUNL postflop) unchanged.
- cli.py: `--hunl-mode preflop` choice + the seven new flags. `full`
  alias preserved as deprecated synonym.
- hunl.py: `_enumerate_preflop_hole_outcomes_canonical()` generator
  (169 × 169 outcomes, 6/4/12 weights, blocker-aware). Default
  `_enumerate_preflop_hole_outcomes()` (1.6M outcomes) preserved
  unchanged. Detection via `chance_strategy="canonical_classes"`
  kwarg; default behavior unchanged.
- __init__.py: re-exports `solve_hunl_preflop`, `PreflopSolveResult`,
  `BlueprintResult`, `SubgameRefinementResult`, `SubgameKey`,
  `build_blueprint`, `refine_subgame`.

New files (crates/cfr_core/src/):
- preflop.rs (~600 LOC): Rust port of `preflop_solver.py`. Mechanical
  translation per PR 6 pattern; reuses PR 6's postflop port for the
  postflop legs.
- blueprint.rs (~400 LOC): Rust port of `blueprint.py`. Reuses PR 6's
  `dcfr.rs` core.
- subgame.rs (~300 LOC): Rust port of `subgame_refiner.py`. Wraps
  PR 6's postflop solver in the refinement loop.

Modified (crates/cfr_core/src/):
- lib.rs: PyO3 bindings for `solve_hunl_preflop_rust`,
  `build_blueprint_rust`, `refine_subgame_rust`. Each accepts
  `Option<PyObject>` for `on_progress` and invokes via
  `Python::with_gil` + `callable.call1((iter, expl, report))`. JSON
  config marshalling; py.allow_threads around the solve.

New tests:
- tests/test_hunl_preflop_blueprint.py (~6 tests): convergence at 100
  BB (slow; CI variant at 500 iter), reach-probabilities-sum-to-one,
  leaf-values-finite, strategy-covers-all-preflop-infosets, memory-
  under-budget, coarse-menu-respected. Plus `test_preflop_canonical_
  chance_weights_correct` (brute-force validator against a tiny
  subset; locks the 6/4/12 + blocker math).
- tests/test_hunl_preflop_refinement.py (~5 tests): parity with direct
  PR 5 postflop solve (5e-2 per action), warm-start-speeds-convergence
  (soft), full-action-menu-respected, reach-threshold-filtering,
  ranges-extracted-correctly (`p0_range["AA"] > p0_range["72o"]` with
  meaningful ratio).
- tests/test_hunl_preflop_integration.py (~5 tests): dispatch boundary
  tests at 15 BB / 16 BB / 251 BB (locked names per §6: `test_preflop_
  dispatch_pushfold_at_15bb`, `_solver_at_16bb`, `_error_at_251bb`),
  published-ref SB-open-raise at 100 BB (AA/JJ/72o anchors), combined
  exploitability < 0.05 BB/hand on the Pio 100 BB cash-game validation
  fixture (slow; CI variant at 5k blueprint + 2k refine asserts
  < 0.5 BB/hand).
- tests/test_preflop_diff.py (~4 tests): Python ↔ Rust differential at
  5e-3 per-action / 1e-3 × base_pot per-spot game value (PR 6/7/8
  tolerance cluster per consistency review I3; was misquoted as 1e-4
  in an earlier draft). Tests cover blueprint, refinement, combined
  strategy table, and dispatch path consistency across tiers.
- tests/fixtures/hunl_preflop_fixtures.py: `preflop_config_100bb()`,
  `preflop_config_50bb()`, `preflop_config_200bb()`, reuses PR 5's
  tiny synthetic abstraction.

Spec amendments locked this round (4 items, per the 2026-05-21
consistency review applied pre-launch):
- §6 declared the CANONICAL HUNL dispatch composition section; PR 3.5
  §6 and PR 5 §6 cross-reference instead of restating ordering.
- §10.4 diff-test tolerance aligned to the PR 6/7/8 cluster (5e-3 per
  action / 1e-3 × base_pot per-spot game value); the earlier 1e-4
  figure was a misquote and is excised.
- §7.4 + §17 end-to-end exploitability target <0.05 BB/hand added on
  the Pio 100 BB cash-game validation fixture (matches the "professional
  standard" of <0.5% pot from gtow_how_solvers_work.md, ~7× looser
  than Pio's published benchmark to account for our coarser blueprint).
- §12 explicit 10% psutil RSS calibration inheritance from PR 5 §7.6
  (runs on every blueprint solve AND every per-subgame refinement,
  not just the blueprint pass).

Notable contract decisions (defaults per spec §14):
- Hard cliff at 15 BB between push/fold chart and preflop solver
  (NOT a 12-18 BB interpolation band).
- Blueprint default menu: 1 size (0.75-pot) + all-in, 1-cap (NOT 2
  sizes; load-bearing for the 14 GB memory ceiling at 100 BB).
- Maximum stack depth 250 BB with two-tier-tightened abstraction
  (64/32/16); ValueError at >250 BB.
- Default reach_threshold = 1e-3; default blueprint_iterations =
  50_000; default refine_iterations = 10_000.
- Canonical-class chance generator is opt-in (`chance_strategy=
  "canonical_classes"`); default 1.6M-combo generator preserved
  unchanged (avoids breaking PR 3 / PR 5 callers).
- `--hunl-mode preflop` is canonical; `--hunl-mode full` is a
  deprecated synonym.
- Full-traverse DCFR (consistent with PRs 1-8); MCCFR is deferred.
- Rust port is a v0.7 ship requirement (parity with PR 6's
  two-tier-from-day-1 commitment).

Out of scope (per spec §2): push/fold mode at ≤15 BB (PR 3.5
unchanged), ante UI configurability (PR 10), multi-table tournaments
/ ICM, 3-handed / 6-max, rake, continuous bet sizing, real-time
depth-limited search, asymmetric per-position ranges (node-locking),
new abstraction artifact, new DCFR algorithm. All deferred to v2 or
beyond.

Verification:
- cargo build --release --package cfr_core: clean.
- cargo test --package cfr_core --all-targets: all Rust tests pass
  (PR 1-8 existing + the new preflop/blueprint/subgame tests
  exercised via the PyO3 boundary in tests/test_preflop_diff.py).
- cargo clippy --package cfr_core --all-targets -- -D warnings: clean.
- pytest -m "not slow and not very_slow" --tb=line: all pass / skip;
  no failures, no timeouts. PR 1-8 regression: all pass unchanged.
- pytest tests/test_hunl_preflop_*.py tests/test_preflop_diff.py: ~20
  new Python tests + 4 differential tests all pass at the 5e-3 / 1e-3
  cluster.
- ruff check + ruff format + black --check + mypy --strict on the
  modified Python files: clean.
- check_pr.sh license audit: clean; no new third-party deps. PyInstaller
  not added here (PR 11). psutil already on the dep list from PR 5.
- Manual CLI smoke: `poker-solver solve --game hunl --hunl-mode preflop
  --stacks 15` dispatches to push/fold chart (no blueprint built);
  `--stacks 16` routes to preflop solver; `--stacks 251` raises
  ValueError. End-to-end 100 BB preflop solve with 5k blueprint +
  2k refine iter runs in <2 hours Python / <30 min Rust on Apple M4
  Pro; CI variant exploitability < 0.5 BB/hand.

License compliance: zero AGPL code. Every new .rs file ships the
module-level attribution docstring per PR 6 §3 template:
- preflop.rs cites `poker_solver/preflop_solver.py` (project-internal,
  MIT) for semantics; Pluribus paper (Brown & Sandholm 2019) cited
  from references/papers/ for the blueprint+refinement pattern.
- blueprint.rs cites `poker_solver/blueprint.py` (MIT) +
  noambrown_poker_solver/cpp/src/trainer.{h,cpp} (MIT) for
  DCFR-on-preflop control flow.
- subgame.rs cites `poker_solver/subgame_refiner.py` (MIT); reuses
  PR 6's `hunl_solver.rs` (MIT) for the postflop kernel.
- Every file carries the explicit "NEVER copy from
  references/code/postflop-solver (AGPL) or
  references/code/TexasSolver (AGPL)" disclaimer.
- check_pr.sh license audit (PLAN.md §4 step 6) confirms no new
  AGPL/GPL deps.

Branch: pr-9-hunl-preflop (off integration tip post-PR-8). Awaits
PR 10b (UI dispatch through the new entrypoints) for end-to-end
user-facing browser flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
