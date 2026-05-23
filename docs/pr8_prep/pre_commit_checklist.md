# PR 8 pre-commit checklist

**Status:** Gate before staging the PR 8 commit on `pr-8-neon-simd-pcs`.
**Date:** 2026-05-22
**Scope:** Local verification — run each gate, mark PASS/FAIL, fix any FAIL before staging.

Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_prompt_final.md`
Pre-audit risk forecast: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/audit_preprep.md`
Commit message draft: `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/commit_message_draft.md`

---

## 1. Build gates (Rust side)

### 1.1 cargo build clean (NEON intrinsics compile, no manual RUSTFLAGS)
```
cargo build --release --package cfr_core --target aarch64-apple-darwin
```
- [ ] PASS — clean compile, no warnings, no manual `RUSTFLAGS` needed (compile-time NEON guard per spec §10 risk 1).
- FAIL action: if `simd.rs` fails to compile without RUSTFLAGS, the `#[cfg(target_arch = "aarch64")]` guard or `static_assertions::const_assert!` is missing — patch `simd.rs` before commit.

### 1.2 cargo test clean (all 3 layers)
```
cargo test --package cfr_core --all-targets --release
```
- [ ] PASS — PR 1-7 Rust tests + new `test_simd` / `test_layout` / `test_pcs` all green.
- Expected new-test count: ~30 (audit_prompt §1 enumeration).
- Critical canaries:
  - `test_simd::bit_exact_parity_neon_vs_scalar` (Layer A — MUST pass with `to_bits()` equality).
  - `test_simd::nan_propagation_neon` + `test_simd::signed_zero_preservation_neon`.
  - `test_layout::kuhn_hashmap_vs_flat_parity_1e_minus_12` + `test_layout::leduc_hashmap_vs_flat_parity_1e_minus_12`.
  - `test_pcs::importance_weight_required_or_diverges` (negative control — MUST FAIL when `w=K` removed; the test asserts the failure).
  - `test_pcs::seed_7_first_100_cards_match_fixture` (cross-platform repro).
  - `test_pcs::use_pcs_true_sets_beta_half`.

### 1.3 cargo clippy clean
```
cargo clippy --package cfr_core --all-targets -- -D warnings
```
- [ ] clippy clean across all targets.
- [ ] `#[deny(unsafe_op_in_unsafe_fn)]` enforced on `simd.rs` module per agent_a_prompt §193-200.
- [ ] No `#[allow(clippy::*)]` overrides creeping into new files.

### 1.4 `unsafe` discipline grep (manual gate, audit area 4)
```
grep -nE 'unsafe[[:space:]]*\{' crates/cfr_core/src/*.rs
```
- [ ] Every hit is in `simd.rs` ONLY (ZERO matches in `layout.rs`, `pcs.rs`, `dcfr.rs`, `hunl_solver.rs`, `lib.rs`, `solver.rs`).
- [ ] Every hit has a preceding `// SAFETY: ...` non-trivial comment (NOT `// SAFETY: trust me`); the comment names alignment + length invariant.
- FAIL action: any naked `unsafe { ... }` without SAFETY → must-fix per audit prompt area 4; patch the comment before commit.

### 1.5 Rayon non-goal grep (manual gate, audit area 11)
```
grep -n 'rayon' crates/cfr_core/Cargo.toml crates/cfr_core/src/*.rs
```
- [ ] ZERO matches across `Cargo.toml` and all `.rs` files.
- FAIL action: any `rayon` reference → must-fix (spec §1 non-goal + §10 risk 8).

---

## 2. Build gates (Python side)

### 2.1 Python tier still green (PR 6 carry-over)
```
pytest -m "not slow and not very_slow" --tb=line --timeout=120
```
- [ ] All pass / skip; 0 fail, 0 error, 0 timeout.
- [ ] PR 1-7 regression: Kuhn + Leduc + HUNL Python + HUNL Rust + river-diff harness all green.
- [ ] PR 8 new tests in `tests/test_pr8_convergence.py` PASS (5 tests).

### 2.2 ruff + black + mypy strict on Python changes
```
ruff check poker_solver/hunl.py tests/test_pr8_convergence.py
black --check poker_solver/hunl.py tests/test_pr8_convergence.py
mypy --strict poker_solver/hunl.py
```
- [ ] All three return exit 0.
- [ ] `HUNLConfig.use_pcs: bool = False` field type-checks (mypy strict).

---

## 3. Correctness gates (cross-tier parity)

### 3.1 Layer A bit-exact SIMD/scalar parity (audit area 2 — HIGH-PROB)
- [ ] `test_simd.rs` uses `result_simd[i].to_bits() == result_scalar[i].to_bits()` — NOT `abs() < EPS`, NOT `approx_eq!`.
- [ ] Edge values covered: `0.0`, `-0.0`, `f64::NAN`, `f64::INFINITY`, `f64::NEG_INFINITY`, smallest denormal, 1000-trial seeded random.
- [ ] FMA `vfmaq_f64` ULP≤1 allowance scoped to the FMA op only (not widened to non-FMA ops).
- FAIL action: silent tolerance relaxation → must-fix; patch `test_simd.rs` before commit.

### 3.2 Layer B layout parity at 1e-12 (audit area 6)
- [ ] `test_layout.rs` runs Kuhn (12 infosets, 1K iter) + Leduc (288 infosets, 10K iter) on both HashMap-backed and `FlatInfosetStore`-backed DCFR.
- [ ] Per-infoset average strategy probability match within `1e-12` literal (NOT `1e-6`, NOT `1e-9`).
- [ ] HashMap path REMOVED in same PR (verify via `grep -n 'HashMap' crates/cfr_core/src/dcfr.rs` — should not appear on the regret/strategy storage path).
- [ ] `const BLOCK_SIZE: usize = 64` in `layout.rs` (not 32, not 128).

### 3.3 Layer C PCS variance + importance weight (audit area 3 — HIGH-PROB)
- [ ] `test_pcs.rs` applies importance weight `w = K` (K=44 turn, K=43 river) at every chance node — `grep -n 'w \* ' crates/cfr_core/src/pcs.rs` should show the multiplication.
- [ ] Negative-control `test_pcs::importance_weight_required_or_diverges` removes the weight and ASSERTS divergence (MUST FAIL without weight; passes by failing).
- [ ] Per-action MAE thresholds: mean < `5e-3`, max < `2e-2`, across 5 seeds; per-spot cluster < `1e-3 * pot`.
- [ ] β-switch confirmed: `use_pcs=true → solver.beta == 0.5`; `use_pcs=false → solver.beta == 0.0`.

### 3.4 Layer D Python end-to-end (audit area 7)
- [ ] `tests/test_pr8_convergence.py` runs the existing river-spot test with the optimized Rust solver (SIMD + layout, PCS off by default).
- [ ] Tolerance literal == `5e-3` in fixture + harness + any parametrized cases (NO `1e-2`, NO `5e-2` — silent relaxation is must-fix).
- [ ] No tolerances weaker than PR 6's existing Python↔Rust diff test.

### 3.5 PR 6 river fixture still bit-exact (regression)
```
pytest tests/test_hunl_diff.py -v --tb=line
```
- [ ] `test_hunl_river_subgame_diff_python_vs_rust` still passes BIT-EXACTLY (PR 6 baseline; SIMD + layout swap must not introduce drift).
- FAIL action: if bit-exact regressed to merely-5e-3, audit before commit — drift may indicate hash-seed leakage from layout swap or summation-order change in SIMD reduction.

---

## 4. Performance gate (audit area 8 — HIGH-PROB, 30% NOT-READY)

### 4.1 Baseline-first commit ordering (audit area 1 — HIGH-PROB)
```
git log integration..HEAD --oneline | head -5
```
- [ ] First commit (oldest) is `bench: capture pre-PR-8 baseline ...` containing ONLY `benches/baseline.json` (no `layout.rs`, no `dcfr.rs`, no `simd.rs` deltas).
- [ ] Header metadata in `baseline.json`: machine identifier, `sw_vers -productVersion`, `rustc --version`, `git rev-parse HEAD` (PR 6 tip — NOT PR 8 tip), date, criterion version, warm_up=5, samples=20.
- FAIL action: if baseline bundled with refactor → split-commit before push (must-fix per audit area 1).

### 4.2 10x hard gate on `hunl_simple_flop` (primary) + per-layer breakdown
```
cargo bench --release --package cfr_core
```
- [ ] `hunl_simple_flop` (64/32/16 buckets, 1K iter) measured >=10x speedup vs `benches/baseline.json`.
- [ ] Per-layer breakdown (mandatory per memory `feedback_no_extrapolate`):
  - [ ] SIMD microbench >=3x over scalar (NEON inner loop vs scalar f64).
  - [ ] Layout `FlatInfosetStore` vs HashMap >=3x.
  - [ ] PCS vs full enumeration >=3x.
- [ ] Stddev <10% mean (M-series typically <8%; if >10%, re-run).
- [ ] Stretch `hunl_standard_flop` (256/128/64) approaches ~50x (advisory; gate is `hunl_simple_flop`).

**FAIL action:** if cumulative <10x OR any per-layer <3x → spec §11 Decision 13 fallback: 8a (SIMD + layout, ship if >=10x without PCS) / 8b (PCS deferred to subsequent PR). Re-bench post-fallback before commit. Do NOT commit with a stale 10x claim.

### 4.3 Criterion methodology gate (audit area 9)
```
grep -nE 'iter_(with_setup|batched)' benches/cfr_bench.rs
```
- [ ] Non-zero matches — every spot uses `iter_with_setup` or `iter_batched` to exclude tree-build / alloc from per-iter cost.
- [ ] Bucket counts in `cfr_bench.rs` for spot 3 == `64/32/16` (NOT `50/64` — 2026-05-21 spec amendment).
- FAIL action: raw `iter` without setup separation → 10x claim invalidated → must-fix.

---

## 5. License + attribution gates (audit area 12)

- [ ] `simd.rs` module docstring opens with the spec §3 template attribution: cites Apple NEON intrinsics docs (primary reference); cites postflop-solver's `chunks_exact + remainder` pattern as AGPL read-only inspiration with explicit "implementation derived from scratch. No code copied." disclaimer.
- [ ] `layout.rs` module docstring cites postflop-solver's flat-storage PATTERN (AGPL read-only inspiration only); names Mike Acton's data-oriented-design talk + project-internal references; carries the "NEVER copy from references/code/postflop-solver (AGPL) or references/code/TexasSolver (AGPL)" disclaimer.
- [ ] `pcs.rs` module docstring cites the PCS paper (Lanctot et al. NIPS 2009) + project-internal `dcfr.py` (MIT).
- [ ] AGPL grep on new `.rs` files: no verbatim postflop-solver patterns.
- [ ] `check_pr.sh` license audit clean: `criterion` (Apache-2.0/MIT dual), `rand = "0.8.5"` (Apache-2.0/MIT dual, pinned), `rand_chacha = "0.3.1"` (Apache-2.0/MIT dual, pinned). No AGPL/GPL deps.

---

## 6. Branch + integration gates

### 6.1 Branch identity + integration sync
- [ ] Current branch: `pr-8-neon-simd-pcs` (`git branch --show-current`).
- [ ] Integration tip: post-PR-7 `v0.5.1` SHA (verify with `git log integration --oneline -1`).
- [ ] `pr-8-neon-simd-pcs` is branched from / rebased onto this tip — no silent divergence.

### 6.2 No accidental edits outside PR 8 scope
```
git diff integration..HEAD --stat
```
- [ ] Expected file set:
  - 3 new Rust source: `crates/cfr_core/src/{simd,layout,pcs}.rs`
  - 3 new Rust integration tests: `tests/test_{simd,layout,pcs}.rs`
  - 1 new Python E2E test: `tests/test_pr8_convergence.py`
  - 1 new Criterion bench: `benches/cfr_bench.rs`
  - 1 new baseline data file (separate commit): `benches/baseline.json`
  - 5 modified Rust: `crates/cfr_core/src/{dcfr,hunl_solver,lib,solver}.rs`, `crates/cfr_core/Cargo.toml`
  - 1 modified Python: `poker_solver/hunl.py` (use_pcs field)
  - 4 ride-along (version bump bundle): `poker_solver/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`, `Cargo.lock`
- [ ] No edits to PR 1-7 fixtures, PR 4 abstraction artifacts, PR 5/6 hunl_solver.py orchestration, PR 7 parity wrapper.

---

## 7. Audit gate

- [ ] **G-audit — PR 8 audit verdict.** `docs/pr8_prep/audit_report.md` exists and carries verdict **READY** or **READY-WITH-PATCHES**, NOT **NOT-READY**.
  - READY → proceed to commit pipeline.
  - READY-WITH-PATCHES → apply patches in-place, re-run §1-§6 on patched code, then commit.
  - NOT-READY → abort commit; escalate to user with audit must-fix list. **Most likely NOT-READY trigger:** 10x gate fails on `hunl_simple_flop` → spec §11 Decision 13 8a/8b split (drop PCS to subsequent PR; ship SIMD + layout alone if those clear 10x).
- [ ] All 14 audit focus areas marked "Looks good" or have a resolved patch.

---

## 8. Biggest gates (load-bearing)

1. **§4.2 — 10x speedup gate.** Load-bearing for the entire PR 8 narrative; if it fails, the commit message + version bump are stale. Re-bench and re-draft before any commit.
2. **§3.1 — Layer A bit-exact SIMD parity.** Silent float-behavior divergence is a cross-platform reproducibility break.
3. **§3.3 — PCS importance weighting + negative control.** Missing `w=K` → biased estimator → average strategy converges to wrong fixed point at large iters (small-iter "passes" mask the bug).
4. **§4.1 — Baseline-first commit ordering.** If baseline is bundled with refactor in one SHA, the 10x measurement is contaminated → claim invalid → must-fix.

---

## 9. Commit firing order

Once all gates green:
1. `git status` — confirm clean working tree on `pr-8-neon-simd-pcs`.
2. `git log integration..HEAD --oneline` — confirm 2-commit sequence (baseline first, implementation second).
3. `git diff --cached --stat` — final file-set sanity (per §6.2).
4. `git commit -F docs/pr8_prep/commit_message_draft.md` (or paste via HEREDOC per memory `git-safety protocol`).
5. `git status` — verify commit success.
6. DO NOT push yet — wait for user OK on the commit + audit bundle.

---

## 10. Constraints

- **DO NOT commit yet.** This checklist is gate-only.
- **DO NOT skip hooks** (`--no-verify`) under any condition.
- **DO NOT amend** — PR 8 is a fresh commit on its own feature branch (per `feedback_pr_branches`).
- **DO NOT bundle baseline + refactor** into one commit (per audit area 1 — must-fix if violated).
- Reference audit prompt + risk forecast by absolute path in the commit message body (already done in `commit_message_draft.md`).
- If 10x gate fails → spec §11 Decision 13 fallback (8a/8b split); do NOT silently relax to <10x.

When all gates above are PASS, proceed to stage + commit per `commit_pipeline.md`.
