# PR #20 — CI Timeout Bump Attempt (Hypothesis A Disambiguation)

**Date:** 2026-05-26
**Branch:** `pr-64-cross-platform-ci-matrix` (PR #20 — "feat(ci): cross-platform CI matrix for v1.8 prep")
**Workspace branch:** `pr-20-ci-timeout-bump` (preserved on origin)
**Author:** automation agent
**Reference:** `docs/pr_20_leduc_diff_linux_diagnosis_2026-05-26.md`

---

## Procedure executed

1. Created worktree from `origin/pr-64-cross-platform-ci-matrix` at `/Users/ashen/Desktop/poker_solver_worktrees/pr-20-timeout` on workspace branch `pr-20-ci-timeout-bump`.
2. Edited `.github/workflows/ci.yml` — only two lines changed (verified via `git diff`).
3. Committed (`8675e70`), pushed workspace branch to `origin/pr-20-ci-timeout-bump` for traceability.
4. Cherry-picked `8675e70` onto a fresh `pr-20-rebase-with-timeout-fix` from `origin/pr-64-cross-platform-ci-matrix` (Approach A — no conflicts).
5. Force-pushed (`--force-with-lease`) to `origin/pr-64-cross-platform-ci-matrix`. Old tip `2226c6d` → new tip `14762c8`.

## Diff — only 2 lines changed

```
@@ -30,7 +30,7 @@ jobs:
     runs-on: ${{ matrix.os }}
-    timeout-minutes: 30
+    timeout-minutes: 60

@@ -63,7 +63,7 @@ jobs:
       - name: Pytest smoke (fast tier)
-        run: pytest -m "not slow" --timeout=120
+        run: pytest -m "not slow" --timeout=300
```

| Field | Before | After |
|---|---|---|
| Job `timeout-minutes` | 30 | 60 |
| Pytest `--timeout` | 120 | 300 |

## CI outcome

_Pending — Monitor armed on task `bqcj7ko58`. Update once matrix terminal._

## Decision

_To be determined based on CI outcome._
