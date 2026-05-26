# Task List Review — 2026-05-23 (late)

Generated during late-day cleanup wave. The task list has 200+ entries; many are stale. This doc flags items for the user's signon. **TaskUpdate was NOT called** — these are recommendations only.

## Tasks that should be marked completed (currently pending/in_progress)

| ID  | Title                                  | Current state | Recommended state | Reason                                                                 |
|-----|----------------------------------------|---------------|-------------------|------------------------------------------------------------------------|
| #179 | River parity test fix                 | in_progress   | completed         | River parity work landed in v1.4.2 / v1.5.x ladder; nothing outstanding |
| #223 | v1.6.1 ship NO-GO                     | pending       | needs new status  | Dry-run #2 confirmed NO-GO; Path D PROPOSED — not "pending" anymore   |
| #225 | CHANGELOG fix v1.5.2→v1.6.1           | pending       | completed         | Shipped in commit `94007ca`                                            |

## Tasks still genuinely pending

| ID  | Title                                       | Status                                                                                  |
|-----|---------------------------------------------|-----------------------------------------------------------------------------------------|
| #167 | Gate 4 200K-iter validation                | Never run; needs scheduling                                                              |
| #169 | All-18 final sweep retest                  | Partial via post-v1.7.0 retests; **W2.3 still pending**                                  |
| #170 | v-final .dmg                               | v1.6.0 .dmg is current LIVE; v1.7.0 .dmg not yet built                                  |
| #189 | Range fractional-frequency refactor        | v1.8+ scope; deferred                                                                    |

## New tasks the user should add

- v1.6.0 SHIPPED + .dmg LIVE
- v1.7.0 SHIPPED with corrected release notes
- v1.7.1 candidate: docs-only patch (USAGE.md class-label semantics)
- Path D PROPOSED on v1.6.1 (awaiting user OK)
- 5th-reversal lesson codified in memory

## Notes

- Per [Continuous pruning rule](../../.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_continuous_pruning.md), task list should be pruned after each release wave; this list has accumulated drift.
- Per [Label vs semantics rule](../../.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_label_vs_semantics.md), task titles must be verified against current semantics — several here show titles whose meaning has changed since they were filed.
