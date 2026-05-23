# PR 7 launch-readiness verification

**Reviewer:** launch-readiness audit agent
**Branch staging:** `pr-7-noambrown-diff` (not yet open; pre-drafted)
**Inputs audited:** `pr7_spec.md`, `agent_{a,b,c}_prompt.md`, `audit_prompt.md`, Brown's `cpp/CMakeLists.txt`
**Date:** 2026-05-22

## Verdict: READY-WITH-PATCHES

Three of the six gates are clean; two need a one-line edit in `pr7_spec.md` + `audit_prompt.md`; one is acceptable but worth flagging. PR 7 CAN fire after PR 6 lands provided the orchestrator applies the two-line spec patch documented below before launching the three implementation agents.

---

## Check 1: Brown binary path (post-build) — **PATCH REQUIRED (P1)**

**Finding:** The canonical binary path is `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` (CMake source root is `cpp/`, per `references/code/noambrown_poker_solver/cpp/CMakeLists.txt:1-2`; the `add_executable(river_solver_optimized ...)` target at `cpp/CMakeLists.txt:14` places the binary in whatever `-B` directory cmake is called with).

`pr7_spec.md` is **internally inconsistent**:
- Line 89: `references/code/noambrown_poker_solver/build/river_solver_optimized` (WRONG — missing `cpp/`)
- Line 102: `build/river_solver_optimized` (WRONG — same)
- Line 141, 220: `cpp/build/` (correct)
- Line 206 risk #9: `build/river_solver_optimized` (WRONG)

`audit_prompt.md:84` repeats the wrong path.

Agent A's prompt (`agent_a_prompt.md:61`) already catches this and locks in `cpp/build/` as canonical — so Agent A will produce correct code. But Agent B will skip-check by calling `find_brown_binary()` (Agent A's function), so as long as A is implemented correctly the runtime is fine. The risk: audit agent (`audit_prompt.md:84`) will read the wrong path and may report a false "must-fix" against Agent A's correct path.

**Patch:** `sed -i ''` replace `noambrown_poker_solver/build/` → `noambrown_poker_solver/cpp/build/` in `pr7_spec.md` (3 occurrences) and `audit_prompt.md` (1 occurrence).

## Check 2: DCFR flag invocation — **READY**

`--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2` is consistent across `pr7_spec.md:24, 89`, `agent_a_prompt.md:62, 228-230`, and `audit_prompt.md:63`. Matches Brown's `cpp/src/trainer.cpp:353-361` and PLAN §1.

## Check 3: Tolerance (5e-3 / 1e-3 × pot) — **READY**

Per-action `5e-3`, per-spot game value `1e-3 × pot` is consistent across `pr7_spec.md:1, 101, 196, 283`, `agent_a_prompt.md:12`, `agent_b_prompt.md:10, 58-59, 137-138`, `agent_c_prompt.md` (smoke-tier looser at `0.02 × pot`), `audit_prompt.md:79-81`, and `spec_consistency_review.md:41-49` (I3 confirms PR 6 + PR 7 + PR 8 align at this tolerance).

## Check 4: Raise encoding canonicalization (Brown extra-beyond-call ↔ ours raise-to-total) — **READY**

`pr7_spec.md:99, 190` documents Brown's `r<extra>` ↔ our `r<to_total>` mapping with state accumulation. `agent_a_prompt.md:248-301, 357-378` provides full canonicalization signatures + the state-machine spec (per-player contributions tracked left-to-right). `agent_c_prompt.md:162-191` provides 10 hand-built round-trip test cases. `audit_prompt.md:47-54` audits this surface. Load-bearing piece is well-covered.

**Minor note:** `agent_c_prompt.md:181` test case `("b500/r9000", "b500A", (("b", 500), ("r", 9500)))` has a state-arithmetic subtlety; Agent C's prompt at line 193 already flags this explicitly as needing verification against Agent A's implementation. Acceptable.

## Check 5: License compliance (invoke-only, no code copy) — **READY**

`pr7_spec.md:158-186` documents MIT terms + attribution header verbatim. `agent_a_prompt.md:429-449, 453-456, 458-468` reiterates: depend on CLI surface + JSON schema (public interface), no code copy from `cpp/src/*.cpp`. Attribution docstring template is mandatory and reproduced. `audit_prompt.md:88-93` audits for contamination. Brown's `LICENSE:1-21` (MIT, Copyright 2025 Noam Brown) confirmed at the source.

## Check 6: `pytest.mark.skipif` for missing compiler / cmake — **READY**

Three-layer skip strategy is consistent:
1. `scripts/build_noambrown.sh` soft-fails (`exit 0`) if `cmake` or `c++` absent (`pr7_spec.md:127-129, 139`, `agent_a_prompt.md:397-405`).
2. `find_brown_binary()` returns `None` if file absent (`agent_a_prompt.md:179-188`).
3. `tests/test_noambrown_river_parity.py` calls `pytest.skip("Brown's river_solver_optimized not built; ...")` at the top of each test (`pr7_spec.md:102`, `agent_b_prompt.md:151-153, 159-164, 227-236`).
4. The infra test `test_brown_binary_buildable` itself has a `shutil.which("cmake")` check (`agent_b_prompt.md:152-154`).
5. Agent C's smoke tests do NOT require the binary at all (`agent_c_prompt.md:9-12`).

`audit_prompt.md:82-86` audits this. Comprehensive.

---

## Residual findings

1. **(P1) Binary path inconsistency** in `pr7_spec.md` (lines 89, 102, 206) and `audit_prompt.md:84`. Patch before launching the audit agent post-implementation, even if implementation is correct — otherwise the audit will mis-report.
2. **(P3) `agent_c_prompt.md:181`** all-in-as-raise canonical value assumes state-tracking semantics agent A will verify. Already flagged in the prompt. No action.
3. **(P3) `pr7_spec.md:62`** lists `"Jh Tc Tc 5d 3s"` as a paired-board example which has duplicate `Tc`; `agent_a_prompt.md:419` already flags this for Agent A to fix to `Jh Td Tc 5d 3s` and note in report. No action.

## Can PR 7 fire post-PR-6? **YES (with the P1 patch applied first)**

PR 7 is dependency-clean from PR 6: PR 6 ports DCFR to Rust; PR 7 compares Python DCFR vs Brown's C++. They share no files. PR 7 freezes `poker_solver/hunl.py`, `solver.py`, `dcfr.py` (agent prompts ban modification), so it cannot race PR 6's Rust port. The two can run in either order; PR 6 first matches the locked validation chain in PLAN §4. Apply the P1 patch (~30 seconds of `sed`), then launch Agents A+B+C in parallel per `pr7_spec.md:208-275`.
