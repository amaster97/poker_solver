# Ship Process Hardening — Pre-Ship CI Guard Recommendations

**Date:** 2026-05-25
**Trigger:** v1.7.1 ship halted/killed 3 times this session (retries #1, #2, #3)
**Audience:** Solver maintainer (and future agents inheriting the ship flow)
**Scope:** Process-level fixes, not per-incident patches

---

## 1. The three hazard patterns observed

Three different failures, one common root: **the ship script is the first place where the joint stack gets exercised end-to-end.** Each PR passes its own tests in isolation. The bundled cherry-pick chain is only tested at ship time, and ship time is the worst time to discover a stale fixture, a missing prereq, or a SHA conflict.

### A. SHA-pinning hazard ("the hand-rolled bash drift")

`scripts/ship_v1_7_1.sh` hardcodes 10 PR SHAs (lines 97–120). Each SHA was correct at the moment the script was authored, but PR branches keep moving (rebases, follow-on commits, PR 53 → 53b → 53c). Retry #2's PR 53b/53c stacking conflict was exactly this — the script referenced an older PR 53 SHA that no longer cherry-picked cleanly on top of PR 54.

The same pattern bites whenever a bundled PR receives a touch-up rebase after the ship script is staged. There is no automated check that says "your pinned SHAs still cherry-pick onto current main."

### B. Stale-golden hazard ("the goldens don't refresh themselves")

PR 50's correctness fix changes the canonical solver tree shape (mean actions 3.25 → 2.75, grand total 2230 → 2102 bytes). The `memory_profiler` golden file was written before that fix landed, so the golden assertion failed on the new behavior — but the failure looked like "PR 50 broke something" when actually the GOLDEN was stale.

Retry #1 halted on exactly this. The fix (PR 59) was a one-line regeneration. The cost was a full ship attempt.

### C. Silent-skip hazard ("the test passed because it never ran")

`tests/test_v1_5_brown_apples_to_apples.py` (the load-bearing parity gate) uses `pytest.skip()` when Brown's `river_solver_optimized` binary is missing. The ship script's worktree at `/tmp/ship-v1.7.1-*` does NOT inherit the gitignored prebuilt binary from the shared tree, so retry #2's gate reported `2 SKIPPED in 0.03s` — which the smoke matrix interpreted as PASS.

This is the same hazard family as the v1.7.0 `.so` arch mismatch (silent test-skip on x86_64-on-arm64). Anywhere a "passes" condition includes "didn't run," there's a load-bearing-skip hazard.

---

## 2. CI guard recommendations (concrete)

### Guard A — Ship-bundle dry-run workflow (SHA hazard)

Add `.github/workflows/ship_bundle_preflight.yml` that runs on every PR push to any `pr-*` branch:

1. Check out `origin/main`.
2. Read the current `scripts/ship_v1_7_1.sh` (or the active ship script) and extract its pinned SHA list.
3. For each open `pr-*` branch, attempt the cherry-pick chain against a scratch worktree (no commit).
4. If any cherry-pick conflicts: apply PR label `ship-bundle-conflict` and post a comment with the failing SHA + the rebased SHA it should be.
5. If clean: apply PR label `ship-bundle-clean`.

**Cost:** ~3 minutes per PR push. Worth it.

**Effect:** Retry #2's PR 53b/53c conflict would have shown up as a red label on PR #15 the moment PR 53c was force-pushed.

### Guard B — Golden regeneration discipline (stale-golden hazard)

1. Tag golden-file tests with `@pytest.mark.golden`.
2. Add `make regen-goldens` (or `pytest --update-goldens`) that re-runs the tagged tests in record mode and overwrites the fixture.
3. Pre-commit hook: if a tagged golden test fails AND the commit message does not contain `[regen-goldens]`, block the commit. If the tag IS present, run `make regen-goldens` automatically and stage the refreshed fixtures.
4. CI: same rule — golden test failure without `[regen-goldens]` in the PR's commit messages = red.

**Effect:** PR 50 would have either shipped with the refreshed memory_profiler golden (because its author added `[regen-goldens]` to the commit) or never landed (because pre-commit blocked the stale-golden state). PR 59 becomes unnecessary.

### Guard C — Silent-skip ban for load-bearing tests

1. Forbid `pytest.skip()` in `tests/acceptance/` and any test marked `@pytest.mark.acceptance` or `@pytest.mark.load_bearing`. Enforce via a tiny `conftest.py` plugin that raises if `pytest.skip()` is reached in a marked test.
2. Acceptance tests must use `pytest.fail()` with an explicit message on missing prereqs ("Brown binary missing — build before invoking gate"), OR use the `_skip_or_fail()` pattern PR 60 already establishes (skip in dev, fail under `REQUIRE_BROWN_PARITY=1`).
3. Pre-commit hook: grep tests/acceptance/ for `pytest.skip(` and reject; allow `_skip_or_fail(` (which respects the env var).

**Effect:** Retry #2's `2 SKIPPED` would have been `2 FAILED` instead, which the ship script's `set -e` would have caught immediately rather than passing through to the tag/push phase.

---

## 3. Migration path (bash → CI-managed)

Three phases. Don't try to skip ahead — each phase de-risks the next.

**Phase 1 (v1.7.x patch chain):** Keep `scripts/ship_v1_7_1.sh` as-is. Add Guard A (dry-run workflow) and Guard C (silent-skip ban) as PR-gate CI checks. Guard B (golden regen) layers in as a pre-commit hook. The bash script remains the ship entry point; CI just prevents the three hazard classes from reaching ship time.

**Phase 2 (v1.8.x):** A `.github/workflows/release.yml` triggered by pushing a `ship/v1.x.y` branch. It runs the cherry-pick chain, the smoke matrix, the version bumps, the changelog insertion, and the tag — all in GitHub Actions. The bash script becomes a thin local-rehearsal wrapper for the same workflow. Failures roll back automatically (no half-pushed tags).

**Phase 3 (v2.x+):** `release-please` or `semantic-release` driven by conventional-commits. Bundle composition becomes declarative (a `.release-please-manifest.json`), version bumps are automatic, the changelog writes itself. The ship-script bundle goes away.

The user is one person solving real problems with this tool. Phase 1 is enough investment to stop the 3-retry-per-ship pattern. Phase 2 is worth it once v1.8 lands. Phase 3 is luxury — only do it if v2 is a big-enough change that the manifest pays back.

---

## 4. Immediate action for v1.7.1+

1. **Ship v1.7.1 first.** Do NOT block the current ship on this hardening work. Retry #4 has all three blockers explicitly addressed at the script level (PR 59 in bundle, PR 60 `_skip_or_fail` + `REQUIRE_BROWN_PARITY=1`, binary-link guard in ship script Phase 5). The hardening is for v1.7.2+ scope, not v1.7.1.
2. **After v1.7.1 ships:** open `Issue: ship-process hardening tracker` referencing this doc; spawn three sub-issues for Guards A/B/C.
3. **Add `--dry-run` flag to `scripts/ship_v1_7_1.sh`** (or its v1.7.2 successor) that runs Phases 1–6 (worktree, cherry-pick chain, version bump, changelog, smoke matrix, PII grep) but skips Phase 7+ (commit, tag, push, release). This lets future ship attempts validate the bundle end-to-end without burning a tag.
4. **Make the halt-on-fail explicit** — the script already has `set -euo pipefail` (line 74) but each phase's marker comment should also say "HALT POINT: failure here means \<X\>." Helps future agents reading the log know which phase to retry from.

---

## 5. Recommendation

**High-priority for v1.7.2 scope.** The three-retry pattern is not random — it is the systematic consequence of a hand-rolled ship process that defers integration testing to ship time. The 25-minute investment of writing this doc is paid back the first time Guard A flags a stale SHA before retry #5.

Do not ship v1.8 features before Guard A is in place. The bigger the bundle, the more SHAs to drift, and v1.8 (NEON SIMD release) will be a larger bundle than v1.7.1's nine PRs.

The Phase 1 guards are the floor. Phases 2 and 3 are aspirational and depend on user appetite for CI work vs. solver work.
