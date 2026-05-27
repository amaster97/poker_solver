# LEG 15 — v1.5.0 Ship Report

**Date:** 2026-05-23
**Ship plan:** `docs/leg13_v1_5_0_ship_plan.md`
**PR 23 audit:** `docs/v1_5_0_pr_23_audit.md` (APPROVED verdict)

## Outcome

**SHIPPED.** v1.5.0 live on origin/main + GitHub release.

| Field | Value |
|---|---|
| v1.5.0 tag SHA | `544bd0ed3d84405234777b4551b8ce82f488f5fc` (annotated tag) |
| Tag points to | `dc3df6c93986029e598e61b333d11ecee3a26bcd` (commit) |
| Release URL | https://github.com/amaster97/poker_solver/releases/tag/v1.5.0 |
| Acceptance test verdict | **SKIP** (Brown's `river_solver_optimized` binary not built locally — graceful skip per spec; framework verified wired correctly) |
| Total wall-clock | ~22 min (well under 40 min budget) |

## Step log

1. **Pre-flight (~1 min):** origin/main confirmed at `eea3a8b` (v1.4.3 tip); PR 23 worktree at `35bef3e`; PR 28 worktree at `8f88634`. Shared tree had untracked-only state; clean for parallel operation.
2. **F4 + F5 hygiene fix-ups on PR 23 (~1 min):**
   - F4: removed `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening` absolute path from `docs/pr_proposals/v1_5_pr_23_implementer_notes.md` line 3.
   - F5: reworded CHANGELOG entry to drop the `feedback_ui_packaging_sync.md` internal-memory file name; replaced with generic "documented Q4 default" phrasing.
   - Amended PR 23 tip. New SHA `ac45b8c2e55d11fa00a3e3939558807f07b8b4a1`.
3. **Cherry-pick PR 23 (~1 min):**
   - 5 clean cherry-picks: `e229608` `0026390` `fa4c03b` `4664112` `bfcfa3b`.
   - Final commit (amended `ac45b8c`) had the expected CHANGELOG.md conflict — additive merge: v1.5.0 entry placed ABOVE v1.4.3 entry as instructed. Continued with `GIT_EDITOR=true`. New commit `2b46093`.
4. **Cherry-pick PR 28 (~30 sec):** Single commit `8f88634` → `97efcc3`. Conflict-free (new file only).
5. **Maturin rebuild (~3 min):** `maturin develop --release` from `cargo` on PATH + symlinked venv. Built cfr_core successfully, installed editable. New entry point `solve_range_vs_range_rust` import-verified.
6. **Smoke tests (initial run, ~2 min): 5 failures surfaced** — all same root cause: `initial_hole_cards=None` in test fixtures incompatible with v1.4.3's PR-31 tightened validation (now requires empty tuple `()`). Affected three files:
   - `tests/test_node_locking.py:372`
   - `tests/test_range_vs_range_rust_diff.py:204`
   - `tests/test_v1_5_brown_apples_to_apples.py:256`
   Fixed all three by changing `None` to `()`. Re-ran: **54 passed, 1 skipped, 0 failed** in 152 sec.
7. **Acceptance test (~5 sec):** Both `dry_K72_rainbow` and `dry_A83_rainbow` parametrizations SKIPPED with reason: "Brown's river_solver_optimized not built; run `bash scripts/build_noambrown.sh` to enable parity tests." This is the spec-acceptable outcome — the test framework is wired correctly and will validate as soon as the Brown binary is built locally. Importantly, the test no longer fails at fixture construction (the `None`→`()` fix unblocked it).
8. **Version bump + CHANGELOG polish (~1 min):**
   - `pyproject.toml`: 1.4.3 → 1.5.0.
   - `poker_solver/__init__.py`: `__version__ = "1.5.0"`.
   - CHANGELOG header: "[1.5.0] - candidate (PR 23)" → "[1.5.0] - 2026-05-23".
   - Added PR 28 acceptance-test sub-section under the v1.5.0 entry.
   - Single bundling commit `dc3df6c`.
9. **Tag + push (~10 sec):** `git tag -a v1.5.0`, then `git push origin HEAD:main` (fast-forward `eea3a8b..dc3df6c`) and `git push origin v1.5.0`. Both clean.
10. **GitHub release (~3 sec):** `gh release create v1.5.0` with public-OK release notes at `/tmp/v1.5.0_release_notes.md`. Live at https://github.com/amaster97/poker_solver/releases/tag/v1.5.0.
11. **Post-ship verification:** `git ls-remote origin v1.5.0` confirms `544bd0e...` on origin. `gh release list` shows v1.5.0 as Latest.
12. **Cleanup:** ship worktree removed with `--force` (had .venv symlink + maturin build artifacts). PR 23 + PR 28 worktrees remain in place per ship plan (cleanup of those is a separate housekeeping task).

## Unexpected complexity

**One real surprise** (not severe): the test-fixture `initial_hole_cards=None` regression. Cause: PR 23 was authored on a v1.3-era base; the PR-31 validation in v1.4.3 tightened the HUNLConfig contract such that `None` is no longer accepted (only `()` for the chance-enum case). PR 23's own worktree didn't trigger this because the worktree's `poker_solver/hunl.py` was the v1.3-era version (no `_validate_initial_hole_cards`). On the ship surface (v1.4.3 hunl.py × PR 23 tests), the clash surfaced. Trivial 3-line fix; no algorithmic change required. Documented in the merged commit message.

**Worth noting:** the audit at `docs/v1_5_0_pr_23_audit.md` should be amended on a follow-up to include this fixture-drift finding so the next merge of a long-running branch isn't surprised the same way.

## Authorization compliance

- PR 23 audit cleared per `docs/v1_5_0_pr_23_audit.md` (APPROVED verdict).
- PR 28 verified compatible by audit.
- F4 + F5 hygiene fix-ups applied per ship plan §2.
- No force-push; no branch deletion.
- PR 29 NOT included (private-only — confirmed by absence from cherry-pick list).
- Release notes audited: no `/Users/ashen/...` paths, no session IDs, no internal-memory file names, no PII.
- Per autonomous-commit authorization: end-to-end commit + push + tag + release executed without interrupting orchestrator.

## Follow-ups (for next session, not blocking)

1. **Build Brown's `river_solver_optimized`** in CI/local — converts the acceptance test from SKIP to PASS/FAIL and gives empirical Brown-parity evidence to publish.
2. **Audit amendment** on `docs/v1_5_0_pr_23_audit.md` to record the `initial_hole_cards=None` → `()` fixture-drift incident, so future long-running-branch merges check this surface.
3. **Cleanup of PR 23 + PR 28 worktrees** (separate housekeeping; ship plan only specified ship-v1.5.0 cleanup).
4. **v1.5.1 backlog** (already noted in CHANGELOG "Deferred" section): preflop RvR, EMD bucketing, SIMD terminal-leaf, range_aggregator wiring, UI surfacing.
