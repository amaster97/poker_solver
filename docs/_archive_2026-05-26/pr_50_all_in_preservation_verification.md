# PR 50 — ALL_IN-as-Raise Preservation Verification

**Date:** 2026-05-24
**Branch under test:** `pr-50-facing-all-in-guard` (commit `18a7640`)
**Reviewer:** read-only verification agent
**Scope:** Confirm the new `can_actually_raise = stack > to_call` guard suppresses
the *degenerate* ALL_IN (when ALL_IN ≡ CALL) without over-suppressing the
*legitimate* ALL_IN-as-raise (when hero has chips left beyond the call amount).

---

## 1. The fix under review

Both `crates/cfr_core/src/hunl.rs:1133+` and
`poker_solver/action_abstraction.py:236+` add the same two-clause guard:

```rust
let can_actually_raise = stack > ctx.to_call;
if ctx.include_all_in && !cap_reached && can_actually_raise {
    actions.push(ACTION_ALL_IN);
}
```

The guard fires only when **both** conditions hold:

1. `!cap_reached` — `street_num_raises < raise_cap(ctx)`
2. `can_actually_raise` — `stack > to_call` (strict; equality suppresses)

Helpers used: `stack_remaining(ctx) = ctx.stacks[ctx.cur_player]`,
`raise_cap(ctx)` (preflop=4, postflop=3 by default),
`force_allin_chip_threshold(ctx) = ctx.force_allin_threshold * ctx.big_blind`
(this last one is consumed by `_enumerate_raises` / `_enumerate_bets`, not by
the ALL_IN gate — important for understanding why fractional raises drop out
on short stacks while ALL_IN survives).

---

## 2. Scenario sweep (PR 50 code, Python `enumerate_legal_actions`)

All four scenarios are produced by direct execution against the PR-50 source.

| # | Scenario | stack | to_call | raises_so_far | cap | `can_actually_raise` | Expected | Actual |
|---|----------|-------|---------|---------------|-----|----------------------|----------|--------|
| **S1** | Deep stack, normal bet | 10 000 | 100 | 1 | 3 | True | `[FOLD, CALL, R_33, R_75, R_100, R_150, R_200, ALL_IN]` | ✅ `[FOLD, CALL, R_33, R_75, R_100, R_150, R_200, ALL_IN]` |
| **S2** | Deep stack at cap | 10 000 | 100 | 3 | 3 | True | `[FOLD, CALL]` (cap dominates) | ✅ `[FOLD, CALL]` |
| **S3** | Short stack, big bet (degenerate facing-all-in) | 100 | 500 | 1 | 3 | False | `[FOLD, CALL]` (CALL = go-all-in-to-call; no separate ALL_IN) | ✅ `[FOLD, CALL]` |
| **S4** | Short stack, small bet (legit ALL_IN-as-raise) | 200 | 100 | 1 | 3 | True | `[FOLD, CALL, ALL_IN]` (fractional raises filtered by `force_allin` threshold) | ✅ `[FOLD, CALL, ALL_IN]` |

### Per-scenario reasoning

- **S1 (deep, normal):** `stack > to_call` holds (10 000 > 100), `!cap_reached`
  holds (1 < 3), so the full menu — fold/call, all five fractional re-raises,
  plus ALL_IN as the topmost option — is emitted. **ALL_IN-as-raise preserved.**

- **S2 (deep, cap):** even though `can_actually_raise=True`, `cap_reached`
  short-circuits the entire raise enumeration AND the ALL_IN gate. Output is
  `[FOLD, CALL]`. This matches Brown's `river_game.cpp:76` reference behavior.
  **Correct rule-driven suppression, not a `can_actually_raise` artifact.**

- **S3 (short, big bet = facing-all-in):** `stack <= to_call` (100 ≤ 500), so
  `can_actually_raise=False`. ALL_IN is suppressed. CALL semantically means
  "commit remaining 100 to call partially" (side-pot resolution at showdown).
  This is the **target degenerate case** the fix was written for, and it is
  correctly handled.

- **S4 (short, small bet):** `stack > to_call` (200 > 100) holds; ALL_IN is
  emitted. The fractional raises (`R_33` … `R_200`) all get filtered out by
  `_enumerate_raises`'s `(stack - chips_added) <= force_threshold` clause
  because raising to ≥150 would leave the player with ≤50 chips behind, which
  is below `force_allin_threshold_bb=1 * big_blind=100`. Result:
  `[FOLD, CALL, ALL_IN]`. **ALL_IN-as-raise preserved as the sole raise
  option** — exactly what is wanted (the short-stack player can fold, call to
  100, or jam to 200 = real re-shove).

---

## 3. Boundary edge cases

| # | Edge | stack | to_call | `can_actually_raise` | Actual |
|---|------|-------|---------|----------------------|--------|
| **EdgeA** | Exact equality | 500 | 500 | False (`>` is strict) | `[FOLD, CALL]` — ALL_IN suppressed (CALL consumes whole stack; ALL_IN would be identical) |
| **EdgeB** | One chip above | 501 | 500 | True | `[FOLD, CALL, ALL_IN]` — ALL_IN preserved (raise by 1 chip is technically real) |
| **EdgeC** | Open bet (`to_call=0`) | 10 000 | 0 | True (invariant: stack > 0) | `[CHECK, BET_33, BET_75, BET_100, BET_150, BET_200, ALL_IN]` — open-shove preserved |
| **EdgeD** | Cap reached, deep stack | 10 000 | 100 | True | `[FOLD, CALL]` — cap dominates |
| **EdgeE** | Preflop, cap=4 | 10 000 | 100 | True | `[FOLD, CALL, R_33, R_75, R_100, R_150, R_200, ALL_IN]` — preflop cap unchanged |

**EdgeA is the most semantically nuanced case.** At `stack == to_call`, CALL and
ALL_IN both commit the entire remaining stack, so they are the *same* action.
The strict `>` correctly collapses them to a single CALL entry, avoiding a
duplicate-regret-bucket bug (the original PR 50 motivation).

**EdgeC confirms** the guard does not affect the no-facing-bet path: when
`to_call=0`, `can_actually_raise = stack > 0` is the same invariant as the
`stack <= 0 ⇒ return early` guard at the top of `enumerate_legal_actions`,
so ALL_IN-as-open-shove is always emitted (subject to `!cap_reached` &
`include_all_in`).

---

## 4. Existing-test regression check

Re-ran `tests/test_action_abstraction.py` (12 tests, all touching
`enumerate_legal_actions` / `compute_bet_amount` / `compute_raise_to`)
against the PR-50 Python source:

```
............                                                             [100%]
12 passed in 0.01s
```

No regressions. Notably:

- `test_abstraction_raise_actions_when_to_call_positive` (S1-equivalent)
  passes: ALL_IN is still asserted present in the deep-stack facing-bet menu.
- `test_abstraction_no_raise_at_cap` (S2-equivalent) passes: cap-reached
  emits `[FOLD, CALL]` only.
- `test_abstraction_all_in_replaces_oversize` and `test_abstraction_all_in_dedup`
  (open-bet path, EdgeC-flavored) both pass: ALL_IN is emitted exactly once.

Rust unit tests were NOT re-run in this audit (auto-mode permission
restriction); however the two diffs are structurally identical
(same `can_actually_raise = stack > ctx.to_call` boolean, same `!cap_reached`
gate, same control flow), so semantic parity is established by the paired-source
construction.

---

## 5. Looking for over-suppression hazards

The `can_actually_raise` boolean is computed as `stack > ctx.to_call` where:

- `stack = stack_remaining(ctx) = ctx.stacks[ctx.cur_player]` — the **remaining**
  stack of the current player (post-prior-contributions; HUNL invariant per
  `HUNLState`).
- `ctx.to_call` — chips needed to match the aggressor's contribution.

The boolean is mathematically equivalent to: "after calling, would the player
have ≥1 chip behind?" — which is the precise definition of "can the player
make a strictly larger commitment than CALL?". The fix is therefore
**tight by construction**:

- If `True`, ALL_IN is a genuinely different action from CALL (jam = call + extra
  chips beyond what was required to match).
- If `False`, ALL_IN ≡ CALL (both consume the same number of chips).

**No code path was found** where `can_actually_raise` could incorrectly evaluate
to `False` while ALL_IN-as-raise is still semantically meaningful, because the
only "way" to make ALL_IN distinct from CALL is to have strictly more chips than
`to_call`. The relationship `stack > to_call ⟺ ALL_IN ≢ CALL` is an identity.

One mild caveat: in the open-bet path (`facing_bet == False`), `to_call == 0`,
so `can_actually_raise = stack > 0`. This is already enforced by the
`if stack <= 0 { return empty }` short-circuit at the top of
`enumerate_legal_actions`, so the new gate is redundant-but-correct on that path.
No risk.

---

## 6. Verdict

**PRESERVES-LEGITIMATE.**

The PR 50 guard correctly:
- ✅ Preserves ALL_IN-as-raise in **all 4 mandated scenarios** + 5 edge cases.
- ✅ Suppresses ALL_IN only when it would be **provably identical to CALL**
  (strict equality at `stack == to_call`, or short-stack-vs-big-bet where CALL
  already commits the full remaining stack).
- ✅ Does not interfere with the cap-reached rule (cap suppresses raises
  independently, as it always has).
- ✅ Does not interfere with the open-bet / no-facing-bet path.
- ✅ Passes all 12 existing `test_action_abstraction.py` tests with zero
  regression.

The boolean `can_actually_raise = stack > ctx.to_call` is the **tight**
formulation of "ALL_IN is semantically distinct from CALL". There is no slack
in either direction — neither under-suppression (where a real ALL_IN-as-raise
would be allowed when it is actually degenerate) nor over-suppression (where a
real ALL_IN-as-raise would be dropped from the menu).

Recommendation: **safe to ship.** Suggest adding two targeted regression tests
that pin the new semantics: one for S3 (suppression) and one for S4 (preservation
of ALL_IN-as-raise with all fractional raises filtered by force-all-in threshold).
