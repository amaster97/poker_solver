//! HUNL Rust-only correctness tests (PR 6).
//!
//! Verifies game-state semantics, bucket-roundtrip parity (byte-for-byte
//! against Python via PyO3 introspection), evaluator parity, and end-to-end
//! solve smoke tests. Bucket-roundtrip + Strength-ordering tests run on
//! large random batches (10K boards, 1K hand pairs) to catch canonicalization
//! drift early.
//!
//! Source-of-truth chain: PR 6 spec §7.1 Test 3 + §8.3 deliverable list +
//! §9 critical-correctness items #1, #2, #3, #6.
//!
//! Cross-tier introspection uses `pyo3::Python::with_gil` to invoke the
//! Python reference tier from inside `#[test]`. Agent B's `Cargo.toml`
//! provides `pyo3` as a dev-dependency with `auto-initialize`, so
//! `cargo test --package cfr_core --test test_hunl_rust` runs without
//! additional setup.
//!
//! **IMPORTANT — run with single-threaded test execution:**
//!
//! ```bash
//! cargo test --package cfr_core --test test_hunl_rust -- --test-threads=1
//! ```
//!
//! Python module-import is process-global and not thread-safe under PyO3's
//! `auto-initialize` (concurrent `Python::with_gil` blocks race on
//! `poker_solver.__init__` and produce circular-import errors). Multi-
//! threaded `cargo test` (the default `--test-threads=N`) is not safe for
//! these PyO3 tests. CI should always pass `--test-threads=1` or set
//! `CARGO_TEST_THREADS=1`.

use std::sync::Arc;

use cfr_core::abstraction::{canonicalize, load_abstraction, lookup_bucket};
use cfr_core::hunl::{
    default_tiny_subgame, HUNLConfig, HUNLState, Street, ACTION_ALL_IN, ACTION_BET_100,
    ACTION_BET_150, ACTION_BET_200, ACTION_BET_33, ACTION_BET_75, ACTION_CALL, ACTION_CHECK,
    ACTION_FOLD, ACTION_RAISE_100, ACTION_RAISE_150, ACTION_RAISE_200, ACTION_RAISE_33,
    ACTION_RAISE_75,
};
use cfr_core::hunl_eval::Strength;
use cfr_core::hunl_solver::{solve_hunl_postflop, HUNLSolveError};
use cfr_core::hunl_tree::HUNLTree;

use pyo3::prelude::*;
use pyo3::types::{IntoPyDict, PyList, PyTuple};

// ---------------------------------------------------------------------------
// Test fixture: river-only postflop config (mirrors PR 3 default_tiny_subgame).
// ---------------------------------------------------------------------------

/// Card ints for the canonical river fixture (AhKc vs QdQh on As7c2dKh5s).
/// Encoding: `card_int = rank * 4 + suit`, range `[8, 59]`.
const FIXTURE_RIVER_BOARD: [u8; 5] = [
    14 * 4,     // As (suit 0)
    7 * 4 + 3,  // 7c (suit 3)
    2 * 4 + 2,  // 2d (suit 2)
    13 * 4 + 1, // Kh (suit 1)
    5 * 4,      // 5s (suit 0)
];

const FIXTURE_RIVER_HOLE_P0: [u8; 2] = [14 * 4 + 1, 13 * 4 + 3]; // Ah Kc
const FIXTURE_RIVER_HOLE_P1: [u8; 2] = [12 * 4 + 2, 12 * 4 + 1]; // Qd Qh

// ---------------------------------------------------------------------------
// PyO3 cross-tier helpers.
// ---------------------------------------------------------------------------

fn py_card<'py>(py: Python<'py>, card_int: u8) -> PyResult<Bound<'py, PyAny>> {
    let card_module = py.import("poker_solver.card")?;
    let int_to_card = card_module.getattr("int_to_card")?;
    int_to_card.call1((card_int,))
}

fn py_river_subgame<'py>(py: Python<'py>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let hunl_module = py.import("poker_solver.hunl")?;
    let default_tiny = hunl_module.getattr("default_tiny_subgame")?;
    let config = default_tiny.call0()?;
    let hunl_poker = hunl_module.getattr("HUNLPoker")?;
    let game = hunl_poker.call1((config.clone(),))?;
    Ok((config, game))
}

fn py_compare_seven<'py>(
    py: Python<'py>,
    hand_a: &[u8; 7],
    hand_b: &[u8; 7],
) -> PyResult<std::cmp::Ordering> {
    let evaluator = py.import("poker_solver.evaluator")?;
    let evaluate = evaluator.getattr("evaluate")?;
    let cards_a: Vec<Bound<'_, PyAny>> = hand_a
        .iter()
        .map(|c| py_card(py, *c))
        .collect::<PyResult<Vec<_>>>()?;
    let cards_b: Vec<Bound<'_, PyAny>> = hand_b
        .iter()
        .map(|c| py_card(py, *c))
        .collect::<PyResult<Vec<_>>>()?;
    let list_a = PyList::new(py, cards_a)?;
    let list_b = PyList::new(py, cards_b)?;
    let rank_a = evaluate.call1((list_a,))?;
    let rank_b = evaluate.call1((list_b,))?;
    let lt: bool = rank_a
        .rich_compare(rank_b.clone(), pyo3::pyclass::CompareOp::Lt)?
        .extract()?;
    let eq: bool = rank_a
        .rich_compare(rank_b, pyo3::pyclass::CompareOp::Eq)?
        .extract()?;
    if eq {
        Ok(std::cmp::Ordering::Equal)
    } else if lt {
        Ok(std::cmp::Ordering::Less)
    } else {
        Ok(std::cmp::Ordering::Greater)
    }
}

fn py_canonicalize<'py>(
    py: Python<'py>,
    board: &[u8],
    hole: &[u8; 2],
) -> PyResult<(String, String)> {
    let buckets = py.import("poker_solver.abstraction.buckets")?;
    let canon = buckets.getattr("_canonicalize")?;
    let card_module = py.import("poker_solver.card")?;
    let int_to_card = card_module.getattr("int_to_card")?;
    let board_cards: Vec<Bound<'_, PyAny>> = board
        .iter()
        .map(|c| int_to_card.call1((*c,)))
        .collect::<PyResult<Vec<_>>>()?;
    let hole_cards: Vec<Bound<'_, PyAny>> = hole
        .iter()
        .map(|c| int_to_card.call1((*c,)))
        .collect::<PyResult<Vec<_>>>()?;
    let board_tuple = PyTuple::new(py, board_cards)?;
    let hole_tuple = PyTuple::new(py, hole_cards)?;
    let result = canon.call1((board_tuple, hole_tuple))?;
    let pair: (String, String) = result.extract()?;
    Ok(pair)
}

fn py_lookup_bucket<'py>(
    py: Python<'py>,
    npz_path: &str,
    board: &[u8],
    hole: &[u8; 2],
    street: Street,
) -> PyResult<i32> {
    let buckets = py.import("poker_solver.abstraction.buckets")?;
    let load = buckets.getattr("load_abstraction")?;
    let path_obj = py.import("pathlib")?.getattr("Path")?.call1((npz_path,))?;
    let tables = load.call1((path_obj,))?;
    let lookup = buckets.getattr("lookup_bucket")?;
    let card_module = py.import("poker_solver.card")?;
    let int_to_card = card_module.getattr("int_to_card")?;
    let board_cards: Vec<Bound<'_, PyAny>> = board
        .iter()
        .map(|c| int_to_card.call1((*c,)))
        .collect::<PyResult<Vec<_>>>()?;
    let hole_cards: Vec<Bound<'_, PyAny>> = hole
        .iter()
        .map(|c| int_to_card.call1((*c,)))
        .collect::<PyResult<Vec<_>>>()?;
    let board_tuple = PyTuple::new(py, board_cards)?;
    let hole_tuple = PyTuple::new(py, hole_cards)?;
    let street_module = py.import("poker_solver.hunl")?;
    let street_class = street_module.getattr("Street")?;
    let street_value = match street {
        Street::Preflop => street_class.getattr("PREFLOP")?,
        Street::Flop => street_class.getattr("FLOP")?,
        Street::Turn => street_class.getattr("TURN")?,
        Street::River => street_class.getattr("RIVER")?,
        Street::Showdown => street_class.getattr("SHOWDOWN")?,
    };
    let bucket = lookup.call1((tables, board_tuple, hole_tuple, street_value))?;
    let v: i32 = bucket.extract()?;
    Ok(v)
}

// ---------------------------------------------------------------------------
// Deterministic LCG so reproducibility is preserved across test runs.
// ---------------------------------------------------------------------------

struct Lcg(u64);
impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg(seed.wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ 0xDEAD_BEEF)
    }
    fn next_u32(&mut self) -> u32 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.0 >> 32) as u32
    }
    fn next_range(&mut self, n: u32) -> u32 {
        self.next_u32() % n
    }
}

fn deal_distinct(rng: &mut Lcg, count: usize, exclude: &[u8]) -> Vec<u8> {
    let mut available: Vec<u8> = (8u8..60u8).filter(|c| !exclude.contains(c)).collect();
    let mut out = Vec::with_capacity(count);
    for _ in 0..count {
        let n = available.len() as u32;
        let idx = rng.next_range(n) as usize;
        out.push(available.swap_remove(idx));
    }
    out
}

// ---------------------------------------------------------------------------
// Test 1: postflop initial state contributions / stacks / cur_player.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_initial_state_blinds_posted_correctly() {
    // PR 6 spec §"HUNLState::initial": postflop subgames start with both
    // players carrying `starting_stack` behind and `initial_contributions`
    // already in the pot (dead money). This is the canonical sanity check.
    let state = HUNLState::initial(Arc::new(default_tiny_subgame()));
    assert_eq!(state.contributions, [500, 500], "contributions wrong");
    assert_eq!(state.stacks, [1000, 1000], "stacks wrong");
    assert_eq!(state.to_call, 0, "to_call at root should be 0");
    assert_eq!(state.cur_player, 1, "P1 (BB-side) acts first postflop");
    assert_eq!(state.street, Street::River);
    assert!(!state.folded[0] && !state.folded[1]);
}

// ---------------------------------------------------------------------------
// Test 2: legal actions at the river subgame root match Python's.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_legal_actions_at_river_subgame_root() {
    Python::with_gil(|py| -> PyResult<()> {
        let (_cfg, game) = py_river_subgame(py)?;
        let state = game.call_method0("initial_state")?;
        let py_actions: Vec<u8> = game.call_method1("legal_actions", (state,))?.extract()?;
        assert!(
            !py_actions.is_empty(),
            "Python tier returned empty legal action set at root"
        );
        let rs_state = HUNLState::initial(Arc::new(default_tiny_subgame()));
        let rs_actions = rs_state.legal_actions();
        assert_eq!(
            rs_actions, py_actions,
            "legal_actions diverges at river subgame root: rs={:?} py={:?}",
            rs_actions, py_actions
        );
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 3: apply() advances state correctly + terminal utility.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_apply_advances_state_correctly() {
    let mut state = HUNLState::initial(Arc::new(default_tiny_subgame()));
    let actions = state.legal_actions();
    assert!(
        actions.contains(&ACTION_CHECK),
        "river root should allow check"
    );
    state = state.apply(ACTION_CHECK);
    state = state.apply(ACTION_CHECK);
    assert!(state.is_terminal(), "two checks should reach terminal");
    let utility = state.utility();
    // AhKc vs QdQh on As7c2dKh5s: P0's two-pair (Aces+Kings) > P1's one
    // pair of Queens with K/A kickers? Wait - let me re-evaluate.
    // P0: Ah Kc + As 7c 2d Kh 5s -> two pair AA KK (using As, Ah, Kc, Kh)
    // P1: Qd Qh + As 7c 2d Kh 5s -> one pair QQ (Qd Qh) with A K 7 kickers
    // -> Two pair (AAKK) >> One pair (QQ). P0 wins big.
    assert!(utility[0] > 0.0, "P0 should win the showdown");
    assert!(utility[1] < 0.0, "P1 should lose the showdown");
    assert!(
        (utility[0] + utility[1]).abs() < 1e-9,
        "zero-sum check: u0+u1 should be 0, got {:?}",
        utility
    );
}

// ---------------------------------------------------------------------------
// Test 4: infoset_key lossless format matches Python byte-for-byte.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_infoset_key_lossless_format() {
    Python::with_gil(|py| -> PyResult<()> {
        let (_cfg, game) = py_river_subgame(py)?;
        let py_state = game.call_method0("initial_state")?;
        for player in 0..2u8 {
            let py_key: String = game
                .call_method1("infoset_key", (py_state.clone(), player))?
                .extract()?;
            let rs_state = HUNLState::initial(Arc::new(default_tiny_subgame()));
            let rs_key = rs_state.infoset_key(player, None);
            assert_eq!(
                rs_key, py_key,
                "lossless infoset_key drift at root P{}: rs={:?} py={:?}",
                player, rs_key, py_key
            );
        }
        // Walk a short action sequence and recheck.
        let py_state2 = game.call_method1("apply", (py_state, ACTION_CHECK))?;
        let py_key2: String = game
            .call_method1("infoset_key", (py_state2.clone(), 0u8))?
            .extract()?;
        let rs_state = HUNLState::initial(Arc::new(default_tiny_subgame()));
        let rs_state2 = rs_state.apply(ACTION_CHECK);
        let rs_key2 = rs_state2.infoset_key(0, None);
        assert_eq!(
            rs_key2, py_key2,
            "lossless infoset_key drift after check: rs={:?} py={:?}",
            rs_key2, py_key2
        );

        // 100 random walks (per spec §8.3 #4).
        let mut rng = Lcg::new(101);
        for _ in 0..98 {
            let py_walk_start = game.call_method0("initial_state")?;
            let mut py_walk: Bound<'_, PyAny> = py_walk_start;
            let mut rs_walk = HUNLState::initial(Arc::new(default_tiny_subgame()));
            for _ in 0..3 {
                if rs_walk.is_terminal() {
                    break;
                }
                let legal = rs_walk.legal_actions();
                if legal.is_empty() {
                    break;
                }
                let pick = legal[(rng.next_u32() as usize) % legal.len()];
                rs_walk = rs_walk.apply(pick);
                py_walk = game.call_method1("apply", (py_walk, pick))?;
            }
            if rs_walk.is_terminal() {
                continue;
            }
            let player = rs_walk.cur_player;
            if !(0..=1).contains(&player) {
                continue;
            }
            let py_key_iter: String = game
                .call_method1("infoset_key", (py_walk, player as u8))?
                .extract()?;
            let rs_key_iter = rs_walk.infoset_key(player as u8, None);
            assert_eq!(
                rs_key_iter, py_key_iter,
                "lossless infoset_key drift on random walk for P{}",
                player
            );
        }
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 5: infoset_key bucketed format matches Python byte-for-byte.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_infoset_key_bucketed_format() {
    Python::with_gil(|py| -> PyResult<()> {
        // Use PR 5 Agent C's river-only synthetic abstraction (pins the
        // fixture's board + both fixture hands; lookup never misses).
        let sys_path = py.import("sys")?.getattr("path")?;
        let project_root = std::env::current_dir().unwrap();
        sys_path.call_method1("insert", (0u8, project_root.to_str().unwrap()))?;
        let fixtures = py.import("tests.fixtures.hunl_solve_fixtures")?;
        let ref_obj = fixtures.call_method0("river_only_synthetic_abstraction_ref")?;
        let source_path: String = ref_obj.getattr("source_path")?.extract()?;

        // Python tier with abstraction attached.
        let buckets = py.import("poker_solver.abstraction.buckets")?;
        let abstraction_ref_class = buckets.getattr("AbstractionRef")?;
        let py_ref = abstraction_ref_class.call1((source_path.clone(), "test-river-only-v1"))?;
        let hunl_module = py.import("poker_solver.hunl")?;
        let default_tiny = hunl_module.getattr("default_tiny_subgame")?;
        let base_cfg = default_tiny.call0()?;
        let dataclasses = py.import("dataclasses")?;
        let kwargs = [("abstraction", py_ref)].into_py_dict(py)?;
        let py_cfg = dataclasses
            .getattr("replace")?
            .call((base_cfg,), Some(&kwargs))?;
        let hunl_poker = hunl_module.getattr("HUNLPoker")?;
        let py_game = hunl_poker.call1((py_cfg,))?;
        let py_state = py_game.call_method0("initial_state")?;

        // Rust tier: load tables directly (Agent B's `load_abstraction` API).
        let rs_tables = load_abstraction(std::path::Path::new(&source_path))
            .expect("Rust load_abstraction failed");
        let rs_state = HUNLState::initial(Arc::new(default_tiny_subgame()));

        for player in 0..2u8 {
            let py_key: String = py_game
                .call_method1("infoset_key", (py_state.clone(), player))?
                .extract()?;
            let rs_key = rs_state.infoset_key(player, Some(&rs_tables));
            assert_eq!(
                rs_key, py_key,
                "bucketed infoset_key drift at root P{}: rs={:?} py={:?}",
                player, rs_key, py_key
            );
        }
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 6: canonicalization parity over 10K random (board, hole) inputs.
// ---------------------------------------------------------------------------

#[test]
fn test_abstraction_canonicalization_matches_python() {
    // Spec §9 #2: the SINGLE MOST FRAGILE cross-tier seam. 10K random inputs
    // exercise both string-key components (board_key + hand_key).
    Python::with_gil(|py| -> PyResult<()> {
        let mut rng = Lcg::new(42);
        let mut divergence_count: usize = 0;
        const N: usize = 10_000;
        for i in 0..N {
            let board_len = 3 + (rng.next_range(3) as usize); // 3, 4, or 5
            let board = deal_distinct(&mut rng, board_len, &[]);
            let hole_pair = deal_distinct(&mut rng, 2, &board);
            let hole: [u8; 2] = [hole_pair[0], hole_pair[1]];
            let py_keys = py_canonicalize(py, &board, &hole)?;
            let (rs_board, rs_hand) = canonicalize(&board, &hole);
            if rs_board != py_keys.0 || rs_hand != py_keys.1 {
                if divergence_count < 5 {
                    eprintln!(
                        "iter {}: divergence on board={:?} hole={:?}",
                        i, board, hole
                    );
                    eprintln!(
                        "  rs=({:?}, {:?})  py=({:?}, {:?})",
                        rs_board, rs_hand, py_keys.0, py_keys.1
                    );
                }
                divergence_count += 1;
            }
        }
        assert_eq!(
            divergence_count, 0,
            "{}/{} canonicalization divergences (spec §9 #2)",
            divergence_count, N
        );
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 7: lookup_bucket parity on the river fixture (pinned coverage).
// ---------------------------------------------------------------------------

#[test]
fn test_abstraction_lookup_bucket_matches_python() {
    Python::with_gil(|py| -> PyResult<()> {
        let sys_path = py.import("sys")?.getattr("path")?;
        let project_root = std::env::current_dir().unwrap();
        sys_path.call_method1("insert", (0u8, project_root.to_str().unwrap()))?;
        let fixtures = py.import("tests.fixtures.hunl_solve_fixtures")?;
        let ref_obj = fixtures.call_method0("river_only_synthetic_abstraction_ref")?;
        let source_path: String = ref_obj.getattr("source_path")?.extract()?;
        let rs_tables = load_abstraction(std::path::Path::new(&source_path))
            .expect("Rust load_abstraction failed");

        let board = FIXTURE_RIVER_BOARD.to_vec();
        let pinned_holes = [FIXTURE_RIVER_HOLE_P0, FIXTURE_RIVER_HOLE_P1];
        const N: usize = 200;
        let mut divergence_count: usize = 0;
        for i in 0..N {
            let hole = pinned_holes[i % 2];
            let py_bucket = py_lookup_bucket(py, &source_path, &board, &hole, Street::River)?;
            let rs_bucket = lookup_bucket(&rs_tables, &board, &hole, Street::River);
            if rs_bucket != py_bucket {
                if divergence_count < 5 {
                    eprintln!(
                        "iter {}: hole={:?}: rs={} py={}",
                        i, hole, rs_bucket, py_bucket
                    );
                }
                divergence_count += 1;
            }
        }
        assert_eq!(
            divergence_count, 0,
            "{}/{} bucket-lookup divergences on river fixture",
            divergence_count, N
        );
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 8: HUNLTree::build terminates with bounded node count.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_tree_build_terminates() {
    let config = Arc::new(default_tiny_subgame());
    let tree = HUNLTree::build(config, None);
    assert!(!tree.nodes.is_empty(), "tree must have at least the root");
    assert!(
        tree.nodes.len() < 50_000,
        "river subgame tree should be <50K nodes (got {})",
        tree.nodes.len()
    );
}

// ---------------------------------------------------------------------------
// Test 9: Strength evaluator ORDERING parity over 1000 random 7-card pairs.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_strength_eval_matches_python() {
    Python::with_gil(|py| -> PyResult<()> {
        let mut rng = Lcg::new(123);
        let mut divergence_count: usize = 0;
        const N: usize = 1_000;
        for _ in 0..N {
            let cards_a = deal_distinct(&mut rng, 7, &[]);
            let hand_a: [u8; 7] = cards_a.as_slice().try_into().unwrap();
            let cards_b = deal_distinct(&mut rng, 7, &[]);
            let hand_b: [u8; 7] = cards_b.as_slice().try_into().unwrap();
            let rs_a = Strength::evaluate_7(&hand_a);
            let rs_b = Strength::evaluate_7(&hand_b);
            let rs_cmp = rs_a.cmp(&rs_b);
            let py_cmp = py_compare_seven(py, &hand_a, &hand_b)?;
            if rs_cmp != py_cmp {
                if divergence_count < 5 {
                    eprintln!(
                        "ordering drift on hand_a={:?} hand_b={:?}: rs={:?} py={:?}",
                        hand_a, hand_b, rs_cmp, py_cmp
                    );
                }
                divergence_count += 1;
            }
        }
        assert_eq!(
            divergence_count, 0,
            "{}/{} Strength-ordering divergences",
            divergence_count, N
        );
        Ok(())
    })
    .unwrap();
}

// ---------------------------------------------------------------------------
// Test 10: Strength evaluator returns equal values on tied 7-card hands.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_strength_eval_handles_ties() {
    // Board J♠ J♥ T♦ K♣ Q♠. Both players' hole cards are kicker-irrelevant.
    // Both 7-card hands evaluate to the same best-5: pair of Jacks +
    // K-Q-T kickers from the board.
    let board = [
        11u8 * 4,     // J♠
        11u8 * 4 + 1, // J♥
        10u8 * 4 + 2, // T♦
        13u8 * 4 + 3, // K♣
        12u8 * 4,     // Q♠
    ];
    let p0_hand: [u8; 7] = [
        board[0],
        board[1],
        board[2],
        board[3],
        board[4],
        2u8 * 4 + 2,
        3u8 * 4 + 3,
    ];
    let p1_hand: [u8; 7] = [
        board[0],
        board[1],
        board[2],
        board[3],
        board[4],
        4u8 * 4 + 2,
        5u8 * 4 + 3,
    ];
    let s0 = Strength::evaluate_7(&p0_hand);
    let s1 = Strength::evaluate_7(&p1_hand);
    assert_eq!(
        s0, s1,
        "tied 7-card hands should produce equal Strength: s0={:?} s1={:?}",
        s0, s1
    );
}

// ---------------------------------------------------------------------------
// Test 11: solve_hunl_postflop runs to completion on the river subgame.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_solve_river_subgame_smoke() {
    let config = default_tiny_subgame();
    let result = solve_hunl_postflop(&config, None, 100, 1.5, 0.0, 2.0, None, Some(42), None);
    assert!(
        result.is_ok(),
        "river subgame solve returned error: {:?}",
        result.err()
    );
    let output = result.unwrap();
    assert!(
        !output.average_strategy.is_empty(),
        "river subgame solve produced empty strategy"
    );
    assert_eq!(output.iterations, 100, "iteration count round-trip");
    for (key, probs) in &output.average_strategy {
        let sum: f64 = probs.iter().sum();
        assert!(
            (sum - 1.0).abs() < 1e-6,
            "infoset {}: probs sum {} differs from 1.0",
            key,
            sum
        );
    }
}

// ---------------------------------------------------------------------------
// Test 12: solve_hunl_postflop rejects preflop configs.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_solve_reject_preflop() {
    let config = HUNLConfig {
        starting_street: Street::Preflop,
        initial_board: Vec::new(),
        initial_pot: 0,
        initial_contributions: [0, 0],
        initial_hole_cards: None,
        ..HUNLConfig::default()
    };
    let result = solve_hunl_postflop(&config, None, 10, 1.5, 0.0, 2.0, None, None, None);
    match result {
        Err(HUNLSolveError::PreflopNotSupported) => {} // expected
        Err(e) => panic!("preflop should yield PreflopNotSupported, got: {:?}", e),
        Ok(_) => panic!("preflop config should be rejected"),
    }
}

// ---------------------------------------------------------------------------
// Test 13: action ID constants match Python's canonical table.
// ---------------------------------------------------------------------------

#[test]
fn test_hunl_action_ids_match_python_constants() {
    // Spec §4.1 + §9 #15: Rust action constants must mirror Python's exactly.
    assert_eq!(ACTION_FOLD, 0);
    assert_eq!(ACTION_CHECK, 1);
    assert_eq!(ACTION_CALL, 2);
    assert_eq!(ACTION_BET_33, 3);
    assert_eq!(ACTION_BET_75, 4);
    assert_eq!(ACTION_BET_100, 5);
    assert_eq!(ACTION_BET_150, 6);
    assert_eq!(ACTION_BET_200, 7);
    assert_eq!(ACTION_RAISE_33, 8);
    assert_eq!(ACTION_RAISE_75, 9);
    assert_eq!(ACTION_RAISE_100, 10);
    assert_eq!(ACTION_RAISE_150, 11);
    assert_eq!(ACTION_RAISE_200, 12);
    assert_eq!(ACTION_ALL_IN, 13);
}
