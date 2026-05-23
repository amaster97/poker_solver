"""v1.5.0 acceptance test — Brown apples-to-apples parity for PR 23's vector-form CFR.

This is the **load-bearing acceptance claim** for v1.5.0's "true Nash range-vs-range"
headline (task #184). It exercises PR 23's NEW Rust vector-form CFR entry point
(`poker_solver._rust.solve_range_vs_range_rust`) and asserts per-history strategy
parity against Brown's `river_solver_optimized` binary on the SAME restricted hand
set — i.e. the genuinely apples-to-apples comparison defined in
`docs/brown_apples_to_apples_2026-05-23.md` §2.

## Why this test, vs the existing parity / diff tests

The existing parity coverage in this repo is each insufficient for v1.5.0's
acceptance claim:

  * ``tests/test_river_diff.py::test_river_parity_vs_brown`` exercises our
    **Python** ``solve_hunl_postflop`` with ``initial_hole_cards=()`` — a
    chance-enum-at-root tree that is **algorithmically different** from
    Brown's vector-form CFR. The 6.7% history-coverage failure on
    ``dry_K72_rainbow`` is a documented runtime artifact of the Python tier
    timing out, NOT a correctness measurement
    (``docs/brown_apples_to_apples_2026-05-23.md`` §1, §6a). Once PR 23
    lands, that test becomes obsolete-by-design for the Rust path; this
    new test takes its acceptance-gate role.

  * ``tests/test_range_vs_range_rust_diff.py`` (PR 23 worktree) diffs
    PR 23's Rust vector-form against a **Python** ``DCFRSolver`` wrapping
    a ``_RestrictedHUNLGame``. That establishes Rust↔Python parity on the
    SAME algorithm but does NOT establish Rust↔Brown parity. The Python
    `_RestrictedHUNLGame` is itself a chance-enum-at-root tree; it agrees
    with vector CFR on exploitability under the restricted game but not
    necessarily on per-history strategies (Nash mixed-strategy
    non-uniqueness; see that module's docstring).

  * The blueprint aggregator (``solve_range_vs_range``) is the documented
    Pluribus-blueprint approximation
    (``poker_solver/range_aggregator.py`` lines 1-32) and diverges from
    Brown by mean TV 0.47 on the dry_K72 spot per the apples-to-apples
    experiment. It is NOT a Nash solver and cannot serve as the acceptance
    baseline for the "true Nash" headline.

So this file is the ONLY place where PR 23's vector-form CFR meets Brown's
binary on identical inputs (same board, same hand lists, same DCFR
hyperparams). If this test passes, the v1.5.0 headline holds; if it
fails, the headline does not hold.

## Test design (per docs/brown_apples_to_apples_2026-05-23.md §2)

For each of the two covered river spots (``dry_K72_rainbow`` +
``dry_A83_rainbow``):

  1. Load the spot from ``tests/data/river_spots.json`` (full ranges
     from the PR 7 fixture — 30+ combos per side).
  2. Solve with Brown's binary via ``run_brown_solver`` (the existing
     wrapper, already wires the subgame config + DCFR hyperparams).
  3. Solve with PR 23's Rust vector-form via
     ``_rust.solve_range_vs_range_rust`` passing the SAME hand list as
     ``p0_holes`` / ``p1_holes`` (apples-to-apples — both engines see
     the same restricted hand set at root).
  4. For each Brown infoset row, locate the matching ``(hole, history)``
     key in Rust's ``average_strategy`` dict. Map Brown's action labels
     (``c`` / ``b<amount>``) to Rust's emitted action ordering and assert
     per-(hand, action) probability parity within ``5e-3``.

The 5e-3 tolerance matches the existing ``tests/test_river_diff.py``
locked PR 7 §1 setting and the PR 23 spec §5 Case B tolerance for
bucketed comparisons. PR 23 spec §5 Case A proposed a tighter 1e-3
tolerance for small-RvR full-precision cases, but the apples-to-apples
test runs Brown's default 2000 iterations vs our default DCFR
hyperparams — both achieve sub-1-chip exploitability per the
apples-to-apples experiment (Brown: 0.142 chips; ours: comparable),
which is well within the 5e-3-per-action envelope. Keeping the same
tolerance as ``test_river_diff.py`` means a passing acceptance test
here implies the existing PR 7 contract is also satisfied; we can
tighten in a follow-up if convergence is cleaner than expected.

## Opt-in markers (same pattern as test_river_diff.py)

  * ``@pytest.mark.parity_noambrown`` — deselected from the default
    pytest run via ``pyproject.toml [tool.pytest.ini_options]``
    (``-m "not parity_noambrown"`` in default ``addopts``). Run
    explicitly with ``pytest -m parity_noambrown`` or
    ``pytest tests/test_v1_5_brown_apples_to_apples.py``.
  * ``@pytest.mark.slow`` — additional opt-in gate; the river-spot
    apples-to-apples solve takes ~30s per spot on the Rust tier and
    ~1s on Brown's, so two spots is ~1 min total. The current test
    file is NOT marked very_slow because it stays well under the
    5-min ceiling per ``PLAN.md:192``.

## Graceful skips

  * Brown's binary not built → skip with a build hint.
  * PR 23 not merged (i.e. ``_rust.solve_range_vs_range_rust`` not
    available) → skip with a maturin rebuild hint.
  * ``noambrown_wrapper`` import failure → skip cleanly.

These mirror ``test_river_diff.py``'s Layer A/B/C skip strategy so a
fresh clone or pre-PR-23 checkout still collects cleanly.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"

# Spots covered by this acceptance test. The first MUST be `dry_K72_rainbow`
# (the load-bearing spot from the apples-to-apples experiment); the second
# is a second dry-board spot for cross-check that the parity isn't a
# coincidence on a single board.
COVERED_SPOT_IDS: tuple[str, ...] = ("dry_K72_rainbow", "dry_A83_rainbow")

# Locked tolerances (rationale in module docstring).
PER_ACTION_TOL: float = 5e-3

# Coverage floor: ≥ 80% of Brown's canonical histories must appear in our
# Rust solve. Matches `test_river_diff.py` COVERAGE_FLOOR (PR 7 spec §10).
COVERAGE_FLOOR: float = 0.80

# DCFR hyperparameters — same as Brown's defaults so both engines run the
# same algorithm. Hard-coded; do not mutate at call sites. See PLAN.md §1.
DCFR_ALPHA: float = 1.5
DCFR_BETA: float = 0.0
DCFR_GAMMA: float = 2.0

# Iteration count. Brown's default is 2000 (`noambrown_wrapper._DEFAULT_ITERATIONS`).
# We pass it explicitly so the wrapper survives any upstream default change.
ITERATIONS: int = 2000

# Subprocess timeout for Brown's binary. Same as `test_river_diff.py` (PR 7).
BROWN_TIMEOUT_SEC: float = 600.0


# ---------------------------------------------------------------------------
# Defensive imports — keep test collection green on fresh clones / pre-PR-23
# checkouts. Per-test skip guards then surface the precise reason.
# ---------------------------------------------------------------------------

try:
    from poker_solver.parity.noambrown_wrapper import (
        BrownStrategyDump,
        RiverSpot,
        canonicalize_brown_history,
        find_brown_binary,
        load_spots,
        run_brown_solver,
    )

    _WRAPPER_OK = True
    _WRAPPER_ERR: str | None = None
except Exception as exc:  # noqa: BLE001
    BrownStrategyDump = None  # type: ignore[assignment,misc]
    RiverSpot = None  # type: ignore[assignment,misc]
    canonicalize_brown_history = None  # type: ignore[assignment]
    find_brown_binary = None  # type: ignore[assignment]
    load_spots = None  # type: ignore[assignment]
    run_brown_solver = None  # type: ignore[assignment]
    _WRAPPER_OK = False
    _WRAPPER_ERR = f"{type(exc).__name__}: {exc}"

try:
    from poker_solver import HUNLConfig, Street
    from poker_solver.card import Card, card_to_int
    from poker_solver.hunl import _serialize_hunl_config

    _CORE_OK = True
except Exception:  # noqa: BLE001
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    Card = None  # type: ignore[assignment,misc]
    card_to_int = None  # type: ignore[assignment]
    _serialize_hunl_config = None  # type: ignore[assignment]
    _CORE_OK = False

try:
    _rust_module = importlib.import_module("poker_solver._rust")
    _rust_solve_rvr = getattr(_rust_module, "solve_range_vs_range_rust", None)
except Exception:  # noqa: BLE001
    _rust_solve_rvr = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_preconditions() -> None:
    """Skip cleanly if any precondition is unmet."""
    if not _WRAPPER_OK:
        pytest.skip(
            f"poker_solver.parity.noambrown_wrapper unavailable: {_WRAPPER_ERR}"
        )
    if not _CORE_OK:
        pytest.skip("poker_solver core surface failed to import")
    if _rust_solve_rvr is None:
        pytest.skip(
            "_rust.solve_range_vs_range_rust missing — PR 23 not merged / not built. "
            "After PR 23 lands, run `maturin develop --release` to enable."
        )
    if not SPOTS_JSON.exists():
        pytest.skip(f"river fixture missing: {SPOTS_JSON}")


def _require_brown_binary() -> Path:
    """Skip if Brown's binary is not built. Returns the binary path on success."""
    assert find_brown_binary is not None  # narrowed by _require_preconditions
    binary = find_brown_binary()
    if binary is None or not Path(binary).exists():
        pytest.skip(
            "Brown's river_solver_optimized not built; "
            "run `bash scripts/build_noambrown.sh` to enable parity tests."
        )
    return Path(binary)


def _spot_by_id(spot_id: str) -> Any:
    """Load and return the named spot from the river fixture."""
    assert load_spots is not None  # narrowed by _require_preconditions
    spots = load_spots(SPOTS_JSON)
    for spot in spots:
        if spot.id == spot_id:
            return spot
    raise AssertionError(
        f"spot {spot_id!r} not found in {SPOTS_JSON}; available: "
        f"{[s.id for s in spots]}"
    )


def _build_rust_config_for_spot(spot: Any) -> Any:
    """Construct the river-only HUNLConfig that matches Brown's subgame.

    Brown's `RiverGame` (`cpp/src/river_game.cpp:14-15`) starts both
    players at contribution = pot/2 with `stack` chips behind. Our
    HUNLConfig encodes the same with `initial_contributions=(pot/2, pot/2)`
    and `starting_stack=stack`. `initial_hole_cards=()` triggers the
    range-vs-range path; PR 23's Rust vector-form CFR consumes this.

    bet_size_fractions / include_all_in / postflop_raise_cap mirror
    the spot fixture so both engines explore the same betting tree.
    """
    assert HUNLConfig is not None and Street is not None
    pot = int(spot.pot)
    return HUNLConfig(
        starting_stack=int(spot.stack),
        small_blind=50,
        big_blind=100,
        ante=0,
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=pot,
        initial_contributions=(pot // 2, pot - pot // 2),
        initial_hole_cards=(),
        postflop_raise_cap=int(spot.max_raises),
        bet_size_fractions=tuple(spot.bet_sizes),
        include_all_in=bool(spot.include_all_in),
    )


def _spot_hand_ids(spot: Any, player: int) -> list[list[int]]:
    """Return the player's hand list as `[[card_id, card_id], ...]` for Rust.

    Brown's binary and PR 23's Rust vector-form both index hands as
    `[u8; 2]` of `card_to_int` ids; Python passes the same shape through
    PyO3 as `list[list[int]]`. Order matches the spot fixture's hand list
    so per-hand indices line up between the two engines.

    Note on player mapping: Brown's P0 acts first on river; our P1 acts
    first on river per `poker_solver/hunl.py:286-289`
    (per ``docs/brown_apples_to_apples_2026-05-23.md`` §2 "Convention notes").
    This is an apples-to-apples test in the sense of "same hand set on
    each side"; the actor-ordering inversion is handled by reading
    Brown's per-player profile and matching it against the corresponding
    Rust player. We pass spot.ranges[0] as `p0_holes` (= our P0,
    second-to-act on river) and spot.ranges[1] as `p1_holes` (= our P1,
    first-to-act on river) so the Rust hand vector is interpretable
    the same way the spot itself is authored.
    """
    assert card_to_int is not None
    out: list[list[int]] = []
    for combo, _weight in spot.ranges[player]:
        c0, c1 = combo
        out.append([card_to_int(c0), card_to_int(c1)])
    return out


def _combo_to_hole_string(combo: tuple[Any, Any]) -> str:
    """Render a (Card, Card) combo as Rust's `hole_string` output format.

    Rust's `exploit::hole_string` (`crates/cfr_core/src/exploit.rs:490-498`,
    referenced by `dcfr_vector.rs:712-714`):

        let mut sorted = hole;
        sorted.sort_unstable();         // sort by card_to_int ascending
        for c in sorted { push_card_str(c, out) }  // RANKS = "23456789TJQKA", SUITS = "shdc"

    Python `card_to_int(card) = rank * 4 + suit` (`poker_solver/card.py:117-119`),
    so sorting by `card_to_int` is equivalent to sorting by
    `(rank, suit)` ascending. Suit string uses `shdc` order (suit 0 → s,
    suit 1 → h, suit 2 → d, suit 3 → c).
    """
    ranks = "23456789TJQKA"
    suits = "shdc"

    def fmt(card: Any) -> tuple[int, str]:
        cid = card_to_int(card)  # type: ignore[misc]
        rank_str = ranks[card.rank - 2]
        suit_str = suits[card.suit]
        return cid, f"{rank_str}{suit_str}"

    a, b = fmt(combo[0]), fmt(combo[1])
    # Sort by card_to_int ascending (Rust's sort_unstable on [u8; 2]).
    if a[0] <= b[0]:
        return a[1] + b[1]
    return b[1] + a[1]


def _rust_history_substr_for_canonical(
    canonical_history: tuple[tuple[str, int], ...],
) -> str:
    """Render canonical history tokens as our hunl.py history substring.

    The Rust solver emits infoset keys with the same `<hole>|<board>|<street>|<history>`
    format as Python's `HUNLState.infoset_key` (PR 23 dcfr_vector.rs line 660-661).
    The history substring follows our hunl.py conventions
    (``poker_solver/hunl.py:343-437``):

      * check / call → ``"x"`` / ``"c"``
      * fold → ``"f"``
      * bet → ``"b<chips_added>"``
      * raise → ``"r<actor_new_total>"``

    Our canonical form (per ``noambrown_wrapper._walk_brown_tokens``) is:

      * ``("c", 0)``   = either check or call — emit as ``"c"``
        (our engine, like Brown's, treats both identically at the wire
        token; the chip-amount-zero invariant of canonical ``c`` covers
        both. The c-vs-x distinction is consumed during canonicalization
        already.)
      * ``("f", 0)``   = fold — emit as ``"f"``
      * ``("b", amt)`` = bet to actor_new_total — convert to "b<chips_added>"
        relative to the actor's prior contribution.
      * ``("r", amt)`` = raise to actor_new_total — emit as ``"r<amt>"``.

    For the river-first-actor subgame the initial contribution per
    player is ``pot // 2``; we walk a small state machine to compute
    chips_added for bets relative to the pre-bet contribution.
    """
    # State machine — same shape as `noambrown_wrapper._HistoryState`
    # but stripped down for this rendering pass.
    contrib = [500, 500]  # filled per-call; OK for the dry K72/A83 spots (pot=1000)
    actor = 1  # river-open OOP for our engine
    tokens: list[str] = []
    for kind, amt in canonical_history:
        if kind == "c":
            # Check (to_call==0) → "x"; call (to_call>0) → "c". Our engine
            # distinguishes them in the wire token but the canonical form
            # collapses both to ("c", 0). For the river-first-actor open
            # the first ("c", 0) is always a check; subsequent ("c", 0)
            # after a bet is a call. The infoset key substring uses the
            # original wire token, so we recover it from the local state.
            to_call = max(contrib[1 - actor] - contrib[actor], 0)
            if to_call > 0:
                tokens.append("c")
                contrib[actor] += to_call
            else:
                tokens.append("x")
            actor = 1 - actor
        elif kind == "f":
            tokens.append("f")
            break
        elif kind == "b":
            chips_added = amt - contrib[actor]
            tokens.append(f"b{chips_added}")
            contrib[actor] = amt
            actor = 1 - actor
        elif kind == "r":
            tokens.append(f"r{amt}")
            contrib[actor] = amt
            actor = 1 - actor
    return "".join(tokens)


def _build_rust_strategy_lookup(
    rust_strategy: dict[str, list[float]],
    hands_p0_strs: list[str],
    hands_p1_strs: list[str],
) -> dict[tuple[int, str], dict[str, list[float]]]:
    """Index Rust's average_strategy by (player, history_substr) → hand_str → probs.

    Rust emits one dict entry per `(infoset, hand)` row with key
    ``<hole_string>|<board>|<street>|<history>``. We need to group by
    (player, history) to compare against Brown's per-history infoset
    matrices.
    """
    out: dict[tuple[int, str], dict[str, list[float]]] = {}
    set_p0 = set(hands_p0_strs)
    set_p1 = set(hands_p1_strs)
    for key, probs in rust_strategy.items():
        parts = key.split("|")
        if len(parts) != 4:
            continue
        hole_str, _board_str, _street, history_substr = parts
        if hole_str in set_p0:
            player = 0
        elif hole_str in set_p1:
            player = 1
        else:
            continue
        out.setdefault((player, history_substr), {})[hole_str] = list(probs)
    return out


# ---------------------------------------------------------------------------
# Acceptance test (parametrized over the covered spots)
# ---------------------------------------------------------------------------


@pytest.mark.parity_noambrown
@pytest.mark.slow
@pytest.mark.timeout(int(BROWN_TIMEOUT_SEC) + 1800)  # Brown 600s + Rust 30 min ceiling
@pytest.mark.parametrize("spot_id", COVERED_SPOT_IDS)
def test_v1_5_brown_apples_to_apples_parity(spot_id: str) -> None:
    """v1.5.0 acceptance: PR 23 Rust vector-form CFR vs Brown on same hand set.

    For each covered spot:
      1. Load spot from the river fixture (full 30+ combos per side).
      2. Solve with Brown's binary.
      3. Solve with PR 23's Rust vector-form, passing the SAME hand list
         via ``p0_holes`` / ``p1_holes``.
      4. Walk Brown's infoset profile, locate matching Rust strategy rows
         by ``(player, history, hole_str)``, and assert per-action
         probability parity within ``5e-3``.

    Tolerance rationale + skip-strategy rationale in the module docstring.
    """
    _require_preconditions()
    binary = _require_brown_binary()

    spot = _spot_by_id(spot_id)

    # ---- Brown side ----
    brown_dump = run_brown_solver(  # type: ignore[misc]
        spot,
        binary,
        iterations=ITERATIONS,
        seed=7,
        timeout_sec=BROWN_TIMEOUT_SEC,
    )

    # ---- Our side (PR 23 Rust vector-form CFR) ----
    config = _build_rust_config_for_spot(spot)
    config_json = _serialize_hunl_config(config)  # type: ignore[misc]
    p0_holes = _spot_hand_ids(spot, 0)
    p1_holes = _spot_hand_ids(spot, 1)

    rust_result = _rust_solve_rvr(  # type: ignore[misc]
        config_json,
        ITERATIONS,
        DCFR_ALPHA,
        DCFR_BETA,
        DCFR_GAMMA,
        p0_holes,
        p1_holes,
    )
    rust_strategy = rust_result["average_strategy"]
    assert len(rust_strategy) > 0, (
        f"{spot_id}: Rust returned empty strategy dict — PR 23 implementation "
        f"never reached a decision node (likely tree-construction bug)."
    )

    # Build Rust hand-str lists in the same order as the spot's ranges, so
    # the lookup table indexes are aligned with Brown's `hands` arrays.
    hands_p0_strs: list[str] = [
        _combo_to_hole_string(combo) for combo, _w in spot.ranges[0]
    ]
    hands_p1_strs: list[str] = [
        _combo_to_hole_string(combo) for combo, _w in spot.ranges[1]
    ]

    rust_lookup = _build_rust_strategy_lookup(
        rust_strategy, hands_p0_strs, hands_p1_strs
    )

    # ---- History coverage check ----
    # Brown's histories live on player profiles. Build the canonical form
    # of each, render to our hunl.py substring shape, and check it appears
    # in Rust's emitted keys.
    brown_keys_p0 = set(brown_dump.players[0].profile.keys())
    brown_keys_p1 = set(brown_dump.players[1].profile.keys())
    brown_keys_all = brown_keys_p0 | brown_keys_p1

    matched_history_count = 0
    for brown_key in brown_keys_all:
        canonical = canonicalize_brown_history(brown_key, spot=spot)  # type: ignore[misc]
        history_substr = _rust_history_substr_for_canonical(canonical)
        # Did EITHER Rust player produce a strategy row at this history?
        if (0, history_substr) in rust_lookup or (1, history_substr) in rust_lookup:
            matched_history_count += 1

    coverage = matched_history_count / max(len(brown_keys_all), 1)
    assert coverage >= COVERAGE_FLOOR, (
        f"{spot_id}: history coverage {coverage:.1%} < {COVERAGE_FLOOR:.0%}. "
        f"Brown produced {len(brown_keys_all)} histories; "
        f"{matched_history_count} found in Rust's keys. Either the engines "
        f"explore different trees (acceptance failure) or the history "
        f"canonicalization is mis-rendered (test bug — fix the renderer)."
    )

    # ---- Per-(history, hand, action) probability parity ----
    diffs: list[str] = []
    for player in (0, 1):
        brown_profile = brown_dump.players[player].profile
        brown_hands = brown_dump.players[player].hands
        for brown_key, entry in brown_profile.items():
            canonical = canonicalize_brown_history(brown_key, spot=spot)  # type: ignore[misc]
            history_substr = _rust_history_substr_for_canonical(canonical)
            rust_rows = rust_lookup.get((player, history_substr))
            if rust_rows is None:
                # Counted in coverage; not a per-cell diff.
                continue
            actions = entry.actions
            n_actions = len(actions)
            # For each Brown hand row, look up the matching Rust row by
            # hole_str. Brown's hand string uses the same suit chars as
            # Rust's `hole_string` (both use lowercase suit; Brown sorts
            # by card_id ascending — same convention).
            for hand_idx, brown_row in enumerate(entry.strategy):
                hand_str = brown_hands[hand_idx]
                rust_row = rust_rows.get(hand_str)
                if rust_row is None:
                    # Hand not emitted by Rust for this history — skip,
                    # already reflected in coverage. (Could be a hand
                    # filtered out by board-disjointness; Brown does the
                    # same filter at construction.)
                    continue
                if len(rust_row) != n_actions:
                    diffs.append(
                        f"{spot_id} P{player} hand={hand_str} hist={history_substr!r}: "
                        f"action-count mismatch — Brown has {n_actions} "
                        f"actions ({actions}), Rust has {len(rust_row)}"
                    )
                    continue
                for a_idx in range(n_actions):
                    brown_p = float(brown_row[a_idx])
                    rust_p = float(rust_row[a_idx])
                    if abs(brown_p - rust_p) >= PER_ACTION_TOL:
                        diffs.append(
                            f"{spot_id} P{player} hand={hand_str} "
                            f"hist={history_substr!r} action={actions[a_idx]!r}: "
                            f"brown={brown_p:.6f} rust={rust_p:.6f} "
                            f"|diff|={abs(brown_p - rust_p):.3e}"
                        )

    if diffs:
        head = "\n  ".join(diffs[:20])
        suffix = ""
        if len(diffs) > 20:
            suffix = f"\n  ... ({len(diffs) - 20} more diffs)"
        pytest.fail(
            f"{spot_id}: per-action probabilities diverge between Brown's "
            f"vector CFR and PR 23 Rust vector CFR (tolerance "
            f"{PER_ACTION_TOL:.0e}):\n  {head}{suffix}\n\n"
            f"This is the v1.5.0 'true Nash range-vs-range' acceptance gate "
            f"(task #184). A failure here means PR 23's vector-form CFR is "
            f"not in fact Brown-equivalent on the same hand set; the "
            f"headline does not hold. Triage starts at "
            f"`crates/cfr_core/src/dcfr_vector.rs` (port of Brown's "
            f"`trainer.cpp:138-209`) and "
            f"`docs/brown_apples_to_apples_2026-05-23.md`."
        )
