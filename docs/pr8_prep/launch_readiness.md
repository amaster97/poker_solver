# PR 8 launch-readiness verification

**Date:** 2026-05-22
**Reviewer:** orchestrator pre-launch check
**Inputs audited:** `pr8_spec.md` (504 LoC), `agent_a_prompt.md` (376 LoC), `agent_b_prompt.md` (585 LoC), `agent_c_prompt.md` (481 LoC), `audit_prompt.md` (177 LoC).
**Scope of verification:** the 8 launch-readiness checks below against the PR-8-fanout package; alignment to PR 6 (HUNL Rust port) post-write.

## Verdict

**READY-WITH-PATCHES** — 2 minor documentation patches recommended pre-launch; nothing blocking. PR 8 can fire post-PR-6 with the patches applied (or even without them, given they are clarifications rather than spec gaps).

## Check-by-check results

### 1. `HUNLConfig.use_pcs: bool` field authorized

**Status:** CONFIRMED.

- PR 6 spec line 3, line 121: `use_pcs: bool` pre-emptively added to the Rust `HUNLConfig` mirror; consistency review I6 referenced.
- PR 8 spec §6 row "Modify" line 281: Python-side `HUNLConfig.use_pcs: bool = False` field addition authorized.
- Agent C prompt lines 218-226: explicit single-line edit to `poker_solver/hunl.py` (additive only; PR 3 lossless `infoset_key` preserved).
- Agent B's `dcfr.rs` storage and Agent C's β-switch + Python field cleanly split with orchestrator-mediated coordination notes.

**Patch note:** the user's prompt says "added to PR 4 + PR 6 specs" but I6 only requires PR 6 (PR 4 is abstraction-only and doesn't touch `HUNLConfig`). The PR 6 auth is the load-bearing one and it is in place. No remediation needed.

### 2. SIMD intrinsics correctly target aarch64; scalar fallback for x86 CI

**Status:** CONFIRMED.

- Spec §3 lines 89-94: `std::arch::aarch64` intrinsics only; `#[cfg(target_arch = "aarch64")]` gates NEON; `#[cfg(not(target_arch = "aarch64"))]` gates the scalar fallback.
- Agent A prompt lines 57, 63, 181-183: NEON-on-aarch64 + scalar fallback for non-aarch64; storage is `float64x2x2_t` on aarch64, `[f64;4]` on scalar.
- Decision 11.1 (locked): no Cargo `simd` feature; `target_arch` gating only — correct choice for CI where x86 runners exist.

### 3. SIMD/scalar bit-exact parity required

**Status:** CONFIRMED.

- Spec §7 Layer A line 305: `result_simd[i].to_bits() == result_scalar[i].to_bits()` — exact bit equality, with documented FMA ULP≤1 exception (line 307).
- Agent A prompt lines 207-213: bit-exact default; FMA allowance ULP≤1 only on `vfmaq_f64` op.
- Audit prompt §1 (lines 45-50): anti-pattern `f64::abs() < 1e-9` flagged as must-fix.
- NaN/Inf/signed-zero handling explicitly addressed (Agent A lines 224-237; spec §9 #1).

### 4. PCS variance test tolerance documented

**Status:** CONFIRMED.

- Spec §7 Layer C lines 323-329: per-action MAE < 5e-3 mean, < 2e-2 max, across 5 seeds.
- Layer D (Python end-to-end) lines 333-337 explicitly reaffirms the 5e-3 per-action + 1e-3 per-spot game-value cluster matches PR 6/7/9 (consistency review I3).
- Spec §1 line 16: "PCS path is allowed to differ (sampling is statistical) but the average strategy at convergence must agree within tolerance."
- Agent C prompt lines 74-78, 333-339: tolerance contracts explicit; negative-control test (importance weight removed → MUST FAIL) wired in `test_pcs.rs`.

### 5. Slumbot MIT for vectorized eval pattern; postflop-solver AGPL never copied

**Status:** CONFIRMED.

- Spec §3 lines 98-112: postflop-solver (`utility.rs:79-203`) is AGPL **read-only inspiration only**, "implementation derived from scratch per Apple's NEON intrinsics docs"; `vector_eval.cpp:90-131` (MIT, `noambrown_poker_solver`) is the safe-to-port reference with attribution header.
- Spec §10 risk 10 + license-audit grep in `scripts/check_pr.sh`.
- Agent A prompt lines 270-286: AGPL/MIT distinction clearly enforced; required module docstring attribution comment provided verbatim.
- Agent B prompt lines 497-512: slumbot2019 (MIT, `build_kmeans_buckets.cpp`) cited as architectural inspiration source.

### 6. Baseline measurement: PR 8 step 0 = capture PR 6 baseline before any opt

**Status:** CONFIRMED.

- Spec §2 lines 24-47: "PR 6 produces benchmark data. PR 8's first action is to capture the unoptimized baseline." Line 47: "No baseline = no PR 8."
- Agent B prompt lines 321-329 (process sequence): write `cfr_bench.rs` → confirm compile/run → check out pre-PR-8 state → capture baseline → return to optimization branch → begin refactor.
- Spec §9 #8 + Decision 11.9: `benches/baseline.json` committed FIRST (separate clean commit before refactor commits).
- Audit prompt §8 (lines 85-88): missing baseline = must-fix.

### 7. No `unsafe` outside SIMD intrinsics wrappers (each has `// SAFETY:` comment)

**Status:** CONFIRMED.

- Spec §1 line 22 (non-goals); §9 #3 line 419.
- Agent A prompt lines 250-256: per-block `// SAFETY:` comments required; `#[deny(unsafe_op_in_unsafe_fn)]` hygiene; example SAFETY comment provided (lines 193-200).
- Agent B prompt line 70, 484: NO `unsafe` in `layout.rs` by default; `get_unchecked` only with profiling justification + explicit SAFETY.
- Agent C prompt: NO `unsafe` in `pcs.rs` (implicit — RNG/HashMap are safe).
- Audit prompt §3 + §4 (lines 57-66): grep-based audit for every `unsafe` block + SAFETY-comment quality check.

### 8. Multi-thread (Rayon) is OUT of scope for PR 8

**Status:** CONFIRMED.

- Spec §1 line 19 (non-goal): "No GPU. No new multi-threading beyond rayon if PR 6 already enabled it."
- Spec §11 Decision 10 line 488-489: "Should PR 8 add multi-threading (rayon) to the DCFR walker? Recommended: no — out of scope."
- Spec §9 #6 line 425: "Do not add `rayon` here — if PR 6 added it, we leave it alone."
- Agent B prompt line 71: "No new runtime dependencies. ... no `rayon`."
- No rayon parallelization is in any agent's deliverables.

## Residual findings / recommended patches

### Patch 1 (nice-to-fix, NON-BLOCKING) — clarify "PR 4 + PR 6 specs"

The user's verbal launch-readiness brief said `use_pcs` was "added to PR 4 + PR 6 specs." In actuality, only **PR 6 spec** mirrors the field (PR 4 is the abstraction PR and has no `HUNLConfig` surface). The PR 8 spec §6 amended note correctly attributes pre-emption to PR 6 §4.1 only. **No code/spec change needed**; just an awareness item for the orchestrator.

### Patch 2 (nice-to-fix, NON-BLOCKING) — confirm PR 6's `hunl_solver.rs` filename

Spec §6 line 277 and Agent C prompt lines 164-188 assume PR 6 lands `crates/cfr_core/src/hunl_solver.rs`. Spec §10 risk 6 (line 443) acknowledges the file may be named differently (`hunl.rs`, `postflop.rs`) and provides the 8a/8b split fallback. **Before launching Agent C**, verify the actual PR 6 filename so the prompt can name the right file inline (avoids a ~1-day adaptation step). If PR 6 used a different name, a 2-line edit to Agent C's prompt suffices.

## Can PR 8 fire post-PR-6?

**Yes.** The package is internally consistent, all 8 launch checks pass, file ownership is cleanly partitioned across A/B/C, the audit prompt rigorously enforces every spec invariant, and the only residual items (Patch 1 + Patch 2) are pre-launch confirmations rather than spec gaps. **Recommend launching as soon as PR 6 lands and the `hunl_solver.rs` filename is confirmed.**
