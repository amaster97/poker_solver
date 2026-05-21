from poker_solver.card import parse_card as p
from poker_solver.evaluator import HandRank, evaluate


def cards(*s):
    return [p(x) for x in s]


def test_high_card():
    r = evaluate(cards("Ah", "Kd", "9c", "7s", "2h"))
    assert r[0] == HandRank.HIGH_CARD
    assert r[1:] == (14, 13, 9, 7, 2)


def test_pair():
    r = evaluate(cards("Ah", "Ad", "Kc", "9s", "2h"))
    assert r[0] == HandRank.PAIR
    assert r[1] == 14
    assert r[2:] == (13, 9, 2)


def test_two_pair():
    r = evaluate(cards("Ah", "Ad", "Kc", "Ks", "9h"))
    assert r[0] == HandRank.TWO_PAIR
    assert r[1:] == (14, 13, 9)


def test_three_of_a_kind():
    r = evaluate(cards("Ah", "Ad", "Ac", "Ks", "9h"))
    assert r[0] == HandRank.THREE_OF_A_KIND
    assert r[1] == 14
    assert r[2:] == (13, 9)


def test_straight():
    r = evaluate(cards("9h", "8d", "7c", "6s", "5h"))
    assert r[0] == HandRank.STRAIGHT
    assert r[1] == 9


def test_wheel_straight():
    r = evaluate(cards("5h", "4d", "3c", "2s", "Ah"))
    assert r[0] == HandRank.STRAIGHT
    assert r[1] == 5


def test_broadway_straight():
    r = evaluate(cards("Th", "Jd", "Qc", "Ks", "Ah"))
    assert r[0] == HandRank.STRAIGHT
    assert r[1] == 14


def test_flush():
    r = evaluate(cards("Ah", "Kh", "Jh", "8h", "4h"))
    assert r[0] == HandRank.FLUSH
    assert r[1:] == (14, 13, 11, 8, 4)


def test_full_house():
    r = evaluate(cards("Ah", "Ad", "Ac", "Ks", "Kh"))
    assert r[0] == HandRank.FULL_HOUSE
    assert r[1:] == (14, 13)


def test_full_house_two_trips_uses_lower_as_pair():
    # Aces full of kings — both trips, top pair is the lower triple
    r = evaluate(cards("Ah", "Ad", "Ac", "Ks", "Kh", "Kd", "2c"))
    assert r[0] == HandRank.FULL_HOUSE
    assert r[1:] == (14, 13)


def test_four_of_a_kind():
    r = evaluate(cards("Ah", "Ad", "Ac", "As", "Kh"))
    assert r[0] == HandRank.FOUR_OF_A_KIND
    assert r[1:] == (14, 13)


def test_straight_flush():
    r = evaluate(cards("9h", "8h", "7h", "6h", "5h"))
    assert r[0] == HandRank.STRAIGHT_FLUSH
    assert r[1] == 9


def test_royal_flush():
    r = evaluate(cards("Th", "Jh", "Qh", "Kh", "Ah"))
    assert r[0] == HandRank.STRAIGHT_FLUSH
    assert r[1] == 14


def test_wheel_straight_flush():
    r = evaluate(cards("5h", "4h", "3h", "2h", "Ah"))
    assert r[0] == HandRank.STRAIGHT_FLUSH
    assert r[1] == 5


def test_seven_card_best_five_is_chosen():
    # Best from 7: full house (aces full of kings) beats flush in hearts
    r = evaluate(cards("Ah", "Ad", "Ac", "Kh", "Kd", "2h", "5h"))
    assert r[0] == HandRank.FULL_HOUSE


def test_flush_beats_straight():
    # Both available; flush should win
    r = evaluate(cards("9h", "8h", "7h", "6h", "2h", "5d", "4c"))
    assert r[0] == HandRank.FLUSH


def test_straight_does_not_wrap_around():
    # QKA23 should NOT be a straight
    r = evaluate(cards("Qd", "Kh", "Ac", "2s", "3h", "7c", "8d"))
    assert r[0] != HandRank.STRAIGHT


def test_comparisons_total_ordering():
    high_card = evaluate(cards("Ah", "Kd", "9c", "7s", "2h"))
    pair = evaluate(cards("2h", "2d", "5c", "7s", "9h"))
    flush = evaluate(cards("Ah", "Kh", "Jh", "8h", "4h"))
    assert pair > high_card
    assert flush > pair


def test_kicker_breaks_ties():
    # Pair of aces, K kicker beats Q kicker
    a = evaluate(cards("Ah", "Ad", "Kc", "9s", "2h"))
    b = evaluate(cards("Ah", "Ad", "Qc", "9s", "2h"))
    assert a > b
