# PR 8 audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~50%) > NOT-READY-on-10x-gate (~30%) > clean READY (~15%) > must-fix-on-float-parity (~5%).
> - Top three pre-flagged risk surfaces (audit MUST touch with file:line evidence): 10x speedup hard gate (`audit_preprep.md` §1.6 — 30% NOT-READY probability), baseline-first sequencing (§1.1 — separate commit required), `unsafe` discipline (§1.5 — first-in-codebase, every block needs SAFETY comment).
> - **Branch canonicalization:** the branch is `pr-8-neon-simd-pcs` (per user directive 2026-05-22); the upstream `audit_prompt.md:7` template said `pr-8-simd-layout-pcs` but this final overrides to NEON-explicit naming.
> - **PR 6 filename verification:** before launch, orchestrator MUST confirm PR 6 landed `hunl_solver.rs` (vs `hunl.rs` / `postflop.rs`). If filename diverged, edit focus area 5 evidence stub accordingly.
> - **Rayon explicitly out-of-scope** per spec §1 non-goals + §10 risk 8; auditor flags any `rayon` dep addition as must-fix.
> - **Benchmark methodology:** Criterion `iter_with_setup` pattern is REQUIRED so per-iteration cost excludes one-time alloc + tree-build (steady-state CFR iteration cost only). If bench uses `iter` without setup separation, flag as must-fix (invalidates 10× claim).

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-8-neon-simd-pcs` branch and you have not seen the design discussions. Your job is to audit the PR 8 implementation (NEON SIMD + cache-blocked SoA layout + Public Chance Sampling in Rust) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-8-neon-simd-pcs` (branched from `integration`; canonical name per orchestrator directive 2026-05-22 + `audit_preprep.md:5`).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md` — read end-to-end. Note the 2026-05-21 amendments (auth for Python `HUNLConfig.use_pcs: bool = False` field; 64/32/16 bucket tier; 5e-3 / 2e-2 / 1e-3 cluster).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 8 entries.
- **Target architecture:** `aarch64-apple-darwin` (M-series). NEON is mandatory; scalar fallback exists only for portability of tests on x86 CI.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goals + non-goals — no `unsafe` outside SIMD; 10× hard speedup gate; rayon OUT), §2 (baseline measurement — first action of the PR), §3 (NEON SIMD module + impl rules), §4 (cache-blocked SoA layout, `BLOCK_SIZE=64`), §5 (PCS algorithm + importance weighting + β-switch), §6 (files to modify, especially the 2026-05-21 amendment about `HUNLConfig.use_pcs: bool = False` on the Python side), §7 (differential test scope — four layers A/B/C/D), §9 (critical correctness items, 8 items), §10 (risks), §11 (decisions — esp Decision 13 SIMD+layout-only 8a/8b fallback if PCS slips).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-8-neon-simd-pcs`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 8 entries (Agents A/B/C).
4. **The actual new / modified files:** at minimum
   - `crates/cfr_core/src/simd.rs`
   - `crates/cfr_core/src/layout.rs`
   - `crates/cfr_core/src/pcs.rs`
   - `crates/cfr_core/src/dcfr.rs` (modified — HashMap → FlatInfosetStore swap, SIMD routing, β-switch)
   - `crates/cfr_core/src/hunl_solver.rs` (modified — `use_pcs` wiring; verify filename pre-launch)
   - `crates/cfr_core/src/lib.rs` (module declarations)
   - `crates/cfr_core/src/solver.rs` (adapter for new store, if touched)
   - `crates/cfr_core/Cargo.toml` (criterion dev-dep + possibly `rand`/`rand_chacha` runtime-dep added)
   - `poker_solver/hunl.py` (modified — `HUNLConfig.use_pcs: bool = False` field added; flows through `_serialize_hunl_config`)
   - `tests/test_simd.rs` (Rust integration)
   - `tests/test_layout.rs` (Rust integration)
   - `tests/test_pcs.rs` (Rust integration)
   - `tests/test_pr8_convergence.py` (Python end-to-end)
   - `benches/cfr_bench.rs`
   - `benches/baseline.json` (captured FIRST, separate commit)
   - any other touched files

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.1, §1.5, §1.6 per `audit_preprep.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **Baseline-first sequencing — Agent B's FIRST commit MUST be `benches/baseline.json`.** [HIGH-PROB per `audit_preprep.md` §1.1; ~moderate probability of bundling]
   - Per spec §2 + §9 #8 + Decision 11.9: PR 8's first action captures the unoptimized baseline. `git log integration..HEAD --oneline` MUST show a `bench: capture pre-PR-8 baseline ...` commit STRICTLY BEFORE the first refactor commit (layout.rs / dcfr.rs deltas).
   - `benches/baseline.json` standalone in that commit (no `layout.rs` / `dcfr.rs` / `simd.rs` deltas in same SHA).
   - Header metadata: machine identifier, `sw_vers -productVersion`, `rustc --version`, `git rev-parse HEAD` (PR 6 tip — NOT PR 8 tip), date, criterion version, warm_up=5, samples=20 (per agent_b_prompt §298-319).
   - **Failure mode:** bundled commit (baseline + refactor in same SHA) → baseline measurement contaminated by refactor → 10× claim invalid → must-fix; auditor MUST split-commit recommend.
   - **Evidence stub:** `git log integration..HEAD --oneline | head -3` — confirm baseline is commit #1.

2. **SIMD/scalar bit-exact parity (Layer A).** [HIGH-PROB must-fix per `audit_preprep.md` §1.2]
   - Per spec §7 Layer A line 305 + §9 #1: `result_simd[i].to_bits() == result_scalar[i].to_bits()` — exact bit equality. NaN propagates, Inf propagates, signed zero preserved.
   - Edge values tested: `0.0`, `-0.0`, `f64::NAN`, `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal, random uniform across 1000 trials (seeded).
   - **Exception:** `vfmaq_f64` results may differ at LSB; allowance `ULP ≤ 1` applies ONLY on the explicit FMA op. Default is exact equality elsewhere. If the FMA-tolerance is widened to non-FMA ops → should-fix.
   - **Anti-pattern grep on `tests/test_simd.rs`:**
     - `f64::abs() < 1e-9` / `(a-b).abs() < EPS` / `approx_eq!` / `assert_relative_eq!` macros → must-fix (loose tolerance hides parity bugs).
     - Missing edge-value coverage (NaN / -0.0 / denormal) → should-fix.
     - NaN-quieting via `f64::max` vs NaN-preserving `vmaxq_f64`: signaling-NaN vs quiet-NaN bit-pattern mismatch → must-fix.
     - Signed-zero loss in horizontal-sum reduction order → must-fix.
   - **Failure mode:** silent float behavior divergence between scalar fallback (x86 CI) and aarch64 NEON (production) → cross-platform reproducibility broken.
   - **Evidence stubs:** `tests/test_simd.rs:?` — find `to_bits()` comparison; `crates/cfr_core/src/simd.rs:?` — FMA op location.

3. **PCS allowed to differ statistically; importance weighting MUST be applied (Layer C).** [HIGH-PROB must-fix per `audit_preprep.md` §1.3]
   - Per spec §5 + §7 Layer C + §9 #5: PCS uses importance weight `w = K` (number of public outcomes). Without it, the estimator is biased and the average strategy diverges from the unsampled equilibrium.
   - **Importance weighting:** `w = K`. K=44 for turn-card sampling (52 - 2 hole - 3 flop - 3 dead), K=43 for river-card sampling (52 - 2 hole - 3 flop - 1 turn - 3 dead). Missing weight = biased estimator → must-fix.
   - **Negative-control test** (`tests/test_pcs.rs::importance_weight_required_or_diverges` or similar): removes the `w=K` weight → MUST FAIL. If this test passes when it should fail, tolerance is mis-calibrated → must-fix. If absent entirely → should-fix.
   - **PCS variance bound:** per-action MAE thresholds — mean < **5e-3**, max < **2e-2**, across **5 seeds** (matches PR 6 / PR 7 / PR 9 tolerance cluster per consistency review I3 + 2026-05-21 amendment). Per-spot cluster bound: 1e-3 * pot.
   - Single-seed run insufficient for variance bound → should-fix.
   - **Failure mode:** PCS path "passes" at small iters because variance hasn't manifested but converges to wrong fixed point at large iters. Negative-control is the safety net.
   - **Evidence stubs:** `crates/cfr_core/src/pcs.rs:?` (importance weight application); `tests/test_pcs.rs:?` (negative-control + 5-seed loop + 5e-3 / 2e-2 thresholds).

4. **`unsafe` discipline — first time in codebase.** [HIGH-PROB per `audit_preprep.md` §1.5]
   - Per spec §1 non-goal line 22 + §9 #3 line 419: no `unsafe` outside SIMD intrinsics wrappers.
   - **Grep gate (auditor MUST run):** `grep -nE 'unsafe[[:space:]]*\{' crates/cfr_core/src/*.rs` → enumerate every hit + verify each has a **preceding `// SAFETY:` comment**.
   - SAFETY comments must be non-trivial (NOT `// SAFETY: trust me`); typical content explains alignment + length invariant. NEON 128-bit ops do not require 16-byte alignment on AArch64, but length must be ≥ 4 in the SIMD path.
   - **No `unsafe` in `layout.rs`** unless an explicit hotspot was identified by profiling AND has its own SAFETY comment. Default is bounds-checked `slice[i]`; `get_unchecked` only with profiling justification + own SAFETY → must-fix if naked.
   - **No `unsafe` in `pcs.rs`** (RNG and HashMap-equivalent are safe APIs).
   - `#[deny(unsafe_op_in_unsafe_fn)]` lint hygiene per agent_a_prompt §193-200.
   - **Failure mode:** unsafe block without SAFETY comment, or unsafe leaking into layout/pcs without profiling-driven justification.
   - **Evidence stubs:** `crates/cfr_core/src/simd.rs:?` (every unsafe + preceding SAFETY); `crates/cfr_core/src/layout.rs:?` (expect ZERO unsafe); `crates/cfr_core/src/pcs.rs:?` (expect ZERO unsafe).

5. **`HUNLConfig.use_pcs: bool = False` field correctly declared (Python ↔ Rust).** [pre-staged in PR 6; PR 8 amend authorizes Python side]
   - Per the 2026-05-21 spec amendment (§6 "Files to modify" + consistency review I6): PR 8 **explicitly authorizes** the `HUNLConfig.use_pcs: bool = False` Python schema extension. PR 6 §4.1 pre-mirrors this in the Rust `HUNLConfig`.
   - Python side: `poker_solver/hunl.py::HUNLConfig` has a `use_pcs: bool = False` field. Default False (opt-in per §5 "Default" + §11 #2).
   - Field flows through `_serialize_hunl_config` → Rust → solver.
   - When `use_pcs=True`, the Rust solver internally switches β=0 → β=0.5 (per `_INDEX.md:38` caveat + §5 "DCFR-PCS parameter compatibility" + §9 #4).
   - Tested: `pcs.rs` docstring + explicit `use_pcs=true → solver.beta == 0.5` unit test.
   - **Boundary risk:** Agent B owns `pub use_pcs: bool` on `dcfr.rs` storage struct; Agent C owns the `if config.use_pcs { beta = 0.5 } else { beta = 0.0 }` switch in `dcfr.rs` walker. Concurrent edit on same file → silent merge overlap risk. Orchestrator reconciles per autonomous_log S1.
   - **Failure modes:** boundary collision on `dcfr.rs`; field declared but β never flips; β flips without field.
   - **PR 6 filename note:** the modified file is `hunl_solver.rs` per spec §6; orchestrator MUST have confirmed this filename (vs `hunl.rs` / `postflop.rs`) before audit launch. If filename diverged, treat the diverged name as the new evidence target.
   - **Evidence stubs:** `poker_solver/hunl.py:?` (field declaration); `crates/cfr_core/src/dcfr.rs:?` (β-switch); `crates/cfr_core/src/hunl_solver.rs:?` (wiring); `tests/test_pcs.rs:?` (beta==0.5 unit test).

6. **Cache-blocked layout parity (Layer B).**
   - Per §7 Layer B + §4: `tests/test_layout.rs` runs Kuhn (12 infosets, 1K iter) + Leduc (288 infosets, 10K iter) on both `HashMap`-backed and `FlatInfosetStore`-backed DCFR.
   - Pass criterion: per-infoset average strategy probabilities match within **1e-12** (absorbs FP-noise from different summation orders in tail handling).
   - **Anti-pattern:** silent relaxation to `1e-6` or larger → must-fix (hides genuine layout bugs).
   - The HashMap path is **removed in the same PR** once parity confirmed (spec §4 "Migration path"). Verify the HashMap-backed code is deleted, not just gated behind a flag.
   - Block size `const BLOCK_SIZE: usize = 64` per §4 "Block size". Any other value → must-fix.
   - **Evidence stubs:** `tests/test_layout.rs:?` (1e-12 literal + Kuhn + Leduc); `crates/cfr_core/src/layout.rs:?` (BLOCK_SIZE const + flat SoA struct); `crates/cfr_core/src/dcfr.rs:?` (HashMap path deletion).

7. **Python end-to-end test tolerance (Layer D).**
   - Per spec §7 Layer D (reaffirmed in 2026-05-21 amendments for I3): `tests/test_pr8_convergence.py` runs the existing river-spot test with the optimized Rust solver (SIMD + layout + PCS off by default) and asserts Python reference ↔ optimized Rust agreement within **5e-3** per-action.
   - **No tolerances are weaker than the existing PR 6 Python↔Rust diff test.** Per §7 "No tolerances are weaker..." paragraph.
   - Auditor checks tolerance literal in fixture, harness, AND any parametrized cases — all must use `5e-3`.
   - **Evidence stub:** `tests/test_pr8_convergence.py:?` — find `5e-3` literal + tolerance comparison.

8. **10× speedup hard gate.** [HIGH-PROB per `audit_preprep.md` §1.6 — 30% NOT-READY probability]
   - Per spec §1 line 13 + §8 integration step: hard gate at **≥10× wall-clock speedup** on Section 2 spot 4 (HUNL standard flop, 256/128/64 buckets) — or primary gate on `hunl_simple_flop` (64/32/16 buckets) ≥ 10× per audit_preprep §1.6 + Decision 13.
   - **PR does NOT ship if gate fails.** Verdict: NOT READY.
   - **Per-layer breakdown REQUIRED** (memory `feedback_no_extrapolate`): SIMD microbench ≥3× over scalar; layout-vs-HashMap ≥3×; PCS-vs-enumeration ≥3×. If any per-layer <3×, cumulative cannot reach 10× → PR does NOT ship.
   - Stretch: `hunl_standard_flop` (256/128/64) target ~50×.
   - Stddev > 10% mean → re-run (M-series variance typically <8% mean per fanout_ready §6).
   - The integration phase output (`pr_report.md` or equivalent) MUST show this measurement. If only end-to-end measurement is provided without per-layer breakdown → must-fix (cannot verify the cumulative is genuine vs. one layer dominating).
   - **Fallback:** spec §11 Decision 13 + autonomous_log defines an 8a/8b split — SIMD+layout alone in 8a; PCS in 8b. If 8a measurably hits 10× without PCS, ship 8a; defer PCS.
   - **Evidence stub:** `pr_report.md:?` or `docs/pr8_prep/pr_report.md:?` — speedup table + per-layer breakdown.

9. **Bench harness coverage + `iter_with_setup` methodology.**
   - Per §2 spot list: Kuhn, Leduc, HUNL flop simple (64/32/16 buckets), HUNL flop standard (256/128/64 buckets). Four spots.
   - The 2026-05-21 amendment clarifies "64/32/16" (the documented tier from PLAN.md §1) replaces an earlier "50/64" typo. Verify the bench code uses 64/32/16 for spot 3.
   - **Methodology gate:** Criterion `iter_with_setup` (or `iter_batched`) pattern REQUIRED so per-iteration cost excludes one-time alloc + tree-build → only steady-state CFR iteration cost is measured. If bench uses raw `iter` without setup separation, the per-iter cost is inflated by setup → 10× claim invalidated → must-fix.
   - Criterion bench runs `cargo bench --release` on `aarch64-apple-darwin`.
   - Warm_up=5, samples=20 (per agent_b_prompt §298-319 + matches `baseline.json` header).
   - **Evidence stubs:** `benches/cfr_bench.rs:?` — find `iter_with_setup` or `iter_batched`; verify 64/32/16 bucket count literal for spot 3.

10. **Reproducibility of PCS.**
    - Per §9 #7: ChaCha8Rng is portable; explicit unit test runs sampler with `seed=7` and asserts the first 100 sampled cards match a recorded fixture.
    - Cross-platform deterministic (aarch64 + x86_64). If the fixture was captured on aarch64 only, verify it round-trips on x86 CI too.
    - **Evidence stub:** `tests/test_pcs.rs:?` — find `seed=7` + 100-card fixture comparison.

11. **No new dependencies beyond `criterion` (+ pinned `rand`/`rand_chacha` for PCS).**
    - Per spec §9 #6 + §10 risk 8 + §11 #8: no `ndarray`, no `simd-sys`, no `packed_simd_2`, no `rayon`. Uses `std::arch::aarch64` directly.
    - `criterion = "0.5"` added under `[dev-dependencies]` with `default-features = false` + only required features.
    - `rand` / `rand_chacha` may be added by Agent C for PCS sampler — verify under `[dependencies]` (runtime, not dev) and **pinned** (exact version). Unpinned `rand` → reproducibility break → should-fix.
    - `cargo tree --depth 99` on the criterion path: scan transitive deps for AGPL/copyleft → license-audit grep per `scripts/check_pr.sh`. Transitive AGPL → must-fix.
    - **First-lander wins** on Cargo.toml criterion line: A and B both own this addition per fanout_ready §3 step 1. Duplicate → merge conflict resolved by orchestrator.
    - **Rayon explicit check:** `grep -n 'rayon' crates/cfr_core/Cargo.toml` → expect ZERO matches.
    - **Evidence stub:** `crates/cfr_core/Cargo.toml:?` — `[dev-dependencies]` + `[dependencies]` blocks.

12. **License hygiene + AGPL inspiration boundaries.**
    - Per §10 risk 10: `simd.rs` module docstring acknowledges postflop-solver's `chunks_exact + remainder` pattern as **AGPL read-only inspiration**, with explicit "implementation derived from scratch per Apple's NEON intrinsics docs. No code copied."
    - `vector_eval.cpp:90-131` port (if landed per §11 #13) carries MIT attribution to `noambrown_poker_solver`.
    - Grep new `.rs` files for AGPL-only patterns from postflop-solver. None should match verbatim.
    - **Evidence stub:** `crates/cfr_core/src/simd.rs:1-?` — module docstring with attribution.

13. **Compile-time NEON assertion.**
    - Per §10 risk 1: `simd.rs` includes a compile-time assertion (e.g., `static_assertions::const_assert!` or `#[cfg(target_arch = "aarch64")]` guards) or equivalent doc-comment ensuring NEON is mandatory on aarch64. `cargo build --release --target aarch64-apple-darwin` should succeed without manual `RUSTFLAGS`.
    - **Evidence stub:** `crates/cfr_core/src/simd.rs:?` — find `cfg(target_arch)` guard or `const_assert!`.

14. **`scripts/check_pr.sh` green on `pr-8-neon-simd-pcs` tip.**
    - Per `feedback_pr_branches` + standard PR hygiene: `cargo test --release`, `cargo bench --release` (smoke), `cargo clippy -- -D warnings`, `pytest`, license-audit grep — all green.
    - If check_pr.sh failed at audit launch, audit returns NOT READY without analysis (per `audit_preprep.md` §4 step 3).
    - **Evidence stub:** the agent's `pr_report.md` should include the check_pr.sh summary.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_report.md` with this exact structure:

```markdown
# PR 8 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-8-neon-simd-pcs
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [`cargo test --release` results; `pytest tests/test_pr8_convergence.py`; full suite delta]

**Speedup:** [Measured speedup on Section 2 spot 4 (or primary gate spot 3) vs baseline. Must be ≥10×. Per-layer breakdown table.]

## Must-fix

[SIMD/scalar bit-parity violated; importance weighting missing or negative-control absent; `unsafe` blocks without SAFETY comments; `unsafe` outside `simd.rs`; `HUNLConfig.use_pcs` missing or wrongly typed; layout parity tolerance silently loosened; baseline.json missing or bundled in refactor commit; 10× speedup gate failed; new dep beyond criterion + pinned rand/rand_chacha; AGPL contamination; rayon added; bench uses raw `iter` (no setup separation). Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, awkward APIs, missing comments on tricky NEON code, test holes (no NaN propagation, no -0.0 case), missing compile-time NEON assertion, single-seed PCS variance run, unpinned rand. Each: file:line + description + fix.]

## Nice-to-fix

[Style, clippy lints, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-14 matching the 14 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: SIMD pattern attributed (postflop-solver AGPL inspiration only, no code copy); if vector_eval ported, MIT attribution present; no new third-party deps beyond `criterion` + pinned `rand`/`rand_chacha`. Cite specific module docstrings.]

## Release-notes follow-up

[Note for v0.6.0 / v0.7.0: PR 8 lands NEON SIMD + cache-blocked layout + PCS in Rust. Performance milestone (≥10× over PR 6 baseline) merits explicit release-note callout. Public API change: `HUNLConfig.use_pcs` field added (default False — non-breaking).]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification. Speedup gate result is load-bearing in the verdict.]
```

## Severity rules

- **must-fix:** SIMD bit-parity violated, missing importance weight (PCS converges to wrong fixed point), `unsafe` without SAFETY, `unsafe` outside `simd.rs`, missing `use_pcs` field, layout parity tolerance silently loose, missing or bundled baseline.json commit, failed 10× gate, AGPL code-copy, new dep beyond approved set, rayon added, bench methodology raw `iter` (inflated per-iter cost). Blocks PR.
- **should-fix:** missing negative-control test, awkward APIs, test holes (no NaN propagation), missing compile-time NEON assertion, single-seed PCS run, unpinned rand. Doesn't block.
- **nice-to-fix:** style, clippy, comments. Pure polish.

When in doubt: any silently-wrong float behavior (parity violations, missing importance weight, inflated per-iter cost) → must-fix. Performance-only issues that don't affect correctness → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr8_prep/audit_report.md`.
- For unsafe-comment audit: `grep -nE 'unsafe[[:space:]]*\{' crates/cfr_core/src/*.rs` and verify each has a preceding `// SAFETY:` comment.
- For rayon audit: `grep -n 'rayon' crates/cfr_core/Cargo.toml` — expect zero matches.
- For bench methodology audit: `grep -nE 'iter_(with_setup|batched)' benches/cfr_bench.rs` — expect non-zero matches.
- HIGH-PROB risk surfaces (focus areas 1, 2, 3, 4, 8) MUST get paragraph-level discussion even with no defect found.

Begin by reading the spec (especially the 2026-05-21 amendments about Python `use_pcs` field auth + 64/32/16 bucket tier + 5e-3 / 2e-2 / 1e-3 tolerance cluster), then the diff, then the new files. Then write the report.
