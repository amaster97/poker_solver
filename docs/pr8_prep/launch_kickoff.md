# PR 8 launch kickoff — NEON SIMD + cache-blocked layout + PCS

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 6 has merged to `integration` and the user has approved firing PR 8.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when PR 6 lands and PR 8 is next on deck. This doc collapses §0–§8 of `docs/pr_launch_runbook.md` against the PR 8-specific shape into a single executable transcript so launch is mechanical, not improvisational.

**Branch:** `pr-8-neon-simd-pcs` (per `pr_launch_runbook.md` §"PR 8" + PLAN.md §1 "Per-PR feature branches from PR 3 onward").

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_readiness.md` (READY-WITH-PATCHES — 8/8 checks PASS, 2 non-blocking nice-to-fix)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate (run BEFORE branch creation)

All six checks must pass. If ANY fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 6 is committed AND merged to integration. PR 8 OPTIMIZES the Rust port
# from PR 6; `crates/cfr_core/src/hunl_solver.rs` must exist on integration
# before Agent C can modify it.
git fetch origin
git log --oneline integration -5
# Expected: topmost commit is "Integration: merge PR 6 (rust-hunl-postflop)".
# If not, PR 6 has not landed; do not launch PR 8. Spec §10 risk 6 documents
# an 8a/8b split fallback if PR 6 is absent — preferred path is to wait.

# 1b. integration tip matches origin/integration (zero divergence).
git rev-parse integration && git rev-parse origin/integration
# Both hashes equal. If not: `git pull --ff-only origin integration`, re-verify.

# 1c. Working tree clean.
git status   # Expected: "nothing to commit, working tree clean".

# 1d. All PR 8 prompts up to date.
ls -la docs/pr8_prep/
# Expected: pr8_spec.md (~504 lines), agent_{a,b,c}_prompt.md, audit_prompt.md,
# launch_readiness.md (verdict: READY-WITH-PATCHES).

# 1e. PR 6's hunl_solver.rs filename confirmed (Patch 2 from launch_readiness).
ls -la crates/cfr_core/src/hunl_solver.rs
# Expected: file exists. If PR 6 used a different filename (e.g., hunl.rs,
# postflop.rs), edit agent_c_prompt.md "Strict file ownership" + "hunl_solver.rs
# modifications" sections to point at the actual filename BEFORE launching
# Agent C. A 2-line edit suffices; spec §10 risk 6 documents the fallback.

# 1f. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_8.hash
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green before
branching. If red, PR 6 merge introduced a regression; investigate before
launching PR 8.

---

## 2. Branch creation

Mechanical. Branch name is hard-coded in `audit_prompt.md` (line 14) — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-8-neon-simd-pcs
git status   # expect: clean tree, on pr-8-neon-simd-pcs
git log --oneline -1  # expect: PR 6 merge commit
```

Branch convention rationale (PLAN.md §1 + runbook §"Per-PR specifics → PR 8"): every PR from PR 3 onward gets its own feature branch from `integration`, NOT `main`.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries locked in each prompt. **Crucially, Agent B has a Step-0 baseline capture as its first internal action** (see Section 7 for the explicit inversion vs PR 6 / PR 7).

For each agent, the prompt is the **full contents of `docs/pr8_prep/agent_{a,b,c}_prompt.md` between the two `---` markers** (NOT the orchestrator header above the first `---`). Copy verbatim.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent tool call 1:
  description: "PR 8 Agent A — NEON SIMD module + scalar fallback + parity tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_a_prompt.md>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 8 Agent B — flat-array layout + DCFR refactor + Criterion bench + baseline capture"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_b_prompt.md>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 8 Agent C — PCS sampler + hunl_solver integration + PCS tests + Python schema"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_c_prompt.md>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership recap (do NOT relax):**

| Agent | Owns (write/create) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `crates/cfr_core/src/simd.rs`, `tests/test_simd.rs`, `crates/cfr_core/benches/simd_microbench.rs` | `lib.rs` (`pub mod simd;`); `Cargo.toml` (`criterion = "0.5"` dev-dep) | `layout.rs`, `pcs.rs`, `dcfr.rs`, `solver.rs`, `hunl_solver.rs`, `benches/cfr_bench.rs`, `benches/baseline.json`, any Python |
| B | `crates/cfr_core/src/layout.rs`, `tests/test_layout.rs`, `tests/test_pr8_convergence.py`, `crates/cfr_core/benches/cfr_bench.rs`, `benches/baseline.json`, `tests/fixtures/dcfr_{kuhn,leduc}_10k.json` | `dcfr.rs` (HashMap swap + SIMD routing + `use_pcs` field storage); `solver.rs` (adapter); `lib.rs` (`pub mod layout;`); `Cargo.toml` ([[bench]] entries) | `simd.rs`, `pcs.rs`, `hunl_solver.rs`, `poker_solver/hunl.py` |
| C | `crates/cfr_core/src/pcs.rs`, `tests/test_pcs.rs`, `tests/fixtures/pcs_seed7_first100.json` | `hunl_solver.rs` (PCS at chance nodes); `dcfr.rs` (β-switch ONLY); `lib.rs` (`pub mod pcs;`); `poker_solver/hunl.py` (`use_pcs: bool = False` field); `Cargo.toml` (`rand`/`rand_chacha`) | `simd.rs`, `layout.rs`, `solver.rs`, `benches/*` |

**Parallel fan-out during agent runtime** (per PLAN.md §5 + runbook §"Step 3"): while A/B/C run, launch downstream-PR agents so orchestrator never idles. Candidates: PR 9 spec polish, `docs/autonomous_log.md` housekeeping, PLAN.md trajectory sanity check, doc inventory sweep.

Aggregate per wave — wait for all three implementation agents to return, then synthesize in one pass.

---

## 4. Monitor + reconciliation patterns

While agents run, orchestrator does NOT block. Track via background-task notifications.

### 4a. Cargo build errors

Common causes: missing `mod` declaration in `lib.rs` (each agent owns ONE line — verify Agent A's `pub mod simd;`, Agent B's `pub mod layout;`, Agent C's `pub mod pcs;` all landed); NEON intrinsic typo (`vmaxq_f64` etc. against Apple's NEON intrinsics docs); `rand`/`rand_chacha` version drift (spec §11 #7 locks `rand = "0.8"` + `rand_chacha = "0.3"`); unresolved import (`pcs.rs` imports `crate::layout::TreeNodeId` — Cargo handles dep order, but spec §3/§4/§5 are canonical for signatures).

### 4b. SIMD bit-parity test failure (Layer A)

Most common cause: NaN-propagation mismatch. NEON's `vmaxq_f64` is NaN-PRESERVING; Rust's `f64::max` is NaN-QUIETING. Agent A's scalar fallback must implement `scalar_max` to mirror NEON bit-for-bit (Agent A prompt lines 224-237). Also: signed-zero loss in `max(+0.0, -0.0)`; horizontal-sum reduction order divergence (must be left-associative pairwise per Agent A prompt lines 239-244); FMA allowance applied on non-FMA op (ULP≤1 only on explicit `fma`, exact bit equality elsewhere).

**Anti-pattern (audit will catch):** silently switching the test to `f64::abs() < 1e-9`. Spec §7 Layer A + audit focus area #1 + audit_prompt.md line 49: must-fix.

### 4c. Layout parity test failure (Layer B, 1e-12 tolerance)

**Diagnostic ladder:**
1. Verify Agent A's Layer A bit-exact tests pass first — if SIMD/scalar parity broken, downstream layout drift is noise.
2. Confirm golden fixtures captured pre-refactor (`"captured_commit": "<pre-PR-8 hash>"` in `tests/fixtures/dcfr_{kuhn,leduc}_10k.json`).
3. Run with scalar SIMD fallback explicitly — if parity holds against scalar but fails against NEON, Layer A test gap.
4. Examine actual divergence — if max diff is 1.5e-12 (just over spec), find the float-reduction-order divergence, do NOT loosen tolerance.

**Anti-pattern:** silently relaxing 1e-12. Audit focus area #6 + audit_prompt.md line 78: must-fix.

### 4d. PCS convergence test failure (Layer C, 5e-3 mean / 2e-2 max)

**Diagnostic ladder:**
1. Importance weighting first (Agent C prompt lines 342-351). Estimator `E[w·v(c)] = sum_c (1/K)·K·v(c) = sum_c v(c)` requires `w = K` (47 for turn, 46 for river). Without it, estimate is K× too small. Negative-control test (`test_pcs_negative_control_without_importance_weight_fails`) should FAIL when weight removed — if it doesn't fail, importance weight isn't load-bearing → deeper bug.
2. β-switch logic (Agent C prompt lines 196-204). `use_pcs=true` → solver internally sets β=0.5 (not 0.0). Test `test_pcs_beta_switch_to_half_when_enabled` asserts this.
3. Sampling distribution must be UNIFORM over K outcomes for `w = K` to be correct.
4. ChaCha8Rng cross-platform determinism — confirm seed-7 fixture matches `tests/fixtures/pcs_seed7_first100.json`.

**Anti-pattern:** silently relaxing below PR 6/7/9 `5e-3` / `1e-3` cluster (spec §7 Layer C + consistency review I3). Spec §7 line 337: "No tolerances are weaker than the existing Python ↔ Rust diff test."

### 4e. 10× speedup hard gate failure

Common causes: SIMD microbench <3× speedup (compiler auto-vectorized scalar fallback — use `#[inline(never)]` to defeat); `FlatInfosetStore` lookup arithmetic dominates (profile with `cargo flamegraph`); thermal throttling (Apple M-series; Criterion stddev should be <10% of mean).

**Diagnosis:** Agent B's `pr_report.md` should contain pre/post numbers per spec §10 risk 7. Re-run if stddev high. Hard gate failure after re-run → PR does not ship; investigate via flamegraph.

### 4f. PyO3 build / Python integration failure

Common causes: Python `HUNLConfig.use_pcs` added by Agent C but not threaded through `_serialize_hunl_config`; Rust-side `HUNLConfig::deserialize` doesn't include `use_pcs` (PR 6 §4.1 pre-mirrors this per consistency review I6 — verify `grep use_pcs crates/cfr_core/src/hunl.rs`); `maturin develop --release` not re-run after Cargo.toml changes.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in parallel.

### 5a. Interface drift reconciliation (Step 4)

```sh
cd /Users/ashen/Desktop/poker_solver
cargo build --release --manifest-path crates/cfr_core/Cargo.toml
cargo test --release --manifest-path crates/cfr_core/Cargo.toml
pip install -e .   # rebuild PyO3 extension
pytest -x tests/
cargo bench --bench cfr_bench --manifest-path crates/cfr_core/Cargo.toml
```

Typical drift: Agent A's `simd::*` signatures vs Agent B's `dcfr.rs` call sites (spec §3 + Agent A prompt §"Public API contract" canonical); Agent B's `FlatInfosetStore` API vs Agent C's `pcs.rs` import of `TreeNodeId` (spec §4 canonical); `ruff`/`black` drift on Agent C's `hunl.py` edit (`ruff check --fix --unsafe-fixes poker_solver && black poker_solver`); `mypy --strict` on `test_pr8_convergence.py`.

After fixes: `pytest -x` fully green AND `cargo bench` ≥10× speedup on Section 2 spot 4 before proceeding to audit.

### 5b. Audit + check battery in parallel (Step 5)

```sh
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently launch audit:

```
Agent tool call (audit):
  description: "PR 8 audit — fresh reviewer, no implementation context"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt.md>
  subagent_type: general-purpose
  run_in_background: true
```

Audit writes to `docs/pr8_prep/audit_report.md`. Fan out additional downstream work in parallel.

After both complete: read `pr_report.md` (all gates `OK`/`skip`, not `FAIL`); read `audit_report.md` (**must-fix items hard stop; should-fix/nice-to-fix deferrable**).

**PR 8-specific must-fix triggers** (audit_prompt.md §1-14):
- SIMD bit-parity violated (test uses `f64::abs() < 1e-9` instead of `.to_bits() ==`).
- PCS importance weighting missing; or negative-control test absent / not failing.
- `unsafe` block without `// SAFETY:` comment in `simd.rs`.
- `unsafe` ANYWHERE outside `simd.rs` (unless explicit profiled hotspot with SAFETY).
- `HUNLConfig.use_pcs` missing on Python side, wrong default, or not threaded through `_serialize_hunl_config`.
- Layout parity tolerance silently loosened beyond `1e-12`.
- `benches/baseline.json` missing from diff (PR cannot be reviewed for speedup claims).
- 10× speedup hard gate failed on Section 2 spot 4.
- New runtime dep beyond `rand = "0.8"` + `rand_chacha = "0.3"` (and `criterion = "0.5"` dev-only).
- AGPL contamination from `references/code/postflop-solver/` (verbatim function names or near-verbatim sequences from `utility.rs`).
- Bench uses `50/64` buckets instead of `64/32/16` tier (consistency review I7).

### 5c. Commit (Step 6)

```sh
cd /Users/ashen/Desktop/poker_solver
git status
git add crates/cfr_core/ benches/ tests/ poker_solver/hunl.py docs/pr8_prep/audit_report.md
git status
git commit -m "$(cat <<'EOF'
PR 8: NEON SIMD + cache-blocked layout + PCS for Rust HUNL solver

Performance optimization of the Rust HUNL solver (PR 6). No algorithmic
change on the non-PCS path; PCS path switches β=0 to β=0.5 internally per
Tammelin 2014 caveat.

Three orthogonal optimizations:
- NEON 128-bit SIMD (std::arch::aarch64): vectorized regret-matching,
  strategy accumulation, sign-conditional discount. Bit-exact vs scalar
  fallback (ULP≤1 on explicit FMA op only).
- Cache-blocked SoA infoset layout: FlatInfosetStore replaces
  HashMap<String, InfosetData>. BLOCK_SIZE=64 (fits M1 L1d).
- Public chance sampling: opt-in via HUNLConfig.use_pcs (default False).
  Importance weight w=K. ChaCha8Rng for cross-platform determinism.

License posture: MIT-only Rust source. noambrown_poker_solver (MIT) cited
for vector_eval; slumbot2019 (MIT) for flat-array layout; postflop-solver
(AGPL) NEVER copied — pattern-only inspiration with explicit "no code
copied" in simd.rs docstring.

Baseline: benches/baseline.json captured on <machine> at <commit>.
Speedup: <N>× on Section 2 spot 4. Hard gate ≥10× met.

Test result: <X>/<X> pass.
Audit: <m> must-fix, <s> should-fix, <n> nice-to-fix.
EOF
)"
```

DO NOT use `git add -A`/`.`. Stage explicit paths.

### 5d. Push (Step 7) + 5e. Merge (Step 8)

```sh
git push -u origin pr-8-neon-simd-pcs
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-8-neon-simd-pcs -m "Integration: merge PR 8 (simd-layout-pcs)"
git push origin integration
```

`--no-ff` mandatory. Divergence on `pull --ff-only` → STOP, investigate.

### 5f. Update PLAN.md + autonomous_log

Update `PLAN.md` §2 trajectory: PR 8 row → `landed on integration` + branch name + measured speedup. Append `docs/autonomous_log.md` entry with timestamp + commit hash + test count + audit-finding count + benchmark deltas. Per plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Failure modes + recovery (PR 8-specific)

### 6a. PR 6's `hunl_solver.rs` named differently

**Recovery:** preferred — 2-line edit to `agent_c_prompt.md` to name the actual file (verify pre-launch via Pre-flight gate 1e). Fallback — 8a/8b split: Agent C stubs the integration (`// TODO(PR 6 filename): wire PCSSampler at chance nodes when use_pcs=true`); PR 8a (SIMD + layout) lands without PCS integration; PR 8b (PCS integration) is ~1-day follow-up.

**Anti-pattern:** Agent C silently picking a filename and modifying it. Spec §10 risk 6 + Agent C prompt §"7. PR 6 absence" — Agent C MUST flag to orchestrator before touching a non-expected file.

### 6b. NEON intrinsic mis-named or unstable

`cargo build` fails with `cannot find function 'vfmaq_f64'` etc. Causes: typo (cross-reference Apple NEON intrinsics docs + spec §3 lines 89-94); MSRV too old (intrinsics stable since Rust 1.59 / Feb 2022); wrong `#[cfg(target_arch)]` gate (NEON code paths compiled on x86).

### 6c. Bench machine variance high (Criterion stddev > 10%)

Mitigations: close other apps, plug in MacBook, "High Power" Energy Saver; re-run with `sample_size = 50`; document stddev in `pr_report.md` per Agent B prompt line 580. Spec §10 risk 7 — Criterion controls but doesn't eliminate variance.

### 6d. `use_pcs` flag wiring confusion (Agent B / Agent C boundary)

Storage owned by Agent B (`pub use_pcs: bool` on DCFR config); behavior owned by Agent C (β-switch in `dcfr.rs` + PCS sampler call in `hunl_solver.rs`).

**Recovery:** grep `dcfr.rs` for `use_pcs` (should appear twice — config struct + β-init); grep `hunl_solver.rs` (chance-node visits); grep `hunl.py` (HUNLConfig field). Missing → responsible agent rewrites; orchestrator does NOT silently patch (autonomous_log S1 pattern).

### 6e. ChaCha8Rng cross-platform fixture diverges

`tests/fixtures/pcs_seed7_first100.json` captured on aarch64; CI on x86_64 fails determinism test. Causes: `rand_chacha = "0.3"` minor drift (lock exact version `=0.3.X`); endianness assumption; HashMap iteration leaking into test setup. Spec §9 #7 + Agent C prompt line 359 — do NOT silently regenerate per-platform.

---

## 7. Orchestrator decisions needed BEFORE this kickoff fires + EXPLICIT BASELINE-FIRST INVERSION

### Baseline-first inversion (the load-bearing PR-8-specific deviation from PR 6 / PR 7 pattern)

**PR 6 / PR 7 pattern:** branch → fan out three implementation agents in parallel → all three start optimization/refactor work immediately → audit + commit.

**PR 8 deviation:** branch → fan out three implementation agents in parallel, BUT **Agent B's very first action inside the agent is the baseline capture, not optimization.** Sequence inside Agent B (per Agent B prompt lines 321-329):

1. Write `crates/cfr_core/benches/cfr_bench.rs` skeleton with stubbed bodies that compile but don't optimize.
2. Confirm `cargo bench --bench cfr_bench` runs to completion on the pre-PR-8 (post-PR-6) state.
3. Capture `benches/baseline.json` with metadata: machine ID, macOS version, `rustc --version`, `git rev-parse HEAD` (pre-PR-8 commit), date.
4. **Commit `baseline.json` as a clean separate commit** (`bench: capture pre-PR-8 baseline on M?`) — NOT bundled with refactor commits.
5. THEN begin the `FlatInfosetStore` refactor + DCFR rewrite + Layer B test.

**Why this matters:**
- Spec §2 line 47: "No baseline = no PR 8."
- Spec §9 #8: "Baseline `benches/baseline.json` must be committed before any optimization lands. If the baseline is not present in the diff, the PR cannot be reviewed."
- Audit prompt §8 (lines 85-88): missing baseline = must-fix.
- The 10× speedup hard gate (spec §1 + §8 integration step) is meaningless without a reproducible pre-optimization measurement.

If Agent B begins the refactor before capturing the baseline, the measurement contaminates the optimization measurement (refactor already changed the codebase). **Orchestrator MUST verify Agent B's first commit on the PR branch is the baseline-only commit** before approving subsequent refactor work.

### Other decisions

None unresolved beyond the baseline-first inversion. Launch-readiness verdict is READY-WITH-PATCHES (8/8 checks PASS, 2 non-blocking nice-to-fix: clarification of PR 4+6 spec attribution; confirmation of PR 6's `hunl_solver.rs` filename per Pre-flight gate 1e).

The 15 spec-locked defaults (D1 NEON always-on, D2 PCS opt-in, D3 10× hard gate, D4 SoA primary, D5 block size 64, D6 per-iteration sampling, D7 seed=7, D8 Criterion, D9 commit baseline.json, D10 no rayon, D11 no SVE, D12 bench diff-test loop, D13 MIT-attributed vector_eval port OK, D14 silent β-switch, D15 gauntlet check) are locked-with-default per `pr8_spec.md` §11.

If user wants to revisit any locked default before launch (e.g., PCS default-on — D2, relax 10× gate to 5× — D3), that is the moment. Default: launch as spec'd.

---

## 8. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md` — canonical spec.
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_{a,b,c}_prompt.md` — agent prompt bodies.
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt.md` — audit prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_report.md` — written by audit agent.
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_readiness.md` — READY-WITH-PATCHES verdict.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook.
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh`.
- `/Users/ashen/Desktop/poker_solver/benches/baseline.json` — committed by Agent B BEFORE refactor (Section 7 baseline-first inversion).
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/dcfr_{kuhn,leduc}_10k.json` — Agent B golden fixtures for Layer B parity.
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/pcs_seed7_first100.json` — Agent C cross-platform determinism fixture.
- `/tmp/integration_pre_pr_8.hash` — reflog backup (pre-flight 1f).
