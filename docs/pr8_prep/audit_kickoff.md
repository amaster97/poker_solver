# PR 8 audit kickoff (pre-staged, fire-on-implementer-completion)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **When to fire:** after the PR 8 implementer agents (A / B / C) all return and report their `pr_report.md` is complete. The branch under audit is `pr-8-simd` (worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd`). DO NOT fire while any of the three implementers are still in flight — partial diff = mis-classified audit.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `pr8_spec.md` §8 acceptance gates + the 10× hard perf gate: **READY-WITH-PATCHES (~50%) > READY (~30%) > NOT-READY (~20%)**. The 10× perf gate is unusual and adds verdict-risk vs PR 10a.5's narrow conformance scope.
> - Hard scope: 3 orthogonal optimizations (NEON SIMD, cache-blocked layout, PCS). Each is bench-gated.
> - Worktree path for inspection: `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd`. Audit may `cd` there for read-only inspection but must NOT branch-switch the shared working tree at `/Users/ashen/Desktop/poker_solver`.
> - Hard-forbidden additions: any new dep besides `criterion` (per §9 #6). Any AGPL code copied from `postflop-solver` (verbatim or near-verbatim from `references/code/postflop-solver/src/utility.rs`).
> - Differential test tolerances are LOCKED at the PR 6/7/8/9 cluster: `5e-3` per-action, `1e-3 × base_pot` per-spot game value. Any tolerance loosening = must-fix.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-8-simd` branch and you have not seen the design discussions. Your job is to audit the PR 8 implementation (NEON SIMD + cache-blocking + public chance sampling for the Rust HUNL solver) against the PR 8 spec and report findings in a structured Markdown report.

Treat `docs/pr8_prep/pr8_spec.md` and the three implementer `pr_report.md` files as the sources of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 8 is a **performance optimization PR** on top of the unoptimized Rust HUNL solver landed by PR 6. Three orthogonal optimizations: (1) ARM NEON 128-bit SIMD vectorization; (2) cache-blocked SoA infoset storage replacing `HashMap<String, InfosetData>`; (3) public chance sampling (PCS) with importance correction. Hard perf gate: **≥10× speedup** on Section 2 spot 4 (standard HUNL flop) vs the committed `benches/baseline.json`. Target tag: deferred to integration release time.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-8-simd`. Worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd`. Branched from main tip `62c75d5` (post-v1.0.0 GA merge). Verify via `git -C /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd log main..HEAD --oneline`.
- **Base commit:** `62c75d5` (main after FF merge).
- **Spec (authoritative):** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md` — read end-to-end first. §2 (bench spots + baseline methodology), §3 (NEON SIMD scope + API + impl rules), §4 (cache-blocked layout), §5 (PCS algorithm + importance weighting + β-switch), §6 (files to create/modify), §7 (4-layer differential test commitment), §8 (3-agent fan-out + integration gate), §9 (critical correctness items), §10 (risks), §11 (deferred decisions — read for context).
- **Implementer reports:** there should be three (`docs/pr8_prep/pr_report_agent_a.md`, `pr_report_agent_b.md`, `pr_report_agent_c.md`) OR a single consolidated `docs/pr8_prep/pr_report.md`. Read whichever exist end-to-end.
- **Originating audit-prompt precedent:** `/Users/ashen/Desktop/poker_solver/docs/pr10a_5_prep/audit_kickoff.md` (for the structural template) and `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` (closest peer — Rust postflop port, same parallel-agent pattern).

## Inputs to read (in order)

1. **The spec:** `pr8_spec.md`. Internalize §2 (4 bench spots; expected baseline wall-clock), §3 (NEON API + 4 hot ops + scalar fallback + tail handling), §4 (FlatInfosetStore layout + indexing + block size = 64), §5 (PCS sampling + K-weight importance + β=0.5 switch), §7 (Layers A/B/C/D + tolerances), §8 (3-agent ownership + integration gate), §9 (8 correctness items).
2. **The implementer report(s):** under `docs/pr8_prep/`. Cross-reference each agent's deliverable list against their owned-files block in §8.
3. **The committed baseline:** `benches/baseline.json` MUST exist and be committed before any optimization. Read its header (machine identifier + macOS version + commit hash of the run). Per §2: "No baseline = no PR 8."
4. **The diff:** from the worktree path `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd`, run `git log main..HEAD --oneline` and `git diff main..HEAD --stat`. Confirm the file list aligns with §6's "Create" + "Modify" tables.
5. **Cargo.lock:** `git diff main..HEAD -- Cargo.lock`. Verify only `criterion` (+ its transitive crates) was added. No `ndarray`, `simd-sys`, `packed_simd_2`, or any AGPL-licensed crate.

Do NOT actually run `cargo bench` from the audit shell unless you have time budget — Criterion benches take 5–20 minutes per spot. If you skip the bench run, you MUST instead verify the baseline.json hard gate by reading the implementer's pr_report.md perf-results table and cross-checking it against the baseline.json header (machine identity must match between the two runs).

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. HIGH-PROB items (1, 2, 3, 4, 7 — the correctness core) MUST receive paragraph-level discussion even if no defect is found.

1. **NEON intrinsic correctness on M-series (Apple Silicon aarch64).** [must-fix on incorrect intrinsic use]
   - `crates/cfr_core/src/simd.rs` uses ONLY `std::arch::aarch64` intrinsics: `vld1q_f64`, `vst1q_f64`, `vaddq_f64`, `vsubq_f64`, `vmulq_f64`, `vfmaq_f64`, `vmaxq_f64`, `vminq_f64`, `vdupq_n_f64`, `vgetq_lane_f64`, `vpaddq_f64`. No inline assembly (forbidden per §3).
   - **`Vec4f64` represents 4 lanes of f64 via 2× `float64x2_t` (NEON has 128-bit registers = 2 f64 lanes; the "4-wide" name is a logical abstraction over 2 NEON regs).** Verify the storage is `float64x2x2_t` or two separate `float64x2_t` fields. If the implementer used a single `float64x2_t` and called it "Vec4f64", that's a naming bug — flag should-fix.
   - **Every `unsafe { ... }` block has a `// SAFETY:` comment** explaining the alignment + length invariant. No unsafe outside `simd.rs`.
   - **Probe:** `grep -nE 'unsafe\s*\{' crates/cfr_core/src/simd.rs` — each hit should be followed by a `// SAFETY:` line within 2 lines.
   - **Probe:** `grep -rE 'unsafe\s*\{' crates/cfr_core/src/ --include='*.rs' | grep -v simd.rs` — expected empty (no unsafe outside simd.rs).
   - **Scalar fallback** gated by `#[cfg(not(target_arch = "aarch64"))]` exists for x86_64 CI compat.
   - **Evidence stub:** `crates/cfr_core/src/simd.rs:?` (`Vec4f64` definition; intrinsic call sites; SAFETY comment lines; cfg-gated fallback).

2. **Cache-blocking ordering: actually helps, not hurts cache misses.** [must-fix on perf regression; should-fix on micro-bench gap]
   - `crates/cfr_core/src/layout.rs` defines `FlatInfosetStore` per §4. Single bucket's actions are contiguous (stride = `num_actions`). Single tree node's bucket × action matrix is contiguous.
   - `const BLOCK_SIZE: usize = 64;` exists (or with a brief comment justifying any divergence from §4's 64-infoset block recommendation).
   - **Verify SoA primary path:** `regret_sum: Vec<f64>` and `strategy_sum: Vec<f64>` are SEPARATE flat arrays (not interleaved AoS). If implementer chose AoS instead of the §4-recommended SoA, they MUST justify in `pr_report.md` with microbench data showing AoS won — without the data, flag as should-fix.
   - **Verify the indexing formula:** `node_offset[n] + bucket_id * node_actions[n] + action` (per §4 "Indexing & strides"). Single multiply + single add per access. If implementer added a div, mod, or HashMap lookup, that defeats the purpose — must-fix.
   - **Verify the HashMap path is REMOVED** (not coexisting). Per §4 "Migration path": "Once parity is confirmed and benches pass, the HashMap path is deleted in the same PR." A coexisting HashMap path = scope leak (build complexity creep) → should-fix.
   - **Probe:** `grep -nE 'HashMap<String,\s*InfosetData>' crates/cfr_core/src/` — expected empty (no remaining HashMap-keyed infoset storage).
   - **Probe:** confirm the layout parity test (`tests/test_layout.rs`) runs both Kuhn (12 infosets) and Leduc (288 infosets) and asserts `1e-12` per-infoset strategy parity (per §7 Layer B).
   - **Evidence stub:** `crates/cfr_core/src/layout.rs:?` (FlatInfosetStore definition + BLOCK_SIZE const + indexing fn); `tests/test_layout.rs:?` (parity assertion line).

3. **Public chance sampling correctness vs unsampled reference.** [must-fix on biased estimator]
   - `crates/cfr_core/src/pcs.rs` implements `PCSSampler::sample_public(node) -> (Card, f64)` returning the sampled outcome AND the importance weight `K` (= number of outcomes at that chance node, per §5 "Importance weighting").
   - **Verify the importance weight is applied** at the call site (in `dcfr.rs`'s chance-node recursion when `use_pcs=true`). If the weight is computed but never multiplied into the value/regret update → biased estimator, must-fix. Per §5: "**The convergence-to-Nash guarantee requires this importance correction.**"
   - **Negative-control test exists and passes** (per §7 Layer C): a test that removes the importance weight and asserts the convergence test FAILS. This prevents silent regressions. If the negative-control test is absent or doesn't fail-as-expected → should-fix (the tolerance is uncalibrated).
   - **β-switch on PCS path:** `use_pcs=true` → β internally switches from 0.0 to 0.5 (per §5 "DCFR-PCS parameter compatibility" + §9 #4). A test sets `use_pcs=true` and asserts `solver.beta == 0.5` after construction.
   - **Verify private chance is NOT sampled.** Per §5 "Hand pairs stay vector-form": only PUBLIC chance is sampled; private (hole-card combos) stays enumerated as full vector-form CFR. If the implementer sampled both → that's external sampling MCCFR, not PCS — different algorithm — must-fix.
   - **Convergence test (Leduc, 5 seeds, 10K iter PCS vs 2K iter full):** per-action mean abs error < `5e-3`, per-action max < `2e-2`, cross-seed mean of per-seed mean errors < `5e-3` (per §7 Layer C).
   - **Default `use_pcs=false`:** verified opt-in (per §5 "Default" + §11 #2). `HUNLConfig.use_pcs: bool = False` in both `crates/cfr_core/src/hunl_solver.rs` (Rust) AND `poker_solver/hunl.py` (Python — per §6 "Modify" + I6 amendment).
   - **Evidence stub:** `crates/cfr_core/src/pcs.rs:?` (sampler + weight + β-switch); `crates/cfr_core/src/dcfr.rs:?` (weight multiplication at chance node); `tests/test_pcs.rs:?` (convergence + negative-control); `poker_solver/hunl.py:?` (`use_pcs: bool = False` field).

4. **Determinism: no thread-scheduling drift, no HashMap iteration drift.** [must-fix on flaky cross-run output]
   - PR 8 is **single-threaded** per §11 #10 ("Should PR 8 add multi-threading (rayon) to the DCFR walker? Recommended: no — out of scope."). If the implementer added rayon parallelism on the hot loop → scope leak, must-fix.
   - **HashMap iteration:** the new `FlatInfosetStore` is Vec-backed and iteration-deterministic. Any remaining HashMap (e.g., `PCSSampler.public_outcomes_per_node`) MUST be iterated in a sort-stabilized order (e.g., `BTreeMap` or `Vec::sort_by_key` before consumption) when the iteration order affects FP-summation order.
   - **PCS RNG:** `ChaCha8Rng` with explicit `seed: u64 = 7` default (per §11 #7). Same seed → same sequence of sampled cards on aarch64 AND x86_64 (cross-platform reproducibility test per §10 #9). A unit test runs the sampler with `seed=7` and asserts the first 100 sampled cards match a recorded fixture.
   - **SIMD tail handling determinism:** length-N slice processes `N / 4` chunks via SIMD + `N % 4` via scalar. The horizontal_sum within each chunk sums lanes in a fixed order (per §10 #5); the scalar tail adds at the end in fixed order. Two runs on the same input → bit-identical output.
   - **Probe:** `grep -rnE 'rayon::|par_iter|par_chunks' crates/cfr_core/src/ --include='*.rs'` — expected zero hits (no rayon added by PR 8). If PR 6 already added rayon, audit confirms PR 8 didn't EXTEND rayon usage.
   - **Probe:** verify the layout parity test (`tests/test_layout.rs`) and PCS convergence test (`tests/test_pcs.rs`) both pass on TWO consecutive runs (no flakes). Implementer's `pr_report.md` should cite cross-run determinism.
   - **Evidence stub:** `crates/cfr_core/src/pcs.rs:?` (ChaCha8Rng seed handling); `crates/cfr_core/src/simd.rs:?` (horizontal_sum impl); `tests/test_pcs.rs:?` (seed determinism test).

5. **Cargo.lock + dependency audit (no new AGPL).** [must-fix on AGPL contamination]
   - Only NEW direct dep is `criterion = "0.5"` as a dev-dep (per §6 "Modify" Cargo.toml row + §11 #8). No new runtime deps. No `ndarray`, no `simd-sys`, no `packed_simd_2`, no `rayon` (if not already in main), no postflop-solver-derived crate.
   - **Probe:** `git diff main..HEAD -- Cargo.toml crates/cfr_core/Cargo.toml` — only `criterion` addition expected.
   - **Probe:** `git diff main..HEAD -- Cargo.lock | grep -E '^\+name = ' | head -50` — list newly-introduced crates; cross-check each against criterion's known transitive dep tree (https://crates.io/crates/criterion). Any crate not in criterion's tree → flag for source license check.
   - **AGPL grep:** `references/code/postflop-solver/` is AGPL — no code copied. The implementer cited it for "pattern inspiration" (`chunks_exact + remainder` shape). Verify no verbatim or near-verbatim sequence in `simd.rs`. Recommended probe: `grep -F "scratch.prefix" crates/cfr_core/src/simd.rs` (postflop-solver-specific identifier — expected zero hits); also compare function-name shapes (e.g., `apply_swap_to_strategy`, `compute_strength_indices`) — none should appear verbatim in PR 8's diff.
   - **MIT attribution check:** if `references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp:90-131` was ported (per §3 "Reference pattern" + §11 #13), the file header MUST contain an MIT-attribution comment citing `references/code/noambrown_poker_solver/LICENSE`. Missing attribution → must-fix.
   - **Evidence stub:** `Cargo.toml:?` (criterion line); `Cargo.lock:?` (new crate entries); `crates/cfr_core/src/simd.rs:?` (file-header attribution comment if MIT port).

6. **Differential test stays green vs Python tier (Layer D).** [must-fix on tolerance drift or test failure]
   - `tests/test_pr8_convergence.py` exists. Runs the existing `tests/test_dcfr_diff.py` river-spot test with the OPTIMIZED Rust solver (SIMD + cache-blocked layout enabled, PCS off).
   - **Tolerance:** `5e-3` per-action — MATCHES `tests/test_leduc_diff.py` (per §7 Layer D: "No tolerances are weaker than the existing Python ↔ Rust diff test"). Any loosening = must-fix.
   - **Verify the test asserts against `solve_hunl_postflop(use_pcs=False, ...)`** — Layer D tests the non-PCS optimized path. PCS convergence is Layer C (Leduc).
   - **Verify the test passes** in the implementer's report; if any agent reports it as flaky or marked `@pytest.mark.xfail`, must-fix.
   - **Probe:** `grep -nE '@pytest.mark.xfail' tests/test_pr8_convergence.py` — expected empty.
   - **Probe:** `grep -nE '5e-?3|0\.005' tests/test_pr8_convergence.py` — expected at least one hit (the tolerance constant).
   - **Evidence stub:** `tests/test_pr8_convergence.py:?` (test body + tolerance assertion).

7. **Perf regression check: must show speedup, not regression.** [must-fix on regression; must-fix on baseline missing]
   - **Hard gate:** ≥10× wall-clock speedup on §2 spot 4 (HUNL flop standard, 5 bet sizes, 100 BB, 256/128/64 buckets) vs `benches/baseline.json`. Per §8 Integration step #2: "PR does not ship until the 10× gate passes."
   - **Soft gate:** ≥30× on either spot 3 or spot 4 (stretch target). Per §11 #3: "Hard gate at 10× on standard HUNL flop... stretch at 50×".
   - **Baseline.json hygiene:** `benches/baseline.json` committed. Header includes: macOS version, model identifier (e.g., "MacBookPro18,1" / "Mac14,7"), thermal state at run start, date, commit hash of the bench run. Per §2 "Methodology" + §9 #8: "Baseline `benches/baseline.json` must be committed before any optimization lands."
   - **Same machine for pre/post:** the baseline must be captured on the SAME machine as the post-PR perf run. The implementer's `pr_report.md` perf-results section MUST cite both machine identifiers; if they differ → invalid comparison, must-fix.
   - **Iteration-only time:** the bench must measure steady-state CFR iteration cost, NOT end-to-end including setup. Per §10 #11: "Agent B's Criterion harness measures iteration-only time using `Criterion::bench_function`'s setup hook." Verify via `benches/cfr_bench.rs:?` — setup is in a closure outside the benchmarked region.
   - **Stddev report:** Criterion reports mean ± stddev. High stddev (>20% of mean) triggers re-run; the implementer's report should document stddev alongside mean.
   - **Probe:** read `benches/baseline.json` header — confirm machine ID + date + commit-hash + thermal state present.
   - **Probe:** the implementer report's "perf results" table — extract speedup figures, confirm ≥10× on spot 4.
   - **Evidence stub:** `benches/baseline.json:?` (header); `benches/cfr_bench.rs:?` (iteration-only-time bench setup); `docs/pr8_prep/pr_report.md` (speedup table).

8. **SIMD scalar-parity (Layer A — bit equality).** [must-fix on bit drift]
   - `tests/test_simd.rs` exhaustively tests `Vec4f64` ops against scalar equivalents on: aligned 4-element inputs; length-7 inputs (tail handling); edge values (0.0, -0.0, NaN, +Inf, -Inf, smallest denormal); 1000 random uniform trials (seeded).
   - **Pass criterion:** `result_simd[i].to_bits() == result_scalar[i].to_bits()` (EXACT bit equality, not approximate float compare).
   - **FMA exception:** ULP ≤ 1 allowed ONLY for the explicit `vfmaq_f64` op (Inf-precision FMA differs from round-after-multiply at LSB). Default is exact equality for all non-FMA ops. Per §7 Layer A.
   - **NaN propagation:** test asserts NaN inputs produce NaN outputs (not 0.0 or undefined).
   - **Signed-zero preservation:** test asserts -0.0 input preserves sign bit.
   - **Probe:** `grep -nE 'to_bits\(\)' tests/test_simd.rs` — expected multiple hits (exact-bit-compare pattern).
   - **Probe:** `grep -nE 'f64::NAN|f64::INFINITY|f64::NEG_INFINITY' tests/test_simd.rs` — expected hits for edge-value tests.
   - **Evidence stub:** `tests/test_simd.rs:?` (test body + tolerance scheme).

9. **DCFR algorithm preserved bit-for-bit on the non-PCS path.** [must-fix on algorithmic drift]
   - Per §1 "Non-goals": "No algorithmic change beyond the three opt'ns. The DCFR(α=1.5, β=0, γ=2.0) loop is preserved bit-for-bit on the non-PCS path; PCS path switches to β=0.5."
   - `crates/cfr_core/src/dcfr.rs`: the regret-matching + strategy-accumulation logic is THE SAME as pre-PR-8, just routed through `simd::*` ops. Verify by reading the diff: every `f64 += ...` line should now be a `simd::fma_scalar_vec` or `simd::regret_matching_simd` call; no NEW arithmetic introduced.
   - **Probe:** `git diff main..HEAD -- crates/cfr_core/src/dcfr.rs | grep -E '^[+-]' | wc -l` — expect 100-300 lines of diff (rewriting hot loop call sites + swapping HashMap → FlatInfosetStore). >500 lines → flag for review.
   - **Probe:** the existing Kuhn + Leduc tests (pre-PR-8) MUST pass unchanged with the new storage + SIMD path. Verify via the implementer's pr_report.md "tests pass" section.
   - **Evidence stub:** `crates/cfr_core/src/dcfr.rs:?` (rewritten hot loop call sites; no new arithmetic).

10. **No `unsafe` outside `simd.rs`.** [must-fix on stray unsafe]
    - Per §1 "Non-goals" + §9 #3: "**No `unsafe` outside SIMD intrinsics wrappers.** Every `unsafe` block in `simd.rs` carries a `// SAFETY:` comment; the rest of the codebase remains safe Rust."
    - **Probe:** `git diff main..HEAD --stat -- crates/cfr_core/src/*.rs` then for each modified file other than `simd.rs`: `git diff main..HEAD -- <file> | grep -E '^\+.*unsafe'` — expected empty.
    - **Allowance:** `layout.rs` MAY contain `get_unchecked` IF profile-justified AND each call site has an explicit `// SAFETY:` comment. Default is checked indexing (`slice[i]`). Per §9 #3 + §10 risk discussion.
    - **Evidence stub:** `git diff main..HEAD` grep output.

11. **Clippy + format clean.** [must-fix on warning]
    - `cargo clippy --all-targets -- -D warnings` clean on the worktree.
    - `cargo fmt --check` clean.
    - Per §8 Agent A/B/C acceptance gates.
    - **Probe:** `cd /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd && cargo clippy --all-targets -- -D warnings 2>&1 | tail -20` — expected "no warnings".
    - **Evidence stub:** clippy output.

12. **HUNLConfig schema extension wired (PR 6 / PR 8 / PR 9 alignment).** [must-fix on schema break]
    - Per §6 "Modify" Python row + I6 amendment: `poker_solver/hunl.py` adds `use_pcs: bool = False` to `HUNLConfig` dataclass.
    - PR 6 §4.1 pre-emptively mirrors this in the Rust `HUNLConfig` — verify both sides exist and the default is `False` (opt-in).
    - **Probe:** `grep -n 'use_pcs' poker_solver/hunl.py crates/cfr_core/src/hunl_solver.rs` — expected one hit each on the field declaration.
    - **Probe:** confirm no existing field was renamed or repurposed (schema-additive only).
    - **Evidence stub:** `poker_solver/hunl.py:?`; `crates/cfr_core/src/hunl_solver.rs:?`.

13. **No scope creep (engine vs perf vs MCCFR).** [must-fix on scope leak]
    - PR 8 does NOT add MCCFR / external sampling beyond PCS (per §1 "Non-goals"). PCS is specifically public-chance only; if the implementer added private-chance sampling or action sampling, scope leak.
    - PR 8 does NOT add GPU code (per §1 "Non-goals").
    - PR 8 does NOT add node locking, exploitative play, or real-time depth-limited search (per §1 "Non-goals").
    - PR 8 does NOT add multi-threading (per §11 #10).
    - PR 8 does NOT add new card abstraction (per §1 "Non-goals" — reuses PR 4's EMD bucketing).
    - PR 8 does NOT change Kuhn / Leduc (kept as parity tests).
    - **Probe:** `git diff main..HEAD --stat -- poker_solver/dcfr.py poker_solver/abstraction/ poker_solver/charts/` — expected empty (Python algorithm + abstraction unchanged).
    - **Probe:** the `noambrown_poker_solver/cpp/src/mccfr.cpp` is cited in §5 as a "structural mirror" for the recursive shape, but PCS is DIFFERENT from ES-MCCFR — verify the implementation does PCS-not-MCCFR.
    - **Evidence stub:** `git diff --stat` output.

14. **Baseline.json committed BEFORE any optimization.** [must-fix on baseline missing]
    - `benches/baseline.json` exists in the diff and was the FIRST commit on the branch (per §2 "No baseline = no PR 8" + §8 Agent B "Baseline capture step" + §9 #8).
    - **Probe:** `git -C /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd log --oneline main..HEAD --format='%h %s' -- benches/baseline.json` — confirm the baseline was committed on a dedicated early commit.
    - If baseline.json was committed late (alongside optimization work), the perf comparison is suspect — flag as should-fix at minimum, must-fix if no commit-hash header proves baseline was captured against unoptimized code.
    - **Evidence stub:** `git log` output; `benches/baseline.json:?` header showing baseline commit hash.

15. **PR 6 dependence resolved.** [should-fix on integration gap]
    - Per §6 "Note on PR 6 dependence": PR 8 modifies `crates/cfr_core/src/hunl_solver.rs` (PR 6's file). If PR 6 named it differently, Agent C's integration is a ~1-day adaptation.
    - Verify the file `hunl_solver.rs` (or whatever PR 6 named it) exists on main at `62c75d5` AND PR 8's diff modifies it correctly.
    - **Probe:** `git -C /Users/ashen/Desktop/poker_solver ls-tree main:crates/cfr_core/src/ | grep -i hunl` — confirm the postflop solver file landed on main.
    - **Evidence stub:** file listing.

16. **Test count and naming.** [should-fix on naming drift]
    - Per §6 "Create": 4 new Rust integration tests + 1 new Python test + 1 bench harness:
      - `tests/test_simd.rs` (Layer A: SIMD parity)
      - `tests/test_layout.rs` (Layer B: layout parity)
      - `tests/test_pcs.rs` (Layer C: PCS convergence + negative-control)
      - `tests/test_pr8_convergence.py` (Layer D: Python end-to-end)
      - `benches/cfr_bench.rs` (Criterion harness)
      - `benches/baseline.json` (artifact)
    - **Probe:** `ls /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd/tests/test_simd.rs tests/test_layout.rs tests/test_pcs.rs tests/test_pr8_convergence.py benches/cfr_bench.rs benches/baseline.json` — expected all 6 exist.
    - **Evidence stub:** `ls` output.

17. **Code size within budget.** [should-fix on bloat]
    - Expected diff: ~3000-5000 LoC across the 3 new modules + tests + bench. Heavily over-budget (>8000 LOC) indicates scope creep.
    - **Probe:** `git diff main..HEAD --shortstat`.
    - **Evidence stub:** `git diff --shortstat` output.

18. **Implementer report(s) accurate.** [should-fix on discrepancy]
    - For each of Agent A/B/C (or the consolidated `pr_report.md`):
      - File list cited matches `git diff --stat`.
      - LoC numbers match `git diff --shortstat`.
      - Perf-results table machine ID + commit hash matches `baseline.json` header.
      - Claimed test-pass status matches a clean `cargo test --release` + `pytest` run.
    - **For each discrepancy:** flag as should-fix + recommend implementer regenerate report from final diff.
    - **Evidence stub:** specific section in `pr_report.md` + corresponding `git diff` or test output.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_report.md` with this exact structure:

```markdown
# PR 8 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-8-simd
**Worktree:** /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd
**Branched-from:** main tip 62c75d5 (post-v1.0.0 GA)
**Diff size:** [N modified + M created files = ±X LoC total]

**Test status:** [cargo test --release pass/fail; pytest pass/fail; Layer A/B/C/D status]

**Perf gate:** [10× hard gate on spot 4: PASS/FAIL with figure; stretch 30-50× soft gate status]

**Implementer reports:** [reviewed; accurate / discrepancies noted]

## Item-by-item correctness verification (focus areas 1-18)

[Each: PASS/FAIL + file:line evidence + verification note. HIGH-PROB items 1/2/3/4/7 get paragraph-level discussion even if no defect.]

## Must-fix

[NEON intrinsic misuse; biased PCS estimator (missing importance weight); layout regression vs HashMap baseline; perf 10× gate fail; tolerance loosened below 5e-3; AGPL contamination; baseline.json missing or post-hoc captured; algorithmic drift on non-PCS path; stray unsafe outside simd.rs; clippy warnings. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[AoS picked without microbench justification; missing negative-control test; β-switch not tested; cross-platform RNG determinism untested; report discrepancies; suboptimal block size; missing MIT attribution; test naming drift; baseline.json committed late but with provable hash. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-18 matching the 18 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Perf gate verification

[Detailed analysis: machine identity match, stddev, per-spot speedup figures, baseline.json header validation. Verdict on the 10× hard gate.]

## Spec coverage gaps (missing tests)

[Items in pr8_spec.md not covered by tests. Each: spec section + what's missing + suggested follow-up.]

## License compliance

[Explicit statement: only criterion added as dev-dep; no AGPL code from postflop-solver; MIT attribution present if vector_eval.cpp was ported. Cite specific files + headers.]

## Implementer-report accuracy audit

[Cross-check pr_report files against actual diff. Discrepancies (file list, LOC, perf table, test status) listed here with severity.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification. Expected verdict given the 10× perf gate + the 3-orthogonal-optimization scope: READY-WITH-PATCHES is the modal outcome; READY is plausible if all four test layers green and perf gate clears; NOT-READY would indicate a failed 10× gate, biased PCS, or AGPL contamination — escalate to orchestrator before writing.]
```

## Severity rules

- **must-fix:** 10× perf gate fails on spot 4; PCS estimator biased (importance weight missing); baseline.json absent or commit hash doesn't match unoptimized code; NEON intrinsic misuse (correctness break); tolerance loosened below 5e-3 cluster; algorithmic drift on non-PCS path (Kuhn/Leduc regress); AGPL code copied from postflop-solver; stray unsafe outside simd.rs; clippy warnings; Layer D (Python ↔ Rust diff) fails. Blocks PR.
- **should-fix:** AoS over SoA without microbench justification; missing negative-control test for PCS; β-switch untested; missing MIT attribution if vector_eval.cpp ported; pr_report.md discrepancies vs actual diff; cross-platform RNG determinism untested; block size off-spec without justification; baseline.json committed mid-branch instead of first; spec-coverage gaps. Doesn't block.
- **nice-to-fix:** style, naming, comments. Pure polish.

When in doubt: anything that breaks the 10× perf gate, breaks PCS-to-Nash convergence, or leaks AGPL into the diff → must-fix.

## Procedural notes

- **READ-ONLY DIFF REVIEW.** Cite **file paths and line numbers** for every finding. **Do NOT commit, push, or modify any code on `pr-8-simd`.** The only write allowed is `docs/pr8_prep/audit_report.md`.
- Inspect via the worktree path `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd` to avoid contending with the shared working tree. Per `feedback_no_concurrent_branch_ops` discipline: parallel agents may be active in the shared working tree; never `git checkout` to switch branches there.
- Quote spec section numbers when verifying claims (`pr8_spec.md` §2 / §3 / §4 / §5 / §7 / §8 / §9 / §10 / §11).
- Quote implementer-report section numbers when cross-checking deliverables (or quote pr_report_agent_a.md / agent_b / agent_c if reports are split).
- Scope-silent behavior → "Spec coverage gaps".
- HIGH-PROB risk surfaces (focus areas 1, 2, 3, 4, 7) MUST get paragraph-level discussion even with no defect found.
- For perf gate: if you DO have time to run `cargo bench` from the worktree, do it — but a static review of the implementer's perf table + baseline.json header is acceptable when budgeting against the audit's 30-60 min target.
- **No branch switches.** Stay in your audit shell. Inspect the worktree via absolute path; do not `git checkout main` on either the worktree or the shared tree.

Begin by reading the spec (`pr8_spec.md`), then the implementer report(s), then the diff (`git -C /Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd diff main..HEAD --stat`). Then write the report.

**Expected verdict given the 10× perf gate + the 3-orthogonal-optimization scope + LOCKED diff tolerances: READY-WITH-PATCHES is the modal outcome** (small bugs caught in audit are expected); READY is plausible on a clean run; NOT-READY would indicate the 10× gate failed, the PCS estimator is biased, or AGPL contamination was found — escalate to orchestrator before writing if you see any of these signals.
