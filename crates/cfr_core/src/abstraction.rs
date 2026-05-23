//! HUNL card-bucket abstraction loader (Rust production tier).
//!
//! Adapted from `poker_solver/abstraction/buckets.py` (project-internal, MIT)
//! for semantics; `.npz` reading delegates to `ndarray-npy` (MIT/Apache 2.0).
//! Lookup-table layout patterned after
//! `references/code/slumbot2019/src/card_abstraction*.cpp` (MIT) by structural
//! pattern, not by code transcription.
//!
//! PR 6 §4.4 (post-launch-readiness-v2 amendment): the on-disk shape is
//! string-keyed dict-of-dict indices + a single JSON `metadata` blob. Each
//! `*_board_index` / `*_hand_index` / `metadata` entry in the `.npz` is a
//! one-element bytes array holding `json.dumps(d, sort_keys=True,
//! separators=(',', ':')).encode()` — this loader parses each via
//! `serde_json::from_slice` for byte-determinism parity with Python.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
//!
//! Public surface (consumed by `hunl.rs` Agent A + `hunl_solver.rs`):
//!   - `AbstractionTables` (struct fields per spec §4.4)
//!   - `AbstractionMetadata` (parsed from the JSON metadata blob)
//!   - `AbstractionError` (load/lookup error variants)
//!   - `load_abstraction(path) -> Result<AbstractionTables, _>`
//!   - `lookup_bucket(tables, board, hole, street) -> i32`

use std::collections::HashMap;
use std::fs::File;
use std::path::{Path, PathBuf};

use ndarray::{Array1, Ix1, OwnedRepr};
use ndarray_npy::NpzReader;
use serde::Deserialize;

use crate::hunl::Street;

/// On-disk schema version. Bump in lockstep with Python's
/// `poker_solver.abstraction.buckets.SCHEMA_VERSION` on incompatible layout
/// changes.
pub const SCHEMA_VERSION: u8 = 1;

/// Suit-permutation table — matches Python's
/// `itertools.permutations((0, 1, 2, 3))` byte-for-byte (24 entries, ordered).
/// Used by `canonical_hand_key` so the Rust and Python tiers produce
/// identical hand-key strings under a given board's chosen permutation.
const SUIT_PERMUTATIONS: [[u8; 4]; 24] = [
    [0, 1, 2, 3],
    [0, 1, 3, 2],
    [0, 2, 1, 3],
    [0, 2, 3, 1],
    [0, 3, 1, 2],
    [0, 3, 2, 1],
    [1, 0, 2, 3],
    [1, 0, 3, 2],
    [1, 2, 0, 3],
    [1, 2, 3, 0],
    [1, 3, 0, 2],
    [1, 3, 2, 0],
    [2, 0, 1, 3],
    [2, 0, 3, 1],
    [2, 1, 0, 3],
    [2, 1, 3, 0],
    [2, 3, 0, 1],
    [2, 3, 1, 0],
    [3, 0, 1, 2],
    [3, 0, 2, 1],
    [3, 1, 0, 2],
    [3, 1, 2, 0],
    [3, 2, 0, 1],
    [3, 2, 1, 0],
];

/// Mirror of Python's `RANKS = "23456789TJQKA"`. Rank 2 → '2', …, rank 14 → 'A'.
const RANKS: &[u8; 13] = b"23456789TJQKA";

/// Mirror of Python's `SUITS = "shdc"`. Suit 0 → 's', 1 → 'h', 2 → 'd', 3 → 'c'.
const SUITS: &[u8; 4] = b"shdc";

/// Encoded card-int mapping per `poker_solver.card.card_to_int`:
///   `card_int = rank * 4 + suit`, range `[8, 59]`.
/// PR 6's `Card` representation is `u8` matching that integer encoding (see
/// `hunl.rs`). This loader receives the same raw `u8` ids.
#[inline]
fn rank_of(card: u8) -> u8 {
    card / 4
}

#[inline]
fn suit_of(card: u8) -> u8 {
    card % 4
}

/// Parsed metadata blob. PR 4 writes this as a JSON-encoded `dict` inside a
/// one-element bytes array in the `.npz` (key: `metadata`). Tolerates unknown
/// writer-side keys via `#[serde(flatten)] extra`.
#[derive(Clone, Debug, Deserialize)]
pub struct AbstractionMetadata {
    pub schema_version: u8,
    /// String version tag — must match `HUNLConfig.abstraction.version` when
    /// the resolver wires the artifact to a solve config (defense in depth on
    /// top of Python's `resolve_abstraction_ref` version check).
    pub version: String,
    /// `[K_flop, K_turn, K_river]` bucket counts per street.
    pub bucket_counts: Vec<u16>,
    pub feature_bins: u16,
    pub seed: u64,
    /// Tolerate any additional writer-side keys without failing parse.
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// In-memory representation of the bucket lookup tables. Mirrors Python's
/// `AbstractionTables` dataclass in `poker_solver/abstraction/buckets.py`.
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

    /// Populated by `load_abstraction(path)`; NOT persisted to disk.
    /// Matches Python's `AbstractionTables.source_path` field.
    pub source_path: PathBuf,
}

/// Load-side / lookup-side error variants. All loud failures — never silent
/// stale-artifact reuse.
#[derive(Debug)]
pub enum AbstractionError {
    Io(std::io::Error),
    Npz(String),
    Json(String),
    SchemaMismatch { expected: u8, found: u8 },
    VersionMismatch { expected: String, found: String },
    Malformed(String),
}

impl std::fmt::Display for AbstractionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AbstractionError::Io(e) => write!(f, "I/O error reading abstraction: {e}"),
            AbstractionError::Npz(msg) => write!(f, "npz read error: {msg}"),
            AbstractionError::Json(msg) => write!(f, "metadata JSON parse error: {msg}"),
            AbstractionError::SchemaMismatch { expected, found } => write!(
                f,
                "abstraction schema v{found}; loader expects v{expected}; \
                 rebuild via `poker-solver precompute-abstraction`"
            ),
            AbstractionError::VersionMismatch { expected, found } => write!(
                f,
                "AbstractionRef version mismatch: ref.version={expected:?} \
                 but on-disk metadata['version']={found:?}"
            ),
            AbstractionError::Malformed(msg) => {
                write!(f, "malformed abstraction artifact: {msg}")
            }
        }
    }
}

impl std::error::Error for AbstractionError {}

impl From<std::io::Error> for AbstractionError {
    fn from(e: std::io::Error) -> Self {
        AbstractionError::Io(e)
    }
}

/// Load `AbstractionTables` from a `.npz` artifact written by Python's
/// `save_abstraction`. Reads three per-street uint8 assignment arrays, three
/// JSON-encoded board-index dicts, three JSON-encoded hand-index nested
/// dicts, and one JSON-encoded metadata dict. Verifies
/// `metadata.schema_version == SCHEMA_VERSION` and populates
/// `source_path = path`.
pub fn load_abstraction(path: &Path) -> Result<AbstractionTables, AbstractionError> {
    if !path.exists() {
        return Err(AbstractionError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("abstraction artifact not found: {}", path.display()),
        )));
    }
    let file = File::open(path)?;
    let mut npz = NpzReader::new(file).map_err(|e| AbstractionError::Npz(e.to_string()))?;

    let flop_assignments = read_u8_vec(&mut npz, "flop_assignments")?;
    let turn_assignments = read_u8_vec(&mut npz, "turn_assignments")?;
    let river_assignments = read_u8_vec(&mut npz, "river_assignments")?;

    let flop_board_index = decode_str_int_dict(&mut npz, "flop_board_index")?;
    let turn_board_index = decode_str_int_dict(&mut npz, "turn_board_index")?;
    let river_board_index = decode_str_int_dict(&mut npz, "river_board_index")?;

    let flop_hand_index = decode_nested_dict(&mut npz, "flop_hand_index")?;
    let turn_hand_index = decode_nested_dict(&mut npz, "turn_hand_index")?;
    let river_hand_index = decode_nested_dict(&mut npz, "river_hand_index")?;

    let metadata_bytes = read_u8_vec(&mut npz, "metadata")?;
    let metadata: AbstractionMetadata = serde_json::from_slice(&metadata_bytes)
        .map_err(|e| AbstractionError::Json(format!("metadata: {e}")))?;

    if metadata.schema_version != SCHEMA_VERSION {
        return Err(AbstractionError::SchemaMismatch {
            expected: SCHEMA_VERSION,
            found: metadata.schema_version,
        });
    }

    Ok(AbstractionTables {
        flop_assignments,
        turn_assignments,
        river_assignments,
        flop_board_index,
        turn_board_index,
        river_board_index,
        flop_hand_index,
        turn_hand_index,
        river_hand_index,
        metadata,
        source_path: path.to_path_buf(),
    })
}

/// Read a 1-D `u8` array out of the `.npz` and convert it to `Vec<u8>`.
fn read_u8_vec(npz: &mut NpzReader<File>, name: &str) -> Result<Vec<u8>, AbstractionError> {
    let arr: ndarray::ArrayBase<OwnedRepr<u8>, Ix1> = npz
        .by_name(name)
        .map_err(|e| AbstractionError::Npz(format!("{name}: {e}")))?;
    Ok(Array1::from(arr).into_raw_vec_and_offset().0)
}

/// Decode a one-element bytes array containing a JSON-encoded `dict[str, int]`.
fn decode_str_int_dict(
    npz: &mut NpzReader<File>,
    name: &str,
) -> Result<HashMap<String, u32>, AbstractionError> {
    let raw = read_u8_vec(npz, name)?;
    let value: serde_json::Value =
        serde_json::from_slice(&raw).map_err(|e| AbstractionError::Json(format!("{name}: {e}")))?;
    let obj = value
        .as_object()
        .ok_or_else(|| AbstractionError::Malformed(format!("{name} JSON is not an object")))?;
    let mut out: HashMap<String, u32> = HashMap::with_capacity(obj.len());
    for (k, v) in obj {
        let n = v.as_u64().ok_or_else(|| {
            AbstractionError::Malformed(format!("{name}[{k:?}] is not a non-negative integer"))
        })?;
        if n > u32::MAX as u64 {
            return Err(AbstractionError::Malformed(format!(
                "{name}[{k:?}] value {n} exceeds u32 range"
            )));
        }
        out.insert(k.clone(), n as u32);
    }
    Ok(out)
}

/// Decode a one-element bytes array containing a JSON-encoded
/// `dict[str, dict[str, int]]`.
fn decode_nested_dict(
    npz: &mut NpzReader<File>,
    name: &str,
) -> Result<HashMap<String, HashMap<String, u32>>, AbstractionError> {
    let raw = read_u8_vec(npz, name)?;
    let value: serde_json::Value =
        serde_json::from_slice(&raw).map_err(|e| AbstractionError::Json(format!("{name}: {e}")))?;
    let obj = value
        .as_object()
        .ok_or_else(|| AbstractionError::Malformed(format!("{name} JSON is not an object")))?;
    let mut out: HashMap<String, HashMap<String, u32>> = HashMap::with_capacity(obj.len());
    for (k, v) in obj {
        let inner = v.as_object().ok_or_else(|| {
            AbstractionError::Malformed(format!("{name}[{k:?}] is not an object"))
        })?;
        let mut inner_map: HashMap<String, u32> = HashMap::with_capacity(inner.len());
        for (ik, iv) in inner {
            let n = iv.as_u64().ok_or_else(|| {
                AbstractionError::Malformed(format!(
                    "{name}[{k:?}][{ik:?}] is not a non-negative integer"
                ))
            })?;
            if n > u32::MAX as u64 {
                return Err(AbstractionError::Malformed(format!(
                    "{name}[{k:?}][{ik:?}] value {n} exceeds u32 range"
                )));
            }
            inner_map.insert(ik.clone(), n as u32);
        }
        out.insert(k.clone(), inner_map);
    }
    Ok(out)
}

/// Compute the lexicographically-minimal board key across the 24 suit
/// permutations. Returns `(canonical_board_string, chosen_perm_index)`. Must
/// match Python's `canonicalize_for_suit_iso` byte-for-byte (same string
/// format, same tie-break — earliest-permutation wins among equal-keyed
/// outputs).
fn canonicalize_board(board: &[u8]) -> (String, usize) {
    // Each permutation produces a sorted-pair tuple `(rank, perm[suit])`;
    // we keep the lexicographically smallest one with the smallest perm
    // index as the tie-breaker (matches Python's `<` comparison on tuples
    // + the first-wins enumerate loop).
    let mut best_perm: usize = 0;
    let mut best_pairs: Option<Vec<(u8, u8)>> = None;
    for (i, perm) in SUIT_PERMUTATIONS.iter().enumerate() {
        let mut pairs: Vec<(u8, u8)> = board
            .iter()
            .map(|&c| (rank_of(c), perm[suit_of(c) as usize]))
            .collect();
        pairs.sort();
        match &best_pairs {
            None => {
                best_pairs = Some(pairs);
                best_perm = i;
            }
            Some(existing) => {
                if pairs < *existing {
                    best_pairs = Some(pairs);
                    best_perm = i;
                }
            }
        }
    }
    let best = best_pairs.expect("board must have at least one card");
    // Stable string format: each card is "r{rank}s{suit}" joined with "_".
    // Exactly matches Python's `"_".join(f"r{r}s{s}" for r, s in best_key)`.
    let parts: Vec<String> = best.iter().map(|(r, s)| format!("r{r}s{s}")).collect();
    (parts.join("_"), best_perm)
}

/// Apply the board's chosen suit permutation to the hole cards and produce
/// the within-board hand key. Mirrors Python's `_apply_suit_perm_to_hand`:
/// sort the permuted cards by (rank, suit), then concatenate their string
/// representation (`RANKS[rank-2] + SUITS[suit]`).
fn canonical_hand_key(hole: &[u8; 2], perm_index: usize) -> String {
    let perm = &SUIT_PERMUTATIONS[perm_index];
    let mut cards: [(u8, u8); 2] = [
        (rank_of(hole[0]), perm[suit_of(hole[0]) as usize]),
        (rank_of(hole[1]), perm[suit_of(hole[1]) as usize]),
    ];
    cards.sort();
    let mut out = String::with_capacity(4);
    for (r, s) in cards.iter() {
        // Python `RANKS = "23456789TJQKA"`, ranks indexed by `rank - 2`.
        let rank_char = RANKS[(*r as usize).saturating_sub(2)] as char;
        // Python `SUITS = "shdc"`.
        let suit_char = SUITS[*s as usize] as char;
        out.push(rank_char);
        out.push(suit_char);
    }
    out
}

/// Canonicalize `(board, hole)` to the `(board_key, hand_key)` string pair
/// used by `lookup_bucket`. Public for cross-tier parity tests (PR 6
/// Agent C `test_abstraction_canonicalization_matches_python`); not part of
/// the hot path consumed by `HUNLState::infoset_key`. Must be byte-for-byte
/// identical to Python's `_canonicalize` in
/// `poker_solver/abstraction/buckets.py`.
pub fn canonicalize(board: &[u8], hole: &[u8; 2]) -> (String, String) {
    let (board_key, perm_index) = canonicalize_board(board);
    let hand_key = canonical_hand_key(hole, perm_index);
    (board_key, hand_key)
}

/// O(1) bucket lookup. MUST be byte-for-byte identical to Python's
/// `lookup_bucket` in `poker_solver/abstraction/buckets.py`. Preflop returns
/// `-1`; the caller falls back to the lossless preflop infoset.
///
/// Implementation steps mirror Python exactly:
///   1. If `street == Preflop`, return `-1`.
///   2. Canonicalize `(board, hole) -> (board_key, hand_key)` via the same
///      suit-iso scheme Python uses (lexicographically-minimal board under
///      24 suit permutations, with earliest-perm-index tie-break).
///   3. Resolve `board_offset = *_board_index[&board_key]` and
///      `within = *_hand_index[&board_key][&hand_key]`.
///   4. Return `*_assignments[board_offset + within]` as `i32`.
///
/// # Panics
///
/// Panics if `board_key` / `hand_key` is missing from the table (signals a
/// build-side coverage bug — the artifact does not cover all reachable
/// boards). This matches Python's `ValueError` on the same condition; we
/// surface it as a panic here because the call site (`HUNLState::infoset_key`
/// in Agent A's module, plus tree-builder traversal) cannot recover.
pub fn lookup_bucket(
    tables: &AbstractionTables,
    board: &[u8],
    hole: &[u8; 2],
    street: Street,
) -> i32 {
    if street == Street::Preflop {
        return -1;
    }
    let (board_key, perm_index) = canonicalize_board(board);
    let hand_key = canonical_hand_key(hole, perm_index);

    type StreetTables<'a> = (
        &'a Vec<u8>,
        &'a HashMap<String, u32>,
        &'a HashMap<String, HashMap<String, u32>>,
    );
    let (assignments, board_index, hand_index): StreetTables<'_> = match street {
        Street::Flop => (
            &tables.flop_assignments,
            &tables.flop_board_index,
            &tables.flop_hand_index,
        ),
        Street::Turn => (
            &tables.turn_assignments,
            &tables.turn_board_index,
            &tables.turn_hand_index,
        ),
        Street::River => (
            &tables.river_assignments,
            &tables.river_board_index,
            &tables.river_hand_index,
        ),
        // Preflop handled above; Showdown is not a decision point.
        Street::Preflop | Street::Showdown => {
            panic!("lookup_bucket called on non-postflop street: {street:?}")
        }
    };

    let board_offset = board_index.get(&board_key).copied().unwrap_or_else(|| {
        panic!(
            "canonical board key {board_key:?} not in {street:?} table \
             (build-side coverage bug)"
        )
    });
    let per_board = hand_index.get(&board_key).unwrap_or_else(|| {
        panic!(
            "canonical board key {board_key:?} missing from {street:?} \
             hand_index (build-side coverage bug)"
        )
    });
    let within = per_board.get(&hand_key).copied().unwrap_or_else(|| {
        panic!(
            "canonical hand key {hand_key:?} not in {street:?} hand_index for \
             board {board_key:?} (build-side coverage bug)"
        )
    });
    let idx = (board_offset as usize) + (within as usize);
    assignments[idx] as i32
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Sanity: the suit-permutation table matches Python's
    /// `itertools.permutations((0,1,2,3))` order. Spot-check a few indices.
    #[test]
    fn suit_permutations_match_python_order() {
        assert_eq!(SUIT_PERMUTATIONS[0], [0, 1, 2, 3]);
        assert_eq!(SUIT_PERMUTATIONS[1], [0, 1, 3, 2]);
        assert_eq!(SUIT_PERMUTATIONS[6], [1, 0, 2, 3]);
        assert_eq!(SUIT_PERMUTATIONS[23], [3, 2, 1, 0]);
    }

    /// Card-int → (rank, suit) round-trips for the legal range [8, 59].
    #[test]
    fn card_int_split() {
        // Card(rank=2, suit=0) -> card_int = 8.
        assert_eq!(rank_of(8), 2);
        assert_eq!(suit_of(8), 0);
        // Card(rank=14, suit=3) -> card_int = 59.
        assert_eq!(rank_of(59), 14);
        assert_eq!(suit_of(59), 3);
    }

    /// Hand-key format matches Python's `_apply_suit_perm_to_hand` for an
    /// identity permutation: "KhAc" for hole=(Kh, Ac).
    #[test]
    fn hand_key_identity_perm() {
        // Card.from_str("Kh") = Card(rank=13, suit=1) -> card_int = 53.
        // Card.from_str("Ac") = Card(rank=14, suit=3) -> card_int = 59.
        let hole = [53_u8, 59_u8];
        let key = canonical_hand_key(&hole, 0);
        assert_eq!(key, "KhAc");
    }
}
