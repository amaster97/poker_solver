# v1.5 Brown apples-to-apples post-purge numbers (2026-05-27)

**Purpose:** capture per-fixture aggregate numbers from the post-purge v1.5
Brown apples-to-apples test to fill the two remaining
`<TBD-POST-PURGE-RESIDUAL>` and `<TBD-POST-PURGE-MAX-Δ-A83-2K>`
placeholders in `docs/v1_8_0_release_notes_DRAFT.md`.

**Test:** `tests/test_v1_5_brown_apples_to_apples.py` (both fixtures, full
log at `~/Desktop/v1_5_brown_post_purge.log`).

**Origin head at capture:** `f1e9c81` (test: add `@pytest.mark.slow` to 2
more heavy tests in `test_river_diff_self_sanity`, follow-up to b53e0f0,
PR #82). Post-purge SHA per release notes substitution is `37e5be1`
(PR #78); the current `main` is downstream of that purge.

**Runtime:** 272.91 s for both fixtures end-to-end. **Verdict gate:** both
fixtures `PASSED` under the gated SANITY layer.

---

## Per-fixture numbers (post-purge, 2026-05-27)

| Fixture            | L1 max | p75   | median | Top-action % | Shallow viol | Coverage | Action-count match | Strict viol (>=5e-2) | Strict max \|Δ\| |
|--------------------|--------|-------|--------|--------------|--------------|----------|--------------------|----------------------|------------------|
| `dry_K72_rainbow`  | 1.703  | 0.066 | 0.002  | 160/168 (95.2%) | 13 / 0    | 100.0%   | 195/195 (100.0%)   | 85                   | 8.517e-01        |
| `dry_A83_rainbow`  | 1.813  | 0.194 | 0.050  | 326/342 (95.3%) | 21 / 0    | 100.0%   | 441/441 (100.0%)   | 313                  | 9.066e-01        |

Notes:
- "Shallow viol" column is `shallow_cells / violations` — both fixtures
  have zero shallow violations under gated thresholds.
- "Strict viol" and "Strict max |Δ|" lines are informational-only (per
  reframed gate per the chase-vs-ship decision); the gated SANITY layer
  is what determines PASS/FAIL.

## Pre-purge baseline (per `docs/v1_5_brown_current_state_2026-05-26.md`)

| Fixture            | L1 max (pre) | Strict max \|Δ\| (pre) |
|--------------------|--------------|------------------------|
| `dry_K72_rainbow`  | 1.736        | 0.8679                 |
| `dry_A83_rainbow`  | 1.813        | 0.9066                 |

## Delta (post-purge − pre-purge)

| Fixture            | ΔL1 max  | ΔStrict max \|Δ\| |
|--------------------|----------|-------------------|
| `dry_K72_rainbow`  | −0.033   | −0.0162           |
| `dry_A83_rainbow`  |  0.000   |  0.0000           |

K72 moved slightly tighter on both L1 max (1.736 → 1.703) and strict
max |Δ| (0.8679 → 0.8517). A83 is essentially unchanged at the four-digit
precision recorded in the pre-purge state doc (1.813 / 0.9066 → 1.813 /
0.9066).

## Verdict: **PARTIAL**

- The purge **did not collapse Brown apples-to-apples residual** to
  near-zero. It is not a closing-the-gap event for this gate.
- K72 tightened by ~2% on L1 max and ~2% on strict max |Δ|. A83 is
  unchanged at the precision the pre-purge doc recorded.
- Both fixtures remain `PASSED` under the gated SANITY layer (which is
  the binding contract). The strict layer remains informational and is
  consistent with the Nash-multiplicity acceptance framing
  (`feedback_nash_multiplicity_acceptance.md`): deep-cap indifference
  manifolds prevent strict per-cell convergence, so the strict numbers
  here are a noise floor, not a regression.
- This is the **expected post-purge baseline** for v1.8.0 release-notes
  substitution: residual is bounded and stable, not collapsed.

## Substitution values for `docs/v1_8_0_release_notes_DRAFT.md`

These are the values to drop into the placeholders:

- `<TBD-POST-PURGE-RESIDUAL>` →
  `L1 max 1.703 (K72) / 1.813 (A83); strict max |Δ| 0.852 / 0.907; both
  fixtures PASS under gated SANITY (top-action ≥95% on both, 100%
  action-count match, 0 shallow violations)`

- `<TBD-POST-PURGE-MAX-Δ-A83-2K>` →
  `0.907` (`dry_A83_rainbow` strict max |Δ| at `iter=2000`; L1 max
  1.813)

These come from the post-purge run at `f1e9c81` and match the
expectations recorded in the pre-purge state doc within precision.

## Caveats

1. The specific cell `3sAs|...|b1000r3000` is not surfaced in the test's
   default output; per-cell logs would require harness instrumentation,
   which is out of scope for this capture (per brief: no source/test
   modification).
2. The pre-purge L1-max value of `1.813` for A83 in
   `docs/v1_5_brown_current_state_2026-05-26.md` matches the post-purge
   value at 3 decimals; this is consistent with the deep-cap
   indifference-manifold framing — the L1 distance to Brown is bounded
   below by the Nash multiplicity, and the purge does not change the
   multiplicity.
3. Verdict is **PARTIAL** rather than DIDN'T-HELP because K72 moved in
   the right direction (small but real), and rather than
   PURGE-CLOSED-THE-GAP because A83 didn't move and neither fixture
   collapses to anywhere near the gated SANITY noise floor.

## Files

- Full pytest log: `~/Desktop/v1_5_brown_post_purge.log`
- Source draft requiring substitution:
  `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md`
  (lines 388 and 401)
- Pre-purge baseline doc:
  `/Users/ashen/Desktop/poker_solver/docs/v1_5_brown_current_state_2026-05-26.md`
