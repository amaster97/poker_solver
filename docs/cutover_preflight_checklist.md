# Cutover Pre-Flight Checklist (30-Second Scan)

Read this immediately before running `scripts/execute_dual_channel_cutover.sh --execute`.

## Before running

- Working tree clean: `git status --short` shows only `?? V1_GA_CLOSE.md` (office `.docx` artifacts OK)
- On integration branch: `git branch --show-current` returns `integration`
- backup remote reachable: `git ls-remote backup` returns 3 refs (HEAD, main, integration)
- backup/integration matches local: `git rev-parse integration` == `git ls-remote backup refs/heads/integration | cut -f1`
- Dry-run first: `scripts/execute_dual_channel_cutover.sh` (no flag = dry-run)
- v0.6.1 tag reachable from main post-cutover (script patcher closing this gap)

## What you'll see during execution

- Per-step prompts (D / E / F / G / H) with the exact command shown
- Color-coded output: green=OK, yellow=skip, red=error, blue=info
- Step H requires typing literal `DELETE` to confirm

## Stop conditions (abort on any)

- Any test failure
- Unexpected file appears in staging
- backup or origin push fails after 1 retry
- Non-FF merge from integration->main (means main has commits we don't know about)

## Recovery if something breaks mid-cutover

- Local commits + force-pushes are reversible
- `git reflog` shows the path back
- Step H (delete origin/integration) is the only "destructive in spirit" step; commits remain reachable via origin/main (FF-merged from `62c75d5`). Worst case: re-push integration to origin.

## Post-cutover sanity

- `git ls-remote origin` shows only main + tags (no integration ref)
- `git ls-remote backup` shows main + integration + tags
- Visit https://github.com/amaster97/poker_solver/blob/main: STATUS.md + SESSION_END_FINAL.md gone; USAGE.md + DEVELOPER.md visible
