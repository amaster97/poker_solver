# Comprehensive Consistency Review — 2026-05-23

**Scope:** Tier 1 (PLAN/README/USAGE/DEVELOPER/CONTRIBUTING/CHANGELOG), Tier 2 (`docs/pr_proposals/`, `docs/pr13_prep/`), Tier 3 (`MEMORY.md` index + all memory files).
**Constraint:** Surgical, non-conflicting edits; CHANGELOG / pyproject / `__init__.py` / `persona_acceptance_spec.md` are off-limits.

---

## Section 1 — State snapshot

### Actually shipped (`git tag` + commit log)

| Tag | Commit | What |
|---|---|---|
| v0.6.0 | `87c5e7f` | PR 10a NiceGUI scaffold + mock solver |
| v0.6.1 | `8386a68` | PR 10a.5 UI conformance pass |
| v1.0.0 | `314a459` | PR 11 GA — library + macOS .dmg |
| v1.0.1 | `e9156a8` | PR 8 NEON SIMD + cache layout + PCS infra (PATCH; 10x gate NOT MET; PR 8b parked) |
| v1.1.0 | `ddbd7a1` | PR 9 HUNL preflop subgame solver + equity-leaf |
| v1.2.0 | `1ddb75b` | PR 10b real-solver UI bindings |
| v1.2.1 | `1c92032` | universal2 `_rust.so` patch |
| v1.3.0 | `ee709b2` | PR 16 Pluribus-blueprint range-vs-range aggregator |

### In flight (NOT shipped)

- **LEG 5 / v1.3.0 revert.** Tag exists at `ee709b2`; working-tree staged changes roll back: `__version__` + `pyproject` `1.3.0 → 1.1.0`; `range_aggregator.py` + tests deleted; CHANGELOG `[1.3.0]` + `[1.2.1]` stripped; USAGE.md §5 RvR removed; `ui/state.py`, `tests/test_ui_smoke.py`, `hunl_solver.py`, `preflop.py` modified.
- **Plan C / Stage C1.** Prompts: `v1_3_plan_c_prompt.md` (Rust vector-form BR, < 30 s gate, 5–7 days) and `v1_3_stage_c1_prompt.md` (numpy slab, v1.3.1 PATCH, 1–2 days, 22.4× target).

### Deferred

- PR 8b (FlatInfosetStore primary-wire); PR 12 (3-handed); Option A (Rust BR port, superseded); true Nash RvR via chance-enum.

---

## Section 2 — Drift per Tier 1 doc

### PLAN.md — HEAVILY STALE (recommended for orchestrator)

L3 status: "PR 1-7 + 3.5 + 3.5-followup + 4.5 + 10a + 10a.5 + 11 landed" — pre-PR-8 era; PR 8/9/10b/16 all shipped since. L3 main at `62c75d5` — main is at `58b1ebd` (~13 commits stale). L5 "PR 10a.5 landed locally" — shipped as v0.6.1. L7 "PR 8 + PR 9 implementers still in flight" — both shipped. L96-97 PR table: PR 8, PR 9 marked `📋 spec'd` — both shipped. L100: PR 10b marked `📋 spec'd` — shipped at v1.2.0. L124-126 post-GA sequencing: all 4 PRs labeled in-flight — all shipped. L232 integration tip `9936d5f` — integration is at `0ea83e1`. L246 GA callout lists PR 8 / 9 / 10b as "remaining" — shipped. L300, L302 sequencing intent stale. MISSING: LEG 5, Plan C, Stage C1, v1.3 RvR, persona acceptance harness + Phase 1/2 results, persona-time-budget rubric, v1.3 validation gate.

### README.md — MODERATELY STALE

L18 "Current version: 1.0.0 (GA)" — should reflect current tag. L11-14 v1.0.0 release callout — historical, fine to keep but outdated as state-of-art claim. L75-79 "NiceGUI app (mock-first scaffold)" — PR 10b shipped at v1.2.0, banner copy is wrong. L87-92 "What's coming next" — names PR 10a.5/8/9/10b as upcoming; all shipped. L97-98 "raises NotImplementedError today, pointing at PR 9" — v1.1.0 shipped preflop subgame solver; full-tree preflop still pending. L179, L186-190 mock-mode section + banner copy — stale.

### USAGE.md — STALE; LEG 5 partially addresses

L1 "(v1.0.0)" header — version sticker stale; LEG 5 staged changes do not update this. L41-50 ".dmg" path — references v1.0.0 only; should mention v1.2.1 universal2. L149-171 "## 4. The UI (currently mock mode)" — stale post-v1.2.0; LEG 5 staged USAGE.md keeps this block. L208-243 "Known limitations (v1.0.0)" + "What's coming" — references PR 9 / PR 10b as future, both shipped. LEG 5 reverts USAGE.md to pre-v1.3.0 form (drops §5 RvR section, renumbers, re-introduces "PR 9 ... ~2 weeks" framing) — that's a regression but in line with the v1.3.0 revert posture.

### DEVELOPER.md — MILDLY STALE

L60 ui/ cell: "(mock-backed today; a future PR swaps in real solver)" — stale post-v1.2.0. L243-246 "Where to go next" lists PR 8 / PR 9 / PR 10b items — all delivered.

### CONTRIBUTING.md — STABLE

No staleness. Locked decisions and PR-flow contract intact.

### CHANGELOG.md — OFF-LIMITS (LEG 5 owns)

---

## Section 3 — Drift per Tier 2 doc

- **`v1_3_range_vs_range.md`** — L3 "Draft proposal. Ships after v1.2.0" + L90-99, L144-149 "Ship Option A, defer B" — directly contradicted by reality (Option B shipped at v1.3.0, then reverted; Option A never implemented). L171-174 cites four in-flight PRs — all shipped.
- **`v1_3_research_alternatives.md`** — research summary; reasonable as-is. L141 recommendation predates Plan C promotion.
- **`v1_3_plan_c_verification.md`** — internally consistent; current.
- **`v1_3_stress_tests.md`** — L4 trigger "Apply when Option A AND Option B both ship" — obsolete; Plan C is the live path.
- **`v1_3_plan_c_prompt.md`**, **`v1_3_stage_c1_prompt.md`** — internally consistent, current.
- **`persona_time_budgets.md`** + **`persona_acceptance_spec.md`** + **`rectification_framework.md`** — all post-rubric-recalibration; consistent.
- **`v1_3_validation_gate.md`** — §3 Per-option thresholds still references Option A as live; Option A was never implemented and Plan C now occupies that slot.
- **`usage_md_v1_3_0_update.md`** — PRE-STAGED file; assumes `solve_range_vs_range` ships. LEG 5 reverts it, so these pre-staged edits should not be applied.

---

## Section 4 — Drift per memory file

- **`MEMORY.md`** L18-19 — descriptions of `post_v1_ga_status.md` + `post_ga_parallel_launch.md` describe "four in-flight PRs"; all four shipped weeks ago.
- **`post_v1_ga_status.md`** — entire file is the "in-flight" snapshot; retirement trigger (own L37) met.
- **`post_ga_parallel_launch.md`** — same; explicit retirement trigger met (L42).
- **`project_solver.md`** L33-55 "Status as of 2026-05-22" — describes PR 10a.5/8/9 as in-flight, PR 10b as staged; all shipped.
- **`reference_planfile.md`** L14-16 — "v1.0.0 GA landed ... Four post-GA PRs in flight"; stale.
- All `feedback_*.md` files (process / discipline rules) — current.

---

## Section 5 — Cross-doc contradictions

1. **v1.3.0 ship state.** Tag exists (`git tag` + CHANGELOG); LEG 5 reverts it; user instruction context says "in flight"; proposal docs claim Option A was the planned ship (it wasn't). Multi-doc disagreement.
2. **Range-vs-range capability.** `usage_md_v1_3_0_update.md` claims `solve_range_vs_range` ships with 24s/79s timings; LEG 5 USAGE.md removes it; `v1_3_range_vs_range.md` claims Option A is shipping. Reality: blueprint aggregator landed then reverted; live recommendation is Plan C / Stage C1.
3. **Current version sticker.** `pyproject.toml`/`__init__.py` (HEAD) say `1.3.0`; staged say `1.1.0`; README + USAGE say `1.0.0`. All four out of phase.
4. **UI mock-mode.** CHANGELOG `[1.2.0]` documents PR 10b mock→real swap; README L75-79 + L179-190, USAGE §4, DEVELOPER L60 all still say UI is mock-mode.
5. **PR 8 perf gate.** CHANGELOG `[1.0.1]` says 10x gate NOT MET; PLAN.md treats PR 8 as not-yet-started.
6. **"PR 10a.5 not yet on main."** PLAN.md L3/L99 says so; CHANGELOG ships `[0.6.1]`; PR 10a.5 is long-since merged.

---

## Section 6 — Surgical fixes APPLIED

10 edits applied; cap respected.

| # | File | Change | Status |
|---|---|---|---|
| 1 | `README.md` L18 | Replace stale "1.0.0 (GA)" line with CHANGELOG cross-ref | APPLIED |
| 2 | `README.md` L97-98 | Drop "pointing at PR 9" — v1.1.0 shipped preflop subgame | APPLIED |
| 3 | `DEVELOPER.md` L60 | Update ui/ cell to v1.2.0 real-solver bindings | APPLIED |
| 4 | `DEVELOPER.md` §10 | Replace PR 8/9/10b items with Plan C / node-locking / full-tree preflop | APPLIED |
| 5 | `v1_3_range_vs_range.md` Status header | Mark SUPERSEDED; point to Plan C / Stage C1 | APPLIED |
| 6 | `v1_3_research_alternatives.md` §4 recommendation | Append post-LEG-5 note (Plan C promoted from Rank 1) | APPLIED |
| 7 | `v1_3_stress_tests.md` Status | Update trigger to Plan C / Stage C1 | APPLIED |
| 8 | `MEMORY.md` L18-19 | Mark `post_v1_ga_status.md` + `post_ga_parallel_launch.md` STALE | APPLIED |
| 9 | `project_solver.md` Honest gaps | Acknowledge PR 9 / PR 10b shipped; flag Plan C in flight | APPLIED |
| 10 | `reference_planfile.md` Repo state | Refresh baseline to v1.2.1 + Plan C in flight | APPLIED |

---

## Section 7 — Larger reconciliations flagged for orchestrator

1. **PLAN.md §2 PR roadmap table** — needs rows for PR 8 / 9 / 10b / 16 (universal2) / 17 (Plan C) / 18 (Stage C1) with shipped status; current state describes PR 8/9/10b as `📋 spec'd`. Hold until LEG 5 stabilizes so the v1.3.0 row reflects ground truth.
2. **PLAN.md L3-7 Status/Branch state** — full rewrite needed.
3. **PLAN.md §6 retro** — add v1.3.0 + LEG 5 + Plan C decision narrative + persona-acceptance findings.
4. **PLAN.md §7 Kickoff docs staged** — add PR 15 / 16 / 17 / 18; current list stops at PR 12.
5. **README.md "What's coming next" + "Features (v1.0)"** — needs full pass once LEG 5 lands.
6. **USAGE.md** — three-part rewrite: (a) header version, (b) §4 UI mock-mode section reframed, (c) §6 known limitations cleared + §7 what's-coming pruned. Hold until LEG 5 lands.
7. **`post_v1_ga_status.md` + `post_ga_parallel_launch.md`** — both files explicitly say "retire once all 4 in-flight PRs are merged"; trigger met. Spawn memory-retirement / consolidation agent.
8. **`project_solver.md` §"Status as of 2026-05-22"** — refresh to 2026-05-23 post-LEG-5 once it lands.
9. **`v1_3_range_vs_range.md` Section 5** — Status header (Fix 5) flags it, but the body still recommends Option A; archival or rewrite needed.
10. **`v1_3_validation_gate.md` §3 Per-option thresholds** — Option A is defunct; replace with Plan C / Stage C1 framing.
11. **PLAN.md §1 solver UI control** — defaults are TBD "until measurement pass runs after PR 10b lands"; PR 10b shipped, measurement pass is now actionable.
12. **CHANGELOG `[Unreleased]` post-LEG-5** — needs Plan C / Stage C1 forward entry. CHANGELOG is LEG 5's; surface to orchestrator on LEG 5 sign-off.

---

## Section 8 — Verdict

**Verdict: NEEDS-USER-REVIEW.**

PLAN.md is the worst offender — multiple sections describe a pre-PR-8 reality. The memory subsystem has two files (`post_v1_ga_status.md`, `post_ga_parallel_launch.md`) whose own retirement triggers are met; both should be consolidated. The v1.3 PR proposals contradict reality on which option shipped. CONTRIBUTING.md, the locked-decisions sections of PLAN.md + project_solver.md, and the persona-time-budget / rectification framework subsystem remain accurate; drift is concentrated in status / roadmap / sequencing layers.

**Most consequential contradiction worth surfacing:** v1.3.0 ship state. The tag exists, CHANGELOG documents it as shipped, LEG 5 is rolling it back, but proposal docs still claim Option A was the chosen path (it wasn't). User decision needed on what "v1.3.0" means after LEG 5 — was it shipped + reverted (next ship is v1.3.1 or v1.4.0), or is the tag itself being deleted? This affects everything downstream including release-notes copy and version stickers across README / USAGE.
