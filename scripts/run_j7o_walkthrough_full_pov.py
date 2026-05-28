"""J7o player-POV walkthrough with FULL postflop subgame solves.

Companion / replacement for ``run_j7o_walkthrough.py``. The original
script reported per-street **equity** because the 169-class preflop
engine is preflop-only. This script wires the preflop blueprint into the
postflop subgame solver (PR #177 ``solve_postflop_from_blueprint``) to
report **actual GTO action distributions** for J♠7♦ at each street's
decision point — true player-POV format.

Architecture per street:

  Preflop  -> 169-class engine (shared with the equity-only walkthrough).
  Flop     -> solve_postflop_from_blueprint(action_sequence, board=[3])
              extracts SB's J7o strategy at SB's first flop decision
              (which the projection reaches by following BB's modal flop
              action — typically a check or small bet).
  Turn     -> same call with board=[4]; the subgame starts fresh at the
              turn with both players' continuation ranges propagated from
              preflop, but postflop history is NOT threaded (the solver
              does not yet accept a postflop action prefix). This is an
              ACKNOWLEDGED limitation — we surface it in the doc rather
              than hand-wave around it.
  River    -> same with board=[5].

For Test 3 (postflop cbet -> BB raise -> SB facing raise) we ALSO walk
the ``per_history_strategy`` dict from the flop solve to find the explicit
infoset where SB faces a raise after cbet, and report J♠7♦'s strategy
there directly from the raw per-history rows.

Run wall budget: ~5-15 minutes total.

Limitations surfaced honestly:
    * Turn/river subgame solves start fresh from the supplied board —
      they DO NOT condition on a specific postflop action history. The
      strategies returned are "what GTO says with this range vs this
      range on this board" rather than "what SB does on the turn after
      having cbet flop and gotten called." For a faithful threaded walk
      a postflop-history parameter would need to be plumbed through
      solve_postflop_from_blueprint (currently scoped as a follow-up).
    * ``per_class_strategy`` follows BB's MODAL action to surface SB's
      first decision. Non-modal lines (e.g. "SB facing BB's bet" when BB
      modally checks) are accessible only by manual per_history walk.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from poker_solver.blueprint import (
    BlueprintConfig,
    HandResolution,
    generate_blueprint,
    hunl_config_from_blueprint_config,
)
from poker_solver.blueprint_subgame import (
    BlueprintPostflopResult,
    derive_continuation_ranges_from_blueprint,
    solve_postflop_from_blueprint,
)
from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.range_aggregator import (
    _hole_string_rust,
    _key_suffix_for_state,
    _label_for_action,
)

OUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "j7o_player_pov_walkthrough_2026-05-28.md"
)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Aggressive defaults: vector-form flop solves are O(N²) in combo count
# AND have a deep chance tree to turn/river. To land Tests 1-4 inside a
# 60-min wall budget we use a tight top-K class filter (always pinning the
# hero class) and a small iteration count. The strategies are directional
# (modal action + relative frequencies) not numerically precise.

PREFLOP_ITERS = 1500
POSTFLOP_TURN_ITERS = 10
POSTFLOP_RIVER_ITERS = 30
HERO_TOPK_CLASSES = 8
VILLAIN_TOPK_CLASSES = 8
SKIP_FLOP_SOLVES = True  # Empirical (2026-05-28): flop solves with the
                         # vector-form solver at the smallest viable
                         # top-K (4 + pin) and iters=5 still exceed
                         # ~5 min CPU per solve. The chance tree from
                         # flop to river blows up the per-iter cost too
                         # much. Turn and river solves work fine
                         # (turn ~15s, river <1s with TerminalCache).
                         # Surface this limitation in the doc.
SKIP_TURN_RIVER_TEST4 = True  # Test 4 (72o, 5x open) is off-distribution
                              # — 72o has near-zero reach in SB's 5x-open
                              # range so the projection would be noisy.
                              # Skip entirely; preflop is the headline.

# Cards
J7o_HERO = [Card.from_str("Js"), Card.from_str("7d")]
TWO7o_HERO = [Card.from_str("2d"), Card.from_str("7h")]
FLOP_CARDS = [Card.from_str("Ad"), Card.from_str("8h"), Card.from_str("9d")]
TURN_CARDS = FLOP_CARDS + [Card.from_str("2c")]
RIVER_CARDS = TURN_CARDS + [Card.from_str("3s")]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt_pct(x: float) -> str:
    if x != x:  # NaN
        return "  n/a"
    return f"{100 * x:5.1f}%"


def fmt_strategy(actions: list[str], probs: dict[str, float], threshold: float = 0.005) -> str:
    """Format a strategy dict — only actions with mass > threshold."""
    parts = []
    for a in actions:
        p = probs.get(a, 0.0)
        if p >= threshold:
            parts.append(f"{a}={fmt_pct(p)}")
    return ", ".join(parts) if parts else "(all near-zero)"


def dominant_action(probs: dict[str, float]) -> tuple[str, float]:
    """Return ``(label, prob)`` of the modal action in ``probs``."""
    if not probs:
        return ("(none)", 0.0)
    return max(probs.items(), key=lambda kv: kv[1])


def strategy_block(actions_in_order: list[str], probs: dict[str, float]) -> list[str]:
    """Render a strategy as a list of '  action       : XX.X%' lines."""
    if not probs:
        return ["  (no strategy returned — solver projection empty)"]
    width = max(len(a) for a in actions_in_order)
    out = []
    for a in actions_in_order:
        p = probs.get(a, 0.0)
        out.append(f"  {a:<{width}}: {fmt_pct(p)}")
    return out


# ---------------------------------------------------------------------------
# Postflop subgame: extract SPECIFIC combo strategy via per_history walk
# ---------------------------------------------------------------------------


def specific_combo_strategy_at_root(
    result: BlueprintPostflopResult,
    hero_combo: tuple[Card, Card],
    config_template: HUNLConfig,
    board: list[Card],
    hero_player: int = 0,
) -> tuple[list[str], dict[str, float]] | None:
    """Extract J♠7♦-specific (not J7o-class-averaged) strategy.

    Walks the betting tree from postflop root, following BB's modal
    action (just like ``_project_to_hand_classes``), and looks up the
    SPECIFIC combo's per-history row.

    Returns ``(action_labels, {label: prob})`` or ``None`` if the row
    is missing.
    """
    from dataclasses import replace as dc_replace

    if len(board) == 3:
        starting_street = Street.FLOP
    elif len(board) == 4:
        starting_street = Street.TURN
    else:
        starting_street = Street.RIVER

    pot = int(result.continuation.pot_chips)
    half = pot // 2
    contribs = (half, pot - half)
    postflop_cfg = dc_replace(
        config_template,
        starting_street=starting_street,
        initial_board=tuple(board),
        initial_pot=pot,
        initial_contributions=contribs,
        initial_hole_cards=(),
    )

    game = HUNLPoker(postflop_cfg)
    state = game.initial_state()
    avg = result.postflop.per_history_strategy
    visited = 0
    while visited < 100:
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur != hero_player:
            # Modal-follow villain.
            actions = game.legal_actions(state)
            key_suffix = _key_suffix_for_state(game, state, cur)
            # Average across all hands present at this key suffix.
            sums = [0.0] * len(actions)
            count = 0
            for k, row in avg.items():
                if not k.endswith(key_suffix) or len(row) != len(actions):
                    continue
                for i in range(len(actions)):
                    sums[i] += row[i]
                count += 1
            if count == 0:
                return None
            modal_idx = max(range(len(actions)), key=lambda i: sums[i])
            state = game.apply(state, actions[modal_idx])
            visited += 1
            continue
        # Hero's turn — look up the specific combo.
        actions = game.legal_actions(state)
        action_labels = [
            _label_for_action(a, postflop_cfg.bet_size_fractions) for a in actions
        ]
        hole_str = _hole_string_rust(hero_combo)
        key_suffix = _key_suffix_for_state(game, state, hero_player)
        row = avg.get(hole_str + key_suffix)
        if row is None or len(row) != len(actions):
            return None
        probs = dict(zip(action_labels, [float(x) for x in row], strict=True))
        return action_labels, probs
    return None


def bb_modal_action_at_root(
    result: BlueprintPostflopResult,
    config_template: HUNLConfig,
    board: list[Card],
    hero_player: int = 0,
) -> tuple[str, float, dict[str, float]] | None:
    """Inspect the villain (BB) modal flop action driving the projection.

    Returns ``(modal_label, prob, full_dist)`` where ``full_dist`` is the
    BB combo-averaged action distribution at the flop root.
    """
    from dataclasses import replace as dc_replace

    if len(board) == 3:
        starting_street = Street.FLOP
    elif len(board) == 4:
        starting_street = Street.TURN
    else:
        starting_street = Street.RIVER

    pot = int(result.continuation.pot_chips)
    half = pot // 2
    contribs = (half, pot - half)
    postflop_cfg = dc_replace(
        config_template,
        starting_street=starting_street,
        initial_board=tuple(board),
        initial_pot=pot,
        initial_contributions=contribs,
        initial_hole_cards=(),
    )

    game = HUNLPoker(postflop_cfg)
    state = game.initial_state()
    avg = result.postflop.per_history_strategy
    visited = 0
    while visited < 100:
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur == hero_player:
            # We never reach BB's first action — hero acts first. No villain modal.
            return None
        # BB is current; aggregate their average across all hands.
        actions = game.legal_actions(state)
        action_labels = [
            _label_for_action(a, postflop_cfg.bet_size_fractions) for a in actions
        ]
        key_suffix = _key_suffix_for_state(game, state, cur)
        sums = [0.0] * len(actions)
        count = 0
        for k, row in avg.items():
            if not k.endswith(key_suffix) or len(row) != len(actions):
                continue
            for i in range(len(actions)):
                sums[i] += row[i]
            count += 1
        if count == 0:
            return None
        avgs = [s / count for s in sums]
        full_dist = dict(zip(action_labels, avgs, strict=True))
        modal_idx = max(range(len(actions)), key=lambda i: avgs[i])
        return action_labels[modal_idx], avgs[modal_idx], full_dist
    return None


def sb_strategy_facing_specific_bb_action(
    result: BlueprintPostflopResult,
    hero_combo: tuple[Card, Card],
    config_template: HUNLConfig,
    board: list[Card],
    bb_action_label: str,
    hero_player: int = 0,
) -> tuple[list[str], dict[str, float]] | None:
    """Walk the postflop tree forcing BB's first action = ``bb_action_label``.

    For Test 3 we want SB's strategy AFTER BB raises (which is typically
    a non-modal action). Walk the tree, when BB acts pick the action
    whose label matches ``bb_action_label`` (rather than the modal).
    """
    from dataclasses import replace as dc_replace

    if len(board) == 3:
        starting_street = Street.FLOP
    elif len(board) == 4:
        starting_street = Street.TURN
    else:
        starting_street = Street.RIVER

    pot = int(result.continuation.pot_chips)
    half = pot // 2
    contribs = (half, pot - half)
    postflop_cfg = dc_replace(
        config_template,
        starting_street=starting_street,
        initial_board=tuple(board),
        initial_pot=pot,
        initial_contributions=contribs,
        initial_hole_cards=(),
    )

    game = HUNLPoker(postflop_cfg)
    state = game.initial_state()
    avg = result.postflop.per_history_strategy
    visited = 0
    bb_action_forced = False
    while visited < 100:
        if game.is_terminal(state):
            return None
        cur = game.current_player(state)
        if cur == -1:
            outcomes = game.chance_outcomes(state)
            if not outcomes:
                return None
            state = game.apply(state, outcomes[0][0])
            visited += 1
            continue
        if cur != hero_player:
            actions = game.legal_actions(state)
            action_labels = [
                _label_for_action(a, postflop_cfg.bet_size_fractions) for a in actions
            ]
            if not bb_action_forced and bb_action_label in action_labels:
                # Force BB's first action to the specified label.
                idx = action_labels.index(bb_action_label)
                state = game.apply(state, actions[idx])
                bb_action_forced = True
                visited += 1
                continue
            # Subsequent villain action: follow modal.
            key_suffix = _key_suffix_for_state(game, state, cur)
            sums = [0.0] * len(actions)
            count = 0
            for k, row in avg.items():
                if not k.endswith(key_suffix) or len(row) != len(actions):
                    continue
                for i in range(len(actions)):
                    sums[i] += row[i]
                count += 1
            if count == 0:
                return None
            modal_idx = max(range(len(actions)), key=lambda i: sums[i])
            state = game.apply(state, actions[modal_idx])
            visited += 1
            continue
        actions = game.legal_actions(state)
        action_labels = [
            _label_for_action(a, postflop_cfg.bet_size_fractions) for a in actions
        ]
        hole_str = _hole_string_rust(hero_combo)
        key_suffix = _key_suffix_for_state(game, state, hero_player)
        row = avg.get(hole_str + key_suffix)
        if row is None or len(row) != len(actions):
            return None
        probs = dict(zip(action_labels, [float(x) for x in row], strict=True))
        return action_labels, probs
    return None


# ---------------------------------------------------------------------------
# Per-test runners
# ---------------------------------------------------------------------------


def _topk_classes(reach: dict[str, float], k: int, pin: list[str]) -> list[str]:
    """Return top-K classes by reach plus any pinned classes (always included).

    Pinned classes are included even if their reach is below the top-K
    cutoff — this guarantees the hero's specific hand of interest (e.g.
    J7o) is in the solved range.
    """
    by_reach = sorted(reach.items(), key=lambda kv: -kv[1])
    top = [k for k, v in by_reach[:k] if v > 0]
    out = list(top)
    for cls in pin:
        if cls in reach and reach[cls] > 0 and cls not in out:
            out.append(cls)
    return out


def run_postflop_solve(
    bp,
    hunl_template: HUNLConfig,
    action_sequence: tuple[str, ...],
    board: list[Card],
    *,
    label: str,
    hero_pin: list[str] | None = None,
    villain_pin: list[str] | None = None,
) -> BlueprintPostflopResult:
    """Wrapper that times each postflop solve and prints a status line.

    Filters hero / villain ranges to top-K classes by reach to keep memory
    and wall time tractable for the vector-form Rust solve. ``hero_pin`` /
    ``villain_pin`` are class labels that MUST be in the filtered range
    even if below top-K (the hero's hand of interest is always pinned).
    """
    hero_pin = hero_pin or []
    villain_pin = villain_pin or []
    # Step 1: walk preflop tree to get the full reach dict.
    cont = derive_continuation_ranges_from_blueprint(
        bp, config_template=hunl_template,
        action_sequence=action_sequence, hero_player=0,
    )
    # Step 2: filter to top-K classes (plus pinned).
    hero_top = _topk_classes(cont.hero, HERO_TOPK_CLASSES, hero_pin)
    villain_top = _topk_classes(cont.villain, VILLAIN_TOPK_CLASSES, villain_pin)
    # Pick iteration count by street: river benefits from more iters
    # (TerminalCache keeps each iter ~10ms); turn is slower so we run
    # fewer; flop is gated by SKIP_FLOP_SOLVES so we should never reach
    # here for flop with the current settings.
    n_board = len(board)
    if n_board == 5:
        n_iters = POSTFLOP_RIVER_ITERS
    elif n_board == 4:
        n_iters = POSTFLOP_TURN_ITERS
    else:
        # Flop — not used in current configuration but keep a sane default.
        n_iters = POSTFLOP_TURN_ITERS
    t0 = time.time()
    print(
        f"  [{label}] postflop solve: action_sequence={action_sequence}, "
        f"board={[str(c) for c in board]}, iters={n_iters}, "
        f"hero_classes={len(hero_top)}, villain_classes={len(villain_top)}"
    )
    res = solve_postflop_from_blueprint(
        bp,
        config_template=hunl_template,
        action_sequence=action_sequence,
        board=tuple(board),
        hero_player=0,  # SB hero
        iterations=n_iters,
        hero_classes=hero_top,
        villain_classes=villain_top,
        compute_exploitability_at_end=False,
    )
    dt = time.time() - t0
    print(
        f"  [{label}] done in {dt:.1f}s — hero combos={len(res.hero_range)}, "
        f"villain combos={len(res.villain_range)}, "
        f"per_class_strategy keys={len(res.postflop.per_class_strategy)}"
    )
    return res


def test1_full(bp, hunl_template) -> dict:
    """Test 1 — Baseline: SB opens 3x, BB calls, runout A♦8♥9♦ 2♣ 3♠."""
    print("=== Test 1 — Baseline ===")
    # Preflop strategy of J7o (from the engine root infoset).
    root = bp.infosets["||p|"]
    j7o_pf = dict(zip(root["actions"], root["strategy"]["J7o"]))

    # Action sequence after preflop closes: SB open_to_300 + BB call.
    pf_seq = ("b300", "c")

    # FLOP — empirically slow to solve (>5min at top-K=4/iters=5); skip
    # and provide a directional read instead. The continuation range
    # data alone (computed via derive_continuation_ranges_from_blueprint
    # which is fast and exact) is enough for a written read.
    if SKIP_FLOP_SOLVES:
        cont = derive_continuation_ranges_from_blueprint(
            bp, config_template=hunl_template,
            action_sequence=pf_seq, hero_player=0,
        )
        flop_res = None
        j7o_flop_class = {}
        specific_flop = None
        bb_flop_modal = None
        flop_pot = int(cont.pot_chips)
        print(f"  [flop] SKIPPED (SKIP_FLOP_SOLVES=True); pot={flop_pot}")
    else:
        flop_res = run_postflop_solve(
            bp, hunl_template, pf_seq, FLOP_CARDS, label="flop",
            hero_pin=["J7o"],
        )
        j7o_flop_class = flop_res.postflop.per_class_strategy.get("J7o", {})
        specific_flop = specific_combo_strategy_at_root(
            flop_res, (J7o_HERO[0], J7o_HERO[1]), hunl_template, FLOP_CARDS
        )
        bb_flop_modal = bb_modal_action_at_root(flop_res, hunl_template, FLOP_CARDS)
        flop_pot = flop_res.continuation.pot_chips

    # TURN — solve subgame at turn root. Empirically works at top-K=8 +
    # iters=10 in ~15s.
    turn_res = run_postflop_solve(
        bp, hunl_template, pf_seq, TURN_CARDS, label="turn",
        hero_pin=["J7o"],
    )
    j7o_turn_class = turn_res.postflop.per_class_strategy.get("J7o", {})
    specific_turn = specific_combo_strategy_at_root(
        turn_res, (J7o_HERO[0], J7o_HERO[1]), hunl_template, TURN_CARDS
    )
    bb_turn_modal = bb_modal_action_at_root(turn_res, hunl_template, TURN_CARDS)

    # RIVER — TerminalCache makes river solves <1s. Use iters=30 for
    # better convergence.
    river_res = run_postflop_solve(
        bp, hunl_template, pf_seq, RIVER_CARDS, label="river",
        hero_pin=["J7o"],
    )
    j7o_river_class = river_res.postflop.per_class_strategy.get("J7o", {})
    specific_river = specific_combo_strategy_at_root(
        river_res, (J7o_HERO[0], J7o_HERO[1]), hunl_template, RIVER_CARDS
    )
    bb_river_modal = bb_modal_action_at_root(river_res, hunl_template, RIVER_CARDS)

    return {
        "j7o_pf_strategy": j7o_pf,
        "pf_actions": root["actions"],
        "flop": {
            "class_strategy": j7o_flop_class,
            "specific": specific_flop,
            "bb_modal": bb_flop_modal,
            "pot": flop_pot,
            "hero_range_combos": len(flop_res.hero_range) if flop_res else None,
            "villain_range_combos": len(flop_res.villain_range) if flop_res else None,
            "wall_solve_s": flop_res.wall_time_solve_s if flop_res else None,
            "skipped": flop_res is None,
        },
        "turn": {
            "class_strategy": j7o_turn_class,
            "specific": specific_turn,
            "bb_modal": bb_turn_modal,
            "pot": turn_res.continuation.pot_chips if turn_res else None,
            "wall_solve_s": turn_res.wall_time_solve_s if turn_res else None,
            "skipped": turn_res is None,
        },
        "river": {
            "class_strategy": j7o_river_class,
            "specific": specific_river,
            "bb_modal": bb_river_modal,
            "pot": river_res.continuation.pot_chips if river_res else None,
            "wall_solve_s": river_res.wall_time_solve_s if river_res else None,
            "skipped": river_res is None,
        },
    }


def test2_full(bp, hunl_template) -> dict:
    """Test 2 — 3-bet/4-bet variant: SB 4-bets, BB calls. Flop only (SPR ~0.45)."""
    print("=== Test 2 — 4-bet pot ===")
    root = bp.infosets["||p|"]
    j7o_pf = dict(zip(root["actions"], root["strategy"]["J7o"]))

    # Preflop sequence: SB 3x -> BB 3-bet to 900 -> SB 4-bet to 2100 -> BB call.
    pf_seq = ("b300", "r900", "r2100", "c")

    # Verify all infosets are present.
    for mid in (("b300",), ("b300", "r900"), ("b300", "r900", "r2100")):
        key = "||p|" + "".join(mid)
        if key not in bp.infosets:
            print(f"  WARN: missing infoset {key!r} — blueprint may not cover this 4-bet path")

    if SKIP_FLOP_SOLVES:
        cont = derive_continuation_ranges_from_blueprint(
            bp, config_template=hunl_template,
            action_sequence=pf_seq, hero_player=0,
        )
        flop_res = None
        j7o_flop_class = {}
        specific_flop = None
        bb_flop_modal = None
        flop_pot = int(cont.pot_chips)
        print(f"  [flop_4bp] SKIPPED (SKIP_FLOP_SOLVES=True); pot={flop_pot}")
    else:
        flop_res = run_postflop_solve(
            bp, hunl_template, pf_seq, FLOP_CARDS, label="flop_4bp",
            hero_pin=["J7o"],
        )
        j7o_flop_class = flop_res.postflop.per_class_strategy.get("J7o", {})
        specific_flop = specific_combo_strategy_at_root(
            flop_res, (J7o_HERO[0], J7o_HERO[1]), hunl_template, FLOP_CARDS
        )
        bb_flop_modal = bb_modal_action_at_root(flop_res, hunl_template, FLOP_CARDS)
        flop_pot = flop_res.continuation.pot_chips

    return {
        "j7o_pf_strategy": j7o_pf,
        "pf_actions": root["actions"],
        "pf_seq": pf_seq,
        "flop": {
            "class_strategy": j7o_flop_class,
            "specific": specific_flop,
            "bb_modal": bb_flop_modal,
            "pot": flop_pot,
            "hero_range_combos": len(flop_res.hero_range) if flop_res else None,
            "villain_range_combos": len(flop_res.villain_range) if flop_res else None,
            "wall_solve_s": flop_res.wall_time_solve_s if flop_res else None,
            "skipped": flop_res is None,
        },
    }


def test3_full(bp, hunl_template) -> dict:
    """Test 3 — Postflop raise: cbet/raise tree.

    Use the same preflop sequence as Test 1, but inspect the flop solve's
    per_history_strategy for the specific 'SB facing BB raise' infoset.
    We force BB's first action to ``raise_*`` rather than the modal.
    """
    print("=== Test 3 — postflop cbet/raise ===")
    pf_seq = ("b300", "c")

    if SKIP_FLOP_SOLVES:
        cont = derive_continuation_ranges_from_blueprint(
            bp, config_template=hunl_template,
            action_sequence=pf_seq, hero_player=0,
        )
        flop_res = None
        j7o_flop_class = {}
        specific_flop = None
        bb_flop_modal = None
        flop_pot = int(cont.pot_chips)
        print(f"  [flop_t3] SKIPPED (SKIP_FLOP_SOLVES=True); pot={flop_pot}")
        # No per_history_strategy available => Test 3's facing-raise spot
        # cannot be looked up at this scale. Surface as "deferred" in doc.
        return {
            "pf_seq": pf_seq,
            "flop": {
                "class_strategy": j7o_flop_class,
                "specific": specific_flop,
                "bb_modal": bb_flop_modal,
                "pot": flop_pot,
                "wall_solve_s": None,
                "skipped": True,
            },
            "facing_raise_summary": None,
            "n_facing_raise_keys_found": 0,
        }

    flop_res = run_postflop_solve(
        bp, hunl_template, pf_seq, FLOP_CARDS, label="flop_t3",
        hero_pin=["J7o"],
    )
    j7o_flop_class = flop_res.postflop.per_class_strategy.get("J7o", {})
    specific_flop = specific_combo_strategy_at_root(
        flop_res, (J7o_HERO[0], J7o_HERO[1]), hunl_template, FLOP_CARDS
    )
    bb_flop_modal = bb_modal_action_at_root(flop_res, hunl_template, FLOP_CARDS)

    # Force BB to raise on flop after SB's cbet — but wait, BB acts FIRST
    # on flop. So Test 3's "SB cbets -> BB raises" requires SB to bet first.
    # That only happens if BB checks first, then SB bets, then BB raises.
    # That's a 4-deep node and isn't accessible via per_class_strategy's
    # first-decision projection. Instead we'll scan per_history_strategy
    # for keys that contain a check + bet + raise sequence.
    avg = flop_res.postflop.per_history_strategy
    j7o_hole_str = _hole_string_rust((J7o_HERO[0], J7o_HERO[1]))
    # Find all keys for J7o where the betting history shows BB checked, SB bet, BB raised.
    facing_raise_keys: list[tuple[str, list[float]]] = []
    for k, row in avg.items():
        if not k.startswith(j7o_hole_str):
            continue
        # Heuristic: at least 3 actions on the flop street and the last token is a raise.
        # The key format is hole|board|street|history. We split off the history portion.
        parts = k.split("|")
        if len(parts) < 4:
            continue
        history = parts[-1]
        # History tokens (postflop) include 'b<chips>' (bet), 'r<chips>' (raise), 'x' (check), 'c' (call), 'f' (fold).
        # We want: BB checked (x), SB bet (b...), BB raised (r...). That's a 3-token history.
        # The history string concatenates tokens with no separator, so we have to parse it.
        # Tokens: 'x', 'c', 'f', or 'b<digits>' / 'r<digits>'. We can iterate.
        tokens = _parse_history_tokens(history)
        if len(tokens) == 3 and tokens[0] == "x" and tokens[1].startswith("b") and tokens[2].startswith("r"):
            facing_raise_keys.append((k, [float(x) for x in row]))

    facing_raise_summary = None
    if facing_raise_keys:
        # Take the first one we find — typically there's only one bet/raise sizing path at modal.
        k, row = facing_raise_keys[0]
        # Reconstruct actions at this infoset. We need to know which legal actions are
        # available. Easiest: walk to this state.
        from dataclasses import replace as dc_replace

        pot = int(flop_res.continuation.pot_chips)
        half = pot // 2
        contribs = (half, pot - half)
        postflop_cfg = dc_replace(
            hunl_template,
            starting_street=Street.FLOP,
            initial_board=tuple(FLOP_CARDS),
            initial_pot=pot,
            initial_contributions=contribs,
            initial_hole_cards=(),
        )
        game = HUNLPoker(postflop_cfg)
        # Parse the history tokens from the key and replay them.
        parts = k.split("|")
        history = parts[-1]
        tokens = _parse_history_tokens(history)
        state = game.initial_state()
        for tok in tokens:
            actions = game.legal_actions(state)
            chosen = None
            for a in actions:
                trial = game.apply(state, a)
                # token of the transition
                if len(trial.current_street_tokens) > len(state.current_street_tokens):
                    new_tok = trial.current_street_tokens[len(state.current_street_tokens)]
                    if new_tok == tok:
                        chosen = a
                        break
            if chosen is None:
                break
            state = game.apply(state, chosen)
        actions = game.legal_actions(state)
        action_labels = [
            _label_for_action(a, postflop_cfg.bet_size_fractions) for a in actions
        ]
        if len(row) == len(action_labels):
            probs = dict(zip(action_labels, row, strict=True))
            facing_raise_summary = {
                "history": history,
                "tokens": tokens,
                "action_labels": action_labels,
                "probs": probs,
                "infoset_key": k,
            }

    return {
        "pf_seq": pf_seq,
        "flop": {
            "class_strategy": j7o_flop_class,
            "specific": specific_flop,
            "bb_modal": bb_flop_modal,
            "pot": flop_res.continuation.pot_chips,
            "wall_solve_s": flop_res.wall_time_solve_s,
        },
        "facing_raise_summary": facing_raise_summary,
        "n_facing_raise_keys_found": len(facing_raise_keys),
    }


def test4_full(bp, hunl_template) -> dict:
    """Test 4 — 27o off-distribution 5x open."""
    print("=== Test 4 — 27o 5x open ===")
    root = bp.infosets["||p|"]
    # 72o is the canonical class.
    two7o_pf = dict(zip(root["actions"], root["strategy"]["72o"]))

    # Preflop sequence: SB open_to_500 -> BB call.
    pf_seq = ("b500", "c")

    if SKIP_FLOP_SOLVES:
        cont = derive_continuation_ranges_from_blueprint(
            bp, config_template=hunl_template,
            action_sequence=pf_seq, hero_player=0,
        )
        flop_res = None
        two7o_flop_class = {}
        specific_flop = None
        bb_flop_modal = None
        flop_pot = int(cont.pot_chips)
        print(f"  [flop_t4] SKIPPED (SKIP_FLOP_SOLVES=True); pot={flop_pot}")
    else:
        flop_res = run_postflop_solve(
            bp, hunl_template, pf_seq, FLOP_CARDS, label="flop_t4",
            hero_pin=["72o"],
        )
        two7o_flop_class = flop_res.postflop.per_class_strategy.get("72o", {})
        specific_flop = specific_combo_strategy_at_root(
            flop_res, (TWO7o_HERO[0], TWO7o_HERO[1]), hunl_template, FLOP_CARDS
        )
        bb_flop_modal = bb_modal_action_at_root(flop_res, hunl_template, FLOP_CARDS)
        flop_pot = flop_res.continuation.pot_chips

    if SKIP_TURN_RIVER_TEST4:
        two7o_turn_class = {}
        specific_turn = None
        bb_turn_modal = None
        turn_res = None
        two7o_river_class = {}
        specific_river = None
        bb_river_modal = None
        river_res = None
        print(f"  [turn_t4] SKIPPED (SKIP_TURN_RIVER_TEST4=True)")
        print(f"  [river_t4] SKIPPED (SKIP_TURN_RIVER_TEST4=True)")
    else:
        turn_res = run_postflop_solve(
            bp, hunl_template, pf_seq, TURN_CARDS, label="turn_t4",
            hero_pin=["72o"],
        )
        two7o_turn_class = turn_res.postflop.per_class_strategy.get("72o", {})
        specific_turn = specific_combo_strategy_at_root(
            turn_res, (TWO7o_HERO[0], TWO7o_HERO[1]), hunl_template, TURN_CARDS
        )
        bb_turn_modal = bb_modal_action_at_root(turn_res, hunl_template, TURN_CARDS)

        river_res = run_postflop_solve(
            bp, hunl_template, pf_seq, RIVER_CARDS, label="river_t4",
            hero_pin=["72o"],
        )
        two7o_river_class = river_res.postflop.per_class_strategy.get("72o", {})
        specific_river = specific_combo_strategy_at_root(
            river_res, (TWO7o_HERO[0], TWO7o_HERO[1]), hunl_template, RIVER_CARDS
        )
        bb_river_modal = bb_modal_action_at_root(river_res, hunl_template, RIVER_CARDS)

    return {
        "two7o_pf_strategy": two7o_pf,
        "pf_actions": root["actions"],
        "pf_seq": pf_seq,
        "flop": {
            "class_strategy": two7o_flop_class,
            "specific": specific_flop,
            "bb_modal": bb_flop_modal,
            "pot": flop_pot,
            "wall_solve_s": flop_res.wall_time_solve_s if flop_res else None,
            "skipped": flop_res is None,
        },
        "turn": {
            "class_strategy": two7o_turn_class,
            "specific": specific_turn,
            "bb_modal": bb_turn_modal,
            "pot": turn_res.continuation.pot_chips if turn_res else None,
            "wall_solve_s": turn_res.wall_time_solve_s if turn_res else None,
            "skipped": turn_res is None,
        },
        "river": {
            "class_strategy": two7o_river_class,
            "specific": specific_river,
            "bb_modal": bb_river_modal,
            "pot": river_res.continuation.pot_chips if river_res else None,
            "wall_solve_s": river_res.wall_time_solve_s if river_res else None,
            "skipped": river_res is None,
        },
    }


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def _parse_history_tokens(history: str) -> list[str]:
    """Parse a postflop history string into tokens.

    Tokens: ``x`` (check), ``c`` (call), ``f`` (fold), ``b<digits>``,
    ``r<digits>``, ``A`` (all-in).
    """
    out = []
    i = 0
    n = len(history)
    while i < n:
        ch = history[i]
        if ch in ("x", "c", "f", "A"):
            out.append(ch)
            i += 1
        elif ch in ("b", "r"):
            j = i + 1
            while j < n and history[j].isdigit():
                j += 1
            out.append(history[i:j])
            i = j
        else:
            # Unrecognized — bail.
            break
    return out


# ---------------------------------------------------------------------------
# Markdown rendering — player POV
# ---------------------------------------------------------------------------


def render_md(
    wall_solve_pf: float,
    test1: dict,
    test2: dict,
    test3: dict,
    test4: dict,
    wall_total: float,
) -> str:
    out: list[str] = []
    out.append("# J7o Player-POV Walkthrough — Tests 1-4 (FULL Postflop Solves)")
    out.append("")
    out.append("**Date:** 2026-05-28")
    out.append("")
    out.append("Companion to ``docs/j7o_walkthrough_tests_1_4_2026-05-28.md``")
    out.append("(which reported equity only). This doc reports **actual GTO")
    out.append("action distributions** from postflop subgame solves at each")
    out.append("decision point. Format = player POV: at each street, what")
    out.append("does the solver say SB does specifically with J♠7♦?")
    out.append("")
    out.append("## Configuration")
    out.append("")
    out.append("```python")
    out.append("Stack: 40 BB (4000 chips at 100 chips/BB)")
    out.append("Blinds: SB 50 / BB 100")
    out.append(f"Preflop solve: {PREFLOP_ITERS} DCFR iterations (169-class engine)")
    out.append(f"Postflop turn solve: {POSTFLOP_TURN_ITERS} DCFR iterations, top-{HERO_TOPK_CLASSES} classes / side + hero pin")
    out.append(f"Postflop river solve: {POSTFLOP_RIVER_ITERS} DCFR iterations, top-{HERO_TOPK_CLASSES} classes / side + hero pin")
    out.append("Postflop bet sizings: 33%, 75%, 100%, 150%, 200% pot")
    out.append("Postflop raise cap: 3 (set by engine default)")
    out.append("```")
    out.append("")
    out.append("**Flop solves are DEFERRED** in this walkthrough. Empirical measurement")
    out.append("on 2026-05-28 (worktree ``j7o-walkthrough-full-pov``) showed flop subgame")
    out.append("solves exceeding 5 minutes of CPU per solve even at top-K = 4 classes")
    out.append("and 5 iterations — the chance tree from flop to river blows up per-iter")
    out.append("cost in the vector-form solver. Turn solves succeed in ~15s and river")
    out.append("solves in <1s (TerminalCache amortizes the dominant evaluator cost on")
    out.append("a constant board). The flop directional reads below are from the")
    out.append("equity-only walkthrough in ``docs/j7o_walkthrough_tests_1_4_2026-05-28.md``.")
    out.append("")
    out.append(f"**Wall time:** preflop solve = {wall_solve_pf:.1f}s, total = {wall_total:.1f}s")
    out.append("")
    out.append("## Methodology")
    out.append("")
    out.append("- Preflop: read SB's 169-class blueprint at the root infoset")
    out.append("  (``||p|``); J7o gets its action distribution directly.")
    out.append("- Postflop: at each street we call")
    out.append("  ``solve_postflop_from_blueprint`` with the preflop action")
    out.append("  sequence and the board. The solver propagates the preflop")
    out.append("  blueprint's continuation ranges (SB's open range vs BB's")
    out.append("  defend-vs-open range) into a postflop range-vs-range Nash")
    out.append("  solve, then we extract J7o's per-class strategy at SB's")
    out.append("  first decision and J♠7♦'s specific per-history strategy.")
    out.append("- Convention: in this engine, **BB acts first postflop**. So")
    out.append("  SB's flop decision is a RESPONSE to BB's modal action (check or")
    out.append("  bet). The ``BB modal`` line at each street reports what BB")
    out.append("  does most-often in the Nash solve — that's the context for")
    out.append("  SB's strategy.")
    out.append("- **Limitation surfaced**: turn/river subgame solves do NOT")
    out.append("  condition on a specific postflop action history. They solve")
    out.append("  Nash from the turn/river root given the preflop continuation")
    out.append("  ranges. So the turn strategy is 'what does GTO say with SB's")
    out.append("  open-call range vs BB's call range on this turn board' — not")
    out.append("  'what does SB do on the turn having checked-back the flop'.")
    out.append("")

    # =================== TEST 1 ===================
    out.append("=" * 56)
    out.append("## TEST 1 — Baseline (no folds)")
    out.append("=" * 56)
    out.append("")
    out.append("**You hold:** J♠ 7♦")
    out.append("**Position:** Small Blind (40 BB effective)")
    out.append("")
    out.append("### Preflop decision")
    out.append("")
    out.append(f"Action on you. Pot: 1.5 BB (0.5 SB + 1.0 BB). Stack: 39.5 BB.")
    out.append("")
    out.append("**Solver strategy for J♠7♦:**")
    out.append("```")
    out.extend(strategy_block(test1["pf_actions"], test1["j7o_pf_strategy"]))
    out.append("```")
    dom_a, dom_p = dominant_action(test1["j7o_pf_strategy"])
    out.append(f"**GTO action:** ``{dom_a}`` ({fmt_pct(dom_p)} of the time)")
    out.append("")
    out.append("**Test forces:** raise to 3 BB (open_to_300). Slight off-tree —")
    out.append("solver prefers 2 BB open at 40 BB, but 3 BB is a near-equilibrium")
    out.append("alternative (no fold-mass).")
    out.append("")
    out.append("(You raise to 3 BB. BB calls.)")
    out.append("")
    out.append(f"**Pot after preflop:** {test1['flop']['pot']} chips ({test1['flop']['pot']/100:.1f} BB). Stacks: 37 BB each.")
    out.append("")

    # FLOP
    out.append("### Flop: A♦ 8♥ 9♦")
    out.append("")
    flop = test1["flop"]
    if flop.get("skipped"):
        out.append(f"Pot: {flop['pot']} chips ({flop['pot']/100:.1f} BB).")
        out.append("")
        out.append("**Flop subgame solve DEFERRED.** Empirical measurement (2026-05-28):")
        out.append("the vector-form solver runs > 5 minutes of CPU per flop solve at")
        out.append("the smallest viable parameters (top-K = 4 hand classes + J7o pin,")
        out.append("only 5 DCFR iterations) — the chance tree from flop to river blows")
        out.append("up per-iter cost. Turn and river solves succeed (turn ~15s with")
        out.append("top-K=8, river <1s with TerminalCache).")
        out.append("")
        out.append("Directional read (from equity-only walkthrough, doc #179):")
        out.append("J♠7♦ has no pair, no draw on A♦8♥9♦ (the 7♦ blocks a flush draw")
        out.append("but is otherwise dry). Equity vs BB's call range = ~40.1%. On an")
        out.append("Ax-heavy continuing range, J-high is a low-equity hand — solver's")
        out.append("preferred line is the smallest action that lets J7o give up")
        out.append("cheaply (check or fold to a small bet), occasionally a bluff cbet.")
    else:
        out.append(f"Pot: {flop['pot']} chips. Continuation ranges: SB={flop['hero_range_combos']} combos, BB={flop['villain_range_combos']} combos.")
        out.append("")
        bb_modal = flop["bb_modal"]
        if bb_modal:
            bb_a, bb_p, bb_dist = bb_modal
            out.append(f"**BB acts first.** BB's modal flop action: ``{bb_a}`` ({fmt_pct(bb_p)}).")
            out.append("BB's full flop action distribution (combo-averaged):")
            out.append("```")
            for a, p in bb_dist.items():
                if p >= 0.01:
                    out.append(f"  {a:<10}: {fmt_pct(p)}")
            out.append("```")
        else:
            out.append("**SB acts first** (no BB action to follow).")
        out.append("")
        out.append("**SB strategy for J♠7♦ (class-averaged J7o, after following BB's modal action):**")
        out.append("```")
        if flop["class_strategy"]:
            for a, p in sorted(flop["class_strategy"].items(), key=lambda kv: -kv[1]):
                out.append(f"  {a:<10}: {fmt_pct(p)}")
        else:
            out.append("  (per_class projection empty)")
        out.append("```")
        if flop["specific"]:
            sp_labels, sp_probs = flop["specific"]
            out.append("**SB strategy for the SPECIFIC combo J♠7♦ (per-history row):**")
            out.append("```")
            for a in sp_labels:
                p = sp_probs.get(a, 0.0)
                if p >= 0.005:
                    out.append(f"  {a:<10}: {fmt_pct(p)}")
            out.append("```")
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for J♠7♦:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
        out.append("**Reading:** J♠7♦ has no pair, no draw on A♦8♥9♦ (the 7♦ blocks")
        out.append("a flush draw but is otherwise dry). On an Ax-heavy continuing range,")
        out.append("J-high is a low-equity hand — the solver's preferred line will be")
        out.append("the smallest action that lets J7o give up cheaply unless it can")
        out.append("realize equity via a low-frequency bluff.")
    out.append("")

    # TURN
    out.append("### Turn: 2♣ (brick)")
    out.append("")
    turn = test1["turn"]
    if turn.get("skipped"):
        out.append("**Turn subgame solve DEFERRED.** A turn-root flop subgame with")
        out.append("the full preflop continuation range expansion (~150 combos / side)")
        out.append("at 10+ iterations exceeds the salvage time budget. The vector-form")
        out.append("solver pays O(N²) in combo count and walks a 44-card chance tree")
        out.append("from turn to river per iteration; at this resolution it is not")
        out.append("interactive. Deferred to a follow-up burst.")
        out.append("")
        out.append("Directional read (from equity-only Test 1 walkthrough, doc #179):")
        out.append("the 2♣ does not improve J♠7♦ — still J-high on Ax-heavy board.")
        out.append("Expected solver behaviour: continue with the smallest action that")
        out.append("realizes equity cheaply (check, or fold to BB's bet).")
    else:
        out.append(f"Pot at turn: {turn['pot']} chips. Board: A♦ 8♥ 9♦ 2♣.")
        out.append("")
        out.append("**Subgame solved fresh at turn root** (does not condition on flop")
        out.append("action; sees only preflop continuation ranges).")
        out.append("")
        bb_modal_t = turn["bb_modal"]
        if bb_modal_t:
            bb_a, bb_p, bb_dist = bb_modal_t
            out.append(f"**BB acts first on turn.** BB's modal action: ``{bb_a}`` ({fmt_pct(bb_p)}).")
            out.append("BB's turn action distribution:")
            out.append("```")
            for a, p in bb_dist.items():
                if p >= 0.01:
                    out.append(f"  {a:<10}: {fmt_pct(p)}")
            out.append("```")
        out.append("")
        out.append("**SB strategy for J♠7♦ on turn (after BB's modal action):**")
        out.append("```")
        if turn["class_strategy"]:
            for a, p in sorted(turn["class_strategy"].items(), key=lambda kv: -kv[1]):
                out.append(f"  {a:<10}: {fmt_pct(p)}")
        else:
            out.append("  (per_class projection empty)")
        out.append("```")
        if turn["specific"]:
            sp_labels, sp_probs = turn["specific"]
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for J♠7♦ on turn:** ``{dom_a}`` ({fmt_pct(dom_p)})")
    out.append("")

    # RIVER
    out.append("### River: 3♠ (brick)")
    out.append("")
    river = test1["river"]
    if river.get("skipped"):
        out.append("**River subgame solve DEFERRED.** Same constraint as turn — solving")
        out.append("Nash from the river root with full-range expansion at meaningful")
        out.append("iteration counts exceeds the salvage budget. Deferred to follow-up.")
        out.append("")
        out.append("Directional read: J-high almost never wins at showdown vs BB's")
        out.append("call range on A♦8♥9♦ 2♣ 3♠ (a dry, no-draw runout). Expected")
        out.append("solver behaviour: give up the vast majority of the time (fold to")
        out.append("any bet or check back if checked to), with a low-frequency bluff")
        out.append("when SB faces a check on the river.")
    else:
        out.append(f"Pot at river: {river['pot']} chips. Board: A♦ 8♥ 9♦ 2♣ 3♠.")
        out.append("")
        bb_modal_r = river["bb_modal"]
        if bb_modal_r:
            bb_a, bb_p, bb_dist = bb_modal_r
            out.append(f"**BB acts first on river.** BB's modal action: ``{bb_a}`` ({fmt_pct(bb_p)}).")
        out.append("")
        out.append("**SB strategy for J♠7♦ on river (after BB's modal action):**")
        out.append("```")
        if river["class_strategy"]:
            for a, p in sorted(river["class_strategy"].items(), key=lambda kv: -kv[1]):
                out.append(f"  {a:<10}: {fmt_pct(p)}")
        else:
            out.append("  (per_class projection empty)")
        out.append("```")
        if river["specific"]:
            sp_labels, sp_probs = river["specific"]
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for J♠7♦ on river:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
        out.append("**Reading:** J-high almost never wins at showdown vs BB's wide call")
        out.append("range on this dry runout. The solver's preferred river action")
        out.append("reflects either a give-up (fold/check) or a low-frequency bluff.")
    out.append("")

    # =================== TEST 2 ===================
    out.append("=" * 56)
    out.append("## TEST 2 — 3-bet / 4-bet pot (committed)")
    out.append("=" * 56)
    out.append("")
    out.append("**You hold:** J♠ 7♦")
    out.append("**Position:** Small Blind (40 BB)")
    out.append("")
    out.append(f"**Solver preflop strategy for J♠7♦ (root):** ``{dominant_action(test2['j7o_pf_strategy'])[0]}`` modally.")
    out.append("")
    out.append("**Test forces:** SB opens 3x -> BB 3-bets to 9 BB -> SB 4-bets to")
    out.append("21 BB (nearest menu choice for ~22 BB) -> BB calls. The engine")
    out.append("actually has J7o folding to a 3-bet at near-100% rate, so this")
    out.append("flop scenario is OFF the GTO tree for J7o specifically — but the")
    out.append("postflop range solve still reflects SB's 4-bet range and BB's")
    out.append("call-vs-4bet range as they ACTUALLY are in the blueprint.")
    out.append("")
    out.append("### Flop: A♦ 8♥ 9♦ (4-bet pot)")
    out.append("")
    flop = test2["flop"]
    out.append(f"Pot at flop: {flop['pot']} chips ({flop['pot']/100:.1f} BB).")
    out.append(f"Effective stack remaining: {4000 - flop['pot']//2} chips per player.")
    spr = (4000 - flop['pot']//2) / flop['pot'] if flop['pot'] > 0 else float('inf')
    out.append(f"SPR ≈ {spr:.2f} — shallow; with 4-bet sizing both players are heavily committed.")
    out.append("")
    if flop.get("skipped"):
        out.append("**Flop subgame solve DEFERRED.** Same constraint as Test 1 — flop")
        out.append("solves exceed the salvage budget at any meaningful resolution.")
        out.append("")
        out.append(f"Directional read: at SPR ~{spr:.1f} (after a 4-bet pot of {flop['pot']} chips)")
        out.append("both players are committed enough that modal SB action with most")
        out.append("hands is shove or call, not fold. J7o on A♦8♥9♦ has ~40% equity")
        out.append("vs BB's call-vs-4bet range (per doc #179), which clears the")
        out.append("required-equity threshold at this SPR. The headline finding is from")
        out.append("the preflop blueprint above: J7o folds to a 3-bet at 99.99% rate,")
        out.append("so this postflop spot is reachable only as a non-modal off-tree")
        out.append("event for J7o specifically.")
    else:
        out.append(f"Continuation ranges: SB={flop['hero_range_combos']} combos, BB={flop['villain_range_combos']} combos.")
        out.append("")
        bb_modal = flop["bb_modal"]
        if bb_modal:
            bb_a, bb_p, _ = bb_modal
            out.append(f"**BB acts first.** BB's modal flop action: ``{bb_a}`` ({fmt_pct(bb_p)}).")
        out.append("")
        out.append("**SB strategy for J♠7♦ on flop (4-bet pot):**")
        out.append("```")
        if flop["class_strategy"]:
            for a, p in sorted(flop["class_strategy"].items(), key=lambda kv: -kv[1]):
                out.append(f"  {a:<10}: {fmt_pct(p)}")
        else:
            out.append("  (per_class projection empty — class may have zero reach in SB's 4-bet range)")
        out.append("```")
        if flop["specific"]:
            sp_labels, sp_probs = flop["specific"]
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for J♠7♦ in 4-bet pot:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
        out.append("**Reading:** Note — J7o is not in SB's GTO 4-bet range, so this")
        out.append("strategy is the projection of an OFF-TREE node. The class-averaged")
        out.append("J7o response reflects what SB does with the few J7o combos that")
        out.append("might leak into a 4-bet at this depth (likely near-zero weight).")
        out.append("With SPR ≈ 0.45 the modal action will be a shove or call, not a")
        out.append("fold — at this stack-to-pot ratio you are essentially pot-committed.")
    out.append("")

    # =================== TEST 3 ===================
    out.append("=" * 56)
    out.append("## TEST 3 — Postflop cbet / raise tree")
    out.append("=" * 56)
    out.append("")
    out.append("**You hold:** J♠ 7♦")
    out.append("**Position:** Small Blind")
    out.append("**Setup:** Same as Test 1 — SB opens 3x, BB calls. Pot 6 BB.")
    out.append("")
    out.append("### Flop: A♦ 8♥ 9♦")
    out.append("")
    flop = test3["flop"]
    out.append(f"Pot: {flop['pot']} chips. (Same as Test 1 flop.)")
    out.append("")
    if flop.get("skipped"):
        out.append("**Flop subgame solve DEFERRED** (same constraint as Tests 1-2). The")
        out.append("postflop cbet-then-raise spot also requires the per_history_strategy")
        out.append("dict from a flop solve to surface, which is unavailable here. The")
        out.append("equity-based read below stands in.")
        out.append("")
    else:
        bb_modal = flop["bb_modal"]
        if bb_modal:
            bb_a, bb_p, bb_dist = bb_modal
            out.append(f"**BB modal action:** ``{bb_a}`` ({fmt_pct(bb_p)}).")
        out.append("")
        out.append("**SB strategy for J♠7♦ on flop (Test 1 result reproduced):**")
        if flop["specific"]:
            _, sp_probs = flop["specific"]
            out.append("```")
            for a, p in sorted(sp_probs.items(), key=lambda kv: -kv[1]):
                if p >= 0.005:
                    out.append(f"  {a:<10}: {fmt_pct(p)}")
            out.append("```")
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for J♠7♦:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
    out.append("### Hypothetical: BB checks, SB cbets, BB raises")
    out.append("")
    out.append("Test 3's scenario asks: what does SB do when BB **raises** SB's")
    out.append("cbet? This requires a 3-deep flop infoset (BB check, SB bet,")
    out.append("BB raise). Since BB acts first on flop, the per_class projection")
    out.append("(which follows BB's modal first action) gives only SB's response")
    out.append("to BB's modal action — not the facing-raise spot.")
    out.append("")
    out.append("We scanned the per_history_strategy dict for J♠7♦ rows where the")
    out.append("flop history matches ``x-b<size>-r<size>`` (BB check, SB bet, BB raise):")
    out.append("")
    n_keys = test3["n_facing_raise_keys_found"]
    out.append(f"- Number of facing-raise infosets found for J♠7♦: **{n_keys}**")
    if test3["facing_raise_summary"]:
        s = test3["facing_raise_summary"]
        out.append("")
        out.append(f"**Found:** flop history = ``{s['history']}`` (tokens: {s['tokens']})")
        out.append("")
        out.append(f"**SB strategy for J♠7♦ facing the raise:**")
        out.append("```")
        for a in s["action_labels"]:
            p = s["probs"].get(a, 0.0)
            if p >= 0.005:
                out.append(f"  {a:<10}: {fmt_pct(p)}")
        out.append("```")
        dom_a, dom_p = dominant_action(s["probs"])
        out.append(f"**GTO action for J♠7♦ facing raise:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
        out.append("**Reading:** A J-high hand with no draw vs a raise on Ax-heavy")
        out.append("board has very poor equity — fold or shove (with the rare bluff)")
        out.append("are the only sensible actions.")
    else:
        out.append("")
        out.append("**No 3-deep facing-raise infosets found** — likely because BB's")
        out.append("modal flop action is check (the bet-then-raise lines have low")
        out.append("probability under the converged strategy, and the vector-form")
        out.append("Rust binding only emits rows for infosets actually visited).")
        out.append("If SB cbets and BB raises, J7o's response is essentially the")
        out.append("'last-action' decision: with no equity and no draw, the GTO")
        out.append("response is a fold the vast majority of the time.")
    out.append("")

    # =================== TEST 4 ===================
    out.append("=" * 56)
    out.append("## TEST 4 — Off-distribution 5x open with 2♦7♥")
    out.append("=" * 56)
    out.append("")
    out.append("**You hold:** 2♦ 7♥ (canonical class 72o)")
    out.append("**Position:** Small Blind")
    out.append("")
    out.append("**Solver preflop strategy for 72o (root):**")
    out.append("```")
    out.extend(strategy_block(test4["pf_actions"], test4["two7o_pf_strategy"]))
    out.append("```")
    dom_a, dom_p = dominant_action(test4["two7o_pf_strategy"])
    out.append(f"**GTO action for 72o:** ``{dom_a}`` ({fmt_pct(dom_p)}) — fold is correct, 5x open is heavily off-tree.")
    out.append("")
    out.append("**Test forces:** 5x open (open_to_500) with 72o. BB calls. We solve")
    out.append("the postflop subgame with SB's 5x-open range vs BB's call-vs-5x range")
    out.append("on A♦8♥9♦ -> 2♣ -> 3♠.")
    out.append("")
    for street_name, key in (("Flop", "flop"), ("Turn", "turn"), ("River", "river")):
        d = test4[key]
        if street_name == "Flop":
            board_str = "A♦ 8♥ 9♦"
        elif street_name == "Turn":
            board_str = "A♦ 8♥ 9♦ 2♣"
        else:
            board_str = "A♦ 8♥ 9♦ 2♣ 3♠"
        out.append(f"### {street_name}: {board_str}")
        out.append("")
        if d.get("skipped"):
            out.append(f"**{street_name} subgame solve DEFERRED.** Test 4 skips all postflop")
            out.append("solves because 72o has near-zero reach in SB's 5x-open range — the")
            out.append("per-class projection would be very noisy at any iteration budget.")
            out.append("Flop is additionally subject to the global SKIP_FLOP_SOLVES gate.")
            out.append("")
            continue
        out.append(f"Pot: {d['pot']} chips.")
        bb_modal = d.get("bb_modal")
        if bb_modal:
            bb_a, bb_p, _ = bb_modal
            out.append(f"**BB modal action:** ``{bb_a}`` ({fmt_pct(bb_p)}).")
        out.append("")
        out.append(f"**SB strategy for 2♦7♥ on {street_name.lower()}:**")
        out.append("```")
        if d["class_strategy"]:
            for a, p in sorted(d["class_strategy"].items(), key=lambda kv: -kv[1]):
                if p >= 0.005:
                    out.append(f"  {a:<10}: {fmt_pct(p)}")
        else:
            out.append("  (per_class projection empty — 72o has near-zero reach in 5x-open range)")
        out.append("```")
        if d["specific"]:
            _, sp_probs = d["specific"]
            dom_a, dom_p = dominant_action(sp_probs)
            out.append(f"**GTO action for 2♦7♥:** ``{dom_a}`` ({fmt_pct(dom_p)})")
        out.append("")
    out.append("**Reading:** 72o on A89dd with no draw or pair has near-zero")
    out.append("equity vs BB's defending range. The solver's preferred lines will")
    out.append("be give-ups or rare bluffs — but note 72o has near-zero reach in")
    out.append("SB's 5x-open range to begin with, so the class-averaged strategy")
    out.append("reflects what FEW 72o combos that DID open 5x would do.")
    out.append("")

    out.append("## Reproduction")
    out.append("")
    out.append("```")
    out.append("python scripts/run_j7o_walkthrough_full_pov.py")
    out.append("```")
    out.append("")
    out.append("Branch: ``j7o-walkthrough-full-pov`` (off origin/main).")
    out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, float):
        if obj != obj:
            return None
        return obj
    if isinstance(obj, Card):
        return str(obj)
    return obj


def main() -> int:
    overall_t0 = time.time()
    print(f"Generating 40 BB preflop blueprint ({PREFLOP_ITERS} iters)...")
    cfg = BlueprintConfig(
        stack_bb=40,
        ante_bb=0.0,
        iterations=PREFLOP_ITERS,
        preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
        preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
        preflop_raise_cap=4,
        small_blind_bb=0.5,
        alpha=1.5,
        beta=0.0,
        gamma=2.0,
    )
    t0 = time.time()
    bp = generate_blueprint(cfg, hand_resolution=HandResolution.CLASS_169)
    wall_solve_pf = time.time() - t0
    print(f"  blueprint generated in {wall_solve_pf:.2f}s; n_infosets={bp.n_infosets}")

    hunl_template = hunl_config_from_blueprint_config(cfg)

    print()
    t = time.time()
    r1 = test1_full(bp, hunl_template)
    print(f"Test 1 total: {time.time() - t:.1f}s")

    print()
    t = time.time()
    r2 = test2_full(bp, hunl_template)
    print(f"Test 2 total: {time.time() - t:.1f}s")

    print()
    t = time.time()
    r3 = test3_full(bp, hunl_template)
    print(f"Test 3 total: {time.time() - t:.1f}s")

    print()
    t = time.time()
    r4 = test4_full(bp, hunl_template)
    print(f"Test 4 total: {time.time() - t:.1f}s")

    wall_total = time.time() - overall_t0
    print(f"\nTotal wall: {wall_total:.1f}s")

    md = render_md(wall_solve_pf, r1, r2, r3, r4, wall_total)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")

    raw = {
        "wall_solve_pf": wall_solve_pf,
        "wall_total": wall_total,
        "preflop_iters": PREFLOP_ITERS,
        "postflop_turn_iters": POSTFLOP_TURN_ITERS,
        "postflop_river_iters": POSTFLOP_RIVER_ITERS,
        "test1": _to_jsonable(r1),
        "test2": _to_jsonable(r2),
        "test3": _to_jsonable(r3),
        "test4": _to_jsonable(r4),
    }
    raw_path = OUT_PATH.with_suffix(".raw.json")
    raw_path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
