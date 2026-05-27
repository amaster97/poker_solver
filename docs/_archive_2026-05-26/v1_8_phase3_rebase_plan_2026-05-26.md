# v1.8 Phase 3 (PR #33) Rebase Plan — 2026-05-26

## Worktree / branch

- **Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-33-phase3-rebase`
- **New branch (local only):** `pr-33-phase3-rebase-2026-05-26`
- **Rebased onto:** `origin/main` (currently `8073bcc` — PR 63b Phase 2 SIMD update_regret_sum)
- **Rebased HEAD:** `4eba77d` (single new commit, same author / message as the original `6490016`)
- **Remote branch this is meant to replace:** `origin/pr-70-v1.8-phase3-update-strategy-sum-simd`

## Pre-rebase state

- Original commit on remote: `6490016 feat(cfr_core): v1.8 Phase 3 — update_strategy_sum SIMD`
- Merge-base with main: `60a9818` (pre-Phase 2)
- Phase 3 was branched off pre-Phase-2 main, so it conflicted with the SSE2/AVX2 module bodies, x86_64 section headers, and the in-source test block that PR 63b (Phase 2) added.

## Conflicts encountered

Only **one file** had conflicts: `crates/cfr_core/src/simd.rs` (10 hunks).
`dcfr_vector.rs` (16 lines) and the new `tests/test_simd_phase3.rs` auto-merged cleanly.

| # | Range (post-merge) | Kind | Description |
|---|--------------------|------|-------------|
| 1 | top-of-file `//!` docstring | doc text | HEAD describes Phase 1 + Phase 2 (AVX2); incoming had stale wording mentioning PR 68 layering on top of SSE2 but missing the Phase 2 framing. |
| 2 | `// x86_64 SSE2 kernels` section header | doc text | Same pattern — HEAD has the current Phase 1+2 framing; incoming had stale wording. |
| 3 | inside `mod sse2 { ... }` body | structural / additive | HEAD had three functions (`discount_regrets_sse2`, `discount_strategy_sum_sse2`, `update_regret_sum_vector_sse2`). Incoming wanted to **replace** them with just `update_strategy_sum_sse2`. The intended net result is **all four** functions coexisting. |
| 4 | `// x86_64 AVX2 kernels` section header | doc text | Same pattern as #2. |
| 5–6 | inside `mod avx2 { ... }` body (two adjacent conflict blocks, split by the shared `#[target_feature(enable = "avx2")] #[inline]` attribute lines) | structural / additive | HEAD had `discount_regrets_avx2` + `discount_strategy_sum_avx2`. Incoming wanted to replace them with `update_strategy_sum_avx2`. Resolution: keep both HEAD functions and append the new one. |
| 7 | `// Public dispatch: ...` comment above the `pub fn discount_regrets` block | doc text | HEAD's wording is the most accurate ("AVX2 (runtime) > SSE2"); incoming was stale. |
| 8–9 | inside `mod tests { ... }` — two adjacent conflict blocks for SSE2- and AVX2-specific x86_64 parity tests | structural / additive | HEAD has tests for `discount_*_sse2` and `discount_*_avx2`. Incoming wanted to replace them with `update_strategy_sum_sse2_matches_scalar` and `update_strategy_sum_avx2_matches_scalar`. Resolution: keep all HEAD tests and append the two new ones. |
| 10 | inside `mod tests { ... }` — block after the AVX2-vs-SSE2 cross-check | structural | HEAD has the AVX2-vs-SSE2 cross-check + the Phase 2 `update_regret_sum_vector_*` parity tests. Incoming branch was pre-Phase-2 so had nothing there. Resolution: keep all of HEAD's content. |

## Resolutions applied (all 10 hunks were mechanical)

Every conflict matched one of two clean patterns:

- **(Doc text)** Hunks 1, 2, 4, 7. Keep HEAD's framing (it accurately describes the live Phase 1 + Phase 2 state) and extend wording where appropriate to also mention PR 70 (Phase 3) extending the `update_strategy_sum` kernel. No semantic change.
- **(Additive: both branches added unrelated functions/tests at the same point)** Hunks 3, 5–6, 8–9, 10. Keep all of HEAD's items and append the new Phase 3 item(s). This is precisely the "kept both" case the user gave as the threshold for mechanical auto-resolution.

Per-file resolution:

- `crates/cfr_core/src/simd.rs`:
  - **mod sse2:** 4 functions (3 existing + 1 new `update_strategy_sum_sse2`), in order: `discount_regrets_sse2`, `discount_strategy_sum_sse2`, `update_regret_sum_vector_sse2`, `update_strategy_sum_sse2`.
  - **mod avx2:** 3 functions (2 existing + 1 new): `discount_regrets_avx2`, `discount_strategy_sum_avx2`, `update_strategy_sum_avx2`.
  - **mod tests:** all HEAD's tests intact + 2 new ones (`update_strategy_sum_sse2_matches_scalar`, `update_strategy_sum_avx2_matches_scalar`) interleaved in the natural SSE2-then-AVX2 ordering.
  - Module-level + section-header doc comments merged to credit all three phases.

- `crates/cfr_core/src/dcfr_vector.rs`: auto-merged. Inner `for a` loop in `update_strategy_sum`-equivalent block now routes through `crate::simd::update_strategy_sum(...)` instead of scalar.

- `crates/cfr_core/tests/test_simd_phase3.rs`: new file, auto-merged (164 lines, 6 tests).

## Conflicts NOT auto-resolved

**None.** Every conflict was mechanical per the user's brief. No items require user decision.

## Cargo verification (host: aarch64-apple-darwin)

| Command | Result |
|---------|--------|
| `cargo check --manifest-path crates/cfr_core/Cargo.toml` | Clean (`Finished dev profile target(s) in 7.47s`). |
| `cargo build --release --manifest-path crates/cfr_core/Cargo.toml` | Clean (`Finished release profile target(s) in 9.68s`). |
| `cargo test --release -p cfr_core --lib simd` | **9/9 pass** (incl. `update_strategy_sum_matches_scalar_bit_exact`, both PR 63 `update_regret_sum_vector_*` tests, both PR 63 in-source SSE2/AVX2 tests — though x86_64 tests are `#[cfg]`-skipped on aarch64). |
| `cargo test --release -p cfr_core --test test_simd_phase3` | **6/6 pass** (full HUNL width 3978 lanes, lengths 0–12, larger odd lengths 17/33/64/128/1024/1325–1327, spec example, zero-reach identity, 1e-12 tolerance vs scalar). |
| `cargo test --release -p cfr_core --test test_simd_dispatch` | **5/5 pass** (Phase 1+2 dispatcher tests). |
| `cargo test --release -p cfr_core --test test_simd_cross_platform_smoke` | **2/2 pass** (1 intentionally `ignored`). |

Diffstat vs `origin/main`: 3 files, 389 insertions / 25 deletions (was 412/9 pre-rebase; the shrinkage is because the post-Phase-2 main already contains the `update_strategy_sum` dispatch shell + module docstring framing the original commit had to introduce).

## What this does NOT verify

- x86_64 SSE2 / AVX2 paths are compile-checked but cannot be executed on the user's aarch64 host. CI's `cross-platform-ci-matrix` (PR 64) job is expected to exercise them on x86_64 runners after force-push.

## Next actions (commands surfaced, NOT executed)

### (a) Approve and force-push the rebase to overwrite the PR #33 branch

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-33-phase3-rebase
git push --force-with-lease origin pr-33-phase3-rebase-2026-05-26:pr-70-v1.8-phase3-update-strategy-sum-simd
```

`--force-with-lease` ensures the push aborts if `origin/pr-70-v1.8-phase3-update-strategy-sum-simd` advanced (no clobbering a concurrent push).

### (b) Abort and discard the rebase work

```bash
# We've already finalised the rebase (no in-flight rebase state remains),
# so `git rebase --abort` is a no-op here. The clean rollback is to drop
# the local branch + worktree:
cd /Users/ashen/Desktop/poker_solver
git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/pr-33-phase3-rebase
git branch -D pr-33-phase3-rebase-2026-05-26
```

## Downstream impact

Once PR #33 is force-pushed and re-merged:

- **PR #32 (Phase 4 `compute_strategy` SIMD)** is stacked on Phase 3 and is also `CONFLICTING`. Its rebase needs a separate worktree at `pr-71-v1.8-phase4-compute-strategy-simd` onto the new `main` (post-Phase-3-merge). The conflict surface there will likely mirror this PR's: SSE2/AVX2/tests modules gain another function each.

## Memory-rule cross-check

- **Per-PR branches** (`feedback_pr_branches`): satisfied — new branch `pr-33-phase3-rebase-2026-05-26`, no direct commits to main.
- **PR autonomous commit gate** (`feedback_pr10a5_autonomous_commit`): force-push is **explicitly excluded** from autonomous shipping; user approval required before running command (a).
- **No concurrent branch ops** (`feedback_no_concurrent_branch_ops`): used worktree, no stash-drop / pop sequences.
- **Public repo hygiene**: not yet pushed — review HOLD state until user approves.
