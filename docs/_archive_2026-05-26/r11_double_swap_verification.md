# R11 Double-Swap Verification — Independent Empirical Check

**Date**: 2026-05-24
**Method**: Run K72 (dry_K72_rainbow) under all 4 swap configurations.
**Iterations**: 500 (matches hypothesis doc's evidence level); CONFIG B
also re-run at 2000 iters to disambiguate convergence noise.
**Spot**: `dry_K72_rainbow` (board `Ks 7h 2d 4c Jh`, pot 1000, stack 9500;
55 combos per range).
**Worktree**: `/tmp/r11_verify_83431/` (isolated; READ-ONLY on repo code).

---

## Phase 1 — Per-PR what-it-does at the boundary

### PR 40 (`tests/test_v1_5_brown_apples_to_apples.py`, lines 578-584 in bundle)

```python
# Fix B (PR 40): Brown's P0 = opener; Rust's P1 = opener
# (`poker_solver/hunl.py:286-289`). To put the SAME range in each
# engine's opener slot, Rust P1 gets the opener range (spot.ranges[0])
# and Rust P0 gets the defender (spot.ranges[1]). Brown-player →
# Rust-player crossing is handled below via `rust_player = 1 - brown_player`.
p0_holes = _spot_hand_ids(spot, 1)  # Rust P0 = defender = ranges[1]
p1_holes = _spot_hand_ids(spot, 0)  # Rust P1 = opener = ranges[0]
```

**Effect**: Swaps which range slot is passed to which Rust solver slot.
Rust's first-actor (P1 per `hunl.py:429: postflop_first_actor=1`) receives
`ranges[0]`. Rust's second-actor (P0) receives `ranges[1]`.

**Per PR 40 commit message**: "Swap so the SAME range lives in each
engine's opener slot." (commit `988c3fc`)

### PR 55-ext (`poker_solver/parity/noambrown_wrapper.py:660-677` in bundle)

```python
# PR 55 extension: swap range slots at the wrapper boundary so
# Brown's player 0 (first-actor) receives our first-actor's range.
brown_player_ranges = (spot.ranges[1], spot.ranges[0])
config: dict[str, Any] = {
    ...
    "players": [
        {"hands": [_combo_to_brown_hand_str(combo) for combo, _ in player_range],
         "weights": [float(w) for _, w in player_range]}
        for player_range in brown_player_ranges
    ],
}
```

**Effect**: Swaps which range slot is written into Brown's input JSON.
Brown's native player[0] (first-actor on river per Brown's
`cpp/src/river_game.cpp:10`) receives `spot.ranges[1]`. Brown's
player[1] receives `spot.ranges[0]`.

**Per PR 55-ext commit** (`848723c`): Justifies the swap based on the
wrapper docstring's claim that `spot.ranges[0]` = our P0 = second-to-act
on river.

### Same logical channel?

**Yes — both swap the same logical channel** (range slot → first-actor's
solver input):
- PR 40 swaps the channel on Rust's side: `ranges[0]` → Rust first-actor.
- PR 55-ext swaps the channel on Brown's side: `ranges[1]` → Brown first-actor.

When BOTH are applied: Rust first-actor trains on `ranges[0]`, Brown
first-actor trains on `ranges[1]`. Different ranges → different games →
structural disagreement (R11 manifests).

When NEITHER is applied: Brown first-actor trains on `ranges[0]`
(default), Rust first-actor trains on `ranges[1]` (default).
Different ranges → different games → structural disagreement (mirror of R11).

When EITHER ONE is applied: both first-actors end up on the SAME range.

---

## Phase 2 — Empirical results, 4 configurations on K72

Script: `/tmp/r11_verify_83431/verify.py`. Reads Brown's strategy.json
directly (bypassing the wrapper's PR 55 output swap), extracts AA at the
root infoset (Brown's `"root"` key in `players[0].profile`; Rust's
empty-history entries under `'<hand>|<board>|r|'`).

### Brown's first-actor (native players[0]) AA strategy at root

| Config | Brown input swap (PR 55-ext) | Brown first-actor's range | Brown AA[0] avg (over 6 AA combos) | Brown expl (500 iter) |
|---|---|---|---|---|
| A=BOTH    | YES (= ranges[1]) | condensed/value (KK, AA, QQ, TT, ...) | `[1.0, 0.0, 0.0, 0.0]` (pure check) | 0.730 |
| B=ONLY_PR40 | NO (= ranges[0])  | polarized/bettor (KK, busted draws, ...) | `[0.0007, 0.5559, 0.4433, 0.0]` (mixed bet) | 0.602 |
| C=ONLY_PR55ext | YES (= ranges[1]) | condensed/value | `[1.0, 0.0, 0.0, 0.0]` (pure check) | 0.730 |
| D=NEITHER | NO (= ranges[0])  | polarized/bettor | `[0.0007, 0.5559, 0.4433, 0.0]` (mixed bet) | 0.602 |

### Rust's first-actor (P1) AA strategy at root

| Config | Rust test swap (PR 40) | Rust first-actor's range | Rust AA[0] avg (over 6 AA combos) |
|---|---|---|---|
| A=BOTH    | YES (p1_holes=ranges[0]) | polarized/bettor | `[0.0069, 0.6596, 0.3336, 0.0]` (mixed bet) |
| B=ONLY_PR40 | YES (p1_holes=ranges[0]) | polarized/bettor | `[0.0069, 0.6596, 0.3336, 0.0]` (mixed bet) |
| C=ONLY_PR55ext | NO (p1_holes=ranges[1]) | condensed/value | `[1.0, 0.0, 0.0, 0.0]` (pure check) |
| D=NEITHER | NO (p1_holes=ranges[1]) | condensed/value | `[1.0, 0.0, 0.0, 0.0]` (pure check) |

### L1 distance (Brown first-actor avg vs Rust first-actor avg, 500 iters)

| Config | L1 distance | Verdict |
|---|---|---|
| A=BOTH    | **1.99** | STRUCTURAL DIVERGE (Brown=pure-check, Rust=mixed) |
| B=ONLY_PR40 | 0.22 | minor mix-ratio noise (same game, slow convergence on bettor's polarized range) |
| C=ONLY_PR55ext | **0.00** | EXACT AGREEMENT |
| D=NEITHER | **2.00** | STRUCTURAL DIVERGE (Brown=mixed, Rust=pure-check; mirror of A) |

### CONFIG B at 2000 iters (to disambiguate noise vs structure)

At 2000 iters, Brown's exploitability drops to 0.044 chips. Brown's AA
per-combo strategy:
- `AhAs, AdAs (no-club AA)`: `[0, 0.01, 0.99, 0]` — pure b1500
- `AcAs (has-club AA)`: `[0, 0.99, 0.01, 0]` — pure b750

Rust's AA per-combo strategy at 2000 iters:
- `AdAc, AhAc, AhAd (no-spade AA)`: `[0, 0.05, 0.95, 0]` — mostly b1500
- `AsAc, AsAd, AsAh (has-spade AA)`: `[0, 0.98, 0.02, 0]` — mostly b750

Both engines converge to the same QUALITATIVE Nash structure (split
AA combos into two equivalence classes, one bets b1500, the other bets
b750) but cluster combos by different suit conventions (Brown uses
`cdhs` ordering; Rust uses `shdc` ordering). This is **Nash polytope
multiplicity caused by internal suit-canonicalization differences** —
NOT R11. It's the kind of cosmetic divergence the v1.5.0 `PER_ACTION_TOL=2e-2`
was loosened to absorb.

So CONFIG B's L1=0.22 at 500 iters is convergence noise plus
suit-multiplicity, not structural disagreement.

---

## Phase 3 — Diagnosis confirmed

**Confirmed: YES.** The R11 "engine bug" surfaced at the K72 root for AA
is fully explained by the test-harness double-swap. Both engines are
algorithmically converging; they are simply being fed opposite range
assignments under config A.

The hypothesis doc's broader claim (`docs/r11_brown_convergence_hypothesis.md`)
held on the A83 spot it tested. My independent K72 run reproduces the
same pattern on a different fixture: BOTH = wrong, EITHER ONE = right.

The hypothesis doc's prediction "WITHOUT BOTH = correct" was slightly
inaccurate. Empirically NEITHER (config D) also diverges, mirror-image
to BOTH (config A). The correct rule is: **exactly ONE swap (PR 40 or
PR 55-ext, not both, not neither) yields the SAME GAME on both engines**.

---

## Phase 4 — Recommended revert

### Per the corrected audit (`docs/poker_spots_audit_CORRECTED_2026-05-23.md`)

The audit's authoritative labeling: **"P0 = villain = bettor"**.
- For dry_K72: P0's range contains busted draws (KK, K-8s, QTs, T9s,
  98s, 65s, 54s, T8s, A5s, A4s) — the polarized bettor range.
- P1's range contains AA/QQ/TT/99/etc. — the condensed defender range.

So **`spot.ranges[0]` = bettor's range = first-actor's range** in the
fixture-authoring convention.

### Each PR's compatibility with the audit's canonical labeling

| PR | What it asserts about `ranges[0]` | Matches audit? |
|---|---|---|
| **PR 40**     | `ranges[0]` = opener = first-actor → Rust's P1 (first-actor) gets `ranges[0]` | **YES** |
| **PR 55-ext** | `ranges[0]` = our P0 = second-actor → Brown's player[0] (first-actor) gets `ranges[1]` | **NO** |

PR 55-ext's docstring at `noambrown_wrapper.py:634-643` (bundle) cites
"`poker_solver/hunl.py:425-429` and `hunl.py:789`" — but those are
references to OUR engine's run-time convention (where our P0 happens to
be the second-actor postflop), NOT the fixture-authoring convention.
Confusing those two levels is the root error.

### Recommendation: **REVERT PR 55-ext**

Keep PR 40 (the test-side swap), revert PR 55-ext (the wrapper-side
input swap). This yields CONFIG B:

- Brown's native player[0] (= Brown's first-actor) trains on `ranges[0]`
  (the bettor's polarized range) — matches the audit's canonical
  labeling.
- Rust's P1 (= our first-actor on river) trains on `ranges[0]` (via
  PR 40's swap) — matches the audit's canonical labeling.
- Both engines solve the same game.

CONFIG C (only PR 55-ext, no PR 40) also yields agreement (and at 500
iters shows perfect 0.0 L1 distance because the resulting game has a
trivial AA→pure-check Nash). But CONFIG C trains both engines on the
DEFENDER's range as the first-actor — which is the wrong game per the
fixture-authoring convention.

### Action items for fixing the bundle

1. **REVERT** the input-side swap in `write_brown_config` (lines 660-664
   in bundle / lines 660-664 in `848723c`). After revert: `for player_range
   in spot.ranges` (no `brown_player_ranges` alias).
2. **KEEP** the test-side swap from PR 40 (lines 583-584 of bundle test).
3. Update wrapper docstring at lines 634-658 to reflect the audit
   convention: `spot.ranges[0]` = the bettor's range = first-actor's
   range = Brown's player[0] = our P1.
4. (Independent concern, NOT in scope of this verification): audit
   whether PR 55 (output swap at `_parse_brown_dump` line 909) is
   compatible with the bundle test's `rust_player = 1 - brown_player`
   crossing. The bundle test's comment treats `brown_dump.players[0]`
   as "Brown's first-actor / opener" which assumes PR 55 output swap is
   NOT active. If PR 55 IS active in the bundle (it is), the role
   crossing is double-applied and the comparison may be silently
   miscompared in some PRs / configurations. This is a follow-up
   diagnosis, not part of R11 directly.

### Action items for main

Main is currently in CONFIG D (neither swap), which my empirical results
show ALSO diverges structurally. Main never had a passing acceptance run
on this fixture — the R11 problem predates the bundle.

To bring main to a working state (CONFIG B), land the test-side swap
(PR 40) on main without applying PR 55-ext.

---

## Files referenced (absolute paths)

- `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py` (MAIN: config D, no swap)
- `/private/tmp/bisect-c-bundle-75843/tests/test_v1_5_brown_apples_to_apples.py` (BUNDLE: PR 40 swap at L583-584)
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` (MAIN: no input swap at write_brown_config)
- `/private/tmp/bisect-c-bundle-75843/poker_solver/parity/noambrown_wrapper.py` (BUNDLE: PR 55-ext input swap at L660-664, PR 55 output swap at L909)
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py:418-429` (`postflop_first_actor = 1` proof: our P1 acts first on river)
- `/Users/ashen/Desktop/poker_solver/docs/poker_spots_audit_CORRECTED_2026-05-23.md` (canonical P0=villain=bettor)
- `/Users/ashen/Desktop/poker_solver/docs/r11_brown_convergence_hypothesis.md` (prior diagnosis)
- `/tmp/r11_verify_83431/verify.py` (this verification's empirical script)
- `/tmp/r11_verify_83431/results.json` (raw 500-iter results across all 4 configs)
- `/tmp/r11_verify_83431/verify_b_2000.py` (CONFIG B re-run at 2000 iters)

---

## Verdict

**Double-swap diagnosis confirmed.** R11's "depth-0 root engine
disagreement on AA at K72" is fully explained by PR 40 and PR 55-ext
simultaneously swapping the same logical channel (range slot → first-actor's
training data). Both swaps independently make sense relative to their
authoring claim; together they over-correct.

**Recommended revert: PR 55-ext** (the wrapper input swap). This
preserves the audit's canonical `ranges[0] = villain = bettor =
first-actor` convention and keeps PR 40 (which already matches that
convention).
