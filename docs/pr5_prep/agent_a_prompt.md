# PR 5 Agent A — HUNL postflop solver orchestration

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 5 Agent A.**
**Your scope:** the HUNL postflop solver orchestration module that wires `HUNLPoker` (PR 3) + `AbstractionTables`/`lookup_bucket` (PR 4) + `DCFRSolver` (PR 1) + `MemoryProbe` (Agent B's class) into the first end-to-end HUNL postflop solve in the Python reference tier.
**Your contract:** ship `solve_hunl_postflop(...)` with the signature in §"Public API contract" plus a `HUNLSolveResult` dataclass that subclasses `SolveResult`; wire the CLI's `--hunl-mode postflop` path and add a routing branch in `solver.solve()`; Agent B's `MemoryProbe` / `MemoryReport` are your collaborator; Agent C tests you from spec alone.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on `hunl_solver.py`; the first HUNL postflop solve produces a valid strategy (per-infoset probs in `[0, 1]`, sum to 1.0, no NaN); works WITHOUT card abstraction on the river subgame, WITH PR 4's bucketing on flop subgames; OOM is caught + reported, not a hard crash; ALL 138+ existing tests still pass.
**File ownership:** you own and may write ONLY `poker_solver/hunl_solver.py`. You may surgically modify `poker_solver/solver.py` (routing branch), `poker_solver/cli.py` (`--hunl-mode postflop`), `poker_solver/__init__.py` (re-exports), and `pyproject.toml` (add `psutil>=5.9` if Agent B hasn't already). You may NOT touch `dcfr.py`, `hunl.py`, `abstraction/`, or any test/profiler file.

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` (new file)

**You may surgically modify (small, additive edits only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — add a routing branch in `solve()` per PR 5 spec §6 (postflop branch; the push/fold + preflop branches land in PR 3.5 + PR 9 respectively; see PR 9 §6 for the canonical full dispatch composition).
- `/Users/ashen/Desktop/poker_solver/poker_solver/cli.py` — extend `--hunl-mode` to accept `postflop`; add flags `--board`, `--stacks`, `--abstraction`, `--max-memory-gb`, `--bet-sizes`; update the `full` mode message to point at PR 9.
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — re-export `solve_hunl_postflop`, `HUNLSolveResult` from `hunl_solver`; re-export `MemoryReport`, `MemoryProbe`, `StreetMemoryEntry` from `profiler` (Agent B's module).
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — add `psutil>=5.9` to runtime dependencies if not already present (Agent B may have already done this; if both you and Agent B touch it, the additive edit is idempotent — confirm the final state has the dep listed exactly once).

**You must NOT touch:**
- `poker_solver/dcfr.py` — frozen per spec §6 ("DCFRSolver remains unchanged"). The profiler probes from outside.
- `poker_solver/hunl.py` — frozen for PR 5 per spec §6 (PR 6 + PR 8 modify this in later PRs; PR 5 itself touches nothing in this file).
- `poker_solver/abstraction/*` — PR 4's territory; consumed as a read-only artifact.
- `poker_solver/profiler/*` — Agent B owns this entire subpackage. You import from it; you do NOT modify it.
- Any test file (`tests/test_hunl_postflop_solve.py`, `tests/test_memory_profiler.py`, `tests/fixtures/hunl_solve_fixtures.py`) — Agent C owns these.

If you discover an awkward signature or a contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`. Internalize §3 (conceptual architecture), §4 (Stages A–E), §5 (files to create), §6 (files to modify), §8 (convergence + memory targets), §10 Agent A deliverables, §11 (critical correctness items), §12 (risks).
2. **Spec consistency review (cross-cutting decisions; recently amended):** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially N7 (locks `HUNLSolveResult` as `SolveResult` subclass) and B4 (PR 9 §6 is canonical for full dispatch composition; PR 5 only adds the postflop branch).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. Especially §1 "Card abstraction" (256/128/64 default + PR 5 profiler revisits), the stack-depth-tier table, and §3 "Architecture summary" (Python is ground truth).
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 5 entries and any cross-cutting locks (e.g., dispatch ordering canonical reference to PR 9 §6).
5. **Existing surfaces you wire together:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — `DCFRSolver(game)`; methods you call: `solve(iterations, log_every=...)`, `average_strategy()`. Hyperparameters (α=1.5, β=0, γ=2.0) are locked per PLAN.md.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `SolveResult` dataclass (you subclass), `exploitability(game, strategy)` function (you call).
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — `HUNLPoker`, `HUNLConfig`, `Street`. PR 5 consumes these unchanged.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/abstraction/buckets.py` — `AbstractionTables`, `lookup_bucket(tables, board, hand, street)`. PR 4's artifact. **PR 5 depends on PR 4's card abstraction being present at this path.**
   - **Agent B's surface (Module: `poker_solver.profiler.memory`):** import `MemoryProbe`, `MemoryReport`, `StreetMemoryEntry`. The contract you depend on is locked in §"Cross-agent contracts" below; do NOT reach inside Agent B's implementation.
6. **Reference style — PR 4 Agent A prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_a_prompt.md`. Same shape and tone.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 5 spec §14 (10 deferred decisions) and the consistency review N7. The user has authorized autonomous mode; these defaults are LOCKED unless the user redirects before launch:

1. **Memory budget hard ceiling: 14 GB abort path** (spec §14 #1; matches PLAN.md §1 "Card abstraction" — the 14 GB upper bound for 100 BB tree-builder memory). The function parameter is `memory_budget_gb: float = 14.0`. CLI flag `--max-memory-gb` defaults to 14.0.
2. **Convergence semantics: iteration count primary; optional `target_exploitability` early-exit** (spec §14 #2). `iterations: int = 50_000` is the default per the cross-agent contract; `target_exploitability: Optional[float] = None` early-exits when reached.
3. **`HUNLSolveResult` is a subclass of `SolveResult`** (locked per consistency review N7 = PR 5 spec §14 #3). PR 9's `PreflopSolveResult` extends `HUNLSolveResult`; PR 11's library mode depends on `SolveResult.average_strategy` access. Subclass, not tuple. Adds `memory_report: MemoryReport`.
4. **Default `bet_size_fractions` for fixture-style postflop ad-hoc invocations: `(0.33, 0.75, 2.00)`** (spec §14 #4) — 3 sizes — when the CLI doesn't override. (The CLI flag default is `"33,75,100,150,200"` per spec §6.)
5. **No fixture-selector CLI flag** (spec §14 #5). The CLI builds ad-hoc `HUNLConfig` from `--board`, `--stacks`, etc.
6. **Single end-of-solve summary** (spec §14 #6) — no progress bar, no new deps like `tqdm`.
7. **`abstraction=None` + `starting_street == Street.FLOP` → emit `UserWarning`** (spec §14 #7) about lossless mode using a lot of memory. Do NOT error.
8. **No `--memory-report-json` flag in PR 5** (spec §14 #8). Memory report printed to stdout + accessible via `result.memory_report`.
9. **Slow tests marked `@pytest.mark.slow`** (spec §14 #9; for Agent C — you don't write tests but you respect the iteration counts the spec assumes when testing your CLI manually).
10. **Snapshot frequency: caller-chosen via `log_every`** (spec §14 #10). Default: snapshot once at end (`log_every=None`). When `log_every` is set, the probe snapshots between chunks.

**Non-spec defaults LOCKED for cross-agent contract compatibility:**
- The cross-agent contract in the brief uses `iterations: int = 50_000` and `memory_budget_gb: float = 14.0` as the signature defaults. **Use these exact defaults.** The spec §5 originally listed `iterations: int = 10_000` in the function-signature shorthand — the cross-agent contract wins; use `50_000`. (Document this in a code comment for future spec-editors.)

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from `poker_solver/hunl_solver.py`. **Signature drift breaks Agent C's tests and the CLI integration.** Type hints required (mypy --strict).

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from poker_solver.abstraction.buckets import AbstractionTables  # PR 4
from poker_solver.hunl import HUNLConfig
from poker_solver.profiler.memory import MemoryProbe, MemoryReport  # Agent B
from poker_solver.solver import SolveResult


@dataclass(frozen=True)
class HUNLSolveResult(SolveResult):
    """Extends SolveResult with the per-street memory breakdown.

    Inherits from SolveResult so PR 9's PreflopSolveResult and PR 11's library
    mode can rely on isinstance(result, SolveResult). Locked per spec
    consistency review N7 + PR 5 spec §14 #3.
    """
    memory_report: MemoryReport


def solve_hunl_postflop(
    config: HUNLConfig,
    abstraction: Optional[AbstractionTables] = None,
    iterations: int = 50_000,
    target_exploitability: Optional[float] = None,
    memory_budget_gb: float = 14.0,
    *,
    log_every: Optional[int] = None,
    seed: Optional[int] = None,
    dcfr_kwargs: Optional[dict] = None,
) -> HUNLSolveResult:
    """First end-to-end HUNL postflop solver in the Python reference tier.

    Wires HUNLPoker (PR 3) + optional AbstractionTables (PR 4) + DCFRSolver
    (PR 1) + MemoryProbe (Agent B). Routes through the existing solver path
    with profiling instrumentation.

    Args:
        config: HUNLConfig with starting_street >= Street.FLOP and a populated
            initial_board (3/4/5 cards for flop/turn/river).
        abstraction: Optional AbstractionTables artifact from PR 4. If None,
            runs in lossless mode; emits UserWarning for flop/turn starts
            where lossless mode uses a lot of memory.
        iterations: Hard cap on DCFR iterations. Default 50,000.
        target_exploitability: If set, early-exit when reached.
        memory_budget_gb: Hard ceiling for total memory (solver arrays +
            abstraction table + overhead). Exceeding triggers a MemoryError
            carrying the partial MemoryReport as args[1]. Default 14.0 per
            PLAN.md card-abstraction commitment.
        log_every: When set, snapshot memory + exploitability between chunks.
        seed: Reserved for deterministic re-runs. Threads through to DCFR if
            supported.
        dcfr_kwargs: Reserved for future DCFR hyperparameter overrides; PR 5
            does NOT expose α/β/γ flags (locked at 1.5/0/2.0 per PLAN.md).

    Returns:
        HUNLSolveResult with average_strategy, exploitability_history, and
        memory_report.

    Raises:
        ValueError: starting_street == PREFLOP (deferred to PR 9);
            initial_board length mismatch; non-zero rake_rate/rake_cap;
            invalid abstraction shape.
        MemoryError: total memory exceeds memory_budget_gb. The exception's
            args[1] is the partial MemoryReport.
    """
    ...
```

**Internal helpers (you choose, but document them):**
- `_validate_postflop_config(config: HUNLConfig) -> None` — Stage A.
- `_attach_abstraction(config: HUNLConfig, abstraction: AbstractionTables | None) -> HUNLConfig` — Stage B; attaches via the `HUNLConfig.abstraction` field (PR 4 added this; if you discover PR 4 did NOT add the field, file an interface adjustment note rather than mutating it yourself).
- `_run_with_probe(solver, probe, iterations, log_every, target_exploitability, memory_budget_gb) -> tuple[list[float], MemoryReport]` — Stage C with the budget enforcement loop.

## Cross-agent contracts (Agent B's surface; do NOT reach inside)

Treat these as opaque. Import only the names; do not depend on internals:

```python
# From poker_solver.profiler.memory (Agent B's module):

class MemoryProbe:
    def __init__(self, solver, *, include_abstraction: AbstractionTables | None = None): ...
    def measure_per_street(self, dcfr_solver) -> MemoryReport: ...  # cross-agent contract per brief
    def snapshot(self) -> MemoryReport: ...                         # spec §7.1
    @property
    def latest(self) -> MemoryReport: ...

@dataclass(frozen=True)
class MemoryReport:
    flop_gb: float
    turn_gb: float
    river_gb: float
    total_gb: float
    process_rss_gb: float
    river_ratio: float  # river_gb / total_gb — the PR 4 revisit trigger per PLAN.md
    # Plus the richer fields from spec §7.2: per_street, preflop_lossless_entry,
    # abstraction_table_bytes, solver_arrays_total_bytes, grand_total_bytes, etc.
    # You only need river_ratio, total_gb, and process_rss_gb for budget enforcement.
```

**Contract for budget enforcement (your responsibility):**
After each iteration chunk, call `probe.snapshot()` (or `probe.measure_per_street(solver)`) and read `report.total_gb` (or `grand_total_bytes / 1024**3` if Agent B exposes only bytes). If it exceeds `memory_budget_gb`, raise:
```python
raise MemoryError(
    f"Memory budget exceeded: {report.total_gb:.1f} GB > {memory_budget_gb} GB. "
    f"River layer: {report.river_ratio:.1%}. "
    f"Consider tightening the abstraction or restricting --bet-sizes. "
    f"Partial report attached as args[1].",
    report,
)
```
This is **caught and reported**, not a hard interpreter crash. The user sees actionable guidance and can `except MemoryError as e: report = e.args[1]`.

## Critical correctness items

### 1. First HUNL solve produces valid strategy

For every infoset in `result.average_strategy`:
- `sum(probs) == pytest.approx(1.0, abs=1e-9)` — exact L1-normalization.
- `all(0.0 <= p <= 1.0 for p in probs)` — no probabilities outside `[0, 1]`.
- `not any(math.isnan(p) or math.isinf(p) for p in probs)` — no NaN, no Inf.
- `len(probs) == num_actions_at_that_infoset` — matches `game.legal_actions(state)` at that infoset.

This is the headline acceptance criterion (spec §11 #1; PR 5 spec §9.1 test 4).

### 2. Works WITHOUT abstraction on small subtrees (lossless mode for tests)

When `abstraction is None`:
- River-only subgame (e.g., PR 3's `default_tiny_subgame()`) MUST run end-to-end and produce a valid strategy. (Spec §11 #2; test 8 in §9.1.)
- Flop-start with `abstraction=None` emits `UserWarning` mentioning "lossless" (spec §14 #7; test 9 in §9.1).

### 3. Works WITH PR 4's bucketing on larger trees

When `abstraction` is a real `AbstractionTables` (or Agent C's `tiny_synthetic_abstraction()` with bucket counts `(4, 2, 2)`):
- The solver runs without crashing on flop-start configs.
- The infoset keys produced by `HUNLPoker` are bucketed per PR 4 §3.5 (format `b<id>|<street>|...`).
- Agent B's `MemoryProbe` correctly assigns these to per-street entries (their parsing logic; not your concern but your tests indirectly exercise it).

### 4. Memory profiler reports match psutil within 10%

Not directly your assertion — Agent B owns the calibration logic. But **your orchestration must construct the probe correctly** (passing `include_abstraction=abstraction` so the abstraction-table bytes count toward `grand_total_bytes`) and **must call snapshot at the right time** (between chunks, not inside the CFR recursion). If you mis-construct the probe, the 10% calibration test (Agent C's `test_memory_profiler_matches_rss_within_10pct`) fails.

### 5. `MemoryReport.river_ratio` answers "is river layer <30% of total?"

This is the PR 4 revisit trigger per PLAN.md §1 "Card abstraction":
- After a solve, the user reads `result.memory_report.river_ratio`.
- River ratio < 30%: PR 4's revisit shrinks the river bucket count.
- River ratio 30-50%: abstraction well-balanced; no revisit.
- River ratio > 50%: consider lossless river in a future PR.

**Your responsibility:** ensure `river_ratio` is non-zero and computable on every successful solve. Print it in the CLI's memory-section output.

### 6. Locked defaults — failure mode = OOM caught + reported, not hard crash

- `MemoryError` raised with the partial report as `args[1]`.
- The solver does NOT swallow the exception silently.
- The CLI catches it, prints the report nicely, and exits with code 1.

### 7. Hyperparameters locked

α=1.5, β=0, γ=2.0 (Brown & Sandholm 2019 paper defaults; PLAN.md lock). Do NOT expose `--alpha` / `--beta` / `--gamma` flags. The `dcfr_kwargs` parameter is reserved for future use — pass `None` through to `DCFRSolver(game)` for now.

### 8. PR 1/2/3/4 tests still pass unchanged

138+ existing tests pass with your routing branch added to `solver.solve()`. The routing branch must NOT perturb Kuhn/Leduc/Leduc-DCFR convergence behavior. Run `pytest -x` to confirm.

### 9. Deterministic re-runs

Same `seed` + same `config` + same `abstraction` → identical strategy table within float tolerance. DCFR is deterministic; your routing code must not introduce nondeterminism via dict iteration order in the result-packaging code.

### 10. Dispatch composition (cross-PR safety)

Per PR 9 §6 (canonical; see consistency review B4 resolution): the full dispatch in `solver.solve()` is:
```python
def solve(game, iterations, ...):
    if isinstance(game, HUNLPoker):
        eff_stack_bb = game.config.starting_stack / game.config.big_blind
        if eff_stack_bb <= 15:
            return pushfold.solve_pushfold(...)  # PR 3.5 (already landed)
        if eff_stack_bb > 250:
            raise ValueError(...)  # PR 9 lands the >250 BB rejection
        if game.config.starting_street >= Street.FLOP:
            return solve_hunl_postflop(game.config, ...)  # PR 5 — YOUR branch
        # starting_street == Street.PREFLOP → PR 9 preflop solver (not yet landed)
        raise NotImplementedError("HUNL preflop solve lands in PR 9.")
    # Non-HUNL games go to the existing DCFR path.
    ...
```
**PR 5 adds the postflop branch only.** The push/fold branch (PR 3.5) is already landed; the preflop branch (PR 9) lands later. Be careful to preserve the push/fold short-circuit's precedence: a config with `starting_stack=1500` (15 BB) and `starting_street=Street.FLOP` still hits the chart (push/fold takes precedence over postflop because at <=15 BB stack depth, postflop play is forced jam/fold which the chart handles).

## CLI behavior (your extension to `cli.py`)

Per spec §6:

```
poker-solver solve --game hunl --hunl-mode postflop \
    --board "As 7c 2d" \
    --stacks 100 \
    [--abstraction PATH] \
    [--max-memory-gb 14.0] \
    [--bet-sizes "33,75,100,150,200"] \
    [--iterations 50000] \
    [--target-exploitability 0.1] \
    [--log-every 100]
```

- `--board STR`: comma-or-space separated cards (`"As 7c 2d"` for flop; `"As 7c 2d Kh"` for turn; 5 cards for river). REQUIRED for `--hunl-mode postflop`.
- `--stacks INT`: BB per player (symmetric); default 100.
- `--abstraction PATH`: path to PR 4's `.npz` artifact. If omitted, runs lossless. Note: lossless flop/turn = warning per spec §14 #7.
- `--max-memory-gb FLOAT`: default 14.0.
- `--bet-sizes STR`: comma-separated pot fractions (percentages); default `"33,75,100,150,200"`. All-in always available.

The `--hunl-mode full` mode (HUNL preflop) continues to raise `NotImplementedError` but now points at PR 9 (was PR 5). Update the message.

Output: print the strategy table + exploitability history + a new "Memory" section showing per-street breakdown + total + RSS + river ratio.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only architectural inspiration on solver orchestration. Brown's `cpp/` + `python/` two-tier shape is the validation case for our architecture.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/src/lib.rs` — **AGPL v3**. Read-only. The `solve()` orchestration shape (game + abstraction → CFR iterations → result) is generic, but their specific code lives behind AGPL.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

If you cite a pattern from an AGPL repo, do so in a docstring comment that says "pattern inspired by; no code copied" and derive your implementation from scratch. The PR 5 spec §7.8 already documents this for the profiler; you don't need to re-document for the orchestrator.

## Quality bar

- **ruff clean:** `ruff check poker_solver/hunl_solver.py` reports zero issues.
- **black clean:** `black --check poker_solver/hunl_solver.py` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/hunl_solver.py` reports zero errors.
- **mypy on the whole repo: no new errors.** Your edits to `solver.py` / `cli.py` / `__init__.py` must not introduce type errors.
- **All 138+ existing tests still pass.** Run `pytest -x` to confirm. Routing branch in `solver.solve()` must not perturb Kuhn/Leduc behavior.
- **Agent C's tests pass once your code + Agent B's code are both in.** The integration test is `pytest tests/test_hunl_postflop_solve.py -x`.
- **No new third-party deps beyond `psutil` (which Agent B may have already added).** Confirm `pyproject.toml`'s final state has `psutil>=5.9` listed exactly once.
- **Code size budget: ~300–500 LOC** for `hunl_solver.py`; CLI/solver/init edits should each be ≤30 lines.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md` — skim it for "DCFR orchestration", "solver entry point", "memory profiler" entries.

If a fact is needed (e.g., "DCFR α=1.5, β=0, γ=2.0"), cite PLAN.md §1 or Brown & Sandholm 2019 in `references/papers/`. If you need to make a non-trivial claim about postflop-solver's orchestration shape, do NOT copy — derive your own.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/hunl_solver.py
black --check poker_solver/hunl_solver.py

# 2. Type-check
mypy --strict poker_solver/hunl_solver.py

# 3. Smoke test: lossless river subgame end-to-end (Fixture 1 shape)
python -c "
from poker_solver.hunl import HUNLPoker, default_tiny_subgame
from poker_solver.hunl_solver import solve_hunl_postflop
config = default_tiny_subgame()
result = solve_hunl_postflop(config, abstraction=None, iterations=200)
print(f'Strategy infosets: {len(result.average_strategy)}')
print(f'Exploitability history len: {len(result.exploitability_history)}')
print(f'River ratio: {result.memory_report.river_ratio:.1%}')
print(f'Total memory: {result.memory_report.total_gb:.3f} GB')
# Validate strategy shape
for key, probs in list(result.average_strategy.items())[:3]:
    assert abs(sum(probs) - 1.0) < 1e-6, f'{key}: probs do not sum to 1'
    assert all(0.0 <= p <= 1.0 for p in probs), f'{key}: prob out of range'
print('river subgame smoke OK')
"

# 4. Preflop config rejected
python -c "
from poker_solver.hunl import HUNLConfig, Street
from poker_solver.hunl_solver import solve_hunl_postflop
try:
    solve_hunl_postflop(HUNLConfig(), iterations=1)
    print('FAIL: preflop config not rejected')
except ValueError as e:
    print(f'preflop rejection OK: {e}')
"

# 5. OOM caught + reported (not hard crash)
python -c "
from poker_solver.hunl import default_tiny_subgame
from poker_solver.hunl_solver import solve_hunl_postflop
try:
    solve_hunl_postflop(default_tiny_subgame(), iterations=10, memory_budget_gb=1e-9)
    print('FAIL: memory budget not enforced')
except MemoryError as e:
    report = e.args[1] if len(e.args) > 1 else None
    print(f'OOM caught: total={report.total_gb if report else None}')
"

# 6. CLI integration (river subgame)
poker-solver solve --game hunl --hunl-mode postflop \
    --board 'As 7c 2d Kh 5s' --stacks 10 --iterations 100 2>&1 | tail -20

# 7. Full test suite must still pass
pytest -x 2>&1 | tail -20
```

If any step fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why).
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
5. License attributions you added (if any).
6. The river_ratio value observed on the river-subgame smoke test (informs PR 4 revisit decision).
