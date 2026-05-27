# PR Conflict Resolution — PR 53b

**Date:** 2026-05-24
**Status:** PR 53b open; ship bundle updated; PR #7 (PR 53) pending close-without-merge.

---

## TL;DR

Original **PR 53 (PR #7)** and **PR 54 (PR #9)** conflict at 4 hunks. **PR 53b (PR #14)** rebases PR 53 on top of PR 54 to resolve the conflict. Both original PRs remain open; the v1.7.1 ship bundle now uses PR 53b instead of PR 53. User action: **merge PR 53b, then close PR #7 without merging.**

---

## Why PR 53b exists

When the burst extended through R7-R10, two of the queued PRs landed on overlapping code paths:

- **PR 53 (PR #7)** — queued bundle item touching the renderer-adjacent surface.
- **PR 54 (PR #9)** — the renderer change itself.

Both PRs were opened against `origin/main` (`3843ce7`, v1.7.0). Each is clean against `main` independently, but when stacked together they conflict at **4 hunks** in the renderer-adjacent file(s) PR 53 was edited against — PR 54 rewrites the surrounding context that PR 53 patched.

The `scripts/ship_v1_7_1.sh` bundle script squash-merges in dependency order, but with the 4-hunk overlap there is no clean dependency order that lands both PRs untouched. A rebase is required.

---

## The fix: PR 53b

**Branch:** `pr-53b-rebased-on-54`
**PR number:** #14
**Base:** PR 54's branch (so PR 54 lands first, then PR 53b lands on top with the conflicts resolved in-tree).

PR 53b carries the same intent as PR 53 — the 4 conflicting hunks are resolved against PR 54's renderer-rewritten surface so the change applies cleanly. No semantic changes vs PR 53; only the lines that PR 54 touched are reflowed.

---

## What this means for the ship bundle

The Hybrid v1.7.1 bundle is still **8 PRs**, with the membership updated:

**Before (with conflict):** PR #5, #6, **#7**, #8, #9, #10, #11, #12, #13
**After (resolved):** PR #5, #6, #8, #9, #10, #11, #12, #13, **#14 (PR 53b)**

The ordering in `scripts/ship_v1_7_1.sh` already accounts for the dependency: PR 54 (PR #9) lands before PR 53b (PR #14).

---

## What remains open

- **PR #7 (PR 53)** — remains OPEN on origin as informational. It is superseded by PR 53b in the ship bundle. Do **not** merge PR #7; it will conflict against `main` once PR 54 lands.
- **PR #14 (PR 53b)** — OPEN on origin; this is what the bundle uses.
- **PR #9 (PR 54)** — OPEN on origin; lands before PR 53b in the bundle order.

---

## User action

1. Approve the Hybrid path (per `docs/WELCOME_BACK_USER_2026-05-23.md`).
2. Run `bash scripts/ship_v1_7_1.sh`. The script lands PR 53b (not PR 53).
3. After the v1.7.1 ship completes successfully, **close PR #7 without merging**:
   ```bash
   gh pr close 7 --repo amaster97/poker_solver --comment "Superseded by PR 53b (#14); landed in v1.7.1."
   ```

---

## Verification

- **Dry-run #7** (logged): 100% coverage, 63% cells > 1e-1 — algorithmic-not-labeling; Brown as sanity-check.
- **Dry-run #8** (pending): re-runs the acceptance battery with the conflict-resolved PR 53b in the bundle to verify the final clean state pre-ship.

Dry-run #8 must complete cleanly before `scripts/ship_v1_7_1.sh` fires.

---

## Related docs

- `docs/PR_REVIEW_PREP_2026-05-23.md` — per-PR triage table (now includes PR #14)
- `docs/SIGNON_CHECKLIST.md` — step 2 references the 8-PR bundle with PR 53b
- `docs/WELCOME_BACK_USER_2026-05-23.md` — decision list notes PR 53b acceptance
- `docs/SESSION_TLDR.md` — 60-second TL;DR mentions the conflict + PR 53b
