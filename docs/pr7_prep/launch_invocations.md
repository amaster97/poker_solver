# PR 7 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until PR 6 has merged to `integration` and the user has approved firing PR 7.

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 7 the moment PR 6 lands. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_kickoff.md`. This file is the mechanical operations sheet — paste blocks in order.

---

## 1. Pre-launch verification (run AFTER PR 6 lands, BEFORE branch creation)

All four checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip past PR 6 merge commit.
git fetch origin
git log --oneline integration -3
# Expected topmost commit: "Integration: merge PR 6 (rust-hunl-postflop)".
# Next-down expected: "Integration: merge PR 5 (HUNL postflop solve + memory profiler)" (eee9b4b).
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1b. Branch pr-7-noambrown-diff does NOT yet exist.
git branch --list pr-7-noambrown-diff
# Expected: empty output. If branch exists from a prior aborted launch, decide
# whether to reuse (rare) or rename the prior branch (`git branch -m pr-7-noambrown-diff-prior`).

# 1c. Brown binary at canonical path (already built, ~201 KB Mach-O arm64).
test -x references/code/noambrown_poker_solver/cpp/build/river_solver_optimized && \
    ls -l references/code/noambrown_poker_solver/cpp/build/river_solver_optimized
# Expected: ~206136 bytes (verified 2026-05-22), executable, present.

# 1d. 3-agent prompts up to date (P1 binary-path patch already applied).
ls docs/pr7_prep/agent_{a,b,c}_prompt.md
grep -n "noambrown_poker_solver/build/" docs/pr7_prep/pr7_spec.md docs/pr7_prep/audit_prompt.md \
    || echo "P1 patch clean — all paths canonical"
# Expected: "P1 patch clean". Any grep hit → apply sed patch before firing.

# 1e. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_7.hash
echo "integration tip pre-PR-7: $(cat /tmp/integration_pre_pr_7.hash)"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green before branching.

---

## 2. Branch creation

Branch name `pr-7-noambrown-diff` is hard-coded in `docs/pr7_prep/audit_prompt.md:14` — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull origin integration   # last sanity check before branching
git checkout -b pr-7-noambrown-diff
git status   # expect: clean tree on pr-7-noambrown-diff
git log --oneline -1   # expect: PR 6 merge commit
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

All three implementation agents launch in the SAME tool-call block. They are independent — file-ownership boundaries are locked inside each prompt. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator-note header above the first `---`). Copy verbatim — do not paraphrase, do not truncate, do not inline.

```
Agent A — "PR 7 Agent A — Brown build wrapper + 15 river fixture spots + canonicalizer module"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 7 Agent B — pytest diff harness (15 spots, parity_noambrown marker)"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 7 Agent C — self-sanity smoke tests (no-binary, 8 tests per spec §10)"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `scripts/build_noambrown.sh`, `tests/data/river_spots.json`, `poker_solver/parity/__init__.py`, `poker_solver/parity/noambrown_wrapper.py` | `.gitignore`, `references/README.md` (append-only) | any test file, `poker_solver/hunl.py`, `poker_solver/solver.py`, `pyproject.toml` |
| B | `tests/test_noambrown_river_parity.py` | `pyproject.toml` (register `parity_noambrown` marker) | wrapper, fixture JSON, build script, Agent C's test |
| C | `tests/test_noambrown_self_sanity.py` | (none) | non-test files, build script, Agent B's test, `pyproject.toml` |

**Parallel fan-out during agent runtime** (per parallel-agents-default + min-five-agents memory rules): while A/B/C run, fan out independent agents on downstream work — PR 8 baseline-bench spec polish, PR 9 dispatcher-rewrite research, `docs/autonomous_log.md` pruning, post-PR-6 doc-inventory sweep. Aggregate per wave; do NOT react agent-by-agent.

---

## 4. Expected wall-clock: ~3 hours

Small PR — mostly subprocess wrapping and fixture authoring. Per `fanout_ready.md` §4 estimate:
- Agent A: ~45-75 min (fixture curation + canonicalizer is the heaviest piece).
- Agent B: ~30-45 min (test harness from spec, no implementation reads).
- Agent C: ~30-45 min (8 smoke tests, no subprocess).
- Concurrent execution: ~1-2 hours wall-clock for fan-out itself.
- Audit + check battery + reconciliation: ~30-60 min.
- Commit + merge: ~10 min.

**Total: ~3 hours wall-clock** end-to-end (PR 7 branch creation → integration merge).

**Deliverables (PR surface):** ~600-900 LOC net add; one new `poker_solver/parity/` package; `scripts/build_noambrown.sh`; `tests/data/river_spots.json` (15 spots, ~22 KB); two new test files; pyproject marker registration; one-line appends to `.gitignore` + `references/README.md`. No edits to `hunl.py`/`solver.py`/`dcfr.py`.

---

## 5. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5a-5e. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 5a. Interface drift reconciliation (build + test the new surface).
bash scripts/build_noambrown.sh    # soft-fails on missing cmake/c++; tests skip cleanly
pip install -e .                   # rebuild PyO3 bindings if PR 6 touched them
pytest tests/test_noambrown_self_sanity.py -xvs   # Agent C smoke (no binary needed)
pytest tests/test_noambrown_river_parity.py -v    # Agent B diff (skips if no binary)

# 5b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 7 audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr7_prep/audit_report.md.

# 5c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; no .env / secrets / build artifacts
git add scripts/build_noambrown.sh tests/data/river_spots.json poker_solver/parity/ \
        tests/test_noambrown_river_parity.py tests/test_noambrown_self_sanity.py \
        pyproject.toml .gitignore references/README.md docs/pr7_prep/audit_report.md
git status   # re-verify
git commit -m "PR 7: river-spot differential test vs noambrown/poker_solver"   # full message in launch_kickoff.md §5c

# 5d. Push + --no-ff merge into integration.
git push -u origin pr-7-noambrown-diff
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-7-noambrown-diff -m "Integration: merge PR 7 (noambrown-diff)"
git push origin integration

# 5e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
```

`must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Full failure-mode + recovery patterns in `launch_kickoff.md` §6.

---

## 6. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt.md`
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/fanout_ready.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_invocations.md`
- Brown binary (gitignored): `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
- Reflog backup: `/tmp/integration_pre_pr_7.hash`
