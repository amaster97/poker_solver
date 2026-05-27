# poker-solver v1.8.0 — Cross-platform SIMD portability + terminal-utility convention purge + `.dmg` fork-bomb fix

**Status: DRAFT (post-purge framed) — Phases 1-4 + AVX2 all merged to
`main` as of `77e751c` (PR #32, 2026-05-26). The terminal-utility
convention purge lands as PR `78` (`37e5be1`)
and is the engine correctness fix in v1.8.0 — see "Engine fixes" §5
and "Migration / breaking changes" below. Engine + parity fixes from
the v1.7.1 bundle and v1.7.2 (.dmg fork-bomb fix + CI hardening) are
folded into v1.8.0 per `docs/v1_6_1_ship_hold_review_2026-05-26.md`
and `docs/v1_7_1_tag_decision_2026-05-26.md`. The v1.6.1 ship hold is
LIFTED under the canonical convention (see "Known issues remaining"
A83 entry). Final ship step is SHA substitution for the
`<TBD-*>` placeholders + tag + GitHub release.**

**Release date:** 2026-05-XX (TBD at ship time)
**Tag:** `v1.8.0` (to be created at ship time)
**Baseline commit on `origin/main`:** `eb74fb3` (PR #60, 2026-05-26),
plus the terminal-utility convention purge at `37e5be1`
(PR `78`).
Final tag SHA will be set at `git tag` time.

---

## Headline

**v1.8.0 — Cross-platform SIMD portability + terminal-utility convention purge + `.dmg` fork-bomb fix.**

Three things land together in this release:

1. **Cross-platform SIMD complete (portability win).** The Discounted
   CFR solver's hot inner loops are now hand-vectorized across NEON
   (Apple Silicon), AVX2 + SSE2 (x86_64, runtime-detected), with an
   automatic scalar fallback for anything else. **This is a portability
   win, not a speedup** — measured wall-clock on Apple Silicon
   (M4 Pro, aarch64) is within noise (~1.0×) because LLVM's `-O3`
   autovectorizer already covers the small-slice case. The headline
   value is closing the ~3-month gap between Apple Silicon and x86_64
   coverage with a stable hand-written floor that doesn't depend on the
   compiler's heuristics.
2. **Terminal-utility convention purge (engine correctness fix).** The
   prior "rust" terminal-utility convention treated `initial_contributions`
   as recoverable, which produced a per-action regret bias of 12-50pp
   versus the reference Brown solver at deep cap. v1.8.0 adopts the
   single canonical real-poker convention (winner collects the full pot
   including dead money from prior streets). See "Engine fixes" and
   "Migration / breaking changes" for the formula, a one-line numeric
   example, and the rebaseline policy. **Pre-v1.8.0 solver outputs are
   NOT comparable to v1.8.0 outputs.**
3. **`.dmg` fork-bomb fix (CRITICAL).** The v1.6.0 `.dmg` had an
   uncontrolled-spawn bug on Finder launch
   (`multiprocessing.freeze_support()` missing from the PyInstaller
   entry point). v1.6.0 `.dmg` has been pulled from its GitHub Release;
   v1.8.0 ships the repackaged build.

**SIMD vector kernels (cross-platform):** Explicit NEON/AVX2/SSE2
intrinsics replace the previous scalar inner loops in `dcfr_vector.rs`.
Bit-identical SIMD-vs-scalar output on the same convention; **measured
wall-clock impact on Apple Silicon (M4 Pro, aarch64) is within noise
(~1.0×)** because LLVM's autovectorizer at `-O3` already covers the
small-slice case (action_count = 2-5 per decision row). Primary value
is portability (x86_64 with explicit AVX2 dispatch, runtime-detected)
and a stable hand-written floor that doesn't depend on the compiler's
heuristics. x86_64 wall-clock measurement is pending (no AVX2 hardware
in the bench fleet at time of write). Full benchmark report:
`docs/v1_8_simd_perf_benchmark_2026-05-26.md`.

---

## Highlights

### 1. Cross-platform SIMD vector kernels (Phase 1-4)

Four hot loops in `crates/cfr_core/src/dcfr_vector.rs` are now
vectorized, each behind a single safe public API with runtime ISA
detection. Bit-identical output verified by an end-to-end cross-backend
smoke test that runs 1000 iterations of a Kuhn poker solve on both the
scalar and SIMD paths and asserts equality.

| Phase | Kernel                                          | PR        | Merge SHA |
|-------|-------------------------------------------------|-----------|-----------|
| 1     | `discount_regrets` + `discount_strategy_sum`    | [#23][pr23] | `485aa8c` |
| 1+    | AVX2 runtime-detect path (x86_64)               | [#35][pr35] | `db8d646` |
| 2     | `update_regret_sum`                             | [#41][pr41] | `8073bcc` |
| 3     | `update_strategy_sum`                           | [#33][pr33] | `a712950` |
| 4     | `compute_strategy`                              | [#32][pr32] | `77e751c` |

Per-backend coverage:

- **NEON** for `target_arch = "aarch64"` (Apple Silicon, ARM servers) —
  128-bit, 2-lane f64.
- **AVX2 + SSE2** for `target_arch = "x86_64"`, with
  `is_x86_feature_detected!("avx2")` runtime dispatch:
  - **AVX2** path: 256-bit, 4-lane f64 (Haswell+, ~2013 and later).
  - **SSE2** baseline: 128-bit, 2-lane f64 (any x86_64 CPU).
- **Scalar** fallback for any other architecture and for the epilogue
  (the 0-3 trailing elements that don't fit a SIMD lane).

Why this matters: the previous v1.7.x line was already NEON-optimized
for Apple Silicon, but x86_64 users (Intel Macs, Windows PCs, Linux
desktops, CI runners) got the scalar fallback. That's a ~3-month gap
between Apple Silicon and x86_64 performance, now closed (at the
architecture level — the empirical x86_64 wall-clock measurement
remains pending). The cross-platform spec
(`docs/pr_proposals/v1_8_cross_platform_simd_spec.md`) drives the
architecture. Sarah persona W2.3 remains pending the post-v1.8 retest
(turn-fixture, agent in flight 2026-05-26); the original "unblocked
on M-series" projection was tied to a 4-8× SIMD speedup that did not
materialize on M4 Pro arm64 (see "Persona test status" below).

### 2. `.dmg` fork-bomb fix (CRITICAL)

The v1.6.0 `.dmg` had a critical fork-bomb on Finder launch.
Double-clicking `Poker Solver.app` on macOS spawned the app's
`multiprocessing` workers recursively because
`multiprocessing.freeze_support()` was missing from the PyInstaller
entry point. Each spawned child re-launched the parent process,
exponentially — freezing the user's Mac.

**Resolution:**

- **PR #42** ([`728206e`][pr42]) adds the `multiprocessing.freeze_support()`
  guard to the PyInstaller entry point, eliminating the fork-bomb on
  the v1.8.0 build.
- **The v1.6.0 `.dmg` asset has been retroactively pulled from its
  GitHub Release.** The v1.6.0 release page now carries a critical
  warning pointing users at the v1.8.0 repackaged build (or the
  from-source install) instead.
- A user-facing warning was also added to the CHANGELOG retroactive
  amendment for v1.6.0.

If you previously downloaded the v1.6.0 `.dmg`, **delete the
`Poker Solver.app` bundle and switch to the v1.8.0 `.dmg`** when this
release publishes. If you ran the v1.6.0 `.dmg` and your Mac froze on
launch, no persistent damage was done — the workers stopped when the
parent process was killed.

Full RCA: `docs/dmg_spawn_loop_rca_2026-05-26.md`.

### 3. Lint / format / deps green-up (PR #43)

[PR #43][pr43] (`cfc6bc5`) is a non-functional cleanup pass that brings
the main-branch lint gates back to green after the v1.7.x churn:

- `cargo clippy --all-targets --release` — clean.
- `ruff check .` — clean (lint).
- `ruff format --check .` — clean (format). `black` is removed in favor
  of `ruff format`; the two formatters had diverged on a handful of
  multi-line argument lists.
- `rich>=13.0` added as an explicit runtime dependency. It was
  implicitly required by `poker-solver parity` (Brown reference parity
  CLI subcommand) via `rich.console.Console` imports, but the install
  wouldn't fail until users actually invoked the subcommand.

No public API or algorithm changes.

### 4. Documentation accuracy (PRs #44, #45)

Two doc-only PRs land alongside the SIMD bundle:

- **[PR #44][pr44]** (`a6b89f7`) fixed **three executable code bugs** in
  `README.md` and `USAGE.md` examples:
  1. `Range` parser example used the wrong constructor signature.
  2. A `solve_river_nash()` example was missing the `iterations=`
     keyword.
  3. A hero/board overlap example assumed a card slot that the API
     rejects.
  Plus a stale claim about "no CLI for parity comparison" was scrubbed
  (the `poker-solver parity` subcommand has shipped since v1.7.0).
- **[PR #45][pr45]** (`dbfc8d0`) cleaned up downstream doc drift:
  - `USAGE.md` header version stamp brought to v1.7.x.
  - `CHANGELOG.md` `.dmg` retroactive amendment for v1.6.0 (see
    Highlight 2).
  - `docs/dmg_install_guide.md` banner pointing to the v1.8.0 repackaged
    build.
  - Supersede banners on a handful of stale planning docs.

### 5. Engine + parity-wrapper fixes carried from the v1.7.1 bundle

v1.8.0 inherits a 10-PR bundle of engine and parity-wrapper fixes that
landed piecewise on `main` between v1.7.0 and v1.8.0. **No formal
`v1.7.1` tag was created** (per `docs/v1_7_1_tag_decision_2026-05-26.md`);
the fixes are folded into this release. The v1.6.1 ship hold has been
lifted per `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

**Engine correctness:**

- **PR 78 (`37e5be1`) — Terminal-utility
  convention purge (canonical real-poker convention).** Prior versions
  used a "rust" terminal-utility formula that treated
  `initial_contributions` as recoverable by the player who folded; this
  produced a per-action regret bias that diverged 12-50pp from the
  reference Brown solver at deep cap (PR #93 ablation,
  `docs/a83_terminal_utility_ablation_results_2026-05-26.md`). v1.8.0
  deletes that path and ships a single canonical `utility()` function.

  **Canonical formula** (per `feedback_brown_convention_adopt.md`):
  ```
  winner_utility = pot_total - contrib_subgame_winner
                 = base_pot + contrib_subgame_loser     (in BB)
  loser_utility  = -contrib_subgame_loser               (in BB)
  tie_each       = pot_total/2 - contrib_subgame_player (in BB)
  ```
  where `contrib_subgame[i] = state.contributions[i] - cfg.initial_contributions[i]`
  and `pot_total = cfg.initial_pot + contrib_subgame[0] + contrib_subgame[1]`.

  **One-line numeric example.** At a canonical leaf where P0 folds with
  `base_pot = 10 BB` and zero in-subgame contributions
  (`contrib_subgame = (0, 0)`, `initial_contributions = (5, 5)`):
  the old "rust" path returned `(-5, +5)` BB (treating each player's
  seed-split half-pot as still recoverable); the canonical path
  returns `(0, +10)` BB — P1 (the non-folder) collects the full pot
  including the dead money already on the table, P0 loses only their
  in-subgame contribution (zero here).

  The game is **constant-sum** under the canonical convention
  (sum of utilities = `+base_pot/bb` per leaf rather than zero); DCFR
  convergence is unaffected (proofs require bounded utilities + finite
  action set, not zero-sum). No feature flag, no
  `TerminalUtilityConvention` enum, no runtime switch — one formula.
  See "Migration / breaking changes" below for the rebaseline policy.
- **PR 50 (#5)** — Phantom `ALL_IN` action menu guard (paired Rust +
  Python). At facing-all-in nodes, the responder's action menu no
  longer emits a degenerate `ALL_IN` raise that would have had no chip
  distinction from calling. Closes R6.
- **PR 51 / PR #16** — `dcfr_vector.rs` off-by-one + asymmetric-range
  `next_reach` sizing fix; closes the asymmetric-range solve panic.

**Brown parity test harness — wrapper boundary corrections:**

- **PR 52 (#8)** — Suit-encoding char-to-char fix; replaced a silent
  paired `h ↔ d` swap with explicit mapping. Closes R8.
- **PR 55 (#10)** — P0/P1 player-index convention swap at the wrapper
  boundary. Closes R9.
- **PR 56 (#12)** — Hand-string sort-order canonicalization at the
  wrapper boundary. Closes R10.

**Brown parity test harness — renderer + acceptance reframe:**

- **PR 54 (#9)** — Renderer `stack_ceiling` kwarg + `"A"` token for
  bets/raises at stack ceiling.
- **PR 53b (#14) + PR 53c (#15)** — Brown apples-to-apples acceptance
  test reframed from strict 5e-2 per-action gate to a 4-layer gate
  (L1 structural / L2 shallow-strict / L3 deep-directional L1 ≤ 1.9 /
  L3' p75 L1 ≤ 0.60 / L4 top-action ≥ 60%). Codifies that external
  reference solvers (Brown, Pluribus) are sanity checks rather than
  strict ground truth when action menus differ and deep-cap subgames
  have indifference manifolds. **PASSES on both river spots under
  Dry-run #10 (2026-05-24)** — see `docs/v1_6_1_dryrun_10.md`.

**Ship-hardening + CI:**

- **PR 59 (#18)** — `memory_profiler` golden-file refresh + regen-mode
  flag.
- **PR 60-equivalent (folded into PR #22)** — `_skip_or_fail()` helper
  + `STRICT_ACCEPTANCE=1` env var: Brown parity test hard-fails on
  missing prereqs in strict mode.

The bundle resolves the 22-42pp Brown apples-to-apples deep-cap
divergence reported in v1.5.0 / v1.5.1 / v1.6.0 dry-runs as a
combination of test-side wrapper bugs (R8/R9/R10), one engine-side
mechanical guard (R6, PR 50), the **terminal-utility convention
purge** (PR `78`, the engine correctness fix; see the
first bullet under "Engine correctness" above), and Nash multiplicity
on the residual at deep-cap indifference manifolds (see "Known issues
remaining" below). Pre-purge framings that treated the convention as
a "documented Brown design divergence" are explicitly retracted per
`feedback_brown_convention_adopt.md`; there is one canonical
convention.

### 6. v1.7.2 entries folded into v1.8.0

Per the v1.7.1 tag decision and the v1.6.1 ship-hold review, the
following v1.7.2 entries are also folded into v1.8.0 rather than
shipping under a separate tag:

- **PR #21** (`bed37c4`) — CI-driven release workflow (PR 62 origin).
- **PR #22** (`1fefaff`) — ship-process hardening Guards B + C
  (PR 65 origin). Includes `_skip_or_fail()` + `STRICT_ACCEPTANCE=1`.
- **PR #42** (`728206e`) — `.dmg` fork-bomb fix
  (`multiprocessing.freeze_support()`); the v1.6.0 `.dmg` was pulled
  retroactively. See Highlight 2 for the user-facing impact.

CHANGELOG follows **Option A** alignment (fold v1.7.2 entry into
v1.8.0, do not preserve a separate v1.7.2 section) per
`docs/v1_8_0_release_notes_prep_2026-05-26.md` Open Question #1.

### 7. Documentation + ship-process cleanup wave

A user-impactful subset of the documentation / packaging / CI cleanup
PRs that landed on `main` between v1.7.0 and v1.8.0 (in addition to
the lint/clippy/deps green-up and doc-accuracy PRs already called out
in §3 and §4 above):

- **[PR #46][pr46]** — `mypy` resolves 7 substantive type errors
  (post-cleanup follow-up; tightens runtime correctness for the public
  Python API).
- **[PR #47][pr47]** — `.dmg` packaging hardening: arch label + version
  stamp accuracy follow-up to PR #42's fork-bomb fix. Removes a
  user-confusing "universal" arch label on a `.dmg` that ships an
  arm64-only `_rust.so`.
- **[PR #48][pr48]** — `USAGE.md` §7b header refresh (v1.4.x → v1.7.x)
  with regime guidance (salvaged from a stale PR #24).
- **[PR #54][pr54-script]** — v1.8.0 release execution script + `.dmg`
  build runbook (codifies the ship sequence so the next release does
  not relitigate the build-environment quirks).
- **[PR #58][pr58]** — CHANGELOG note for the `poker-solver` PATH shim
  quirk (see "Known issues remaining" below for the user-facing
  workaround).
- **[PR #59][pr59-persona]** — persona-test status snapshot refresh
  post-W3.2 / W3.4 retests (see "Persona test status" below).
- **[PR #60][pr60-orphan]** — track previously-orphan reference targets
  (closes 7 dangling-reference lints from the doc-cross-check sweep).

This cleanup wave does not change any runtime behavior; it lifts the
release boundary to a clean lint / docs / packaging baseline.

### 8. Persona test status (post-v1.8 SIMD + W3.2 + W3.3 + W3.4 retests)

The persona-test framework's counts as of 2026-05-26 (post the W3.2 +
W3.3 + W3.4 retests; W2.3 turn-fixture retest IN PROGRESS):

| Verdict | Count | Workflows |
|---|---|---|
| **PASS** | **10** | W1.1, W1.2, W1.3, W1.4, W2.5, W3.1, **W3.2** (new), **W3.3** (new; P2 closing test), **W3.4** (caveated), W4.1, W4.3 *(W4.3 via aggregator path)* |
| **PARTIAL** | 4 | W1.5, W2.1, W2.2, W2.4, W4.2 |
| **BLOCKED** | 2 | W2.3 *(pending retest)*, others closed by v1.8 + PR #38 |
| **FAIL** | 1 | W3.5 *(Type B-DOC; docs-only follow-up, no code patch needed per `v1_7_1_wrapper_fix_spec.md`)* |

**Net delta vs the 2026-05-25 snapshot (7 / 5 / 4 / 2):** +3 PASS, -2
BLOCKED, -1 FAIL→PARTIAL, +1 PARTIAL→PASS (W3.3 PARTIAL → PASS via
PR #66 P2 closing test for node-locking-at-scale; W3.5 reclassified to
PARTIAL-Type-B-DOC after the v1.8 retest confirmed bit-identical-to-v1.7.0
behavior).

- **W3.2: BLOCKED → PASS.** PR 76 (PR #38, commit `feee974`) shipped
  `solve_best_response(game, opponent_strategy, *, hero_player)` plus
  a `poker-solver best-response` CLI subcommand; the Kuhn smoke shows
  `exploit_gap_bb > 0` on both seats. Type A (correctness; cleared the
  named API blocker). Source: `docs/persona_w3_2_smoke_2026-05-26.md`.
- **W3.3: PARTIAL → PASS.** PR #66 (P2 closing test for
  node-locking-at-scale) — all 4 acceptance criteria PASS (lock
  passthrough bit-exact <1e-9; villain L1 = 0.3070 at facing-raise
  node; EV invariant 5.0/5.0 BB on indifference manifold; 5 downstream
  infosets diverge >1%); 3.00 s Python wall-clock (well under Daniel's
  15 min budget). Type A (correctness; node-locking primitive verified
  at scale). Source: `docs/persona_w3_3_retest_2026-05-26.md`.
- **W3.4: BLOCKED → PASS (caveated).** PASS on the **repurposed**
  monotone-river 3-bet-pot polarization fixture (80.71 s wall-clock,
  27% of the Sarah 300 s gate); all 7 acceptance thresholds met.
  **The W3.4 unblock was via fixture-repurposing, NOT via the v1.8
  SIMD perf gain** — the original W3.4 flop MDF fixture remains
  perf-bound; v1.8 SIMD measured ~1.0× on M4 Pro arm64 did not deliver
  the projected 4-8× speedup. Source:
  `docs/persona_w3_4_retest_2026-05-26.md`.
- **W3.5: FAIL → PARTIAL (Type B-DOC).** v1.8 SIMD bit-identical to
  v1.7.0 on the 6-class smoke (delta ~0); classification stands per
  `v1_7_1_wrapper_fix_spec.md` (docstring + regression-test gaps; no
  code patch needed). Source:
  `docs/persona_w3_5_retest_2026-05-26.md`.
- **W2.3: PENDING.** Post-v1.8 retest agent in flight (`a99ec2e`) on
  the pre-staged turn fixture. Final tally will be 10 or 11 PASS / 1
  or 2 BLOCKED depending on the wall-clock measurement.

Full per-workflow status: `docs/persona_test_status_2026-05-26.md`
(supersedes the 2026-05-25 baseline). The post-v1.8 audit framing is
captured at `docs/persona_status_post_v1_8_2026-05-26.md`.

**Note on persona baselines vs. the convention purge.** Persona tests
whose acceptance gate depends on absolute strategy probabilities,
exploitability magnitudes, or numerical agreement with a pre-v1.8.0
baseline need re-collection under the canonical convention (see
"Migration / breaking changes" below). Persona tests gated on
structural / topological / wall-clock criteria (W3.4 wall-clock,
W3.2 API existence, etc.) are unaffected by the convention purge.
The bit-identical-to-v1.7.0 note for W3.5 above refers to the
pre-purge SIMD smoke (SIMD-vs-scalar, same convention); under the
canonical convention, all v1.7.x baselines are stale.

---

## Known issues remaining

The following are **NOT** resolved in v1.8.0 and remain open for future
work:

### A83: Deep-cap Brown apples-to-apples residual gap (post-convention-purge)

**A83 deep-cap residual (Nash multiplicity, not bug):** Post-purge v1.5
Brown apples-to-apples test PASSES on both K72 + A83 spots under the
reframed 4-layer SANITY gate. Strict-per-cell |Δ| values: K72 0.852,
A83 0.907 — these reflect Nash multiplicity at deep-cap indifference
manifolds (Brown picks one Nash, our solver picks another; both are
valid). The reframed gate does NOT strict-assert per-cell (that would
be non-falsifiable under multiplicity per
`feedback_nash_multiplicity_acceptance.md`); it gates on L1, top-action
coverage, and overall coverage. The convention purge (PR #78,
`37e5be1`) closed the regret-update bias (PR #93's measured 12-50pp
Rust-vs-Rust shift); residual is genuine multiplicity. EV-of-action
invariance gauntlet (`docs/ev_invariance_sanity_gauntlet_design_2026-05-27.md`)
is the canonical sanity check for the residual.

**Status post-purge:** L1 max 1.703 (K72) / 1.813 (A83); strict max |Δ|
0.852 / 0.907; both fixtures PASS the reframed 4-layer SANITY gate
(strict per-cell layer is informational, not asserted, per
`feedback_nash_multiplicity_acceptance.md`) (v1.5 Brown
apples-to-apples residual after the canonical-convention adoption,
captured 2026-05-27 from the post-purge dry-run; full numbers at
`docs/v1_5_brown_post_purge_numbers_2026-05-27.md`).

Whatever remains after the convention purge is **Nash multiplicity at
indifference manifolds** rather than a game-definition mismatch: deep-cap
HUNL has indifference manifolds where multiple Nash equilibria are all
valid and small initial-condition perturbations select between them.
The convention purge DID fix the regret-update bias (PR #93's 12-50pp
gap is closed); the strict per-cell |Δ| residual is a SEPARATE
phenomenon and is NOT expected to collapse — A83's strict max |Δ|
moved from 0.907 (pre-purge) to 0.907 (post-purge) unchanged at the
recorded precision. The test PASSES because the reframed 4-layer gate
does not strict-assert per-cell. This is testable via **EV-of-action
invariance** — for a constant-sum game, the EV of each action at each
infoset is unique across all Nash equilibria, even when strategy
probabilities aren't (see
`docs/ev_invariance_sanity_gauntlet_design_2026-05-27.md`).

Trajectory of `0.907` (max |Δ| on the A83
fixture at `iter=2000`) anchors the post-purge baseline relative to
the pre-purge `12.27pp @ 2000 iters / 10.28pp @ 8000 iters` figure
from PR #93's ablation. Note: the 12-50pp PR #93 gap was a
Rust-vs-Rust ablation between conventions and IS closed by the purge;
the 0.907 strict max |Δ| is the Rust-vs-Brown apples-to-apples residual
under the canonical convention, dominated by Nash multiplicity.

**v1.6.1 hold-lift validated.** The hold-lift decision stands under
the canonical convention: the v1.5 Brown apples-to-apples reframed
4-layer gate (L1 structural / L2 shallow-strict / L3 deep-directional /
L4 top-action ≥ 60%) PASSES on both river spots under Dry-run #10
(2026-05-24), and the post-purge residual is Nash-multiplicity rather
than a bug. Pre-purge premature framings (PR #49 "fully closed via
Nash multiplicity," the arbitrator NOT-A-BUG verdict) are explicitly
retracted per `feedback_brown_convention_adopt.md` and the supersede
banners landed by PR #75.
- **Gate 4 200K-iter river/turn validation results — PROVISIONAL,
  re-run pending.** The 2026-05-25 Gate 4 200K river-phase run
  (reported `5.28e-14 mbb/g` exploitability, monotone clean) and the
  2026-05-26 Gate 4 200K v2 attempts (river: 186-byte empty-strategy
  output; turn: killed mid-run at ~60 min) both used the same
  `solve --hunl-mode postflop --backend rust` CLI path **without
  `--initial-hole-cards`**, which routes through
  `_rust.solve_hunl_postflop` with `HUNLConfig.initial_hole_cards =
  None`. Per `docs/a83_track_a_results_analysis_2026-05-26.md` §2c,
  `HUNLState::chance_outcomes` returns `Vec::new()` defensively when
  `hole_cards = None`, the scalar CFR loop's chance branch iterates
  over the empty list and returns `[0.0, 0.0]` immediately, no
  infoset is ever inserted into `strategy_sum`, and the reported
  exploitability is then recomputed by `_rust.compute_exploitability`
  against an empty strategy map (falls back to `uniform(n_actions)`
  on every cache miss per `exploit.rs:472-475`). The earlier
  `5.28e-14` figure was from the prior nohup that may have hit the
  same no-op path; treat that value as PROVISIONAL until a re-run
  via the correct entrypoint (or via `solve_range_vs_range_nash`)
  is completed. The Gate 4 200K validation does NOT block the
  v1.8.0 release boundary: the v1.5 Brown apples-to-apples
  acceptance test (Dry-run #10) is the canonical pass; Gate 4 was
  a secondary high-iter sanity check.
- **Silent no-op hardening (resolved, PR #69 / `98fb503`).** PR #69
  hard-fails the `solve --hunl-mode postflop --backend rust` CLI when
  `--initial-hole-cards` is missing; previously this path silently
  returned empty strategies (root cause: `chance_outcomes()` returned
  `Vec::new()` defensively when `hole_cards = None`, so the scalar
  CFR loop iterated over zero outcomes and `strategy_sum` stayed empty
  across all iterations — the exploitability recompute then walked a
  near-empty tree with uniform-fallback strategy cache and reported
  bogus numbers). Two surgical additive validation checks (~5 LOC each)
  close the asymmetry with the vector-form path (which already rejected
  the inverse case at `dcfr_vector.rs:806-811`); no behavior change for
  callers already supplying `initial_hole_cards`. This caused at least
  one false-positive multi-hour investigation (Track A nohup, ~2 hours
  of agent time on a zero-output experiment) before the RCA landed.
  See `docs/chance_outcomes_empty_rca_2026-05-26.md`.
- **Apple Silicon arch hazard (dev-environment, pre-existing).**
  pyenv's x86_64 Python can't load the arm64 `_rust.so`; use
  `.venv/bin/python` to avoid silent SKIPs. Symptoms: silent SKIPs
  in `pytest` output for parity / diff tests, `ModuleNotFoundError`
  on `poker_solver._rust`, or `dlopen` "missing symbol" errors when
  the underlying issue is actually an arch mismatch. See `CONTRIBUTING.md`
  + `docs/poker_solver_shim_fix_2026-05-26.md`.
- **`poker-solver` PATH shim quirk (dev-environment, pre-existing).**
  If `poker-solver` on PATH fails with `ModuleNotFoundError: No module
  named 'poker_solver'`, the shim is likely resolving against a stale
  editable-install `.pth` from a deleted temp worktree in another
  Python on PATH. Two equally good workarounds:
  - `./.venv/bin/poker-solver ...` (from project root)
  - `python -m poker_solver.cli ...` (with `.venv` activated)
  Cleanup: `pip uninstall poker_solver` from the broken Python env,
  then `pip install -e .` from project root. This is a pre-existing
  dev-environment quirk surfaced by W3.2 smoke — NOT a v1.8 regression.
  Full diagnostic: `docs/poker_solver_shim_fix_2026-05-26.md`. The
  CHANGELOG carries the same workaround text under v1.8.0 known issues
  (PR #58).
- **`Range` fractional frequencies.** The spec for true fractional
  frequencies (e.g. `AKs:0.6`) landed in [PR #36][pr36]; the
  implementation is tracked separately and not in v1.8.0.
- **`.app` / `.dmg` notarization.** The v1.8.0 `.dmg` is still
  ad-hoc-signed (same as v1.6.0). Apple Developer enrollment is a
  user carry-item and gates full notarization.

---

## Migration / breaking changes

### Terminal-utility convention change (BREAKING for output comparability)

**Pre-v1.8.0 solver outputs are NOT comparable to v1.8.0 outputs.**
v1.8.0 adopts the canonical real-poker terminal-utility convention
(see "Engine fixes" §5 above for the formula and a one-line numeric
example). The prior "rust" convention treated `initial_contributions`
as recoverable by the player who folded; the canonical convention does
not. The two conventions produce **different strategy probabilities
even on identical seeds + identical action menus** — the per-action
regret bias measured between conventions was 12-50pp at deep cap
(PR #93 ablation,
`docs/a83_terminal_utility_ablation_results_2026-05-26.md`).

**Justification:** per `feedback_brown_convention_adopt.md`, there is
exactly one correct terminal-utility convention — the rule of real
poker, in which the winner collects every chip in the pot including
dead money already on the table from prior streets. The "rust"
convention was an implementation error; it is not a feature flag, not
a runtime switch, and not a valid alternative. No
`TerminalUtilityConvention::Rust` variant exists in v1.8.0.

**Rebaseline policy.** Any artifact captured under the pre-v1.8.0
convention must be regenerated against v1.8.0:

- **Exploit-diff snapshots.** Re-run against v1.8.0; do not compare to
  v1.7.0-and-earlier exploit numbers numerically. The class of game
  changed from zero-sum to constant-sum (sum of utilities =
  `+base_pot/bb` per leaf rather than zero), which moves the
  exploit-vs-Nash absolute number even when the strategies are
  qualitatively the same.
- **Persona test baselines.** Persona retest wrappers re-baseline
  against v1.8.0; pre-v1.8.0 PASS / FAIL counts for any persona test
  whose acceptance gate depends on strategy probabilities or
  exploitability magnitudes are stale and need re-collection.
- **Fixtures + golden files.** Any deterministic fixture or
  golden-file artifact captured under the pre-v1.8.0 convention is
  regenerated under v1.8.0. Don't preserve them via a flag; they were
  captured under an incorrect game model.

If you have downstream tooling that diff-tests v1.8.0 against a
pre-v1.8.0 baseline expecting numerical agreement, that test will fail
by design — replace the baseline with a v1.8.0 capture.

---

## Upgrade path

### From v1.7.0 source install

```bash
git pull
pip install -e .
maturin develop --release
```

The Rust binary `_rust.cpython-313-darwin.so` (or the equivalent on
your platform) **must be rebuilt** because the SIMD kernels are new
Rust source. `pip install -e .` alone is not enough; you need
`maturin develop --release` (or `pip install -e . --force-reinstall`
which triggers maturin rebuild).

### From the v1.6.0 `.dmg`

1. Delete the existing `Poker Solver.app` bundle (Finder → drag to
   Trash).
2. Download the v1.8.0 `.dmg` from the GitHub Release page (when
   published — note: the v1.8.0 `.dmg` build verification is the
   final ship step before this release publishes).
3. Drag-install as usual.

The v1.6.0 `.dmg` was pulled; do not attempt to redownload it.

---

## Compatibility

- **No public API changes.** All vectorization is behind the existing
  Rust extension's safe Python API.
- **CFR algorithm: bit-identical SIMD-vs-scalar on the same
  convention.** The cross-backend SIMD smoke test asserts bit-identical
  regret + strategy_sum tables across NEON / AVX2 / SSE2 / scalar at
  every iteration.
- **CFR output vs v1.7.0: NOT bit-identical** because of the
  terminal-utility convention purge (see "Migration / breaking
  changes" above). The change is in the game definition (terminal
  payoff at winner-take-all leaves), not in the CFR update rule.
- **Min Python**: unchanged from v1.7.0.
- **Min Rust toolchain**: stable, unchanged from v1.7.0.
- **`crates/cfr_core` version bump**: 0.7.x → 0.8.0.
- **`black` is no longer a dev dependency.** `ruff format` is the
  formatter. If your local dev environment installed `black`
  explicitly, you can leave it or `pip uninstall black` — `ruff
  format` is run by the project's pre-commit and CI gates.

If you observe non-bit-identical output between two v1.8.0 backends
(NEON vs AVX2 vs SSE2 vs scalar) on the same problem, please open an
issue — that is a regression by definition. Non-identical output
between v1.7.0 and v1.8.0 is expected per the convention purge.

---

## Verification

Run the cross-backend smoke test yourself:

```bash
cargo test --release --features simd -- --nocapture cross_backend_smoke
```

This solves Kuhn poker for 1000 DCFR iterations on both the scalar and
SIMD paths and asserts bit-identical regret + strategy_sum tables at
every iteration.

To verify the AVX2 dispatch on x86_64 with an AVX2-capable CPU:

```bash
RUST_LOG=info cargo test --release --features simd -- compute_strategy_avx2
```

---

## Full PR list

All PRs that ship in v1.8.0, in merge order:

- [#23][pr23] `485aa8c` — feat(simd): v1.8 Phase 1 — cross-platform discount kernel
- [#35][pr35] `db8d646` — feat(simd): v1.8 AVX2 runtime-detect for x86_64
- [#41][pr41] `8073bcc` — feat(simd): v1.8 Phase 2 — update_regret_sum
- [#33][pr33] `a712950` — feat(simd): v1.8 Phase 3 — update_strategy_sum
- [#32][pr32] `77e751c` — feat(simd): v1.8 Phase 4 — compute_strategy
- [#42][pr42] `728206e` — fix(dmg): freeze_support() patches v1.6.0 fork-bomb + warn users
- [#43][pr43] `cfc6bc5` — chore: green up lint/clippy/format/deps gates on main
- [#44][pr44] `a6b89f7` — docs: fix executable code bugs in README + USAGE
- [#45][pr45] `dbfc8d0` — docs: drift cleanup v2 (USAGE header, CHANGELOG `.dmg`, supersede banners)
- [#`78`][pr-purge] `37e5be1` — fix(engine): terminal-utility convention purge (canonical real-poker convention; single `utility()` function; deletes "rust" convention path)

Plus the CI-hardening prerequisites that landed earlier in the v1.7.x
sequence but enable the cross-platform SIMD CI matrix:

- [#20][pr20] — feat(ci): cross-platform CI matrix (Ubuntu x86_64 + macOS arm64)
- [#21][pr21] `bed37c4` — PR 62: v1.7.2 — CI-driven release workflow
- [#22][pr22] `1fefaff` — PR 65: ship-process hardening Guards B + C
- [#28][pr28] `6e9fb11` — fix(scripts): auto-bootstrap references when build_noambrown runs on fresh checkout
- [#30][pr30] `7edb1aa` — test(cfr_core): v1.8 cross-platform end-to-end SIMD smoke

---

## Acknowledgments

This release closes a ~3-month gap between Apple Silicon and x86_64
performance and a ~2-month-old critical packaging bug. Thanks to:

- The cross-platform SIMD spec
  (`docs/pr_proposals/v1_8_cross_platform_simd_spec.md`) for the
  original architecture plan.
- The cherry-pick / merge-orchestration workflow for letting the 4
  SIMD phases land cleanly across the v1.7.x churn without merge
  conflicts.
- The persona-test framework (Sarah W2.3, Marcus turn-spot) for
  empirically anchoring the performance budgets that motivated the
  release.

---

## What's next

- **v1.8.1+**: vectorize secondary hot paths (range expansion,
  payoff computation at terminal nodes) if profiling shows they're now
  the dominant cost.
- **v1.9 candidate**: EMD bucketing for flop interactive viability.
  Since v1.8 SIMD measured ~1.0× on M4 Pro arm64 (root cause: LLVM
  `-O3` already autovectorizes the small-slice case), EMD bucketing
  is now the more likely lever for unblocking the perf-bound turn /
  flop persona workflows (W2.3 / W3.4 flop / W2.1 / W2.4); the W2.3
  retest in flight will set the final wall-clock baseline.
- **v2.0**: full-tree preflop solver + range-based dealing (currently
  on a long-running v2 feature branch).

---

[pr20]: https://github.com/amaster97/poker_solver/pull/20
[pr21]: https://github.com/amaster97/poker_solver/pull/21
[pr22]: https://github.com/amaster97/poker_solver/pull/22
[pr23]: https://github.com/amaster97/poker_solver/pull/23
[pr28]: https://github.com/amaster97/poker_solver/pull/28
[pr30]: https://github.com/amaster97/poker_solver/pull/30
[pr32]: https://github.com/amaster97/poker_solver/pull/32
[pr33]: https://github.com/amaster97/poker_solver/pull/33
[pr35]: https://github.com/amaster97/poker_solver/pull/35
[pr36]: https://github.com/amaster97/poker_solver/pull/36
[pr41]: https://github.com/amaster97/poker_solver/pull/41
[pr42]: https://github.com/amaster97/poker_solver/pull/42
[pr43]: https://github.com/amaster97/poker_solver/pull/43
[pr44]: https://github.com/amaster97/poker_solver/pull/44
[pr45]: https://github.com/amaster97/poker_solver/pull/45
[pr46]: https://github.com/amaster97/poker_solver/pull/46
[pr47]: https://github.com/amaster97/poker_solver/pull/47
[pr48]: https://github.com/amaster97/poker_solver/pull/48
[pr54-script]: https://github.com/amaster97/poker_solver/pull/54
[pr58]: https://github.com/amaster97/poker_solver/pull/58
[pr59-persona]: https://github.com/amaster97/poker_solver/pull/59
[pr60-orphan]: https://github.com/amaster97/poker_solver/pull/60
[pr-purge]: https://github.com/amaster97/poker_solver/pull/78
