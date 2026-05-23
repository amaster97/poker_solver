# PR 4.5 launch invocations — copy-paste ready

**Status:** PRE-STAGED. Do NOT execute until PR 7 has merged to `integration` and the user has approved firing PR 4.5 (per `launch_decision.md` §5: defer until PR 7 commits to `integration`).

**Purpose:** the exact, copy-paste-ready set of operations to fire PR 4.5 the moment PR 7 lands. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md`. Authoritative fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/fanout_ready.md`. This file is the mechanical operations sheet — paste blocks in order.

---

## 1. Pre-launch verification (run AFTER PR 7 lands, BEFORE branch creation)

All six checks must pass. If any fails, stop and resolve before continuing.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip past PR 7 merge commit (and PR 5 + PR 6 still upstream).
git fetch origin
git log --oneline integration -10
# Expected topmost commit: "Integration: merge PR 7 (noambrown-diff)".
# Expected near top: PR 5 + PR 6 merge commits also visible.
git rev-parse integration; git rev-parse origin/integration   # must be equal
# If divergent: git pull --ff-only origin integration

# 1b. Branch pr-4.5-audit-debt-sweep does NOT yet exist.
git branch --list pr-4.5-audit-debt-sweep
# Expected: empty. If branch exists from a prior aborted launch, rename:
#   git branch -m pr-4.5-audit-debt-sweep pr-4.5-audit-debt-sweep-prior

# 1c. Working tree clean.
git status
# Expected: "nothing to commit, working tree clean".

# 1d. All four source audit reports + cleanup plan + backlog present.
ls -la docs/cross_pr_cleanup_plan.md docs/audit_followup_backlog.md
ls -la docs/pr3_prep/audit_report.md docs/pr3_5_prep/audit_report.md
ls -la docs/pr4_prep/audit_report.md docs/pr5_prep/audit_report.md

# 1e. All 7 target source files exist (no PR 6 / PR 7 rename drift).
ls -la poker_solver/hunl.py poker_solver/action_abstraction.py poker_solver/pushfold.py \
       poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py \
       poker_solver/abstraction/precompute.py poker_solver/profiler/memory.py

# 1f. Reflog backup hash (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_4_5.hash
echo "integration tip pre-PR-4.5: $(cat /tmp/integration_pre_pr_4_5.hash)"
```

Optional final sanity: `pytest -x -q` from the `integration` tip — must be green; the count becomes the post-PR-4.5 regression bar.

---

## 2. Branch creation

Branch name `pr-4.5-audit-debt-sweep` is fixed per `launch_kickoff.md` §7 and audit-prompt cross-referenced — do NOT improvise.

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-4.5-audit-debt-sweep
git status   # expect: clean tree on pr-4.5-audit-debt-sweep
git log --oneline -1   # expect: PR 7 merge commit
```

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

All three implementation agents launch in the SAME tool-call block. They are independent — file-ownership boundaries are locked inside each prompt. PR 4.5 has no separate `agent_{a,b,c}_prompt.md` files; the kickoff doc IS the spec. Each agent's prompt body is: (a) the items list from `launch_kickoff.md` §2 for that PR slice, (b) ownership row from `launch_kickoff.md` §5a, (c) the standing "mechanical fixes only; no behavior changes; no new tests; no docstring expansions" clause, (d) cite kickoff doc as canonical scope source.

```
Agent A — "PR 4.5 Agent A — PR 3/3.5 mechanical audit-debt fixes (8 items)"
  scope: Items 3-A, 3-B, 3-C, 3-D, 3-E, 3.5-A, 3.5-B, 3.5-C
  files: poker_solver/hunl.py (lines 14, 107, 109 + license header),
         poker_solver/action_abstraction.py,
         poker_solver/pushfold.py
  prompt body: <launch_kickoff.md §2 PR 3 + PR 3.5 sections> +
               <launch_kickoff.md §5a Agent A row> + standing clause
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 4.5 Agent B — PR 4 mechanical audit-debt fixes (4 items)"
  scope: Items 4-A, 4-B, 4-C, 4-D
  files: poker_solver/abstraction/equity_features.py,
         poker_solver/abstraction/emd_clustering.py,
         poker_solver/abstraction/precompute.py,
         poker_solver/hunl.py:336 ONLY (4-B predicate; line range disjoint from Agent A)
  prompt body: <launch_kickoff.md §2 PR 4 section> +
               <launch_kickoff.md §5a Agent B row> + standing clause
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 4.5 Agent C — PR 5 mechanical audit-debt fixes (1 item)"
  scope: Item 5-A
  files: poker_solver/profiler/memory.py
  prompt body: <launch_kickoff.md §2 PR 5 section> +
               <launch_kickoff.md §5a Agent C row> + standing clause
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax) — `fanout_ready.md` §3:**

| Agent | Owns | Read-only on | Forbidden |
|---|---|---|---|
| A | `hunl.py` (lines 14, 107, 109 + license header), `action_abstraction.py`, `pushfold.py` | `docs/pr{3,3_5}_prep/audit_report.md` | `hunl.py:336` (Agent B's), Agent B/C files, any new tests |
| B | `abstraction/equity_features.py`, `abstraction/emd_clustering.py`, `abstraction/precompute.py`, `hunl.py:336` only | `docs/pr4_prep/audit_report.md` | Agent A's lines in `hunl.py`, Agent C files, any new tests |
| C | `profiler/memory.py` | `docs/pr5_prep/audit_report.md` | any non-`profiler/` edits, any new tests |

**Shared-file caveat (4-B):** `hunl.py:336` is Agent B's edit even though `hunl.py` is otherwise Agent A's file. Line ranges do NOT overlap (A: 14, 107, 109 + header; B: 336). Git auto-merges trivially.

**Parallel fan-out during agent runtime** (per parallel-agents-default + min-five-agents memory rules): while A/B/C run, fan out independent agents on downstream work — PR 8 baseline-bench polish, `docs/autonomous_log.md` continuous pruning, doc inventory sweep. Aggregate per wave; do NOT react agent-by-agent.

---

## 4. Expected wall-clock: ~90 min

Small PR — purely mechanical fixes. Per `launch_kickoff.md` §5b + `fanout_ready.md` §4 estimate:
- Agent A: ~30 min (8 items across 3 files; mostly subtractions + one-line additions).
- Agent B: ~30 min (4 items across 3 files + 1 line in `hunl.py`).
- Agent C: ~15 min (1 item: drop unused import + suppression).
- Concurrent execution: ~30-45 min wall-clock for fan-out itself.
- Audit + check battery + reconciliation: ~30 min.
- Commit + merge: ~10 min.

**Total: ~90 min wall-clock** end-to-end (branch creation → integration merge). Net throughput vs sequential is ~2.5x.

**Deliverables (PR surface, 7 source files):** ~30-50 LoC net delta, mostly subtractions + one-line additions. Reviewable in <15 min not counting audit cross-refs. No new tests; possibly one test-side update (`pytest.raises(AssertionError)` → `pytest.raises(ValueError)` on rake-config test per kickoff §8a, part of 3-C mechanical fix).

---

## 5. Risk reminders (mechanical only; no behavior changes)

All 13 items are mechanical / low-risk by design. Standing constraints (per kickoff §2 + §3):

- **NO behavior change.** Every fix preserves observable behavior: error-type narrowing (`ValueError` subclasses), license header text, predicate tightening on unreachable branches, dead-code removal, magic-number sentinels, import drops.
- **NO new tests.** Test coverage additions are explicitly deferred per kickoff §3.
- **NO docstring expansions** beyond the one-line license-posture items.
- **NO spec amendments.** Any spec-touching items (HUNLState.config source-of-truth; d=2 universal-jam landmark; strategic-equivalence collapse) stay deferred.
- **NO scope expansion.** If an agent reports "while reviewing PR N audit, I also fixed X" — REVERT X. Defer list in kickoff §3 is authoritative.
- **Unreachable-assert tripwires (3-E, 4-C):** if `assert False` fires in CI, the branch was reachable — latent bug surfaced. STOP, revert the assertion, file follow-up must-fix per kickoff §8c. Do NOT downgrade to `pass`.
- **Pre-grep before import drops (3-D, 5-A):** confirm `field(` (3-D) and `np\.` (5-A) are not referenced elsewhere before removing. Per kickoff §8e.
- **`PushFoldChartUnavailable(ValueError)` (3.5-A):** grep `except PushFoldChartUnavailable` consumers BEFORE landing. Per kickoff §9b must-fix trigger.
- **License header text consistency (3-A, 3-B, 4-A):** aggregator normalizes wording across the 3 modules (kickoff §8d).
- **LOC budget:** net delta must stay <50 LoC (kickoff §12, audit_preprep §1.8). Exceeding signals scope creep.

---

## 6. Audit + commit pipeline

Per `launch_kickoff.md` §9a-9e. After all three agents return:

```sh
cd /Users/ashen/Desktop/poker_solver

# 6a. Interface drift reconciliation.
pytest -x              # full suite green
mypy --strict poker_solver/
ruff check
# Test-count must equal pre-PR-4.5 baseline. Only allowed test-side change:
# the 3-C rake-config test exception-type swap (AssertionError -> ValueError).

# 6b. Check battery + audit agent in parallel.
sh /Users/ashen/Desktop/poker_solver/scripts/check_pr.sh > /tmp/check_pr_4_5_output.log 2>&1
# Concurrently launch audit agent:
#   Audit — "PR 4.5 audit — fresh reviewer; verify 13-item scope + no behavior change"
#     prompt: "Audit branch pr-4.5-audit-debt-sweep against the 13 items in
#              docs/pr4_5_audit_debt/launch_kickoff.md §2; flag any behavior change
#              or scope creep; cross-reference findings against
#              docs/pr4_5_audit_debt/audit_preprep.md §1; write report to
#              docs/pr4_5_audit_debt/audit_report.md."
#     subagent_type: general-purpose; run_in_background: true
# Audit writes to docs/pr4_5_audit_debt/audit_report.md.

# PR 4.5-specific must-fix triggers (kickoff §9b):
#   - Any behavior change beyond the 13 items.
#   - Test deletion or skip-marking introduced by cleanup.
#   - License header wording drift across the 3 modules.
#   - PushFoldChartUnavailable(ValueError) breaks an except consumer (grep first).
#   - Unreachable-assert (3-E, 4-C) fires in CI -> revert + file follow-up.
# Should-fix triggers: new mypy/ruff warnings; item not implemented per §2 letter.

# 6c. Commit (explicit paths only — no git add -A).
git status   # verify staged set; no .env / secrets / build artifacts
git add poker_solver/hunl.py poker_solver/action_abstraction.py poker_solver/pushfold.py \
        poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py \
        poker_solver/abstraction/precompute.py poker_solver/profiler/memory.py \
        docs/pr4_5_audit_debt/audit_report.md
# If 3-C drove a test-side exception-type swap, also include:
#   git add tests/<rake_config_test_file>.py
git status   # re-verify
git commit -m "PR 4.5: cross-PR audit-debt sweep (mechanical fixes only)"
# Full multi-line message body in launch_kickoff.md §9c.

# 6d. Push + --no-ff merge into integration.
git push -u origin pr-4.5-audit-debt-sweep
git checkout integration
git pull --ff-only origin integration
git merge --no-ff pr-4.5-audit-debt-sweep -m "Integration: merge PR 4.5 (audit-debt-sweep)"
git push origin integration

# 6e. Update PLAN.md trajectory + docs/autonomous_log.md per plan-sync rule.
# Fire prune agent post-merge:
#   - Mark the 13 items resolved in docs/audit_followup_backlog.md.
#   - Update docs/cross_pr_cleanup_plan.md §2 to "resolved" state.
# Per continuous-pruning user-memory rule.
```

`must-fix` audit items are a hard stop. `should-fix` / `nice-to-fix` can defer to a follow-up with a TODO. Full failure-mode + recovery patterns in `launch_kickoff.md` §10.

---

## 7. Quick-reference paths

- Kickoff (authoritative): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/fanout_ready.md`
- Audit pre-prep: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_preprep.md`
- Launch decision (defer until PR 7 lands): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_decision.md`
- This file (operational ready-to-paste): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_invocations.md`
- Audit report (written post-fan-out): `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/audit_report.md`
- Source audits: `docs/pr{3,3_5,4,5}_prep/audit_report.md`
- Cross-PR cleanup canonical: `/Users/ashen/Desktop/poker_solver/docs/cross_pr_cleanup_plan.md`
- Full backlog: `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md`
- Reflog backup: `/tmp/integration_pre_pr_4_5.hash`
- Universal runbook: `/Users/ashen/Desktop/poker_solver/docs/pr_launch_runbook.md`
