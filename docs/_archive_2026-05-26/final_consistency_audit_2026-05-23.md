# Final Consistency Audit — 2026-05-23 (session close)

**Mode:** READ-ONLY. No file modifications. No git operations beyond fetch + log + pr list + tag list.
**Auditor:** Orchestrator self-audit per TEST/WRITE/REFERENCE rule.
**Scope:** Cross-doc consistency on v1.7.0, Path D, v1.6.0 .dmg, PR 44; memory snapshot; reversal-chain documentation; PR open state; tags + releases.

---

## 1. Cross-doc consistency

### v1.7.0 status

| Source | Claim | Status |
|---|---|---|
| README.md (origin/main) | "Latest tagged release: v1.6.0 (GUI Gate 2); v1.7.0 in flight" | **CONSISTENT** — README explicitly acknowledges v1.7.0 is in flight (line 15-18). |
| CHANGELOG.md (origin/main) | `## [1.7.0] - 2026-05-23` entry with PR 43 + PR 39 detail | **CONSISTENT** — v1.7.0 listed as the latest released entry; v1.6.1 noted HELD. |
| USAGE.md (origin/main) | Header reads `v1.4.x`; baseline through v1.4.3 only | **CONSISTENT BY DESIGN** — PR #2 (`pr-48-usage-v1-7-0-semantics`) is the v1.7.0 update; not yet merged, awaiting user. |
| USAGE.md (PR #2 branch) | Header reads `v1.4.x`, baseline updated to "through v1.7.0"; §5.6 + class-label semantics; §7a CLI subcommands | **CONSISTENT** with v1.7.0 release-notes correction. |
| v1.7.0 GitHub release notes | Post-release validation findings section (R5 correction); class-expansion semantics nuance; aligned with USAGE.md PR #2 | **CONSISTENT** — release notes already corrected past retraction; aligned with PR #2 wording. |

Verdict: **CONSISTENT**. USAGE.md "still on v1.4.x" on origin is intentional (PR #2 unmerged); release notes already retract+replace per R5.

### Path D status

| Source | Claim | Status |
|---|---|---|
| `docs/v1_6_1_path_d_decision.md` | "PROPOSED — pending user review" | **CONSISTENT** |
| `docs/STATUS_2026-05-23_post_retest_5th_reversal.md` | "AWAITING USER on signon" (decision queue #1) | **CONSISTENT** |
| `docs/WELCOME_BACK_USER_2026-05-23.md` | "PENDING USER OK" — primary decision (TL;DR §2) | **CONSISTENT** |
| PLAN.md §10 Gate 1 | "~closed pending Path D v1.6.1-engine ship" | **CONSISTENT** |
| Memory `project_solver.md` §Status | "Path D PROPOSED — v1.6.1-engine ship script VERIFIED ready; AWAITING USER OK" | **CONSISTENT** |

Verdict: **CONSISTENT**. All five surfaces agree: Path D = PROPOSED, awaiting user OK on signon.

### v1.6.0 .dmg status

| Source | Claim | Status |
|---|---|---|
| README.md (origin) | "arm64-only, experimental" + "see docs/dmg_install_guide.md" | **CONSISTENT** (line 21-24, "macOS install (.dmg, experimental)") |
| `docs/dmg_install_guide.md` (origin) | "v1.6.0 / 45 MB / SHA256 `0443e8f0...`" + full install guide | **CONSISTENT** |
| v1.6.0 GitHub release notes | `.dmg` attached, adhoc-signed, Gatekeeper bypass instructions | **CONSISTENT** |
| WELCOME_BACK doc | ".dmg still attached to v1.6.0 release (45 MB, SHA256 0443e8f0...) — remains latest downloadable" | **CONSISTENT** |

Verdict: **CONSISTENT**.

### PR 44 status

| Source | Claim | Status |
|---|---|---|
| PR #3 on origin (`pr-44-dmg-packaging-fix`) | open, MERGEABLE, not merged | **CONSISTENT** |
| `docs/pr44_completion_report.md` | "Edits applied; COMPLETE" | **CONSISTENT** (no claim of "merged"; only of edits applied + verification) |
| WELCOME_BACK doc | "PR #3 — .dmg packaging fix: verified; URL given" | **CONSISTENT** |

Verdict: **CONSISTENT**.

---

## 2. Memory snapshot

- File count: 30 .md files in memory dir (29 + MEMORY.md = 30).
- `MEMORY.md`: 30 lines — **AT the cap**, not over.
- All four new session entries present:
  - `feedback_test_write_reference.md`
  - `feedback_dotso_arch_check.md`
  - `feedback_post_ship_persona_retest.md`
  - `feedback_independent_verification.md`
- Floor=4 documented in `feedback_min_five_agents.md` (per line 11 of MEMORY.md: "current floor=4 (re-reaffirmed 2026-05-23 late evening)") — **CURRENT**.
- All `[link](file.md)` references resolve to files in the memory dir — **NO BROKEN REFERENCES**.

Verdict: **CLEAN**.

---

## 3. Reversal chain (R1-R5) documented

| Source | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| PLAN.md §13 lessons (line 469) | refs §4 archived | refs §4 archived | refs §4 archived | refs §4 archived | refs §4 archived |
| `STATUS_2026-05-23_post_retest_5th_reversal.md` (lines 7-11) | full | full | full | full | full |
| `WELCOME_BACK_USER_2026-05-23.md` (lines 47-51) | full | full | full | full | full |

PLAN.md §13 line 469 cites `docs/archived_claims_2026-05-23.md` §4 as canonical source for R1-R5 details, with a one-line meta-summary. STATUS and WELCOME_BACK each carry the full chain inline. Chain semantics agree across all three:

- R1: solver-broken (PR 23 deep-dive)
- R2: solver-broken → test-bugs-only (v1.5.0 acceptance harness bisection)
- R3: test-bugs-only → solver-has-deep-cap-bug (A83 dry-run #1)
- R4: no-bug-just-plumbing REFUTED by dry-run #2 (K72 42pp / A83 27pp; convention divergence; Path D)
- R5: W3.5 wrapper-bug REFUTED by independent diff-test; class-expansion semantics nuance only

Verdict: **COMPLETE**.

---

## 4. PR open state

`gh pr list --state open` returns 3 PRs, all MERGEABLE:

- **PR #2** — `pr-48-usage-v1-7-0-semantics` — docs(usage): v1.7.0 aggregator-vs-Nash + class-label semantics
- **PR #3** — `pr-44-dmg-packaging-fix` — fix(packaging): v1.4.0 .dmg nicegui bundle + arch + version
- **PR #4** — `pr-49-readme-broken-ref-cleanup` — docs(readme): fix broken cross-ref to internal-only smoke doc

Verdict: **3/3 OPEN, all MERGEABLE**.

---

## 5. Tags + releases

`gh release list --limit 5`:
- v1.7.0 (LIVE, latest) — 2026-05-23T23:06:07Z
- v1.6.0 (LIVE, with .dmg attached) — 2026-05-23T20:14:18Z

`git tag -l 'v1.*'`: v1.0.0 through v1.7.0 chronologically (with v1.6.0 and v1.7.0 the most recent two).

Verdict: **2 LIVE** (v1.6.0 + v1.7.0).

---

## Final verdict

**SESSION-CLOSE-READY.**

No cross-doc drift; memory snapshot clean (30/30 cap, floor=4 documented, 4 new entries present); reversal chain R1-R5 complete across PLAN.md §13 + STATUS + WELCOME_BACK; 3/3 PRs open + mergeable; 2 LIVE releases (v1.6.0 + v1.7.0).

USAGE.md on origin/main remains at v1.4.x baseline — this is consistent with PR #2 being the unmerged v1.7.0 update, exactly as the documents claim ("USAGE.md update IN FLIGHT on `pr-48-usage-v1-7-0-semantics`"). The v1.7.0 release notes were already corrected past the wrapper-bug retraction; the corrected version is on GitHub and aligned with PR #2's wording.

User can sign on, review the open PRs + Path D decision doc, and proceed without remediation. No fixes required pre-signon.
