# PR 9 fan-out ready — HUNL preflop (both tiers)

**Status:** PRE-STAGED. Do NOT launch agents from this doc. Fires only after PR 5 + PR 6 are on `integration`, and ideally PR 7 too (external Nash validation). Largest single PR fan-out after PR 6: ~3-5 days per spec §9, owning ~1,300 Rust LOC + ~600 Python LOC + ~600 test LOC + four surgical edit sites.

**Inputs (all locked):**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md`
- Full playbook: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_kickoff.md` (this doc is the condensed launcher pointer; kickoff is the executable transcript)
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

---

## 1. Pre-flight gate

PR 9 fires only AFTER the following are on `integration`:

| Dependency | Why it must land first | Verify |
|---|---|---|
| **PR 5 (HUNL postflop)** | Agent B's `refine_subgame` calls `solve_hunl_postflop(...)` unchanged; `HUNLSolveResult` is the parent class of `PreflopSolveResult` | `git log --oneline integration | grep "PR 5"` |
| **PR 6 (Rust port)** | Agent C's mechanical port of blueprint + subgame reuses PR 6's `dcfr.rs` core + tree pattern + PyO3 callback-from-Rust precedent (`Python::with_gil`) | `git log --oneline integration | grep "PR 6"` |
| **PR 4 (card abstraction)** | Blueprint loads `AbstractionTables`; diff tests need the tiny abstraction fixture | `git log --oneline integration | grep -E "PR 4|abstraction"` |
| **PR 3.5 (push/fold chart)** | Dispatch short-circuit at ≤15 BB delegates to `pushfold.solve_pushfold(...)` | `git log --oneline integration | grep -E "PR 3.5|pushfold"` |
| **(Ideal) PR 7 (external Nash validation)** | External proof of solver correctness before deploying the biggest end-to-end deliverable; not strictly blocking but reduces risk surface | `git log --oneline integration | grep "PR 7"` |

**Integration tips:**
- After PR 6 lands, Rust port pattern (PR 6 `tree.rs`/`pcs.rs` modules + `lib.rs` PyO3 bindings) is the canonical template Agent C follows.
- Rust port is available for BOTH the blueprint pass AND subgame solves (reusing PR 6's postflop port).
- PR 9 prompts up to date: `on_progress: Callable[[int, float, MemoryReport], None] | None` kwarg patched into all three Python entrypoints + all three Rust entrypoints per launch-readiness Check 6 (PR 10b consumer at `docs/pr10_prep/pr10b_spec.md` lines 152-156).
- **Pluribus paper:** Agents A + B must read `references/papers/pluribus_brown_2019_science.pdf` pages 2-4 (blueprint pass + offline-batched refinement; PR 9 §16 cites exact passages).
- Working tree clean; integration tip matches origin/integration.
- Reflog backup hash: `git rev-parse integration > /tmp/integration_pre_pr_9.hash`.

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-9-hunl-preflop
```

Branch name is hard-coded in `audit_prompt.md` — do NOT improvise. Per-PR-branches rule (PLAN.md §1; never direct commits to main/integration).

---

## 3. Three-agent fan-out launch (parallel, same wave)

All three implementation agents launch in the SAME tool-call block (per `pr_launch_runbook.md` §"Step 2"). Each prompt is the **full body of its prompt file between the `---` markers** — no paraphrasing, no truncation, no inlining.

| Agent | Description | Prompt path | Owns |
|---|---|---|---|
| **A** | Python blueprint + preflop solver orchestrator | `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_a_prompt.md` | `preflop_solver.py`, `blueprint.py`; surgical: `solver.py` (preflop dispatch + >250 BB error), `cli.py` (`--hunl-mode preflop` + new flags), `__init__.py` (re-exports), `hunl.py` (canonical-class chance generator) |
| **B** | Python subgame refiner + PR 5 integration | `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_b_prompt.md` | `subgame_refiner.py` ONLY (wraps PR 5's `solve_hunl_postflop` with range extraction + warm-start regret loading) |
| **C** | Rust port + PyO3 bindings + ALL Python tests | `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_c_prompt.md` | `crates/cfr_core/src/{preflop,blueprint,subgame}.rs`; surgical: `lib.rs` (additive PyO3 bindings); ALL test files (`test_hunl_preflop_{blueprint,refinement,integration}.py`, `test_preflop_diff.py`, `fixtures/hunl_preflop_fixtures.py`) |

All three launched `run_in_background: true`. While they run, fan out to PR 10a/10b spec polish, PR 11 scaffolding, doc-inventory sweep, `precompute-blueprint` CLI spec (PR 9.5 follow-up per §15).

**Wait for all three to return before reacting**; aggregate per wave, do not greedy-schedule.

---

## 4. Critical context (PR 10b ties in here)

**`on_progress` kwarg** — already patched into PR 9 prompts (Agent A LOCKED #13; Agent B LOCKED #10; Agent C LOCKED #11; audit focus area 16):

- Signature on all three Python entrypoints: `on_progress: Callable[[int, float, MemoryReport], None] | None = None`.
- `solve_hunl_preflop` threads the callback to `build_blueprint(...)` AND `refine_subgame(...)`.
- `refine_subgame` passes through to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)`.
- Rust entrypoints (`solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`) accept `Option<PyObject>` and invoke via `Python::with_gil` + `callable.call1(...)` (PR 6 precedent).
- Silent drop (accepted but never invoked) = **must-fix** — breaks PR 10b UI dispatch (`docs/pr10_prep/pr10b_spec.md` lines 152-156); UI ships with hung progress bar.
- Cancellation NOT in this contract — PR 10a handles via separate flag.

**Dispatch composition canonical at PR 9 §6** (cross-referenced by PR 3.5 §6, PR 5 §6): push/fold ≤15 BB short-circuit → >250 BB ValueError → postflop (PR 5) → preflop (PR 9). Locked boundary tests: `test_preflop_dispatch_pushfold_at_15bb`, `..._solver_at_16bb`, `..._error_at_251bb`.

**Diff-test tolerance cluster:** `5e-3` per-action + `1e-3 × base_pot` per-spot game value (PR 6/7/8 cluster; consistency review I3). NOT `1e-4` — earlier draft outlier; audit must-fix if tightened silently.

**End-to-end target:** exploitability < 0.05 BB/hand on Pio 100 BB validation fixture (`test_combined_exploitability_under_0_05_bb_per_hand`, slow).

---

## 5. Monitor patterns (during agent runtime)

While A/B/C run, watch for these failure signatures (full diagnosis in `launch_kickoff.md` §4):

1. **Blueprint convergence:** exploitability_history trending down monotonically; final < 0.5 BB/100 on every reached preflop infoset at 50k iter; `< 5.0` BB/100 on relaxed CI 500-iter smoke.
2. **Subgame refinement:** `refine_subgame` parity with cold-start PR 5 within 5e-2 per action (`test_refine_subgame_parity_with_direct_postflop_solve`); warm-start reduces iterations vs cold-start (soft); range extraction non-uniform (`p0_range["AA"] > p0_range["72o"]` on 3-bet pot).
3. **Memory under 14 GB ceiling:** per blueprint solve AND per subgame refinement; `MemoryReport.rss_calibration_error <= 0.10` (PR 5 inheritance). Sequential subgame cleanup via `del solver; gc.collect()` between calls — leak = must-fix.
4. **Canonical-class chance weights:** `_enumerate_preflop_hole_outcomes_canonical()` outcome probabilities sum to 1.0 within 1e-9 (pairs=6 combos, suited=4, offsuit=12, blocker accounting). Off by 0.01 = must-fix; refinement can't fix the bias.
5. **Interface gaps:** if Agent B reports `HUNLConfig` lacks `range_p0`/`range_p1` fields OR `solve_hunl_postflop` lacks warm-start kwarg, recovery paths are documented in kickoff §4a (regret-warm preferred via direct `DCFRSolver` instantiation; strategy-warm fallback).

Audit focus areas 1-16 catch all must-fix patterns. Audit runs in parallel with `check_pr.sh` after agents return (kickoff §5b).

---

## 6. Effort estimate

**3-5 days per PR 9 spec §9.** Biggest single PR after PR 6 (Rust port). Surface:

- Agent A: ~550 Python LOC (~300 preflop_solver + ~250 blueprint) + ~30 LOC × 4 surgical edits
- Agent B: ~350 Python LOC (subgame_refiner)
- Agent C: ~1,300 Rust LOC (~600 preflop + ~400 blueprint + ~300 subgame) + ~600 test LOC + additive `lib.rs` bindings

Total: ~2,250 LOC implementation + ~600 LOC tests. Two PR-5-sized chunks plus a Rust port equivalent to PR 6 in mechanical scope.

PR 9 is the **first end-to-end HUNL preflop → river deliverable**: Pluribus blueprint + subgame refinement pattern, with both Python reference tier and Rust production tier. Headline acceptance: `test_combined_exploitability_under_0_05_bb_per_hand` clears < 0.05 BB/hand on the Pio 100 BB cash-game fixture.

---

## 7. After-fan-out pipeline

After all 3 agents return: interface drift reconciliation (kickoff §5a) → audit + `check_pr.sh` parallel (§5b) → commit (§5c) → push (§5d) → merge no-ff into integration (§5e) → PLAN.md trajectory + autonomous_log entry (§5f). Full transcripts in `launch_kickoff.md`.

**Constraint reminder:** this doc pre-stages the fan-out. Do NOT execute agent launches from here. Trigger is user GO after PR 5 + PR 6 (and ideally PR 7) land on `integration`.
