# v1.8.0 release-notes prep report — 2026-05-26

**Purpose:** Pre-draft v1.8.0 release notes so they're ready when Phase
4 SIMD (PR #32) lands and we tag. Per user decision: **ONE v1.8.0
release that folds in the `.dmg` fork-bomb fix.** Stage-3
"trust-the-draft — edit then ship" authorized.

**Status:** Draft staged. Ready for user review.

---

## TL;DR

- Draft file written: `docs/v1_8_0_release_notes_DRAFT.md` (306 lines).
- Mirrored on branch `pr-88-v1.8.0-release-notes-prep` (origin) at
  commit `01b661c5fb1cd7e8bf9b60ee866e45d38b8b8047` for safe-keeping.
- No PR opened (file is for user review only; actual publish happens
  via `gh release create` after Phase 4 lands).
- No tag created. No release created.

---

## What changed vs. PR #34's earlier draft

PR #34 (`pr-74-v1.8-release-notes-prep`, status HOLD) had a v1.8.0
draft already, but it pre-dated:

1. The decision to fold the `.dmg` fork-bomb fix into v1.8.0 (originally
   tracked as v1.7.2).
2. PRs #42, #43, #44, #45 landing on `main` after PR #34 opened.
3. The renumbering of Phase 2 (#26 auto-closed → #41) and Phase 3 (#70
   replaced by #33).

This new draft (`docs/v1_8_0_release_notes_DRAFT.md`) supersedes the
PR #34 file content. Recommended action: close PR #34 once the v1.8.0
ship completes, or rebase it on top of this new draft if you prefer to
keep that PR open as the ship-PR vehicle.

Key additions vs. PR #34:

- **Headline broadened** from "Cross-platform SIMD acceleration" to
  "Cross-platform SIMD + `.dmg` fork-bomb fix" — both are user-facing
  and the `.dmg` fix is critical-severity.
- **Highlight 2 (`.dmg` fork-bomb fix)** added in full, with RCA pointer
  and explicit retroactive-pull note for v1.6.0.
- **Highlight 3 (lint/format/deps green-up)** added — PR #43, including
  `black` → `ruff format` migration and explicit `rich>=13.0` runtime
  dep.
- **Highlight 4 (doc accuracy)** added — PRs #44 and #45, with the
  three executable-code-bug fixes called out individually.
- **Known issues** section added — A83 deep-cap divergence, `Range`
  fractional frequencies, `.app`/`.dmg` notarization carry-item.
- **Upgrade path** section expanded — from-source + from-v1.6.0-`.dmg`
  paths each documented, including the `maturin develop --release`
  rebuild requirement (Rust source has changed).
- **PR list** updated with current merge SHAs and the corrected PR
  numbers (Phase 2 = #41 not #26; Phase 3 = #33 not #70).

---

## PR list with merge SHAs

### Core v1.8.0 changes (in merge order)

| PR | Title | Merge SHA | Status |
|----|-------|-----------|--------|
| [#23](https://github.com/amaster97/poker_solver/pull/23) | PR 61: v1.8 Phase 1 — cross-platform SIMD discount kernel | `485aa8c1f78e73c2eadd52e543b677e42f9fe542` | Merged |
| [#35](https://github.com/amaster97/poker_solver/pull/35) | PR 68: v1.8 — AVX2 runtime-detect path for x86_64 hosts | `db8d6463f914ea678681d18bf99bf7662533fdb7` | Merged |
| [#41](https://github.com/amaster97/poker_solver/pull/41) | PR 63b: v1.8 Phase 2 — update_regret_sum SIMD | `8073bcce33800f62ddfc9187cc7af6600ff6e2d0` | Merged |
| [#33](https://github.com/amaster97/poker_solver/pull/33) | feat(cfr_core): v1.8 Phase 3 — update_strategy_sum SIMD | `a71295031d52ea664038c6a2f08d8d94e31a24ed` | Merged |
| [#32](https://github.com/amaster97/poker_solver/pull/32) | PR 71: v1.8 Phase 4 — compute_strategy SIMD | TBD | **OPEN — pending merge** |
| [#42](https://github.com/amaster97/poker_solver/pull/42) | fix(dmg): freeze_support() patches v1.6.0 fork-bomb + warn users | `728206e3e0bad675ad3f7a9a42f1f7229392015f` | Merged |
| [#43](https://github.com/amaster97/poker_solver/pull/43) | chore: green up lint/clippy/format/deps gates on main | `cfc6bc5288ea541a0497393268ea9025129c8381` | Merged |
| [#44](https://github.com/amaster97/poker_solver/pull/44) | docs: fix executable code bugs in README + USAGE | `a6b89f70f163503b6d7dac9668a744cef20a08c0` | Merged |
| [#45](https://github.com/amaster97/poker_solver/pull/45) | docs: drift cleanup v2 — USAGE header, CHANGELOG .dmg, supersede banners | `dbfc8d02696d02c17f1c66f20b3ac213e0e37a32` | Merged |

### CI-hardening prerequisites (already on main, enabled the SIMD CI matrix)

| PR | Title | Merge SHA |
|----|-------|-----------|
| [#20](https://github.com/amaster97/poker_solver/pull/20) | feat(ci): cross-platform CI matrix | (still open — runner-config refresh; not blocking ship) |
| [#21](https://github.com/amaster97/poker_solver/pull/21) | PR 62: v1.7.2 — CI-driven release workflow | `bed37c4` |
| [#22](https://github.com/amaster97/poker_solver/pull/22) | PR 65: ship-process hardening Guards B + C | `1fefaff` |
| [#28](https://github.com/amaster97/poker_solver/pull/28) | fix(scripts): auto-bootstrap references when build_noambrown runs on fresh checkout | `6e9fb11` |
| [#30](https://github.com/amaster97/poker_solver/pull/30) | test(cfr_core): v1.8 cross-platform end-to-end SIMD smoke | `7edb1aa` |

---

## Where the draft lives

- **Local working file:** `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md`
  (uncommitted on `main` working tree — intentional; ship-time merge to
  `main` is via the actual release PR, not this prep file).
- **Origin-mirrored on branch:**
  `pr-88-v1.8.0-release-notes-prep`
  at commit `01b661c5fb1cd7e8bf9b60ee866e45d38b8b8047`
- **Branch URL:**
  https://github.com/amaster97/poker_solver/tree/pr-88-v1.8.0-release-notes-prep
- **Diff URL (for reviewing against `main`):**
  https://github.com/amaster97/poker_solver/compare/main...pr-88-v1.8.0-release-notes-prep
- **Worktree path:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-88-v1.8.0-notes`

No PR opened. The branch exists purely to back up the draft on origin
during the pre-Phase-4 wait.

---

## Recommended `gh release create` command (for ship time)

When Phase 4 (PR #32) lands and v1.8.0 is tagged, the user can publish
the GitHub Release with:

```bash
# 1. Fill in the TBD fields in the draft (date, tag SHA, Phase 4 SHA)
#    in /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md
#    or copy it to docs/release_notes/v1.8.0.md as the canonical home.

# 2. Tag v1.8.0 (not run here — queued in Task #14):
git tag -a v1.8.0 -m "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
git push origin v1.8.0

# 3. Publish the release:
gh release create v1.8.0 \
  --title "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix" \
  --notes-file /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md
```

If you want to attach the repackaged `.dmg` to the release at the same
time:

```bash
gh release create v1.8.0 \
  --title "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix" \
  --notes-file /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md \
  /path/to/Poker-Solver-v1.8.0.dmg
```

---

## TBD fields to fill in at ship time

These four placeholders in the draft must be substituted before
publishing:

1. **`2026-05-XX`** — actual release date (top of file + headline area).
2. **`(TBD)` next to Tag** — confirm `v1.8.0` and the final commit SHA.
3. **`TBD (merging into v1.8.0)`** in the Phase 4 row of the kernels
   table — replace with PR #32's merge SHA once it lands.
4. **`TBD — feat(simd): v1.8 Phase 4 — compute_strategy (pending)`** in
   the Full PR list — replace SHA likewise.

A single `sed` over the file handles all four once you have the Phase 4
SHA (call it `<P4>`) and the release date `<DATE>`:

```bash
sed -i.bak \
  -e "s|2026-05-XX|<DATE>|g" \
  -e "s|TBD (merging into v1.8.0)|\`<P4>\`|" \
  -e "s|TBD — feat(simd): v1.8 Phase 4|\`<P4>\` — feat(simd): v1.8 Phase 4|" \
  /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md
```

(After running, review the file and `rm` the `.bak`.)

---

## Open questions for the user

1. **CHANGELOG.md alignment.** The current `CHANGELOG.md` on `main` has
   the `.dmg` fork-bomb fix logged as a separate v1.7.2 entry. The
   v1.8.0 release notes draft folds it under v1.8.0 (per user
   decision). At ship time, the user has two options:

   - **Option A (clean):** Squash the v1.7.2 CHANGELOG entry into the
     v1.8.0 entry. The fix lands in users' hands as part of v1.8.0;
     the v1.7.2-named entry never published as a release anyway.
   - **Option B (preserve history):** Keep the v1.7.2 entry in
     CHANGELOG.md as-is, and have v1.8.0 reference back to it. This
     reflects the actual dev sequencing but creates a documented
     v1.7.2 that never got tagged or released.

   Default recommendation: **Option A**. The v1.7.2 entry was added in
   anticipation of a tag that never materialized; folding it into
   v1.8.0 is cleaner for the public-facing CHANGELOG.

2. **PR #34 disposition.** PR #34 holds an earlier draft with the same
   filename `docs/release_notes/v1.8.0_release_notes_draft.md`. The
   new draft is at `docs/v1_8_0_release_notes_DRAFT.md` (different
   path, deliberately not colliding). At ship time:

   - **Close PR #34** as superseded, and merge the new draft via a
     fresh ship-PR.
   - Or **rebase PR #34** on top of `pr-88-v1.8.0-release-notes-prep`
     and use it as the ship-PR vehicle.

   Default recommendation: **close PR #34** and use a fresh ship-PR
   with the new draft. The branch `pr-88-v1.8.0-release-notes-prep`
   can be promoted to PR-status at ship time with `gh pr create` if
   that's the preferred path.

---

## Full draft text (for convenient diff against PR #34)

The full draft is below for inline review. It is identical to
`docs/v1_8_0_release_notes_DRAFT.md` and to the file on branch
`pr-88-v1.8.0-release-notes-prep`.

---

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
| 1     | `discount_regrets` + `discount_strategy_sum`    | #23       | `485aa8c` |
| 1+    | AVX2 runtime-detect path (x86_64)               | #35       | `db8d646` |
| 2     | `update_regret_sum`                             | #41       | `8073bcc` |
| 3     | `update_strategy_sum`                           | #33       | `a712950` |
| 4     | `compute_strategy`                              | #32       | TBD (merging into v1.8.0) |

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

- **PR #42** (`728206e`) adds the `multiprocessing.freeze_support()`
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

PR #43 (`cfc6bc5`) is a non-functional cleanup pass that brings the
main-branch lint gates back to green after the v1.7.x churn:

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

- **PR #44** (`a6b89f7`) fixed **three executable code bugs** in
  `README.md` and `USAGE.md` examples:
  1. `Range` parser example used the wrong constructor signature.
  2. A `solve_river_nash()` example was missing the `iterations=`
     keyword.
  3. A hero/board overlap example assumed a card slot that the API
     rejects.
  Plus a stale claim about "no CLI for parity comparison" was scrubbed
  (the `poker-solver parity` subcommand has shipped since v1.7.0).
- **PR #45** (`dbfc8d0`) cleaned up downstream doc drift:
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
  frequencies (e.g. `AKs:0.6`) landed in PR #36; the implementation is
  tracked separately and not in v1.8.0.
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

- #23 `485aa8c` — feat(simd): v1.8 Phase 1 — cross-platform discount kernel
- #35 `db8d646` — feat(simd): v1.8 AVX2 runtime-detect for x86_64
- #41 `8073bcc` — feat(simd): v1.8 Phase 2 — update_regret_sum
- #33 `a712950` — feat(simd): v1.8 Phase 3 — update_strategy_sum
- #32 TBD — feat(simd): v1.8 Phase 4 — compute_strategy (pending)
- #42 `728206e` — fix(dmg): freeze_support() patches v1.6.0 fork-bomb + warn users
- #43 `cfc6bc5` — chore: green up lint/clippy/format/deps gates on main
- #44 `a6b89f7` — docs: fix executable code bugs in README + USAGE
- #45 `dbfc8d0` — docs: drift cleanup v2 (USAGE header, CHANGELOG `.dmg`, supersede banners)

Plus the CI-hardening prerequisites that landed earlier in the v1.7.x
sequence but enable the cross-platform SIMD CI matrix:

- #20 — feat(ci): cross-platform CI matrix (Ubuntu x86_64 + macOS arm64)
- #21 `bed37c4` — PR 62: v1.7.2 — CI-driven release workflow
- #22 `1fefaff` — PR 65: ship-process hardening Guards B + C
- #28 `6e9fb11` — fix(scripts): auto-bootstrap references when build_noambrown runs on fresh checkout
- #30 `7edb1aa` — test(cfr_core): v1.8 cross-platform end-to-end SIMD smoke

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
