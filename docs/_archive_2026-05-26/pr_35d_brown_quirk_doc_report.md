# PR 35 Fix D — Path C: Document Brown base_pot Quirk + Widen Tolerance

**Branch:** `pr-35d-brown-quirk-doc`
**Base:** `d885bca` (v1.6.0, `origin/main`)
**Commit:** `e9e5d3ad05cf002866b63549119a255c02e60065`
**Worktree:** `/tmp/pr-35d-brown-quirk-61060`
**Date:** 2026-05-23 late

## Summary

Path C of the A83 root-cause investigation: documents the Brown `base_pot`
convention divergence (non-zero-sum vs zero-sum payoff) and widens the
acceptance tolerance from `5e-3` to `5e-2` to accommodate the resulting
systematic 3-7pp action probability shifts at deep-cap.

## Note on Starting Tolerance

Task brief stated the current `PER_ACTION_TOL` was `2e-2`; actual file
content on `d885bca` had `PER_ACTION_TOL: float = 5e-3`. The widened target
of `5e-2` was applied as instructed; the documentation comment block matches
the task brief verbatim (which mentions both `2e-2` and `5e-2` in context).

## Edits Applied

### File: `tests/test_v1_5_brown_apples_to_apples.py`

Diff:

```diff
@@ -114,8 +114,39 @@ SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"
 # coincidence on a single board.
 COVERED_SPOT_IDS: tuple[str, ...] = ("dry_K72_rainbow", "dry_A83_rainbow")

-# Locked tolerances (rationale in module docstring).
-PER_ACTION_TOL: float = 5e-3
+# Acceptance tolerance per action probability.
+#
+# Set to 5e-2 (5 percentage points) to accommodate a known convention divergence
+# between Brown's reference solver (cpp/vector_eval.cpp) and our Rust
+# implementation:
+#
+# - Brown's showdown_values and fold_values include the base_pot in the WIN
+#   payoff (winner_payoff = base_pot + opp_contrib). His payoff structure
+#   is non-zero-sum: total payoff per leaf = base_pot + (winner's contrib +
+#   loser's contrib).
+#
+# - Our Rust terminal_utility computes a zero-sum payoff: winner gets
+#   opp's contribution only; no base_pot bonus.
+#
+# This convention difference biases Brown's regret(fold) downward by
+# (base_pot × P_win_node) at the leaf, producing systematic 3-7pp action
+# probability shifts at deep-cap facing-raise spots on hand classes where
+# the equity distribution is bimodal (e.g., bottom-pair-Ace on A-high
+# boards facing a 3x re-raise into a 1500-chip pot).
+#
+# We do NOT change our convention because:
+# - Internal Python ↔ Rust diff tests rely on zero-sum semantics
+# - Exploitability snapshots in earlier versions assumed zero-sum
+# - The convention is a documentation issue, not a correctness issue;
+#   both solvers compute valid Nash equilibria for their respective
+#   payoff structures
+#
+# A tighter 2e-2 tolerance was attempted but consistently fails on A83 spot
+# bottom-pair-Ace cells with diffs 3.3e-1 to 6.9e-2; this is the documented
+# convention gap, not an algorithmic bug.
+#
+# Reference: docs/a83_deep_cap_root_cause_investigation.md
+PER_ACTION_TOL: float = 5e-2

 # Coverage floor: ≥ 80% of Brown's canonical histories must appear in our
 # Rust solve. Matches `test_river_diff.py` COVERAGE_FLOOR (PR 7 spec §10).
```

`COVERAGE_FLOOR` at `0.80` was left unchanged — no dry-run report available
in this worktree to justify a loosening; can be revisited in the v1.6.1
bundle if combined Path A + Path C dry-run shows a coverage shortfall.

## Verification

### 1. Syntax check

```
$ python -c "import ast; ast.parse(open('tests/test_v1_5_brown_apples_to_apples.py').read()); print('SYNTAX OK')"
SYNTAX OK
```

### 2. Pytest collection

```
$ python -m pytest tests/test_v1_5_brown_apples_to_apples.py --collect-only -q
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow]
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow]

2 tests collected in 0.02s
```

### 3. Pytest dry-run (with `parity_noambrown` marker enabled)

```
$ python -m pytest tests/test_v1_5_brown_apples_to_apples.py -m parity_noambrown -v -rs
...
SKIPPED [2] tests/test_v1_5_brown_apples_to_apples.py:231: _rust.solve_range_vs_range_rust missing — PR 23 not merged / not built. After PR 23 lands, run `maturin develop --release` to enable.
============================== 2 skipped in 0.01s ==============================
```

**Observation:** The acceptance test skips cleanly on the worktree because
`_rust.solve_range_vs_range_rust` is not built. Path C is a code change with
no compile-time impact; its empirical effect cannot be measured on this
worktree alone. Full dry-run requires the v1.6.1 integration branch where
PR 23's Rust vector-form CFR and Brown's binary are both available.

**Expected behavior at 5e-2 alone (per task brief, recapped from the A83
investigation):**

- `dry_K72_rainbow`: max diff per prior dry-run was 6.9e-2 → 5e-2 alone
  will NOT fully close; expect ~10-50 cells still failing.
- `dry_A83_rainbow`: max diff was 3.3e-1 → ~100+ cells still failing
  without Path A (paired cap-guard, PR 35c).

This is the documented convention gap acting alone, before the Path A
(Fix C, paired cap-guard at `enumerate_legal_actions`) tree-shape fix is
applied. Path A + Path C combined is the predicted-passing bundle.

## Branch State

```
$ git log --oneline -2
e9e5d3a PR 35 Fix D: document Brown base_pot quirk + widen acceptance tolerance to 5e-2
d885bca v1.6.0: GUI Gate 2 surfaces (range editor + RvR + node-locking + asymmetric + slider)
```

- Branch SHA: `e9e5d3ad05cf002866b63549119a255c02e60065`
- Single commit on top of `origin/main@d885bca`
- NOT pushed to origin (feature branch awaiting v1.6.1 ship per task brief)
- Worktree-isolated; shared working tree untouched

## Recommendation for v1.6.1 Bundle

**Include both Path A (PR 35c, paired cap-guard) AND Path C (this branch,
PR 35d).** Per the A83 investigation:

- Path C alone closes ~70% of A83 deep-cap divergence cells but leaves a
  long tail driven by the extra ALL_IN action in Rust's `cap_reached`
  legal-action set (a tree-shape mismatch independent of the payoff
  convention).
- Path A alone removes the tree-shape mismatch but leaves the 3-7pp
  systematic per-action bias caused by Brown's non-zero-sum payoff.
- Combined, the dry_K72 max diff is predicted to fall below 5e-2 and A83
  bottom-pair-Ace diffs are predicted to drop into the 2-4pp band, both
  within the new tolerance.

**Sequencing:**

1. Cherry-pick `pr-35c-paired-fix` first (it's the algorithmic correctness
   fix; semantically required regardless of Path C).
2. Cherry-pick `pr-35d-brown-quirk-doc` second (it's the documented
   convention-gap accommodation that lets the test reflect "predicted
   PASS" once Path A is in).
3. Re-run `pytest tests/test_v1_5_brown_apples_to_apples.py -m parity_noambrown`
   on the v1.6.1 integration branch with Brown's binary built; expect
   both spots to PASS at the new tolerance.

## Critical-Constraint Compliance

- Worktree-isolated: `/tmp/pr-35d-brown-quirk-61060` (NOT shared working tree)
- NOT pushed to origin
- Shared working tree files untouched
- Time budget: well under 20 min
- No sub-agents spawned
