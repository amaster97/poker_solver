# PR 8 CHANGELOG drafts

## Draft (a) — Ship as honest perf-infra baseline (v1.1.0)

```markdown
## [1.1.0] - 2026-05-23

PR 8: NEON SIMD kernels + cache-blocked layout primitive + public chance
sampling. Rust-tier perf infrastructure on top of v1.0.0 GA. Kernel wins
are measured (1.55-3.52x at HUNL row widths); end-to-end DCFR wall-clock
is flat because the HashMap-backed infoset store is the bottleneck, not
kernel arithmetic. PR 8.5 will primary-wire `FlatInfosetStore` to unlock
the end-to-end gain. Per the no-extrapolation rule, no end-to-end
multiplier is claimed until per-layer instrumentation backs it. MINOR
bump: additive Rust-tier modules, opt-in `use_pcs` forward-declared in
PR 6, zero public Python API changes.

### Added

- **`crates/cfr_core/src/simd.rs`** (~470 LOC): six ARM NEON 128-bit
  kernels (`discount_regrets`, `discount_strategy_sum`,
  `positive_regrets_and_total`, `normalize`, `update_regret_sum`,
  `update_strategy_sum`) with bit-identical scalar fallbacks.
  `target_arch = "aarch64"` dispatch; `force_scalar` Cargo feature.
  No `vfmaq_f64`: FMA's single-rounding pushed Leduc diff past
  `STRATEGY_ATOL = 1e-4`; two-rounding NEON matches scalar bit-for-bit.
- **`crates/cfr_core/src/layout.rs`** (~190 LOC): `FlatInfosetStore`
  cache-blocked store. Parallel `Vec<f64>` arenas, `BLOCK_SIZE = 64`
  (8 KB at 8-action HUNL width, fits L1d). 32-bit `InfosetId`; per-row
  `RowMeta` in a separate compact array. `row_mut(id)` yields disjoint
  mutable borrows of `(regret, strategy, meta)`. Public + 100%-tested
  but NOT primary-wired; PR 8.5 plumbs `infoset_key -> InfosetId`.
- **`crates/cfr_core/src/pcs.rs`** (~175 LOC): public chance sampling
  per Tammelin 2014. `SamplingStrategy::{Full, PublicChance}` opt-in
  via `HUNLConfig.use_pcs` (forward-declared in PR 6 I6).
  `PcsRng` splitmix64-derived, no new dep.
  `sample_uniform_outcome(rng, k) -> (idx, weight=k)` so
  `E[w*v(c)/k] = E[v(c)]`; negative-control verifies un-reweighted is
  k-biased. `effective_beta(PublicChance, _) = 0.5` silent switch.
- **`crates/cfr_core/benches/dcfr_bench.rs`** (~210 LOC):
  `std::time::Instant` microbench. Per-kernel ns/iter at widths
  2/3/6/8/16/32/64 + Kuhn/Leduc wall-clock. JSON stdout. No `criterion`.

### Changed

- **`dcfr.rs`** — `discount_info`, `get_strategy`, post-recursion update
  route through `simd::`. Public API unchanged.
- **`hunl_solver.rs`** — same SIMD routing; internal `cfr()` gains
  `sampling`/`rng` params; `solve_hunl_postflop` honors `config.use_pcs`.
- **`lib.rs`** — `pub mod {simd, layout, pcs};`; `mod solver -> pub mod`.
- **`Cargo.toml`** — `[[bench]] dcfr_bench` + `[features] force_scalar`.
  No new runtime deps.

### Performance (measured, Apple M-series release build)

- **NEON vs scalar at HUNL widths 6-8:** `positive_regrets_and_total`
  1.85-3.52x; `update_regret_sum` 1.72-2.58x; `discount_strategy_sum`
  1.93-3.25x; wide-row (64) `discount_regrets` 1.55x.
- **End-to-end DCFR (500 iters):** Kuhn 1.00x, Leduc 0.95x. Flat by
  design: SIMD kernels spend <100 ns per Leduc visit; remaining ~7.9 us
  is HashMap lookup, recursive descent, allocations, `state.clone()`.
- **Spec 10x hard gate NOT met end-to-end.** Top kernel 3.52x;
  acceptance bar deferred to PR 8.5.

### Tests

- 6 new `simd::tests` (bit-exact NEON-vs-scalar via `to_bits()`),
  3 new `layout::tests`, 4 new `pcs::tests` (incl. negative control).
- Existing diff gates green: `test_dcfr_diff`, `test_kuhn_dcfr`,
  `test_leduc_dcfr`, `test_leduc_diff`, `test_leduc_intuition`
  (Leduc diff under `STRATEGY_ATOL = 1e-4`).

### Out of scope (deferred to PR 8.5)

- Primary-wire `FlatInfosetStore` (the unlock; 10x gate acceptance).
- HUNL flop/turn end-to-end PCS measurement (blocked on pre-existing
  abstraction-coverage bug in `test_hunl_diff.py`).
- Python tier untouched.

### Internal

- `__version__` -> `1.1.0` (MINOR). Single-agent implementation;
  honest-numbers audit per `docs/pr8_prep/audit_prompt_final.md`.
```

---

## Draft (b) — Hold for primary-wire (internal status note)

```markdown
## [Unreleased] — v1.1.0 work in progress

PR 8 NEON SIMD work is feature-complete on `pr-8-simd-perf` but held
pending `FlatInfosetStore` primary-wire. Both pieces ship together as
v1.1.0 so the milestone delivers the spec's 10x gate end-to-end, not a
kernel-only baseline plus a perf-unlock dot release.

### Done on `pr-8-simd-perf` (held)

- NEON kernels in `simd.rs` (~470 LOC): six kernels, bit-exact scalar
  parity (no FMA), 1.55-3.52x at HUNL widths.
- `FlatInfosetStore` primitive in `layout.rs` (~190 LOC): cache-blocked
  arenas, 32-bit `InfosetId`, disjoint borrows. Public + tested; NOT
  primary-wired.
- Public chance sampling in `pcs.rs` (~175 LOC): splitmix64 PRNG,
  importance-weighted estimator + negative control,
  `effective_beta = 0.5` behind `HUNLConfig.use_pcs`.
- Microbench in `benches/dcfr_bench.rs` (~210 LOC).

### Pending before v1.1.0 ships

- **Primary-wire `FlatInfosetStore` into `DCFRSolver` + `HUNLDcfr`.**
  Inner CFR uses `HashMap<String, InfosetData>`; at Leduc's 8 us/visit,
  ~7.9 us is HashMap. `InfosetId`-keyed traversal is the unlock for the
  10x gate and the single v1.1.0 blocker. Touches every inner CFR
  borrow site; needs fresh diff-test pass (Leduc inside
  `STRATEGY_ATOL = 1e-4`).
- Re-run `dcfr_bench` end-to-end post-rewire; capture honest numbers.

### Why held

Shipping NEON today delivers real kernel wins but flat end-to-end DCFR;
the 10x gate would remain open and require a v1.2.0 closer. Holding ~1
follow-up commit lets v1.1.0 land the gate as a single milestone.
```

---

## Comparison

**Pros of (a) ship-now:** faster cadence (v1.0 -> v1.1 next-day signals
active post-GA pace); honest framing builds trust; `use_pcs` and
`FlatInfosetStore` reach the public API for external consumers now;
smaller blast radius per release.

**Pros of (b) hold-for-primary:** delivers the 10x hard gate in one
milestone, not two; avoids "v1.1 was a letdown" risk; single audit +
diff-test event for kernel + wire-up.

**Recommendation: (a) ship now.** Project cadence is small, focused PRs
with explicit out-of-scope sections (PR 4.5, PR 7, PR 10a, PR 10a.5
each bundle one coherent change). Draft (a) fits. Holding (b) risks
scope creep on a rewire that "touches every inner CFR borrow site" and
would implicitly promise an unmeasured 10x, breaking the
no-extrapolation rule. If the user picks (b), scope the wire-up
explicitly first so "hold for one follow-up" doesn't slip.
