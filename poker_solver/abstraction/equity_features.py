"""Equity-distribution histograms for card-abstraction features (Stage 1).

License posture: no third-party code derivation; equity feature is original
(implemented from first principles atop :func:`poker_solver.evaluator.evaluate`).

For each (board, hero_hole_cards, street), compute the histogram (over ``H``
equal-width bins on equity in [0, 1]) of the hand's equity against a
uniform-random opponent hole pair, integrated over all future board runouts.

Three per-street entry points (:func:`compute_river_features`, etc.) produce
(N, H) float32 feature matrices that downstream EMD-clustering in
:mod:`poker_solver.abstraction.emd_clustering` consumes.

A pure helper :func:`canonicalize_for_suit_iso` exposes the suit-isomorphism
key Agent B uses to dedup and index bucket tables. Per locked decision D1,
suit-iso ships in PR 4 (not deferred to PR 4.5).

Per locked decision D2, the default for flop / turn / river features is Monte
Carlo with 200_000 iterations per (board, hand). ``mode="exact"`` is still
exposed for unit tests where bit-identical enumeration matters and the runout
space is small.

All randomness flows through a ``numpy.random.Generator`` derived from the
``seed`` argument; reruns with identical inputs produce byte-identical output.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Literal

import numpy as np

from poker_solver.card import Card, full_deck
from poker_solver.evaluator import evaluate
from poker_solver.hunl import Street

# Number of suit permutations: 4! = 24. Cast explicitly: ``itertools.permutations``
# returns ``tuple[int, ...]`` per its stub, but for a 4-element input every output
# is a length-4 tuple — so narrow to ``tuple[int, int, int, int]`` for downstream
# indexing convenience.
_SUIT_PERMUTATIONS: tuple[tuple[int, int, int, int], ...] = tuple(
    (p[0], p[1], p[2], p[3]) for p in itertools.permutations((0, 1, 2, 3))
)


def _validate_street_board(board: Sequence[Card], street: Street) -> None:
    """Raise ValueError if the board length doesn't match the street."""
    expected = {Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}
    if street not in expected:
        raise ValueError(
            f"equity_distribution supports FLOP/TURN/RIVER; got {street.name}"
        )
    if len(board) != expected[street]:
        raise ValueError(
            f"{street.name} requires {expected[street]} board cards; got {len(board)}"
        )


def _validate_no_conflict(board: Sequence[Card], hole_cards: tuple[Card, Card]) -> None:
    """Raise ValueError on duplicate cards across board + hero hole."""
    if hole_cards[0] == hole_cards[1]:
        raise ValueError(f"hole_cards has duplicate: {hole_cards}")
    used = list(board) + list(hole_cards)
    if len(set(used)) != len(used):
        raise ValueError(
            f"Duplicate cards across board+hole: board={list(board)} "
            f"hole={list(hole_cards)}"
        )


def _bin_equity(equity: float, H: int) -> int:
    """Bin a scalar equity in [0, 1] into one of H equal-width bins.

    Boundaries land on the lower index (``int(0.5 * 50) = 25``). Equity ==
    1.0 (the nuts) clamps to ``H - 1``.
    """
    idx = int(equity * H)
    if idx < 0:
        idx = 0
    if idx >= H:
        idx = H - 1
    return idx


def _river_equity_vs_uniform(
    board: Sequence[Card],
    hero_hole: tuple[Card, Card],
) -> float:
    """Exact equity for hero on a full 5-card board vs uniform-random opponent.

    Enumerates all C(45, 2) = 990 opponent hole-card combos from the deck
    complement of (board ∪ hero_hole), evaluates the 7-card showdown for both
    players, and returns ``(wins + 0.5 * ties) / total``.
    """
    used = set(board) | set(hero_hole)
    remaining = [c for c in full_deck() if c not in used]
    hero_score = evaluate(list(hero_hole) + list(board))

    wins = 0
    ties = 0
    total = 0
    for opp_a, opp_b in itertools.combinations(remaining, 2):
        opp_score = evaluate([opp_a, opp_b] + list(board))
        if hero_score > opp_score:
            wins += 1
        elif hero_score == opp_score:
            ties += 1
        total += 1
    return (wins + 0.5 * ties) / total if total > 0 else 0.0


def _enumerate_turn_runouts(
    board4: Sequence[Card],
    hero_hole: tuple[Card, Card],
) -> list[float]:
    """For each of the 44 unseen river cards on a 4-card turn board, return
    the river equity of hero vs uniform-random opponent."""
    used = set(board4) | set(hero_hole)
    candidates = [c for c in full_deck() if c not in used]
    out: list[float] = []
    for river_card in candidates:
        full5 = list(board4) + [river_card]
        out.append(_river_equity_vs_uniform(full5, hero_hole))
    return out


def _flop_runout_iter_exact(
    board3: Sequence[Card],
    hero_hole: tuple[Card, Card],
) -> list[tuple[Card, Card]]:
    """Return all C(44, 2) = 946 unordered (turn, river) candidate pairs."""
    used = set(board3) | set(hero_hole)
    candidates = [c for c in full_deck() if c not in used]
    return list(itertools.combinations(candidates, 2))


def _flop_runout_iter_mc(
    board3: Sequence[Card],
    hero_hole: tuple[Card, Card],
    n_samples: int,
    rng: np.random.Generator,
) -> list[tuple[Card, Card]]:
    """Sample ``n_samples`` unordered (turn, river) pairs uniformly from the
    44 cards remaining after board+hero."""
    used = set(board3) | set(hero_hole)
    candidates = [c for c in full_deck() if c not in used]
    n_cand = len(candidates)
    if n_cand < 2:
        return []
    out: list[tuple[Card, Card]] = []
    # ``rng.integers`` draws uniformly. Reject (i == j) pairs and order them
    # canonically as (min, max) so the unordered-pair distribution is uniform
    # over C(44, 2) pairs.
    while len(out) < n_samples:
        a = int(rng.integers(0, n_cand))
        b = int(rng.integers(0, n_cand))
        if a == b:
            continue
        if a > b:
            a, b = b, a
        out.append((candidates[a], candidates[b]))
    return out


def equity_distribution(
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Equity-distribution histogram of one (board, hand) on one street.

    The "histogram" is the distribution of hero's *river* equity (vs a
    uniform-random opponent hole) across all future board runouts from
    ``street``:

      - ``RIVER``: a single equity value (the board is complete), placed in
        one bin; the histogram is one-hot at the binned equity.
      - ``TURN``: 44 river-equity values, one per unseen river card; the
        histogram is the 44-sample distribution over H bins.
      - ``FLOP``: under ``mode="exact"``, the 946 unordered (turn, river)
        pairs; under ``mode="mc"``, ``mc_iterations`` uniformly-sampled
        unordered (turn, river) pairs via ``rng``.

    L1-normalized: ``output.sum() == 1.0``. Equity boundaries bin to the
    lower index (e.g., 0.5 with H=50 lands in bin 25); equity == 1.0 clamps
    to bin ``H-1``.

    Args:
        board: 3/4/5 community cards (flop/turn/river).
        hole_cards: hero's two distinct hole cards (unordered).
        street: must be FLOP, TURN, or RIVER. Others raise ``ValueError``.
        H: number of equal-width bins on equity in [0, 1] (default 50).
        mode: "exact" enumerates all runouts; "mc" samples ``mc_iterations``
            unordered (turn, river) pairs (flop only; river/turn are always
            exact since their runout space is tiny).
        mc_iterations: number of MC samples when ``mode="mc"`` (default
            200_000, locked per D2).
        rng: NumPy ``Generator`` for MC sampling. If ``None``, uses
            ``np.random.default_rng(0)``. Pass an explicit ``rng`` for
            bit-reproducibility across calls.

    Returns:
        ``(H,)`` float32 array, L1-normalized.

    Raises:
        ValueError: on board/street length mismatch, duplicate cards, or
            unsupported street.
    """
    if H <= 0:
        raise ValueError(f"H must be positive; got {H}")
    _validate_street_board(board, street)
    _validate_no_conflict(board, hole_cards)
    if rng is None:
        rng = np.random.default_rng(0)

    counts = np.zeros(H, dtype=np.float64)

    if street == Street.RIVER:
        eq = _river_equity_vs_uniform(board, hole_cards)
        counts[_bin_equity(eq, H)] = 1.0
    elif street == Street.TURN:
        # Turn always exact: 44 runouts is cheap. We honor "mc" by still
        # enumerating since exact is strictly more accurate at this scale.
        equities = _enumerate_turn_runouts(board, hole_cards)
        for eq in equities:
            counts[_bin_equity(eq, H)] += 1.0
    elif street == Street.FLOP:
        if mode == "exact":
            pairs = _flop_runout_iter_exact(board, hole_cards)
        else:
            if mc_iterations <= 0:
                raise ValueError(
                    f"mc_iterations must be positive when mode='mc'; got "
                    f"{mc_iterations}"
                )
            pairs = _flop_runout_iter_mc(board, hole_cards, mc_iterations, rng)
        for turn_card, river_card in pairs:
            full5 = list(board) + [turn_card, river_card]
            eq = _river_equity_vs_uniform(full5, hole_cards)
            counts[_bin_equity(eq, H)] += 1.0
    else:  # pragma: no cover — guarded above
        raise ValueError(f"Unsupported street: {street}")

    total = float(counts.sum())
    if total <= 0:
        # Degenerate fallback: uniform over bins. Should not happen on a
        # valid board/hand pair.
        return np.full(H, 1.0 / H, dtype=np.float32)
    return (counts / total).astype(np.float32)


def _compute_features_for_street(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    street: Street,
    H: int,
    mode: Literal["exact", "mc"],
    mc_iterations: int,
    seed: int,
    progress: bool,
) -> np.ndarray:
    """Shared per-street feature builder; row order is documented in the
    public ``compute_*_features`` entry points.

    Determinism: a single ``np.random.default_rng(seed)`` is constructed
    here, and per-(board, hand) sub-rngs are derived deterministically by
    spawning child rngs in row order via ``rng.spawn(1)``. This guarantees
    that two reruns with identical inputs produce identical histograms even
    if iteration order over boards/hands is preserved.
    """
    # Count rows up-front so we can allocate (N, H) deterministically.
    total_rows = 0
    for i in range(len(boards)):
        total_rows += len(hands_per_board.get(i, []))

    out = np.zeros((total_rows, H), dtype=np.float32)
    if total_rows == 0:
        return out

    parent_rng = np.random.default_rng(seed)
    row = 0
    for i, board in enumerate(boards):
        hands = hands_per_board.get(i, [])
        for hand in hands:
            # Spawn a fresh child rng per (board, hand). This shields each
            # row from any neighboring row's draw count and guarantees the
            # output of any single row is determined solely by (seed, i,
            # within-board index, mc_iterations) — bit-reproducible.
            child = parent_rng.spawn(1)[0]
            out[row] = equity_distribution(
                board=board,
                hole_cards=hand,
                street=street,
                H=H,
                mode=mode,
                mc_iterations=mc_iterations,
                rng=child,
            )
            row += 1
            if progress and (row % 1000 == 0):
                # Plain stderr-style progress; avoid stdout to stay quiet
                # under capture in tests. We use a simple print so we don't
                # add a tqdm dep (D7.4).
                print(
                    f"[equity_features] {street.name} row {row}/{total_rows}",
                    flush=True,
                )
    return out


def compute_river_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 river entry point.

    Each river board has 5 cards; the histogram per (board, hand) is one-hot
    at the binned equity, so ``mode`` and ``mc_iterations`` are ignored (river
    runouts are exact by construction). ``seed`` is unused on the river but
    accepted for API symmetry.

    Args:
        boards: list of 5-card tuples (canonical sort already applied by
            caller; this function does not re-canonicalize).
        hands_per_board: ``dict[board_index, list[hole_pair]]``; only
            ``hole_pair``s that don't collide with the board are valid.
        H: bin count (default 50).
        mode: ignored on river.
        mc_iterations: ignored on river.
        seed: ignored on river.
        progress: emit a progress line every 1000 rows on stdout.

    Returns:
        ``(N, H)`` float32 feature matrix where
        ``N = sum(len(hands_per_board[i]) for i in range(len(boards)))``.
        Row order: for board ``i`` in order, for hand in
        ``hands_per_board[i]`` in order.
    """
    return _compute_features_for_street(
        boards=boards,
        hands_per_board=hands_per_board,
        street=Street.RIVER,
        H=H,
        mode=mode,
        mc_iterations=mc_iterations,
        seed=seed,
        progress=progress,
    )


def compute_turn_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 turn entry point. Boards have 4 cards.

    Turn features always enumerate the 44 unseen river cards (small runout
    space; exact is fast). ``mode`` / ``mc_iterations`` are accepted for API
    symmetry but unused. ``seed`` is also unused on turn.

    See :func:`compute_river_features` for the row-order contract.
    """
    return _compute_features_for_street(
        boards=boards,
        hands_per_board=hands_per_board,
        street=Street.TURN,
        H=H,
        mode=mode,
        mc_iterations=mc_iterations,
        seed=seed,
        progress=progress,
    )


def compute_flop_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 flop entry point. Boards have 3 cards.

    Default ``mode="mc"`` with ``mc_iterations=200_000`` per locked D2.
    ``mode="exact"`` enumerates all C(44, 2) = 946 unordered (turn, river)
    pairs per (board, hand) — useful for tests with small board sets but
    multi-day for the full 1755-flop build.

    See :func:`compute_river_features` for the row-order contract.
    """
    return _compute_features_for_street(
        boards=boards,
        hands_per_board=hands_per_board,
        street=Street.FLOP,
        H=H,
        mode=mode,
        mc_iterations=mc_iterations,
        seed=seed,
        progress=progress,
    )


# --------------------------------------------------------------------------
# Suit-isomorphism canonicalization (locked D1: ships in PR 4).
# --------------------------------------------------------------------------


def _apply_perm_to_card(card: Card, perm: tuple[int, int, int, int]) -> Card:
    """Return a Card with the same rank and ``perm[card.suit]`` as the new suit."""
    return Card(card.rank, perm[card.suit])


def _board_key_under_perm(
    board: Sequence[Card],
    perm: tuple[int, int, int, int],
) -> tuple[tuple[int, int], ...]:
    """Apply ``perm`` to every card in ``board``, sort the resulting pairs,
    and return them as a hashable tuple. Used as the canonical-key
    comparator across the 24 permutations.

    Sorting makes the key independent of input card order on the board.
    """
    permuted = [(c.rank, perm[c.suit]) for c in board]
    permuted.sort()
    return tuple(permuted)


def canonicalize_for_suit_iso(
    board: Sequence[Card],
    hand: tuple[Card, Card],
) -> tuple[str, int]:
    """Suit-isomorphism canonical key for a (board, hand) pair.

    Two boards that are suit-isomorphic (i.e., one is a global suit
    permutation of the other) produce the same ``canonical_board_key``.
    The chosen permutation makes the board's sorted-pair tuple
    lexicographically minimal across the 24 suit permutations of
    ``{0, 1, 2, 3}``; ties are broken by the permutation index (earlier
    permutation in ``itertools.permutations((0,1,2,3))`` wins).

    Hand canonicalization: applying the chosen permutation to ``hand``
    yields a deterministic hand representation that Agent B uses as the
    within-canonical-board hand key. (Agent B is responsible for encoding
    the permuted hand into a within-board index; this function just
    surfaces the permutation_index so Agent B can recover it.)

    Locked per decision D1 (suit-iso INCLUDED in PR 4, not deferred).

    Args:
        board: 3/4/5 community cards (any order — internally sorted).
        hand: hero's two hole cards (unordered).

    Returns:
        ``(canonical_board_key, permutation_index)`` where:

          - ``canonical_board_key`` is a stable string of the form
            ``"r{rank}s{suit}_r{rank}s{suit}_..."`` over the suit-permuted,
            sorted-by-(rank, suit) board cards. The format is documented
            here so Agent B can rely on it without re-deriving it.
          - ``permutation_index`` is the index (0..23) of the chosen
            permutation in ``itertools.permutations((0,1,2,3))``.

    Notes:
        ``hand`` does NOT participate in choosing the permutation — only the
        board does. This matches the standard suit-isomorphism convention
        (the opponent range is uniform over ALL hands, so the canonical
        permutation depends only on the public board). Once the permutation
        is fixed, the caller applies it to ``hand`` via
        ``Card(c.rank, perm[c.suit])`` for each card in the hand.
    """
    if len(board) not in (3, 4, 5):
        raise ValueError(
            f"canonicalize_for_suit_iso: board must have 3/4/5 cards; got "
            f"{len(board)}"
        )
    if hand[0] == hand[1]:
        raise ValueError(f"hand has duplicate card: {hand}")
    used = list(board) + list(hand)
    if len(set(used)) != len(used):
        raise ValueError(
            f"Duplicate cards across board+hand: board={list(board)} hand={list(hand)}"
        )

    best_key: tuple[tuple[int, int], ...] | None = None
    best_perm_idx = 0
    for i, perm in enumerate(_SUIT_PERMUTATIONS):
        key = _board_key_under_perm(board, perm)
        if best_key is None or key < best_key:
            best_key = key
            best_perm_idx = i

    assert best_key is not None  # for type-narrowing
    # Stable string format. Each card is "r{rank}s{suit}" joined with "_".
    canonical_string = "_".join(f"r{r}s{s}" for r, s in best_key)
    return canonical_string, best_perm_idx
