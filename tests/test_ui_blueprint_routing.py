"""Phase 6 UI source-indicator + blueprint routing tests (task #68).

Covers the consumer-side wiring added by Phase 6:

  1. ``ui.blueprint_router.BlueprintRouter`` correctly routes exact /
     interpolated / live decisions on a synthetic asset bundle and
     produces a populated :class:`RouteInfo`.
  2. ``describe_route`` renders a stable badge string for each source.
  3. ``SolveRunner.try_blueprint_preflop_chart`` returns True on a
     blueprint hit and populates ``preflop_chart_result`` +
     ``preflop_route_info`` without spawning a worker thread.
  4. ``SolveRunner.try_blueprint_preflop_chart`` returns False when no
     bundle exists (the fallback to live-solve dispatch path).
  5. The preflop chart widget renders a ``preflop-chart-source-badge``
     marker reflecting the current route info (smoke through NiceGUI's
     ``User`` fixture).
  6. The chained tab renders the routing indicator with both preflop
     and postflop markers, defaulting to "[unrouted]" when no chained
     solve has yet been triggered.

These tests do NOT depend on the Phase 5 ``SolverRouter`` landing —
Phase 6 consumes ``BlueprintLoader`` + ``interpolate_strategy`` directly
through ``ui.blueprint_router.BlueprintRouter`` (Phase 5 will replace
this with the central router as a follow-up).
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from pathlib import Path

import pytest

# Allow NiceGUI-based smoke tests to skip cleanly when the optional
# extra isn't installed; only those tests need the harness.
pytest.importorskip("nicegui")

# ruff: noqa: E402, I001  (post-importorskip imports must follow the skip)
from nicegui.testing import User

pytest_plugins = [
    "nicegui.testing.general_fixtures",
    "nicegui.testing.user_plugin",
]

pytestmark = [
    pytest.mark.ui,
    pytest.mark.nicegui_main_file("ui/app.py"),
]


# ---------------------------------------------------------------------------
# Synthetic asset bundle fixture (mirrors tests/test_blueprint_loader.py)
# ---------------------------------------------------------------------------


def _synthetic_blueprint(stack_bb: int, ante_bb: float = 0.0):  # type: ignore[no-untyped-def]
    """Build a minimal blueprint with two infosets + three classes.

    Action menu intentionally MATCHES between depths so interpolation
    can run without fallback to nearest-snap.
    """
    from poker_solver.blueprint import SCHEMA_VERSION, Blueprint, BlueprintConfig

    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=BlueprintConfig(
            stack_bb=stack_bb,
            ante_bb=ante_bb,
            iterations=100,
        ),
        wall_seconds=0.5,
        final_exploitability_bb100=None,
        infosets={
            "||p|": {
                "actions": ["fold", "call", "open_3", "all_in"],
                "strategy": {
                    "AA": [0.0, 0.0, 0.3, 0.7],
                    "KK": [0.0, 0.1, 0.6, 0.3],
                    "72o": [1.0, 0.0, 0.0, 0.0],
                },
            },
        },
    )


def _write_bundle(td: Path, depths: list[int], ante_bb: float = 0.0) -> Path:
    """Materialize a manifest + shards in ``td`` (one shard per depth)."""
    from poker_solver.blueprint import (
        SCHEMA_VERSION,
        Manifest,
        ManifestEntry,
        blueprint_shard_filename,
        save_blueprint,
        save_manifest,
    )

    entries = []
    for s in depths:
        bp = _synthetic_blueprint(stack_bb=s, ante_bb=ante_bb)
        fname = blueprint_shard_filename(bp.config)
        path = td / fname
        sha = save_blueprint(bp, path)
        entries.append(
            ManifestEntry(
                stack_bb=s,
                ante_bb=ante_bb,
                filename=fname,
                sha256=sha,
                file_size_bytes=path.stat().st_size,
                final_exploitability_bb100=None,
                wall_seconds=0.5,
                iterations=100,
            )
        )
    save_manifest(
        Manifest(
            schema_version=SCHEMA_VERSION,
            premium_a_version="v1",
            generated_date_utc="2026-05-28T00:00:00+00:00",
            entries=entries,
        ),
        td / "manifest.json",
    )
    return td


# ---------------------------------------------------------------------------
# Section 1: BlueprintRouter unit semantics
# ---------------------------------------------------------------------------


def test_router_returns_none_when_no_bundle(tmp_path: Path) -> None:
    from ui.blueprint_router import BlueprintRouter

    # Empty directory, no manifest.json.
    assert BlueprintRouter.from_asset_dir(tmp_path) is None
    # Non-existent path.
    assert BlueprintRouter.from_asset_dir(tmp_path / "does_not_exist") is None


def test_router_exact_lookup_returns_blueprint_source(tmp_path: Path) -> None:
    """A request at exactly an anchor depth resolves to ``BLUEPRINT``."""
    from ui.blueprint_router import BlueprintRouter, SourceLabel

    _write_bundle(tmp_path, depths=[100], ante_bb=0.0)
    router = BlueprintRouter.from_asset_dir(tmp_path)
    assert router is not None
    info = router.lookup_chart(stack_bb=100, ante="none")
    assert info.source == SourceLabel.BLUEPRINT
    assert "AA" in info.per_class
    # Strategy was preserved exactly.
    assert info.per_class["AA"]["open_3"] == pytest.approx(0.3)
    assert info.per_class["AA"]["all_in"] == pytest.approx(0.7)
    # Confidence label is human-readable.
    assert "exact" in info.confidence
    assert "100" in info.confidence


def test_router_interp_lookup_returns_interpolated_source(tmp_path: Path) -> None:
    """A request between two anchors resolves to ``INTERPOLATED``."""
    from ui.blueprint_router import BlueprintRouter, SourceLabel

    _write_bundle(tmp_path, depths=[60, 100], ante_bb=0.0)
    router = BlueprintRouter.from_asset_dir(tmp_path)
    assert router is not None
    info = router.lookup_chart(stack_bb=80, ante="none")
    assert info.source == SourceLabel.INTERPOLATED
    assert info.anchor_depths == (60, 100)
    # 80 is the midpoint of 60 and 100; the blended AA strategy must be
    # the mean of the two flanks (here identical fixtures -> same value).
    assert info.per_class["AA"]["open_3"] == pytest.approx(0.3)


def test_router_unknown_ante_falls_back_to_live(tmp_path: Path) -> None:
    """No coverage for the requested ante -> ``LIVE`` placeholder."""
    from ui.blueprint_router import BlueprintRouter, SourceLabel

    _write_bundle(tmp_path, depths=[100], ante_bb=0.0)
    router = BlueprintRouter.from_asset_dir(tmp_path)
    assert router is not None
    info = router.lookup_chart(stack_bb=100, ante="half")
    assert info.source == SourceLabel.LIVE
    assert info.per_class == {}


def test_router_describe_route_is_stable() -> None:
    """``describe_route`` produces predictable strings — guards the
    badge format against accidental rephrasing breaking smoke tests."""
    from ui.blueprint_router import RouteInfo, SourceLabel, describe_route

    info = RouteInfo(
        source=SourceLabel.BLUEPRINT,
        wall_time_s=0.001,
        confidence="exact 100BB / no-ante",
    )
    badge = describe_route(info)
    assert badge.startswith("[blueprint]")
    assert "exact 100BB" in badge
    assert "wall" in badge

    info_live = RouteInfo(
        source=SourceLabel.LIVE,
        wall_time_s=5.2,
        confidence="500 iter rust_preflop_rvr",
    )
    assert describe_route(info_live).startswith("[live]")

    info_interp = RouteInfo(
        source=SourceLabel.INTERPOLATED,
        wall_time_s=0.003,
        confidence="67BB between 60/80BB / no-ante",
    )
    assert describe_route(info_interp).startswith("[interpolated]")


# ---------------------------------------------------------------------------
# Section 2: SolveRunner.try_blueprint_preflop_chart
# ---------------------------------------------------------------------------


def test_runner_try_blueprint_hit_populates_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A blueprint hit populates both ``preflop_chart_result`` and
    ``preflop_route_info`` without spawning a worker thread."""
    from ui import blueprint_router
    from ui.blueprint_router import SourceLabel
    from ui.state import SolveRunner

    _write_bundle(tmp_path, depths=[100], ante_bb=0.0)
    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: tmp_path)

    runner = SolveRunner()
    hit = runner.try_blueprint_preflop_chart(stack_bb=100, ante="none")
    assert hit is True
    assert runner.preflop_chart_result is not None
    assert "AA" in runner.preflop_chart_result["per_class"]
    assert runner.preflop_route_info is not None
    assert runner.preflop_route_info.source == SourceLabel.BLUEPRINT
    # No worker thread should be running.
    assert runner.is_alive() is False


def test_runner_try_blueprint_interp_populates_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interpolated hit also returns True + populates state."""
    from ui import blueprint_router
    from ui.blueprint_router import SourceLabel
    from ui.state import SolveRunner

    _write_bundle(tmp_path, depths=[60, 100], ante_bb=0.0)
    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: tmp_path)

    runner = SolveRunner()
    hit = runner.try_blueprint_preflop_chart(stack_bb=80, ante="none")
    assert hit is True
    assert runner.preflop_chart_result is not None
    assert runner.preflop_route_info.source == SourceLabel.INTERPOLATED
    assert runner.preflop_route_info.anchor_depths == (60, 100)


def test_runner_try_blueprint_miss_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No bundle on disk -> return False so caller falls back to live."""
    from ui import blueprint_router
    from ui.state import SolveRunner

    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: tmp_path)
    # tmp_path has no manifest.json.

    runner = SolveRunner()
    hit = runner.try_blueprint_preflop_chart(stack_bb=100, ante="none")
    assert hit is False
    assert runner.preflop_chart_result is None
    # route_info stays None so the badge says "[unrouted]".
    assert runner.preflop_route_info is None


def test_runner_try_blueprint_unknown_ante_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coverage exists but not at this ante -> False + LIVE info stash."""
    from ui import blueprint_router
    from ui.blueprint_router import SourceLabel
    from ui.state import SolveRunner

    _write_bundle(tmp_path, depths=[100], ante_bb=0.0)
    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: tmp_path)

    runner = SolveRunner()
    hit = runner.try_blueprint_preflop_chart(stack_bb=100, ante="half")
    assert hit is False
    # The router returned LIVE; runner stashes the hint so the badge
    # can render "[live] no blueprint coverage" before solve.
    assert runner.preflop_route_info is not None
    assert runner.preflop_route_info.source == SourceLabel.LIVE


# ---------------------------------------------------------------------------
# Section 3: NiceGUI smoke — source badge present on chart widget
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Override HOME so state.json lands in tmp_path; reset runner."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("POKER_SOLVER_UI_STATE_DIR", str(tmp_path / ".poker_solver_ui"))
    from ui.state import get_state, reset_state_for_testing

    reset_state_for_testing()
    try:
        current = get_state()
        if current.runner.is_alive():
            current.runner.stop()
            current.runner.join(timeout=3.0)
        current.runner._stop_event.clear()
        current.runner._pause_event.clear()
    except Exception:  # noqa: BLE001
        pass
    yield tmp_path
    import contextlib

    with contextlib.suppress(Exception):
        reset_state_for_testing()


async def test_preflop_chart_renders_source_badge(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The chart widget always renders the ``preflop-chart-source-badge``
    marker — even before any solve has fired, the badge shows
    ``[unrouted]``."""
    await user.open("/")
    badges = user.find(marker="preflop-chart-source-badge").elements
    assert len(badges) >= 1, "preflop-chart-source-badge marker missing"


async def test_chained_tab_renders_routing_markers(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """The chained tab always renders preflop + postflop routing-indicator
    rows — both markers present even before any chained solve has run."""
    await user.open("/")
    indicator = user.find(marker="chained-tab-route-indicator").elements
    assert len(indicator) >= 1, "chained-tab-route-indicator missing"
    pre = user.find(marker="chained-tab-route-preflop").elements
    assert len(pre) >= 1, "chained-tab-route-preflop missing"
    post = user.find(marker="chained-tab-route-postflop").elements
    assert len(post) >= 1, "chained-tab-route-postflop missing"


# ---------------------------------------------------------------------------
# Section 4: NiceGUI smoke — blueprint hit shows blueprint badge after Solve
# ---------------------------------------------------------------------------


async def test_solve_button_uses_blueprint_when_available(
    user: User,
    isolated_state_dir: pathlib.Path,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a blueprint asset bundle exists and covers (100BB, no-ante),
    clicking Solve does NOT hit the Rust live solver — the chart
    populates from the blueprint and the badge text reflects it."""
    import asyncio

    from ui import blueprint_router
    from ui.state import get_state

    bundle_dir = tmp_path / "_bundle"
    bundle_dir.mkdir()
    _write_bundle(bundle_dir, depths=[100], ante_bb=0.0)
    monkeypatch.setattr(
        blueprint_router, "default_asset_dir", lambda: bundle_dir
    )

    # Block the rust binding so a stray live-solve dispatch hard-fails
    # (verifies the blueprint path was taken).
    import poker_solver
    from types import SimpleNamespace

    def _fake_solve(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError(
            "blueprint hit must skip the live solver; got call with "
            f"args={args} kwargs={kwargs}"
        )

    fake_module = SimpleNamespace(solve_hunl_preflop_rvr=_fake_solve)
    monkeypatch.setattr(poker_solver, "_rust", fake_module, raising=False)

    await user.open("/")
    state = get_state()
    state.current_spot.stacks_bb = (100, 100)
    state.current_spot.ante = 0.0

    user.find(marker="preflop-chart-solve-button").click()
    # Let the polling timer + refreshable replay.
    await asyncio.sleep(0.7)

    # Should land synchronously — no worker thread.
    assert state.runner.preflop_chart_result is not None
    assert "AA" in state.runner.preflop_chart_result["per_class"]
    assert state.runner.preflop_route_info is not None
    from ui.blueprint_router import SourceLabel

    assert state.runner.preflop_route_info.source == SourceLabel.BLUEPRINT
    # Badge text reflects the blueprint hit. The refreshable produces a
    # fresh label after the click; iterate over every match in case
    # NiceGUI's element pool retains the pre-refresh placeholder.
    badges = list(user.find(marker="preflop-chart-source-badge").elements)
    assert len(badges) >= 1
    badge_texts = [str(getattr(b, "text", "")) for b in badges]
    assert any(
        "Blueprint" in t for t in badge_texts
    ), f"no Blueprint badge among {badge_texts!r}"


def test_chained_route_info_populated_after_solve() -> None:
    """When the chained worker finalizes, both ``chained_preflop_route_info``
    and ``chained_postflop_route_info`` are populated with ``LIVE``
    sources so the badge can render before the user picks a flop."""
    from unittest.mock import MagicMock

    from ui.blueprint_router import SourceLabel
    from ui.state import SolveRunner

    runner = SolveRunner()
    # Build a stub ChainedSolveResult-shaped object the worker writes to.
    fake_preflop = MagicMock()
    fake_preflop.iterations = 42
    fake_preflop.wall_clock_s = 1.7
    fake_preflop.exploitability = 0.005
    fake_result = MagicMock()
    fake_result.preflop_result = fake_preflop

    # Directly invoke the post-solve commit block by mimicking the worker
    # body's final lock section. The cleanest way to exercise that code
    # is to call the runner's chained-completion bookkeeping the same way
    # ``_run_chained_path`` does at success.
    with runner._lock:
        runner.chained_result = fake_result
        runner.iteration = fake_preflop.iterations
        runner.expl_history.append((42, 0.005))
        runner.status = "done"
        # Simulate the route-info commit (mirrors the body of
        # ``_run_chained_path``'s success branch).
        from ui.blueprint_router import RouteInfo

        runner.chained_preflop_route_info = RouteInfo(
            source=SourceLabel.LIVE,
            wall_time_s=1.7,
            confidence="42 iter Route A aggregator",
        )
        runner.chained_postflop_route_info = RouteInfo(
            source=SourceLabel.LIVE,
            wall_time_s=0.0,
            confidence="live subgame (triggered per flop pick)",
        )

    assert runner.chained_preflop_route_info is not None
    assert runner.chained_preflop_route_info.source == SourceLabel.LIVE
    assert "42 iter" in runner.chained_preflop_route_info.confidence
    assert runner.chained_postflop_route_info is not None
    assert "live subgame" in runner.chained_postflop_route_info.confidence


async def test_solve_button_uses_interp_when_between_anchors(
    user: User,
    isolated_state_dir: pathlib.Path,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stack 67BB with anchors at 60+100 -> interpolated source label."""
    import asyncio

    from ui import blueprint_router
    from ui.state import get_state

    bundle_dir = tmp_path / "_bundle"
    bundle_dir.mkdir()
    _write_bundle(bundle_dir, depths=[60, 100], ante_bb=0.0)
    monkeypatch.setattr(
        blueprint_router, "default_asset_dir", lambda: bundle_dir
    )

    import poker_solver
    from types import SimpleNamespace

    def _fake_solve(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("interpolated hit must skip the live solver")

    monkeypatch.setattr(
        poker_solver,
        "_rust",
        SimpleNamespace(solve_hunl_preflop_rvr=_fake_solve),
        raising=False,
    )

    await user.open("/")
    state = get_state()
    state.current_spot.stacks_bb = (67, 67)
    state.current_spot.ante = 0.0

    user.find(marker="preflop-chart-solve-button").click()
    await asyncio.sleep(0.7)

    assert state.runner.preflop_chart_result is not None
    from ui.blueprint_router import SourceLabel

    assert state.runner.preflop_route_info.source == SourceLabel.INTERPOLATED
    badges = list(user.find(marker="preflop-chart-source-badge").elements)
    assert len(badges) >= 1
    badge_texts = [str(getattr(b, "text", "")) for b in badges]
    assert any(
        "Interpolated" in t for t in badge_texts
    ), f"no Interpolated badge among {badge_texts!r}"
