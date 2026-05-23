## Linked issue

Fixes #... (or "n/a — small drive-by fix" / "n/a — roadmap PR").

## Summary

What this PR changes, in 1-3 sentences. Focus on the *why*; the diff
shows the *what*.

## Test plan

What was verified, concretely:

- [ ] `pytest` clean locally
- [ ] `cargo test --all --manifest-path crates/cfr_core/Cargo.toml` clean
- [ ] `sh scripts/check_pr.sh` clean (`pr_report.md` attached / linked)
- [ ] New tests added for new behavior (list them)
- [ ] Differential test (`tests/test_dcfr_diff.py` /
  `tests/test_leduc_diff.py`) updated if both tiers were touched
- [ ] Closed-form / oracle check still passes (Kuhn `-1/18`,
  Leduc `~-0.085`, etc.), if relevant

## Audit checklist (PR 3 onward)

- [ ] Branch name follows `pr-N-<short-title>` convention
- [ ] `pr_report.md` is clean and attached
- [ ] `audit_report.md` from an independent agent is attached, with
  zero must-fix items remaining
- [ ] No copying from AGPL repos (`postflop-solver`, `TexasSolver`,
  `shark-2.0`); any MIT / Apache 2.0 porting carries attribution

## Cross-cutting changes

- [ ] If the change affects a locked design decision (algorithm,
  abstraction, stack range, license posture), call it out in the PR
  body
- [ ] `CHANGELOG.md` entry added under `[Unreleased]` (or appropriate
  version section if cutting a release)
- [ ] `README.md` updated if a public-facing feature, command, or
  installation step changed

## Notes for the reviewer

Anything the reviewer should look at first, known limitations, or
follow-ups deferred to a later PR.
