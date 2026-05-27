# Rust Scalar-Form Terminal-Utility Audit

**Scope.** `crates/cfr_core/src/*.rs` excluding `dcfr_vector.rs`. The audit
targets every place a scalar-form CFR walker reads a terminal payoff. The
core question: does the winner receive the **full pot** (= own contribs +
opp contribs + prior-street pot), or just opp's contributions, or
something else?

**TL;DR.** All scalar paths funnel terminals through one function:
`HUNLState::utility()` in `crates/cfr_core/src/hunl.rs:485-521`. That
function returns the **zero-sum chip delta from start of the subgame, in
BB units**, which is mathematically equivalent to "winner takes the full
pot" once the constant prior-street pot is netted out. The one separate
terminal path (preflop equity-leaf in `preflop.rs:241-255`) uses the same
zero-sum convention. **No bug found.**

---

## The Convention, Once

`HUNLState::utility()` returns `[u0, u1]` in BB where:
- Fold by P0 → `[-c0/bb, +c0/bb]`
- Fold by P1 → `[+c1/bb, -c1/bb]`
- Showdown win by P0 → `[+c1/bb, -c1/bb]`
- Showdown win by P1 → `[-c0/bb, +c0/bb]`
- Showdown tie → `[0, 0]`

The winner's number is **what the opponent contributed to the pot during
this subgame**. That is exactly the chip delta from the subgame's starting
stack: the winner started with `starting_stack − initial_contributions[i]`,
and ends with `starting_stack + opponent_contribution`. The "base pot"
from prior streets (= `initial_pot − sum(initial_contributions)`) was
already deducted from both starting stacks before the subgame; it is a
sunk constant that does not change either player's net stack delta.

Equivalence to "winner takes full pot":
- Total pot at terminal = `c0 + c1 + (initial_pot − Σ initial_contribs)`.
- Winner's NET stack delta = total pot − own_contrib_subgame − prior_pot_share.
- Since the prior-street pot left **both** stacks short by the same per-player
  amount (or asymmetric, but already accounted in `initial_contributions`),
  the net delta reduces to `opp_contrib` for the winner and `−own_contrib`
  for the loser. Zero-sum, full-pot-collected.

This is the same convention Brown's reference solver uses, and it matches
the Python implementation line-for-line (see cross-reference below).

---

## Per-File Findings

### 1. `crates/cfr_core/src/hunl.rs:485-521` — `HUNLState::utility()`

The canonical scalar terminal function. Used by EVERY scalar walker
(directly via `state.utility()` or indirectly through the `Game` trait
adapter at `hunl.rs:879-881`).

Verbatim:

```rust
pub fn utility(&self) -> [f64; 2] {
    let bb = self.config.big_blind as f64;
    let c0 = self.contributions[0] as f64;
    let c1 = self.contributions[1] as f64;
    if self.folded[0] {
        return [-c0 / bb, c0 / bb];
    }
    if self.folded[1] {
        return [c1 / bb, -c1 / bb];
    }
    // ... build 7-card hands, evaluate strengths ...
    if s0 > s1 {
        [c1 / bb, -c1 / bb]
    } else if s1 > s0 {
        [-c0 / bb, c0 / bb]
    } else {
        [0.0, 0.0]   // tie
    }
}
```

**Verdict: WINNER-GETS-FULL-POT (via zero-sum convention) ✓.**

Cross-reference: `poker_solver/hunl.py:465-479` is line-identical (same
variables, same branches, same returned values). Both files document the
relationship in their respective module docs.

Inline test `showdown_winner_collects_loser_contrib` (`hunl.rs:1226-1239`)
asserts P0-wins → `[+5.0, −5.0]` when `contributions=[500,500]` and
`bb=100`. Inline test `fold_terminates_with_loser_paying_contrib`
(`hunl.rs:1212-1223`) asserts P0-folds → `[−5.0, +5.0]` with the same
contribs. Both pin the zero-sum convention end-to-end.

---

### 2. `crates/cfr_core/src/dcfr.rs:189-192` — Scalar DCFR loop

```rust
pub fn cfr(&mut self, state: &G, reach: [f64; 3], iteration: u32) -> [f64; 2] {
    if state.is_terminal() {
        return state.utility();
    }
    // ... chance / decision recursion ...
}
```

Pure delegation. No payoff transformation. **Verdict ✓.**

---

### 3. `crates/cfr_core/src/hunl_solver.rs:237-240` — HUNL solver entry

```rust
if state.is_terminal() {
    return state.utility();
}
```

Pure delegation. **Verdict ✓.**

---

### 4. `crates/cfr_core/src/solver.rs:73-74, 168, 216-217` — Generic
solver / EV / best-response walkers

```rust
// expected_value
if state.is_terminal() {
    return state.utility();
}
// best_response (player view)
if state.is_terminal() {
    return state.utility()[br_player];
}
```

Pure delegation to `Game::utility()`. **Verdict ✓.**

---

### 5. `crates/cfr_core/src/exploit.rs:515-573` — Flat-tree
`terminal_utility()`

A re-implementation in flat-tree form. Used by the EV / BR passes on the
precomputed `BettingTree` (also reused by the vector path, which the
sibling agent owns).

Verbatim Fold branch:

```rust
FlatNode::Fold { contributions, big_blind, folded_player } => {
    let c0 = contributions[0] as f64;
    let c1 = contributions[1] as f64;
    let bb = *big_blind as f64;
    if *folded_player == 0 {
        if player == 0 { -c0 / bb } else { c0 / bb }
    } else if player == 0 { c1 / bb } else { -c1 / bb }
}
```

Verbatim Showdown branch:

```rust
FlatNode::Showdown { contributions, big_blind, board } => {
    // ... build 7-card hands & evaluate ...
    if s0 > s1 {
        if player == 0 { c1 / bb } else { -c1 / bb }
    } else if s1 > s0 {
        if player == 0 { -c0 / bb } else { c0 / bb }
    } else { 0.0 }
}
```

Bit-identical convention to `HUNLState::utility()`. **Verdict ✓.**

---

### 6. `crates/cfr_core/src/preflop.rs:241-255` — Preflop equity-leaf

The one non-trivial terminal: at the preflop-close frontier, instead of
recursing through the full postflop runout, we collapse to an
equity-weighted EV. Verbatim:

```rust
fn preflop_subgame_utility(state: &HUNLState, cache: &mut EquityCache) -> [f64; 2] {
    if state.folded[0] || state.folded[1] || state.street == Street::Showdown {
        return state.utility();
    }
    // Equity-leaf case.
    let bb = state.config.big_blind as f64;
    let c0 = state.contributions[0] as f64;
    let c1 = state.contributions[1] as f64;
    let risk = c0.min(c1);
    let pot = 2.0 * risk;
    let hole = state.hole_cards.expect("equity leaf requires hole cards");
    let eq_p0 = compute_p0_equity(&hole, &state.board, cache);
    let ev_p0_chips = pot * eq_p0 - risk;
    [ev_p0_chips / bb, -ev_p0_chips / bb]
}
```

Decoded: `risk = min(c0, c1)` is the matched stake (over-shoves are
already refunded by `apply_player`, so c0==c1 here in practice).
`pot = 2 * risk` is the contested chips this subgame.
`ev_p0_chips = pot * eq_p0 - risk`:
- `eq_p0=1` → `2r − r = +r` (P0 wins the matched pot)
- `eq_p0=0` → `0 − r = −r` (P0 loses their stake)
- `eq_p0=0.5` → `r − r = 0`

Zero-sum, same "subgame chip delta" convention as the postflop fold /
showdown paths. **Verdict ✓.**

Cross-reference: `poker_solver/preflop.py:129-`. Same formula, same vars.

---

### 7. `crates/cfr_core/src/hunl_tree.rs:233-252` — Flat HUNL tree
builder

Stores `TerminalKind::Fold { winner, contribution_loss }` and
`TerminalKind::Showdown { board_complete }`. **Does not compute utility
itself** — it only marks tree topology. The utility consumer is whoever
walks the tree (scalar path: `HUNLState::utility`; vector path:
`exploit.rs::terminal_utility`, audited above). **Not in the suspect
surface.**

---

### 8. `crates/cfr_core/src/exploit.rs:118-119, 196-197, 243` — EV /
BR walkers on the recursive HUNL tree

All three are pure delegations to `state.utility()` at terminal nodes.
**Verdict ✓.**

---

## Summary Table

| Street    | Showdown                           | Fold                               | All-in (run-out)                   | Verdict |
| --------- | ---------------------------------- | ---------------------------------- | ---------------------------------- | ------- |
| Preflop   | equity-leaf (preflop.rs:241-255)   | utility() (hunl.rs:489-493)        | equity-leaf (preflop.rs:241-255)   | ✓       |
| Flop      | utility() (hunl.rs:495-520)        | utility() (hunl.rs:489-493)        | utility() after full runout        | ✓       |
| Turn      | utility() (hunl.rs:495-520)        | utility() (hunl.rs:489-493)        | utility() after full runout        | ✓       |
| River     | utility() (hunl.rs:495-520)        | utility() (hunl.rs:489-493)        | utility() (closes at river)        | ✓       |

All-in paths: `after_board_dealt` (`hunl.rs:656-671`) and
`begin_street_transition` (`hunl.rs:829-859`) deal cards one at a time
until the board hits 5 cards, then set `Street::Showdown`, after which
`utility()` evaluates strengths on the completed board. The exploit /
EV / BR walkers reach this terminal through the standard recursion.

---

## Cross-Reference vs Python

| Function                            | Python                                       | Rust                                      | Parity |
| ----------------------------------- | -------------------------------------------- | ----------------------------------------- | ------ |
| Showdown / fold utility             | `poker_solver/hunl.py:465-479` `HUNLPoker.utility` | `crates/cfr_core/src/hunl.rs:485-521` `HUNLState::utility` | exact |
| Preflop equity-leaf utility         | `poker_solver/preflop.py:129-`               | `crates/cfr_core/src/preflop.rs:241-255` | exact |
| Flat-tree terminal_utility (vector reuse) | n/a (vector path is Rust-only)         | `crates/cfr_core/src/exploit.rs:515-573` | matches HUNLState::utility |

---

## Final Verdict

**CORRECT.** Every scalar-form terminal node in `cfr_core` returns the
zero-sum chip delta from the start of the subgame, which is the standard
poker / CFR convention and is mathematically equivalent to "winner takes
the full pot" once the prior-street pot constant is netted out. Both
postflop (`HUNLState::utility`) and preflop equity-leaf
(`preflop_subgame_utility`) paths use the same convention. The flat-tree
re-implementation in `exploit.rs::terminal_utility` is bit-identical to
the recursive `HUNLState::utility`. Two inline tests in `hunl.rs` pin
the contract end-to-end.

**No bug.** The "non-zero-sum convention divergence" hypothesis is not
supported by the Rust scalar source.

---

## Recommended Next Action

1. **Stop chasing the divergence inside scalar utility code.** Three
   independent surfaces (hunl.rs, exploit.rs, preflop.rs) all use the
   identical zero-sum subgame-delta convention. Tests pass.
2. **Re-examine the original "divergence" claim.** Likely candidates for
   the actual root cause:
   - Vector-form path (`dcfr_vector.rs`) — sibling agent's audit.
   - Brown-comparison harness: are we comparing chip deltas vs full-pot
     numbers between the two solvers? A unit mismatch on the COMPARATOR
     would produce a phantom "convention difference" without any bug in
     either solver.
   - Reach / chance weighting at the leaf, not the leaf value itself.
3. **If the vector audit also returns CORRECT,** trace the comparator /
   harness side. If both leaf surfaces are clean, the divergence has to
   be in: (a) tree topology mismatch, (b) reach / chance weighting,
   (c) the post-CFR aggregation, or (d) the comparator's unit handling.
