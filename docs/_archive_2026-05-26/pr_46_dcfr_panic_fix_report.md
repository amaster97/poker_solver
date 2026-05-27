# PR 46: Re-apply PR 34 P0 fix for `dcfr_vector.rs:651` panic

**Branch**: `pr-46-dcfr-panic-fix`
**Worktree**: `/tmp/dcfr_panic_repro_66023` (kept; not removed pending review)
**Base SHA**: `94007ca` (origin/main, v1.6.0 docs refresh)
**Commit SHA**: `cd56761f867815cb69f48e9d3bf815e9c28539e0`
**Date**: 2026-05-23
**Reporter agent**: PR 46 executor

---

## Verdict

**FIXED.** The dcfr_vector.rs:651 index-out-of-bounds panic no longer
reproduces on the asymmetric A83 range case. Both
`test_v1_5_brown_apples_to_apples_parity` parametrizations
(K72 + A83) now run to completion under `pytest --timeout=600`.

They still fail the 80% coverage threshold (K72 53.3%, A83 66.7%) —
but that is the next-layer tree-shape divergence already documented in
the Path A report (`docs/pr_35c_paired_fix_report.md` §"A83 spot test"
+ §"Recommended Next Step"), **not** a panic. The P0 panic is gone.

---

## Reproduction (before fix)

```
git -C /Users/ashen/Desktop/poker_solver worktree add \
    /tmp/dcfr_panic_repro_66023 origin/main
# HEAD = 94007ca docs: refresh README to v1.5.x ...

cd /tmp/dcfr_panic_repro_66023
python -m venv .venv
.venv/bin/pip install maturin numpy psutil pytest pytest-timeout
source .venv/bin/activate
export PATH="/Users/ashen/.cargo/bin:$PATH"
maturin develop --release

# Symlink Brown's binary so the test isn't skipped:
mkdir -p references/code/noambrown_poker_solver/cpp/build
ln -s /Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized \
      references/code/noambrown_poker_solver/cpp/build/river_solver_optimized

RUST_BACKTRACE=1 pytest tests/test_v1_5_brown_apples_to_apples.py \
    -v -k A83 --timeout=300
```

### Captured panic (pre-fix)

```
thread '<unnamed>' (30980033) panicked at crates/cfr_core/src/dcfr_vector.rs:651:22:
index out of bounds: the len is 49 but the index is 49
stack backtrace:
   0: __rustc::rust_begin_unwind
   1: core::panicking::panic_fmt
   2: core::panicking::panic_bounds_check
   3: cfr_core::dcfr_vector::VectorDCFR::traverse
   4: cfr_core::dcfr_vector::VectorDCFR::traverse
   5: cfr_core::dcfr_vector::VectorDCFR::traverse
   6: pyo3::marker::Python::allow_threads
   7: cfr_core::solve_range_vs_range_rust
   8: cfr_core::__pyfunction_solve_range_vs_range_rust
   ...
```

### Input parameters at panic
* Spot: `dry_A83_rainbow` (asymmetric: P0=49 hands, P1=50 hands)
* Board: A♣ 8♦ 3♥ (rainbow river)
* Tree: vector-form DCFR over the river subgame
* Trigger: `solve_range_vs_range_rust` is called with a config whose
  `hand_count[0] != hand_count[1]`; the panic fires deep in the
  recursion at the first terminal-leaf hit on the opponent-node
  branch.

---

## Diagnosis

### Is PR 34's fix actually on origin/main?

**No.** `git log origin/main --oneline -- crates/cfr_core/src/dcfr_vector.rs`
shows only three commits, all from PR 23:

```
bfcfa3b PR 23: per-street memory profiler (spec §4)
4664112 PR 23: differential test (exploitability metric) + hand-list extension
0026390 PR 23: vector-form DCFR module (Brown's trainer.cpp pattern, MIT)
```

PR 34's three duplicate commits (`bf178c8`, `4aa2723`, `0bafcfa` —
all titled *"PR 34: Fix off-by-one panic at dcfr_vector.rs:651
(PR 23 P0)"*) only exist on `v1-6-1-staging-verify`, a local-only
integration branch.

`git branch --contains bf178c8` confirms:
```
v1-6-1-staging-verify
```
— only one branch, and it's local, not on `origin`.

**Conclusion**: Task #198's "fixed by PR 34" status was almost
certainly a mis-reading of the local integration branch. The fix was
authored, but never merged to `origin/main`. The Path A agent's
A83 testing on `origin/main` correctly observed the panic
still reproducing.

### Root cause (unchanged from PR 34's diagnosis)

In `VectorDCFR::traverse` (`crates/cfr_core/src/dcfr_vector.rs:338-378`),
the opponent-node branch builds `next_reach` for recursion into
children. Pre-fix it was sized by:

```rust
let opp_player = 1 - player;
let opp_hands  = eval_ctx.hand_count[opp_player];  // = hand_count[update_player]
...
let mut next_reach = vec![0.0_f64; opp_hands];
for h in 0..opp_hands { next_reach[h] = reach_opp[h] * strategy[h * action_count + a]; }
```

But at this point `reach_opp` is indexed by the *current player*'s
hand axis (the non-update player). Its actual length is
`player_hands = hand_count[player]`.

* `player`           = the node's current actor (here ≠ update_player)
* `1 - player`       = update_player
* `hand_count[1-player]` = update_player's hand count
* `reach_opp` is the opponent of `update_player` = `player`, so
  its length is `hand_count[player] = player_hands`.

For **symmetric** ranges (e.g. dry_K72 with 55 vs 55) the two sizes
are equal — bug silently invisible.
For **asymmetric** ranges (e.g. dry_A83 with 49 vs 50) the loop walks
one past the end of `reach_opp` and `strategy`. The wrong-sized
`next_reach` propagates down the tree until it reaches a terminal
leaf, where `terminal_value_vector` (line 651) panics on
`reach_opp[ho]`.

### Reference parity

Brown's `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:170-173`:
```cpp
const int opp_hands = info_const.hand_count;        // = num_hands_[node.player]
```
i.e. *current player's* hand count. The PR 34 / PR 46 fix matches
Brown's MIT reference exactly.

---

## Fix applied

### File: `crates/cfr_core/src/dcfr_vector.rs`

**Hunk 1** (lines 338-378 in the worktree, opponent-node branch):

```rust
// before
let opp_player = 1 - player;
let opp_hands  = eval_ctx.hand_count[opp_player];
...
let mut next_reach = vec![0.0_f64; opp_hands];
for (a, &child_idx) in children.iter().enumerate() {
    for h in 0..opp_hands {
        next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
    }
    ...
}

// after
let _opp_player = 1 - player;
let _opp_hands  = eval_ctx.hand_count[_opp_player];  // kept as underscored debug-aid
...
// PR 46 fix: reach_opp is sized by player_hands, NOT _opp_hands
let mut next_reach = vec![0.0_f64; player_hands];
for (a, &child_idx) in children.iter().enumerate() {
    for h in 0..player_hands {
        next_reach[h] = reach_opp[h] * strategy[h * action_count + a];
    }
    ...
}
```

**Hunk 2** (`terminal_value_vector`, line 651): debug_assert guard

```rust
let utility = terminal_utility(node, combo, update_player);
debug_assert!(
    ho < reach_opp.len(),
    "ho={} reach_opp.len()={}",
    ho,
    reach_opp.len()
);
total += reach_opp[ho] * utility;
```

### Incidental: `Cargo.lock`
`cfr_core 0.5.0 → 0.6.0` lockfile sync (`Cargo.toml` had already
declared 0.6.0; lockfile on origin/main was stale — same drift the
Path A report observed and fixed).

Total footprint: **2 files, +35 / −5 lines**.

---

## Test results (post-fix)

| Suite | Result |
|-------|--------|
| `cargo test --manifest-path crates/cfr_core/Cargo.toml --release` | **82/82 PASS** (50 lib + 19 hunl_state_unit + 13 hunl_rust + 0 doc) |
| `pytest tests/ -k exploit_diff --timeout=600` | **5/5 PASS** (the regression gate that revertd PR 35 Fix C the first time) |
| `pytest tests/test_v1_5_brown_apples_to_apples.py --timeout=600` | **Runs to completion** (no panic). Coverage check still fails: K72 53.3%, A83 66.7%. **NOT a panic — pre-existing tree-shape divergence per Path A report.** |

The A83 test now spends ~5 min in the solver and exits with a coverage
assertion (66.7% < 80%) instead of an index-out-of-bounds panic. K72
behaves identically to its pre-fix state (53.3% coverage, no panic on
either side because of its symmetric range).

---

## Branch state

* Branch: `pr-46-dcfr-panic-fix`
* Commit SHA: **`cd56761f867815cb69f48e9d3bf815e9c28539e0`**
* Worktree: `/tmp/dcfr_panic_repro_66023` (kept; venv + Brown-binary
  symlink already in place for the next agent)
* Push status: **NOT pushed** (per task spec — awaiting v1.6.1 bundle)

### Cleanup / next-agent notes

* The worktree has a `.venv/` (worktree-local) and a symlink at
  `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
  pointing into the shared tree's Brown build. Both are read-only
  from the shared tree's perspective and do NOT pollute it.
* If the next agent needs to rerun the test from a clean checkout,
  they should source `.venv/bin/activate` and add `~/.cargo/bin` to
  `PATH` before `maturin develop --release`.

---

## Constraints honored

- [x] Worktree-isolated (no edits to `/Users/ashen/Desktop/poker_solver`)
- [x] No push to origin
- [x] No sub-agents spawned
- [x] No destructive git operations
- [x] No branch-switch in shared working tree
- [x] Within 45-minute time budget (test runs themselves consumed
      ~14 min — fix + diagnosis + rebuild was <10 min)
