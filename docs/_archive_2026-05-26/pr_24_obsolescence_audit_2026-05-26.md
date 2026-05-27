# PR #24 Obsolescence Audit — 2026-05-26

**Auditor:** PR #24 obsolescence audit agent (one-shot, ~20 min budget)
**Mode:** read-only classification + minimal salvage + close
**PR audited:** [#24 `docs: refresh public docs for v1.7.1/v1.7.2/v1.8`](https://github.com/amaster97/poker_solver/pull/24)
**PR branch:** `pr-69-docs-refresh-v1.7.1-v1.8`
**Outcome:** **PR #24 CLOSED as obsolete; minimal salvage merged via PR #48.**

---

## TL;DR

- PR #24 was a 151-line docs refresh that telegraphed v1.7.1 (placeholder), v1.7.2 (CI rigor), and v1.8.0 (cross-platform SIMD) before any of those ships landed. Hold condition was "merge once v1.7.1 ships."
- v1.7.1 was **decided CLOSE-as-obsolete** on 2026-05-26 per `docs/v1_7_1_tag_decision_2026-05-26.md` (bundle shipped piecewise on `main`; tag was never created; v1.7.2 / v1.8 work landed before the v1.7.1 ship script could complete). The hold condition is now dead.
- Most PR #24 scope was absorbed by other landings: PR #45 added the real `[1.7.2] - 2026-05-26` CHANGELOG entry (with .dmg fork-bomb fix, not the speculative CI-rigor framing); PR #34 (in flight) covers the v1.8.0 CHANGELOG + release notes more comprehensively.
- A single hunk was unique salvageable: the USAGE.md §7b header version refresh + a small regime guidance summary block. Salvaged in **PR #48** (merged 2026-05-26 06:25:18 UTC, squash commit `610986d1`).

---

## Hunk-by-hunk classification

PR #24 modifies 3 files: CHANGELOG.md (+59 / -4), README.md (+12 / -7), USAGE.md (+17 / -4).

| # | File | Hunk | Classification | Reason |
|---|---|---|---|---|
| 1 | CHANGELOG.md | `### In progress` adds `v1.7.1 placeholder` | **OBSOLETE** | v1.7.1 decided CLOSE-as-obsolete (no tag, no release, no version bump); per the decision doc, the v1.7.1 bundle is shipped piecewise and the next release boundary is v1.8.0. |
| 2 | CHANGELOG.md | New `## [1.7.2] - unreleased, planned` block (CI-driven release workflow, pre-flight ship-bundle dry-run, silent-skip ban) | **OBSOLETE** | Main has a REAL `## [1.7.2] - 2026-05-26` entry already (via PR #45, commit `dbfc8d0`) with completely different content — the .dmg fork-bomb fix (PR #42), not the CI hardening framing in PR #24. Adding the planned block would conflict with the shipped block. |
| 3 | CHANGELOG.md | New `## [1.8.0] - unreleased, planned` block (NEON + SSE/AVX + scalar fallback; 4-8x / 2-4x targets; Sarah's turn workflow unblock) | **ABSORBED** | PR #34 (`pr-74-v1.8-release-notes-prep`, in flight) owns the v1.8.0 CHANGELOG + release notes draft. PR #34's draft is substantially more detailed (per-phase PR mapping, runtime-detect AVX2 callout, ~3-month cross-platform gap closure framing, public API compatibility note). Re-adding PR #24's speculative block would create drift with PR #34. |
| 4 | CHANGELOG.md | Drive-by scrub: `docs/leg9_v1_4_0_ship_plan.md` internal-ref → "the stagger-fallback path" | **UNIQUE, NOT WORTH SALVAGING** | Main still has the `leg9_v1_4_0_ship_plan.md` reference (verified via `git show origin/main:CHANGELOG.md \| grep leg9`). The public-doc grep gate would in principle flag it; in practice the gate has not flagged main since merge of the v1.4.0 entry. Low-priority cleanup; defer to a future drift-cleanup wave (a la PR #45). Including it would require carrying CHANGELOG.md in the salvage PR and risk merge churn against PR #34. |
| 5 | README.md | Status block rewrite: v1.6.0 → v1.7.0/v1.7.1/v1.7.2/v1.8 + platform support matrix (current vs. post-v1.8) | **OBSOLETE** + **HAZARDOUS** | Main's README Status block (a) already reads v1.7.0 as latest, and (b) carries a critical user-facing warning about the v1.6.0 .dmg fork-bomb bug ("**v1.6.0 .dmg has a critical fork-bomb bug on Finder launch — DO NOT use until the v1.7.2+ packaging fix lands.**"). Applying PR #24's README hunk would **delete the safety warning** that PR #42 + PR #44 + PR #45 explicitly added to protect users. Hazardous; absolutely do not salvage. |
| 6 | USAGE.md | §7b header `v1.4.x` → `v1.4.x; v1.8 SIMD pending` + add river/turn/flop regime guidance block + v1.8 SIMD forecast paragraph | **UNIQUE — SALVAGED (with edit)** | Main's §7b header still reads `(v1.4.x)`. The river/turn/flop regime guidance bullets are genuinely useful and not present elsewhere in main's USAGE.md. **Salvaged via PR #48** with edits: (a) header bumped directly to `v1.7.x` (matching the rest of USAGE.md, which PR #45 already refreshed), (b) regime guidance bullets retained, (c) v1.8 SIMD forecast paragraph DROPPED (v1.8 is in flight; including a forecast now would create drift with PR #34's v1.8 release notes work; the USAGE.md v1.8 refresh should land alongside the v1.8 ship). |

---

## Salvage execution

- Created worktree `/Users/ashen/Desktop/poker_solver_worktrees/pr-87-salvage` from `origin/main` (commit `dbfc8d0`).
- Applied minimal §7b edit (11 insertions, 2 deletions on USAGE.md only).
- Committed as `987d029` on branch `pr-87-docs-refresh-salvage`.
- Pushed to origin; opened as PR #48 (GitHub auto-numbered; PR #87 was the intended slot but the gh service assigned #48).
- Enabled auto-merge via `gh pr merge 48 --auto --squash`; auto-merged at 06:25:18 UTC (squash SHA `610986d1`).
- CI status at merge time: `Golden File Check`, `Ship Dry Run`, and `Skip-Ban (Acceptance Tests)` were IN_PROGRESS (UNSTABLE rollup); repo merge rules did not block on those checks for a docs-only diff.

### PR #48 diff (final shipped content)

```diff
--- a/USAGE.md
+++ b/USAGE.md
@@ -703,14 +703,23 @@ ...
-## 7b. Known perf cliffs (v1.4.x)
+## 7b. Known perf cliffs (v1.7.x)

-The honest framing: the v1.4.x Python solver targets two regimes
+The honest framing: the v1.7.x Python solver targets two regimes
 well — short pushfold (§3a) and fixed-cards postflop subgames (§3b).
 ...

+Regime guidance at a glance:
+
+- **River spots:** fast (sub-second to seconds on the Rust tier);
+  good for interactive use today.
+- **Turn spots:** minutes per solve on the Nash path; aggregator
+  (§5.2) is recommended for interactive turn queries.
+- **Flop spots:** not interactive on the Nash path; use the
+  aggregator (§5.2) for production-scale flop range queries.
+
 - **`initial_hole_cards=()` on flop / turn / river is slow.** ...
```

---

## PR #24 closure

- Closed PR #24 at 2026-05-26 06:25:27 UTC with comment:
  > Closing as obsolete. v1.7.1 hold condition dead (per docs/v1_7_1_tag_decision_2026-05-26.md). Content absorbed by #42, #43, #44, #45. Salvage: PR #48 (USAGE.md §7b header refresh + regime guidance) — auto-closed under Stage-3
- Branch `pr-69-docs-refresh-v1.7.1-v1.8` was **NOT deleted** (per instruction "NO `--delete-branch`"). Retained on origin for git archaeology of the original 151-line proposal.

---

## Verification

| Item | Value |
|---|---|
| PR #24 state | **CLOSED** (2026-05-26 06:25:27 UTC) |
| PR #24 branch on origin | retained (`pr-69-docs-refresh-v1.7.1-v1.8`) |
| Salvage PR | **#48 MERGED** (2026-05-26 06:25:18 UTC, squash `610986d1`) |
| Salvage scope | USAGE.md §7b header refresh (v1.4.x → v1.7.x) + 3-bullet regime guidance block |
| Files affected by salvage | USAGE.md only |
| Hazard avoided | README.md hunk would have removed the v1.6.0 .dmg fork-bomb safety warning |
| Drift avoided | v1.8.0 CHANGELOG block deferred to PR #34 (in flight, more comprehensive) |
| Drift avoided | v1.8 SIMD §7b forecast deferred to land with the v1.8 ship's USAGE refresh |

---

## Action taken by this agent

- **Created branch `pr-87-docs-refresh-salvage` from `origin/main`.**
- **Pushed and opened PR #48 (intended as #87; GitHub assigned #48).**
- **Auto-merge enabled; PR #48 merged at squash commit `610986d1`.**
- **Closed PR #24 with obsolescence comment.**
- **Did NOT delete branch `pr-69-docs-refresh-v1.7.1-v1.8` on origin.**
- **Wrote this report.**
