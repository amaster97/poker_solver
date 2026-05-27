# MEDIUM Staleness Fix — PR #99 Report (2026-05-26)

**Branch:** `pr-99-medium-staleness-fix` (worktree at
`/Users/ashen/Desktop/poker_solver_worktrees/pr-99-medium-staleness-fix`)
**Base:** `origin/main` @ `bf645ae` (post HIGH-fix #55, post release-
notes-honesty #56)
**Scope:** 7 MEDIUM-priority stale claims from
`docs/doc_staleness_sweep_2026-05-26.md`
**Coordination:** Distinct file scope vs in-flight PRs:
- PR #55 (HIGH-priority staleness, MERGED at `7bb21d8`) touched
  README.md, USAGE.md, CHANGELOG.md L16-78 / L189-190 / L58-64. My
  CHANGELOG edits are at L1298-1300, L1517, L1562, L1627-1635 (v0.5.2
  and v0.3.0/v0.3.1 historical entries) — strictly outside HIGH-fix
  territory.
- PR #56 (release-notes-honesty + W3.2 smoke, MERGED at `bf645ae`)
  touched `docs/v1_8_0_release_notes_DRAFT.md`. No overlap.
- PR #20 (CI timeout) touches `.github/workflows/ci.yml`. No overlap.

---

## Per-claim summary

| ID | File | Stale wording | Replacement |
|---|---|---|---|
| **M1** | `docs/aggregator_vs_true_nash_explainer.md` (TL;DR + Example 3) | TL;DR: "currently under investigation for a deep-cap facing-raise divergence". Example 3: "v1.6.1-bundle dry-run empirically re-confirms a residual algorithmic divergence... Investigation in flight: best-response cross-check + iteration sweep + side-by-side re-read." | TL;DR: "deep-cap facing-raise residual divergence is resolved as Nash-multiplicity within an indifference manifold". Example 3: Investigation closed; two compound causes (test-side wrapper bugs fixed in v1.7.1 bundle PR 52/55/56; Nash-multiplicity at depth ≥ 11 facing-all-in `(c,f)` AA leaves, both solvers within indifference manifold, Brown exploitability 0.06 chips at 2000 iters). Cites tracked docs `a83_validation_2026-05-26.md`, `terminal_utility_audit_2026-05-26.md`, `terminal_utility_arbitration_2026-05-26.md` (arbitrator's NOT-A-BUG verdict), `v1_6_1_ship_hold_review_2026-05-26.md`. |
| **M2** | `docs/dmg_spawn_loop_rca_2026-05-26.md` (file previously untracked; added) | Header Status: "Confirmed via code inspection — do NOT launch the .app". Section L197: "Use v1.7.1 or later". L210: "Upgrade to v1.7.1 or later. The .dmg has been corrected in subsequent releases." L230: "Recommended Fix (For v1.7.2 / v-final)". L290-291: "v1.7.1 GUI re-introduced (v1.6 engine) \| Likely still vulnerable", "v-final \| Fix planned \| TBD". | Header: "Fix merged on `main` (PR #42, commit `728206e`); ships in v1.8.0 (repackaged .dmg pending)". L197/L210: "Use v1.8.0 or later (v1.7.1 closed as obsolete per `docs/v1_7_1_tag_decision_2026-05-26.md`; fix folds into v1.8.0)". L230: "Recommended Fix (For v1.8.0 / repackaged .dmg)". Timeline rows for v1.7.1, v1.7.2 reframed as "closed as obsolete; folded into v1.8.0"; v1.8.0 row added: "Fork-bomb fix shipped (PR #42, commit `728206e`); repackaged .dmg pending tag + release". v1.6.0 historical reference preserved. **Action:** ALSO added the file to git (was untracked despite being referenced from tracked README.md L40, L235 and USAGE.md L49) — converts broken README/USAGE links to working links. |
| **M3** | `docs/dmg_install_guide.md` (top banner + Known limitations + Related documents) | Title: "macOS .dmg Install Guide (v1.6.0)". Banner: "This guide is preserved for use with the upcoming v1.7.2 repackaged build, NOT v1.6.0." Limitations: "v1.6.0 feature set only. Newer features merged after v1.6.0 are available only via source install." | Title: "macOS .dmg Install Guide (v1.6.0 — withdrawn; v1.8.0 repackage pending)". Banner: v1.6.0 .dmg retroactively pulled; v1.8.0 repackaged .dmg pending; no v1.7.1/v1.7.2 tag (closed as obsolete); install from source until v1.8.0 ships. Limitations reframed: "v1.6.0 .dmg feature set is now outdated... upcoming v1.8.0 repackaged build folds in everything merged on `main` since v1.6.0". Related documents: added cross-link to `dmg_spawn_loop_rca_2026-05-26.md`. |
| **M4** | `CHANGELOG.md` L1517 (broken link to `docs/architecture.md`) | "agent writing `docs/architecture.md` surfaced the dispatch gap" | "agent writing the architecture overview now consolidated into [`DEVELOPER.md`](DEVELOPER.md) surfaced the dispatch gap" (sweep's own recommendation: "likely meant to point at DEVELOPER.md"). DEVELOPER.md is tracked and exists. |
| **M5** | `CHANGELOG.md` L1562, L1627-1631 (2 broken links to `docs/pushfold_v1_generation_notes.md`) | L1562: "See `docs/pushfold_v1_generation_notes.md` for the full methodology." L1627: Documentation bullet referencing the file as authoritative methodology source. | L1562: "(Internal methodology notes were retired during the 2026-05-23 doc archive sweep; the generator script is self-documenting.)". L1627: Reframed as historical narrative noting retirement. Broken cross-link references removed; narrative preserved. |
| **M6** | `CHANGELOG.md` L1632-1635 (broken link to `docs/release_notes_v0.3.md`) | "`docs/release_notes_v0.3.md`: user-facing release notes for this release." | "This CHANGELOG entry is the user-facing release note for v0.3.0; the separate `docs/release_notes_v0.3.md` working note was retired during the 2026-05-23 doc archive sweep." |
| **M7** | `CHANGELOG.md` L1298-1301 (2 broken links to `docs/pr4_5_audit_debt/launch_kickoff.md` and `docs/pr4_5_audit_debt/audit_report.md`) | "Three-agent fan-out (A: PR 3/3.5; B: PR 4; C: PR 5) per `docs/pr4_5_audit_debt/launch_kickoff.md` sec 2. Audit verdict READY-WITH-PATCHES per `docs/pr4_5_audit_debt/audit_report.md`; must-fix patches landed before this commit." | "Three-agent fan-out (A: PR 3/3.5; B: PR 4; C: PR 5). Audit verdict READY-WITH-PATCHES; must-fix patches landed before this commit. (The internal `docs/pr4_5_audit_debt/` working-folder was retired during the 2026-05-23 doc archive sweep; the narrative is preserved in this entry.)" |

---

## Broken-link existence audit

Per the sweep's M7 finding, all 4 broken-link targets were verified
ABSENT in both the live `docs/` tree AND in `docs/_archive_2026-05-26/`,
`docs/_archive_2026-05-26_session/`:

| Target | Status | Action |
|---|---|---|
| `docs/architecture.md` | Missing on origin/main; not in archive | Redirected to `DEVELOPER.md` (sweep's own recommendation) |
| `docs/pushfold_v1_generation_notes.md` | Missing on origin/main; not in archive | Removed cross-link; narrative preserved citing the generator script |
| `docs/release_notes_v0.3.md` | Missing on origin/main; not in archive | Removed cross-link; clarified the CHANGELOG entry IS the release notes |
| `docs/pr4_5_audit_debt/audit_report.md` and `launch_kickoff.md` | Missing on origin/main; folder doesn't exist; not in archive | Removed cross-links; narrative preserved |

No fabricated placeholder docs were created. Per user constraint:
"prefer LINK REMOVAL or CORRECTION over creating placeholder docs."

---

## Files changed

- `CHANGELOG.md` — historical entries at L1298-1301, L1517-1521, L1562, L1627-1638 (4 broken-link blocks resolved; 0 lines touched in the v1.8.0 / v1.7.0 / v1.6.0 / v1.5.0 HIGH-fix territory at L16-78, L189-190, L58-64)
- `docs/aggregator_vs_true_nash_explainer.md` — TL;DR + Example 3 reframed
- `docs/dmg_install_guide.md` — title + banner + limitations + Related-documents
- `docs/dmg_spawn_loop_rca_2026-05-26.md` — added to git + header + L197/L210/L230/L290-291 updated

---

## Caveats

1. **`docs/v1_7_1_tag_decision_2026-05-26.md` remains untracked on
   `origin/main`** despite being referenced from CHANGELOG.md L21,
   README.md L21, `docs/v1_8_0_release_notes_DRAFT.md` L8/L157/L255, and
   my updated `dmg_spawn_loop_rca` / `dmg_install_guide`. This is a
   pre-existing broken-link condition introduced by PR #55 (HIGH fix).
   Adding it is out of scope for this PR (would require a separate
   doc-tracking decision the user did not authorize). My references to
   it are consistent with the existing main-line state; they will
   resolve when that file is tracked in a follow-up.

2. The MEMORY.md project rule `feedback_label_vs_semantics` cross-
   reference was dropped from the aggregator explainer (was relevant to
   the open-investigation framing; redundant now that the resolution is
   stated). The doc still preserves the substantive structural-review
   summary.

---

## Test plan (zero engine impact)

- Docs-only PR; no code, no tests, no CI workflow changes.
- Manual eyeball confirmation:
  - `grep -nE "\[.+\]\(.*pr4_5_audit_debt|\[.+\]\(.*release_notes_v0\.3|\[.+\]\(.*pushfold_v1_generation|\[.+\]\(.*architecture\.md" CHANGELOG.md` returns empty (no markdown links to nonexistent docs).
  - `grep -n "investigation in flight\|currently under investigation" docs/aggregator_vs_true_nash_explainer.md` returns empty.
  - `grep -n "Upgrade to v1.7.1\|Use v1.7.1 or later" docs/dmg_spawn_loop_rca_2026-05-26.md` returns empty.
  - `grep -n "v1.7.2 repackaged build" docs/dmg_install_guide.md` returns empty.

---

**Audit classification:** **Type A docs-only** per
`feedback_persona_test_rectification.md`; eligible for autonomous
commit if audit-clean.
