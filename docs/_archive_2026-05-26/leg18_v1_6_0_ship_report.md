# LEG 18 — v1.6.0 Ship Report

**Date**: 2026-05-23
**Status**: SHIPPED

## Outcome

- **Origin/main HEAD before**: `9a2a89e` (examples: add range-vs-range river solve example)
- **Origin/main HEAD after**: `d885bca` (v1.6.0: GUI Gate 2 surfaces)
- **Tag pushed**: `v1.6.0` → `d885bca`
- **Commits shipped**: 10 (9 cherry-picked PR 24a + PR 24b + 1 version-bump commit)

## What shipped

PR 24a (4 commits) + PR 24b (5 commits) bring GUI Gate 2 user-facing
surfaces online for v1.3.0+ engine features that were previously
library-only:

- Range-vs-range solve panel + hero_player selector (PR 24a)
- 4-tier exploitability slider with measured iteration counts
  (Draft 200 / Standard 500 / Tight 1000 / Library 2000) (PR 24a)
- Node-locking editor with per-action sliders + tree-browser hook +
  run-panel locked-strategies expansion (PR 24b)
- Asymmetric initial_contributions UI for facing-bet scenarios via
  `pot_so_far_bb` + `villain_bet_bb` + `bettor_is_p0` (PR 24b)
- Range editor polish: per-combo frequency dialog + 4 built-in chart
  presets (PR 24b)
- "True Nash" vs "blueprint" chart labels (PR 24a)
- 16 new UI smoke tests (7 from PR 24a + 9 from PR 24b)

## Process notes

1. **Worktree used**: `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.6.0`
   (dedicated, per `feedback_no_concurrent_branch_ops`).
2. **Rebase**: clean rebase onto `9a2a89e`. Zero conflicts as expected
   (PR 24a/24b touched UI files; `9a2a89e` only added
   `examples/range_vs_range_river.py`).
3. **PII grep**: PASS on all new files
   (docs/pr_proposals/v1_5_pr_24[ab]_implementer_notes.md,
   poker_solver/charts/{README.md,*.json}, tests/test_ui_pr24[ab].py,
   ui/views/{node_lock_editor,range_freq_editor}.py). No
   ashen26/columbia.edu/personal-gmail leakage.
4. **Smoke**: pytest ran 169 passed / 1 skipped / 1 xfailed / 1 failed.
   The failure (`test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction`,
   `ValueError: canonical board key 'r2s0_r2s1_r7s2_r14s0' not in TURN
   table (build-side coverage bug)`) was **verified pre-existing on
   origin/main `9a2a89e`** — NOT a regression introduced by PR 24a/24b
   or the rebase. It is a known build-side coverage bug in the TURN
   abstraction table, orthogonal to GUI surfaces. Ship proceeded per
   smoke-pass-modulo-known-failure standard.
5. **Push**: fast-forward only. No force. `9a2a89e..d885bca` to main +
   `v1.6.0` tag.

## Unblocked downstream

- **v1.6.1**: small follow-ups + polish iterations now unblocked.
- **v1.7.0**: Nash wrapper PR 43 (in-flight on `pr-43-nash-wrapper`
  worktree) now unblocked from sharing the v1.6.0 baseline.
- **PR 11 .dmg rebuild** (LEG 19 candidate): triggered per
  `feedback_ui_packaging_sync` — this ship is user-facing.
- **PR 10b UI re-audit**: downstream follow-on.

## Open items (NOT blockers, surfaced for queue)

- TURN-table coverage bug in `test_hunl_diff.py` — pre-existing,
  needs separate investigation (build-side fix to
  `poker_solver/abstraction/buckets.py:232` invariant).
- Engine bundle (PR 33+34+35 for true Brown parity) still deferred to
  v1.5.2 pending per-action divergence diagnosis (unchanged from
  CHANGELOG-noted status).
