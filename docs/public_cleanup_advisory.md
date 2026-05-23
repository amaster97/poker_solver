# Public Repo Cleanup Advisory

Date: 2026-05-23  
Scope: remove pre-existing leak on `origin/main` + `origin/integration` at `https://github.com/amaster97/poker_solver.git`  
Hard rule: this is an advisory only. No commands below have been executed.

## Section 1 — Current public exposure

`origin/main` (HEAD = `62c75d5`) tracks 109 files. Two of those are extraneous internal content that should never have been pushed:

- `STATUS.md` — blob `c6be6d6`, 2207 bytes
- `SESSION_END_FINAL.md` — blob `607f2bf`, 1168 bytes

Total leak surface: ~3.3 KB. Per the routing audit, no PII was found: `amaster97@gmail.com` is the user's public GitHub identity (fine on public); `ashen26@gsb.columbia.edu` does not appear in either tracked tree.

`origin/integration` is currently pinned to the same commit `62c75d5` — identical content to `origin/main`. So the leak is mirrored on both public branches.

What is NOT yet leaked (because local `integration` is 7 commits ahead of `origin/integration` and was never pushed):

- 277-file Option C cutover delta (planning + docs scaffolding)
- `PLAN.md`, `USAGE.md`, `DEVELOPER.md`
- `scripts/sync_repos.sh`, `scripts/split_main_for_publish.sh`
- `docs/branch_split_runbook.md`, `docs/routing_check_2026-05-23.md`

These remain local-only and are safe.

Note: `origin` also publishes 9 stale `pr-*` topic branches (e.g. `pr-3-hunl-tree`, `pr-11-library-and-packaging`). These are out of scope for this advisory but worth a separate sweep.

## Section 2 — Recommended sequence

Execute strictly in order. Each step is gated on the previous succeeding.

A. Create `poker_solver_private` on GitHub (web UI, private, no README). Manual step.

B. Wire the backup remote:
   ```
   git remote add backup git@github.com:amaster97/poker_solver_private.git
   git remote -v   # confirm backup appears
   ```

C. Bootstrap planning history into backup before any destructive op on origin:
   ```
   git push -u backup integration
   ```

D. Dry-run, review, then execute the split script:
   ```
   cd /Users/ashen/Desktop/poker_solver
   scripts/split_main_for_publish.sh --dry-run
   # inspect output: must show only STATUS.md + SESSION_END_FINAL.md being untracked
   scripts/split_main_for_publish.sh --execute
   ```

E. Commit the cleaned main locally:
   ```
   git commit -m "chore: clean main — untrack STATUS.md + SESSION_END_FINAL.md (Option C public-channel filter)"
   ```

F. Push cleaned main to both remotes:
   ```
   git push origin main
   git push -u backup main
   ```

G. Push the v0.6.1 tag (and any other release tags not yet on backup):
   ```
   git push origin v0.6.1
   git push backup v0.6.1
   ```

H. Delete `origin/integration` (destructive on remote ref only):
   ```
   git push origin --delete integration
   ```
   Reversible: yes — commit `62c75d5` remains reachable from `origin/main` (main was FF-merged from that commit). Deleting the branch ref does not delete commits. Re-creation is one `git push origin <sha>:refs/heads/integration` away.  
   Side effects: the branch disappears from the public branch list. Current public audience: 0 stars, 0 forks, 0 contributors — no external observers affected.

I. Verify:
   ```
   git ls-remote origin
   ```
   Expected: only `refs/heads/main` (plus the 9 `pr-*` branches, out of scope) and `refs/tags/*`. No `refs/heads/integration`.

## Section 3 — Risk per step

| Step | Blast radius | Reversible? | Time |
|---|---|---|---|
| A | None (private repo creation) | Yes (delete repo) | 1 min |
| B | None (local remote config) | Yes (`git remote remove backup`) | 5 s |
| C | Writes to private mirror only | Yes | ~10 s |
| D dry-run | None | N/A | 5 s |
| D execute | Local working tree only | Yes (`git restore --staged .`) | 5 s |
| E | Local commit only | Yes (`git reset HEAD~1`) | 2 s |
| F | Public-facing — replaces tip of `origin/main` with a clean commit | Reversible via `git push origin <old-sha>:main` if needed | ~10 s |
| G | Public — adds tag ref | Yes (`git push origin :refs/tags/v0.6.1`) | 5 s |
| H | **Destructive on public branch ref.** Requires deliberate user OK. | Yes (commit reachable from main; re-pushable) | 5 s |
| I | Read-only | N/A | 5 s |

Flag: **step H is the only step that mutates a public branch ref destructively.** Pause for explicit go/no-go before running it.

## Section 4 — Order rationale

- C before D-I: planning history (7 local-only commits including the cleanup tooling itself) must live in backup before any destructive op touches origin. If F or H goes wrong, planning history is already off-machine.
- H matters: without it, a future `git push origin --all` or accidental `git push origin integration` re-leaks the 109-file tree (and, if local integration has advanced, the 277-file Option C delta too). Deletion is mechanical safety.

## Section 5 — Alternative to step H

Soft alternative: force-push `origin/integration` to track `origin/main`:
```
git push origin +main:integration
```
The public `integration` branch survives but holds only cleaned content.

Trade-offs:
- The branch name still publicly advertises an internal workflow concept.
- Ongoing maintenance burden: every future push to local `integration` risks landing on `origin/integration` by mistake and re-leaking.
- A future `git push origin integration` from a stale workstation would overwrite the cleaned tip with the local 277-file delta.

Recommendation: prefer step H (delete). The soft alternative is acceptable only if the user has a specific reason to keep the branch name visible.

---

End of advisory. No execution performed.
