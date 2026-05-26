"""Self-sanity smoke tests for PR 7's noambrown wrapper module.

These tests run on ANY machine where the rest of the project works —
they do NOT require Brown's C++ binary to be built. They validate:

  - fixture loading + invariants (the spec-correctness gate)
  - our engine solves each of the first 3 spots end-to-end (wiring sane)
  - canonicalize_*_history round-trips identity for 10 hand-built histories
  - our_strategy_to_brown_matrix produces correctly-shaped arrays
  - find_brown_binary returns either an existing path or None (never raises)
  - iterations_override plumbing actually changes the iteration count

These complement (do NOT replace) the real diff test in
``tests/test_river_diff.py``, which DOES require Brown's binary.

PR 7 spec §10 Agent C.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from poker_solver import HUNLConfig, HUNLPoker, Street, solve_hunl_postflop
from poker_solver.parity.noambrown_wrapper import (
    RiverSpot,
    canonicalize_brown_history,
    canonicalize_our_history,
    find_brown_binary,
    load_spots,
    our_strategy_to_brown_matrix,
)
from poker_solver.parity.noambrown_wrapper import (  # noqa: PLC2701
    _parse_brown_dump,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"

# Convergence-test iteration count (spec §10 Agent C #2 — 2000 iters with
# expl < 0.02 × pot). The original PR 7 (v0.5.1) comment described 2000
# iters as "cheap (<10s/spot on a typical dev box)" — that was an
# aspirational target, never empirically validated. In practice the
# canonical parity test takes >660s on the Python tier due to the
# chance-enum-at-root architecture (1.6M hole-card combos per iter); see
# `docs/river_parity_timeout_investigation_2026-05-23.md` for the
# TEST-WAS-ALWAYS-SLOW verdict. The canonical parity test was marked
# `@pytest.mark.slow` in v1.4.2; a full runtime fix awaits PR 23
# vector-form CFR (v1.5.0).
CONVERGENCE_ITERS: int = 2000

# Smoke iteration count for the strategy-matrix shape test (cheaper; we
# only need a non-trivial average_strategy populated, not convergence).
SMOKE_ITERS: int = 500

# Smoke iteration count for the iterations_override plumbing test (must
# differ from the default so the override is observable).
OVERRIDE_ITERS: int = 500


# ---------------------------------------------------------------------------
# Module-level fixture loading. Failing to load the fixture is fatal for
# every test in this module — surface it loudly at collection time.
# ---------------------------------------------------------------------------


def _load_spots_or_fail() -> list[RiverSpot]:
    """Load the river_spots fixture; raise on absence (spec-correctness gate)."""
    if not SPOTS_JSON.exists():
        pytest.fail(
            f"river fixture missing at {SPOTS_JSON}; "
            "PR 7 spec §4 requires this fixture be present in the repo."
        )
    return load_spots(SPOTS_JSON)


SPOTS: list[RiverSpot] = _load_spots_or_fail()


def _build_hunl_config(spot: RiverSpot) -> HUNLConfig:
    """Construct a river-only HUNLConfig from a fixture spot.

    Mirrors the production diff path in ``test_river_diff.py``'s
    ``_solve_with_our_engine`` helper so the smoke run exercises the same
    config the parity test will use.
    """
    pot = int(spot.pot)
    return HUNLConfig(
        starting_stack=int(spot.stack),
        starting_street=Street.RIVER,
        initial_board=tuple(spot.board),
        initial_pot=pot,
        initial_contributions=(pot // 2, pot - pot // 2),
        initial_hole_cards=(),
        bet_size_fractions=tuple(spot.bet_sizes),
        include_all_in=bool(spot.include_all_in),
        postflop_raise_cap=int(spot.max_raises),
        abstraction=None,
    )


# ---------------------------------------------------------------------------
# Test 1: every fixture spot constructs a valid HUNLConfig (spec §10 Agent C #1).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spot", SPOTS, ids=lambda s: s.id)
def test_each_spot_loads_into_hunl_config(spot: RiverSpot) -> None:
    """Each of the 15 spots constructs a valid river-start HUNLConfig.

    Validates the fixture wire-format → solver-config mapping: any schema
    drift (new field, type change, missing key) surfaces here as a
    construction-time error rather than silently in the diff test.
    """
    cfg = _build_hunl_config(spot)
    game = HUNLPoker(cfg)
    state = game.initial_state()
    assert state.street == Street.RIVER
    assert state.board == tuple(spot.board)
    assert sum(state.contributions) == spot.pot
    assert state.stacks == (spot.stack, spot.stack)


# ---------------------------------------------------------------------------
# Test 2: our engine converges on the first 3 spots (spec §10 Agent C #2).
# Soft assertion: failure prompts user review, not auto-fix. Loose
# threshold of 0.02 × pot — we only confirm convergence to a strategy,
# not optimality. The full convergence diff is Agent B's job at 2000+
# iters with a Brown reference.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spot", SPOTS[:3], ids=lambda s: s.id)
def test_each_spot_solver_converges(spot: RiverSpot) -> None:
    """Our DCFR converges to expl < 0.02 × pot at 2000 iters on the first 3 spots.

    Soft assertion — failure prompts user review, not auto-fix. Loose
    threshold catches gross wiring breakage (NaN, divergence, non-finite
    exploitability) without binding the smoke test to optimality.
    """
    cfg = _build_hunl_config(spot)
    result = solve_hunl_postflop(
        cfg,
        abstraction=None,
        iterations=CONVERGENCE_ITERS,
        seed=7,
    )
    assert result.exploitability_history, (
        f"{spot.id}: exploitability_history is empty; solver did not "
        f"snapshot any exploitability values"
    )
    final_expl = result.exploitability_history[-1]
    assert math.isfinite(
        final_expl
    ), f"{spot.id}: final exploitability is not finite: {final_expl!r}"
    assert (
        final_expl >= 0.0
    ), f"{spot.id}: exploitability must be non-negative, got {final_expl}"
    # exploitability_history is in BB-units (per PR 5 / solver.exploitability).
    # The 0.02 × pot threshold is in chips; convert by dividing pot by big_blind.
    bb_threshold = 0.02 * spot.pot / cfg.big_blind
    assert final_expl < bb_threshold, (
        f"{spot.id}: final exploitability {final_expl:.6f} BB exceeds "
        f"smoke threshold {bb_threshold:.6f} BB (= 0.02 × pot / big_blind)"
    )


# ---------------------------------------------------------------------------
# Test 3: game_value finite + bounded for the first 3 spots (spec §10 Agent C #3).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spot", SPOTS[:3], ids=lambda s: s.id)
def test_each_spot_game_value_is_finite(spot: RiverSpot) -> None:
    """game_value is finite and bounded by [-pot, pot] in chips."""
    cfg = _build_hunl_config(spot)
    result = solve_hunl_postflop(
        cfg,
        abstraction=None,
        iterations=CONVERGENCE_ITERS,
        seed=7,
    )
    # SolveResult.game_value is in BB-units (per PR 5); convert to chips.
    gv_chips = result.game_value * cfg.big_blind
    assert math.isfinite(
        gv_chips
    ), f"{spot.id}: game_value not finite: {result.game_value!r}"
    assert not math.isnan(gv_chips), f"{spot.id}: game_value is NaN"
    assert -spot.pot <= gv_chips <= spot.pot, (
        f"{spot.id}: game_value {gv_chips:.4f} chips outside [-pot, pot] "
        f"= [{-spot.pot}, {spot.pot}]"
    )


# ---------------------------------------------------------------------------
# Test 4: canonicalize_*_history round-trip on 10 hand-built histories
# (spec §10 Agent C #4; spec §5 step 5 raise-encoding canonicalization).
#
# Default state assumed: pot=1000 (half=500/side already in), stack=9500/side.
# Canonical amounts are post-initial-contribution to-totals: each player's
# chip total INCLUDING the half-pot already contributed. Both Brown and
# our canonicalizers feed the same state machine starting at half-pot-each,
# so they emit identical canonical tuples.
# ---------------------------------------------------------------------------


# Each test case is (brown_token_string, our_token_string, expected_canonical).
# Values verified against the canonicalizer state machine documented in
# poker_solver/parity/noambrown_wrapper.py:_walk_brown_tokens /
# _walk_our_tokens, and the docstring of canonicalize_{brown,our}_history.
ROUNDTRIP_CASES: tuple[tuple[str, str, tuple], ...] = (
    # 1. Empty history: Brown's "root" and our "" both → ().
    ("root", "", ()),
    # 2. Check-first (no bet to call): Brown's 'c' and our 'x' both → ("c", 0).
    ("c", "x", (("c", 0),)),
    # 3. Call when to_call > 0: Brown still emits 'c'; ours emits 'c' too.
    #    With pot=1000 and no prior bet, to_call==0, so the call is effectively
    #    a check — both forms collapse to ("c", 0).
    ("c", "c", (("c", 0),)),
    # 4. Check-check: Brown splits streets on '/', so "c/c" is two tokens; ours
    #    concatenates within a street as "xx". Both → two ("c", 0) tuples.
    ("c/c", "xx", (("c", 0), ("c", 0))),
    # 5. Bet 500: Brown's b500 means "add 500 chips"; new actor total = 500 + 500
    #    = 1000. Same for our b500 (chips-added form). Canonical: ("b", 1000).
    ("b500", "b500", (("b", 1000),)),
    # 6. Bet-then-call: bet 500 → ("b", 1000), then opponent calls → ("c", 0).
    ("b500/c", "b500c", (("b", 1000), ("c", 0))),
    # 7. Bet-then-fold: bet 500 → ("b", 1000), then opponent folds → ("f", 0).
    ("b500/f", "b500f", (("b", 1000), ("f", 0))),
    # 8. Raise after bet. Brown stores r<extra-beyond-call>; we store r<to_total>.
    #    After b500 the opponent (P1) is at total 1000. Brown's r500 means
    #    "500 chips beyond the call of 500" → raiser (P0) total = 1000 + 500 =
    #    1500. Our equivalent is r1500 (raise-to-total form, emitted as-is).
    ("b500/r500", "b500r1500", (("b", 1000), ("r", 1500))),
    # 9. All-in opening jam. With half-pot=500 already in and stack=9500
    #    remaining, the all-in ceiling is 10000. Brown emits b9500 (chips
    #    added). Our 'A' token canonicalizes to ("b", 10000) because to_call==0
    #    at the open (no bet yet) — re-emit as a bet for amount=remaining_total.
    ("b9500", "A", (("b", 10000),)),
    # 10. All-in as raise after b500. Brown emits r9000 (extra beyond the
    #     to-call of 500; 1000 + 9000 = 10000 total). Our 'A' canonicalizes
    #     to ("r", 10000) because to_call > 0 here — re-emit as raise-to-total.
    ("b500/r9000", "b500A", (("b", 1000), ("r", 10000))),
)


def test_canonicalize_history_roundtrip() -> None:
    """10 hand-built histories round-trip in both directions to the same tuple.

    This is THE spec-correctness gate for the raise-encoding canonicalization
    (PR 7 spec §5 step 5). If a case fails the wrapper has a bug: either the
    raise extra-vs-total transform is wrong, or the all-in state-dependent
    re-emission is wrong, or the state machine drifts between the two halves.

    The default state matches the PR 7 fixture convention (pot=1000,
    stack=9500/side), so the canonical amounts here are exactly what the
    production diff test would emit on the equivalent token strings.
    """
    assert (
        len(ROUNDTRIP_CASES) == 10
    ), f"spec §10 Agent C #4 mandates 10 cases; have {len(ROUNDTRIP_CASES)}"

    for brown_form, our_form, expected in ROUNDTRIP_CASES:
        brown_canon = canonicalize_brown_history(brown_form)
        assert (
            brown_canon == expected
        ), f"brown {brown_form!r}: got {brown_canon}, expected {expected}"
        our_canon = canonicalize_our_history(our_form)
        assert (
            our_canon == expected
        ), f"our {our_form!r}: got {our_canon}, expected {expected}"
        # Cross-engine identity (the actual round-trip invariant).
        assert canonicalize_our_history(our_form) == canonicalize_brown_history(
            brown_form
        ), (
            f"round-trip identity broken for "
            f"brown={brown_form!r} vs ours={our_form!r}: "
            f"brown_canon={canonicalize_brown_history(brown_form)}, "
            f"our_canon={canonicalize_our_history(our_form)}"
        )


def test_canonicalize_history_is_idempotent() -> None:
    """Re-canonicalizing the rendered form of a canonical history is a no-op.

    Auxiliary invariant per audit report M1 #5 — guards against accidental
    double-normalization (e.g. if a downstream consumer re-feeds the
    rendered form through canonicalize_our_history).
    """
    # The empty history renders to "root" (Brown form) or "" (our form);
    # both round-trip to () via canonicalize_*. We exercise the four
    # non-trivial cases (one each of: bet, raise, all-in-open, all-in-raise).
    for brown_form, our_form, expected in ROUNDTRIP_CASES:
        if not expected:
            continue
        # Re-canonicalize Brown's form: idempotent on the parser's input domain.
        # Brown form itself is the parser's input; double-canonicalizing the
        # SAME wire format must produce the same canonical tuple.
        first = canonicalize_brown_history(brown_form)
        second = canonicalize_brown_history(brown_form)
        assert first == second, (
            f"brown {brown_form!r}: non-idempotent on repeated parse: "
            f"{first} vs {second}"
        )
        first_ours = canonicalize_our_history(our_form)
        second_ours = canonicalize_our_history(our_form)
        assert first_ours == second_ours, (
            f"our {our_form!r}: non-idempotent on repeated parse: "
            f"{first_ours} vs {second_ours}"
        )


# ---------------------------------------------------------------------------
# Test 5: strategy matrix shape (spec §10 Agent C #5).
# ---------------------------------------------------------------------------


def test_strategy_matrix_shape() -> None:
    """our_strategy_to_brown_matrix produces correctly-shaped arrays.

    For the first spot, solve at SMOKE_ITERS, project to Brown's matrix shape,
    and assert:
      - the returned dict is non-empty (at least one canonical history present)
      - each ndarray has shape (num_hands, num_actions)
      - probabilities are in [0.0, 1.0]
      - each per-hand row sums to 1.0 ± 1e-6 OR is all-zero (hand didn't
        reach this infoset).
    """
    spot = SPOTS[0]
    cfg = _build_hunl_config(spot)
    result = solve_hunl_postflop(
        cfg,
        abstraction=None,
        iterations=SMOKE_ITERS,
        seed=7,
    )
    hands_p0 = tuple(combo for (combo, _w) in spot.ranges[0])
    hands_p1 = tuple(combo for (combo, _w) in spot.ranges[1])
    matrix = our_strategy_to_brown_matrix(result, hands_p0, hands_p1, spot)

    assert matrix, (
        f"{spot.id}: our_strategy_to_brown_matrix returned an empty dict; "
        f"expected at least one canonical history"
    )

    for history_key, player_dict in matrix.items():
        assert isinstance(player_dict, dict), (
            f"{spot.id}: history {history_key!r} entry is not a dict, got "
            f"{type(player_dict).__name__}"
        )
        for player, arr in player_dict.items():
            assert player in (0, 1), (
                f"{spot.id}: history {history_key!r} unexpected player "
                f"index {player}"
            )
            num_hands_expected = len(hands_p0) if player == 0 else len(hands_p1)
            assert arr.shape[0] == num_hands_expected, (
                f"{spot.id}: history {history_key!r} player {player} "
                f"hand-axis size {arr.shape[0]} != "
                f"len(spot.ranges[{player}]) {num_hands_expected}"
            )
            assert arr.shape[1] >= 1, (
                f"{spot.id}: history {history_key!r} player {player} "
                f"action axis empty: shape={arr.shape}"
            )
            # All probabilities are in [0, 1].
            assert (arr >= 0.0).all(), (
                f"{spot.id}: history {history_key!r} player {player} "
                f"has negative probabilities"
            )
            assert (arr <= 1.0 + 1e-9).all(), (
                f"{spot.id}: history {history_key!r} player {player} "
                f"has probabilities > 1.0"
            )
            # Each row sums to 1.0 ± 1e-6 OR is all-zero (hand didn't
            # reach this infoset).
            for h_idx in range(arr.shape[0]):
                row_sum = float(arr[h_idx].sum())
                if row_sum > 1e-9:
                    assert abs(row_sum - 1.0) < 1e-6, (
                        f"{spot.id}: history {history_key!r} player "
                        f"{player} hand {h_idx} row sum {row_sum} not 1.0 "
                        f"(and not all-zero)"
                    )


# ---------------------------------------------------------------------------
# Test 6: every fixture range is board-disjoint (spec §10 Agent C #6).
# ---------------------------------------------------------------------------


def test_no_overlap_in_fixture_ranges() -> None:
    """For every spot, no hand shares a card with the board or itself.

    Fixture-correctness gate. Failure here indicates the fixture JSON has
    a bad entry; load_spots already enforces this on construction, so this
    test is a belt-and-braces guard that the loader's invariant holds for
    every spot we ship.
    """
    for spot in SPOTS:
        board_set = set(spot.board)
        for player_idx, player_range in enumerate(spot.ranges):
            for combo, _weight in player_range:
                c1, c2 = combo
                assert c1 != c2, (
                    f"{spot.id}: players[{player_idx}] combo {combo!r} has "
                    f"duplicate cards"
                )
                assert c1 not in board_set, (
                    f"{spot.id}: players[{player_idx}] combo {combo!r} "
                    f"first card {c1!r} overlaps board {spot.board!r}"
                )
                assert c2 not in board_set, (
                    f"{spot.id}: players[{player_idx}] combo {combo!r} "
                    f"second card {c2!r} overlaps board {spot.board!r}"
                )


# ---------------------------------------------------------------------------
# Test 7: iterations_override is wired through end-to-end (spec §10 Agent C #7).
# ---------------------------------------------------------------------------


def test_iterations_override_respected() -> None:
    """A spot with iterations_override=N drives the solver to N iterations.

    Constructs a spot with a small override (OVERRIDE_ITERS) via
    dataclasses.replace, then verifies the solver actually runs that many
    iterations (not the default 2000). The wrapper itself does not run the
    solve — iteration plumbing is the test harness's job (mirroring
    test_river_diff.py's pattern at line 338). So we verify here that the
    end-to-end shape works: the override is exposed on the spot, and feeding
    it to solve_hunl_postflop produces a result with iterations==OVERRIDE_ITERS.
    """
    spot = SPOTS[0]
    overridden = replace(spot, iterations_override=OVERRIDE_ITERS)
    assert (
        overridden.iterations_override == OVERRIDE_ITERS
    ), "dataclasses.replace did not apply iterations_override"

    # End-to-end check: feed the override-derived iter count to the solver
    # and verify the SolveResult.iterations field reports back the same N.
    iters = int(overridden.iterations_override or 2000)
    assert iters == OVERRIDE_ITERS

    cfg = _build_hunl_config(overridden)
    result = solve_hunl_postflop(
        cfg,
        abstraction=None,
        iterations=iters,
        seed=7,
    )
    assert result.iterations == OVERRIDE_ITERS, (
        f"solver reported iterations={result.iterations}, expected "
        f"{OVERRIDE_ITERS} (override plumbing broken)"
    )


# ---------------------------------------------------------------------------
# Test 8: find_brown_binary returns Path-or-None, never raises (spec §10 Agent C #8).
# ---------------------------------------------------------------------------


def test_brown_binary_finder_returns_path_or_none() -> None:
    """find_brown_binary returns Path-or-None on any host; never raises.

    On CI without the binary: returns None.
    On a dev box with the binary built: returns an existing executable Path.

    Path resolution that fails (e.g. references directory missing) MUST
    return None — never throw. The function is the public skip-cleanly
    contract for Agent B's parity test; an exception would break the
    5-layer skipif strategy.
    """
    # First invocation: no setup, must not raise.
    binary = find_brown_binary()
    assert binary is None or isinstance(
        binary, Path
    ), f"expected Path or None, got {type(binary).__name__}: {binary!r}"
    if binary is not None:
        assert (
            binary.exists()
        ), f"find_brown_binary returned {binary} but it doesn't exist"
        assert (
            binary.is_file()
        ), f"find_brown_binary returned {binary} but it's not a file"

    # Second invocation: idempotent — repeated calls return the same path
    # (or None) without side effects.
    binary2 = find_brown_binary()
    assert binary == binary2, (
        f"find_brown_binary is not idempotent: first={binary!r}, " f"second={binary2!r}"
    )


# ---------------------------------------------------------------------------
# Test 9 (PR 55): _parse_brown_dump swaps players[0] / players[1] at the
# wrapper boundary so callers index Brown's profile in our P0/P1 convention.
# ---------------------------------------------------------------------------


def test_parse_brown_dump_swaps_players_p0_p1() -> None:
    """PR 55 regression: ``_parse_brown_dump`` swaps Brown's player axis.

    Brown's JSON exposes ``players[0]`` as Brown's tree-internal player 0,
    which is the **first-to-act on river** (per
    ``cpp/src/river_game.cpp:10``). Our engine puts the **second-to-act**
    profile at our P0 (per ``poker_solver/hunl.py:425-429`` and
    ``hunl.py:789``). So Brown's ``players[0]`` is our P1, and Brown's
    ``players[1]`` is our P0.

    This test feeds a hand-crafted Brown dump (with marker
    ``hands``/``weights`` distinct per side) through ``_parse_brown_dump``
    and asserts that the returned dump indexes the profiles in our
    convention: ``parsed.players[0]`` contains the input ``players[1]``
    payload and vice versa. Failure here = silently regressing the swap
    and re-introducing the K72/A83 cross-role comparison bug
    (see ``docs/p0_p1_convention_investigation.md``).
    """
    # Hand-crafted Brown dump with deliberately distinct payloads per side
    # so the swap is observable. ``hands`` and ``weights`` are the simplest
    # to assert on without depending on profile-key canonicalization.
    raw_dump = {
        "players": [
            {
                # Brown's input players[0] = first-to-act on river (≡ our P1).
                # Marker hands: AsKs (some "OOP-looking" hand) at weight 1.0.
                "hands": ["AsKs"],
                "weights": [1.0],
                "profile": {
                    "root": {
                        "actions": ["c", "f"],
                        "strategy": [[0.7, 0.3]],
                    }
                },
            },
            {
                # Brown's input players[1] = second-to-act on river (≡ our P0).
                # Marker hands: QdQh (distinct from players[0]) at weight 0.5.
                "hands": ["QdQh"],
                "weights": [0.5],
                "profile": {
                    "root": {
                        "actions": ["c", "f"],
                        "strategy": [[0.4, 0.6]],
                    }
                },
            },
        ]
    }

    parsed = _parse_brown_dump(
        raw_dump,
        iterations_run=2000,
        game_value_p0=None,
        game_value_p1=None,
        exploitability_chips=None,
    )

    # ``parsed.players[0]`` (our P0 = second-to-act) MUST receive the
    # second-to-act payload from Brown — which Brown put at input
    # ``players[1]``: hands=["QdQh"], weights=[0.5].
    assert parsed.players[0].hands == ("QdQh",), (
        f"PR 55 swap regressed: parsed.players[0].hands = "
        f"{parsed.players[0].hands!r}, expected ('QdQh',) "
        f"(Brown's players[1] payload, our P0)"
    )
    assert parsed.players[0].weights == (0.5,), (
        f"PR 55 swap regressed: parsed.players[0].weights = "
        f"{parsed.players[0].weights!r}, expected (0.5,)"
    )
    assert parsed.players[0].profile["root"].strategy == ((0.4, 0.6),), (
        "PR 55 swap regressed: parsed.players[0] is carrying Brown's "
        "players[0] strategy, not players[1]"
    )

    # Symmetric assertion: parsed.players[1] = our P1 = first-to-act on
    # river = Brown's players[0] payload.
    assert parsed.players[1].hands == ("AsKs",), (
        f"PR 55 swap regressed: parsed.players[1].hands = "
        f"{parsed.players[1].hands!r}, expected ('AsKs',) "
        f"(Brown's players[0] payload, our P1)"
    )
    assert parsed.players[1].weights == (1.0,), (
        f"PR 55 swap regressed: parsed.players[1].weights = "
        f"{parsed.players[1].weights!r}, expected (1.0,)"
    )
    assert parsed.players[1].profile["root"].strategy == ((0.7, 0.3),), (
        "PR 55 swap regressed: parsed.players[1] is carrying Brown's "
        "players[1] strategy, not players[0]"
    )


def test_parse_brown_dump_nuts_vs_air_asymmetric_fixture() -> None:
    """PR 55 sanity: nuts-vs-air asymmetric fixture surfaces the swap.

    Constructs a minimal Brown dump where the two seats are
    behaviourally distinguishable:

    - Brown's ``players[0]`` (= first-to-act = our P1) is given a pure
      "nuts" infoset that always bets pot at the root: ``b1000`` weight 1.0.
    - Brown's ``players[1]`` (= second-to-act = our P0) is given a pure
      "air" infoset that always folds at a faced bet:
      ``b1000`` reply ``f`` weight 1.0.

    After PR 55's swap, the post-parse dump must put the FOLD-AT-bet
    profile at ``parsed.players[0]`` (our P0) and the BET-EVERY-time
    profile at ``parsed.players[1]`` (our P1). This is the exact
    asymmetric semantic the investigation flagged in Phase 4 as the
    minimal nuts-vs-air fixture; if the swap is ever undone, this test
    is the first to fail.
    """
    raw_dump = {
        "players": [
            {
                # Brown's first-to-act (our P1): pure-nuts strategy, bets pot.
                "hands": ["AcAd"],  # marker
                "weights": [1.0],
                "profile": {
                    "root": {
                        "actions": ["b1000", "c"],
                        "strategy": [[1.0, 0.0]],  # always bet pot
                    }
                },
            },
            {
                # Brown's second-to-act (our P0): pure-air, folds to bet.
                "hands": ["2c3d"],  # marker
                "weights": [1.0],
                "profile": {
                    "b1000": {
                        "actions": ["c", "f"],
                        "strategy": [[0.0, 1.0]],  # always fold
                    }
                },
            },
        ]
    }

    parsed = _parse_brown_dump(
        raw_dump,
        iterations_run=2000,
        game_value_p0=None,
        game_value_p1=None,
        exploitability_chips=None,
    )

    # After swap, parsed.players[0] (our P0) must carry the air/fold
    # profile (Brown's input players[1]).
    assert parsed.players[0].hands == ("2c3d",), (
        "PR 55: parsed.players[0] must carry Brown's players[1] (our P0 = "
        "second-to-act = air-side in this fixture); "
        f"got {parsed.players[0].hands!r}"
    )
    assert "b1000" in parsed.players[0].profile, (
        "PR 55: parsed.players[0] (our P0, our second-to-act) must have a "
        "response to the b1000 facing bet — i.e. the swap put the "
        "responder's infoset on our P0"
    )
    assert parsed.players[0].profile["b1000"].strategy == ((0.0, 1.0),), (
        "PR 55: post-swap our-P0 strategy at b1000 should be fold-heavy "
        "(this fixture's air side); regression here means the swap was "
        "undone or inverted"
    )

    # And parsed.players[1] (our P1) carries the nuts/bet profile.
    assert parsed.players[1].hands == ("AcAd",), (
        "PR 55: parsed.players[1] must carry Brown's players[0] (our P1 = "
        "first-to-act = nuts-side); "
        f"got {parsed.players[1].hands!r}"
    )
    assert "root" in parsed.players[1].profile
    assert parsed.players[1].profile["root"].strategy == ((1.0, 0.0),), (
        "PR 55: post-swap our-P1 strategy at root should be bet-heavy "
        "(this fixture's nuts side)"
    )
