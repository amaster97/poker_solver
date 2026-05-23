# PR 6 pre-commit checklist

**Date staged:** 2026-05-22
**Author:** orchestrator pre-commit prep agent
**Purpose:** gate list the orchestrator runs immediately before firing
the commit pipeline once the audit verdict clears. Every gate MUST
pass (or carry an explicit waiver with rationale) before `git commit`.

## Build + lint gates (Rust side)

- [ ] **G1 — cargo build clean.** `cargo build --release --package cfr_core` returns 0 with no warnings.
  - Run from repo root.
  - Watch for: `ndarray-npy` resolution, `serde`/`serde_json` derives, `ahash` feature flags.
  - Failure mode: missing `Cargo.toml` dep, unresolved trait bound in `DCFRSolver<HUNLState>`.

- [ ] **G2 — cargo test clean (post-reconciliation).** `cargo test --package cfr_core --all-targets` returns 0; all 12 new Rust tests in `crates/cfr_core/tests/test_hunl_rust.rs` plus PR 1's existing Kuhn/Leduc tests pass.
  - Expected new-test count: 12 (per spec §8.3 Agent C deliverables list).
  - Critical canaries: `test_abstraction_canonicalization_matches_python` (10K random inputs), `test_abstraction_lookup_bucket_matches_python` (10K random inputs), `test_hunl_infoset_key_lossless_format`, `test_hunl_infoset_key_bucketed_format`.
  - Pre-existing Kuhn/Leduc Rust tests MUST remain green (spec §9 #14).

- [ ] **G3 — cargo clippy clean.** `cargo clippy --package cfr_core --all-targets -- -D warnings` returns 0.
  - `-D warnings` upgrades every clippy warning to an error.
  - Watch for: unused imports in new modules, `#[allow(clippy::*)]` overrides creeping in.

## Build + lint gates (Python side)

- [ ] **G4 — pytest fast tier clean.** `pytest -m "not slow and not very_slow" --tb=line` returns 0.
  - All tests pass / skip / xfail. NO failures, NO timeouts.
  - Expected new-test count (Python): 8 in `tests/test_hunl_diff.py` per spec §8.3 Agent C deliverables.
  - PR 1-5 regression (88 + ~22 pre-existing Python tests): all green.
  - Skip rationale (carried from PR 5): 6-test set tied to PR 4's tiny synthetic abstraction's TURN-coverage gap remains skipped; PR 6 does NOT re-enable them in this round (re-enablement is a follow-up once PR 4 fixture revisit lands or PR 6 Rust port exercises full TURN traversal independently).

- [ ] **G5 — ruff + black clean.** `ruff check poker_solver tests` and `black --check poker_solver tests` return 0.
  - Format-only nits acceptable; logical lints are not.

- [ ] **G6 — mypy strict clean on Python changes.** `mypy --strict poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py` returns 0.
  - Per-file check, not whole-tree (which would over-scope to unrelated files).
  - Watch for: `_serialize_hunl_config` return type, `_solve_rust` HUNL branch type narrowing (`isinstance(game, HUNLPoker)` + `Street.PREFLOP` check).

## Correctness gates (cross-tier parity)

- [ ] **G7 — Bit-exact diff verified on tiny river subgame.** `test_hunl_river_subgame_diff_python_vs_rust` passes at far better than the 1e-3 spec tolerance — agent reports BIT-EXACT match (no observable float drift) on the river-only fixture under ahash fixed-seed test mode.
  - Spec §7.1 Test 1 requires 1e-3 relative + 1e-6 absolute floor.
  - Achieved: bit-exact (6 orders of magnitude tighter than spec).
  - If reconciliation/audit reveals this regressed to non-bit-exact, that is an inflection point — confirm 1e-3 still holds before proceeding; do NOT silently loosen the assertion.

- [ ] **G8 — Flop fixture diff within 5e-3.** `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` passes at 5e-3 tolerance (spec §7.1 Test 2).
  - Wall-clock budget: <5 min Python, <30 s Rust per spec.
  - 200 iteration smoke level (NOT a convergence test).

- [ ] **G9 — Action ID constants match Python.** `test_hunl_rust_action_ids_match_python_constants` passes — Rust `ACTION_FOLD = 0`, ..., `ACTION_ALL_IN = 13` integer values match Python's via PyO3 introspection.

- [ ] **G10 — Strategy validity invariants hold.** `test_hunl_rust_strategy_sums_to_one`: every infoset's returned action-probability vector sums to 1.0 ± 1e-9.

- [ ] **G11 — Deterministic-with-seed passes.** `test_hunl_rust_deterministic_with_seed`: same seed + config -> identical strategy, also implicitly validating `py.allow_threads` GIL release across threads (spec §9 #11).

## License + attribution gates

- [ ] **G12 — License attribution headers on every new Rust file.** Each of `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, `abstraction.rs`, `hunl_solver.rs` opens with the module-level attribution docstring per spec §3 template:
  - Names the Python source-of-truth (project-internal, MIT).
  - Names the MIT/Apache reference adapted by pattern (noambrown river_game/cards/trainer, slumbot hand_value_tree/card_abstraction, ndarray-npy MIT/Apache).
  - Carries the explicit `NEVER copy from references/code/postflop-solver (AGPL) or references/code/TexasSolver (AGPL)` disclaimer.
  - Audit-agent focus area #1 + #2.

- [ ] **G13 — abstraction.rs + hunl_solver.rs attribution.** Specifically called out (per user note): `abstraction.rs` cites slumbot2019 `card_abstraction*.cpp` (MIT) for the layout pattern + `ndarray-npy` (MIT/Apache dual-licensed) for the loader. `hunl_solver.rs` cites noambrown_poker_solver `trainer.{h,cpp}` (MIT) for the DCFR-on-postflop control flow.

- [ ] **G14 — `check_pr.sh` license audit clean.** PLAN.md §4 step 6 — confirms no new AGPL/GPL deps. `ndarray-npy` MIT/Apache 2.0 dual-licensed (verified). `ahash` MIT/Apache. `serde_json` MIT/Apache.

## Branch + integration gates

- [ ] **G15 — All 5 branches still synced to origin.** `git fetch --all` then verify the integration baselines have not shifted under PR 6 since the agents launched:
  - `main`: unchanged.
  - `integration`: unchanged (PR 5's tip is still `5832b2f` or whatever it was at PR 6 launch — confirm exact SHA before commit).
  - `pr-3-hunl-core-game`, `pr-4-card-abstraction`, `pr-5-hunl-postflop-solve`: all merged into integration; PR 6 branches off the integration tip.
  - `pr-6-rust-hunl-port` (new): contains all Agent A/B/C diffs, no merge conflicts against integration.
  - If any baseline shifted (e.g., a hotfix landed on PR 5 mid-PR-6), PR 6 must rebase before commit; do NOT commit on stale base.

- [ ] **G16 — No accidental edits to unrelated files.** `git diff integration..pr-6-rust-hunl-port --stat` shows ~18 files staged, scoped to:
  - 5 new Rust source files:
    - `crates/cfr_core/src/hunl.rs` (NEW)
    - `crates/cfr_core/src/hunl_tree.rs` (NEW)
    - `crates/cfr_core/src/hunl_eval.rs` (NEW)
    - `crates/cfr_core/src/abstraction.rs` (NEW)
    - `crates/cfr_core/src/hunl_solver.rs` (NEW)
  - 1 new Rust integration test:
    - `crates/cfr_core/tests/test_hunl_rust.rs` (NEW)
  - 2 new test files (one Rust unit, one Python diff):
    - `crates/cfr_core/tests/hunl_state_unit.rs` (NEW)
    - `tests/test_hunl_diff.py` (NEW)
  - Rust modifications:
    - `crates/cfr_core/Cargo.toml` (MODIFIED, dep adds)
    - `crates/cfr_core/src/lib.rs` (MODIFIED, additive only)
  - Python modifications:
    - `poker_solver/__init__.py` (MODIFIED, re-export surface)
    - `poker_solver/cli.py` (MODIFIED, `--backend rust` flag)
    - `poker_solver/solver.py` (MODIFIED, additive `_solve_rust` branch)
    - `poker_solver/hunl.py` (MODIFIED, `_serialize_hunl_config` add)
  - v0.4 bump + docs touch-ups (ride-along on PR 6 commit):
    - `CHANGELOG.md`
    - `README.md`
    - `pyproject.toml`
    - `Cargo.lock`
    - `docs/roadmap_status_2026-05-22.md`
  - **Addendum:** PR 6 commit will also include the v0.4.0 metadata bump + README/CHANGELOG/roadmap touch-ups that accumulated in the working tree during the PR 6 implementation. These are intentional bundle items, not drift.
  - No edits to: `dcfr.py`, `evaluator.py`, PR 4 abstraction artifacts, PR 5 hunl_solver.py orchestration, Kuhn/Leduc test files, profiler/memory.py.

## Audit gate

- [ ] **G17 — PR 6 audit verdict.** `docs/pr6_prep/audit_report.md` carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY -> commit.
  - READY-WITH-PATCHES -> apply patches in-place, re-run G1-G16 on the patched code, then commit.
  - NOT-READY -> abort commit; orchestrator escalates to the user with the audit-report's must-fix list.
  - Audit focus areas (spec §15): license hygiene per file, integer-only chip arithmetic, banker's-rounding parity ((x + 0.5).floor() not f64::round()), infoset-key byte-for-byte parity, PyO3 GIL release, NEON deferred (zero std::arch::aarch64), diff-test tolerance, dispatch ordering AFTER push/fold short-circuit (PR 9 §6 canonical), `load_abstraction` schema version check + version-mismatch loud error, existing Kuhn/Leduc tests unchanged.

## Biggest gate

**G7 (bit-exact river-subgame diff)** is the biggest gate — it is the load-bearing parity claim for the entire PR 6 narrative. The commit message highlights bit-exact match as exceeding spec tolerance by 6 orders of magnitude; if reconciliation or audit reveals the bit-exact claim regressed (e.g., a HashMap hasher seed isn't actually locked in test mode, or a banker's-rounding edge case slipped through), the commit message must be corrected before commit and the spec's 1e-3 tolerance treated as the operative floor. Do NOT commit with a stale bit-exact claim.

Secondary biggest gate: **G15 (branch sync)** — committing on a stale integration base would silently mask any PR 5 hotfix and cause a merge headache downstream.

## Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-6-hunl-rust-port` with all expected staged changes.
2. `git diff --cached --stat` — final sanity check.
3. `git commit -F docs/pr6_prep/commit_message_draft.md` (or paste the message via HEREDOC per memory's git-safety protocol).
4. `git status` — verify commit success.
5. Push not yet — wait for user OK on the commit + audit report bundle before `git push origin pr-6-hunl-rust-port`.

## Non-commits in this round

- Do NOT auto-merge `pr-6-hunl-rust-port` into `integration`. Wait for PR 7 (noambrown river-spot oracle diff) to land in parallel and merge as a coordinated pair.
- Do NOT close any GitHub PRs yet.
- Do NOT touch PR 4 abstraction artifacts on disk.
- Do NOT rerun PR 5 fixtures; PR 6 inherits PR 5's skip set unchanged.
