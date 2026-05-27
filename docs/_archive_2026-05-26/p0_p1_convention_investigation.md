# P0/P1 convention investigation (Site 3 follow-up)

**Date**: 2026-05-24
**Scope**: READ-ONLY diagnosis of the player-index seam between Brown's
solver and our solver in the apples-to-apples diff harness.
**Verdict**: **BUG-FOUND-PR-55-NEEDED**

---

## Phase 1 — Convention claims verified

### Brown's convention (CONFIRMED)
- `references/code/noambrown_poker_solver/cpp/src/river_game.cpp:10` —
  `struct State { int player = 0; ... }`. The root river-open state has
  Brown's `player = 0`, so Brown's player 0 is the first-to-act on the
  river.
- `cpp/src/main.cpp:669-675` — `subgame.players[0].hands` is loaded into
  `config.ranges[0]`, which `RiverGame` uses as `hands[0]` for player 0.
  → Brown's `players[0]` in input JSON ⇔ Brown's player 0 in the tree
  ⇔ first-to-act on river.
- `cpp/src/main.cpp:231-289` — `write_strategy_json` emits
  `"players":[...]` indexed `for (int player = 0; player < 2; ++player)`
  using the same `player` axis as the tree. So Brown's output
  `players[0]` ⇔ first-to-act strategy.

### Our convention (CONFIRMED)
- `poker_solver/hunl.py:789` (`_after_board_dealt`) — when both players
  have acted preflop and the board street opens with no all-in,
  `cur_player=1`. → on a symmetric river open, OUR P1 acts first.
- `poker_solver/hunl.py:425-429` — subgame builder for symmetric
  contributions (`c0 == c1`) sets `postflop_first_actor = 1`. Same rule
  applies for the river subgame fixtures (which all use symmetric
  initial contributions `pot // 2` each).
- `poker_solver/parity/noambrown_wrapper.py:802` — `_state_for_history`
  initializes the walk with `actor=1`, matching the engine's first-actor
  convention.

### Mapping
Both claims are verified. **Brown's player 0 ⇔ our player 1** on the
river open. Brown's player 1 ⇔ our player 0.

---

## Phase 2 — Comparator analysis

### Range assignment to each solver
- `poker_solver/parity/noambrown_wrapper.py:527-533` (`write_brown_config`)
  writes `spot.ranges[i]` straight to Brown's input `players[i]` slot —
  **no swap**.
- `tests/test_v1_5_brown_apples_to_apples.py:457-468` (`_spot_hand_ids`)
  passes `spot.ranges[0]` as `p0_holes` and `spot.ranges[1]` as
  `p1_holes` to the Rust solver — **no swap**.
- `crates/cfr_core/src/dcfr_vector.rs:558-566, 591-600` — `p0_holes` go
  into `hole[0]` (our player 0's slot), `p1_holes` into `hole[1]`.

### What each side does with `spot.ranges[0]`
- **Brown side**: `spot.ranges[0]` → Brown's `players[0]` → Brown's
  first-to-act on river.
- **Our side**: `spot.ranges[0]` → our P0 → our **second**-to-act on
  river.

So the SAME hand list is given to two SEMANTICALLY DIFFERENT seats. The
acceptance test acknowledges this in the docstring at
`tests/test_v1_5_brown_apples_to_apples.py:271-280`:

> "We pass spot.ranges[0] as `p0_holes` (= our P0, second-to-act on
> river) and spot.ranges[1] as `p1_holes` (= our P1, first-to-act on
> river) so the Rust hand vector is interpretable the same way the spot
> itself is authored."

This is correct as a *literal description* of what the code does. It is
NOT a normalization that resolves the convention mismatch.

### The diff loop
`tests/test_v1_5_brown_apples_to_apples.py:515-521`:

```python
for player in (0, 1):
    brown_profile = brown_dump.players[player].profile
    ...
    rust_rows = rust_lookup.get((player, history_substr))
```

`rust_lookup` is keyed by `(player_int, history)` where `player_int = 0`
iff the hole string is in `hands_p0_strs = spot.ranges[0]` (line 407-408).

So `player=0` pulls **Brown's first-actor strategy** AND **our P0's
strategy (= our second-actor)**. **No swap is applied anywhere.**

`tests/test_river_diff.py:400-405` has the identical pattern:

```python
for player in (0, 1):
    brown_profile = brown_dump.players[player].profile
    ...
    our_player_matrix = our_matrix[history].get(player)
```

### Cross-check with the apples doc
`docs/brown_apples_to_apples_2026-05-23.md:103-132` was written with a
DIFFERENT scaffolding (the `range_aggregator` path with
`hero_player=1`), which DOES apply the swap correctly: hero is placed
into our slot 1 via `hero_player=1` so that hero ends up first-to-act
in our engine, matching Brown's player 0. The 2026-05-23 ad-hoc
experiment in that doc compared `brown_dump.players[0]` against our
P1 strategy via that mapping. That experiment is unaffected.

The bug is specifically in the **direct vector-form diff** tests
(`test_v1_5_brown_apples_to_apples`, `test_river_diff`) which bypass
the aggregator and pass `spot.ranges` to both solvers without remapping.

---

## Phase 3 — Empirical sanity check (K72)

K72 fixture (`tests/data/river_spots.json`, `dry_K72_rainbow`):
- `players[0]`: 55 combos including K8s (Kc8c/Kd8d/Kh8h), K9s,
  small/mid suited connectors (9c8c, 6c5c, 5d4d), Tc8c etc. — has
  **bluff candidates**.
- `players[1]`: 55 combos heavy on pocket pairs (Q, T, 9, 8, 5, 3 +
  AA, KK) plus AK + JTs + T9s. **Polarized to value / no air**.

These ranges are markedly asymmetric in composition — exactly the
condition where the swap surfaces.

Worst diff cells from `docs/v1_6_1_dryrun_attempt_2.md:130-136`:

| Hand | Action | Brown | Rust | \|diff\| |
|---|---|---|---|---|
| 8hKh (K8s) | c (check) | 0.875 | 0.454 | 4.22e-1 |
| 8dKd (K8s) | c (check) | 0.870 | 0.455 | 4.16e-1 |
| 9hKh (K9s) | c (check) | 0.839 | 0.442 | 3.97e-1 |
| 9dKd (K9s) | c (check) | 0.827 | 0.444 | 3.83e-1 |

**Critical observation**: `K8s` (Kc8c/Kd8d/Kh8h) appears in
`players[0]` only — NOT in `players[1]`. So this cell's reported diff is
between:
- `brown_dump.players[0]` strategy for K8s (Brown's first-actor with
  K8s = top pair) — a check-heavy strategy makes sense.
- `rust_lookup[(0, ...)]` strategy for K8s (our P0 with K8s = our
  second-to-act). When we are second-to-act, K8s is a strong showdown
  hand we want to keep face-up: also check-heavy, but with a different
  bet-defense profile (we close the action by calling-or-raising rather
  than opening the betting).

The 42pp gap is exactly the kind of role-vs-role discrepancy a
position swap produces: same range card but PLAYED IN A DIFFERENT
SEAT.

This is consistent with — but does not by itself prove — the swap
hypothesis. A definitive empirical test would re-run the diff with
the swap applied and check whether the 4.22e-1 gap collapses to near
zero. That experiment is in scope for the rectification PR, not this
read-only diagnosis.

---

## Phase 4 — Recommended fix

### Mismatch confirmed: YES

### Fix recommendation (option B, wrapper-layer remap — cleanest)

Apply the swap at the boundary between Brown's player indexing and our
player indexing, in **one** place: the BrownStrategyDump construction
in `poker_solver/parity/noambrown_wrapper.py:_parse_brown_dump` (around
lines 681-734).

After parsing Brown's JSON into `parsed_players[0]` and
`parsed_players[1]`, **swap the order** when constructing the
`BrownStrategyDump`:

```python
# Brown indexes players by their own convention (player 0 = first-actor
# on river). Our solver indexes by ours (player 1 = first-actor on
# river). Remap at the boundary so callers can use our-convention
# indexing consistently.
players=(parsed_players[1], parsed_players[0]),
```

**Pros**: callers (`test_v1_5_brown_apples_to_apples.py`,
`test_river_diff.py`, plus the `our_strategy_to_brown_matrix` and any
future consumers) need NO awareness of the convention gap. The
seam is sealed at one point. The downstream diff loop
`for player in (0, 1): brown_dump.players[player] vs our[player]` then
compares same-role strategies.

**Cons**: This changes the semantics of `BrownStrategyDump.players`
silently. Callers that DELIBERATELY operate in Brown's convention
(the apples-to-apples doc's `players[0] = first-actor` reading at
`docs/brown_apples_to_apples_2026-05-23.md:114`) would break. Mitigate
by:
- Renaming the dump fields (`first_actor`, `second_actor`) OR
- Adding a `convention` field documenting which convention applies, OR
- Leaving the field name but updating the docstring + all docs.

### Alternative fix (option A, comparator-side swap)

At each diff site, pull `brown_dump.players[1 - player]` when
indexing with our `player`. Three known sites:
- `tests/test_v1_5_brown_apples_to_apples.py:515-521`
- `tests/test_river_diff.py:400-405`
- `poker_solver/parity/noambrown_wrapper.py:1124-1156` (the
  `our_strategy_to_brown_matrix` function — needs a similar audit; if
  it indexes Brown's `player_idx` against our matrix, it has the same
  bug).

**Pros**: leaves the `BrownStrategyDump` semantics untouched (Brown's
players[0] STAYS Brown's first-actor). No callers break.

**Cons**: each new diff/comparator site must remember to apply the
swap. Easy to forget on subsequent additions.

### Recommended scope

**Option B preferred** — single boundary swap. With supporting
changes:
1. Rename `BrownStrategyDump.players` axis or add explicit
   `first_actor` / `second_actor` properties.
2. Audit `our_strategy_to_brown_matrix` and any other consumer.
3. Update `docs/brown_apples_to_apples_2026-05-23.md` and the suit-
   encoding hazard hunt doc to reflect the new convention.
4. Add a unit test that constructs an asymmetric two-side fixture and
   asserts that the diff collapses (e.g., set `spot.ranges[0]` = pure
   nuts and `spot.ranges[1]` = pure air on a paired board, then verify
   the comparator's reported player matches the strategy semantics).

### Estimated impact on dry-run #2

- K72 max diff is currently **4.22e-1** on K8s/K9s in `players[0]`.
  After the swap, those cells become a same-role comparison and should
  collapse toward equilibrium-level noise (~1e-3 if Rust's CFR is
  Brown-equivalent at the algorithm level).
- A83 max diff is currently **2.71e-1** on `3sAs` at `b1000r4500`. Same
  expectation.
- If the swap collapses the diffs to <1e-2, the deep-cap divergence
  hypothesis in `docs/v1_6_1_dryrun_attempt_2.md:210-215` is
  **partially refuted** — the deep-cap nodes were never actually
  divergent; they were apples-to-oranges.
- If the swap collapses the surface to <1e-2 but the deep cap residual
  persists at >5e-2, both bugs are real and need separate fixes.

This is the kind of layered uncertainty that justifies a measured
instrument-and-revisit approach (per the "Don't extrapolate" memo).
**Do not** assume the swap fully resolves K72/A83 until measured.

---

## Phase 5 — Action items for PR 55

1. Implement option B in `_parse_brown_dump`.
2. Audit `our_strategy_to_brown_matrix` for the same bug; fix if
   present.
3. Update both diff harnesses (`test_v1_5_brown_apples_to_apples.py`,
   `test_river_diff.py`) to remove the now-redundant convention
   acknowledgements in docstrings and to add a positive assertion
   that they compare same-role strategies.
4. Add an asymmetric-fixture unit test that proves the swap is correct
   (e.g., nuts-vs-air on a paired board with a single hand per side —
   the first-actor should have a deterministic bet-or-check strategy
   that is invariant under the swap).
5. Re-run dry-run #2 and report the post-swap divergence. If
   K72/A83 now pass at 5e-3, ship; if not, surface the residual as a
   separate issue.

**Prerequisite fixes**: Sites 1-2 (suit encoding) must be fixed before
this audit's empirical claims can be fully trusted — currently the
hand-string mismatches mask many cells via the `if rust_row is None:
continue` skip. PR 55 should bundle the suit fix with the player
swap.
