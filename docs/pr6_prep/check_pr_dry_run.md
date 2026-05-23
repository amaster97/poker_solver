# PR 6 Dry-Run Check Battery

**Branch:** `pr-6-rust-hunl-port`
**Date:** 2026-05-21 / 2026-05-22 (crossed midnight during pytest)
**Working state:** Uncommitted (3 agent diffs + reconciliation + v0.4.0 bump)
**Purpose:** Verify PR 6 will pass `scripts/check_pr.sh`-equivalent steps before committing.

---

## Overall Verdict

| # | Step | Status |
|---|------|--------|
| 1 | `cargo build --release --package cfr_core` | PASS |
| 2 | `cargo test --package cfr_core --lib --release` | PASS (24 tests) |
| 3 | `cargo test --package cfr_core --all-targets --release -- --test-threads=1` | PASS (24+19+13=56 tests) |
| 4 | `cargo clippy --package cfr_core --all-targets -- -D warnings` | PASS |
| 5 | `pip install -e .` | PASS (after installing `x86_64-apple-darwin` Rust target) |
| 6 | `pytest -m "not slow and not very_slow" --tb=line` | **FAIL** (197 passed, 1 failed, 11 errors — all Leduc timeouts; **all HUNL tests pass**) |
| 7 | `ruff check poker_solver tests` | PASS |
| 8 | `black --check poker_solver tests` | PASS |
| 9 | `mypy poker_solver/hunl_solver.py poker_solver/solver.py` | PASS |

**Final verdict:** 8/9 pass. Step 6 has 1 fail + 11 errors that are **all Leduc pytest-timeout failures** unrelated to HUNL/PR 6 code. Every HUNL test (`test_hunl_core`, `test_hunl_diff`, `test_hunl_postflop_solve`, `test_hunl_tree` — 51 tests) passes cleanly.

---

## Step 1: Cargo Build (release, cfr_core)

```
$ cargo build --release --package cfr_core
   Compiling cfr_core v0.2.0 (/Users/ashen/Desktop/poker_solver/crates/cfr_core)
    Finished `release` profile [optimized] target(s) in 1.83s
```

**Verdict: PASS**

Note: Crate version is still `0.2.0` in `Cargo.toml` even though pyproject bumps to `0.4.0`. This may or may not be intentional — Rust crate vs. Python package version drift was already present pre-PR 6.

---

## Step 2: Cargo Lib Tests (release)

```
$ cargo test --package cfr_core --lib --release
    Finished `release` profile [optimized] target(s) in 0.11s
     Running unittests src/lib.rs (target/release/deps/cfr_core-97e86a7377dd3fde)

running 24 tests
test abstraction::tests::card_int_split ... ok
test abstraction::tests::hand_key_identity_perm ... ok
test abstraction::tests::suit_permutations_match_python_order ... ok
test hunl::tests::action_ids_match_python_constants ... ok
test hunl::tests::banker_rounding_matches_python_on_half ... ok
test hunl::tests::card_encoding_matches_python_range ... ok
test hunl::tests::check_check_advances_to_showdown_on_river ... ok
test hunl::tests::fold_terminates_with_loser_paying_contrib ... ok
test hunl::tests::infoset_key_lossless_format_uses_sorted_cards ... ok
test hunl::tests::raise_cap_postflop_is_three ... ok
test hunl::tests::river_subgame_legal_actions_postflop_open ... ok
test hunl::tests::river_subgame_root_is_player_one_to_act ... ok
test hunl::tests::showdown_winner_collects_loser_contrib ... ok
test hunl_eval::tests::category_ordering ... ok
test hunl_eval::tests::flush_beats_straight ... ok
test hunl_eval::tests::full_house_beats_flush ... ok
test hunl_eval::tests::identical_hands_tie ... ok
test hunl_eval::tests::pair_kickers_compare_correctly ... ok
test hunl_eval::tests::royal_flush_beats_quads ... ok
test hunl_eval::tests::seven_card_picks_best_five ... ok
test hunl_eval::tests::two_pair_kicker_breaks_tie ... ok
test hunl_eval::tests::wheel_straight_is_lowest_straight ... ok
test hunl_tree::tests::river_subgame_tree_builds_and_has_leaves ... ok
test hunl_tree::tests::tree_node_count_is_finite_and_bounded ... ok

test result: ok. 24 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

**Verdict: PASS — 24/24 unit tests.**

---

## Step 3: Cargo All-Target Tests (release, single-threaded)

```
$ cargo test --package cfr_core --all-targets --release -- --test-threads=1

running 24 tests   [lib tests, see Step 2]
test result: ok. 24 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/hunl_state_unit.rs (target/release/deps/hunl_state_unit-08942d1782f44ac6)

running 19 tests
test test_01_initial_postflop_state_invariants ... ok
test test_02_legal_actions_river_root ... ok
test test_03_legal_actions_facing_bet ... ok
test test_04_fold_terminates_correctly ... ok
test test_05_showdown_winner_collects_loser_contribution ... ok
test test_06_raise_cap_postflop ... ok
test test_07_all_in_absorption ... ok
test test_08_infoset_key_lossless_format ... ok
test test_10_infoset_key_with_history ... ok
test test_11_legal_action_dedup ... ok
test test_12_compute_bet_amount_rounding ... ok
test test_13_compute_raise_to_min_increment ... ok
test test_14_tree_build_river_subgame ... ok
test test_15_tree_terminals ... ok
test test_16_strength_evaluator_categories ... ok
test test_17_strength_tie ... ok
test test_18_showdown_tie_returns_zero_utility ... ok
test test_19_card_to_int_range ... ok
test test_20_all_in_runout_single_card_chance ... ok

test result: ok. 19 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/test_hunl_rust.rs (target/release/deps/test_hunl_rust-61189534f9981c4a)

running 13 tests
test test_abstraction_canonicalization_matches_python ... ok
test test_abstraction_lookup_bucket_matches_python ... ok
test test_hunl_action_ids_match_python_constants ... ok
test test_hunl_apply_advances_state_correctly ... ok
test test_hunl_infoset_key_bucketed_format ... ok
test test_hunl_infoset_key_lossless_format ... ok
test test_hunl_initial_state_blinds_posted_correctly ... ok
test test_hunl_legal_actions_at_river_subgame_root ... ok
test test_hunl_solve_reject_preflop ... ok
test test_hunl_solve_river_subgame_smoke ... ok
test test_hunl_strength_eval_handles_ties ... ok
test test_hunl_strength_eval_matches_python ... ok
test test_hunl_tree_build_terminates ... ok

test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.49s
```

**Verdict: PASS — 24 + 19 + 13 = 56/56 tests.** Matches the expected count exactly.

(Note: `hunl_state_unit.rs` has tests 01-20 but only 19 are present — appears `test_09` is intentionally absent, not a regression.)

---

## Step 4: Clippy

```
$ cargo clippy --package cfr_core --all-targets -- -D warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.14s

# Re-run forced rebuild on release profile for confidence:
$ cargo clippy --package cfr_core --all-targets --release -- -D warnings
    Checking pyo3-ffi v0.23.5
    Checking pyo3 v0.23.5
    Checking cfr_core v0.2.0 (/Users/ashen/Desktop/poker_solver/crates/cfr_core)
    Finished `release` profile [optimized] target(s) in 1.70s
```

**Verdict: PASS — no warnings, all targets checked clean.**

---

## Step 5: `pip install -e .`

**First attempt failed** because the Rust toolchain only had `aarch64-apple-darwin` installed but Python is x86_64:

```
error[E0463]: can't find crate for `core`
note: the `x86_64-apple-darwin` target may not be installed
help: consider downloading the target with `rustup target add x86_64-apple-darwin`
```

Resolved with `rustup target add x86_64-apple-darwin` (one-time machine setup, unrelated to PR 6).

After install, retry succeeded:

```
$ pip install -e .
Obtaining file:///Users/ashen/Desktop/poker_solver
  Installing build dependencies: done
  Checking if build backend supports build_editable: done
  Getting requirements to build editable: done
  Preparing editable metadata (pyproject.toml): done
Requirement already satisfied: numpy>=1.24 ...
Requirement already satisfied: psutil>=5.9 ...
Building wheels for collected packages: poker_solver
  Building editable for poker_solver (pyproject.toml): done
  Created wheel for poker_solver: filename=poker_solver-0.4.0-cp313-cp313-macosx_10_12_x86_64.whl
Successfully built poker_solver
Installing collected packages: poker_solver
Successfully installed poker_solver-0.4.0
```

**Verdict: PASS — v0.4.0 editable wheel built and installed cleanly.**

---

## Step 6: Pytest Fast Suite

```
$ pytest -m "not slow and not very_slow" --tb=line
============================= test session starts ==============================
platform darwin -- Python 3.13.1+, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/ashen/Desktop/poker_solver
configfile: pyproject.toml
testpaths: tests
plugins: timeout-2.4.0, asyncio-1.3.0
timeout: 90.0s
collected 222 items / 2 deselected / 220 selected

tests/test_abstraction_buckets.py ..............                         [  6%]
tests/test_abstraction_emd.py ..............                             [ 12%]
tests/test_abstraction_integration.py ..x.....                           [ 16%]
tests/test_action_abstraction.py ............                            [ 21%]
tests/test_card.py ..........                                            [ 26%]
tests/test_dcfr_core.py ....                                             [ 28%]
tests/test_dcfr_diff.py .....                                            [ 30%]
tests/test_equity.py ........                                            [ 34%]
tests/test_evaluator.py ...................                              [ 42%]
tests/test_hunl_core.py ...................                              [ 51%]
tests/test_hunl_diff.py .......                                          [ 54%]
tests/test_hunl_postflop_solve.py .ss.....s.ss...                        [ 61%]
tests/test_hunl_tree.py ..........                                       [ 65%]
tests/test_kuhn_dcfr.py ......                                           [ 68%]
tests/test_leduc_core.py ..............                                  [ 75%]
tests/test_leduc_dcfr.py ...F.                                           [ 77%]
tests/test_leduc_diff.py EEEEE                                           [ 79%]
tests/test_leduc_intuition.py EEEEEE.                                    [ 82%]
tests/test_memory_profiler.py .sss.s....s                                [ 87%]
tests/test_pushfold.py .............                                     [ 93%]
tests/test_range.py ..............                                       [100%]

=========================== short test summary info ============================
FAILED tests/test_leduc_dcfr.py::test_leduc_exploitability_monotone_trend - Failed: Timeout (>90.0s)
ERROR tests/test_leduc_diff.py::test_leduc_python_rust_infoset_keys_match - Failed: Timeout (>180.0s) [fixture]
ERROR tests/test_leduc_diff.py::test_leduc_python_rust_strategy_agreement - Failed: Timeout (>180.0s) [fixture]
ERROR tests/test_leduc_diff.py::test_leduc_python_rust_game_value_agreement - Failed: Timeout (>180.0s) [fixture]
ERROR tests/test_leduc_diff.py::test_leduc_python_rust_exploitability_agreement - Failed: Timeout (>180.0s) [fixture]
ERROR tests/test_leduc_diff.py::test_leduc_both_backends_reach_published_value - Failed: Timeout (>180.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_king_never_folds_to_first_bet - Failed: Timeout (>90.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_jack_never_raises_round1_when_facing_raise - Failed: Timeout (>90.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_pair_with_public_card_value_betting - Failed: Timeout (>90.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_underpair_caution - Failed: Timeout (>90.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_strategy_mass_sums_to_one - Failed: Timeout (>90.0s) [fixture]
ERROR tests/test_leduc_intuition.py::test_strategy_is_well_defined_on_all_reachable_infosets - Failed: Timeout (>90.0s) [fixture]

= 1 failed, 197 passed, 10 skipped, 2 deselected, 1 xfailed, 11 errors in 732.70s (0:12:12) =
```

**Verdict: FAIL** vs. expected ~210 passed / ~10 skipped / 1 xfailed / 0 fail / 0 err.

**Counts:**
- 197 passed (-13 vs. expected)
- 10 skipped (matches)
- 2 deselected (slow markers)
- 1 xfailed (matches)
- 1 failed (`test_leduc_exploitability_monotone_trend`)
- 11 errors (5 in `test_leduc_diff.py`, 6 in `test_leduc_intuition.py` — all "ERROR at setup", i.e. fixture timeouts)
- Total runtime: 12 minutes 12 seconds.

### Failure Analysis

**All 12 failure events are Leduc, not HUNL:**

1. `test_leduc_dcfr.py::test_leduc_exploitability_monotone_trend` — Direct timeout. Test runs 3 sequential `solve(LeducPoker(), n)` calls at n=100/300/600 iterations on the **default Python backend** (slow). Smoke-test measurement on this machine: Python Leduc solve at 200 iters ≈ 14s, so 100+300+600 ≈ 70s plus framework overhead exceeds the 90s default timeout.

2. `test_leduc_diff.py` (5 errors) — Module-scoped fixture `both_results()` calls **both** `solve(..., backend="python")` **and** `solve(..., backend="rust")` at 2000 iterations. Python at 2000 iters ≈ 140s on this machine; Rust ≈ 18s. The fixture's per-test `_LEDUC_DIFF_TIMEOUT = 180s` is exceeded by the Python leg alone.

3. `test_leduc_intuition.py` (6 errors) — Same root cause: module fixture invokes a slow Python Leduc solve that exceeds the 90s default timeout.

**Root cause assessment:** These look like **pre-existing slowness in Python Leduc on this machine**, not regressions introduced by PR 6. The Rust Leduc path works fine (independently verified: 100-iter Rust solve completes in ~0.9s). The failures are purely about the **Python baseline** taking too long to fit inside the pytest-timeout cap.

**HUNL tests (PR 6 scope) — all green:**
- `test_hunl_core.py` — 19/19 passed
- `test_hunl_diff.py` — 7/7 passed (new file, Python↔Rust postflop parity)
- `test_hunl_postflop_solve.py` — 15/15 passed (.ss.....s.ss... = 11 passed + 4 skipped)
- `test_hunl_tree.py` — 10/10 passed

PR 6 has not regressed any HUNL behavior.

**Recommendation:** This is a check_pr.sh blocker as-is. Options:
- (a) Mark the affected Leduc tests as `@pytest.mark.slow` (preferred — they're 70-300s Python baselines).
- (b) Bump per-test timeouts in `test_leduc_dcfr.py` / `test_leduc_intuition.py` to 240-300s.
- (c) Investigate whether the Python Leduc solver has slowed down on a recent commit (pre-PR 6). Compare against a fresh checkout of `main`.

I did **not** patch any of these — out of scope for "dry-run sanity, no commits."

---

## Step 7: Ruff

```
$ ruff check poker_solver tests
All checks passed!
```

**Verdict: PASS.**

---

## Step 8: Black `--check`

```
$ black --check poker_solver tests
All done! ✨ 🍰 ✨
45 files would be left unchanged.
```

**Verdict: PASS.**

---

## Step 9: Mypy (strict on PR 5 + PR 6 modules)

```
$ mypy poker_solver/hunl_solver.py poker_solver/solver.py
Success: no issues found in 2 source files
```

**Verdict: PASS.**

---

## Summary

| Category | Result |
|----------|--------|
| Rust build + tests + clippy (steps 1-4) | clean |
| Editable install (step 5) | clean after one-time `rustup target add x86_64-apple-darwin` |
| Pytest fast suite (step 6) | **1 failed + 11 errored — all Leduc Python-baseline timeouts**, all HUNL green |
| Python lint/format/type (steps 7-9) | clean |

**Anomaly to surface to user before commit:**
The Leduc Python-baseline tests don't fit inside the default 90s pytest-timeout cap on this machine. This is independent of PR 6 (Rust HUNL port) but **will block any `check_pr.sh` run** because step 6 returns nonzero exit. Recommend pre-commit either marking these as `slow` or bumping their per-test timeouts.

**Environment notes:**
- macOS arm64 (Darwin 24.6.0) running x86_64 Python under Rosetta — required installing `x86_64-apple-darwin` Rust target before maturin succeeded.
- Python: 3.13.1+ (pyenv 3.13-dev), x86_64.
- Rust: 1.95.0 stable, aarch64+x86_64 targets installed.
- Pytest: 9.0.2 with timeout=90s default.
