# PR 10a.5 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Ready to fire in parallel with PR 11 (`pr-11-library-and-packaging`, in flight in the shared tree). No interlock with PR 11 except a clean rename of `ui/views/library_browser.py` (PR 11 owns; PR 10a.5 does not touch).

**Purpose:** mechanical operations sheet for PR 10a.5, the **UI smoke-test conformance pass**. Resolves the 5 hard failures (Agent B marker drift) + 7 xfailed tests (missing markers / constants) catalogued in `docs/pr10_prep/pr10a5_conformance_backlog.md`. Target version: **v0.6.1 PATCH**. Single-agent execution — total scope ~150-250 LOC.

Authoritative scope freeze: `docs/pr10_prep/pr10a5_conformance_backlog.md` §4 ("Recommended PR 10a.5 scope") and §6 ("Out of scope").

---

## 1. Pre-launch verification (run BEFORE branch creation)

All five checks must pass. If any fails, stop and resolve before continuing. **Do NOT switch branches in the shared working tree while PR 11 is still writing** — use a git worktree (per `no_concurrent_branch_ops` memory rule).

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip is PR 10a merge commit (b880032).
git fetch origin
git log --oneline integration -3
# Expected topmost commit: "Integration: merge PR 10a (UI mock-first scaffold + xfail followup, v0.6.0)"
# Topmost SHA expected: b880032
git rev-parse integration   # expect: b880032xxxxxxx (PR 10a follow-up)
git rev-parse integration == git rev-parse origin/integration   # must match

# 1b. PR 10a.5 branch does NOT yet exist anywhere.
git branch --list pr-10a5-ui-conformance
# Expected: empty. If non-empty, rename prior branch
#   (`git branch -m pr-10a5-ui-conformance-prior`) before proceeding.

# 1c. PR 11 branch IS active in the shared tree (file-overlap is zero, but
#     we confirm it's the live writer to avoid surprises).
git worktree list
# Expected lines (or similar):
#   /Users/ashen/Desktop/poker_solver  b880032 [pr-11-library-and-packaging]
#   /private/tmp/poker_pr35            1cbf52a [pr-3.5-pushfold]

# 1d. Conformance backlog file present (scope-freeze artifact).
test -f docs/pr10_prep/pr10a5_conformance_backlog.md && \
    wc -l docs/pr10_prep/pr10a5_conformance_backlog.md
# Expected: ~180 lines.

# 1e. xfail decorator anchors present at the 7 documented lines.
grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py
# Expected lines: 452, 498, 531, 580, 620, 659, 683 (exactly seven matches).

# 1f. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_10a5.hash
echo "integration tip pre-PR-10a.5: $(cat /tmp/integration_pre_pr_10a5.hash)"
```

Optional final sanity: from a *clean* checkout of `integration` (in a separate worktree), `pytest tests/test_ui_smoke.py -v` should show **8 passing, 5 failing, 7 xfail** — the green-board baseline PR 10a.5 must bring to 20 / 20.

---

## 2. Branch creation (via git worktree — NOT in-tree switch)

PR 11 is the current shared-tree writer (`/Users/ashen/Desktop/poker_solver` on `pr-11-library-and-packaging`). PR 10a.5 launches from a sibling worktree at `/private/tmp/poker_pr10a5`. This honors `no_concurrent_branch_ops`.

```sh
# Create the worktree off integration. Single command — does NOT alter the
# shared tree's checkout.
git -C /Users/ashen/Desktop/poker_solver worktree add \
    -b pr-10a5-ui-conformance \
    /private/tmp/poker_pr10a5 \
    integration

# Verify.
cd /private/tmp/poker_pr10a5
git status                  # expect: clean tree on pr-10a5-ui-conformance
git log --oneline -1        # expect: b880032 PR 10a merge commit
git worktree list           # expect: 3 worktrees (shared, pr35, pr10a5)
```

If the user prefers in-tree execution and confirms PR 11 is paused or merged, swap to a standard `git checkout -b pr-10a5-ui-conformance integration` in the shared tree — but **only** with explicit user approval.

---

## 3. Single-agent invocation (one tool-call wave)

PR 10a.5 is a small-scope conformance pass. Single-agent execution is the right shape — fan-out adds coordination cost with no parallelism benefit at ~150-250 LOC. Files are scoped to four UI views + one state module + one app wire.

```
Agent — "PR 10a.5 UI conformance pass — fix Agent B marker drift + add 7 missing markers/constants"
  prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_10a5_prompt.md between the two `---` markers>
  subagent_type: general-purpose
  cwd: /private/tmp/poker_pr10a5
  run_in_background: true
```

**Note:** `docs/pr10_prep/agent_10a5_prompt.md` is NOT yet written. The orchestrator must author it before firing — pull the §4 recommended scope (six numbered steps) and the F1-F5 + X1-X7 row tables from `pr10a5_conformance_backlog.md`. Estimated prompt length: ~250-400 lines. Block on prompt existence: `test -f docs/pr10_prep/agent_10a5_prompt.md || stop`.

**Agent owns (single agent, no contention):**

| Edit type | Files | LOC |
|---|---|---|
| Marker enumeration fix | `ui/views/range_matrix.py` (lines 735, 844; +F4 preset cross-check in `spot_input.py`) | ~30 LOC |
| New adapter / constants | `ui/views/range_matrix.py` (`cell_rgb_for_action_freqs`, `DISPLAY_PALETTE`); `ui/views/spot_input.py` (`INPUT_PALETTE`) | ~50 LOC |
| Blocker overlay class | `ui/views/range_matrix.py` (`_cell_tag`) | ~10 LOC |
| Log-scale toggle marker | `ui/views/run_panel.py:221-224` | ~3 LOC |
| OOM remediation button | `ui/views/run_panel.py:506` (`_show_error`) | ~20 LOC |
| Push/fold dispatch button | `ui/app.py:294-302` and/or `ui/views/spot_input.py:373-380` | ~15 LOC |
| Progress-ETA marker + state method | `ui/views/run_panel.py:469`; `ui/state.py` (`SolveRunner.compute_eta`) | ~30 LOC |
| xfail decorator removal | `tests/test_ui_smoke.py` lines 452, 498, 531, 580, 620, 659, 683 | -7 lines |

**Forbidden (PR 11 owns):**

| File | Owner | Reason |
|---|---|---|
| `ui/views/library_browser.py` | PR 11 | rewritten under PR 11 library mode |
| `crates/` | PR 11 | PyInstaller bundling |
| `pyproject.toml` (packaging metadata) | PR 11 | DMG bundling additions |
| `poker_solver/library/` (new package) | PR 11 | new module tree |
| `tests/test_library_*.py` | PR 11 | new test set |

**Out of scope for PR 10a.5** (per backlog §6): no Q-lock revisits; no fixture changes (12 named spots stay frozen); no mock-solver signature edits; no new smoke tests (20-test count is locked); no engine-side changes (zero `poker_solver/` diff); no version bump beyond v0.6.1 PATCH.

---

## 4. Expected wall-clock: ~4-6 hours

Single-agent, narrow scope. Per `pr10a5_conformance_backlog.md` §4 estimate:

- Agent runtime: ~3-4 hours (marker fix + 4 UX wire-ups + 2 module-level constants + state method).
- Audit + check battery: ~30-60 min.
- Reconciliation (full smoke-test green-board verification 20/20): ~15-30 min.
- Commit + merge: ~10 min.

**Total: ~4-6 hours wall-clock** end-to-end (worktree creation → integration merge). If runtime exceeds 8 hours, treat as scope creep — invoke a scope-review gate.

**Deliverables (PR surface):** ~150-250 LOC net change across `ui/views/range_matrix.py` (~80 LOC), `ui/views/spot_input.py` (~30 LOC), `ui/views/run_panel.py` (~50 LOC), `ui/state.py` (~30 LOC), `ui/app.py` (~15 LOC). Test file: -7 lines (xfail decorator removal only). Zero engine-side, zero `pyproject.toml`, zero new files.

---

## 5. Risk reminders

| Risk | Mitigation |
|---|---|
| **Touch `ui/views/library_browser.py`** (PR 11 territory) | Hard-forbidden in agent prompt + verified in §3 "Forbidden" table; pre-commit `git diff --stat` review will catch. |
| **Re-introduce mock-solver signature drift** | Mock signature locked at v0.6.0 per `release_notes_v0.6.0.md` §1 caveat #2 — agent is forbidden from editing `poker_solver/mock_solver.py` or fixture surfaces. |
| **Accidental fixture-ID rename** | The 12 named spots are frozen — agent must verify preset marker IDs in `spot_input.py` match `ui/mock_solver_fixtures.py` exactly (F4 hypothesis cross-check), not invent new ones. |
| **In-tree branch switch while PR 11 writes** | §2 uses `git worktree`, NOT `git checkout`. The shared tree stays on `pr-11-library-and-packaging`. |
| **Pio-anchor palette regression** | Agent must use **pure** `(255, 0, 0)` / `(255, 255, 0)` / `(0, 255, 0)` anchors for `cell_rgb_for_action_freqs`, NOT the existing `(220, 40, 40)` fade values. Leave `cell_color()` untouched for CSS-string consumers. |
| **xfail decorator removal before wire-up lands** | Removal is the LAST step (per backlog §4 step 5). Agent prompt sequences: implementation → smoke-test confirmation 20/20 → xfail removal in same commit. |
| **PR 11 merges first, integration-tip drift** | After PR 11 merges, rebase PR 10a.5 onto new tip: `git -C /private/tmp/poker_pr10a5 fetch origin && git -C /private/tmp/poker_pr10a5 rebase origin/integration`. Conflict surface is zero (no file overlap). |
| **Pyproject-level pin drift** | Out of scope — agent must NOT edit `pyproject.toml`. Any pin-bump need indicates a scope leak; halt for scope review. |

---

## 6. Post-completion: audit + commit pipeline

Per `pr10_prep/launch_invocations_10a.md` §5 pattern. After the agent returns:

```sh
cd /private/tmp/poker_pr10a5

# 6a. Interface drift reconciliation — verify all 20 smoke tests green.
pip install -e ".[ui]"          # rebuild if any ui/ surfaces changed
pytest tests/test_ui_smoke.py -v
# Expected: 20 passed, 0 failed, 0 xfail. Acceptance gate: green-board count
# rises from 8 / 20 (pre-PR 10a.5 baseline) to 20 / 20.

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_10a5_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 10a.5 audit — fresh reviewer, no implementation context"
#     prompt: <body of /Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt_10a5.md
#              between the `---` markers (TO BE AUTHORED)>
#     subagent_type: general-purpose; run_in_background: true; cwd: /private/tmp/poker_pr10a5
# Audit writes to docs/pr10_prep/audit_report_10a5.md.

# 6c. Commit (explicit paths only — NO `git add -A`).
git -C /private/tmp/poker_pr10a5 status     # verify staged set; no .env, no build artifacts
git -C /private/tmp/poker_pr10a5 add \
    ui/views/range_matrix.py \
    ui/views/spot_input.py \
    ui/views/run_panel.py \
    ui/state.py \
    ui/app.py \
    tests/test_ui_smoke.py \
    docs/pr10_prep/audit_report_10a5.md
git -C /private/tmp/poker_pr10a5 status     # re-verify
git -C /private/tmp/poker_pr10a5 commit -m "PR 10a.5: UI smoke-test conformance pass (v0.6.1)"
# Full commit message body to be drafted in docs/pr10_prep/commit_message_draft_10a5.md.

# 6d. Push + --no-ff merge into integration. CRITICAL: do this from the
#     worktree directory, NOT from the shared tree (PR 11 may still be live).
git -C /private/tmp/poker_pr10a5 push -u origin pr-10a5-ui-conformance
git -C /private/tmp/poker_pr10a5 fetch origin
# Switch integration in a fresh worktree (NOT the shared tree); merge there.
git -C /Users/ashen/Desktop/poker_solver worktree add /private/tmp/poker_integration integration
git -C /private/tmp/poker_integration pull --ff-only origin integration
git -C /private/tmp/poker_integration merge --no-ff pr-10a5-ui-conformance \
    -m "Integration: merge PR 10a.5 (UI conformance pass, v0.6.1)"
git -C /private/tmp/poker_integration push origin integration
# Cleanup integration worktree after push:
git -C /Users/ashen/Desktop/poker_solver worktree remove /private/tmp/poker_integration

# 6e. Tag v0.6.1.
git -C /private/tmp/poker_pr10a5 tag -a v0.6.1 -m "v0.6.1 — UI smoke-test conformance pass"
git -C /private/tmp/poker_pr10a5 push origin v0.6.1

# 6f. Cleanup PR 10a.5 worktree once merged.
git -C /Users/ashen/Desktop/poker_solver worktree remove /private/tmp/poker_pr10a5

# 6g. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
#     Update docs/release_notes_v0.6.0.md §"Honest caveats" item #5 to mark
#     "deferred 12 smoke tests" as resolved in v0.6.1.
```

**Audit gate semantics:** `must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Given PR 10a.5 IS itself a follow-up for PR 10a should-fixes, any should-fix the audit raises against PR 10a.5 must either be in-scope (fix now) or explicitly logged as v0.6.2 backlog — no double-deferral.

---

## 7. Quick-reference paths

- Backlog (scope freeze): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a5_conformance_backlog.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_invocations_10a5.md`
- PR 10a audit report (anchor for must-/should-fix): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a.md`
- PR 10a release notes (caveat #5 anchor): `/Users/ashen/Desktop/poker_solver/docs/release_notes_v0.6.0.md`
- Smoke-test file (xfail decorator removal targets): `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py:452,498,531,580,620,659,683`
- Agent prompt (TO BE AUTHORED): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_10a5_prompt.md`
- Audit prompt (TO BE AUTHORED): `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt_10a5.md`
- Worktree (created at launch): `/private/tmp/poker_pr10a5`
- Reflog backup: `/tmp/integration_pre_pr_10a5.hash`

**Blocking dependency before fire:** `agent_10a5_prompt.md` and `audit_prompt_10a5.md` are not yet written. Orchestrator must author both before this invocation sheet can be paste-executed.
