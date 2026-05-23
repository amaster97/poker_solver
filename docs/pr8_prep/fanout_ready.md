# PR 8 fan-out — ready to fire

**Status:** PRE-STAGED. Do NOT execute until PR 6 is on integration AND user explicitly approves.
**Source playbook:** `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_kickoff.md` (canonical; this file is the orchestrator-side condensation).
**Per-PR-branch policy:** PLAN.md §1 — every PR from PR 3+ on its own feature branch from `integration`.
**Parallel-agent default:** PLAN.md memory `feedback_parallel_agents.md` — A/B/C launch in ONE tool-call wave.

---

## 1. Pre-flight gate

All must pass; any fail → STOP.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 6 merged to integration (PR 8 optimizes PR 6's Rust port).
git fetch origin && git log --oneline integration -5
# Expected: top commit "Integration: merge PR 6 (rust-hunl-postflop)".
# If absent: do NOT launch. Spec §10 risk 6 = 8a/8b fallback; preferred = wait.

# 1b. Integration tip == origin/integration (zero divergence).
git rev-parse integration && git rev-parse origin/integration

# 1c. Working tree clean.
git status

# 1d. PR 8 prompts current (all read).
ls docs/pr8_prep/   # pr8_spec.md + agent_{a,b,c}_prompt.md + audit_prompt.md + launch_{kickoff,readiness}.md

# 1e. benches/baseline.json does NOT exist (Agent B's Step 0 creates it).
test ! -f benches/baseline.json && echo OK

# 1f. Criterion NOT yet in Cargo.toml dev-deps (Agent A/B add it).
grep -n 'criterion' crates/cfr_core/Cargo.toml || echo "OK — added in PR 8"

# 1g. PR 7 (optional): does not gate PR 8. Confirm no overlap with
# simd.rs / layout.rs / pcs.rs / dcfr.rs / hunl_solver.rs.

# 1h. PR 6's hunl_solver.rs filename confirmed (Patch 2 of launch_readiness).
ls crates/cfr_core/src/hunl_solver.rs
# Different name → 2-line edit to agent_c_prompt.md BEFORE Agent C launch.

# 1i. Reflog backup.
git rev-parse integration > /tmp/integration_pre_pr_8.hash
```

---

## 2. Branch creation

```sh
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-8-neon-simd-pcs integration
git status   # expect: clean, on pr-8-neon-simd-pcs
git log --oneline -1  # expect: PR 6 merge commit
```

Note: `launch_kickoff.md` §2 names the branch `pr-8-simd-layout-pcs`; user instruction here specifies `pr-8-neon-simd-pcs`. **Use `pr-8-neon-simd-pcs`** per the explicit task; if `audit_prompt.md` hard-codes a different name (line 14 of audit_prompt.md says `pr-8-simd-layout-pcs`), patch audit_prompt.md line 14 to match BEFORE running audit, OR override branch name via orchestrator note when invoking audit agent.

---

## 3. Step 0 — baseline-first inversion (Agent B's FIRST commit)

**PR-8-specific deviation from PR 6/PR 7.** Embedded in agent_b_prompt.md lines 321-329, 466-473.

Sequence inside Agent B BEFORE any optimization:

1. Add criterion dev-dep to `crates/cfr_core/Cargo.toml`: `criterion = { version = "0.5", default-features = false, features = ["html_reports"] }`. (Agent A's prompt also owns this line; first-lander wins, other verifies no duplicate.)
2. Write `crates/cfr_core/benches/cfr_bench.rs` skeleton (compiles + runs, no opt). Five fns: `bench_kuhn`, `bench_leduc`, `bench_hunl_simple_flop` (64/32/16 buckets — NOT 50/64 per consistency review I7), `bench_hunl_standard_flop` (256/128/64), `bench_dcfr_diff_loop` (Decision 11.12).
3. Run `cargo bench --bench cfr_bench --manifest-path crates/cfr_core/Cargo.toml` on pre-PR-8 (post-PR-6) state.
4. Capture `benches/baseline.json` with metadata: machine, `sw_vers -productVersion`, `rustc --version`, `git rev-parse HEAD` (PR 6 tip), date, criterion version, warm_up=5, samples=20. Format: agent_b_prompt.md lines 298-319.
5. **CLEAN separate commit:** `bench: capture pre-PR-8 baseline on M?`. Do NOT bundle with refactor. Audit (audit_prompt.md §8) requires baseline.json as standalone diff artifact.
6. THEN begin `FlatInfosetStore` refactor + Layer B fixtures + `test_layout.rs` + `test_pr8_convergence.py`.

**Orchestrator verification:** Agent B's `pr_report.md` MUST show two commits — baseline-only, then refactor. One commit → contaminated → reject. Spec §2 line 47, §9 #8; audit §8 = must-fix on missing baseline.

---

## 4. Three-agent fan-out (parallel, same tool-call wave)

For each agent, the prompt is the **full text of `docs/pr8_prep/agent_{a,b,c}_prompt.md` between the two `---` markers** (skip the orchestrator header above the first `---`). Copy verbatim. All three launch in ONE tool-call block.

```
Agent tool call 1:
  description: "PR 8 Agent A — NEON SIMD module + scalar fallback + parity tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_a_prompt.md>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 8 Agent B — baseline.json (Step 0) THEN flat-array layout + DCFR refactor + Criterion bench + Layer B/D tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_b_prompt.md>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 8 Agent C — PCS sampler + hunl_solver integration + use_pcs Python field + β-switch + PCS tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_c_prompt.md>
  subagent_type: general-purpose
  run_in_background: true
```

Ownership (do NOT relax; full table in launch_kickoff.md §3):
- **A:** `simd.rs`, `tests/test_simd.rs`, `benches/simd_microbench.rs`; +lib.rs `pub mod simd;`, +Cargo.toml criterion dev-dep.
- **B:** `layout.rs`, `tests/test_layout.rs`, `tests/test_pr8_convergence.py`, `benches/cfr_bench.rs`, `benches/baseline.json`, `tests/fixtures/dcfr_{kuhn,leduc}_10k.json`; modifies `dcfr.rs` (HashMap→FlatInfosetStore + simd routing + `use_pcs: bool` STORAGE), `solver.rs`, lib.rs `pub mod layout;`.
- **C:** `pcs.rs`, `tests/test_pcs.rs`, `tests/fixtures/pcs_seed7_first100.json`; modifies `hunl_solver.rs` (PCS + importance-weight K), `dcfr.rs` (β-switch BEHAVIOR), lib.rs `pub mod pcs;`, `hunl.py` (`use_pcs: bool = False`), Cargo.toml (`rand`/`rand_chacha`).

Boundary risk: `use_pcs` STORAGE (Agent B) vs BEHAVIOR (Agent C) on `dcfr.rs` — agent_c_prompt.md lines 26, 481 cover this. Silent overlap → orchestrator reconciles per autonomous_log S1.

Parallel-fan-out during runtime (PLAN.md §5): while A/B/C run, schedule downstream-PR agents (PR 9 spec polish, log housekeeping). Aggregate per wave.

---

## 5. Monitor patterns

Background-task notifications; orchestrator does NOT block.

- **SIMD parity (Layer A):** failure modes = NaN-quieting (`f64::max` vs `vmaxq_f64`), signed-zero loss, horizontal-sum reduction order divergence. Anti-pattern: switching test to `f64::abs() < 1e-9` instead of `.to_bits() ==` → must-fix.
- **Layout parity (Layer B, 1e-12):** ladder = (a) Layer A bit-exact first, (b) golden fixture at PR-6 tip, (c) scalar-only run, (d) divergence magnitude. Anti-pattern: relaxing 1e-12.
- **PCS convergence (Layer C, 5e-3 mean / 2e-2 max, 5 seeds):** ladder = (a) importance weight K applied + negative-control FAILS without K, (b) β-switch active (`use_pcs=true` → `solver.beta == 0.5`), (c) uniform sampling, (d) ChaCha8Rng cross-platform via `pcs_seed7_first100.json`.
- **Benchmark deltas:** Agent B's `pr_report.md` reports mean ± stddev per spot vs baseline. Stddev > 10% mean → re-run. Hard gates: ≥10× on `hunl_simple_flop` (spec §1+§8); ≥3× SIMD over scalar (Agent A microbench).
- **PCS variance:** if fails at 10K iter, Johanson 2012 = ~5× more iter; if fails at 50K iter, importance weight or β-switch broken.

---

## 6. Quick sanity — 10× speedup gate measurability

Cumulative math:
- Pre-PR-6 baseline = pure Python DCFR (PLAN.md §1 for exact numbers).
- PR 6 measured = ~24× (Python → Rust port; bit-for-bit non-PCS path).
- PR 8 target = 10-50× on top of PR 6's Rust → cumulative ~240×-1200× Python-to-PR-8-Rust.

Gate is **genuinely measurable** because:
1. `benches/baseline.json` captured at PR-6 tip (post-PR-6, pre-PR-8) → measures ONLY the PR 8 layer, independent of the prior 24× layer.
2. Criterion with sample_size=20 + warm_up=5 → M-series variance typically <8% mean (no thermal throttle).
3. Spot 3 `hunl_simple_flop` (64/32/16 buckets, 1K iter) = primary 10× target; spot 4 `hunl_standard_flop` (256/128/64, 1K iter) = stretch 50×.
4. Negative control: if any per-layer measurement <3× (SIMD microbench, layout-vs-HashMap, or PCS-vs-enumeration), cumulative cannot reach 10× — PR does not ship (launch_kickoff.md §4e).

Per memory `feedback_no_extrapolate`: orchestrator measures per-layer BEFORE claiming multi-layer speedup. Agent B's `pr_report.md` MUST break out contributions.

---

## 7. After-launch — audit + commit (pointer)

Per `launch_kickoff.md` §5: audit agent runs in parallel with `scripts/check_pr.sh` → resolve must-fix → commit on `pr-8-neon-simd-pcs` (template §5c lines 227-254; explicit paths, no `git add -A`) → push → `--no-ff` merge to integration → update PLAN.md §2 + append `autonomous_log.md`. Per `feedback_plan_sync.md`: `cp ~/.claude/plans/poker_solver.md PLAN.md` before commit if plan edited.
