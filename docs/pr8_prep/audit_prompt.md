# PR 8 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-8-neon-simd-pcs` branch and you have not seen the design discussions. Your job is to audit the PR 8 implementation (NEON SIMD + cache-blocked layout + public chance sampling in Rust) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-8-neon-simd-pcs` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md` — read end-to-end. Note the 2026-05-21 amendments (auth for `use_pcs` Python field; 64/32/16 bucket tier; 5e-3 / 1e-3 cluster).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 8 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goals + non-goals — no `unsafe` outside SIMD; 10× hard speedup gate), §2 (baseline measurement — first action of the PR), §3 (NEON SIMD module + impl rules), §4 (cache-blocked SoA layout), §5 (PCS algorithm + importance weighting + β-switch), §6 (files to modify, especially the 2026-05-21 amendment about `HUNLConfig.use_pcs: bool = False` on the Python side), §7 (differential test scope — four layers), §9 (critical correctness items, 8 items), §10 (risks), §11 (decisions).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-8-neon-simd-pcs`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 8 entries.
4. **The actual new / modified files:** at minimum
   - `crates/cfr_core/src/simd.rs`
   - `crates/cfr_core/src/layout.rs`
   - `crates/cfr_core/src/pcs.rs`
   - `crates/cfr_core/src/dcfr.rs` (modified — HashMap swap, SIMD routing)
   - `crates/cfr_core/src/hunl_solver.rs` (modified — `use_pcs` wiring)
   - `crates/cfr_core/src/lib.rs` (module declarations)
   - `crates/cfr_core/src/solver.rs` (adapter for new store)
   - `crates/cfr_core/Cargo.toml` (criterion dev-dep added)
   - `poker_solver/hunl.py` (modified — `HUNLConfig.use_pcs: bool = False` field added)
   - `tests/test_simd.rs` (Rust integration)
   - `tests/test_layout.rs` (Rust integration)
   - `tests/test_pcs.rs` (Rust integration)
   - `tests/test_pr8_convergence.py` (Python end-to-end)
   - `benches/cfr_bench.rs`
   - `benches/baseline.json`
   - any other touched files

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **SIMD/scalar bit-exact parity.**
   - Per spec §7 Layer A + §9 #1: `result_simd[i].to_bits() == result_scalar[i].to_bits()` exact bit equality. NaN propagates, Inf propagates, signed zero preserved.
   - Edge values tested: `0.0`, `-0.0`, `f64::NAN`, `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal, random uniform across 1000 trials (seeded).
   - Exception: `vfmaq_f64` results may differ at LSB; allowance `ULP ≤ 1` only on the explicit FMA op. Default is exact equality elsewhere.
   - Anti-pattern: if the test silently uses a loose `f64::abs() < 1e-9` rather than `.to_bits() ==`, flag as must-fix.

2. **PCS allowed to differ statistically; importance weighting MUST be applied.**
   - Per spec §5 + §7 Layer C + §9 #5: PCS uses importance weight `w = K` (number of public outcomes). Without it, the estimator is biased and the average strategy diverges from the unsampled equilibrium.
   - **Negative-control test:** a test that removes the importance weight must FAIL — confirming the tolerance is calibrated. Per §7 Layer C + §9 #5.
   - PCS convergence test: 5 seeds, mean per-action error < 5e-3, max per-action error < 2e-2.
   - Tolerance matches PR 6 / PR 7 / PR 9 cluster (5e-3 per-action) — reaffirmed in the 2026-05-21 amendment.

3. **No `unsafe` outside SIMD intrinsics wrappers.**
   - Per spec §1 non-goals + §9 #3: every `unsafe { ... }` block in `simd.rs` has a `// SAFETY: ...` comment explaining alignment + length invariant.
   - **No unsafe in `layout.rs`** unless an explicit hotspot was identified by profiling AND has its own SAFETY comment.
   - **No unsafe in `pcs.rs`.**
   - Flat-array indexing uses bounds-checked `slice[i]` by default. `get_unchecked` only with explicit `// SAFETY:` if profiling justifies.
   - Grep new `.rs` files for `unsafe`: count + verify each one has a preceding `// SAFETY:` comment.

4. **`// SAFETY:` comments on every unsafe block.**
   - Per §3 + §9 #3: each `unsafe` block carries a comment explaining why the operation is safe — typically alignment + length invariants for NEON. NEON 128-bit ops do not require 16-byte alignment on AArch64, but length must be ≥ 4 in the SIMD path.
   - Verify the comments are non-trivial (not just `// SAFETY: trust me`).

5. **`HUNLConfig.use_pcs: bool = False` field correctly declared.**
   - Per the 2026-05-21 spec amendment (§6 "Files to modify" + consistency review I6): PR 8 **explicitly authorizes** the `HUNLConfig.use_pcs: bool = False` Python schema extension. PR 6 §4.1 pre-mirrors this in the Rust `HUNLConfig` already.
   - On the Python side: `poker_solver/hunl.py::HUNLConfig` has a `use_pcs: bool = False` field. Default False (opt-in per §5 "Default" + §11 #2).
   - This field flows through `_serialize_hunl_config` to Rust.
   - When `use_pcs=True`, the Rust solver internally switches β=0 → β=0.5 (per `_INDEX.md:38` caveat + §5 "DCFR-PCS parameter compatibility" + §9 #4).
   - Tested: `pcs.rs` docstring + explicit test (`use_pcs=true` → `solver.beta == 0.5`).

6. **Cache-blocked layout parity (Layer B).**
   - Per §7 Layer B + §4: `tests/test_layout.rs` runs Kuhn (12 infosets, 1K iter) + Leduc (288 infosets, 10K iter) on both `HashMap`-backed and `FlatInfosetStore`-backed DCFR.
   - Pass criterion: per-infoset average strategy probabilities match within **1e-12** (absorbs FP-noise from different summation orders in tail handling).
   - The HashMap path is **removed in the same PR** once parity confirmed (spec §4 "Migration path").
   - Block size `const BLOCK_SIZE: usize = 64` per §4 "Block size".

7. **Python end-to-end test tolerance (Layer D).**
   - Per spec §7 Layer D (reaffirmed in the 2026-05-21 amendments for I3): `tests/test_pr8_convergence.py` runs the existing river-spot test with the optimized Rust solver (SIMD + layout + PCS off by default) and asserts Python reference ↔ optimized Rust agreement within **5e-3** per-action.
   - **No tolerances are weaker than the existing PR 6 Python↔Rust diff test.** Per §7 "No tolerances are weaker..." paragraph.

8. **Baseline `benches/baseline.json` committed FIRST (before optimization).**
   - Per §2 + §9 #8: Agent B's first task is the baseline capture on PR 6's unoptimized code. Baseline lives at `benches/baseline.json` at repo root.
   - Header metadata: machine identifier, macOS version, date, commit hash of the unoptimized base run.
   - If the baseline JSON is missing from the diff → must-fix (the PR cannot be reviewed for speedup claims).

9. **10× speedup hard gate.**
   - Per spec §1 + §8 integration step: hard gate at **≥10× wall-clock speedup** on Section 2 spot 4 (standard HUNL flop) vs baseline. PR does NOT ship if the gate fails.
   - The integration phase output should show this measurement (in `pr_report.md` or equivalent). Verify the bench was actually run and the speedup demonstrated.

10. **Bench harness coverage.**
    - Per §2 spot list: Kuhn, Leduc, HUNL flop simple (64/32/16 buckets), HUNL flop standard (256/128/64 buckets). Four spots.
    - The 2026-05-21 amendment clarifies "64/32/16" (the documented tier from PLAN.md §1) replaces an earlier "50/64" typo. Verify the bench code uses 64/32/16 for spot 3.
    - Criterion bench runs `cargo bench --release` on `aarch64-apple-darwin`.

11. **Reproducibility of PCS.**
    - Per §9 #7: ChaCha8Rng is portable; explicit unit test runs sampler with `seed=7` and asserts the first 100 sampled cards match a recorded fixture.
    - Cross-platform deterministic (aarch64 + x86_64).

12. **No new dependencies beyond `criterion`.**
    - Per §9 #6: no `ndarray`, no `simd-sys`, no `packed_simd_2`. Uses `std::arch::aarch64` directly. No `rayon` added.
    - `criterion = "0.5"` added under `[dev-dependencies]` with `default-features = false` + only required features (per §10 risk 8 + §11 #8).

13. **License hygiene.**
    - Per §10 risk 10: `simd.rs` module docstring acknowledges postflop-solver's `chunks_exact + remainder` pattern as AGPL **read-only inspiration**, with explicit "implementation derived from scratch per Apple's NEON intrinsics docs. No code copied."
    - `vector_eval.cpp:90-131` port (if landed per §11 #13) carries MIT attribution to `noambrown_poker_solver`.
    - Grep new `.rs` files for AGPL-only patterns from postflop-solver. None should match verbatim.

14. **Compile-time NEON assertion.**
    - Per §10 risk 1: `simd.rs` includes a compile-time assertion (e.g., `static_assertions::const_assert!`) or equivalent doc-comment ensuring NEON is mandatory on aarch64. `cargo build --release --target aarch64-apple-darwin` should succeed without manual `RUSTFLAGS`.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_report.md` with this exact structure:

```markdown
# PR 8 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-8-neon-simd-pcs
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [`cargo test --release` results; `pytest tests/test_pr8_convergence.py`; full suite delta]

**Speedup:** [Measured speedup on Section 2 spot 4 vs baseline. Must be ≥10×.]

## Must-fix

[SIMD/scalar bit-parity violated; importance weighting missing or negative-control test absent; `unsafe` blocks without SAFETY comments; `unsafe` outside `simd.rs`; `HUNLConfig.use_pcs` missing or wrongly typed; layout parity tolerance silently loosened; baseline.json missing from diff; 10× speedup gate failed; new dep beyond criterion; AGPL contamination. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, awkward APIs, missing comments on tricky NEON code, test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, clippy lints, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-14 matching the 14 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: SIMD pattern attributed (postflop-solver AGPL inspiration only, no code copy); if vector_eval ported, MIT attribution present; no new third-party deps beyond `criterion`. Cite specific module docstrings.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification. Speedup gate result is part of the verdict.]
```

## Severity rules

- **must-fix:** SIMD bit-parity violated, missing importance weight (PCS converges to wrong fixed point), `unsafe` without SAFETY, `unsafe` outside `simd.rs`, missing `use_pcs` field, layout parity tolerance silently loose, missing baseline.json, failed 10× gate, AGPL code-copy. Blocks PR.
- **should-fix:** missing negative-control test, awkward APIs, test holes (e.g., no NaN propagation test), missing compile-time NEON assertion. Doesn't block.
- **nice-to-fix:** style, clippy, comments. Pure polish.

When in doubt: any silently-wrong float behavior (parity violations, missing importance weight) → must-fix. Performance-only issues that don't affect correctness → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr8_prep/audit_report.md`.
- For unsafe-comment audit: `grep -nE 'unsafe[[:space:]]*\{' crates/cfr_core/src/*.rs` and verify each has a preceding `// SAFETY:` comment.

Begin by reading the spec (especially the 2026-05-21 amendments about Python `use_pcs` field auth + 64/32/16 bucket tier + tolerance cluster), then the diff, then the new files. Then write the report.
