# PR 12 spec — 3-handed postflop solve (optional / stretch / explicitly approximate)

## 1. Goal

Ship the **first multi-player solve in the codebase**: a 3-handed postflop solver
that takes a public flop (or turn or river), three player ranges, three stack
depths, and produces an **approximate equilibrium** strategy profile for the
postflop subgame. This is the optional v1 deliverable per PLAN.md §2 ("PR 12 —
3-handed postflop stretch (optional; explicitly approximate)") and §1 "Features
beyond v1" line ("3-handed postflop (heavy abstraction; explicitly approximate
equilibrium — CFR has no convergence guarantee for ≥3 players)").

PR 12 is **explicitly framed as approximate, not Nash.** This is the
load-bearing framing decision: every output surface (`SolveResult`, CLI stdout,
UI badges, library metadata) labels 3-handed solutions as "≈ approximate
equilibrium" with a hover/footer explaining that multi-player CFR has no known
convergence proof. We cite Pluribus's own framing here: Brown & Sandholm 2019
(*Science* 365:6456) explicitly disclaim their multiplayer agent as a
"near-Nash blueprint" rather than a Nash equilibrium and validate it
empirically by win-rate, not by exploitability theorem (p. 2: *"in the case of
six-player poker, we take the viewpoint that our goal should not be a specific
game-theoretic solution concept, but rather to create an AI that empirically
consistently defeats human opponents"*).

PR 12 ships if PR 1–11 are stable. It is the **stretch milestone** — the
codebase's first move beyond the two-player zero-sum setting where DCFR carries
real convergence guarantees.

## 2. Non-goals (explicit)

- **No 3-handed preflop solve.** Preflop 3-handed is astronomically larger than
  HUNL preflop (3 active hand ranges, 3 position-conditioned action trees, plus
  the multiplayer factor on every node). Even Pluribus only stored a *blueprint*
  for preflop and switched to real-time search starting in round 1 (p. 4:
  *"Pluribus only plays according to this blueprint strategy in the first
  betting round (of four)"*). PR 12 does not attempt this. Out of v1 entirely.
- **No 4+ player.** Solve time and memory scale superlinearly with player
  count — Pluribus needed a 64-core server, ~12,400 CPU core-hours, and <512 GB
  of RAM for blueprint training (Pluribus paper p. 3) for *six* players. Our
  16 GB MacBook target rules out 4+ player game trees with any reasonable
  abstraction; we lock to **3 players only** in PR 12.
- **No claim of "Nash equilibrium" anywhere.** All user-facing copy uses
  "approximate equilibrium" or "near-equilibrium strategy" or "blueprint" — never
  "Nash" or "GTO". This is enforced in code (string-literal audit; see §11)
  and in tests.
- **No exploitability-as-Nash-distance.** Multi-player exploitability has no
  Lyapunov / Nash interpretation. We compute per-pair best-response gaps (P0 vs
  joint{P1,P2}, P1 vs joint{P0,P2}, P2 vs joint{P0,P1}) as a *diagnostic only*,
  not as a Nash distance metric. Labelled "≈ best-response upper bound" in UI.
- **No real-time depth-limited search** with k-strategy continuations
  (Pluribus's k=4 fold-/call-/raise-biased blueprint variants, paper p. 4).
  That's a research direction; PR 12 produces only the blueprint-style offline
  solve. Real-time search is a v2 / PR 13+ candidate.
- **No tournament / ICM-aware solving.** 3-handed is a natural ICM setting (SNG
  bubbles) but adding ICM payouts is its own spec. PR 12 is **cash-equity** only.
- **No new card abstraction.** Reuses PR 4's `AbstractionTables` with tighter
  bucket counts (see §5). No re-bucketing pipeline changes; we just pass tighter
  counts to `precompute-abstraction`.
- **No new DCFR variants.** Stays on Linear CFR (the multi-player-friendly
  special case per Pluribus paper p. 3: *"Pluribus uses a recent form of CFR
  called Linear CFR (38) in early iterations"*), then stops discounting after a
  cutoff. Defaults: LCFR for iterations 1..t_cutoff, then vanilla CFR thereafter.
  We **do not** use DCFR_{1.5, 0, 2} for 3-handed (the (β=0) behavior of
  truncating negative regret is a 2p0s heuristic; for n-player the conservative
  choice is LCFR which Pluribus validated).
- **No rake.** Same lock as PR 3/5/9: `rake_rate == 0.0`, `rake_cap == 0`.
- **No UI for 3-handed range input.** Bare minimum: three text-based range
  strings via the CLI. The PR 10 UI gets a *display* update (three side-by-side
  range matrices + the approximate badge — see §6) but not a per-player
  interactive range editor for 3-handed in v1. Editing rich 3-handed input is
  PR 12.5 if the user wants it.
- **No node locking** (Phase-4 feature, see PR 10 §1 non-goals).
- **No "claim Pio parity" sanity check.** PioSolver is HU-only. There is no
  PioSolver baseline to validate against (see §7).

## 3. Theoretical honesty (the central section)

This section is the spec's reason for existing. Everything below references it.

### 3.1 What CFR proves and doesn't prove

For 2-player zero-sum games, CFR (Zinkevich et al. 2007, indexed at
`references/papers/_INDEX.md` under `zinkevich_2008_cfr_nips.pdf`) proves
**average regret R_T → 0 as T → ∞**, and by the standard regret-Nash
connection (Theorem 2 in Zinkevich 2007) the average strategy converges to a
Nash equilibrium at rate O(T^{-1/2}). DCFR (Brown & Sandholm 2019,
`dcfr_brown_2019.pdf`) tightens the constant factor but retains the same
asymptotic guarantee.

**For ≥3 player games, this is not true.** Multiple failure modes:

1. **No polynomial-time algorithm to find a Nash equilibrium exists** in n-player
   games (Daskalakis-Goldberg-Papadimitriou 2009 / Chen-Deng-Teng 2009; cited
   directly in Pluribus paper p. 2 refs 13–14: *"finding a Nash equilibrium in
   zero-sum games with three or more players is at least as hard..."*).
2. **Joint independent Nash play is not itself a Nash equilibrium.** If each
   player independently computes a Nash and plays one of its strategies, the
   joint strategy profile is generally NOT a Nash equilibrium of the joint game.
   The Pluribus paper illustrates with the Lemonade Stand Game (p. 2): a Nash
   requires uniform spacing around a ring, but there are infinitely many ways
   to instantiate uniform spacing; players independently picking one won't
   line up.
3. **Nash equilibria are not unique** in n-player ≥3, and **playing a Nash
   strategy is not even guaranteed to not-lose-in-expectation** — that property
   is unique to 2p0s (Pluribus paper p. 1: *"Two-player zero-sum games are a
   special class of games in which Nash equilibria also have an extremely useful
   additional property"*).
4. **CFR may cycle, depend on initialization, or fail to converge** in n-player
   games. Gibson 2013 (`gibson_2013_regret_minimization.pdf`) provides the
   strongest known theoretical result: regret minimization in extensive-form
   games eliminates **iteratively strictly dominated actions** even in n-player
   non-zero-sum settings, but this is *much weaker* than Nash convergence.
   Counterfactual regret still grows sublinearly in T in all finite games
   (Pluribus paper p. 3: *"CFR guarantees in all finite games that all
   counterfactual regrets grow sublinearly in the number of iterations"*), but
   sublinear total regret does not imply Nash convergence outside 2p0s.

### 3.2 What we do anyway

We use Linear CFR (LCFR = DCFR_{1, 1, 1}) on a heavily-abstracted 3-handed
postflop tree. This follows Pluribus exactly (p. 3): *"Pluribus uses a recent
form of CFR called Linear CFR (38) in early iterations. (We stop the
discounting after that because the time cost of doing the multiplications with
the discount factor is not worth the benefit later on.)"* — i.e., LCFR for
iterations 1..t_cutoff, then plain CFR averaging thereafter. Default
`t_cutoff = T/2` per Pluribus's reported recipe.

We also adopt Pluribus's other practical levers (paper p. 3):

- **Negative-regret pruning in 95% of iterations** — actions with very negative
  regret are skipped 95% of the time, speeding up convergence by ~3× without
  affecting the limit point in practice.
- **Information abstraction during offline blueprint computation.** The whole
  point — see §5.
- **Action abstraction with few discrete sizes per node** — same as PR 3's
  fixed-fraction menu, but tighter (see §5).

### 3.3 What we report

We report three things and label each one carefully:

- **Game value per player** under the converged blueprint. Three numbers (one
  per player) in mBB/hand. **Sum to ~0** by construction (zero-sum game) but
  individual values are interpretable only as "what this strategy earns against
  the *other two players' converged strategies*" — not as an unbeatable value.
- **Per-pair best-response gap** as the diagnostic. For each player p, compute
  `BR_p = max_π v_p(π, σ_{-p}) - v_p(σ_p, σ_{-p})` where `σ_{-p}` is the joint
  converged strategy of the other two. Three numbers. Label: "≈ best-response
  EV upper bound (multi-player; NOT Nash exploitability)". Rendered with an
  approximate badge (see §6).
- **Convergence stability:** rerun the solve from 3 different random seeds and
  report the L1 distance between resulting strategies (or per-infoset
  distribution diffs). Cited as "stability metric"; large drift between seeds
  → user is shown a warning that multi-player CFR has no convergence guarantee
  (per §3.1 #4) and the reported strategy is one particular fixed point among
  potentially many.

### 3.4 What we never claim

- Never "Nash equilibrium" or "GTO" or "optimal" in any output string. Only
  "approximate equilibrium" or "blueprint" or "approximate solution".
- Never "exploitability" without the modifier "best-response upper bound,
  per-pair, multi-player" or similar. The single word "exploitability" is a
  reserved technical term for the 2p0s metric and we don't reuse it for
  3-handed.
- Never compare 3-handed results to HU results as if they were the same kind of
  artifact. They are different solution concepts with different guarantees.

## 4. Game state changes (3-handed)

PR 3 locked `HUNLState` to two players (`tuple[bool, bool]` for `folded`, fixed
`contributions: tuple[int, int]`, etc.). PR 12 **generalizes** to N players,
with v1 tested only at N=2 (existing HUNL path) and N=3 (new 3-handed path).

### 4.1 Generalized state shape

| Field | Old (N=2) | New (N-player) |
|---|---|---|
| `contributions` | `tuple[int, int]` | `tuple[int, ...]` (length = `num_players`) |
| `stacks` | `tuple[int, int]` | `tuple[int, ...]` |
| `folded` | `tuple[bool, bool]` | `tuple[bool, ...]` |
| `all_in` | `tuple[bool, bool]` | `tuple[bool, ...]` |
| `hole_cards` | `tuple[(C,C), (C,C)] \| ()` | `tuple[tuple[Card, Card], ...] \| ()` |
| `cur_player` | `int` (0, 1, -1) | `int` (0..N-1, or -1) |
| `street_aggressor` | `int` | `int` |
| `street_num_raises` | `int` | `int` |
| `to_call` | `int` | `int` — relative to `cur_player`'s contribution vs. aggressor's |

The generalization is mechanical for the small surface that touches
player-index logic; **but several semantic items are not mechanical** (see
§9 critical correctness):

- **Position semantics for 3-handed** (locked, see Pluribus paper p. 5 on
  "limping" being suboptimal except for SB): **P0 = SB (acts first preflop,
  acts first postflop after BB), P1 = BB, P2 = BTN.** In 3-handed (3-max),
  there are exactly three positions. Pre-flop action order is SB → BB → BTN →
  back to SB if needed. **Post-flop** action order is SB → BB → BTN (SB is
  out-of-position; BTN is in-position). PR 12 postflop-only, so we only need
  the post-flop order. This matches the standard 3-max convention.
- **Action turn advancement**: instead of "switch to the other player", we
  advance to the **next non-folded, non-all-in player** in the post-SB rotation.
  If only one player remains non-folded and non-all-in, the betting round ends
  (matched contributions or single live player → street advance).
- **Street ends when**: all live (non-folded) players have either matched the
  current `street_aggressor`'s contribution, or are all-in for less and cannot
  call more, AND every live player has had an opportunity to act since the last
  raise. Standard NLHE rule, generalized from HU.
- **Showdown happens when**: river betting completes AND ≥2 live players
  remain (i.e., not everyone-but-one folded). Pot is awarded per side-pot
  hand-ranking (see §9 #1).

### 4.2 Generalized `HUNLConfig` (renamed in spirit but kept name for code stability)

We do NOT rename `HUNLPoker` / `HUNLConfig`. PR 5/9/10/11 all import these and
renaming cascades downstream. Instead, we extend `HUNLConfig` with:

| Field | Default | Purpose |
|---|---|---|
| `num_players` | `2` | Total players at the table. v1 tests N=2 (default) and N=3. |
| `starting_stacks` | `(10_000, 10_000)` (HUNL legacy) | Length = `num_players`; per-player starting stacks in cents. Asymmetric stacks allowed. For 3-handed default: `(10_000, 10_000, 10_000)` (100 BB each). |
| `initial_contributions` | `(0, 0)` | Length = `num_players`. For 3-handed subgame starts (postflop), pre-subgame contributions per player. |

The class is renamed internally to `PokerConfig` *for clarity in code comments
only* — the import path stays `HUNLConfig` to avoid breaking PR 5/9/10/11.
Comment at top of `hunl.py` documents the misnomer.

The `HUNLPoker(Game)` class becomes `PokerGame(Game)` semantically but keeps the
old name. A docstring note explains. New attribute `self.num_players` is used
throughout `apply()`, `current_player()`, `is_terminal()`, etc.

### 4.3 What PR 12 does not generalize

- **Preflop blinds posting logic** assumes 2-player or 3-player. We don't
  parametrize blind-posting across arbitrary N; we ship `_post_blinds_2p()` and
  `_post_blinds_3p()` and route by `num_players`. 4+ player is `NotImplementedError`.
- **Action turn order** is implemented for N=2 and N=3 specifically. A generic
  N-player rotation is not built; we don't pretend to support N=4 by accident.

## 5. Memory + abstraction

### 5.1 Why tighter buckets

PR 4's card abstraction defaults to **256 flop / 128 turn / 64 river** for HU.
At 3-handed, the joint state space is *not* simply 3× the size — it's larger
because each player's range conditions on **two** opponents' ranges (joint
opponent reach), and the action tree branches at each player's decision.

Empirically (per Pluribus paper §Hardware footprint, p. 3): Pluribus's blueprint
ran in <512 GB of RAM at 6-player. Scaling down to 3-handed on 16 GB requires
**substantially tighter** abstraction.

**Default for 3-handed (v1):** **128 / 64 / 32** (one tier tighter than HU
default). This matches PLAN.md's existing "150–200 BB" row (which also goes
one tier tighter). Empirical revisit per §5.3.

### 5.2 Concrete bucket-count alternatives

| Tier | Flop / Turn / River | Estimated memory | Notes |
|---|---|---|---|
| **Default 3p** | 128 / 64 / 32 | ~6–10 GB | Recommended starting point. |
| Tight 3p | 64 / 32 / 16 | ~3–5 GB | If default OOMs. |
| Ultra-tight 3p | 32 / 16 / 8 | ~1–2 GB | Smoke-test / dev iteration. |

These are estimates only. **The empirical revisit pattern from PR 5 is the
gate:** PR 12 reuses the `MemoryProbe` from `poker_solver/profiler/memory.py`
unmodified. The profiler reports per-street memory; the user (or the autonomous
log) tightens until the solve fits.

### 5.3 PR 4 reuse

PR 12 does NOT write new abstraction-builder code. It calls the existing
`precompute-abstraction --bucket-counts 128,64,32` from PR 4 with new numbers
and consumes the resulting `.npz` artifact via `lookup_bucket()` exactly as
PR 5/6 do.

A new artifact `abstractions/3p_default_128_64_32.npz` ships as a *recipe*
(documented build command), not as a committed binary file (license / repo
size discipline; same as PR 4's pattern).

## 6. Files to create/modify

### 6.1 Files to create

- **`poker_solver/multiway_solver.py`** (~500 LOC) — 3p-specific orchestration.
  Mirrors `hunl_solver.py` (PR 5) in structure but routes through a multi-player
  CFR loop instead of the 2p one. Exports:
  - `solve_3p_postflop(config, abstraction, iterations, ...) -> MultiwaySolveResult`
  - `MultiwaySolveResult` dataclass (extends/wraps `SolveResult` with `num_players`,
    per-player `game_value: tuple[float, ...]`, per-player `br_gap: tuple[float, ...]`,
    `convergence_stability: float | None`).
  - `MultiwayBestResponse` computation utility (per-pair BR; see §7.3).
  - Stability diagnostic: `run_stability_diagnostic(config, abstraction, seeds=(0,1,2)) -> StabilityReport`.

- **`crates/cfr_core/src/multiway.rs`** (~600 LOC) — Rust port mirroring PR 6's
  approach. Mechanical translation of the Python multi-player CFR loop, with
  LCFR + 95%-pruning. Gated by differential test against the Python tier on a
  tiny 3p river subgame (~few thousand infosets, ~tens of seconds to solve in
  Python). Same pattern as PR 6 vs PR 5.

- **`tests/test_3p_core.py`** (~15 tests) — game-state invariants for N=3:
  side-pot calculation, action turn advancement, 3-way showdown evaluation,
  fold-then-2-handed-continuation correctness.

- **`tests/test_3p_solve.py`** (~10 tests) — convergence smoke tests, stability
  diagnostic, per-pair BR gap structure. Marked `@pytest.mark.slow` for the
  multi-minute solves; CI runs only the smoke variants.

- **`tests/test_3p_diff.py`** (~3 tests) — Python ↔ Rust differential test on
  a tiny 3p river subgame, mirroring `tests/test_dcfr_diff.py` from PR 6.

- **`tests/fixtures/multiway_fixtures.py`** — fixture builders for the standard
  3p test spots: 3p river-only subgame (deterministic, no chance nodes, ~1k
  infosets), 3p flop subgame with tight abstraction (~10^5 infosets), 3p turn
  subgame (~few × 10^4 infosets).

### 6.2 Files to modify

- **`poker_solver/hunl.py`** — generalize to N-player per §4. Largest single
  file change in PR 12 (~200 LOC delta). All existing PR 3 tests must still
  pass; the generalization is *strictly additive* on the API.
- **`poker_solver/action_abstraction.py`** — generalize `ActionContext` to
  carry `num_players` and pass through to raise-cap / aggressor-tracking logic.
  Bet/raise math is the same (pot fractions); only the *who acts next*
  calculation changes.
- **`poker_solver/solver.py`** — add a routing branch: if
  `config.num_players == 3 and config.starting_street >= Street.FLOP`, route to
  `multiway_solver.solve_3p_postflop`. HU path unchanged. 4+ player → clear
  `NotImplementedError`.
- **`poker_solver/cli.py`** — add `--num-players` flag (default 2). When 3,
  `--ranges` must accept three comma-separated range strings (e.g. `"AA,KK / AKs+ / 76s+"`)
  instead of two. Documented in `--help`.
- **`poker_solver/__init__.py`** — re-export `solve_3p_postflop`,
  `MultiwaySolveResult`, `StabilityReport`.
- **`ui/views/range_matrix.py`** (PR 10's centerpiece) — add an "approximate
  equilibrium" badge per §6.3 that renders only for `num_players >= 3` results.
  Three side-by-side mini-matrices instead of one when displaying a 3p result.
- **`ui/views/run_panel.py`** — add a `num_players` toggle (2 / 3). When 3, add
  a third range input panel. Display the stability diagnostic in the result
  panel. Display per-pair BR gaps instead of single-number exploitability.
- **`poker_solver/library.py`** (from PR 11) — `SpotDescription` already
  serializes `num_players` (because it serializes the whole `HUNLConfig`). The
  library viewer in `ui/views/library_browser.py` should display a small
  "3-handed (approximate)" badge on rows where `spot_json` parses to
  `num_players == 3`.

### 6.3 UI badge ("≈ approximate" — load-bearing)

Every UI surface that displays a 3-handed result MUST render the following
badge (locked spec):

```
┌──────────────────────────────┐
│ ≈ approximate equilibrium     │   <— red/yellow Quasar `q-badge` color="warning"
│ multi-player; not Nash        │       (tooltip on hover)
└──────────────────────────────┘
```

Tooltip text (locked):

> "Three-handed solves use Linear CFR on a heavily-abstracted tree. Multi-player
> CFR has no Nash convergence proof (Brown & Sandholm 2019, Pluribus); the
> strategy shown is one approximate fixed point among potentially many.
> Best-response gaps below are per-pair upper bounds, not Nash exploitability."

Placement: top of the range matrix display panel for 3-handed solves; top of
the library row entry; top of the CLI stdout result block (rendered as a 3-line
text banner with `===` borders).

## 7. Validation strategy

Multi-player solve has no closed-form ground truth. Validation must be
empirical and structural.

### 7.1 What we can't do

- **Compare to Nash.** No closed-form Nash exists for 3-handed NLHE postflop.
- **Compare to PioSolver.** Pio is HU-only.
- **Compare to GTO Wizard.** GTOW does multiway preflop in a cloud library,
  but their *postflop* coverage is HU-only as of Feb 2026 (per
  `references/blog/gtow_multiway_preflop_launch.md`). Even if it covered
  postflop, the library is gated behind a paid cloud account — out of scope per
  PLAN.md "no cloud spend".

### 7.2 What we can do — structural sanity

For each fixture solve:

1. **Game value zero-sum check.** `sum(per_player_game_value) ≈ 0.0` (within
   float tolerance × pot). Holds by construction; tests verify.
2. **Strategy validity per infoset.** For every infoset key in the strategy,
   `sum(probs) ≈ 1.0`, all `probs ∈ [0, 1]`, no NaN/Inf.
3. **Iteratively-strict-dominated actions vanish.** Per Gibson 2013 main result
   (`gibson_2013_regret_minimization.pdf`): CFR eliminates iteratively strictly
   dominated actions even in n-player non-zero-sum games. Construct a 3p toy
   subgame where one action is strictly dominated for one player; solve;
   assert that action's frequency converges to 0 (within ε).
4. **Per-pair BR gaps decrease across iterations.** Not monotone, but the moving
   average of the three BR gaps should trend down. This is a soft assertion —
   per §3.1 #4, multi-player CFR may not converge cleanly. Failure prompts user
   review, not auto-fail. (Same pattern as PR 3/5's loose bounds + intuition
   gauntlet.)

### 7.3 Per-pair best-response math

For each player p ∈ {0, 1, 2}:

```
σ_{-p} = product of the other two players' converged strategies
v_p^{best}  = max over alternative pure-or-mixed σ'_p of v_p(σ'_p, σ_{-p})
v_p^{σ}     = v_p(σ_p, σ_{-p})
BR_gap_p    = v_p^{best} - v_p^{σ}    (always ≥ 0)
```

`v_p^{best}` is computed by walking the tree with the BR recursion (standard
two-step: each player p computes their best response *given* the other two are
fixed). Each BR walk is O(tree size); three BR walks per snapshot.

**Important:** BR_gap_p is NOT a Nash exploitability. In 2p0s, sum of BR gaps
across both players IS Nash exploitability up to a factor of 2; the same does
not hold for n>2. We do not sum them, do not report a single number, and do
not call any of these "exploitability".

### 7.4 Convergence stability diagnostic

Run the same solve from 3 different random seeds (`seed=0, 1, 2`):

```python
stability = StabilityReport(
    seeds=(0, 1, 2),
    strategies=[σ_0, σ_1, σ_2],
    l1_per_infoset=l1_distance_between_strategy_pairs(σ_0, σ_1, σ_2),
    pairwise_max=max(l1_per_infoset.values()),
    pairwise_mean=mean(l1_per_infoset.values()),
)
```

Assertion: `pairwise_max < 0.05` (5% in L1 per infoset) on the river-only
fixture. **This is a soft assertion** — if it fails, the user is warned that
the 3 seeds produced visibly different strategies (per §3.1 #4: CFR may have
multiple fixed points in n-player games). The strategy is still served to the
user, but the badge in §6.3 gains an extra line: "⚠ stability degraded: seeds
0/1/2 differ in L1 norm by up to X% per infoset."

### 7.5 Cross-validate against MonkerSolver (optional, user-supplied data)

**MonkerSolver** is a paid Windows desktop solver that supports multiway. If
the user has access (per the open decision in §12), they can supply MonkerSolver
output JSON / CSV for a small set of 3-handed flop spots, and the test harness
in `tests/test_3p_solve.py::test_against_monker_data` reads the user-supplied
file and asserts per-infoset L1 < 0.10 between our strategy and MonkerSolver's.

This is **opt-in**: the test is decorated `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`
and is skipped when the user has no Monker data. The fixture format is
documented; user populates the directory manually. No bundled data (license).

### 7.6 Intuition gauntlet (3-handed-specific)

Specific spots where 3-handed strategy should match well-known poker intuition:

- **3-way UTG opens, BTN 3-bets, SB folds.** After solve, BB's defending range
  on the 3-bet vs UTG should be *narrower* than the HU-3-bet-defense range
  (because of the squeeze pressure from a remaining cold-caller dynamic). Soft
  assertion: top-10% of BB's range continues at a *lower* frequency than the
  same spot in HU.
- **Multi-way wet-flop check-down freq.** On a 3-handed flop where one player
  has missed equity (e.g. SB with AK-high on 876ss board), the SB's check
  frequency should be *higher* than HU because of multi-way coverage need.
- **In-position bluff frequencies decrease multi-way.** Standard poker rule.

Tests are documented as "soft assertions"; failure prompts user review, not
automatic block.

## 8. Three-agent fan-out

Same parallelism pattern as PR 3/4/5/10/11. Tight per-agent ownership; specs
are the interface lock.

### 8.1 Agent A — Generalize HUNL to N-player

**Owns:**
- `poker_solver/hunl.py` (the §4 generalization; ~200 LOC delta)
- `poker_solver/action_abstraction.py` (`ActionContext.num_players` plumbing)
- `tests/test_3p_core.py` (game-state invariant tests)

**Does NOT touch:**
- `multiway_solver.py`, `crates/`, any UI file, any test except its owned files.

**Deliverables:**
- `HUNLState` with N-player tuple fields per §4.1.
- `HUNLConfig.num_players: int = 2` field; default unchanged.
- `_post_blinds_2p()` and `_post_blinds_3p()` helpers; `apply()` routes by N.
- Action turn rotation logic for N=3, with the standard 3-max position
  convention (SB / BB / BTN).
- All PR 3 tests pass unchanged (regression gate). N=2 path is identical to
  the existing code in observable behavior.
- New tests in `test_3p_core.py` per §6.1.

**Interface lock:** the `HUNLState` field names and the
`HUNLPoker.apply/legal_actions/utility/current_player/chance_outcomes`
signatures are stable. Agent B/C consume these unchanged.

### 8.2 Agent B — 3p orchestration + Rust port

**Owns:**
- `poker_solver/multiway_solver.py`
- `crates/cfr_core/src/multiway.rs`
- `poker_solver/solver.py` (the routing branch)
- `poker_solver/__init__.py` (re-exports)

**Does NOT touch:**
- `hunl.py` (Agent A's), tests (Agent C's), UI files (deferred to Agent C-bis).

**Deliverables:**
- `solve_3p_postflop(...)` with the signature in §6.1.
- `MultiwaySolveResult` dataclass.
- Linear CFR + 95%-pruning + LCFR-to-CFR cutoff logic per §3.2.
- Per-pair BR computation via `MultiwayBestResponse`.
- Stability diagnostic via `run_stability_diagnostic`.
- Rust port that passes the differential test on a tiny 3p river subgame.
- `mypy --strict` clean on the Python file; `cargo clippy --all-targets -- -D warnings` clean.

**Interface lock:** Agent B imports `HUNLState`, `HUNLConfig`,
`HUNLPoker` from `poker_solver.hunl` unchanged. Imports the abstraction layer
from PR 4 unchanged. Imports `MemoryProbe` from PR 5 unchanged.

### 8.3 Agent C — tests + cross-validation harness + UI integration

**Owns:**
- `tests/test_3p_solve.py`
- `tests/test_3p_diff.py`
- `tests/fixtures/multiway_fixtures.py`
- `ui/views/range_matrix.py` (the badge + 3-up matrix display)
- `ui/views/run_panel.py` (the `num_players` toggle + 3-range input)
- `ui/views/library_browser.py` (the row badge for 3p spots)

**Does NOT touch:**
- `hunl.py`, `multiway_solver.py`, `solver.py`, Rust code.

**Deliverables:**
- Convergence smoke tests (PR-12-specific) per §6.1.
- Per-pair BR gap tests per §7.3.
- Stability diagnostic test per §7.4.
- MonkerSolver cross-validation harness per §7.5 (file format + opt-in fixture).
- Intuition gauntlet tests per §7.6.
- UI: approximate-equilibrium badge per §6.3; tooltip; 3-up range matrix
  display when `result.num_players == 3`.

**Edge-case allowance:** same as PR 3/5 — tests that are correct-per-spec but
reveal genuine ambiguities are escalated to the user; the spec is the source of
truth.

## 9. Critical correctness items

1. **Side-pot calculation with multiple all-ins at different stack sizes.** The
   single hardest correctness item in 3-handed. Example: P0 has 50 BB, P1 has
   100 BB, P2 has 150 BB; everyone goes all-in. There are two side pots: the
   first contested by all three players up to 50 BB each (main pot = 150 BB),
   the second between P1 and P2 only for the next 50 BB each (side pot = 100 BB);
   P2 has 50 BB returned uncalled. The pot-distribution rule is: each side pot
   is won by the live player with the best hand *who contributed to that pot*.
   This is a known correctness pitfall (PioSolver, postflop-solver, and
   Slumbot all have public bug reports on side-pot edge cases). Mitigated by:
   (a) explicit `_compute_side_pots(contributions, folded) -> list[SidePot]`
   helper with a 6-test unit-test fixture covering known-tricky cases; (b)
   triple-checked against the standard reference (TDA / WSOP rule set, summarized
   in our codebase comment). Tests:
   - 3-way all-in at equal stacks → one main pot, no side pots.
   - 3-way all-in at unequal stacks → one main + one side pot.
   - 3-way: two all-in at different stacks, one folded → main pot only (folded
     player's chips go to the main pot).
   - Tie at showdown across a side pot → pot split among tied contributors.
   - Floor/ceiling correctness on odd-chip splits (3-way tie on a pot of 100
     cents — first chip(s) by position).

2. **3-way showdown evaluation.** When ≥2 live players remain at river end, each
   player's hand is evaluated against the 5-card board. Best hand wins each
   side pot they contributed to. Implementation reuses `poker_solver.evaluator`
   per-player; the only new logic is the **multi-winner per side pot** path. Test:
   3-way showdown where each player wins a different side pot (different stack
   sizes, different hand ranks).

3. **Per-player BR considers all opponents' joint strategy.** When computing
   `BR_gap_0`, the search must walk against the *joint* distribution of P1 and
   P2's strategies, not against either individually. Implementation: at each
   opponent decision node, the recursion weights by `σ_p(I, a)` for whichever
   `p` is to act. Test: synthetic 3p tree where the BR-against-joint is
   different from BR-against-either-individually-treated-as-fixed; assert the
   BR walk picks the correct (joint-aware) value.

4. **"Exploitability" framed correctly per pair.** Strings in code, in CLI
   stdout, in UI, in `SolveResult.__repr__`, in JSON serialization. A
   string-literal audit step in `scripts/check_pr.sh` for PR 12: `grep -ri
   'exploitability\|nash\|GTO' poker_solver/multiway_solver.py
   ui/views/library_browser.py | grep -v 'best-response\|approximate\|≈\|near-Nash'`
   should report only commented references to historical papers. Any
   unaccompanied bare "exploitability" in 3-handed-relevant code path → fail.

5. **`num_players == 3` consistently checked.** Routing in `solver.py` is the
   single dispatch point. The HU path (`num_players == 2`) is unchanged; the 3p
   path is new; `num_players >= 4` raises `NotImplementedError("PR 12 supports
   N=2 and N=3 only; 4+ players require a separate solve infrastructure.")`.

6. **All PR 3/4/5/6/7/8/9/10/11 tests still pass.** Hard regression gate. The
   N-player generalization in Agent A's `hunl.py` is strictly additive on the
   N=2 path. Tested by running the full pytest suite as part of `check_pr.sh`.

7. **Linear CFR cutoff is configurable but defaults correctly.** Per Pluribus
   p. 3: LCFR for early iterations, then plain CFR averaging. Default cutoff
   `t_cutoff = T // 2`. Exposed as `dcfr_kwargs={'lcfr_cutoff': T//2}` in
   `solve_3p_postflop`. Test: solve with `lcfr_cutoff=0` (pure plain CFR) and
   `lcfr_cutoff=T` (pure LCFR) and the default; observe convergence behavior.

8. **Negative-regret pruning in 95% of iterations.** Per Pluribus p. 3:
   *"actions with extremely negative regret are not explored in 95% of
   iterations"*. Implementation: at each player decision node, sample whether
   to skip pruned actions with probability 0.95 (random.random()); pruning
   threshold C is a hyperparameter (default `-300_000` per Libratus supplement
   §ES-MCCFR regret-pruning, since their threshold convention matches). Tested
   indirectly via per-iteration wallclock: pruning should give ~3× speedup
   per Pluribus's empirical claim.

9. **Multi-way "limping" not specially encoded.** Pluribus paper p. 5
   discusses that limping is suboptimal except for SB. We do NOT bake this
   into the prior; the action menu is unconditioned and CFR discovers what it
   discovers. (We note this in commentary but don't constrain the action
   space.)

10. **Approximate-equilibrium badge cannot be disabled.** No CLI / config flag
    to suppress the "≈ approximate" badge in CLI output or UI display. This is
    a load-bearing user-experience commitment (per §1 goal).

## 10. Risks

### 10.1 Convergence may not happen; strategies may cycle

Per §3.1, multi-player CFR has no Nash convergence proof. The solver may:
- Reach a fixed point that isn't a Nash. (Most likely; this is the "near-Nash
  blueprint" Pluribus describes.)
- Cycle between strategies without converging. (Possible; CFR's regret
  guarantees still hold but the average strategy may oscillate.)
- Depend on random initialization. (Per §3.1 #4; stability diagnostic in §7.4
  detects this.)

**Mitigation:**
- Stability diagnostic in §7.4 quantifies the magnitude.
- UI badge in §6.3 communicates the framing.
- Documentation does not promise convergence.
- LCFR-to-CFR cutoff per Pluribus's recipe is the empirically-validated mitigation.

### 10.2 Memory at default 128/64/32 abstraction may not fit 16 GB

Per §5.2, default 3p memory estimate is 6–10 GB. **Estimate**, not promise.
The Python tier in particular may overshoot because Python dict overhead grows
with infoset count. PR 5's `MemoryProbe` calibration check at 10% tolerance
may not extend cleanly to 3p (joint reach probabilities introduce dimensions
not exercised in HU profiling).

**Mitigation:**
- Reuse PR 5's `MemoryProbe` and let it abort cleanly on OOM (per PR 5 §7.7).
- Three abstraction tiers in §5.2 give the user fallback options.
- Default `max_memory_gb=14.0` (same as PR 5) — if exceeded, the partial
  MemoryReport tells the user what's bloated.
- Tighten-on-OOM is documented in the abort message.

### 10.3 Side-pot math is a known correctness pitfall

Pio caught side-pot bugs for years; postflop-solver's `bunching.rs` is partly
about side-pot edge cases. Our test fixtures in §9 #1 are designed against the
known-tricky cases, but additional bugs may exist.

**Mitigation:**
- 6+ unit tests on `_compute_side_pots` against hand-rolled fixtures matching
  TDA rule examples.
- Audit agent for PR 12 gets "side-pot correctness" as an explicit focus area.
- The user is warned in PR 12's report that side-pot math is the most likely
  bug class.

### 10.4 No external reference to validate against without MonkerSolver license

Per §7, the only external 3p solver we could cross-validate against is
MonkerSolver, which is paid commercial software the user may or may not own.
This is unique to PR 12: PR 3-11 all had at least one external reference
(open_spiel, noambrown, postflop-solver, PioSolver).

**Mitigation:**
- Structural sanity (§7.2) doesn't need external data.
- Stability diagnostic (§7.4) doesn't need external data.
- Intuition gauntlet (§7.6) is hand-rolled.
- MonkerSolver cross-validation (§7.5) is opt-in; spec ships without the data,
  the user opts in if they have the data.

### 10.5 PR 12 may not converge in finite wallclock on the Python tier

Per PR 5's risk on Python tier wallclock for HU (PR 5 §12: *"Each iteration
walks the full tree. Even on a flop-start spot with 256/128/64 abstraction, a
10k-iteration solve could take many hours"*), 3-handed at 128/64/32 may be
worse. The Rust port (Agent B's `multiway.rs`) is the production path.

**Mitigation:**
- Python tier targets *small* 3p subgames (river-only, 1k-infoset fixtures).
- Rust tier targets the actual flop/turn subgames.
- Tests are marked `@pytest.mark.slow` for solves >1min.

### 10.6 UI surface inconsistency

PR 10 (Agent C in PR 12's fan-out) extends the range matrix UI, but if PR 10
locks the matrix to HU-only assumptions internally (e.g. range-matrix
aggregation assuming exactly 2 ranges), 3-handed display may require deeper
refactoring than the spec anticipates.

**Mitigation:**
- PR 10's `RangeWithFreqs` and `cell_strategy_summary` are designed to be
  range-count-agnostic. Verified by reading PR 10 spec §7. If a downstream
  refactor is needed, scope it as PR 12.5.

### 10.7 Linear CFR may not be the right schedule for 3-handed

We adopt LCFR because Pluribus did, but Pluribus's empirical validation was
6-player no-limit. 3-handed-specific schedule tuning is an open research
question. We may discover that DCFR_{1.5, 0, 2} works fine, or that a new
schedule is needed.

**Mitigation:**
- LCFR cutoff is configurable (`lcfr_cutoff` parameter).
- Stability diagnostic gives signal on whether the schedule converged.
- Documented as "tunable; defaults follow Pluribus".

### 10.8 95%-pruning may interact badly with our action abstraction

Pluribus pruned within an action abstraction tuned for 6p NLHE; our action
abstraction is 33/75/100/150/200 + all-in (the PR 3 menu). Pruning thresholds
may need re-tuning.

**Mitigation:**
- Pruning threshold C is configurable.
- Default C = -300_000 (cents-scaled; Pluribus paper doesn't give an absolute
  number, but the order of magnitude follows from blueprint regret scales).
- A/B test: solve with pruning and without; report wallclock diff. Done as a
  manual diagnostic in the autonomous log; not a CI test.

## 11. Estimated effort

**6–12 weeks of focused work.** Substantial. Breakdown:

| Sub-task | Estimate |
|---|---|
| Agent A (N-player generalization of HUNL game state) | 1.5–3 weeks |
| Agent B (multiway_solver.py + Rust port + LCFR loop + BR) | 2.5–4 weeks |
| Agent B (Rust port + differential test) | 1–2 weeks |
| Agent C (tests + fixtures + UI integration) | 1–2 weeks |
| Audit + bugfix cycle | 0.5–1 week |
| MonkerSolver cross-validation (if user has data) | 0.5–1 week |
| Empirical abstraction tuning (memory profiler runs) | 0.5–1 week |

This is the longest single PR in the v1 roadmap by a 2–3× factor over PR 5.
Worth flagging upfront: the user may want to scope PR 12 down to "Agent A only,
3p game state available but no solver yet" as a half-step, then PR 12.5 ships
the solver. Open question to user (see §12).

## 12. Open decisions for user

Each entry locks a default; if the user prefers otherwise, redirect before
launching A/B/C.

1. **Push/fold for 3-handed at short stacks?** Default: **out of v1 scope.** The
   2p push/fold table in PR 3.5 is built from Sklansky-Chubukov / Nash HU SNG
   charts that don't generalize cleanly to 3-handed. A 3-handed push/fold table
   would require its own multi-player Nash approximation, which has the same
   theoretical issues as the postflop solve. Override candidate: ship a
   precomputed 3-handed push/fold table from ICMIZER / equivalent source if the
   user has the data. Rejected by default.

2. **Render exploitability differently in UI?** Default: **yes** — per §6.3,
   the 3-handed result panel shows three per-pair best-response gaps with the
   "≈" prefix and the explanatory tooltip. No single "exploitability" number.
   Override candidate: show a single number (max of the three per-pair gaps)
   for visual simplicity. Rejected because it conflates two different metrics.

3. **Cross-validate against MonkerSolver?** Default: **opt-in via
   user-supplied data.** The spec ships the harness in §7.5 but no fixture
   data. The user, if they own MonkerSolver, exports 3-handed flop spots to
   `tests/fixtures/monker/` and the harness runs. Override candidate: require
   MonkerSolver validation as a gate (would block PR 12 on a paid Windows
   product). Rejected.

4. **Ship PR 12 as a single PR or split into PR 12 (game state) + PR 12.5
   (solver)?** Default: **single PR** if Agents A/B/C all complete in the
   6–12 week window. Override candidate: split into PR 12 (Agent A only,
   N-player game state generalized) + PR 12.5 (Agent B + C; solver, UI,
   tests). Splitting reduces risk but doubles the audit + review overhead.
   User to decide based on PR 11's actual timeline.

5. **Default N for "3-handed"** — `num_players=3` is locked. Future extensions
   (4-handed, 6-handed) are out of scope per §2.

6. **Default abstraction tier for 3-handed.** Default: **128 / 64 / 32** per
   §5.2. Override candidates per the §5.2 table. User can pick a tier when
   building the artifact; the spec just locks the default for v1.

7. **LCFR cutoff fraction.** Default: **t_cutoff = T // 2** per Pluribus's
   recipe. Override candidates: 0 (pure plain CFR; safer but slower) or T (pure
   LCFR throughout; what Pluribus did *initially* before they added the
   cutoff). Pluribus paper p. 3 doesn't give a numerical cutoff; "T/2" is our
   conservative interpretation of "after that the discount factor is not
   worth it."

8. **Pruning threshold C.** Default: **-300_000 cents** (-3000 BB, scaled to
   our integer cents). Override candidates: a smaller absolute value (more
   aggressive pruning, more speedup, more risk of skipping useful actions) or
   larger (less aggressive). Empirical tuning recommended in the autonomous
   log after first end-to-end solve.

9. **Stability diagnostic seed count.** Default: **3 seeds (0, 1, 2)** per §7.4.
   Override candidate: more seeds (better signal, longer wallclock). Three is
   the minimum that detects any one seed being anomalous.

10. **What goes in `MultiwaySolveResult` vs. tuple-of-results.** Default:
    **dataclass** (extends `SolveResult`) per the pattern in PR 5
    `HUNLSolveResult`. Override candidate: tuple of three `SolveResult`s, one
    per player. Rejected (loses per-result structural cohesion).

11. **Whether `solve()` in `solver.py` auto-detects 3-handed.** Default:
    **yes** — `solver.solve(HUNLPoker(config))` with `config.num_players == 3`
    routes to `solve_3p_postflop` transparently. Override candidate: require
    explicit `solve_3p_postflop` import. Rejected — the unified entry point is
    a load-bearing UX choice from PR 5.

12. **`num_players` flag in the library (PR 11) export format.** Default:
    **included** in `SpotDescription.config.num_players`, which is already
    serialized. No schema change needed. The library row badge in §6.2 reads
    this field.

13. **CLI flag for 3-handed:** Default: `--num-players 3` with three range
    arguments. Override candidate: subcommand `solve-3p` for visual clarity.
    Rejected — subcommand proliferation adds maintenance burden when a flag
    suffices.

## 13. Reference citations

Cited for the theoretical-honesty framing (per the spec's reference-first
rule):

- **Brown, N. & Sandholm, T. (2019). "Superhuman AI for multiplayer poker."
  *Science* 365:6456, 885–890.** Local: `references/papers/pluribus_brown_2019_science.pdf`.
  Indexed entry: `references/papers/_INDEX.md` `pluribus_brown_2019_science.pdf`.
  - p. 1: 2p0s Nash equilibrium "unbeatable" property explicitly limited to 2p0s.
  - p. 2: "the case of six-player poker, we take the viewpoint that our goal
    should not be a specific game-theoretic solution concept, but rather to
    create an AI that empirically consistently defeats human opponents."
  - p. 2: Lemonade Stand Game illustration of why joint independent Nash play
    is not itself Nash.
  - p. 3: Linear CFR + 95%-pruning recipe used in Pluribus blueprint training.
  - p. 3: "CFR guarantees in all finite games that all counterfactual regrets
    grow sublinearly in the number of iterations."
  - p. 3: 8 days on 64-core server, 12,400 CPU core-hours, <512 GB RAM for
    blueprint training. Hardware floor reference for our scaled-down version.

- **Gibson, R. (2013). "Regret Minimization in Non-Zero-Sum Games with
  Applications to Building Champion Multiplayer Computer Poker Agents."**
  Local: `references/papers/gibson_2013_regret_minimization.pdf`.
  Indexed entry: `references/papers/_INDEX.md` `gibson_2013_regret_minimization.pdf`.
  - The strongest known theoretical property of CFR in n-player non-zero-sum
    games: regret minimization eliminates iteratively strictly dominated
    actions. This is *much weaker* than Nash convergence but is what we have.
  - Memory-saving "current-strategy CFR" variant: drop the average-strategy
    accumulator for n-player. We do NOT adopt this in PR 12 (we need the
    average for the stability diagnostic and BR computation), but it's a
    candidate for PR 12.5 memory optimization.

- **Zinkevich, M., Johanson, M., Bowling, M., Piccione, C. (2007). "Regret
  Minimization in Games with Incomplete Information."** Local:
  `references/papers/zinkevich_2008_cfr_nips.pdf`. The foundational CFR paper;
  its convergence proof is explicitly 2p0s.

- **GTO Wizard blog: "Quirks of Nash Equilibrium in Multiway."** Local:
  `references/blog/gtow_quirks_multiway_nash.md`.
  - User-facing framing: *"in a multiplayer scenario, the foundational
    promises of a Nash Equilibrium don't hold."*
  - The EV-transfer / Nash-distance discussion is the closest pre-existing
    user-facing explanation of our framing. The UI tooltip in §6.3 is written
    in this register.

For the HUNL game-tree shape (PR 12 extends):

- PR 3 spec: `docs/pr3_prep/pr3_spec.md` — HUNL tree builder, action
  abstraction, blinds-posting, infoset key format.
- PR 5 spec: `docs/pr5_prep/pr5_spec.md` — postflop solve pipeline, memory
  profiler, abstraction integration. Mirror this structure for 3p.
- PR 10 spec: `docs/pr10_prep/pr10_spec.md` — UI architecture; the
  `RangeWithFreqs` extension is range-count-agnostic.
- PR 11 spec: `docs/pr11_prep/pr11_spec.md` — library schema; `num_players`
  flows through `SpotDescription.config`.

## 14. Success criteria

- `poker-solver solve --game hunl --num-players 3 --board "As 7c 2d Kh 5s"
  --stacks 100,100,100 --abstraction tests/fixtures/3p_tiny_abstraction.npz
  --iterations 1000` runs to completion and prints a strategy table with the
  "≈ approximate equilibrium" banner and three per-pair best-response gaps.
- The river-only 3p smoke fixture solves in <60 sec on the M-series MacBook.
- All PR 3/4/5/6/7/8/9/10/11 tests pass unchanged.
- New tests pass (~30 new tests across the three new test files + multiway
  fixtures).
- `ruff check poker_solver tests ui` clean.
- `mypy --strict poker_solver/multiway_solver.py poker_solver/hunl.py
  poker_solver/action_abstraction.py` clean.
- Differential test in `tests/test_3p_diff.py` passes on the tiny 3p river
  subgame (Python ↔ Rust strategy L1 < 1e-6 after 500 iterations on shared
  inputs).
- Stability diagnostic on the river-only fixture: pairwise L1 < 0.05 across
  seeds 0, 1, 2.
- The audit agent reviews against this spec and produces
  `docs/pr12_prep/audit_report.md`. Focus areas listed in §15.

## 15. Post-implementation audit

Per PLAN.md "Mandatory PR audit from PR 3 onward": after A+B+C land, a fresh
`general-purpose` audit agent runs with no prior context and reviews:

- The full diff (Agent A's `hunl.py` + `action_abstraction.py` deltas, Agent
  B's `multiway_solver.py` + `multiway.rs` + `solver.py` deltas, Agent C's
  tests + UI deltas).
- Against this spec only.
- Output: `docs/pr12_prep/audit_report.md` with structured sections (must-fix
  / should-fix / nice-to-fix / looks-good).
- User reads alongside `pr_report.md` before commit OK.

Focus areas the audit must touch:

- **No-Nash-claim discipline.** Strings, comments, docstrings, CLI output,
  UI labels: nothing says "Nash" or "GTO" for 3-handed without the
  "≈ approximate" framing. The string-literal audit in §9 #4 is the gate.
- **Side-pot correctness.** §9 #1 explicit fixture cases tested.
- **3-way showdown evaluation.** §9 #2 multi-winner-per-side-pot logic.
- **N-player turn rotation.** §4.1 SB → BB → BTN order, with fold/all-in
  skip semantics.
- **Regression on N=2 path.** All PR 3-11 tests pass.
- **Linear CFR + pruning implementation matches Pluribus paper.** Per §3.2.
- **Stability diagnostic actually rerun-stably itself.** I.e., running the
  diagnostic twice produces the same diagnostic numbers (the diagnostic itself
  must be deterministic given the same seeds).
- **UI badge unsuppressible.** Per §6.3.
- **MonkerSolver fixture format documented.** Per §7.5.
- **License hygiene.** No new AGPL/GPL dependencies; no code copied from
  postflop-solver or TexasSolver (both AGPL) for multi-player logic. Read-only
  inspiration only.

## 16. Out-of-scope follow-ups

- **PR 12.5:** real-time depth-limited search for 3-handed (Pluribus-style k=4
  continuation strategies; paper p. 4). Substantial extension; gated on PR 12
  shipping cleanly.
- **PR 12.5:** 3-handed preflop solve (the hard one; out of v1 per §2).
- **PR 13:** 4–6 player extension. Not on the v1 roadmap; PLAN.md §1
  "Explicitly out of scope: 4–9 player full game."
- **PR 13+:** library-aware warm-starts from a 3-handed solved-spot cache.
- **PR 13+:** ICM-aware 3-handed solver (tournament / SNG bubble).
- **PR 13+:** node-locking for 3-handed (exploitative analysis).
- **PR 13+:** richer multi-player range editor in the UI (per-position
  preset library, e.g. "UTG opens", "BTN 3-bets vs UTG").
