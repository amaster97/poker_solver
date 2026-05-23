# PR 7 Agent B — river-spot diff harness

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 7 Agent B.**
**Your scope:** the pytest module that, for each of the 15 curated river spots, solves with our Python DCFR engine, solves with Noam Brown's `river_solver_optimized` C++ binary, canonicalizes both result sets into the same `(canonical_history, hand) → action_distribution` schema, and asserts per-action probability agreement within `5e-3` and per-spot game value agreement within `1e-3 × spot.pot`.
**Your contract:** ship `tests/test_noambrown_river_parity.py` (the 15-spot parametrized diff test + one infra test for buildability) + register the `pytest.mark.parity_noambrown` marker in `pyproject.toml`; use only the public API of `poker_solver.parity.noambrown_wrapper` (Agent A's territory) plus `poker_solver`'s own surface; the spec is the interface lock — you write strictly from spec without seeing Agent A's implementation.
**Your success criteria:** all 15 parametrized tests pass when Brown's binary is built; cleanly skip via `pytest.skip` when binary missing; ruff clean, black clean; 5e-3 / 1e-3-of-pot tolerances match PR 7 spec §1; ALL 138+ existing tests still pass; the infra test `test_brown_binary_buildable` invokes `scripts/build_noambrown.sh` and asserts the binary exists afterward (or skips if toolchain missing).
**File ownership:** you own `tests/test_noambrown_river_parity.py`. You may surgically modify `pyproject.toml` to add the marker entry. You may NOT touch any non-test file outside of `pyproject.toml` (no Agent A's wrapper module, no `hunl.py`, no `dcfr.py`, no `solver.py`, no `tests/test_noambrown_self_sanity.py` — Agent C's).

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/tests/test_noambrown_river_parity.py` (new file)

**You may surgically modify:**
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — add `parity_noambrown` to the `[tool.pytest.ini_options.markers]` list (or wherever pytest markers are declared in this project; check the existing file structure first). Idempotent edit: if the marker is already registered, don't duplicate it.

**You must NOT touch:**
- `poker_solver/parity/noambrown_wrapper.py`, `poker_solver/parity/__init__.py` — Agent A owns these. You import the public surface; you do NOT modify it.
- `tests/data/river_spots.json` — Agent A authors the fixture; you READ it via `load_spots`.
- `scripts/build_noambrown.sh` — Agent A's build script; you invoke it via subprocess in the infra test.
- `poker_solver/hunl.py`, `poker_solver/dcfr.py`, `poker_solver/solver.py`, `poker_solver/abstraction/*` — frozen for PR 7.
- `tests/test_noambrown_self_sanity.py` — Agent C's territory. Smaller, no-binary smoke. Don't replicate or import from it.
- Any other test file (`tests/test_hunl_*.py`, `tests/test_dcfr_*.py`, `tests/test_leduc_*.py`, etc.) — frozen; PR 7 spec §6 freezes existing tests.

**You write tests strictly from the spec; you do NOT read Agent A's implementation while writing.** This is the parallelism rationale: the spec is the interface lock. By the time A returns, your test file is ready; pytest is the integration check (PR 7 spec §10 same pattern as PR 4/5).

**Edge-case allowance:** If a test you wrote (correctly per spec) fails because the spec was ambiguous, **the spec is the source of truth** — flag the ambiguity for orchestrator review; do NOT silently tweak the test to match Agent A's implementation.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`. Internalize §1 (goal + tolerances), §3 (what PR 7 does NOT do — no flop/turn diff, no Rust-vs-Brown diff), §4 (fixture spots — your tests parametrize over these), §5 (diff harness design — YOUR module; read all 7 steps carefully), §7 row "Agent B" (files to create), §9 risks 4, 5, 6, 8 (your responsibility), §10 Agent B deliverables, §11 #3 (tolerance justification), §12 (open decisions — defaults locked below).
2. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially I3 (PR 6 + PR 7 + PR 8 tolerance standardization: `5e-3` per-action, `1e-3 × base_pot` per game value). Confirms the numbers you assert against.
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. §1 "DCFR α=1.5, β=0, γ=2.0" and §4 "River-only HUNL spots → diff vs `noambrown/poker_solver`" — confirms PR 7 is the river parity gate.
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 7 entries and tolerance-locking notes.
5. **Existing test style references (DO read for style; DO NOT modify):**
   - `/Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py` — the closest analog: Python ↔ Rust differential test, with parametric tolerances. Reuse the assertion style.
   - `/Users/ashen/Desktop/poker_solver/tests/test_leduc_diff.py` — another differential test in the family. Same 5e-3 / 1e-3 tolerance pattern.
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_core.py` — HUNL game test style.
   - `/Users/ashen/Desktop/poker_solver/tests/test_hunl_tree.py` — for `HUNLConfig` construction patterns.
6. **Agent A's contract (the public API you consume):** the "Public API contract" section of `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_a_prompt.md`. Internalize the exported names + their signatures. **Do NOT read Agent A's implementation while you write; only the contract.**
7. **Our solver surface:**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `SolveResult` dataclass; `solve()` orchestration; `exploitability()` function.
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 165-189 (`default_tiny_subgame`) for the river-only `HUNLConfig` pattern; lines 80-103 for `HUNLConfig` field semantics. **PR 7 wraps explicit-range solves; we don't use `default_tiny_subgame` directly.**
8. **Reference style — PR 5 Agent C prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_c_prompt.md`. Same shape and tone for a "tests-from-spec" agent.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 7 spec §12 + the orchestrator brief:

1. **Tolerance per-action: `5e-3`** (PR 7 spec §1, §11 #3, §12 #1; consistency review I3 confirms PR 6 + PR 7 + PR 8 align). Use `abs(our_prob - brown_prob) < 5e-3` in assertions. NOT `5e-3 * something`; the threshold is absolute.
2. **Tolerance per-spot game value: `1e-3 × spot.pot`** (PR 7 spec §1). Computed in chips. NOT 1e-3 absolute; scales with pot size.
3. **Default iterations: 2000** (PR 7 spec §12 #5; matches Brown's `--iters` default). Per-spot override via `spot.iterations_override`.
4. **Spot count: 15** (PR 7 spec §12 #2). Loaded from `tests/data/river_spots.json`. Parameterize pytest tests by `spot.id`.
5. **Cleanly skip on missing binary** (PR 7 spec §5 step 7 + §12 #3). Use `pytest.skip("Brown's river_solver_optimized not built; run scripts/build_noambrown.sh")`. Do NOT fail.
6. **Pytest marker: `parity_noambrown`** (PR 7 spec §10 Agent B). Register in `pyproject.toml`. CI can opt-out with `pytest -m "not parity_noambrown"`.
7. **Coverage threshold: ≥80%** of Brown's histories must appear in our canonicalized result per spot (PR 7 spec §10 Agent B). Catches accidental tree-truncation in either engine.
8. **Per-spot test runtime budget: ~30s** (PR 7 spec §5 "Test runtime budget"). 15 spots × ~30s = ~7.5 min total. Acceptable for per-PR check.
9. **No iteration-by-iteration trace comparison** (PR 7 spec §3). Compare only **converged average strategy** at fixed iteration count.
10. **DCFR algorithm only** (PR 7 spec §3). We don't diff CFR / CFR+ / LCFR / MCCFR. Brown's binary is invoked with `--algo dcfr`.

## Public API you use (do NOT modify implementations)

From `poker_solver.parity.noambrown_wrapper` (Agent A's exports):
```python
from poker_solver.parity.noambrown_wrapper import (
    RiverSpot, BrownStrategyDump, BrownPlayerProfile, BrownInfosetEntry,
    CanonicalHistory,
    load_spots, find_brown_binary, write_brown_config, run_brown_solver,
    canonicalize_brown_history, canonicalize_our_history,
    our_strategy_to_brown_matrix,
)
```

From `poker_solver` (existing, PR 1-5 surface):
- `HUNLPoker`, `HUNLConfig`, `Street` from `poker_solver.hunl`.
- `SolveResult` and a solving entry point. **PR 7 introduces an explicit-range river solve;** check whether PR 5's `solve_hunl_postflop` accepts the explicit-range form OR whether PR 7 needs a new helper (Agent A's `noambrown_wrapper.py` may expose `solve_river_subgame_explicit_ranges(...)` or similar — refer to PR 7 spec §5 step 2 which mentions "PR 7 introduces a `solve_river_subgame(config, range_p0, range_p1, iterations)` helper in `poker_solver/parity/noambrown_wrapper.py` that runs our DCFR loop once per (hand_p0, hand_p1) pair and aggregates"). **If Agent A exposes this helper, use it. If not, document the gap and flag in your report; do NOT invent a private workaround.**

From `pytest`:
- `pytest`, `pytest.skip`, `pytest.mark.parametrize`, `pytest.mark.parity_noambrown`, `pytest.approx`.

From stdlib:
- `pathlib.Path`, `subprocess`, `tempfile`, `numpy`.

## Test plan (master list — implement EVERY test below)

Per PR 7 spec §5 (the diff harness logic) and §10 Agent B. Each test gets a function definition; names map to the PR 7 spec sections.

### Module-level fixture

```python
import pytest
from pathlib import Path
from poker_solver.parity.noambrown_wrapper import load_spots, find_brown_binary

REPO_ROOT = Path(__file__).resolve().parent.parent
SPOTS_JSON = REPO_ROOT / "tests" / "data" / "river_spots.json"


@pytest.fixture(scope="module")
def all_spots():
    """Load 15 river spots once per test module run."""
    return load_spots(SPOTS_JSON)
```

### Parametrized diff test (the headline; 1 function, 15 invocations)

```python
@pytest.mark.parity_noambrown
@pytest.mark.parametrize(
    "spot",
    load_spots(SPOTS_JSON),  # collected at import time
    ids=lambda s: s.id,
)
def test_river_parity_vs_brown(spot):
    """Per-spot differential test vs Noam Brown's river_solver_optimized.

    For each spot:
    1. If Brown's binary is missing → pytest.skip with informative message.
    2. Solve with our engine at `spot.iterations_override or 2000` iterations.
    3. Solve with Brown's binary at the same iteration count.
    4. Canonicalize both result sets to the same (canonical_history, hand) →
       action_distribution schema via Agent A's helpers.
    5. Take the intersection of canonical history keys present in BOTH engines.
    6. For each shared (history, hand), for each action: assert
       abs(our_prob - brown_prob) < 5e-3.
    7. Assert abs(our_game_value - brown_game_value) < 1e-3 * spot.pot.
    8. Assert at least 80% of Brown's history keys appear in our canonicalized
       result (catches accidental tree-truncation in either engine).

    Tolerances: 5e-3 per-action, 1e-3 * pot per game value. Locked per PR 7 §1.
    """
    ...
```

### Infrastructure test (1 function)

```python
def test_brown_binary_buildable():
    """Invoke scripts/build_noambrown.sh and assert binary exists afterward.

    Skip cleanly if cmake or c++ is missing (toolchain-free CI stays green).
    PR 7 spec §10 Agent B: "skips if cmake missing".
    """
    import shutil
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake or c++ unavailable; cannot build Brown's binary")
    script = REPO_ROOT / "scripts" / "build_noambrown.sh"
    if not script.exists():
        pytest.skip("scripts/build_noambrown.sh missing")
    # Invoke the script; expect exit 0 even on idempotent re-runs.
    import subprocess
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, f"build script failed: {result.stderr}"
    binary = find_brown_binary()
    assert binary is not None, "binary still missing after successful build"
    assert binary.exists(), f"binary path returned but file missing: {binary}"
```

### Auxiliary helpers (private to your test module)

You may add private helpers (prefix with `_`) for:
- `_solve_with_our_engine(spot)` — wraps Agent A's `solve_river_subgame_*` helper if available; otherwise builds a `HUNLConfig` with `starting_street=Street.RIVER, initial_board=spot.board, initial_pot=spot.pot, initial_contributions=(spot.pot//2, spot.pot//2), starting_stack=spot.stack, bet_size_fractions=tuple(spot.bet_sizes), include_all_in=spot.include_all_in, postflop_raise_cap=spot.max_raises, abstraction=None` and invokes our solver. Return `(SolveResult, game_value_chips: float)`.
- `_intersect_histories(our_matrix, brown_dump)` — returns the set of canonical history strings present in BOTH outputs, plus the per-hand action-list (zipped from Brown's `actions` tuple).
- `_compare_action_distributions(our_dist, brown_dist, tol)` — element-wise `abs` comparison with informative failure messages (which spot, which history, which hand, which action, which actual vs expected). Use `pytest.fail` with structured details rather than `assert` for actionable diagnostics on failure.

## Critical correctness items

### 1. Tolerance arithmetic

- **Per-action:** `assert abs(our_prob - brown_prob) < 5e-3`. NOT `pytest.approx(brown_prob, abs=5e-3)` — the explicit `abs(...)` style produces better failure messages.
- **Per-spot game value:** `assert abs(our_value - brown_value) < 1e-3 * spot.pot`. The threshold scales with pot size. For `spot.pot=1000`, threshold = `1.0` chip.

Match the assertion style of `tests/test_dcfr_diff.py` for consistency.

### 2. History intersection (PR 7 §5 step 5–6)

Both engines may produce histories the other doesn't (Brown's binary tree may include states our solver pruned, or vice versa due to action-abstraction differences). The comparison is on the **intersection** of canonical histories, AND we assert ≥80% Brown coverage:

```python
brown_keys = set(brown_dump.players[0].profile.keys()) | set(brown_dump.players[1].profile.keys())
our_keys = set(our_matrix.keys())  # from our_strategy_to_brown_matrix output
shared = brown_keys & our_keys
coverage = len(shared) / max(len(brown_keys), 1)
assert coverage >= 0.80, f"{spot.id}: only {coverage:.1%} of Brown histories present in our solve"
```

If coverage is below 80%, the diagnostic message should list the FIRST few missing keys to help debug.

### 3. Hand-keyed comparison

Brown's strategy matrix is `(num_hands, num_actions)` per infoset, indexed by Brown's hand list. Our canonicalized matrix (Agent A's `our_strategy_to_brown_matrix`) uses the SAME hand ordering (because Agent A is responsible for mapping). When comparing:

```python
for history in shared:
    brown_entry = brown_dump.players[player].profile[history]
    our_entry = our_matrix[history][player]  # np.ndarray (num_hands, num_actions)
    assert our_entry.shape == (len(brown_entry.strategy), len(brown_entry.actions)), \
        f"shape mismatch at {history}"
    for h_idx in range(our_entry.shape[0]):
        for a_idx in range(our_entry.shape[1]):
            ours = our_entry[h_idx, a_idx]
            theirs = brown_entry.strategy[h_idx][a_idx]
            assert abs(ours - theirs) < 5e-3, (
                f"{spot.id}, history={history!r}, hand_idx={h_idx}, "
                f"action={brown_entry.actions[a_idx]!r}: "
                f"our={ours:.4f} vs brown={theirs:.4f}"
            )
```

### 4. Game value extraction

- Brown's game value: from `BrownStrategyDump.game_value_p0` (Agent A parses from stdout). If `None`, skip the game-value assertion for that spot and warn (the per-action assertions still run).
- Our game value: from `SolveResult.game_value` (PR 1 `poker_solver/solver.py`). Brown emits values in chips; ours may be in BB-units (`utility()` returns `c0 / bb`). **Multiply our value by `spot.big_blind` (or by `cfg.big_blind`) to get chips.** Verify the unit conversion carefully — the comparison threshold `1e-3 * spot.pot` is in chips.

If unit conversion is ambiguous, flag in the report and use a generous tolerance (`5e-3 * spot.pot`) temporarily while flagging.

### 5. Skip-on-missing-binary semantics

```python
def test_river_parity_vs_brown(spot):
    binary = find_brown_binary()
    if binary is None:
        pytest.skip(
            "Brown's river_solver_optimized not built; "
            "run `bash scripts/build_noambrown.sh` to enable parity tests."
        )
    ...
```

The skip path must NOT do any expensive work first. Check `find_brown_binary()` at the TOP of the test function.

### 6. Marker registration in `pyproject.toml`

Find the pytest marker section. It's likely:
```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    # ... existing markers ...
]
```

Add (idempotent):
```toml
"parity_noambrown: marks tests as Brown's river-solver parity diff (deselect with '-m \"not parity_noambrown\"')",
```

If no `markers` list exists yet, create the section. If `pyproject.toml`'s pytest config lives elsewhere (e.g., `pytest.ini` or `setup.cfg`), check there first; the spec says `pyproject.toml` so default to it unless evidence indicates otherwise.

### 7. Subprocess isolation (pytest-xdist safe)

Per PR 7 §9 risk #8: when xdist runs spots in parallel, ensure each test gets a unique temp directory. Agent A's `run_brown_solver` should already handle this (per Agent A contract); if you discover it doesn't, raise a flag rather than working around it.

### 8. Iteration count fairness

Both engines run the SAME iteration count for a given spot:
```python
iters = spot.iterations_override or 2000
our_result = _solve_with_our_engine(spot, iterations=iters)
brown_dump = run_brown_solver(spot, binary, iterations=iters, seed=7)
assert brown_dump.iterations_run == iters, "Brown didn't run requested iterations"
```

### 9. Brown's "root" history

Brown's empty/root history is the string `"root"` (per `cpp/src/main.cpp:204`). Our solver's root river-start infoset has an empty current-street-tokens segment. Agent A's canonicalizer normalizes "root" to `()` (empty tuple). Verify the empty-history case is in the shared set when expected.

### 10. Suit-isomorphism is NOT applied in PR 7

Per PR 7 spec §3: "No EMD-bucketed inputs" — we use the lossless representation (no abstraction). Our solver iterates over the **explicit** range. Suit-iso (PR 4) does not affect the PR 7 fixture — every hand in the range is its own entry.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only inspiration. Brown's binary is invoked, never copied.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/`, `references/code/TexasSolver/` — **AGPL v3**. Not relevant to PR 7's tests.

**You may NOT extrapolate from training data.** If you "remember" how pytest parametric differential tests look, ground in `tests/test_dcfr_diff.py` + `tests/test_leduc_diff.py`. These are local authoritative sources.

## Quality bar

- **ruff clean:** `ruff check tests/test_noambrown_river_parity.py` reports zero issues.
- **black clean:** `black --check tests/test_noambrown_river_parity.py` reports no changes needed.
- **All existing tests still pass.** Run `pytest -x -m "not parity_noambrown"` to confirm the rest of the suite is unaffected. The parity test is opt-in via the marker.
- **Marker is properly registered** in `pyproject.toml`. Running `pytest --markers` shows `parity_noambrown` in the list.
- **No new third-party dependencies.** Standard library + `pytest` + `numpy` + existing `poker_solver`-internal imports only.
- **Code size budget:** ~250-400 LOC for the test file. Stay within budget; do not over-engineer helpers.
- **Per-spot test reaches the assertion stage** when binary is present (i.e., it doesn't error out in setup; the assertions either pass or produce actionable failures).

## Reference-first rule

Before any technical claim, cite the local reference. Never extrapolate from training data when a local authoritative source exists.

If a fact is needed (e.g., "5e-3 per-action threshold matches PR 6 / PR 7 / PR 8"), cite spec consistency review I3 or PR 7 spec §1. If you need to know Brown's strategy JSON schema, cite `cpp/src/main.cpp:222-290` (referenced by Agent A's docstring).

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check tests/test_noambrown_river_parity.py
black --check tests/test_noambrown_river_parity.py

# 2. Marker is registered
pytest --markers 2>&1 | grep -i "parity_noambrown" && echo "marker registered"

# 3. Tests collect cleanly (parametric IDs visible)
pytest tests/test_noambrown_river_parity.py --collect-only 2>&1 | head -30

# 4. Run the parity tests (skips cleanly if binary missing)
pytest tests/test_noambrown_river_parity.py -v 2>&1 | tail -40
# If toolchain present: all 15 should PASS plus the infra test.
# If toolchain missing: all should SKIP with informative messages.

# 5. Existing test suite still passes when we deselect the parity marker
pytest -x -m "not parity_noambrown" 2>&1 | tail -20

# 6. Existing test suite still passes WITH the parity marker on systems without binary (skips)
pytest -x 2>&1 | tail -20
```

If any step fails (other than the parity tests skipping cleanly), fix the issue before reporting done. If a smoke test reveals a spec ambiguity (e.g., Agent A didn't expose `solve_river_subgame` and PR 7 spec §5 step 2 implies you need it), **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created/modified with line counts.
2. Any spec amendment you made or contract drift you flagged (and why). Specifically:
   - Did Agent A expose a `solve_river_subgame(...)` helper, or did you have to construct `HUNLConfig` directly?
   - Did `SolveResult.game_value` come back in chips or BB-units? What conversion did you apply?
   - Did the 80% coverage threshold hold on a typical spot, or did Brown produce many more histories than our solver?
3. Verification command output (paste tails).
4. Per-spot tolerance results when run with binary present (or note that toolchain was unavailable and tests skipped).
5. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
6. Whether you observed any spots that needed `iterations_override` to converge (a signal that 2000 iters is insufficient for that spot).
