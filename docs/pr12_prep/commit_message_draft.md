PR 12: 3-handed postflop stretch (approximate equilibrium) (v1.1.0)

Ships the first multi-player solve in the codebase: a 3-handed
postflop solver (flop / turn / river start, three player ranges,
three stack depths) producing an explicitly approximate equilibrium
strategy profile via Linear CFR + 95%-pruning on a heavily-abstracted
tree. PR 12 is the POST-v1 stretch milestone per PLAN.md §2 ("PR 12 —
3-handed postflop stretch (optional; explicitly approximate)") and
the codebase's first move beyond 2p0s where DCFR carries real
convergence guarantees. Three-agent fan-out (A: N-player
generalization of HUNL game state; B: multiway_solver.py + Rust port
+ LCFR loop + per-pair BR; C: tests + fixtures + UI integration) plus
a post-implementation audit pass. Ships if PR 1-11 are stable and v1
is tagged.

Bumps __version__ to 1.1.0 per semver. MINOR bump (NOT patch; NOT
major) because PR 12 adds a NEW public API path — `solve_3p_postflop`,
`MultiwaySolveResult`, `StabilityReport`, `MultiwayBestResponse`
re-exported from `poker_solver`, plus the `--num-players` CLI flag
with 3-range parsing — that did not exist in v1.0.x. Net-additive
surface: HU path (`num_players == 2`, the default) is UNCHANGED;
existing PR 1-11 callers compile and pass unmodified. MINOR per
project's PR 2 / PR 3 / PR 5 / PR 6 / PR 8 / PR 9 precedent for
new-API-no-breakage releases. NOT a MAJOR bump because no breaking
changes to v1.0 — the `HUNLConfig.num_players: int = 2` field is
strictly additive on the dataclass and defaults preserve all v1.0
behavior. Release artifacts bundled with the implementation:
- poker_solver/__init__.py: __version__ "1.0.x" -> "1.1.0".
- pyproject.toml [project] version "1.0.x" -> "1.1.0".
- CHANGELOG.md: new [1.1.0] - 2026-05-22 section above the prior
  v1.0 entries, populated with the PR 12 entry moved out of
  [Unreleased]. Explicit "approximate equilibrium; multi-player CFR
  has no Nash convergence proof" disclaimer in the section header.
- README.md: "Current version: 1.0.x" -> "Current version: 1.1.0",
  with the feature-line caption updated to the v1.1 line ("3-handed
  postflop solve (approximate equilibrium; not Nash)").

Scope (spec §1, §3, §4, §5, §6, §7, §9):
- **Theoretical honesty discipline (spec §3 — LOAD-BEARING):** every
  output surface for 3-handed results labels the strategy as
  "≈ approximate equilibrium" with the locked badge text from §6.3
  ("≈ approximate equilibrium / multi-player; not Nash") and tooltip.
  Badge UNSUPPRESSIBLE per §9 #10 — no CLI flag, no config option,
  no `verbose=False` shortcut. Pluribus paper (Brown & Sandholm 2019,
  *Science* 365:6456) cited as the framing precedent: 6-player
  blueprint described as "near-Nash blueprint" rather than Nash.
- Linear CFR (LCFR = DCFR_{1,1,1}) for iterations 1..t_cutoff (default
  `t_cutoff = T // 2` per Pluribus paper p. 3), then plain CFR
  averaging thereafter. NOT DCFR_{1.5, 0, 2} (β=0 negative-regret
  truncation is a 2p0s heuristic that overclaims Pluribus's empirical
  validation for n-player).
- Negative-regret pruning in 95% of iterations per Pluribus p. 3.
  Threshold C configurable; default `-300_000` cents (-3000 BB).
  `random.random() < 0.95` skip on pruned actions; ~3× wallclock
  speedup per Pluribus's empirical claim.
- N-player game state generalization in `hunl.py` (per spec §4):
  `contributions`, `stacks`, `folded`, `all_in`, `hole_cards` become
  `tuple[..., ...]` length=`num_players`. NEW field
  `HUNLConfig.num_players: int = 2` (default unchanged → all PR 1-11
  callers unaffected). Field name `folded` preserved (NOT renamed to
  `is_folded` — cascading break risk per audit_preprep §1.5).
  Positions LOCKED for 3-max: P0 = SB (first preflop AND postflop),
  P1 = BB, P2 = BTN. Action rotation implemented for N=2 and N=3
  specifically; `num_players >= 4` raises `NotImplementedError` per
  spec §4.3 + §9 #5.
- Side-pot math (`_compute_side_pots(contributions, folded) ->
  list[SidePot]`) with 5 TDA-fixture unit tests per spec §9 #1: equal
  all-in / unequal all-in / folded-contributor / tie split with
  position remainder (SB first postflop) / odd-chip floor-ceiling.
  Each side pot won by the live player with the best hand WHO
  CONTRIBUTED to that pot. Multi-winner-per-side-pot showdown path
  in `multiway_solver.py` reuses `poker_solver.evaluator`.
- Per-pair best-response gap as the diagnostic (NOT "exploitability"):
  three numbers per solve, one per player. Field name `br_gap`. Label
  "≈ best-response EV upper bound (multi-player; NOT Nash
  exploitability)". BR walk weights opponents at decision nodes by
  their joint strategy. NEVER summed; NEVER reported as a single
  number; NEVER labeled "exploitability".
- Convergence stability diagnostic: `StabilityReport(seeds=(0,1,2),
  strategies, l1_per_infoset, pairwise_max, pairwise_mean)`. Soft
  assertion `pairwise_max < 0.05` on the river-only fixture. Failure
  → user warned + badge gains "⚠ stability degraded" line. Diagnostic
  itself MUST be deterministic given the same seeds (test
  `test_stability_diagnostic_is_deterministic` — fails if
  `np.random.default_rng()` used without explicit seed threading).
- Routing in `solver.py`: `config.num_players == 3 AND
  config.starting_street >= Street.FLOP` → `solve_3p_postflop`. HU
  path unchanged (`num_players == 2`). `num_players >= 4` → clear
  `NotImplementedError("PR 12 supports N=2 and N=3 only; 4+ players
  require a separate solve infrastructure.")`. `num_players == 3 AND
  starting_street == Street.PREFLOP` → `NotImplementedError`
  (preflop 3-handed explicitly out of v1 per §2).
- Tighter abstraction for 3-handed: default 128/64/32 (one tier
  tighter than HU default per PLAN.md "150-200 BB" row). Reuses PR 4's
  `precompute-abstraction` unchanged with new `--bucket-counts
  128,64,32`. New artifact `abstractions/3p_default_128_64_32.npz`
  shipped as a documented BUILD RECIPE, not as a committed binary
  (license + repo-size discipline per PR 4 pattern).
- MonkerSolver cross-validation OPT-IN per spec §7.5: test decorated
  `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`.
  Skipped when user has no Monker data. Format documented; user
  populates manually. NO bundled data (license).

New files (poker_solver/):
- multiway_solver.py (~500 LOC): `solve_3p_postflop` orchestrator +
  `MultiwaySolveResult` (extends `SolveResult` with `num_players`,
  per-player `game_value: tuple[float, ...]`, per-player `br_gap:
  tuple[float, ...]`, `convergence_stability: float | None`) +
  `MultiwayBestResponse` + `run_stability_diagnostic(config,
  abstraction, seeds=(0,1,2)) -> StabilityReport`. Module docstring
  cites Pluribus paper (Brown & Sandholm 2019) for LCFR + 95%-pruning
  recipe and Gibson 2013 for the iteratively-strict-dominated theorem
  (IDSD ONLY; explicit "NOT Nash convergence" qualifier per spec §3.1).

Modified (poker_solver/):
- hunl.py (~200 LOC delta): N-player generalization per §4.
  `HUNLState` tuple fields generalized; `HUNLConfig.num_players: int
  = 2`; `_post_blinds_2p()` / `_post_blinds_3p()` route by N;
  `apply()` / `legal_actions()` / `utility()` / `current_player()`
  / `chance_outcomes()` parametrized on `num_players`. All PR 3
  tests pass unchanged (regression gate per §9 #6).
- action_abstraction.py: `ActionContext.num_players` plumbing.
  Bet/raise math unchanged (pot fractions); only "who acts next"
  changes.
- solver.py: routing branch per §9 #5. HU path unchanged.
- cli.py: `--num-players` flag (default 2). When 3, `--ranges`
  accepts three comma-separated range strings. `--help` documented.
- __init__.py: re-exports `solve_3p_postflop`, `MultiwaySolveResult`,
  `StabilityReport`.
- library.py (PR 11): `SpotDescription.config.num_players` already
  serialized; library row badge reads this for 3p display.

New files (crates/cfr_core/src/):
- multiway.rs (~600 LOC): Rust port of `multiway_solver.py`.
  Mechanical translation per PR 6 pattern; LCFR + 95%-pruning
  identical to Python tier. Gated by `tests/test_3p_diff.py` (Python
  ↔ Rust strategy L1 < 1e-6 after 500 iterations on tiny 3p river
  subgame — tighter than HU 5e-3 cluster; small-fixture justified
  per spec §14).

New tests:
- tests/test_3p_core.py (~15 tests): game-state invariants — side-pot
  5 TDA fixtures, action turn advancement with fold/all-in skip,
  3-way showdown evaluation (multi-winner per side pot),
  fold-then-2-handed-continuation correctness, N-player turn rotation
  SB→BB→BTN, `num_players >= 4` NotImplementedError.
- tests/test_3p_solve.py (~10 tests): convergence smoke,
  stability diagnostic determinism, per-pair BR gap structure (joint
  vs individual), iteratively-strict-dominated-action-vanishes
  (Gibson 2013), zero-sum game-value invariant, intuition gauntlet
  (3-way BB defense narrower than HU; multi-way wet-flop SB checkdown
  freq higher than HU; multi-way bluff freq lower than HU). Slow
  variants `@pytest.mark.slow`. MonkerSolver cross-validation
  `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`.
- tests/test_3p_diff.py (~3 tests): Python ↔ Rust differential on
  tiny 3p river subgame. Tolerance LOCKED at L1 < 1e-6 (NOT silently
  relaxed; spec §14 + audit focus 13).
- tests/fixtures/multiway_fixtures.py: 3p river-only deterministic
  (~1k infosets), 3p flop tight abstraction (~10^5 infosets), 3p
  turn (~few×10^4 infosets).
- tests/test_badge_unsuppressible.py: string-literal audit asserts
  badge text appears in CLI stdout / UI / JSON for every 3p result;
  asserts NO `--suppress-badge` / `--quiet-approximate` /
  `verbose=False`-conditioned-skip path exists.

Modified (ui/):
- ui/views/range_matrix.py: approximate-equilibrium badge per §6.3
  rendered for `num_players >= 3` results. Three side-by-side
  mini-matrices instead of one for 3p display.
- ui/views/run_panel.py: `num_players` toggle (2 / 3); third range
  input panel for 3p; per-pair BR gaps display (three numbers,
  labeled as upper bounds NOT exploitability); stability diagnostic
  display.
- ui/views/library_browser.py: "3-handed (approximate)" row badge
  for `spot_json.config.num_players == 3`.

Out of scope (per spec §2): 3-handed preflop (astronomically larger;
out of v1 entirely), 4+ player (16 GB MacBook ruled out per Pluribus
hardware footprint), Nash-equilibrium claims (LOAD-BEARING; no string
"Nash"/"GTO"/"optimal" appears in 3p code paths), exploitability-as-
Nash-distance (3 per-pair BR gaps NOT a Nash metric), real-time
depth-limited search (Pluribus k=4 continuations — v2 candidate),
tournament/ICM-aware solving, new card abstraction (PR 4 reused),
new DCFR variants (LCFR per Pluribus), rake (unchanged from PR 3/5/9),
node locking (Phase-4), Pio parity (Pio is HU-only), PR 12.5 3p
preflop / real-time search.

Verification:
- cargo build --release --package cfr_core: clean.
- cargo test --package cfr_core --all-targets: all Rust tests pass
  (PR 1-11 existing + new multiway.rs tests via PyO3 boundary in
  test_3p_diff.py).
- cargo clippy --package cfr_core --all-targets -- -D warnings: clean.
- pytest -m "not slow and not very_slow" --tb=line: all pass / skip.
  PR 1-11 regression: all green (N=2 path unchanged; spec §9 #6).
- pytest tests/test_3p_*.py: ~30 new tests + slow variants pass.
- ruff check + black --check + mypy --strict on
  `multiway_solver.py`, `hunl.py`, `action_abstraction.py`,
  `solver.py`, `cli.py`: clean.
- String-literal audit (spec §9 #4): `grep -ri 'exploitability|nash|
  GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs
  tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v
  'best-response|approximate|≈|near-Nash'` returns EMPTY.
- Stability diagnostic on river-only fixture: pairwise L1 < 0.05
  across seeds 0/1/2 (soft assertion; failure → "⚠ stability
  degraded" badge).
- Differential test passes at L1 < 1e-6.
- check_pr.sh license audit clean; no new third-party deps; no AGPL
  code from postflop-solver / TexasSolver for multi-player logic.
- Manual CLI smoke: `poker-solver solve --game hunl --num-players 3
  --board "As 7c 2d Kh 5s" --stacks 100,100,100 --abstraction
  tests/fixtures/3p_tiny_abstraction.npz --iterations 1000` runs to
  completion, prints strategy table with "≈ approximate equilibrium"
  banner and three per-pair BR gaps. `--num-players 4` raises clear
  NotImplementedError.

License compliance: zero AGPL code. Every new .rs file ships
attribution per PR 6 §3 template:
- multiway.rs cites `poker_solver/multiway_solver.py` (project-internal,
  MIT) for semantics; Pluribus paper cited from references/papers/
  for LCFR + 95%-pruning recipe; Gibson 2013 cited from
  references/papers/ for IDSD theorem (with explicit "NOT Nash
  convergence" qualifier — overclaim must-fix per audit focus 15).
- Explicit "NEVER copy from references/code/postflop-solver (AGPL) or
  references/code/TexasSolver (AGPL) for multi-player logic" disclaimer.
- check_pr.sh license audit clean; MonkerSolver data NOT bundled
  (license; opt-in user-supplied per §7.5).

Branch: pr-12-three-handed-stretch (off integration tip AFTER ALL of
PR 1-11 land on main AND v1 is tagged AND user explicitly approves
launch per fanout_ready.md §0). 6-12 week estimate per spec §11;
longest single PR in v1 roadmap by 2-3× over PR 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
