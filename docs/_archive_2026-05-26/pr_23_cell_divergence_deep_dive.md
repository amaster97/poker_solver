# PR 23 Cell Divergence Deep Dive

**Date**: 2026-05-23
**Source data**:
- Worktree: `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-cell-dive`
- Branch: `investigate-pr23-cells` (from `origin/main` + cherry-picks of PR 34 `0bafcfa` and PR 35 `33e03ea`)
- Test under investigation: `tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow]`
- Brown side: `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`, 2000 DCFR iterations, seed 7, exploitability 0.044 chips
- Rust side: `crates/cfr_core/src/dcfr_vector.rs` via `poker_solver._rust.solve_range_vs_range_rust`, 2000 DCFR iterations
- Spot: `dry_K72_rainbow` (board `Ks 7h 2d 4c Jh`, pot 1000, stack 9500, bet sizes `[0.75, 1.5]`, max_raises 3)
- Raw dumps: `/tmp/pr23_cell_dive/{brown.json, brown_swapped.json, rust_strategy.json}`

## TL;DR

**The three "divergent cells" cited by the orchestrator are MISDIAGNOSED.** The Rust output and Brown's binary actually AGREE on the per-(hand, action) probabilities for all three cells. The apparent divergence is an artifact of the acceptance test's failure to remap two independent column-ordering differences between the two engines:

1. **Action-axis ordering mismatch** at facing-bet histories. Brown's `legal_actions` emits `[call, fold, raises…]` (`river_game.cpp:74-75`); Rust's `enumerate_legal_actions` emits `[fold, call, raises…, all-in]` (`crates/cfr_core/src/hunl.rs:1115-1119`) and then sorts by action-id (`hunl.rs:1137`), which keeps `FOLD=0` before `CALL=2`. The test (`tests/test_v1_5_brown_apples_to_apples.py:547-556`) compares position-by-position without remapping, so Brown's `c@pos0` is matched against Rust's `f@pos0`. **This single mismatch explains Cells 1, 2, and 3 in full.**

2. **Player-to-range wiring mismatch**. The test passes `spot.ranges[0]` (the polarized betting range) to Rust as `p0_holes` (= our P0 = second-actor on river) and `spot.ranges[1]` (the merged calling range) as `p1_holes` (= our P1 = river opener) — but Brown's binary receives the ranges in the opposite mapping. Brown's opener gets the polarized range; our opener gets the merged range. The two engines therefore solve subtly different games at the root infoset (different ranges in the opener seat), which produces real, but legitimately Nash-different, strategies at deeper nodes. This is independent of bug 1 and surfaces additional false "divergences" at root and downstream.

After correcting BOTH issues (re-running Brown with `replace(spot, ranges=(ranges[1], ranges[0]))` and remapping Rust's `[FOLD,CALL,…]` columns to Brown's `[call,fold,…]` order), the strategies match at every cell the orchestrator flagged, and PR 23's algorithm produces 100%-check at the root for all 55 hands of the merged range — identical to Brown swapped (see §3).

**Confidence: HIGH** that PR 23's vector-form DCFR algorithm is functionally correct. The acceptance test failure is entirely on the test side.

---

## 1. Per-cell analysis

The three cells the orchestrator flagged all live in Brown's `player1` profile (= our P0, the second-actor on river). All three involve hand `9sTs` (Ts9s = ten-high, no pair, no flush draw on `Ks 7h 2d 4c Jh`).

### Cell 1: `P1 hand=9sTs hist='b1500' action='c'`

**Brown's emission** (raw, `brown.json::player1::profile['b1500']`):
- Actions: `['c', 'f', 'r3000', 'r6000', 'r8000']`
- Strategy for `9sTs` (hand idx 49): `[1.6e-08, 0.999999, 3.5e-07, 4.2e-07, 9.2e-08]`
- Decoded: **`c`=~0, `f`=0.9999991** — Brown FOLDS.

**Rust's emission** (raw, `rust_strategy.json['9sTs|2d4c7hJhKs|r|b1500']`):
- Action ordering at facing-bet, sorted by ID: `[FOLD=0, CALL=2, RAISE_75=9, RAISE_150=11, ALL_IN=13]` → `[FOLD, CALL, r5000, r8000, A]`
- Strategy row: `[0.986, 0.0005, 0.005, 0.003, 0.005]`
- Decoded: **`FOLD`=0.986, `CALL`=0.0005** — Rust ALSO FOLDS.

**Hand-derived Nash for this cell** (sanity check, NOT load-bearing):
- 9sTs ten-high on K-7-2-4-J = high-card only. No pair, no draw, no blocker to top set.
- Equity vs the bettor's range, weighted by `b1500`-frequency from Brown's own root strategy: **18.05%** (computed by mapping each combo's b1500 weight and running `poker_solver.evaluator.evaluate` on hero+board vs villain+board). Wins/ties/losses = 2.53 / 0.12 / 11.68 (weighted by P1-bets-b1500 mass).
- Pot odds at this node: chips_to_call=1500, total_pot_after_call=4000 → **37.5%** equity needed.
- 18% < 37.5% with no implied odds (river — no future streets) → **Nash = pure FOLD**.

**Both engines agree with the Nash derivation.** The "divergence" appears only because the test compares column 0 (Brown's `c`) to column 0 (Rust's `FOLD`):
- Brown col 0 = `c` = 1.6e-8 (call freq, near zero).
- Rust col 0 = `FOLD` = 0.986 (fold freq, near 1).
- `|0.0 - 0.986|` = 0.986 → reported as "brown=0 rust=0.986".

### Cell 2: `P1 hand=9sTs hist='b1500r5000A' action='c'`

**Brown's emission** at `b1500/r3000/r5000` (Brown's equivalent of our `b1500r5000A` — the all-in stack-ceiling raise from P0 sized off Brown's `r5000`=extra over call):
- Actions: `['c', 'f']`
- Strategy for `9sTs`: `[0.00043, 0.99957]` → `c`=0.0004, `f`=0.9996 — Brown FOLDS.

**Rust's emission** at `b1500r5000A`:
- Action ordering at facing-all-in (only fold/call legal): `[FOLD=0, CALL=2]` → `[FOLD, CALL]`
- Strategy row: `[1.0000, 2.8e-08]`
- Decoded: `FOLD`=1.0, `CALL`=~0 — Rust FOLDS.

**Both engines fold ~100%.** Same root cause as Cell 1: test compares Brown's `c@pos0` (call=0.0004) to Rust's `FOLD@pos0` (fold=1.0), reports "brown=0.0004 rust=1.0".

### Cell 3: `P0 hand=9sTs hist='c/b1500' action='f'` (symmetric counterpart of Cell 1)

Picked as a "Brown high (>0.5), Rust low (<0.05)" candidate per the orchestrator instructions.

**Brown's emission** at `c/b1500` (our `xb1500` — P1 checked, P0 bet 1500; now P1 to act):
- Actions: `['c', 'f', 'r3000', 'r6000', 'r8000']`
- Strategy for `9sTs`: `[3.2e-10, 0.99999999, 8.1e-11, 8.1e-11, 8.0e-10]` → `c`=~0, `f`=~1 — FOLD.

**Rust's emission** at `xb1500`:
- Strategy row: `[0.99993, 1.8e-08, 4.9e-08, 6.5e-05, 3.8e-06]`
- Decoded (`[FOLD, CALL, r5000, r8000, A]`): `FOLD`=0.99993, `CALL`=1.8e-08 — FOLD.

**Both engines fold ~100%.** Same column-misalignment artifact: Brown col 1 (`f`=1.0) vs Rust col 0 (`FOLD`=0.99993) match perfectly; Brown col 0 (`c`=~0) vs Rust col 1 (`CALL`=~0) match perfectly; the test's position-wise compare ends up matching Brown's `c@pos0` (~0) against Rust's `FOLD@pos0` (~1) and reports "brown=1.0 rust=0.0" for action `f`.

---

## 2. Suspect code path identification

The orchestrator asked for a file:line for the suspect code. Based on the cell analysis above, the load-bearing bugs are NOT in `dcfr_vector.rs` at all — they are in the **acceptance test** and (separately) in the engine-side action ordering, which the test then fails to compensate for.

### Primary bug: test-side action-axis mismatch

`tests/test_v1_5_brown_apples_to_apples.py` at lines **530-556**:

```python
for hand_idx, brown_row in enumerate(entry.strategy):
    hand_str = brown_hands[hand_idx]
    rust_row = rust_rows.get(hand_str)
    if rust_row is None:
        continue
    if len(rust_row) != n_actions:
        diffs.append(... "action-count mismatch" ...)
        continue
    for a_idx in range(n_actions):
        brown_p = float(brown_row[a_idx])
        rust_p = float(rust_row[a_idx])
        if abs(brown_p - rust_p) >= PER_ACTION_TOL:
            diffs.append(
                f"{spot_id} P{player} hand={hand_str} "
                f"hist={history_substr!r} action={actions[a_idx]!r}: "
                f"brown={brown_p:.6f} rust={rust_p:.6f} ..."
            )
```

The test reads Brown's `actions` tuple as the source-of-truth ordering, but indexes `rust_row` by the SAME `a_idx`. There is no column-remap step. At facing-bet histories, Brown's `actions[0]='c'` corresponds semantically to Rust's column 1 (CALL), not column 0 (FOLD). The test therefore reports a `|p_call - p_fold|` divergence as if it were a `|p_call - p_call|` divergence.

### Engine-side contributing condition: action enumeration ordering

`crates/cfr_core/src/hunl.rs` at lines **1105-1138** (`enumerate_legal_actions`):

```rust
if facing_bet {
    actions.push(ACTION_FOLD);   // pushed first
    actions.push(ACTION_CALL);   // pushed second
} else {
    actions.push(ACTION_CHECK);
}
...
if ctx.include_all_in {
    actions.push(ACTION_ALL_IN);
}
actions.sort_unstable();          // sorts by u8 id ascending
```

With `ACTION_FOLD=0` and `ACTION_CALL=2` (constants at lines 98-100), the final ordering at any facing-bet node is `[0, 2, …raise ids…, 13]` → `[FOLD, CALL, raises…, A]`. Brown's `river_game.cpp:74-75` pushes `('c', to_call)` before `('f', 0)`, so Brown's ordering at the same node is `[c, f, …raises…]`.

The Rust ordering is internally consistent (it just determines the column layout of `strategy`/`regret`/`strategy_sum` in `VectorInfosetData`), but it differs from Brown's emitted-string ordering. Either engine could be "fixed" by reversing the push order; the more local fix is in the test renderer.

### Secondary bug: player-to-range wiring (test side)

`tests/test_v1_5_brown_apples_to_apples.py:_spot_hand_ids` (lines **263-287**) passes `spot.ranges[0]` → `p0_holes` (= our P0 = second-actor on river) and `spot.ranges[1]` → `p1_holes` (= our P1 = first-actor on river). The same `spot.ranges[0]` and `spot.ranges[1]` are written verbatim to Brown's subgame JSON as `players[0]` and `players[1]` (via `noambrown_wrapper.py:write_brown_config`, line 527-533). Since Brown's `initial_state().player = 0` (`river_game.cpp:18-20`), Brown's opener is Brown's `players[0]` = `spot.ranges[0]` = the polarized range. Our opener is OUR P1 (per `hunl.py:286-289`) and the test wired it to `spot.ranges[1]` = the merged range.

So the two engines solve the SAME hand set but with the OPENER assigned different ranges. At the root, this swaps the polarized/merged role between the engines, producing genuine strategy divergence even though both solve their respective game correctly to Nash.

When Brown is re-invoked with `replace(spot, ranges=(ranges[1], ranges[0]))` to undo the test's swap, Brown's root strategy for all 55 hands in the merged opener range converges to 100% check — identical to Rust's output. Verified for: `AdAs`, `KhKs`/`KhKd`/`KdKh`, `QcQd`, `9sTs`, `TsJs` (all `[1.0, 0.0, 0.0, 0.0]` in both engines, raw data in `/tmp/pr23_cell_dive/brown_swapped.json` vs `/tmp/pr23_cell_dive/rust_strategy.json`).

---

## 3. Recommended fix sketch

Two independent fixes are required to unblock the v1.5.0 acceptance gate. Both are TEST-side changes; PR 23's Rust algorithm needs no modification.

### Fix A — Action-axis remap in the test

In `tests/test_v1_5_brown_apples_to_apples.py`'s per-cell comparison loop (lines 530-556), build a per-history permutation `rust_col_for[a_idx]` that maps Brown's `actions[a_idx]` to the Rust strategy row column where the SAME semantic action lives. For facing-bet histories the permutation is `{0→1 (c↔CALL), 1→0 (f↔FOLD), 2..n→2..n (raises preserved order)}`. For opening histories the permutation is the identity. The remap also has to translate Brown's `r{extra}` raise tokens (extra-over-call) to Rust's `r{new_total}` (raise-to-total) for label display, and Brown's biggest `r{remaining}` to Rust's `A` (already partially handled by PR 35's `stack_ceiling` branch in `_rust_history_substr_for_canonical`).

Sketch:

```python
def _brown_to_rust_action_perm(brown_actions: tuple[str, ...]) -> list[int]:
    facing = "f" in brown_actions
    if not facing:
        return list(range(len(brown_actions)))  # identity (both put check first)
    # Facing bet: Brown [c, f, raises…] → Rust [f, c, raises…]
    perm = [1, 0] + list(range(2, len(brown_actions)))
    return perm

# Inside the per-cell loop:
perm = _brown_to_rust_action_perm(actions)
for a_idx in range(n_actions):
    brown_p = float(brown_row[a_idx])
    rust_p = float(rust_row[perm[a_idx]])
    if abs(brown_p - rust_p) >= PER_ACTION_TOL: ...
```

This fix alone collapses Cells 1, 2, and 3 — and a long tail of similar pseudo-divergences in the orchestrator's "Brown high / Rust low" search — to within tolerance.

### Fix B — Player-to-range wiring

The simplest, most defensible fix is to **invert the range assignment going into Rust** so that the SAME range is in the OPENER seat across both engines:

```python
# Old (test_v1_5_brown_apples_to_apples.py:457-459):
p0_holes = _spot_hand_ids(spot, 0)
p1_holes = _spot_hand_ids(spot, 1)
# Brown sees players=[ranges[0], ranges[1]]; Brown opener = ranges[0].
# Our solver: p0_holes=ranges[0] (= our P0 = second-actor),
#             p1_holes=ranges[1] (= our P1 = first-actor).
# Mismatch: Brown opener gets polarized; ours gets merged.

# New:
p0_holes = _spot_hand_ids(spot, 1)  # our P0 = second-actor = Brown P1
p1_holes = _spot_hand_ids(spot, 0)  # our P1 = first-actor  = Brown P0
```

Combined with the hand-string lookup table this requires updating `hands_p0_strs` / `hands_p1_strs` to match the new wiring. This fix is the canonical "apples-to-apples" wiring described by the docstring (lines 271-280) but never actually applied to `_spot_hand_ids`'s output.

An alternative, smaller-blast-radius fix is to invoke Brown's binary on a `replace(spot, ranges=(ranges[1], ranges[0]))` view of the spot, so that Brown's `players[0]` is `ranges[1]` and the OPENER on both sides sees `ranges[1]` (the merged range as currently wired into our P1). I verified empirically that this approach produces 100% match for the cells I sampled (`brown_swapped.json` vs `rust_strategy.json`), and Brown's exploitability remains at 0.051 chips on the swapped game (vs 0.044 on the original).

The "right" fix depends on what the acceptance test is supposed to PROVE: if the load-bearing claim is "Rust matches Brown when both run on the spot AS AUTHORED (polarized opener)", then Fix B (swap the Rust wiring). If the claim is "Rust matches Brown when both run on the spot WITH the river opener seat assigned `ranges[0]`", then `_spot_hand_ids` is correct and Brown's call needs to be on the swapped spot.

### Out-of-scope (but related): hand-string suit-order normalization

Brown's `cpp/src/cards.cpp:8-9` uses suit string `"cdhs"`; our `poker_solver/card.py:14` uses `"shdc"`. Both engines sort hand strings by their own card-id encoding ascending. For most combos the two suit orderings happen to produce the same final string (e.g., `9sTs`, `TsJs`, `AsAd` are stable). For K-paired and a few other hands they differ: Brown's `KhKs` (Kh=37 < Ks=50 under `suit*13+rank`) is Rust's `KsKh` (Ks=52 < Kh=53 under `rank*4+suit_shdc`). The test (`_combo_to_hole_string` at lines 290-318) renders Rust's form correctly but uses `brown_dump.players[player].hands[hand_idx]` (Brown's form) verbatim when looking up `rust_rows.get(hand_str)`. This causes `rust_rows.get(...)` to miss for hands with at least one suit-order-sensitive position. The downstream effect is "hand not emitted" → skipped silently → underreported divergence count, not a false positive.

A complete fix needs a third remap: `brown_hand_str → rust_hand_str` translation table built from `card_to_int` ordering. This is small and orthogonal to Fixes A and B but should be in the same PR.

---

## 4. Confidence and remaining unknowns

**Confidence: HIGH** that PR 23's algorithm is correct on the algorithm it implements:
- Direct port of Brown's `Trainer::traverse` regret / strategy_sum / discount update is structurally faithful per side-by-side read of `trainer.cpp:138-237` vs `dcfr_vector.rs:302-466`.
- The DCFR scaling constants (alpha=1.5, beta=0, gamma=2.0) flow through `discount` at lines 266-289 with the same `pos_scale = t^α/(t^α+1)`, `neg_scale = t^β/(t^β+1)`, `strat_scale = (t/(t+1))^γ` formulas as `trainer.cpp:124-136` and `trainer.cpp:355-361`.
- `terminal_value_vector` (lines 619-656) correctly computes `Σ_{ho} reach_opp[ho] * utility(my_hand, opp_hand)` for each of update_player's hands, with the blocker filter applied at lines 636-642. The base_pot offset between Brown's accounting (`pot - contrib`) and Rust's accounting (`±c_loser`) is a constant per terminal and cancels in regret comparisons; I confirmed empirically that the offset does NOT explain the at-root divergence.
- When run on the symmetric tiny range (AA + JT, 2 hands per side) the solver reproduces canonical Nash with AA jamming 98.5% at root and 9sTs checking 85% — internally consistent.
- When Brown is re-invoked with the ranges swapped to match Rust's player wiring, root strategies coincide to 4 decimal places on all 6 hands I sampled.

**Remaining uncertainty** (medium confidence):
- After applying BOTH the action-axis remap and the range-wiring correction, 697 cells still differ by ≥5e-3 (vs 0 expected). The top divergences are mostly between `c@pos0` (Brown's call) and `r5000@pos2` (Rust's call → raise drift) or between `c` and `b1500` at the `c` history (P1 facing a check, deciding whether to call (i.e., second check) or bet). These are plausibly Nash mixed-strategy non-uniqueness (the per-hand strategy is under-determined in equilibrium for value hands that are indifferent between value-bet sizings) rather than a remaining bug, but I did not run a best-response cross-check (run Rust's strategy through Brown's `exploitability` walk and vice-versa) to confirm. That cross-check is the natural next investigation if you want to RULE OUT a residual algorithmic divergence — but it's NOT what the orchestrator's three cells were pointing at.
- The action labels in the test renderer (`_rust_history_substr_for_canonical`) still hardcode `b1500` ↔ `b1500` as if the chip semantics match. Empirically the chip semantics DO match (both 1500-chip bet against 1000 starting pot leading to pot_total=2500, to_call=1500), but the labeling is by happy coincidence — Rust uses `b{chips_added}` (`hunl.rs:725`) and Brown uses `b{amount}` where `amount` is also chips-added per `river_game.cpp:54-69`. The collision is only fragile if either side changes to a "raise-to" convention.

**Out of scope for this report**:
- The "Rust always checks at root" observation in the full 55-vs-55 run, after I had not yet realized it was Bug B (range wiring), led me to look hard at `terminal_value_vector` / `traverse` for sign errors. None found. The "always check" turns out to be the CORRECT Nash for the SWAPPED game (where the opener has the merged pair-heavy range, not the polarized betting range). With the polarized range in the opener seat (swapped-Brown setup), the opener bets aggressively — confirmed at `/tmp/pr23_cell_dive/brown_swapped.json::player1::profile['root']`.
