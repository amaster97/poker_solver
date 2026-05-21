"""Bucket lookup, serialization, and `AbstractionRef` plumbing (PR 4 Stage 4 + 5).

Stages 4 (build-time packing) and 5 (on-disk persistence) of the card-abstraction
pipeline live here. The runtime hot path is `lookup_bucket(tables, board, hand,
street)` — O(1) after canonicalization via Agent A's `canonicalize_for_suit_iso`.

Storage layout (per street):
  - `*_assignments`: flat `uint8` array of bucket ids (one per (canonical_board,
    canonical_hand) pair).
  - `*_board_index`: dict mapping `canonical_board_key (str) -> start offset`
    (int) into `*_assignments`. The start offset is where this board's slice
    begins in the flat array.
  - `*_hand_index`: dict mapping `canonical_board_key -> dict[canonical_hand_key
    -> within-board offset]`. The bucket id for (board, hand) is then
    `*_assignments[board_index[board_key] + hand_index[board_key][hand_key]]`.

`.npz` serialization: per-street arrays + JSON-encoded dicts (sorted-keys for
byte-determinism) + a single `metadata` JSON blob. `source_path` is NOT written
to disk (per PR 6 forward-compat) — it's populated by `load_abstraction(path)`.

Pattern inspired (architecturally) by slumbot2019's bucket-write pipeline (MIT).
Reference: references/code/slumbot2019/src/build_kmeans_buckets.cpp
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from poker_solver.card import Card
from poker_solver.hunl import Street

SCHEMA_VERSION: int = 1
"""On-disk schema version. Bump on incompatible layout changes."""

_STREET_NAMES: dict[Street, str] = {
    Street.FLOP: "flop",
    Street.TURN: "turn",
    Street.RIVER: "river",
}

_REQUIRED_BOARD_LEN: dict[Street, int] = {
    Street.FLOP: 3,
    Street.TURN: 4,
    Street.RIVER: 5,
}


@dataclass(frozen=True)
class AbstractionTables:
    """In-memory representation of a bucket lookup table for postflop streets.

    Indices are keyed by suit-iso-canonicalized board / hand strings produced
    by Agent A's `canonicalize_for_suit_iso(board, hand) -> (board_key, suit_perm)`.
    Preflop is NOT stored; preflop infosets always use the lossless form.

    `source_path` is populated by `load_abstraction(path)` and is consumed by
    PR 6's PyO3 boundary (Rust loader re-reads the .npz from the path). It is
    NOT persisted to disk.
    """

    flop_assignments: np.ndarray  # uint8, K_flop <= 256 fits in u8
    turn_assignments: np.ndarray  # uint8
    river_assignments: np.ndarray  # uint8

    flop_board_index: dict[str, int]
    turn_board_index: dict[str, int]
    river_board_index: dict[str, int]

    flop_hand_index: dict[str, dict[str, int]]
    turn_hand_index: dict[str, dict[str, int]]
    river_hand_index: dict[str, dict[str, int]]

    metadata: dict[str, object]

    source_path: Path | None = field(default=None)


@dataclass(frozen=True)
class AbstractionRef:
    """Lightweight pointer to an on-disk abstraction artifact.

    Carried on `HUNLConfig.abstraction` (per consistency review v2 NEW-1) so
    PR 6's PyO3 boundary can ship only the path string across, not the full
    in-memory table. The runtime resolves a ref to an `AbstractionTables` via
    `resolve_abstraction_ref(ref)` (LRU-cached).
    """

    source_path: str
    version: str


@lru_cache(maxsize=4)
def _cached_load(source_path: str, version: str) -> AbstractionTables:
    """Internal cached loader keyed by (source_path, version).

    Cache is keyed on both so an A/B test with two abstractions of the same
    version-string-but-different-path stays cached separately.
    """
    path = Path(source_path)
    tables = load_abstraction(path)
    file_version = str(tables.metadata.get("version", ""))
    if file_version != version:
        raise ValueError(
            f"AbstractionRef version mismatch: ref.version={version!r} but "
            f"on-disk metadata['version']={file_version!r} at {source_path!r}"
        )
    return tables


def resolve_abstraction_ref(ref: AbstractionRef) -> AbstractionTables:
    """Resolve an `AbstractionRef` to a loaded `AbstractionTables` (LRU-cached).

    Raises:
        ValueError: if the on-disk metadata['version'] does not match
            `ref.version` (refuses to silently use a stale artifact).
        FileNotFoundError: if `ref.source_path` does not exist.
    """
    return _cached_load(ref.source_path, ref.version)


def _validate_board_and_hand(
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
) -> None:
    required = _REQUIRED_BOARD_LEN.get(street)
    if required is None:
        return
    if len(board) != required:
        raise ValueError(
            f"board has {len(board)} cards but street {street.name} requires "
            f"{required}"
        )
    board_set = set(board)
    if len(board_set) != len(board):
        raise ValueError("board has duplicate cards")
    if hole_cards[0] == hole_cards[1]:
        raise ValueError("hole cards are duplicates")
    if hole_cards[0] in board_set or hole_cards[1] in board_set:
        raise ValueError(
            "hole_cards conflict with board (a hole card appears on the board)"
        )


def _canonicalize(
    board: Sequence[Card], hole_cards: tuple[Card, Card]
) -> tuple[str, str]:
    """Canonicalize (board, hand) via Agent A's `canonicalize_for_suit_iso`.

    Returns `(canonical_board_key, canonical_hand_key)`. The canonical hand
    key is derived by applying the suit permutation chosen for the board to
    the hole cards, then formatting as a sorted-by-(rank,suit) string —
    exactly matching the build-time indexing protocol.

    Build time uses the same canonicalization, so lookup keys round-trip.
    """
    from poker_solver.abstraction.equity_features import canonicalize_for_suit_iso

    board_key, perm_index = canonicalize_for_suit_iso(tuple(board), hole_cards)
    hand_key = _apply_suit_perm_to_hand(hole_cards, perm_index)
    return board_key, hand_key


def _apply_suit_perm_to_hand(hole_cards: tuple[Card, Card], perm_index: int) -> str:
    """Apply Agent A's suit permutation (by index) to a hand and return its key.

    Agent A's `canonicalize_for_suit_iso(...)` returns `(board_key,
    permutation_index)` where `permutation_index` is the index (0..23) into
    `_SUIT_PERMUTATIONS = list(itertools.permutations((0, 1, 2, 3)))`. We
    look that up and apply it to each hole card.

    The result is the sort-by-(rank, suit) joined string of the permuted
    cards — same shape the build pipeline writes into `*_hand_index`.
    """
    from poker_solver.abstraction.equity_features import _SUIT_PERMUTATIONS

    perm = _SUIT_PERMUTATIONS[perm_index]
    permuted = [Card(c.rank, perm[c.suit]) for c in hole_cards]
    permuted.sort(key=lambda c: (c.rank, c.suit))
    return "".join(str(c) for c in permuted)


def lookup_bucket(
    tables: AbstractionTables,
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
) -> int:
    """Return the bucket id for (board, hole_cards) on the given street.

    - PREFLOP: returns `-1` (caller falls back to lossless preflop infoset).
    - FLOP/TURN/RIVER: canonicalizes via `canonicalize_for_suit_iso(...)`,
      then per-street `board_index` + `hand_index` to locate the bucket id
      in the flat `*_assignments` array.

    Raises:
        ValueError: if board has wrong card count for the street, board+hand
            conflict, or the canonical (board, hand) is not in the table
            (signals a build-side coverage bug, NOT a runtime path — the
            table must cover all reachable boards).
    """
    if street == Street.PREFLOP:
        return -1
    if street == Street.SHOWDOWN:
        raise ValueError("lookup_bucket called on SHOWDOWN street")

    _validate_board_and_hand(board, hole_cards, street)
    board_key, hand_key = _canonicalize(board, hole_cards)

    if street == Street.FLOP:
        assignments = tables.flop_assignments
        board_index = tables.flop_board_index
        hand_index = tables.flop_hand_index
    elif street == Street.TURN:
        assignments = tables.turn_assignments
        board_index = tables.turn_board_index
        hand_index = tables.turn_hand_index
    elif street == Street.RIVER:
        assignments = tables.river_assignments
        board_index = tables.river_board_index
        hand_index = tables.river_hand_index
    else:
        raise ValueError(f"unsupported street: {street!r}")

    if board_key not in board_index:
        raise ValueError(
            f"canonical board key {board_key!r} not in {street.name} table "
            f"(build-side coverage bug)"
        )
    if board_key not in hand_index:
        raise ValueError(
            f"canonical board key {board_key!r} missing from {street.name} "
            f"hand_index (build-side coverage bug)"
        )
    per_board = hand_index[board_key]
    if hand_key not in per_board:
        raise ValueError(
            f"canonical hand key {hand_key!r} not in {street.name} "
            f"hand_index for board {board_key!r} (build-side coverage bug)"
        )
    offset = board_index[board_key] + per_board[hand_key]
    return int(assignments[offset])


def _stable_sort_dict(d: dict[str, int]) -> dict[str, int]:
    """Return a new dict with keys sorted lexicographically (byte-determinism)."""
    return dict(sorted(d.items()))


def _stable_sort_nested(
    d: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    return {k: _stable_sort_dict(v) for k, v in sorted(d.items())}


def save_abstraction(tables: AbstractionTables, path: Path) -> None:
    """Serialize `AbstractionTables` to a single `.npz` via `np.savez_compressed`.

    Encoding:
      - `*_assignments`: numpy uint8 arrays as-is.
      - `*_board_index`: stable-sorted dict serialized as JSON bytes inside a
        one-element uint8 array (per spec consistency review B1 — single
        JSON blob keeps the writer simple; PR 6's Rust loader un-nests).
      - `*_hand_index`: same encoding.
      - `metadata`: stable-sorted dict, JSON-encoded with `sort_keys=True`.
      - `source_path` is NOT written (per PR 6 forward-compat decision).

    Byte-deterministic given identical inputs:
      - dict iteration is sorted before JSON encode.
      - JSON uses `sort_keys=True` and `separators=(',', ':')`.
      - numpy arrays use fixed dtypes (uint8).
      - `np.savez_compressed` is called with explicit keyword args in a fixed
        order so the resulting zip stream is deterministic.

    Raises:
        OSError: write failure.
    """

    def _enc(obj: object) -> np.ndarray:
        text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
        return np.frombuffer(text.encode("utf-8"), dtype=np.uint8)

    flop_assign = np.asarray(tables.flop_assignments, dtype=np.uint8)
    turn_assign = np.asarray(tables.turn_assignments, dtype=np.uint8)
    river_assign = np.asarray(tables.river_assignments, dtype=np.uint8)

    flop_bi = _enc(_stable_sort_dict(tables.flop_board_index))
    turn_bi = _enc(_stable_sort_dict(tables.turn_board_index))
    river_bi = _enc(_stable_sort_dict(tables.river_board_index))

    flop_hi = _enc(_stable_sort_nested(tables.flop_hand_index))
    turn_hi = _enc(_stable_sort_nested(tables.turn_hand_index))
    river_hi = _enc(_stable_sort_nested(tables.river_hand_index))

    metadata_blob = _enc(tables.metadata)

    np.savez_compressed(
        path,
        flop_assignments=flop_assign,
        turn_assignments=turn_assign,
        river_assignments=river_assign,
        flop_board_index=flop_bi,
        turn_board_index=turn_bi,
        river_board_index=river_bi,
        flop_hand_index=flop_hi,
        turn_hand_index=turn_hi,
        river_hand_index=river_hi,
        metadata=metadata_blob,
    )


def _dec(arr: np.ndarray) -> object:
    return json.loads(bytes(arr.tobytes()).decode("utf-8"))


def load_abstraction(path: Path) -> AbstractionTables:
    """Read a `.npz` file and reconstruct `AbstractionTables`.

    - Verifies `metadata['schema_version'] == SCHEMA_VERSION`; raises
      `ValueError` on mismatch with a clear message.
    - Populates `source_path = path` (for PR 6's Rust loader boundary).

    Raises:
        FileNotFoundError: if `path` does not exist.
        ValueError: on schema mismatch or malformed file.
    """
    if not path.exists():
        raise FileNotFoundError(f"abstraction artifact not found: {path}")
    with np.load(path, allow_pickle=False) as data:
        try:
            flop_assign = np.asarray(data["flop_assignments"], dtype=np.uint8)
            turn_assign = np.asarray(data["turn_assignments"], dtype=np.uint8)
            river_assign = np.asarray(data["river_assignments"], dtype=np.uint8)
            flop_bi = _dec(data["flop_board_index"])
            turn_bi = _dec(data["turn_board_index"])
            river_bi = _dec(data["river_board_index"])
            flop_hi = _dec(data["flop_hand_index"])
            turn_hi = _dec(data["turn_hand_index"])
            river_hi = _dec(data["river_hand_index"])
            metadata = _dec(data["metadata"])
        except KeyError as e:
            raise ValueError(
                f"malformed abstraction file {path}: missing array {e}"
            ) from e

    if not isinstance(metadata, dict):
        raise ValueError(f"malformed abstraction file {path}: metadata is not a dict")
    schema = metadata.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"artifact schema v{schema}; loader expects schema v{SCHEMA_VERSION}; "
            f"rebuild or upgrade ({path})"
        )

    def _as_str_int(d: object) -> dict[str, int]:
        if not isinstance(d, dict):
            raise ValueError(f"malformed board_index in {path}: not a dict")
        return {str(k): int(v) for k, v in d.items()}

    def _as_nested(d: object) -> dict[str, dict[str, int]]:
        if not isinstance(d, dict):
            raise ValueError(f"malformed hand_index in {path}: not a dict")
        out: dict[str, dict[str, int]] = {}
        for k, v in d.items():
            if not isinstance(v, dict):
                raise ValueError(f"malformed hand_index in {path}: inner is not a dict")
            out[str(k)] = {str(ik): int(iv) for ik, iv in v.items()}
        return out

    return AbstractionTables(
        flop_assignments=flop_assign,
        turn_assignments=turn_assign,
        river_assignments=river_assign,
        flop_board_index=_as_str_int(flop_bi),
        turn_board_index=_as_str_int(turn_bi),
        river_board_index=_as_str_int(river_bi),
        flop_hand_index=_as_nested(flop_hi),
        turn_hand_index=_as_nested(turn_hi),
        river_hand_index=_as_nested(river_hi),
        metadata=metadata,
        source_path=path,
    )


__all__ = [
    "AbstractionRef",
    "AbstractionTables",
    "SCHEMA_VERSION",
    "load_abstraction",
    "lookup_bucket",
    "resolve_abstraction_ref",
    "save_abstraction",
]
