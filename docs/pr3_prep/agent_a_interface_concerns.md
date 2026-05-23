# Agent A interface concerns (PR 3)

Notes from Agent A about places where the orchestrator-supplied contract didn't
quite line up with Agent B's actual `action_abstraction.py` signatures. These
were resolved at integration time by adapting Agent A's call sites; no spec
deviation. Listed here per the orchestrator's instruction to file concerns
rather than mutate the contract.

## 1. `ActionContext` field shape

**Orchestrator-supplied contract:** `ActionContext` exposes flat fields
including `street`, `bet_size_fractions`, `preflop_raise_cap`,
`postflop_raise_cap`, `force_allin_threshold_bb`, `min_bet_bb`,
`include_all_in`.

**Agent B's actual shape:** `ActionContext` exposes a nested
`config: ActionAbstractionConfig` for the menu/cap/threshold fields, plus an
`is_preflop: bool` instead of a numeric `street`.

**Resolution:** Agent A constructs `ActionContext` with `is_preflop` derived
from `state.street == Street.PREFLOP` and `config=HUNLConfig.to_action_config()`.
Functionally equivalent. No tests need to change.

## 2. `compute_bet_amount` semantics

The spec says "returns the chip amount put in this action". Agent B returns
the chips added *this action* for bets (consistent with the spec). For
`ACTION_ALL_IN` Agent B returns the player's remaining stack (also the chips
they're adding). Agent A uses this directly in `_apply_player`.

## 3. `compute_raise_to` for `ACTION_ALL_IN`

Agent B's `compute_raise_to(ACTION_ALL_IN, ctx)` returns
`contributions[cur] + stacks[cur]`, i.e. the total contribution after shoving
the remaining stack. Agent A uses `compute_raise_to` only for actions in the
RAISE family (not for ACTION_ALL_IN); the all-in branch in `_apply_player`
computes the shove directly from the state. This is a no-op for correctness
but worth noting for future maintainers.
