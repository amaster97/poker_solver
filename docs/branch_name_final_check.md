# Branch-name final sanity pass — commit_message_draft + commit_pipeline docs

**Date:** 2026-05-22
**Scope:** Final read-only sweep across `docs/prN_prep/commit_message_draft*.md` and `docs/prN_prep/commit_pipeline*.md` for branch-name drift against the canonical list.
**State at run-time:** PR 7 commit pipeline IS in flight (`pr-7-noambrown-diff` checked out, working tree dirty). Per constraint, all patches deferred; this doc records findings only.

## Canonical names (per task brief)

- `pr-4.5-audit-debt-sweep`
- `pr-6-rust-hunl-port`
- `pr-7-noambrown-diff`
- `pr-8-neon-simd-pcs`
- `pr-9-hunl-preflop`
- `pr-10a-ui-mock-first`
- `pr-10b-ui-real-solver`
- `pr-11-library-and-packaging`
- `pr-12-three-handed-stretch`

## Files audited (14 total)

```
docs/pr5_prep/commit_message_draft.md
docs/pr6_prep/commit_message_draft.md
docs/pr6_prep/commit_pipeline_readiness.md
docs/pr6_prep/commit_pipeline_steps.md
docs/pr7_prep/commit_message_draft.md
docs/pr7_prep/commit_pipeline_readiness.md
docs/pr7_prep/commit_pipeline_v2.md
docs/pr8_prep/commit_message_draft.md
docs/pr8_prep/commit_pipeline.md
docs/pr9_prep/commit_message_draft.md
docs/pr10_prep/commit_message_draft_10a.md
docs/pr10_prep/commit_message_draft_10b.md
docs/pr11_prep/commit_message_draft.md
docs/pr12_prep/commit_message_draft.md
```

## Unique branch tokens found

`pr-3-hunl-tree`, `pr-3.5-pushfold`, `pr-4-card-abstraction`, `pr-5-hunl-postflop-solve` (all closed PRs — fine), `pr-6-hunl-rust-port` (DRIFT — see below), `pr-6-rust-hunl-port` (canonical), `pr-7-noambrown-diff` (canonical), `pr-8-neon-simd-pcs` (canonical), `pr-9-hunl-preflop` (canonical), `pr-10a-ui-mock-first` (canonical), `pr-10b-ui-real-solver` (canonical), `pr-11-library-and-packaging` (canonical), `pr-12-three-handed-stretch` (canonical).

`pr-4.5-audit-debt-sweep` is not referenced in this doc set (PR 4.5 already closed; not expected in these files).

## Known drift patterns — confirmed clean

| Bad pattern | Hits in scope | Verdict |
| --- | --- | --- |
| `pr-8-simd-layout-pcs` | 0 | CLEAN |
| `pr-6-rust-hunl-postflop` | 0 | CLEAN |
| `pr-11-library-packaging` (missing `-and-`) | 0 | CLEAN |
| `pr-12-three-handed` (missing `-stretch`) | 0 | CLEAN |

(Note: these bad patterns DO still appear in `docs/pr_launch_runbook.md` and `docs/roadmap_status_2026-05-22.md` — but those are outside the scope of this pass. Flag for a separate non-commit-pipeline sweep.)

## DRIFT FOUND: `pr-6-hunl-rust-port` typo

Canonical is `pr-6-rust-hunl-port` (verified — `git worktree list` confirms `pr-6-rust-hunl-port` was the actual branch). The typo swaps `rust-hunl` to `hunl-rust`.

| File | Line | Context | Action class |
| --- | --- | --- | --- |
| `pr6_prep/commit_message_draft.md` | 225 | `Branch: pr-6-hunl-rust-port (off integration tip post-PR-5).` | STALE TEXT — patch to `pr-6-rust-hunl-port` |
| `pr6_prep/commit_pipeline_steps.md` | 3 | Audience header: `running PR 6's commit on \`pr-6-hunl-rust-port\`` | STALE INSTRUCTION — patch |
| `pr6_prep/commit_pipeline_steps.md` | 11 | Step 0 checkbox: `Branch: \`pr-6-hunl-rust-port\` is checked out` | STALE INSTRUCTION — patch |
| `pr6_prep/commit_pipeline_steps.md` | 88 | Step 2 bash comment: `# From repo root, on pr-6-hunl-rust-port.` | STALE INSTRUCTION — patch |
| `pr6_prep/commit_pipeline_readiness.md` | 10 | `> \`pr-6-hunl-rust-port\`; the actual branch checked out is` | DRIFT NOTE (intentional) — leave |
| `pr6_prep/commit_pipeline_readiness.md` | 73 | `# 4. Push the PR 6 branch (note: branch name in tree is pr-6-rust-hunl-port, NOT pr-6-hunl-rust-port as the checklist text says — confirm before push)` | DRIFT NOTE (intentional) — leave |
| `pr6_prep/commit_pipeline_readiness.md` | 130 | `order" all reference \`pr-6-hunl-rust-port\`; the local branch is` | DRIFT NOTE (intentional) — leave |
| `pr6_prep/commit_pipeline_readiness.md` | 170 | `Branch-name drift between checklist (\`pr-6-hunl-rust-port\`) and actual branch (\`pr-6-rust-hunl-port\`)` | DRIFT NOTE (intentional) — leave |

`commit_pipeline_readiness.md` is a meta dashboard whose POINT is to document the drift it observed; rewriting both halves of its comparison would destroy the note. Leave as-is.

The 4 STALE entries (`commit_message_draft.md:225`, `commit_pipeline_steps.md:3,11,88`) are the only items that need patching.

## Verdict on Branch lines in commit_message_draft files (Branch: header sweep)

| PR | File | Branch: line | Canonical? |
| --- | --- | --- | --- |
| 5 | `pr5_prep/commit_message_draft.md:133` | `pr-5-hunl-postflop-solve` | n/a (closed) |
| 6 | `pr6_prep/commit_message_draft.md:225` | `pr-6-hunl-rust-port` | **DRIFT** |
| 7 | `pr7_prep/commit_message_draft.md:159` | `pr-7-noambrown-diff` | OK |
| 8 | `pr8_prep/commit_message_draft.md:251` | `pr-8-neon-simd-pcs` | OK |
| 9 | `pr9_prep/commit_message_draft.md:236` | `pr-9-hunl-preflop` | OK |
| 10a | `pr10_prep/commit_message_draft_10a.md:257` | `pr-10a-ui-mock-first` | OK |
| 10b | `pr10_prep/commit_message_draft_10b.md:134` | `pr-10b-ui-real-solver` | OK |
| 11 | `pr11_prep/commit_message_draft.md:293` | `pr-11-library-and-packaging` | OK |
| 12 | `pr12_prep/commit_message_draft.md:229` | `pr-12-three-handed-stretch` | OK |

## Recommended patches (DEFERRED — PR 7 in flight)

Orchestrator should apply these AFTER PR 7 commit pipeline reports back:

```bash
# 1. commit_message_draft.md (PR 6)
#   line 225: "pr-6-hunl-rust-port" -> "pr-6-rust-hunl-port"

# 2. commit_pipeline_steps.md (PR 6)
#   line 3:  "pr-6-hunl-rust-port" -> "pr-6-rust-hunl-port"
#   line 11: "pr-6-hunl-rust-port" -> "pr-6-rust-hunl-port"
#   line 88: "pr-6-hunl-rust-port" -> "pr-6-rust-hunl-port"
```

Safe to use `Edit` tool with `replace_all=false` on each line (each occurrence's surrounding context is unique enough). A single `replace_all=true` on `pr6_prep/commit_pipeline_steps.md` (3 occurrences, all stale) is also safe because every instance of the typo in that file is stale-instructional, not drift-documentation.

DO NOT `replace_all` on `commit_pipeline_readiness.md` — the typo is load-bearing documentation there. Leave it untouched.

## Cross-doc note (out of scope, flag only)

Forward-canonical drift still exists in non-commit-pipeline docs:
- `docs/pr_launch_runbook.md` lines 270, 296, 341, 355 still use old names (`pr-6-rust-hunl-postflop`, `pr-8-simd-layout-pcs`, `pr-11-library-packaging`, `pr-12-three-handed`).
- `docs/roadmap_status_2026-05-22.md` lines 64, 66, 69, 70 same.

Recommend a separate cleanup pass on those once orchestrator has cycles; they don't block any in-flight commit pipeline.
