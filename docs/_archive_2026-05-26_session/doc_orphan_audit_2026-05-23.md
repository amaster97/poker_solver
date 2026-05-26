# Doc Orphan Audit — 2026-05-23

**Scope:** all `docs/**/*.md` modified in the last 24 hours.

**Nav corpus checked:**
- `/Users/ashen/Desktop/poker_solver/PLAN.md`
- `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-23_*.md` (4 files)
- `/Users/ashen/Desktop/poker_solver/docs/WELCOME_BACK_USER_2026-05-23.md`
- `/Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/*.md` (31 files)

**Method:** Substring search of each session-end doc's basename, repo-relative path, and docs-relative path against the combined corpus.

**Constraints honored:** Read-only; no edits to source docs; recommendations only.

---

## Headline numbers

| Metric | Count |
|---|---|
| Total session-end docs | **226** |
| Linked from >=1 nav doc | **32** |
| Orphaned (no nav reference) | **194** |
| Nav-hub docs (self, not orphans) | 2 |
| **True orphans** (excluding nav hubs) | **192** |

Linked ratio: **14%** (32 / 226). The mass of session output is not discoverable from PLAN.md / STATUS / WELCOME_BACK / MEMORY.

---

## Orphans by category

| Category | Count | Notes |
|---|---:|---|
| `pr<N>_prep/*` historical artifacts | 33 | Most are from prior PRs (PR 8 / 9 / 10b / 11 / 13). Intentionally archived; PR boundary closes the topic. |
| `persona_test_results/*` retest data | 31 | The raw retest data. PLAN §Status references some by version (e.g. v1.7.0 retest), but the individual W*_v*_retest files are not directly linked. Intentionally archived for now; only the post-R5 reclassification rolls forward. |
| `pr_proposals/*` design notes | 28 | Historical proposals (v1.3 → v1.7). Most are decision-archived; the future-facing `v1_8_neon_vector_kernels_spec.md` IS linked. |
| `*audit*` / `*verification*` / `*consistency*` | 25 | Mostly session-bound hygiene checks. Some are the audit doc this session ran (e.g. `audit_docs_cross_reference_check.md`). |
| `OTHER` (misc reports/profiles/fix specs) | 23 | Mixed bag — needs case-by-case review (see below). |
| `leg*_v*_ship_*` (plan + report) | 20 | Per-leg ship docs (leg6 → leg21). PLAN.md §Status carries forward the version ladder but doesn't link per-leg artifacts. |
| `integration_*` / `*_sync` / `*_push_*` | 12 | Session-bound integration/sync reports. Not load-bearing once ladder advances. |
| `*_diagnosis` / `*_investigation` / `*_recovery` | 8 | Some are linked from PLAN (e.g. `archived_claims_2026-05-23.md`); others are local-only. |
| `v1_*_ship_*` / `v1_*_release_*` / `v1_*_synthesis` | 5 | Ship orchestration docs (sequences, merge order). Session-bound. |
| `comprehensive_review_2026-05-23-*.md` | 4 | Successive review snapshots (morning, late, night, final). Chronicled into STATUS docs but the files themselves aren't linked. |
| README / changelog / strip-and-soften edits | 3 | Edit-record docs; outputs already landed in README/CHANGELOG. |
| NAV_HUB_SELF | 2 | `STATUS_2026-05-23_post_retest_5th_reversal.md`, `WELCOME_BACK_USER_2026-05-23.md` — these ARE the nav hubs; not actually orphans. |

---

## Triage: which orphans are intentional vs need a landing place?

### Intentionally private (no action needed) — ~165 docs

These are session-ephemera or archive material that the user shouldn't need to navigate to:

- **All `pr<N>_prep/*`** — historical PR artifacts. The PR is shipped; preserved for audit trail.
- **All `persona_test_results/W*_v*_retest.md`** — raw per-version retest data. PLAN.md tracks PASS/FAIL by version; individual files are the receipts.
- **Most `pr_proposals/*`** — design notes that either landed (so the PR itself is the record) or were refuted (decision lives in archived_claims).
- **All `comprehensive_review_*` snapshots** — superseded by the next snapshot; final state lives in STATUS docs.
- **`leg*_ship_plan.md` and `leg*_ship_report.md`** — the version ladder in PLAN.md §Status is the canonical roll-up; per-leg docs are receipts.
- **Session-bound hygiene** (`midsession_hygiene_check.md`, `state_consistency_audit_*.md`, `*_post_sync_*`, `task_list_review_*`) — point-in-time checks; the answer either rolled into STATUS or was never material.
- **Integration / push / mirror reports** — once the next ladder advance happens, prior sync reports are stale.

### Genuinely useful — should be linked (top candidates)

These 8 orphans are referenced indirectly (by topic) in nav docs but the files themselves aren't linked, and they contain durable findings:

| Orphan | Why it matters | Recommended landing |
|---|---|---|
| `kk_fold_inversion_diagnosis.md` | KK river fold=0.9998 math diagnosis — referenced by W2.3 caveat; the math is durable. | PLAN.md §Known bugs OR STATUS §Known bugs |
| `v1_7_0_nash_path_perf_profile.md` | Sarah's multi-street envelope perf data — explains why W2.1 is Type D timeout. | PLAN.md §Persona retests (where W2.1 Type D is noted) |
| `pr_23_cell_divergence_deep_dive.md` | Deep-cap K72 algorithmic findings — supports the Path D rationale. | PLAN.md §Status (where Path D is discussed) — or link from `archived_claims_2026-05-23.md` |
| `aggregator_vs_true_nash_explainer.md` | Already linked (in linked set). No action. |
| `pr_23_deep_cap_algorithmic_triage.md` | Triage that led to Path D — pairs with `v1_6_1_path_d_decision.md` (which IS linked). | Cross-link from `v1_6_1_path_d_decision.md` (linked) — make it findable via the linked chain. |
| `pytest_pyenv_arch_quirk_2026-05-23.md` | pyenv shim arm64 workaround — recurring tooling quirk, lessons-learned material. | STATUS §Meta-lesson or a memory note (e.g. `feedback_pyenv_arch_quirk.md`) |
| `v1_5_slider_tier_defaults_measured.md` | Empirical tier-boundary measurements — load-bearing for PLAN.md §1 "Tier boundaries are empirical". | PLAN.md §1 stack-depth table — add reference link |
| `gate_4_operational_plan.md` | Already linked. No action. |
| `autonomous_burst_release_plan.md` | Multi-leg ship plan that drove the burst. Superseded by per-leg ship plans but the meta-plan is useful retrospect. | STATUS §"Shipped this session" or memory |
| `untested_workflow_readiness_audit.md` | Audit of which persona workflows haven't been tested post-v1.7.0. Gates the Gate 3 close. | PLAN.md §Persona retests |
| `dcfr_perf_regression_bisection_2026-05-23.md` | DCFR perf bisection findings — relevant to the v1.7.x perf story. | PLAN.md §Status (perf) OR linked from `v1_7_0_nash_path_perf_profile.md` |
| `river_parity_timeout_investigation_2026-05-23.md` | River parity timeout root cause — recurring class of bug. | PLAN.md §Known bugs |
| `heuristic_judgement_audit_2026-05-23.md` | Audit of heuristic judgement calls; meta-discipline. | Memory note (alongside `feedback_label_vs_semantics.md`) |
| `pr_46_dcfr_panic_fix_report.md` | DCFR panic fix — bug report, post-mortem. | PLAN.md §Status (bugs fixed) or archived_claims |
| `venv_shadow_audit.md` | Shadow-venv issue — tooling hazard. | Memory note (tooling) |

### Edge cases — defensible either way (~19)

- `audit_docs_cross_reference_check.md` — this is itself a prior version of this audit. Could link from STATUS but probably superseded by this very doc.
- `final_consistency_audit_2026-05-23.md` + `final_consistency_audit.md` — duplicated names suggest one is stale; both orphaned.
- `release_docs_consistency_check.md`, `changelog_consistency_audit.md` — session-bound, not load-bearing once next ship advances.
- `doc_walkback_3rd_reversal_2026-05-23.md`, `state_verification_2026-05-23-late.md`, `state_consistency_audit_2026-05-23-late.md` — the 5th reversal STATUS supersedes them.
- `wake_up_brief_2026-05-23.md`, `session_shipped_2026-05-23.md`, `task_list_review_2026-05-23-late.md` — session-handoff scaffolding; superseded by WELCOME_BACK_USER + STATUS.
- `PR_REVIEW_PREP_2026-05-23.md` — PR review checklist for the 3 open PRs on amaster97/poker_solver. Probably worth surfacing in STATUS §In flight if those PRs are still pending.

---

## Per-orphan recommended landing (top 15)

Ordered by signal-to-noise (highest first):

| # | Orphan | Landing recommendation |
|---:|---|---|
| 1 | `kk_fold_inversion_diagnosis.md` | PLAN.md §Known bugs (post-R5) — add as bullet under W2.3 KK fold inversion |
| 2 | `v1_7_0_nash_path_perf_profile.md` | PLAN.md §Status — paragraph on W2.1 Type D timeout currently mentions the symptom; cite this profile as the evidence |
| 3 | `untested_workflow_readiness_audit.md` | PLAN.md §Persona retests — Gate 3 close requires this audit's checklist |
| 4 | `v1_5_slider_tier_defaults_measured.md` | PLAN.md §1 stack-depth table — caption "Tier boundaries are empirical" should cite this |
| 5 | `pr_23_cell_divergence_deep_dive.md` | `docs/archived_claims_2026-05-23.md` §1 (deep cap convention) — already linked from PLAN, so the chain reaches it |
| 6 | `pr_23_deep_cap_algorithmic_triage.md` | Same as above — cross-link from `v1_6_1_path_d_decision.md` (already linked) |
| 7 | `dcfr_perf_regression_bisection_2026-05-23.md` | PLAN.md §Status perf section, or link from item #2 above |
| 8 | `river_parity_timeout_investigation_2026-05-23.md` | PLAN.md §Known bugs |
| 9 | `pr_46_dcfr_panic_fix_report.md` | STATUS §"Shipped this session" or §Known bugs (resolved) |
| 10 | `pytest_pyenv_arch_quirk_2026-05-23.md` | New memory note `feedback_pyenv_arch_quirk.md` — recurring tooling hazard |
| 11 | `heuristic_judgement_audit_2026-05-23.md` | Memory — pairs with `feedback_label_vs_semantics.md` |
| 12 | `venv_shadow_audit.md` | Memory — tooling hazards bundle |
| 13 | `PR_REVIEW_PREP_2026-05-23.md` | STATUS §AWAITING USER (if those amaster97 PRs are still open) |
| 14 | `autonomous_burst_release_plan.md` | STATUS §"Shipped this session" as a retrospective anchor (low priority) |
| 15 | `pr44_completion_report.md` + `pr44_dmg_fix_spec.md` + `pr44_dmg_rebuild_report.md` + `pr44_fix_audit.md` | PLAN.md §Status — PR 44 .dmg packaging fix is already mentioned ("PR 44 .dmg packaging fix verified on `pr-44-dmg-packaging-fix` @ `c09abe7`") but specs/reports aren't cited. Cite at least the completion_report. |

The remaining ~177 orphans are session-bound or archive-by-design and **don't need linking**.

---

## Verdict

**GAPS-IDENTIFIED** (not blocking).

- **14% link ratio** reflects the volume of receipt/audit/leg-ship docs that are intentionally PR-bound rather than navigationally surfaced — that's by design and not a problem.
- **~15 high-signal orphans** contain durable findings (bugs, perf data, empirical measurements, tooling quirks) that the user *would* benefit from finding via PLAN/STATUS, and currently can't.
- Two nav-hub docs (STATUS_5th_reversal, WELCOME_BACK_USER) self-orphan because they aren't referenced from peers; that's expected for hubs.
- No critical findings are buried — bugs are captured in PLAN.md §Status or archived_claims; the gap is depth-of-evidence, not surface-level visibility.

**Recommended follow-up (separate task):** add ~6-8 inline references to PLAN.md/STATUS for the top-priority orphans above (KK diagnosis, Nash perf profile, untested workflows, slider tier measurements, pr_46 fix, pyenv quirk memory). Do NOT bulk-link the leg/persona/pr_prep archives — those are working as intended.
