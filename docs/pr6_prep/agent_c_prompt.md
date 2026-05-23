# PR 6 Agent C — differential tests (Python ↔ Rust) + Rust-only correctness

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 6 Agent C.**
**Your scope:** the differential test that gates PR 6 — Python tier (PR 5) vs Rust tier (Agents A + B) must produce strategies that match per-infoset-per-action within `1e-3` on a river-only subgame and `5e-3` on a tiny-abstraction flop subgame, plus a focused suite of Rust-only correctness tests for bucket-roundtrip, infoset-key parity, integer-cent chip arithmetic, and evaluator parity.
**Your contract:** ship `tests/test_hunl_diff.py` (~8 Python tests crossing the PyO3 boundary) and `crates/cfr_core/tests/test_hunl_rust.rs` (~12 Rust unit/integration tests including 10K-input bucket-roundtrip + canonicalization + Strength ordering parity). You test ONLY against the public API surfaces spec'd in §4.1–§4.5 of the PR 6 spec; the spec is the source of truth — when implementation and test disagree, update the spec (via the orchestrator) or update the implementation, never silently tweak the test.
**Your success criteria:** `pytest tests/test_hunl_diff.py -x` passes; `cargo test --package cfr_core test_hunl_rust` passes; `ruff` / `black` / `mypy --strict` clean on `tests/test_hunl_diff.py`; ALL 138+ existing tests still pass.
**File ownership:** you own ONLY `tests/test_hunl_diff.py` and `crates/cfr_core/tests/test_hunl_rust.rs`. You may NOT modify any non-test file.

---

## Strict file ownership

PR 6 depends on **PR 4** (the `.npz` bucket file format Agent B's Rust loader consumes) and **PR 5** (the Python orchestration baseline that Agent B's Rust port mirrors). Both have landed.

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_diff.py` (new file)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/tests/test_hunl_rust.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/tests/fixtures/hunl_diff_fixtures.py` (optional — if you need to share fixtures between tests; check if a sibling fixture file already exists from PR 5)

**You must NOT touch:**
- Any Rust source file under `crates/cfr_core/src/` — Agents A + B own these.
- Any Python source file under `poker_solver/` — Agents A + B own modifications; you only consume.
- `crates/cfr_core/Cargo.toml` — Agent B owns. (You may add `dev-dependencies` if needed — confirm with orchestrator if a new dev-dep is required; default is no new dev-deps.)
- Any other test file (`tests/test_*.py`, `crates/cfr_core/tests/*.rs`) — frozen for PR 6; respect existing test scopes.

If you discover a contract gap mid-implementation (e.g., your test surfaces a genuine spec ambiguity), **the spec is the source of truth.** Flag the gap to the orchestrator; do NOT silently tweak the test to pass. The same rule from PR 3/4/5 applies: we update the impl or update the spec, not the test.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md`. Internalize §7 (differential test scope — your primary reference), §7.1 (Test 1: river subgame at 1e-3; Test 2: flop fixture at 5e-3; Test 3: Rust-only checks), §7.3 (tolerance rationale), §8.3 (your deliverables — 8 Python tests + 12 Rust tests), §9 (critical correctness items — your tests verify these), §10 (risks — especially tolerance choice).
2. **Spec consistency review (cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially I3 (the 1e-3 / 5e-3 cluster is canonical across PR 6/7/8/9), B1 + B2 (the abstraction-loader seam that your `test_abstraction_canonicalization_matches_python` validates).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 architecture (Python is ground truth, Rust is the production port) and §6 License audit (no AGPL in tests either).
4. **PR 5 Python baseline (what you diff against):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` — `solve_hunl_postflop` (Python tier).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `default_tiny_subgame()`, `HUNLPoker`, `HUNLConfig`, `_serialize_hunl_config` (Agent B's helper).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` — `lookup_bucket`, `_canonical_board_id`, `_canonical_hand_key` (your Rust-side test verifies the canonicalization matches byte-for-byte).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/precompute.py` — `tiny_synthetic_abstraction()` if PR 4 ships one for tests; otherwise build a tiny abstraction in `conftest.py` style.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/evaluator.py` — Python's evaluator (your Rust-side `Strength` parity test crosses the PyO3 boundary to this).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `solve(game, backend="python")` and `solve(game, backend="rust")` paths.
5. **Existing test patterns:**
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py` — Kuhn/Leduc differential test pattern. PR 6 extends this pattern to HUNL (with looser tolerance due to scale).
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — PR 3's HUNL state tests. Pattern reference for testing game-state semantics.
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_postflop_solve.py` — PR 5's HUNL postflop solve tests. Pattern reference for end-to-end fixtures.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/tests/` — existing Rust integration tests (if any). Pattern reference for `cargo test`.
6. **PyO3 surface (Agent B's contract):**
   - `poker_solver._rust.solve_hunl_postflop(config_json, abstraction_path, iterations, alpha, beta, gamma, target_exploitability, seed) -> dict` — see §"Public API contract" in Agent B's prompt.
7. **MIT/Apache references** (read-only):
   - `references/code/noambrown_poker_solver/` (MIT) — pattern reference; not needed for your tests.
   - `references/code/postflop-solver/`, `references/code/TexasSolver/` — **AGPL.** Do not study; do not import test patterns from these repos.

## Default decisions LOCKED (do not deviate)

The locked defaults that touch your scope (from PR 6 spec §11 and the consistency review):

- **D7 — Diff-test tolerance: 1e-3 (river-only fixture), 5e-3 (flop fixture).** These are CANONICAL across PR 6/7/8 per consistency-review I3. Use them exactly. Use `rel_tol = max(abs_tol, expected * rel_tol_factor)` semantics if you compare floats with relative tolerance; spec uses an absolute floor of 1e-6 on tiny probabilities to avoid divide-by-zero.
- **D10 — Default backend: `python`.** Your diff tests explicitly pass `backend="rust"` for the Rust path and `backend="python"` (or no arg) for the Python path. Do not assume the default has flipped.
- **D8 — HashMap nondeterminism is bounded.** Strategies converge to the same Nash distribution regardless of HashMap iteration order. Same seed + config + abstraction → same Rust strategy (deterministic test via `test_hunl_rust_deterministic_with_seed`); cross-tier strategies differ at the 1e-3 level due to float-reduction-tree ordering, NOT a bug.
- **D5 — Python recomputes exploitability + game_value.** When you call `solve(game, backend="rust")`, the returned `SolveResult.exploitability_history[-1]` is Python's recomputation of exploitability from the Rust strategy, NOT a Rust-side value. Same for `game_value`. Your tests assert on these recomputed values.

## Test specification (lock these test names — Agent B's CI may grep for them)

### `tests/test_hunl_diff.py` — ~8 Python tests

```python
"""HUNL Python ↔ Rust differential tests (PR 6).

Verifies that the Rust port (Agents A + B) produces strategies, infoset keys,
and bucket lookups byte-or-strategy-equivalent to the Python tier (PR 5).
Tolerance: 1e-3 per-action on the river-only subgame, 5e-3 on the flop fixture
(locked per consistency-review I3 + PR 6 spec §7.3).

The spec is the source of truth. If a test surfaces a genuine spec ambiguity,
flag the orchestrator; do NOT silently tweak the tolerance.
"""

import pytest
from poker_solver._rust import solve_hunl_postflop as _rust_solve_hunl
from poker_solver.hunl import (
    HUNLConfig, HUNLPoker, Street, default_tiny_subgame, _serialize_hunl_config,
)
from poker_solver.solver import solve


def test_hunl_river_subgame_diff_python_vs_rust():
    """River-only subgame: AhKc vs QdQh on As7c2dKh5s, SPR 1, full menu.
    1000 iterations on both tiers; per-infoset-per-action diff <= 1e-3
    (with abs floor 1e-6).
    """
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    py_result = solve(game, iterations=1000, backend="python", seed=42)
    rs_result = solve(game, iterations=1000, backend="rust", seed=42)
    # Compare per-infoset-per-action probabilities
    assert set(py_result.average_strategy.keys()) == set(rs_result.average_strategy.keys()), (
        "infoset key sets diverge between tiers"
    )
    for key, py_probs in py_result.average_strategy.items():
        rs_probs = rs_result.average_strategy[key]
        assert len(py_probs) == len(rs_probs)
        for i, (p, r) in enumerate(zip(py_probs, rs_probs)):
            tol = max(1e-6, 1e-3 * max(abs(p), abs(r)))
            assert abs(p - r) <= tol, (
                f"divergence at {key}[{i}]: py={p:.6f} rs={r:.6f} tol={tol:.6f}"
            )


def test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction():
    """Flop dry As7c2d, 100 BB, 3 bet sizes [33%, 75%, 200%], 3-cap.
    PR 4's tiny_synthetic_abstraction() with bucket_counts=(4, 2, 2).
    200 iterations; per-infoset-per-action diff <= 5e-3.
    Marked slow: this is the longer-running test (~5 min Python, ~30s Rust).
    """
    # ... build config from PR 5 fixture 2 setup
    # ... call solve(backend="python") and solve(backend="rust")
    # ... assert per-action diff <= 5e-3
    pytest.skip("PR 5 fixture 2 setup; requires tiny_synthetic_abstraction()")


def test_hunl_rust_validates_postflop_only():
    """Passing a preflop config raises NotImplementedError (mirroring Python)."""
    config = HUNLConfig(starting_street=Street.PREFLOP)  # ... fill required fields
    game = HUNLPoker(config)
    with pytest.raises(NotImplementedError, match=r"PR 9"):
        solve(game, iterations=10, backend="rust")


def test_hunl_rust_validates_board_length():
    """4-card board with starting_street=Street.FLOP raises clear error."""
    config = HUNLConfig(
        starting_street=Street.FLOP,
        initial_board=[/* 4 cards, mismatched */],
        # ... fill required fields
    )
    game = HUNLPoker(config)
    with pytest.raises((ValueError, RuntimeError), match=r"board"):
        solve(game, iterations=10, backend="rust")


def test_hunl_rust_strategy_sums_to_one():
    """Every infoset's returned probs sum to 1.0 +/- 1e-9."""
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    result = solve(game, iterations=100, backend="rust", seed=42)
    for key, probs in result.average_strategy.items():
        assert abs(sum(probs) - 1.0) < 1e-9, (
            f"{key}: probs={probs} sum={sum(probs)}"
        )
        assert all(0.0 <= p <= 1.0 for p in probs), f"{key}: probs out of range"
        import math
        assert not any(math.isnan(p) or math.isinf(p) for p in probs)


def test_hunl_rust_deterministic_with_seed():
    """Same seed + config -> identical strategy bytewise."""
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    r1 = solve(game, iterations=100, backend="rust", seed=42)
    r2 = solve(game, iterations=100, backend="rust", seed=42)
    assert r1.average_strategy.keys() == r2.average_strategy.keys()
    for key in r1.average_strategy:
        assert r1.average_strategy[key] == r2.average_strategy[key], (
            f"nondeterminism at {key}"
        )


def test_hunl_rust_exploitability_matches_python_recompute():
    """Python recomputes exploitability from the Rust strategy (D5 lock).
    The recomputed value should match solve(backend='python') within 1e-2
    after enough iterations.
    """
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    py = solve(game, iterations=1000, backend="python", seed=42)
    rs = solve(game, iterations=1000, backend="rust", seed=42)
    assert rs.exploitability_history, "Rust path should populate exploitability_history"
    assert rs.exploitability_history[-1] >= 0.0, "exploitability non-negative"
    # Python recomputation of Rust strategy ≈ Python's own exploitability
    assert abs(rs.exploitability_history[-1] - py.exploitability_history[-1]) <= 1e-2


def test_hunl_rust_action_ids_match_python_constants():
    """Rust ACTION_FOLD..ACTION_ALL_IN integer constants match Python."""
    from poker_solver import action_abstraction as aa
    # Rust constants are not directly exposed via PyO3 in PR 6;
    # this test verifies by indirect means: invoke a known legal action
    # sequence and confirm the same ACTION_* IDs round-trip through the
    # JSON config + Rust solve + returned strategy keys.
    # The infoset_key format is the proxy: if the betting_history token
    # in the Rust-returned infoset keys matches Python's, the action IDs match.
    config = default_tiny_subgame()
    game = HUNLPoker(config)
    py = solve(game, iterations=100, backend="python", seed=42)
    rs = solve(game, iterations=100, backend="rust", seed=42)
    # Infoset key parity:
    assert set(py.average_strategy.keys()) == set(rs.average_strategy.keys()), (
        "action-ID drift: infoset key sets differ (likely betting_history token mismatch)"
    )
```

### `crates/cfr_core/tests/test_hunl_rust.rs` — ~12 Rust tests

```rust
//! HUNL Rust-only correctness tests (PR 6).
//!
//! Verifies game-state semantics, bucket-roundtrip parity (byte-for-byte
//! against Python via PyO3 introspection), evaluator parity, and end-to-end
//! solve smoke tests. Bucket-roundtrip test runs 10K random inputs to catch
//! canonicalization drift early.

use cfr_core::hunl::{HUNLState, HUNLConfig, Street};
use cfr_core::hunl_tree::HUNLTree;
use cfr_core::hunl_eval::Strength;
use cfr_core::abstraction::{load_abstraction, lookup_bucket, AbstractionTables};
use std::sync::Arc;

#[test]
fn test_hunl_initial_state_blinds_posted_correctly() {
    // Construct config with 100 BB stacks, post blinds, assert contribs.
    // ...
}

#[test]
fn test_hunl_legal_actions_at_river_subgame_root() {
    // Build river subgame state; assert legal_actions() matches the expected
    // list from Python (call out via PyO3 inside the test or hard-code the
    // expected list per PR 5 fixture 1).
    // ...
}

#[test]
fn test_hunl_apply_advances_state_correctly() {
    // Manual action sequence (e.g., check, bet, fold), assert terminal
    // utility matches Python (hard-coded from PR 5 fixture).
    // ...
}

#[test]
fn test_hunl_infoset_key_lossless_format() {
    // 100 random states; for each, call HUNLState::infoset_key(player, None)
    // and assert byte-for-byte parity with Python's lossless format.
    // Implementation: spawn pyo3 inside the test with `Python::with_gil`,
    // call into the Python tier's HUNLPoker.infoset_key.
    // ...
}

#[test]
fn test_hunl_infoset_key_bucketed_format() {
    // 100 random (state, abstraction) pairs; same approach as above but
    // with a tiny synthetic abstraction loaded.
    // ...
}

#[test]
fn test_abstraction_canonicalization_matches_python() {
    // 10K random (board, hole) inputs across all 3 streets; assert
    // _canonical_board_id + _canonical_hand_key match Python's byte-for-byte.
    // This is the SINGLE MOST FRAGILE cross-tier seam per spec §9 #2.
    // ...
}

#[test]
fn test_abstraction_lookup_bucket_matches_python() {
    // 10K random inputs return identical bucket IDs to Python's lookup_bucket.
    // ...
}

#[test]
fn test_hunl_tree_build_terminates() {
    // For the river subgame, HUNLTree::build returns a finite tree with
    // expected node count (loose bounds matching PR 3's tree-size estimate).
    // ...
}

#[test]
fn test_hunl_strength_eval_matches_python() {
    // 1000 random 7-card hands; for each pair (hand_a, hand_b), assert
    // (Strength::evaluate_7(hand_a) > Strength::evaluate_7(hand_b))
    // matches Python's (eval.evaluate(hand_a) > eval.evaluate(hand_b)).
    // ORDERING parity, not exact integer parity (Python and Rust may use
    // different rank encodings).
    // ...
}

#[test]
fn test_hunl_strength_eval_handles_ties() {
    // Known tied 5-card hands → equal Strength values. Verify tie path is
    // hit in HUNLState::utility (returns [0.0, 0.0] for showdown ties).
    // ...
}

#[test]
fn test_hunl_solve_river_subgame_smoke() {
    // Calls solve_hunl_postflop for 100 iterations on the river subgame;
    // returns non-empty strategy. Smoke test, not a correctness gate.
    // ...
}

#[test]
fn test_hunl_solve_reject_preflop() {
    // Passing a preflop config returns Err(HUNLSolveError::PreflopNotSupported).
    // ...
}

#[test]
fn test_hunl_solve_reject_rake_nonzero() {
    // Passing a config with rake_rate != 0 or rake_cap != 0 returns
    // Err(HUNLSolveError::RakeNonZero). Mirrors Python's assertion.
    // ...
}
```

## Critical correctness items (your tests verify these)

### 1. Tolerance is **lower-bound, not target** (D7)

`1e-3` (river) and `5e-3` (flop tiny abstraction) are the **maximum allowed** divergence. If your test passes at `1e-4`, great — but the assertion threshold is `1e-3`. If you observe divergence > `1e-3` on the river subgame, **do NOT loosen the tolerance.** Flag the orchestrator; the diff is real and the implementation is broken.

The rationale (spec §7.3):
- 1e-6 would require lock-stepping HashMap iteration order + identical float-reduction trees across tiers. Achievable but costs perf; punted to PR 8.
- 1e-3 is "strategy-behaviorally indistinguishable for poker purposes" — a 0.1% mix difference between two actions has no exploitable consequence at typical CFR convergence.
- 1e-2 is too loose; convergence still has ~1% noise at this level.

### 2. Bucket-roundtrip test is the canary

`test_abstraction_canonicalization_matches_python` + `test_abstraction_lookup_bucket_matches_python` run **10K random inputs each**. This catches any drift in the un-nesting of PR 4's `metadata` dict (B1 resolution), in the canonicalization sort orders, in the suit-isomorphism reduction, or in the bucket-index packing. If either fails, the diff tests downstream will also fail; fix the loader first.

**Generate inputs:**
- Random board: choose 3/4/5 cards uniformly from the 52-card deck without replacement.
- Random hole: choose 2 cards uniformly from the remaining 50/49/48 cards.
- Street: matches board length (3 → Flop, 4 → Turn, 5 → River).
- RNG: `seed = 42` deterministic (so failures are reproducible).

### 3. Infoset key byte-for-byte parity (lossless + bucketed)

`test_hunl_infoset_key_lossless_format` and `_bucketed_format`: 100 random states each.

**How to cross the tier boundary in a Rust test:**
- Use `pyo3::Python::with_gil` inside `#[test]` to invoke Python's `HUNLPoker.infoset_key(state, player)`.
- Construct the Rust `HUNLState` with the same hole cards / board / history.
- Compare the two strings with `assert_eq!`.

**What can drift:**
- Card sort order in the hole/board portions.
- Bet-amount formatting (leading zeros, trailing decimals).
- Bucket ID stringification.
- The street_token (does Python use "flop" or "FLOP" or `Street.FLOP.name.lower()`?).
- The separator character between segments.

If your test fails, isolate which substring drifts and report to the orchestrator.

### 4. Evaluator ORDERING parity (not integer parity)

`test_hunl_strength_eval_matches_python` compares **orderings**, not integer values. Python and Rust may use different rank encodings; what matters is `(hand_a > hand_b)` in Rust matches `(python_a > python_b)`.

```rust
for _ in 0..1000 {
    let (h_a, h_b) = random_pair_of_seven_card_hands(&mut rng);
    let rs_cmp = Strength::evaluate_7(&h_a).cmp(&Strength::evaluate_7(&h_b));
    let py_cmp = python_evaluate_compare(&h_a, &h_b);  // via PyO3
    assert_eq!(rs_cmp, py_cmp, "ordering drift on {h_a:?} vs {h_b:?}");
}
```

### 5. Determinism gate

`test_hunl_rust_deterministic_with_seed`: same `(config_json, abstraction_path, seed)` → byte-identical strategy. Tests Agent B's `seed` parameter passes through, and tests Agent B's HashMap hasher is locked under `#[cfg(test)]` (D8). If this fails, the test infrastructure has a HashMap-seed leak.

### 6. Existing 138+ tests must still pass

Your edits are purely additive. **Do NOT modify** any existing test file. After your test files land, run `pytest -x` and `cargo test --all`; both must pass clean. Existing Kuhn/Leduc differential tests (`tests/test_dcfr_diff.py`) MUST be untouched.

### 7. License-aware test infrastructure

Your tests may use:
- Standard fixtures from `poker_solver/hunl.py` (`default_tiny_subgame`) — project-internal MIT.
- PR 4's `tiny_synthetic_abstraction()` if it exists — project-internal MIT.
- PyO3 for cross-tier introspection — already a dep.
- Standard `pytest` and `cargo test` machinery.

Your tests may NOT:
- Reference `postflop-solver`, `TexasSolver`, or `shark-2.0` patterns. Test patterns from these AGPL/unlicensed repos are off-limits.
- Add new third-party Python deps (`pyproject.toml` is Agent B's; no new test-only deps either).
- Add new Rust `dev-dependencies` to `Cargo.toml` — confirm with orchestrator if you absolutely need one. Default: no new dev-deps.

## Cross-agent contracts (consumed by your tests; do NOT depend on internals)

```python
# From poker_solver.hunl (Agent A + PR 3 + PR 4 + Agent B's edit):
class HUNLConfig: ...
class HUNLPoker: ...
class Street(IntEnum): PREFLOP, FLOP, TURN, RIVER, SHOWDOWN
def default_tiny_subgame() -> HUNLConfig: ...
def _serialize_hunl_config(config: HUNLConfig) -> str: ...   # Agent B's helper

# From poker_solver.solver:
def solve(game, iterations, backend="python", seed=None, ...) -> SolveResult:
    """backend='python' → PR 5 path; backend='rust' → PR 6 Rust path (Agent B's branch)."""

# From poker_solver._rust (Agent B's PyO3 surface):
def solve_hunl_postflop(
    config_json: str,
    abstraction_path: Optional[str],
    iterations: int,
    alpha: float, beta: float, gamma: float,
    target_exploitability: Optional[float],
    seed: Optional[int],
) -> dict:
    """Returns: {'average_strategy': dict, 'exploitability': float, ...}"""

# From poker_solver.abstraction.buckets (PR 4):
def lookup_bucket(tables, board, hole, street) -> int: ...
```

```rust
// From cfr_core::hunl, hunl_tree, hunl_eval (Agent A):
pub struct HUNLState { /* per spec §4.1 */ }
pub struct HUNLTree { pub fn build(...) -> Self }
pub struct Strength { pub fn evaluate_7(&[u8;7]) -> Self }

// From cfr_core::abstraction (Agent B) — per pr6_spec.md §4.4
// (post launch-readiness-v2 amendment, 2026-05-22):
//
// `AbstractionTables` holds per-street uint8 `*_assignments` arrays plus
// string-keyed indices (`HashMap<String, u32>` for `*_board_index`,
// `HashMap<String, HashMap<String, u32>>` for `*_hand_index`), all parsed
// from JSON-bytes blobs inside the .npz on load. Top-level scalars like
// `schema_version`, `bucket_counts`, `feature_bins`, `seed`, `version`
// live inside a typed `AbstractionMetadata` struct, NOT as separate fields.
// `source_path: PathBuf` is set by `load_abstraction(path)` at runtime;
// it is NOT persisted on disk. There is no `HandLookup` packed struct and
// no `Vec<u32>` board-offset arrays at the top level — the bucket-roundtrip
// test exercises this shape via `serde_json::from_slice` parity.
//
// Canonical Python entry is `resolve_abstraction_ref(ref)` — `@lru_cache(
// maxsize=4)` + version-checked. Never reach into `source_path` directly
// from Python; always go through the resolver.

pub struct AbstractionMetadata { /* schema_version, version, bucket_counts,
    feature_bins, seed, plus `#[serde(flatten)] extra: HashMap<...>` */ }

pub struct AbstractionTables {
    pub flop_assignments: Vec<u8>,
    pub turn_assignments: Vec<u8>,
    pub river_assignments: Vec<u8>,
    pub flop_board_index: HashMap<String, u32>,
    pub turn_board_index: HashMap<String, u32>,
    pub river_board_index: HashMap<String, u32>,
    pub flop_hand_index: HashMap<String, HashMap<String, u32>>,
    pub turn_hand_index: HashMap<String, HashMap<String, u32>>,
    pub river_hand_index: HashMap<String, HashMap<String, u32>>,
    pub metadata: AbstractionMetadata,
    pub source_path: PathBuf,
}

pub fn load_abstraction(path: &Path) -> Result<AbstractionTables, _>;
pub fn lookup_bucket(tables: &AbstractionTables, board: &[u8], hole: &[u8; 2], street: Street) -> i32;
// -1 for preflop / out-of-range; non-negative bucket ID otherwise.

// From cfr_core::hunl_solver (Agent B):
pub fn solve_hunl_postflop(config, abstraction, iterations, ...) -> Result<HUNLSolveOutput, _>;
```

If either Agent's surface differs slightly when their modules land, **flag the drift** to the orchestrator. Update your tests only if the spec changes; otherwise the spec wins.

## Quality bar

- **`pytest tests/test_hunl_diff.py -x`** passes cleanly.
- **`cargo test --package cfr_core --test test_hunl_rust`** passes (note: integration tests live under `crates/cfr_core/tests/`; the `--test test_hunl_rust` flag matches the file name without `.rs`).
- **`ruff check tests/test_hunl_diff.py`** clean.
- **`black --check tests/test_hunl_diff.py`** clean.
- **`mypy --strict tests/test_hunl_diff.py`** clean (or use `# type: ignore` ONLY where unavoidable for PyO3 dynamic dispatch — minimize).
- **Existing 138+ tests still pass:** `pytest -x` clean.
- **No regression in Kuhn/Leduc diff tests:** `pytest tests/test_dcfr_diff.py` unchanged.
- **`cargo test --all`** all green (existing Rust tests + your new tests).
- **`@pytest.mark.slow`** on the flop fixture test (Test 2) per spec §14 #9. The river subgame test is fast (<60s) and stays in the default suite.
- **Code size budget:** `test_hunl_diff.py` ~300-500 LOC; `test_hunl_rust.rs` ~400-700 LOC. Stay within budget.

## Reference-first rule

Before any test approach, citation, or numerical threshold, check the local references. **Never extrapolate from training data when a local authoritative source exists.** The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md`.

Specific anchors for your scope:
- For tolerance choice: PR 6 spec §7.3 (the 1e-3 / 5e-3 cluster) and consistency-review I3.
- For test patterns: `tests/test_dcfr_diff.py` (Kuhn/Leduc precedent) and `tests/test_hunl_postflop_solve.py` (PR 5 precedent).
- For PyO3 cross-tier test patterns: see `crates/cfr_core/tests/*.rs` if any exist, otherwise consult `pyo3` documentation for `Python::with_gil`.

If you "remember" a poker-test pattern from training data (e.g., a particular bucket-roundtrip approach), ground it in the spec or in `poker_solver/abstraction/buckets.py`. When in doubt, prefer the spec's stated approach.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_hunl_diff.py
black --check tests/test_hunl_diff.py

# 2. Type-check
mypy --strict tests/test_hunl_diff.py

# 3. Run YOUR Python diff tests
pytest tests/test_hunl_diff.py -v 2>&1 | tail -30

# 4. Run YOUR Rust integration tests
cargo test --package cfr_core --test test_hunl_rust 2>&1 | tail -30

# 5. Run with the slow marker for the flop fixture (longer wallclock)
pytest tests/test_hunl_diff.py -v -m slow 2>&1 | tail -10

# 6. Existing tests must still pass
pytest -x 2>&1 | tail -10
cargo test --all 2>&1 | tail -20

# 7. Specifically confirm Kuhn/Leduc diff test untouched
pytest tests/test_dcfr_diff.py -v 2>&1 | tail -10
```

If any step fails, fix the issue before reporting done. **If a test reveals a genuine spec ambiguity, STOP and flag to the orchestrator — do not silently tweak the test to pass.** The spec is the source of truth.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec ambiguity surfaced by your tests (and how the orchestrator should resolve it).
3. Verification command output (paste tails of `pytest tests/test_hunl_diff.py`, `cargo test --test test_hunl_rust`, `pytest -x`, `cargo test --all`).
4. Observed tolerance margins on the river subgame and flop fixture tests (e.g., "max per-action divergence on river subgame: 4.2e-4 — well within 1e-3 threshold"). This calibration data informs PR 6 spec §10's "tolerance choice is wrong" mitigation.
5. Confirmation that 10K-input bucket-roundtrip + 1K-input Strength-ordering tests passed (these are the high-volume canaries).
6. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
