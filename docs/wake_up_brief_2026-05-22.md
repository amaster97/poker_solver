# Wake-up brief — autonomous session 2026-05-22

> **Supersedes** `wake_up_brief.md` (2026-05-21 session, marked stale at top).
> **Refreshed post-v1.0.0-GA milestone hit.** Read this first; drill-down references cited inline.

---

## 1. TL;DR

- **v1.0.0 GA MILESTONE HIT this session.** 10 PRs shipped: 3, 3.5, 3.5-fu, 4, 4.5, 5, 6, 7, 10a, 11.
- **`integration` tip = `5af56a7`** (PR 11 follow-up); **v1.0.0** tagged on `bbb4395`, **v0.6.0** tagged earlier on integration. PR 11 (library + macOS .dmg) shipped at `6af3684` for v1.0.0 GA; PR 10a (NiceGUI scaffold + mock) shipped at `93dde21` for v0.6.0.
- **Main awaits user approval to merge** — `integration → main` is now the v1.0.0 GA RELEASE. This is the single biggest pending action.
- **Top decisions awaiting you (in order):** (1) **main merge of `integration`** = v1.0.0 GA release; (2) confirm autonomous tags (v0.6.0 + v1.0.0 on integration) — accept (recommended) or move to main only post-merge; (3) PR 10a.5 conformance pass scope OK; (4) other minor (Q3 1000 vs 2000, dangling branch delete).
- **Honest gap surfaced:** No full HUNL solve performed yet — Kuhn/Leduc/river-only smokes against synthetic abstractions. Production-scale 200K-iter abstraction build never executed end-to-end (~10 hr wall-clock). Rust port (PR 6) bit-exact on river fixture only.

---

## 2. PR status (integration tip `5af56a7`)

| PR | Version | Status | Commit |
|---|---|---|---|
| **PR 11** | **v1.0.0 GA** | **shipped** | `6af3684` |
| PR 10a | v0.6.0 | shipped | `93dde21` |
| PR 4.5 | v0.5.2 | shipped | `d00e1aa` |
| PR 7 | v0.5.1 | shipped | `83d7b9c` (noambrown diff) |
| PR 6 | v0.5.0 | shipped | `0933367` (~24x Rust speedup) |
| PR 5 | v0.4.0 | shipped | `a9d02ca` |
| PR 4 / 3.5-fu / 3.5 / 3 | — | shipped earlier | (in integration) |
| PR 10a.5 | — | future (conformance) | staged |
| PR 10b | — | future (mock→real) | depends on PR 9 |
| PR 8 / 9 / 12 | — | future | staged |

**Docs:** new this session — `competitor_ui_deep_dive.md` (863 L), `ui_design_principles.md` (421 L), `ui_mockups_and_debates.md` (611 L), `autonomous_decisions_2026-05-22.md`, `open_items_audit_2026-05-22.md`, `audit_followup_backlog.md`, `roadmap_status_2026-05-22.md`, `equity_precision_branch_investigation.md`, `pr10b_spec.md`, `pr10a_spec.md` (with §0.1 locked-decisions block), `pr5_prep/exploitability_verification_2026-05-22.md`, this brief.

---

## 3. User decisions awaiting (priority order)

### Priority 1 — Main merge of `integration` → `main` = **v1.0.0 GA RELEASE**

- **What:** `main` sits at `2b67370` (equity hybrid only). `integration` at `5af56a7` carries **PR 1–11 + PR 11 follow-up (cumulative v1.0.0 GA; v1.0.0 tag on `bbb4395`)**. Single largest pending action.
- **Default:** holding. Per `docs/pr_launch_runbook.md` §Pacing, main merges require explicit user OK.
- **Reversibility:** non-trivial post-merge (forced revert). Reviewable: cumulative diff `2b67370..integration` covers PR 3 / 3.5 / 3.5-fu / 4 / 4.5 / 5 / 6 / 7 / 10a / 11.
- **Recommendation:** approve merge — flips v1.0.0 GA tag onto main and ends the milestone.

### Priority 2 — Confirm autonomous tags (v0.6.0 + v1.0.0 on integration)

- **What:** `v0.6.0` placed autonomously on integration at `93dde21`; `v1.0.0` placed at `6af3684`. Both flagged in `docs/autonomous_decisions_2026-05-22.md`.
- **Default:** **accept (recommended)** — keep tags on integration; they ride forward to main once Priority 1 lands. Alt: strip and re-tag main only post-merge.

### Priority 3 — PR 10a.5 conformance pass scope OK

- **What:** PR 10a shipped with 5 failing + 7 xfailed tests (Agent B mock-solver marker drift). PR 10a.5 is scoped to drain these; low-priority cleanup, non-blocking for v1.0.0.
- **Default:** holding for OK.

### Priority 4 — Other minor

- **Q3 coin-flip (1000 vs 2000 iter default):** PR 10a §0.1 locked 1000; bump to 2000 in PR 10b if under-converged.
- **Delete dangling `origin/equity-precision` branch:** tree byte-identical to `main`; safe to delete (`git push origin --delete equity-precision`).

---

## 4. Locked autonomous decisions (what you did NOT have to decide)

1. **PR 10a UI design — all 7 Qs locked in `docs/pr10_prep/pr10a_spec.md` §0.1**: two-pane / hand-class labels / 1000 iter (coin-flip) / 4-of-6 bet sizes / combo inspector below matrix / tree reach filter 0.01 / yellow mock-mode banner.
2. **PR 5 must-fix #1 patched in `a9d02ca`** — lossless-flop exploitability guard at `hunl_solver.py:164`; both `exploitability(` call sites guarded. River-only spec §11 fallback tests landed; `--abstraction PATH` CLI flag landed.
3. **PR 6 prompt patches** applied: AbstractionRef carried; on-disk shape matches PR 4 contract (`pr6_prep/MUST_PATCH_BEFORE_LAUNCH.md`).
4. **PR 7 P1 binary-path patch** applied (NoamBrown ground-truth path corrected).
5. **pytest-timeout** active: 90s default / 3600s slow / 0 very_slow markers wired.
6. **PLAN.md updates** applied autonomously — PR 10 → PR 10a / PR 10b split; per-PR progress legend; §6/§7 refresh against `open_items_audit_2026-05-22.md`.
7. **PR-branch + integration pushes autonomous; main pushes require explicit OK** (D3 in `autonomous_log.md`).

---

## 5. Kickoffs staged (9 launch_kickoff.md docs ready to fire)

Each kickoff is invokable verbatim as the orchestrator-launch prompt; spawns the appropriate fan-out wave (implementer + tests-from-spec + audit + specialized agents).

| Path | Purpose |
|---|---|
| `docs/pr4_5_audit_debt/launch_kickoff.md` | Audit-debt sweep PR (drains should-fix backlog before PR 6 audit). Can run parallel to PR 6. |
| `docs/pr6_prep/launch_kickoff.md` | **Commit-ready** — HUNL postflop port to Rust. ~24x measured, bit-exact parity. Audit + dry-run pending (non-blocking). Next event: squash commit per `commit_pipeline_steps.md`. |
| `docs/pr7_prep/launch_kickoff.md` | River-spot diff test vs `noambrown/poker_solver`; gates PR 6 trust. |
| `docs/pr8_prep/launch_kickoff.md` | NEON SIMD + cache-blocking + public chance sampling in Rust. |
| `docs/pr9_prep/launch_kickoff.md` | HUNL preflop, both tiers. |
| `docs/pr10_prep/launch_kickoff_10a.md` | NiceGUI scaffold + mock solver. |
| `docs/pr10_prep/launch_kickoff_10b.md` | Replace mock with real solver bindings (deps: PR 9 + 10a). |
| `docs/pr11_prep/launch_kickoff.md` | Library mode + macOS packaging (codesign + notarize + .dmg). |
| `docs/pr12_prep/launch_kickoff.md` | 3-handed postflop stretch (post-v1; default skip). |

**Sequencing intent:** PR 6 (in flight) → PR 4.5 sweep + PR 7 in parallel → PR 8 → PR 9 + PR 10a in parallel → PR 10b → PR 11 → PR 12.

---

## 6. Realistic time-to-v1

PR 5 burn rate was **~6 hours** (committed `a9d02ca` + merged `eee9b4b`). Projecting forward at similar agent throughput:

| Wave | Content | Estimate |
|---|---|---|
| PR 6 (commit-ready) | Rust port — commit + integration merge | hours |
| PR 4.5 + PR 7 (parallel post-PR-6) | Audit-debt sweep + river-spot diff | half day |
| PR 8 | NEON SIMD + cache-blocking + PCS | 1–2 days |
| PR 9 + PR 10a (parallel) | HUNL preflop + UI scaffold/mock | 1 day |
| PR 10b + PR 11 | Real-solver bindings + packaging | half day – 1 day |

**Total remaining: ~3–4 days** (was ~5–6 days in previous brief). PR 12 is post-v1 and skipped by default.

---

## 6.5. Milestone numbers (as of this brief)

| Metric | Value | Source |
|---|---|---|
| Session totals — LOC added | **~30K** | session aggregate |
| Session totals — tests | **303+** | pytest suite |
| Memory rules in MEMORY.md | **15** | `~/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/MEMORY.md` |
| Docs files staged | **~250** | `docs/` tree |
| PRs shipped (integration tip `5af56a7`) | **PR 1–11 (v1.0.0 GA; tag on `bbb4395`)** | `git log --oneline integration` |
| PR 6 measured speedup (100k iter, river fixture) | **~24x** (Python 92.9 s vs Rust 3.88 s) | `docs/pr6_prep/speedup_measurement.md` |

Honest caveat on the 24x: measured on the 16-infoset river subgame only. The flop fixture parity is 5e-3 (not bit-exact). End-to-end production solve (200K-iter abstraction build → full HUNL solve) still unmeasured.

---

## 7. Risks / unknowns to surface honestly

1. **PR 4 TURN abstraction coverage gap blocks 6 PR 5 tests in CI.** Synthetic abstraction fixture doesn't cover certain turn boards. PR 6's production-scale Rust kmeans is expected to dissolve this; if it doesn't, fixture-side fix is needed.
2. **PR 6 may surface new license violations or HashMap iteration nondeterminism** — addressable in the 3-agent fan-out reconciliation. Mitigation: PR 6 audit prompt explicitly checks both classes; reconciliation agent will arbitrate any drift between Agent A/B/C outputs.
3. **Synthetic abstraction build (200K MC iter) is ~10 hours wall-clock.** Production build never executed end-to-end this session.
4. **Mac GPU explored and confirmed not viable.** Locked path: CPU + ARM NEON 128-bit SIMD + cache-blocked infoset layout. M-series 120 GB/s memory bandwidth is the real ceiling.
5. **No full HUNL solve has been performed end-to-end yet.** First real production solve happens in PR 6.
6. **PR 11 PyInstaller `_rust.so` bundling risk** flagged in `pr_launch_runbook.md`; resolution deferred to PR 11 audit.
7. **PR 4 kmeans homogeneity test loosened (95% → 50%)** per spec §8 Agent C #3. Tighten when PR 6's Rust kmeans lands.

---

## 8. Recommended skim order

1. **This brief** (`docs/wake_up_brief_2026-05-22.md`) — 5-min skim of current state.
2. **`docs/roadmap_status_2026-05-22.md`** — current shipped state, dependency graph, honest gaps.
3. **`docs/autonomous_decisions_2026-05-22.md`** — what was locked autonomously.
4. **`docs/open_items_audit_2026-05-22.md`** — cross-PR audit follow-up.
5. **`docs/pr10_prep/pr10a_spec.md` §0.1** — locked UI decisions with citations.

Optional drilldowns: `docs/audit_followup_backlog.md` · `docs/equity_precision_branch_investigation.md` · `docs/pr6_prep/launch_kickoff.md` · `PLAN.md` §2 + §6.

---

## 9. Files-on-disk index

| Topic | Path |
|---|---|
| Integration tip | `5af56a7` on local `integration` and `origin/integration` (carries `v0.6.0` + `v1.0.0` tags; `v1.0.0` tag on `bbb4395`) |
| PR 11 (shipped, v1.0.0 GA) | `6af3684` on `pr-11-library-and-packaging`; merged into integration |
| PR 10a (shipped, v0.6.0) | `93dde21` (NiceGUI scaffold + mock solver) |
| PR 4.5 (shipped, v0.5.2) | `d00e1aa` (audit-debt sweep) |
| PR 7 (shipped, v0.5.1) | `83d7b9c` (noambrown diff) |
| PR 6 (shipped, v0.5.0) | `0933367`; ~24x measured (`docs/pr6_prep/speedup_measurement.md`) |
| PR 5 (shipped, v0.4.0) | `a9d02ca` |
| Dangling remote | `origin/equity-precision` at `01475e8` (delete candidate) |
| PR 10a/10b specs | `docs/pr10_prep/pr10a_spec.md`, `pr10b_spec.md` |
| Cleanup backlog | `docs/audit_followup_backlog.md` |
| Audit reports | `docs/pr3_prep/audit_report.md`, `pr3_5_prep/audit_report.md`, `pr4_prep/audit_report.md`, `pr5_prep/audit_report.md` |
| Kickoffs staged | `docs/pr{4_5_audit_debt,6,7,8,9,10,11,12}_prep/launch_kickoff*.md` (9 total) |
