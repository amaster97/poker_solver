# README accuracy check — integration branch state, 2026-05-22

**Scope:** Read-only audit of `/Users/ashen/Desktop/poker_solver/README.md`
against package state on `integration` (the pseudo-main), `CHANGELOG.md`,
`poker_solver/__init__.py`, and `git log integration -20`.

**Snapshot of evidence:**
- README: 238 lines, claims "Current version: 0.3.0" (line 14), "Features
  (v0.3)" header (line 23), "Not yet (roadmap)" header (line 63).
- `poker_solver/__init__.py:158`: `__version__ = "0.3.0"`.
- `CHANGELOG.md`: `[Unreleased]` section explicitly says **PR 4 is "Spec'd;
  implementation pending."** Integration `__init__.py` already imports
  `poker_solver.abstraction.{buckets, equity_features, precompute}`.
- `git log integration -20` confirms PR 4 *is* merged on integration:
  - `5832b2f Integration: merge PR 4 (card abstraction)`
  - `6565b84 PR 4: Card abstraction pipeline (EMD bucketing, 256/128/64, suit-iso)`

## 1. Version-string sync

| Source | Value | Match? |
|---|---|---|
| `README.md` line 14 | `0.3.0 ("HUNL substrate")` | — |
| `poker_solver/__init__.py:158` | `__version__ = "0.3.0"` | yes |
| `CHANGELOG.md` heading | `[0.3.0] - 2026-05-21` | yes |
| `CHANGELOG.md` 0.3.0 notes | `__version__: 0.1.0 -> 0.2.0 ... release tag is 0.3.0; __version__ lag will be reconciled in a later PR` | **stale text** — the lag has been reconciled. |

**Result:** README and `__init__.py` agree on `0.3.0`. CHANGELOG note about
a "version lag" is now self-contradictory but is **CHANGELOG**, not README,
so it's out of scope here. Flag for a CHANGELOG hygiene PR.

## 2. Feature accuracy per claim

All seven items live in README §"Features (v0.3)" (lines 23–61). Each is
verified against the integration tree.

| Claim (README) | Evidence | Status |
|---|---|---|
| Equity calc (hybrid exact + MC) | `poker_solver/equity.py`, `tests/test_equity.py` present; CHANGELOG 0.3.0 §Added confirms hybrid dispatch | shipped |
| Hand evaluator | `poker_solver/evaluator.py` + `tests/test_evaluator.py` | shipped |
| Range parser | `poker_solver/range.py` + `tests/test_range.py` | shipped |
| Kuhn DCFR (Python + Rust, diff-tested) | `dcfr.py`, `crates/cfr_core/src/kuhn.rs`, `tests/test_dcfr_diff.py` | shipped |
| Leduc DCFR (Python + Rust, diff-tested) | `games.py::LeducPoker`, `crates/cfr_core/src/leduc.rs`, `tests/test_leduc_diff.py` | shipped |
| HUNL game state + tree (PR 3) | `poker_solver/hunl.py`, `action_abstraction.py`; integration commit `a96675c` | shipped |
| Push/fold charts 2–15 BB (PR 3.5) | `poker_solver/pushfold.py`, `charts/pushfold_v1.json`; integration commit `9f91c83` | shipped |

## 3. "Not yet (roadmap)" accuracy

README lines 63–81 list what is **NOT** yet shipped. Cross-checked vs.
integration:

| README claim | Reality on integration | Status |
|---|---|---|
| PR 4 (card abstraction: imperfect-recall EMD bucketing, 256/128/64 targets) is "Not yet" | **PR 4 is merged** (commit `5832b2f`). `poker_solver/abstraction/` exists with `buckets.py`, `emd_clustering.py`, `equity_features.py`, `precompute.py`. `__init__.py` exports `build_abstraction`, `AbstractionTables`, `lookup_bucket`, etc. CLI has `precompute-abstraction` subcommand. | **INACCURATE — biggest gap** |
| PR 5 (Python reference solver + per-street memory profiler) is "Not yet" | Not on integration (lives only on `pr-5-hunl-postflop-solve` branch). | accurate |
| PR 6 (Rust port of HUNL postflop) is "Not yet" | Not started. | accurate |
| PR 7 (river-spot diff vs `noambrown/poker_solver`) is "Not yet" | Not started. | accurate |
| PR 8 (NEON SIMD + cache-blocking + public chance sampling) is "Not yet" | Not started. | accurate |
| PR 9 (HUNL preflop solve) is "Not yet" | Not started. | accurate |
| PR 10 (NiceGUI app), PR 11 (macOS packaging), PR 12 (3-handed stretch) | Not started. | accurate |
| `poker-solver solve --game hunl --hunl-mode full` raises `NotImplementedError` "pointing at PR 5" | On integration: `cli.py` `--hunl-mode` choices are `("tiny_subgame", "full")` and `full` still raises `NotImplementedError`. **However**, the current PR-5 branch *moves* the postflop entry-point to `--hunl-mode postflop` and re-points `full` at PR 9 — so the README text is correct against integration today, will need a re-word once PR 5 merges. | accurate today |

**Net:** one concrete inaccuracy on integration today — PR 4 listed as
"not yet" when it is in fact merged.

## 4. Quick-start commands tested

Tested by feeding each example to `poker_solver.cli.build_parser()` and
checking `parse_args` succeeds with the expected `Namespace`. (Full
runtime execution skipped — argparse validation is sufficient signal for
"the command is valid CLI syntax".)

| README example (line) | Parses? |
|---|---|
| `poker-solver equity AhKh QdQc --board 2h7h9d` (103) | yes |
| `poker-solver equity "AA,KK,AKs" QdQc` (106) | yes |
| `poker-solver equity AhKh QdQc -n 1000000 --seed 0` (109) | yes |
| `poker-solver solve --game kuhn --iterations 50000 --backend python` (112) | yes |
| `poker-solver solve --game leduc --iterations 5000 --backend rust` (115) | yes |
| `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500` (118) | yes |
| Python-API block (lines 126–151): `from poker_solver import HUNLConfig, HUNLPoker, default_tiny_subgame, equity, get_full_range, get_pushfold_strategy, KuhnPoker, parse_board, parse_hand, solve` | imports succeed; all symbols are in `__all__` |

All seven examples are syntactically valid against the integration tree.

## 5. License + contributing

| Check | Result |
|---|---|
| README mentions MIT correctly | yes — lines 18 and 236 both say MIT, and `LICENSE` is MIT. |
| README links to `CONTRIBUTING.md` | **no** — README has an inline §Contributing (lines 190–198) but does not link to the standalone `CONTRIBUTING.md` file that exists at the repo root. |
| README links to `PLAN.md`, `CHANGELOG.md`, `LICENSE` | yes (lines 15–18, 164, 187, 194, 237). |

## 6. README amendments needed (proposed, NOT applied)

Six amendments, none load-bearing. Listed in priority order.

**A1 — Move PR 4 out of "Not yet" and into "Features".** Highest priority;
this is the only flat inaccuracy.

In README §"Not yet (roadmap)" lines 65–67, drop:

```
- **Full HUNL postflop solve** — PR 4 (card abstraction: imperfect-recall
  EMD bucketing, 256/128/64 targets) and PR 5 (Python reference solver +
  per-street memory profiler).
```

Replace with:

```
- **Full HUNL postflop solve** — PR 5 (Python reference solver +
  per-street memory profiler) is the next merge.
```

And add a new bullet at the end of §"Features (v0.3)":

```
- **Card abstraction (EMD bucketing)** — imperfect-recall buckets with
  256 flop / 128 turn / 64 river targets, suit-isomorphism canonicalization
  on input features, earth-mover-distance k-means. Persisted as a `.npz`
  artifact and looked up via `AbstractionRef` on `HUNLConfig`. See
  `poker_solver/abstraction/`, the `poker-solver precompute-abstraction`
  CLI, and `tests/test_abstraction_*.py`.
```

**A2 — Add `CONTRIBUTING.md` link.** Replace README line 190 with:

```
## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full dev-environment,
test, and PR-flow contract. The TL;DR: this is a personal solo build
right now; ...
```

**A3 — Add `precompute-abstraction` to the quick-start block.** Suggested
new line under the existing CLI examples (after line 121):

```
# Card abstraction (PR 4): build once, reuse from --abstraction.
poker-solver precompute-abstraction --output abstraction_v1.npz \
    --bucket-counts 256,128,64 --mc-iterations 200000
```

**A4 — Re-word the `--hunl-mode full` sentence (line 79–80).** Once PR 5
merges, this will need to change to point at PR 9, not PR 5. Defer to
PR 5 merge.

**A5 — CHANGELOG `[Unreleased]` section is stale.** Says "PR 4: ... Spec'd;
implementation pending." but PR 4 has been merged to integration. Move
PR 4 bullet into a new `[0.3.1]` (or `[0.4.0]`) section, or into the
existing `[0.3.0]` if treating as a back-patch. Out of scope for *this*
README check; flag for a separate CHANGELOG PR.

**A6 — CHANGELOG 0.3.0 §Changed has a now-resolved "version lag" note.**
Line says `release tag is 0.3.0; __version__ lag will be reconciled in a
later PR`. The lag is resolved (`__version__ == "0.3.0"`). Out of scope
here; flag for the same CHANGELOG PR as A5.

## 7. Recommended one-line fix

If exactly one amendment ships: **A1** (move PR 4 from "Not yet" to
"Features"). It is the only outright inaccuracy and is user-visible from
the first scroll of the README. Everything else (CONTRIBUTING link,
precompute-abstraction example, CHANGELOG hygiene) is incremental polish.
