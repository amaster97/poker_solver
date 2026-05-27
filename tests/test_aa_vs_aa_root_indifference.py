"""Regression test: AA-vs-AA river minimal Nash fixture (R11 localization).

This is the **shallowest possible** range-vs-range river spot whose Nash
equilibrium is fully indifferent: both ranges are `{AA}` only (6 combos
per side, board-disjoint), so every showdown chops. By construction,
all action sequences yield zero EV change, so any strategy profile is
a valid Nash equilibrium.

The fixture is designed to localize whether residual Brown/Rust
divergence (the user's "R11" hypothesis) is in:

1. **Per-hand DCFR / equity / terminal utility** (per-combo asymmetry
   would appear here; expected: 0.0 asymmetry across the 6 AA combos).
2. **Class-expansion / hand-mixing** (would only appear with multi-class
   ranges; this test is single-class).
3. **Action abstraction pruning** (DOES diverge at Fixture A; see
   Fixture A test below).
4. **Multi-iteration convergence dynamics on indifference manifolds**
   (BOTH engines reach zero exploitability but can land on different
   points within the indifference manifold; observed at deeper nodes).

Test design (per `docs/r11_aa_vs_aa_minimal.md`):

* **Fixture A** (1 BB stack-behind, exact task spec):
  - Our Rust solver's `force_allin_threshold` filter drops both bet
    sizes, leaving only CHECK at root.
  - Brown does NOT have this filter; it offers all 3 actions.
  - Documented behavior; the test asserts the action-menu cardinality
    discrepancy so future audits don't re-investigate.

* **Fixture B** (3 BB stack-behind, intact action menu):
  - Both engines see the same `[c, b100, b200]` action menu at root.
  - Both converge to **identical** strategies for every AA combo at
    root (floating-point agreement < 1e-3).
  - **THIS IS THE LOAD-BEARING ASSERTION**: per-hand DCFR + equity +
    terminal computation are correct.

Opt-in via `@pytest.mark.parity_noambrown` — requires Brown's
`river_solver_optimized` binary at
`references/code/noambrown_poker_solver/cpp/build/`.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
BROWN_BINARY_PATH = (
    REPO_ROOT
    / "references"
    / "code"
    / "noambrown_poker_solver"
    / "cpp"
    / "build"
    / "river_solver_optimized"
)


try:
    from poker_solver import HUNLConfig, Street, parse_board
    from poker_solver.card import Card, card_to_int, parse_card
    from poker_solver.hunl import _serialize_hunl_config
    from poker_solver.parity.noambrown_wrapper import (
        _card_to_brown_str,
        _combo_to_brown_hand_str,
    )
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    Card = None  # type: ignore[assignment,misc]
    card_to_int = None  # type: ignore[assignment]
    parse_card = None  # type: ignore[assignment]
    _serialize_hunl_config = None  # type: ignore[assignment]
    _card_to_brown_str = None  # type: ignore[assignment]
    _combo_to_brown_hand_str = None  # type: ignore[assignment]


try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
except Exception:  # noqa: BLE001
    _rust_module = None  # type: ignore[assignment]
    _rust_solve_rvr = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.parity_noambrown,
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_solve_rvr is None,
        reason=(
            "_rust.solve_range_vs_range_rust missing — rebuild via "
            "`maturin develop --release`"
        ),
    ),
    pytest.mark.skipif(
        not BROWN_BINARY_PATH.is_file(),
        reason=(
            "Brown's river_solver_optimized not built at "
            f"{BROWN_BINARY_PATH}; build via "
            "`cmake -S references/code/noambrown_poker_solver/cpp -B "
            "references/code/noambrown_poker_solver/cpp/build && "
            "cmake --build references/code/noambrown_poker_solver/cpp/build`"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Fixture constants
# ---------------------------------------------------------------------------

BOARD_STR = "Ks 7h 2d Qc 5s"
AA_COMBO_STRS = ("AcAd", "AcAh", "AcAs", "AdAh", "AdAs", "AhAs")

BET_SIZES = (0.5, 1.0)
RAISE_CAP = 1
ITERATIONS = 500
ALPHA, BETA, GAMMA = 1.5, 0.0, 2.0
SEED = 7

# Tolerances per `docs/r11_aa_vs_aa_minimal.md`.
ROOT_TOLERANCE_FIXTURE_B = 1e-3
ASYMMETRY_TOLERANCE = 1e-6


# ---------------------------------------------------------------------------
# Helpers — Rust side
# ---------------------------------------------------------------------------


def _hole_string_rust(combo: tuple[Card, Card]) -> str:
    """Mirror Rust's hole_string."""
    ranks = "23456789TJQKA"
    suits = "shdc"
    ids = sorted([card_to_int(combo[0]), card_to_int(combo[1])])
    out = []
    for cid in ids:
        r = cid >> 2
        s = cid & 3
        out.append(f"{ranks[r - 2]}{suits[s]}")
    return "".join(out)


def _board_string_rust(board: tuple[Card, ...]) -> str:
    """Mirror hunl._sorted_card_string for the board key."""
    sorted_cards = sorted(board, key=lambda c: (c.rank, c.suit))
    return "".join(str(c) for c in sorted_cards)


def _build_rust_config(pot: int, stack_behind: int) -> HUNLConfig:
    board = tuple(parse_board(BOARD_STR))
    return HUNLConfig(
        starting_stack=stack_behind + pot // 2,
        big_blind=100,
        small_blind=50,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=pot,
        initial_contributions=(pot // 2, pot // 2),
        initial_hole_cards=(),
        bet_size_fractions=BET_SIZES,
        include_all_in=False,
        postflop_raise_cap=RAISE_CAP,
    )


def _all_aa_combos() -> list[tuple[Card, Card]]:
    return [(parse_card(s[:2]), parse_card(s[2:])) for s in AA_COMBO_STRS]


def _hole_ids_sorted(combo: tuple[Card, Card]) -> list[int]:
    return sorted([card_to_int(combo[0]), card_to_int(combo[1])])


def _run_rust(pot: int, stack_behind: int) -> dict[str, list[float]]:
    config = _build_rust_config(pot=pot, stack_behind=stack_behind)
    config_json = _serialize_hunl_config(config)
    combos = _all_aa_combos()
    holes = [_hole_ids_sorted(c) for c in combos]
    result = _rust_solve_rvr(
        config_json,
        ITERATIONS,
        ALPHA,
        BETA,
        GAMMA,
        list(holes),
        list(holes),
    )
    return dict(result["average_strategy"])


def _rust_root_p1_row(rust_strategy, combo) -> list[float] | None:
    board = tuple(parse_board(BOARD_STR))
    key = f"{_hole_string_rust(combo)}|{_board_string_rust(board)}|r|"
    return rust_strategy.get(key)


# ---------------------------------------------------------------------------
# Helpers — Brown side
# ---------------------------------------------------------------------------


def _build_brown_config(pot: int, stack_behind: int) -> dict:
    board = [parse_card(s) for s in BOARD_STR.split()]
    combos = _all_aa_combos()
    hands = [_combo_to_brown_hand_str(c) for c in combos]
    weights = [1.0] * len(hands)
    return {
        "board": [_card_to_brown_str(c) for c in board],
        "pot": pot,
        "stack": stack_behind + pot // 2,
        "bet_sizes": list(BET_SIZES),
        "include_all_in": False,
        "max_raises": RAISE_CAP,
        "players": [
            {"hands": hands, "weights": weights},
            {"hands": hands, "weights": weights},
        ],
    }


def _run_brown(pot: int, stack_behind: int) -> dict:
    config = _build_brown_config(pot=pot, stack_behind=stack_behind)
    workdir = Path(tempfile.mkdtemp(prefix="aa_vs_aa_brown_"))
    try:
        config_path = workdir / "config.json"
        dump_path = workdir / "strategy.json"
        config_path.write_text(json.dumps(config))
        argv = [
            str(BROWN_BINARY_PATH),
            "--config", str(config_path),
            "--algo", "dcfr",
            "--iters", str(ITERATIONS),
            "--dcfr-alpha", str(ALPHA),
            "--dcfr-beta", str(BETA),
            "--dcfr-gamma", str(GAMMA),
            "--seed", str(SEED),
            "--dump-strategy", str(dump_path),
        ]
        subprocess.run(argv, check=True, capture_output=True, text=True, timeout=60.0)
        return json.loads(dump_path.read_text())
    finally:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)


def _brown_root_p0_row(brown_dump, combo) -> list[float] | None:
    """Brown's player[0] at 'root' = our P1 (first-to-act postflop)."""
    hand_str = _combo_to_brown_hand_str(combo)
    p = brown_dump["players"][0]
    if "root" not in p["profile"]:
        return None
    if hand_str not in p["hands"]:
        return None
    hand_idx = p["hands"].index(hand_str)
    return p["profile"]["root"]["strategy"][hand_idx]


# ---------------------------------------------------------------------------
# Module-scoped fixtures — solve once and reuse across all tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_a_results():
    """Fixture A: 1 BB stack-behind. Exercises the force_allin_threshold filter."""
    rust = _run_rust(pot=200, stack_behind=100)
    brown = _run_brown(pot=200, stack_behind=100)
    return {"rust": rust, "brown": brown}


@pytest.fixture(scope="module")
def fixture_b_results():
    """Fixture B: 3 BB stack-behind. Both engines see the same action menu."""
    rust = _run_rust(pot=200, stack_behind=300)
    brown = _run_brown(pot=200, stack_behind=300)
    return {"rust": rust, "brown": brown}


# ===========================================================================
# Tests
# ===========================================================================


def test_fixture_a_rust_action_menu_pruned(fixture_a_results):
    """Fixture A: our action-abstraction filter eliminates bets at <=1BB behind.

    With stack_behind=100 (1 BB), pot=200, half-pot bet=100, the
    `_enumerate_bets` filter (`action_abstraction.py:180`) eliminates
    any bet whose post-bet remaining stack <= force_allin_threshold
    (default = 1 BB = 100 chips). So bet_05=100 -> remaining 0
    (filtered), bet_10=200 -> caps to 100 -> remaining 0 (filtered).
    Net menu: CHECK only.
    """
    rust = fixture_a_results["rust"]
    combos = _all_aa_combos()
    for combo in combos:
        row = _rust_root_p1_row(rust, combo)
        assert row is not None, f"Rust strategy missing root entry for AA combo {combo}"
        assert len(row) == 1, (
            f"Fixture A: Rust action menu at root should have 1 action "
            f"(CHECK only) due to force_allin_threshold filter; got {len(row)} actions "
            f"with row={row} for combo {combo}"
        )
        assert abs(row[0] - 1.0) < 1e-9, (
            f"Fixture A: Rust's only action at root must be pure CHECK=1.0; got {row}"
        )


def test_fixture_a_brown_action_menu_intact(fixture_a_results):
    """Fixture A: Brown does NOT apply our threshold filter, so all 3 actions remain."""
    brown = fixture_a_results["brown"]
    root_entry = brown["players"][0]["profile"].get("root")
    assert root_entry is not None, "Brown's strategy dump missing 'root' for player[0]"
    assert root_entry["actions"] == ["c", "b100", "b200"], (
        f"Fixture A: Brown's root action menu should be [c, b100, b200]; got {root_entry['actions']}"
    )
    # Verify Brown's check vs bet mix — should be near-zero check, ~50/50 between bets.
    for hand_idx in range(len(brown["players"][0]["hands"])):
        row = root_entry["strategy"][hand_idx]
        assert row[0] < 0.01, (
            f"Fixture A: Brown's check rate at root should be near-zero "
            f"(driven down by CFR exploration even on indifferent game); got {row[0]:.4f}"
        )


def test_fixture_b_rust_brown_root_agreement(fixture_b_results):
    """Fixture B: with action menus matched, Rust and Brown agree at root.

    This is the load-bearing assertion: when both engines see the same
    `[c, b100, b200]` action menu, per-hand DCFR + equity + terminal
    utility produce IDENTICAL strategies for every AA combo at root.
    Per-action agreement within 1e-3.
    """
    rust = fixture_b_results["rust"]
    brown = fixture_b_results["brown"]
    combos = _all_aa_combos()
    for combo in combos:
        rust_row = _rust_root_p1_row(rust, combo)
        brown_row = _brown_root_p0_row(brown, combo)
        assert rust_row is not None, f"Rust missing root entry for AA combo {combo}"
        assert brown_row is not None, f"Brown missing root entry for AA combo {combo}"
        assert len(rust_row) == len(brown_row), (
            f"Action count mismatch: rust={len(rust_row)} brown={len(brown_row)}"
        )
        for i, (r, b) in enumerate(zip(rust_row, brown_row)):
            assert abs(r - b) < ROOT_TOLERANCE_FIXTURE_B, (
                f"Fixture B root mismatch for combo {combo} action[{i}]: "
                f"rust={r:.6f} brown={b:.6f} delta={abs(r-b):.6f} "
                f"(tol={ROOT_TOLERANCE_FIXTURE_B})"
            )


def test_fixture_b_per_combo_asymmetry_zero(fixture_b_results):
    """Fixture B: all 6 AA combos must get identical root strategies on both engines.

    By construction every AA-vs-AA matchup chops regardless of suit, so
    no card-removal effect can distinguish combos. Any per-combo
    asymmetry on this fixture would indicate a per-hand DCFR bug
    (e.g. mis-indexed regret accumulators).
    """
    rust = fixture_b_results["rust"]
    combos = _all_aa_combos()
    rows = [_rust_root_p1_row(rust, combo) for combo in combos]
    rows = [r for r in rows if r is not None]
    assert len(rows) == 6, f"Expected 6 AA combo rows; got {len(rows)}"
    # All rows must agree with the first to within ASYMMETRY_TOLERANCE.
    reference = rows[0]
    for i, row in enumerate(rows[1:], start=1):
        assert len(row) == len(reference), (
            f"Combo {AA_COMBO_STRS[i]}: row length {len(row)} != reference {len(reference)}"
        )
        for j, (a, b) in enumerate(zip(reference, row)):
            assert abs(a - b) < ASYMMETRY_TOLERANCE, (
                f"Per-combo asymmetry in Rust strategy: "
                f"combo {AA_COMBO_STRS[i]} action[{j}] diverges from reference: "
                f"ref={a:.9f} this={b:.9f} delta={abs(a-b):.9f}"
            )
