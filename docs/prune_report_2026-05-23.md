# Memory + PLAN.md prune report — 2026-05-23

Sweep against the seven verification points the orchestrator flagged. Memory files reviewed against current repo state (`62c75d5` on main + integration; PR 10a.5 audit verdict READY; 3 PRs in flight, not 4; docs/ gitignored; no HIGH-severity PII per `docs/repo_audit.md`; private mirror authorized but not yet created).

## Memory files reviewed

| File | Action | Notes |
|---|---|---|
| `MEMORY.md` (index) | no-change | Index is consistent with the 18 memory files in directory; no orphan entries. |
| `user_role.md` | no-change | Stable user profile; no stale claims. |
| `project_solver.md` | **edited** | Updated "4 in flight" → "3 in flight (10a.5 audit-passed pending commit; 8, 9 implementer in flight); PR 10b staged behind PR 9." |
| `post_v1_ga_status.md` | **edited** | Frontmatter + body updated to reflect 3-in-flight state and PR 10a.5 audit verdict READY with 3 should-fix items; "four in-flight" → "three in-flight". |
| `post_ga_parallel_launch.md` | **edited** | Title "4-parallel" → "parallel"; table reformatted to 3 in-flight + 1 staged (10b). PR 10a.5 row notes audit READY + pending commit. |
| `feedback_public_repo_hygiene.md` | **edited** | "Origin push policy TBD pending user confirmation" line replaced with the resolved Option C state (origin public main-only; private mirror not yet created); cross-links to `[[dual-remote-workflow]]`. |
| `feedback_dual_remote_workflow.md` | no-change | Recent (today); consistent with the public-repo-hygiene edit above. Note: mirror does NOT exist yet, but the file already frames first-time setup correctly — no edit needed. |
| `feedback_continuous_pruning.md` | no-change | Process rule; still current. |
| `feedback_min_five_agents.md` | no-change | Process rule; current. |
| `feedback_orchestrator_only.md` | no-change | Process rule; current. |
| `feedback_parallel_agents.md` | no-change | Process rule; current. |
| `feedback_agent_scheduling.md` | no-change | Process rule; current. |
| `feedback_no_concurrent_branch_ops.md` | no-change | Process rule + PR 5 incident lessons; current. |
| `feedback_no_extrapolate.md` | no-change | Process rule; current. |
| `feedback_pr_branches.md` | no-change | Process rule; current. |
| `feedback_plan_sync.md` | no-change | Process rule; current. |
| `feedback_references.md` | no-change | Process rule; current. |
| `feedback_interaction.md` | no-change | Process rule; current. |
| `reference_planfile.md` | no-change | Status line already says "v1.0.0 GA landed"; lists 4 in-flight PRs but the wording is consistent if read as "post-GA backlog of 4 PRs" (10b is still pending). Leaving as-is to avoid >1-line churn; recommend orchestrator confirm. |

## PLAN.md changes applied

- **PR 10a.5 status row** (Section 2 trajectory table): appended "audit verdict **READY** (2026-05-23) with 3 should-fix items — pending commit." (single cell edit). Emoji stays 🚧 until commit lands.

## PLAN.md changes proposed (not applied — multi-line)

1. **§7 USAGE.md / DEVELOPER.md "Being written this session"** language (lines 304-305): both docs landed in PR 11 follow-ups; "this session" wording is stale. Recommend collapsing to a single line acknowledging both are part of the v1.0.0 tracked surface.
2. **§6 Carryover items I2 + N5** — both deferred to PR 11; PR 11 is shipped. Recommend marking RESOLVED or moving to §9 archive (need orchestrator to verify the I2 first-launch warning and N5 wheel-bundling fix actually landed before declaring RESOLVED).
3. **§2 footer "Each PR ends with..." paragraph** is fine but the "Sequencing intent" line in §7 still implies PR 10a.5 + PR 8 + PR 9 are all in motion. After PR 10a.5 commits, the chain should compress to "PR 8 ∥ PR 9 → PR 10b → PR 12". One-line edit, but defer until PR 10a.5 actually commits.

## Contradictions found

1. **`reference_planfile.md` vs `post_v1_ga_status.md`** — `reference_planfile` references "Four post-GA PRs in flight" while `post_v1_ga_status` (now edited) says "three in flight". Reconciled by treating `reference_planfile`'s claim as "post-GA backlog of 4 PRs including the staged-but-not-in-flight PR 10b". A tighter rewrite would help but exceeds the one-line edit scope.
2. **`post_v1_ga_status.md` references `docs/cross_pr_coordination_2026-05-22.md`** but the actual filename on disk is `docs/cross_pr_coordination.md` (no date suffix). Minor path drift; left for orchestrator to confirm if they want the citation tightened.

## Duplicate entries (near-duplicates)

1. **Post-GA snapshot duplicated** between `post_v1_ga_status.md` and `post_ga_parallel_launch.md`. Both list the same set of in-flight PRs with the same coordination doc. Their retirement triggers also overlap. **Recommend** merging into one file once 10a.5 + 8 + 9 land — the two files were created as sibling snapshots and are now redundant.
2. **`project_solver.md` "Status as of 2026-05-22"** section duplicates portions of `post_v1_ga_status.md`. Lower priority; project_solver also carries the locked-decisions content which the status memory doesn't.
3. **Parallelism rules spread across three memories** (`feedback_parallel_agents.md`, `feedback_agent_scheduling.md`, `feedback_min_five_agents.md`). Each covers a distinct angle (fan-out by default / smart-not-greedy scheduling / inviolable ≥5 floor). Not a strict duplicate but worth a unified "parallelism playbook" rewrite at some point.

## Recommended-delete

- None. All 18 files carry distinct content. Duplicates above are candidates for **merge**, not deletion.
