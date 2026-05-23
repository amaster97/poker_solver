//! HUNL hand evaluator (5- and 7-card).
//!
//! Adapted from `poker_solver/evaluator.py` (project-internal, MIT) for
//! semantics. `Strength` type and ranking pattern adapted by name from
//! `references/code/noambrown_poker_solver/cpp/src/cards.{h,cpp}` (MIT);
//! 7-card algorithmic-eval pattern referenced from
//! `references/code/slumbot2019/src/hand_value_tree.cpp` (MIT) — but the
//! actual algorithm here is a direct port of Python's category + tiebreaker
//! tuple encoding, not slumbot's lookup table (deferred to PR 8).
//!
//! NEVER copy from `references/code/postflop-solver` (AGPL) or
//! `references/code/TexasSolver` (AGPL).
//!
//! Encoding details (matches Python's `evaluator.evaluate`):
//! - Cards are `u8` in `card_to_int` form (`rank * 4 + suit`, range [8, 59]);
//!   `rank = c >> 2` (or `c / 4`) in 2..=14, `suit = c & 3` in 0..=3.
//! - `Strength` is a 64-bit value where the high byte holds the category
//!   (0..=8 mirroring Python's `HandRank`) and successive 4-bit nibbles hold
//!   the tiebreaker ranks (high → low). This preserves Python's tuple
//!   ordering under `<`/`>` comparisons because lex-compare of (category,
//!   tb1, tb2, …) with ranks in 2..=14 fits cleanly in 4 bits each. Equal
//!   `Strength` values mean equal hands (showdown ties).

/// Best-five-of-N hand strength. Higher is stronger; equal means tied.
///
/// Internal encoding: a 64-bit value structured as
/// `[ category(8) | tb1(4) | tb2(4) | tb3(4) | tb4(4) | tb5(4) | 0(28) ]`.
/// We pack into 64 bits because some tiebreaker chains can run 5 deep
/// (high-card, flush) and we want lex-comparison-equivalence with Python's
/// `(category, *tiebreakers)` tuple under `<`/`>`. The trailing 28 bits stay
/// zero so equality is still bit-identical.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd, Hash)]
pub struct Strength(pub u64);

/// Hand-rank categories — must match `poker_solver/evaluator.HandRank`
/// integer values byte-for-byte (Python's `IntEnum`).
#[allow(dead_code)]
const HAND_HIGH_CARD: u64 = 0;
const HAND_PAIR: u64 = 1;
const HAND_TWO_PAIR: u64 = 2;
const HAND_THREE_OF_A_KIND: u64 = 3;
const HAND_STRAIGHT: u64 = 4;
const HAND_FLUSH: u64 = 5;
const HAND_FULL_HOUSE: u64 = 6;
const HAND_FOUR_OF_A_KIND: u64 = 7;
const HAND_STRAIGHT_FLUSH: u64 = 8;

/// Pack `(category, tb1..=tb5)` into a `Strength` value.
///
/// Tiebreakers must be in 0..=14 (rank values); unused slots pass 0. The
/// high byte holds the category; each tiebreaker takes 4 bits, ordered
/// high → low so lex-compare matches Python tuple compare.
fn pack(category: u64, tb1: u64, tb2: u64, tb3: u64, tb4: u64, tb5: u64) -> Strength {
    let v = (category << 56) | (tb1 << 52) | (tb2 << 48) | (tb3 << 44) | (tb4 << 40) | (tb5 << 36);
    Strength(v)
}

#[inline]
fn rank_of(card: u8) -> u8 {
    card >> 2
}

#[inline]
fn suit_of(card: u8) -> u8 {
    card & 3
}

/// Return the high card of the best straight, or 0 if none. Mirrors
/// `_straight_high(unique_ranks_desc)` in `poker_solver/evaluator.py`.
fn straight_high(unique_ranks_desc: &[u8]) -> u8 {
    if unique_ranks_desc.is_empty() {
        return 0;
    }
    // Wheel handling: if Ace (14) is present, append Ace-low (1).
    let mut ranks: Vec<i32> = unique_ranks_desc.iter().map(|&r| r as i32).collect();
    if ranks[0] == 14 {
        ranks.push(1);
    }
    if ranks.len() < 5 {
        return 0;
    }
    for i in 0..(ranks.len() - 4) {
        if ranks[i] - ranks[i + 4] == 4 {
            return ranks[i] as u8;
        }
    }
    0
}

/// Evaluate the best-five-of-N hand. `cards` must have len >= 5.
fn evaluate_n(cards: &[u8]) -> Strength {
    assert!(
        cards.len() >= 5,
        "evaluate_n needs at least 5 cards, got {}",
        cards.len()
    );

    // ranks_desc: sorted descending, with duplicates (matches Python's
    // `sorted((c.rank for c in cards), reverse=True)`).
    let mut ranks_desc: Vec<u8> = cards.iter().map(|&c| rank_of(c)).collect();
    ranks_desc.sort_by(|a, b| b.cmp(a));

    // rank_counts: count of each rank
    let mut rank_counts: [u8; 15] = [0; 15];
    for &r in &ranks_desc {
        rank_counts[r as usize] += 1;
    }

    // suit_counts: count of each suit
    let mut suit_counts: [u8; 4] = [0; 4];
    for &c in cards {
        suit_counts[suit_of(c) as usize] += 1;
    }

    // Straight flush check: find flush suit (>=5 of one suit), then test
    // for a straight within that suit's ranks.
    let flush_suit: Option<u8> = suit_counts
        .iter()
        .enumerate()
        .find(|&(_, &n)| n >= 5)
        .map(|(s, _)| s as u8);

    if let Some(fs) = flush_suit {
        let mut flush_ranks_desc: Vec<u8> = cards
            .iter()
            .filter(|&&c| suit_of(c) == fs)
            .map(|&c| rank_of(c))
            .collect();
        flush_ranks_desc.sort_by(|a, b| b.cmp(a));
        let sf_high = straight_high(&flush_ranks_desc);
        if sf_high > 0 {
            return pack(HAND_STRAIGHT_FLUSH, sf_high as u64, 0, 0, 0, 0);
        }
    }

    // Grouped (count desc, rank desc) — Python's `sorted(rank_counts.items(),
    // key=lambda x: (-x[1], -x[0]))`. Build a list of (count, rank) pairs.
    let mut grouped: Vec<(u8, u8)> = Vec::with_capacity(13);
    for rank in (2..=14u8).rev() {
        let cnt = rank_counts[rank as usize];
        if cnt > 0 {
            grouped.push((cnt, rank));
        }
    }
    // Sort by (count desc, rank desc). Since `rank` already iterates high→low,
    // a stable sort by count desc preserves the high-rank-first order within
    // equal counts.
    grouped.sort_by_key(|b| std::cmp::Reverse(b.0));

    // Four of a kind
    if grouped[0].0 == 4 {
        let quad = grouped[0].1;
        // Kicker = highest rank != quad
        let kicker = ranks_desc.iter().copied().find(|&r| r != quad).unwrap_or(0);
        return pack(HAND_FOUR_OF_A_KIND, quad as u64, kicker as u64, 0, 0, 0);
    }

    // Full house — trips + (pair or another trip)
    if grouped[0].0 == 3 {
        for &(cnt, r) in &grouped[1..] {
            if cnt >= 2 {
                let trips = grouped[0].1;
                return pack(HAND_FULL_HOUSE, trips as u64, r as u64, 0, 0, 0);
            }
        }
    }

    // Flush (no straight flush already handled)
    if let Some(fs) = flush_suit {
        let mut top5: Vec<u8> = cards
            .iter()
            .filter(|&&c| suit_of(c) == fs)
            .map(|&c| rank_of(c))
            .collect();
        top5.sort_by(|a, b| b.cmp(a));
        top5.truncate(5);
        return pack(
            HAND_FLUSH,
            top5[0] as u64,
            top5[1] as u64,
            top5[2] as u64,
            top5[3] as u64,
            top5[4] as u64,
        );
    }

    // Straight — use unique ranks descending
    let mut unique_desc: Vec<u8> = Vec::with_capacity(13);
    for rank in (2..=14u8).rev() {
        if rank_counts[rank as usize] > 0 {
            unique_desc.push(rank);
        }
    }
    let s_high = straight_high(&unique_desc);
    if s_high > 0 {
        return pack(HAND_STRAIGHT, s_high as u64, 0, 0, 0, 0);
    }

    // Three of a kind
    if grouped[0].0 == 3 {
        let trips = grouped[0].1;
        let mut kickers: Vec<u8> = ranks_desc.iter().copied().filter(|&r| r != trips).collect();
        kickers.truncate(2);
        let k0 = *kickers.first().unwrap_or(&0);
        let k1 = *kickers.get(1).unwrap_or(&0);
        return pack(
            HAND_THREE_OF_A_KIND,
            trips as u64,
            k0 as u64,
            k1 as u64,
            0,
            0,
        );
    }

    // Two pair
    if grouped[0].0 == 2 && grouped.len() >= 2 && grouped[1].0 == 2 {
        let p1 = grouped[0].1;
        let p2 = grouped[1].1;
        let kicker = ranks_desc
            .iter()
            .copied()
            .find(|&r| r != p1 && r != p2)
            .unwrap_or(0);
        return pack(HAND_TWO_PAIR, p1 as u64, p2 as u64, kicker as u64, 0, 0);
    }

    // One pair
    if grouped[0].0 == 2 {
        let pair = grouped[0].1;
        let mut kickers: Vec<u8> = ranks_desc.iter().copied().filter(|&r| r != pair).collect();
        kickers.truncate(3);
        let k0 = *kickers.first().unwrap_or(&0);
        let k1 = *kickers.get(1).unwrap_or(&0);
        let k2 = *kickers.get(2).unwrap_or(&0);
        return pack(HAND_PAIR, pair as u64, k0 as u64, k1 as u64, k2 as u64, 0);
    }

    // High card — top 5 ranks descending
    let top5: Vec<u8> = ranks_desc.iter().take(5).copied().collect();
    pack(
        HAND_HIGH_CARD,
        *top5.first().unwrap_or(&0) as u64,
        *top5.get(1).unwrap_or(&0) as u64,
        *top5.get(2).unwrap_or(&0) as u64,
        *top5.get(3).unwrap_or(&0) as u64,
        *top5.get(4).unwrap_or(&0) as u64,
    )
}

impl Strength {
    /// Best-five-of-five hand rank. Matches `poker_solver/evaluator.evaluate`.
    pub fn evaluate_5(cards: &[u8; 5]) -> Strength {
        evaluate_n(cards)
    }

    /// Best-five-of-seven hand rank. Matches Python's same `evaluate` entry
    /// (which accepts >=5 cards and selects the best 5 internally via the
    /// category-tuple comparison logic).
    pub fn evaluate_7(cards: &[u8; 7]) -> Strength {
        evaluate_n(cards)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helpers: build a u8 card from (rank, suit). Suits per Python's SUITS:
    // 's'=0, 'h'=1, 'd'=2, 'c'=3. Ranks: 2..=14.
    const fn c(rank: u8, suit: u8) -> u8 {
        rank * 4 + suit
    }

    #[test]
    fn royal_flush_beats_quads() {
        // Royal flush in spades: A K Q J T of spades
        let rf = [c(14, 0), c(13, 0), c(12, 0), c(11, 0), c(10, 0)];
        // Quad aces with king kicker
        let quads = [c(14, 1), c(14, 2), c(14, 3), c(13, 1), c(2, 0)];
        assert!(Strength::evaluate_5(&rf) > Strength::evaluate_5(&quads));
    }

    #[test]
    fn wheel_straight_is_lowest_straight() {
        // A 2 3 4 5 (wheel)
        let wheel = [c(14, 0), c(2, 1), c(3, 2), c(4, 3), c(5, 0)];
        // 2 3 4 5 6
        let six_low = [c(6, 1), c(2, 2), c(3, 3), c(4, 0), c(5, 1)];
        let s1 = Strength::evaluate_5(&wheel);
        let s2 = Strength::evaluate_5(&six_low);
        assert!(
            s1 < s2,
            "wheel ({s1:?}) should rank below 6-high straight ({s2:?})"
        );
    }

    #[test]
    fn flush_beats_straight() {
        // 9-high flush
        let flush = [c(9, 0), c(7, 0), c(5, 0), c(3, 0), c(2, 0)];
        // 9-high straight
        let straight = [c(9, 0), c(8, 1), c(7, 2), c(6, 3), c(5, 0)];
        assert!(Strength::evaluate_5(&flush) > Strength::evaluate_5(&straight));
    }

    #[test]
    fn full_house_beats_flush() {
        // Aces full of kings
        let fh = [c(14, 0), c(14, 1), c(14, 2), c(13, 0), c(13, 1)];
        // A-high flush
        let flush = [c(14, 0), c(11, 0), c(8, 0), c(5, 0), c(2, 0)];
        assert!(Strength::evaluate_5(&fh) > Strength::evaluate_5(&flush));
    }

    #[test]
    fn pair_kickers_compare_correctly() {
        // Pair of 8s, AKQ kickers
        let h1 = [c(8, 0), c(8, 1), c(14, 0), c(13, 0), c(12, 0)];
        // Pair of 8s, AKJ kickers — h1 should win
        let h2 = [c(8, 2), c(8, 3), c(14, 1), c(13, 1), c(11, 0)];
        assert!(Strength::evaluate_5(&h1) > Strength::evaluate_5(&h2));
    }

    #[test]
    fn identical_hands_tie() {
        let h1 = [c(14, 0), c(13, 0), c(12, 0), c(11, 0), c(10, 0)];
        // Same hand in a different suit
        let h2 = [c(14, 1), c(13, 1), c(12, 1), c(11, 1), c(10, 1)];
        assert_eq!(Strength::evaluate_5(&h1), Strength::evaluate_5(&h2));
    }

    #[test]
    fn seven_card_picks_best_five() {
        // Five-card flush in the seven, plus two off-suit garbage.
        let seven = [
            c(14, 0),
            c(11, 0),
            c(8, 0),
            c(5, 0),
            c(2, 0), // A-high flush
            c(7, 1),
            c(6, 2), // ignored
        ];
        let five = [c(14, 0), c(11, 0), c(8, 0), c(5, 0), c(2, 0)];
        assert_eq!(Strength::evaluate_7(&seven), Strength::evaluate_5(&five));
    }

    #[test]
    fn two_pair_kicker_breaks_tie() {
        // Two pair AA 88 with K kicker
        let h1 = [c(14, 0), c(14, 1), c(8, 0), c(8, 1), c(13, 0)];
        // Two pair AA 88 with Q kicker
        let h2 = [c(14, 2), c(14, 3), c(8, 2), c(8, 3), c(12, 0)];
        assert!(Strength::evaluate_5(&h1) > Strength::evaluate_5(&h2));
    }

    #[test]
    fn category_ordering() {
        // Build one sample of each category and confirm strict ordering.
        let high_card = Strength::evaluate_5(&[c(14, 0), c(11, 1), c(8, 2), c(5, 3), c(2, 0)]);
        let pair = Strength::evaluate_5(&[c(8, 0), c(8, 1), c(14, 0), c(11, 1), c(2, 0)]);
        let two_pair = Strength::evaluate_5(&[c(8, 0), c(8, 1), c(5, 0), c(5, 1), c(14, 0)]);
        let trips = Strength::evaluate_5(&[c(8, 0), c(8, 1), c(8, 2), c(14, 0), c(2, 1)]);
        let straight = Strength::evaluate_5(&[c(9, 0), c(8, 1), c(7, 2), c(6, 3), c(5, 0)]);
        let flush = Strength::evaluate_5(&[c(14, 0), c(11, 0), c(8, 0), c(5, 0), c(2, 0)]);
        let full_house = Strength::evaluate_5(&[c(14, 0), c(14, 1), c(14, 2), c(13, 0), c(13, 1)]);
        let quads = Strength::evaluate_5(&[c(14, 0), c(14, 1), c(14, 2), c(14, 3), c(13, 0)]);
        let straight_flush = Strength::evaluate_5(&[c(9, 0), c(8, 0), c(7, 0), c(6, 0), c(5, 0)]);

        assert!(high_card < pair);
        assert!(pair < two_pair);
        assert!(two_pair < trips);
        assert!(trips < straight);
        assert!(straight < flush);
        assert!(flush < full_house);
        assert!(full_house < quads);
        assert!(quads < straight_flush);
    }
}
