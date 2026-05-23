# postflop-solver tree builder — architectural notes
*Read-only study; postflop-solver is AGPL, we cannot copy code.*

Source location studied:
- `/Users/ashen/Desktop/poker_solver/references/code/postflop-solver/src/`
- Files referenced below by `<path>:<line>` (paths relative to `src/`).
- All `:line` citations are to commit on disk at `references/code/postflop-solver/` (last upstream commit: 2023-10-01).
- AGPL-3.0: **do not copy code**. Concepts, file structure, data-flow patterns, and DSL grammars are reproducible from scratch as facts/ideas.

## Summary (3 sentences)

postflop-solver builds the postflop tree in **two layers**: a card-agnostic `ActionTree` (recursive `Box<MutexLike<ActionTreeNode>>`) that encodes the betting structure, then a **flat `Vec<PostFlopNode>` arena** ("`node_arena`") that materializes each `(action, board)` instance using `children_offset: u32` displacements into the same arena and a single global byte arena per role (`storage1`/`storage2`/`storage_ip`/`storage_chance`) that all nodes index into via raw pointers. Chance nodes are **enumerated explicitly** as one child per legal card, with isomorphic suit duplicates removed at *build* time and reapplied via per-suit swap lists at *iterate* time. There is **no card abstraction** — every distinct private hand is tracked explicitly through the tree, so the bucket pipeline is "buckets baked in at build time" reduces to "the private-hand list is built once in `init_hands`/`init_card_fields` and consulted at every action/chance node."

---

## Node representation

### Two distinct node types: `ActionTreeNode` and `PostFlopNode`

**Layer 1 — `ActionTreeNode`** (card-agnostic structure)
`action_tree.rs:151`
```
struct ActionTreeNode {
    player: u8,            // includes PLAYER_TERMINAL_FLAG, PLAYER_CHANCE_FLAG, PLAYER_FOLD_FLAG bits
    board_state: BoardState,
    amount: i32,           // chips committed so far
    actions: Vec<Action>,
    children: Vec<MutexLike<ActionTreeNode>>,
}
```
- Lives in a `Box<MutexLike<ActionTreeNode>>` tree (real recursive heap structure).
- Owned by `ActionTree` (`action_tree.rs:140`) and consumed during `update_config` via `eject()` (`action_tree.rs:382`).
- Purpose: declares the betting tree only; one logical chance node per street regardless of how many cards could be dealt.

**Layer 2 — `PostFlopNode`** (card-instance materialization)
`game/mod.rs:120-139`, `#[repr(C)]`, `#[derive(Debug, Clone, Copy)]`
```
struct PostFlopNode {
    prev_action: Action,        // 8 B (1 disc + 4 i32 payload + 3 pad)
    player: u8,                 // 1
    turn: Card (u8),            // 1
    river: Card (u8),            // 1
    is_locked: bool,            // 1
    amount: i32,                // 4
    children_offset: u32,       // 4   <-- relative arena index to first child
    num_children: u16,          // 2
    num_elements_ip: u16,       // 2
    num_elements: u32,          // 4   <-- num_actions * num_private_hands(player)
    scale1: f32,                // 4
    scale2: f32,                // 4
    scale3: f32,                // 4
    storage1: *mut u8,          // 8   <-- strategy / cfvalues_chance
    storage2: *mut u8,          // 8   <-- regrets or cfvalues
    storage3: *mut u8,          // 8   <-- IP cfvalues
}
```
- Approximate sizeof: **64 bytes** on 64-bit (`repr(C)`, fields in declared order; the trailing three `*mut u8` align to 8 cleanly).
- The hard size guard at `game/base.rs:528` is `size_of::<PostFlopNode>() * total_num_nodes <= isize::MAX`.
- Nodes are stored as `Vec<MutexLike<PostFlopNode>>` (where `MutexLike` is `repr(transparent)` over `UnsafeCell<T>`, so memory-layout-identical to `Vec<PostFlopNode>` — see `mutex_like.rs:22`).

### Storage trick: child access via arena offset

`game/node.rs:233-243`:
```
fn children(&self) -> &[MutexLike<Self>] {
    let self_ptr = self as *const _ as *const MutexLike<PostFlopNode>;
    unsafe {
        slice::from_raw_parts(
            self_ptr.add(self.children_offset as usize),
            self.num_children as usize,
        )
    }
}
```
- Children are addressed by **offset from `self`** (not absolute index, and not pointer). This makes the whole `node_arena` relocatable.
- Cap on tree size: `total_num_nodes <= u32::MAX` because `children_offset: u32`.

### Action storage is *implicit* — encoded by child position
- `PostFlopNode` has **no `Vec<Action>`** — actions are not stored on the postflop node.
- Each child node's `prev_action` (set in `push_chances`/`push_actions`) encodes "the action that led here." So action menu = `(0..node.num_children).map(|i| children()[i].prev_action)`.
- Reverse lookup (e.g., "find child for action X") = `binary_search_by(|child| child.lock().prev_action.cmp(&action))` (`game/base.rs:1367`).

### Strategy/regret storage is *external* (split-arena pattern)
- Each `PostFlopNode` holds three raw pointers (`storage1/2/3`) into four global `Vec<u8>` arenas owned by `PostFlopGame`: `storage1`, `storage2`, `storage_ip`, `storage_chance` (`game/mod.rs:96-99`).
- Allocated in one big shot in `allocate_memory_nodes` (`game/base.rs:1420-1449`) by sweeping `node_arena` and assigning `node.storage{1,2,3} = base_ptr.add(running_counter)`.
- This means **strategy, regrets, and CFVs for the entire tree are 4 contiguous byte arenas** — extremely cache-friendly for vector ops, trivially memcpy-able for serialization, and lets compression switch (`u8 = 2 vs 4 bytes per entry`) be a single allocation-size decision.

### Terminal/chance/player encoding via bit flags
`action_tree.rs:8-14`:
```
PLAYER_OOP           = 0
PLAYER_IP            = 1
PLAYER_CHANCE        = 2
PLAYER_MASK          = 3
PLAYER_CHANCE_FLAG   = 4    // chance node: player = PLAYER_CHANCE_FLAG | prev_player
PLAYER_TERMINAL_FLAG = 8
PLAYER_FOLD_FLAG     = 24   // 8 | 16 — terminal that also is a fold (= folding player encoded in low bits)
```
- All node-kind queries are bit tests (`game/node.rs:7-15`): `is_terminal() = player & 8 != 0`, `is_chance() = player & 4 != 0`.
- `cfvalue_storage_player()` (`game/node.rs:17-26`): chance nodes store CFVs for the *previous* (non-chance) player; encoded by stripping the chance flag and inverting (so the prev-player computes its CFVs at chance time).

### Memory footprint (per-node)
- `PostFlopNode`: ~64 B node struct.
- External storage per **action node**: `num_actions * num_private_hands(player) * 4 B` for strategy + same for regrets + (if first action in street) `num_private_hands(IP) * 4 B` for IP CFVs. Halved with compression.
- External storage per **chance node**: `num_private_hands(prev_player) * 4 B` (or 0 if no prev player — e.g., root of flop tree).

---

## Action abstraction

### `BetSize` enum + `BetSizeOptions` DSL
`bet_size.rs:42-81`:
```
struct BetSizeOptions { bet: Vec<BetSize>, raise: Vec<BetSize> }

enum BetSize {
    PotRelative(f64),            // "70%"
    PrevBetRelative(f64),        // "2.5x" — raise-only, must be > 1.0
    Additive(i32, i32),          // "100c" or "20c3r"  (constant adder, raise cap)
    Geometric(i32, f64),         // "3e200%" — N streets, max ratio of pot
    AllIn,                       // "a"
}
```
- Parser at `bet_size.rs:152-251` (`bet_size_from_str`): suffix-driven (`x`/`c`/`e`/`%`/`a`).
- Donk sizes are a separate struct (`DonkSizeOptions`) but use the same `BetSize` enum (no raises).
- Sizes are stored **sorted ascending** by `partial_cmp` (`bet_size.rs:112-113`).

### Per-street / per-context storage in `TreeConfig`
`action_tree.rs:82-134`:
```
struct TreeConfig {
    initial_state, starting_pot, effective_stack,
    rake_rate, rake_cap,
    flop_bet_sizes:  [BetSizeOptions; 2],   // [OOP, IP]
    turn_bet_sizes:  [BetSizeOptions; 2],
    river_bet_sizes: [BetSizeOptions; 2],
    turn_donk_sizes:  Option<DonkSizeOptions>,
    river_donk_sizes: Option<DonkSizeOptions>,
    add_allin_threshold: f64,      // add all-in if max_bet/pot <= threshold
    force_allin_threshold: f64,    // replace bet with all-in if SPR-after-call <= threshold
    merging_threshold: f64,        // PioSOLVER-style sibling-bet merging
}
```
- Differs per street (flop/turn/river) and per player (OOP/IP) and per context (donk vs cbet vs raise).
- Geometric sizes default to `streets-remaining` (`3e` flop, `2e` turn, `1e≡a` river) when `Geometric(0, _)` is used (`bet_size.rs:14-19`, `action_tree.rs:540-543`).

### Action menu generation (`push_actions`)
`action_tree.rs:526-740`:
1. Compute `pot`, `min_amount`, `max_amount`, `to_call`, `spr_after_call`.
2. Build the menu based on context:
   - **Donk position** (`oop_call_flag && prev_action is Chance`): Check + per-donk-size Bet(amount) + optional all-in (if `add_allin_threshold` exceeded).
   - **First-to-act or after Check/Chance**: Check + per-bet-size Bet(amount) + optional all-in.
   - **Facing a bet/raise**: Fold + Call + (if `!allin_flag`) per-raise-size Raise(amount) + optional all-in.
3. Compute concrete chip amounts per `BetSize` variant (`action_tree.rs:597-664`).
4. **Clamp to `[min_amount, max_amount]`** (`action_tree.rs:673-693`). Bets that clamp to max become `AllIn(max_amount)`. Bets above `force_allin_threshold * new_pot` also collapse to all-in.
5. `actions.sort_unstable(); actions.dedup();` (`action_tree.rs:695-697`) — duplicates from clamping/all-in collapse are removed by sorting + dedup.
6. **Merge close sizes** (`merge_bet_actions`, `action_tree.rs:1067-1095`): iterating from largest, drop any smaller size whose ratio (relative to current largest) is below the merging threshold. PioSOLVER-compatible algorithm.

### Action enum is `Bet(i32) / Raise(i32) / AllIn(i32)` with concrete chip amounts
`action_tree.rs:19-44` — the chip amount is baked into the action variant, not symbolic ("pot-3x") — much easier to debug and equality-check.

---

## Raise cap

There is no single configurable "max-raises-per-street" — raise containment is achieved through **four converging mechanisms**, all enforced at *tree-build* time (not runtime):

1. **Stack constraint (the universal cap).** Bet amounts are clamped to `max_amount = opponent_stack + prev_amount` (`action_tree.rs:536`). Once a raise equals max_amount it is rewritten as `Action::AllIn(...)`. Subsequent action menus check `info.allin_flag` and stop offering raises (`action_tree.rs:628`).

2. **`Additive(adder, raise_cap)` size's per-size cap.** A constant raise like `20c3r` (used for FLHE) carries its own raise cap; `action_tree.rs:640-644` checks `info.num_bets <= raise_cap` before emitting it. `num_bets` is tracked in `BuildTreeInfo` and reset to 0 on every call (`action_tree.rs:1015`).

3. **`add_allin_threshold` + `force_allin_threshold`** collapse "tiny remaining stack" into a single all-in option, preventing absurdly small bets being treated as new raises (`action_tree.rs:664-693`).

4. **`merging_threshold`** removes near-duplicate sibling bets so the menu doesn't bloat from clamping (`action_tree.rs:700`, `1067-1095`).

**Key insight:** the tree is *fully expanded at build* with no per-runtime cap check. The combination "raise actions clamp to stack → eventually become all-in → all-in nodes stop offering raises" provides natural finite termination. There's **no `max_raises_per_street` knob anywhere**.

The author also exposes manual editing via `add_line()`/`remove_line()` (`action_tree.rs:222-264`) for fine-tuning specific lines after auto-build — also a build-time mechanism.

---

## Chance nodes

### Enumerated explicitly, one child per legal card
`game/base.rs:712-759`:
- Turn chance node: iterate `card` in `0..52`, skip cards in flop mask and isomorphism-skip mask, push one `PostFlopNode` per surviving card. `child.prev_action = Action::Chance(card); child.turn = card;`.
- River chance node: same idea but skip flop + turn + per-turn isomorphism-skip mask.

So a flop chance node typically has **(49 - |iso_skip_turn|)** children (49 = 52 - 3 flop cards), and each turn chance node has **(48 - |iso_skip_river_for_this_turn|)** children. That's a lot of branching.

### Isomorphic suit reduction
`card.rs:247-361` (`CardConfig::isomorphism`): at build time, examines (a) flop rank-sets per suit and (b) per-player range suit-isomorphism (`range.rs::is_suit_isomorphic`). If two suits have identical flop rank-sets *and* both player ranges are symmetric in those suits, one suit is marked "isomorphic to" another. Produces:
- `isomorphism_card_turn`: cards skipped at turn (Vec<Card>).
- `isomorphism_ref_turn`: for each skipped card, the index of the canonical child it refers to (Vec<u8>).
- `isomorphism_swap_turn[suit]`: per-player list of `(hand_index, hand_index)` pairs to swap when applying the isomorphism (4 suits × 2 players).
- Same per-turn for river (`isomorphism_ref_river: Vec<Vec<u8>>` indexed by turn card).

At iterate time (`solver.rs:204-219`), after computing the canonical CFV, each isomorphic chance: `apply_swap(tmp, swap_list); accumulate into result; apply_swap(tmp, swap_list);` — i.e., swap private-hand vector indices in-place, add to total, swap back. The double-swap leaves storage untouched.

**Concrete example** from author's docs: monotone flop on 3 cards of suit S = 3 of the 4 turn suits are isomorphic to one canonical → ~75% reduction in turn chance branching. Big win.

### Chance node has its own external storage
`game/base.rs:754-758`:
```
node.num_elements = node
    .cfvalue_storage_player()
    .map_or(0, |player| self.num_private_hands(player)) as u32;
info.num_storage_chance += node.num_elements as u64;
```
- Chance nodes store CFVs for the **previous player** (not action probabilities — there's nothing to choose for the chance "player").
- Uses `storage1` pointer into the global `storage_chance` arena (separate from `storage1`/`storage2` action-arenas).

### `chance_factor` = number of unrevealed deck cards
`game/base.rs:54-60`:
- Turn chance: `45 - bunching_num_dead_cards` (52 - 3 flop - 2 hero cards - 2 opp cards = 45).
- River chance: `44 - bunching_num_dead_cards` (one more card removed).
- Bunching cards (cards held by folded players in 6-max) decrement this factor.

Applied at `solver.rs:173-178` as a uniform `1.0 / chance_factor` scalar on the reach probabilities at the chance node — i.e., uniform prior over remaining unseen cards.

---

## Card abstraction integration

**postflop-solver uses NO card abstraction.** Every distinct `(c1, c2)` private hand combination with non-zero range weight is tracked individually:

- `private_cards: [Vec<(Card, Card)>; 2]` (`game/mod.rs:48`) — per-player list of allowed hole-card combos (filtered against board cards via `Range::get_hands_weights` at `game/base.rs:480-484`).
- `initial_weights: [Vec<f32>; 2]` — per-hand initial reach prob.
- Each action node's `num_elements = num_actions * num_private_hands(player)` (`game/base.rs:793-794`). So the strategy slab has one f32 per (action, hand) pair.
- Each chance node holds one f32 per opponent hand (`game/base.rs:754-758`).

**Hand-strength precomputation** (the closest thing to "abstraction"): `card.rs:183-245` (`hand_strength`):
- For every possible (turn, river) board pair, evaluates each hero hand using the 7-card lookup (`hand.rs` + `hand_table.rs`).
- Sorts hands by strength and stores sentinels (weakest 0 and strongest `u16::MAX`) for fast cumulative-sum-with-blockers tricks at terminals.
- Per-board: ~1326 hands × `u16 strength` + `u16 index` = 4 KB × 52*51/2 = ~3.4 MB per (turn,river) board, but only board pairs reachable from the flop are populated (`card.rs:194-201`).

**`valid_indices_{flop,turn,river}`** (`card.rs:106-145`): per-board lists of which private-hand indices don't conflict with the board cards (i.e., aren't blocked by the public cards). Used to skip evaluation/regret-updates for hands that don't exist on a given board.

### Pipeline
1. Parse ranges (`range.rs`) → bitmask-encoded `Range` with `is_suit_isomorphic`.
2. `init_hands` → `private_cards[player]` and `initial_weights[player]`.
3. `init_card_fields` → `same_hand_index`, `valid_indices_*`, `hand_strength`, isomorphism tables.
4. `init_root` → calls `count_num_nodes` then allocates `node_arena: Vec<MutexLike<PostFlopNode>>` flat.
5. `build_tree_recursive` walks the `action_root` (Layer 1) and materializes nodes into the arena (Layer 2), filling `prev_action`, `turn`, `river`, `children_offset`, `num_children`, `num_elements`.
6. `allocate_memory(enable_compression)` → allocate 4 byte arenas + sweep nodes to assign `storage{1,2,3}`.

So in our terms: **the "buckets" (here = individual hands) are baked in at build time as the per-player private-card vector — same indices used everywhere downstream.**

---

## Memory optimization

### 1. Flat `Vec<PostFlopNode>` arena with `u32` children offsets
- Total tree fits in one contiguous allocation; node-id is just an arena index.
- Children addressed by 4-byte offset from self (`game/node.rs:233-243`), not 8-byte pointer.
- Iteration order during build (`game/base.rs:589-615` `count_num_nodes`) ensures children appear *after* parents in the arena.

### 2. Three external split arenas (`storage1`, `storage2`, `storage_ip`, `storage_chance`)
- All strategy floats live in one byte arena (`storage1`); all regrets in another (`storage2`); IP CFVs in another (`storage_ip`); chance CFVs in a fourth (`storage_chance`).
- Nodes hold raw `*mut u8` pointers into these (`game/mod.rs:136-138`).
- `Vec<u8>` is convenient because the same arena holds either `f32`s or `i16`s depending on compression mode — `node.num_bytes() * node.num_elements` is the per-node slice length.

### 3. Optional 16-bit compression
`solver.rs:255-299`, `game/node.rs:100-148`:
- Strategy stored as `u16` with per-node f32 `scale1`.
- Regrets stored as `i16` with per-node f32 `scale2`.
- IP CFVs as `i16` with per-node f32 `scale3`.
- Encode/decode lives in `utility.rs::encode_signed_slice` / `encode_unsigned_slice`.
- Halves the four big arenas. Toggle on a per-`PostFlopGame` basis via `allocate_memory(true)`.

### 4. Storage-mode pruning
`game/serialization.rs:62-100` (`num_target_storage`): can save just the CFVs computed up to a chosen street, dropping deeper detail — used for partial saves.

### 5. Repr(C) on `PostFlopNode`, `repr(transparent)` on `MutexLike`
- Predictable layout + no wrapper overhead. `MutexLike<T>` has the same size and alignment as `T`.

### 6. Action enum reuses 8 bytes for all variants
- `Action::Bet(i32) | Raise(i32) | AllIn(i32) | Chance(u8) | Fold | Check | Call | None` all fit in 8 bytes (1 disc + 4 payload + 3 pad). Stored in node by-value.

### 7. `same_hand_index: Vec<u16>` (per-player)
- For each of my hands, the opponent's index of the **same** hand if it appears in their range (`game/base.rs:488-502`). Used at showdown evaluation to skip the "we hold the same card combo" case without an O(N) scan.

### 8. `bunching_arena: Vec<f32>` (when bunching effect enabled)
- Single shared f32 arena indexed by precomputed `bunching_num_*` index vectors per board (`game/base.rs:835-987`). Same pattern as the strategy arena.

### 9. Custom stack allocator (nightly-only feature)
`alloc.rs`:
- `StackAlloc` allocates from thread-local 1MB chunks in a stack-like push/pop pattern (`alloc.rs:25-101`).
- Used at `solver.rs:162, 170, 194` for the per-recurse `cfv_actions`, `cfreach_updated`, `result_f64` buffers.
- Sidesteps the default allocator for hot recursion. Assumes only one solver instance running at a time.

### 10. `MaybeUninit` + `set_len` for spare capacity
- Avoid zero-init for slice scratch buffers (`solver.rs:177, 178, 200`, `sliceop.rs::sum_slices_f64_uninit`, etc.). Heavy use of `unsafe` for SIMD-friendly inner loops.

---

## Tree-build cost

postflop-solver's tree-build is **cheap relative to solve time**, but only after you've paid for the substantial per-board precomputations.

### Build sequence (`game/base.rs::update_config` → `init_root`)
1. `check_card_config` + `init_hands` — O(num_hands_OOP * num_hands_IP) for the `num_combinations` computation (`game/base.rs:442-456`). For full ranges ~1326 × 1326 = 1.76M pair checks.
2. `init_card_fields`:
   - `same_hand_index` — O(num_hands log num_hands), trivial.
   - `valid_indices(flop, turn, river)` — iterates 52 turn cards + ~1326 river card-pairs, per-board scanning ~1326 hands. ~70k–1.7M ops.
   - **`hand_strength`** — for each reachable `(turn, river)` board (up to ~52*51/2 ≈ 1326 pairs), evaluate ~1326 hands per player using the 7-card lookup table. This is the **dominant precompute cost**: ~3.5M lookups + 3.5M sorts.
   - `isomorphism` — fast, just suit-pair checks.
3. `count_num_nodes` — recursive walk of `action_root`, O(num_action_nodes). Negligible.
4. `node_arena` allocation — single `Vec::with_capacity(N)` of ~64-byte slots. For a `60%, e, a` × `2.5x` HUNL tree on flop-turn-river with full ranges, this is typically tens to low-hundreds of millions of `PostFlopNode`s (gigabytes of nodes).
5. `build_tree_recursive` — walks `action_root` once, materializing one `PostFlopNode` per (action_node, board_instance). O(total_num_nodes).
6. `allocate_memory(enable_compression)` — allocates 4 `Vec<u8>` and sweeps `node_arena` once to set pointers. O(total_num_nodes) plus a single big allocation.

### Order-of-magnitude expectations
From `examples/basic.rs` (Td9d6h flop, Qc turn, full ranges, `60%, e, a` cbets, `2.5x` raises, donk 50% on river):
- Build is **seconds**.
- Solve to 0.5%-pot exploitability over 1000 iterations is **minutes** on a desktop CPU (per the author's docs/CHANGES).
- `memory_usage()` printed in `examples/basic.rs:51-58` is typically several GB uncompressed for full-range turn trees.

From `game/tests.rs:1148-1198` (flop-only Qs Jh 2h, ~50% pot bets, ~45% raises, 1000-iter to 0.1%-pot exploitability): also marked `#[ignore]` (i.e., slow), but builds and solves cleanly.

### Build:solve ratio
The build itself is **a tiny fraction of total work** — most cost is in the per-iteration tree-walk (the solver's `solve_recursive`). Authors don't profile build separately because it's noise. The expensive build-time step is `hand_strength` precompute, not the tree-walk itself.

### What does NOT happen at build time
- No regret/strategy initialization (those are inside the four big byte arenas, zero-initialized via `vec![0; storage_bytes]` at `game/base.rs:345-348`).
- No solver-state copy (storage is initialized once and modified in-place by `solve`).

---

## Patterns we should adopt

- **Two-layer tree: card-agnostic `ActionTree` + card-aware materialized arena.** Lets us edit the betting structure (`add_line` / `remove_line`) before paying the cost of materializing N copies of each subtree per board. This is the right separation of concerns for HUNL postflop. (`action_tree.rs:140-147`, `game/base.rs:678-709`.)

- **Flat `Vec<Node>` arena with relative offset children (`children_offset: u32`).** This is the canonical CFR tree representation — cache-friendly, single allocation, easy to serialize. Use a `u32` offset (4 B) not a `usize`/pointer (8 B) and keep it relative to the parent so the arena is relocatable.

- **External "split" storage arenas keyed by node-via-pointer.** All strategy floats in one big `Vec<u8>` (or `Vec<f32>`/`Vec<f32>`), regrets in another, CFVs/IP in others. Per-node pointer is just `base.add(running_counter)`. Massive cache wins, halves on memory map/save, lets compression be a build-time flag rather than a code path.

- **Bit-flag encoding for terminal/chance/player kind** (`player & PLAYER_TERMINAL_FLAG`, `player & PLAYER_CHANCE_FLAG`). One u8 holds everything, zero-branch checks at hot path. (`action_tree.rs:8-14`, `game/node.rs:7-15`.)

- **Action stored on the child as `prev_action`, not on the parent as `Vec<Action>`.** Saves a heap allocation per action node and lets binary-search by action work directly on children sorted by prev_action. (`game/base.rs:786-791`, `1364-1367`.)

- **Bet-size DSL grammar** (`60%, e, a` for bets; `2.5x` for raises; `100c3r` for additive + raise cap; `Xe` geometric). This is the de-facto industry syntax — adopt the same grammar (which is functional fact, not expressive copyright) for interop with PioSOLVER/GTO+ users. (`bet_size.rs`.)

- **All bet/raise amounts clamp to `[min_amount, max_amount]` then collapse-to-`AllIn` if at max.** Eliminates a whole class of bugs from "bet exceeds stack" and naturally caps the raise ladder. (`action_tree.rs:673-693`.)

- **Per-street, per-player, per-context bet-size menus.** Different sizes for flop vs turn vs river, OOP vs IP, and a separate `DonkSizeOptions` for the donk-bet context. Critical for realistic solves. (`action_tree.rs:101-113`.)

- **`merge_bet_actions` sibling-bet merging.** Same as PioSOLVER: walking from largest, drop any smaller bet whose ratio (vs cur) is below threshold. Prevents 4-5 sibling bets blowing up the tree. (`action_tree.rs:1067-1095`.)

- **Isomorphic chance reduction at build time, swap-list replay at iterate time.** Significant runtime win on monotone/paired boards. Build-time cost is just suit-pair comparisons + per-suit hand-pair swap-list precompute. Plan this in from day one — it's painful to retrofit. (`card.rs:247-433`, `solver.rs:204-219`.)

- **Optional 16-bit compression** with per-node `f32` scale factor, toggleable at `allocate_memory(true)`. Halves memory at the cost of a small amount of code duplication in the hot path. Defer to "later" but design the storage API to make this a flag. (`solver.rs:255-299`.)

- **`Game` / `GameNode` trait split in `interface.rs`.** Decouples the solver from the game representation; lets us unit-test the CFR engine on Kuhn/Leduc and trust it for HUNL. (`interface.rs`.)

- **Per-thread `StackAlloc` for hot recursion buffers.** Sidesteps default-allocator contention. Defer to a `nightly` feature if needed. (`alloc.rs`.)

- **`MaybeUninit` + `set_len` for SIMD-friendly inner loops** in slice operations. Avoid zero-init when we'll overwrite immediately. Keep the unsafe contained to a `sliceop.rs`-style module. (`sliceop.rs`.)

- **Precomputed `valid_indices` and `hand_strength` keyed by `card_pair_to_index(b1, b2)`.** Fast index-into-Vec lookup at every (turn, river) board. (`card.rs:106-245`.)

---

## Patterns we should NOT adopt (and why)

- **AGPL-3.0 source code, verbatim.** Cannot copy a single line. We must re-derive every concept above from public knowledge (paper algorithms, standard data-structure patterns, our own grammar parser).

- **`MutexLike`-as-`UnsafeCell` "lock-free pseudo-mutex".** Author explicitly says "extremely unsafe" (`mutex_like.rs:18-20`). We should use proper `Mutex`/`RwLock`/`AtomicCell` or, better, a single-writer iteration model that doesn't need any wrapper. Premature pessimization of safety for ≤1% perf gain.

- **Raw `*mut u8` pointer-into-arena for storage.** `node.storage1 = base.add(offset)` requires that the `Vec<u8>` arena never reallocates (it doesn't, because allocated once). We can get the same memory layout via a typed `Vec<f32>` storage + per-node `(start, len)` index pair without any unsafe. Slightly more bookkeeping; vastly safer.

- **`heavy unsafe` for `set_len` / `slice::from_raw_parts_mut` everywhere.** Hot-path SIMD slices are reasonable, but the API surface should not expose raw `from_raw_parts_mut` on every getter (`game/node.rs:43-149`). Wrap unsafe inside safe abstractions; the perf delta from a bounds-checked-but-elided-after-inlining `&[f32]` is usually zero.

- **`State` enum gates** (`State::ConfigError → Uninitialized → TreeBuilt → MemoryAllocated → Solved`, `game/mod.rs:23-30`). Manual state machine spread across many methods that panic if state is wrong. A type-state design (e.g., `PostFlopGame<Building>` → `PostFlopGame<MemoryAllocated>` → `PostFlopGame<Solved>`) is cleaner in Rust.

- **`add_line` / `remove_line` mutation API.** Powerful but error-prone — users have reported many sharp edges (per `_NOTES.md`). For PR 3 we should fully build the action tree from declarative config and require recompilation for any change. Add post-build edits later only if user-demand is clear.

- **DCFR-only (no CFR+, no vanilla CFR).** Hardcoding DCFR with custom γ=3 + power-of-4 reset is a strong choice that the author *publicly says* "deviates from the paper" (README:48-51). We should leave the variant pluggable so we can A/B vs CFR+ for our internal benchmarks.

- **Configurable raise-cap by stack-only (no `max_raises_per_street` knob).** Stack-only termination is correct for HUNL deep-stack but a per-street cap is a useful knob for limit-style or rake-cap testing. We should expose both.

- **Bunching effect implementation.** The author's bunching effect is famously slow (`O(N²)` evaluation at terminals, README:62-64). Probably not needed for HUNL — skip entirely from v0.

- **One-instance-only custom allocator.** `StackAlloc` thread-locals and assumed-single-game design make multi-game/multi-thread benchmarking awkward. Either use the global allocator or use a normal `bumpalo::Bump`-style arena passed by handle.

- **Mixing chance/action node logic in the same `PostFlopNode` struct (with three `storage{1,2,3}` pointers that mean different things).** Different node kinds have different storage needs — separating them into `enum NodeData { Chance { ... }, Action { ... }, Terminal }` is much cleaner Rust, even if it costs a tag byte per node.

- **Author's repo officially suspended (Oct 2023).** Treat as a frozen snapshot — no upstream patches, no community evolution. We have to maintain whatever we adopt.

---

## Open questions for the user / for follow-up research

1. **Bucket abstraction (PR 3 main feature) integration**: postflop-solver has none. If our PR 3 introduces a card-bucket abstraction (e.g., k-means on EHS, or hand-strength quantiles), we need to decide whether buckets are computed *before* `init_card_fields` (one strategy slot per bucket-pair) or *inside* the per-hand vectors (a soft-bucket weighting). The first is closer to LP-style abstractions, the second to "no-abstraction-but-grouped-equity." postflop-solver is firmly the latter (full hand vector). Which approach are we targeting for PR 3?

2. **Tree-build hot-paths to benchmark**: postflop-solver's expensive precompute is `hand_strength` (per-(turn,river)-board 7-card eval + sort). If we ship abstraction, our equivalent would be the bucket-table lookup at terminals — what's our terminal evaluation cost target?

3. **Action-tree edit semantics**: do we need `add_line`/`remove_line` post-build, or is build-from-config-only acceptable for v0?

4. **Compression at the f16 / int16 level**: postflop-solver does i16+scale. PR 3 may want bf16 (Rust support is improving) — worth a quick comparison.

5. **Multi-board / per-board solving**: postflop-solver solves one specific flop at a time. Our PR 3 likely intends a flop-class precomputed model; how do we slot multiple flops into the same arena, or do we re-build per flop and stitch via the abstraction?

6. **Rake support**: postflop-solver has `rake_rate` + `rake_cap` baked into terminals (`action_tree.rs:94-98`). Is that on our PR 3 roadmap?

7. **Memory budget for v0**: postflop-solver's `examples/basic.rs` `60%, e, a / 2.5x` Td9d6h Qc turn tree with full ranges is several GB. Our PR 3 targets — single-machine RAM-cap, or do we plan a disk-spilling design from the start?

8. **`StackAlloc` and `MaybeUninit::set_len` patterns**: do we accept `unsafe` blocks in the hot path for ~10–30% perf gain, or do we constrain ourselves to safe Rust + benchmarking-driven exceptions?

9. **`Game` / `GameNode` trait split**: should our PR 3 expose a similar trait so we can unit-test CFR on Kuhn/Leduc independently of the HUNL game, or wire HUNL-specific logic directly into the solver?

10. **Bet-size DSL grammar**: adopt postflop-solver/PioSOLVER syntax verbatim for user interop, or design our own? The grammar itself (suffix-based parsing) is uncopyrightable but the specific token choices (`%/x/c/e/a`) are de-facto industry standard — worth adopting.
