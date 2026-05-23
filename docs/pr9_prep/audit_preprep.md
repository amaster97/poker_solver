# PR 9 audit pre-prep — anticipated findings & pre-patches

**Status:** Pre-PR-9 reference. Read this BEFORE the audit agent fires post-implementation.
**Date:** 2026-05-22
**Scope:** Forecast the eight highest-probability audit findings (per user-flagged risk surfaces), document pre-patches viable before launch, and set an expected verdict.

This doc complements `launch_readiness.md` (which audits the prompts — READY-WITH-PATCHES; on_progress patch applied per `fanout_ready.md:29`) and `audit_prompt.md` (the 16-area audit brief). It is read-only — no source files touched.

PR 9 fires after PR 5 (HUNL postflop) + PR 6 (Rust port) are on integration; ideally PR 7 too. Largest single PR fan-out after PR 6 (~2,250 implementation LOC + ~600 test LOC across three parallel agents).

---

## 1. Likely audit findings

Numbered to match the eight user-flagged risk surfaces. Each: probability, severity-band the audit will likely assign, evidence anchor, mitigation status.

### 1.1 Range extraction reach-prob conditioning — **HIGH probability / must-fix band**

**Risk:** `_extract_ranges_from_blueprint` in `subgame_refiner.py` must compute `p0_range[hand_class] = Σ_paths reach_prob(path_to_subgame_root | hand_class)` under the **blueprint.strategy posteriors**, NOT 1/169 priors. Silent corruption mode: if the agent grabs the uniform prior over canonical classes (because canonical-class chance is the chance node), the refinement solves on a degenerate range and the 3-bet pot subgame parity (`p0_range["AA"] > p0_range["72o"]`) fails by accident — or worse, passes spuriously because both terms are tiny non-uniform numbers.

**Audit anchor:** `audit_prompt.md` focus area 5 (lines 76-79) — explicitly checks `test_refinement_ranges_extracted_correctly` and asserts non-uniform reach under blueprint strategy.

**Likely audit verdict:** must-fix if Agent B confuses chance-node prior with reach-conditional posterior. Probability HIGH because (a) the canonical-class chance generator (added in `hunl.py`) introduces a fresh uniform-ish prior surface; (b) Agent B's prompt §"Critical correctness items §1" calls this out but the failure mode is subtle.

### 1.2 on_progress kwarg threaded through all three entrypoints — **MEDIUM probability / must-fix band**

**Risk:** `solve_hunl_preflop`, `build_blueprint`, AND `refine_subgame` must each accept `on_progress: Callable[[int, float, MemoryReport], None] | None = None` and invoke it every `log_every` iterations. Failure modes:
- (a) **Silent drop** — kwarg accepted but never invoked (UI shows hung progress bar).
- (b) **Threading gap** — `solve_hunl_preflop` accepts `on_progress` but doesn't pass it down to `build_blueprint` (blueprint pass progresses silently).
- (c) **Refinement threading** — `refine_subgame` accepts `on_progress` but fails to forward to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)`.
- (d) **Rust port omission** — `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust` skip the `Option<PyObject>` parameter or fail to invoke via `Python::with_gil` + `callable.call1(...)`.

**Audit anchor:** `audit_prompt.md` focus area 16 (lines 130-137) — flags missing/dropped kwarg as must-fix; cites PR 10b consumer at `docs/pr10_prep/pr10b_spec.md:152-156`.

**Status:** Prompts are patched (Agent A LOCKED #13; Agent B LOCKED #10; Agent C LOCKED #11). Likely audit catch is the **threading** dimension, not the signature dimension.

### 1.3 Blueprint convergence target (<0.5 BB/100 reached infosets) — **LOW probability / must-fix band IF the assertion is missing**

**Risk:** Per spec §7.4, blueprint exploitability `< 0.5 BB/100` on every reached preflop infoset at 50k iter; relaxed CI variant `< 5.0 BB/100` at 500 iter. Common slips:
- `test_blueprint_converges_at_100bb` asserts global exploitability only (not per-reached-infoset) — gives a free pass when one rare infoset blows up.
- CI variant tolerance silently bumped to `< 50 BB/100` to make a flaky run green.

**Audit anchor:** `audit_prompt.md` focus area 3 (lines 65-68); `launch_readiness.md` Check 3 confirms PASS for the spec; Agent C owns the test.

**Status:** Spec is unambiguous; failure mode is implementation drift, not spec drift.

### 1.4 PR 5 warm-start signature compatibility — **MEDIUM probability / should-fix band**

**Risk:** Agent B reuses `solve_hunl_postflop(refinement_config, abstraction, iterations=...)` and must inject blueprint regret values into the refinement's regret table at iteration 0. If PR 5's signature does NOT admit a `warm_start_regrets` kwarg (or equivalent), Agent B must instantiate `DCFRSolver` directly + file an interface-adjustment note (per `agent_b_prompt.md:64, 167-169`).

**Audit anchor:** `audit_prompt.md` focus area 4 (lines 70-75) — soft-assertion allowance per spec §10.2 #2 (warm-start speeds convergence vs cold-start; failure prompts user review, not auto-fix).

**Likely audit verdict:** should-fix if Agent B silently drops to a strategy-warm fallback without filing the interface-adjustment note. Cold-start fallback that passes parity but skips warm-start = should-fix (loses the iteration-reduction win) but not must-fix.

### 1.5 Canonical-class chance weights (6/4/12 + blocker accounting) — **HIGH probability / must-fix band IF wrong**

**Risk:** The new `_enumerate_preflop_hole_outcomes_canonical()` in `hunl.py` must emit 169 hand-class chance outcomes with combinatorial weights:
- Pairs (e.g., AA): 6 combos.
- Suited (e.g., AKs): 4 combos.
- Offsuit (e.g., AKo): 12 combos.
- **Blocker accounting:** hero AA → villain AA has 1 combo (not 6 — 2 aces removed from deck). Hero AKs → villain AKs has 3 combos (1 of each suit combo blocked).

Failure modes:
- (a) Weights normalized but blockers ignored → AA-vs-AA computed with 6 combos instead of 1 → range silently biased.
- (b) Sum across opponent classes != 1.0 (within 1e-9) given a fixed hero class → bias propagates through every blueprint and refinement infoset.
- (c) The non-canonical 1.6M-combo generator gets silently switched to canonical for default callers (spec §14 #8 says preserve default unchanged).

**Audit anchor:** `audit_prompt.md` focus area 6 (lines 81-86) + the spec §13 risk row 6 brute-force-tiny-subset validator (`test_preflop_canonical_chance_weights_correct`).

**Likely audit verdict:** must-fix if any of (a)/(b)/(c). Probability HIGH because the combinatorics are easy to miscode and the test is the only safety net — a self-consistent-but-wrong implementation passes through to the blueprint and silently corrupts every reached infoset's payoff.

### 1.6 §6 canonical dispatch composition order — **MEDIUM probability / must-fix band IF reordered**

**Risk:** Per spec §6 (the authoritative section for HUNL dispatch across PRs 3.5, 5, 9), the order in `solver.solve()` must be:
1. Push/fold short-circuit (≤15 BB, regardless of `starting_street`) → `pushfold.solve_pushfold(...)`.
2. Stack-depth ceiling (`eff_stack_bb > 250` → `ValueError`).
3. Postflop branch (`starting_street >= Street.FLOP`) → `solve_hunl_postflop(...)`.
4. Preflop branch (`starting_street == Street.PREFLOP`) → `solve_hunl_preflop(...)`.

Critical invariant: a `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` (15 BB preflop) hits the chart, NOT the preflop solver.

Failure modes:
- Push/fold check placed AFTER the preflop branch → 15 BB preflop calls hit the solver (chart bypass).
- Stack ceiling check missing → 300 BB silently routes to preflop solver with unstable abstraction.
- Postflop check placed AFTER preflop with `>=` on the wrong side → flop spots route to preflop branch.

**Audit anchor:** `audit_prompt.md` focus area 1 (lines 46-57) + the three locked boundary tests (`test_preflop_dispatch_pushfold_at_15bb`, `_solver_at_16bb`, `_error_at_251bb`).

**Likely audit verdict:** must-fix if order reversed at any of the three boundary tests; probability MEDIUM because Agent A's prompt reproduces the §6 sketch verbatim and the boundary tests catch silent reorderings.

### 1.7 14 GB ceiling + 10% calibration inheritance — **LOW probability / must-fix band IF dropped**

**Risk:** PR 9 inherits PR 5's `MemoryProbe` and the 10% `psutil` RSS calibration tolerance (I4 reconciliation). Each blueprint solve AND each subgame refinement runs the calibration; `del solver; gc.collect()` between subgames. Failure modes:
- (a) Calibration runs on blueprint but not refinement → larger preflop tree never validates its profiler accuracy.
- (b) Sequential cleanup missing between subgames → integration test exposes RSS leak; `test_memory_no_leak_across_subgames` fails.
- (c) 14 GB ceiling enforced as soft warning rather than `MemoryError(..., args[1]=report)` raising pattern.

**Audit anchor:** `audit_prompt.md` focus areas 8 + 9 (lines 93-99); `launch_readiness.md` Check 5 confirms PASS at spec level.

**Status:** Spec is unambiguous; failure mode is plumbing drift, not spec drift.

### 1.8 Exploitability target <0.05 BB/hand on validation fixture — **MEDIUM probability / should-fix band**

**Risk:** End-to-end target: combined preflop + refinement exploitability `< 0.05 BB/hand` on Pio 100 BB validation fixture (HU NL cash, no ante, $0.50/$1.00 blinds). Slow test; CI relaxed variant: `< 0.5 BB/hand` at 5k blueprint + 2k refine. Failure modes:
- Test marked `@pytest.mark.slow` but never wired to a slow-CI lane → silently never runs.
- CI variant tolerance bumped to `< 5.0 BB/hand` to absorb flakes → loses the safety margin entirely.
- Test passes locally on CPU but fails on GitHub Actions (memory pressure changes solver convergence).

**Audit anchor:** `audit_prompt.md` focus area 7 (lines 88-91); spec §17 success criteria; Agent A's "Critical correctness items §5" cites I5 + flags "bump iterations" over "weaken the bar".

**Likely audit verdict:** should-fix if the slow test exists but the CI variant doesn't OR if the CI tolerance is silently > 0.5 BB/hand. Probability MEDIUM because the test is novel (no PR 1-8 precedent for an end-to-end exploitability fixture at this scale).

---

## 2. Pre-patches viable BEFORE PR 9 fires

**Recommendation: NONE required.** Pre-stage is strong:
- `launch_readiness.md` cleared 6 of 7 checks; the one failure (Check 6, `on_progress`) was patched into all five PR 9 documents per `fanout_ready.md:29`.
- 16 audit focus areas in `audit_prompt.md` map cleanly to anchored implementations.
- Agent prompts internalize the spec §6 canonical dispatch, the 5e-3/1e-3 tolerance cluster (I3), the 10% calibration inheritance (I4), the <0.05 BB/hand target (I5), and the canonical-class chance weights with blocker accounting (§13 risk row 6).
- All three agents have LOCKED decision lists; Agent B has a documented contingency for the warm-start interface gap.

Possible pre-patch candidates considered and deferred:
- **Tighten `agent_b_prompt.md` range-extraction example** — could add a fully-worked numerical example (`p0_range["AA"]` reach calculation under a 2-bet blueprint), but Agent B's prompt §"Critical correctness items §1" already cites the formula. Audit catches via focus area 5 regardless.
- **Add a 9th canonical-class weight test for hero=AKo vs villain=AKs blocker case** — incremental coverage. `test_preflop_canonical_chance_weights_correct` already validates against brute-force enumeration on a tiny subset per §13 risk row 6.

Both are belt-and-suspenders; **launch without them**.

---

## 3. Expected verdict given current prep quality

**Forecast: READY for commit AFTER must-fix items resolved** (per `audit_prompt.md:180` verdict taxonomy).

Rationale:
- The 7 launch-readiness gates are READY (one patched). Spec/prompt surface is clean.
- 16 audit focus areas anchor to well-documented surfaces.
- Most-likely must-fix findings: **1.1 (range-extraction prior vs posterior)** and **1.5 (canonical-class chance weights + blockers)**. Both are subtle correctness bugs that pass smoke tests but corrupt downstream solves.
- Likely should-fix findings: 1.4 (warm-start signature fallback) and 1.8 (CI variant of exploitability target).
- Lower-probability findings: 1.2 (on_progress threading — prompts are patched), 1.3 (blueprint target — spec is unambiguous), 1.6 (§6 order — boundary tests catch reorderings), 1.7 (memory ceiling — spec is unambiguous).

**Expected severity counts at audit:** 1-3 must-fix (most likely 1-2 from {1.1, 1.5}; outside risk from {1.2, 1.6}); 2-5 should-fix; 3-7 nice-to-fix.

**P(clean READY-no-patches verdict):** ~15%.
**P(READY-with-must-fix verdict):** ~70%.
**P(NOT-READY verdict):** ~15% (only if Agent B botches range extraction AND Agent A miscodes canonical-class weights — both load-bearing correctness surfaces).

PR 9 is the largest single PR after PR 6 (~2,250 LOC + 600 test LOC, three parallel agents). Expected severity counts are higher than PR 7's forecast (0-2 must-fix) commensurate with the larger surface.

---

## 4. Sequencing: when this doc fires

**Trigger:** This file becomes the audit-prep reference the moment the PR 9 audit agent is dispatched per `fanout_ready.md` §7.

**PR 9 audit fires AFTER agents A/B/C complete** — never in parallel with implementation. Specifically:
1. Wait for all three implementation agents (A, B, C) to return; aggregate per wave (do not greedy-schedule).
2. Reconcile interface drift (`launch_kickoff.md` §5a) — particularly if Agent B reports PR 5 warm-start signature gap.
3. Launch audit agent + `check_pr.sh` in parallel (`launch_kickoff.md` §5b). Audit reads `audit_prompt.md` as primary brief; this file is reference-only.
4. Compare `audit_report.md` findings against §1 forecasts here. If audit finds must-fix items NOT in §1, those are blind spots — root-cause and update this doc for future PRs.
5. Apply patches per audit, re-test, commit, push, merge no-ff into integration.

**Read order at audit time:**
1. `audit_prompt.md` (the audit brief — primary input).
2. This file (anticipated findings — calibrate expectations).
3. `launch_readiness.md` (proves the pre-stage gates passed).
4. `audit_report.md` (the audit agent's output — compare against §1 forecasts).

**Post-audit action:**
- If audit finds ≤2 must-fix matching §1.1/§1.5 forecast → apply patches per audit, re-test, commit.
- If audit reports NOT-READY → halt, escalate to user, do not merge.
- This doc is reference-only. Do NOT modify source files based on §1 forecasts before the audit runs — the audit is what catches the actual bugs. Use this only to (a) prime expectations and (b) accelerate post-audit triage.

---

## Anchors

- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md`
- Launch readiness: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_readiness.md`
- Fan-out launcher: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/fanout_ready.md`
- Launch kickoff playbook: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_kickoff.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_{a,b,c}_prompt.md`
- PR 10b consumer (on_progress contract): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md:152-156`
