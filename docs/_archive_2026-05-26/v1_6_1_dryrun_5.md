# v1.6.1 Engine Bundle — Dry-Run #5 (PR 50 + 51 + 52, PR 54 NOT-YET-LANDED)

**Date:** 2026-05-24 (early-AM)
**Mode:** READ-ONLY dry-run in disposable git worktree at `/tmp/dryrun-5-bundle-43243`.
**Main working tree NOT modified.** Worktree removed at end of session.

**Composition:** PR 50 + PR 51 + PR 52, on `origin/main = 3843ce7`.
**Renderer fix (PR 54) gap:** PR 54 branch (`pr-54-*`) was NOT open at run time. PR 55 also not open. Proceeded per protocol with the 3 PRs that exist; noting the gap.

---

## TL;DR

**Verdict: STILL-FAILS.** Both spots **FAIL at the history-coverage floor**
(80%) BEFORE the per-cell deep-cap diff is even measured. **Outcome is identical to dry-run #4** because the bundle is unchanged (PR 54 not yet open).

- K72: coverage **53.3%** (16 / 30 brown histories matched) — unchanged from baseline / DR#4
- A83: coverage **66.7%** (28 / 42 brown histories matched) — unchanged from DR#4 (no panic; matches DR#4 once PR 51 unblocks A83)

This dry-run **reconfirms** the DR#4 finding: without PR 54 (renderer fix that adds `stack_ceiling`), the 3-fix bundle does not lift the coverage floor. PR 52 (suit-encoding) addresses card-identity within hand strings, not history-string shape. **v1.6.1 cannot ship as 3-PR composite; the renderer fix (PR 54) is the gating dependency.**

---

## 1. Bundle composition

All 3 PRs applied cleanly via cherry-pick from origin:

| Order | PR | Branch | SHA | Result |
|---|---|---|---|---|
| 1 | PR 50 | `origin/pr-50-facing-all-in-guard` | `782398b` | CLEAN cherry-pick |
| 2 | PR 51 | `origin/pr-51-dcfr-vector-asymmetric-fix` | `bd286e6` | CLEAN cherry-pick |
| 3 | PR 52 | `origin/pr-52-suit-encoding-fix` | `4897fb6` | CLEAN cherry-pick (now lands directly from origin — no manual reconstruction needed unlike DR#4) |
| 4 | PR 54 | `origin/pr-54-*` | — | **NOT-LANDED — branch absent on origin at run time** |
| 5 | PR 55 | (proposed P0/P1 convention) | — | NOT-LANDED |

**Final composite SHA:** `4897fb6` on branch `dryrun-5-composite`.

---

## 2. Phase results

### Phase 1: Wait for PR 54
- `gh pr list --state open` enumerated PRs #2–#8 only.
- PR 54 branch absent on origin; PR 55 likewise.
- Per protocol (≤20-min wait), proceeded without PR 54 and noted the gap.

### Phase 2: Worktree assembled
- `git worktree add /tmp/dryrun-5-bundle-43243 origin/main` — OK
- 3 cherry-picks — all clean, no conflicts.

### Phase 3: Build + smoke

| Step | Result |
|---|---|
| `cargo build --release` | PASS (~7.20s) |
| `cargo test --lib --release` | **50/50 PASS** (17.24s) |
| `pip install -e .` | PASS (`poker_solver-1.7.0`, `numpy-2.4.6`) |
| `pytest tests/test_exploit_diff.py -v --timeout=120` | **5/5 PASS** (35.24s) |

No regressions detected at smoke level.

### Phase 4: K72 + A83 acceptance test

```
pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800 -s
```

**Wall-clock time:** 282.37s (~4m 42s) — both spots ran Brown solver + Rust vector CFR to completion; failed at coverage gate (per-cell parity assertions never reached).

#### K72 (dry_K72_rainbow)
- Coverage: **53.3%** (16 / 30 Brown histories matched in Rust keys)
- FAIL (< 80% floor) → per-cell diff never measured
- Max |diff|, cells > 5e-2, cells > 1e-1, action-count mismatches: **NOT MEASURED**

#### A83 (dry_A83_rainbow)
- Coverage: **66.7%** (28 / 42 Brown histories matched in Rust keys)
- FAIL (< 80% floor) → per-cell diff never measured
- Max |diff|, cells > 5e-2, cells > 1e-1, action-count mismatches: **NOT MEASURED**
- **No panic** (PR 51 still confirms asymmetric-range fix; A83 reaches the gate instead of crashing)

### Phase 5: Comparison table

| Metric | Baseline | DR #2 (PR 35 only) | DR #3 (PR 50) | DR #4 (50+51+52) | DR #5 (50+51+52, NO PR 54) |
|---|---|---|---|---|---|
| K72 coverage | 53.3% | ≥80% | 53.3% | 53.3% | **53.3%** |
| K72 max \|diff\| | 4.22e-1 | 4.22e-1 | 1.000 | n/a (gate-blocked) | **n/a (gate-blocked)** |
| K72 cells > 5e-2 | 305 | 305 | 74 | n/a | **n/a** |
| A83 coverage | n/a (panic prior to PR 51) | ≥80% | n/a (panic) | 66.7% | **66.7%** |
| A83 max \|diff\| | n/a | 2.71e-1 | panic | n/a (gate-blocked) | **n/a (gate-blocked)** |
| Action-count mismatches | 4 | 4 | 0 | 0 | **0** |
| Wall-clock | — | — | — | 442s | **282s** |

### Phase 6: Interpretation

Per the task framework:
- Strict gate (coverage ≥80% AND max |diff| < 5e-2): **FAILS** — coverage 53.3%/66.7% below the 80% floor; per-cell diff not even reachable.
- Widened gate (coverage ≥80% AND max |diff| < 1e-1): **FAILS** — same coverage-gate blocker.
- Investigation path: **PR 54 (renderer/`stack_ceiling`) is the load-bearing fix**, confirmed by DR#2's coverage uplift to ≥80% when PR 35 (which carried Fix A's `stack_ceiling` kwarg) was applied. PR 54 reintroduces that renderer-side change in isolation.

### Phase 7: Cleanup
- Worktree removed: see end of report.

---

## 3. Verdict

**STILL-FAILS** at the coverage gate. The 3-PR bundle (50+51+52) does not lift K72/A83 coverage; identical numerical outcome to DR#4 confirms PR 52 alone does not address history-string shape. PR 54 (renderer fix) is the gating dependency for any v1.6.1 ship decision. Until PR 54 lands and a DR#6 measures the bundle of 50+51+52+54, the strict-gate and widened-gate decisions remain UNDEFINED.

**Recommended next action:** Spawn an agent to author PR 54 (the renderer fix — `stack_ceiling` kwarg threading, in isolation, no other coupling). Once open, run DR#6 to measure the full 4-PR bundle and finally surface the per-cell divergence numbers for K72 + A83.

---

## 4. Reproducibility

```bash
git worktree add /tmp/dryrun-5-bundle-43243 origin/main
cd /tmp/dryrun-5-bundle-43243
git checkout -b dryrun-5-composite
git cherry-pick origin/pr-50-facing-all-in-guard   # 782398b
git cherry-pick origin/pr-51-dcfr-vector-asymmetric-fix  # bd286e6
git cherry-pick origin/pr-52-suit-encoding-fix     # 4897fb6
ln -s /Users/ashen/Desktop/poker_solver/references references  # gitignored deps
cargo build --release
cargo test --lib --release
pip install -e .
pytest tests/test_exploit_diff.py -v --timeout=120
pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800 -s
```
