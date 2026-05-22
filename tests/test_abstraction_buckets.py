"""Tests for canonicalization, bucket lookup, and serialization round-trip.

Covers the public surface from PR 4 spec §8 Agent B deliverables for
``poker_solver.abstraction.buckets`` and ``poker_solver.abstraction.precompute``:
``AbstractionTables``, ``lookup_bucket``, ``save_abstraction``,
``load_abstraction``, ``build_abstraction``, plus suit-isomorphism
canonicalization via ``canonicalize_for_suit_iso``.

Per spec §3.5 + autonomous-log D1: suit-iso IS included in PR 4. Per spec
§4 Stage 5 + consistency-review B1: ``metadata`` is a single nested dict
serialized as a JSON ``bytes_`` array inside the ``.npz``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

from poker_solver import (
    AbstractionTables,
    Card,
    Street,
    build_abstraction,
    canonicalize_for_suit_iso,
    load_abstraction,
    lookup_bucket,
)

# -- Helpers ---------------------------------------------------------------


def _card(s: str) -> Card:
    return Card.from_str(s)


def _flop(s: str) -> tuple[Card, Card, Card]:
    parts = s.split()
    if len(parts) != 3:
        raise ValueError(f"expected 3 flop cards, got {len(parts)}: {s!r}")
    return tuple(_card(p) for p in parts)  # type: ignore[return-value]


def _parse_canonical_key(key: str) -> list[Card]:
    """Inverse of ``canonicalize_for_suit_iso``'s board-key format: split a
    canonical key like ``"r2s0_r7s1_r14s2"`` into the corresponding Cards.

    Lives in the test module so the test doesn't reach into private
    abstraction internals. Matches the documented format from
    ``equity_features.canonicalize_for_suit_iso``'s docstring.
    """
    out: list[Card] = []
    for token in key.split("_"):
        # Token is "r{rank}s{suit}"; split on the 's' boundary.
        if not token.startswith("r") or "s" not in token[1:]:
            raise ValueError(f"unexpected canonical token: {token!r}")
        rank_s, suit_s = token[1:].split("s", 1)
        out.append(Card(int(rank_s), int(suit_s)))
    return out


def _pick_covered_board_and_hand(tables, street: Street):
    """Return a (board, hand) pair guaranteed to be in ``tables`` for the
    given street. Picks the lexicographically-smallest stored canonical
    board, then the first canonical hand offset under it.

    Robust to ``build_abstraction``'s autosize truncation: the chosen
    (board, hand) is always present in the table.
    """
    if street == Street.FLOP:
        board_index = tables.flop_board_index
        hand_index = tables.flop_hand_index
    elif street == Street.TURN:
        board_index = tables.turn_board_index
        hand_index = tables.turn_hand_index
    elif street == Street.RIVER:
        board_index = tables.river_board_index
        hand_index = tables.river_hand_index
    else:
        raise ValueError(f"unsupported street: {street!r}")

    board_key = sorted(board_index.keys())[0]
    board_cards = _parse_canonical_key(board_key)

    # Find a hand on this board: pick any hand_key under it; we need to
    # produce a Card-tuple that, when canonicalized against this board,
    # yields that hand_key. The hand_key stored is the result of applying
    # the board's suit-perm to the original hand cards, formatted as a
    # sorted string. Working backwards is messy, so instead enumerate the
    # off-board cards and find the first (Card, Card) pair whose
    # canonicalize-against-this-board hand_key is in hand_index[board_key].
    from poker_solver.abstraction.buckets import _apply_suit_perm_to_hand
    from poker_solver.abstraction.equity_features import canonicalize_for_suit_iso

    board_set = set(board_cards)
    all_cards = [Card(r, s) for r in range(2, 15) for s in range(4)]
    off_board = [c for c in all_cards if c not in board_set]
    candidate_hand_keys = hand_index[board_key]
    for i in range(len(off_board)):
        for j in range(i + 1, len(off_board)):
            hand = (off_board[i], off_board[j])
            _bk, perm_idx = canonicalize_for_suit_iso(tuple(board_cards), hand)
            hk = _apply_suit_perm_to_hand(hand, perm_idx)
            if hk in candidate_hand_keys:
                return tuple(board_cards), hand
    raise AssertionError(
        f"no covered hand found for board_key={board_key!r} on {street.name} "
        f"(test fixture/abstraction-build mismatch)"
    )


# -- Suit-isomorphism canonicalization (D1) -------------------------------


def test_canonical_board_id_suit_iso_collapses_isomorphic_boards():
    """Two suit-isomorphic boards must produce the same canonical board key.

    Per D1 (locked in autonomous_log.md), PR 4 INCLUDES suit-isomorphism at
    the abstraction layer. Boards that differ only by a global suit
    permutation (and have matching hole-card suit permutations) collapse
    to the same canonical id.
    """
    board1 = (_card("As"), _card("7c"), _card("2d"))
    hand1 = (_card("Kh"), _card("Qh"))
    key1, _ = canonicalize_for_suit_iso(board1, hand1)

    # Apply suit permutation s↔h, c↔d, d↔s, h↔c (an arbitrary global
    # permutation that maps suits in board+hand consistently).
    board2 = (_card("Ah"), _card("7d"), _card("2s"))
    hand2 = (_card("Kc"), _card("Qc"))
    key2, _ = canonicalize_for_suit_iso(board2, hand2)

    assert key1 == key2


def test_canonical_hand_key_sorts_input_within_board():
    """Within the same canonical board, (Ah, Kh) and (Kh, Ah) collapse."""
    board = (_card("As"), _card("7c"), _card("2d"))
    key_a, idx_a = canonicalize_for_suit_iso(board, (_card("Ah"), _card("Kh")))
    key_b, idx_b = canonicalize_for_suit_iso(board, (_card("Kh"), _card("Ah")))
    assert key_a == key_b
    assert idx_a == idx_b


# -- Synthetic AbstractionTables construction ------------------------------
#
# Building real tables via ``build_abstraction`` is slow even at small
# configs; some tests use a tiny end-to-end build, others construct a
# synthetic AbstractionTables fixture via ``build_abstraction`` once and
# reuse it for cheap lookups.


@pytest.fixture(scope="module")
def tiny_tables(tmp_path_factory):
    """Tiny river-only abstraction; shared across cheap tests."""
    out = tmp_path_factory.mktemp("abs") / "tiny.npz"
    tables = build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    return tables, out


# -- Lookup semantics ------------------------------------------------------


def test_lookup_bucket_returns_minus_one_for_preflop(tiny_tables):
    tables, _ = tiny_tables
    board: tuple[Card, ...] = ()
    hand = (_card("As"), _card("Kh"))
    assert lookup_bucket(tables, board, hand, Street.PREFLOP) == -1


@pytest.mark.timeout(180)
def test_lookup_bucket_returns_in_range_for_postflop(tmp_path):
    """Build a tiny artifact covering all three streets and check ranges.

    Pin the boards to specific canonical-set members (rank-2/3/4 suits 0/1/2)
    that are guaranteed to land inside ``build_abstraction``'s autosize
    smoke-test board cap (default 8 canonical boards / 16 hands per board
    when ``mc_iterations < 5_000``). Using rank-14 (Ace) boards drops the
    test into the "not enumerated" branch of ``lookup_bucket`` because the
    autosize cap stops at the lowest-rank canonical boards in iteration
    order.
    """
    out = tmp_path / "all.npz"
    tables = build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.FLOP, Street.TURN, Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    # Pull a covered (board, hand) from each street's index so the test is
    # robust to autosize truncation. The board_index keys are canonical
    # strings; pair each with the representative hand for that board (the
    # first key in the per-board hand_index) and reconstruct the Card tuple
    # by walking the table's stored representative — derived via a
    # round-trip enumeration of the truncated canonical set.
    flop_board, flop_hand = _pick_covered_board_and_hand(tables, Street.FLOP)
    turn_board, turn_hand = _pick_covered_board_and_hand(tables, Street.TURN)
    river_board, river_hand = _pick_covered_board_and_hand(tables, Street.RIVER)

    bf = lookup_bucket(tables, flop_board, flop_hand, Street.FLOP)
    bt = lookup_bucket(tables, turn_board, turn_hand, Street.TURN)
    br = lookup_bucket(tables, river_board, river_hand, Street.RIVER)

    assert 0 <= bf < 4
    assert 0 <= bt < 2
    assert 0 <= br < 2


def test_lookup_bucket_deterministic(tiny_tables):
    tables, _ = tiny_tables
    # Pick a covered (board, hand) from the truncated abstraction so the
    # test is robust to autosize board/hand caps.
    board, hand = _pick_covered_board_and_hand(tables, Street.RIVER)
    first = lookup_bucket(tables, board, hand, Street.RIVER)
    for _ in range(100):
        assert lookup_bucket(tables, board, hand, Street.RIVER) == first


# -- Save / load round trip + schema -------------------------------------


@pytest.mark.timeout(180)
def test_save_load_round_trip(tmp_path):
    out = tmp_path / "round.npz"
    built = build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )

    loaded = load_abstraction(out)

    # Per-array equality on the river assignments.
    assert np.array_equal(
        np.asarray(loaded.river_assignments),
        np.asarray(built.river_assignments),
    )
    # Metadata deep-equal (excluding build_timestamp/build_duration_sec
    # which are wall-clock dependent — they appear in both copies but we
    # ignore those volatile fields and compare the rest).
    for k, v in built.metadata.items():
        if k in ("build_timestamp", "build_duration_sec"):
            continue
        assert loaded.metadata[k] == v


@pytest.mark.timeout(180)
def test_save_load_schema_version_check(tmp_path):
    """Corrupt schema_version on disk; loader must raise ValueError.

    Per spec §4 Stage 5: metadata is a single JSON-encoded nested dict
    inside the .npz. Loader checks schema_version == 1; mismatch raises
    a ValueError mentioning 'schema'.
    """
    out = tmp_path / "bad.npz"
    build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )

    # Rewrite the npz with corrupted schema_version in the metadata JSON.
    with np.load(out, allow_pickle=False) as npz:
        arrays = {name: np.array(npz[name]) for name in npz.files}
    meta_key = next(k for k in arrays if "metadata" in k.lower())
    meta_bytes = arrays[meta_key].tobytes()
    meta_dict = json.loads(meta_bytes.decode("utf-8"))
    meta_dict["schema_version"] = 999
    new_bytes = json.dumps(meta_dict).encode("utf-8")
    arrays[meta_key] = np.frombuffer(new_bytes, dtype=np.uint8)

    buf = io.BytesIO()
    np.savez_compressed(buf, **arrays)
    out.write_bytes(buf.getvalue())

    with pytest.raises(ValueError, match=r"(?i)schema"):
        load_abstraction(out)


@pytest.mark.timeout(180)
def test_save_load_source_path_populated_on_load(tmp_path):
    """B2 amendment: load_abstraction sets source_path; build leaves it None."""
    out = tmp_path / "src.npz"
    built = build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    loaded = load_abstraction(out)

    assert loaded.source_path == Path(out)
    # Interpretation note: spec amendment says build_abstraction leaves
    # source_path unset (None); save_abstraction writes file but does not
    # stamp the source_path back onto the in-memory copy.
    assert built.source_path is None


@pytest.mark.timeout(180)
def test_save_load_size_under_guard_rail(tmp_path):
    out = tmp_path / "small.npz"
    build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    size = out.stat().st_size
    assert size < 100_000  # < 100 KB for tiny config


# -- Error handling --------------------------------------------------------


def test_lookup_bucket_raises_on_blocker(tiny_tables):
    """Board includes one of hero's hole cards → ValueError, not silent."""
    tables, _ = tiny_tables
    board = (
        _card("As"),
        _card("7c"),
        _card("2d"),
        _card("Kh"),
        _card("5s"),
    )
    # Hand reuses As from the board.
    hand = (_card("As"), _card("Kc"))
    with pytest.raises(ValueError, match=r"(?i)(blocker|conflict|duplicate)"):
        lookup_bucket(tables, board, hand, Street.RIVER)


def test_lookup_bucket_raises_on_wrong_board_size(tiny_tables):
    """Caller passes a turn-shaped board (4 cards) but claims Street.FLOP."""
    tables, _ = tiny_tables
    board = (_card("As"), _card("7c"), _card("2d"), _card("Kh"))
    hand = (_card("Ah"), _card("Qh"))
    with pytest.raises(ValueError):
        lookup_bucket(tables, board, hand, Street.FLOP)


# -- Metadata + build artifact -------------------------------------------


@pytest.mark.timeout(180)
def test_abstraction_tables_metadata_includes_required_fields(tmp_path):
    out = tmp_path / "meta.npz"
    tables = build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    required = {
        "schema_version",
        "bucket_counts",
        "feature_bins",
        "seed",
        "build_timestamp",
        "build_duration_sec",
        "lossless_streets",
        "flop_mode",
        "mc_iterations",
    }
    missing = required - set(tables.metadata.keys())
    assert not missing, f"metadata missing fields: {missing}"
    assert tables.metadata["schema_version"] == 1
    # lossless_streets per spec §4 Stage 5: empty list when all postflop
    # streets are bucketed (i.e., nothing is lossless in PR 4 v1).
    assert list(tables.metadata["lossless_streets"]) == []


def test_canonical_hand_key_in_range_for_random_inputs():
    """Loose check: canonicalize_for_suit_iso runs over random inputs.

    Tests well-typedness rather than uniqueness: function does not crash
    and returns the documented ``(canonical_board_key, suit_perm_index)``
    tuple over 100 random (flop, hand) inputs.
    """
    rng = np.random.default_rng(0)
    deck = [Card(r, s) for r in range(2, 15) for s in range(4)]
    for _ in range(100):
        idxs = rng.choice(len(deck), size=5, replace=False)
        chosen = [deck[i] for i in idxs]
        board = tuple(chosen[:3])
        hand = (chosen[3], chosen[4])
        key, idx = canonicalize_for_suit_iso(board, hand)
        assert isinstance(key, str)
        assert isinstance(idx, int)
        assert idx >= 0


@pytest.mark.timeout(180)
def test_build_abstraction_writes_file_with_correct_shape(tmp_path):
    out = tmp_path / "shape.npz"
    build_abstraction(
        out_path=out,
        bucket_counts=(4, 2, 2),
        seed=0,
        H=10,
        max_iter=20,
        streets=[Street.RIVER],
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
    )
    assert out.exists()
    loaded = load_abstraction(out)

    assert isinstance(loaded, AbstractionTables)
    river_arr = np.asarray(loaded.river_assignments)
    # Spec §4 Stage 4: bucket ids fit in u8 per street.
    assert river_arr.dtype == np.uint8
    # K_river = 2 (from bucket_counts=(4, 2, 2))
    assert len(np.unique(river_arr)) <= 2
