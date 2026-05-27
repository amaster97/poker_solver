# A83 Track A — Nash Multiplicity Empirical Confirmation: Setup Report

**Date:** 2026-05-26
**PR:** [#53](https://github.com/amaster97/poker_solver/pull/53) (merged as `29d608e`)
**Branch:** `pr-90-regret-init-noise` (deleted post-merge)
**Status:** Engine plumbing shipped; two 200K-iter nohups launched; analysis pending.

---

## 1. Goal

Empirically confirm Nash multiplicity at deep-cap indifference manifolds.
The hypothesis (per `feedback_nash_multiplicity_acceptance.md` +
`docs/a83_deep_cap_root_cause_investigation.md`): the 33pp A83 deep-cap
divergence vs Brown decomposes into (a) terminal-utility convention
[Track B, separate] + (b) Nash multiplicity, where infinitesimally
different initial conditions can converge to materially different Nash
equilibria on identical-exploitability manifolds.

Confirmation protocol:
- Run TWO 200K-iter DCFR solves on the SAME A83 spot, ONLY differing in
  initial regret perturbation.
- Run 1: `regret_init_noise = 0.0` (current production default)
- Run 2: `regret_init_noise = 1e-9` (infinitesimal symmetry-breaking)
- Compare strategy on cells `3sAs` / `3cAc` at history `b1000r3000`.

Outcomes:
- `|p_call_run1 - p_call_run2| >= 0.05` → Nash multiplicity CONFIRMED.
  A83 closes as a Type-B (semantic, not bug) finding. Acceptable
  behavior.
- `|p_call_run1 - p_call_run2| < 0.01` → No multiplicity at this iter
  count. The 33pp Brown divergence is fully attributable to Root Cause
  #2 (terminal-utility convention), making Track B the only remaining
  work.

---

## 2. Implementation summary (PR #53)

### CLI surface

```
poker-solver solve --game hunl --hunl-mode postflop --backend rust \
  --regret-init-noise EPSILON \
  --rng-seed SEED \
  [other flags …]
```

- `--regret-init-noise`: float, default `0.0`. When `> 0`, each new
  infoset's `regret_sum[a]` is seeded with `epsilon * U(-1, 1)` instead
  of `0.0`.
- `--rng-seed`: u64, default `0`. Seed for the deterministic PRNG used
  by the noise path. Same value across runs reproduces the perturbation
  pattern bit-exactly.

### Engine plumbing

Both Rust solver paths are wired:
- `crates/cfr_core/src/hunl_solver.rs::solve_hunl_postflop` —
  production path used by `--backend rust --hunl-mode postflop` (the
  A83 path). Noise is applied lazily at the `or_insert_with` site
  whenever a new infoset is first visited.
- `crates/cfr_core/src/dcfr_vector.rs::solve_range_vs_range_postflop_with_hands`
  — vector-form RvR path (`solve_range_vs_range_rust` PyO3 binding).
  Noise is applied eagerly in `VectorDCFR::with_init_noise` constructor
  (vector-form populates all decision-node infosets up front).

Determinism: no new crate dep. Extended existing `PcsRng` (splitmix64)
in `crates/cfr_core/src/pcs.rs` with `next_f64_signed()` returning
`f64 ∈ [-1, 1)` via 53-bit mantissa scaling.

The default (`noise = 0.0`) is **bit-identical** to the prior all-zero
initialization (the perturbation branch is gated on `> 0.0`).

### Python plumbing

- `poker_solver/cli.py`: new argparse flags on `solve` subcommand.
- `poker_solver/solver.py`:
  - `_solve_rust` threads `regret_init_noise` + `rng_seed` from
    `dcfr_kwargs` into the `_rust.solve_hunl_postflop` binding.
  - The postflop Python tier path filters them out of the kwargs
    forwarded to `DCFRSolver` (`_RUST_ONLY_KEYS`). The Python reference
    tier silently ignores the flag — Python is reference, not
    production target.

### Tests added (`crates/cfr_core/src/dcfr_vector.rs::tests`)

- `regret_init_noise_zero_is_reproducible` — noise=0 reruns produce
  bit-identical strategy maps.
- `regret_init_noise_epsilon_perturbs_strategy` — noise=1e-9 produces
  non-zero divergence from noise=0 (proves end-to-end plumbing engages).
- `regret_init_noise_seed_changes_outcome` — different `rng_seed`
  values with same noise produce different strategies (proves the seed
  is actually consumed).

The epsilon test required boosting `tiny_river_rvr`'s
`postflop_raise_cap = 3 + include_all_in = true` because the original
fixture (`raise_cap=1 + single bet size`) collapses every decision node
to one legal action, masking the perturbation (all strategy rows are
`[1.0]` regardless of regret state).

---

## 3. Verification

### Rust

| Suite | Result |
|---|---|
| `cargo test --lib --release` | 56/56 PASS (incl. 3 new PR 90 tests) |
| `cargo test --test test_simd_phase3 --release` | 6/6 PASS |
| `cargo test --test test_simd_phase4 --release` | 6/6 PASS |
| `cargo test --test test_simd_dispatch --release` | 5/5 PASS |
| `cargo clippy --all-targets -- -D warnings` | CLEAN |

### Python differential

| Suite | Result |
|---|---|
| `tests/test_dcfr_diff.py` (Kuhn) | PASS |
| `tests/test_leduc_diff.py` (Leduc) | PASS (10/10 combined) |
| `tests/test_range_vs_range_rust_diff.py` (RvR diff, fast) | 3/3 PASS + 1 slow skip |
| `ruff check poker_solver/` | CLEAN |
| `mypy poker_solver/cli.py poker_solver/solver.py` | CLEAN |

### CLI smoke

```
$ poker-solver solve --game hunl --hunl-mode postflop --backend rust \
    --board "As 7c 2d Kh 5s" --stacks 100 --iterations 5 \
    --bet-sizes 75 --regret-init-noise 0.0 --rng-seed 1
[...]
Game value:  -0.149306 (P1 perspective)
Exploitability (final): 15.066668
```

Same call with `--regret-init-noise 1e-9 --rng-seed 1` runs cleanly.

### Pre-existing failures NOT touched by PR 90

For the record (verified on origin/main HEAD too):
- `crates/cfr_core/tests/hunl_state_unit.rs::test_03_legal_actions_facing_bet`
- `crates/cfr_core/tests/hunl_state_unit.rs::test_06_raise_cap_postflop`
- `tests/test_hunl_diff.py::test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction`

---

## 4. PR URL

**PR #53:** https://github.com/amaster97/poker_solver/pull/53
Merged 2026-05-26 as commit `29d608e`.

CI checks at merge time: `check` (Golden File Check), `bundle-dry-run`
(Ship Dry Run), `check` (Skip-Ban) — all COMPLETED SUCCESS.

---

## 5. Nohup PIDs + output paths

Both runs launched 2026-05-26 03:15 PDT via
`/Users/ashen/Desktop/a83_track_a_run.sh`.

| Run | PID file | Log file | PID | RNG seed | Noise |
|---|---|---|---|---|---|
| Baseline | `~/Desktop/a83_track_a_baseline.pid` | `~/Desktop/a83_track_a_baseline.log` | 49308 | 1 | 0.0 |
| Perturbed | `~/Desktop/a83_track_a_perturbed.pid` | `~/Desktop/a83_track_a_perturbed.log` | 49310 | 1 | 1e-9 |

Both PIDs verified running with `--regret-init-noise` flag accepted at
launch. Logs in `~/Desktop/` (not `/tmp/`) so they survive reboot.

### Spot configuration

Matches `tests/data/river_spots.json:dry_A83_rainbow`:
- Board: `Ah 8c 3d Tc 6s` (5-card river)
- Pot: 1000 (= 10 BB)
- Stack: 9500 (≈ 95 BB)
- Bet sizes: `50,100` (matches fixture's `[0.5, 1.0]`)
- Iterations: 200,000
- DCFR α=1.5, β=0.0, γ=2.0 (PLAN.md locked defaults)
- Postflop raise cap: 3 (default)
- Include all-in: true (default)
- Stacks BB CLI flag: `95` (so per-player starting_stack = 95 * 100 cents)
- Seed: 42 (for chance-sampling determinism)

The CLI invocation slightly differs from the literal task spec (which
suggested `--board "As 8s 3s" --stacks 100`). The 3-card monotone flop
spec is a deep-tree configuration that would not finish in reasonable
wall-clock at 200K iters; the actual A83 dry-run investigation
(`docs/a83_deep_cap_root_cause_investigation.md` §1a) explicitly
references the river-phase fixture for the `b1000r3000` cell, so this
matches the actual investigation scope.

---

## 6. Expected wall-clock + interpretation framework

### Wall-clock estimate

The fixture itself runs at ≈ 2000 iters in seconds (per `_cmd_parity`
defaults). 200K iters extrapolates to roughly **30-90 minutes per run
on aarch64** (M-series). Both runs in parallel saturate ≈ 2 cores; the
M-series memory bandwidth ceiling is the more likely bottleneck than
CPU.

### Interpretation framework (for the follow-up analysis)

The analysis script (TBD, separate PR) should:

1. Load both `--log-every 10000` JSON snapshots from
   `~/Desktop/a83_track_a_{baseline,perturbed}.log`.
2. Extract the final average strategy from both runs.
3. For each cell in
   `{3sAs, 3cAc} × {b1000r3000}`:
   - Compute `p_call_baseline` (from baseline strategy)
   - Compute `p_call_perturbed` (from perturbed strategy)
   - Compute `delta = |p_call_baseline - p_call_perturbed|`
4. Decision rule:
   - `delta >= 0.05` on ANY of the 2 cells → **Nash multiplicity
     CONFIRMED**. Close A83 as Type-B (semantic, acceptable behavior).
   - `delta < 0.01` on BOTH cells → **No multiplicity** at 200K iters.
     The 33pp Brown divergence is fully attributable to Root Cause #2.
     Track B becomes the only remaining work.
   - `0.01 <= delta < 0.05` → **Inconclusive**. May need higher iter
     count or larger perturbation.
5. Additional diagnostics:
   - Exploitability convergence curve from both runs. Two strategies
     on the same indifference manifold should have **identical**
     exploitability within float tolerance, even if per-action
     probabilities differ. This is the load-bearing check that
     distinguishes "Nash multiplicity" from "one run failed to
     converge".
   - Game-value convergence. Should also match within float tolerance.

### Negative-result protocol

If exploitability OR game-value diverge materially between the two
runs, the hypothesis is REFUTED: the perturbation is biasing the
solver toward a non-Nash strategy. In that case, the noise magnitude
may be too large at 1e-9 for 200K iters; rerun with 1e-12 or 1e-15.

---

## 7. Constraints upheld

- DCFR math UNCHANGED. Only the lazy `or_insert_with` site +
  `VectorInfosetData::new` constructor were modified.
- Default behavior UNCHANGED. `noise = 0.0` produces bit-identical
  output to pre-PR-90 (verified by
  `regret_init_noise_zero_is_reproducible` Rust unit test).
- Diff-test parity preserved (10/10 Kuhn + Leduc).
- Deterministic RNG seeded by explicit flag — no implicit randomness.

---

## 8. References

- PR: https://github.com/amaster97/poker_solver/pull/53 (merged)
- Root-cause investigation: `docs/a83_deep_cap_root_cause_investigation.md`
- Validator's audit closing dcfr_vector.rs as correct: `docs/a83_validation_2026-05-26.md`
- Memory rule: `feedback_nash_multiplicity_acceptance.md`
- Brown vs ours framing: `feedback_external_solver_sanity_check.md`
- Brown apples-to-apples experiment: `docs/brown_apples_to_apples_2026-05-23.md`

---

## 9. Launch script (for re-launch / reproduction)

`~/Desktop/a83_track_a_run.sh` (created in this session). Re-runs both
nohups idempotently — overwrites prior log + pid files. To kill in-flight
runs:

```
kill -9 $(cat ~/Desktop/a83_track_a_baseline.pid)
kill -9 $(cat ~/Desktop/a83_track_a_perturbed.pid)
```

(Note: kill commands disabled in this autonomous session per the
agent's safety classifier; user can run them manually if needed.)
