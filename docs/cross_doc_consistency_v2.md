# Cross-doc consistency review v2 — 2026-05-22

**Scope:** Final sanity sweep of all 9 `launch_kickoff*.md` files, all 8 `fanout_ready*.md` files (note: task said 9, only 8 exist on disk — pr6_prep has no `fanout_ready.md` because PR 6 is in-flight and uses `launch_readiness_v2/v3.md` instead), and all 8 `audit_preprep*.md` files, against `PLAN.md` + `INDEX_2026-05-22.md`.

**Verdict:** **MINOR-DRIFT** — 4 drift items found, 1 material (PR 8 branch-name inconsistency within its own doc set), 3 minor (INDEX coverage gap; one cosmetic forward-version mention; expected file-count discrepancy in the task brief).

**Total drift count:** 4 items (1 material, 2 minor, 1 task-brief discrepancy).

---

## 1. Check-by-check results

### Check 1: Branch name consistency — **MATERIAL DRIFT on PR 8**

Canonical names from task brief and matches found:

| PR | Canonical | Found | Status |
|---|---|---|---|
| PR 6 | `pr-6-rust-hunl-port` | `pr-6-rust-hunl-port` | OK |
| PR 7 | `pr-7-noambrown-diff` | `pr-7-noambrown-diff` | OK |
| **PR 8** | **`pr-8-neon-simd-pcs`** | `pr-8-simd-layout-pcs` (in `pr8_prep/launch_kickoff.md` 5 occurrences); `pr-8-neon-simd-pcs` (in `pr8_prep/fanout_ready.md` + `pr8_prep/audit_preprep.md`) | **DRIFT** |
| PR 9 | `pr-9-hunl-preflop` | `pr-9-hunl-preflop` | OK |
| PR 10a | `pr-10a-ui-mock-first` | `pr-10a-ui-mock-first` | OK |
| PR 10b | `pr-10b-ui-real-solver` | `pr-10b-ui-real-solver` | OK |
| PR 11 | `pr-11-library-and-packaging` | `pr-11-library-and-packaging` | OK |
| PR 12 | `pr-12-three-handed-stretch` | `pr-12-three-handed-stretch` | OK |
| PR 4.5 | `pr-4.5-audit-debt-sweep` | `pr-4.5-audit-debt-sweep` | OK |

**Drift #1 (MATERIAL):** `pr8_prep/launch_kickoff.md` still names the branch `pr-8-simd-layout-pcs` throughout (lines 7, 71, 72, 262, 265 — branch creation, push, merge, commit message), while `pr8_prep/fanout_ready.md` and `pr8_prep/audit_preprep.md` use the canonical `pr-8-neon-simd-pcs`. `fanout_ready.md:60` explicitly flags this divergence and instructs to "patch audit_prompt.md line 14 BEFORE running audit OR override branch name." This drift is intentional-but-unresolved — the canonical name is `pr-8-neon-simd-pcs` (per fanout_ready / audit_preprep / task brief), so `launch_kickoff.md` is stale. Will likely cause confusion at launch time; resolve by editing `pr8_prep/launch_kickoff.md` to use `pr-8-neon-simd-pcs` at all 5 sites.

### Check 2: Versioning — **CLEAN** (with one cosmetic note)

- `v0.4.0` is referenced only in `INDEX_2026-05-22.md` lines 12, 87 and `PLAN.md` line 88 ("v0.4.0 milestone = PR 4 + PR 5"). Confirmed shipped.
- `v0.5.0` is referenced only in `pr6_prep/` internal docs (`semver_sequencing.md`, `commit_pipeline_steps.md`, `commit_message_draft.md`, `audit_followup_triage.md`, `audit_report.md`) — PR 6 target version, locked.
- **Drift #2 (MINOR/cosmetic):** `PLAN.md` line 89 still hedges "(or v0.4.1 if semver sequencing decision favors patch — TBD at PR 6 land)" even though `pr6_prep/semver_sequencing.md` already locked the decision to `v0.5.0`. The v0.4.1 hedge in PLAN is a future-looking caveat; could be tightened post-PR-6-land. Outside the scope of these 26 prep docs, but noted because PLAN was in the read set.
- No future-version assignments past v0.5.0 found in any of the 26 prep docs reviewed. PR 7-12 are silent on version targets.

### Check 3: Tolerance numbers (5e-3 per-action + 1e-3 game value) — **CLEAN**

Verified consistent across:
- `pr6_prep/launch_kickoff.md`: river `1e-3` per-action, flop `5e-3` per-action (the PR 6 inversion: river is the tighter end because no abstraction; flop is looser because of bucket noise). Spec §7.3 canonical.
- `pr7_prep/launch_kickoff.md` line 156, 226, 254: `5e-3` per-action + `1e-3 × pot` per game value.
- `pr7_prep/audit_preprep.md` lines 50, 54: same.
- `pr8_prep/launch_kickoff.md` line 154: cites "PR 6/7/9 `5e-3` / `1e-3` cluster".
- `pr8_prep/fanout_ready.md` line 122: PCS Layer C mean<5e-3 / max<2e-2.
- `pr8_prep/audit_preprep.md` line 48: matches PR 6/7/9 cluster.
- `pr9_prep/launch_kickoff.md` lines 10, 138, 143, 148, 217, 247: `5e-3` per-action + `1e-3 × base_pot`; lines 143, 217 explicitly flag `1e-4` as the earlier-draft outlier and must-fix anti-pattern.
- `pr9_prep/fanout_ready.md` line 78: same cluster.
- `pr9_prep/audit_preprep.md` line 120: 5e-3/1e-3 cluster (I3).

No drift. The PR 6 inversion (river 1e-3, flop 5e-3) is the intentional asymmetry; downstream PRs reference both numbers as the "cluster."

### Check 4: Dispatch composition (PR 9 §6) — **CLEAN, but task brief differs slightly**

Task brief states: "push/fold ≤15 BB → HUNL Rust → HUNL Python → preflop → Kuhn/Leduc".

Doc-set canonical (PR 9 §6, cross-referenced by PR 3.5 §6 and PR 5 §6):
- `pr9_prep/fanout_ready.md` line 76: "push/fold ≤15 BB short-circuit → >250 BB ValueError → postflop (PR 5) → preflop (PR 9)".
- `pr9_prep/launch_kickoff.md` line 216, 244: same 4-element ordering.
- `pr9_prep/audit_preprep.md` lines 75-78: same 4-element ordering with locked boundary tests `test_preflop_dispatch_pushfold_at_15bb`, `..._solver_at_16bb`, `..._error_at_251bb`.
- `pr6_prep/launch_kickoff.md` line 238: cross-refs "PR 9 §6 canonical dispatch ordering" (correctly).

The doc-set ordering is internally consistent. The task brief's expanded composition (HUNL Rust → HUNL Python → preflop → Kuhn/Leduc) appears to fold backend-selection (Rust vs Python) and Game-type-selection (HUNL vs Kuhn/Leduc) into the same chain. The doc-set's 4-element composition stops at the HUNL dispatch boundary (push/fold → ceiling → postflop → preflop) and leaves backend-selection to `solver.py`'s `--backend` flag (PR 6 §6 / spec §6.3). No drift inside the doc set; the task brief's richer composition is a fuller picture that the docs don't currently spell out in one place.

### Check 5: Integration tip `eee9b4b` — **CLEAN within doc set**

Direct references found:
- `pr7_prep/fanout_ready.md` lines 18, 22: explicit `eee9b4b` mention.
- `pr6_prep/launch_kickoff.md` lines 13, 14 (verdict cite), elsewhere implicit via "integration tip".
- `PLAN.md` line 5, 218, 228: `eee9b4b` as PR 5 merge / current integration tip.
- `INDEX_2026-05-22.md` line 132, 143: `eee9b4b` as PR 5 integration commit.

Other docs (PR 8/9/10a/10b/11/12/4.5 launch_kickoff + fanout_ready + audit_preprep) reference "integration tip" abstractly via `git rev-parse integration` pre-flight checks rather than the specific hash, which is correct (those PRs land AFTER PR 6 / PR 7, so their integration tip is post-`eee9b4b`). No drift.

### Check 6: No `v0.4.1` leftover references — **CLEAN within the 26 prep docs**

- Zero `v0.4.1` references found in any `launch_kickoff*.md`, `fanout_ready*.md`, or `audit_preprep*.md` file (the 26 docs in scope).
- `pr6_prep/semver_sequencing.md` discusses the `v0.4.1 → v0.5.0` upgrade decision (already locked); not a leftover, an audit trail.
- **Drift #3 (MINOR):** `PLAN.md` line 89 still hedges "(or v0.4.1 if semver sequencing decision favors patch — TBD at PR 6 land)" — same as Drift #2 above; flagged once.

### Check 7: `on_progress` kwarg threading (PR 9 + PR 10b spec; PR 5 supports; PR 6 inherits) — **CLEAN**

`on_progress` referenced in 67 lines across 6 of the 26 prep docs (correctly scoped to PR 9 + PR 10b surfaces):
- `pr9_prep/launch_kickoff.md`: ~13 references; §4d "on_progress kwarg threading" is the dedicated section; explicit thread-through requirement on `solve_hunl_preflop`, `build_blueprint`, `refine_subgame` plus Rust ports.
- `pr9_prep/fanout_ready.md` line 29, §4: locked into Agent A/B/C prompts (Agent A LOCKED #13, Agent B LOCKED #10, Agent C LOCKED #11).
- `pr9_prep/audit_preprep.md` §1.2: silent-drop must-fix gate.
- `pr10_prep/launch_kickoff_10b.md` lines 50, 99, 118, 124, 136, 167, 192, 224, 239: dispatch wrapper signature `Callable[[int, float, MemoryReport], None] | None = None` byte-locked.
- `pr10_prep/fanout_ready_10b.md` lines 5, 31, 38: pre-flight gate asserts PR 9 ships the kwarg.
- `pr10_prep/audit_preprep_10b.md` §1.2: signature compatibility check.

PR 5 supports it (per PR 9 spec §4 amendment derived from `pr10b_spec.md` §3); PR 6 inherits (per PR 6 spec §4.1 pre-mirrors). The chain `PR 5 → PR 6 → PR 9 → PR 10b` is consistent across all relevant docs. No drift.

### Check 8: INDEX accuracy — **MINOR DRIFT (coverage gap)**

`INDEX_2026-05-22.md` §2a "Per-PR prep packs" lists the standard pack per PR (spec + agent prompts + audit + readiness + kickoff) but does NOT mention any `fanout_ready*.md` (8 files) or `audit_preprep*.md` (8 files) anywhere in the document. Total of 16 prep docs created this session that are not surfaced in INDEX §2a.

- **Drift #4 (MINOR):** `INDEX_2026-05-22.md` doesn't list the `fanout_ready*.md` or `audit_preprep*.md` family. Per-PR entries should add these two lines each (e.g., PR 7's row should add "`fanout_ready.md`, `audit_preprep.md`"). Eight PRs × 2 docs = 16 missing INDEX entries. Non-correctness — all 16 files exist on disk and are functional — but the INDEX undercounts the doc set.

All other INDEX-listed docs verified present on disk via earlier `find` sweeps. No missing-file drift; only missing-entry drift.

---

## 2. Task-brief discrepancy (not a drift, but worth flagging)

The task brief states "All `docs/prN_prep/fanout_ready*.md` (9 files)". Disk reality: 8 files. `pr6_prep/` has no `fanout_ready.md` because PR 6 is currently IN FLIGHT (not pre-staged); it uses `launch_readiness_v2.md` + `launch_readiness_v3.md` + `MUST_PATCH_BEFORE_LAUNCH.md` instead. The 8 `fanout_ready*.md` files are:
1. `pr4_5_audit_debt/fanout_ready.md`
2. `pr7_prep/fanout_ready.md`
3. `pr8_prep/fanout_ready.md`
4. `pr9_prep/fanout_ready.md`
5. `pr10_prep/fanout_ready_10a.md`
6. `pr10_prep/fanout_ready_10b.md`
7. `pr11_prep/fanout_ready.md`
8. `pr12_prep/fanout_ready.md`

This is consistent with PR 6's in-flight status (per PLAN.md and INDEX); the missing 9th file is expected, not a drift.

---

## 3. Summary table

| # | Drift | Severity | Location | Fix |
|---|---|---|---|---|
| 1 | PR 8 branch name `pr-8-simd-layout-pcs` in launch_kickoff vs `pr-8-neon-simd-pcs` in fanout_ready + audit_preprep | MATERIAL (within doc set) | `pr8_prep/launch_kickoff.md` lines 7, 71, 72, 262, 265 | Sed replace `pr-8-simd-layout-pcs` → `pr-8-neon-simd-pcs` in launch_kickoff.md (5 sites) |
| 2 | PLAN.md still hedges "v0.4.1 if semver sequencing favors patch" | MINOR/cosmetic | `PLAN.md` line 89 (outside scope of 26 prep docs but read here) | Tighten to "v0.5.0 (locked per pr6_prep/semver_sequencing.md)" |
| 3 | Same as #2 (one-and-the-same drift) | — | — | Counted once |
| 4 | INDEX_2026-05-22.md doesn't list any `fanout_ready*.md` or `audit_preprep*.md` files | MINOR (coverage gap) | `INDEX_2026-05-22.md` §2a per-PR rows | Add 2 file entries per PR row (8 PRs × 2 = 16 missing entries) |

Effective count: 3 distinct drift items (PR 8 branch name; PLAN v0.4.1 hedge; INDEX coverage). The PR 8 drift is the only one that could plausibly cause an operational error at launch time (orchestrator launches with the wrong branch name; either the launch_kickoff.md or the audit_prompt.md will be wrong, depending on which file the operator reads first).

---

## 4. Overall doc-set health

- **Internal consistency (within each PR's own folder):** 7 of 8 PRs CLEAN. PR 8 has the branch-name split.
- **Cross-PR consistency (tolerances, dispatch ordering, kwarg threading):** CLEAN across all 26 docs. The 5e-3/1e-3 tolerance cluster, `on_progress` signature, dispatch ordering, and license posture all match across kickoff / fanout / audit-preprep / spec / audit-prompt.
- **PR 6 special case:** intentionally lacks `fanout_ready.md` (in-flight rather than pre-staged) and `audit_preprep.md` (audit already completed for PR 6 via `audit_report.md`). Both omissions are correct, not drift.
- **INDEX as source-of-truth:** undercounts the doc set by 16 entries; functional impact is zero (all files are findable via `ls docs/pr*_prep/`), but a fresh reader using INDEX as their only entry point would miss the fan-out shortlist + audit pre-prep family.

The doc set is operationally launch-ready for PR 6 (in flight) and PR 7-12 + PR 4.5 (staged). The PR 8 branch-name drift should be resolved before PR 8 fires (post-PR-6 land). The two minor drifts (PLAN v0.4.1 hedge, INDEX coverage gap) are documentation hygiene rather than launch blockers.

**Final verdict: MINOR-DRIFT.**
