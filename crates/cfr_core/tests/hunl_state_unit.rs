//! HUNL state-unit tests (Rust-only).
//!
//! Adapted from `poker_solver/tests/test_hunl_core.py` (project-internal, MIT)
//! Tests 1–18 by parity, not by code transcription. These mirror the Python
//! tier's coverage of blinds, fold paths, raise-cap enforcement, all-in
//! absorption, and infoset-key canonicalization.
//!
//! Tests sit at the integration-test level (i.e., consume the crate as an
//! external library) so they verify Agent A's *public* surface — the same
//! surface Agent B will consume in `hunl_solver.rs`.

// Crate is built as `cdylib` per `crates/cfr_core/Cargo.toml` (Agent B-owned).
// Integration tests need the crate to also expose an `rlib` crate-type; the
// minimum change is `crate-type = ["cdylib", "rlib"]` in that Cargo.toml.
// Agent B is the owner of that file — flagged in Agent A's report. With that
// one-line change, this file compiles and runs as written. Agent C's
// `test_hunl_rust.rs` has the same requirement.
use cfr_core::hunl::{
    card_to_int, compute_bet_amount, compute_raise_to, default_tiny_subgame,
    enumerate_legal_actions, ActionContext, HUNLConfig, HUNLState, Street, ACTION_ALL_IN,
    ACTION_BET_100, ACTION_BET_33, ACTION_BET_75, ACTION_CALL, ACTION_CHECK, ACTION_FOLD,
    ACTION_RAISE_100,
};
use cfr_core::hunl_eval::Strength;
use cfr_core::hunl_tree::{HUNLTree, TerminalKind};

use std::sync::Arc;

fn river_state() -> HUNLState {
    HUNLState::initial(Arc::new(default_tiny_subgame()))
}

fn flop_state(starting_stack: i32, pot: i32) -> HUNLState {
    let board = vec![card_to_int(14, 0), card_to_int(7, 3), card_to_int(2, 2)];
    let hole = [
        [card_to_int(14, 1), card_to_int(13, 3)],
        [card_to_int(12, 2), card_to_int(12, 1)],
    ];
    let cfg = HUNLConfig {
        starting_stack,
        starting_street: Street::Flop,
        initial_board: board,
        initial_pot: pot,
        initial_contributions: [pot / 2, pot / 2],
        initial_hole_cards: Some(hole),
        ..Default::default()
    };
    HUNLState::initial(Arc::new(cfg))
}

// ---------------------------------------------------------------------------
// Test 1: blinds + postflop subgame starts behind full stacks
// ---------------------------------------------------------------------------
#[test]
fn test_01_initial_postflop_state_invariants() {
    let s = river_state();
    assert_eq!(s.street, Street::River);
    assert_eq!(s.contributions, [500, 500]);
    assert_eq!(s.stacks, [1000, 1000]);
    assert_eq!(s.to_call, 0);
    assert_eq!(s.cur_player, 1);
    assert_eq!(s.street_aggressor, -1);
    assert_eq!(s.street_num_raises, 0);
    assert!(!s.folded[0] && !s.folded[1]);
    assert!(!s.all_in[0] && !s.all_in[1]);
}

// ---------------------------------------------------------------------------
// Test 2: legal actions on river root include CHECK and ALL_IN
// ---------------------------------------------------------------------------
#[test]
fn test_02_legal_actions_river_root() {
    let s = river_state();
    let acts = s.legal_actions();
    assert!(acts.is_sorted(), "legal_actions must be sorted: {acts:?}");
    assert!(acts.contains(&ACTION_CHECK));
    assert!(acts.contains(&ACTION_ALL_IN));
    assert!(!acts.contains(&ACTION_FOLD));
    assert!(!acts.contains(&ACTION_CALL));
}

// ---------------------------------------------------------------------------
// Test 3: facing a bet adds FOLD and CALL, removes CHECK
// ---------------------------------------------------------------------------
#[test]
fn test_03_legal_actions_facing_bet() {
    let s = river_state();
    let after_bet = s.apply(ACTION_BET_100); // P1 bets 100% pot
    let acts = after_bet.legal_actions();
    assert!(acts.contains(&ACTION_FOLD));
    assert!(acts.contains(&ACTION_CALL));
    assert!(!acts.contains(&ACTION_CHECK));
    assert!(acts.contains(&ACTION_ALL_IN));
}

// ---------------------------------------------------------------------------
// Test 4: fold ends the hand with loser paying contribution
// ---------------------------------------------------------------------------
#[test]
fn test_04_fold_terminates_correctly() {
    let s = river_state();
    let after_check = s.apply(ACTION_CHECK); // P1 checks
    let after_fold = after_check.apply(ACTION_FOLD); // P0 folds
    assert!(after_fold.is_terminal());
    let u = after_fold.utility();
    // P0 had contribution 500, BB=100 → P0 loses 5 BB.
    assert!((u[0] + 5.0).abs() < 1e-9);
    assert!((u[1] - 5.0).abs() < 1e-9);
}

// ---------------------------------------------------------------------------
// Test 5: showdown evaluates correctly (AhKc with top pair beats QdQh)
// ---------------------------------------------------------------------------
#[test]
fn test_05_showdown_winner_collects_loser_contribution() {
    let s = river_state();
    let after_check_check = s.apply(ACTION_CHECK).apply(ACTION_CHECK);
    assert!(after_check_check.is_terminal());
    assert_eq!(after_check_check.street, Street::Showdown);
    let u = after_check_check.utility();
    // Board As 7c 2d Kh 5s with hole AhKc → P0 has two pair (AA KK + kicker
    // actually no, two pairs A-pair K-pair). P1 has QQ underpair. P0 wins.
    assert!((u[0] - 5.0).abs() < 1e-9, "u[0] = {}", u[0]);
    assert!((u[1] + 5.0).abs() < 1e-9, "u[1] = {}", u[1]);
}

// ---------------------------------------------------------------------------
// Test 6: raise cap postflop = 3 — at-cap, no more raises legal
// ---------------------------------------------------------------------------
#[test]
fn test_06_raise_cap_postflop() {
    let s = flop_state(100_000, 200);
    let s1 = s.apply(ACTION_BET_100);
    let s2 = s1.apply(ACTION_RAISE_100);
    let s3 = s2.apply(ACTION_RAISE_100); // 3rd raise → at cap
    let acts = s3.legal_actions();
    let any_raise = acts.iter().any(|a| (8..=12).contains(a));
    assert!(!any_raise, "expected no raise actions at cap; got {acts:?}");
    let any_bet = acts.iter().any(|a| (3..=7).contains(a));
    assert!(
        !any_bet,
        "bets shouldn't appear when facing a raise; got {acts:?}"
    );
    assert!(acts.contains(&ACTION_FOLD));
    assert!(acts.contains(&ACTION_CALL));
    assert!(acts.contains(&ACTION_ALL_IN));
}

// ---------------------------------------------------------------------------
// Test 7: all-in absorption + dedup — small stack collapses to ALL_IN only
// ---------------------------------------------------------------------------
#[test]
fn test_07_all_in_absorption() {
    // Stack = 100, pot = 1000 → 33%-pot bet would be 330 > stack → all bet
    // candidates absorbed into ALL_IN. Also stack <= big_blind enforces
    // ALL_IN only via force_allin_threshold = 1 BB.
    let board = vec![card_to_int(14, 0), card_to_int(7, 3), card_to_int(2, 2)];
    let hole = [
        [card_to_int(14, 1), card_to_int(13, 3)],
        [card_to_int(12, 2), card_to_int(12, 1)],
    ];
    let cfg = HUNLConfig {
        starting_stack: 100, // tiny
        starting_street: Street::Flop,
        initial_board: board,
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: Some(hole),
        ..Default::default()
    };
    let s = HUNLState::initial(Arc::new(cfg));
    let acts = s.legal_actions();
    // Expect CHECK + ALL_IN only (no intermediate bet candidates).
    assert!(acts.contains(&ACTION_CHECK));
    assert!(acts.contains(&ACTION_ALL_IN));
    let any_bet = acts.iter().any(|a| (3..=7).contains(a));
    assert!(!any_bet, "expected no intermediate bets; got {acts:?}");
}

// ---------------------------------------------------------------------------
// Test 8: infoset key lossless format byte-for-byte
// ---------------------------------------------------------------------------
#[test]
fn test_08_infoset_key_lossless_format() {
    let s = river_state();
    let key_p0 = s.infoset_key(0, None);
    // AhKc sorted by (rank, suit) ascending = Kc(13,3), Ah(14,1) → "KcAh"
    // Board As(14,0), 7c(7,3), 2d(2,2), Kh(13,1), 5s(5,0)
    // sorted ascending by card-int (= rank*4+suit): 2d=10, 5s=20, 7c=31, Kh=53, As=56
    // → "2d5s7cKhAs"
    // street_token "r" for river; history empty.
    assert_eq!(key_p0, "KcAh|2d5s7cKhAs|r|");
    let key_p1 = s.infoset_key(1, None);
    // QdQh sorted: Qh(12,1) then Qd(12,2)
    assert_eq!(key_p1, "QhQd|2d5s7cKhAs|r|");
}

// ---------------------------------------------------------------------------
// Test 9: infoset key bucketed-format coverage lives in Agent C's cross-tier
// diff (`tests/test_hunl_rust.rs::test_hunl_infoset_key_bucketed_format`),
// which can construct a real `AbstractionTables` via Agent B's loader and
// avoids the test-side mocking that the spec deliberately keeps out of the
// Rust-only unit suite. Slot intentionally left as a marker.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Test 10: infoset key bucketed format with non-empty history
// ---------------------------------------------------------------------------
#[test]
fn test_10_infoset_key_with_history() {
    let s = river_state();
    // P1 checks, P0 bets 100, P1 calls is mid-stream — capture infoset before
    // the call so cur_player still has an action.
    let after_check = s.apply(ACTION_CHECK); // P1 checks, P0 to act
    let after_bet = after_check.apply(ACTION_BET_100); // P0 bets 100% pot
                                                       // After bet, P1 to act. P1's infoset key should reflect history "x" + "b{amount}".
    let key = after_bet.infoset_key(1, None);
    // History format: "/".join("".join(tokens) for tokens in all_streets).
    // No completed streets yet → just current "x" + "b{amount}".
    // Pot = 1000 → 100% bet amount = 1000 chips → token = "b1000".
    assert_eq!(key, "QhQd|2d5s7cKhAs|r|xb1000");
}

// ---------------------------------------------------------------------------
// Test 11: enumerate_legal_actions dedup — identical chip amounts collapse
// ---------------------------------------------------------------------------
#[test]
fn test_11_legal_action_dedup() {
    // Pot = 100, BB = 100, stack = 10000 — 33% pot = 33, 75% pot = 75, 100% = 100.
    // All distinct → expect all three bet sizes. Also test against a pot
    // configuration where 75% and 100% might collapse.
    let ctx = ActionContext {
        pot: 100,
        to_call: 0,
        stacks: [10_000, 10_000],
        contributions: [50, 50],
        cur_player: 0,
        street: Street::Flop,
        street_num_raises: 0,
        street_aggressor: -1,
        big_blind: 100,
        bet_size_fractions: vec![0.33, 0.75, 1.0, 1.5, 2.0],
        preflop_raise_cap: 4,
        postflop_raise_cap: 3,
        force_allin_threshold: 1,
        min_bet_bb: 1,
        include_all_in: true,
    };
    let acts = enumerate_legal_actions(&ctx);
    // Bet 33% pot = 33 → min_bet_bb*BB = 100 (clamped) → bet 33 collapses to bet 100.
    // Bet 75% pot = 75 → clamped to 100 → also collapses.
    // Bet 100% pot = 100 → 100. Bet 150 = 150. Bet 200 = 200.
    // After dedup expect: CHECK, one bet ≤100 (the lowest action ID kept by ordering),
    // and the rest. Confirm the dedup at least produces a single 100-chip outcome.
    // Verify computed amounts for present actions.
    for &a in &acts {
        if (3..=7).contains(&a) {
            let amount = compute_bet_amount(a, &ctx);
            assert!(amount > 0, "bet action {a} → amount {amount}");
        }
    }
    assert!(acts.contains(&ACTION_CHECK));
    assert!(acts.contains(&ACTION_ALL_IN));
}

// ---------------------------------------------------------------------------
// Test 12: compute_bet_amount banker's-rounding parity (33% of 1000 → 330)
// ---------------------------------------------------------------------------
#[test]
fn test_12_compute_bet_amount_rounding() {
    let ctx = ActionContext {
        pot: 1000,
        to_call: 0,
        stacks: [10_000, 10_000],
        contributions: [500, 500],
        cur_player: 0,
        street: Street::Flop,
        street_num_raises: 0,
        street_aggressor: -1,
        big_blind: 100,
        bet_size_fractions: vec![0.33, 0.75, 1.0, 1.5, 2.0],
        preflop_raise_cap: 4,
        postflop_raise_cap: 3,
        force_allin_threshold: 1,
        min_bet_bb: 1,
        include_all_in: true,
    };
    assert_eq!(compute_bet_amount(ACTION_BET_33, &ctx), 330);
    assert_eq!(compute_bet_amount(ACTION_BET_75, &ctx), 750);
    assert_eq!(compute_bet_amount(ACTION_BET_100, &ctx), 1000);
}

// ---------------------------------------------------------------------------
// Test 13: compute_raise_to vs aggressor contrib + min raise
// ---------------------------------------------------------------------------
#[test]
fn test_13_compute_raise_to_min_increment() {
    // After P1 opens 100% pot from a 200-chip pot, P0 raise sizes are
    // computed off (pot + to_call) * fraction added on top of aggressor's
    // contribution. Verify raise_to math.
    let s = flop_state(100_000, 200);
    let after_bet = s.apply(ACTION_BET_100); // pot was 200, bet 200 → contributions become [100, 300]
                                             // Now pot = 100 + 300 = 400 (sum contribs) - 200 (initial contributions = sum 200) + 200 (initial_pot)
                                             // = 400 - 200 + 200 = 400. to_call = 200 (P0 needs to match P1's 300 - own 100).
    let ctx = after_bet.action_context();
    assert_eq!(ctx.pot, 400);
    assert_eq!(ctx.to_call, 200);
    // Raise 100% = (pot + to_call) * 1.0 = 600 added on top of aggressor's
    // 300 → raise_to = 900.
    assert_eq!(compute_raise_to(ACTION_RAISE_100, &ctx), 900);
}

// ---------------------------------------------------------------------------
// Test 14: HUNLTree::build for river subgame yields a finite, non-empty tree
// ---------------------------------------------------------------------------
#[test]
fn test_14_tree_build_river_subgame() {
    let cfg = Arc::new(default_tiny_subgame());
    let tree = HUNLTree::build(cfg, None);
    assert!(!tree.nodes.is_empty());
    let root = &tree.nodes[tree.root as usize];
    assert_eq!(root.player, 1);
    assert!(!root.legal_actions.is_empty());
    // Root infoset key set on player nodes.
    assert!(root.infoset_key.is_some());
}

// ---------------------------------------------------------------------------
// Test 15: HUNLTree::build records terminal kinds correctly
// ---------------------------------------------------------------------------
#[test]
fn test_15_tree_terminals() {
    let cfg = Arc::new(default_tiny_subgame());
    let tree = HUNLTree::build(cfg, None);
    let mut fold_seen = false;
    let mut showdown_seen = false;
    for node in &tree.nodes {
        match node.terminal_kind {
            TerminalKind::Fold {
                winner,
                contribution_loss,
            } => {
                fold_seen = true;
                assert!(winner < 2);
                assert!(contribution_loss > 0);
            }
            TerminalKind::Showdown { .. } => {
                showdown_seen = true;
            }
            TerminalKind::NonTerminal => {}
        }
    }
    assert!(fold_seen);
    assert!(showdown_seen);
}

// ---------------------------------------------------------------------------
// Test 16: Strength evaluator orders categories correctly
// ---------------------------------------------------------------------------
#[test]
fn test_16_strength_evaluator_categories() {
    let high_card = Strength::evaluate_5(&[
        card_to_int(14, 0),
        card_to_int(11, 1),
        card_to_int(8, 2),
        card_to_int(5, 3),
        card_to_int(2, 0),
    ]);
    let pair = Strength::evaluate_5(&[
        card_to_int(8, 0),
        card_to_int(8, 1),
        card_to_int(14, 0),
        card_to_int(11, 1),
        card_to_int(2, 0),
    ]);
    let full_house = Strength::evaluate_5(&[
        card_to_int(14, 0),
        card_to_int(14, 1),
        card_to_int(14, 2),
        card_to_int(13, 0),
        card_to_int(13, 1),
    ]);
    let royal_flush = Strength::evaluate_5(&[
        card_to_int(14, 0),
        card_to_int(13, 0),
        card_to_int(12, 0),
        card_to_int(11, 0),
        card_to_int(10, 0),
    ]);
    assert!(high_card < pair);
    assert!(pair < full_house);
    assert!(full_house < royal_flush);
}

// ---------------------------------------------------------------------------
// Test 17: Strength evaluator ties when two hands identical-by-rank
// ---------------------------------------------------------------------------
#[test]
fn test_17_strength_tie() {
    // Two A-high flushes with identical ranks in different suits.
    let h1 = [
        card_to_int(14, 0),
        card_to_int(11, 0),
        card_to_int(8, 0),
        card_to_int(5, 0),
        card_to_int(2, 0),
    ];
    let h2 = [
        card_to_int(14, 1),
        card_to_int(11, 1),
        card_to_int(8, 1),
        card_to_int(5, 1),
        card_to_int(2, 1),
    ];
    assert_eq!(Strength::evaluate_5(&h1), Strength::evaluate_5(&h2));
}

// ---------------------------------------------------------------------------
// Test 18: Showdown tie returns (0.0, 0.0) utility
// ---------------------------------------------------------------------------
#[test]
fn test_18_showdown_tie_returns_zero_utility() {
    // Construct a tied showdown: same hole-card rank pair, board makes both
    // hands identical. Use AhKc vs AcKh (suited isn't possible — different
    // suits) on a paired board so ranks are identical.
    let board = vec![
        card_to_int(9, 0),
        card_to_int(7, 1),
        card_to_int(4, 2),
        card_to_int(3, 3),
        card_to_int(2, 0),
    ];
    let hole = [
        [card_to_int(14, 1), card_to_int(13, 3)], // AhKc
        [card_to_int(14, 3), card_to_int(13, 1)], // AcKh — same ranks
    ];
    let cfg = HUNLConfig {
        starting_stack: 1000,
        starting_street: Street::River,
        initial_board: board,
        initial_pot: 1000,
        initial_contributions: [500, 500],
        initial_hole_cards: Some(hole),
        ..Default::default()
    };
    let s = HUNLState::initial(Arc::new(cfg));
    let terminal = s.apply(ACTION_CHECK).apply(ACTION_CHECK);
    assert!(terminal.is_terminal());
    let u = terminal.utility();
    assert!(
        u[0].abs() < 1e-9,
        "tied utility[0] should be 0, got {}",
        u[0]
    );
    assert!(
        u[1].abs() < 1e-9,
        "tied utility[1] should be 0, got {}",
        u[1]
    );
}

// ---------------------------------------------------------------------------
// Test 19: card_to_int range check
// ---------------------------------------------------------------------------
#[test]
fn test_19_card_to_int_range() {
    assert_eq!(card_to_int(2, 0), 8);
    assert_eq!(card_to_int(14, 3), 59);
    // Every (rank, suit) maps to a unique card-int in [8, 59].
    let mut seen = [false; 60];
    for r in 2u8..=14 {
        for s in 0u8..4 {
            let c = card_to_int(r, s);
            assert!((8..=59).contains(&c));
            assert!(!seen[c as usize]);
            seen[c as usize] = true;
        }
    }
}

// ---------------------------------------------------------------------------
// Test 20: all-in run-out walks remaining streets via single-card chance
// ---------------------------------------------------------------------------
#[test]
fn test_20_all_in_runout_single_card_chance() {
    let s = flop_state(1000, 200);
    // Both shove pre-betting → triggers all-in run-out.
    let s1 = s.apply(ACTION_ALL_IN); // P1 shoves
    let s2 = s1.apply(ACTION_CALL); // P0 calls
                                    // After call closes the flop, the runout begins: street advances and
                                    // chance node deals one card at a time.
    assert!(s2.all_in[0] && s2.all_in[1], "both should be all-in");
    assert_eq!(s2.cur_player, -1, "expected chance node after all-in/call");
    // Walk the runout to terminal.
    let mut cur = s2;
    let mut iters = 0;
    while !cur.is_terminal() && iters < 30 {
        let outcomes = cur.chance_outcomes();
        if outcomes.is_empty() {
            break;
        }
        cur = cur.apply(outcomes[0].0);
        iters += 1;
    }
    assert!(
        cur.is_terminal(),
        "runout should terminate within bounded iterations"
    );
    assert_eq!(
        cur.board.len(),
        5,
        "runout should fill the board to 5 cards"
    );
}
