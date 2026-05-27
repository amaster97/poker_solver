# Memory link integrity audit

**Date:** 2026-05-23
**Scope:** All `[[<slug>]]` references in `/Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/`
**Mode:** READ-ONLY (no files modified)

## Summary

- **Total unique `[[slug]]` references:** 23
- **Resolved (point to existing canonical `name:` slug):** 16
- **Unresolved (no matching frontmatter `name:`):** 7
- **Memory files in dir:** 30 (29 entries + MEMORY.md index)
- **Orphan files (in dir, not listed in MEMORY.md):** 0
- **MEMORY.md entries with no corresponding file:** 0

## Methodology

The canonical identifier for a memory file is its `name:` field in YAML frontmatter (NOT the filename). A `[[foo-bar]]` reference resolves iff some file's `name:` equals `foo-bar`.

## Reference resolution table

| Reference | Canonical slug match | Status | Resolves to file |
|---|---|---|---|
| `[[continuous-pruning]]` | none (canonical is `feedback-continuous-pruning`) | UNRESOLVED | — |
| `[[dual-remote-workflow]]` | dual-remote-workflow | RESOLVED | feedback_dual_remote_workflow.md |
| `[[feedback-label-vs-semantics]]` | feedback-label-vs-semantics | RESOLVED | feedback_label_vs_semantics.md |
| `[[feedback-no-extrapolate]]` | feedback-no-extrapolate | RESOLVED | feedback_no_extrapolate.md |
| `[[feedback-parallel-agents]]` | feedback-parallel-agents | RESOLVED | feedback_parallel_agents.md |
| `[[feedback-plan-sync]]` | feedback-plan-sync | RESOLVED | feedback_plan_sync.md |
| `[[feedback-research-first-failure-protocol]]` | none (canonical is `research-first-failure-protocol`) | UNRESOLVED | — |
| `[[feedback-test-write-reference]]` | none (canonical is `test-write-reference`) | UNRESOLVED | — |
| `[[github-auth-setup]]` | github-auth-setup | RESOLVED | reference_github_auth.md |
| `[[label-vs-semantics]]` | none (canonical is `feedback-label-vs-semantics`) | UNRESOLVED | — |
| `[[min-five-agents]]` | min-five-agents | RESOLVED | feedback_min_five_agents.md |
| `[[no-concurrent-branch-ops]]` | none (canonical is `feedback-no-concurrent-branch-ops`) | UNRESOLVED | — |
| `[[no-extrapolate]]` | none (canonical is `feedback-no-extrapolate`) | UNRESOLVED | — |
| `[[orchestrator-only]]` | orchestrator-only | RESOLVED | feedback_orchestrator_only.md |
| `[[persona-test-rectification]]` | none (canonical is `feedback-persona-test-rectification`) | UNRESOLVED | — |
| `[[post-ship-persona-retest]]` | post-ship-persona-retest | RESOLVED | feedback_post_ship_persona_retest.md |
| `[[pr-branches]]` | none (canonical is `feedback-pr-branches`) | UNRESOLVED | — |
| `[[public-repo-hygiene]]` | public-repo-hygiene | RESOLVED | feedback_public_repo_hygiene.md |
| `[[reference-first-rule]]` | none (canonical is `feedback-references`) | UNRESOLVED | — |
| `[[reference-planfile]]` | reference-planfile | RESOLVED | reference_planfile.md |
| `[[research-first-failure-protocol]]` | research-first-failure-protocol | RESOLVED | feedback_research_first_failure_protocol.md |
| `[[stall-check-relaunch]]` | stall-check-relaunch | RESOLVED | feedback_stall_check.md |
| `[[test-write-reference]]` | test-write-reference | RESOLVED | feedback_test_write_reference.md |

## Unresolved references — analysis

All 7 unresolved refs are **slug-naming inconsistencies**, NOT stale pointers. Every unresolved slug DOES have a corresponding memory file; the link just uses a name that doesn't match the file's frontmatter `name:` field. None are "worth writing later" — they all already exist.

Two naming patterns cause the misses:

**Pattern A — `feedback-` prefix mismatch (4 cases):**
The file's canonical slug starts with `feedback-` but the link omits it (or vice versa).

| Reference | What the link expected | Canonical slug in file | File |
|---|---|---|---|
| `[[continuous-pruning]]` | name with no prefix | `feedback-continuous-pruning` | feedback_continuous_pruning.md |
| `[[no-concurrent-branch-ops]]` | name with no prefix | `feedback-no-concurrent-branch-ops` | feedback_no_concurrent_branch_ops.md |
| `[[no-extrapolate]]` | name with no prefix | `feedback-no-extrapolate` | feedback_no_extrapolate.md |
| `[[persona-test-rectification]]` | name with no prefix | `feedback-persona-test-rectification` | feedback_persona_test_rectification.md |
| `[[label-vs-semantics]]` | name with no prefix | `feedback-label-vs-semantics` | feedback_label_vs_semantics.md |
| `[[pr-branches]]` | name with no prefix | `feedback-pr-branches` | feedback_pr_branches.md |
| `[[feedback-research-first-failure-protocol]]` | name with `feedback-` prefix | `research-first-failure-protocol` | feedback_research_first_failure_protocol.md |
| `[[feedback-test-write-reference]]` | name with `feedback-` prefix | `test-write-reference` | feedback_test_write_reference.md |

**Pattern B — semantic rename (1 case):**

| Reference | What the link expected | Canonical slug in file | File |
|---|---|---|---|
| `[[reference-first-rule]]` | reference-first-rule | `feedback-references` | feedback_references.md |

The MEMORY.md index calls this "Reference-first rule" but the file's `name:` is `feedback-references`.

## Orphan check (files in dir not listed in MEMORY.md)

All 29 memory files (excluding MEMORY.md itself) ARE listed in MEMORY.md. No orphans.

MEMORY.md links use **path-style** (`feedback_foo.md`), not `[[slug]]`, so they always resolve via filesystem — they are not part of the `[[slug]]` count.

## Recommended cleanup actions

The unresolved refs are real broken links — they will not resolve if a memory tool walks `name:` fields. The fixes are 1-line edits in the source files. Three options ordered by least to most invasive:

### Option 1 — Fix the link sites (least invasive, recommended)

Replace the 7 distinct broken refs with their canonical equivalents at the call sites:

| Old (in file) | New |
|---|---|
| `[[continuous-pruning]]` | `[[feedback-continuous-pruning]]` |
| `[[no-concurrent-branch-ops]]` | `[[feedback-no-concurrent-branch-ops]]` |
| `[[no-extrapolate]]` | `[[feedback-no-extrapolate]]` |
| `[[persona-test-rectification]]` | `[[feedback-persona-test-rectification]]` |
| `[[label-vs-semantics]]` | `[[feedback-label-vs-semantics]]` |
| `[[pr-branches]]` | `[[feedback-pr-branches]]` |
| `[[reference-first-rule]]` | `[[feedback-references]]` |
| `[[feedback-research-first-failure-protocol]]` | `[[research-first-failure-protocol]]` |
| `[[feedback-test-write-reference]]` | `[[test-write-reference]]` |

Call-site files touched: feedback_continuous_pruning.md, feedback_dotso_arch_check.md, feedback_independent_verification.md, feedback_label_vs_semantics.md, feedback_min_five_agents.md, feedback_persona_test_rectification.md, feedback_persona_time_budgets.md, feedback_post_ship_persona_retest.md, feedback_post_integration_verification.md, feedback_pr_branch_hygiene.md, feedback_pr_branches.md, feedback_pr10a5_autonomous_commit.md, feedback_public_repo_hygiene.md, feedback_research_first_failure_protocol.md, feedback_stall_check.md, feedback_test_write_reference.md, feedback_ui_packaging_sync.md.

### Option 2 — Normalize canonical names (more invasive)

Pick ONE convention (drop or keep `feedback-` prefix in `name:`) and update frontmatter to match. Risk: any external tool / link that currently resolves via the existing canonical name would break. Not recommended — frontmatter is the source of truth and changing it has cascading impact.

### Option 3 — Add aliases (cleanest if supported)

If the memory loader supports an `aliases:` field in frontmatter, add the dropped/added-prefix variant as an alias. Zero call-site edits, both forms resolve. Requires confirming the loader honors aliases; not visible from frontmatter alone.

### Adjacent observation (not a link issue, but pruning-relevant)

MEMORY.md line 11 reads `[Agent floor + orchestrator free](feedback_min_five_agents.md) — current floor=4`, while the file itself opens with "steady-state count must be ≥ 5 concurrent agents at ALL times". The numbers diverge (5 vs 4). Out of audit scope to resolve, but flagging for the next prune pass since `[[continuous-pruning]]` mandates it.
