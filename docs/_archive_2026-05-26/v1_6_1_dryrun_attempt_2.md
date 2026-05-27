# v1.6.1 Engine Bundle — Dry-Run Attempt #2

**Date:** 2026-05-23 (late)
**Mode:** READ-ONLY dry-run in disposable git worktree at `/tmp/v1_6_1_dryrun2_72023`.
**Main working tree NOT modified.** Worktree removed at end of session (verified gone).

**Source docs verified against:**
- `docs/a83_deep_cap_root_cause_investigation.md`
- `docs/pr_35c_paired_fix_report.md`
- `docs/pr_35d_brown_quirk_doc_report.md`
- `docs/pr_46_dcfr_panic_fix_report.md`
- `docs/v1_6_1_dryrun_verification.md` (the previous failed dry-run)

---

## TL;DR

**Verdict: NO-GO.** Both spots FAIL at the new 5e-2 tolerance, with max
\|diff\| **far above** the 1e-1 escalation threshold (K72 = **4.22e-1**,
A83 = **2.71e-1**). The bundle's Path A (paired cap-guard) + Path C
(tolerance widen + Brown quirk doc) **substantially reduces but does
not close** the deep-cap divergence. The acceptance gate is not
satisfied; v1.6.1 cannot ship as-composed.

Compared to the previous dry-run (which had no Path A or Path C),
the magnitude of divergence is actually **larger** on K72 (42pp vs the
prior 7pp on top-pair-K), suggesting the paired cap-guard fix has
altered the equilibrium in a way that exposes additional structural
divergence at non-cap nodes upstream from the previously-shrunken cap
divergence. Path C tolerance widening (5e-3 → 5e-2) is insufficient to
bracket this.

---

## 1. Bundle composition confirmed

Five branches cherry-picked in this order onto `origin/main = 94007ca`:

| Order | PR | Branch | SHA | Result |
|---|---|---|---|---|
| 1 | PR 46 | `pr-46-dcfr-panic-fix` | `cd56761` | CLEAN |
| 2 | PR 33 | `pr-33-python-delegate` | `29a00c0` | CLEAN |
| 3 | PR 35c | `pr-35c-paired-fix` | `63c9432` | CLEAN |
| 4 | PR 35d | `pr-35d-brown-quirk-doc` | `e9e5d3a` | CLEAN |
| 5 | PR 40 | `pr-40-acceptance-test-fix` | `c058e97` | **ONE EXPECTED CONFLICT** at `PER_ACTION_TOL` line |

**Conflict resolution (PR 40):** Kept PR 35d's 5e-2 tolerance with
documented Brown quirk comment (HEAD side). Manually re-applied PR 35
Fix A's `stack_ceiling` kwarg to `_rust_history_substr_for_canonical`
(both the bet "A" branch and the raise "A" branch) and added the
`stack_ceiling = int(spot.pot) // 2 + int(spot.stack)` calculation in
`test_v1_5_brown_apples_to_apples_parity` with the two call-site
updates passing `stack_ceiling=stack_ceiling`. This follows the task
brief's instruction to "keep PR 40's loop rename + PR 35-derived
stack_ceiling kwarg" — PR 35 was skipped entirely from cherry-pick but
its Fix A renderer change had to be re-applied manually since PR 40
does not include it.

**Final bundle SHA:** `93fc20d` (5 commits above `origin/main`).

**File-level diff vs `origin/main`** (8 files, 745 ins / 32 del):

```
 Cargo.lock                                |   2 +-
 crates/cfr_core/src/dcfr_vector.rs        |  38 +++-
 crates/cfr_core/src/hunl.rs               |   8 +-
 crates/cfr_core/tests/hunl_state_unit.rs  |   7 +-
 poker_solver/action_abstraction.py        |   6 +-
 poker_solver/hunl_solver.py               | 247 +++++++++++++++++++++++++-
 tests/test_python_delegate.py             | 284 ++++++++++++++++++++++++++++++
 tests/test_v1_5_brown_apples_to_apples.py | 185 ++++++++++++++++---
```

---

## 2. Build + test results

### 2a. `cargo build --release` — PASS

```
Finished `release` profile [optimized] target(s) in 7.14s
```

### 2b. `cargo test --release` (cfr_core crate)

| Suite | Result |
|---|---|
| Library tests (`--lib`) | **50/50 PASS** |
| `hunl_state_unit.rs` integration | **19/19 PASS** |
| `test_hunl_rust.rs` integration | 8/13 PASS, 5 FAIL (env artifact) |

**The 5 failures in `test_hunl_rust.rs` are the same environment
artifacts noted in the previous dry-run** — PyO3 tests pick up the
shared tree's `_rust.so` via the venv's `.pth` and trigger a circular-
import error (`cannot import name 'Street' from partially initialized
module 'poker_solver.hunl'`). The failures are pre-existing on
`origin/main` and not caused by the bundle. The critical regression
gate `test_exploit_diff` (which caused the original PR 35 Fix C to be
reverted) was already verified PASS 5/5 in the PR 35c report.

### 2c. `maturin develop --release` — PASS

Built and installed `poker_solver-1.6.0` into the worktree's venv.

### 2d. `pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=900`

**Both spots FAILED** at 5e-2 tolerance after 5m 17s total runtime.

```
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow] FAILED
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow] FAILED
=================== 2 failed, 1 warning in 317.38s (0:05:17) ===================
```

---

## 3. Empirical results per spot

### 3a. `dry_K72_rainbow` — FAIL

| Metric | Value |
|---|---|
| Max \|diff\| | **4.217e-01** (42pp) |
| Total diffs >= 5e-2 | ~305 cells (20 shown + 285 elided) |
| Coverage | >= 80% (test reached per-cell loop; coverage assertion not raised) |
| Action-count mismatches | 6 (across both spots; e.g., `b1000A` history Brown emits 2 actions, Rust emits 3) |

**Worst diff cells (top 5):**

| Hand | Action | Brown | Rust | \|diff\| |
|---|---|---|---|---|
| 8hKh | c (top-pair K) | 0.875 | 0.454 | **4.22e-1** |
| 8dKd | c | 0.870 | 0.455 | **4.16e-1** |
| 9hKh | c | 0.839 | 0.442 | **3.97e-1** |
| 9dKd | c | 0.827 | 0.444 | **3.83e-1** |
| 8hKh | r5000 | 0.072 | 0.317 | 2.45e-1 |

Pattern unchanged from previous dry-run: at deep-cap raise node
`b1500r5000`, Rust **over-folds** and **under-calls** on top-pair-K
hands; Brown calls 84-88% while Rust calls only 44-45%.

### 3b. `dry_A83_rainbow` — FAIL

| Metric | Value |
|---|---|
| Max \|diff\| | **2.707e-01** (27pp) |
| Total diffs >= 5e-2 | ~306 cells (20 shown + 286 elided) |
| Coverage | >= 80% (test reached per-cell loop) |

**Worst diff cells (top 5):**

| Hand | Action | Brown | Rust | \|diff\| |
|---|---|---|---|---|
| 3sAs | f (at `b1000r4500`) | 0.447 | 0.176 | **2.71e-1** |
| 3sAs | c (at `b1000r4500`) | 0.362 | 0.617 | 2.55e-1 |
| 3cAc | c (at `b1000r4500`) | 0.362 | 0.596 | 2.33e-1 |
| 3cAc | f (at `b1000r4500`) | 0.446 | 0.229 | 2.17e-1 |
| 3sAs | f (at `b1000r3000`) | 0.307 | 0.091 | **2.16e-1** |

A83 max divergence dropped from previous run's 3.3e-1 → 2.71e-1
(~6pp improvement), and shifted from `b1000r3000` history to
`b1000r4500` history — consistent with Path A fixing the deep-cap
tree-shape mismatch but exposing residual upstream divergence.

### 3c. K72 worsening vs previous dry-run

K72 max diff went from **6.9e-2** (previous, with PR 35 Fix A+B only)
to **4.22e-1** (this run, with paired cap-guard added). This is
counterintuitive: the cap-guard should match Brown's shape better, not
worse. The likely explanation is that the previous run had a coverage
shortfall (53.3%) that was masking the deep cells now reached after
the renderer fix lets Rust find more histories. Per the PR 35c report,
coverage on K72 was unchanged with the paired fix alone (still 53.3%);
the renderer fix (PR 35 Fix A re-applied here manually) is what
unlocked the deeper history coverage.

So the K72 "worsening" is partly an artifact: previous run did not
look at the deep cells where divergence is concentrated; this run does.
The previous 6.9e-2 was on top-pair-K at `b1500r5000` which now shows
~21pp diff. The decision matrix's previous expectation (5pp K72
coverage with this fix) was incorrect — the deep-cap divergence is far
larger than originally diagnosed.

---

## 4. Decision matrix evaluation

| Condition | This run | Verdict |
|---|---|---|
| Both spots PASS at 5e-2, 80% coverage | NO | GO not applicable |
| One PASS, one FAIL but max diff < 1e-1 | NO | GO-WITH-FURTHER-LOOSENING not applicable |
| Either spot has max diff > 1e-1 | **YES** (K72=42pp, A83=27pp; both >1e-1) | **NO-GO** |
| Coverage < 70% on either spot | NO (test reached per-cell loop) | n/a |

**Verdict: NO-GO.**

---

## 5. Diagnosis (why Path A + Path C is insufficient)

The A83 root-cause investigation identified TWO independent root
causes:
- **(b)** Tree-shape mismatch at cap (closed by Path A: paired
  cap-guard)
- **(d)** Brown's `base_pot` in terminal utility (documented by Path C
  but NOT fixed; bias scales with `base_pot × P_win` per leaf)

The investigation also estimated "Path A reduces A83 33pp → ~22pp;
Path C accepts the residual at 5e-2 tolerance." This dry-run shows the
empirical residual is **27pp on A83 and 42pp on K72** — both well
above 5e-2.

The discrepancy between the estimate and the measurement suggests:

1. **The `base_pot × P_win` bias is much larger than the investigation
   estimated** at deep-cap facing-bet nodes. At `b1500r5000` (K72) the
   pot is already 5000+1500=6500; with base_pot=1000, the bias is
   `1000 × P_win_node` per regret-iteration. After 2000 iterations
   with DCFR discount, this can produce 40pp+ strategy shifts on
   top-pair-K hands (high P_win).

2. **There may be a third source of divergence not yet identified.**
   The 6 action-count mismatches at `b1000A` history (where Brown
   emits 2 actions, Rust emits 3) suggests the cap-guard may not be
   reaching all the nodes it should — possibly there are still nodes
   downstream of an all-in jam where Rust treats the situation as
   pre-cap and emits ALL_IN. This needs investigation.

3. **The Path A + Path C bundle's success criterion (5e-2 tolerance)
   was set without empirical validation.** The PR 35d report
   acknowledged "Full dry-run requires the v1.6.1 integration branch."
   This is that dry-run, and the prediction did not hold.

---

## 6. Recommended next action

**Do NOT ship v1.6.1.**

The A83 investigation's tractable-fix list is exhausted (Path A + B + C
all explored). Remaining options ranked by expected efficacy:

1. **Investigate the 6 action-count mismatches at `b1000A` histories.**
   Brown emits 2 actions `(c, f)` but Rust emits 3. This is independent
   evidence that some deep-cap state is NOT triggering the cap-guard.
   Likely a missing path through `enumerate_legal_actions` that
   doesn't honor `cap_reached`. Could be load-bearing for a portion of
   the K72 / A83 divergence.

2. **Empirically quantify the `base_pot × P_win` bias contribution.**
   Build a small minimal-tree test that isolates the terminal-utility
   convention divergence on a single 2-action node with known P_win,
   and verify the predicted regret-delta magnitude. If empirical
   magnitude matches the 40pp+ observation, candidate (d) alone
   explains it and the only path forward is to either:
   - Modify our `terminal_utility` to match Brown's convention (high
     risk: breaks all internal exploitability snapshots), OR
   - Widen the acceptance tolerance to 1e-1 or higher with documented
     justification (low confidence; the test becomes a structural
     correctness check, not a strict probability match).

3. **Re-define the acceptance gate** as the investigation doc §3
   alternative: action-count parity 100% + coverage ≥80% + per-action
   divergence WARN at 5e-2, FAIL at 1.5e-1 or 2e-1. This re-frames
   the gate as a "Brown structural parity" check rather than "Brown
   probability match" — defensible given the documented convention
   divergence, but a deviation from the original v1.5.0 acceptance
   contract that user/persona stakeholders should approve.

4. **Investigate the K72 worsening more carefully.** Previous dry-run
   showed 6.9e-2 max on K72; this run shows 4.22e-1. The likely
   explanation (coverage shift exposing new cells) needs confirmation.
   If the cells at `b1500r5000` were already in the previous run's
   per-cell loop but diffs were smaller, then something the bundle
   added has actively worsened the K72 equilibrium.

---

## 7. Cleanup confirmed

```
$ git worktree remove --force /tmp/v1_6_1_dryrun2_72023
$ ls -d /tmp/v1_6_1_dryrun2_72023
ls: /tmp/v1_6_1_dryrun2_72023: No such file or directory
$ git worktree list | grep dryrun2
(empty)
```

No leaked worktrees. Main working tree untouched.

---

## 8. Constraints honored

- [x] Worktree-isolated (no edits to `/Users/ashen/Desktop/poker_solver`)
- [x] No push to origin
- [x] No commit to main
- [x] No sub-agents spawned
- [x] No destructive git operations
- [x] Within 45-min time budget (cargo build ~7s, maturin develop ~7s,
      cargo lib tests ~25s, pytest 5m17s — total <30min)
