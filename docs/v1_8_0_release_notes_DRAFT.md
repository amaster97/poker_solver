# poker-solver v1.8.0 — Cross-platform SIMD + `.dmg` fork-bomb fix

**Status: DRAFT — pre-staged before Phase 4 (PR #32) lands. Do not
publish until the SIMD bundle is merged to `main` and tagged.**

**Release date:** 2026-05-XX (TBD at ship time)
**Tag:** `v1.8.0` (TBD)
**Commit SHA:** (TBD at ship time, after PR #32 merges)

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
| 4     | `compute_strategy`                              | [#32][pr32] | TBD (merging into v1.8.0) |

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

---

## Known issues remaining

The following are **NOT** resolved in v1.8.0 and remain open for future
work:

- **Deep-cap A83 33-pp bottom-pair-Ace divergence.** The v1.5.0 Brown
  apples-to-apples acceptance test still reports a 33-percentage-point
  per-cell divergence at the bottom-pair-Ace cluster on the A83 board
  in deep-cap (100bb+) settings. Root-cause investigation is in flight
  (`docs/a83_deep_cap_root_cause_investigation.md`); the v1.6.1 engine
  bundle remains HELD pending diagnosis. Note: deep-cap multi-action
  Nash has indifference manifolds, and external reference solvers
  (Brown, Pluribus) are treated as sanity checks rather than strict
  ground truth — the divergence may be a design difference rather than
  a bug.
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
- [#32][pr32] TBD — feat(simd): v1.8 Phase 4 — compute_strategy (pending)
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
