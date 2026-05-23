# Cutover Execution Runbook

Date: 2026-05-23
Driver script: `scripts/execute_dual_channel_cutover.sh`
Source advisory: `docs/public_cleanup_advisory.md` (steps C2-H)
Patched: 2026-05-23 to add step C2 (integration -> main FF-merge), closing the v0.6.1 dangling-tag gap flagged in `docs/cutover_dry_run_preview.md`.

## When to run

Run this script **exactly once**, after steps A-C of the advisory are complete:

- **A.** Private repo `poker_solver_private` exists on GitHub.
- **B.** Local `backup` remote is wired (`git remote add backup git@github.com:amaster97/poker_solver_private.git`).
- **C.** `git push -u backup integration` has succeeded (planning history is mirrored off-machine).

Pre-flight in the script will refuse to start if any of those are missing.

After cutover, routine maintenance uses `scripts/sync_repos.sh`, not this script.

## The sequence in plain English

1. **Pre-flight.** Confirm you are on `integration` with a clean tree, both remotes configured, and `backup/integration` already matches your local integration HEAD.
2. **Step C2 (NEW).** Script verifies `main` is at the expected `62c75d5` and `integration` is at `9936d5f` (or a descendant), then switches to `main` and runs `git merge --ff-only integration`. This brings the 8 integration commits (PR 10a.5 + planning) onto main's line so the `v0.6.1` tag (target `a0b1994`) is reachable from `origin/main` after cutover — closing the dangling-tag gap flagged in `docs/cutover_dry_run_preview.md`. Local-only; nothing is pushed yet.
3. **Step D.** With HEAD already on `main`, the script runs `scripts/split_main_for_publish.sh --execute`. That helper untracks `docs/`, `PLAN.md`, `STATUS.md`, `SESSION_END_FINAL.md`, and any other files not on the allowlist (the integration FF-merge brought ~283 internal files onto main's tree; the allowlist drops it back to ~109). It also appends session-artifact globs to `.gitignore`. Changes are staged, not committed.
4. **Step E.** Script commits the staged cleanup with a fixed message (`chore: clean main - Option C public-channel filter`). The cleanup commit sits on top of the FF-merged main HEAD.
5. **Step F.** Pushes cleaned `main` to:
   - `origin` (public GitHub) — a normal forward push of 9 new commits (the 8 FF-merged integration commits + the cleanup commit) on top of the current `origin/main` at `62c75d5`.
   - `backup` (private mirror) — `--force` is required because `backup/main` currently holds GitHub's auto-created initial commit (`b83835e0...`), which has no shared history with local main.
6. **Step G.** Pushes the `v0.6.1` tag to both remotes. The tag is now reachable from `main` (since step C2 brought its target `a0b1994` onto main's line) — no longer a dangling tag.
7. **Step H. (Destructive.)** Deletes `origin/integration`. Mandatory confirmation: you must type the literal string `DELETE`. Commits remain reachable from `origin/main` (integration HEAD is now on main's line via the FF-merge), so this is reversible by re-pushing the SHA to a new branch ref.

Each of C2 / D / E / F / G prompts y/N before acting. `--yes` skips those prompts but **never** skips H — H is always interactive and always demands `DELETE`.

## What "success" looks like

After the script finishes cleanly:

```
$ git ls-remote origin
<cleanup_sha>  refs/heads/main             # FF-merged integration + cleanup commit on top
<a0b1994>      refs/tags/v0.6.1            # REACHABLE from origin/main (via step C2)
<sha>          refs/heads/pr-3-hunl-tree   # 9 stale pr-* branches: out of scope
... (other pr-* branches)
# NO refs/heads/integration

$ git ls-remote backup
<cleanup_sha>  refs/heads/main
<9936d5f>      refs/heads/integration
<a0b1994>      refs/tags/v0.6.1

$ git log --oneline main | head -3
<cleanup_sha>  chore: clean main - Option C public-channel filter
9936d5f        docs: routing check report (2026-05-23)
c50f4dd        scripts: add split_main_for_publish.sh (Option C public-channel filter)
# ... earlier integration commits, then 62c75d5 (pre-cutover origin/main)

$ git ls-files | grep -E '^(docs/|PLAN\.md|STATUS\.md|SESSION_END_FINAL\.md)'
# (empty — all internal artifacts untracked from the index on main)
```

You should be left on `main` locally with a clean tree (no `docs/`, no `PLAN.md`, no `STATUS.md`, no `SESSION_END_FINAL.md` tracked; working-tree copies preserved). The `v0.6.1` tag points to a commit reachable via `git log main`.

## Failure recovery per step

| Step | Symptom | Recovery |
|---|---|---|
| Pre-flight | Pre-req missing (no `backup`, dirty tree, wrong branch, `backup/integration` stale) | Script aborts before changes. Fix the named pre-req and re-run. |
| C2 | SHA sanity check failed (main not at `62c75d5`, integration not at/descendant of `9936d5f`) | Script aborts BEFORE branch switch. The runbook snapshot has drifted from reality — re-audit, update `EXPECTED_MAIN_SHA` / `EXPECTED_INTEGRATION_SHA` in the script, and re-run. |
| C2 | `git merge --ff-only integration` failed | Either integration diverged from main or there are local commits on main. Inspect `git log --oneline main..integration` and `git log --oneline integration..main`. If main has unique commits, decide whether to discard them (`git reset --hard 62c75d5`) or rebase before re-running. |
| D | `split_main_for_publish.sh` failed | Script left you on `main` (already FF-merged from C2). Inspect `git status`. Either re-run after fixing, or `git restore --staged . && git checkout HEAD -- .gitignore` to undo the split's staged changes (the FF-merge stays — to undo that too, `git reset --hard 62c75d5`). |
| E | Commit failed (nothing staged, hook rejection) | If nothing staged, step D didn't take effect — re-run D. If hook rejected, fix the cause, then `git add -u && git commit -m "chore: clean main - Option C public-channel filter"` manually, then re-run from step F. |
| F | `origin` push rejected | Likely diverged. Inspect `git fetch origin && git log --oneline origin/main..main`. If only the FF-merged commits + cleanup are new, `git push origin main` directly. If `origin/main` advanced unexpectedly, investigate before forcing. |
| F | `backup --force` push rejected | Confirm `backup` URL with `git remote get-url backup`; check SSH key. If `backup` was deleted server-side, recreate the repo and re-run. |
| G | Tag push rejected as existing | Idempotent — the script skips if the remote already has the tag at the same SHA. If SHAs disagree, decide whether to overwrite (`git push origin v0.6.1 --force`) or rename the local tag. |
| H | Refused with `DELETE` not typed | Intentional. Re-run the script; it will skip C2-G (idempotent) and ask for `DELETE` again. |
| H | Push --delete rejected | Branch may already be gone (the script tries to detect this) or protected. Check GitHub branch protection settings. |

No step performs automatic rollback. The script's philosophy is: stop on failure, leave state for inspection, let you decide. Commits (steps D and E) are local-only until step F runs, so the blast radius before step F is fully contained.

## Quick reference

```
# Dry-run (the default) — see exactly what would happen:
scripts/execute_dual_channel_cutover.sh

# Execute interactively (recommended):
scripts/execute_dual_channel_cutover.sh --execute

# Execute auto-confirming C2-G (H still prompts for DELETE):
scripts/execute_dual_channel_cutover.sh --execute --yes
```
