# PR 7 fan-out ready — pre-staged launch sequence

**Status:** PRE-STAGED. Do NOT execute until PR 6 has merged to `integration`.

**Last verified:** 2026-05-22. Binary built (`206136` bytes, Mach-O arm64); P1 path patch already applied across `pr7_spec.md` + `audit_prompt.md`; DCFR flags `--dcfr-alpha/beta/gamma` confirmed in `cpp/src/main.cpp` lines 619-624.

This doc collapses `launch_kickoff.md` into the fire-when-PR-6-lands order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_kickoff.md`. This file is the operational shortlist.

---

## 1. Pre-flight gate (run AFTER PR 6 lands, BEFORE branch creation)

All four must pass. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip is past eee9b4b (PR 6 merge commit must be on top).
git fetch origin
git log --oneline integration -3
# Expected: topmost is "Integration: merge PR 6 (rust-hunl-postflop)".
# Then: "Integration: merge PR 5 (HUNL postflop solve + memory profiler)" (eee9b4b).
git rev-parse integration; git rev-parse origin/integration   # must be equal

# 1b. PR 7 prompts up to date (5 files present + P1 patch applied).
ls docs/pr7_prep/    # expect: pr7_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md, launch_readiness.md, launch_kickoff.md, noambrown_build_status.md, fanout_ready.md
grep -n "noambrown_poker_solver/build/" docs/pr7_prep/pr7_spec.md docs/pr7_prep/audit_prompt.md \
    || echo "P1 patch clean — all paths canonical"
# Verified 2026-05-22: returns "P1 patch clean".

# 1c. Brown binary executable at canonical path.
test -x references/code/noambrown_poker_solver/cpp/build/river_solver_optimized && echo "binary OK"
# Verified 2026-05-22: present, 206136 bytes, Mach-O arm64.

# 1d. DCFR flags present in Brown source.
grep -c "dcfr-alpha\|dcfr-beta\|dcfr-gamma" references/code/noambrown_poker_solver/cpp/src/main.cpp
# Verified 2026-05-22: returns 6 (three flag-defs, three help-line mentions).

# 1e. Reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_7.hash
```

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-7-noambrown-diff integration
git status   # expect: clean tree on pr-7-noambrown-diff
```

Branch name hard-coded in `audit_prompt.md:14` — do NOT improvise.

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

For each agent, copy the **body of the prompt file between the two `---` markers** verbatim. Do NOT paraphrase the header.

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

While A/B/C run, fan out parallel work (PR 8 spec polish, PR 9 dispatcher-rewrite research, autonomous-log pruning) per parallel-agents-default memory.

---

## 4. Expected outputs + timeline

**Wall-clock:** ~1-2 hours (A: ~45-75 min on fixture curation + canonicalizer; B + C: ~30-45 min each; concurrent).

**Deliverables (PR surface):**
- `scripts/build_noambrown.sh` (idempotent, soft-fails on missing toolchain)
- `tests/data/river_spots.json` (15 spots, 5 categories × 3)
- `poker_solver/parity/__init__.py` + `poker_solver/parity/noambrown_wrapper.py`
- `tests/test_noambrown_river_parity.py` (15-spot parametrize + buildability infra test)
- `tests/test_noambrown_self_sanity.py` (8 smoke tests)
- `pyproject.toml` marker registration (`parity_noambrown`)
- `.gitignore` + `references/README.md` (one-line appends)

**Small PR:** ~600-900 LOC net add; one new `poker_solver/parity/` package; no `hunl.py`/`solver.py`/`dcfr.py` edits.

**Pass criteria:** all 138+ existing tests still pass; 15 parity tests pass when binary present, skip cleanly otherwise; ruff/black/mypy-strict clean on new files.

---

## 5. Quick sanity: Brown binary `--help` (share with Agent A)

```
Usage: river_solver_optimized [--config PATH] [--stack N] [--algo cfr|cfr+|lcfr|dcfr|mccfr|mccfr-linear|all] [--iters N] [--bet-sizes LIST] [--no-all-in] [--max-raises N] [--checkpoints LIST] [--target-exp X] [--seed N] [--mccfr-linear] [--no-eval] [--eval-interval N]
  DCFR params: --dcfr-alpha A --dcfr-beta B --dcfr-gamma G
  Bet sizes: --bet-sizes 0.5,1 (comma-separated pot fractions)
  Checkpoints: --checkpoints 1024,2048,4096
  Strategy dump: --dump-strategy PATH
```

PR 7 invocation locked by spec §1: `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7 --iters 2000`.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §5: after all three agents return, run audit + check battery in same parallel wave; commit explicit paths (no `git add -A`); push `pr-7-noambrown-diff`; `--no-ff` merge into `integration`; update `PLAN.md` trajectory + `docs/autonomous_log.md`.

Full pipeline lives in `launch_kickoff.md` §5a-5e. This doc stops at fan-out launch.
