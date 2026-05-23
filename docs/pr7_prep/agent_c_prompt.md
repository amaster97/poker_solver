# PR 7 Agent C — self-sanity smoke test (no Brown binary required)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 7 Agent C.**
**Your scope:** the smaller, no-binary-required smoke test module that validates the PR 7 fixture + wrapper module work correctly in isolation — fixture-load round-trip, our engine alone solving the first 3 spots, the history-canonicalizer round-trip, the strategy-matrix shape adapter, the range-overlap-with-board check, the `iterations_override` plumbing, and `find_brown_binary()` safety. **No `subprocess`, no Brown binary, no cmake required.**
**Your contract:** ship `tests/test_noambrown_self_sanity.py` (8 tests per PR 7 spec §10 Agent C); use only the public API of `poker_solver.parity.noambrown_wrapper` plus `poker_solver`'s own surface; you write strictly from spec without seeing Agent A's implementation. **These tests run on ANY machine where the rest of the project works — they're the "is the wrapper sane?" gate, separate from the actual diff.**
**Your success criteria:** all 8 tests pass after Agent A lands; ruff clean, black clean; runtime under ~30s total (these are smoke tests, not full diffs); ALL 138+ existing tests still pass; tests survive in CI environments without C++ toolchains.
**File ownership:** you own `tests/test_noambrown_self_sanity.py`. You may NOT touch any non-test file (no Agent A's `noambrown_wrapper.py`, no `pyproject.toml` — Agent B owns that — no `hunl.py`, no `dcfr.py`, no `solver.py`, no `tests/test_noambrown_river_parity.py` — Agent B's).

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/tests/test_noambrown_self_sanity.py` (new file)

**You must NOT touch:**
- `poker_solver/parity/noambrown_wrapper.py`, `poker_solver/parity/__init__.py` — Agent A owns. You import the public surface; you do NOT modify.
- `tests/data/river_spots.json` — Agent A authors. You READ via `load_spots`.
- `scripts/build_noambrown.sh` — Agent A's build script. **Agent C MUST NOT invoke this script.** PR 7 spec §10 Agent C: "Does NOT invoke Brown's binary (Agent C's tests run even without the build)."
- `poker_solver/hunl.py`, `poker_solver/dcfr.py`, `poker_solver/solver.py`, `poker_solver/abstraction/*` — frozen for PR 7.
- `tests/test_noambrown_river_parity.py` — Agent B's territory. You do NOT replicate or import from it.
- `pyproject.toml` — Agent B handles marker registration. You don't use any marker (no slow, no parity_noambrown — these are pure smoke tests that run on any machine).
- Any other test file (`tests/test_hunl_*.py`, `tests/test_dcfr_*.py`, etc.) — frozen.

**You write tests strictly from the spec; you do NOT read Agent A's implementation while writing.** This is the parallelism rationale: the spec is the interface lock. By the time A returns, your test file is ready; pytest is the integration check.

**Edge-case allowance:** If a test you wrote (correctly per spec) fails because the spec was ambiguous, **the spec is the source of truth** — flag the ambiguity for orchestrator review; do NOT silently tweak the test to match Agent A's implementation.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`. Internalize §4 (fixture spots — you load + validate these), §5 step 5 (history canonicalization — you test the round-trip), §7 row "Agent C" (files to create), §10 Agent C deliverables (the 8 tests you write, listed by name), §11 (critical correctness items — your tests assert these), §12 open decisions.
2. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Skim for PR 7 entries.
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. §1 "Card abstraction" — confirms PR 7 uses LOSSLESS (no abstraction); your fixtures load with `abstraction=None` for our solver.
4. **Existing test style references (DO read for style; DO NOT modify):**
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — closest style match for HUNL game tests.
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_tree.py` — for `HUNLConfig` construction patterns.
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_core.py` — short, focused DCFR tests.
   - `/Users/ashen/Desktop/poker_solver/tests/test_card.py` — for Card construction patterns.
5. **Agent A's contract (the public API you consume):** the "Public API contract" section of `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_a_prompt.md`. Internalize exported names + signatures. **Do NOT read Agent A's implementation while you write; only the contract.**
6. **Our solver surface:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `SolveResult`, `solve()`, `exploitability()`.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 80-103 for `HUNLConfig` field semantics; lines 165-189 for `default_tiny_subgame` (a useful template).
7. **Reference style — PR 5 Agent C prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_c_prompt.md`. Same shape and tone for a smoke-test agent.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 7 spec §10 Agent C + §12:

1. **No Brown binary invocation.** Your tests do NOT call `run_brown_solver`, do NOT call `subprocess`, do NOT invoke `scripts/build_noambrown.sh`. PR 7 spec §10 Agent C is explicit: these tests run on ANY machine where the rest of the project works.
2. **First 3 spots only** (PR 7 spec §10 Agent C). For the "runs end-to-end" smoke tests, iterate over `spots[:3]` (the first three loaded). Keeps runtime under ~30s.
3. **Smoke iterations: small** (e.g., 200-500). The full convergence is Agent B's job; you just verify wiring + finiteness.
4. **Tolerances are smoke-style:** `exploitability < 0.02 * pot` (loose); `result.game_value` is finite (`math.isfinite(...)` returns True); `game_value` is bounded by `[-pot, pot]` in chips.
5. **`find_brown_binary()` test asserts safety, not correctness.** Returns `None` OR an existing `Path`; never raises. On most CI boxes (without Brown built), returns `None`.
6. **Canonicalize round-trip on TEN hand-built histories** (PR 7 spec §10 Agent C #4 + §9 risk 1 mitigation). Author the histories yourself in the test — these are short tuples like `(("b", 500),)`, `(("b", 500), ("c", 0))`, etc.
7. **`iterations_override` plumbing test:** load a spot, mutate via `dataclasses.replace(spot, iterations_override=500)`, invoke our solver (mocked or real), assert iteration count actually used. **If `RiverSpot` is frozen, use `dataclasses.replace(...)` rather than mutating.**
8. **No marker required.** These are default-on smoke tests. No `slow` marker, no `parity_noambrown` marker.

## Public API you use (do NOT modify implementations)

From `poker_solver.parity.noambrown_wrapper` (Agent A's exports):
```python
from poker_solver.parity.noambrown_wrapper import (
    RiverSpot, CanonicalHistory,
    load_spots, find_brown_binary,
    canonicalize_brown_history, canonicalize_our_history,
    our_strategy_to_brown_matrix,
)
```

From `poker_solver` (existing, PR 1-5 surface):
- `HUNLPoker`, `HUNLConfig`, `Street` from `poker_solver.hunl`.
- `SolveResult` and the solving entry point — likely `solve()` from `poker_solver.solver` or a more specific helper Agent A exposes (e.g., `solve_river_subgame_explicit_ranges`). **Use whatever Agent A exposes per the public API contract; if neither is documented in the contract, document the gap and use what exists.**

From `pytest`:
- `pytest`, `pytest.raises`, `pytest.approx`.

From stdlib:
- `pathlib.Path`, `dataclasses` (for `replace`), `math` (for `isfinite`).

## Test plan (master list — implement EXACTLY these 8 tests)

Per PR 7 spec §10 Agent C. Each test gets ONE function definition; names match spec §10 exactly so the orchestrator can grep:

### `tests/test_noambrown_self_sanity.py` (8 tests)

```python
"""Self-sanity smoke tests for PR 7's noambrown wrapper module.

These tests run on ANY machine where the rest of the project works —
they do NOT require Brown's C++ binary to be built. They validate:
  - fixture loading + invariants (the spec-correctness gate)
  - our engine solves each of the first 3 spots end-to-end (wiring sane)
  - canonicalize_*_history round-trips identity for 10 hand-built histories
  - our_strategy_to_brown_matrix produces correctly-shaped arrays
  - find_brown_binary returns either an existing path or None (never raises)
  - iterations_override plumbing actually changes the iteration count

These complement (do NOT replace) the real diff test in
tests/test_noambrown_river_parity.py, which DOES require Brown's binary.

PR 7 spec §10 Agent C.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from poker_solver.parity.noambrown_wrapper import (
    RiverSpot,
    canonicalize_brown_history,
    canonicalize_our_history,
    find_brown_binary,
    load_spots,
    our_strategy_to_brown_matrix,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"
```

**Test 1: `test_each_spot_loads_into_hunl_config`** (spec §10 Agent C #1)

Load all 15 spots. For each, construct a `HUNLConfig` with:
- `starting_street=Street.RIVER`
- `initial_board=spot.board`
- `initial_pot=spot.pot`
- `initial_contributions=(spot.pot // 2, spot.pot // 2)`
- `starting_stack=spot.stack`
- `bet_size_fractions=tuple(spot.bet_sizes)`
- `include_all_in=spot.include_all_in`
- `postflop_raise_cap=spot.max_raises`

Assert no exception is raised and `HUNLPoker(config).initial_state()` returns successfully.

**Test 2: `test_each_spot_solver_converges`** (spec §10 Agent C #2)

For `spots[:3]`, solve at 2000 iterations. Assert `exploitability < 0.02 * spot.pot` after solve. **Loose threshold** — just confirms convergence to a strategy, not optimality. Soft assertion: "failure prompts user review, not auto-fix."

If our solver doesn't expose an `exploitability` field on `SolveResult`, document the gap and use a fallback assertion (e.g., `result.average_strategy` non-empty with valid probability distributions per infoset).

**Test 3: `test_each_spot_game_value_is_finite`** (spec §10 Agent C #3)

For `spots[:3]`, solve. Assert:
- `math.isfinite(result.game_value)` is True.
- `-spot.pot <= result.game_value <= spot.pot` (in chips; account for BB unit conversion if `SolveResult.game_value` is in BB-units — multiply by `cfg.big_blind`).
- No `NaN`, no `±inf`.

**Test 4: `test_canonicalize_history_roundtrip`** (spec §10 Agent C #4)

Hand-author TEN canonical history cases. For each, verify the round-trip in both directions:

```python
# Default fixture-realistic state: pot=1000 (half=500/side already in), stack=9500/side
# remaining. Canonical amounts are post-initial-contribution to-total chip amounts (i.e.
# the per-player chip total INCLUDING the half-pot already contributed) — both Brown
# and our canonicalizers feed the same state machine with the same starting state, so
# they emit identical canonical tuples.
#
# Each test case is a 3-tuple: (brown_token_string, our_token_string, expected_canonical)
test_cases = [
    # (brown_form, our_form, canonical)
    ("root", "", ()),
    ("c", "x", (("c", 0),)),          # check-first (no bet to call)
    ("c", "c", (("c", 0),)),          # call (Brown emits 'c' for both)
    ("c/c", "xx", (("c", 0), ("c", 0))),  # check-check (Brown splits streets on '/')
    # Cases 5-7: bet-500 family. Brown's b500 adds 500 chips on top of the half-pot 500
    # already in, so the actor's new total is 1000. Same for ours.
    ("b500", "b500", (("b", 1000),)),
    ("b500/c", "b500c", (("b", 1000), ("c", 0))),
    ("b500/f", "b500f", (("b", 1000), ("f", 0))),
    # Case 8: raise-after-bet. Brown stores 'r<extra>' beyond the call; we store
    # 'r<to_total>'. After b500 the opponent (P1) is at total 1000. Brown's r500 means
    # 500 chips beyond the call ⇒ raiser (P0) total = 1000 + 500 = 1500. Our equivalent
    # is r1500 (raise-to-total 1500).
    ("b500/r500", "b500r1500", (("b", 1000), ("r", 1500))),
    # Case 9: all-in opening. With stack=9500/side and half-pot=500 in, the all-in
    # ceiling is 500 + 9500 = 10000. Brown emits b9500 (chips added by P1). Our A
    # token canonicalizes to ("b", 10000) because to_call==0 at the open.
    ("b9500", "A", (("b", 10000),)),
    # Case 10: all-in as raise after b500. Brown emits r9000 (extra beyond the
    # to-call of 500; 1000 + 9000 = 10000 total). Our A canonicalizes to
    # ("r", 10000) because to_call > 0 at this point.
    ("b500/r9000", "b500A", (("b", 1000), ("r", 10000))),
]
for brown_form, our_form, expected in test_cases:
    brown_canon = canonicalize_brown_history(brown_form)
    assert brown_canon == expected, f"brown {brown_form!r}: got {brown_canon}, expected {expected}"
    our_canon = canonicalize_our_history(our_form)
    assert our_canon == expected, f"our {our_form!r}: got {our_canon}, expected {expected}"
    # And the round-trip identity:
    assert canonicalize_our_history(our_form) == canonicalize_brown_history(brown_form), \
        f"round-trip differs for {our_form!r} vs {brown_form!r}"
```

**Note on the all-in / raise-extra cases:** the exact `("r", to_total)` value depends on the state-tracking semantics in PR 7 spec §5 step 5. If your hand-built expected value disagrees with Agent A's implementation, **flag the ambiguity**; do NOT silently change either side. The spec is the source of truth.

**Test 5: `test_strategy_matrix_shape`** (spec §10 Agent C #5)

For `spots[0]`, solve at 500 iterations. Call `our_strategy_to_brown_matrix(result, hands_p0=p0_combos, hands_p1=p1_combos, spot=spots[0])`. Assert the returned dict:
- Is non-empty (at least one canonical history present).
- For each `(canonical_history_str, player_int) → np.ndarray`, the array has shape `(num_hands, num_actions)` where `num_hands == len(spot.ranges[player_int])` (or fewer if hands were pruned for board overlap; document either case explicitly).
- All probabilities in `[0.0, 1.0]`.
- Each row (per-hand strategy) sums to `1.0 ± 1e-6` OR is all-zero (for hands that didn't reach this infoset).

**Test 6: `test_no_overlap_in_fixture_ranges`** (spec §10 Agent C #6)

Load all 15 spots. For each spot, for each player's range, for each hand:
- `combo[0] != combo[1]` (no duplicate cards within a hand).
- `combo[0] not in spot.board and combo[1] not in spot.board` (no overlap with board).

Assert via `assert ...` with informative failure message including spot.id, player index, and offending combo.

**This is the fixture-correctness gate.** Failure here indicates Agent A's fixture file has bad data; should never silently slip past.

**Test 7: `test_iterations_override_respected`** (spec §10 Agent C #7)

Create a spot with `iterations_override=500` via `replace(spots[0], iterations_override=500)`. Invoke the solver with the override (the wrapper or test_b's helper should honor this). Assert the actual iteration count run is 500, not 2000.

**Implementation detail:** if Agent A exposes a `solve_river_subgame(spot, iterations=None)` helper that respects `spot.iterations_override`, use it. Otherwise document the gap. Worst case, count iterations via `result.exploitability_history` length (if `log_every=1` is set) or via a counter the wrapper exposes. **Don't fabricate a private workaround.**

**Test 8: `test_brown_binary_finder_returns_path_or_none`** (spec §10 Agent C #8)

```python
def test_brown_binary_finder_returns_path_or_none():
    """find_brown_binary() returns Path or None — never raises.

    On CI without the binary: returns None.
    On a dev box with the binary built: returns an existing Path.
    """
    binary = find_brown_binary()
    assert binary is None or isinstance(binary, Path), (
        f"expected Path or None, got {type(binary)}"
    )
    if binary is not None:
        assert binary.exists(), f"find_brown_binary returned {binary} but it doesn't exist"
        assert binary.is_file(), f"find_brown_binary returned {binary} but it's not a file"
```

**No exception expected.** If `find_brown_binary()` raises on any path, that's a bug — surface via `pytest.raises` would mask it.

## Critical correctness items

### 1. Canonicalize-history hand-built cases are the spec-correctness gate

The 10 cases in Test 4 are the only place we lock down the raise-encoding mapping (PR 7 spec §9 risk #1). If Test 4 fails on a real spot, the wrapper has a bug. Author each case **carefully** — work through the state on paper before writing the expected value. Cite PR 7 spec §5 step 5 in your test docstring.

If a case feels ambiguous (e.g., the all-in-as-raise case), include a comment explaining the chosen interpretation and flag it in your report so Agent A and the orchestrator can verify alignment.

### 2. Smoke tests stay smoke

Test 2 (`test_each_spot_solver_converges`) uses a LOOSE threshold (`exploitability < 0.02 * spot.pot`). This is the smoke equivalent of the full convergence assertion. Don't tighten it; the real convergence diff is Agent B's job at 2000 iterations.

If 2000 iterations isn't enough for one of `spots[:3]` to hit `0.02 * pot`, **flag this** as a sign that the iteration count or the spot itself needs tuning — don't silently raise the threshold.

### 3. Range-overlap test is unconditional

Test 6 is a fixture-correctness gate. It MUST pass for all 15 spots. If a fixture entry has a hand that shares a card with the board, that's a fixture authoring bug; the test surfaces it loudly. Don't loosen.

### 4. `find_brown_binary()` is no-exception

Test 8: the function returns Path-or-None. Never raises. Path resolution that fails (e.g., the references directory was removed) should return None, not throw. If Agent A's implementation raises, that's a contract violation — flag, don't catch.

### 5. Tests run without Brown binary

The whole point of Agent C is the no-toolchain gate. None of your tests invoke `subprocess`, `cmake`, or Brown's binary. If a test seems to require the binary, you've misread the spec — re-check §10 Agent C.

### 6. Bookkeeping note on `RiverSpot` immutability

`RiverSpot` is `@dataclass(frozen=True)` per Agent A's contract. To override `iterations_override`, use `dataclasses.replace(spot, iterations_override=500)` rather than `spot.iterations_override = 500` (which would raise).

### 7. Smoke-test wall-clock

Total module runtime should be under ~30s on a reasonable dev box. Solving each of `spots[:3]` at 500 iterations is the heaviest cost; everything else is microseconds. If wall-clock exceeds 60s, reduce the smoke iteration count (e.g., 200) — convergence isn't the point; finiteness + valid distributions are.

### 8. Soft assertions are documented

For tests with loose / "looks like poker" assertions (Test 2 convergence smoke), include a docstring note: "Soft assertion — failure prompts user review, not auto-fix." This pattern matches PLAN.md §4 intuition-gauntlet style.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only inspiration for the test patterns.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/`, `references/code/TexasSolver/` — **AGPL v3**. Not relevant.

**You may NOT extrapolate from training data.** If you "remember" how to round-trip a canonical poker history representation, ground it in PR 7 spec §5 step 5. Don't invent semantics.

## Quality bar

- **ruff clean:** `ruff check tests/test_noambrown_self_sanity.py` reports zero issues.
- **black clean:** `black --check tests/test_noambrown_self_sanity.py` reports no changes needed.
- **All 8 tests PASS** (none skip, none xfail) after Agent A lands.
- **All 138+ existing tests still pass.** Run `pytest -x` to confirm.
- **No subprocess invocation. No `scripts/build_noambrown.sh` invocation.** If your tests do either, you misread the spec; re-read §10 Agent C.
- **Total module runtime < 60s** on a reasonable dev box. If slower, lower the smoke iteration count.
- **Code size budget:** ~250-400 LOC for the test file.

## Reference-first rule

Before any technical claim, cite the local reference. Never extrapolate from training data when a local authoritative source exists.

If a fact is needed (e.g., "Brown stores raises as extra-beyond-call"), cite PR 7 spec §5 step 5 or `cpp/src/main.cpp:193-194`. If you need to know the `RiverSpot` schema, cite Agent A's contract section.

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_noambrown_self_sanity.py
black --check tests/test_noambrown_self_sanity.py

# 2. Tests collect cleanly
pytest tests/test_noambrown_self_sanity.py --collect-only 2>&1 | head -20

# 3. Tests run + pass (no Brown binary required)
pytest tests/test_noambrown_self_sanity.py -v 2>&1 | tail -30

# 4. Verify no subprocess invocation in your code
grep -E "subprocess|run_brown_solver|build_noambrown" tests/test_noambrown_self_sanity.py
# Expected: empty output (or only the import of find_brown_binary which is allowed)

# 5. Existing test suite still passes
pytest -x 2>&1 | tail -20
```

If any step fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity (e.g., Agent A's `RiverSpot` schema differs from the contract you wrote against), **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts.
2. Any spec amendment you made or contract drift you flagged (and why). Specifically:
   - Did `SolveResult` expose an exploitability you could assert against, or did you fall back to per-infoset distribution checks?
   - Did the 10 canonicalize cases all match Agent A's implementation, or did any need flagging?
   - Did Agent A expose a `solve_river_subgame(spot, iterations=None)` helper for `iterations_override` testing, or did you have to detect iteration count via another mechanism?
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
5. Confirmation that no test invokes `subprocess` / `scripts/build_noambrown.sh` / Brown's binary directly.
6. The wall-clock time observed for the full module on your dev box (for the orchestrator to assess CI cost).
