# PR 12 Agent A — N-player game state generalization

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 12 Agent A.**
**Your scope:** generalize `HUNLPoker` + `HUNLState` from 2-player to N-player (tested at N=2 and N=3 only), generalize `ActionContext` in `action_abstraction.py` to carry `num_players`, and write the N=3 game-state invariant tests (`tests/test_3p_core.py`).
**Your contract:** strictly-additive on the N=2 API. All PR 3/4/5/6/7/8/9/10/11 tests pass unchanged. Field names and method signatures in `HUNLState`/`HUNLPoker` stay stable so Agent B/C can consume unchanged.
**Your success criteria:** ruff/black clean; `mypy --strict` clean on the two touched files; ~30 new N=3 invariant tests pass; full existing pytest suite passes unchanged; `HUNLConfig.num_players: int = 2` default preserves the legacy code path bit-exactly.
**File ownership:** you own and may write ONLY `poker_solver/hunl.py`, `poker_solver/action_abstraction.py`, `tests/test_3p_core.py`. You may NOT modify any other file.

---

## Theoretical concern that frames everything below

Multi-player CFR has **no Nash convergence proof**. Gibson 2013 (`references/papers/gibson_2013_regret_minimization.pdf`) gives only **iteratively-strictly-dominated-action elimination (IDSD)** in n-player games — much weaker than Nash convergence. Pluribus (Brown & Sandholm 2019, *Science*) explicitly calls itself a "near-Nash blueprint," not a Nash equilibrium (paper p. 2: *"in the case of six-player poker, we take the viewpoint that our goal should not be a specific game-theoretic solution concept, but rather to create an AI that empirically consistently defeats human opponents"*).

This shapes your work via:
- **No "Nash" / "GTO" / "optimal" / "exploitability" string** anywhere in your code, docstrings, comments, or test descriptions for N>=3 paths. Use "approximate equilibrium", "blueprint", "approximate strategy" instead. (§9 #4 of the spec; enforced by a string-literal audit step.)
- **The game-state code itself is theory-neutral** (it just encodes the rules of 3-handed NLHE). But your tests for "fold-then-2-handed-continuation" must not assert anything resembling "the resulting strategy is optimal" — only that the game state evolves correctly.

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` (modify; ~200 LOC delta)
- `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` (modify; `ActionContext.num_players` plumbing + raise-cap / aggressor-tracking generalization)
- `/Users/ashen/Desktop/poker_solver/tests/test_3p_core.py` (new file; ~15 tests, ~400 LOC)

**You must NOT touch:**
- `poker_solver/multiway_solver.py` — Agent B (new file; the 3p orchestration)
- `poker_solver/solver.py` — Agent B (adds routing branch for N==3)
- `poker_solver/__init__.py` — Agent B (re-exports `solve_3p_postflop`)
- `poker_solver/cli.py` — Agent B (adds `--num-players` flag)
- `crates/cfr_core/src/multiway.rs` — Agent B (new file; Rust port)
- `tests/test_3p_solve.py`, `tests/test_3p_diff.py`, `tests/fixtures/multiway_fixtures.py` — Agent C
- Any `ui/views/*.py` file — Agent C (badge + 3-up matrix + range panel + library badge)
- Any existing PR 3 test file — read-only references (must continue to pass unchanged)

If you discover an awkward signature mid-implementation, **do not silently change it**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md`. Internalize:
   - §3 (theoretical honesty — frames the language discipline; cite when in doubt)
   - §4 (game state changes — your primary blueprint)
   - §6.1–§6.2 (which files create/modify)
   - §8.1 (your agent deliverables)
   - §9 #1, #2, #5, #6 (critical correctness items in your scope: side-pots, 3-way showdown, routing, regression on N=2)
   - §15 (post-implementation audit — your work is reviewed for "Regression on N=2 path" and "N-player turn rotation")
2. **The current PR 3 game state** (your starting point):
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` — read fully. Internalize `HUNLState`, `HUNLPoker`, `Street`, `Action`, `_post_blinds`, action-turn advancement, terminal-detection, payoff distribution.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — read fully. Internalize `ActionContext` and how raise-cap + aggressor-tracking work in HU.
3. **The PR 3 test suite** (regression gate):
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_*` — confirm what existing tests assert. Your generalization MUST preserve every behavior these tests check.
4. **Pluribus position convention** (§4.1 of spec):
   - **3-handed positions: P0 = SB, P1 = BB, P2 = BTN** (standard 3-max).
   - **Postflop action order: SB → BB → BTN** (SB is OOP; BTN is IP).
   - PR 12 is postflop-only; you only need to implement postflop action order. But blinds-posting for 3-handed is still required for `_post_blinds_3p()` because the subgame can be set up with `initial_contributions` representing a posted-blinds scenario.

## Default decisions LOCKED (do not deviate)

- **N=2 and N=3 ONLY.** `num_players >= 4` raises `NotImplementedError("PR 12 supports N=2 and N=3 only; 4+ players require a separate solve infrastructure.")` in `HUNLPoker.__init__` (or wherever you centralize the dispatch). Do NOT pretend to generalize to arbitrary N — the action turn rotation, side-pot math, and blinds-posting are implemented only for N=2 and N=3.
- **Strictly additive on N=2.** `HUNLConfig.num_players: int = 2` is the default. All existing PR 3 tests instantiate `HUNLConfig()` without specifying `num_players`, so they hit the N=2 path. That path must be bit-identical in behavior to the pre-PR-12 code.
- **Class names stay.** `HUNLConfig` and `HUNLPoker` keep their import paths (PR 5/9/10/11 import them). Add a top-of-file docstring noting that the names are a misnomer post-PR-12 (the class now supports 3p) but are retained for code stability.
- **3-handed position convention: SB / BB / BTN as P0 / P1 / P2.** Locked per §4.1.
- **Postflop action order for 3p: SB → BB → BTN.** Locked per §4.1.
- **No preflop solve for 3-handed in PR 12.** You implement `_post_blinds_3p()` so 3-handed subgames can be constructed from a postflop start, but `HUNLPoker.apply` is not exercised on preflop-starting 3-handed configs in PR 12 tests. Document this in a code comment.
- **No 3-handed push/fold.** Per §12 #1 of spec. Out of scope.
- **`num_players` is the only generalization knob** in `HUNLConfig`. Also generalize `starting_stacks: tuple[int, ...]` and `initial_contributions: tuple[int, ...]` to length-N tuples (per §4.2 of spec). Old defaults: `starting_stacks=(10_000, 10_000)`, `initial_contributions=(0, 0)`. New 3p defaults: `starting_stacks=(10_000, 10_000, 10_000)`, `initial_contributions=(0, 0, 0)`.

## Public API contract (signatures Agent B + Agent C depend on)

Field names and method signatures listed below are the interface lock. **Drift breaks Agent B's `multiway_solver.py` and Agent C's `tests/test_3p_core.py` / fixtures.**

### `poker_solver/hunl.py`

```python
from __future__ import annotations

# All existing imports preserved.

@dataclass(frozen=True)
class HUNLConfig:
    # Existing fields preserved.
    num_players: int = 2  # NEW. Length of all per-player tuples.
    starting_stacks: tuple[int, ...] = (10_000, 10_000)  # generalized
    initial_contributions: tuple[int, ...] = (0, 0)  # generalized
    # ... rest of existing fields unchanged.

    def __post_init__(self) -> None:
        # Validate len(starting_stacks) == num_players and len(initial_contributions) == num_players.
        # Validate num_players in {2, 3}; else NotImplementedError.
        ...


@dataclass(frozen=True)
class HUNLState:
    contributions: tuple[int, ...]  # length num_players
    stacks: tuple[int, ...]         # length num_players
    folded: tuple[bool, ...]        # length num_players
    all_in: tuple[bool, ...]        # length num_players
    hole_cards: tuple[tuple[Card, Card], ...] | tuple[()]  # length num_players or empty
    cur_player: int                  # 0..num_players-1, or -1 at terminal
    street_aggressor: int            # 0..num_players-1, -1 if no raises this street
    street_num_raises: int
    to_call: int                     # relative to cur_player's contribution vs aggressor's
    # ... existing fields preserved.


class HUNLPoker(Game):
    """N-player no-limit Texas hold 'em game tree, supporting N=2 (HU) and N=3 (3-max).

    Despite the name, this class supports 3-handed play after PR 12. The name is
    retained for code stability across PR 5/9/10/11; importers should continue
    to call this `HUNLPoker`. Internally we treat it as a generic poker game.

    N=4+ is explicitly NotImplementedError per PR 12 §2 non-goals.

    Theoretical note: for N>=3, CFR has no Nash convergence guarantee
    (Gibson 2013; Pluribus paper). This class encodes only the *rules* of
    n-player NLHE; the solver in `multiway_solver.py` is what makes the
    "approximate equilibrium" framing necessary.
    """

    def __init__(self, config: HUNLConfig) -> None:
        if config.num_players not in (2, 3):
            raise NotImplementedError(
                "PR 12 supports N=2 and N=3 only; 4+ players require a "
                "separate solve infrastructure."
            )
        self.config = config
        self.num_players = config.num_players
        ...

    # Public API — signatures unchanged from PR 3 except where noted:
    def initial_state(self) -> HUNLState: ...
    def current_player(self, state: HUNLState) -> int: ...
    def legal_actions(self, state: HUNLState) -> list[Action]: ...
    def apply(self, state: HUNLState, action: Action) -> HUNLState: ...
    def is_terminal(self, state: HUNLState) -> bool: ...
    def utility(self, state: HUNLState) -> tuple[float, ...]:
        """Returns length-num_players tuple of per-player payoffs in cents.
        Sum must be 0 (zero-sum). For 3p, distribute via side-pot rules; see §9 #1."""
        ...
    def chance_outcomes(self, state: HUNLState) -> list[tuple[HUNLState, float]]: ...

    # NEW helpers (internal):
    def _post_blinds_2p(self) -> HUNLState: ...  # existing logic factored out
    def _post_blinds_3p(self) -> HUNLState: ...  # 3-max blind posting; SB=P0, BB=P1, BTN=P2
    def _next_player(self, state: HUNLState, current: int) -> int:
        """Return the next non-folded, non-all-in player after `current` in the
        postflop rotation (SB->BB->BTN for 3p, or P0->P1 for 2p). Returns -1 if
        only one live player remains (street ends)."""
        ...

    def _compute_side_pots(
        self, contributions: tuple[int, ...], folded: tuple[bool, ...]
    ) -> list[SidePot]:
        """See §9 #1 of spec. Critical correctness item."""
        ...
```

### `poker_solver/action_abstraction.py`

```python
@dataclass(frozen=True)
class ActionContext:
    # Existing fields preserved.
    num_players: int  # NEW. Required field; constructors must pass through from HUNLConfig.
    # Raise-cap / aggressor-tracking generalize to N players: aggressor is an int
    # 0..N-1 or -1; raise-cap logic is the same per-street; no math changes.
```

### `SidePot` dataclass (new; in `poker_solver/hunl.py`)

```python
@dataclass(frozen=True)
class SidePot:
    amount: int                # total chips in this pot (cents)
    eligible: tuple[int, ...]  # indices of players who contributed and are still live
```

## Critical correctness items

### 1. Side-pot calculation with multiple all-ins at different stack sizes (§9 #1 of spec — THE hardest correctness item)

`_compute_side_pots(contributions, folded) -> list[SidePot]` is the single most bug-prone function in your scope. Reference: TDA / WSOP rule set, summarized in a code comment at top of the helper.

Algorithm sketch (from spec §9 #1):
1. Sort distinct contribution levels ascending.
2. For each level l (delta = l - previous_level), the pot at this layer is `delta * (count of players who contributed >= l)`. Eligible players for THIS layer = those who contributed >= l AND are not folded.
3. Folded players' chips go to a pot (typically the main pot or the layer they reached); they are NEVER eligible to win any pot.

Required unit-test cases (in `tests/test_3p_core.py`):
- **3-way all-in at equal stacks** (e.g., 50/50/50): one main pot of 150, no side pots; eligible = {0,1,2}.
- **3-way all-in at unequal stacks** (e.g., 50/100/150): main pot 150 with eligible {0,1,2}; side pot 100 with eligible {1,2}; P2 has 50 returned uncalled (this last bit is in `utility`/payout distribution, not in `_compute_side_pots` per se).
- **3-way: two all-in at different stacks, one folded** (e.g., 50/folded@30/100): folded player's chips go to the pot; main pot has eligible = {0,2} (NOT the folded P1).
- **Tie at showdown across a side pot** — split among tied contributors.
- **Floor/ceiling correctness on odd-chip splits** (e.g., 3-way tie on a pot of 100 cents: first chip(s) by position — earliest position relative to button. For postflop 3p, that's SB first.)

Document the TDA rule citation as a code comment. This helper is the explicit focus of the post-implementation audit per §15.

### 2. 3-way showdown evaluation (§9 #2 of spec)

When >= 2 live players remain at river end, each live player's hand is evaluated against the 5-card board. Best hand wins each side pot they contributed to. Implementation reuses `poker_solver.evaluator` per-player; the **only new logic** is the multi-winner-per-side-pot path:

```python
for pot in side_pots:
    eligible_live = [p for p in pot.eligible if not folded[p]]
    if len(eligible_live) == 0:
        continue  # shouldn't happen if invariants hold
    ranks = [evaluator.evaluate(hole_cards[p] + board) for p in eligible_live]
    best = min(ranks)  # lower rank = better hand
    winners = [p for p, r in zip(eligible_live, ranks) if r == best]
    share = pot.amount // len(winners)
    remainder = pot.amount - share * len(winners)
    for w in winners:
        payouts[w] += share
    # Distribute remainder by position (earliest postflop position first).
    ...
```

Test case (required): 3-way showdown where each player wins a different side pot (different stack sizes, different hand ranks). Specifically:
- Stacks: P0=50, P1=100, P2=150.
- All go all-in.
- P0 has the best 50-chip-layer hand; P1 wins the 100-chip layer; P2's overcards lose. (Or some equivalent constructed scenario.)
- Assert each player's payout matches the layered side-pot allocation.

### 3. Action turn advancement (§4.1 of spec)

`_next_player(state, current)` returns the next non-folded, non-all-in player after `current` in the postflop rotation. For 3p:
- Postflop order is SB (P0) → BB (P1) → BTN (P2) → wraps to SB.
- Skip folded and all-in players.
- Returns -1 if only one live (non-folded, non-all-in) player remains (street ends OR everyone folded to one).

Edge cases (required tests):
- All three live → standard rotation.
- One folded, two live → skip the folded one; rotate between the two.
- One all-in (still in the hand), two with chips → the all-in still gets advanced past on action turn (they have no decision to make once all-in for less than the call); the action goes to the next chips-having player.
- Two folded, one live → returns -1 (single-live-player; hand ends; that player wins the pot uncontested).

### 4. Street-ending conditions (§4.1 of spec)

Street ends when:
- All live (non-folded) players have either matched the current `street_aggressor`'s contribution, OR are all-in for less and cannot call more, AND
- Every live player has had an opportunity to act since the last raise.

This is the standard NLHE street-end rule, generalized from HU. The 2p case already correctly implements this (your existing PR 3 code); for 3p, the "every live player has had an opportunity to act since the last raise" condition becomes load-bearing because there can be an intermediate player who hasn't yet had a chance to act.

Required test case: 3p flop, SB checks, BB bets, BTN raises. Action should return to SB (who has not yet had a chance to respond to BB's bet OR the new raise). Then SB calls/folds, then BB calls/folds. Street ends only after both SB and BB have responded to BTN's raise.

### 5. `HUNLConfig.__post_init__` validation

```python
def __post_init__(self) -> None:
    if self.num_players not in (2, 3):
        raise NotImplementedError(
            "PR 12 supports N=2 and N=3 only; 4+ players require a "
            "separate solve infrastructure."
        )
    if len(self.starting_stacks) != self.num_players:
        raise ValueError(
            f"starting_stacks length {len(self.starting_stacks)} != num_players {self.num_players}"
        )
    if len(self.initial_contributions) != self.num_players:
        raise ValueError(
            f"initial_contributions length {len(self.initial_contributions)} != num_players {self.num_players}"
        )
```

### 6. Regression on N=2 path (§9 #6 — HARD GATE)

Every PR 3/4/5/6/7/8/9/10/11 test that exercises `HUNLConfig()` / `HUNLPoker(...)` / `HUNLState` must still pass byte-identically.

Verification strategy:
- Run the full test suite before any changes (`pytest`) and record the count of passing tests.
- After your generalization, run the same command. Same count of passing tests.
- If ANY existing test fails, you broke the N=2 path. Fix immediately.

The N=2 path is "strictly additive" — meaning when `num_players == 2`, the new code path should be observably identical to the old code path (same state transitions, same payoffs, same legal actions in the same order).

### 7. No "Nash" / "GTO" / "exploitability" strings in N>=3 paths (§9 #4)

This applies to your `tests/test_3p_core.py`. Test names, test docstrings, and any assertions about "the game tree behaves correctly" must NOT use the words "Nash", "GTO", "optimal", or "exploitability" — those are reserved for 2p0s contexts. Use "approximate equilibrium" or "blueprint" or just describe the rule being tested ("side-pot allocation", "street-end detection").

This is enforced by the post-PR audit. The grep gate in `scripts/check_pr.sh` (per §9 #4) will reject your test file if it contains a bare "exploitability" without an "approximate" / "best-response" qualifier.

### 8. `hole_cards` shape

`HUNLState.hole_cards` becomes `tuple[tuple[Card, Card], ...] | tuple[()]` — i.e., either a length-N tuple of 2-card tuples, or the empty tuple (when hole cards aren't dealt yet, as in early subgame setup).

PR 5's solver constructs `HUNLState` instances with explicit `hole_cards` for known-range solves. Your generalization must keep this construction pattern working at N=2 unchanged. At N=3, `hole_cards` is length-3.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/open_spiel/` (**Apache 2.0**) — general n-player game-state inspiration; their universal_poker_game.cc implements multi-player NLHE. Read-only architectural inspiration; no code copy.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/` — **AGPL v3**. Read-only inspiration only. No code copy.
- `references/code/TexasSolver/` — **AGPL v3**. Same rule.

**You may NOT extrapolate from training data.** If you "remember" a side-pot algorithm, ground it in the TDA / WSOP rule documentation (cited in a code comment) and re-derive from scratch.

If you copy a non-trivial code snippet (>5 LOC) from an MIT/Apache source, add an attribution comment at the top of the function.

## Quality bar

- **ruff clean:** `ruff check poker_solver/hunl.py poker_solver/action_abstraction.py tests/test_3p_core.py` reports zero issues.
- **black clean:** `black --check poker_solver/hunl.py poker_solver/action_abstraction.py tests/test_3p_core.py` reports no changes needed.
- **mypy strict-clean on new + touched code:** `mypy --strict poker_solver/hunl.py poker_solver/action_abstraction.py` reports zero errors. (Test file mypy is best-effort.)
- **No new third-party deps.** Imports come only from existing dependencies + stdlib.
- **All existing tests pass.** Run `pytest -x` after your work lands and confirm. Your work is strictly additive on the N=2 path; any failure means the additive constraint was violated.
- **New tests added:** ~15 tests in `tests/test_3p_core.py` per §6.1. Cover all the test cases listed in §"Critical correctness items" above (side-pots, 3-way showdown, action turn advancement, street-end, validation errors).
- **Code size budget:** ~200 LOC delta on `hunl.py`, ~50 LOC delta on `action_abstraction.py`, ~400 LOC on the new test file.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. Specifically:

- For side-pot rules: TDA / WSOP rule references. Cite the specific document and section in your code comment.
- For position semantics in 3-max: cite Pluribus paper §5 (limping for SB) or our spec §4.1.
- For "no Nash convergence for n>=3": cite Gibson 2013 + Pluribus paper §3 of spec.

If a fact is needed (e.g., "3-max postflop order is SB → BB → BTN"), it's standard poker; cite the convention inline. For more complex claims, cite the specific source file.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/hunl.py poker_solver/action_abstraction.py tests/test_3p_core.py
black --check poker_solver/hunl.py poker_solver/action_abstraction.py tests/test_3p_core.py

# 2. Type-check
mypy --strict poker_solver/hunl.py poker_solver/action_abstraction.py

# 3. Smoke test N=2 regression
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker
cfg = HUNLConfig()
assert cfg.num_players == 2
assert cfg.starting_stacks == (10_000, 10_000)
game = HUNLPoker(cfg)
state = game.initial_state()
assert game.current_player(state) in (0, 1)
print('N=2 regression smoke OK')
"

# 4. Smoke test N=3 path
python -c "
from poker_solver.hunl import HUNLConfig, HUNLPoker
cfg = HUNLConfig(
    num_players=3,
    starting_stacks=(10_000, 10_000, 10_000),
    initial_contributions=(0, 0, 0),
)
game = HUNLPoker(cfg)
print('N=3 instantiation smoke OK')
"

# 5. Smoke test N>=4 NotImplementedError
python -c "
from poker_solver.hunl import HUNLConfig
try:
    HUNLConfig(num_players=4, starting_stacks=(1,1,1,1), initial_contributions=(0,0,0,0))
    assert False, 'should have raised NotImplementedError'
except NotImplementedError as e:
    print(f'N=4 correctly rejected: {e}')
"

# 6. Full test suite must pass (regression gate)
pytest -x 2>&1 | tail -30

# 7. Your new tests
pytest tests/test_3p_core.py -v 2>&1 | tail -40

# 8. String-literal audit on your new test file (no bare 'Nash'/'exploitability')
grep -E 'Nash|GTO|exploitability|optimal' tests/test_3p_core.py | grep -v 'approximate\|best-response\|near-Nash\|# ' || echo "no bare claims found"
```

If any of the above fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (<=300 words) covering:

1. Files modified/created with LOC deltas.
2. Side-pot algorithm: brief sketch + which TDA rule reference you cited in the code comment.
3. Action-turn rotation: confirmed working for N=2 (regression) and N=3 (new); list any tricky edge cases you tested beyond the spec's required list.
4. Verification command output (paste tails).
5. Any spec amendment or contract drift you flagged (and why).
6. Any open question you couldn't resolve from the spec / PLAN — flag for human review.
7. License attributions you added (if any).

**Hard gates before reporting done:**
- All PR 3-11 tests pass unchanged (regression count match).
- `mypy --strict` clean on `hunl.py` and `action_abstraction.py`.
- New `tests/test_3p_core.py` covers all critical-correctness test cases from §"Critical correctness items" above.
- No "Nash" / "GTO" / "exploitability" / "optimal" bare strings in your new code/tests.
