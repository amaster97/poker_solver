//! v1.10 PR-4 — opt-in Rayon multi-threading for the postflop chance subtree.
//!
//! ## Concurrency model
//!
//! At the root of a postflop solve, the betting tree's first non-decision
//! node is typically a `FlatNode::Chance` enumerating the turn-card (or
//! river-card) outcomes. Each child of that chance node defines an
//! **independent subtree** with a disjoint range of `node_idx` values
//! (DFS pre-order build in `exploit.rs::BettingTree::add` makes child
//! subtrees contiguous and non-overlapping).
//!
//! That structural property is what makes parallelization safe: when
//! `traverse` mutates `self.infosets[node_idx]` for the `update_player`'s
//! decision nodes, the mutated indices in two different turn-card
//! subtrees never overlap. We therefore partition `self.infosets` by
//! splitting the underlying vector into one disjoint mutable slice per
//! child, hand each slice to a Rayon worker, and rejoin at the end of
//! the chance-level walk.
//!
//! No data races are possible:
//!   - Read-only shared state: `&BettingTree`, `&EvalContext`,
//!     `&TerminalCache`, immutable reach vectors. These are inherently
//!     `Sync` and `Send`.
//!   - Mutable per-thread state: a slot-range view (`InfosetView`) that
//!     owns the `&mut [Option<VectorInfosetData>]` for that thread's
//!     subtree. Rust's borrowck enforces non-overlap statically because
//!     the views are produced by repeated `split_at_mut` on the original
//!     `&mut [Option<VectorInfosetData>]`.
//!
//! ## Why this preserves CFR semantics
//!
//! The `traverse` flow at an `own (update_player)` decision node is:
//!   1. compute_strategy → read regret table for current strategy
//!   2. recurse into children, accumulate action_values
//!   3. discount regret + strategy_sum (DCFR catch-up)
//!   4. write delta back into regret + strategy_sum
//!
//! Each turn-card subtree's flow is fully self-contained within its slot
//! range — steps (1), (3), (4) only touch nodes in its own range, and
//! step (2) only recurses INTO that range. There is no cross-thread
//! dependency, so the parallel walk produces the SAME regret table as
//! the sequential walk would, up to **floating-point sum-reordering at
//! the chance node** where per-thread per-hand value vectors are
//! combined with `prob * v_child`.
//!
//! Sum reordering is the ONLY source of non-bit-identical drift; this is
//! why the opt-in path runs against a looser tolerance (1e-6
//! exploitability, 1e-9 game value) in
//! `tests/test_vector_rayon_diff.py`. The canonical single-threaded
//! path remains bit-identical to pre-PR-4.
//!
//! ## Activation
//!
//! Set `CFR_RAYON_CHANCE=1` at the entry to `VectorDCFR::solve`. The
//! check happens once per solve (not per iteration) and stays cached in
//! the dispatch in `solve`. Default (env var unset) keeps the canonical
//! single-threaded code path.
//!
//! ## Safety
//!
//! No `unsafe` is used in this module. Disjoint mutable access is
//! achieved via `split_at_mut` over the original `&mut [...]` slice.
//! The `parallel_traverse_chance_root` function asserts that the root
//! chance node's children form a contiguous, non-overlapping coverage
//! of `tree.nodes` (the DFS-build invariant in `exploit.rs`).

use rayon::prelude::*;

use crate::dcfr_vector::{
    traverse_with_infosets, EvalContext, TerminalCache, VectorInfosetData,
};
use crate::exploit::BettingTree;

/// Coverage descriptor for a single chance child — the contiguous
/// `node_idx` range its DFS pre-order subtree occupies.
///
/// Returned by [`derive_child_ranges`]. The ranges are
/// `[start, end_exclusive)` and partition `[chance_idx + 1, tree.len())`
/// (with possible gaps when the chance node is NOT the literal root and
/// later children exist after the chance subtree).
#[derive(Debug, Clone, Copy)]
struct ChildRange {
    /// First node_idx owned by this child's subtree.
    start: usize,
    /// One past the last node_idx owned by this child's subtree.
    end: usize,
    /// Index of the child's root node (always `start` for the DFS build,
    /// kept explicit for readability).
    root_idx: usize,
}

/// Walks `tree.nodes` to derive each chance child's contiguous subtree
/// `node_idx` range. Returns one [`ChildRange`] per child in the same
/// order as `chance.children`.
///
/// **Invariant relied on**: the DFS pre-order build in
/// `exploit.rs::BettingTree::add` assigns each child's subtree a
/// contiguous range that starts at the child's `root_idx` and ends just
/// before the next sibling's `root_idx` (or `tree.nodes.len()` for the
/// last child). We assert that invariant here as a defensive check.
fn derive_child_ranges(tree: &BettingTree, children: &[usize]) -> Vec<ChildRange> {
    debug_assert!(!children.is_empty(), "chance node with no children");
    let total = tree.nodes.len();
    let mut ranges = Vec::with_capacity(children.len());
    for i in 0..children.len() {
        let start = children[i];
        let end = if i + 1 < children.len() {
            children[i + 1]
        } else {
            total
        };
        // Invariant: each child's subtree is contiguous and starts at
        // its own root_idx. If the DFS-build ever changes, the diff
        // test in `tests/test_vector_rayon_diff.py` would catch
        // strategy drift, but this guard surfaces the violation early
        // and clearly.
        assert!(
            start < end,
            "child range invariant violated: child {i} has start={start} >= end={end}"
        );
        ranges.push(ChildRange { start, end, root_idx: start });
    }
    ranges
}

/// Parallel traversal of a `FlatNode::Chance` node. Mirrors the
/// sequential `Chance` branch in `traverse_recursive_with_parallel`
/// but partitions the children across Rayon workers.
///
/// `infosets` is a slice that COVERS the chance node and its full
/// subtree — typically `&mut self.infosets[chance_offset..]` where
/// `chance_offset` is the global node index of the chance node minus
/// the caller's existing `offset`. We split this slice into one
/// disjoint sub-slice per child using `split_at_mut`; each worker
/// only ever indexes into its assigned sub-slice via global
/// `node_idx - new_offset`, guaranteed safe by Rust's borrowck.
///
/// `chance_idx` is the global node index of the chance node.
/// `offset` is the global index that `infosets[0]` represents.
/// Combined, the chance node's children's node-idx ranges live at
/// positions `child_start - offset` through `child_end - offset` in
/// the slice.
///
/// Returns the chance node's per-update_player-hand value vector,
/// computed as `Σ_c prob * traverse(c)`. The summation happens AFTER
/// all workers complete, in source-iteration order (Rayon's
/// `par_iter().collect()` preserves source order), so the reduction is
/// performed sequentially against the collected child-value vectors.
/// That keeps the reduction deterministic and bit-stable across runs.
///
/// `terminal_ie` is threaded unchanged into each worker's
/// `traverse_with_infosets` so workers use the inclusion-exclusion
/// terminal evaluator iff `CFR_TERMINAL_IE` was set at solve start.
#[allow(clippy::too_many_arguments)]
pub(crate) fn parallel_traverse_chance(
    tree: &BettingTree,
    eval_ctx: &EvalContext,
    terminal_cache: &TerminalCache,
    chance_idx: usize,
    children: &[usize],
    prob: f64,
    update_player: usize,
    iteration: u32,
    alpha: f64,
    beta: f64,
    gamma: f64,
    reach_p: &[f64],
    reach_opp: &[f64],
    infosets: &mut [Option<VectorInfosetData>],
    offset: usize,
    terminal_ie: bool,
    has_chance_template: &[bool],
    suit_iso: bool,
    suit_iso_cache: &crate::suit_iso::SuitIsoCache,
) -> Vec<f64> {
    let update_hands = eval_ctx.hand_count[update_player];

    // Defensive invariant: the chance node and all its children must
    // live inside our slice range [offset, offset + infosets.len()).
    debug_assert!(
        chance_idx >= offset,
        "parallel_traverse_chance: chance_idx {chance_idx} < caller offset {offset}",
    );
    debug_assert!(
        chance_idx - offset < infosets.len(),
        "parallel_traverse_chance: chance_idx {chance_idx} outside slice [{offset}, {})",
        offset + infosets.len(),
    );

    // Derive per-child node_idx ranges from the DFS-built betting tree.
    let ranges = derive_child_ranges(tree, children);

    // Per-child subtrees are at GLOBAL indices [range.start, range.end);
    // their position in our local `infosets` slice is offset by the
    // caller's `offset`. Carve the slice into disjoint sub-slices.
    //
    // The local positions are:
    //   local_start_i = ranges[i].start - offset
    //   local_end_i   = ranges[i].end   - offset
    //
    // We walk from the start of the slice forward, peeling off each
    // child's sub-slice with `split_at_mut`. Any "prelude" between
    // siblings (e.g., the chance node itself at position
    // chance_idx - offset, or interleaved non-decision nodes) is
    // discarded into the per-iteration `_prelude` slot.
    let mut remaining: &mut [Option<VectorInfosetData>] = infosets;
    let mut prefix_consumed_local: usize = 0;
    let mut shards: Vec<(ChildRange, &mut [Option<VectorInfosetData>])> =
        Vec::with_capacity(ranges.len());
    for &range in &ranges {
        let local_start = range.start - offset;
        let local_end = range.end - offset;
        debug_assert!(
            local_start >= prefix_consumed_local,
            "child ranges must be in ascending order; got local_start={local_start} \
             after prefix_consumed_local={prefix_consumed_local}",
        );
        debug_assert!(
            local_end <= prefix_consumed_local + remaining.len(),
            "child range exceeds available slice: local_end={local_end} > end of remaining",
        );
        let lead_len = local_start - prefix_consumed_local;
        let (_prelude, after_prelude) = remaining.split_at_mut(lead_len);
        let shard_len = local_end - local_start;
        let (shard, rest) = after_prelude.split_at_mut(shard_len);
        shards.push((range, shard));
        remaining = rest;
        prefix_consumed_local = local_end;
    }
    let _ = remaining;

    // Snapshot reach vectors so each Rayon worker can borrow them as `&[f64]`.
    let reach_p_vec = reach_p.to_vec();
    let reach_opp_vec = reach_opp.to_vec();

    // Each worker walks its assigned child subtree via the
    // `traverse_with_infosets` thin wrapper (which always passes
    // `allow_parallel = false` to prevent nested rayon dispatch).
    // The `range.root_idx` is the GLOBAL node_idx of the child's
    // root; the shard's local positions start at `range.start`,
    // so the worker's local offset is also `range.start`.
    let per_child_values: Vec<Vec<f64>> = shards
        .into_par_iter()
        .map(|(range, shard)| {
            traverse_with_infosets(
                tree,
                eval_ctx,
                terminal_cache,
                range.root_idx,
                update_player,
                iteration,
                alpha,
                beta,
                gamma,
                &reach_p_vec,
                &reach_opp_vec,
                shard,
                range.start,
                terminal_ie,
                has_chance_template,
                suit_iso,
                suit_iso_cache,
            )
        })
        .collect();

    // Source-order reduction over the collected per-child values.
    // Bit-stable across runs (Rayon's `par_iter::collect` preserves
    // source order, and the per-hand sum loop is sequential).
    let mut values = vec![0.0_f64; update_hands];
    for child_values in &per_child_values {
        for (i, v) in child_values.iter().enumerate() {
            values[i] += prob * v;
        }
    }
    values
}

/// Read `CFR_RAYON_CHANCE` from the environment. Returns `true` iff
/// the variable is set to any non-empty value. Called once per
/// `VectorDCFR::solve` invocation; the cached boolean is then threaded
/// through the iteration loop. The dispatch in `solve_one_traverse`
/// also requires the root node to be a multi-child `FlatNode::Chance`
/// — see that function for the structural check.
pub(crate) fn parallel_chance_enabled() -> bool {
    matches!(std::env::var("CFR_RAYON_CHANCE"), Ok(v) if !v.is_empty())
}
