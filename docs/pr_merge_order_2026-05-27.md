# PR Merge-Order Analysis (4 open PRs)

**Generated:** 2026-05-27T10:03Z (UTC)
**Analyst worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-merge-analysis`
**Analyst branch:** `analysis/pr-merge-2026-05-27` (off `origin/main` @ `9213085`)
**Scope:** Pre-flight assessment only — no merges performed. Read-only on the 4 open PRs.

---

## TL;DR

**Recommended order:** `#89 → #20 → #49 → #94`

- **Zero file-level conflicts in any pairwise or sequential ordering.** All 4 PRs touch disjoint file sets; sequential merge of `89 → 20 → 49 → 94` clean-merged with `ort` strategy, no overlap.
- **All 4 are LOW-to-MEDIUM risk.** None touch engine/solver code. Mix is: 1 build-script (#89), 1 CI infra (#20), 2 docs-only (#49, #94).
- **CI gating:** all 4 PRs are green on the 3 currently-required checks (`Golden File Check`, `Ship Dry Run`, `Skip-Ban`). PR #20 additionally exercises its own new matrix; macOS-14 leg passed, macOS-13 + Ubuntu-22.04 legs still pending at snapshot time but unblock-only.
- **The #89-before-#20 ordering is recommended on principle, not necessity** — see Dependencies §.
- **Caveat on #94:** branch HEAD `db77bd4` is recent (05:58 EDT, ~5 min before snapshot). User flagged agent `aab53475` may still be revising. Do not merge #94 until you confirm no further commits land — see Caveats §.

---

## Per-PR snapshot

| PR  | Title (truncated)                                              | Branch                                          | Head SHA   | Files | +Lines | -Lines | Touches            | Risk    | CI                           |
|-----|----------------------------------------------------------------|-------------------------------------------------|------------|-------|--------|--------|--------------------|---------|------------------------------|
| #89 | `fix(build): patch Brown's subgame_config.cpp for GCC 11`     | `fix-brown-buildable-ubuntu`                    | `5f814e4`  | 1     | 28     | 0      | build-script       | MEDIUM  | 3/3 green                    |
| #20 | `feat(ci): cross-platform CI matrix for v1.8 prep`             | `pr-64-cross-platform-ci-matrix`                | `39a01c8`  | 3     | 130    | 0      | CI + 1 test-marker | MEDIUM  | 5/7 green, 2 matrix pending  |
| #49 | `docs: RESUME_2026-05-26 morning hand-off`                     | `pr-92-resume-doc`                              | `4922364`  | 1     | 518    | 0      | docs               | LOW     | 3/3 green                    |
| #94 | `docs(persona): post-v1.8.0 production-scale retest results`  | `docs/persona-post-v1-8-0-production-retest`    | `db77bd4`  | 9     | 662    | 0      | docs + retest scripts | LOW  | 3/3 green                    |

### File touch detail

- **#89** — `scripts/build_noambrown.sh` (sed-based idempotent patch of Brown's `unordered_map<string, JsonValue>` → `map`, for GCC 11 libstdc++).
- **#20** — `.github/workflows/ci.yml` (new, matrix: macos-14 aarch64 / macos-13 x86_64 / ubuntu-22.04 x86_64), `.github/workflows/lint.yml` (new, clippy+rustfmt+ruff+black, all `continue-on-error`), `tests/test_river_diff_self_sanity.py` (+2 lines, `@pytest.mark.slow`).
- **#49** — `docs/RESUME_2026-05-26.md` only.
- **#94** — `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md`, `docs/v1_8_1_candidate_findings_2026-05-27.md`, 6 files under `scripts_retest/` (no overlap with any existing script directory).

### Last-touched timestamps (commit author dates, EDT)

| PR  | Last commit SHA | Subject                                                                                  | Authored             |
|-----|-----------------|------------------------------------------------------------------------------------------|----------------------|
| #89 | `5f814e4`       | `fix(build): patch Brown's subgame_config.cpp ...`                                       | 2026-05-27 05:17 EDT |
| #20 | `39a01c8`       | `test: mark heavy river_diff_self_sanity convergence tests @pytest.mark.slow`            | 2026-05-27 05:26 EDT |
| #49 | `4922364`       | `docs(RESUME): eighth-pass refresh — convention purge LANDED + ship-ready`               | 2026-05-27 05:18 EDT |
| #94 | `db77bd4`       | `docs(persona): revise W3.5 finding to Hypothesis A vs B (convergence vs wrapper-bug)`   | 2026-05-27 05:58 EDT |

(All four touched within a ~40 min window today. No staleness concerns.)

---

## Pairwise & sequential merge tests

All tests run from a fresh `origin/main` checkout in the analyst worktree using `git merge --no-ff --no-commit`. The `ort` strategy reported "Automatic merge went well" for every case.

### Pairwise (each PR vs main, isolated)

| PR  | Result               | Files staged after merge                                                                 |
|-----|----------------------|------------------------------------------------------------------------------------------|
| #89 | clean (no conflicts) | M `scripts/build_noambrown.sh`                                                           |
| #20 | clean                | A `.github/workflows/ci.yml`, A `.github/workflows/lint.yml`, M `tests/test_river_diff_self_sanity.py` |
| #49 | clean                | A `docs/RESUME_2026-05-26.md`                                                            |
| #94 | clean                | A `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` + 8 more (all `A`, listed above) |

### Sequential (89 → 20 → 49 → 94 on top of main)

```
9213085 origin/main
b457652 test merge 89  (Merge made by 'ort'; 1 file +28)
ab157e1 test merge 20  (Merge made by 'ort'; 3 files +130)
e980e89 test merge 49  (Merge made by 'ort'; 1 file +518)
07cee94 test merge 94  (Merge made by 'ort'; 9 files +662)
```

No conflict markers, no auto-resolve choices flagged, final tree clean.

### File-overlap matrix (paths touched, set-intersection)

|       | #89 | #20 | #49 | #94 |
|-------|-----|-----|-----|-----|
| **#89** | —   |  ∅  |  ∅  |  ∅  |
| **#20** |  ∅  | —   |  ∅  |  ∅  |
| **#49** |  ∅  |  ∅  | —   |  ∅  |
| **#94** |  ∅  |  ∅  |  ∅  | —   |

All pairs are disjoint. Order is order-of-operations only, not conflict-driven.

---

## Dependencies (real and apparent)

### Stated: "PR #20 needs PR #89 to pass Ubuntu CI"

**Verdict: not strictly true at the level of CI today.** Reasoning:

1. PR #20's new `.github/workflows/ci.yml` matrix builds the **Rust + Python** tier (via `maturin develop`) and runs `cargo test`. It does **not** invoke `scripts/build_noambrown.sh`. The Ubuntu leg should pass without PR #89.
2. The existing `.github/workflows/release.yml` is the only workflow that runs `bash scripts/build_noambrown.sh`, and it is pinned to `macos-14`. Apple Clang/libc++ accepts the recursive `std::unordered_map<std::string, JsonValue>` member just fine — that's why CI hasn't been red.
3. PR #89's patch only matters **if** a future CI step runs the Brown build on Ubuntu/GCC. None of the four PRs in this set add that step.

**However**, ordering #89 before #20 is still preferable because:
- It establishes the Ubuntu buildability invariant **before** the Ubuntu CI runner is in place, so a follow-up PR that wires Brown-build into the matrix won't need to be ordered around #89 separately.
- The diff in #89 is tiny (28 LOC, idempotent sed), and is dead code on macOS — landing it first is purely upside.

### Other dependencies

- **#49 and #94 are independent docs.** Order between them is free.
- **#20's lint workflow is entirely `continue-on-error`** for first-baseline. It cannot block any other PR's CI by failing.

---

## Risk classification

| PR  | Classification | Rationale                                                                                                         |
|-----|----------------|-------------------------------------------------------------------------------------------------------------------|
| #89 | MEDIUM         | Modifies a build script. Idempotent (grep-guarded), zero-behavior-change on macOS (no `unordered_map` line to match → no-op), affects Brown C++ source on Ubuntu only. No engine touch. |
| #20 | MEDIUM         | New CI workflows + 1-line test marker. Lint workflow non-gating. CI workflow gating but proven green on macOS-14. macOS-13 + Ubuntu legs pending at snapshot — flag if either fails. |
| #49 | LOW            | docs-only, single new file, no cross-reference touch.                                                             |
| #94 | LOW            | docs + new `scripts_retest/` files. No engine, no test imports into `tests/`, no `pyproject.toml` changes.       |

No HIGH-risk items in this batch.

---

## CI state snapshot (as of 10:00 UTC)

| PR  | Golden File Check | Ship Dry Run | Skip-Ban | Lint (python) | Lint (rust) | Matrix tests                                            |
|-----|-------------------|--------------|----------|---------------|-------------|---------------------------------------------------------|
| #89 | PASS              | PASS         | PASS     | —             | —           | —                                                       |
| #20 | PASS              | PASS         | PASS     | PASS          | PASS        | macos-14: PASS; macos-13: pending; ubuntu-22.04: pending |
| #49 | PASS              | PASS         | PASS     | —             | —           | —                                                       |
| #94 | PASS              | PASS         | PASS     | —             | —           | —                                                       |

**Note:** PRs #89, #49, #94 don't trigger the new CI matrix because that matrix is introduced *by* PR #20 (not yet on main). After PR #20 lands, all subsequent PRs will inherit the matrix checks.

---

## Recommended merge sequence

**`#89 → #20 → #49 → #94`**

### Rationale per step

1. **#89 first** — Tiny, surgical, zero-risk on macOS, future-proofs Ubuntu builds. Land before any CI matrix that might one day call into the Brown build. Re-running CI on #20 after #89 lands gives the strongest signal.
2. **#20 second** — Wait for macos-13 + Ubuntu matrix legs to complete on PR #20 itself first. If either fails, address before merging. Once green, merge — this defines the CI matrix that subsequent PRs inherit.
3. **#49 third** — Docs handoff. Merge after #20 so the new matrix exercises the doc (trivial, but free signal).
4. **#94 last** — Largest doc + retest-script payload. Merging after #20 lets the new CI matrix sanity-check the new files. **Block on the #94 freshness caveat below.**

### Alternative orderings (all also valid, no conflicts)

- `#49 → #89 → #20 → #94` — fine if you want the lowest-risk doc to land first as a warm-up.
- `#89 → #49 → #20 → #94` — fine, identical end-state.

Any permutation works mechanically; the recommended order is just the cleanest causal narrative.

---

## Caveats

### CAVEAT 1 — PR #94 freshness

**Do NOT merge #94 until you confirm the persona-retest agent is finished revising.**

- Branch head at snapshot: `db77bd4` (authored 2026-05-27 05:58:09 EDT, ~5 min before this analysis).
- Earlier commit `6004c93` (05:53 EDT) was the initial post-v1.8.0 retest doc; `db77bd4` revised W3.5 to Hypothesis A vs B.
- The user's task description noted agent `aab53475` may still be iterating. I could not positively confirm whether the agent has finished — no `aab53475` process found in `ps aux`, but absence of evidence ≠ evidence of absence (the agent may be between bash calls).
- **Recommendation:** before merging #94, run `git log -1 --format="%H %ci" origin/docs/persona-post-v1-8-0-production-retest`. If the head SHA has changed since `db77bd4` and the timestamp is within the last 10 min, wait.

### CAVEAT 2 — PR #20 matrix legs pending

- At snapshot, `macos-13 / 3.13 / x86_64-apple-darwin` and `ubuntu-22.04 / 3.13 / x86_64-unknown-linux-gnu` legs of PR #20's own CI matrix are still queued (the macOS-14 leg passed in 24m). Hold #20 until both report PASS.
- If the Ubuntu leg fails for a reason unrelated to Brown (i.e., not in `scripts/build_noambrown.sh`), PR #89 won't fix it.

### CAVEAT 3 — PR #20's lint workflow is informational only

- All 4 lint steps (clippy, rustfmt, ruff, black) are `continue-on-error: true` for first-baseline. They will not block merge if they fail. This is intentional per the inline comments. Worth knowing if you trust the green checks at face value.

### CAVEAT 4 — Brown-build dependency is "soft" today

- As detailed in Dependencies §, no current CI step exercises the Brown C++ build on Ubuntu. PR #89's patch is dormant insurance on macOS and on the current CI matrix. The hard dependency only materializes when some future workflow runs `build_noambrown.sh` on Ubuntu. Order #89 first anyway to keep the property monotone.

---

## What this doc does NOT cover

- Whether any of the PR contents are semantically correct (out of scope for merge-order analysis).
- Whether `.github/workflows/release.yml` should be matrixed (separate concern; would be a new PR).
- Whether `docs/RESUME_2026-05-26.md` (#49) conflicts *semantically* with `docs/persona_status_post_v1_8_0_shipped_2026-05-27.md` (#94) — both are status docs covering overlapping time windows. They land in different files (no merge conflict), but a human-readable cross-reference reconciliation may be wanted post-merge.

---

## Reproducing this analysis

```bash
# Fresh worktree off main:
git worktree add /tmp/pr-merge-analysis -b analysis/pr-merge origin/main
cd /tmp/pr-merge-analysis

# Fetch PR heads:
git fetch origin pull/89/head:pr-89 pull/20/head:pr-20 \
                 pull/49/head:pr-49 pull/94/head:pr-94

# Test each pair against main (repeat with --abort between):
git merge --no-commit --no-ff pr-89
git merge --abort && git reset --hard origin/main

# Sequential test:
git merge --no-ff -m "t" pr-89 && \
git merge --no-ff -m "t" pr-20 && \
git merge --no-ff -m "t" pr-49 && \
git merge --no-ff -m "t" pr-94

# Cleanup:
git worktree remove /tmp/pr-merge-analysis
```

---

## Sign-off

Read-only analysis. No merges performed on origin. No PR branches touched.
Analyst worktree will be removed by the user after review.
