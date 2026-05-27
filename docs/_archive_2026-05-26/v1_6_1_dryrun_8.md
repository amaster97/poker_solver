# v1.6.1 dry-run #8 — final 8-PR bundle with reframed acceptance gate (PR 53b)

**Date**: 2026-05-24
**Worktree**: `/private/tmp/dryrun-8-final-69327` (`origin/main` + 7 cherry-picks
+ manually-resolved PR 53b)
**Verdict**: **NEEDS-MORE-WORK** — even with PR 53's load-bearing reframe of
the acceptance test, the bundle FAILS the new 4-layer sanity gate. Two of
four layers fail on BOTH spots: Layer 2 (Shallow-Strict, root-history
per-action <=5e-2) and Layer 3 (Deep Directional, p75 row-L1 <=0.60). The
divergence is no longer attributable to action-menu mismatch at deep cap
— it is now visible AT THE ROOT, on hands like AA/88/TT, where Brown's
strategy is "check 100%" and Rust's is split across check / b500 / b1000.
This indicates an engine-level disagreement on opening-action equilibrium,
not just deep-cap abstraction divergence.

## PR 53b status

PR 53b was NOT opened on origin within the wait window. Per spec, applied
fallback: manually-resolved cherry-pick of PR 53 onto the 7-PR base. The
four conflicts in `tests/test_v1_5_brown_apples_to_apples.py` were:

| Region | Source of conflict | Resolution |
|---|---|---|
| L453-463 (all-in jam comment) | PR 54 comment wording vs PR 53 comment wording (both apply the same `tokens.append("A")` semantics) | Kept HEAD (PR 54's wording) — no Fix-A historical context |
| L472-477 (all-in raise comment) | Same as above | Kept HEAD |
| L644-647 (coverage scan comment) | PR 50 added `# Did EITHER Rust player...` inline | Kept HEAD (preserves PR 50's helpful annotation) |
| L715-719 (rust_player vs player) | HEAD has `player`; PR 53 has `rust_player` (because PR 53's loop var is `brown_player` with `rust_player = 1 - brown_player`) | Kept PR 53 (`rust_player`) — correct for the reframe's loop structure |

Manual resolution committed as `6e77f0f`. Python AST parse OK; test
collection OK (2 parametrized tests collected).

## Bundle composition (8 cherry-picks)

| # | PR | Branch | Commit (after CP) | Status |
|---|---|---|---|---|
| 1 | 51 | `pr-51-dcfr-vector-asymmetric-fix` | `06e7c77` | CLEAN |
| 2 | 50 | `pr-50-facing-all-in-guard` | `0af663b` | CLEAN |
| 3 | 52 | `pr-52-suit-encoding-fix` | `7eb4324` | CLEAN |
| 4 | 54 | `pr-54-renderer-stack-ceiling` | `d82a407` | CLEAN |
| 5 | 55 | `pr-55-p0-p1-player-swap` | `ffd2eda` | CLEAN (auto-merge) |
| 6 | 55-ext | `pr-55-extend-input-range-swap` | `d8b23e8` | CLEAN (auto-merge) |
| 7 | 56 | `pr-56-hand-sort-canonicalization` | `2792bfa` | CLEAN (auto-merge) |
| 8 | 53b | manual-resolve | `6e77f0f` | CONFLICT-RESOLVED (4 regions, all comment/loop-var) |

7 of 8 clean. PR 53b required manual conflict resolution but the
conflicts were trivial (3 comment-only + 1 loop-variable-rename); none
required semantic re-coding.

## Build + smoke matrix

| Phase | Result | Wall |
|---|---|---|
| `cargo build --release` | OK | 7.24s |
| `cargo test --lib --release` | **50/50 passed** | 17.79s |
| `pip install -e .` | FAIL (x86_64 cross-arch issue per DR#7 protocol) | — |
| `maturin build --target universal2-apple-darwin` | OK (universal wheel) | ~5s |
| `pip install` universal wheel + copy `.so` to worktree | OK | — |
| `pytest tests/test_exploit_diff.py -v --timeout=120` | **5/5 passed** | 56.39s |
| `pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800` | **2/2 FAILED** (reframed gate, Layer 2) | 452.44s |
| `pytest tests/test_asymmetric_range_sanity.py` | Not present in worktree | — |
| `pytest -x --timeout=60 -m "not slow"` | 77 passed + 1 unrelated CLI-parity timeout | ~250s |

Note: `tests/test_cli_subcommands.py::test_parity_happy_path_runs_to_completion`
times out even at 300s. This test runs a 50-iter Rust solve via CLI — it
is slow regardless of bundle; not bundle-attributable.

## Reframed gate results

### `dry_K72_rainbow`

| Layer | Threshold | Actual | Pass/Fail |
|---|---|---|---|
| 1a Coverage | >= 80% | **100.0%** | PASS |
| 1b NaN-free | structural | OK | PASS |
| 1c Action-count parity | >= 50% | 195/195 (**100.0%**) | PASS |
| 2 Shallow-Strict | <= 5 violations @ 5e-2 root tol | **20 violations** | **FAIL** |
| 3 Deep Directional (max L1) | <= 1.0 | **2.000** | **FAIL** |
| 3 Deep Directional (p75 L1) | <= 0.60 | **1.008** | **FAIL** |
| 3 Deep Directional (median L1) | — (informational) | 0.053 | — |
| 4 Top-action agreement | >= 60% | 138/154 (**89.6%**) | PASS |
| STRICT_RESULT (informational) | — | 227 cells >= 5e-2; max |diff|=1.000 | — |

### `dry_A83_rainbow`

| Layer | Threshold | Actual | Pass/Fail |
|---|---|---|---|
| 1a Coverage | >= 80% | **100.0%** | PASS |
| 1b NaN-free | structural | OK | PASS |
| 1c Action-count parity | >= 50% | 441/441 (**100.0%**) | PASS |
| 2 Shallow-Strict | <= 5 violations @ 5e-2 root tol | **20 violations** | **FAIL** |
| 3 Deep Directional (max L1) | <= 1.0 | **2.000** | **FAIL** |
| 3 Deep Directional (p75 L1) | <= 0.60 | **0.792** | **FAIL** |
| 3 Deep Directional (median L1) | — (informational) | 0.299 | — |
| 4 Top-action agreement | >= 60% | 283/307 (**92.2%**) | PASS |
| STRICT_RESULT (informational) | — | 671 cells >= 5e-2; max |diff|=1.000 | — |

## Top shallow-strict violations (both spots)

Both spots' Layer-2 failures live at the **root history (`hist=''`)** on
strong made-hands / pocket pairs. Brown's solver checks 100%; Rust's
splits across check + multiple bet sizes. Examples:

### K72 root
```
P0 hand=KsKh hist=''  action='c'    brown=1.0000 rust=0.???? |diff|≈0.9
P0 hand=KhKd hist=''  action='b500' brown=0.0000 rust=0.???? |diff|≈0.6
```
(13 hands × ~1.5 actions = 20 violations on 13 root cells)

### A83 root
```
P1 hand=AdAc hist='' action='c'    brown=1.0000 rust=0.2525 |diff|=7.475e-01
P1 hand=AdAc hist='' action='b500' brown=0.0000 rust=0.4463 |diff|=4.463e-01
P1 hand=AdAc hist='' action='b1000' brown=0.0000 rust=0.3013 |diff|=3.013e-01
P1 hand=AsAc hist='' action='c'    brown=1.0000 rust=0.1124 |diff|=8.876e-01
P1 hand=8s8d hist='' action='c'    brown=1.0000 rust=0.0000 |diff|=1.000e+00
P1 hand=ThTd hist='' action='c'    brown=1.0000 rust=0.0002 |diff|=9.998e-01
```
21 root cells checked; 20 violations.

This pattern — **AA/TT/88 want to check 100% per Brown but Rust opens for
30-92% of the range** — is now genuinely diagnostic of an engine-level
equilibrium disagreement at the root, NOT a deep-cap abstraction issue.

## Comparison table

| Metric | DR#7 | **DR#8** |
|---|---|---|
| Bundle | 7 PRs | **8 PRs (+ PR 53b)** |
| Strict 5e-2 gate (PR 53 absent in DR#7) | FAIL | n/a (replaced) |
| Reframed Layer 1 (structural) | n/a | **PASS** |
| Reframed Layer 2 (shallow-strict) | n/a | **FAIL** (K72: 20, A83: 20) |
| Reframed Layer 3 (deep directional p75) | n/a | **FAIL** (K72: 1.008, A83: 0.792) |
| Reframed Layer 4 (top-action) | n/a | **PASS** (K72: 89.6%, A83: 92.2%) |
| K72 coverage | 100.0% | 100.0% |
| K72 max \|diff\| (informational) | 1.000 | 1.000 |
| K72 strict violations (informational) | n/a | 227 |
| A83 coverage | 100.0% | 100.0% |
| A83 max \|diff\| (informational) | 1.000 | 1.000 |
| A83 strict violations (informational) | n/a | 671 |

## Verdict

**NEEDS-MORE-WORK**. The reframed gate fails on:

- **Layer 2 (Shallow-Strict)** — 20 root-history violations per spot.
  PR 53's own docstring states explicitly: *"Root histories cannot have
  action-menu divergence (no cap-reached / facing-all-in possible at
  depth 0). A violation here is a genuine engine bug — likely in
  hole-card hashing, terminal utility, or DCFR weighting. Triage:
  `crates/cfr_core/src/dcfr_vector.rs`."*
- **Layer 3 (Deep Directional)** — p75 row-L1 = 1.008 on K72 (vs <=0.60
  threshold); 0.792 on A83. Direction-of-aggression on 25% of deep
  histories diverges by more than half the action mass.

PR 53b is **load-bearing** for the bundle's ability to land — without
PR 53's reframe, the bundle fails strict 5e-2 at 898 cells (227+671).
With PR 53's reframe, the bundle STILL fails the new gate at the root
level.

### What this means

- **The strict 5e-2 gate was hiding** the root-equilibrium gap behind
  the action-menu narrative. With PR 53's surgical isolation of root
  histories (where action menus DO match), the residual disagreement is
  exposed as root-level, not deep-cap.
- **PR 53's `SHALLOW_MAX_VIOLATIONS_PER_SPOT = 5`** is a tight but
  principled threshold. Brown and our Rust solver agree on action menus
  at depth 0; if they don't agree on Nash-equilibrium probabilities at
  depth 0, that's an engine-level finding. 20 violations is 4x the
  allowance.
- **Pattern is consistent across both spots**: top pairs / pocket pairs
  prefer "check" in Brown but "mix bet sizes" in Rust. This is symmetric
  enough across K72 (P0 first-to-act after preflop X) and A83 (P1
  first-to-act after preflop X) to suggest a **single root-cause**
  rather than two independent bugs.

### Path forward

Per `docs/pr13_prep/rectification_framework.md`, this is Type
**C-CRITICAL**: acceptance gate fails after the load-bearing reframe.
Routing options:

1. **Pause v1.6.1 ship**. Investigate root-history equilibrium
   disagreement in `crates/cfr_core/src/dcfr_vector.rs` — specifically:
   - hole-card hashing parity (`exploit::hole_string`)
   - terminal-utility computation at fold-vs-showdown boundary
   - DCFR's regret-weight averaging vs Brown's strategy-sum averaging
   - the all-in stack-ceiling normalization affecting bet-sizing equilibrium
2. **Loosen Layer 2 tolerance** to `MAX_VIOLATIONS = 25` (covering both
   spots' 20 observed). This would mask a real engine finding and is
   NOT recommended without research-first review of whether the gap is
   genuinely "abstraction noise" vs "incorrect Nash mixing".
3. **Bisect the bundle** to isolate which PR introduces the shallow
   violations (run DR#7-base + PR 53b only to see if violations are
   present without PRs 50/51/52/54/55/55-ext/56, then add back
   incrementally). This would tell us whether the bundle CAUSES the
   shallow gap or merely EXPOSES a pre-existing engine bug.

The recommendation is **option 1 (pause)** combined with **option 3
(bisect)** to localize the divergence. Option 2 is a clear violation of
the "don't extrapolate" / "research-first failure" memory rules: we have
direct evidence of a 20-violation root-equilibrium gap, and shipping
under a loosened gate would constitute Type-D risk masking.

## Cleanup

Worktree to be removed after this report (per spec).

```bash
cd /Users/ashen/Desktop/poker_solver
git worktree remove --force /private/tmp/dryrun-8-final-69327
```
