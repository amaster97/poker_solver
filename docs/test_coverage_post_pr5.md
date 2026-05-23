# Test coverage snapshot — post-PR-5 (integration branch)

**Branch read from:** `integration` (HEAD `eee9b4b` — "Integration: merge PR 5
(HUNL postflop solve + memory profiler)"). Working-tree-only file
`tests/test_hunl_diff.py` (PR 6 in-flight) is **excluded** from all counts
below.

**Collection command:**
`pytest -m "not slow and not very_slow" --collect-only -q --ignore=tests/test_hunl_diff.py`

**Top-line:** 214 tests across 20 files. 213 active under the default CI
marker filter (`not slow and not very_slow`); 1 slow-marked, 0 very_slow;
9 skips + 1 xfail are collected but do not execute as PASS.

---

## 1. Test inventory by file

Path attribution is by `git log --diff-filter=A --follow` (first-add commit).

| Path | Tests | Origin PR | Purpose |
|---|---:|---|---|
| `tests/test_card.py` | 10 | PR 0 | Card / hand / board / deck parsers; roundtrip + reject paths. |
| `tests/test_evaluator.py` | 19 | PR 0 | 7-card hand evaluator: rank class + tiebreak correctness across all categories. |
| `tests/test_equity.py` | 8 | PR 0 | Monte-Carlo equity solver: sum-to-1, deterministic seeding, range vs range. |
| `tests/test_range.py` | 14 | PR 0 | Range parser (pairs, suited, offsuit, dash, plus, explicit combos, error paths). |
| `tests/test_kuhn_dcfr.py` | 6 | PR 1 | Kuhn DCFR: Nash value convergence + strategy validity (Python tier). |
| `tests/test_dcfr_core.py` | 4 | PR 1 | Regret-matching + discount math unit tests on `DCFRSolver` internals. |
| `tests/test_dcfr_diff.py` | 5 | PR 1 | Python vs Rust DCFR on Kuhn (bit-exact game value + exploitability). |
| `tests/test_leduc_core.py` | 14 | PR 2 | Leduc state machine, legality, terminal payoffs, board reveal. |
| `tests/test_leduc_dcfr.py` | 5 | PR 2 | Leduc DCFR convergence + exploitability threshold (600 iters, ε < 0.05). |
| `tests/test_leduc_diff.py` | 5 | PR 2 | Python vs Rust DCFR on Leduc + published-value cross-check (both backends). |
| `tests/test_leduc_intuition.py` | 7 | PR 2 | Leduc poker-sanity: K never folds to first bet, J never re-raises, value-bet pairs, etc. |
| `tests/test_hunl_core.py` | 19 | PR 3 | HUNL state machine + legality + payout + action enum layout. |
| `tests/test_hunl_tree.py` | 10 | PR 3 | Tree-builder smoke + `default_tiny_subgame` shape + integration with `solve`. |
| `tests/test_action_abstraction.py` | 12 | PR 3 | Discrete bet-size set (33/75/100/150/200/all-in) + legality filters. |
| `tests/test_pushfold.py` | 13 | PR 3.5 | Push/fold chart lookup (2-15 BB), per-hand frequency, 169-hand bulk, errors, mode dispatch. |
| `tests/test_abstraction_emd.py` | 14 | PR 4 | EMD math (`emd_1d`, `batch_emd`) + k-means++ on synthetic histograms (homogeneity floor 0.50). |
| `tests/test_abstraction_buckets.py` | 14 | PR 4 | Suit-isomorphism canonicalizer + bucket lookup + serialize/deserialize roundtrip. |
| `tests/test_abstraction_integration.py` | 8 | PR 4 | End-to-end PR 4 pipeline: build → save → load → `AbstractionRef` → tiny solve via `HUNLPoker.infoset_key`. |
| `tests/test_hunl_postflop_solve.py` | 16 | PR 5 | `solve_hunl_postflop` surface: river-subtree convergence (slow), config validation, OOM abort, intuition gauntlet. |
| `tests/test_memory_profiler.py` | 11 | PR 5 | `MemoryProbe` snapshot, per-street accounting, psutil RSS calibration, key-format dispatch. |
| **Total** | **214** | | |

---

## 2. Coverage by PR

- **PR 0 (foundation — card/eval/equity/range):** 51 tests across 4 files
  (`test_card.py`, `test_evaluator.py`, `test_equity.py`, `test_range.py`).
- **PR 1 (Kuhn DCFR + Python/Rust two-tier foundation):** 15 tests across 3
  files (`test_kuhn_dcfr.py`, `test_dcfr_core.py`, `test_dcfr_diff.py`).
- **PR 2 (Leduc + Game trait abstraction):** 31 tests across 4 files
  (`test_leduc_core.py`, `test_leduc_dcfr.py`, `test_leduc_diff.py`,
  `test_leduc_intuition.py`).
- **PR 3 (HUNL tree builder + action abstraction, Python tier):** 41 tests
  across 3 files (`test_hunl_core.py`, `test_hunl_tree.py`,
  `test_action_abstraction.py`).
- **PR 3.5 (push/fold mode 2-15 BB):** 13 tests in `test_pushfold.py`.
- **PR 4 (card abstraction, EMD bucketing 256/128/64, suit-iso):** 36 tests
  across 3 files (`test_abstraction_emd.py`, `test_abstraction_buckets.py`,
  `test_abstraction_integration.py`).
- **PR 5 (HUNL postflop solve + per-street memory profiler):** 27 tests
  across 2 files (`test_hunl_postflop_solve.py`, `test_memory_profiler.py`).

**Cumulative: 51 + 15 + 31 + 41 + 13 + 36 + 27 = 214.** ✓

---

## 3. Slow-marked tests (deselected by default CI filter)

Exactly 1, all in `test_hunl_postflop_solve.py`:

1. `test_hunl_postflop_solve.py::test_postflop_river_subtree_converges`
   (`@pytest.mark.slow`, line 126) — the only spec §11 #2 convergence
   gate. Runs the river subtree to the audit-required iteration count
   and asserts game value within tolerance.

---

## 4. Very_slow-marked tests

**None on integration.** `pytest -m very_slow --collect-only` collects 0
tests. Reserved for future heavyweight gates (e.g. full HUNL preflop
exploitability when PR 7+ lands).

---

## 5. Skip-marked tests (collected, not executed)

All 9 skips trace to the **same root cause: PR 4's tiny `(4, 2, 2)`
abstraction does not cover every TURN runout reachable from the flop-start
fixture; `lookup_bucket` raises and the lossless fallback hangs.** The
skip reasons all reference each other in a chain pointing back to the PR
4 TURN coverage gap.

Note: the task brief said "the 6 from PR 4 TURN coverage gap." Actual count
is **9** — 4 in `test_memory_profiler.py` + 5 in `test_hunl_postflop_solve.py`.

In `tests/test_hunl_postflop_solve.py` (5 skips):
1. `test_postflop_flop_solve_runs_without_crashing` (line 177)
2. `test_postflop_flop_solve_strategy_is_valid` (line 204)
3. `test_postflop_solve_memory_budget_aborts_cleanly` (line 344)
4. `test_postflop_solve_intuition_gauntlet_dry_overpair_bets` (line 409)
5. `test_postflop_solve_intuition_gauntlet_polarization_on_monotone` (line 480)

In `tests/test_memory_profiler.py` (4 skips):
1. `test_memory_report_per_street_covers_postflop` (line 126)
2. `test_memory_report_river_ratio_in_plausible_range` (line 156)
3. `test_memory_report_grand_total_equals_sum` (line 183)
4. `test_memory_profiler_matches_rss_within_10pct` (line 240)

**Skip reasons (verbatim summary):**

> "Tiny (4,2,2) abstraction doesn't cover all TURN runouts from
> flop-start; `lookup_bucket` raises AND lossless fallback hangs.
> **PR 6 (Rust) or fixture redesign with full TURN coverage will
> re-enable.**"

The river-only equivalents (`test_postflop_river_solve_strategy_is_valid`,
`test_memory_profiler_matches_rss_within_10pct_river_only`, etc.) **are**
active and pass — they sidestep the TURN gap by starting from a river
fixture.

PR 6 (Rust HUNL port) is the planned unblocker.

---

## 6. Xfail-marked tests

Exactly 1:

1. `tests/test_abstraction_integration.py::test_abstraction_collapses_strategically_similar_hands`
   (line 122). Reason verbatim:
   `"soft sanity check; abstraction quality varies with seed + tiny config"`.
   `strict=False`. This is the k-means-style soft homogeneity check the
   user referred to as "the kmeans homogeneity one." The harder
   `test_kmeans_separates_clearly_distinct_clusters` in
   `tests/test_abstraction_emd.py` is **not** xfail — it has an inline
   0.50 homogeneity floor and runs every CI cycle.

---

## 7. Total counts (integration HEAD)

| Bucket | Count |
|---|---:|
| Total tests collected | 214 |
| Collected under `not slow and not very_slow` | 213 |
| `slow`-marked | 1 |
| `very_slow`-marked | 0 |
| `skip`-marked (all PR 4 TURN coverage gap) | 9 |
| `xfail`-marked | 1 |
| Active PASS-or-FAIL under default CI filter | 213 − 9 − 1 = **203** |

(Skips and xfails still appear in the collected set; they simply don't
produce a PASS/FAIL result. The active arithmetic above is the
"effective" non-trivial pass-required count.)

---

## 8. Gaps surfaced — what isn't covered yet

1. **Rust HUNL diff tests — to be added in PR 6.** The Rust tier currently
   has diff tests only for Kuhn (`test_dcfr_diff.py`, 5) and Leduc
   (`test_leduc_diff.py`, 5). HUNL (PRs 3, 3.5, 5) is **Python-only** on
   integration. PR 6 will introduce `tests/test_hunl_diff.py` (already
   present in the in-flight working tree) to assert Python/Rust HUNL
   parity on game value, exploitability, and tree shape. **This is the
   single largest coverage gap on integration today.**

2. **Full TURN-coverage flop-start fixture.** Five `solve_hunl_postflop`
   tests and four `MemoryProbe` tests are skipped because the PR 4 tiny
   `(4, 2, 2)` abstraction can't bucket every TURN runout reachable from
   the spec's flop-start fixture. River-only equivalents pass; the
   flop-start path is functionally untested in CI. Unblocker is PR 6
   (Rust) or a fixture redesign with full TURN coverage.

3. **No end-to-end preflop solve coverage.** All current HUNL tests are
   postflop subgame solves (river fixture, occasional flop-fixture skips).
   There is no `solve_hunl_preflop` test surface yet — preflop is treated
   only via the push/fold chart (`test_pushfold.py`, 2-15 BB short-stack
   regime). Deep-stack preflop solving is deferred to PR 7+.

4. **psutil RSS calibration only exercised on river-only path.**
   `test_memory_profiler_matches_rss_within_10pct` (flop-start) is
   skipped; only its river-only sibling actually validates the <10%
   error budget. Spec §11 #4 is implemented but only partially exercised
   in CI.

5. **No exploitability gate on HUNL.** Leduc and Kuhn have explicit
   exploitability thresholds in their convergence tests
   (`LEDUC_EXPLOIT_THRESHOLD = 0.05`). HUNL has the river subtree
   convergence test (`test_postflop_river_subtree_converges`, slow) but
   no equivalent exploitability check on the full postflop tree, only
   game-value tolerance.

6. **No CLI / end-user surface tests.** `poker_solver/cli.py` is touched
   in the PR 6 working tree but has no dedicated `tests/test_cli.py`
   covering the user-visible entry points.

7. **`test_dcfr_core.py` is Kuhn-only.** Its 4 unit tests exercise
   regret-matching + discount math via a Kuhn-configured `DCFRSolver`.
   Equivalent unit tests against the HUNL-configured solver path
   (sequence-form discount under chance nodes, larger action sets) do
   not exist yet.
