# PR 7 spec — river-spot differential test vs `noambrown/poker_solver`

## 1. Goal

Differential-test our HUNL river solves against **Noam Brown's MIT-licensed `noambrown/poker_solver`** (the DCFR author's own reference) on a curated set of 10–20 river spots. For each spot we run our `solve()` and Brown's `river_solver_optimized` binary on the same `(board, ranges, pot, stack, bet_sizes)` input, then compare strategies and game values. **Pass criteria:** per-action average-strategy probabilities agree within **5e-3**; per-spot game values (in chips) agree within **1e-3 × base_pot**. This is the last correctness gate before PR 8 starts perf-mutating the Rust engine.

## 2. Why this matters

Noam Brown is the DCFR author (Brown & Sandholm 2019). His `noambrown/poker_solver` repo is the **gold-standard MIT-licensed river-only reference**: a clean Python+C++ pair with the *exact* algorithm we ship (DCFR α=1.5, β=0, γ=2.0; see `references/code/noambrown_poker_solver/cpp/src/trainer.h:16-20` and `cpp/src/trainer.cpp:353-361`). Catching a divergence here means catching a real bug in our solver — not in our abstraction (PR 4) and not in our Rust port (PR 6). Three properties of Brown's repo make it the right gate:

- **Same algorithm.** Brown's `Algorithm::DCFR` branch (`cpp/src/trainer.cpp:353-361`) computes `pos_base = t^alpha`, `neg_base = t^beta`, `strat_scale = (t/(t+1))^gamma` with the exact paper defaults we use.
- **Same shape.** River-only HUNL with pot-fraction bet sizing, `(label, amount)` action tuples, fold-or-showdown terminals (`cpp/src/river_game.cpp:114-156`). Maps 1:1 to our `HUNLConfig(starting_street=Street.RIVER, ...)` invocation (see `poker_solver/hunl.py:165-189` for `default_tiny_subgame`).
- **Same license.** MIT (see `references/code/noambrown_poker_solver/LICENSE:1-21`). We may invoke the binary, parse its output, and even port code with attribution — but PR 7 only *invokes* it; we do not copy.

This is the cross-validation arm of the validation chain that PLAN.md §4 mandates: "River-only HUNL spots → diff vs `noambrown/poker_solver`".

## 3. What PR 7 does NOT do

- **No flop/turn diff.** Brown's repo is **river-only** (single street, all 5 board cards pre-dealt). Our flop/turn solves cannot be cross-validated this way — they require PR 4's bucketing, which has no external authoritative reference. Flop sanity is covered later by AGPL-licensed read-only inspection of `b-inary/postflop-solver` and by the poker-intuition gauntlet (PLAN.md §4).
- **No Rust diff against Brown.** That comparison lives in PR 6 (Rust port) via the existing `tests/test_dcfr_diff.py` pattern (`tests/test_leduc_diff.py:1` is the template). PR 7 only diffs Python ↔ Brown.
- **No multiway diff.** Brown's repo is HU only (`std::array<..., 2>` in `cpp/src/river_game.h:42-43`).
- **No EMD-bucketed inputs.** Brown stores the full 1326-hand range with explicit weights (`cpp/src/river_game.h:42-43`, `cpp/src/river_game.cpp:213-251`); we use the same lossless representation by *not* attaching an `AbstractionTables` to `HUNLConfig`. The river abstraction (PR 4) is bypassed for this test. This keeps the comparison apples-to-apples.
- **No iteration-by-iteration trace comparison.** Convergence trajectories diverge due to FP rounding even between identical implementations; we compare only the **converged average strategy** at a fixed iteration count, the same way PLAN.md "Differential tests" do for Python ↔ Rust.
- **No CFR / CFR+ / LCFR diffs.** Brown exposes four algorithms (`Algorithm::CFR`, `CFR_PLUS`, `LINEAR_CFR`, `DCFR`; see `cpp/src/trainer.h:9-14`); we only diff DCFR. PR 7 invokes Brown with `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2`.
- **No MCCFR diff.** Brown's `MCCFRTrainer` (`cpp/src/mccfr.h`) is sampled / stochastic; we use full-traverse DCFR. Comparing the two is apples-to-oranges.

## 4. Test fixture design (`tests/data/river_spots.json`)

A canonical, version-controlled file with **15 hand-picked spots** spanning the river texture space. Format mirrors Brown's subgame JSON schema (`cpp/src/subgame_config.h:7-22`, `cpp/src/subgame_config.cpp:303-388`) so the same file feeds both engines:

```json
{
  "schema_version": 1,
  "spots": [
    {
      "id": "dry_K72_rainbow",
      "description": "Dry rainbow K72: tight ranges, 100 BB single bet size",
      "board": ["Ks", "7h", "2d"],
      "_board_note": "WAIT — river is 5 cards; see Decision 12.3",
      "board_river": ["Ks", "7h", "2d", "4c", "Jh"],
      "pot": 1000,
      "stack": 9500,
      "bet_sizes": [0.75, 1.5],
      "include_all_in": true,
      "max_raises": 1000,
      "players": [
        {"hands": ["AhKh", "..."], "weights": [1.0, "..."]},
        {"hands": ["QdQc", "..."], "weights": [1.0, "..."]}
      ]
    }
  ]
}
```

**Spot list (15 entries, ~3 per category):**

| Category | Spots (board examples) |
|---|---|
| Dry rainbow | `Ks 7h 2d 4c Jh`, `Ah 8c 3d Tc 6s`, `Qh 5s 2c 9d 4h` |
| Wet rainbow | `Ts 9h 8d 5c 2h`, `Jh Tc 9d 4h 3s`, `8s 7h 6c 5d 2h` |
| Monotone | `As Ks 7s 4s 2c`, `Th 8h 5h 3h Jd`, `Qs Js 9s 4s 2h` |
| Paired | `Ah Ad 7c 4h 2s`, `Ks 7h 7d 4c 2h`, `Jh Th Tc 5d 3s` |
| Broadway-heavy | `Ah Kh Qd Jc 2s`, `Ks Qc Jh Ts 4d`, `As Th Jc Qh Kd` |

Each spot specifies:
- 5 board cards (river street has all 5 dealt)
- per-player **explicit hand list + weights** (≈30–60 combos per range; lossless — no abstraction)
- pot in chips (Brown uses integer chips; we will too — see Decision 12.4)
- stack per player (assumed equal; Brown's `cpp/src/river_game.h:38` has a single `stack int`)
- bet_sizes as pot fractions (Brown matches our convention)
- `include_all_in: true`, `max_raises: 3` (matches our postflop cap; PLAN.md §1 "Raise caps: postflop 3")

**Range design rule:** ranges must (a) include both made hands and bluff candidates, (b) total ≥30 combos per side (smaller ranges produce trivial strategies and weak signal), (c) not overlap with the board (filtered at fixture-build time). Recipe: take a 25% PFR vs 35% defending range, polarize OOP, condensed IP.

**File size budget:** 15 spots × ~50 hands × ~30 bytes per hand = ~22 KB. Well under the 100 KB hard ceiling for `tests/data/` files.

**Reproducibility:** the JSON file is hand-authored and committed. No random seeds enter fixture construction.

## 5. Diff harness design (`tests/test_noambrown_river_parity.py`)

One pytest module. For each spot:

1. **Load** the spot from `tests/data/river_spots.json`.
2. **Solve with our engine.**
   - Construct `HUNLConfig(starting_street=Street.RIVER, initial_board=spot.board_river, initial_pot=spot.pot, initial_contributions=(spot.pot//2, spot.pot//2), starting_stack=spot.stack, bet_size_fractions=tuple(spot.bet_sizes), include_all_in=spot.include_all_in, postflop_raise_cap=spot.max_raises, abstraction=None)`. (See `poker_solver/hunl.py:80-103`.)
   - Set `initial_hole_cards=()` (PR 7's solver iterates over the explicit range, not a single combo). This may require a small extension: PR 7 introduces a `solve_river_subgame(config, range_p0, range_p1, iterations)` helper in `poker_solver/parity/noambrown_wrapper.py` that runs our DCFR loop once per (hand_p0, hand_p1) pair and aggregates the per-hand strategies — matching Brown's vectorized layout.
   - Run **fixed iteration count: 2000** (matches Brown's default `--iters 2000` in `cpp/src/main.cpp:31`).
3. **Solve with Brown's engine via subprocess.**
   - Invoke `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized --config /tmp/spot_<id>.json --algo dcfr --iters 2000 --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --dump-strategy /tmp/spot_<id>.strategy.json`.
   - The subgame JSON is written from the fixture spot (same schema as `cpp/src/subgame_config.cpp:303-388`).
   - The strategy dump (see `cpp/src/main.cpp:222-290`) emits a JSON with per-infoset, per-hand action probabilities — exactly what we need.
4. **Parse Brown's output.** See `poker_solver/parity/noambrown_wrapper.py` (Section 7).
5. **Map infosets.** Brown's infoset keys (`cpp/src/main.cpp:176-219`) are `/`-joined action tokens like `"root"`, `"b500"`, `"b500/c"`, `"b500/r1000/c"`. Our keys (`poker_solver/hunl.py:312-321`) are formatted as `f"{player_hole}|{board}|{street_token}|{history}"` where history uses `b<amount>`, `r<to_total>`, `c`, `x`, `f`, `A` tokens (`poker_solver/hunl.py:378-401`).
   - **Critical canonicalization step**: convert both into a *betting-history-only, hand-keyed* form. Drop board and hole cards from our key; keep just the betting sequence. Our action tokens map to Brown's as follows:
     - `c` (check/call) → `c`
     - `x` (check) → `c` (same in Brown — `cpp/src/main.cpp:182`)
     - `f` (fold) → `f`
     - `b<amount>` (bet) → `b<amount>` (identical — both encode bet *amount* in chips, see Brown `cpp/src/main.cpp:184-186`)
     - `r<to_total>` → `r<delta>` where `delta = to_total - prev_aggressor_contrib` (Brown stores **raise extra-beyond-call**, not raise-to; see `cpp/src/main.cpp:193-194` and `cpp/src/river_game.cpp:80-93`)
     - `A` (all-in) → `b<remaining>` or `r<remaining-to_call>` depending on whether there's a bet to call (Brown does not have a special "all-in" token; it just emits the bet/raise amount; see `cpp/src/river_game.cpp:63-66, 98-100`)
6. **Assert per-action agreement.** For each (infoset, hand) common to both engines, assert |our_prob[action] - brown_prob[action]| < 5e-3. For each spot, assert |our_game_value - brown_game_value| < 1e-3 × spot.pot. Brown's game value is computed by `Trainer::best_response_value(0)` etc (`cpp/src/trainer.cpp:307-335`); ours by `solve()`'s `SolveResult.game_value` (`poker_solver/solver.py:71-77`).
7. **Skip cleanly if binary missing.** If `cpp/build/river_solver_optimized` does not exist (no C++ compiler / cmake on the system), pytest skip with `pytest.skip("Brown's river_solver_optimized not built; run scripts/build_noambrown.sh")`. Do **not** fail.

**Test marker:** `@pytest.mark.parity_noambrown` so CI can opt-out the slow path if needed. Default = on.

**Test runtime budget:** 15 spots × ~30 s/spot (Brown solver + our solver + comparison) = ~7.5 min. Acceptable for a per-PR check; not a blocker.

## 6. Brown solver build wrapping (`scripts/build_noambrown.sh`)

A one-shot, idempotent bash script. Pseudocode:

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC=references/code/noambrown_poker_solver/cpp
BUILD=$SRC/build
BIN=$BUILD/river_solver_optimized

# Idempotency: skip if binary exists and is newer than every .cpp/.h.
if [[ -x $BIN ]] && find "$SRC/src" -newer "$BIN" -type f | grep -q .; then
  : # something is newer; rebuild
elif [[ -x $BIN ]]; then
  echo "Brown's binary already up-to-date at $BIN"
  exit 0
fi

# Probe build environment.
command -v cmake >/dev/null || { echo "cmake missing; skipping"; exit 0; }
command -v c++   >/dev/null || { echo "c++ missing; skipping"; exit 0; }

cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j

[[ -x $BIN ]] && echo "Built: $BIN" || { echo "Build failed"; exit 1; }
```

Key properties:
- **Idempotent:** rebuild only if any `.cpp`/`.h` is newer than the binary. Otherwise no-op.
- **Soft-fail on missing tools:** if cmake or a C++ compiler is unavailable, print an informative message and `exit 0` (not `exit 1`). The test harness handles the missing-binary case with `pytest.skip`.
- **No git submodule fuss:** `references/code/noambrown_poker_solver/` is already vendored as a directory tree (per `references/README.md`); we build in place.
- **Out-of-tree build:** all artifacts go under `references/code/noambrown_poker_solver/cpp/build/` — gitignored via `references/code/.gitignore` (or extend the root `.gitignore` if needed; verify in PR open).

**CMake invocation matches** Brown's `cpp/CMakeLists.txt:14-22` (single `river_solver_optimized` target, Release default at `cpp/CMakeLists.txt:8-10`, `-O3 -march=native -ffast-math` for non-MSVC at `cpp/CMakeLists.txt:32`).

## 7. Files to create

| Path | Owner | Purpose |
|---|---|---|
| `scripts/build_noambrown.sh` | Agent A | Idempotent build of Brown's C++ binary (Section 6) |
| `tests/data/river_spots.json` | Agent A | 15 canonical river fixture spots (Section 4) |
| `poker_solver/parity/__init__.py` | Agent A | Empty package init |
| `poker_solver/parity/noambrown_wrapper.py` | Agent A | Subprocess invocation + output parsing + history canonicalization (Section 5 step 5) |
| `tests/test_noambrown_river_parity.py` | Agent B | The diff test module (Section 5) |
| `tests/test_noambrown_self_sanity.py` | Agent C | Smaller smoke test: our engine alone, asserting it produces stable outputs on the fixture spots (Section 11) |

No existing files are *modified* by PR 7 except (possibly) `pyproject.toml` if we add `pytest.mark.parity_noambrown` to the `markers` list, and `.gitignore` to ignore Brown's build artifacts.

## 8. License + attribution

Brown's `noambrown/poker_solver` is **MIT-licensed** (verified at `references/code/noambrown_poker_solver/LICENSE:1-21`, Copyright (c) 2025 Noam Brown). Our PR 7 use:

- **We invoke the binary.** Not a derivative work under any reading.
- **We parse the JSON output it emits.** Not a derivative work.
- **We do NOT copy code.** No verbatim port; no algorithmic adaptation; no header-file reuse. Our `noambrown_wrapper.py` is original.
- **We DO depend on Brown's CLI surface** (`--algo`, `--iters`, `--dcfr-alpha/beta/gamma`, `--dump-strategy`, `--config`) and his output JSON schema (`cpp/src/main.cpp:222-290`). These are public interface, not licensed code.

**Attribution header in `poker_solver/parity/noambrown_wrapper.py`:**

```python
"""Wrapper around Noam Brown's river_solver_optimized for differential testing.

This file invokes (via subprocess) and parses output from
`noambrown/poker_solver` (https://github.com/noambrown/poker_solver, MIT
Licensed, Copyright (c) 2025 Noam Brown). No source code from that repo
is copied here; this wrapper depends only on the public CLI flags and
JSON output format documented in:

  - references/code/noambrown_poker_solver/cpp/src/main.cpp (CLI flags)
  - references/code/noambrown_poker_solver/cpp/src/main.cpp:222-290 (output schema)
  - references/code/noambrown_poker_solver/LICENSE (MIT terms)

License of the wrapper itself: MIT (same as this project).
"""
```

No NOTICE file changes required (MIT does not mandate one). We update `references/README.md` to note that Brown's repo is now also a runtime dependency of the PR 7 differential test (not just a read-only reference).

## 9. Risks

1. **Action-token semantics drift.** Brown stores raises as **extra-beyond-call** (`cpp/src/river_game.cpp:88-93`, `cpp/src/main.cpp:193-194`); we store as **raise-to-total** (`poker_solver/hunl.py:391-401`). The canonicalization in Section 5 step 5 is load-bearing — a bug here will produce spurious diff failures. *Mitigation:* Agent A writes parametric unit tests for `_canonicalize_history()` that round-trip ten hand-built histories through both encodings.

2. **Rule subtleties differ.** Brown does not model rake (we don't either in PR 7 — `HUNLConfig.rake_rate=0.0` is asserted in `poker_solver/hunl.py:106-107`). Brown uses integer chip units (we use integer cents; 1 BB = 100 cents per `poker_solver/hunl.py:1-10`). Brown's "to_call" handling differs subtly on partial all-ins. *Mitigation:* fixtures use **equal effective stacks** and **whole-BB pot+stack values** to keep these edges out of scope. Tests assert `spot.stacks[0] == spot.stacks[1]` and `spot.pot % spot.big_blind == 0`.

3. **Build environment missing.** No cmake or C++ compiler → no Brown binary → no diff. *Mitigation:* `scripts/build_noambrown.sh` exits 0 with a message; `tests/test_noambrown_river_parity.py` skips with informative `pytest.skip(...)`. Open question 12.3.

4. **Tolerance threshold may be too tight (or too loose).** Both engines run finite-iteration DCFR; the converged averages differ at the 1e-3 to 1e-2 scale even between identical implementations due to FP order-of-summation. *Mitigation:* the spec defaults to 5e-3 per-action and 1e-3 × pot for value (matching the Python-Rust diff tolerance in `tests/test_dcfr_diff.py`); Agent C empirically calibrates this on the 15 spots before fixing. Open question 12.1.

5. **Brown's strategy output format differs from ours.** Brown emits `(infoset_key → action_list, strategy_matrix[hand][action])` (`cpp/src/main.cpp:266-285`); we currently emit `(infoset_key → action_probability_list)` from `SolveResult.average_strategy`. The wrapper must aggregate our per-hand strategies into Brown's matrix shape. *Mitigation:* `noambrown_wrapper.py` has a dedicated `our_strategy_to_brown_matrix(result, hands)` adapter; tested standalone in `test_noambrown_self_sanity.py`.

6. **Iteration count may be inadequate for convergence parity.** At 2000 iterations both engines may still be 1–2% from equilibrium on complex spots, and the difference between them in that regime exceeds 5e-3. *Mitigation:* if a spot fails, the fix is increasing iterations (e.g., to 10000) for that spot only — encoded in the fixture as `"iterations": 10000` override.

7. **Range overlap with board.** Hands containing a board card must be filtered. Brown filters silently in `cpp/src/river_game.cpp:228-240`; our spec requires the fixture to pre-filter (assert no overlap at load time, with a clear error). *Mitigation:* `noambrown_wrapper.py::load_spots` validates and rejects overlapping-card spots with a fixture-file line-number error.

8. **Race condition on subprocess invocation in pytest-xdist.** If pytest-xdist runs spots in parallel, multiple processes may write to the same `/tmp/spot_*.json` file. *Mitigation:* use `tempfile.NamedTemporaryFile` per call; each test gets a unique temp directory.

9. **Brown's binary path is not portable.** Hardcoding `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` works on dev machines but might fail in CI. *Mitigation:* the wrapper resolves the path via `Path(__file__).resolve().parents[2] / "references" / "code" / ...` (anchored to the repo root, not the cwd).

## 10. Three-agent fan-out plan

Same pattern as PR 3, 3.5, 4: tight per-agent specs against the interfaces in Sections 5–7. Launch concurrently. Integrate at the end.

### Agent A — build wrapper + spot fixtures + wrapper module

**Owns:** `scripts/build_noambrown.sh`, `tests/data/river_spots.json`, `poker_solver/parity/__init__.py`, `poker_solver/parity/noambrown_wrapper.py`.

**Does NOT touch:** any test file, `poker_solver/hunl.py`, `poker_solver/solver.py`.

**Deliverables:**

- `scripts/build_noambrown.sh` — per Section 6: idempotent, soft-fails on missing tools, build out-of-tree under `references/code/noambrown_poker_solver/cpp/build/`.
- `tests/data/river_spots.json` — exactly 15 spots per Section 4, schema_version=1, hand-authored, no random seeds.
- `poker_solver/parity/noambrown_wrapper.py` — module with:
  - `load_spots(path: Path) -> list[RiverSpot]` — JSON loader with full validation (no overlapping board/hand cards; bet_sizes are floats in (0, 5]; pot/stack are positive ints; player count == 2).
  - `RiverSpot` dataclass: `id: str`, `description: str`, `board: tuple[Card, ...]`, `pot: int`, `stack: int`, `bet_sizes: tuple[float, ...]`, `include_all_in: bool`, `max_raises: int`, `ranges: tuple[list[tuple[Combo, float]], list[tuple[Combo, float]]]`, `iterations_override: int | None`.
  - `find_brown_binary() -> Path | None` — returns the path or None if not built.
  - `write_brown_config(spot: RiverSpot, path: Path) -> None` — emits a JSON in Brown's subgame schema (`cpp/src/subgame_config.h:7-22`) that the binary can load with `--config PATH`. Note: Brown's schema does not include `iterations_override` — that's a wrapper-level field we pass via CLI flag.
  - `run_brown_solver(spot: RiverSpot, binary: Path, iterations: int) -> BrownStrategyDump` — subprocess invocation; returns a parsed `BrownStrategyDump` dataclass.
  - `BrownStrategyDump` dataclass: `players: tuple[BrownPlayerProfile, BrownPlayerProfile]` where each `BrownPlayerProfile` has `hands: tuple[str, ...]`, `weights: tuple[float, ...]`, `profile: dict[str, BrownInfosetEntry]` and each `BrownInfosetEntry` has `actions: tuple[str, ...]`, `strategy: tuple[tuple[float, ...], ...]` (per-hand × per-action probabilities). Format matches `cpp/src/main.cpp:222-290`.
  - `canonicalize_brown_history(token: str) -> CanonicalHistory` — split on `/`, parse each token via the rules in Section 5 step 5, return a tuple of `(action_kind, amount)` pairs.
  - `canonicalize_our_history(history: str) -> CanonicalHistory` — same return type, applied to our `infoset_key`-derived history substring; normalizes raise-to ↔ raise-extra-beyond-call.
  - `our_strategy_to_brown_matrix(result: SolveResult, hands: tuple[Combo, ...], infoset_keys: dict[str, str]) -> dict[str, np.ndarray]` — flatten our per-(hand, infoset) probabilities into Brown's matrix shape, keyed by canonicalized history.
- Type-hinted; `mypy --strict` clean. Pure Python + standard library + numpy + the existing `poker_solver` imports. No new dependencies.

### Agent B — diff harness

**Owns:** `tests/test_noambrown_river_parity.py`.

**Does NOT touch:** any non-test file. Reads (does not modify) `poker_solver/parity/noambrown_wrapper.py`, `poker_solver/hunl.py`, `poker_solver/solver.py`, `tests/data/river_spots.json`.

**Deliverables:**

- `test_noambrown_river_parity.py` — module-scoped fixture loads spots once; per-spot test parameterized via `pytest.mark.parametrize("spot", load_spots(...), ids=lambda s: s.id)`.
- Per-spot test logic per Section 5 steps 1–7:
  1. If binary missing → `pytest.skip` with informative message.
  2. Solve with our `solve()` at 2000 iterations (or spot.iterations_override).
  3. Solve with Brown's binary at the same iteration count.
  4. Canonicalize both result sets to the same `(canonical_history, hand) → action_distribution` schema.
  5. Take the intersection of canonical history keys present in both engines.
  6. For each shared (history, hand), for each action, assert `abs(our_prob - brown_prob) < 5e-3`.
  7. Assert `abs(our_game_value - brown_game_value) < 1e-3 * spot.pot`.
- Per-spot assertion: at least **80%** of Brown's histories appear in our canonicalized result (catches accidental tree-truncation in either engine).
- Pytest marker `@pytest.mark.parity_noambrown` registered in `pyproject.toml`.
- One additional infra test `test_brown_binary_buildable` that runs `scripts/build_noambrown.sh` and asserts the binary exists afterwards — **but skips if cmake missing** (so CI without a compiler stays green).
- Test file is self-contained; no Helpers / fixtures live elsewhere except `noambrown_wrapper.py` (Agent A's territory).

### Agent C — self-sanity smoke test

**Owns:** `tests/test_noambrown_self_sanity.py`.

**Does NOT touch:** any non-test file. Does NOT invoke Brown's binary (Agent C's tests run even without the build).

**Deliverables:**

- `test_noambrown_self_sanity.py` — runs our engine alone on the first 3 fixture spots, asserts:
  1. `test_each_spot_loads_into_hunl_config` — `load_spots()` results round-trip into a valid `HUNLConfig(starting_street=Street.RIVER, ...)` with no errors.
  2. `test_each_spot_solver_converges` — 2000 iterations gives `exploitability < 0.02 * pot` (loose; just confirms convergence, not optimality).
  3. `test_each_spot_game_value_is_finite` — `result.game_value` is finite and bounded by `[-pot, pot]`.
  4. `test_canonicalize_history_roundtrip` — for ten hand-built histories, `canonicalize_our_history(canonicalize_brown_history(our_history))` is identity (sanity for the canonicalizer, since the diff test depends on it).
  5. `test_strategy_matrix_shape` — `our_strategy_to_brown_matrix()` produces matrices of shape `(len(hands), num_actions)` for every canonical history.
  6. `test_no_overlap_in_fixture_ranges` — for every fixture spot, no hand in either range shares a card with the board (fixture-correctness gate).
  7. `test_iterations_override_respected` — a spot with `iterations_override=500` runs 500 iterations, not 2000.
  8. `test_brown_binary_finder_returns_path_or_none` — `find_brown_binary()` returns either an existing path or `None`; no exceptions.
- These tests **do not require Brown's binary to be built.** They run on any machine that has the rest of the project working. They serve as the "is the wrapper sane?" gate, separate from the actual diff.

Agent C writes from spec alone; does not see A/B code while writing. Allowed to surface ambiguities — those round-trip to spec edits, not silent test tweaks.

## 11. Critical correctness items

The user-flagged items, mapped to the spec:

1. **Fixture spots are reproducible (no random seeds vary outputs).** Section 4: the JSON file is hand-authored, no `rng.choice` in `load_spots`, and Brown's `--algo dcfr` is deterministic given seed (`cpp/src/main.cpp:36` defaults `seed = 7`; we explicitly pass `--seed 7` for paranoia). Our DCFR is also deterministic (`poker_solver/dcfr.py:47-48`: "DCFR is deterministic; seed accepted for forward-compat").
2. **Brown's binary output is parsed deterministically.** Section 5 step 5: parsing uses Python `json.load` + structured dataclass mapping. The canonicalizer is pure (history string in → tuple out, no global state).
3. **Tolerance threshold is justified.** Section 1 and Section 9 risk 4: 5e-3 per-action matches the existing `tests/test_dcfr_diff.py` and `tests/test_leduc_diff.py` thresholds. 1e-3 × pot for game values is the standard "0.1% of pot" gate.
4. **Build script is idempotent.** Section 6: rebuild only when source is newer than binary; soft-fail when toolchain missing.

## 12. Open decisions (defer to user)

1. **Tolerance threshold per action: 5e-3 (default), 1e-3 (tight), or 1e-2 (loose)?** Default 5e-3 is consistent with `tests/test_leduc_diff.py`; tighter risks false positives on long-tail FP differences between Python and C++; looser risks missing real bugs. Recommend keeping 5e-3 unless empirical calibration in Agent C shows otherwise.

2. **Test set size: 10, 15, or 20 spots?** Spec defaults to 15. 10 risks missing a category; 20 stretches CI runtime past 10 min. Could grow to 20 if Agent C's empirical analysis shows ≤7.5 min runtime headroom remaining. Recommend 15.

3. **If Brown's binary won't build (no compiler), should tests be skipped or fail?** Spec says **skip with informative `pytest.skip`** (Section 5 step 7 + Section 6 soft-fail). The user may want to instead fail loudly in CI if the parity gate is critical. The spec defaults to skip; converting to fail is one config flag change.

4. **Pot/stack units: chips (Brown) vs cents (us)?** Brown's `pot` and `stack` are integer chips with no implied BB scale (`cpp/src/river_game.h:36-38`). Our `HUNLConfig` uses integer cents with `big_blind=100` cents per BB. The wrapper must scale: `brown_pot = our_pot` is fine if we set our `big_blind` to match Brown's implicit BB. Fixture uses `pot=1000, stack=9500, big_blind=100` so 1000 chips = 10 BB pot, 9500 chips = 95 BB stack. Recommend this convention.

5. **Iteration count: 2000 (Brown default) or 5000 (tighter convergence)?** Brown's `--iters` default is 2000 (`cpp/src/main.cpp:31`). 5000 reduces risk 6 (under-convergence on hard spots) at 2.5× CI cost. Recommend 2000 default with per-spot override.

6. **Does PR 7 introduce a new pytest marker, or use an existing one?** Spec proposes `@pytest.mark.parity_noambrown`. Existing markers are checked in the PR open; if there's already a `parity` or `external` marker, prefer reuse.

7. **Should `poker_solver/parity/` be the canonical home for *all* future cross-references** (Slumbot, OpenSpiel)? Recommend yes — set up the package structure to host `slumbot_wrapper.py`, `open_spiel_wrapper.py` in later PRs. Document in the package docstring.

8. **Strategy comparison granularity: action-by-action (default) or distribution-distance (TV / KL)?** Spec defaults to action-by-action `|p - q| < 5e-3`. A distribution-distance metric (`TV(p, q) < 5e-3`) is stricter and combines all actions; it's a single number per infoset. Less actionable on failure (you lose "which action diverged"); prefer action-by-action for diagnostics.

9. **Spot range size: ≥30 combos per side (default) or larger?** Larger ranges (~100 combos) give richer strategy signal but multiply Brown's tree size — and Brown evaluates strengths eagerly at construction (`cpp/src/river_game.cpp:213-251`), so 100×100 = 10K combo pairs × 21 evaluations each on the river = ~200K per spot. Still seconds; not a blocker. Recommend 30–60 combos per side per spot.

10. **Should we cache Brown's output across test runs (e.g., via `pytest-cache`)?** Brown's output for a given (spot, iterations) is deterministic; caching could cut CI time from ~7.5 min to ~30 s on a no-source-change re-run. Recommend deferring to PR 7.5 / a follow-up — adds complexity for marginal benefit.
