# PR 9 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until PR 5 + PR 6 have merged to `integration` (PR 7 ideally also landed) and the user has approved firing PR 9.

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 9 — first end-to-end HUNL preflop → river deliverable. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_kickoff.md`. This file is the mechanical operations sheet — paste blocks in order.

---

## 1. Pre-launch verification (run AFTER PR 5 + PR 6 land, ideally PR 7 too; BEFORE branch creation)

All six checks must pass. PR 9 has a heavier dependency surface than PR 6/7/8: consumes both PR 4 (abstraction artifact) and PR 5 (postflop solver) directly; on `on_progress` kwarg threading PR 10b depends.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 5 merged to integration (subgame refinement calls solve_hunl_postflop unchanged).
git fetch origin
git log --oneline integration -20 | grep -E "PR 5|hunl-postflop"
# Expected: "Integration: merge PR 5 (hunl-postflop)" present.

# 1b. PR 6 merged to integration (Rust port consumed by Agent C's Rust port).
git log --oneline integration -20 | grep -E "PR 6|rust-hunl-postflop"
# Expected: "Integration: merge PR 6 (rust-hunl-postflop)" present.
# PR 7 (noambrown-diff) ideally also landed; non-blocking for PR 9 itself.

# 1c. PR 4 merged to integration (blueprint loads AbstractionTables; diff tests need tiny abstraction).
git log --oneline integration -20 | grep -E "PR 4|abstraction|precompute"

# 1d. integration tip matches origin/integration; working tree clean.
git rev-parse integration; git rev-parse origin/integration   # must match
git status                                                     # must be clean
# If divergent: git pull --ff-only origin integration

# 1e. All PR 9 prompts + audit prompt present (verdict READY after on_progress patch).
ls docs/pr9_prep/agent_{a,b,c}_prompt.md docs/pr9_prep/audit_prompt.md
# Confirm `on_progress` kwarg references present in all three implementation prompts.
grep -l "on_progress" docs/pr9_prep/agent_{a,b,c}_prompt.md
# Expected: all three files match.

# 1f. Reflog backup hash.
git rev-parse integration > /tmp/integration_pre_pr_9.hash
echo "integration tip pre-PR-9: $(cat /tmp/integration_pre_pr_9.hash)"
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green. Especially confirm `tests/test_hunl_postflop_*` and `tests/test_abstraction*` are green.

---

## 2. Branch creation

Branch name `pr-9-hunl-preflop` is hard-coded in `docs/pr9_prep/audit_prompt.md` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-9-hunl-preflop
git status   # expect: clean tree, on pr-9-hunl-preflop
git log --oneline -1   # expect: PR 5/6/7 merge commit
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

All three implementation agents launch in the SAME tool-call block. They are independent — file-ownership boundaries locked inside each prompt. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator header above the first `---`). Copy verbatim.

```
Agent A — "PR 9 Agent A — Python blueprint + preflop solver orchestrator"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 9 Agent B — Python subgame refiner + PR 5 integration + on_progress threading"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 9 Agent C — Rust port + PyO3 + all Python tests"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `poker_solver/preflop_solver.py`, `poker_solver/blueprint.py` | `solver.py` (preflop dispatch branch per §6); `cli.py` (`--hunl-mode preflop` + new flags); `__init__.py` re-exports; `hunl.py` (single new canonical-class chance generator method, opt-in) | `subgame_refiner.py`, any Rust file, any test file, `dcfr.py`, `hunl_solver.py`, `abstraction/*`, `charts/*` |
| B | `poker_solver/subgame_refiner.py` | (none) | `blueprint.py`, `preflop_solver.py`, `hunl.py`, `hunl_solver.py`, `dcfr.py`, any Rust file, any test file |
| C | `crates/cfr_core/src/preflop.rs`, `blueprint.rs`, `subgame.rs`; ALL test files (`tests/test_hunl_preflop_*.py`, `tests/test_preflop_diff.py`, `tests/fixtures/hunl_preflop_fixtures.py`) | `crates/cfr_core/src/lib.rs` (additive PyO3 bindings only) | any Python non-test file, existing Rust files, `Cargo.toml` |

**Parallel fan-out during runtime** (per parallel-agents-default + min-five-agents rules): launch independent agents on downstream work — PR 10a/10b spec polish (direct consumer of `on_progress`), PR 11 research, `docs/autonomous_log.md` pruning, doc inventory sweep, precompute-blueprint CLI tool spec (PR 9.5). Aggregate per wave.

---

## 4. Expected wall-clock: ~8-10 hours

Largest fan-out to date (Python orchestrator + Python refiner + Rust port + all tests).
- Agent A: ~150-210 min (blueprint builder + preflop orchestrator + dispatch branch + canonical-class chance generator).
- Agent B: ~120-180 min (subgame refiner + range extraction + warm-start regret loading + on_progress threading into PR 5).
- Agent C: ~180-240 min (Rust port of three modules + PyO3 bindings + comprehensive test surface including diff tests).
- Concurrent execution: ~3-4 hours wall-clock for fan-out itself.
- Audit + check battery + reconciliation: ~90-120 min (largest reconciliation surface).
- Commit + merge: ~10 min.

**Deliverables (PR surface):** ~3000-4500 LOC net add; new Python modules (`blueprint.py`, `preflop_solver.py`, `subgame_refiner.py`); new Rust modules (`preflop.rs`, `blueprint.rs`, `subgame.rs`); ~5-7 new test files; `solver.py`/`cli.py`/`hunl.py` surgical edits. End-to-end exploitability target: < 0.05 BB/hand on Pio 100 BB validation fixture.

---

## 5. Risk reminders specific to PR 9

- **Dispatch composition (§6 canonical).** push/fold ≤15 BB short-circuits; postflop branch wins at 15 BB preflop; ValueError at >250 BB; preflop branch otherwise. Anti-pattern (audit must-fix): postflop branch wins at 15 BB; no >250 BB ceiling.
- **Diff-test tolerance cluster.** `5e-3` per-action + `1e-3 × base_pot` per-spot game value. NOT `1e-4` (earlier-draft outlier). Audit focus area 2 catches `1e-4` as must-fix.
- **Canonical-class chance generator combinatorial weights.** Pair weights = 6 combos (C(4,2)), suited = 4, offsuit = 12. Brute-force enumeration check is hard gate; bias propagates to blueprint strategy if sum ≠ 1.0.
- **`on_progress` kwarg threading (LOAD-BEARING for PR 10b).** Must thread through `solve_hunl_preflop` → `build_blueprint` → `refine_subgame` → PR 5's `solve_hunl_postflop` AND Rust counterparts via `Option<PyObject>` + `Python::with_gil`. Silent drop ships PR 10b with hung progress bar.
- **Warm-start regret transfer.** ONLY transfer keys where action sets exactly match. Blueprint has 3 actions (1-size menu); refinement has 8 (full menu) — cross-tree corruption if not filtered.
- **Sequential subgame refinement memory leak.** `del solver; gc.collect()` between calls. Module-level cache pinning references is the common bug.
- **Range extraction must be strategy-conditioned posterior**, NOT prior uniform. `p0_range["AA"] > 5 × p0_range["72o"]` on a 3-bet pot subgame is the sanity check.
- **Frozen files (do NOT modify).** `dcfr.py` (α=1.5, β=0, γ=2.0 unchanged); `hunl_solver.py` (PR 5 frozen). Audit must-fix triggers on modification.
- **AGPL contamination.** `postflop-solver` / `TexasSolver` are AGPL. Architectural inspiration only. No verbatim copies.
- **Blueprint OOM at 100 BB.** Three recovery levers in `MemoryError` message: tighten tier (128/64/32 or 64/32/16); drop menu (0-cap); reduce iterations. Canonical-class generator opt-in is mandatory.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5a-5e. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation.
cargo build --release   # confirm Rust builds clean
pip install -e .         # rebuild PyO3 extension
pytest tests/test_hunl_preflop_blueprint.py -xvs
pytest tests/test_hunl_preflop_refinement.py -xvs
pytest tests/test_hunl_preflop_integration.py -xvs -m "not slow"
pytest tests/test_preflop_diff.py -xvs
cargo test --release --manifest-path crates/cfr_core/Cargo.toml
# slow-marked tests run nightly, not gating for audit pass.

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 9 audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr9_prep/audit_report.md.

# 6c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; no .env / secrets / .npz blobs
git add poker_solver/ crates/cfr_core/ tests/ docs/pr9_prep/audit_report.md
git status   # re-verify
git commit -m "PR 9: HUNL preflop solve (Python + Rust tiers)"   # full message in launch_kickoff.md §5c

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-9-hunl-preflop
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-9-hunl-preflop -m "Integration: merge PR 9 (hunl-preflop)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
# Note: "first end-to-end HUNL preflop+postflop deliverable shipped."
```

`must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Full failure-mode + recovery patterns in `launch_kickoff.md` §6.

---

## 7. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` (§6 dispatch CANONICAL; §10.4 tolerance cluster; §7.4 exploitability target; §12 memory budget)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/audit_prompt.md`
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/fanout_ready.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/launch_invocations.md`
- PR 10b consumer of `on_progress`: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` (lines 152-156)
- Reflog backup: `/tmp/integration_pre_pr_9.hash`
