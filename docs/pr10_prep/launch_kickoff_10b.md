# PR 10b launch kickoff — swap the mock solver for the real solvers

**Status:** PRE-STAGED PLAYBOOK. Do NOT execute until BOTH PR 9 (HUNL preflop solver) AND PR 10a (NiceGUI scaffold + mock) have merged to `integration` and the user has approved firing PR 10b.

**Purpose:** the exact command sequence the orchestrator runs when both gating PRs have landed and PR 10b is fired. PR 10b is the smallest of the kickoffs — it is a one-import swap plus one engine-side kwarg addition. There is no three-agent fan-out, no UX debate, no surface-design work; the entire PR is a mechanical change against an already-frozen UI.

**Branch:** `pr-10b-ui-real-solver` (per PLAN.md §1 per-PR feature-branch rule).

**Inputs that govern this playbook:**
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` (**updated 2026-05-22 with §0.1 Q3 reframe — exploitability slider**; read end-to-end before launch)
- **One-page launch checklist:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/ready_to_fire_checklist_10b.md` (day-0 action list incorporating the slider reframe; read this if pressed for time)
- Sibling kickoff (reference): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`
- PR 10a spec (the frozen UI surface this PR must NOT regress, except Q3 + Q7): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` §0.1 Q1–Q7 locks (Q3 is reframed per `pr10b_spec.md` §0.1; Q7 downgrades to chip)
- PR 9 spec (preflop solver — must ship `on_progress` kwarg per its §4 amendment derived from `pr10b_spec.md`, AND `target_exploitability` kwarg to support the slider): `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`
- PLAN.md §1 "Solver UI control" row — the canonical reference for the Q3 reframe
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`

**Why this kickoff is shorter than 10a's:** PR 10a was a UX-locked, multi-agent build of a brand-new subsystem (`ui/`). PR 10b is a delete-and-replace of one file (`ui/mock_solver.py`) plus one kwarg added to one solver function, **plus** a single design reframe (Q3 — iter count → exploitability slider; locked 2026-05-22, see `pr10b_spec.md` §0.1). The structural debate is over; the UI is frozen at PR 10a apart from Q3 and Q7; the only new code is a ~30-line dispatch wrapper in `ui/state.py` (with the SOLVE_QUALITY_TIERS dict), a ~4-line addition to `hunl_solver.py`, and a slider element replacing the iter input in `ui/views/run_panel.py`.

---

## 1. Pre-flight gate

All four checks must pass.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. BOTH PR 9 and PR 10a are merged to integration.
git fetch origin
git log --oneline integration -20
# Expected: both "Integration: merge PR 9 (hunl-preflop)" and
# "Integration: merge PR 10a (ui-mock-first)" reachable from integration.

# 1b. integration tip matches origin/integration.
git rev-parse integration
git rev-parse origin/integration
# Hashes equal. If not: `git pull --ff-only origin integration`.

# 1c. Working tree clean.
git status

# 1d. Public-surface sanity: PR 9's `solve_hunl_preflop` exists AND already
# exposes BOTH `on_progress` kwarg (per PR 9 §4 amendment derived from
# pr10b_spec.md §3) AND `target_exploitability` kwarg (required for the
# Q3 slider reframe per pr10b_spec.md §0.1).
python -c "
import inspect
from poker_solver.preflop_solver import solve_hunl_preflop
from poker_solver.hunl_solver import solve_hunl_postflop
sig_pre = inspect.signature(solve_hunl_preflop)
sig_post = inspect.signature(solve_hunl_postflop)
assert 'on_progress' in sig_pre.parameters, 'PR 9 preflop solver missing on_progress kwarg'
assert 'target_exploitability' in sig_pre.parameters, 'PR 9 preflop solver missing target_exploitability kwarg (required for Q3 slider reframe)'
# postflop's on_progress kwarg is ADDED by PR 10b itself; not expected to exist yet.
# postflop's target_exploitability already exists from PR 5; verify.
assert 'target_exploitability' in sig_post.parameters, 'PR 5 postflop solver missing target_exploitability kwarg (unexpected — verify branch)'
print('PR 9 surface OK; postflop on_progress kwarg to be added in PR 10b')
print('preflop on_progress default:', sig_pre.parameters['on_progress'].default)
print('preflop target_exploitability default:', sig_pre.parameters['target_exploitability'].default)
"
# If preflop solver's `on_progress` is absent or its signature deviates from
# `Callable[[int, float, MemoryReport], None] | None = None`, OR if
# `target_exploitability` is absent on EITHER solver, STOP and revisit
# the relevant PR before PR 10b — the dispatch wrapper assumes both kwargs
# are uniformly present.

# 1e. Reflog backup hash.
git rev-parse integration > /tmp/integration_pre_pr_10b.hash
```

Optional sanity: `pytest -x -q` from `integration` — must be green (includes PR 10a's 20 smoke tests against the mock; some will be deleted in this PR).

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-10b-ui-real-solver
git status   # clean, on pr-10b-ui-real-solver
```

---

## 3. Single-agent execution (no fan-out)

PR 10b does not warrant a three-agent fan-out — the diff is small, the files touched are non-overlapping in spirit, and parallelism would create coordination overhead larger than the work itself. One agent owns the whole PR; the orchestrator launches downstream-PR work (PR 11 spec polish, autonomous-log pruning, doc inventory) in parallel waves while the implementation agent runs.

Agent prompt (orchestrator side, one tool call): points the agent at `pr10b_spec.md` as canonical; names the branch (`pr-10b-ui-real-solver`); names the engine-side kwarg addition (`solve_hunl_postflop`'s `on_progress: Callable[[int, float, MemoryReport], None] | None = None`); lists the delete list (§5), the test delete list (5 tests per §5) and test add list (2 tests per §6); forbids any change to UI structure / markers / Q1–Q6 locks (regression protection — only Q7 banner→chip is permitted, per `pr10b_spec.md` §0).

**Files the agent touches:**

| Surface | Change |
|---|---|
| `poker_solver/hunl_solver.py` | Add `on_progress` kwarg to `solve_hunl_postflop`; thread into `_run_with_probe` per `pr10b_spec.md` §3 diff |
| `ui/state.py` | Replace mock import with dispatch wrapper (`_solve_postflop_impl`) per `pr10b_spec.md` §4 diff; add `SOLVE_QUALITY_TIERS` dict + `ITER_SAFETY_CAP` constant (Q3 reframe per §0.1) |
| `ui/views/run_panel.py` | Replace iter-count input with 4-tier `ui.slider` ("Solve quality") + live status line below; demote iter input into "Advanced" `ui.expansion`, hard-clamped at 2000. Markers added: `solve-quality-slider`, `solve-quality-tier-label`, `solve-quality-status-line` |
| `ui/mock_solver.py` | DELETE |
| `ui/mock_solver_fixtures.py` | DELETE (if PR 10a created it as a split file) |
| `ui/app.py` (or wherever Q7 banner lives) | Downgrade yellow banner → subtle `(mock)` chip in header per `pr10b_spec.md` §0; chip disappears after first successful real solve |
| `tests/test_ui_smoke.py` | Delete 5 mock-specific tests (per §5); add 4 real-solve tests (per §6); update 1–2 retained tests' locators to find iter input inside the new Advanced expansion |
| `README.md` | Change `## UI (mock)` → `## UI`; remove the PR 10a mock-mode paragraph |
| `USAGE.md` | Update §4 to use slider-tier framing (Draft/Standard/Tight/Library) instead of "iterations + target-expl mode"; note placeholder defaults pending PR 10c calibration |

**Files the agent MUST NOT touch:**

- Any `ui/views/*.py` (range matrix, tree browser, spot input, library browser, onboarding) — UI structure is frozen.
  **Exception:** `ui/views/run_panel.py` is touched in this PR to swap the iter-input element for the new exploitability slider (Q3 reframe per `pr10b_spec.md` §0.1). The rest of run_panel.py (chart, buttons, backend toggle) stays unchanged.
- Six of the original seven Q1–Q7 design decisions (`pr10a_spec.md` §0.1). The two-pane layout, cell labels, 4-of-6 bet sizes, below-matrix inspector, reach filter 0.01, and the dark theme stay identical. **Q3 and Q7 change** per `pr10b_spec.md` §0:
  - **Q3 (reframed):** iter-count input → exploitability slider (4 tiers); iter input demoted to "Advanced" expansion, capped at 2000.
  - **Q7 (downgrade):** yellow banner → subtle `(mock)` chip in the header (or removed entirely once a real solve completes successfully).
  These are the **only** two visible UI differences between PR 10a and PR 10b.
- Marker contracts registered in PR 10a (`mock-mode-banner`, `matrix-cell`, `preset-*`, etc.). If the Q7 banner element is removed in favor of a chip, the test that asserted the banner's presence is among the 5 deleted; the chip needs a new marker (`mock-mode-chip`) that the new test 14/15 may or may not query (test design decision lives in the agent prompt).
- `poker_solver/range.py` (RangeWithFreqs invariant from PR 10a audit).
- The library viewer stub (`ui/views/library_browser.py`) stays a stub — that file grows in PR 11.

**Parallel fan-out during the implementation agent's runtime:**

- PR 11 (desktop wrapper + library persistence) spec polish.
- `docs/autonomous_log.md` housekeeping (continuous-pruning rule).
- Doc inventory sweep for stale cross-PR references after PR 9 + PR 10a merges.

Aggregate per wave.

---

## 4. Monitor + reconciliation patterns (PR 10b-specific failure signatures)

### 4a. `on_progress` kwarg signature mismatch between PR 9 (preflop) and PR 10b (postflop)

**Symptom:** the dispatch wrapper in `ui/state.py` calls `solve_hunl_preflop(..., on_progress=cb)` and gets `TypeError: got an unexpected keyword argument 'on_progress'`, OR the preflop solver accepts the kwarg but invokes it with a different tuple shape (e.g., `cb(iter, expl, memory_gb_float)` instead of `cb(iter, expl, MemoryReport)`).

**Common causes:**
- PR 9 shipped without the §4 amendment that mandates the `on_progress: Callable[[int, float, MemoryReport], None] | None = None` kwarg. The pre-flight 1d check is the gate against this; if it slipped past, fix PR 9 first (a tiny follow-up commit on integration before PR 10b).
- The callback's third argument shape diverged. PR 10b's spec §3 fixes this as `MemoryReport` (the same class PR 5 already exposes from `poker_solver.profiler.memory`).

**Diagnosis:** `inspect.signature(solve_hunl_preflop)` + `inspect.signature(solve_hunl_postflop)` should be structurally identical on the first nine positional/keyword parameters and on `on_progress`. The pre-flight 1d check catches the absence case; signature equality is the agent's responsibility.

### 4b. UI structure regression vs. PR 10a

**Symptom:** PR 10a's 8 retained smoke tests (the structural ones, NOT the 5 mock-specific tests being deleted) start failing after the swap. Examples: matrix no longer renders 169 cells; preset dropdown items renamed; marker spellings drifted; combo inspector moved out of below-matrix position.

**Common causes:**
- The agent edited a `ui/views/*.py` file it should not have touched. The forbidden-files list in §3 above is the gate; the agent must respect it.
- Q7 banner downgrade was implemented as a structural change to the page header rather than as a marker swap (yellow banner element → `(mock)` chip element). The chip should occupy nominal-width header real estate, not push other elements.
- The 5 deleted tests included one that was actually structural rather than mock-specific (review the deletion set against `pr10b_spec.md` §5; the named list is canonical — do not delete tests outside the named list).

**Diagnosis:** after the swap, ALL 8 retained smoke tests must still pass without modification. If any retained test fails, that's a regression — fix the impl, not the test.

### 4c. Real-solver wall-clock + memory + tree-size surprises (consolidated)

The mock fabricated cheap latencies (~5–10 s), round memory numbers (~2 GB flop / ~1 GB turn / ~0.5 GB river), and tiny curated trees (~50 nodes). Real solvers are not cheap and not round; PR 10b is where these realities first reach the UI.

- **Wall-clock:** real flop at 1000 iters ≈ 30–60 s; at 50_000 iters ≈ 5–15 min (PLAN.md §1 perf table). UI handles this via `ui.timer(0.5, ...)` + worker thread (per `pr10a_spec.md` §7.5). README's "Quick tour" recommends `default_tiny_subgame` (river-only, <2 s) for first-time use. Smoke 15 gates that `on_progress` fires at least once per 500-iter run with `log_every=100`; if `log_every` defaults to `None` in the run panel, the expl chart stays empty and the UI looks hung — should-fix candidate (default `log_every=100`).
- **Memory:** real `MemoryReport.total_gb` may diverge from the mock's plausible 0.5–2 GB band (e.g., 8 GB flop). PR 10a's memory panel uses `f"{report.total_gb:.2f} GB"` responsive formatting (`pr10b_spec.md` §8 risk #3), so layout should hold; cosmetic should-fix if not.
- **Tree size:** real trees have 10^4–10^6 infosets vs. the mock's ~50. PR 10a's tree adapter is lazy + caps visible nodes at 2000 (`pr10_spec.md` §8.5). `test_tree_visible_nodes_under_cap` from PR 10a is retained and gates the structural correctness; interactive sluggishness beyond that is a perf follow-up.

---

## 5. Audit + commit pipeline

### 5a. Test battery (runbook §"Step 4")

```sh
cd /Users/ashen/Desktop/poker_solver
pytest tests/test_ui_smoke.py -xvs    # expect ~10 tests (8 retained + 2 new)
pytest -x                              # full suite; gates the on_progress kwarg
                                       # addition against PR 5/6/7 existing tests
poker-solver ui                        # manual smoke; load default_tiny_subgame
                                       # and confirm real DCFR converges
```

### 5b. Audit + check battery in parallel (runbook §"Step 5")

```sh
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_output.log 2>&1
```

The audit prompt for PR 10b is lighter than 10a's — focus areas are: (1) UI structure regression vs. PR 10a markers + smoke tests; (2) `on_progress` callback fires on the worker thread and does not call NiceGUI directly; (3) `ui/mock_solver*.py` files deleted (grep returns nothing); (4) the kwarg addition does not break PR 5/6/7 existing tests (existing callers pass nothing → default `None` → original behavior).

PR 10b-specific must-fix triggers:
- Any PR 10a Q1–Q6 lock changed (Q7 banner → chip is the **only** allowed UX delta).
- Any retained PR 10a smoke test failing after the swap.
- `on_progress` invoked from the main thread instead of the worker.
- `ui/mock_solver.py` still present in the tree.
- Existing PR 5/6/7 tests broken by the `on_progress` kwarg addition.

### 5c. Commit, push, merge (runbook §"Steps 6–8")

```sh
cd /Users/ashen/Desktop/poker_solver
git status
git add poker_solver/hunl_solver.py ui/state.py ui/app.py tests/test_ui_smoke.py README.md
git rm ui/mock_solver.py
# git rm ui/mock_solver_fixtures.py    # if it exists
git commit -m "$(cat <<'EOF'
PR 10b: swap mock solver for real solvers

Deletes ui/mock_solver.py (and ui/mock_solver_fixtures.py if split) and
points ui/state.py's _solve_postflop_impl at a thin dispatch wrapper
that routes preflop configs through solve_hunl_preflop (PR 9) and
postflop configs through solve_hunl_postflop (PR 5).

Adds the on_progress kwarg to solve_hunl_postflop (the one engine-side
change in PR 10b). PR 9's solve_hunl_preflop already exposes the same
kwarg per its §4 amendment.

UI structure unchanged from PR 10a (Q1-Q6 locks all preserved
identically; Q7 yellow banner downgrades to a subtle (mock) chip in
the header, which disappears after the first successful real solve).

Test result: ~10 smoke tests pass (8 retained + 2 new; 5 mock-specific
tests deleted per pr10b_spec.md §5). Full suite green (on_progress
kwarg defaults to None; existing callers unaffected).
EOF
)"

git push -u origin pr-10b-ui-real-solver
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-10b-ui-real-solver -m "Integration: merge PR 10b (ui-real-solver)"
git push origin integration
```

### 5d. Update PLAN.md trajectory

PLAN.md §2: PR 10b row → `landed on integration` + branch name. `docs/autonomous_log.md`: progress entry with timestamp, commit hash, test count, audit-finding-count. Plan-sync rule applies if `~/.claude/plans/poker_solver.md` was edited.

---

## 6. Risks (PR 10b-specific, not present in PR 10a)

Original spec §8 lists four risks. The two that are **uniquely critical to PR 10b** (uncovered by PR 10a's mock):

1. **UI structure regression vs. PR 10a (the dominant risk).** PR 10b's job is to swap the solver, **not** to redesign the UI. Q1–Q6 stay literally identical; only Q7 changes (banner → chip). The forbidden-files list in §3 above (every `ui/views/*.py`, every marker contract registered in PR 10a, `poker_solver/range.py`) is the gate. The 8 retained PR 10a smoke tests are the regression alarm — if any fails after the swap, that's a must-fix before merge. The library viewer stub stays a stub until PR 11; growing it in PR 10b would be scope creep.

2. **`on_progress` kwarg signature mismatch between PR 9's preflop solver and PR 10b's postflop addition.** The dispatch wrapper assumes identical kwarg shape: `on_progress: Callable[[int, float, MemoryReport], None] | None = None`. PR 9's §4 amendment (derived from `pr10b_spec.md` §3) mandates this; pre-flight 1d enforces it. If PR 9 landed with a divergent shape (e.g., `Callable[[int, float, float], None]` with memory as a float instead of a `MemoryReport`), the dispatch wrapper grows runtime-shaping logic and the callback contract loses type safety. Fix at the PR 9 source (a tiny integration-branch follow-up) before landing PR 10b — do not paper over with adapter logic in the UI.

Auxiliary risks worth tracking but lower-severity:

- **Real DCFR wall-clock surprise** (spec §8 risk #2): the mock returned in seconds; real flop solves can be minutes. UI was designed for this; README "Quick tour" recommends `default_tiny_subgame` for first-time use.
- **`MemoryReport` range divergence** (spec §8 risk #3): responsive formatting in the memory panel should hold up; cosmetic should-fix if not.
- **Tree-browser performance with real trees** (spec §8 risk #4): the lazy + 2000-cap design from PR 10a should handle it; smoke 8 from PR 10a is the retained gate.

---

## 7. Quick-reference: paths this kickoff touches

- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md` — canonical spec (read end-to-end before launch).
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md` §0.1 — Q1–Q7 locks the swap must not regress.
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md` — sibling kickoff (structure / pattern reference).
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md` — preflop solver §4 amendment requiring `on_progress`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` — `solve_hunl_postflop`; PR 10b adds the `on_progress` kwarg here.
- `/Users/ashen/Desktop/poker_solver/poker_solver/preflop_solver.py` — `solve_hunl_preflop` (lands in PR 9); already exposes `on_progress`.
- `/Users/ashen/Desktop/poker_solver/ui/state.py` — dispatch wrapper replaces the mock import.
- `/Users/ashen/Desktop/poker_solver/ui/mock_solver.py` — DELETED by this PR.
- `/Users/ashen/Desktop/poker_solver/ui/mock_solver_fixtures.py` — DELETED by this PR (if it exists).
- `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py` — 5 tests deleted, 2 added.
- `/Users/ashen/Desktop/poker_solver/README.md` — `## UI (mock)` → `## UI`.
- `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md` — universal runbook.
- `/Users/ashen/Desktop/poker_solver/PLAN.md` — trajectory table updated post-merge.
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — progress entry post-merge.
- `/Users/ashen/Desktop/poker_solver/scripts/check_pr.sh` — check battery.
- `/tmp/integration_pre_pr_10b.hash` — reflog backup hash (pre-flight 1e).
