//! Cache-blocked flat infoset layout (PR 8).
//!
//! Replaces the `HashMap<String, InfosetData>` access pattern in the DCFR
//! inner loop with a *flat array* that groups regret + strategy vectors in
//! contiguous blocks sized to fit Apple M-series L1d (32 KB) cache lines.
//!
//! **Why this matters for performance:** the `HashMap<String, …>` lookup
//! does (1) hash the key (`String` — short for Kuhn/Leduc, longer for HUNL),
//! (2) probe the bucket array, (3) deref the `Box<InfosetData>` and follow
//! two more pointer chases into `regret_sum: Vec<f64>` and
//! `strategy_sum: Vec<f64>`. That's three pointer hops + a string hash on
//! every infoset visit — and the visited rows are tiny (1–8 f64 lanes),
//! meaning we touch maybe 64 bytes per visit while spending most cycles in
//! cache-miss latency.
//!
//! **What we do here:** pack rows into a contiguous `Vec<f64>` ("regret
//! arena") and a parallel `Vec<f64>` ("strategy arena"), 1 row = `num_actions`
//! lanes wide. Each block of `BLOCK_SIZE` rows (default 64) is laid out
//! consecutively in memory. Per-row metadata (`num_actions`,
//! `last_discount_iter`) is in a separate compact array so reading metadata
//! doesn't pollute the regret cache line.
//!
//! BLOCK_SIZE choice: 64 rows × 8 actions × 8 bytes × 2 (regret + strategy
//! arenas) = 8192 B per block — fits comfortably in L1d (32 KB) so a full
//! block's regret + strategy stays hot while the discount/update kernel
//! sweeps it. For Kuhn (2 actions) the equivalent block is 2 KB — also
//! cache-resident.
//!
//! This module is **opt-in** for PR 8: the existing `HashMap`-backed paths
//! in `dcfr.rs` and `hunl_solver.rs` continue to work. A `FlatInfosetStore`
//! is exposed for future call sites (the microbench drives it directly to
//! measure the layout-only speedup); the DCFR loops route their inner
//! arithmetic through `simd.rs` regardless of the storage backing. Both
//! changes compose without coupling.
//!
//! Licensing posture: pattern-only inspiration from `slumbot2019` (MIT,
//! `references/code/slumbot2019/CFR.cpp`); **never** copied from
//! `references/code/postflop-solver` or `references/code/TexasSolver`
//! (AGPL).

use std::collections::HashMap;

/// Rows per cache block. 64 × 8-action × 8-byte regret + strategy arenas
/// = 8 KB per block (fits in L1d on Apple M-series; tuned for HUNL's
/// 2–8 action width). For Kuhn (2 actions) blocks are 2 KB.
pub const BLOCK_SIZE: usize = 64;

/// Handle into a [`FlatInfosetStore`]. Opaque so callers can't reach into
/// the internals; used to fetch regrets / strategy / metadata.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub struct InfosetId(pub u32);

/// Per-row metadata kept in a compact array so reading it doesn't pollute
/// regret cache lines. (16 bytes per row vs `InfosetData`'s 48 bytes
/// equivalent including the two `Vec` heads.)
#[derive(Clone, Copy, Debug)]
pub struct RowMeta {
    /// Where this row's regret/strategy lanes start in the arena.
    pub offset: u32,
    /// Number of legal actions at this infoset (1..=8 in HUNL, 2..=3 in
    /// Leduc/Kuhn).
    pub num_actions: u16,
    /// DCFR last-discount-iter (lazy-discount catch-up state).
    pub last_discount_iter: u32,
}

/// Cache-blocked SoA infoset store. Allocates regret + strategy arenas
/// (parallel `Vec<f64>`) sized for `BLOCK_SIZE` rows; appends new blocks
/// as more infosets are inserted.
pub struct FlatInfosetStore {
    /// Key → InfosetId lookup (still indirection on first visit, but the
    /// hot inner loop walks `regret_arena` / `strategy_arena` directly
    /// once it has the `InfosetId`).
    pub key_to_id: HashMap<String, InfosetId>,
    /// Reverse map for diagnostic dumps + final `average_strategy`.
    pub id_to_key: Vec<String>,
    /// Per-row metadata.
    pub meta: Vec<RowMeta>,
    /// Contiguous regret values, BLOCK_SIZE × max-row-width per block.
    pub regret_arena: Vec<f64>,
    /// Contiguous strategy values, parallel layout to `regret_arena`.
    pub strategy_arena: Vec<f64>,
    /// Width of each row slot in the arena. Set to the max num_actions seen
    /// so all rows in a block stride uniformly.
    pub row_width: usize,
}

impl FlatInfosetStore {
    /// Construct an empty store with the given `row_width` (the max
    /// `num_actions` across all infosets — typically 8 for HUNL, 3 for
    /// Leduc, 2 for Kuhn).
    pub fn new(row_width: usize) -> Self {
        Self {
            key_to_id: HashMap::new(),
            id_to_key: Vec::new(),
            meta: Vec::new(),
            regret_arena: Vec::new(),
            strategy_arena: Vec::new(),
            row_width: row_width.max(1),
        }
    }

    /// Number of infosets stored.
    pub fn len(&self) -> usize {
        self.meta.len()
    }

    /// True if no infosets stored yet.
    pub fn is_empty(&self) -> bool {
        self.meta.is_empty()
    }

    /// Insert (or fetch existing) infoset by key. Returns the ID.
    pub fn intern(&mut self, key: &str, num_actions: usize) -> InfosetId {
        if let Some(&id) = self.key_to_id.get(key) {
            return id;
        }
        let id = InfosetId(self.meta.len() as u32);
        let offset = (id.0 as usize * self.row_width) as u32;
        // Grow arenas if needed.
        let needed = offset as usize + self.row_width;
        if needed > self.regret_arena.len() {
            // Round up to next BLOCK_SIZE-row boundary to keep block-aligned
            // allocations consistent.
            let blocks_needed = needed.div_ceil(BLOCK_SIZE * self.row_width);
            let new_cap = blocks_needed * BLOCK_SIZE * self.row_width;
            self.regret_arena.resize(new_cap, 0.0);
            self.strategy_arena.resize(new_cap, 0.0);
        }
        self.meta.push(RowMeta {
            offset,
            num_actions: num_actions as u16,
            last_discount_iter: 0,
        });
        self.id_to_key.push(key.to_string());
        self.key_to_id.insert(key.to_string(), id);
        id
    }

    /// Borrow the regret row for the given ID. Length matches the row's
    /// `num_actions` (not `row_width`).
    #[inline]
    pub fn regret(&self, id: InfosetId) -> &[f64] {
        let m = self.meta[id.0 as usize];
        let off = m.offset as usize;
        &self.regret_arena[off..off + m.num_actions as usize]
    }

    /// Mutably borrow the regret row for the given ID.
    #[inline]
    pub fn regret_mut(&mut self, id: InfosetId) -> &mut [f64] {
        let m = self.meta[id.0 as usize];
        let off = m.offset as usize;
        &mut self.regret_arena[off..off + m.num_actions as usize]
    }

    /// Borrow the strategy-sum row for the given ID.
    #[inline]
    pub fn strategy_sum(&self, id: InfosetId) -> &[f64] {
        let m = self.meta[id.0 as usize];
        let off = m.offset as usize;
        &self.strategy_arena[off..off + m.num_actions as usize]
    }

    /// Mutably borrow the strategy-sum row for the given ID.
    #[inline]
    pub fn strategy_sum_mut(&mut self, id: InfosetId) -> &mut [f64] {
        let m = self.meta[id.0 as usize];
        let off = m.offset as usize;
        &mut self.strategy_arena[off..off + m.num_actions as usize]
    }

    /// Disjoint mutable borrow of regret + strategy rows. Useful when the
    /// CFR inner loop needs both in scope simultaneously without two
    /// `meta[id]` lookups or any clones.
    ///
    /// Implemented with safe borrows only (no `unsafe`): the three target
    /// regions live in three distinct fields of `self` (`regret_arena`,
    /// `strategy_arena`, `meta`), so the borrow checker can prove
    /// disjointness without raw-pointer trickery. Per spec §1 / §9 #3,
    /// `unsafe` outside `simd.rs` is forbidden.
    #[inline]
    pub fn row_mut(&mut self, id: InfosetId) -> (&mut [f64], &mut [f64], &mut RowMeta) {
        let idx = id.0 as usize;
        // Take a mutable borrow of meta[idx] first, capturing offset+na by
        // copy (RowMeta is Copy) so the arena borrows below can proceed
        // without colliding on `self.meta` access.
        let meta_ref: &mut RowMeta = &mut self.meta[idx];
        let off = meta_ref.offset as usize;
        let na = meta_ref.num_actions as usize;
        // Disjoint mutable borrows on two distinct Vec fields — the borrow
        // checker handles this without unsafe because the fields are
        // separate struct members.
        let regret: &mut [f64] = &mut self.regret_arena[off..off + na];
        let strat: &mut [f64] = &mut self.strategy_arena[off..off + na];
        (regret, strat, meta_ref)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn intern_returns_stable_id() {
        let mut s = FlatInfosetStore::new(3);
        let a = s.intern("foo", 2);
        let b = s.intern("foo", 2);
        let c = s.intern("bar", 3);
        assert_eq!(a, b);
        assert_ne!(a, c);
        assert_eq!(s.len(), 2);
    }

    #[test]
    fn row_mut_yields_disjoint_borrows() {
        let mut s = FlatInfosetStore::new(3);
        let id = s.intern("foo", 3);
        {
            let (r, st, meta) = s.row_mut(id);
            assert_eq!(r.len(), 3);
            assert_eq!(st.len(), 3);
            r[0] = 1.0;
            st[1] = 2.0;
            meta.last_discount_iter = 42;
        }
        assert_eq!(s.regret(id)[0], 1.0);
        assert_eq!(s.strategy_sum(id)[1], 2.0);
        assert_eq!(s.meta[id.0 as usize].last_discount_iter, 42);
    }

    #[test]
    fn arena_grows_in_block_increments() {
        let mut s = FlatInfosetStore::new(8);
        for i in 0..BLOCK_SIZE + 1 {
            s.intern(&format!("k{i}"), 8);
        }
        // After BLOCK_SIZE+1 inserts we should be in the second block.
        assert!(s.regret_arena.len() >= 2 * BLOCK_SIZE * 8);
        assert!(s.regret_arena.len().is_multiple_of(BLOCK_SIZE * 8));
    }
}
