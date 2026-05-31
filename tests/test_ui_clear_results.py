"""Regression tests for ``SolveRunner.clear_results()`` — W2 concurrency hazard.

W2 (HIGH): ``clear_results()`` is invoked from the RESET SPOT / preset-load
handlers (``ui/views/spot_input.py``), which are NOT disabled while a solve is
running — and the preset-load handler is *async*, so its synchronous core can
land AFTER a worker thread has already started. The pre-fix implementation
unconditionally set ``status = "idle"`` and nulled the result fields even with
a LIVE worker thread, producing the toxic ``(status="idle", thread alive)``
state:

  * ``is_running`` (``status in ('running','paused')``) goes False while the
    worker is still alive, so ``start()``'s in-flight guard
    (``if self.is_running: raise SolveInFlightError``) is bypassed and a SECOND
    worker can spawn alongside the orphaned first; and
  * ``'idle'`` is in ``_TERMINAL_STATUSES``, so the next
    ``_reap_finished_worker()`` would ``thread.join(timeout=2.0)`` a LIVE
    worker — violating its "never join a running worker" invariant.

The fix makes ``clear_results()`` cancel + reap any in-flight worker BEFORE
clearing, reusing the existing ``stop()`` / ``join()`` / ``_reap_finished_worker()``
machinery, so the toxic state can never be observed and no worker is orphaned.

These are direct ``SolveRunner`` unit tests (no ``nicegui.testing.User``
needed). They drive the mock-solver path (``mock_latency_ms`` /
``mock_failure_mode`` injection) so they stay fast and never build a real tree.
The repo runs ``asyncio_mode=auto`` but these tests are plain sync functions.
"""

from __future__ import annotations

import threading
import time

import pytest

from poker_solver.hunl import HUNLPoker
from ui.mock_solver import _CANCEL_FLAG, load_fixture
from ui.state import _TERMINAL_STATUSES, SolveInFlightError, SolveRunner


@pytest.fixture(autouse=True)
def _reset_cancel_flag():
    """The mock's module-level cancel flag is shared; clear it around each test
    so one test's ``stop()`` never leaks into the next."""
    _CANCEL_FLAG.clear()
    yield
    _CANCEL_FLAG.clear()


def _start_running_solve(runner: SolveRunner, latency_ms: int = 1000) -> None:
    """Start a mock solve and block until ``is_running`` is observably True.

    A non-zero ``mock_latency_ms`` keeps the worker alive long enough that the
    test can call ``clear_results()`` while the solve is genuinely in flight.
    """
    cfg = load_fixture("flop_k72r_100bb")
    runner.start(
        HUNLPoker(cfg),
        iterations=100_000,
        log_every=50,
        mock_latency_ms=latency_ms,
    )
    # Wait (bounded) until the worker has flipped status to "running".
    deadline = time.time() + 2.0
    while time.time() < deadline and not runner.is_running:
        time.sleep(0.01)
    assert runner.is_running, "precondition: solve must be in flight before clear"
    assert runner.is_alive(), "precondition: worker thread must be alive"


def test_clear_results_never_leaves_idle_with_live_thread() -> None:
    """The core W2 invariant: ``clear_results()`` must never produce a state
    where the status is terminal (e.g. ``'idle'``) while the worker thread is
    still alive — that is the state that bypasses the ``start()`` guard and
    trips the ``_reap`` join-a-live-worker invariant."""
    runner = SolveRunner()
    _start_running_solve(runner)

    runner.clear_results()

    # After clear: the toxic (terminal-status AND live-thread) combination must
    # NOT hold. Either the worker is fully reaped (no live thread) or it is
    # still logically running — never the in-between that bypasses the guard.
    assert not (runner.status in _TERMINAL_STATUSES and runner.is_alive()), (
        f"clear_results left a terminal status {runner.status!r} with a LIVE "
        f"worker thread (is_alive={runner.is_alive()}) — the W2 hazard state."
    )
    # is_running must agree with thread liveness: an idle/terminal runner must
    # have no live worker.
    if runner.status in _TERMINAL_STATUSES:
        assert not runner.is_alive(), (
            "terminal status must imply no live worker thread"
        )
        assert not runner.is_running


def test_clear_results_reaps_worker_and_clears_fields() -> None:
    """Preferred-shape behaviour: clearing during a solve cancels + reaps the
    worker (no orphan) and then nulls the result/route-info fields + sets idle."""
    runner = SolveRunner()
    _start_running_solve(runner)

    t0 = time.time()
    runner.clear_results()
    elapsed = time.time() - t0

    # Cooperative stop lands within one mock snapshot, so the synchronous
    # cancel+reap is fast (well under the join timeout); the UI thread is not
    # blocked for seconds.
    assert elapsed < 5.0, f"clear_results blocked too long ({elapsed:.2f}s)"

    # No orphaned worker: the thread has been joined and dropped.
    assert not runner.is_alive(), "worker thread must be reaped, not orphaned"
    assert runner._thread is None, "worker handle must be dropped after reap"
    assert runner.status == "idle"
    assert not runner.is_running

    # Result / route-info holders are cleared.
    assert runner.result is None
    assert runner.rvr_result is None
    assert runner.nash_result is None
    assert runner.chained_result is None
    assert runner.preflop_chart_result is None
    assert runner.preflop_route_info is None
    assert runner.chained_preflop_route_info is None
    assert runner.chained_postflop_route_info is None


def test_start_after_clear_does_not_spawn_concurrent_worker() -> None:
    """A ``start()`` immediately after ``clear_results()`` must NOT silently
    spawn a second worker alongside an orphaned first.

    With the W2 hazard, the post-clear ``(idle + live-thread)`` state made
    ``is_running`` False (bypassing the in-flight guard) while the first worker
    was still alive, so ``start()`` would launch a second concurrent worker.
    After the fix, the first worker is reaped during ``clear_results()`` so the
    second ``start()`` runs alone."""
    runner = SolveRunner()
    _start_running_solve(runner)

    # Snapshot the live worker thread BEFORE clearing so we can prove it is the
    # one that gets reaped (not left running beside a new one).
    first_thread = runner._thread
    assert isinstance(first_thread, threading.Thread)

    runner.clear_results()
    assert not first_thread.is_alive(), (
        "the original worker must be stopped+joined by clear_results, not "
        "orphaned alongside the next solve"
    )

    # A fresh start must NOT raise the in-flight guard and must run a NEW,
    # single worker. A zero-latency mock finishes near-instantly.
    runner.start(
        HUNLPoker(load_fixture("river_tiny_subgame")),
        iterations=100,
        log_every=10,
        mock_latency_ms=0,
    )
    second_thread = runner._thread
    assert second_thread is not first_thread, "start must spawn a distinct worker"
    runner.join(timeout=5.0)
    # The original worker never came back to life as a concurrent orphan.
    assert not first_thread.is_alive()
    assert runner.status in ("done", "stopped"), (
        f"second solve should reach a terminal status; got {runner.status!r}"
    )


def test_clear_results_on_idle_runner_is_noop_safe() -> None:
    """Calling ``clear_results()`` on a never-started (idle, no thread) runner
    must be safe: no exception, no join attempt, fields nulled, status idle."""
    runner = SolveRunner()
    assert runner._thread is None
    runner.clear_results()  # must not raise / must not try to join a None thread
    assert runner.status == "idle"
    assert not runner.is_alive()
    assert runner.result is None


def test_clear_results_after_solve_finished_clears_terminal_state() -> None:
    """After a solve has *finished* (terminal, thread possibly not yet reaped),
    ``clear_results()`` must still leave a clean (idle, no-live-thread) state —
    not an idle+alive zombie."""
    runner = SolveRunner()
    # Fast successful mock solve.
    runner.start(
        HUNLPoker(load_fixture("river_tiny_subgame")),
        iterations=100,
        log_every=10,
        mock_latency_ms=0,
    )
    runner.join(timeout=5.0)
    assert runner.status == "done"

    runner.clear_results()
    assert runner.status == "idle"
    assert not runner.is_alive()
    assert not (runner.status in _TERMINAL_STATUSES and runner.is_alive())
    assert runner.result is None


def test_inflight_guard_still_fires_for_a_genuine_collision() -> None:
    """Sanity backstop: the W2 fix must not weaken the legitimate in-flight
    guard. Starting a second solve WHILE the first is genuinely running (no
    intervening clear) must still raise ``SolveInFlightError``."""
    runner = SolveRunner()
    _start_running_solve(runner)
    try:
        with pytest.raises(SolveInFlightError):
            runner.start(
                HUNLPoker(load_fixture("river_tiny_subgame")),
                iterations=100,
                log_every=10,
                mock_latency_ms=0,
            )
    finally:
        # Clean up the in-flight worker so the thread doesn't outlive the test.
        runner.clear_results()
    assert not runner.is_alive()
