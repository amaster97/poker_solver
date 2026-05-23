# CHANGELOG v0.6.1 entry — audit

**Date:** 2026-05-23
**Auditor:** orchestrator-spawned read-only verification agent
**Scope:** Verify CHANGELOG.md v0.6.1 entry (lines 186-202) against PR 10a.5
implementer / audit / backlog reports.

## Verdict

**ACCURATE** (one surgical fix applied — see "Edits" below).

## Claim-by-claim verification

| # | Claim | Source | Status |
|---|-------|--------|--------|
| 1 | "Resolves 5 fail + 7 xfail; 22/22 (was 8/22)" | pr_report §1 + audit §"Test status"; F1-F5 + X1-X7 confirmed | ACCURATE |
| 2 | "audit-found f-string fix in `spot_input.py` (push/fold toast `{bb}`)" | audit Should-fix #1; backlog opening line "PR 10a.5 (v0.6.1) landed the conformance fix for the pushfold f-string toast (item 1)" | ACCURATE |
| 3 | "Defers 2 should-fix items to v0.6.2: `bet_sizes_checked` prune + `state.compute_eta` dead-code" | backlog §"v0.6.2 scope" items 1 + 2 (= audit Should-fix #2 + #3) | ACCURATE |
| 4 | Files touched: 7 enumerated in prompt | pr_report §7 lists exactly those 7; CHANGELOG body doesn't enumerate (no false claim to flag) | ACCURATE |
| 5 | v0.6.0 (lines 204-218) mentions "PR 10a... NiceGUI browser UI scaffold backed by a mock solver layer" | direct read | ACCURATE |

## Additional verifications

- PATCH-bump justification ("zero behavior change in solver / spec; UI-only polish; same public API") matches audit §"Production-code touches are plumbing, not semantics" and pr_report §3.
- The seven UX surfaces enumerated (DISPLAY_PALETTE + cell colorization, blocker overlays, INPUT_PALETTE, expl-chart linear toggle, OOM bet-size reducer, push/fold switch stub, progress ETA + SolveRunner.compute_eta) map 1:1 to X1-X7 in the pr_report.
- The two NiceGUI 3.x bug patches (FixturePreset repr in UI; EChart.options read-only mutation) map to F4 + X4.

## Drift flagged

- **Format drift (fixed):** version-link footer was missing `[0.6.1]` entry between `[1.0.0]` and `[0.6.0]` (lines 783-784). Every other release has a footer link; v0.6.1 did not.

## Edits applied

- Added `[0.6.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.6.1`
  between the v1.0.0 and v0.6.0 footer links. Single-line surgical fix; no
  body-text changes.

## Not flagged / out of scope

- Pre-existing `[Unreleased]` block (line 13) still lists "PR 10b mock→real
  solver swap" as in-flight, while v1.0.0 (line 53) declares PR 10b "rolled
  into PR 11". This is a v1.0.0-entry inconsistency, not introduced by
  v0.6.1 and outside this audit's scope.
