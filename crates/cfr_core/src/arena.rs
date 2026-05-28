//! v1.10 PR-1 — thread-local bump arena for vector-form DCFR scratch buffers.
//!
//! Replaces the per-call `vec![0.0_f64; N]` allocations in
//! `dcfr_vector::VectorDCFR::traverse` with reusable `&mut [f64]` slices
//! drawn from a single contiguous `Vec<f64>`. The arena is **stack-disciplined**
//! (LIFO): every `traverse` frame records the entry high-water-mark, allocates
//! whatever scratch it needs above that mark, and rewinds back to the mark
//! before returning. Children always allocate above parents, so parent
//! buffers remain valid for the duration of the child call (the contiguous
//! backing `Vec<f64>` only grows, never shifts).
//!
//! ## Why an offset-based API (not `&mut [f64]`)?
//!
//! Returning `&mut [f64]` from `alloc_zeroed` would tie the slice's lifetime
//! to `&mut BumpArena`, making it impossible to hold a buffer while
//! recursing (the recursion needs `&mut BumpArena` too). The offset-based
//! API hands out `usize` indices that the caller dereferences via
//! `get_mut(off, n)` only when needed — borrows are short-lived and never
//! overlap with the recursive `&mut self.arena` re-borrow.
//!
//! ## Reference
//!
//! - `references/code/postflop-solver/src/alloc.rs` (AGPL — NOT copied,
//!   referenced only for the high-level "thread-local + LIFO stack" idea;
//!   our backing layout is a single Vec instead of chunked pages, and our
//!   API is safe Rust without `unsafe`).
//! - `crates/cfr_core/src/layout.rs:80-127` — precedent for an arena-backed
//!   regret/strategy_sum store inside this crate (scalar DCFR).
//!
//! ## Performance notes
//!
//! - **Initial capacity**: 1 MB (`INITIAL_CAPACITY_F64 = 131_072` doubles).
//!   The first solve grows this until the working set fits; subsequent
//!   solves of similar size pay zero allocator cost.
//! - **Zeroing**: explicit `for x in slice { *x = 0.0; }` loop. LLVM lowers
//!   this to `memset` on aarch64 and x86_64 release builds.
//! - **No `unsafe`**: spec §1 / §9 #3 forbids `unsafe` outside `simd.rs`.

use std::cell::RefCell;

/// Initial capacity of the arena's backing `Vec<f64>` in elements (8 bytes
/// each) — 1 MB. The Vec grows by doubling on demand, so steady-state
/// solves of a given size pay one growth round-trip total.
const INITIAL_CAPACITY_F64: usize = 1 << 17;

/// Single-threaded bump-pointer arena for `f64` scratch buffers.
///
/// **Invariant**: `mark <= buf.len()`. Slots are valid as long as the
/// caller holds an offset that is `< mark` for the duration of the borrow.
///
/// **LIFO discipline**: callers MUST restore the high-water-mark to its
/// entry value before returning. `BumpScope` automates this via RAII;
/// direct callers (e.g. `traverse`) record the mark on entry and call
/// `reset_to` before returning.
pub struct BumpArena {
    buf: Vec<f64>,
    mark: usize,
}

impl BumpArena {
    /// Construct an empty arena with the default 1 MB initial capacity.
    pub fn new() -> Self {
        Self {
            buf: Vec::with_capacity(INITIAL_CAPACITY_F64),
            mark: 0,
        }
    }

    /// Reserve `n` zeroed `f64`s; returns the offset into the arena.
    ///
    /// Grows the backing `Vec` by doubling when capacity is exhausted.
    /// The returned offset remains valid until the arena's mark is reset
    /// to a value `<= offset` (typically via `reset_to` or `BumpScope::drop`).
    #[inline]
    pub fn alloc_zeroed(&mut self, n: usize) -> usize {
        let start = self.mark;
        let end = start + n;
        if end > self.buf.len() {
            // Grow by doubling. Reserve at least `end`; never shrink.
            let new_len = end.max(self.buf.len().saturating_mul(2)).max(INITIAL_CAPACITY_F64);
            self.buf.resize(new_len, 0.0);
        } else {
            // The slot may hold stale data from a prior allocation that
            // hit this region. Zero it explicitly. LLVM lowers this to
            // `memset` on both aarch64 and x86_64.
            for x in &mut self.buf[start..end] {
                *x = 0.0;
            }
        }
        self.mark = end;
        start
    }

    /// Borrow an immutable slice of length `n` at offset `off`.
    #[inline]
    pub fn get(&self, off: usize, n: usize) -> &[f64] {
        &self.buf[off..off + n]
    }

    /// Borrow a mutable slice of length `n` at offset `off`.
    #[inline]
    pub fn get_mut(&mut self, off: usize, n: usize) -> &mut [f64] {
        &mut self.buf[off..off + n]
    }

    /// Disjoint mutable borrow of two non-overlapping slots.
    ///
    /// Used by `traverse` when both `strategy` and `next_reach` must be
    /// in scope simultaneously to compute `next_reach[h] = reach[h] *
    /// strategy[h*A+a]`. `split_at_mut` proves disjointness without
    /// `unsafe`.
    #[inline]
    pub fn get_mut_pair(
        &mut self,
        off_a: usize,
        len_a: usize,
        off_b: usize,
        len_b: usize,
    ) -> (&mut [f64], &mut [f64]) {
        debug_assert!(
            off_a + len_a <= off_b || off_b + len_b <= off_a,
            "BumpArena::get_mut_pair: overlapping slots ({}..{}, {}..{})",
            off_a,
            off_a + len_a,
            off_b,
            off_b + len_b,
        );
        if off_a < off_b {
            let (left, right) = self.buf.split_at_mut(off_b);
            (&mut left[off_a..off_a + len_a], &mut right[..len_b])
        } else {
            let (left, right) = self.buf.split_at_mut(off_a);
            (&mut right[..len_a], &mut left[off_b..off_b + len_b])
        }
    }

    /// Disjoint borrow of three slots: two read-only + one mutable.
    ///
    /// Used by `traverse` to compute `next_reach[h] = reach[h] *
    /// strategy[h*A+a]` (two reads, one write) without `unsafe`.
    /// Slots MUST be non-overlapping (debug-asserted).
    ///
    /// Implementation: take a single `&mut [f64]` over the full arena
    /// buffer, then carve out the mutable slot via two `split_at_mut`
    /// calls. The remaining ranges are downgraded to `&[f64]` (Rust
    /// allows a `&[T]` re-borrow from a `&mut [T]`).
    #[inline]
    pub fn get_two_ref_one_mut(
        &mut self,
        off_r1: usize,
        len_r1: usize,
        off_r2: usize,
        len_r2: usize,
        off_w: usize,
        len_w: usize,
    ) -> (&[f64], &[f64], &mut [f64]) {
        debug_assert!(
            off_r1 + len_r1 <= off_w || off_w + len_w <= off_r1,
            "BumpArena::get_two_ref_one_mut: r1 overlaps w"
        );
        debug_assert!(
            off_r2 + len_r2 <= off_w || off_w + len_w <= off_r2,
            "BumpArena::get_two_ref_one_mut: r2 overlaps w"
        );
        // Split the buffer around `off_w` so the write region is a
        // distinct &mut slice from the two read regions.
        let total_len = self.buf.len();
        debug_assert!(off_w + len_w <= total_len, "write slot out of bounds");
        let (left, right) = self.buf.split_at_mut(off_w);
        let (write_region, right_tail) = right.split_at_mut(len_w);
        // Downgrade left + right_tail to &[f64].
        let left_ro: &[f64] = left;
        let right_ro: &[f64] = right_tail;
        // Map (off_r{1,2}, len_r{1,2}) into left or right_tail.
        let r1 = if off_r1 < off_w {
            &left_ro[off_r1..off_r1 + len_r1]
        } else {
            let local = off_r1 - off_w - len_w;
            &right_ro[local..local + len_r1]
        };
        let r2 = if off_r2 < off_w {
            &left_ro[off_r2..off_r2 + len_r2]
        } else {
            let local = off_r2 - off_w - len_w;
            &right_ro[local..local + len_r2]
        };
        (r1, r2, write_region)
    }

    /// Current high-water-mark (number of `f64`s in use).
    #[inline]
    pub fn mark(&self) -> usize {
        self.mark
    }

    /// Reset the high-water-mark to `m`. All offsets `>= m` are invalidated.
    /// Backing capacity is retained for reuse.
    #[inline]
    pub fn reset_to(&mut self, m: usize) {
        debug_assert!(m <= self.mark, "BumpArena::reset_to: cannot advance via reset");
        self.mark = m;
    }
}

impl Default for BumpArena {
    fn default() -> Self {
        Self::new()
    }
}

/// RAII guard that restores `arena.mark` to its construction value on drop.
///
/// Use to scope arena allocations to a function or block. The `BumpScope`
/// holds a `&mut BumpArena` — callers that need to recurse should NOT
/// construct a `BumpScope` at the recursion frame (it would conflict with
/// the `&mut arena` argument); instead they should record + restore the
/// mark manually inside `traverse`. `BumpScope` is for the outer wrapper
/// in `solve` where the arena is constructed.
pub struct BumpScope<'a> {
    arena: &'a mut BumpArena,
    entry_mark: usize,
}

impl<'a> BumpScope<'a> {
    /// Begin a new scope.
    pub fn new(arena: &'a mut BumpArena) -> Self {
        let entry_mark = arena.mark;
        Self { arena, entry_mark }
    }

    /// Borrow the underlying arena.
    pub fn arena(&mut self) -> &mut BumpArena {
        self.arena
    }
}

impl Drop for BumpScope<'_> {
    fn drop(&mut self) {
        self.arena.mark = self.entry_mark;
    }
}

thread_local! {
    /// Thread-local arena instance. The vector-form DCFR solver pulls this
    /// at the top of `solve` (single-threaded path) so subsequent solves
    /// on the same thread reuse the same backing allocation.
    pub static TLS_ARENA: RefCell<BumpArena> = RefCell::new(BumpArena::new());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alloc_zeroed_returns_zeroed_slice() {
        let mut arena = BumpArena::new();
        let off = arena.alloc_zeroed(10);
        let slice = arena.get(off, 10);
        for &x in slice {
            assert_eq!(x, 0.0);
        }
    }

    #[test]
    fn alloc_advances_mark() {
        let mut arena = BumpArena::new();
        assert_eq!(arena.mark(), 0);
        let _ = arena.alloc_zeroed(5);
        assert_eq!(arena.mark(), 5);
        let _ = arena.alloc_zeroed(7);
        assert_eq!(arena.mark(), 12);
    }

    #[test]
    fn reset_to_rewinds_mark() {
        let mut arena = BumpArena::new();
        let _ = arena.alloc_zeroed(5);
        let m = arena.mark();
        let _ = arena.alloc_zeroed(20);
        assert_eq!(arena.mark(), 25);
        arena.reset_to(m);
        assert_eq!(arena.mark(), 5);
    }

    #[test]
    fn realloc_zeros_stale_data() {
        let mut arena = BumpArena::new();
        let off = arena.alloc_zeroed(10);
        // Write garbage to the slot.
        for x in arena.get_mut(off, 10) {
            *x = 99.0;
        }
        // Rewind and re-alloc the same region.
        arena.reset_to(0);
        let off2 = arena.alloc_zeroed(10);
        assert_eq!(off, off2);
        let slice = arena.get(off2, 10);
        for &x in slice {
            assert_eq!(x, 0.0, "reallocated slot must be zeroed");
        }
    }

    #[test]
    fn bump_scope_restores_mark() {
        let mut arena = BumpArena::new();
        let _ = arena.alloc_zeroed(3);
        let outer_mark = arena.mark();
        {
            let mut scope = BumpScope::new(&mut arena);
            let _ = scope.arena().alloc_zeroed(100);
            assert_eq!(scope.arena().mark(), 103);
        }
        assert_eq!(arena.mark(), outer_mark);
    }

    #[test]
    fn arena_grows_by_doubling() {
        let mut arena = BumpArena::new();
        let initial_cap = arena.buf.capacity();
        let big = initial_cap + 1024;
        let _ = arena.alloc_zeroed(big);
        assert!(arena.buf.len() >= big);
    }

    #[test]
    fn get_mut_pair_disjoint() {
        let mut arena = BumpArena::new();
        let a = arena.alloc_zeroed(5);
        let b = arena.alloc_zeroed(5);
        let (sa, sb) = arena.get_mut_pair(a, 5, b, 5);
        sa[0] = 1.0;
        sb[0] = 2.0;
        assert_eq!(arena.get(a, 5)[0], 1.0);
        assert_eq!(arena.get(b, 5)[0], 2.0);
    }

    #[test]
    fn get_mut_pair_reverse_order() {
        let mut arena = BumpArena::new();
        let a = arena.alloc_zeroed(5);
        let b = arena.alloc_zeroed(5);
        // Request in reverse-allocation order — the helper handles it.
        let (sb, sa) = arena.get_mut_pair(b, 5, a, 5);
        sb[0] = 2.0;
        sa[0] = 1.0;
        assert_eq!(arena.get(a, 5)[0], 1.0);
        assert_eq!(arena.get(b, 5)[0], 2.0);
    }
}
