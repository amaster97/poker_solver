# v1.6.1 Bundle Bisection Diagnosis

**Date:** 2026-05-23
**Verifier:** bisection diagnostic (research-first failure protocol)
**Bundle under test:** PR 33 + PR 34 + PR 35 + PR 40 (the proposed v1.6.1 ship)
**Predecessor:** `docs/v1_6_1_staged_acceptance_verification.md`
   (NO-GO verdict on full bundle: 2/2 spots FAIL @ 22-42pp; NEW
   `test_exploit_diff.py` regression)
**Verdict:** ALL four PRs are individually load-bearing for their
   respective targets, but PR 35's Fix C is **structurally inconsistent**
   with the Python solver and PR 23's Rust vector-form CFR has at least
   one **additional algorithmic divergence from Brown**. v1.6.1 should
   NOT ship as currently composed.

---

## TL;DR

Three findings from the bisection:

1. **PR 34 is load-bearing.** Without it, the `dry_A83_rainbow` spot
   panics at `dcfr_vector.rs:363` (index out of bounds 49/49) before the
   Rust vector-form CFR can return a strategy. PR 34 fixes this.
2. **PR 35 Fix A (renderer) is load-bearing for coverage.** Without it,
   K72 coverage drops to 53.3% and A83 coverage to 66.7%, both below
   the 80% floor. PR 35 Fix A restores K72 to 100%.
3. **PR 35 Fix C (Rust engine ALL_IN-at-cap) is the source of the
   `test_exploit_diff.py` regression.** PR 35 modified the Rust
   `enumerate_legal_actions` to skip `ACTION_ALL_IN` when the raise
   cap is reached. The Python `enumerate_legal_actions` in
   `poker_solver/action_abstraction.py` was NOT updated to match,
   creating a structural Python-Rust divergence. Test-A and Test-B
   (which lack PR 35) pass `test_exploit_diff.py` 5/5; Test-C (also
   without PR 35) passes 5/5; the full bundle (with PR 35) fails.
4. **PR 23's Rust vector-form CFR has at least one ALGORITHMIC bug
   beyond the index panic and renderer issue.** Even with PR 33 + 34 +
   35 + 40 all applied (per the staging verification), per-action
   probabilities diverge from Brown by 22-42pp on facing-bet decision
   rows at high stakes. This is real solver-level disagreement, not
   test plumbing.

PR 33 (Python delegate) is innocuous — it does not affect the underlying
acceptance test (which calls Rust directly) and does not contribute to
any failure.

---

## Bisection setup

Three temp worktrees, each branched from `v1.5.0` (`dc3df6c`):

| Branch | Cherry-picks (in order) | Purpose |
|--------|------------------------|---------|
| `bisect-A` (test-A) | PR 40 only | Is the test fix sufficient on plain v1.5.0? |
| `bisect-B` (test-B) | PR 34 → PR 40 | Off-by-one fix + test fix, no PR 33/35 |
| `bisect-C` (test-C) | PR 34 → PR 33 → PR 40 | Python delegate + off-by-one + test fix, no PR 35 |

All cherry-picks applied cleanly with no conflicts.

Each worktree had its own `.venv` (Python 3.13.1) with build/test deps
only (`maturin`, `numpy`, `pytest`, `pytest-timeout`, `psutil`).

Each worktree was built with:

```
PATH=$HOME/.cargo/bin:$PATH .venv/bin/maturin develop --release \
    --target universal2-apple-darwin
```

All three builds completed cleanly (12-13s incremental on top of the
shared `~/.cargo/registry`; the underlying release compile took 4.2-4.4s
per worktree).

Each worktree was symlinked `references/ -> /Users/ashen/Desktop/poker_solver/references`
so the pre-built `river_solver_optimized` resolved.

---

## Per-test results

### Test A: PR 40 only (no PR 33/34/35)

**Build:** OK (`poker_solver.__version__ = 1.5.0`).

**`test_exploit_diff.py` (5 tests):** **5/5 PASS** in 50.8s.

```
PASSED test_fixed_combo_river_empty_strategy_matches
PASSED test_fixed_combo_river_after_short_solve_matches
PASSED test_fixed_combo_river_single_bet_size_matches   <-- the regression detector
PASSED test_chance_enum_river_completes_within_perf_gate
PASSED test_chance_enum_river_end_to_end_solve_within_perf_gate
```

**Acceptance test (`test_v1_5_brown_apples_to_apples.py`):**
**2/2 FAIL** in 200.9s (3m20s).

| Spot | Verdict | Failure | Detail |
|------|---------|---------|--------|
| `dry_K72_rainbow` | FAIL | History coverage gate | coverage 53.3% (16/30 < 80%) |
| `dry_A83_rainbow` | FAIL | Rust panic | `index out of bounds: the len is 49 but the index is 49` at `dcfr_vector.rs:363` |

K72 fails the *coverage* assertion (PR 35 Fix A is missing — the
`_rust_history_substr_for_canonical` renderer never emits "A" for
canonical-amount-equals-stack-ceiling), so 14/30 Brown histories don't
match any Rust key.

A83 panics in the Rust vector-form CFR (PR 34 is missing — the
asymmetric range 49 vs 50 walks past `reach_opp.len()` and panics at
the opponent-node branch in `traverse`).

### Test B: PR 34 + PR 40 (no PR 33/35)

**Build:** OK (`poker_solver.__version__ = 1.5.0`).

**`test_exploit_diff.py` (5 tests):** **5/5 PASS** in 51.5s.

```
PASSED test_fixed_combo_river_empty_strategy_matches
PASSED test_fixed_combo_river_after_short_solve_matches
PASSED test_fixed_combo_river_single_bet_size_matches   <-- the regression detector
PASSED test_chance_enum_river_completes_within_perf_gate
PASSED test_chance_enum_river_end_to_end_solve_within_perf_gate
```

**Acceptance test:** **2/2 FAIL** in 523.0s (8m43s).

| Spot | Verdict | Failure | Detail |
|------|---------|---------|--------|
| `dry_K72_rainbow` | FAIL | History coverage gate | coverage 53.3% (16/30 < 80%) (inferred from test-A — same K72 coverage failure mode without PR 35; the truncated log only shows A83 traceback) |
| `dry_A83_rainbow` | FAIL | History coverage gate | coverage 66.7% (28/42 < 80%) |

A83 NO LONGER panics (PR 34 is in place), but BOTH spots now fail
the *coverage* gate. K72 stays at 53.3% (PR 35 Fix A is the renderer
fix that K72 needs). A83 at 66.7% is below floor too — so Brown's
A83 profile has the same "A"-token canonicalization gap.

This is the key result: **PR 35 Fix A is load-bearing for coverage on
both K72 and A83**. Without it, neither spot can clear the coverage
floor, so we never even reach the per-action parity check.

### Test C: PR 34 + PR 33 + PR 40 (no PR 35)

**Build:** OK (`poker_solver.__version__ = 1.5.0`).

**`test_exploit_diff.py` (5 tests):** **5/5 PASS** in 51.9s.

```
PASSED test_fixed_combo_river_empty_strategy_matches
PASSED test_fixed_combo_river_after_short_solve_matches
PASSED test_fixed_combo_river_single_bet_size_matches   <-- the regression detector
PASSED test_chance_enum_river_completes_within_perf_gate
PASSED test_chance_enum_river_end_to_end_solve_within_perf_gate
```

**Acceptance test:** **2/2 FAIL** in 519.3s (8m39s).

| Spot | Verdict | Failure | Detail |
|------|---------|---------|--------|
| `dry_K72_rainbow` | FAIL | History coverage gate | coverage 53.3% (16/30) (inferred — same as test-B) |
| `dry_A83_rainbow` | FAIL | History coverage gate | coverage 66.7% (28/42) |

Identical failure profile to test-B. PR 33 (Python delegate) has no
effect on the acceptance test (which calls Rust directly via
`_rust_solve_rvr`), so adding it does not change any verdict.

### Test D: same as Test A (PR 40 only on v1.5.0)

Per the bisection plan, Test D was specified as "PR 23 baseline + PR
40 test fix (no further engine changes)" — this is exactly Test A. No
separate worktree was needed; Test A's result stands for both A and
D. The plan's interpretation: A83's panic at `dcfr_vector.rs:363`
confirms PR 23 vector-form CFR has a real bug (off-by-one) that PR 34
correctly fixes.

### Recap: full v1.6.1 bundle (PR 33 + 34 + 35 + 40)

Re-stating from `docs/v1_6_1_staged_acceptance_verification.md` for
comparison:

- `test_exploit_diff.py`: **1/5 FAIL** (`test_fixed_combo_river_single_bet_size_matches`
  has python=4.167, rust=3.75, delta=0.417 > 1e-6 tolerance).
- Acceptance test: **2/2 FAIL** with per-action divergences up to
  0.422 (42pp) on facing-bet rows. Coverage now PASSES at 100% (PR
  35 Fix A restores it), so the test reaches the per-action parity
  check — and then fails there.

---

## Matrix view: which PRs are necessary for what?

| Component | A (PR 40) | B (34+40) | C (33+34+40) | Full (33+34+35+40) |
|-----------|----------|-----------|--------------|---------------------|
| PR 34 in tree? | NO | YES | YES | YES |
| PR 35 in tree? | NO | NO | NO | YES |
| `test_exploit_diff::test_fixed_combo_river_single_bet_size_matches` | PASS | PASS | PASS | **FAIL** |
| K72 coverage | 53.3% FAIL | 53.3% FAIL | 53.3% FAIL | 100% (per stage doc) |
| A83 panic | YES (`:363`) | NO | NO | NO |
| A83 coverage | (panicked) | 66.7% FAIL | 66.7% FAIL | 100% (per stage doc) |
| K72 per-action parity | (not reached) | (not reached) | (not reached) | FAIL ~42pp |
| A83 per-action parity | (not reached) | (not reached) | (not reached) | FAIL ~21pp |

---

## Hypothesis verdicts

### H1 (PR 35 Fix C introduced `test_exploit_diff` regression): **CONFIRMED**

The regression is exactly attributable to PR 35 Fix C. Test-C (PR 33 +
PR 34 + PR 40, lacking only PR 35) passes `test_exploit_diff.py` 5/5
including `test_fixed_combo_river_single_bet_size_matches`. The full
bundle (which adds PR 35) fails the same test with delta=0.417.

**Mechanism (now confirmed by source inspection):**

- PR 35 (`crates/cfr_core/src/hunl.rs:1136-1144`): adds
  `&& !cap_reached` to the `ACTION_ALL_IN` push in
  `enumerate_legal_actions`, mirroring Brown's
  `river_game.cpp:76-78`.
- Python (`poker_solver/action_abstraction.py:236-237`): still pushes
  `ACTION_ALL_IN` unconditionally when `ctx.include_all_in` is true,
  regardless of `cap_reached`.

For `_fixed_combo_river_config(bet_fractions=(1.0,), postflop_raise_cap=1)`:
once the first raise lands, raise_count=1 = cap=1, so cap_reached=True.
At that node, Brown emits {c, f}; PR 35-patched Rust now emits {c, f}
(matches Brown); but Python still emits {c, f, A}. So Python's
exploitability walk includes an ALL_IN branch that Rust's walk
doesn't — hence python=4.167, rust=3.75 (= 4.167 - 0.417, almost
exactly the ALL_IN branch's contribution).

### H2 (PR 34's off-by-one fix is wrong direction): **REJECTED**

PR 34's fix is correct and load-bearing. Without PR 34, A83 panics at
`dcfr_vector.rs:363` with "index out of bounds: the len is 49 but the
index is 49" — exactly the bug PR 34's commit message describes. The
fix changes `opp_hands` (= `hand_count[1 - player]`) to `player_hands`
(= `hand_count[player]`) in the opponent-node branch of
`VectorDCFR::traverse`, mirroring Brown's `trainer.cpp:170-173` where
`opp_hands = num_hands_[node.player]`. PR 34 IS structurally
empirically correct.

### H3 (PR 23 has additional algorithmic bugs beyond PR 34): **CONFIRMED**

With all four PRs applied, the per-action parity check STILL fails by
22-42pp on facing-bet decision rows. Source: `docs/v1_6_1_staged_acceptance_verification.md`
§4 ("Magnitude of divergence (worst cells)"). This is real solver
disagreement — the test plumbing is correct (PR 40's action
permutation + player-slot mapping is confirmed by §"Interpretation"),
the coverage is 100% (PR 35 Fix A), the panic is fixed (PR 34), and
the player-index inversion in the comparison is correct (PR 35 Fix
B). What remains is a deeper algorithmic bug in `dcfr_vector.rs` that
this bisection did not pinpoint to a specific line.

Triage hint (from staging doc §5): Rust over-folds at facing-bet
high-stakes nodes (K72: brown 0.09 fold → rust 0.26 fold = 3x
over-folding) and under-calls (K72: brown 0.87 call → rust 0.45 call).
This pattern is consistent with an incorrect regret update on the
fold action at deep-cap nodes, or an opponent-reach-probability error
that biases the call action down.

### H4 (PR 33's Python delegate has a routing bug): **REJECTED**

PR 33 changes only `poker_solver/__init__.py` and adds
`tests/test_python_delegate.py`. The acceptance test
`tests/test_v1_5_brown_apples_to_apples.py` does NOT use the Python
delegate — it calls `_rust_solve_rvr` directly (see test-A log lines
51-59). PR 33 cannot affect the acceptance test outcome. Test-B and
Test-C produced identical acceptance-test failure profiles
(K72 53.3% / A83 66.7%), confirming PR 33 is a no-op on this test.

---

## `test_exploit_diff` regression attribution: PR 35

Confirmed by elimination:

- Test-A (PR 40 only): `test_fixed_combo_river_single_bet_size_matches` PASSES.
- Test-B (PR 34 + PR 40): PASSES.
- Test-C (PR 33 + PR 34 + PR 40): PASSES.
- Full bundle (PR 33 + 34 + 35 + 40): FAILS at delta=0.417.

The only PR present in the failing case and absent from all passing
cases is **PR 35**. Of PR 35's three sub-fixes:

- Fix A (test renderer, `noambrown_wrapper.py:1017-1033`): can't
  affect `test_exploit_diff` (which doesn't use the canonical
  renderer at all).
- Fix B (player-index inversion in
  `tests/test_v1_5_brown_apples_to_apples.py`): test-side only, no
  effect on `test_exploit_diff`.
- Fix C (Rust engine `enumerate_legal_actions` skip ALL_IN at cap):
  **this is the only PR 35 sub-fix that changes solver behavior**.

So the regression is squarely **PR 35 Fix C**, and the mechanism is
the Python-Rust asymmetry described under H1.

---

## Recommended v1.6.1 bundle composition

**Option 1 (preferred): drop PR 35 entirely and ship PR 33 + 34 + 40.**

- PR 34 fixes the A83 panic.
- PR 40 fixes the test-side encoding bugs (semantic action
  permutation + player-slot swap).
- PR 33 adds the Python delegate (independent feature, useful for
  v1.5.x callers).
- Acceptance test still FAILS on coverage (K72 53.3% / A83 66.7%)
  because PR 35 Fix A is not in the tree — but **the test was already
  failing in v1.5.0**; shipping without PR 35 just means the headline
  "Brown apples-to-apples = GREEN" stays UNCLAIMED.
- `test_exploit_diff.py` regression is AVOIDED.

The trade-off: v1.6.1 doesn't claim a green Brown acceptance, but it
also doesn't regress test_exploit_diff. The CHANGELOG should be honest
about this state: "PR 23 P0 panic fixed for asymmetric ranges; full
Brown apples-to-apples acceptance still failing on per-action parity
(under investigation as deeper algorithmic bug in `dcfr_vector.rs`)."

**Option 2: ship PR 33 + 34 + 35-Fix-A + 35-Fix-B + 40 (drop Fix C only).**

This is more surgical but requires splitting PR 35:

- PR 35 Fix A (test renderer): needed for K72/A83 coverage. Keep.
- PR 35 Fix B (per-action parity player-index inversion): needed for
  semantic correctness in the per-action loop. Keep.
- PR 35 Fix C (Rust engine ALL_IN-at-cap skip): currently breaks
  Python-Rust parity. **Drop**, OR update Python's
  `enumerate_legal_actions` to match.

If Fix C is dropped, the action-count parity check in the acceptance
test would need its own adjustment (Brown emits {c,f} at cap, Rust
would emit {c,f,A}) — but since the test now passes coverage and the
PER-ACTION parity check is what's failing, the action-count gate is
likely orthogonal to the 42pp gap.

The honest assessment is that **fixing Fix C correctly requires
updating Python too** (`action_abstraction.py:236-237`: add
`if not cap_reached` guard) AND verifying that
`test_exploit_diff.py` then passes with the engine fix in both
engines. This is a true bug in Python AND Rust that PR 35 only
half-fixed.

**Option 3 (NOT recommended): keep the full bundle but suppress
`test_exploit_diff`'s regression with a tolerance loosening.**

Rejected. The 0.417 delta is real algorithmic divergence, not
numeric noise; loosening the 1e-6 tolerance would defeat the test's
purpose (verifying Python-Rust algorithmic equivalence).

---

## PR 23 Rust vector-form CFR correctness assessment

**Honest verdict: PR 23's Rust vector-form CFR is NOT yet correct vs
Brown's reference.**

Two algorithmic bugs identified so far:

1. **The off-by-one** (`dcfr_vector.rs:363` / `:651`): the
   opponent-node branch sized buffers using the wrong player's
   `hand_count`. PR 34 fixes this correctly.
2. **The unknown deeper bug** (manifesting at 22-42pp per-action
   divergence on facing-bet high-stakes rows): NOT yet diagnosed.

The fact that PR 34 was needed at all is significant: it means PR 23's
`VectorDCFR::traverse` was demonstrably wrong on asymmetric ranges
before v1.5.0 shipped. The acceptance test (which would have caught
it) was not running in CI gating at the time; PR 28 added the test
but it was marked `parity_noambrown` opt-in.

The "audit APPROVED" verdict on PR 34 in earlier review was correct
structurally (it mirrors Brown's `trainer.cpp:170-173`) and is now
**also empirically validated** by this bisection (test-A panics
without it; test-B doesn't).

Whether the deeper bug (the 22-42pp divergence with all four PRs
applied) is in the regret/reach-prob updates, the DCFR
alpha/beta/gamma weighting, the chance-node accumulation, or
elsewhere in `dcfr_vector.rs` is **out of scope for this bisection**
and is the job of a follow-up algorithmic-triage agent.

The pattern (Rust over-folds and under-calls at deep-cap facing-bet
nodes) is consistent with several possible bugs:

- Incorrect regret accumulation on the fold action when the opponent
  is at cap (fold = give up pot equity, not "lose remaining stack").
- Mis-scaled iteration weight in DCFR's alpha-discount on
  positive regrets at cap nodes.
- Mis-attributed terminal utility on the "fold by opponent" branch
  (where the opponent's reach-prob for fold appears in the regret
  for the current player's call).

Recommended next step: spawn a focused algorithmic-triage agent on
`crates/cfr_core/src/dcfr_vector.rs` vs `cpp/src/trainer.cpp`,
specifically lines 138-209 of trainer.cpp (the recursive update
loop), using the K72 worst-cell from the staging doc as the
reproducer.

---

## Honest framing for the v1.6.1 release notes

If Option 1 is taken (drop PR 35), the release notes should say:

> v1.6.1 fixes a P0 index-out-of-bounds panic in the Rust vector-form
> CFR for asymmetric hand ranges (PR 34), adds a Python delegate that
> auto-routes to the Rust path for full-range subgames (PR 33), and
> corrects test-side encoding bugs in the Brown apples-to-apples
> acceptance test (PR 40). The acceptance test still does not pass
> on per-action parity — a deeper algorithmic divergence in the Rust
> vector-form CFR is under investigation (tracked in the v1.6.x
> roadmap).

If Option 2 is taken (drop only PR 35 Fix C), the release notes
should additionally call out:

> v1.6.1 also fixes the history canonicalization renderer for
> stack-ceiling all-in tokens (PR 35 Fix A) and corrects the
> player-index inversion in the per-action parity walk (PR 35 Fix B).
> The Rust engine's ACTION_ALL_IN-at-cap behavior was NOT changed in
> v1.6.1, pending a corresponding Python-side fix to keep the two
> implementations in parity (tracked as a v1.6.x ticket).

Either way, the headline must NOT claim "Brown apples-to-apples =
GREEN". That claim is currently false and would require fixing the
deeper algorithmic bug first.

---

## Time & resource accounting

- 3 worktree creations + cherry-picks: ~30 seconds.
- 3 venv setups + dep installs: ~3 minutes total.
- 3 maturin builds: ~12-13 seconds each (incremental on shared
  cargo registry; warm), ~40 seconds total.
- 3 `test_exploit_diff.py` runs: ~51-52 seconds each (sequential),
  ~155 seconds total.
- 3 acceptance test runs: 200s (test-A, faster because K72 fails
  fast on coverage and A83 panics quickly) + 523s (test-B) + 519s
  (test-C). The B and C tests ran in parallel under shared CPU
  contention, so wall time ~9 minutes for both.

Total wall time: ~22 minutes, well under the 60-minute budget.

---

## Cleanup

All three worktrees + their staging branches were created in
`/tmp/bisect_v1.6.1/` and have been (or will be, at end of this
agent's run) removed.

```
git worktree remove /tmp/bisect_v1.6.1/test-A
git worktree remove /tmp/bisect_v1.6.1/test-B
git worktree remove /tmp/bisect_v1.6.1/test-C
git branch -D bisect-A bisect-B bisect-C
```

No pushes, no tags, no merges. Source code in
`/Users/ashen/Desktop/poker_solver` was NOT modified.

---

## Summary table

| Question | Answer |
|----------|--------|
| Which PR caused `test_exploit_diff` regression? | **PR 35 Fix C** (Rust ALL_IN-at-cap skip without matching Python update) |
| Is PR 34's off-by-one fix correct? | **YES**, empirically validated (test-A A83 panics without it) |
| Is PR 35 entirely harmful? | **NO** — Fix A (renderer) and Fix B (player-index inversion in test) are load-bearing; Fix C is the problem |
| Is PR 33 implicated in any failure? | **NO**, the Python delegate doesn't touch the acceptance test path |
| Is PR 23 vector-form CFR correct? | **NO** — at least one additional algorithmic bug beyond the off-by-one; manifests as 22-42pp divergence on facing-bet high-stakes nodes even with all four PRs applied |
| Recommended v1.6.1 bundle? | **Option 1**: PR 33 + 34 + 40 (drop PR 35). **Option 2**: PR 33 + 34 + 35-without-Fix-C + 40 (split PR 35). Option 3 (full bundle as-is) is NOT recommended. |
| Should v1.6.1 claim Brown acceptance = GREEN? | **NO** in either option. The deeper algorithmic bug remains. |
