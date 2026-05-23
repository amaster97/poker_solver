# Cross-PR cleanup plan (PR 3 / 3.5 / 4 audit triage)

**Scope:** consolidates the should-fix / nice-to-fix items from the three audit
reports under `docs/pr3_prep/`, `docs/pr3_5_prep/`, `docs/pr4_prep/`. Read-only
triage — no code edits.

**Items reviewed:** ~25 should-fix + ~17 nice-to-fix + 11 coverage gaps = ~53
items across the three PRs.

---

## 1. Common themes (cross-PR patterns)

| Pattern | PRs affected | Count |
|---|---|---|
| **Error-type consistency** — `ValueError` vs `AssertionError` vs custom exceptions for config / out-of-range / load failures | PR 3 (`__post_init__`), PR 3.5 (`PushFoldChartUnavailable` not subclassing `ValueError`, silent clamping), PR 4 (`lookup_bucket` error wording) | 4 |
| **License / attribution header consistency** — every new module should carry a one-line license-posture statement, even when no derivation occurred | PR 3 (none on `hunl.py` / `action_abstraction.py` — confirmed no derivation, but no statement), PR 4 (`equity_features.py` missing) | 2 |
| **Magic constants / undocumented thresholds** — bare numeric thresholds where a sentinel or named constant would be clearer | PR 3.5 (`v1-placeholder` accepted, 80% sum-floor), PR 4 (`mc_iterations < 5_000` autosize trigger, `chosen_idx[c] = chosen_idx[0]` fallback) | 4 |
| **Predicate range tightness** — IntEnum comparisons that accidentally include sentinel members (SHOWDOWN, etc.) | PR 4 (`infoset_key` uses `>= FLOP` capturing SHOWDOWN), PR 3 (`Street.SHOWDOWN` value 4 not in `_CARDS_TO_DEAL`) | 2 |
| **Dead-code / unreachable defensive branches** | PR 3 (`enumerate_legal_actions` stack≤0 case), PR 3.5 (`_canonical_hand_classes` unused), PR 4 (`_kmeans_plusplus_init` empty fallback at line 188) | 3 |
| **Duplicated configuration defaults** — same constant defined in 2-3 dataclasses | PR 3 (`bet_size_fractions` triplicated), PR 3.5 (`_canonical_hand_classes` vs `_all_hand_classes`) | 2 |
| **Tests assert weaker invariants than spec** — floor / band thresholds used in place of equality where spec gives a literal value | PR 3 (no wall-clock bound; raise-cap reset un-asserted), PR 3.5 (80% combo floor vs spec's 100%; missing S-C band tests) | 4 |
| **Docstring-promised behavior contradicted by impl** | PR 3 (`include_all_in=False` flag still leaks via helpers), PR 4 (`compute_river_features` "seed unused on river" but rng still spawned) | 2 |
| **Missing INFO/debug log on dispatch** | PR 3.5 (chart-mode dispatch silent vs spec §6.205-206) | 1 |

---

## 2. Easy batched fixes (<2 hr agent work, all PRs)

These are fast, low-risk, mechanical fixes that benefit from being done together:

1. **Add license-posture header line to `equity_features.py` + `hunl.py` + `action_abstraction.py`** (3 files, one-line each: "no third-party code derivation; original implementation"). Est: 10 min.
2. **Make `PushFoldChartUnavailable` subclass `ValueError`** in `poker_solver/pushfold.py:30`. Removes the should-fix on consistent error types without rewriting call sites. Est: 5 min + verify 13 pushfold tests still pass.
3. **Convert `AssertionError` → `ValueError` for config violations** in `HUNLConfig.__post_init__` (hunl.py:107, 109 — rake-field invariants). 2 lines. Est: 10 min.
4. **Tighten `infoset_key` predicate to exclude SHOWDOWN** (hunl.py:326 — change `>= FLOP` to `in (FLOP, TURN, RIVER)`). 1 line. Est: 5 min.
5. **Remove dead code: `_canonical_hand_classes` in `pushfold.py:185`** + `enumerate_legal_actions` stack≤0 branch + `_kmeans_plusplus_init` line-188 fallback to `# unreachable` assert. 3 sites. Est: 15 min.
6. **Remove unused import `field` from `hunl.py:14`**. 1 line. Est: 1 min.
7. **Drop `v1-placeholder` from `PUSHFOLD_CHART_VERSIONS`** (pushfold.py:25). 1 line. Est: 5 min.
8. **Add explicit "raise-cap resets to 0 on street transition" assertion** to an existing test in `test_hunl_core.py`. Est: 10 min.
9. **Surface `--max-boards None`/`-1` sentinel disambiguation in `precompute.py`** with one-line comment + CLI help text. Est: 15 min.
10. **Clarify `lookup_bucket` error message** to mention user-facing remedy (buckets.py:233-245). Est: 10 min.

**Total estimate: ~90 minutes** for one agent, or ~30 min wall-clock with 3-way fan-out.

---

## 3. PR-specific issues (cannot be batched)

These are domain-specific and must wait for their dedicated PR cycle:

### PR 3 (HUNL tree)
- **`HUNLState.config` vs `HUNLPoker.config` source-of-truth selection** — needs careful audit of all read sites; defer to PR 5+ if no caller mutates.
- **`initial_contributions=(0,0)` dead-money interpretation** — needs spec amendment (§4 invariants) before code can clarify; defer.
- **Add wall-clock bound to `test_hunl_default_tiny_subgame_solvable_in_one_minute`** — would require a CI-runtime calibration pass.
- **CLI smoke test for `--hunl-mode tiny_subgame`** — easy but belongs in CLI test file, not abstraction PRs.

### PR 3.5 (push/fold charts)
- **`solve_pushfold` public API + `get_pushfold_range` alias + `backend == "pushfold_chart"` + `force_tree_solve` kwarg** (audit must-fixes 1, 2, 3) — these are PR 3.5's own must-fix items, not cross-PR batchable. **MUST land before PR 5** or downstream tooling depending on the spec'd public surface will break.
- **`final_exploitability_bb_per_100` scalar + `game_value` populated + `exploitability_history` per-depth** — chart-data + loader contract changes, single domain.
- **`ValueError` on out-of-range stack (not silent clamp)** — solver.py:293-297. Single domain.
- **Spec amendment OR regen for d=2 universal-jam landmark** — needs strategic decision between regen and amendment; PR 3.5 cleanup only.
- **Strategic-equivalence collapse assertion in generator OR alternate tree-builder cross-check** — generator-side validation; needs separate study.
- **`tests/test_pushfold_regen.py` smoke test** — single-file new test.

### PR 4 (card abstraction)
- **`save_abstraction` byte-determinism via timestamp override** — needs design decision; defer or env-var-gate.
- **Rename `_canonicalize` / `_apply_suit_perm_to_hand` to spec names `_canonical_board_id` / `_canonical_hand_key`** — touches buckets.py + tests; PR-4-specific.
- **CLI test for `--flop-mode exact` path** — single-test addition; PR 4 follow-up.
- **K-means quality tuning** (centroid count, EMD tolerance) — **blocked on PR 6 Rust port**; deferred indefinitely.

---

## 4. Recommended cleanup PR scope (PR 4.5)

**Recommendation: YES, do it.** Create a small PR-4.5 "audit-debt sweep" between PR 4 and PR 5.

### Proposed scope ("PR 4.5: cross-PR cleanup batch")

**Branch:** `pr-4.5-audit-cleanup`

**In-scope (batched fixes only — no design changes):**
- All 10 items from §2 above.
- PR 3.5 must-fixes 1-5 (public API rename + `ValueError` + `backend` string + chart metadata scalars) — these are NOT cross-PR-cleanable but they MUST land before PR 5 anyway, and folding them into the same maintenance branch reduces context-switch cost.
- PR 4 should-fix #1 (equity_features.py header) and #2 (SHOWDOWN predicate).

**Out-of-scope (defer to PR 5+ or dedicated):**
- All spec-amendment-requiring items (PR 3 `HUNLState.config` dedup, PR 3.5 d=2 landmark, etc.).
- Any item touching `references/` or kmeans tuning.
- New tests beyond §2 item 8.

### Agent fan-out plan

Parallel waves (one agent per track, all independent):

- **Agent A (~30 min):** PR 3 mechanical fixes (`AssertionError` → `ValueError`, unused import, dead code in `enumerate_legal_actions`, license header on `hunl.py` + `action_abstraction.py`, raise-cap-reset test assertion).
- **Agent B (~45 min):** PR 3.5 must-fixes 1-5 (public API surface + `ValueError` raise + backend string + drop `v1-placeholder` + remove `_canonical_hand_classes` dead code + `PushFoldChartUnavailable(ValueError)`).
- **Agent C (~30 min):** PR 4 cleanup (equity_features.py header, SHOWDOWN predicate, `lookup_bucket` error message, `_kmeans_plusplus_init` line-188, `--max-boards` sentinel docs).
- **Aggregator wave:** single agent runs full pytest + mypy --strict + ruff; opens PR; updates `docs/autonomous_log.md` with deltas.

**Total wall-clock estimate: ~60 minutes for the parallel waves + 30 min aggregate = ~90 min.** Net throughput vs sequential is roughly 2.5x.

### Acceptance gates for PR 4.5

1. All existing tests pass (151+ tests).
2. `mypy --strict poker_solver/` clean.
3. `ruff check` clean.
4. No new dependencies.
5. `docs/autonomous_log.md` records each must-fix → fix mapping with file:line refs.

---

## 5. Items to leave indefinitely

Truly nice-to-have items with no material correctness or quality impact:

- **PR 3 nice-to-fix #3** — `_pack_hole_outcome` 8-bit-per-card vs 6-bit. Cosmetic; kept for byte alignment / Rust simplicity.
- **PR 3 nice-to-fix #5** — `bet_size_fractions` default duplicated across 3 dataclasses. DRY-defer per audit; only worth fixing if a downstream change is planned.
- **PR 3 nice-to-fix #7** — `Street.SHOWDOWN` comment about no-cards-dealt. Code is correct; comment is decorative.
- **PR 3.5 nice-to-fix #4** — generator float precision (4-decimal rounding vs full). Charts converge to <0.05 bb/100; sub-borderline regret signals will not move strategy.
- **PR 3.5 nice-to-fix #6** — README clarification of per-depth vs aggregate exploitability. Docs polish.
- **PR 4 nice-to-fix #2** — `uint8` dtype comment "K up to 256" wording. Comment is technically correct.
- **PR 4 nice-to-fix #3** — `canonicalize_for_suit_iso` returns `(str, int)` vs packed int. **Deferred to PR 6** (Rust port boundary).
- **PR 4 nice-to-fix #5** — `dists * dists` vs `np.square(dists)`. Pure cosmetic.
- **PR 4 nice-to-fix #6** — `_progress(msg)` helper to consolidate `print` formatting. Aesthetic.
- **PR 4 should-fix #4** — `save_abstraction` byte-determinism via timestamp. Spec is silent; existing tests verify modulo-timestamp equality; defer to a future content-addressable-cache PR if one ever materializes.
- **All PR 3.5 §9 / §10 spec-coverage-gap tests beyond what's already batched** — adding S-C band tests at d=4, d=10 etc. is value-add but not gating. Schedule as a separate "data quality" track if needed.

---

## Locked-spec sanity check

None of the proposed cleanup items conflicts with locked decisions in
`PLAN.md`: integer-chip discipline preserved, no abstraction-table mutation,
no AGPL contamination introduced, `solve_pushfold` rename respects the
documented public-API contract in pr3_5_spec.md §6.
