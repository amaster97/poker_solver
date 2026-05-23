# Smoke Test: `scripts/split_main_for_publish.sh`

**Date:** 2026-05-23
**Script:** `/Users/ashen/Desktop/poker_solver/scripts/split_main_for_publish.sh` (15970 bytes, mode `-rwxr-xr-x`)
**Tested by:** Claude (orchestrator-spawned agent)

## Commands Run

| # | Command (cwd) | Purpose | Exit |
|---|---|---|---|
| 1 | `bash scripts/split_main_for_publish.sh` (shared tree, branch `pr-10a.5-conformance`) | Validate safety precondition (refuse non-main HEAD) | **1** |
| 2 | `bash scripts/split_main_for_publish.sh --help` | Verify help text | **0** |
| 3 | `bash scripts/split_main_for_publish.sh --bogus-flag` | Verify unknown-arg rejection | **2** |
| 4 | `bash scripts/split_main_for_publish.sh --dry-run` (shared tree) | Confirm explicit `--dry-run` also blocked off-branch | **1** |
| 5 | `bash scripts/split_main_for_publish.sh` (fresh worktree `/tmp/poker-solver-smoke-test` checked out to `main` at `62c75d5`) | Full dry-run pass | **0** |

Worktree was added via `git worktree add`, script copied in (not yet tracked on `main`), executed, and the worktree was removed cleanly afterward. The shared working tree was never branch-switched.

## Findings (Pass/Fail)

| Check | Result |
|---|---|
| Default mode is `dry-run` (no flag needed) | PASS — `MODE="dry-run"` on line 87 |
| Dry-run header uses non-destructive color (`C_BLUE`) and says "DRY RUN" | PASS — `=== DRY RUN: no changes will be made ===` |
| Refuses to run when HEAD != `main` | PASS — exit 1 with red `[ERROR]` |
| Refuses to run on dirty tree | PASS by inspection (untested directly; `git diff --quiet` gate at line 153) |
| Untracked files ignored (does not see `DEVELOPER.md`/`USAGE.md`/`V1_GA_CLOSE.md` in PR 10a.5 tree) | PASS — only blocks on branch precondition |
| Help text matches runbook (lists `--dry-run`, `--execute`, `-h/--help`) | PASS |
| Unknown flag → exit code 2 with clear error | PASS |
| Reports exactly 2 violators on real `main` (`STATUS.md`, `SESSION_END_FINAL.md`) | PASS — `files that WOULD be untracked: 2` |
| `V1_GA_CLOSE.md` reported as no-op (not tracked on `main`) | PASS — `[INFO]  not tracked (no-op):     V1_GA_CLOSE.md` |
| Lists 6 expected `.gitignore` globs needing addition | PASS — `STATUS*.md`, `SESSION_*.md`, `V*_GA_CLOSE.md`, `V*_MILESTONE*.md`, `wake_up_*.md`, `*_HANDOFF.md` |
| Prints suggested commit message in next-steps footer | PASS in `--execute` mode (heredoc lines 410-417); in dry-run mode it points the user at `--execute` instead, which is acceptable |
| No filesystem side effects in dry-run | PASS — `git status` after run shows only the untracked script copy |
| Math: 107 allowlisted + 2 violators = 109 tracked files (matches `git ls-files \| wc -l`) | PASS |

## Unexpected Behavior / Notes

1. **Suggested commit message only printed in `--execute` mode.** The dry-run footer omits the heredoc commit-message preview and instead tells the user to re-run with `--execute`. The runbook checklist asks "Does it print the suggested commit message at the end?" — strictly, the dry run does **not**. Not a bug, but worth flagging if the user expected a preview without committing.
2. **No `private` remote configured** — script warns but continues (correct behavior per lines 161-169).
3. **Script is currently untracked on `main`** (it lives in the PR 10a.5 working tree, hasn't been merged yet). When the user runs it for real on `main`, it must be present in that branch's tree — either commit it to `main` first, or land PR 10a.5 (or whichever PR ships it) before invoking. Otherwise `bash scripts/split_main_for_publish.sh` will 127 on `main`.

## Verdict

**SAFE-TO-RUN** (when user OKs cutover, and after ensuring the script is committed on `main`).

The script's safety preconditions all fire correctly, dry-run is fully non-destructive, the allowlist math reconciles with the real `main` tree, and the audit-mandated files are correctly identified for untracking. No latent bugs found.
