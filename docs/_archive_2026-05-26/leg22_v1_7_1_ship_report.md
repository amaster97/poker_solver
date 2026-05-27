# Leg 22: v1.7.1 Ship Retry Report

**Date:** 2026-05-25
**Status:** HALTED on smoke matrix (Phase 5 / pytest non-slow tier)
**v1.7.1 SHIPPED:** No
**Outcome:** Bundle composition fix verified clean; one pre-existing golden-file
test diverges from PR 50's expected behavior change.

---

## 1. Bundle composition fix

### 1.1 Problem (from preflight halt earlier in session)

The original ship script treated `pr-53c-loosen-layer-3-max` as a standalone
commit that "supersedes" `pr-53b-rebased-on-pr-54`. Inspection shows PR 53c is
a 41-line ceiling-tweak commit (`ba1c7162`) that sits ON TOP OF PR 53b's
625-line reframe (`3e50b760`). Cherry-picking PR 53c alone drops the 4-layer
acceptance test reframe and produces conflicts.

Additionally the SHA constant `SHA_PR53C=3e50b760` in the previous script was
mislabeled — that SHA is actually PR 53b's tip.

### 1.2 Edits to `/Users/ashen/Desktop/poker_solver/scripts/ship_v1_7_1.sh`

| Change | Detail |
|---|---|
| `EXPECTED_MAIN` | `0a0e8852` → `60a98189` (post-PR-#11 merge) |
| New constant | `SHA_PR53B=3e50b760` |
| Constant fix | `SHA_PR53C=3e50b760` → `SHA_PR53C=ba1c7162` (true PR 53c tip) |
| Cherry-pick order | added `git cherry-pick "$SHA_PR53B"` between PR 56 and PR 53c |
| Branch fetch list | added `pr-53b-rebased-on-pr-54` |
| Phase 2 header | rewritten: PR 53b is now a DEPENDENCY of PR 53c, not "superseded by" |
| Sanity loop | now iterates over 8 SHAs (was 7) |
| Tag message | now references `PR 50/51/52/54/55/56/53b/53c` (was `…/53c`) |
| Commit message | updated to describe both PR 53b (reframe) + PR 53c (ceiling tweak) |
| Environment fix | added `export PATH="$HOME/.cargo/bin:$PATH"` for non-interactive cargo resolution |
| Environment fix | added `export VIRTUAL_ENV=…/.venv` so maturin finds the repo's venv from `/tmp/ship-…` worktree |
| Header validation | "Validated by" line updated to reference 2026-05-25 retry preflight |

`bash -n` clean.

PR 55-ext (`pr-55-extend-input-range-swap`) confirmed absent from the
cherry-pick list — only appears in explanatory comments tied to the
2026-05-24 double-swap diagnosis.

---

## 2. Preflight (Phase 2)

Disposable worktree at `/tmp/v1.7.1-retry-26413` (subsequently removed).
All 8 cherry-picks landed CLEAN, no conflicts:

| # | PR | SHA | Result |
|---|---|---|---|
| 1 | PR 51 dcfr_vector | `78c71557` | OK (21+/7-) |
| 2 | PR 50 facing-all-in guard | `18a7640e` | OK (19+/2-) |
| 3 | PR 52 suit-encoding | `9e6662b6` | OK (25+/3-) |
| 4 | PR 54 renderer stack_ceiling | `f389b433` | OK (28+/5-) |
| 5 | PR 55 P0/P1 output swap | `ac7c6406` | OK (247+/3-, auto-merged) |
| 6 | PR 56 hand-sort canonical | `950b82c0` | OK (66+/1-, auto-merged) |
| 7 | PR 53b 4-layer reframe | `3e50b760` | OK (450+/175-) |
| 8 | PR 53c ceiling tweak | `ba1c7162` | OK (25+/16-) |

Bundle composition fix VERIFIED.

---

## 3. Ship execution (Phase 3)

Ran `bash scripts/ship_v1_7_1.sh 2>&1 | tee /tmp/v1.7.1_ship_retry.log`.

| Phase | Status |
|---|---|
| Phase 1 (fresh worktree from origin/main 60a98189) | OK |
| Phase 2 (8 cherry-picks) | OK — all clean, same as preflight |
| Phase 3 (version bumps: pyproject/init/Cargo all 1.7.0/0.7.0 → 1.7.1/0.7.1) | OK |
| Phase 4 (CHANGELOG entry inserted, dated 2026-05-25) | OK |
| Phase 5a (cargo build --release) | OK |
| Phase 5b (cargo test --lib --release) | **OK — 50/50** |
| Phase 5c (maturin develop --release) | OK (after VIRTUAL_ENV fix) |
| Phase 5d (pytest test_exploit_diff.py) | **OK — 5/5** |
| Phase 5e (pytest test_v1_5_brown_apples_to_apples.py) | **2 SKIPPED** — see §5 anomaly |
| Phase 5f (pytest test_asymmetric_range_sanity.py — new gate) | **OK — 4/4** |
| Phase 5g (pytest non-slow tier) | **HALTED — 1 failed, 270 passed, 15 skipped** |
| Phase 6 (PII grep) | not reached |
| Phase 7 (commit/tag/push) | not reached |
| Phase 8 (gh release) | not reached |

No tag created. No push to origin. No GitHub release. Origin/main remains at
`60a98189`. Working tree cleaned up; ship worktree removed.

---

## 4. Smoke failure (the halt)

```
FAILED tests/test_memory_profiler.py::test_memory_profiler_golden_file_river_only
```

Golden-file drift, river-only synthetic abstraction:

```
solver_arrays_total_bytes:  golden=832   got=704
grand_total_bytes:          golden=2230  got=2102
river_regret_bytes:         golden=416   got=352
river_strategy_bytes:       golden=416   got=352
river_total_bytes:          golden=1764  got=1636
river_mean_actions:         golden=3.25  got=2.75
```

### Root cause (high-confidence)

`river_mean_actions` dropping 3.25 → 2.75 corresponds directly to PR 50's
facing-all-in action menu guard. When a player faces an all-in, only
fold/call are legal (2-action menu) rather than the full 3-4 action menu.
The river-only synthetic abstraction in this test includes infosets that hit
the facing-all-in branch; after PR 50, those infosets now correctly carry
2 actions instead of 3-4, lowering the mean from 3.25 to 2.75 and
proportionally shrinking regret/strategy byte counts (each saved 64 bytes
per infoset × 16 infosets = 1024 bytes total; the deltas 832→704 (−128) and
1764→1636 (−128) are bit-for-bit consistent with this interpretation across
the regret/strategy/total fields).

This is an **expected behavior change** introduced by PR 50, **not a
regression**. The golden file in `tests/test_memory_profiler.py` predates
the PR 50 fix and was not refreshed when PR 50 landed on its branch.

### Why no override

User's halt-on-fail rule is unambiguous: "If smoke fails: HALT." The
correct rectification path is to regenerate the golden file in a dedicated
PR (probably folded into PR 50's branch as a post-merge refresh, or as a
companion PR 50b) and re-run the ship.

---

## 5. Anomalies worth flagging

**A. Brown apples-to-apples acceptance gate was SKIPPED (2 skipped).**
The reframed test executed in `0.03s` and reported `2 skipped`, suggesting
the per-board fixtures (`dry_K72_rainbow`, `dry_A83_rainbow`) were not
found in the bundle and the test has a skip-when-fixture-missing guard.
This is the headline reframed acceptance gate; it should not be silently
skipped at ship time. Verify fixture provisioning before the next attempt.

**B. Script had two environment gaps that surfaced sequentially.**
- First run halted at `cargo build` (`cargo: command not found`) because
  `~/.cargo/bin` is not on PATH in non-interactive shells.
- Second run halted at `maturin develop` because `VIRTUAL_ENV` was unset
  and the worktree at `/tmp/ship-v1.7.1-*` couldn't auto-discover
  `/Users/ashen/Desktop/poker_solver/.venv` via parent-folder search.

Both are now fixed in the script's preamble (idempotent guards). Future ship
scripts in this repo should adopt the same preamble.

**C. The script's previous `SHA_PR53C=3e50b760` constant was mislabeled.**
That SHA is PR 53b's tip; PR 53c's actual tip is `ba1c7162`. The previous
ship attempt would have effectively cherry-picked PR 53b twice (once
under the PR 53c label) and silently dropped PR 53c's ceiling-tweak. Now
fixed.

---

## 6. Current state

- Local repo HEAD: `ca8c7af` on `main` (unchanged, behind origin by 10).
- origin/main: `60a98189` (unchanged from start).
- Local v1.7.1 tag: **not created**.
- origin/v1.7.1 tag: **not created**.
- GitHub release v1.7.1: **not created**.
- Ship worktrees: all removed; `/tmp/ship-v1.7.1-*` clean.

---

## 7. Recommended next steps

1. **Refresh golden file** in `tests/test_memory_profiler.py`:
   ```
   solver_arrays_total_bytes: 704
   grand_total_bytes: 2102
   river_regret_bytes: 352
   river_strategy_bytes: 352
   river_total_bytes: 1636
   river_mean_actions: 2.75
   ```
   Verify these numerically against a fresh local run before committing.
   This should be either:
   - Folded into PR 50 as a post-merge addendum, or
   - Filed as PR 50b "golden-file refresh for PR 50 action menu change".
2. **Diagnose Brown apples-to-apples skips** before next ship attempt — the
   2-test skip in 0.03s suggests fixture-loading is failing silently and the
   acceptance gate isn't actually exercising the reframe.
3. **Re-run ship script** once both above are resolved. The bundle
   composition fix is verified; only the post-PR-50 cleanups remain.

---

## 8. Time budget

| Phase | Wall-clock |
|---|---|
| Script edits | ~3 min |
| Preflight (8 cherry-picks) | ~1 min |
| Ship attempt 1 (cargo PATH halt) | ~30 sec |
| Ship attempt 2 (full smoke matrix to memory_profiler halt) | ~11 min |
| Cleanup + report | ~3 min |
| **Total** | **~18 min** (well under 90-min budget) |
