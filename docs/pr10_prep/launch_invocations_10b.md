# PR 10b launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until BOTH PR 9 (HUNL preflop solver) AND PR 10a (NiceGUI scaffold + mock) have merged to `integration` AND the user has approved firing PR 10b.

**Purpose:** mechanical operations sheet for firing PR 10b — paste blocks in order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10b.md`. Operational shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10b.md`. Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` (273 lines, canonical for the swap).

**Why SINGLE-agent, not 3-agent fan-out:** PR 10b is a delete-and-replace of one file (`ui/mock_solver.py`) plus a dispatch wrapper swap in `ui/state.py` plus a 5-test-delete / 2-test-add diff on `tests/test_ui_smoke.py`. Coordination overhead of fan-out exceeds the work itself. One agent owns the whole PR; orchestrator fans out downstream PR 11 work in parallel waves while the implementation agent runs.

**Post-PR-10a-Option-A note:** PR 10a's `mock_solve` is byte-identical to `solve_hunl_postflop` (no `on_progress` kwarg; progress published to a module-level `_LATEST_PROGRESS` buffer read by a `ui.timer` poll). PR 10b does **NOT** add `on_progress` to the engine. Swap reduces to: 1 import line, delete `ui/mock_solver.py` (+ `ui/mock_solver_fixtures.py` if present), delete the mock-only `_publish_progress` call site, and connect real-solver progress via a watcher thread reading `solver.iteration` / `solver.exploitability_history` at the poll cadence (Option A §4.4 A1, ~30 LOC inside `ui/state.py`).

---

## 1. Pre-launch verification (run AFTER PR 9 + PR 10a both land, BEFORE branch creation)

All five checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. BOTH PR 9 and PR 10a merged to integration.
git fetch origin
git log --oneline integration -20
# Expected: both "Integration: merge PR 9 (hunl-preflop)" and
# "Integration: merge PR 10a (ui-mock-first)" reachable from integration.
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1b. Branch pr-10b-ui-real-solver does NOT yet exist.
git branch --list pr-10b-ui-real-solver
# Expected: empty. If branch exists from prior aborted launch, rename
# (`git branch -m pr-10b-ui-real-solver-prior`) before re-creating.

# 1c. Working tree clean.
git status   # expected: "nothing to commit, working tree clean"

# 1d. PR 9 preflop solver + PR 10a mock signature parity check.
# Post-Option-A: neither solver needs `on_progress`. The dispatch wrapper
# routes by config.street; both real callables share the byte-identical
# first-N positional surface (config, abstraction, iterations,
# target_exploitability, memory_budget_gb, *, log_every, seed, dcfr_kwargs).
python -c "
import inspect
from poker_solver.preflop_solver import solve_hunl_preflop
from poker_solver.hunl_solver import solve_hunl_postflop
from ui.mock_solver import mock_solve
sig_pre = inspect.signature(solve_hunl_preflop)
sig_post = inspect.signature(solve_hunl_postflop)
sig_mock = inspect.signature(mock_solve)
# Real-vs-real positional parity (dispatch wrapper requirement).
pre_pos = [p for p in sig_pre.parameters.values() if p.kind != p.KEYWORD_ONLY]
post_pos = [p for p in sig_post.parameters.values() if p.kind != p.KEYWORD_ONLY]
assert [p.name for p in pre_pos] == [p.name for p in post_pos], (
    f'PR 9 preflop positional surface drifts from postflop: '
    f'pre={[p.name for p in pre_pos]} post={[p.name for p in post_pos]}'
)
# Mock-vs-real parity (Option A invariant; lets PR 10b be a 1-line swap).
assert 'on_progress' not in sig_mock.parameters, (
    'PR 10a mock still has on_progress; Option A did not land. STOP.'
)
print('Dispatch surface OK; mock is byte-identical to real (Option A).')
"
# If positional surfaces diverge or the mock still carries `on_progress`,
# STOP — Option A did not fully land in PR 10a (re-check mock_signature_drift.md).

# 1e. PR 10a smoke tests green on integration (20 tests per pr10a_spec.md §10).
pytest tests/test_ui_smoke.py -x -q   # expect 20 pass

# 1f. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10b.hash
echo "integration tip pre-PR-10b: $(cat /tmp/integration_pre_pr_10b.hash)"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green before branching.

---

## 2. Branch creation

Branch name `pr-10b-ui-real-solver` is hard-coded in the kickoff and fanout-ready docs — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration   # last sanity check before branching
git checkout -b pr-10b-ui-real-solver
git status         # expect: clean tree on pr-10b-ui-real-solver
git log --oneline -1   # expect: PR 10a or PR 9 merge commit (whichever landed later)
```

---

## 3. Single-agent execution (NO fan-out)

One agent owns the whole swap. Prompt body is derived inline from `pr10b_spec.md` §0-§6 plus `launch_kickoff_10b.md` §3 forbidden-files list (per `fanout_ready_10b.md` §3 — no dedicated agent prompt file exists because PR 10b is too small to warrant one). The prompt must name: the branch (`pr-10b-ui-real-solver`); the **NO engine-side kwarg addition** post-Option-A (the mock is now byte-identical to the real solver; PR 10b does **not** touch `poker_solver/hunl_solver.py`); the delete list (§5); the test delete list (5 tests) + test add list (2 tests); the forbidden surface; the watcher-thread requirement to wire real-solver progress into `_LATEST_PROGRESS` (Option A §4.4 A1, ~30 LOC in `ui/state.py`).

```
Agent (sole) — "PR 10b — swap mock solver for real solvers (single-agent swap)"
  prompt: <body derived from pr10b_spec.md §0-§6 + launch_kickoff_10b.md §3 forbidden-files list>
  subagent_type: general-purpose
  run_in_background: true
```

**Files the agent touches (post-Option-A):**

| Surface | Change |
|---|---|
| `poker_solver/hunl_solver.py` | **NO CHANGE** (Option A obsoleted the on_progress addition) |
| `ui/state.py` | Replace mock import with dispatch wrapper (`_solve_postflop_impl` routes preflop→`solve_hunl_preflop`, postflop→`solve_hunl_postflop`); add watcher thread (~30 LOC, §4.4 A1) that polls `solver.iteration`/`solver.exploitability_history` and calls `_publish_progress` so `_LATEST_PROGRESS` stays warm |
| `ui/mock_solver.py` | DELETE |
| `ui/mock_solver_fixtures.py` | DELETE (if PR 10a split it out) |
| `ui/progress_buffer.py` | KEEP — buffer module is engine-agnostic. If PR 10a placed `_publish_progress` inside `ui/mock_solver.py`, lift it to `ui/progress_buffer.py` before deleting the mock |
| `ui/app.py` (or wherever Q7 banner lives) | Yellow banner → subtle `(mock)` chip in header; chip disappears after first successful real solve |
| `tests/test_ui_smoke.py` | Delete 5 mock-specific tests (per §5); add 2 real-solve tests (per §6) |
| `README.md` | `## UI (mock)` → `## UI`; remove PR 10a mock-mode paragraph |

**Forbidden surface (do NOT relax):** any `ui/views/*.py` (UI structure frozen); any Q1-Q6 design lock from `pr10a_spec.md` §0.1 (Q7 banner→chip is the ONLY allowed UX delta); PR 10a marker contracts (`matrix-cell`, `preset-*`, etc. — only `mock-mode-banner`→`mock-mode-chip` swap permitted); `poker_solver/range.py`; the library viewer stub (grows in PR 11).

**Parallel fan-out during the implementation agent's runtime** (per parallel-agents-default + min-five-agents memory rules): PR 11 (desktop wrapper + library persistence) spec polish; `docs/autonomous_log.md` housekeeping (continuous-pruning rule); doc inventory sweep for stale cross-PR refs after PR 9 + PR 10a merges. Aggregate per wave; do NOT react agent-by-agent.

---

## 4. Expected wall-clock: ~45-90 min

Small mechanical diff — most time spent on the dispatch wrapper + the 2 new tests + manual smoke of `default_tiny_subgame`. Per `fanout_ready_10b.md` §4:
- Single agent: ~45-90 min total.
- Audit + check battery + reconciliation: ~20-30 min.
- Commit + merge: ~5 min.

**Total: ~1.5-2 hours wall-clock** end-to-end (PR 10b branch creation → integration merge).

**Deliverables (PR surface, post-Option-A):** ~200-350 LOC net negative (more deletes than adds: `ui/mock_solver.py` is ~400-600 LOC gone; `ui/state.py` dispatch wrapper ~15 LOC; `ui/state.py` watcher thread ~30 LOC; `poker_solver/hunl_solver.py` **0 LOC change** post-Option-A; tests net-negative ~3).

---

## 5. PR-10b-specific risk reminders

Two risks are uniquely critical to PR 10b (uncovered by PR 10a's mock; full ladder in `launch_kickoff_10b.md` §4 + §6):

1. **UI structure regression vs. PR 10a (the dominant risk).** PR 10b's job is to swap the solver, NOT to redesign the UI. Q1-Q6 stay literally identical; only Q7 changes (banner → chip). The forbidden-files list in §3 above is the gate. The 8 retained PR 10a smoke tests are the regression alarm — if any fails after the swap, that's must-fix before merge. The library viewer stub stays a stub until PR 11; growing it in PR 10b is scope creep.

2. **Positional surface drift between PR 9 preflop, PR 5 postflop, and the PR 10a mock.** Dispatch wrapper assumes the first N positional params (`config`, `abstraction`, `iterations`, `target_exploitability`, `memory_budget_gb`) are name-and-order identical across `solve_hunl_preflop`, `solve_hunl_postflop`, and `mock_solve`. Option A locked this; pre-flight 1d enforces. If any of the three drifted (e.g., PR 9 landed with `abstraction` after `iterations`), fix at the source on integration BEFORE landing PR 10b — do NOT paper over with adapter logic in the UI.

3. **Watcher thread correctness (Option A §4.4 A1).** Real `solve_hunl_postflop` runs `_run_with_probe` internally; intermediate state is not visible to the caller via callback. PR 10b's worker spawns a watcher thread that reads `solver.iteration` / `solver.exploitability_history` (or whatever the DCFRSolver instance exposes) at the `ui.timer` poll cadence and publishes to `_LATEST_PROGRESS`. Watcher must (a) clean-up on solve completion (no zombie threads), (b) not race the worker's result handoff, (c) be guarded by the same `_PROGRESS_LOCK` as the buffer. If watcher access requires exposing `solver` on `SolveRunner`, that is acceptable per Option A §4.4.

Auxiliary lower-severity:
- **Real DCFR wall-clock surprise** — mock returned in seconds; real flop solves can be minutes. UI was designed for this; README "Quick tour" recommends `default_tiny_subgame` for first-time use.
- **`MemoryReport` range divergence** — responsive formatting should hold; cosmetic should-fix if not.
- **Tree-browser performance with real trees** — lazy + 2000-cap design from PR 10a; smoke 8 retained gate.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff_10b.md` §5a-5d. After the single agent returns:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation (test the swap).
pytest tests/test_ui_smoke.py -xvs    # expect ~10 tests (8 retained + 2 new)
pytest -x                              # full suite; gates the on_progress kwarg
                                       # addition against PR 5/6/7 existing tests
poker-solver ui                        # manual smoke; load default_tiny_subgame
                                       # and confirm real DCFR converges (<2 s)

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 10b audit — fresh reviewer, no implementation context"
#     prompt: <body derived from pr10b_spec.md §7 acceptance criteria + launch_kickoff_10b.md §5b focus areas>
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr10_prep/audit_report_10b.md.

# 6c. Commit (explicit paths only — no git add -A).
# Post-Option-A: poker_solver/hunl_solver.py is NOT in the diff.
git status   # verify staged set; no .env / secrets / build artifacts
git add ui/state.py ui/app.py \
        tests/test_ui_smoke.py README.md docs/pr10_prep/audit_report_10b.md
# git add ui/progress_buffer.py        # if buffer module lifted out of mock
git rm ui/mock_solver.py
# git rm ui/mock_solver_fixtures.py    # if it exists
git status   # re-verify staged set is exactly the PR 10b surface
git commit -m "PR 10b: swap mock solver for real solvers"   # full message in launch_kickoff_10b.md §5c

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-10b-ui-real-solver
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-10b-ui-real-solver -m "Integration: merge PR 10b (ui-real-solver)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
```

PR-10b-specific must-fix triggers (hard stop): any PR 10a Q1-Q6 lock changed (Q7 banner→chip is the ONLY allowed UX delta); any retained PR 10a smoke test failing after the swap; watcher thread accessing `_LATEST_PROGRESS` without `_PROGRESS_LOCK` or leaking past solve completion; `ui/mock_solver.py` still present (`git ls-files | grep mock_solver` returns nothing); any change to `poker_solver/hunl_solver.py` (post-Option-A this file must be untouched in PR 10b). `should-fix` / `nice-to-fix` can defer to follow-up with TODO. Full failure-mode + recovery in `launch_kickoff_10b.md` §4a-4c.

---

## 7. Quick-reference paths

- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` (canonical for the swap)
- Sibling spec (UI surface this PR must NOT regress): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` §0.1 Q1-Q7 locks
- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10b.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10b.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_invocations_10b.md`
- PR 9 spec (preflop solver — must expose `on_progress`): `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`
- Check battery: `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh`
- Reflog backup: `/tmp/integration_pre_pr_10b.hash`
