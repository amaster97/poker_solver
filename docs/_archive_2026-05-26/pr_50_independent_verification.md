# PR 50 Independent Verification — phantom-ALL_IN fix impact

**Date:** 2026-05-24
**Mode:** READ-ONLY analysis. No code modified. No sub-agents spawned.
**Trigger:** Pre-PR-50 sanity check on the diagnosis that "phantom ALL_IN
at facing-all-in nodes (`stack <= to_call`) explains the 22-42pp
K72/A83 divergence in dry-run #2."

---

## Verdict: DIAGNOSIS-PARTIAL (lean WRONG for K72's worst cells)

Confidence: **MEDIUM**.

Top-line: the proposed `stack > to_call` guard ELIMINATES action-count
mismatches (the 6 cases at facing-all-in nodes) and will likely close a
visible slice of the 5e-2 divergence cells via upstream-propagation, but
**will NOT** close the K72 42pp worst cells at top-pair-K hands. Those
worst cells are at NON-facing-all-in nodes where action counts already
match — `action_menu_topology_audit.md §6` explicitly admits this and
attributes the residual to Brown's terminal-utility convention divergence
(candidate (d) in `a83_deep_cap_root_cause_investigation.md`).

---

## Phase 1: phantom-ALL_IN sites in K72 tree (post-PR-35c)

K72 fixture: `pot=1000, stack=9500, bet_sizes=[0.75, 1.5], max_raises=3,
half-pot contribs=[500, 500]`. PR 35c (cap-guard) is in the dry-run #2
bundle, so cap-reached phantom sites are CLOSED. Remaining phantom sites
must satisfy: `facing-bet, not cap-reached, stack <= to_call`.

Enumerated facing-all-in nodes (Brown emits [c, f], Rust emits
[FOLD, CALL, ALL_IN]):

1. `b9500` (P1 root jam) — P0 facing-all-in, stack=9500=to_call
2. `xb9500` (P1 check, P0 jam) — symmetric
3. `b750r10000` (P1 small bet, P0 all-in raise) — P1 facing-all-in, stack=8750=to_call
4. `b1500r10000` (P1 big bet, P0 all-in raise) — P1 facing-all-in, stack=8000=to_call
5. `xb750r10000` — symmetric (P0 facing-all-in after P0 small bet + P1 jam)
6. `xb1500r10000` — symmetric

**Count: 6 distinct phantom-ALL_IN nodes in K72 tree.**

Per-hand × per-history multiplies the action-count-mismatch count by
range size (~50 hands each side). The dry-run #2 report's "6 action-count
mismatches across both spots" almost certainly refers to mismatches at a
single shared history class (e.g., the `b1000A` family in A83) where
Brown emits a row Rust can match position-by-position; the per-cell count
is presumably 6 (player, hand) pairs that survive filtering.

A83 has the same topology under different sizings; identical 6 phantom-
ALL_IN nodes.

## Phase 2: predicted impact

**Direct impact (action-count cells):** Closes 100% of the 6 action-count
mismatches. These cells go from undefined-diff (Rust column doesn't exist
in Brown's row) to well-defined comparable rows.

**Upstream-propagation impact (5e-2 divergent cells):** At each facing-
all-in node, the spurious ALL_IN bucket bleeds regret mass that would
otherwise concentrate on CALL/FOLD. This bleed propagates one level up to
parent nodes (`b1500`, `b750`, root) and alters the EV of the parent's
raise actions. Estimated upstream propagation:
- Removing 1 spurious action out of 3 redistributes ~5-15pp of
  probability mass at the facing-all-in node itself.
- Parent node sees a corrected EV(raise-to-all-in-jam) child; this
  shifts parent's mixed strategy by ~3-8pp on adjacent actions.
- Grandparent (root or `b1500`-level) sees ~1-3pp shift.

Best-case: 30-50% of the 305+306 = 611 divergent cells close to < 5e-2.

**NOT closed:** The worst K72 cells (4.22e-1 on top-pair-K at "c"
action) are at a node the audit doc identifies as
NON-facing-all-in (`b1500r5000` with stack=8000 > to_call=3000, both
engines emit 5 actions). The 42pp divergence here is consistent with
candidate (d) (Brown's `base_pot × P_win` terminal-utility bias) and
is NOT mechanically caused by phantom ALL_IN. The diagnosis claim
that "phantom ALL_IN explains 22-42pp" overstates the fix's reach.

## Phase 3: sanity-check vs dry-run #2

Dry-run #2: K72 max |diff| = 4.22e-1, 305 cells > 5e-2; A83 max
|diff| = 2.71e-1, 306 cells > 5e-2; 6 action-count mismatches.

**Phantom-ALL_IN explains:**
- 6/6 action-count mismatches (100%)
- ESTIMATE: 30-60% of the 611 per-action divergent cells via upstream
  propagation
- 0% of the K72 4.22e-1 worst cell directly (audit doc §6 confirms this
  cell's node is not facing-all-in)

**Residual after PR 50 fix (predicted):**
- Action-count mismatches: 0
- Per-action divergent cells (> 5e-2): ~250-450 still present
- Max |diff|: still > 1e-1 on K72 (top-pair-K cells driven by (d))

## Phase 4: prediction for dry-run #3 (BEFORE result lands)

| Metric | Dry-run #2 (no PR 50) | Predicted dry-run #3 (with PR 50) |
|---|---|---|
| K72 max \|diff\| | 4.22e-1 | **3.0e-1 - 4.2e-1** (small reduction; root cause is (d)) |
| K72 cells > 5e-2 | ~305 | **150-250** (some cells close via propagation) |
| A83 max \|diff\| | 2.71e-1 | **2.0e-1 - 2.7e-1** (small reduction; root cause is (d)) |
| A83 cells > 5e-2 | ~306 | **150-250** |
| Action-count mismatches | 6 | **0** (fully closed) |
| Acceptance gate (5e-2) | FAIL | **FAIL** (both spots still > 1e-1) |

**Falsifiable claim:** If dry-run #3 shows K72 max |diff| < 5e-2,
the diagnosis is MORE correct than I think (DIAGNOSIS-CONFIRMED
override). If K72 max |diff| stays > 3e-1 with similar top-cell
hands, my prediction holds (DIAGNOSIS-PARTIAL). If max |diff|
roughly matches dry-run #2 (> 4e-1), the fix didn't help at all
(DIAGNOSIS-WRONG, escalate to candidate (d)).

## Phase 5: confidence

**MEDIUM.** I have HIGH confidence on the topology audit (action-count
math is mechanical and verified against `hunl.rs:1133` and
`river_game.cpp:98`). I have MEDIUM confidence on the upstream-
propagation impact estimate (no quantitative model for regret bleed,
only directional reasoning). I have HIGH confidence that the worst
K72 cells are NOT closed by PR 50 alone (audit doc §6 traces the
specific node and confirms it's not facing-all-in).

**Key risk:** if the audit doc's identification of `b1500r5000`'s
parameters (stack=8000, to_call=3000) is wrong, my LOW estimate
for K72 closure could be too pessimistic. But the audit doc's
analysis cross-references Brown's `river_game.cpp:98` directly and
the chip-math is verifiable.

## Recommendation

PR 50 fix is necessary (closes Diff #3 + action-count mismatches) but
NOT sufficient. The session should be prepared for dry-run #3 to STILL
fail acceptance at 5e-2 tolerance, with the residual concentrated at
non-facing-all-in nodes on high-equity hands (top-pair-K in K72,
bottom-pair-A in A83). The path forward at that point is documented
in `a83_deep_cap_root_cause_investigation.md` §3 Path C: widen
tolerance with documented Brown convention divergence, OR redefine
the acceptance gate as a structural-correctness check.

---

## Source-of-truth pointers (absolute paths)

- Fixture: `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json`
- Rust enum: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:1133`
- Brown enum: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp:98`
- Topology audit: `/Users/ashen/Desktop/poker_solver/docs/action_menu_topology_audit.md`
- A83 root-cause doc: `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
- Dry-run #2: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_attempt_2.md`
- Test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- This doc: `/Users/ashen/Desktop/poker_solver/docs/pr_50_independent_verification.md`
