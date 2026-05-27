# v1.6.1 dry-run #7 — bundle of all 7 fixes (PRs 50/51/52/54/55 + 55-ext + 56)

**Date**: 2026-05-24
**Worktree**: `/private/tmp/dryrun-7-bundle-57930` (`origin/main` + cherry-picks
+ manual PR 55-ext + PR 56)
**Verdict**: **GAP-REMAINS** — strict gate still fails. Coverage is now
100% on both spots (PR 54 + PR 56 working), but per-cell strategy
divergence remains pervasive at full magnitude (max |diff| = 1.000,
~63% of cells ≥ 1e-1 on each spot). PR 23's Rust vector-form CFR and
Brown's DCFR are not in fact computing the same equilibrium on these
spots; the gap is algorithmic, not a labeling/encoding artifact.

## Bundle composition

| Order | PR | Branch | Cherry-pick / commit |
|---|---|---|---|
| 1 | 51 | `pr-51-dcfr-vector-asymmetric-fix` | a084ee9 (clean) |
| 2 | 50 | `pr-50-facing-all-in-guard` | adb2622 (clean) |
| 3 | 52 | `pr-52-suit-encoding-fix` | 0f0d7fd (clean) |
| 4 | 54 | `pr-54-renderer-stack-ceiling` | de2d1bc (clean) |
| 5 | 55 | `pr-55-p0-p1-player-swap` | bb25601 (Auto-merging into 0f0d7fd; clean) |
| 6 | 55-ext + 56 | **manual apply** | 18decef (single commit, see below) |

**Manual PR 55-ext + PR 56**: neither `pr-55-extend-input-range-swap` /
`pr-57-*` nor `pr-56-hand-sort-canonicalization` opened on origin within
the wait window. Built manually per `docs/v1_6_1_dryrun_6.md` §"Path
forward":

- **PR 55-ext**: in `write_brown_config`, swap `spot.ranges[0]/[1]`
  so Brown's tree-internal player 0 (first-to-act) is fed `ranges[1]`
  (= our P1's range, our first-to-act). Paired with PR 55's output-side
  swap, both sides now solve the same underlying game with matching
  role↔range assignment, and the round-trip is transparent to callers
  indexing in our P0/P1.
- **PR 56**: added `_canonicalize_hand_pair(brown_hand_str: str) -> str`
  at the wrapper boundary; called from `_parse_brown_dump` when
  constructing `hands_tuple`. CHAR mapping is identity (Brown's
  `c<d<h<s` already produces lowercase suit chars matching Rust);
  SORT order is converted from Brown's `id=suit*13+rank` to Rust's
  `id=rank*4+suit_idx` with `_RUST_SUIT_INDEX = {s:0, h:1, d:2, c:3}`.

## Build + smoke

- `cargo build --release` (with `PATH=$HOME/.cargo/bin:$PATH`): OK,
  7.42s.
- `cargo test --lib --release`: **50/50 passed** (17.94s).
- `pip install -e .` + maturin universal2 wheel build replacing the
  worktree's x86_64 stub `.so` (cached site-packages `.so` copied in to
  unblock `from poker_solver import _rust`).
- Symlinked `references/` from the canonical checkout so Brown's
  binary at
  `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`
  resolves.
- `pytest tests/test_exploit_diff.py -v --timeout=120`: **5/5 passed**
  (55.42s).

## Acceptance results (`pytest test_v1_5_brown_apples_to_apples.py`)

Pytest verdict: **2 failed** — both at first per-cell diff above
tolerance 5e-3. Wall: 447.98s (7m28s).

### Full metrics (from `/tmp/dryrun7_diagnose.py`, no short-circuit)

#### `dry_K72_rainbow`

| Metric | Value |
|---|---|
| coverage | **100.0%** (30/30 Brown histories matched in Rust) |
| max \|diff\| | **1.000000e+00** |
| cells total | **4171** |
| cells ≥ 5e-3 | 3287 (78.8%) |
| cells ≥ 5e-2 | 2822 (67.7%) |
| cells ≥ 1e-1 | **2644 (63.4%)** |
| action-count mismatches | 0 |
| Brown wall | 0.08s |
| Rust wall | 127.14s |

Top diffs (sorted by |diff|):

```
P0 hand=8c9c hist='xb750A'  action='f' brown=1.0000 rust=0.0000 |diff|=1.000e+00
P0 hand=8d9d hist='xb750A'  action='f' brown=1.0000 rust=0.0000 |diff|=1.000e+00
P0 hand=8c9c hist='xb750A'  action='c' brown=0.0000 rust=1.0000 |diff|=1.000e+00
P0 hand=5d6d hist='xb1500A' action='c' brown=0.0000 rust=1.0000 |diff|=1.000e+00
P0 hand=5s6s hist='xb1500A' action='f' brown=1.0000 rust=0.0000 |diff|=1.000e+00
```

Pattern: P0 facing all-in on K72 with suited connectors (89s, 56s).
Brown folds (1.0), Rust calls (1.0). Action probabilities completely
inverted.

#### `dry_A83_rainbow`

| Metric | Value |
|---|---|
| coverage | **100.0%** (42/42 Brown histories matched in Rust) |
| max \|diff\| | **1.000000e+00** |
| cells total | **4758** (vs 0 vacuous in DR#6 — PR 56 working) |
| cells ≥ 5e-3 | 3757 (79.0%) |
| cells ≥ 5e-2 | 3177 (66.8%) |
| cells ≥ 1e-1 | **2977 (62.6%)** |
| action-count mismatches | 0 |
| Brown wall | 0.09s |
| Rust wall | 160.38s |

Top diffs:

```
P1 hand=8hKh hist='xA' action='c' brown=0.0000 rust=1.0000 |diff|=1.000e+00
P1 hand=7h8h hist='xA' action='c' brown=0.0000 rust=1.0000 |diff|=1.000e+00
P1 hand=6d7d hist='xA' action='c' brown=0.0000 rust=1.0000 |diff|=1.000e+00
P1 hand=8sKs hist='xA' action='f' brown=1.0000 rust=0.0000 |diff|=1.000e+00
```

Pattern: P1 facing river-open shove on A83. Brown folds K8s and 78s;
Rust calls. Again, action-probability inversion.

## Comparison table

| Metric | DR#2 | DR#3 | DR#4 | DR#5 | DR#6 | **DR#7** |
|---|---|---|---|---|---|---|
| Bundle | 35c | 50 | 50+51+52 | 50+51+52 | 50+51+52+54+55 | **50+51+52+54+55+55-ext+56** |
| K72 coverage | ≥80% | 53.3% | 53.3% | 53.3% | 100.0% | **100.0%** |
| K72 max \|diff\| | 4.22e-1 | 1.000 | gate | gate | ~1.000 | **1.000** |
| K72 cells total | — | — | — | — | 172 | **4171** |
| K72 cells ≥ 5e-2 | 305 | 74 | gate | gate | 124 | **2822** |
| K72 cells ≥ 1e-1 | — | — | — | — | 122 | **2644** |
| A83 coverage | ≥80% | panic | 66.7% | 66.7% | 100.0% | **100.0%** |
| A83 max \|diff\| | 2.71e-1 | panic | gate | gate | 0 (vacuous) | **1.000** |
| A83 cells total | — | — | — | — | 0 (vacuous) | **4758** |
| A83 cells ≥ 1e-1 | — | — | — | — | 0 (vacuous) | **2977** |
| Action-count mismatches | 4 | 0 | 0 | 0 | 0 | **0** |

## Key findings

### 1. PR 56 (hand-pair canonicalization): confirmed working

A83 cells_total jumped from **0 (vacuous pass)** in DR#6 to **4758**
in DR#7. The encoding-mismatch black hole that hid every A83 cell is
closed. K72 went from 172 cells (same-suit-only matches) to 4171
cells — i.e. ~24× more cells are now compared, including offsuit
holdings and pocket pairs.

### 2. PR 55-ext (input-range swap in `write_brown_config`): consistent

K72 unmatched histories from DR#6 came from raise-to-stack tokens
rendering as e.g. `b1500r10000` instead of Rust's `b1500A`. PR 54's
`stack_ceiling` kwarg fixed that in the test renderer; combined with
PR 55-ext's input-range swap, all 30 K72 / 42 A83 Brown histories
render to substrings that Rust emits. Coverage is **100% on both
spots**. The test-renderer / encoding side of the gap is fully
closed.

### 3. Per-cell divergence persists at full magnitude

With both encoding hazards eliminated, the residual diffs are
unambiguously real. **63% of K72 cells and 63% of A83 cells diverge by
≥ 1e-1** between Brown and Rust. The top diffs cluster on
all-in-facing rows (`xb750A`, `xb1500A`, `xA`) where Brown and Rust
emit completely inverted action probabilities (one folds 1.0, the
other calls 1.0).

The pattern is suggestive: at the all-in call/fold decision, Brown
and Rust appear to be solving different equilibria, not the same
equilibrium with rounding noise. Candidate explanations (not yet
diagnosed in this dry-run):

- **PR 23's `dcfr_vector.rs` is not a faithful port** of Brown's
  `trainer.cpp:138-209`. The asymmetric-ranges fix (PR 51) closed an
  off-by-one panic but not necessarily a deeper algorithmic deviation.
- **Bet-size set / action menu** at the all-in node differs between
  the two engines despite identical `bet_sizes` / `include_all_in` /
  `max_raises` configs. Action-count mismatches are 0, so the menus
  agree by length, but agreement by length isn't proof of agreement
  by semantics (e.g. one engine offers a 75%-pot bet and an all-in,
  the other offers a 100%-pot bet and an all-in — both length-2).
- **Reach probability / range-weight accounting** at terminal-fold
  vs showdown evaluation differs. Brown's `RiverGame::terminal_utility`
  vs Rust's terminal evaluator.

### 4. Coverage <80% would have re-triggered the regression diagnostic

Initial diagnosis pass (without `stack_ceiling=` in the harness) showed
coverage of 53.3%/66.7% — that was a harness mis-call, not a
regression. The full-fidelity rerun with `stack_ceiling` matches the
real pytest assertion (which passed coverage and failed on per-cell
diff). The strict-gate verdict is unaffected.

## Verdict

**GAP-REMAINS**. Per the decision tree:

- coverage ≥ 80% (100% on both) AND max \|diff\| ≥ 1e-1 → **GAP-REMAINS**.

The strict gate (coverage ≥ 80% AND max \|diff\| < 5e-2) does NOT pass.
The widened gate (max \|diff\| < 1e-1) does NOT pass either. The fix
bundle for v1.7.1 has closed every encoding/labeling vector but the
underlying CFR equilibrium gap is unchanged.

### Path forward (per spec)

- **Path D** (accept Brown-as-sanity-only): ship v1.7.1 with PR 53
  reframe load-bearing. The acceptance test becomes coverage + action-set
  parity + bounded-diff-on-most-cells, not per-cell probability parity.
  This is the only option that ships v1.7.1 today.
- **Diagnose-first** (do not ship v1.7.1 yet): treat the residual diff
  as a deeper algorithmic divergence requiring focused triage in
  `crates/cfr_core/src/dcfr_vector.rs` — line-by-line comparison
  against `cpp/src/trainer.cpp:138-209`, plus single-action-tree
  fixture spots that isolate the divergent decisions. This blocks
  v1.7.1 ship.

Decision routing for the user: this is a Type C-CRITICAL finding under
`docs/pr13_prep/rectification_framework.md` (acceptance-test gate
ungated by load-bearing reframe). Recommend pausing v1.7.1 ship until
the routing call is made.

## Cleanup

Worktree to be removed after report.
