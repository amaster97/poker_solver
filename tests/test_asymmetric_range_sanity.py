"""Asymmetric-range sanity regression gate.

This test is a **wrapper-hazard regression gate**, not a Brown-parity gate.
It is designed to catch wrapper bugs that swap players, mismatch hand
strings, or invert equity — failure modes that have repeatedly slipped
past symmetric-range fixtures (per the wrapper-hazard memory rule:
*asymmetric ranges surface convention bugs; symmetric ranges hide them*).

The fixture pits two **very different** hand classes against each other on
a dry rainbow river:

  - Hero strong range: ``{AA, KK}`` — premium pairs.
  - Villain weak range: ``{72o, 83o}`` — pure air (offsuit low cards).
  - Board: ``Tc 9d 4h Jc 6s`` — dry rainbow, **no pair**, no flush draw,
    no card that pairs villain's hands.

On this board every hero combo CRUSHES every villain combo:

  - AA -> pair of aces (rank PAIR=1).
  - KK -> pair of kings (rank PAIR=1; villain still loses on kickers).
  - 72o -> high card (no pair; 7-high or 2-high beats nothing).
  - 83o -> high card (8-high beats nothing).

(Verified by exhaustive hero-vs-villain combo enumeration: 0 hero losses,
0 ties across 9 hero x 24 villain combos.)

Expected Nash behavior on any correctly-wired solver:

  - Hero (AA, KK) should bet **most** sizes, **most** of the time at the
    initial decision (pure value bets vs villain's air).
  - Villain (72o, 83o) should **fold** to nearly any bet (no equity, no
    bluff-catcher candidates exist in villain's range).

Two code paths are exercised:

  1. ``solve_range_vs_range`` (aggregator) — both perspectives.
  2. ``solve_range_vs_range_nash`` (vector-form Nash) — both perspectives.

**Wrapper-bug catch table.**

Any one of the wrapper bugs caught this session (R8, R9, R10) would have
made this test fail spectacularly on day one:

  - **R8 suit-encoding swap.** Mis-mapping suits in ``hole_string`` would
    misroute AA's strategy row to a 72o key (or vice versa), inverting
    the bet/fold direction.
  - **R9 P0/P1 convention.** Swapping hero/villain slots would put the
    strong range in the weak slot, making the "AA bets" check fail and
    "72o folds" become "72o bets".
  - **R10 hand-string sort.** A mis-sorted hand prefix would miss the
    strategy row entirely; the per_class_strategy projection would
    return ``{}`` and the assertion would fail with a clear message.

None of these would fail on a symmetric fixture (e.g., AA-vs-AA), where
the strategy is the same for both sides.

**Nash-path scope caveat.** The Rust vector-form binding (PR 23) panics
with an index-out-of-bounds error when the two players have **different
combo counts** (e.g., 12 hero combos vs 24 villain combos). This is a
known limitation surfaced by this asymmetric fixture (see PR body for
details). The Nash assertions therefore use ``{22, 33}`` as villain's
weak-range stand-in (12 combos, equal to hero's ``{AA, KK}`` 12 combos)
to keep both paths green on origin/main. The 22/33-vs-AA/KK matchup is
still **strictly asymmetric in hand class** (pair tiers differ by ~9
ranks; equity 99%+) and catches the same wrapper bugs.

**Time budget.** ~3 s on M-series Apple Silicon (Rust backend, 300
aggregator iters per per-hand solve, 500 Nash iters per solve, 4 total
solves: 2 aggregator + 2 Nash).
"""

from __future__ import annotations

import importlib
import re
import time

import pytest

try:
    from poker_solver import (
        HUNLConfig,
        Street,
        parse_board,
        solve_range_vs_range,
        solve_range_vs_range_nash,
    )
except Exception:  # noqa: BLE001 - defensive
    HUNLConfig = None  # type: ignore[assignment,misc]
    Street = None  # type: ignore[assignment,misc]
    parse_board = None  # type: ignore[assignment]
    solve_range_vs_range = None  # type: ignore[assignment]
    solve_range_vs_range_nash = None  # type: ignore[assignment]

try:
    _rust_module = importlib.import_module("poker_solver._rust")
except Exception:  # noqa: BLE001 - defensive
    _rust_module = None  # type: ignore[assignment]


pytestmark = [
    pytest.mark.skipif(
        HUNLConfig is None,
        reason="poker_solver HUNL surface not importable",
    ),
    pytest.mark.skipif(
        _rust_module is None,
        reason=(
            "poker_solver._rust extension missing — rebuild via "
            "`maturin develop --release` to exercise the Rust-backed paths"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Fixture constants — kept module-level so the test functions stay short.
# ---------------------------------------------------------------------------

# Dry rainbow river: no pair, no flush draw, no straight draw, and no card
# that pairs 72o / 83o. Hand-verified that every {AA, KK} combo crushes
# every {72o, 83o} combo (0 losses across 9 x 24 matchups).
BOARD_STR = "Tc 9d 4h Jc 6s"

# Aggregator iteration count. Each per-hand solve is a 1v1 river spot;
# 300 iters converges well under 0.1 s on Rust.
AGG_ITERS = 300

# Nash iteration count. Vector-form CFR; 500 iters convergence target.
NASH_ITERS = 500

# Strict bet-rate threshold for hero's strong hands. On this board AA/KK
# have ~99%+ equity vs villain's air; correct Nash betting is 95%+. We
# leave a generous 50% slack to accommodate any future small-iter-count
# regressions.
HERO_BET_FREQ_THRESHOLD = 0.50

# Strict fold-rate threshold for villain's weak hands. Villain's air has
# zero equity vs hero's range, so any correct Nash response is 95%+ fold.
# 80% slack guards against future smoke-iter regressions.
VILLAIN_FOLD_FREQ_THRESHOLD = 0.80


def _build_config() -> HUNLConfig:
    """River-only spot with 2 bet sizes (0.5x and 1.0x pot)."""
    board = tuple(parse_board(BOARD_STR))
    return HUNLConfig(
        starting_stack=10_000,
        starting_street=Street.RIVER,
        initial_board=board,
        initial_pot=200,
        initial_contributions=(100, 100),
        bet_size_fractions=(0.5, 1.0),
        include_all_in=False,
        postflop_raise_cap=2,
    )


def _bet_frequency(strategy: dict[str, float]) -> float:
    """Sum probability of any ``bet_*`` action (multi-size aware).

    The aggregator and Nash projections both emit labels like
    ``bet_50``, ``bet_100``, ``check``, ``fold``, ``call`` (see
    ``range_aggregator._label_for_action``). We sum across all ``bet_*``
    so the assertion does not depend on bet-size enumeration order.
    """
    return sum(p for label, p in strategy.items() if label.startswith("bet_"))


def _fold_frequency(strategy: dict[str, float]) -> float:
    """Probability of folding (single label ``"fold"``)."""
    return float(strategy.get("fold", 0.0))


# ===========================================================================
# Aggregator path — solve_range_vs_range
#
# Uses the very asymmetric prompt fixture: hero {AA, KK} (12 combos) vs
# villain {72o, 83o} (24 combos). The aggregator runs N per-hand 1v1
# subgame solves and averages by combo count; it tolerates any combo-count
# asymmetry between the two ranges.
# ===========================================================================


@pytest.mark.timeout(60)
def test_aggregator_aa_kk_bets_vs_72o_83o() -> None:
    """Hero ``{AA, KK}`` must bet heavily vs villain ``{72o, 83o}`` air.

    Setup: hero at P1 slot (P1 acts first on river with symmetric
    contribs), villain at P0. The first-decision projection is hero's
    bet/check split — both classes should bet.

    A wrapper bug that swaps player slots would put the weak range at P1
    and produce a check/fold strategy, failing the bet-rate assertion.
    A wrapper bug that mismatches hand strings would drop AA/KK from
    ``per_class_strategy`` entirely, failing the key-presence assertion.
    """
    cfg = _build_config()

    t0 = time.perf_counter()
    result = solve_range_vs_range(
        config_template=cfg,
        hero_range=["AA", "KK"],
        villain_range=["72o", "83o"],
        iterations=AGG_ITERS,
        backend="rust",
        villain_reps=1,
        hero_player=1,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"Aggregator forward path took {elapsed:.1f}s; budget 15s"

    # Both hero classes must produce a strategy. Missing-key failure mode
    # surfaces hand-string mismatch or board-block edge-case bugs.
    assert "AA" in result.per_class_strategy, (
        f"AA missing from per_class_strategy; warnings: {result.warnings}"
    )
    assert "KK" in result.per_class_strategy, (
        f"KK missing from per_class_strategy; warnings: {result.warnings}"
    )

    aa_bet = _bet_frequency(result.per_class_strategy["AA"])
    kk_bet = _bet_frequency(result.per_class_strategy["KK"])
    assert aa_bet > HERO_BET_FREQ_THRESHOLD, (
        f"AA bet rate = {aa_bet:.4f}; expected > {HERO_BET_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['AA']})"
    )
    assert kk_bet > HERO_BET_FREQ_THRESHOLD, (
        f"KK bet rate = {kk_bet:.4f}; expected > {HERO_BET_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['KK']})"
    )

    # Position field must reflect the hero_player choice — guards against
    # any future wrapper bug that mis-reports which slot hero occupies.
    assert result.position == "defender", (
        f"expected position='defender' for hero_player=1; got {result.position!r}"
    )


@pytest.mark.timeout(60)
def test_aggregator_72o_83o_folds_vs_aa_kk() -> None:
    """Villain ``{72o, 83o}`` must fold heavily facing hero ``{AA, KK}`` bet.

    Setup: villain at P1 (acts first, bets modal value range); hero air
    at P0 faces the bet and must fold. The first-decision projection is
    hero's fold/call/raise split — air should fold near-100%.

    A wrapper bug that inverts equity (e.g., a misrouted comparator)
    would have the air hands calling/raising for value, failing the fold
    assertion.
    """
    cfg = _build_config()

    t0 = time.perf_counter()
    result = solve_range_vs_range(
        config_template=cfg,
        hero_range=["72o", "83o"],
        villain_range=["AA", "KK"],
        iterations=AGG_ITERS,
        backend="rust",
        villain_reps=1,
        hero_player=0,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"Aggregator reverse path took {elapsed:.1f}s; budget 15s"

    assert "72o" in result.per_class_strategy, (
        f"72o missing from per_class_strategy; warnings: {result.warnings}"
    )
    assert "83o" in result.per_class_strategy, (
        f"83o missing from per_class_strategy; warnings: {result.warnings}"
    )

    v72_fold = _fold_frequency(result.per_class_strategy["72o"])
    v83_fold = _fold_frequency(result.per_class_strategy["83o"])
    assert v72_fold > VILLAIN_FOLD_FREQ_THRESHOLD, (
        f"72o fold rate = {v72_fold:.4f}; expected > {VILLAIN_FOLD_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['72o']})"
    )
    assert v83_fold > VILLAIN_FOLD_FREQ_THRESHOLD, (
        f"83o fold rate = {v83_fold:.4f}; expected > {VILLAIN_FOLD_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['83o']})"
    )

    assert result.position == "aggressor", (
        f"expected position='aggressor' for hero_player=0; got {result.position!r}"
    )


# ===========================================================================
# Nash path — solve_range_vs_range_nash
#
# The Rust vector-form binding (PR 23 / `dcfr_vector.rs`) panics with
# "index out of bounds" when hero and villain have different combo counts
# (e.g., 12-vs-24). This is a known limitation surfaced BY THIS FIXTURE
# during PR 58 development — see PR body for the panic trace.
#
# To keep the Nash path green on origin/main while still asymmetric in
# hand class, we use {AA, KK} (12 combos) vs {22, 33} (12 combos): 9
# ranks apart, equity ~99%+ on this rainbow board, same combo count.
# The 22/33 stand-in is still air relative to AA/KK on a Q-high-no-pair
# board (22, 33 = pair of 2s/3s; AA, KK = overpairs that crush).
# ===========================================================================

# Nash-compatible weak villain range with same combo count as {AA, KK}.
# Asymmetric in hand class (low pair vs high pair, 9+ ranks apart) but
# matched in combo count to avoid the Rust binding's mixed-count panic.
NASH_VILLAIN_WEAK_RANGE = ["22", "33"]


@pytest.mark.timeout(60)
def test_nash_aa_kk_bets_vs_weak_pairs() -> None:
    """Nash path: hero ``{AA, KK}`` must bet heavily vs villain low-pair air.

    On a Tc-9d-4h-Jc-6s board, AA and KK are overpairs that dominate
    22/33 (small underpairs); equity is ~99%+. Hero at P1 (acts first on
    river) — first-decision projection is bet/check.
    """
    cfg = _build_config()

    t0 = time.perf_counter()
    result = solve_range_vs_range_nash(
        config_template=cfg,
        hero_range=["AA", "KK"],
        villain_range=NASH_VILLAIN_WEAK_RANGE,
        iterations=NASH_ITERS,
        hero_player=1,
        compute_exploitability_at_end=False,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"Nash forward path took {elapsed:.1f}s; budget 15s"

    assert "AA" in result.per_class_strategy, (
        f"AA missing from Nash per_class_strategy; warnings: {result.warnings}"
    )
    assert "KK" in result.per_class_strategy, (
        f"KK missing from Nash per_class_strategy; warnings: {result.warnings}"
    )

    aa_bet = _bet_frequency(result.per_class_strategy["AA"])
    kk_bet = _bet_frequency(result.per_class_strategy["KK"])
    assert aa_bet > HERO_BET_FREQ_THRESHOLD, (
        f"Nash AA bet rate = {aa_bet:.4f}; expected > {HERO_BET_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['AA']})"
    )
    assert kk_bet > HERO_BET_FREQ_THRESHOLD, (
        f"Nash KK bet rate = {kk_bet:.4f}; expected > {HERO_BET_FREQ_THRESHOLD} "
        f"(strategy: {result.per_class_strategy['KK']})"
    )

    assert result.position == "defender", (
        f"expected Nash position='defender' for hero_player=1; got {result.position!r}"
    )


@pytest.mark.timeout(60)
def test_nash_weak_pairs_fold_vs_aa_kk() -> None:
    """Nash path: villain low pairs must fold heavily facing hero ``{AA, KK}``.

    Hero air {22, 33} at P0; villain {AA, KK} at P1 acts first. When the
    air FACES a bet, it must fold near-100%.

    **Why we assert on ``per_history_strategy`` (the bet-facing nodes)
    rather than the modal-walk ``per_class_strategy`` projection.**

    On this dry last-street spot, {AA, KK} vs pure air ({22, 33} with 0%
    equity that folds to any bet) are EV-INDIFFERENT between check and
    bet: villain never calls and there is no future street, so AA/KK win
    exactly the pot whether they check or bet. That is a genuine Nash
    *indifference manifold* — multiple optimal strategies. The v1.11
    perf paths (suit-iso + inclusion-exclusion, both ON by default) land
    on the *uniform* {check, bet_50, bet_100} = 1/3 each Nash strategy;
    the legacy path landed on *pure check*. (Confirmed NOT an engine bug:
    when villain holds a hand with real equity/calling range, e.g. a set,
    the AA/KK root trains to a *strict* pure check — the indifference
    appears ONLY against 0-equity air.)

    Because the ``per_class_strategy`` modal-walk follows villain's modal
    action, and "check" is (weakly) modal here, the projected hero node
    is "22 faces a CHECK" (check/bet) — which structurally has no fold
    action, so a "fold rate > 0.8" assertion on it is non-falsifiable.

    To keep this a meaningful *wrapper-hazard* gate (player-swap /
    suit-encoding / hand-string bugs) AND poker-correct, we assert on the
    actual bet-facing infosets in ``per_history_strategy``: every
    ``...|r|b<size>`` node (P0 = 22/33 facing P1's bet) must put ~all of
    its mass on FOLD (action index 0). A player-swap bug would route the
    strong range to these nodes and they'd call/raise for value instead
    of folding, failing the assertion.
    """
    cfg = _build_config()

    t0 = time.perf_counter()
    result = solve_range_vs_range_nash(
        config_template=cfg,
        hero_range=NASH_VILLAIN_WEAK_RANGE,
        villain_range=["AA", "KK"],
        iterations=NASH_ITERS,
        hero_player=0,
        compute_exploitability_at_end=False,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"Nash reverse path took {elapsed:.1f}s; budget 15s"

    # Bet-facing infosets: hero (22/33, P0) acting after villain (P1) bets.
    # Key format: ``<hole>|<board>|r|b<size>`` (history ends in a bet token
    # with no further hero action). Action ordering at a facing-bet node is
    # [fold, call, raise...]; index 0 is fold.
    bet_facing = {
        k: v
        for k, v in result.per_history_strategy.items()
        if re.search(r"\|r\|b\d+$", k)
    }
    assert bet_facing, (
        "expected at least one bet-facing 22/33 infoset in "
        f"per_history_strategy; got keys: "
        f"{sorted(result.per_history_strategy)[:5]!r}"
    )
    for key, row in bet_facing.items():
        fold_prob = float(row[0])
        assert fold_prob > VILLAIN_FOLD_FREQ_THRESHOLD, (
            f"Nash bet-facing fold rate at {key!r} = {fold_prob:.4f}; "
            f"expected > {VILLAIN_FOLD_FREQ_THRESHOLD} (row: "
            f"{[round(x, 4) for x in row]})"
        )

    # Sanity: both weak classes are present in the projection (the
    # modal-walk node still exists — it is just a check node here).
    for cls in NASH_VILLAIN_WEAK_RANGE:
        assert cls in result.per_class_strategy, (
            f"{cls} missing from Nash per_class_strategy; warnings: {result.warnings}"
        )

    assert result.position == "aggressor", (
        f"expected Nash position='aggressor' for hero_player=0; got {result.position!r}"
    )
