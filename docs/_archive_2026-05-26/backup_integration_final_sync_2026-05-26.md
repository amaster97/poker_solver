# Final `backup/integration` Sync — 2026-05-26

Sync of the private mirror's full-state branch (`backup/integration`) with
`origin/main` after ~20+ PR merges had landed since the prior sync earlier
this session.

## Pre-sync state

- Commits on `origin/main` **not** on `backup/integration`: **14**
- Commits on `backup/integration` **not** on `origin/main`: **40**
  (planning/audit docs, R6-R11 investigation cascade, v1.7.0/v1.7.1 prep,
  pre-PR-1 / v1.4.0 / v1.3.2 historical commits — preserved for archaeology)

Top of `origin/main` before sync: `533cb8e` (PR #63 — a83 supersede banner)
Top of `backup/integration` before sync: `daab5f5` (prior session's merge)

## Procedure executed

1. Created worktree: `git worktree add /tmp/integration-sync-final backup/integration`
   → detached at `daab5f5`.
2. Ran `git merge origin/main` in the worktree.
3. Conflicts encountered: **2 add/add** (both in `docs/`).
4. Resolved both with `git checkout --theirs` (see Conflicts section).
5. Created merge commit with default message: **`71a1349`** —
   `"Merge remote-tracking branch 'origin/main' into HEAD"`.
6. Pushed to `backup/integration` via fast-forward
   (`daab5f5..71a1349  HEAD -> integration`).
7. Removed worktree.

No force-push required; clean fast-forward push.

## Conflicts encountered + resolutions

| File | Type | Resolution | Reason |
|------|------|------------|--------|
| `docs/a83_deep_cap_root_cause_investigation.md` | add/add | `--theirs` (origin/main) | `533cb8e` (PR #63) adds a supersede banner correcting a math error in §2(d). The origin/main version is strictly newer and contains the corrected status. The integration-side version was an earlier draft without the correction. No unique content lost. |
| `docs/v1_6_1_engine_ship_plan_final.md` | add/add | `--theirs` (origin/main) | `a5be2be` (PR #50) adds a "HOLD LIFTED" banner reflecting that v1.6.1 fixes were folded into v1.8.0. The integration version lacked this status update. No unique planning content lost. |

Both conflicts were status-banner additions on docs that exist in both
branches; the origin/main side strictly supersedes (more current and
authoritative). No semantic differences in body content required manual
merging.

No conflicts in code files. Code changes (CHANGELOG, README, USAGE,
crates/cfr_core/*, poker_solver/*) auto-merged cleanly.

## Post-sync verification

- `git log --oneline backup/integration..origin/main | wc -l` → **0**
  (backup/integration now contains all of origin/main).
- `git log --oneline origin/main..backup/integration | wc -l` → **41**
  (40 planning archaeology commits + new merge commit `71a1349` preserved).
- `git push backup main` → `Everything up-to-date`. `backup/main` SHA
  matches `origin/main`: `533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d`.

## Final state

| Branch | SHA | Status |
|--------|-----|--------|
| `origin/main` | `533cb8e` | Public, current |
| `backup/main` | `533cb8e` | Private mirror, matches origin/main |
| `backup/integration` | `71a1349` | Private mirror, merge of origin/main into prior integration head; preserves 41 unique commits for archaeology |

Worktree cleaned up (`/tmp/integration-sync-final` removed). No outstanding
remote divergence.
