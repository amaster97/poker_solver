# PR 9 launch readiness review

**Date:** 2026-05-22
**Reviewer:** launch-readiness verification pass (post-consistency-review)
**Scope:** verifies pr9_spec.md + agent_{a,b,c}_prompt.md + audit_prompt.md against a 7-point checklist.
**Verdict:** **READY-WITH-PATCHES** — one concrete amendment needed (PR 10b `on_progress` kwarg); everything else is aligned.

---

## Check 1 — Diff-test tolerance: 5e-3 per-action + 1e-3 game value (NOT 1e-4)

**Status:** PASS. Consistently propagated across all five documents.

- pr9_spec.md §10.4 (line 380) explicitly states the new cluster + cites the consistency-review I3 reconciliation. Same line documents the rationale (HashMap iteration × float-accumulation order at HUNL scale) and rejects 1e-4 as fragile.
- pr9_spec.md §13 risk row 8 (line 479) cross-references the same tolerance.
- pr9_spec.md §3 header (line 3) explicitly flags "(c) tolerance aligned 5e-3 / 1e-3 — was 1e-4."
- agent_a_prompt.md "Default decisions LOCKED" item 1 surfaces the I3 reconciliation; agent_a does not author tests but knows the cluster.
- agent_b_prompt.md "Default decisions" §2 (line 38) cites I3 + the 5e-3 / 1e-3 cluster.
- agent_c_prompt.md "Default decisions LOCKED" item 1 (line 74) calls out **`NOT 1e-4` — outlier from earlier draft** in caps, with full I3 quote; the four diff-test specs in §10.4 (lines 154-160) each embed the tolerance.
- audit_prompt.md focus area 2 (line 60-63) flags any tolerance < 5e-3 (e.g., 1e-4) as a **must-fix anti-pattern**.

The 1e-4 figure has been ruthlessly excised; no residual occurrences in the five PR 9 documents.

---

## Check 2 — PR 9 §6 canonical dispatch composition documented + cross-referenced

**Status:** PASS.

- pr9_spec.md §6 (lines 188-235) explicitly opens with "**This section is the authoritative source for HUNL solve dispatch ordering across PRs 3.5, 5, and 9.**" The full Python sketch lists the four-step order: ≤15 BB short-circuit → >250 BB error → postflop → preflop. The ordering invariant + locked boundary tests (`test_preflop_dispatch_pushfold_at_15bb`, `_solver_at_16bb`, `_error_at_251bb`) are stated verbatim.
- agent_a_prompt.md owns the dispatch edit; §"Dispatch composition (canonical per PR 9 §6 — you implement this)" (lines 329-372) reproduces the four-step sketch.
- agent_b_prompt.md notes B4 (PR 9 §6 canonical) in "Read first" and "Default decisions"; Agent B does not implement dispatch but understands the boundary.
- agent_c_prompt.md "Default decisions LOCKED" item 6 (line 79) cites B4.
- audit_prompt.md focus area 1 (lines 46-57) is built around the §6 canonical ordering and the three boundary tests verbatim.

---

## Check 3 — Blueprint convergence target documented

**Status:** PASS.

- pr9_spec.md §7.4 (lines 264-269) locks per-stage targets:
  - Blueprint: exploitability **< 0.5 BB/100** on every reached preflop infoset (loose by design — refinement tightens postflop).
  - Refined subgame: **< 0.1 BB/100** (matches PR 5 Fixture 1).
  - Unrefined long tail: **< 1 BB/100**.
- §10.1 test 1 (line 355) — `test_blueprint_converges_at_100bb` asserts `exploitability_history[-1] < 1.0` (slow) / `< 5.0` (CI 500-iter relaxed variant).
- §17 (line 553) restates the CI smoke + full target.
- audit_prompt.md focus area 3 (line 65-68) explicitly tracks the blueprint < 0.5 BB/100 target and the slow/CI split.

---

## Check 4 — Subgame refinement reuses PR 5 `solve_hunl_postflop` with warm-start

**Status:** PASS.

- pr9_spec.md §8.3 (lines 305-311) lays out the regret-table warm-start protocol; §8.4 (line 314-316) is explicit: refinement constructs a `HUNLConfig(starting_street=Street.FLOP, ...)` with the full PR 3 menu and calls `hunl_solver.solve_hunl_postflop(refinement_config, abstraction, iterations=refine_iterations)`.
- pr9_spec.md §5 "NOT modified" explicitly lists `hunl_solver.py` (PR 5) as called-by but not modified.
- agent_b_prompt.md §"Default decisions" items 1+2 (lines 56-57) lock the full-menu refinement + warm-start regret loading. §"Critical correctness items" §1 (range extraction) and §2 (warm-start) are the load-bearing detail; the agent prompt also flags the contingency: if PR 5's signature doesn't admit a warm-start kwarg, instantiate `DCFRSolver` directly + file an interface-adjustment note (line 64, 167-169).
- audit_prompt.md focus area 4 (lines 70-75) audits the warm-start; focus area 9 (lines 97-99) audits sequential refinement memory hygiene.

---

## Check 5 — Memory budget: PR 5 profiler, 14 GB ceiling, 10% calibration

**Status:** PASS.

- pr9_spec.md §12 (lines 456-466) explicitly inherits PR 5's `MemoryProbe` and the **10% `psutil` RSS calibration tolerance** (I4 reconciliation). 14 GB hard ceiling for blueprint AND each subgame solve; sequential drop (`del solver; gc.collect()`) between subgames.
- §3.4 (line 65) gives the empirical rationale (10–14 GB postflop alone at 100 BB per PLAN.md §1).
- agent_a_prompt.md "Default decisions LOCKED" item 11 + §"Critical correctness items" §4 (lines 392-411) bind the 14 GB ceiling + 10% calibration + the `MemoryError(..., args[1]=report)` raising pattern.
- agent_b_prompt.md §"Default decisions" item 5 (line 60) inherits the same 14 GB / 10% calibration per subgame.
- audit_prompt.md focus areas 8 + 9 (lines 93-99) verify both layers.

---

## Check 6 — `on_progress` kwarg for PR 10b integration

**Status:** **FAIL — PATCH REQUIRED**.

This is the only material gap. PR 10b's spec at line 152-156 dispatches to `solve_hunl_preflop(config, iterations=iterations, on_progress=on_progress, **kwargs)` and explicitly notes (line 270-272): "*(`solve_hunl_postflop` — PR 5; PR 10b adds the `on_progress` kwarg)*" and "*(preflop solver expected to accept the same `on_progress` kwarg per §3 of this spec).*"

Current PR 9 signatures expose **only `log_every`** (callback frequency hint), not the **callback itself**:

- pr9_spec.md §4 line 131: `solve_hunl_preflop(..., seed: int | None = None, log_every: int | None = None) -> PreflopSolveResult` — no `on_progress`.
- agent_a_prompt.md `solve_hunl_preflop` signature line 130, `build_blueprint` line 228 — both have `log_every` but no `on_progress: Callable[[int, float, MemoryReport], None] | None`.
- agent_b_prompt.md `refine_subgame` signature line 134 — same gap.
- Zero occurrences of "on_progress" across all five PR 9 documents.

**Required patch (≤6 lines per file):**

1. **pr9_spec.md §4** — extend `solve_hunl_preflop` signature to add `on_progress: Callable[[int, float, MemoryReport], None] | None = None` after `log_every`. Optionally add the same kwarg to `build_blueprint` and `refine_subgame` for orchestration consistency (PR 10b only directly consumes the top-level `solve_hunl_preflop`, but plumbing it through is cheap and avoids re-spec'ing in PR 10b).
2. **agent_a_prompt.md** — mirror the signature update in `solve_hunl_preflop` + `build_blueprint`; add a sentence noting PR 10b expects this kwarg and the callback contract `cb(iter, exploitability, partial_memory_report)` matches PR 5's pattern per pr10b_spec.md §3.
3. **agent_b_prompt.md** — extend `refine_subgame` similarly (for orchestration symmetry; Agent B passes `on_progress` through to `solve_hunl_postflop`'s PR-5-added callback, which per PR 10b §3 lands at the same time).
4. **agent_c_prompt.md** — add an `on_progress` smoke test variant analogous to PR 10a's `test_real_solve_progress_callback_fires` (or note that test belongs to PR 10b).
5. **audit_prompt.md** — add focus-area item 16: "`on_progress` kwarg present on `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` per PR 10b integration contract." Severity: must-fix if absent, because PR 10b's wiring breaks without it.

Without this patch, PR 10b's dispatch in `ui/state.py` will raise `TypeError: solve_hunl_preflop() got an unexpected keyword argument 'on_progress'` and PR 10b cannot ship without re-touching PR 9.

---

## Check 7 — Exploitability target: < 0.05 BB/hand on validation fixture

**Status:** PASS.

- pr9_spec.md §7.4 end-to-end paragraph (line 269) locks **< 0.05 BB/hand on the Pio 100 BB cash-game validation fixture** (HU NL, no ante, $0.50/$1.00 blinds — Pio's published reference setup). Cites `gtow_how_solvers_work.md` "< 0.5% pot = professional standard" and justifies the 7× looseness given the coarse-blueprint architecture.
- §3 header line 3 surfaces (c): "end-to-end exploitability target added to §7 / §17."
- §10.3 test 5 (line 376) — `test_combined_exploitability_under_0_05_bb_per_hand`, marked `@pytest.mark.slow`; CI relaxed variant at 5k blueprint + 2k refine asserts `< 0.5 BB/hand`.
- §17 success criteria (line 554) restates.
- agent_a_prompt.md "Default decisions" + §"Critical correctness items" §5 (lines 414-416) cite I5; Agent A is responsible for orchestration quality clearing the bar; flags "bump iterations" rather than "weaken the bar" if it doesn't clear.
- agent_c_prompt.md "Default decisions" item 3 (line 76) and §"Critical correctness items" §4 (line 313) lock the test + CI smoke; the test name is verbatim.
- audit_prompt.md focus area 7 (lines 88-91) verifies.

---

## Residual findings (beyond the 7 checks)

- **Spec §10.3 count drift.** §10.3 header says "~4 tests" (also said in §4 line 148) but lists 5 numbered tests + 2 intuition-gauntlet additions = 7 total. The text in agent_c_prompt.md "Test plan" §"`tests/test_hunl_preflop_integration.py`" correctly says "~5 tests" then enumerates 7. Cosmetic nit — neither test count is wrong, just inconsistent in the headers. Suggest updating §4 + §10.3 header to "~5 tests + 2 intuition gauntlet" to match the body.
- **`agent_c_prompt.md` §10.1 lists ~6 tests + 1 additional (canonical chance weights, from §13 risk row 6) = 7 total.** This is correctly justified in Agent C's "Tests you added beyond spec §10" reporting requirement. Fine as-is.
- **`PreflopSolveResult` inherits `HUNLSolveResult` inherits `SolveResult`** lineage is consistent across all five docs (N7 lock from PR 5).
- **PR 5 `solve_hunl_postflop` signature.** Agent B's prompt at line 44 documents PR 5's signature as `(config, abstraction, iterations, target_exploitability, memory_budget_gb, log_every, seed, dcfr_kwargs)` — no `on_progress` either. If PR 10b's plan is for PR 5 to also receive `on_progress` simultaneously (per pr10b_spec.md line 270's "PR 10b adds the `on_progress` kwarg"), confirm whether PR 10b modifies PR 5 too or whether PR 9 + PR 5 both need the patch. Likely PR 10b modifies both — but PR 9's `solve_hunl_preflop` must accept the kwarg natively so PR 10b's only change is the import swap + dispatch wrapper.

---

## Verdict: READY-WITH-PATCHES

The PR 9 deliverable is internally consistent and aligned with the consistency review's amendments (canonical §6 dispatch, 5e-3/1e-3 tolerance, 10% calibration inheritance, < 0.05 BB/hand target). Six of seven checks pass cleanly.

The single material gap is the missing `on_progress: Callable[[int, float, MemoryReport], None] | None = None` kwarg on `solve_hunl_preflop` (and ideally `build_blueprint` + `refine_subgame`). PR 10b's spec explicitly relies on this kwarg; without the patch, PR 10b will not ship without re-opening PR 9.

**Recommendation:** apply the 5-file patch documented under Check 6 before launching Agents A/B/C. The patch is small (≤6 lines/file), purely additive, and avoids retro-touching PR 9 from PR 10b.
