# PR 10a launch invocations — copy-paste ready

**Status:** PRE-STAGED. PR 5 has merged to `integration` (tip `6c438b8`); branch creation is unblocked. Do NOT execute until the user has approved firing PR 10a.

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 10a. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`. Operational shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10a.md`. This file is the mechanical operations sheet — paste blocks in order.

**Why PR 10a fires on PR 5 alone (NOT gated on PR 6/7/8/9):** UI consumes only `HUNLSolveResult`, `MemoryReport`, `HUNLConfig`, `Range`/`Combo` — all shape-locked by PR 5. `ui/mock_solver.py` (Agent C owned) isolates UI from downstream solver work; PR 10b is a one-line import swap.

---

## 1. Pre-launch verification (run BEFORE branch creation)

All six checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip carries PR 5 merge (verified 2026-05-22 at 6c438b8).
git fetch origin
git log --oneline integration -5
# Expected: "Integration: merge PR 5 (hunl-postflop)" reachable; tip = 6c438b8 or later.
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1b. Branch pr-10a-ui-mock-first does NOT yet exist.
git branch --list pr-10a-ui-mock-first
# Expected: empty. If branch exists from prior aborted launch, rename
# (`git branch -m pr-10a-ui-mock-first-prior`) before re-creating.

# 1c. Working tree clean.
git status   # expected: "nothing to commit, working tree clean"

# 1d. PR 10a prep complete (post-polish per pr10a_polish_report.md §4).
ls docs/pr10_prep/
# Expected: pr10a_spec.md, pr10b_spec.md, agent_{a,b,c}_prompt.md, audit_prompt.md,
#           launch_kickoff_10{a,b}.md, fanout_ready_10a.md, pr10a_polish_report.md,
#           competitor_ui_deep_dive.md, ui_design_principles.md, ui_mockups_and_debates.md
grep -n "Prompts ready" docs/pr10_prep/pr10a_polish_report.md
# Expected: verdict "Prompts ready (post-polish)". If drifted, re-polish before firing.

# 1e. PR 5 public-surface sanity (the four imports the mock depends on).
python -c "
from poker_solver.hunl_solver import HUNLSolveResult, solve_hunl_postflop
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry
from poker_solver.hunl import HUNLConfig
from poker_solver.range import Range, Combo
print('PR 5 public surface OK')
"
# If any import fails, PR 5 did not land cleanly — investigate before PR 10a.

# 1f. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10a.hash
echo "integration tip pre-PR-10a: $(cat /tmp/integration_pre_pr_10a.hash)"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green before branching.

---

## 2. Branch creation

Branch name `pr-10a-ui-mock-first` is hard-coded across post-polish prompts + `audit_prompt.md` — do NOT improvise. Branch creation is unblocked NOW (PR 5 already merged); does NOT need to wait for PR 6/7/8/9.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check before branching
git checkout -b pr-10a-ui-mock-first
git status         # expect: clean tree on pr-10a-ui-mock-first
git log --oneline -1   # expect: PR 5 merge commit (or later integration tip)
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

All three implementation agents launch in the SAME tool-call block. They are independent — file-ownership boundaries are locked inside each prompt. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator-note header above the first `---`). Copy verbatim — do not paraphrase, do not truncate, do not inline.

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
| C | `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py` (stub), `tests/test_ui_smoke.py` | `poker_solver/cli.py` (add `ui` subcommand), `pyproject.toml` (`[ui]` extra: `nicegui>=2.0,<3.0` + `ui_smoke` pytest marker), `README.md` (UI section) | every other UI file, every existing test, every other `poker_solver/*.py` |

**Seven Q-locks each agent inherits (pr10a_spec.md §0.1 — follow literally, do NOT re-debate):**

- **Q1:** Two-pane layout — matrix center + collapsible right sidebar with three `ui.expansion` panels (spot input / run panel / tree browser). Agent A renders the shell.
- **Q2:** Hand-class labels visible in matrix cells ("AKs", "QQ", "72o"); numeric frequencies on hover only. Agent B's display matrix + Agent A's input matrix both honor.
- **Q3:** Default iterations = 1000 (NOT 2000). Target-exploitability mode is the opt-in alternative. **Weakly-held — see §5.**
- **Q4:** Bet sizes default = 4 of 6 checked (33% / 75% / 100% / all-in). Agent A's run panel encodes.
- **Q5:** Combo inspector position = below matrix (full-width horizontal strip). Agent B owns; Agent A leaves horizontal real estate untouched.
- **Q6:** Tree reach filter default = 0.01 (slider visible above tree). Agent B's `SolveTree.__init__(min_reach=0.01)`; Agent A's `UIPrefs.tree_reach_filter = 0.01`.
- **Q7:** Yellow "Mock mode" banner across top, dismissible (downgrades to subtle `(mock)` chip in PR 10b). Agent A renders banner (`mock-mode-banner` marker); Agent C's smoke 1 asserts it.

**NiceGUI 2.x pinned:** `nicegui>=2.0,<3.0` as `[ui]` optional extra in Agent C's `pyproject.toml` ownership. Engine-only users do NOT pay install cost; CLI lazy-imports `ui.app`.

**Parallel fan-out during agent runtime** (per parallel-agents-default + min-five-agents memory rules): while A/B/C run, fan out independent agents on downstream work — PR 10b consistency review against as-built 10a surface, PR 11 spec polish, `docs/autonomous_log.md` pruning, post-PR-5 doc-inventory sweep. Aggregate per wave; do NOT react agent-by-agent.

---

## 4. Expected wall-clock: ~2 days (largest UI work)

Medium-large PR — heaviest UI surface in the project (NiceGUI scaffold + 12 hand-crafted fixtures + 20 smoke tests). Per `fanout_ready_10a.md` §4:
- Agent A: ~75-120 min (shell + state.json atomicity + onboarding + run panel).
- Agent B: ~60-90 min (matrix + tree browser).
- Agent C: ~75-120 min (12 fixtures + 20 tests + CLI/pyproject + README).
- Concurrent execution: ~2-3 hours wall-clock for fan-out itself.
- Reconciliation + audit + check battery: ~60-90 min (manual smoke against all 12 fixtures + audit must-fix triage).
- Commit + merge: ~15 min.

**Total: ~2 days wall-clock** end-to-end (largest single PR in the project; UI threading + state.json atomicity + mock-fidelity tuning extend reconciliation).

**Deliverables (PR surface):** ~1500-2500 LOC net add; one new `ui/` sibling package (NOT inside `poker_solver/`); `ui/mock_solver.py` with 12 hand-crafted fixtures (byte-locked first-8-param signature for PR 10b swap); 20 smoke tests; CLI `ui` subcommand; `[ui]` extra in pyproject; README section. No edits to `hunl.py`/`solver.py`/`dcfr.py`/`range.py`.

---

## 5. Known orchestrator decision (weakly-held lock)

**Q3 default iters = 1000** is the coin-flip (spec §0.1 + §12 risk #5). Competitor evidence supports "fast first-feedback" directionally (DeepSolver "result in seconds", GTOW 6 s vs Pio's 4,862 s) but pins no exact integer. Launch as spec'd; bump to 2000 in PR 10b if manual testing shows under-converged matrices (river polarization not crisp, flop mixes noisy). Other six Q-locks have no residual uncertainty per `pr10a_polish_report.md` §5.

---

## 6. PR-10a-specific risk reminders

Three risks are uniquely PR 10a (downstream PRs don't touch these surfaces):

1. **UI threading correctness.** Mock snapshot loop runs in `threading.Thread`; UI polls via `ui.timer(0.5, ...)`. Any worker call into NiceGUI freezes the UI / corrupts state. Cancellation flows through `_CANCEL_FLAG` (`threading.Event`); same flag survives PR 10b swap. Stop-button = smoke 5 gate. Audit focus #1.
2. **`state.json` atomicity.** Atomic write (`state.json.tmp` → `fsync` → `rename`) required; corrupt JSON on second launch must back up to `state.json.bak` + start from defaults, NOT crash. Debounced save (500 ms window). Tests must use `isolated_state_dir` fixture — do NOT pollute real `~/.poker_solver_ui/`.
3. **Mock-data fidelity (poker eye test).** 12 hand-crafted fixtures must pass: realistic mixing, no dominated actions, MDF-obeying bluff freq on rivers, polarization on rivers vs. flops, blocker effects on rivers. Yellow "Mock mode" banner (Q7) discloses provenance but does NOT excuse obviously-wrong strategies. Interpolation fallback on off-distribution combos is a known cliff.

Auxiliary lower-severity: palette disjointness drift (smoke 16 locks); PR 10a→10b surface drift (PR 9 spec consistency review checks); Q3 1000-vs-2000 coin-flip (§5 above).

---

## 7. Post-fan-out: audit + commit

Per `launch_kickoff_10a.md` §5a-5f. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 7a. Interface drift reconciliation (install [ui] extra + run smoke).
pip install -e .[ui]                          # pulls nicegui>=2.0,<3.0
pytest tests/test_ui_smoke.py -xvs            # 20 smoke tests (per spec §10)
poker-solver ui                               # manual smoke; load each of 12 fixtures

# 7b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 10a audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr10_prep/audit_report.md.

# 7c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; no .env / secrets / state.json blobs
git add ui/ tests/test_ui_smoke.py poker_solver/cli.py \
        pyproject.toml README.md docs/pr10_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 10a surface
git commit -m "PR 10a: NiceGUI scaffold against MOCK solver"   # full message in launch_kickoff_10a.md §5c

# 7d. Push + --no-ff merge into integration.
git push -u origin pr-10a-ui-mock-first
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-10a-ui-mock-first -m "Integration: merge PR 10a (ui-mock-first)"
git push origin integration

# 7e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
```

PR-10a-specific must-fix triggers (hard stop): UI blocks on solver (no worker thread); stop button doesn't halt within 1 mocked iter; off-by-one in matrix combo→cell mapping; opponent hole-card leak in tooltips; NiceGUI in base `dependencies` rather than `[ui]` extra; `ui/` placed inside `poker_solver/`; `poker_solver/range.py` modified; library viewer isn't a stub. `should-fix` / `nice-to-fix` can defer to follow-up with TODO. Full failure-mode + recovery in `launch_kickoff_10a.md` §4a-4f.

---

## 8. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` (§0.1 Q-locks, §7 mock contract, §10 smoke tests)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_{a,b,c}_prompt.md` (post-polish)
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md`
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10a.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_invocations_10a.md`
- Polish report (provenance): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_polish_report.md`
- Companion spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`
- Reflog backup: `/tmp/integration_pre_pr_10a.hash`
