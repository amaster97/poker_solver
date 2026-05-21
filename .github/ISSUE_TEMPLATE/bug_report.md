---
name: Bug report
about: A reproducible defect in the solver, evaluator, equity calculator, or CLI.
title: ""
labels: bug
assignees: ""
---

## Summary

One sentence describing what is wrong.

## Reproduction

Minimal steps or code that reproduces the issue. A failing test is
ideal; a CLI command line is also fine.

```python
# or shell, e.g.
# poker-solver equity AhKh QdQc --board 2h7h9d
```

## Expected behavior

What you expected to happen, and why (closed-form value, a paper, a
prior version, another solver, etc.).

## Actual behavior

What actually happened. Include stack traces, numeric output, or the
relevant log line.

## Environment

- OS + version (e.g. macOS 14.5 / Ubuntu 22.04):
- Python version (`python --version`):
- `poker_solver` version (`pip show poker_solver | grep Version` or commit hash):
- Rust toolchain version (`rustc --version`), if relevant:

## Additional context

Anything else: was this working on a prior version? Have you tried
flipping `--backend python` vs `--backend rust`? Does
`sh scripts/check_pr.sh` pass on your clone?
