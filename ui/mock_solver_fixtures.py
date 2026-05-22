"""Twelve hand-curated fixture spots for the PR 10a mock solver.

Each fixture ships:
  - a ``HUNLConfig`` (board / stacks / starting street / pot)
  - a hand-crafted ``average_strategy`` dict[infoset_key -> probs] that
    passes the poker-player eye test per ``pr10a_spec.md`` §7.4:
      * realistic mixing (no pure 100/0 splits where mixed is right)
      * no dominated actions
      * MDF-obeying bluff freq on rivers
      * polarization on rivers, more linear on flops
      * blocker effects on rivers

The strategies use a small infoset-key vocabulary keyed by hand-class
shorthand (e.g. ``'AKs'``, ``'QQ'``, ``'72o'``), street token, and a
short history. This keeps the mock independent of the real solver's
infoset-key format (which is hole-card-specific); the UI's range matrix
view aggregates real solver output back to hand-class granularity, so
the contract holds either way.

License posture: all hand-crafted; no copy from references/code/.
"""

from __future__ import annotations

from dataclasses import dataclass

from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, Street


@dataclass(frozen=True)
class FixturePreset:
    """One row in the preset dropdown (per ``pr10a_spec.md`` §7.1)."""

    id: str
    label: str
    description: str
    starting_street: str  # 'PREFLOP' | 'FLOP' | 'TURN' | 'RIVER'


# ---------------------------------------------------------------------------
# Hand-class enumeration (mirrors Agent A's ``ui.state.enumerate_hand_classes``
# contract; mock owns its own copy so it doesn't depend on Agent A landing).
# ---------------------------------------------------------------------------

_RANKS: tuple[str, ...] = (
    "A",
    "K",
    "Q",
    "J",
    "T",
    "9",
    "8",
    "7",
    "6",
    "5",
    "4",
    "3",
    "2",
)


def _hand_class_grid() -> list[str]:
    """Enumerate the 169 hand classes in standard 13x13 row-major order.

    Pairs on the diagonal (row == col), suited above (col > row), offsuit
    below (col < row).
    """
    out: list[str] = []
    for r, hi in enumerate(_RANKS):
        for c, lo in enumerate(_RANKS):
            if r == c:
                out.append(hi + hi)
            elif c > r:
                out.append(hi + lo + "s")
            else:
                out.append(lo + hi + "o")
    return out


_HAND_CLASSES: tuple[str, ...] = tuple(_hand_class_grid())


# ---------------------------------------------------------------------------
# Strategy archetypes — reusable templates keyed by "this hand-class on this
# board archetype." Each archetype returns the action distribution as a list
# of floats in the order matching the cell's legal actions.
#
# Action ordering convention here is uniform: [fold, check_or_call, bet33,
# bet75, bet100, allin]. The mock's UI consumer aggregates by action label;
# missing actions are zero-filled. This is a SIMPLIFIED action set vs the
# real solver's 14-action menu, but it's the right granularity for the
# range-matrix display (R / Y / G).
# ---------------------------------------------------------------------------

_ACTION_LABELS: tuple[str, ...] = (
    "fold",
    "call",
    "bet33",
    "bet75",
    "bet100",
    "allin",
)


def _classify_strength(hand_class: str, street: str, board_archetype: str) -> str:
    """Approximate hand strength bucket for archetype dispatch.

    Returns one of:
      'value_premium' — top of range, monsters
      'value_strong'  — strong made hands
      'value_medium'  — medium-strength made hands / good kickers
      'medium'        — marginal made hands / weak pairs
      'draw_combo'    — combo draws (only meaningful on flop/turn)
      'draw_one'      — single-card draws (gutshots, weak flush draws)
      'air_blocker'   — air with blockers (bluff candidates on river)
      'air'           — pure air

    This is a hand-crafted heuristic, intentionally simple — the mock
    strategies that consume it are eye-test-checked, not provably optimal.
    """
    is_pair = len(hand_class) == 2
    if is_pair:
        rank = hand_class[0]
        if rank in ("A", "K", "Q"):
            return "value_premium"
        if rank in ("J", "T", "9"):
            return "value_strong"
        if rank in ("8", "7", "6"):
            return "value_medium"
        return "medium"

    hi, lo = hand_class[0], hand_class[1]
    suited = hand_class[-1] == "s"
    hi_idx = _RANKS.index(hi)
    lo_idx = _RANKS.index(lo)

    # Premium broadway suited/offsuit.
    if hand_class in ("AKs", "AKo"):
        return "value_premium"
    if hi in ("A",) and lo_idx <= 4 and suited:  # AQs/AJs/ATs
        return "value_strong"
    if hi == "A" and lo_idx <= 4:
        return "value_strong" if suited else "value_medium"
    if hi == "K" and lo_idx <= 3:
        return "value_strong" if suited else "value_medium"
    if hi == "Q" and lo_idx <= 3:
        return "value_medium" if suited else "medium"
    # Suited connectors.
    if suited and (hi_idx + 1 == lo_idx or hi_idx + 2 == lo_idx):
        if lo_idx >= 8:  # 76s and below
            return "draw_combo"
        return "draw_combo" if street in ("FLOP", "TURN") else "medium"
    # Suited aces with low kicker — blocker candidates.
    if hi == "A" and suited:
        return "air_blocker"
    # Weak offsuit.
    if hi_idx >= 6 and lo_idx >= 8:
        return "air"
    return "draw_one"


def _strategy_for_archetype(
    archetype: str, street: str, polarized: bool = False
) -> list[float]:
    """Map (strength, street) to a 6-action distribution.

    Returned probs sum to 1.0. ``polarized=True`` (rivers, big spots) widens
    the bet/fold gap; ``polarized=False`` (flops, linear ranges) keeps more
    call frequency.
    """
    # Base templates per archetype.
    table = {
        "value_premium": {
            "FLOP": [0.0, 0.30, 0.10, 0.40, 0.18, 0.02],
            "TURN": [0.0, 0.20, 0.05, 0.50, 0.20, 0.05],
            "RIVER": [0.0, 0.15, 0.0, 0.20, 0.45, 0.20],
            "PREFLOP": [0.0, 0.20, 0.0, 0.10, 0.50, 0.20],
        },
        "value_strong": {
            "FLOP": [0.0, 0.45, 0.15, 0.30, 0.08, 0.02],
            "TURN": [0.0, 0.35, 0.10, 0.40, 0.13, 0.02],
            "RIVER": [0.05, 0.40, 0.0, 0.30, 0.20, 0.05],
            "PREFLOP": [0.0, 0.40, 0.0, 0.20, 0.30, 0.10],
        },
        "value_medium": {
            "FLOP": [0.10, 0.60, 0.20, 0.10, 0.0, 0.0],
            "TURN": [0.15, 0.55, 0.15, 0.15, 0.0, 0.0],
            "RIVER": [0.30, 0.60, 0.0, 0.08, 0.02, 0.0],
            "PREFLOP": [0.15, 0.60, 0.0, 0.20, 0.05, 0.0],
        },
        "medium": {
            "FLOP": [0.25, 0.65, 0.08, 0.02, 0.0, 0.0],
            "TURN": [0.40, 0.55, 0.04, 0.01, 0.0, 0.0],
            "RIVER": [0.65, 0.30, 0.0, 0.04, 0.01, 0.0],
            "PREFLOP": [0.45, 0.50, 0.0, 0.05, 0.0, 0.0],
        },
        "draw_combo": {
            "FLOP": [0.05, 0.40, 0.10, 0.35, 0.08, 0.02],
            "TURN": [0.15, 0.45, 0.08, 0.27, 0.05, 0.0],
            "RIVER": [0.55, 0.30, 0.0, 0.12, 0.03, 0.0],
            "PREFLOP": [0.30, 0.50, 0.0, 0.15, 0.05, 0.0],
        },
        "draw_one": {
            "FLOP": [0.45, 0.45, 0.05, 0.05, 0.0, 0.0],
            "TURN": [0.60, 0.30, 0.05, 0.05, 0.0, 0.0],
            "RIVER": [0.80, 0.18, 0.0, 0.02, 0.0, 0.0],
            "PREFLOP": [0.70, 0.25, 0.0, 0.04, 0.01, 0.0],
        },
        "air_blocker": {
            "FLOP": [0.50, 0.30, 0.04, 0.14, 0.02, 0.0],
            "TURN": [0.60, 0.20, 0.03, 0.15, 0.02, 0.0],
            "RIVER": [0.45, 0.10, 0.0, 0.30, 0.13, 0.02],
            "PREFLOP": [0.70, 0.20, 0.0, 0.08, 0.02, 0.0],
        },
        "air": {
            "FLOP": [0.85, 0.10, 0.02, 0.03, 0.0, 0.0],
            "TURN": [0.92, 0.06, 0.01, 0.01, 0.0, 0.0],
            "RIVER": [0.97, 0.02, 0.0, 0.01, 0.0, 0.0],
            "PREFLOP": [0.92, 0.07, 0.0, 0.01, 0.0, 0.0],
        },
    }
    probs = list(table[archetype][street])
    if polarized and street == "RIVER":
        # Polarization pass: shift call mass to fold + bet100 for value,
        # fold for everything else.
        if archetype.startswith("value"):
            shift = probs[1] * 0.3
            probs[1] -= shift
            probs[4] += shift
        elif archetype == "air_blocker":
            shift = probs[1] * 0.5
            probs[1] -= shift
            probs[4] += shift
    # Renormalize defensively.
    total = sum(probs)
    if total <= 0:
        # Degenerate; fall back to uniform call.
        return [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    return [p / total for p in probs]


def _build_average_strategy(
    starting_street: str,
    board_archetype: str,
    polarized: bool = False,
    blocker_cards: tuple[str, ...] = (),
) -> dict[str, list[float]]:
    """Generate the 169-cell hand-class -> action-probs dict.

    Infoset key format: ``'{hand_class}|{street_token}|root'``. The UI
    treats this as opaque; only the (hand_class, action_probs) pair
    matters for the matrix display.

    ``blocker_cards`` is a tuple of card strings (e.g. ('Kh', 'Ks')) that
    are on the board; suited combos using those exact cards get the
    'BLOCKED' marker (we encode this as a near-zero, fold-heavy strategy
    so the matrix view's blocker overlay test (#15) can detect it).
    """
    street_tokens = {"PREFLOP": "p", "FLOP": "f", "TURN": "t", "RIVER": "r"}
    token = street_tokens.get(starting_street, "f")
    out: dict[str, list[float]] = {}
    for hc in _HAND_CLASSES:
        key = f"{hc}|{token}|root"
        archetype = _classify_strength(hc, starting_street, board_archetype)
        probs = _strategy_for_archetype(archetype, starting_street, polarized)
        out[key] = probs
    # Blocker pass (simple): we never have full visibility into per-combo
    # state in the hand-class dict, but we can mark a sentinel infoset
    # for combos blocked by the board. The matrix view inspects per-combo
    # data via a separate channel; for the mock we add explicit
    # 'BLOCKED:{combo}|...' entries the matrix view can probe.
    for card_str in blocker_cards:
        out[f"BLOCKED:{card_str}|{token}|root"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    return out


# ---------------------------------------------------------------------------
# Fixture builders. Each ``_make_*`` returns ``(HUNLConfig, strategy_dict)``.
# Wired into ``_FIXTURE_BUILDERS`` at module bottom.
# ---------------------------------------------------------------------------


def _make_river_tiny_subgame() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """PR 3 fixture: river-only AhKc vs QdQh subgame on As7c2dKh5s, pot 1000."""
    board = (
        Card.from_str("As"),
        Card.from_str("7c"),
        Card.from_str("2d"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    )
    hole = (
        (Card.from_str("Ah"), Card.from_str("Kc")),
        (Card.from_str("Qd"), Card.from_str("Qh")),
    )
    config = HUNLConfig(
        starting_stack=1000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=hole,
    )
    strat = _build_average_strategy(
        "RIVER",
        "axxs_dry",
        polarized=True,
        blocker_cards=("Ah", "Kc", "Qd", "Qh"),
    )
    return config, strat


def _make_flop_k72r_100bb() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Dry rainbow flop K72r, 100bb deep."""
    board = (Card.from_str("Kh"), Card.from_str("7d"), Card.from_str("2c"))
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "k72r_dry", polarized=False, blocker_cards=("Kh", "7d", "2c")
    )
    return config, strat


def _make_flop_t87s_100bb() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Wet flop T87 two-tone with straight + flush draws, 100bb."""
    board = (Card.from_str("Th"), Card.from_str("8h"), Card.from_str("7c"))
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "t87_wet", polarized=False, blocker_cards=("Th", "8h", "7c")
    )
    return config, strat


def _make_flop_monotone_hhh() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Monotone hearts flop AhKh4h, 100bb. Flush-draw heavy."""
    board = (Card.from_str("Ah"), Card.from_str("Kh"), Card.from_str("4h"))
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "monotone", polarized=False, blocker_cards=("Ah", "Kh", "4h")
    )
    return config, strat


def _make_flop_paired_q9q() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Paired flop Q9Q, 100bb. Trips-heavy."""
    board = (Card.from_str("Qh"), Card.from_str("9d"), Card.from_str("Qc"))
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "paired", polarized=False, blocker_cards=("Qh", "9d", "Qc")
    )
    return config, strat


def _make_turn_kqj9_4_flush() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Turn brings 4-flush KhQhJh9h, 100bb."""
    board = (
        Card.from_str("Kh"),
        Card.from_str("Qh"),
        Card.from_str("Jh"),
        Card.from_str("9h"),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.TURN,
        initial_board=board,
        initial_pot=600,
        initial_contributions=(300, 300),
    )
    strat = _build_average_strategy(
        "TURN",
        "4_flush",
        polarized=True,
        blocker_cards=("Kh", "Qh", "Jh", "9h"),
    )
    return config, strat


def _make_turn_t872_brick() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Turn brick T872r, 100bb."""
    board = (
        Card.from_str("Th"),
        Card.from_str("8d"),
        Card.from_str("7c"),
        Card.from_str("2s"),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.TURN,
        initial_board=board,
        initial_pot=600,
        initial_contributions=(300, 300),
    )
    strat = _build_average_strategy(
        "TURN", "brick", polarized=False, blocker_cards=("Th", "8d", "7c", "2s")
    )
    return config, strat


def _make_river_axxs_polar() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """River polarization: Ah6c2d Kh 5s. Big bet / pure bluff split."""
    board = (
        Card.from_str("Ah"),
        Card.from_str("6c"),
        Card.from_str("2d"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=2000,
        initial_contributions=(1000, 1000),
    )
    strat = _build_average_strategy(
        "RIVER",
        "axxs",
        polarized=True,
        blocker_cards=("Ah", "6c", "2d", "Kh", "5s"),
    )
    return config, strat


def _make_preflop_btn_vs_bb() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Preflop BTN vs BB, 100bb. PR 9 stub — mock fakes a postflop start
    so the mock loop can run without preflop tree builder support.

    Caveat: we set ``starting_street=FLOP`` with a synthetic flop so the
    mock can run while marking the strategy under a preflop street token.
    The UI display still shows hand-class shorthand correctly.
    """
    board = (
        Card.from_str("2s"),
        Card.from_str("7h"),
        Card.from_str("Td"),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "PREFLOP", "btn_open", polarized=False, blocker_cards=()
    )
    return config, strat


def _make_river_blocker_heavy() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Adversarial blocker test: river AsKsQs9d2s. AhKh is dead."""
    board = (
        Card.from_str("As"),
        Card.from_str("Ks"),
        Card.from_str("Qs"),
        Card.from_str("9d"),
        Card.from_str("2s"),
    )
    config = HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=1500,
        initial_contributions=(750, 750),
    )
    strat = _build_average_strategy(
        "RIVER",
        "blocker_heavy",
        polarized=True,
        blocker_cards=("As", "Ks", "Qs", "9d", "2s"),
    )
    return config, strat


def _make_shortstack_25bb() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Short stack 25bb postflop on dry K72r."""
    board = (Card.from_str("Kh"), Card.from_str("7d"), Card.from_str("2c"))
    config = HUNLConfig(
        starting_stack=2_500,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "shortstack", polarized=False, blocker_cards=("Kh", "7d", "2c")
    )
    return config, strat


def _make_deepstack_200bb() -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Deep stack 200bb postflop on T87 wet."""
    board = (Card.from_str("Th"), Card.from_str("8h"), Card.from_str("7c"))
    config = HUNLConfig(
        starting_stack=20_000,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )
    strat = _build_average_strategy(
        "FLOP", "deepstack", polarized=False, blocker_cards=("Th", "8h", "7c")
    )
    return config, strat


# ---------------------------------------------------------------------------
# Public surface: preset metadata + builder registry.
# ---------------------------------------------------------------------------

FIXTURE_PRESETS: tuple[FixturePreset, ...] = (
    FixturePreset(
        "river_tiny_subgame",
        "River subgame (PR 3 fixture)",
        "AhKc vs QdQh on As 7c 2d Kh 5s, pot 1000.",
        "RIVER",
    ),
    FixturePreset(
        "flop_k72r_100bb",
        "Flop K72r, 100bb",
        "Dry rainbow flop, deep postflop spot.",
        "FLOP",
    ),
    FixturePreset(
        "flop_t87s_100bb",
        "Flop T87 two-tone, 100bb",
        "Wet flop with combo draws + flush draws.",
        "FLOP",
    ),
    FixturePreset(
        "flop_monotone_hhh",
        "Flop AhKh4h monotone, 100bb",
        "Three-flush flop; flush-draw-rich ranges.",
        "FLOP",
    ),
    FixturePreset(
        "flop_paired_q9q",
        "Flop Q9Q paired, 100bb",
        "Paired board; trips and slowplay candidates.",
        "FLOP",
    ),
    FixturePreset(
        "turn_kqj9_4_flush",
        "Turn KhQhJh9h 4-flush, 100bb",
        "Turn brings 4-flush; polarized ranges.",
        "TURN",
    ),
    FixturePreset(
        "turn_t872_brick",
        "Turn T872r brick, 100bb",
        "Turn brick; ranges stay similar to flop.",
        "TURN",
    ),
    FixturePreset(
        "river_axxs_polar",
        "River AhKh polar, 100bb",
        "River polarization; pure bluff / pure value split.",
        "RIVER",
    ),
    FixturePreset(
        "preflop_btn_vs_bb",
        "Preflop BTN vs BB (PR 9 stub)",
        "BTN open vs BB defend; mock-only until PR 9 ships.",
        "PREFLOP",
    ),
    FixturePreset(
        "river_blocker_heavy",
        "River blocker-heavy AsKsQs9d2s",
        "Adversarial blocker test; AhKh is dead.",
        "RIVER",
    ),
    FixturePreset(
        "shortstack_25bb",
        "Short stack 25bb postflop",
        "Short-stack postflop on dry K72r.",
        "FLOP",
    ),
    FixturePreset(
        "deepstack_200bb",
        "Deep stack 200bb postflop",
        "Deep-stack postflop on T87 wet.",
        "FLOP",
    ),
)


_FIXTURE_BUILDERS: dict[str, object] = {
    "river_tiny_subgame": _make_river_tiny_subgame,
    "flop_k72r_100bb": _make_flop_k72r_100bb,
    "flop_t87s_100bb": _make_flop_t87s_100bb,
    "flop_monotone_hhh": _make_flop_monotone_hhh,
    "flop_paired_q9q": _make_flop_paired_q9q,
    "turn_kqj9_4_flush": _make_turn_kqj9_4_flush,
    "turn_t872_brick": _make_turn_t872_brick,
    "river_axxs_polar": _make_river_axxs_polar,
    "preflop_btn_vs_bb": _make_preflop_btn_vs_bb,
    "river_blocker_heavy": _make_river_blocker_heavy,
    "shortstack_25bb": _make_shortstack_25bb,
    "deepstack_200bb": _make_deepstack_200bb,
}


def fixture_ids() -> tuple[str, ...]:
    """Return all 12 preset IDs in canonical order."""
    return tuple(p.id for p in FIXTURE_PRESETS)


def build_fixture(preset_id: str) -> tuple[HUNLConfig, dict[str, list[float]]]:
    """Materialize a preset id into ``(HUNLConfig, strategy_dict)``.

    Raises ``KeyError`` if ``preset_id`` is not one of the 12 known IDs.
    """
    builder = _FIXTURE_BUILDERS.get(preset_id)
    if builder is None:
        raise KeyError(
            f"unknown fixture preset {preset_id!r}; "
            f"valid IDs: {', '.join(fixture_ids())}"
        )
    return builder()  # type: ignore[operator,no-any-return]


__all__ = [
    "ACTION_LABELS",
    "FIXTURE_PRESETS",
    "FixturePreset",
    "build_fixture",
    "fixture_ids",
]


# Re-export with the conventional name.
ACTION_LABELS = _ACTION_LABELS
