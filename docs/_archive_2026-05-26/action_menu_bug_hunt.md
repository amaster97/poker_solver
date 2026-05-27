# Action-Menu Bug Hunt — Beyond the Phantom ALL_IN

**Date:** 2026-05-24
**Scope:** Comb every action-emission site in `enumerate_legal_actions`,
`enumerate_bets`, `enumerate_raises` (Rust + Python) and compare against
Brown's `legal_actions` (`references/code/noambrown_poker_solver/cpp/src/river_game.cpp:31-107`).
The known phantom-ALL_IN bug at facing-all-in nodes is documented in
`docs/action_menu_topology_audit.md` Diff #3; this doc hunts for
**additional** bugs.

**Read-only.** No code modified.

---

## 1. Side-by-side: every action-emission case

### Case A. `to_call > 0` → push FOLD + CALL

**Brown** (`river_game.cpp:74-75`):
```cpp
actions.push_back({'c', to_call});
actions.push_back({'f', 0});
```

**Rust** (`hunl.rs:1115-1117`):
```rust
if facing_bet {
    actions.push(ACTION_FOLD);
    actions.push(ACTION_CALL);
}
```

**Python** (`action_abstraction.py:221-223`):
```python
if facing_bet:
    actions.append(ACTION_FOLD)
    actions.append(ACTION_CALL)
```

**Guards present:** none on the CALL (Rust/Python). Brown also has no
explicit guard, but Brown can never reach a state with
`to_call > remaining` because its action-emission upstream never permits
an over-shove (Brown's bet/raise emission gates on `remaining > to_call`).

**Guards missing in our tier:** The Rust/Python solver DOES allow states
where `stack <= to_call` (the phantom-ALL_IN case from the topology
audit). When `stack <= to_call`, CALL collapses to a sub-call (clamp at
`hunl.rs:694`) — game-theoretically fine — but CALL is emitted
unconditionally whether or not the player has chips behind, which
matches Brown's intent (the cur player must respond to a bet).

**Bug found:** none, but **see Bug #2** for what the related
`stack == 0` case means.

---

### Case B. `to_call == 0` → push CHECK

**Brown** (`river_game.cpp:50`):
```cpp
actions.push_back({'c', 0});  // ('c', 0) means CHECK in Brown
```

**Rust** (`hunl.rs:1118-1120`):
```rust
} else {
    actions.push(ACTION_CHECK);
}
```

**Python** (`action_abstraction.py:224-225`):
```python
else:
    actions.append(ACTION_CHECK)
```

**Guards present:** none on CHECK. Brown also has none.

**Match.** CHECK is correctly emitted only when `to_call == 0`.

---

### Case C. CALL when `stack == 0`

Brown never reaches this; the unreachable invariant is enforced in our
Python tier (`action_abstraction.py:214-217`):

```python
if stack <= 0:
    # Unreachable per HUNL invariant: stack-0 player has all_in[p]==True
    # so is never current player. Fail loudly per PR 3 audit (Should-fix).
    raise AssertionError("unreachable; stack<=0 implies all_in[p]==True")
```

In Rust (`hunl.rs:1109-1111`):

```rust
if stack <= 0 {
    return actions;
}
```

**Note:** Rust returns an empty `Vec` instead of raising. This is a
soft-fail. Upstream (`legal_actions`, `apply_player`) treats the empty
vector as "no legal actions" and the solver never reaches a node where
`stack == 0` for the current player (because `all_in[player] == true`
is set in `apply_player` whenever `stacks[player]` hits 0 — lines 697,
706, 718, 732). The next-to-act sentinel at line 769-779 then closes
the street with a refund. So the empty return is dead in practice.

**Guards missing:** none, but **inconsistency** — Python panics, Rust
silently returns empty. Not strictly a bug (the dead path is dead) but
the divergence is a smell.

---

### Case D. Opening bets (when `to_call == 0`)

**Brown** (`river_game.cpp:53-70`):
```cpp
for (double size : bet_sizes) {
    int bet_amount = static_cast<int>(std::round(pot * size));
    if (bet_amount <= 0) {
        continue;
    }
    bet_amount = std::min(bet_amount, remaining);   // CLAMP
    if (bet_amount > 0) {
        amounts.push_back(bet_amount);
    }
}
if (include_all_in && remaining > 0) {              // STACK > 0 guard
    amounts.push_back(remaining);
}
std::sort(...);
amounts.erase(std::unique(...), amounts.end());     // DEDUPE incl. ALL_IN
```

**Rust** (`hunl.rs:1062-1079`, `enumerate_bets`):
```rust
for (action_id, &fraction) in BET_ACTION_IDS.iter().zip(ctx.bet_size_fractions.iter()) {
    let raw_amount = bet_amount_for_fraction(ctx, fraction);
    if raw_amount >= stack || (stack - raw_amount) <= force_threshold {
        continue;                                   // SKIP (no clamp)
    }
    if seen_amounts.contains(&raw_amount) { continue; }
    seen_amounts.push(raw_amount);
    actions.push(*action_id);
}
```

**Python** (`action_abstraction.py:173-186`): identical logic.

**Guards present (Rust/Python):**
- `raw_amount >= stack` → skip (no clamp; relies on separate ALL_IN
  action to cover the would-be-clamped bet)
- `(stack - raw_amount) <= force_threshold` → skip near-shoves
- Dedupe on raw amount

**Guards missing vs Brown:**
- **Brown clamps; we skip.** When `raw_amount >= stack`, Brown emits a
  CLAMPED bet equal to `remaining` (which then dedupes against the
  ALL_IN amount). We skip and rely on the separate ALL_IN action being
  pushed. **Topology audit Diff S3** — already documented.
- **No `stack > 0` guard on the bet-iteration loop.** If `stack == 0`,
  every iteration trivially hits `raw_amount >= stack` and is skipped,
  so this is moot in practice.

**Bug found:** none new (Diff S3 already tracked).

---

### Case E. Raises (when `to_call > 0`)

**Brown** (`river_game.cpp:80-105`):
```cpp
if (state.raises >= max_raises) {
    return actions;                                 // CAP-REACHED short-circuit
}
int pot_after_call = pot + to_call;
for (double size : bet_sizes) {
    int raise_amount = static_cast<int>(std::round(pot_after_call * size));
    if (raise_amount <= 0) { continue; }
    int total_add = to_call + raise_amount;
    if (total_add > remaining) {
        total_add = remaining;                      // CLAMP to stack
        raise_amount = total_add - to_call;
    }
    if (raise_amount > 0 && total_add > to_call) {
        amounts.push_back(raise_amount);
    }
}
if (include_all_in && remaining > to_call) {        // STACK > TO_CALL guard
    amounts.push_back(remaining - to_call);
}
std::sort(...);
amounts.erase(std::unique(...), amounts.end());     // DEDUPE
```

**Rust** (`hunl.rs:1081-1101`, `enumerate_raises`):
```rust
for (action_id, &fraction) in RAISE_ACTION_IDS.iter().zip(ctx.bet_size_fractions.iter()) {
    let raise_to = raise_to_for_fraction(ctx, fraction);
    let chips_added = raise_to - cur_contrib;
    if raise_to >= max_raise_to || (stack - chips_added) <= force_threshold {
        continue;                                   // SKIP (no clamp)
    }
    if seen_raise_tos.contains(&raise_to) { continue; }
    seen_raise_tos.push(raise_to);
    actions.push(*action_id);
}
```

(Cap-reached short-circuit lives in `enumerate_legal_actions`:
`hunl.rs:1122-1131` — only enumerates raises/bets if `!cap_reached`.)

**Python** (`action_abstraction.py:189-205`): identical to Rust.

**Guards present (Rust/Python):**
- Cap-reached short-circuit (skips raise enumeration entirely)
- `raise_to >= max_raise_to` → skip
- Force-allin-threshold collapse
- Dedupe on `raise_to`
- Min-raise floor in `raise_to_for_fraction` (`hunl.rs:1027`): the raw
  `raise_to` is `max(raise_to, aggressor_contrib + min_raise_increment)`
  where `min_raise_increment = max(to_call, big_blind)` — this is a
  legitimate min-raise rule that Brown does NOT enforce.

**Guards missing vs Brown:**
- **Brown clamps; we skip.** Same as Case D.
- The Rust/Python ALL_IN push at `hunl.rs:1133-1135` /
  `action_abstraction.py:236-237` has NO `stack > to_call` guard, where
  Brown has `if (include_all_in && remaining > to_call)`. **This IS the
  phantom-ALL_IN bug** (topology audit Diff #3) — already known.

**Guards we have that Brown doesn't:**
- **Min-raise floor** (`raise_to_for_fraction`, line 1027) — Brown has
  no min-raise check; the smallest fraction (0.33) effectively sets a
  pot-fraction floor. Our floor is `max(to_call, big_blind)` chips,
  which is the standard NLHE min-raise rule. Defensible; arguably a
  correctness improvement over Brown.

**Bug found:** none new.

---

### Case F. Unconditional ALL_IN push at the bottom

**Brown:** no such unconditional push. ALL_IN is folded into the bet/raise
amount list and gated by `remaining > 0` (no-bet case) or
`remaining > to_call` (facing-bet case).

**Rust** (`hunl.rs:1133-1135`):
```rust
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);
}
```

**Python** (`action_abstraction.py:236-237`):
```python
if ctx.include_all_in:
    actions.append(ACTION_ALL_IN)
```

**Guards present:** only `include_all_in` config flag. NO check on
`stack > 0`, NO check on `stack > to_call`, NO check on `cap_reached`.

**Guards missing vs Brown:**

1. **`stack > to_call` guard at facing-bet nodes** — this is the known
   phantom-ALL_IN bug at facing-all-in nodes (Diff #3). Already
   documented; **fix is open**.

2. **`!cap_reached` guard at facing-bet nodes** — Diff #2. On `main`,
   when raises are capped, we push CALL+FOLD but ALSO push ALL_IN
   (since ALL_IN is unconditional). PR 35c added the cap guard.
   **Status on `main` is uncertain** — line 1133-1135 has no cap guard
   visible. ToDo: confirm whether PR 35c landed.

3. **`stack > 0` guard** — if `stack == 0`, the function returns early
   at line 1109. So the line-1133 ALL_IN push is dead-reachable when
   `stack > 0`. The push is safe in that case (the ALL_IN action pays
   `stacks[player]` which is `>0`).

**Bug found:** the unconditional push is the **single source** of all
three Diff #2 / Diff #3 / "phantom" symptoms. Already known. NO
additional new bugs surfaced.

---

## 2. Specific sanity checks from the brief

| Check | Status | Notes |
|---|---|---|
| CALL when `stack == 0` | OK | `stack <= 0` early-return at `hunl.rs:1109` and `action_abstraction.py:214` prevents CALL emission. Python `raise AssertionError`; Rust returns empty. Divergence is a smell, not a bug. |
| FOLD when no bet to face | OK | FOLD only pushed inside `if facing_bet` branch (`hunl.rs:1116`, `action_abstraction.py:222`). Brown matches. |
| CHECK vs CALL at start of betting round | OK | Mutually exclusive on `facing_bet` (Rust 1115-1120; Python 221-225). When `to_call == 0`, CHECK; when `to_call > 0`, CALL. **No conflation.** |
| Bet sizes clamped when exceeding stack | **MISMATCH** | Brown clamps (`river_game.cpp:58`); we skip (`hunl.rs:1069`). Diff S3 — already tracked. |
| Min-raise discipline | OK | `raise_to_for_fraction` (`hunl.rs:1021-1028`) floors at `aggressor_contrib + max(to_call, big_blind)`. Brown has no min-raise floor. We are STRICTER. |

---

## 3. Identified bugs (none new)

After full code review of `enumerate_legal_actions`, `enumerate_bets`,
`enumerate_raises`, `compute_bet_amount`, `compute_raise_to`, and
`apply_player` in both `crates/cfr_core/src/hunl.rs` and
`poker_solver/action_abstraction.py`:

**Pre-existing bugs (already documented in `action_menu_topology_audit.md`):**

1. **Phantom ALL_IN at facing-all-in nodes (Diff #3).** File:
   `crates/cfr_core/src/hunl.rs:1133-1135` and
   `poker_solver/action_abstraction.py:236-237`.
   Missing guard: `ctx.to_call < stack_remaining(ctx)`.
   Recommended fix sketch:
   ```rust
   if ctx.include_all_in && stack_remaining(ctx) > ctx.to_call {
       actions.push(ACTION_ALL_IN);
   }
   ```
   (Brown's equivalent: `remaining > to_call` at line 98.)

2. **Phantom ALL_IN at cap-reached facing-bet nodes (Diff #2).** Same
   file:line.
   Missing guard: `!cap_reached`.
   Recommended fix sketch:
   ```rust
   if ctx.include_all_in && !cap_reached {
       actions.push(ACTION_ALL_IN);
   }
   ```
   (Brown's equivalent: `raises >= max_raises` early-return at line 76-78
   means no ALL_IN at cap either.) **Note:** topology audit says
   "PR 35c fixes" — still not seen on `main`.

3. **Bet-size skip-instead-of-clamp (Diff S3).** Files:
   `hunl.rs:1062-1079` (`enumerate_bets`), `hunl.rs:1081-1101`
   (`enumerate_raises`), and Python mirrors.
   Missing behavior: clamp `bet_amount = min(bet_amount, stack)` and
   `total_add = min(total_add, remaining)` then dedupe (Brown style).
   Recommended fix sketch: emit the clamped amount, rely on dedupe to
   collapse against ALL_IN amount (Brown's pattern).

**NEW bugs found this audit:** **NONE.**

---

## 4. Style/divergence notes (not bugs)

- **Python `raise` vs Rust empty-return** on `stack <= 0`
  (`action_abstraction.py:214-217` vs `hunl.rs:1109-1111`). Both
  branches are unreachable per invariant; divergence does not affect
  correctness but is a cleanliness issue. Could harmonize by having
  Rust `unreachable!()` in debug.
- **Action ORDER** difference (Brown `[c, f, ...]` vs Rust
  `[FOLD, CALL, ...]`) is COMPENSATED by PR 40's permutation. Not a
  bug. (Topology audit Diff #1.)
- **Min-raise floor** — we are STRICTER than Brown. This is a
  correctness improvement (standard NLHE rule) not a bug.
- **Banker's rounding** — `python_round_positive` uses
  `round_ties_even()` to match Python's `round()`. Brown uses
  `std::round` which is round-half-away-from-zero. Sub-chip rounding
  drift; topology audit Diff S2.

---

## 5. Verdict

**NO-OTHER-BUGS.**

The phantom-ALL_IN bug at facing-all-in nodes (Diff #3) and the
phantom-ALL_IN bug at cap-reached nodes (Diff #2) are both manifestations
of the SAME root cause: the unconditional `ALL_IN` push at
`crates/cfr_core/src/hunl.rs:1133-1135` and
`poker_solver/action_abstraction.py:236-237` has no guards beyond the
`include_all_in` config flag, where Brown's ALL_IN emission is gated by
`remaining > 0` (no-bet) or `remaining > to_call` (facing-bet), and
short-circuited entirely when `raises >= max_raises`.

The Diff S3 bet-size skip-instead-of-clamp is structurally different but
also already tracked.

No additional unconditional action emissions were found that lack a
sanity guard Brown has. The action menu has exactly ONE structural bug
class (the unguarded ALL_IN push), with two distinct symptoms
(cap-reached, facing-all-in). The single-fix recommendation is to add
both guards to the line 1133-1135 / 236-237 push:

```rust
if ctx.include_all_in
    && !cap_reached
    && stack_remaining(ctx) > ctx.to_call
{
    actions.push(ACTION_ALL_IN);
}
```

(The `stack > to_call` guard collapses to `stack > 0` at no-bet nodes
where `to_call == 0`, which is the correct Brown analog.)
