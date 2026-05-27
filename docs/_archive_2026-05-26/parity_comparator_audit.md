# Parity-Test Comparator Audit (v1.6.1 Dry-Run #2 Triage)

**Date**: 2026-05-24
**Trigger**: 4 prior audit agents confirmed both our solver and Brown's use
correct zero-sum semantics. The empirical 22-42pp divergence at deep-cap
in `v1_6_1_dryrun_attempt_2.md` therefore cannot stem from a
terminal-utility convention mismatch. This audit examines the
parity-test comparator harness for the *actual* source of the gap.

**Files audited**:
- `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/__init__.py`
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py`
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs` (action enumeration)
- `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp` (Brown's action enumeration)

---

## 1. What the comparator actually diffs

### 1.1 Brown side — quotes

`noambrown_wrapper._parse_brown_dump` (lines 718-723) reads Brown's
`--dump-strategy` JSON straight through:

```python
profile_entries[key] = BrownInfosetEntry(
    actions=actions_tuple,
    strategy=tuple(strategy_rows),  # shape (num_hands, num_actions)
)
```

These are **per-(history, hand, action) probability rows**, NOT utility
values, NOT exploitability deltas, NOT base_pot-normalized BR values.
The dump path is `--dump-strategy <path>` (`run_brown_solver` argv,
lines 595-596); stdout's `Exploitability (chips): X.YYY` line is
salvaged into `dump.exploitability_chips` but is **never consumed by
the diff harness**.

### 1.2 Our side — quotes

`test_v1_5_brown_apples_to_apples.py:469`:

```python
rust_result = _rust_solve_rvr(  # type: ignore[misc]
    config_json,
    ITERATIONS,
    DCFR_ALPHA, DCFR_BETA, DCFR_GAMMA,
    p0_holes, p1_holes,
)
rust_strategy = rust_result["average_strategy"]
```

`rust_strategy` is a `HashMap<String, Vec<f64>>` from
`build_average_strategy` (`crates/cfr_core/src/dcfr_vector.rs:668-706`):
each entry is one `(decision_node, hand)` row of average-strategy
probabilities — built by `VectorDCFR::compute_avg_strategy(info, &mut avg)`
on line 687. Again: **probabilities**, NOT utilities or BR values.

### 1.3 The diff itself

`test_v1_5_brown_apples_to_apples.py:547-556`:

```python
for a_idx in range(n_actions):
    brown_p = float(brown_row[a_idx])
    rust_p = float(rust_row[a_idx])
    if abs(brown_p - rust_p) >= PER_ACTION_TOL:
        diffs.append(...)
```

Both sides are dimensionless probabilities in `[0, 1]`. No unit
normalization. No subtraction of base_pot. No multiplication by
big_blind. **Direct probability-vs-probability diff.**

---

## 2. Does the comparator apply Brown's `-base_pot` normalization?

**No, and it doesn't need to.** Brown's `(br0 + br1 - base_pot) / 2.0`
normalization (`trainer.cpp:340`) is for converting per-player BR
*utility* values into a meaningful *exploitability* scalar (so the
"value of the game to each player" recombines correctly under Brown's
"pot-minus-self-contrib" winner utility). It applies only when you're
comparing utility/BR scalars across solvers with different terminal
conventions. **Average-strategy probabilities are convention-agnostic**:
they are the result of normalizing strategy-sum totals, and the
normalization cancels out any constant shift in the underlying utility
function. (Two solvers with utility functions `u` and `u + k` for any
constant `k` will arrive at the same Nash strategies because adding
`k` to every leaf utility doesn't change the regret-relative ordering
of actions at any infoset.)

So the unit-mismatch theory does **not** apply to the dry-run #2 22-42pp
gap. The diffed quantities are already in the same units.

---

## 3. So where IS the gap coming from?

The dry-run #2 report (`v1_6_1_dryrun_attempt_2.md:126`) explicitly
flags: **"6 action-count mismatches at `b1000A` history; Brown emits
2 actions, Rust emits 3"**. This is the load-bearing clue. Action-menu
mismatch directly causes probability-mass redistribution, which then
cascades through the upstream regret updates.

### 3.1 Concrete trace at history `b1000A` (K72, max_raises=3, stack=9500)

State after `b1000A`:
- P0 jammed all-in: `contrib=10000, stack=0, all_in=true`
- P1 to act: `contrib=1500, stack=8000, to_call=8500` (to_call > stack — P1 cannot fully call)

**Brown's `legal_actions` (`cpp/src/river_game.cpp:74-106`)**:
- Lines 74-75 push `c` and `f`.
- Line 76: `if (state.raises >= max_raises)` — false (`raises=2 < 3`).
- Line 81: `pot_after_call = pot + to_call`.
- Lines 83-97: enumerate sized raises. Each one needs `raise_amount > 0 && total_add > to_call`. For every sizing, `total_add` gets capped to `remaining=8000`, so `raise_amount = remaining - to_call = 8000 - 8500 = -500`. Filter rejects all.
- Lines 98-100: `if (include_all_in && remaining > to_call)` — false (`8000 > 8500` is false). Skip.
- Result: **`actions = [c, f]`** — exactly 2 actions.

**Our Rust `enumerate_legal_actions` (`crates/cfr_core/src/hunl.rs:1105-1139`)**:
- Lines 1115-1117: push `FOLD`, `CALL`.
- Lines 1122-1131: `cap_reached = 2 >= 3 = false`. Call `enumerate_raises`. Every sized raise filters out because `raise_to >= max_raise_to=9500`.
- **Lines 1133-1135: `if ctx.include_all_in { actions.push(ACTION_ALL_IN); }`** — UNCONDITIONAL push, with NO `remaining > to_call` guard. ALL_IN gets emitted.
- Result: **`actions = [FOLD, CALL, ALL_IN]`** — 3 actions.

The Rust ALL_IN here is degenerate: `compute_raise_to(ALL_IN) = cur_contrib + stack = 1500 + 8000 = 9500`, which is *less* than the opponent's contrib of 10000. This is semantically a "call for less" (P1 putting in their entire remaining stack), not a real raise. Brown subsumes this into the `c` action via its over-shove handling; Rust emits it as a third action label.

### 3.2 Why this fans out into a 22-42pp probability gap

When Rust splits probability mass across 3 actions (FOLD / CALL / ALL_IN-as-degenerate-call) while Brown splits across 2 (`c`, `f`), the CALL action under our regime takes ~2/3 of what Brown's `c` takes (rough — actual ratio depends on regret dynamics). The dry-run shows top-pair hands like `8hKh` calling 0.875 in Brown but only 0.454 in Rust at the deep node — a ~42pp drop that matches this mechanism. The remaining mass goes to ALL_IN (which leads to the same chip-pushing terminal as CALL — same payoff, just different label).

The fan-out cascades upstream: P0's earlier decision (whether to all-in at `b1000`) is informed by P1's response at `b1000A`. If Rust's tree at `b1000A` has different mass distribution than Brown's, P0's regret updates at `b1000` are different, propagating divergence backward.

### 3.3 Why PR 35c (paired cap-guard) didn't fix it

The PR 35c paired fix (`pr_35c_paired_fix_report.md`) gates ALL_IN
emission on `!cap_reached`:

```rust
if ctx.include_all_in && !cap_reached {
    actions.push(ACTION_ALL_IN);
}
```

That guard fires when `street_num_raises >= cap`. At `b1000A`,
`street_num_raises = 2`, `cap = 3`, so the guard is **inactive**.
PR 35c only blocks ALL_IN at hard cap; it doesn't catch the
"degenerate ALL_IN equivalent to call-for-less" case where the
shover doesn't have chips for a real raise. The dry-run #2 was run
against the paired-fix bundle and STILL shows the action-count
mismatch — direct evidence the guard is too narrow.

---

## 4. Likely cause of empirical 22-42pp divergence

**Primary**: Action-menu mismatch at `b1000A`-type "no-real-raise-possible"
nodes (Rust emits ALL_IN as a 3rd action where Brown emits only c/f).
This is at LEAST partially load-bearing for the gap — it directly
explains the 6 action-count mismatches the dry-run flagged, and the
worst diff cells in the dry-run cluster at deep-cap nodes where this
pattern would dominate (`b1500r5000`, `b1000r4500`).

**Possibly contributing** (need further investigation):
- Different convergence rates between Brown and our Rust on the same
  hyperparams (Brown's regret-matching+ uses subtle update sequencing
  decisions; would manifest as systematic over/under-shoot at any node,
  not just deep-cap).
- Brown's `base_pot` carried in the terminal utility as `pot - contrib_self`
  changes the value-of-shift constant on a per-leaf basis (the leaf
  utility is `(base_pot + opp_contrib)` for winner vs our
  `opp_contrib`); whether this shifts strategy DEPENDS on whether
  P_win at the leaf is hand-dependent. For pre-board chance-enum it
  cancels out, but for fixed-board river RvR where P_win is
  per-(hand, opp_hand) the shift is utility-correlated — could
  shift the regret ordering even though it's a "constant" per leaf.

**Not contributing**:
- Comparator unit-mismatch (already ruled out by quoting test_v1_5
  line 547-556).
- Different reach weights (both engines build the same restricted
  game from the same hand list).

---

## 5. Concrete next-step recommendation

**Highest-leverage fix (try first)**: Tighten our Rust ALL_IN guard
to match Brown's `include_all_in && remaining > to_call` shape.

Change `crates/cfr_core/src/hunl.rs:1133-1135` from:

```rust
if ctx.include_all_in && !cap_reached {
    actions.push(ACTION_ALL_IN);
}
```

to:

```rust
// Match Brown's `cpp/src/river_game.cpp:98` guard: ALL_IN is only
// a legal action if the shover has chips beyond what's needed to
// call. Otherwise the all-in is degenerate (equivalent to a
// call-for-less) and Brown subsumes it into the `c` action.
let remaining = stack_remaining(ctx);
let can_actually_raise_all_in = remaining > ctx.to_call;
if ctx.include_all_in && !cap_reached && can_actually_raise_all_in {
    actions.push(ACTION_ALL_IN);
}
```

Then re-run `pytest tests/test_v1_5_brown_apples_to_apples.py -v` to
measure the new max diff. The hypothesis is:

- Action-count mismatches drop to 0 across both K72 and A83.
- Per-cell max diff drops substantially (estimated 10-30pp reduction
  based on the ~42pp peak at deep-cap; the exact residual depends on
  what fraction of the gap was purely action-menu vs other sources).

Apply the matching guard to `poker_solver/action_abstraction.py`
(Python tier — preserves Rust↔Python parity that PR 35c established
and `test_exploit_diff` regression-gates).

**If residual gap > 5e-2** after this fix:
- Bisect via a minimal 2-hand test against Brown to isolate convergence
  vs leaf-utility-shift contributions.
- Re-examine Brown's regret-matching+ vs DCFR update sequence in
  `trainer.cpp` — small ordering differences (positive regret clamp
  before vs after discount) can leave a 5-10pp residual at fixed
  iteration count.

**Out of scope for this PR**: Modifying our terminal_utility to mirror
Brown's `(base_pot + opp_contrib)` form. That breaks all internal
exploitability snapshots and `test_exploit_diff` regression-gates, and
the prior 4 audit agents already confirmed the convention is mathematically
equivalent. Only revisit if the action-menu fix leaves a 10pp+ residual.
