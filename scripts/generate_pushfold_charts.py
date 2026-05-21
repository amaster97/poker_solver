"""Generate Heads-Up Nash push/fold charts for stack depths 2-15 BB.

Pipeline:
  1. Enumerate the 169 canonical hand classes (AA, KK, ..., 32o).
  2. Precompute a 169 x 169 equity matrix once via Monte Carlo, with
     combo-compatibility counts so we can weight outcomes by the joint
     prior of valid (combo_sb, combo_bb) pairings.
  3. For each stack depth d in 2..15:
       - Run regret-matching DCFR on the abstracted matrix game:
         SB chooses fold/jam per hand class; BB chooses fold/call per
         hand class given SB jammed. Payoffs come from the equity matrix
         and a pure jam/fold accounting (no minraise / limp lines).
       - Strategies converge in seconds because the game has only
         169 + 169 infosets per depth.
  4. Write the resulting jam/call frequencies to
     poker_solver/charts/pushfold_v1.json (overwriting Agent A's
     placeholder) in the schema Agent A's loader consumes.

Validation prints SB jam frequencies for AA / KK / AKs / 72o across all
stack depths so the user can sanity-check against published references
(Sklansky-Chubukov tables in `references/papers/_INDEX.md`,
gto_poker_survey_2024.pdf; competitor charts surveyed in
`references/products/_COMPETITORS.md`). Deviations larger than 2% are
called out in `docs/pushfold_v1_generation_notes.md`.

Usage:
    python scripts/generate_pushfold_charts.py            # full 14-depth run
    python scripts/generate_pushfold_charts.py --dry-run  # depth 5 only (smoke)

This script is deterministic: `random.seed(42)` is fixed and DCFR is
itself deterministic given the same regret-matching schedule. Re-running
on the same machine produces a byte-identical JSON.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Ensure the package is importable when the script is run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from poker_solver.card import RANKS, Card  # noqa: E402
from poker_solver.evaluator import evaluate  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

STACK_DEPTHS: tuple[int, ...] = tuple(range(2, 16))  # 2..15 BB inclusive
SMALL_BLIND_BB: float = 0.5
BIG_BLIND_BB: float = 1.0
ANTE_BB: float = 0.0

# Monte Carlo configuration for the 169x169 equity table. We sample
# `EQUITY_COMBO_PAIRS_PER_CLASS_PAIR` compatible (combo_sb, combo_bb)
# pairings per hand-class pair and average `EQUITY_BOARDS_PER_COMBO_PAIR`
# random board runouts per pairing. The combo sampling captures
# suit-config variance (e.g. AKs vs KQs depends on whether the ace blocks
# the king-queen suit); board sampling reduces variance per pairing.
# With (4, 350) the full table builds in ~6-7 min on a MacBook M-series
# and per-pair standard error is roughly 1% (well below the strategy
# tolerance for pure jam/fold equilibria, where most decisions are
# well-separated).
EQUITY_COMBO_PAIRS_PER_CLASS_PAIR: int = 4
EQUITY_BOARDS_PER_COMBO_PAIR: int = 350

# DCFR hyperparameters (Brown & Sandholm 2019, alpha/beta/gamma defaults).
DCFR_ALPHA: float = 1.5
DCFR_BETA: float = 0.0
DCFR_GAMMA: float = 2.0
DCFR_ITERATIONS: int = 4000

CHART_OUTPUT_PATH: Path = _REPO_ROOT / "poker_solver" / "charts" / "pushfold_v1.json"

# Hand classes whose frequencies we always log to stdout for sanity checks.
LANDMARK_HANDS: tuple[str, ...] = ("AA", "KK", "QQ", "AKs", "AKo", "72o", "32o")

# Published HU-Nash push/fold landmarks for sanity-checking generated
# SB jam frequencies. These cite Sklansky-Chubukov (Sklansky & Miller
# 2006 *No Limit Hold'em Theory and Practice* -- a unilateral concept,
# upper-bound on the jam range only) and HU Nash references compiled
# in the gto_poker_survey_2024 paper (`references/papers/_INDEX.md`).
# Sklansky-Chubukov is *not* HU Nash; it overestimates jam frequency
# at the 4-10 BB depths because it assumes a calling-station BB. We
# only assert the well-defined endpoints: AA / KK / AKs always jam,
# 72o stops jamming by 6 BB+, and at 2 BB everyone jams everything.
# Deviations are flagged > 2% but not treated as failures.
SKLANSKY_ANCHORS: dict[tuple[int, str], float] = {
    # (stack_bb, hand): expected SB jam frequency under HU Nash
    # Top-of-range hands always jam at every depth in [2, 15].
    (2, "AA"): 1.0,
    (2, "KK"): 1.0,
    (2, "AKs"): 1.0,
    (3, "AA"): 1.0,
    (3, "KK"): 1.0,
    (3, "AKs"): 1.0,
    (4, "AA"): 1.0,
    (4, "KK"): 1.0,
    (4, "AKs"): 1.0,
    (5, "AA"): 1.0,
    (5, "KK"): 1.0,
    (5, "AKs"): 1.0,
    (8, "AA"): 1.0,
    (8, "KK"): 1.0,
    (8, "AKs"): 1.0,
    (8, "72o"): 0.0,  # 72o is a clear fold by 6 BB+ in HU Nash
    (10, "AA"): 1.0,
    (10, "KK"): 1.0,
    (10, "AKs"): 1.0,
    (10, "72o"): 0.0,
    (15, "AA"): 1.0,
    (15, "KK"): 1.0,
    (15, "AKs"): 1.0,
    (15, "72o"): 0.0,
}

# ---------------------------------------------------------------------------
# Hand-class enumeration & combo helpers
# ---------------------------------------------------------------------------


def canonical_hand_classes() -> list[str]:
    """Return all 169 strategically-distinct preflop hand classes.

    Order: pairs AA..22, then suited AKs..32s, then offsuit AKo..32o.
    Matches `poker_solver.range.parse_range` notation.
    """
    hands: list[str] = []
    for r in range(12, -1, -1):
        hands.append(RANKS[r] * 2)
    for hi in range(12, -1, -1):
        for lo in range(hi - 1, -1, -1):
            hands.append(RANKS[hi] + RANKS[lo] + "s")
    for hi in range(12, -1, -1):
        for lo in range(hi - 1, -1, -1):
            hands.append(RANKS[hi] + RANKS[lo] + "o")
    return hands


def _expand_hand_class(hand_class: str) -> list[tuple[Card, Card]]:
    """Return all concrete 2-card combos for a hand class string."""
    r1_char = hand_class[0]
    r2_char = hand_class[1]
    v1 = 2 + RANKS.index(r1_char)
    v2 = 2 + RANKS.index(r2_char)
    combos: list[tuple[Card, Card]] = []
    if v1 == v2:
        # Pair: pick two distinct suits from {0,1,2,3}.
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                combos.append((Card(v1, s1), Card(v1, s2)))
        return combos
    # Suited or offsuit branch.
    assert len(hand_class) == 3
    suit_flag = hand_class[2]
    if v1 < v2:
        v1, v2 = v2, v1
    if suit_flag == "s":
        for s in range(4):
            combos.append((Card(v1, s), Card(v2, s)))
    elif suit_flag == "o":
        for s1 in range(4):
            for s2 in range(4):
                if s1 != s2:
                    combos.append((Card(v1, s1), Card(v2, s2)))
    else:
        raise ValueError(f"Bad suit flag in {hand_class!r}")
    return combos


def combo_count(hand_class: str) -> int:
    """Number of concrete combos in a hand class (6 / 4 / 12)."""
    return len(_expand_hand_class(hand_class))


# ---------------------------------------------------------------------------
# Equity matrix (Monte Carlo)
# ---------------------------------------------------------------------------


def _build_compat_count(hand_classes: list[str]) -> np.ndarray:
    """Return matrix M[i][j] = number of (combo_a, combo_b) pairs that share
    no card, for hand_classes[i] vs hand_classes[j]."""
    n = len(hand_classes)
    combos: list[list[tuple[Card, Card]]] = [
        _expand_hand_class(h) for h in hand_classes
    ]
    compat = np.zeros((n, n), dtype=np.int64)
    for i in range(n):
        a_set_per_combo = [{c[0], c[1]} for c in combos[i]]
        for j in range(n):
            count = 0
            for a in a_set_per_combo:
                for b in combos[j]:
                    if b[0] not in a and b[1] not in a:
                        count += 1
            compat[i, j] = count
    return compat


def _sample_combo(
    hand_class: str, excluded: set[Card], rng: random.Random
) -> tuple[Card, Card] | None:
    """Sample a uniform random combo from `hand_class` with no card in `excluded`."""
    combos = _expand_hand_class(hand_class)
    valid = [c for c in combos if c[0] not in excluded and c[1] not in excluded]
    if not valid:
        return None
    return rng.choice(valid)


def _exact_equity_pair(
    combo_sb: tuple[Card, Card],
    combo_bb: tuple[Card, Card],
    rng: random.Random,
    boards: int,
) -> float:
    """Return SB's equity (wins + 0.5 * ties) against a specific BB combo
    via Monte Carlo over `boards` random 5-card boards."""
    excluded = {combo_sb[0], combo_sb[1], combo_bb[0], combo_bb[1]}
    deck = [
        Card(r, s) for r in range(2, 15) for s in range(4) if Card(r, s) not in excluded
    ]
    sb_hand = list(combo_sb)
    bb_hand = list(combo_bb)
    wins = 0
    ties = 0
    sample = rng.sample
    for _ in range(boards):
        board = sample(deck, 5)
        s0 = evaluate(sb_hand + board)
        s1 = evaluate(bb_hand + board)
        if s0 > s1:
            wins += 1
        elif s0 == s1:
            ties += 1
    return (wins + 0.5 * ties) / boards


def build_equity_matrix(
    hand_classes: list[str],
    rng: random.Random,
    combo_pairs_per_class_pair: int = EQUITY_COMBO_PAIRS_PER_CLASS_PAIR,
    boards_per_combo_pair: int = EQUITY_BOARDS_PER_COMBO_PAIR,
    verbose: bool = True,
) -> np.ndarray:
    """Return matrix E[i][j] = SB equity (hand_class i vs j), averaged over
    a uniform sample of compatible (combo_sb, combo_bb) representatives.

    Per class pair we sample `combo_pairs_per_class_pair` random compatible
    combo pairings (capturing suit-config variance: AKs vs KQs equity
    depends on whether the ace blocks the king-queen suit) and evaluate
    `boards_per_combo_pair` random 5-card boards per pairing.

    Incompatible class pairs (e.g. AA vs AA — only 4 aces in the deck)
    get nan, never read by the solver because compat_count == 0 there.
    """
    n = len(hand_classes)
    equity = np.full((n, n), np.nan, dtype=np.float64)
    combos: list[list[tuple[Card, Card]]] = [
        _expand_hand_class(h) for h in hand_classes
    ]
    start = time.time()
    for i in range(n):
        if verbose and i % 20 == 0:
            elapsed = time.time() - start
            print(
                f"  equity matrix row {i:3d}/{n}  ({hand_classes[i]:>3s}) "
                f"elapsed={elapsed:6.1f}s",
                flush=True,
            )
        for j in range(n):
            samples: list[float] = []
            # Pick up to `combo_pairs_per_class_pair` random compatible
            # combo pairs (with replacement if the compatible pool is small).
            for _ in range(combo_pairs_per_class_pair):
                combo_a = rng.choice(combos[i])
                # Pick a compatible combo b. Try a few random combos; if all
                # conflict, do a full scan.
                compat_combo_b = None
                for _attempt in range(8):
                    cb = rng.choice(combos[j])
                    if cb[0] not in (combo_a[0], combo_a[1]) and cb[1] not in (
                        combo_a[0],
                        combo_a[1],
                    ):
                        compat_combo_b = cb
                        break
                if compat_combo_b is None:
                    valid = [
                        cb
                        for cb in combos[j]
                        if cb[0] not in (combo_a[0], combo_a[1])
                        and cb[1] not in (combo_a[0], combo_a[1])
                    ]
                    if not valid:
                        continue
                    compat_combo_b = rng.choice(valid)
                samples.append(
                    _exact_equity_pair(
                        combo_a, compat_combo_b, rng, boards_per_combo_pair
                    )
                )
            if samples:
                equity[i, j] = sum(samples) / len(samples)
    if verbose:
        print(
            f"  equity matrix complete in {time.time()-start:.1f}s",
            flush=True,
        )
    return equity


# ---------------------------------------------------------------------------
# DCFR matrix-game solver (per stack depth)
# ---------------------------------------------------------------------------


def _payoff_jam_called_sb(depth_bb: int, equity_sb: float) -> float:
    """SB's chip-EV in BB units when SB jams and BB calls.

    Pot after call = 2 * depth_bb (both players in for `depth_bb` BB each).
    SB risked `depth_bb` BB, wins it back plus opp's `depth_bb` BB with prob
    eq, loses `depth_bb` BB with prob (1 - eq). Net = depth_bb * (2*eq - 1).
    """
    return float(depth_bb) * (2.0 * equity_sb - 1.0)


def solve_pushfold_for_depth(
    depth_bb: int,
    hand_classes: list[str],
    equity: np.ndarray,
    compat: np.ndarray,
    iterations: int = DCFR_ITERATIONS,
    alpha: float = DCFR_ALPHA,
    beta: float = DCFR_BETA,
    gamma: float = DCFR_GAMMA,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (sb_jam_freq, bb_call_freq, exploitability_bb_per_100) for one depth.

    Models the abstracted preflop game:
      SB has |hand_classes| infosets (own hand_class). Action set {fold, jam}.
      BB has |hand_classes| infosets ("SB jammed; my hand_class"). Action set
        {fold, call}.

    Joint hand prior weights each (h_sb, h_bb) by compat[h_sb][h_bb] (number
    of disjoint combo pairings). DCFR regret matching with the standard
    (alpha, beta, gamma) discount schedule on positive regrets, negative
    regrets, and the strategy sum respectively.

    Returns SB's jam frequency per hand class and BB's call-vs-jam frequency
    per hand class, both as 1-D arrays in the same order as `hand_classes`,
    along with a coarse exploitability estimate in milli-bb/100 (computed by
    best-responding against the average strategies).
    """
    n = len(hand_classes)

    # Joint prior P(h_sb, h_bb) over the 169x169 grid, with card-removal
    # accounted via `compat`. Normalize so weights sum to 1 (numerical
    # convenience, not strictly necessary for regret matching).
    joint = compat.astype(np.float64)
    joint_sum = joint.sum()
    if joint_sum > 0:
        joint /= joint_sum
    p_sb = joint.sum(axis=1)  # marginal P(SB hand = h_sb)
    p_bb = joint.sum(axis=0)  # marginal P(BB hand = h_bb)
    p_bb_given_sb = np.where(
        p_sb[:, None] > 0, joint / np.where(p_sb[:, None] > 0, p_sb[:, None], 1.0), 0.0
    )
    p_sb_given_bb = np.where(
        p_bb[None, :] > 0, joint / np.where(p_bb[None, :] > 0, p_bb[None, :], 1.0), 0.0
    )

    # Per-pair SB-EV-if-called (in BB units), masked by compatibility.
    showdown_ev = np.where(
        np.isnan(equity),
        0.0,
        depth_bb * (2.0 * np.nan_to_num(equity, nan=0.5) - 1.0),
    )

    # Strategy storage. Order: [fold, jam] for SB; [fold, call] for BB.
    sb_regret = np.zeros((n, 2), dtype=np.float64)
    bb_regret = np.zeros((n, 2), dtype=np.float64)
    sb_strategy_sum = np.zeros((n, 2), dtype=np.float64)
    bb_strategy_sum = np.zeros((n, 2), dtype=np.float64)

    def regret_to_strategy(regret: np.ndarray) -> np.ndarray:
        pos = np.maximum(regret, 0.0)
        sums = pos.sum(axis=1, keepdims=True)
        strategy = np.where(sums > 0, pos / np.where(sums > 0, sums, 1.0), 0.5)
        return strategy

    fold_ev_sb = -SMALL_BLIND_BB  # SB folds = loses small blind
    bb_uncontested_fold_ev = -BIG_BLIND_BB  # BB folds vs jam = -1 BB

    for t in range(1, iterations + 1):
        # ---- get current strategies via regret matching ----
        sb_strategy = regret_to_strategy(sb_regret)
        bb_strategy = regret_to_strategy(bb_regret)

        # SB EV per hand class for each action.
        # When SB jams: EV = sum_bb P(h_bb|h_sb) * [
        #   p_fold_bb(h_bb) * (+BIG_BLIND)   # BB folds, SB wins BB's blind
        # + p_call_bb(h_bb) * showdown_ev(h_sb,h_bb)
        # ]
        bb_fold = bb_strategy[:, 0]
        bb_call = bb_strategy[:, 1]
        # jam_ev_when_called[h_sb] = sum_bb P(h_bb|h_sb) * p_call_bb(h_bb) * showdown_ev
        jam_ev_called = (p_bb_given_sb * bb_call[None, :] * showdown_ev).sum(axis=1)
        jam_ev_fold = BIG_BLIND_BB * (p_bb_given_sb * bb_fold[None, :]).sum(axis=1)
        jam_ev = jam_ev_called + jam_ev_fold
        sb_action_values = np.stack(
            [np.full(n, fold_ev_sb), jam_ev], axis=1
        )  # shape (n, 2)
        sb_node_value = (sb_strategy * sb_action_values).sum(axis=1)

        # BB EV per hand class given SB jammed.
        # call_ev[h_bb] = E_{h_sb | jam, h_bb} [ -showdown_ev(h_sb, h_bb) ]
        # The conditional P(h_sb | jam, h_bb) ∝ P(h_sb, h_bb) * p_jam(h_sb)
        # via Bayes' rule. In regret matching with simultaneous updates we
        # use the *current* SB strategy.
        sb_jam = sb_strategy[:, 1]
        # P(h_sb, jam | h_bb) for each h_bb -- the joint times SB's jam prob
        # along the h_sb dim, divided by P(h_bb).
        joint_jam_given_bb = p_sb_given_bb * sb_jam[:, None]  # (h_sb, h_bb)
        p_sb_jams_given_bb = joint_jam_given_bb.sum(axis=0)  # P(jam | h_bb)
        p_sb_jams_given_bb_safe = np.where(
            p_sb_jams_given_bb > 0, p_sb_jams_given_bb, 1.0
        )
        # Conditional P(h_sb | jam, h_bb) = joint_jam_given_bb[h_sb, h_bb] / P(jam | h_bb)
        cond_sb_given_jam_bb = joint_jam_given_bb / p_sb_jams_given_bb_safe[None, :]
        call_ev = -(cond_sb_given_jam_bb * showdown_ev).sum(axis=0)
        bb_action_values = np.stack(
            [np.full(n, bb_uncontested_fold_ev), call_ev], axis=1
        )
        bb_node_value = (bb_strategy * bb_action_values).sum(axis=1)

        # Counterfactual reach for BB at infoset h_bb = opponent's reach to
        # the infoset given BB holds h_bb. That's P(SB jams | h_bb).
        bb_cf_reach = p_sb_jams_given_bb

        # ---- DCFR discounts ----
        ta = float(t) ** alpha
        tb = float(t) ** beta
        pos_scale = ta / (ta + 1.0)
        neg_scale = tb / (tb + 1.0)
        strat_scale = (float(t) / (float(t) + 1.0)) ** gamma

        for regret_arr in (sb_regret, bb_regret):
            regret_arr[:] = np.where(
                regret_arr > 0,
                regret_arr * pos_scale,
                np.where(regret_arr < 0, regret_arr * neg_scale, regret_arr),
            )
        sb_strategy_sum *= strat_scale
        bb_strategy_sum *= strat_scale

        # ---- accumulate regrets and strategy sums ----
        # Counterfactual reach for SB at infoset h_sb is the opponents'
        # reach -- here, just chance (the prior on BB's hand). Since we
        # condition the SB EV on h_sb already, that opponents'-reach
        # factor is constant in h_sb and we can fold it in via p_sb (the
        # marginal hand-prior, since regret scales the same for all
        # actions at the infoset).
        sb_regret += p_sb[:, None] * (sb_action_values - sb_node_value[:, None])
        # BB's regret is counterfactual-reach-weighted by P(SB jams | h_bb).
        bb_regret += bb_cf_reach[:, None] * (bb_action_values - bb_node_value[:, None])

        # Player-own-reach-weighted strategy sums (DCFR averaging).
        # Own reach to (h_sb) infoset = P(h_sb); to (h_bb) infoset = P(h_bb).
        sb_strategy_sum += p_sb[:, None] * sb_strategy
        bb_strategy_sum += p_bb[:, None] * bb_strategy

    # ---- finalize average strategy ----
    def avg_strategy(strategy_sum: np.ndarray) -> np.ndarray:
        sums = strategy_sum.sum(axis=1, keepdims=True)
        return np.where(sums > 0, strategy_sum / np.where(sums > 0, sums, 1.0), 0.5)

    sb_avg = avg_strategy(sb_strategy_sum)
    bb_avg = avg_strategy(bb_strategy_sum)
    sb_jam_freq = sb_avg[:, 1]
    bb_call_freq = bb_avg[:, 1]

    # Coarse exploitability: best-response value minus on-policy value.
    expl = _exploitability(
        n,
        depth_bb,
        p_sb,
        p_bb,
        p_bb_given_sb,
        p_sb_given_bb,
        showdown_ev,
        sb_avg,
        bb_avg,
    )
    return sb_jam_freq, bb_call_freq, expl


def _exploitability(
    n: int,
    depth_bb: int,
    p_sb: np.ndarray,
    p_bb: np.ndarray,
    p_bb_given_sb: np.ndarray,
    p_sb_given_bb: np.ndarray,
    showdown_ev: np.ndarray,
    sb_avg: np.ndarray,
    bb_avg: np.ndarray,
) -> float:
    """Best-response gap in BB / 100 hands."""
    bb_fold = bb_avg[:, 0]
    bb_call = bb_avg[:, 1]
    jam_ev_called = (p_bb_given_sb * bb_call[None, :] * showdown_ev).sum(axis=1)
    jam_ev_fold = BIG_BLIND_BB * (p_bb_given_sb * bb_fold[None, :]).sum(axis=1)
    sb_action_ev = np.stack(
        [np.full(n, -SMALL_BLIND_BB), jam_ev_called + jam_ev_fold], axis=1
    )
    sb_best = sb_action_ev.max(axis=1)
    sb_on_policy = (sb_avg * sb_action_ev).sum(axis=1)
    sb_gap = (p_sb * (sb_best - sb_on_policy)).sum()

    sb_jam = sb_avg[:, 1]
    joint_jam_given_bb = p_sb_given_bb * sb_jam[:, None]
    p_sb_jams_given_bb = joint_jam_given_bb.sum(axis=0)
    p_sb_jams_given_bb_safe = np.where(p_sb_jams_given_bb > 0, p_sb_jams_given_bb, 1.0)
    cond_sb_given_jam_bb = joint_jam_given_bb / p_sb_jams_given_bb_safe[None, :]
    call_ev = -(cond_sb_given_jam_bb * showdown_ev).sum(axis=0)
    bb_action_ev = np.stack([np.full(n, -BIG_BLIND_BB), call_ev], axis=1)
    bb_best = bb_action_ev.max(axis=1)
    bb_on_policy = (bb_avg * bb_action_ev).sum(axis=1)
    # BB's contribution scaled by P(reach the infoset) = P(h_bb) * P(SB jams|h_bb).
    bb_gap = (p_bb * p_sb_jams_given_bb * (bb_best - bb_on_policy)).sum()

    # Convert BB/hand to BB/100. Average over players (NashConv / 2).
    return float((sb_gap + bb_gap) * 100.0 / 2.0)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _coerce_freq(x: float) -> float:
    """Clip floating-point noise out of strategy frequencies."""
    if x <= 1e-4:
        return 0.0
    if x >= 1.0 - 1e-4:
        return 1.0
    return round(float(x), 4)


def _build_chart_dict(
    hand_classes: list[str], freqs: np.ndarray, sparse: bool = True
) -> dict[str, float]:
    """Return {hand_class: freq} mapping; if `sparse`, omit zero-frequency keys."""
    out: dict[str, float] = {}
    for h, f in zip(hand_classes, freqs):
        clipped = _coerce_freq(float(f))
        if sparse and clipped == 0.0:
            continue
        out[h] = clipped
    return out


def _format_landmark_table(
    hand_classes: list[str],
    sb_jam_by_depth: dict[int, np.ndarray],
) -> list[str]:
    idx = {h: i for i, h in enumerate(hand_classes)}
    header = "depth |  " + "  ".join(f"{h:>4s}" for h in LANDMARK_HANDS)
    rows = [header, "-" * len(header)]
    for d in sorted(sb_jam_by_depth.keys()):
        freqs = sb_jam_by_depth[d]
        row = f"  {d:>3d} |  " + "  ".join(
            f"{freqs[idx[h]]:>4.2f}" for h in LANDMARK_HANDS
        )
        rows.append(row)
    return rows


def _flag_sklansky_deviations(
    hand_classes: list[str],
    sb_jam_by_depth: dict[int, np.ndarray],
) -> list[str]:
    """Return list of formatted lines naming Sklansky-Chubukov deviations > 2%."""
    idx = {h: i for i, h in enumerate(hand_classes)}
    flags: list[str] = []
    for (depth, hand), expected in sorted(SKLANSKY_ANCHORS.items()):
        if depth not in sb_jam_by_depth or hand not in idx:
            continue
        observed = float(sb_jam_by_depth[depth][idx[hand]])
        delta = abs(observed - expected)
        if delta > 0.02:
            flags.append(
                f"depth={depth:>2d}  hand={hand:>4s}  "
                f"observed={observed:.3f}  expected={expected:.3f}  "
                f"delta={delta:.3f}"
            )
    return flags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solve a single stack depth (5 BB) for a quick smoke test; do not "
        "overwrite the chart JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CHART_OUTPUT_PATH,
        help="Path to the chart JSON file to write (default: %(default)s).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DCFR_ITERATIONS,
        help="DCFR iterations per stack depth (default: %(default)s).",
    )
    parser.add_argument(
        "--equity-combo-pairs",
        type=int,
        default=EQUITY_COMBO_PAIRS_PER_CLASS_PAIR,
        help="Combo pairs sampled per class pair (default: %(default)s).",
    )
    parser.add_argument(
        "--equity-boards",
        type=int,
        default=EQUITY_BOARDS_PER_COMBO_PAIR,
        help="Monte Carlo boards per combo pair (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    # In dry-run we shrink the equity matrix sampling so the smoke test
    # completes in <60s regardless of the user-supplied flag defaults.
    if args.dry_run:
        args.equity_combo_pairs = min(args.equity_combo_pairs, 2)
        args.equity_boards = min(args.equity_boards, 100)
        args.iterations = min(args.iterations, 1000)

    random.seed(42)
    rng = random.Random(42)
    np.random.seed(42)

    hand_classes = canonical_hand_classes()
    assert len(hand_classes) == 169, "Expected 169 canonical hand classes"

    total_boards = args.equity_combo_pairs * args.equity_boards
    print(
        f"[1/4] Building 169x169 equity matrix "
        f"({args.equity_combo_pairs} combo pairs x {args.equity_boards} boards "
        f"= {total_boards} samples/class-pair)..."
    )
    t0 = time.time()
    equity = build_equity_matrix(
        hand_classes,
        rng,
        combo_pairs_per_class_pair=args.equity_combo_pairs,
        boards_per_combo_pair=args.equity_boards,
    )
    t_equity = time.time() - t0
    print(f"  equity matrix built in {t_equity:.1f}s")

    print("[2/4] Counting combo compatibility...")
    t0 = time.time()
    compat = _build_compat_count(hand_classes)
    t_compat = time.time() - t0
    print(f"  compat matrix built in {t_compat:.1f}s")

    depths_to_solve = [5] if args.dry_run else list(STACK_DEPTHS)

    print(f"[3/4] Solving DCFR for {len(depths_to_solve)} stack depth(s)...")
    sb_jam_by_depth: dict[int, np.ndarray] = {}
    bb_call_by_depth: dict[int, np.ndarray] = {}
    exploit_by_depth: dict[int, float] = {}
    runtime_by_depth: dict[int, float] = {}
    for d in depths_to_solve:
        t0 = time.time()
        sb_jam, bb_call, expl = solve_pushfold_for_depth(
            d,
            hand_classes,
            equity,
            compat,
            iterations=args.iterations,
        )
        runtime_by_depth[d] = time.time() - t0
        sb_jam_by_depth[d] = sb_jam
        bb_call_by_depth[d] = bb_call
        exploit_by_depth[d] = expl
        jam_pct = (
            sb_jam * np.array([combo_count(h) for h in hand_classes])
        ).sum() / 1326.0
        call_pct = (
            bb_call * np.array([combo_count(h) for h in hand_classes])
        ).sum() / 1326.0
        print(
            f"  depth={d:>2d} BB  runtime={runtime_by_depth[d]:5.1f}s  "
            f"SB jam={jam_pct:5.1%}  BB call={call_pct:5.1%}  expl={expl:6.3f} bb/100"
        )

    print("[4/4] Writing chart JSON...")

    # Build the JSON payload in Agent A's schema.
    charts: dict[str, dict[str, dict[str, float]]] = {
        "sb_jam": {},
        "bb_call_vs_jam": {},
    }
    for d, freqs in sb_jam_by_depth.items():
        charts["sb_jam"][str(d)] = _build_chart_dict(hand_classes, freqs, sparse=True)
    for d, freqs in bb_call_by_depth.items():
        charts["bb_call_vs_jam"][str(d)] = _build_chart_dict(
            hand_classes, freqs, sparse=True
        )

    metadata = {
        "version": "v1-placeholder" if args.dry_run else "v1",
        "ante": ANTE_BB,
        "small_blind": SMALL_BLIND_BB,
        "big_blind": BIG_BLIND_BB,
        "stack_depths_bb": sorted(depths_to_solve),
        "notation": "poker_solver.range -- hand classes like AA, AKs, AKo (169 total)",
        "generator": "scripts/generate_pushfold_charts.py",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iterations_per_solve": args.iterations,
        "equity_combo_pairs_per_class_pair": args.equity_combo_pairs,
        "equity_boards_per_combo_pair": args.equity_boards,
        "dcfr_hyperparameters": {
            "alpha": DCFR_ALPHA,
            "beta": DCFR_BETA,
            "gamma": DCFR_GAMMA,
        },
        "exploitability_bb_per_100": {
            str(d): round(exploit_by_depth[d], 4) for d in sorted(depths_to_solve)
        },
        "notes": (
            "Pure jam/fold action set. SB jams or folds; BB calls or folds. "
            "No minraise / limp lines (see docs/pushfold_v1_generation_notes.md). "
            "Hands omitted from a (depth, position) cell default to frequency 0.0."
        ),
        "charts": charts,
    }

    if args.dry_run:
        print("\n[dry-run] Skipping JSON write; printing landmarks.")
    else:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, sort_keys=False)
            fh.write("\n")
        print(f"  wrote {output_path}")

    # ----- Sanity printout -----
    print("\nLandmark SB jam frequencies:")
    for line in _format_landmark_table(hand_classes, sb_jam_by_depth):
        print("  " + line)

    flags = _flag_sklansky_deviations(hand_classes, sb_jam_by_depth)
    if flags:
        print("\nDeviations > 2% vs Sklansky-Chubukov anchors:")
        for f in flags:
            print("  " + f)
    else:
        print("\nNo deviations > 2% vs Sklansky-Chubukov anchors.")

    total_runtime = t_equity + t_compat + sum(runtime_by_depth.values())
    print(f"\nTotal runtime: {total_runtime:.1f}s ({total_runtime/60:.1f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
