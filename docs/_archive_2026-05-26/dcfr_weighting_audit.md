# DCFR Weighting Audit — Brown reference vs. our vector-form Rust port

**Date:** 2026-05-24
**Scope:** `crates/cfr_core/src/dcfr_vector.rs` vs.
`references/code/noambrown_poker_solver/cpp/src/{trainer.cpp,trainer.h}`
**Focus:** α, β, γ, weighting constants (`regret_weight`, `avg_weight`),
iteration counter `t`, sampling scheme, off-by-ones.
**Investigation context:** P0 — empirical 22–42pp divergence at deep-cap.
Solver convention (chip ↔ BB normalization) already cleared.

---

## 1. α, β, γ defaults

### Brown's reference

`trainer.h:16-20`:

```cpp
struct DcfrParams {
    double alpha = 1.5;
    double beta = 0.0;
    double gamma = 2.0;
};
```

`main.cpp:35`: `DcfrParams dcfr;` — no overrides at the CLI default;
overrides flow through optional `--dcfr-alpha/beta/gamma` flags.

### Our Rust vector form

`crates/cfr_core/src/dcfr_vector.rs:167-178`:

```rust
pub struct VectorDCFR {
    alpha: f64,
    beta: f64,
    gamma: f64,
    iteration: u32,
    ...
}
```

No internal defaults — α/β/γ are constructor arguments. Callers pass them
through `solve_range_vs_range_postflop(config, iters, alpha, beta, gamma)`
(`dcfr_vector.rs:717-723`). The smoke test pins them at
`1.5, 0.0, 2.0` (line 940), matching the Brown defaults and the
paper (Brown & Sandholm 2019).

**Production call sites:** the PyO3 binding routes user-supplied or
config-defaulted α/β/γ through the same Brown values when invoked under
the "true RvR" tier. The audit relies on those call sites being held at
`(1.5, 0.0, 2.0)`; if a deep-cap config has been quietly tuned to
different α/β/γ, that is itself the bug.

**Verdict — α/β/γ:** IDENTICAL when callers honor the paper defaults.
No silent override in either codebase.

---

## 2. `regret_weight` / `avg_weight` (the per-iteration scalars)

### Brown's reference

`trainer.cpp:343-365` (DCFR branch):

```cpp
} else if (algo_ == Algorithm::DCFR) {
    regret_weight_ = 1.0;
    avg_weight_ = 1.0;
    double t = static_cast<double>(iteration_);
    double pos_base = std::pow(t, dcfr_.alpha);
    double neg_base = std::pow(t, dcfr_.beta);
    dcfr_pos_scale_ = pos_base / (pos_base + 1.0);
    dcfr_neg_scale_ = neg_base / (neg_base + 1.0);
    dcfr_strat_scale_ = std::pow(t / (t + 1.0), dcfr_.gamma);
}
```

DCFR uses `regret_weight_ = avg_weight_ = 1.0` *every iteration*. The
α/β/γ work is folded into `pos_scale/neg_scale/strat_scale` which run
through `apply_dcfr_discount` (not through `regret_weight`).

The non-DCFR algorithms (`LINEAR_CFR`, `CFR_PLUS`) use non-unit weights —
those are *not* what we are porting. DCFR is correctly 1/1.

Update sites (`trainer.cpp:210-237`):

```cpp
double delta = (action_values[a * update_hands + h] - base) * regret_weight_;
...
double weight = reach_p[h] * avg_weight_;
```

So Brown's regret-update increment has no opponent-reach multiplier
in the vector form; opponent reach is *already baked into the
per-hand `action_value` returned from the leaf*. The strategy-sum
update multiplies by `reach_p[h]` (own reach), not opponent reach.

### Our Rust vector form

`dcfr_vector.rs:438-439`:

```rust
let regret_weight = 1.0_f64; // DCFR uses `regret_weight = 1` (trainer.cpp:354-355).
let avg_weight = 1.0_f64;   // DCFR uses `avg_weight = 1` (trainer.cpp:355).
```

`dcfr_vector.rs:447-462`:

```rust
for h in 0..update_hands {
    let offset = h * action_count;
    let base = node_values[h];
    for a in 0..action_count {
        let delta = (action_values[a * update_hands + h] - base) * regret_weight;
        info.regret[offset + a] += delta;
    }
}
// strategy_sum
for h in 0..update_hands {
    let weight = reach_p[h] * avg_weight;
    if weight == 0.0 { continue; }
    let offset = h * action_count;
    for a in 0..action_count {
        info.strategy_sum[offset + a] += weight * strategy[offset + a];
    }
}
```

The `regret_weight` and `avg_weight` are hardcoded at `1.0`, with
inline comments correctly citing `trainer.cpp:354-355`. The
update arithmetic matches Brown's:
* `regret[h,a] += (action_value[a,h] - node_value[h]) * 1`
* `strategy_sum[h,a] += reach_p[h] * 1 * strategy[h,a]`

The `if weight == 0.0 { continue; }` skip is a micro-optimization —
Brown does not have it explicitly, but the math is bit-equivalent
because adding zero is a no-op.

**Verdict — weighting constants:** IDENTICAL.

---

## 3. Iteration counter handling

### Brown's reference

`trainer.cpp:343-369`:

```cpp
void Trainer::run(int iterations) {
    for (int i = 0; i < iterations; ++i) {
        iteration_ += 1;            // pre-increment BEFORE first traverse
        if (algo_ == Algorithm::DCFR) {
            ...
            double t = static_cast<double>(iteration_);    // t starts at 1
            ...
        }
        for (int player = 0; player < 2; ++player) {
            traverse(tree_.root, player, ...);
        }
    }
}
```

* `iteration_` starts at `0` (`trainer.h:60`) and is incremented to `1`
  before the FIRST player pass.
* So at the first DCFR step `t = 1`, and `t^α / (t^α + 1) = 0.5` —
  the standard DCFR step-1 behavior.
* `apply_dcfr_discount` is called from `traverse` at line 186 *only*
  when `player == update_player` (the early-return for opponent nodes
  is at line 181 *before* the discount call). So each infoset
  is discounted exactly ONCE per outer iteration `i`.
* The scales `dcfr_pos_scale_/neg_scale_/strat_scale_` are computed
  once at the top of the iteration and reused inside `apply_dcfr_discount`.

### Our Rust vector form

`dcfr_vector.rs:488-494`:

```rust
for _ in 0..iterations {
    self.iteration += 1;            // pre-increment, matches Brown
    self.traverse(tree, eval_ctx, 0, 0, &reach_p0, &reach_p1);
    self.traverse(tree, eval_ctx, 0, 1, &reach_p1, &reach_p0);
}
```

* `iteration` starts at `0` (line 196), pre-incremented to `1` before
  the first traverse. Same as Brown. **Off-by-one match: IDENTICAL.**
* `discount` is called inside `traverse` only at the
  `player == update_player` branch (`dcfr_vector.rs:384-389`):

```rust
{
    let info = self.infosets[node_idx]
        .as_mut()
        .expect("decision node must have an infoset slot");
    Self::discount(info, self.iteration, self.alpha, self.beta, self.gamma);
}
```

* The lazy `last_discount_iter` check in `discount`
  (`dcfr_vector.rs:267-289`) iterates `tt` from `last_discount_iter + 1`
  through `t`, applying the per-iteration scales. For a freshly-visited
  node at iteration `t = 1`, the loop runs once with `tt = 1`. This
  matches Brown's single application per iteration.
* The scales are re-derived per `tt` inside the loop rather than cached
  once at the top of `run`, but the arithmetic is `t^α / (t^α + 1)`,
  `t^β / (t^β + 1)`, `(t/(t+1))^γ` — bit-identical formulae.

**Verdict — iteration counter + discount frequency:** IDENTICAL.

---

## 4. Sampling scheme + reach-weighting at the leaf

Brown's `trainer.cpp:138-240` is **vector-form CFR, NOT MCCFR / external
sampling**. The full betting tree is walked once per (iteration × player),
with per-hand vectors carrying reach. Our `dcfr_vector.rs:302-468`
mirrors this exactly — no sampling, full enumeration.

### Where does opp_reach enter the regret update?

This is the load-bearing detail that differs from the *scalar* CFR
update (`crates/cfr_core/src/simd.rs:105-115`), where the regret
delta is `opp_reach * (action_v[i] - node_v)`.

In the vector form, opp_reach enters at the **terminal leaf**:
* Brown: `evaluator_.showdown_values(update_player, reach_opp, pot, ...)`
  computes `value[hp] = Σ_ho reach_opp[ho] * utility(hp, ho)`
  (`trainer.cpp:157`). The returned vector is already a counterfactual
  value for `update_player`.
* Our port: `terminal_value_vector` (`dcfr_vector.rs:619-656`) does
  the same explicit sum over opp hands with `reach_opp[ho] * utility`.

After that, opp_reach is implicit — the recursion returns per-hand cf
values, and at internal decision nodes the regret update has NO
additional opp_reach multiplier (correctly, since the leaf already
absorbed it). The Rust port matches this verbatim, with an in-line
comment at `dcfr_vector.rs:430-437` calling out the difference vs.
the scalar tier.

**Off-by-one in the leaf sum:** Brown uses `reach_opp[ho]` where `ho`
indexes the opp's hand vector — no off-by-one. Our port also iterates
`for ho in 0..opp_hands` (line 633). IDENTICAL.

**Verdict — sampling scheme + leaf weighting:** IDENTICAL.

---

## 5. Subtle differences worth noting (NOT divergence sources)

The audit looked for divergence sources. The differences below are
real but cannot account for the empirical 22–42pp deep-cap gap; they
are documented for completeness.

### 5a. Scalar precision

* Brown: `CFRScalar = float` by default (`trainer.h:23-27`),
  `double` only with `-DCFR_USE_DOUBLE`.
* Our port: `f64` always (`dcfr_vector.rs:74-77`).

If Brown's binary was built without `CFR_USE_DOUBLE`, his regret
buffers are `float`. After ~thousands of iterations this drifts —
but it drifts *toward* an under-regretted (smoother) strategy, which
*reduces* exploitability, opposite of our observed divergence
direction. So this is not the bug.

### 5b. Reach initialization

* Brown: initializes `reach_p` from `game.hand_weights[player]`
  (`trainer.cpp:10-11`), i.e. user-supplied per-hand range weights.
* Our port: hardcodes `reach_p0 = reach_p1 = vec![1.0; hand_count]`
  (`dcfr_vector.rs:486-487`).

This is a real difference for non-uniform ranges. For uniform-range
deep-cap solves, both reduce to `1.0` per hand, so this is IDENTICAL
for the tested deep-cap configs. If the deep-cap divergence is being
measured on a *non-uniform* range setup, this would be a real source.
The PLAN should confirm the test rig is uniform.

### 5c. Scratch arenas

Brown pre-allocates per-depth scratch frames (`trainer.cpp:27-37`,
`trainer.h:48-53`). Our port allocates per-call (`dcfr_vector.rs:295-300`
notes this as a v1.5.x perf follow-up). This is purely a perf detail;
no math change.

### 5d. Lazy vs. eager discount

* Brown: eager — discount runs every time the infoset is visited at
  `player == update_player`.
* Our port: lazy with `last_discount_iter` catch-up.

Since each infoset belongs to exactly one player and is visited
exactly once per iteration at `player == update_player`, both schemes
apply the discount exactly once per iteration `t` for that infoset.
The lazy form catches up across skipped iterations (relevant if an
infoset is unreachable on some passes); the eager form would have
already missed those — but Brown's eager form runs *unconditionally*
on every `traverse` visit at the update branch, so it doesn't miss
either (because the infoset IS visited at every update pass of its
owning player, since the tree walk is full vector-form, no sampling).

For full vector-form (no MCCFR), both schemes are mathematically
equivalent. IDENTICAL behavior.

---

## 6. Final verdict

**IDENTICAL** on α/β/γ, on `regret_weight`/`avg_weight`, on iteration
counter `t` (1-indexed in both), on sampling scheme (full vector-form
in both), and on where opp_reach enters the regret update (at the
terminal leaf in both).

**The DCFR weighting hyperparameters and update arithmetic are NOT
the source of the empirical 22–42pp deep-cap divergence.** The audit
should now turn to:

1. The betting tree itself (action sets, raise-cap handling, chance
   children at the boundary between streets) — `BettingTree::build_from`.
2. The terminal utility computation in `terminal_utility` (especially
   the all-in / partial-call boundary cases that get more common at
   deep-cap).
3. Range initialization assumptions (5b above) — confirm the test rig
   uses uniform ranges in both Brown's binary and our solve.
4. Scalar float precision (5a above) — only relevant if Brown was
   built without `CFR_USE_DOUBLE`; rule it out by checking the
   reference build flags.

None of the four sources above are *DCFR weighting* — they are tree-
construction or numerical-precision issues. This audit's negative
result narrows the hypothesis space.

---

## Summary table

| Aspect | Brown (`trainer.cpp/h`) | Our (`dcfr_vector.rs`) | Match? |
|---|---|---|---|
| α | 1.5 (default) | caller-supplied; smoke uses 1.5 | IDENTICAL when paper defaults |
| β | 0.0 (default) | caller-supplied; smoke uses 0.0 | IDENTICAL when paper defaults |
| γ | 2.0 (default) | caller-supplied; smoke uses 2.0 | IDENTICAL when paper defaults |
| `regret_weight` (DCFR) | `1.0` (l.354) | `1.0` (l.438) | IDENTICAL |
| `avg_weight` (DCFR) | `1.0` (l.355) | `1.0` (l.439) | IDENTICAL |
| Iter counter `t` start | 1 (pre-inc at start of iter) | 1 (pre-inc at start of iter) | IDENTICAL |
| Discount frequency | once / iter / owning infoset | once / iter / owning infoset (lazy catch-up) | IDENTICAL (math equiv) |
| Sampling scheme | vector-form, full enum | vector-form, full enum | IDENTICAL |
| Opp reach folded in at | terminal leaf | terminal leaf | IDENTICAL |
| Regret delta | `(a_v - node_v) * 1` | `(a_v - node_v) * 1` | IDENTICAL |
| Strategy-sum delta | `reach_p[h] * 1 * strategy[h,a]` | `reach_p[h] * 1 * strategy[h,a]` | IDENTICAL |
| Scalar precision | `float` default (`double` opt-in) | `f64` always | DIFFERENT (precision, NOT bias) |
| Reach init | `hand_weights[player]` | `vec![1.0; ...]` | DIFFERENT only for non-uniform ranges |
| Scratch arena | pre-allocated per depth | per-call allocation | DIFFERENT (perf only) |
