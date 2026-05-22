"""1-D Earth Mover's Distance + custom NumPy k-means for card-abstraction clustering.

Stage 2 + Stage 3 of the PR 4 pipeline. Pure NumPy, no scipy / sklearn / scikit-learn.

EMD is the 1-D closed-form Wasserstein-1 distance:

    EMD(p, q) = mean(|cumsum(p) - cumsum(q)|)

valid for L1-normalized histograms of identical length. K-means here is Lloyd's
iteration with kmeans++ initialization (architectural pattern from
``references/code/slumbot2019/src/kmeans.cpp::SeedPlusPlus``, MIT; no code copied)
adapted to EMD-on-CDFs instead of squared Euclidean.

All randomness flows through a ``numpy.random.Generator`` seeded from the
``seed`` argument; reruns with identical inputs produce byte-identical outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Chunking guard: limit the (N, K, H) broadcast tensor in :func:`batch_emd`
# to roughly 1 GB so multi-million-row feature matrices do not OOM.
_BATCH_EMD_MAX_FLOATS = 250_000_000  # ~1 GB at float32


def emd_1d(p: np.ndarray, q: np.ndarray) -> float:
    """1-D closed-form Wasserstein-1 (Earth Mover's) distance.

    For L1-normalized histograms ``p`` and ``q`` of identical length ``H``,
    ``EMD(p, q) = mean(|cumsum(p) - cumsum(q)|)``. The ``mean`` divides by
    ``H``, not ``sum``: this normalizes the distance against bin count so
    the maximum (delta-at-0 vs delta-at-(H-1)) approaches but never equals
    1.0 — for H=50 it is ``(H-1)/H = 0.98``.

    Args:
        p: L1-normalized 1-D float array, shape (H,).
        q: L1-normalized 1-D float array, shape (H,).

    Returns:
        Non-negative scalar distance. ``emd_1d(p, p) == 0``; symmetric;
        triangle inequality holds.
    """
    p_arr = np.asarray(p, dtype=np.float64)
    q_arr = np.asarray(q, dtype=np.float64)
    if p_arr.shape != q_arr.shape or p_arr.ndim != 1:
        raise ValueError(
            f"emd_1d expects two 1-D arrays of identical shape; got {p_arr.shape}, "
            f"{q_arr.shape}"
        )
    return float(np.mean(np.abs(np.cumsum(p_arr) - np.cumsum(q_arr))))


def batch_emd(points: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Vectorized 1-D EMD between N points and K centroids.

    Computes ``d[i, j] = emd_1d(points[i], centroids[j])`` for all i, j by
    precomputing both CDFs once and broadcasting the per-bin absolute
    difference, then averaging across the H bin axis.

    For very large N (e.g., 2.3M flop rows × 256 centroids × 50 bins), the
    naive ``|P_cdf[:, None, :] - C_cdf[None, :, :]|`` allocation can exceed
    available memory. The implementation chunks along N so the temporary
    tensor stays under ~1 GB (see ``_BATCH_EMD_MAX_FLOATS``).

    Args:
        points: (N, H) L1-normalized histograms (float32 or float64).
        centroids: (K, H) L1-normalized centroids (float32 or float64).

    Returns:
        (N, K) float32 distance matrix.
    """
    p = np.asarray(points)
    c = np.asarray(centroids)
    if p.ndim != 2 or c.ndim != 2:
        raise ValueError(
            f"batch_emd expects 2-D arrays; got shapes {p.shape}, {c.shape}"
        )
    if p.shape[1] != c.shape[1]:
        raise ValueError(
            f"batch_emd: points H={p.shape[1]} must equal centroids H={c.shape[1]}"
        )
    n, h = p.shape
    k = c.shape[0]
    p_cdf = np.cumsum(p, axis=1).astype(np.float64, copy=False)
    c_cdf = np.cumsum(c, axis=1).astype(np.float64, copy=False)

    # Chunk N to keep |P_cdf_chunk[:, None, :] - C_cdf[None, :, :]| under
    # roughly _BATCH_EMD_MAX_FLOATS scalar elements.
    elems_per_row = max(1, k * h)
    chunk_n = max(1, _BATCH_EMD_MAX_FLOATS // elems_per_row)
    out = np.empty((n, k), dtype=np.float32)
    for start in range(0, n, chunk_n):
        end = min(start + chunk_n, n)
        diff = np.abs(p_cdf[start:end, None, :] - c_cdf[None, :, :])
        out[start:end] = diff.mean(axis=2).astype(np.float32)
    return out


@dataclass
class KMeansResult:
    """Result of :func:`kmeans_emd`.

    Attributes:
        assignments: shape (N,) integer array; ``assignments[i] in [0, K)``.
            Dtype is ``uint8`` when ``K <= 256`` and ``uint16`` otherwise.
        centroids: shape (K, H) float32 array; each row L1-normalized.
        history: per-iteration mean point-to-nearest-centroid EMD distance,
            in order. Length equals the number of iterations actually run
            (``<= max_iter``). A non-increasing sequence (allowing small
            numerical noise) indicates healthy convergence.
    """

    assignments: np.ndarray
    centroids: np.ndarray
    history: list[float] = field(default_factory=list)


def _l1_normalize_rows(arr: np.ndarray) -> np.ndarray:
    """Return a copy of ``arr`` with each row scaled to sum to 1 (float32).

    Rows that sum to 0 (degenerate empty cluster after centroid update) are
    left as uniform 1/H to keep them valid probability distributions; the
    empty-cluster recovery in :func:`kmeans_emd` then re-seeds them.
    """
    out = arr.astype(np.float32, copy=True)
    row_sums = out.sum(axis=1, keepdims=True)
    zero_rows = (row_sums <= 0).squeeze(-1)
    # Avoid divide-by-zero. Zero rows are recovered separately upstream.
    safe_sums = np.where(row_sums <= 0, 1.0, row_sums)
    out = (out / safe_sums).astype(np.float32, copy=False)
    if zero_rows.any():
        h = out.shape[1]
        out[zero_rows] = np.full(h, 1.0 / h, dtype=np.float32)
    return np.asarray(out, dtype=np.float32)


def _kmeans_plusplus_init(
    features: np.ndarray,
    K: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Deterministic kmeans++ initialization on EMD distances.

    Algorithm:
        1. Pick the first centroid uniformly at random from ``features``.
        2. For each subsequent centroid, sample a point with probability
           proportional to ``D(x)^2``, where ``D(x)`` is the EMD distance
           from ``x`` to the nearest already-selected centroid.

    Architectural pattern from ``references/code/slumbot2019/src/kmeans.cpp::
    SeedPlusPlus`` (MIT, attribution: pattern only, no code copied).

    Args:
        features: (N, H) L1-normalized histograms.
        K: number of centroids to select.
        rng: NumPy Generator; ALL randomness flows through this.

    Returns:
        (K, H) array of selected centroids, L1-normalized rows.
    """
    n = features.shape[0]
    if K <= 0:
        raise ValueError(f"K must be positive; got {K}")
    if n < K:
        # Degenerate: every point becomes its own centroid; pad with
        # duplicates of the first point to fill K. This matches Slumbot's
        # ``SingleObjectClusters`` fallback (kmeans.cpp:571).
        idxs = list(range(n)) + [0] * (K - n)
        return _l1_normalize_rows(features[np.array(idxs)])

    chosen_idx = np.empty(K, dtype=np.int64)
    chosen_idx[0] = int(rng.integers(0, n))
    centroids = np.empty((K, features.shape[1]), dtype=np.float32)
    centroids[0] = features[chosen_idx[0]]

    # Squared EMD distance from each point to the nearest already-selected
    # centroid; initialize with distance to the first centroid.
    dists = batch_emd(features, centroids[:1])[:, 0].astype(np.float64)
    sq_dists = dists * dists

    for c in range(1, K):
        total = float(sq_dists.sum())
        if total <= 0.0:
            # All remaining points coincide with selected centroids;
            # fall back to a uniform random pick over unselected indices.
            mask = np.ones(n, dtype=bool)
            mask[chosen_idx[:c]] = False
            unselected = np.flatnonzero(mask)
            if unselected.size == 0:
                # Unreachable: every point being selected requires n == c < K,
                # but the n < K branch at line 167 (above) already handled
                # that case before entering this loop.
                raise AssertionError(
                    "unreachable; n < K degenerate branch handled at line 167"
                )
            chosen_idx[c] = int(rng.choice(unselected))
        else:
            # Sample with probability sq_dists / total. Use ``rng.random()``
            # + cumulative sum for an explicit inverse-CDF draw so the path
            # is independent of NumPy's internal ``choice`` algorithm.
            r = float(rng.random()) * total
            cum = np.cumsum(sq_dists)
            idx = int(np.searchsorted(cum, r, side="right"))
            if idx >= n:
                idx = n - 1
            chosen_idx[c] = idx

        centroids[c] = features[chosen_idx[c]]
        # Update sq_dists to reflect nearest-of-(0..c).
        new_dists = batch_emd(features, centroids[c : c + 1])[:, 0].astype(np.float64)
        new_sq = new_dists * new_dists
        sq_dists = np.minimum(sq_dists, new_sq)
        # The just-selected point has distance 0 — keep it that way explicitly.
        sq_dists[chosen_idx[c]] = 0.0

    return _l1_normalize_rows(centroids)


def kmeans_emd(
    features: np.ndarray,
    K: int,
    seed: int = 42,
    max_iter: int = 200,
    change_tolerance: float = 0.001,
) -> KMeansResult:
    """Lloyd's-iteration k-means with EMD-on-CDFs and kmeans++ seeding.

    Each iteration:

        1. Compute (N, K) EMD distance matrix point-to-centroid.
        2. Assign each point to its argmin centroid.
        3. Update each centroid to the L1-renormalized arithmetic mean of
           its members (per-bin average; matches Slumbot's `kmeans.cpp::Update`).
        4. Recover empty clusters by re-seeding from the farthest point
           under the current centroid set (deterministic; no fresh randomness).
        5. Convergence check: stop if the fraction of points whose assignment
           changed is below ``change_tolerance``, or after ``max_iter``.

    Reproducibility: given ``(features bytes, K, seed)`` the result is
    byte-identical across reruns. All randomness flows through a single
    ``np.random.default_rng(seed)`` used only inside :func:`_kmeans_plusplus_init`.

    Args:
        features: (N, H) L1-normalized histograms (float32 or float64).
        K: target cluster count (must be positive; ``K > N`` triggers the
            "every point its own cluster" fallback).
        seed: RNG seed for initialization.
        max_iter: hard upper bound on iterations (default 200, locked per
            PR 4 spec §7).
        change_tolerance: convergence threshold on the fraction of points
            whose assignment changed (default 0.001 = 0.1%).

    Returns:
        :class:`KMeansResult` with deterministic assignments, centroids,
        and per-iteration mean-distance history.
    """
    if features.ndim != 2:
        raise ValueError(f"features must be 2-D; got shape {features.shape}")
    if K <= 0:
        raise ValueError(f"K must be positive; got {K}")
    n, h = features.shape
    feats_f32 = features.astype(np.float32, copy=False)

    # Dtype for assignments: uint8 fits K up to 256, uint16 otherwise.
    asn_dtype = np.uint8 if K <= 256 else np.uint16

    rng = np.random.default_rng(seed)
    centroids = _kmeans_plusplus_init(feats_f32, K, rng)
    assignments = np.zeros(n, dtype=asn_dtype)
    prev_assignments = np.full(n, fill_value=np.iinfo(asn_dtype).max, dtype=asn_dtype)

    history: list[float] = []

    for it in range(max_iter):
        dists = batch_emd(feats_f32, centroids)  # (N, K)
        new_assignments = dists.argmin(axis=1).astype(asn_dtype)
        min_dists = dists[np.arange(n), new_assignments.astype(np.int64)]

        # Centroid update: per-cluster arithmetic mean, then L1-renormalize.
        sums = np.zeros((K, h), dtype=np.float64)
        counts = np.zeros(K, dtype=np.int64)
        # vectorized accumulation
        np.add.at(sums, new_assignments.astype(np.int64), feats_f32)
        np.add.at(counts, new_assignments.astype(np.int64), 1)
        new_centroids = np.empty_like(centroids)
        nonempty = counts > 0
        if nonempty.any():
            new_centroids[nonempty] = (sums[nonempty] / counts[nonempty, None]).astype(
                np.float32
            )
        # Empty-cluster recovery: re-seed from the farthest point under the
        # CURRENT (about-to-be-replaced) centroid set; no fresh randomness so
        # determinism holds. ``min_dists`` is already the per-point distance
        # to its assigned centroid; picking the global argmax gives the
        # farthest point.
        if (~nonempty).any():
            empty_clusters = np.flatnonzero(~nonempty)
            # We pick distinct farthest points; mask out each as we go to
            # avoid picking the same row twice when multiple clusters are empty.
            available_min_dists = min_dists.astype(np.float64).copy()
            for empty_c in empty_clusters:
                farthest_idx = int(np.argmax(available_min_dists))
                new_centroids[empty_c] = feats_f32[farthest_idx]
                available_min_dists[farthest_idx] = -np.inf
                # Re-assign that point to this cluster so the next iter's
                # centroid update has at least one member.
                new_assignments[farthest_idx] = empty_c

        new_centroids = _l1_normalize_rows(new_centroids)

        # Record the mean point-to-nearest-centroid distance for this iter
        # AFTER the centroid update (the spec wording: "after that iteration's
        # centroid update").
        post_dists = batch_emd(feats_f32, new_centroids)
        post_min = post_dists.min(axis=1)
        history.append(float(post_min.mean()))

        # Convergence: fraction of points whose assignment changed vs prev iter.
        if it == 0:
            # First iteration has no meaningful "changed" baseline; never stop.
            changed_frac = 1.0
        else:
            changed = int(np.sum(new_assignments != prev_assignments))
            changed_frac = changed / n

        prev_assignments = new_assignments
        centroids = new_centroids
        assignments = new_assignments

        if it >= 1 and changed_frac < change_tolerance:
            break

    return KMeansResult(
        assignments=assignments,
        centroids=centroids,
        history=history,
    )
