# PR 10b fan-out ready — pre-staged launch sequence (single-agent execution)

**Status:** PRE-STAGED. Do NOT execute until BOTH PR 9 AND PR 10a have merged to `integration`.

**Last verified:** 2026-05-22. Mock solver byte-locked first-8-parameter contract in `pr10a_spec.md` §7.1; PR 9 §4 amendment (derived from `pr10b_spec.md` §3) mandates `on_progress: Callable[[int, float, MemoryReport], None] | None = None` on `solve_hunl_preflop`; PR 10b adds the same kwarg to `solve_hunl_postflop` (one engine-side change).

This doc collapses `launch_kickoff_10b.md` into the fire-when-PR-9+10a-land order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10b.md`. This file is the operational shortlist.

**Why no three-agent fan-out:** PR 10b is a delete-and-replace of one file (`ui/mock_solver.py`) plus one kwarg added to one solver function plus a 5-test-delete / 2-test-add diff on `tests/test_ui_smoke.py`. Coordination overhead of fan-out exceeds the work itself. One agent owns the whole PR; the orchestrator launches downstream PR 11 work in parallel waves while the implementation agent runs.

---

## 1. Pre-flight gate (run AFTER PR 9 AND PR 10a land, BEFORE branch creation)

All five must pass. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. BOTH PR 9 and PR 10a merged to integration.
git fetch origin
git log --oneline integration -20
# Expected: both "Integration: merge PR 9 (hunl-preflop)" and
# "Integration: merge PR 10a (ui-mock-first)" reachable from integration.
git rev-parse integration; git rev-parse origin/integration   # must be equal

# 1b. working tree clean.
git status

# 1c. PR 9's preflop solver exposes `on_progress` with the locked signature
# (postflop's `on_progress` is added BY PR 10b — not expected to exist yet).
python -c "
import inspect
from poker_solver.preflop_solver import solve_hunl_preflop
from poker_solver.hunl_solver import solve_hunl_postflop
sig_pre = inspect.signature(solve_hunl_preflop)
assert 'on_progress' in sig_pre.parameters, 'PR 9 preflop solver missing on_progress kwarg'
print('PR 9 surface OK; postflop kwarg added by PR 10b')
print('preflop on_progress default:', sig_pre.parameters['on_progress'].default)
"
# If preflop `on_progress` is absent or its signature deviates from
# `Callable[[int, float, MemoryReport], None] | None = None`, STOP and fix PR 9
# on integration first — the dispatch wrapper assumes identical kwarg shape.

# 1d. PR 10a smoke tests green on integration (8 retained + 5 mock-specific that
# this PR deletes + 7 other = 20 total per pr10a_spec.md §10).
pytest tests/test_ui_smoke.py -x -q   # expect 20 pass

# 1e. Reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10b.hash
```

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-10b-ui-real-solver integration
git status   # expect: clean tree on pr-10b-ui-real-solver
```

---

## 3. Single-agent execution (NO fan-out)

One agent owns the whole swap. Prompt points the agent at `pr10b_spec.md` as canonical and names: the branch (`pr-10b-ui-real-solver`); the engine-side kwarg addition (`solve_hunl_postflop`'s `on_progress`); the delete list (§5); the test delete list (5 tests, §5) + test add list (2 tests, §6); the forbidden surface — every `ui/views/*.py`, every Q1-Q6 lock (Q7 banner→chip is the only allowed UX delta), all PR 10a marker contracts, `poker_solver/range.py`, the library viewer stub.

```
Agent (sole) — "PR 10b — swap mock solver for real solvers (single-agent swap)"
  prompt: <body derived from pr10b_spec.md §0-§6 + launch_kickoff_10b.md §3 forbidden-files list>
  subagent_type: general-purpose
  run_in_background: true
```

**Files touched by the agent:**

| Surface | Change |
|---|---|
| `poker_solver/hunl_solver.py` | Add `on_progress` kwarg to `solve_hunl_postflop`; thread into `_run_with_probe` per spec §3 diff |
| `ui/state.py` | Replace mock import with dispatch wrapper (`_solve_postflop_impl` routes preflop→`solve_hunl_preflop`, postflop→`solve_hunl_postflop`) |
| `ui/mock_solver.py` | DELETE |
| `ui/mock_solver_fixtures.py` | DELETE (if PR 10a created it as a split file) |
| `ui/app.py` (or wherever Q7 banner lives) | Yellow banner → subtle `(mock)` chip in header; chip disappears after first successful real solve |
| `tests/test_ui_smoke.py` | Delete 5 mock-specific tests; add 2 real-solve tests |
| `README.md` | `## UI (mock)` → `## UI`; remove PR 10a mock-mode paragraph |

**Forbidden (must NOT touch):** any `ui/views/*.py` (UI structure frozen); any Q1-Q6 design lock from `pr10a_spec.md` §0.1; PR 10a marker contracts (`matrix-cell`, `preset-*`, etc. — only `mock-mode-banner`→`mock-mode-chip` swap permitted); `poker_solver/range.py`; the library viewer stub (grows in PR 11).

**Parallel fan-out during the implementation agent's runtime:** PR 11 spec polish; autonomous-log pruning; doc inventory sweep for stale cross-PR refs after PR 9 + PR 10a merges. Aggregate per wave.

---

## 4. Expected outputs + timeline

**Wall-clock:** ~45-90 min (small mechanical diff; most time spent on the dispatch wrapper + the 2 new tests + manual smoke of `default_tiny_subgame`).

**Deliverables (PR surface):** ~150-300 LOC net (more deletes than adds: `ui/mock_solver.py` is ~400-600 LOC gone; `ui/state.py` dispatch wrapper ~15 LOC; `hunl_solver.py` kwarg addition ~4 LOC; tests net-negative ~3).

**Pass criteria:** 8 retained PR 10a smoke tests pass UNMODIFIED after the swap (regression alarm); 2 new real-solve tests pass; full suite green (`on_progress` defaults to `None` so PR 5/6/7 callers unaffected); `poker-solver ui` loads `default_tiny_subgame` and DCFR converges (river-only, <2 s manual smoke).

---

## 5. Post-execution: audit + commit

Per `launch_kickoff_10b.md` §5. Audit focus is lighter than 10a's: (1) UI structure regression vs. PR 10a markers + smoke tests; (2) `on_progress` fires on worker thread, not main; (3) `ui/mock_solver*.py` actually deleted (`git ls-files | grep mock_solver` returns nothing); (4) kwarg addition doesn't break PR 5/6/7 existing tests.

PR-10b-specific must-fix triggers: any PR 10a Q1-Q6 lock changed (Q7 banner→chip is the ONLY allowed UX delta); any retained PR 10a smoke test failing after the swap; `on_progress` invoked from main thread; `ui/mock_solver.py` still present; existing PR 5/6/7 tests broken by the kwarg addition.

Commit explicit paths: `git add poker_solver/hunl_solver.py ui/state.py ui/app.py tests/test_ui_smoke.py README.md && git rm ui/mock_solver.py` (+ `git rm ui/mock_solver_fixtures.py` if it exists). Never `git add -A`. Push `pr-10b-ui-real-solver`; `--no-ff` merge into `integration`; update `PLAN.md` trajectory + `docs/autonomous_log.md`.

Full pipeline lives in `launch_kickoff_10b.md` §5a-5d. This doc stops at execution kickoff.
