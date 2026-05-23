# PR 6 Commit Message Amendments

**Date:** 2026-05-22
**Source:** Orchestrator follow-up to parallel agents (external Nash + speedup measurement).
**Target file:** `docs/pr6_prep/commit_message_draft.md` (surgical in-place edit; no code touched, no commit issued).

---

## Amendment 1: External Nash deferral note

**Why:** Per `docs/pr6_prep/external_nash_cross_check.md`, the PR 6 tiny river
subgame fixture has degenerate geometry — P0 (`AhKc`) makes top two pair on
`As 7c 2d Kh 5s` while P1 (`QdQh`) makes only a pair of queens, so P0 has
100% showdown equity. With singleton vs singleton ranges and zero P1 equity,
the equilibrium is well-defined and CFR/DCFR converges to exploitability ~0
within ~100 iterations. The 1000-iteration bit-exact Python ↔ Rust match plus
exploitability ~0 is therefore *consistent with theory* but is **not** an
external Nash validation — both tiers could share the same subtle bug
(e.g., utility-sign flip) and still produce identical converged strategies.
PR 7's `noambrown` C++ diff harness is the proper external anchor.

**Edit:** Inserted a clarifying sentence into the "Differential test result"
paragraph (around line 132 of the pre-amendment draft), distinguishing the
internal-parity guarantee from the deferred external-Nash agreement and
naming PR 7's noambrown diff harness as the next gate.

**Before (excerpt):**
> The flop fixture matches within 5e-3 (per spec). HUNL postflop solve on
> the river fixture runs in ~3 s in Rust vs ~95 s in Python (~30x speedup,
> on track for the 10-50x PLAN.md target).

**After (excerpt):**
> The flop fixture matches within 5e-3 (per spec). Note: the tiny river
> subgame fixture has degenerate geometry (P0's AhKc has 100% showdown
> equity vs P1's QdQh on As 7c 2d Kh 5s), so exploitability~0 plus
> bit-exact Python ↔ Rust agreement is consistent with theory; this is
> an internal-parity gate, and external Nash agreement (vs another solver)
> is deferred to PR 7's noambrown diff harness.

---

## Amendment 2: Speedup claim — measured pending parenthetical

**Why:** The in-flight speedup measurement agent has not yet produced
`docs/pr6_prep/speedup_measurement.md` (verified via `ls`; file does not
exist at edit time). Per orchestrator constraints, when the measurement is
not done yet the `~30x` claim is retained with a `(measured pending;
recheck before commit)` parenthetical.

**Edit 2a (primary speedup claim, body paragraph):**

Before:
> ~30x speedup, on track for the 10-50x PLAN.md target). PR 8 SIMD ...

After:
> ~30x speedup, on track for the 10-50x PLAN.md target; measured pending,
> recheck before commit). PR 8 SIMD ...

**Edit 2b (verification-section CLI-smoke timing):**

Before:
> Manual CLI smoke (river subgame, no abstraction, 500 iters via
> --backend rust): prints strategy table + exploitability in <3 s
> (vs ~95 s for the equivalent python-backend call).

After:
> Manual CLI smoke (river subgame, no abstraction, 500 iters via
> --backend rust): prints strategy table + exploitability in <3 s
> (vs ~95 s for the equivalent python-backend call; timings measured
> pending, recheck before commit).

Both timing references now flag the `recheck before commit` action so the
actual measurement (whenever the speedup agent lands) can either confirm
the `~30x` and `<3 s / ~95 s` numbers or replace them with the measured
values.

---

## What was NOT changed

- All other content of `commit_message_draft.md`: scope list, file
  inventory, license attribution, contract decisions, spec-amendments,
  out-of-scope list, branch line, Co-Authored-By trailer.
- No code edits.
- No commit issued.
- No other doc files modified.

## Follow-ups blocking the final commit

1. **Speedup measurement.** When `speedup_measurement.md` lands, replace
   both `~30x` / `<3 s` / `~95 s` numbers with the measured values and
   drop the `(measured pending; recheck before commit)` parenthetical.
2. **PR 7 noambrown diff harness.** External Nash validation lives in
   PR 7. The commit message now flags this deferral explicitly.
3. **Optional plausibility sanity-checks** (P0 game_value > 0,
   exploitability ≤ 1e-6, P1 check-call freq low) — `external_nash_cross_check.md`
   §5 #4 recommends deferring these tests to PR 7 to keep PR 6's surface
   scoped to parity. No change needed in the commit message.
