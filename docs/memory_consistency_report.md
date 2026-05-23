# Memory Consistency Report — 2026-05-23

Cross-checked four memory entries created/edited today plus `MEMORY.md` index.

## Verdict: CONTRADICTIONS-FOUND (one resolved in place)

## Pair-by-pair findings

### 1. `public_repo_hygiene` + `dual_remote_workflow` — MINOR-DRIFT (resolved)

Both describe the same dual-channel model. Routing rules match:
- `origin` = public, `main` only — hygiene line 49, dual-remote line 12.
- `private` = backup, `integration` + `main` — hygiene line 49, dual-remote line 13.
- "Never push `integration` to `origin`" — hygiene line 49, dual-remote line 14.

**Contradiction (resolved):** hygiene line 49 stated the private remote was "not yet created as of 2026-05-23", but `github-auth-setup` line 22 references "the 23 MB pack to `poker_solver_private` today" — i.e., the remote exists and has been pushed to. Surgical edit applied to line 49 to read "exists as of 2026-05-23 — see [[github-auth-setup]] for naming/auth".

### 2. `dual_remote_workflow` + `github_auth` — MINOR-DRIFT

Push commands in dual-remote (`git push private integration`, `git push origin main`) work given the auth setup: HTTPS + osxkeychain + persistent `http.postBuffer=500 MB` covers both remotes.

**Naming drift (recommend only, no edit):** auth file refers to the private remote as `poker_solver_private` (the repo name, line 22) and `backup` (example, line 45); dual-remote uses the alias `private`. Not a contradiction — these are remote *names* (user's choice) vs. *repo* names — but recommend a single one-line note in `github-auth-setup` clarifying "remote alias is `private` per dual-remote-workflow" to lock the naming.

### 3. `pr10a5_autonomous_commit` + `public_repo_hygiene` — CONSISTENT

Cleanly separated layers:
- Autonomous-commit (PR 10a.5 memory line 10, 16) covers *commit/merge/tag/CHANGELOG on integration* without explicit OK.
- HOLD-default (hygiene line 37) covers *push to remote*.

Autonomous-commit memory line 16 explicitly carves out: "Push to origin still requires explicit user OK". The two rules compose without conflict.

### 4. All four files + `MEMORY.md` — CONSISTENT

Every memory file has a pointer in `MEMORY.md`:
- `feedback_public_repo_hygiene.md` — line 14
- `feedback_dual_remote_workflow.md` — line 15
- `feedback_pr10a5_autonomous_commit.md` — line 19
- `reference_github_auth.md` — line 20

## Recommended fixes (drift-only, not applied)

1. `reference_github_auth.md`: add one line clarifying that the remote alias used in `dual-remote-workflow` is `private` (repo name is `poker_solver_private`). Locks naming.

## Resolved in this pass

- `feedback_public_repo_hygiene.md` line 49 updated: "not yet created" replaced with "exists as of 2026-05-23 — see [[github-auth-setup]] for naming/auth".
