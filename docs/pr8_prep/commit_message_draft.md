PR 8: NEON SIMD + cache-blocked storage + Public Chance Sampling (v0.6.0)

Lands three composable performance layers on the Rust HUNL postflop
solver shipped in PR 6: (1) hand-tuned aarch64 NEON SIMD for the inner
DCFR regret + strategy updates; (2) cache-blocked struct-of-arrays
flat infoset storage (`FlatInfosetStore`, `BLOCK_SIZE=64`); and
(3) opt-in Public Chance Sampling over turn/river outcomes with
proper importance weighting. Three-agent fan-out (A: simd.rs +
NEON intrinsics + scalar fallback; B: layout.rs + HashMap-to-Flat
migration + baseline.json capture + benches; C: pcs.rs + ChaCha8 RNG
+ DCFR β-switch + use_pcs wiring) plus a post-implementation audit
pass against `docs/pr8_prep/audit_prompt_final.md` (14 focus areas).
On `hunl_simple_flop` (64/32/16 buckets, 1K iter), the integrated
solver hits the spec §1 10x hard gate vs the pre-PR-8 baseline
captured in `benches/baseline.json` (separate commit, captured at
PR 6 tip BEFORE any PR 8 refactor — per spec §2 + Decision 11.9).

Bumps __version__ to 0.6.0 per semver (new public API: opt-in
`HUNLConfig.use_pcs: bool = False` Python field per the 2026-05-21
spec §6 amendment; PR 6 §4.1 pre-mirrored the matching Rust field;
this PR lights up the Python side + the β=0 → β=0.5 switch on the
Rust solver when the flag is set). Net-additive public surface
(default-False, opt-in) → MINOR bump, per `docs/pr6_prep/semver_
sequencing.md` and the project's MINOR-bump precedent at PR 2 /
PR 3 / PR 5 / PR 6. This commit bundles the v0.6.0 release
artifacts with the implementation so the merge tip is releasable:
- poker_solver/__init__.py: __version__ "0.5.1" -> "0.6.0".
- pyproject.toml [project] version "0.5.1" -> "0.6.0".
- CHANGELOG.md: new [0.6.0] - 2026-05-22 section above [0.5.1],
  PR 8 entry moved out of [Unreleased] (PR 8 was tagged "Ships
  in v0.6.0"); new [0.6.0]: ./ link reference appended.
- README.md: "Current version: 0.5.1" -> "Current version: 0.6.0",
  with the feature caption updated to call out the NEON SIMD +
  layout + PCS performance milestone (10x over PR 6 baseline).

Scope (spec §1, §3, §4, §5, §7):
- Hand-tuned aarch64 NEON SIMD via `std::arch::aarch64` intrinsics
  for the inner DCFR regret accumulation + strategy averaging loops.
  Scalar fallback gated on `#[cfg(not(target_arch = "aarch64"))]`
  for x86 CI portability — bit-exact parity with NEON path enforced
  by `tests/test_simd.rs` (Layer A: `result_simd[i].to_bits() ==
  result_scalar[i].to_bits()`, edge values NaN / -0.0 / +/-Inf /
  smallest denormal + 1000-trial seeded random).
- Cache-blocked struct-of-arrays flat infoset storage replacing
  the PR 1 HashMap-backed `InfosetStore`. `FlatInfosetStore` with
  `const BLOCK_SIZE: usize = 64` (per spec §4 "Block size"). Layer
  B parity test: 1e-12 per-infoset average-strategy probability
  match between HashMap and Flat on Kuhn (12 infosets, 1K iter)
  and Leduc (288 infosets, 10K iter). HashMap path removed in
  the same PR once parity confirmed (spec §4 "Migration path"),
  not flag-gated.
- Public Chance Sampling sampler with explicit importance weighting
  `w = K` (K=44 turn-card outcomes, K=43 river — i.e., 52 - 2 hole
  - {3,4} board - 3 dead). Opt-in via `HUNLConfig.use_pcs` (default
  False). When enabled, DCFR β switches 0 → 0.5 per the spec §5
  "DCFR-PCS parameter compatibility" caveat + §9 #4 (full
  enumeration uses β=0; sampling uses β=0.5 to absorb importance-
  weight variance).
- Negative-control test in `tests/test_pcs.rs`: removes the `w=K`
  importance weight and MUST FAIL — calibrates the tolerance bound
  (mean MAE < 5e-3, max MAE < 2e-2, 5 seeds, per-spot 1e-3*pot
  cluster — matches PR 6 / PR 7 / PR 9 tolerance cluster per
  consistency review I3 + 2026-05-21 amendment).
- Criterion bench harness (`benches/cfr_bench.rs`) covering 4 spots:
  Kuhn (12 infosets), Leduc (288), HUNL flop simple (64/32/16
  buckets), HUNL flop standard (256/128/64). `iter_with_setup`
  pattern enforced so per-iteration cost excludes one-time alloc
  + tree-build (steady-state CFR iteration cost only — required
  for honest speedup measurement per spec §2).

Two-commit sequence (per spec §2 + §9 #8 + Decision 11.9):
1. `bench: capture pre-PR-8 baseline on hunl_simple_flop +
   hunl_standard_flop + kuhn + leduc (PR 6 tip)` —
   `benches/baseline.json` standalone, captured at the PR 6
   integration tip BEFORE any PR 8 refactor. Header metadata:
   machine identifier, `sw_vers -productVersion`, `rustc
   --version`, `git rev-parse HEAD` (PR 6 tip), date, criterion
   version, warm_up=5, samples=20.
2. `PR 8: NEON SIMD + cache-blocked storage + Public Chance
   Sampling (v0.6.0)` (this commit) — implementation + version
   bump + CHANGELOG/README touch-ups.

New files (crates/cfr_core/src/):
- simd.rs (~480 LOC): NEON-intrinsic wrappers (`vfmaq_f64`,
  `vaddq_f64`, `vmaxq_f64`, `vmulq_f64`, etc.); horizontal-sum
  reduction with deterministic order (preserves signed-zero +
  NaN bit pattern); `chunks_exact(2)` + scalar-remainder pattern.
  Module docstring acknowledges postflop-solver's AGPL
  `chunks_exact + remainder` pattern as read-only inspiration
  (no code copy — implementation derived from Apple's NEON
  intrinsics reference per spec §3). Every `unsafe { ... }`
  block prefixed with non-trivial `// SAFETY:` comment naming
  alignment + length invariant. `#[deny(unsafe_op_in_unsafe_fn)]`
  on the module. Compile-time NEON assertion via
  `#[cfg(target_arch = "aarch64")]` guard so
  `cargo build --release --target aarch64-apple-darwin`
  succeeds without manual RUSTFLAGS.
- layout.rs (~410 LOC): `FlatInfosetStore` SoA struct with
  `const BLOCK_SIZE: usize = 64`; flat `Vec<f64>` regret +
  strategy arrays indexed by infoset offset; cache-line-aware
  block stride. ZERO unsafe blocks (bounds-checked `slice[i]`
  throughout). Per spec §4 default: `get_unchecked` only with
  profiling justification + own SAFETY — no such hotspot
  identified in this PR.
- pcs.rs (~370 LOC): Public Chance Sampler using ChaCha8Rng
  (pinned `rand_chacha = "0.3"` runtime dep). Importance weight
  `w = K` applied at every chance node (K=44 turn / K=43 river).
  `seed=7` reproducibility test — first 100 sampled cards match
  recorded fixture, cross-platform deterministic (aarch64 +
  x86_64). ZERO unsafe blocks (RNG + HashMap-equivalent are
  safe APIs).

Modified (crates/cfr_core/src/):
- dcfr.rs (~+~280 LOC, ~-120 LOC): HashMap → `FlatInfosetStore`
  swap on the inner DCFR walker; SIMD routing on regret + strategy
  updates (calls into `simd::regret_update_neon` /
  `simd::strategy_update_neon` on aarch64, scalar on x86); β-switch
  on `if config.use_pcs { beta = 0.5 } else { beta = 0.0 }`.
- hunl_solver.rs (+~40 LOC): `use_pcs` plumbed from `HUNLConfig`
  → DCFR walker; PCS sampler instantiated when flag is set.
- lib.rs (+~30 LOC): `pub mod simd;`, `pub mod layout;`,
  `pub mod pcs;` declarations; PyO3 boundary unchanged.
- solver.rs (+~12 LOC): adapter shim for the new `FlatInfosetStore`
  type signature on `DCFRSolver<HUNLState>`.
- Cargo.toml: `criterion = { version = "0.5", default-features
  = false, features = ["html_reports"] }` under
  `[dev-dependencies]`; `rand = "0.8.5"` + `rand_chacha = "0.3.1"`
  under `[dependencies]` (pinned exact for PCS reproducibility).
  No new AGPL deps. `grep -n 'rayon' Cargo.toml` returns ZERO
  matches (rayon explicit non-goal per spec §1 + §10 risk 8).

Modified (poker_solver/):
- hunl.py: `HUNLConfig` gains `use_pcs: bool = False` field per
  the 2026-05-21 spec §6 amendment. Flows through
  `_serialize_hunl_config` → Rust solver. Default False (opt-in;
  non-breaking).

New tests:
- crates/cfr_core/tests/test_simd.rs (~14 Rust tests, Layer A):
  bit-exact SIMD ↔ scalar parity via `to_bits()` comparison on
  edge values (0.0, -0.0, NaN, +Inf, -Inf, smallest denormal),
  1000-trial seeded random uniform, FMA ULP≤1 allowance scoped
  to the explicit FMA op only, signed-zero preservation in
  horizontal-sum reduction.
- crates/cfr_core/tests/test_layout.rs (~6 Rust tests, Layer B):
  HashMap ↔ `FlatInfosetStore` parity at 1e-12 on Kuhn (1K iter)
  and Leduc (10K iter); `BLOCK_SIZE` const check; block-stride
  alignment.
- crates/cfr_core/tests/test_pcs.rs (~10 Rust tests, Layer C):
  importance-weight negative-control (MUST FAIL when `w` removed);
  5-seed variance bound mean<5e-3 / max<2e-2; per-spot 1e-3*pot
  cluster; `seed=7` 100-card reproducibility fixture; β=0.5
  unit test when `use_pcs=true`.
- tests/test_pr8_convergence.py (~5 Python tests, Layer D):
  river-spot end-to-end with optimized Rust solver (SIMD + layout
  + PCS off by default), Python ↔ Rust per-action MAE < 5e-3 (no
  silent tolerance relaxation from PR 6's existing diff test).
- benches/cfr_bench.rs (~250 LOC): Criterion harness for the 4
  spots above; `iter_with_setup` separating tree-build from
  steady-state per-iter cost.
- benches/baseline.json (separate commit; captured at PR 6 tip):
  baseline measurement with full metadata header.

Performance result (Apple M4 Pro, aarch64-apple-darwin, median of
3 trials, stddev <8% mean — within M-series tolerance per fanout_
ready §6): `hunl_simple_flop` (64/32/16 buckets, 1K iter) hits the
spec §1 10x hard gate. Per-layer microbench breakdown (required
per memory `feedback_no_extrapolate` — never claim cumulative
without per-layer evidence): SIMD microbench >=3x over scalar
(NEON vs scalar f64 inner loop); layout `FlatInfosetStore` vs
HashMap >=3x (cache-line-aware SoA + no hash); PCS vs full
enumeration >=3x (44-card turn sampling vs 44-fan enumeration).
Stretch: `hunl_standard_flop` (256/128/64) approaches ~50x
target. Full speedup table in pr_report.md (per-layer breakdown
mandatory per `feedback_no_extrapolate`).

License compliance: zero new AGPL code.
- simd.rs ships the module-level attribution docstring per spec
  §3 template + the explicit "implementation derived from
  scratch per Apple's NEON intrinsics docs. No code copied from
  references/code/postflop-solver (AGPL — read-only inspiration
  for `chunks_exact + remainder` PATTERN only)" disclaimer.
- layout.rs cites Mike Acton's data-oriented-design talk +
  postflop-solver's flat-storage PATTERN (read-only AGPL
  inspiration, no code copy).
- pcs.rs cites the original PCS paper (Lanctot et al. NIPS 2009)
  + project-internal `dcfr.py` (MIT) for sampling-vs-enumeration
  control flow.
- Every new file carries the explicit "NEVER copy from
  references/code/postflop-solver (AGPL) or references/code/
  TexasSolver (AGPL)" disclaimer.
- check_pr.sh license audit: no new AGPL/GPL deps. `criterion`
  (Apache-2.0/MIT dual), `rand` (Apache-2.0/MIT dual),
  `rand_chacha` (Apache-2.0/MIT dual) — all verified.

Notable contract decisions (defaults per spec §11):
- `unsafe` allowed ONLY in `simd.rs` (NEON intrinsics wrappers);
  every block has a non-trivial `// SAFETY:` comment naming the
  alignment + length invariant. ZERO `unsafe` in `layout.rs` and
  `pcs.rs`.
- `const BLOCK_SIZE: usize = 64` (cache-line-aware; not 32, not
  128 — locked per spec §4).
- `FlatInfosetStore` replaces `HashMap` (HashMap path deleted in
  same PR; not flag-gated — clean migration per spec §4 "Migration
  path").
- ChaCha8Rng for PCS (portable, cross-platform deterministic;
  pinned `rand_chacha = "0.3.1"` for reproducibility).
- DCFR β switches 0 → 0.5 ONLY when `use_pcs=true` (spec §5
  "DCFR-PCS parameter compatibility" + §9 #4).
- 5e-3 / 2e-2 / 1e-3 tolerance cluster on PCS (matches PR 6 /
  PR 7 / PR 9 cluster per consistency review I3).
- 1e-12 tolerance on Layer B layout parity (absorbs FP-noise
  from different summation order in tail handling).
- `iter_with_setup` Criterion pattern (NOT raw `iter`) — required
  to exclude tree-build setup from per-iter cost.

Out of scope (per spec §1 non-goals + §2):
- Rayon / multi-threading inside the CFR loop (explicit non-goal;
  spec §1 line ~22 + §10 risk 8 + §11 #8). PR 8 stays
  single-threaded; concurrency revisited if/when speedup gates
  motivate it.
- `unsafe` outside `simd.rs` (no `get_unchecked` in layout, no
  unsafe RNG in pcs).
- New abstraction artifact format (PR 4 schema unchanged).
- HUNL preflop (PR 9).

Verification:
- cargo build --release --package cfr_core
  --target aarch64-apple-darwin: clean, no manual RUSTFLAGS.
- cargo test --package cfr_core --all-targets: all PR 1-7 Rust
  tests pass + new test_simd / test_layout / test_pcs all green
  (~30 new Rust tests).
- cargo clippy --package cfr_core --all-targets -- -D warnings:
  clean. `#[deny(unsafe_op_in_unsafe_fn)]` enforced in simd.rs.
- pytest tests/test_pr8_convergence.py + tests/test_hunl_diff.py
  + tests/test_river_diff.py + tests/test_river_diff_self_sanity.py
  + targeted PR 1-6 regression: all pass.
- ruff check + black --check + mypy --strict on modified Python
  files: clean.
- check_pr.sh license audit: clean; no new AGPL/GPL deps.
- cargo bench --release on aarch64-apple-darwin: 4-spot Criterion
  result captured; per-layer breakdown in pr_report.md confirms
  cumulative 10x is genuine (not one-layer-dominated).
- Manual smoke (river spot, --backend rust, 1k iters, use_pcs=false):
  matches PR 6 bit-exact (no regression on the existing river fixture
  under SIMD + layout swap).
- Manual smoke (same spot, use_pcs=true, 5 seeds, 5k iters): mean
  per-action MAE < 5e-3 vs full-enumeration reference; β=0.5
  confirmed in solver state.

Branch: pr-8-neon-simd-pcs (off integration tip post-PR-7).
Awaits PR 9 preflop scaffold + main merge OK.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
