# PR 11 follow-up — v1.0.0 docs polish

**Date drafted:** 2026-05-22
**Branch:** `pr-11-library-and-packaging`
**Status:** PRE-STAGED RECIPE. Do **not** auto-run.
**Type:** Doc-only follow-up to the v1.0.0 GA merge.

This is a small, post-GA polish pass on README + STATUS to align tone
with the v1.0.0 GA milestone. **Companion docs:**

- `docs/pr11_prep/commit_pipeline.md` (parent PR 11 pipeline)
- `docs/pr11_prep/commit_message_draft.md` (parent commit body)

---

## 1. Scope

Three files are dirty on `pr-11-library-and-packaging`:

| File | Change | Intent |
|---|---|---|
| `README.md` | line edits, GA tone, v1.0.0 banner refresh, reflow | **in scope** — doc polish |
| `STATUS.md` | header → "v1.0.0 GA HIT", PR table refresh, decision-log update | **in scope** — doc polish |
| `poker_solver/library.py` | (a) clarifying comment on `label` exclusion in `_canonicalize_spot` referencing spec §2.3; (b) improved `LibrarySchemaError` message ("created by a newer poker_solver") | **verify before committing** |

**Verdict on `library.py`:** Both edits are substantive and look
intentional — the comment cements a spec-derived invariant (re-label
is not a new spot), and the error-message rewrite clarifies the
common newer-writer / older-reader case. **Recommend: keep, but
commit it in a *separate* follow-up commit** (not bundled with
README/STATUS), since it touches behaviorally-relevant code (error
text users will see) and deserves its own atomic history entry.

**If `library.py` turns out to be unintentional drift:** revert with
`git checkout -- poker_solver/library.py` before staging.

---

## 2. Recipe (when ready to commit)

**Two-commit variant (recommended):**

```bash
# Commit 1: docs polish
git add README.md STATUS.md
git commit -m "PR 11 follow-up: v1.0.0 docs polish (README + STATUS for GA tone)"

# Commit 2: library.py micro-polish (only if intentional)
git add poker_solver/library.py
git commit -m "PR 11 follow-up: clarify label-exclusion invariant + schema-version error wording"

# Push + integration merge
git push origin pr-11-library-and-packaging
git checkout integration
git merge --no-ff pr-11-library-and-packaging -m "Integration: merge PR 11 follow-up (v1.0.0 docs polish)"
git push origin integration
```

**Single-commit variant (if `library.py` is reverted):**

```bash
git add README.md STATUS.md
git commit -m "PR 11 follow-up: v1.0.0 docs polish (README + STATUS for GA tone)"
git push origin pr-11-library-and-packaging
git checkout integration
git merge --no-ff pr-11-library-and-packaging -m "Integration: merge PR 11 follow-up (v1.0.0 docs polish)"
git push origin integration
```

**Constraint reminder:** no concurrent branch ops (memory rule); do
not switch to `integration` while any agent has the working tree.

---

## 3. Version impact

- **No version bump.** Doc-only polish stays at `v1.0.0`.
- `library.py` edits are also non-API: comment + error-message string
  refinement. No public-surface change → still no bump warranted.
- **No** new tag. v1.0.0 tag already points at the parent PR 11 merge
  commit (`6af3684` → integration `bbb4395` per STATUS).
- If we later decide the schema-version wording is a user-facing
  enough change to merit `v1.0.1`, that decision can be deferred to
  the next minor (post-PR 8/9).

---

## 4. Sequencing

- **Priority:** LOW. Pure cosmetic / tone alignment.
- **Fire time:** anytime — completely independent of PR 8/9/10b/12.
  No agents block on this. Could be deferred to the next session
  without consequence.
- **Recommended slot:** end of current session OR start of next
  session, whichever has spare context. Do not preempt active
  research / solver agents for this.
- **Prerequisites:** PR 11 parent merge to integration must already
  be in (per STATUS: `bbb4395`). Confirmed shipped.

---

## 5. Constraints

- **Read-only / staging only this turn.** No commits, no pushes, no
  branch switches.
- Defer actual firing until user explicitly green-lights.
- Verify `library.py` intent with user (or via spot-check of the
  diff) before bundling — recipe above already isolates it into its
  own commit so a revert-and-redo costs ~10 seconds.
