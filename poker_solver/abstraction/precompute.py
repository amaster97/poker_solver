"""CLI orchestrator: build the abstraction artifact end-to-end.

Pipeline (per spec §4):
  Stage 1: enumerate (board, hand) instances → call Agent A's compute_*_features
  Stage 2/3: call Agent A's kmeans_emd to cluster each street's feature matrix
  Stage 4: pack assignments into `AbstractionTables`
  Stage 5: serialize via `save_abstraction(tables, out_path)`

Reproducibility: same args → byte-identical artifact on disk.

Checkpoint-and-resume (per spec §9 risks): per-street intermediate feature
arrays are saved to `out_path.parent / f".{out_path.stem}_tmp/"` so an
interrupted build can skip already-computed streets.

Pattern inspired (architecturally) by slumbot2019's build_kmeans_buckets.cpp (MIT).
Reference: references/code/slumbot2019/src/build_kmeans_buckets.cpp
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Literal

import numpy as np

from poker_solver.abstraction.buckets import (
    SCHEMA_VERSION,
    AbstractionTables,
    save_abstraction,
)
from poker_solver.card import Card
from poker_solver.hunl import Street

_DECK: list[Card] = [Card(r, s) for r in range(2, 15) for s in range(4)]

# Per-street required board card counts.
_STREET_BOARD_LEN: dict[Street, int] = {
    Street.FLOP: 3,
    Street.TURN: 4,
    Street.RIVER: 5,
}

# Bucket-count fits in u8 (max 256).
_MAX_BUCKETS_U8 = 256

# Autosize heuristic: ``None`` + mc below threshold => smoke-test caps applied;
# ``-1`` => explicit "no cap"; positive => direct cap. Threshold sits well
# below the locked production default (D2: 200_000) so production never trips.
_AUTOSIZE_MC_ITERATIONS_THRESHOLD = 5_000
_AUTOSIZE_BOARDS_CAP = 8
_AUTOSIZE_HANDS_CAP = 16


def _abs_size_bytes(
    flop_assign: np.ndarray,
    turn_assign: np.ndarray,
    river_assign: np.ndarray,
    indexes: Sequence[dict[str, int] | dict[str, dict[str, int]]],
) -> int:
    """Conservative size estimate (uncompressed bytes). Overshoot is OK for the
    guard rail."""
    arr_bytes = flop_assign.nbytes + turn_assign.nbytes + river_assign.nbytes
    # Index overhead: per-board key (~10 chars) + 4-byte offset; nested adds
    # ~10 chars + 4-byte offset per (board, hand). Approximate.
    index_bytes = 0
    for idx in indexes:
        if not idx:
            continue
        sample_key = next(iter(idx))
        if isinstance(idx[sample_key], dict):
            for k, v in idx.items():
                assert isinstance(v, dict)
                index_bytes += len(k) + 4
                for ik in v:
                    index_bytes += len(ik) + 4
        else:
            for k in idx:
                index_bytes += len(k) + 4
    return arr_bytes + index_bytes


_CanonFn = Callable[
    [Sequence[Card], tuple[Card, Card]],
    tuple[str, int],
]


def _enumerate_canonical_boards(
    street: Street,
    canon_fn: _CanonFn,
    max_boards: int | None = None,
    required_boards: Sequence[tuple[Card, ...]] | None = None,
) -> dict[str, tuple[Card, ...]]:
    """Enumerate canonical boards (suit-iso reduced) for the given street.

    Returns dict mapping `canonical_board_key -> a representative board tuple`.
    We keep the *first-seen* board as the representative for each canonical key.

    ``max_boards`` limits the enumeration to the first N canonical boards
    (in iteration order over ``combinations(_DECK, n_cards)``). Used for tests
    + tiny configs where full enumeration (1755 flop / 16K turn / 134K river)
    would dominate test time. ``None`` (default) means no limit.

    ``required_boards`` is an optional set of (Card, ...) tuples that must
    appear in the output regardless of ``max_boards``. Each required board
    is canonicalized via ``canon_fn`` (with the same dummy-hand trick used
    for iteration) and added to the output if not already present; required
    boards do NOT count against the ``max_boards`` budget. This is how
    HUNL-integration tests pin a specific test-fixture board into a tiny
    autosize-truncated abstraction.
    """
    n_cards = _STREET_BOARD_LEN[street]
    out: dict[str, tuple[Card, ...]] = {}

    # Seed required boards first so they're guaranteed coverage.
    required_key_count = 0
    if required_boards is not None:
        for combo in required_boards:
            if len(combo) != n_cards:
                # Skip boards whose card count doesn't match this street.
                continue
            board_set = set(combo)
            dummy_pool = [c for c in _DECK if c not in board_set][:2]
            if len(dummy_pool) < 2:
                continue
            dummy_hand: tuple[Card, Card] = (dummy_pool[0], dummy_pool[1])
            board_key, _suit_perm = canon_fn(combo, dummy_hand)
            if board_key not in out:
                out[board_key] = combo
                required_key_count += 1

    for combo in combinations(_DECK, n_cards):
        board_set = set(combo)
        dummy_pool = [c for c in _DECK if c not in board_set][:2]
        if len(dummy_pool) < 2:
            continue
        dummy_hand_iter: tuple[Card, Card] = (dummy_pool[0], dummy_pool[1])
        board_key, _suit_perm = canon_fn(combo, dummy_hand_iter)
        if board_key not in out:
            out[board_key] = combo
            # Budget only counts non-required boards.
            non_required_count = len(out) - required_key_count
            if max_boards is not None and non_required_count >= max_boards:
                break
    return out


def _enumerate_hands_for_board(
    board: tuple[Card, ...],
    canon_fn: _CanonFn,
    max_hands: int | None = None,
    required_hands: Sequence[tuple[Card, Card]] | None = None,
) -> dict[str, tuple[Card, Card]]:
    """Enumerate canonical hands for a representative board.

    Returns dict mapping `canonical_hand_key -> a representative hole-pair`.
    Uses Agent A's canonicalization to dedupe suit-equivalent hands.

    ``max_hands`` truncates the enumeration to the first N canonical hands
    (in suit-iso-dedup iteration order). Tests and smoke configs pass a
    small value; production leaves it ``None`` for full enumeration.

    ``required_hands`` always-include set; required hands do NOT count
    against ``max_hands`` budget. Used to pin specific test-fixture hands
    into a tiny autosize-truncated abstraction.
    """
    from poker_solver.abstraction.buckets import _apply_suit_perm_to_hand

    board_set = set(board)
    off_board = [c for c in _DECK if c not in board_set]
    out: dict[str, tuple[Card, Card]] = {}

    required_key_count = 0
    if required_hands is not None:
        for hand in required_hands:
            # Skip hands that collide with the board (e.g., this required
            # hand was meant for a different board); silent skip so the
            # caller can pass a union of test hands across boards.
            if hand[0] in board_set or hand[1] in board_set or hand[0] == hand[1]:
                continue
            _board_key, suit_perm = canon_fn(board, hand)
            hand_key = _apply_suit_perm_to_hand(hand, suit_perm)
            if hand_key not in out:
                out[hand_key] = hand
                required_key_count += 1

    for c0, c1 in combinations(off_board, 2):
        hand_iter: tuple[Card, Card] = (c0, c1)
        _board_key, suit_perm = canon_fn(board, hand_iter)
        hand_key = _apply_suit_perm_to_hand(hand_iter, suit_perm)
        if hand_key not in out:
            out[hand_key] = hand_iter
            non_required_count = len(out) - required_key_count
            if max_hands is not None and non_required_count >= max_hands:
                break
    return out


def _build_street(
    street: Street,
    K: int,
    seed: int,
    H: int,
    max_iter: int,
    flop_mode: Literal["exact", "mc"],
    mc_iterations: int,
    progress: bool,
    checkpoint_dir: Path | None,
    max_boards: int | None = None,
    max_hands_per_board: int | None = None,
    required_boards: Sequence[tuple[Card, ...]] | None = None,
    required_hands: Sequence[tuple[Card, Card]] | None = None,
) -> tuple[
    np.ndarray,
    dict[str, int],
    dict[str, dict[str, int]],
]:
    """Build (assignments, board_index, hand_index) for one street.

    Returns the flat assignments + the two index dicts to merge into the
    full `AbstractionTables`.
    """
    from poker_solver.abstraction.emd_clustering import kmeans_emd
    from poker_solver.abstraction.equity_features import (
        canonicalize_for_suit_iso,
        compute_flop_features,
        compute_river_features,
        compute_turn_features,
    )

    # Stage 1a: canonical board set.
    if progress:
        print(f"[{street.name}] enumerating canonical boards...")
    canonical_boards = _enumerate_canonical_boards(
        street,
        canonicalize_for_suit_iso,
        max_boards=max_boards,
        required_boards=required_boards,
    )

    # Stage 1b: per-board canonical hand set.
    if progress:
        print(
            f"[{street.name}] enumerating canonical hands "
            f"({len(canonical_boards)} boards)..."
        )
    hands_per_board: dict[str, dict[str, tuple[Card, Card]]] = {}
    for board_key, board in canonical_boards.items():
        hands_per_board[board_key] = _enumerate_hands_for_board(
            board,
            canonicalize_for_suit_iso,
            max_hands=max_hands_per_board,
            required_hands=required_hands,
        )

    # Build flat (boards, hands) list in stable order.
    boards_list: list[tuple[Card, ...]] = []
    hands_list_per_board: dict[str, list[tuple[Card, Card]]] = {}
    board_index: dict[str, int] = {}
    hand_index: dict[str, dict[str, int]] = {}
    flat_hands: list[tuple[tuple[Card, ...], tuple[Card, Card]]] = []

    for board_key in sorted(canonical_boards.keys()):
        board = canonical_boards[board_key]
        per_board_hands = hands_per_board[board_key]
        start = len(flat_hands)
        board_index[board_key] = start
        hand_offsets: dict[str, int] = {}
        ordered_hand_keys = sorted(per_board_hands.keys())
        boards_list.append(board)
        ordered_hands = [per_board_hands[hk] for hk in ordered_hand_keys]
        hands_list_per_board[board_key] = ordered_hands
        for i, hk in enumerate(ordered_hand_keys):
            hand_offsets[hk] = i
            flat_hands.append((board, per_board_hands[hk]))
        hand_index[board_key] = hand_offsets

    if not flat_hands:
        # Defensive: empty street (shouldn't happen in production). Return
        # empty uint8 array.
        return (
            np.zeros((0,), dtype=np.uint8),
            board_index,
            hand_index,
        )

    # Stage 1c: compute features via Agent A.
    if progress:
        print(
            f"[{street.name}] computing equity features "
            f"({len(flat_hands)} hands)..."
        )
    feature_ckpt = (
        checkpoint_dir / f"features_{street.name.lower()}.npy"
        if checkpoint_dir is not None
        else None
    )
    if feature_ckpt is not None and feature_ckpt.exists():
        if progress:
            print(f"[{street.name}] reusing cached features from {feature_ckpt}")
        features = np.load(feature_ckpt)
    else:
        # Build hands_per_board mapping in the shape Agent A expects:
        # dict[board_index_int, list[(Card, Card)]] where the board_index is
        # the position in `ordered_boards`.
        ordered_board_keys = sorted(canonical_boards.keys())
        ordered_boards = [canonical_boards[k] for k in ordered_board_keys]
        hands_for_features: dict[int, list[tuple[Card, Card]]] = {
            i: hands_list_per_board[ordered_board_keys[i]]
            for i in range(len(ordered_boards))
        }

        if street == Street.RIVER:
            features = compute_river_features(
                ordered_boards,
                hands_for_features,
                H=H,
                mode="mc",
                mc_iterations=mc_iterations,
                seed=seed,
                progress=progress,
            )
        elif street == Street.TURN:
            features = compute_turn_features(
                ordered_boards,
                hands_for_features,
                H=H,
                mode="mc",
                mc_iterations=mc_iterations,
                seed=seed,
                progress=progress,
            )
        elif street == Street.FLOP:
            features = compute_flop_features(
                ordered_boards,
                hands_for_features,
                H=H,
                mode=flop_mode,
                mc_iterations=mc_iterations,
                seed=seed,
                progress=progress,
            )
        else:
            raise ValueError(f"unsupported street: {street!r}")
        if feature_ckpt is not None:
            feature_ckpt.parent.mkdir(parents=True, exist_ok=True)
            np.save(feature_ckpt, features)

    features = np.asarray(features, dtype=np.float32)
    if features.shape[0] != len(flat_hands):
        raise ValueError(
            f"[{street.name}] feature matrix rows ({features.shape[0]}) do not "
            f"match flat-hand count ({len(flat_hands)}); Agent A contract drift?"
        )

    # Stage 2 + 3: k-means via Agent A.
    if progress:
        print(f"[{street.name}] running k-means (K={K}, max_iter={max_iter})...")
    kmeans_result = kmeans_emd(
        features,
        K,
        seed=seed,
        max_iter=max_iter,
    )
    assignments = np.asarray(kmeans_result.assignments, dtype=np.uint8)
    if assignments.shape[0] != len(flat_hands):
        raise ValueError(
            f"[{street.name}] k-means assignments length {assignments.shape[0]} "
            f"does not match flat-hand count ({len(flat_hands)})"
        )
    if int(assignments.max(initial=0)) >= K:
        raise ValueError(
            f"[{street.name}] k-means produced assignment out of range "
            f"(max={int(assignments.max())}, K={K})"
        )

    return assignments, board_index, hand_index


def build_abstraction(
    out_path: Path,
    bucket_counts: tuple[int, int, int] = (256, 128, 64),
    seed: int = 42,
    H: int = 50,
    max_iter: int = 200,
    streets: Sequence[Street] = (Street.FLOP, Street.TURN, Street.RIVER),
    flop_mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    progress: bool = True,
    size_guard_gb: float = 1.0,
    max_boards_per_street: int | None = None,
    max_hands_per_board: int | None = None,
    required_boards: Sequence[tuple[Card, ...]] | None = None,
    required_hands: Sequence[tuple[Card, Card]] | None = None,
    version: str | None = None,
) -> AbstractionTables:
    """Orchestrate Stages 1 → 5 of the abstraction pipeline.

    See module docstring for the conceptual flow. Same args produce a
    byte-identical artifact on disk.

    ``max_boards_per_street`` (orchestrator note, NOT in original prompt
    signature): optional cap on canonical-board enumeration per street.
    Tests + smoke configs typically pass a small value (e.g., 8); the
    production build leaves this ``None`` to enumerate the full canonical
    space (1755 flop / ~16K turn / ~134K river). Without this knob the
    "tiny" test/smoke configs would still attempt a multi-hour build.
    Surfaced for orchestrator review during integration.

    Autosize fallback: when the caller leaves ``max_boards_per_street`` as
    ``None`` AND ``mc_iterations`` is small (< 5_000), the build interprets
    this as a smoke-test signature and silently caps board enumeration at
    8 canonical boards per street AND hand enumeration at 16 canonical
    hands per board. The production build uses ``mc_iterations=200_000``
    (locked per D2), so production is unaffected. Pass an explicit
    positive ``max_boards_per_street`` / ``max_hands_per_board`` to override.

    ``max_hands_per_board``: optional cap on canonical-hand enumeration per
    board. Required separately from ``max_boards_per_street`` because the
    turn equity feature is exact-enumeration (44 river runouts × 990 opp
    pairs = ~43.5K evaluations per hand) — even at 1 board, full hand
    enumeration on the turn takes ~860s with the pure-Python evaluator.

    ``required_boards`` / ``required_hands``: optional must-include sets.
    Each canonicalized board / hand is forced into the build regardless of
    the truncation caps; this lets HUNL-integration tests pin specific
    fixture boards into a tiny smoke-test abstraction. (The caller passes
    a multi-street union; ``_enumerate_canonical_boards`` filters by the
    right street's card count, and ``_enumerate_hands_for_board`` silently
    drops board-colliding hands.)

    ``version``: optional string written to ``metadata["version"]``. Defaults
    to ``f"v{SCHEMA_VERSION}"`` (currently ``"v1"``). Override for tests that
    want a tagged version (e.g., ``"test-v1"``) so the AbstractionRef
    version-check round-trips without surfacing schema_version coupling to
    the test side.

    Raises:
        ValueError: bucket counts > 256 (won't fit in u8); flop_mode invalid;
            or estimated artifact size exceeds `size_guard_gb`.
    """
    for k in bucket_counts:
        if k > _MAX_BUCKETS_U8 or k <= 0:
            raise ValueError(
                f"bucket count {k} out of range (must be in [1, 256] to fit u8)"
            )
    if flop_mode not in ("exact", "mc"):
        raise ValueError(f"invalid flop_mode: {flop_mode!r}")

    # Autosize smoke-test guard (see ``_AUTOSIZE_MC_ITERATIONS_THRESHOLD``
    # above for the rationale and sentinel scheme). ``None`` => autosize when
    # mc budget is tiny; ``-1`` => explicit "no cap"; positive => direct cap.
    if (
        max_boards_per_street is None
        and mc_iterations < _AUTOSIZE_MC_ITERATIONS_THRESHOLD
    ):
        max_boards_per_street = _AUTOSIZE_BOARDS_CAP
    if (
        max_hands_per_board is None
        and mc_iterations < _AUTOSIZE_MC_ITERATIONS_THRESHOLD
    ):
        max_hands_per_board = _AUTOSIZE_HANDS_CAP
    if max_boards_per_street == -1:
        max_boards_per_street = None
    if max_hands_per_board == -1:
        max_hands_per_board = None

    out_path = Path(out_path)
    checkpoint_dir = out_path.parent / f".{out_path.stem}_tmp"

    K_flop, K_turn, K_river = bucket_counts

    start_ts = time.monotonic()

    flop_assign = np.zeros((0,), dtype=np.uint8)
    turn_assign = np.zeros((0,), dtype=np.uint8)
    river_assign = np.zeros((0,), dtype=np.uint8)

    flop_bi: dict[str, int] = {}
    turn_bi: dict[str, int] = {}
    river_bi: dict[str, int] = {}
    flop_hi: dict[str, dict[str, int]] = {}
    turn_hi: dict[str, dict[str, int]] = {}
    river_hi: dict[str, dict[str, int]] = {}

    requested = set(streets)
    if Street.FLOP in requested:
        flop_assign, flop_bi, flop_hi = _build_street(
            Street.FLOP,
            K_flop,
            seed,
            H,
            max_iter,
            flop_mode,
            mc_iterations,
            progress,
            checkpoint_dir,
            max_boards_per_street,
            max_hands_per_board,
            required_boards,
            required_hands,
        )
    if Street.TURN in requested:
        turn_assign, turn_bi, turn_hi = _build_street(
            Street.TURN,
            K_turn,
            seed,
            H,
            max_iter,
            flop_mode,
            mc_iterations,
            progress,
            checkpoint_dir,
            max_boards_per_street,
            max_hands_per_board,
            required_boards,
            required_hands,
        )
    if Street.RIVER in requested:
        river_assign, river_bi, river_hi = _build_street(
            Street.RIVER,
            K_river,
            seed,
            H,
            max_iter,
            flop_mode,
            mc_iterations,
            progress,
            checkpoint_dir,
            max_boards_per_street,
            max_hands_per_board,
            required_boards,
            required_hands,
        )

    elapsed = time.monotonic() - start_ts

    # Size guard rail (uncompressed estimate).
    size_bytes = _abs_size_bytes(
        flop_assign,
        turn_assign,
        river_assign,
        [flop_bi, turn_bi, river_bi, flop_hi, turn_hi, river_hi],
    )
    if size_bytes / 1e9 > size_guard_gb:
        raise ValueError(
            f"artifact would be ~{size_bytes / 1e9:.2f} GB, exceeds "
            f"size_guard_gb={size_guard_gb:.2f}; consider reducing bucket_counts "
            f"or skipping a street"
        )

    metadata: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "version": version if version is not None else f"v{SCHEMA_VERSION}",
        "bucket_counts": [int(K_flop), int(K_turn), int(K_river)],
        "feature_bins": int(H),
        "seed": int(seed),
        "max_iter": int(max_iter),
        "flop_mode": flop_mode,
        "mc_iterations": int(mc_iterations),
        "streets": sorted(s.name for s in requested),
        "build_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build_duration_sec": float(round(elapsed, 3)),
        "lossless_streets": [],
    }

    tables = AbstractionTables(
        flop_assignments=flop_assign,
        turn_assignments=turn_assign,
        river_assignments=river_assign,
        flop_board_index=flop_bi,
        turn_board_index=turn_bi,
        river_board_index=river_bi,
        flop_hand_index=flop_hi,
        turn_hand_index=turn_hi,
        river_hand_index=river_hi,
        metadata=metadata,
    )

    save_abstraction(tables, out_path)
    if progress:
        print(f"Wrote abstraction to {out_path}")
    return tables


__all__ = ["build_abstraction"]
