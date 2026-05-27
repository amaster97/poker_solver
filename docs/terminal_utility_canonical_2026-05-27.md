# Terminal-utility canonical formula — 2026-05-27

**Status:** authoritative reference for the in-source comment at
`crates/cfr_core/src/hunl.rs:495` (and the parallel Python path in
`poker_solver/hunl.py`). This doc is a thin pointer to the underlying
memory rule + the PR that landed the canonical implementation.

---

## Canonical source

The single rule of real poker, per memory rule
`feedback_brown_convention_adopt.md`:

> The winner of a hand collects every chip in the pot, including the
> dead money already on the table from prior streets (`initial_pot`).
> The loser eats their subgame-only contribution. There is no
> "rust" convention in which `initial_contributions` are recoverable
> by the player who folded — that was an implementation error, not a
> feature flag.

This convention is enforced in code by `HUNLState::utility()`
(`crates/cfr_core/src/hunl.rs:496`).

---

## Canonical formula

In big-blind units:

```
winner_utility = pot_total - contrib_subgame_winner
               = base_pot + contrib_subgame_loser
loser_utility  = -contrib_subgame_loser
tie_each       = pot_total / 2 - contrib_subgame_player
```

Where:

- `contrib_subgame[i] = state.contributions[i] - cfg.initial_contributions[i]`
- `pot_total = cfg.initial_pot + contrib_subgame[0] + contrib_subgame[1]`

The game is **constant-sum** with
`u[0] + u[1] = initial_pot / big_blind` per leaf (not zero-sum when
dead money is present). DCFR convergence proofs only require bounded
utilities + a finite action set, so this is well-posed.

---

## Numeric example

At a canonical leaf where P0 folds with `base_pot = 10 BB` and zero
in-subgame contributions
(`contrib_subgame = (0, 0)`, `initial_contributions = (5, 5)`):

- Old "rust" path (DELETED in PR #78): `(-5, +5)` BB — treated each
  player's `initial_contributions` as recoverable by the folder.
- Canonical path (current): `(0, +10)` BB — winner collects the entire
  dead-money pot; loser keeps their `initial_contributions` because
  those chips are already in the pot and belong to the winner.

---

## Implementation

- Rust kernel: `crates/cfr_core/src/hunl.rs:496` —
  `HUNLState::utility() -> [f64; 2]`.
- Python parity wrapper: `poker_solver/hunl.py:470` —
  `HUNLState.utility()`. Same formula; same canonical convention.

Both implementations were unified in PR #78 (`37e5be1`,
"Terminal-utility convention purge"), which deleted the dual-convention
code path. The pre-purge empirical ablation that demonstrated the rust
convention introduced a 12-50pp regret-update bias at deep cap is
archived at
`docs/a83_terminal_utility_ablation_results_2026-05-26_archived.md`
(from local branch `pr-93-terminal-utility-ablation` @ `986f48d`, an
internal investigation that was never opened as a GitHub PR).

---

## See also

- `feedback_brown_convention_adopt.md` (memory rule, authoritative)
- PR #78 (`37e5be1`) — the convention purge that shipped in v1.8.0
- `docs/a83_terminal_utility_ablation_results_2026-05-26_archived.md`
  — empirical ablation motivating the purge
