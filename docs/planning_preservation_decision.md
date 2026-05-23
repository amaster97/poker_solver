# Planning Preservation: Decision Brief

## Discovery

`docs/` (85 entries: PR prep, audits, `autonomous_log.md`, etc.) and `PLAN.md`
are currently in `.gitignore`. They live on disk only — no git history, no
remote backup, no blame trail. The "dual-channel" model (main = public,
integration = internal) currently does nothing: integration is identical to
main at `62c75d5`. The just-authorized private mirror would clone the same
109 public files and add zero planning preservation.

## Options

**A — Status quo (keep `docs/` gitignored).** Planning stays on disk only.
No version history of how `PLAN.md` evolved across PRs. Backup depends on
Time Machine. Mental model is trivially simple. The private mirror is
pointless — buys nothing the public repo doesn't already give.

**B — Dual-channel (track `docs/` on integration only).** Remove `docs/` +
`PLAN.md` from `.gitignore`. Commit them to integration only. Keep main
clean via `scripts/split_main_for_publish.sh` or `git rm --cached` at merge.
Push integration to private mirror; origin still gets main only. Planning
gains full history, blame, revert, multi-machine sync. Cost: two remotes,
two divergent trees, discipline required at every integration→main merge.

**C — Single private mirror, track `docs/` everywhere on integration.**
Remove `docs/` from `.gitignore`. Commit to integration. Push integration
to a private remote (`backup` or similar) that mirrors *everything*
including docs. Public `origin/main` stays clean because main never gets
the docs commits — the split script enforces that on merge. Same end-state
as B, but framed as "private remote is the full archive, public remote is
the curated subset" — one less conceptual axis to track.

## Recommendation

**Option C.**

1. **Lowest maintenance for a non-maintainer.** GSB / Python-strong user
   wants to *use* the solver, not babysit branch topology. C collapses
   "what goes where" to one rule: integration = full truth, main = public
   subset. B requires remembering which remote gets which branch.
2. **Actually preserves "for ourselves."** Without tracking `docs/` in git,
   the planning corpus is one disk failure from gone. C puts 85 planning
   docs under version control with a private remote — the stated goal of
   the mirror authorization.
3. **Public repo stays clean by construction.** The split script already
   exists. C reuses it. Main on origin never sees `docs/`, so public
   hygiene is mechanically enforced, not discipline-dependent.

## Next steps if C is chosen

1. Create private GitHub repo (e.g., `poker-solver-private`).
2. Add as remote: `git remote add backup <url>`.
3. Remove `docs/` and `PLAN.md` lines from `.gitignore` on integration branch.
4. `git add docs/ PLAN.md && git commit` on integration.
5. `git push backup integration` (and `backup main` for symmetry).
6. Confirm `scripts/split_main_for_publish.sh` strips `docs/` before any
   integration→main merge destined for `origin`.
7. Document the rule in `PLAN.md`: "docs/ tracked on integration only;
   origin/main never receives docs/."
