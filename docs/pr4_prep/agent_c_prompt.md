# PR 4 Agent C — tests (written from spec alone)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 4 Agent C.**
**Your scope:** write the three test files (`test_abstraction_emd.py`, `test_abstraction_buckets.py`, `test_abstraction_integration.py`) for PR 4's card abstraction pipeline, working strictly from the spec without seeing Agent A or Agent B's implementations.
**Your contract:** ~34 tests across the three files matching the spec §8 Agent C deliverables; tests written against the public API in `poker_solver/abstraction/` (and the `HUNLConfig.abstraction` field on `poker_solver/hunl.py`); ambiguities surfaced as test failures that round-trip to spec edits, NOT silently smoothed over.
**Your success criteria:** ruff clean, black clean on new test files; all tests are SELF-CONTAINED; the test files are write-only — you must NOT modify any non-test file; spec-ambiguity findings reported as written notes, not as test tweaks.
**File ownership:** you own `tests/test_abstraction_emd.py`, `tests/test_abstraction_buckets.py`, `tests/test_abstraction_integration.py`. You may NOT modify any other file.

---

## Strict file ownership

**You own (create new):**
- `/Users/ashen/Desktop/poker_solver/tests/test_abstraction_emd.py`
- `/Users/ashen/Desktop/poker_solver/tests/test_abstraction_buckets.py`
- `/Users/ashen/Desktop/poker_solver/tests/test_abstraction_integration.py`

**You must NOT touch:**
- Any non-test file (`poker_solver/abstraction/*.py`, `poker_solver/hunl.py`, `poker_solver/__init__.py`, `poker_solver/cli.py`, `pyproject.toml`, etc.) — Agent A and Agent B
- Any existing test file (`tests/test_*.py`) — these test PR 1/2/3/3.5 and must remain unchanged
- The spec itself (`docs/pr4_prep/pr4_spec.md`) — read-only; if the spec is ambiguous, flag it in your report; the orchestrator (not you) updates the spec

**Critical:** you are writing the tests from the **spec alone**. Do NOT read `poker_solver/abstraction/equity_features.py`, `emd_clustering.py`, `buckets.py`, or `precompute.py` even after Agents A/B land. The dividend of the fan-out pattern is that your tests independently encode the spec — if your tests fail against the impl, it's a real bug OR a real spec ambiguity, and the orchestrator resolves it. Reading the impl would defeat this dividend.

(Exception: if a test fails due to an obvious typo in YOUR test code, you may inspect the impl to figure out the typo. But you do not adjust tests to match impl behavior — only to fix your own bug.)

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`. Internalize ENTIRE spec, but especially §3 (architecture), §4 (Stages 1-5), §5 (file structure), §6 (modifications to existing files), §7 (design decisions), §8 Agent C deliverables (your test plan), §11 (success criteria).
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Card abstraction defaults (256/128/64), stack-depth tiers.
3. **The autonomous log (D1/D2 LOCKED):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. D1 = suit-iso INCLUDED in PR 4, D2 = Monte Carlo at 200K iter.
4. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially B1, B2 (the `source_path` field; the metadata-dict-on-load behavior).
5. **PR 3 test patterns (style guide):** `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — function-level tests, `pytest.approx` for floats, no test classes, parametrize only when meaningful. Mirror this style.
6. **PR 3.5 test patterns:** `/Users/ashen/Desktop/poker_solver/tests/test_pushfold.py` if present — for examples of how to test cached / data-loading modules.
7. **HUNL test fixtures:** `/Users/ashen/Desktop/poker_solver/tests/test_hunl_tree.py` — for the tiny-subgame integration test pattern.

## Public API you test (from spec §8)

### Agent A produces (in `poker_solver.abstraction.equity_features` + `poker_solver.abstraction.emd_clustering`):

```python
def equity_distribution(board, hole_cards, street, H=50, mode="mc",
                        mc_iterations=200_000, rng=None) -> np.ndarray: ...

def compute_river_features(boards, hands_per_board, H=50, mode="mc",
                           mc_iterations=200_000, seed=42, progress=False) -> np.ndarray: ...

def compute_turn_features(...) -> np.ndarray: ...
def compute_flop_features(...) -> np.ndarray: ...

def canonicalize_for_suit_iso(board, hand) -> tuple[str, int]:
    """Returns (canonical_board_key, suit_permutation_index)."""

def emd_1d(p, q) -> float: ...
def batch_emd(points, centroids) -> np.ndarray: ...

@dataclass
class KMeansResult:
    assignments: np.ndarray
    centroids: np.ndarray
    history: list[float]

def kmeans_emd(features, K, seed=42, max_iter=200,
               change_tolerance=0.001) -> KMeansResult: ...
```

### Agent B produces (in `poker_solver.abstraction.buckets` + `poker_solver.abstraction.precompute`):

```python
@dataclass(frozen=True)
class AbstractionTables:
    flop_assignments: np.ndarray
    turn_assignments: np.ndarray
    river_assignments: np.ndarray
    flop_board_index: dict[str, int]
    turn_board_index: dict[str, int]
    river_board_index: dict[str, int]
    flop_hand_index: dict[str, dict[str, int]]
    turn_hand_index: dict[str, dict[str, int]]
    river_hand_index: dict[str, dict[str, int]]
    metadata: dict[str, object]
    source_path: Path | None = None  # B2 amendment

def lookup_bucket(tables, board, hole_cards, street) -> int: ...
def save_abstraction(tables, path) -> None: ...
def load_abstraction(path) -> AbstractionTables: ...

def build_abstraction(out_path, bucket_counts=(256, 128, 64), seed=42, H=50,
                     max_iter=200, streets=(FLOP, TURN, RIVER),
                     flop_mode="mc", mc_iterations=200_000,
                     progress=True, size_guard_gb=1.0) -> AbstractionTables: ...
```

### Agent B modifies (in `poker_solver.hunl`):

```python
@dataclass(frozen=True)
class HUNLConfig:
    # ... existing fields ...
    abstraction: AbstractionRef | None = None  # NEW (corrected: AbstractionRef not AbstractionTables — see pr4_spec.md §3.5)

# HUNLPoker.infoset_key(state, player):
#   - If cfg.abstraction is None: lossless format (PR 3 unchanged).
#   - If cfg.abstraction is not None AND state.street >= Street.FLOP:
#     returns f"b{bucket_id}|{street_token}|{betting_history}"
#   - Preflop ALWAYS uses lossless even with abstraction set.
```

### CLI subcommand:
```
poker-solver precompute-abstraction --output PATH [--bucket-counts X,Y,Z]
                                    [--feature-bins H] [--seed S] [--max-iter N]
                                    [--street {flop,turn,river,all}]
                                    [--flop-mode {exact,mc}]
                                    [--mc-iterations N]

poker-solver solve --game hunl --abstraction PATH ...
```

## Default decisions LOCKED (do not deviate)

These are the locked decisions from the PR 4 spec + the autonomous log. Your tests must encode these defaults:

- **D1 = SUIT-ISO INCLUDED.** Two suit-isomorphic boards (e.g., As-7c-2d and Ah-7d-2s) plus suit-permuted hands must produce the same bucket. Test this in `test_abstraction_buckets.py` and (more loosely) in the integration tests.
- **D2 = Monte Carlo at 200K iter.** `equity_distribution(..., mode="mc", mc_iterations=200_000, rng=rng)` is the production path. Tests use much smaller iteration counts for speed (e.g., `mc_iterations=1000` or `mc_iterations=100`), but verify the determinism contract: same `rng` state + same inputs → identical histogram.
- **Bucket counts: (256, 128, 64)** default. Tests use tiny counts (e.g., `(4, 2, 2)`) for speed; the default is verified in `test_build_abstraction_writes_file` (or similar).
- **Histogram resolution: H = 50** default.
- **`.npz` artifact format**, default filename `abstraction_v1.npz`.
- **Schema version 1.** Loader rejects schema mismatches with `ValueError`.
- **Preflop returns bucket id -1** unconditionally.
- **No new third-party deps.** Your tests import only from `numpy`, `pytest`, `poker_solver.*`, and stdlib. No scikit-learn, no scipy.

## Tests to write (per spec §8 Agent C deliverables)

### `tests/test_abstraction_emd.py` (~12 tests)

Tests for EMD math + k-means. Use synthetic histogram data (NumPy arrays); no poker domain needed.

1. **`test_emd_zero_for_identical_histograms`** — `emd_1d(p, p) == 0.0` for several random histograms.
2. **`test_emd_one_for_opposite_extremes`** — `emd_1d(delta_at_0, delta_at_H-1)` is approximately `(H-1)/H`. For H=50: ≈ 0.98. (The spec test plan says "≈ 1.0" but per the correct closed-form formula with `mean(|cumsum diff|)`, the answer is `(H-1)/H`. Use `pytest.approx((H-1)/H, abs=1e-6)`.)
3. **`test_emd_symmetric`** — `emd_1d(p, q) == emd_1d(q, p)` for several random pairs.
4. **`test_emd_triangle_inequality`** — for three random L1-normalized histograms p, q, r: `emd_1d(p, r) <= emd_1d(p, q) + emd_1d(q, r) + small_tol`. (Use `+ 1e-9` for numerical noise.)
5. **`test_batch_emd_matches_loop`** — for `points` shape `(20, 50)` and `centroids` shape `(4, 50)`, `batch_emd(points, centroids)[i, j]` matches `emd_1d(points[i], centroids[j])` for all i, j.
6. **`test_kmeans_separates_clearly_distinct_clusters`** — generate 4 well-separated synthetic histogram blobs (e.g., delta at bin 5, delta at bin 15, delta at bin 25, delta at bin 35, with small Gaussian noise on each). Run `kmeans_emd(features, K=4, seed=0)`. Assert each blob's points are assigned to a single cluster (homogeneity ≥ 0.95).
7. **`test_kmeans_reproducible_with_seed`** — two calls to `kmeans_emd(features, K=4, seed=42)` on the same features produce identical assignments (`np.array_equal`).
8. **`test_kmeans_converges_within_max_iter`** — on synthetic 4-blob data, the `history` is monotonically non-increasing (allowing 1e-9 tolerance for noise) and stabilizes before `max_iter`. The number of iterations recorded is < `max_iter`.
9. **`test_kmeans_handles_empty_cluster`** — construct features that, with a particular adversarial init, would produce an empty cluster on iter 1. The spec says kmeans recovers by re-seeding from the farthest point. Test that no cluster has 0 assignments after kmeans completes (assert `len(np.unique(result.assignments)) == K`).
10. **`test_kmeans_centroid_is_l1_normalized`** — every returned centroid sums to ~1.0 (`pytest.approx(1.0, abs=1e-5)`).
11. **`test_kmeans_assignments_in_range`** — every assignment in `[0, K)` for various K (e.g., K=2, 4, 8).
12. **`test_kmeans_plusplus_init_deterministic`** — same seed → same initial centroids. (Test by patching the rng OR by checking that two consecutive runs produce identical first-iteration history values, which depend only on init + first centroid update.)

### `tests/test_abstraction_buckets.py` (~14 tests)

Tests for canonicalization, lookup, and serialization round-trip. Some tests construct synthetic `AbstractionTables` directly; others run through `build_abstraction` with tiny configs.

1. **`test_canonical_board_id_suit_iso_collapses_isomorphic_boards`** — `canonicalize_for_suit_iso([As, 7c, 2d], (Kh, Qh))` and `canonicalize_for_suit_iso([Ah, 7d, 2s], (suit-permuted hand))` produce the same `canonical_board_key`. (Per D1: suit-iso INCLUDED.)
2. **`test_canonical_hand_key_sorts_input_within_board`** — for a fixed canonical board, `(Ah, Kh)` and `(Kh, Ah)` map to the same lookup position. (Hole-card pair is unordered.)
3. **`test_lookup_bucket_returns_minus_one_for_preflop`** — for any `AbstractionTables` (even a tiny synthetic one), `lookup_bucket(t, board=(), hand=(Card.from_str('As'), Card.from_str('Kh')), street=Street.PREFLOP) == -1`.
4. **`test_lookup_bucket_returns_in_range_for_postflop`** — for a tiny synthetic `AbstractionTables` with bucket_counts=(4, 2, 2), bucket id is in [0, 4) for flop, [0, 2) for turn, [0, 2) for river.
5. **`test_lookup_bucket_deterministic`** — same input → same output for 100 repeated calls.
6. **`test_save_load_round_trip`** — write a synthetic tables (built via tiny `build_abstraction` or constructed by hand), read it back, assert per-array equality (`np.array_equal`) and `metadata` deep-equal.
7. **`test_save_load_schema_version_check`** — write a synthetic tables; corrupt the `schema_version` field on disk (load the .npz, modify metadata, save back); load → `ValueError` with a message mentioning "schema". (Implementation hint: use `np.load(...)['metadata.npy']` style direct manipulation, or just write a small fake .npz with the wrong version and confirm load raises.)
8. **`test_save_load_source_path_populated_on_load`** — after `t = load_abstraction(Path('/tmp/x.npz'))`, `t.source_path == Path('/tmp/x.npz')`. After `build_abstraction(...)` directly, `t.source_path is None`. (Per B2 amendment.)
9. **`test_save_load_size_under_guard_rail`** — tiny config (bucket_counts=(4, 2, 2)) artifact is < 100 KB on disk.
10. **`test_lookup_bucket_raises_on_blocker`** — board includes one of hero's hole cards (e.g., `board=[As, 7c, 2d]`, `hand=(As, Kh)`); `lookup_bucket(...)` raises `ValueError` mentioning the conflict.
11. **`test_lookup_bucket_raises_on_wrong_board_size`** — board has 4 cards (turn shape) but caller passes `street=Street.FLOP`; raises `ValueError`.
12. **`test_abstraction_tables_metadata_includes_required_fields`** — after `build_abstraction(tiny_config)`, the saved tables' metadata contains: `schema_version` (==1), `bucket_counts`, `feature_bins`, `seed`, `build_timestamp`, `build_duration_sec`, `lossless_streets` (== []), `flop_mode`, `mc_iterations`.
13. **`test_canonical_hand_key_in_range_for_random_inputs`** — for 100 randomly-generated (board, hand) pairs on random canonical flops, the resulting (canonical_board_key, canonical_hand_key) tuple is unique-per-strategically-distinct-hand. (Loose test: just assert the function doesn't crash and returns well-typed output.)
14. **`test_build_abstraction_writes_file_with_correct_shape`** — `build_abstraction(out_path='/tmp/test.npz', bucket_counts=(4, 2, 2), H=10, streets=[Street.RIVER], mc_iterations=100, seed=0)` produces a valid `.npz`; `load_abstraction` reads it back; `river_assignments.dtype == np.uint8`; `len(np.unique(river_assignments)) <= 2` (river K=2).

### `tests/test_abstraction_integration.py` (~8 tests)

End-to-end tests: build → save → load → use through `HUNLPoker.infoset_key`. Tiny configs throughout — these must run in under 60 seconds total.

1. **`test_pr3_tiny_subgame_still_passes_without_abstraction`** — re-run PR 3's `default_tiny_subgame()` configuration with `HUNLConfig(abstraction=None)` (the default). Run DCFR for 100 iterations via `solve(...)`. Assert: (a) no crash, (b) `result.exploitability_history[-1]` is finite, (c) every infoset key in `result.average_strategy.keys()` matches the lossless format (contains a `|` and a card-string segment matching `r'^[2-9TJQKA][shdc]?'`).
2. **`test_tiny_subgame_with_abstraction_produces_bucketed_infosets`** — build a tiny abstraction (`bucket_counts=(4, 2, 2)`, river-only, `mc_iterations=100`), save it via `save_abstraction(tables, path)`, then construct an `AbstractionRef(source_path=str(path), version="test-v1")` (per pr4_spec.md §3.5 — `HUNLConfig.abstraction` field type is `AbstractionRef | None`, NOT `AbstractionTables`). Override `HUNLConfig(..., abstraction=ref)`. Solve. Assert: every infoset key starts with `b<digit>|` (bucketed form), NOT with a card string.
3. **`test_abstraction_collapses_strategically_similar_hands`** (soft) — construct two hands on a dry board with similar equity distributions (e.g., AhKh and AhQh on As7c2d board); after building with K=4 buckets on the flop, assert they end up in the same bucket. (Spec §8 marks this soft — if it fails, comment it as `pytest.mark.xfail(reason="soft sanity check; abstraction quality varies")`.)
4. **`test_end_to_end_build_loadback_solve`** — build a tiny abstraction; save; load; attach to a HUNL config; run `solve(...)` for 100 iterations; assert no crash + finite exploitability.
5. **`test_abstraction_lookup_speed_under_1us`** — measure: 1000 `lookup_bucket(...)` calls in under 5ms (i.e., O(1) lookup, allowing generous margin for Python overhead). Use `time.perf_counter()`.
6. **`test_build_abstraction_seed_reproducibility`** — `build_abstraction(out_path1, seed=42, ...)` and `build_abstraction(out_path2, seed=42, ...)` (same other args) produce artifacts that load to byte-identical `AbstractionTables` (`np.array_equal` on all arrays, deep-equal on metadata EXCEPT `build_timestamp` and `build_duration_sec` which are wall-clock-dependent and excluded from the comparison).
7. **`test_cli_precompute_abstraction_smoke`** — invoke the CLI via `subprocess.run(['poker-solver', 'precompute-abstraction', '--output', '/tmp/test.npz', '--bucket-counts', '4,2,2', '--feature-bins', '10', '--street', 'river', '--mc-iterations', '100', '--seed', '0'])`. Assert exit code 0, file exists, schema_version == 1, river bucket count == 2.
8. **`test_cli_solve_with_abstraction_loads_file`** — `subprocess.run(['poker-solver', 'solve', '--game', 'hunl', '--hunl-mode', 'tiny_subgame', '--abstraction', '/tmp/test.npz', '--iterations', '50'])`. Assert exit code 0, output contains "Game value" (proxy for "ran to completion").

## Critical correctness items in your tests

### 1. Test the spec, not the implementation

If the spec says "bucket id in [0, 256)", your test asserts `0 <= bucket_id < 256`, NOT `bucket_id < t.bucket_counts[0]` (which depends on impl behavior). Encode the spec invariant directly.

### 2. Tiny configs everywhere

Full PR 4 build is multi-hour. Your tests use:
- `bucket_counts=(4, 2, 2)` or smaller.
- `H=10` (not 50).
- `mc_iterations=100` or `1000` (not 200_000).
- `--street river` only when possible (river is fastest).
- `seed=0` or fixed small int for reproducibility.

Total test suite wall-clock target: < 60 seconds.

### 3. Determinism testing

For any function with a `seed` or `rng` parameter, write a test that calls it twice with the same seed and asserts identical output. This is the load-bearing reproducibility check.

### 4. Spec-ambiguity flagging

If you find that the spec is ambiguous about an expected behavior (e.g., "should `lookup_bucket(t, board with wrong card count, ...)` raise `ValueError` or `KeyError`?"), write the test for the version that seems most consistent with the spec's other language. Then, in your final report, list the ambiguity and how you resolved it. **Do NOT silently weaken the test to "pass either way."** The orchestrator will adjudicate.

### 5. Spec test plan ≠ your final test list

The spec §8 lists ~34 tests. Use it as your target. If you spot a missing test (e.g., a critical invariant the spec doesn't enumerate), ADD it — but tag it in code as `# additional: this is not in spec §8 but covers <invariant>`. If a spec test seems impossible to write as-described (e.g., it depends on a function that doesn't exist), flag it in your report and skip it.

### 6. Style: match PR 3 test style

- Function-level tests, no classes.
- `pytest.approx` for float comparisons.
- `pytest.raises(ValueError, match="...")` for expected exceptions.
- One assertion per test where practical; document multi-assert tests with a comment.
- No `pytest.fixture` unless multiple tests share the same expensive setup (e.g., building a tiny abstraction once and reusing across `test_abstraction_integration.py`).
- Imports at the top of the file; no inline imports.
- Module-level docstring describing what the file tests.

## License-aware sourcing

Your tests are entirely first-party code; no license attribution needed. You may NOT copy test patterns or fixtures from AGPL repos (`postflop-solver`, `TexasSolver`); MIT/Apache repos (`slumbot2019`, `noambrown_poker_solver`, `open_spiel`) are OK to architecturally inspire but not code-copy.

If you copy a test pattern non-trivially (>~5 LOC) from an MIT source, add an attribution comment. Otherwise, write tests from scratch against the spec.

## Quality bar

- **ruff clean:** `ruff check tests/test_abstraction_emd.py tests/test_abstraction_buckets.py tests/test_abstraction_integration.py` reports zero issues.
- **black clean:** `black --check tests/test_abstraction_emd.py tests/test_abstraction_buckets.py tests/test_abstraction_integration.py` reports no changes.
- **Tests use the public API only.** Imports: `from poker_solver import ...` or `from poker_solver.abstraction import ...`. Do NOT import from internal modules like `poker_solver.abstraction.equity_features` or `poker_solver.abstraction.buckets` directly (the `__init__.py` re-exports everything needed).
- **Tests are self-contained.** No reading of fixtures from `tests/data/` unless you create that data inline; no network access; no requiring the abstraction artifact to be pre-built.
- **No test exceeds 5 seconds wall-clock.** If a test is slow, reduce `iterations` / `mc_iterations` / `bucket_counts`.
- **All 138 existing tests must still pass.** Your tests are purely additive; ensure no test ID collision with existing tests.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_abstraction_emd.py tests/test_abstraction_buckets.py tests/test_abstraction_integration.py
black --check tests/test_abstraction_emd.py tests/test_abstraction_buckets.py tests/test_abstraction_integration.py

# 2. Test count + collection (your tests must collect without import errors)
pytest --collect-only tests/test_abstraction_emd.py tests/test_abstraction_buckets.py tests/test_abstraction_integration.py 2>&1 | tail -10

# Expected: ~34 tests collected (12 + 14 + 8 per spec §8).
# If <30 or >40, justify in your report.

# 3. Run YOUR tests (against Agent A + Agent B's implementations after they land).
# These commands may FAIL if Agent A or Agent B haven't finished yet.
pytest -x tests/test_abstraction_emd.py 2>&1 | tail -30
pytest -x tests/test_abstraction_buckets.py 2>&1 | tail -30
pytest -x tests/test_abstraction_integration.py 2>&1 | tail -30

# 4. Full test suite (your tests + all 138 existing tests).
pytest -x 2>&1 | tail -20
# Expected: 138 existing + ~34 new = ~172 tests pass.

# 5. If any test fails: classify it.
#    a) typo in your test code → fix the typo
#    b) spec ambiguity → leave the test, document in report
#    c) genuine bug in Agent A or Agent B → leave the test, document in report
# Do NOT silently weaken tests to pass.
```

If your tests cannot be collected (import errors), that's a "tests broken" bug to fix in your code BEFORE reporting done. If your tests collect but fail because Agent A or Agent B has a bug, that's a finding to report — not a test to weaken.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created + test counts per file + total LOC.
2. Tests that PASS against Agents A+B's implementations (count).
3. Tests that FAIL — classified as: (a) test bug (you fixed it), (b) spec ambiguity (flag for human), (c) impl bug (flag for human).
4. Any spec ambiguity you couldn't resolve from the spec / PLAN / autonomous log.
5. Tests you added beyond the spec §8 list (justify each).
6. Tests from the spec §8 list you couldn't write (justify each).
7. Open questions for human review.
