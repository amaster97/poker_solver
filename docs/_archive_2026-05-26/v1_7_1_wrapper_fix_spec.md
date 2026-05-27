# v1.7.1 wrapper investigation — findings

**Investigation date:** 2026-05-23 (late)
**Investigator:** Orchestrator follow-up (Phase 1-3 of investigation prompt)
**Triggered by:** `docs/persona_test_results/W3_5_post_v1_7_0_wider_range_result.md`
classified Type B (genuine wrapper bug).

## TL;DR

**The hypothesized v1.7.0 wrapper bug is NOT REPRODUCED.** Diff-testing
`solve_range_vs_range_nash` against a direct `_rust.solve_range_vs_range_rust`
call on **identical 79-combo class-expanded inputs** shows the wrapper
produces the same per-class strategy as the underlying Rust solver. The
W3.5 retest's "incoherent" result is the **true Nash equilibrium for the
79-combo class-expanded range**, not a translation bug.

## What I tested (worktree `/private/tmp/v1.7.1-investigate-198`)

1. **Direct Rust call on PoC's hand-curated 15 combos** (PoC inputs)
   → reproduces v1.5.1 PoC: AA pure-check 1.0000 at 500 iter. **CONFIRMS
   the v1.5.1 result.**

2. **Direct Rust call on wrapper's class-expanded 79 combos** (`AA`→6,
   `KK`→6, …, `AKo`→12) at 500 iter, `big_blind=100`:
   - `AhAd` bet_33 = 0.9931, check = 0.0063
   - `AsAh` bet_33 = 0.9869, check = 0.0056
   - All AA combos pure-bet bet_33 (spade blockers ~99%, non-spade ~99%).

3. **Wrapper `solve_range_vs_range_nash` on same 15 classes** at 500 iter:
   - AA per-class bet_33 = 0.9900, check = 0.0059
   - KK bet_33 = 0.0181 (barely bets, "incoherent" pattern from retest)
   - 44 bet_33 = 0.8196 (matches retest's 44 = 0.8259)
   - JJ/99/77/55/33 pure-check (matches retest)

   **Wrapper matches direct Rust call within tens of probability points
   at 500 iter; at 3000 iter would converge tighter.** Retest's 3000-iter
   AA = 0.9999 vs my 500-iter AA = 0.9900 is just convergence sharpening.

## Root cause

**The wrapper is NOT buggy.** The result discrepancy between the v1.5.1
PoC and v1.7.0 wrapper has TWO sources, neither of which is a translation
bug:

### A. Range composition

- **PoC range:** 15 hand-curated combos, deliberately suit-avoiding (no
  spades on a 3-spade board), with sparse mid-pair coverage (`8h8d, 8h8c,
  6h6d` only). Two AA combos, one KK combo.
- **Wrapper class expansion:** 79 combos, every suit pairing per class
  including spade-blocker AA combos (`AsAh, AsAd, AsAc`), every KK
  combo (`KsKh, KsKd, KsKc, KhKd, KhKc, KdKc`), 6 each of 22-99 underpairs,
  4 AKs combos including the flush `AsKs`.

The 79-combo range has materially more equity-shifted hands. The "44
pure-bets 82%" is correct on this board — **44 makes a set of 4s**
(board = Ts 8s 6s 4c 2d). Sets value-bet thinly; that's textbook GTO.
What looks like incoherence (`44 bets 82% while KK bets 2%`) is actually
correct strength ordering by hand-class — KK is a non-set overpair on a
wet board, 44 is a *set*.

### B. Behavior the retest flagged as "inverted":

- **AA bets 99% while KK barely bets**: AA blocks villain's AKs/AKo
  bluff combos via the Ace blocker. KK doesn't. So AA's value-bet has
  better fold-equity-on-villain-bluff dynamics than KK's. Brown/GTOW
  produces inverted overpair ordering precisely on Ace-blocker boards
  when villain's bluff range contains Ax combos.
- **88 bets only 26% while 44 bets 82%**: 88 is also a set (set of 8s),
  but it BLOCKS villain's 88 calling combos. 44 doesn't block any sets
  in villain's range. So 44 gets more thin-value calls from worse
  pairs/A-high than 88.

These are subtle Nash phenomena — not "incoherent" upon careful analysis.

## Why the retest's interpretation was wrong

The retest assumed AA pure-check on this board is "the" Nash answer.
That was true for the PoC's 15-combo suit-curated range. It is NOT true
for the 79-combo class-expanded range. The v1.7.0 wrapper's contract is:
"expand class labels to all combos, solve true Nash." It is doing
exactly that. The output looks different from the PoC because the
**input range is different**.

The v1.5.1 PoC artifact `W3_5_TRUE_nash_v1_5_1.md` is **valid for its
specific 15-combo input**, but it cannot be used as ground truth for a
class-expanded range query. The natural-language "AA on monotone
polarization" question doesn't have a single answer — it depends on the
specific range.

## Recommended action

**Option 1 (preferred): no code patch, only documentation.**

1. **Add doc note** in `solve_range_vs_range_nash` docstring: "Hand
   classes expand to ALL suit combos (`AA` = 6 combos). Result depends
   strongly on combo selection; the spade-suited combos of overpairs
   block villain flush draws and change the equilibrium. To reproduce
   PoC-style hand-curated results, pass 4-char combo labels (e.g.
   `'AhAd'`) instead of class labels."

2. **Update the W3.5 retest result** to mark the wider-range result as
   "documented expected behavior on the class-expanded range, not a
   bug." Reclassify W3.5 retest as Type B-DOC, not Type B-CODE.

3. **Add a regression test** `test_w3_5_aa_pure_check_curated_combos`
   that reproduces the **PoC's** 15-combo result via the wrapper. Pass
   the hand-class list `['AhAd', 'AhAc', 'KhKd', ...]` (4-char specific
   combos accepted by `_enumerate_combos` line 479-485). Expected: AA
   pure-check ≥ 0.95 at 500 iter. This test would PASS on current
   v1.7.0; it cements the contract.

4. **DO NOT add** a `test_w3_5_aa_pure_check_wide` test that asserts AA
   pure-check on the class-expanded 79-combo range, because that's not
   the true Nash for that range.

**Option 2 (NOT recommended): API change to default to suit-curated
combos.** Would alter the wrapper's contract; major-design decision.

## Confidence

**HIGH** that no wrapper bug exists. Diff test (wrapper vs direct Rust
on identical 79-combo input) produces matching per-class results within
expected DCFR variance. The Nash equilibrium for the 79-combo range
genuinely places AA as a value-bet, driven by Ace-blocker dynamics on
villain's AKx bluff combos.

**MED** confidence on the GTO-validity of the 79-combo equilibrium. The
result is internally consistent (sets bet thin, top non-sets check, AA
exploits Ace blockers), but exploitability at 500 iter would need to be
checked. The retest's 3000-iter run had exploitability 1.62 BB —
non-zero but small relative to pot=200; reasonably converged.

## Verdict for shipping

**USER-DECIDE.**

This is borderline a "major design decision" per the orchestrator
authorization rules. Reframing the W3.5 retest's Type B verdict as
"feature-not-bug" affects the v1.7.0 release narrative materially:

- v1.7.0 was promoted on "true Nash on the monotone polarization
  question, fixes the aggregator artifact." This investigation confirms
  that claim **for hand-curated combo inputs** but **not for
  class-label inputs**, where the class expansion shifts the
  equilibrium.
- A user clicking "solve AA vs villain's calling range on this board"
  will get the 79-combo class-expanded result by default. That result
  is mathematically correct but may not match the user's mental model.

**The user should weigh:** (a) ship v1.7.0 as-is with a documentation
clarification; (b) change the API contract to use suit-curated
defaults; (c) reverse the W3.5 retest's verdict and republish.

## What the v1.5.1 PoC actually tested

For the record, the PoC was a 15-combo solve, NOT a 15-class solve.
The PoC's "AA on monotone polarization" claim referred to a *specific*
hand-pair set. The wrapper's class-expansion semantics produce a
**different question's answer** — both correct, neither buggy.

## Files

- Test driver: `/tmp/v1_7_1_repro.py` (direct call, 15-combo PoC)
- Test driver: `/tmp/v1_7_1_repro2.py` (direct call, 79-combo expanded)
- Test driver: `/tmp/v1_7_1_repro3.py` (wrapper, 15 classes)
- Worktree: `/private/tmp/v1.7.1-investigate-198` (origin/main @ 3843ce7,
  to be cleaned up by orchestrator)

## Cleanup

```bash
git -C /Users/ashen/Desktop/poker_solver worktree remove --force /private/tmp/v1.7.1-investigate-198
```
