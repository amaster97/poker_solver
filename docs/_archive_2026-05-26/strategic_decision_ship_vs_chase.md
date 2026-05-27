# Strategic Decision: Ship v1.7.1 vs Chase Wrapper Bugs

**Date**: 2026-05-24
**Author**: Strategic analysis agent
**Status**: READ-ONLY analysis for user sign-on
**Recommendation**: **Hybrid (Path B + ready wrapper fixes, no new bug hunting)**

---

## 1. What we know

- **Solver is correct.** 5 independent audits, multiple test waves, asymmetric-range fixture passes internally. The DCFR engine itself is not the issue.
- **6 wrapper-side bugs** found in this burst (PR 52, 54, 55, 55-ext, 56, 57). Plus PR 50 (action menu) and PR 51 (dcfr_vector panic) are legitimate solver-adjacent fixes.
- **Dry-run #6 result**: 100% cell coverage, but 124 cells > 1e-1 on K72 (concentrated in one hand class), 0 matches on A83 (caused by sort-order bug, PR 56).
- **The pattern**: each fix exposes another. Wrapper has been incrementally broken since day one. We do not have a closed-form count of remaining bugs.
- **PR 53 reframe** already exists: shallow-agreement + direction-of-aggression captures what Brown's solver can validate; per-cell strict comparison was over-constrained from the start.

## 2. Path A: keep chasing

- **Time-to-strict-gate**: unbounded. Best case 2-3 more PRs + 2-3 dry-runs (~4-6 hours). Worst case: indefinite — onion-peel suggests we genuinely don't know the floor.
- **Risk**: every "one more fix" carries the same prior. The strict gate may not be reachable with Brown's solver at all, regardless of wrapper quality (Brown is a *different* algorithm with its own equilibrium selection).
- **Value**: rigorous external numerical agreement *if* achieved. But see the meta-point: even Brown vs Brown rerun would not match at strict 5e-2 due to stochastic seeds and abstraction differences.

## 3. Path B: ship with PR 53 reframe

- **Time-to-ship**: 30-40 min (per existing `v1_7_1_wrapper_fix_spec.md` + `leg20` template).
- **Risk**: undocumented wrapper bugs could mislead future investigators if anyone re-attempts strict-mode Brown comparison.
- **Value**: closes the loop; users get v1.7.1; captures the meta-lesson (Brown = sanity check, not ground truth) in code + docs.

## 4. Hybrid: Path B + ready-now wrapper fixes (RECOMMENDED)

- Ship v1.7.1 with the reframe AND any wrapper fixes already drafted (PR 56 hand-sort, PR 55-ext range-swap if patch is ready).
- Do **not** gate ship on running another dry-run or finding the next bug.
- Time: 45-60 min total.
- Risk: ~same as Path B; we just pre-fix what's already on the cutting board.
- Value: same closure as Path B, plus less wrapper debt left for the next investigator.

## 5. Recommendation: **Hybrid**

Rationale:

1. **Solver correctness is not in question.** The thing we ship is sound. The thing we're chasing is comparison-harness fidelity to a *different* solver — diminishing returns past sanity-check level.
2. **Onion-peel has no floor estimate.** Path A's time budget is unbounded; user's "utmost importance" was for v1.7.1 ship, not for matching Brown's solver to 5e-2.
3. **PR 53 reframe is the *correct* gate.** Strict per-cell-vs-Brown was always over-constrained — Brown himself wouldn't replicate himself to 5e-2 across reruns.
4. **Ready fixes are cheap inclusions.** PR 56 and PR 55-ext are already scoped; folding them in costs ~15 min and reduces wrapper-debt liability.
5. **Hybrid preserves all autonomous-burst work.** PR 50, 51, 52, 53, 54, 55, 56, 55-ext all land. Nothing is wasted; nothing is over-claimed.

## 6. Commitments either way (irrespective of A/B/Hybrid)

- **Memory entry**: codify the "wrapper peel-onion" pattern → add to `~/.claude/projects/.../memory/` as `feedback_wrapper_peel_onion.md`. Pattern: external-solver comparison harnesses accumulate silent bugs; never trust strict-mode delta as solver-correctness signal.
- **Asymmetric-range fixture**: promote to baseline regression test in `crates/.../tests/` so any future wrapper rewrite must pass it before strict-mode comparison is attempted.
- **Future-proofing**: any new external-solver integration (TexasSolver, etc.) starts with asymmetric-fixture sanity check + PR 53-style reframe gate from day one. Strict per-cell numerical match is **not** the default acceptance criterion.

---

## What user needs to decide on sign-on

1. **A / B / Hybrid?** (Recommendation: Hybrid)
2. **Does PR 55-ext (range-swap) ship now or hold?** If the patch is drafted and audit-cleared, fold in. If still in flight, ship v1.7.1 without it and queue for v1.7.2.
3. **Memory entry phrasing**: approve "wrapper peel-onion" as the codified pattern name, or rename.
4. **Brown-comparison status going forward**: deprecate strict-mode entirely in the harness, or keep it behind a `--strict` flag with a doc-banner warning?

User sign-on unblocks the ship sequence (`leg20`-style script, dual-remote sync, tag v1.7.1).
