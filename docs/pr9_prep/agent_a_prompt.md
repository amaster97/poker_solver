# PR 9 Agent A — Python blueprint + preflop solver orchestration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 9 Agent A.**
**Your scope:** the Python coarse-blueprint pass and the top-level preflop solve orchestrator — the first end-to-end HUNL preflop → river deliverable in the Python reference tier. You wire `HUNLPoker` (PR 3) + a coarsened action menu + `AbstractionTables` (PR 4) + `DCFRSolver` (PR 1) + `MemoryProbe` (PR 5) into a blueprint pass, then drive Agent B's `refine_subgame(...)` over each high-reach preflop subgame, then assemble a combined strategy table. You also own the dispatch composition edits to `solver.py` / `cli.py` / `__init__.py` and the canonical-class preflop chance generator in `hunl.py`.
**Your contract:** ship `solve_hunl_preflop(...)` + `PreflopSolveResult` (extends `HUNLSolveResult`) in `preflop_solver.py`; ship `build_blueprint(...)` + `BlueprintResult` in `blueprint.py`; surgically edit `solver.py` (dispatch composition per spec §6 — CANONICAL HERE), `cli.py` (`--hunl-mode preflop` + new flags), `__init__.py` (re-exports), and `hunl.py` (add `_enumerate_preflop_hole_outcomes_canonical(...)` opt-in generator). Consume Agent B's `refine_subgame(...)` public surface only.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on `preflop_solver.py` + `blueprint.py` + the `hunl.py` additions; blueprint produces a strategy for every reachable preflop infoset; dispatch ordering test cliff at 15 BB / 16 BB / 251 BB locks correctly; combined `PreflopSolveResult` round-trips through Agent B's `refine_subgame(...)` without contract drift; ALL existing tests (PR 1 through PR 8, ~190+) still pass.
**File ownership:** you own and may write ONLY `poker_solver/preflop_solver.py` + `poker_solver/blueprint.py`. You may surgically modify `poker_solver/solver.py`, `poker_solver/cli.py`, `poker_solver/__init__.py`, `poker_solver/hunl.py`. You may NOT touch `subgame_refiner.py`, any Rust file, any test file.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/preflop_solver.py` (new file)
- `/Users/ashen/Desktop/poker_solver/poker_solver/blueprint.py` (new file)

**You may surgically modify (small, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — add the preflop dispatch branch + the ≤15 BB push/fold short-circuit confirmation + the >250 BB error per PR 9 §6 (CANONICAL). PR 3.5's branch and PR 5's postflop branch already exist; you ADD the preflop branch and the >250 BB ceiling. Do NOT remove or perturb the existing branches.
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — extend `--hunl-mode` choices to add `preflop` (with `full` as deprecated synonym); add `--stacks`, `--ante`, `--blueprint-iterations`, `--refine-iterations`, `--reach-threshold`, `--abstraction`, `--max-memory-gb` flags. The existing `--hunl-mode full` `NotImplementedError` is replaced with the wiring to `solve_hunl_preflop(...)`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — re-export `solve_hunl_preflop`, `PreflopSolveResult`, `BlueprintResult`, `build_blueprint`. Re-export Agent B's `refine_subgame`, `SubgameKey`, `SubgameRefinementResult` (the actual names must match Agent B's exports verbatim). Add to `__all__`.
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — add a SINGLE new generator method `_enumerate_preflop_hole_outcomes_canonical(self) -> Iterator[ChanceOutcome]` per spec §5. Modify the existing `chance_outcomes` path so that when `config.starting_street == Street.PREFLOP` AND a new `chance_strategy: Literal["full", "canonical_classes"] = "full"` kwarg (or per-config attribute — see "PR 9 hunl.py modification" below) is `"canonical_classes"`, the canonical generator is used. **Preserve the existing 1.6M-combo generator behavior unchanged for any other caller** (per §14 decision 8: opt-in only).

**You must NOT touch:**
- `poker_solver/subgame_refiner.py` — Agent B owns this entirely. You import only its public surface (`refine_subgame`, `SubgameKey`, `SubgameRefinementResult`).
- `poker_solver/dcfr.py` — frozen per spec §5 ("DCFR algorithm unchanged. Hyperparameters (α=1.5, β=0, γ=2.0) unchanged.").
- `poker_solver/hunl_solver.py` (PR 5) — called BY Agent B's `subgame_refiner` but not modified.
- `poker_solver/abstraction/*` — PR 4's territory; consumed as a read-only artifact.
- `poker_solver/profiler/*` — PR 5 owns; you import `MemoryProbe`, `MemoryReport` from it.
- `poker_solver/charts/pushfold_v1.json` — PR 3.5's chart; you dispatch to `pushfold.solve_pushfold(...)` unchanged.
- Any Rust file under `crates/cfr_core/src/` — Agent C owns these.
- Any test file (`tests/test_hunl_preflop_*.py`, `tests/test_preflop_diff.py`, `tests/fixtures/hunl_preflop_fixtures.py`) — Agent C owns these.

If you discover an awkward signature or contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`. Internalize §1 (goal), §3 (architecture), §4 (files to create), §5 (files to modify), §6 (dispatch composition — CANONICAL, you implement this), §7 (blueprint design — your stage), §8 (subgame refinement — your orchestration calls Agent B's `refine_subgame`), §11 Agent A deliverables, §12 (memory budget enforcement — inherits PR 5 §7.6 with 10% calibration), §13 (risks), §14 decisions (defaults locked below), §17 (success criteria).
2. **Spec consistency review (recent amendments):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially B4 (PR 9 §6 is now the canonical dispatch composition reference), I3 (diff-test tolerance reconciled to PR 6/7/8 cluster — `5e-3` per-action / `1e-3 × base_pot` per-spot game value), I4 (10% psutil calibration tolerance inherits to PR 9 — see §12), I5 (combined exploitability target added: <0.05 BB/hand on Pio 100 BB cash-game fixture).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" (256/128/64 default, stack-depth tier table — your `_tier_for_depth` helper consumes this), §1 "Memory budget" (14 GB hard ceiling), §3 "Architecture summary" (Python is ground truth).
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 9 entries and any cross-cutting locks.
5. **Pluribus paper (canonical blueprint + refinement reference):** `references/papers/pluribus_brown_2019_science.pdf`. Pages 2–4 cover the blueprint strategy, the postflop real-time search (analogous to our offline-batched refinement), and the pruning rule. PR 9 §16 cites the exact passages.
6. **Existing surfaces you wire together:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — `DCFRSolver(game)`; methods `solve(iterations, log_every=...)`, `average_strategy()`. Hyperparameters frozen (α=1.5, β=0, γ=2.0).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `solve(...)` orchestration (you add the preflop dispatch branch + the >250 BB error path); `SolveResult` superclass; `exploitability(game, strategy)` function.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLPoker`, `HUNLConfig`, `Street`, the existing `_enumerate_preflop_hole_outcomes()` (1.6M outcomes; you preserve unchanged and add a sibling canonical-class generator).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — `ActionAbstractionConfig`, the 6-fraction menu, and the 4-cap (preflop) / 3-cap (postflop) rules. **Your blueprint coarsens the postflop menu but keeps preflop unchanged.**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` — `AbstractionTables`, `load_abstraction(path)`, `lookup_bucket(...)`. PR 4 artifact.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` (PR 5) — `solve_hunl_postflop(...)`, `HUNLSolveResult` (you subclass it for `PreflopSolveResult`). Agent B calls this from inside `refine_subgame`.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/profiler/memory.py` (PR 5) — `MemoryProbe`, `MemoryReport`. You construct a probe for the blueprint pass.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/pushfold.py` (PR 3.5) — `solve_pushfold(config)`. You short-circuit to this at ≤15 BB.
7. **Reference style — PR 5 Agent A prompt:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_a_prompt.md`. Same shape, same tone, same five-line summary header.
8. **License-aware sourcing patterns:** see §"License-aware sourcing" below.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 9 spec §14 + the consistency review. The user has authorized autonomous mode; these are LOCKED unless the user redirects before launch:

1. **Boundary handoff at 15 BB: HARD CLIFF** (spec §14 #1; §6 default). `eff_stack_bb ≤ 15` → push/fold chart; `eff_stack_bb > 15` → preflop solver. No interpolation band in v1.
2. **Blueprint postflop menu: 1 size (0.75-pot) + all-in, 1-cap** (spec §14 #2 default; §7.1). Compose a coarsened `HUNLConfig` for the blueprint pass: `bet_size_fractions=(0.75,)`, `include_all_in=True`, `postflop_raise_cap=1`. Preflop menu UNCHANGED (full PR 3 menu, 4-cap).
3. **Maximum stack depth: 250 BB** (spec §14 #3; §6). `eff_stack_bb > 250` raises `ValueError` with message: `f"Stack depth {eff_stack_bb} BB > 250 BB max."`
4. **Reach threshold for subgame refinement: 1e-3** (spec §14 #4; §8.1). Default `reach_threshold: float = 1e-3` on `solve_hunl_preflop` signature.
5. **Blueprint iterations: 50,000** (spec §14 #5; §7.4). Default `blueprint_iterations: int = 50_000`.
6. **Per-subgame refinement iterations: 10,000** (spec §14 #6). Default `refine_iterations: int = 10_000`.
7. **Blueprint artifact NOT committed to repo** (spec §14 #7). Local build only. A `precompute-blueprint` CLI is a PR 9.5 follow-up.
8. **Canonical-class chance enumeration: OPT-IN** (spec §14 #8). The existing `_enumerate_preflop_hole_outcomes()` (1.6M combos) preserved unchanged; the new `_enumerate_preflop_hole_outcomes_canonical()` (28,561 outcomes = 169 × 169 with proper combinatorial weights) is opt-in. `BlueprintResult` builder passes the opt-in flag automatically.
9. **`--hunl-mode preflop` is canonical; `--hunl-mode full` is deprecated synonym** (spec §14 #9). Both work; help text marks `full` as deprecated.
10. **Full-traverse DCFR (not MCCFR / external sampling)** (spec §14 #10). Consistent with PRs 1–5 + PR 8 default. If PR 8's public chance sampling has shipped, you may use it for the chance node walk, but full-traverse remains the default.
11. **Memory budget: 14 GB hard ceiling, inherits PR 5's 10% calibration tolerance** (spec §12; consistency review I4). Default `max_memory_gb: float = 14.0`. If exceeded, raise `MemoryError` with the partial `MemoryReport` as `args[1]` (same pattern PR 5 established).
12. **`HUNLSolveResult` is a subclass of `SolveResult`** (PR 5 §14 #3 locked; consistency review N7). `PreflopSolveResult` subclasses `HUNLSolveResult` (locked by spec §4).
13. **`on_progress` kwarg is part of the public surface** (launch-readiness patch; PR 10b consumer at `docs/pr10_prep/pr10b_spec.md` lines 152-156). Both `solve_hunl_preflop(...)` and `build_blueprint(...)` accept `on_progress: Callable[[int, float, MemoryReport], None] | None = None`. When non-None, invoke every `log_every` iterations with `(iteration_number, current_exploitability_bb, memory_snapshot)`. Thread the callback from `solve_hunl_preflop` → `build_blueprint` (blueprint pass) and → `refine_subgame` (subgame pass, via Agent B's surface). Cancellation NOT in this contract.

**Non-spec defaults LOCKED:**
- The `_tier_for_depth(eff_stack_bb)` helper returns `(256, 128, 64)` for 15–150 BB, `(128, 64, 32)` for 150–200 BB, `(64, 32, 16)` for 200–250 BB (per spec §6 table). When the abstraction artifact for the requested tier does not exist on disk, raise `ValueError` with message pointing at `precompute-abstraction --bucket-counts X,Y,Z`.
- All `HUNLConfig` mutations for the blueprint pass go via `dataclasses.replace(config, ...)` — never mutate a frozen dataclass directly.

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from your two files. **Signature drift breaks Agent B's `subgame_refiner.py` consumers and Agent C's tests + Rust port.** Type hints required (mypy --strict).

### `poker_solver/preflop_solver.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.blueprint import BlueprintResult
from poker_solver.hunl import HUNLConfig
from poker_solver.hunl_solver import HUNLSolveResult
from poker_solver.profiler.memory import MemoryReport
from poker_solver.subgame_refiner import (
    SubgameKey,
    SubgameRefinementResult,
)


@dataclass(frozen=True)
class PreflopSolveResult(HUNLSolveResult):
    """First end-to-end HUNL preflop → river solve result.

    Subclasses HUNLSolveResult (which subclasses SolveResult per N7 lock).
    Adds the blueprint, the refined subgame strategies, and the dispatch
    metadata so downstream PRs (PR 10 GUI, PR 11 spot library) can present
    the combined strategy table to the user.
    """
    blueprint_strategy: dict[str, list[float]]
    refined_subgames: dict[SubgameKey, SubgameRefinementResult]
    unrefined_subgames: list[SubgameKey]
    dispatched_to_pushfold: bool = False  # True iff eff_stack_bb <= 15
    blueprint_memory_report: Optional[MemoryReport] = None


def solve_hunl_preflop(
    config: HUNLConfig,
    abstraction: Optional[AbstractionTables] = None,
    *,
    blueprint_iterations: int = 50_000,
    refine_iterations: int = 10_000,
    reach_threshold: float = 1e-3,
    max_memory_gb: float = 14.0,
    seed: Optional[int] = None,
    log_every: Optional[int] = None,
    on_progress: Optional[Callable[[int, float, MemoryReport], None]] = None,
) -> PreflopSolveResult:
    """First end-to-end HUNL preflop → river solver in the Python tier.

    Stages:
      1. Validate config; dispatch to push/fold chart if eff_stack_bb <= 15
         (then the result is wrapped as PreflopSolveResult with
         dispatched_to_pushfold=True; refined_subgames={}; unrefined_subgames=[];
         blueprint_strategy={}).
      2. Reject eff_stack_bb > 250 with ValueError.
      3. Construct coarsened HUNLConfig for the blueprint pass; load
         abstraction tier via _tier_for_depth(eff_stack_bb) if abstraction
         is None.
      4. Build blueprint via build_blueprint(...) — produces BlueprintResult.
      5. Identify reachable subgames (reach_prob > reach_threshold).
      6. For each reachable subgame, call refine_subgame(...) (Agent B's
         public surface). Drop previous solver state between subgames
         (gc.collect()) per spec §12.
      7. Assemble PreflopSolveResult with the combined strategy table
         (preflop from blueprint, postflop from refined where available,
         postflop from blueprint coarse strategy for the unrefined tail).

    Args:
        config: HUNLConfig with starting_street == Street.PREFLOP. Rake must
            be zero (PR 3 invariant preserved).
        abstraction: Optional pre-loaded AbstractionTables. If None, the
            solver loads the tier-appropriate artifact via _tier_for_depth.
        blueprint_iterations: Hard cap on blueprint DCFR iterations.
            Default 50_000.
        refine_iterations: Per-subgame DCFR iterations during refinement.
            Default 10_000.
        reach_threshold: Subgames with reach_prob <= threshold are NOT
            refined; they use the blueprint's coarse strategy. Default 1e-3.
        max_memory_gb: Hard ceiling per blueprint solve AND per subgame
            refinement. Exceeding raises MemoryError. Default 14.0.
        seed: Optional seed for deterministic re-runs. Threads through to
            DCFR + Agent B's refine_subgame.
        log_every: When set, snapshot exploitability + memory between
            chunks. Default None (snapshot once at end).
        on_progress: PR 10b launch-readiness hook (cf.
            `docs/pr10_prep/pr10b_spec.md` lines 152-156). When non-None,
            called every `log_every` iterations with
            `(iteration_number, current_exploitability_bb, memory_snapshot)`.
            `memory_snapshot: MemoryReport` is re-imported from
            `poker_solver.profiler.memory`. Threaded down to
            `build_blueprint(...)` during blueprint pass and to
            `refine_subgame(...)` (which threads it into PR 5's
            `solve_hunl_postflop`) during refinement. Cancellation is NOT
            in this contract — PR 10a handles via a separate flag.

    Returns:
        PreflopSolveResult covering the combined strategy table + diagnostic
        sub-reports.

    Raises:
        ValueError: starting_street != PREFLOP; eff_stack_bb > 250;
            rake_rate != 0; abstraction tier artifact not found on disk.
        MemoryError: blueprint or any subgame refinement exceeds
            max_memory_gb. e.args[1] carries the partial MemoryReport.
    """
    ...
```

**Internal helpers (you choose, but document them):**
- `_validate_preflop_config(config: HUNLConfig) -> None` — Stage 1.
- `_dispatch_pushfold_or_solve(config: HUNLConfig, eff_stack_bb: int, ...) -> PreflopSolveResult | None` — Stage 1/2 short-circuit. Returns `None` if no dispatch; returns a wrapped `PreflopSolveResult` if push/fold was used.
- `_tier_for_depth(eff_stack_bb: int) -> tuple[int, int, int]` — bucket-count tier per PR 9 §6 table.
- `_identify_reachable_subgames(blueprint: BlueprintResult, threshold: float) -> tuple[list[SubgameKey], list[SubgameKey]]` — returns `(reachable, unreached)`.
- `_assemble_strategy_table(blueprint: BlueprintResult, refined: dict[SubgameKey, SubgameRefinementResult]) -> dict[str, list[float]]` — combined strategy per spec §8.5.

### `poker_solver/blueprint.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from poker_solver.abstraction.buckets import AbstractionTables
from poker_solver.hunl import HUNLConfig
from poker_solver.profiler.memory import MemoryReport
from poker_solver.subgame_refiner import SubgameKey


@dataclass(frozen=True)
class BlueprintResult:
    """Output of the coarse blueprint pass (Pluribus-style).

    Contains the strategy at every reached preflop infoset + the per-leaf
    reach probabilities + per-subgame leaf values, plus the memory report
    so the orchestrator can decide whether to tier-tighten on retry.
    """
    strategy: dict[str, list[float]]
    reach_probs: dict[str, float]
    leaf_values: dict[SubgameKey, float]
    exploitability_history: list[float]
    memory_report: MemoryReport


def build_blueprint(
    config: HUNLConfig,
    abstraction: AbstractionTables,
    *,
    postflop_menu: tuple[float, ...] = (0.75,),
    postflop_raise_cap: int = 1,
    iterations: int = 50_000,
    max_memory_gb: float = 14.0,
    seed: Optional[int] = None,
    log_every: Optional[int] = None,
    on_progress: Optional[Callable[[int, float, MemoryReport], None]] = None,
) -> BlueprintResult:
    """Build the coarse preflop+postflop blueprint at the given stack depth.

    Constructs a coarsened HUNLConfig (postflop_menu, postflop_raise_cap
    coarsened; preflop unchanged) via dataclasses.replace, attaches the
    abstraction, opts in to the canonical-class preflop chance generator
    (via the new hunl.py opt-in flag), runs DCFR for `iterations` with
    MemoryProbe instrumentation, then walks the preflop tree to compute
    per-infoset reach probabilities + per-subgame leaf values.

    Args:
        config: HUNLConfig with starting_street == Street.PREFLOP. Must
            pass _validate_preflop_config.
        abstraction: AbstractionTables (the tier-appropriate artifact).
        postflop_menu: Coarsened postflop bet-size fractions. Default
            (0.75,) per spec §7.1.
        postflop_raise_cap: Postflop raise cap during the blueprint pass.
            Default 1 per spec §7.1.
        iterations: Blueprint DCFR iterations. Default 50_000.
        max_memory_gb: Hard ceiling. Exceeding raises MemoryError.
        seed: Optional for deterministic re-runs.
        log_every: When set, snapshot memory + exploitability between chunks.
        on_progress: PR 10b launch-readiness hook (cf.
            `docs/pr10_prep/pr10b_spec.md` lines 152-156). When non-None,
            called every `log_every` iterations during the blueprint DCFR
            loop with `(iteration_number, current_exploitability_bb,
            memory_snapshot)`. Passed through unchanged from
            `solve_hunl_preflop`'s caller.

    Returns:
        BlueprintResult with strategy, reach_probs, leaf_values,
        exploitability_history, memory_report.

    Raises:
        ValueError: invalid config (non-PREFLOP starting_street, non-zero
            rake, etc.).
        MemoryError: total memory exceeds max_memory_gb. e.args[1] is the
            partial MemoryReport.
    """
    ...
```

**Internal helpers (you choose, but document them):**
- `_build_coarse_hunl_config(config: HUNLConfig, postflop_menu, postflop_raise_cap, abstraction) -> HUNLConfig` — Stage A.
- `_compute_reach_probabilities(solver, game) -> dict[str, float]` — walks the tree under the average strategy; standard CFR reach recurrence.
- `_extract_subgame_keys(reach_probs, game) -> dict[SubgameKey, float]` — every preflop terminal that enters postflop becomes a `SubgameKey` entry.

## Cross-agent contracts (Agent B's surface; do NOT reach inside)

Treat these as opaque. Import only the names; do not depend on internals:

```python
# From poker_solver.subgame_refiner (Agent B's module):

@dataclass(frozen=True)
class SubgameKey:
    starting_street: Street            # FLOP / TURN / RIVER
    board: tuple[Card, ...]            # empty at preflop-leaf level; populated
                                       # during refinement when board is dealt
    pot: int                           # integer cents
    p0_contribution: int               # integer cents
    p1_contribution: int               # integer cents
    preflop_betting_history: str       # canonical PR 3 history encoding

@dataclass(frozen=True)
class SubgameRefinementResult:
    refined_strategy: dict[str, list[float]]
    game_value: float                  # BB
    exploitability: float              # BB/100
    p0_range: dict[str, float]
    p1_range: dict[str, float]

def refine_subgame(
    subgame_key: SubgameKey,
    blueprint: BlueprintResult,
    abstraction: AbstractionTables,
    *,
    iterations: int = 10_000,
    max_memory_gb: float = 14.0,
    seed: Optional[int] = None,
) -> SubgameRefinementResult: ...
```

You call `refine_subgame(...)` once per high-reach subgame. Do NOT inspect Agent B's internal range-extraction or warm-start logic; the public contract is the boundary. If you find an awkward call site (e.g., Agent B needs additional context from the blueprint that's not in `BlueprintResult`), file an interface-adjustment note for the orchestrator — do NOT silently modify Agent B's signature.

## PR 9 hunl.py modification (canonical-class preflop chance generator)

Per spec §5: add `_enumerate_preflop_hole_outcomes_canonical(self) -> Iterator[ChanceOutcome]` to `HUNLPoker`. This generator yields the 169 × 169 = 28,561 hand-class × hand-class outcomes (where each class is one of the 169 strategically-unique starting hands per PR 4 §7.12). Combinatorial weights per class:

- Pairs (AA, KK, …, 22): **6 combos each** (4 suits choose 2).
- Suited non-pairs (AKs, AQs, …): **4 combos each** (one per suit).
- Offsuit non-pairs (AKo, AQo, …): **12 combos each** (4 × 3).

Total: 13 pairs × 6 + 78 suited × 4 + 78 offsuit × 12 = 78 + 312 + 936 = 1326 combos for one player. The (hero_class, villain_class) outcome weight is `hero_combos × villain_combos_after_blockers / total_pairs`, where `villain_combos_after_blockers` respects suit conflicts (e.g., when hero has AA, villain cannot have AA in the 4-suit world; 6 combos hero × `(C(4-2, 2)) = C(2,2) = 1` combos villain = wrong because canonical classes abstract over suits — see spec §13 risk row 6).

**Critical correctness:** the weights must produce a total probability of 1.0 across all (hero_class, villain_class) outcomes after accounting for blockers. Validate via the brute-force enumeration check that Agent C's test `test_preflop_canonical_chance_weights_correct` will exercise. Document the formula in a code comment with citations to PR 4 §7.12 and PR 9 §5.

**Opt-in protocol (per §14 #8):** the existing `_enumerate_preflop_hole_outcomes()` is preserved unchanged. Choose ONE of these activation patterns:

- **Option A (recommended):** add a per-`HUNLConfig` opt-in field, e.g., `preflop_chance_strategy: Literal["full", "canonical_classes"] = "full"`, and have `HUNLPoker.chance_outcomes(state)` switch on this field. `BlueprintResult` builder sets the field via `dataclasses.replace(config, preflop_chance_strategy="canonical_classes")` before passing to the solver.
- **Option B:** add a `chance_strategy` kwarg directly on `chance_outcomes(state, *, strategy="full")`. Slightly more invasive (the calling convention changes); A is cleaner.

Pick A unless you discover a blocker. Document the choice in the code + the implementor report.

**`Iterator[ChanceOutcome]` shape:** match the existing `_enumerate_preflop_hole_outcomes()` return type exactly. If the existing one yields tuples `(probability, outcome_state)`, your canonical version yields the same shape with `outcome_state` being a `HUNLState` after hole-card deal. The `probability` field carries the combinatorial weight (sums to 1.0 across all yields).

## Dispatch composition (canonical per PR 9 §6 — you implement this)

The full `solver.solve()` body for HUNL games becomes:

```python
def solve(game, iterations, ...):
    if isinstance(game, HUNLPoker):
        eff_stack_bb = game.config.starting_stack // game.config.big_blind

        # Short-stack short-circuit FIRST (regardless of starting_street).
        if eff_stack_bb <= 15:
            return pushfold.solve_pushfold(game.config)  # PR 3.5

        # Stack-depth ceiling.
        if eff_stack_bb > 250:
            raise ValueError(
                f"Stack depth {eff_stack_bb} BB > 250 BB max."
            )

        # Then dispatch by starting_street.
        if game.config.starting_street >= Street.FLOP:
            return hunl_solver.solve_hunl_postflop(game.config, ...)  # PR 5

        if game.config.starting_street == Street.PREFLOP:
            abstraction = (
                provided_abstraction
                if provided_abstraction is not None
                else load_abstraction(_path_for_tier(eff_stack_bb))
            )
            return preflop_solver.solve_hunl_preflop(
                game.config,
                abstraction=abstraction,
                ...
            )  # PR 9 — YOUR branch

        raise ValueError(f"Unsupported starting_street: {game.config.starting_street}")

    # Non-HUNL games (Kuhn, Leduc) go to the existing DCFR path.
    ...
```

**Ordering invariant:** push/fold MUST short-circuit before postflop AND preflop branches. A `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` (15 BB preflop) hits the push/fold branch, NOT the preflop solver. The locked tests (`test_preflop_dispatch_pushfold_at_15bb`, `test_preflop_dispatch_solver_at_16bb`, `test_preflop_dispatch_error_at_251bb`) verify this.

**Existing PR 3.5 branch:** if PR 3.5's `if eff_stack_bb <= 15: return pushfold.solve_pushfold(...)` is already present in `solver.py`, do NOT duplicate it; ensure the >250 BB error and the preflop branch are added AFTER the existing short-circuit. If PR 3.5's branch is missing or worded differently, prefer reconciling to the canonical PR 9 §6 wording.

## Critical correctness items

### 1. Push/fold short-circuit precedence (THE dispatch invariant)

Tests `test_preflop_dispatch_pushfold_at_15bb`, `test_preflop_dispatch_solver_at_16bb`, `test_preflop_dispatch_error_at_251bb` lock the boundary behavior. Verify in your own smoke tests (manual, not in `tests/`) that:
- `HUNLConfig(starting_stack=1500, starting_street=Street.PREFLOP)` → push/fold (1500 cents = 15 BB at 1 BB = 100 cents).
- `HUNLConfig(starting_stack=1600, starting_street=Street.PREFLOP)` → preflop solver.
- `HUNLConfig(starting_stack=25_100, starting_street=Street.PREFLOP)` → ValueError mentioning the 250 BB cap.
- `HUNLConfig(starting_stack=1500, starting_street=Street.FLOP, initial_board=(...))` → push/fold (the short-circuit takes precedence over the postflop branch per the spec).

### 2. Blueprint produces a strategy for every reached preflop infoset

For every `(hand_class, betting_history)` pair where `reach_prob > 0`, `BlueprintResult.strategy[infoset_key]` exists. For unreached infosets (probability 0 under both players' strategies), the entry may be absent OR may carry the default uniform — document your choice. (Spec §10.1 test 4 enforces this.)

### 3. Reach probabilities sum to 1.0 at preflop root

After computing per-infoset reach probabilities, `sum(reach_probs[infoset] for infoset in root_infosets) == pytest.approx(1.0, abs=1e-6)`. The root infosets are the first-action SB infosets for each of the 169 hand classes, weighted by their combinatorial probability under uniform-random opener ranges.

### 4. Memory budget enforcement inherits PR 5's 10% calibration tolerance

Per spec §12 + consistency review I4: the blueprint pass AND each subgame refinement inherit PR 5's `psutil` RSS calibration check (10% tolerance). If `MemoryReport.rss_calibration_error` exceeds 0.10, log a warning but do NOT abort — the calibration tolerance is documented but informational. Hard abort only when `MemoryReport.total_gb > max_memory_gb`.

Pattern (Agent A constructs the probe; reads `report.total_gb`; raises `MemoryError` with the partial report as `args[1]`):

```python
probe = MemoryProbe(solver, include_abstraction=abstraction)
# ... iteration loop ...
report = probe.snapshot()
if report.total_gb > max_memory_gb:
    raise MemoryError(
        f"Memory budget exceeded: {report.total_gb:.2f} GB > "
        f"{max_memory_gb} GB. River layer: {report.river_ratio:.1%}. "
        f"Consider tightening abstraction tier or restricting menu. "
        f"Partial report attached as args[1].",
        report,
    )
```

Between subgames, explicitly drop the previous solver's state (`del solver; gc.collect()`) so the next subgame starts from a clean baseline (spec §12).

### 5. Combined exploitability target: < 0.05 BB/hand on Pio 100 BB fixture

Per spec §7.4 + §17 (consistency review I5): the end-to-end deliverable target is exploitability < 0.05 BB/hand on the Pio-published 100 BB cash-game validation fixture (HU NL, no ante, $0.50/$1.00 blinds). Agent C's `test_combined_exploitability_under_0_05_bb_per_hand` will exercise this. Your job is to make sure the orchestration produces enough convergence quality to clear the bar at the spec's default iteration counts; if it doesn't, that's a finding to flag (the answer may be "bump iterations to 100k blueprint + 20k refine" not "weaken the bar").

### 6. Canonical-class preflop chance generator combinatorial weights

The 169 × 169 outcome weights must sum to 1.0 after blocker accounting. The combinatorial weight per (hero_class, villain_class) pair is computed in your `_enumerate_preflop_hole_outcomes_canonical()`. Validate via a brute-force enumeration on the standard 52-card deck:

```python
# Sanity (pseudo):
total = sum(prob for prob, _ in game._enumerate_preflop_hole_outcomes_canonical())
assert abs(total - 1.0) < 1e-9
```

Spec §13 risk row 6 explicitly calls this out as a likely-bug-source. If your weights are off by even a small amount (e.g., 0.99 vs 1.00), the blueprint's strategy will be biased; refinement won't fix it. Get this right.

### 7. CLI integration end-to-end

After your CLI edits, the following must run to completion (small iteration counts for smoke):

```
poker-solver solve --game hunl --hunl-mode preflop --stacks 100 \
    --blueprint-iterations 100 --refine-iterations 50 \
    --reach-threshold 0.05 --abstraction /tmp/tiny_abs.npz \
    --max-memory-gb 14
```

And output a `PreflopSolveResult` printed nicely (preflop strategy + refined-subgame count + unrefined long tail + memory report).

### 8. Deterministic re-runs

Same `seed` + same `config` + same `abstraction` → identical strategy table within float tolerance. The blueprint AND each refinement is deterministic given the seed; your orchestration must not introduce nondeterminism via dict iteration order. (Python 3.7+ guarantees insertion-order; ensure your construction order is stable.)

### 9. Existing tests (PR 1 through PR 8) pass unchanged

Your dispatch edits to `solver.py` MUST NOT perturb Kuhn / Leduc / HUNL-postflop / push-fold behavior. The push/fold short-circuit's precedence must be exactly the same as PR 3.5's existing behavior. Run `pytest -x` after your edits and confirm all existing tests pass.

### 10. `mypy --strict` clean on new + touched code

`mypy --strict poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py` reports zero errors.

## CLI behavior (your extension to `cli.py`)

Per spec §5:

```
poker-solver solve --game hunl --hunl-mode preflop \
    --stacks 100 \
    [--ante 0] \
    [--blueprint-iterations 50000] \
    [--refine-iterations 10000] \
    [--reach-threshold 0.001] \
    [--abstraction PATH] \
    [--max-memory-gb 14.0]
```

- `--hunl-mode preflop`: canonical name (also accept `full` as deprecated synonym; emit a `DeprecationWarning` when `full` is used).
- `--stacks INT`: effective stack depth in BB (default 100).
- `--ante INT_CENTS`: ante in cents (default 0; PR 9 solves at ante=0 by default per spec §2).
- `--blueprint-iterations INT`: default 50_000.
- `--refine-iterations INT`: default 10_000.
- `--reach-threshold FLOAT`: default 1e-3.
- `--abstraction PATH`: path to PR 4's `.npz` artifact (the tier-appropriate one — `256_128_64.npz` for 25–150 BB, etc.). If omitted, the CLI errors with a message pointing at `precompute-abstraction --bucket-counts X,Y,Z` (where X,Y,Z is the tier per `_tier_for_depth`).
- `--max-memory-gb FLOAT`: default 14.0.

The `--hunl-mode full` `NotImplementedError` (which has pointed at "PR 9" since PR 5) is replaced with `solve_hunl_preflop(...)` wiring + a `DeprecationWarning` for the `full` name.

Output: print the blueprint strategy summary + refined-subgame count + unrefined-tail count + memory report (per-street + total + RSS + river ratio).

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — Brown's public reference. Read-only architectural inspiration on solver orchestration. The two-tier shape is the validation case for our architecture.
- `references/code/slumbot2019/` (**MIT**) — Slumbot's blueprint + refinement architecture for HUNL. Read-only.
- Pluribus paper (`references/papers/pluribus_brown_2019_science.pdf`) — algorithmic reference, not a code source. Cite specific page numbers per spec §16.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration. No code copy. If you cite a pattern from this repo, do so in a docstring comment that says "pattern inspired by; no code copied" and derive from scratch.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a blueprint + refinement implementation and want to use it, ground it in the Pluribus paper or the PR 9 spec. When in doubt, prefer the spec's stated approach.

If you copy a non-trivial code snippet (>~5 LOC) from an MIT-licensed source, add an attribution comment at the top of the function:
```python
# Pattern from slumbot2019/<path>.cpp (MIT, attribution required).
# Reference: references/code/slumbot2019/<path>.cpp
```

## Quality bar

- **ruff clean:** `ruff check poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py` reports zero issues.
- **black clean:** `black --check` on the same set reports no changes.
- **mypy strict-clean on new + touched code:** `mypy --strict poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py` reports zero errors.
- **No new third-party deps.** Imports: `numpy`, `psutil` (already a dep from PR 5), `poker_solver.*`, stdlib only.
- **All existing tests pass unchanged.** Run `pytest -x` after your work lands. Your dispatch edits are surgical; the existing PR 1 through PR 8 behavior must be preserved bit-for-bit.
- **Code size budget: ~550 LOC total** (`preflop_solver.py` ~300 LOC + `blueprint.py` ~250 LOC per spec §9) + minimal additive edits to the four touched files (~30 LOC each, mostly the dispatch branch, the CLI flags, the re-exports, the chance generator). Stay within budget; do not over-engineer.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md`.

If a fact is needed (e.g., "Pluribus uses MCCFR with sampling"), cite the specific source: `references/papers/pluribus_brown_2019_science.pdf` page 3 (per PR 9 §16).

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py
black --check poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py

# 2. Type-check
mypy --strict poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/hunl.py poker_solver/solver.py poker_solver/cli.py poker_solver/__init__.py

# 3. Existing test suite must still pass (PR 1 through PR 8)
pytest -x 2>&1 | tail -20

# 4. Dispatch smoke (manual, not in tests/)
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.solver import solve

# 15 BB → push/fold
cfg = HUNLConfig(starting_stack=1500, starting_street=Street.PREFLOP)
result = solve(HUNLPoker(cfg), iterations=1)
assert getattr(result, 'dispatched_to_pushfold', False) is True, 'dispatch broken at 15 BB'

# 16 BB → preflop solver (will likely fail because no abstraction artifact;
# expect ValueError mentioning precompute-abstraction)
cfg = HUNLConfig(starting_stack=1600, starting_street=Street.PREFLOP)
try:
    result = solve(HUNLPoker(cfg), iterations=1)
except ValueError as e:
    msg = str(e)
    assert 'precompute-abstraction' in msg or 'abstraction' in msg.lower()
    print(f'16 BB dispatch OK (errored as expected on missing abstraction): {msg[:80]}')
print('dispatch smoke OK')
"

# 5. Canonical-class chance generator weight check
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
cfg = HUNLConfig(starting_stack=10000, starting_street=Street.PREFLOP)
game = HUNLPoker(cfg)
total = sum(prob for prob, _ in game._enumerate_preflop_hole_outcomes_canonical())
assert abs(total - 1.0) < 1e-6, f'canonical-class weights sum to {total}, not 1.0'
print(f'canonical-class chance generator weights sum to {total:.9f}')
"

# 6. >250 BB error
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker, Street
from poker_solver.solver import solve
cfg = HUNLConfig(starting_stack=25_100, starting_street=Street.PREFLOP)
try:
    solve(HUNLPoker(cfg), iterations=1)
    raise AssertionError('expected ValueError')
except ValueError as e:
    assert '250' in str(e), f'expected 250 in error message; got: {e}'
    print(f'>250 BB error OK: {e}')
"

# 7. CLI smoke (will probably need a tiny abstraction artifact built first)
# poker-solver solve --game hunl --hunl-mode preflop --stacks 100 \
#     --blueprint-iterations 50 --refine-iterations 25 \
#     --reach-threshold 0.05 --abstraction /tmp/tiny.npz
```

If any of the above fails, fix the issue before reporting done. If a smoke check reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with LOC; files modified with line-delta.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. The opt-in protocol you chose for the canonical-class chance generator (Option A or B; explain).
5. Combinatorial-weight sum sanity-check result (should be 1.0 to 6+ decimals).
6. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
7. License attributions you added (if any).
8. Confirmation that `on_progress` is threaded through `solve_hunl_preflop` → `build_blueprint` (blueprint pass) AND `solve_hunl_preflop` → `refine_subgame` (refinement pass). Cite the line(s) where you invoke the callback.
