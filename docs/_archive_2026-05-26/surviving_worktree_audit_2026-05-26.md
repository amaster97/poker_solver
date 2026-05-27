# Surviving Worktree Audit — 2026-05-26

**Author:** orchestrator agent (Stage-3 autonomous)
**Working dir:** `/Users/ashen/Desktop/poker_solver`
**Brief:** `docs/worktree_housekeeping_2026-05-26.md` — 5 user-gated kill candidates
**Outcome:** **5 of 5 worktrees removed + 5 branches deleted; load-bearing untracked content salvaged to `docs/_archive_2026-05-26/`.**

---

## Action Summary

| # | Worktree | Branch | Decision | Action taken |
|---|---|---|---|---|
| 1 | `cli-ergonomics` | `pr-39-cli-ergonomics` | **ABSORBED — REMOVE** | `worktree remove --force` + `branch -D` |
| 2 | `persona-corrections` | `pr-38-persona-corrections` | **SUPERSEDED — SALVAGE + REMOVE** | Salvage 2 untracked docs (1008 lines) + commit patches → `docs/_archive_2026-05-26/persona_corrections_pr38/`; `worktree remove --force` + `branch -D` |
| 3 | `phase2b-audit-revision` | `pr-41-phase2b-audit-revision` | **SUPERSEDED — SALVAGE + REMOVE** | Salvage PR 41 commit as patch (depends on PR 38) → same archive dir; `worktree remove --force` + `branch -D` |
| 4 | `pr-17-plan-c` | `pr-17-plan-c-dense-slabs` | **AUTHOR-PARKED — SALVAGE + REMOVE** | Salvage `bench_3way.py` + PR 17 WIP patch → `docs/_archive_2026-05-26/pr17_plan_c_parked/`; `worktree remove --force` + `branch -D` |
| 5 | `pr-23-p0-off-by-one` | `pr-34-p0-off-by-one` | **ABSORBED — REMOVE** | `worktree remove --force` + `branch -D` (no salvage needed; `references/` is gitignored local-only) |

No new PRs created. No origin-branch deletes. No force-pushes.

---

## Per-Worktree Findings

### 1. `cli-ergonomics` (pr-39-cli-ergonomics) — ABSORBED

**Unique commits:** `7584e06 PR 39: CLI ergonomics subcommands (pushfold, river, parity)`

**Verdict:** The identical patch is on `origin/main` as commit `25972d7` (same author, same date, same subject, same body, same diff). Author timestamps match exactly. This is the same PR landed via a different rebase path.

**Action:** Removed worktree + deleted branch. No salvage needed (PR shipped).

---

### 2. `persona-corrections` (pr-38-persona-corrections) — SUPERSEDED

**Unique commits:**
- `71d161d PR 38: spec + audit framing + retest prompts + revision history` (1143 insertions across 6 docs in `docs/pr13_prep/` + `docs/pr_proposals/`)
- `149ca11 PR 38: propagate persona verdict downgrades (W3.5, W1.2)`

**Untracked content (2 docs, 1008 lines, load-bearing):**
- `docs/poker_spots_audit_CORRECTED_2026-05-23.md` (554 lines)
- `docs/poker_spots_reverification_2026-05-23.md` (454 lines)

**Verdict:** Work is partially superseded:
- W3.5 downgrade in PR 38 was REVERSED by later `794df95 PR 42: REVERSE W3.5 downgrade per vector-form TRUE Nash validation` and re-reversed in `d29af7d docs: 5th reversal in W3.5 thread`. Final state in main's `docs/persona_test_status_2026-05-25.md` is W3.5 = "FAIL → Type B (wrapper bug)".
- W1.2 downgrade in PR 38 was contradicted by `54dd0d3 docs: v1.7.0 shipped + persona retest results (W3.5 PARTIAL / W1.2 PASS / W2.1 timeout)`. Final state: W1.2 = "PASS via Nash path" (PR 43).
- The `docs/pr13_prep/` and `docs/persona_test_results/` directories that PR 38 modifies are NOT tracked on `origin/main` at all — those dirs exist only on disk locally and on feature branches. The PR #40 persona snapshot on main *references* them as sources, but doesn't itself ship them. (This is a separate doc-drift issue beyond this audit's scope.)

**Why not a fresh PR:** The verdict downgrades in `149ca11` have been re-evaluated multiple times since. Landing them now would re-introduce stale (contested) classifications. The framing-correction docs in `71d161d` describe methodology lessons that may still be useful but are out of sync with the current persona status snapshot.

**Action:**
- Salvaged 2 untracked docs to `docs/_archive_2026-05-26/persona_corrections_pr38/`
- Saved both commits as `pr_38_commits.patch` (1814 lines) in same dir
- Removed worktree + deleted branch

---

### 3. `phase2b-audit-revision` (pr-41-phase2b-audit-revision) — SUPERSEDED

**Unique commits (relative to origin/main):**
- `dcc9d83 PR 41: Phase 2b audit AK revision + per-hand breakdown cross-reference` (modifies `docs/pr13_prep/v1_3_2_phase2b_audit.md`, +33/-1)
- `71d161d`, `149ca11` (inherited from PR 38, see above)

**Verdict:** PR 41 is a follow-up doc revision to PR 38 cross-referencing a per-hand breakdown report (`docs/persona_test_results/W2b_1_per_hand_breakdown.md`) that itself does not exist on `origin/main`. The revision rewrites the audit's "AK pure-fold" claim with a 500-iter measurement showing `AK defend=0.227`.

The patch target file `docs/pr13_prep/v1_3_2_phase2b_audit.md` is not tracked on `origin/main`. Even if landed, the patch dangling-references a doc that also isn't on main. Stale.

**Action:**
- Saved PR 41 patch as `pr_41_phase2b_audit.patch` (72 lines) → `docs/_archive_2026-05-26/persona_corrections_pr38/`
- Removed worktree + deleted branch

---

### 4. `pr-17-plan-c` (pr-17-plan-c-dense-slabs) — AUTHOR-PARKED

**Unique commit:**
- `ea2511c WIP: Plan C dense slabs + vectorized showdown (parked; superseded by Option A v1.3.2)` (988 insertions: `exploit_vec.rs` + tests + Python glue)

The commit message itself says: *"Killed prematurely 2026-05-23. Work was in progress: exploit_vec.rs + diff test. Option A (PR 15) shipped first with 26s perf gate cleared; Plan C is now potential v2.0 enhancement only."*

**Untracked content:**
- `docs/pr17_prep/bench_3way.py` (147 lines) — perf-bench script comparing 3 exploitability paths. References Rust symbols (`exploitability_hunl_postflop_vec`) that only exist on this branch. Usable as a v2.0 baseline test if Plan C is ever revived.

**Verdict:** Author's own commit message explicitly parks this as a v2.0 enhancement candidate. Not landable now.

**Action:**
- Salvaged `bench_3way.py` + full `pr17_plan_c_wip.patch` (45,268 bytes) → `docs/_archive_2026-05-26/pr17_plan_c_parked/`
- Removed worktree + deleted branch

---

### 5. `pr-23-p0-off-by-one` (pr-34-p0-off-by-one) — ABSORBED (different SHA, same fix)

**Unique commit:**
- `0bafcfa PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)` (28 lines in `crates/cfr_core/src/dcfr_vector.rs`)

**Verdict:** Functionally absorbed via commit `2d7ea58 fix(dcfr_vector): size next_reach by player_hands not opp_hands (#16)` on `origin/main`. Both commits change the same lines from `opp_hands` → `player_hands`:

```
-                    let mut next_reach = vec![0.0_f64; opp_hands];
+                    let mut next_reach = vec![0.0_f64; player_hands];
-                        for h in 0..opp_hands {
+                        for h in 0..player_hands {
```

Main's version of the fix adds an additional regression test (`vector_solver_handles_asymmetric_combo_counts`) that PR 34's worktree did not include — main's version is strictly broader. The PR 34 worktree commit is therefore strictly redundant.

**Untracked content:** `references/` — 192 MB of papers/blogs/code. Gitignored at repo root (`.gitignore: references/`). Local-only, not load-bearing for the worktree.

**Action:** Removed worktree + deleted branch. No salvage (`references/` is gitignored local data; the orchestrator-root `/Users/ashen/Desktop/poker_solver/references/` is the canonical local copy).

---

## Salvaged Content (Archive Inventory)

```
docs/_archive_2026-05-26/
  persona_corrections_pr38/
    poker_spots_audit_CORRECTED_2026-05-23.md       (35,257 bytes — referenced by PR 38 commits)
    poker_spots_reverification_2026-05-23.md        (20,871 bytes — referenced by PR 38 commits)
    pr_38_commits.patch                              (1814 lines — both PR 38 commits)
    pr_41_phase2b_audit.patch                        (72 lines — PR 41 doc revision)
  pr17_plan_c_parked/
    bench_3way.py                                    (5,562 bytes — 3-way perf bench, v2.0 baseline)
    pr17_plan_c_wip.patch                            (45,268 bytes — full WIP commit)
```

These archives are not added to git in this audit. Recommend tracking under a single follow-up commit later.

---

## Final State

- Worktrees at `/Users/ashen/Desktop/poker_solver_worktrees/`: **21** (down from 26)
- Branches deleted (5): `pr-39-cli-ergonomics`, `pr-38-persona-corrections`, `pr-41-phase2b-audit-revision`, `pr-17-plan-c-dense-slabs`, `pr-34-p0-off-by-one`
- Origin branches touched: **none** (no force-push / no origin delete — per brief)
- New PRs created: **none** (all 5 candidates were absorbed or stale)

## Followups for User Review

1. The `docs/pr13_prep/` and `docs/persona_test_results/` directories are referenced by `docs/persona_test_status_2026-05-25.md` (shipped via PR #40) but are NOT tracked on `origin/main`. This is a broader doc-drift issue worth a dedicated cleanup PR (out of scope for this audit).
2. Recommend committing `docs/_archive_2026-05-26/` to main in a follow-up so the salvaged content is durable.
