"""HUNL preflop solver orchestration (Python reference tier — PR 9).

PR 9 closes the public OSS preflop gap: most open-source NLHE solvers are
postflop-only because preflop turns the C(52,2) * C(50,2) = 1,624,350 hole-
combo chance node into a tractability nightmare. This module solves the
**preflop subgame** case — preflop where the hole cards are already fixed,
i.e. "deal-then-solve" mode. That covers:

  - The standard `--hole AhAd --hole-opp KsKc` interactive solve.
  - The full preflop tree with a fixed-range opening shape (caller draws hole
    cards from the range, calls this once per hand, aggregates).
  - The downstream postflop-refinement entry (PR 10b consumes
    `PreflopSolveResult` to drive UI).

Dispatch composition (PR 9 §6 canonical, locked by `solver.solve()`):

  1. push/fold short-circuit (PR 3.5 — ≤15 BB HUNL preflop → chart). Stays
     authoritative; this module is NEVER reached for ≤15 BB configs.
  2. HUNL postflop branch (PR 5 / PR 6 — postflop tree solver).
  3. **HUNL preflop branch (PR 9 — this module)** — 15 BB < stack ≤ 250 BB.

Stack-depth contract: preflop is tractable only when hole cards are fixed
(no preflop chance enum). The full enumerated preflop tree (1.6M hole-card
chance branches per node) is intractable; PR 9 explicitly does NOT attempt
it. Callers that want full preflop solve compose: per-hand-class call this
function, aggregate via reach-weighted average (Pluribus blueprint pattern,
post-v1 stretch).

License posture: original implementation; no third-party code derivation.
Inspired by the orchestration pattern in `poker_solver/hunl_solver.py`
(PR 5) which is itself inspired by `noambrown_poker_solver` (MIT) — no
code copied.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.card import Card
from poker_solver.dcfr import DCFRSolver
from poker_solver.equity import equity as compute_equity
from poker_solver.evaluator import evaluate
from poker_solver.hunl import HUNLConfig, HUNLPoker, HUNLState, Street
from poker_solver.hunl_solver import HUNLSolveResult, OnProgressFn, ShouldStopFn
from poker_solver.profiler.memory import MemoryProbe, MemoryReport
from poker_solver.pushfold import PUSHFOLD_MAX_BB, is_pushfold_mode
from poker_solver.solver import exploitability


class PreflopSubgameGame(HUNLPoker):
    """HUNL preflop with **postflop runouts collapsed to equity-based leaves**.

    The full HUNL preflop tree includes the postflop board chance nodes
    (flop = C(50,3) ≈ 19,600 combos; turn = 47; river = 46). Multiplied
    by the preflop action sequence depth, this is intractable without a
    card abstraction (PR 4) and a postflop solver (PR 5). PR 9's preflop
    tier instead **substitutes equity** at the moment preflop closes:
    once the betting round ends and we would transition to FLOP, we
    treat the state as terminal with utility = (equity-weighted pot
    delta). This is the canonical "leaf-value oracle" pattern used in
    depth-limited solving (Brown & Sandholm 2018, "Depth-Limited Solving
    for Imperfect-Information Games").

    For all-in lines this approximation is **exact** — no postflop
    decisions remain, so equity is the true expected utility. For limp /
    flat-call lines it is **inexact** — it bakes in the assumption that
    both players check down postflop. This is a known approximation and
    is documented in the PR 9 spec; the closed-form sanity tests
    (AA vs anything; push/fold edge stacks) target the all-in regime
    where the approximation is exact.

    Implementation: subclass `HUNLPoker` and override `apply` to detect
    the FLOP transition; convert that branch into a SHOWDOWN-terminal
    state whose contributions = the matched pot. `utility()` then runs
    the exact-enumeration equity calculation on the dealt hole cards.

    For UX, an **exhaustive enumeration cache** memoizes equity per
    (hole_cards_pair, partial_board) pair — DCFR walks the same leaf
    millions of times across iterations, but the equity is constant.
    """

    def __init__(
        self,
        config: HUNLConfig,
        equity_cache: dict[tuple[tuple[int, int, int, int], tuple[int, ...]], float]
        | None = None,
    ) -> None:
        super().__init__(config)
        # Cache key: ((p0_c0, p0_c1, p1_c0, p1_c1), partial_board_as_ints).
        # Value: P0 equity (0.0..1.0). P1 equity = 1 - P0 equity - 0 (ties
        # split half each, so we store P0's equity-as-fractional-value:
        # 1.0 = sure win, 0.5 = exactly tied, 0.0 = sure loss).
        self._equity_cache: dict[
            tuple[tuple[int, int, int, int], tuple[int, ...]], float
        ] = equity_cache if equity_cache is not None else {}

    def is_terminal(self, state: HUNLState) -> bool:
        # Base game's terminals: fold or full showdown.
        if super().is_terminal(state):
            return True
        # The "about to enter postflop" frontier comes in two flavors:
        #
        # (a) Normal preflop close → street advances to FLOP with
        #     pending_board_deals = 3, empty board, cur_player = -1.
        # (b) All-in preflop close → `_begin_street_transition` keeps
        #     `street == PREFLOP` (since the if-any-all-in branch fires
        #     before the `Street(int(flushed.street) + 1)` line) and
        #     starts dealing one card at a time with pending = 1.
        #
        # Both flavors share: cur_player == -1, hole_cards dealt,
        # len(board) < 5, pending_board_deals > 0, no fold, both
        # contributions matched (otherwise we'd still be in betting).
        # We claim ANY such "about to deal a board card on a non-showdown
        # frontier with matched contributions" state as terminal and
        # substitute the equity leaf.
        return bool(
            state.cur_player == -1
            and state.hole_cards
            and len(state.board) < 5
            and state.pending_board_deals > 0
            and not any(state.folded)
            and state.to_call == 0
        )

    def utility(self, state: HUNLState) -> tuple[float, float]:
        # Fold case + full-showdown case: delegate to base.
        if any(state.folded) or state.street == Street.SHOWDOWN:
            return super().utility(state)
        # Equity-leaf case: matched contributions, runout pending. Compute
        # equity-weighted utility in BB units (matching HUNLPoker's contract).
        bb = state.config.big_blind
        c0, c1 = state.contributions
        # Pot is what each player put in (which should be equal — preflop
        # closed with matched bets). The equity-weighted EV for P0 is:
        #   EV_p0 = pot * eq_p0 - c0    (P0 wins `pot * eq_p0` chips on
        #   average; P0 paid c0).
        # In zero-sum BB units, P1's EV is -P0's EV.
        # (Side pots from unequal contributions don't apply: by construction
        # this leaf is only entered when c0 == c1 - if one player is short-
        # stacked + all-in, the base game would have set folded=True for
        # the over-bet side at apply-time, or set both all_in=True and we
        # would still get here with c0 != c1. Handle the c0 != c1 case
        # explicitly: P0 risks min(c0, c1), the excess is returned
        # uncontested.)
        risk = min(c0, c1)
        pot = 2 * risk  # contested chips
        # Hole cards are integer-keyed; build the cache key in canonical
        # ordering (sort hole cards within each player's pair for stability).
        hole = state.hole_cards
        # Narrow the tuple shape for mypy + add a runtime guard. The leaf is
        # only reached when both players' hole cards are fixed (PR 9 subgame
        # entry: HUNLConfig.initial_hole_cards is required). An empty
        # `hole_cards` tuple here would be a programming error.
        assert len(hole) == 2, "leaf reached without both players' hole cards"
        p0_cards, p1_cards = hole
        assert len(p0_cards) == 2 and len(p1_cards) == 2, (
            "leaf reached with malformed hole cards"
        )
        p0h: tuple[int, int] = tuple(  # type: ignore[assignment]
            sorted(
                [
                    p0_cards[0].rank * 4 + p0_cards[0].suit,
                    p0_cards[1].rank * 4 + p0_cards[1].suit,
                ]
            )
        )
        p1h: tuple[int, int] = tuple(  # type: ignore[assignment]
            sorted(
                [
                    p1_cards[0].rank * 4 + p1_cards[0].suit,
                    p1_cards[1].rank * 4 + p1_cards[1].suit,
                ]
            )
        )
        board_key = tuple(sorted(c.rank * 4 + c.suit for c in state.board))
        cache_key = (p0h + p1h, board_key)
        eq_p0 = self._equity_cache.get(cache_key)
        if eq_p0 is None:
            eq_p0 = _compute_p0_equity(p0_cards, p1_cards, state.board)
            self._equity_cache[cache_key] = eq_p0
        # P0's expected chip win: pot * eq_p0 - risk (paid 'risk', wins
        # 'pot' fraction eq_p0 of the time). Convert to BB units.
        ev_p0_chips = pot * eq_p0 - risk
        return (ev_p0_chips / bb, -ev_p0_chips / bb)

    def current_player(self, state: HUNLState) -> int:
        if self.is_terminal(state):
            return -1
        return state.cur_player

    def chance_outcomes(self, state: HUNLState) -> list[tuple[int, float]]:
        # If we've collapsed this state to terminal, return empty (no
        # chance children below it).
        if self.is_terminal(state):
            return []
        return super().chance_outcomes(state)


def _compute_p0_equity(
    p0_hole: tuple[Card, Card],
    p1_hole: tuple[Card, Card],
    partial_board: tuple[Card, ...],
) -> float:
    """P0's equity (win + 0.5*tie share) given fixed hole + partial board.

    Exhaustive enumeration via `equity()` with `iterations=0` (forces
    enumeration when board completions are <= enum_threshold). Partial
    boards of length 0/3/4/5 are all in scope; for empty board, the
    enumeration count is C(48, 5) = 1,712,304 — too large for the default
    enum threshold, so we fall back to MC with enough iterations for
    ~0.1% standard error.

    Returns:
        Float in [0.0, 1.0]: P0's fractional equity (1.0 = always wins,
        0.5 = pure tie, 0.0 = always loses; ties contribute 0.5).
    """
    used = set(p0_hole) | set(p1_hole) | set(partial_board)
    remaining_count = 52 - len(used)
    n_to_deal = 5 - len(partial_board)
    from math import comb

    total_runouts = comb(remaining_count, n_to_deal) if n_to_deal > 0 else 1
    if total_runouts == 1:
        # Board complete; deterministic showdown.
        full_board = list(partial_board)
        r0 = evaluate(list(p0_hole) + full_board)
        r1 = evaluate(list(p1_hole) + full_board)
        if r0 > r1:
            return 1.0
        if r1 > r0:
            return 0.0
        return 0.5
    # Use exact enumeration if feasible; else MC at 100k samples.
    # The exact equity calculator handles both modes (auto-dispatch via
    # `enum_threshold`).
    enum_threshold = max(total_runouts + 1, 200_000)
    iters_mc = max(100_000, total_runouts)
    results = compute_equity(
        [list(p0_hole), list(p1_hole)],
        board=list(partial_board) if partial_board else None,
        iterations=iters_mc,
        enum_threshold=enum_threshold,
    )
    return float(results[0].equity)


@dataclass
class PreflopSolveResult(HUNLSolveResult):
    """SolveResult plus per-street memory + a `mode` discriminator.

    Subclasses `HUNLSolveResult` so PR 11 library mode + downstream
    consumers can rely on `isinstance(result, SolveResult)` and on the
    `memory_report` field.

    The extra `mode` field distinguishes subgame solves (fixed hole cards)
    from full-tree solves. PR 9 ships subgame mode only; full-tree mode
    is reserved for a post-v1 hand-class abstraction follow-up.
    """

    mode: str = "subgame"


# Cross-PR contract defaults. `iterations=10_000` is the PR 9 default
# (preflop trees with fixed hole cards are smaller than postflop flop
# trees, so DCFR converges faster — 10k typically reaches sub-1% exploit
# on standard 100 BB spots).
_DEFAULT_ITERATIONS: int = 10_000
_DEFAULT_MEMORY_BUDGET_GB: float = 14.0

# Stack-depth ceiling — see PLAN.md §1 stack-depth table. The solver
# refuses to spawn an HUNL tree wider than this because (a) preflop trees
# blow up at 200+ BB unless paired with a much tighter card abstraction,
# and (b) the PLAN.md commitment is 250 BB max. Exceeding raises
# ValueError; users can override via `_PREFLOP_MAX_BB_OVERRIDE` (env-style
# escape hatch documented in the public docstring).
PREFLOP_MAX_BB: int = 250


def solve_hunl_preflop(
    config: HUNLConfig,
    abstraction: AbstractionTables | None = None,
    iterations: int = _DEFAULT_ITERATIONS,
    target_exploitability: float | None = None,
    memory_budget_gb: float = _DEFAULT_MEMORY_BUDGET_GB,
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
    allow_pushfold_range: bool = False,
    on_progress: OnProgressFn | None = None,
    should_stop: ShouldStopFn | None = None,
    locked_strategies: Mapping[str, Sequence[float]] | None = None,
) -> PreflopSolveResult:
    """First end-to-end HUNL preflop solver in the Python reference tier.

    Args:
        config: ``HUNLConfig`` with ``starting_street == Street.PREFLOP``
            and a populated ``initial_hole_cards`` (subgame mode).
        abstraction: Optional ``AbstractionTables`` (PR 4) — applied to
            postflop streets only (preflop is always lossless per PR 4
            decision 7.12). Forward-compat hook; PR 9 itself never bucks
            preflop, so this argument is plumbed through to the tree only
            for downstream-postflop run-outs (all-in flips).
        iterations: Hard DCFR iteration cap. Default 10,000.
        target_exploitability: Optional early-exit threshold in BB/hand
            (checked at every ``log_every`` chunk; ``None`` disables).
        memory_budget_gb: Hard ceiling for total memory. Exceeding triggers
            a ``MemoryError`` whose ``args[1]`` is the partial
            ``MemoryReport``. Default 14.0 per PLAN.md commitment.
        log_every: When set, snapshot memory + record exploitability between
            chunks of this size. Default None (single end-of-solve summary).
            WARNING: per-chunk exploitability walks the full tree twice
            (best-response per player); on 100 BB preflop trees this is
            seconds per call.
        seed: Reserved for deterministic re-runs (threads through to DCFR).
        dcfr_kwargs: Reserved for DCFR hyperparameter overrides; PR 9 pins
            α=1.5 / β=0 / γ=2.0 per PLAN.md.
        allow_pushfold_range: If True, accept ≤15 BB configs and run the
            full tree solve anyway. The default (False) raises
            ``ValueError`` pointing at ``solve_pushfold``. The override is
            a research-mode escape hatch — useful for differential
            validation of the chart against a fresh DCFR solve at edge
            stacks (5/10/15 BB). Not exposed via CLI.
        on_progress: Optional callback fired once per ``log_every`` chunk
            with ``(iteration_count, exploitability_mBB_per_pot, memory_report)``.
            Mirrors the ``solve_hunl_postflop`` contract so the UI worker
            (PR 10b) can drive both code paths uniformly. Requires
            ``log_every`` to be set; the chunk-boundary fire-rate is the
            same as postflop. Callback runs on the solver thread; callers
            must be thread-safe. Exceptions inside the callback are
            suppressed so a misbehaving UI client cannot crash the solver.
        should_stop: Optional predicate polled at chunk boundaries. When it
            returns True the solver exits cleanly and returns a partial
            ``PreflopSolveResult`` whose ``iterations`` reflects how far
            the solve progressed. Mirrors postflop's cooperative-cancel
            contract for the UI worker.

    Returns:
        A ``PreflopSolveResult`` with ``average_strategy``,
        ``exploitability_history``, ``memory_report``, and ``mode=subgame``.

    Raises:
        ValueError: ``starting_street != PREFLOP``; missing
            ``initial_hole_cards`` (full-tree preflop deferred); stack
            depth ≤15 BB without the override (chart owns that range);
            stack depth >250 BB (PLAN.md ceiling); non-zero rake.
        MemoryError: total memory exceeds ``memory_budget_gb``. The
            exception's ``args[1]`` is the partial ``MemoryReport``.
    """
    _validate_preflop_config(config, allow_pushfold_range=allow_pushfold_range)
    if abstraction is not None:
        _validate_abstraction(abstraction)

    # The wrapper game collapses postflop runouts to equity leaves so the
    # solve is tractable without a full postflop card abstraction. For
    # all-in lines the substitution is exact; for limp / flat-call lines it
    # bakes in a check-it-down approximation (documented on the class).
    game = PreflopSubgameGame(config)

    extra_kwargs: dict[str, Any] = dict(dcfr_kwargs or {})
    if seed is not None and "seed" not in extra_kwargs:
        extra_kwargs["seed"] = seed
    if locked_strategies is not None and len(locked_strategies) > 0:
        extra_kwargs["locked_strategies"] = locked_strategies
    solver = DCFRSolver(game, **extra_kwargs)
    probe = MemoryProbe(solver, include_abstraction=abstraction)

    history, report = _run_with_probe(
        solver=solver,
        probe=probe,
        iterations=iterations,
        log_every=log_every,
        target_exploitability=target_exploitability,
        memory_budget_gb=memory_budget_gb,
        game=game,
        on_progress=on_progress,
        should_stop=should_stop,
    )

    avg = solver.average_strategy()
    if log_every is None and avg and iterations > 0:
        history.append(exploitability(game, avg))

    game_value = _game_value(game, avg) if avg else 0.0

    return PreflopSolveResult(
        average_strategy=avg,
        exploitability_history=history,
        game_value=game_value,
        iterations=solver.iteration,
        backend="python",
        memory_report=report,
        mode="subgame",
    )


def _validate_preflop_config(
    config: HUNLConfig,
    *,
    allow_pushfold_range: bool,
) -> None:
    """Stage A — reject configs PR 9 cannot handle.

    PR 9 ships **preflop-subgame mode only**: ``starting_street ==
    PREFLOP`` AND ``initial_hole_cards`` non-empty. The full-tree case
    (hole cards drawn as preflop chance) blows up to 1.6M chance branches
    and is reserved for a post-v1 hand-class-abstraction follow-up.
    """
    if config.starting_street != Street.PREFLOP:
        raise ValueError(
            f"solve_hunl_preflop requires starting_street == Street.PREFLOP; "
            f"got {config.starting_street!r}. Postflop configs route through "
            f"solve_hunl_postflop (PR 5)."
        )
    if not config.initial_hole_cards:
        raise ValueError(
            "solve_hunl_preflop requires initial_hole_cards to be set "
            "(subgame mode). PR 9 ships subgame-only; full-tree preflop "
            "(unfixed hole cards via the 1.6M-combo chance enum) is "
            "intractable without a hand-class abstraction — reserved for "
            "a post-v1 follow-up."
        )
    if len(config.initial_hole_cards) != 2:
        raise ValueError(
            f"initial_hole_cards must have exactly 2 entries (hero, villain); "
            f"got {len(config.initial_hole_cards)}."
        )
    # Cross-PR contract: push/fold owns ≤15 BB.
    effective_bb = config.starting_stack // config.big_blind
    if (
        is_pushfold_mode(config.starting_stack, config.big_blind)
        and not allow_pushfold_range
    ):
        raise ValueError(
            f"solve_hunl_preflop refuses to solve at effective stack "
            f"{effective_bb} BB (≤{PUSHFOLD_MAX_BB} BB belongs to the "
            f"push/fold chart per PLAN.md §1). Use `solve_pushfold(config)` "
            f"for a chart lookup, or pass `allow_pushfold_range=True` to "
            f"run a fresh DCFR solve for validation against the chart."
        )
    # Cross-PR contract: PLAN.md §1 caps at 250 BB.
    if effective_bb > PREFLOP_MAX_BB:
        raise ValueError(
            f"solve_hunl_preflop refuses to solve at effective stack "
            f"{effective_bb} BB (>{PREFLOP_MAX_BB} BB; PLAN.md §1 ceiling). "
            f"Deep-stack preflop is out of scope for v1."
        )
    if config.rake_rate != 0.0 or config.rake_cap != 0:
        raise ValueError(
            "PR 9 does not yet support rake; rake lands in a follow-up. "
            "Set rake_rate=0.0 and rake_cap=0."
        )


def _validate_abstraction(abstraction: AbstractionTables) -> None:
    """Same shape-check as PR 5; preflop only consults the abstraction for
    all-in run-out leaves (which never reach an abstracted infoset key
    today — preflop infoset keys are always lossless per PR 4 7.12) but we
    enforce the shape so unexpected artifacts fail loudly."""
    if not isinstance(abstraction, AbstractionTables):
        raise ValueError(
            f"abstraction must be an AbstractionTables instance, got "
            f"{type(abstraction).__name__!r}."
        )
    bucket_counts = abstraction.metadata.get("bucket_counts")
    if bucket_counts is None:
        raise ValueError(
            "abstraction metadata is missing 'bucket_counts'; not a valid "
            "PR 4 artifact."
        )
    if not isinstance(bucket_counts, (list, tuple)) or len(bucket_counts) != 3:
        raise ValueError(
            f"abstraction metadata['bucket_counts'] must be length 3 "
            f"(flop, turn, river); got {bucket_counts!r}."
        )


def _run_with_probe(
    *,
    solver: DCFRSolver,
    probe: MemoryProbe,
    iterations: int,
    log_every: int | None,
    target_exploitability: float | None,
    memory_budget_gb: float,
    game: PreflopSubgameGame,
    on_progress: OnProgressFn | None = None,
    should_stop: ShouldStopFn | None = None,
) -> tuple[list[float], MemoryReport]:
    """Chunked DCFR with memory + exploitability checks.

    Mirrors PR 5's `_run_with_probe` exactly (the orchestration pattern is
    identical between postflop and preflop subgames — both are extensive-
    form trees solved by `DCFRSolver`). Could be lifted into a shared
    helper in a future refactor, but inlining here keeps PR 9 surgical and
    avoids touching `hunl_solver.py` (frozen per PR 5 §6 + PR 9 §6).

    PR 10b fix: ``on_progress`` + ``should_stop`` hooks fire at the same
    chunk-boundary granularity as ``solve_hunl_postflop``'s ``_run_with_probe``
    so the UI worker (``ui/state.py::_dispatch_solve``) can drive preflop
    and postflop with identical callback semantics.
    """
    history: list[float] = []
    if iterations <= 0:
        return history, probe.snapshot()

    chunk_size = log_every if log_every is not None else iterations
    chunk_size = max(1, min(chunk_size, iterations))

    done = 0
    final_report: MemoryReport | None = None
    while done < iterations:
        # PR 10b: cooperative cancellation between chunks. Polled before the
        # next DCFR.solve() call so the average strategy stays consistent on
        # exit (we never break mid-iteration). Mirrors hunl_solver._run_with_probe.
        if should_stop is not None and should_stop():
            final_report = probe.snapshot()
            break

        step = min(chunk_size, iterations - done)
        solver.solve(step)
        done += step

        final_report = probe.snapshot()
        if final_report.total_gb > memory_budget_gb:
            raise MemoryError(
                f"Memory budget exceeded: {final_report.total_gb:.3f} GB > "
                f"{memory_budget_gb} GB after {done} iterations. "
                f"Consider reducing iterations or restricting "
                f"`bet_size_fractions` to fewer sizes. Partial report "
                f"attached as args[1].",
                final_report,
            )

        if log_every is not None:
            expl = exploitability(game, solver.average_strategy())
            history.append(expl)
            # PR 10b: fire the on_progress callback with the live snapshot
            # so the UI worker can stream expl_history without polling. We
            # suppress exceptions so a misbehaving UI cannot crash the
            # solver mid-iteration (mirrors hunl_solver._run_with_probe).
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(done, expl, final_report)
            if target_exploitability is not None and expl <= target_exploitability:
                break

    assert final_report is not None  # nosec: invariant
    return history, final_report


def _game_value(game: PreflopSubgameGame, strategy: dict[str, list[float]]) -> float:
    """Player-0 expected value under `strategy` (delegates to solver.py)."""
    import numpy as np

    from poker_solver.solver import _expected_value

    ev = _expected_value(
        game,
        strategy,
        game.initial_state(),
        np.ones(game.num_players + 1, dtype=np.float64),
    )
    return float(ev[0])


__all__ = [
    "PREFLOP_MAX_BB",
    "PreflopSolveResult",
    "solve_hunl_preflop",
]
