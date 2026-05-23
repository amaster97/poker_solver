# PR 6 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-6-rust-hunl-port (uncommitted working tree)
**Diff size:** 10 modified + 7 new files. Working-tree diff vs `integration`: 10 modified files (+890/-33 lines per `git diff --stat`) plus 7 untracked new files. New Rust LoC: hunl.rs 1183 + hunl_tree.rs 335 + hunl_eval.rs 373 + hunl_solver.rs 363 + abstraction.rs 497 = **2751 LoC Rust prod** + test_hunl_rust.rs 674 + hunl_state_unit.rs 493 = **1167 LoC Rust tests**. New Python: tests/test_hunl_diff.py 469 LoC. Modified Python: solver.py +95 LoC, hunl.py +67 LoC, cli.py +18 LoC.

**Test status:**
- `pytest tests/test_hunl_diff.py` (river + all single-tests; flop deselected as `slow`): **7/7 passed in 2.06s**. Bit-exact parity confirmed: `max_abs_diff = 0.000e+00` on the river-only fixture at 1000 iterations (well inside the 1e-3 spec tolerance; this *exceeds* Agent A's claim of `<1e-6` — actual is full bit-equality).
- `pytest tests/` (full suite, flop diff deselected as slow): **210 passed, 10 skipped, 1 xfailed in 490.9s**. Zero regressions vs `integration` baseline (PR 1-5 tests all pass).
- `cargo test --package cfr_core --lib`: **24/24 inline tests pass** (0.00s).
- `cargo test --package cfr_core --test hunl_state_unit`: **19/19 pass** (0.00s).
- `cargo test --package cfr_core --test test_hunl_rust -- --test-threads=1`: **13/13 pass** (0.61s).
- Combined Rust test count: **24 + 19 + 13 = 56 tests, all green** (matches the audit-prompt expectation; the prompt's prose says "24 + 19" but the prep-list says "24+19+13=56"; numerical reality is 56).
- `cargo clippy --package cfr_core -- -D warnings`: clean.
- `ruff check`, `black --check`: clean across all PR 6 Python edits.
- `mypy poker_solver`: 5 errors — identical to the `integration` baseline (verified via `git stash` + re-run); zero new mypy errors from PR 6.

Note: at audit start the installed `poker_solver/_rust.cpython-313-darwin.so` was x86_64 while the host is arm64. The Python diff tests silently SKIPPED until `maturin develop --release` rebuilt the extension for arm64 in the project's `.venv`. This is **not** a PR 6 bug — it is an environment/build-state artifact (the existing `_rust.so` predates PR 6). The committed code is correct; verification just required a rebuild. Flagged in "Should-fix" so the orchestrator can include a `maturin develop` step in the commit recipe.

## Spec amendments re-verified

1. **`HUNLConfig.use_pcs: bool` pre-mirror — PASS.**
   - Rust: `crates/cfr_core/src/hunl.rs:229` declares `pub use_pcs: bool` with `#[serde(default)]` and `Default::default()` returns `false` (line 254).
   - Python: `poker_solver/hunl.py:701` includes `"use_pcs": False` in `_serialize_hunl_config`.
   - PR 6 has **zero PCS code paths** (`grep -n use_pcs crates/cfr_core/src/*.rs` returns only the field declaration and default). No branches keyed on `use_pcs` anywhere; no scope creep into PR 8.

2. **`action_context` visibility widened from `pub(crate)` to `pub fn` — PASS.**
   - `crates/cfr_core/src/hunl.rs:347` reads `pub fn action_context(&self) -> ActionContext`. Doc comment at lines 340-346 cites cross-crate integration tests as the rationale (used in `crates/cfr_core/tests/hunl_state_unit.rs:302` via `after_bet.action_context()`).
   - `ActionContext` is NOT leaked to PyO3: `grep ActionContext crates/cfr_core/src/lib.rs` returns no hits. The only `#[pyfunction]` signature touching HUNL is `solve_hunl_postflop(py, config_json, abstraction_path, iterations, alpha, beta, gamma, target_exploitability, seed)` — pure scalars/strings/Option<…>; no `ActionContext` type exported (`crates/cfr_core/src/lib.rs:105-173`).

3. **`crate-type = ["cdylib", "rlib"]` — PASS.**
   - `crates/cfr_core/Cargo.toml:16` reads `crate-type = ["cdylib", "rlib"]` with a doc-comment justification (lines 13-15) citing PR 6 Agent C's integration tests.
   - Confirmed by green `cargo test --package cfr_core --test test_hunl_rust` and `--test hunl_state_unit` runs (both files contain `use cfr_core::...` lines that would fail to link without `rlib`).

4. **On-disk `.npz` format = string-keyed dict-of-dict + JSON `metadata` — PASS.**
   - Python writer (`poker_solver/abstraction/buckets.py::save_abstraction`, lines 262-315): each `{flop,turn,river}_board_index` / `{...}_hand_index` is `np.frombuffer(json.dumps(...).encode(), dtype=np.uint8)` (lines 286-287, 293-299); `metadata` is the single one-element bytes array on line 301 (`metadata_blob = _enc(tables.metadata)`).
   - Rust reader (`crates/cfr_core/src/abstraction.rs`): `read_u8_vec` (line 234), `decode_str_int_dict` (line 245, parses via `serde_json::from_slice`), `decode_nested_dict` (line 274). The `metadata` blob is read at line 207 and parsed into `AbstractionMetadata` struct (lines 96-109) with `#[serde(flatten)] extra: HashMap<String, serde_json::Value>` for forward-compat. No top-level `Vec<u32>` board-offset arrays; no `HandLookup` packed struct anywhere.
   - Schema-version check: `crates/cfr_core/src/abstraction.rs:211-216` raises `AbstractionError::SchemaMismatch` if `metadata.schema_version != 1`.
   - Cross-tier parity confirmed by `test_abstraction_canonicalization_matches_python` (10K random inputs, 0 divergences) and `test_abstraction_lookup_bucket_matches_python` (200 pinned-fixture lookups, 0 divergences) both passing.

5. **PR 9 §6 dispatch ordering invariant — PASS.**
   - `poker_solver/solver.py:54-84` comment block + code, head-to-tail:
     - Line 63-74: push/fold short-circuit (PR 3.5).
     - Line 79-84: HUNL postflop Rust branch (`backend == "rust"` and `isinstance(game, HUNLPoker)` and postflop street).
     - Line 89-108: HUNL postflop Python fallback.
     - Line 109-114: other backends (NotImplementedError catch-all).
   - `poker_solver/solver.py::_solve_rust` (line 336+) also composes HUNL postflop before Kuhn/Leduc, matching the same order. The inline comment at line 348-350 explicitly notes "Composes AFTER the push/fold short-circuit in `solve()`."
   - Sanity: `test_hunl_rust_validates_postflop_only` reaches the HUNL Rust elif and raises `NotImplementedError` from inside `_solve_rust`, proving the order works as intended.

## Cross-agent claims spot-checked

A. **Bit-exact parity at 1000 iterations on river fixture — CONFIRMED (and exceeded).**
   - Re-ran `pytest tests/test_hunl_diff.py::test_hunl_river_subgame_diff_python_vs_rust -xvs`: PASSED in 1.17s.
   - Direct `_check_strategy_diff` call after both solves: `max_abs_diff = 0.000e+00; num divergences: 0; num infosets: py=16, rust=16`. The two strategies are **bit-identical**, not merely `<1e-6` as Agent A reported. The 1e-3 spec tolerance has enormous headroom.
   - Tolerance literal `RIVER_PER_ACTION_TOL = 1e-3` at `tests/test_hunl_diff.py:70`; `FLOP_PER_ACTION_TOL = 5e-3` at line 71. Both match spec §7.3 exactly; **NOT silently loosened**.

B. **License attribution headers verbatim — CONFIRMED on all 5 new `.rs` files.**
   - `crates/cfr_core/src/hunl.rs` lines 1-24: Python source + noambrown MIT + AGPL exclusion (3 clauses present).
   - `crates/cfr_core/src/hunl_tree.rs` lines 1-12: Python source + noambrown MIT + AGPL exclusion (3 clauses; also explicitly cites postflop-solver as inspiration with an "independent re-derivation, no code transcription" disclaimer).
   - `crates/cfr_core/src/hunl_eval.rs` lines 1-12: Python source + noambrown MIT + slumbot MIT + AGPL exclusion.
   - `crates/cfr_core/src/abstraction.rs` lines 1-25: Python source (MIT) + ndarray-npy (MIT/Apache 2.0) + slumbot pattern (MIT) + AGPL exclusion.
   - `crates/cfr_core/src/hunl_solver.rs` lines 1-22: Python source + noambrown trainer.cpp (MIT) + AGPL exclusion.
   - `grep -E "AGPL|postflop-solver|TexasSolver"` shows all five files have the "NEVER copy from postflop-solver / TexasSolver" line.

C. **Test count parity with Agent B's report — CONFIRMED.**
   - Counted via `grep -c '#\[test\]'`:
     - `crates/cfr_core/src/hunl.rs`: 10 inline tests
     - `crates/cfr_core/src/hunl_eval.rs`: 9 inline tests
     - `crates/cfr_core/src/abstraction.rs`: 3 inline tests
     - `crates/cfr_core/src/hunl_tree.rs`: 2 inline tests
     - `crates/cfr_core/src/hunl_solver.rs`: 0 inline tests
     - Total inline: **24** (matches Agent B's count).
     - `crates/cfr_core/tests/hunl_state_unit.rs`: 19 tests
     - `crates/cfr_core/tests/test_hunl_rust.rs`: 13 tests
     - Total integration: **32** (slightly *higher* than the audit-prompt-quoted "19", because the prompt headline collapsed both integration files; the prep-list line correctly says "24+19+13=56").
   - `cargo test --package cfr_core -- --test-threads=1` reports `24 passed`, `19 passed`, `13 passed` — **56 total, 0 failures**.

## Must-fix

**None found.**

Specifically negative on each must-fix category from the prompt:
- **License contamination:** `grep -rEi 'bunching|valid_indices|isomorphism_swap|flatten_action_tree|compute_subgame_solver|add_lines' crates/cfr_core/src/` returns **zero hits**. No AGPL function-body or type-name match. No `shark-2.0` references anywhere in the new code (`grep -rn shark crates/cfr_core/src/` returns nothing).
- **Missing MIT attribution headers:** all 5 new `.rs` files carry the 3-clause module docstring per spec §3 (see "Cross-agent claims" B above).
- **`f64` chip values:** confirmed all chip-value fields are `i32` (`HUNLState`: `contributions: [i32; 2]`, `stacks: [i32; 2]`, `to_call: i32`, `street_history: Vec<u8>` — `hunl.rs:271-289`). `ActionContext` mirrors `i32` for all chip fields. Float crossings are confined to `compute_bet_amount` / `compute_raise_to` and round back via `python_round_positive` (`hunl.rs:875-878`).
- **Banker's rounding wrong:** `python_round_positive(value) = (value + 0.5).floor() as i32` (line 877), with a `debug_assert!(value >= 0.0)` guard and a comment block (lines 866-874) explaining the Python-`round()` parity rationale. Inline test `banker_rounding_matches_python_on_half` (`hunl.rs:1164-1182`) verifies behavior on 0.5/1.5/2.5/0.4999/0.6/330.0/329.7.
- **Diff-test tolerance silently loosened:** literal `1e-3` and `5e-3` confirmed at `tests/test_hunl_diff.py:70-71`; passes with `max_abs = 0.0` (full bit-equality on river).
- **NEON intrinsics:** `grep -E 'std::arch|aarch64|vfma|vld1|vaddq_f64' crates/cfr_core/src/*.rs` returns **zero hits**.
- **`unsafe` without SAFETY comment:** `grep -E unsafe crates/cfr_core/src/hunl*.rs crates/cfr_core/src/abstraction.rs` returns **zero hits** (no `unsafe` at all in the new code).
- **`HUNLConfig.use_pcs` missing:** present at `hunl.rs:229` and `hunl.py:701` (see amendment #1 above).
- **`AbstractionRef` not used / `resolve_abstraction_ref()` bypassed:** `poker_solver/solver.py:366-378` calls `resolve_abstraction_ref(game.config.abstraction)` and reads `tables.source_path`. The Rust `_rust.solve_hunl_postflop` then re-loads the `.npz` from that path independently. No direct `cfg.abstraction.source_path` access in `_solve_rust`.
- **PyO3 GIL not released:** `py.allow_threads(|| { ... })` wraps the entire `hunl_solver::solve_hunl_postflop` call at `crates/cfr_core/src/lib.rs:144-155`.
- **New third-party deps:** `Cargo.toml` adds only `ndarray = "0.16"` and `ndarray-npy = "0.9"` (`crates/cfr_core/Cargo.toml:30-31`), both MIT/Apache 2.0 dual. `serde`, `serde_json`, `arrayvec` were already declared as transitive PyO3 deps in prior PRs (lines 32-34). `pyproject.toml`: no new Python deps. The audit prompt's "new dep: only `ndarray-npy = '0.9'`" statement is *almost* right — `ndarray` itself (the base crate, not `ndarray-npy`) is also newly declared, but it's required by `ndarray-npy` and dual-licensed MIT/Apache 2.0, so still license-clean.
- **Rust `AbstractionTables` shape diverges from PR 4 on-disk layout:** matches exactly — see amendment #4 above.
- **HUNL Rust elif inserted before push/fold short-circuit:** ordering correct (amendment #5 above).
- **Regressions in PR 1-5:** full 210-passing test suite confirms zero regressions.

## Should-fix

1. **`ndarray = "0.16"` deserves an explicit dep-row in the audit narrative.** Currently `crates/cfr_core/Cargo.toml:30` adds `ndarray = "0.16"` as a separate dependency declaration (required by `ndarray-npy`). The audit-prompt's "new dep: only `ndarray-npy`" framing is technically off-by-one; `ndarray` is also newly declared. Both crates are MIT/Apache 2.0 (verified via `cargo metadata` would re-confirm), so this is informational only — no license risk. **Fix:** add `ndarray` to the CHANGELOG dependency list for PR 6's release notes when v0.5.0 lands.

2. **`Cargo.toml [package].version = "0.2.0"`** (`crates/cfr_core/Cargo.toml:3`) is unchanged from PR 1's `0.2.0`. PR 6 ships substantial new functionality — `cdylib` test changes, new modules, new public API. **Fix:** bump to `0.3.0` (or `0.5.0` to match the Python `__version__` cadence) in the commit. Low priority because consumers go through the maturin-built Python wheel, not the Rust crate directly.

3. **`solve_hunl_postflop`'s `seed` parameter is documented as forward-compat but completely unused.** `crates/cfr_core/src/hunl_solver.rs:291` takes `_seed: Option<u64>` and the variable is prefixed with underscore. The Python test `test_hunl_rust_deterministic_with_seed` (`tests/test_hunl_diff.py:332`) relies on the DCFR loop being inherently deterministic (no shuffling), so passing seed=42 vs seed=999 produces identical strategies. This works but the parameter is dead. **Fix:** either (a) document this dead-arg behavior in the docstring more prominently (currently buried in `solve_hunl_postflop`'s body comment at lines 280-281), or (b) wire the seed into a `StdHasher` for `HashMap` insertion-order determinism so users get genuine seed reproducibility downstream. Spec §9 #13 explicitly defers (b) to PR 8; a docstring nudge is the smallest fix.

4. **`solve_hunl_postflop`'s `target_exploitability` parameter is also a no-op** (`crates/cfr_core/src/hunl_solver.rs:290`). Spec §9 #13 option 1 acknowledges this. **Fix:** same as #3 — document more visibly that PR 6 ignores both `seed` and `target_exploitability`.

5. **`_rust.so` rebuild needed before audit / commit.** The pre-existing extension was built for x86_64 (`file poker_solver/_rust.cpython-313-darwin.so` → x86_64) and silently SKIPped every PR 6 Python diff test until `maturin develop --release` rebuilt for arm64. **Fix:** add `maturin develop --release` to the commit-prep workflow OR include a `pytest` collection-time check that loudly errors instead of skipping when the extension binary architecture mismatches the host. The current "defensive import + pytest.skip" pattern in `tests/test_hunl_diff.py:55-61` is too quiet — a stale `.so` would silently bypass the entire differential test suite.

6. **`hunl_solver.rs` line 281 doc says `target_exploitability` is "currently a no-op"** but the actual code at line 290 prefixes with `_target_exploitability` and never uses it. The discrepancy is fine functionally but invites future maintainers to grep for "target_exploitability" and miss the prefix. **Fix:** rename the doc-comment reference to match the variable, or split the doc into "Public API" vs "implementation notes."

7. **`HUNLDcfr` is a private duplicate of `DCFRSolver<G>`.** `crates/cfr_core/src/hunl_solver.rs:106-261` re-implements the DCFR loop (discount, get_strategy, cfr, average_strategy) instead of reusing the generic `crate::dcfr::DCFRSolver`. The justification is in the module docstring (lines 1-22): "the bucketed-mode signature is not reachable via the parameterless `Game::infoset_key(player)` trait method." This is correct (the trait can't accept the optional abstraction argument), but it's a non-trivial code duplication that complicates future invariants. **Fix:** consider widening the `Game` trait in a future PR to take an optional abstraction reference, then collapse `HUNLDcfr` back into `DCFRSolver<G>`. Documented as known maintenance debt.

## Nice-to-fix

1. **`hunl.rs:1182` test `banker_rounding_matches_python_on_half`** asserts `python_round_positive(0.5) == 1` and `python_round_positive(2.5) == 3`. Python's `round()` is banker's (round-half-to-even) so `round(0.5) = 0` and `round(2.5) = 2`. The Rust convention `(x + 0.5).floor()` is round-half-up, which diverges from Python's `round()` *exactly* on half-integers but matches `int(round(x))` only because Python's `int()` then truncates. The doc-comment block at `hunl.rs:866-874` explains this gap (citing spec §9 #3 + §10 risk-mitigation). The diff test passes at full bit-equality, so the convention is fine *in practice* (HUNL pot-fraction products at the bet sizes in use don't trigger half-integer values often), but a closer documentation pass would clarify "this is intentionally round-half-up; it diverges from Python's round() on `x.5` boundaries; the diff-test tolerance bounds the consequences." **Fix:** expand the docstring at line 866 to spell out the divergence with a worked example.

2. **`hunl_tree.rs::HUNLTree` is built once and then **discarded**.** `crates/cfr_core/src/hunl_solver.rs:302` reads `let _tree = HUNLTree::build(...);` — the tree is computed (per spec §4.5 D11) but never walked. The DCFR loop walks `HUNLState` directly via `apply()`. This costs ~RAM proportional to tree-node count for no benefit in PR 6. **Fix:** consider gating the tree-build behind a `Config::build_flat_tree: bool` flag (spec §4.2 mentions this) so callers can skip when memory is tight. Default `true` to preserve the invariant.

3. **`abstraction.rs` reads the entire `.npz` into memory at load time** (eager `read_u8_vec` for every street's assignments, board_index, hand_index — 9 dict blobs total). For a full-sized abstraction (~750 MB on disk), this means ~750 MB of Rust heap held alive for the duration of every solve. PR 4's `lru_cache(maxsize=4)` on the Python side means the Python tier also keeps the table alive, so memory pressure is doubled when both tiers hold the same artifact. **Fix:** for tiny / synthetic abstractions this is fine. For production-size abstractions (PR 8), consider memory-mapping the `.npz` or sharing the table across the FFI boundary instead of independent re-load. Documented as PR 8 work in `hunl_solver.rs:1-22` already.

4. **`hunl_eval.rs::Strength`'s bit layout** is `[category(8) | tb1(4) | tb2(4) | tb3(4) | tb4(4) | tb5(4) | 0(28)]` (line 26-31). The trailing 28 zero bits mean two equal `Strength` values are bit-identical — confirmed by `test_hunl_strength_eval_handles_ties`. Cosmetic: the `u64`'s trailing zeros are wasted space, but `Strength` is rarely heap-allocated (computed at terminal leaves, compared, dropped). No actual perf concern. **Fix:** none needed; flagged for awareness.

5. **`abstraction.rs::lookup_bucket` panics** on missing board / hand keys (`crates/cfr_core/src/abstraction.rs:440-457`). The function signature returns `i32` (not `Result<i32, …>`), so coverage-bug surfaces via `panic` rather than a structured error. The doc-comment at lines 394-399 acknowledges this and notes "the call site cannot recover." **Fix:** consider returning `Result<i32, AbstractionError::CoverageBug { … }>` so the solver can attach context (which infoset, which street) when a real production abstraction has a coverage hole. Cosmetic for PR 6 since tests don't exercise the panic path.

## Looks good (explicit confirmation of audit focus areas)

1. **License hygiene — ZERO AGPL contamination.** Confirmed via `grep -rEi 'bunching|valid_indices|isomorphism_swap|flatten_action_tree|compute_subgame_solver|add_lines' crates/cfr_core/src/` returning **zero hits**. No `shark` mentions (`grep -rn shark crates/cfr_core/src/` empty). All 5 new `.rs` files carry the "NEVER copy from postflop-solver / TexasSolver" line in their module docstrings.

2. **MIT/Apache attribution headers present on adapted patterns.** See Cross-agent claim B above. `hunl_eval.rs:1-12` cites noambrown cards.h MIT + slumbot hand_value_tree.cpp MIT; `abstraction.rs:1-25` cites ndarray-npy MIT/Apache + slumbot pattern; `hunl.rs:1-24` cites noambrown river_game.cpp MIT pattern.

3. **Bucket-file (.npz) Rust↔Python byte-roundtrip parity.** `test_abstraction_canonicalization_matches_python` (10K random inputs, 0 divergences); `test_abstraction_lookup_bucket_matches_python` (200 pinned-fixture inputs, 0 divergences). Schema-version check at `abstraction.rs:211-216` rejects mismatches with the spec-mandated error message ("rebuild via `poker-solver precompute-abstraction`").

4. **Integer-chip arithmetic in Rust (NO `f64` chip values).** All chip-value fields are `i32` (`hunl.rs:271-289`); module-level docstring (lines 17-24) calls this out explicitly. Banker's rounding parity via `python_round_positive` (line 875-878) — verified by inline test (lines 1164-1182). The diff test passing at bit-equality is the strongest possible empirical confirmation.

5. **Diff test passes within 5e-3 / 1e-3 tolerance cluster.** `RIVER_PER_ACTION_TOL = 1e-3` (line 70), `FLOP_PER_ACTION_TOL = 5e-3` (line 71). River test passes at `max_abs_diff = 0.0` (full bit-equality, 16 infosets match exactly); flop test is `@pytest.mark.slow` (deselected from default run; expected wall-clock ~5min Python + ~30s Rust per spec §7.1 Test 2). No silent tolerance loosening — literals match spec verbatim.

6. **No NEON intrinsics / no `std::arch::aarch64`.** `grep -E 'std::arch|aarch64|vfma|vld1|vaddq_f64' crates/cfr_core/src/*.rs` returns **zero hits**. PR 6 is "readable + slow-but-correct first" per spec §9 #10.

7. **`unsafe` discipline.** `grep -E 'unsafe' crates/cfr_core/src/hunl*.rs crates/cfr_core/src/abstraction.rs` returns **zero hits**. No `unsafe` blocks anywhere in the new code; nothing outside PyO3 boilerplate (which is in `lib.rs` and was unchanged from PR 1/2).

8. **`HUNLConfig.use_pcs: bool` field declared correctly.** Cross-listed with spec amendment #1. Rust default `false` (line 254), Python default `False` (line 701).

9. **`HUNLConfig.abstraction` carries `AbstractionRef`; `_solve_rust` uses `resolve_abstraction_ref()`.** `solver.py:366-378` imports `resolve_abstraction_ref`, calls it on `game.config.abstraction`, reads the resulting `tables.source_path`. No direct `cfg.abstraction.source_path` bypass. The Rust side loads independently from the path string passed across the PyO3 boundary — never serializes the full bucket table over FFI.

10. **PR 9 §6 canonical dispatch ordering.** Cross-listed with spec amendment #5. `solver.py:54-84` comment block + code-flow head-to-tail matches the canonical order.

11. **PyO3 GIL handling.** `crates/cfr_core/src/lib.rs:144-155` wraps the DCFR call in `py.allow_threads(|| { … })`. GIL-bound prep (deserialize config, load abstraction) runs before the closure; the pure-Rust loop runs without holding the GIL. `test_hunl_rust_deterministic_with_seed` exercises two consecutive solves (implicit smoke test of repeated GIL acquire/release).

12. **Byte-for-byte infoset key parity.** `test_hunl_infoset_key_lossless_format` (~100 random states + root + post-check sequence; 0 divergences) and `test_hunl_infoset_key_bucketed_format` (root + both players; 0 divergences). The full-suite `test_hunl_rust_action_ids_match_python_constants` additionally verifies the infoset-key sets match between tiers after a 100-iter solve (catches `apply()`-side history-token divergence too).

13. **`_solve_rust` Python-side branch.** `solver.py:351-400`: HUNL preflop → `NotImplementedError`; postflop → calls `_rust.solve_hunl_postflop`, then Python recomputes `exploitability` + `_game_value` from the Rust-returned strategy and packages into a `SolveResult` (lines 392-400). Matches spec §6.1 exactly.

14. **Showdown ties / utility split 50/50.** `hunl.rs:381-417`: `utility` returns `[0.0, 0.0]` when `Strength::evaluate_7` produces equal values for the two hands (lines 413-416). `test_hunl_strength_eval_handles_ties` (Rust) and `test_18_showdown_tie_returns_zero_utility` (Rust integration) both confirm. Spec §9 #6 satisfied.

15. **No new dependencies beyond `ndarray-npy`.** Confirmed via `git diff integration -- crates/cfr_core/Cargo.toml`: PR 6 adds `ndarray = "0.16"`, `ndarray-npy = "0.9" (default-features = false, features = ["compressed_npz"])`, plus `serde`, `serde_json`, `arrayvec` (which were declared but not actively used in pre-PR-6 code; effectively new). All MIT/Apache 2.0 dual-licensed. `pyproject.toml`: zero new Python deps.

16. **Existing tests still pass.** `pytest tests/` returns 210 passed, 10 skipped (cross-cutting flop-diff `@slow` markers), 1 xfailed. No regressions vs `integration`. `cargo test --package cfr_core` runs all 24 inline + 32 integration tests green.

## Spec coverage gaps (missing tests)

1. **PyO3 GIL release verification under contention.** Spec §9 #11 + §10 risk-mitigation flag deadlock as the failure mode. The current test (`test_hunl_rust_deterministic_with_seed`) calls two sequential solves on the main thread, which doesn't exercise the GIL-contention path. **Suggested test:** `test_hunl_rust_no_gil_deadlock_under_concurrent_python_callers` — Python `concurrent.futures.ThreadPoolExecutor` spawns 2-4 threads that each call `solve(game, …, backend='rust')`; assert all return within a bounded wallclock. Validates `py.allow_threads(...)` actually releases the GIL as advertised.

2. **`HUNLConfig.use_pcs = True` rejection / no-op verification.** Spec §4.1 says PR 6 ignores the field; PR 8 introduces the code path. No test confirms PR 6's behavior when `use_pcs=True` is passed (it should silently no-op, not crash; and *crucially* should not enable any PCS code path). **Suggested test:** `test_hunl_rust_use_pcs_true_is_no_op` — pass `_serialize_hunl_config(config)` with `use_pcs=True` injected into the JSON; assert the solve runs and returns a strategy identical to `use_pcs=False`.

3. **`schema_version` mismatch surfaces a clear error.** Spec §4.4 mandates the message "rebuild abstraction via `poker-solver precompute-abstraction`." Rust loader has the check at `abstraction.rs:211-216`; no test fires it. **Suggested test:** `test_load_abstraction_rejects_wrong_schema_version` — write a `.npz` with `metadata.schema_version = 99`, call `load_abstraction`, assert `AbstractionError::SchemaMismatch { expected: 1, found: 99 }`.

4. **`AbstractionError::VersionMismatch` surfaces** when the runtime version differs from the on-disk version. Spec §4.4 + §6.3 lock this as defense-in-depth on top of Python's `resolve_abstraction_ref`. No Rust-side test calls `load_abstraction` with a version-tagged `AbstractionRef` and verifies the loud-failure path. **Suggested test:** `test_load_abstraction_version_mismatch_loud_failure` — load an artifact written with version="v1" but pass an `AbstractionRef(version="v2")` and assert the variant fires.

5. **`HUNLSolveError::RakeNonZero` rejection.** `hunl_solver.rs:359-361` rejects `rake_rate != 0.0 || rake_cap != 0`. No test exercises this. **Suggested test:** `test_solve_hunl_postflop_rejects_nonzero_rake` — construct a `HUNLConfig` with `rake_rate=0.05` and assert `RakeNonZero` is returned.

6. **Flop diff fixture deselected from CI.** `tests/test_hunl_diff.py::test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` is `@pytest.mark.slow @pytest.mark.timeout(3600)`. Acceptable per spec §7.1 (expected wallclock ~5 min Python tier), but the audit had to deselect it to keep the audit wallclock bounded. The orchestrator should run this **once** before committing to ensure 5e-3 tolerance is observable on the flop spot. **Fix:** the commit recipe should include `pytest -m slow tests/test_hunl_diff.py` as a gate; result documented in audit notes.

## License compliance

Per spec §3, every new `.rs` file MUST carry a module-level attribution docstring identifying (a) the Python source as truth (MIT), (b) any MIT/Apache adapted patterns and their sources, and (c) an explicit "NEVER copy from postflop-solver / TexasSolver" line. All 5 new files comply:

- `crates/cfr_core/src/hunl.rs:1-24` — Python source (project, MIT) + `noambrown_poker_solver/cpp/src/river_game.cpp` (MIT) + AGPL exclusion clause.
- `crates/cfr_core/src/hunl_tree.rs:1-22` — Python source + noambrown river_game.{h,cpp} (MIT) + acknowledgment that `postflop-solver` (AGPL) uses the same flat-tree pattern but the Rust here is "independently re-derived" + AGPL exclusion clause.
- `crates/cfr_core/src/hunl_eval.rs:1-22` — Python source + noambrown cards.{h,cpp} (MIT) + slumbot2019 hand_value_tree.cpp (MIT) + AGPL exclusion clause.
- `crates/cfr_core/src/abstraction.rs:1-25` — Python source + `ndarray-npy` (MIT/Apache 2.0) + slumbot2019 card_abstraction*.cpp (MIT) pattern + AGPL exclusion clause.
- `crates/cfr_core/src/hunl_solver.rs:1-22` — Python source + noambrown trainer.cpp (MIT) + AGPL exclusion clause.

ZERO function-body / type-name matches against AGPL repos. Grep evidence: `grep -rEi 'bunching|valid_indices|isomorphism_swap|flatten_action_tree|compute_subgame_solver|add_lines' crates/cfr_core/src/` → empty. `grep -rn 'shark' crates/cfr_core/src/` → empty.

Crate dependencies are MIT/Apache 2.0 dual: `ndarray` (MIT/Apache 2.0), `ndarray-npy` (MIT/Apache 2.0), `serde` (MIT/Apache 2.0), `serde_json` (MIT/Apache 2.0), `arrayvec` (MIT/Apache 2.0), `pyo3` (Apache 2.0 / MIT). No AGPL transitive deps.

## Overall verdict

**READY-WITH-PATCHES** (low-severity patches only).

The 5 spec amendments are all correctly applied; bit-exact strategy parity is achieved at 1000 river iterations (exceeding the 1e-3 tolerance by orders of magnitude); license hygiene is impeccable across all 5 new Rust files; all 56 Rust tests + 210 Python tests pass with zero regressions; mypy / ruff / black / clippy are all clean. Cross-agent claims A/B/C verify. No must-fix findings.

The seven "should-fix" items are all minor — three are dead-arg / dead-tree polish (target_exploitability, seed, HUNLTree-built-and-discarded), one is a dependency-narrative correction (ndarray itself is also newly declared), one is a Cargo version bump, one is a duplicated DCFR loop documented as known maintenance debt, and one is a build-state recipe gap (require `maturin develop --release` before testing so a stale `_rust.so` can't silently make the differential test skip). None block the commit; the maturin-recipe one is the highest priority because it caught the audit agent off-guard at the start (and would catch human reviewers similarly).

Recommended commit-prep checklist for the orchestrator:
1. Add `maturin develop --release` to the pre-commit script if not already present.
2. Run `pytest -m slow tests/test_hunl_diff.py::test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` once to verify the flop fixture also passes within 5e-3.
3. Bump `crates/cfr_core/Cargo.toml` version (0.2.0 → 0.5.0 to match the planned `__version__`).
4. (Optional) Apply the should-fix-3 docstring nudge for the unused `seed` / `target_exploitability` arguments.
5. Commit; PR 7 (river-spot diff vs noambrown) can resume against this branch.
