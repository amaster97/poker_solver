# Strip-and-soften edits applied — 2026-05-23

**Strategy:** strip-and-soften (Option 1 from the public-doc audit).
**Scope:** every user-facing file flagged in `docs/public_doc_content_audit.md`.
**Total edits applied:** 30 across 8 files.

## Per-file breakdown

### `.github/PULL_REQUEST_TEMPLATE.md` (2 edits)
- L3: replaced `PR N from PLAN.md` placeholder with `roadmap PR`.
- L34: replaced the broken `PLAN.md updated...` checkbox with "If the
  change affects a locked design decision, call it out in the PR body."
  External contributors can now satisfy this checkbox.

### `.github/ISSUE_TEMPLATE/feature_request.md` (2 edits)
- L16: dropped the `[PLAN.md](../../PLAN.md)` link; kept the locked-decision
  guidance inline.
- L28: replaced "anything PLAN.md calls out as explicitly out of scope"
  with "anything explicitly out of scope for v1".

### `assets/README.md` (1 edit)
- L100: removed "per PR 11 spec decision 13.6 and PLAN.md hardware
  target"; simplified to "explicitly out of scope for v1.0.0".

### `CONTRIBUTING.md` (3 edits)
- L11: removed the `[PLAN.md](PLAN.md)` bullet; added a one-line note
  summarizing the locked decisions inline (algorithm, abstraction,
  stack range, license).
- L101: dropped the parenthetical `(references/papers/)`.
- L110: changed "change to a locked decision in PLAN.md" to "change to
  a locked design decision".

### `README.md` (8 edits) — at the per-file cap
- Status section: dropped the broken release-notes lines + the
  `[PLAN.md](PLAN.md)` roadmap line.
- Push/fold features: dropped the `docs/pushfold_v1_generation_notes.md`
  reference.
- NiceGUI feature + UI section: dropped both `docs/pr10_prep/` links
  (1x in features list, 2x in UI section); rephrased "PR 10b swaps in
  the real solver" to "a future PR".
- Architecture section: replaced "see PLAN.md section 3" with "see
  DEVELOPER.md" (which is on origin/main).
- Development section: dropped "see PLAN.md section 4 for the full
  validation chain".
- Contributing section: rewrote the `PLAN.md`-referencing sentence to
  point at CONTRIBUTING.md instead and listed the locked decisions
  inline.
- References section (L250 STALE-CLAIM): corrected the gitignore-scope
  claim — the entire `references/` tree is gitignored, not just
  `references/code/`. Now reads "(the entire `references/` tree is
  gitignored)".

### `USAGE.md` (5 edits) — at the per-file cap
- §1 (L29): dropped `Roadmap: [PLAN.md](PLAN.md)`.
- §2 (L39 STALE-CLAIM): clarified distribution channel — `.dmg` is
  attached to the v1.0.0 GitHub Release; local build is still
  documented as an option.
- §4 (L168-169): dropped both `docs/pr10_prep/` spec links; rephrased
  "PR 10a (shipped in v1.0.0) ... PR 10b swaps in" to omit per-PR
  internal naming.
- §7 (L235): dropped "Tracked in [PLAN.md](PLAN.md)".
- §8 (L255-256): replaced both broken refs (`PLAN.md`, never-written
  `docs/release_notes_v1.0.0.md`) with a pointer to `CHANGELOG.md` and
  the v1.0.0 GitHub Release.

### `DEVELOPER.md` (8 edits) — well under cap
- L9: dropped the trailing PLAN.md reference.
- L39: replaced `[references/code/noambrown_poker_solver](references/code/)`
  with the inline name `noambrown/poker_solver`.
- §2 repo tour: replaced the `references/` row with a local-only note;
  removed the `docs/` row entirely.
- §2 references subsection: rewrote intro to note the tree is local-only
  and populated by `setup_references.sh`; removed broken sub-bullets'
  links while preserving the substantive prose.
- §7: rewrote the opening paragraph to describe the reference-first
  rule without linking `references/README.md` or the `_INDEX.md` /
  `_NOTES.md` files; dropped the "If you are unsure where to look"
  follow-up that pointed at those files.
- §8: removed the `references/README.md section 2` reference; kept the
  summary table intact.
- §9 (L241 INTERNAL-LEAK): removed the `docs/autonomous_log.md`
  pointer — softened to "Substantive design decisions are logged with
  date, rationale, and the references consulted" without a link.
- §10: condensed "Where to go next" into a single roadmap paragraph
  + a GitHub-issues pointer; removed all PR-prep / audit-backlog /
  architecture-deep-dive links.

### `CHANGELOG.md` (1 edit)
- L782-794 reference footer: removed dead release URLs for versions
  that were never tagged on origin (v0.5.x, v0.4.0, v0.3.x, v0.2.0,
  v0.1.0, v0.0.1). Kept only `[Unreleased]`, `[1.0.0]`, `[0.6.1]`,
  `[0.6.0]` — confirmed live via `git ls-remote --tags origin`.
- Per the audit's instruction, historical `docs/...` mentions inside
  CHANGELOG release notes (L218, L314, etc.) were left as-is —
  classified NICE-TO-FIX, clearly past-tense, low-impact.

## What was skipped (with reason)

- **CHANGELOG.md historical docs/ references inside release notes** —
  audit classified as NICE-TO-FIX with explicit recommendation to
  leave-as-historical-context. Not touched per the task constraint.
- **README.md L284 (`references/` in License section)** — audit
  classified OK / NICE-TO-FIX; matches the local-only convention now
  that the gitignore-scope claim at L250 is fixed. Left as-is.
- **scripts/*.py and scripts/*.sh docstring refs to docs/...** —
  audit flagged as lower-urgency (code docstrings, not user-facing
  docs); out of scope for the strip-and-soften pass on user-facing
  prose.

## Verification

- `grep -nE 'PLAN\.md|docs/' README.md USAGE.md DEVELOPER.md CONTRIBUTING.md`
  returns no results.
- The only remaining `references/` mentions in README.md are at L241
  (the corrected gitignore-scope note) and L275 (the License section,
  intentional).
- CHANGELOG.md link footer references only v1.0.0, v0.6.1, v0.6.0 —
  all confirmed live on `origin`.

## Verdict

**PUBLIC-DOCS-CLEAN-FOR-NEXT-SYNC**
