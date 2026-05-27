# Release Docs Consistency Check — 2026-05-23

**Scope:** 4 release-prep docs cross-validated for internal consistency.
**Mode:** READ-ONLY across the 4 release docs; only this file written.

Docs audited:
1. `RELEASE_NOTES_2026-05-23.md`
2. `RELEASE_HEADLINES_2026-05-23.md`
3. `RELEASE_CHECKLIST_2026-05-23.md`
4. `docs/README_proposed_update_2026-05-23.md`

---

## Per-check verdicts

| # | Check | Verdict | Notes |
|---|---|---|---|
| 1 | **Version claims** (v1.5.1 latest public; v1.4.0 latest .dmg; v1.6.0 GUI in flight; v1.6.1 engine bundle queued) | CONSISTENT | Notes §1+§4, Headlines §1-3, Checklist §1+§5+§6, README-draft "Status" + "Trajectory" all align. The README draft is the only one that does not explicitly name v1.6.0/v1.6.1 (by design — "describes what's shipped on public origin"); this is internally documented at draft Notes §6 and is a deliberate omission, not a contradiction. |
| 2 | **SHA citations** (origin/main = `b5777f22…`; .dmg = `Poker-Solver-1.4.0-universal2.dmg`) | CONSISTENT | Notes §1 cites `b5777f22`; Checklist §1 cites the full `b5777f22f99ee3b912822c0fb30d771dd03954df` (consistent short→long); .dmg filename is verbatim identical in Notes §5, Checklist §1+§5, README-draft "Status" + "Installation". |
| 3 | **Persona count** (10 PASS / 5 PARTIAL / 3 BLOCKED) | CONSISTENT | Notes §6 states verbatim; Checklist §4 + §7 quotes verbatim. Headlines + README-draft do not include persona counts (deliberate omission per Checklist §4 "default: omit from announcement, keep in release notes" and README-draft Notes §5). No contradiction. |
| 4 | **PR 23 framing** ("test bugs + actively investigating deep-cap gap") | INCONSISTENT — OVER-PESSIMISTIC vs latest triage | See HIGH-severity note below. Notes §5, README-draft "Known limitations", and the cell-bisection citation now blame BOTH test bugs AND a confirmed algorithmic gap. The triage agent (`docs/pr_23_deep_cap_algorithmic_triage.md`, landed AFTER critical revision) concludes: **no algorithmic bug; reported divergence is a test artifact (HIGH confidence)**. Headlines §2/§3 + Checklist §4 still say "algorithmically correct, failures test-side" — which is now the more-accurate framing. Notes + README-draft over-pessimize. |
| 5 | **CLI subcommands** (`pushfold`, `river`, `parity` NOT YET shipped; queued v1.7.0) | CONSISTENT | Notes §5 ("queued for v1.7.0"); Headlines §3 ("queued"); README-draft "Known limitations" ("queued for the next MINOR"). Checklist does not name them directly — no contradiction. |
| 6 | **License + platform** (MIT; macOS/Linux; Apple Silicon primary) | CONSISTENT | All four docs concur verbatim. |

---

## Public-OK content scan

**Result: 1 leak found, otherwise clean.**

- LEAK (low-severity, fixable single-line): `RELEASE_CHECKLIST_2026-05-23.md:14` contains an absolute path `/Users/ashen/Desktop/poker_solver` inside a `git -C` smoke command. This is PII (home-directory username) and should be replaced with `git -C .` or a relative path, OR the checklist should be marked internal-only (the file itself reads like an internal ops doc, not a public artifact, so the latter is preferable).
- No session UUIDs, agent IDs, private-mirror mentions, or internal task references found in any of the 4 docs.
- README-draft Notes §5 explicitly catalogs what was kept OUT (burst-summary internals, PR numbers, private-mirror state, integration-branch sequencing, persona scores) — that meta-text is fine because it documents the redaction discipline, not the redacted content.

---

## Recommended micro-edits

1. **HIGH PRIORITY — PR 23 framing reconciliation (orchestrator decision required).** Either: (a) walk Notes §5 + README-draft "Known limitations" back toward "code-review-validated algorithmically correct; 22-42pp divergence is a test artifact per latest triage; deep-cap caveat is a 10-15% confidence-discount, not a known bug" — aligning with triage + Headlines + Checklist; OR (b) walk Headlines + Checklist forward to match Notes' over-pessimistic framing. Recommendation: option (a) — the triage agent landed last and is the most informed source, and option (b) would publicly contradict 3 independent code reviews already cited in Checklist §4.
2. **LOW PRIORITY — PII redaction.** Either replace `git -C /Users/ashen/Desktop/poker_solver` at `RELEASE_CHECKLIST_2026-05-23.md:14` with `git -C .`, or treat the checklist as internal-only (do not publish).

---

## Net verdict

**NEEDS-MINOR-FIX.**

- **Doc:** `/Users/ashen/Desktop/poker_solver/docs/release_docs_consistency_check.md`
- **High-severity inconsistency:** PR 23 framing — Notes §5 and README-draft "Known limitations" over-pessimize ("confirmed algorithmic gap, actively investigating") relative to the post-revision triage agent's finding ("HIGH confidence no algorithmic bug; the 22-42pp divergence is a test-side action-axis + range-slot artifact"). Headlines + Checklist already align with triage. Reconciliation needed before publication.
- **Low-severity inconsistency:** PII in checklist line 14 (`/Users/ashen/` absolute path).

Version claims, SHA citations, persona counts, CLI-subcommand framing, and license/platform claims are otherwise CONSISTENT across all 4 docs.
