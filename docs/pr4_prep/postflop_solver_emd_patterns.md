# postflop-solver EMD patterns for PR 4 inspiration

**License reminder:** `postflop-solver` is **AGPL v3**. This document studies its
patterns for our independent re-implementation. **NO code is copied verbatim.**
All quoted line ranges are read-only inspiration; the algorithm shapes are
described in plain English, then re-derived from first principles for our
Python (and later Rust) ports. Even paraphrased pseudocode in this document is
written from scratch.

## 0. Scope correction (read this first)

The PR 4 task prompt asks for `abstraction*.rs` and `cfr.rs` files. **Neither
file exists in `postflop-solver`**:

- `src/lib.rs:17` states verbatim: *"The solver does not perform any
  abstraction."*
- The only "abstraction" postflop-solver implements is
  **suit-isomorphism on chance nodes** (board cards), not a card-bucket /
  EMD / k-means abstraction. Hole cards are stored **per individual combo**
  (`(Card, Card)` tuples), not as bucket ids. The full per-private-hand vector
  is the resolution at which the entire solver operates.
- There is no Discounted CFR file named `cfr.rs`; the CFR recursion lives in
  `src/solver.rs::solve_recursive` and `src/utility.rs::compute_cfvalue_recursive`.

**Implication for PR 4:** `postflop-solver` is the wrong reference for *EMD
bucketing patterns themselves* — the right reference for those is
`references/code/slumbot2019/src/build_kmeans_buckets.cpp` (MIT, safe to port
architecturally) and the literature already cited in `docs/pr4_prep/pr4_spec.md`
Section 3.3.

What `postflop-solver` **does** give us is a closely-related set of patterns
that PR 4 must interoperate with:

1. **How a mature postflop solver lays out per-hand state** when the resolution
   is one row per hole-card pair. This is the data layout PR 4's bucket
   lookup must *coexist with* and PR 6's Rust port will eventually replace.
2. **Suit-isomorphism canonicalization** on the board side — a technique
   PR 4's bucket key explicitly **defers** (see `pr4_spec.md` §4 Stage 4:
   *"Suit symmetry is left to a separate PR"*) but which PR 6 will want to
   add for the Rust solver. Studying it now lets PR 4 design its
   `board_canonical_id` so the future suit-iso layer can drop in without
   re-keying the lookup table.
3. **Hot-path memory layout** — `f32` vectors indexed by private-hand id,
   `Vec<[Vec<StrengthItem>; 2]>` keyed by `card_pair_to_index`, the SwapList
   trick for re-using one board's CFVs across isomorphic siblings. PR 6's
   Rust solver must produce the same hot-path shape with bucket ids
   substituted for private-hand indices.
4. **Card-removal correctness** — the per-board `valid_indices` and
   `same_hand_index` machinery that the showdown evaluation depends on.
   Card-removal is what makes "both players' hands bucketed" *hard*; the
   first-order naïve approach silently loses combinatorial mass.

Below: seven patterns, each cited to a specific file + line range, each
described in our own words, with explicit guidance on whether PR 4 should
**adopt**, **defer**, or **avoid** the pattern.

---

## 1. Suit-isomorphism canonicalization

### Algorithm shape

The solver computes, **at config-load time** (not per-iteration), which
suits on the current board are interchangeable. Two suits are "isomorphic"
if (a) the player ranges weight them identically and (b) the flop's
per-suit rank-set is identical (i.e., flushes are not differentially in
play). A small `suit_isomorphism: [u8; 4]` table is built — equivalent
suits share an id.

At chance nodes (turn / river deals), the solver enumerates 49 (or 48)
candidate next-cards but **skips** any whose suit is the "second copy" of
an already-computed isomorphic suit; instead, it records an
`isomorphism_ref` pointing back at the canonical sibling, plus an
`isomorphism_swap` list of `(u16, u16)` hand-index pairs that must be
swapped in the reach/CFV vector to map the canonical sibling's
per-hand values back onto this sibling's hand ordering.

The "swap list" trick is the load-bearing detail. Suit-isomorphism is not
just "two boards are equivalent"; it's "two boards are equivalent **after
permuting which hole-card combos correspond to which row in the CFV
vector**." The solver pre-computes the permutation once, then applies it
in place inside `apply_swap` during the CFV roll-up.

### Non-obvious details

- Isomorphism is computed for two streets: turn-after-flop and
  river-after-turn. The turn case checks `flop_rankset[s1] == flop_rankset[s2]`;
  the river case checks both the flop and the turn rank-sets.
- The swap list is **player-specific** (`[SwapList; 2]`). A suit swap
  permutes each player's private-hand vector differently because each
  player's range may have a different combo ordering.
- Iteration uses `apply_swap`-then-`accumulate`-then-`apply_swap`-again
  to avoid a separate scratch buffer — the swap is its own inverse.

### Cited at

- `references/code/postflop-solver/src/card.rs:247-361` (the
  `isomorphism()` builder)
- `references/code/postflop-solver/src/card.rs:363-401`
  (`isomorphism_swap_internal`, where the per-player permutation is built
  via a reverse-lookup table)
- `references/code/postflop-solver/src/card.rs:404-432`
  (`isomorphism_internal`, where the `isomorphism_ref` skip-list is
  built)
- `references/code/postflop-solver/src/range.rs:660-684`
  (`is_suit_isomorphic` — checks that the range weights are equal
  under a suit swap across all 1326 hole-card combos)
- `references/code/postflop-solver/src/utility.rs:232-241`
  (`apply_swap`, the in-place hot-path application)
- `references/code/postflop-solver/src/utility.rs:420-436`
  (the call site inside `compute_cfvalue_recursive` showing the
  swap-accumulate-swap pattern)

### PR 4 recommendation

**Defer, but make compatible.** PR 4's `pr4_spec.md` §4 Stage 4 explicitly
says suit-isomorphism is **not** applied at the bucket-lookup layer.
However, PR 6's Rust solver will want it for chance-node deduplication.

The design choice PR 4 must make consciously: the bucket-lookup key
should be `(board_canonical_id, hand_canonical_id) → bucket_id` where
`board_canonical_id` is `1755` for the flop (rank-isomorphism-reduced
count, suits not collapsed). PR 6 can then **add** a separate "which
suit-iso class does this board belong to" layer on top of the bucket
lookup without re-keying. **Do not** bake suit-iso into the bucket
lookup itself in PR 4.

---

## 2. Equity feature vector construction

### What postflop-solver actually computes

**Postflop-solver does not compute equity feature vectors at all.** Hand
strength is computed once per (board, hand) pair as a single `u16` from
a 7-card poker-hand evaluator, then sorted lexicographically so showdown
can be evaluated by a two-pointer sweep over strength-sorted indices.
This is the *direct equity* path, not the *equity distribution* path that
EMD bucketing requires.

What it does do that's relevant:

- For each `(turn_card, river_card)` pair (i.e., every possible 5-card
  board), it builds `[Vec<StrengthItem>; 2]` — one strength vector per
  player. Each `StrengthItem` is `{ strength: u16, index: u16 }` where
  `strength = hand.evaluate() + 1` (the +1 is so 0 can be a sentinel)
  and `index` is the private-hand row id.
- These vectors are **sorted by strength**, so showdown becomes a
  monotonic sweep with cfreach accumulation.

### Why this matters for PR 4

PR 4 needs equity-distribution histograms (`pr4_spec.md` §3.3) — a
*different* feature than what postflop-solver materializes. But the
**evaluator infrastructure** (lines below) is exactly what PR 4 needs to
call ~10^6 times per flop hand to build features:

- `Hand::evaluate` returns a `u16` rank-in-canonical-order via binary
  search into a precomputed `HAND_TABLE: [i32; 4824]`.
- The internal representation packs rankset, per-suit rankset, and
  count-bucket rankset into one i32 (`category << 26 | tiebreakers`).
  This is the standard "Cactus Kev"-style trick; we already have
  equivalent machinery in `poker_solver/evaluator.py`.

### Cited at

- `references/code/postflop-solver/src/hand.rs:53-126` (the evaluator
  itself — `evaluate_internal` returns an i32 that compresses
  category + tiebreaker bits, then `HAND_TABLE.binary_search` maps it
  to a 16-bit rank).
- `references/code/postflop-solver/src/hand_table.rs:1-200+` (the
  precomputed lookup table — 4824 ranks total).
- `references/code/postflop-solver/src/card.rs:183-245`
  (`hand_strength` builder — for every `(board1, board2)` pair valid
  for the current street, build sorted strength vectors per player).

### Non-obvious detail

`hand_strength` lives in `Vec<[Vec<StrengthItem>; 2]>` indexed by
`card_pair_to_index(turn, river)` (a flattened ordered-pair index over
the 52 × 51 / 2 = 1326 possible (turn, river) pairs). This is **not the
same** as the bucket-lookup shape PR 4 needs, but it's the layout PR 6
will inherit if it goes the lossless-river route per `pr4_spec.md` §2.

### PR 4 recommendation

**Adopt the evaluator pattern, build a different feature.** PR 4's
Stage 1 (`pr4_spec.md` §4 Stage 1) builds equity-vs-uniform-opponent
histograms. The fast 7-card evaluator from `Hand::evaluate_internal` is
the inner loop; our Python `poker_solver/evaluator.py` already has an
equivalent. **Do not** copy postflop-solver's `HAND_TABLE` literal —
4824 i32 entries — that's the AGPL trap (verbatim data table). Instead,
regenerate the table via the standard Cactus-Kev / Two-Plus-Two
algorithm at build time, or use our existing evaluator.

---

## 3. K-means or other clustering

### What postflop-solver does

**Nothing. There is no k-means.** No clustering of any kind.
Confirmed by `lib.rs:17` ("The solver does not perform any abstraction")
and by absence of any clustering / nearest-centroid code across the
17 source files.

### What this means for PR 4

For the k-means + EMD pattern itself, the **right** reference is
`references/code/slumbot2019/src/build_kmeans_buckets.cpp` and
`references/code/slumbot2019/src/kmeans.cpp` (MIT-licensed — safe to
port architecturally), per `pr4_spec.md` §3.3. The patterns from
postflop-solver are zero help for the clustering loop itself.

### Cited at

- `references/code/postflop-solver/src/lib.rs:17` (verbatim:
  *"The solver does not perform any abstraction."*)

### PR 4 recommendation

**Look elsewhere.** Use Slumbot's `build_kmeans_buckets.cpp` for the
clustering shape, scipy / scikit-learn for k-means primitives, and the
1-D Wasserstein closed-form (`pr4_spec.md` §4 Stage 2) for distances.

---

## 4. Bucket file format

### What postflop-solver does

No bucket files. The closest analog is the **serialization of
`PostFlopGame`** via `bincode`:

- `src/file.rs` (~378 lines) handles compressed-zstd binary I/O for
  the whole game tree including all per-hand state.
- The on-disk format is a `bincode`-serialized
  `PostFlopGame` struct with optional zstd compression — *not* a
  schema-stable format and *not* designed for partial / random-access
  load.

### Cited at

- `references/code/postflop-solver/src/file.rs:1-50` (the file
  header / version sentinels)
- `references/code/postflop-solver/src/game/serialization.rs:1-200+`
  (the `bincode::Encode` / `bincode::Decode` derives on `PostFlopGame`)
- `references/code/postflop-solver/src/lib.rs:34-48` (crate features —
  `bincode` for serialization, `zstd` for compression — both
  feature-gated).

### Non-obvious detail

The whole file format requires loading the entire tree into RAM at
once. There is no streaming / mmap path. This is fine for postflop
subgame sizes (≤ a few GB) but wouldn't scale to a full game-tree
abstraction — confirming PR 4's choice to use NumPy `.npz` for the
bucket artifact, which *is* mmap-able and partially loadable.

### PR 4 recommendation

**Avoid as a model.** Our `.npz` choice (`pr4_spec.md` §4 Stage 5) is
better suited to the bucket-table use case — partial load, NumPy-native
read, schema-stable. The `bincode`-serialized full-game-tree pattern is
the **wrong** shape for our needs. **Do not** copy file.rs.

---

## 5. Bucket lookup at runtime

### What postflop-solver does

The solver's hot path uses **direct array indexing by private-hand id**,
not bucket lookup. The shape we'd substitute bucket ids into:

- `private_cards[player]: Vec<(Card, Card)>` — one row per
  hole-card combo in that player's range. Lengths typically 1000-1300.
- All per-hand state (`cfreach`, `cfvalues`, strategy, regrets) is a
  parallel `Vec<f32>` of the same length, accessed by row index `i`.
- Showdown reads `hand_strength[card_pair_to_index(turn, river)][player]`
  — a `Vec<StrengthItem>` of `(strength, index)` pairs sorted by
  strength. The sweep is `for &StrengthItem { strength, index } in
  ...` and dereferences `cfreach[index]` and
  `private_cards[player][index]` inside the loop.
- Card removal at showdown uses the inclusion-exclusion trick on
  per-board-card cfreach sums (see Pattern 6).

There is **no hashtable lookup** in the hot path. Everything is array
indexing into pre-allocated `Vec`s. This is the fastest possible
shape: linear scan with monotonic index, contiguous memory, no
pointer chasing.

### What this teaches PR 4

PR 4's Stage 5 lookup (`pr4_spec.md` §4 Stage 4: "a flat array indexed
by `(board_canonical_id * max_hands_per_board) + hand_canonical_id`") is
**aligned with** this pattern: u8 bucket-id array, direct index. The
runtime cost is dominated by the **conversion** from the engine's
`(board: list[Card], hole_cards: tuple[Card,Card])` representation to
the `(board_canonical_id, hand_canonical_id)` index — that's the
function PR 4 must keep tight.

For PR 6's Rust port, the bucket-id substitution is straightforward:
replace `Vec<f32>` of length `num_private_hands(player)` with
`Vec<f32>` of length `K_street` (the bucket count). Card removal
becomes **harder** when both players are bucketed because the
inclusion-exclusion identity in Pattern 6 below relies on knowing the
specific card-pair per row.

### Cited at

- `references/code/postflop-solver/src/game/base.rs:29-31`
  (`num_private_hands(player) = self.private_cards[player].len()` —
  the dimension that PR 6's port must change to bucket count).
- `references/code/postflop-solver/src/game/evaluation.rs:104-124`
  (showdown sweep — two pointers over strength-sorted indices,
  cfreach indexed by `index`).
- `references/code/postflop-solver/src/game/evaluation.rs:28-29`
  (`player_cards = &self.private_cards[player]`, the array used to
  fetch the hole-card pair given a row index).
- `references/code/postflop-solver/src/utility.rs:74-76`
  (`weighted_sum` — the inner product over `num_private_hands`).

### Non-obvious detail

The strength sweep at `game/evaluation.rs:104-124` uses **`get_unchecked`**
(unsafe Rust) — bounds-check elision is load-bearing for hot-path
throughput. Per `lib.rs:13-16`: *"the engine takes full advantage of
unsafe Rust in hot spots"*. PR 6 will need to make the same call
(idiomatic safe Rust vs. measured-correct unsafe at the inner loop).

### PR 4 recommendation

**Adopt the flat-array direct-index pattern for the bucket-id store.**
That's already the spec (`pr4_spec.md` §4 Stage 4 step 3). The lesson
from postflop-solver: do **not** use a `dict[tuple, int]` hashtable for
the runtime lookup — that's 10–100× slower per call than a NumPy `u8`
array indexed directly. PR 4's Python implementation can still expose a
`lookup_bucket(board, hole_cards, street)` Python function, but the
internal table must be a contiguous `np.ndarray[uint8]`.

---

## 6. Card removal / valid_indices in bucket land

### What postflop-solver does (the lossless-cards case)

`valid_indices_*` is a precomputed `Vec<u16>` (per board) listing which
private-hand row indices do **not** conflict with the visible board
cards. Inside the showdown / fold evaluation, the inner loop iterates
only over `valid_indices[player]` — rows with a card-conflict are
skipped without a runtime mask test.

Card removal across the **opponent** is handled via the
**inclusion-exclusion trick**:

- The opponent's reach-sum `cfreach_sum` is computed once over all
  valid opponent rows.
- A 52-entry `cfreach_minus[card]` array accumulates, for each card
  `c`, the total opponent cfreach of rows where one of the hole cards
  equals `c`.
- For each player row `(c1, c2)`, the *effective* opponent cfreach is
  `cfreach_sum - cfreach_minus[c1] - cfreach_minus[c2] +
  cfreach_minus[c1∩c2]` — i.e., subtract the mass of opponent rows
  blocked by `c1`, subtract those blocked by `c2`, *add back* the
  mass double-counted (those blocked by both, which is only the row
  where opponent holds `(c1, c2)` itself — `same_hand_index`).

This is O(N_opp + N_player) instead of O(N_opp × N_player). The
`same_hand_index[player][i]` precomputes "what row in the opponent
range is exactly `(c1, c2)`?" so the double-count correction is
O(1) per player row.

### What this means for bucketed play (the PR 4 problem)

The inclusion-exclusion trick **breaks when hole cards are bucketed**
because the inner loop no longer knows which specific `(c1, c2)`
the player's bucket-row represents. A bucket aggregates many
hole-card combos, each with its own card-conflict pattern.

The standard mitigation in tabular abstraction CFR is:
- **Either** compute per-bucket "average card-removal weight" at
  build time and use it as an approximation (introduces some
  abstraction error — the bucket's hands removal-weight different
  combos differently from the average).
- **Or** keep the per-hand `cfreach` vector at solve time even
  though bucket ids gate the *strategy* lookup (i.e., bucket the
  *infoset key* but not the *probability vector*). This is what
  Slumbot does — buckets index the strategy table, but the per-iteration
  reach probability is still over individual hands. The bucket adds a
  level of indirection: `strategy[infoset_key_with_bucket]` instead of
  `strategy[infoset_key_with_lossless_hand]`.

This is **not yet a PR 4 problem** — `pr4_spec.md` §3.5 specifies that
bucket ids replace the lossless hand prefix in the **infoset key**, and
the solver consuming this is PR 5. But PR 4 must surface this as a
known design tension so PR 5 doesn't get blindsided.

### Cited at

- `references/code/postflop-solver/src/card.rs:106-181`
  (`valid_indices` and `valid_indices_internal` — per-board
  card-removal filter, built at config time).
- `references/code/postflop-solver/src/game/evaluation.rs:42-92`
  (fold evaluation showing the inclusion-exclusion trick — note the
  `cfreach_minus` 52-entry array and the `same_hand_index` lookup at
  line 80).
- `references/code/postflop-solver/src/game/evaluation.rs:118-122`
  (the per-row card-removal correction in the no-rake fast path:
  `cfreach = cfreach_sum - cfreach_minus[c1] - cfreach_minus[c2]`).

### Non-obvious detail

`same_hand_index[player][i] = u16::MAX` is the sentinel for "opponent
range does not contain row i's hole pair." The check at
`game/evaluation.rs:80-86` handles the sentinel before computing the
double-count correction. **A bucketed system cannot have a
single-`u16` `same_hand_index` because a bucket might contain dozens of
combos that match dozens of opponent buckets.**

### PR 4 recommendation

**Flag this as a known unresolved hazard.** PR 4 ships the bucket lookup;
PR 5 consumes it and will face the card-removal-with-bucketing tension.
The recommended escape (per Slumbot's design) is: keep
`(reach, regret, strategy)` vectors at lossless-hand resolution; only
use bucket ids in the **infoset key**. This means the abstraction saves
storage in the **strategy table** (one row per bucket, not per hand) but
not in the per-iteration vectors. PR 5 should validate this on the
profiler. Mention this explicitly in PR 4's deliverables doc so PR 5's
author doesn't re-derive it. Concretely, add a "card-removal hazard"
paragraph to the abstraction.py module docstring.

---

## 7. Memory layout — SoA vs AoS

### What postflop-solver does

The per-hand state layout is **Array-of-Structs at the small scale, Struct-of-Arrays at the large scale**:

- `private_cards[player]: Vec<(Card, Card)>` — AoS for the
  hole-card pair (2 bytes per row).
- `initial_weights[player]: Vec<f32>`, `cfreach`, `cfvalues`,
  `strategy` — each a **separate** `Vec<f32>` of the same length
  (one entry per private-hand row). This is SoA: each per-hand
  "field" is its own contiguous f32 vector. Cache-friendly for SIMD
  fused-multiply-add (`fma_slices`).
- `hand_strength[card_pair_to_index(turn, river)]: [Vec<StrengthItem>; 2]`
  — AoS per row (`StrengthItem` is `{u16, u16}` = 4 bytes). Sorted
  by strength so the showdown sweep is monotonic.

The SoA layout enables the SIMD-friendly ops in `utility.rs`:

- `slice_absolute_max` (utility.rs:79-140) — vectorized horizontal
  max over an f32 slice. Two implementations: wasm32 SIMD128 path
  with explicit `f32x4_*` intrinsics, scalar-but-unrolled fallback.
- `fma_slices`, `sum_slices`, `mul_slice_scalar` — all f32-slice
  ops, all auto-vectorizable on x86 AVX.
- 16-bit encoded slices for compressed storage (`encode_signed_slice`
  at utility.rs:207-215) — uses `slice_absolute_max` to compute the
  scale factor, then `i16::MAX / scale` per entry. The compression
  mode trades 2x storage for an extra scale-factor multiply per
  read.

### Cited at

- `references/code/postflop-solver/src/game/mod.rs:46-50` (the
  `PostFlopGame` field declarations showing
  `private_cards: [Vec<(Card, Card)>; 2]` AoS alongside
  `initial_weights: [Vec<f32>; 2]` SoA).
- `references/code/postflop-solver/src/game/mod.rs:57` (`hand_strength`
  — `Vec<[Vec<StrengthItem>; 2]>` keyed by `card_pair_to_index`).
- `references/code/postflop-solver/src/utility.rs:79-140`
  (`slice_absolute_max` — vectorized horizontal max, AoS-incompatible).
- `references/code/postflop-solver/src/utility.rs:207-228`
  (`encode_signed_slice` / `encode_unsigned_slice` — the i16 / u16
  compressed storage path).
- `references/code/postflop-solver/src/lib.rs:21-24`
  ("Precision: 32-bit floating-point numbers... there is also a
  compression option where each game node stores the values by 16-bit
  integers with a single 32-bit floating-point scaling factor.").

### Non-obvious detail

The compressed mode (16-bit per-value with a single 32-bit scale per
slice) is **lossy by design** but the loss is bounded — about 1 part
in 32768 per stored value. For CFR convergence this is fine; the
exploitability bound is dominated by the abstraction error, not the
floating-point compression error.

PR 4 should note: our bucket-id storage (u8 per (board, hand) entry)
is **not** the same kind of compression. It's a **categorical**
compression with a deliberate-and-known representation collapse.
Postflop-solver's 16-bit compression is a **numerical** compression
preserving the lossless-hand identity. The two layers compose: PR 6
could conceivably ship both — u8 bucket lookup + 16-bit cfvalue
encoding — on top of each other.

### PR 4 recommendation

**Adopt SoA for the per-bucket vectors when PR 6 ports to Rust.**
For PR 4's Python implementation: NumPy arrays are SoA by default,
so this is a non-issue. The takeaway is more for PR 5/6 — when the
solver materializes per-bucket `(regret, cfreach, strategy)` vectors,
each must be its own `np.ndarray` (Python) or `Vec<f32>` (Rust), not
a `Vec<BucketState>` AoS. **Document this in the abstraction.py
module docstring so PR 5 doesn't go AoS by accident.**

---

## Patterns to adopt vs avoid for PR 4

| # | Pattern | PR 4 decision | Rationale |
|---|---------|--------------|-----------|
| 1 | Suit-isomorphism canonicalization | **Defer to PR 6** | `pr4_spec.md` §4 Stage 4 already chose this; design the `board_canonical_id` so suit-iso layer can drop in cleanly |
| 2 | Hand evaluator (`Hand::evaluate`) | **Use ours, don't copy** | Our `poker_solver/evaluator.py` already covers this; AGPL trap is the `HAND_TABLE` literal |
| 3 | K-means / EMD clustering | **Look elsewhere** | postflop-solver has zero clustering code; use Slumbot reference instead |
| 4 | Bucket file format (`bincode` serialization) | **Avoid** | Our NumPy `.npz` is better-suited to the bucket-table use case; postflop-solver's monolithic-tree format is wrong shape |
| 5 | Runtime bucket lookup (flat array, direct index) | **Adopt** | This is the same shape PR 4 already specced; reinforces "no `dict` hashtable in hot path" |
| 6 | Card removal in bucket land | **Surface as a known hazard for PR 5** | The inclusion-exclusion trick *breaks* under hole-card bucketing; mitigation = keep per-hand reach vector even when bucket ids gate strategy lookup |
| 7 | SoA memory layout for per-row state | **Adopt for PR 5/6** | NumPy is SoA by default in Python; PR 6's Rust port must explicitly use parallel `Vec<f32>`s, not `Vec<Struct>` |

---

## Risks of NOT studying these patterns

If we'd re-derived PR 4 from scratch without reading postflop-solver,
we'd likely have gotten the following wrong:

1. **Bucket lookup as `dict[tuple, int]`.** The naïve Python instinct is
   to key by `(board_canonical, hole_canonical)` tuples in a dict. That's
   10–100× slower than the flat `np.ndarray[uint8]` indexed by a
   precomputed integer key. We would have shipped, profiled in PR 5,
   and re-shipped. Reading Pattern 5 surfaces this before we ship.

2. **Lossy bucket-aware card-removal.** The naïve approach to
   "both players bucketed" is to compute opponent reach as `cfreach_sum`
   directly without per-card subtraction. That double-counts blocked
   combos and corrupts both equity and exploitability. Pattern 6
   surfaces the inclusion-exclusion trick that the lossless-hand
   solver uses, and forces us to articulate why bucketed CFR keeps
   *per-hand* reach vectors even when the strategy table is bucketed.
   Without this, PR 5 would likely ship a subtly wrong solver.

3. **Suit-isomorphism baked into the bucket key.** If we had not seen
   postflop-solver's per-chance-node suit-iso layer, we might have
   "helpfully" pre-collapsed suit-equivalent boards in the PR 4 bucket
   key. That would entangle bucket-level abstraction (lossy, PR 4) with
   chance-node-level isomorphism (lossless, PR 6), making PR 6's
   isomorphism layer impossible to add without re-keying the artifact.
   `pr4_spec.md` §4 Stage 4 already gets this right, but reading
   Pattern 1 confirms the choice was correct.

4. **AoS per-bucket state.** A natural Python class
   `class BucketState: reach: float; regret: np.ndarray; strategy:
   np.ndarray; ...` stored as `List[BucketState]` would have been the
   first-pass design. Pattern 7 forces SoA NumPy arrays from day one,
   which is what PR 5/6 vectorization will require anyway.

5. **Skipping the "non-zero cfreach gate" inside the showdown sweep.**
   The hot-path `if cfreach_i != 0.0 { ... }` check (evaluation.rs:108)
   skips rows that are dead from the start of the iteration. Without
   reading the postflop-solver implementation, we'd likely have rolled
   over all rows unconditionally and lost ~20-40% of throughput on
   sparse ranges. PR 5 / PR 6 will need this. PR 4 doesn't directly,
   but should document the optimization so PR 5 knows it exists.

6. **`HAND_TABLE` as a 4824-i32 inline literal.** If we had copied
   postflop-solver's hand evaluator we would have copied this. **This is
   the central AGPL trap of postflop-solver.** Reading-only-for-inspiration
   is the explicit prohibition. We regenerate (or reuse our existing
   evaluator).

---

## Appendix: AGPL traps for the reader of this report

For anyone consuming this report and considering writing code "inspired
by" postflop-solver, the AGPL violations that are easiest to commit
unintentionally:

- **Copying the `HAND_TABLE` literal** (`hand_table.rs`) — this is a
  precomputed numerical data table. Regenerate it; do not copy the
  bytes. The algorithm to generate it (Cactus Kev / category +
  tiebreaker bit-packing) is in `hand.rs:57-126` and is well-described
  in the public literature; the *values* in `HAND_TABLE` are
  AGPL-licensed.
- **Reusing the `card_pair_to_index` formula** (`card.rs:88-93`) — the
  closed-form `card1 * (101 - card1) / 2 + card2 - 1` is a standard
  triangular-number identity and not original to postflop-solver, but
  *copying the function as-written* is a violation. Re-derive: it
  enumerates unordered pairs `(i, j)` with `i < j` over `[0, 52)` in
  lexicographic order; the inverse uses the quadratic formula. PR 4
  needs an analogous index for canonical (turn, river) ordering — we
  derive ours independently.
- **Copying the suit-isomorphism algorithm verbatim** (`card.rs:247-432`)
  — the algorithm shape is described in Pattern 1 above; a from-scratch
  Python or Rust implementation is a few dozen lines and easy. **Do
  not** translate the Rust line-by-line.
- **Copying the showdown two-pointer sweep** (`game/evaluation.rs:104-150`)
  — the inclusion-exclusion identity and the two-pointer strategy are
  algorithm shapes, not code. Re-implement; do not translate.

**Verification path:** before merging any PR 4 / PR 5 / PR 6 code, grep
for distinctive postflop-solver tokens (`StrengthItem`, `cfreach_minus`,
`card_pair_to_index`, `valid_indices_internal`, `isomorphism_swap_internal`)
in our own source tree. Identical names + identical-shape implementation
is the AGPL warning sign. Our names are different by convention (we use
`HandStrength`, `opp_reach_minus`, `pair_index`, etc.); a code search
for the postflop-solver names should return zero hits in our repo.
