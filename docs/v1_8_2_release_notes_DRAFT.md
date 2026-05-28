# poker-solver v1.8.2 — TerminalCache 213× river win + CLI walk-tree + DCFR safety guards

**Status: DRAFT (compile-since-v1.8.0). Compiled 2026-05-27 from the
post-v1.8.0 main branch. Skips the v1.8.1 tag — the v1.8.1 candidate
patches (#91 / #95 / #96) landed on main directly during the
post-v1.8.0 doc-hygiene wave and are folded into v1.8.2 rather than
shipping under a separate tag, mirroring the v1.7.x → v1.8.0 fold-in
decision (per `docs/v1_8_1_release_decision_2026-05-27.md`).**

**Baseline commit on `origin/main`:** `8a9c8d2` (v1.8.0 tag, 2026-05-27).
**Compilation tip:** `27e6b1d` (PR #130, 2026-05-28 01:58 UTC).
**Release date:** TBD (user-gated; release notes are user-facing).
**Tag:** `v1.8.2` (to be created at ship time; v1.8.1 skipped per
fold-in decision above).
Final tag SHA will be set at `git tag` time.

---

## Headline

**v1.8.2 — TerminalCache 213× river RvR speedup + CLI walk-tree/drill-down + DCFR α-guard hard-fail.**

Three things land together in this release:

1. **TerminalCache: 213× speedup on vector-form river RvR.** Profiling
   identified `evaluate_7` calls in the O(N²) per-pair terminal loop as
   ~100% of inner-kernel time. The new `TerminalCache` precomputes
   per-player hand-strength vectors at each Showdown leaf and constant
   chip-flow payoffs at each Fold leaf, **once per solve**. Result on a
   1081-hand × 30-decision-node full-tree river fixture: **28.62 s/iter
   → 0.134 s/iter (~213×).** The bit-equality unit test
   (`cached_matches_uncached_terminal_value`) confirms zero strategy
   drift vs the uncached path. See "Engine perf" §1.
2. **CLI walk-tree + per-class drill-down + JSON/CSV output.** The
   `poker-solver river` CLI grows three composable presentation knobs
   (`--walk-tree`, `--node`, `--format`) that let users navigate the
   full decision tree instead of only the first-decision aggregate. The
   new `subgame --street flop|turn|river` command generalizes the same
   surface across all postflop streets with byte-identical backward
   compatibility for the legacy `river` invocation. See "CLI" §3.
3. **DCFR α-guard: hard-fail on α ≤ 0, warn on 0 < α < 0.5.** Closed a
   silent non-Nash footgun where `α=0` produced flat exploitability on
   Kuhn (`8.6e-2` vs the correct `~1.27e-3` at `α=1.5`) by halving
   positive regrets every iteration. Production default `α=1.5` was
   never affected; the guard prevents reasonable-looking experimental
   configs from silently passing. See "Engine quality" §2.

The release also folds in the v1.8.1 candidate doc/test-hygiene wave
(#91 Brown dump literals, #95 `.dmg` build absolute path, #96 release
notes broken refs + naming collision + silent-skip hazard), the
EV(action) invariance gauntlet (#98) as a Nash-invariant cross-solver
sanity check that complements strict-σ parity at deep-cap multiplicity
manifolds, and four ship-script hazard checks (#119) encoding the
post-v1.8.0 burst's release-process lessons. Marcus W1.5 (pushfold
`return_ev=True`), Priya W4.2 (spec amendment), and Daniel W3.5
(range-setup-mode spec amendment) all move into PASS in the persona
table. PR [#129][pr129] also adds `reach_probability` +
`off_path_keys` fields to `SolveResult` so downstream consumers can
filter phantom 5% infosets (closes user-issue #47).

---

## Highlights

### 1. TerminalCache: 213× speedup on vector-form river RvR (PR [#114][pr114])

**Merge SHA:** `036a101`.

A per-phase profile of `dcfr_vector::traverse` on a 1326-hand × 30-decision-node
full-tree river fixture (`crates/cfr_core/benches/rvr_profile.rs`,
new in this PR) pinpointed `terminal_value_vector` as ~100% of inner-kernel
time. Root cause: the O(N²) per-pair loop at every terminal leaf called
`evaluate_7` afresh on every iteration even though the board is fixed
across the entire solve.

**Fix:** `TerminalCache` (new in `crates/cfr_core/src/dcfr_vector.rs`)
precomputes:
- Per-player `Strength` vectors at each **Showdown** leaf, once per
  solve.
- Constant chip-flow payoffs at each **Fold** leaf, once per solve.

`terminal_value_vector_cached` reads from the cache instead of calling
`evaluate_7` per-pair-per-iter. The old uncached function is retained
as the parity reference and exercised by a new bit-exact Rust unit test
(`cached_matches_uncached_terminal_value`).

**Bench numbers (full-tree river, 1081 hands × 30 decision nodes,
M4 Pro arm64):**

| Variant            | s / iter | Notes                              |
|--------------------|----------|------------------------------------|
| Baseline (uncached)| **28.62**| Matches HIGH-2's ~26 s/iter framing|
| **Cached**         | **0.134**| Cache build amortized over iters   |
| **Speedup**        | **~213×**| Well past the 2× HIGH-2 target     |

After caching, `terminal_value_vector` still dominates (~99% of cached
inner-kernel time) but in absolute terms it's now 0.134 s/iter from
28.6 s/iter. All other phases (compute_strategy, update_regret_sum,
update_strategy_sum, etc.) sum to <0.001 s/iter — no remaining
low-hanging optimization at this fixture size.

**Bit-exactness gates:**
- New Rust unit test `cached_matches_uncached_terminal_value` asserts
  bit-identical output between cached + uncached paths across all
  terminal leaves of a 1081-hand fixture. **PASSES.**
- All 57 `cfr_core` library unit tests pass (`cargo test --lib`).
- All 37 RvR Python differential / aggregator / Nash tests pass
  (`tests/test_range_vs_range_rust_diff.py`,
  `tests/test_range_vs_range_aggregator.py`,
  `tests/test_range_vs_range_nash.py`).

**Tooling shipped alongside:**
- `crates/cfr_core/benches/rvr_profile.rs`: per-phase `Instant`-based
  bench harness. Reports total wall, per-iter wall, and (with
  `--features profile_rvr`) a cost breakdown across 11 named phases.
- `CFR_VECTOR_NO_TERMINAL_CACHE=1` env knob routes through the uncached
  path for baseline comparison; production has this unset.
- `profile_rvr` feature flag is opt-in; without it the profiling macros
  expand to no-ops (zero overhead on the production hot path).

**Why caching instead of wider SIMD?** The original HIGH-2 framing
assumed the bottleneck was inner-f64 vector ops missing wider SIMD. The
profile **refuted** that: the kernel was bottlenecked by repeated O(N²)
`evaluate_7` calls on a constant board, not by f64 arithmetic. NEON
SIMD on the post-cache hot path remains a clean follow-up but the ~200×
speedup from caching alone takes river RvR wall-clock from minutes to
seconds at typical iteration counts — sufficient to unblock the
downstream UI True-Nash work (PR #126, HOLD) and the W2.3 perf-budget
retest (still BLOCKED on best-response walk caching, separate follow-on
wall).

Full bench report: see PR #114 description.

### 2. DCFR α-guard: hard-fail α ≤ 0, warn α < 0.5 (PR [#113][pr113])

**Merge SHA:** `3ef9b76`. Implements **Option B** from the merged
proposal in PR [#99][pr99] (`c534bf0`).

Closes the HIGH-1 silent non-Nash bug from
`docs/perpetual_qa_findings_2026-05-27.md`. The DCFR positive-regret
discount kernel computed `pos_scale = t^α / (t^α + 1)`, which at α=0
collapses to `1/2` for all t, **halving positive regrets every
iteration** regardless of t. On Kuhn at 10k iter, α=0 stays at
exploitability `~8.6e-2` vs `~1.27e-3` at the production default α=1.5
(50× worse). Game value lands at −0.093 BB instead of the correct
~−0.056 BB. Max strategy-cell diff vs α=1.5 @ 10k iter: **0.411**.

**Behavior in v1.8.2:**

| α value         | Behavior                                                       |
|-----------------|----------------------------------------------------------------|
| α ≤ 0           | **HARD-FAIL** (`PyValueError` / Rust panic) at solver init.    |
| Non-finite (NaN/±∞) | **HARD-FAIL** at solver init.                              |
| 0 < α < 0.5     | **WARN** — `UserWarning` (Python) / `eprintln!` (Rust).        |
| α ≥ 0.5         | Silent OK. Includes production `α=1.5` and paper-range `α=2.0`.|

The warn band reflects that Brown & Sandholm 2019 validates `α=3/2`
only; values in `(0, 0.5)` are below the paper's analyzed range but
not provably broken.

**Surface area covered (12 entry points per the proposal):**

- **Rust:** Single `cfr_core::dcfr::validate_alpha` helper called from
  4 DCFR ctors (`DCFRSolver`, `PreflopDcfr`, `VectorDCFR`, `HUNLDcfr`).
  The 5 PyO3 entries (`solve_kuhn`, `solve_leduc`, `solve_hunl_postflop`,
  `solve_hunl_preflop`, `solve_range_vs_range_rust`) already wrap
  invocations in `catch_unwind`, so panics surface as `PyValueError`.
- **Python:** `poker_solver.dcfr._validate_alpha` called from
  `DCFRSolver.__init__`, `solver._solve_rust`,
  `range_aggregator.solve_range_vs_range_nash`.

**Test plan PASS:**
- `crates/cfr_core/tests/test_dcfr_alpha_guard.rs` — 7 Rust cases (α=0,
  <0, NaN, ±inf, warn-band 0.3, prod 1.5, paper-range 2.0). All PASS.
- `tests/test_dcfr_alpha_guard.py` — 14 Python cases including the
  user-requested `test_alpha_zero_hard_fails` / `test_alpha_small_warns`
  / `test_alpha_default_silent` on `_rust.solve_kuhn` + `_solve_rust`.
  All PASS.
- Regression: `test_dcfr_core.py` + `test_dcfr_diff.py` +
  `test_kuhn_dcfr.py` + `test_leduc_dcfr.py` — 20/20 PASS. Existing
  α=2.0 sensitivity probes remain silent.
- Rust lib: `cargo test -p cfr_core --release --lib` — 56/56 PASS.

**Migration impact:** any downstream call passing α ≤ 0 will now raise
instead of silently producing wrong strategies. See "Migration /
breaking changes" below.

### 3. EV(action) invariance gauntlet (PR [#98][pr98])

**Merge SHA:** `3cc5eba`.

A new test-only deliverable
(`tests/test_ev_invariance_gauntlet.py`, ~530 LOC) implementing the
Nash-invariance EV(action) gauntlet on the canonical K72 + A83 deep-cap
multiplicity fixtures. Per Brown 2019 Thm 2 / von Neumann minimax,
`Q_p(I, a)` is unique across all Nash of a 2-player constant-sum game
**even when strategy probabilities are not** (Nash multiplicity at
indifference manifolds). This compares EV-of-action at depth=0 (true
root) between Brown's solver and our Rust DCFR, walking the SAME Python
game tree under the canonical Brown utility convention (PR #78 in
v1.8.0).

**Why this test exists.** Strict per-cell σ parity FAILS on K72/A83 at
deep-cap indifference manifolds — Brown and ours land on different
points of the manifold (both Nash, just non-unique). The σ gate flags
this as a FALSE POSITIVE per
`feedback_nash_multiplicity_acceptance.md`. The EV gauntlet is the
principled answer: at the root, EV should agree regardless of which
Nash each solver picked.

**Empirical baseline (2000 iters, 2026-05-27):**

| Fixture          | depth=0 p75 \|Δ\| | depth=0 max \|Δ\| | depth ≥ 1 max \|Δ\| | Verdict |
|------------------|-------------------|-------------------|---------------------|---------|
| dry_K72_rainbow  | 0.018 BB (gate ≤ 0.10) | 1.04 BB (gate ≤ 1.50) | 29.6 BB (informational) | PASS  |
| dry_A83_rainbow  | 0.012 BB (gate ≤ 0.10) | 0.38 BB (gate ≤ 1.50) | 27.3 BB (informational) | PASS  |

Both fixtures PASS the load-bearing depth=0 gate where strict per-cell
σ parity FAILS. Deep-layer (depth ≥ 1) EV deltas are REPORTED but NOT
gated — per `feedback_nash_multiplicity_acceptance.md`, deep-cap
convergence at 2000 iters is imperfect on both solvers; this manifests
as depth=1 σ-driven downstream EV divergence, NOT a Nash-invariance
violation per se.

**What the gauntlet catches that strict-σ misses:** convention bugs
(e.g. the legacy "rust" terminal utility purged in PR #78), regret-update
bugs, and wrong-tree shape (missing action, wrong infoset bucketing).
Accepts Nash-multiplicity σ divergence at deep cap (false-positive-clean
by design).

Marked `@slow` + `@parity_noambrown` (default-deselected); runs in
~5 min total locally.

Design doc: `docs/ev_invariance_sanity_gauntlet_design_2026-05-27.md`.
Phase 1 baseline: `docs/ev_invariance_gauntlet_phase1_baseline_2026-05-27.md`.

### 4. CLI: walk-tree + per-class drill-down + JSON/CSV (PR [#123][pr123])

**Merge SHA:** `8f173db`.

Extends `poker-solver river` with six new composable flags so users can
navigate the full decision tree instead of only the first-decision
aggregate. **Zero engine touch** — all new logic lives in a new helper
module `poker_solver/cli_tree_walk.py` (~520 LOC). `average_strategy`
dict schema unchanged; works on any backend.

**Backward compat invariant:** with no new flags, `poker-solver river`
output is **byte-identical** to the prior CLI surface (test 7 verifies
via direct comparison against the `main` branch).

**Phase 1 — `--walk-tree`.** Walks every on-path decision node (reach
> 1e-4 by default), printing player + hole-card label, humanized action
history (`"check then bet 750"`), per-action labels with chip amounts
(`"raise to 3125 (75% pot)"`), ASCII bar charts, and reach probability
along the path. `--full-tree` adds off-path phantoms marked `[OFF-PATH]`.

**Phase 2 — `--node "..."` drill-down.** For range queries, aggregates
per-hand-class strategy at a specific history (e.g. `--node "xb750"`).
Top-12 by Shannon entropy by default (mixing hands first); `--full-classes`
shows all. **MDF annotation** appears when fold + call are in the action
menu — e.g. `MDF=70.00%, observed fold=99.85% (over-folding)`.

**Phase 3 — `--format {text|json|csv}`.**
- `text` (default): pretty tree with bar charts.
- `json`: full dict dump (every combo / node / action / hand class) —
  parseable by `json.loads`.
- `csv`: rows of `(combo, node_history, action_label, probability,
  reach_prob)` with header.

**New flags:** `--walk-tree`, `--full-tree`, `--node`, `--top-n`,
`--full-classes`, `--format`.

**Test plan PASS:**
- 7 acceptance tests in new `tests/test_cli_walk_tree.py` (~330 LOC):
  AK-vs-QQ on-path walk, off-path phantoms, node drill-down with MDF
  annotation, JSON parseability, CSV header + rows, action-label
  decoder (`b750` / `A` / `r3125` / `x` / `c` / `f`), backward-compat
  byte-identical default output.
- All 7 existing CLI tests (`test_cli_subcommands.py`,
  `test_cli_version.py`) still pass.
- Ruff + mypy clean on the new files.

### 5. CLI: `subgame` command for flop / turn / river (PR [#127][pr127])

**Merge SHA:** `f2d7106`.

Generalizes the v1.8.2 `river` CLI to
`subgame --street {flop|turn|river}`. The engine's
`solve_hunl_postflop` already supports all postflop streets; this is a
**pure CLI surface** — zero engine touch.

`_cmd_river` is refactored into a thin wrapper over a new shared helper
`_run_subgame_solve(street, show_street_line)`. The `river` alias passes
`show_street_line=False` so its v1.8.2 output stays **byte-for-byte
identical** to the legacy invocation.

**All v1.8.2 presentation knobs** (`--walk-tree`, `--node`, `--format`)
work uniformly across all three streets.

**Usage:**
```bash
# Flop spot
poker-solver subgame --street flop --board "As 7c 2d" \
    --hero AhKh --villain-range "QQ,JJ,AKs" --iters 200

# Turn spot
poker-solver subgame --street turn --board "As 7c 2d Kh" \
    --hero AhKh --villain-range "QQ"

# River spot (equivalent to legacy `river`)
poker-solver subgame --street river --board "As 7c 2d Kh 5s" \
    --hero AhKh --villain-range "QQ"

# All v1.8.2 knobs work on every street
poker-solver subgame --street flop --board "..." --hero ... \
    --villain-range "..." --walk-tree --format json
```

**Backward compat:** `poker-solver river ...` keeps working unchanged.
Help text annotates the deprecation but the output is byte-identical to
v1.8.2.

**Test plan PASS:** 7 new tests in `tests/test_cli_subgame.py` (flop /
turn / river dispatch, `--walk-tree` on flop, `--node` drill-down on
turn, `--format json` on flop, `--river-alias` backward compat). All 14
existing CLI tests (`test_cli_subcommands.py` + `test_cli_walk_tree.py`)
still pass.

### 6. Off-path infoset annotation in `SolveResult` (PR [#129][pr129])

**Merge SHA:** `5fec960`. Closes user-issue #47.

Adds two new fields to `SolveResult` so consumers can filter phantom
5% infosets:

- `reach_probability: dict[str, float]` — per-infoset joint reach
  (own × opp × chance), computed via a forward walk over the solved
  strategy.
- `off_path_keys: frozenset[str]` — infoset keys whose reach falls
  below a tolerance, exposed as a fast-membership-check companion to
  `reach_probability`.

**Fully additive.** Every existing `SolveResult(...)` call site,
library round-trip, and PR #123's `cli_tree_walk` tests still pass
byte-for-byte. The CLI tree-walker
(`cli_tree_walk.walk_tree`) now prefers the engine reach map over the
legacy per-walk heuristic when available, with graceful fallback when
missing.

**Threading:** populated on every Python + Rust solve exit point —
Kuhn/Leduc (both tiers), HUNL postflop (both tiers), HUNL preflop
subgame. Intentionally skipped: push/fold chart short-circuit
(precomputed; non-trainable, fields stay empty) + library
deserialization (`_dict_to_result`) — old payloads load with empty
defaults to signal "annotation unavailable".

**Test plan PASS:** 8 new cases in `tests/test_off_path_annotation.py`
(includes the canonical AK-vs-QQ river phantom-5% case: on-path reach
> 0.1, off-path reach < 1e-6, `off_path_keys` non-empty). All 7 PR #123
walk-tree tests + Kuhn/Leduc DCFR tests (42 cases) + CLI subcommand
tests still pass.

### 7. Marcus W1.5 — `return_ev=True` parameter (PR [#125][pr125])

**Merge SHA:** `f098e1f`.

Adds an additive `return_ev` keyword-only parameter to
`get_pushfold_strategy`. Default `False` preserves the legacy `float`
return (backward compat); `True` returns
`{"strategy": prob, "ev_bb": ev}`.

EV is computed at lookup time via Monte Carlo equity sampling against
the equilibrium opposing chart range at the requested depth, then
combined with the chart payoff structure (blinds + showdown EV). Cached
via `@cache` per `(stack_bb, position, hand)` — first call ~0.15s,
repeats O(1).

**Addresses Marcus W1.5 chart-lookup PARTIAL.** Marcus wants the EV in
BB alongside the strategy probability. The structural blocker is closed
in v1.8.2.

**Test plan PASS:** 6 new tests in `tests/test_pushfold_return_ev.py`
(default-float backcompat, dict shape, AKs/72o jam EV ordering, BB-call
EV, mixed-decision EV, BB AA defends well). All 13 existing
`test_pushfold.py` tests still pass (no signature breakage). Ruff +
mypy clean. CLI `pushfold` subcommand still works (positional caller,
unaffected).

### 8. CLI: `--version` flag (PR [#116][pr116])

**Merge SHA:** `9b6fd1f`. HIGH-deferred from PR #107 audit.

Adds `--version` to the top-level `poker-solver` argparse parser; emits
`poker-solver <ver>` and exits 0. Source of truth is
`poker_solver.__version__` — no hardcoding.

**Test plan PASS:** 2 in-process tests + 2 env-dependent subprocess
tests (subprocess paths skip when the console-script shim is bound to a
different interpreter; in-process tests are authoritative). All 7
existing `test_cli_subcommands.py` tests still pass.

### 9. Ship-script hazard checks (PR [#119][pr119])

**Merge SHA:** `00b15b8`. Encodes 4 hazards from the 2026-05-27 v1.8.0
ship burst as programmatic checks in
`scripts/release_v1_8_0_trigger.sh`, each keyed to its memory rule so
future ships can't regress on the same patterns.

| Check | Hazard | Memory rule | v1.8.0 cost |
|---|---|---|---|
| Hazard guard 0 | bash 3.2 + nounset + empty-array footgun | `feedback_bash3_2_empty_array.md` | ~30 min + PRs #88/#90 |
| Phase C.2 (tightened) | `TBD` placeholder false-flag from meta-text | `feedback_release_check_specificity.md` | PR #87 |
| Phase C.6 (new) | `PR #N` citation collision between gh + local branches | `feedback_pr_naming_collision.md` | PR #96 v1.8.1 docs patch |
| Phase C.7 (new) | Cited docs untracked on tag tree (404) | `feedback_release_cited_doc_tracking.md` | 4 docs + 2 tests cited but untracked on v1.8.0 tag |

Each check has a per-check env-var bypass
(`SKIP_BASH_VERSION_CHECK`, `SKIP_PHASE_C_2`, `SKIP_PHASE_C_6`,
`SKIP_PHASE_C_7`) for emergencies. HARD-FAIL messages all cite the
relevant memory rule by filename. New `SMOKE_TEST=1` env var bypasses
Phase A (branch=main) + Phase B (origin sync) so the new hazard checks
can be exercised from a feature-branch worktree.

### 10. Build / docs hygiene wave (v1.8.1 candidate fold-in)

The v1.8.1 candidate patches landed on main during the post-v1.8.0
doc-hygiene wave and are folded into v1.8.2 rather than shipping under
a separate tag (per
`docs/v1_8_1_release_decision_2026-05-27.md`).

- **PR [#91][pr91]** (`23f8966`) — `fix(tests): update Brown dump
  literals + chance_enum hole_cards post PR #69 + #78`. Two test-side
  stragglers from PR #69 (hard-fail on missing `initial_hole_cards`) +
  PR #78 (TerminalUtilityConvention purge): switch
  `test_chance_enum_river_end_to_end_solve_within_perf_gate` to
  `_fixed_combo_river_config()`, and update 3 literals in
  `test_river_diff_self_sanity.py` for the new
  `_canonicalize_hand_pair` suit re-sort. No runtime impact; tests
  only.
- **PR [#95][pr95]** (`cdb1c47`) — `fix(build): resolve APP_PATH to
  absolute before defaults read`. Patches `scripts/build_macos_dmg.sh`
  step 5.5 relative-path silent-fail when `APP_PATH` is relative under
  the default `OUTPUT_DIR=dist`. macOS `defaults read` treats relative
  paths as DOMAIN names (not filesystem paths), silently returning
  empty and surfacing a misleading `MISSING != <version>` drift error.
  Step 5.5 now resolves `APP_PATH_ABS` via `cd "$(dirname …)" && pwd`
  and HARD-FAILs on empty/`MISSING` plist values before the drift
  comparison.
- **PR [#96][pr96]** (`9213085`) — `docs(v1.8.1): fix release-notes
  broken refs + PR #93 collision + silent-skip hazard`. Addresses ALL
  HIGH findings from `docs/post_burst_audit_2026-05-27.md` + 
  `docs/v1_8_1_candidate_doc_overclaims.md`:
  - 4 broken release-notes doc refs added to git
    (`v1_5_brown_post_purge_numbers_2026-05-27.md`,
    `ev_invariance_sanity_gauntlet_design_2026-05-27.md`,
    `a83_terminal_utility_ablation_results_2026-05-26_archived.md`,
    `terminal_utility_canonical_2026-05-27.md`).
  - PR #93 naming collision (5 release-notes refs to "PR #93"
    mismapping to the WAKEUP doc instead of the local ablation branch
    `pr-93-terminal-utility-ablation` @ `986f48d`) disambiguated.
  - 2 silent-skip test files
    (`tests/test_minimal_nash_fixture.py`,
    `tests/test_aa_vs_aa_root_indifference.py`) added to git so the
    skip-ban CI guard + persona retest doc no longer reference
    untracked files.
- **PR [#89][pr89]** (`6c913aa`) — `fix(build): patch Brown's
  subgame_config.cpp for GCC 11 incomplete-type build`. Closes the
  Brown-buildable-on-Ubuntu blocker for the cross-platform CI matrix.
- **PR [#103][pr103]** (`faea951`) — `fix(ui): remove stale mock-mode
  banner (PR 10b shipped at v1.2.0)`. The banner had been correct under
  v0.x mocked output but was stale since the live-solver wiring shipped
  at v1.2.0.
- **PR [#107][pr107]** (`362e484`) — `fix(docs): README/quickstart
  drift after v1.8.0 ship`. Closes README + quickstart drift caught in
  the post-v1.8.0 audit.
- **PR [#111][pr111]** (`89ec90a`) — `test: add missing @pytest.mark.slow
  to 2 river_diff_self_sanity tests`. PR #82 / #91 follow-up to keep
  the fast lane green.
- **PR [#101][pr101]** (`949f8fe`) — `docs: disclose v1.8.0 GUI
  mock-mode in user-facing locations (post-PR-94 audit)`. User-facing
  disclosure follow-up.

### 11. Persona test status (post-v1.8.2)

Net delta vs the v1.8.0 baseline (`docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`):

| Verdict | Pre-v1.8.2 | Post-v1.8.2 | Delta | Notes |
|---|---|---|---|---|
| **PASS**    | 10 | **12** | +2 | W4.2 PARTIAL → PASS via PR #128 spec amendment (informational criteria when `bet_size_fractions=()`). W3.5 FAIL → PASS via PR #130 spec amendment (no-flush vs class-name API setup distinction). |
| **PARTIAL** | 5  | **3**  | −2 | W1.5 closed by PR #125 `return_ev=True`; W4.2 closed by PR #128 spec amendment; W2.1 / W2.2 / W2.4 unchanged. |
| **BLOCKED** | 1  | **1**  | =  | W2.3 still BLOCKED — TerminalCache speeds the solve phase (>1200 s kill → 16.6 s on 8-class symmetric turn fixture per PR #120) but best-response walk (exploitability compute) is NOT cached by PR #114; W2.3 is a separate perf wall. |
| **FAIL**    | 1  | **0**  | −1 | W3.5 reclassified FAIL → PASS via PR #130 spec amendment. PoC's explicit-no-flush range setup reproduces AA check = 1.0000 bit-clean at v1.8.0; class-name API result (includes flush combos) is informational-only — both are mathematically correct Nash on their respective ranges. |

**Personas unblocked in v1.8.2:**

- **W1.5 (Marcus chart EV)** — `return_ev=True` parameter on
  `get_pushfold_strategy` returns `{"strategy": prob, "ev_bb": ev}`.
  Closes the Marcus W1.5 chart-lookup PARTIAL. **PR #125.**
- **W4.2 (Priya limp-or-fold action menu)** — spec criteria (3-trash
  fold >=0.90) and (4 BB iso-raise / SB aggregate limp band)
  reclassified as informational-only when `bet_size_fractions=()` —
  subgame mode collapses equilibrium to per-hand equity comparison
  (`EV_limp > EV_fold iff equity > 0.25`), so the range-aware heuristic
  doesn't structurally apply. Wiring, action-set restriction, premium-hand
  LIMP, and wall-clock criteria remain hard PASS gates. **PR #128.**
- **W3.5 (Daniel monotone polarization)** — spec criterion
  `AA check ≥ 0.99` reclassified as **strict under the PoC's
  explicit-no-flush range setup** (called via `solve_range_vs_range_rust`
  directly per `W3_5_TRUE_nash_v1_5_1.md`) and **informational-only
  under the class-name API setup** (villain range as hand classes that
  include flush-carrying combos like `AKs`, `KQs`, `JTs`). PoC setup at
  v1.8.0 reproduces AA check = 1.0000 bit-clean at 3000 iter; class-name
  API result differs because flush combos in villain's range make AA a
  thin-value-bet candidate (mathematically correct Nash on a different
  range). **PR #130.**
- **W2.3 status update** — solve-phase wall-clock drops from >1200 s
  kill to **16.6 s** on the 8-class symmetric turn fixture (>72×
  production-scale speedup from PR #114 TerminalCache). KK defend
  = 1.0000; top-action 5/8 = 62%. **Best-response walk** (exploitability
  computation) is NOT cached by PR #114 and is a separate perf wall;
  W2.3's BLOCKED label is held pending user judgment on whether
  solve-side PASS satisfies W2.3 spec §B (per PR #120, HELD for review).
  See `docs/persona_post_pr114_retest_2026-05-27.md`.

Full per-workflow status:
`docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` (will be
superseded by `docs/persona_status_post_v1_8_2_shipped_<DATE>.md` at
ship time).

---

## Known issues remaining

The following are **NOT** resolved in v1.8.2 and remain open for future
work:

### A83 deep-cap Brown apples-to-apples residual (unchanged from v1.8.0)

Post-purge v1.5 Brown apples-to-apples PASSES on both K72 + A83 spots
under the reframed 4-layer SANITY gate; strict-per-cell |Δ| values
(K72 0.852, A83 0.907) reflect Nash multiplicity at deep-cap
indifference manifolds. The EV(action) invariance gauntlet (PR #98,
shipped in v1.8.2) is now the canonical sanity check for the residual.
See v1.8.0 release notes for the full Nash-multiplicity framing — no
delta in v1.8.2.

### Persona table — PARTIAL rows remaining

- **W2.1 (Sarah preflop chart)** — `solve_hunl_preflop` raises
  `ValueError`: requires `initial_hole_cards` (subgame mode only).
  Full-tree preflop "intractable without hand-class abstraction —
  reserved for post-v1 follow-up." The Phase A engine work for this
  lands on PR [#122][pr122] (full-tree preflop RvR engine, HELD for
  review at v1.8.2 compilation) and PR [#121][pr121] (chained
  orchestrator Phase A, HELD for review). Both stay HELD — major new
  features per project policy.
- **W2.2 (Sarah Range.diff per-combo frequencies)** — `Range.diff()`
  set-membership returns 56 combos (works); no per-combo frequency
  methods. **B10** (Range fractional refactor) blocker, tracked
  separately.
- **W2.3 (Sarah deep-stack turn RvR)** — see "Personas unblocked"
  above; solve-side >72× faster but exploitability compute (BR walk)
  is separate perf wall. PR #120 retest is HELD for user review of
  reclassification.
- **W2.4 (Sarah batch-solve CLI)** — CLI `batch-solve` calls
  `solve_hunl_postflop` (Python `DCFRSolver`), NOT the Rust vector RvR
  path. PR #114 doesn't reach this code path. Library-direct path
  still PASSes; CLI path remains INCONCLUSIVE-SLOW pending separate
  follow-on.
(W3.5 reclassified to PASS via PR #130 spec amendment — see "Personas
unblocked" above.)

### Engine / build carry-overs (unchanged from v1.8.0)

- **Apple Silicon arch hazard** (dev-environment, pre-existing) —
  pyenv's x86_64 Python can't load the arm64 `_rust.so`; use
  `.venv/bin/python`. See `CONTRIBUTING.md`.
- **`poker-solver` PATH shim quirk** (dev-environment, pre-existing) —
  if the shim fails with `ModuleNotFoundError`, use
  `./.venv/bin/poker-solver ...` or `python -m poker_solver.cli ...`.
  Full diagnostic at `docs/poker_solver_shim_fix_2026-05-26.md`.
- **`Range` fractional frequencies** — spec landed in PR #36; full
  implementation tracked separately (B10).
- **`.app` / `.dmg` notarization** — v1.8.2 `.dmg` is still ad-hoc-signed
  (same as v1.6.0 / v1.8.0). Apple Developer enrollment is a user
  carry-item.

---

## Migration / breaking changes

### DCFR α ≤ 0 now hard-fails

**Pre-v1.8.2:** `solve_kuhn(..., alpha=0.0, ...)` and other entry
points accepted α ≤ 0 silently. The resulting strategy was non-Nash
(positive regrets halved every iter; exploitability 50× worse than the
production default α=1.5 on Kuhn).

**v1.8.2:** all 4 DCFR solver constructors (Rust:
`DCFRSolver`, `PreflopDcfr`, `VectorDCFR`, `HUNLDcfr`; Python:
`DCFRSolver.__init__`, `solver._solve_rust`,
`range_aggregator.solve_range_vs_range_nash`) validate α and
**HARD-FAIL** on α ≤ 0 or non-finite (NaN, ±∞). The 5 PyO3 entries
surface this as `PyValueError`.

**Warn band:** 0 < α < 0.5 emits a `UserWarning` (Python) /
`eprintln!` (Rust) because Brown & Sandholm 2019 validates α=3/2 only
and values below 0.5 are below the paper's analyzed range. Silent OK
band starts at α ≥ 0.5.

**Production default α=1.5 is unchanged and unaffected.** Only callers
explicitly passing α=0 (e.g. attempting "disable positive-regret
discount") are impacted. If your downstream code does this, switch to
α=0.5 (minimum analyzed) or α=1.5 (PLAN production default).

### CLI surface additions (additive, not breaking)

- `poker-solver --version` (new global flag).
- `poker-solver river --walk-tree | --full-tree | --node | --top-n |
  --full-classes | --format {text|json|csv}` (new flags; legacy
  invocation byte-identical).
- `poker-solver subgame --street {flop|turn|river} ...` (new
  subcommand; `river` alias byte-identical to v1.8.2 legacy output).

No flags removed. No legacy invocations broken.

### Python API additions (additive, not breaking)

- `get_pushfold_strategy(..., return_ev=False)` — `return_ev=True`
  returns `{"strategy": prob, "ev_bb": ev}`. Default `False` returns
  the legacy `float`. No signature change for existing callers.

---

## Upgrade path

### From v1.8.0 source install

```bash
git pull
pip install -e .
maturin develop --release
```

The Rust binary `_rust.cpython-313-darwin.so` (or the equivalent on
your platform) **should be rebuilt** for the new
`TerminalCache` machinery and DCFR α-guard. `pip install -e .` alone is
not enough; you need `maturin develop --release` (or
`pip install -e . --force-reinstall` which triggers maturin rebuild).

### From the v1.8.0 `.dmg`

1. Delete the existing `Poker Solver.app` bundle (Finder → drag to
   Trash).
2. Download the v1.8.2 `.dmg` from the GitHub Release page (when
   published).
3. Drag-install as usual.

---

## Compatibility

- **CFR algorithm:** bit-identical SIMD-vs-scalar on the same convention
  (unchanged from v1.8.0). New `TerminalCache` is also bit-identical to
  the uncached path on the same convention (asserted by
  `cached_matches_uncached_terminal_value`).
- **CFR output vs v1.8.0:** bit-identical on Kuhn / Leduc / HUNL
  postflop subgame (no convention change since v1.8.0 PR #78). The
  213× river RvR perf improvement is a pure caching optimization with
  no algorithmic change.
- **Public Python API:** additive only (see "Migration / breaking
  changes" above).
- **Min Python:** unchanged from v1.8.0.
- **Min Rust toolchain:** stable, unchanged from v1.8.0.
- **`crates/cfr_core` version bump:** 0.8.0 → 0.8.2.
- **`pyproject.toml [project] version`:** 1.8.0 → 1.8.2 (skipping
  1.8.1 per fold-in decision).
- **`poker_solver/__init__.py __version__`:** 1.8.0 → 1.8.2 (same).

---

## Verification

Run the new bit-equality tests yourself:

```bash
# TerminalCache parity (Rust)
cargo test --release --lib --manifest-path crates/cfr_core/Cargo.toml \
    cached_matches_uncached_terminal_value

# DCFR α-guard (Rust + Python)
cargo test --release -p cfr_core --test test_dcfr_alpha_guard
pytest tests/test_dcfr_alpha_guard.py -v

# EV invariance gauntlet (slow, parity_noambrown — opt in)
pytest tests/test_ev_invariance_gauntlet.py -v -s -m parity_noambrown

# CLI walk-tree + subgame
pytest tests/test_cli_walk_tree.py tests/test_cli_subgame.py -v
```

Per-phase RvR profile bench (optional):

```bash
cargo bench --bench rvr_profile \
    --manifest-path crates/cfr_core/Cargo.toml \
    --features profile_rvr -- 1326 5 1 --full-tree
```

---

## Full PR list

All PRs that ship in v1.8.2, in merge order since v1.8.0 (`8a9c8d2`).
Compiled 2026-05-27 from main HEAD `f64ad5a`.

**Engine perf / quality (load-bearing):**

- [#114][pr114] `036a101` — perf: TerminalCache for vector-form RvR
  inner kernel (~213× speedup on full-tree river).
- [#113][pr113] `3ef9b76` — feat: HARD-FAIL DCFR `alpha<=0`, WARN
  `alpha<0.5` (HIGH-1 fix per PR #99 Option B).
- [#98][pr98]  `3cc5eba` — feat(tests): EV(action) invariance gauntlet
  against Brown (Nash-invariant cross-solver check).
- [#129][pr129] `5fec960` — feat: off-path infoset annotation in
  `SolveResult` (`reach_probability` + `off_path_keys`, closes #47).

**CLI surface:**

- [#127][pr127] `f2d7106` — feat(cli): `subgame` command for flop /
  turn / river (generalizes river, #51).
- [#125][pr125] `f098e1f` — feat(pushfold): `return_ev=True` parameter
  for Marcus W1.5 persona (#48).
- [#123][pr123] `8f173db` — feat(cli): walk-tree + per-class drill-down
  + JSON/CSV output (v1.8.2).
- [#116][pr116] `9b6fd1f` — feat(cli): `--version` flag (HIGH-deferred
  from PR #107 audit).

**Build / release hardening:**

- [#119][pr119] `00b15b8` — feat(release): encode 4 ship-script hazard
  checks (post-v1.8.0 hardening per memory cluster).
- [#95][pr95]  `cdb1c47` — fix(build): resolve APP_PATH to absolute
  before defaults read (.dmg build with default OUTPUT_DIR).
- [#89][pr89]  `6c913aa` — fix(build): patch Brown's `subgame_config.cpp`
  for GCC 11 incomplete-type build.

**Docs / test hygiene (v1.8.1 candidate fold-in + misc):**

- [#91][pr91]  `23f8966` — fix(tests): update Brown dump literals +
  chance_enum hole_cards post PR #69 + #78.
- [#96][pr96]  `9213085` — docs(v1.8.1): fix release-notes broken refs +
  PR #93 collision + silent-skip hazard.
- [#103][pr103] `faea951` — fix(ui): remove stale mock-mode banner
  (PR 10b shipped at v1.2.0).
- [#107][pr107] `362e484` — fix(docs): README/quickstart drift after
  v1.8.0 ship.
- [#111][pr111] `89ec90a` — test: add missing `@pytest.mark.slow` to
  2 river_diff_self_sanity tests.
- [#101][pr101] `949f8fe` — docs: disclose v1.8.0 GUI mock-mode in
  user-facing locations.
- [#115][pr115] `c4a7d6b` — docs(api): soften vector-RvR perf warning
  (PR #114 made it 213× faster).
- [#112][pr112] `d641d1a` — docs(api): add perf warning to vector-form
  RvR (HIGH-2 fix per PR #105 Option A+D; superseded by PR #114 +
  PR #115).
- [#94][pr94]  `d0cf7be` — docs(persona): post-v1.8.0 production-scale
  retest results.
- [#124][pr124] `6236702` — docs: W4.2 Priya production-scale
  investigation (#52).
- [#128][pr128] `f64ad5a` — docs(persona): reclassify W4.2 PARTIAL →
  PASS via spec amendment (task #62).
- [#130][pr130] `27e6b1d` — docs(persona): amend W3.5 spec to
  distinguish no-flush vs class-name API setups (reclassify FAIL →
  PASS, task #63).

**Proposals + decision matrices (informational):**

- [#99][pr99]  `c534bf0` — proposal: DCFR α-guard options (v1.8.1
  candidate; implemented in PR #113).
- [#105][pr105] `9c5b2b5` — proposal: vector-form RvR perf wall options
  (v1.8.2 candidate; implemented in PR #114).
- [#100][pr100] `4a096f3` — docs: v1.8.1 release decision matrix.

**Excluded from v1.8.2** (open at compilation time; HOLD-for-user-review):

- **PR [#120][pr120]** — `docs(persona): retest perf-blocked personas
  post-PR-114 (TerminalCache 213× win)`. Held for user judgment on
  W2.3 BLOCKED → PARTIAL reclassification.
- **PR [#121][pr121]** — `feat: preflop chained orchestrator Phase A
  (#31)`. Major new feature, HELD per project memory rule.
- **PR [#122][pr122]** — `feat: full-tree preflop RvR engine
  (#32 Phase A)`. Major new feature, HELD per project memory rule.
- **PR [#126][pr126]** — `feat(ui): True Nash RvR mode toggle
  (post-PR-114 perf unlock, #61)`. Major UI feature, HELD per project
  memory rule.

If any of these flip to MERGED before v1.8.2 ships, the user decides
whether to roll them into this release or defer to v1.8.3.

---

## Acknowledgments

This release closes:

- A ~200× perf wall on vector-form river RvR
  (`docs/perpetual_qa_findings_2026-05-27.md` HIGH-2 / PR #114).
- A silent non-Nash hazard on DCFR α ≤ 0
  (`docs/perpetual_qa_findings_2026-05-27.md` HIGH-1 / PR #113).
- The Marcus W1.5 chart-EV PARTIAL (PR #125), Priya W4.2 spec
  mismatch PARTIAL (PR #128), and Daniel W3.5 range-setup-mode FAIL
  (PR #130).
- The user-issue #47 off-path infoset filtering ask (PR #129).
- The post-v1.8.0 audit doc-hygiene backlog (PRs #91 / #95 / #96 /
  #103 / #107 / #111 / #124 / #128 / #130).
- The post-v1.8.0 release-process burst lessons (encoded as
  programmatic hazard checks in PR #119).

Thanks to the persona-test framework (Marcus W1.5, Priya W4.2, Sarah
W2.3) for empirically anchoring the engine and CLI work that motivated
this release.

---

## What's next

- **v1.8.3+** candidates: best-response walk caching for the W2.3
  exploitability-compute perf wall; True Nash UI toggle default
  (PR #126); persona-spec hygiene update for W3.5 (class-name vs
  explicit-no-flush API distinction).
- **v1.9 candidate:** full-tree preflop solver (chained orchestrator
  PR #121 + RvR engine PR #122 Phase A → Phase B caching + parallel).
- **v2.0:** EMD bucketing for flop interactive viability (the W2.3 /
  W3.4 / W2.1 / W2.4 lever once best-response caching lands).

---

[pr89]: https://github.com/amaster97/poker_solver/pull/89
[pr91]: https://github.com/amaster97/poker_solver/pull/91
[pr94]: https://github.com/amaster97/poker_solver/pull/94
[pr95]: https://github.com/amaster97/poker_solver/pull/95
[pr96]: https://github.com/amaster97/poker_solver/pull/96
[pr98]: https://github.com/amaster97/poker_solver/pull/98
[pr99]: https://github.com/amaster97/poker_solver/pull/99
[pr100]: https://github.com/amaster97/poker_solver/pull/100
[pr101]: https://github.com/amaster97/poker_solver/pull/101
[pr103]: https://github.com/amaster97/poker_solver/pull/103
[pr105]: https://github.com/amaster97/poker_solver/pull/105
[pr107]: https://github.com/amaster97/poker_solver/pull/107
[pr111]: https://github.com/amaster97/poker_solver/pull/111
[pr112]: https://github.com/amaster97/poker_solver/pull/112
[pr113]: https://github.com/amaster97/poker_solver/pull/113
[pr114]: https://github.com/amaster97/poker_solver/pull/114
[pr115]: https://github.com/amaster97/poker_solver/pull/115
[pr116]: https://github.com/amaster97/poker_solver/pull/116
[pr119]: https://github.com/amaster97/poker_solver/pull/119
[pr120]: https://github.com/amaster97/poker_solver/pull/120
[pr121]: https://github.com/amaster97/poker_solver/pull/121
[pr122]: https://github.com/amaster97/poker_solver/pull/122
[pr123]: https://github.com/amaster97/poker_solver/pull/123
[pr124]: https://github.com/amaster97/poker_solver/pull/124
[pr125]: https://github.com/amaster97/poker_solver/pull/125
[pr126]: https://github.com/amaster97/poker_solver/pull/126
[pr127]: https://github.com/amaster97/poker_solver/pull/127
[pr128]: https://github.com/amaster97/poker_solver/pull/128
[pr129]: https://github.com/amaster97/poker_solver/pull/129
[pr130]: https://github.com/amaster97/poker_solver/pull/130
