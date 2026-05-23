# PR 6 spec — HUNL postflop solver port to Rust (production tier)

**Updated 2026-05-21 per consistency review:** (a) §4.4 clarifies that the Rust loader parses the nested `metadata` dict from PR 4's `.npz` (resolves blocker B1 — PR 4 stays authoritative as the writer of a single nested metadata dict; PR 6 un-nests on load); (b) §6.3 cross-references PR 4's `AbstractionRef` declaration (resolves blocker B2 — `source_path` is declared on PR 4's `AbstractionTables` via the new `AbstractionRef` field of `HUNLConfig.abstraction`, see PR 4 §6 amended note); (c) §4.1 Rust `HUNLConfig` mirror now includes `use_pcs: bool` (pre-empts PR 8's schema extension per consistency review I6 — see PR 8 §"Files to modify" amended note); (d) §7.3 diff-test tolerance language reaffirms the `1e-3` / `5e-3` cluster as canonical across PR 6/7/8/9.

**Updated 2026-05-22 per launch-readiness v2 review:** (e) §4.4 rewritten to match the committed PR 4 on-disk layout (`poker_solver/abstraction/buckets.py`). The `.npz` stores per-street **string-keyed** dict-of-dict indices (`*_board_index: dict[str, int]`, `*_hand_index: dict[str, dict[str, int]]`), each JSON-encoded inside a single uint8 array; **all** metadata (`schema_version`, `bucket_counts`, `feature_bins`, `seed`, `version`, …) is JSON-encoded inside a single one-element bytes array named `metadata`. The previous draft's `HandLookup` packed struct + top-level `bucket_counts` / `schema_version` / `feature_bins` / `seed` fields are gone; they live inside the parsed `metadata` dict and the loader reads them from there. Canonical board / hand IDs are **strings** (`canonical_board_key`, `canonical_hand_key`) produced by `canonicalize_for_suit_iso`, NOT `u32`. (f) §6.1/§6.3 wiring updated to call `resolve_abstraction_ref(cfg.abstraction)` (PR 4's LRU-cached resolver + version-check) rather than reaching into `cfg.abstraction.source_path` directly. (g) §6.1 dispatch-ordering invariant: when wiring the Rust HUNL solve path into Python `solver.solve()`, the new HUNL postflop branch must compose **AFTER** the PR 3.5 push/fold short-circuit (PR 9 §6 is canonical). Order: `pushfold → HUNL postflop (Rust if backend=='rust') → HUNL postflop Python fallback`.

## 1. Goal

Port the **Python HUNL postflop solver shipped in PR 5** (`poker_solver/hunl_solver.py` + `poker_solver/hunl.py` + `poker_solver/abstraction/`) to **Rust at `crates/cfr_core/`**, exposed through PyO3 as `poker_solver._rust.solve_hunl_postflop`. The port is **mechanical** — same algorithm (DCFR α=1.5, β=0, γ=2.0), same tree, same action menu, same bucket lookups, same chance enumeration. The only intentional differences are:

- Compact native data structures (flat `Vec<u32>` indexed tree instead of Python `dataclass` recursion) to give the **10-50× speedup** PLAN.md commits us to ("Python solve times are impractical at HUNL scale; Rust gives the 10-50× speedup").
- Native hand evaluation in `hunl_eval.rs` instead of the Python evaluator's eval call per leaf.
- A bucket-lookup table loaded once from PR 4's `.npz` and held in a `&[u8]` for O(1) reads.

The Rust port is **gated by a differential test** against the Python tier: PR 5's three fixtures (river-only, flop dry 3-size, flop dry full-menu) must produce strategies that match Python's to within tolerance (§6).

## 2. What PR 6 does NOT do

- **No preflop port.** Preflop is PR 9. PR 6 inherits PR 5's postflop-only restriction; preflop `HUNLConfig` is rejected up front by `solve_hunl_postflop` (Rust side mirrors Python's `ValueError`).
- **No UI.** PR 10. The CLI route from PR 5 (`poker-solver solve --game hunl --hunl-mode postflop --backend rust …`) is the only user surface PR 6 ships.
- **No NEON SIMD / cache-blocking / public chance sampling.** That's PR 8. PR 6's regret accumulator is a straightforward `Vec<f64>` per infoset (matches PR 5 byte layout). Vectorization comes later. **Rust should be readable + slow-but-correct first** — PR 8 is the perf PR, not PR 6.
- **No new abstraction artifact format.** PR 6 reads PR 4's `.npz` exactly as Python does (via `ndarray-npy`). No re-quantization, no on-disk repacking, no separate Rust-native format.
- **No multi-threading inside the CFR loop.** Like PR 5, PR 6 runs single-threaded DCFR. Parallelism is PR 8.
- **No `noambrown`-style vector CFR.** Noam Brown's `cpp/src/trainer.cpp` (MIT) carries per-infoset "hand-vectorized" CFR (regret stored as `[action × hand]` matrix for fast batch evaluation against an opponent range). That is an *abstraction-quality / range-condition* design choice on top of vanilla DCFR. PR 6 stays scalar (one regret value per (infoset, action)) — same as PR 5. **Decision deferred to user if vector CFR should land here instead of PR 8**; default is scalar.
- **No memory profiler.** PR 5's `MemoryProbe` (Python `psutil` calibration) is a Python-tier artifact; Rust's heap is harder to attribute granularly to streets and the perf PR (PR 8) will revisit memory layout. PR 6 just reports `solver.infosets.len()` and per-iteration wallclock through the existing Python wrapper.
- **No CFR variant work** (CFR+, MCCFR, external sampling, etc.). Same algorithm as PR 5.
- **No license drift.** Zero code copied from AGPL repos. See §3.
- **No bunching / blocker-aware features.** postflop-solver's bunching module is AGPL and outside our v1 scope (PR 5 explicitly skipped it; PR 6 inherits).
- **No solver-side rake.** Same assertion as PR 5: `rake_rate == 0.0 && rake_cap == 0`. PR 9 introduces rake throughout the stack.

## 3. License-aware sourcing strategy

The license audit in PLAN.md §6 is load-bearing for this PR — postflop is the first place we have direct counterparts in AGPL repos, and silent copying contaminates the project. Source-by-source policy:

| Source | License | Use in PR 6 |
|---|---|---|
| `references/code/noambrown_poker_solver/cpp/src/river_game.{h,cpp}` | **MIT** | **Canonical port reference.** Safe to study + port patterns from (Action struct shape, `legal_actions` bet-size enumeration, pot/contrib tracking). Attribution required in each ported file's module docstring. |
| `references/code/noambrown_poker_solver/cpp/src/cards.{h,cpp}` | **MIT** | Reference for the `Strength` evaluator type and hand-rank ordering; safe to port. |
| `references/code/noambrown_poker_solver/cpp/src/trainer.{h,cpp}` | **MIT** | Reference for DCFR-on-postflop control flow; we already structurally match this from PR 1's port. |
| `references/code/noambrown_poker_solver/cpp/src/vector_eval.{h,cpp}` | **MIT** | Reference for evaluator design. NOT ported (PR 6 stays scalar). |
| `references/code/open_spiel/open_spiel/games/universal_poker/` | **Apache 2.0** | Safe to study + adopt patterns with attribution. Useful for terminal/showdown handling. We already use open_spiel as the Kuhn/Leduc oracle in PR 1/2; same pattern extends here. |
| `references/code/slumbot2019/src/` (`hand_value_tree.cpp`, `card_abstraction*.cpp`) | **MIT** | Safe to port. Helpful for the 7-card hand evaluator design in `hunl_eval.rs`. Architecture inspiration for the abstraction lookup table layout. |
| `references/code/postflop-solver/src/*` | **AGPL v3** | **Read-only inspiration.** Never copy code, function bodies, or distinctive type names. The architectural ideas (flat tree, postflop subgame, action enumeration) are public knowledge — we may **independently re-derive** the same patterns from MIT/Apache sources or from `dcfr.py`. Cite postflop-solver in spec docs only, never in Rust comments. |
| `references/code/TexasSolver/` | **AGPL v3** | Same as postflop-solver — read-only inspiration. |
| `references/code/shark-2.0/` | **Unlicensed** | Treat as all-rights-reserved. Do not study for PR 6 — too much copy-risk surface. |

**Source-of-truth chain for PR 6:**
1. **First reference:** the Python tier (`poker_solver/hunl.py`, `poker_solver/hunl_solver.py`, `poker_solver/abstraction/`). Rust must match this byte-for-byte semantically.
2. **Second reference:** `noambrown_poker_solver` (MIT) for any postflop-specific pattern not in the Python tier.
3. **Third reference:** `open_spiel`, `slumbot2019` (MIT/Apache) for evaluator + edge-case patterns.
4. **Never:** AGPL repos. We *can* glance at them to confirm a reference number is sane (e.g., "1755 strategically-unique flops" — that's well-known regardless), but no code copy, no function-body translation, no naming-convention adoption.

**Module-level attribution template** to use in each new Rust file (matches `leduc.rs` precedent):

```rust
//! HUNL postflop game state (Rust production tier).
//!
//! Adapted from poker_solver/hunl.py (project-internal, MIT) for semantics;
//! action-enumeration shape mirrors
//! references/code/noambrown_poker_solver/cpp/src/river_game.cpp (MIT) by
//! pattern, not by code transcription.
//!
//! NEVER copy from references/code/postflop-solver (AGPL) or
//! references/code/TexasSolver (AGPL).
```

The `check_pr.sh` license audit (per PLAN.md §4 step 6) is responsible for the runtime check that no new AGPL deps were added.

## 4. Files to create

In `crates/cfr_core/src/`:

### 4.1 `hunl.rs` — `HUNLState` + `impl Game for HUNLState`

Field-for-field port of `poker_solver/hunl.py::HUNLState`. Must implement the `Game` trait already declared in `crates/cfr_core/src/game.rs`. Reference: Python source is the spec; structural pattern matches `crates/cfr_core/src/leduc.rs` (which is the precedent for porting a Python game state to Rust).

**Type sketch:**

```rust
#[repr(C)]
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub enum Street { Preflop = 0, Flop = 1, Turn = 2, River = 3, Showdown = 4 }

#[derive(Clone, Debug)]
pub struct HUNLState {
    pub hole_cards: [[u8; 2]; 2],       // card-int encoding from `card_to_int`
    pub board: ArrayVec<u8, 5>,         // 0..5 cards
    pub street: Street,
    pub contributions: [i32; 2],        // INTEGER CENTS, never float (PR 3 invariant)
    pub stacks: [i32; 2],
    pub street_history: Vec<u8>,        // ActionId stream
    pub street_aggressor: i8,
    pub street_num_raises: u8,
    pub to_call: i32,
    pub cur_player: i8,
    pub folded: [bool; 2],
    pub all_in: [bool; 2],
    pub config: Arc<HUNLConfig>,        // shared config; Arc so apply() is cheap
}

#[derive(Clone, Debug)]
pub struct HUNLConfig {
    pub starting_stack: i32,
    pub small_blind: i32,
    pub big_blind: i32,
    pub ante: i32,
    pub starting_street: Street,
    pub initial_board: ArrayVec<u8, 5>,
    pub initial_pot: i32,
    pub initial_contributions: [i32; 2],
    pub preflop_raise_cap: u8,
    pub postflop_raise_cap: u8,
    pub bet_size_fractions: Vec<f64>,
    pub include_all_in: bool,
    pub force_allin_threshold: i32,
    pub min_bet_bb: i32,
    pub abstraction: Option<Arc<AbstractionTables>>,
    /// Public Chance Sampling opt-in flag. Default `false`; PR 8 introduces
    /// the actual PCS code path. Pre-included here to avoid a forced schema
    /// migration when PR 8 lands (per consistency review I6).
    pub use_pcs: bool,
}
```

**Functions to port (1:1 from `poker_solver/hunl.py`):**

- `HUNLState::initial(config: Arc<HUNLConfig>) -> Self` — posts blinds + antes.
- `is_terminal(&self) -> bool` — fold or showdown check.
- `utility(&self) -> [f64; 2]` — fold-vs-showdown in **BB units** (`/ config.big_blind` at the leaf, matches Python; PR 3 §"Terminal states + utility" locks this).
- `current_player(&self) -> i8` — `-1` for chance, `0`/`1` for players.
- `chance_outcomes(&self) -> Vec<(u8, f64)>` — uniform over remaining-deck minus blockers. Per-card; sequential single-card runouts (PR 3 §"Decisions deferred" #2).
- `legal_actions(&self) -> Vec<u8>` — delegates to a Rust port of `action_abstraction.enumerate_legal_actions`; see §4.1.5.
- `apply(&self, action: u8) -> Self` — mutates contribs, stacks, history, num_raises, current_player, street as needed.
- `infoset_key(&self, player: u8) -> String` — must match Python's format byte-for-byte:
  - lossless: `f"{player_hole}|{board}|{street_token}|{betting_history}"` (PR 3 §"Infoset key")
  - bucketed: `f"b{bucket_id}|{street_token}|{betting_history}"` (PR 4 §3.5)
  - **Critical:** integer formatting (`{bucket_id}`, bet amounts in cents) and ordering of card sort must match Python's `f"…"` output character-for-character.

**Action ID constants** — replicate PR 3 `action_abstraction.py` integer constants (`ACTION_FOLD = 0`, `ACTION_CHECK = 1`, …, `ACTION_ALL_IN = 13`) as `pub const` in `hunl.rs`. Single source of truth: the Python file. Rust constants are checked against Python's by an explicit test (`test_hunl_action_ids_match_python`).

**Action enumeration logic** is identical to the Python tier:
- bet sizes computed from `pot * fraction`, rounded to nearest int (banker's rounding via `(x + 0.5).floor()` to match Python's `round()` semantics on positive integers — verify with a parity test).
- raise sizes computed from `(pot + to_call) * fraction` added on top of the call, per PR 3 §"How bet sizes map to action ids."
- min-bet clamp = 1 BB; min-raise = last bet/raise increment; max = stack.
- dedup: identical chip outcomes collapsed; `ACTION_ALL_IN` replaces oversized bets (PR 3 §"Min-bet/min-raise rules" 1-5).
- `force_allin_threshold` snaps near-shove abstractions to all-in (PR 3 §"Min-bet/min-raise rules" 5).
- Raise cap: preflop 4, postflop 3 (PR 3 §"Raise cap enforcement"). At-cap → only fold/call/all-in legal.

**Integer arithmetic discipline.** Like Python's PR 3 invariant: **all chip values are `i32` cents**. Only the pot-fraction multiplications cross to `f64`, then immediately round back to `i32`. No `f64` chip accumulator anywhere in `hunl.rs`. (Audit-agent focus area.)

**Card encoding** must use Python's `card_to_int` mapping (PR 3 §"Card → integer mapping"): `card_int = (rank * 4) + suit`, range `[8, 59]`. Encoded as `u8` in `hole_cards` / `board` fields. Add `card_to_int(rank: u8, suit: u8) -> u8` helper as `const fn` for compile-time card constants in tests.

### 4.1.5 Internal helpers (still in `hunl.rs`)

Pure functions ported from `poker_solver/action_abstraction.py`:

- `enumerate_legal_actions(ctx: &ActionContext) -> Vec<u8>` — main entry.
- `compute_bet_amount(action_id: u8, ctx: &ActionContext) -> i32`
- `compute_raise_to(action_id: u8, ctx: &ActionContext) -> i32`
- `ActionContext { pot, to_call, stacks, contributions, cur_player, street, street_num_raises, street_aggressor, big_blind, bet_size_fractions, preflop_raise_cap, postflop_raise_cap, force_allin_threshold, min_bet_bb, include_all_in }` — `repr(C)` Plain Old Data struct.

These live in `hunl.rs` (single owner) rather than a separate `action_abstraction.rs` because the Python side is also flat-functional and the Rust call sites are entirely internal to `HUNLState::legal_actions` / `HUNLState::apply`. (Alternative considered: separate module for testability. Rejected: differential test against Python is the integration check.)

### 4.2 `hunl_tree.rs` — compact tree representation

PR 5's Python solver walks the tree on the fly via recursion (one `HUNLState` per stack frame). At HUNL postflop scale this is slow even in Rust because each `apply()` allocates a fresh state. PR 6 introduces a **pre-built flat tree** with indexed children, walked by the DCFR loop.

**Rationale:** matches `noambrown/cpp/src/river_game.h::Tree` (MIT, safe to port the shape):

```cpp
struct TreeNode {
    int player = -1;           // -1 = chance, 0/1 = player, -2 = terminal
    int terminal_winner = -1;  // -1 = no fold (showdown), else fold winner
    int contrib0 = 0;
    int contrib1 = 0;
    int action_count = 0;
    std::vector<int> next;     // child node indices
};
struct Tree { int root; int max_actions; int max_depth; std::vector<TreeNode> nodes; };
```

**Rust shape** (re-derived, attribution to noambrown in module docstring):

```rust
#[derive(Clone, Debug)]
pub struct HUNLTreeNode {
    pub player: i8,               // -1 chance, 0/1 player, -2 terminal
    pub terminal_kind: TerminalKind,
    pub contrib: [i32; 2],
    pub street: Street,
    pub num_actions: u8,
    pub legal_actions: ArrayVec<u8, 14>,
    pub children: [u32; 14],      // flat-table indices into `Tree::nodes`
    pub infoset_key: Option<String>,  // None for chance/terminal
    pub chance_action: Option<u8>,    // the card dealt entering this node
    pub chance_prob: f64,             // for sampling; precomputed
    // For chance nodes:
    pub chance_outcomes: ArrayVec<(u8, f64), 52>,
}

pub enum TerminalKind {
    NonTerminal,
    Fold { winner: u8, contribution_loss: i32 },
    Showdown { board_complete: bool },
}

pub struct HUNLTree {
    pub nodes: Vec<HUNLTreeNode>,
    pub root: u32,
    pub max_depth: u32,
    pub max_actions: u8,
    pub config: Arc<HUNLConfig>,
}
```

**Build function:** `HUNLTree::build(config: Arc<HUNLConfig>) -> HUNLTree` — recursive build via `HUNLState`'s `apply` / `chance_outcomes`, registering each unique state as a node. Memoize by (cur_player, contribs, street, history) to dedupe states reachable via different chance orderings (matches postflop-solver's `flatten_action_tree` shape; we re-derive independently — this is a standard CSP folding pattern, not novel to AGPL repos).

**Trade-off:** building the tree up-front costs RAM (10–14 GB per PLAN.md at HUNL postflop), but saves the per-iteration cost of `apply()` on hot paths. Both PR 5 and `noambrown` follow this approach; PR 6 inherits it.

**Falling back to on-the-fly traversal:** if RAM pressure exceeds the budget at tree-build time, the solver can fall back to PR 1/2-style state-machine traversal (no flat tree). Default for PR 6: **flat tree.** Override via `Config::build_flat_tree: bool` (default `true`). Spec defaults to flat-tree; user override if budget concerns arise.

### 4.3 `hunl_eval.rs` — hand evaluator port

Port of `poker_solver/evaluator.py`. The Python evaluator is the source of truth (used by PR 4's equity features, PR 5's solver, every existing test). Rust must produce identical hand ranks (same integer comparison semantics) for the same 7-card input.

**Approach:** the Python `evaluator.py` (per PR 5 spec mention) currently evaluates ~200K hands/sec. We can match (and exceed) that in Rust by porting the same algorithm — likely a 2+3 ranking pass (best 5 from 7 cards) returning a comparable `Strength` value.

**Two-step delivery:**
1. **Step 1 (this PR):** straight port. Match Python's algorithm exactly. Validate with a `tests/test_hunl_eval_rust.rs` test that round-trips ~10K known hand-vs-hand comparisons against the Python evaluator (called via PyO3 in the test).
2. **Step 2 (later, PR 8):** swap to a `slumbot2019`-style 7-card lookup table (~133M entries, ~500 MB precomputed). 100× speedup; out of scope for PR 6.

**Interface:**

```rust
pub struct Strength(pub u32);  // higher = stronger; compares with `<`

impl Strength {
    pub fn evaluate_7(cards: &[u8; 7]) -> Strength { ... }
    pub fn evaluate_5(cards: &[u8; 5]) -> Strength { ... }
}
```

**Reference:** `noambrown_poker_solver/cpp/src/cards.h` declares `Strength` (MIT, may be ported). `slumbot2019/src/cards.cpp` has the canonical 7-card evaluation pattern (MIT, may be ported). Cross-check against `poker_solver/evaluator.py` for correctness — Python is the truth.

**Determinism + tie-breaking.** Python ties split utility 50/50 at the terminal. Rust must do the same — the evaluator returning equal `Strength` values triggers the tie path in `HUNLState::utility`. Tested explicitly.

### 4.4 `abstraction.rs` — card-bucket lookup

Loads PR 4's `.npz` abstraction file and exposes a single read-only API.

**Real on-disk format (per committed PR 4 — `poker_solver/abstraction/buckets.py::save_abstraction` / `load_abstraction`):**

```
abstraction_v1.npz   (np.savez_compressed)
  flop_assignments   : uint8[total_flop_hands]    # flat bucket-id array
  turn_assignments   : uint8[total_turn_hands]
  river_assignments  : uint8[total_river_hands]
  flop_board_index   : uint8[]   # one-element bytes array; JSON-encoded dict[str, int]
  turn_board_index   : uint8[]   # JSON bytes; dict[str, int] mapping canonical_board_key -> start offset
  river_board_index  : uint8[]   # JSON bytes; dict[str, int]
  flop_hand_index    : uint8[]   # JSON bytes; dict[str, dict[str, int]]
  turn_hand_index    : uint8[]   # JSON bytes; nested dict — board_key -> hand_key -> within-board offset
  river_hand_index   : uint8[]   # JSON bytes; nested dict
  metadata           : uint8[]   # one-element bytes array; JSON-encoded dict[str, object]
                                 # contains: schema_version, bucket_counts, feature_bins,
                                 #          seed, version, and any other writer-side keys
```

The bucket id for `(board, hole)` on a given street is:

```
offset = board_index[canonical_board_key] + hand_index[canonical_board_key][canonical_hand_key]
bucket_id = assignments[offset]
```

where `canonical_board_key` and `canonical_hand_key` are **strings** produced by Agent A's `canonicalize_for_suit_iso(board, hole) -> (board_key, perm_index)` (PR 4 §"Stage 4"). They are NOT integers — they are sorted-by-(rank,suit) joined card-strings.

**Resolution of consistency-review blocker B1 (post-launch-readiness-v2 amendment).** PR 4 §4 Stage 5 is authoritative on the on-disk layout: `metadata` is **one JSON-encoded dict** inside the `.npz`, NOT separate top-level NumPy arrays per field. **Every dict-of-dict index (board_index, hand_index) is ALSO JSON-encoded inside a single bytes array** — there are NO `Vec<u32>` board-offset arrays at the top level. PR 6's Rust loader is responsible for parsing the JSON bytes on load (one `serde_json::from_slice` call per index + one for `metadata`). PR 4 is unchanged on this seam. Add a `_decode_json_bytes(npz: &NpzFile, key: &str) -> serde_json::Value` helper in `abstraction.rs`; Python writes each dict as `json.dumps(d, sort_keys=True, separators=(',', ':')).encode()` for byte-determinism, so the Rust side parses with `serde_json::from_slice`.

**Rust loader:**

```rust
use std::collections::HashMap;

#[derive(Clone, Debug, serde::Deserialize)]
pub struct AbstractionMetadata {
    pub schema_version: u8,
    pub version: String,                    // matches HUNLConfig.abstraction.version
    pub bucket_counts: Vec<u16>,            // [K_flop, K_turn, K_river]
    pub feature_bins: u16,
    pub seed: u64,
    // Any additional writer-side keys may exist; tolerate them via #[serde(flatten)] catch-all
    // or by deserializing into serde_json::Value and pulling fields by name.
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

#[derive(Clone, Debug)]
pub struct AbstractionTables {
    pub flop_assignments: Vec<u8>,
    pub turn_assignments: Vec<u8>,
    pub river_assignments: Vec<u8>,

    // String-keyed indices, parsed from the JSON-bytes blobs in the .npz.
    pub flop_board_index: HashMap<String, u32>,
    pub turn_board_index: HashMap<String, u32>,
    pub river_board_index: HashMap<String, u32>,

    pub flop_hand_index: HashMap<String, HashMap<String, u32>>,
    pub turn_hand_index: HashMap<String, HashMap<String, u32>>,
    pub river_hand_index: HashMap<String, HashMap<String, u32>>,

    // Parsed once from the single `metadata` JSON blob.
    pub metadata: AbstractionMetadata,

    // Set by load_abstraction(path); NOT persisted on disk. Matches Python's
    // AbstractionTables.source_path field. Used by the version-check seam.
    pub source_path: std::path::PathBuf,
}

pub fn load_abstraction(path: &Path) -> Result<AbstractionTables, AbstractionError>;

pub fn lookup_bucket(
    tables: &AbstractionTables,
    board: &[u8],
    hole: &[u8; 2],
    street: Street,
) -> i32 {
    // Preflop returns -1.
    // Otherwise:
    //   1. Canonicalize (board, hole) -> (board_key: String, hand_key: String) via
    //      a port of poker_solver/abstraction/equity_features.canonicalize_for_suit_iso.
    //   2. Look up board_index[board_key] -> board_offset (u32).
    //   3. Look up hand_index[board_key][hand_key] -> within-board offset (u32).
    //   4. Return assignments[board_offset + within_board_offset] as i32.
    // MUST be byte-for-byte identical to Python's lookup_bucket output for every
    // valid (board, hole, street) input.
}
```

**Dependency:** `ndarray-npy = "0.9"` for `.npz` reading (parses each entry into a `ndarray::Array1<u8>` or similar; the JSON-encoded dicts come out as `Vec<u8>`). **NPY/NPZ format is open + Apache 2.0** (NumPy spec). The `ndarray-npy` crate itself is MIT/Apache 2.0 dual-licensed — verify with `check_pr.sh` license audit.

**Canonicalization parity.** Python's `canonicalize_for_suit_iso(board, hole) -> (board_key, perm_index)` plus `_apply_suit_perm_to_hand(hole, perm_index) -> hand_key` (see `poker_solver/abstraction/buckets.py::_canonicalize` and `_apply_suit_perm_to_hand`) must produce identical **string** keys on the Rust side. This is the *single most fragile cross-tier seam* — if Rust's sort differs by one element, the resulting string differs and the HashMap miss cascades into every post-flop bucket diverging. Add a dedicated test (`test_abstraction_canonicalization_matches_python`) that runs 10K random (board, hole) inputs through both tiers and asserts equal string keys.

**Schema-version check.** Rust loader asserts `tables.metadata.schema_version == 1`; mismatch → error with a clear message ("rebuild abstraction via `poker-solver precompute-abstraction`"). Mirrors Python's check in `load_abstraction`.

**Version-check seam (B2 follow-up).** The wiring code that calls `load_abstraction(path)` MUST also verify `tables.metadata.version == ref.version` (where `ref: AbstractionRef`) and raise `AbstractionError::VersionMismatch` on drift. This matches Python's `resolve_abstraction_ref`, which is the canonical entry point (see §6.3) — loud failure, never silent stale-artifact reuse.

### 4.5 `hunl_solver.rs` — postflop solve entrypoint

The Rust counterpart of `poker_solver/hunl_solver.py::solve_hunl_postflop`. Owns the DCFR loop wired to PR 6's flat tree + abstraction + evaluator.

**Top-level call:**

```rust
pub struct HUNLSolveOutput {
    pub average_strategy: HashMap<String, Vec<f64>>,
    pub exploitability: f64,
    pub game_value: f64,
    pub iterations: u32,
    pub wallclock_seconds: f64,
    pub infoset_count: u32,
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

**Algorithm:**
1. Validate config (same checks as Python Stage A: postflop-only, rake=0, board-length matches `starting_street`).
2. Build flat tree via `HUNLTree::build` (§4.2).
3. Allocate `HashMap<String, InfosetData>` (reuses `crate::dcfr::InfosetData`; PR 1's `DCFRSolver<G>` is generic).
4. For `iterations` rounds: walk the tree via the generic `DCFRSolver::cfr`. **No new CFR code needed** — the existing solver in `crates/cfr_core/src/dcfr.rs` already handles any `Game` implementor.
5. Optional early-exit: if `target_exploitability.is_some()` and current exploitability beats target, stop. (Python tier exposes this same option per PR 5 §14 #2.)
6. Compute `exploitability` and `game_value` via the existing `crate::solver::exploitability::<HUNLState>`. **Caveat:** the existing `exploitability` walks the tree without using the flat representation — for HUNL postflop trees with millions of nodes this is slow. **PR 6 spec defers full Rust BR/exploitability optimization to a follow-up.** Default: use existing `solver::exploitability` (slow but correct). If user wants fast exploitability, defer to a Python-tier reference call (cheaper because Python's `solver.exploitability` is already plenty fast for small fixtures; full HUNL exploitability is expensive in either tier).

**Recovery for the "this is too slow" case:** the Python tier's `solver._solve_rust` recomputes exploitability via Python after Rust returns the strategy — same pattern as Kuhn/Leduc (see `poker_solver/solver.py:295`). **Default for PR 6: same pattern — Rust returns strategy + iteration count, Python recomputes exploitability + game_value.** This (a) matches the existing precedent, (b) lets diff tests compare apples-to-apples, (c) sidesteps Rust BR optimization until PR 8.

## 5. PyO3 surface

Add to `crates/cfr_core/src/lib.rs`:

```rust
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
) -> PyResult<PyObject>;
```

**Why JSON for the config?** `HUNLConfig` is a complex frozen dataclass on the Python side. Three viable options:

| Option | Pro | Con |
|---|---|---|
| Pass a `dict` and parse in Rust | Standard PyO3 pattern | Verbose; many fields |
| Pass JSON string | Simple Rust side (serde), easy to log | Round-trip serialization cost (small) |
| Build full PyO3-bound `HUNLConfig` Rust struct | Most idiomatic | Largest surface; needs PyO3 macros on every field |

**Default: JSON string.** Single boundary, easy to inspect, identical-shape to the Python dataclass dump. ~50 lines of `serde` derive in Rust. Decision flagged for user override (§10 #2).

**Return shape** matches Python's existing `SolveResult`-ish dict:

```python
{
    "average_strategy": dict[str, list[float]],
    "exploitability": float,    # if Rust computed it; else 0.0 + Python recomputes
    "game_value": float,        # if Rust computed it; else 0.0 + Python recomputes
    "iterations": int,
    "wallclock_seconds": float,
    "infoset_count": int,
    "backend": "rust",
}
```

**PyO3 GIL handling.** The DCFR loop is pure-Rust (no Python callbacks). We release the GIL for the duration of `solve_hunl_postflop` via `py.allow_threads(|| { … })`. Critical for multi-call scenarios (UI thread + solver thread). See §9 for the GIL risk note.

**Module export:** add `m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;` to the `_rust` `#[pymodule]` block. Following the Kuhn / Leduc pattern exactly.

## 6. Python tier integration

### 6.1 `poker_solver/solver.py::_solve_rust` — add HUNL branch

Append to the `_solve_rust` dispatch (existing pattern in `poker_solver/solver.py:268-305`):

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
        # Resolve through the LRU-cached helper so the version-check + cache reuse
        # hold across solve calls. The Rust side reloads the .npz independently
        # from `tables.source_path` (cheap because the OS page cache is warm and
        # `resolve_abstraction_ref` already verified version match).
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
    game_value = _game_value(game, avg)
    return SolveResult(
        average_strategy=avg,
        exploitability_history=[expl],
        game_value=game_value,
        iterations=int(raw["iterations"]),
        backend="rust",
    )
```

**Same pattern as Kuhn/Leduc:** Python recomputes exploitability + game_value from the Rust-returned strategy. Removes any cross-tier floating-point drift in those values.

**Dispatch ordering invariant (PR 9 §6 is canonical).** The new HUNL postflop branch must compose **AFTER** the PR 3.5 push/fold short-circuit and **BEFORE** any preflop dispatch. Canonical ordering, head-to-tail:

```
solve() / _solve_rust() dispatch order:
  1. push/fold short-circuit (PR 3.5; routes ≤15-BB HUNL preflop to the chart fast path)
  2. HUNL postflop Rust branch (THIS PR — when backend == "rust" and game is HUNLPoker postflop)
  3. HUNL postflop Python fallback (PR 5 — when backend != "rust" and game is HUNLPoker postflop)
  4. HUNL preflop branch (PR 9 — not implemented in PR 6; raise NotImplementedError)
  5. Kuhn/Leduc branches (PR 1/2 — unchanged)
```

Inserting the HUNL Rust branch **before** the push/fold check would silently re-route low-stack postflop solves through the full DCFR loop instead of the chart fast path. PR 9 §6 declares this ordering canonical; PR 6 inherits it. Audit-agent and Agent B must both verify this composition order.

**`resolve_abstraction_ref` is canonical, never reach into `cfg.abstraction.source_path` directly.** PR 4 ships `resolve_abstraction_ref(ref: AbstractionRef) -> AbstractionTables` as the **LRU-cached + version-checked** entry point (`@lru_cache(maxsize=4)` keyed on `(source_path, version)` — raises `ValueError` on metadata-version mismatch). Bypassing it (e.g., `str(cfg.abstraction.source_path)` directly into `_rust_solve_hunl`) skips the cache and the version check, allowing stale artifacts to silently load. Always go through the resolver, then pass the path string from `tables.source_path` to Rust.

### 6.2 `_serialize_hunl_config(config: HUNLConfig) -> str`

Add to `poker_solver/hunl.py` (the natural owner). Dumps every field of `HUNLConfig` to a JSON dict matching Rust's `serde::Deserialize` shape. Includes the abstraction's `source_path` (so Rust can `load_abstraction` independently from the path stored on the config object — avoids serializing the entire bucket table through the PyO3 boundary).

### 6.3 `HUNLConfig.abstraction` — track the source path (via PR 4's `AbstractionRef`)

**Resolution of consistency-review blocker B2.** PR 4's committed code (`poker_solver/abstraction/buckets.py`) declares `HUNLConfig.abstraction: Optional[AbstractionRef] = None`, where `AbstractionRef` is a small dataclass `(source_path: str, version: str)`. The Rust solver needs only the on-disk path (not the full bucket-table object) across the PyO3 boundary, so this field is the seam: Python carries it on the config; Rust loads the `.npz` from the path independently via `load_abstraction(path)`. PR 6 does NOT add a new field; it consumes the one PR 4 already declared.

**Canonical resolver — `resolve_abstraction_ref(ref) -> AbstractionTables`.** PR 4 ships this helper (also in `poker_solver/abstraction/buckets.py`) as the LRU-cached + version-checked entry point for going from `AbstractionRef` to a loaded `AbstractionTables`. Python tier consumers (including PR 6's `_solve_rust` HUNL branch, §6.1) MUST go through this resolver — never reach into `cfg.abstraction.source_path` directly. The Rust side gets the path string from the resolved `tables.source_path`. Loader confirms the runtime `AbstractionTables.metadata.version` matches `config.abstraction.version` (loud error on mismatch) — this check is **already enforced inside `resolve_abstraction_ref` on the Python side**, so the Rust loader's version check is defense-in-depth (still required per spec §4.4).

### 6.4 `poker_solver/__init__.py`

No new public exports. `solve_hunl_postflop` (Rust) is internal; users still call `solve(game, …, backend="rust")` as the entry point. Matches Kuhn/Leduc precedent.

### 6.5 `poker_solver/cli.py`

Add `--backend rust` support to the existing `solve --game hunl --hunl-mode postflop` path. Defaults to `python` (PR 5 behavior). User must opt in to Rust.

## 7. Differential test scope

PR 6's gating test is `tests/test_hunl_diff.py`. The scope is **deliberately narrower** than Kuhn/Leduc's bit-exact diff because HUNL state space + HashMap iteration order × float order makes bit-exact infeasible at scale.

### 7.1 Comparable scope: small postflop subtrees

**Test 1 (river-only subgame, no abstraction):**
- Fixture: PR 5's `default_tiny_subgame()` (`AhKc` vs `QdQh` on `As7c2dKh5s`, SPR 1, full 6-size menu).
- Iterations: 1000.
- **Assertion:** Python and Rust strategies match per-infoset-per-action within `1e-3` (relative tolerance with absolute floor 1e-6).
- **Why not bit-exact:** Rust HashMap iteration order is non-deterministic by default (randomized seed). Per-iteration regret accumulation order differs ⇒ floats accumulate differently. We can either (a) lock HashMap to deterministic seed for testing, or (b) accept 1e-3 tolerance and document. **Default: 1e-3 tolerance**, matches what postflop-solver's own diff tests use against their reference implementations (read-only inspiration).
- Wall-clock: <60s on the MacBook for both tiers (river-only is tiny).

**Test 2 (single flop spot, restricted bet menu, tiny synthetic abstraction):**
- Fixture: PR 5's Fixture 2 setup (dry flop `As7c2d`, 100 BB, 3 bet sizes 33/75/200, 3-cap), with PR 4's `tiny_synthetic_abstraction()` (bucket_counts=(4,2,2)).
- Iterations: 200 (smoke level).
- **Assertion:** Python and Rust strategies match within `5e-3` per-action (looser because the flop tree has more chance branching and HashMap order × float order interact more).
- Wall-clock: <5 min Python, <30 s Rust.

**Test 3 (Rust-only correctness checks — `tests/test_hunl_rust.rs`):**
- Construct the river-only subgame state in Rust; assert `legal_actions()` matches Python's expected list (load Python via PyO3 in the test).
- Walk the tree to terminal via a fixed action sequence; assert `utility()` matches Python's.
- Test `infoset_key` for both lossless and bucketed inputs against Python's output.
- Bucket-lookup parity (`test_abstraction_canonicalization_matches_python`): 10K random (board, hole) inputs.

### 7.2 Out-of-scope diff comparisons

- **Full HUNL flop diff** is impractical because Python solve time on Fixture 2 (default abstraction 256/128/64) is 10s of hours, while Rust may take 10s of minutes. Running both for diff requires multi-day total wallclock. **Documented as a known limit** — once the Rust port has differential-tested against Python on the smaller fixtures, larger fixtures rely on the Rust → Python correctness chain established at the small scale, plus the noambrown river-spot diff (PR 7).
- **HUNL preflop diff:** N/A. Preflop port is PR 9.
- **Bit-exact strategy match:** abandoned. The two implementations are mathematically equivalent up to float ordering; the strategy converges to the same Nash distribution but per-iteration values diverge.

### 7.3 Tolerance choice rationale

Why 1e-3 (not 1e-2 or 1e-6)?

- 1e-6 would require lock-stepping HashMap iteration order across tiers + identical float-reduction trees. Both are achievable (BTreeMap with deterministic ordering) but cost performance. Punt to PR 8 if needed.
- 1e-3 is the level at which strategy *behavior* is indistinguishable for poker purposes — a 0.1% mix difference between two actions has no exploitable consequence at the typical CFR convergence threshold.
- 1e-2 is too loose; convergence at this level still has ~1% noise in average-strategy values, which we expect to be at-or-below the tolerance.

Spec uses **1e-3** for the river-only fixture (tighter), **5e-3** for the flop fixture (looser due to chance branching). Decision flagged for user (§10).

## 8. Three-agent fan-out plan

Matches PR 3/4/5 pattern: tight per-agent ownership, parallel execution, integration at end.

### 8.1 Agent A — game state + tree + eval

**Owns:** `crates/cfr_core/src/hunl.rs`, `crates/cfr_core/src/hunl_tree.rs`, `crates/cfr_core/src/hunl_eval.rs`.

**Does NOT touch:** `abstraction.rs`, `hunl_solver.rs`, `lib.rs`, any Python file, any test file.

**Deliverables:**
- `HUNLState`, `HUNLConfig`, `Street` (mirror of Python types).
- `impl Game for HUNLState` (full trait, ported from `poker_solver/hunl.py`).
- `ACTION_FOLD = 0`, …, `ACTION_ALL_IN = 13` constants matching Python.
- Internal `ActionContext` + `enumerate_legal_actions` + `compute_bet_amount` + `compute_raise_to`.
- `HUNLTree` + `HUNLTreeNode` + `HUNLTree::build`.
- `Strength` + `evaluate_5` + `evaluate_7` matching Python's evaluator (cross-validated via existing test pattern — Agent A writes the Rust-only unit tests, Agent C cross-tier diff).
- Module-level attribution docstrings per §3 template.
- Zero clippy warnings.
- Tests in `crates/cfr_core/tests/hunl_state_unit.rs` covering: blinds posted correctly, fold path, raise cap enforcement, all-in absorption, infoset key canonicalization. (Mirrors PR 3 `tests/test_hunl_core.py` Tests 1–18 but in Rust.)

**Interface lock:** Agent A's surface (`HUNLConfig`, `HUNLState`, `HUNLTree`, `Strength`) is what Agent B imports. Spec locks the field shapes in §4.1, §4.2, §4.3.

### 8.2 Agent B — abstraction + solver pipeline + PyO3 + Python integration

**Owns:** `crates/cfr_core/src/abstraction.rs`, `crates/cfr_core/src/hunl_solver.rs`, `crates/cfr_core/src/lib.rs` (extending the existing file), `poker_solver/solver.py` (small `_solve_rust` extension), `poker_solver/hunl.py` (adding `_serialize_hunl_config` + `source_path` field), `poker_solver/cli.py` (adding `--backend rust`).

**Does NOT touch:** `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`, any test file.

**Deliverables:**
- `AbstractionTables` Rust struct + `load_abstraction` + `lookup_bucket`.
- `ndarray-npy` dependency added to `crates/cfr_core/Cargo.toml`.
- `solve_hunl_postflop` Rust entry (calls Agent A's `HUNLState` + `HUNLTree` + existing `DCFRSolver<G>`).
- PyO3 binding: `_rust.solve_hunl_postflop(config_json, abstraction_path, iterations, alpha, beta, gamma, target_exploitability, seed)`.
- Python serialization: `_serialize_hunl_config` in `hunl.py`.
- Python routing: extends `_solve_rust` in `solver.py` to handle `HUNLPoker` (postflop branch only; preflop raises `NotImplementedError` pointing at PR 9).
- `--backend rust` flag on the CLI.

**Interface lock:** Agent B imports Agent A's types via `crate::hunl::*` and `crate::hunl_tree::*`. Agent A's shapes are locked by §4.1–§4.3.

### 8.3 Agent C — tests

**Owns:** `tests/test_hunl_diff.py`, `crates/cfr_core/tests/test_hunl_rust.rs`.

**Does NOT touch:** any non-test file.

**Deliverables:**

**`tests/test_hunl_diff.py` (~8 tests):**
1. `test_hunl_river_subgame_diff_python_vs_rust` — Test 1 from §7.1.
2. `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` — Test 2 from §7.1.
3. `test_hunl_rust_validates_postflop_only` — passing a preflop config raises `NotImplementedError`.
4. `test_hunl_rust_validates_board_length` — 4-card board with `starting_street=Street.FLOP` raises clear error.
5. `test_hunl_rust_strategy_sums_to_one` — every infoset's returned probs sum to 1.0 ± 1e-9.
6. `test_hunl_rust_deterministic_with_seed` — same seed + config → identical strategy.
7. `test_hunl_rust_exploitability_matches_python_recompute` — Python's `exploitability(game, rust_strategy)` is finite, non-negative, and matches the value from `solve(game, …, backend="python")` within `1e-2` after enough iterations.
8. `test_hunl_rust_action_ids_match_python_constants` — Rust `ACTION_FOLD`, …, `ACTION_ALL_IN` == Python's via PyO3 introspection.

**`crates/cfr_core/tests/test_hunl_rust.rs` (~12 tests):**
1. `test_hunl_initial_state_blinds_posted_correctly` — Rust-side blinds posted (100 BB stacks).
2. `test_hunl_legal_actions_at_river_subgame_root` — Rust matches Python's expected list.
3. `test_hunl_apply_advances_state_correctly` — manual action sequence, terminal utility correct.
4. `test_hunl_infoset_key_lossless_format` — lossless format matches Python byte-for-byte for 100 random states.
5. `test_hunl_infoset_key_bucketed_format` — bucketed format matches Python byte-for-byte for 100 random (state, abstraction) pairs.
6. `test_abstraction_canonicalization_matches_python` — 10K random (board, hole) inputs canonicalize to same IDs.
7. `test_abstraction_lookup_bucket_matches_python` — 10K random inputs return identical bucket IDs.
8. `test_hunl_tree_build_terminates` — for the river subgame, `HUNLTree::build` returns a finite tree with expected node count (loose bounds matching PR 3's tree-size estimate).
9. `test_hunl_strength_eval_matches_python` — 1000 random 7-card hands evaluated; comparisons (hand_a > hand_b) match Python.
10. `test_hunl_strength_eval_handles_ties` — known tied 5-card hands → equal `Strength`.
11. `test_hunl_solve_river_subgame_smoke` — calls `solve_hunl_postflop` for 100 iterations on the river subgame, returns non-empty strategy.
12. `test_hunl_solve_reject_preflop` — passing preflop config returns an error.

**Parallelism rationale:** Agent C runs concurrently with A+B because the spec is the interface lock. Tests use only the public types declared in §4.1–§4.5 + the PyO3 surface in §5.

**Edge-case allowance:** Agent C may write tests that surface genuine spec ambiguities. Same rule as PR 3/4/5: **the spec is the source of truth** — we update the impl or update the spec, not silently tweak the test.

## 9. Critical correctness items

1. **Byte-for-byte identical infoset keys.** Both lossless and bucketed formats. Rust's `format!` output must match Python's `f""` output character for character. Tested via `test_hunl_infoset_key_lossless_format` + `test_hunl_infoset_key_bucketed_format`.

2. **Byte-for-byte identical bucket lookups.** The canonicalization (`canonicalize_for_suit_iso` + `_apply_suit_perm_to_hand` — producing **string** keys, not integer IDs) and the resulting bucket ID must match Python's for every (board, hole, street) input. This is the single most fragile cross-tier seam. Tested via `test_abstraction_canonicalization_matches_python` + `test_abstraction_lookup_bucket_matches_python`.

3. **Exact integer chip arithmetic.** `HUNLState::contributions` / `stacks` / `to_call` are all `i32` cents. Float crossings happen only for the pot-fraction multiplication and round immediately back to integer. **Python uses banker's rounding** via `round()`; Rust's `f64::round()` ties to even by default, which **does not match Python**. Use `(x + 0.5).floor() as i32` (matches Python's `round()` semantics on positive integers) for parity. Audit-agent focus area.

4. **No float drift in regret accumulation between tiers** — at least at the bit-exact level for Kuhn/Leduc (PR 1/2 already verified). For HUNL we accept 1e-3 tolerance per §7.3.

5. **`force_allin_threshold` and dedup logic matches Python.** The clamp + replace-with-all-in + dedup path is identity-sensitive; tested via the diff test's `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction`.

6. **Showdown ties split utility exactly 50/50.** Python returns `(0.0, 0.0)`; Rust must too. `Strength` comparisons producing equality must trip the tie path in `HUNLState::utility`.

7. **All-in run-out walks exactly the right number of remaining streets via single-card chance nodes.** Matches PR 3 §"Decisions deferred" #2.

8. **HUNL preflop rejected.** Rust mirrors Python's `ValueError`. Tested in both tiers.

9. **Schema version check in `load_abstraction`.** Rust loader checks `metadata['schema_version'] == 1`; fails clearly otherwise.

10. **NEON intrinsics deferred to PR 8.** Rust is **readable + slow-but-correct first.** No `std::arch::aarch64` calls in PR 6. The flat tree shape (§4.2) is forward-compatible with NEON adoption (data already arranged in `Vec<f64>` per infoset).

11. **PyO3 GIL release.** `solve_hunl_postflop` wraps the DCFR loop in `py.allow_threads(…)`. Otherwise multi-call scenarios (CLI vs UI thread later) deadlock waiting on the GIL. Tested implicitly by `test_hunl_rust_deterministic_with_seed` (which threads two solve calls in different threads — must both succeed without deadlock).

12. **No code copied from AGPL.** Every Rust file in this PR has a module-level attribution docstring naming its MIT/Apache sources. Audit-agent confirms.

13. **HashMap iteration nondeterminism is bounded.** Strategies converge to the same Nash distribution regardless of iteration order. Tested via `test_hunl_rust_deterministic_with_seed` (same seed → same strategy — Rust uses `ahash` with a seed, locked).

14. **Existing tests must still pass.** Kuhn/Leduc diff tests (`tests/test_dcfr_diff.py`) unchanged. PR 3/4/5 Python tests unchanged.

15. **`HUNLConfig.bet_size_fractions` is a tuple of f64s but compared between Python and Rust by exact bit pattern.** Python sends `(0.33, 0.75, …)` over JSON; Rust deserializes via `serde_json` which preserves IEEE-754 doubles bit-exactly. **Tested** via a round-trip parity test.

## 10. Risks and mitigations

- **Large bucket file load time.** PR 4's `.npz` is ~100–750 MB compressed. `ndarray-npy` load cost is ~5 seconds for a 750 MB file. **Mitigation:** load once per solve invocation; cache in process memory across multiple solve calls. **Watch for:** double-loading if the Python config carries an `AbstractionTables` object AND the Rust binding reloads from path; we explicitly avoid this by passing only the path (not the object) over the PyO3 boundary.

- **PyO3 GIL contention on solve.** Long-running solver holds the GIL ⇒ Python is frozen. **Mitigation:** wrap the solver in `py.allow_threads(…)`. Tested in §8.3 Test 6. Risk-level: high if missed, low once implemented. Audit-agent focus area.

- **Mismatch between Python's `dataclass` infoset encoding and Rust's `String` encoding.** Python's `f"…"` formatting may differ in subtle ways (e.g., trailing zeros on floats, leading zeros on ints, sort stability of `frozenset` keys). **Mitigation:** the `test_hunl_infoset_key_lossless_format` + `…_bucketed_format` tests are the canary. Failure here is high-priority; the entire diff test fails downstream.

- **HashMap iteration order non-determinism × float order.** Two runs of the same Rust solver with different default-hasher seeds produce slightly different per-iteration regret accumulation. **Mitigation:** lock the hasher seed in test mode (`ahash::AHasher` with a fixed seed) so `test_hunl_rust_deterministic_with_seed` passes reliably. Documented as a test-mode requirement.

- **Tree build OOMs on M-series MacBook.** A full HUNL postflop tree at 100 BB with 6 bet sizes is 10–14 GB per PLAN.md. If Agent A's `HUNLTree::build` is allocation-heavy, peak memory could exceed 16 GB. **Mitigation:** use `Arc<HUNLConfig>` to avoid per-node config copies; pre-allocate `Vec<HUNLTreeNode>` with capacity hint from PR 3's tree-size estimate. If build OOMs, fall back to state-machine traversal (config flag, defaults to flat tree).

- **Rust evaluator slower than expected vs Python.** Python is ~200K hands/sec; Rust port should match or exceed easily. **Mitigation:** if it doesn't, defer the slumbot-style lookup table to PR 8 (already planned). Correctness is the gate, not perf.

- **Differential test tolerance choice is wrong.** 1e-3 may be too tight (false positives) or too loose (real bugs slip through). **Mitigation:** the first run of `test_hunl_river_subgame_diff_python_vs_rust` is the empirical calibration; if it passes at 1e-3, lock; if it fails reliably with strategies that *look* aligned, loosen incrementally with clear rationale (audit-agent reviews).

- **Banker's rounding semantics mismatch.** Python's `round()` rounds-half-to-even; Rust's `f64::round()` rounds-half-away-from-zero. **Mitigation:** explicitly use `(x + 0.5).floor()` for positive integers in `compute_bet_amount` / `compute_raise_to`. Audit-agent flagged.

- **JSON config round-trip drift.** Sending `f64` bet-size fractions through JSON could lose precision if serializer truncates. **Mitigation:** `serde_json` preserves f64 bit-exactly when using `to_string()` → `from_str()` chain. Tested via `test_hunl_rust_action_ids_match_python_constants` (extended to also compare bet-size-derived amounts).

- **noambrown attribution gap.** If a future maintainer ports another file without the attribution docstring, license compliance erodes. **Mitigation:** `check_pr.sh` step adds a grep-check requiring the attribution template in any new `.rs` file under `crates/cfr_core/src/hunl_*`. (Audit follow-up if not landed in this PR.)

- **PR 5's profiler doesn't extend to Rust.** Python-side `MemoryReport` doesn't have a Rust counterpart in PR 6. **Mitigation:** documented as out-of-scope (PR 8 owns Rust-side memory profiling). PR 6 reports infoset count + wall-clock only.

- **`Game` trait generic over `HUNLState` may compile slowly.** Generic instantiation for `DCFRSolver<HUNLState>` could add seconds to compile times. **Mitigation:** Rust's monomorphization is fine here; if it's noticeable, monomorphize once in `lib.rs` (`pub type HUNLDCFRSolver = DCFRSolver<HUNLState>`) to centralize instantiation.

- **Vector CFR (postflop-solver / noambrown style) absent.** Future per-hand vectorization (regret-stored-as-`[action × hand]` matrix) could give a further 10× speedup but adds substantial complexity (range modeling, vector evaluator). PR 6 explicitly stays scalar; PR 8 may reconsider. Decision flagged §11 #1.

## 11. Decisions deferred to user (defaults locked)

Each entry locks a default; if user prefers otherwise, redirect before launching A/B/C. Captured in the autonomous log.

1. **Scalar vs vector CFR.** Default: **scalar** (one regret per (infoset, action), matches Python tier and PR 1/2). Override candidate: vector CFR (per-hand regret matrix) — adds 1–2 weeks of work, requires range modeling first; defer to PR 8.

2. **Config marshalling: JSON string vs PyO3-bound struct.** Default: **JSON string** via `serde`. Override candidate: PyO3 struct (~200 LOC more, cleaner but more PyO3 boilerplate).

3. **Regret storage: f64 vs f32.** Default: **f64 to match Python.** `noambrown_poker_solver/cpp/src/trainer.h:21-27` allows compile-time toggle via `CFR_USE_DOUBLE`; default in noambrown is `float` (f32) per `#if defined(CFR_USE_DOUBLE)` guard. We use **f64** because: (a) Python tier uses `np.float64` → diff test parity simpler; (b) flop-tree convergence may benefit from extra precision; (c) PR 8 may revisit f32 for cache density. PR 6 default: **f64**.

4. **Bucket file format: keep `.npz` vs new Rust-native binary.** Default: **keep `.npz`** (PR 4 owns the artifact format; PR 6 is a consumer). Override candidate: dual-format (Python writes `.npz` for inspection; Rust reads a paired `.bin` for speed). Adds complexity; deferred.

5. **Exploitability + game_value: computed in Rust vs Python.** Default: **Python recomputes** from the Rust strategy. Matches Kuhn/Leduc pattern (`_solve_rust:295`). Override candidate: Rust computes (saves Python BR walk for fixtures where Python BR is slow, but Python BR is already plenty fast for PR 6's fixtures).

6. **Tree build: flat (eager) vs on-the-fly (lazy).** Default: **flat tree** at build time. Matches noambrown + postflop-solver pattern (read-only inspiration). Override candidate: on-the-fly only (saves build RAM, costs per-iteration time).

7. **Diff test tolerance: 1e-3 (default) vs 1e-2 (looser) vs 1e-4 (tighter).** Default: **1e-3** for river subgame, **5e-3** for flop subgame. Override candidate: 1e-2 (relaxed if 1e-3 reveals legitimate cross-tier drift from float ordering).

8. **HashMap hasher: default (random seed) vs ahash (fixed seed for tests).** Default: **`std::collections::HashMap` with default hasher in production, ahash with fixed seed under `#[cfg(test)]`** for deterministic per-test repro. Override candidate: ahash everywhere.

9. **Evaluator: port Python (slow) vs port slumbot lookup table (fast).** Default: **port Python.** Slumbot's 7-card lookup table (~500 MB) is a PR 8 perf task. Override candidate: ship slumbot port in PR 6 if user prioritizes solve perf over scope.

10. **CLI flag default backend: python vs rust.** Default: **python** (PR 5 default preserved). User opts in via `--backend rust`. Override candidate: flip default to rust once diff tests pass reliably.

11. **Build flat tree before or after abstraction load.** Default: **after** (so `infoset_key` for bucketed nodes uses live bucket IDs). Override candidate: build tree first with placeholder buckets (saves memory churn if config-iter changes between builds; not relevant in PR 6).

12. **Should the Rust tier support `target_exploitability` early-exit?** Default: **yes** (Python's PR 5 spec exposes it). Forwarded through the PyO3 surface. Override candidate: defer to PR 8 (simpler PR 6).

## 12. Out-of-scope follow-ups

- **PR 7:** River-spot diff test vs `noambrown/poker_solver` (MIT). Uses Rust solver as the workhorse; `noambrown` is the reference oracle on river-only spots (a known-correct MIT-licensed solver by the DCFR paper author).
- **PR 8:** NEON SIMD + cache-blocking + public chance sampling + slumbot evaluator port + memory-layout optimization. PR 6's flat tree is the substrate this builds on.
- **PR 9:** HUNL preflop port — same pattern as PR 6 but for the preflop subtree. Uses PR 6's evaluator + abstraction unchanged.
- **PR 11:** Macros wrap on top — solver cache + spot library + `.dmg` packaging.
- **PR 13 (candidate):** Deep CFR if tabular HUNL preflop OOMs.

## 13. Success criteria

- All new tests pass (~20 new tests across `test_hunl_diff.py` + `crates/cfr_core/tests/`).
- All PR 1/2/3/4/5 tests pass unchanged.
- `cargo test --all` passes in <2 minutes on the MacBook (river subgame diff is the slowest test).
- `cargo clippy --all-targets -- -D warnings` clean.
- `ruff check poker_solver tests` clean.
- `mypy poker_solver/hunl.py poker_solver/solver.py` strict-clean.
- License audit (`check_pr.sh` step 6): no new AGPL/GPL deps. `ndarray-npy` confirmed MIT/Apache.
- `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d Kh 5s" --backend rust --iterations 500` runs in <30 seconds and prints a strategy table + exploitability.
- `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" --stacks 100 --abstraction /tmp/abstraction_v1.npz --backend rust --iterations 1000` runs to completion (target: <2 minutes on a flop spot with the tiny synthetic abstraction; full 256/128/64 artifact may be longer and that's acceptable).
- Audit agent (`general-purpose` with no PR 6 context) reviews against this spec and produces `docs/pr6_prep/audit_report.md` with must-fix / should-fix / nice-to-fix / looks-good sections.

## 14. Reference citations

For DCFR algorithm formulae (not invented in this spec):
- Brown, N. & Sandholm, T. (2019). "Solving Imperfect-Information Games via Discounted Regret Minimization." AAAI 2019. References folder: `references/papers/`. The hyperparameter set α=1.5, β=0, γ=2.0 is the paper's recommended default.
- Regret update formulae documented at the top of `crates/cfr_core/src/dcfr.rs` (PR 1's port).

For postflop tree shape:
- `references/code/noambrown_poker_solver/cpp/src/river_game.{h,cpp}` (MIT) — the `Tree`/`TreeNode`/`Action` shape we re-derive in §4.2.
- `references/code/noambrown_poker_solver/cpp/src/trainer.{h,cpp}` (MIT) — the DCFR control flow we re-derive in §4.5 (already structurally matches PR 1's port).
- `references/code/postflop-solver/src/` (AGPL) — **read-only inspiration; no code copied.** Architectural ideas (flat tree, postflop subgame) confirmed against our independent re-derivation from the Python tier.

For hand evaluation:
- `references/code/slumbot2019/src/hand_value_tree.cpp` (MIT) — pattern for 7-card lookup table; PR 6 ports the Python equivalent (PR 8 may switch to this).
- `references/code/noambrown_poker_solver/cpp/src/cards.{h,cpp}` (MIT) — `Strength` type definition; PR 6 re-derives the equivalent.
- `poker_solver/evaluator.py` (project-internal, MIT) — source of truth for cross-tier evaluator parity.

For PyO3 + serde patterns:
- `crates/cfr_core/src/lib.rs` (PR 1) — pattern for `_rust.solve_*` PyO3 functions.
- `pyo3` documentation — `py.allow_threads`.

For card abstraction:
- PR 4 spec §3.5 + §4 Stage 5 — `AbstractionTables` shape and lookup semantics.
- PR 4 spec §"Stage 4" — canonicalization that Rust must replicate.

For Python tier source-of-truth:
- `poker_solver/hunl.py` (PR 3) — `HUNLState`, `HUNLConfig`, action enumeration.
- `poker_solver/hunl_solver.py` (PR 5) — top-level solve flow.
- `poker_solver/abstraction/` (PR 4) — bucket lookup.

## 15. Post-implementation audit

Per PLAN.md "Code + test audit (mandatory from PR 3 onward)": after A+B+C land, a fresh `general-purpose` audit agent runs with **no prior context** and reviews:

- The full diff (Agent A's Rust files, Agent B's Rust + Python integration, Agent C's tests, plus `Cargo.toml` + `pyproject.toml` deltas).
- Against this spec only.
- Output: `docs/pr6_prep/audit_report.md` with must-fix / should-fix / nice-to-fix / looks-good sections.
- User reads alongside `pr_report.md` before commit OK.

**Focus areas the audit must touch:**
- **License hygiene:** every new `.rs` file has the attribution docstring. Zero AGPL function bodies / type names / distinctive idioms. (Per §3.)
- **Integer-only chip arithmetic:** no `f64` chip accumulator. (Per §9 #3.)
- **Banker's rounding parity:** bet-amount calculation uses `(x + 0.5).floor()` not `f64::round()`. (Per §10.)
- **Infoset key byte-for-byte parity:** the diff test catches drifts. Audit confirms tests exist.
- **PyO3 GIL release:** `solve_hunl_postflop` wraps the loop in `allow_threads`. (Per §9 #11.)
- **NEON deferred:** zero `std::arch::aarch64` usage in PR 6. (Per §9 #10.)
- **Diff test scope realistic:** river-only + tiny-abstraction flop, not full HUNL flop. (Per §7.)
- **Cross-tier tolerance documented:** 1e-3 / 5e-3 with rationale. (Per §7.3.)
- **No fall-through bugs in `_solve_rust`:** preflop config raises clear error, postflop routes correctly.
- **`load_abstraction` schema version check:** loud failure on mismatch. (Per §4.4.)
- **Existing tests still pass:** Kuhn/Leduc diff untouched. (Per §9 #14.)
