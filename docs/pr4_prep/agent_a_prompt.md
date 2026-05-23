# PR 4 Agent A — equity features + EMD clustering

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 4 Agent A.**
**Your scope:** the equity-distribution feature extraction stage + the EMD distance + custom-NumPy k-means clustering stage of the card abstraction pipeline, including the suit-isomorphism canonicalization helper that Agent B consumes.
**Your contract:** produce a self-contained module pair (`equity_features.py` + `emd_clustering.py`) plus public helper `canonicalize_for_suit_iso(...)`, exporting the function signatures documented in §"Public API contract" below; Agent B calls these from `precompute.py` and `buckets.py`, Agent C tests them from spec alone.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on the two new files; deterministic given a seed; produces L1-normalized 50-bin equity histograms; closed-form 1-D EMD; vectorized k-means converges on synthetic 4-blob fixtures; ALL 138 existing tests still pass (your work is purely additive to `poker_solver/abstraction/`).
**File ownership:** you own and may write ONLY `poker_solver/abstraction/equity_features.py` and `poker_solver/abstraction/emd_clustering.py`. You may NOT modify any other file.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/equity_features.py` (new file)
- `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/emd_clustering.py` (new file)

**You must NOT touch:**
- `poker_solver/abstraction/__init__.py` — Agent B owns this. (Do NOT create it. Agent B will define exports there. You may inspect Agent B's output after they land, but only to verify your interfaces are wired correctly.)
- `poker_solver/abstraction/buckets.py` — Agent B
- `poker_solver/abstraction/precompute.py` — Agent B (the CLI orchestrator that calls your functions)
- `poker_solver/hunl.py` — Agent B (integration touch)
- `poker_solver/__init__.py` — Agent B (re-exports)
- `poker_solver/cli.py` — Agent B (`precompute-abstraction` subcommand)
- `pyproject.toml` — Agent B (no new third-party deps; see Decision 7.4)
- Any test file (`tests/test_abstraction_*`) — Agent C
- Any existing `poker_solver/*.py` file (`card.py`, `equity.py`, `evaluator.py`, etc.) — read-only references

If you discover an awkward signature mid-implementation, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator will reconcile across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`. Internalize §3 (conceptual architecture), §4 Stages 1–3 (your stages), §7.1 + §7.7 + §7.8 + §7.10 + §7.11 (your decisions), §8 Agent A deliverables, §9 risks.
2. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" (256/128/64 locked bucket counts) and the stack-depth-tier table.
3. **The autonomous log (locked D1/D2):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Confirm D1 = suit-iso INCLUDED in PR 4, D2 = Monte Carlo equity features at 200K iter.
4. **Spec consistency review (any cross-cutting amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Skim for entries referring to PR 4.
5. **Existing equity machinery you'll wrap:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/equity.py` — Monte Carlo equity vs uniform/range opponents. You'll re-use the `evaluate` pattern but call `poker_solver.evaluator.evaluate` directly per the spec (the existing `equity()` is too high-level for our per-(board,hand) deterministic feature builder).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/evaluator.py` — 5-to-7 card hand evaluator. Pure Python, ~200K evals/sec.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/card.py` — `Card`, `card_to_int`, `int_to_card`, `full_deck`, `RANKS`, `SUITS`. The card-int mapping is `rank * 4 + suit`, range [8, 59].
6. **HUNL street enum (for type hints in your signatures):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 57-73 define `Street` (IntEnum: PREFLOP=0, FLOP=1, TURN=2, RIVER=3, SHOWDOWN=4). Import via `from poker_solver.hunl import Street`.
7. **License-aware sourcing patterns:** see §"License-aware sourcing" below.

## Default decisions LOCKED (do not deviate)

These are amendments / clarifications to the PR 4 spec; if the spec text differs, **these locked defaults win** because the user confirmed them in the autonomous log:

- **D1 = SUIT-ISO INCLUDED in PR 4** (the PR 4 spec §7.6 originally deferred this to PR 4.5; the user reversed that — suit-iso ships in PR 4). This affects you because the `canonicalize_for_suit_iso(...)` helper is in your scope (see §"Public API contract"). Agent B uses your canonicalization to size + index the bucket tables.
- **D2 = Monte Carlo equity features at 200K iterations** (NOT exact enumeration). Default `mode="mc"`, `mc_iterations=200_000` on flop, turn, AND river feature extraction. Exact mode is still exposed via `mode="exact"` for unit-testing, but it is NOT the production path. (The spec §7.7 originally allowed exact on river + turn; we override to MC across all streets for uniformity and predictable wall-clock.)
- **Bucket counts (Agent B will pass these to your `kmeans_emd`):** 256 flop / 128 turn / 64 river per `PLAN.md` §1 "Card abstraction" table.
- **Histogram resolution: H = 50** (Decision 7.1), equal-width bins on equity in [0, 1] (Decision 7.11).
- **EMD library: custom NumPy** (Decision 7.2), 1-D closed form `mean(|cumsum(p) - cumsum(q)|)`.
- **K-means library: custom NumPy** (Decision 7.3); kmeans++ init; arithmetic-mean centroid update; max-iter 200; change-tolerance 0.001 (i.e., stop when fraction-of-points-that-changed-assignment < 0.001).
- **No new third-party dependencies** (Decision 7.4). You may import only from: `numpy`, `poker_solver.card`, `poker_solver.evaluator`, `poker_solver.hunl` (for `Street`), and the Python stdlib (`dataclasses`, `typing`, `collections.abc`, `math`, `random`, `itertools`, `functools`).
- **Flop runout enumeration: UNORDERED pairs** (Decision 7.10) — 44*43/2 = 946 pairs per flop, not ordered 1892.

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from your two files. **Signature drift breaks Agent B's `precompute.py` and Agent C's tests.** Type hints required (mypy --strict).

### From `poker_solver/abstraction/equity_features.py`

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np

from poker_solver.card import Card
from poker_solver.hunl import Street


def equity_distribution(
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return an H-element histogram (sum to 1.0, dtype float32) of the hand's
    equity vs a uniform-random opponent over all future runouts from this street.

    - For street=Street.RIVER: enumerate the ~990 opponent hole-card combos given
      board+hero, compute exact equity, return a single-bin histogram (one bin at
      the equity value).
    - For street=Street.TURN: for each of the ~44 unseen river cards, compute the
      river equity vs uniform opponent → 44 equity values → histogram over H bins.
    - For street=Street.FLOP: for each of the 44*43/2 = 946 UNORDERED (turn, river)
      pairs, compute river equity vs uniform opponent. mode="mc" samples
      mc_iterations runout-pairs uniformly with the provided rng; mode="exact"
      enumerates all 946. Output: histogram over H bins.

    L1-normalized; output[i] is the probability mass for equity bin i = [i/H, (i+1)/H).

    Args:
        board: 3/4/5 community cards for flop/turn/river.
        hole_cards: hero's two hole cards (unordered pair; canonicalize internally).
        street: one of FLOP/TURN/RIVER. PREFLOP/SHOWDOWN raise ValueError.
        H: histogram bin count (default 50).
        mode: "exact" enumerates all runouts; "mc" samples mc_iterations runouts.
        mc_iterations: number of MC samples when mode="mc" (default 200_000).
        rng: NumPy Generator for MC sampling. If None, uses default_rng(0).

    Raises:
        ValueError: if board+hole_cards conflict, board has wrong card count for
            street, hole_cards contains duplicates, or street ∉ {FLOP, TURN, RIVER}.
    """
    ...


def compute_river_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 entry for river. Returns shape (N, H) float32 features where
    N = sum(len(hands_per_board[i]) for i in range(len(boards))).

    boards: list of 5-card river boards (canonical sort already applied).
    hands_per_board: dict mapping board index -> list of hero hole-card pairs
        valid on that board (no blocker conflicts).
    Output row order: for each board i in order, for each hand in
        hands_per_board[i] in order.
    """
    ...


def compute_turn_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 entry for turn. Same shape contract as compute_river_features.
    boards have 4 cards. Default mode='mc' per locked D2."""
    ...


def compute_flop_features(
    boards: Sequence[tuple[Card, ...]],
    hands_per_board: dict[int, list[tuple[Card, Card]]],
    H: int = 50,
    mode: Literal["exact", "mc"] = "mc",
    mc_iterations: int = 200_000,
    seed: int = 42,
    progress: bool = False,
) -> np.ndarray:
    """Stage 1 entry for flop. Same shape contract. boards have 3 cards.
    Default mode='mc' per locked D2."""
    ...


def canonicalize_for_suit_iso(
    board: Sequence[Card],
    hand: tuple[Card, Card],
) -> tuple[str, int]:
    """Return (canonical_board_key, suit_permutation_index) for suit-isomorphism.

    Two (board, hand) pairs that play identically under a suit permutation must
    produce the same canonical_board_key AND the same hand-within-canonical
    indexing. The string key is a deterministic representation of the board
    after the suit-permutation that minimizes lexicographic order over the
    24 suit-permutations of {0,1,2,3}.

    The suit_permutation_index is the index (0..23) of the chosen permutation,
    used by Agent B to canonicalize the hand on a per-board basis.

    This helper is the ONLY suit-iso entry point. Agent B's bucket-table
    indexing uses (canonical_board_key, canonicalized_hand_key) as the lookup
    key. Hands within the same canonical class share the same bucket.

    Locked per D1 (suit-iso INCLUDED in PR 4).
    """
    ...
```

### From `poker_solver/abstraction/emd_clustering.py`

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def emd_1d(p: np.ndarray, q: np.ndarray) -> float:
    """1-D closed-form Wasserstein-1 / Earth Mover's Distance.

    EMD(p, q) = mean(|cumsum(p) - cumsum(q)|).
    Assumes p, q are L1-normalized 1-D float arrays of the same length.

    Edge cases:
    - emd_1d(p, p) == 0.0
    - emd_1d(delta_at_0, delta_at_H-1) == 1.0 (approximately; depends on H).
    - Symmetric: emd_1d(p, q) == emd_1d(q, p).
    - Triangle inequality holds.
    """
    ...


def batch_emd(points: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Vectorized 1-D EMD between N points and K centroids.

    points: (N, H) L1-normalized histograms.
    centroids: (K, H) L1-normalized centroids.
    Returns: (N, K) float32 distance matrix where d[i,j] == emd_1d(points[i], centroids[j]).

    Implementation hint: precompute cumsum(centroids, axis=1) once per call and
    cumsum(points, axis=1) once, then broadcast |P_cdf[:, None, :] - C_cdf[None, :, :]|.mean(axis=2).
    """
    ...


@dataclass
class KMeansResult:
    assignments: np.ndarray  # shape (N,), dtype uint16 (or uint8 if K <= 256)
    centroids: np.ndarray    # shape (K, H), dtype float32, L1-normalized rows
    history: list[float]      # per-iteration mean point-to-centroid EMD distance


def kmeans_emd(
    features: np.ndarray,
    K: int,
    seed: int = 42,
    max_iter: int = 200,
    change_tolerance: float = 0.001,
) -> KMeansResult:
    """Lloyd's-iteration k-means with EMD-on-CDFs as the distance, kmeans++ init.

    features: (N, H) L1-normalized histograms (float32 or float64).
    K: target cluster count.
    seed: RNG seed for kmeans++ initialization (deterministic given seed).
    max_iter: hard cap on iterations.
    change_tolerance: stop when fraction-of-points-that-changed-assignment < this.

    Centroid update: arithmetic mean of cluster members (per-bin), then L1-renormalize.
    Empty-cluster recovery: re-seed empty cluster from the farthest point under
    current centroids.

    Reproducibility: same (features bytes, K, seed) → identical (assignments,
    centroids) byte-for-byte.
    """
    ...


def _kmeans_plusplus_init(
    features: np.ndarray,
    K: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Internal: deterministic kmeans++ initialization given an rng.

    Picks K initial centroids by:
    1. Random first centroid.
    2. For each subsequent: probability ∝ EMD distance² to nearest existing
       centroid.

    Returns (K, H) array of L1-normalized centroids selected from features.
    """
    ...
```

## Critical correctness items

### 1. MC seeded reproducibility (D2)

When `mode="mc"`, **every** invocation of `equity_distribution(..., mode="mc", rng=...)` with the same `rng` state, the same `board`, the same `hole_cards`, and the same `mc_iterations` MUST return the bit-identical histogram. The `rng` is the only source of randomness. Do NOT call `random.random()` or `np.random.random()` without going through the supplied `rng` argument.

Inside `compute_*_features(..., seed=42, ...)`: construct `rng = np.random.default_rng(seed)` once, then either thread `rng` through every `equity_distribution` call, or generate per-(board, hand) sub-rngs with `rng.spawn(N)`-style or seed-derived sub-generators. Document the choice in a code comment.

### 2. Suit-iso canonicalization (D1)

`canonicalize_for_suit_iso(board, hand)` must be a pure function with:
- Two boards differing only by a global suit-permutation produce the **same** `canonical_board_key`.
- The chosen permutation index makes the board-key lexicographically minimal over the 24 permutations of `{0,1,2,3}` applied uniformly to all suits in the board + hand.
- Hand canonicalization is consistent with the board canonicalization: applying the chosen permutation to `hand` yields a deterministic hand representation that Agent B uses as the within-canonical-board hand key.

Example: `board=[As, 7c, 2d]` and `board=[Ah, 7d, 2s]` are suit-isomorphic if the opponent range is suit-symmetric (which uniform-random IS). Both should produce the same `canonical_board_key`. The chosen permutation determines how `hand` is canonicalized for indexing.

The canonical string format is YOUR choice (you might use sorted rank-suit pair tuples, packed integers, or a stable string like `"r14s0_r7s1_r2s2"`); document it clearly so Agent B can rely on it.

### 3. EMD math (closed-form 1-D Wasserstein-1)

`emd_1d(p, q) = mean(|cumsum(p) - cumsum(q)|)`. This is **not** sum, it's mean — divide by `H`. Cross-check via:
- `emd_1d(p, p) == 0.0`
- `emd_1d(delta_0, delta_{H-1}) ≈ (H-1)/H` — for H=50 this is ≈ 0.98. (The "1.0" in the test description is approximate.)
- Symmetry: `emd_1d(p, q) == emd_1d(q, p)`.
- Triangle: `emd_1d(p, r) <= emd_1d(p, q) + emd_1d(q, r)`.

### 4. Histogram L1-normalization

Every histogram returned by `equity_distribution` must satisfy `np.isclose(hist.sum(), 1.0, atol=1e-6)`. River single-bin case: place 1.0 at the bin containing the exact equity, zeros elsewhere. Turn/flop multi-runout case: divide raw bin counts by total count.

Edge cases:
- If a runout produces equity *exactly* on a bin boundary (e.g., equity = 0.5 with H=50 boundary at index 25 vs 26), bin to the **lower** index (use `np.clip(int(equity * H), 0, H-1)` — note `int(0.5 * 50) = 25` so 0.5 lands in bin 25).
- For an equity of exactly 1.0 (hero has the nuts), `int(1.0 * 50) = 50` is out of range; clamp to `H-1 = 49`.

### 5. K-means determinism + convergence

- `seed=42` (the default) plus the same `features` array bytes → identical `KMeansResult.assignments` and `KMeansResult.centroids` across reruns.
- Empty-cluster recovery: when a cluster has 0 assigned points in an iteration, re-seed it from the **farthest point under the current centroid set** (NOT a random point — randomness here breaks reproducibility unless explicitly seeded with the existing rng).
- Convergence: stop when `(assignments == prev_assignments).mean() >= 1.0 - change_tolerance`, OR `it == max_iter - 1`.
- `history` is a `list[float]` of length `n_iterations_actually_run`, where each entry is `np.mean(batch_emd(features, centroids).min(axis=1))` after that iteration's centroid update — the mean point-to-nearest-centroid distance. This is for convergence diagnostics; Agent C's `test_kmeans_converges_within_max_iter` asserts the sequence is non-increasing (allowing a small noise tolerance, e.g., 1e-9).

### 6. Vectorization in `batch_emd`

Naive double-loop is O(N·K·H) but slow in Python. Vectorize:
```python
P_cdf = np.cumsum(points, axis=1)           # (N, H)
C_cdf = np.cumsum(centroids, axis=1)        # (K, H)
diff = np.abs(P_cdf[:, None, :] - C_cdf[None, :, :])  # (N, K, H)
return diff.mean(axis=2).astype(np.float32)
```
Watch memory: `N * K * H * 4 bytes` can be large (e.g., 2.3M flops × 256 buckets × 50 = ~29 GB if computed all at once). If `N * K * H * 4 > 1e9` (i.e., > 1 GB), chunk along `N`:
```python
chunk_size = max(1, int(1e8 / (K * H)))
for start in range(0, N, chunk_size):
    out[start:start+chunk_size] = ...
```
Document the chunking in a code comment.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/src/build_kmeans_buckets.cpp` (**MIT**) — k-means pipeline shape (feature vectors → dedup → k-means → assignments).
- `references/code/slumbot2019/src/kmeans.cpp` (**MIT**) — `SeedPlusPlus` (kmeans++ init) pattern.
- `references/code/slumbot2019/src/build_rollout_features.cpp` (**MIT**) — per-hand feature-vector layout.
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only architectural inspiration.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration. No code copy. If you cite a pattern from this repo, do so in a docstring comment that says "pattern inspired by; no code copied" and derive your implementation from scratch.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a k-means implementation or an EMD formula and want to use it, ground it in either the locally-cited MIT source above or the PR 4 spec / PLAN. When in doubt, prefer the spec's stated approach.

If you copy a non-trivial code snippet (more than ~5 LOC) from an MIT-licensed source, add an attribution comment at the top of the function:
```python
# Pattern from slumbot2019/src/kmeans.cpp::SeedPlusPlus (MIT, attribution required).
# Reference: <repo>/references/code/slumbot2019/src/kmeans.cpp
```

## Quality bar

- **ruff clean:** `ruff check poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py` reports zero issues.
- **black clean:** `black --check poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py` reports zero errors. (mypy is not strict on the whole repo yet, but new abstraction code must be.)
- **No new third-party deps.** Confirm by checking `pyproject.toml` has not been edited (Agent B owns that). Your imports come only from `numpy` (already a dep) + stdlib + `poker_solver.*`.
- **All 138 existing tests still pass.** Run `pytest -x` after your work lands and confirm. Your work is purely additive; you should not be touching anything that breaks existing tests, but a circular import or a name collision would do so — guard against this.
- **Code size budget: ~600–800 LOC** combined across the two files (per spec §8). Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "EMD", "k-means", "abstraction", "equity distribution" entries.

If a fact is needed (e.g., "the river has 5 community cards", "C(50,2) = 1225"), it's trivially derivable — cite it inline. If a more complex claim is needed (e.g., "Slumbot uses kmeans++"), cite the specific file: `references/code/slumbot2019/src/kmeans.cpp::SeedPlusPlus`.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py
black --check poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py

# 2. Type-check
mypy --strict poker_solver/abstraction/equity_features.py poker_solver/abstraction/emd_clustering.py

# 3. Smoke test your own code (in a Python REPL)
python -c "
import numpy as np
from poker_solver.abstraction.emd_clustering import emd_1d, batch_emd, kmeans_emd

# EMD sanity
p = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
assert emd_1d(p, p) == 0.0
assert abs(emd_1d(p, q) - 0.75) < 1e-6  # CDF diffs: 1,1,1,0 / 4

# batch_emd consistency
pts = np.random.RandomState(0).dirichlet(np.ones(50), size=20).astype(np.float32)
ctrs = np.random.RandomState(1).dirichlet(np.ones(50), size=4).astype(np.float32)
dists = batch_emd(pts, ctrs)
assert dists.shape == (20, 4)
assert abs(dists[3, 2] - emd_1d(pts[3], ctrs[2])) < 1e-5

# kmeans determinism
r1 = kmeans_emd(pts, K=3, seed=0)
r2 = kmeans_emd(pts, K=3, seed=0)
assert np.array_equal(r1.assignments, r2.assignments)
print('emd_clustering smoke OK')
"

python -c "
import numpy as np
from poker_solver.card import Card
from poker_solver.hunl import Street
from poker_solver.abstraction.equity_features import equity_distribution

# river single-bin
board = [Card.from_str(s) for s in ['As', '7c', '2d', 'Kh', '5s']]
hand = (Card.from_str('Ah'), Card.from_str('Kc'))
hist = equity_distribution(board, hand, Street.RIVER, H=50, mode='exact')
assert hist.shape == (50,)
assert abs(hist.sum() - 1.0) < 1e-6
print('equity_features river smoke OK')
"

# 4. Full test suite must still pass (your work is additive)
pytest -x 2>&1 | tail -20

# 5. Suit-iso smoke (your canonicalization helper)
python -c "
from poker_solver.card import Card
from poker_solver.abstraction.equity_features import canonicalize_for_suit_iso

# Two suit-isomorphic flops should produce the same canonical key.
b1 = [Card.from_str('As'), Card.from_str('7c'), Card.from_str('2d')]
b2 = [Card.from_str('Ah'), Card.from_str('7d'), Card.from_str('2s')]
h1 = (Card.from_str('Kc'), Card.from_str('Qh'))
h2_perm = (Card.from_str('Kd'), Card.from_str('Qs'))  # suit-permuted under the b1→b2 mapping
k1, _ = canonicalize_for_suit_iso(b1, h1)
k2, _ = canonicalize_for_suit_iso(b2, h2_perm)
assert k1 == k2, f'expected canonical equality: {k1} != {k2}'
print('suit-iso smoke OK')
"
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
5. License attributions you added (if any).
