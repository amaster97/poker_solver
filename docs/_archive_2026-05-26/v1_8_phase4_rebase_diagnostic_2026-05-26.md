# v1.8 Phase 4 (PR #32) Rebase Diagnostic — 2026-05-26

**Branch:** `origin/pr-71-v1.8-phase4-compute-strategy-simd`
**PR:** GitHub #32 — currently shown `CONFLICTING` with `origin/main`.
**Status:** Read-only diagnostic. No git mutations. No worktree creation.
**Trigger:** Mac crash wiped `/private/tmp/v1.8-phase4-57428`; need to plan the
rebase without losing the commit on origin.
**Companion:** Phase 3 (PR #33, branch `pr-70-v1.8-phase3-update-strategy-sum-simd`)
is also CONFLICTING and has its own rebase in flight. Phase 4 is **logically**
stacked on Phase 3 in the v1.8 plan, but the branches were created as
**parallel siblings** off the same old base (see §3 below).

---

## 1. PR #32 commit list (ahead of `origin/main`)

```
0734c0d feat(cfr_core): v1.8 Phase 4 — compute_strategy SIMD
```

Single commit. Author: amaster97. Date: 2026-05-25 22:54 EDT.

Commit message excerpt:
> NEON + SSE2 + AVX2 paths for regret matching (compute_strategy) hot loop.
> Includes max(0, R) clip + sum-then-divide normalization. Runtime-detect
> AVX2 on x86_64; scalar fallback for tail. All paths bit-identical to
> scalar reference including the all-negative-regret → uniform-distribution
> edge case. Follows v1.8 Phase 1 (PR 61) pattern.

---

## 2. File-level diff against `origin/main`

```
 crates/cfr_core/src/dcfr_vector.rs        |  27 +--
 crates/cfr_core/src/simd.rs               | 360 +++++++++++++++++++++++++++++-
 crates/cfr_core/tests/test_simd_phase4.rs | 189 ++++++++++++++++
 3 files changed, 555 insertions(+), 21 deletions(-)
```

### 2a. `crates/cfr_core/src/dcfr_vector.rs` — Phase 4 change

Single hunk: `@@ -204,30 +204,21 @@ impl VectorDCFR {`

Replaces the per-hand body of `compute_strategy` (lines 204-232 in main) with
a call to `crate::simd::compute_strategy_row(regrets_row, out_row)`. The old
inline scalar clamp + sum + normalize / uniform-fallback is moved into
`simd::compute_strategy_row_scalar` (added in `simd.rs`).

### 2b. `crates/cfr_core/src/simd.rs` — Phase 4 additions

| Hunk anchor | Adds |
| ----------- | ---- |
| `@@ -144,6 +144,43 @@ pub fn normalize_scalar` | `pub fn compute_strategy_row_scalar` |
| `@@ -378,12 +415,288 @@ mod neon {` | NEON: `compute_strategy_row_neon`; **new `mod sse2` block** with `compute_strategy_row_sse2`; **new `mod avx2` block** with `compute_strategy_row_avx2` |
| `@@ -470,6 +783,47 @@ pub fn update_strategy_sum(...)` | Public dispatch `pub fn compute_strategy_row(...)` (NEON / AVX2-detected / SSE2 / scalar) |

### 2c. `crates/cfr_core/tests/test_simd_phase4.rs` — new file

189-line integration parity test. Verifies `simd::compute_strategy_row`
(dispatch) matches `simd::compute_strategy_row_scalar` bit-for-bit over row
lengths 0..=12, width-14 HUNL row, all-negative-regret edge case, all-zero
edge case. No naming collision with `test_simd_phase3.rs` or any existing
test file.

---

## 3. Overlap matrix with Phase 3 (PR #33)

### Shared merge base (both branches)

```
$ git merge-base origin/main origin/pr-71-v1.8-phase4-compute-strategy-simd
60a9818947cc8ae56570359d21fb81baf8a9e048

$ git merge-base origin/main origin/pr-70-v1.8-phase3-update-strategy-sum-simd
60a9818947cc8ae56570359d21fb81baf8a9e048

$ git merge-base origin/pr-70-v1.8-phase3-... origin/pr-71-v1.8-phase4-...
60a9818947cc8ae56570359d21fb81baf8a9e048
```

**Both PRs branched from the same commit `60a9818`** ("test: add asymmetric-range
sanity regression gate (#11)"). That commit is *behind* the v1.8 phases that
have already merged into main:

```
$ git log --oneline 60a9818..origin/main -- crates/cfr_core/src/simd.rs
8073bcc PR 63b: v1.8 Phase 2 — update_regret_sum SIMD (#41)
db8d646 PR 68: v1.8 — AVX2 runtime-detect path for x86_64 hosts (#35)
485aa8c PR 61: v1.8 Phase 1 — cross-platform SIMD discount kernel (#23)
```

**Critical observation:** Phase 3 and Phase 4 are NOT stacked on each other in
git — they are **parallel siblings** off the same pre-Phase-1 base.
Phase 4 is *logically* stacked on Phase 3 (per the v1.8 roadmap), but in
the branch graph each one independently re-invents `mod sse2 { ... }` and
`mod avx2 { ... }` for the file. Both were authored against a simd.rs that
contained only `mod neon`; both will have to fold their new kernels INTO
the now-existing `mod sse2` / `mod avx2` blocks during rebase.

### File overlap

| File | Phase 3 touches | Phase 4 touches | Overlap |
|------|-----------------|-----------------|---------|
| `crates/cfr_core/src/dcfr_vector.rs` | hunk `@@ -451,15 +451,25 @@` (inside `update_strategy_sum` block — line 451) | hunk `@@ -204,30 +204,21 @@` (inside `compute_strategy` — line 204) | **NONE.** Different functions, ~250 lines apart. |
| `crates/cfr_core/src/simd.rs` | adds `mod sse2 { update_strategy_sum_sse2 }`, `mod avx2 { update_strategy_sum_avx2 }`, expands `mod neon`, edits `pub fn update_strategy_sum` dispatch | adds `mod sse2 { compute_strategy_row_sse2 }`, `mod avx2 { compute_strategy_row_avx2 }`, expands `mod neon`, adds `pub fn compute_strategy_row` dispatch (new function) | **STRUCTURAL.** Both add fresh `mod sse2` / `mod avx2` blocks against a base where they didn't exist. Function NAMES are disjoint (`update_strategy_sum_*` vs `compute_strategy_row_*`). |
| `crates/cfr_core/tests/test_simd_phase{3,4}.rs` | adds `test_simd_phase3.rs` | adds `test_simd_phase4.rs` | **NONE.** Distinct filenames. |

### Function-name disjointness (Phase 3 vs Phase 4 contribution)

| Symbol | Belongs to | File location |
| ------ | ---------- | ------------- |
| `update_strategy_sum_scalar` | pre-existing (PR 8) | `simd.rs` top of file |
| `update_strategy_sum_neon` | pre-existing (PR 8) | `mod neon` |
| `update_strategy_sum_sse2` | **Phase 3** | `mod sse2` (Phase 3 adds it) |
| `update_strategy_sum_avx2` | **Phase 3** | `mod avx2` (Phase 3 adds it) |
| `pub fn update_strategy_sum` (dispatch) | pre-existing (PR 8); **Phase 3** extends it with AVX2/SSE2 branches | `simd.rs` dispatch section |
| `compute_strategy_row_scalar` | **Phase 4** | `simd.rs` top section (new helper) |
| `compute_strategy_row_neon` | **Phase 4** | `mod neon` |
| `compute_strategy_row_sse2` | **Phase 4** | `mod sse2` |
| `compute_strategy_row_avx2` | **Phase 4** | `mod avx2` |
| `pub fn compute_strategy_row` (dispatch) | **Phase 4** | `simd.rs` dispatch section (brand-new entrypoint) |

The kernels are completely independent — no name collision, no semantic
dependency between Phase 3's `update_strategy_sum_simd` work and Phase 4's
`compute_strategy_row` work.

---

## 4. Predicted conflict scope once Phase 3 lands on `main`

### Will resolve themselves (no conflict expected)

1. **`crates/cfr_core/src/dcfr_vector.rs`** — Phase 4's hunk at line 204
   (`compute_strategy`) does not overlap Phase 3's hunk at line 451
   (`update_strategy_sum`). When Phase 3 lands, line 451 changes; line 204 is
   untouched. Phase 4's rebase context (line 204 ± 15 lines) is stable.
   → No merge conflict expected on this file.

2. **`crates/cfr_core/tests/test_simd_phase4.rs`** — new file; Phase 3's
   landing only adds `test_simd_phase3.rs` (different name). No overlap.

### Will still conflict after Phase 3 lands

3. **`crates/cfr_core/src/simd.rs`** — the structural conflict persists.

   Once Phase 3 lands, `simd.rs` on main will contain:
   - `mod sse2 { ... update_strategy_sum_sse2 ... }` (extended by Phase 3)
   - `mod avx2 { ... update_strategy_sum_avx2 ... }` (extended by Phase 3)
   - extended `pub fn update_strategy_sum` dispatch (Phase 3)

   Phase 4's commit tries to re-add a *fresh* `mod sse2 { ... }` block with
   `compute_strategy_row_sse2` and a fresh `mod avx2 { ... }` block with
   `compute_strategy_row_avx2`. Git's textual merge will see two `mod sse2 {`
   openings on adjacent lines and flag them as a conflict — resolution will
   require **manually folding** Phase 4's new SSE2 / AVX2 functions INTO the
   existing module bodies (delete Phase 4's extra `mod sse2 {` / `mod avx2 {`
   wrappers; insert just the `pub unsafe fn compute_strategy_row_{sse2,avx2}`
   bodies inside main's pre-existing modules).

   Additionally, Phase 4 expands `mod neon` to add `compute_strategy_row_neon`.
   Phase 3 also expands `mod neon` (adds `update_strategy_sum_neon` SIMD
   variant). These expansions are at slightly different line ranges within
   `mod neon` (Phase 3's at line 161-407, Phase 4's at line 162-510 of the
   Phase 4 branch's view) — git may or may not auto-merge depending on
   adjacent-line context. **Expected: 1-3 additional `mod neon` hunks to
   resolve manually.**

   Phase 4's `pub fn compute_strategy_row` (the new public dispatch
   entrypoint) is a fresh function — no naming conflict with Phase 3's
   modified `pub fn update_strategy_sum`. But both edits land in the same
   "public dispatch section" of simd.rs; git may report adjacent-hunk
   conflicts here too.

### Conflict scope summary

| Region | Pre-Phase-3-landing | Post-Phase-3-landing |
|--------|---------------------|----------------------|
| `dcfr_vector.rs` line 204 (compute_strategy) | clean | clean (no overlap with Phase 3) |
| `dcfr_vector.rs` line 451 (update_strategy_sum) | conflict (Phase 4 doesn't touch but Phase 3 does, and main differs) | **resolves itself** once Phase 3 lands |
| `simd.rs` `mod sse2` block | conflict (Phase 4 adds; main already has) | conflict persists (Phase 4 still adds; main now has *more*) |
| `simd.rs` `mod avx2` block | conflict (Phase 4 adds; main already has) | conflict persists |
| `simd.rs` `mod neon` block | conflict (Phase 4 expands; Phase 1/2 also did) | possibly clean if hunks are non-adjacent; else 1-3 small conflicts |
| `simd.rs` public dispatch | conflict (adjacent to `update_strategy_sum` dispatch which Phase 3 also edits) | conflict persists but smaller (Phase 3's dispatch edits are now in main; only Phase 4's new `compute_strategy_row` dispatch needs to be inserted) |
| `tests/test_simd_phase4.rs` | clean | clean |

**Net:** rebasing Phase 4 AFTER Phase 3 lands eliminates approximately 50-60%
of the work-graph conflict surface (the `update_strategy_sum` dispatch edits
self-resolve), but the `mod sse2` / `mod avx2` structural conflict in
`simd.rs` remains either way. The path is: Phase 3 lands → Phase 4 rebases
onto the new main → resolves the `simd.rs` module-redeclaration conflict by
folding Phase 4's new functions into main's existing `mod sse2` / `mod avx2`
bodies.

---

## 5. Roadmap-intended ordering

Per `docs/v1_8_neon_implementation_roadmap.md` and `docs/v1_8_decision_brief.md`:

- **Phase 1** (`discount`) → MERGED `485aa8c` ✓
- **Phase 2** (`update_regret_sum`) → MERGED `8073bcc` ✓
- **Phase 3** (`update_strategy_sum`) → in flight as PR #33
- **Phase 4** (`compute_strategy`) → in flight as PR #32 (this PR)

The roadmap (page 4, lines 103-139) treats Phase 3 and Phase 4 as
**sequential**: Phase 3 is "LOW complexity, same dispatch pattern" first,
then Phase 4 is "LOW-MEDIUM, same dispatch pattern as Phase 3" — i.e. Phase 4
is supposed to follow Phase 3's already-landed pattern, not be developed
concurrently against the same pre-Phase-1 base.

The branch graph (both branches off `60a9818`) was created in concurrent
development. That's not wrong — the *content* of Phase 4 doesn't depend on
Phase 3's content (see §6 below) — but it does mean the `simd.rs`
structural merge work is duplicated across the two PRs.

---

## 6. Risk flag: Phase 4 dependency on Phase 3 APIs?

**Answer: NO functional dependency.**

Verified by inspecting `origin/pr-71-v1.8-phase4-compute-strategy-simd`:

- `crates/cfr_core/src/dcfr_vector.rs` — Phase 4 calls only
  `crate::simd::compute_strategy_row` (its own new function). No call to
  `update_strategy_sum`, `update_strategy_sum_simd`, or any other Phase 3
  symbol.

- `crates/cfr_core/src/simd.rs` (Phase 4 branch) — `pub fn update_strategy_sum`
  still routes only through NEON / scalar (the pre-Phase-3 shape from the
  `60a9818` base):
  ```
  776:pub fn update_strategy_sum(strategy_sum: &mut [f64], strategy: &[f64], own_reach: f64) {
  ...
  780:        neon::update_strategy_sum_neon(strategy_sum, strategy, own_reach)
  ...
  783:    update_strategy_sum_scalar(strategy_sum, strategy, own_reach)
  ```
  Phase 4 does NOT call or extend `update_strategy_sum_sse2` / `_avx2`. They
  don't exist in Phase 4's worldview.

- Tests — `tests/test_simd_phase4.rs` imports only `cfr_core::simd` (the
  module path); it calls `simd::compute_strategy_row` and
  `simd::compute_strategy_row_scalar` exclusively. No Phase 3 symbol
  referenced.

**Conclusion: Phase 4 is functionally independent of Phase 3.** The "stacked"
relationship in the v1.8 plan is sequencing/ordering only, not API.
Rebasing Phase 4 on top of a Phase-3-merged main will not introduce any
"undefined symbol" or "wrong signature" errors — only the module-redeclaration
textual conflict in `simd.rs`.

### Secondary risk flags

- **`mod neon` expansion overlap (LOW).** Phase 3 adds `update_strategy_sum_neon`
  improvements inside `mod neon`. Phase 4 adds `compute_strategy_row_neon`
  inside the same module. After Phase 3 lands, Phase 4's NEON additions need
  to insert as new functions in the now-extended `mod neon` block. Likely
  auto-mergeable (different functions, different anchors), but verify
  manually.

- **Public dispatch comment drift (NOISE).** Phase 4 modifies a header
  comment ("Public dispatch: prefer NEON…") to mention `compute_strategy_row`
  alongside the other dispatches. Phase 3 may also touch this comment.
  Resolve by hand to mention BOTH new dispatches.

- **No call-graph risk.** No code in Phase 4 *uses* `update_strategy_sum` or
  any Phase 3 SIMD entrypoint, so the order in which Phase 3 lands does not
  affect Phase 4's compile or runtime behavior beyond the textual rebase.

---

## 7. Recommended rebase sequence

### Step 0 — wait

Do NOT rebase Phase 4 until Phase 3 has merged to `origin/main`. Rebasing
Phase 4 against the current main (pre-Phase-3) will require resolving the
`mod sse2` / `mod avx2` redeclaration conflict TWICE — once now against
current main, then again when Phase 3 lands because Phase 3 will have
extended those same modules.

### Step 1 — confirm Phase 3 is in main

```
git fetch origin
git log --oneline origin/main | head -5
# verify the Phase 3 merge commit is present, e.g.:
#   <sha> Merge pull request #33 ... v1.8 Phase 3 ...
```

### Step 2 — create an isolated worktree for the rebase

Per [feedback_no_concurrent_branch_ops](feedback_no_concurrent_branch_ops.md):
never rebase the active checkout; use a worktree.

```
cd /Users/ashen/Desktop/poker_solver
git worktree add /tmp/v1.8-phase4-rebase origin/pr-71-v1.8-phase4-compute-strategy-simd
cd /tmp/v1.8-phase4-rebase
git checkout -b pr-71-v1.8-phase4-compute-strategy-simd
```

(The branch name on the worktree should match the public branch name so the
final push targets the right ref.)

### Step 3 — perform the rebase

```
git fetch origin
git rebase origin/main
```

Expected conflict: `crates/cfr_core/src/simd.rs` only.

### Step 4 — resolve the simd.rs conflict

Open `crates/cfr_core/src/simd.rs` and apply this resolution pattern:

1. **Inside the existing (main's) `mod sse2 { ... }` block** — after
   `update_strategy_sum_sse2` (added by Phase 3) and before the closing `}`,
   insert Phase 4's `compute_strategy_row_sse2` function body. Do NOT keep
   Phase 4's duplicate `#[cfg(target_arch = "x86_64")] mod sse2 {` header
   line — main already has one.

2. **Inside the existing `mod avx2 { ... }` block** — same pattern: insert
   `compute_strategy_row_avx2` after the existing functions, drop the
   duplicate `mod avx2 {` header.

3. **Inside `mod neon { ... }`** — insert `compute_strategy_row_neon` after
   the existing NEON functions. If git auto-merged this, verify the function
   is present and that no duplicate was created.

4. **At the top of `simd.rs` (after `normalize_scalar`)** — add Phase 4's
   `compute_strategy_row_scalar` (this region of the file was untouched by
   Phase 3, so the addition should be straightforward).

5. **In the public dispatch section** (after `pub fn update_strategy_sum`) —
   add Phase 4's `pub fn compute_strategy_row` dispatcher. Verify the
   comment block above the dispatch section mentions both
   `update_strategy_sum` and `compute_strategy_row` callers.

### Step 5 — verify

```
cargo check -p cfr_core
cargo test -p cfr_core --test test_simd_phase4
cargo test -p cfr_core --test test_simd_phase3
cargo test -p cfr_core --lib simd::tests
git rebase --continue
```

The `test_simd_phase3` test should still pass (it tests Phase 3's kernels,
which are in main now). The `test_simd_phase4` test verifies Phase 4's
kernels are working post-rebase.

### Step 6 — preview the new diff against main (sanity check)

```
git log --oneline origin/main..HEAD
# Expect a single commit, same SHA family as before
git diff origin/main..HEAD --stat
# Expect:
#   crates/cfr_core/src/dcfr_vector.rs        |  ~25 +-
#   crates/cfr_core/src/simd.rs               | ~350 +
#   crates/cfr_core/tests/test_simd_phase4.rs | 189 ++
```

If the diff against main is materially larger than the original Phase 4
delta (~555 insertions, ~21 deletions), inspect — it may indicate Phase 3
code was accidentally re-introduced in the conflict resolution.

### Step 7 — push (after user review)

Per `feedback_pr_autonomous_commit` and `feedback_public_repo_hygiene`,
user reviews + approves before any push. The user explicitly requested
this is a read-only diagnostic; no push happens from this report.

When the user authorizes:
```
git push origin pr-71-v1.8-phase4-compute-strategy-simd --force-with-lease
```

`--force-with-lease` is the appropriate flag — rebased branch needs to
overwrite the remote pointer, but the lease guard ensures the push is
rejected if someone else updated the branch in between (defense against
concurrent rebase agents).

### Step 8 — clean up the worktree

```
cd /Users/ashen/Desktop/poker_solver
git worktree remove /tmp/v1.8-phase4-rebase
```

---

## 8. Summary

| Item | Value |
|------|-------|
| PR #32 commits ahead of main | 1 (`0734c0d`) |
| Files touched | 3 (`dcfr_vector.rs`, `simd.rs`, `tests/test_simd_phase4.rs`) |
| Shared merge base with Phase 3 | `60a9818` (pre-Phase-1) |
| Phase 4 → Phase 3 API dependency | NONE (functionally independent) |
| dcfr_vector.rs overlap with Phase 3 | NONE (different functions, 250 lines apart) |
| simd.rs overlap with Phase 3 | STRUCTURAL — both PRs add fresh `mod sse2` / `mod avx2` blocks against a pre-Phase-1 base |
| Predicted post-Phase-3 conflicts | `simd.rs` only (module redeclaration + adjacent-hunk in `mod neon` and dispatch section) |
| Recommended action | WAIT for Phase 3 to merge → rebase Phase 4 → resolve `simd.rs` by folding Phase 4's functions INTO main's existing `mod sse2`/`mod avx2` bodies → user review → `git push --force-with-lease` |
| Risk level | LOW. Pure textual conflict, no semantic dependency. ~30-60 min focused rebase work assuming Phase 3 has landed. |

---

## 9. Open questions for the user

1. **Phase 3 status check.** Is Phase 3's rebase agent expected to complete
   in this session, or is it a multi-session effort? Recommend deferring
   Phase 4 rebase to the session AFTER Phase 3 merges, to avoid two
   concurrent rebases racing the same `simd.rs` modules.

2. **Squash vs preserve commit?** Phase 4 is currently a single commit
   (`0734c0d`). A `git rebase origin/main` will rewrite its SHA but preserve
   it as one commit. Confirm this is the desired shape (alternative: opening
   an editor and squashing into the rebase target — not recommended for a
   simple single-commit rebase).

3. **Force-push policy.** Per `feedback_pr_branch_hygiene`, public-origin
   branches must be clean — `--force-with-lease` is the right primitive,
   but flagging here because force-push is on the "user-must-approve" list
   in [feedback_pr_autonomous_commit](feedback_pr10a5_autonomous_commit.md).
