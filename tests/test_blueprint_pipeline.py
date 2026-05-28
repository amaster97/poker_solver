"""Phase 1 blueprint pipeline tests (Premium-A, task #68).

Coverage:
  1. ``BlueprintConfig`` + ``Blueprint`` schema round-trip (serialize/deserialize).
  2. Combo-weighted aggregation correctness (1326 -> 169) with a synthetic
     in-memory strategy where every combo within a class has the same
     probabilities, so the aggregated row must match exactly.
  3. Mixed-strategy aggregation: variant combos within a class converge
     to the per-class average.
  4. Action-label reconstruction for the SB root infoset.
  5. Validator catches malformed strategies (non-canonical class names,
     length mismatches, non-summing rows).
  6. Manifest serialization round-trip.
  7. Filename canonicalization for the three locked ante configs.
  8. Smoke: end-to-end generation against a stub Rust solver — verifies
     the generation pipeline talks correctly to the engine API surface
     without paying real solve cost.
  9. CLI dry-run smoke: ``--dry-run`` produces an empty-but-valid shard
     + manifest end-to-end.
 10. Idempotent re-run: running the same spec twice in a row reuses
     the existing shard and the manifest is consistent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from poker_solver.blueprint import (
    CANONICAL_169_CLASSES,
    SCHEMA_VERSION,
    Blueprint,
    BlueprintConfig,
    HandResolution,
    Manifest,
    ManifestEntry,
    aggregate_to_169_classes,
    blueprint_shard_filename,
    file_sha256,
    generate_blueprint,
    hunl_config_from_blueprint_config,
    load_blueprint,
    load_manifest,
    reconstruct_action_labels_per_infoset,
    save_blueprint,
    save_manifest,
    standard_batch_specs,
    validate_blueprint,
)

# ---------------------------------------------------------------------------
# 1. Schema round-trip
# ---------------------------------------------------------------------------


def test_blueprint_config_dict_round_trip() -> None:
    bc = BlueprintConfig(
        stack_bb=40,
        ante_bb=0.5,
        iterations=1000,
        preflop_open_sizes_bb=(2.5, 3.0, 4.0),
        preflop_reraise_multipliers=(2.0, 3.5, 5.0),
    )
    d = bc.to_dict()
    assert d["stack_bb"] == 40
    assert d["ante_bb"] == 0.5
    assert d["preflop_open_sizes_bb"] == [2.5, 3.0, 4.0]
    round_tripped = BlueprintConfig.from_dict(d)
    assert round_tripped == bc


def test_blueprint_save_load_round_trip(tmp_path: Path) -> None:
    bc = BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=100)
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=bc,
        wall_seconds=12.5,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.05, 0.95],
                    "KK": [0.0, 0.1, 0.9],
                    "72o": [1.0, 0.0, 0.0],
                },
            }
        },
    )
    path = tmp_path / "test_shard.json.gz"
    sha = save_blueprint(bp, path)
    assert path.exists()
    assert len(sha) == 64  # sha256 hex
    loaded = load_blueprint(path)
    assert loaded.schema_version == SCHEMA_VERSION
    assert loaded.config == bc
    assert abs(loaded.wall_seconds - 12.5) < 1e-9
    assert loaded.infosets == bp.infosets
    # The sha returned by save matches file_sha256.
    assert file_sha256(path) == sha


# ---------------------------------------------------------------------------
# 2 + 3. Combo-weighted aggregation
# ---------------------------------------------------------------------------


def _build_uniform_combo_strategy(
    *, class_probs: dict[str, list[float]]
) -> dict[str, list[float]]:
    """Build a 1326-combo strategy where every combo in a class has the
    same probs vector. Used to verify the aggregator preserves class-
    constant strategies exactly.
    """
    from poker_solver.card import Card
    from poker_solver.range_aggregator import _combo_to_hand_class

    ranks = "23456789TJQKA"
    suits = "shdc"
    out: dict[str, list[float]] = {}
    cards = [(r, s) for r in ranks for s in suits]
    for i, (r0, s0) in enumerate(cards):
        for r1, s1 in cards[i + 1 :]:
            c0 = Card.from_str(r0 + s0)
            c1 = Card.from_str(r1 + s1)
            # Sort cards by int to match engine canonicalization.
            from poker_solver.range_aggregator import card_to_int

            i0 = card_to_int(c0)
            i1 = card_to_int(c1)
            hole_str = f"{r0}{s0}{r1}{s1}" if i0 < i1 else f"{r1}{s1}{r0}{s0}"
            cls = _combo_to_hand_class((c0, c1))
            if cls not in class_probs:
                continue
            key = f"{hole_str}||p|"
            out[key] = list(class_probs[cls])
    return out


def test_aggregate_preserves_class_constant_strategies() -> None:
    class_probs = {
        "AA": [0.0, 0.05, 0.95],
        "AKs": [0.1, 0.4, 0.5],
        "72o": [1.0, 0.0, 0.0],
    }
    strategy_1326 = _build_uniform_combo_strategy(class_probs=class_probs)
    out = aggregate_to_169_classes(strategy_1326)
    assert "||p|" in out
    aggregated = out["||p|"]
    for cls, expected in class_probs.items():
        assert cls in aggregated, f"class {cls} missing from aggregate"
        actual = aggregated[cls]
        for a, b in zip(actual, expected, strict=True):
            assert abs(a - b) < 1e-9, f"class {cls}: expected {expected}, got {actual}"


def test_aggregate_averages_within_class() -> None:
    # Two AA combos with different strategies — the aggregated AA row
    # should be the average.
    strategy = {
        # As-Ah and Ks-Kh.
        "AsAh||p|": [0.2, 0.8],
        "AsAd||p|": [0.4, 0.6],
        "AsAc||p|": [0.4, 0.6],
        "AhAd||p|": [0.4, 0.6],
        "AhAc||p|": [0.4, 0.6],
        "AdAc||p|": [0.4, 0.6],
    }
    out = aggregate_to_169_classes(strategy)
    aa = out["||p|"]["AA"]
    # average = (0.2 + 5*0.4) / 6 = 2.2/6
    assert abs(aa[0] - (2.2 / 6.0)) < 1e-9
    assert abs(aa[1] - (3.8 / 6.0)) < 1e-9
    assert abs(sum(aa) - 1.0) < 1e-9


def test_aggregate_handles_empty_input() -> None:
    assert aggregate_to_169_classes({}) == {}


def test_aggregate_groups_by_infoset_history() -> None:
    strategy = {
        "AsAh||p|": [0.0, 1.0],
        "AsAd||p|": [0.0, 1.0],
        "AsAh||p|b300|": [1.0, 0.0],
        "AsAd||p|b300|": [1.0, 0.0],
    }
    out = aggregate_to_169_classes(strategy)
    assert "||p|" in out
    assert "||p|b300|" in out
    assert out["||p|"]["AA"] == [0.0, 1.0]
    assert out["||p|b300|"]["AA"] == [1.0, 0.0]


def test_aggregate_skips_unparseable_keys() -> None:
    # Bad key — should be silently skipped, not crash.
    strategy = {
        "garbage": [0.5, 0.5],
        "AsAh||p|": [0.0, 1.0],
    }
    out = aggregate_to_169_classes(strategy)
    assert "||p|" in out
    assert "AA" in out["||p|"]


# ---------------------------------------------------------------------------
# 4. Action-label reconstruction
# ---------------------------------------------------------------------------


def test_reconstruct_labels_sb_root() -> None:
    # SB root: action_count = 1 (fold) + 1 (call) + len(open_sizes) + 1 (all_in) ?
    # For 100 BB starting stack with open sizes [2,3,4,5]: SB has fold, call,
    # open_to_200, open_to_300, open_to_400, open_to_500, all_in = 7 actions.
    strategy = {"AsAh||p|": [0.0] * 7}
    labels = reconstruct_action_labels_per_infoset(
        strategy,
        preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
        preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
        big_blind=100,
        small_blind=50,
        ante=0,
        starting_stack=10_000,
        preflop_raise_cap=4,
    )
    assert "||p|" in labels
    sb_labels = labels["||p|"]
    assert sb_labels[0] == "fold"
    assert sb_labels[1] == "call"
    assert "all_in" in sb_labels
    # At least one of the open_to_NNN labels (engine uses absolute chips).
    assert any(lab.startswith("open_to_") for lab in sb_labels)


# ---------------------------------------------------------------------------
# 5. Validator
# ---------------------------------------------------------------------------


def test_validate_passes_well_formed_blueprint() -> None:
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=10),
        wall_seconds=0.0,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {"AA": [0.0, 0.1, 0.9], "KK": [0.0, 0.2, 0.8]},
            }
        },
    )
    assert validate_blueprint(bp) == []


def test_validate_catches_non_canonical_class() -> None:
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=10),
        wall_seconds=0.0,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "all_in"],
                "strategy": {"ZZ": [0.0, 1.0]},  # ZZ is not a real class
            }
        },
    )
    warnings = validate_blueprint(bp)
    assert any("non-canonical class label" in w for w in warnings)


def test_validate_catches_length_mismatch() -> None:
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=10),
        wall_seconds=0.0,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "all_in"],
                "strategy": {"AA": [0.5, 0.5]},  # only 2, expected 3
            }
        },
    )
    warnings = validate_blueprint(bp)
    assert any("strategy length 2 != actions length 3" in w for w in warnings)


def test_validate_catches_non_summing_strategy() -> None:
    bp = Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=10),
        wall_seconds=0.0,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "all_in"],
                "strategy": {"AA": [0.3, 0.5]},  # sums to 0.8
            }
        },
    )
    warnings = validate_blueprint(bp, sum_tolerance=1e-3)
    assert any("sum to 0.8" in w for w in warnings)


# ---------------------------------------------------------------------------
# 6. Manifest round-trip
# ---------------------------------------------------------------------------


def test_manifest_round_trip(tmp_path: Path) -> None:
    manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        premium_a_version="v1",
        generated_date_utc="2026-05-28T12:00:00+00:00",
        entries=[
            ManifestEntry(
                stack_bb=40,
                ante_bb=0.0,
                filename="preflop_169class_40bb_anteNone.json.gz",
                sha256="a" * 64,
                file_size_bytes=12345,
                final_exploitability_bb100=None,
                wall_seconds=300.0,
                iterations=25000,
            )
        ],
    )
    path = tmp_path / "manifest.json"
    save_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded == manifest


# ---------------------------------------------------------------------------
# 7. Filename canonicalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ante_bb,expected_token",
    [
        (0.0, "anteNone"),
        (0.5, "anteHalf"),
        (1.0, "anteFull"),
        (0.25, "ante0.25"),
    ],
)
def test_blueprint_shard_filename_canonical(
    ante_bb: float, expected_token: str
) -> None:
    bc = BlueprintConfig(stack_bb=40, ante_bb=ante_bb, iterations=25000)
    fn = blueprint_shard_filename(bc)
    assert fn == f"preflop_169class_40bb_{expected_token}.json.gz"


# ---------------------------------------------------------------------------
# 8. Stub-solver smoke
# ---------------------------------------------------------------------------


def _stub_rust_solver(*args, **kwargs) -> dict:
    """A minimal stand-in for ``_rust.solve_hunl_preflop_rvr`` that
    returns a small synthetic 1326-style strategy (only AA + KK + QQ at
    the SB root).
    """
    return {
        "average_strategy": {
            "AsAh||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "AsAd||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "AsAc||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "AhAd||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "AhAc||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "AdAc||p|": [0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.9],
            "KsKh||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
            "KsKd||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
            "KsKc||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
            "KhKd||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
            "KhKc||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
            "KdKc||p|": [0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.8],
        },
        "iterations": 10,
        "decision_node_count": 1,
        "strategy_entry_count": 12,
        "hand_count_per_player": [1326, 1326],
        "backend": "stub",
    }


def test_generate_blueprint_with_stub_solver(tmp_path: Path) -> None:
    # `_stub_rust_solver` emits 1326-combo keys (matching the hybrid path);
    # the wrapper aggregates them via `aggregate_to_169_classes`. The new
    # True Path B path consumes 169-class keys natively from the engine, so
    # we explicitly opt into the legacy COMBO_1326 mode for this stub.
    config = BlueprintConfig(stack_bb=40, ante_bb=0.0, iterations=10)
    bp = generate_blueprint(
        config,
        rust_solver=_stub_rust_solver,
        hand_resolution=HandResolution.COMBO_1326,
    )
    assert bp.schema_version == SCHEMA_VERSION
    assert bp.config == config
    assert "||p|" in bp.infosets
    aa = bp.infosets["||p|"]["strategy"]["AA"]
    kk = bp.infosets["||p|"]["strategy"]["KK"]
    assert abs(sum(aa) - 1.0) < 1e-9
    assert abs(sum(kk) - 1.0) < 1e-9
    # Round-trip on disk.
    path = tmp_path / "shard.json.gz"
    sha = save_blueprint(bp, path)
    loaded = load_blueprint(path)
    assert loaded.infosets["||p|"]["strategy"]["AA"] == pytest.approx(aa)
    assert loaded.infosets["||p|"]["strategy"]["KK"] == pytest.approx(kk)
    assert validate_blueprint(loaded) == []
    assert sha == file_sha256(path)


# ---------------------------------------------------------------------------
# 9. CLI dry-run smoke
# ---------------------------------------------------------------------------


def test_cli_dry_run_smoke(tmp_path: Path) -> None:
    """``--dry-run`` end-to-end: CLI produces shard files + manifest without
    invoking the engine. Verifies the script's plumbing is correct.
    """
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "generate_preflop_blueprint.py"
    output = tmp_path / "out"
    cmd = [
        sys.executable,
        str(script),
        "--depth",
        "40",
        "--ante",
        "none",
        "--iterations",
        "10",
        "--output",
        str(output),
        "--dry-run",
    ]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    if result.returncode != 0:
        pytest.fail(
            f"CLI dry-run exited {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    manifest_path = output / "manifest.json"
    assert manifest_path.exists()
    with open(manifest_path) as f:
        d = json.load(f)
    assert d["schema_version"] == SCHEMA_VERSION
    assert len(d["shards"]) == 1
    shard_filename = d["shards"][0]["filename"]
    assert shard_filename == "preflop_169class_40bb_anteNone.json.gz"
    shard_path = output / shard_filename
    assert shard_path.exists()
    # Dry-run shard has metadata but empty infosets.
    bp = load_blueprint(shard_path)
    assert bp.schema_version == SCHEMA_VERSION
    assert bp.config.stack_bb == 40
    assert bp.config.ante_bb == 0.0
    assert bp.n_infosets == 0


# ---------------------------------------------------------------------------
# 10. Idempotent re-run
# ---------------------------------------------------------------------------


def test_cli_idempotent_resume(tmp_path: Path) -> None:
    """Running the same spec twice in a row: second run skips the
    already-existing shard.
    """
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "generate_preflop_blueprint.py"
    output = tmp_path / "out"
    cmd = [
        sys.executable,
        str(script),
        "--depth",
        "60",
        "--ante",
        "half",
        "--iterations",
        "10",
        "--output",
        str(output),
        "--dry-run",
    ]
    # First run.
    r1 = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=str(repo_root)
    )
    assert r1.returncode == 0, r1.stderr
    manifest_path = output / "manifest.json"
    assert manifest_path.exists()
    first_manifest = json.loads(manifest_path.read_text())
    assert len(first_manifest["shards"]) == 1

    # Second run — same spec. Should produce SKIP log + identical manifest.
    r2 = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=str(repo_root)
    )
    assert r2.returncode == 0, r2.stderr
    assert "SKIP" in r2.stderr or "SKIP" in r2.stdout
    second_manifest = json.loads(manifest_path.read_text())
    assert second_manifest == first_manifest


# ---------------------------------------------------------------------------
# 11. Standard batch grid
# ---------------------------------------------------------------------------


def test_standard_batch_specs_27_cells() -> None:
    specs = standard_batch_specs()
    assert len(specs) == 27
    depths = {s.stack_bb for s in specs}
    antes = {s.ante_bb for s in specs}
    assert depths == {20, 30, 40, 60, 80, 100, 150, 175, 200}
    assert antes == {0.0, 0.5, 1.0}


def test_hunl_config_construction_from_blueprint_config() -> None:
    bc = BlueprintConfig(stack_bb=40, ante_bb=0.5, iterations=100, preflop_raise_cap=4)
    cfg = hunl_config_from_blueprint_config(bc, chip_per_bb=100)
    assert cfg.starting_stack == 40 * 100  # 4000 cents
    assert cfg.big_blind == 100
    assert cfg.small_blind == 50  # 0.5 BB
    assert cfg.ante == 50  # 0.5 BB
    assert cfg.preflop_raise_cap == 4


def test_canonical_169_classes_complete_and_unique() -> None:
    """Sanity check: 169 classes, 13 pairs + 78 suited + 78 offsuit."""
    assert len(CANONICAL_169_CLASSES) == 169
    assert len(set(CANONICAL_169_CLASSES)) == 169
    pairs = [c for c in CANONICAL_169_CLASSES if len(c) == 2]
    suited = [c for c in CANONICAL_169_CLASSES if c.endswith("s")]
    offsuit = [c for c in CANONICAL_169_CLASSES if c.endswith("o")]
    assert len(pairs) == 13
    assert len(suited) == 78
    assert len(offsuit) == 78


# ---------------------------------------------------------------------------
# 12. HandResolution enum sanity
# ---------------------------------------------------------------------------


def test_hand_resolution_enum_values() -> None:
    assert HandResolution.COMBO_1326.value == "combo_1326"
    assert HandResolution.CLASS_169.value == "class_169"
    # Round-trip through string serialization (used by future JSON config).
    assert HandResolution("class_169") == HandResolution.CLASS_169
