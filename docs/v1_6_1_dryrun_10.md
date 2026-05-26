# v1.6.1 Engine Ship — Dry-Run #10 (Final: PR 53c Layer-3 Loosening)

**Date:** 2026-05-24
**Worktree:** `/tmp/dryrun-10-final-87409` (disposable; removed at cleanup)
**Base:** `origin/main` @ `3843ce7` (v1.7.0)
**Branch:** `dryrun-10-composite` (worktree-local only)
**Trigger:** confirm the DR#9 corrected 7-PR bundle plus PR 53c Layer-3 ceiling
loosening (`L1_PER_ROW_CEILING: 1.0 → 1.9`) yields **ALL-LAYERS-PASS** on
both river spots.

---

## Pre-condition handling — PR 53c

PR 53c was **not present on `origin/`** at the start of this dry-run
(`gh pr list` only returned PR 53/53b plus the unchanged DR#9 bundle).
Per the orchestrator spec ("If not landing in 15 min, build the Layer 3
loosening manually") and the active auto-mode directive, PR 53c was
synthesized in-worktree:

1. Cherry-pick `origin/pr-53b-rebased-on-pr-54` (= base of 53c).
2. Edit `tests/test_v1_5_brown_apples_to_apples.py`:
   * `L1_PER_ROW_CEILING: float = 1.0` → `1.9`
   * Docstring header reference updated for coherence (`= 1.0` → `= 1.9` +
     justification comment).
   * Test-summary docstring updated (`L1-distance > 1.0` → `> 1.9`).
3. Commit as **"PR 53c: loosen Layer 3 L1_PER_ROW_CEILING from 1.0 to 1.9"**.

Net effect is byte-equivalent to cherry-picking a published `pr-53c-*`
branch built on top of `pr-53b-rebased-on-pr-54`. No double-application of
PR 53b (it appears exactly once, as the base of the synthesized 53c).

---

## Bundle composition (7 cherry-picks)

| # | PR  | Branch                              | Role                                                |
|---|-----|-------------------------------------|-----------------------------------------------------|
| 1 | 51  | `pr-51-dcfr-vector-asymmetric-fix`  | Rust panic fix (asymmetric ranges)                  |
| 2 | 50  | `pr-50-facing-all-in-guard`         | Action-menu guard (Rust + Python)                   |
| 3 | 52  | `pr-52-suit-encoding-fix`           | Wrapper suit-char map                               |
| 4 | 54  | `pr-54-renderer-stack-ceiling`      | Test renderer `stack_ceiling` kwarg                 |
| 5 | 55  | `pr-55-p0-p1-player-swap`           | Wrapper P0/P1 output-side swap                      |
| 6 | 56  | `pr-56-hand-sort-canonicalization`  | Wrapper hand-string canonical sort                  |
| 7 | 53c | (synth: `pr-53b` + L1 ceiling 1→1.9)| Acceptance 4-layer reframe + Layer-3 loosening      |

**EXCLUDED:** `pr-55-extend-input-range-swap` (same as DR#9 — input-side
range swap not part of the corrected hypothesis).
**SUPERSEDED:** `pr-53b-rebased-on-pr-54` (its content is the base of
PR 53c; 53b is *not* applied separately).

All 7 cherry-picks landed cleanly (zero conflicts; PR 55 and PR 56 each
auto-merged `noambrown_wrapper.py`).

---

## Build + smoke

| Step | Result |
|------|--------|
| `cargo build --release` | **OK** (`Finished release in 7.39s`) |
| `cargo test --lib --release` | **50 passed; 0 failed; 0 ignored** (17.43s) |
| `maturin build --target universal2-apple-darwin --release` | OK; wheel `poker_solver-1.7.0-cp313-cp313-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl` |
| `pip install --force-reinstall --no-deps target/wheels/*.whl` | OK (replaced existing 1.7.0 install) |
| `pytest tests/test_exploit_diff.py` | **5 skipped, 0 failed** (baseline behavior under default env; matches DR#9) |

Two worktree-only conveniences (no effect on test logic, only on import
resolution since the wheel installs to site-packages):
* Copied installed `_rust.cpython-313-darwin.so` into the worktree's
  `poker_solver/` source dir so the test process finds the extension
  alongside the worktree source (parallels how `maturin develop` would
  populate a venv).
* Symlinked `references/` from `/Users/ashen/Desktop/poker_solver` so
  `find_brown_binary()` resolves the binary (paths gitignored per repo
  policy).

---

## Acceptance: `pytest tests/test_v1_5_brown_apples_to_apples.py`

```
collected 2 items
... ::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow] PASSED
... ::test_v1_5_brown_apples_to_apples_parity[dry_A83_rainbow] PASSED
======================== 2 passed in 447.86s (0:07:27) =========================
```

### Per-spot, per-layer results

**`dry_K72_rainbow`**

| Layer | Measurement | Threshold | Status |
|-------|-------------|-----------|--------|
| L1 STRUCTURAL coverage | 100.0% | ≥ 80% | PASS |
| L1 STRUCTURAL action-count parity | 195/195 = 100% | ≥ 50% | PASS |
| L2 SHALLOW-STRICT violations | 0 / 13 cells | ≤ 5 per spot | PASS |
| L3 DEEP-DIRECTIONAL max L1 | **1.736** | **≤ 1.9** (loosened) | PASS |
| L3' DEEP-DIRECTIONAL p75 L1 | 0.069 | ≤ 0.60 | PASS |
| L4 TOP-ACTION pass rate | 160/168 = **95.2%** | ≥ 60% | PASS |
| (informational) Strict per-cell violations | 80 | not gated | — |
| (informational) Strict max \|diff\| | 8.679e-01 | not gated | — |

**`dry_A83_rainbow`**

| Layer | Measurement | Threshold | Status |
|-------|-------------|-----------|--------|
| L1 STRUCTURAL coverage | 100.0% | ≥ 80% | PASS |
| L1 STRUCTURAL action-count parity | 441/441 = 100% | ≥ 50% | PASS |
| L2 SHALLOW-STRICT violations | 0 / 21 cells | ≤ 5 per spot | PASS |
| L3 DEEP-DIRECTIONAL max L1 | **1.813** | **≤ 1.9** (loosened) | PASS |
| L3' DEEP-DIRECTIONAL p75 L1 | 0.194 | ≤ 0.60 | PASS |
| L4 TOP-ACTION pass rate | 326/342 = **95.3%** | ≥ 60% | PASS |
| (informational) Strict per-cell violations | 313 | not gated | — |
| (informational) Strict max \|diff\| | 9.066e-01 | not gated | — |

---

## Comparison to DR#9 (Layer 3 max was the only gate that tripped)

| Spot | Max L1 (DR#9) | Max L1 (DR#10) | L1 ceiling | DR#9 verdict | DR#10 verdict |
|------|---------------|----------------|------------|--------------|---------------|
| dry_K72_rainbow | 1.736 | 1.736 | 1.0 → 1.9 | FAIL (L3 max) | **PASS** |
| dry_A83_rainbow | 1.813 | 1.813 | 1.0 → 1.9 | FAIL (L3 max) | **PASS** |

Note that the L1 max numbers are **identical** to DR#9 (same engine + same
wrapper fixes; only the test's ceiling moved), confirming the loosening
was the sole missing piece. The load-bearing aggregate (`p75 L1`) is well
inside the 0.60 ceiling on both spots (0.069 and 0.194 — same as DR#9).

---

## Verdict

**ALL-LAYERS-PASS** — both river spots, all five gates (L1 STRUCTURAL,
L2 SHALLOW-STRICT, L3 max L1 ≤ 1.9, L3' p75 L1 ≤ 0.60, L4 TOP-ACTION).

The corrected 7-PR engine bundle (PR 51, 50, 52, 54, 55, 56) plus the
Layer-3 loosening (PR 53c, which subsumes PR 53b's reframe) clears the
acceptance gate cleanly, with **zero shallow-strict violations** and
**95.2-95.3% top-action agreement** with Brown on the gated parity
spots.

---

## Cleanup

Worktree removed via `git worktree remove --force /tmp/dryrun-10-final-87409`.
No commits or pushes to any branch (per CRITICAL constraints).
