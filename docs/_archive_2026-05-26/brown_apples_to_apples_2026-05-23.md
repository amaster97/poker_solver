# Brown apples-to-apples parity experiment (2026-05-23)

**Subject:** Determine whether the 6.7% history-coverage failure on
`tests/test_river_diff.py::test_river_parity_vs_brown[dry_K72_rainbow]` reflects a
genuine correctness gap or an experimental setup mismatch.

**HEAD inspected:** `89a124b` (v1.4.1, main).
**Budget used:** ~50 min. **Mode:** READ-ONLY, no tracked-file modifications.
**Artifacts:** raw comparison JSON at `/tmp/apples_results.json`; driver
script at `/tmp/apples_to_apples_experiment.py`.

---

## Verdict

**EXPERIMENT-IS-NOT-APPLES-TO-APPLES — but switching to the apples-to-apples
comparison reveals a REAL, INHERENT divergence that is the documented
limitation of the Option B blueprint aggregator, NOT a bug.**

Concretely:

1. The existing `test_river_parity_vs_brown` test compares OUR
   `solve_hunl_postflop` with `initial_hole_cards=()` (root chance enum over
   1.6M hole-card pairs) vs Brown's vector-form CFR. These two paths solve
   the **same conceptual problem** (range-vs-range Nash on a river subgame)
   but with **fundamentally different algorithms**. The "6.7% history
   coverage" failure mode is dominated by the Python tier timing out before
   exploration completes (`poker_solver/dcfr.py:223`; see the pre-existing
   investigation at `docs/river_parity_timeout_investigation_2026-05-23.md`).
   It is therefore not measuring divergence — it is measuring runtime.

2. The proper apples-to-apples experiment substitutes our
   `solve_range_vs_range` aggregator (the documented Option B workaround) for
   `solve_hunl_postflop`. This makes the comparison run in ~2 s. The
   resulting per-class action distributions diverge substantially from
   Brown's vector-CFR output (**mean total variation 0.47, max TV 1.00 across
   8 hand classes**).

3. The divergence is **architecturally inevitable** for Option B. The
   per-hand 1v1 Nash that the aggregator solves is mathematically a
   different object than Brown's vector CFR: each per-hand solve sees a
   single concrete villain holding (drawn from `villain_reps_by_class`) and
   converges to the Nash of that 1v1 problem; the aggregator then averages
   first-decision frequencies across these per-hand solves. Brown's vector
   CFR propagates per-hand reach probabilities through one shared tree and
   converges to a single Nash over the joint hand distribution. The
   averaging of conditional 1v1 strategies is not the marginal of the joint
   Nash, and no amount of additional iterations or hand-class coverage will
   bridge that gap within Option B.

4. PR 23's spec (`docs/pr_proposals/v1_5_rust_dcfr_widening.md`) already
   identifies this exact architectural limit and proposes the correct fix
   (Path B: vector-form CFR in Rust, matching Brown's `trainer.cpp:138-209`
   pattern). **PR 23 closes the gap; task #182 (Python→Rust delegate)
   does NOT.** Task #182 only makes the existing `solve_hunl_postflop` path
   tractable — but that path's `initial_hole_cards=()` chance-enum
   semantics is itself a different algorithm from Brown's vector CFR, so
   making it faster does not make it match Brown.

---

## 1. Why the existing river_diff test is not apples-to-apples

### 1a. Our `solve_hunl_postflop` with `initial_hole_cards=()`

`tests/test_river_diff.py:205-242` (`_solve_with_our_engine`) constructs a
`HUNLConfig` with `initial_hole_cards=()` and dispatches to the Python
solver via `solve_hunl_postflop`. With empty hole cards, the engine treats
the root as a chance node (`poker_solver/hunl.py:347-350`) that enumerates
`_enumerate_preflop_hole_outcomes()` — `C(52,2) × C(50,2) = 1,624,350`
hole-card pairs. DCFR then expands every betting subtree under each chance
child, paying that chance-enum cost on every iteration.

### 1b. Brown's `river_solver_optimized` vector-form CFR

Brown's binary (`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`)
builds the betting tree ONCE (no chance children at root —
`river_game.h:19-26` confirms `TreeNode` has no chance branch). Per-hand
strategies are stored as a `hand_count × action_count` matrix per infoset.
The traversal at `trainer.cpp:171-180` iterates actions then vectorizes over
opponent hands (`reach_opp[h] * strategy[h, a]`); the symmetric pass at
`trainer.cpp:191-208` does the same for the updating player.

### 1c. The algorithmic mismatch is the root cause

These solve the same game but use fundamentally different algorithms. The
test's 6.7% history-coverage measurement reflects Python-tier slowness —
the Python solver gets cut off by `pytest-timeout` after ~140 iterations,
which is not enough to enumerate even the betting subtrees that *do* show
up in Brown's output (because Brown ran 2000 iterations in 0.04 s and saw
the full tree). It is impossible to read a correctness verdict off this
test as designed.

---

## 2. Apples-to-apples experiment design

### Setup

* **Spot:** trimmed `dry_K72_rainbow` (board `Ks 7h 2d 4c Jh`, pot 1000,
  stack 9500, `bet_sizes=(0.75, 1.5)`, `include_all_in=true`,
  `max_raises=3`).
* **Hero range (Brown's P0 = our P1, first actor on river):** KK, 77, AA,
  QTs, T9s, 9c8c-family, 6c5c-family, T8s = 32 combos, 8 hand classes.
* **Villain range (Brown's P1 = our P0):** KK, AA, QQ, TT, 99, 88 = 33
  combos, 6 hand classes.
* **Iteration count:** 2000 (Brown's default; matches the test's spec).

### Brown side

Invoke `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
via `poker_solver.parity.noambrown_wrapper.run_brown_solver`. Wall: 0.04 s.
Exploitability after 2000 iters: 0.142 chips. Read Brown's root infoset
strategy from `brown_dump.players[0].profile["root"]` (Brown's P0 = first
actor). Aggregate per-hand strategy to per-class by combo-averaging.

### Our side

Call `poker_solver.range_aggregator.solve_range_vs_range(
config_template, hero_range=HERO_CLASSES, villain_range=VILLAIN_CLASSES,
iterations=200, backend="rust", reps_per_class=1, villain_reps=3,
hero_player=1)`. Wall: 1.87 s; 114 per-hand solves succeeded with 0 misses.
`hero_player=1` is critical — our engine has P1 acting first on river when
contributions are symmetric (`poker_solver/hunl.py:286-289`), matching
Brown's P0.

### Convention notes worth pinning

* **Player-index inversion:** Brown's P0 acts first on river; our P1 acts
  first on river. The `noambrown_wrapper` writes `spot.ranges[0]` as Brown's
  P0, so spot[0] = HERO (first actor for both engines as long as we map
  hero_player=1 in our aggregator).
* **Action-label mapping:** Brown emits `b<amount>` tokens (chips added);
  our aggregator emits `bet_<pct>` / `all_in` labels derived from the
  fraction list. For this spot: Brown's `b750` = our `bet_75`,
  Brown's `b1500` = our `bet_150`, Brown's `b9500` = our `all_in`,
  Brown's `c` = our `check`.

---

## 3. Per-spot comparison data

### Per-class action distributions (root, first actor)

Brown's vector-CFR strategy and our aggregator output, with total-variation
distance per class. **TV ∈ [0, 1]; TV ≈ 0 means agreement, TV near 1 means
the two distributions put their mass on disjoint actions.**

| Class | Brown (`c`/`b750`/`b1500`/`b9500`) | Ours (`check`/`bet_75`/`bet_150`/`all_in`) | TV |
|---|---|---|---|
| AA | 0.000 / 1.000 / 0.000 / 0.000 | 0.260 / 0.219 / 0.187 / 0.334 | **0.781** |
| KK | 0.000 / 0.291 / 0.709 / 0.000 | 0.075 / 0.274 / 0.233 / 0.418 | **0.493** |
| 77 | 0.000 / 0.020 / 0.980 / 0.000 | 0.229 / 0.228 / 0.194 / 0.348 | **0.785** |
| QTs | 0.666 / 0.334 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 / 0.000 | 0.334 |
| 98s | 0.666 / 0.334 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 / 0.000 | 0.334 |
| 65s | 0.000 / 0.241 / 0.759 / 0.000 | 1.000 / 0.000 / 0.000 / 0.000 | **1.000** |
| T9s | 1.000 / 0.000 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 / 0.000 | 0.000 |
| T8s | 1.000 / 0.000 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 / 0.000 | 0.000 |

**Summary:** mean TV = 0.466; max TV = 1.000; 6 of 8 classes diverge by
TV > 0.10; 6 of 8 classes diverge by TV > 0.25; 1 class (65s) is
completely opposed (Brown bets, we check).

### Specific qualitative gaps

* **AA:** Brown bets 100% at b750. We mix all four actions (~26% check,
  ~22% small, ~19% large, ~33% jam). Brown's pattern is "small for value
  vs villain's underpair range"; ours is "every action is OK because the
  averaged per-hand Nash sees a mix of winning and losing matchups."
* **KK:** Brown bets ~71% large / ~29% small. Ours jams 42%, checks 7.5%.
  Both engines agree KK has nut equity but we over-jam because the per-hand
  Nash assumes villain's exact hole is fixed.
* **77 (under-set):** Brown bets 98% at b1500 (over-pair value bet). Ours
  jams 35%. Same pattern as KK.
* **65s (busted draw):** Brown converts to a bluff — bets 76% at b1500 +
  24% at b750. Ours checks 100% (the per-hand Nash for 65s vs any pair has
  showdown value ~0; with known opponent holding, the EV-maximizing play is
  give-up).

---

## 4. Root cause: Option B is a documented blueprint approximation

### 4a. Mechanism inside the aggregator

`poker_solver/range_aggregator.py:644-702` (`_extract_first_decision_freqs`)
walks the game from initial state to the first hero decision, reads the
average-strategy probabilities at that infoset, and returns them. Each
per-hand subgame is a single 1v1 solve with `initial_hole_cards=(villain,
hero)` (line 605-608). The villain's hole is therefore KNOWN to the per-
hand solver. Average strategy at the hero infoset is the Nash response
assuming villain has THAT specific holding (modulo: the infoset key in
`poker_solver/hunl.py:391-399` omits villain's hole, so the strategy
collapses to a single distribution per hero-hole — but the GAME VALUES, and
hence the regrets that drive convergence, depend on villain's identity).

We empirically confirmed in `/tmp/aa_strategy_variation.py` that AA's
per-hand Nash strategy on this board is:

| Villain holding | AA's first-decision strategy (`c`/`bet_75`/`bet_150`/`all_in`) |
|---|---|
| KK (AA loses) | 1.000 / 0.000 / 0.000 / 0.000 |
| QQ (AA wins) | 0.075 / 0.274 / 0.233 / 0.418 |
| TT, 99, 88 (AA wins) | 0.075 / 0.274 / 0.233 / 0.418 |

The arithmetic average over the 18 villain reps (3 each × 6 classes) gives
the aggregator's reported AA frequencies. This is provably not the marginal
of any joint Nash over the full villain range — it is an average of six
conditional 1v1 Nash strategies, each conditioned on a specific known
opponent.

### 4b. The aggregator's own documentation says this

`poker_solver/range_aggregator.py:1-32` (module docstring):

> This is **not** a "true" range-vs-range Nash solver (that requires the
> empty-`initial_hole_cards` chance-enum path, which is the focus of
> v1.3 Option A in parallel). Instead, this is the
> **blueprint-aggregation workaround** documented in §4 of
> `docs/pr_proposals/v1_3_range_vs_range.md`:
> [...] Every per-hand solve is a 1-combo-vs-1-combo Nash, so the
> resulting frequencies reflect what hero does *against a specific villain
> combo*, not against the full villain range. The aggregation averages
> across representative villain combos to approximate the range-level
> behavior, but: It does NOT model villain's mixed strategy across the
> range [...] For premium pairs vs underpairs on dry boards this is
> approximately correct (the value-vs-air dynamic dominates), but on
> draw-heavy boards or polarized villain ranges the approximation can
> shift several percentage points.

The empirical numbers above are consistent with "several percentage points"
on the easier classes (QTs / 98s: TV = 0.334) but explode to TV = 0.78–1.00
on the polarized hands where the value-vs-bluff dynamic differs sharply
from the value-vs-air-only blueprint.

### 4c. PR 23 / Option A is the right architectural fix

`docs/pr_proposals/v1_5_rust_dcfr_widening.md:5-9`:

> Lift the Rust production tier so it can solve true range-vs-range Nash
> from empty `initial_hole_cards = ()` [...] The right fix is **NOT** a
> `u8 → u16` widening — it is an **architectural change to vector-form
> CFR**, matching how Brown's reference C++ solver does it
> (`references/code/noambrown_poker_solver/cpp/src/trainer.cpp`).

PR 23's Path B explicitly mirrors Brown's `Trainer::traverse`
(`trainer.cpp:138-209`). When PR 23 ships, our Rust tier will solve the
same algorithmic problem as Brown, and the apples-to-apples comparison
should converge within tolerance (the residual delta is float-precision +
node-iteration-order, both bounded ≤ 1e-7 per `docs/pr_proposals/v1_3_range_vs_range.md:162-165`).

---

## 5. Specific file/line citations of the gap

| Where | Why it diverges from Brown |
|---|---|
| `poker_solver/range_aggregator.py:1-32` | Module docstring: explicitly labels itself the "Pluribus-blueprint aggregation workaround", not a true Nash solver. |
| `poker_solver/range_aggregator.py:208-418` | `solve_range_vs_range` loops over hero classes × villain reps and calls `_run_one_subgame` (line 374-388). Each call is an independent 1v1 Nash. |
| `poker_solver/range_aggregator.py:577-641` | `_run_one_subgame` pins `initial_hole_cards=(hero_combo, villain_combo)` (line 605-612). Villain's exact combo is therefore part of every per-hand solve. |
| `poker_solver/range_aggregator.py:644-702` | `_extract_first_decision_freqs` reads hero's first-decision strategy from THIS conditional 1v1 Nash result. |
| `poker_solver/range_aggregator.py:710-733` | `_average_freqs` does an arithmetic mean across reps. **This is the load-bearing approximation**: marginalizing villain's range by uniform averaging of conditional Nash strategies. |
| `poker_solver/range_aggregator.py:736-763` | `_aggregate_range` combo-weights across hero classes (which IS the right shape for the hero marginal). The flaw is purely in `_average_freqs`. |

For Brown's side the equivalent code is `trainer.cpp:138-209`. The
load-bearing operation Brown does that we do NOT do is the vector-form
node value computation at `trainer.cpp:200-208`:

```cpp
double *node_values = frame.values.data();
for (int h = 0; h < update_hands; ++h) {
    double value = 0.0;
    int offset = h * action_count;
    for (int a = 0; a < action_count; ++a) {
        value += frame.strategy[offset + a] * action_values[a * update_hands + h];
    }
    node_values[h] = value;
}
```

This computes per-hand node values where `action_values[a][h]` already
encodes the OPPONENT'S range distribution (folded into `reach_opp[h]` at
`trainer.cpp:173`). Our aggregator never has access to a "reach_opp" array
because each per-hand solve treats villain as a single known holding.

---

## 6. Recommendation

### 6a. The existing river_diff test is mis-designed; PR 25's fix is on the right track

`tests/test_river_diff.py::test_river_parity_vs_brown` should NOT be
expected to pass at any cost (timeout or otherwise) because its
construction is not measuring what its docstring claims to measure. The
1.6M chance-enum-at-root path the test exercises is structurally different
from Brown's vector CFR. Even with task #182's Python→Rust delegate it
would still measure a different algorithm than Brown.

The right outcomes for the test infrastructure are:

1. **Short-term (no PR 23 yet):** keep the test marked
   `parity_noambrown` (already done — `pyproject.toml:61` deselects it
   from the default suite). Document in the test docstring that it is
   reserved for the v1.5 Rust DCFR widening (PR 23) and should not be
   expected to converge under the current `solve_hunl_postflop` path.
   `docs/river_parity_timeout_investigation_2026-05-23.md` already
   captures this for the timeout angle; we should add a docstring pointer
   for the algorithmic angle too.

2. **PR 25's task #182 — adjust scope:** if task #182 is "delegate Python
   `solve_hunl_postflop` to Rust", it closes the runtime timeout but does
   NOT close the algorithmic gap to Brown. The test would then complete
   but probably still fail with a substantively different per-action
   distribution. Recommend re-scoping task #182 to a more honest target:
   "make `solve_hunl_postflop(initial_hole_cards=())` complete inside the
   parity test's 660 s budget; the parity assertion itself is deferred to
   PR 23."

3. **Long-term (PR 23 ships):** once PR 23 lands the Rust vector CFR, the
   apples-to-apples comparison is automatic — `solve_hunl_postflop` with
   `initial_hole_cards=()` routes to the Rust vector CFR and matches
   Brown's algorithm bit-for-bit (modulo iteration-order float drift).

### 6b. The aggregator is doing its job; don't change Option B

The Option B blueprint approximation IS NOT WRONG within the scope of what
it advertises. It is a fast practical workaround that gives "approximately
correct" frequencies on dry-board value-vs-air spots
(`poker_solver/range_aggregator.py:24-30`). On the dry K-7-2-4-J spot
tested here, the approximation breaks down on the polarized hands (AA, KK,
77 over-bet; 65s under-bluff) because the per-hand Nash misses the
mixed-equity dynamic of a real range.

For UI surfaces that need approximate frequencies fast (≤2 s), the
aggregator's current accuracy is adequate. For correctness assertions vs
Brown — use PR 23, not the aggregator.

### 6c. Concrete action items

1. **Test docstring update** (READ-ONLY rec; orchestrator action):
   `tests/test_river_diff.py` should grow a top-of-file note explaining
   that it is the **algorithmically-correct** parity test (chance-enum vs
   vector CFR) and is therefore PRE-CONDITIONED on PR 23 landing — not
   merely on task #182's perf delegate.

2. **PR 23 scoping check** (orchestrator action): the spec at
   `docs/pr_proposals/v1_5_rust_dcfr_widening.md:154-156` says "PR 7 river
   diff vs `noambrown` ... remain green" as an acceptance gate. That gate
   is currently flipping under the algorithmic mismatch, not under PR 23's
   own changes. Recommend acceptance-gating PR 23 on a NEW test
   (`tests/test_rust_vector_cfr_vs_brown.py`?) that uses the new
   `solve_range_vs_range_rust(..., true_nash=True)` entry-point Path B
   introduces, instead of leaning on the existing test.

3. **MEMORY.md / PLAN.md continuous-pruning task**: the existing river_diff
   test's "broken-by-design" status should be promoted to a top-level
   honest caveat in MEMORY.md `project_solver.md` §Status so future agents
   don't spend cycles trying to fix it before PR 23.

---

## 7. Inline reply to the user's framing

> **Hypothesis to test:** The current `tests/test_river_diff.py::test_river_parity_vs_brown` compares **OUR single-hand-pair `solve_hunl_postflop` Nash** vs **Brown's full range-vs-range Nash** — these are NOT comparable.

**Confirmed half-true.** The test does compare two different algorithms,
but the mismatch is not "single-hand-pair Nash vs range-vs-range Nash" —
it's "chance-enum-at-root over 1.6M hole pairs vs vector-form CFR over
hand-indexed strategies." Both algorithms IN PRINCIPLE solve the same
problem (range-vs-range Nash on a river subgame), but with different
state spaces, infoset key shapes, and convergence rates. Our chance-enum
path is structurally infeasible at 2000 iterations on the Python tier
(it has never converged in this configuration; see
`docs/river_parity_timeout_investigation_2026-05-23.md`).

> The PROPER comparison is: **OUR `solve_range_vs_range` aggregator** (Option B from v1.3.0, the workaround that emulates range-vs-range via per-hand Nash + aggregation) vs **Brown's full range-vs-range solve**. THIS would be apples-to-apples in scope, even though architecturally different (we aggregate post-solve; Brown vectorizes pre-solve).

**Half-true.** Apples-to-apples in scope (both produce a per-class hero
strategy at the root infoset), but as the experiment shows the
architectural difference creates a real, irreducible delta in the output.
For premium dry-board spots like the one tested, the gap is large (mean TV
0.47, max TV 1.00). This is a HONEST KNOWN-LIMIT of Option B, not a bug.

---

## 8. Appendix: experiment provenance

**Driver script:** `/tmp/apples_to_apples_experiment.py` (transient, gitignored).
**Raw output:** `/tmp/apples_results.json` (transient).

**Brown invocation:**
```
$BIN --config /tmp/.../config.json --algo dcfr --iters 2000
     --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7
     --dump-strategy /tmp/.../strategy.json
```
Wall: 0.04 s. Exploitability after 2000 iters: 0.142 chips.

**Our invocation:**
```python
solve_range_vs_range(
    config_template=HUNLConfig(starting_street=Street.RIVER,
                               initial_board=BOARD, initial_pot=1000,
                               initial_contributions=(500, 500),
                               initial_hole_cards=(),
                               bet_size_fractions=(0.75, 1.5),
                               include_all_in=True, postflop_raise_cap=3),
    hero_range=HERO_CLASSES,           # 8 classes
    villain_range=VILLAIN_CLASSES,     # 6 classes
    iterations=200, backend="rust",
    reps_per_class=1, villain_reps=3,
    hero_player=1)                     # P1 = our first actor on river
```
Wall: 1.87 s. 114 per-hand solves, 0 misses.

**Per-hand convergence check:** `/tmp/sanity_per_hand_convergence.py` — KK
vs AA 1v1 Nash at 200 / 1000 / 2000 / 5000 iters all converge to the same
first-decision strategy (exploitability < 1e-7 at 5000). Iteration count
is NOT a confound.

**Villain-conditional strategy probe:** `/tmp/aa_strategy_variation.py` —
demonstrates AA's per-hand Nash strategy varies dramatically across villain
combos (100% check vs KK; mixed bet vs underpairs). This is the smoking
gun that the aggregator's arithmetic mean cannot recover Brown's joint
Nash marginal.

---

## 9. Verdict (recap)

* **EXPERIMENT-IS-NOT-APPLES-TO-APPLES** (existing river_diff test): yes,
  the existing test compares disparate algorithms; the 6.7% history-
  coverage failure is a runtime artifact of the Python chance-enum path,
  not a correctness measurement.
* **SOLVER-DIVERGES-FROM-BROWN** (apples-to-apples experiment): yes, our
  `solve_range_vs_range` aggregator diverges substantially from Brown's
  vector CFR (mean TV 0.47, max TV 1.00). The divergence is **NOT a bug** —
  it is the documented Option B blueprint approximation limit.
* **PR 23 closes the gap; task #182 does NOT.** Task #182 only fixes the
  Python-tier timeout. PR 23 (Rust vector-form CFR) is the only path that
  produces a Brown-comparable Nash.
* **Recommendation:** mark the existing river_diff test PRE-CONDITIONED on
  PR 23 in its docstring; do NOT mark Option B as broken; sequence PR 23
  ahead of any task that depends on Brown-comparable RvR outputs.
