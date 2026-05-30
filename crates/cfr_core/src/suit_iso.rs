//! Exact suit/board isomorphism class grouping for chance nodes (Stage 1
//! foundation).
//!
//! A chance node deals one board card. Many of the dealt cards are *exactly*
//! isomorphic given the prefix board already on the table: relabeling suits by
//! a permutation that fixes the prefix board maps one undealt card to another
//! and induces a bijection on every player's hand vector. Solving only one
//! representative per isomorphism class and permuting its value vector to the
//! members is the Stage 2 win; this module builds and unit-tests the grouping
//! machinery only. NOTHING here is wired into the solve / chance-walk hot path,
//! so flag-off behavior is byte-identical.
//!
//! ## Card encoding (verified against `hunl::card_to_int` + `abstraction`)
//! A card is a `u8` with `card = rank * 4 + suit`, `rank in 2..=14`,
//! `suit in 0..=3` (`SUITS = "shdc"`). Hence `rank_of(c) = c >> 2` (== `c / 4`)
//! and `suit_of(c) = c & 3` (== `c % 4`). A suit permutation `perm: [u8; 4]`
//! relabels suit `s` to `perm[s]`; applying it to a card keeps the rank and
//! relabels the suit:
//! ```text
//! apply_perm_to_card(perm, c) = rank_of(c) * 4 + perm[suit_of(c)]
//! ```
//!
//! ## Algorithm (stabilizer + orbits — NOT naive canonical-board equality)
//! 1. `prefix_board` is the cards already dealt above the chance node.
//! 2. The **stabilizer** `S` is the subgroup of the 24 suit permutations that
//!    map the prefix board's card multiset to itself.
//! 3. The dealt cards are partitioned into **orbits** under `S`: `d_i ~ d_j`
//!    iff some `perm in S` has `apply_perm_to_card(perm, d_i) == d_j`.
//! 4. Each orbit is one isomorphism class. The representative is the member
//!    with the smallest child index; every member records a `rel_perm in S`
//!    mapping the representative's dealt card to that member's dealt card
//!    (identity for the representative).
//!
//! Naive `canonicalize_board(prefix ++ d)` equality can *mis-merge*: two dealt
//! cards can land on the same canonical board yet not be reachable from each
//! other by a single prefix-fixing permutation (the canonicalizer is free to
//! also relabel the *new* card's suit). The stabilizer/orbit construction is
//! the exact one.

use std::collections::HashMap;

use crate::abstraction::{rank_of, suit_of, SUIT_PERMUTATIONS};

/// One exact isomorphism class of a chance node's children, relative to the
/// prefix board.
///
/// `representative_child_idx` is the smallest child index in the class.
/// `members` lists every child in the class (including the representative)
/// paired with a `rel_perm` — a prefix-stabilizing suit permutation that maps
/// the representative's dealt card to that member's dealt card. The
/// representative's own `rel_perm` is the identity `[0, 1, 2, 3]`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct IsoClass {
    pub(crate) representative_child_idx: usize,
    pub(crate) members: Vec<(usize, [u8; 4])>,
}

/// Apply a suit permutation to a single card: keep the rank, relabel the suit.
#[inline]
pub(crate) fn apply_perm_to_card(perm: &[u8; 4], card: u8) -> u8 {
    rank_of(card) * 4 + perm[suit_of(card) as usize]
}

/// True iff `perm` maps the prefix board's card multiset onto itself.
///
/// A permutation only relabels suits, so it fixes the board iff applying it to
/// every board card yields a permutation of the same multiset. We compare
/// sorted card vectors (multiset equality).
fn fixes_board(perm: &[u8; 4], prefix_board: &[u8]) -> bool {
    let mut relabeled: Vec<u8> = prefix_board
        .iter()
        .map(|&c| apply_perm_to_card(perm, c))
        .collect();
    relabeled.sort_unstable();
    let mut original: Vec<u8> = prefix_board.to_vec();
    original.sort_unstable();
    relabeled == original
}

/// Compute the stabilizer subgroup of `prefix_board`: the indices into
/// `SUIT_PERMUTATIONS` of every permutation that fixes the board multiset.
///
/// Always contains the identity (index 0), so the result is non-empty even for
/// an empty prefix board (where *all* 24 permutations fix it).
pub(crate) fn board_stabilizer(prefix_board: &[u8]) -> Vec<usize> {
    SUIT_PERMUTATIONS
        .iter()
        .enumerate()
        .filter(|(_, perm)| fixes_board(perm, prefix_board))
        .map(|(i, _)| i)
        .collect()
}

/// Group a chance node's children into exact isomorphism classes relative to
/// `prefix_board`.
///
/// `dealt_cards[i]` is the board card that child `i` adds versus the prefix.
/// Returns one [`IsoClass`] per orbit of the dealt cards under the prefix
/// stabilizer. The returned classes are ordered by ascending representative
/// child index, and within each class `members` is ordered by ascending child
/// index. Every child index appears in exactly one class (the sum of class
/// sizes equals `dealt_cards.len()`).
///
/// Invariant: for every member `(idx, rel_perm)`,
/// `apply_perm_to_card(rel_perm, dealt_cards[rep]) == dealt_cards[idx]`.
pub(crate) fn group_chance_children(prefix_board: &[u8], dealt_cards: &[u8]) -> Vec<IsoClass> {
    let stabilizer: Vec<[u8; 4]> = board_stabilizer(prefix_board)
        .into_iter()
        .map(|i| SUIT_PERMUTATIONS[i])
        .collect();

    // Map each dealt card to its child index for O(1) orbit-member lookup.
    // Dealt cards within one chance node are distinct (distinct undealt cards),
    // so this map is injective.
    let card_to_child: HashMap<u8, usize> = dealt_cards
        .iter()
        .enumerate()
        .map(|(idx, &c)| (c, idx))
        .collect();

    let mut assigned = vec![false; dealt_cards.len()];
    let mut classes: Vec<IsoClass> = Vec::new();

    for rep_idx in 0..dealt_cards.len() {
        if assigned[rep_idx] {
            continue;
        }
        let rep_card = dealt_cards[rep_idx];
        // Collect the orbit of `rep_card` under the stabilizer. For each
        // stabilizer perm, the image card (if it is one of our dealt cards)
        // is an orbit member; the perm that produced it is a valid rel_perm.
        // We keep the FIRST perm that reaches each member (deterministic).
        let mut members: Vec<(usize, [u8; 4])> = Vec::new();
        for perm in &stabilizer {
            let image = apply_perm_to_card(perm, rep_card);
            if let Some(&member_idx) = card_to_child.get(&image) {
                if !assigned[member_idx] {
                    assigned[member_idx] = true;
                    members.push((member_idx, *perm));
                }
            }
        }
        members.sort_by_key(|&(idx, _)| idx);
        // The representative reaches itself via the identity permutation; force
        // its rel_perm to the identity so callers can rely on it.
        for m in members.iter_mut() {
            if m.0 == rep_idx {
                m.1 = SUIT_PERMUTATIONS[0];
            }
        }
        classes.push(IsoClass {
            representative_child_idx: rep_idx,
            members,
        });
    }

    classes
}

/// Build a `(sorted hole-pair) -> index` map for a player's hole-card list.
///
/// The key is the two hole cards sorted ascending (`[lo, hi]`), so it is
/// independent of input order. Used by [`hand_index_permutation`] to resolve
/// the image of a permuted hand back to its slot in the same hole list.
pub(crate) fn build_hole_index(holes: &[[u8; 2]]) -> HashMap<[u8; 2], usize> {
    holes
        .iter()
        .enumerate()
        .map(|(idx, &h)| {
            let mut sorted = h;
            sorted.sort_unstable();
            (sorted, idx)
        })
        .collect()
}

/// Produce the hand-index permutation `sigma` induced by relabeling suits with
/// `rel_perm` on a player's hole-card list.
///
/// `sigma[h]` is the index, in the *same* hole list, of the hand obtained by
/// applying `rel_perm` to hand `h`'s two cards (re-sorted consistently). For a
/// stabilizer permutation acting on a closed hole list, this is a true
/// permutation (bijection) of the hand indices.
///
/// `hole_index` must be `build_hole_index(holes)` for the same `holes`.
///
/// # Panics
/// Panics if a permuted hand is not present in `hole_index`. For a `rel_perm`
/// drawn from the board stabilizer acting on a suit-closed hole list this never
/// happens; a panic signals the caller passed a non-stabilizing perm or a hole
/// list that is not closed under `rel_perm`.
pub(crate) fn hand_index_permutation(
    holes: &[[u8; 2]],
    hole_index: &HashMap<[u8; 2], usize>,
    rel_perm: &[u8; 4],
) -> Vec<u32> {
    holes
        .iter()
        .map(|&h| {
            let mut image = [
                apply_perm_to_card(rel_perm, h[0]),
                apply_perm_to_card(rel_perm, h[1]),
            ];
            image.sort_unstable();
            *hole_index
                .get(&image)
                .expect("permuted hand must exist in the same hole list (stabilizer closure)")
                as u32
        })
        .collect()
}

// ============================================================================
// Stage 2b — value-collapse tables wired into the chance walk.
//
// Stage 1 above builds the per-chance-node isomorphism classes. Stage 2b
// turns each class into a concrete *value-collapse* table: for every member
// child we precompute the hand-index permutation (for BOTH players) that maps
// the representative child's per-hand value vector onto the member child's,
// so the solver can traverse only the representative and permute its values to
// the members. The collapse is EXACT only when the opponent's reach vector is
// suit-symmetric under each class's `rel_perm`s — captured by `is_symmetric`.
// ============================================================================

/// A single value-collapse member of a chance-node class: the member's child
/// index plus the per-player hand-index permutation that maps the
/// representative child's value vector onto this member's.
///
/// `sigma[p][h]` is the index, in player `p`'s hole list, of the hand obtained
/// by applying the member's `rel_perm` to hand `h`. The representative member
/// has the identity permutation in both slots.
#[derive(Debug, Clone)]
pub(crate) struct CollapseMember {
    /// Original child index of this member (preserves DFS summation order).
    pub(crate) child_idx: usize,
    /// Per-player hand-index permutation induced by this member's `rel_perm`.
    /// `sigma[p]` is `hand_index_permutation(holes[p], …, rel_perm)`.
    pub(crate) sigma: [Vec<u32>; 2],
}

/// One chance-node class collapsed for the value walk: the representative child
/// to actually traverse, plus every member (including the representative) in
/// ascending child-index order.
#[derive(Debug, Clone)]
pub(crate) struct CollapseClass {
    pub(crate) representative_child_idx: usize,
    pub(crate) members: Vec<CollapseMember>,
}

/// Per-chance-node value-collapse table. `representative_set[child]` is `true`
/// iff `child` is a class representative (the only members actually traversed).
/// `classes` lists every class for this node in representative-index order.
///
/// `symmetric` is the range-symmetry guard result for BOTH players: the
/// collapse for this node is only EXACT when every class `rel_perm` leaves both
/// players' INITIAL reach vectors invariant. When `false` the solver MUST fall
/// back to the legacy per-child loop for this node.
#[derive(Debug, Clone)]
pub(crate) struct ChanceCollapse {
    pub(crate) classes: Vec<CollapseClass>,
    pub(crate) symmetric: bool,
}

/// The whole-tree value-collapse cache, keyed by chance-node `FlatNode` index.
/// `nodes[idx]` is `Some(collapse)` for a multi-child chance node that has a
/// usable (symmetric) collapse table, `None` otherwise (non-chance node,
/// single-child run-out chance, or a node whose range failed the symmetry
/// guard).
#[derive(Debug, Clone, Default)]
pub(crate) struct SuitIsoCache {
    nodes: Vec<Option<ChanceCollapse>>,
}

impl SuitIsoCache {
    /// O(1) lookup of the collapse table for chance node `node_idx`. Returns
    /// `None` when no usable collapse exists (so the caller runs the legacy
    /// loop).
    #[inline]
    pub(crate) fn get(&self, node_idx: usize) -> Option<&ChanceCollapse> {
        self.nodes.get(node_idx).and_then(|o| o.as_ref())
    }

    /// True iff at least one chance node has a usable collapse table (used to
    /// short-circuit the dispatch when nothing collapsed).
    #[inline]
    pub(crate) fn is_active(&self) -> bool {
        self.nodes.iter().any(|o| o.is_some())
    }
}

/// Check whether a reach vector is invariant under a hand-index permutation:
/// `reach[h] == reach[sigma[h]]` for all `h`. The value collapse is exact only
/// when this holds for the OPPONENT's reach under every class `rel_perm`.
fn reach_is_symmetric(reach: &[f64], sigma: &[u32]) -> bool {
    debug_assert_eq!(reach.len(), sigma.len());
    reach
        .iter()
        .enumerate()
        .all(|(h, &r)| r == reach[sigma[h] as usize])
}

/// Build the whole-tree value-collapse cache.
///
/// For every multi-child `FlatNode::Chance` node we reconstruct its prefix
/// board (the running board on the table when the deal happens — `initial_board`
/// plus the chance cards dealt on the path from the root), group its children
/// into [`IsoClass`]es via [`group_chance_children`], and precompute each
/// member's per-player hand-index permutation. The class is collapsible only if
/// both players' INITIAL reach vectors are invariant under every member
/// `rel_perm` (the [`reach_is_symmetric`] guard); a node with any asymmetric
/// class is recorded as `symmetric = false` and the solver falls back to the
/// legacy loop for it.
///
/// `dealt_cards[child]` is the card a chance child adds versus its parent's
/// prefix (the Stage-1 side table). `holes[p]` is player `p`'s hole list,
/// positionally aligned with the reach vectors. `reach[p]` is player `p`'s
/// INITIAL reach vector.
pub(crate) fn build_suit_iso_cache(
    nodes: &[crate::exploit::FlatNode],
    dealt_cards: &[Option<u8>],
    initial_board: &[u8],
    holes: &[Vec<[u8; 2]>; 2],
    reach: &[&[f64]; 2],
) -> SuitIsoCache {
    use crate::exploit::FlatNode;

    let hole_index = [build_hole_index(&holes[0]), build_hole_index(&holes[1])];

    // Reconstruct the prefix board per node via an explicit DFS that threads
    // the running board. The root's prefix is `initial_board`; each chance
    // child appends its dealt card. We only need prefixes AT chance nodes, but
    // threading the board for every node is O(tree) and simplest.
    let mut prefix_at: Vec<Option<Vec<u8>>> = vec![None; nodes.len()];
    let mut stack: Vec<(usize, Vec<u8>)> = vec![(0, initial_board.to_vec())];
    while let Some((idx, board)) = stack.pop() {
        match &nodes[idx] {
            FlatNode::Chance { children, .. } => {
                prefix_at[idx] = Some(board.clone());
                for &c in children {
                    let mut child_board = board.clone();
                    if let Some(card) = dealt_cards[c] {
                        child_board.push(card);
                    }
                    stack.push((c, child_board));
                }
            }
            FlatNode::Decision { children, .. } => {
                for &c in children {
                    stack.push((c, board.clone()));
                }
            }
            FlatNode::Fold { .. } | FlatNode::Showdown { .. } => {}
        }
    }

    let mut out: Vec<Option<ChanceCollapse>> = vec![None; nodes.len()];
    for idx in 0..nodes.len() {
        let FlatNode::Chance { children, .. } = &nodes[idx] else {
            continue;
        };
        if children.len() < 2 {
            continue;
        }
        let prefix = match &prefix_at[idx] {
            Some(b) => b,
            None => continue,
        };
        // Dealt card per child, in child-index order. Every child of a chance
        // node records its dealt card; bail out (skip collapse) if any is
        // missing rather than mis-grouping.
        let mut child_dealt: Vec<u8> = Vec::with_capacity(children.len());
        let mut complete = true;
        for &c in children {
            match dealt_cards[c] {
                Some(card) => child_dealt.push(card),
                None => {
                    complete = false;
                    break;
                }
            }
        }
        if !complete {
            continue;
        }

        let iso_classes = group_chance_children(prefix, &child_dealt);
        let mut classes: Vec<CollapseClass> = Vec::with_capacity(iso_classes.len());
        let mut symmetric = true;
        for iso in &iso_classes {
            let mut members: Vec<CollapseMember> = Vec::with_capacity(iso.members.len());
            for &(member_local_idx, rel_perm) in &iso.members {
                let sigma0 =
                    hand_index_permutation(&holes[0], &hole_index[0], &rel_perm);
                let sigma1 =
                    hand_index_permutation(&holes[1], &hole_index[1], &rel_perm);
                // Guard: the collapse is exact only if BOTH players' reach is
                // invariant under this rel_perm. (The non-trivial constraint is
                // on the opponent reach used inside the value walk; we require
                // both so the guard holds whichever player is updating.)
                if !reach_is_symmetric(reach[0], &sigma0)
                    || !reach_is_symmetric(reach[1], &sigma1)
                {
                    symmetric = false;
                }
                members.push(CollapseMember {
                    child_idx: children[member_local_idx],
                    sigma: [sigma0, sigma1],
                });
            }
            members.sort_by_key(|m| m.child_idx);
            classes.push(CollapseClass {
                representative_child_idx: children[iso.representative_child_idx],
                members,
            });
        }
        out[idx] = Some(ChanceCollapse { classes, symmetric });
    }

    SuitIsoCache { nodes: out }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::abstraction::canonicalize_board;
    use crate::hunl::card_to_int;

    /// SUITS = "shdc" => s=0, h=1, d=2, c=3.
    const S: u8 = 0;
    const H: u8 = 1;
    const D: u8 = 2;
    const C: u8 = 3;

    fn card(rank: u8, suit: u8) -> u8 {
        card_to_int(rank, suit)
    }

    /// All 52 cards minus the prefix board = the undealt cards (parallel to a
    /// turn/river chance node's children), in deck order (rank-major,
    /// suit-minor) — the same order `chance_outcomes` enumerates.
    fn undealt_cards(prefix_board: &[u8]) -> Vec<u8> {
        let held: std::collections::HashSet<u8> = prefix_board.iter().copied().collect();
        let mut out = Vec::new();
        for r in 2u8..=14 {
            for s in 0u8..4 {
                let c = card(r, s);
                if !held.contains(&c) {
                    out.push(c);
                }
            }
        }
        out
    }

    /// Assert the classes form a partition of `0..n` with no orphan / double
    /// count, and that every member's rel_perm maps the representative's dealt
    /// card to the member's dealt card.
    fn assert_partition_and_relperm(classes: &[IsoClass], dealt: &[u8]) {
        let mut seen = vec![false; dealt.len()];
        let mut total = 0usize;
        for class in classes {
            let rep_card = dealt[class.representative_child_idx];
            for &(idx, rel_perm) in &class.members {
                assert!(!seen[idx], "child {idx} double-counted across classes");
                seen[idx] = true;
                total += 1;
                assert_eq!(
                    apply_perm_to_card(&rel_perm, rep_card),
                    dealt[idx],
                    "rel_perm must map representative card -> member card"
                );
            }
            // representative's rel_perm is the identity
            let rep_entry = class
                .members
                .iter()
                .find(|(idx, _)| *idx == class.representative_child_idx)
                .expect("representative must be a member of its own class");
            assert_eq!(rep_entry.1, [0, 1, 2, 3], "representative rel_perm = identity");
        }
        assert_eq!(total, dealt.len(), "sum of class sizes != number of dealt cards");
        assert!(seen.iter().all(|&b| b), "some dealt card was orphaned");
    }

    /// Helper: which class index holds a given dealt card.
    fn class_of_card(classes: &[IsoClass], dealt: &[u8], target: u8) -> usize {
        let child = dealt.iter().position(|&c| c == target).unwrap();
        classes
            .iter()
            .position(|cl| cl.members.iter().any(|(idx, _)| *idx == child))
            .unwrap()
    }

    fn same_class(classes: &[IsoClass], dealt: &[u8], a: u8, b: u8) -> bool {
        class_of_card(classes, dealt, a) == class_of_card(classes, dealt, b)
    }

    // ---- TEST 1: stabilizer + orbit correctness on the four textures ----

    #[test]
    fn rainbow_texture_orbits() {
        // As Kd 7h — three distinct ranks, three distinct present suits
        // (s, d, h); the absent suit is c. Stabilizer = perms fixing the board
        // multiset. Since the three present cards have distinct ranks AND
        // distinct suits, the only suit relabeling that preserves the multiset
        // is the identity on {s, d, h}; the absent suit c is free but there is
        // no other absent suit to swap it with, so the stabilizer is the
        // identity ONLY. => every undealt card is its own singleton class.
        let prefix = [card(14, S), card(13, D), card(7, H)];
        let stab = board_stabilizer(&prefix);
        assert_eq!(stab, vec![0], "rainbow stabilizer is identity-only");

        let dealt = undealt_cards(&prefix);
        let classes = group_chance_children(&prefix, &dealt);
        assert_partition_and_relperm(&classes, &dealt);
        // Identity stabilizer => one singleton class per undealt card.
        assert_eq!(classes.len(), dealt.len(), "all singletons under rainbow");
        assert_eq!(dealt.len(), 49, "52 - 3 prefix cards");
    }

    #[test]
    fn two_tone_texture_orbits() {
        // As Ks 7h — present suits: s (A, K) and h (7). Absent suits: d, c.
        // The two absent suits d <-> c are interchangeable (no board card uses
        // either), so the stabilizer contains the transposition (d c) and the
        // identity => |S| = 2. Undealt cards in suits s and h are singletons;
        // each (rank, d) pairs with (rank, c).
        let prefix = [card(14, S), card(13, S), card(7, H)];
        let stab = board_stabilizer(&prefix);
        assert_eq!(stab.len(), 2, "two-tone: identity + (d c) swap");

        let dealt = undealt_cards(&prefix);
        let classes = group_chance_children(&prefix, &dealt);
        assert_partition_and_relperm(&classes, &dealt);

        // 2c and 2d in the same class (interchangeable absent suits).
        assert!(
            same_class(&classes, &dealt, card(2, C), card(2, D)),
            "2c and 2d must be isomorphic"
        );
        // 2s and 2h are NOT in the d/c orbit (present suits) -> singletons.
        assert!(!same_class(&classes, &dealt, card(2, S), card(2, D)));
        assert!(!same_class(&classes, &dealt, card(2, H), card(2, D)));

        // Class count: undealt = 49. Suit s has 11 undealt (13 ranks - A,K),
        // suit h has 12 undealt (13 - 7), both singletons => 23 classes.
        // Suits d & c: each has 13 ranks, none on board, pairing up => for
        // each rank one {Xd, Xc} class = 13 classes. Total = 23 + 13 = 36.
        assert_eq!(classes.len(), 36, "two-tone class count");
    }

    #[test]
    fn monotone_texture_orbits() {
        // As Ks 7s — all three board cards are spades. Absent suits h, d, c are
        // fully interchangeable (none on board) => stabilizer = all perms that
        // fix s and permute {h, d, c} arbitrarily => |S| = 3! = 6. Undealt
        // spades are singletons; each offsuit rank forms a size-3 class
        // {Xh, Xd, Xc}.
        let prefix = [card(14, S), card(13, S), card(7, S)];
        let stab = board_stabilizer(&prefix);
        assert_eq!(stab.len(), 6, "monotone: S3 on the three absent suits");

        let dealt = undealt_cards(&prefix);
        let classes = group_chance_children(&prefix, &dealt);
        assert_partition_and_relperm(&classes, &dealt);

        // {2h, 2d, 2c} one class.
        assert!(same_class(&classes, &dealt, card(2, H), card(2, D)));
        assert!(same_class(&classes, &dealt, card(2, D), card(2, C)));
        let cl = class_of_card(&classes, &dealt, card(2, H));
        assert_eq!(classes[cl].members.len(), 3, "{{2h,2d,2c}} size-3 class");

        // Spades are singletons (present suit, not permuted).
        assert!(!same_class(&classes, &dealt, card(2, S), card(2, H)));

        // Undealt = 49. Spades: 13 - 3 on board = 10 singletons. Offsuit:
        // 13 ranks each {Xh, Xd, Xc} = 13 size-3 classes (39 cards). Total
        // classes = 10 + 13 = 23.
        assert_eq!(classes.len(), 23, "monotone class count");
    }

    #[test]
    fn paired_texture_orbits() {
        // Ks Kd 7h — the two kings occupy suits s and d. Suit s has rankset
        // {K}; suit d has rankset {K}; they share the same rankset, so the
        // transposition (s d) maps the board multiset to itself
        // (Ks <-> Kd, 7h fixed). The absent suit is c; suit h is present (7h)
        // and has rankset {7}, distinct from {K}, so h is NOT interchangeable
        // with s or d. c is absent but there is no other absent suit to swap
        // with, AND swapping c with s or d would move a K off its suit pair
        // unless paired — but (s d) already covers the king pair. So the
        // stabilizer = { identity, (s d) }, |S| = 2.
        let prefix = [card(13, S), card(13, D), card(7, H)];
        let stab = board_stabilizer(&prefix);
        assert_eq!(stab.len(), 2, "paired: identity + (s d) king-suit swap");

        let dealt = undealt_cards(&prefix);
        let classes = group_chance_children(&prefix, &dealt);
        assert_partition_and_relperm(&classes, &dealt);

        // (s d) swap => for an undealt rank, (rank, s) ~ (rank, d).
        // 2s ~ 2d (both suits free to swap), but 2h and 2c are singletons.
        assert!(
            same_class(&classes, &dealt, card(2, S), card(2, D)),
            "2s and 2d isomorphic under (s d)"
        );
        assert!(!same_class(&classes, &dealt, card(2, S), card(2, H)));
        assert!(!same_class(&classes, &dealt, card(2, S), card(2, C)));

        // Undealt = 49. Suit s: 13 - K = 12 undealt. Suit d: 13 - K = 12.
        // These pair up (s,d) -> 12 classes of size 2 (24 cards). Suit h:
        // 13 - 7 = 12 undealt singletons. Suit c: 13 undealt singletons.
        // Total = 12 + 12 + 13 = 37 classes.
        assert_eq!(classes.len(), 37, "paired class count");
    }

    // ---- TEST 2: rel_perm correctness (covered inside assert_partition_and_relperm) ----

    #[test]
    fn rel_perm_maps_representative_to_member_all_textures() {
        for prefix in [
            vec![card(14, S), card(13, D), card(7, H)], // rainbow
            vec![card(14, S), card(13, S), card(7, H)], // two-tone
            vec![card(14, S), card(13, S), card(7, S)], // monotone
            vec![card(13, S), card(13, D), card(7, H)], // paired
        ] {
            let dealt = undealt_cards(&prefix);
            let classes = group_chance_children(&prefix, &dealt);
            // assert_partition_and_relperm already checks the rel_perm law;
            // re-run it here as the dedicated TEST 2 gate.
            assert_partition_and_relperm(&classes, &dealt);
            // Every rel_perm must itself be in the board stabilizer.
            let stab: std::collections::HashSet<[u8; 4]> = board_stabilizer(&prefix)
                .into_iter()
                .map(|i| SUIT_PERMUTATIONS[i])
                .collect();
            for class in &classes {
                for &(_, rel_perm) in &class.members {
                    assert!(stab.contains(&rel_perm), "rel_perm must be a stabilizer perm");
                }
            }
        }
    }

    // ---- TEST 3: sigma round-trip (bijection + inverse) ----

    /// Invert a suit permutation: `inv[perm[s]] = s`.
    fn invert_perm(perm: &[u8; 4]) -> [u8; 4] {
        let mut inv = [0u8; 4];
        for s in 0..4u8 {
            inv[perm[s as usize] as usize] = s;
        }
        inv
    }

    /// Build a suit-closed hole list: ALL C(52,2) = 1326 two-card combos. Any
    /// suit permutation maps this set onto itself, so sigma is always a true
    /// permutation.
    fn all_holes() -> Vec<[u8; 2]> {
        let mut out = Vec::with_capacity(1326);
        for a in 0u8..52 {
            for b in (a + 1)..52 {
                out.push([card_from_idx(a), card_from_idx(b)]);
            }
        }
        out
    }

    /// Map a 0..52 deck index to a `rank*4+suit` card (ranks 2..=14).
    fn card_from_idx(i: u8) -> u8 {
        let r = i / 4 + 2;
        let s = i % 4;
        card(r, s)
    }

    #[test]
    fn sigma_is_a_permutation_and_round_trips() {
        let holes = all_holes();
        let hole_index = build_hole_index(&holes);

        // Use the monotone stabilizer (richest: |S| = 6) for a thorough check.
        let prefix = [card(14, S), card(13, S), card(7, S)];
        let stab: Vec<[u8; 4]> = board_stabilizer(&prefix)
            .into_iter()
            .map(|i| SUIT_PERMUTATIONS[i])
            .collect();

        for perm in &stab {
            let sigma = hand_index_permutation(&holes, &hole_index, perm);
            assert_eq!(sigma.len(), holes.len());

            // Bijection: every output index hit exactly once.
            let mut hit = vec![false; holes.len()];
            for &dst in &sigma {
                assert!(!hit[dst as usize], "sigma is not injective");
                hit[dst as usize] = true;
            }
            assert!(hit.iter().all(|&b| b), "sigma is not surjective");

            // Round-trip: sigma composed with the inverse perm's sigma = id.
            let inv = invert_perm(perm);
            let sigma_inv = hand_index_permutation(&holes, &hole_index, &inv);
            for h in 0..holes.len() {
                let back = sigma_inv[sigma[h] as usize] as usize;
                assert_eq!(back, h, "sigma then inverse-sigma must be identity");
            }
        }
    }

    // ---- TEST 4: consistency with the existing parity-locked canonicalizer ----

    #[test]
    fn rep_and_member_agree_with_canonicalize_board() {
        // For a member reached from the representative by `rel_perm in S`,
        // canonicalize_board(prefix ++ rep_card) must equal
        // canonicalize_board(prefix ++ member_card): rel_perm fixes the prefix
        // and maps rep_card -> member_card, so the two full boards are exactly
        // suit-isomorphic and the lex-min canonical key is identical.
        for prefix in [
            vec![card(14, S), card(13, D), card(7, H)], // rainbow
            vec![card(14, S), card(13, S), card(7, H)], // two-tone
            vec![card(14, S), card(13, S), card(7, S)], // monotone
            vec![card(13, S), card(13, D), card(7, H)], // paired
        ] {
            let dealt = undealt_cards(&prefix);
            let classes = group_chance_children(&prefix, &dealt);
            for class in &classes {
                let rep_card = dealt[class.representative_child_idx];
                let mut rep_board = prefix.clone();
                rep_board.push(rep_card);
                let (rep_key, _) = canonicalize_board(&rep_board);
                for &(idx, _) in &class.members {
                    let mut member_board = prefix.clone();
                    member_board.push(dealt[idx]);
                    let (member_key, _) = canonicalize_board(&member_board);
                    assert_eq!(
                        rep_key, member_key,
                        "members of one iso class must share the canonical board key"
                    );
                }
            }
        }
    }

    #[test]
    fn empty_prefix_stabilizer_is_full_group() {
        // No prefix cards => every suit perm fixes the (empty) board.
        assert_eq!(board_stabilizer(&[]).len(), 24);
    }
}
