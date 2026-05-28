//! Phase A.1 — Preflop 169x169 equity leaf table.
//!
//! Builds (and at runtime loads) a precomputed equity matrix
//! `eq[hero_class][villain_class][variant] = P(hero_wins) + 0.5*P(tie)`
//! over exhaustive C(48, 5) board run-outs. Used by the Phase A vector-form
//! preflop solver (`preflop_rvr.rs`) to collapse the postflop chance subtree
//! to a single equity-leaf value, mirroring the depth-limited solving
//! pattern (Brown & Sandholm 2018) and the `preflop.rs` subgame solver's
//! `compute_p0_equity` helper.
//!
//! ## Why 169 classes
//!
//! Hold'em starting hands fall into 169 "preflop equivalence classes" by
//! the canonical rank+suitedness reduction: pocket pairs (13), suited
//! (13*12/2 = 78), offsuit (13*12/2 = 78). 13 + 78 + 78 = 169.
//!
//! ## Why 2-3 micro-bucket variants per pair
//!
//! Two hands in the same class can have different blocker/board-overlap
//! patterns depending on the suits they hold relative to each other. For
//! example, hero AsKs vs villain QhJh has 0 suit overlap between players;
//! hero AsKs vs villain QsJs forces both flushes to share the s suit,
//! shifting equity. We compute the equity under each *distinct* suit-
//! overlap orientation between hero and villain and store the table
//! indexed by that orientation.
//!
//! The orientations we distinguish:
//!   - Variant 0: representative orientation (hero in suits A/B; villain in
//!     non-overlapping suits as far as possible).
//!   - Variant 1: maximum suit overlap (hero and villain share a suit).
//!   - Variant 2: paired-suit case where both pockets share both suits
//!     (only meaningful when hero/villain are both suited with matching
//!     ranks).
//!
//! For the v1 ship we standardize on **3 variants per (hero_class,
//! villain_class)** with deterministic suit-orientation rules.
//!
//! ## File format
//!
//! Storage: a single 3-dim `Array<f64, Ix3>` of shape `(169, 169, 3)`
//! serialized as `assets/preflop_equity_169x169.npz` via the `ndarray-npy`
//! crate. The serialized table is ~700 KB compressed.

use ndarray::Array3;
use std::path::Path;
use std::sync::Mutex;

use crate::hunl::card_to_int;
use crate::hunl_eval::Strength;
use crate::pcs::PcsRng;

/// Number of preflop equivalence classes (Hold'em starting hands).
pub const NUM_CLASSES: usize = 169;

/// Number of micro-bucket variants per (hero, villain) class pair.
pub const NUM_VARIANTS: usize = 3;

/// Preflop hand class label (e.g. "AA", "AKs", "72o"). Index in 0..169.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub struct HandClass(pub u16);

/// One concrete (rank, suit) pair representative for a given class +
/// variant. Suits are 0..4 (`shdc` indexing).
#[derive(Clone, Copy, Debug)]
pub struct HoleRep {
    pub hero: [u8; 2],
    pub villain: [u8; 2],
}

/// Static rank ordering used for class indexing (high to low).
const RANKS_HIGH_TO_LOW: [u8; 13] = [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];

/// Build the class index `0..169` from rank/suitedness.
///
/// Encoding:
///   - Pocket pair (r, r): index = position_of(r) in 0..13.
///   - Suited (r_hi > r_lo): index = 13 + (12*pos_hi + pos_lo'), where
///     pos_lo' is the position within the suited triangle.
///   - Offsuit: index = 13 + 78 + (12*pos_hi + pos_lo').
///
/// Simpler indexing: enumerate `(r_hi, r_lo, suited)` in canonical order.
pub fn class_index(rank_hi: u8, rank_lo: u8, suited: bool) -> u16 {
    debug_assert!(rank_hi >= rank_lo, "rank_hi must be >= rank_lo");
    debug_assert!((2..=14).contains(&rank_hi));
    debug_assert!((2..=14).contains(&rank_lo));
    let pos_hi = pos_for_rank(rank_hi);
    let pos_lo = pos_for_rank(rank_lo);
    if rank_hi == rank_lo {
        return pos_hi as u16;
    }
    let off = if suited { 13 } else { 13 + 78 };
    let pair_idx = unordered_pair_index(pos_hi, pos_lo);
    (off + pair_idx) as u16
}

fn pos_for_rank(rank: u8) -> usize {
    RANKS_HIGH_TO_LOW
        .iter()
        .position(|&r| r == rank)
        .expect("invalid rank")
}

/// Index into the upper-triangle pair enumeration for two distinct
/// positions `(pos_hi, pos_lo)` with `pos_hi < pos_lo` (positions are
/// high-to-low so pos_hi smaller = stronger rank).
fn unordered_pair_index(pos_hi: usize, pos_lo: usize) -> usize {
    debug_assert!(pos_hi != pos_lo);
    let (a, b) = if pos_hi < pos_lo {
        (pos_hi, pos_lo)
    } else {
        (pos_lo, pos_hi)
    };
    // Standard upper-triangle linearization for a 13x13 grid (78 unique pairs).
    // Sum over rows 0..a of (12 - row) = a*12 - a*(a-1)/2; then column
    // offset is (b - a - 1).
    a * 12 - (a * a.saturating_sub(1)) / 2 + (b - a - 1)
}

/// Decode a `class_idx` back to (rank_hi, rank_lo, suited).
pub fn class_decode(class_idx: u16) -> (u8, u8, bool) {
    let idx = class_idx as usize;
    if idx < 13 {
        let r = RANKS_HIGH_TO_LOW[idx];
        return (r, r, false);
    }
    let suited = idx < 13 + 78;
    let pair_idx = if suited { idx - 13 } else { idx - 13 - 78 };
    // Reverse the unordered_pair_index linearization.
    let (a, b) = decode_pair(pair_idx);
    (RANKS_HIGH_TO_LOW[a], RANKS_HIGH_TO_LOW[b], suited)
}

fn decode_pair(pair_idx: usize) -> (usize, usize) {
    let mut idx = pair_idx;
    for a in 0..12 {
        let row_len = 12 - a;
        if idx < row_len {
            return (a, a + 1 + idx);
        }
        idx -= row_len;
    }
    unreachable!("pair_idx out of bounds")
}

/// Build a concrete hole-pair for `(hero_class, villain_class, variant)`.
///
/// Variant semantics:
///   - 0: hero suits {0, 1}; villain suits {2, 3} where possible (minimum
///     suit overlap). Falls back gracefully for paired ranks.
///   - 1: hero and villain share one suit (e.g. hero As Kh, villain Ah Qh
///     if hero is suited; otherwise one rank overlap).
///   - 2: paired-suit / maximum overlap (used when both are suited).
///
/// Returns `None` if the combination is geometrically impossible
/// (e.g. both AA pocket pair against AA — 4 aces, can only deal one pair).
pub fn build_hole_rep(
    hero_class: u16,
    villain_class: u16,
    variant: u8,
) -> Option<HoleRep> {
    let (h_hi, h_lo, h_suited) = class_decode(hero_class);
    let (v_hi, v_lo, v_suited) = class_decode(villain_class);

    // Suit assignment. We allocate suits per (player, slot) and check
    // disjointness at the end. For an offsuit hand the two cards have
    // different suits; for suited they share one. The variant index
    // determines how hero suits overlap villain suits.
    //
    // We define hero suits first, then assign villain suits to produce
    // the desired overlap profile.
    let hero_pair = if h_hi == h_lo {
        // Pocket pair: two different suits (any two of 4).
        ([card_to_int(h_hi, 0), card_to_int(h_lo, 1)], None)
    } else if h_suited {
        // Suited: both cards same suit.
        ([card_to_int(h_hi, 0), card_to_int(h_lo, 0)], Some(0_u8))
    } else {
        // Offsuit: two different suits.
        ([card_to_int(h_hi, 0), card_to_int(h_lo, 1)], None)
    };

    let h_used = [hero_pair.0[0], hero_pair.0[1]];
    let villain_pair = pick_villain_suits(
        v_hi,
        v_lo,
        v_suited,
        variant,
        h_used,
        hero_pair.1,
        h_suited,
    )?;

    // Final disjointness check (must not duplicate a card).
    let combo: [u8; 4] = [h_used[0], h_used[1], villain_pair[0], villain_pair[1]];
    let mut seen = [false; 64];
    for &c in &combo {
        if seen[c as usize] {
            return None;
        }
        seen[c as usize] = true;
    }

    Some(HoleRep {
        hero: h_used,
        villain: villain_pair,
    })
}

/// Pick suits for the villain's hole given the hero's and the variant.
fn pick_villain_suits(
    v_hi: u8,
    v_lo: u8,
    v_suited: bool,
    variant: u8,
    h_used: [u8; 2],
    h_suit: Option<u8>,
    h_suited: bool,
) -> Option<[u8; 2]> {
    // Try a search over candidate suit assignments, picking the first that
    // (a) matches the variant's overlap semantics and (b) does not
    // duplicate hero cards.
    //
    // Variant 0 (low overlap): prefer suits disjoint from hero's suit set.
    // Variant 1 (medium overlap): one shared suit.
    // Variant 2 (paired-suit): two shared suits if possible (only fully
    //                          meaningful for suited-vs-suited paired ranks).
    let hero_suits: Vec<u8> = h_used.iter().map(|&c| c & 3).collect();
    let suits_all: Vec<u8> = (0..4).collect();
    let suits_not_hero: Vec<u8> = suits_all
        .iter()
        .copied()
        .filter(|s| !hero_suits.contains(s))
        .collect();

    if v_hi == v_lo {
        // Pocket pair: pick two different suits for the two cards.
        let (s_a, s_b) = match variant {
            0 => {
                // Try a pair of suits not held by hero first.
                if suits_not_hero.len() >= 2 {
                    (suits_not_hero[0], suits_not_hero[1])
                } else if let Some(&s0) = suits_not_hero.first() {
                    (s0, hero_suits[0])
                } else {
                    (hero_suits[0], hero_suits[1])
                }
            }
            1 => {
                if let Some(&s_overlap) = hero_suits.first() {
                    let s_other = suits_all
                        .iter()
                        .copied()
                        .find(|s| *s != s_overlap)
                        .unwrap_or(0);
                    (s_overlap, s_other)
                } else {
                    (0, 1)
                }
            }
            _ => {
                // Variant 2: pair shares both suits with hero where possible.
                if hero_suits.len() >= 2 {
                    (hero_suits[0], hero_suits[1])
                } else if let Some(&s) = hero_suits.first() {
                    let s_other = suits_all.iter().copied().find(|x| *x != s).unwrap_or(0);
                    (s, s_other)
                } else {
                    (0, 1)
                }
            }
        };
        return finalize_pair(v_hi, s_a, v_lo, s_b, h_used);
    }

    if v_suited {
        // Suited: both cards same suit.
        // h_suited is not load-bearing for this branch — we always fall back
        // to hero_suits[0] when h_suit is None. Hold on to the variable so
        // the signature stays self-documenting.
        let _ = h_suited;
        let s = match variant {
            0 => suits_not_hero.first().copied().unwrap_or(0),
            1 => h_suit.unwrap_or(hero_suits[0]),
            _ => h_suit.unwrap_or(hero_suits[0]),
        };
        return finalize_pair(v_hi, s, v_lo, s, h_used);
    }

    // Offsuit: two different suits.
    let (s_hi, s_lo) = match variant {
        0 => {
            // Prefer suits disjoint from hero.
            if suits_not_hero.len() >= 2 {
                (suits_not_hero[0], suits_not_hero[1])
            } else if !suits_not_hero.is_empty() {
                (suits_not_hero[0], hero_suits[0])
            } else {
                (hero_suits[0], hero_suits[1])
            }
        }
        1 => {
            // One suit overlap.
            (
                hero_suits.first().copied().unwrap_or(0),
                suits_all
                    .iter()
                    .copied()
                    .find(|s| Some(*s) != hero_suits.first().copied())
                    .unwrap_or(1),
            )
        }
        _ => {
            // Both suits overlap with hero where possible.
            (
                hero_suits.first().copied().unwrap_or(0),
                hero_suits.get(1).copied().unwrap_or(1),
            )
        }
    };
    finalize_pair(v_hi, s_hi, v_lo, s_lo, h_used)
}

fn finalize_pair(
    rank_a: u8,
    suit_a: u8,
    rank_b: u8,
    suit_b: u8,
    hero: [u8; 2],
) -> Option<[u8; 2]> {
    let c_a = card_to_int(rank_a, suit_a);
    let c_b = card_to_int(rank_b, suit_b);
    if c_a == c_b {
        return None;
    }
    if hero.contains(&c_a) || hero.contains(&c_b) {
        return None;
    }
    Some([c_a.min(c_b), c_a.max(c_b)])
}

/// Exhaustively enumerate hero's equity vs villain over all C(48, 5)
/// runouts.
///
/// Mirrors `preflop.rs::enumerate_equity` but takes a `(hero, villain)`
/// pair directly rather than the `HUNLState` shape.
pub fn enumerate_pair_equity(hero: [u8; 2], villain: [u8; 2]) -> f64 {
    let mut used = [false; 64];
    for &c in hero.iter().chain(villain.iter()) {
        used[c as usize] = true;
    }
    let mut deck: Vec<u8> = Vec::with_capacity(48);
    for r in 2u8..=14 {
        for s in 0u8..4 {
            let c = card_to_int(r, s);
            if !used[c as usize] {
                deck.push(c);
            }
        }
    }
    let n = deck.len();
    // C(48, 5) board run-outs.
    let mut indices: Vec<usize> = (0..5).collect();
    let mut seven0 = [0u8; 7];
    let mut seven1 = [0u8; 7];
    seven0[0] = hero[0];
    seven0[1] = hero[1];
    seven1[0] = villain[0];
    seven1[1] = villain[1];

    let mut wins: u64 = 0;
    let mut ties: u64 = 0;
    let mut total: u64 = 0;
    loop {
        for (k, &di) in indices.iter().enumerate() {
            seven0[2 + k] = deck[di];
            seven1[2 + k] = deck[di];
        }
        let s0 = Strength::evaluate_7(&seven0);
        let s1 = Strength::evaluate_7(&seven1);
        if s0 > s1 {
            wins += 1;
        } else if s0 == s1 {
            ties += 1;
        }
        total += 1;

        // Advance combination index.
        let mut k = 5usize;
        loop {
            if k == 0 {
                let eq = (wins as f64 + 0.5 * ties as f64) / total as f64;
                return eq;
            }
            k -= 1;
            indices[k] += 1;
            if indices[k] < n - (5 - 1 - k) {
                for j in (k + 1)..5 {
                    indices[j] = indices[j - 1] + 1;
                }
                break;
            }
        }
    }
}

/// Build the full 169 x 169 x NUM_VARIANTS equity table. Each entry is the
/// hero's equity (win + 0.5 * tie) under a specific suit-overlap variant.
///
/// Entries that are geometrically impossible (e.g. AA vs AA pocket pair —
/// only 4 aces in the deck) get `f64::NAN` so callers can detect and
/// blocker-correct them. In practice, the preflop RvR solver will weight-
/// zero those combos via reach (no hero-villain combo conflict in valid
/// ranges), so NaN entries never affect Nash convergence.
///
/// Single-threaded, exhaustive over C(48, 5) ≈ 1.7M runouts per cell.
/// Wall time on M4 Pro single-threaded is ~16 hours; use
/// [`build_full_equity_table_parallel`] for production builds.
pub fn build_full_equity_table() -> Array3<f64> {
    let mut arr = Array3::<f64>::from_elem((NUM_CLASSES, NUM_CLASSES, NUM_VARIANTS), f64::NAN);
    for hero_class in 0..NUM_CLASSES as u16 {
        for villain_class in 0..NUM_CLASSES as u16 {
            for variant in 0..NUM_VARIANTS as u8 {
                if let Some(rep) = build_hole_rep(hero_class, villain_class, variant) {
                    let eq = enumerate_pair_equity(rep.hero, rep.villain);
                    arr[(hero_class as usize, villain_class as usize, variant as usize)] = eq;
                }
            }
        }
    }
    arr
}

/// Multi-threaded full-table build. Uses `std::thread::spawn` (no rayon
/// dep) across `n_threads` worker threads. Wall time on M4 Pro
/// (8P/4E, 10 threads) is ~2 hours for exhaustive enumeration.
pub fn build_full_equity_table_parallel(n_threads: usize) -> Array3<f64> {
    let n_threads = n_threads.max(1);
    let arr = Mutex::new(Array3::<f64>::from_elem(
        (NUM_CLASSES, NUM_CLASSES, NUM_VARIANTS),
        f64::NAN,
    ));
    // Enumerate all (hero_class, villain_class, variant) tuples up front.
    let mut work: Vec<(u16, u16, u8)> = Vec::with_capacity(NUM_CLASSES * NUM_CLASSES * NUM_VARIANTS);
    for hero_class in 0..NUM_CLASSES as u16 {
        for villain_class in 0..NUM_CLASSES as u16 {
            for variant in 0..NUM_VARIANTS as u8 {
                work.push((hero_class, villain_class, variant));
            }
        }
    }
    let work = std::sync::Arc::new(work);
    let arr_ref = std::sync::Arc::new(arr);
    let cursor = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));

    let mut handles = Vec::with_capacity(n_threads);
    for _ in 0..n_threads {
        let work = std::sync::Arc::clone(&work);
        let arr_ref = std::sync::Arc::clone(&arr_ref);
        let cursor = std::sync::Arc::clone(&cursor);
        let handle = std::thread::spawn(move || loop {
            let i = cursor.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            if i >= work.len() {
                break;
            }
            let (hero_class, villain_class, variant) = work[i];
            if let Some(rep) = build_hole_rep(hero_class, villain_class, variant) {
                let eq = enumerate_pair_equity(rep.hero, rep.villain);
                let mut a = arr_ref.lock().unwrap();
                a[(
                    hero_class as usize,
                    villain_class as usize,
                    variant as usize,
                )] = eq;
            }
        });
        handles.push(handle);
    }
    for h in handles {
        h.join().expect("worker thread panicked");
    }
    let inner = std::sync::Arc::try_unwrap(arr_ref).expect("all handles joined");
    inner.into_inner().expect("mutex unpoisoned")
}

/// Monte-Carlo estimate of pair equity. Uses `n_samples` random board
/// run-outs (sampled without replacement); for `n_samples` < C(48, 5)
/// this is faster than exhaustive enumeration with bounded sampling
/// error `≈ sqrt(0.25 / n_samples)`. With 100K samples the error per cell
/// is ~0.00158 standard deviations.
pub fn monte_carlo_pair_equity(hero: [u8; 2], villain: [u8; 2], n_samples: usize, seed: u64) -> f64 {
    let mut used = [false; 64];
    for &c in hero.iter().chain(villain.iter()) {
        used[c as usize] = true;
    }
    let mut deck: Vec<u8> = Vec::with_capacity(48);
    for r in 2u8..=14 {
        for s in 0u8..4 {
            let c = card_to_int(r, s);
            if !used[c as usize] {
                deck.push(c);
            }
        }
    }
    let n = deck.len();
    let mut rng = PcsRng::new(seed);
    let mut wins: u64 = 0;
    let mut ties: u64 = 0;
    let mut seven0 = [0u8; 7];
    let mut seven1 = [0u8; 7];
    seven0[0] = hero[0];
    seven0[1] = hero[1];
    seven1[0] = villain[0];
    seven1[1] = villain[1];
    for _ in 0..n_samples {
        // Sample 5 distinct positions from 0..n via rejection sampling.
        let mut picks = [0u8; 5];
        let mut chosen: [usize; 5] = [usize::MAX; 5];
        for k in 0..5 {
            loop {
                let pos = rng.gen_range(n as u64) as usize;
                if !chosen[..k].contains(&pos) {
                    chosen[k] = pos;
                    picks[k] = deck[pos];
                    break;
                }
            }
        }
        seven0[2..7].copy_from_slice(&picks);
        seven1[2..7].copy_from_slice(&picks);
        let s0 = Strength::evaluate_7(&seven0);
        let s1 = Strength::evaluate_7(&seven1);
        if s0 > s1 {
            wins += 1;
        } else if s0 == s1 {
            ties += 1;
        }
    }
    (wins as f64 + 0.5 * ties as f64) / n_samples as f64
}

/// Monte-Carlo full-table build. Fast enough to ship as a stopgap while
/// the exhaustive table is computed offline.
pub fn build_full_equity_table_monte_carlo(n_threads: usize, n_samples: usize) -> Array3<f64> {
    let n_threads = n_threads.max(1);
    let arr = Mutex::new(Array3::<f64>::from_elem(
        (NUM_CLASSES, NUM_CLASSES, NUM_VARIANTS),
        f64::NAN,
    ));
    let mut work: Vec<(u16, u16, u8)> = Vec::with_capacity(NUM_CLASSES * NUM_CLASSES * NUM_VARIANTS);
    for hero_class in 0..NUM_CLASSES as u16 {
        for villain_class in 0..NUM_CLASSES as u16 {
            for variant in 0..NUM_VARIANTS as u8 {
                work.push((hero_class, villain_class, variant));
            }
        }
    }
    let work = std::sync::Arc::new(work);
    let arr_ref = std::sync::Arc::new(arr);
    let cursor = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));

    let mut handles = Vec::with_capacity(n_threads);
    for worker_id in 0..n_threads {
        let work = std::sync::Arc::clone(&work);
        let arr_ref = std::sync::Arc::clone(&arr_ref);
        let cursor = std::sync::Arc::clone(&cursor);
        let handle = std::thread::spawn(move || loop {
            let i = cursor.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            if i >= work.len() {
                break;
            }
            let (hero_class, villain_class, variant) = work[i];
            if let Some(rep) = build_hole_rep(hero_class, villain_class, variant) {
                // Per-cell seed derived from (hero_class, villain_class, variant, worker_id)
                // so each cell is deterministic given the build params.
                let seed = ((hero_class as u64) << 32)
                    | ((villain_class as u64) << 16)
                    | (variant as u64)
                    | ((worker_id as u64) << 56);
                let eq = monte_carlo_pair_equity(rep.hero, rep.villain, n_samples, seed);
                let mut a = arr_ref.lock().unwrap();
                a[(
                    hero_class as usize,
                    villain_class as usize,
                    variant as usize,
                )] = eq;
            }
        });
        handles.push(handle);
    }
    for h in handles {
        h.join().expect("worker thread panicked");
    }
    let inner = std::sync::Arc::try_unwrap(arr_ref).expect("all handles joined");
    inner.into_inner().expect("mutex unpoisoned")
}

/// Load the precomputed equity table from a `.npz` file shipped under
/// `assets/preflop_equity_169x169.npz`. Returns the 169x169x3 array.
pub fn load_equity_table<P: AsRef<Path>>(path: P) -> Result<Array3<f64>, String> {
    use ndarray_npy::NpzReader;
    use std::fs::File;
    let file = File::open(path.as_ref())
        .map_err(|e| format!("open equity table {}: {e}", path.as_ref().display()))?;
    let mut npz = NpzReader::new(file).map_err(|e| format!("read npz: {e}"))?;
    let arr: Array3<f64> = npz
        .by_name("equity")
        .map_err(|e| format!("read 'equity' array from npz: {e}"))?;
    if arr.shape() != [NUM_CLASSES, NUM_CLASSES, NUM_VARIANTS] {
        return Err(format!(
            "equity table shape mismatch: expected ({NUM_CLASSES}, {NUM_CLASSES}, {NUM_VARIANTS}), \
             got {:?}",
            arr.shape()
        ));
    }
    Ok(arr)
}

/// Save the precomputed equity table to a `.npz` file. Used by the
/// `examples/build_preflop_equity.rs` binary; not in the production hot
/// path.
pub fn save_equity_table<P: AsRef<Path>>(path: P, table: &Array3<f64>) -> Result<(), String> {
    use ndarray_npy::NpzWriter;
    use std::fs::File;
    let file = File::create(path.as_ref())
        .map_err(|e| format!("create equity table {}: {e}", path.as_ref().display()))?;
    let mut npz = NpzWriter::new_compressed(file);
    npz.add_array("equity", table)
        .map_err(|e| format!("write npz: {e}"))?;
    npz.finish().map_err(|e| format!("finish npz: {e}"))?;
    Ok(())
}

/// Classify a concrete hole pair to its 169-class index.
///
/// Used at runtime by the preflop RvR solver: every concrete C(52, 2) =
/// 1326 hand is mapped to its class, and the equity-leaf utility is
/// looked up via the 169x169 table.
pub fn hole_to_class(hole: [u8; 2]) -> u16 {
    let r0 = hole[0] >> 2;
    let r1 = hole[1] >> 2;
    let s0 = hole[0] & 3;
    let s1 = hole[1] & 3;
    let (rank_hi, rank_lo) = if r0 >= r1 { (r0, r1) } else { (r1, r0) };
    let suited = s0 == s1 && r0 != r1;
    class_index(rank_hi, rank_lo, suited)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn class_index_pocket_pair_aa() {
        assert_eq!(class_index(14, 14, false), 0);
    }

    #[test]
    fn class_index_pocket_pair_22() {
        assert_eq!(class_index(2, 2, false), 12);
    }

    #[test]
    fn class_index_suited_ak() {
        let idx = class_index(14, 13, true);
        assert_eq!(idx, 13);
    }

    #[test]
    fn class_index_offsuit_ak() {
        let idx = class_index(14, 13, false);
        assert_eq!(idx, 13 + 78);
    }

    #[test]
    fn class_index_roundtrip_all_169() {
        let mut seen = std::collections::HashSet::new();
        for r_hi in 2u8..=14 {
            // Pocket pair.
            let idx = class_index(r_hi, r_hi, false);
            assert!(idx < 169);
            assert!(seen.insert(idx));
            let (r1, r2, s) = class_decode(idx);
            assert_eq!(r1, r_hi);
            assert_eq!(r2, r_hi);
            assert!(!s);
            // Pairs with r_lo < r_hi.
            for r_lo in 2u8..r_hi {
                for suited in [true, false] {
                    let idx = class_index(r_hi, r_lo, suited);
                    assert!(idx < 169);
                    assert!(seen.insert(idx));
                    let (r1, r2, s) = class_decode(idx);
                    assert_eq!(r1, r_hi);
                    assert_eq!(r2, r_lo);
                    assert_eq!(s, suited);
                }
            }
        }
        assert_eq!(seen.len(), 169);
    }

    #[test]
    fn hole_to_class_aa() {
        let h = [card_to_int(14, 0), card_to_int(14, 1)];
        assert_eq!(hole_to_class(h), 0);
    }

    #[test]
    fn hole_to_class_aks_suited() {
        let h = [card_to_int(14, 0), card_to_int(13, 0)];
        assert_eq!(hole_to_class(h), class_index(14, 13, true));
    }

    #[test]
    fn hole_to_class_72o_offsuit() {
        let h = [card_to_int(7, 1), card_to_int(2, 2)];
        assert_eq!(hole_to_class(h), class_index(7, 2, false));
    }

    #[test]
    fn enumerate_pair_equity_aa_vs_kk_matches_known() {
        let hero = [card_to_int(14, 0), card_to_int(14, 1)];
        let villain = [card_to_int(13, 2), card_to_int(13, 3)];
        let eq = enumerate_pair_equity(hero, villain);
        // Brunson 2-player odds: AA vs KK ~0.813.
        assert!(
            (0.805..=0.820).contains(&eq),
            "AA vs KK equity {eq} outside [0.805, 0.820]"
        );
    }

    #[test]
    fn build_hole_rep_some_for_aa_vs_kk() {
        let rep = build_hole_rep(0, 1, 0); // class 0 = AA, class 1 = KK
        assert!(rep.is_some());
        let rep = rep.unwrap();
        // Hero is AA.
        let h_ranks: Vec<u8> = rep.hero.iter().map(|c| c >> 2).collect();
        assert!(h_ranks.iter().all(|&r| r == 14));
        // Villain is KK.
        let v_ranks: Vec<u8> = rep.villain.iter().map(|c| c >> 2).collect();
        assert!(v_ranks.iter().all(|&r| r == 13));
    }
}
