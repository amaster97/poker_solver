# PR 9 spec — HUNL preflop solve (Python + Rust tiers)

**Updated 2026-05-21 per consistency review:** (a) dispatch composition in §6 is now declared canonical (PR 3.5 + PR 5 cross-reference this section for the full short-stack / postflop / preflop / error routing); (b) diff-test tolerance in §10.4 aligned to PR 6/7/8 cluster (5e-3 per-action, 1e-3 per-spot game value — was 1e-4) with justification; (c) end-to-end exploitability target added to §7 / §17 (< 0.05 BB/hand on the Pio 100 BB cash-game validation fixture, combined preflop+refinement); (d) §13 risk row referencing the old 1e-4 tolerance updated to the new figure.

## 1. Goal

Ship the **first end-to-end HUNL preflop → river solve** in both tiers (Python reference + Rust production), completing the v1 deliverable PLAN.md §1 commits to: *"HUNL postflop + preflop together."* PR 9 builds the full preflop tree (open-raise / 3-bet / 4-bet / 5-bet ladder, blind structure, postflop continuations as child subtrees) and produces an **average strategy table covering every preflop infoset** at every supported stack depth (15 BB through 250 BB; the 2–15 BB short-stack regime continues to dispatch to PR 3.5's push/fold charts).

The strategy table must be:

1. **Per-stack-depth.** A separate solve per depth in {25, 50, 75, 100, 125, 150, 175, 200, 250} BB (the depths the user picks; spec default is these nine). The PLAN.md stack-depth tier table dictates the card abstraction granularity per depth (256/128/64 default; 128/64/32 from 150–200; 64/32/16 from 200–250).
2. **Plumbed through `solve(...)`.** `poker-solver solve --game hunl --hunl-mode preflop --stacks 100bb` returns a `HUNLSolveResult` (the PR 5 dataclass) extended with a preflop-specific subreport.
3. **Validated against published references.** SB open-raise frequency at 100 BB matches published PioSolver outputs within 5%. BB defense vs 3-bet ≥ MDF (minimum-defense frequency). At least two intuition gauntlet tests covering polarization on 100 BB 4-bet-or-fold spots.

The approach is **blueprint + subgame refinement**, the Pluribus pattern (Brown & Sandholm 2019). Solving the full preflop+postflop tree with the full action menu at the full card-abstraction granularity is RAM-prohibitive on a 16 GB MacBook (per PLAN.md §1: ~10–14 GB for *postflop alone* at 100 BB; the preflop multiplier explodes that). Pluribus solves the same problem on a *64-core 512 GB server* (Brown & Sandholm 2019, Science, page 3: *"The blueprint strategy for Pluribus was computed in 8 days on a 64-core server… less than 512 GB of memory"*); we cannot replicate that infrastructure. The blueprint+refinement pattern shrinks the offline solve to MacBook scale and pushes finer-grained search into the per-spot refinement step.

## 2. What PR 9 does NOT do

- **Push/fold mode (≤15 BB).** Handled by PR 3.5's static chart lookup (`poker_solver/charts/pushfold_v1.json`). PR 9's CLI dispatches `stacks ≤ 15 BB` to PR 3.5 unchanged; the preflop solver only runs for `15 < stacks ≤ 250 BB`. The boundary handoff at 15 BB is tested explicitly (see §10).
- **Ante UI configurability.** The HUNL engine accepts `HUNLConfig(ante=X)` since PR 3 (see `poker_solver/hunl.py:88-103`). PR 9 solves at `ante=0` by default; user can override via `--ante INT_CENTS` on the CLI. The UI surface for ante goes in PR 10.
- **Multi-table tournaments / ICM / bounties.** Out of v1 scope per PLAN.md §1 ("Explicitly out of scope (v1)").
- **3-handed / 6-max preflop.** Pluribus is 6-max but takes a 64-core server. HUNL only. Per PLAN.md §1.
- **Rake.** PR 3's `HUNLConfig.__post_init__` asserts `rake_rate == 0.0`; PR 9 preserves that. Rake support is a v2 follow-up.
- **Continuous bet sizing.** Same 6-fraction discrete menu PR 3 established (33/75/100/150/200% + all-in). Pluribus likewise discretizes (Brown & Sandholm 2019, page 2: *"Pluribus only considers a few different bet sizes at any given decision point"*).
- **Real-time depth-limited search at decision time.** Pluribus does this during live play (Brown & Sandholm 2019, page 4); PR 9 ships *offline* blueprint+subgame refinement, where the subgame refinement is also offline (precomputed). Online search is a Phase-4 roadmap item.
- **Asymmetric ranges.** Both players start with a uniform-random opener range — the standard HU full-game configuration. Per-position custom ranges (e.g., exploitative analysis against a fixed opponent range) is a node-locking follow-up (PLAN.md §1 "Features beyond v1").
- **New abstraction artifact.** Reuses PR 4's `AbstractionTables` unchanged. Preflop stays *lossless* (169 strategically-unique hand classes via suit-isomorphism, per PR 4 §7.12).
- **No fundamentally new solver.** Same `DCFRSolver` (`poker_solver/dcfr.py`) as PRs 1–5, same hyperparameters (α=1.5, β=0, γ=2.0). PR 9 wires the bigger tree to it; it doesn't change the algorithm.

## 3. Conceptual architecture

### 3.1 Why preflop is harder than postflop

PR 5 solved postflop subtrees on a fixed starting board. PR 9 must solve the **preflop tree whose leaves are flop subtrees, whose leaves are turn subtrees, whose leaves are river subtrees**. Every postflop solve PR 5 ships is *one chance subtree* of a preflop leaf.

Concretely:

- **Postflop tree (PR 5):** start on a fixed board (3 / 4 / 5 cards), enumerate actions, transition through chance nodes. Card abstraction collapses the 1326-hand × 22100-flop space to 256 buckets. Tree fits in ~10–14 GB at 100 BB with the 6-size menu and 3-cap.
- **Preflop tree (PR 9):** start with no board, enumerate preflop actions, each preflop terminal that reaches showdown is followed by *every* flop chance outcome → every flop subtree from PR 5. The branching factor of the chance node is 1755 strategically-unique flops (Pluribus and Libratus both use this number; see PR 4 §4 Stage 4). Each flop subtree is itself ~10⁵ infosets after abstraction.

The math: if PR 5's postflop subtree at 100 BB has N_postflop infosets, then the full preflop+postflop tree at 100 BB has roughly `N_preflop * 1755 * N_postflop` total infosets (modulo overlap from abstraction collapsing). N_preflop is small (~10⁴ after action abstraction); the explosion is multiplicative through the flop chance node.

### 3.2 Two-stage solve: blueprint + subgame refinement

The Pluribus pattern (Brown & Sandholm 2019, page 2: *"The core of Pluribus's strategy was computed via self play, in which the AI plays against copies of itself… Pluribus's self play produces a strategy for the entire game offline, which we refer to as the blueprint strategy"*) decomposes the solve:

1. **Blueprint pass (offline).** Solve the entire preflop+postflop game tree at *coarse* fidelity: tight card abstraction (256/128/64 default, or tier-tighter at deeper stacks per PLAN.md §1), restricted postflop action menu (1–2 bet sizes per node instead of the full 6, raise cap 1–2 instead of 3), moderate iteration count (~50k iterations of DCFR). The blueprint produces a strategy for every preflop and postflop infoset, but is *strategically coarse* on postflop (because the action menu and abstraction were tightened to make the tree fit).
2. **Subgame refinement pass (offline-batched).** For each preflop leaf that the blueprint reaches with non-trivial reach probability (above a threshold, e.g., > 0.001), re-solve the *postflop subtree* with the full PR 3 action menu (6 sizes + all-in, 3-cap) and the standard PR 4 abstraction tier. The refined postflop solve uses the blueprint's strategy as a **warm start** for the regret tables and as the **range-input** (the blueprint's preflop strategy defines the player ranges arriving at this postflop spot).

The combined output is the **refined strategy table**: blueprint for the preflop infosets, refined per-subgame strategies for the postflop infosets the blueprint reaches.

### 3.3 Why the blueprint is "good enough" at preflop

Pluribus (Brown & Sandholm 2019, page 4): *"The blueprint strategy for the entire game is necessarily coarse-grained owing to the size and complexity of no-limit Texas hold'em. Pluribus only plays according to this blueprint strategy in the first betting round (of four), where the number of decision points is small enough that the blueprint strategy can afford to not use information abstraction and have a lot of actions in the action abstraction. After the first round… Pluribus instead conducts real-time search to determine a better, finer-grained strategy."*

Translating to our setting:

- **Preflop has ~3.4k strategically-unique infosets** at the 169-hand × full-betting-tree level (4-cap, 6 sizes per node). That's small enough that the blueprint's preflop strategy is *not significantly compromised* by the coarse postflop continuation menu — the player still chooses among the full preflop menu, and the postflop EV (rolled up to preflop) averages over the coarse continuation.
- **Postflop has ~10⁶–10⁸ infosets** even abstracted. That's where the blueprint's coarseness matters. The subgame refinement step fixes this: by re-solving each reached postflop spot with the full menu + full abstraction tier, we recover strategies that match what a from-scratch postflop solve would produce.

The accuracy claim is: **post-refinement, every postflop infoset reached with probability > threshold has a strategy as good as PR 5's direct postflop solve would produce.** Preflop infosets inherit the blueprint's strategy directly. The unrefined long tail (preflop leaves below threshold) uses the blueprint's coarse strategy — acceptable since the blueprint *did* train on them, just at coarse fidelity.

### 3.4 Memory budget

The blueprint pass must fit in **~10–14 GB** (PLAN.md §1 default postflop budget; we burn a bit more for the preflop extension since preflop is lossless and adds ~10⁴ infosets). Subgame refinement uses the same budget per subgame, but only one subgame at a time (the others are pickled to disk between refinement rounds).

Empirical commitment: PR 5's profiler runs during the blueprint pass and reports per-street + per-tree memory. If the blueprint blows the 14 GB budget at any depth, we tighten the abstraction tier per the PLAN.md table:

| Stack depth | Card abstraction (flop/turn/river) | Blueprint postflop menu | Notes |
|---|---|---|---|
| 25–100 BB | 256 / 128 / 64 (default) | 1–2 sizes per node, 1-cap | Tightest tree |
| 100–150 BB | 256 / 128 / 64 (default) | 1–2 sizes, 1-cap | Stretch budget |
| 150–200 BB | 128 / 64 / 32 (tier 1) | 1 size, 1-cap | Tier-tightened |
| 200–250 BB | 64 / 32 / 16 (tier 2) | 1 size, 1-cap | Tier-tightened |

Subgame refinement always uses the full action menu (6 + all-in) and 3-cap regardless of stack depth.

### 3.5 Wiring diagram

```
┌──────────────────────────┐         ┌─────────────────────────────┐
│  poker_solver/cli.py     │────────▶│  poker_solver/solver.py     │
│  (extends preflop mode)  │         │  (routes preflop config →   │
│                          │         │   preflop_solver.solve_…)   │
└──────────────────────────┘         └─────────────┬───────────────┘
                                                   │
                                                   ▼
                ┌─────────────────────────────────────────────────────┐
                │   poker_solver/preflop_solver.py (NEW)              │
                │   solve_hunl_preflop(config, abstraction, depth, …) │
                │                                                     │
                │    1. validate config + dispatch (push/fold ≤15 BB) │
                │    2. build blueprint (calls blueprint.py)          │
                │    3. identify reachable postflop subgames          │
                │    4. refine each subgame (calls subgame_refiner)   │
                │    5. assemble combined strategy table              │
                │    6. produce PreflopSolveResult + MemoryReport     │
                └────────┬─────────────┬──────────────────────────────┘
                         │             │
                         ▼             ▼
        ┌────────────────────────┐ ┌──────────────────────────────┐
        │ poker_solver/          │ │ poker_solver/                │
        │   blueprint.py (NEW)   │ │   subgame_refiner.py (NEW)   │
        │ build_blueprint(...)   │ │ refine_subgame(...)          │
        └─────────────┬──────────┘ └──────────────┬───────────────┘
                      │                            │
                      ▼                            ▼
            ┌─────────────────────┐   ┌────────────────────────────┐
            │ HUNLPoker (PR 3)    │   │ solve_hunl_postflop (PR 5) │
            │   + abstraction     │   │ DCFRSolver (PR 1)          │
            │   + coarse menu     │   │ MemoryProbe (PR 5)         │
            └─────────────────────┘   └────────────────────────────┘
```

Rust mirror (PR 9 implementation, half the deliverable):

```
crates/cfr_core/src/preflop.rs       (NEW — Rust preflop tree)
crates/cfr_core/src/blueprint.rs     (NEW — Rust blueprint solver)
crates/cfr_core/src/subgame.rs       (NEW — Rust subgame refiner; wraps existing postflop port from PR 6)
crates/cfr_core/src/lib.rs           (extend PyO3 bindings)
```

Same shape as PR 6's pattern: Rust is a mechanical port of the Python reference, gated by differential tests.

## 4. Files to create

### Python

- **`poker_solver/preflop_solver.py`** — orchestration. Functions:
  - `solve_hunl_preflop(config: HUNLConfig, abstraction: AbstractionTables | None, *, blueprint_iterations: int = 50_000, refine_iterations: int = 10_000, reach_threshold: float = 1e-3, max_memory_gb: float = 14.0, seed: int | None = None, log_every: int | None = None, on_progress: Callable[[int, float, MemoryReport], None] | None = None) -> PreflopSolveResult`
    - **`on_progress` kwarg (added for PR 10b launch-readiness; consumer: `docs/pr10_prep/pr10b_spec.md` lines 152-156).** When non-None, the solver invokes `on_progress(iteration_number, current_exploitability_bb, memory_snapshot)` every `log_every` iterations (default 50 per PR 5 cluster). `memory_snapshot: MemoryReport` is re-imported from `poker_solver.profiler.memory`. Threaded down to `build_blueprint(...)` during the blueprint pass and to PR 5's `solve_hunl_postflop(...)` (via `refine_subgame(...)`) during refinement. Cancellation is NOT part of the `on_progress` contract — UI cancellation flows through a separate flag per PR 10a design.
  - `PreflopSolveResult` dataclass: extends `HUNLSolveResult` with `blueprint_strategy: dict[str, list[float]]`, `refined_subgames: dict[SubgameKey, SolveResult]`, `unrefined_subgames: list[SubgameKey]` (those below `reach_threshold`), `dispatched_to_pushfold: bool` (set when ≤15 BB).
  - Internal: `_validate_preflop_config`, `_dispatch_pushfold_or_solve`, `_identify_reachable_subgames`, `_assemble_strategy_table`.

- **`poker_solver/blueprint.py`** — coarse preflop blueprint pass. Functions:
  - `build_blueprint(config: HUNLConfig, abstraction: AbstractionTables, *, postflop_menu: tuple[float, ...] = (0.75,), postflop_raise_cap: int = 1, iterations: int = 50_000, seed: int | None = None, on_progress: Callable[[int, float, MemoryReport], None] | None = None) -> BlueprintResult`
    - **`on_progress` kwarg (PR 10b launch-readiness; cf. `docs/pr10_prep/pr10b_spec.md` lines 152-156).** Same signature/semantics as `solve_hunl_preflop`: called every `log_every` iterations during the blueprint DCFR loop with `(iteration_number, current_exploitability_bb, memory_snapshot)`. Caller (`solve_hunl_preflop`) passes its `on_progress` through unchanged.
  - `BlueprintResult` dataclass: `(strategy: dict[str, list[float]], reach_probs: dict[str, float], leaf_values: dict[SubgameKey, float], exploitability_history: list[float], memory_report: MemoryReport)`
  - Internal: `_build_coarse_hunl_config` (overrides `bet_size_fractions` and `postflop_raise_cap`), `_compute_reach_probabilities`, `_extract_subgame_keys`.

- **`poker_solver/subgame_refiner.py`** — postflop refinement against blueprint warm-start + ranges. Functions:
  - `refine_subgame(subgame_key: SubgameKey, blueprint: BlueprintResult, abstraction: AbstractionTables, *, iterations: int = 10_000, max_memory_gb: float = 14.0, seed: int | None = None, on_progress: Callable[[int, float, MemoryReport], None] | None = None) -> SubgameRefinementResult`
    - **`on_progress` kwarg (PR 10b launch-readiness; cf. `docs/pr10_prep/pr10b_spec.md` lines 152-156).** Passes through to PR 5's `solve_hunl_postflop(...)` which already exposes the same callback shape (see PR 5 spec). Semantics identical: `(iteration_number, current_exploitability_bb, memory_snapshot)`, invoked every `log_every` iterations during the refinement DCFR loop. `memory_snapshot: MemoryReport` re-exported from PR 5's `poker_solver.profiler.memory`.
  - `SubgameKey` dataclass: `(starting_street: Street, board: tuple[Card, ...], pot: int, p0_contribution: int, p1_contribution: int, preflop_betting_history: str)` — uniquely identifies a postflop subtree reachable from the preflop blueprint.
  - `SubgameRefinementResult` dataclass: `(refined_strategy: dict[str, list[float]], game_value: float, exploitability: float, p0_range: dict[str, float], p1_range: dict[str, float])`
  - Internal: `_extract_ranges_from_blueprint` (computes per-player range arriving at the subgame node from the blueprint's preflop strategy + chance probabilities), `_build_subgame_config` (constructs a `HUNLConfig` with `starting_street=Street.FLOP/TURN/RIVER`, `initial_board=...`, `initial_pot=...`, `initial_contributions=...`, full PR 3 action menu, range-weighted hole-card distributions), `_warm_start_from_blueprint` (initializes the DCFR regret tables from the blueprint's strategy where infoset keys overlap).

- **`tests/test_hunl_preflop_blueprint.py`** — blueprint convergence + reach-probability correctness (~6 tests).
- **`tests/test_hunl_preflop_refinement.py`** — subgame refinement correctness, parity with direct PR 5 postflop solve on the same subgame (~5 tests).
- **`tests/test_hunl_preflop_integration.py`** — end-to-end + push/fold handoff at 15 BB + published-ref comparisons (~4 tests).
- **`tests/fixtures/hunl_preflop_fixtures.py`** — fixture builders: `preflop_config_100bb()`, `preflop_config_50bb()`, `preflop_config_200bb()`, `tiny_synthetic_abstraction()` (reuses PR 5's fixture).

### Rust (port pattern from PR 6)

- **`crates/cfr_core/src/preflop.rs`** — preflop tree builder + DCFR driver (mechanical port of `blueprint.py` and `preflop_solver.py`). Mirrors `crates/cfr_core/src/tree.rs` (flat-array compact tree, indexed traversal).
- **`crates/cfr_core/src/subgame.rs`** — wraps PR 6's postflop solver in the subgame-refinement loop. Functions: `refine_subgame_rust(subgame_input) -> SubgameOutput`.
- **`crates/cfr_core/src/blueprint.rs`** — Rust blueprint solver (port of `blueprint.py`). Reuses PR 6's `dcfr.rs` core.
- **`tests/test_preflop_diff.py`** — differential test Python ↔ Rust on the preflop solve (~4 tests; matches the `tests/test_dcfr_diff.py` and `tests/test_leduc_diff.py` template).

## 5. Files to modify

- **`poker_solver/solver.py`** — extend the dispatch in `solve()`. After the existing PR 5 routing (postflop → `solve_hunl_postflop`), add a *preflop* branch: if `game.config.starting_street == Street.PREFLOP`, check stack depth:
  - `≤ 15 BB`: route to `pushfold.solve_pushfold` (PR 3.5).
  - `> 250 BB`: raise `ValueError("Stack depth > 250 BB exceeds supported range; max is 250 BB.")`
  - otherwise: route to `preflop_solver.solve_hunl_preflop`.
- **`poker_solver/cli.py`** — extend `--hunl-mode` choices to add `preflop`. Add CLI flags:
  - `--stacks INT` (in BB, default 100) — effective stack depth.
  - `--ante INT_CENTS` (default 0) — passes through to `HUNLConfig.ante`.
  - `--blueprint-iterations INT` (default 50_000)
  - `--refine-iterations INT` (default 10_000)
  - `--reach-threshold FLOAT` (default 1e-3)
  - `--abstraction PATH` (carries over from PR 4)
  - `--max-memory-gb FLOAT` (default 14.0)
  - The `--hunl-mode full` path (which raised `NotImplementedError` pointing at "PR 9" since PR 5) now wires to `preflop_solver.solve_hunl_preflop` directly. The `full` and `preflop` mode names become synonyms; one is documented as the canonical name and the other deprecated for v2.
- **`poker_solver/hunl.py`** — verify no edge cases. Specifically:
  - The `initial_state` code path for `starting_street == Street.PREFLOP` already exists (lines 215–240 of `hunl.py`). PR 9 audit confirms it handles antes, asymmetric stacks (currently rejected at config level — must remain so), and the `initial_hole_cards` pre-deal path used by tests.
  - The `chance_outcomes` path for the preflop hole-card deal (lines 291–296) materializes 1,624,350 outcomes lazily via `_enumerate_preflop_hole_outcomes()`. PR 9's blueprint *does not enumerate them all* — it walks them as a chance node with bucketed-by-class semantics (169 hand classes × 169 opponent classes = 28,561 outcomes, with proper suit-iso weighting). This is the **key PR 9 modification** to `hunl.py`: add a `_enumerate_preflop_hole_outcomes_canonical()` generator that yields the 169×169 unique hand-class chance outcomes with correct combinatorial weights. PR 9 detection: `if config.starting_street == Street.PREFLOP and chance_strategy == "canonical_classes"`, use the canonical generator; default behavior (full 1.6M outcomes) is preserved for any caller that explicitly opts in. The `BlueprintResult` builder passes `chance_strategy="canonical_classes"` automatically.
  - The 4-cap raise rule (preflop 4-cap, postflop 3-cap) is already implemented in `action_abstraction.py`. PR 9 audit confirms a walk through the 4-bet/5-bet ladder hits the cap correctly.
- **`poker_solver/__init__.py`** — re-export `solve_hunl_preflop`, `PreflopSolveResult`, `BlueprintResult`, `SubgameRefinementResult`, `SubgameKey`, `build_blueprint`, `refine_subgame`.
- **`pyproject.toml`** — no new third-party deps. (PR 5 already pulled in `psutil`; PR 9 reuses it.)
- **`crates/cfr_core/src/lib.rs`** — add PyO3 bindings for the new Rust modules (`solve_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`).

**NOT modified:**

- `poker_solver/dcfr.py` — DCFR algorithm unchanged. Hyperparameters (α=1.5, β=0, γ=2.0) unchanged.
- `poker_solver/abstraction/` — PR 4 artifact consumed read-only.
- `poker_solver/hunl_solver.py` (PR 5) — the postflop solver is called *by* `subgame_refiner.py` but not modified.
- `poker_solver/charts/pushfold_v1.json` — PR 3.5's chart unchanged; PR 9 only dispatches to it.

## 6. Stack-depth dispatch (CANONICAL — referenced by PR 3.5 §6 and PR 5 §6)

**This section is the authoritative source for HUNL solve dispatch ordering across PRs 3.5, 5, and 9.** PR 3.5 §6 and PR 5 §6 each cross-reference this section rather than restating the ordering; if dispatch logic ever needs to change, this is the one place to edit.

The CLI / solver picks the path based on effective stack depth AND `starting_street`:

```
eff_stack_bb = config.starting_stack // config.big_blind

# Short-stack short-circuit FIRST (regardless of starting_street).
# PR 3.5's chart only covers preflop pure jam/fold; if a user supplies
# starting_street >= FLOP at ≤15 BB stacks, the chart still wins
# (postflop play at sub-15 BB is rare; jam/fold dominates).
if isinstance(game, HUNLPoker) and eff_stack_bb <= 15:
    return pushfold.solve_pushfold(config)        # PR 3.5

# Stack-depth ceiling.
if isinstance(game, HUNLPoker) and eff_stack_bb > 250:
    raise ValueError(f"Stack depth {eff_stack_bb} BB > 250 BB max.")

# Then dispatch by starting_street.
if isinstance(game, HUNLPoker) and config.starting_street >= Street.FLOP:
    return hunl_solver.solve_hunl_postflop(config, ...)        # PR 5

if isinstance(game, HUNLPoker) and config.starting_street == Street.PREFLOP:
    abstraction_tier = _tier_for_depth(eff_stack_bb)
    return preflop_solver.solve_hunl_preflop(
        config,
        abstraction=load_abstraction(abstraction_tier),
        …
    )                                                             # PR 9
```

**Ordering invariant:** push/fold short-circuit MUST execute before the postflop and preflop branches. A `HUNLConfig(starting_street=Street.PREFLOP, starting_stack=1500)` (15 BB preflop) hits the push/fold branch, NOT the preflop solver — the chart is the right tool at that depth regardless of `starting_street`.

**Boundary tests (locked):** `test_preflop_dispatch_pushfold_at_15bb` (1500 cents = 15 BB → chart), `test_preflop_dispatch_solver_at_16bb` (1600 cents = 16 BB → preflop solver), `test_preflop_dispatch_error_at_251bb` (25100 cents → ValueError).

Where `_tier_for_depth` returns the bucket-count tuple per the PLAN.md §1 table:

| Stack depth | Bucket counts (flop/turn/river) |
|---|---|
| 15–150 BB | (256, 128, 64) — default |
| 150–200 BB | (128, 64, 32) — one tier tighter |
| 200–250 BB | (64, 32, 16) — two tiers tighter |

The user must supply the appropriate abstraction artifact path for the tier (built via `precompute-abstraction --bucket-counts 256,128,64` etc.). If the artifact doesn't exist, the solver errors with a clear message pointing at `precompute-abstraction`.

**Boundary handoff at 15 BB.** §13 Risks documents this as a hard cliff (chart at ≤15, solver at >15). Decision flagged for user (§14): whether to interpolate in a 12–18 BB band by averaging chart output with solver output, weighted by depth. **Default: hard cliff** (simpler, deterministic). User may override.

## 7. Blueprint design

### 7.1 Coarse postflop menu

The blueprint must fit in 14 GB at 100 BB. The dominant cost is postflop infoset count, which is `(bet_sizes_per_node × raise_cap) ** postflop_streets × bucket_counts_per_street`. Tightening menu + cap is the lever.

**Default blueprint postflop menu: 1 size (0.75 pot) + all-in, 1-cap.**

This gives 3 actions per non-cap postflop node (check/bet/all-in or call/raise/all-in), 2 actions at the cap (call/all-in or fold/all-in). Compared to the full menu (8 actions per non-cap node), the blueprint tree is ~3x smaller per street → ~27x smaller over flop/turn/river. Combined with the standard 256/128/64 abstraction, this should fit in 14 GB at 100 BB.

**Rationale for choosing 0.75-pot as the single size:** it's the modal cbet size in published solver outputs (PioSolver, GTO Wizard) and a reasonable middle ground between block (33%) and overbet (200%). The blueprint approximates EV by averaging over actually-used bet sizes; 0.75-pot is the least biased single choice.

**Alternative considered:** 2 sizes (e.g., 0.33 and 1.5 pot) + all-in, still 1-cap. Doubles the tree size but provides a richer blueprint — better at distinguishing thin value vs polarized lines. **Decision flagged (§14):** menu choice impacts blueprint quality vs subgame-refinement cost; user may want 2 sizes for better blueprint at the cost of slower offline pass.

### 7.2 Preflop menu unchanged

The blueprint **uses the full PR 3 preflop menu** (33/75/100/150/200% + all-in, 4-cap). Preflop is the focus of the blueprint's strategy quality; tightening preflop would defeat the purpose.

### 7.3 Card abstraction

Same as PR 5 default: 256/128/64 at 100 BB, tier-tightened per the §6 table at deeper stacks. **Preflop is lossless** (169 classes via suit-iso, per PR 4 §7.12).

### 7.4 Iteration count and exploitability targets

**Default: 50,000 blueprint iterations.** Pluribus solves its blueprint in ~12,400 CPU core-hours on a 64-core server (Brown & Sandholm 2019, page 3); proportionally scaling to a single MacBook core and a vastly smaller game (HU instead of 6-max), 50k iterations is the right order of magnitude.

**Per-stage exploitability targets:**

- **Blueprint:** exploitability < **0.5 BB/100** on every reached preflop infoset. Loose, because the blueprint is intentionally coarse — subgame refinement tightens postflop per-subtree.
- **Refined postflop subgame (per-subtree):** exploitability < **0.1 BB/100** for every subgame above the reach threshold (matches PR 5's Fixture 1 target — what a direct postflop solve achieves).
- **Unrefined postflop subgames (long tail, reach below threshold):** exploitability < **1 BB/100** (the blueprint's coarse strategy is what they inherit; not load-bearing because reach is small).

**End-to-end (combined preflop + refinement) exploitability target:** **< 0.05 BB/hand on the PR 9 validation fixture (HU NL cash-game 100 BB starting stacks, no ante, $0.50/$1.00 blinds — Pio's published reference setup).** Rationale: this matches PioSolver's published professional-standard accuracy (gtow_how_solvers_work.md cites "< 0.5% pot = professional standard"; on a 1.5 BB base pot that's ~0.0075 BB/hand exploitability — our 0.05 BB/hand is 7× looser, intentionally so given our coarser blueprint and the per-subgame heterogeneity of refinement quality). Tests this with `test_published_ref_sb_open_raise_100bb` (§10.3 #4) and `test_combined_exploitability_under_0_05_bb_per_hand` (added to §10.3 — see below).

If a more authoritative figure than 0.05 BB/hand surfaces during implementation (e.g., a Pio-published benchmark on the exact same spot we test against), substitute that figure; the spec's commitment is "within the published professional-standard band."

### 7.5 Reach probability and leaf-value caching

After the blueprint pass, walk the preflop tree to compute:

- **Reach probability per preflop infoset** = product of action probabilities for both players along the path. Computed via standard CFR reach-probability recurrence.
- **Leaf value per preflop terminal that enters a postflop subgame** = the EV the blueprint assigns to the subgame's root (already computed during the blueprint's CFR walk; cached here for the refinement step).

Both stored in the `BlueprintResult`.

### 7.6 Subgame identification

A *subgame* is uniquely identified by the (preflop betting history, postflop start configuration) at any preflop leaf where the game continues to postflop (i.e., at least one player called the prior bet, no one folded, no all-in run-out triggered). Encoded as `SubgameKey(starting_street=Street.FLOP, board=(), initial_pot=..., initial_contributions=..., preflop_betting_history=...)`.

Note: the *board* is empty at the SubgameKey level because the flop chance node hasn't dealt yet. The subgame refinement enumerates flops *inside* the refinement step — each refinement solves one subgame configuration across all 1755 strategically-unique flops.

## 8. Subgame refinement

### 8.1 Which subgames get refined

A subgame is refined if its **reach probability under the blueprint exceeds `reach_threshold` (default 1e-3)**. This filters out the long tail of preflop infosets that the blueprint reaches with near-zero probability (e.g., extreme 5-bet jam lines with 23o); refining them would burn compute for marginal strategy-table improvement.

Pluribus uses a similar pruning rule (Brown & Sandholm 2019, page 3: *"To speed up the blueprint strategy computation even further, actions with extremely negative regret are not explored in 95% of iterations"*). Our setup is the opposite direction — we refine only the *high-reach* subgames, not prune the low-reach ones during the blueprint pass — but the spirit is the same: don't burn compute on lines that don't matter.

### 8.2 Range input

The refinement step needs per-player ranges arriving at the subgame's root. These are computed from the blueprint:

- `p0_range[hand_class]` = `Σ_paths reach_prob(path_to_subgame_root | hand_class)` where `path_to_subgame_root` is all preflop betting paths leading to the subgame, and the reach is computed under the blueprint's strategy.
- Similarly `p1_range[hand_class]`.

The ranges are non-uniform (some hands reach a given subgame with high probability; others rarely). This is critical: a uniform range at a 3-bet pot would give wrong refinement results.

### 8.3 Warm start

The refined postflop solve uses the blueprint's strategy as a **regret-table warm start**:

- For every postflop infoset key that exists in *both* the blueprint and the refinement tree (same board + same betting history + same hand bucket), copy the blueprint's regret values into the refinement's regret table at iteration 0. Then run DCFR for `refine_iterations` more iterations.
- Infosets that exist only in the refinement tree (because the refinement has the full 6-size menu and the blueprint only had 1–2 sizes) start with zero regret.

This warm start typically reduces refinement iterations needed by 50–80% — the blueprint is already in the right neighborhood; refinement is a local polish.

### 8.4 Reuse PR 5's postflop solver

`refine_subgame()` constructs a `HUNLConfig` with `starting_street=Street.FLOP, initial_board=(), initial_pot=..., initial_contributions=..., bet_size_fractions=(0.33, 0.75, 1.00, 1.50, 2.00), include_all_in=True, postflop_raise_cap=3` (full PR 3 menu + 3-cap), then calls `hunl_solver.solve_hunl_postflop(refinement_config, abstraction, iterations=refine_iterations)`. The only PR 9-specific layer is range-input handling and warm-start regret loading; the rest is PR 5 unchanged.

### 8.5 Output: refined per-subgame strategies

The `SubgameRefinementResult` for each subgame is stored in a dict keyed by `SubgameKey`. The final `PreflopSolveResult` assembles:

- **Preflop strategy:** from the blueprint, unmodified.
- **Postflop strategy:** for subgames above the reach threshold, from the refinement; otherwise, from the blueprint (coarse).

The combined strategy table is queryable via the standard `result.average_strategy[infoset_key]` interface — the user doesn't see the blueprint/refinement split unless they inspect `result.refined_subgames` and `result.unrefined_subgames`.

## 9. Files to create / modify (consolidated checklist)

(Restated from §4–§5 for the implementor's convenience.)

**Create:**
- `poker_solver/preflop_solver.py` — ~300 LOC
- `poker_solver/blueprint.py` — ~250 LOC
- `poker_solver/subgame_refiner.py` — ~350 LOC
- `tests/test_hunl_preflop_blueprint.py` — ~6 tests
- `tests/test_hunl_preflop_refinement.py` — ~5 tests
- `tests/test_hunl_preflop_integration.py` — ~4 tests
- `tests/fixtures/hunl_preflop_fixtures.py` — fixture builders
- `crates/cfr_core/src/preflop.rs` — ~600 LOC (Rust port)
- `crates/cfr_core/src/blueprint.rs` — ~400 LOC
- `crates/cfr_core/src/subgame.rs` — ~300 LOC
- `tests/test_preflop_diff.py` — ~4 tests (Python ↔ Rust differential)

**Modify:**
- `poker_solver/solver.py` — add preflop dispatch branch
- `poker_solver/cli.py` — add `--hunl-mode preflop` and associated flags
- `poker_solver/hunl.py` — add canonical-class chance node generator for preflop
- `poker_solver/__init__.py` — re-exports
- `crates/cfr_core/src/lib.rs` — PyO3 bindings

## 10. Test plan

### 10.1 `tests/test_hunl_preflop_blueprint.py` (~6 tests)

1. **`test_blueprint_converges_at_100bb`** — `build_blueprint(preflop_config_100bb(), tiny_abstraction(), iterations=5_000)`; assert `exploitability_history[-1] < 1.0` (loose; the blueprint is coarse). Marked `@pytest.mark.slow`; CI uses 500 iterations and asserts `< 5.0`.
2. **`test_blueprint_reach_probabilities_sum_to_one_at_root`** — `sum(reach_probs[root_infosets]) == pytest.approx(1.0)`.
3. **`test_blueprint_leaf_values_computed_for_postflop_subgames`** — for each preflop terminal that enters postflop (i.e., not a fold leaf), `BlueprintResult.leaf_values[subgame_key]` is finite and in `[-100, 100]` BB.
4. **`test_blueprint_strategy_covers_all_preflop_infosets`** — for the 169 hand classes × ~3.4k preflop infosets, every reachable infoset (reach_prob > 0) has a strategy entry in `blueprint.strategy`.
5. **`test_blueprint_memory_under_budget_at_100bb`** — `BlueprintResult.memory_report.grand_total_bytes < 14 * 1024**3`. Skipped if not run with `--run-slow`.
6. **`test_blueprint_coarse_menu_respected`** — assert that no postflop infoset in the blueprint has more than `len(postflop_menu) + 3` actions (where the +3 covers fold/call/all-in). Catches accidental menu leakage from the full PR 3 abstraction.

### 10.2 `tests/test_hunl_preflop_refinement.py` (~5 tests)

1. **`test_refine_subgame_parity_with_direct_postflop_solve`** — for one subgame (e.g., flop 3-bet pot at 100 BB, board AsKsQh), compare `refine_subgame(...)` output to `solve_hunl_postflop(equivalent_config, ...)` (the direct PR 5 solve with the same ranges and abstraction). Strategies must agree within 5e-2 per action (loose; refinement uses warm start, direct solve doesn't, so trajectories differ but converged strategies should match).
2. **`test_refinement_warm_start_speeds_convergence`** — run the same subgame with and without warm start (toggle via internal flag); assert warm-start solve reaches `exploitability < 0.1` in fewer iterations than cold-start solve. Soft assertion (5e-1 slack); failure prompts user review.
3. **`test_refinement_uses_full_action_menu`** — assert that the refined strategy contains infosets with the full 8-action menu (6 sizes + fold + call) at non-cap postflop nodes, even though the blueprint used only 3.
4. **`test_refinement_respects_reach_threshold`** — `solve_hunl_preflop(..., reach_threshold=0.1)`; assert that all `refined_subgames.keys()` have `reach_probs > 0.1` and all `unrefined_subgames` have `reach_probs <= 0.1`.
5. **`test_refinement_ranges_extracted_correctly`** — for a 3-bet pot subgame, assert that the extracted `p0_range["AA"]` (SB's reach with AA into the 3-bet-call subgame) > `p0_range["72o"]` (SB rarely 3-bets 72o). Soft sanity check.

### 10.3 `tests/test_hunl_preflop_integration.py` (~5 tests)

1. **`test_preflop_dispatch_pushfold_at_15bb`** — call `solve(HUNLPoker(HUNLConfig(starting_stack=1500)))`; assert `result.dispatched_to_pushfold is True` and `result.backend == "pushfold_chart"`.
2. **`test_preflop_dispatch_solver_at_16bb`** — call `solve(HUNLPoker(HUNLConfig(starting_stack=1600)))`; assert `result.dispatched_to_pushfold is False` and the preflop solver actually ran (`PreflopSolveResult` returned).
3. **`test_preflop_dispatch_error_at_251bb`** — call with `starting_stack=25_100`; assert `ValueError` mentioning the 250 BB cap.
4. **`test_published_ref_sb_open_raise_100bb`** — at 100 BB, solve preflop fully; for the SB-first-action infoset with hand `AA`, assert the strategy assigns `>= 95%` probability to non-fold actions (open). For `72o`, assert `>= 60%` fold. For `JJ`, assert open frequency in `[0.85, 1.0]`. These are loose published-ref anchors; tight comparison requires PR 7 cross-validation infrastructure adapted for preflop, deferred to a follow-up. Marked `@pytest.mark.slow`.
5. **`test_combined_exploitability_under_0_05_bb_per_hand`** (NEW, per §7.4 end-to-end target) — at 100 BB, full blueprint + refinement; sample 5 representative reached infosets across preflop and refined postflop subgames; for each, compute exploitability via `solver.exploitability` and assert each is `< 0.05 BB/hand`. The 0.05 figure matches the gtow_how_solvers_work.md "< 0.5% pot = professional standard" guideline scaled to BB/hand on Pio's 100 BB cash-game spot. Marked `@pytest.mark.slow`. CI runs a relaxed variant at 5k blueprint iter + 2k refine iter and asserts `< 0.5 BB/hand` (10× looser; serves as a smoke).

### 10.4 `tests/test_preflop_diff.py` (~4 tests — Python ↔ Rust)

**Tolerance:** PR 9 adopts the **PR 6 / PR 7 / PR 8 tolerance cluster** — `5e-3` per-action probability + `1e-3 × base_pot` per-spot game value. (Earlier draft cited `1e-4`; reconciled to match the established cluster per `docs/spec_consistency_review.md` finding I3.) Justification: Rust HashMap iteration order × float-accumulation order makes tolerances tighter than `1e-3` unjustifiably fragile at HUNL scale (per the `feedback_no_extrapolate.md` lesson and PR 6 §7.3's explicit choice). Tightening to `1e-4` would require deterministic HashMap ordering across both tiers + identical float-reduction trees — achievable in principle but a cost we don't justify here when behavior is indistinguishable at `5e-3`.

1. **`test_preflop_diff_blueprint_strategies_match`** — `build_blueprint(...)` in both tiers; assert per-infoset strategies agree within `5e-3` per action, per-spot game value within `1e-3 × base_pot`.
2. **`test_preflop_diff_refinement_strategies_match`** — same tolerances for one refined subgame.
3. **`test_preflop_diff_combined_strategy_table`** — full `solve_hunl_preflop` in both tiers; assert combined strategy tables match within the same `5e-3 / 1e-3` cluster.
4. **`test_preflop_diff_dispatch_paths_consistent`** — at 15 BB (push/fold), at 100 BB (solver), at 251 BB (error), both tiers behave identically.

### 10.5 Intuition gauntlet (in `test_hunl_preflop_integration.py`)

Soft sanity checks per PLAN.md §4 ("Poker-intuition gauntlet"):

- **MDF at BB facing 3-bet:** at 100 BB after SB opens 2.5 BB and faces a 3-bet to 8 BB by BB, the SB's *defense frequency* (call + 4-bet) must be `>= MDF(8_BB_to_call, 11.5_BB_pot) = 41%`. Documented as a soft assertion.
- **Polarization on 4-bet stacks at 100 BB:** the SB's 4-bet range should be polarized (a mix of value 4-bets like AA/KK and bluff 4-bets like A5s) rather than linear (no broadway hands like KQs in the 4-bet range). Soft assertion: `4bet_freq("KQs") < 4bet_freq("A5s") * 0.5`.

These tests use the full 100 BB solve and are marked `@pytest.mark.slow`.

## 11. Three-agent fan-out plan

Same pattern as PR 5 (tight per-agent ownership, parallel execution, integration at end).

### Agent A — Python blueprint + preflop solver

**Owns:** `poker_solver/blueprint.py`, `poker_solver/preflop_solver.py`. Also: dispatch edits to `solver.py`, `cli.py`, `__init__.py`, and the canonical-class chance generator in `hunl.py`.

**Does NOT touch:** `subgame_refiner.py`, any Rust file, any test file.

**Deliverables:**

- `solve_hunl_preflop` with the signature in §4.
- `PreflopSolveResult` dataclass.
- `build_blueprint` per §7.
- `BlueprintResult` dataclass.
- Dispatch logic per §6 (push/fold at ≤15 BB, error at >250 BB).
- Canonical-class preflop chance generator in `hunl.py`.
- CLI integration: `--hunl-mode preflop --stacks 100` works end-to-end.
- Type-hinted; `mypy --strict` clean.

**Interface lock:** Agent A imports from `poker_solver.subgame_refiner` only the public surface in §4 (`refine_subgame`, `SubgameKey`, `SubgameRefinementResult`).

### Agent B — Python subgame refiner + PR 5 integration

**Owns:** `poker_solver/subgame_refiner.py`.

**Does NOT touch:** `blueprint.py`, `preflop_solver.py`, any Rust file, any test file.

**Deliverables:**

- `refine_subgame` with the signature in §4.
- `SubgameKey`, `SubgameRefinementResult` dataclasses.
- Range-extraction logic per §8.2.
- Warm-start logic per §8.3.
- Calls `poker_solver.hunl_solver.solve_hunl_postflop` (PR 5 unchanged) for the actual solve.
- Type-hinted; `mypy --strict` clean.

**Interface lock:** Agent B's `refine_subgame` signature is fixed by §4; if Agent A discovers an awkward call site, they file an "interface adjustment" note for the orchestrator (user) to approve.

### Agent C — Rust port + PyO3 + tests

**Owns:** `crates/cfr_core/src/preflop.rs`, `crates/cfr_core/src/blueprint.rs`, `crates/cfr_core/src/subgame.rs`, edits to `crates/cfr_core/src/lib.rs`. ALSO: writes all Python test files (`tests/test_hunl_preflop_*.py`, `tests/test_preflop_diff.py`, `tests/fixtures/hunl_preflop_fixtures.py`) from the spec alone.

**Does NOT touch:** any Python `.py` non-test file.

**Deliverables:**

- Rust port of `blueprint.py` → `blueprint.rs`. Mechanical translation (PR 6 pattern).
- Rust port of `preflop_solver.py` → `preflop.rs`. Reuses PR 6's postflop port for the postflop legs.
- Rust port of `subgame_refiner.py` → `subgame.rs`.
- PyO3 bindings exposing `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust` as Python-callable functions.
- All test files per §10. Agent C does NOT see Agent A/B Python code while writing tests; they write strictly from this spec.
- `cargo clippy --all-targets -- -D warnings` clean.

**Parallelism rationale:** Agent C launches concurrently with A+B because the spec is the interface lock. By the time A+B return, C's tests are ready; pytest + cargo test is the integration check.

**Edge-case allowance:** Agent C may surface ambiguities in the spec via failing tests; the spec is the source of truth, not the tests or the implementation. (Same rule as PR 3, PR 4, PR 5.)

## 12. Memory budget enforcement

The blueprint pass uses PR 5's `MemoryProbe` unchanged, including the **10% `psutil` RSS calibration check** documented in PR 5 §7.6 (per consistency review I4: PR 9 explicitly inherits the same calibration tolerance — the larger preflop tree should not exceed the 10% bound, and if it does, that's a profiler-correctness signal worth investigating). The `max_memory_gb` parameter (default 14.0) applies to the blueprint solve; if exceeded, abort with `MemoryError` + partial `MemoryReport`.

For subgame refinement, each subgame is solved sequentially (one at a time) with the same memory budget AND the same 10% calibration tolerance per-subgame. Between subgames, the previous solve's regret tables and infoset dicts are explicitly dropped (`del solver` and `gc.collect()`) so the next subgame starts from a clean memory baseline.

**Hard ceiling at 100 BB:** if the blueprint at the standard 256/128/64 abstraction + 1-size/1-cap coarse menu doesn't fit, the user must either:
- (a) tighten the abstraction tier (e.g., use the 128/64/32 artifact intended for 150–200 BB);
- (b) drop the blueprint menu further (e.g., 0-cap = no postflop raises at all, only check/bet/call/fold/all-in);
- (c) reduce blueprint iterations (less convergent but fits).

The CLI surfaces all three options in the error message.

## 13. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Preflop tree explodes if abstraction not tight enough at 250 BB. | High | PLAN.md §1 tier-tightening (64/32/16 at 200–250 BB) addresses this; the blueprint's 1-size/1-cap menu compounds the savings. If still too big, fall back to (b) above. The CLI errors loudly rather than silently swapping. |
| Blueprint convergence quality is poor → subgame refinement gets bad ranges. | Medium | The blueprint exploitability target is < 0.5 BB/100 (loose but non-trivial). If the blueprint fails to converge, the user sees an exploitability warning and can bump iterations. Subgame refinement is robust to mildly miscalibrated input ranges (DCFR converges to local equilibrium on the subgame regardless). |
| Subgame refinement cost (refining N subgames sequentially) exceeds reasonable wall-clock. | Medium | The reach threshold (default 1e-3) prunes the long tail. At 100 BB, expect ~50–200 subgames above threshold (broad estimate; precise count is empirical from PR 9's first run). At 10k iterations per refinement and ~5 min per refinement on the Python tier, that's ~10 hours wall-clock at the upper end. Rust port (Agent C) brings this to ~30 min. Documented as "overnight on Python, lunch break on Rust". |
| Push/fold ↔ preflop solver handoff at 15 BB has a discontinuity. | Medium | Hard cliff at 15 BB (default). The published Sklansky-Chubukov / Nash charts above 15 BB are interpolation-friendly but our solver doesn't currently smooth across the boundary. **Test `test_preflop_dispatch_pushfold_at_15bb` + `test_preflop_dispatch_solver_at_16bb` lock the boundary behavior.** If smoothing is needed, a v2 follow-up can add a 12–18 BB interpolation band (see decisions §14). |
| Lossless preflop has 169 × ~3,400 infosets × 8 actions × 8 bytes = ~37 MB just for regret tables, before postflop multiplication. | Low | This is small; the dominant cost is postflop. The preflop layer is well within budget. |
| Canonical-class chance generator in `hunl.py` introduces a subtle bug in the preflop hole-card weights. | Medium | The 169 hand classes have non-uniform weights (pairs are 6 combos, suited non-pairs are 4, offsuit non-pairs are 12). The generator must produce the correct combinatorial weight per class, and the opponent class enumeration must respect blockers (e.g., AA when hero has AA leaves 0 combos of AA for the opponent). Test `test_preflop_canonical_chance_weights_correct` (in the blueprint test file) validates this against a brute-force enumeration on a tiny subset. |
| Pluribus uses MCCFR with sampling; we use full-traverse DCFR. The full-traverse cost may dominate. | Medium | Pluribus's choice was driven by 6-max scale (Brown & Sandholm 2019, page 3: *"We use a form of Monte Carlo CFR (MCCFR) that samples actions in the game tree rather than traversing the entire game tree on each iteration"*). At HU scale with our coarse blueprint menu, full-traverse should be tractable. If not, MCCFR is a PR 13 candidate per PLAN.md §1 "No Deep CFR for v1." A simpler intermediate is *external sampling* (sample chance nodes, traverse actions), which is what PR 8's public chance sampling work prepares for. |
| Differential test Python ↔ Rust on the preflop solve diverges. | Medium | Same risk as PR 6 (postflop differential). Mitigation: PR 6's diff-test infrastructure carries over; the `5e-3` per-action + `1e-3 × base_pot` per-spot game-value tolerance from PR 6/7/8 applies (aligned per `docs/spec_consistency_review.md` I3; was previously misquoted as `1e-4`). If divergence > tolerance, the offending implementation gets fixed (precedent: PR 1's Kuhn diff revealed a bug in the Rust regret-update logic). |
| Memory accounting drifts because the blueprint and refinement allocate/free across the solve. | Low | PR 5's `psutil` calibration check (10% tolerance) applies. If drift exceeds 10%, the memory abort path catches it. |

## 14. Open decisions for user

Each entry locks a default; user may redirect before launching A/B/C.

1. **★ Hard or soft handoff at 15 BB.** Default: **hard cliff** — push/fold at ≤15 BB, solver at >15 BB. Override candidate: interpolation band in 12–18 BB where the strategy is a weighted average of chart + solver output, with weights linear in depth. The hard cliff is simpler and matches the PLAN.md §1 stack-depth table; interpolation would smooth the user experience but adds complexity and a new test category.

2. **★ Default blueprint postflop menu.** Default: **1 size (0.75-pot) + all-in, 1-cap**. Override candidates: 2 sizes (e.g., 0.33 + 1.5 pot, 1-cap) for better blueprint quality at ~3x compute cost; or full 6 sizes + 3-cap (= no coarseness at all) which would defeat the blueprint pattern but be empirically valuable for benchmarking. **Decision is load-bearing for memory budget** — if user picks 2 sizes, the blueprint may not fit at 100 BB and we'd need to tier-tighten the abstraction.

3. **★ Maximum stack depth with full quality.** Default: **250 BB with two-tier-tightened abstraction (64/32/16)**. Override candidate: cap at 200 BB and reject 200–250 BB calls (user can use Pio for ultra-deep). The PLAN.md §1 commitment is 250 BB; the user previously locked this. PR 9 ships 250 BB unless the user revises.

4. **Reach threshold for subgame refinement.** Default: **1e-3** (subgames reached with probability >0.001 get refined). Lower threshold → more subgames refined → more compute. Override candidates: 1e-4 (refine essentially every subgame; ~5x compute), 1e-2 (refine only the most common subgames; ~3x faster but worse long-tail quality).

5. **Blueprint iteration count.** Default: **50,000**. Override candidates: 10,000 (faster but coarser blueprint), 200,000 (slower, ~PR 5-quality blueprint convergence). The default is calibrated to "blueprint exploitability < 0.5 BB/100 on the Python tier in ~overnight wall-clock."

6. **Per-subgame refinement iteration count.** Default: **10,000**. Override candidates: 5,000 (warm-start makes this often enough; faster), 50,000 (refines to near-zero exploitability per subgame; slower).

7. **Whether to commit the blueprint artifact to the repo.** Default: **no** — built locally by `precompute-blueprint` (a follow-on CLI tool spec'd in §15). Override candidate: yes, via Git LFS (blueprint at 100 BB is ~50–200 MB compressed). The PR 4 abstraction artifact is also locally built; staying consistent.

8. **Canonical-class chance enumeration scope.** Default: **canonical-class generator added to `hunl.py` as an opt-in, with the existing 1.6M-combo generator preserved unchanged.** Override candidate: replace the 1.6M generator entirely with the canonical version. PR 3's `_enumerate_preflop_hole_outcomes` is used elsewhere (CLI smoke tests, etc.); preserving it avoids regression risk.

9. **Whether to fold preflop solve into the existing `--hunl-mode full` invocation or use a new `--hunl-mode preflop`.** Default: **both work; `preflop` is canonical, `full` is deprecated synonym**. Override candidate: keep `full` as the only name (drop `preflop`); or drop `full` entirely (force users to migrate). The default minimizes user breakage.

10. **MCCFR / external sampling for blueprint.** Default: **full-traverse DCFR** (consistent with PRs 1–5). Override candidate: external sampling (cheaper per iteration but more iterations needed). PR 8 prepares the chance-sampling infrastructure; if PR 8 lands before PR 9 implementation begins, PR 9 can leverage it.

11. **Rust tier parity gate.** Default: **Rust port required for PR 9 to ship** (mirrors PR 6's pattern for postflop). Override candidate: ship Python only; Rust follows in PR 9.5. The default is consistent with the two-tier architecture commitment in PLAN.md §1.

## 15. Out-of-scope follow-ups

- **`precompute-blueprint` CLI tool** — analogous to PR 4's `precompute-abstraction`. Builds and serializes the blueprint to `blueprint_<depth>bb_v1.npz` so users can rebuild once and query repeatedly. Likely a PR 9.5 polish task.
- **Range editor UI** — the per-position range arriving at each subgame is currently computed automatically from the blueprint. PR 10 (NiceGUI) could expose a UI for inspecting and editing these ranges (i.e., exploitative analysis). Out of v1 scope.
- **Per-spot library mode (PR 11)** — cache solved preflop spots to disk, lookup by (stack, ante). PR 9's `PreflopSolveResult` is the natural serialization unit.
- **Ante variants** — engine supports ante since PR 3; PR 9 solves at default `ante=0`. Adding `ante=12.5% BB` and `ante=25% BB` chart packs (similar to PR 3.5's push/fold pattern) is a follow-up.
- **Node locking for preflop** — freeze a preflop strategy and re-solve postflop against it (exploitative analysis). Trivial extension once PR 9 lands; deferred per PLAN.md §1.
- **3-handed preflop** — Pluribus is 6-max; the blueprint+refinement pattern generalizes to N players. Out of v1 scope per PLAN.md §1 ("3-handed postflop (heavy abstraction; explicitly approximate equilibrium)").
- **PioSolver parity benchmark for preflop** — analogous to PR 7's river diff but for preflop strategies. Pio's preflop output format is well-documented; a side-by-side comparison is a v2 follow-up (PR 7.5 or PR 11+).
- **GPU acceleration** — PLAN.md §1 explicitly rejects GPU for v1 ("PyTorch MPS underperforms CPU on sparse CFR"). v2 if benchmarks show otherwise.
- **Deep CFR** — PR 13 candidate per PLAN.md §1 if tabular HUNL preflop OOMs at the v1 boundaries. PR 9's empirical memory measurements inform this go/no-go.

## 16. Reference citations

For the blueprint + subgame-refinement pattern (canonical Pluribus reference, `references/papers/pluribus_brown_2019_science.pdf`):

- Page 2 — abstraction strategy: *"To reduce the complexity of the game, we eliminate some actions from consideration and also bucket similar decision points together in a process called abstraction… We use two kinds of abstraction in Pluribus: action abstraction and information abstraction."*
- Page 2 — discrete bet sizing: *"Pluribus only considers a few different bet sizes at any given decision point. The exact number of bets it considers varies between one and 14 depending on the situation."* Our 6-size menu (PR 3) is within this range.
- Page 3 — blueprint pattern: *"The core of Pluribus's strategy was computed via self play… Pluribus's self play produces a strategy for the entire game offline, which we refer to as the blueprint strategy."*
- Page 3 — DCFR convergence rate: *"In the vanilla form of CFR, the influence of this first iteration decays at a rate of 1/T… Therefore, the influence of the first iteration decays at a rate of 1/[sum_{t=1}^T t] = 2/[T(T+1)]."* Same convergence behavior our DCFR (α=1.5, β=0, γ=2.0) inherits.
- Page 3 — Pluribus compute budget: *"The blueprint strategy for Pluribus was computed in 8 days on a 64-core server for a total of 12,400 CPU core hours. It required less than 512 GB of memory."* Our 14 GB / single-MacBook budget is two orders of magnitude tighter, motivating the coarse-blueprint + per-subgame-refinement decomposition.
- Page 3 — pruning rule: *"To speed up the blueprint strategy computation even further, actions with extremely negative regret are not explored in 95% of iterations."* We use a similar high-reach-only refinement filter (§8.1).
- Page 4 — depth-limited refinement: *"After the first round (and even in the first round if an opponent chooses a bet size that is sufficiently different from the sizes in the blueprint action abstraction) Pluribus instead conducts real-time search to determine a better, finer-grained strategy for the current situation it is in."* Our PR 9 ships *offline-batched* refinement (run once at solve time, store the refined strategies in the result); Pluribus's *online* real-time search is a Phase-4 roadmap item per PLAN.md §1.

For DCFR algorithm and hyperparameters (referenced in PR 1+):
- Brown, N. & Sandholm, T. (2019). "Solving Imperfect-Information Games via Discounted Regret Minimization." AAAI 2019. Local copy: `references/papers/`. α=1.5, β=0, γ=2.0 per Section 5 of the paper.

For the action menu and 4-bet/5-bet ladder structure (PR 3 spec):
- `docs/pr3_prep/pr3_spec.md` §"Action encoding" and §"Raise cap enforcement". Preflop 4-cap (allows 4-bet/5-bet ladder) is the PR 3 default, enforced by `poker_solver/action_abstraction.py` and tested in `tests/test_action_abstraction.py:test_abstraction_no_raise_at_cap`.

For card abstraction tiers per stack depth:
- PLAN.md §1 stack-depth table. PR 4 builds the 256/128/64 default; tier-tighter artifacts (128/64/32 and 64/32/16) are built by re-running `precompute-abstraction` with the corresponding `--bucket-counts`.

For postflop solver reused inside subgame refinement:
- `docs/pr5_prep/pr5_spec.md` — `solve_hunl_postflop` interface, `HUNLSolveResult` shape, `MemoryProbe` instrumentation. PR 9 consumes these unchanged.

## 17. Success criteria

- All new tests pass (~19 new Python tests + 4 Rust diff tests).
- All PR 1–8 tests pass unchanged (the dispatch branch in `solver.solve` must not perturb existing Kuhn/Leduc/HUNL-postflop behavior).
- `ruff check poker_solver tests` clean.
- `ruff format --check` clean.
- `mypy poker_solver/preflop_solver.py poker_solver/blueprint.py poker_solver/subgame_refiner.py` strict-clean.
- `cargo clippy --all-targets -- -D warnings` clean on Rust additions.
- `poker-solver solve --game hunl --hunl-mode preflop --stacks 15` dispatches to push/fold chart (no blueprint built).
- `poker-solver solve --game hunl --hunl-mode preflop --stacks 100 --blueprint-iterations 5000 --refine-iterations 2000 --abstraction /path/to/256_128_64.npz` runs to completion in <2 hours on the Python tier (Rust tier: <30 min) and produces a `PreflopSolveResult` with blueprint exploitability < 5 BB/100 (loose CI-runner target; full convergence < 0.5 BB/100 requires the spec's 50k iteration default).
- **End-to-end exploitability < 0.05 BB/hand on the Pio-published 100 BB cash-game validation fixture** (per §7.4; matches "professional standard" of < 0.5% pot from gtow_how_solvers_work.md). Tested via `test_combined_exploitability_under_0_05_bb_per_hand` (§10.3 #5).
- The SB open-raise frequency at 100 BB for `AA` is ≥ 95%; for `72o` is ≤ 40%; the BB defense frequency vs a 2.5x SB open is ≥ MDF(reasonable_pot_odds).
- Memory budget <14 GB at 100 BB; aborts cleanly otherwise.
- Audit agent reviews against this spec and produces `docs/pr9_prep/audit_report.md` with structured must-fix / should-fix / nice-to-fix / looks-good sections.

## 18. Post-implementation audit

Per PLAN.md "Code + test audit (mandatory from PR 3 onward)": after A+B+C land, a fresh `general-purpose` audit agent runs with no prior context and reviews:

- The full diff (Agent A's `preflop_solver.py` + `blueprint.py` + hunl.py edits, Agent B's `subgame_refiner.py`, Agent C's Rust files + Python tests + fixtures, plus the `solver.py` + `cli.py` + `__init__.py` + `lib.rs` deltas).
- Against this spec only.
- Output: `docs/pr9_prep/audit_report.md` with structured sections (must-fix / should-fix / nice-to-fix / looks-good).
- User reads alongside `pr_report.md` before commit OK.

Focus areas the audit must touch:

- **Push/fold ↔ solver handoff at 15 BB.** The dispatch branch in `solver.solve` must route correctly at every boundary depth.
- **Range extraction from blueprint.** The ranges arriving at each subgame are the load-bearing input to refinement; mis-computed ranges produce wrong refined strategies. Audit traces the math against the CFR reach-probability recurrence.
- **Canonical-class preflop chance generator.** Combinatorial weights (6/4/12 for pairs/suited/offsuit) and blocker-aware enumeration must be correct.
- **Warm-start regret loading.** Blueprint regret values must be copied into the refinement solver at the *right* infoset keys (not a stale or mismatched mapping).
- **Memory budget enforcement across subgames.** Sequential refinement must drop the previous solve's state before the next; otherwise memory leaks across the chain.
- **Rust ↔ Python differential.** PR 6's diff infrastructure carries over; the new tests must use the same tolerance and seed handling.
- **License hygiene.** Any code copy-pasted from `noambrown_poker_solver` (MIT, OK with attribution) or `postflop-solver` (AGPL, no copy) must be flagged.
- **DCFR algorithmic invariants.** `dcfr.py` is unchanged; the audit confirms.
- **Reproducibility.** Same seed + config + abstraction → identical blueprint + refined strategies in both tiers.
