# PR 10a fan-out ready — pre-staged launch sequence

**Status:** PRE-STAGED. Do NOT execute until PR 5 has merged to `integration`.

**Last verified:** 2026-05-22. Seven Q1-Q7 design decisions locked in `pr10a_spec.md` §0.1; three agent prompts post-polish per `pr10a_polish_report.md` §4 (verdict: "Prompts ready"); NiceGUI 2.x pinned (`nicegui>=2.0,<3.0`) as `[ui]` optional extra in Agent C's `pyproject.toml` ownership.

This doc collapses `launch_kickoff_10a.md` into the fire-when-PR-5-lands order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`. This file is the operational shortlist.

**Why PR 10a launches on PR 5 alone (NOT gated on PR 6/7/8/9):** UI consumes only `HUNLSolveResult`, `MemoryReport`, `HUNLConfig`, `Range`/`Combo` — all shape-locked by PR 5. The mock solver (`ui/mock_solver.py`, Agent C owned) isolates UI from downstream solver work; PR 10b is a one-line import swap.

---

## 1. Pre-flight gate (run AFTER PR 5 lands, BEFORE branch creation)

All six must pass. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip carries PR 5 merge.
git fetch origin
git log --oneline integration -5
# Expected: "Integration: merge PR 5 (hunl-postflop)" reachable.
git rev-parse integration; git rev-parse origin/integration   # must be equal

# 1b. working tree clean.
git status   # expected: "nothing to commit, working tree clean"

# 1c. PR 10a prompts up to date (post-polish).
ls docs/pr10_prep/    # expect: pr10a_spec.md, pr10b_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md, launch_kickoff_10{a,b}.md, pr10a_polish_report.md, competitor_ui_deep_dive.md, ui_design_principles.md, ui_mockups_and_debates.md
grep -n "Prompts ready" docs/pr10_prep/pr10a_polish_report.md
# Expected: verdict line "Prompts ready (post-polish)". If verdict drifted, re-polish before launching.

# 1d. PR 5 public-surface sanity (the four imports the mock depends on).
python -c "
from poker_solver.hunl_solver import HUNLSolveResult, solve_hunl_postflop
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry
from poker_solver.hunl import HUNLConfig
from poker_solver.range import Range, Combo
print('PR 5 public surface OK')
"
# If any import fails, PR 5 did not land cleanly — investigate before PR 10a.

# 1e. integration is green from its tip (smoke before adding 1500+ LOC).
pytest -x -q

# 1f. Reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10a.hash
```

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-10a-ui-mock-first integration
git status   # expect: clean tree on pr-10a-ui-mock-first
```

Branch name hard-coded across post-polish prompts + `audit_prompt.md` — do NOT improvise.

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

For each agent, copy the **body of the prompt file between the two `---` markers** verbatim. Do NOT paraphrase the header.

```
Agent A — "PR 10a Agent A — spot input + run panel + state + onboarding"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_a_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 10a Agent B — range matrix display + decision tree browser"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_b_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 10a Agent C — mock solver + library stub + 20 smoke tests + CLI"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_c_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Surgical edit | Forbidden |
|---|---|---|---|
| A | `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/__init__.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/views/onboarding.py` | (none) | `ui/views/range_matrix.py`, `ui/views/tree_browser.py`, `ui/views/library_browser.py`, any `ui/mock_solver*.py`, any test, any existing `poker_solver/*.py` |
| B | `ui/views/range_matrix.py`, `ui/views/tree_browser.py` | (none) | every other UI file, every test, every `poker_solver/*.py` |
| C | `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py` (stub), `tests/test_ui_smoke.py` | `poker_solver/cli.py` (add `ui` subcommand), `pyproject.toml` (`[ui]` extra + `ui_smoke` marker), `README.md` (UI section) | every other UI file, every existing test, every other `poker_solver/*.py` |

**Seven Q-locks (pr10a_spec.md §0.1 — agents follow literally, do NOT re-debate):** Q1 two-pane + right-sidebar expansions; Q2 hand-class labels in cells, numeric freq on hover; Q3 default iters = 1000 (weakly-held); Q4 4-of-6 bet sizes checked (33/75/100/all-in); Q5 combo inspector below matrix; Q6 reach filter 0.01 default; Q7 yellow "Mock mode" banner top, dismissible.

While A/B/C run, fan out parallel work (PR 10b consistency review against as-built 10a surface, PR 11 spec polish, autonomous-log pruning, doc inventory sweep) per parallel-agents-default memory.

---

## 4. Expected outputs + timeline

**Wall-clock:** ~2-3 hours (A: ~75-120 min on shell + state.json atomicity + onboarding; B: ~60-90 min on matrix + tree; C: ~75-120 min on 12 fixtures + 20 tests + CLI/pyproject; concurrent).

**Deliverables (PR surface):**
- `ui/__init__.py`, `ui/app.py`, `ui/state.py` (atomic save to `~/.poker_solver_ui/state.json`)
- `ui/views/{spot_input,run_panel,onboarding,range_matrix,tree_browser,library_browser}.py`
- `ui/mock_solver.py` (12 hand-crafted fixtures, byte-locked signature for PR 10b swap)
- `tests/test_ui_smoke.py` (20 smoke tests per spec §10)
- `poker_solver/cli.py` (add `ui` subcommand, lazy-import)
- `pyproject.toml` (`[ui]` extra: `nicegui>=2.0,<3.0`; `ui_smoke` pytest marker)
- `README.md` (UI section)

**Medium-large PR:** ~1500-2500 LOC net add; one new `ui/` sibling package (NOT inside `poker_solver/`); no edits to `hunl.py`, `solver.py`, `dcfr.py`, `range.py`.

**Pass criteria:** all existing tests still pass; 20 smoke tests pass with `pip install -e .[ui]`; ruff/black/mypy-strict clean on new files; `poker-solver ui` launches and loads all 12 fixtures.

---

## 5. Known orchestrator decision (weakly-held lock)

**Q3 default iters = 1000** is the coin-flip (spec §0.1 + §12 risk #5). Competitor evidence supports "fast first-feedback" directionally (DeepSolver "result in seconds", GTOW 6 s) but pins no exact integer. Launch as spec'd; bump to 2000 in PR 10b if manual testing shows under-converged matrices (river polarization not crisp, flop mixes noisy). Other six Q-locks have no residual uncertainty.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff_10a.md` §5: after all three agents return, run interface-drift reconciliation (`pytest tests/test_ui_smoke.py -xvs`) + audit + check battery in same parallel wave. Commit explicit paths (`ui/ tests/test_ui_smoke.py poker_solver/cli.py pyproject.toml README.md docs/pr10_prep/audit_report.md` — never `git add -A`); push `pr-10a-ui-mock-first`; `--no-ff` merge into `integration`; update `PLAN.md` trajectory + `docs/autonomous_log.md`.

PR-10a-specific must-fix triggers: UI blocks on solver (no worker thread); stop button doesn't halt within 1 mocked iter; off-by-one in matrix combo→cell mapping; opponent hole-card leak in tooltips; NiceGUI in base `dependencies` rather than `[ui]` extra; `ui/` placed inside `poker_solver/`; `poker_solver/range.py` modified; library viewer isn't a stub.

Full pipeline lives in `launch_kickoff_10a.md` §5a-5f. This doc stops at fan-out launch.
