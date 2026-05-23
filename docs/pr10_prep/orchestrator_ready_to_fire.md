# PR 10a orchestrator ready-to-fire (post PR 4.5 gate)

**Status:** PRE-STAGED. Do NOT execute until PR 4.5 commits + merges to `integration`. Per the no-concurrent-branch-ops rule, PR 10a fires SERIALLY after PR 4.5 lands — never in parallel with another branch-mutating PR in the shared working tree.

**Authoritative kickoff:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`.
**Operational ops sheet:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_invocations_10a.md`.

---

## 1. Pre-flight checklist (run AFTER PR 4.5 lands)

All checks must pass before branch creation. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip carries PR 4.5 merge.
git fetch origin
git log --oneline integration -5
# Expected: PR 4.5 merge commit reachable; integration tip = post-PR-4.5 hash.
git rev-parse integration; git rev-parse origin/integration   # must match
# If divergent: git pull --ff-only origin integration

# 1b. Working tree clean.
git status   # expected: "nothing to commit, working tree clean"

# 1c. Branch pr-10a-ui-mock-first does NOT exist (rename if leftover).
git branch --list pr-10a-ui-mock-first
# If non-empty: git branch -m pr-10a-ui-mock-first pr-10a-ui-mock-first-prior

# 1d. Public-surface sanity (the four imports the mock depends on).
python -c "
from poker_solver.hunl_solver import HUNLSolveResult, solve_hunl_postflop
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry
from poker_solver.hunl import HUNLConfig
from poker_solver.range import Range, Combo
print('public surface OK')
"

# 1e. Reflog backup.
git rev-parse integration > /tmp/integration_pre_pr_10a.hash
echo "integration tip pre-PR-10a: $(cat /tmp/integration_pre_pr_10a.hash)"

# 1f. Branch creation (verify/create from current integration tip).
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-10a-ui-mock-first    # create from current integration tip
git status                              # expect: clean tree on pr-10a-ui-mock-first
git log --oneline -1                    # expect: PR 4.5 merge (or later)
```

Optional: `pytest -x -q` from `integration` tip — must be green before branching.

---

## 2. Three-agent fan-out (SAME tool-call wave)

All three agents launch in ONE tool-call block. They are independent — file-ownership boundaries locked inside each prompt. For each agent, the prompt is the **body of the corresponding prompt file between the two `---` markers** (NOT the orchestrator-note header above the first `---`). Copy verbatim — do not paraphrase or truncate.

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

| Agent | Owns | Surgical edits | Forbidden |
|---|---|---|---|
| A | `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/__init__.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/views/onboarding.py` | (none) | matrix/tree/library views, mock_solver, any test, any `poker_solver/*.py` |
| B | `ui/views/range_matrix.py`, `ui/views/tree_browser.py` | (none) | every other UI file, every test, every `poker_solver/*.py` |
| C | `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py` (stub), `tests/test_ui_smoke.py` | `poker_solver/cli.py` (add `ui` subcommand), `pyproject.toml` (`[ui]` extra + `ui_smoke` marker), `README.md` (UI section) | every other UI file, every existing test, every other `poker_solver/*.py` |

**NiceGUI 2.x pinned** as `[ui]` optional extra (`nicegui>=2.0,<3.0`); engine-only users pay zero install cost; CLI lazy-imports `ui.app`.

---

## 3. Seven locked design decisions (pr10a_spec.md §0.1)

Follow literally — do NOT re-debate. Each agent inherits all seven.

- **Q1:** Two-pane layout — matrix center + ONE collapsible right sidebar stacking three `ui.expansion` panels (spot input / run panel / tree browser, top-to-bottom; spot input open by default). Agent A renders the shell.
- **Q2:** Hand-class labels visible in matrix cells ("AKs", "QQ", "72o" upper-left); numeric frequencies on hover only. Both Agent B's display matrix and Agent A's range-INPUT matrix honor.
- **Q3:** Default iterations = 1000 (NOT 2000). Target-exploitability mode is the opt-in alternative. **Weakly-held** — bump to 2000 in PR 10b if manual testing shows under-converged matrices.
- **Q4:** Bet sizes default = 4 of 6 checked (33% / 75% / 100% / all-in checked; 150% / 200% unchecked). Custom-size text field still present. Agent A's run panel encodes.
- **Q5:** Combo inspector position = below matrix (full-width horizontal strip). Agent B owns; Agent A leaves horizontal real estate untouched.
- **Q6:** Tree reach filter slider default = 0.01 (NOT 0.0; slider visible above tree). Agent B's `SolveTree.__init__(min_reach=0.01)`; Agent A's `UIPrefs.tree_reach_filter = 0.01`.
- **Q7:** Yellow "Mock mode" banner across header, dismissible after first solve (downgrades to subtle `(mock)` chip in PR 10b). Agent A renders banner (`mock-mode-banner` marker); Agent C's smoke 1 asserts.

---

## 4. Expected wall-clock: ~2 days (biggest UI work)

Largest single PR in the project — heaviest UI surface (NiceGUI scaffold + 12 hand-crafted fixtures + 20 smoke tests).

- Agent A: ~75-120 min (shell + state.json atomicity + onboarding + run panel).
- Agent B: ~60-90 min (matrix + tree browser).
- Agent C: ~75-120 min (12 fixtures + 20 tests + CLI/pyproject + README).
- Concurrent execution: ~2-3 hours wall-clock for fan-out itself.
- Reconciliation + audit + check battery: ~60-90 min (manual smoke against all 12 fixtures + audit must-fix triage).
- Commit + merge: ~15 min.

**Total: ~2 days wall-clock** end-to-end. UI threading + state.json atomicity + mock-fidelity tuning extend reconciliation.

**Deliverables:** ~1500-2500 LOC net add; one new `ui/` sibling package (NOT inside `poker_solver/`); `ui/mock_solver.py` with 12 hand-crafted fixtures (byte-locked first-8-param signature for PR 10b swap); 20 smoke tests; CLI `ui` subcommand; `[ui]` extra in pyproject; README section. No edits to `hunl.py` / `solver.py` / `dcfr.py` / `range.py`.

---

## 5. Risk reminders (PR-10a-unique surfaces)

Three risks are uniquely PR 10a (downstream PRs don't touch these surfaces):

1. **UI threading correctness.** Mock snapshot loop runs in `threading.Thread`; UI polls via `ui.timer(0.5, ...)`. Any worker call into NiceGUI freezes the UI / corrupts state. Cancellation flows through `_CANCEL_FLAG` (`threading.Event`); same flag survives PR 10b swap. Stop-button = smoke 5 gate. Audit focus #1.
2. **`state.json` atomicity.** Atomic write (`state.json.tmp` → `fsync` → `rename`) required; corrupt JSON on second launch must back up to `state.json.bak` + start from defaults, NOT crash. Debounced save (500 ms window). Tests must use `isolated_state_dir` fixture — do NOT pollute real `~/.poker_solver_ui/`.
3. **Mock-data fidelity (poker eye test).** 12 hand-crafted fixtures must pass: realistic mixing, no dominated actions, MDF-obeying bluff freq on rivers, polarization on rivers vs flops, blocker effects on rivers. Yellow "Mock mode" banner discloses provenance but does NOT excuse obviously-wrong strategies. Interpolation fallback on off-distribution combos is a known cliff.

Auxiliary lower-severity: palette disjointness drift (smoke 16 locks); PR 10a→10b surface drift (PR 9 spec consistency review checks); Q3 1000-vs-2000 coin-flip.

---

## 6. Post-fan-out: audit + commit pipeline

After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation.
pip install -e .[ui]                                    # pulls nicegui>=2.0,<3.0
pytest tests/test_ui_smoke.py -xvs                      # 20 smoke tests
poker-solver ui                                         # manual smoke; load each of 12 fixtures

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 10a audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md between the `---` markers>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr10_prep/audit_report.md.

# 6c. Commit (explicit paths only — NO `git add -A`).
git status   # verify staged set; no .env / secrets / state.json blobs
git add ui/ tests/test_ui_smoke.py poker_solver/cli.py \
        pyproject.toml README.md docs/pr10_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 10a surface
git commit -m "PR 10a: NiceGUI scaffold against MOCK solver"

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-10a-ui-mock-first
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-10a-ui-mock-first -m "Integration: merge PR 10a (ui-mock-first)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
```

**PR-10a-specific must-fix triggers (hard stop):** UI blocks on solver (no worker thread); stop button doesn't halt within 1 mocked iter; off-by-one in matrix combo→cell mapping; opponent hole-card leak in tooltips; NiceGUI in base `dependencies` rather than `[ui]` extra; `ui/` placed inside `poker_solver/`; `poker_solver/range.py` modified; library viewer isn't a stub. `should-fix` / `nice-to-fix` can defer to follow-up with TODO.

**Parallel fan-out during agent runtime** (per parallel-agents-default + min-five-agents memory rules): while A/B/C run, spawn independent agents on downstream work — PR 10b consistency review against as-built 10a surface, PR 11 spec polish, `docs/autonomous_log.md` pruning, post-PR-4.5 doc-inventory sweep. Aggregate per wave; do NOT react agent-by-agent.

---

## 7. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` (§0.1 Q-locks, §7 mock contract, §10 smoke tests)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_{a,b,c}_prompt.md`
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md`
- Kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`
- Operational sheet: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_invocations_10a.md`
- Companion spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`
- Reflog backup: `/tmp/integration_pre_pr_10a.hash`
