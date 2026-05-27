# Action-Menu Topology Audit: Our Rust HUNL vs Brown's River Solver

**Date:** 2026-05-24
**Mode:** Read-only audit. No code modified.
**Trigger:** Empirical 22-42pp divergence at deep-cap nodes between our
solver and Brown's. Terminal-utility convention has been audited and is
correct in both engines. The leading remaining hypothesis is
**game-tree topology mismatch** in the action-menu enumeration.

**Files audited:**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` lines
  1062-1139 (`enumerate_legal_actions`, `enumerate_bets`,
  `enumerate_raises`, sizing helpers)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp`
  lines 31-107 (`legal_actions`)

**Tree state on main (verified):** PR 35c (paired cap-guard) is NOT
merged. Current `hunl.rs:1133` is the unconditional
`if ctx.include_all_in { actions.push(ACTION_ALL_IN); }`. The "spawned
fix" / "PR 47" alluded to in the task brief does NOT exist on `main`
or in any pushed branch.

**Tree state on PR 35c branch (verified):** Adds `&& !cap_reached` to
the ALL_IN push (both Rust and Python). Does NOT add a
`stack > to_call` guard.

---

## TL;DR

**Verdict: TOPOLOGY-MISMATCH.** Counted **3 confirmed mismatches** at
distinct node types, plus **3 secondary sizing differences** that could
emit different bet/raise amounts even when the action count agrees.

The two most load-bearing mismatches (cap-reached, facing-all-in) BOTH
manifest at deep-cap nodes in the K72/A83 fixtures and BOTH cause Rust
to emit an extra `ALL_IN` action that Brown does not have. PR 35c
closes one of the two; the other remains open and is the direct
mechanical cause of the dry-run-#2 observation that at history
`b1000A`, Brown emits `[c, f]` (2 actions) while Rust emits
`[FOLD, CALL, ALL_IN]` (3 actions).

---

## 1. Side-by-side comparison per node type

For each node type, Brown emits actions in the order `[c|f, c|b|r..., (all-in)]`
(insertion order from `legal_actions`); Rust emits actions sorted by
action-ID via `sort_unstable` at line 1137 of `hunl.rs`.

### 1.1 No-bet (open / check-around) node

**Brown** (`river_game.cpp:48-71`):

```cpp
if (to_call == 0) {
    actions.push_back({'c', 0});                  // check
    std::vector<int> amounts;
    for (double size : bet_sizes) {
        int bet_amount = static_cast<int>(std::round(pot * size));
        if (bet_amount <= 0) continue;
        bet_amount = std::min(bet_amount, remaining);
        if (bet_amount > 0) amounts.push_back(bet_amount);
    }
    if (include_all_in && remaining > 0) {
        amounts.push_back(remaining);
    }
    std::sort(amounts.begin(), amounts.end());
    std::unique(...);
    for (int amount : amounts) actions.push_back({'b', amount});
    return actions;
}
```

Emitted: `[c, b_low, b_med, ..., (b_jam if include_all_in && remaining > 0)]`.

**Rust** (`hunl.rs:1118-1138`):

```rust
} else {
    actions.push(ACTION_CHECK);
}
// ...
if !cap_reached {
    if facing_bet { ... } else {
        actions.extend(enumerate_bets(ctx));    // sized bets only
    }
}
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);                 // ALWAYS
}
actions.sort_unstable();
```

Emitted (after sort by ID): `[CHECK=1, BET_33=3, BET_75=4, ..., ALL_IN=13]`.

**Diff:**
- **Match in steady state** (both have `[check, bets..., all_in]` when
  `remaining > 0` and `include_all_in == true`).
- **Diff #S1 (sizing): `min_bet` floor.** Rust applies
  `raw.max(min_bet)` where `min_bet = min_bet_bb * big_blind`
  (`hunl.rs:1018`). Brown has NO floor; if `round(pot * fraction)` is
  zero, Brown SKIPS the bet (line 55: `if (bet_amount <= 0) continue;`),
  whereas Rust BUMPS it up to `min_bet_bb * big_blind`. With
  default `min_bet_bb=1` and `big_blind=100`, any fraction-produced
  amount below 100 chips gets floored to 100 in Rust. Brown skips it.
  Impact: at the river fixtures (pot=1000+), `0.5 * 1000 = 500 > 100`,
  so this won't trigger. But on small-pot or very-small-fraction
  configs it can.

- **Diff #S2 (sizing): rounding mode.** Brown uses `std::round` (C++
  round-half-away-from-zero). Rust uses `python_round_positive`
  (banker's rounding / round-half-to-even). For fractions like
  `pot * 0.5 = 622.5`, Brown returns 623, Rust returns 622. Impact: on
  ties of the form `pot * fraction = integer + 0.5`, the two engines
  pick adjacent integers. Off by 1 chip, which then propagates into the
  pot for subsequent nodes. (Documented in `hunl.rs:992-1014`.)

- **Diff #S3 (sizing): all-in collapse / clamping.** Brown clamps a
  too-big bet to `remaining` (line 58: `bet_amount = std::min(bet_amount, remaining)`)
  and KEEPS it. Rust SKIPS bets where `raw_amount >= stack` or
  `(stack - raw_amount) <= force_allin_threshold` (line 1069 of
  `enumerate_bets`). So Brown's `b_2x_pot` becomes a smaller-than-2x
  bet that happens to equal `remaining`; Rust drops the 2x sizing
  entirely and relies on the separate `ALL_IN` action to cover it.
  Brown's `std::unique` then merges the clamped bet with `b_jam` (the
  all-in amount) if they're identical, so Brown emits ONE action where
  Rust emits TWO (`b_2x_clamped == ALL_IN`, but Rust never pushed the
  `b_2x` and pushes `ALL_IN` separately). **Net action-count effect: in
  steady state with pot=1000, stack=9500, fractions=[0.5, 1.0], no
  clamping triggers and both emit the same set. At deep nodes with
  short remaining stacks, this can produce off-by-one action counts.**

### 1.2 Facing-bet node, not at cap, opponent NOT all-in

**Brown** (`river_game.cpp:73-106`):

```cpp
actions.push_back({'c', to_call});                // call
actions.push_back({'f', 0});                      // fold
if (state.raises >= max_raises) return actions;   // CAP guard
int pot_after_call = pot + to_call;
for (double size : bet_sizes) {
    int raise_amount = round(pot_after_call * size);
    if (raise_amount <= 0) continue;
    int total_add = to_call + raise_amount;
    if (total_add > remaining) {
        total_add = remaining;
        raise_amount = total_add - to_call;
    }
    if (raise_amount > 0 && total_add > to_call) {
        amounts.push_back(raise_amount);
    }
}
if (include_all_in && remaining > to_call) {       // STACK > TO_CALL guard
    amounts.push_back(remaining - to_call);
}
// sort+unique amounts, push as `{'r', amount}` each.
```

Emitted: `[c, f, r_low, r_med, ..., (r_jam if remaining > to_call)]`.

**Rust** (`hunl.rs:1115-1138`):

```rust
if facing_bet {
    actions.push(ACTION_FOLD);
    actions.push(ACTION_CALL);
}
if !cap_reached {
    if facing_bet {
        actions.extend(enumerate_raises(ctx));    // sized raises only
    } else { ... }
}
if ctx.include_all_in {                            // NO stack > to_call guard
    actions.push(ACTION_ALL_IN);
}
actions.sort_unstable();
```

Emitted: `[FOLD=0, CALL=2, RAISE_33=8, ..., ALL_IN=13]`.

**Diff:**
- **Diff #1 (ORDER): Brown is `[c, f, raises]`; Rust is `[FOLD, CALL, raises, ALL_IN]`.**
  PR 40's `_brown_to_rust_action_permutation` (`test_v1_5_brown_apples_to_apples.py:389-441`)
  remaps brown→rust as `[1, 0, 2, ...]`. PR 40 is NOT merged on main.
  The acceptance test on `main` compares position-by-position
  (`brown_row[a_idx]` vs `rust_row[a_idx]`), so Brown's `c` is compared
  against Rust's `f`, etc. **Verified by inspection** of
  `tests/test_v1_5_brown_apples_to_apples.py:547-555` (no permutation
  applied). The dry-run reports cited in the task brief include the
  PR 40 branch via cherry-pick (see
  `docs/v1_6_1_dryrun_attempt_2.md` table at line 41), so the column-
  mapping IS applied in those measurements.

- **Match: raise sizings in steady state agree by ascending amount.**

- **Diff #S4 (sizing): raise computation.** Brown computes
  `raise_amount = round(pot_after_call * fraction)`, where
  `pot_after_call = pot + to_call`. The new contribution becomes
  `cur_contrib + to_call + raise_amount`. Rust computes
  `raise_to = aggressor_contrib + round((pot + to_call) * fraction)`.
  When `cur_contrib + to_call == aggressor_contrib` (always true after
  a single bet/raise has been called and the next actor is facing the
  bet for the first time — because `cur_contrib + to_call` brings me
  level with the aggressor), the two formulas produce the SAME new
  contribution. Verified algebraically:
  - Brown: `new_contrib = cur + to_call + round((pot+to_call) * f)`
  - Rust: `new_contrib = aggressor_contrib + round((pot+to_call) * f)`
  - These are equal iff `cur + to_call == aggressor_contrib`, i.e.,
    after a call the cur-player would be level with the aggressor. This
    holds at every facing-bet node in a 2-player game.
  **No mismatch in steady state.**

- **Diff #S5 (sizing): min-raise floor.** Rust applies
  `raise_to.max(aggressor_contrib + max(to_call, big_blind))`
  (`hunl.rs:1027`). Brown has no min-raise floor. Impact: very small
  pot-fraction raises that round below `to_call` get bumped up in Rust
  and silently kept-as-is in Brown. Could produce different raise
  amounts on small-pot tiny-fraction configs; on K72/A83 (pot=1000+,
  fractions=[0.5, 0.75, 1.0, 1.5]), `round(pot_after_call * 0.5)` >= 750,
  which exceeds `to_call=1000`? No — at the bet-1000 facing-bet node,
  `pot_after_call = 3000`, `round(3000 * 0.5) = 1500 > 1000`. Floor
  does not trigger.

### 1.3 Facing-bet node, at cap (raises >= max_raises)

**Brown** (`river_game.cpp:76-78`):

```cpp
actions.push_back({'c', to_call});
actions.push_back({'f', 0});
if (state.raises >= max_raises) {
    return actions;                                // EARLY RETURN
}
// ... (raise/all-in code skipped)
```

Emitted: `[c, f]` only. 2 actions.

**Rust (current `main`, `hunl.rs:1115-1138`):**

```rust
if facing_bet {
    actions.push(ACTION_FOLD);
    actions.push(ACTION_CALL);
}
let cap = raise_cap(ctx);
let cap_reached = ctx.street_num_raises >= cap;
if !cap_reached {
    // raise enumeration — skipped at cap, GOOD
}
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);                  // UNCONDITIONAL — BUG
}
actions.sort_unstable();
```

Emitted (on `main`): `[FOLD, CALL, ALL_IN]`. 3 actions. **MISMATCH.**

**Rust (with PR 35c paired-fix branch):**

```rust
if ctx.include_all_in && !cap_reached {
    actions.push(ACTION_ALL_IN);                  // cap-guarded
}
```

Emitted: `[FOLD, CALL]`. 2 actions. **MATCH.**

**Diff #2 (CAP): On `main`, Rust emits an extra ALL_IN at cap-reached
nodes. PR 35c fixes this.**

### 1.4 Facing-bet node, opponent ALREADY all-in (stack < to_call OR to_call >= remaining)

This is the case the task brief calls "facing-all-in." At
history `b1000A` on the A83 fixture (pot=1000, stack=9500,
initial_contributions=[500, 500]):

1. P1 bets 1000. contribs=[500, 1500], to_call=1000 from P0's view,
   raises=1.
2. P0 ALL_IN: contribs=[10000, 1500], stacks=[0, 8500], P0's
   `all_in=true`, raises=2.
3. P1's turn. From P1's view: `to_call = contrib_P0 - contrib_P1 = 8500`,
   `stack_P1 = 8500`. So `to_call == stack`.

**Brown** (`river_game.cpp:74-100`):

```cpp
actions.push_back({'c', to_call});         // call  — line 74
actions.push_back({'f', 0});                // fold  — line 75
if (state.raises >= max_raises) return actions;  // cap=3, raises=2, NOT triggered
// ... raise enumeration: with remaining=8500, for each fraction:
//    raise_amount = round(pot_after_call * f), e.g. 0.5 * (12500) = 6250
//    total_add = to_call + raise_amount = 8500 + 6250 = 14750
//    if (total_add > remaining) { total_add = remaining=8500; raise_amount = 0 }
//    if (raise_amount > 0 && total_add > to_call) { push }
//      → raise_amount = 0, SKIPPED. Same for all fractions.
if (include_all_in && remaining > to_call) {   // 8500 > 8500 = FALSE — SKIPPED
    amounts.push_back(remaining - to_call);
}
// amounts is empty. No raises pushed.
return actions;   // [c, f] — 2 actions
```

Emitted: `[c, f]`. 2 actions.

**Rust (current `main` AND PR 35c branch — same behavior at this node):**

```rust
// facing_bet=true, cap_reached=false (raises=2 < cap=3)
actions.push(ACTION_FOLD);
actions.push(ACTION_CALL);
// enter enumerate_raises(ctx):
//   for each fraction:
//     raise_to = aggressor_contrib(10000) + round((pot + to_call) * f)
//     min_raise_to = 10000 + max(to_call=8500, big_blind=100) = 18500
//     raise_to = max(raise_to, 18500) >= 18500
//     max_raise_to = cur_contrib(1500) + stack(8500) = 10000
//     `if raise_to >= max_raise_to` → 18500 >= 10000 → SKIP every fraction.
//   No raises pushed. GOOD.
if ctx.include_all_in {                  // TRUE — UNCONDITIONAL push
    actions.push(ACTION_ALL_IN);
}
actions.sort_unstable();
```

Emitted: `[FOLD=0, CALL=2, ALL_IN=13]`. 3 actions. **MISMATCH.**

**The downstream effect of the phantom ALL_IN at `b1000A`:** when P1
"ALL_INs" here, `apply_player` (`hunl.rs:703-712`) sets `pay = stacks[1] = 8500`,
`contribs = [10000, 10000]`, `to_call = max(0, 0) = 0`. This is
mechanically equivalent to a CALL but tagged with action_id=13 (ALL_IN)
instead of action_id=2 (CALL). The Rust solver treats this as a
separately-indexed action with its own regret bucket, splitting
strategy mass that should be concentrated on CALL/FOLD. This is
plausibly load-bearing for the dry-run-#2 K72 42pp / A83 27pp residual.

**Diff #3 (FACING-ALL-IN): On `main` AND on PR 35c, Rust emits an
extra ALL_IN at facing-all-in (stack <= to_call) nodes.** PR 35c does
NOT fix this. Brown's `remaining > to_call` guard at
`river_game.cpp:98` is the missing safeguard.

---

## 2. Bet-size set comparison

| Spot | Brown's `bet_sizes` | Rust's `bet_size_fractions` (per-spot config) |
|---|---|---|
| `dry_K72_rainbow` | `[0.75, 1.5]` (from `river_spots.json`) | `[0.75, 1.5]` (test sets via `bet_size_fractions=tuple(spot.bet_sizes)` at line 258) |
| `dry_A83_rainbow` | `[0.5, 1.0]` | `[0.5, 1.0]` |

**Verdict:** bet-size sets MATCH per spot (test wiring is correct).
Rust's default `[0.33, 0.75, 1.00, 1.50, 2.00]` is overridden by the
per-spot config.

---

## 3. Action ORDER comparison

| Node type | Brown order | Rust order (after `sort_unstable` by ID) |
|---|---|---|
| No-bet | `[c, b_low, b_med, ..., b_jam]` | `[CHECK=1, BET_33=3, BET_75=4, BET_100=5, BET_150=6, BET_200=7, ALL_IN=13]` |
| Facing-bet | `[c, f, r_low, r_med, ..., r_jam]` | `[FOLD=0, CALL=2, RAISE_33=8, ..., RAISE_200=12, ALL_IN=13]` |
| At cap | `[c, f]` | `[FOLD, CALL, (ALL_IN on main)]` |

**Order Diff:** at facing-bet nodes, Brown has `c` first then `f`;
Rust has `FOLD` first then `CALL`. PR 40's
`_brown_to_rust_action_permutation` swaps positions 0 and 1 to
compensate. PR 40 is NOT on `main` but IS in the dry-run-#2 bundle.
Action_count parity-check confirms PR 40 is applied in those
measurements (the dry-run reports show `(brown_pos=0, rust_pos=1)` and
`(brown_pos=1, rust_pos=0)` annotations).

**Verdict:** order difference is COMPENSATED in dry-run #2 by PR 40.
Order is NOT the cause of the residual 22-42pp divergence.

---

## 4. All-in collapse (when call >= stack)

When `to_call >= stack` (facing an over-shove or jam-for-equal-stack):

- **Brown** (`river_game.cpp:120-138`): A CALL contribution adds
  `to_call` chips. If the cur-player's `contrib_player + to_call`
  exceeds their stack, this would be a chip-math error in Brown — but
  Brown's tree builder NEVER reaches this state because the parent
  action (the all-in by opponent) only emits when
  `remaining > to_call_of_parent`. So Brown's tree never enters a
  state where a player has `to_call > remaining`. **No collapse path
  needed.**

- **Rust** (`hunl.rs:693-702`): A CALL applies
  `pay = self.to_call.min(stacks[player])` — explicit clamp. So Rust's
  CALL collapses to a sub-call (whatever the cur-player has) at
  `b1000A` when P1 calls, paying its remaining 8500. This is correct
  game-theoretically. But Rust ALSO emits ALL_IN (the phantom action
  from Diff #3 above), which also pays 8500 — semantically identical
  to CALL but with different action-ID and different regret bucket.

**Verdict:** Rust's CALL handles the collapse correctly. The problem is
the EXTRA `ALL_IN` action emitted alongside it (Diff #3).

---

## 5. Summary of mismatches

| # | Type | Severity | Description | Fix on main? | Fix in PR 35c? |
|---|---|---|---|---|---|
| 1 | ORDER | LOW (compensated) | Brown `[c, f, raises]` vs Rust `[F, C, raises, A]` | NO | NO (PR 40 separate) |
| 2 | CAP-REACHED | HIGH | Rust emits extra ALL_IN at cap | NO | YES (cap-guard added) |
| 3 | FACING-ALL-IN | HIGH | Rust emits extra ALL_IN when stack <= to_call | NO | **NO** (still open) |
| S1 | SIZING | LOW (steady state) | Rust min_bet floor; Brown skips | NO | NO |
| S2 | SIZING | LOW (±1 chip) | Rust banker rounding; Brown round-half-up | NO | NO |
| S3 | SIZING | MEDIUM | Brown clamps bet to remaining; Rust skips and relies on ALL_IN | NO | NO |
| S4 | SIZING | NONE in steady state | Brown/Rust raise math differs algebraically but is equal in 2P after call | (n/a) | (n/a) |
| S5 | SIZING | LOW (steady state) | Rust min-raise floor; Brown has none | NO | NO |

**Count: 3 confirmed structural mismatches + 4 sizing-rule mismatches
(of which only S3 has plausible non-trivial impact on K72/A83).**

**Note on PR 40:** PR 40 fixes ORDER on the test SIDE (Brown→Rust
column permutation), NOT on the engine side. The engines still emit
in different orders. This is fine for the acceptance test but means
any other consumer comparing Rust action vectors to Brown's must
also apply the permutation.

---

## 6. Verdict

**TOPOLOGY-MISMATCH** at the following node types:

1. **Cap-reached facing-bet node** (`raises >= max_raises`):
   Rust on `main` emits an extra `ALL_IN`. PR 35c fixes.
2. **Facing-all-in node** (`to_call >= stack`):
   Rust on both `main` and PR 35c emits an extra `ALL_IN`. Open.

The dry-run-#2 finding (history `b1000A`: Brown 2 actions, Rust 3
actions) is exactly this second case. Even though PR 35c was in the
dry-run #2 bundle, the bundle's A83 retained a 27pp divergence — the
unpatched facing-all-in case is a direct mechanical cause for this
residual.

The K72 42pp residual at `b1500r5000` is NOT explained by Diff #3
alone. Traced: at `b1500r5000` (K72: pot=1000, stack=9500,
sizes=[0.75, 1.5]), P1's `stack = 8000 > to_call = 3000`, so this
node is NOT facing-all-in. Both Brown and Rust correctly emit 3
actions here (`[c, f, r_jam]` for Brown, `[FOLD, CALL, ALL_IN]` for
Rust — equivalent action set under PR 40's column permutation). The
ALL_IN-as-raise child at this node also matches Brown exactly
(P1 contrib 2000→10000). The cap-reached / facing-all-in nodes
TWO levels deeper are where Diff #2 (closed by PR 35c) and Diff #3
(still open) bleed regret into the upstream node.

After PR 35c (cap-guard) closes Diff #2, the remaining K72 divergence
is most consistent with the terminal-utility convention bias
(`base_pot × P_win` regret accumulation documented in
`a83_deep_cap_root_cause_investigation.md` candidate (d)). The
contribution of the still-open Diff #3 (facing-all-in extra ALL_IN)
to K72 vs A83 is unknown from this audit alone; would require an
A/B run with Fix 1 applied to quantify.

---

## 7. Recommended fixes (in priority order)

### Fix 1 — Close Diff #3 (facing-all-in) — paired Rust+Python

**Rust:** `crates/cfr_core/src/hunl.rs:1133-1135`

```rust
// CURRENT:
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);
}

// PROPOSED (combines PR 35c's cap-guard + new stack > to_call guard):
let stack = stack_remaining(ctx);
let to_call = ctx.to_call;
let can_increase_stake = stack > to_call;   // Brown's `remaining > to_call`
if ctx.include_all_in && !cap_reached && can_increase_stake {
    actions.push(ACTION_ALL_IN);
}
```

The new `stack > to_call` guard mirrors Brown's `river_game.cpp:98`
condition exactly. When the cur-player can't bet beyond what's already
been wagered (because their entire remaining stack equals the
to-call), CALL is semantically identical to ALL_IN and Brown does not
emit the latter.

For the no-bet branch (`facing_bet == false`, `to_call == 0`), the
guard simplifies to `stack > 0`, which is already enforced by the
`if stack <= 0 { return actions; }` early-return at line 1109.

**Python:** `poker_solver/action_abstraction.py:236-237`

```python
# CURRENT:
if ctx.include_all_in:
    actions.append(ACTION_ALL_IN)

# PROPOSED:
stack = _stack_remaining(ctx)
can_increase_stake = stack > ctx.to_call
if ctx.include_all_in and not cap_reached and can_increase_stake:
    actions.append(ACTION_ALL_IN)
```

**Impact:** closes the dry-run-#2 `b1000A` action-count mismatch. Should
remove the extra-ALL_IN regret bucket at every facing-all-in node and
allow CALL to absorb the full mass that previously bled to ALL_IN.

### Fix 2 — Also close Diff #2 (already done in PR 35c)

Merge PR 35c if not already absorbed by the proposed Fix 1 above. Fix 1
as written supersedes PR 35c (it ADDS the `&& !cap_reached` guard from
PR 35c plus the `&& can_increase_stake` guard for Diff #3).

### Fix 3 — Compensate or close Diff #1 (action order)

Either:
- Apply PR 40's `_brown_to_rust_action_permutation` to all test sites
  that compare Brown vs Rust position-by-position (current acceptance
  test wiring on main does NOT have this; the dry-run bundles do).
- OR change Rust's action ID assignment so that sorted-by-ID matches
  Brown's `[c, f, raises]` order: would require renumbering CALL=0,
  FOLD=1, ... (large blast radius — every test, every infoset key,
  every CHANGELOG entry would shift).

The first option (test-side permutation) is preferred; it's local and
already exists as PR 40.

### Fix 4 (defer) — sizing diffs S1/S2/S3/S5

Low priority. None are load-bearing for the current K72/A83 fixtures
under the current configs.

---

## 8. Source-of-truth pointers

- This document:
  `/Users/ashen/Desktop/poker_solver/docs/action_menu_topology_audit.md`
- Rust enumeration:
  `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:1062-1139`
- Rust apply_player (call/all-in semantics):
  `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:673-782`
- Python enumeration:
  `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py:208-239`
- Brown enumeration:
  `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp:31-107`
- PR 35c fix report (cap-guard only):
  `/Users/ashen/Desktop/poker_solver/docs/pr_35c_paired_fix_report.md`
- Dry-run #2 finding (b1000A mismatch):
  `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_attempt_2.md`
- A83 root-cause analysis:
  `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
- Test (action-order permutation lives here in PR 40):
  `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
