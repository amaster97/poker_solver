"""Wrapper around Noam Brown's river_solver_optimized for differential testing.

This file invokes (via subprocess) and parses output from
`noambrown/poker_solver` (https://github.com/noambrown/poker_solver, MIT
Licensed, Copyright (c) 2025 Noam Brown). No source code from that repo
is copied here; this wrapper depends only on the public CLI flags and
JSON output format documented in:

  - references/code/noambrown_poker_solver/cpp/src/main.cpp (CLI flags)
  - references/code/noambrown_poker_solver/cpp/src/main.cpp:222-290 (output schema)
  - references/code/noambrown_poker_solver/LICENSE (MIT terms)

License of the wrapper itself: MIT (same as this project).

Module layout
-------------
1. Dataclasses (``RiverSpot``, ``BrownStrategyDump`` and friends).
2. JSON fixture loader (``load_spots``) with strict validation.
3. Binary path resolver (``find_brown_binary``).
4. Subgame config writer (``write_brown_config``).
5. Subprocess driver (``run_brown_solver``) + stdout parsing.
6. History canonicalization (``canonicalize_brown_history`` and
   ``canonicalize_our_history``) — Brown's raise-extra-beyond-call
   encoding is normalized to our raise-to-total encoding so both halves
   of the diff harness use one shape.
7. Strategy reshaping (``our_strategy_to_brown_matrix``).

Reference invariants
--------------------
Brown's encoding (see ``cpp/src/main.cpp:176-194``) and ours (see
``poker_solver/hunl.py:390-437``) differ on three axes:

  * raise amount: Brown emits ``r<extra_beyond_call>``; we emit
    ``r<total_contributed>``. Canonical form: total-contributed.
  * check vs call: Brown emits ``c`` for both; we emit ``x`` (check) or
    ``c`` (call). Canonical form: ``("c", 0)`` for both.
  * all-in: Brown has no special token; emits the bet/raise amount. We
    emit ``"A"``. Canonical form: re-emit as ``("b", remaining)`` if no
    bet to call, else ``("r", actor_new_total)``.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from poker_solver.card import Card, parse_card
from poker_solver.solver import SolveResult

# ============================================================================
# Type aliases
# ============================================================================

#: Two-card hand: order is whatever the caller authors. Sorting / canonical
#: spelling for diff comparisons is the caller's responsibility — this type
#: is the raw user-facing combo.
Combo = tuple[Card, Card]

#: Canonical form of a history token (string ``"f"``/``"c"``/``"b"``/``"r"``
#: paired with an integer chip amount). ``"f"`` and ``"c"`` always carry
#: amount 0; ``"b"`` and ``"r"`` carry the (positive) chip amount in the
#: same to-total form our solver emits.
CanonicalToken = tuple[Literal["f", "c", "b", "r"], int]

#: A canonical history is a tuple of canonical tokens.
CanonicalHistory = tuple[CanonicalToken, ...]


# ============================================================================
# Dataclasses
# ============================================================================


@dataclass(frozen=True)
class RiverSpot:
    """A single river-spot fixture parsed from ``tests/data/river_spots.json``.

    Schema version 1. Hand-authored, no random seeds in construction.
    Tuples are used throughout for hashability / immutability so spots can
    be passed through ``pytest.mark.parametrize`` cleanly.
    """

    id: str
    description: str
    board: tuple[Card, ...]  # all 5 river cards
    pot: int  # integer chips
    stack: int  # integer chips, per player (symmetric)
    bet_sizes: tuple[float, ...]
    include_all_in: bool
    max_raises: int
    ranges: tuple[
        tuple[tuple[Combo, float], ...],  # player 0 (hand, weight) pairs
        tuple[tuple[Combo, float], ...],  # player 1
    ]
    iterations_override: int | None  # None → use default (2000)


@dataclass(frozen=True)
class BrownInfosetEntry:
    """One infoset row from Brown's strategy dump.

    Attributes:
        actions: per-action token list, e.g. ``("b500", "c", "f")``.
        strategy: per-hand × per-action probability matrix; shape
            ``(num_hands, num_actions)``. Brown stores it as
            ``list[list[float]]``; we keep tuple-of-tuple for hashability
            and let consumers convert to ``np.ndarray`` if needed.
    """

    actions: tuple[str, ...]
    strategy: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class BrownPlayerProfile:
    """One player's slice of Brown's strategy dump.

    ``hands`` is the post-board-filter hand list Brown actually iterated
    over (it drops hands sharing a card with the board on construction;
    see ``cpp/src/river_game.cpp:228-240``). Hand strings are Brown's
    sorted form (lowest-card-id first per ``cpp/src/cards.cpp:48-50``).
    """

    hands: tuple[str, ...]
    weights: tuple[float, ...]
    profile: dict[str, BrownInfosetEntry]  # key = "/"-joined history


@dataclass(frozen=True)
class BrownStrategyDump:
    """Parsed output from Brown's ``--dump-strategy`` JSON.

    ``game_value_p0`` and ``game_value_p1`` are populated only if Brown's
    stdout exposed them. The current binary (``cpp/src/main.cpp:440-471``)
    prints exploitability, not game value, so these fields are usually
    ``None`` — kept on the dataclass for forward compatibility with later
    Brown builds.
    """

    players: tuple[BrownPlayerProfile, BrownPlayerProfile]
    game_value_p0: float | None
    game_value_p1: float | None
    iterations_run: int
    exploitability_chips: float | None = None


# ============================================================================
# Constants
# ============================================================================

#: Brown's CLI defaults to seed 7 (``cpp/src/main.cpp:36``); we pass it
#: explicitly so the wrapper survives upstream default changes.
_DEFAULT_BROWN_SEED: int = 7

#: Brown's CLI defaults to 2000 iterations (``cpp/src/main.cpp:31``);
#: matched by us per PR 7 spec §5 step 2.
_DEFAULT_ITERATIONS: int = 2000

#: Subprocess timeout. Brown's binary on a typical spot finishes in
#: well under a minute; 600 s is a paranoid ceiling.
_DEFAULT_TIMEOUT_SEC: float = 600.0

#: DCFR hyperparameters locked by PLAN.md §1 (Brown & Sandholm 2019
#: paper defaults). Passed verbatim to Brown's CLI so both engines run
#: the same algorithm. Do not mutate at call sites.
_DCFR_ALPHA: float = 1.5
_DCFR_BETA: float = 0.0
_DCFR_GAMMA: float = 2.0


# ============================================================================
# Card / hand string helpers (Brown side)
# ============================================================================

# Brown's card string convention (cpp/src/cards.cpp:8-9):
#   ranks "23456789TJQKA", suits "cdhs". Lowercase suit.
# Our `parse_card` accepts the same lowercase-suit form (poker_solver/card.py:44).

_BROWN_RANK_CHARS: str = "23456789TJQKA"
_BROWN_SUIT_CHARS: str = "cdhs"
_BROWN_RANK_INDEX: dict[str, int] = {r: i for i, r in enumerate(_BROWN_RANK_CHARS)}
_BROWN_SUIT_INDEX: dict[str, int] = {s: i for i, s in enumerate(_BROWN_SUIT_CHARS)}


def _card_to_brown_str(card: Card) -> str:
    """Emit a card in Brown's two-char form (e.g. ``Ah``)."""
    rank_char = _BROWN_RANK_CHARS[card.rank - 2]
    suit_char = _BROWN_SUIT_CHARS[card.suit]
    return rank_char + suit_char


def _brown_card_id(card: Card) -> int:
    """Mirror of Brown's ``card_id`` (``cpp/src/cards.cpp:19-28``).

    Brown encodes a card as ``suit * 13 + rank`` where rank is 0..12
    (2..A) and suit is 0..3 (c d h s). We need this only to sort hand
    strings the same way Brown does (lowest id first).
    """
    rank_char = _BROWN_RANK_CHARS[card.rank - 2]
    suit_char = _BROWN_SUIT_CHARS[card.suit]
    return _BROWN_SUIT_INDEX[suit_char] * 13 + _BROWN_RANK_INDEX[rank_char]


def _combo_to_brown_hand_str(combo: Combo) -> str:
    """Render a 2-card combo as Brown's sorted hand string.

    Matches the swap in ``cpp/src/cards.cpp:48-50``: the lower-id card
    appears first, so ``(Ah, Ad)`` round-trips to ``"AdAh"``.
    """
    c1, c2 = combo
    id1, id2 = _brown_card_id(c1), _brown_card_id(c2)
    if id1 <= id2:
        return _card_to_brown_str(c1) + _card_to_brown_str(c2)
    return _card_to_brown_str(c2) + _card_to_brown_str(c1)


# ============================================================================
# Fixture loading
# ============================================================================


def _parse_combo(hand_str: str, *, spot_id: str) -> Combo:
    """Parse a 4-char hand string ``"AhKd"`` into a ``(Card, Card)`` tuple.

    Raises:
        ValueError if the string is malformed (with spot-id context).
    """
    if len(hand_str) != 4:
        raise ValueError(
            f"spot {spot_id!r}: hand string must be 4 chars (e.g. 'AhKd'); got {hand_str!r}"
        )
    try:
        c1 = parse_card(hand_str[0:2])
        c2 = parse_card(hand_str[2:4])
    except ValueError as exc:
        raise ValueError(f"spot {spot_id!r}: invalid hand {hand_str!r}: {exc}") from exc
    if c1 == c2:
        raise ValueError(f"spot {spot_id!r}: hand {hand_str!r} has duplicate cards")
    return (c1, c2)


def load_spots(path: Path) -> list[RiverSpot]:
    """Load + validate ``river_spots.json``.

    Validation gates (each raises ``ValueError`` referencing the spot id):

    - ``schema_version == 1``
    - exactly 2 players per spot
    - ``len(board) == 5`` (river has all 5 cards)
    - all 5 board cards distinct
    - every hand: 2 cards, both distinct, neither overlapping the board
    - all weights strictly positive
    - ``bet_sizes`` is a non-empty list of floats in ``(0, 5]``
    - ``pot > 0``, ``stack > 0``, both integers
    - ``max_raises >= 1``
    - at least 30 combos per side (per PR 7 §4 range design rule)
    """
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise ValueError(
            f"{path}: unsupported schema_version {schema_version!r}; expected 1"
        )
    raw_spots = raw.get("spots")
    if not isinstance(raw_spots, list) or not raw_spots:
        raise ValueError(f"{path}: 'spots' must be a non-empty list")

    spots: list[RiverSpot] = []
    seen_ids: set[str] = set()
    for entry in raw_spots:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every spot must be a JSON object")
        spot = _build_spot_from_json(entry)
        if spot.id in seen_ids:
            raise ValueError(f"{path}: duplicate spot id {spot.id!r}")
        seen_ids.add(spot.id)
        spots.append(spot)
    return spots


def _build_spot_from_json(entry: dict[str, Any]) -> RiverSpot:
    """Validate one JSON spot dict and return a ``RiverSpot``."""
    spot_id = entry.get("id")
    if not isinstance(spot_id, str) or not spot_id:
        raise ValueError(f"spot entry missing 'id': {entry!r}")
    description = entry.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"spot {spot_id!r}: 'description' must be a string")

    # Board: list of 5 distinct card strings.
    raw_board = entry.get("board")
    if not isinstance(raw_board, list) or len(raw_board) != 5:
        raise ValueError(
            f"spot {spot_id!r}: 'board' must have exactly 5 card strings, got {raw_board!r}"
        )
    board_cards: list[Card] = []
    for s in raw_board:
        if not isinstance(s, str):
            raise ValueError(
                f"spot {spot_id!r}: board entries must be card strings, got {s!r}"
            )
        try:
            board_cards.append(parse_card(s))
        except ValueError as exc:
            raise ValueError(
                f"spot {spot_id!r}: invalid board card {s!r}: {exc}"
            ) from exc
    if len(set(board_cards)) != 5:
        raise ValueError(f"spot {spot_id!r}: duplicate cards on board {raw_board!r}")
    board_set = set(board_cards)

    # Pot / stack: positive integers.
    pot = entry.get("pot")
    stack = entry.get("stack")
    if not isinstance(pot, int) or isinstance(pot, bool) or pot <= 0:
        raise ValueError(f"spot {spot_id!r}: 'pot' must be a positive int, got {pot!r}")
    if not isinstance(stack, int) or isinstance(stack, bool) or stack <= 0:
        raise ValueError(
            f"spot {spot_id!r}: 'stack' must be a positive int, got {stack!r}"
        )

    # Bet sizes: non-empty list of floats in (0, 5].
    raw_bet_sizes = entry.get("bet_sizes")
    if not isinstance(raw_bet_sizes, list) or not raw_bet_sizes:
        raise ValueError(
            f"spot {spot_id!r}: 'bet_sizes' must be a non-empty list of pot fractions"
        )
    bet_sizes: list[float] = []
    for v in raw_bet_sizes:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(
                f"spot {spot_id!r}: bet_sizes entries must be numbers, got {v!r}"
            )
        fv = float(v)
        if not (0.0 < fv <= 5.0):
            raise ValueError(
                f"spot {spot_id!r}: bet_sizes entry {fv!r} must be in (0, 5]"
            )
        bet_sizes.append(fv)

    include_all_in = entry.get("include_all_in", True)
    if not isinstance(include_all_in, bool):
        raise ValueError(f"spot {spot_id!r}: 'include_all_in' must be a bool")

    max_raises = entry.get("max_raises", 3)
    if (
        not isinstance(max_raises, int)
        or isinstance(max_raises, bool)
        or max_raises < 1
    ):
        raise ValueError(
            f"spot {spot_id!r}: 'max_raises' must be an int >= 1, got {max_raises!r}"
        )

    iterations_override = entry.get("iterations_override")
    if iterations_override is not None and (
        isinstance(iterations_override, bool)
        or not isinstance(iterations_override, int)
        or iterations_override < 1
    ):
        raise ValueError(
            f"spot {spot_id!r}: 'iterations_override' must be a positive int or null, "
            f"got {iterations_override!r}"
        )

    # Players: list of exactly 2 {hands, weights} dicts.
    raw_players = entry.get("players")
    if not isinstance(raw_players, list) or len(raw_players) != 2:
        raise ValueError(
            f"spot {spot_id!r}: 'players' must be a list of exactly 2 entries"
        )
    parsed_ranges: list[tuple[tuple[Combo, float], ...]] = []
    for idx, player in enumerate(raw_players):
        if not isinstance(player, dict):
            raise ValueError(f"spot {spot_id!r}: players[{idx}] must be a JSON object")
        hands = player.get("hands")
        weights = player.get("weights")
        if not isinstance(hands, list) or not hands:
            raise ValueError(
                f"spot {spot_id!r}: players[{idx}].hands must be a non-empty list"
            )
        if not isinstance(weights, list) or len(weights) != len(hands):
            raise ValueError(
                f"spot {spot_id!r}: players[{idx}].weights must match hands length "
                f"({len(weights) if isinstance(weights, list) else type(weights).__name__} "
                f"vs {len(hands)})"
            )
        pairs: list[tuple[Combo, float]] = []
        seen_combos: set[Combo] = set()
        for hand_str, weight in zip(hands, weights):
            if not isinstance(hand_str, str):
                raise ValueError(
                    f"spot {spot_id!r}: players[{idx}] hand entries must be strings"
                )
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(
                    f"spot {spot_id!r}: players[{idx}] weights must be numbers"
                )
            fw = float(weight)
            if fw <= 0.0:
                raise ValueError(
                    f"spot {spot_id!r}: players[{idx}] weight for {hand_str!r} must be > 0"
                )
            combo = _parse_combo(hand_str, spot_id=spot_id)
            if combo[0] in board_set or combo[1] in board_set:
                raise ValueError(
                    f"spot {spot_id!r}: players[{idx}] hand {hand_str!r} overlaps with board "
                    f"{raw_board!r}"
                )
            # Canonical combo (lower-card-id first) for dedup; the caller-facing
            # combo retains the authored order.
            canonical = (
                (combo[0], combo[1]) if combo[0] < combo[1] else (combo[1], combo[0])
            )
            if canonical in seen_combos:
                raise ValueError(
                    f"spot {spot_id!r}: players[{idx}] duplicates hand {hand_str!r}"
                )
            seen_combos.add(canonical)
            pairs.append((combo, fw))
        if len(pairs) < 30:
            raise ValueError(
                f"spot {spot_id!r}: players[{idx}] range has {len(pairs)} combos; "
                f"PR 7 §4 requires >=30 combos per side"
            )
        parsed_ranges.append(tuple(pairs))

    return RiverSpot(
        id=spot_id,
        description=description,
        board=tuple(board_cards),
        pot=pot,
        stack=stack,
        bet_sizes=tuple(bet_sizes),
        include_all_in=include_all_in,
        max_raises=max_raises,
        ranges=(parsed_ranges[0], parsed_ranges[1]),
        iterations_override=iterations_override,
    )


# ============================================================================
# Binary path resolution
# ============================================================================


def find_brown_binary() -> Path | None:
    """Resolve Brown's binary path or return None if it isn't built.

    Anchors at the repo root via ``Path(__file__).resolve().parents[2]``
    (``parity → poker_solver → repo root``). The canonical layout is
    ``<repo_root>/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized``;
    Brown's CMake configures with ``cpp/`` as the build root, so the
    artifact lands under ``cpp/build/`` (not directly under ``build/``).

    Never raises; if the file is missing or not executable, returns
    ``None`` so callers can ``pytest.skip`` cleanly.
    """
    repo_root = Path(__file__).resolve().parents[2]
    candidate = (
        repo_root
        / "references"
        / "code"
        / "noambrown_poker_solver"
        / "cpp"
        / "build"
        / "river_solver_optimized"
    )
    try:
        if candidate.is_file():
            # On POSIX, file_exists() is enough; check executability defensively.
            import os

            if os.access(str(candidate), os.X_OK):
                return candidate
    except OSError:
        return None
    return None


# ============================================================================
# Subgame config writer
# ============================================================================


def write_brown_config(spot: RiverSpot, path: Path) -> None:
    """Emit a JSON file in Brown's subgame schema.

    Schema source: ``cpp/src/subgame_config.h:7-22`` and
    ``cpp/src/subgame_config.cpp:303-388``. Brown's parser accepts:

    .. code-block:: json

        {
            "board": ["Ks", "7h", "2d", "4c", "Jh"],
            "pot": 1000,
            "stack": 9500,
            "bet_sizes": [0.75, 1.5],
            "include_all_in": true,
            "max_raises": 3,
            "players": [
                {"hands": ["AhKh", ...], "weights": [1.0, ...]},
                {"hands": ["QdQc", ...], "weights": [1.0, ...]}
            ]
        }

    Card-to-string convention matches Brown's ``cpp/src/cards.cpp``:
    rank in ``"23456789TJQKA"`` and suit in ``"cdhs"`` (lowercase).
    """
    config: dict[str, Any] = {
        "board": [_card_to_brown_str(c) for c in spot.board],
        "pot": int(spot.pot),
        "stack": int(spot.stack),
        "bet_sizes": [float(s) for s in spot.bet_sizes],
        "include_all_in": bool(spot.include_all_in),
        "max_raises": int(spot.max_raises),
        "players": [
            {
                "hands": [_combo_to_brown_hand_str(combo) for combo, _ in player_range],
                "weights": [float(weight) for _, weight in player_range],
            }
            for player_range in spot.ranges
        ],
    }
    path.write_text(json.dumps(config, indent=2))


# ============================================================================
# Subprocess driver
# ============================================================================


# Brown's stdout currently prints e.g.:
#   "Discounted CFR: iters=2000 Exploitability (chips): 0.123456 | ..."
# We don't need to parse this for correctness; the strategy dump is the
# source of truth. We do salvage exploitability when present, for
# downstream reporting. game_value lines are reserved for forward compat.
_EXPL_RE = re.compile(r"Exploitability \(chips\):\s*([0-9.+\-eE]+)")
_GAME_VALUE_RE = re.compile(r"game_value_p([01])[:=\s]+([0-9.+\-eE]+)")


def run_brown_solver(
    spot: RiverSpot,
    binary: Path,
    iterations: int = _DEFAULT_ITERATIONS,
    seed: int = _DEFAULT_BROWN_SEED,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
) -> BrownStrategyDump:
    """Invoke Brown's binary on ``spot`` and parse its strategy dump.

    Writes the subgame config + strategy dump under a private temp dir
    (so pytest-xdist parallel runs don't collide); cleans up on success
    or failure. Returns a fully parsed ``BrownStrategyDump``.

    Raises:
        FileNotFoundError if ``binary`` does not point at a real file.
        subprocess.CalledProcessError on non-zero exit from Brown.
        subprocess.TimeoutExpired if Brown exceeds ``timeout_sec``.
        ValueError if Brown's strategy dump is missing or malformed.
    """
    if not binary.is_file():
        raise FileNotFoundError(f"Brown's river_solver_optimized not found at {binary}")

    workdir = Path(tempfile.mkdtemp(prefix=f"noambrown_{spot.id}_"))
    try:
        config_path = workdir / "config.json"
        dump_path = workdir / "strategy.json"
        write_brown_config(spot, config_path)

        argv: list[str] = [
            str(binary),
            "--config",
            str(config_path),
            "--algo",
            "dcfr",
            "--iters",
            str(int(iterations)),
            "--dcfr-alpha",
            str(_DCFR_ALPHA),
            "--dcfr-beta",
            str(_DCFR_BETA),
            "--dcfr-gamma",
            str(_DCFR_GAMMA),
            "--seed",
            str(int(seed)),
            "--dump-strategy",
            str(dump_path),
        ]

        completed = subprocess.run(  # noqa: S603 — argv built from typed inputs
            argv,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

        if not dump_path.is_file():
            raise ValueError(
                f"Brown's --dump-strategy at {dump_path} was not written "
                f"(stdout: {completed.stdout!r}, stderr: {completed.stderr!r})"
            )
        with open(dump_path, encoding="utf-8") as fh:
            raw_dump = json.load(fh)

        # Stdout salvage: exploitability + (forward-compat) game value.
        gv_p0: float | None = None
        gv_p1: float | None = None
        expl: float | None = None
        for line in completed.stdout.splitlines():
            m = _EXPL_RE.search(line)
            if m:
                with contextlib.suppress(ValueError):
                    expl = float(m.group(1))
            for gm in _GAME_VALUE_RE.finditer(line):
                try:
                    val = float(gm.group(2))
                except ValueError:
                    continue
                if gm.group(1) == "0":
                    gv_p0 = val
                else:
                    gv_p1 = val
    finally:
        # Best-effort cleanup; ignore stragglers (e.g. NFS lag) so we never
        # mask the original exception when something inside fails.
        try:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)
        except OSError:
            pass

    return _parse_brown_dump(
        raw_dump,
        iterations_run=int(iterations),
        game_value_p0=gv_p0,
        game_value_p1=gv_p1,
        exploitability_chips=expl,
    )


def _parse_brown_dump(
    raw_dump: Any,
    *,
    iterations_run: int,
    game_value_p0: float | None,
    game_value_p1: float | None,
    exploitability_chips: float | None,
) -> BrownStrategyDump:
    """Translate Brown's JSON shape into ``BrownStrategyDump``.

    Brown's format (``cpp/src/main.cpp:222-290``):

    .. code-block:: json

        {"players": [
            {"hands": [...], "weights": [...], "profile": {
                "<key>": {"actions": [...], "strategy": [[...], ...]},
                ...
            }},
            {... same shape ...}
        ]}
    """
    if not isinstance(raw_dump, dict):
        raise ValueError("Brown dump: top-level must be a JSON object")
    players_raw = raw_dump.get("players")
    if not isinstance(players_raw, list) or len(players_raw) != 2:
        raise ValueError("Brown dump: 'players' must be a list of length 2")

    parsed_players: list[BrownPlayerProfile] = []
    for idx, p in enumerate(players_raw):
        if not isinstance(p, dict):
            raise ValueError(f"Brown dump: players[{idx}] must be an object")
        hands_raw = p.get("hands")
        weights_raw = p.get("weights")
        profile_raw = p.get("profile")
        if not isinstance(hands_raw, list):
            raise ValueError(f"Brown dump: players[{idx}].hands must be a list")
        if not isinstance(weights_raw, list):
            raise ValueError(f"Brown dump: players[{idx}].weights must be a list")
        if not isinstance(profile_raw, dict):
            raise ValueError(f"Brown dump: players[{idx}].profile must be an object")

        hands_tuple: tuple[str, ...] = tuple(str(h) for h in hands_raw)
        weights_tuple: tuple[float, ...] = tuple(float(w) for w in weights_raw)

        profile_entries: dict[str, BrownInfosetEntry] = {}
        for key, entry in profile_raw.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Brown dump: players[{idx}].profile[{key!r}] must be an object"
                )
            actions_raw = entry.get("actions")
            strategy_raw = entry.get("strategy")
            if not isinstance(actions_raw, list):
                raise ValueError(f"Brown dump: profile[{key!r}].actions must be a list")
            if not isinstance(strategy_raw, list):
                raise ValueError(
                    f"Brown dump: profile[{key!r}].strategy must be a list"
                )
            actions_tuple: tuple[str, ...] = tuple(str(a) for a in actions_raw)
            strategy_rows: list[tuple[float, ...]] = []
            for row in strategy_raw:
                if not isinstance(row, list):
                    raise ValueError(
                        f"Brown dump: profile[{key!r}].strategy rows must be lists"
                    )
                strategy_rows.append(tuple(float(v) for v in row))
            profile_entries[key] = BrownInfosetEntry(
                actions=actions_tuple,
                strategy=tuple(strategy_rows),
            )

        parsed_players.append(
            BrownPlayerProfile(
                hands=hands_tuple,
                weights=weights_tuple,
                profile=profile_entries,
            )
        )

    return BrownStrategyDump(
        players=(parsed_players[0], parsed_players[1]),
        game_value_p0=game_value_p0,
        game_value_p1=game_value_p1,
        iterations_run=iterations_run,
        exploitability_chips=exploitability_chips,
    )


# ============================================================================
# History canonicalization
# ============================================================================

# Shared state for state-tracked canonicalization. Both canonicalizers walk
# tokens left-to-right, tracking each player's cumulative contribution; the
# starting contributions are spot.pot/2 each, matching Brown's RiverGame
# construction (cpp/src/river_game.cpp:14-15 starts contrib0/contrib1 at 0
# *above* base_pot; we add base_pot/2 to align with our hunl encoding which
# treats initial_contributions as already-paid chips).
#
# Important: in Brown's encoding the state's "contrib" is the EXTRA chips
# above the base pot. In our encoding, the state's "contributions" is the
# TOTAL chips contributed (including the base pot half). Both canonicalizers
# normalize to our shape: amounts in canonical tokens are ALWAYS our
# raise-to-total in our chip accounting (initial_contributions + extra).


@dataclass
class _HistoryState:
    """Mutable accumulator used while walking history tokens."""

    contrib0: int  # P0 total contribution including initial half-pot
    contrib1: int  # P1 total contribution including initial half-pot
    stack: int  # symmetric per-player stack at street start
    raises: int = 0  # number of bets+raises this street
    actor: int = 0  # next player to act (river-open = P1 / OOP = our P1)

    def to_call(self) -> int:
        """Chips ``actor`` owes to match the larger contribution."""
        actor_contrib = self.contrib0 if self.actor == 0 else self.contrib1
        opp_contrib = self.contrib1 if self.actor == 0 else self.contrib0
        return max(0, opp_contrib - actor_contrib)

    def actor_remaining(self) -> int:
        """Chips the current actor has still behind."""
        actor_contrib = self.contrib0 if self.actor == 0 else self.contrib1
        # stack here is the per-player effective stack at street start (i.e.
        # not yet decremented). The remaining behind = stack - actor_contrib.
        return self.stack - actor_contrib


def _state_for_history(spot: RiverSpot) -> _HistoryState:
    """Construct the initial state used while walking a river history.

    Per PR 7 fixtures (river-open subgame), both players have already
    contributed ``spot.pot // 2`` chips and the actor on the river open
    is P1 (OOP — big blind acts first postflop).
    """
    half = spot.pot // 2
    # PR 7 fixtures are symmetric: starting_stack already includes the
    # half-pot contribution conceptually carried into the subgame, so
    # the per-player "stack ceiling" we use for to_call/remaining math
    # is `half + spot.stack` — half-pot already contributed plus stack
    # left behind.
    return _HistoryState(
        contrib0=half,
        contrib1=half,
        stack=half + spot.stack,
        raises=0,
        actor=1,
    )


def _state_for_default_river_pot(
    initial_pot: int, initial_stack: int = 9500
) -> _HistoryState:
    """Construct an initial state for round-trip tests with no spot context.

    Used by ``canonicalize_brown_history`` / ``canonicalize_our_history``
    when called without a fixture, e.g. on hand-built histories in
    Agent C's tests. The starting actor is P1 (river-open) and both
    players start with ``initial_pot // 2`` contributed.

    ``initial_stack`` is the per-player remaining stack (NOT including the
    half-pot already contributed) — same convention as ``RiverSpot.stack``
    and our ``HUNLConfig.starting_stack`` for river subgames. The internal
    ``state.stack`` ceiling becomes ``half + initial_stack`` (the total
    chips each player can have in by the end of the street), matching
    ``_state_for_history`` exactly. The default 9500 matches PR 7 fixtures
    (pot=1000, stack=9500) so the all-in token in hand-built round-trip
    histories maps to the same canonical amount the production diff path
    sees.
    """
    half = initial_pot // 2
    return _HistoryState(
        contrib0=half,
        contrib1=half,
        stack=half + initial_stack,
        raises=0,
        actor=1,
    )


def canonicalize_brown_history(
    token_str: str,
    *,
    spot: RiverSpot | None = None,
    initial_pot: int = 1000,
    initial_stack: int = 9500,
) -> CanonicalHistory:
    """Convert Brown's history string to canonical form.

    Brown's encoding (``cpp/src/main.cpp:176-194``):

      * ``"c"``         → ``("c", 0)`` (covers both check and call)
      * ``"f"``         → ``("f", 0)``
      * ``"b<amount>"`` → ``("b", actor_new_total)`` — Brown's ``amount``
        is chips added by the actor (``cpp/src/main.cpp:185``). The actor
        had ``actor_contrib`` chips in, so ``new_total = actor_contrib + amount``.
      * ``"r<extra>"``  → ``("r", actor_new_total)`` — Brown's
        ``extra`` is the chips beyond the call (``cpp/src/main.cpp:193-194``).
        Walk state: ``new_total = max(c0, c1) + extra``.

    ``"root"`` and the empty string both map to ``()`` (the empty
    history). Tokens are split on ``"/"``.

    If a ``spot`` is supplied, the initial state uses its pot/stack; if
    not, a synthetic state with the supplied ``initial_pot`` and
    ``initial_stack`` is used (intended for round-trip tests on
    hand-built histories). Defaults match the PR 7 fixture convention
    (pot=1000, stack=9500) so the all-in token canonicalizes to the same
    amount the production diff path sees.
    """
    state = (
        _state_for_history(spot)
        if spot is not None
        else _state_for_default_river_pot(initial_pot, initial_stack)
    )
    return _walk_brown_tokens(token_str, state)


def _walk_brown_tokens(token_str: str, state: _HistoryState) -> CanonicalHistory:
    """Tokenize a Brown history string and walk state along it."""
    if not token_str or token_str == "root":
        return ()
    tokens = token_str.split("/")
    out: list[CanonicalToken] = []
    for tok in tokens:
        if tok == "c":
            # Check-or-call: actor calls (if to_call > 0) or checks. Either
            # way it's ("c", 0). State update: contribution increases by
            # to_call for a call; for a check it's a no-op.
            to_call = state.to_call()
            if to_call > 0:
                if state.actor == 0:
                    state.contrib0 += to_call
                else:
                    state.contrib1 += to_call
            out.append(("c", 0))
            state.actor = 1 - state.actor
        elif tok == "f":
            out.append(("f", 0))
            # No further play possible; remain at this state.
            state.actor = -1
        elif tok.startswith("b"):
            try:
                amount = int(tok[1:])
            except ValueError as exc:
                raise ValueError(f"Brown history: malformed bet token {tok!r}") from exc
            actor_contrib = state.contrib0 if state.actor == 0 else state.contrib1
            new_total = actor_contrib + amount
            if state.actor == 0:
                state.contrib0 = new_total
            else:
                state.contrib1 = new_total
            state.raises += 1
            out.append(("b", new_total))
            state.actor = 1 - state.actor
        elif tok.startswith("r"):
            try:
                extra = int(tok[1:])
            except ValueError as exc:
                raise ValueError(
                    f"Brown history: malformed raise token {tok!r}"
                ) from exc
            opponent_total = max(state.contrib0, state.contrib1)
            new_total = opponent_total + extra
            if state.actor == 0:
                state.contrib0 = new_total
            else:
                state.contrib1 = new_total
            state.raises += 1
            out.append(("r", new_total))
            state.actor = 1 - state.actor
        else:
            raise ValueError(f"Brown history: unrecognized token {tok!r}")
    return tuple(out)


def canonicalize_our_history(
    history_str: str,
    *,
    spot: RiverSpot | None = None,
    initial_pot: int = 1000,
    initial_stack: int = 9500,
) -> CanonicalHistory:
    """Convert our hunl.py history substring to canonical form.

    Our encoding (``poker_solver/hunl.py:343-437``):

      * ``"c"``           → ``("c", 0)``
      * ``"x"``           → ``("c", 0)`` (check ≡ call(0); Brown treats both as ``c``)
      * ``"f"``           → ``("f", 0)``
      * ``"b<amount>"``   → ``("b", actor_new_total)`` — our ``amount`` is chips added,
        same as Brown.
      * ``"r<to_total>"`` → ``("r", to_total)`` — our amount is already total-form;
        emit as-is. We still update state from it for downstream tokens.
      * ``"A"``           → ``("b", remaining_total)`` if ``to_call == 0``, else
        ``("r", remaining_total)`` (state-dependent re-emission per PR 7 §5).

    The history substring is the part AFTER the third ``|`` in our
    infoset key. Streets are joined by ``/`` and tokens within a street
    are concatenated without a separator (``hunl.py:344``). PR 7 only
    covers river-only subgames, so a single street's worth of tokens
    appears here, never preceded by an empty-prior-streets segment.

    ``hunl.py`` joins all-street token lists with ``"/"``. In a
    river-start subgame the lists for prior streets are empty, so this
    parser tolerates leading ``/`` separators and treats them as no-ops.

    ``initial_stack`` is propagated to the default-state helper when no
    ``spot`` is supplied (needed for accurate all-in/``A``-token mapping).
    """
    state = (
        _state_for_history(spot)
        if spot is not None
        else _state_for_default_river_pot(initial_pot, initial_stack)
    )
    if not history_str:
        return ()

    return _walk_our_tokens(history_str, state)


# Regex matching one token of our betting history. Captures explicitly so
# we can distinguish ``r1875`` (one token) from ``c x`` (two tokens).
_OUR_TOKEN_RE = re.compile(r"r(\d+)|b(\d+)|A|c|x|f")


def _walk_our_tokens(history_str: str, state: _HistoryState) -> CanonicalHistory:
    """Tokenize our betting history and walk state along it.

    Our concatenated-within-street format means we cannot split on a
    separator alone; we use a left-anchored regex to peel one token at
    a time. ``/`` between streets is consumed as a separator.
    """
    out: list[CanonicalToken] = []
    pos = 0
    n = len(history_str)
    while pos < n:
        if history_str[pos] == "/":
            # Inter-street separator; PR 7 fixtures are river-only so we
            # expect at most leading slashes from empty prior-street segments.
            pos += 1
            continue
        m = _OUR_TOKEN_RE.match(history_str, pos)
        if not m:
            raise ValueError(
                f"Our history: cannot tokenize at offset {pos} in {history_str!r}"
            )
        tok = m.group(0)
        pos = m.end()
        if tok in ("c", "x"):
            to_call = state.to_call()
            if to_call > 0:
                if state.actor == 0:
                    state.contrib0 += to_call
                else:
                    state.contrib1 += to_call
            out.append(("c", 0))
            state.actor = 1 - state.actor
        elif tok == "f":
            out.append(("f", 0))
            state.actor = -1
        elif tok == "A":
            # All-in: depends on to_call at this moment.
            to_call = state.to_call()
            actor_contrib = state.contrib0 if state.actor == 0 else state.contrib1
            new_total = state.stack  # actor pushes all chips, total = stack
            if state.actor == 0:
                state.contrib0 = new_total
            else:
                state.contrib1 = new_total
            state.raises += 1
            if to_call == 0:
                # Opening all-in jam: re-emit as a bet for amount=remaining.
                out.append(("b", new_total))
            else:
                # All-in as raise: re-emit as raise-to-total.
                out.append(("r", new_total))
            state.actor = 1 - state.actor
            _ = actor_contrib  # quiet linter; kept above to document semantics
        elif tok.startswith("b"):
            amount = int(m.group(2))
            actor_contrib = state.contrib0 if state.actor == 0 else state.contrib1
            new_total = actor_contrib + amount
            if state.actor == 0:
                state.contrib0 = new_total
            else:
                state.contrib1 = new_total
            state.raises += 1
            out.append(("b", new_total))
            state.actor = 1 - state.actor
        elif tok.startswith("r"):
            new_total = int(m.group(1))
            if state.actor == 0:
                state.contrib0 = new_total
            else:
                state.contrib1 = new_total
            state.raises += 1
            out.append(("r", new_total))
            state.actor = 1 - state.actor
        else:  # pragma: no cover — regex already enumerates the cases
            raise ValueError(f"Our history: unrecognized token {tok!r}")
    return tuple(out)


# ============================================================================
# Strategy reshaping
# ============================================================================


def our_strategy_to_brown_matrix(
    result: SolveResult,
    hands_p0: tuple[Combo, ...],
    hands_p1: tuple[Combo, ...],
    spot: RiverSpot,
) -> dict[str, dict[int, np.ndarray]]:
    """Flatten our per-infoset strategies into Brown's matrix shape.

    Walks ``result.average_strategy``, parses each infoset key into
    ``(player, hand, canonical_history)``, and groups into a nested
    dict:

    .. code-block:: python

        out[canonical_history_str][player_index] = np.ndarray(num_hands, num_actions)

    where ``canonical_history_str`` is a string representation of the
    canonical (action_kind, amount) tuple — currently a ``/``-joined
    Brown-style key with raises re-encoded as ``r<to_total>`` (matching
    the canonical form, NOT Brown's wire format). Agent B's diff harness
    builds the corresponding key for Brown's profile by canonicalizing
    each Brown history with ``canonicalize_brown_history`` and rendering
    it with the same renderer (``_render_canonical_history``) so both
    sides agree on the keying scheme.

    Hand orderings follow ``hands_p0`` / ``hands_p1`` (caller passes the
    same lists used to build ``spot.ranges``); hands not appearing in
    our strategy keys for a given infoset get a zero row.

    Returns:
        A nested dict keyed by canonical_history_str → player int (0 or 1)
        → ``np.ndarray`` of shape (num_hands, num_actions). The
        action-count is determined per-infoset from the first hand row we
        see; if our infosets span different action sets within the same
        history (shouldn't happen in well-formed river subgames), the
        function raises ``ValueError`` to surface the inconsistency.
    """
    # Build (player, canonical_history) → {hand_index → list[probs]}
    by_infoset: dict[tuple[int, CanonicalHistory], dict[int, list[float]]] = {}
    hand_index_p0 = _build_combo_index(hands_p0)
    hand_index_p1 = _build_combo_index(hands_p1)

    # Our infoset_key format:
    #   "{player_hole}|{board}|{street_token}|{history}"
    # where player_hole is the sorted card-string of the player's hole.
    # We need to figure out which player owns a key — but the key itself
    # only contains the hole. We rely on which range the hole belongs to.
    for key, probs in result.average_strategy.items():
        parts = key.split("|")
        if len(parts) != 4:
            # Not an infoset we recognize; skip (e.g. bucketed-path keys
            # in a different shape, not used in PR 7 river fixtures).
            continue
        player_hole_str, _board_str, _street, history_substr = parts
        # Identify which player by hole-card membership.
        hand = _parse_sorted_hole_str(player_hole_str)
        if hand is None:
            continue
        if hand in hand_index_p0:
            player = 0
            hand_index = hand_index_p0[hand]
        elif hand in hand_index_p1:
            player = 1
            hand_index = hand_index_p1[hand]
        else:
            # Hole not in either range; PR 7 ranges are explicit so this
            # shouldn't happen in well-formed fixtures, but we silently
            # drop rather than crashing.
            continue
        canonical = canonicalize_our_history(history_substr, spot=spot)
        bucket = by_infoset.setdefault((player, canonical), {})
        if hand_index in bucket:
            # Two strategy entries for the same (player, hand, infoset) —
            # this can happen if our infoset_key collides across paths
            # (shouldn't for river subgames). Take the last one.
            pass
        bucket[hand_index] = list(probs)

    # Materialize ndarrays keyed by canonical_history_str.
    out: dict[str, dict[int, np.ndarray]] = {}
    for (player, canonical), hand_to_probs in by_infoset.items():
        key_str = _render_canonical_history(canonical)
        # Determine num_actions from the first hand row.
        first_probs = next(iter(hand_to_probs.values()))
        num_actions = len(first_probs)
        for probs in hand_to_probs.values():
            if len(probs) != num_actions:
                raise ValueError(
                    f"Inconsistent action count at infoset {key_str!r} player {player}: "
                    f"{len(probs)} vs {num_actions}"
                )
        num_hands = len(hands_p0) if player == 0 else len(hands_p1)
        matrix = np.zeros((num_hands, num_actions), dtype=np.float64)
        for hand_idx, probs in hand_to_probs.items():
            matrix[hand_idx, :] = probs
        out.setdefault(key_str, {})[player] = matrix
    return out


def _build_combo_index(hands: tuple[Combo, ...]) -> dict[tuple[Card, Card], int]:
    """Map sorted-combo tuples to their position in the caller's hand list.

    Our infoset key uses ``_sorted_card_string`` (``hunl.py:207-209``),
    which sorts by ``(rank, suit)`` ascending. We replicate that sort
    here so we can look up holes parsed from infoset keys.
    """
    index: dict[tuple[Card, Card], int] = {}
    for i, (c1, c2) in enumerate(hands):
        sorted_pair = (c1, c2) if (c1.rank, c1.suit) <= (c2.rank, c2.suit) else (c2, c1)
        index[sorted_pair] = i
    return index


def _parse_sorted_hole_str(s: str) -> tuple[Card, Card] | None:
    """Parse our infoset key's hole-card substring into a sorted (Card, Card).

    Returns ``None`` for empty strings (chance-node infosets); raises for
    malformed strings.
    """
    if not s:
        return None
    if len(s) != 4:
        raise ValueError(f"hole-card substring must be 4 chars, got {s!r}")
    c1 = parse_card(s[0:2])
    c2 = parse_card(s[2:4])
    pair = (c1, c2) if (c1.rank, c1.suit) <= (c2.rank, c2.suit) else (c2, c1)
    return pair


def _render_canonical_history(history: CanonicalHistory) -> str:
    """Render a canonical history as a stable ``/``-joined key string.

    Brown-style separator, but with raise amounts in to-total form (the
    canonical shape) — this is *not* Brown's wire format, it's the
    common cross-engine key both sides of the diff agree on.
    """
    if not history:
        return "root"
    parts: list[str] = []
    for kind, amt in history:
        if kind in ("f", "c"):
            parts.append(kind)
        else:
            parts.append(f"{kind}{amt}")
    return "/".join(parts)


# Export the canonical-history renderer alongside the canonicalizers so
# Agent B can produce matching keys for Brown's side. We also expose the
# state helper for advanced callers (e.g. tests that need to seed state).
__all__ = [
    "BrownInfosetEntry",
    "BrownPlayerProfile",
    "BrownStrategyDump",
    "CanonicalHistory",
    "CanonicalToken",
    "Combo",
    "RiverSpot",
    "canonicalize_brown_history",
    "canonicalize_our_history",
    "find_brown_binary",
    "load_spots",
    "our_strategy_to_brown_matrix",
    "run_brown_solver",
    "write_brown_config",
]
