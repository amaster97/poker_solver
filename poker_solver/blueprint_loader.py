"""Premium-A preflop blueprint loader API (Phase 2, task #68).

This module is the user-facing read path for the blueprint shards
produced by :mod:`poker_solver.blueprint` (Phase 1) and the offline
generator at ``scripts/generate_preflop_blueprint.py``.

Phase 1 ships the *generator* + the on-disk asset format. Phase 2
(this module) ships:

1. **Manifest discovery** — read ``assets/blueprints/manifest.json``
   once at load time, list the available ``(stack_bb, ante_bb)``
   cells without paying disk cost for the actual strategy data.
2. **Lazy shard loading** — gzip-decompress + JSON-parse a shard on
   first lookup, then keep the parsed ``Blueprint`` in memory for the
   process lifetime. The 27-shard target grid fits comfortably in
   memory (each shard is ~0.5-3 MB compressed, ~3-15 MB decompressed),
   so we use a simple unbounded dict cache rather than an LRU.
3. **Clean Python lookup surface** — ``loader.lookup(stack_bb, ante,
   hand, action_history)`` returns the action distribution as a
   ``numpy.ndarray`` (or ``None`` on miss). Action labels are
   available via ``loader.actions(...)``.
4. **Miss-handling hook** — callers can provide ``on_miss`` to plug in
   Phase 3's stack-depth interpolation without this module depending
   on Phase 3.

## Mental model: layered lookup

The blueprint is keyed by ``(stack_bb, ante, history) -> {hand -> probs}``.
Lookups proceed in layers, each of which may miss:

  Layer 1: shard discovery — is there a shard for ``(stack_bb, ante)``
    in the manifest? If no, this is the typical interpolation
    trigger (e.g. user asks for 175 BB but only 150 and 200 are in
    the asset). We hand off to ``on_miss`` if provided.

  Layer 2: infoset discovery — is the ``action_history`` reachable
    from the blueprint root? If no, we return ``None``. Action
    sequences outside the blueprint's action menu (e.g. an open size
    the blueprint doesn't sample) cannot be served from a precomputed
    asset and must fall through to live solve at a higher layer.

  Layer 3: class discovery — does this infoset have a strategy entry
    for ``hand``? If no, return ``None``. All 169 canonical classes
    should be present in well-formed shards, but we don't synthesize
    zeros for absent classes — that hides asset bugs.

## Performance contract

The loader holds a ``dict[BlueprintKey, Blueprint]`` cache. Once a shard
is loaded, lookups walk only Python ``dict`` accesses (one for the
shard cache, one for the infoset, one for the strategy class). The
target perf is **≥ 100k lookups/sec on a warm cache** — verified by
``tests/test_blueprint_loader.py::test_cache_hit_perf``.

## Thread safety

Not thread-safe by default. Concurrent first-lookups on the same shard
will trigger redundant disk reads; callers needing thread-safety should
wrap ``lookup`` in a per-loader lock. The DCFR + UI pipelines that
consume this module are single-threaded today, so we skip the lock
overhead.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from poker_solver.blueprint import (
    SCHEMA_VERSION,
    Blueprint,
    Manifest,
    load_manifest,
)

# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "BlueprintKey",
    "BlueprintLoader",
    "BlueprintLookupError",
    "ManifestMismatchError",
    "OnMissCallback",
    "normalize_action_history",
    "normalize_ante",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BlueprintLookupError(ValueError):
    """Raised on structural errors that callers should fix (bad ante token,
    malformed action history, etc.).

    Distinct from a *miss* — misses return ``None`` so the routing layer
    can route to interpolation or live solve. Errors signal "the caller
    fed us garbage", which is not recoverable.
    """


class ManifestMismatchError(RuntimeError):
    """Raised when a shard's on-disk sha256 disagrees with the manifest."""


# ---------------------------------------------------------------------------
# Ante normalization
# ---------------------------------------------------------------------------

# Authoritative ante token <-> BB mapping. Mirrors the generation script
# (``scripts/generate_preflop_blueprint.py``). The "intuitive" tokens
# users type are normalized to floats internally so shard keys are
# unambiguous even if the user mixes ``"half"`` and ``0.5``.
_ANTE_TOKEN_TO_BB: dict[str, float] = {"none": 0.0, "half": 0.5, "full": 1.0}


def normalize_ante(ante: str | float | int) -> float:
    """Normalize a user ante input to a canonical BB float.

    Accepts ``"none" | "half" | "full"`` (case-insensitive) or a numeric
    value (BB units). Returns the float in BB units.

    >>> normalize_ante("none")
    0.0
    >>> normalize_ante("HALF")
    0.5
    >>> normalize_ante(1.0)
    1.0
    """
    if isinstance(ante, str):
        key = ante.strip().lower()
        if key not in _ANTE_TOKEN_TO_BB:
            raise BlueprintLookupError(
                f"unrecognized ante token {ante!r}; expected one of "
                f"{sorted(_ANTE_TOKEN_TO_BB.keys())} or a float (BB)"
            )
        return _ANTE_TOKEN_TO_BB[key]
    if isinstance(ante, (int, float)):
        v = float(ante)
        if v < 0.0:
            raise BlueprintLookupError(f"ante must be >= 0, got {v}")
        return v
    raise BlueprintLookupError(f"ante must be str|float|int, got {type(ante).__name__}")


# ---------------------------------------------------------------------------
# Action history normalization
# ---------------------------------------------------------------------------


def normalize_action_history(history: str) -> str:
    """Normalize a user-supplied action history string to the infoset key.

    The blueprint stores infoset keys as ``"||p|<history>"``. Users pass
    just the history token suffix, where empty string = SB root.

    Examples:
      ``""``        -> ``"||p|"``           (SB facing BB, no opens yet)
      ``"b250"``    -> ``"||p|b250"``       (BB facing 2.5 BB open)
      ``"b300r700"``-> ``"||p|b300r700"``   (SB facing a 3-bet to 7 BB)
      ``"||p|"``    -> ``"||p|"``           (already prefixed; idempotent)

    The function validates that the token grammar matches the engine's
    history alphabet (``f c x A b<digits> r<digits>``). If the user
    passes a malformed token, raises ``BlueprintLookupError``.
    """
    if not isinstance(history, str):
        raise BlueprintLookupError(
            f"action_history must be str, got {type(history).__name__}"
        )
    body = history[len("||p|") :] if history.startswith("||p|") else history

    # Validate token alphabet. We don't require the sequence to be a
    # valid betting line (that's the engine's job); we just guard against
    # garbage like "fold200" or "garbage". The blueprint either has the
    # infoset or it doesn't, and the caller gets a miss either way.
    i = 0
    while i < len(body):
        c = body[i]
        if c in "fcxA":
            i += 1
        elif c in "br":
            j = i + 1
            while j < len(body) and body[j].isdigit():
                j += 1
            if j == i + 1:
                raise BlueprintLookupError(
                    f"action_history token at offset {i} in {history!r} "
                    f"missing digits after {c!r}"
                )
            i = j
        else:
            raise BlueprintLookupError(
                f"unrecognized action_history character {c!r} at offset {i} "
                f"in {history!r}; expected one of f c x A b<n> r<n>"
            )
    return "||p|" + body


# ---------------------------------------------------------------------------
# Key + types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlueprintKey:
    """Hashable shard identifier ``(stack_bb, ante_bb)``."""

    stack_bb: int
    ante_bb: float

    @classmethod
    def from_user(cls, stack_bb: int, ante: str | float | int) -> BlueprintKey:
        return cls(stack_bb=int(stack_bb), ante_bb=normalize_ante(ante))


#: Callback invoked when a lookup misses at Layer 1 (shard absent from
#: manifest). Signature: ``on_miss(key, hand, history) -> np.ndarray | None``.
#: Phase 3's interpolator plugs in here to satisfy out-of-anchor depths.
OnMissCallback = Callable[
    [BlueprintKey, str, str], np.ndarray | None
]


# ---------------------------------------------------------------------------
# Manifest entry helpers — keyed lookup of the manifest's shard list
# ---------------------------------------------------------------------------


def _ante_keys_match(a: float, b: float) -> bool:
    """Whether two ante-BB values refer to the same shard cell.

    The on-disk manifest stores ante as a float (0.0 / 0.5 / 1.0 today,
    possibly arbitrary in the future). User input may have been
    normalized via ``normalize_ante`` from a string token, so we
    compare with a tight tolerance.
    """
    return math.isclose(a, b, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------


@dataclass
class BlueprintLoader:
    """Lazy, cached loader for the Premium-A preflop blueprint assets.

    Typical use:

    >>> loader = BlueprintLoader.from_dir("assets/blueprints/")  # doctest: +SKIP
    >>> probs = loader.lookup(
    ...     stack_bb=40, ante="none", hand="AA", action_history=""
    ... )  # doctest: +SKIP

    The loader holds:
      - ``manifest`` — parsed once at ``from_dir``.
      - ``asset_dir`` — path to the directory holding shards + manifest.
      - ``_shard_cache`` — populated lazily on first lookup per shard.
      - ``verify_sha256`` — toggle for SHA verification (default True;
        disable for low-latency unit tests against synthetic shards).
    """

    asset_dir: Path
    manifest: Manifest
    verify_sha256: bool = True
    #: Internal cache: ``BlueprintKey -> Blueprint``. Populated lazily.
    _shard_cache: dict[BlueprintKey, Blueprint] = field(
        default_factory=dict, repr=False
    )
    #: Cache of which shards we've verified the SHA of. We verify at most
    #: once per process per shard.
    _sha_verified: set[BlueprintKey] = field(default_factory=set, repr=False)

    # -- Construction -------------------------------------------------------

    @classmethod
    def from_dir(
        cls, asset_dir: str | Path, *, verify_sha256: bool = True
    ) -> BlueprintLoader:
        """Construct a loader from a directory containing ``manifest.json``.

        Args:
            asset_dir: Path to the directory holding ``manifest.json`` and
                the per-shard ``.json.gz`` files.
            verify_sha256: If True (default), each shard's on-disk sha256
                is checked against the manifest on first load. Set False
                to skip SHA verification — useful for fast unit tests
                against synthetic shards but disabled-by-default in
                production to detect bit-rot or corrupt downloads.

        Raises:
            FileNotFoundError: if ``manifest.json`` is missing.
            json.JSONDecodeError / KeyError: if the manifest is malformed.
        """
        asset_dir = Path(asset_dir)
        manifest_path = asset_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"manifest.json not found in {asset_dir}; expected at "
                f"{manifest_path}"
            )
        manifest = load_manifest(manifest_path)
        # Sanity: schema version.
        if manifest.schema_version != SCHEMA_VERSION:
            raise ManifestMismatchError(
                f"manifest schema_version={manifest.schema_version!r} != "
                f"loader expected {SCHEMA_VERSION!r}; rebuild the blueprint "
                "asset bundle or upgrade poker_solver"
            )
        return cls(
            asset_dir=asset_dir,
            manifest=manifest,
            verify_sha256=verify_sha256,
        )

    # -- Public discovery --------------------------------------------------

    def available_keys(self) -> list[BlueprintKey]:
        """Return every (stack_bb, ante_bb) cell present in the manifest.

        Useful for UI dropdowns + Phase 3 interpolation anchor selection.
        Order matches the manifest's on-disk order (typically depth-major,
        ante-minor).
        """
        return [
            BlueprintKey(stack_bb=e.stack_bb, ante_bb=e.ante_bb)
            for e in self.manifest.entries
        ]

    def available_depths(self, ante: str | float | int | None = None) -> list[int]:
        """Return the sorted unique stack depths in BB.

        If ``ante`` is given, restrict to shards matching that ante.
        Otherwise return depths across all antes.
        """
        depths: set[int] = set()
        if ante is None:
            for e in self.manifest.entries:
                depths.add(e.stack_bb)
        else:
            target = normalize_ante(ante)
            for e in self.manifest.entries:
                if _ante_keys_match(e.ante_bb, target):
                    depths.add(e.stack_bb)
        return sorted(depths)

    def has_shard(self, stack_bb: int, ante: str | float | int) -> bool:
        """Whether a shard for ``(stack_bb, ante)`` is in the manifest."""
        try:
            target = normalize_ante(ante)
        except BlueprintLookupError:
            return False
        for e in self.manifest.entries:
            if e.stack_bb == int(stack_bb) and _ante_keys_match(e.ante_bb, target):
                return True
        return False

    # -- Internal: shard load ---------------------------------------------

    def _find_manifest_entry(self, key: BlueprintKey) -> Any | None:
        """Find the manifest entry for a shard key, or None."""
        for e in self.manifest.entries:
            if e.stack_bb == key.stack_bb and _ante_keys_match(e.ante_bb, key.ante_bb):
                return e
        return None

    def _load_shard(self, key: BlueprintKey) -> Blueprint:
        """Load a shard from disk, verify SHA (if enabled), cache it.

        On cache hit, returns the cached Blueprint without disk I/O.
        On cache miss, reads + parses + caches. Raises FileNotFoundError
        if the shard's filename (per the manifest) isn't on disk, or
        ManifestMismatchError if the SHA disagrees with the manifest.
        """
        cached = self._shard_cache.get(key)
        if cached is not None:
            return cached
        entry = self._find_manifest_entry(key)
        if entry is None:
            raise FileNotFoundError(
                f"no manifest entry for blueprint key {key}; "
                f"available depths: {self.available_depths()}"
            )
        # Resolve the shard path. The generation pipeline writes to
        # ``blueprint_shard_filename(config)``, which the manifest also
        # records as ``entry.filename`` — trust the manifest's filename
        # so we honor renames cleanly.
        path = self.asset_dir / entry.filename
        if not path.exists():
            raise FileNotFoundError(
                f"manifest entry {entry.filename} not found on disk in "
                f"{self.asset_dir}; the asset bundle is incomplete"
            )
        # Parse the shard.
        with gzip.open(path, "rb") as f:
            raw = f.read()
        payload = json.loads(raw.decode("utf-8"))
        bp = Blueprint.from_dict(payload)

        # Verify SHA if requested and we haven't already.
        if self.verify_sha256 and key not in self._sha_verified:
            # We compute the SHA over the *serialized* representation of
            # the Blueprint's to_dict() — matching the generator's
            # ``save_blueprint`` and ``file_sha256``. This avoids
            # depending on gzip header bytes, which are non-deterministic.
            payload_str = json.dumps(bp.to_dict(), sort_keys=False, separators=(",", ":"))
            sha = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
            if sha != entry.sha256:
                raise ManifestMismatchError(
                    f"sha256 mismatch for {entry.filename}: "
                    f"on-disk={sha} manifest={entry.sha256}; "
                    "the asset bundle is corrupt or stale"
                )
            self._sha_verified.add(key)

        # Cache + return.
        self._shard_cache[key] = bp
        return bp

    def is_shard_loaded(self, stack_bb: int, ante: str | float | int) -> bool:
        """Whether a shard has been pulled into memory yet.

        Used by ``tests/test_blueprint_loader.py`` to assert lazy-load
        semantics — the loader must not read a shard until the first
        lookup against it.
        """
        try:
            key = BlueprintKey.from_user(stack_bb, ante)
        except BlueprintLookupError:
            return False
        return key in self._shard_cache

    # -- Lookups -----------------------------------------------------------

    def lookup(
        self,
        *,
        stack_bb: int,
        ante: str | float | int,
        hand: str,
        action_history: str = "",
        on_miss: OnMissCallback | None = None,
    ) -> np.ndarray | None:
        """Return action probabilities for ``(hand, history)`` at the cell.

        Returns:
            ``np.ndarray`` of action probabilities (length matches the
            infoset's action list), OR ``None`` if any of:
              - the shard is not in the manifest (and ``on_miss`` is
                ``None`` or returns ``None``)
              - the action_history is not a reachable infoset in the
                shard
              - the hand class has no strategy entry at that infoset

        Args:
            stack_bb: Effective stack depth in BB (integer).
            ante: ``"none" | "half" | "full"`` or a float BB value.
            hand: 169-class label (e.g. ``"AA"``, ``"AKs"``, ``"72o"``).
            action_history: Engine token sequence (``"" | "b200" | ...``).
                Empty = SB root decision.
            on_miss: Optional callback invoked on Layer-1 misses (shard
                absent from manifest). Allows Phase 3 interpolation to
                hook in without this module depending on Phase 3.

        Raises:
            BlueprintLookupError: on caller-facing input errors (bad ante
                token, malformed history). Note: a *missing* shard /
                infoset / class is a soft miss (returns ``None``), not
                an error.
        """
        # Layer 0: normalize inputs.
        key = BlueprintKey.from_user(stack_bb, ante)
        history_key = normalize_action_history(action_history)

        # Layer 1: shard discovery.
        if not self.has_shard(stack_bb, key.ante_bb):
            # Hand off to the miss callback if provided.
            if on_miss is not None:
                return on_miss(key, hand, history_key)
            return None

        # Layer 1.5: shard load (lazy, cached).
        bp = self._load_shard(key)

        # Layer 2: infoset discovery.
        info = bp.infosets.get(history_key)
        if info is None:
            return None

        # Layer 3: class discovery.
        strategy_map = info.get("strategy", {})
        probs = strategy_map.get(hand)
        if probs is None:
            return None

        return np.asarray(probs, dtype=np.float64)

    def actions(
        self,
        *,
        stack_bb: int,
        ante: str | float | int,
        action_history: str = "",
    ) -> list[str] | None:
        """Return the action labels for an infoset, or ``None`` on miss.

        Useful for UI code that wants to render "fold / call / open_to_300"
        instead of bare indices. The label list aligns with the strategy
        vector returned by :meth:`lookup`.
        """
        key = BlueprintKey.from_user(stack_bb, ante)
        history_key = normalize_action_history(action_history)
        if not self.has_shard(stack_bb, key.ante_bb):
            return None
        bp = self._load_shard(key)
        info = bp.infosets.get(history_key)
        if info is None:
            return None
        labels = info.get("actions")
        if labels is None:
            return None
        return list(labels)

    # -- Cache management --------------------------------------------------

    def cache_size(self) -> int:
        """Number of shards currently loaded into memory."""
        return len(self._shard_cache)

    def clear_cache(self) -> None:
        """Drop all cached shards. The next lookup will re-read from disk."""
        self._shard_cache.clear()
        self._sha_verified.clear()

    def preload_all(self) -> None:
        """Eagerly load every shard listed in the manifest.

        Use when latency matters more than memory (e.g. a long-running
        UI session). The default policy is lazy.
        """
        for key in self.available_keys():
            self._load_shard(key)
