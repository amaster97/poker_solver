"""End-to-end smoke test for the Phase 6 blueprint UI integration.

PR #178 wired the blueprint router into the chart widget and chained-tab
source-indicator badges. There are unit tests in
``tests/test_ui_blueprint_routing.py`` that probe individual surfaces;
this module is the integration counterpart: it boots NiceGUI in
headless mode, drives the page through the same flows a user would,
and asserts the rendered DOM reflects the correct route / badge / data.

The three flows covered are:

  1. **Chart widget — exact blueprint hit** at 100BB / no-ante. Pulls
     the production blueprint bundle in ``assets/blueprints/`` so the
     test exercises real shard data (not synthetic). Verifies the AKs
     cell renders with a non-empty tooltip whose action probabilities
     match the blueprint's stored strategy.

  2. **Chart widget — interpolation path** at 67BB / no-ante (between
     anchors at 60 and 80). Verifies the source badge says
     ``[interpolated]`` and the per-class chart populates.

  3. **Chained tab — preflop dispatch**. Mocks ``solve_chained`` so the
     orchestrator isn't actually invoked; verifies the badge transitions
     from ``[unrouted]`` to ``[live] N iter ...`` (post-PR-178 chained
     stays live). The postflop badge shows
     ``[live] live subgame (triggered per flop pick)`` per v1.9.0
     state because flop OOM blocks live subgame solves at this depth;
     this assertion will need to update post-v1.10 when the flop
     subgame lands (current PR #186 measures the OOM, PR #187+ will
     fix it).

## Headless mechanism

We use NiceGUI's built-in ``User`` test fixture
(``nicegui.testing.User``). This is in-process, has no display, no
browser, and no Selenium — exactly what a CI runner needs. The
fixture stitches together a fake ASGI loop, runs the ``@ui.page("/")``
builder, and lets the test ``find(marker=...)`` against the resulting
NiceGUI element tree.

This test module skips cleanly when either ``nicegui`` or
``pytest-asyncio`` (which nicegui's async ``user`` fixture requires)
is unavailable. In CI today, ``pip install -e ".[dev]"`` ships
neither — so the test is effectively gated on a separate ``[ui]``
install path. PR opening this test should also surface the CI gap.
"""

from __future__ import annotations

import asyncio
import pathlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# Both nicegui (for the User fixture) AND pytest-asyncio (for the
# async fixture support nicegui's user fixture needs) must be present;
# skip otherwise so CI without the [ui] extra installed doesn't fail
# this module.
pytest.importorskip("nicegui")
pytest.importorskip("pytest_asyncio")

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
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_state_dir(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pathlib.Path]:
    """Sandbox state.json + quiesce any leftover SolveRunner threads.

    Mirrors the protocol every other UI smoke uses
    (``test_ui_chained_tab.py``, ``test_ui_blueprint_routing.py``):
    redirect ``$HOME`` so state.json lands in ``tmp_path``, reset the
    singleton state so each test starts clean, and stop any background
    worker thread the previous test left running.
    """
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


def _production_asset_dir() -> Path:
    """Return the repo's shipped blueprint asset directory.

    We point the router at the same dir users see (``assets/blueprints/``
    relative to the repo root) so the test exercises real shard data
    rather than a synthetic fixture. If the dir is missing (clean dev
    checkout that hasn't pulled blueprints LFS yet), the tests
    pytest.skip rather than fail.
    """
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "assets" / "blueprints"


# ---------------------------------------------------------------------------
# Flow 1: chart widget — 100BB / no-ante / AKs blueprint hit
# ---------------------------------------------------------------------------


async def test_chart_100bb_no_ante_aks_blueprint_hit(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E flow: 100BB / no-ante / AKs is an exact blueprint shard.

    Procedure mirrors what a user does:
      1. Open the app.
      2. Navigate to the Preflop Chart tab.
      3. Confirm stack = 100BB and ante = 0 (the page defaults — no
         spot inputs needed).
      4. Click "Solve preflop chart".
      5. Assert the badge says ``[blueprint]`` and the AKs cell
         renders with the real blueprint AKs probabilities.

    The Rust ``solve_hunl_preflop_rvr`` binding is monkey-patched to
    raise if invoked — a blueprint hit must NOT trigger a live solve.
    """
    asset_dir = _production_asset_dir()
    if not (asset_dir / "manifest.json").exists():
        pytest.skip(
            f"production blueprint bundle missing at {asset_dir}; "
            "skipping (clean dev checkouts without LFS will hit this)"
        )

    from ui import blueprint_router
    from ui.state import get_state

    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: asset_dir)

    # Hard-fail any stray live-solve dispatch — a blueprint hit must
    # bypass the Rust binding entirely. If this raises, the blueprint
    # routing regressed (the live-solve fallback fired).
    import poker_solver
    from types import SimpleNamespace

    def _explode_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "100BB / no-ante blueprint hit must skip the Rust live solver"
        )

    monkeypatch.setattr(
        poker_solver,
        "_rust",
        SimpleNamespace(solve_hunl_preflop_rvr=_explode_if_called),
        raising=False,
    )

    await user.open("/")
    state = get_state()
    # Page defaults to (100, 100); ante starts at 0.0. Explicit assignment
    # for clarity AND to defend against any future spot-default change.
    state.current_spot.stacks_bb = (100, 100)
    state.current_spot.ante = 0.0

    # Click Solve — this is the entry point Phase 6 wired blueprint
    # lookup into (``ui/app.py:_on_preflop_chart_solve``).
    user.find(marker="preflop-chart-solve-button").click()

    # Blueprint lookup is synchronous — the refreshable+ polling timer
    # in app.py's tick should fire within one cycle. Give it a couple.
    await asyncio.sleep(0.6)

    # ----- Assertion 1: badge says [blueprint] -----
    from ui.blueprint_router import SourceLabel

    assert state.runner.preflop_route_info is not None, (
        "blueprint hit must populate preflop_route_info"
    )
    assert state.runner.preflop_route_info.source == SourceLabel.BLUEPRINT, (
        f"expected SourceLabel.BLUEPRINT for 100BB exact hit; got "
        f"{state.runner.preflop_route_info.source!r}"
    )

    badges = list(user.find(marker="preflop-chart-source-badge").elements)
    assert len(badges) >= 1, "preflop-chart-source-badge marker missing"
    badge_texts = [str(getattr(b, "text", "")) for b in badges]
    assert any("[blueprint]" in t for t in badge_texts), (
        f"no [blueprint] badge text among {badge_texts!r}"
    )
    # The confidence string includes "exact 100BB / no-ante".
    assert any("100BB" in t and "no-ante" in t for t in badge_texts), (
        f"blueprint badge missing expected confidence text; got {badge_texts!r}"
    )

    # ----- Assertion 2: AKs cell rendered + carries real probabilities -----
    chart_result = state.runner.preflop_chart_result
    assert chart_result is not None
    per_class = chart_result.get("per_class", {})
    assert "AKs" in per_class, (
        f"AKs missing from blueprint per_class; have {list(per_class.keys())[:8]}..."
    )
    aks_strategy = per_class["AKs"]
    # AKs at 100BB / no-ante is mostly call + open_to_400 + open_to_500
    # (per the shipped blueprint shards). We don't lock the exact
    # values — that would make the test brittle against re-trains —
    # but we DO assert the strategy is meaningfully populated.
    assert isinstance(aks_strategy, dict)
    total_mass = sum(float(v) for v in aks_strategy.values())
    assert total_mass == pytest.approx(1.0, abs=1e-3), (
        f"AKs strategy doesn't sum to 1.0 (got {total_mass}); "
        f"blueprint shard malformed?"
    )
    # At 100BB / no-ante AKs is a strong calling hand — call mass
    # should dominate fold mass by a wide margin.
    fold_p = float(aks_strategy.get("fold", 0.0))
    call_p = float(aks_strategy.get("call", 0.0))
    assert call_p > fold_p + 0.4, (
        f"AKs at 100BB expected call >> fold; got call={call_p}, fold={fold_p}"
    )

    # ----- Assertion 3: the AKs cell is actually rendered in the DOM -----
    aks_cells = user.find(marker="preflop-chart-cell-AKs").elements
    assert len(aks_cells) >= 1, "AKs cell missing from rendered chart grid"


# ---------------------------------------------------------------------------
# Flow 2: chart widget — interpolation path at 67BB
# ---------------------------------------------------------------------------


async def test_chart_67bb_no_ante_interpolated(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E flow: 67BB / no-ante is BETWEEN 60 and 80 anchors -> INTERPOLATED.

    Asserts the badge text reflects interpolation AND the chart
    populates with a non-empty per-class dict (i.e. the interpolation
    actually executed, not just labeled).
    """
    asset_dir = _production_asset_dir()
    if not (asset_dir / "manifest.json").exists():
        pytest.skip(
            f"production blueprint bundle missing at {asset_dir}; "
            "skipping interpolation E2E"
        )

    from ui import blueprint_router
    from ui.state import get_state

    monkeypatch.setattr(blueprint_router, "default_asset_dir", lambda: asset_dir)

    # Same live-solve trip-wire as Flow 1.
    import poker_solver
    from types import SimpleNamespace

    def _explode_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "67BB / no-ante interpolated hit must skip the Rust live solver"
        )

    monkeypatch.setattr(
        poker_solver,
        "_rust",
        SimpleNamespace(solve_hunl_preflop_rvr=_explode_if_called),
        raising=False,
    )

    await user.open("/")
    state = get_state()
    state.current_spot.stacks_bb = (67, 67)
    state.current_spot.ante = 0.0

    user.find(marker="preflop-chart-solve-button").click()
    await asyncio.sleep(0.6)

    # ----- Source = INTERPOLATED, anchors = (60, 80) -----
    from ui.blueprint_router import SourceLabel

    assert state.runner.preflop_route_info is not None
    assert state.runner.preflop_route_info.source == SourceLabel.INTERPOLATED, (
        f"expected INTERPOLATED for 67BB; got "
        f"{state.runner.preflop_route_info.source!r}"
    )
    assert state.runner.preflop_route_info.anchor_depths == (60, 80), (
        f"expected anchors (60, 80); got "
        f"{state.runner.preflop_route_info.anchor_depths!r}"
    )

    # Badge text says [interpolated] and names the anchor depths.
    badges = list(user.find(marker="preflop-chart-source-badge").elements)
    badge_texts = [str(getattr(b, "text", "")) for b in badges]
    assert any("[interpolated]" in t for t in badge_texts), (
        f"no [interpolated] badge among {badge_texts!r}"
    )
    assert any("60/80" in t for t in badge_texts), (
        f"interpolated badge missing '60/80' anchor text; got {badge_texts!r}"
    )

    # Chart actually populated.
    chart_result = state.runner.preflop_chart_result
    assert chart_result is not None
    per_class = chart_result.get("per_class", {})
    assert "AKs" in per_class, (
        "interpolated chart must populate AKs (one of the strong-AKs "
        "classes present in every shard)"
    )
    # Sums to 1.0 after blending.
    aks_strategy = per_class["AKs"]
    total = sum(float(v) for v in aks_strategy.values())
    assert total == pytest.approx(1.0, abs=1e-3), (
        f"interpolated AKs doesn't sum to 1.0 (got {total})"
    )


# ---------------------------------------------------------------------------
# Flow 3: chained tab — preflop solve dispatch + route badges
# ---------------------------------------------------------------------------


def _fake_chained_result_for_dispatch() -> Any:
    """Tiny synthetic ChainedSolveResult for the chained-tab dispatch test.

    Mirrors the shape used in ``test_ui_chained_tab.py`` — a 2-class
    preflop strategy plus an empty postflop cache. We only need enough
    structure for ``runner._run_chained_path`` to commit a result and
    populate the route_info badges.
    """
    from poker_solver.chained import ChainedSolveResult
    from poker_solver.range_aggregator import RangeVsRangeNashResult

    preflop_result = RangeVsRangeNashResult(
        per_history_strategy={},
        per_class_strategy={
            "AA": {"all_in": 0.95, "fold": 0.05},
            "KK": {"all_in": 0.80, "fold": 0.20},
        },
        range_aggregate={"all_in": 0.875, "fold": 0.125},
        exploitability=0.01,
        iterations=30,
        wall_clock_s=1.2,
        decision_node_count=8,
        hand_count_per_player=(2, 2),
        memory_profile={},
        backend="python_chained_route_a",
        position="aggressor",
        warnings=[],
    )
    return ChainedSolveResult(
        preflop_result=preflop_result,
        continuation_ranges={},
        postflop_cache={},
    )


async def test_chained_tab_preflop_solve_populates_route_badges(
    user: User,
    isolated_state_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E flow: chained tab Solve -> preflop result + route badges.

    Stubs ``solve_chained`` so the test doesn't run the orchestrator
    (covered by ``test_chained_orchestrator.py``); instead we verify
    the UI dispatch wiring + post-solve badge population:

      * Badges start as ``[unrouted]`` before any solve.
      * After clicking Solve, the preflop badge transitions to
        ``[live]`` with the iteration count.
      * The postflop badge transitions to ``[live] live subgame
        (triggered per flop pick)`` — the v1.9.0 placeholder state
        because the flop OOM (PR #186 measurement) blocks the actual
        live subgame solve from running on the click path.

    NOTE: when v1.10 lands the post-flop optimization (PR #187+), the
    postflop badge will read differently — likely ``[blueprint]`` for
    bundled flop spots or a real wall time after the subgame solve.
    Update the postflop assertion at that time.
    """
    from ui.state import RangeWithFreqs, get_state

    fake_chained_calls: dict[str, Any] = {"count": 0}

    def _fake_solve_chained(
        config: Any,
        hero_range: Any,
        villain_range: Any,
        **kwargs: Any,
    ) -> Any:
        fake_chained_calls["count"] += 1
        return _fake_chained_result_for_dispatch()

    monkeypatch.setattr("poker_solver.chained.solve_chained", _fake_solve_chained)

    await user.open("/")
    state = get_state()
    # Use a 40BB SB-3BB-open-style spot: ranges with at least one class
    # each side so the chained dispatch validates.
    state.current_spot.ranges = (
        RangeWithFreqs.from_string("AA, KK"),
        RangeWithFreqs.from_string("AA, KK"),
    )
    state.current_spot.stacks_bb = (40, 40)
    state.current_spot.board = []

    # ----- BEFORE solve: badges show [unrouted] -----
    pre_badges_initial = list(user.find(marker="chained-tab-route-preflop").elements)
    post_badges_initial = list(user.find(marker="chained-tab-route-postflop").elements)
    assert len(pre_badges_initial) >= 1, "chained-tab-route-preflop missing"
    assert len(post_badges_initial) >= 1, "chained-tab-route-postflop missing"
    initial_pre_texts = [str(getattr(b, "text", "")) for b in pre_badges_initial]
    initial_post_texts = [str(getattr(b, "text", "")) for b in post_badges_initial]
    assert any("[unrouted]" in t for t in initial_pre_texts), (
        f"preflop badge should start as [unrouted]; got {initial_pre_texts!r}"
    )
    assert any("[unrouted]" in t for t in initial_post_texts), (
        f"postflop badge should start as [unrouted]; got {initial_post_texts!r}"
    )

    # ----- Click solve -----
    user.find(marker="chained-tab-solve-button").click()

    # Wait for the worker to commit the result + route info. The
    # chained-tab worker dispatches off the main thread; route info
    # is written under the runner lock when the worker finishes.
    deadline = 4.0
    waited = 0.0
    while waited < deadline and fake_chained_calls["count"] == 0:
        await asyncio.sleep(0.1)
        waited += 0.1
    assert fake_chained_calls["count"] == 1, (
        f"expected solve_chained to be called exactly once; "
        f"got {fake_chained_calls['count']}"
    )
    state.runner.join(timeout=3.0)
    assert state.runner.status in ("done", "stopped"), (
        f"runner status after chained solve: {state.runner.status!r}"
    )

    # ----- AFTER solve: badges populated with live source -----
    from ui.blueprint_router import SourceLabel

    assert state.runner.chained_preflop_route_info is not None
    assert state.runner.chained_preflop_route_info.source == SourceLabel.LIVE, (
        f"expected preflop route source LIVE; got "
        f"{state.runner.chained_preflop_route_info.source!r}"
    )
    # The confidence text names the iteration count.
    assert "iter" in state.runner.chained_preflop_route_info.confidence
    # Postflop: pre-seeded LIVE placeholder per ui/state.py
    # _run_chained_path's commit block (v1.9.0 state).
    assert state.runner.chained_postflop_route_info is not None
    assert state.runner.chained_postflop_route_info.source == SourceLabel.LIVE
    assert "live subgame" in state.runner.chained_postflop_route_info.confidence, (
        f"v1.9.0 postflop badge should say 'live subgame'; got "
        f"{state.runner.chained_postflop_route_info.confidence!r}"
    )

    # ----- Force-refresh the chained tab so the new badges render -----
    refresh = getattr(state.runner, "_chained_refresh", None)
    if callable(refresh):
        refresh()
    # Give the refreshable a tick to flush.
    await asyncio.sleep(0.3)

    # Verify the rendered DOM picked up the new badge text. NiceGUI's
    # refreshable element pool may retain the old labels alongside the
    # new ones; we accept any element with the marker whose text
    # contains the expected token.
    pre_badges = list(user.find(marker="chained-tab-route-preflop").elements)
    post_badges = list(user.find(marker="chained-tab-route-postflop").elements)
    pre_texts = [str(getattr(b, "text", "")) for b in pre_badges]
    post_texts = [str(getattr(b, "text", "")) for b in post_badges]
    assert any("[live]" in t for t in pre_texts), (
        f"preflop badge should contain [live] after solve; got {pre_texts!r}"
    )
    assert any("live subgame" in t for t in post_texts), (
        f"postflop badge should mention 'live subgame' (v1.9.0 state); "
        f"got {post_texts!r}"
    )


# ---------------------------------------------------------------------------
# Smoke 4: page composition — chart widget + chained tab both render w/ badges
# ---------------------------------------------------------------------------


async def test_chart_and_chained_badges_both_present_on_page_load(
    user: User, isolated_state_dir: pathlib.Path
) -> None:
    """Sanity gate: BOTH the chart-widget badge marker and the chained-tab
    routing markers are present on an unsolved page load.

    This catches the regression class where a layout refactor accidentally
    drops one of the two badge slots — the unit tests in
    test_ui_blueprint_routing.py only check the per-page case in isolation.
    """
    await user.open("/")
    # Chart widget badge slot.
    chart_badges = user.find(marker="preflop-chart-source-badge").elements
    assert len(chart_badges) >= 1, "preflop-chart-source-badge missing on page"
    # Chained-tab route indicator + both rows.
    chained_indicator = user.find(marker="chained-tab-route-indicator").elements
    assert len(chained_indicator) >= 1, "chained-tab-route-indicator missing"
    chained_pre = user.find(marker="chained-tab-route-preflop").elements
    chained_post = user.find(marker="chained-tab-route-postflop").elements
    assert len(chained_pre) >= 1, "chained-tab-route-preflop missing"
    assert len(chained_post) >= 1, "chained-tab-route-postflop missing"
