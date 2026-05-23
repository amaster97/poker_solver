# PR 4.5 fan-out ready — pre-staged launch sequence

**Status:** PRE-STAGED. Do NOT execute until PR 5 + PR 6 have BOTH merged to `integration` and the user approves firing. PR 4.5 can also legally fire after PR 5 alone (alternative sequencing; narrower scope — drops 4-C / 4-D / 5-A).

**Last verified:** 2026-05-22. 13-item scope locked against four source audits (PR 3, 3.5, 4, 5). All 7 target source files exist; no behavior change expected; ~30–50 LoC delta.

This doc collapses `launch_kickoff.md` into the fire-when-PR-5+PR-6-land order. Authoritative kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md`. This file is the operational shortlist.

---

## 1. Pre-flight gate (run AFTER PR 5 + PR 6 land, BEFORE branch creation)

All five must pass. If any fails, stop and resolve.

```sh
cd /Users/ashen/Desktop/poker_solver

# 1a. integration tip includes BOTH PR 5 + PR 6 merge commits.
git fetch origin
git log --oneline integration -10
# Expected: PR 5 and PR 6 merges both visible near the top.

# 1b. integration tip matches origin/integration.
git rev-parse integration; git rev-parse origin/integration   # must be equal

# 1c. Working tree clean.
git status   # expect: "nothing to commit, working tree clean"

# 1d. All four audit reports + the cross-PR cleanup plan present.
ls -la docs/cross_pr_cleanup_plan.md docs/audit_followup_backlog.md
ls -la docs/pr3_prep/audit_report.md docs/pr3_5_prep/audit_report.md
ls -la docs/pr4_prep/audit_report.md docs/pr5_prep/audit_report.md

# 1e. Reflog backup (per runbook §0).
git rev-parse integration > /tmp/integration_pre_pr_4_5.hash
```

Optional sanity: `pytest -x -q` from `integration` tip — must be green. That count becomes the post-PR-4.5 regression bar.

---

## 2. Branch creation

```sh
cd /Users/ashen/Desktop/poker_solver
git checkout integration
git pull --ff-only origin integration
git checkout -b pr-4.5-audit-debt-sweep
git status   # expect: clean tree on pr-4.5-audit-debt-sweep
```

Branch name fixed and audit-prompt-cross-referenced; do NOT improvise.

---

## 3. Three-agent fan-out launch (SAME tool-call wave)

For each agent, the prompt body is the items list from `launch_kickoff.md` §2 for that PR slice, plus ownership row from §5a, plus the standing "mechanical fixes only; no behavior changes; no new tests; no docstring expansions" clause. There are no separate `agent_{a,b,c}_prompt.md` files for PR 4.5 — the kickoff doc IS the spec.

```
Agent A — "PR 4.5 Agent A — PR 3/3.5 mechanical audit-debt fixes (8 items)"
  scope: Items 3-A, 3-B, 3-C, 3-D, 3-E, 3.5-A, 3.5-B, 3.5-C
  files: hunl.py, action_abstraction.py, pushfold.py
  prompt body: <kickoff §2 PR 3 + PR 3.5 sections> + <kickoff §5a Agent A row> + standing clause
  subagent_type: general-purpose
  run_in_background: true

Agent B — "PR 4.5 Agent B — PR 4 mechanical audit-debt fixes (4 items)"
  scope: Items 4-A, 4-B, 4-C, 4-D
  files: equity_features.py, emd_clustering.py, precompute.py, hunl.py:336 only
  prompt body: <kickoff §2 PR 4 section> + <kickoff §5a Agent B row> + standing clause
  subagent_type: general-purpose
  run_in_background: true

Agent C — "PR 4.5 Agent C — PR 5 mechanical audit-debt fixes (1 item)"
  scope: Item 5-A
  files: profiler/memory.py
  prompt body: <kickoff §2 PR 5 section> + <kickoff §5a Agent C row> + standing clause
  subagent_type: general-purpose
  run_in_background: true
```

**Ownership lock (do NOT relax):**

| Agent | Owns | Read-only on | Forbidden |
|---|---|---|---|
| A | `poker_solver/hunl.py` (lines 14, 107, 109; license header), `action_abstraction.py`, `pushfold.py` | `docs/pr{3,3_5}_prep/audit_report.md` | `hunl.py:336` (Agent B owns), Agent B/C files, any new tests |
| B | `abstraction/equity_features.py`, `abstraction/emd_clustering.py`, `abstraction/precompute.py`, `hunl.py:336` only | `docs/pr4_prep/audit_report.md` | Agent A's lines in `hunl.py`, Agent C files, any new tests |
| C | `profiler/memory.py` | `docs/pr5_prep/audit_report.md` | any non-`profiler/` edits, any new tests |

**Shared-file caveat (4-B):** `hunl.py:336` is Agent B's edit even though `hunl.py` is otherwise Agent A's file. Line ranges do NOT overlap (A: 14, 107, 109, ~plus header; B: 336). Git auto-merges trivially.

While A/B/C run, fan out parallel work (PR 7 spec polish, autonomous-log pruning, doc inventory sweep) per parallel-agents-default memory.

---

## 4. Expected outputs + timeline

**Wall-clock:** ~90 min total (~60 min parallel agent waves — A: ~30 min, B: ~30 min, C: ~15 min, concurrent + ~30 min aggregator). Net throughput vs sequential is ~2.5×.

**Deliverables (PR surface, 7 files touched):**
- `poker_solver/hunl.py` (3-A license header; 3-C `AssertionError` → `ValueError`; 3-D drop `field` import; 4-B SHOWDOWN predicate tighten)
- `poker_solver/action_abstraction.py` (3-B license header; 3-E unreachable assert)
- `poker_solver/pushfold.py` (3.5-A `PushFoldChartUnavailable(ValueError)`; 3.5-B drop `v1-placeholder`; 3.5-C remove dead `_canonical_hand_classes`)
- `poker_solver/abstraction/equity_features.py` (4-A license header)
- `poker_solver/abstraction/emd_clustering.py` (4-C unreachable assert on empty-cluster fallback)
- `poker_solver/abstraction/precompute.py` (4-D `max_boards_per_street` sentinel kwarg)
- `poker_solver/profiler/memory.py` (5-A drop unused `numpy` import + `_ = np` suppression)

**Small PR:** ~30–50 LoC net delta (mostly subtractions + one-line additions). Reviewable in <15 min not counting audit cross-refs.

**Pass criteria:** test-count equals pre-PR-4.5 baseline (no test deletions; possible exception: rake-config test updated from `pytest.raises(AssertionError)` → `pytest.raises(ValueError)` per §8a of kickoff — counts as part of the mechanical fix); `mypy --strict poker_solver/` clean; `ruff check` clean.

---

## 5. Out-of-scope guard (do NOT silently expand)

If an agent reports "while reviewing PR N audit, I also fixed X" — REVERT X. Defer list (kickoff §3) is authoritative:
- K-means quality tuning (post-PR-6; production-scale evidence)
- `save_abstraction` byte-determinism (future content-addressable cache PR)
- 6 skip-marked PR 5 TURN tests (PR 6 should resolve)
- PR 3.5 §6 must-fixes 1–5 (already landed in commit `1cbf52a`)
- Spec-amendment items (HUNLState.config source-of-truth; d=2 jam landmark; strategic-equivalence collapse)
- `_canonicalize` / `_apply_suit_perm_to_hand` rename (next PR touching `buckets.py`)
- CLI integration items (next PR with CLI surface changes)
- New test coverage (not mechanical-fix scope)

If reclassification needed: add to kickoff §2 + update §5a ownership; do NOT silently extend.

---

## 6. Post-fan-out: audit + commit

Per `launch_kickoff.md` §9: after all three agents return, run `pytest -x` + `mypy --strict poker_solver/` + `ruff check`. Then audit + check battery in parallel: `sh scripts/check_pr.sh > /tmp/check_pr_4_5_output.log 2>&1` + audit agent writes `docs/pr4_5_audit_debt/audit_report.md` (kickoff §9b prompt body).

PR 4.5-specific must-fix triggers: any behavior change beyond the 13 items; test deletion/skip introduced by cleanup; license header wording drift across 3 modules; `PushFoldChartUnavailable(ValueError)` breaks an `except PushFoldChartUnavailable` consumer (grep first); unreachable assert fires in CI (kickoff §8c — revert + file follow-up).

Commit explicit paths (NO `git add -A`); push `pr-4.5-audit-debt-sweep`; `--no-ff` merge into `integration`; update `PLAN.md` trajectory + `docs/autonomous_log.md`. Fire prune agent post-merge to mark the 13 items resolved in `audit_followup_backlog.md` + flip `cross_pr_cleanup_plan.md` §2 state to "resolved" (continuous-pruning rule).

Full pipeline lives in `launch_kickoff.md` §9a–9e. This doc stops at fan-out launch.
