# PR 10a launch kickoff — NiceGUI scaffold against a MOCK solver

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until PR 5 has merged to `integration` and the user has approved firing PR 10a.

**Purpose:** the exact command sequence + agent fan-out the orchestrator runs when PR 5 lands and PR 10a is fired. This doc collapses §0–§8 of `docs/pr_launch_runbook.md` against the PR 10a-specific shape into a single executable transcript so launch is mechanical, not improvisational.

**Branch:** `pr-10a-ui-mock-first` (per PLAN.md §1 per-PR feature-branch rule + the post-polish prompt convention).

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` (976 lines, post-UX-lock; §0.1 holds the seven Q1–Q7 locks)
- Agent prompts: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md` (all post-polish per `pr10a_polish_report.md` §4)
- Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md`
- Polish report (provenance): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_polish_report.md`
- Companion spec (forward context): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

**Why PR 10a can launch as soon as PR 5 lands (NOT gated on PR 6/7/8/9):** the UI consumes a small public surface (`HUNLSolveResult`, `MemoryReport`, `HUNLConfig`, `Range`/`Combo`) whose shapes are locked after PR 5. PR 6 Rust port, PR 7 Brown parity, PR 8 SIMD, PR 9 preflop all preserve those shapes. The mock solver layer (`ui/mock_solver.py`, Agent C owned) is the load-bearing piece; PR 10b is a one-line import swap once the real solvers ship.

---

## 1. Pre-flight gate (run BEFORE branch creation)

All five checks must pass. If ANY fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. PR 5 is committed AND merged to integration.
git fetch origin
git log --oneline integration -10
# Expected: a "Integration: merge PR 5 (hunl-postflop)" commit (or equivalent
# --no-ff merge of pr-5-hunl-postflop) reachable from integration tip.
# PR 6/7/8/9 are NOT required to launch PR 10a — the mock solver shim
# isolates the UI from downstream solver work.

# 1b. integration tip matches origin/integration (zero divergence).
git rev-parse integration
git rev-parse origin/integration
# Both hashes must be equal. If not: `git pull --ff-only origin integration`.

# 1c. Working tree clean.
git status
# Expected: "nothing to commit, working tree clean".

# 1d. All PR 10a prompts up to date (post-polish per polish report).
ls -la docs/pr10_prep/
# Expected files present:
#   pr10a_spec.md (~976 lines; §0.1 has Q1-Q7 locks)
#   agent_a_prompt.md (post-polish; references pr10a_spec.md, Q-locks surfaced)
#   agent_b_prompt.md (post-polish; Q6 slider default = 0.01)
#   agent_c_prompt.md (post-polish; 20 tests, owns mock_solver)
#   audit_prompt.md
#   pr10a_polish_report.md (verdict: "Prompts ready (post-polish)")
# Confirm `pr10a_polish_report.md` §5 still reads "Prompts ready". If a
# subsequent edit invalidated any prompt, re-polish before launching.

# 1e. Public-surface sanity: confirm PR 5 shipped HUNLSolveResult + MemoryReport
# at the expected import paths (mock surface contract depends on these).
python -c "
from poker_solver.hunl_solver import HUNLSolveResult, solve_hunl_postflop
from poker_solver.profiler.memory import MemoryReport, StreetMemoryEntry
from poker_solver.hunl import HUNLConfig
print('PR 5 public surface OK')
"
# If any import fails, PR 5 did not land cleanly — investigate before PR 10a.

# 1f. Confirm integration tip hash for the reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10a.hash
echo "integration tip pre-PR-10a: $(cat /tmp/integration_pre_pr_10a.hash)"
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green before branching.

---

## 2. Branch creation

Mechanical. Branch name is locked across the post-polish prompts.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check
git checkout -b pr-10a-ui-mock-first
git status   # expect: clean tree, on pr-10a-ui-mock-first
git log --oneline -1  # expect: PR 5 merge commit (or whatever integration tip is)
```

Branch convention rationale: every PR from PR 3 onward gets its own feature branch from `integration` (PLAN.md §1). `pr-10a-ui-mock-first` is the spelling the audit prompt will cross-reference and the spelling consistent with the post-polish report.

---

## 3. Three-agent fan-out launch (parallel, same wave)

Per `pr_launch_runbook.md` §"Step 2": all three implementation agents launch in the SAME tool-call wave. They are designed to be independent — file-ownership boundaries are locked in each prompt.

For each agent, the prompt is the **full contents of the corresponding `docs/pr10_prep/agent_{a,b,c}_prompt.md` file between the two `---` markers** (NOT the orchestrator header above the first `---`). Do not paraphrase, do not truncate, do not inline.

**Launch sequence (orchestrator side, all three in one tool-call block):**

```
Agent tool call 1:
  description: "PR 10a Agent A — spot input + run panel + state + onboarding"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_a_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 2:
  description: "PR 10a Agent B — range matrix display + decision tree browser"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_b_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true

Agent tool call 3:
  description: "PR 10a Agent C — mock solver + library stub + 20 smoke tests + CLI"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_c_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership recap (verifies interface lock — do NOT relax these):**

| Agent | Owns (create / write) | May surgically modify | Forbidden |
|---|---|---|---|
| A | `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/__init__.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/views/onboarding.py` | (none) | `ui/views/range_matrix.py`, `ui/views/tree_browser.py`, `ui/views/library_browser.py`, `ui/mock_solver*.py`, any test file, any existing `poker_solver/*.py` |
| B | `ui/views/range_matrix.py`, `ui/views/tree_browser.py` | (none) | every other UI file, every test, every `poker_solver/*.py` |
| C | `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py`, `tests/test_ui_smoke.py` | `poker_solver/cli.py` (add `ui` subcommand), `pyproject.toml` (`[ui]` extra + pytest marker), `README.md` (UI section) | every other UI file, every existing test, every other `poker_solver/*.py` |

**The seven Q-locks each agent inherits (pr10a_spec.md §0.1 — agents follow these literally; do NOT re-debate):**

- **Q1:** Two-pane layout — matrix center + collapsible right sidebar with three `ui.expansion` panels (spot input / run panel / tree browser). Agent A renders the shell.
- **Q2:** Hand-class labels visible in matrix cells ("AKs", "QQ", "72o"); numeric frequencies on hover only. Agent B's display matrix + Agent A's input matrix both honor this.
- **Q3:** Default iterations = 1000 (NOT 2000). Target-exploitability mode is the opt-in alternative. **Weakly-held — see §6.**
- **Q4:** Bet sizes default = 4 of 6 checked (33% / 75% / 100% / all-in). Agent A's run panel encodes.
- **Q5:** Combo inspector position = below the matrix (full-width horizontal strip). Agent B owns; Agent A leaves the horizontal real estate untouched.
- **Q6:** Tree reach filter default = 0.01 (slider visible above tree). Agent B's `SolveTree.__init__(min_reach=0.01)` default. Agent A's `UIPrefs.tree_reach_filter = 0.01`.
- **Q7:** Yellow "Mock mode" banner across the top, dismissible (downgrades to subtle `(mock)` chip in PR 10b). Agent A renders the banner (`mock-mode-banner` marker); Agent C's smoke test 1 asserts it.

**Theme default:** dark mode default per Q7 lock (the yellow banner reads correctly against dark; auto/system-preference fallback is the override path per `ui_design_principles.md` §5).

**Parallel fan-out during agent runtime (per PLAN.md §5 + runbook §"Step 3"):** while A/B/C run, launch independent agents on downstream work so the orchestrator never idles. Candidates:
- PR 10b consistency review against the as-built PR 10a surface (worker-import line drift check).
- PR 11 (desktop wrapper + library persistence) spec polish.
- `docs/autonomous_log.md` housekeeping (prune entries per the continuous-pruning rule).
- Doc inventory sweep (check if any cross-PR references became stale after PR 5 merge).

Aggregate per wave — do NOT react agent-by-agent. Wait for all three implementation agents to return, then synthesize the result vector in one pass.

---

## 4. Monitor + reconciliation patterns (PR 10a-specific failure signatures)

While agents run, the orchestrator does NOT block. Track agent completion via the standard background-task notification stream.

### 4a. NiceGUI 2.x API drift

**Symptom:** Agent A or Agent B reports `AttributeError: 'ui' has no attribute 'echart'` (or similar) on the log-scale chart, or `ElementFilter(marker=...)` not resolving.

**Common causes:**
- Agent installed `nicegui<2.0` (1.x didn't expose `ui.echart` natively). Pinned dependency is `nicegui>=2.0,<3.0`; Agent C owns the `[ui]` extra in `pyproject.toml`.
- `ui.line_plot` used instead of `ui.echart` (1.x convention; 2.x supports both but only `ui.echart` exposes `yAxis.type: 'log'`).

**Diagnosis:** check `pip show nicegui` for installed version; cross-reference `nicegui/llms.md` (if present locally) for the 2.x API surface.

### 4b. Mock-solver public-surface drift

**Symptom:** Agent A's `SolveRunner._worker` raises `TypeError: mock_solve() got an unexpected keyword argument 'X'` (or similar).

**Common causes:**
- Agent C's `mock_solve` signature drifted from the byte-locked first-8-parameter contract in `pr10a_spec.md` §7.1. The first 8 params MUST match PR 5's `solve_hunl_postflop` exactly so PR 10b is a one-line swap.
- Field name mismatch in `HUNLConfig` deserialization (the mock returns a `HUNLConfig` from `load_fixture(...)`; Agent A's `Spot.to_hunl_config()` must build the same shape).

**Diagnosis:** `pr10a_spec.md` §7.1 is canonical for the mock signature. PR 5's `solve_hunl_postflop` signature is the byte-baseline.

### 4c. ElementFilter marker drift between Agent A / B and Agent C's tests

**Symptom:** Agent C's smoke tests fail with `KeyError: marker 'X'` or `len(elements) == 0` when the marker should resolve.

**Common causes:**
- Agent A didn't register a marker Agent C's test queries (e.g., `preset-shortstack-25bb`, `mock-mode-banner`).
- Agent B didn't register a marker on the matrix grid (`matrix-cell` — must yield exactly 169 elements per smoke 6).
- Marker name spelling diverged between prompt and impl (underscore vs. hyphen — pr10a §9 preset markers convention: underscores in IDs become hyphens in markers).

**Diagnosis:** the consolidated marker list lives in `agent_c_prompt.md` §7 (Critical correctness item 7). Cross-reference against actual `ui/*.py` files; the spec is canonical.

### 4d. UI threading hazards (PR 10a-specific)

**Symptom:** UI freezes during solve; or `RuntimeError: Cannot call NiceGUI from worker thread` raised; or stop button has multi-second latency.

**Common causes:**
- Worker thread calling NiceGUI API directly (must be read-only state via the `SolveRunner` attributes; the `ui.timer(0.5, refresh)` poller is the only path into the UI).
- `_CANCEL_FLAG` not propagated from `SolveRunner._stop_event` into the mock's per-snapshot check (per `pr10a_spec.md` §7.5 contract).
- `asyncio.to_thread` used instead of `threading.Thread` (locked decision: `threading.Thread` for interruptibility + resumability).

**Diagnosis:** Agent A prompt §"Critical correctness items" #1 + #2 are canonical. The worker pseudocode in §7.5 of the spec is the exact pattern.

### 4e. Browser-state persistence (`~/.poker_solver_ui/state.json`)

**Symptom:** UI state lost across launches; or corrupt JSON crashes app on second launch; or tests pollute the real home dir.

**Common causes:**
- Non-atomic write (Agent A skipped the `state.json.tmp` → `fsync` → `rename` pattern in `pr10a_spec.md` §9.2).
- Load failure (corrupt / version-mismatched JSON) not handled with the backup-to-`state.json.bak` + defaults pattern.
- Tests didn't use the `isolated_state_dir` fixture (Agent C must monkeypatch the state path; spec §10 + `agent_c_prompt.md` Default decisions).

**Diagnosis:** §9.2 of the spec + `agent_a_prompt.md` Critical correctness item 5 are canonical.

### 4f. Mock-data fidelity (poker-realism eye test)

**Symptom:** Fixtures load and render but a poker-literate user calls out a dominated action (e.g., calls on AA pre on a dry board) or missing polarization on a river.

**Common causes:**
- Hand-crafted fixtures violate MDF, miss polarization on rivers, or skip blocker effects.
- Interpolation fallback off-distribution: combos not in the curated fixture set are filled in with naive defaults.

**Diagnosis:** spec §7.4 (12-fixture acceptance criteria) is canonical: realistic mixing, no dominated actions, MDF-obeying bluff freq on rivers, polarization on rivers vs. flops, blocker effects on rivers. The (mock) banner mitigates by warning users — but if the eye test is loudly failing on common spots, that's a should-fix from the audit pass.

---

## 5. Audit + commit pipeline (after all 3 agents report back)

Per `pr_launch_runbook.md` §"Step 4–8". Run audit + check battery in same parallel wave.

### 5a. Interface drift reconciliation (runbook §"Step 4")

After ALL three agents return, run Agent C's tests against Agents A+B's implementation:

```sh
cd /Users/ashen/Desktop/poker_solver
pip install -e .[ui]      # pulls nicegui>=2.0,<3.0
pytest tests/test_ui_smoke.py -xvs    # 20 tests (per pr10a_spec.md §10)
poker-solver ui            # manual smoke; load each of the 12 fixtures
```

Typical drift patterns:
- ElementFilter marker name mismatch — fix the side that diverged from `agent_c_prompt.md` §7 marker list.
- `ruff`/`black` formatting drift on Agent C's `cli.py` edits — auto-fix: `ruff check --fix --unsafe-fixes ui/ tests/ poker_solver/cli.py && black ui/ tests/ poker_solver/cli.py`.
- `mypy --strict ui/` finds Optional/Union edge cases at the `ui.state` boundary — fix narrowly.

After all fixes: `pytest -x` MUST be fully green before proceeding to audit.

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

Concurrently, launch the audit agent:

```
Agent tool call (audit):
  description: "PR 10a audit — fresh reviewer, no implementation context"
  prompt: <full body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md
           between the two `---` markers>
  subagent_type: general-purpose
  run_in_background: true
```

Audit writes its report to `docs/pr10_prep/audit_report.md`. While both run, fan out additional downstream-PR work per parallelization rule.

After both complete:
- Read `pr_report.md` (output of `check_pr.sh`). Confirm "ready for user review" with all gates `OK` or `skip` (NOT `FAIL`).
- Read `docs/pr10_prep/audit_report.md`. **`must-fix` items are a hard stop.** `should-fix` / `nice-to-fix` can be deferred to a follow-up with a TODO.

PR 10a-specific must-fix triggers (per audit focus areas):
- UI blocks on solver (no worker thread, or worker calls NiceGUI directly).
- Stop button doesn't halt within 1 (mocked) iteration.
- Off-by-one in matrix combo → cell mapping (smoke 7 is the gate).
- Opponent hole-card leak in tooltips (spec §13 open decision 9: matrix shows the **player-to-act**'s strategy only).
- NiceGUI in base `dependencies` rather than the `[ui]` extra.
- `ui/` placed inside `poker_solver/` (must be a sibling).
- `poker_solver/range.py` modified (`RangeWithFreqs` MUST wrap, not modify).
- Library viewer isn't a stub (premature PR 11 work).

### 5c. Commit (runbook §"Step 6")

```sh
cd /Users/ashen/Desktop/poker_solver
git status   # verify what is staged; confirm no .env / secrets / state.json blobs
git add ui/ tests/test_ui_smoke.py poker_solver/cli.py pyproject.toml README.md docs/pr10_prep/audit_report.md
git status   # re-verify staged set is exactly the PR 10a surface
git commit -m "$(cat <<'EOF'
PR 10a: NiceGUI scaffold against MOCK solver

Ships the NiceGUI browser UI (two-pane layout per Q1 lock: matrix center
+ collapsible right sidebar) wired to ui/mock_solver.py, which produces
realistic HUNLSolveResult instances for 12 hand-crafted fixture spots.
The UI is the exact artifact PR 10b ships; only ui/mock_solver.py
contents change between PRs.

Seven Q1-Q7 design decisions locked in pr10a_spec.md §0.1 against three
landed UX research docs (competitor_ui_deep_dive, ui_design_principles,
ui_mockups_and_debates). Yellow "Mock mode" banner (Q7) surfaces the
fixture provenance; downgrades to subtle (mock) chip in PR 10b.

NiceGUI 2.x pinned (>=2.0,<3.0) as a [ui] optional-dependency extra so
engine-only users don't pay the install cost. CLI lazy-imports ui.app.

Test result: 20/20 smoke pass (was <Y>/<Y> on integration tip).
Audit: <must-fix-count> must-fix, <should-fix-count> should-fix,
<nice-to-fix-count> nice-to-fix.
EOF
)"
```

DO NOT use `git add -A` or `git add .`. Stage explicit paths.

### 5d. Push PR branch (runbook §"Step 7")

```sh
git push -u origin pr-10a-ui-mock-first
```

Branch visible at https://github.com/amaster97/poker_solver/tree/pr-10a-ui-mock-first.

### 5e. Merge into integration (runbook §"Step 8")

```sh
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-10a-ui-mock-first -m "Integration: merge PR 10a (ui-mock-first)"
git push origin integration
```

`--no-ff` mandatory (preserves PR-branch lineage in `git log --graph`).

If `git pull --ff-only` reports divergence: STOP. Another session pushed to `integration`. Investigate before merging.

### 5f. Update PLAN.md trajectory (runbook §"Step 10")

In `/Users/ashen/Desktop/poker_solver/PLAN.md` §2 trajectory table: update PR 10a's row to `landed on integration` + record branch name. In `docs/autonomous_log.md`: append progress entry with timestamp + commit hash + test count + audit-finding-count. Plan-sync rule: if `~/.claude/plans/poker_solver.md` was edited, `cp` to local `PLAN.md` before commit.

---

## 6. Orchestrator decisions needed BEFORE this kickoff fires

Polish report (`pr10a_polish_report.md` §5) verdict: **Prompts ready (post-polish).** All seven Q1–Q7 locks encoded as concrete operational guidance in each agent prompt; mock-solver contract consistent across A/B/C; NiceGUI 2.x pinned everywhere.

**One weakly-held lock to flag pre-launch:** **Q3 default iterations = 1000** is the coin-flip flag (per spec §0.1 + §12 risk #5). The competitor evidence supports "fast first-feedback" directionally (DeepSolver "result in just few seconds", GTOW 6 s vs Pio's 4,862 s) but pins no exact integer. If PR 10a manual testing shows under-converged matrices on common spots (river polarization not crisp, flop mixes look noisy), bump to 2000 in PR 10b. The user may override to 2000 at launch time if they have a strong prior; default is launch as spec'd. None of the other six locks (Q1, Q2, Q4, Q5, Q6, Q7) have residual uncertainty per the polish report.

---

## 7. Risks (PR 10a-specific, not present in PR 6/7/8/9)

Original spec §12 lists six risks; this section calls out the three that are **uniquely PR 10a** (downstream PR launches don't touch these surfaces):

1. **UI threading correctness.** The DCFR loop (and the mock's snapshot loop) runs in a `threading.Thread`; the UI event loop polls via `ui.timer(0.5, ...)`. Any path where the worker calls NiceGUI directly will freeze the UI or corrupt state. Cancellation flows through `_CANCEL_FLAG` (`threading.Event`) — the same flag survives the PR 10b swap. Stop-button correctness is the smoke 5 gate; UI-blocks-on-solver is the audit focus area #1.

2. **Browser-state persistence atomicity (`~/.poker_solver_ui/state.json`).** Atomic write (`state.json.tmp` → `fsync` → `rename`) is required; corrupt JSON on second launch must back up to `state.json.bak` and start from defaults rather than crash. Debounced save (500 ms window). The onboarding-modal gating bool (`prefs.onboarding_completed`) is independent of file presence per spec §12 risk #6, so wiping `state.json` for testing doesn't also nuke panel widths.

3. **Mock-data fidelity (poker-realism eye test).** Twelve hand-crafted fixtures (`pr10a_spec.md` §7.4) must pass a poker-player eye test: realistic mixing, no dominated actions, MDF-obeying bluff freq on rivers, polarization on rivers vs. flops, blocker effects on rivers. The yellow "Mock mode" banner (Q7) is the auditability mitigation — fixture provenance is loudly disclosed for the first 30 s of every session — but it does NOT excuse obviously-wrong strategies. Interpolation fallback on off-distribution combos is a known cliff (spec §12 risk #2).

Auxiliary PR-10a-only risks worth tracking but lower-severity:
- **Palette disjointness drift** (spec §12 risk #4): future PRs repurposing the blue input-matrix palette for a strategy element silently break principle 4. Smoke test #16 locks the assertion.
- **Surface drift PR 10a → PR 10b** (spec §12 risk #3): PR 9's preflop solver could add a kwarg `solve_hunl_postflop` lacks. PR 9 spec consistency review checks alignment.
- **Q3 1000 vs 2000 coin-flip** (spec §12 risk #5): see §6 above. Bump in PR 10b if needed.

---

## 8. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` — canonical spec (read end-to-end before launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_a_prompt.md` — Agent A prompt body (post-polish).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_b_prompt.md` — Agent B prompt body (post-polish).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_c_prompt.md` — Agent C prompt body (post-polish; 20 tests).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md` — audit agent prompt body.
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report.md` — written by audit agent (does not exist pre-launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_polish_report.md` — pre-launch readiness provenance ("Prompts ready (post-polish)").
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` — companion spec for the post-10a mechanical swap.
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/competitor_ui_deep_dive.md` — load-bearing reference for the §0.1 Q1–Q7 evidence matrix.
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/ui_design_principles.md` — 9 principles, 8 anti-patterns, 4-tier disclosure.
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/ui_mockups_and_debates.md` — 5 view mockups + 6 pro/con debates + 5 edge cases.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook.
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/Users/ashen/Desktop/poker_solver/pr_report.md` — written by `check_pr.sh` at repo root.
- `/tmp/integration_pre_pr_10a.hash` — reflog backup hash (pre-flight 1f).
