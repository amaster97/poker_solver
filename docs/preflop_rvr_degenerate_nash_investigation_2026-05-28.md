# Preflop RvR degenerate-Nash investigation — 2026-05-28

**Status:** root cause identified (config-vs-state convention mismatch). Code-level fix proposed; user decides whether to fix the code or document the config invariant. Smoke test passed — but only because the smoke test uses the "correct" config convention.

**Trigger:** `_rust.solve_hunl_preflop_rvr` from PR #122 produces a degenerate equilibrium at 40 BB / 1000 iters: SB folds J7o 100% at root, BB folds 99.25% facing 3bb, KQs and 98s defend 0%. Convergence is going IN THE WRONG DIRECTION as iter count increases (93% → 99.25% from 100 → 1000 iters).

**Reproduction:** `/tmp/test1_40bb_1000iter.py`.

## Root cause: `initial_contributions` interpretation mismatch

The user's repro config passes:

```python
"small_blind": 50, "big_blind": 100,
"initial_pot": 0,
"initial_contributions": [50, 100],   # <-- THIS
```

The Rust solver's preflop state initializer (`crates/cfr_core/src/preflop_rvr.rs:113-135`) sets:

```rust
let sb_contrib = config.small_blind + config.ante;   // 50
let bb_contrib = config.big_blind + config.ante;     // 100
contributions: [sb_contrib, bb_contrib],             // [50, 100]
```

The blinds are pushed into `contributions[]` from `small_blind`/`big_blind` **regardless** of `config.initial_contributions`. The user's `initial_contributions: [50, 100]` is then **double-subtracted** at every leaf payoff calculation:

`crates/cfr_core/src/preflop_rvr.rs:489-492` (equity leaf):
```rust
let cs0 = (contributions[0] - initial_contributions[0]) as f64;  // 50 - 50 = 0
let cs1 = (contributions[1] - initial_contributions[1]) as f64;  // 100 - 100 = 0
let pot_total = initial_pot as f64 + cs0 + cs1;                  // 0 + 0 + 0 = 0
```

And `crates/cfr_core/src/preflop_rvr.rs:580-589` (fold leaf):
```rust
let cs0 = (contributions[0] - initial_contributions[0]) as f64;  // also 0 at root
let cs1 = (contributions[1] - initial_contributions[1]) as f64;
let pot_total = *initial_pot as f64 + cs0 + cs1;                 // 0
let payoff = if *folded_player == 0 {
    [-cs0 / bb, (pot_total - cs1) / bb]                          // [0, 0]
} else {
    [(pot_total - cs0) / bb, -cs1 / bb]                          // [0, 0]
};
```

### Numeric trace at 40 BB with the buggy config

| Scenario | `contributions` | `cs0`, `cs1` | `pot_total` | SB payoff | BB payoff |
|---|---|---|---|---|---|
| SB folds at root | [50, 100] | 0, 0 | 0 | **0 BB** | **0 BB** |
| BB folds to SB 3bb open | [300, 100] | 250, 0 | 250 | **0 BB** | 0 BB |
| BB calls SB 3bb open (showdown @ ε=50%) | [300, 300] | 250, 200 | 450 | (225-250)/100 = **-0.25 BB** | -0.20 BB |

Compare to the **correct** chip flow (what user expected):
| Scenario | SB payoff | BB payoff |
|---|---|---|
| SB folds at root | -0.5 BB (loses SB) | +0.5 BB (wins SB) |
| BB folds to SB 3bb open | +1.0 BB (wins BB blind) | -1.0 BB (loses BB) |
| BB calls SB 3bb open (showdown @ ε=50%) | -0.5 BB | -0.5 BB (dead money — wait this isn't right) |

Wait — the third row uses `pot_total = 600` correctly: `(600*0.5 - 300)/100 = 0` for both. The real divergence is rows 1 and 2: under the buggy config the SB has nothing to gain by opening (BB folding pays SB 0 BB instead of +1 BB) and nothing to lose by folding pre-action (SB folding pays SB 0 BB instead of -0.5 BB). **Folding becomes dominant.** That is exactly the degenerate equilibrium the user observed.

### Why the AA-vs-KK smoke test (`preflop_rvr_smoke.rs:104`) passed

The smoke-test config (`crates/cfr_core/tests/preflop_rvr_smoke.rs:29-52`, `default_preflop_config()`) sets `initial_contributions: [0, 0]`. Under THAT config:

- `contributions = [50, 100]` (set by `initial_preflop` from blinds)
- `cs0 = 50, cs1 = 100, pot_total = 150` at root
- SB fold payoff: `[-0.5, +0.5]` BB — **correct**

AA still wants to raise: equity vs KK is ~81% so opening any size to a call earns ~0.31 × pot BB. With proper chip flow, AA's raise is correctly EV-positive. The smoke test asserts only `fold_prob < 0.05` and `agg_prob > 0.5`; it never exercises the `initial_contributions: [50, 100]` path.

## Action mapping (task 1) — confirmed

`crates/cfr_core/src/preflop_rvr.rs:142-233`. SB-at-root action enumeration (`state.to_call > 0` → `facing_bet = true`, `street_num_raises == 1 && street_aggressor == 1 && player == 0`):

| Index | Action | `PreflopAction` variant |
|---|---|---|
| 0 | Fold | `Fold` |
| 1 | Call (limp to 1 BB) | `Call` |
| 2-5 | Open to 2 BB, 3 BB, 4 BB, 5 BB | `OpenTo(amt)` |
| 6 | All-in | `AllIn` |

The user's reading is correct (and the AA strategy `[0, 0, 0.37, 0.26, 0.19, 0.13, 0.05]` has zero on fold/limp, mass on opens/jam — matches the menu).

## Equity-table loading (task 2) — not the bug

`crates/cfr_core/src/preflop_rvr.rs:1062` calls `load_equity_table(equity_table_path)`. The 169x169x3 table is queried in `build_equity_leaf_payoff` (line 516) with `(h_class, v_class, variant)`. With `cs0 = cs1 = 0` the equity edge is multiplied into a zero pot, so per-class equity differences become moot in the EV calc. AA-vs-KK still works in the smoke test only because that test uses the correct `initial_contributions = [0, 0]`. Equity loading is not the proximate cause.

## Reach-probability chain (task 4) — not the bug

`crates/cfr_core/src/preflop_rvr.rs:776-792` (opponent-node branch) maintains `next_reach[h] = reach_opp[h] * strategy[h*A + a]` per hand, then re-enters traversal. Lines 810-826 do the symmetric update for own-node. Blocker filter inside `terminal_value_vector` (lines 902-944) zero-weights conflict pairs. Per-hand reach is correctly maintained; this is not the proximate cause.

## Recommended fix

Two equivalent options:

**Option A — fix the code (small, localized):** make `PreflopRvrState::initial` consistent with `HUNLState::initial_preflop` and the user's natural intuition that `initial_contributions: [50, 100]` means "the blinds are already in the pot." Replace `crates/cfr_core/src/preflop_rvr.rs:113-135` with:

```rust
fn initial(config: &HUNLConfig) -> Self {
    // Use config.initial_contributions if non-zero, else default to the
    // posted-blinds layout. This matches the convention used everywhere
    // else: initial_contributions=[0,0] means "treat the blinds as live
    // (counted into chip flow)"; initial_contributions=[sb, bb] means
    // "the blinds are already sunk; don't re-charge them."
    //
    // Currently this fn IGNORES initial_contributions and always uses
    // blinds-from-config, leading to a double-subtraction at the leaf
    // when the user passes initial_contributions=[sb, bb].
    let sb_contrib = if config.initial_contributions[0] > 0 {
        config.initial_contributions[0]
    } else {
        config.small_blind + config.ante
    };
    let bb_contrib = if config.initial_contributions[1] > 0 {
        config.initial_contributions[1]
    } else {
        config.big_blind + config.ante
    };
    // ... rest unchanged
}
```

Actually a cleaner fix: **reject `initial_contributions != [0, 0]` for full-tree preflop RvR** since the only correct setup is to let the engine push the blinds. Add a config validator alongside the existing `initial_hole_cards.is_some()` check at line 1050.

**Option B — document the invariant:** add a docstring + runtime assert in the Python wrapper that `initial_contributions` MUST be `[0, 0]` for `solve_hunl_preflop_rvr`, with the engine handling the blinds internally.

Option B is faster but easier for downstream callers (UI, batch-solve, smoke harnesses) to mis-set silently. Option A's reject-mode is the safest because:
- it surfaces the bug with a clear error message
- it doesn't change semantics for the smoke test or any working caller
- it costs ~6 lines of code

## Suggested next step

1. Add a runtime assert at `crates/cfr_core/src/preflop_rvr.rs:1050` (next to the `initial_hole_cards` check):
   ```rust
   if config.initial_contributions != [0, 0] {
       return Err("solve_hunl_preflop_rvr: initial_contributions must be [0, 0] (blinds are handled internally; pass blinds via small_blind/big_blind)".into());
   }
   ```

2. Re-run `/tmp/test1_40bb_1000iter.py` with `"initial_contributions": [0, 0]` and verify SB opens J7o > 50% and BB defends KQs ~100%.

3. If results look correct, add a regression smoke test analogous to `aa_vs_kk_closed_form_aa_does_not_fold` that uses J7o vs a defending range to catch this class of bug.

## Root cause identified: YES

- **Bug file:line:** `crates/cfr_core/src/preflop_rvr.rs:113-135` (state initializer ignores `initial_contributions`) + `crates/cfr_core/src/preflop_rvr.rs:489-492` and `:580-583` (downstream double-subtraction).
- **User-side mitigation:** pass `"initial_contributions": [0, 0]` in the config; the blinds are pushed internally.
- **Engine-side mitigation:** reject non-zero `initial_contributions` in the public solver entry, since the only valid root-state config is the default.

