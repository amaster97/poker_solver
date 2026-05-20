import random

import pytest

from poker_solver.card import parse_board, parse_hand
from poker_solver.equity import equity
from poker_solver.range import parse_range


def test_equity_sums_to_one_two_hands():
    hands = [parse_hand("AhKh"), parse_hand("QdQc")]
    rng = random.Random(42)
    results = equity(hands, iterations=2000, rng=rng)
    total = sum(r.equity for r in results)
    assert abs(total - 1.0) < 1e-9


def test_aa_beats_kk_heads_up():
    # AA vs KK preflop — should be around 81% / 19%
    hands = [parse_hand("AhAd"), parse_hand("KsKc")]
    rng = random.Random(123)
    results = equity(hands, iterations=4000, rng=rng)
    aa_equity = results[0].equity
    assert aa_equity > 0.75
    assert aa_equity < 0.90


def test_set_over_set_dominates_on_locked_board():
    # AsAh vs 7s7h on board As 7c 2d 9s Jh — AAA full of 7s beats 777 full of A's
    # Actually, with 2 hole cards locked + 5 board locked = 7 known cards each.
    # AA has AAA77 (full house aces full of sevens), 77 has 777AA (sevens full of aces). AA wins.
    hands = [parse_hand("AsAh"), parse_hand("7s7h")]
    board = parse_board("Ac7c2d9sJh")
    results = equity(hands, board=board, iterations=200)
    assert results[0].equity == 1.0
    assert results[1].equity == 0.0


def test_full_board_no_randomness():
    # When the full board is known, the result should be deterministic.
    hands = [parse_hand("AsKs"), parse_hand("2c2d")]
    board = parse_board("Ah Kh Qc 5d 3s")
    rng = random.Random(1)
    r1 = equity(hands, board=board, iterations=100, rng=rng)
    r2 = equity(hands, board=board, iterations=50, rng=random.Random(99))
    assert r1[0].equity == r2[0].equity == 1.0  # two pair AK beats pocket twos
    assert r1[1].equity == r2[1].equity == 0.0


def test_tie_split_pot():
    # Both players have identical hole-card values modulo suit on a board that
    # makes the same straight: board 9 8 7 6 5 (a straight on the board itself).
    # The board itself plays as a 9-high straight for both, no kicker matters.
    hands = [parse_hand("2c3d"), parse_hand("2h3s")]
    board = parse_board("9h8d7c6s5h")
    results = equity(hands, board=board, iterations=100)
    # Tied — both should get 0.5 equity
    assert results[0].equity == pytest.approx(0.5)
    assert results[1].equity == pytest.approx(0.5)
    assert results[0].tie == results[0].iterations


def test_range_vs_hand():
    # Big pair range vs a smaller pair
    big_pairs = parse_range("AA,KK,QQ")
    hands = [big_pairs, parse_hand("7s7h")]
    rng = random.Random(7)
    results = equity(hands, iterations=2000, rng=rng)
    # Range of overpairs should crush 77 — pretty close to 80%
    assert results[0].equity > 0.70


def test_seed_reproducibility():
    hands = [parse_hand("AhKh"), parse_hand("QdQc")]
    r1 = equity(hands, iterations=500, rng=random.Random(42))
    r2 = equity(hands, iterations=500, rng=random.Random(42))
    assert r1[0].equity == r2[0].equity
    assert r1[1].equity == r2[1].equity


def test_rejects_single_hand():
    with pytest.raises(ValueError):
        equity([parse_hand("AhKh")], iterations=10)
