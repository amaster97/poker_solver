# R11 — Brown Convergence Hypothesis Investigation

**Date**: 2026-05-24
**Spot under test**: `dry_A83_rainbow` (the DR#8 AA-divergence canonical spot)
**Worktree**: `/private/tmp/bisect-c-bundle-75843` (v1.7.0 + 8-PR bundle = the
exact build that produced DR#8's findings).
**Verdict**: **NOT a real engine bug, NOT genuine Nash multiplicity, NOT
under-convergence. The "AA divergence" surfaced in DR#8 is a TEST-SIDE
range-assignment misalignment between the wrapper's input-side swap (PR
55-ext) and the test's own Rust-side range swap (Fix B / PR 40). The
two swaps assume OPPOSITE spot-range semantics; they fight each other,
so Brown trains on one range assignment and Rust trains on a different
one. Both solvers are converging correctly; they are just not solving
the same game.**

---

## Phase 1 — Iteration count match: **Y**

Both the bundle's test (`tests/test_v1_5_brown_apples_to_apples.py`) and
the wrapper invoke at `ITERATIONS = 2000`. Both engines run DCFR
(alpha=1.5, beta=0.0, gamma=2.0). Brown's binary defaults to `--algo
cfr+` per `cpp/src/main.cpp:25`, but the wrapper explicitly passes
`--algo dcfr` (`noambrown_wrapper.py:583-593`). Verified iter count
match.

## Phase 2 — Seed match: **N/A (no RNG)**

Brown's DCFR path (`cpp/src/trainer.cpp` whole file) uses **no RNG**.
The `--seed` flag is wired only into `MCCFRTrainer::FastRng`
(`mccfr.cpp:9`) which is used by the MCCFR algorithm, not DCFR. Both
the wrapper and the test invoke `--algo dcfr`, so the seed is never
read.

Our Rust `dcfr_vector.rs` also has **no RNG** (grep for `rand|Rng|seed`
returns zero hits in that file). The PyO3 entry
`solve_range_vs_range_rust` doesn't accept a seed parameter
(`crates/cfr_core/src/lib.rs:417-425` signature). Both solvers are
deterministic given iteration order. Seed differences cannot account
for the divergence.

## Phase 3 — Exploitability reporting

Brown's solver reports its own exploitability inline
(`main.cpp:437-458`). Trend at `dry_A83_rainbow`:

| Iters | Brown exploitability (chips) |
|---|---|
| 100 | 4.20 |
| 500 | 0.28 |
| 2000 | **0.0349** |

Brown is clearly converging — exploitability drops 2 orders of
magnitude between iter 500 and 2000.

Our Rust path's `solve_range_vs_range_rust` does NOT report
exploitability in its return dict
(`crates/cfr_core/src/lib.rs:417-503`, no `exploitability` key). I
attempted to recompute it via
`_rust.compute_exploitability(config_json, rust_strategy)` (the
PR 15 walker), but that walker enumerates the **full deck** of
C(50,2)×C(50,2) hand pairs (`solver.py` range-vs-range mode); for the
~80% of hand pairs that are NOT in `spot.ranges`, the walker uses
uniform-default play (per `dcfr_vector.rs:222-228`). So the reported
14.3-14.4 chip exploitability is dominated by uniform-default play
on untrained hands and is NOT a valid measure of how well the
strategy converged on the trained range.

**Conclusion of Phase 3**: Brown reports its own exploitability and is
clearly converged. Our Rust path doesn't have a clean equivalent for
range-vs-range mode — we have to fall back to per-row strategy
comparison (which is what DR#8 actually measures anyway).

## Phase 4 — Nash multiplicity at root: theoretically possible but NOT what's happening here

For AA on `Ah 8c 3d Tc 6s`, AA has top set (Ace blocked by board's
`Ah` means only 3 AA combos exist, all containing the case Aces). Top
set on this board dominates virtually every hand in the opponent's
range. The Nash strategy space here is not a continuum:

  * **Pure check** (Brown's solution) is a valid Nash: AA has no fold
    equity vs better hands (there are none), bluff-protection isn't
    needed against a range that's mostly value/pairs, and a calling
    range exists.
  * A **mixed bet/check** could be Nash IFF villain's calling range
    against the bet keeps AA indifferent — i.e. villain calls enough
    worse hands to make betting equally profitable to checking. On
    this board with these ranges, that condition is not met
    automatically; we'd need to verify by computing the equity of
    AA's bet line vs villain's response.

But **regardless of multiplicity**: the per-row strategy comparison
under the NO-swap convention shows Brown and Rust agree to 6 decimals
(see Phase 5). Both engines arrive at the SAME equilibrium when the
inputs match. So there is no observed multiplicity at this spot.

## Phase 5 — Convergence trend (Rust)

### Under the DR#8 SWAP convention (`p0_holes=ranges[1], p1_holes=ranges[0]`)

| Iters | AdAc | AsAc | AsAd |
|-------|------|------|------|
| 100   | [0.24, 0.46, 0.29, 0.01] | [0.24, 0.45, 0.29, 0.01] | [0.24, 0.47, 0.28, 0.01] |
| 500   | [0.18, 0.52, 0.30, 0.00] | [0.11, 0.53, 0.36, 0.00] | [0.19, 0.56, 0.25, 0.00] |
| 2000  | [0.25, 0.45, 0.30, 0.00] | [0.11, 0.46, 0.42, 0.00] | [0.26, 0.64, 0.10, 0.00] |

### Under the NO-swap convention (`p0_holes=ranges[0], p1_holes=ranges[1]`)

| Iters | AdAc | AsAc | AsAd |
|-------|------|------|------|
| 100   | [0.986, 0.012, 0.002, 0.0003] | [0.982, 0.014, 0.003, 0.0004] | [0.987, 0.011, 0.002, 0.0003] |
| 500   | [0.9999, 0.0001, 0.0, 0.0] | [0.9999, 0.0001, 0.0, 0.0] | [0.9999, 0.0001, 0.0, 0.0] |
| 2000  | [0.99999, 1.9e-6, 3.9e-7, 5.4e-8] | [0.99999, 1.5e-6, 3.0e-7, 4.0e-8] | [0.99999, 1.4e-6, 2.9e-7, 4.1e-8] |

Brown trend at same spot (Brown's `players[1]` after wrapper swap = our P1 = first-to-act):

| Iters | P1.AdAc | P1.AsAc | P1.AsAd | Brown expl |
|-------|---|---|---|---|
| 100   | [0.985, 0.013, 0.002, 0.0003] | [0.985, 0.013, 0.002, 0.0003] | [0.985, 0.012, 0.002, 0.0003] | 4.20 |
| 500   | [0.9999, 0.0001, 0.0, 0.0] | [0.9999, 0.0001, 0.0, 0.0] | [0.9999, 0.0001, 0.0, 0.0] | 0.28 |
| 2000  | [1.00, 0.00, 0.00, 0.00] | [1.00, 0.00, 0.00, 0.00] | [1.00, 0.00, 0.00, 0.00] | **0.035** |

**Critical observation #1**: Brown's exploitability drops monotonically
(4.2 → 0.28 → 0.035) and Brown's AA tightens to pure-check by iter 500.
Brown is converging.

**Critical observation #2**: Under the SWAP convention, Rust's AA
oscillates around [0.20, 0.50, 0.30, 0.0] across all iter counts and
does NOT trend toward Brown's pure-check value. Strategies vary slightly
between iter counts but stay in the same shape.

**Critical observation #3 (the smoking gun)**: Under the NO-SWAP
convention, Rust's AA tracks Brown almost identically at every iter
level:
  * At 100 iters: Rust [0.986, 0.012, 0.002, 0.0003] vs Brown
    [0.985, 0.013, 0.002, 0.0003] — agreement to 3 decimals.
  * At 500 iters: Rust [0.9999, 0.0001, 0.0, 0.0] vs Brown
    [0.9999, 0.0001, 0.0, 0.0] — agreement to 4 decimals (essentially
    perfect).
  * At 2000 iters: Rust [0.99999, 1.9e-6, ...] vs Brown
    [1.00, 0.0, ...] — agreement to ~6 decimals.

The engine produces **Brown-correct output** when the input ranges are
assigned to slots consistent with what the wrapper put into Brown.

## Root cause — TEST SIDE bug (not engine)

Two PRs each made a "swap" decision that internally is self-consistent
but they assume OPPOSITE semantics for `spot.ranges`:

  * **Wrapper `noambrown_wrapper.py`** (PR 55 + PR 55-ext) treats
    `spot.ranges[0]` as **our P0 = second-to-act on river** (per its
    docstring at `parity/noambrown_wrapper.py:638-643` citing
    `hunl.py:425-429`). It swaps inside `write_brown_config` so
    Brown's first-actor (Brown's native `players[0]`) is given
    `spot.ranges[1]` (= our P1 = first-actor range).
  * **Bundle's test** (`Fix B` / PR 40, comment at
    `tests/test_v1_5_brown_apples_to_apples.py:578-584`) treats
    `spot.ranges[0]` as **the opener range** ("Brown's P0 = opener;
    Rust's P1 = opener"). It swaps so `p1_holes = ranges[0]` —
    putting `ranges[0]` into Rust's first-actor slot.

So Brown's first-actor trains on `ranges[1]` (per wrapper), but
Rust's first-actor trains on `ranges[0]` (per test's swap). **The
two engines are solving different games**, hence Rust's "non-Nash"
strategy is actually a Nash strategy of a different game.

The audit `docs/poker_spots_audit_CORRECTED_2026-05-23.md` describes
`dry_K72`'s `players[0]` as "Villain (P0) … bet 1500 into 1000 pot"
— i.e. **`players[0]` is the bettor / first-to-act**, contradicting
the wrapper module's docstring. So the test's view of "ranges[0] is
the opener" matches the spot author's intent; the wrapper's docstring
is the documentation that's wrong, but its CODE happens to encode the
wrapper view consistently.

Either:

  * Patch the wrapper to align with `spot.ranges[0]=first-actor` (the
    fixture authoring convention): swap NEITHER input nor output, since
    Brown's native player_0 already matches `spot.ranges[0]` and our
    P1 also matches `spot.ranges[0]`. (But then the test must use
    `p0_holes=ranges[1], p1_holes=ranges[0]`, treating ranges[0] as
    Rust's first-actor = our P1.)
  * Or patch the test to align with the wrapper's view: drop the
    `Fix B` swap and use `p0_holes=ranges[0], p1_holes=ranges[1]`.
    With the no-swap configuration, Rust matches Brown to 6 decimals
    on AA root (verified above).

Either patch eliminates the "AA at root" divergence claim.

## Verdict

**CONVERGENCE-ISSUE: NO.** Under the SWAP convention, Rust at 100,
500, and 2000 iters all produce the same shape of AA strategy
(~[0.20, 0.50, 0.30, 0]) — it is NOT trending toward Brown's
1.0-check value with more iterations. So this isn't a "needs more
iterations" issue.

**GENUINE-NASH-MULTIPLICITY: NO.** Under the NO-SWAP convention, Brown
and Rust both arrive at AA → 100% check (agreement to 4-6 decimals
across all iter levels). The two engines converge to the SAME
equilibrium when given the same inputs, so there's no observed
multiplicity at this spot.

**REAL-ENGINE-BUG: NO.** When fed the same range assignment as Brown
(no-swap convention), Rust converges to AA → 100% check matching
Brown's strategy to ~6 decimals. The engine is fine; it's the test
harness that's mis-aligned in the bundle.

**TEST-SIDE / WRAPPER-SIDE MISALIGNMENT: YES.** Two layers of
"swap" (wrapper PR 55-ext input swap + test PR 40 Rust-side swap)
each make a self-consistent decision based on opposite spot-range
semantics; they cancel out incorrectly. Brown trains its first-actor
on `spot.ranges[1]` while Rust trains its first-actor on
`spot.ranges[0]`. The two solvers are solving different games,
hence different equilibria.

## Recommendation

Before treating the DR#8 "AA at root" finding as an engine signal,
**re-run the test with the test's `Fix B` swap reverted** (or with
the wrapper's swap reverted, whichever is consistent with how the
fixture was authored). Per the `dry_K72` audit, the fixture's
`players[0]` is the first-to-act, so the wrapper docstring is wrong
and the wrapper's swap is the one to revert.

This finding is **Type B** per the rectification framework (wrapper
+ test code, not engine). The headline "20 shallow-strict violations
on AA/TT/88 root histories" in DR#8 is an artifact of the broken
alignment, not evidence of an engine equilibrium bug.

## Files referenced (absolute paths)

  * `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py` (main, no swap, lines 457-458)
  * `/private/tmp/bisect-c-bundle-75843/tests/test_v1_5_brown_apples_to_apples.py` (bundle, with swap, lines 583-584)
  * `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` (PR 55-ext write_brown_config L611-680, _parse_brown_dump L885-914)
  * `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/main.cpp` (Brown CLI: --algo / --iters / --seed, lines 25, 31, 36, 583-635)
  * `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp` (Brown DCFR — no RNG)
  * `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs` (Rust DCFR — no RNG)
  * `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs:417-503` (`solve_range_vs_range_rust`, no seed param)
  * `/Users/ashen/Desktop/poker_solver/docs/poker_spots_audit_CORRECTED_2026-05-23.md` (P0=villain=bettor convention)
  * `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_8.md` (the DR#8 finding)
  * `/Users/ashen/Desktop/poker_solver/docs/minimal_nash_regression_test.md` (notes the AA-at-root indifference manifold; tolerates a_1≈0.075 there)
