# poker-solver v1.8.0 — Cross-platform SIMD + `.dmg` fork-bomb fix

**Status: DRAFT — Phases 1-4 + AVX2 all merged to `main` as of
`77e751c` (PR #32, 2026-05-26). v1.6.1 hold lifted; engine + parity
fixes from the v1.7.1 bundle and v1.7.2 (.dmg fork-bomb fix + CI
hardening) are folded into v1.8.0 per
`docs/v1_6_1_ship_hold_review_2026-05-26.md` and
`docs/v1_7_1_tag_decision_2026-05-26.md`. Do not publish until the
final ship sequence executes (tag + GitHub release).**

**Release date:** 2026-05-XX (TBD at ship time)
**Tag:** `v1.8.0` (TBD)
**Commit SHA:** TBD at tag time (post-PR-32 baseline is `77e751c`).

---

## Headline

**v1.8.0 — Cross-platform SIMD + `.dmg` fork-bomb fix.**

Two things land together in this release:

1. **Cross-platform SIMD acceleration.** The Discounted CFR solver's hot
   inner loops are now hand-vectorized across NEON (Apple Silicon),
   AVX2 + SSE2 (x86_64, runtime-detected), with an automatic scalar
   fallback for anything else. Bit-identical output to v1.7.0 on every
   backend.
2. **`.dmg` fork-bomb fix (CRITICAL).** The v1.6.0 `.dmg` had an
   uncontrolled-spawn bug on Finder launch
   (`multiprocessing.freeze_support()` missing from the PyInstaller
   entry point). v1.6.0 `.dmg` has been pulled from its GitHub Release;
   v1.8.0 ships the repackaged build.

Expected per-iter speedup vs. v1.7.0 scalar baseline:

- **Apple Silicon (M-series)**: ~4-8x
- **x86_64 with AVX2** (~2013+ Intel/AMD): ~2-4x
- **x86_64 SSE2-only** (pre-Haswell): ~1.5-2x
- **Other architectures**: scalar path, no regression

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
between Apple Silicon and x86_64 performance, now closed. The
cross-platform spec
(`docs/pr_proposals/v1_8_cross_platform_simd_spec.md`) drives the
architecture; Sarah persona W2.3 (turn Nash under a 5-min budget) is
now unblocked on M-series.

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
mechanical guard (R6, PR 50), and a documented Brown design
divergence (terminal-utility convention + Nash multiplicity at deep
cap; see "Known issues remaining" below and
`docs/a83_validation_2026-05-26.md`).

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

---

## Known issues remaining

The following are **NOT** resolved in v1.8.0 and remain open for future
work:

- **Deep-cap A83 ≥33-pp bottom-pair-Ace divergence vs Brown reference
  solver.** The Brown apples-to-apples acceptance test continues to
  report per-cell strict divergences at the bottom-pair-Ace cluster
  on the A83 board in deep-cap (100bb+) settings. **Root cause is
  established as a combination of two documented designs, neither of
  which is a DCFR-algorithm bug: (a) terminal-utility convention
  divergence — Brown's solver awards the full pot (including base_pot)
  to the winner, while our convention is zero-sum (winner receives
  opponent contribution only); and (b) Nash multiplicity at indifference
  manifolds in the deep-cap subgame.** Both solvers are essentially
  Nash (Brown exploitability 0.06 chips at 2000 iters = 0.006% of pot;
  matched-config empirical verification 2026-05-25, VERDICT C). **The
  reframed 4-layer acceptance test (L1 structural / L2 shallow-strict /
  L3 deep-directional L1 ≤ 1.9 / L3' p75 L1 ≤ 0.60 / L4 top-action
  ≥ 60%) PASSES on both river spots — see Dry-run #10.** The strict
  per-cell residual is treated as informational; see
  `docs/a83_validation_2026-05-26.md` (DCFR-math validation, PASS),
  `docs/a83_deep_cap_root_cause_investigation.md`,
  `docs/matched_config_investigation.md`, and the project memory rule
  `feedback_nash_multiplicity_acceptance.md`. The v1.6.1 engine bundle
  has shipped piecewise on `origin/main` (10 PRs landed
  2026-05-26 02:32-03:02 UTC); the hold is lifted and the fixes are
  folded into v1.8.0 per `docs/v1_6_1_ship_hold_review_2026-05-26.md`
  and `docs/v1_7_1_tag_decision_2026-05-26.md`.
- **`Range` fractional frequencies.** The spec for true fractional
  frequencies (e.g. `AKs:0.6`) landed in [PR #36][pr36]; the
  implementation is tracked separately and not in v1.8.0.
- **`.app` / `.dmg` notarization.** The v1.8.0 `.dmg` is still
  ad-hoc-signed (same as v1.6.0). Apple Developer enrollment is a
  user carry-item and gates full notarization.

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
- **No CFR algorithm changes.** Bit-identical output to v1.7.0 on the
  same inputs across all backends.
- **Min Python**: unchanged from v1.7.0.
- **Min Rust toolchain**: stable, unchanged from v1.7.0.
- **`crates/cfr_core` version bump**: 0.7.x → 0.8.0.
- **`black` is no longer a dev dependency.** `ruff format` is the
  formatter. If your local dev environment installed `black`
  explicitly, you can leave it or `pip uninstall black` — `ruff
  format` is run by the project's pre-commit and CI gates.

If you observe non-bit-identical output between v1.7.0 and v1.8.0 on
the same problem, please open an issue — this is a regression by
definition.

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
  v1.8 unblocks turn workflows; flop is the next persona-budget gate.
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
