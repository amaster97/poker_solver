# v1.7.1 Final Readiness Audit — 2026-05-24

**Mode:** Read-only independent sanity audit
**Auditor:** Final-readiness agent (one-shot)
**Verdict:** **DEPENDS-ON-DRY-RUN-9** (ship script and user docs need touch-ups regardless)

---

## TL;DR

- **Kernel:** verified correct via AA-vs-AA minimal fixture + `dcfr_vector.rs` re-audit (see Phase 1).
- **Bundle:** the canonical corrected bundle (7 PRs, post-R11) is composed of mergeable+clean branches on origin; PR 55-ext and PR 53 (original) and PR 11 (asymmetric fixture) are correctly excluded.
- **Ship script:** **STALE.** Still cherry-picks PR 55-ext as the 5th step (8 cherry-picks total). Needs PR 55-ext removal + comment/checklist updates before fire.
- **User signon docs:** **STALE.** All five docs (`WELCOME_BACK`, `SESSION_TLDR`, `PR_REVIEW_PREP_2026-05-23`, `SIGNON_CHECKLIST`, `PRE_SIGNON_FAQ`) still frame v1.7.1 as **HELD pending R11 root cause** with an 8-PR bundle. The R11-resolved status doc (`STATUS_2026-05-24_r11_resolved.md`) has been written but the user-facing docs have not been refreshed to match.
- **Dry-run #9:** not yet landed in `docs/`. No `*dryrun_9*` or `*dryrun*9*` file exists. The corrected-bundle empirical clear-at-depth-0 is still PENDING per `STATUS_2026-05-24_r11_resolved.md` L5.

---

## Phase 1 — Kernel verification status

Two independent confirmations are written and consistent:

1. `docs/r11_aa_vs_aa_minimal.md` — AA-vs-AA minimal Nash fixture with identical action menus on both sides shows **floating-point precision agreement** between our Rust DCFR and Brown's binary. **Refutes the kernel-bug hypothesis empirically.** (See L143-150 and the Phase 4 minimal-fixture description.)
2. `docs/r11_dcfr_vector_reaudit.md` — line-by-line semantic re-audit of `crates/cfr_core/src/dcfr_vector.rs`. Verdict at L770-774: **"No fix recommended for `dcfr_vector.rs` — the audit found no semantic bug, and the AA-vs-AA minimal fixture empirically confirms the kernel is correct."**

**Kernel is verified correct.** R11 is reclassified as a TEST-SIDE bug (PR 40 + PR 55-ext double-swap) per `STATUS_2026-05-24_r11_resolved.md`.

---

## Phase 2 — Open PRs on origin (gh pr list)

| # | Branch | Title | Mergeable | In bundle? |
|---|---|---|---|---|
| 14 | `pr-53b-rebased-on-pr-54` | test(acceptance): reframe (rebased on PR 54 renderer) | MERGEABLE+CLEAN | YES |
| 13 | `pr-55-extend-input-range-swap` | PR 55-extend: paired input-side range swap | MERGEABLE+CLEAN | **NO (redundant w/ PR 40)** |
| 12 | `pr-56-hand-sort-canonicalization` | fix(parity): hand-string sort-order canonicalization | MERGEABLE+CLEAN | YES |
| 11 | `pr-58-asymmetric-fixture` | test: asymmetric-range sanity regression gate | MERGEABLE+CLEAN | NO (informational) |
| 10 | `pr-55-p0-p1-player-swap` | fix(parity): P0/P1 convention swap | MERGEABLE+CLEAN | YES |
| 9  | `pr-54-renderer-stack-ceiling` | fix(test-renderer): stack_ceiling kwarg | MERGEABLE+CLEAN | YES (folded into PR 53b but listed) |
| 8  | `pr-52-suit-encoding-fix` | fix(parity): suit-encoding bug | MERGEABLE+CLEAN | YES |
| 7  | `pr-53-acceptance-test-reframe` | test(acceptance): reframe original | MERGEABLE+CLEAN | **NO (superseded by PR 53b)** |
| 6  | `pr-51-dcfr-vector-asymmetric-fix` | fix(engine): dcfr_vector.rs off-by-one panic | MERGEABLE+CLEAN | YES |
| 5  | `pr-50-facing-all-in-guard` | fix(engine): facing-all-in action menu guard | MERGEABLE+CLEAN | YES |
| 4  | `pr-49-readme-broken-ref-cleanup` | docs(readme): fix broken cross-ref | MERGEABLE+CLEAN | NO (independent) |
| 3  | `pr-44-dmg-packaging-fix` | fix(packaging): v1.4.0 .dmg | MERGEABLE+CLEAN | NO (carried over) |
| 2  | `pr-48-usage-v1-7-0-semantics` | docs(usage): v1.7.0 aggregator-vs-Nash | MERGEABLE+CLEAN | NO (carried over) |

**All 7 bundle PRs are MERGEABLE+CLEAN on origin.** Per `gh pr list` 2026-05-24.

---

## Phase 3 — Ship script vs corrected bundle

`scripts/ship_v1_7_1.sh`:

| Element | Current state | Needs change? |
|---|---|---|
| Cherry-pick chain (L137-156) | 7 cherry-picks INCLUDING PR 55-ext (`SHA_PR55_EXT=6e545e63`, L71, L149-150) | **YES — drop PR 55-ext (lines 71, 88, 94, 149-150, 234, 331)** |
| Header docstring (L14) | "Cherry-picks PR 51, PR 50, PR 52, PR 55, PR 55-extend, PR 56, PR 53b" | **YES — remove "PR 55-extend"** |
| Pre-exec checklist (L38) | "All 8 PR branches still resolvable on origin" | **YES — 7, not 8** |
| Phase 1 sanity loop (L91-101) | Says "All 7 PR SHAs" but actually loops over 7 (including PR 55-ext) | **YES — change to 6 SHAs after removing PR 55-ext** |
| `git fetch` list (L82-89) | Fetches `pr-55-extend-input-range-swap` | **YES — drop** |
| CHANGELOG body (L234) | Includes "PR 55-extend" entry | **YES — remove** |
| Commit message body (L331) | Lists "PR 55-extend" | **YES — remove** |
| Tag message (L357) | `v1.7.1: ... (PR 50/51/52/55/55-ext/56/53b)` | **YES — drop 55-ext** |
| PR 53b SHA (L77) | `3e50b766` matches origin tip `3e50b76` | OK |
| PR 50/51/52/55/56 SHAs (L67-72) | Match origin branch tips | OK |
| `origin/main` pin (L104) | `3843ce78` — confirmed via `git rev-parse origin/main` = `3843ce7` | OK |

**Ship script must be edited before fire.** It still bundles PR 55-ext, which would reintroduce the R11 double-swap.

---

## Phase 4 — User signon docs alignment

All five user-facing docs reflect the **pre-R11-resolution** state (still describe v1.7.1 as HELD with R11 active, 8-PR bundle). Refresh required before sign-on.

| Doc | R11 framing | Bundle size claimed | v1.7.1 status claimed | Needs refresh? |
|---|---|---|---|---|
| `WELCOME_BACK_USER_2026-05-23.md` | "R11 WARNING — v1.7.1 SHIP HELD" (L10); "Dry-run #8 surfaced R11... AA/TT/88 still diverge 60-75pp" (L12); "DO NOT bash `scripts/ship_v1_7_1.sh`" (L18) | 8 PRs (L28, L57, L67) | HELD pending R11 root cause | **YES — full refresh** |
| `SESSION_TLDR.md` | "Burst extended through R11" (L5); "v1.7.1 ship HELD pending R11 root cause" (L5); reversal chain stated as "R1-R11 (11 reversals)" but framed as engine bug (L5) | 8 PRs (L29) | HELD | **YES — refresh to test-side resolution + 7-PR bundle** |
| `PR_REVIEW_PREP_2026-05-23.md` | (No R11 mention; dated 2026-05-23 — predates R11) | 8 PRs (L29) | Implies clear-to-ship (8 PRs squash-merge) | **YES — drop PR 55-ext line item (L18, L79)** |
| `SIGNON_CHECKLIST.md` | "DO NOT MERGE YET — R11 active" (L9); "v1.7.1 ship HELD" (L13); "Do NOT bash `scripts/ship_v1_7_1.sh`" (L13, L55) | 8 PRs (L13) implied; 9 open PRs (L15) | HELD | **YES — full refresh** |
| `PRE_SIGNON_FAQ.md` | Q11 "What's R11 and why is v1.7.1 held?" (L132); "shipping v1.7.1 with R11 unresolved would put a real engine bug into production" (L151); "PREMATURE" session-close call (L155-157) | 8 PRs (L6, L27, L29) | HELD | **YES — full refresh, including Q11** |

**Pattern:** none of the five docs reflect:
- R11 resolved as test-side (PR 40 + PR 55-ext double-swap)
- Corrected 7-PR bundle (PR 55-ext dropped)
- Kernel verified correct (AA-vs-AA minimal + dcfr_vector re-audit)
- Reversal chain R1-R11 with honest framing (R11 not an engine bug after all)

The fresh status doc `STATUS_2026-05-24_r11_resolved.md` carries the corrected framing but the user signon docs have not been re-synced from it.

---

## Phase 5 — Recommendation

**SHIP-READY conditional on three actions in this order:**

1. **Land dry-run #9** (the corrected-bundle empirical check). Per `STATUS_2026-05-24_r11_resolved.md` L5+L109 it is "in flight". Need its result file in `docs/` and a clear depth-0 PASS verdict.
2. **Edit `scripts/ship_v1_7_1.sh`** to drop PR 55-ext (8 sites enumerated in Phase 3 table).
3. **Refresh the five user signon docs** to reflect (a) R11 resolved as test-side, (b) 7-PR bundle, (c) kernel verified, (d) honest reversal chain R1-R11.

**If dry-run #9 passes:** ship via the (edited) script.

**If dry-run #9 fails at depth-0:** PR 40 vs PR 55-ext sense of the swap may be inverted. Per `STATUS_2026-05-24_r11_resolved.md` L87: "If dry-run #9 still shows depth-0 divergence → R11 reopens; the convergence chain was incomplete." In that case the alternative is to revert PR 40 (already merged in `origin/main` at commit `988c3fc`) instead of excluding PR 55-ext — i.e. keep the wrapper-side swap, drop the test-side swap.

**If neither swap-revert helps:** kernel claim needs re-examination — re-run AA-vs-AA minimal with the actual v1.7.1 bundle applied (not stock origin/main + v1.7.0), and bisect each PR's individual contribution to depth-0 AA/TT/88.

---

## Verdict

**DEPENDS-ON-DRY-RUN-9.**

- Kernel: VERIFIED CORRECT (Phase 1).
- Bundle composition: CORRECT on paper (Phase 2; 7 PRs all MERGEABLE+CLEAN).
- Ship script: NEEDS-EDIT (Phase 3; still bundles PR 55-ext).
- User docs: NEEDS-REFRESH (Phase 4; all five docs stale).
- Dry-run #9: NOT YET LANDED (Phase 5).

Even if dry-run #9 passes immediately, the ship script edit and the doc refresh are blockers before user sign-on. Recommended sequencing: dry-run #9 → ship script edit → doc refresh → user sign-on → fire script.

---

## State at a glance

| Item | Value |
|---|---|
| Origin HEAD | `3843ce7` (v1.7.0) — unchanged, matches script pin |
| Latest tag | `v1.7.0` |
| Open PRs on origin | 13 (7 in bundle, 6 not) |
| Corrected bundle | 7 PRs (PR 50, 51, 52, 53b, 54, 55, 56) |
| Ship script bundle | 8 PRs (includes PR 55-ext — stale) |
| Kernel | verified correct (AA-vs-AA minimal + dcfr_vector re-audit) |
| R11 status | resolved test-side per `STATUS_2026-05-24_r11_resolved.md` |
| Dry-run #9 | in flight; result not yet in `docs/` |
| User signon docs | all five reflect pre-R11-resolution framing |
| Verdict | **DEPENDS-ON-DRY-RUN-9** with ship-script + docs touch-ups required |
