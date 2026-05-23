# PR 10a wave aggregation checklist

**Date staged:** 2026-05-22
**Author:** orchestrator wave-aggregation prep agent
**Purpose:** stepwise runbook the orchestrator follows the moment all three
Agents A/B/C complete on `pr-10a-ui-mock-first` (branched off integration tip
`9f09d49` + PR 4.5). Read-only doc — does not run agents, does not modify
source. Sequenced after `orchestrator_ready_to_fire.md` §2 fan-out and
before `pre_commit_checklist_10a.md` G1-G32 gates.

---

## 0. Agent completion checker (poll order, not parallel)

When the harness reports any agent finished, do NOT immediately aggregate —
wait until all three return. Acceptable end-states per agent:

- **Agent A "done":** returned message includes paths to `ui/__init__.py`, `ui/app.py`, `ui/state.py`, `ui/views/__init__.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/views/onboarding.py`. Plus a summary covering Q1+Q3+Q4+Q7 lock compliance + threading model choice (`threading.Thread`).
- **Agent B "done":** returned message includes paths to `ui/views/range_matrix.py` + `ui/views/tree_browser.py`. Plus Q2 (hand-class labels) + Q5 (inspector below) + Q6 (reach 0.01) compliance + the 1326-combo coordinate-mapping note.
- **Agent C "done":** returned message includes paths to `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (optional split), `ui/views/library_browser.py`, `tests/test_ui_smoke.py`, edits to `poker_solver/cli.py` + `pyproject.toml` + `README.md`. Plus the 12-fixture list + 20-test count + interface-contract signature.

If any agent returns with a "blocked" or "ownership conflict" status, stop;
escalate to user before applying any patches. Do NOT proceed agent-by-agent.

---

## 1. File ownership verification (grep before aggregation)

Run from `/Users/ashen/Desktop/poker_solver` on `pr-10a-ui-mock-first`:

```sh
git diff integration..pr-10a-ui-mock-first --stat
```

Then verify each agent touched only their lane (any cross-agent edit is a
must-fix — file-ownership lock per `orchestrator_ready_to_fire.md` §2 table):

- **Agent A authorship:** `git log --author=... ui/state.py ui/views/run_panel.py ui/views/onboarding.py ui/app.py ui/__init__.py ui/views/__init__.py ui/views/spot_input.py` (or `git blame` if single-author session). Must NOT show edits to `ui/views/range_matrix.py`, `ui/views/tree_browser.py`, `ui/mock_solver.py`, `tests/test_ui_smoke.py`, any `poker_solver/*.py`.
- **Agent B authorship:** `ui/views/range_matrix.py`, `ui/views/tree_browser.py` only. Must NOT show edits to any other UI file, any test, any `poker_solver/*.py`.
- **Agent C authorship:** `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` (if split), `ui/views/library_browser.py`, `tests/test_ui_smoke.py`. Plus surgical edits to `poker_solver/cli.py` (new `ui` subcommand), `pyproject.toml` (`[ui]` extra + `ui_smoke` marker), `README.md` (UI section).

Hard guard: `git diff integration -- poker_solver/range.py` must be EMPTY
(engine-pollution lock per G18). If non-empty → must-fix before aggregation.

---

## 2. Audit verdict expectations

Per `audit_preprep_10a.md` §3 forecast:

- **READY (clean, no patches): ~25%** — all 7 Q-locks held, threading correct, mock contract intact, no MDF violations. Skip to §4.
- **READY-WITH-PATCHES: ~55%** — most likely outcome. 1-2 must-fix + 2-4 should-fix. Apply patches in-place; re-run pre-commit gates; commit.
- **NOT-READY: ~20%** — only if threading model botched (Agent A used `asyncio.to_thread` AND worker calls `ui.*` directly) OR mock shape drifted (returns `dict` not `HUNLSolveResult`). Abort commit; escalate to user with audit must-fix list.

Audit-input bundle: `audit_prompt_final_10a.md` (15-area brief),
`audit_preprep_10a.md` (forecast), all three agent prompts, the staged diff.

---

## 3. Common must-fix patches likely

Ranked by audit-forecast probability per `audit_preprep_10a.md` §1 +
`engineering_aggregate.md` §2:

### 3.1 Threading model bugs (worker → UI) — HIGHEST
- `grep -r "ui\." /Users/ashen/Desktop/poker_solver/ui/mock_solver.py` returns any hit → patch: replace with writes to `state.runner` dataclass.
- `grep "asyncio.to_thread" /Users/ashen/Desktop/poker_solver/ui/` returns hits → patch: convert to `threading.Thread`.
- Missing `ui.timer(0.5, update_ui)` poller in `ui/app.py` → patch: add timer.
- Stop-button latency >1 mock-iter → patch: add `_stop_event.is_set()` check at every iter boundary in `mock_solve()`.

### 3.2 Mock fidelity (MDF violations on river fixtures) — HIGH
- For bet-size B, bluff_freq must satisfy `bluff_freq <= B/(1+B) * value_combos`. Pot-sized (B=1.0) → 50% cap.
- Check `river_axxs_polar`, `river_blocker_heavy`, `river_tiny_subgame`. Patch: clamp bluff freq post-hoc, re-balance value freq, re-check polarization.

### 3.3 state.json atomicity gaps — MEDIUM
- Direct `open(path, 'w').write(json.dumps(...))` without tmp+fsync+rename → patch: rewrite `ui/state.py::save_state()` with atomic-rename trio.
- Missing corrupt-load fallback → patch: try/except in `load_state()` with `.bak` backup.
- Missing 0.5s debounce → patch: wrap save in `ui.timer(0.5, ...)`.

### 3.4 Q3/Q4/Q6 lock drift — LOW
- Q3 default iters drifted to 2000 → patch `ui/views/run_panel.py` to 1000.
- Q4 bet sizes missing one of (33/75/100/all-in) → patch checkbox defaults.
- Q6 reach filter at 0.0 instead of 0.01 → patch `ui/views/tree_browser.py`.
- Q7 banner non-dismissible or missing yellow color → patch `ui/app.py` header.

### 3.5 Mock interface contract drift — HIGH (silent breakage of PR 10b)
- `mock_solve` signature first 8 params not byte-identical to `solve_hunl_postflop` post-PR-9 → patch signature.
- Return type not `HUNLSolveResult` → patch return + `MemoryReport` population.
- Field-name drift (`strategy` vs `final_strategy`) → patch field names.

### 3.6 Matrix off-by-one — TERTIARY
- `_combo_to_cell` row/col swap on offsuit combos → entire matrix mirrored silently → patch coordinate mapping; re-run `test_combo_to_cell_mapping_no_off_by_one` (test #7 of 20).

---

## 4. Commit pipeline sequencing

Sequential. Each step gates the next.

1. **Lint pass.** `ruff check ui tests/test_ui_smoke.py poker_solver/cli.py && black --check ui tests/test_ui_smoke.py poker_solver/cli.py && mypy --strict ui/ tests/test_ui_smoke.py poker_solver/cli.py`. Fix in-place if format-only. Logical-lint fails → escalate.
2. **Apply audit must-fix patches.** In-place edits to the agent's owned files (DO NOT cross ownership lines post-hoc). Re-stage with `git add` on explicit paths only (no `git add -A`).
3. **Re-run pre-commit gates G1-G32** from `pre_commit_checklist_10a.md`. All must green. G16 + G12 + G18 are the load-bearing trio.
4. **Version bump.** Edit `poker_solver/__init__.py` (`__version__ = "0.7.1"`), `pyproject.toml` `[project] version`, `CHANGELOG.md` (new `[0.7.1] - 2026-05-22` section above `[0.7.0]`), `README.md` ("Current version: 0.7.1"). Per `commit_message_draft_10a.md` lines 28-37.
5. **Final staging review.** `git status` + `git diff --cached --stat` → ~14-16 files per G32 expected scope.
6. **Commit.** `git commit -F /Users/ashen/Desktop/poker_solver/docs/pr10_prep/commit_message_draft_10a.md` (or HEREDOC per memory's git-safety protocol). NEW commit only — never `--amend`.
7. **Push.** `git push -u origin pr-10a-ui-mock-first` after user OK.
8. **Merge.** Do NOT auto-merge into `integration` — per `orchestrator_ready_to_fire.md` "Non-commits", wait for PR 10b's mock→real swap to land as coordinated pair. PR 10a sits on its branch.

---

## 5. Branch + reflog

- **Branch:** `pr-10a-ui-mock-first` (created from integration tip `9f09d49` + PR 4.5 merge).
- **Reflog backup:** `/tmp/integration_pre_pr_10a.hash` (captured pre-branch by `orchestrator_ready_to_fire.md` §1e).
- **Worktree safety:** all three agents wrote in the SAME working tree. Per the no-concurrent-branch-ops rule, do NOT branch-switch the shared tree during or immediately after aggregation. Audit + patches run on `pr-10a-ui-mock-first` HEAD.

---

## 6. Biggest risk surface (one-line summary)

**Threading model + mock interface contract drift.** If Agent A used
`asyncio.to_thread` instead of `threading.Thread`, OR if any of the three
agents called `ui.*` from worker context, the UI deadlocks under load —
NOT-READY trigger. If Agent C's `mock_solve` signature or return shape
drifted from `HUNLSolveResult`, PR 10b's one-line import swap breaks
silently — must-fix on PR 10a before commit. Both surfaces are caught by
audit focus areas 1+2 and 9 respectively per `audit_prompt_final_10a.md`.

---

## Anchors

- Pre-commit gates: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pre_commit_checklist_10a.md`
- Audit forecast: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_preprep_10a.md`
- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt_final_10a.md`
- Engineering aggregate: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/engineering_aggregate.md`
- Commit draft: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/commit_message_draft_10a.md`
- Fan-out invocations: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/orchestrator_ready_to_fire.md`
