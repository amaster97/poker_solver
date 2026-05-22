"""Unit tests for ``poker_solver.library`` (PR 11 Agent C).

Per ``docs/pr11_prep/pr11_spec.md`` §9 + ``docs/pr11_prep/agent_c_prompt.md``.

These tests are written strictly from the spec, not from Agent A's
implementation. The dividend of the fan-out pattern: if a test fails
against the impl, it is a real bug OR a real spec ambiguity — the
orchestrator (NOT this file's author) resolves it.

Each test is < 5 s, uses ``tmp_path`` for isolation, builds a tiny
synthetic ``SolveResult`` inline (no real solver invocation). Schema /
WAL / gzip behavior is asserted indirectly through public API contracts
(roundtrip, concurrency, schema-version error).

Spot-ID determinism behaviors (tests 3 + 4) are gated through
``SpotDescription.spot_id()`` rather than the internal helper.

The known spec ambiguity surfaced by test 4d (label-only change): spec
§2.3 lists 7 canonicalization rules and none mention ``label``;
therefore a label-only change should produce the SAME spot_id. If the
impl deviates, the test fails — flag for orchestrator, do NOT silently
adjust.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, Street
from poker_solver.solver import SolveResult

# --------------------------------------------------------------------------- #
# Synthetic fixtures (built inline; no conftest per spec §9 opening).
# --------------------------------------------------------------------------- #


def _make_synthetic_result(**overrides: Any) -> SolveResult:
    """Construct a ``SolveResult`` with sensible defaults; override per test."""
    defaults: dict[str, Any] = dict(
        average_strategy={
            "infoset1": [0.6, 0.4],
            "infoset2": [0.5, 0.5],
        },
        game_value=0.0,
        exploitability_history=[0.5, 0.3, 0.1],
        iterations=10,
        backend="python",
    )
    defaults.update(overrides)
    return SolveResult(**defaults)


def _make_flop_config(
    starting_stack: int = 10_000,
    board: tuple[Card, ...] = (
        Card.from_str("As"),
        Card.from_str("Kc"),
        Card.from_str("7d"),
    ),
    bet_size_fractions: tuple[float, ...] = (0.5, 1.0, 2.0),
) -> HUNLConfig:
    """Construct a minimal flop ``HUNLConfig`` for tests.

    Starts at flop with a 3-card board so the canonicalizer can exercise
    its board-sort path. Pot is split evenly between the two players to
    satisfy ``HUNLConfig.__post_init__`` invariants.
    """
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=50,
        big_blind=100,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
        bet_size_fractions=bet_size_fractions,
    )


def _make_river_config(
    starting_stack: int = 1_000,
    board: tuple[Card, ...] = (
        Card.from_str("As"),
        Card.from_str("Kc"),
        Card.from_str("7d"),
        Card.from_str("Kh"),
        Card.from_str("5s"),
    ),
) -> HUNLConfig:
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=50,
        big_blind=100,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
    )


def _make_turn_config(starting_stack: int = 10_000) -> HUNLConfig:
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=50,
        big_blind=100,
        starting_street=Street.TURN,
        initial_board=(
            Card.from_str("As"),
            Card.from_str("Kc"),
            Card.from_str("7d"),
            Card.from_str("Kh"),
        ),
        initial_pot=200,
        initial_contributions=(100, 100),
    )


def _make_synthetic_spot(
    config: HUNLConfig | None = None,
    label: str = "test_spot",
    initial_ranges: Any = None,
):
    """Construct a ``SpotDescription`` for tests. Imports lazily so the
    rest of the file is collectable before Agent A lands ``library.py``.
    """
    from poker_solver.library import SpotDescription

    return SpotDescription(
        config=config if config is not None else _make_flop_config(),
        initial_ranges=initial_ranges,
        label=label,
    )


# --------------------------------------------------------------------------- #
# Tests 1-15 per spec §9.
# --------------------------------------------------------------------------- #


def test_library_open_creates_schema(tmp_path: Path) -> None:
    """1. Fresh DB has both tables + the five named indexes (spec §2.2)."""
    from poker_solver.library import Library

    db_path = tmp_path / "lib.db"
    lib = Library.open(db_path)
    lib.close()

    # Inspect schema via a parallel read-only connection.
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','index') ORDER BY name"
        )
        names = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    assert "spots" in names, f"missing 'spots' table; got {names}"
    assert "spots_meta" in names, f"missing 'spots_meta' table; got {names}"
    for idx in (
        "idx_spots_board",
        "idx_spots_street",
        "idx_spots_stack",
        "idx_spots_created",
        "idx_spots_solver",
    ):
        assert idx in names, f"missing index {idx!r}; got {names}"


def test_library_put_get_roundtrip(tmp_path: Path) -> None:
    """2. ``put`` then ``get`` returns a SolveResult equal on all key fields."""
    from poker_solver.library import Library

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        original = _make_synthetic_result()
        spot_id = lib.put(spot, original)
        assert isinstance(spot_id, str) and len(spot_id) > 0

        returned = lib.get(spot)
        assert returned is not None, "get(spot) returned None after put"

        assert returned.average_strategy == original.average_strategy
        assert returned.game_value == pytest.approx(original.game_value)
        # Spec §2.2 schema stores only ``exploitability`` (singular = final
        # value), NOT the full history blob. The roundtrip therefore can
        # only restore exploitability_history to length-1 with the final
        # value preserved. Documented as a known limitation; widen the
        # roundtrip if a future schema migration adds the history column.
        assert (
            len(returned.exploitability_history) >= 1
        ), "exploitability_history must have at least the final value"
        assert returned.exploitability_history[-1] == pytest.approx(
            original.exploitability_history[-1]
        )
        assert returned.iterations == original.iterations
    finally:
        lib.close()


def test_library_spot_id_deterministic(tmp_path: Path) -> None:
    """3. Canonicalization: reordering board cards + bet menu yields the same ID.

    Per spec §2.3 rules 1 + 3: board sorted ascending, bet fractions
    sorted ascending. Two ``SpotDescription``s with semantically
    equivalent inputs in different order MUST map to the same SHA-256.
    """
    cfg_a = _make_flop_config(
        board=(Card.from_str("As"), Card.from_str("Kc"), Card.from_str("7d")),
        bet_size_fractions=(0.5, 1.0, 2.0),
    )
    cfg_b = _make_flop_config(
        # Reversed board + reversed bet menu.
        board=(Card.from_str("7d"), Card.from_str("As"), Card.from_str("Kc")),
        bet_size_fractions=(2.0, 1.0, 0.5),
    )

    id_a = _make_synthetic_spot(config=cfg_a).spot_id()
    id_b = _make_synthetic_spot(config=cfg_b).spot_id()
    assert id_a == id_b, (
        "spot_id MUST be order-invariant under spec §2.3 rules 1+3 "
        f"(got {id_a!r} vs {id_b!r})"
    )


def test_library_spot_id_differs_on_meaningful_change(tmp_path: Path) -> None:
    """4. Per-element sensitivity: stack, board, bet menu (spec §2.3 + crit-item 2).

    Sub-assertions:
      - 4a. Stack delta of 1 BB (10000 → 10100 cents) → different ID.
      - 4b. Board card swap (As → Ah) → different ID.
      - 4c. Bet menu entry delta (drop 2.0) → different ID.
      - 4d. Label-only change → SAME ID (spec §2.3 lists 7 canonicalization
            rules; label is NOT among them, so by spec it cannot affect
            the spot_id). If this fails, flag for orchestrator — do NOT
            silently change the assertion.
    """
    baseline_cfg = _make_flop_config()
    baseline = _make_synthetic_spot(config=baseline_cfg).spot_id()

    # 4a. Stack delta.
    cfg_stack = _make_flop_config(starting_stack=10_100)
    id_stack = _make_synthetic_spot(config=cfg_stack).spot_id()
    assert id_stack != baseline, "spot_id must differ when stack changes"

    # 4b. Board card swap.
    cfg_board = _make_flop_config(
        board=(Card.from_str("Ah"), Card.from_str("Kc"), Card.from_str("7d"))
    )
    id_board = _make_synthetic_spot(config=cfg_board).spot_id()
    assert id_board != baseline, "spot_id must differ when board changes"

    # 4c. Bet menu entry delta.
    cfg_bet = _make_flop_config(bet_size_fractions=(0.5, 1.0))
    id_bet = _make_synthetic_spot(config=cfg_bet).spot_id()
    assert id_bet != baseline, "spot_id must differ when bet menu changes"

    # 4d. Label-only change: spec §2.3 rules 1-7 do not mention label.
    id_label = _make_synthetic_spot(config=baseline_cfg, label="renamed").spot_id()
    assert id_label == baseline, (
        "spot_id should NOT depend on label (spec §2.3 rules 1-7 omit "
        "label). If this fails, flag spec/impl mismatch for orchestrator "
        "resolution; do not silently change the assertion."
    )


def test_library_put_duplicate_raises_without_overwrite(tmp_path: Path) -> None:
    """5. Second ``put`` on the same spot raises ``LibraryDuplicateError``."""
    from poker_solver.library import Library, LibraryDuplicateError

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        result = _make_synthetic_result()
        lib.put(spot, result)
        with pytest.raises(LibraryDuplicateError):
            lib.put(spot, result)
    finally:
        lib.close()


def test_library_put_duplicate_succeeds_with_overwrite(tmp_path: Path) -> None:
    """6. ``put(overwrite=True)`` replaces; ``get`` returns the latest result."""
    from poker_solver.library import Library

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        first = _make_synthetic_result(iterations=10)
        modified = _make_synthetic_result(
            iterations=20,
            average_strategy={"infoset1": [0.7, 0.3], "infoset2": [0.4, 0.6]},
            game_value=1.5,
        )

        lib.put(spot, first)
        lib.put(spot, modified, overwrite=True)

        returned = lib.get(spot)
        assert returned is not None
        assert returned.iterations == 20
        assert returned.average_strategy == modified.average_strategy
        assert returned.game_value == pytest.approx(1.5)
    finally:
        lib.close()


def test_library_list_returns_metadata_only(tmp_path: Path) -> None:
    """7. ``list()`` returns ``SpotMetadata`` only — never decompresses strategy.

    Per spec §3.2, ``SpotMetadata`` carries no strategy field; the
    surface is intentionally narrow so list() is fast on large libraries.
    """
    from poker_solver.library import Library, SpotMetadata

    lib = Library.open(tmp_path / "lib.db")
    try:
        for i, label in enumerate(("alpha", "beta", "gamma")):
            # Vary the bet menu so each spot has a distinct id.
            cfg = _make_flop_config(
                bet_size_fractions=tuple(
                    round(0.5 + 0.1 * i + 0.5 * j, 6) for j in range(3)
                )
            )
            lib.put(
                _make_synthetic_spot(config=cfg, label=label),
                _make_synthetic_result(),
            )

        rows = lib.list()
        assert len(rows) == 3
        for row in rows:
            assert isinstance(row, SpotMetadata)
            assert not hasattr(
                row, "average_strategy"
            ), "SpotMetadata must not carry the decompressed strategy blob"
            assert not hasattr(
                row, "strategy"
            ), "SpotMetadata must not carry a strategy field"
    finally:
        lib.close()


def test_library_list_filter_by_street(tmp_path: Path) -> None:
    """8. ``LibraryFilter(street="river")`` returns only river spots."""
    from poker_solver.library import Library, LibraryFilter

    lib = Library.open(tmp_path / "lib.db")
    try:
        lib.put(
            _make_synthetic_spot(config=_make_flop_config(), label="flop_one"),
            _make_synthetic_result(),
        )
        lib.put(
            _make_synthetic_spot(config=_make_turn_config(), label="turn_one"),
            _make_synthetic_result(),
        )
        lib.put(
            _make_synthetic_spot(config=_make_river_config(), label="river_one"),
            _make_synthetic_result(),
        )

        rows = lib.list(LibraryFilter(street="river"))
        assert len(rows) == 1, f"expected 1 river row; got {len(rows)}"
        assert rows[0].label == "river_one"
        assert rows[0].street == "river"
    finally:
        lib.close()


def test_library_list_filter_combines_multiple(tmp_path: Path) -> None:
    """9. ``LibraryFilter`` AND-combines: street AND stack_bb_min/max."""
    from poker_solver.library import Library, LibraryFilter

    lib = Library.open(tmp_path / "lib.db")
    try:
        # Four spots: two flops (stacks 50 BB, 120 BB), one turn (100 BB),
        # one river (100 BB).
        # HUNLConfig stacks are in cents; BB = big_blind=100, so 100 BB = 10_000.
        for stack_bb, cfg_maker, label in (
            (50, _make_flop_config, "flop_50"),
            (120, _make_flop_config, "flop_120"),
            (100, _make_turn_config, "turn_100"),
            (100, _make_river_config, "river_100"),
        ):
            if cfg_maker is _make_flop_config:
                cfg = _make_flop_config(starting_stack=stack_bb * 100)
            elif cfg_maker is _make_turn_config:
                cfg = _make_turn_config(starting_stack=stack_bb * 100)
            else:
                cfg = _make_river_config(starting_stack=stack_bb * 100)
            lib.put(
                _make_synthetic_spot(config=cfg, label=label),
                _make_synthetic_result(),
            )

        # Both flop spots: only stack 50 falls in [40, 100]; flop_120 is
        # excluded by stack_bb_max=100. So expected = {flop_50}.
        rows = lib.list(LibraryFilter(street="flop", stack_bb_min=40, stack_bb_max=100))
        labels = {r.label for r in rows}
        assert labels == {"flop_50"}, (
            f"AND-combined filter (street=flop, stacks 40..100) yielded "
            f"{labels!r}; expected {{'flop_50'}}"
        )
    finally:
        lib.close()


def test_library_export_import_roundtrip(tmp_path: Path) -> None:
    """10. export → delete → import_ preserves the SolveResult bit-exactly."""
    from poker_solver.library import Library

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        original = _make_synthetic_result()
        spot_id = lib.put(spot, original)

        export_path = tmp_path / "export.json"
        lib.export(spot_id, export_path)
        assert export_path.exists() and export_path.stat().st_size > 0

        lib.delete(spot_id)
        assert lib.get(spot) is None, "get must return None after delete"

        reimported_id = lib.import_(export_path)
        assert reimported_id == spot_id

        roundtripped = lib.get(spot)
        assert roundtripped is not None
        assert roundtripped.average_strategy == original.average_strategy
        assert roundtripped.game_value == pytest.approx(original.game_value)
        assert roundtripped.iterations == original.iterations
    finally:
        lib.close()


def test_library_compression_preserves_bit_exact_strategy(tmp_path: Path) -> None:
    """11. gzip + JSON roundtrip preserves IEEE-754 float bits.

    Per spec §2.4: "Bit-exact roundtrip required — the float values must
    compare ``==`` after roundtrip." Tested with edge-of-precision values.
    """
    from poker_solver.library import Library

    # Edge cases: zero, one, near-zero, near-one, mid-precision.
    edge_strategy = {
        "edge": [
            0.0,
            1.0,
            1e-15,
            1.0 - 1e-15,
            0.123456789012345,
            0.987654321098765,
        ],
        "normal": [0.25, 0.25, 0.25, 0.25],
    }

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        original = _make_synthetic_result(average_strategy=edge_strategy)
        lib.put(spot, original)

        returned = lib.get(spot)
        assert returned is not None
        for key, original_values in edge_strategy.items():
            returned_values = returned.average_strategy[key]
            assert len(returned_values) == len(original_values)
            for i, (orig_val, ret_val) in enumerate(
                zip(original_values, returned_values, strict=True)
            ):
                assert ret_val == orig_val, (
                    f"bit-exact roundtrip failed at {key}[{i}]: "
                    f"original={orig_val!r}, returned={ret_val!r}"
                )
    finally:
        lib.close()


def test_library_concurrent_readers_dont_corrupt(tmp_path: Path) -> None:
    """12. WAL mode: one writer + one concurrent reader, no corruption.

    Two threads share one DB file; the writer inserts 10 spots, the
    reader polls ``list()`` repeatedly. Reads must monotonically grow
    (or hold), and no thread raises.
    """
    from poker_solver.library import Library

    db_path = tmp_path / "lib.db"
    # Bootstrap the schema with a primary instance to avoid open-race on
    # the schema-create path.
    Library.open(db_path).close()

    errors: list[BaseException] = []
    counts: list[int] = []
    stop_flag = threading.Event()

    def writer() -> None:
        try:
            lib = Library.open(db_path)
            try:
                for i in range(10):
                    cfg = _make_flop_config(
                        # Vary bet menu so each spot has a unique id.
                        bet_size_fractions=tuple(
                            round(0.5 + 0.1 * j + 0.01 * i, 6) for j in range(3)
                        )
                    )
                    lib.put(
                        _make_synthetic_spot(config=cfg, label=f"w{i}"),
                        _make_synthetic_result(),
                    )
                    time.sleep(0.01)
            finally:
                lib.close()
        except BaseException as exc:  # pragma: no cover - failure visibility
            errors.append(exc)
        finally:
            stop_flag.set()

    def reader() -> None:
        try:
            lib = Library.open(db_path)
            try:
                while not stop_flag.is_set():
                    rows = lib.list()
                    counts.append(len(rows))
                    time.sleep(0.005)
                # One final read after writer completes.
                counts.append(len(lib.list()))
            finally:
                lib.close()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    w = threading.Thread(target=writer)
    r = threading.Thread(target=reader)
    w.start()
    r.start()
    w.join(timeout=10.0)
    r.join(timeout=10.0)

    assert not w.is_alive() and not r.is_alive(), "threads did not finish"
    assert not errors, f"concurrent access raised: {errors!r}"
    assert counts, "reader produced no observations"
    # Monotonic non-decreasing growth (WAL allows stale reads, but never
    # higher than the eventual final count).
    final = max(counts)
    assert final == 10, f"final visible row count = {final}; expected 10"
    for prev, nxt in zip(counts, counts[1:], strict=False):
        assert nxt >= prev, f"reader count went backwards: {prev} -> {nxt}"


def test_library_delete_removes_spot(tmp_path: Path) -> None:
    """13. ``delete`` makes the spot disappear; deleting twice raises ``KeyError``."""
    from poker_solver.library import Library

    lib = Library.open(tmp_path / "lib.db")
    try:
        spot = _make_synthetic_spot()
        spot_id = lib.put(spot, _make_synthetic_result())

        lib.delete(spot_id)
        assert lib.get(spot) is None
        rows = lib.list()
        assert spot_id not in {r.spot_id for r in rows}

        # Deleting again raises KeyError per spec §3.1 + Agent A contract.
        with pytest.raises(KeyError):
            lib.delete(spot_id)
    finally:
        lib.close()


def test_library_stats_counts_match(tmp_path: Path) -> None:
    """14. ``stats()`` reports total_count, by_street breakdown, size+timestamps."""
    from poker_solver.library import Library

    lib = Library.open(tmp_path / "lib.db")
    try:
        plan = [
            (_make_flop_config, "flop", "f1"),
            (
                lambda: _make_flop_config(starting_stack=20_000),
                "flop",
                "f2",
            ),
            (_make_turn_config, "turn", "t1"),
            (
                lambda: _make_turn_config(starting_stack=20_000),
                "turn",
                "t2",
            ),
            (_make_river_config, "river", "r1"),
        ]
        for cfg_factory, _street, label in plan:
            lib.put(
                _make_synthetic_spot(config=cfg_factory(), label=label),
                _make_synthetic_result(),
            )

        stats = lib.stats()
        assert stats.total_count == 5
        assert stats.by_street == {
            "flop": 2,
            "turn": 2,
            "river": 1,
        }, f"by_street mismatch: {stats.by_street!r}"
        assert stats.total_size_bytes > 0
        assert stats.oldest_created_at is not None
        assert stats.newest_created_at is not None
        assert stats.oldest_created_at <= stats.newest_created_at
    finally:
        lib.close()


def test_library_schema_version_mismatch_errors(tmp_path: Path) -> None:
    """15. Forward-incompatible library_version triggers ``LibrarySchemaError``.

    Bootstrap the schema, then inject a ``library_version=999`` row into
    ``spots_meta`` via a raw connection. Reopening via ``Library.open``
    MUST raise ``LibrarySchemaError`` with a "newer" hint (spec §11 #8 +
    decision 13.5: "if newer, errors loudly").
    """
    from poker_solver.library import Library, LibrarySchemaError

    db_path = tmp_path / "lib.db"
    Library.open(db_path).close()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO spots_meta (key, value) VALUES "
            "('library_version', '999')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(LibrarySchemaError) as exc_info:
        Library.open(db_path)
    msg = str(exc_info.value).lower()
    assert (
        "newer" in msg
    ), f"LibrarySchemaError message must mention 'newer'; got {msg!r}"
