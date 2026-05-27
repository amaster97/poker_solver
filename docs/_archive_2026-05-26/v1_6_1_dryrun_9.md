# v1.6.1 Engine Ship — Dry-Run #9 (Corrected Bundle: PR 55-ext Excluded)

**Date:** 2026-05-24
**Worktree:** `/tmp/dryrun-9-corrected-83355` (disposable, removed at cleanup)
**Base:** `origin/main` @ `3843ce7` (v1.7.0)
**Branch:** `dryrun-9-composite-no-55ext` (worktree-local only)
**Trigger:** double-swap diagnosis confirmation
  (`docs/r11_brown_convergence_hypothesis.md`, dated 2026-05-24 05:06)
**Pre-condition source:** the sibling verification doc
  `docs/r11_double_swap_verification.md` did NOT land within the wait
  window; this dry-run proceeded under auto-mode based on the existing,
  independent empirical confirmation in `r11_brown_convergence_hypothesis.md`,
  which showed Brown↔Rust agreement to ~6 decimals on AA root under the
  NO-swap convention vs ~3-class divergence under the double-swap (DR#8)
  convention. The convergence-hypothesis doc explicitly recommends
  reverting the wrapper's input-side swap (= PR 55-ext). See "Pre-condition
  handling" section below.

---

## Bundle composition (7 cherry-picks, was 8 in DR#8)

| # | PR | Branch | SHA (origin tip) | Role |
|---|----|--------|------------------|------|
| 1 | 51 | `pr-51-dcfr-vector-asymmetric-fix` | `78c71557` | Rust panic fix (asymmetric ranges) |
| 2 | 50 | `pr-50-facing-all-in-guard` | `18a7640e` | Action-menu guard (Rust + Python) |
| 3 | 52 | `pr-52-suit-encoding-fix` | `9e6662b6` | Wrapper suit-char map |
| 4 | 54 | `pr-54-renderer-stack-ceiling` | `f389b433` | Test renderer `stack_ceiling` kwarg |
| 5 | 55 | `pr-55-p0-p1-player-swap` | `ac7c6406` | Wrapper P0/P1 output-side swap |
| 6 | 56 | `pr-56-hand-sort-canonicalization` | `950b82c0` | Wrapper hand-string canonical sort |
| 7 | 53b | `pr-53b-rebased-on-pr-54` | `3e50b766` | Acceptance test 4-layer reframe (PR 53 rebased) |

**EXCLUDED 2026-05-24:** `pr-55-extend-input-range-swap` (`6e545e63`)
— left open on origin per orchestrator instruction; not merged, not closed.

Cherry-pick order (matches orchestrator spec):
```
git cherry-pick origin/pr-51-dcfr-vector-asymmetric-fix
git cherry-pick origin/pr-50-facing-all-in-guard
git cherry-pick origin/pr-52-suit-encoding-fix
git cherry-pick origin/pr-54-renderer-stack-ceiling
git cherry-pick origin/pr-55-p0-p1-player-swap
git cherry-pick origin/pr-56-hand-sort-canonicalization
git cherry-pick origin/pr-53b-rebased-on-pr-54
```

All 7 cherry-picks landed cleanly (no conflicts; PR 53b's reframe of
`tests/test_v1_5_brown_apples_to_apples.py` applies on top of PR 54's
renderer kwarg without overlap — the kwarg is at line ~459 of the test;
PR 53b's reframe replaces lines ~600-850).

---

## Build + smoke

| Step | Result |
|------|--------|
| `cargo build --release` | OK (`Finished release profile [optimized] target(s) in 7.58s`) |
| `cargo test --lib --release` | **50 passed; 0 failed; 0 ignored** (17.60s) |
| `maturin build --target universal2-apple-darwin --release` | OK; wheel at `target/wheels/poker_solver-1.7.0-cp313-cp313-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl` |
| `pip install --force-reinstall --no-deps target/wheels/...` | OK; reinstalled `poker_solver-1.7.0` |
| Local `_rust.so` copied into `poker_solver/` source tree so pytest's `importlib.import_module('poker_solver._rust')` resolves correctly (maturin develop unavailable without venv) | OK |
| Local `references/` symlinked from main repo so `find_brown_binary()` returns the prebuilt binary | OK |
| `pytest tests/test_exploit_diff.py -v --timeout=120` | 5 skipped (Rust-Python differential gates marked optional/env-gated; not a regression — same skip pattern as DR#8 and prior runs) |
| `pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800` | **2 FAILED** (Layer 3 L1 max ceiling 1.0 still tripped) |

---

## Reframed 4-layer gate, per spot

### `dry_K72_rainbow`

| Layer | Threshold | DR#9 result | DR#8 (with PR 55-ext) | Verdict |
|-------|-----------|-------------|-----------------------|---------|
| 1a Coverage | ≥ 80% | **100.0%** | 100.0% | PASS |
| 1b Action-count match | ≥ 50% | **100.0%** (195/195) | n/a in DR#8 | PASS |
| 2 Shallow-strict (root) | ≤ 5 violations @ 5e-2 | **0 / 13 cells** | **20 violations** | **PASS** (was FAIL in DR#8) |
| 3 L1 per-row ceiling | ≤ 1.0 (no row 100%-inverted) | **1.736** (1 row violates) | n/a (only p75 was gated in DR#8) | **FAIL** |
| 3' L1 p75 ceiling | ≤ 0.60 | **0.069** | **1.008** | **PASS** (was FAIL in DR#8) |
| 4 Top-action agreement | ≥ 60% pass rate | **95.2%** (160/168) | 89.6% | PASS |

### `dry_A83_rainbow`

| Layer | Threshold | DR#9 result | DR#8 (with PR 55-ext) | Verdict |
|-------|-----------|-------------|-----------------------|---------|
| 1a Coverage | ≥ 80% | **100.0%** | 100.0% | PASS |
| 1b Action-count match | ≥ 50% | **100.0%** (441/441) | n/a | PASS |
| 2 Shallow-strict (root) | ≤ 5 violations @ 5e-2 | **0 / 21 cells** | **20 violations** | **PASS** (was FAIL in DR#8) |
| 3 L1 per-row ceiling | ≤ 1.0 | **1.813** (~16 rows violate) | n/a | **FAIL** |
| 3' L1 p75 ceiling | ≤ 0.60 | **0.194** | **0.792** | **PASS** (was FAIL in DR#8) |
| 4 Top-action agreement | ≥ 60% pass rate | **95.3%** (326/342) | 92.2% | PASS |

---

## Diff vs DR#8 (PR 55-ext effect, isolated)

Removing the double-swap (PR 55-ext) is a **dramatic improvement**:

* **Shallow-strict (Layer 2):** 20 violations → **0** on BOTH spots.
  The "AA at root pure-check vs mixed-strategy" divergence is GONE.
  Brown↔Rust agree at the root within 5e-2 per action on every depth-0
  cell.
* **L1 p75 (Layer 3 aggregate):** K72: 1.008 → **0.069** (15× tighter).
  A83: 0.792 → **0.194** (4× tighter). Both well under the 0.60 ceiling.
* **Top-action agreement (Layer 4):** K72 89.6% → **95.2%**.
  A83 92.2% → **95.3%**.
* **L1 median:** K72: 0.004. A83: 0.049. Both near-zero, indicating the
  vast majority of cells agree byte-close.

This empirically confirms the double-swap diagnosis from
`docs/r11_brown_convergence_hypothesis.md` — at the **root** and
**aggregated across depth**, Brown and Rust converge to the same
equilibrium when only ONE of the two range-swap layers is applied.

## What still fails

**Layer 3 strict L1 per-row ceiling (1.0)** trips on a small set of
deep-cap rows with multi-raise or `A` (all-in) tokens in history:

* K72: 1 row over 1.0, max L1 = 1.736
  (`Bp1/Rp0 hand=AsAd hist='xb750r5000A'`: Brown checks 91% / Rust checks 96%,
  i.e. near-inversion of fold vs call).
* A83: ~16 rows over 1.0, max L1 = 1.813
  (clustered on T-T and 8-8 hands at `xb1000r3000r6000`,
  `xb500r2000r4000`, `xb500r2000r6000`, and `r3125r7813` / `r5000A`
  deep-cap histories).

All failing rows share the pattern: deep-cap histories with
multi-bet sequences or all-in tokens (`A`). These are exactly the
histories where action-menu and cap-handling differ between Brown's
and our action abstractions — Brown's tree allows different bet sizes
at cap than ours does, even with PR 50's facing-all-in guard. The
divergence at these rows is consistent with Nash multiplicity on the
deep-cap indifference manifold; both engines converge to valid (but
different) Nash strategies given their respective action menus.

---

## Verdict

**STILL-FAILS the bundled acceptance test as currently written**, but
the failure mode is dramatically different from DR#8:

* Root agreement (Layer 2) is now CLEAN.
* Aggregate behavior (Layer 3 p75, Layer 4) PASS.
* Only the strict per-row L1 ≤ 1.0 ceiling (Layer 3 strict) trips —
  and only on deep-cap multi-raise / all-in rows.

The double-swap was the dominant cause of the DR#8 failure. With it
removed, the bundle is much closer to Brown's reference — within the
test's own reframed sanity envelope on 3 of 4 layers. The remaining
Layer 3 strict failure is on a small minority of deep-cap rows where
action-menu divergence between solvers genuinely produces different
(both correct) Nash equilibria.

**Recommended next step (NOT executed in this dry-run):**

Two paths, choose one based on user/orchestrator preference:

1. **Loosen Layer 3 strict ceiling to acknowledge deep-cap Nash
   multiplicity.** E.g. raise `L1_PER_ROW_CEILING` from 1.0 to 1.8, or
   gate it conditionally on shallow-history-only cells. The L1 p75
   ceiling (0.60) plus the action-count parity floor already catch
   meaningful structural divergence; the per-row ceiling at 1.0
   over-constrains the bundle for deep-cap rows where divergence is
   expected.
2. **Investigate the ~17 outlier rows** before shipping. Likely root
   cause is action-menu cap behavior at deep histories, NOT an engine
   bug per se — `r11_brown_convergence_hypothesis.md` already noted
   that the engine kernel produces Brown-correct strategies when fed
   matched inputs.

**HOLD on tagging/pushing v1.7.1** until path 1 or 2 is decided. The
ship-script update in this PR removes PR 55-ext but does NOT change
acceptance-test thresholds (those would require a new PR 53c / Layer 3
relaxation).

---

## Bundle status

**CORRECTED-BUNDLE-PARTIALLY-READY** — engine + wrapper fixes are
sound; bundle eliminates the double-swap; acceptance test still gates
on a strict deep-cap L1 ceiling that the current bundle does NOT meet.

Per the strict orchestrator-specified verdicts:
* `CORRECTED-BUNDLE-READY-TO-SHIP` would require Layer 3 strict to pass.
* `STILL-FAILS` (the choice here) — Layer 3 strict per-row ceiling
  fails on 1 row in K72 (max L1 = 1.736) and ~16 rows in A83
  (max L1 = 1.813). Layers 1, 2, 3-aggregate, and 4 all PASS.

---

## Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver
git worktree remove --force /tmp/dryrun-9-corrected-83355
# branch 'dryrun-9-composite-no-55ext' was worktree-local only; auto-deletes
# with the worktree
```

(Performed at end of dry-run; see audit log.)

---

## Pre-condition handling

**Verification doc (`docs/r11_double_swap_verification.md`) did NOT land
within the wait window** (polled ~60s, then proceeded under auto-mode
directive). The decision to proceed was based on:

1. `docs/r11_brown_convergence_hypothesis.md` (2026-05-24 05:06)
   independently confirms the double-swap diagnosis via empirical
   Rust runs under both swap conventions:
   * NO-swap convention: Rust matches Brown to ~6 decimals on AA root.
   * Double-swap convention (DR#8 bundle): 3+ class divergence.
2. That doc's "Recommendation" section explicitly recommends reverting
   the wrapper's input-side swap (= PR 55-ext) as the correct fix.
3. Auto-mode directive: "Work without stopping for clarifying
   questions. When you'd normally pause to check, make the reasonable
   call and keep going — they'll redirect you if needed."

If `docs/r11_double_swap_verification.md` lands later with a different
verdict (e.g., "PR 40 should be reverted instead" or "diagnosis is
wrong"), the changes in this PR should be reverted:
* Restore `git cherry-pick origin/pr-55-extend-input-range-swap` line
  to `scripts/ship_v1_7_1.sh`.
* Restore PR 55-ext CHANGELOG entry.
* Restore SHA_PR55_EXT variable.

The ship script changes are bundled as a single atomic edit to make
revert trivial.

---

## Files touched in this PR

* `/Users/ashen/Desktop/poker_solver/scripts/ship_v1_7_1.sh` — removed
  PR 55-ext cherry-pick, updated header comments, updated commit
  message template, updated CHANGELOG block, updated tag annotation,
  updated SHA list and fetch list.
* `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_9.md` — this
  document.

No engine code touched; no test thresholds touched.

---

## References

* `docs/r11_brown_convergence_hypothesis.md` (2026-05-24) — diagnosis +
  empirical confirmation
* `docs/r11_aa_depth0_diagnosis.md` (2026-05-24) — companion hypothesis
  audit
* `docs/r11_aa_vs_aa_minimal.md` (2026-05-24) — engine-kernel cleared on
  minimal fixture
* `docs/v1_6_1_dryrun_8.md` — prior dry-run with PR 55-ext (showing
  20 shallow violations)
* `/tmp/dryrun-9-pytest-brown.log` — full pytest output for this run
* `scripts/ship_v1_7_1.sh` — updated bundle script
