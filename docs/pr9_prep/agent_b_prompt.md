# PR 9 Agent B — Python subgame refiner + PR 5 postflop integration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 9 Agent B.**
**Your scope:** the postflop subgame refinement module that re-solves each high-reach preflop leaf with the full PR 3 action menu (6 sizes + all-in, 3-cap) against per-player ranges extracted from Agent A's blueprint, with the blueprint's regret tables loaded as a warm-start. You delegate the actual solve to PR 5's `solve_hunl_postflop(...)` unchanged; PR 9 wraps the call site with range-input handling + warm-start regret loading.
**Your contract:** ship `refine_subgame(...)`, `SubgameKey`, `SubgameRefinementResult` in `poker_solver/subgame_refiner.py`. Agent A's `solve_hunl_preflop` calls your public surface once per reachable subgame; Agent C tests you from spec alone.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on `subgame_refiner.py`; refined subgame matches a direct PR 5 postflop solve on the same configuration within 5e-2 per action (loose; warm-start vs cold-start trajectories differ but converged strategies should match); range extraction non-trivial (3-bet pots produce non-uniform ranges); warm-start reduces convergence iterations vs cold start; per-subgame memory drop between calls is clean; ALL existing tests still pass.
**File ownership:** you own and may write ONLY `poker_solver/subgame_refiner.py`. You may NOT touch `blueprint.py`, `preflop_solver.py`, any Rust file, any test file.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/subgame_refiner.py` (new file)

**You must NOT touch:**
- `poker_solver/blueprint.py`, `poker_solver/preflop_solver.py` — Agent A owns these. You import only their public surface (`BlueprintResult` from `blueprint`).
- `poker_solver/dcfr.py` — frozen per spec §5.
- `poker_solver/hunl.py` — Agent A makes the canonical-class chance generator edit; you do NOT modify this file.
- `poker_solver/hunl_solver.py` (PR 5) — you call `solve_hunl_postflop(...)` from this module unchanged. Do NOT modify it.
- `poker_solver/abstraction/*` — PR 4's territory; consumed as a read-only artifact.
- `poker_solver/profiler/*` — PR 5 owns; you import `MemoryReport` if needed.
- `poker_solver/solver.py`, `poker_solver/cli.py`, `poker_solver/__init__.py` — Agent A's surgical edits.
- Any Rust file under `crates/cfr_core/src/` — Agent C owns.
- Any test file (`tests/test_hunl_preflop_*.py`, `tests/test_preflop_diff.py`, `tests/fixtures/hunl_preflop_fixtures.py`) — Agent C owns.

If you discover an awkward signature or a contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`. Internalize §1 (goal), §3.2 (two-stage solve), §3.3 (why blueprint is "good enough" at preflop), §4 (your file's signatures), §5 (files to modify — what you DON'T touch), §8 (subgame refinement — your stage; especially §8.1 high-reach filter, §8.2 range input, §8.3 warm start, §8.4 reuse PR 5, §8.5 output assembly), §11 Agent B deliverables, §12 (memory budget — sequential per-subgame, drop state between), §13 (risks — especially the range-extraction row + the warm-start regret-loading row).
2. **Spec consistency review (recent amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially B4 (PR 9 §6 canonical dispatch — informs your understanding even though you don't implement dispatch), I3 (diff-test tolerance: 5e-3 per-action / 1e-3 per-spot game value; you don't implement diff tests but downstream tests check your output), I4 (10% psutil calibration inherits to PR 9 — applies to YOUR per-subgame solves), I5 (combined <0.05 BB/hand target — your refinement quality contributes).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" (256/128/64 default, stack-depth tier table) and §1 "Memory budget" (14 GB hard ceiling, applies per-subgame in PR 9).
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 9 entries.
5. **PR 5 spec (you depend on this entirely):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. Especially §5 (`solve_hunl_postflop` signature), §7.3 (infoset key formats — lossless AND bucketed), §10 + §11 (`HUNLSolveResult` shape — Agent A's return type subclasses this).
6. **Pluribus paper (canonical reference for refinement pattern):** `references/papers/pluribus_brown_2019_science.pdf`. Page 4: *"After the first round (and even in the first round if an opponent chooses a bet size that is sufficiently different from the sizes in the blueprint action abstraction) Pluribus instead conducts real-time search to determine a better, finer-grained strategy for the current situation it is in."* Our refinement is *offline-batched* (run once at solve time, store strategies in result), not online; spirit is the same.
7. **Existing surfaces you wrap:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` (PR 5) — `solve_hunl_postflop(config, abstraction, iterations, target_exploitability, memory_budget_gb, log_every, seed, dcfr_kwargs) -> HUNLSolveResult`. You call this with a constructed `HUNLConfig` per spec §8.4.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLPoker`, `HUNLConfig`, `Street`, the existing `HUNLState`. Read-only. You construct a `HUNLConfig` for each subgame: `starting_street=Street.FLOP`, `initial_board=()`, `initial_pot=...`, `initial_contributions=...`, full PR 3 menu, 3-cap.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — `DCFRSolver`, `InfosetData` (with `regret_sum: np.ndarray`, `strategy_sum: np.ndarray`, `num_actions: int`). Read-only; you may inspect `solver.infosets: dict[str, InfosetData]` for warm-start loading.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` — `AbstractionTables`, `lookup_bucket(...)`. PR 4 artifact.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/blueprint.py` (Agent A's surface) — `BlueprintResult` dataclass. You consume this as input.
8. **Reference style — PR 5 Agent B prompt:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_b_prompt.md`. Same shape and tone.
9. **License-aware sourcing patterns:** see §"License-aware sourcing" below.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 9 spec §14 + the consistency review:

1. **Refinement uses full PR 3 menu + 3-cap** (spec §8.4). Construct `HUNLConfig(..., bet_size_fractions=(0.33, 0.75, 1.00, 1.50, 2.00), include_all_in=True, postflop_raise_cap=3)`. Even though the blueprint used a coarse menu, refinement always uses the full menu — that's the whole point.
2. **Warm-start regret loading** (spec §8.3). For every postflop infoset key that exists in BOTH the blueprint's solver state AND the refinement's tree, copy the blueprint's regret values into the refinement's regret table at iteration 0. Infosets that exist only in refinement (because refinement has the full 6-size menu) start with zero regret.
3. **Range extraction is per-player, per-hand-class** (spec §8.2). `p0_range[hand_class] = Σ_paths reach_prob(path_to_subgame_root | hand_class)` where the sum is over all preflop betting paths leading to the subgame, and the reach is computed under the blueprint's strategy.
4. **Each subgame solved SEQUENTIALLY** (spec §12). Agent A's orchestration calls `refine_subgame(...)` once per subgame. Between calls, the orchestrator drops the previous solver's state; your job is just to ensure your own per-call allocations don't leak into a global state that survives the call.
5. **Per-subgame memory budget: same as blueprint** (spec §12). Default `max_memory_gb: float = 14.0`. If exceeded, raise `MemoryError` with the partial `MemoryReport` as `args[1]` (PR 5 pattern).
6. **Per-subgame iteration count: 10,000** (spec §14 #6). Default `iterations: int = 10_000`.
7. **Per-subgame exploitability target: <0.1 BB/100** (spec §7.4). Matches PR 5's Fixture 1 target for a direct postflop solve.
8. **Calling convention: keyword-only for everything except `subgame_key`, `blueprint`, `abstraction`** (the three positional args by convention; spec §4).
9. **NO modification to `dcfr.py` or `hunl_solver.py`.** Both are frozen. Your warm-start loading is purely external — you populate `solver.infosets` dict AFTER constructing `DCFRSolver(game)` but BEFORE running `solver.solve(...)`. If `DCFRSolver` doesn't expose a clean hook for this, you may extract regret values from the blueprint's solver state and pass them through PR 5's `solve_hunl_postflop` if it accepts a warm-start kwarg; if PR 5 doesn't, you instantiate `DCFRSolver` yourself, populate the warm start, then drive it. **CRITICAL:** if PR 5's interface doesn't admit a warm start, file an interface adjustment note for the orchestrator rather than modifying PR 5.
10. **`on_progress` kwarg is part of `refine_subgame`'s public surface** (launch-readiness patch; PR 10b consumer at `docs/pr10_prep/pr10b_spec.md` lines 152-156). Signature: `on_progress: Callable[[int, float, MemoryReport], None] | None = None`. Pass through unchanged to PR 5's `solve_hunl_postflop(..., on_progress=on_progress)`. If you bypass PR 5 (instantiate `DCFRSolver` directly per item 9), invoke the callback yourself every `log_every` iterations with `(iteration, exploitability_bb, memory_snapshot)`. Cancellation NOT in this contract.

**Non-spec defaults LOCKED:**
- `SubgameKey` is a frozen dataclass (hashable, can be dict key).
- `SubgameRefinementResult` is a frozen dataclass.
- Both follow the same N7 pattern PR 5 established (immutable value objects).

## Public API contract (signatures Agent A + Agent C depend on)

Export the following from `poker_solver/subgame_refiner.py`. **Signature drift breaks Agent A's `solve_hunl_preflop` and Agent C's tests + Rust port.** Type hints required (mypy --strict).

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.card import Card
from poker_solver.hunl import Street
from poker_solver.profiler.memory import MemoryReport


@dataclass(frozen=True)
class SubgameKey:
    """Identifies a postflop subtree reachable from the preflop blueprint.

    Uniquely identified by the preflop betting history + the postflop start
    configuration. The `board` field is empty at the preflop-leaf level
    (the flop chance node hasn't dealt yet); refinement enumerates flops
    *inside* the per-subgame solve.

    All chip values are integer cents (per PR 3 invariant; no float chip
    arithmetic).
    """
    starting_street: Street
    board: tuple[Card, ...]
    pot: int
    p0_contribution: int
    p1_contribution: int
    preflop_betting_history: str


@dataclass(frozen=True)
class SubgameRefinementResult:
    """Output of one refined postflop subgame.

    Fields:
      refined_strategy: dict mapping infoset_key -> action probabilities
        (sums to 1.0 per row). Spans the full postflop tree below the
        subgame root.
      game_value: EV at the subgame root in BB (positive = P0 EV).
      exploitability: BB/100 — target < 0.1 for refined subgames.
      p0_range: dict mapping hand_class -> reach probability (sums to 1.0).
      p1_range: same for P1.
    """
    refined_strategy: dict[str, list[float]]
    game_value: float
    exploitability: float
    p0_range: dict[str, float]
    p1_range: dict[str, float]


def refine_subgame(
    subgame_key: SubgameKey,
    blueprint: "BlueprintResult",  # forward ref to avoid circular import
    abstraction: AbstractionTables,
    *,
    iterations: int = 10_000,
    max_memory_gb: float = 14.0,
    seed: Optional[int] = None,
    log_every: Optional[int] = None,
    on_progress: Optional[Callable[[int, float, MemoryReport], None]] = None,
) -> SubgameRefinementResult:
    """Refine one postflop subgame using full PR 3 menu + 3-cap, warm-
    started from the blueprint's regret tables, against the blueprint's
    per-player ranges.

    Stages (per spec §8):
      1. Extract p0_range, p1_range from blueprint.reach_probs +
         blueprint.strategy walked along the preflop path encoded in
         subgame_key.preflop_betting_history.
      2. Build a HUNLConfig for this subgame:
         starting_street=subgame_key.starting_street,
         initial_board=subgame_key.board (may be empty if FLOP-start;
           PR 5 handles this by enumerating flops via chance node),
         initial_pot=subgame_key.pot,
         initial_contributions=(subgame_key.p0_contribution,
                                 subgame_key.p1_contribution),
         bet_size_fractions=(0.33, 0.75, 1.00, 1.50, 2.00),
         include_all_in=True,
         postflop_raise_cap=3,
         range_p0=p0_range,
         range_p1=p1_range.
         (If PR 3's HUNLConfig doesn't have explicit range fields, use
          dataclasses.replace + whatever range-attachment hook PR 3 / PR 5
          exposes. File an interface adjustment note if no clean hook
          exists.)
      3. Warm-start: load blueprint regret values into the new solver's
         regret_sum / strategy_sum dicts for matching infoset keys.
      4. Run the refinement via solve_hunl_postflop(refinement_config,
         abstraction, iterations, max_memory_gb=max_memory_gb,
         seed=seed, log_every=log_every, on_progress=on_progress).
         (If solve_hunl_postflop doesn't admit a warm-start kwarg,
         instantiate DCFRSolver yourself, populate the warm-start regret
         tables, then drive solver.solve(iterations). File an interface
         adjustment note if a cleaner path emerges. The `on_progress`
         kwarg is part of PR 5's public surface; pass through unchanged.)
      5. Compute the subgame's exploitability via solver.exploitability
         on the refinement config (or use PR 5's exploitability helper).
      6. Pack into SubgameRefinementResult.

    Args:
        subgame_key: identifies the postflop subtree configuration.
        blueprint: Agent A's BlueprintResult containing the blueprint
            strategy + reach probs + leaf values + memory report.
        abstraction: pre-loaded AbstractionTables (the tier-appropriate
            artifact for the stack depth implied by subgame_key.pot +
            contributions).
        iterations: refinement DCFR iterations. Default 10_000.
        max_memory_gb: hard ceiling. Exceeding raises MemoryError.
            Default 14.0.
        seed: optional for deterministic re-runs.
        log_every: snapshot frequency for memory + exploitability.
        on_progress: PR 10b launch-readiness hook (cf.
            `docs/pr10_prep/pr10b_spec.md` lines 152-156). When non-None,
            called every `log_every` iterations during the refinement DCFR
            loop with `(iteration_number, current_exploitability_bb,
            memory_snapshot)`. Pass through to PR 5's `solve_hunl_postflop`
            via its same-named kwarg (PR 5 already supports this shape per
            PR 5 spec). `memory_snapshot: MemoryReport` re-exported from
            `poker_solver.profiler.memory`. Cancellation NOT in this
            contract — PR 10a handles separately.

    Returns:
        SubgameRefinementResult.

    Raises:
        ValueError: subgame_key inconsistent (e.g., negative pot,
            contributions don't sum to pot, FLOP-start with non-empty
            board, etc.).
        MemoryError: subgame solve exceeds max_memory_gb. e.args[1]
            carries the partial MemoryReport.
    """
    ...
```

**Internal helpers (you choose, but document them):**
- `_extract_ranges_from_blueprint(blueprint: BlueprintResult, subgame_key: SubgameKey) -> tuple[dict[str, float], dict[str, float]]` — computes (p0_range, p1_range) per spec §8.2 via CFR reach-probability recurrence.
- `_build_subgame_config(subgame_key: SubgameKey, abstraction: AbstractionTables, p0_range, p1_range) -> HUNLConfig` — constructs the per-subgame `HUNLConfig` with full PR 3 menu.
- `_warm_start_from_blueprint(solver: DCFRSolver, blueprint: BlueprintResult) -> int` — populates `solver.infosets` regret_sum dict from blueprint regret values for matching keys. Returns the count of warm-started infosets (for the report).
- `_validate_subgame_key(subgame_key: SubgameKey) -> None` — sanity (non-negative pot, contributions sum correctly, etc.).

## Cross-agent contracts (Agent A's surface; do NOT reach inside)

Treat these as opaque. Import only the names; do not depend on internals:

```python
# From poker_solver.blueprint (Agent A's module):

@dataclass(frozen=True)
class BlueprintResult:
    strategy: dict[str, list[float]]       # blueprint's per-infoset strategies
    reach_probs: dict[str, float]          # per-infoset reach under avg strategy
    leaf_values: dict[SubgameKey, float]   # subgame root values cached during walk
    exploitability_history: list[float]
    memory_report: MemoryReport
```

You consume `blueprint.strategy` for warm-starting and `blueprint.reach_probs` for range extraction. Treat `blueprint.leaf_values` as informational (the EV the blueprint assigned to this subgame's root, useful for diagnostics).

**Critical:** the blueprint's strategy keys use the same infoset-key format as PR 5 (lossless + bucketed per PR 4 §3.5; see PR 5 §7.3). When you load regret values for warm-start, the matching is on infoset-key equality. If an infoset key exists in the blueprint but not in your refinement tree (because the refinement uses the full 6-size menu and the blueprint used 1 size), that infoset's regret is dropped from the warm-start — only "exact-match" keys transfer.

## Critical correctness items

### 1. Range extraction is mathematically correct (spec §8.2)

For a given subgame key `sk`, the per-player ranges arriving at the subgame's root are:

```
p0_range[hand_class] = Σ over preflop_paths p ending at sk's root,
                       weighted by reach_prob(p | hand_class, blueprint.strategy)
                       and the prior P(hand_class).
```

The reach computation follows the standard CFR reach-probability recurrence (e.g., Brown & Sandholm 2019 §"Counterfactual regret minimization"). The result must satisfy `sum(p0_range.values()) == pytest.approx(1.0, abs=1e-6)`.

**Spec §13 risk row 2:** the load-bearing input to refinement is the ranges. Misextracted ranges produce wrong refined strategies. Get this right. Validate via Agent C's test `test_refinement_ranges_extracted_correctly` (spec §10.2 #5): for a 3-bet pot, `p0_range["AA"] > p0_range["72o"]` (SB rarely 3-bets 72o; AA is in the 3-bet range).

### 2. Warm-start regret loading is correct (spec §8.3)

For every infoset key `k` that exists in BOTH `blueprint.strategy` AND the refinement solver's tree:
- Read the blueprint's regret values for `k` (you may need to extract these from the blueprint's solver state; if `BlueprintResult` exposes them via a helper, use it; otherwise, infer from `blueprint.strategy` via the inverse mapping — but the spec implies the blueprint's regret table is accessible alongside the strategy, see §8.3).
- Copy them into `solver.infosets[k].regret_sum` (NumPy array, dtype float64).
- The action count must match: if the blueprint had 3 actions at `k` (1-size menu) and the refinement has 8 actions at `k` (full menu), the action sets don't align — DROP this key from the warm start. Only transfer keys where action sets exactly match.

Spec §8.3: *"This warm start typically reduces refinement iterations needed by 50-80% — the blueprint is already in the right neighborhood; refinement is a local polish."* Agent C's test `test_refinement_warm_start_speeds_convergence` (spec §10.2 #2) exercises this.

If `BlueprintResult` does NOT expose regret tables directly (only the average strategy), the warm-start is "strategy-warm" rather than "regret-warm" — you'd derive regret approximations from the strategy. Document your choice; if you can't get regret-warm from the spec'd `BlueprintResult` shape, file an interface adjustment note.

### 3. Subgame solve produces a valid refined strategy

For every infoset in `SubgameRefinementResult.refined_strategy`:
- `sum(probs) == pytest.approx(1.0, abs=1e-9)`.
- `all(0.0 <= p <= 1.0 for p in probs)`.
- `not any(math.isnan(p) or math.isinf(p) for p in probs)`.
- The action count equals the legal actions at that infoset under the FULL PR 3 menu + 3-cap (NOT the blueprint's coarsened menu). Agent C's `test_refinement_uses_full_action_menu` (spec §10.2 #3) asserts this.

### 4. Parity with direct PR 5 postflop solve (spec §10.2 #1)

For one subgame (e.g., flop 3-bet pot at 100 BB, board AsKsQh), the refined strategy must match a direct `solve_hunl_postflop(equivalent_config, ...)` (cold-start, same ranges, same abstraction) within `5e-2` per action. This is loose — warm-start vs cold-start trajectories differ but converged strategies should agree.

If they DON'T agree within 5e-2, that's evidence of: (a) a range-extraction bug, (b) a warm-start regret-loading bug, or (c) a subtle interface mismatch with PR 5. Diagnose, don't paper over.

### 5. Memory budget per subgame inherits 10% calibration

Per spec §12 + consistency review I4: each subgame solve uses the same `MemoryProbe` calibration check as PR 5. If `MemoryReport.rss_calibration_error > 0.10`, log a warning but do NOT abort. Hard abort only when `report.total_gb > max_memory_gb`.

Your `refine_subgame` raises `MemoryError` with the partial `MemoryReport` as `args[1]`, matching PR 5's pattern:

```python
raise MemoryError(
    f"Subgame refinement exceeded memory budget: "
    f"{report.total_gb:.2f} GB > {max_memory_gb} GB. "
    f"Partial report attached as args[1].",
    report,
)
```

### 6. Subgame state cleanly droppable between calls (spec §12)

Your `refine_subgame` must NOT leave behind module-level state that survives across calls. Each invocation should be self-contained:
- Construct your solver inside the function (or pass a fresh one to PR 5).
- Local variables release naturally at function exit.
- No `global` regret tables, no module-level caches.

Agent A's orchestration does `del solver; gc.collect()` between subgames; you support that by not pinning references inadvertently.

### 7. Determinism

Same `seed` + same `subgame_key` + same `blueprint` + same `abstraction` → identical `SubgameRefinementResult` within float tolerance. The refinement is deterministic given the seed; your code must not introduce nondeterminism via dict iteration order in result-packaging.

### 8. SubgameKey hashability

`@dataclass(frozen=True)` on `SubgameKey` makes it hashable as long as all fields are hashable. `board: tuple[Card, ...]` is hashable (tuple of hashable Cards). `preflop_betting_history: str` is hashable. Confirm with a smoke test that `dict[SubgameKey, ...]` round-trips.

### 9. The `HUNLConfig` you construct for the refinement must validate

Per PR 3 invariants: `rake_rate == 0.0`, integer chip values, `starting_street == subgame_key.starting_street`, `initial_board` has the right card count for the street (0 for FLOP-start, 3 for TURN-start with a known flop, etc.). If you build an invalid config, PR 5's validator catches it — but it's better to fail in your own `_validate_subgame_key` first with a clearer error.

### 10. Existing tests still pass

Your new module is purely additive; no existing tests should break. Run `pytest -x` and confirm.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/slumbot2019/` (**MIT**) — Slumbot's subgame solving pattern. Read-only architectural inspiration.
- `references/code/noambrown_poker_solver/` (**MIT**) — Brown's reference. The blueprint + refinement architecture is canonical Pluribus.
- Pluribus paper (`references/papers/pluribus_brown_2019_science.pdf`) — algorithmic reference, page 4 for refinement pattern.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. No code copy.

**You may NOT extrapolate from training data.** If you "remember" a subgame solving implementation and want to use it, ground it in the Pluribus paper or the PR 9 spec.

If you copy a non-trivial code snippet (>~5 LOC) from an MIT source, add an attribution comment.

## Quality bar

- **ruff clean:** `ruff check poker_solver/subgame_refiner.py` reports zero issues.
- **black clean:** `black --check poker_solver/subgame_refiner.py` reports no changes.
- **mypy strict-clean:** `mypy --strict poker_solver/subgame_refiner.py` reports zero errors.
- **No new third-party deps.** Imports: `numpy`, `psutil` (already a dep), `poker_solver.*`, stdlib only.
- **All existing tests pass unchanged.** Run `pytest -x` after your work lands. Your module is purely additive.
- **Code size budget: ~350 LOC** (per spec §9). Stay within budget; the public surface is small (one function + two dataclasses); the heavy lifting is internal helpers + the PR 5 call site.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

For the blueprint + refinement pattern: cite `references/papers/pluribus_brown_2019_science.pdf` page 4 (per PR 9 §16).

For the CFR reach-probability recurrence (used in range extraction): cite the same paper §"Counterfactual regret minimization" or `references/papers/cfr_zinkevich_2007.pdf` if present locally.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/subgame_refiner.py
black --check poker_solver/subgame_refiner.py

# 2. Type-check
mypy --strict poker_solver/subgame_refiner.py

# 3. Existing test suite must still pass (PR 1 through PR 8 + Agent A's edits)
pytest -x 2>&1 | tail -20

# 4. SubgameKey hashability smoke
python -c "
from poker_solver.subgame_refiner import SubgameKey
from poker_solver.hunl import Street
k1 = SubgameKey(
    starting_street=Street.FLOP,
    board=(),
    pot=200,
    p0_contribution=100,
    p1_contribution=100,
    preflop_betting_history='ck',
)
k2 = SubgameKey(
    starting_street=Street.FLOP,
    board=(),
    pot=200,
    p0_contribution=100,
    p1_contribution=100,
    preflop_betting_history='ck',
)
assert k1 == k2
assert hash(k1) == hash(k2)
d = {k1: 'x'}
assert d[k2] == 'x'
print('SubgameKey hashability OK')
"

# 5. Smoke: range extraction on a trivial blueprint
# (You'll need a tiny mock BlueprintResult; this is a smoke, not a real test.)
python -c "
from poker_solver.subgame_refiner import SubgameKey, refine_subgame
from poker_solver.hunl import Street
# Smoke that the import works and the function is callable; full
# behavior tested by Agent C.
sk = SubgameKey(
    starting_street=Street.FLOP, board=(), pot=200,
    p0_contribution=100, p1_contribution=100,
    preflop_betting_history='ck',
)
print(f'refine_subgame importable; SubgameKey={sk}')
"

# 6. Dataclass frozenness
python -c "
from dataclasses import FrozenInstanceError
from poker_solver.subgame_refiner import SubgameKey, SubgameRefinementResult
from poker_solver.hunl import Street
sk = SubgameKey(
    starting_street=Street.FLOP, board=(), pot=200,
    p0_contribution=100, p1_contribution=100,
    preflop_betting_history='ck',
)
try:
    sk.pot = 400  # type: ignore
    raise AssertionError('should have raised FrozenInstanceError')
except FrozenInstanceError:
    print('SubgameKey frozen OK')
"
```

If any of the above fails, fix the issue before reporting done. If a smoke reveals a spec ambiguity (especially around the warm-start hook into PR 5 or the range field on `HUNLConfig`), **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with LOC.
2. Any spec amendment you made or contract drift you flagged (and why).
   - Specifically: did `HUNLConfig` admit `range_p0` / `range_p1` fields, or did you need an interface adjustment? Did `solve_hunl_postflop` admit a warm-start kwarg, or did you instantiate `DCFRSolver` yourself?
3. The warm-start protocol you chose: regret-warm (preferred) or strategy-warm (fallback). Why?
4. Verification command output (paste tails).
5. Range-extraction sanity check (`p0_range["AA"] > p0_range["72o"]` on a synthetic 3-bet-pot subgame; pasted output).
6. Any open question you couldn't resolve from the spec / PLAN / PR 5 spec — flag for human review.
7. License attributions you added (if any).
8. Confirmation that `on_progress` is plumbed through `refine_subgame` → PR 5's `solve_hunl_postflop` (or, if you instantiated DCFRSolver directly, the callback site in your own loop). Cite the file:line where the callback is forwarded/invoked.
