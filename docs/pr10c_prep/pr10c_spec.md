# PR 10c spec — tier calibration pass (measure the four solve-quality numbers)

**Status:** drafted 2026-05-22. Fires after PR 10b lands. Doc-only PR
beyond constant updates.

## 1. Goal

PR 10b shipped the solve-quality slider with four named tiers — **Draft
(1.0% pot)**, **Standard (0.5% pot)**, **Tight (0.25% pot)**, **Library
(0.1% pot)** — but the wall-clock cost of each is unknown on this
solver / hardware. Each placeholder carries a
`# TODO(pr-10c-calibration): tune post-measurement` comment.

PR 10c **measures** the wall-clock cost on real hardware, **fills the
TBD placeholders** in the UI and `USAGE.md`, and removes every
`pr-10c-calibration` TODO.

## 2. Scope

**Inside scope:**

- **Four tier targets:** 1.0% / 0.5% / 0.25% / 0.1% pot exploitability.
- **Three spot complexities** (drawn from `PLAN.md` §1's perf table):
  - **simple flop** — 3 bet sizes, 100 BB, dry texture (e.g., `K72r`).
  - **standard flop** — 5 bet sizes, 100 BB, mid texture (e.g., `Th8c6d`).
  - **complex turn** — 6 bet sizes, 100 BB, wet runout (e.g., `Js9s7c2d`).
- **Both backends:** Python reference (`poker_solver.hunl_solver`) and
  Rust production (`poker_solver._rust` via `--backend rust`).
- **Hardware:** M-series MacBook, 16 GB unified memory — primary target
  per `PLAN.md` §1.
- **Output:** a 4 × 3 wall-clock matrix per backend (24 cells total),
  median + IQR over N=5 runs per cell.

**Outside scope:**

- Solver internals (PR 5 / 6 / 9 code as-is; no DCFR hyperparameter
  re-tuning).
- UI structure (only updates the four numeric defaults in
  `ui/state.py::SOLVE_QUALITY_TIERS` + tooltip in `run_panel.py`).
- New perf work (PR 8 owns SIMD; surface unreachable tiers as follow-ups,
  do not fix here).
- New fixtures (reuse `tests/fixtures/hunl_solve_fixtures.py` +
  PR 10a's preset configs).

## 3. Measurement methodology

1. **Repetition.** N=5 per `(tier × spot × backend)` triple. Report
   **median + IQR** (25–75th percentile). Not mean — CFR convergence
   is heavy-tailed near reachability margins.
2. **Fixtures.** Reuse `tests/fixtures/hunl_solve_fixtures.py` where
   possible; document the exact `HUNLConfig` per spot in
   `calibration_results.md`.
3. **Solver invocation.** Call the UI dispatch wrapper (calibrate the
   user's code path):
   - `target_exploitability` = tier value (10.0 / 5.0 / 2.5 / 1.0 mBB/pot).
   - `iterations=2000` (PR 10b's `ITER_SAFETY_CAP`).
   - `log_every=100`, `seed=0`.
4. **Per-run record:** wall-clock; final exploitability; exit iter;
   exit reason (`target_reached` / `iter_cap`); peak
   `MemoryReport.total_gb`.
5. **Iter-cap analysis:**
   - All 5 runs `target_reached` → **reachable**; report median.
   - Any `iter_cap` → flag `"UNREACHABLE on M-series @ 16 GB"` with
     achieved exploitability.
   - Mixed → flag `"MARGINAL"` with reach rate.
6. **Library cap-policy revisit.** PR 10b §0.1.3 defers the "Library
   cap 2000 vs 5000" question to PR 10c. Answer: if Library hits
   `iter_cap` on >2 of 3 spot complexities, propose a separate
   `LIBRARY_ITER_CAP=5000`. Else keep 2000 uniform.

## 4. Deliverables

1. **`docs/pr10c_prep/calibration_results.md`** — the measured 4 × 3 × 2
   matrix with median + IQR, fixture configs, per-cell flag.
2. **`ui/views/run_panel.py` patch** — `SOLVE_QUALITY_TIERS` retains the
   exploitability floors (1.0% / 0.5% / 0.25% / 0.1% pot), but the
   tooltip / helper text gains measured wall-clock medians + IQRs
   (`"Standard (≈X min, range Y–Z)"`). Remove every
   `# TODO(pr-10c-calibration)` comment.
3. **`USAGE.md` §4 patch** — replace any "(TBD until measured)" /
   "placeholder" tags with measured numbers; slider description reads
   like a spec, not a placeholder.
4. **`PLAN.md` §1 patch** — strip the "TBD until measurement pass"
   tag from the Solver UI control row; back-reference
   `calibration_results.md`.

## 5. Acceptance criteria

1. All 4 tiers have measured wall-clock medians + IQRs on every
   `(spot × backend)` cell, **OR** an explicit
   `"unreachable on M-series @ 16 GB"` flag.
2. UI shows no TBD / placeholder text on slider or tooltip.
3. Every `# TODO(pr-10c-calibration)` comment removed (grep clean).
4. **Variance reported alongside median** (IQR mandatory).
5. **Spot complexity tiering explicit** in deliverable docs —
   simple / standard / complex are three measured tiers users can map
   their own spots to.
6. Library iter-cap question (2000 vs 5000) decided in writing in
   `calibration_results.md`, backed by measurement data.

## 6. Risks

1. **Compute-heavy.** Library ≈ 25× Standard iters worst case; a
   Library × complex-turn cell could be hours per backend. 24 cells ×
   N=5 = 1–2 days serialized. Mitigation: parallelize across cells
   (DCFR is single-threaded; concurrent different-cell runs are safe).
2. **Variance dominates median.** If IQR > 50% of median, the headline
   misleads. Mitigation: surface IQR in tooltip; don't hide it.
3. **PR 9 preflop perf.** Preflop isn't in the 4×3 matrix
   (postflop-only). `PLAN.md` §1 flags PR 8 SIMD may not cover preflop
   traversal. **Preflop calibration deferred** to a follow-up if needed.
4. **PR 8 SIMD timing.** If PR 10c runs before PR 8 lands, Rust numbers
   are pre-SIMD and need re-run later. Document PR 8 status at
   calibration time.
5. **Hardware variance across M-series.** M1 / M2 / M3 / M4 differ.
   Document exact chip + RAM; other users see numbers within a constant
   factor.

## 7. Dependencies

- **PR 10b landed** — calibration runs the real UI dispatch path
  (`SolveRunner.start(quality_tier=...)`).
- **PR 9 production-grade** — dispatch routes preflop configs through it
  (actual preflop calibration deferred per §6.3).
- **PR 8 ideally landed** — otherwise Rust numbers are pre-perf and
  go stale within weeks.

## 8. Test plan (sanity checks during measurement)

Smoke checks that flag "something is badly wrong" before investing
hours in a full sweep:

1. **Draft × simple flop × Rust** finishes in **< 5 minutes**. Else
   Rust backend is broken or fixture is mis-sized.
2. **Standard × simple flop × Rust** finishes in **< 30 minutes**. Else
   abstraction / DCFR is degraded.
3. **Library × complex turn × Rust** **either** produces a number
   within **5 hours** **or** hits iter-cap. No silent runaway.
4. **Python vs Rust parity** — for any cell completing on both
   backends, achieved exploitability matches within float tolerance
   (the PR 6 / PR 7 diff-test invariant). Flag any cell where Rust
   converges to a different exploitability at the same iter count.

---

**Reference appendix:** `pr10b_spec.md` §0.1.3 (calibration pass
spec source); `PLAN.md` §1 (Solver UI control row + perf target
table); `references/blog/gtow_how_solvers_work.md` (industry
convergence-band convention); `references/code/noambrown_poker_solver/`
(Brown's 2000-iter default).
