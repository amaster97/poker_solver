"""Fixture builders for PR 5 HUNL postflop solve tests.

Per PR 5 spec §9.5: exposes five constructors so test files can build the
three canonical postflop scenarios (river-only, flop-dry 3-size, flop-full
menu) plus the monotone polarization gauntlet, and a tiny in-memory
``AbstractionTables`` artifact that all flop-start tests share.

Determinism is enforced by:
- All ``HUNLConfig`` constructors pin ``initial_hole_cards`` and
  ``initial_board`` explicitly.
- The synthetic abstraction is built once at module import via
  ``build_abstraction`` with ``seed=42``, ``mc_iterations=100``,
  ``max_boards_per_street=8``, ``max_hands_per_board=16``.

Per spec §14 + agent brief, ``bucket_counts=(4, 2, 2)`` is the chosen
fixture-2 abstraction shape (spec §9.5 wins over the §8 mention of
``(16, 8, 4)``).
"""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path

from poker_solver import (
    AbstractionRef,
    AbstractionTables,
    Card,
    HUNLConfig,
    Street,
    build_abstraction,
    default_tiny_subgame,
    resolve_abstraction_ref,
)

# Cards used by the three postflop fixtures. Defined as module constants so
# tests can reference them directly when looking up specific infosets.
FIXTURE_RIVER_BOARD: tuple[Card, ...] = (
    Card.from_str("As"),
    Card.from_str("7c"),
    Card.from_str("2d"),
    Card.from_str("Kh"),
    Card.from_str("5s"),
)
FIXTURE_FLOP_BOARD_DRY: tuple[Card, ...] = (
    Card.from_str("As"),
    Card.from_str("7c"),
    Card.from_str("2d"),
)
FIXTURE_FLOP_BOARD_MONOTONE: tuple[Card, ...] = (
    Card.from_str("8h"),
    Card.from_str("7h"),
    Card.from_str("6h"),
)

# Hole-card pairs for each fixture. Mirrors PR 3's ``default_tiny_subgame``
# pattern (P0 = AhKc strong, P1 = QdQh medium). The flop fixtures use
# AhKh (overpair candidate on the As-7c-2d board) for the gauntlet check.
FIXTURE_RIVER_HOLES: tuple[tuple[Card, Card], tuple[Card, Card]] = (
    (Card.from_str("Ah"), Card.from_str("Kc")),
    (Card.from_str("Qd"), Card.from_str("Qh")),
)
FIXTURE_FLOP_HOLES_DRY: tuple[tuple[Card, Card], tuple[Card, Card]] = (
    (Card.from_str("Ah"), Card.from_str("Kh")),
    (Card.from_str("Qd"), Card.from_str("Jd")),
)
FIXTURE_FLOP_HOLES_MONOTONE: tuple[tuple[Card, Card], tuple[Card, Card]] = (
    (Card.from_str("Kc"), Card.from_str("Ks")),
    (Card.from_str("Ad"), Card.from_str("Qd")),
)

ABSTRACTION_VERSION: str = "test-v1"
"""Version string both the on-disk artifact and the ``AbstractionRef``
carry. Per PR 4 the AbstractionRef.version must match the on-disk
metadata['version'] for the LRU loader to accept the resolution."""


def river_subgame_config() -> HUNLConfig:
    """PR 3 default_tiny_subgame, river-only, lossless.

    Per spec §3.4 fixture 1 + §9.5: ``AhKc`` vs ``QdQh`` on
    ``As 7c 2d Kh 5s``, SPR ~1, no abstraction. Mirrors the PR 3
    ``default_tiny_subgame()`` exactly (we re-create it instead of
    importing so a future change to the PR 3 default does not silently
    drift our tests).
    """
    return HUNLConfig(
        starting_stack=1000,
        starting_street=Street.RIVER,
        initial_board=FIXTURE_RIVER_BOARD,
        initial_pot=1000,
        initial_contributions=(500, 500),
        initial_hole_cards=FIXTURE_RIVER_HOLES,
    )


def flop_dry_3size_config(*, abstraction: AbstractionRef | None = None) -> HUNLConfig:
    """Spec §3.4 fixture 2: dry flop ``As 7c 2d``, 100 BB stacks, 3 bet sizes.

    Per spec §14 #4 the default ``bet_size_fractions`` is
    ``(0.33, 0.75, 2.00)`` (3 sizes; locked default). Caller supplies
    the abstraction via the optional kwarg so the standard
    abstraction-shared-across-tests pattern works.
    """
    return HUNLConfig(
        starting_stack=10_000,  # 100 BB at 100 cents per BB
        starting_street=Street.FLOP,
        initial_board=FIXTURE_FLOP_BOARD_DRY,
        initial_pot=200,  # 1 BB SB + 1 BB BB = pre-action limp pot
        initial_contributions=(0, 0),
        initial_hole_cards=FIXTURE_FLOP_HOLES_DRY,
        bet_size_fractions=(0.33, 0.75, 2.00),
        postflop_raise_cap=3,
        abstraction=abstraction,
    )


def flop_full_menu_config(*, abstraction: AbstractionRef | None = None) -> HUNLConfig:
    """Spec §3.4 fixture 3: same flop, full 5-size menu + all-in.

    100 BB stacks, ``bet_size_fractions=(0.33, 0.75, 1.00, 1.50, 2.00)``
    (the PR 3 default), ``include_all_in=True``, ``postflop_raise_cap=3``.
    """
    return HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=FIXTURE_FLOP_BOARD_DRY,
        initial_pot=200,
        initial_contributions=(0, 0),
        initial_hole_cards=FIXTURE_FLOP_HOLES_DRY,
        bet_size_fractions=(0.33, 0.75, 1.00, 1.50, 2.00),
        postflop_raise_cap=3,
        include_all_in=True,
        abstraction=abstraction,
    )


def monotone_flop_config(*, abstraction: AbstractionRef | None = None) -> HUNLConfig:
    """Spec §9.4 polarization gauntlet: monotone low-connected flop.

    Flop ``[8h, 7h, 6h]`` with hand ``(Kc, Ks)`` (vulnerable overpair).
    100 BB stacks, 3-size menu, postflop_raise_cap=3.
    """
    return HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.FLOP,
        initial_board=FIXTURE_FLOP_BOARD_MONOTONE,
        initial_pot=200,
        initial_contributions=(0, 0),
        initial_hole_cards=FIXTURE_FLOP_HOLES_MONOTONE,
        bet_size_fractions=(0.33, 0.75, 2.00),
        postflop_raise_cap=3,
        abstraction=abstraction,
    )


@functools.lru_cache(maxsize=1)
def _build_synthetic_artifact() -> tuple[Path, AbstractionTables]:
    """Build the shared synthetic abstraction artifact exactly once.

    Cached at module level: every call to ``tiny_synthetic_abstraction()``
    returns the same in-memory tables, and the on-disk ``.npz`` is written
    once into a session-scoped tempdir.

    Per spec §9.5 the bucket counts are ``(4, 2, 2)``. We force-include
    both the river fixture board (``As 7c 2d Kh 5s``) AND the flop dry
    board (``As 7c 2d``) plus the monotone flop board (``8h 7h 6h``)
    via ``required_boards``, and the hole pairs each fixture uses via
    ``required_hands``. This way ``lookup_bucket`` finds every (board,
    hand) the postflop solver will visit on the flop / river starting
    positions; turn/river runouts from a flop start are NOT pinned (the
    autosize cap of 8 boards / 16 hands per street covers the iteration-
    order prefix only) - Agent A's solver may need to tolerate uncovered
    runouts on flop-start tests; if it does not, that is a spec
    ambiguity for orchestrator review (spec §10 edge-case allowance).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="pr5_test_abstraction_"))
    out_path = tmpdir / "tiny_synthetic.npz"

    required_boards = [
        FIXTURE_RIVER_BOARD,
        FIXTURE_FLOP_BOARD_DRY,
        FIXTURE_FLOP_BOARD_MONOTONE,
    ]
    required_hands = [
        FIXTURE_RIVER_HOLES[0],
        FIXTURE_RIVER_HOLES[1],
        FIXTURE_FLOP_HOLES_DRY[0],
        FIXTURE_FLOP_HOLES_DRY[1],
        FIXTURE_FLOP_HOLES_MONOTONE[0],
        FIXTURE_FLOP_HOLES_MONOTONE[1],
    ]

    tables = build_abstraction(
        out_path=out_path,
        bucket_counts=(4, 2, 2),
        seed=42,
        H=10,
        max_iter=20,
        streets=(Street.FLOP, Street.TURN, Street.RIVER),
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
        max_boards_per_street=8,
        max_hands_per_board=16,
        required_boards=required_boards,
        required_hands=required_hands,
        version=ABSTRACTION_VERSION,
    )
    return out_path, tables


def tiny_synthetic_abstraction() -> AbstractionTables:
    """Return the shared ``AbstractionTables`` for postflop-with-abstraction tests.

    Per spec §9.5: bucket counts ``(4, 2, 2)`` (spec §8 fixture-2 mentions
    ``(16, 8, 4)`` but §9.5 wins because it is in Agent C's deliverables
    section). Built via ``build_abstraction`` with ``seed=42``,
    ``mc_iterations=100``, ``max_boards_per_street=8``,
    ``max_hands_per_board=16``, and the three fixture boards pinned via
    ``required_boards``.

    Deterministic across test runs (same seed -> same artifact bytes).
    Built once per session via ``functools.lru_cache``.
    """
    _, tables = _build_synthetic_artifact()
    return tables


def tiny_synthetic_abstraction_ref() -> AbstractionRef:
    """Return an ``AbstractionRef`` pointing at the on-disk synthetic artifact.

    Per PR 4 spec + consistency-review NEW-1, ``HUNLConfig.abstraction``
    holds an ``AbstractionRef`` (NOT an ``AbstractionTables``). Tests that
    want to thread the synthetic abstraction into a fixture config use
    this helper.

    Ensures the ref's version matches the on-disk metadata so
    ``resolve_abstraction_ref(ref)`` round-trips.
    """
    out_path, _ = _build_synthetic_artifact()
    return AbstractionRef(source_path=str(out_path), version=ABSTRACTION_VERSION)


def warm_abstraction_cache() -> None:
    """Resolve the synthetic abstraction once to warm the PR 4 LRU loader.

    Memory-profiler tests that include the abstraction in their accounting
    need the LRU cache populated before ``MemoryProbe`` snapshots, so the
    abstraction bytes are deterministically observable. Call this in
    ``setup_module`` or at the top of a test before constructing the
    probe.
    """
    ref = tiny_synthetic_abstraction_ref()
    resolve_abstraction_ref(ref)


# ---------------------------------------------------------------------------
# River-only abstraction (audit S4 / G1-G3 should-fix #2 follow-up).
# ---------------------------------------------------------------------------
#
# The shared ``tiny_synthetic_abstraction`` above is built across all three
# postflop streets (``streets=(FLOP, TURN, RIVER)``) with a board cap of 8;
# this leaves the TURN/RIVER tables incomplete for flop-start runouts, which
# is the documented PR 4 coverage gap. River-only solves do NOT trigger that
# gap because no chance transitions cross a street boundary — the only
# ``lookup_bucket`` calls are on the river street, and we pin the river
# fixture board explicitly via ``required_boards``.
#
# Two callers below:
#   - ``river_only_synthetic_abstraction_ref()`` for ``solve_hunl_postflop``
#   - ``river_only_synthetic_abstraction()`` returning the in-memory tables


@functools.lru_cache(maxsize=1)
def _build_river_only_artifact() -> tuple[Path, AbstractionTables]:
    """Build a river-only synthetic abstraction once per session.

    Bucket counts ``(4, 2, 2)`` (flop/turn entries are empty by virtue of
    ``streets=(Street.RIVER,)``; ``lookup_bucket`` only touches the river
    table). The river fixture board (``As 7c 2d Kh 5s``) and both river
    fixture hands are pinned via ``required_boards`` / ``required_hands``
    so ``lookup_bucket(...)`` cannot raise on the river fixture's reachable
    (board, hand) pairs.

    Used by the river-only fallback tests added per audit should-fix #2
    (spec §11 critical-correctness items #1, #3, #4, #5).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="pr5_river_only_abstraction_"))
    out_path = tmpdir / "river_only_synthetic.npz"

    required_boards = [FIXTURE_RIVER_BOARD]
    required_hands = [FIXTURE_RIVER_HOLES[0], FIXTURE_RIVER_HOLES[1]]

    tables = build_abstraction(
        out_path=out_path,
        bucket_counts=(4, 2, 2),
        seed=42,
        H=10,
        max_iter=20,
        streets=(Street.RIVER,),
        flop_mode="mc",
        mc_iterations=100,
        progress=False,
        max_boards_per_street=4,
        max_hands_per_board=8,
        required_boards=required_boards,
        required_hands=required_hands,
        version="test-river-only-v1",
    )
    return out_path, tables


def river_only_synthetic_abstraction() -> AbstractionTables:
    """Return the river-only ``AbstractionTables`` (in-memory).

    Audit should-fix #2: this artifact does NOT have FLOP/TURN entries (per
    ``streets=(Street.RIVER,)``), so the PR-4 TURN coverage gap that
    plagues flop-start tests does not apply. Safe to use with any
    river-start ``HUNLConfig``.
    """
    _, tables = _build_river_only_artifact()
    return tables


def river_only_synthetic_abstraction_ref() -> AbstractionRef:
    """Return an ``AbstractionRef`` for the river-only synthetic artifact."""
    out_path, _ = _build_river_only_artifact()
    return AbstractionRef(source_path=str(out_path), version="test-river-only-v1")


__all__ = [
    "ABSTRACTION_VERSION",
    "FIXTURE_FLOP_BOARD_DRY",
    "FIXTURE_FLOP_BOARD_MONOTONE",
    "FIXTURE_FLOP_HOLES_DRY",
    "FIXTURE_FLOP_HOLES_MONOTONE",
    "FIXTURE_RIVER_BOARD",
    "FIXTURE_RIVER_HOLES",
    "default_tiny_subgame",
    "flop_dry_3size_config",
    "flop_full_menu_config",
    "monotone_flop_config",
    "river_only_synthetic_abstraction",
    "river_only_synthetic_abstraction_ref",
    "river_subgame_config",
    "tiny_synthetic_abstraction",
    "tiny_synthetic_abstraction_ref",
    "warm_abstraction_cache",
]
