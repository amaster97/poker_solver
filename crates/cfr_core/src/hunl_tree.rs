//! HUNL flat-array game tree.
//!
//! Adapted from `poker_solver/hunl.py` (project-internal, MIT) for the
//! state-machine traversal semantics. Tree-node shape adapted by pattern
//! from `references/code/noambrown_poker_solver/cpp/src/river_game.{h,cpp}`
//! (MIT) — independent re-derivation, no code transcription. The flat-tree
//! pattern (indexed `Vec<TreeNode>` with `children: [u32; N]`) is also used
//! in `postflop-solver` (AGPL), but we re-derive it independently from the
//! Python tier + the MIT noambrown reference — no copying.
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
//!
//! Build strategy (per PR 6 spec §4.2): recursive traversal via
//! `HUNLState::apply` / `chance_outcomes`. Memoize duplicate states by the
//! *infoset-equivalence key* `(cur_player, contribs, street, history)` so
//! states reached via different chance orderings collapse to one node.
//!
//! The infoset key for each player node is computed *during* the build using
//! the optional `BucketLookup` impl supplied by the caller. Default (lossless)
//! mode uses the unbucketed key format. The build runs after abstraction load
//! per locked decision D11.

use crate::abstraction::AbstractionTables;
use crate::hunl::{HUNLConfig, HUNLState, Street};
use std::collections::HashMap;
use std::sync::Arc;

/// Terminal-leaf classification.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TerminalKind {
    NonTerminal,
    /// A fold ended the hand. `winner` is the player who collects the pot;
    /// `contribution_loss` is the loser's contribution (chip cost, used to
    /// reconstruct the utility without re-walking the state).
    Fold {
        winner: u8,
        contribution_loss: i32,
    },
    /// Showdown leaf — the actual winner depends on the dealt cards, so the
    /// solver evaluates `Strength` at solve time. `board_complete` indicates
    /// whether the board has all 5 cards (vs an all-in run-out leaf that
    /// preceded full board reveal, which shouldn't happen in PR 6 because
    /// run-outs deal one card at a time).
    Showdown {
        board_complete: bool,
    },
}

/// One node in the flat tree. The `children` array indexes into
/// `HUNLTree::nodes`. Player-action children are dense; chance-action
/// children are stored under `chance_outcomes` (action u8 → child index +
/// probability).
#[derive(Clone, Debug)]
pub struct HUNLTreeNode {
    /// -1 chance, 0/1 player, -2 terminal.
    pub player: i8,
    pub terminal_kind: TerminalKind,
    pub contrib: [i32; 2],
    pub street: Street,
    pub num_actions: u8,
    /// Legal actions for a player node (sorted, max 14). Empty for chance
    /// and terminal nodes.
    pub legal_actions: Vec<u8>,
    /// Child indices indexed by position in `legal_actions`. Length matches
    /// `legal_actions.len()` for player nodes; empty for chance and terminal.
    pub children: Vec<u32>,
    /// Infoset key for player nodes; `None` for chance and terminal nodes.
    pub infoset_key: Option<String>,
    /// The card dealt to enter this node (chance edge). `None` at the root
    /// or for non-chance-entry nodes.
    pub chance_action: Option<u8>,
    /// Probability of entering this node from its parent (for chance nodes
    /// only; 1.0 otherwise). Mirrors a per-edge sample weight stored on the
    /// child side for cache locality during traversal.
    pub chance_prob: f64,
    /// For chance nodes: (card, prob) per uniform outcome over the remaining
    /// deck. Up to 52 entries (a fresh deck minus blockers).
    pub chance_outcomes: Vec<(u8, f64)>,
    /// For chance nodes: child index aligned 1:1 with `chance_outcomes`.
    pub chance_children: Vec<u32>,
}

impl HUNLTreeNode {
    fn empty(player: i8, contrib: [i32; 2], street: Street) -> Self {
        Self {
            player,
            terminal_kind: TerminalKind::NonTerminal,
            contrib,
            street,
            num_actions: 0,
            legal_actions: Vec::new(),
            children: Vec::new(),
            infoset_key: None,
            chance_action: None,
            chance_prob: 1.0,
            chance_outcomes: Vec::new(),
            chance_children: Vec::new(),
        }
    }
}

/// Flat HUNL game tree.
#[derive(Clone, Debug)]
pub struct HUNLTree {
    pub nodes: Vec<HUNLTreeNode>,
    pub root: u32,
    pub max_depth: u32,
    pub max_actions: u8,
    pub config: Arc<HUNLConfig>,
}

/// Memoization key. Player-action histories AND in-progress street tokens
/// (encoded via the state's actual `street_history` and the betting-token
/// representation) together identify the infoset-equivalence class.
///
/// We use `street_history` for the current-street action sequence and the
/// flattened betting-tokens history string for prior-street actions —
/// `street_history` alone resets between streets, so the prior-streets
/// portion is captured via the tokens.
#[derive(Hash, Eq, PartialEq, Debug, Clone)]
struct MemoKey {
    cur_player: i8,
    contributions: [i32; 2],
    stacks: [i32; 2],
    street: Street,
    street_history: Vec<u8>,
    /// Joined per-street tokens for completed streets (matches the prefix of
    /// the `infoset_key` history portion). Two states that differ only in
    /// chance ordering of board cards can share this key only if their
    /// board sequences are identical; we include the board cards via the
    /// chance_action breadcrumbs implicitly through the parent node, so the
    /// memo key intentionally OMITS the board itself (different boards live
    /// in different subtrees by construction).
    completed_streets: Vec<Vec<u8>>,
    /// In-progress tokens for the current street. Same field shape as Python.
    current_street_tokens: Vec<String>,
    /// Per-player fold/all-in flags so a fold subtree never collides with
    /// the live betting subtree.
    folded: [bool; 2],
    all_in: [bool; 2],
    /// Board contents. Including the board distinguishes chance-permutation
    /// equivalents that land on different cards: while infoset equivalence
    /// is per-player, the tree must walk every actual board explicitly.
    board: Vec<u8>,
    /// Hole cards; included so that a tree built for a specific (P0, P1)
    /// hole pair doesn't memoize across different hole assignments. In
    /// practice PR 6's HUNL postflop subgame fixes hole cards at the root.
    hole_cards: Option<[[u8; 2]; 2]>,
    pending_board_deals: u8,
    to_call: i32,
    street_num_raises: u8,
    street_aggressor: i8,
}

impl MemoKey {
    fn from_state(state: &HUNLState) -> Self {
        Self {
            cur_player: state.cur_player,
            contributions: state.contributions,
            stacks: state.stacks,
            street: state.street,
            street_history: state.street_history.clone(),
            completed_streets: state
                .betting_tokens
                .iter()
                .map(|s| s.concat().into_bytes())
                .collect(),
            current_street_tokens: state.current_street_tokens.clone(),
            folded: state.folded,
            all_in: state.all_in,
            board: state.board.clone(),
            hole_cards: state.hole_cards,
            pending_board_deals: state.pending_board_deals,
            to_call: state.to_call,
            street_num_raises: state.street_num_raises,
            street_aggressor: state.street_aggressor,
        }
    }
}

impl HUNLTree {
    /// Build the flat tree starting from `HUNLState::initial(config)`.
    ///
    /// The optional `abstraction` populates per-player infoset_key with
    /// bucketed keys; `None` produces lossless keys. Agent B passes the
    /// loaded abstraction through this builder.
    ///
    /// Build runs after abstraction load per locked decision D11.
    pub fn build(config: Arc<HUNLConfig>, abstraction: Option<&AbstractionTables>) -> Self {
        let mut tree = HUNLTree {
            nodes: Vec::new(),
            root: 0,
            max_depth: 0,
            max_actions: 0,
            config: config.clone(),
        };
        let mut memo: HashMap<MemoKey, u32> = HashMap::new();
        let initial = HUNLState::initial(config);
        let root = tree.build_node(&initial, abstraction, &mut memo, 0);
        tree.root = root;
        tree
    }

    /// Recursively register `state` (and its descendants) as tree nodes.
    /// Returns the node index. Updates `max_depth` and `max_actions`.
    fn build_node(
        &mut self,
        state: &HUNLState,
        abstraction: Option<&AbstractionTables>,
        memo: &mut HashMap<MemoKey, u32>,
        depth: u32,
    ) -> u32 {
        let key = MemoKey::from_state(state);
        if let Some(&idx) = memo.get(&key) {
            return idx;
        }

        // Reserve the slot up-front so children that recurse back to us
        // (cycles aren't possible in HUNL trees, but the bookkeeping keeps
        // construction order stable) see a stable index.
        let my_idx = self.nodes.len() as u32;
        self.nodes.push(HUNLTreeNode::empty(
            state.cur_player,
            state.contributions,
            state.street,
        ));
        memo.insert(key, my_idx);
        if depth > self.max_depth {
            self.max_depth = depth;
        }

        if state.is_terminal() {
            // Terminal classification.
            let kind = if state.folded[0] {
                TerminalKind::Fold {
                    winner: 1,
                    contribution_loss: state.contributions[0],
                }
            } else if state.folded[1] {
                TerminalKind::Fold {
                    winner: 0,
                    contribution_loss: state.contributions[1],
                }
            } else {
                TerminalKind::Showdown {
                    board_complete: state.board.len() >= 5,
                }
            };
            let node = &mut self.nodes[my_idx as usize];
            node.player = -2;
            node.terminal_kind = kind;
            return my_idx;
        }

        if state.cur_player == -1 {
            // Chance node.
            let outcomes = state.chance_outcomes();
            let mut chance_children: Vec<u32> = Vec::with_capacity(outcomes.len());
            for (action, _prob) in &outcomes {
                let next_state = state.apply(*action);
                let child_idx = self.build_node(&next_state, abstraction, memo, depth + 1);
                // Annotate the child with its chance breadcrumbs (parent edge).
                let child = &mut self.nodes[child_idx as usize];
                if child.chance_action.is_none() {
                    child.chance_action = Some(*action);
                }
                chance_children.push(child_idx);
            }
            // Update self (now safe — children's recursion is done).
            let node = &mut self.nodes[my_idx as usize];
            node.chance_outcomes = outcomes;
            node.chance_children = chance_children;
            return my_idx;
        }

        // Player node.
        let actions = state.legal_actions();
        if actions.len() > self.max_actions as usize {
            self.max_actions = actions.len() as u8;
        }
        let infoset_key = state.infoset_key(state.cur_player as u8, abstraction);
        let mut child_indices: Vec<u32> = Vec::with_capacity(actions.len());
        for &action in &actions {
            let next_state = state.apply(action);
            let child_idx = self.build_node(&next_state, abstraction, memo, depth + 1);
            child_indices.push(child_idx);
        }
        let node = &mut self.nodes[my_idx as usize];
        node.num_actions = actions.len() as u8;
        node.legal_actions = actions;
        node.children = child_indices;
        node.infoset_key = Some(infoset_key);
        my_idx
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hunl::default_tiny_subgame;

    #[test]
    fn river_subgame_tree_builds_and_has_leaves() {
        let cfg = Arc::new(default_tiny_subgame());
        let tree = HUNLTree::build(cfg, None);
        // Root must be a player node (P1 to act on river, no chance gating).
        let root = &tree.nodes[tree.root as usize];
        assert_eq!(root.player, 1);
        assert!(!root.legal_actions.is_empty());
        // Find at least one fold-terminal and one showdown-terminal.
        let mut fold_seen = false;
        let mut showdown_seen = false;
        for node in &tree.nodes {
            match node.terminal_kind {
                TerminalKind::Fold { .. } => fold_seen = true,
                TerminalKind::Showdown { .. } => showdown_seen = true,
                TerminalKind::NonTerminal => {}
            }
        }
        assert!(fold_seen, "tree must contain at least one fold terminal");
        assert!(
            showdown_seen,
            "tree must contain at least one showdown terminal"
        );
        // Max actions must include the root's legal-action count.
        assert!(tree.max_actions >= root.num_actions);
    }

    #[test]
    fn tree_node_count_is_finite_and_bounded() {
        let cfg = Arc::new(default_tiny_subgame());
        let tree = HUNLTree::build(cfg, None);
        // River subgame with no chance branching → bounded by the action tree
        // depth (raise cap 3 × 14 actions). Empirically 10²–10³ nodes; assert
        // a loose upper bound to catch infinite loops.
        assert!(
            tree.nodes.len() < 100_000,
            "river subgame tree should be small, got {} nodes",
            tree.nodes.len()
        );
        assert!(tree.nodes.len() > 5, "tree should have multiple nodes");
    }
}
