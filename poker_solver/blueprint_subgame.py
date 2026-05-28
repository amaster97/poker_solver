"""Glue layer: Premium-A blueprint -> postflop subgame solver.

Phase 4 of the Premium-A blueprint subplan (issue #68). This module bridges
the 169-class preflop blueprint produced by :mod:`poker_solver.blueprint`
(Phase 1) and the postflop range-vs-range Nash solver
(:func:`poker_solver.range_aggregator.solve_range_vs_range_nash`).

## Scope

Phase 4's explicit goal (per the user-confirmed prompt):

  1. Trace the data flow: blueprint strategy -> range expansion
     (169 -> 1326) -> postflop solver ingest as range prior.
  2. If wiring is missing, add a THIN glue layer (Python) that:
     - Takes a preflop blueprint and a preflop action sequence
     - Walks the action sequence and reads per-class reach probabilities
       from the blueprint
     - Expands each 169-class to its 1326 combos (uniform within class)
       weighted by the class's reach probability into this terminal
     - Constructs ``Range`` objects with these per-combo weights
     - Calls :func:`solve_range_vs_range_nash` on the resulting prior

Phase 4 is **independent of** Phases 2 (loader) and 3 (interpolation).
Those phases land separately; this module operates directly on a
:class:`Blueprint` instance, regardless of how it was obtained (loaded
from disk, generated in-memory, or constructed in a test fixture).

## Why we DON'T touch ``chained.py``

The existing :func:`poker_solver.solve_chained` orchestrator performs its
OWN Stage 1 preflop solve via Route A blueprint aggregation — it does
NOT consume a pre-existing Premium-A :class:`Blueprint` asset. Modifying
``chained.py`` would replace its Stage 1 with a blueprint lookup, but
that's a wider behavioral change (Phase 4 subplan §4 anticipates it as a
follow-up). For now we ship a SEPARATE entry point that operates from a
blueprint asset, leaving the chained orchestrator's Phase A behavior
intact.

## Per-combo weighting -> Range vector form

The postflop subgame solver
(:func:`solve_range_vs_range_nash`) accepts ``Range`` objects with
per-combo weights (B10 Phase B, PR #133). We construct ``Range``
objects whose per-combo weight equals the class's reach into this
terminal, divided uniformly across its member combos (within-class
suit-symmetry assumption per the Phase 1 design — preflop equity is
suit-symmetric modulo blockers).
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from poker_solver.blueprint import Blueprint
from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, HUNLState, Street
from poker_solver.range import Range
from poker_solver.range_aggregator import (
    HandClass,
    RangeVsRangeNashResult,
    _enumerate_combos,
    solve_range_vs_range_nash,
)

# ---------------------------------------------------------------------------
# History-key reconstruction
# ---------------------------------------------------------------------------


def _build_history_key(
    tokens_so_far: Sequence[str], *, trailing_pipe: bool
) -> str:
    """Return the blueprint history key for the current point in the tree.

    The Rust engine's :class:`PreflopFlatNode::Decision` ``key_suffix`` is
    ``"||p|<concat_tokens>"`` (NO trailing pipe). However the schema
    docstring + some test fixtures use ``"||p|<concat_tokens>|"`` (with
    trailing pipe). To be tolerant we try both flavors when looking up
    the blueprint; this helper produces whichever the caller asks for.
    """
    body = "".join(tokens_so_far)
    if trailing_pipe and body:
        return f"||p|{body}|"
    return f"||p|{body}"


def _lookup_infoset_or_none(
    blueprint: Blueprint, tokens_so_far: Sequence[str]
) -> dict[str, Any] | None:
    """Try both with-pipe and without-pipe variants; return the infoset dict.

    Returns ``None`` when neither variant is present in the blueprint.
    """
    # Order: matches engine first (no trailing pipe), then schema-docstring.
    for trailing in (False, True):
        key = _build_history_key(tokens_so_far, trailing_pipe=trailing)
        info = blueprint.infosets.get(key)
        if info is not None:
            return info
    return None


# ---------------------------------------------------------------------------
# Engine token <-> blueprint action label mapping
# ---------------------------------------------------------------------------


def _token_to_action_label(token: str) -> str:
    """Map an engine action token (``"b300"``, ``"c"``, ``"f"``, etc.)
    to the user-facing label the blueprint schema uses.

    Mirrors :func:`poker_solver.blueprint._decode_engine_action`. Kept
    inline here so this module does not depend on that helper's private
    name (the schema-level mapping is stable enough to inline).
    """
    if token == "f":
        return "fold"
    if token == "c":
        return "call"
    if token == "x":
        return "check"
    if token == "A":
        return "all_in"
    if token.startswith("b"):
        return f"open_to_{token[1:]}"
    if token.startswith("r"):
        return f"raise_to_{token[1:]}"
    raise ValueError(f"unrecognized engine action token: {token!r}")


def _player_to_act_after_tokens(
    config_template: HUNLConfig, tokens_so_far: Sequence[str]
) -> int:
    """Replay ``tokens_so_far`` against a placeholder HUNL game and return
    the player whose turn it is at the resulting state.

    Returns ``-1`` if the sequence reaches a terminal (preflop close or
    fold). We use a placeholder pair of hole cards (always
    ``AsAh / KdKc``) — the tree shape at preflop depends only on stacks
    and contributions, not hole cards.
    """
    placeholder = (
        (Card.from_str("As"), Card.from_str("Ah")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
    )
    cfg = replace(config_template, initial_hole_cards=placeholder)
    game = HUNLPoker(cfg)
    state = game.initial_state()
    remaining = list(tokens_so_far)
    visited = 0
    while remaining and visited < 100:
        if game.is_terminal(state):
            return -1
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return -1
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        actions = game.legal_actions(state)
        next_tok = remaining[0]
        chosen_idx: int | None = None
        for idx, action in enumerate(actions):
            trial = game.apply(state, action)
            tok = _action_token_from_states(state, trial)
            if tok == next_tok:
                chosen_idx = idx
                break
        if chosen_idx is None:
            return -1
        state = game.apply(state, actions[chosen_idx])
        remaining.pop(0)
        visited += 1
    if game.is_terminal(state):
        return -1
    return int(game.current_player(state))


def _action_token_from_states(prev: HUNLState, new: HUNLState) -> str:
    """Return the single engine-action token that takes ``prev`` to ``new``.

    Mirrors :func:`poker_solver.chained._last_token` for our internal use
    so we don't import private helpers across module boundaries.
    """
    prev_cs = prev.current_street_tokens
    new_cs = new.current_street_tokens
    if len(new_cs) > len(prev_cs):
        return new_cs[len(prev_cs)]
    if (
        new.street != prev.street
        or new.pending_board_deals > 0
        or any(new.folded) != any(prev.folded)
    ) and new.betting_tokens and new.betting_tokens[-1]:
        return new.betting_tokens[-1][-1]
    return ""


# ---------------------------------------------------------------------------
# Reach derivation from the blueprint
# ---------------------------------------------------------------------------


@dataclass
class BlueprintContinuationRanges:
    """Per-player class-reach distributions at the end of a preflop sequence.

    Mirrors :class:`poker_solver.chained.ContinuationRanges` but is derived
    from a blueprint asset rather than per-pair solves. Weights are RAW
    reach probabilities (unnormalized — call sites that want
    probabilities sum to 1.0 should normalize).
    """

    hero: dict[HandClass, float] = field(default_factory=dict)
    villain: dict[HandClass, float] = field(default_factory=dict)
    pot_chips: int = 0
    action_sequence: tuple[str, ...] = ()


def derive_continuation_ranges_from_blueprint(
    blueprint: Blueprint,
    *,
    config_template: HUNLConfig,
    action_sequence: Sequence[str],
    hero_player: int = 0,
    hero_classes: Iterable[HandClass] | None = None,
    villain_classes: Iterable[HandClass] | None = None,
) -> BlueprintContinuationRanges:
    """Per-class reach probability propagation along ``action_sequence``.

    For each hand class on each player's side, walk the preflop tree
    token by token. At each decision node, look up the class's action
    distribution from the blueprint and multiply by the probability of
    the chosen action's label. The resulting product is the class's
    reach into the terminal.

    Args:
        blueprint: A loaded / generated :class:`Blueprint` with at least
            the SB-root and every reachable mid-sequence infoset present.
        config_template: ``HUNLConfig`` whose preflop tree shape matches
            the blueprint's. Stacks, blinds, ante, raise cap must match.
        action_sequence: Sequence of engine tokens (e.g. ``("b300", "c")``)
            describing the terminal frontier.
        hero_player: 0 (SB / aggressor) or 1 (BB / defender). Determines
            which player's class-reach map populates ``hero`` vs
            ``villain``.
        hero_classes / villain_classes: Optional class restriction. When
            ``None``, every class present in the blueprint at the
            relevant infosets is propagated. When provided, classes
            outside the set are skipped (reach treated as zero).

    Returns:
        A :class:`BlueprintContinuationRanges` with per-class reach
        probabilities. The pot chip total is the sum of contributions
        at the terminal state.

    Raises:
        ValueError: ``action_sequence`` references an infoset that the
            blueprint does not cover (typically because the blueprint
            shipped at a different stack depth or action-menu config).
        ValueError: ``hero_player`` not in ``(0, 1)``.
    """
    if hero_player not in (0, 1):
        raise ValueError(
            f"hero_player must be 0 (SB/aggressor) or 1 (BB/defender); "
            f"got {hero_player!r}"
        )

    hero_filter = set(hero_classes) if hero_classes is not None else None
    villain_filter = set(villain_classes) if villain_classes is not None else None

    # Initialize per-class reach products at 1.0 — multiplied step-by-step.
    # We initialize using the SB-root infoset's class set so we don't
    # synthesize classes the blueprint doesn't cover.
    root_info = _lookup_infoset_or_none(blueprint, [])
    if root_info is None:
        raise ValueError(
            "blueprint is missing the SB-root infoset (||p|). The blueprint "
            "may be empty or corrupted; cannot derive continuation ranges."
        )
    root_strategy = root_info.get("strategy", {})
    all_classes = list(root_strategy.keys())

    # Reach accumulators per player. SB plays as player 0 in the engine's
    # internal convention; BB is player 1. The blueprint records BOTH
    # players' strategies under the appropriate history keys.
    reach: dict[int, dict[HandClass, float]] = {
        0: {cls: 1.0 for cls in all_classes},
        1: {cls: 1.0 for cls in all_classes},
    }

    tokens_seen: list[str] = []
    for token in action_sequence:
        # Which player is about to act at this point?
        cur_player = _player_to_act_after_tokens(config_template, tokens_seen)
        if cur_player == -1:
            # Tree closed mid-sequence — sequence is over-length. Stop.
            break
        info = _lookup_infoset_or_none(blueprint, tokens_seen)
        if info is None:
            raise ValueError(
                f"blueprint missing infoset for tokens={tokens_seen!r}; "
                f"the blueprint may not cover this action sequence. "
                f"Known root key: {next(iter(blueprint.infosets.keys()), None)!r}"
            )
        actions: list[str] = info.get("actions", [])
        strategy: dict[str, list[float]] = info.get("strategy", {})

        # Find the action label this token corresponds to.
        try:
            target_label = _token_to_action_label(token)
        except ValueError:
            # Unrecognized token — treat as terminating the walk.
            break
        if target_label not in actions:
            raise ValueError(
                f"blueprint infoset for tokens={tokens_seen!r} has no "
                f"action {target_label!r}; available actions={actions!r}. "
                f"Token={token!r}."
            )
        action_idx = actions.index(target_label)

        # Multiply each class's reach by the probability of this action
        # under that class's blueprint strategy. Classes absent at this
        # infoset (e.g. zero reach) get their reach zeroed out.
        new_reach: dict[HandClass, float] = {}
        for cls, prev_w in reach[cur_player].items():
            probs = strategy.get(cls)
            if probs is None or len(probs) <= action_idx:
                continue
            p = float(probs[action_idx])
            if p <= 0.0:
                continue
            new_reach[cls] = prev_w * p
        # The OTHER player's reach is unchanged on this step.
        reach[cur_player] = new_reach

        tokens_seen.append(token)

    hero_raw = reach[hero_player]
    villain_raw = reach[1 - hero_player]
    if hero_filter is not None:
        hero_raw = {k: v for k, v in hero_raw.items() if k in hero_filter}
    if villain_filter is not None:
        villain_raw = {k: v for k, v in villain_raw.items() if k in villain_filter}
    # Drop near-zero entries for cleanliness.
    hero_raw = {k: v for k, v in hero_raw.items() if v > 1e-9}
    villain_raw = {k: v for k, v in villain_raw.items() if v > 1e-9}

    # Compute pot chips at the terminal by replaying the sequence.
    pot_chips = _pot_chips_after_tokens(config_template, action_sequence)

    return BlueprintContinuationRanges(
        hero=hero_raw,
        villain=villain_raw,
        pot_chips=pot_chips,
        action_sequence=tuple(action_sequence),
    )


def _pot_chips_after_tokens(
    config_template: HUNLConfig, tokens: Sequence[str]
) -> int:
    """Replay ``tokens`` and return total contributions in chips."""
    placeholder = (
        (Card.from_str("As"), Card.from_str("Ah")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
    )
    cfg = replace(config_template, initial_hole_cards=placeholder)
    game = HUNLPoker(cfg)
    state = game.initial_state()
    remaining = list(tokens)
    visited = 0
    while remaining and visited < 100:
        if game.is_terminal(state):
            break
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                break
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        actions = game.legal_actions(state)
        next_tok = remaining[0]
        chosen_idx: int | None = None
        for idx, action in enumerate(actions):
            trial = game.apply(state, action)
            tok = _action_token_from_states(state, trial)
            if tok == next_tok:
                chosen_idx = idx
                break
        if chosen_idx is None:
            break
        state = game.apply(state, actions[chosen_idx])
        remaining.pop(0)
        visited += 1
    c0, c1 = state.contributions
    return int(c0) + int(c1)


# ---------------------------------------------------------------------------
# 169 -> 1326 range expansion
# ---------------------------------------------------------------------------


def expand_classes_to_range(
    class_weights: dict[HandClass, float],
    *,
    board: Sequence[Card] = (),
) -> Range:
    """Expand a ``{class: reach_weight}`` dict to a 1326-combo ``Range``.

    Within-class weighting is **uniform** — each combo in a class
    receives the same fractional weight. This matches the Phase 1
    blueprint's within-class suit-symmetry assumption (preflop equity is
    suit-symmetric modulo blockers, already integrated by the engine's
    169×169 equity table).

    Args:
        class_weights: ``{hand_class: reach_weight}``. Weights are
            arbitrary non-negative floats (treated as reach probabilities
            but the function normalizes to ``[0, 1]`` per-combo so the
            ``Range`` weight cap is honored). When all weights are
            equal, the resulting per-combo weights are uniform across
            board-feasible combos.
        board: Optional board cards. Combos that collide with the board
            are excluded from the resulting range.

    Returns:
        A ``Range`` whose combos cover the class-expansion of
        ``class_weights`` (minus board-blocked combos), with per-combo
        weights in ``[0, 1]``.

    Raises:
        ValueError: any reach weight is negative.
    """
    if any(w < 0 for w in class_weights.values()):
        raise ValueError(
            f"reach weights must be non-negative; got "
            f"{[(k, v) for k, v in class_weights.items() if v < 0]!r}"
        )
    board_set = set(board)
    # Per-combo weight = class reach / combos-in-class (uniform within
    # class). Then renormalize to [0, 1] so the Range.add() weight check
    # passes; the postflop solver only cares about relative weights.
    raw: dict[tuple[Card, Card], float] = {}
    for cls, reach in class_weights.items():
        if reach <= 0:
            continue
        try:
            combos = _enumerate_combos(cls)
        except ValueError:
            continue
        feasible = [c for c in combos if c[0] not in board_set and c[1] not in board_set]
        if not feasible:
            continue
        per_combo = reach / float(len(feasible))
        for combo in feasible:
            raw[combo] = raw.get(combo, 0.0) + per_combo
    if not raw:
        return Range()
    # Renormalize so max weight = 1.0 (the Range API caps at 1.0). The
    # postflop solver's per-combo weight handling is scale-invariant —
    # only relative weights matter.
    max_w = max(raw.values())
    out = Range()
    if max_w <= 0:
        return out
    for combo, w in raw.items():
        out.add(combo, weight=w / max_w)
    return out


# ---------------------------------------------------------------------------
# Public entry point — full flow
# ---------------------------------------------------------------------------


@dataclass
class BlueprintPostflopResult:
    """Result of :func:`solve_postflop_from_blueprint`.

    Carries the postflop subgame solver's output PLUS the derived prior
    metadata so callers can verify the wiring (range sizes, reach weights,
    wall times for each stage).
    """

    postflop: RangeVsRangeNashResult
    continuation: BlueprintContinuationRanges
    hero_range: Range
    villain_range: Range
    wall_time_total_s: float
    wall_time_lookup_s: float
    wall_time_expand_s: float
    wall_time_solve_s: float


def _is_terminal_fold_or_allin(
    config_template: HUNLConfig, tokens: Sequence[str]
) -> bool:
    """Return True if replaying ``tokens`` reaches a fold or all-in terminal.

    Fold terminals end the hand preflop — no postflop subgame to solve.
    All-in terminals collapse to equity at the preflop close — likewise
    no postflop decisions remain. Both are unsuitable for the postflop
    pipeline.
    """
    placeholder = (
        (Card.from_str("As"), Card.from_str("Ah")),
        (Card.from_str("Kd"), Card.from_str("Kc")),
    )
    cfg = replace(config_template, initial_hole_cards=placeholder)
    game = HUNLPoker(cfg)
    state = game.initial_state()
    remaining = list(tokens)
    visited = 0
    while remaining and visited < 100:
        if game.is_terminal(state):
            break
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                break
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        actions = game.legal_actions(state)
        next_tok = remaining[0]
        chosen_idx: int | None = None
        for idx, action in enumerate(actions):
            trial = game.apply(state, action)
            tok = _action_token_from_states(state, trial)
            if tok == next_tok:
                chosen_idx = idx
                break
        if chosen_idx is None:
            break
        state = game.apply(state, actions[chosen_idx])
        remaining.pop(0)
        visited += 1
    return bool(any(state.folded) or any(state.all_in))


def solve_postflop_from_blueprint(
    blueprint: Blueprint,
    *,
    config_template: HUNLConfig,
    action_sequence: Sequence[str],
    board: Sequence[Card],
    hero_player: int = 0,
    iterations: int = 500,
    hero_classes: Iterable[HandClass] | None = None,
    villain_classes: Iterable[HandClass] | None = None,
    compute_exploitability_at_end: bool = False,
) -> BlueprintPostflopResult:
    """End-to-end: blueprint lookup -> 169->1326 expansion -> postflop solve.

    The full Phase 4 pipeline:

      1. **Blueprint lookup**: walks ``action_sequence`` through the
         preflop tree, reading each class's action distribution from
         ``blueprint`` and propagating reach products.
      2. **Range expansion**: converts the resulting 169-class reach
         dicts into 1326-combo :class:`Range` objects with per-combo
         weights, filtering out combos that collide with ``board``.
      3. **Postflop solve**: feeds the per-player :class:`Range` priors
         into :func:`solve_range_vs_range_nash` and returns the
         converged :class:`RangeVsRangeNashResult`.

    Args:
        blueprint: A Phase 1 blueprint covering the preflop tree.
        config_template: ``HUNLConfig`` whose preflop tree shape matches
            the blueprint (same stack, blinds, raise cap). The postflop
            solve uses a derived config with ``starting_street=FLOP``,
            ``initial_board=board``, and contributions = the preflop
            terminal's matched pot.
        action_sequence: Preflop tokens (e.g. ``("b300", "c")``)
            reaching the flop subgame.
        board: 3-card flop tuple (Phase 4 supports flop subgames; turn
            / river follow naturally if the caller threads a longer
            board, but PR #170 vector-form preflop work assumes flop).
        hero_player: 0 (SB) or 1 (BB).
        iterations: Postflop CFR iterations (default 500, matches
            :func:`solve_range_vs_range_nash` default).
        hero_classes / villain_classes: Optional class filter (defaults
            to every class present in the blueprint).
        compute_exploitability_at_end: Forwarded to the postflop solver.

    Returns:
        A :class:`BlueprintPostflopResult` with the postflop strategy,
        the derived continuation ranges, the expanded Range objects, and
        per-stage wall times.

    Raises:
        ValueError: ``board`` is not length 3 or 4 or 5 (Phase 4
            supports flop / turn / river starting streets); blueprint
            does not cover an infoset on the action path; hero/villain
            continuation range is empty after propagation.
    """
    n_board = len(board)
    if n_board not in (3, 4, 5):
        raise ValueError(
            f"board must be 3 (flop), 4 (turn), or 5 (river) cards; "
            f"got {n_board}: {list(board)!r}"
        )

    # Reject action sequences that end at fold / all-in terminals — no
    # postflop subgame to solve.
    if _is_terminal_fold_or_allin(config_template, action_sequence):
        raise ValueError(
            f"action_sequence={tuple(action_sequence)!r} reaches a fold or "
            f"all-in terminal; no postflop subgame to solve. Phase 4 supports "
            f"only sequences that reach the flop with both players live."
        )

    t_start = time.perf_counter()
    # Step 1: blueprint lookup + reach propagation.
    continuation = derive_continuation_ranges_from_blueprint(
        blueprint,
        config_template=config_template,
        action_sequence=action_sequence,
        hero_player=hero_player,
        hero_classes=hero_classes,
        villain_classes=villain_classes,
    )
    t_after_lookup = time.perf_counter()
    if not continuation.hero:
        raise ValueError(
            f"hero continuation range is empty for action_sequence="
            f"{tuple(action_sequence)!r}; the action sequence may lead to a "
            f"fold terminal or every class has zero reach."
        )
    if not continuation.villain:
        raise ValueError(
            f"villain continuation range is empty for action_sequence="
            f"{tuple(action_sequence)!r}; the action sequence may lead to a "
            f"fold terminal or every class has zero reach."
        )

    # Step 2: expand to 1326-combo ranges with per-combo weights.
    hero_range = expand_classes_to_range(continuation.hero, board=board)
    villain_range = expand_classes_to_range(continuation.villain, board=board)
    t_after_expand = time.perf_counter()
    if len(hero_range) == 0:
        raise ValueError(
            f"hero range expansion produced zero combos on board "
            f"{list(board)!r}; every continuation combo blocked."
        )
    if len(villain_range) == 0:
        raise ValueError(
            f"villain range expansion produced zero combos on board "
            f"{list(board)!r}; every continuation combo blocked."
        )

    # Step 3: postflop subgame solve.
    pot = int(continuation.pot_chips)
    half = pot // 2
    contribs = (half, pot - half)
    if n_board == 3:
        starting_street = Street.FLOP
    elif n_board == 4:
        starting_street = Street.TURN
    else:
        starting_street = Street.RIVER
    postflop_cfg = replace(
        config_template,
        starting_street=starting_street,
        initial_board=tuple(board),
        initial_pot=pot,
        initial_contributions=contribs,
        initial_hole_cards=(),
    )

    postflop = solve_range_vs_range_nash(
        postflop_cfg,
        hero_range=hero_range,
        villain_range=villain_range,
        iterations=iterations,
        hero_player=hero_player,
        compute_exploitability_at_end=compute_exploitability_at_end,
    )
    t_after_solve = time.perf_counter()

    return BlueprintPostflopResult(
        postflop=postflop,
        continuation=continuation,
        hero_range=hero_range,
        villain_range=villain_range,
        wall_time_total_s=t_after_solve - t_start,
        wall_time_lookup_s=t_after_lookup - t_start,
        wall_time_expand_s=t_after_expand - t_after_lookup,
        wall_time_solve_s=t_after_solve - t_after_expand,
    )


__all__ = [
    "BlueprintContinuationRanges",
    "BlueprintPostflopResult",
    "derive_continuation_ranges_from_blueprint",
    "expand_classes_to_range",
    "solve_postflop_from_blueprint",
]
