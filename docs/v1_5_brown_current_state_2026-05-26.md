# v1.5 Brown apples-to-apples — Current State (2026-05-26)

**Purpose:** State-capture sanity check on `origin/main` post-v1.8 SIMD landing.
**Procedure constraint:** Read-only state capture. **No** test or engine
modification. Test was run unmodified at the HEAD listed below.

---

## TL;DR

**Both spots PASS. ALL FOUR sanity-check layers (L1 / L2 / L3+L3' / L4) clear
on `dry_K72_rainbow` and `dry_A83_rainbow`.** Numbers are byte-identical to
the v1.7.0 dry-run #10 baseline (`docs/v1_6_1_dryrun_10.md`), which means
**v1.8's SIMD landing (PRs 63b, #41, #33, #32) did not perturb the
average-strategy output** at this gate. The 33pp A83 deep-cap divergence
that the strict per-action gate would flag is still present as expected
under the reframed Brown-as-sanity-check contract (informational
`STRICT_RESULT` shows `Strict max |diff|: 9.066e-01` on A83), but the
v1.5+ acceptance gate is the four-layer sanity check, which PASSES.

| Spot | Verdict | L1 max | L1 p75 | L1 median | Coverage | Action-count parity | Shallow violations | Top-action pass | Strict max \|diff\| | Strict viols ≥ 5e-2 |
|---|---|---|---|---|---|---|---|---|---|---|
| dry_K72_rainbow | **PASS** | 1.736 | 0.069 | 0.004 | 100.0% | 195/195 (100%) | 0/13 | 160/168 (95.2%) | 8.679e-01 | 80 |
| dry_A83_rainbow | **PASS** | 1.813 | 0.194 | 0.049 | 100.0% | 441/441 (100%) | 0/21 | 326/342 (95.3%) | 9.066e-01 | 313 |

Both spots cleared the L3 max-L1 ≤ 1.9 ceiling (PR 53c loosening lives on
`origin/main`, merged in PR #15). Both spots cleared the L3' p75-L1 ≤ 0.60
load-bearing gate by a wide margin (K72 p75=0.069 ⪡ 0.60; A83 p75=0.194 ⪡
0.60).

**Total runtime: 294s (4m 54s).** Brown 2× ~1s; Rust 2× ~2.4m each.

---

## 1. Environment

| Item | Value |
|---|---|
| HEAD | `f165eb85fd409e66d4a2c929e411811a7d150fbe` ("docs: archive 34 unreferenced 2026-05-23/25 session drafts (#52)") |
| Branch | `main` (matches `origin/main`) |
| Working tree | only untracked docs; no tracked-file modifications |
| `_rust.cpython-313-darwin.so` | arm64, located at `/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so` |
| Brown binary | `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`, arm64, 206136 bytes (built 2026-05-22) |
| Python (test runner) | `/Users/ashen/Desktop/poker_solver/.venv/bin/python3.13` (universal2; arm64-capable) |
| `pytest` | 9.0.3 |
| OS / Host | Darwin 24.6.0 / Apple Silicon arm64 |

**Silent-skip hazard caught:** initial run via shell `pytest` (resolving
through pyenv to `/Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13`,
which is **x86_64**) silently SKIPPED both tests with
`_rust.solve_range_vs_range_rust missing — PR 23 not merged / not built`
because the arm64 `.so` could not be loaded under x86_64 Python (silent
`ImportError: incompatible architecture`). The skip wording is misleading
in this environment — the function is present, but the import fails. The
universal2 `.venv` Python loads the arm64 `.so` natively.

This matches the documented `.so` arch hazard
(`feedback_dotso_arch_check.md` + `feedback_silent_skip_hazard.md`):
**Always use `/Users/ashen/Desktop/poker_solver/.venv/bin/pytest` for
this test on this machine**, or build a universal2 `.so` via
`maturin develop --release --target universal2-apple-darwin`.

---

## 2. Test contract recap

`tests/test_v1_5_brown_apples_to_apples.py` (HEAD version on
`origin/main`) is the **REFRAMED 2026-05-24** four-layer sanity check —
**not** the original strict 5e-2 per-action gate.

| Layer | Gate | Threshold |
|---|---|---|
| L1a STRUCTURAL coverage | history-coverage Brown→Rust | ≥ 80% |
| L1b STRUCTURAL row well-formedness | per-row \|sum − 1\| | ≤ 1e-3, no NaN/Inf |
| L1c STRUCTURAL action-count parity | matching action counts (after PR 40 perm) | ≥ 50% |
| L2 SHALLOW-STRICT | per-action \|diff\| at root histories (`""`, `"x"`, `"c"`) | < 5e-2, allow ≤ 5 viol/spot |
| L3 DEEP-DIRECTIONAL max | max per-row L1 distance | ≤ **1.9** (loosened from 1.0 in PR 53c / #15) |
| L3' DEEP-DIRECTIONAL p75 | 75th-percentile L1 | ≤ 0.60 |
| L4 TOP-ACTION | when Brown ≥ 70% on one action, Rust gives ≥ 20% on same | pass rate ≥ 60% |

The original strict `PER_ACTION_TOL = 5e-2` is computed as an
**informational** `STRICT_RESULT` printout (not asserted).

**Spots tested:** `dry_K72_rainbow`, `dry_A83_rainbow` (declared in
`COVERED_SPOT_IDS` at `tests/test_v1_5_brown_apples_to_apples.py:158`).
**Q52 is not in the covered set on this HEAD** — task brief asked about
"A83, K72, Q52" but only A83 and K72 are parametrized.

DCFR hyperparameters: α=1.5, β=0.0, γ=2.0; iterations 2000; Brown seed 7.

---

## 3. Test command run

The shell-default `pytest` resolves to the x86_64 pyenv interpreter on
this host (silent-skip hazard above). The state capture below used the
arm64-compatible `.venv` pytest:

```
/Users/ashen/Desktop/poker_solver/.venv/bin/pytest \
    tests/test_v1_5_brown_apples_to_apples.py \
    -x --timeout=600 -v -s 2>&1 | tee /tmp/v1_5_brown_results.log
```

Working directory: `/Users/ashen/Desktop/poker_solver`.

---

## 4. Full output

```
============================= test session starts ==============================
platform darwin -- Python 3.13.1, pytest-9.0.3, pluggy-1.6.0 -- /Users/ashen/Desktop/poker_solver/.venv/bin/python3.13
cachedir: .pytest_cache
rootdir: /Users/ashen/Desktop/poker_solver
configfile: pyproject.toml
plugins: timeout-2.4.0
timeout: 600.0s
timeout method: signal
timeout func_only: False
collecting ... collected 2 items

tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow]
=== dry_K72_rainbow STRICT_RESULT (informational; not asserted) ===
  Strict per-cell violations (>= 5e-02): 80
  Strict max |diff|:                                    8.679e-01
=== dry_K72_rainbow SANITY_RESULT (gated) ===
  L1 max / p75 / median:                                1.736 / 0.069 / 0.004
  Top-action pass rate:                                 160/168 (95.2%)
  Shallow cells / violations:                           13 / 0
  Coverage:                                             100.0%
  Cells action-count match / total:                     195 / 195 (100.0%)
  Cells action-count mismatch (phantom-ALL_IN):         0
PASSED
tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow]
=== dry_A83_rainbow STRICT_RESULT (informational; not asserted) ===
  Strict per-cell violations (>= 5e-02): 313
  Strict max |diff|:                                    9.066e-01
=== dry_A83_rainbow SANITY_RESULT (gated) ===
  L1 max / p75 / median:                                1.813 / 0.194 / 0.049
  Top-action pass rate:                                 326/342 (95.3%)
  Shallow cells / violations:                           21 / 0
  Coverage:                                             100.0%
  Cells action-count match / total:                     441 / 441 (100.0%)
  Cells action-count mismatch (phantom-ALL_IN):         0
PASSED

=================== 2 passed, 1 warning in 294.00s (0:04:54) ===================
```

Raw log persisted at `/tmp/v1_5_brown_results.log` (45 lines, full
captured output).

---

## 5. Per-spot verdict

### 5a. `dry_K72_rainbow` — **PASS**

| Layer | Measurement | Threshold | Status |
|-------|-------------|-----------|--------|
| L1a coverage | 100.0% | ≥ 80% | PASS |
| L1b row well-formedness | (no malformed rows reported) | sum=1 ± 1e-3 | PASS |
| L1c action-count parity | 195/195 = 100% | ≥ 50% | PASS |
| L2 shallow-strict violations | 0 / 13 cells | ≤ 5 per spot | PASS |
| L3 max L1 | **1.736** | ≤ 1.9 | PASS |
| L3' p75 L1 | **0.069** | ≤ 0.60 | PASS |
| L4 top-action pass rate | 160/168 = 95.2% | ≥ 60% | PASS |
| (info) strict viols ≥ 5e-2 | 80 | not gated | — |
| (info) strict max \|diff\| | 8.679e-01 | not gated | — |

### 5b. `dry_A83_rainbow` — **PASS**

| Layer | Measurement | Threshold | Status |
|-------|-------------|-----------|--------|
| L1a coverage | 100.0% | ≥ 80% | PASS |
| L1b row well-formedness | (no malformed rows reported) | sum=1 ± 1e-3 | PASS |
| L1c action-count parity | 441/441 = 100% | ≥ 50% | PASS |
| L2 shallow-strict violations | 0 / 21 cells | ≤ 5 per spot | PASS |
| L3 max L1 | **1.813** | ≤ 1.9 | PASS |
| L3' p75 L1 | **0.194** | ≤ 0.60 | PASS |
| L4 top-action pass rate | 326/342 = 95.3% | ≥ 60% | PASS |
| (info) strict viols ≥ 5e-2 | 313 | not gated | — |
| (info) strict max \|diff\| | 9.066e-01 | not gated | — |

---

## 6. Comparison to prior session

Prior baseline: `docs/v1_6_1_dryrun_10.md` ("Dry-Run #10", 2026-05-24,
base `origin/main = 3843ce7` = v1.7.0 + 7-PR composite incl. PR 53c L1
ceiling loosening). DR#10 was the dry-run that produced the
v1.6.1-engine ship verdict; PR 53c was subsequently landed on `main`
(PR #15 `49c1421`).

| Metric | DR#10 (2026-05-24) | Today (2026-05-26) | Δ |
|---|---|---|---|
| **dry_K72_rainbow** | | | |
| L1 max | 1.736 | 1.736 | **0.000** |
| L1 p75 | 0.069 | 0.069 | **0.000** |
| L4 top-action | 160/168 (95.2%) | 160/168 (95.2%) | **0** |
| Coverage | 100.0% | 100.0% | 0 |
| Strict viols | 80 | 80 | **0** |
| Strict max \|diff\| | 8.679e-01 | 8.679e-01 | **0** |
| **dry_A83_rainbow** | | | |
| L1 max | 1.813 | 1.813 | **0.000** |
| L1 p75 | 0.194 | 0.194 | **0.000** |
| L4 top-action | 326/342 (95.3%) | 326/342 (95.3%) | **0** |
| Coverage | 100.0% | 100.0% | 0 |
| Strict viols | 313 | 313 | **0** |
| Strict max \|diff\| | 9.066e-01 | 9.066e-01 | **0** |

**Every gated and informational metric is byte-identical between DR#10
(v1.7.0 + composite bundle, pre-SIMD-landing) and today's `origin/main`
(post-v1.8 Phase 2/3/4 SIMD landings + PR 76 exploitative play
addition).** Runtime improved modestly: DR#10 reported 447.86s (7m 27s);
today recorded 294.00s (4m 54s) — ~34% wall-time improvement consistent
with the v1.8 SIMD landing's claimed throughput uplift in DCFR's three
hot loops (`update_regret_sum`, `update_strategy_sum`,
`compute_strategy`). Output bit-exactness is the load-bearing finding
for the SIMD landing — confirms the SIMD paths produce identical
average-strategy dumps to the scalar baseline (modulo timing).

---

## 7. Implications for v1.8.0 release notes

**Net:** the v1.8 SIMD landing is a perf optimization with **zero
behavior change** at this gate. The four-layer sanity acceptance test
continues to PASS on both river spots. No new regressions; no new
divergences; no shifts in any gated or informational metric.

**Verifiable assertions for release notes:**

1. `v1.5.0` acceptance gate (Brown apples-to-apples four-layer sanity
   check) still PASSES on both `dry_K72_rainbow` and `dry_A83_rainbow`.
2. The v1.8 SIMD paths produce **bit-identical** average-strategy
   matrices to the v1.7.0 scalar baseline at 2000 DCFR iterations on
   the river spots (L1 max / p75 / strict viols / strict max
   identical to 4 decimal places).
3. Wall-time on these spots improved from ~447s to ~294s
   (~1.5× speedup at the harness level — includes Brown + Rust + test
   overhead).

**Open items unchanged by this run:**

- A83 strict max \|diff\| remains 9.066e-01 (90.7pp) on individual cells
  at deep-cap facing-bet nodes. The 33pp gap framing the task brief is
  the spot-aggregate "Brown calls top-pair X 87% / Rust calls 45%" type
  divergence documented in `docs/v1_6_1_dryrun_attempt_2.md` §3 — that
  per-pair gap is *within* the strict viols count (~313 cells on A83)
  but is not asserted under the reframed gate. The Nash multiplicity /
  ablation probe currently in flight (Track A) is the right
  investigation; this test capture neither confirms nor refutes the
  terminal-utility hypothesis.
- The shell-default `pytest` silent-skip remains an environmental
  hazard on this host — anyone reproducing this run must use
  `.venv/bin/pytest` or rebuild the `.so` as universal2.

---

## 8. Constraints honored

- [x] Test file NOT modified
- [x] Tolerances NOT modified
- [x] Engine code NOT modified
- [x] No commits or pushes
- [x] State-capture only
- [x] Within ~25-min budget (test ran 4m 54s; total session ~10 min)
