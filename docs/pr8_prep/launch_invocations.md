# PR 8 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until PR 6 has merged to `integration` (PR 7 ideally also landed) and the user has approved firing PR 8.

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 8. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_kickoff.md`. This file is the mechanical operations sheet — paste blocks in order. **Note the Step 0 baseline-first inversion in §3 — load-bearing PR-8-specific deviation.**

---

## 1. Pre-launch verification (run AFTER PR 6, ideally PR 7, lands; BEFORE branch creation)

All six checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip past PR 6 (and ideally PR 7) merge commit.
git fetch origin
git log --oneline integration -5
# Expected topmost commit: "Integration: merge PR 7 (noambrown-diff)" OR
# "Integration: merge PR 6 (rust-hunl-postflop)" if PR 7 not yet landed.
# Hard requirement: PR 6 present. PR 7 absence is non-blocking (PR 8 does not
# consume Brown wrapper); user-approve before firing without PR 7.
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1b. Branch pr-8-neon-simd-pcs does NOT yet exist.
git branch --list pr-8-neon-simd-pcs
# Expected: empty output.

# 1c. PR 6's hunl_solver.rs filename confirmed (load-bearing for Agent C).
ls -la crates/cfr_core/src/hunl_solver.rs
# Expected: file exists. If PR 6 used a different filename, edit
# agent_c_prompt.md "Strict file ownership" + "hunl_solver.rs modifications"
# sections to point at the actual filename BEFORE launching Agent C.

# 1d. Three-agent prompts + audit prompt present.
ls docs/pr8_prep/agent_{a,b,c}_prompt.md docs/pr8_prep/audit_prompt.md
# Expected: 4 files present.

# 1e. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_8.hash
echo "integration tip pre-PR-8: $(cat /tmp/integration_pre_pr_8.hash)"

# 1f. Working tree clean.
git status   # expect "nothing to commit, working tree clean"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green before branching.

---

## 2. Branch creation

Branch name `pr-8-neon-simd-pcs` is hard-coded in `docs/pr8_prep/audit_prompt.md` (line 14) — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-8-neon-simd-pcs
git status   # expect: clean tree, on pr-8-neon-simd-pcs
git log --oneline -1   # expect: PR 6 (or PR 7) merge commit
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave) — with Step 0 baseline-first inversion

All three implementation agents launch in the SAME tool-call block. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator header above the first `---`). Copy verbatim.

**LOAD-BEARING:** Agent B's first internal action is the baseline capture (Step 0), NOT optimization. Per `launch_kickoff.md` §7 + spec §2 ("No baseline = no PR 8") + audit must-fix triggers: orchestrator MUST verify Agent B's first commit on the PR branch is the `benches/baseline.json` capture commit BEFORE approving subsequent refactor work. Without baseline, the 10× speedup hard gate is unmeasurable.

```
Agent A — "PR 8 Agent A — NEON SIMD module + scalar fallback + parity tests"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 8 Agent B — Step 0 baseline + flat-array layout + DCFR refactor + Criterion bench"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 8 Agent C — PCS sampler + hunl_solver integration + PCS tests + Python schema"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `crates/cfr_core/src/simd.rs`, `tests/test_simd.rs`, `crates/cfr_core/benches/simd_microbench.rs` | `lib.rs` (`pub mod simd;`); `Cargo.toml` (criterion dev-dep) | `layout.rs`, `pcs.rs`, `dcfr.rs`, `solver.rs`, `hunl_solver.rs`, `benches/cfr_bench.rs`, `benches/baseline.json`, any Python |
| B | `layout.rs`, `tests/test_layout.rs`, `tests/test_pr8_convergence.py`, `benches/cfr_bench.rs`, `benches/baseline.json`, `tests/fixtures/dcfr_{kuhn,leduc}_10k.json` | `dcfr.rs`; `solver.rs`; `lib.rs` (`pub mod layout;`); `Cargo.toml` ([[bench]]) | `simd.rs`, `pcs.rs`, `hunl_solver.rs`, `hunl.py` |
| C | `pcs.rs`, `tests/test_pcs.rs`, `tests/fixtures/pcs_seed7_first100.json` | `hunl_solver.rs`; `dcfr.rs` (β-switch ONLY); `lib.rs` (`pub mod pcs;`); `hunl.py` (`use_pcs: bool = False`); `Cargo.toml` (rand) | `simd.rs`, `layout.rs`, `solver.rs`, `benches/*` |

**Parallel fan-out during runtime** (per parallel-agents-default + min-five-agents rules): launch independent downstream agents — PR 9 spec polish, autonomous_log pruning, PLAN.md trajectory sanity check, doc inventory sweep. Aggregate per wave.

---

## 4. Expected wall-clock: ~5-7 hours

Larger PR than PR 7 — three new Rust modules + Python schema edit + Criterion bench infrastructure + 10× speedup hard gate.
- Agent A: ~90-120 min (NEON intrinsics + bit-exact parity tests).
- Agent B: ~120-180 min (Step 0 baseline + FlatInfosetStore refactor + DCFR rewrite + Layer B 1e-12 parity).
- Agent C: ~60-90 min (PCS sampler + chance-node wiring + β-switch + Python schema).
- Concurrent execution: ~2-3 hours wall-clock for fan-out itself.
- Audit + check battery + reconciliation: ~60-90 min (includes `cargo bench` re-run for speedup verification).
- Commit + merge: ~10 min.

**Deliverables (PR surface):** ~1500-2500 LOC net add; three new Rust modules (`simd.rs`, `layout.rs`, `pcs.rs`); refactored `dcfr.rs`; integrated `hunl_solver.rs`; one Python field add (`HUNLConfig.use_pcs`); Criterion bench harness + `baseline.json` + golden fixtures. **10× speedup hard gate on Section 2 spot 4 — PR does not ship without it.**

---

## 5. Risk reminders specific to PR 8

- **Step 0 baseline-first (load-bearing).** Per `launch_kickoff.md` §7: Agent B's first commit must be `bench: capture pre-PR-8 baseline`. Refactor commits AFTER baseline. If contaminated, hard gate is meaningless.
- **SIMD bit-parity tolerance.** NEON `vmaxq_f64` is NaN-PRESERVING; Rust `f64::max` is NaN-QUIETING. Scalar fallback must mirror NEON bit-for-bit. Anti-pattern (audit must-fix): silently switching test to `f64::abs() < 1e-9`. Use `.to_bits() ==`.
- **PCS importance weighting.** `w = K` (47 for turn, 46 for river). Negative-control test must FAIL when weight removed; if it doesn't, weight isn't load-bearing → deeper bug.
- **10× speedup hard gate.** Section 2 spot 4. Common cause of <10×: compiler auto-vectorized scalar fallback (use `#[inline(never)]`); thermal throttling; Criterion stddev >10%.
- **AGPL contamination.** `references/code/postflop-solver/` is AGPL. NEVER copy verbatim function names or near-verbatim sequences from `utility.rs`. Pattern-only inspiration with explicit "no code copied" docstring.
- **Locked deps.** `rand = "0.8"`, `rand_chacha = "0.3"`, `criterion = "0.5"` (dev-only). No additional runtime deps. Lock exact `rand_chacha` version for cross-platform determinism (fixture at `tests/fixtures/pcs_seed7_first100.json`).
- **64/32/16 bucket tier.** Bench must use spec-locked tier, NOT `50/64` (consistency review I7).

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5a-5e. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation (build + test + bench).
cargo build --release --manifest-path crates/cfr_core/Cargo.toml
cargo test --release --manifest-path crates/cfr_core/Cargo.toml
pip install -e .   # rebuild PyO3 extension after Cargo.toml changes
pytest -x tests/
cargo bench --bench cfr_bench --manifest-path crates/cfr_core/Cargo.toml
# Verify ≥10× speedup on Section 2 spot 4 BEFORE proceeding to audit.

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 8 audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr8_prep/audit_report.md.

# 6c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; no .env / secrets / dist/ / .so build artifacts
git add crates/cfr_core/ benches/ tests/ poker_solver/hunl.py docs/pr8_prep/audit_report.md
git status   # re-verify
git commit -m "PR 8: NEON SIMD + cache-blocked layout + PCS for Rust HUNL solver"   # full message in launch_kickoff.md §5c

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-8-neon-simd-pcs
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-8-neon-simd-pcs -m "Integration: merge PR 8 (simd-layout-pcs)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
# Record measured speedup × on Section 2 spot 4.
```

`must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Full failure-mode + recovery patterns in `launch_kickoff.md` §6.

---

## 7. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt.md`
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/fanout_ready.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/launch_invocations.md`
- Baseline (committed by Agent B BEFORE refactor): `/Users/ashen/Desktop/poker_solver/benches/baseline.json`
- Reflog backup: `/tmp/integration_pre_pr_8.hash`
