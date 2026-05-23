# Contributing to poker_solver

`poker_solver` is a Texas Hold'em equity calculator and GTO solver with a
Python reference tier and a Rust performance tier. It is a personal solo
build aiming at PioSolver-class HU local solving on a MacBook; surface
area is small and design choices are deliberately load-bearing.

Before opening anything non-trivial, please read:

- [`README.md`](README.md) — what ships today, install, quick start.
- [`CHANGELOG.md`](CHANGELOG.md) — what landed in each version.

The project has locked decisions on algorithm (DCFR), abstraction
(bucketed 256/128/64), stack range (2-250 BB), and license posture
(MIT); revisiting these requires empirical evidence, not preference.

## Development environment

A Rust toolchain is required because the project ships a PyO3 extension
module via `maturin`.

```bash
# One-time: install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build and install with dev tooling (pytest, ruff, black, mypy, maturin):
pip install -e ".[dev]"
```

Python 3.9+ (developed on 3.13). Primary platform is macOS / M-series;
Linux is supported but less exercised.

## Running tests

```bash
# Python:
pytest

# Rust:
cargo test --all --manifest-path crates/cfr_core/Cargo.toml

# Full pre-PR check battery (tests, lint, types, diff-tests, license
# audit, perf gate, references integrity; writes pr_report.md):
sh scripts/check_pr.sh
```

`scripts/check_pr.sh` is the same battery the maintainer runs before
every PR review. Treat a clean `pr_report.md` as the minimum bar for a
PR being reviewable.

## Branching

From PR 3 onward every change ships on its own feature branch named
`pr-N-<short-title>` (e.g. `pr-3-hunl-tree`, `pr-4-card-abstraction`).
Never commit directly to `main`. PR 1 and PR 2 went straight to `main`
historically; that lapse is not retroactively fixable but is not the
norm going forward.

## Mandatory PR audit (PR 3+)

Every PR from PR 3 onward gets an independent audit before merge:

1. Run `sh scripts/check_pr.sh` and commit a clean `pr_report.md`.
2. A fresh agent with no implementation context reviews the diff and
   writes `audit_report.md` (must-fix / should-fix / nice-to-fix /
   looks-good).
3. Both `pr_report.md` and `audit_report.md` must look clean before the
   branch is merged.

If you are an external contributor, you do not need to run the audit
agent yourself; the maintainer will run it. But your PR description
should make the audit easy (clear scope, test plan, no drive-by
refactors).

## License + AGPL contamination policy

Project license is **MIT** and that is locked. AGPL contamination is a
one-way door we explicitly avoid.

- **Do not copy or port code from** `b-inary/postflop-solver` (AGPL),
  `bupticybee/TexasSolver` (AGPL), or `24parida/shark-2.0` (unlicensed,
  defaults to all-rights-reserved). These repos are read-only
  inspiration only.
- **OK to port from** `noambrown/poker_solver` (MIT), `slumbot2019`
  (MIT), and `open_spiel` (Apache 2.0) with attribution in code
  comments and (when material) in `CHANGELOG.md`.
- New runtime dependencies must be MIT, Apache 2.0, BSD, or similarly
  permissive. The check battery flags AGPL/GPL strings in build files.

If you are unsure whether a snippet you wrote was influenced by an AGPL
source, say so in the PR — it is far cheaper to rewrite than to
contaminate.

## Style

- **Python:** `ruff check` clean, `black --check` clean, `mypy
  poker_solver` strict-clean on new code. The check battery enforces
  all three.
- **Rust:** `cargo clippy --all-targets -- -D warnings` clean. Zero
  warnings.
- **Reference-first rule:** every non-obvious technical claim in code
  comments, docstrings, or docs should cite a paper, a competitor repo,
  or a test. Do not assert behavior the codebase cannot defend.
- **No floating-point chip math** in `poker_solver/hunl.py`. Integer
  cents only; convert to BB-floats at terminal states.

## Proposing a substantive change

If your change is non-trivial — new module, new algorithm, change to a
locked design decision, or anything cross-cutting — please open an
issue first describing what you want to do and why. Locked decisions
(algorithm = DCFR, abstraction = bucketed 256/128/64, stack range =
2-250 BB, license = MIT, no GPU, no Deep CFR for v1) can be revisited
but the bar is empirical evidence, not preference.

Small fixes (typos, obvious bugs, doc clarifications, test gaps) are
fine to send straight as a PR.
