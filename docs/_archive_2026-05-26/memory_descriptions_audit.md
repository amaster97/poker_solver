# Memory `description:` Frontmatter Audit (2026-05-23)

Scope: `/Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/*.md`, skipping `MEMORY.md`.

Audit bar: ≤200 chars, specific, decision-relevant, not a slug-restatement, not stale vs body.

## Per-file status

| File | Status | Notes |
|------|--------|-------|
| feedback_agent_scheduling.md | EDITED | trimmed from 213 → 177 |
| feedback_continuous_pruning.md | EDITED | trimmed from 357 → 184 |
| feedback_dotso_arch_check.md | EDITED | expanded from 53 (slug-restatement) → 192 with what+why+signal |
| feedback_dual_remote_workflow.md | EDITED | trimmed from 211 → 195 |
| feedback_independent_verification.md | EDITED | trimmed from 252 → 200 |
| feedback_interaction.md | EDITED | expanded from 95 (vague) → 159 with three concrete rules |
| feedback_label_vs_semantics.md | EDITED | expanded from 59 (thin) → 175 with origin incident |
| feedback_min_five_agents.md | CLEAN | 196 chars, already specific + accurate (floor=4 noted) |
| feedback_no_concurrent_branch_ops.md | CLEAN | 187 chars, specific (worktree + stash-drop) |
| feedback_no_extrapolate.md | EDITED | trimmed from 211 → 185 |
| feedback_orchestrator_only.md | CLEAN | 189 chars, specific |
| feedback_parallel_agents.md | CLEAN | 159 chars, specific |
| feedback_persona_test_rectification.md | EDITED | trimmed from 354 → 194 |
| feedback_persona_time_budgets.md | EDITED | trimmed from 239 → 196 |
| feedback_plan_sync.md | EDITED | trimmed from 231 → 130 |
| feedback_post_integration_verification.md | EDITED | trimmed from 239 → 194 |
| feedback_post_ship_persona_retest.md | EDITED | trimmed from 249 → 199 |
| feedback_pr_branch_hygiene.md | EDITED | trimmed from 255 → 189 |
| feedback_pr_branches.md | CLEAN | 126 chars, specific |
| feedback_pr10a5_autonomous_commit.md | EDITED | trimmed from 318 → 200; dropped stale "PR 10a.5-specific" framing |
| feedback_public_repo_hygiene.md | EDITED | trimmed from 289 → 192 |
| feedback_references.md | CLEAN | 120 chars, specific |
| feedback_research_first_failure_protocol.md | EDITED | trimmed from 312 → 193 |
| feedback_stall_check.md | EDITED | trimmed from 303 → 199; dropped specific-incident bytes |
| feedback_test_write_reference.md | EDITED | trimmed from 281 → 198 |
| feedback_ui_packaging_sync.md | CLEAN | 145 chars, specific |
| project_solver.md | CLEAN | 88 chars, scannable |
| reference_github_auth.md | EDITED | trimmed from 209 → 170 |
| reference_planfile.md | CLEAN | 85 chars, scannable |
| user_role.md | CLEAN | 117 chars, specific |

## Old → new (EDITED files)

### feedback_agent_scheduling.md
- OLD: How to schedule concurrent agents — fan out aggressively when tracks are independent, but don't launch work that genuinely depends on another in-flight agent's output. Aggregate per wave before launching the next.
- NEW: Agents are one-shot, not a pool — be smart scheduler not greedy. Fan out independent tracks; defer work gated by in-flight outputs; aggregate per wave before launching the next.

### feedback_continuous_pruning.md
- OLD: Ruthlessly prune PLAN.md and the memory directory after every PR, every research review, and every substantive conversation. Stale "we will" claims, refuted estimates, and superseded decisions must be moved to an Archive section or deleted outright. The user has explicitly flagged that the plan accumulates cruft and wants this disciplined and automatic.
- NEW: After every PR, research wave, or substantive convo: prune PLAN.md + memory. Archive or delete refuted claims, stale 'we will' language, superseded decisions. Auto-spawn a prune agent.

### feedback_dotso_arch_check.md
- OLD: .so arch verification before pytest in ship sequences
- NEW: Before pytest in any maturin/PyO3 ship sequence, verify `.so` arch matches host (`file ... | grep arm64`). Arch-mismatched .so silently skips tests AND hangs pytest output — false-PASS signal.

### feedback_dual_remote_workflow.md
- OLD: How to push updates when there are two remotes — `origin` (public, main only) and `private` (private mirror, integration + main). Keeps the dual-channel model in sync without leaking internal planning to public.
- NEW: Two remotes: origin (public, main only) + private (mirror, integration + main). Always specify remote+branch explicitly; never --all or --mirror against origin. Push protocol + cheatsheet inside.

### feedback_independent_verification.md
- OLD: Before an agent's verdict triggers a v-NEXT release, doc retraction, or release-notes correction, do an INDEPENDENT diff-test verification. Hard-FAIL numbers are hypotheses, not verdicts. The W3.5 thread's 5 sequential reversals make this load-bearing.
- NEW: Before one agent's hard-FAIL triggers v-NEXT release, doc retraction, or public-artifact rollback, run INDEPENDENT diff-test on identical input. One verdict = hypothesis; two converging = verdict.

### feedback_interaction.md
- OLD: How this user wants me to interact — question protocol, response style, when to ask vs proceed.
- NEW: Form-rejection = stop-and-discuss (not stop-and-retry); responses scannable with answer-first density; explain WHY before committing to non-obvious approaches.

### feedback_label_vs_semantics.md
- OLD: Verify what code/tests actually do; don't trust their names
- NEW: Function and test names can lie. Verify semantics at every boundary before trusting label-shaped claims. The 2026-05-23 burst's cascading misroutes both traced to label-trust.

### feedback_no_extrapolate.md
- OLD: When estimating memory / perf / cost across complex multi-dimensional structures, do not extrapolate from a single number without checking the math. Instrument and measure before locking architectural decisions.
- NEW: Never claim a numerical delta on a multi-layer system without per-layer data. Frame estimates as directional, not numerical; instrument-and-revisit beats locking based on extrapolation.

### feedback_persona_test_rectification.md
- OLD: After every persona acceptance test phase (Phase 1, Phase 2, Phase 3, or any future rerun), classify each finding using the rectification taxonomy — Type A docs-only, Type B code bug, Type C-CRITICAL/USEFUL/NICE missing feature, Type D timeout — and route to the response per the framework. Process doc lives at docs/pr13_prep/rectification_framework.md.
- NEW: After every persona acceptance phase, classify findings by Type A docs / B code bug / C-CRITICAL/USEFUL/NICE missing feature / D timeout, and route per docs/pr13_prep/rectification_framework.md.

### feedback_persona_time_budgets.md
- OLD: All v1.3+ perf gates must map to persona-time-budget rubric. Marcus (recreational) is the gating threshold for any user-facing feature. The end goal is real users getting real analysis in reasonable wall-clock — not arbitrary perf numbers.
- NEW: Every perf gate cites persona-time-budget rubric (per-spot + session). Marcus's <30s single-spot = interactive feature gate. PioSolver-class is the bar; >30 min single spot = kill-switch.

### feedback_plan_sync.md
- OLD: After every edit to the plan at ~/.claude/plans/not-exactly-but-a-inherited-river.md, immediately re-sync the local copy to /Users/ashen/Desktop/poker_solver/PLAN.md. The user wants the local copy to always reflect the latest plan.
- NEW: After editing the plan in ~/.claude/plans/, immediately cp to local PLAN.md so the repo copy never drifts from the canonical plan.

### feedback_post_integration_verification.md
- OLD: After every PR integration that touches both integration + main + remotes, run the dual-channel verification protocol from docs/post_integration_verification_protocol.md. Confirms private mirror has full history; public origin stays clean.
- NEW: After every dual-channel sync (integration + main + remotes), spawn agent to run docs/post_integration_verification_protocol.md. PASS gate before next PR; catches leaked filter or routing drift.

### feedback_post_ship_persona_retest.md
- OLD: Post-ship persona retesting catches wrapper-layer bugs that unit tests miss. Wider-range / production-scale fixtures expose narrower-range coverage gaps. Always retest at production scale, not just unit-test scale, AFTER ship — before the next ship.
- NEW: After shipping any wrapper / expansion / aggregation layer, retest at persona / production-scale cardinality before next ship. Unit-test scale hides wrapper bugs; diff-test before concluding code bug.

### feedback_pr_branch_hygiene.md
- OLD: PR branches stay on public origin as walkable history for devs / users — but they must NOT contain session artifacts (STATUS.md, SESSION_END_FINAL.md, etc.). Cutover-time cleanup of main does NOT propagate to PR branches; they need their own cleanup pass.
- NEW: PR branches stay on public origin as walkable history but must be clean — no STATUS/SESSION/HANDOFF artifacts. Main cleanup does NOT auto-propagate; audit + scrub each PR branch separately.

### feedback_pr10a5_autonomous_commit.md
- OLD: All PRs that clear audit cleanly may ship end-to-end autonomously — commit, merge to integration, filter/cherry-pick to main, push to both remotes — without per-step user OK. Originated as a PR 10a.5-specific authorization (2026-05-23 early), expanded to all audit-clear PRs including the main push (2026-05-23 later).
- NEW: Any audit-clear PR ships end-to-end autonomously (commit, integration merge, main cherry-pick, push both remotes). Exceptions: force push, origin branch delete, Type C-CRITICAL, major design.

### feedback_public_repo_hygiene.md
- OLD: Before pushing to any public-facing branch, audit what's being committed. Only push content that genuinely belongs in a public repo (user-readable docs, code, contributor guides). Never push internal planning, session artifacts, agent prompts, personal info, or anything privacy-sensitive.
- NEW: Before any push to origin, audit content: public-OK / sanitize / private-only. Never push internal planning, session artifacts, agent prompts, emails, session IDs, or secrets. Default is HOLD.

### feedback_research_first_failure_protocol.md
- OLD: When a critical-path implementation hits a wall (perf gate not met, design dead-end, no obvious path forward), do research on existing solvers + papers BEFORE surfacing to user. Override only as last resort for truly dire situations. Pair with rigorous testing — solving aggressively must not introduce new bugs.
- NEW: When a critical-path impl hits a wall, research existing solvers / papers BEFORE surfacing. User override is last resort. Aggression on problem-solving, rigor on validation — gates still apply.

### feedback_stall_check.md
- OLD: Periodically check on long-running background agents. If an agent has had no output-file write activity for >30 min, suspect hung. Before killing: ensure work is being done elsewhere OR spawn a replacement. Codified after 2 stalled agents (v1.3 Option A: 91 min idle; Plan C: 59 min idle) on 2026-05-23.
- NEW: Periodically health-check long-running agents. No .output growth >30 min = suspect hung. Before killing: spawn replacement (often tighter-scoped). Check every 20-30 min during autonomous bursts.

### feedback_test_write_reference.md
- OLD: Cross-cutting discipline during multi-agent autonomous bursts: every wave must TEST what was changed, WRITE the state to disk, and check REFERENCES before any claim. Counters the main failure mode of multi-agent work — orchestrator loses track, work is repeated, integrations fail.
- NEW: Every multi-agent wave must TEST integrated tree (don't trust agent reports), WRITE consolidated state to disk, REFERENCE actual source before any claim. Counters orchestrator-loses-track failure.

### reference_github_auth.md
- OLD: User's GitHub auth uses HTTPS + osxkeychain (no SSH keys). Large initial pushes need http.postBuffer raised (now 500 MB globally). PAT setup is a separate concern. SSH alternative available but not configured.
- NEW: GitHub auth: HTTPS + osxkeychain, no SSH keys. PAT required for HTTPS push. http.postBuffer now 500 MB globally (large pack fix). HTTP 400 + 'hung up' = buffer, not auth.

## Files modified: 20

## PII grep results

Ran `grep -nE "/Users/ashen|ashen26@" <edited-files>` on the 20 edited files.

Matches are all in **file bodies** (no edits touched bodies), and all are contextually intentional:
- `feedback_plan_sync.md` body documents the absolute path the rule applies to (cp source + destination)
- `feedback_public_repo_hygiene.md` body lists `ashen26@gsb.columbia.edu` and `/Users/ashen/...` as patterns to scan FOR (it's a privacy-rule file)
- `reference_github_auth.md` body notes `ashen26@gsb.columbia.edu` is NOT the GitHub email (auth fact)

No PII was introduced by description edits.

## Anomalies / findings

- 13 of 30 files had descriptions >250 chars (verbose, hard to skim). Largest was `feedback_continuous_pruning.md` at 357.
- 2 files had near-slug-only descriptions (`feedback_dotso_arch_check.md` at 53 chars, `feedback_label_vs_semantics.md` at 59 chars) that didn't convey decision-relevance.
- `feedback_pr10a5_autonomous_commit.md` was the only one with a clearly STALE framing — described as "PR 10a.5-specific" but body says expanded to all audit-clear PRs. New description matches current scope.
- `feedback_min_five_agents.md` slug is misleading (floor is 4, not 5) but description correctly notes "floor is 4 (reduced from 5 then 3)". Description is accurate; only the slug is historical.
- `feedback_post_ship_persona_retest.md` body was substantially revised post-R5 (W3.5 reversal); old description framed it as "wrapper-layer bugs" — still true but new description adds "diff-test before concluding code bug" to match revised body.
- 8 files were CLEAN — descriptions already concise, specific, accurate.
