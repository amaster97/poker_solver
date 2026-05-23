# PR 6 Agent B — abstraction loader + Rust solver + PyO3 + Python integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 6 Agent B.**
**Your scope:** the abstraction-loader module that reads PR 4's `.npz` artifact into Rust, the postflop solve entrypoint that wires Agent A's `HUNLState` + `HUNLTree` to the existing `DCFRSolver<G>` in `crates/cfr_core/src/dcfr.rs`, the PyO3 surface exposing `_rust.solve_hunl_postflop`, and the Python-side glue that routes `solve()` to the Rust backend for HUNL postflop configs.
**Your contract:** ship `abstraction.rs` (`AbstractionTables` + `load_abstraction` + `lookup_bucket`), `hunl_solver.rs` (`solve_hunl_postflop` Rust entry), extension to `lib.rs` (PyO3 binding), and Python edits in `solver.py` (`_solve_rust` HUNL branch) + `hunl.py` (`_serialize_hunl_config`, confirming PR 4's `AbstractionRef` field is present) + `cli.py` (`--backend rust`). Agent A's types in `crate::hunl::*`, `crate::hunl_tree::*`, `crate::hunl_eval::*` are your inputs; Agent C tests both tiers against your public API.
**Your success criteria:** `cargo build --release` rebuilds the extension; `pip install -e .` succeeds; the Rust branch of `_solve_rust` produces a valid strategy on a tiny river subgame; Python recomputes exploitability + game_value matching Kuhn/Leduc precedent; `ruff` / `black` / `mypy --strict` clean on all modified Python files; ALL 138+ existing tests still pass.
**File ownership:** you own `crates/cfr_core/src/abstraction.rs`, `crates/cfr_core/src/hunl_solver.rs`, `crates/cfr_core/Cargo.toml` (additive); you may surgically modify `crates/cfr_core/src/lib.rs` (PyO3 surface), `poker_solver/solver.py` (HUNL branch in `_solve_rust`), `poker_solver/hunl.py` (`_serialize_hunl_config` helper; confirming `AbstractionRef`), `poker_solver/cli.py` (`--backend rust`). You may NOT touch `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, or any test file.

---

## Strict file ownership

PR 6 depends on **PR 4** (the `.npz` bucket file format — Agent A wrote it; you read it from Rust) and **PR 5** (the Python orchestration baseline you mirror). Both have landed.

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/abstraction.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs` (new file)

**You may surgically modify (small, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` — add `ndarray-npy = "0.9"` (MIT/Apache 2.0; license verified via `check_pr.sh`), `serde = { version = "1", features = ["derive"] }`, `serde_json = "1"`, `arrayvec = "0.7"` if not already present. Confirm each addition is MIT/Apache before committing.
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — add the `mod abstraction;` + `mod hunl;` + `mod hunl_tree;` + `mod hunl_eval;` + `mod hunl_solver;` declarations and the `#[pyfunction] fn solve_hunl_postflop(...)` PyO3 binding registered in the `#[pymodule]` block.
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — extend `_solve_rust` with an HUNL postflop branch (preflop raises `NotImplementedError` pointing at PR 9).
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — add `_serialize_hunl_config(config) -> str` helper. Confirm (do not re-add) PR 4's `AbstractionRef` field on `HUNLConfig.abstraction`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — add `--backend rust` opt-in to the `solve --game hunl --hunl-mode postflop` path (default remains `python` per PR 5 lock).

**You must NOT touch:**
- `crates/cfr_core/src/hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs` — Agent A owns these. You import their types via `crate::hunl::*`, `crate::hunl_tree::*`, `crate::hunl_eval::*`.
- `crates/cfr_core/src/dcfr.rs`, `game.rs`, `solver.rs`, `kuhn.rs`, `leduc.rs` — frozen for PR 6. The existing `DCFRSolver<G>` is generic over `Game` and consumes Agent A's `HUNLState` unchanged.
- `poker_solver/hunl_solver.py`, `poker_solver/dcfr.py`, `poker_solver/abstraction/*` — frozen for PR 6.
- Any test file — Agent C.

If you discover a contract gap mid-implementation, **do not silently change the spec interface**. Stop and flag to the orchestrator.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md`. Internalize §3 (license-aware sourcing), §4.4 (`abstraction.rs` — note the 2026-05-22 launch-readiness-v2 amendment: PR 4's on-disk format is **string-keyed dict-of-dict indices + JSON `metadata` blob**, NOT the original draft's `HandLookup` packed struct + top-level scalar fields; your loader parses each dict from JSON bytes), §4.5 (`hunl_solver.rs`), §5 (PyO3 surface — JSON config marshalling), §6 (Python tier integration — note §6.1 dispatch ordering invariant: HUNL Rust branch composes AFTER push/fold short-circuit per PR 9 §6, and §6.3 `AbstractionRef` resolution via `resolve_abstraction_ref`), §8.2 (your deliverables), §9 (critical correctness items — especially #2, #9, #11, #15), §10 (risks).
2. **Spec consistency review (cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Key entries for your scope: **B1** (PR 4's `metadata` is a single JSON-encoded dict inside the `.npz`; **AND** `*_board_index` / `*_hand_index` are each ALSO JSON-encoded inside one-element bytes arrays — not `Vec<u32>` arrays; your Rust loader uses `serde_json::from_slice` on each), **B2** (PR 4 declared `AbstractionRef { source_path, version }` on `HUNLConfig.abstraction`; you consume, do NOT re-declare; canonical entry is `resolve_abstraction_ref(ref)` which is LRU-cached + version-checked), **I6** (PR 8 will add `use_pcs: bool`; PR 6 Rust mirror pre-includes; Python `HUNLConfig` may or may not have the field — confirm via Read on `poker_solver/hunl.py`; if missing in Python add the field to your serializer with default `false`).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 (Python ground truth + Rust 10-50× speedup), §6 License audit (the AGPL/MIT/Apache table is load-bearing).
4. **Python source of truth (you mirror their orchestration):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` (PR 5) — the orchestration shape; you produce a Rust-tier counterpart.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` lines 268-305 — the existing `_solve_rust` pattern for Kuhn/Leduc; you extend it with an HUNL branch following the same pattern.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` (PR 4 — **AUTHORITATIVE on the on-disk format**) — `AbstractionTables`, `AbstractionRef`, `resolve_abstraction_ref` (LRU-cached + version-checked resolver — this is the canonical entry from Python, never reach into `.source_path` directly), `lookup_bucket`, `_canonicalize`, `_apply_suit_perm_to_hand`, `save_abstraction`, `load_abstraction`. Your Rust port must produce identical **string** keys (not integers) and read the JSON-bytes dicts the writer produces.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/equity_features.py` (PR 4) — `canonicalize_for_suit_iso`, `_SUIT_PERMUTATIONS`. The suit-iso canonicalization that produces the string board/hand keys.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/precompute.py` (PR 4) — the writer side; your loader parses what it wrote.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` (PR 3 + PR 4 amendment) — `HUNLConfig`, `AbstractionRef`. You add `_serialize_hunl_config` here.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` (PR 5) — the existing postflop CLI path; you extend with `--backend rust`.
5. **Rust precedent (style + PyO3 pattern):**
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — the existing `solve_kuhn` / `solve_leduc` PyO3 functions. Match this pattern for `solve_hunl_postflop` (with the `py.allow_threads(...)` addition).
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/solver.rs` — the existing `solve_kuhn` / `solve_leduc` orchestrators returning `SolveOutput`. Your `solve_hunl_postflop` should return a similar shape.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — the generic `DCFRSolver<G>` you call.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/leduc.rs` — module-docstring attribution style (Apache 2.0 attribution for the `open_spiel` port).
6. **MIT/Apache reference code (you MAY port architecturally with attribution):**
   - `references/code/noambrown_poker_solver/cpp/src/trainer.{h,cpp}` (MIT) — DCFR-on-postflop control flow pattern. You won't need much here because `DCFRSolver<G>` is already generic; cite if you do anything novel.
   - `references/code/slumbot2019/src/card_abstraction*.cpp` (MIT) — abstraction lookup table layout reference.
   - `references/code/open_spiel/games/leduc_poker.cc` (Apache 2.0) — terminal handling reference (Agent A's domain, but if you touch it in `_solve_rust` for error messages, attribute).
7. **AGPL repos you must NOT copy from:**
   - `references/code/postflop-solver/` — **AGPL v3.** Read-only inspiration.
   - `references/code/TexasSolver/` — **AGPL v3.** Same rule.

## Default decisions LOCKED (do not deviate)

PR 6 spec §11 lists 12 deferred decisions. Per the consistency review, all defaults are **LOCKED** unless the user redirects before launch. The ones that touch your scope:

- **D1 — Scalar CFR for PR 6.** One regret value per (infoset, action). Vector-CFR (Noam Brown's per-hand vectorization) is PR 8. The existing `DCFRSolver<G>` is scalar; you do not modify it. Vector-CFR is NOT in your scope.
- **D2 — JSON string config marshalling.** Not PyO3-struct binding. Python serializes `HUNLConfig` to a JSON string via `_serialize_hunl_config`; Rust deserializes via `serde_json`. Single boundary, easy to inspect. ~50 lines of `serde::Deserialize` derive on Rust side. Simpler than struct binding for v1; can refactor later. **DO NOT try to expose `HUNLConfig` as a `#[pyclass]` — that's a future PR.**
- **D3 — Regret storage: f64 throughout.** Matches Python's `np.float64`. The f32 alternative is NOT locked.
- **D4 — Keep `.npz` artifact format.** PR 4 owns the writer; PR 6 is a consumer. No re-quantization, no on-disk repacking.
- **D5 — Python recomputes exploitability + game_value from the Rust strategy.** Matches the Kuhn/Leduc `_solve_rust` pattern in `poker_solver/solver.py:295`. Your Rust side returns the strategy + iteration count; the Python wrapper calls the existing `exploitability(game, strategy)` + `_game_value(game, strategy)` to compute those fields. **Do NOT add a Rust-side exploitability walk in PR 6** — PR 8 may revisit.
- **D6 — Flat tree at build time.** Agent A's `HUNLTree::build` is called once at the top of `solve_hunl_postflop`, then walked by the DCFR loop.
- **D7 — Diff-test tolerance: 1e-3 (river-only), 5e-3 (flop fixture).** Not directly your concern (Agent C tests), but your strategy output must be precise enough to pass. Use `f64` arithmetic throughout.
- **D8 — HashMap hasher: default in production, `ahash` with fixed seed under `#[cfg(test)]`.** If you maintain any HashMap inside the solver (e.g., the DCFR regret map, which is in `dcfr.rs` and not your file — but if you wrap it), the hasher policy applies.
- **D10 — CLI default backend: `python`.** User opts in to Rust via `--backend rust`. **DO NOT flip the default.**
- **D11 — Build flat tree AFTER abstraction load.** In `solve_hunl_postflop`: (1) load `AbstractionTables` from `abstraction_path`; (2) build `HUNLTree` with the loaded abstraction; (3) run DCFR loop.
- **D12 — `target_exploitability` early-exit forwarded through PyO3.** You expose the parameter; the DCFR loop uses it to terminate early. (If the existing `DCFRSolver<G>` doesn't support early-exit on `target_exploitability`, document the limitation and either: pass through as an unused parameter, OR add a minimal wrapper that snapshots and checks every K iterations. The former is simpler; pick it if `DCFRSolver` lacks the hook.)

## Public API contract (signatures Agent A + Agent C depend on)

**Signature drift breaks Agent A's `infoset_key` consumer surface and Agent C's tests.** Lock these shapes.

### From `crates/cfr_core/src/abstraction.rs`

**On-disk format reality check (post-PR-4-merge).** PR 4 shipped a different shape than the original PR 6 spec draft anticipated. The committed `save_abstraction` / `load_abstraction` in `poker_solver/abstraction/buckets.py` stores:

- `*_assignments`: flat `uint8` numpy arrays (bucket ids).
- `*_board_index`: a **JSON-encoded `dict[str, int]`** stored as a one-element bytes array inside the `.npz`. Maps `canonical_board_key` (str) → start offset (int).
- `*_hand_index`: a **JSON-encoded `dict[str, dict[str, int]]`** stored as a one-element bytes array. Maps `canonical_board_key` → `canonical_hand_key` → within-board offset.
- `metadata`: a **JSON-encoded `dict`** stored as a one-element bytes array. Contains `schema_version`, `version`, `bucket_counts`, `feature_bins`, `seed`, and any other writer-side keys.

The lookup is:

```python
offset = board_index[canonical_board_key] + hand_index[canonical_board_key][canonical_hand_key]
bucket_id = assignments[offset]
```

Canonical keys are **strings** (sorted-by-(rank, suit) joined card-strings produced by `canonicalize_for_suit_iso` + `_apply_suit_perm_to_hand`), NOT `u32` IDs. There is no top-level `HandLookup` struct; there is no top-level `bucket_counts` / `schema_version` / `feature_bins` / `seed` field — those live inside the parsed `metadata` dict.

**Locked Rust shape:**

```rust
//! HUNL card-bucket abstraction loader.
//!
//! Reads PR 4's `.npz` artifact (project-internal, MIT) via `ndarray-npy`
//! (MIT/Apache 2.0). String-keyed dict-of-dict indices + single JSON `metadata`
//! blob per the committed PR 4 layout (`poker_solver/abstraction/buckets.py::
//! save_abstraction`/`load_abstraction`). Lookup-table layout patterned after
//! `references/code/slumbot2019/src/card_abstraction*.cpp` (MIT) with attribution.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).

use crate::hunl::Street;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, serde::Deserialize)]
pub struct AbstractionMetadata {
    pub schema_version: u8,
    pub version: String,           // matches `HUNLConfig.abstraction.version` for the sanity check
    pub bucket_counts: Vec<u16>,   // [K_flop, K_turn, K_river]
    pub feature_bins: u16,
    pub seed: u64,
    // Tolerate any additional writer-side keys without failing parse.
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

#[derive(Clone, Debug)]
pub struct AbstractionTables {
    pub flop_assignments: Vec<u8>,
    pub turn_assignments: Vec<u8>,
    pub river_assignments: Vec<u8>,

    // String-keyed dicts parsed from the JSON-bytes blobs in the .npz.
    pub flop_board_index: HashMap<String, u32>,
    pub turn_board_index: HashMap<String, u32>,
    pub river_board_index: HashMap<String, u32>,

    pub flop_hand_index: HashMap<String, HashMap<String, u32>>,
    pub turn_hand_index: HashMap<String, HashMap<String, u32>>,
    pub river_hand_index: HashMap<String, HashMap<String, u32>>,

    pub metadata: AbstractionMetadata,

    // Populated by load_abstraction(path); NOT persisted to disk.
    pub source_path: PathBuf,
}

#[derive(Debug)]
pub enum AbstractionError {
    Io(std::io::Error),
    Npz(String),
    Json(String),
    SchemaMismatch { expected: u8, found: u8 },
    VersionMismatch { expected: String, found: String },
    Malformed(String),
}

pub fn load_abstraction(path: &Path) -> Result<AbstractionTables, AbstractionError>;

/// O(1) bucket lookup. MUST be byte-for-byte identical to Python's
/// `lookup_bucket` in `poker_solver/abstraction/buckets.py`. Preflop returns -1.
///
/// Implementation:
///   1. If street is Preflop, return -1.
///   2. Canonicalize (board, hole) -> (board_key: String, hand_key: String)
///      via the suit-iso canonicalizer (must match Python's
///      `canonicalize_for_suit_iso` + `_apply_suit_perm_to_hand` byte-for-byte).
///   3. board_offset = *_board_index[&board_key]
///   4. within = *_hand_index[&board_key][&hand_key]
///   5. return *_assignments[board_offset + within] as i32
pub fn lookup_bucket(
    tables: &AbstractionTables,
    board: &[u8],
    hole: &[u8; 2],
    street: Street,
) -> i32;

// Internal canonicalization helpers (private; consumed by lookup_bucket).
// MUST match Python's `canonicalize_for_suit_iso` + `_apply_suit_perm_to_hand`
// byte-for-byte — the keys are STRINGS, not integers.
pub(crate) fn canonical_board_key(board: &[u8], street: Street) -> String;
pub(crate) fn canonical_hand_key(hole: &[u8; 2], perm_index: u8) -> String;

// Internal helper: decode a one-element bytes array in the .npz holding a JSON-
// encoded dict. Used for board_index / hand_index / metadata. PR 4 writes each
// dict via `json.dumps(d, sort_keys=True, separators=(',', ':')).encode()`.
fn decode_json_bytes(raw: &[u8]) -> Result<serde_json::Value, AbstractionError>;
```

**Lookup hot path notes:**
- The HashMap is keyed on `String` — clones are cheap relative to a flop solve, but if hot-path allocation becomes a problem, switch to `&str` lookups via `HashMap::get(key.as_str())`. PR 6 default: simple `String` keys to mirror Python.
- `canonical_board_key` / `canonical_hand_key` allocate the result string. Acceptable for PR 6; PR 8 may revisit.

### From `crates/cfr_core/src/hunl_solver.rs`

```rust
//! HUNL postflop solve entry (Rust production tier).
//!
//! Counterpart to `poker_solver/hunl_solver.py::solve_hunl_postflop` (project-
//! internal, MIT). Wires Agent A's `HUNLState` + `HUNLTree` to the generic
//! `crate::dcfr::DCFRSolver<G>`. Algorithm shape mirrors
//! `references/code/noambrown_poker_solver/cpp/src/trainer.cpp` (MIT) by
//! structural pattern (already inherited from PR 1's port).
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).

use crate::abstraction::{AbstractionTables, load_abstraction};
use crate::dcfr::DCFRSolver;
use crate::hunl::{HUNLConfig, HUNLState, Street};
use crate::hunl_tree::HUNLTree;
use std::collections::HashMap;
use std::sync::Arc;

pub struct HUNLSolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub exploitability: f64,    // 0.0 in PR 6 (Python recomputes; D5)
    pub game_value: f64,        // 0.0 in PR 6 (Python recomputes; D5)
    pub iterations: u32,
    pub wallclock_seconds: f64,
    pub infoset_count: u32,
}

#[derive(Debug)]
pub enum HUNLSolveError {
    PreflopNotSupported,
    BoardLengthMismatch { expected: usize, found: usize, street: Street },
    RakeNonZero,
    AbstractionLoad(crate::abstraction::AbstractionError),
    InvalidConfig(String),
}

pub fn solve_hunl_postflop(
    config: &HUNLConfig,
    abstraction: Option<&AbstractionTables>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    target_exploitability: Option<f64>,
    seed: Option<u64>,
) -> Result<HUNLSolveOutput, HUNLSolveError>;
```

### From `crates/cfr_core/src/lib.rs` (additive — your edit)

```rust
mod abstraction;
mod hunl;
mod hunl_eval;
mod hunl_solver;
mod hunl_tree;

#[pyfunction]
fn solve_hunl_postflop(
    py: Python<'_>,
    config_json: &str,
    abstraction_path: Option<&str>,
    iterations: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    target_exploitability: Option<f64>,
    seed: Option<u64>,
) -> PyResult<PyObject> {
    // 1. Deserialize config from JSON
    // 2. Optionally load abstraction
    // 3. Release the GIL and run the solve
    let result = py.allow_threads(|| {
        // ... blocking Rust solve here
    });
    // 4. Marshal HUNLSolveOutput → PyDict
    // ...
}

// In #[pymodule] fn _rust(...):
//    m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;
```

### From `poker_solver/hunl.py` (additive — your edit)

```python
def _serialize_hunl_config(config: HUNLConfig) -> str:
    """Dump HUNLConfig to a JSON string matching the Rust serde shape.

    Includes every field of HUNLConfig that the Rust side needs:
    starting_stack, small_blind, big_blind, ante, starting_street (as int),
    initial_board (list of card-ints), initial_pot, initial_contributions,
    preflop_raise_cap, postflop_raise_cap, bet_size_fractions (list of f64),
    include_all_in, force_allin_threshold, min_bet_bb, rake_rate, rake_cap,
    abstraction_path (str or None), abstraction_version (str or None),
    use_pcs (bool, defaults to False).

    Does NOT include the full AbstractionTables; only the on-disk path so the
    Rust side can load independently.
    """
    ...
```

### From `poker_solver/solver.py` (additive — your edit to `_solve_rust`)

```python
elif isinstance(game, HUNLPoker):
    if game.config.starting_street == Street.PREFLOP:
        raise NotImplementedError(
            "HUNL preflop port lands in PR 9. Use --hunl-mode postflop."
        )
    from poker_solver._rust import solve_hunl_postflop as _rust_solve_hunl
    from poker_solver.abstraction.buckets import resolve_abstraction_ref
    config_json = _serialize_hunl_config(game.config)
    abstraction_path: str | None = None
    if game.config.abstraction is not None:
        # Go through the canonical LRU-cached + version-checked resolver — do
        # NOT reach into `game.config.abstraction.source_path` directly.
        # PR 4 declares `resolve_abstraction_ref(ref) -> AbstractionTables` as
        # the public seam; it (a) reuses cached loads keyed on
        # (source_path, version) and (b) raises if the on-disk
        # metadata['version'] disagrees with `ref.version`. Bypassing it
        # silently re-loads + silently accepts stale artifacts.
        tables = resolve_abstraction_ref(game.config.abstraction)
        abstraction_path = str(tables.source_path)
    raw = _rust_solve_hunl(
        config_json,
        abstraction_path,
        int(iterations),
        alpha, beta, gamma,
        dcfr_kwargs.get("target_exploitability"),
        dcfr_kwargs.get("seed"),
    )
    avg = {k: list(v) for k, v in raw["average_strategy"].items()}
    expl = exploitability(game, avg)
    gv = _game_value(game, avg)
    return SolveResult(
        average_strategy=avg,
        exploitability_history=[expl],
        game_value=gv,
        iterations=int(raw["iterations"]),
        backend="rust",
    )
```

**Dispatch ordering invariant (PR 9 §6 canonical).** The new HUNL branch must compose **AFTER** the PR 3.5 push/fold short-circuit and **BEFORE** any preflop dispatch. Canonical ordering, head-to-tail:

```
solve() / _solve_rust() dispatch:
  1. push/fold short-circuit (PR 3.5; routes ≤15-BB HUNL preflop to the chart fast path)
  2. HUNL postflop Rust branch (THIS PR — `backend == "rust"` and `isinstance(game, HUNLPoker)`, postflop)
  3. HUNL postflop Python fallback (PR 5 — postflop without `backend == "rust"`)
  4. HUNL preflop branch (PR 9 — not implemented in PR 6; raise NotImplementedError)
  5. Kuhn/Leduc branches (PR 1/2 — unchanged)
```

If you insert the HUNL Rust elif **before** the push/fold check, low-stack postflop configurations (≤15 BB) will silently bypass the chart fast path and go through the full DCFR loop. PR 9 §6 declares this ordering canonical; PR 6 inherits it. Read `poker_solver/solver.py:268-305` and confirm the push/fold short-circuit is the first branch — your insertion goes after it.

## Critical correctness items

### 1. Bucket file roundtrip — byte-for-byte parity with Python

**This is the single most fragile cross-tier seam.** Rust's `load_abstraction(path)` followed by `lookup_bucket(tables, board, hole, street)` MUST produce the same bucket ID as Python's `lookup_bucket(tables, board, hole, street)` for **every** valid `(state, player)` input. The canonicalization (`canonicalize_for_suit_iso` + `_apply_suit_perm_to_hand`) produces **string** keys — if Rust's sort order or string-format differs from Python's by one byte, the HashMap miss cascades into every post-flop bucket diverging, and Agent C's `test_abstraction_canonicalization_matches_python` (10K random inputs) will fail.

**Implementation rules:**
- Read `poker_solver/abstraction/buckets.py` (save_abstraction / load_abstraction / `_canonicalize` / `_apply_suit_perm_to_hand`) and `poker_solver/abstraction/equity_features.py` (`canonicalize_for_suit_iso`, `_SUIT_PERMUTATIONS`) carefully. Replicate the exact sort + permutation + key-formatting logic.
- The `.npz` `metadata` is **one** JSON-encoded dict (B1 resolution). Each `*_board_index` and `*_hand_index` is **also** a JSON-encoded dict stored as bytes (one `np.savez_compressed` entry per dict — they are NOT separate `Vec<u32>` arrays). Use `serde_json::from_slice` on each set of bytes; Python writes `json.dumps(d, sort_keys=True, separators=(',', ':')).encode()` for byte-determinism.
- Schema version check: assert `metadata.schema_version == 1`; mismatch → return `AbstractionError::SchemaMismatch` with a clear message ("rebuild abstraction via `poker-solver precompute-abstraction`").
- Version check: if the runtime `AbstractionTables.metadata.version` does NOT match `HUNLConfig.abstraction.version` (passed in via JSON serialization of the config), return `AbstractionError::VersionMismatch`. Loud failure, not silent mismatch. (Note: Python tier already enforces this via `resolve_abstraction_ref` — Rust check is defense-in-depth.)
- Canonical keys are **strings** (e.g., `"2c3d4h"` style — exact format follows `_apply_suit_perm_to_hand` in `buckets.py`). NOT `u32`. The Rust `HashMap<String, _>` must use byte-identical strings to the dicts Python wrote.

### 2. JSON config marshalling preserves f64 bit-exactly

`HUNLConfig.bet_size_fractions` is `Vec<f64>`. Python sends `[0.33, 0.75, …]` over JSON via `_serialize_hunl_config`. `serde_json` preserves IEEE-754 doubles bit-exactly when using `to_string()` → `from_str()` chain (verified for non-NaN, non-Inf values; you only handle finite f64s).

Test path: round-trip a `HUNLConfig` through serialize → deserialize and confirm bet-size-derived bet amounts are exactly the same in both tiers. Agent C's `test_hunl_rust_action_ids_match_python_constants` extends to compare bet-size-derived chip amounts.

### 3. PyO3 GIL release in `solve_hunl_postflop`

The DCFR loop is pure-Rust (no Python callbacks). **Wrap the entire solve in `py.allow_threads(|| { … })`.** Otherwise multi-call scenarios (CLI vs UI thread later) deadlock waiting on the GIL.

```rust
let result = py.allow_threads(|| {
    let config: HUNLConfig = serde_json::from_str(config_json)?;
    let tables: Option<AbstractionTables> = match abstraction_path {
        Some(p) => Some(load_abstraction(Path::new(p))?),
        None => None,
    };
    let mut solver_out = solve_hunl_postflop(
        &config, tables.as_ref(), iterations, alpha, beta, gamma,
        target_exploitability, seed,
    )?;
    Ok::<HUNLSolveOutput, _>(solver_out)
});
```

**Critical** — if missed, easy to ship a deadlock. Audit-agent focus area per spec §9 #11.

### 4. Python recomputes exploitability + game_value (D5)

In Rust, set `HUNLSolveOutput.exploitability = 0.0` and `HUNLSolveOutput.game_value = 0.0` on the way out. The Python wrapper in `_solve_rust` calls `exploitability(game, strategy)` and `_game_value(game, strategy)` to fill those fields in `SolveResult`. Matches Kuhn/Leduc pattern (see `poker_solver/solver.py:268-305`).

**Why:** removes cross-tier float drift in exploitability values; sidesteps Rust BR optimization until PR 8.

### 5. HUNL preflop rejected up front

Both tiers reject. Rust returns `Err(HUNLSolveError::PreflopNotSupported)` if `config.starting_street == Street.Preflop`. The Python wrapper raises `NotImplementedError("HUNL preflop port lands in PR 9.")` BEFORE calling into Rust (defense in depth). Tested in both tiers.

### 6. `rake_rate == 0.0 && rake_cap == 0` enforced

Same assertion as PR 5: solver-side rake is PR 9. Reject any config with `rake_rate != 0.0` or `rake_cap != 0` with `HUNLSolveError::RakeNonZero`. Loud failure.

### 7. CLI flag — default backend remains Python

`poker-solver solve --game hunl --hunl-mode postflop --board "..." --iterations 500` without `--backend rust` continues to route through `poker_solver/hunl_solver.py::solve_hunl_postflop` (PR 5 path). Only when `--backend rust` is set does the CLI invoke `_solve_rust`. PR 5 behavior preserved.

### 8. License attribution headers MANDATORY

`abstraction.rs` and `hunl_solver.rs` MUST start with the module-level attribution docstring per spec §3. Cite MIT/Apache sources; explicitly call out AGPL repos as "NEVER copy from." The `check_pr.sh` audit will grep.

### 9. `ndarray-npy` license verified

`ndarray-npy = "0.9"` is **MIT/Apache 2.0 dual-licensed**. Confirm via `cargo tree --package ndarray-npy --format "{p} {l}"` after adding the dep. Same check for `serde`, `serde_json`, `arrayvec` (all MIT/Apache). The `check_pr.sh` license audit (PLAN.md §4 step 6) will fail if any new AGPL/GPL dep slipped in.

### 10. No code copied from AGPL

No function bodies, no distinctive type names, no idioms from `postflop-solver` or `TexasSolver`. The architectural ideas (flat tree, postflop subgame, action enumeration) are public knowledge — derive independently from Python + MIT sources. Cite postflop-solver in spec docs only, never in Rust comments.

### 11. Existing Kuhn/Leduc paths untouched

PR 1/2's `solve_kuhn` / `solve_leduc` PyO3 functions in `lib.rs` continue to work. Your edit to `lib.rs` is purely additive (new `mod` declarations + new `#[pyfunction]` + new registration in `#[pymodule]`). `tests/test_dcfr_diff.py` (Kuhn/Leduc differential test) must still pass unchanged.

### 12. Python tier integration preserves PR 5 behavior

After your edits to `poker_solver/solver.py`, `hunl.py`, `cli.py`:
- The 138+ existing tests still pass (`pytest -x`).
- `solve(game, ..., backend="python")` continues to route to `poker_solver/hunl_solver.py` (PR 5 path).
- `solve(game, ..., backend="rust")` newly routes to your `_solve_rust` HUNL branch.
- The `_serialize_hunl_config` helper produces JSON that round-trips bit-exact with the Rust `serde::Deserialize` shape.

### 13. `target_exploitability` early-exit

If the existing `DCFRSolver<G>` in `dcfr.rs` doesn't have an early-exit hook, you have two choices:
1. Pass `target_exploitability` through as an unused parameter and document the limitation in a code comment. PR 8 may add the hook.
2. Add a minimal wrapper in `hunl_solver.rs` that runs DCFR in chunks of (say) 100 iterations, snapshots the strategy, computes exploitability against the current strategy, and exits when below threshold.

**Default: option 1** (simpler; matches Kuhn/Leduc behavior). Option 2 if user explicitly asks. Document the choice.

## Cross-agent contracts

Treat Agent A's surface as opaque. Import only the names; do not depend on internals:

```rust
// From crate::hunl (Agent A's module — DO NOT TOUCH):

pub enum Street { Preflop, Flop, Turn, River, Showdown }
pub const ACTION_FOLD: u8 = 0;
// ... ACTION_ALL_IN = 13
pub struct HUNLConfig { /* ... per spec §4.1 */ }
pub struct HUNLState { /* ... per spec §4.1 */ }
impl Game for HUNLState { /* full trait */ }

// From crate::hunl_tree (Agent A's module):
pub struct HUNLTree { /* ... per spec §4.2 */ }
impl HUNLTree {
    pub fn build(
        config: Arc<HUNLConfig>,
        abstraction: Option<&crate::abstraction::AbstractionTables>,
    ) -> Self;
}

// From crate::hunl_eval (Agent A's module):
pub struct Strength(pub u32);
impl Strength {
    pub fn evaluate_5(cards: &[u8; 5]) -> Strength;
    pub fn evaluate_7(cards: &[u8; 7]) -> Strength;
}
```

You consume these from `hunl_solver.rs`. You do NOT modify them. If Agent A's surface differs slightly when their module lands, **flag the drift** to the orchestrator. The spec lock is in §4.1–§4.3.

**Agent A consumes from YOUR module:**
- `crate::abstraction::AbstractionTables` (struct, fields per §4.4)
- `crate::abstraction::lookup_bucket(tables, board, hole, street) -> i32`

Agent A's `HUNLState::infoset_key` receives `Option<&AbstractionTables>` and calls `lookup_bucket` for the bucketed branch. Stable surface = `AbstractionTables` field set + `lookup_bucket` signature.

## License-aware sourcing

The license audit in PLAN.md §6 is **load-bearing**. Policy for each new file:

| Source | License | Use in your files |
|---|---|---|
| `poker_solver/abstraction/buckets.py` | project-internal MIT | **First reference.** Byte-for-byte port of `lookup_bucket` + canonicalization. |
| `poker_solver/abstraction/precompute.py` | project-internal MIT | Reference for the writer side (so you know what to parse). |
| `poker_solver/hunl_solver.py` | project-internal MIT | **First reference.** Mirror the orchestration semantics. |
| `poker_solver/solver.py::_solve_rust` | project-internal MIT | **First reference.** Extend the existing pattern. |
| `ndarray-npy` (crate) | MIT/Apache 2.0 dual | OK to use. Verify via `cargo tree`. |
| `serde`, `serde_json`, `arrayvec` (crates) | MIT/Apache 2.0 dual | OK to use. Verify via `cargo tree`. |
| `noambrown_poker_solver/cpp/src/trainer.{h,cpp}` | **MIT** | Pattern reference (already inherited from PR 1's port). Attribution if you cite. |
| `slumbot2019/src/card_abstraction*.cpp` | **MIT** | Pattern reference for abstraction layout. Attribution required. |
| `postflop-solver/src/*` | **AGPL v3** | **Never copy.** Architectural ideas only. |
| `TexasSolver/*` | **AGPL v3** | **Never copy.** Same rule. |
| `shark-2.0/*` | **Unlicensed** | **Never study.** |

**Module-level attribution template** (paste at the top of each new file):

```rust
//! <short description>
//!
//! Adapted from `poker_solver/<file>.py` (project-internal, MIT) for semantics;
//! <pattern> mirrors `<MIT source path>` (MIT) by pattern, not by transcription.
//! Uses `ndarray-npy` (MIT/Apache 2.0) for `.npz` reading; `serde_json` (MIT/Apache
//! 2.0) for metadata parsing.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
```

## Quality bar

- **`cargo build --release --package cfr_core`** clean.
- **`cargo clippy --package cfr_core --all-targets -- -D warnings`** clean. Zero warnings.
- **`pip install -e .`** succeeds (rebuilds the PyO3 extension after your Rust edits).
- **`ruff check poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py`** clean.
- **`black --check poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py`** clean.
- **`mypy --strict poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py`** clean. (mypy is already strict on these files per PR 5.)
- **`pytest -x` passes** — all 138+ existing tests must still pass. Your edits are additive.
- **License audit** (`cargo tree --package cfr_core | grep -i "agpl\|gpl-3"`) returns no AGPL/GPL deps.
- **No new third-party Python deps.** Confirm `pyproject.toml` has no diff in the dependency section.
- **Code size budget:** `abstraction.rs` ~400-600 LOC, `hunl_solver.rs` ~200-300 LOC, `lib.rs` edit ~50-80 LOC, Python edits ~30-50 LOC per file.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. **Never extrapolate from training data when a local authoritative source exists.** The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md`.

Specific anchors:
- For `.npz` parsing: the `ndarray-npy` crate docs + `poker_solver/abstraction/precompute.py` writer.
- For bucket lookup: `poker_solver/abstraction/buckets.py::lookup_bucket`.
- For solve orchestration: `poker_solver/hunl_solver.py::solve_hunl_postflop` (Python tier).
- For `_solve_rust` pattern: `poker_solver/solver.py:268-305`.

If you "remember" a PyO3 idiom from training data, ground it in `crates/cfr_core/src/lib.rs` (the existing `solve_kuhn` / `solve_leduc`). Same for serde patterns — derive from spec or local references.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Build the Rust crate
cargo build --release --package cfr_core 2>&1 | tail -20

# 2. Clippy zero-warnings
cargo clippy --package cfr_core --all-targets -- -D warnings 2>&1 | tail -20

# 3. Rebuild Python extension after Rust edits
pip install -e . 2>&1 | tail -10

# 4. License audit on Rust deps
cargo tree --package cfr_core 2>&1 | grep -iE "agpl|gpl-3" && echo "FAIL: AGPL dep found" || echo "License audit OK"

# 5. Python lint / format / type-check
ruff check poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py
black --check poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py
mypy --strict poker_solver/solver.py poker_solver/hunl.py poker_solver/cli.py

# 6. PyO3 surface smoke test
python -c "
from poker_solver._rust import solve_hunl_postflop
print('_rust.solve_hunl_postflop importable:', callable(solve_hunl_postflop))
"

# 7. JSON config round-trip smoke
python -c "
from poker_solver.hunl import default_tiny_subgame, _serialize_hunl_config
config = default_tiny_subgame()
js = _serialize_hunl_config(config)
print(f'config JSON length: {len(js)} chars')
print(f'first 200 chars: {js[:200]}')
import json
parsed = json.loads(js)
assert 'starting_stack' in parsed
assert 'bet_size_fractions' in parsed
print('JSON config serialize OK')
"

# 8. Tiny river subgame end-to-end via Rust backend
python -c "
from poker_solver.hunl import default_tiny_subgame, HUNLPoker
from poker_solver.solver import solve
config = default_tiny_subgame()
game = HUNLPoker(config)
result = solve(game, iterations=100, backend='rust')
assert result.backend == 'rust'
assert len(result.average_strategy) > 0
print(f'Rust backend OK: {len(result.average_strategy)} infosets, expl={result.exploitability_history[-1]:.4f}')
"

# 9. Existing tests must still pass
pytest -x 2>&1 | tail -20
```

If any step fails, fix the issue before reporting done. If a verification reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails of `cargo build`, `cargo clippy`, `pip install -e .`, `pytest`, the river-subgame smoke test).
4. License attributions added (paste the module docstring headers).
5. Confirmation of `cargo tree` license audit (zero AGPL/GPL deps).
6. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
