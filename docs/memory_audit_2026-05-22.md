# Memory Rules Audit — 2026-05-22

**Scope:** Audit of `/Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/` against the `MEMORY.md` index.

**Method:** Read every `.md` file in the memory directory + the index, then ran the five required checks. Read-only — no memory files were modified.

**Note on count:** Task brief said "13 memory rules" but the actual count is **14** (matching 14 files + 14 index entries — both are internally consistent with each other; the task brief was off by one).

---

## 1. Inventory Table (14 rules)

| # | Filename | Slug | Type | Bytes | Last modified | Strength |
|---|---|---|---|---:|---|---|
| 1 | `user_role.md` | user-role | user | 906 | 2026-05-20 19:46 | FLOOR |
| 2 | `feedback_interaction.md` | feedback-interaction | feedback | 1,695 | 2026-05-20 19:46 | FLOOR |
| 3 | `project_solver.md` | project-solver | project | 2,588 | 2026-05-20 20:21 | FLOOR |
| 4 | `feedback_references.md` | feedback-references | feedback | 1,581 | 2026-05-20 19:56 | FLOOR |
| 5 | `feedback_plan_sync.md` | feedback-plan-sync | feedback | 1,448 | 2026-05-20 23:50 | DEFAULT |
| 6 | `feedback_pr_branches.md` | feedback-pr-branches | feedback | 2,743 | 2026-05-21 01:07 | FLOOR |
| 7 | `feedback_parallel_agents.md` | feedback-parallel-agents | feedback | 4,879 | 2026-05-21 01:11 | FLOOR |
| 8 | `feedback_agent_scheduling.md` | feedback-agent-scheduling | feedback | 3,467 | 2026-05-20 23:57 | DEFAULT |
| 9 | `feedback_no_extrapolate.md` | feedback-no-extrapolate | feedback | 2,021 | 2026-05-21 00:18 | DEFAULT |
| 10 | `feedback_continuous_pruning.md` | feedback-continuous-pruning | feedback | 5,110 | 2026-05-21 00:39 | DEFAULT |
| 11 | `feedback_min_five_agents.md` | min-five-agents | feedback | 2,199 | 2026-05-22 02:02 | FLOOR (autonomous only) |
| 12 | `feedback_orchestrator_only.md` | orchestrator-only | feedback | 2,817 | 2026-05-22 01:29 | FLOOR |
| 13 | `feedback_no_concurrent_branch_ops.md` | feedback-no-concurrent-branch-ops | feedback | 4,210 | 2026-05-22 02:34 | FLOOR |
| 14 | `reference_planfile.md` | reference-planfile | reference | 1,342 | 2026-05-20 19:47 | DEFAULT |

**Totals:** 14 rules · 36,996 bytes · 10 feedback / 1 user / 1 project / 1 reference (note: 11 + 1 + 1 + 1 = 14).

---

## 2. Check 1 — Index Consistency

**Result:** PASS.

- Every memory file present on disk has an entry in `MEMORY.md`: yes (14/14).
- Every entry in `MEMORY.md` resolves to a real file: yes (14/14).
- No orphan files; no dangling links.

| Index entry | File path | Resolves? |
|---|---|---|
| `user_role.md` | user_role.md | yes |
| `feedback_interaction.md` | feedback_interaction.md | yes |
| `project_solver.md` | project_solver.md | yes |
| `feedback_references.md` | feedback_references.md | yes |
| `feedback_plan_sync.md` | feedback_plan_sync.md | yes |
| `feedback_pr_branches.md` | feedback_pr_branches.md | yes |
| `feedback_parallel_agents.md` | feedback_parallel_agents.md | yes |
| `feedback_agent_scheduling.md` | feedback_agent_scheduling.md | yes |
| `feedback_no_extrapolate.md` | feedback_no_extrapolate.md | yes |
| `feedback_continuous_pruning.md` | feedback_continuous_pruning.md | yes |
| `feedback_min_five_agents.md` | feedback_min_five_agents.md | yes |
| `feedback_orchestrator_only.md` | feedback_orchestrator_only.md | yes |
| `feedback_no_concurrent_branch_ops.md` | feedback_no_concurrent_branch_ops.md | yes |
| `reference_planfile.md` | reference_planfile.md | yes |

---

## 3. Check 2 — Cross-Reference Consistency

**Result:** PASS. All `[[slug]]` references resolve.

| Source file | Reference token | Target slug | Resolves? |
|---|---|---|---|
| `project_solver.md` | `[[noambrown-poker-solver-ref]]` | (project-local ref label, not a memory slug) | Convention — see note |
| `feedback_plan_sync.md` | `[[feedback-plan-sync]]` (self-mention) | feedback-plan-sync | yes (self) |
| `feedback_agent_scheduling.md` | `[[feedback-parallel-agents]]` | feedback-parallel-agents | yes |
| `feedback_continuous_pruning.md` | `[[feedback-plan-sync]]` | feedback-plan-sync | yes |

**Note on `[[noambrown-poker-solver-ref]]`:** This token is used in `project_solver.md` line 31 as a project-internal reference label, not as a pointer to a memory file. The actual filesystem location of the Noam Brown clone is documented in `reference_planfile.md` line 18. This is a stylistic ambiguity — the same `[[…]]` syntax is used both for memory cross-refs and for "this entity exists somewhere project-side." Not a bug, but worth flagging.

**Cross-reference graph (textual):**

```
feedback-parallel-agents  <──── feedback-agent-scheduling
feedback-plan-sync        <──── feedback-continuous-pruning
project-solver            ────> [[noambrown-poker-solver-ref]] (project-side, not memory)
```

Most rules are independent (no in/out edges). The hub-and-spoke pattern is light, which is healthy — rules are loosely coupled.

---

## 4. Check 3 — Recency / Contradiction Check

**Result:** PASS — no contradictions found. Two pairs reinforce each other and both should be kept.

**Pair A — Parallel-agents vs Min-five-agents (REINFORCING, not contradicting):**
- `feedback_parallel_agents.md` (2026-05-21): "Default to fan-out of 3-5 agents whenever the parallel budget permits."
- `feedback_min_five_agents.md` (2026-05-22): "Floor is now 5. Steady-state count must be ≥ 5 concurrent agents at ALL times."
- **Analysis:** The newer min-five rule **strengthens** the older parallel-agents rule. Parallel-agents had `3-5` as the default; min-five tightens the floor to `≥ 5`. They are consistent — min-five is the operative floor, parallel-agents provides the "why" and the fan-out patterns. Keep both.

**Pair B — Agent-scheduling vs Parallel-agents (REINFORCING):**
- `feedback_agent_scheduling.md`: smart scheduling, aggregate per wave, don't launch dependent agents prematurely.
- `feedback_parallel_agents.md`: default to fan-out, don't fall back to sequential.
- **Analysis:** Parallel-agents is the "go wide" rule; agent-scheduling is the "be smart about it" guardrail. They are complementary, not contradictory.

**Pair C — Orchestrator-only vs Parallel-agents (REINFORCING):**
- `feedback_orchestrator_only.md`: I do not implement; I spawn agents.
- `feedback_parallel_agents.md`: When I spawn, spawn multiple.
- **Analysis:** Orchestrator-only is the "what I do" rule; parallel-agents is the "how I spawn" rule. They compose cleanly.

**No contradictions found.** All 14 rules are internally consistent.

---

## 5. Check 4 — Sunset Candidates

**Result:** **0 strong sunset candidates.** All rules are still operative as of 2026-05-22.

**Reviewed for sunset; kept (with rationale):**

| Rule | Why considered | Why kept |
|---|---|---|
| `feedback_pr_branches.md` | PR 1 and PR 2 are historical; rule mentions them | The historical note is *useful context* (explains why the rule was needed). PR 3+ work is ongoing per docs/. Keep. |
| `feedback_no_extrapolate.md` | Born from a PR 3 prep incident | The lesson generalizes — applies to any future memory/perf estimate. Keep. |
| `reference_planfile.md` | Mentions "first PR" / Phase 0 setup | The plan path itself is still load-bearing. The Phase-0 clone list is stale but minor. Soft candidate for a *content trim*, not deletion. |

**Soft trim suggestion (optional, not a recommended deletion):**

- `reference_planfile.md` lines 14-15: "Current state: Python equity calculator (single commit)..." — this is outdated; the repo has progressed to PR 5+ per `docs/`. The rest of the file (plan-file location, Noam Brown clone location) is still load-bearing. **Recommend:** trim lines 14-15 in a future pass. Not urgent.

Per the constraint "Don't recommend rule deletions without strong justification," I am **not** recommending any deletions today.

---

## 6. Check 5 — Strength Gradient

Rules ranked by current operative strength based on recent-session evidence (frequency of citation, recency of edits, criticality if violated).

### FLOOR (inviolable — violating breaks the working relationship)

1. **`feedback_orchestrator_only.md`** — newest hard rule (2026-05-22). User explicitly told me to commit it to memory after I drifted. Violating = doing inline work = direct user friction.
2. **`feedback_no_concurrent_branch_ops.md`** — newest rule (2026-05-22, post-PR-5-near-loss). Violating = data loss risk. Backed by a live incident.
3. **`feedback_min_five_agents.md`** — explicit user-stated floor with verbatim quote (2026-05-22). Inviolable during autonomous sessions.
4. **`feedback_parallel_agents.md`** — user has flagged drift **three** times verbatim. Violating = wasted wall-clock + user frustration.
5. **`feedback_pr_branches.md`** — every PR from PR 3+ must be on its own branch. Violating = unreviewable diffs on main.
6. **`feedback_references.md`** — never guess from training data. Violating = silently bad CFR/competitor claims.
7. **`user_role.md`** — foundation (who the user is). Always operative.
8. **`feedback_interaction.md`** — response density + form-rejection protocol. Always operative.
9. **`project_solver.md`** — locked architectural decisions. Violating = re-litigating closed scope.

### DEFAULT (always-on but lower friction if briefly forgotten)

10. **`feedback_continuous_pruning.md`** — prune after every PR/wave/conversation. Drift here accumulates slowly.
11. **`feedback_agent_scheduling.md`** — wave-aggregation discipline. Mostly a refinement of parallel-agents.
12. **`feedback_plan_sync.md`** — `cp` after every plan edit. Drift is recoverable.
13. **`feedback_no_extrapolate.md`** — instrument before locking. Specific to memory/perf estimates.
14. **`reference_planfile.md`** — pointer rule (path lookups).

### NICE-TO-HAVE

(None — all current rules are at least DEFAULT-strength. The memory directory is appropriately curated.)

---

## 7. Summary Findings

- **Total rules:** 14 (task brief said 13; off by one — actual is 14, and the index is consistent with the filesystem).
- **Contradictions:** 0.
- **Sunset candidates:** 0 strong; 1 soft content-trim opportunity in `reference_planfile.md` lines 14-15 (outdated repo state description). No rule should be deleted.
- **Cross-reference health:** all `[[slug]]` links resolve. One stylistic ambiguity (`[[noambrown-poker-solver-ref]]` in `project_solver.md` is project-side, not memory-side) — minor.
- **Strength distribution:** 9 FLOOR / 5 DEFAULT / 0 NICE-TO-HAVE. The memory layer is dense and operative; nothing is dead weight.

### Top 3 most load-bearing rules per recent-session evidence

Based on memory file edit recency, explicit user-quoted enforcement, and visibility in recent project artifacts (`docs/wake_up_brief_2026-05-22.md`, `docs/autonomous_decisions_2026-05-22.md`, `docs/git_state_post_recovery.md`):

1. **`feedback_orchestrator_only.md`** (2026-05-22 01:29) — fresh user-quoted rule; directly governs every turn I take.
2. **`feedback_min_five_agents.md`** (2026-05-22 02:02) — fresh user-quoted floor; governs autonomous-session scheduling.
3. **`feedback_no_concurrent_branch_ops.md`** (2026-05-22 02:34) — born from a live near-loss incident on PR 5; governs every branch-switching agent decision.

(Honorable mention: `feedback_parallel_agents.md` — user has flagged drift three times; perma-load-bearing but slightly less recent.)

---

## 8. Audit Hygiene

- This audit modified zero memory files.
- Output saved to `/Users/ashen/Desktop/poker_solver/docs/memory_audit_2026-05-22.md` (per task instruction — memory dir is gitignored / private).
- Re-run cadence suggestion: re-audit after the next 5 PRs or whenever rule count crosses 18.
