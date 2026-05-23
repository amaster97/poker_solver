# Snapshot — in-flight & pending (2026-05-22)

## 1. Branch status

| Branch | Tip | State |
|---|---|---|
| `main` | `2b67370` | unchanged; awaiting merge OK |
| `integration` | `d135add` | PR 7 merge landed (post-handoff write); v0.5.1 |
| `pr-4.5-audit-debt-sweep` | current checkout | dirty tree: 8 modified files staged for sweep |
| `pr-7-noambrown-diff` | `83d7b9c` | squashed + merged to integration |
| `pr-3.5-pushfold` | local-only | shipped; safe to prune |
| Other staged PR branches | created | `pr-6`, `pr-5`, `pr-4`, `pr-10a` exist locally + remote |
| `origin/equity-precision` | `01475e8` | byte-identical to main; **deletion-pending user OK** |

Working-tree dirty (current checkout `pr-4.5-audit-debt-sweep`): `CHANGELOG.md`, `emd_clustering.py`, `equity_features.py`, `precompute.py`, `action_abstraction.py`, `hunl.py`, `profiler/memory.py`, `pushfold.py`.

## 2. PRs shipped this session (7)

| # | PR | SHA → merge | Version |
|---|---|---|---|
| 1 | PR 3 (HUNL tree) | `a96675c` | pre-v0.4 |
| 2 | PR 3.5 (pushfold) | `9f91c83` | pre-v0.4 |
| 3 | PR 3.5 audit follow-up | `1cbf52a` → `f67bfa3` | pre-v0.4 |
| 4 | PR 4 (card abstraction) | `6565b84` → `5832b2f` | v0.4.0 |
| 5 | PR 5 (HUNL postflop + profiler) | `a9d02ca` → `eee9b4b` | v0.4.0 |
| 6 | PR 6 (Rust port) | `0933367` → `6c438b8` | v0.5.0 (~24x speedup, bit-exact) |
| 7 | PR 7 (Brown diff) | `83d7b9c` → `d135add` | v0.5.1 (landed post-handoff-write) |

Cumulative integration diff `2b67370..d135add` = PR 3 + 3.5 + followup + 4 + 5 + 6 + 7. STATUS.md / SESSION_HANDOFF.md both wrote before the PR 7 merge committed — actual integration tip is `d135add`, not `6c438b8` as those docs report.

## 3. PR 4.5 (audit-debt sweep) — mid-audit

- Branch checked out, **8 files modified** (uncommitted).
- Drains the 77-item audit follow-up backlog (PR 3 / 3.5 / 4 / 5).
- Full pipeline pre-staged: `launch_kickoff.md`, `fanout_ready.md`, `audit_preprep.md`, `audit_prompt_final.md`, `audit_report.md`, `commit_pipeline.md`, `commit_message_draft.md`, `pre_commit_checklist.md`, `incidental_edits_review.md`, `launch_decision.md`, `launch_invocations.md`.
- Audit phase appears live (report file present). No commits on the branch yet.
- **Next action:** finalize commit pipeline → squash → merge to integration.

## 4. PR 10a ready to fire (post-PR-4.5)

- Spec at `docs/pr10_prep/launch_kickoff_10a.md`.
- All artifacts staged: agents A / B / C prompts, audit preprep+final, commit draft, fanout, launch invocations, competitor UI deep-dive, implementation challenges, orchestrator-ready-to-fire.
- 7 UI questions locked (Q3 iter-count = 1000, coin-flip flag — revisit in 10b).
- Branch `pr-10a-ui-mock-first` already created.
- Independent of PR 9; only depends on PR 3 + PR 5 data types.

## 5. PR 7 must-fix patches landed (formal completion pending)

- Patches M1 + M2 + M3 verified per `docs/pr7_prep/patch_verification.md`.
- Squash `83d7b9c` + merge `d135add` to integration are landed.
- `agent_a_completion.md` filed; orchestrator commit recipe + commit_pipeline_v2 still flagged as the "official" closure docs.
- v0.5.1 PATCH bump bundle landed. Brown binary cross-solver gate remains empirically untested (4 `test_brown_binary_*` tests SKIP cleanly when binary absent — first true gate requires building Brown's MIT solver locally).

## 6. Doc retention recommendations

**Keep (active):**
- `docs/SESSION_HANDOFF.md`, `STATUS.md`, `PLAN.md`, `audit_followup_backlog.md`, `autonomous_log.md`.
- `docs/pr4_5_audit_debt/*` — pipeline in flight.
- `docs/pr10_prep/*`, `pr8_prep/*`, `pr9_prep/*` — next launches.
- `docs/INDEX_2026-05-22.md`, `ONE_PAGE_SUMMARY.md`, `session_retrospective_2026-05-22.md`.

**Archive (shipped PRs):**
- `docs/pr3_prep/`, `pr3.5_prep/`, `pr4_prep/`, `pr5_prep/`, `pr6_prep/` (move to `docs/archive/`).
- `docs/pr7_prep/` after formal PR 7 closure doc is filed.
- `wake_up_brief_2026-05-22.md` superseded by SESSION_HANDOFF — archive.

**Update before next session:**
- `STATUS.md` §1 + §2: integration tip is `d135add` (not `6c438b8`); PR 7 status = shipped (not in flight).
- `SESSION_HANDOFF.md` §2 table: same correction.
- Trigger continuous-pruning agent per memory rule.

## 7. Decisions still blocking (3, unchanged)

1. Main merge approval (integration → main).
2. Q3 UI iter count default 1000 vs 2000 (PR 10a → revisit in 10b).
3. `origin/equity-precision` deletion OK.
