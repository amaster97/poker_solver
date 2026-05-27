# v1.8.0 Release Notes Final Polish — 2026-05-26

**Branch:** `pr-103-release-notes-final`
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-103-release-notes-final`
**Base:** `origin/main` @ `eb74fb3` (PR #60).
**Target file:** `docs/v1_8_0_release_notes_DRAFT.md`
**Diff stat:** +137 / -27 (net +110 lines)

---

## Scope (per task brief)

Polish — not rewrite — of `docs/v1_8_0_release_notes_DRAFT.md` to fold
in everything that landed since PR #50 (initial fold-in) and PR #56
(SIMD ~1.0× honesty). Items in brief:

1. Shim quirk in Known Issues (was missing from draft).
2. Persona counts → 9 PASS / 5 PARTIAL / 2 BLOCKED / 1 FAIL.
3. A83 / v1.6.1 framing aligned with arbitrator (NOT-A-BUG) +
   hold-lifted decision.
4. Cleanup wave (user-impactful subset, not full list).
5. TBD placeholders filled where appropriate.
6. Version-number sanity (no v1.7.1/v1.7.2 stragglers as final tag).

No structural re-frame; the "two MAJOR findings" (cross-platform SIMD +
`.dmg` fork-bomb) framing is preserved.

---

## Before/after change summary

### A. Header block (lines 11-13 → 11-16)

**Before:**

```
**Release date:** 2026-05-XX (TBD at ship time)
**Tag:** `v1.8.0` (TBD)
**Commit SHA:** TBD at tag time (post-PR-32 baseline is `77e751c`).
```

**After:**

```
**Release date:** 2026-05-XX (TBD at ship time)
**Tag:** `v1.8.0` (to be created at ship time)
**Baseline commit on `origin/main`:** `eb74fb3` (PR #60, 2026-05-26).
Final tag SHA will be set at `git tag` time; the polish PRs landing
after this draft are documentation-only and do not change the SIMD /
`.dmg` ship surface.
```

Why: Release date legitimately remains TBD until tag time. Baseline
commit on `main` updated from stale PR-32 reference (`77e751c`) to
the current HEAD (`eb74fb3`).

### B. §1 SIMD "Why this matters" paragraph (was claiming Sarah W2.3 unblock)

**Before:** "Sarah persona W2.3 (turn Nash under a 5-min budget) is now unblocked on M-series."

**After:** "Sarah persona W2.3 remains pending the post-v1.8 retest (turn-fixture, agent in flight 2026-05-26); the original 'unblocked on M-series' projection was tied to a 4-8× SIMD speedup that did not materialize on M4 Pro arm64 (see 'Persona test status' below)."

Why: PR #56 corrected the SIMD measurement to ~1.0×. The "unblocked"
claim was incompatible with that correction and the W2.3 retest is
still in flight (`a99ec2e`).

### C. NEW §7 — Documentation + ship-process cleanup wave

User-impactful subset of cleanup PRs: PR #46 (mypy), #47 (dmg arch
label), #48 (USAGE refresh), #54 release script, #58 shim CHANGELOG,
#59 persona refresh, #60 orphan-refs. Explicitly not exhaustive
(per task constraint: "Don't list ALL — pick the user-impactful
subset"). Lint/clippy/deps green-up (#43) and doc-code-fix bundle
(#44/#45) are already called out in §3 and §4 above.

### D. NEW §8 — Persona test status (post-v1.8 SIMD + W3.2 + W3.4 retests)

New section with the 9 PASS / 5 PARTIAL / 2 BLOCKED / 1 FAIL table
plus per-workflow narrative for the changed entries:

- W3.2: BLOCKED → PASS (PR 76 shipped `solve_best_response()`).
- W3.4: BLOCKED → PASS caveated (fixture-repurposing, NOT v1.8 SIMD).
- W3.5: FAIL → PARTIAL (Type B-DOC; v1.8 SIMD bit-identical to v1.7.0).
- W2.3: PENDING (retest in flight, agent `a99ec2e`).

Explicit "fixture-repurposing, not v1.8 SIMD perf gain" caveat on W3.4
per task constraint #2 ("Add a note: 'W3.4 unblock was via fixture-
repurposing, not v1.8 SIMD perf gain.'").

### E. "Known issues remaining" — A83 entry expanded with arbitrator framing

**Before (lead-in):** "Root cause is established as a combination of two
documented designs, neither of which is a DCFR-algorithm bug..."

**After (lead-in):** "Deep-cap A83 ≥33-pp bottom-pair-Ace divergence vs
Brown reference solver — NOT-A-BUG (arbitrator-confirmed). ... **The
terminal-utility arbitration (2026-05-26) rendered a NOT-A-BUG
verdict** for the divergence: when `initial_contributions` is set to
`(base_pot/2, base_pot/2)` (the seed-split applied by every production
codepath), the per-terminal delta vs Brown is a uniform constant that
cancels exactly at the regret-difference step, so the Nash equilibrium
is unchanged."

Added citations to:
- `docs/terminal_utility_arbitration_2026-05-26.md` (NOT-A-BUG verdict)
- `docs/v1_6_1_ship_hold_review_2026-05-26.md` (HOLD-LIFTED decision)

Existing citations preserved (a83_validation, deep_cap_root_cause,
matched_config, feedback_nash_multiplicity_acceptance).

### F. "Known issues remaining" — NEW `poker-solver` PATH shim quirk entry

Added a new bullet for the shim quirk with both workarounds verbatim:
- `./.venv/bin/poker-solver ...` from project root.
- `python -m poker_solver.cli ...` with `.venv` activated.

Cross-references `docs/poker_solver_shim_fix_2026-05-26.md` (full
diagnostic) + PR #58 (CHANGELOG note). Explicit "pre-existing
dev-environment quirk surfaced by W3.2 smoke — NOT a v1.8 regression"
framing per the shim fix doc's recommended language.

### G. "What's next" v1.9 EMD bucketing entry

**Before:** "v1.8 unblocks turn workflows; flop is the next persona-budget gate."

**After:** "Since v1.8 SIMD measured ~1.0× on M4 Pro arm64 (root cause: LLVM `-O3` already autovectorizes the small-slice case), EMD bucketing is now the more likely lever for unblocking the perf-bound turn / flop persona workflows (W2.3 / W3.4 flop / W2.1 / W2.4); the W2.3 retest in flight will set the final wall-clock baseline."

Why: same SIMD honesty correction as item B — the prior "v1.8 unblocks
turn workflows" claim is inconsistent with the bench refutation.

### H. Footnote link references — 7 new entries added

- `[pr46]` → 46
- `[pr47]` → 47
- `[pr48]` → 48
- `[pr54-script]` → 54 *(suffix to avoid collision with the existing v1.7.2-era `[pr54]`)*
- `[pr58]` → 58
- `[pr59-persona]` → 59 *(suffix to avoid future collision)*
- `[pr60-orphan]` → 60 *(suffix to avoid future collision)*

---

## What was NOT changed (constraint-bounded)

- The "two MAJOR findings" framing (cross-platform SIMD + `.dmg`
  fork-bomb) is preserved verbatim.
- No new findings introduced; every claim traces to a document that
  already landed on `main`.
- The Brown apples-to-apples 4-layer reframed gate language is
  preserved (PRs 53b/53c).
- The `Range` fractional-frequency known-issue is preserved.
- The notarization carry-item known-issue is preserved.
- No edits to `CHANGELOG.md` (shim entry is already there via PR #58).
- No edits to `PLAN.md` (per `feedback_orchestrator_only` — PLAN.md
  changes are user-review only).

---

## Verification of "no v1.7.1 / v1.7.2 stragglers"

Remaining `v1.7.1` / `v1.7.2` references after polish: all are
**intentional retrospective references** to the pre-fold tag stream
(now consolidated into v1.8.0). They appear in:

- Header status block: "fixes from the v1.7.1 bundle and v1.7.2
  (.dmg fork-bomb fix + CI hardening) are folded into v1.8.0" — context.
- §5 title: "Engine + parity-wrapper fixes carried from the v1.7.1
  bundle" — context.
- §6 title: "v1.7.2 entries folded into v1.8.0" — context.
- CHANGELOG alignment Option A reference — context.
- Full PR list: PR #21 v1.7.2 CI release workflow — context.

All correct as historical context; none claim the release ships as
v1.7.x.

---

## PR sequence (per task workflow §1.4)

1. Worktree created at `/Users/ashen/Desktop/poker_solver_worktrees/pr-103-release-notes-final` on branch `pr-103-release-notes-final` from `origin/main` (`eb74fb3`).
2. Surgical edits applied via Edit tool (no full rewrites).
3. Commit + push.
4. PR opened titled "docs: v1.8.0 release notes final polish (persona + arbitrator + cleanup wave)".
5. Auto-merge if CI green per Stage-3 (audit-clear docs-only).

---

## Files referenced

- Target: `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md`
- Persona snapshot: `/Users/ashen/Desktop/poker_solver/docs/persona_test_status_2026-05-26.md`
- Persona ship report (PR #59): `/Users/ashen/Desktop/poker_solver/docs/persona_status_update_2026-05-26.md`
- Arbitrator verdict: `/Users/ashen/Desktop/poker_solver/docs/terminal_utility_arbitration_2026-05-26.md`
- v1.6.1 hold-lift decision: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_ship_hold_review_2026-05-26.md`
- Shim diagnostic: `/Users/ashen/Desktop/poker_solver/docs/poker_solver_shim_fix_2026-05-26.md`
- SIMD bench (load-bearing for ~1.0×): `/Users/ashen/Desktop/poker_solver/docs/v1_8_simd_perf_benchmark_2026-05-26.md`
- W3.2 smoke: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_2_smoke_2026-05-26.md`
- W3.4 retest: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_4_retest_2026-05-26.md`
- W3.5 retest: `/Users/ashen/Desktop/poker_solver/docs/persona_w3_5_retest_2026-05-26.md`
