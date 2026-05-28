"""Phase 2 blueprint loader tests (Premium-A, task #68).

Coverage:
  1. Manifest discovery — ``available_keys`` / ``available_depths`` /
     ``has_shard`` reflect the manifest exactly without loading any
     shards.
  2. Lazy load — ``is_shard_loaded`` is False until the first lookup
     against that shard, then True. Loading shard A must not pull in
     shard B.
  3. Lookup round-trip — produce a synthetic blueprint, save it, load
     it via ``BlueprintLoader``, assert the strategy vector matches.
  4. Cache hit — second lookup on the same shard does not re-read
     disk (monkeypatch ``gzip.open``).
  5. Miss handling — out-of-manifest stack depth returns ``None`` (or
     invokes ``on_miss`` callback). Malformed action history raises
     ``BlueprintLookupError``. Unknown hand class returns ``None``.
     Unknown infoset (history not reachable) returns ``None``.
  6. SHA verification — corrupting a shard's on-disk content raises
     ``ManifestMismatchError`` when ``verify_sha256=True``. With
     ``verify_sha256=False``, the corrupted shard loads silently.
  7. Action labels — ``loader.actions(...)`` returns the per-infoset
     action list.
  8. Ante normalization — ``"none"``, ``"half"``, ``"full"``, and
     numeric values all resolve to the same shard.
  9. Perf — warm-cache lookups exceed 100k/sec.
 10. Smoke against the real assets if present — ensures we work
     against the actual blueprints produced by Phase 1.5.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from poker_solver.blueprint import (
    SCHEMA_VERSION,
    Blueprint,
    BlueprintConfig,
    Manifest,
    ManifestEntry,
    blueprint_shard_filename,
    save_blueprint,
    save_manifest,
)
from poker_solver.blueprint_loader import (
    BlueprintKey,
    BlueprintLoader,
    BlueprintLookupError,
    ManifestMismatchError,
    normalize_action_history,
    normalize_ante,
)

# ---------------------------------------------------------------------------
# Synthetic-shard fixture builder
# ---------------------------------------------------------------------------


def _synthetic_blueprint(
    stack_bb: int = 40,
    ante_bb: float = 0.0,
    *,
    iterations: int = 100,
) -> Blueprint:
    """Build a minimal valid blueprint for unit tests.

    Two infosets, three hand classes each, action vectors that sum to 1.0
    by construction. Avoids the engine entirely.
    """
    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(
            stack_bb=stack_bb,
            ante_bb=ante_bb,
            iterations=iterations,
        ),
        wall_seconds=0.5,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "open_to_300", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.0, 0.7, 0.3],
                    "KK": [0.0, 0.1, 0.6, 0.3],
                    "72o": [1.0, 0.0, 0.0, 0.0],
                },
            },
            "||p|b300": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.4, 0.6],
                    "KK": [0.0, 0.5, 0.5],
                    "72o": [1.0, 0.0, 0.0],
                },
            },
        },
    )


def _write_blueprint_bundle(
    tmp_path: Path,
    blueprints: list[Blueprint],
    *,
    sabotage_sha: bool = False,
) -> Path:
    """Materialize a manifest + shards in ``tmp_path``.

    If ``sabotage_sha`` is True, append an extra byte to one of the
    shards on disk after the manifest has been written — exercises the
    SHA-mismatch path.
    """
    entries: list[ManifestEntry] = []
    paths: dict[str, Path] = {}
    for bp in blueprints:
        fname = blueprint_shard_filename(bp.config)
        path = tmp_path / fname
        sha = save_blueprint(bp, path)
        entries.append(
            ManifestEntry(
                stack_bb=bp.config.stack_bb,
                ante_bb=bp.config.ante_bb,
                filename=fname,
                sha256=sha,
                file_size_bytes=path.stat().st_size,
                final_exploitability_bb100=bp.final_exploitability_bb100,
                wall_seconds=bp.wall_seconds,
                iterations=bp.config.iterations,
            )
        )
        paths[fname] = path
    manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        premium_a_version="v1",
        generated_date_utc="2026-05-28T00:00:00+00:00",
        entries=entries,
    )
    save_manifest(manifest, tmp_path / "manifest.json")
    if sabotage_sha:
        # Corrupt the first shard by writing a *valid but different*
        # blueprint to it: a structurally-valid Blueprint with an empty
        # infosets dict. Its serialized SHA differs from what the
        # manifest recorded, so the loader's verification must fire.
        first_entry = entries[0]
        bogus = Blueprint(
            schema_version=SCHEMA_VERSION,
            config=BlueprintConfig(
                stack_bb=first_entry.stack_bb,
                ante_bb=first_entry.ante_bb,
                iterations=first_entry.iterations,
            ),
            wall_seconds=0.0,
            final_exploitability_bb100=None,
            infosets={},
        )
        save_blueprint(bogus, paths[first_entry.filename])
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Manifest discovery
# ---------------------------------------------------------------------------


def test_from_dir_reads_manifest(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [
            _synthetic_blueprint(stack_bb=20, ante_bb=0.0),
            _synthetic_blueprint(stack_bb=40, ante_bb=0.5),
        ],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    assert loader.manifest.schema_version == SCHEMA_VERSION
    assert len(loader.manifest.entries) == 2
    # No shards loaded yet (lazy).
    assert loader.cache_size() == 0


def test_from_dir_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="manifest.json not found"):
        BlueprintLoader.from_dir(tmp_path)


def test_available_keys_and_depths(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [
            _synthetic_blueprint(stack_bb=20, ante_bb=0.0),
            _synthetic_blueprint(stack_bb=20, ante_bb=0.5),
            _synthetic_blueprint(stack_bb=40, ante_bb=0.0),
        ],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    assert loader.available_depths() == [20, 40]
    assert loader.available_depths(ante="none") == [20, 40]
    assert loader.available_depths(ante="half") == [20]
    assert loader.available_depths(ante="full") == []
    keys = loader.available_keys()
    assert len(keys) == 3
    assert BlueprintKey(stack_bb=20, ante_bb=0.0) in keys
    assert BlueprintKey(stack_bb=40, ante_bb=0.0) in keys


def test_has_shard(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.5)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    assert loader.has_shard(40, "half") is True
    assert loader.has_shard(40, 0.5) is True
    assert loader.has_shard(40, "none") is False
    assert loader.has_shard(50, "half") is False
    # Bad ante token does not raise — returns False.
    assert loader.has_shard(40, "quarter") is False


# ---------------------------------------------------------------------------
# 2. Lazy load
# ---------------------------------------------------------------------------


def test_lazy_load_not_triggered_by_construction(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [
            _synthetic_blueprint(stack_bb=20, ante_bb=0.0),
            _synthetic_blueprint(stack_bb=40, ante_bb=0.0),
        ],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    # Nothing loaded yet.
    assert not loader.is_shard_loaded(20, "none")
    assert not loader.is_shard_loaded(40, "none")
    # First lookup triggers a load of only that shard.
    loader.lookup(stack_bb=20, ante="none", hand="AA", action_history="")
    assert loader.is_shard_loaded(20, "none")
    assert not loader.is_shard_loaded(40, "none")
    # Lookup against the other shard then loads it.
    loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    assert loader.is_shard_loaded(40, "none")


def test_preload_all_loads_every_shard(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [
            _synthetic_blueprint(stack_bb=20, ante_bb=0.0),
            _synthetic_blueprint(stack_bb=40, ante_bb=0.5),
        ],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    loader.preload_all()
    assert loader.cache_size() == 2


# ---------------------------------------------------------------------------
# 3. Lookup round-trip
# ---------------------------------------------------------------------------


def test_lookup_round_trip(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    probs = loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    assert probs is not None
    assert isinstance(probs, np.ndarray)
    np.testing.assert_allclose(probs, [0.0, 0.0, 0.7, 0.3])
    probs2 = loader.lookup(
        stack_bb=40, ante="none", hand="72o", action_history="b300"
    )
    assert probs2 is not None
    np.testing.assert_allclose(probs2, [1.0, 0.0, 0.0])


def test_lookup_actions_round_trip(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    actions = loader.actions(stack_bb=40, ante="none", action_history="")
    assert actions == ["fold", "call", "open_to_300", "all_in"]
    actions2 = loader.actions(stack_bb=40, ante="none", action_history="b300")
    assert actions2 == ["fold", "call", "all_in"]


def test_lookup_history_already_prefixed_idempotent(tmp_path: Path) -> None:
    """Passing ``"||p|"`` instead of ``""`` is accepted and returns the same."""
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    a = loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    b = loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="||p|")
    assert a is not None and b is not None
    np.testing.assert_allclose(a, b)


# ---------------------------------------------------------------------------
# 4. Cache hit (no redundant disk read)
# ---------------------------------------------------------------------------


def test_cache_hit_does_not_re_read_disk(tmp_path: Path, monkeypatch) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    # First lookup -> loads from disk.
    loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    # Now monkeypatch gzip.open to fail loudly if called again.
    import poker_solver.blueprint_loader as bpm

    def _no_gzip(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("gzip.open should not be called on a cache hit")

    monkeypatch.setattr(bpm.gzip, "open", _no_gzip)
    # Second lookup must NOT touch gzip.open.
    probs = loader.lookup(stack_bb=40, ante="none", hand="KK", action_history="")
    assert probs is not None


# ---------------------------------------------------------------------------
# 5. Miss handling
# ---------------------------------------------------------------------------


def test_lookup_miss_returns_none(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)

    # Unknown stack depth.
    assert (
        loader.lookup(stack_bb=175, ante="none", hand="AA", action_history="") is None
    )
    # Unknown ante (manifest only has 0.0).
    assert (
        loader.lookup(stack_bb=40, ante="half", hand="AA", action_history="") is None
    )
    # Unknown infoset (history not reachable in the synthetic shard).
    assert (
        loader.lookup(
            stack_bb=40, ante="none", hand="AA", action_history="b777"
        )
        is None
    )
    # Unknown hand class (not in the strategy of that infoset).
    assert (
        loader.lookup(
            stack_bb=40, ante="none", hand="QJs", action_history=""
        )
        is None
    )


def test_on_miss_callback_invoked_on_layer1_miss(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    captured: dict = {}

    def _interpolate(key, hand, history):
        captured["key"] = key
        captured["hand"] = hand
        captured["history"] = history
        return np.asarray([0.25, 0.25, 0.5])

    probs = loader.lookup(
        stack_bb=175,
        ante="none",
        hand="AA",
        action_history="b300",
        on_miss=_interpolate,
    )
    assert probs is not None
    np.testing.assert_allclose(probs, [0.25, 0.25, 0.5])
    assert captured["key"] == BlueprintKey(stack_bb=175, ante_bb=0.0)
    assert captured["hand"] == "AA"
    assert captured["history"] == "||p|b300"


def test_on_miss_not_invoked_on_layer2_or_layer3_miss(tmp_path: Path) -> None:
    """on_miss is only for missing-shard cases, not missing-infoset/class."""
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    called = [False]

    def _interp(key, hand, history):
        called[0] = True
        return np.asarray([0.0])

    # Layer 2 miss — unknown infoset in a present shard.
    out = loader.lookup(
        stack_bb=40,
        ante="none",
        hand="AA",
        action_history="b777",
        on_miss=_interp,
    )
    assert out is None
    assert called[0] is False

    # Layer 3 miss — known infoset, missing hand class.
    out = loader.lookup(
        stack_bb=40,
        ante="none",
        hand="QJs",
        action_history="",
        on_miss=_interp,
    )
    assert out is None
    assert called[0] is False


def test_malformed_history_raises(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    with pytest.raises(BlueprintLookupError):
        loader.lookup(
            stack_bb=40, ante="none", hand="AA", action_history="fold200"
        )
    with pytest.raises(BlueprintLookupError):
        # "b" with no digits
        loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="b")
    with pytest.raises(BlueprintLookupError):
        loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="garbage")


def test_bad_ante_raises(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    with pytest.raises(BlueprintLookupError):
        loader.lookup(
            stack_bb=40, ante="quarter", hand="AA", action_history=""
        )
    with pytest.raises(BlueprintLookupError):
        loader.lookup(stack_bb=40, ante=-1.0, hand="AA", action_history="")


# ---------------------------------------------------------------------------
# 6. SHA verification
# ---------------------------------------------------------------------------


def test_sha_mismatch_raises_when_verifying(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
        sabotage_sha=True,
    )
    loader = BlueprintLoader.from_dir(tmp_path, verify_sha256=True)
    with pytest.raises(ManifestMismatchError, match="sha256 mismatch"):
        loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")


def test_sha_skip_when_verification_disabled(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
        sabotage_sha=True,
    )
    loader = BlueprintLoader.from_dir(tmp_path, verify_sha256=False)
    # No SHA check -> the corrupted shard loads silently with whatever
    # the (different) contents say. The sabotaged shard's infosets dict
    # is empty, so this lookup is a Layer-2 miss.
    out = loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    assert out is None


# ---------------------------------------------------------------------------
# 7. Ante normalization
# ---------------------------------------------------------------------------


def test_ante_normalization_token_vs_float(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.5)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    a = loader.lookup(stack_bb=40, ante="half", hand="AA", action_history="")
    b = loader.lookup(stack_bb=40, ante=0.5, hand="AA", action_history="")
    c = loader.lookup(stack_bb=40, ante="HALF", hand="AA", action_history="")
    assert a is not None and b is not None and c is not None
    np.testing.assert_allclose(a, b)
    np.testing.assert_allclose(a, c)


def test_normalize_ante_function() -> None:
    assert normalize_ante("none") == 0.0
    assert normalize_ante("half") == 0.5
    assert normalize_ante("full") == 1.0
    assert normalize_ante("HALF") == 0.5
    assert normalize_ante(0.0) == 0.0
    assert normalize_ante(2) == 2.0
    with pytest.raises(BlueprintLookupError):
        normalize_ante("quarter")
    with pytest.raises(BlueprintLookupError):
        normalize_ante(-1.0)


def test_normalize_action_history_function() -> None:
    assert normalize_action_history("") == "||p|"
    assert normalize_action_history("b200") == "||p|b200"
    assert normalize_action_history("b200r400c") == "||p|b200r400c"
    assert normalize_action_history("||p|") == "||p|"
    assert normalize_action_history("||p|b200") == "||p|b200"
    # All-in token.
    assert normalize_action_history("A") == "||p|A"
    with pytest.raises(BlueprintLookupError):
        normalize_action_history("b")
    with pytest.raises(BlueprintLookupError):
        normalize_action_history("xyz")


# ---------------------------------------------------------------------------
# 8. Perf — warm-cache lookups
# ---------------------------------------------------------------------------


def test_cache_hit_perf(tmp_path: Path) -> None:
    """Warm-cache lookups must exceed 100k/sec.

    The contract from the subplan is sub-100ms per lookup; we set a much
    tighter bar to catch regressions. On an M-series macbook the
    achievable rate is comfortably above 500k/sec; we leave headroom
    for CI runner variability.
    """
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    # Prime the cache.
    loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    n = 50_000
    start = time.perf_counter()
    for _ in range(n):
        probs = loader.lookup(
            stack_bb=40, ante="none", hand="AA", action_history=""
        )
        assert probs is not None
    elapsed = time.perf_counter() - start
    rate = n / elapsed
    print(f"\nCache hit rate: {rate:,.0f} lookups/sec ({elapsed*1e6/n:.2f} us each)")
    assert rate >= 100_000, (
        f"Cache hit perf regressed: {rate:,.0f}/sec < 100,000/sec target"
    )


# ---------------------------------------------------------------------------
# 9. Cache management
# ---------------------------------------------------------------------------


def test_clear_cache_forces_reload(tmp_path: Path) -> None:
    _write_blueprint_bundle(
        tmp_path,
        [_synthetic_blueprint(stack_bb=40, ante_bb=0.0)],
    )
    loader = BlueprintLoader.from_dir(tmp_path)
    loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    assert loader.cache_size() == 1
    loader.clear_cache()
    assert loader.cache_size() == 0
    # Re-lookup populates cache again.
    loader.lookup(stack_bb=40, ante="none", hand="AA", action_history="")
    assert loader.cache_size() == 1


# ---------------------------------------------------------------------------
# 10. Smoke against real assets (skip if missing)
# ---------------------------------------------------------------------------


def _real_asset_dir() -> Path | None:
    """Locate the real assets/blueprints/ directory shipped with the repo."""
    here = Path(__file__).resolve().parent.parent
    candidate = here / "assets" / "blueprints"
    if not (candidate / "manifest.json").exists():
        return None
    return candidate


def test_real_asset_smoke() -> None:
    asset_dir = _real_asset_dir()
    if asset_dir is None:
        pytest.skip("real assets/blueprints/ not present in this checkout")
    loader = BlueprintLoader.from_dir(asset_dir)
    # Pick any (depth, ante) listed in the manifest and pull a lookup.
    keys = loader.available_keys()
    assert keys, "real manifest has no shards"
    key = keys[0]
    probs = loader.lookup(
        stack_bb=key.stack_bb,
        ante=key.ante_bb,
        hand="AA",
        action_history="",
    )
    # The blueprint always has a strategy for AA at the SB root.
    assert probs is not None
    assert isinstance(probs, np.ndarray)
    assert abs(float(probs.sum()) - 1.0) < 1e-4
