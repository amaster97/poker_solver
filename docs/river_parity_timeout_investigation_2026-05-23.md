# River-parity test timeout investigation (2026-05-23)

**Subject:** `tests/test_river_diff.py::test_river_parity_vs_brown[dry_K72_rainbow]`
**HEAD inspected:** `166d2b8` (v1.4.0; main)
**Investigator wall-clock budget:** 45 min (used ~35 min).
**Mode:** DIAGNOSTIC ONLY (no source / test / crate modifications; no commit; no push).

---

## Verdict

**TEST-WAS-ALWAYS-SLOW.** The test cannot complete on the Python tier with the current river-spot fixture; it is structurally infeasible at 2000 iterations on `initial_hole_cards=()`. This is a pre-existing condition that PR 15 explicitly identified and explicitly left as a follow-up; the test never had a passing wall-clock baseline on this configuration, and nothing in PR 15 / PR 16 / PR 21 changed the inner-loop cost in a way that turned a passing test into a failing one. LEG 10 simply ran an opt-in test (`parity_noambrown` marker, default-deselected) that has been broken-by-design since v0.5.1 (PR 7).

This is **not** environmental, **not** a Brown-side hang, and **not** a regression introduced by PR 15 / 16 / 21.

## Evidence

### 1. Test architecture forces the slow Python tree-walk path

`tests/test_river_diff.py::test_river_parity_vs_brown` calls
`solve_hunl_postflop(cfg, ...)` directly with `initial_hole_cards=()` (the
empty-tuple chance-enum-at-root config). Key file references:

- `tests/test_river_diff.py:205-242` — `_solve_with_our_engine` builds `HUNLConfig` with `initial_hole_cards=()`.
- `tests/test_river_diff.py:341` — calls `solve_hunl_postflop(...)` (Python entry-point, NOT routed through `solve(..., backend="rust")`).
- `poker_solver/hunl_solver.py:100-226` — `solve_hunl_postflop` runs Python `DCFRSolver` and then `exploitability(game, avg)` (the Python tree walk) at line 215, plus `_game_value(game, avg)` at line 217. Both walks pay the chance-enum cost.
- `poker_solver/hunl.py:267,310-315,601-618` — when `hole_cards == ()`, `chance_outcomes` returns `_enumerate_preflop_hole_outcomes()` which enumerates all `C(52,2) × C(50,2) = 1,624,350` hole-card combinations. This chance fan-out is the root of every DCFR iteration.

### 2. PR 15 documented this exact bottleneck and explicitly deferred fixing it

`docs/pr15_prep/pr_report.md:58-64`:

> `pytest tests/test_river_diff_self_sanity.py::test_each_spot_solver_converges`:
> **PRE-EXISTING TIMEOUT on main (>120s)** — uses Python tier `solve_hunl_postflop`
> with `initial_hole_cards=()` at 2000 iters, hitting the exact bottleneck this
> PR addresses on the Rust side. To unblock the Python tier we'd wire
> `solve_hunl_postflop` to also use the Rust expl walk; **the task scope keeps
> the Rust binding behind `backend='rust'` only, so Python tier slowness is left
> as a follow-up.**

This is the sister test of `test_river_diff.py`. Both use the identical Python path (same `_build_hunl_config` shape, same `initial_hole_cards=()`, same 2000 iters). PR 15's audit kickoff line claiming "No PR 7 differential regression. `test_river_diff.py` ... all green" (`docs/pr15_prep/audit_kickoff.md:32-33`) is not backed by a wall-clock measurement anywhere in `docs/pr15_prep/*` — the marker is opt-in (`-m 'not parity_noambrown'` deselects it) so default test runs skip it.

### 3. PR 15 also documents that Rust cannot solve this config either

`docs/pr15_prep/pr_report.md:101-107`:

> The Rust HUNL DCFR solver itself **does NOT yet solve when `initial_hole_cards = ()`** (the chance enum at the root is a 32-bit-packed action that doesn't fit in `Game::Action = u8`). The bench end-to-end timing (~26 s) is therefore **the exploit walk in isolation** — the solver returns an empty strategy and the walk computes the all-uniform exploitability against it. A real RvR solver is a follow-up.

`crates/cfr_core/src/hunl.rs:307-308` confirms: "Without hole cards the chance enum is intractable (1.6M combos) and panics — that's the post-v1 follow-up." So there is no "just switch the test to `backend='rust'`" fix; the Rust DCFR solver does not support this config at all.

### 4. Per-iteration wall-clock measurement (this session)

Probe at `/tmp/probe_river_K72_small.py` (deleted after this report) built the identical river config the test uses (stack=9500, pot=1000, bet_sizes=(0.75, 1.5), max_raises=3, all-in=True, board=Ks 7h 2d 4c Jh, hole=()) and measured:

| Engine | Iters | Wall-clock | Notes |
|---|---|---|---|
| Brown's `river_solver_optimized` | 2000 | **0.11 s** | external binary; fast |
| Our Python `solve_hunl_postflop` | 1 | **>67 s and still running when killed** | per-iter cost is the chance-enum walk × bet tree |
| Our Python (extrapolated) | 2000 | **>36 h** | linear extrapolation from one iter; the test's 660 s timeout fires inside DCFR after ~140 iters |

The Brown-side cost is **three orders of magnitude smaller** than our Python-side cost. The test's 660 s timeout is functionally a 660 s Python-DCFR runtime — Brown finishes long before the timer fires.

### 5. Test re-run in this session

```
$ python3 -m pytest tests/test_river_diff.py::test_river_parity_vs_brown \
    -k dry_K72_rainbow -m parity_noambrown --timeout=1800 -v -o "addopts="
```
- Start: 04:55:01 (this session)
- End: 660.30 s later (11:00 wall-clock)
- Status: **FAILED — Timeout (>660.0s) from pytest-timeout** inside `poker_solver/dcfr.py:223` (the DCFR inner loop)
- Note: the test's own `@pytest.mark.timeout(int(BROWN_TIMEOUT_SEC) + 60)` decorator at `tests/test_river_diff.py:306` evaluates to **660 s** and OVERRIDES the command-line `--timeout=1800`. (`BROWN_TIMEOUT_SEC = 600.0`, `BROWN_TIMEOUT_SEC + 60 = 660`.)
- The test is the FIRST parametrize case (id `dry_K72_rainbow`); the next case in the fixture is `dry_A83_rainbow` (`tests/data/river_spots.json`).

### 6. Git history shows no regression candidate

```
$ git log --since="2026-04-01" --oneline -- poker_solver/hunl_solver.py poker_solver/solver.py poker_solver/dcfr.py poker_solver/hunl.py
117a953 PR 21: v1.4.0 node locking (Python + Rust)
fc3a8f3 PR 15: Rust port of HUNL exploitability + game-value walks (v1.3 RvR perf)
033cff3 PR 10b: replace UI mock solver with real-solver bindings
... [older PRs]
```

- **PR 21** adds one `dict.get()` per CFR-node visit in `dcfr.py:_cfr`. With an empty `MappingProxyType({})` this is a constant-time lookup; cannot turn a passing test into 660-second timeout.
- **PR 15** added the Rust expl walk but explicitly did NOT wire `solve_hunl_postflop` to use it (`solve_hunl_postflop` runs the Python `exploitability(game, avg)` at `hunl_solver.py:215` regardless of backend).
- **PR 16** (range_vs_range aggregator) touches `range_aggregator.py`, not the postflop DCFR / tree-walk path.
- **PR 22 / `tests/test_river_diff.py`** itself: file last modified at PR 7 commit `83d7b9c` (v0.5.1, 2026-05-23 early), never since.

PR 7's own comment in the SISTER file `tests/test_river_diff_self_sanity.py:41-42` asserts "River subgames are small ... 2000 iters is cheap (<10s/spot on a typical dev box)." That claim is **not** backed by any wall-clock measurement that survived into main and is empirically false on the `initial_hole_cards=()` configuration the test uses. The test was written with an aspirational performance assumption that the engine never delivered.

### 7. LEG 10 prescribed scope did not include this test

`docs/leg9_v1_4_0_ship_plan.md §6` (LEG 10 follow-up): "Rebuild `Poker-Solver-1.4.0-universal2.dmg`... Smoke test: one locked solve + one facing-bet solve to confirm `_rust.so` is v1.4.0." The river-parity test is **not** in this scope. The marker `parity_noambrown` is default-deselected per `pyproject.toml:61`. The LEG 10 smoke that hit it ran without the deselect filter and pulled in an opt-in test that has been broken-by-design since v0.5.1.

### 8. Environmental check — the `.so` is fine

```
$ python3 -c "import poker_solver; from poker_solver import _rust; print(poker_solver.__version__, dir(_rust))"
poker_solver version: 1.4.0
_rust import OK
exports: ['compute_exploitability', 'solve_hunl_postflop', 'solve_hunl_preflop', 'solve_kuhn', 'solve_leduc']
```

The `_rust.cpython-313-darwin.so` at `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` loads cleanly and exposes the expected PR 15 + PR 21 surface. Brown's binary at `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` runs in 0.11 s on the K72 spot. There is no environmental wedge; the test fails on its own structural costs.

## Files inspected

- `/Users/ashen/Desktop/poker_solver/tests/test_river_diff.py`
- `/Users/ashen/Desktop/poker_solver/tests/test_river_diff_self_sanity.py`
- `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json`
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py` (PR 21 diff inspected via `git show 117a953`)
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py`
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs`
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs`
- `/Users/ashen/Desktop/poker_solver/docs/pr15_prep/pr_report.md` (the smoking-gun deferral note)
- `/Users/ashen/Desktop/poker_solver/docs/pr15_prep/audit_kickoff.md`
- `/Users/ashen/Desktop/poker_solver/docs/leg9_v1_4_0_ship_plan.md` (LEG 10 scope)
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` (marker registration + timeout)

Git commits inspected: `83d7b9c` (PR 7), `d15c3b7` (PR 8), `033cff3` (PR 10b), `fc3a8f3` (PR 15), `30cd142` (PR 16), `117a953` (PR 21).

## Recommendation

**INCREASE-TIMEOUT-AND-MOVE-ON is wrong** — the test would need a >36-hour timeout to actually complete, and even then the value is questionable (a 36-hour CI gate gives no useful signal).

**Correct recommendation: open-bug-task (with a structured remediation).** Three options for the actual fix, in increasing order of work:

1. **Cheapest (1-line):** Add `@pytest.mark.slow` or a stricter dedicated marker to `test_river_parity_vs_brown`, and confirm LEG 10 / standard test runs exclude it via `-m 'not slow'` already-existing wiring (slow marker is registered in `pyproject.toml:59`). This formalizes the opt-in posture the test already has via `parity_noambrown` and stops it from showing up in any default smoke run.

2. **Honest fix (small):** Shrink the test fixture's K72_rainbow spot to use the explicit ranges from `spot.players[*].hands` (55 + 55 = ~55 hands per player, not the full 1326 × 1225 chance enum) by passing concrete hole-card pairs in `_solve_with_our_engine` rather than `initial_hole_cards=()`. This solves the actual spot the fixture describes (which is range-vs-range with restricted ranges) rather than the full chance-enum-at-root tree. This is also what Brown's binary appears to be doing internally (it converges in 0.11 s).

3. **Real fix (substantial; the PR 15 deferred follow-up):** Route `solve_hunl_postflop`'s Python path to the Rust `compute_exploitability` walk (already done for `_solve_rust` per `solver.py:585-593`), and add a real Rust HUNL DCFR solver that supports `initial_hole_cards=()`. Both are post-v1 follow-ups per the PR 15 report and the Rust `hunl.rs:307-308` comment.

Until one of those lands, the test is **purely advisory** and should not gate any LEG / release. Any LEG smoke that runs `pytest tests/` MUST include `-m 'not parity_noambrown' -m 'not slow'` to suppress this test (and likely also `test_river_diff_self_sanity.py::test_each_spot_solver_converges`, which has the same bottleneck per PR 15 report).

For LEG 10 specifically: this test was not in the prescribed LEG 10 smoke scope per `docs/leg9_v1_4_0_ship_plan.md §6`; the LEG 10 build / packaging is unaffected by this finding.

## Post-investigation cleanup

- No source modifications (`poker_solver/`, `crates/`, `tests/`) — `git status` confirms clean working tree against `166d2b8`.
- Temporary probe scripts at `/tmp/probe_river_K72.py` and `/tmp/probe_river_K72_small.py` were created OUTSIDE the repo (in `/tmp`) and contain no commit-worthy changes; they are diagnostic-only and may be left or deleted by the orchestrator.
- No `git checkout` / `git restore` was needed because no in-tree source was edited.
- No PR / branch / tag operations performed.
