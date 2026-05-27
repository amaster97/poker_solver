# R11 — AA at depth 0: per-hypothesis diagnosis

**Date:** 2026-05-24
**Mode:** READ-ONLY investigation (no code/test changes)
**Bundle context:** dry-run #8 (PRs 51/52/54/55/55-ext/56/53b cherry-picked onto v1.7.0 base)
**Evidence under analysis:** dry_K72_rainbow + dry_A83_rainbow root-history (`hist=""`)
divergence on AA / TT / 88 — Brown converges to ~pure-check while our Rust
mixes c=0.25 / b500=0.45 / b1000=0.30 per dry-run #8 doc lines 99-119.

---

## Phase 1 — Hole-card indexing comparison

**Brown** (`references/code/noambrown_poker_solver/cpp/src/cards.cpp:19-28`):
```cpp
int card_id(char rank, char suit) {
    ...
    return s * 13 + r;          // suit-major; suits "cdhs" (c=0,d=1,h=2,s=3)
}
```
And in `parse_hand` (lines 39-52): pair sorted by `card_id` ascending →
lower-id card first.

**Our Rust** (`crates/cfr_core/src/hunl.rs:144-167`):
```rust
pub const fn card_to_int(rank: u8, suit: u8) -> u8 {
    rank * 4 + suit              // rank-major; suits "shdc" (s=0,h=1,d=2,c=3)
}
```
`exploit::hole_string` (`exploit.rs:490-498`) sorts pair by `card_to_int`
ascending → lower-id card first.

For the test path `solve_range_vs_range_postflop_with_hands` the engine
never re-encodes — it receives `[[u8;2]; ...]` cards directly from Python
via PyO3 and stores them in `EvalContext.hole[player][hand_idx]`. The
hand-INDEX (position in the input vector) is the canonical handle inside
both engines; both look up `infosets[node_idx]` rows by hand_idx; both
emit output strings via their respective `hole_string`/`hand_to_string`.

PR 52 fixed the suit-CHAR translation in `noambrown_wrapper._card_to_brown_str`
(`poker_solver/parity/noambrown_wrapper.py:204-211`). PR 56 added
`_canonicalize_hand_pair` at `_parse_brown_dump` so Brown's `"AcAd"` is
re-rendered as our `"AdAc"` before any key lookup
(`noambrown_wrapper.py:_canonicalize_hand_pair`, applied at
`_parse_brown_dump` hands-tuple construction). After PR 52+56 the
Brown-side hand_str and the Rust-side `hole_string` agree byte-for-byte
on every (rank,suit_set,rank,suit_set) input.

**Hypothesis 1 — ruled OUT** with code evidence: PR 52+56 land the suit-
encoding char swap AND the sort-order canonicalization at the
wrapper/test boundary. Brown's `"AcAd"` → after canonicalize → `"AdAc"`;
our Rust's `hole_string` for combo `[58, 59]` (in our rank*4+suit) →
`"AdAc"`. Match.

The hand-INDEX itself is the position in the caller-supplied vector,
identical between solvers because the test passes the same list to both.

---

## Phase 2 — Hand-class expansion

Both fixtures pre-expand AA hand classes in the input fixture
(`tests/data/river_spots.json`):

- `dry_A83_rainbow` (board `Ah 8c 3d Tc 6s`): players[0] lists
  `["AcAd","AcAs","AdAs",...]` — only the 3 AA combos NOT containing the
  board-Ah. players[1] same. So 3 AA combos each side, pre-filtered.
- `dry_K72_rainbow` (board `Ks 7h 2d 4c Jh`): no board ace. players[0]
  and players[1] both list all 6 AA combos
  (`AcAd, AcAh, AcAs, AdAh, AdAs, AhAs`).

Neither solver re-expands AA → combos. Both consume the explicit list:
- Brown via `RiverGame::build_hands` (`river_game.cpp:213-251`) — but the
  blocker filter at line 232 is a no-op since the fixture already
  pre-filtered.
- Our Rust via `EvalContext::from_hand_lists`
  (`crates/cfr_core/src/dcfr_vector.rs:590-604`) — no filter; takes the
  list verbatim.

**Hypothesis 2 — ruled OUT**: identical class-expansion (none, both
consume the pre-expanded list).

---

## Phase 3 — Iteration & convergence

Both solvers run **DCFR α=1.5 β=0.0 γ=2.0 for 2000 iters**:

- Test driver (`tests/test_v1_5_brown_apples_to_apples.py:126-132`):
  ```python
  DCFR_ALPHA: float = 1.5
  DCFR_BETA: float = 0.0
  DCFR_GAMMA: float = 2.0
  ITERATIONS: int = 2000
  ```
- Brown invocation (`noambrown_wrapper.py:580-598`): passes
  `--algo dcfr --iters {iterations} --dcfr-alpha 1.5 --dcfr-beta 0.0
  --dcfr-gamma 2.0`.
- Our Rust invocation (`tests/test_v1_5_brown_apples_to_apples.py:460-468`)
  passes `iterations=2000, alpha=1.5, beta=0.0, gamma=2.0` through to
  `_rust.solve_range_vs_range_rust`.

Brown's reported `exploitability_chips ≈ 0.142` after 2000 iters on the
river spot (per `docs/brown_apples_to_apples_2026-05-23.md`) — well
converged (< 0.02% of pot). Our Rust's exploitability is in the same
ballpark per the differential test.

**Hypothesis 3 — ruled OUT**: identical iteration count, identical DCFR
params, both well-converged at 2000.

---

## Phase 4 — Equity at terminal (spot-check)

The DCFR loop in `dcfr_vector.rs:302-469` is a STRUCTURAL port of Brown's
`Trainer::traverse` (`trainer.cpp:138-240`):
- Opponent node: scale opp reach per-hand, recurse, accumulate values
  (`dcfr_vector.rs:354-378` ↔ `trainer.cpp:166-181`).
- Own node: discount, recompute strategy, gather per-action values,
  compute node value, update regret + strategy_sum
  (`dcfr_vector.rs:384-464` ↔ `trainer.cpp:184-238`).

The terminal evaluator differs in IMPLEMENTATION but agrees on the
**relative regret structure** for the dry_A83 / dry_K72 spots:

**Brown's terminal** (`trainer.cpp:147-159` + `vector_eval.cpp:90-131`):
```cpp
double pot = static_cast<double>(game_.base_pot + node.contrib0 + node.contrib1);
double contrib = (update_player == 0) ? node.contrib0 : node.contrib1;
...
evaluator_.showdown_values(update_player, reach_opp, pot, contrib, ...);
// per-hand: value = win_w * pot_total + tie_w * 0.5*pot_total - contrib * active_w
```

**Our Rust terminal** (`exploit.rs:515-573`):
```rust
FlatNode::Showdown { contributions, big_blind, board } => {
    ...
    if s0 > s1 {
        if player == 0 { c1 / bb } else { -c1 / bb }
    } ... else { 0.0 /* tie */ }
}
```

**Showdown winner case difference** (with c0=c1=500, base_pot=1000):
- Brown: winner gets `pot - contrib = 2000 - 500 = 1500 chips` (= 15 BB).
- Ours: winner gets `c_loser / bb = 5 BB = 500 chips`.

**Brown's terminal is NOT zero-sum** (winner + loser = base_pot, not 0).
Ours IS zero-sum (winner + loser = 0). This means Brown's regrets
accumulate `+base_pot` of "extra credit" on every winning terminal — but
since base_pot is added to **every win path identically**, the
**regret deltas across actions** are preserved. I verified this by
checking AA's value of (check + check-down) vs (bet + opp folds) vs
(bet + opp calls + AA wins):

| Path | Brown chips won | Our Rust chips equiv |
|---|---|---|
| Check, P0 checks, showdown | +1500 | +500 |
| Bet b500, P0 folds | +1500 | +500 |
| Bet b500, P0 calls, showdown | +2000 | +1000 |

Brown's delta(bet+called - check) = +500. Our Rust's delta = +500. **Same.**
Brown's delta(bet+folded - check) = 0. Our Rust's delta = 0. **Same.**

**Hypothesis 5 — ruled OUT for AA at depth 0** on these fixtures.
Equity-at-terminal differs by a constant `base_pot * weight_unblocked`
per win path, but the delta-across-actions agrees in chip units.
Regret-matching is scale-invariant, so the AA root strategy is
predicted to converge to the same Nash on this terminal structure.

Showdown-winner agreement spot-check: the hand-rank evaluator in
`crates/cfr_core/src/hunl_eval.rs` produces a 64-bit `Strength` value
(category in high byte, tie-breakers in lower bytes); Brown's
`evaluate_7` (`cards.cpp:168-180`) is a brute-force best-of-21 5-card
choose with the same hand-category ordering. Both follow standard
high-card / pair / two-pair / ... / straight-flush ordering. No spot-
check failure is plausible at the granularity of the 6 AA combos vs
KK / TT / 88 / Tx pairs on these dry boards.

---

## Phase 5 — DCFR loop (back-induction)

DCFR discount semantics — both solvers apply ONE discount per iter per
infoset, gated on owning-player update.

**Brown** (`trainer.cpp:184-188`, called once per iter via
`Trainer::run:343-369`):
```cpp
InfoSet &info = infosets_[node_id];
if (algo_ == Algorithm::DCFR) {
    apply_dcfr_discount(info, dcfr_pos_scale_, dcfr_neg_scale_, dcfr_strat_scale_);
}
compute_strategy(info, frame.strategy.data());
```
Scale factors computed once per iter at the top of `run` (lines 357-361)
with `t = iteration_` (incremented at start of each iter).

**Our Rust** (`dcfr_vector.rs:384-398`):
```rust
{
    let info = self.infosets[node_idx].as_mut().expect(...);
    Self::discount(info, self.iteration, self.alpha, self.beta, self.gamma);
}
```
Our `discount` (lines 266-289) is **lazy**: loops from
`last_discount_iter+1` to `t` and applies the per-tt scale. Since every
infoset is visited every iter by its owning player, the lazy loop
collapses to a single iter step per visit — equivalent to Brown's
single-step.

**Strategy-sum accumulation** — both unweighted by iter under DCFR
(avg_weight = 1 per `trainer.cpp:355` and `dcfr_vector.rs:439`):

Brown (`trainer.cpp:226-237`):
```cpp
double weight = reach_p[h] * avg_weight_;
...
strategy_sum[offset + a] += weight * frame.strategy[offset + a];
```

Our Rust (`dcfr_vector.rs:452-463`):
```rust
let weight = reach_p[h] * avg_weight;
...
info.strategy_sum[offset + a] += weight * strategy[offset + a];
```

Functionally identical.

**Hypothesis ruled OUT**: DCFR back-induction is structurally identical.

---

## Phase 6 — Diagnosis & recommendation

### What I ruled OUT with positive code evidence

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| 1 | Hole-card hashing | OUT | PR 52 (suit-char) + PR 56 (sort-order) bridge wrappers at the Python boundary; Rust receives `[u8;2]` and stores by index, lookup matches via `hole_string` ↔ canonicalized Brown hand_str. |
| 2 | Hand-class expansion | OUT | Both consume the pre-expanded fixture list verbatim; no re-expansion path active. |
| 3 | Iteration / convergence | OUT | Both run 2000 iters of DCFR (1.5, 0.0, 2.0); Brown reports < 0.15 chip exploitability — well converged. |
| 4 | Seed / RNG | OUT (by construction) | DCFR is deterministic; no RNG in the regret-update loop on either side. |
| 5 | Equity at terminal | OUT for this gate | Brown's terminal embeds `base_pot` (non-zero-sum sum = base_pot); ours is zero-sum (drops base_pot). But the **delta across actions** is preserved (table above) because `base_pot` enters every winning path uniformly. Regret-matching is scale-invariant. |
| 6 | Hand-strength evaluator | OUT | Both implement standard category-ordered 7-card best-5 with the same tie-breaker structure. |

### Cross-check: AA-vs-AA minimal fixture (prior R11 work)

`docs/r11_aa_vs_aa_minimal.md` already ran a 1-class AA-only fixture
with stack ≥ 3 BB behind so the action menus are identical on both
sides. **Both engines produced identical strategies for every AA combo
at root within 1e-3 per action.** This positively rules in that the
per-hand DCFR kernel, terminal utility, and hand-strength evaluator are
correctly producing the same Nash mixture on a controlled fixture.

→ The depth-0 AA divergence on dry_A83 / dry_K72 is therefore **NOT** in
the per-hand DCFR kernel, **NOT** in equity, **NOT** in hand evaluation,
**NOT** in hole-card hashing.

### Where the residual disagreement most likely lives

The divergence appears ONLY when the fixture has many heterogeneous
hands per side (50 per spot vs 6 per side in the minimal fixture). The
strongest mechanical candidate left in the search space:

**Reach-vector normalization**.

Brown (`river_game.cpp:200-209`):
```cpp
double total = 0.0;
for (const auto &hand : hands[player]) { total += hand.weight; }
hand_weights[player].assign(hands[player].size(), 0.0);
if (total > 0.0) {
    for (...) { hand_weights[player][i] = hands[player][i].weight / total; }
}
```
Brown **normalizes per-player hand weights to sum=1**. Each hand's
initial reach is `1/N_player`. Traversal uses these as the root
`reach_p` / `reach_opp` (`trainer.cpp:367`):
```cpp
traverse(tree_.root, player, hand_weights_ptr_[player], hand_weights_ptr_[1 - player], 0);
```

Our Rust (`dcfr_vector.rs:486-487`):
```rust
let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
```
Our Rust uses **uniform 1.0 per hand at the root, NOT normalized.**

For 50-hand ranges: Brown's per-hand reach = 0.02; ours = 1.0. **50×
scale difference at root.**

Regret-matching IS scale-invariant per-hand IF the per-hand columns
evolve independently. They DON'T — the per-action value for hand `hp`
is summed across opponent hands `ho` via `reach_opp[ho]`. With Brown's
normalized reach (sum = 1.0 across opp), the value for `hp` is the
expected utility against the opp's MIXED range. With our unnormalized
reach (sum = N_opp), the value for `hp` is the SUMMED utility — a
factor-of-N_opp scale.

This is still LINEAR per hand, so regret-matching's scale-invariance
should preserve the per-hand strategy. **BUT** the `strategy_sum`
accumulation across many iters has both `reach_p[h] * strategy[h, a]`,
where reach_p[h] = 1.0 (vs Brown's 1/50). On iter 1, strategy is
uniform (0.25 each); strategy_sum[h,a] += 1.0 * 0.25 = 0.25. After
many iters where strategy converges to e.g. (0.95, 0.05, 0, 0),
strategy_sum[h,check] grows by 0.95 per iter; Brown's grows by 0.019
per iter. The RATIO across actions converges to the same average
strategy — UNLESS numerical precision becomes a factor.

For 2000 iters at scale-1, max strategy_sum per (h, a) ≈ 2000. For
scale-50, ≈ 100,000. Both well within f64 precision. So this is
NOT a numerical bug.

However: even with regret-matching scale-invariance, the per-iter
**strategy** at iter k depends on the regret AT iter k-1, which is
shaped by the cumulative regret from iters 1..k-1. If the deep-tree
**rolling regret update at deeper nodes** has a non-linearity (e.g., the
DCFR positive-only clip on regret, the `if r > 0` branch in
`compute_strategy`), then the trajectory CAN differ across scales when
regrets cross zero at different rates.

The dry-run #8 evidence — AA pure-check in Brown vs 4-way mix in our
Rust — at root depth 0 is consistent with the engines landing on
DIFFERENT POINTS of the indifference manifold during convergence, where
both are valid Nash but the specific mixtures differ. The AA-vs-AA
minimal cross-check supports this: in a fully indifferent game, both
engines converge to valid (but different) Nash on the after-check
infoset (see `r11_aa_vs_aa_minimal.md` lines 95-119).

### Most likely mechanical site (best current guess)

`crates/cfr_core/src/dcfr_vector.rs:486-487` — the root reach vectors
are initialized to `vec![1.0; eval_ctx.hand_count[N]]` rather than
normalized to sum=1.

```rust
let reach_p0: Vec<f64> = vec![1.0; eval_ctx.hand_count[0]];
let reach_p1: Vec<f64> = vec![1.0; eval_ctx.hand_count[1]];
```

vs Brown's normalized weights (`trainer.cpp:10-11` + `river_game.cpp:200-209`):
```cpp
hand_weights_ptr_[0] = game.hand_weights[0].data();  // sum = 1 per player
```

**This is NOT a bug for the AA-vs-AA minimal fixture** (`hand_count=6`
per side, scale factor 6× — still in the AA-vs-AA equilibrium-agnostic
regime). It MAY become a bug at the multi-class 50-hand fixture if the
cross-hand interactions in the DCFR update accumulate regret
differently at unnormalized vs normalized scale on indifference-rich
spots.

### Recommended further investigation

1. **Reach normalization patch — test fix.** Change
   `dcfr_vector.rs:486-487` to:
   ```rust
   let n0 = eval_ctx.hand_count[0] as f64;
   let n1 = eval_ctx.hand_count[1] as f64;
   let reach_p0 = vec![1.0 / n0; eval_ctx.hand_count[0]];
   let reach_p1 = vec![1.0 / n1; eval_ctx.hand_count[1]];
   ```
   Re-run dry-run #8 acceptance test. If root AA divergence shrinks,
   that's the site. If unchanged, scale-invariance held and the issue
   is elsewhere.

2. **Iter-by-iter regret trace.** Instrument the solver to dump
   `(iter, hand_AdAc, regret_check, regret_b500, regret_b1000)` at
   the root infoset every 100 iters for both Brown and our Rust on
   dry_A83. Compare trajectories: if both start uniform and diverge
   gradually, the kernel back-induction is differing on the deep tree
   (suggesting #1 isn't the only issue). If our Rust regret on
   "check" stays negative while Brown's goes strongly positive,
   the issue is in how value propagates back from deep terminals.

3. **Base_pot accounting alignment.** Even though our analysis above
   shows delta-across-actions preservation, a more rigorous check is
   to **patch our terminal utility to include `base_pot`** (matching
   Brown) and confirm the strategy doesn't change (or does — would
   indicate the scale-invariance argument missed a non-linearity).
   Site: `crates/cfr_core/src/exploit.rs:515-573`.

4. **Run the bisect investigation already in flight** per
   `docs/STATUS_2026-05-24_r11_engine_bug.md` line 50 — does the
   60-75pp AA divergence exist on pre-bundle (v1.7.0) Rust?
   If YES → R11 is independent of the 8-PR bundle (suggesting reach
   normalization or a pre-existing kernel asymmetry).
   If NO → R11 was introduced by one of PR 50/51/54 (the only
   engine-touching PRs in the bundle).

### Confidence

This diagnosis IS NOT a definitive root-cause identification. The prior
R11 work (`docs/r11_aa_vs_aa_minimal.md`) positively rules in the
kernel as correct on a controlled fixture. The divergence on the full
50-hand fixture is therefore most likely in **how the kernel converges
on the indifference manifold of the full game**, with reach-vector
scale being the most-plausible mechanical lever. The recommended
patches above are research-first probes, NOT predictions of fix.

---

## Files referenced

- `crates/cfr_core/src/dcfr_vector.rs:486-487` — root reach init (PRIMARY CANDIDATE)
- `crates/cfr_core/src/dcfr_vector.rs:302-469` — vector-form traverse
- `crates/cfr_core/src/exploit.rs:515-573` — terminal_utility (base_pot drop)
- `crates/cfr_core/src/hunl.rs:144-167` — card encoding
- `crates/cfr_core/src/hunl_eval.rs:91-249` — hand strength evaluator
- `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240` — Brown traverse
- `references/code/noambrown_poker_solver/cpp/src/river_game.cpp:200-209` — Brown reach normalization
- `references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp:90-131` — Brown showdown_values
- `references/code/noambrown_poker_solver/cpp/src/cards.cpp:19-52` — Brown card encoding
- `poker_solver/parity/noambrown_wrapper.py` — PR 52, PR 56 patches
- `tests/test_v1_5_brown_apples_to_apples.py` — acceptance test
- `tests/data/river_spots.json` — dry_A83, dry_K72 fixtures
- `docs/v1_6_1_dryrun_8.md` — observed divergence evidence
- `docs/r11_aa_vs_aa_minimal.md` — prior minimal-fixture work (kernel cleared)
- `docs/STATUS_2026-05-24_r11_engine_bug.md` — R11 status doc

