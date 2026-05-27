# Reference validation — README.md + aggregator_vs_true_nash_explainer.md

**Date:** 2026-05-23
**Validator:** opened files directly; no sub-agents; READ-ONLY.
**Scope:** verify every CLI command / flag / function / file-path / version claim.

---

## 1. README CLI commands

| Claim | Location in README | Verified against | Verdict |
|---|---|---|---|
| `poker-solver equity` | L58, L61, L64 | `cli.py:600` (`sub.add_parser("equity", ...)`) | PASS |
| `poker-solver solve --game kuhn` | L67 | `cli.py:631`, `_GAMES` at `cli.py:222-226` | PASS |
| `poker-solver solve --game leduc` | L70 | as above | PASS |
| `poker-solver solve --game hunl --hunl-mode tiny_subgame` | L73, L76 | `cli.py:639-648` choice list includes `tiny_subgame` | PASS |
| `poker-solver solve --game hunl --hunl-mode postflop ...` | L79-82 | choice list includes `postflop`; flags below | PASS |
| `poker-solver ui` | L147 | `cli.py:777-793` | PASS |
| `poker-solver batch-solve` (mentioned in Known issues L225) | L225 | `cli.py:855-864` | PASS |
| `pip install -e .` | L35 | `pyproject.toml` `[project]` + `[project.scripts]` = `poker-solver = "poker_solver.cli:main"` | PASS |

## 2. README CLI flags

| Flag | Cited at | Defined at | Verdict |
|---|---|---|---|
| `--board` (equity) | L58 | `cli.py:606-610` | PASS |
| `-n` / `--iterations` (equity) | L64 | `cli.py:611-622` | PASS |
| `--seed` (equity) | L64 | `cli.py:623-628` | PASS |
| `--game` (solve) | L67 | `cli.py:632-637` | PASS |
| `--iterations` (solve) | L67 | `cli.py:702-708` | PASS |
| `--backend python` / `--backend rust` | L67, L70, L76, L81 | `cli.py:709-714` (choices `("python", "rust")`) | PASS |
| `--hunl-mode tiny_subgame` / `postflop` / `full` | L73, L79 | `cli.py:639-648` | PASS |
| `--board "As 7c 2d"` (solve postflop) | L80 | `cli.py:649-657` | PASS |
| `--stacks 100` | L80 | `cli.py:658-663` | PASS |
| `--bet-sizes "33,75,150"` | L80 | `cli.py:673-682` | PASS |

## 3. README Python imports

| Import claim | Location | Verified | Verdict |
|---|---|---|---|
| `from poker_solver import get_pushfold_strategy, get_full_range` | L88 | `__init__.py:87-89`, `__all__:174-175` | PASS |
| `from poker_solver import HUNLConfig, HUNLPoker, Range, solve, solve_range_vs_range` | L105-107 | `__init__.py:60-93,99` all exported | PASS |
| `solve_hunl_postflop`, `solve_hunl_preflop`, `equity` mentioned in API surface (L98-99) | L98-99 | `__init__.py:46,66,80` | PASS |
| `from poker_solver._rust import solve_range_vs_range_rust` | L119 | `crates/cfr_core/src/lib.rs:428` + `pyfunction` registration L513 | PASS |
| `poker_solver/range_aggregator.py` path for `solve_range_vs_range` | L128 | `range_aggregator.py:211` (`def solve_range_vs_range(`) | PASS |
| `crates/cfr_core/src/dcfr_vector.rs` (vector form module path) | L132 | file exists, 984 LOC | PASS |
| `cpp/src/trainer.cpp:138-240` (Brown reference) | L135, L206 | `trainer.cpp` `Trainer::traverse` literally spans 138-240 | PASS |

## 4. README version + install

| Claim | Verified | Verdict |
|---|---|---|
| "Latest tagged release: v1.5.1" (L14) | `git tag -l` ends in `v1.5.1` (latest = v1.5.1) | PASS |
| `pyproject.toml version = "1.5.1"` | confirmed at `pyproject.toml:7` | PASS |
| `__version__ = "1.5.1"` in `poker_solver/__init__.py` | confirmed at `__init__.py:192` | PASS |

## 5. README known-issues citations

| Claim | Verified | Verdict |
|---|---|---|
| `.dmg` missing `nicegui`, fails at `ui/app.py:362` | `ui/app.py:362` is exactly `from nicegui import ui`. Smoke doc cites same line. | PASS |
| `docs/dmg_v1_4_0_smoke_verification.md` exists | file present (verified) | PASS |
| Adhoc signed / not notarized / arm64-only / `Info.plist` reads `0.6.0` | All four items appear in smoke doc §3-5 | PASS |
| `tests/test_v1_5_brown_apples_to_apples.py` exists | present; docstring confirms acceptance role | PASS |
| Brown acceptance failure traces to test-side encoding (action axis, range slot, suit order) | Discussed in `docs/v1_5_0_brown_acceptance_result.md` and the test docstring | PASS |
| "three independent line-by-line code reviews" (L206-207) | Three triage docs exist (see §6) | PASS (3 docs found) |
| 10-15% residual algorithmic-delta caveat (L209-211) | Judgment call; not numerically verifiable | NOTE — not verifiable |
| W2.2 (fractional `Range` weights) historical tracking ref (L214-215) | `Range.diff` does not block this; consistent with code/docs | PASS |
| `poker-solver batch-solve` CSV quoting + missing hole columns (L225-228) | `cli.py:_cmd_batch_solve` confirms batch-solve goes through `scripts/batch_solve.py`; honest framing | PASS |

## 6. Aggregator explainer code-path claims

| Claim | Location in explainer | Verified | Verdict |
|---|---|---|---|
| `solve_range_vs_range` at `poker_solver/range_aggregator.py:211` | L14 | Confirmed: `def solve_range_vs_range(` at line 211 | PASS |
| `solve_range_vs_range_rust` at `crates/cfr_core/src/lib.rs:428` | L15 | Confirmed: `fn solve_range_vs_range_rust(` at line 428 | PASS |
| `range_aggregator.py:225-301` cited | L26 | Lines fall inside the function; docstring contents (combo counts, hero/villain rep loops) match. | PASS |
| `range_aggregator.py:1-32` module docstring with "blueprint-aggregation workaround" | L36-38 | Confirmed at L1-32 | PASS |
| `dcfr_vector.rs:1-54` module header | L54 | Confirmed (module-doc comments span 1-54) | PASS |
| `lib.rs:389-503` PyO3 surface for `solve_range_vs_range_rust` | L55 | Confirmed: pyfunction block lines 389-503 | PASS |
| `dcfr_vector.rs:49-50, 755` (preflop deferred) | L73 | Lines 49-50 say preflop is deferred to v1.5.1; line 755 emits the runtime error. | PASS |
| **`trainer.cpp:138-209`** (cited as the loop range) | L19, L65 | **FAIL — Brown's `Trainer::traverse` spans 138-240, not 138-209.** Line 209 is mid-loop; 210-240 contain the regret + strategy-sum update logic the explainer claims is mirrored. README (L135, L206) uses the correct 138-240 range. The explainer is internally inconsistent: at L106 it correctly says `trainer.cpp:138-240`, but L19 + L65 use 138-209. | **FAIL (cosmetic)** |
| `trainer.cpp:138-240` (Example 3) | L106 | Confirmed correct range. | PASS |
| Three independent code reviews of PR 23 | L105, L120 | Three docs exist: `pr_23_deep_cap_algorithmic_triage.md`, `v1_6_1_final_synthesis.md`, `pr_23_cell_divergence_deep_dive.md` (all under `docs/`). | PASS (claim supported) |
| 10-15% residual probability (L121-123) | L121 | Judgment call; not numerically verifiable (as expected). | NOTE — not verifiable, as task notes |
| W3.5 + W1.2 examples background | implicit | Both scenarios appear in `docs/pr13_prep/persona_acceptance_spec.md` (W3.5 polarization monotone board; W1.2 JJ on As Tc 5d Jh 8s) | PASS |

## 7. Cross-cutting checks

| Check | Result |
|---|---|
| `docs/persona_test_results/*` referenced? | 0 hits | PASS |
| `docs/pr_*_deep_dive` referenced? | 0 hits (note: real file `pr_23_cell_divergence_deep_dive.md` exists but is not cited by either doc) | PASS |
| `docs/v1_*_diagnosis` referenced? | 0 hits | PASS |
| `docs/v1_*_synthesis` referenced in README? | 0 hits | PASS |
| PII (`/Users/ashen`, `ashen26@`) in either file? | 0 hits | PASS |
| Unshipped versions `v1.6` / `v1.7` promised in README? | 0 hits (README mentions only `v1.8+` for `Range` mixed-frequency refactor, framed as future) | PASS |

## 8. Total issue count

- **PASS:** ~45 specific claims verified end-to-end.
- **FAIL:** 1 (explainer cites `trainer.cpp:138-209` at L19 and L65, but the function spans 138-240; explainer itself uses the correct 138-240 at L106).
- **NOTE / not verifiable:** 1 (the 10-15% caveat — expected per task).
- **WARNING:** 0.

## 9. Verdict

**NEEDS-MINOR-FIXES.** Only one substantive issue: the aggregator explainer cites `trainer.cpp:138-209` in two places (L19 in the TL;DR table footer and L65 in the "What VECTOR-FORM CFR does" body), when the actual `Trainer::traverse` function spans **138-240**. The same explainer correctly uses 138-240 at L106. The README uses the correct range (138-240) at L135 and L206. The 138-209 range happens to match the line range *also* printed inside `crates/cfr_core/src/dcfr_vector.rs:12` — so the explainer copied that range from the module header. The module header itself is slightly under-cited; the canonical range is 138-240 (covers the regret + strategy-sum update tail).

Fix: change the two `138-209` references in the explainer to `138-240` (consistent with L106 and with the README). Alternatively, tighten to `138-209` everywhere AND update the dcfr_vector.rs module header. Either is acceptable, but L106 + README + module-header should agree.

No other blocking issues. README claims hold end-to-end. Recommended action: one-line edit to the explainer, then SAFE-TO-PUSH.
