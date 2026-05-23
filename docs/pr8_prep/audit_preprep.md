# PR 8 audit pre-prep

**Date:** 2026-05-22
**Author:** orchestrator pre-stage (audit-anticipation)
**Branch under (future) audit:** `pr-8-neon-simd-pcs`
**Mirror of:** `pr7_prep/audit_preprep.md` pattern.
**Scope:** anticipate likely audit findings for PR 8 (NEON SIMD + cache-blocked layout + Public Chance Sampling) BEFORE PR 8 fires; pre-stage any patches viable today; record sequencing.

PR 8 has **not started**. The branch `pr-8-neon-simd-pcs` does not exist yet (gated on PR 6 landing on integration). This doc is anticipation-only.

---

## 1. Likely audit findings (per the 7 risks user flagged)

### 1.1 Baseline-first sequencing — Agent B's FIRST commit MUST be `benches/baseline.json`

**Spec basis:** §2 lines 24-47 ("PR 6 produces benchmark data. PR 8's first action is to capture the unoptimized baseline. ... No baseline = no PR 8."); §9 #8; Decision 11.9; audit_prompt §8 lines 85-88.

**Anticipated audit signal:**
- `git log integration..HEAD --oneline` must show a `bench: capture pre-PR-8 baseline ...` commit STRICTLY BEFORE the first refactor commit.
- `benches/baseline.json` diff must be standalone in that commit (no `layout.rs` / `dcfr.rs` deltas in same commit).
- Header metadata: machine id, `sw_vers -productVersion`, `rustc --version`, `git rev-parse HEAD` (PR 6 tip — NOT PR 8 tip), date, criterion version, warm_up=5, samples=20 (per agent_b_prompt lines 298-319).

**Failure mode:** bundled commit (baseline + refactor in same SHA) → audit must-fix; baseline measurement contaminated by refactor; 10× claim invalid.

**Severity if violated:** must-fix (blocks PR).

### 1.2 SIMD/scalar bit-exact parity

**Spec basis:** §7 Layer A line 305 (`result_simd[i].to_bits() == result_scalar[i].to_bits()`); §9 #1; audit_prompt §1 lines 45-50.

**Anticipated audit signal:** anti-pattern grep on `tests/test_simd.rs`:
- `f64::abs() < 1e-9` / `(a-b).abs() < EPS` / `approx_eq!` macros → must-fix (loose tolerance hides parity bugs).
- Missing edge-value coverage: `0.0`, `-0.0`, `f64::NAN`, `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal, random 1000-trial seeded → should-fix.
- NaN-quieting via `f64::max` vs NaN-preserving `vmaxq_f64`: signaling-NaN vs quiet-NaN bit-pattern mismatch → must-fix.
- Signed-zero loss in horizontal-sum reduction order → must-fix.
- FMA `vfmaq_f64` ULP≤1 allowance correctly scoped (ONLY on the explicit FMA op, not default everywhere) → if widened, should-fix.

**Failure mode:** silent float behavior divergence between scalar fallback (x86 CI) and aarch64 NEON (production) → cross-platform reproducibility broken.

**Severity if violated:** must-fix.

### 1.3 PCS variance vs strategy convergence

**Spec basis:** §1 line 16 ("PCS path is allowed to differ ... but the average strategy at convergence must agree within tolerance"); §7 Layer C lines 323-329; §9 #5.

**Anticipated audit signal:**
- Per-action MAE thresholds: mean < 5e-3, max < 2e-2, across 5 seeds (matches PR 6/7/9 tolerance cluster per consistency review I3).
- **Negative-control test** (`tests/test_pcs.rs::importance_weight_required_or_diverges` or similar): removes the `w=K` weight → MUST FAIL. If this test passes when it should fail, tolerance is mis-calibrated → must-fix.
- Importance weighting: `w = K` (number of public outcomes — i.e., turn-card sampling → K=44; river → K=43). Missing weight = biased estimator, average strategy diverges from unsampled equilibrium → must-fix.
- 5 seeds (not 1): single-seed run insufficient for variance bound.

**Failure mode:** PCS path "passes" at small iters because variance hasn't manifested but converges to wrong fixed point at large iters. Negative-control is the safety net.

**Severity if importance weight missing:** must-fix. If negative-control test absent: should-fix.

### 1.4 `use_pcs` flag wiring — Agent B storage vs Agent C behavior on `dcfr.rs`

**Spec basis:** PR 6 §4.1 (pre-mirrors Rust `HUNLConfig.use_pcs`); PR 8 §6 line 281 (authorizes Python `HUNLConfig.use_pcs: bool = False`); fanout_ready.md §4 lines 105-110 (boundary risk); agent_c_prompt lines 26, 481.

**Anticipated audit signal:**
- Agent B owns `pub use_pcs: bool` on `dcfr.rs` storage struct.
- Agent C owns the `if config.use_pcs { beta = 0.5 } else { beta = 0.0 }` switch in `dcfr.rs` walker.
- Concurrent edit on same file `dcfr.rs` → silent merge overlap risk if both agents touch adjacent lines or if Agent C's behavior PR rebases over Agent B's storage PR with stale assumptions.
- Python flow: `HUNLConfig.use_pcs=False` (default) → `_serialize_hunl_config` → Rust → `solver.beta == 0.0`. Flipping to `use_pcs=True` → `solver.beta == 0.5` (per `_INDEX.md:38` caveat).
- Test required: `pcs.rs` docstring + explicit `use_pcs=true → beta == 0.5` unit test.

**Failure mode:** boundary collision on `dcfr.rs` causes one agent's edit to clobber the other's; field declared but β never flips; or β flips without field. Orchestrator reconciles per autonomous_log S1.

**Severity if `use_pcs` field missing on Python side:** must-fix. If β-switch missing: must-fix. If both missing entirely: NOT READY.

### 1.5 `unsafe` discipline — every block needs `// SAFETY:` comment, none outside `simd.rs`

**Spec basis:** §1 line 22 (non-goal: no `unsafe` outside SIMD intrinsics wrappers); §9 #3 line 419; audit_prompt §3-§4 lines 57-66.

**Anticipated audit signal:**
- `grep -nE 'unsafe[[:space:]]*\{' crates/cfr_core/src/*.rs` → count.
- For each hit: preceding `// SAFETY: ...` comment (non-trivial; not `// SAFETY: trust me`); typical content explains alignment + length invariant (NEON 128-bit ops don't require 16-byte alignment on AArch64, but length must be ≥4 for the SIMD path).
- **No unsafe in `layout.rs`** (default to bounds-checked `slice[i]`; `get_unchecked` only with profiling justification + own SAFETY).
- **No unsafe in `pcs.rs`** (RNG and HashMap-equivalent are safe APIs).
- `#[deny(unsafe_op_in_unsafe_fn)]` hygiene per agent_a_prompt lines 193-200, 250-256.

**Failure mode:** unsafe block without SAFETY comment, or unsafe leaking into layout/pcs without profiling-driven justification.

**Severity:** must-fix.

### 1.6 10× speedup hard gate — measured on Criterion bench, Section 2 spot 3 (or 4)

**Spec basis:** §1 line 13 (10× hard gate); §8 integration step; audit_prompt §9 lines 90-92.

**Anticipated audit signal:**
- `pr_report.md` MUST contain measured speedup table: per-spot baseline (from `benches/baseline.json`) vs PR-8-tip Criterion result.
- Primary gate: `hunl_simple_flop` (64/32/16 buckets, 1K iter) ≥10× over baseline.
- Stretch: `hunl_standard_flop` (256/128/64) target ~50×.
- Per-layer breakdown required (memory `feedback_no_extrapolate`): SIMD microbench ≥3× over scalar; layout-vs-HashMap ≥3×; PCS-vs-enumeration ≥3×. If any per-layer <3×, cumulative cannot reach 10× → PR does NOT ship.
- Stddev > 10% mean → re-run (M-series variance typically <8% mean per fanout_ready §6).

**Failure mode:** speedup measured at <10× → NOT READY (PR does not ship); or only end-to-end measurement provided without per-layer breakdown → must-fix (cannot verify the cumulative).

**Severity:** must-fix (gate); NOT-READY verdict if speedup <10×.

### 1.7 `Cargo.toml` dev-deps — `criterion` only; verify no transitive AGPL

**Spec basis:** §9 #6 line 425 (no new runtime deps beyond criterion); §10 risk 8; §11 #8; audit_prompt §12 lines 103-105.

**Anticipated audit signal:**
- `crates/cfr_core/Cargo.toml` shows ONLY `criterion = { version = "0.5", default-features = false, features = ["html_reports"] }` added to `[dev-dependencies]`.
- No `ndarray`, no `packed_simd_2`, no `simd-sys`, no new `rayon` (already in PR 6 or absent).
- `rand` / `rand_chacha` may be added by Agent C for PCS sampler — verify these are under `[dependencies]` (runtime, not dev) and pinned (per agent_c_prompt; check exact version).
- `cargo tree --depth 99` on the criterion path: scan transitive deps for AGPL/copyleft → license-audit grep per `scripts/check_pr.sh`.
- **First-lander wins** on Cargo.toml criterion line: A and B both own this addition per fanout_ready §3 step 1 + §4 ownership table. Duplicate → merge conflict → orchestrator-resolved or auto-deduped.

**Failure mode:** transitive AGPL → license contamination (the project is MIT-aspirational); or unpinned `rand` → reproducibility break.

**Severity:** AGPL contamination = must-fix; missing pin on rand = should-fix.

---

## 2. Pre-patches viable BEFORE PR 8 fires

**None.** PR 8 has not started; the branch `pr-8-neon-simd-pcs` does not exist. There is no diff to patch. All seven anticipated findings are conditional on Agent A/B/C output, which is gated on the launch wave that fires post-PR-6.

Pre-stage actions already complete (per launch_readiness.md §1-§8 verdict READY-WITH-PATCHES):

- **Patch 1 (PR 4 + PR 6 attribution):** documentation clarification; non-blocking; no spec change.
- **Patch 2 (PR 6 hunl_solver.rs filename):** orchestrator MUST confirm filename before Agent C fires (2-line edit to agent_c_prompt.md if PR 6 used `hunl.rs` or `postflop.rs`).
- **Branch-name patch (audit_prompt.md line 14):** audit_prompt currently says `pr-8-simd-layout-pcs`; user instruction says `pr-8-neon-simd-pcs`. Orchestrator override at audit launch OR pre-edit audit_prompt line 14 (non-blocking; either works).

No code-level pre-patches are viable. PR 8 audit infra is read-only until A/B/C produce a diff.

---

## 3. Expected audit verdict

PR 8 is the **highest-risk PR in the roadmap**:

- Three concurrent agents on overlapping files (`dcfr.rs` touched by A indirectly via simd routing + B storage + C behavior).
- New `unsafe` blocks (first time in the codebase per §1 non-goal direction).
- Hard 10× speedup gate that can fail (no prior data point that confirms the layered speedups multiply).
- New runtime deps (`rand`/`rand_chacha`) + license-sensitive territory (postflop-solver AGPL is read-only inspiration; the temptation to copy patterns is real).
- Baseline-first sequencing is unusual (most PRs go feature-first, baseline-after).
- Cross-platform reproducibility risk (NEON aarch64 vs scalar x86 CI).

**Most likely verdicts (in order of probability):**

1. **READY-WITH-PATCHES** (~50%): minor findings — missing negative-control test, loose tolerance in one parity test, one unsafe block without SAFETY comment, baseline commit bundled with refactor (needs split). Resolvable in <1 day.
2. **NOT READY** (~30%): 10× speedup gate fails on `hunl_simple_flop` (per-layer breakdown shows <3× on layout or PCS). Requires re-architecture or scope reduction (drop PCS to PR 9, ship SIMD+layout alone, re-bench).
3. **READY for commit** (~15%): all 14 audit focus areas pass clean. Possible if Agents A/B/C execute textbook against the very detailed spec.
4. **Must-fix on float parity** (~5%): NaN-quieting or signed-zero loss in test_simd.rs.

**Probability the 10× gate fails:** non-trivial. Mitigation: spec §11 Decision 13 + autonomous_log defines an 8a/8b split fallback (SIMD+layout alone in 8a; PCS in 8b). If 8a measurably hits 10× without PCS, ship 8a; defer PCS.

**Probability of `unsafe` discipline finding:** moderate. First time the codebase has unsafe blocks; Agent A is well-primed but a single missed SAFETY comment is plausible.

**Probability of baseline-commit bundling:** moderate. Agent B's prompt explicitly separates the commits (agent_b_prompt lines 321-329, 466-473), but agents under load can collapse commits. Orchestrator must verify two commits in Agent B's `pr_report.md`.

---

## 4. Sequencing reminder

PR 8 audit fires **AFTER** all three agents complete AND `scripts/check_pr.sh` passes locally. Per launch_kickoff.md §5:

1. Fan-out wave: Agents A, B, C launch in ONE tool-call block (parallel, background).
2. Wait for all three completions (orchestrator polls via Monitor on background tasks).
3. Run `scripts/check_pr.sh` on `pr-8-neon-simd-pcs` tip → resolve any failures.
4. Launch audit agent in parallel with continuing downstream work (per `feedback_min_five_agents` + `feedback_parallel_agents`).
5. Audit writes `docs/pr8_prep/audit_report.md` with the 14-focus-area structure.
6. Orchestrator resolves must-fix items (likely 1-3 fixes) → re-bench if necessary → commit on `pr-8-neon-simd-pcs` → push → `--no-ff` merge to integration.

**Do NOT fire audit before all three agents return.** Audit on incomplete diff = wasted audit cycle + invalid verdict.

**Per memory `feedback_no_extrapolate`:** even if per-layer microbenchmarks suggest a cumulative 10×, do NOT claim 10× until the integrated `hunl_simple_flop` Criterion result confirms it. Agent B's `pr_report.md` must contain the integrated measurement.

---

## 5. Cross-reference checklist for audit launch

When the audit agent fires post-fan-out, verify these inputs exist (per audit_prompt.md "Inputs to read"):

- [ ] `git diff integration...HEAD` produces non-empty diff on `pr-8-neon-simd-pcs`.
- [ ] `git log integration..HEAD --oneline` shows ≥2 commits with `bench: capture pre-PR-8 baseline ...` first.
- [ ] `benches/baseline.json` exists at repo root with full metadata header.
- [ ] All 7 expected new files exist: `crates/cfr_core/src/{simd,layout,pcs}.rs`, `tests/test_{simd,layout,pcs}.rs`, `tests/test_pr8_convergence.py`, `benches/cfr_bench.rs`.
- [ ] All 5 expected modified files exist: `crates/cfr_core/src/{dcfr,hunl_solver,lib,solver}.rs`, `crates/cfr_core/Cargo.toml`, `poker_solver/hunl.py`.
- [ ] `pr_report.md` from each of Agents A/B/C present in `docs/pr8_prep/` or branch root.
- [ ] Criterion bench output (mean ± stddev per spot) included in B's `pr_report.md`.

If any checkbox unchecked → audit returns NOT READY before any analysis is done.
