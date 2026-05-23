# Doc inventory + maintainability scan

**Generated:** 2026-05-22 (session calendar; all docs live in a session < 3 days old)
**Scope:** every `.md` under `/Users/ashen/Desktop/poker_solver/docs/`, every `.md` at repo root, every `.md` under `/Users/ashen/Desktop/poker_solver/.github/`, plus the user-memory index at `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md`.

**Totals:**
- docs directory: 90 files / 33,574 lines
- repo root + .github: 8 files / 992 lines
- **grand total: 98 markdown files / 34,566 lines**

---

## 1. Doc inventory

### 1.1 Repo root + `.github/`

| Path | Lines | Last modified | Purpose |
|---|---|---|---|
| `/Users/ashen/Desktop/poker_solver/README.md` | 238 | 2026-05-21 | Public face — v0.3 feature list, status, license, install |
| `/Users/ashen/Desktop/poker_solver/CHANGELOG.md` | 208 | 2026-05-21 | Keep-a-Changelog format; Unreleased + 0.3.0 + 0.3.1 |
| `/Users/ashen/Desktop/poker_solver/PLAN.md` | 271 | 2026-05-22 | Locked decisions, scope, dispatch composition, per-PR roadmap |
| `/Users/ashen/Desktop/poker_solver/CONTRIBUTING.md` | 117 | 2026-05-21 | Branch policy, audit gate, license rules for contributors |
| `/Users/ashen/Desktop/poker_solver/pr_report.md` | 31 | 2026-05-21 | Auto-generated check-battery report (PR 3 era; pre-cleanup state) |
| `/Users/ashen/Desktop/poker_solver/.github/PULL_REQUEST_TEMPLATE.md` | 44 | 2026-05-21 | PR template (audit + license + diff-test checklist) |
| `/Users/ashen/Desktop/poker_solver/.github/ISSUE_TEMPLATE/bug_report.md` | 44 | 2026-05-21 | Bug-report template |
| `/Users/ashen/Desktop/poker_solver/.github/ISSUE_TEMPLATE/feature_request.md` | 39 | 2026-05-21 | Feature-request template |

### 1.2 `docs/` — session-level / cross-PR

| Path | Lines | Last modified | Purpose |
|---|---|---|---|
| `docs/architecture.md` | 389 | 2026-05-21 | Mermaid diagrams + module map; dispatch composition + data flow |
| `docs/autonomous_log.md` | 200 | 2026-05-21 | Per-decision audit trail (S/D/I/B/N codes) |
| `docs/autonomous_decisions_2026-05-22.md` | 44 | 2026-05-22 | Decisions locked in 2026-05-22 round (UI defaults, PR 5 ship policy) |
| `docs/card_removal_investigation.md` | 409 | 2026-05-21 | Blocker / card-removal correctness audit ("continue as is") |
| `docs/competitor_landscape.md` | 152 | 2026-05-20 | Solver-market snapshot (Pio / GTOW / OSS); positioning |
| `docs/cross_doc_consistency_check.md` | 209 | 2026-05-22 | 2026-05-22 cross-spec audit (zero material findings) |
| `docs/integration_test_scaffolds.md` | 794 | 2026-05-21 | 18 cross-PR integration test stubs (skip-marked) |
| `docs/pr_launch_runbook.md` | 591 | 2026-05-21 | Universal per-PR launch sequence (PRs 4–12) |
| `docs/pushfold_v1_generation_notes.md` | 193 | 2026-05-21 | Generator pipeline notes for `pushfold_v1.json` |
| `docs/release_notes_v0.3.md` | 258 | 2026-05-21 | v0.3.0 "HUNL substrate" release notes |
| `docs/release_notes_v0.3.1.md` | 162 | 2026-05-21 | v0.3.1 patch release notes (sparse-JSON + dispatch fixes) |
| `docs/roadmap_status_2026-05-22.md` | 143 | 2026-05-22 | Snapshot — PR 1–4 shipped, PR 5 uncommitted, PR 6–12 spec'd |
| `docs/rust_orientation.md` | 154 | 2026-05-20 | Rust-zero → Rust-productive 3–5 day primer for the user |
| `docs/session_pause_2026-05-21.md` | 91 | 2026-05-21 | Mid-session pause snapshot (likely now obsolete) |
| `docs/spec_consistency_review.md` | 210 | 2026-05-21 | v1 cross-spec audit (B/I-level findings) |
| `docs/spec_consistency_review_v2.md` | 133 | 2026-05-21 | v2 round — resolution status of v1 findings + new drift |
| `docs/wake_up_brief.md` | 150 | 2026-05-21 | Executive summary for user on wake (PR 3 shipped, PR 3.5 in flight) |

### 1.3 `docs/prN_prep/` — per-PR prep packs

**Standard pack per PR (template):** `prN_spec.md`, `agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md`, `audit_prompt.md`. Per-PR extras (audit reports, summaries, research notes, launch-readiness reports) are listed inline.

| PR | File | Lines | Last modified | Purpose |
|---|---|---|---|---|
| 3 | `pr3_prep/pr3_spec.md` | 451 | 2026-05-21 | Spec — HUNL tree builder + 14-action abstraction |
| 3 | `pr3_prep/hunl_tree_size_estimate.md` | 368 | 2026-05-20 | Back-of-envelope tree size / RAM estimate |
| 3 | `pr3_prep/postflop_solver_tree_notes.md` | 412 | 2026-05-20 | AGPL read-only study of postflop-solver tree builder |
| 3 | `pr3_prep/open_spiel_noambrown_notes.md` | 496 | 2026-05-20 | open_spiel + noambrown HUNL state comparison |
| 3 | `pr3_prep/agent_a_interface_concerns.md` | 38 | 2026-05-21 | Post-PR-3 interface-drift notes (resolved) |
| 3 | `pr3_prep/audit_report.md` | 164 | 2026-05-21 | PR 3 audit — READY, 0 must-fix |
| 3.5 | `pr3_5_prep/pr3_5_spec.md` | 359 | 2026-05-21 | Spec — push/fold charts (2–15 BB) |
| 3.5 | `pr3_5_prep/audit_prompt.md` | 170 | 2026-05-21 | Auditor prompt |
| 3.5 | `pr3_5_prep/audit_report.md` | 139 | 2026-05-21 | Audit — initially NOT-READY (6 must-fix); follow-up fixed |
| 3.5 | `pr3_5_prep/ready_to_commit_summary.md` | 168 | 2026-05-21 | Pre-commit synthesis (files, tests, ETA) |
| 4 | `pr4_prep/pr4_spec.md` | 460 | 2026-05-21 | Spec — EMD card abstraction 256/128/64 + suit-iso |
| 4 | `pr4_prep/agent_a_prompt.md` | 457 | 2026-05-21 | Equity features + EMD |
| 4 | `pr4_prep/agent_b_prompt.md` | 625 | 2026-05-21 | Bucket lookup + persistence + HUNL integration |
| 4 | `pr4_prep/agent_c_prompt.md` | 288 | 2026-05-21 | Tests |
| 4 | `pr4_prep/audit_prompt.md` | 174 | 2026-05-21 | Auditor prompt |
| 4 | `pr4_prep/audit_report.md` | 114 | 2026-05-21 | Audit — READY, 0 must-fix |
| 4 | `pr4_prep/postflop_solver_emd_patterns.md` | 611 | 2026-05-21 | AGPL read-only EMD pattern study |
| 4 | `pr4_prep/launch_readiness_report.md` | 326 | 2026-05-21 | Pre-launch alignment check (3 patches) |
| 4 | `pr4_prep/launch_alignment_v2.md` | 266 | 2026-05-21 | Re-check after patches |
| 4 | `pr4_prep/ready_to_commit_summary.md` | 175 | 2026-05-21 | Pre-commit synthesis |
| 5 | `pr5_prep/pr5_spec.md` | 591 | 2026-05-21 | Spec — HUNL postflop solve + memory profiler |
| 5 | `pr5_prep/agent_a_prompt.md` | 392 | 2026-05-21 | Solver orchestrator |
| 5 | `pr5_prep/agent_b_prompt.md` | 506 | 2026-05-21 | Memory profiler |
| 5 | `pr5_prep/agent_c_prompt.md` | 357 | 2026-05-21 | Tests |
| 5 | `pr5_prep/audit_prompt.md` | 163 | 2026-05-21 | Auditor prompt |
| 5 | `pr5_prep/audit_report.md` | 323 | 2026-05-22 | Audit — 1 must-fix + should-fix list |
| 5 | `pr5_prep/commit_message_draft.md` | 136 | 2026-05-22 | Commit message draft |
| 5 | `pr5_prep/pre_commit_checklist.md` | 157 | 2026-05-22 | Go/no-go gate before `git commit` |
| 6 | `pr6_prep/pr6_spec.md` | 787 | 2026-05-22 | Spec — Rust port of HUNL postflop |
| 6 | `pr6_prep/agent_a_prompt.md` | 562 | 2026-05-22 | Rust trainer + DCFR mechanics |
| 6 | `pr6_prep/agent_b_prompt.md` | 617 | 2026-05-22 | Abstraction loader (Rust) + PyO3 glue |
| 6 | `pr6_prep/agent_c_prompt.md` | 535 | 2026-05-22 | Diff-test fixtures + parity tests |
| 6 | `pr6_prep/audit_prompt.md` | 191 | 2026-05-22 | Auditor prompt |
| 6 | `pr6_prep/MUST_PATCH_BEFORE_LAUNCH.md` | 22 | 2026-05-22 | Pre-launch blocker list (shape drift, dispatch invariant) |
| 6 | `pr6_prep/launch_readiness_v2.md` | 132 | 2026-05-22 | Pre-launch check — failures listed |
| 6 | `pr6_prep/launch_readiness_v3.md` | 106 | 2026-05-22 | Post-patch re-check — READY |
| 7 | `pr7_prep/pr7_spec.md` | 306 | 2026-05-21 | Spec — river-spot diff vs noambrown |
| 7 | `pr7_prep/agent_a_prompt.md` | 576 | 2026-05-21 | Diff harness setup |
| 7 | `pr7_prep/agent_b_prompt.md` | 347 | 2026-05-21 | Per-spot tolerance enforcement |
| 7 | `pr7_prep/agent_c_prompt.md` | 340 | 2026-05-21 | Fixture import + tests |
| 7 | `pr7_prep/audit_prompt.md` | 189 | 2026-05-21 | Auditor prompt |
| 8 | `pr8_prep/pr8_spec.md` | 504 | 2026-05-21 | Spec — NEON SIMD + cache-blocking + PCS |
| 8 | `pr8_prep/agent_a_prompt.md` | 376 | 2026-05-21 | SIMD kernel |
| 8 | `pr8_prep/agent_b_prompt.md` | 585 | 2026-05-21 | Cache-blocked layout + infoset table |
| 8 | `pr8_prep/agent_c_prompt.md` | 481 | 2026-05-21 | PCS + benchmarks + tests |
| 8 | `pr8_prep/audit_prompt.md` | 177 | 2026-05-21 | Auditor prompt |
| 9 | `pr9_prep/pr9_spec.md` | 578 | 2026-05-21 | Spec — HUNL preflop (blueprint + refinement) |
| 9 | `pr9_prep/agent_a_prompt.md` | 595 | 2026-05-21 | Blueprint solver |
| 9 | `pr9_prep/agent_b_prompt.md` | 426 | 2026-05-21 | Subgame refinement |
| 9 | `pr9_prep/agent_c_prompt.md` | 479 | 2026-05-21 | Tests + dispatch composition |
| 9 | `pr9_prep/audit_prompt.md` | 189 | 2026-05-21 | Auditor prompt |
| 10 | `pr10_prep/pr10_spec.md` | 1227 | 2026-05-21 | Original PR 10 spec (NiceGUI; later split into 10a/10b) |
| 10a | `pr10_prep/pr10a_spec.md` | 986 | 2026-05-22 | Scaffold + mock solver |
| 10b | `pr10_prep/pr10b_spec.md` | 273 | 2026-05-22 | Mock → real-solver swap |
| 10 | `pr10_prep/agent_a_prompt.md` | 615 | 2026-05-21 | UI layout + matrix |
| 10 | `pr10_prep/agent_b_prompt.md` | 511 | 2026-05-21 | Solve / progress / EV display |
| 10 | `pr10_prep/agent_c_prompt.md` | 512 | 2026-05-21 | Tests + NiceGUI harness |
| 10 | `pr10_prep/audit_prompt.md` | 189 | 2026-05-21 | Auditor prompt |
| 10 | `pr10_prep/competitor_ui_deep_dive.md` | 863 | 2026-05-22 | Pio / GTOW / DeepSolver UX deep dive |
| 10 | `pr10_prep/ui_design_principles.md` | 421 | 2026-05-22 | Locked design intent (anti-patterns, taste) |
| 10 | `pr10_prep/ui_mockups_and_debates.md` | 611 | 2026-05-22 | ASCII mockups + alternative-layout debates |
| 11 | `pr11_prep/pr11_spec.md` | 785 | 2026-05-21 | Spec — library mode + macOS packaging |
| 11 | `pr11_prep/agent_a_prompt.md` | 479 | 2026-05-21 | Library mode (programmatic API) |
| 11 | `pr11_prep/agent_b_prompt.md` | 412 | 2026-05-21 | .dmg + signing |
| 11 | `pr11_prep/agent_c_prompt.md` | 393 | 2026-05-21 | Tests + smoke |
| 11 | `pr11_prep/audit_prompt.md` | 189 | 2026-05-21 | Auditor prompt |
| 12 | `pr12_prep/pr12_spec.md` | 960 | 2026-05-21 | Spec — 3-handed postflop (LCFR; post-v1 stretch) |
| 12 | `pr12_prep/agent_a_prompt.md` | 404 | 2026-05-21 | LCFR engine |
| 12 | `pr12_prep/agent_b_prompt.md` | 553 | 2026-05-21 | 3-player tree + dispatch |
| 12 | `pr12_prep/agent_c_prompt.md` | 552 | 2026-05-21 | Tests + 3-player diff |
| 12 | `pr12_prep/audit_prompt.md` | 201 | 2026-05-21 | Auditor prompt |

---

## 2. Coverage by PR

Status legend: spec'd / agent prompts / audit prompt / audit report / ready-to-commit summary.

| PR | Spec | Agent A/B/C | Audit prompt | Audit report | Ready-to-commit | State |
|---|---|---|---|---|---|---|
| 3 | yes (451) | n/a (different artifact: interface-concerns post-mortem) | n/a | yes (READY, 0 must-fix) | implicit (committed `16a0278`) | **shipped** to `integration` |
| 3.5 | yes (359) | n/a (single-author work) | yes | yes (NOT-READY→fixed) | yes (168) | **shipped** to `integration` (`9f91c83`) + follow-up `1cbf52a` |
| 4 | yes (460) | yes (A/B/C 457/625/288) | yes | yes (READY) | yes (175) | **shipped** to `integration` (`6565b84`) |
| 5 | yes (591) | yes (A/B/C 392/506/357) | yes | yes (1 must-fix) | yes (commit-message + checklist) | in-flight (working tree, uncommitted) |
| 6 | yes (787) | yes (A/B/C 562/617/535) | yes | (no — pre-implementation) | (no — pre-implementation) | spec'd; launch-readiness v3 verdict READY |
| 7 | yes (306) | yes (A/B/C 576/347/340) | yes | (no) | (no) | spec'd; blocked on PR 6 |
| 8 | yes (504) | yes (A/B/C 376/585/481) | yes | (no) | (no) | spec'd; blocked on PR 7 |
| 9 | yes (578) | yes (A/B/C 595/426/479) | yes | (no) | (no) | spec'd; blocked on PR 8 |
| 10a | yes (986) | yes (shared A/B/C from PR 10) | yes (shared) | (no) | (no) | spec'd; blocked on PR 9 |
| 10b | yes (273) | yes (shared) | yes (shared) | (no) | (no) | spec'd; blocked on PR 10a |
| 11 | yes (785) | yes (A/B/C 479/412/393) | yes | (no) | (no) | spec'd; blocked on PR 10b |
| 12 | yes (960) | yes (A/B/C 404/553/552) | yes | (no) | (no) | spec'd; **post-v1 stretch** |

**Notes:**
- PR 3 went through a different shape (single-author or pre-fan-out era) — no `agent_{a,b,c}_prompt.md`, just `agent_a_interface_concerns.md` documenting post-integration drift.
- PR 3.5 also single-author (no A/B/C prompts).
- PR 10 split into 10a + 10b mid-cycle. The original `pr10_spec.md` (1227 lines) still lives in-tree; the A/B/C prompts pre-date the split and apply to both halves (though 10a is the primary consumer).
- PR 6 acquired extra "launch readiness" files (v2 + v3 + MUST_PATCH_BEFORE_LAUNCH) because of a shape-drift caught between spec and PR 4's actual on-disk format.
- PR 4 also acquired two launch-readiness files (`launch_readiness_report.md` + `launch_alignment_v2.md`).

---

## 3. Orphans (docs not tied to a current PR or session need)

**None confirmed-stale.** Closest candidates:

1. `docs/session_pause_2026-05-21.md` (91 lines) — captured mid-session pause state from 2026-05-21; PR 3.5 has since committed, integration has advanced. Content is historical-only; safe to archive. **Recommendation: keep as-is** (date-stamped session log; useful for the audit trail).
2. `docs/wake_up_brief.md` (150 lines) — written for user's morning wake of 2026-05-21; references PR 3.5 as in-flight (since shipped) and `docs/pr12_prep/` as empty (since populated). Superseded by `roadmap_status_2026-05-22.md`. **Recommendation: keep for the session-audit trail; do NOT mistake it for the current roadmap snapshot.**
3. `pr_report.md` (root, 31 lines) — PR 3 era check-battery output; ruff/black failures shown are pre-cleanup. Marked stale by `wake_up_brief.md` itself. **Recommendation: regenerate or delete** (it's auto-generated by `scripts/check_pr.sh`; can be reproduced on demand).
4. `docs/pr3_prep/agent_a_interface_concerns.md` (38 lines) — drift-resolution notes; everything was reconciled at integration time. **Recommendation: keep** as a pattern reference for future fan-out PRs.

**Conclusion: no true orphans — each "near-orphan" is a date-stamped historical artifact that earns its keep as part of the audit trail.**

---

## 4. Duplicates / content that appears in 2+ docs

Spot-checked for content overlap; flagged where it crosses ~50 lines of common substance.

1. **PR roadmap state** — appears in `PLAN.md` §"Status" header, `docs/wake_up_brief.md` "Stats" / "Specs ready" table, `docs/roadmap_status_2026-05-22.md` (full status), and (partially) `docs/autonomous_decisions_2026-05-22.md`. **Severity: medium.** These docs serve different purposes (locked plan vs. wake-up vs. status snapshot vs. session decisions) but share PR status enumeration. **Refactor candidate: `roadmap_status_*.md` should be the canonical PR-state doc; `PLAN.md` and `wake_up_brief.md` should link to it rather than restate.**

2. **Spec consistency findings** — `docs/spec_consistency_review.md` (v1, 210 lines) and `docs/spec_consistency_review_v2.md` (133 lines) and `docs/cross_doc_consistency_check.md` (209 lines, 2026-05-22). All three are consistency audits over the spec set; v1 and v2 share the B1–B4/I1–I10 issue framing. **Severity: low** — v1 and v2 are intentionally sequenced (round 1 + round 2); `cross_doc_consistency_check.md` is the latest after the spec set stabilized. **Refactor candidate: consider renaming `cross_doc_consistency_check.md` → `spec_consistency_review_v3.md` for series consistency, OR explicitly archive v1/v2 once the third pass is treated as the live snapshot.**

3. **PR 5 pre-commit artifacts** — `docs/pr5_prep/commit_message_draft.md`, `docs/pr5_prep/pre_commit_checklist.md`, and `docs/pr5_prep/audit_report.md` all describe overlapping aspects of "what PR 5 ships" + "what was found in audit". **Severity: low** — each has a distinct gate role (draft message / gate checklist / fresh-eyes audit). Keep separate but cross-link.

4. **Launch readiness sequence (PR 4, PR 6)** — PR 4 has `launch_readiness_report.md` + `launch_alignment_v2.md`; PR 6 has `launch_readiness_v2.md` + `launch_readiness_v3.md` + `MUST_PATCH_BEFORE_LAUNCH.md`. Each pair documents one round of pre-launch consistency check. **Severity: none — series is intentional; each round records a specific iteration.**

5. **AGPL read-only study notes** — `docs/pr3_prep/postflop_solver_tree_notes.md` (412 lines) and `docs/pr4_prep/postflop_solver_emd_patterns.md` (611 lines) both study the same upstream repo (different subsystems: tree builder vs EMD). Distinct content; no overlap. **No refactor needed.**

---

## 5. Memory consistency

`MEMORY.md` index lists 11 entries; the memory directory contains 13 `.md` files:

```
$ ls ~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/
MEMORY.md
feedback_agent_scheduling.md             ← indexed
feedback_continuous_pruning.md           ← indexed
feedback_interaction.md                  ← indexed
feedback_min_five_agents.md              ← NOT indexed
feedback_no_extrapolate.md               ← indexed
feedback_orchestrator_only.md            ← NOT indexed
feedback_parallel_agents.md              ← indexed
feedback_plan_sync.md                    ← indexed
feedback_pr_branches.md                  ← indexed
feedback_references.md                   ← indexed
project_solver.md                        ← indexed
reference_planfile.md                    ← indexed
user_role.md                             ← indexed
```

**Gaps:**
- `feedback_min_five_agents.md` (2026-05-22, 2199 bytes) — not in `MEMORY.md` index.
- `feedback_orchestrator_only.md` (2026-05-22, 2817 bytes) — not in `MEMORY.md` index.

Both files are dated 2026-05-22 — the same day this scan runs — and represent newly-added memories. The index has not been updated to reflect them.

**Action:** add two bullets to `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md`:
- `- [Min five agents](feedback_min_five_agents.md) — ≥5 concurrent agents at all times during autonomous sessions; fan-out is the default, not the exception`
- `- [Orchestrator-only](feedback_orchestrator_only.md) — orchestrator never implements; delegates all production code to fan-out agents`

(Exact one-liner phrasing TBD — current entries follow `— rationale-summary` shape; mirror that pattern.)

---

## 6. Maintainability flags

### 6.1 Docs >500 lines (split candidates)

26 docs cross the 500-line bar. Highest-value split candidates:

| Path | Lines | Split rationale |
|---|---|---|
| `docs/pr10_prep/pr10_spec.md` | 1227 | Pre-split master spec; intentionally retained for traceability after 10a/10b split. **Keep as-is** — date-stamped historical artifact. |
| `docs/pr10_prep/pr10a_spec.md` | 986 | Active spec; the largest live PR spec. Could be split into §"Mock contract" + §"UI scaffold" + §"Tests" if a future cycle wants finer granularity. **Defer split until PR 10a implementation surfaces friction.** |
| `docs/pr12_prep/pr12_spec.md` | 960 | Post-v1 stretch spec. **Defer** — entire PR is post-v1; refactoring before need is wasted work. |
| `docs/pr10_prep/competitor_ui_deep_dive.md` | 863 | One-off research artifact; will be referenced by future PRs but not rewritten. **Keep as-is** — concise rewrites would lose source citations. |
| `docs/integration_test_scaffolds.md` | 794 | 18 cross-PR test stubs in one file. **Reasonable to split per-PR** once test files start landing (each PR removes its own stub). **Defer split — natural pruning will happen as PRs ship.** |
| `docs/pr6_prep/pr6_spec.md` | 787 | Active spec; READY-verdict locked. **Keep as-is.** |
| `docs/pr11_prep/pr11_spec.md` | 785 | Active spec; blocked on PR 10b. **Keep as-is.** |

**Heuristic:** any agent-facing spec / prompt under 1000 lines is acceptable for a one-shot agent context. The 1227-line `pr10_spec.md` is an outlier but it's the *historical* spec, not the active one; the active 10a / 10b specs are <1000 each.

### 6.2 Stale (no edit in >2 weeks of session calendar time)

**N/A.** Session is < 3 days old (2026-05-20 → 2026-05-22). Oldest doc: `docs/rust_orientation.md` (2026-05-20 19:46). No docs are stale by this metric.

### 6.3 Other flags

- **`pr_report.md` at repo root is stale** (PR 3 era, shows pre-cleanup ruff/black failures). It's auto-generated by `scripts/check_pr.sh` — either regenerate it post-PR-5 or move to `docs/` and gitignore the generated form.
- **Memory index drift** — see §5; two memory files un-indexed.
- **`docs/wake_up_brief.md` is single-day-old artifact** marketed as a current snapshot. Reader could mistake it for live state. Recommend adding a header banner: `**Superseded by:** roadmap_status_2026-05-22.md`.

---

## Verdict

**Doc tree is in good shape — minor cleanup pass recommended.**

The tree is large (98 files, 34.5K lines) but every file earns its place: the per-PR prep packs follow a clean template; cross-PR consistency reviews track resolutions; release notes + CHANGELOG are kept current; the memory index is *mostly* in sync. Nothing is rotting in plain sight.

### 3 specific cleanup actions

1. **Update `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md`** to index the two new memory files (`feedback_min_five_agents.md`, `feedback_orchestrator_only.md`). 5-minute edit; un-indexed memory is invisible to future sessions.

2. **Add a "superseded-by" banner to `docs/wake_up_brief.md`** pointing at `docs/roadmap_status_2026-05-22.md`. One-line edit; prevents the wake-up brief from being mistaken for current state during a future session resume.

3. **Either regenerate or delete `/Users/ashen/Desktop/poker_solver/pr_report.md`** at repo root. It's PR-3 era and shows pre-cleanup lint failures that no longer apply. If the file remains, downstream readers (e.g. PR review) will see misleading red flags. Regeneration is trivial via `scripts/check_pr.sh` once PR 5 commits.

Optional (lower priority): consider renaming `cross_doc_consistency_check.md` → `spec_consistency_review_v3.md` to keep the consistency-review series under one prefix.
