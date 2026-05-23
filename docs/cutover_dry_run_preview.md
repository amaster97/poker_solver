# Cutover Dry-Run Preview (Steps D-H)

Date: 2026-05-23  
Driver: `scripts/execute_dual_channel_cutover.sh`  
Advisory: `docs/public_cleanup_advisory.md`  
**Verdict: PROCEED-WITH-CAVEATS.** D/E/F/H are clean; **G publishes v0.6.1 as a dangling tag** — its target `a0b1994` is not an ancestor of the cleaned main. User must accept or amend before running G.

## Section 1 — Current state snapshot

| Ref | SHA | Notes |
|---|---|---|
| `main` (local) | `62c75d5` | Equals `origin/main` and `origin/integration`; 0 ahead. |
| `origin/main` | `62c75d5` | 109 tracked files, including STATUS.md + SESSION_END_FINAL.md (leak). |
| `backup/main` | `b83835e0` | GitHub auto-init; no shared history with local. |
| `integration` (local) | `9936d5f` | 8 commits ahead of main (split tooling + planning). |
| `origin/integration` | `62c75d5` | Identical to origin/main (step H target). |
| `backup/integration` | `9936d5f` | Matches local (step C complete). |
| Tag `v0.6.1` (annotated `8386a68`) | -> commit `a0b1994` | Parent chain `62c75d5 -> 67760c7 -> a0b1994`. |
| Tag `v0.6.0` | `8d514a2` | On main history; already on origin. |
| Tag `v1.0.0` | `bbb4395` | On main history; already on origin. |
| `origin` | `github.com/amaster97/poker_solver.git` (public) | 17 refs: 1 main, 1 integration, 9 `pr-*`, 1 `pull/1/head`, v0.6.0 + v1.0.0 tags. |
| `backup` | `github.com/amaster97/poker_solver_private.git` (private) | Only main + integration, no tags yet. |

## Section 2 — Per-step expected effect

**D - split script (--execute on main).** Dry-run from a `/tmp/cutover-preview` worktree at main returned:
- Allowlist hits: **107**
- Will be untracked: **2** — `STATUS.md`, `SESSION_END_FINAL.md`
- `.gitignore` patterns added: **6** — `STATUS*.md`, `SESSION_*.md`, `V*_GA_CLOSE.md`, `V*_MILESTONE*.md`, `wake_up_*.md`, `*_HANDOFF.md`

`V1_GA_CLOSE.md` is listed in the explicit untrack set but is "not tracked (no-op)" on main. Index drops 2 files; `.gitignore` gains 6 lines + 1 header.

**E - commit.** Single commit (message: `chore: clean main - Option C public-channel filter`). Staged diff = `D STATUS.md`, `D SESSION_END_FINAL.md`, `M .gitignore`. After E, local main = `cleanup_commit`, parent `62c75d5`.

**F - push main.**
- `git push origin main` — fast-forward (1 new commit on top of `62c75d5`).
- `git push backup main --force` — force-replaces `b83835e0` (no shared history; auto-init only).

**G - push v0.6.1.** `git push origin v0.6.1` + `git push backup v0.6.1`. **Caveat:** target `a0b1994` is not reachable from cleaned main (`a0b1994 -> 67760c7 -> 62c75d5` is the integration line; cleaned main goes `62c75d5 -> cleanup_commit`). The tag publishes successfully but lands **dangling** on both remotes (visible under Releases; not reachable via `git log main --tags`). v0.6.0 and v1.0.0 are unaffected — they were merged into main via integration FF-merges.

**H - delete `origin/integration`.** `git push origin --delete integration`. Branch ref removed; commit `62c75d5` stays reachable via `origin/main`. Script demands literal `DELETE` even with `--yes`.

## Section 3 — Risk / reversibility

| Step | Blast radius | Recovery |
|---|---|---|
| D | Local index + `.gitignore` | `git restore --staged . && git checkout HEAD -- .gitignore` |
| E | Local commit (unpushed) | `git reset HEAD~1` |
| F (origin) | Public main +1 commit (FF) | `git push origin 62c75d5:main` |
| F (backup) | Overwrites auto-init | Effectively irreversible, no real content lost |
| G | Tag refs added | `git push origin :refs/tags/v0.6.1` (+ backup) |
| H | Removes `origin/integration` ref | `git push origin 62c75d5:refs/heads/integration` |

## Section 4 — Net result after D-H

`git ls-remote origin`:
- `refs/heads/main` -> `cleanup_commit` (new)
- `refs/heads/pr-*` -> 9 stale (unchanged, out of scope)
- `refs/pull/1/head` -> unchanged
- `refs/tags/v0.6.0`, `v1.0.0` -> unchanged
- `refs/tags/v0.6.1` -> **new, dangling**
- **No `refs/heads/integration`**

`git ls-remote backup`:
- `refs/heads/main` -> `cleanup_commit` (force-replaced)
- `refs/heads/integration` -> `9936d5f`
- `refs/tags/v0.6.1` -> new (also dangling here)

## Section 5 — User decision points

1. **Dangling v0.6.1 on origin** — pick one: (a) publish anyway (GitHub Releases handles dangling tags); (b) skip G now, re-tag `cleanup_commit` later; (c) cherry-pick the v0.6.1 changelog onto cleaned main, then re-tag.
2. **Force-push justification (backup/main):** `backup/main` is GitHub's auto-init `b83835e0` only — no user content; force is safe.
3. **H readiness:** advisory reports 0 stars / 0 forks / 0 contributors; no external consumer. Reversible via re-push.
4. **Out of scope:** 9 stale `pr-*` branches on origin (separate sweep).
