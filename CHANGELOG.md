# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

In-flight on feature branches; not yet merged to `main`.

### In progress
- v1.5/v2 follow-ups (Q3 exploitability slider reframe; range-based
  dealing; Rust callbacks; full-tree preflop).

## [1.7.0] - 2026-05-23

### Added

- `solve_range_vs_range_nash` direct API for joint range Nash equilibrium (PR 43)
  - Routes through the Rust vector-form CFR; distinct from the aggregator
    pattern's per-combo blueprint approach
  - 12 tests including W3.5-style monotone polarization validation
- CLI subcommands (PR 39):
  - `poker-solver pushfold` — preflop push/fold chart lookup
  - `poker-solver river` — river-only solve
  - `poker-solver parity` — Brown reference parity comparison

### Status

- v1.6.1 engine bundle: HELD pending acceptance gate redefinition
  (deep-cap Brown apples-to-apples reveals architectural divergence
  in payoff convention; see docs/v1_6_1_no_go_synthesis*)
- PR 44 .dmg packaging fix: VERIFIED on disk; ready for Gate 5 attachment

## [1.6.0] - 2026-05-23

### Added — GUI Gate 2 (UI completeness)
- **Range-vs-range solve panel** (PR 24a) — visual RvR mode with hero_player selector
- **4-tier exploitability slider** (PR 24a) — Draft/Standard/Tight/Library at measured 200/500/1000/2000 iters
- **Node-locking editor** (PR 24b) — per-action sliders + lock indicators + tree-browser hook + run-panel locked-strategies expansion
- **Asymmetric initial_contributions UI** (PR 24b) — facing-bet scenario input via `pot_so_far_bb` + `villain_bet_bb` + `bettor_is_p0`
- **Range editor polish** (PR 24b) — per-combo frequency dialog (right-click) + chart preset library (4 built-in presets shipped)
- **"True Nash" vs "blueprint" chart labels** (PR 24a) — honest framing of solve quality
- **44 new UI smoke tests** total (7 from PR 24a + 9 from PR 24b)

### Notes
- Engine bundle (PR 33+34+35 for true Brown parity) still deferred to v1.5.2 pending per-action divergence diagnosis
- GUI is functionally complete for Gate 2; awaiting engine acceptance test PASS before final persona retest sweep
- Per `feedback_ui_packaging_sync`: this ship triggers PR 11 .dmg rebuild (LEG 19 candidate) + PR 10b UI re-audit downstream

## [1.5.1] - 2026-05-23

### Added
- **Equity test helper** (`tests/_equity_helpers.py`): rigorous
  exact-enumeration wrapper exposing `equity_of`, `equity_vs_range`,
  and `assert_equity_close` for use in persona acceptance tests.
  Re-exported via `tests/conftest.py`. Prevents hand-waved equity
  estimates from passing review (PR 37). NO source-code change;
  tests/conftest scaffolding only.
- **Memory profiler test rigor** (`tests/test_memory_profiler.py`):
  4 new tests upgrade the return-non-empty-without-crashing baseline
  to genuine external oracles: closed-form 3-action x 4-infoset toy
  fixture, real-config closed-form calibration on a small river solve,
  golden-file check, and structure-invariant check on per-street
  partitioning (PR 36). NO source-code change; tests-only.

### Changed
- **Docs honesty** in `tests/test_river_diff_self_sanity.py`: replaced
  the aspirational "<10s/spot on a typical dev box" comment (PR 7 /
  v0.5.1, never empirically validated) with a rigorous framing that
  references the river-parity timeout investigation
  (`docs/river_parity_timeout_investigation_2026-05-23.md`) — the
  canonical parity test takes >660s on the Python tier due to
  chance-enum-at-root (1.6M hole-card combos per iter); the test was
  marked `@pytest.mark.slow` in v1.4.2; a full runtime fix awaits
  vector-form CFR (v1.5.0+) (PR 32). Docs-only edit; no assertion or
  test-behavior change.

### Deferred to v1.6.1
- **Engine bundle** (PR 33 Python delegate + PR 34 off-by-one fix +
  PR 35 canonicalization + caveats) is HELD pending per-action
  divergence diagnosis on the v1.5.0 acceptance test. v1.5.1 ships
  docs/test rigor improvements WITHOUT engine changes; the empirical
  Brown apples-to-apples claim remains v1.6.1's gating responsibility
  (engine bundle ships after v1.6.0 GUI per LEG 18 sequencing).

### Honest scope
- PATCH bump: test infrastructure + comment edit. NO public API
  change, NO behavior change, NO Rust source change, NO `poker_solver/`
  source change.
- v1.5.0 `_rust.cpython-313-darwin.so` is reused byte-identically
  (no Rust rebuild). The shipped wheel reuses the v1.5.0 compiled
  binding.
- v1.5.0 acceptance-test status is unchanged. This release does NOT
  address the per-action divergence observed in the v1.5.0 Brown
  apples-to-apples acceptance test.
- Smoke regression: `test_equity_helpers.py`,
  `test_memory_profiler.py`, `test_range.py`, `test_dcfr_diff.py`,
  `test_exploit_diff.py`, `test_range_vs_range_aggregator.py`,
  `test_node_locking.py` — all 91 green (5 skipped, expected).

## [1.5.0] - 2026-05-23

### Added — Vector-form CFR + Brown apples-to-apples acceptance (PR 23 + PR 28)

- New `crates/cfr_core/src/dcfr_vector.rs` module implementing vector-form
  DCFR — per-infoset `hand_count × action_count` regret + strategy_sum
  tables, betting tree walked once per iteration, alternating player
  updates per Brown's `Trainer::run` pattern. Direct structural port of
  `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`
  (MIT, attributed in code comments).
- New `Game::hand_count(&self) -> usize` trait method, default `1` for
  backward compatibility. Vector-form DCFR opt-in via the new top-level
  entrypoint; existing Kuhn / Leduc / fixed-combo HUNL still go through
  the scalar `dcfr.rs::DCFRSolver<G>` byte-identically.
- New PyO3 entry `_rust.solve_range_vs_range_rust(config_json, iters,
  alpha, beta, gamma, p0_holes=None, p1_holes=None) -> dict`. Output
  dict shape matches Python tier (`average_strategy: dict[str,
  list[float]]` with lossless `<hole>|<board>|<street>|<history>` keys),
  plus `decision_node_count`, `iterations`, `wallclock_seconds`,
  `hand_count_per_player`, `memory_profile`, `backend = "rust_vector"`.
- Per-street memory profiler (`VectorMemoryProfile`) surfaced in the
  PyO3 dict's `memory_profile` field with `total_bytes`, `infoset_count`,
  `bytes_by_street`, `infoset_count_by_street`.
- v1.5.0 scope: postflop only (`Street::Flop` / `Turn` / `River`); preflop
  RvR deferred to v1.5.1 per spec §8 Q2 (16 GB memory edge at
  full-1326 hand vector without suit-iso reduction). EMD bucketing in
  the hand dimension also deferred to v1.5.1.
- New tests in `tests/test_range_vs_range_rust_diff.py` (4 active, 1
  skipped): exploitability-convergence diff against Python `dcfr.py`
  on a restricted-range test harness, structural smoke check, and
  end-to-end binding chain verification. Spec §5's per-row tolerance
  metric was replaced with exploitability-under-restricted-game because
  RvR Nash strategies are non-unique in mixed form when hands are
  indifferent; both Python and Rust achieve <= 0.05 BB exploitability
  on the Case A spot.

### Added — Brown apples-to-apples acceptance test (PR 28)

- New `tests/test_v1_5_brown_apples_to_apples.py` (574 LOC) — opt-in
  via `-m parity_noambrown` — runs Brown's `river_solver_optimized`
  reference binary and the new Rust vector-form CFR on the same two
  test spots (`dry_K72_rainbow`, `dry_A83_rainbow`), compares average
  strategies at matching histories, and asserts <= 5e-3 strategy diff
  on >= 80% of histories. Gracefully skips when Brown's binary has not
  been built locally (CI default).

### Unchanged

- All existing scalar paths (`dcfr.rs::DCFRSolver`, `hunl_solver.rs`,
  `preflop.rs`) byte-identical to v1.4.0. 40 existing diff tests
  (Kuhn / Leduc / fixed-combo river / exploit / node-locking) green.

### Deferred to v1.5.1+

- Wire `range_aggregator.solve_range_vs_range` to use the new Rust tier
  (Q3 default for v1.5.0).
- UI surfacing (v1.5.0 is internal-only per the documented Q4 default;
  user-facing UI integration deferred to a later minor).
- SIMD kernels for vector-shape arithmetic (expected 4-8x speedup based
  on PR 8 NEON-on-scalar experience).
- Preflop RvR with suit-iso reduction.

## [1.4.3] - 2026-05-23

### Fixed — HUNLConfig input-validation hardening (PR 31)

- `HUNLConfig.__post_init__` now raises `TypeError`/`ValueError` early
  on malformed inputs rather than allowing garbage to propagate to the
  Rust backend and crash deep in the solver. Loud failure at the
  Python/Rust boundary instead of silent corruption.
- Builds on the v1.4.1 validation foundation (PR 22 already added
  `ValueError` on negative contributions and over-stack contributions);
  PR 31 extends to type-level guards on contribution tuple shape,
  scalar types (`starting_stack`, `big_blind`, `small_blind`, `ante`,
  `initial_pot`), bet-size-fraction containers, and rejects `bool`
  values where `int` fields are expected.
- Tests: 28 new cases in `tests/test_hunl_config_validation.py`
  covering the expanded guard surface, plus 2 regression tests
  confirming the PR 22 negative-contribution and over-stack
  contribution checks still fire.

### Added — `Range.diff()` set-difference utility (PR 27)

- New `Range.diff(other)` method on `poker_solver.range.Range`
  returning a new `Range` containing combos in `self` but not in
  `other`. Directional set-difference semantics
  (`a.diff(b) != b.diff(a)` when ranges overlap partially);
  non-mutating on `self`; returns empty Range when `other` is a
  superset.
- Implementation is equivalent to frequency-aware
  `max(self.freq - other.freq, 0)` under the current Range invariant
  (all stored frequencies are 1.0). Docstring flags the freq-dict
  extension point for when per-combo fractional frequencies are added
  (task #189).
- Unblocks the W2.2 (Sarah) categorical-leak-slice workflow at the
  set-membership level — finding combos present in BB's defending
  range but missing from a candidate exploit response.
  Fractional-frequency exemplars remain out of scope pending Range
  refactor.
- Tests: 8 new cases in `tests/test_range.py` covering empty/self/
  superset/disjoint diffs, directionality, partial overlap,
  non-mutation of `self`, and boolean set-like behavior. All 22
  `test_range.py` tests pass.

### Documentation — USAGE.md + DEVELOPER.md refresh (PR 30)

- **`USAGE.md` refresh.** Updated to reflect v1.4.x capabilities
  (node-locking §5.3, asymmetric contributions §5.4, Range utilities
  including the new `Range.diff()` §5.5), known CLI ergonomics gaps
  (§7a: pushfold subcommand, exploit-target positional convention,
  batch-solve CSV quoting), and observed performance cliffs (§7b:
  range-vs-range walk vs. Rust port path).
- **`DEVELOPER.md` refresh.** Two-tier (Python `solve_hunl_postflop`
  chance-enum-at-root vs. Rust `solve_range_vs_range_rust` vector-form
  CFR) honesty framing, action-abstraction notes
  (`ActionAbstractionConfig` defaults; library round-trip behavior
  including `exploitability_history` truncation), and operational
  notes for contributors (single-worker batch-solve recommendation).

### Honest scope

- PATCH bump: input-validation hardening + additive utility + docs
  refresh. No public API breakage, no behavior change to existing
  call sites, no Rust source changes.
- v1.4.2 `_rust.cpython-313-darwin.so` is byte-identical for this
  release (no Rust rebuild required); the shipped binding reuses the
  v1.4.2 compile output.
- Smoke regression: `test_range.py` (22 tests) and
  `test_hunl_config_validation.py` (28 tests) all green.
- No new persona workflow structurally unblocked beyond v1.4.1; PR 27
  enables the W2.2 categorical-leak-slice workflow at the
  set-membership level (utility-level convenience).

## [1.4.2] - 2026-05-23

### Fixed — Docs honesty + test marker

- `poker_solver/range_aggregator.py`: the `hero_player` parameter
  docstring and the module-level docstring both described P0 as the
  player making the "first postflop decision," which is backwards.
  In HUNL, slot 0 is the SB seat (button) — first to act PREFLOP, last
  to act POSTFLOP. Slot 1 is the BB seat — last to act PREFLOP, first
  to act POSTFLOP. Both docstrings now state the position semantics
  correctly and include a note on the BB-defending workflow
  (`hero_player=1` AND `hero_range=bb_range` so the BB cards land in
  the BB seat).
- `tests/test_river_parity_vs_brown.py::test_river_parity_vs_brown`
  now carries `@pytest.mark.slow` so it is excluded from the default
  CI suite (which runs `-m 'not slow'`) and only executes when
  developers explicitly opt in. Formalizes the opt-in posture that
  was already implicit in CI config.

### Honest framing

- v1.4.2 PATCH: no API or behavior changes. Docs say what the code
  has always done; the slow-test marker formalizes existing opt-in
  posture. Safe drop-in upgrade.

## [1.4.1] - 2026-05-23

### Fixed — Asymmetric initial-contributions (PR 22)

- `HUNLPoker.initial_state` (and the Rust mirror in
  `crates/cfr_core/src/hunl.rs`) now honors asymmetric
  `initial_contributions` for postflop subgames. Previously the
  postflop branch hardcoded `to_call=0`, `street_aggressor=-1`, and
  `cur_player=1` regardless of contribution asymmetry, so passing
  `initial_contributions=(1000, 500)` to model "P0 bet half-pot, P1
  faces the c-bet" silently produced an opening-strategy state instead
  of a facing-bet state (spec: `docs/pr_proposals/v1_4_asymmetric_contributions.md`).
- With the fix, `(1000, 500)` yields `to_call=500`, `cur_player=1`
  (BB faces the bet), `street_aggressor=0` (SB put more in). Symmetric
  `(c, c)` continues to yield `to_call=0`, `cur_player=1`,
  `street_aggressor=-1`, `street_num_raises=0` — bit-identical to
  v1.4.0 behavior, locked by a regression test.
- `HUNLConfig.__post_init__` now raises `ValueError` on negative
  contributions and on a contribution exceeding `starting_stack`,
  rather than letting the Rust backend reach a segfault path (the
  segfault was first observed in `docs/pr13_prep/v1_3_1_s4_retest.md`).
- Engine fix in `_apply_player`: when an over-shove all-in is "called"
  by an opponent who is already all-in for less, the excess (uncalled)
  chips are now refunded to the over-shover and the street closes
  rather than tripping an assertion in `enumerate_legal_actions`. This
  is a latent engine bug made reachable by the asymmetric-contribution
  facing-bet branch (spec §7 "expect 0-2 such bugs during Fix A").
- New `tests/test_asymmetric_contributions.py` (13 tests) covers
  symmetric regression, P0/P1 facing-bet asymmetry, fold-loss
  accounting, ValueError on every invalid-config flavor, and the
  `default_tiny_subgame` fixture invariance.

### Persona workflows unblocked (3 of the documented set)

- W3.4 (Daniel) — BB-defends-vs-half-pot-c-bet MDF check: facing-bet
  subgames now compose, so the aggregator returns a fold/call/raise
  strategy rather than the v1.4.0 100%-opening artifact.
- W2.3 (Sarah) — "KK on Q-high vs c-bet range."
- W1.2 (Marcus) — Bluff-catcher MDF on river vs pot-sized bet.

### Honest framing

- v1.4.1 PATCH (not MINOR): the public API surface is unchanged —
  `HUNLConfig` already accepted `initial_contributions`; the fix is
  that the engine now interprets asymmetric values correctly. No
  caller code that worked on v1.4.0 needs to change.
- The Fix B `ValueError`s are stricter than v1.4.0 (which accepted
  some invalid configs silently and either ignored them or segfaulted
  on solve). Callers that relied on the silent-accept path will now
  get an early, clear error.
## [1.4.0] - 2026-05-23

### Added — Node locking (marquee feature; PR 21)

- New optional `locked_strategies: dict[str, list[float]] | None` kwarg on
  `solve()`, `solve_hunl_postflop()`, and `solve_hunl_preflop()`. Pins a
  player's strategy at one or more infosets to a fixed probability
  distribution over its legal actions; the unlocked side updates against
  the locked strategy as if it were part of the game's structure (spec:
  `docs/pr_proposals/v1_4_node_locking.md`, §2.2).
- Threading through both Python (`poker_solver/dcfr.py`) and Rust
  (`crates/cfr_core/src/{dcfr,hunl_solver,preflop,solver}.rs`) DCFR
  loops. PyO3 binding marshals `Option<HashMap<String, Vec<f64>>>`.
- Bit-identical passthrough: `result.average_strategy[locked_key]` returns
  the supplied lock vector verbatim (spec §3.3).
- Lazy validation on first visit: length-mismatch, negative entries, and
  non-normalized vectors each raise `ValueError` with remediation text.
- Frozen lock map via `MappingProxyType` to prevent mid-solve mutation
  (spec §Appendix #1).
- Push/fold conflict: locks under ≤15 BB HUNL preflop raise `ValueError`
  pointing at `force_tree_solve=True` (spec §Appendix #3); the chart is
  non-trainable so silent passthrough would mislead.
- New tests in `tests/test_node_locking.py` (19 tests) covering:
  empty-lock equivalence, passthrough on both tiers, validation paths,
  cross-tier diff under `[empty, one-key, ten-key]` lock configurations,
  EV monotonicity, best-response heuristic (Daniel persona workflow),
  push/fold conflict, frozen mapping check, and per-iteration overhead.

### Daniel persona workflows unblocked (4 of 5)

- W3.1 / W-DL-01 — Villain never bluffs rivers (lock bet → 0 at bluff-blocked
  river infosets).
- W3.2 / W-DL-02 — GTO-vs-actual EV comparison (lock villain's preflop call
  frequency to a leaky 60%).
- W3.3 / W-DL-03 — Merged range / villain donk-leads small only with draws.
- W-DL-04 — Hero's preferred line (lock hero, ask villain BR — inverse).
- W3.4 / MDF half-pot — queued for v1.4.1 via PR 22 (asymmetric
  initial-contributions); not in this ship.
- W-DL-05 (multi-street tree visualizer) remains GUI-only, deferred to
  v1.4.1 GUI polish.

### Honest framing

- Still a per-combo solve (the engine's infoset key already embeds hole
  cards, so per-hand locking IS per-infoset locking; no range-vector
  representation borrowed from postflop-solver).
- The best-response API (a standalone `best_response()` function returning
  a strategy + EV against a fixed opponent) is NOT included; node-lock +
  re-solve gives equivalent capability (lock the villain, the unlocked
  hero converges to the BR). Deferred per user 2026-05-23.
- Convergence under one-sided locking is single-agent regret minimization
  against a fixed environment — provably correct semantics, but the DCFR
  α=1.5/β=0/γ=2.0 schedule was tuned for two-sided play; observed
  exploitability decay may be slightly softer. Caveat documented in
  `SolveResult.exploitability_history` semantics (represents the unlocked
  side's regret only).
- This is the v1.4.0 ship per the stagger-fallback path in
  `docs/leg9_v1_4_0_ship_plan.md`. PR 22 (asymmetric initial-contributions,
  unblocks W3.4 MDF queries) is queued for v1.4.1; it would compound MDF
  use cases.

### Performance

- Measured Rust-tier overhead on Leduc with 28-of-288 lock keys (≈10% of
  infosets): 1.6% vs unlocked (target: <10% per spec A4).

### Resolves

- v1.4.0 marquee feature ship; Daniel persona W3.1 / W3.2 / W3.3 workflows
  unblocked. Per the persona acceptance discipline (integration sequencing
  §6.5), W3.1 / W3.2 / W3.3 will be re-tested post-ship to confirm the
  loop closes.

## [1.3.2] - 2026-05-23

### Added — Rust port of exploitability + game-value walks (PR 15 / Option A)

- New crate module `crates/cfr_core/src/exploit.rs` (1173 LOC): Rust-tier
  exploitability and game-value walks; replaces the Python recursive walk
  that was the W1.5 timeout bottleneck.
- New PyO3 binding `compute_exploitability` in `crates/cfr_core/src/lib.rs`
- `poker_solver/solver.py` wires `_solve_rust` to call the Rust walk for
  HUNL postflop; `_compute_exploitability_rust` helper exposes the Rust path.

### Performance (measured, not extrapolated)

- W1.5 bench (turn subgame, chance-enum-at-root river): >10 min (killed at
  3 min hard timeout pre-fix) -> **26.43 seconds end-to-end** post-fix
  (25.96s on the post-cherry-pick re-verification).
- Beats Plan C's <30s aspirational target; massively beats Option A's 60s gate.
- PioSolver-class for standard-precision postflop solves.

### Tests

- 5 new Python diff tests (`tests/test_exploit_diff.py`): Python <-> Rust expl
  walks bit-exact within 1e-6 BB/hand on fixed-combo, chance-enum, push/fold
  short-circuit, and Kuhn/Leduc parity.
- All existing tests (PR 6/7/9/Option B) stay GREEN.

### What this does NOT ship (honest disclosure)

- Rust DCFR solver still doesn't solve when `initial_hole_cards = ()`
  (chance-enum-at-root is a 32-bit packed action that doesn't fit u8).
  The Rust expl WALK handles the post-solve metric correctly; the full
  RvR CFR solver remains a post-v1 follow-up. End-to-end timing reflects
  this: DCFR returns immediately with empty strategy; the 26.43s is the
  expl walk alone.
- Plan C dense-slabs + vectorized showdown: parked on `pr-17-plan-c-dense-slabs`
  branch for potential future v2.0 enhancement.

### Closes the test->fix->retest loop

- Original blocker: Phase 1 W1.5 (turn subgame range-vs-range expl walk
  timeout @ 15 min) classified as Type C-CRITICAL.
- This release resolves W1.5 perf gate; re-test post-ship.

## [1.3.1] - 2026-05-23

PATCH bump on top of v1.3.0. Two narrow fixes to the range-vs-range
aggregator's API surface plus honest USAGE caveats. No behavior change
for any v1.3.0 caller that did not opt into the new parameter; no
engine changes; no Rust changes.

Caught by the Option B pre-ship stress test
(`docs/pr16_prep/stress_test_results.md`): S4 MDF query returned 100%
check on a half-pot bluff-catcher spot; S1 K-high turn showed AA and
KK both checking 99.99% — heuristic FAIL traced to position
misclassification (the aggregator hardcoded `hero_player=0` and the
extraction walker silently passed through P1's modal action before
grabbing P0's frequencies on no-history defending spots).

### Fixed

- **`solve_range_vs_range` hero_player gap.** Added a
  `hero_player: int = 0` keyword parameter to
  `poker_solver.range_aggregator.solve_range_vs_range`. v1.3.0
  hardcoded the engine-slot-0 (aggressor) seat and silently returned
  ~100% check for defender-side queries (MDF / calling-frequency).
  v1.3.1 threads `hero_player` through `_run_one_subgame` (which
  places hero's combo at the requested engine slot) and
  `_extract_first_decision_freqs` (which extracts that slot's first
  decision). Default behavior is unchanged: omitting the kwarg gives
  the v1.3.0 aggressor extraction. New value `hero_player=1` places
  hero at engine slot 1 (postflop OOP / first-to-act) and returns
  P1's first-decision frequencies. Invalid values (anything not 0 or
  1) raise `ValueError`.

### Added

- **`RangeVsRangeResult.position` field.** New string field on the
  result dataclass; `"aggressor"` when `hero_player == 0`,
  `"defender"` when `hero_player == 1`. Disambiguates the
  per-class-strategy and range-aggregate dicts: with the matched-pot
  postflop setups in the smoke suite the dict mixes `"check"` /
  `"bet_*"` (aggressor side) vs `"fold"` / `"call"` / `"raise_*"`
  (defender side, when contributions are unmatched). The new field
  lets callers label outputs correctly without inspecting the
  underlying config.

### Tests

- **+3 new tests** in `tests/test_range_vs_range_aggregator.py` (21
  total, was 18):
  - `test_hero_player_1_defender_extraction` — solves an AA-on-K-high
    turn spot with `hero_player=1` and asserts the non-check mass is
    > 30% (rejecting the v1.3.0 "silent ~100% check" failure mode).
  - `test_hero_player_invalid_raises` — `hero_player=2` raises a
    `ValueError` mentioning the parameter name.
  - `test_position_field_default_aggressor` — backward-compat sanity
    check that the v1.3.0 default kwarg path sets
    `position == "aggressor"`.
- All 18 existing tests pass unchanged; the differential parity test
  (`test_per_hand_solve_matches_standalone_solve`) continues to pass
  because it omits `hero_player` and falls through to the
  v1.3.0-equivalent default.

### Docs

- **`USAGE.md` §5.2** — new subsection covering the
  `solve_range_vs_range` API, the v1.3.1 `hero_player` parameter, the
  `position` result field, and an honest perf caveat: 100 BB
  flop-start at full lossless tree size exceeds the 30 s per-solve
  budget (146 s observed on a minimal AA-vs-QQ flop solve during the
  pre-ship stress test); turn-start is the currently-recommended
  path until the Rust exploitability port (Option A) lands. Stress
  test findings cited as the discovery point.
- **`docs/pr16_prep/stress_test_results.md`** — already in the repo
  from the v1.3.0 ship audit; cited from the CHANGELOG and USAGE.

### Stress-test reproduction after fix

The v1.3.1 patch was validated by re-running the S1 K-high turn
heuristic at reduced scale (3 bet sizes instead of 6, 2 hero classes
instead of 5) under both `hero_player=0` and `hero_player=1`:

```
Setup: TURN As-Ks-7h-4d, stack 9750, pot 500, contributions (250, 250),
       bet_size_fractions=(0.5, 0.75, 1.5), villain_reps=1, 200 iters

hero_player=0 (aggressor / v1.3.0 default; hero = SB / IP):
  AA: bet_50=0.0000  bet_75=0.0000  bet_150=0.0000  check=0.9999
  KK: bet_50=0.0000  bet_75=0.0000  bet_150=0.0000  check=0.9999
  → Matches v1.3.0 S1 finding: AA/KK both ~99.99% check. The walker
    steps past P1's (BB's) modal check, P0 (SB / IP) sees no bet to
    face, and the 1v1 equilibrium has SB checking back AA/QQ.

hero_player=1 (defender / new in v1.3.1; hero = BB / OOP):
  AA: bet_50=0.4970  bet_75=0.3570  bet_150=0.0000  check=0.1461
  KK: bet_50=0.4970  bet_75=0.3570  bet_150=0.0000  check=0.1461
  → AA/KK bet ~85% combined as a donk-lead from the BB / OOP seat.
    The walker extracts slot-1's first decision directly (no more
    walking-past-villain-modal-check); the engine assigns most of
    AA/KK's mass to the bet actions.
```

What the fix does NOT do: it does NOT recover a "preflop-aggressor
c-bets K-high" heuristic. The 1v1 collapse + per-hand subgame
structure documented in `range_aggregator.py:19-32` is unchanged. Both
`hero_player=0` and `hero_player=1` are valid engine-seat extractions,
but neither corresponds exactly to the preflop-aggressor c-bet that
S1's heuristic was checking. `hero_player=1` returns the BB's
donk-lead frequency; `hero_player=0` returns the SB's response after
the BB's modal action. Picking the "right" one depends on which
real-world question the caller is asking; the new `position` field
plus this CHANGELOG entry document the disambiguation.

The S4 MDF heuristic (defending after villain's lead) remains
unaddressed even with `hero_player=1` — see "Honest framing" below.

### Honest framing

- The `hero_player=1` path returns hero's FIRST decision frequencies
  at engine slot 1, NOT a true Nash defending mix vs villain's lead.
  Because the engine's `initial_state` always seats slot 1 first
  postflop, "defending after villain's lead" would require either
  unmatched `initial_contributions` (so the to-act player faces a
  bet) or a deeper walker that drives through hero's check and
  villain's response. v1.3.1 does NOT extend the walker; it only
  exposes the engine-slot choice and adds the result field.
- The S4 MDF bluff-catcher spot (`hero_player=1` on a no-history
  river) STILL returns ~100% check after the fix — the engine
  reports P1's first decision as ~100% check, which is mechanically
  correct for "no bet to face, fold not legal, check vs lead choice
  collapses to check at 200 iters." MDF queries proper require the
  unmatched-contributions setup or the deeper walker. Both are
  follow-up work, not in scope for v1.3.1.

### Internal

- `__version__` bumped to `1.3.1` (PATCH).
- `pyproject.toml` `version` bumped to `1.3.1`.
- No Rust changes; the prebuilt `_rust.so` carries over unchanged.

## [1.3.0] - 2026-05-23

### Added — Range-vs-range API (Option B: blueprint aggregator)

- New public function `solve_range_vs_range(config_template, hero_range, villain_range, iterations, backend)` in `poker_solver/range_aggregator.py` (~450 lines)
- Per-hand-class strategy outputs: `result.per_class_strategy["AA"] → {"bet_75": 1.0, "check": 0.0}`
- Combo-weighted range aggregate output for range-level frequencies (MDF, polarization, sizing distributions)
- Combo expansion: "AA" → 6 combos, "AKs" → 4, "AKo" → 12; board-blocked combos filtered
- 18 new tests in tests/test_range_vs_range_aggregator.py

### Performance (measured)

- 6×5 range query (turn-start, 200 iters): 23.9 s
- 10×10 range query: 79.2 s
- Per-hand subgame: 1-3 seconds (Rust backend)

### Honest framing

This is a WORKAROUND pattern (Pluribus blueprint), not Nash range-vs-range:
- Each per-hand solve is 1-vs-1 with the engine's existing dispatcher
- Aggregation is uniform across representative villain combos
- True Nash range-vs-range with full-tree co-dependent strategies awaits future work
- Documented in module docstring + test docstrings + USAGE.md

### What's NOT in this release

- Flop-start at 100 BB lossless is still slow (10-100s per solve at the engine layer, not aggregator)
- Option A (Rust port of exploitability walk) deferred (may follow as v1.3.1 if it lands)
- True Nash range-vs-range solving (post-v1)
- Suit-aware aggregation (v1.4+ work)

### Resolves

- Phase 1E W1E.2/W1E.3/W1E.4 (range-level workflows previously timed out)
- Phase 1 W1.5 (single-spot range solve previously timed out at 15 min)
- Phase 2 W2.3/W2.6 (range-level methodology gaps from preflop testing)
- All previously documented as Type C-CRITICAL per persona acceptance rectification framework

## [1.2.1] - 2026-05-23

Patch release: build the Rust `_rust.cpython-313-darwin.so` as a
**universal2** (arm64 + x86_64 lipo'd) binary so the v1.2.x macOS
artifact loads under both Apple Silicon Python and x86_64 Python
(e.g., pyenv-managed). Phase 1 persona test W1.4 caught `ImportError:
incompatible architecture (have 'arm64', need 'x86_64')` when
`poker-solver --backend rust` was invoked from x86_64 Python against
the v1.2.0 arm64-only .so. PATCH bump: no public-API change; ships a
new artifact `Poker-Solver-1.2.1-universal2.dmg` superseding
`Poker-Solver-1.2.0-arm64.dmg`.

### Fixed

- **`scripts/build_macos_dmg.sh`** pre-flight now rejects a
  single-arch `_rust.so` and instructs the operator to rebuild via
  `maturin develop --release --target universal2-apple-darwin`. DMG
  filename changes from `Poker-Solver-${VERSION}-arm64.dmg` to
  `Poker-Solver-${VERSION}-universal2.dmg` to reflect the broadened
  arch coverage.
- **`docs/pr11_prep/leg4_repackage_now.md`** repackage runbook
  documents the universal2 build step + a Step 1.5 verification that
  the resulting .so reports both `arm64` and `x86_64` slices via
  `file(1)`. Prerequisites add `rustup target add x86_64-apple-darwin
  aarch64-apple-darwin` (one-time).
- **`pyproject.toml`** `[tool.maturin]` section documents the
  universal2 requirement (maturin does not accept `target` as a
  pyproject field; CLI-only).

### Tests

- Local universal2 wheel build via `maturin build --release --target
  universal2-apple-darwin -m crates/cfr_core/Cargo.toml` confirmed to
  produce `Mach-O universal binary with 2 architectures: [x86_64:...]
  [arm64:...]` per `file(1)`.

### Affects

- `ui+package` (packaging change; UI is downstream consumer of the
  bundled .so).

## [1.2.0] - 2026-05-23

PR 10b: replaces the PR 10a mock solver layer with **real-solver UI
bindings**. The NiceGUI UI's `SolveRunner` now dispatches to the real
engine via the canonical `solve()` ladder — push/fold short-circuit
(≤15 BB) → HUNL postflop (`solve_hunl_postflop`) → HUNL preflop
(`solve_hunl_preflop`). The yellow "Mock mode" banner is removed; the
GUI now drives the same engine the CLI does. MINOR bump: replaces an
internal UI-only seam (`ui/mock_solver.py` → real-solver imports)
with no public-API change to `poker_solver` and zero behavior change
to PRs 1-9. First complete v1.x release where the downloadable
artifact (v1.0.0 .dmg) is superseded by a real-solver build (LEG 4
.dmg repackage).

### Changed

- **`ui/state.py`** `SolveRunner` swaps the PR 10a `mock_solve`
  import for the real solver entry points. Routing logic mirrors
  `poker_solver.solver.solve` dispatch order: short-stack push/fold
  → HUNL postflop solve → HUNL preflop solve. UI receives real
  `HUNLSolveResult` objects with real `MemoryReport`, real game
  values, and real exploitability traces.
- **`poker_solver/preflop.py`** — `solve_hunl_preflop(...)` accepts
  `on_progress: Callable[[ProgressEvent], None] | None = None` and
  `should_stop: Callable[[], bool] | None = None` kwargs (the same
  contract PR 5's `solve_hunl_postflop` already exposed). Callbacks
  are invoked at natural DCFR chunk boundaries — best-effort, not
  per-iteration, since the Rust preflop loop runs in a single PyO3
  call per chunk. UI progress bar and Stop button now reflect real
  preflop solve state instead of being no-ops.

### Fixed

- **`Spot.to_hunl_config()` hole-card + pot configuration**
  (pre-existing bug surfaced by PR 10b real-solver wiring). The PR
  10a mock layer accepted any `HUNLConfig`; the real solver does
  not. Without the fix, the first real-solver smoke-test invocation
  hung enumerating ~1.6M combos against an invalid config. The
  patch corrects the hole-card / pot field population so
  `Spot.to_hunl_config()` produces a HUNL config that the real
  solver accepts on the first call.

### Tests

- **28/28 UI smoke tests** (`tests/test_ui_smoke.py`) green against
  the real solver — same suite that ran against the mock in PR 10a
  / v0.6.1, now passing without the mock layer.
- **29/29 preflop tests** (`tests/test_preflop_python.py` +
  `tests/test_preflop_diff.py`, non-slow) green — confirms the
  `on_progress` / `should_stop` kwarg addition is additive and
  preserves PR 9 contract.
- **60/60 cargo tests** + **ruff clean** + **0 new mypy errors**
  verified pre-cherry-pick on `pr-10b-ui-bindings`.

### Out of scope (deferred)

- **Q3 exploitability slider reframe** — PR 10a's iteration-count
  slider stays as-is; the target-exploitability reframe Q-lock is
  deferred to a v1.5 UX polish pass.
- **Range-based dealing** in the UI — PR 9's point-hole-card-pairs
  scope is unchanged here; UI range matrix input is still
  display-only on the preflop solve path.
- **Rust-side `on_progress` / `should_stop` callbacks** — the
  current PyO3 preflop binding does not surface per-iteration
  callbacks back to Python (chunk-boundary best-effort only). Full
  Rust-side callback plumbing is deferred.
- **Full-tree preflop** — same scope boundary as PR 9; subgame-only
  with fixed initial hole cards.
- **LEG 4 .dmg repackage** — the v1.0.0 macOS bundle still embeds
  the mock UI; the LEG 4 follow-up rebuilds the .dmg against this
  v1.2.0 commit so the downloadable artifact matches the public
  release.

### License compliance

Zero new deps; NiceGUI optional extra unchanged; MIT-only posture
preserved.

### Internal

- `__version__` bumped to `1.2.0` (MINOR — UI seam replacement,
  additive kwarg on `solve_hunl_preflop`; no behavior change to
  PRs 1-9 or v1 GA API).

## [1.1.0] - 2026-05-23

PR 9: HUNL **preflop subgame solver** (Python + Rust tiers) with
equity-leaf substitution. Closes the public OSS preflop gap for **point
hole-card pairs**; full-tree preflop deferred. Preflop subgame solves
now ship in both tiers on the PR 3 HUNL tree (4-bet / 5-bet ladder) +
PR 1 DCFR core, with an equity-leaf substitution wrapper (Brown &
Sandholm 2018 depth-limited-solving pattern) collapsing postflop
subtrees to equity-weighted terminals. MINOR bump: new public entry
point + additive dispatch composition; zero behavior change to PRs 1-8
or the v1 GA API surface.

### Added

- **Python preflop solver** (`poker_solver/preflop.py`, 516 lines):
  `solve_hunl_preflop(config, ...)`, `PreflopSubgameGame` wrapper,
  `PreflopSolveResult` dataclass. Caller supplies `HUNLConfig` with
  `starting_street=PREFLOP` + fixed `initial_hole_cards`. Equity is
  exhaustively enumerated (not Monte Carlo) so Python and Rust produce
  bit-exact leaf values.
- **Rust preflop port** (`crates/cfr_core/src/preflop.rs`, 525 lines):
  in-Rust exhaustive equity enumerator + `PreflopDcfr` loop reusing
  `HUNLState` / `HUNLConfig` from PR 3 / 6.
- **PyO3 bindings** (`crates/cfr_core/src/lib.rs`, +66 lines):
  `pub mod preflop;` + `solve_hunl_preflop` binding.
- **Dispatch composition** (`poker_solver/solver.py`, +97/-3): routes
  preflop HUNL with fixed hole cards to Python or Rust per `backend=`.
  Rust branch recomputes exploitability + game_value through
  `PreflopSubgameGame`.
- **Re-exports** in `poker_solver/__init__.py`: `solve_hunl_preflop`,
  `PreflopSolveResult`, `PreflopSubgameGame`.

### Performance (measured, single trial; 500 iters)

100 BB AA vs KK, 5 bet sizes, 608 infosets:

| Tier | Wall-clock | Iters/sec |
|---|---|---|
| Python | ~25 sec | ~20 |
| **Rust** | **~1.2 sec** | **~420** |

**~21x** Rust speedup on the same tree. Equity cache hit rate after
iteration 1: 100% (warms in ~0.1 sec of Rust solve).

### Tests

- 16 Python tests (`tests/test_preflop_python.py`) — API contract,
  symmetry, dispatch, equity-leaf, memory report.
- 4 Rust cargo unit tests in `preflop::tests` — equity AA-vs-KK
  canonical, AA-vs-AA = 0.5, subgame config accepted, missing
  hole-cards rejected.
- 13 differential tests (`tests/test_preflop_diff.py`) at 5 / 20 / 100
  BB, per-action tolerance **5e-3**, per-spot game-value tolerance
  **1e-3** (scope: point hole-card pairs).
- 83 regression tests (HUNL tree / core / pushfold / action
  abstraction / DCFR core+diff) all pass.

### Fixed

- **Banker's-rounding fix** in pre-existing code:
  `crates/cfr_core/src/hunl.rs` `python_round_positive`. PR 6's
  implementation was round-half-up (`(value + 0.5).floor()`) despite
  the docstring claiming "byte-for-byte parity with Python's
  `round()`". Switched to Rust 1.77+ `f64::round_ties_even`.
  Eliminates one-chip token divergences (e.g., Python `r1037` vs
  old-Rust `r1038`) surfaced by the PR 9 diff test at the 4-bet ladder
  rounding boundary.

### Changed

- **`solve()` dispatch ordering** preserved per §6 canonical
  invariant: push/fold chart short-circuit at ≤15 BB still hits FIRST.
  PR 9 only invoked for stacks 15-250 BB (or when caller passes
  `allow_pushfold_range=True`).

### Out of scope (deferred)

- **Full Pluribus blueprint + subgame refinement**: PR 9 ships
  subgame-only with fixed initial hole cards, not the
  `pr9_spec.md` blueprint+refinement architecture.
- **Full-tree preflop** with range-based hole-card dealing — point
  hole-card pairs only; range support is a follow-up (169-class hand
  abstraction or Pluribus blueprint pattern).
- **`on_progress` callback** threading for PR 10b UI dispatch.
- **Postflop continuation beyond equity-leaf**: full Pluribus subgame
  refinement composing PR 5's `solve_hunl_postflop` (current wrapper
  bakes in "check it down" for non-all-in preflop closes).

### License compliance

Zero new deps; no AGPL leakage; MIT-only posture preserved.
`cargo.lock --locked` verified.

### Internal

- `__version__` bumped to `1.1.0`.

## [1.0.1] - 2026-05-23

PR 8: NEON SIMD kernels + cache-blocked layout primitive + public chance
sampling (PCS) infrastructure. Rust-internals only; zero public API
change; PATCH bump. The spec's 10x end-to-end gate is NOT MET — the
"true 10x" refactor (`FlatInfosetStore` primary-wire + `state.clone()`
elimination + arena allocator) is deferred to PR 8b after a feasibility
study (`docs/pr8b_prep/feasibility_study.md`) found a realistic
end-to-end ceiling of 3-5x at 12-23 engineering days. PR 8b is parked
behind a concrete revisit trigger; revisit only if perf becomes a
user-facing constraint.

### Added

- **NEON SIMD kernels** (`crates/cfr_core/src/simd.rs`, ~470 LOC).
  ARM NEON 128-bit f64 intrinsics for the DCFR hot path with
  bit-identical scalar fallbacks. Two-rounding (no-FMA) design is
  load-bearing: FMA shaved ULP that compounded over 1000+ iters past
  the `STRATEGY_ATOL=1e-4` diff bar. Measured speedups at HUNL-relevant
  row widths (per `crates/cfr_core/benches/baseline.json`, Apple M4 Pro,
  release build): `discount_strategy` 3.29x at width=8;
  `positive_regrets_and_total` 2.69x at width=6; `update_regret_sum`
  2.53x at width=8; `discount_regrets` 1.40x at width=64.
- **`FlatInfosetStore`** (`crates/cfr_core/src/layout.rs`, ~190 LOC):
  cache-blocked flat regret + strategy arenas with `BLOCK_SIZE=64` rows
  per block; `InfosetId` opaque handle. **Built but NOT primary-wired**;
  `DCFRSolver` / `HUNLDcfr` still use `HashMap<String, InfosetData>`.
- **Public chance sampling** (`crates/cfr_core/src/pcs.rs`, ~175 LOC):
  Rust-internal only. `SamplingStrategy::{Full, PublicChance}`;
  splitmix64-derived deterministic `PcsRng`; importance-weighted
  unbiased estimator; negative-control test. NOT exposed via PyO3;
  Python `use_pcs` surfacing deferred.
- **Bench harness** (`crates/cfr_core/benches/dcfr_bench.rs`, ~210 LOC)
  with archival `benches/baseline.json` snapshot.

### Fixed

- 4 clippy warnings (`needless_range_loop`, `derivable_impls`,
  `manual_is_multiple_of`).
- One `unsafe` block in `layout.rs::row_mut` refactored to safe
  `split_at_mut` disjoint-borrow.
- Pre-existing `cargo fmt` drift across 8 files reflowed.

### Not shipped (deferred)

- **Spec §2 10x end-to-end gate NOT MET.** Leduc end-to-end NEON vs
  scalar = 2287 us / 2256 us = 0.986x (flat); HashMap + `format!()`
  per-visit dominates kernel arithmetic.
- **`FlatInfosetStore` primary-wire** (PR 8b).
- **True 10x refactor** (PR 8b): feasibility ceiling 3-5x, cost 12-23
  days; see `docs/pr8b_prep/scope.md`.
- **PCS PyO3 surfacing** (Python `use_pcs` parameter): deferred.

### Tests

- Rust: 39 lib + 19 hunl_state_unit + 10 test_hunl_rust passing;
  6 SIMD bit-parity tests (`a.to_bits() == b.to_bits()`) green.
- Python: 21/21 DCFR diff + Leduc diff + Kuhn DCFR PASS;
  `STRATEGY_ATOL=1e-4` gate green.
- Pre-existing PyO3-embed test flake (Python 3.13 `typing.ClassVar`
  circular-import) confirmed unchanged from `main@62c75d5`.

### Internal

- `__version__` bumped to `1.0.1` (PATCH — no public API surface
  change; all additions are Rust-crate internals).

## [1.0.0] - 2026-05-22

**v1 GA milestone.** PR 11: Library mode + macOS .dmg packaging. Ships the
two coupled deliverables that turn the solver into a usable personal tool:
(1) Library mode — a local SQLite-backed on-disk database that persists
solved spots indexed by a deterministic spot ID, queryable from the CLI
and from the PR 10 UI; and (2) macOS distribution — a code-signed,
notarized `.dmg` installer that drops a single `.app` into `/Applications`.
MAJOR bump because: PR 11 closes every v1 deliverable on the roadmap
(HUNL postflop + preflop in Python+Rust; PR 4 abstraction; PR 5 profiler;
PR 9 blueprint+refinement; PR 10 UI; PR 11 library + distribution); the
public API surface is now considered stable under semver — the v0.x
experimental disclaimer is removed from the README; on-disk artifact
compatibility (`library.db` schema_version = 1) is committed to, with
explicit migration paths for v2. PATCH and MINOR semantics resume from
1.0.0 onward.

### v1 GA summary — every PR shipped

- **PR 1** (v0.1.0): Kuhn poker + DCFR; two-tier Python/Rust architecture.
- **PR 2** (v0.2.0): Leduc poker; Game trait abstraction; Rust port.
- **PR 3** (v0.3.0): HUNL game tree + 14-action abstraction + integer-cents
  chip arithmetic.
- **PR 3.5** (v0.3.0): Push/fold charts for 2-15 BB short-stack play.
- **PR 4** (v0.4.0): Card abstraction package; EMD-based equity-distribution
  bucketing; suit-isomorphism canonicalization.
- **PR 4.5** (v0.5.2): Audit-debt sweep (13 should-fix items, no behavior
  changes).
- **PR 5** (v0.4.0): HUNL postflop solve orchestrator + per-street memory
  profiler.
- **PR 6** (v0.5.0): Rust HUNL postflop port; ~24x speedup; bit-exact
  parity.
- **PR 7** (v0.5.1): River-spot diff vs Noam Brown's MIT reference solver;
  first external-Nash agreement gate.
- **PR 8** (deferred to v1.5): NEON SIMD optimizations.
- **PR 9** (rolled into PR 11): HUNL preflop blueprint + refinement.
- **PR 10a** (v0.6.0): NiceGUI browser UI scaffold (mock solver layer);
  two-pane layout; 13×13 range matrix with Pio-convention color blend.
- **PR 10b** (rolled into PR 11): Mock→real solver swap (one-line import).
- **PR 11** (v1.0.0, this release): Library + macOS .dmg distribution.

### Added

- **Library mode** (`poker_solver/library.py`, ~450 LOC): Single SQLite file
  at `~/.poker_solver/library.db` (XDG-style), overridable via
  `POKER_SOLVER_LIBRARY_PATH` env var or `--library-path` CLI flag. WAL
  mode for concurrent readers + single writer.
  - **Schema** (`poker_solver/library_schema.sql`): `spots` table with
    `id` (sha256 of canonicalized spot JSON), `spot_json` (BLOB),
    `strategy_gz` (gzip-compressed avg_strategy JSON), `game_value`,
    `exploitability`, `iterations`, `abstraction_tier`, `solver_version`,
    `schema_version`, `created_at`, plus indexed denormalized projections
    (`board_signature`, `stack_bb`, `bet_menu_hash`, `street`). Indexes on
    `board_signature`, `street`, `stack_bb`, `created_at`, `solver_version`.
    Plus `spots_meta` key-value table.
  - **Deterministic spot ID**: `sha256(canonicalized_spot_json).hexdigest()`.
    Canonicalization: board sorted by `(rank, suit)`; stacks in integer
    cents; bet-menu fractions sorted ascending; ranges serialized as
    sorted hand-list with canonical hand form; antes + rake included
    even when 0; solver hyperparameters EXCLUDED.
  - **Compressed strategy storage**: `gzip.compress(json_bytes,
    compresslevel=6)`; bit-exact roundtrip required (`np.array_equal`,
    NOT `np.allclose`).
  - **API**: `Library.open`, `put`, `get`, `list`, `export`, `import_`,
    `delete`, `stats`, `close`. Internal `threading.Lock` around writes;
    WAL handles concurrent reads.
  - **Versioning**: `solver_version` mismatch → `UserWarning` (soft);
    `schema_version` mismatch → `LibrarySchemaError` (hard).
- **Library re-exports** in `poker_solver/__init__.py`: `Library`,
  `LibraryDuplicateError`, `LibraryError`, `LibraryFilter`,
  `LibrarySchemaError`, `LibraryStats`, `SpotDescription`, `SpotMetadata`.
- **CLI `library` subcommand group** (`poker_solver/cli.py`): `list`,
  `get`, `put`, `export`, `import`, `delete`, `stats`. Output formats:
  tab-separated default, `--json` for machine-readable, `--table` for
  rich-table (if `rich` installed).
- **CLI `batch-solve` subcommand** (alongside `scripts/batch_solve.py`):
  CSV input → idempotent solve loop. Skips already-cached spots by
  `spot_id`. `--workers N` for parallel solves; `--dry-run` validates
  CSV without solving. `--max-memory-gb` per-worker budget.
- **macOS packaging pipeline**:
  - `scripts/build_macos_dmg.sh` (~150 LOC): clean → PyInstaller →
    in-bundle smoke test → codesign → notarize → staple → DMG → codesign
    DMG → notarize DMG → staple DMG. Supports
    `--skip-signing --skip-notarization` for unsigned-fallback path.
  - `scripts/sign_and_notarize.py` (~200 LOC): inside-out signing walk;
    explicit `find Contents -name "*.dylib" -o -name "*.so"` and signs
    each inner binary with Hardened Runtime before the outer `.app`.
  - `scripts/entitlements.plist`: Hardened Runtime entitlements
    (`allow-jit`, `allow-unsigned-executable-memory`,
    `disable-library-validation`).
  - `scripts/poker_solver.spec`, `scripts/pyinstaller_entry.py`:
    PyInstaller spec + entry point with the load-bearing `--add-binary`
    flag for the maturin-built Rust extension.
  - `assets/poker_solver.icns`: app icon. `assets/README.md`: icon
    regeneration instructions.
- **UI library browser** (`ui/views/library_browser.py`): PR 10a stub →
  real loader. Filter form (street dropdown, stack-range slider,
  board-regex input, free-text label search); sortable `SpotMetadata`
  table; per-row actions (Load → main solve panel, Export → file dialog,
  Delete → confirm dialog); footer with `LibraryStats` summary.
  `Library.get` offloaded to `asyncio.to_thread`.
- **"Save to library" button** on the PR 10 spot input panel: explicit,
  user-controlled. No auto-save.
- **Tests**:
  - `tests/test_library.py` (~15 unit tests per spec §9): schema, WAL
    concurrency, spot ID determinism, gzip bit-exact roundtrip,
    put/get/delete/list/export/import roundtrips, duplicate handling,
    filter composition, schema-version hard error.
  - `tests/test_library_cli.py` (~5 integration tests): CLI subcommands
    end-to-end via `subprocess.run`.
  - `tests/test_library_ui_integration.py`: stub
    (`pytest.skip("requires PR 10 UI harness")`).
- **Optional extra** `[project.optional-dependencies] distribution =
  ["pyinstaller>=6.0"]`. Default `pip install -e .` does NOT pull it in.

### Changed

- **`poker_solver/__init__.py`** — re-exports `Library` and related
  symbols; `__version__` bumped to `1.0.0`.
- **`poker_solver/cli.py`** — `library` subcommand group + `batch-solve`
  top-level subcommand.
- **`ui/views/library_browser.py`** — PR 10a stub → real loader per
  spec §4.1.
- **`pyproject.toml`** — `[project.optional-dependencies] distribution =
  ["pyinstaller>=6.0"]`; NO new runtime dependencies (SQLite, gzip,
  hashlib, json are stdlib).
- **`scripts/check_pr.sh`** — extends test command to include
  `tests/test_library.py tests/test_library_cli.py`.
- **`README.md`** — bumped to v1.0.0; v0.x experimental disclaimer
  lifted; semver applies from 1.0.0 onward.

### Contract decisions (per spec §13)

- Apple Developer enrollment OPTIONAL; unsigned-fallback path produces
  a working `.app` without $99/yr cost (D1).
- Library file at `~/.poker_solver/library.db` with env var override (D2).
- Spot export format JSON (uncompressed, human-inspectable) (D3).
- No auto-suggest library spots on UI input (deferred to PR 11.5; D4).
- Explicit schema migration (NOT auto-rebuild lossy; D5).
- arm64-only bundle (NOT universal2; D6).
- Plain default DMG window styling (D7).
- PyInstaller `--onedir` (NOT `--onefile`; D8).
- Explicit "Save to library" button (NOT auto-save; D9).
- `create-dmg` Homebrew formula (NOT sindresorhus npm; D10).
- gzip compresslevel 6 (D11).
- CLI list output tab-separated default (D12).
- PR 11 follows PR 10 (D13).

### Out of scope (deferred)

- Cloud-distributed library, auto-population scheduler, multi-user
  library, neural value warm-starts from cached spots (PR 13+).
- Windows/Linux installers, universal2 binary, Apple Developer enrollment
  mandate.
- New `pyproject.toml` runtime deps; UI test framework introduction.

### License compliance

- PyInstaller is GPL-with-exception — the exception explicitly covers
  bundled apps (per PyInstaller's COPYING file). SQLite is public
  domain (stdlib). NumPy is BSD. NiceGUI is MIT (PR 10a dep, unchanged).
  Library code is pure Python + stdlib (zero new runtime deps). PR 11
  ships zero AGPL/GPL code in the runtime or bundle.

### Internal

- `__version__` bumped to `1.0.0` (MAJOR — v1 GA milestone marker).
- Three-agent fan-out (A: library module + SQLite schema + CLI;
  B: macOS packaging + signing pipeline; C: tests + batch_solve.py)
  plus a post-implementation audit pass.

## [0.6.1] - 2026-05-23

PR 10a.5: UI conformance follow-up to v0.6.0. Resolves the 5 fail + 7 xfail
markers left over from PR 10a so the full UI smoke suite ships green (22/22
passing, was 8/22). Migrates the four UI views from `.props("data-marker=…")`
to NiceGUI 3.x `.mark()` with whitespace-tokenized multi-tag strings, wires
the seven UX surfaces the PR 10a tests already expected (DISPLAY_PALETTE +
cell colorization, blocker overlays, INPUT_PALETTE, expl-chart linear toggle,
OOM bet-size reducer, push/fold switch stub, progress ETA + SolveRunner.
compute_eta), and patches two NiceGUI 3.x bugs (FixturePreset repr leaking
into the UI, EChart.options read-only mutation). Also includes an audit-found
f-string bug fix in `spot_input.py` (push/fold toast was rendering literal
`{bb}` instead of the stack size). Defers 2 should-fix items to a v0.6.2
backlog: `run_panel` unbounded `bet_sizes_checked` prune (needs design
decision on clamp policy) and `state.compute_eta` dead-code path (needs
production ETA wiring + own audit pass). PATCH bump: zero behavior change in
the solver / spec; UI-only polish; same public API.

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

[Unreleased]: https://github.com/amaster97/poker_solver/compare/v1.3.1...HEAD
[1.3.1]: https://github.com/amaster97/poker_solver/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/amaster97/poker_solver/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/amaster97/poker_solver/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/amaster97/poker_solver/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/amaster97/poker_solver/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/amaster97/poker_solver/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/amaster97/poker_solver/releases/tag/v1.0.0
[0.6.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.6.1
[0.6.0]: https://github.com/amaster97/poker_solver/releases/tag/v0.6.0
