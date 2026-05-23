# PR 6 Agent A — HUNL game state + flat tree + hand evaluator (Rust)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 6 Agent A.**
**Your scope:** the three Rust source files that hold the HUNL game-state representation, the flat (pre-built) HUNL game tree, and the 7-card hand evaluator that the Rust solver leans on. You port `poker_solver/hunl.py` + `poker_solver/action_abstraction.py` + `poker_solver/evaluator.py` to Rust under `crates/cfr_core/src/`, matching Python semantics byte-for-byte for infoset keys, bucket lookups (via Agent B's loader), and terminal utility.
**Your contract:** produce `hunl.rs` (`HUNLState`, `HUNLConfig`, `Street`, `impl Game for HUNLState`, action enumeration helpers, all `ACTION_*` constants), `hunl_tree.rs` (`HUNLTree`, `HUNLTreeNode`, `HUNLTree::build`), and `hunl_eval.rs` (`Strength`, `evaluate_5`, `evaluate_7`). Agent B imports your types via `crate::hunl::*`, `crate::hunl_tree::*`, `crate::hunl_eval::*` and wires them to the solver and PyO3 surface. Agent C tests both tiers against your public API.
**Your success criteria:** `cargo build --release` clean; `cargo clippy --all-targets -- -D warnings` clean; Rust unit tests in `crates/cfr_core/tests/hunl_state_unit.rs` pass; integer-cent chip arithmetic throughout (no `f64` chip accumulators); module-level license attribution on every new file; existing Kuhn/Leduc tests untouched.
**File ownership:** you own ONLY `crates/cfr_core/src/hunl.rs`, `crates/cfr_core/src/hunl_tree.rs`, `crates/cfr_core/src/hunl_eval.rs`. You may NOT modify any other file (including `lib.rs`, `Cargo.toml`, anything Python, anything in `tests/`).

---

## Strict file ownership

PR 6 depends on **PR 4** (the `.npz` bucket file format Agent B's loader consumes) and **PR 5** (the Python orchestration baseline you mirror semantically). Both have landed.

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_tree.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_eval.rs` (new file)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/tests/hunl_state_unit.rs` (Rust-only unit tests for blinds, fold path, raise-cap, all-in absorption, infoset key canonicalization — mirrors PR 3's `tests/test_hunl_core.py` Tests 1–18 in Rust)

**You must NOT touch:**
- `crates/cfr_core/src/abstraction.rs` — Agent B (you do NOT load `.npz`; Agent B's loader returns `AbstractionTables`, and you receive `Option<&AbstractionTables>` as a parameter into `infoset_key` paths).
- `crates/cfr_core/src/hunl_solver.rs` — Agent B (the DCFR-loop entry that uses your `HUNLState` + `HUNLTree`).
- `crates/cfr_core/src/lib.rs` — Agent B (PyO3 surface).
- `crates/cfr_core/Cargo.toml` — Agent B (adds `ndarray-npy`, `serde_json`, `arrayvec` if not already present). You may CONSULT it (read-only) to confirm which crates are available to you.
- `crates/cfr_core/src/dcfr.rs`, `game.rs`, `solver.rs`, `kuhn.rs`, `leduc.rs` — frozen for PR 6.
- Any Python file (`poker_solver/hunl.py`, `poker_solver/solver.py`, `poker_solver/hunl_solver.py`, `poker_solver/cli.py`, `poker_solver/abstraction/*`) — read-only references for semantic parity.
- Any other test file (`tests/test_hunl_diff.py`, `crates/cfr_core/tests/test_hunl_rust.rs`) — Agent C.

If you discover a contract gap mid-implementation, **do not silently change the spec interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md`. Internalize §3 (license-aware sourcing strategy), §4.1 (`hunl.rs`), §4.1.5 (internal helpers), §4.2 (`hunl_tree.rs`), §4.3 (`hunl_eval.rs`), §8.1 (your deliverables), §9 (critical correctness items — especially #1, #3, #5, #6, #7, #12), §10 (risks).
2. **Spec consistency review (cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Note: PR 4's `metadata` is a nested dict (B1 resolution; Agent B's concern), PR 4 declares `AbstractionRef` for `HUNLConfig.abstraction` (B2 resolution; both you and Agent B see this on the config), and PR 8 will add `use_pcs: bool` to `HUNLConfig` — **PR 6 pre-emptively includes `use_pcs: bool` in your Rust `HUNLConfig` per I6** so PR 8 has no schema migration.
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 architecture (Python is ground truth, Rust is the production port), §6 License audit (the AGPL vs MIT vs Apache table you must obey), and the "10-50× speedup" commitment that motivates the flat tree.
4. **Python source of truth (the files you port semantically):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLState`, `HUNLConfig`, `Street`, all chip math.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — `ACTION_*` integer constants, `enumerate_legal_actions`, `compute_bet_amount`, `compute_raise_to`.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/evaluator.py` — 5/7-card evaluator.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/card.py` — `card_to_int` mapping (`rank * 4 + suit`, range [8, 59]).
5. **The Rust precedent (style + license-attribution shape):**
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/leduc.rs` — the structural port that PR 6 mirrors. Match its module-level attribution docstring style.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/game.rs` — the `Game` trait you implement.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — the generic `DCFRSolver<G>` that consumes your `HUNLState` (PR 6 does NOT modify it).
6. **MIT/Apache reference code (you MAY port architecturally with attribution):**
   - `references/code/noambrown_poker_solver/cpp/src/river_game.{h,cpp}` (MIT) — pattern for `Tree`/`TreeNode`/`Action` shape; `legal_actions` enumeration; pot/contrib tracking. Attribution required.
   - `references/code/noambrown_poker_solver/cpp/src/cards.{h,cpp}` (MIT) — `Strength` evaluator type. Attribution required.
   - `references/code/slumbot2019/src/hand_value_tree.cpp` (MIT) — 7-card eval pattern (PR 8 may swap to a lookup table; PR 6 stays algorithmic).
   - `references/code/open_spiel/open_spiel/games/universal_poker/` (Apache 2.0) — terminal/showdown handling reference.
7. **AGPL repos you must NOT copy from:**
   - `references/code/postflop-solver/` — **AGPL v3.** Read-only inspiration; never copy code, function bodies, distinctive type names, idioms. Architectural ideas (flat tree, postflop subgame) are public knowledge — derive independently from Python + MIT sources.
   - `references/code/TexasSolver/` — **AGPL v3.** Same rule.
   - `references/code/shark-2.0/` — **Unlicensed.** Treat as all-rights-reserved; do not study for PR 6.

## Default decisions LOCKED (do not deviate)

PR 6 spec §11 lists 12 deferred decisions. Per the consistency review, all defaults are **LOCKED** unless the user redirects before launch. The ones that touch your scope:

- **D3 — Regret storage: f64 throughout.** Matches Python's `np.float64`. The f32 alternative is NOT locked; PR 8 may revisit for cache density. **Use `f64` for any float you produce.**
- **D6 — Flat tree at build time (default).** Eager pre-built tree, not on-the-fly traversal. `HUNLTree::build(config)` builds a `Vec<HUNLTreeNode>` indexed by `u32`. Fall-back to state-machine traversal is NOT in PR 6 scope.
- **D11 — Build flat tree AFTER abstraction load.** Abstraction must be available when the tree is built so chance/player nodes' `infoset_key` strings use live bucket IDs. (Agent B passes you the abstraction; you do not load it.)
- **D8 — HashMap hasher: default in production, `ahash` with fixed seed under `#[cfg(test)]`.** Not directly your concern (you don't own the regret HashMap — `DCFRSolver` does), but if you need an internal HashMap (e.g., tree-build memoization), use `std::collections::HashMap` in `src/` and switch to `ahash::AHashMap` (with a fixed seed) under `#[cfg(test)]` mod blocks.
- **D9 — Evaluator: port Python (slow), not slumbot lookup.** PR 6 ships an algorithmic 5/7-card evaluator that matches Python's. PR 8 may swap to a ~500 MB lookup table.
- **From PR 8 I6 — pre-include `use_pcs: bool` field in `HUNLConfig`.** Default `false`. PR 8 supplies the actual PCS code path. Pre-included here to avoid a forced schema migration.

**Other locked defaults (Agent B's scope, listed for awareness only):**
- D1 scalar CFR (not vector); D2 JSON config marshalling (not PyO3 struct binding); D4 keep `.npz` artifact; D5 Python recomputes exploitability + game_value from the Rust strategy; D7 1e-3 / 5e-3 diff-test tolerance; D10 Python default backend; D12 `target_exploitability` early-exit forwarded through PyO3.

## Public API contract (signatures Agent B + Agent C depend on)

**Signature drift breaks Agent B's `hunl_solver.rs` + PyO3 surface and Agent C's diff tests.** Lock these shapes; document any internal helper choices in code comments but do not deviate from the public surface.

### From `crates/cfr_core/src/hunl.rs`

```rust
//! HUNL postflop game state (Rust production tier).
//!
//! Adapted from `poker_solver/hunl.py` (project-internal, MIT) for semantics;
//! action-enumeration shape mirrors
//! `references/code/noambrown_poker_solver/cpp/src/river_game.cpp` (MIT) by
//! pattern, not by code transcription.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).

use crate::game::Game;
use std::sync::Arc;
use arrayvec::ArrayVec;

// ---- Street enum (matches Python's IntEnum from poker_solver/hunl.py) ----

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub enum Street {
    Preflop = 0,
    Flop = 1,
    Turn = 2,
    River = 3,
    Showdown = 4,
}

// ---- Action ID constants (verbatim with Python's `action_abstraction.py`) ----

pub const ACTION_FOLD: u8 = 0;
pub const ACTION_CHECK: u8 = 1;
pub const ACTION_CALL: u8 = 2;
pub const ACTION_BET_33: u8 = 3;
pub const ACTION_BET_50: u8 = 4;
pub const ACTION_BET_75: u8 = 5;
pub const ACTION_BET_100: u8 = 6;
pub const ACTION_BET_150: u8 = 7;
pub const ACTION_BET_200: u8 = 8;
pub const ACTION_RAISE_33: u8 = 9;
pub const ACTION_RAISE_50: u8 = 10;
pub const ACTION_RAISE_75: u8 = 11;
pub const ACTION_RAISE_100: u8 = 12;
pub const ACTION_ALL_IN: u8 = 13;
// IF Python defines any additional IDs in `action_abstraction.py` confirm via
// Read on that file and align here — single source of truth is the Python file.

// ---- Card encoding helper (matches `poker_solver/card.py::card_to_int`) ----

#[inline]
pub const fn card_to_int(rank: u8, suit: u8) -> u8 {
    // rank in 2..=14 (Two..=Ace), suit in 0..=3 → range [8, 59].
    rank * 4 + suit
}

// ---- HUNLConfig (mirror of Python's frozen dataclass) ----

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
    pub rake_rate: f64,
    pub rake_cap: i32,
    /// Reference to the abstraction artifact on disk; `None` for lossless mode.
    /// The actual `AbstractionTables` is loaded by Agent B's `abstraction.rs`
    /// from `abstraction_path` and passed alongside the config in solver paths.
    pub abstraction_path: Option<String>,
    pub abstraction_version: Option<String>,
    /// PCS opt-in flag for PR 8. Default `false`. PR 6 ignores this field;
    /// PR 8 introduces the actual code path. Pre-included per consistency
    /// review I6 to avoid forced schema migration.
    pub use_pcs: bool,
}

// ---- HUNLState (the `Game`-conformant game state) ----

#[derive(Clone, Debug)]
pub struct HUNLState {
    pub hole_cards: [[u8; 2]; 2],       // card_to_int encoding
    pub board: ArrayVec<u8, 5>,         // 0..=5 cards
    pub street: Street,
    pub contributions: [i32; 2],        // INTEGER CENTS — never f64
    pub stacks: [i32; 2],               // INTEGER CENTS
    pub street_history: Vec<u8>,        // ActionId stream this street
    pub street_aggressor: i8,           // -1 if none
    pub street_num_raises: u8,
    pub to_call: i32,                   // INTEGER CENTS
    pub cur_player: i8,                 // -1 chance, 0/1 player
    pub folded: [bool; 2],
    pub all_in: [bool; 2],
    pub config: Arc<HUNLConfig>,
}

impl HUNLState {
    /// Construct the initial state from a config; posts blinds + antes.
    /// Field-for-field mirror of Python's `HUNLState.initial(config)`.
    pub fn initial(config: Arc<HUNLConfig>) -> Self { /* ... */ }

    /// Build a deterministic infoset key for `player` (0 or 1).
    /// - Lossless (no abstraction): `f"{player_hole}|{board}|{street_token}|{betting_history}"`
    /// - Bucketed (with abstraction): `f"b{bucket_id}|{street_token}|{betting_history}"`
    /// MUST match Python's `f""` formatting byte-for-byte (test
    /// `test_hunl_infoset_key_lossless_format` / `_bucketed_format` will catch drift).
    /// The `abstraction` parameter is Agent B's loaded table; `None` for lossless.
    /// Lookup function signature is locked by Agent B; see §"Cross-agent contracts."
    pub fn infoset_key(
        &self,
        player: u8,
        abstraction: Option<&crate::abstraction::AbstractionTables>,
    ) -> String { /* ... */ }
}

impl Game for HUNLState {
    type Action = u8;
    // ... full trait impl: is_terminal, utility, current_player,
    // chance_outcomes, legal_actions, apply, infoset_key (delegates to
    // self.infoset_key(player, abstraction) — the abstraction is threaded by
    // the solver, not the state).
}

// ---- Internal action-enumeration helpers (per §4.1.5) ----

#[repr(C)]
#[derive(Clone, Debug)]
pub struct ActionContext {
    pub pot: i32,
    pub to_call: i32,
    pub stacks: [i32; 2],
    pub contributions: [i32; 2],
    pub cur_player: u8,
    pub street: Street,
    pub street_num_raises: u8,
    pub street_aggressor: i8,
    pub big_blind: i32,
    pub bet_size_fractions: Vec<f64>,
    pub preflop_raise_cap: u8,
    pub postflop_raise_cap: u8,
    pub force_allin_threshold: i32,
    pub min_bet_bb: i32,
    pub include_all_in: bool,
}

pub(crate) fn enumerate_legal_actions(ctx: &ActionContext) -> Vec<u8>;
pub(crate) fn compute_bet_amount(action_id: u8, ctx: &ActionContext) -> i32;
pub(crate) fn compute_raise_to(action_id: u8, ctx: &ActionContext) -> i32;
```

### From `crates/cfr_core/src/hunl_tree.rs`

```rust
//! HUNL flat-array game tree.
//!
//! Tree shape adapted by pattern from
//! `references/code/noambrown_poker_solver/cpp/src/river_game.{h,cpp}` (MIT).
//! Independent re-derivation; NEVER copy from postflop-solver (AGPL).

use crate::hunl::{HUNLConfig, HUNLState, Street};
use arrayvec::ArrayVec;
use std::sync::Arc;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TerminalKind {
    NonTerminal,
    Fold { winner: u8, contribution_loss: i32 },
    Showdown { board_complete: bool },
}

#[derive(Clone, Debug)]
pub struct HUNLTreeNode {
    pub player: i8,                       // -1 chance, 0/1 player, -2 terminal
    pub terminal_kind: TerminalKind,
    pub contrib: [i32; 2],
    pub street: Street,
    pub num_actions: u8,
    pub legal_actions: ArrayVec<u8, 14>,
    pub children: [u32; 14],              // flat-table indices into nodes
    pub infoset_key: Option<String>,      // None for chance/terminal
    pub chance_action: Option<u8>,        // card dealt to enter this node
    pub chance_prob: f64,
    pub chance_outcomes: ArrayVec<(u8, f64), 52>,
}

pub struct HUNLTree {
    pub nodes: Vec<HUNLTreeNode>,
    pub root: u32,
    pub max_depth: u32,
    pub max_actions: u8,
    pub config: Arc<HUNLConfig>,
}

impl HUNLTree {
    /// Build the flat tree from the initial `HUNLState::initial(config)`.
    /// Recursive build via `apply` / `chance_outcomes`; memoize by
    /// (cur_player, contribs, street, history) to dedupe states reached
    /// via different chance orderings.
    ///
    /// The optional `abstraction` is used to populate per-node `infoset_key`
    /// in bucketed mode; `None` produces lossless keys. Agent B passes the
    /// abstraction in via this builder.
    pub fn build(
        config: Arc<HUNLConfig>,
        abstraction: Option<&crate::abstraction::AbstractionTables>,
    ) -> Self { /* ... */ }
}
```

### From `crates/cfr_core/src/hunl_eval.rs`

```rust
//! HUNL hand evaluator (5- and 7-card).
//!
//! `Strength` type and ranking pattern adapted from
//! `references/code/noambrown_poker_solver/cpp/src/cards.{h,cpp}` (MIT);
//! 7-card algorithmic-eval pattern referenced from
//! `references/code/slumbot2019/src/hand_value_tree.cpp` (MIT). Cross-validated
//! against `poker_solver/evaluator.py` (project-internal, MIT) — Python is the
//! correctness oracle. NEVER copy from AGPL repos.

/// Higher = stronger. Compares with `<` / `>`.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub struct Strength(pub u32);

impl Strength {
    /// Best-five-of-five hand rank. Matches `poker_solver/evaluator.py`.
    pub fn evaluate_5(cards: &[u8; 5]) -> Strength { /* ... */ }

    /// Best-five-of-seven hand rank. Iterates 21 combinations of 5 from 7
    /// (or uses the same algorithm as Python's evaluator). Matches Python.
    pub fn evaluate_7(cards: &[u8; 7]) -> Strength { /* ... */ }
}
```

## Critical correctness items

### 1. Integer-cent chip arithmetic (audit-agent focus)

**All chip values are `i32` cents.** No `f64` chip accumulator anywhere in `hunl.rs`. The only float crossings are:
- Pot-fraction multiplications in `compute_bet_amount` / `compute_raise_to`: `pot * fraction` (f64) → round to nearest int → back to `i32`. **Do this once per call site; never store the f64.**
- `bet_size_fractions: Vec<f64>` lives on the config (the fractions themselves are f64; the resulting chip values are i32).

**Banker's-rounding parity.** Python's `round()` rounds-half-to-even. Rust's `f64::round()` rounds-half-away-from-zero. **They differ for positive `x.5` inputs.** Use `(x + 0.5).floor() as i32` for positive integers (matches Python's `round()` on positive integers, which is what we need here since pot * fraction is always positive). Document in a code comment: `// banker's-rounding parity with Python's round() on positive integers`. Critical correctness item §9 #3 in the spec.

### 2. Byte-for-byte identical infoset keys

Both lossless and bucketed formats. Rust's `format!` output MUST match Python's `f""` output character-for-character:
- Card-int ordering inside the hole-card key must use the same sort that Python uses (typically ascending `card_to_int`).
- Board ordering inside the key must match Python (typically ascending `card_to_int`).
- `street_token` must match Python's string ("flop", "turn", "river", "showdown" or whatever Python uses — confirm from `poker_solver/hunl.py`).
- `betting_history` formatting must match Python (action IDs separated by Python's chosen separator).
- Bucket ID formatting: no leading zeros, no whitespace; match Python exactly.

Agent C's `test_hunl_infoset_key_lossless_format` + `_bucketed_format` tests 100 random states each across the PyO3 boundary; if your formatting drifts you'll see the failure there.

### 3. Showdown ties split utility exactly 50/50

Python returns `(0.0, 0.0)` at a tied showdown. Rust must too. When `Strength::evaluate_7(p0_seven) == Strength::evaluate_7(p1_seven)`, `HUNLState::utility()` returns `[0.0, 0.0]`. Tested via `test_hunl_strength_eval_handles_ties` (Agent C).

### 4. All-in run-out walks exactly the right number of remaining streets

When both players are all-in and the board isn't yet complete, `chance_outcomes()` produces single-card outcomes (NOT multi-card combinations); the runout deals one card at a time, sequentially. Matches PR 3 §"Decisions deferred" #2. Each card is uniform over the remaining deck minus blockers.

### 5. `force_allin_threshold` clamp + dedup matches Python

In `enumerate_legal_actions`:
- Compute each bet/raise size from `bet_size_fractions`.
- If the computed size is within `force_allin_threshold` of the stack (i.e., would leave fewer chips than the threshold), snap to `ACTION_ALL_IN` and dedup against other actions that resolve to the same chip amount.
- Dedup: identical chip outcomes collapsed (keep the lower action ID by convention; verify against Python's `action_abstraction.py`).
- `ACTION_ALL_IN` replaces oversized bets.

Tested via Agent C's `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` end-to-end.

### 6. Raise cap enforcement

Preflop 4, postflop 3 (PR 3 §"Raise cap enforcement"). At-cap → only fold/call/all-in are legal. Tested in your own Rust unit tests.

### 7. Card encoding (`rank * 4 + suit`, range [8, 59])

Match Python's `card_to_int`. The `const fn card_to_int(rank, suit) -> u8` helper is for compile-time card constants in your own tests. **Do not invent a new card encoding.**

### 8. License attribution headers MANDATORY

Every new `.rs` file in `crates/cfr_core/src/hunl_*` MUST start with the module-level attribution docstring per spec §3 template (shown above on each file). Cite MIT/Apache sources; explicitly call out the AGPL repos as "NEVER copy from." The `check_pr.sh` audit step will grep for this.

### 9. NO `std::arch::aarch64` (NEON deferred to PR 8)

PR 6 is **readable + slow-but-correct first.** Zero NEON intrinsics. The flat tree shape is forward-compatible with NEON adoption (regret data already arranged in `Vec<f64>` per infoset by `DCFRSolver`); PR 8 will do the vectorization. If you find yourself reaching for `std::arch`, stop — that's PR 8 scope.

### 10. NO code copied from AGPL

Cross-check before committing: no function bodies, no distinctive type names, no idioms from `postflop-solver` or `TexasSolver`. The architectural ideas (flat tree, postflop subgame, action enumeration) are public knowledge — derive independently from `poker_solver/hunl.py` (the Python tier you're porting) + the MIT references.

### 11. Tree-build memoization is forgiving to chance permutation

`HUNLTree::build` walks via `HUNLState::apply` + `chance_outcomes`. Different chance orderings (e.g., turn=Kh,river=5s vs turn=5s,river=Kh during all-in runout) reach equivalent infosets. Memoize by `(cur_player, contribs, street, history)` so equivalent states map to the same tree node. (Note: at the level of `HUNLState`, the full hole+board is part of identity; but the *infoset* — what's information-equivalent for the acting player — is keyed by `(cur_player, contribs, street, history)`. Tree-node dedup uses the infoset-equivalence key, not the full state.)

### 12. `chance_prob` and `chance_outcomes`

For chance nodes (cur_player == -1), `chance_outcomes()` returns `Vec<(u8, f64)>` where the `f64` sums to 1.0 ± 1e-12. Uniform over remaining deck minus blockers. Per-card; sequential single-card runouts.

### 13. Evaluator parity is the gate

Your `Strength::evaluate_7` must produce results that **order identically** to Python's `evaluator.evaluate(seven_cards)`. The actual integer encoding can differ (you might use a different rank scheme), but `(hand_a > hand_b)` in Rust must equal `(python_rank_a > python_rank_b)`. Agent C's `test_hunl_strength_eval_matches_python` runs 1000 random 7-card hands across the PyO3 boundary and asserts the comparison parity. Ties must be ties in both tiers (item #3).

## Cross-agent contracts

Treat these as opaque. Import only the names; do not depend on internals:

```rust
// From crate::abstraction (Agent B's module — DO NOT TOUCH):
//
// Shape per pr6_spec.md §4.4 (post launch-readiness-v2 amendment, 2026-05-22):
// PR 4's on-disk `.npz` stores per-street uint8 `*_assignments`, plus
// JSON-encoded `*_board_index` (dict[str, int]) and `*_hand_index`
// (dict[str, dict[str, int]]) inside one-element bytes arrays, plus a
// single JSON-encoded `metadata` dict (also one-element bytes). The Rust
// loader parses each JSON blob on load via `serde_json::from_slice`.
// `source_path` is set by `load_abstraction(path)` at runtime; NOT on disk.

use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Clone, Debug, serde::Deserialize)]
pub struct AbstractionMetadata {
    pub schema_version: u8,
    pub version: String,                    // matches HUNLConfig.abstraction.version
    pub bucket_counts: Vec<u16>,            // [K_flop, K_turn, K_river]
    pub feature_bins: u16,
    pub seed: u64,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

pub struct AbstractionTables {
    pub flop_assignments: Vec<u8>,
    pub turn_assignments: Vec<u8>,
    pub river_assignments: Vec<u8>,

    // String-keyed indices, parsed from JSON-bytes blobs in the .npz.
    pub flop_board_index: HashMap<String, u32>,
    pub turn_board_index: HashMap<String, u32>,
    pub river_board_index: HashMap<String, u32>,

    pub flop_hand_index: HashMap<String, HashMap<String, u32>>,
    pub turn_hand_index: HashMap<String, HashMap<String, u32>>,
    pub river_hand_index: HashMap<String, HashMap<String, u32>>,

    // Parsed once from the single JSON `metadata` blob.
    pub metadata: AbstractionMetadata,

    // Populated by `load_abstraction(path)` at runtime; NOT on disk.
    // Mirrors Python's `AbstractionTables.source_path` field. Drives the
    // version-check seam (see §6.3 + `resolve_abstraction_ref`).
    pub source_path: PathBuf,
}

pub fn load_abstraction(path: &Path) -> Result<AbstractionTables, AbstractionError>;

pub fn lookup_bucket(
    tables: &AbstractionTables,
    board: &[u8],
    hole: &[u8; 2],
    street: Street,
) -> i32;
// Returns -1 for preflop or out-of-range; non-negative bucket ID otherwise.
// Implementation: canonicalize (board, hole) -> (board_key: String, hand_key:
// String) via the port of `canonicalize_for_suit_iso`, then
// `board_offset = *_board_index[&board_key]`,
// `within     = *_hand_index[&board_key][&hand_key]`,
// returns `assignments[board_offset + within] as i32`.
```

You consume `lookup_bucket` inside `HUNLState::infoset_key` for the bucketed branch (when `abstraction` is `Some`). You do NOT touch `abstraction.rs`'s internals; Agent B owns it. Stable surface = these names + this signature.

If Agent B's `AbstractionTables` field set differs slightly when their module lands, **flag the drift to the orchestrator** — do not silently mutate your consumer to match. The spec lock is in §4.4 (post-2026-05-22 amendment).

## License-aware sourcing — concrete porting policy

The license audit in PLAN.md §6 is **load-bearing**: AGPL contamination is a one-way door we explicitly avoid. Policy for each new file:

| Source | License | Use in your files |
|---|---|---|
| `poker_solver/hunl.py` | project-internal MIT | **First reference.** Port semantics verbatim. |
| `poker_solver/action_abstraction.py` | project-internal MIT | **First reference.** Port `ACTION_*` IDs + `enumerate_legal_actions` semantics. |
| `poker_solver/evaluator.py` | project-internal MIT | **First reference.** Cross-validate `Strength::evaluate_*` against this. |
| `noambrown_poker_solver/cpp/src/river_game.{h,cpp}` | **MIT** | Pattern reference. Attribution required in module docstring. |
| `noambrown_poker_solver/cpp/src/cards.{h,cpp}` | **MIT** | Pattern reference for `Strength`. Attribution required. |
| `slumbot2019/src/hand_value_tree.cpp` | **MIT** | Pattern reference for 7-card eval. Attribution required. |
| `open_spiel/games/leduc_poker.cc` | **Apache 2.0** | Reference for terminal/showdown handling. Attribution if borrowed. |
| `postflop-solver/src/*` | **AGPL v3** | **Never copy.** Architectural ideas only. Cite in spec docs, never in Rust comments. |
| `TexasSolver/*` | **AGPL v3** | **Never copy.** Same rule. |
| `shark-2.0/*` | **Unlicensed** | **Never study.** Do not view files. |

**Module-level attribution template** (verbatim — paste at the top of each new file):

```rust
//! <short description, one line>
//!
//! Adapted from `poker_solver/<file>.py` (project-internal, MIT) for semantics;
//! <other reference pattern> mirrors `<MIT source path>` (MIT) by pattern,
//! not by code transcription.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
```

**If you copy a non-trivial snippet** (more than ~5 LOC) from an MIT-licensed C++ source, add an inline attribution comment at the function:
```rust
// Pattern from noambrown_poker_solver/cpp/src/river_game.cpp::Tree::add_node (MIT).
// Reference: references/code/noambrown_poker_solver/cpp/src/river_game.cpp:142-178.
```

## Quality bar

- **`cargo build --release`** clean.
- **`cargo clippy --all-targets -- -D warnings`** clean. Zero warnings.
- **`cargo test --package cfr_core hunl_state_unit`** passes (your own Rust unit tests).
- **`cargo test --all`** passes (existing Kuhn/Leduc tests must NOT regress). PR 6 does not modify `dcfr.rs`, `game.rs`, `kuhn.rs`, `leduc.rs`, `solver.rs`, `lib.rs`; if these break it's a circular-import or trait-incoherence symptom — flag to orchestrator.
- **License attribution headers present** on `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`. `check_pr.sh` will grep.
- **No new third-party deps** unless Agent B has already added them to `Cargo.toml`. You may use: `pyo3` (already present), `arrayvec` (Agent B adds if not present — confirm before relying), `std::sync::Arc`, `std::collections::HashMap`. NOT permitted in your scope: `ndarray-npy`, `serde`, `serde_json` (those are Agent B's). NOT permitted: `rayon`, `crossbeam`, NEON intrinsics.
- **Integer-cent chip arithmetic** verified by grep: no `f64` field on `HUNLState` (only `chance_prob`/`bet_size_fractions` on chance/config sides may be f64).
- **Code size budget: ~1500–2200 LOC** across the three files combined. The flat-tree builder + evaluator dominate. Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. **Never extrapolate from training data when a local authoritative source exists.** The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "HUNL", "evaluator", "tree", "DCFR" entries.

If you "remember" a hand-evaluator algorithm from training data, ground it in either the Python `evaluator.py` (first), the MIT-licensed C++ references (second), or the noambrown/slumbot patterns. **Do not import "well-known" algorithms blind** — even if functionally correct, a snippet that pattern-matches an AGPL source could create copyright doubt. When in doubt, port from `poker_solver/evaluator.py` directly.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Build the Rust crate
cargo build --release --package cfr_core 2>&1 | tail -20

# 2. Clippy zero-warnings on your files
cargo clippy --package cfr_core --all-targets -- -D warnings 2>&1 | tail -20

# 3. Your own Rust unit tests
cargo test --package cfr_core hunl_state_unit -- --nocapture 2>&1 | tail -30

# 4. Existing Kuhn/Leduc tests must still pass
cargo test --package cfr_core kuhn leduc 2>&1 | tail -20

# 5. Verify license-attribution headers
grep -l "AGPL" crates/cfr_core/src/hunl.rs crates/cfr_core/src/hunl_tree.rs crates/cfr_core/src/hunl_eval.rs
# All three should print (the docstring mentions AGPL as "NEVER copy from")

# 6. Verify no NEON intrinsics
! grep -r "std::arch::aarch64" crates/cfr_core/src/hunl*.rs && echo "NEON-free OK"

# 7. Verify no f64 chip accumulator (allow chance_prob + bet_size_fractions)
grep -E "f64" crates/cfr_core/src/hunl.rs | grep -vE "chance_prob|bet_size_fractions|rake_rate|utility|chance_outcomes" | head -10
# Inspect output: each match should be a comment, a utility return, or a bet-fraction crossing
# (no contribs / stacks / to_call fields typed f64)
```

If any step fails, fix the issue before reporting done. If a verification reveals a spec ambiguity, **stop and flag it** to the orchestrator — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails of `cargo build`, `cargo clippy`, `cargo test`).
4. License attributions added (paste the module docstring headers).
5. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
6. Confirmation that `Strength::evaluate_7` ordering parity vs Python evaluator was unit-tested (it's Agent C's diff that's the gate, but your own Rust-side smoke test should run a handful of known hand orderings).
