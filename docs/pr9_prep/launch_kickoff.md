# PR 9 launch kickoff — HUNL preflop solve (Python + Rust tiers)

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 5 (HUNL postflop) and PR 4 (card abstraction) are both on `integration` and the user has approved firing PR 9.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when the PR 9 pre-flight clears. This doc collapses the universal launch runbook against the PR 9-specific shape into a single executable transcript so launch is mechanical, not improvisational. PR 9 is the **first end-to-end HUNL preflop → river deliverable** (Pluribus blueprint + subgame refinement pattern) and the largest fan-out to date (Python orchestrator + Python refiner + Rust port + all tests).

**Branch:** `pr-9-hunl-preflop` (per `pr_launch_runbook.md` §"PR 9" + PLAN.md §1 "Per-PR feature branches from PR 3 onward").

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` (post-2026-05-21 amendments — §6 is CANONICAL dispatch composition; tolerance cluster 5e-3 / 1e-3; <0.05 BB/hand exploitability target; `on_progress` kwarg patched in for PR 10b)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md`
- Launch-readiness verdict: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_readiness.md` (READY-WITH-PATCHES → patches applied → READY)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate (run BEFORE branch creation)

All six checks must pass. PR 9 has a heavier dependency surface than PR 6/7/8: it consumes both PR 4 (abstraction artifact) and PR 5 (postflop solver) directly.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 5 merged to integration (subgame refinement calls solve_hunl_postflop unchanged).
git fetch origin
git log --oneline integration -20 | grep -E "PR 5|hunl-postflop"
# Expected: "Integration: merge PR 5 (hunl-postflop)" merge commit present.

# 1b. PR 4 merged to integration (blueprint loads AbstractionTables; diff tests need tiny abstraction).
git log --oneline integration -20 | grep -E "PR 4|abstraction|precompute"

# 1c. integration tip matches origin/integration; working tree clean.
git rev-parse integration; git rev-parse origin/integration   # must match
git status                                                     # must be clean

# 1d. All PR 9 prompts present.
ls -la docs/pr9_prep/
# Expected: pr9_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md, launch_readiness.md.
# Verdict must be READY (originally READY-WITH-PATCHES; on_progress patch
# applied across all five files per launch_readiness Check 6).

# 1e. Reflog backup hash.
git rev-parse integration > /tmp/integration_pre_pr_9.hash
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green. Especially confirm `tests/test_hunl_postflop_*` and `tests/test_abstraction*` are green; PR 9 builds on both.

---

## 2. Branch creation

Branch name is hard-coded in `audit_prompt.md` — do NOT improvise.

```sh
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-9-hunl-preflop
```

Convention (PLAN.md §1 + runbook §"PR 9"): every PR from PR 3 onward gets its own feature branch from `integration`. `pr-9-hunl-preflop` is the exact spelling the audit prompt expects.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries are locked in each prompt, and the public-API contracts at §"Public API contract" in each agent prompt are the interface lock.

For each agent, the prompt is the **full contents of the corresponding `docs/pr9_prep/agent_{a,b,c}_prompt.md` file between the two `---` markers** (NOT the orchestrator header above the first `---`). Do not paraphrase, do not truncate, do not inline — copy the file body verbatim.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent tool call 1:
  description: "PR 9 Agent A — Python blueprint + preflop solver orchestrator"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_a_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 9 Agent B — Python subgame refiner + PR 5 integration"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_b_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 9 Agent C — Rust port + PyO3 + all Python tests"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_c_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership recap (verifies interface lock — do NOT relax these):**

| Agent | Owns (write/create) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `poker_solver/preflop_solver.py`, `poker_solver/blueprint.py` | `poker_solver/solver.py` (preflop dispatch branch per §6 canonical); `poker_solver/cli.py` (`--hunl-mode preflop` + new flags); `poker_solver/__init__.py` (re-exports); `poker_solver/hunl.py` (single new canonical-class chance generator method, opt-in) | `subgame_refiner.py`, any Rust file, any test file, `dcfr.py`, `hunl_solver.py`, `abstraction/*`, `charts/*` |
| B | `poker_solver/subgame_refiner.py` | (none) | `blueprint.py`, `preflop_solver.py`, `hunl.py`, `hunl_solver.py`, `dcfr.py`, any Rust file, any test file |
| C | `crates/cfr_core/src/preflop.rs`, `blueprint.rs`, `subgame.rs`; ALL test files (`tests/test_hunl_preflop_*.py`, `tests/test_preflop_diff.py`, `tests/fixtures/hunl_preflop_fixtures.py`) | `crates/cfr_core/src/lib.rs` (additive PyO3 bindings only) | any Python non-test file, existing Rust files, `Cargo.toml` |

**Parallel fan-out during agent runtime (per PLAN.md §5 + runbook §"Step 3"):** while A/B/C run, launch independent agents on downstream work so the orchestrator never idles. Candidates:
- PR 10a / PR 10b spec polish (NiceGUI UI surface — direct consumer of PR 9's `on_progress` kwarg).
- PR 11 (per-spot library) research / scaffolding — natural consumer of `PreflopSolveResult` as the serialization unit.
- `docs/autonomous_log.md` housekeeping (prune stale entries per continuous-pruning rule).
- Doc inventory sweep (verify no cross-PR references became stale after PR 5/6/7/8 merges).
- `precompute-blueprint` CLI tool spec (PR 9.5 follow-up per §15).

Aggregate per wave — do NOT react agent-by-agent. Wait for all three implementation agents to return, then synthesize the result vector in one pass.

---

## 4. Monitor + reconciliation patterns

While agents run, the orchestrator does NOT block. Track agent completion via the standard background-task notification stream. Specific failure signatures to watch for in agent outputs:

### 4a. `HUNLConfig` range-attachment + warm-start hook into PR 5

**Symptom:** Agent B reports a contract gap — `HUNLConfig` may not expose `range_p0` / `range_p1` fields (needed for refinement input ranges per §8.4), AND/OR `solve_hunl_postflop` (PR 5) may not admit a warm-start kwarg (needed for §8.3 regret preload).

**Recovery (range gap):** Agent B's prompt §"Default decisions" + §"Critical correctness items" §1 authorize `dataclasses.replace` + whatever range-attachment hook PR 5 already exposes; failing that, Agent B files an interface adjustment note and Agent A surgically adds the additive field to `HUNLConfig` (Agent A owns hunl.py edits).

**Recovery (warm-start gap):** Agent B's prompt §"Default decisions" item 9 authorizes two paths: (1) **regret-warm preferred** — instantiate `DCFRSolver` directly, populate `solver.infosets[k].regret_sum` from blueprint state, drive `solver.solve(iterations)` manually; (2) **strategy-warm fallback** — derive approximate regret from blueprint's average strategy. Either way: `hunl_solver.py` (PR 5) stays frozen per spec §5.

### 4b. Canonical-class chance generator combinatorial weights wrong

**Symptom:** Agent C's `test_preflop_canonical_chance_weights_correct` reports the sum of outcome probabilities ≠ 1.0 (within 1e-9). Spec §13 risk row 6 flags this as a likely-bug-source.

**Common bugs:**
- Pair weights wrong: pairs are 6 combos each (C(4,2)), not 4 or 12.
- Suited (4 combos) vs offsuit (12 combos) miscount.
- Blocker accounting wrong: when hero holds AA, opponent AA combos drop to 0 (4-suit world); canonical-class abstraction must propagate via `(hero_combos × villain_combos_after_blockers) / total_pairs` weighting.

**Recovery:** Agent A re-derives from PR 4 §7.12 + PR 9 §5. The brute-force enumeration check in Agent A's verification commands is the hard gate. If sum is 0.99 or 1.01, the bias propagates to blueprint strategy and refinement can't fix it.

### 4c. Diff-test tolerance (5e-3 per-action + 1e-3 per-spot game value)

**Symptom:** `test_preflop_diff_*` fails the tolerance assertion.

**Diagnostic ladder:**
1. **Verify the tolerance is correct.** Per consistency review I3: `5e-3` per-action + `1e-3 × base_pot`. NOT `1e-4` (earlier-draft outlier). Audit focus area 2 flags `1e-4` as must-fix.
2. **Run blueprint-pass diff first.** If `test_preflop_diff_blueprint_strategies_match` fails, divergence is upstream; refinement diff is noise.
3. **Check canonical-class chance generator parity.** Python and Rust must produce bit-for-bit identical combinatorial weights.
4. **HashMap iteration order × float-accumulation order** (PR 6 §6c precedent) — use `ahash::AHashMap` with fixed seed under `#[cfg(test)]` or `BTreeMap`.

Silently relaxing tolerance below `5e-3` / `1e-3` is a must-fix anti-pattern.

### 4d. `on_progress` kwarg threading (THE single engine-side dependency from PR 10b)

**Symptom:** the callback is accepted by the function signature but never invoked. PR 10b's UI dispatch (`docs/pr10_prep/pr10b_spec.md` lines 152-156) calls `solve_hunl_preflop(config, iterations=iterations, on_progress=on_progress, **kwargs)`; silent drop means PR 10b ships with a hung progress bar.

**Required threading:**
- Agent A: `solve_hunl_preflop` invokes `on_progress(iteration, exploitability_bb, memory_snapshot)` every `log_every` iterations AND threads the callback into both `build_blueprint(...)` (blueprint pass) and `refine_subgame(...)` (refinement pass).
- Agent B: `refine_subgame` passes `on_progress` to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)`. If PR 5 doesn't yet expose the kwarg, the regret-warm path (§4a) lets Agent B invoke the callback from its own iteration loop.
- Agent C: Rust ports (`solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`) accept `Option<PyObject>` and invoke via `Python::with_gil` + `callable.call1(...)` per PR 6 precedent.

This is the SINGLE engine-side dependency PR 10b has on PR 9 — every other PR 10b consumer is UI-side. Audit focus area 16 catches silent drops as must-fix.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in same parallel wave.

### 5a. Interface drift reconciliation (runbook §"Step 4")

After ALL three agents return, run Agent C's tests against Agents A+B's implementations:

```sh
cd /Users/ashen/Desktop/poker_solver
cargo build --release   # confirm Rust builds clean
pip install -e .         # rebuild the PyO3 extension into the venv
pytest tests/test_hunl_preflop_blueprint.py -xvs
pytest tests/test_hunl_preflop_refinement.py -xvs
pytest tests/test_hunl_preflop_integration.py -xvs -m "not slow"
pytest tests/test_preflop_diff.py -xvs
cargo test --release --manifest-path crates/cfr_core/Cargo.toml
```

Typical drift patterns (per `docs/autonomous_log.md` S1–S5 from prior PRs, scaled up for PR 9's larger surface):
- Agent A's `BlueprintResult` shape vs Agent B's import expectation (e.g., Agent B expects `regret_tables` field on `BlueprintResult`; Agent A only exposed `strategy`). Rule: spec §4 is canonical; whichever agent diverged gets corrected.
- `HUNLConfig` range-attachment shape (see §4a above).
- `solve_hunl_postflop` warm-start kwarg gap (see §4b above).
- `ruff`/`black` formatting drift on Agent A's surgical edits to `solver.py` / `cli.py` / `hunl.py` — auto-fix: `ruff check --fix --unsafe-fixes poker_solver tests && black poker_solver tests`.
- `mypy --strict` Optional/Union edge cases at the preflop dispatch branch (`Optional[AbstractionTables]` propagation through `_tier_for_depth`).

After all fixes: `pytest -x -m "not slow"` MUST be fully green before proceeding to audit. The `slow`-marked tests (5 of them, per spec §10) run in nightly; not gating for the audit pass.

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
# In orchestrator's main shell:
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently, launch the audit agent:

```
Agent tool call (audit):
  description: "PR 9 audit — fresh reviewer, no implementation context"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

Audit writes its report to `docs/pr9_prep/audit_report.md`. While both run, fan out additional downstream-PR work per parallelization rule.

After both complete:
- Read `pr_report.md` (output of `check_pr.sh`). Confirm "ready for user review" with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/pr9_prep/audit_report.md`. **`must-fix` items are a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up with a TODO.

PR 9-specific must-fix triggers (per audit focus areas):
- Dispatch ordering violates PR 9 §6 canonical (push/fold doesn't short-circuit at ≤15 BB; postflop branch wins at 15 BB preflop; no >250 BB ceiling).
- Diff-test tolerance silently set to `1e-4` (must be `5e-3` / `1e-3`).
- Canonical-class combinatorial weights wrong (pairs/suited/offsuit miscount; blocker accounting wrong).
- Warm-start regret loading copies into mismatched infoset keys (cross-tree corruption).
- Memory leak across sequential subgame refinement (`del solver; gc.collect()` missing between calls).
- AGPL contamination (`postflop-solver` or `TexasSolver` code copied — must be architectural inspiration only).
- `dcfr.py` modified (must remain frozen; α=1.5, β=0, γ=2.0 unchanged).
- `hunl_solver.py` (PR 5) modified (must remain frozen).
- `on_progress` kwarg missing from any of `solve_hunl_preflop`, `build_blueprint`, `refine_subgame`, or their Rust counterparts — breaks PR 10b UI dispatch (audit focus area 16).
- PR 1–8 tests regress (the dispatch branch must not perturb Kuhn/Leduc/HUNL-postflop/push-fold).

### 5c. Commit (runbook §"Step 6")

```sh
cd /Users/ashen/Desktop/poker_solver
git status   # verify what is staged; confirm no .env / secrets / .npz blobs slipped in
git add poker_solver/ crates/cfr_core/ tests/ docs/pr9_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 9 surface
git commit -m "$(cat <<'EOF'
PR 9: HUNL preflop solve (Python + Rust tiers)

First end-to-end HUNL preflop → river deliverable. Blueprint + subgame
refinement (Pluribus pattern, Brown & Sandholm 2019). Python tier:
`blueprint.py` + `preflop_solver.py` + `subgame_refiner.py`. Rust tier:
`crates/cfr_core/src/{blueprint,preflop,subgame}.rs` mechanical port.

Dispatch composition (PR 9 §6 canonical, cross-referenced by PR 3.5 §6
and PR 5 §6): push/fold ≤15 BB → >250 BB ValueError → postflop (PR 5)
→ preflop (PR 9).

End-to-end exploitability target: < 0.05 BB/hand on Pio 100 BB
validation fixture. Diff-test tolerance: 5e-3 per-action + 1e-3 ×
base_pot per-spot game value (PR 6/7/8 cluster).

`on_progress: Callable[[int, float, MemoryReport], None] | None` kwarg
on `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` (Python +
Rust) for PR 10b UI dispatch.

Memory: 14 GB ceiling per solve; inherits PR 5's 10% psutil calibration.

License: MIT-only Rust. Pluribus paper cited. AGPL sources NEVER copied.

Test result: <X>/<X> pass. Audit: <M> must-fix, <S> should-fix.
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths.

### 5d. Push PR branch (runbook §"Step 7")

```sh
git push -u origin pr-9-hunl-preflop
```

Autonomous per the workflow rules. Branch visible at https://github.com/amaster97/poker_solver/tree/pr-9-hunl-preflop.

### 5e. Merge into integration (runbook §"Step 8")

```sh
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-9-hunl-preflop -m "Integration: merge PR 9 (hunl-preflop)"
git push origin integration
```

`--no-ff` mandatory (preserves PR-branch lineage in `git log --graph`).

If `git pull --ff-only` reports divergence: STOP. Another session pushed to `integration`. Investigate before merging — never `git merge` blind.

### 5f. Update PLAN.md trajectory (runbook §"Step 10")

In `/Users/ashen/Desktop/poker_solver/PLAN.md` §2 trajectory table: update PR 9's row to `landed on integration` + record branch name + note "first end-to-end HUNL preflop+postflop deliverable shipped." In `docs/autonomous_log.md`: append progress entry with timestamp + commit hash + test count + audit-finding-count.

Per plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Failure modes + recovery (PR 9-specific)

### 6a. Blueprint OOM at 100 BB

**Symptom:** `build_blueprint(...)` raises `MemoryError` at the 256/128/64 abstraction + 1-size/1-cap coarse menu.

**Causes:** card abstraction tier mismatch (256/128/64 artifact on 200 BB stack where tier calls for 128/64/32); blueprint menu accidentally inheriting full PR 3 menu (8 actions per node instead of coarsened 3 actions, exploding the tree ~27x over flop/turn/river); `_enumerate_preflop_hole_outcomes_canonical()` not actually opted into (blueprint walks the full 1.6M-combo generator instead of the 28,561 canonical-class generator).

**Recovery:** spec §12 surfaces three options in the `MemoryError` message: tighten tier (128/64/32 or 64/32/16); drop menu further (0-cap); reduce iterations. If canonical-class generator was not opted in, that's a must-fix on Agent A's `_build_coarse_hunl_config` — the blueprint builder MUST set the opt-in flag automatically (spec §14 #8).

### 6b. Sequential subgame refinement memory leak

**Symptom:** wall-clock memory monotonically rises across 50+ sequential `refine_subgame(...)` calls; eventually OOMs.

**Cause:** between calls, the previous solver's state is NOT being dropped. `del solver; gc.collect()` is missing OR a module-level cache pinned references.

**Recovery:** Agent A's `solve_hunl_preflop` orchestration MUST do explicit `del solver; gc.collect()` between subgames (spec §12). Agent B's `refine_subgame` MUST NOT leave behind module-level state (Agent B prompt §"Critical correctness items" §6). Audit focus area 9 catches this.

### 6c. Range extraction produces uniform ranges

**Symptom:** `test_refinement_ranges_extracted_correctly` fails — `p0_range["AA"]` ≈ `p0_range["72o"]` (both ~1/169), indicating Agent B's `_extract_ranges_from_blueprint` is returning the prior uniform distribution rather than the strategy-conditioned posterior.

**Cause:** missing the conditioning on `blueprint.strategy` in the reach-probability recurrence. Correct formula per spec §8.2:
```
p0_range[hand_class] = Σ_paths reach_prob(path_to_subgame_root | hand_class, blueprint.strategy) × P(hand_class)
```
If Agent B uses the prior alone, every subgame gets uniform ranges → wrong refined strategies → end-to-end exploitability fails.

**Recovery:** Agent B re-derives from spec §8.2 + Brown & Sandholm 2019 §"Counterfactual regret minimization". Sanity check: `p0_range["AA"] > 5 × p0_range["72o"]` on a 3-bet pot subgame.

### 6d. Warm-start corrupts refinement strategy

**Symptom:** `test_refine_subgame_parity_with_direct_postflop_solve` fails — refined strategy diverges from a direct PR 5 postflop solve by more than 5e-2 per action.

**Causes (diagnostic order):**
1. **Wrong action count.** Blueprint has 3 actions at infoset K (1-size menu); refinement has 8 (full menu). Spec §8.3 + Agent B prompt §"Critical correctness items" §2: ONLY transfer keys where action sets exactly match; drop the rest from warm-start.
2. **Infoset key normalization mismatch** between blueprint and refinement (PR 5 §7.3 is canonical format).
3. **Range extraction wrong** (see §6c).

**Recovery:** diagnose via `test_refinement_uses_full_action_menu` (§10.2 #3) first to confirm action-count rule; then `test_refinement_ranges_extracted_correctly` (§10.2 #5). If both pass, the divergence is in the warm-start regret-loading math.

### 6e. PyO3 build issues

**Symptom:** `maturin develop` / `pip install -e .` fails after adding new `crates/cfr_core/src/*.rs` modules.

**Causes:** missing `mod blueprint; mod preflop; mod subgame;` declarations in `crates/cfr_core/src/lib.rs`; `#[pyfunction]` signature drift on `on_progress: Option<PyObject>` (missing `Option<>` wrapper); wrong import path on internal Rust modules.

**Recovery:** read the maturin error trace; spec §11 Agent C deliverables + PR 6's lib.rs as the precedent. If Rust compiles but Python can't import `poker_solver._rust.solve_hunl_preflop_rust`, `#[pymodule]` is missing `m.add_function(wrap_pyfunction!(solve_hunl_preflop_rust, m)?)?;`.

---

## 7. Orchestrator decisions needed BEFORE this kickoff fires

None unresolved. Launch-readiness verdict is READY-WITH-PATCHES → patches applied → READY. The eleven spec-locked defaults that touched orchestrator-side discretion (§14 #1 hard cliff at 15 BB, #2 1-size/1-cap blueprint menu, #3 250 BB max, #4 1e-3 reach threshold, #5 50k blueprint iterations, #6 10k refine iterations, #7 no blueprint artifact in repo, #8 opt-in canonical-class generator, #9 `preflop` canonical / `full` deprecated synonym, #10 full-traverse DCFR, #11 Rust port required) are locked-with-default per `pr9_spec.md` §14 + the consistency-review record.

If the user wants to revisit any locked default before launch, that is the moment to do so (e.g., switch blueprint menu to 2 sizes — D2; or cap at 200 BB — D3). Default: launch as spec'd.

---

## 8. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` — canonical spec (read end-to-end before launch; especially §6 dispatch composition CANONICAL, §10.4 tolerance cluster, §7.4 end-to-end exploitability target, §12 memory budget + 10% calibration inheritance).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_a_prompt.md` — Agent A prompt body (Python blueprint + preflop orchestrator).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_b_prompt.md` — Agent B prompt body (Python subgame refiner + PR 5 integration).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_c_prompt.md` — Agent C prompt body (Rust port + PyO3 + all tests).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md` — audit agent prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_report.md` — written by audit agent (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_readiness.md` — READY-WITH-PATCHES → READY verdict.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook (§"PR 9" row).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` — PR 10b consumer of `on_progress` (lines 152-156 dispatch; the single engine-side dependency PR 10b has on PR 9).
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh` at repo root.
- `/tmp/integration_pre_pr_9.hash` — reflog backup hash (pre-flight 1f).
