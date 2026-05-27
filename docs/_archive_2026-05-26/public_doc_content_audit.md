# Public-Facing Doc Content Audit (post-dual-channel-cutover)

**Date:** 2026-05-23
**Scope:** every file tracked on `origin/main`, focus on user-facing docs.
**Reference state:** `git ls-tree --name-only origin/main` (top of audit) —
`docs/`, `PLAN.md`, `references/`, `STATUS.md`, `SESSION_*.md`, `wake_up_*.md`,
`V*_GA_CLOSE.md`, `autonomous_log.md` are all absent on `origin/main`.

## Verdict

**NEEDS-USER-REVIEW.** Total findings: **35 BROKEN-LINK + 1 INTERNAL-LEAK + 2 STALE-CLAIM = 38**.
This is far beyond the "10 small / 5 substantial" silent-rewrite ceiling.
**Zero edits applied.** Recommendations below; user (or a dedicated rewrite agent)
decides on the policy (delete vs. soften vs. point at GitHub Releases vs. ship as-is).

## Policy question the user should answer first

Three doc-content strategies are viable on public origin/main:

1. **Strip-and-soften.** Remove every `PLAN.md` / `docs/` / `references/` link
   from public docs; replace with prose like "see project roadmap on the
   maintainer's planning channel" or simply drop the cross-reference. Most
   conservative; biggest churn.
2. **Re-anchor.** Move the high-value content (push/fold notes, release notes,
   PR 10 specs) onto `origin/main` itself under e.g. `docs/release_notes/`,
   then keep the links. This reverses part of the cutover for content the
   user wants public.
3. **Ship as-is with a top-of-README disclaimer.** "Links into `PLAN.md` /
   `docs/` are maintainer-internal references; the public roadmap lives in
   GitHub Issues / Releases." Lowest churn; weakest UX.

Without that decision, I can't pick the right fix surgically — every option
rewrites different prose. Hence: report-only.

## Findings by file

### README.md (12 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 20 | `docs/release_notes_v0.3.md` — not on origin/main | BROKEN-LINK |
| 21 | `docs/release_notes_v0.3.1.md` — not on origin/main | BROKEN-LINK |
| 22 | `PLAN.md` (Roadmap) — not on origin/main | BROKEN-LINK |
| 66 | `docs/pushfold_v1_generation_notes.md` — not on origin/main | BROKEN-LINK |
| 85 | `docs/pr10_prep/` — not on origin/main | BROKEN-LINK |
| 197-198 | `docs/pr10_prep/pr10a_spec.md`, `docs/pr10_prep/pr10b_spec.md` | BROKEN-LINK |
| 211 | `PLAN.md` section 3 (architecture pointer) | BROKEN-LINK |
| 234 | `PLAN.md` section 4 (validation chain) | BROKEN-LINK |
| 241 | `PLAN.md` (locked decisions pointer in Contributing section) | BROKEN-LINK |
| 250 | "kept local under `references/` (gitignored at `references/code/`)" — `.gitignore` line 44 ignores the entire `references/` tree, not just `code/`. The README's claim is inaccurate. | STALE-CLAIM |
| 284 | `references/` reference in License section is OK (matches the local-only convention) | NICE-TO-FIX |

### USAGE.md (5 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 29 | `PLAN.md` (Roadmap pointer) | BROKEN-LINK |
| 168-169 | `docs/pr10_prep/pr10a_spec.md`, `docs/pr10_prep/pr10b_spec.md` | BROKEN-LINK |
| 235 | `PLAN.md` (under "What's coming") | BROKEN-LINK |
| 255 | `PLAN.md` (Getting help → Roadmap) | BROKEN-LINK |
| 256 | `docs/release_notes_v1.0.0.md` — does not exist even locally; would-be-shipped release notes were never written | BROKEN-LINK |

### DEVELOPER.md (13 BROKEN-LINK + 1 INTERNAL-LEAK)

| Line | Issue | Class |
|---|---|---|
| 9 | `PLAN.md` (strategic roadmap pointer) | BROKEN-LINK |
| 39 | `references/code/noambrown_poker_solver` link | BROKEN-LINK |
| 60 | "References" table row pointing at `references/` | BROKEN-LINK |
| 63 | "docs/" table row — "Per-PR prep folders, audit reports, release notes" | BROKEN-LINK |
| 90, 92-94 | `references/papers/`, `references/code/`, `references/blog/`, `references/products/` — entire references-tour subsection points at gitignored content | BROKEN-LINK (x4) |
| 201 | `references/README.md` (topic-to-file index) | BROKEN-LINK |
| 209-210 | `references/papers/_INDEX.md`, `references/code/<repo>/_NOTES.md` | BROKEN-LINK |
| 216 | `references/README.md` section 2 | BROKEN-LINK |
| 241 | `docs/autonomous_log.md` ("Per-decision audit trail") — this is the internal session log. **Public docs should not point at it.** | INTERNAL-LEAK |
| 248 | `PLAN.md` (strategic roadmap) | BROKEN-LINK |
| 252-253 | `docs/<pr>_prep/`, `docs/pr8_prep/`, `docs/pr9_prep/` (Where to go next) | BROKEN-LINK |
| 254 | `docs/audit_followup_backlog.md` ("Good first-issue source") | BROKEN-LINK |
| 257 | `docs/architecture.md` ("deeper architectural reference") | BROKEN-LINK |

### CONTRIBUTING.md (3 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 11 | `PLAN.md` (locked decisions) | BROKEN-LINK |
| 101 | `references/papers/` (Reference-first rule) | BROKEN-LINK |
| 110 | `PLAN.md` ("locked decision in PLAN.md") | BROKEN-LINK |

### CHANGELOG.md (many `docs/` references, all in HISTORICAL entries)

Lines 218, 314, 337, 375, 377, 526, 552, 594, 639, 704, 707, 709, 743, 770 reference
`docs/...` files that aren't on origin/main. Classification: **NICE-TO-FIX**.
Rationale: these are historical breadcrumbs from past releases. A user reading
the CHANGELOG won't expect every cross-reference to resolve — they're
contextual notes. The CHANGELOG is the wrong place to chase down audit reports
anyway. **Recommend: leave as-is, OR do a single Edit pass replacing
`` `docs/...` `` mentions with prose (e.g. "per the PR audit prompt") that
doesn't read as a link.**

Line 743 has a meta-claim: "Internal repo hygiene: `PLAN.md` and `docs/`
untracked (kept local as decision log / author-specific notes; not appropriate
for an external contributor's clone)." This is actually now ACCURATE post-cutover —
keep.

### .github/PULL_REQUEST_TEMPLATE.md (2 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 3 | `` `PLAN.md` `` ("PR N from PLAN.md") | BROKEN-LINK |
| 34 | "`PLAN.md` updated if a locked decision changed" — checkbox an external contributor can't satisfy because `PLAN.md` isn't in their clone | BROKEN-LINK |

### .github/ISSUE_TEMPLATE/feature_request.md (2 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 16 | `[\`PLAN.md\`](../../PLAN.md)` | BROKEN-LINK |
| 28 | "anything `PLAN.md` calls out as explicitly out of scope" | BROKEN-LINK |

### assets/README.md (1 BROKEN-LINK)

| Line | Issue | Class |
|---|---|---|
| 100 | "per PR 11 spec decision 13.6 and PLAN.md hardware target" | BROKEN-LINK |

### scripts/*.sh / scripts/*.py (in-source docstrings)

- `scripts/batch_solve.py` L12, L27 — points at `docs/pr11_prep/pr11_spec.md`. **BROKEN-LINK**, but in a code docstring not a user-facing doc; lower urgency.
- `scripts/generate_pushfold_charts.py` L24, L749 — points at `docs/pushfold_v1_generation_notes.md`. **BROKEN-LINK**.
- `scripts/split_main_for_publish.sh` — references `docs/repo_audit.md`, `docs/branch_split_runbook.md` throughout (L9, 175, 186, 283, 315, 416-417). **BROKEN-LINK** but this script is itself the cutover tool; meta-self-reference. Lower urgency.
- `scripts/build_noambrown.sh`, `scripts/setup_references.sh` — reference `references/...`. Functionally correct (they create / use the local references tree); leave as-is.

### Stale forward-looking claims (STALE-CLAIM)

| File | Line | Quote | Verdict |
|---|---|---|---|
| README.md | 11 | "v1.0.0 released 2026-05-22 — GA milestone" | OK; today is 2026-05-23, milestone is in the past. |
| USAGE.md | 27 | "v1.0.0 (2026-05-22) is the first end-user-shippable artifact" | OK. |
| USAGE.md | 39 | "Distribution channel (web download vs GitHub Release) is TBD; for now, build it locally" | STALE-CLAIM if a Release has since been cut. Verify against `gh release list` before fixing. |

No "EOD" / "by end of day" / "will be done" claims survived.

### Stale GitHub URLs (BROKEN-LINK check)

CHANGELOG.md tail (L782-794) — version-compare URLs at `github.com/amaster97/poker_solver/...`.
These point at GitHub release tags. Whether they resolve depends on:
- Was the GitHub repo published under `amaster97`? (User's GitHub handle is `amaster97`, but git remote `origin` should be checked.)
- Were v1.0.0, v0.6.1, etc. release tags actually pushed?

**Recommendation: verify with `gh api repos/amaster97/poker_solver/releases` before declaring these stale.** Not classifying — needs ground truth.

### Stale absolute paths

None found. (`grep -rn '/Users/ashen' README.md USAGE.md DEVELOPER.md CHANGELOG.md CONTRIBUTING.md assets/ .github/` returned no results.)

## Edits applied

**Zero.** Per "hard constraints" the edit budget ceiling is 10-small / 5-substantial.
The audit found 35+ BROKEN-LINK items spanning 6 files and a directory-tour
section in DEVELOPER.md that's essentially load-bearing for the "References"
narrative. Surgically removing each link would (a) blow past the ceiling, and
(b) leave large gaps in DEVELOPER.md §2, §7, §8, §10 that need rewriting,
not just trimming.

The right next step is a **policy decision** (above) plus a dedicated rewrite
agent that picks one strategy and applies it consistently across all 7 files.

## Highest-priority fixes (if user picks strip-and-soften)

1. **DEVELOPER.md L241** — `docs/autonomous_log.md` reference. This is the only
   true INTERNAL-LEAK; the rest are just dead links. Even if the broader policy
   is "leave links and add a disclaimer," this one should be removed
   (or softened to "design decisions are logged with date, rationale, and
   references consulted" — no link).
2. **`.github/PULL_REQUEST_TEMPLATE.md` L34** — checkbox an external contributor
   can't satisfy. At minimum, remove `[ ] PLAN.md updated...` checkbox or
   reword as "If the change affects a locked design decision, call it out in
   the PR body."
3. **DEVELOPER.md §2, §7, §8 references section** — entire `references/`
   narrative is broken. Either (a) remove §7 and §8's reliance on
   `references/README.md`, OR (b) include a one-line note: "After running
   `sh scripts/setup_references.sh` the `references/` tree is local-only;
   links below resolve in your local clone, not on the published GitHub repo."

## Files that need user judgment

- **CHANGELOG.md** — historical `docs/...` references (15+ lines). Policy:
  leave-as-historical-context vs. scrub.
- **All `PLAN.md` references across 6 files** (~16 total) — policy: link to
  a public roadmap surrogate (GitHub Issues milestone? Releases?) vs. soften
  to prose vs. delete.
- **DEVELOPER.md §2 repo tour table L60, L63** — these are table rows; surgical
  deletion is easy but breaks the table layout's intent.
- **`docs/release_notes_v1.0.0.md` (USAGE L256)** — referenced but never
  written. Either write it and add to origin/main, or remove the reference.

## What's clean

- LICENSE — no stale refs.
- README L284 (`references/` in License section) — OK; matches local-only
  policy.
- `scripts/check_pr.sh` — clean.
- `assets/poker_solver.icns` — not a doc.
- `.github/ISSUE_TEMPLATE/bug_report.md` — clean.

## Recommended workflow

1. User picks a content policy (strip-and-soften / re-anchor / disclaimer).
2. Spawn a dedicated rewrite agent with the chosen policy + this audit as input.
3. Agent rewrites all 7 affected files in one consistent pass.
4. Final spot-check + push.

---

*Audit produced by content-audit agent. No edits applied to the repo.*
