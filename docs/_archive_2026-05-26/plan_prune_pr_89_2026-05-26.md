# Plan + memory prune report (2026-05-26, PR 89)

Continuous-pruning pass per the user's `feedback_continuous_pruning.md` rule. Output of the prune-agent task. PLAN.md write-back to local workspace is HELD pending user review.

## Memory prune (MEMORY.md index)

### Before / after

- **Before:** 30 active entries (cliff = 31; safe but high).
- **After:** ~25 distinct primary entries (under the cliff).
- **Files deleted:** 6 (consolidated into other files).
- **Files updated in place:** 3 (consolidations).
- **Files net-condensed:** 1 (long-running-session-wrap shortened to index pointer).

### Consolidations applied

1. **`feedback_pr_branches.md` + `feedback_pr_branch_hygiene.md` + `feedback_no_concurrent_branch_ops.md` → `feedback_branch_ops.md`** (NEW).
   - Rationale: All three cover branch-ops discipline; they cross-referenced each other heavily. Consolidated into one file with three clearly-marked sub-rules (Rule 1 per-PR branches; Rule 2 PR branch hygiene; Rule 3 no concurrent branch ops + stash hygiene). Originating incident detail for the PR 5 near-loss preserved verbatim under Rule 3. Total file size ~5.5 KB.
   - Net: -2 entries.

2. **`feedback_parallel_agents.md` + `feedback_min_five_agents.md` + `feedback_agent_scheduling.md` → `feedback_parallel_agents.md`** (UPDATED, others deleted).
   - Rationale: All three cover the same concept (concurrent agent fan-out, agent floor, scheduling). The min-five-agents history was already captured by the canonical floor=4 rule. Consolidated into three clear sub-rules: Rule 1 default to fan-out + 6 patterns; Rule 2 floor=4 + orchestrator-always-free; Rule 3 one-shot scheduler not greedy pool. Total file size ~5.5 KB.
   - Net: -2 entries.

3. **`feedback_interaction.md` + `feedback_answer_first.md` → `feedback_interaction.md`** (UPDATED, answer_first deleted).
   - Rationale: Both are user-interaction protocols. Consolidated into four clear sub-rules: answer-first (HARD), response density, form-rejection protocol, "why" before committing. Total file size ~2.4 KB.
   - Net: -1 entry.

4. **`feedback_long_running_session_wrap.md` condensed in place.**
   - Rationale: Previous file was 5.4 KB with a verbose REFUTED-update appendix. Condensed to ~3.5 KB keeping the load-bearing rules (session-close preconditions, REFUTED heuristic note, 3-step kernel-bug verification protocol, revocation protocol) and dropping the multi-paragraph reversal-arc narrative (preserved in PLAN_archive.md).

### MEMORY.md index updated

22 lines (down from 30), each grouping related entries. Distinct primary entries = 25. Sub-entries (clusters like "wrapper-hazard sub-rules" grouped on one line) = ~7. Total unique files = 39 (incl. MEMORY.md and project_solver / user_role / reference_*) — down from 45 pre-prune.

### Files NOT touched (kept verbatim, still load-bearing)

- All 4 reference files (`user_role.md`, `project_solver.md`, `reference_planfile.md`, `reference_github_auth.md`).
- Specific-rule files where the lesson was incident-driven and the rule still applies even if the incident is old (per user's safety guidance):
  - `feedback_dotso_arch_check.md`, `feedback_silent_skip_hazard.md`, `feedback_agent_execution_timeout.md` — load-bearing on ship discipline.
  - All 8 parity-wrapper-hazard cluster files — load-bearing on cross-system verification.
  - `feedback_label_vs_semantics.md`, `feedback_no_extrapolate.md`, `feedback_orchestrator_only.md`, `feedback_test_write_reference.md`, `feedback_stall_check.md` — meta-rules still active.
  - `feedback_public_repo_hygiene.md`, `feedback_dual_remote_workflow.md`, `feedback_pr10a5_autonomous_commit.md` — load-bearing on commit + push autonomy.
  - `feedback_continuous_pruning.md`, `feedback_plan_sync.md`, `feedback_post_integration_verification.md` — load-bearing on workflow discipline.
  - `feedback_persona_test_rectification.md`, `feedback_persona_time_budgets.md`, `feedback_post_ship_persona_retest.md`, `feedback_ui_packaging_sync.md` — load-bearing on persona burst close.
  - `feedback_references.md`, `feedback_research_first_failure_protocol.md` — load-bearing on the reference-first workflow.

### Memory directory work IS COMPLETE; applied in place

The memory directory is outside the project repo. No PR needed. Changes applied directly per the user's procedure.

---

## PLAN.md prune (proposed; HELD for user review)

### Before / after

- **Before:** 102,253 bytes / 600 lines.
- **After:** 39,287 bytes / 438 lines (62% reduction; well under 60 KB target).
- **Archive:** 30,360 bytes at `docs/_archive_plan_2026-05-26/PLAN_archive.md` (captures all moved content).

### Section-by-section keep / archive decisions

| Section | Pre-prune | Decision | Rationale |
|---|---|---|---|
| Status block (top) | ~25 lines, 2026-05-25 mid-day in-flight narrative | **Replaced** with current-state one-paragraph + 5 gate-status lines + framing-rules summary | Most of "in flight" status was stale: PR 50/51/52/54/55/56/53c (v1.7.1 bundle) + PR #20/#21/#22 + v1.8 SIMD Phases 1-4 + PR 76 all SHIPPED on origin/main since the status was written. Reversal-chain detail (R10/R11) preserved in archive. |
| §1 Locked decisions | ~70 lines | **Kept verbatim** | All locked decisions still load-bearing. Minor edit: removed "deferred to a post-PR-10b measurement pass" (deferred → "set post-PR-10b measurement") since slider tier defaults shipped at v1.6.0. |
| §1 Out of scope / In-scope v1 additions | ~15 lines | **Kept; status updated** | B9 marked SHIPPED (PR 76); B10 spec landed marked. |
| §2 PR roadmap table | ~60 rows | **Condensed to 3 grouped lists + 1 small queued table** | Original table was 48+ rows mostly all shipped. Replaced with: (a) one paragraph listing all PR shipped through v1.7.0; (b) one paragraph listing v1.7.1 Hybrid bundle + v1.8 SIMD progression; (c) small table of 4 in-flight items. Dependency graph kept. |
| §3 Architecture | ~50 lines | **Kept verbatim except R11 resolution status notes (archived)** | Architecture decisions all stand. R11-resolution narrative (2 multi-paragraph notes) moved to archive since R11 is RESOLVED. Two-tier honesty + aggregator-vs-vector-form sections kept (still load-bearing). |
| §4 Verification + check battery | ~28 lines | **Kept verbatim** | All load-bearing. |
| §5 Parallelization | ~40 lines | **Kept; references updated** | Hard rules + patterns + scheduling discipline all load-bearing. Reference updated to `feedback_parallel_agents.md` (consolidated). |
| §6 Open items | ~24 lines | **Mildly condensed** | Resolved items consolidated paragraph kept. v1.0.0 GA + v0.5.0 milestone callouts kept. Production-scale validation caveat updated to reflect 200K river PASS / turn in flight. |
| §7 Kickoff docs staged | ~33 lines | **Condensed to 1 paragraph** | All 9 kickoff docs reference shipped PRs; preserved as reference paragraph + archive doc footnote. User-facing docs callouts kept. |
| §8 References + license audit | ~22 lines | **Kept verbatim** | Load-bearing reference-first rule + license audit table. |
| §9 Archive / decision log | ~14 lines | **Kept + extended with 3 new entries** | New: v1.6.1 strict-gate REFUTED, R11 engine-bug-framing REFUTED, PR 47 CANCELED, session-close REVOKED. All decisions-then-revised that the user might re-litigate. |
| §10 Burst close gates | ~17 lines | **Kept; status fields updated** | All 5 gate criteria preserved. Status fields updated to current shipped state (Gate 1 CLOSED via v1.7.1 ship; Gate 2 CLOSED via v1.6.0; Gate 3 12 PASS / 4 PARTIAL / 2 BLOCKED snapshot; Gate 4 200K river complete + turn in flight; Gate 5 PARTIAL CLOSE with PR #3 + #42 + #47 .dmg work). |
| §11 In-scope this burst | ~14 lines (B1-B12) | **Kept; status updated** | All B-items preserved with one-line acceptance criteria. Status fields: B1-B4 CLOSED; B9 SHIPPED (PR 76); B11 SHIPPED (v1.8 phases); B12 SHIPPED (PR #21 + #22); B10 spec landed; B5-B8 live or queued. |
| §12 Burst progression log | ~60 rows | **Condensed to 11 most-recent / in-flight rows** | All v1.4.0 through v1.7.0 shipped rows + dry-run #1-#10 detail + v1.7.1 retry chain (v1.7.1 retry #1-#7) moved to archive. Kept: recent shipped rows (v1.7.1, v1.8 SIMD, PR 76, PR #20/#21/#22) + in-flight rows (v1.7.2 ship, B10, Gate 4 turn, recent doc follow-ups). |
| §13 Lessons from this burst | ~90 lines | **Condensed to 1 paragraph + 12-item memory-file pointer list** | Every R1-R11 lesson is fully codified in a memory file (per the cross-references). Live PLAN.md now points at the memory files; the full pre-prune narrative archived for reasoning trail. |

### What was NOT changed (current decisions, per user constraint)

- All locked decisions in §1.
- All scope boundaries.
- All gate definitions in §10.
- All in-scope B-items in §11 (status fields updated to reflect what's shipped on origin/main, but acceptance criteria unchanged).
- All framing rules from the 2026-05-24 burst (Brown = sanity check, multi-layer gates, audit wrappers before engines).
- All references (§8).

### Worktree + branch

- Worktree: `/tmp/wt-pr-89-plan-prune`
- Branch on origin: `pr-89-plan-prune`
- Commit: `a012de6 docs: archive pre-prune PLAN.md content (2026-05-26 continuous-pruning pass)`
- PR URL: https://github.com/amaster97/poker_solver/pull/new/pr-89-plan-prune
- **PLAN.md write-back to local workspace HELD** pending user review (user explicitly bounded this in the prune-agent prompt).

### Files to review before merging

1. `/tmp/wt-pr-89-plan-prune/PLAN.md` — proposed pruned live PLAN.md (39 KB)
2. `/tmp/wt-pr-89-plan-prune/docs/_archive_plan_2026-05-26/PLAN_archive.md` — archive (30 KB, will land on origin/main on PR merge)
3. `/Users/ashen/Desktop/poker_solver/PLAN.md` — current live (102 KB, untouched)
4. `/Users/ashen/.claude/plans/not-exactly-but-a-inherited-river.md` — master plan (68 KB, untouched; user reviews before sync)

### Recommended next steps (for user)

1. Diff pruned PLAN.md vs local: `diff -u /Users/ashen/Desktop/poker_solver/PLAN.md /tmp/wt-pr-89-plan-prune/PLAN.md | less`
2. Diff archive doc vs PLAN.md to confirm nothing load-bearing was lost.
3. If approved: `cp /tmp/wt-pr-89-plan-prune/PLAN.md /Users/ashen/Desktop/poker_solver/PLAN.md` (apply local write-back) + sync to master plan file per plan-sync rule.
4. Merge PR 89 (archive doc only) to origin/main after content review.
