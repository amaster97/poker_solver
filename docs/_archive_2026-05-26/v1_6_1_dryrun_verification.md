# v1.6.1 Engine Bundle — Dry-Run Verification

**Date:** 2026-05-23 (late)
**Mode:** READ-ONLY dry-run in disposable git worktree at `/tmp/v1_6_1_dryrun_55579`.
**Main working tree NOT modified.** Worktree removed at end of session.

**Source docs being verified:**
- Prep: `docs/v1_6_1_merge_sequence.md`
- Synthesis: `docs/v1_6_1_final_synthesis.md`

---

## TL;DR

**Verdict: NO-GO.**

The composed bundle (`PR 33 + PR 34 + PR 35-A + PR 35-B + PR 40`) cherry-picks cleanly per the
prep doc's recipe, but **both Brown apples-to-apples acceptance tests FAIL at the synthesis's
expected 2e-2 tolerance**. A83 in particular shows |diff| up to **3.3e-1** on a single
infoset/hand cell — far beyond any documented Nash polytope sizing-mix residual. This
triggers fallback rule §8 row 4 of the prep doc / §5 row 4 of the synthesis: "**HOLD
v1.6.1**, spawn deep-investigation agent (best-response cross-check + iteration sweep)".

The bisection's H3 ("PR 23 has an additional algorithmic divergence") is **empirically
re-confirmed** by this dry-run. The synthesis's refutation of H3 (via line-by-line triage)
does not align with the actual empirical run.

---

## 1. Pre-flight: branch SHAs verified

All four SHAs match the prep doc:

| PR | Branch | Expected SHA | Actual SHA | Match |
|---|---|---|---|---|
| PR 33 | `pr-33-python-delegate` | `29a00c0` | `29a00c0` | YES |
| PR 34 | `pr-34-p0-off-by-one` | `0bafcfa` | `0bafcfa` | YES |
| PR 35 | `pr-35-canonicalization` | `33e03ea` | `33e03ea` | YES |
| PR 40 | `pr-40-acceptance-test-fix` | `c058e97` | `c058e97` | YES |

Base: `origin/main = 9a2a89e` (matches prep doc).

---

## 2. Cherry-pick sequence — clean, with one expected conflict

### Step 1 — PR 34 (Rust off-by-one) — CLEAN

```
git cherry-pick pr-34-p0-off-by-one
→ [detached HEAD cda65fc] PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)
  1 file changed, 24 insertions(+), 4 deletions(-)
```

No conflicts. File touched: `crates/cfr_core/src/dcfr_vector.rs`.

### Step 2 — PR 33 (Python delegate) — CLEAN

```
git cherry-pick pr-33-python-delegate
→ [detached HEAD 16d0df6] Add Python delegate for initial_hole_cards=() (task #182): routes to Rust vector-form CFR when applicable
  2 files changed, 530 insertions(+), 1 deletion(-)
  create mode 100644 tests/test_python_delegate.py
```

No conflicts. Files touched: `poker_solver/hunl_solver.py`, `tests/test_python_delegate.py` (new).

### Step 3 — PR 35 Fix A+B only (drop Fix C) — CLEAN per recipe

```
git cherry-pick -n pr-35-canonicalization
→ staged: crates/cfr_core/src/hunl.rs        (Fix C)
          tests/test_v1_5_brown_apples_to_apples.py  (Fix A + Fix B)

git restore --staged --worktree crates/cfr_core/src/hunl.rs
→ Fix C dropped; only test-file changes remain staged.

git commit -m "PR 35 (Fix A+B only): canonicalization + player-index inversion (Fix C dropped...)"
→ [detached HEAD ff58b06] ...
  1 file changed, 33 insertions(+), 6 deletions(-)
```

Verified: post-step `hunl.rs` is byte-identical to `origin/main` (Fix C dropped cleanly).
Staged hunks confirmed as Fix A (`stack_ceiling` ALL-IN token in renderer) + Fix B
(`rust_player = 1 - player` lookup) — no engine code.

### Step 4 — PR 40 — ONE EXPECTED CONFLICT at line 608 of the test file

```
git cherry-pick pr-40-acceptance-test-fix
→ Auto-merging tests/test_v1_5_brown_apples_to_apples.py
  CONFLICT (content): Merge conflict in tests/test_v1_5_brown_apples_to_apples.py
```

Conflict location: single hunk at lines 608-629 of `tests/test_v1_5_brown_apples_to_apples.py`,
inside the per-action loop. Matches prep doc §3a expectation exactly.

**Resolution** (per prep doc §3b): kept PR 40's loop rename (`for brown_player in (0, 1)`,
`rust_player = 1 - brown_player`) and kept PR 35 Fix A's `stack_ceiling=stack_ceiling` kwarg
in the `_rust_history_substr_for_canonical(...)` call. Mechanical, ~30 seconds.

After resolution:

```
git add tests/test_v1_5_brown_apples_to_apples.py
git cherry-pick --continue
→ [detached HEAD eb5ad01] PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance
  1 file changed, 103 insertions(+), 20 deletions(-)
```

### Final bundle: 4 commits above `origin/main`

```
eb5ad01 PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance
ff58b06 PR 35 (Fix A+B only): canonicalization + player-index inversion (Fix C dropped...)
16d0df6 Add Python delegate for initial_hole_cards=() (task #182)...
cda65fc PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)
9a2a89e examples: add range-vs-range river solve example  (= origin/main)
```

File-level diff vs `origin/main` (4 files, 686 ins / 27 del):

```
 crates/cfr_core/src/dcfr_vector.rs        |  28 ++-
 poker_solver/hunl_solver.py               | 247 +++++++++++++++++++++++++-
 tests/test_python_delegate.py             | 284 ++++++++++++++++++++++++++++++
 tests/test_v1_5_brown_apples_to_apples.py | 154 +++++++++++++---
```

Bundle composition **matches the prep doc / synthesis exactly**. `crates/cfr_core/src/hunl.rs`
is untouched (Fix C correctly excluded).

---

## 3. Acceptance test result — BOTH SPOTS FAIL

Run: `pytest tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown`
(2000 DCFR iterations, tolerance 2e-2 per `PER_ACTION_TOL`, coverage floor 80%)

Total runtime: **495.05 s** (~8 min 15 s) — Brown subprocess + Rust solve per spot.

```
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow] FAILED
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow] FAILED
=================== 2 failed, 1 warning in 495.05s (0:08:15) ===================
```

### 3a. `dry_K72_rainbow` — FAIL: ~433 cells exceed 2e-2 tolerance

Sample of worst diffs (all on history `'b1500r5000'`, i.e. P1 bets 1500 → P0 raises 5000,
which is a deep-cap facing-bet sequence):

| Hand | Action | Brown | Rust | \|diff\| |
|---|---|---|---|---|
| 9hKh | f (brown_pos=1, rust_pos=0) | 0.0895 | 0.1584 | **6.90e-2** |
| 9hKh | r5000 (pos 2,2) | 0.0711 | 0.0214 | **4.96e-2** |
| 9dKd | f | 0.1018 | 0.1635 | **6.16e-2** |
| 9dKd | r5000 | 0.0709 | 0.0266 | **4.43e-2** |
| 8hKh | c (brown_pos=0, rust_pos=1) | 0.8754 | 0.9016 | 2.62e-2 |
| 8hKh | r5000 | 0.0718 | 0.0364 | 3.54e-2 |
| TsQs | f | 0.9536 | 0.9761 | 2.25e-2 |
| TsQs | r5000 | 0.0464 | 0.0239 | 2.25e-2 |

Pattern: at the deep-cap raise node `b1500r5000`, Rust **over-folds** (`f` higher than Brown
by ~3-7pp) and **under-raises** (`r5000` lower than Brown by ~2-5pp), with `c` (call)
absorbing the offset where applicable. This is exactly the 22-42pp facing-bet symptom the
bisection diagnosed (though magnitudes here are smaller — possibly because PR 40's column
remap is now applied; `brown_pos != rust_pos` columns are visible in the report).

### 3b. `dry_A83_rainbow` — FAIL: ~655 cells exceed 2e-2 tolerance; max \|diff\| 3.3e-1

Sample of worst diffs (on history `'b1000r3000'`, P1 bets 1000 → P0 raises 3000):

| Hand | Action | Brown | Rust | \|diff\| |
|---|---|---|---|---|
| 3sAs | c (brown_pos=0, rust_pos=1) | 0.3638 | 0.6852 | **3.21e-1** |
| 3sAs | f (pos 1,0) | 0.3068 | 0.1728 | **1.34e-1** |
| 3sAs | r3000 (2,2) | 0.0088 | 0.0447 | 3.58e-2 |
| 3sAs | r6000 (3,3) | 0.1282 | 0.0364 | **9.18e-2** |
| 3sAs | r7000 (4,4) | 0.1924 | 0.0609 | **1.31e-1** |
| 3cAc | c | 0.3565 | 0.6864 | **3.30e-1** |
| 3cAc | f | 0.2975 | 0.1808 | **1.17e-1** |
| 9hTh | f | 1.0000 | 0.9001 | **9.99e-2** |
| 9hTh | r7000 | 0.0000 | 0.0999 | **9.99e-2** |

Pattern: A83 P0 with bottom-pair AAA-x (3sAs/3cAc) facing a raise — Rust calls dramatically
more than Brown (0.69 vs 0.36, 33-pp delta) and folds/raises less. This is **not** Nash
polytope sizing-mix residual; it's a substantive strategy difference on the same cell.

### 3c. Action-axis permutation IS being applied

The output reports `(brown_pos=N, rust_pos=M)` for each diff. On facing-bet histories, the
positions differ (brown_pos=0 c↔rust_pos=1, brown_pos=1 f↔rust_pos=0), confirming
`_brown_to_rust_action_permutation` from PR 40 is in effect. The divergence is therefore
**semantic** (same action, different probability) — not a position-axis mis-alignment.

### 3d. Coverage status

The acceptance test would have raised a coverage-floor failure BEFORE the per-cell loop if
coverage <80%. Since the test reached the per-cell-diff assertion (i.e. the `pytest.fail`
inside the per-action loop), coverage on BOTH spots was ≥80%. Synthesis §5 row 4 fallback
("coverage 70-79% → spawn PR 45") does **not** apply; the failure is per-cell, not coverage.

---

## 4. Cargo test result — 4 environmental failures, NOT bundle-introduced

`cargo test --all --release` ran 90+ tests; the only failing suite was `test_hunl_rust`
(4 of 13 failed): all four are PyO3 integration tests that import `from poker_solver` and
hit a circular-import error because the worktree's Python source shadowed the main tree's
installed `_rust.so`. Specific tests:

- `test_abstraction_canonicalization_matches_python`
- `test_hunl_strength_eval_matches_python`
- `test_hunl_infoset_key_lossless_format`
- `test_hunl_infoset_key_bucketed_format`

**These failures are environment artifacts**, not bundle regressions:

1. The 4 failing tests touch `enumerate_legal_actions`, `infoset_key`, `strength_eval`,
   `canonicalization` — none of which any of PR 33/34/35-A+B/40 modify.
2. `crates/cfr_core/tests/test_hunl_rust.rs` is byte-identical between the worktree and
   `origin/main` (verified via `diff`).
3. The PyO3 tests insert `std::env::current_dir()` into `sys.path` AFTER the venv's `.pth`
   has already pulled in `/Users/ashen/Desktop/poker_solver/poker_solver`, producing the
   shadowing that triggers the circular-import.

The remaining cargo suites — including `cfr_core` unit tests (19 passing in the cfr_core
crate-level test set) — passed. PR 34's off-by-one fix loaded correctly in the worktree's
`_rust.so` (the acceptance test's Rust solve ran to completion on both K72 and A83 without
the previously-panicking `dcfr_vector.rs:651` panic on A83 — concrete empirical confirmation
of PR 34 correctness).

A clean cargo verification post-ship will need to be done against the actual ship worktree
that has maturin-develop'd into a private venv, not the shared `/Users/ashen/Desktop/poker_solver/.venv`.

---

## 5. Cross-reference with synthesis claims

| Synthesis claim | Empirical result |
|---|---|
| §1 "PR 23 vector-form CFR algorithmically correct" | **REFUTED**. A83 max \|diff\|=0.33 on bottom-pair facing raise. |
| §1 "22-42pp divergence is test-side artifact" | **PARTIALLY REFUTED**. K72 max diff is ~7pp (so PR 40 *did* reduce the 22-42pp signal), but A83 max diff is 33pp — the bisection's algorithmic-bug hypothesis is supported. |
| §1 "Acceptance expected PASS at 2e-2" | **REFUTED**. ~1100 cells across the two spots exceed 2e-2. |
| §1 footnote: "deep-dive verified empirically" | The deep-dive's empirical validation was apparently on a **subset** of cells; full re-run shows residual divergence. |
| §1 "honest caveat — 10-15% residual probability deeper algorithmic delta exists" | **TRIGGERED**. We are in the 10-15% residual case. |
| §5 fallback row 4 ("one spot >1e-1 → HOLD") | A83 hits this. |

---

## 6. Ship verdict: NO-GO

Per synthesis §5 fallback rules:
- A83 max \|diff\| = 3.3e-1 (much greater than 1e-1 threshold) → "**HOLD v1.6.1 ship and
  spawn deep-investigation agent (best-response cross-check + iteration sweep)**"

Specific blocker: **A83 deep-cap facing-bet probabilities diverge by up to 33 percentage
points on bottom-pair-Ace hands at history `b1000r3000`**. This is not Nash polytope
residual; it indicates a real algorithmic difference between PR 23's Rust vector-form CFR
and Brown's reference `trainer.cpp:138-209`.

Important: the **bisection's H3 verdict** (PR 23 has an additional algorithmic divergence)
is **empirically supported** by this dry-run. The synthesis's line-by-line triage refutation
was incomplete — at least one path through `dcfr_vector.rs` deviates from `trainer.cpp` in a
way the structural read did not surface. Recommend the deep-investigation agent start by:

1. Side-by-side comparing `dcfr_vector.rs::traverse` line-by-line against `trainer.cpp:138-209`
   for the facing-raise (`r3000` → action set) path specifically, with attention to
   reach-probability propagation and regret update on the bottom-pair-Ace cells.
2. Best-response cross-check: solve A83 with vanilla CFR (no DCFR discount) and check if
   the divergence persists — if it disappears, the DCFR discount application is the bug.
3. Iteration sweep: re-run at iterations ∈ {500, 1000, 2000, 4000, 8000} on A83; if the
   divergence shrinks monotonically, it's a convergence-rate issue (PR 23 may need more
   iterations). If it plateaus, it's algorithmic.

---

## 7. Action item: PR 35 Fix C revisit

Note that during the dry-run we DROPPED PR 35 Fix C (the `enumerate_legal_actions`
`!cap_reached` guard) per synthesis §2 instruction. That decision was based on the
synthesis's claim that Fix C breaks `test_exploit_diff` parity. **If the deep-investigation
agent finds that the A83 divergence is caused by ACTION_ALL_IN emission asymmetry at the
cap**, then Fix C may be load-bearing for the acceptance test after all — but it would need
the parallel Python fix in `action_abstraction.py:236-237` to preserve `test_exploit_diff`
parity. This is orthogonal to the dry-run verdict but worth flagging.

---

## 8. Worktree cleanup confirmed

```bash
git worktree remove --force /tmp/v1_6_1_dryrun_55579
# Verified: /tmp/v1_6_1_dryrun_55579 no longer exists.
# Main tree untouched:
#   - poker_solver/_rust.cpython-313-darwin.so mtime preserved (May 23 06:49:54)
#   - git status delta count unchanged (124 entries, matching pre-session)
#   - HEAD = 9a2a89e (origin/main)
```

No leaked worktrees. No modifications to main working tree.

---

## 9. Recommendation

1. **DO NOT execute the v1.6.1 ship.** The acceptance gate is NOT satisfied by the composed
   bundle.
2. **Re-open the bisection vs triage reconciliation.** The bisection's H3 (PR 23 deep-cap
   algorithmic bug) is empirically supported; the triage's HIGH-confidence NEGATIVE finding
   needs revision. The 10-15% caveat the synthesis carried turned out to be the actual case.
3. **Spawn a deep-investigation agent** with the workplan in §6 above.
4. **Update synthesis doc framing** to reflect that the empirical run did NOT confirm the
   "expected PASS at 2e-2" prediction.
5. The cherry-pick mechanics themselves work as the prep doc specified — if a deeper
   engine fix is identified later, the same merge sequence will work post-fix. The
   blocker is the acceptance verdict, not the merge mechanics.
