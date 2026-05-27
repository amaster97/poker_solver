# Preflop Chained Orchestrator Plan (PioSolver-Style Chain Solve)

**Date:** 2026-05-27
**Issue:** #31 (preflop chained orchestrator)
**Scope:** Phase 1 — plan + Phase A wrapper stub
**Author:** Plan agent (read-only); plan saved by parent agent

## 1. Goal

Reproduce PioSolver's preflop→postflop chain solve in the existing solver: solve the preflop subgame once, then for each preflop terminal action that reaches a flop, derive a continuation range and solve a postflop subgame with that range. Aggregate everything into a single queryable output object so a user can ask "JJ on the BB facing a BTN open — GTO action, and if I call what's my flop strategy on Ks8d2h?"

## 2. Existing seams

### 2.1 Preflop solver — `poker_solver/preflop.py` + `crates/cfr_core/src/preflop.rs`
- `solve_hunl_preflop(config, ...) -> PreflopSolveResult` (`preflop.py:283`).
- **Subgame-only:** `_validate_preflop_config` (`preflop.py:413-431`) hard-rejects `initial_hole_cards == ()`. Full-tree preflop is deferred.
- **Equity-leaf substitution:** `PreflopSubgameGame` (`preflop.py:54-200`) treats every postflop frontier as a terminal with equity-weighted utility. **This is the critical seam to break in chained mode** — instead of collapsing to equity, the chained orchestrator needs the actual postflop solve at that frontier.

### 2.2 Postflop solver — `poker_solver/hunl_solver.py` + `crates/cfr_core/src/hunl.rs`
- `solve_hunl_postflop(config, ...) -> HUNLSolveResult` (`hunl_solver.py:100`).
- **Accepts `initial_contributions` + `initial_pot`** so chained orchestrator can pass matched preflop pot as dead money into the flop subgame.
- **`solve_range_vs_range_nash(...)`** (`range_aggregator.py:878`) is the natural seam: vector-form CFR (PR 23), now 213× faster post-PR-114.

### 2.3 Range aggregator — `poker_solver/range_aggregator.py`
Already does "blueprint aggregation" by iterating over hand classes and combining results. Conceptually the closest thing in the repo to a chained orchestrator but operates one street at a time.

### 2.4 CLI + UI seams
- `cli.py::_cmd_solve` (line 358) — adding `chained` is a new top-level sub-command
- `ui/state.py::SolveRunner.start(...)` (line 698) — supports `rvr_mode`; chained follows same pattern

## 3. Data flow

### Stage 1 — Preflop range-vs-range
**Route A (V1):** Blueprint aggregation pattern from `range_aggregator.solve_range_vs_range` for the preflop tree. Each hand class solved via `solve_hunl_preflop` with rep combo; aggregate to per-class first-decision frequencies.

**Route B (post-V1):** New Rust vector-form preflop solver. 1-2 weeks of engine work.

### Stage 2 — Derive continuation ranges per terminal action
Walk preflop strategy dict + multiply probabilities along the path. New helper:
```python
derive_continuation_ranges(preflop_result, action_sequence) -> (hero_range, villain_range)
```

### Stage 3 — Postflop solve per terminal action
**V1 scope decision:** lazy per-flop on demand. Orchestrator returns preflop result + a `postflop_solver(action_sequence, board)` closure. Sidesteps the 19,600-flop combinatorial explosion.

### Stage 4 — Aggregation
```python
@dataclass
class ChainedSolveResult:
    preflop_result: RangeVsRangeNashResult
    continuation_ranges: dict[PreflopActionSequence, ContinuationRanges]
    postflop_cache: dict[tuple[PreflopActionSequence, BoardTuple], RangeVsRangeNashResult]
    def query(hand_class, action_sequence, board=None) -> dict[str, float]: ...
    def solve_postflop(action_sequence, board) -> RangeVsRangeNashResult: ...  # lazy
```

## 4. Phased plan

### Phase A — Naive Python wrapper (~3-5 days)
**New files:**
- `poker_solver/chained.py` (~400 LOC)
- `tests/test_chained_orchestrator.py` (~300 LOC)

**Modified:**
- `poker_solver/__init__.py` (1 line re-export)

```python
def solve_chained(
    config_template: HUNLConfig,  # starting_street=PREFLOP, initial_hole_cards=()
    hero_range: Sequence[HandClass] | Range,
    villain_range: Sequence[HandClass] | Range,
    *,
    preflop_iterations: int = 10_000,
    postflop_iterations: int = 500,
    backend: str = "rust",
    lazy_postflop: bool = True,
) -> ChainedSolveResult:
    preflop_result = _solve_preflop_range(...)
    terminals = _enumerate_preflop_terminals(...)
    continuation_ranges = {
        action_seq: _derive_continuation_ranges(preflop_result, action_seq)
        for action_seq in terminals
    }
    postflop_cache: dict[tuple, RangeVsRangeNashResult] = {}
    if not lazy_postflop:
        for action_seq in terminals:
            for board in _representative_flops():
                postflop_cache[(action_seq, board)] = _solve_postflop_at(...)
    return ChainedSolveResult(...)
```

### Phase B — Caching + perf (~3-5 days)
- Module-scope LRU on `_compute_p0_equity`
- Cache postflop result by `(canonical_action_sequence, board_isomorphism)` — reuse `crates/cfr_core/src/abstraction.rs`
- Parallelize per-terminal postflop solves via `ThreadPoolExecutor`

### Phase C — GUI integration (~3-5 days)
New "Chain solve" tab: preflop matrix left, per-action breakdown right. Click preflop action → triggers/pulls cached postflop for selected board.

### Phase D — CLI integration (~1-2 days)
```bash
poker-solver chained --hero-range "BTN_open.txt" --villain-range "BB_defend.txt" \
                     --stacks 100 --preflop-iterations 10000 --postflop-iterations 500 \
                     [--board Ks8d2h]
```

## 5. Surface area

| Component | New code | Modified | Tests |
|---|---|---|---|
| Phase A | ~400 LOC | 1 line | ~300 LOC |
| Phase B | ~150 LOC | ~10 LOC | ~100 LOC |
| Phase C | ~250 LOC | ~40 LOC | smoke |
| Phase D | ~150 LOC | ~20 LOC | ~80 LOC |

**Total V1:** ~950 LOC new + ~70 modified + ~480 tests.

## 6. Open questions for user (TOP 3 — BLOCKING)

1. **Single-pass or iterated chain solve?** Phase A is single-pass (preflop → postflop, never re-solve preflop). PioSolver iterates (postflop EVs inform preflop, re-solve preflop with new leaf values). **Recommend single-pass for V1.**

2. **Per-flop solve granularity:**
   - (a) Lazy — solve only when user queries a specific flop (fast first result, slow per-query)
   - (b) Pre-solve ~30 representative strategic flops (medium memory, fast queries on common boards)
   - (c) Pre-solve all 1,755 isomorphic flops (huge memory, fully cached)
   - **Recommend lazy (a) for Phase A.**

3. **Preflop range-vs-range route:**
   - Route A: blueprint aggregation, reuses existing code, ships in Phase A
   - Route B: true Rust vector-form preflop CFR, 1-2 weeks engine work
   - **Recommend Route A for V1.** Public API stays stable when Route B lands later.

## 7. Other risks

- **Action-tree enumeration cost:** ~10-30 chain-able terminals at 100 BB. Not a concern.
- **Degenerate continuation ranges:** 4-bet line has only ~5 hand classes. Warn when <3 classes; postflop RvR may produce unstable strategies on tiny ranges.
- **State explosion at deep stacks:** Need upfront memory estimate + bail. Mirror `_validate_preflop_config` BB ceiling.
- **Per-flop memory:** 1755 flops × 200 MB = 350 GB. **Phase A must be lazy.** Phase B caching needs LRU eviction.
- **All-in line equivalence test:** for all-in lines (where `PreflopSubgameGame`'s equity-leaf is exact), Stage 1 and Stage 3 should produce consistent EVs.

## 8. Critical files for implementation

- `/Users/ashen/Desktop/poker_solver/poker_solver/preflop.py` — equity-leaf model is the seam
- `/Users/ashen/Desktop/poker_solver/poker_solver/range_aggregator.py` — Stage 1 Route A helpers
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` — `solve_hunl_postflop` accepts `initial_contributions` + `initial_pot`
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLConfig` schema; `infoset_key` defines the strategy-dict key
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `solve()` dispatcher; chained is a new top-level entry, not a `solve()` mode

---

**Status:** PLAN COMPLETE. Phase A implementation NOT STARTED (Plan agent operates read-only). Next step: user picks 3 blocking decisions in §6, then implementation agent (write-enabled) consumes this plan.
