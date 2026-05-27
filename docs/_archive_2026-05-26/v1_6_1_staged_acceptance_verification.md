# v1.6.1 Staged Acceptance Verification

**Date:** 2026-05-23
**Verifier:** pre-ship staging check (research-first failure protocol)
**Bundle under test:** PR 34 + PR 35 + PR 33 + PR 40 cherry-picked onto `origin/main` (`b5777f2`, v1.5.1)
**Verdict:** **NO-GO — DO NOT FIRE v1.6.1 SHIP EXECUTOR**

---

## TL;DR

The proposed v1.6.1 bundle does **NOT** make the Brown apples-to-apples
acceptance test pass. Both spots FAIL with **substantial real solver
divergence** (40+%-point differences on individual hand/action cells), far
beyond any plausible tolerance loosening. Additionally, the bundle
introduces a **new regression** in `test_exploit_diff.py` that was green on
`origin/main`. This is a true v1.5.0-style "ship then discover failures"
scenario averted by the pre-ship gate; the bundle must NOT ship as v1.6.1
without further engine work.

---

## Worktree setup

- Created `/Users/ashen/Desktop/poker_solver_worktrees/v1-6-1-staging-verify`
  detached off `origin/main` (`b5777f22 v1.5.1`).
- Created temp branch `v1-6-1-staging-verify` for the cherry-pick stack.
- Fresh `.venv` (Python 3.13.1) installed in worktree; only build/test deps
  (`maturin`, `numpy`, `pytest`, `pytest-timeout`, `psutil`). The main repo
  venv was NOT used to avoid contaminating the editable-install pointing
  at `pr-23-cell-dive`.
- Symlinked `references/ -> /Users/ashen/Desktop/poker_solver/references`
  so the pre-built `river_solver_optimized` resolves under
  `find_brown_binary()` (which anchors at the worktree root).

---

## 1. Pre-flight (PASS)

- `origin/main` HEAD: `b5777f22f99ee3b912822c0fb30d771dd03954df` ("v1.5.1:
  test rigor + docs honesty") — matches expectation.
- All 4 PR-branch SHAs accessible in local git:
  - PR 33 `29a00c0` — Python auto-delegate
  - PR 34 `0bafcfac` — Rust off-by-one fix in `dcfr_vector.rs`
  - PR 35 `33e03ea` — canonicalization + player inversion + `max_raises`
    ALL_IN engine fix
  - PR 40 `c058e97` — test-side encoding bugs A/B/C

## 2. Cherry-pick (3 clean, 1 conflict resolved)

Order per ship plan:

| Step | SHA | Conflict | Notes |
|------|-----|----------|-------|
| 1 | `0bafcfac` (PR 34) | none | Touched `crates/cfr_core/src/dcfr_vector.rs` only |
| 2 | `33e03ea` (PR 35) | none | Touched canonicalization helper + `hunl.rs` |
| 3 | `29a00c0` (PR 33) | none | Pure Python delegate addition |
| 4 | `c058e97` (PR 40) | **1** | `tests/test_v1_5_brown_apples_to_apples.py` lines 608-629 |

**Conflict count:** 1 (in PR 40, on top of PR 35 — both touched the
per-action comparison loop).

**Conflict origin:** PR 40 was authored on `b5777f2` (v1.5.1) directly,
unaware of PR 35's changes. PR 35 introduced the
`stack_ceiling`-parameterized history canonicalization and renamed the
loop variable; PR 40 independently renamed the variable to `brown_player`
and removed the (then-not-yet-existing) `stack_ceiling` argument.

**Resolution:** kept PR 40's clearer `brown_player` naming AND PR 35's
required `stack_ceiling=stack_ceiling` keyword argument. This is the only
correct semantic merge — PR 35's `stack_ceiling` is load-bearing for the
canonicalization fix, and PR 40's naming is consistent with downstream
references (line 630+) which already use `brown_player`.

After resolution, no conflict markers remain anywhere in `tests/`,
`poker_solver/`, or `crates/`. The post-resolution diff
(`HEAD~3..HEAD` of the test) is consistent with the union of intended
edits from PR 35 and PR 40.

Final staging branch log (top 4):
```
988c3fc PR 40: fix test-side encoding bugs in Brown apples-to-apples acceptance
a772904 Add Python delegate for initial_hole_cards=() (task #182)
9033266 PR 35: canonicalization fix + player-index inversion + max_raises ALL_IN engine fix
bf178c8 PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)
b5777f2 v1.5.1: test rigor + docs honesty   <-- origin/main base
```

## 3. Maturin rebuild (PASS)

```
maturin develop --release --target universal2-apple-darwin
```

- `cfr_core v0.5.0` rebuilt cleanly; release profile finished in 4.89s
  (incremental — initial cold compile was the slow leg).
- Wheel built:
  `poker_solver-1.5.1-cp313-cp313-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl`
- `poker_solver.__version__` → `1.5.1` (as expected — version bump deferred
  to the actual ship executor; this is verify-only).
- `from poker_solver._rust import solve_range_vs_range_rust` → ok.

No build errors, no clippy/rustc warnings surfaced as errors.

## 4. Acceptance test (FAIL — gate verdict)

**Command:**
```
perl -e 'alarm 900; exec @ARGV' -- .venv/bin/python -m pytest \
    tests/test_v1_5_brown_apples_to_apples.py -v -m parity_noambrown \
    -o "addopts="
```

**Wall time:** 518.29s (≈ 8m38s) for both spots.

**Result:**
- `dry_K72_rainbow` — **FAILED**
- `dry_A83_rainbow` — **FAILED**

Both spots passed Brown-solve + Rust-solve (no panic, no crash — PR 34 did
its job preventing the index-out-of-bounds), passed the coverage floor
(history canonicalization is intact under PR 35), but FAILED the
per-action probability parity check.

### Magnitude of divergence (worst cells)

| Spot | Player | Hand | Hist | Action | Brown | Rust | \|diff\| |
|------|--------|------|------|--------|-------|------|---------|
| K72  | P0     | 8hKh | b1500r5000 | c (call) | 0.875392 | 0.453725 | **0.422** |
| K72  | P0     | 8dKd | b1500r5000 | c | 0.870353 | 0.454778 | **0.416** |
| K72  | P0     | 9hKh | b1500r5000 | c | 0.839474 | 0.442320 | **0.397** |
| K72  | P0     | 8hKh | b1500r5000 | r5000 | 0.071796 | 0.316952 | **0.245** |
| K72  | P0     | 8dKd | b1500r5000 | r5000 | 0.072150 | 0.310402 | **0.238** |
| A83  | P0     | 3sAs | b1000r3000 | f (fold) | 0.306778 | 0.090832 | **0.216** |
| A83  | P0     | 3sAs | b1000r3000 | r7000 | 0.192359 | 0.319802 | **0.127** |

Top diff is **0.422 (42 percentage points)** — many orders of magnitude
beyond the 2e-2 (2pp) tolerance set by PR 40. **Total divergent cells:**
~395 (K72) + ~415 (A83) = ~810 across both spots, with diffs ranging from
~2e-2 (right at tolerance) up to 0.42.

### Interpretation

The semantic action permutation (PR 40 Fix A) and the player-slot swap
(PR 40 Fix B + PR 35 player-index inversion) ARE working as intended —
the failure rows show `brown_pos=1, rust_pos=0` for `f` and
`brown_pos=0, rust_pos=1` for `c` at facing-bet nodes, which is the
expected Brown[c,f,...] vs Rust[f,c,...] mapping. So the test framing is
no longer the bug.

What's left is a **real solver-level disagreement**: with identical hand
sets, identical history coverage, and the corrected encoding, the Rust
vector CFR is converging to a meaningfully different strategy than
Brown's binary at high-stakes facing-bet nodes. This is consistent with
the PR 23 P0 root-cause stack (the engine bundle deferred from v1.5.1 to
v1.5.2 was supposed to fix this), so the conclusion is:

> **PR 34 + PR 35 + PR 33 + PR 40, as currently composed, do NOT close the
> Brown acceptance gate.** Something in the Rust vector-form CFR is still
> structurally different from Brown's reference, beyond the index panic
> (fixed) and the canonicalization (fixed). PR 40 §"Note" in the commit
> message correctly stated that PR 40 alone would not make the test pass
> and that PR 34/PR 35 had to land alongside — but with all three applied
> here, the test still fails by large margins.

## 5. Sanity tests

```
.venv/bin/python -m pytest tests/test_dcfr_diff.py tests/test_exploit_diff.py \
    tests/test_range_vs_range_aggregator.py tests/test_node_locking.py \
    tests/test_python_delegate.py -v
```

**Wall time:** 359.19s (≈ 6m).

**Result:** **1 failure, 54 passed.**

### NEW REGRESSION (introduced by the bundle):

```
FAILED tests/test_exploit_diff.py::test_fixed_combo_river_single_bet_size_matches
  python=4.1666666667 rust=3.7500000000 delta=4.167e-01
  abs(0.4166666666666661) <= 1e-06   # AssertionError
```

A 0.417 (42%) exploitability mismatch between the Python and Rust solver
on a fixed-combo river config with `bet_fractions=(1.0,)`,
`postflop_raise_cap=1`. The Python implementation reports 4.167; the Rust
implementation (post-bundle) reports 3.75. The 1e-6 tolerance is for
algorithmic equivalence — this delta is well past any acceptable
tolerance. This test was presumed green on `origin/main` (no
PR-34/35-related test changes), so the regression is attributable to one
of the engine commits in the bundle (PR 34 or PR 35; PR 33 is pure
Python and shouldn't be implicated).

### PASSED suites (all green):

- `test_dcfr_diff.py` — full Kuhn/Leduc/HUNL parity vs Python reference,
  all passing.
- `test_range_vs_range_aggregator.py` — 18/18 passed.
- `test_node_locking.py` — 19/19 passed (Python + Rust paths).
- `test_python_delegate.py` (NEW from PR 33) — 5/5 passed; the auto-delegate
  routes correctly to the Rust vector-form CFR and falls back gracefully
  on locked strategies / sarah-budget compliance.

## 6. Default-marker skip behavior

Plan step 5b expected `pytest tests/test_v1_5_brown_apples_to_apples.py`
(no `-m`) to "SKIP gracefully when not opt-in." Empirically this is
**NOT** the current behavior: `pyproject.toml` registers
`parity_noambrown` and `slow` as markers but does NOT add them to a
default `addopts = "-m 'not slow'"` or similar deselection. So a plain
`pytest tests/test_v1_5_brown_apples_to_apples.py` actually runs the
Brown solve + Rust solve at full cost (terminated by the test-level
`@pytest.mark.timeout(BROWN_TIMEOUT_SEC + 1800)`, not by the file-level
30-90s default).

This is a documentation/plan mismatch only — not a blocker for v1.6.1 —
but worth surfacing because the ship-plan step relied on a graceful skip
that doesn't exist.

## 7. Cleanup

The temp worktree at `/Users/ashen/Desktop/poker_solver_worktrees/v1-6-1-staging-verify`
will be removed after this report is finalized. The temp staging branch
(`v1-6-1-staging-verify`) is not pushed anywhere; it lives only in the
shared `.git` and can be deleted at leisure.

The `references/` symlink inside the verify worktree is local to that
worktree and is removed along with it.

---

## Recommendation: NO-GO

**Do NOT fire the v1.6.1 ship executor on the current PR 33 + 34 + 35 + 40
bundle.**

Three blocker findings:

1. **Acceptance gate FAILS 2/2 spots with magnitudes far beyond
   tolerance.** The headline "Brown apples-to-apples = GREEN" cannot
   ship; if this v1.6.1 were released, the next persona test cycle would
   re-flag the same failure that v1.5.0 hit, only with the additional
   embarrassment of having claimed to have fixed it.

2. **NEW REGRESSION in `test_exploit_diff.py`** introduced by one of the
   engine commits (PR 34 or PR 35). This breaks Python↔Rust equivalence
   on the simple fixed-combo river — a foundational invariant that has
   been green since well before v1.4.

3. The pattern (large per-cell divergence at high-stakes facing-bet
   nodes, with action encoding correct) suggests there is at least one
   additional algorithmic bug in the Rust vector-form CFR beyond the
   index-panic and canonicalization fixes. Triage starts at
   `crates/cfr_core/src/dcfr_vector.rs` (per the test's own pytest.fail
   hint) and should include a CFR-by-CFR comparison vs `trainer.cpp:138-209`,
   not just the recursion structure but the regret/reach-prob updates,
   the iteration accounting (DCFR alpha/beta/gamma), and the sampling
   convention at chance nodes if any.

**Next-step suggestions (NOT in scope for this verification):**

- Spawn a focused triage agent on the `dcfr_vector.rs` vs `trainer.cpp`
  diff, with the worst-case cells from §4 as the reproducer. Focus first
  on facing-bet decision rows where Rust over-folds (K72: brown 0.09
  fold → rust 0.26 fold = 3x over-folding) and under-calls (K72: brown
  0.87 call → rust 0.45 call).
- Separately bisect `test_fixed_combo_river_single_bet_size_matches`
  against PR 34 alone vs PR 35 alone — the regression source is likely
  PR 35 (since PR 34 is a bounds check that should not change
  exploitability when the panicking case wasn't otherwise reached), but
  this is a hypothesis that needs the per-commit bisection.
- Hold v1.6.1 in staging; v1.5.1 remains the latest-good origin/main.

---

**Verifier worktree path (transient):**
`/Users/ashen/Desktop/poker_solver_worktrees/v1-6-1-staging-verify`
(removed at end of this verification)

**Verification staging branch:** `v1-6-1-staging-verify`
(local-only, not pushed; can be discarded)
