# v1.6.1 dry-run #6 — bundle of all 5 fixes (PRs 50/51/52/54/55)

**Date**: 2026-05-24
**Worktree**: `/private/tmp/dryrun-6-bundle-46375` (`origin/main` + cherry-picks)
**Verdict**: **GAP-REMAINS** — strict gate still fails; PR 55 (as scoped in
the investigation doc) is **insufficient** to close the K72 gap. Path
forward requires either (a) extending PR 55 to also swap the input
ranges at the test boundary, or (b) PR 53 reframe.

## Bundle composition

| Order | PR | Branch | Cherry-pick result |
|---|---|---|---|
| 1 | 51 | `pr-51-dcfr-vector-asymmetric-fix` | clean |
| 2 | 50 | `pr-50-facing-all-in-guard` | clean |
| 3 | 52 | `pr-52-suit-encoding-fix` | clean |
| 4 | 54 | `pr-54-renderer-stack-ceiling` | clean |
| 5 | 55 | **manual apply** (Option B from investigation doc) | clean |

PR 55 was not opened by the sibling agent within the wait window;
applied manually per `docs/p0_p1_convention_investigation.md` §Phase 4
Option B (swap `parsed_players[0]` ↔ `parsed_players[1]` at
`_parse_brown_dump`, plus mirror swap on `game_value_p0/p1`). Single
commit `e4e789b`.

## Build + smoke

- `cargo build --release`: OK
- `cargo test --lib --release`: **50/50 passed** (17.34s)
- `pip install` + universal2 wheel rebuild (initial pip-install-e
  produced an x86_64-only `.so`; replaced with the universal2 build
  from `maturin build --release --target universal2-apple-darwin` to
  match the host's arm64 site-packages)
- `pytest tests/test_exploit_diff.py`: **5/5 passed** (55s)

## Acceptance results

### K72 (`dry_K72_rainbow`)

Full metrics from `/tmp/dryrun_6_diagnose.py` (instruments the same
math as the test, without short-circuiting on first failure):

| Metric | Value |
|---|---|
| coverage | **100.0%** (30/30 Brown histories matched in Rust) |
| max |diff| | **0.9999999986** (≈1.000) |
| cells total | 172 |
| cells ≥ 5e-3 | 142 |
| cells ≥ 5e-2 | 124 |
| cells ≥ 1e-1 | 122 |
| action-count mismatches | **0** |
| Brown wall | 0.08s |
| Rust wall | 119.7s |

Pytest verdict: **FAILED** at first diff above tolerance 5e-3.
Sample diffs (from `/tmp/dryrun-6-acceptance.log`):

```
P0 hand=9cTc hist='b1500' action='c': brown=0.000 rust=0.879 |diff|=8.79e-1
P0 hand=9cTc hist='b1500' action='f': brown=1.000 rust=0.119 |diff|=8.81e-1
P0 hand=9cTc hist='b1500r5000A' action='c': brown=0.000 rust=0.917 |diff|=9.16e-1
P0 hand=9cTc hist='b1500r8000A' action='c': brown=0.001 rust=0.998 |diff|=9.98e-1
```

### A83 (`dry_A83_rainbow`)

| Metric | Value |
|---|---|
| coverage | **100.0%** (42/42 Brown histories matched in Rust) |
| max |diff| | **0.0** |
| cells total | **0** ← VACUOUS PASS |
| cells ≥ 5e-3 | 0 |
| cells ≥ 5e-2 | 0 |
| cells ≥ 1e-1 | 0 |
| action-count mismatches | 0 |
| Brown wall | 0.10s |
| Rust wall | 156.0s |

Pytest verdict: **PASSED** — but `cells_total=0` means **zero hands
matched between Brown and Rust by hand-string**. A83's ranges contain
NO same-suit-in-same-rank pairs (all entries are pocket pairs, AKs/AKo,
T9s — pocket pairs have two same-rank cards which sort identically in
both encodings only if the suits are the same letter set in the same
order, which they ARE for pairs like AcAd; mixed-rank/different-suit
hands sort differently). So even pocket pairs collide as `AcAd` (Brown)
vs `AdAc` (Rust). **No hands match → no cells compared → vacuous
pass.**

## Comparison table

| Metric | DR#2 | DR#3 | DR#4 | DR#5 | **DR#6** |
|---|---|---|---|---|---|
| Bundle | 35c only | 50 | 50+51+52 | 50+51+52 | **50+51+52+54+55** |
| K72 coverage | ≥80% | 53.3% | 53.3% | 53.3% | **100.0%** |
| K72 max |diff| | 4.22e-1 | 1.000 | gate | gate | **~1.000** |
| K72 cells > 5e-2 | 305 | 74 | gate | gate | **124** |
| K72 cells > 1e-1 | — | — | — | — | **122** |
| A83 coverage | ≥80% | panic | 66.7% | 66.7% | **100.0%** |
| A83 max |diff| | 2.71e-1 | panic | gate | gate | **0** (vacuous) |
| A83 cells total | — | — | — | — | **0** (NO MATCHES) |
| Action-count mismatches | 4 | 0 | 0 | 0 | **0** |

## Key findings (Phase 6 — interpretation)

### 1. PR 54 propagation: confirmed

K72 coverage jumped 53.3% → 100% and A83 53.3-66.7% → 100%. The
renderer `stack_ceiling` kwarg fix is working: every Brown history
now renders to a Rust-recognized substr.

### 2. PR 55 (Option B alone) is insufficient

The investigation doc's Phase 4 §Option B hypothesizes that swapping
the BrownStrategyDump.players ordering at `_parse_brown_dump` makes
the diff loop a same-role comparison. This is half-correct: it makes
the SEAT/ROLE labels align, but it does NOT re-align which RANGE
each solver received as input.

- After PR 55 swap, `brown_dump.players[0]` holds Brown's player 1
  data — strategy computed against ranges-from-Brown's-perspective
  where Brown's player 1 ran on Brown's range[1] vs Brown's range[0].
- Rust's seat 0 (in our convention = our second-actor) ran on
  `p0_holes = spot.ranges[0]` vs `p1_holes = spot.ranges[1]`. Our
  second-actor's range is `spot.ranges[0]` (= Brown's first-actor's
  range, NOT Brown's second-actor's range).
- So `brown_dump.players[0]` strategy was computed on the OPPOSITE
  range from what Rust's seat 0 was computed on. Roles match, ranges
  swapped.

This explains the **~88–99% diffs on suited connector hands**
(9cTc/9dTd/etc.) at K72: those hands are in both ranges, but the
strategy you play for 9cTc on a K72 board depends drastically on
whether your opponent has the K8s/JTs/KX nut combos (P0's range) or
the AA/KK/QQ overpairs (P1's range). Brown's player 1 had P1's value
range against a P0 with bluff candidates; Rust's seat 0 had P0's
bluff range against P1's overpairs. **Different games. Same hand. ≠
strategy.**

### 3. Hand-string-encoding bug: still present, now visible

`cells_total = 0` for A83 reveals a second-order encoding bug: Rust's
`hole_string` sorts cards by Rust's `card_id = rank*4 + s_idx` with
`SUITS = "shdc"` (s=0,h=1,d=2,c=3); Brown sorts cards by Brown's
`card_id = suit*13 + rank` with suits-letter ordering `c<d<h<s`. The
SUIT LETTERS match (PR 52 fixed that), but the SORT KEY differs:

- Brown emits `'KcKd'` (Kc id=11, Kd id=24 → Kc first).
- Rust emits `'KdKc'` (Kd id=46, Kc id=47 → Kd first).

The test compares `rust_rows.get(brown_hand_str)` against Rust's
`rust_rows` keyed by Rust-format. Only hands where the two encodings
agree by accident (same-suit hands like Kc8c where rank dominates
both sort orders) match. All others are silently skipped.

This is why K72's 172 matched cells are exclusively
same-suit hands, and why A83 (which has no same-suit cross-rank
hands and where even pocket pairs sort differently) has 0 matched
cells.

PR 52 fixed the suit-CHAR mapping but did not address the sort-ORDER
divergence. A complete fix needs one of:
- normalize Rust's `hole_string` to emit Brown's sort order, OR
- post-process Brown's hand strings into Rust's sort order before
  the lookup, OR
- key the rust_lookup by the unordered pair `(card_low, card_high)`
  via a canonicalizing form.

## Verdict

**GAP-REMAINS**. The strict gate (coverage ≥80% AND max |diff| < 5e-2)
does **NOT** pass on K72; A83's "pass" is vacuous.

### Path forward

Per the decision tree, this routes to: ship needs **PR 53 reframe**
as load-bearing, OR a more substantive PR 55 (Option B + range swap
at test boundary + hand-string-encoding canonicalization).

The investigation doc's Phase 4 §Option B prediction ("the swap
should collapse the diff to <1e-2 if Rust is Brown-equivalent") is
**partially refuted in the field**: the swap is necessary but not
sufficient because (a) it doesn't remap the SOLVER INPUTS and (b)
the hand-string sort-order mismatch hides most cells.

Two additional changes are required for the strict gate:

1. **PR 55 extension** (or new PR): in
   `test_v1_5_brown_apples_to_apples.py` (and `test_river_diff.py`),
   pass `p0_holes = spot.ranges[1]` and `p1_holes = spot.ranges[0]`
   to the Rust solver so that our seat 1 (first-actor) gets the
   first-actor's range, matching Brown's player 0. Equivalently:
   keep the input order but also swap the lookup logic. This MUST
   pair with the PR 55 brown-dump swap to remain consistent.
2. **PR 56 (proposed)**: align hand-string encoding between Rust and
   Brown. Either change Rust's `hole_string` sort order to match
   Brown's, or canonicalize on the lookup side. Without this, the
   strict gate can never be measured.

Without these two follow-ups, the only paths to a v1.7.1 ship are:
- **PR 53 reframe** (load-bearing): acceptance becomes sanity-check
  on coverage + action-set parity, not per-cell probability parity.
- **WIDENED-GATE** doesn't apply — diffs are ≥1e-1 on real cells.

## Cleanup

Worktree to be removed after report.
