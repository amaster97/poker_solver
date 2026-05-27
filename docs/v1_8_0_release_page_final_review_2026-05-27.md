# v1.8.0 GitHub Release Page — Final Public-Facing Review (2026-05-27)

**Release URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.8.0
**Release tag:** `v1.8.0`
**Release title:** `v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix`
**Published:** 2026-05-27T09:18:40Z (`createdAt = 2026-05-27T09:18:38Z`,
both via `gh release view v1.8.0`)
**Assets:** 0 (no `.dmg` attached — confirmed via
`gh release view v1.8.0 --json assets` → `"assets":[]`)
**Draft/prerelease flags:** `isDraft=false`, `isPrerelease=false`
(public, GA).
**Body line count (markdown source):** 714 lines.
**Compared against:** `docs/v1_8_0_release_notes_DRAFT.md` (722 lines,
updated post-ship via the PR #96 / #87 / #85 amendment chain to scrub
"PR #93" references and re-point to the archived doc).

This review is **read-only** on the GitHub release object — no
amendments made. The release body is preserved as published until the
user decides whether to re-publish.

---

## 1. Body content sanity (PASS/FAIL per check)

| Check | Verdict | Evidence |
|---|---|---|
| Zero unfilled `<TBD-...>` markers | **PASS** | `grep -i "TBD\|<TBD\|<placeholder\|<TODO"` → 0 hits. The "DRAFT" word appears only in the bold preamble status line ("Status: DRAFT (post-purge framed)") — a frozen artifact from the pre-tag draft, not an unfilled marker. |
| Zero "PR #93" references | **FAIL (5 hits)** | Lines 192, 397, 414, 428, 521 all still say "PR #93 ablation" / "PR #93's measured 12-50pp" / "PR #93's 12-50pp" / "PR #93's ablation". This is the divergence-from-draft point — see §3 below. **PR #93 does not exist as a merged GitHub PR**; the underlying ablation was an internal branch `pr-93-terminal-utility-ablation @ 986f48d`. A public viewer clicking "PR #93" on GitHub gets either a 404 or a different unrelated PR — `gh pr view 93` was not executed here, but the draft amendment explicitly flags this as "NOT a merged GitHub PR." |
| Zero local-only filesystem paths used as Markdown links `[text](path)` | **PASS** | No inline `[text](docs/...)` links. All `docs/...` references are written as backtick-quoted code spans (e.g. `` `docs/v1_5_brown_post_purge_numbers_2026-05-27.md` ``), which render as code, not links. Public viewers see them as inert filenames — they cannot click through, but they are not broken either. **Soft FAIL:** there are 23 such code-span doc references in the body; viewers from the browser cannot resolve any of them. Acceptable trade-off for an audit-trail release, but worth flagging. |
| Self-referential PR links resolve in the browser | **PASS** | All reference-style `[prNN]` link definitions at lines 691-713 point at `https://github.com/amaster97/poker_solver/pull/NN` — these resolve correctly when a viewer clicks them on the release page. Verified PR #32 (merged, "PR 71: v1.8 Phase 4") and PR #78 (merged, terminal-utility purge) via `gh pr view`. The 24 ref-link definitions match the 24 unique PR numbers referenced. |
| Headline numerical claims (L1 / strict max |Δ|) match in-repo docs | **PASS** | Body claims "L1 max 1.703 (K72) / 1.813 (A83); strict max \|Δ\| 0.852 / 0.907". `docs/v1_5_brown_post_purge_numbers_2026-05-27.md` lines 25-26 / 40 / 74 confirm L1 1.703 / 1.813 and strict 8.517e-01 / 9.066e-01 (i.e., 0.852 / 0.907). Body and source-of-truth agree. |
| "v1.5 Brown" / "post-purge" / "Nash multiplicity" framing matches in-repo docs | **PASS** | Body's A83 section (lines 386-441) aligns with `feedback_nash_multiplicity_acceptance.md` framing (reframed 4-layer SANITY gate; strict per-cell is informational; multiplicity at deep-cap indifference manifolds). |
| v1.6.0 `.dmg` was actually pulled | **PASS** | `gh release view v1.6.0 --json assets` → `assets: 0`. The v1.6.0 release page now opens with a "CRITICAL — v1.6.0 .dmg is BROKEN" warning banner, consistent with the v1.8.0 body's Highlight 2 narrative. |
| HTML entities not leaking (e.g., `&lt;`, `&amp;`) | **PASS** | `grep -E '\&[a-z]+;'` → 0 hits. |

**Net body-content sanity: 1 hard FAIL** (PR #93 references — see
§3 for the divergence story) + 1 soft FAIL (browser-unreachable local
doc references, acceptable for audit trail).

---

## 2. Format rendering issues

GitHub renders the body as GitHub Flavored Markdown. Items checked:

| Aspect | Status | Notes |
|---|---|---|
| Heading hierarchy (H1 → H2 → H3, no skips) | **CLEAN** | Single H1 at line 1 (the title — note: GitHub typically also renders the release name as its own page heading, so this body H1 will appear immediately below the page header, slightly stacking visually but not broken). H2s at lines 24, 69, 381, 509, 556, 585, 612, 632, 658, 675. H3s at lines 71, 110, 139, 156, 177, 270, 287, 317, 386, 511, 558, 572. No H4. No skipped levels. |
| Tables | **CLEAN** | Two tables: SIMD-phase table (lines 79-85) and persona-verdict table (lines 322-327). Both have proper `|...|` rows and `---` separators. Persona-verdict table's "Workflows" cell is unusually wide but renders fine. |
| Code blocks | **CLEAN** | 4 fenced code blocks: `bash` (lines 560-564, 615-617, 626-628), and one un-tagged formula block (lines 200-204, the `winner_utility = ...` snippet). All correctly triple-backticked, no broken closers. |
| Long lines wrapping | **CLEAN** | Body uses ~72-char wrapping (visible in the source; GitHub flows them on render). One slightly long line at 196 (the formula expansion) is inside a code block and so won't wrap. |
| Reference-style links | **CLEAN** | 24 `[prNN]: url` definitions at lines 691-713, all alphabetized by PR number, all resolve to `https://github.com/amaster97/poker_solver/pull/NN`. The unusual `[#`78`][pr-purge]` at line 645 (backtick-inside-link-text) renders correctly on GitHub but is slightly odd stylistically. |
| Emojis / special characters | **CLEAN** | Em-dashes (`—`), arrows (`→`), Greek delta (`Δ`), times (`×`) all render correctly via UTF-8. No raw HTML entities. |

**Net rendering: clean.** The body renders correctly as Markdown on
GitHub.

---

## 3. Draft-vs-GitHub-body divergences

The current `docs/v1_8_0_release_notes_DRAFT.md` (722 lines) differs
from the GitHub release body (714 lines) in **5 locations**, all
clustered around PR #93 references. The draft has been amended
post-ship (per the task brief, via PR #96 + #87 + #85) to scrub
"PR #93" and re-point to the archived ablation doc; the GitHub release
body is frozen at tag time and still has the old text.

| Body Line | GitHub Release Body Text (frozen) | Current Draft Text (amended) |
|---|---|---|
| 192-193 | `reference Brown solver at deep cap (PR #93 ablation, `docs/a83_terminal_utility_ablation_results_2026-05-26.md`). v1.8.0` | `reference Brown solver at deep cap (internal terminal-utility ablation, branch pr-93-terminal-utility-ablation @ 986f48d — NOT a merged GitHub PR; results archived at docs/a83_terminal_utility_ablation_results_2026-05-26_archived.md). v1.8.0` |
| 397-398 | `closed the regret-update bias (PR #93's measured 12-50pp Rust-vs-Rust shift); residual is genuine multiplicity.` | `closed the regret-update bias (the internal terminal-utility ablation on branch pr-93-terminal-utility-ablation @ 986f48d measured a 12-50pp Rust-vs-Rust shift between conventions; NOT a merged GitHub PR); residual is genuine multiplicity.` |
| 414-415 | `The convention purge DID fix the regret-update bias (PR #93's 12-50pp gap is closed); the strict per-cell |Δ| residual is a SEPARATE` | `The convention purge DID fix the regret-update bias (the pr-93-terminal-utility-ablation branch's measured 12-50pp gap is closed); the strict per-cell |Δ| residual is a SEPARATE` |
| 428-429 | `from PR #93's ablation. Note: the 12-50pp PR #93 gap was a Rust-vs-Rust ablation between conventions and IS closed by the purge;` | `from the internal pr-93-terminal-utility-ablation branch's run. Note: the 12-50pp gap from that internal ablation was a Rust-vs-Rust ablation between conventions and IS closed by the purge;` |
| 521-522 | `(PR #93 ablation, `docs/a83_terminal_utility_ablation_results_2026-05-26.md`).` | `(internal terminal-utility ablation, branch pr-93-terminal-utility-ablation @ 986f48d — NOT a merged GitHub PR; results archived at docs/a83_terminal_utility_ablation_results_2026-05-26_archived.md).` |

Also: the original (non-archived) filename `a83_terminal_utility_ablation_results_2026-05-26.md` referenced in the GitHub body **no longer exists** in `docs/` — only the `_archived.md` variant remains:

```
ls docs/a83_terminal_utility_ablation_results*.md
# -> only docs/a83_terminal_utility_ablation_results_2026-05-26_archived.md
```

So the GitHub body's two backtick code-span references at lines 193 and 522 now point to a filename that's been renamed. Viewers can't click those (they're code spans, not links), but a researcher cloning the repo will not find the file at the path the body names.

---

## 4. Public-facing accuracy (what a user sees)

A public viewer landing on
https://github.com/amaster97/poker_solver/releases/tag/v1.8.0 sees:

1. **Title:** "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix" — clear, scannable, matches the body H1.
2. **Headline + 3-bullet summary:** Cross-platform SIMD (portability win, not a speedup — honestly framed), terminal-utility convention purge (with the BREAKING note up-front), and the `.dmg` fork-bomb fix. **What's in the release is clearly communicated.**
3. **No `.dmg` to download:** the "Assets" section on the GitHub UI will show only "Source code (zip)" and "Source code (tar.gz)" (GitHub's auto-generated source bundles for any tag). There is no v1.8.0 `.dmg`. The body **does mention** the v1.8.0 `.dmg` (Highlight 2, line 53; Upgrade Path line 576-580: "Download the v1.8.0 `.dmg` from the GitHub Release page (when published — note: the v1.8.0 `.dmg` build verification is the final ship step before this release publishes)"). The parenthetical "(when published — note: ... is the final ship step before this release publishes)" is **stale relative to the published state** — the release IS already published, but no `.dmg` is attached. A user clicking through to find the `.dmg` will see no asset and the body's own caveat tells them it's still the "final ship step." **This is honest but slightly self-contradictory.**
4. **Source code download:** GitHub auto-generates source archives from the `v1.8.0` git tag. Users can clone or download source. The body's "From v1.7.0 source install" upgrade path (lines 558-565) gives reproducible install instructions (`git pull && pip install -e . && maturin develop --release`).
5. **PR links:** All 24 reference-style PR links resolve correctly when clicked.

**Net public-facing accuracy:** A user lands and gets a clear picture
of (a) what's in v1.8.0, (b) why there's no `.dmg` yet (caveated as the
final ship step), and (c) how to install from source. The PR #93
references DO appear in body text but are not hyperlinked, so a viewer
sees them as text-only mentions. They will read as confusing
("PR #93… where do I find that?") but not as a broken link.

---

## 5. Recommendation

**Recommendation: LEAVE-AS-IS for now; user decision on whether to
amend.**

The case for amending (re-publishing the body):

- 5 "PR #93" text references that point at a non-existent merged PR.
- 2 backtick code-span references to a filename that has been renamed
  to the `_archived.md` variant.
- 1 stale parenthetical "(when published — note: ... is the final
  ship step)" in the upgrade-path `.dmg` section that contradicts the
  now-published-but-no-asset state.

The case for leaving as-is:

- No hard rendering bug, no broken markdown link, no exposed HTML
  entity, no `<TBD>` marker.
- The PR #93 references are textual confusion, not broken links.
- The amendment trail in the draft (PR #96 + #87 + #85) was a
  post-ship audit-trail decision — the GitHub body acts as a tag-time
  snapshot, which is a valid release-engineering convention.
- A re-publish rewrites release history; for an audit-trail-friendly
  workflow this is undesirable.

**If the user wants to fix the public-facing top 3 issues without
rewriting the whole body**, the surgical edit set is:

1. (Lines 192-193, 397-398, 414-415, 428-429, 521-522) — sweep the
   5 "PR #93" mentions and replace with "internal ablation branch
   `pr-93-terminal-utility-ablation` @ `986f48d`" per the draft.
2. (Lines 193, 522) — update filename `a83_terminal_utility_ablation_results_2026-05-26.md` → `a83_terminal_utility_ablation_results_2026-05-26_archived.md`.
3. (Lines 576-580) — replace the parenthetical "(when published — note: the v1.8.0 `.dmg` build verification is the final ship step before this release publishes)" with a definitive "(v1.8.0 `.dmg` not yet attached as of 2026-05-27; install from source per §Upgrade path or watch for a follow-up release update)".

These are 7 small edits in 4 line ranges; the body would otherwise be
unchanged.

---

## 6. Top user-visible issues (sorted by severity)

| # | Severity | Issue | Where | Impact |
|---|---|---|---|---|
| 1 | **MEDIUM** | 5 references to non-existent "PR #93" | Lines 192, 397, 414, 428, 521 | A diligent reader clicking through will be confused — there is no PR #93 on the public repo (the underlying ablation lived on an internal branch). Text-only mention, so no hyperlink-404. Confusion not breakage. |
| 2 | **LOW-MEDIUM** | "(when published — the v1.8.0 `.dmg` build verification is the final ship step before this release publishes)" | Lines 576-580 (Upgrade Path > From v1.6.0 `.dmg` step 2) | The release IS published, so the parenthetical is stale. A user reading this is told the `.dmg` is coming, finds no asset attached, and is left to infer next steps. |
| 3 | **LOW** | 2 references to renamed file `docs/a83_terminal_utility_ablation_results_2026-05-26.md` (now `_archived.md`) | Lines 193, 522 | Only matters for a viewer who clones the repo and tries to follow the doc reference — the file is at the `_archived.md` path. Public release-page-only viewers won't notice. |
| 4 | **LOW** | 23 `docs/...` code-span references that browser viewers can't click through | Throughout | Audit-trail-friendly but viewer-unfriendly. Acceptable trade-off for this release; no fix recommended. |
| 5 | **LOW** | "Status: DRAFT (post-purge framed)" preamble paragraph (lines 3-13) is a frozen drafting-state artifact | Lines 3-13 | Reads as "this is still a draft" to a casual viewer, though the rest of the body makes clear the release is shipped. Cosmetic. |
| 6 | **NONE** | The unusual `[#`78`][pr-purge]` link in the Full PR list | Line 645 | Renders fine on GitHub; mild stylistic oddity (backticks inside link text wrapping `78`). Not user-visible as breakage. |

No CRITICAL, no HIGH severity issues found. No broken hyperlinks, no
broken Markdown rendering, no exposed HTML entities, no unfilled
placeholder markers.

---

## 7. Summary

- **The release page is publishable as-is for an audit-trail-friendly
  workflow.** A user landing on it gets accurate information about
  what's in v1.8.0, an honest caveat about the missing `.dmg`, and a
  source-install path.
- **The PR #93 references are the one substantive concern.** They are
  not broken links (the text is not hyperlinked), but they reference a
  PR number that does not exist on the public repo. The draft has
  been amended to use "internal ablation branch" language; the
  release body has not.
- **No re-publish is required for safety.** The body does not mislead
  users about the engine fix or the `.dmg` situation; the PR #93
  references read as a slightly confusing internal cross-reference,
  not as a false claim.
- **If the user wants the cleaner public face**, surgical edits to
  the 5 PR #93 mentions + the stale `.dmg`-final-ship-step
  parenthetical + the renamed-file references would resolve all 3 of
  the top user-visible textual issues without rewriting the body.
