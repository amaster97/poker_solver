# PR 12 Agent B — 3p orchestration + Rust port

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 12 Agent B.**
**Your scope:** the 3-handed postflop solver orchestration (`poker_solver/multiway_solver.py`), the Rust port (`crates/cfr_core/src/multiway.rs`), the `solver.py` routing branch for N=3, and the `__init__.py` re-exports. Implements Linear CFR + 95%-pruning + LCFR→CFR cutoff per the Pluribus recipe.
**Your contract:** produce a `solve_3p_postflop(config, abstraction, iterations, ...) -> MultiwaySolveResult` entry point; export per-pair `MultiwayBestResponse` and `run_stability_diagnostic(...)`. All outputs labelled "≈ approximate equilibrium" — never "Nash" / "GTO" / "exploitability". HU code path unchanged.
**Your success criteria:** ruff/black clean; `mypy --strict` on `multiway_solver.py`; `cargo clippy --all-targets -- -D warnings` clean; differential test (Python ↔ Rust) passes on a tiny 3p river subgame (L1 < 1e-6 after 500 iter). All existing tests pass unchanged.
**File ownership:** you own `poker_solver/multiway_solver.py`, `crates/cfr_core/src/multiway.rs`, `poker_solver/solver.py` (routing branch only), `poker_solver/__init__.py` (re-exports only). You may NOT modify any other file.

---

## Theoretical concern that frames everything below

Multi-player CFR has **no Nash convergence proof**. This is the load-bearing fact for your entire module. Concretely:

1. **No polynomial-time algorithm to find Nash exists for n>=3 games** (Daskalakis-Goldberg-Papadimitriou 2009; Pluribus paper p. 2 refs 13–14).
2. **Joint independent Nash play is not itself Nash** in n>=3 games (Pluribus's Lemonade Stand Game example, paper p. 2).
3. **Nash equilibria are not unique** in n>=3 games, and **playing a Nash strategy does not guarantee not-losing-in-expectation** — that's exclusively a 2p0s property (Pluribus paper p. 1).
4. **CFR may cycle, depend on initialization, or fail to converge** in n-player games. Gibson 2013 (`references/papers/gibson_2013_regret_minimization.pdf`) proves only **iteratively-strict-dominated-action elimination (IDSD)** — much weaker than Nash convergence. Counterfactual regret still grows sublinearly in T (Pluribus p. 3), but sublinear total regret does not imply Nash convergence outside 2p0s.

This means:
- **No claim of "Nash equilibrium" anywhere** in your code, docstrings, comments, output strings, CLI output, or repr. Use "approximate equilibrium" or "blueprint" or "approximate strategy".
- **No use of the word "exploitability"** without the modifier "best-response upper bound, per-pair, multi-player" or similar. The bare word is reserved for the 2p0s metric.
- **You build a "near-Nash blueprint" per Pluribus's framing**, not a Nash equilibrium. The per-pair best-response gap is a **diagnostic**, not a Nash distance metric.
- **The convergence-stability diagnostic** (rerun from 3 seeds; compare L1) is the only honest convergence signal we have. Reported, warned on >0.05 L1, never asserted as "proof of convergence".
- **String-literal audit** (per §9 #4 of spec) gates your PR: `grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py | grep -v 'best-response\|approximate\|≈\|near-Nash'` must produce only commented references to historical papers.

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/multiway_solver.py` (new file; ~500 LOC)
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/multiway.rs` (new file; ~600 LOC)
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` (modify; add N==3 routing branch only)
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` (modify; re-export new public API)

**You must NOT touch:**
- `poker_solver/hunl.py` — Agent A (game-state generalization)
- `poker_solver/action_abstraction.py` — Agent A (`ActionContext.num_players` plumbing)
- `poker_solver/cli.py` — Agent C wires the `--num-players` flag through the CLI; you provide the entry-point function, they call it. (Note: spec §6.2 lists `cli.py` as modified, but the modification is the flag wiring which is a UI/UX concern; Agent C owns it. You expose the callable. If the orchestrator clarifies CLI is yours, then write it; default is Agent C.)
- Any test file — Agent C
- Any `ui/views/*.py` file — Agent C
- `tests/fixtures/multiway_fixtures.py` — Agent C

**If you discover an awkward signature mid-implementation, do not silently change it.** Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md`. Internalize:
   - §1 (goal; the "≈ approximate" framing is load-bearing)
   - §3 (theoretical honesty — frames the language discipline in your output strings; cite Pluribus paper p. 2–3 in docstrings)
   - §3.2 (the Pluribus recipe: Linear CFR + 95%-pruning + LCFR→CFR cutoff at T/2)
   - §3.3 (what you report: game value, per-pair BR gaps, stability metric)
   - §3.4 (what you NEVER claim: not Nash, not GTO, not "exploitability")
   - §5 (memory + abstraction; default 128/64/32; reuse PR 4's `precompute-abstraction` artifact)
   - §6.1 (your deliverables)
   - §7.3 (per-pair BR math)
   - §7.4 (convergence stability diagnostic)
   - §8.2 (your agent deliverables)
   - §9 #3, #4, #5, #7, #8, #10 (your critical correctness items)
   - §10.1, §10.5, §10.7, §10.8 (your risks)
2. **The HU solver from PR 5** (your structural template):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py` — read fully. Mirror its structure for the 3p orchestrator.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` — read fully. Your LCFR loop adapts this.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/best_response.py` — read fully. Your `MultiwayBestResponse` adapts this for per-pair walks.
3. **The Rust DCFR from PR 6** (your Rust port template):
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr.rs` — read fully. Mirror for `multiway.rs`.
   - `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/lib.rs` — note the module exports.
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py` — your Python ↔ Rust differential pattern.
4. **Agent A's generalized game state** (your input; assume their work has landed):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` (post-Agent A) — `HUNLConfig.num_players`, `HUNLState` with N-player tuple fields. You consume unchanged.
5. **Pluribus paper:** `references/papers/pluribus_brown_2019_science.pdf`. Specifically:
   - p. 3: Linear CFR recipe; 95%-pruning; "stop the discounting after that because the time cost of doing the multiplications with the discount factor is not worth the benefit later on".
   - p. 5: limping suboptimal except SB (informational; you don't bake this into the prior — see §9 #9 of spec).
6. **Memory profiler from PR 5:** `/Users/ashen/Desktop/poker_solver/poker_solver/profiler/memory.py`. Reuse unmodified.

## Default decisions LOCKED (do not deviate)

- **3-handed only.** `num_players == 3` is the routing trigger. `num_players >= 4` raises `NotImplementedError` in your routing branch in `solver.py`.
- **Postflop only.** Per §2 of spec: no 3-handed preflop solve in PR 12. Your routing branch checks `config.starting_street >= Street.FLOP` before dispatching to `solve_3p_postflop`. Preflop-starting 3-handed configs raise `NotImplementedError` with a clear message ("PR 12 supports only postflop-starting 3-handed solves; preflop is out of scope per spec §2").
- **Algorithm: Linear CFR (LCFR) for iterations 1..t_cutoff, then plain CFR averaging thereafter.** Default `t_cutoff = T // 2` per Pluribus paper p. 3. Exposed as `dcfr_kwargs={'lcfr_cutoff': T//2}` parameter to `solve_3p_postflop`.
- **Do NOT use DCFR_{1.5, 0, 2} for 3-handed.** The (β=0) negative-regret truncation is a 2p0s heuristic; for n-player the conservative choice is LCFR per Pluribus validation. Document this in a docstring.
- **Negative-regret pruning in 95% of iterations.** Per Pluribus p. 3. Default pruning threshold `C = -300_000` cents (per spec §12 #8). Configurable via `dcfr_kwargs={'prune_threshold': C, 'prune_prob': 0.95}`.
- **Card abstraction tier: 128 / 64 / 32 (flop / turn / river)** — one tier tighter than HU default per §5.1. Reuse `precompute-abstraction --bucket-counts 128,64,32` from PR 4 unchanged.
- **No new card-abstraction code.** Reuse `AbstractionTables` / `lookup_bucket()` from PR 4 unchanged.
- **No rake.** `rake_rate == 0.0`, `rake_cap == 0`. Locked per PR 3/5/9.
- **No node locking.** Phase-4 feature; out of scope.
- **No real-time depth-limited search.** Pluribus's k=4 continuation strategies are PR 12.5+ candidates.
- **Stability diagnostic: 3 seeds (0, 1, 2)** per §7.4. Soft assertion `pairwise_max < 0.05` on the river-only fixture; failure → warning + extra badge line, not auto-fail.
- **`MultiwaySolveResult` is a dataclass that extends/wraps `SolveResult`** per §12 #10. Not a tuple of three `SolveResult`s.
- **`solver.solve(HUNLPoker(config))` auto-routes based on `config.num_players == 3`** per §12 #11. The unified entry point is a load-bearing UX choice from PR 5.

## Public API contract (signatures Agent C tests + UI depend on)

**Drift breaks Agent C's tests and the CLI/UI wiring.**

### From `poker_solver/multiway_solver.py`

```python
from __future__ import annotations

from dataclasses import dataclass

from poker_solver.hunl import HUNLConfig, HUNLPoker, HUNLState
from poker_solver.abstraction import AbstractionTables  # PR 4
from poker_solver.solver import SolveResult  # PR 5 base


@dataclass(frozen=True)
class MultiwaySolveResult:
    """Approximate-equilibrium solve result for 3-handed postflop.

    NOT a Nash equilibrium. Multi-player CFR has no Nash convergence proof
    (Gibson 2013; Pluribus paper, Brown & Sandholm 2019). The strategy stored
    here is one approximate fixed point among potentially many. The per-pair
    best-response gaps in `br_gap` are diagnostic upper bounds, NOT Nash
    exploitability.
    """

    strategy: dict[bytes, list[float]]  # infoset key -> action probs
    game_value: tuple[float, ...]  # length num_players, mBB/hand; sums to ~0
    br_gap: tuple[float, ...]  # length num_players; per-pair best-response gap
    num_players: int
    iterations_run: int
    convergence_stability: float | None  # max pairwise L1 across stability seeds; None if not run
    is_approximate: bool = True  # always True for num_players >= 3; load-bearing for UI
    # Inherits / wraps PR 5 SolveResult fields as needed (iterations metadata, etc.).


@dataclass(frozen=True)
class StabilityReport:
    seeds: tuple[int, ...]  # the seeds used
    pairwise_max: float  # max L1 distance per infoset across all seed pairs
    pairwise_mean: float
    l1_per_infoset: dict[bytes, float]  # infoset key -> L1 distance averaged across pairs
    n_infosets: int


def solve_3p_postflop(
    config: HUNLConfig,
    abstraction: AbstractionTables,
    iterations: int,
    seed: int = 0,
    lcfr_cutoff: int | None = None,  # default None -> iterations // 2
    prune_threshold: float = -300_000.0,
    prune_prob: float = 0.95,
    max_memory_gb: float = 14.0,
    progress: bool = False,
) -> MultiwaySolveResult:
    """Solve a 3-handed postflop subgame to approximate equilibrium.

    NOT a Nash equilibrium. The returned strategy is one approximate fixed
    point of Linear CFR + plain CFR averaging in a heavily-abstracted tree.
    Multi-player CFR has no convergence proof (Gibson 2013).

    Algorithm: Linear CFR (Brown & Sandholm 2019, Pluribus) for iterations
    1..lcfr_cutoff, then plain CFR averaging thereafter. Negative-regret
    pruning in `prune_prob` fraction of iterations with threshold
    `prune_threshold`.

    Args:
        config: HUNLConfig with num_players == 3 and starting_street >= FLOP.
        abstraction: PR 4 AbstractionTables, sized for 3p tier (default 128/64/32).
        iterations: total CFR iterations.
        seed: RNG seed for the LCFR/CFR loop (initialization + pruning sampling).
        lcfr_cutoff: switch to plain CFR averaging after this iteration. Default iterations // 2.
        prune_threshold: regret value below which an action is pruned. Default -300k cents.
        prune_prob: probability of skipping pruned actions in each iteration. Default 0.95.
        max_memory_gb: abort if memory exceeds this. Reuses PR 5 MemoryProbe.
        progress: print per-iteration status.

    Returns:
        MultiwaySolveResult with strategy, per-player game value, per-pair BR gaps.

    Raises:
        ValueError: if config.num_players != 3 or config.starting_street < FLOP.
        MemoryError: if MemoryProbe abort triggers.
    """
    ...


class MultiwayBestResponse:
    """Per-pair best-response computation for 3-handed solves.

    Computes BR_p = max_π v_p(π, σ_{-p}) - v_p(σ_p, σ_{-p}) where σ_{-p} is
    the JOINT strategy of the other two players. NOT Nash exploitability.
    See spec §7.3.
    """

    def __init__(self, game: HUNLPoker, strategy: dict[bytes, list[float]]) -> None: ...

    def compute_br_gap(self, player_index: int) -> float:
        """Best-response gap for `player_index` against the joint strategy
        of the other two players in `self.strategy`. Always >= 0."""
        ...

    def compute_all_br_gaps(self) -> tuple[float, ...]:
        """Returns (BR_0, BR_1, BR_2). Length num_players. All >= 0.
        These are per-pair upper bounds, NOT Nash exploitability."""
        ...


def run_stability_diagnostic(
    config: HUNLConfig,
    abstraction: AbstractionTables,
    iterations: int,
    seeds: tuple[int, ...] = (0, 1, 2),
    **kwargs: object,
) -> StabilityReport:
    """Rerun solve_3p_postflop from each seed in `seeds`; compute pairwise L1
    distance between the resulting strategies per infoset.

    Returns StabilityReport with pairwise_max, pairwise_mean, per-infoset L1.

    Spec §7.4: pairwise_max < 0.05 is a SOFT assertion. Failure prompts user
    review (extra badge line "⚠ stability degraded"), not auto-fail.

    Multi-player CFR may have multiple fixed points (Gibson 2013); this
    diagnostic quantifies the magnitude of seed-dependence in the result.
    """
    ...
```

### From `poker_solver/solver.py` (routing branch — additive only)

```python
def solve(game: HUNLPoker, abstraction: AbstractionTables, iterations: int, **kwargs) -> SolveResult | MultiwaySolveResult:
    if game.config.num_players == 2:
        # Existing HU path UNCHANGED.
        return _solve_hu(game, abstraction, iterations, **kwargs)
    elif game.config.num_players == 3:
        if game.config.starting_street < Street.FLOP:
            raise NotImplementedError(
                "PR 12 supports only postflop-starting 3-handed solves; "
                "preflop is out of scope per spec §2."
            )
        from poker_solver.multiway_solver import solve_3p_postflop
        return solve_3p_postflop(game.config, abstraction, iterations, **kwargs)
    else:
        raise NotImplementedError(
            f"num_players={game.config.num_players} not supported; "
            "PR 12 covers N=2 and N=3 only."
        )
```

### From `poker_solver/__init__.py` (re-exports)

```python
from poker_solver.multiway_solver import (
    MultiwaySolveResult,
    StabilityReport,
    solve_3p_postflop,
    MultiwayBestResponse,
    run_stability_diagnostic,
)
```

### From `crates/cfr_core/src/multiway.rs`

```rust
// Mechanical translation of multiway_solver.py's LCFR loop + 95%-pruning.
// Same numerical recipe; same default hyperparameters.
//
// THEORY: Multi-player CFR has no Nash convergence guarantee. This crate
// produces an APPROXIMATE EQUILIBRIUM (Pluribus-style blueprint), not a
// Nash equilibrium. See Gibson 2013 + Brown & Sandholm 2019 (Pluribus paper).

pub struct MultiwaySolveResult {
    pub strategy: HashMap<Vec<u8>, Vec<f32>>,
    pub game_value: Vec<f32>,  // length num_players
    pub br_gap: Vec<f32>,
    pub num_players: usize,
    pub iterations_run: usize,
}

pub fn solve_3p_postflop(
    config: &PokerConfig,
    abstraction: &AbstractionTables,
    iterations: usize,
    seed: u64,
    lcfr_cutoff: usize,
    prune_threshold: f32,
    prune_prob: f32,
) -> MultiwaySolveResult { ... }
```

Differential test (Agent C writes; you make it pass): tiny 3p river subgame, ~few thousand infosets, ~tens of seconds in Python, ~seconds in Rust. After 500 iterations on shared inputs (same seed, same abstraction, same fixture), Python and Rust strategies must agree at L1 < 1e-6 per infoset.

## Critical correctness items

### 1. Per-player BR considers the JOINT strategy of the other two (§9 #3 of spec)

When computing `BR_gap_0`, the BR search must walk against the joint distribution of P1 and P2's strategies — not against either treated individually as fixed. At each opponent decision node in the BR walk, the recursion weights by `σ_p(I, a)` for whichever `p` is to act.

Required test setup (Agent C writes the assertion; you make it correct): synthetic 3p tree where the BR-against-joint is different from BR-against-either-individually-treated-as-fixed. Assert the BR walk picks the correct (joint-aware) value.

Implementation strategy:
```python
def compute_br_gap(self, player_index: int) -> float:
    # At each node:
    #   if node is for player_index: take MAX action value (best response).
    #   else (node is for some other player p): take EXPECTATION over actions
    #        weighted by σ_p(I, a) — the FROZEN strategy from self.strategy.
    # The BR walk produces v_p^best.
    # v_p^current is the EV of self.strategy against itself (already in MultiwaySolveResult.game_value[p]).
    # BR_gap_p = v_p^best - v_p^current.
    ...
```

### 2. NEVER call BR gap "exploitability" (§9 #4 of spec — HARD GATE)

String-literal audit in `scripts/check_pr.sh` for PR 12:

```bash
grep -ri 'exploitability\|nash\|GTO' \
  poker_solver/multiway_solver.py \
  poker_solver/solver.py \
  | grep -v 'best-response\|approximate\|≈\|near-Nash'
```

Should return only commented references to historical papers (e.g., a comment citing the 2p0s exploitability theorem to contrast with multi-player BR gap). Any unaccompanied bare "exploitability" in 3-handed-relevant code path → fail.

In code:
- Field name: `br_gap`, NOT `exploitability`.
- Docstring: "per-pair best-response gap" or "best-response EV upper bound (multi-player; NOT Nash exploitability)".
- Output strings (CLI banner via your `__repr__` or `format()`): "≈ approximate equilibrium" header; "per-pair BR gap" labels; never "exploitability" as a bare term.

### 3. `num_players == 3` routing is centralized in `solver.py` (§9 #5)

Single dispatch point. HU path (`num_players == 2`) unchanged. 3p path is new. `num_players >= 4` raises clear `NotImplementedError`.

Test (Agent C writes): `solver.solve(HUNLPoker(HUNLConfig(num_players=4, ...)))` raises `NotImplementedError` with the message containing "PR 12 supports N=2 and N=3 only".

### 4. Linear CFR cutoff (§9 #7)

Per Pluribus paper p. 3: LCFR for iterations 1..t_cutoff, then plain CFR averaging.

```python
def _cfr_iteration(self, iteration: int, ...) -> None:
    if iteration < self.lcfr_cutoff:
        # LCFR: weight regret by (iteration / (iteration + 1)) per Linear CFR
        # (Brown & Sandholm 2019). This is DCFR(α=1, β=1, γ=1).
        weight = iteration / (iteration + 1)
    else:
        # Plain CFR averaging: no discount factor.
        weight = 1.0
    ...
```

Default cutoff is `iterations // 2`. Configurable via `lcfr_cutoff` parameter.

Test (Agent C writes): solve with `lcfr_cutoff=0` (pure plain CFR), `lcfr_cutoff=iterations` (pure LCFR throughout), and the default; observe each converges (or stably oscillates) and document the wallclock difference. The default should be no worse than pure LCFR on the river-only fixture per Pluribus's claim.

### 5. Negative-regret pruning (§9 #8)

Per Pluribus paper p. 3: "actions with extremely negative regret are not explored in 95% of iterations". Implementation:

```python
def _decide_actions_to_explore(self, infoset_key: bytes, iteration: int) -> list[int]:
    regrets = self.regret_table[infoset_key]
    if self._rng.random() < self.prune_prob:  # 95% of iterations: prune
        return [a for a, r in enumerate(regrets) if r > self.prune_threshold]
    else:  # 5% of iterations: explore all actions (preserves limit-point correctness)
        return list(range(len(regrets)))
```

Default `prune_threshold = -300_000` cents, `prune_prob = 0.95`. Pluribus paper doesn't give an absolute number; this is our scaled interpretation (spec §12 #8).

Test (Agent C writes): solve with pruning enabled and disabled (`prune_prob=0.0`); assert ~3× wallclock speedup with pruning enabled (informational; not strict, since hardware varies).

### 6. Memory budget (§5 + §10.2)

Default abstraction tier 128/64/32 → ~6–10 GB Python memory estimate. Reuse PR 5's `MemoryProbe` unmodified:

```python
from poker_solver.profiler.memory import MemoryProbe

probe = MemoryProbe(max_memory_gb=max_memory_gb)
# in the iteration loop:
probe.check_or_abort()  # raises MemoryError if exceeded
```

PR 5 §7.7 documents the abort behavior. Same pattern here.

### 7. Zero-sum game value (§7.2 #1)

`sum(per_player_game_value) ≈ 0.0` (within `float tolerance * pot`). Holds by construction for any zero-sum game (3p NLHE postflop is zero-sum). Your test (Agent C writes the assertion): after solve, `abs(sum(result.game_value)) < 0.001 * pot_size`.

If this fails, you have a bug in payoff distribution — most likely side-pot or showdown allocation in Agent A's `_compute_side_pots` or `utility`. (You consume Agent A's `utility(state) -> tuple[float, ...]`; that function is responsible for zero-sum; you just verify it via the diagnostic.)

### 8. Stability diagnostic determinism (§15 audit focus area)

The diagnostic itself must be deterministic: running `run_stability_diagnostic(config, abstraction, iterations, seeds=(0,1,2))` twice produces identical `StabilityReport` numbers. Each seed in `seeds` is consumed by a separate solve, but each solve is reproducible given its seed.

Test (Agent C writes): call the diagnostic twice; assert `report1 == report2` (or all numeric fields match within machine epsilon).

### 9. Approximate-equilibrium framing in `__repr__` and serialization (§9 #10)

`MultiwaySolveResult.__repr__` and any JSON serialization must include the "≈ approximate equilibrium" framing. The CLI banner shown to the user (spec §6.3) is rendered as a 3-line text banner with `===` borders:

```
=========================================================
≈ approximate equilibrium (multi-player; not Nash)
Multi-player CFR has no convergence proof; the strategy
shown is one fixed point among potentially many.
=========================================================
```

The banner CANNOT be disabled via any CLI flag or config option (per §9 #10). Hardcode it.

### 10. Linear CFR vs DCFR selection (locked: LCFR)

Do NOT use DCFR_{1.5, 0, 2} for 3-handed. The β=0 (negative-regret truncation) is a 2p0s heuristic; for n-player, LCFR is the validated choice (Pluribus). Document this rationale in the docstring of `solve_3p_postflop`.

Test (Agent C writes): if anyone passes `dcfr_kwargs={'alpha': 1.5, 'beta': 0, 'gamma': 2}` (DCFR), the solver either ignores it with a warning or raises a clear error. Choose one and document.

### 11. Rust port discipline (§6.1)

Mechanical translation. Same numerical recipe; same default hyperparameters. The differential test in `tests/test_3p_diff.py` gates correctness. On a tiny 3p river subgame (~few thousand infosets):

- Python `solve_3p_postflop` and Rust `solve_3p_postflop` produce strategies with L1 < 1e-6 per infoset after 500 iterations on shared inputs.
- Same seed → same RNG sequence → same pruning samples → same numerical output.

Reuse PR 6's pattern. The Rust LCFR loop is similar to PR 6's DCFR but with the LCFR→CFR cutoff.

### 12. `cargo clippy` clean

`cargo clippy --all-targets -- -D warnings` clean on the new `multiway.rs`. No `unwrap()`/`expect()` without explanation. Follow PR 6 patterns.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only architectural inspiration for CFR loop structure.
- `references/code/open_spiel/` (**Apache 2.0**) — read-only architectural inspiration for n-player game tree / best-response computation.
- `references/code/slumbot2019/` (**MIT**) — read-only inspiration for CFR loop / pruning patterns. Slumbot is HU, but the pruning pattern transfers.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration only. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a CFR or Linear CFR formula, ground it in the local Pluribus paper PDF or our spec §3.2; re-derive from scratch.

If you copy a non-trivial code snippet (>5 LOC) from an MIT/Apache source, add an attribution comment at the top of the function:
```python
# Pattern from <source-file> (<license>, attribution required).
# Reference: <repo>/references/code/<path>
```

## Quality bar

- **ruff clean:** `ruff check poker_solver/multiway_solver.py poker_solver/solver.py` reports zero issues.
- **black clean:** `black --check poker_solver/multiway_solver.py poker_solver/solver.py` reports no changes.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/multiway_solver.py` reports zero errors.
- **`cargo clippy --all-targets -- -D warnings` clean** in `crates/cfr_core/`.
- **All existing tests pass.** Your changes to `solver.py` are an additive routing branch; the HU path is unchanged.
- **No new third-party Python deps.** Imports from `numpy`, `poker_solver.*`, stdlib only.
- **No new Rust crate deps** unless necessary; PR 6's existing crate set should suffice.
- **Code size budget:** ~500 LOC `multiway_solver.py`, ~600 LOC `multiway.rs`, ~30 LOC delta on `solver.py`, ~5 LOC delta on `__init__.py`.
- **String-literal audit passes:** no bare "exploitability"/"Nash"/"GTO" in your code.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists.

- For Linear CFR: cite Pluribus paper (`references/papers/pluribus_brown_2019_science.pdf`), p. 3.
- For DCFR base: cite Brown & Sandholm 2019 (`references/papers/dcfr_brown_2019.pdf`).
- For IDSD elimination (the strongest property of multi-player CFR): cite Gibson 2013 (`references/papers/gibson_2013_regret_minimization.pdf`).
- For "no polynomial Nash algorithm": cite Daskalakis-Goldberg-Papadimitriou 2009, referenced via Pluribus paper p. 2 refs 13–14.
- For "joint Nash isn't Nash": Pluribus paper p. 2, Lemonade Stand Game.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/multiway_solver.py poker_solver/solver.py
black --check poker_solver/multiway_solver.py poker_solver/solver.py

# 2. Type-check Python
mypy --strict poker_solver/multiway_solver.py

# 3. Rust lints
cd crates/cfr_core && cargo clippy --all-targets -- -D warnings && cd /Users/ashen/Desktop/poker_solver

# 4. String-literal audit (HARD GATE)
grep -ri 'exploitability\|Nash\|GTO' \
  poker_solver/multiway_solver.py \
  poker_solver/solver.py \
  | grep -v 'best-response\|approximate\|≈\|near-Nash\|# ' \
  && echo "FAIL: bare claims found" || echo "PASS: no bare claims"

# 5. Smoke test routing
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker
from poker_solver.solver import solve
from poker_solver.abstraction import AbstractionTables

# N=2 routing unchanged.
cfg2 = HUNLConfig()
# (Skip actual solve; just confirm import + routing reachable.)

# N=3 routing reachable.
cfg3 = HUNLConfig(num_players=3, starting_stacks=(10_000,)*3, initial_contributions=(0,)*3)
game3 = HUNLPoker(cfg3)
# Confirm routing dispatches without error on instantiation.
print('routing smoke OK')
"

# 6. Smoke test approximate-equilibrium framing
python -c "
from poker_solver.multiway_solver import MultiwaySolveResult
# Verify the field 'is_approximate' exists and defaults True.
fields = MultiwaySolveResult.__dataclass_fields__
assert 'is_approximate' in fields, 'is_approximate field missing'
assert fields['is_approximate'].default is True, 'is_approximate not default-True'
print('approximate-equilibrium framing OK')
"

# 7. Full test suite must pass (regression gate)
pytest -x 2>&1 | tail -30

# 8. Rust differential test (Agent C writes it; you make it pass)
pytest tests/test_3p_diff.py -v 2>&1 | tail -20
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (<=300 words) covering:

1. Files created/modified with LOC counts.
2. Algorithm summary: LCFR cutoff used, pruning settings, BR walk approach.
3. String-literal audit result (paste the grep output; should be clean).
4. Differential test result on tiny 3p river subgame: L1 between Python and Rust strategies after 500 iterations.
5. Stability diagnostic smoke (run on a tiny fixture; report pairwise_max).
6. Verification command output (paste tails).
7. Any spec amendment or contract drift flagged.
8. Any open question for human review.
9. License attributions you added (if any).

**Hard gates before reporting done:**
- All existing tests pass unchanged.
- `mypy --strict` clean on `multiway_solver.py`.
- `cargo clippy -- -D warnings` clean.
- String-literal audit returns no bare claims.
- Differential test passes (L1 < 1e-6 on tiny 3p river fixture).
- `MultiwaySolveResult.is_approximate` defaults True; cannot be disabled.
