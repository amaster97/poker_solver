# PR 3.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-3.5-pushfold (commit `9f91c83`, parent `351cbee` on `integration`)
**Diff size:** 9 new files + 5 modified files = +4963/-61 LoC total (`git diff 351cbee..9f91c83 --stat`)

**Test status:** `pytest tests/test_pushfold.py` — **13/13 pass** (0.15 s). `tests/test_pushfold_regen.py` is **missing** (spec §9 test 11 + §15 gate item 2). Full suite delta not re-run end-to-end in this audit (would require Rust build); pushfold tests verified standalone.

---

## Must-fix

1. **`solve_pushfold(config) -> SolveResult` public function is missing entirely** — spec §6 lines 174–192 mandate this as a first-class entry point on the public API; spec §10 final bullet and §15 gate item 3 both reference it; spec §13 risk row R4 mentions an explicit "force tree solve" path. Implementation provides only a private helper `poker_solver/solver.py:284 _solve_pushfold_lookup(config)` invoked from inside `solve()`. Callers cannot import `solve_pushfold` from `poker_solver` or `poker_solver.pushfold`. **Fix:** expose `solve_pushfold(config: HUNLConfig) -> SolveResult` as a public name in `pushfold.py`, re-export from `poker_solver/__init__.py`, and have `solver.solve()` delegate to it.

2. **`backend` value mismatch with spec §6 line 215** — spec mandates `backend == "pushfold_chart"`; implementation returns `backend == "pushfold"` (`poker_solver/solver.py:310`, asserted in `tests/test_pushfold.py:144` and `tests/test_pushfold.py:163`). Downstream tooling that branches on the backend string will not match. **Fix:** change the string to `"pushfold_chart"` in both the `SolveResult` construction and the two test assertions.

3. **`get_pushfold_range` (spec §6 lines 166–172) renamed to `get_full_range` without spec amendment** — spec defines the public name; impl ships `get_full_range` (`poker_solver/pushfold.py:128`) and `__init__.py:60` re-exports under that name. Both names should be either reconciled in the spec or aliased. **Fix:** add a `get_pushfold_range = get_full_range` alias and re-export, OR amend the spec to lock in `get_full_range` (the autonomous log does not record this rename as an accepted deviation).

4. **`final_exploitability_bb_per_100` metadata field absent** — spec §5 (file format), §7 (chart-generation pipeline), §10 (critical correctness items: "Recorded in the JSON metadata. If a regeneration produces higher exploitability, the PR is rejected"), and the audit prompt focus area 11 all require this top-level scalar in the JSON. `poker_solver/charts/pushfold_v1.json` instead carries a per-depth dict `exploitability_bb_per_100: {"2": 0.0, ..., "15": 0.0}`. Loader does not enforce or surface the scalar. Convergence gate cannot be validated by the schema check the spec describes. **Fix:** add `final_exploitability_bb_per_100: max(per_depth.values())` (or any documented aggregator) to the JSON, and add an assertion in `_load_chart_data()` that it is < 0.05.

5. **`solve_pushfold` does NOT raise `ValueError` for `eff_stack > 15` or `< 2`** — spec §6 lines 188–191 require `ValueError` with a "use the tree-builder solver" message; spec §10 closing bullet reiterates. The implementation's dispatcher `_solve_pushfold_lookup` (solver.py:293–297) silently **clamps** out-of-range stacks to `[2, 15]` (`if eff_bb < PUSHFOLD_MIN_BB: eff_bb = PUSHFOLD_MIN_BB`). A caller asking for 50 BB silently gets the 15-BB chart back — a downstream-silent-wrong-answer pattern (audit prompt severity rule). **Fix:** raise `ValueError` (NOT `PushFoldChartUnavailable`) on `eff_bb > PUSHFOLD_MAX_BB` and `< PUSHFOLD_MIN_BB` in `_solve_pushfold_lookup`; also revisit `get_pushfold_strategy` (see should-fix 2).

6. **Spec §9 test 4 ("at d=2, SB jams 100% of all 169 classes") FAILS against the committed chart** — the JSON has 12 hand classes at `d=2 sb_jam` with frequency 0.0 (`72o, 32o, 82o, 73o, 52o, 43o, 32s, 62o, 42s, 63o, 53o, 42o`). The Sklansky-Chubukov landmark in spec §4 ("SB jams 100% of hands at ≤ 4 BB stacks") is also violated. The generation notes (§3, §5) document this as expected ("HU Nash has BB calling enough at 2 BB that 72o jam is -EV") but no spec amendment was recorded in `docs/autonomous_log.md` accepting the deviation. This is either a spec amendment that must be retro-documented OR a solver-correctness issue. **Fix:** either (a) regenerate with parameters that produce universal jam at d=2 (matching spec §9 test 4), or (b) amend `pr3_5_spec.md` §4 + §9 to accept the HU Nash result, and update the failing-by-spec-text test `test_pushfold_strategy_frequencies_sum_consistently` (line 208 floor of 80%) so that the divergence is intentional. The test currently codifies the deviation silently.

---

## Should-fix

1. **No `INFO` log emitted on chart dispatch** — spec §6 line 205–206 ("This dispatch is silent in the common case … and emits an `INFO` log line noting which mode is active for transparency"). `poker_solver/solver.py:48–56` does no logging. Recommended log line: `logger.info("solve(): dispatching to pushfold chart at %d BB effective stack", eff_bb)`. Affects observability, not correctness.

2. **`get_pushfold_strategy` raises `PushFoldChartUnavailable`, not `ValueError`, for out-of-range stack / unknown position** — spec §6 lines 162–163 (`Raises: ValueError`); audit prompt focus area 6 ("Error messages consistently use `ValueError`"). The implementation distinguishes a custom `PushFoldChartUnavailable` exception (`poker_solver/pushfold.py:30` and tests at `tests/test_pushfold.py:104, 114`). `PushFoldChartUnavailable` does NOT subclass `ValueError`, so `except ValueError` in caller code will not catch it. **Fix:** either make `PushFoldChartUnavailable` subclass `ValueError`, OR change these branches to raise `ValueError` directly per spec.

3. **No `force_tree_solve` kwarg on `solve()`** — spec §13 risk row R4 mitigation explicitly names this kwarg. Not exposed in `solver.solve()` (`poker_solver/solver.py:31–37`). Power users cannot bypass chart dispatch for testing. **Fix:** add `force_tree_solve: bool = False` param to `solve()` and gate the pushfold branch on `not force_tree_solve`.

4. **`test_pushfold_invalid_position_raises` deviates from spec §6** (`tests/test_pushfold.py:114–119`) — the test was patched (per user note) to expect `PushFoldChartUnavailable` instead of `ValueError`. The inline comment justifies it ("position 'bogus_position' isn't malformed input — it's an unsupported config") but the spec's `Raises: ValueError` clause was not updated. Either update the spec or have the test expect `ValueError`. This is the "patches applied during verification chain" item the orchestrator flagged for documentation.

5. **`test_pushfold_strategy_frequencies_sum_consistently` floor of `>= 80%` instead of `~1326` at d=2** (`tests/test_pushfold.py:208–214`) — the comment acknowledges the deviation from the published S-C landmark but is essentially documenting an undocumented HU-Nash variation. The threshold of 80% was chosen to fit the observed 90.3% combo coverage; the test is therefore a regression lock on the generator's specific output rather than a spec-grounded invariant. This is the second of the two patches the orchestrator flagged for documentation. **Fix:** add a comment cross-referencing the (not-yet-existing) spec amendment for §4 + §9 test 4.

6. **Strategic-equivalence collapse assertion absent from generator** — spec §10 ("strategic-equivalence collapse") requires the generator assert all combos within a hand class share strategy within `5e-3`. The generator (`scripts/generate_pushfold_charts.py`) instead solves an abstracted 169×169 matrix game where the per-class strategy is single-valued **by construction** (each hand class IS a single matrix-game infoset). The generation notes §1 document this as mathematically equivalent under suit symmetry, which is plausible — but spec §7 step 1 explicitly describes the alternate approach via a `PushFoldHUNL` subclass that runs DCFR on the preflop tree and then collapses to 169 classes with a within-class spread assert. The implementation skips the assert because the data structure cannot violate it. Either (a) amend spec §7 + §10 to acknowledge the matrix-game shortcut, OR (b) add a separate validation step that compares matrix-game output against a small tree-builder run at one depth (e.g. d=5) to catch any suit-symmetry-breaking abstraction error.

7. **`tests/test_pushfold_regen.py` smoke test missing** — spec §9 test 11 + §15 gate item 2 require it. Absent. Without it, `scripts/generate_pushfold_charts.py` can bit-rot under future refactors without CI catching it. **Fix:** add `tests/test_pushfold_regen.py::test_generator_smoke` per spec.

8. **`v1-placeholder` is an accepted version string at load time** (`poker_solver/pushfold.py:25` `PUSHFOLD_CHART_VERSIONS`) — `v1-placeholder` is documented in the generator (`scripts/generate_pushfold_charts.py:728`) as the dry-run output marker. Allowing it in the loader means a placeholder dry-run JSON would be silently accepted by `get_pushfold_strategy`. Strictly speaking, dry-run output should be rejected — the loader's job is to enforce that production data is canonical. **Fix:** drop `v1-placeholder` from `PUSHFOLD_CHART_VERSIONS` and have the generator either skip the JSON write on dry-run (it already does) or use a separate `_load_chart_data_placeholder` test hook.

9. **Spec §6 line 211 calls for two-action vectors `[fold_prob, jam_or_call_prob]` keyed by `HUNLPoker.infoset_key`** — the implementation keys instead by a custom string `f"pushfold|{position}|{eff_bb}BB|{hand}"` (`poker_solver/solver.py:302`). This is a documented departure: there is no real HUNL `infoset_key` for chart-derived plays (no game tree exists in the chart path). Recommend documenting the format explicitly in the public docstring of `solve_pushfold` / `_solve_pushfold_lookup` so downstream consumers know to use this format rather than expecting raw infoset keys.

10. **`game_value` returned as `0.0` for all chart dispatches** (`poker_solver/solver.py:308`) — spec §6 line 212 specifies `game_value: float — the SB's expected value in BB under both players' Nash strategies (computed once during chart generation and stored in the JSON metadata)`. The JSON does not store this; the solver returns 0.0. Downstream callers reading `result.game_value` will get a silently-wrong answer. **Fix:** either compute `game_value` from the chart strategies at lookup time (cheap — sum over hand-class joint prior), or persist per-depth `game_value_sb_bb` into the chart metadata.

11. **`exploitability_history` returned as `[0.0]`** (`poker_solver/solver.py:307`) — spec §6 line 213 specifies "single entry: the residual exploitability from the chart-generation solve, in bb/100." The JSON has per-depth values; the solver should surface the depth-specific value, not zero.

12. **No CLI integration despite spec §8 modify-list** — spec says "`poker_solver/cli.py` — add `--hunl-mode pushfold` option (or just have the existing `solve` subcommand auto-dispatch based on stack depth …)". `poker_solver/cli.py` is **not** in the diff (`git diff 351cbee..9f91c83 --stat`). Auto-dispatch via the library `solve()` partially covers this, but a CLI-level entry for the chart mode is absent.

13. **No reference to `solve_pushfold` symbol in `poker_solver/__init__.py:__all__`** — even if (1) is addressed, the public-API export list needs an addition.

14. **Spec §4 landmark "BB calls jam with ~67% of hands at 4 BB stacks (cf. S-C tables)" not tested** — the generation notes (§5) record observed 73.2% — a 6 pp delta from S-C. No test enforces the band. Should-fix: add a test asserting BB-call combo coverage at d=4 is in `[60%, 80%]`.

---

## Nice-to-fix

1. **`_canonical_hand_classes()` and `_all_hand_classes()` are duplicated in `pushfold.py`** (`poker_solver/pushfold.py:140` vs `poker_solver/pushfold.py:185`). Both enumerate the 169 canonical hand classes; the first uses string literals, the second uses `RANKS`. Pick one, drop the other.

2. **Chart JSON `notation` field is non-standard metadata** — spec §5 enumerates fields; `notation` is added. Innocuous but undocumented; either lock it into the spec or drop it.

3. **Chart JSON keys sorted by hand strength (descending pairs first, then suited by high card, etc.), not lexicographic** — spec §5 says "sorted by hand_class for deterministic diffing across regenerations." Lexicographic was probably the intent; hand-strength order is a reasonable alternative but should be explicitly documented in spec §5.

4. **`_coerce_freq` in the generator clips to 0.0 or 1.0 within `1e-4` then rounds to 4 decimals** (`scripts/generate_pushfold_charts.py:553–559`). The mid-range rounding to 4 decimal places loses solver-output precision; if a regeneration produces 0.6253 vs 0.6249 at a borderline combo, that's a meaningful regret signal swallowed by the rounding. Consider preserving full float precision in the JSON (cost: <10 KB extra; benefit: bit-exact reproducibility audits).

5. **`PUSHFOLD_CHART_VERSIONS` is a frozenset but only the loader checks it** — `is_pushfold_mode()` doesn't gate on it. If a future major-version bump ships, `is_pushfold_mode` could falsely return True for a config the loader then rejects. Minor; the loader catches it.

6. **README §"Push/fold charts (2-15 BB)" line 58** says "Exploitability after convergence is essentially 0 BB/100 (spec target was < 0.05)" — clarify that this is per-depth (matches the table in `docs/pushfold_v1_generation_notes.md`).

7. **`poker_solver/pushfold.py:185 _canonical_hand_classes()` is dead code** — only `_all_hand_classes()` is called by `get_full_range`. Remove.

---

## Looks good (explicit confirmation of audit focus areas)

1. **Chart JSON schema integrity (PARTIAL).** `version == "v1"` ✓ (`poker_solver/charts/pushfold_v1.json` line 2). `stack_depths_bb` is exactly `[2..15]` ✓. Both top-level chart keys (`sb_jam`, `bb_call_vs_jam`) present ✓. Per-cell hand_class union with implicit 0.0-default totals 169 ✓ (verified by scripted set-equality). All frequencies in `[0.0, 1.0]` ✓ (verified by exhaustive scan). Required metadata present: `generator` ✓, `generated_at` ✓, `ante` ✓ (=0.0), `small_blind` ✓ (=0.5), `big_blind` ✓ (=1.0), `iterations_per_solve` ✓ (=4000), `notes` ✓. **Failing:** `final_exploitability_bb_per_100` scalar (see must-fix 4).

2. **Lookup API correctness (PARTIAL).** `get_pushfold_strategy(stack_bb, position, hand) -> float` returns a float in `[0.0, 1.0]` ✓ (`poker_solver/pushfold.py:104`, verified by `tests/test_pushfold.py:54–67`). Case-insensitive hand parsing ✓ (`_canonicalize_hand` accepts `tt` → `TT`, `akS` → `AKs`). Hands not in chart return 0.0 (sparse default) ✓ (`poker_solver/pushfold.py:124`). `get_full_range` returns all 169 keys with sparse 0.0 fills ✓ (`poker_solver/pushfold.py:128–137`, the patch the orchestrator flagged — verified against `tests/test_pushfold.py:94–101`). **Failing:** `get_pushfold_range` spec name (see must-fix 3), `solve_pushfold` (see must-fix 1), backend string (see must-fix 2).

3. **Dispatch logic in solver.py.** `solve(game, ...)` short-stack dispatch correct: gated on `isinstance(game, HUNLPoker) AND starting_street == Street.PREFLOP AND is_pushfold_mode(...)` (`poker_solver/solver.py:51–56`). This is the **PREFLOP-only guard** the orchestrator flagged — verified by `tests/test_pushfold.py:147 test_pushfold_mode_not_triggered_for_river_subgame_at_short_stack`. Dispatch does NOT trigger for stack > 15 BB ✓ (verified at `tests/test_pushfold.py:167 test_pushfold_mode_not_triggered_at_long_stack`). Dispatch does NOT trigger for non-HUNL games ✓ (the `isinstance(game, HUNLPoker)` guard). **Failing:** dispatch is not silent-with-INFO-log (should-fix 1); no `force_tree_solve` (should-fix 3).

4. **I/O discipline — no unexpected disk reads.** `_load_chart_data` is decorated with `@lru_cache(maxsize=1)` (`poker_solver/pushfold.py:39`) ✓. Chart loaded via `importlib.resources.files("poker_solver.charts").joinpath(_CHART_RESOURCE)` ✓ (`poker_solver/pushfold.py:42`). Cache is module-level lru_cache; repeated calls do NOT re-read the file. No `__file__`-relative path manipulation found.

5. **Generated chart values vs published S-C anchors (PARTIAL).** `AA` `sb_jam` == 1.0 for all `d ∈ [2, 15]` ✓ (verified across the JSON). `KK` ✓, `AKs` ✓ at all `d ∈ [2, 15]`. `72o` `sb_jam` == 0.0 for `d ≥ 2` (not just `d ≥ 6` as spec required) ✓ — `72o` never jams in the committed chart. **Failing:** spec §9 test 4 / §4 landmark "at d=2 SB jams 100% of all 169 classes" — 12 hand classes jam 0.0 at d=2 (see must-fix 6). Spec §4 landmark "BB calls with ~67% at d=4" — observed 73.2%; within ~5 pp of S-C anchor, undertested (should-fix 14).

6. **Error handling consistency (PARTIAL).** `get_pushfold_strategy` raises on malformed hand notation ✓ (`tests/test_pushfold.py:109`). No `AssertionError` / `RuntimeError` / `KeyError` used in `pushfold.py` paths. **Failing:** stack-out-of-range and unknown position raise `PushFoldChartUnavailable` rather than `ValueError` (should-fix 2); `_solve_pushfold_lookup` silently clamps instead of raising (must-fix 5).

7. **Tests use the public API only.** `tests/test_pushfold.py` imports only from `poker_solver` and one Street reference from `poker_solver.hunl` (`tests/test_pushfold.py:13–23, 154`). No imports of `_CHARTS`, `_load_charts`, `_load_chart_data`. No assertions on internal cache structures. No `lru_cache.cache_info()` introspection.

8. **No new dependencies added.** `git diff 351cbee..9f91c83 -- pyproject.toml` shows exactly: version bump 0.2.0 → 0.3.0, and added `[tool.maturin] include = ["poker_solver/charts/*.json"]` for wheel bundling. `[project.dependencies]` and `[project.optional-dependencies]` unchanged ✓.

9. **License compliance — chart data provenance.** Verified clean: see "License compliance" section below.

10. **Strategic-equivalence collapse correctness (DEVIATION FROM SPEC).** Spec §10 requires the generator collapse 1326 combo-specific infosets to 169 hand-class entries and assert within-class spread `< 5e-3`. Implementation (`scripts/generate_pushfold_charts.py`) instead solves an abstracted 169×169 matrix game where each hand class is a single infoset by construction — the within-class assert is vacuously satisfied. `docs/pushfold_v1_generation_notes.md` §1 documents this as mathematically equivalent under suit symmetry. Not flagged as a must-fix because the equivalence is plausible and the generator is well-documented, but spec/code drift logged under should-fix 6.

11. **Convergence gate (PARTIAL).** Per-depth exploitability `0.0000 – 0.0001 bb/100` (`docs/pushfold_v1_generation_notes.md` §6) — well under the < 0.05 spec target ✓. Generation notes report this is the *final* (post-convergence) value, not an early-iteration estimate ✓. **Failing:** the spec-required scalar `final_exploitability_bb_per_100` is absent from the JSON metadata (must-fix 4), so a load-time gate cannot fire.

---

## Spec coverage gaps (missing tests)

1. **Spec §6 `solve_pushfold(config) -> SolveResult` public API** — not tested because it does not exist (must-fix 1). Suggested test: `test_solve_pushfold_returns_solveresult` (spec §9 test 8). Suggested name in failing-state: `test_solve_pushfold_public_api`.
2. **Spec §6 `force_tree_solve` kwarg** — not tested because it does not exist (should-fix 3). Suggested test: `test_force_tree_solve_bypasses_chart_dispatch`.
3. **Spec §6 INFO log on dispatch** — not tested. Suggested test: `test_pushfold_dispatch_emits_info_log` (use `caplog.set_level(logging.INFO)`).
4. **Spec §9 test 4 "at d=2 SB jams 100% of hands"** — the closest existing test (`test_pushfold_strategy_frequencies_sum_consistently` line 208) lowers the floor to 80%; the explicit 100% landmark is not gated. See must-fix 6.
5. **Spec §9 test 5 "at d=4 BB calls AA/KK/QQ/AKs with frequency 1.0"** — not directly tested; covered indirectly by `test_pushfold_returns_frequency_in_zero_to_one_range`.
6. **Spec §9 test 6 "at d=10 SB jam range is ~30% ± 5% of hands"** — not tested. Generator output (~58% at d=10 combo-weighted) **fails this band**, suggesting the spec's 30% figure may need re-anchoring against the matrix-game output OR the chart is materially different from the published reference. **Important to investigate.**
7. **Spec §9 test 7 "`get_pushfold_strategy(10, 'sb_jam', 'AA') == 1.0`; `get_pushfold_strategy(15, 'sb_jam', '72o') == 0.0`"** — partially covered by `test_pushfold_aa_always_jammed_at_all_depths` (line 70) and `test_pushfold_72o_never_jammed_at_15bb` (line 75).
8. **Spec §9 test 9 "top-level `solve(HUNLPoker(cfg_10bb))` returns chart-backed result without invoking DCFR"** — covered by `test_pushfold_mode_dispatch_at_short_stack` (line 138).
9. **Spec §9 test 10 "`solve_pushfold(cfg_with_50bb_stack)` raises `ValueError`"** — not implemented (must-fix 1, must-fix 5).
10. **Spec §9 test 11 "`tests/test_pushfold_regen.py::test_generator_smoke`"** — file does not exist (should-fix 7).
11. **Spec §9 test 12 "top-20 hands of d=4 SB jam list overlap by ≥ 90% with published S-C top-20"** — not tested. The generation notes §5 mention manual cross-checking but no automated literature-overlap gate exists.

---

## License compliance

**Chart data is computed from our own DCFR solver — clean.**

Evidence:
- `poker_solver/charts/pushfold_v1.json` metadata field `generator: "scripts/generate_pushfold_charts.py"` ✓.
- `docs/pushfold_v1_generation_notes.md` §1–§2 document the full pipeline: 169 hand classes, 169×169 Monte-Carlo equity matrix, DCFR `(α, β, γ) = (1.5, 0, 2)`, 4000 iterations per stack depth, ~5.2 min total runtime on a MacBook M-series.
- `iterations_per_solve: 4000` in the JSON matches the value reported in the generation notes §6.
- No references to HRC, ICMIZER, GTO Wizard, or Holdem Resources as data sources in `poker_solver/pushfold.py` or `scripts/generate_pushfold_charts.py` (`grep -ni "HRC|ICMIZER|GTOWizard|GTO Wizard|Holdem Resources"` returns empty for the implementation files).
- Sklansky-Chubukov is referenced only for *validation* anchors (`scripts/generate_pushfold_charts.py:88–125 SKLANSKY_ANCHORS`) — these are publicly-known endpoint values (AA jams 100%, 72o folds at ≥ 6 BB) and the spec §4 explicitly authorizes using S-C as a sanity-check anchor, not as data.
- Brown & Sandholm 2019 (DCFR) and Zinkevich et al. 2007 (CFR) are the only academic references for solver methodology (`docs/pushfold_v1_generation_notes.md` §9).

No commercial-source contamination found. No AGPL contamination found.

---

## Overall verdict

**NOT READY — see must-fix.**

The pure-lookup path (`get_pushfold_strategy`, `get_full_range`, the `lru_cache` resource load, the PREFLOP-only dispatch guard) is solid, the chart data is genuinely DCFR-computed and well-documented, and the test coverage on the actual exposed surface is clean. However, the spec's public-API contract from §6 (`solve_pushfold`, `get_pushfold_range`, `backend == "pushfold_chart"`, `force_tree_solve`, `ValueError` for out-of-range, `final_exploitability_bb_per_100` in JSON, `game_value` populated) is materially under-implemented: a downstream consumer following the spec literally would hit ImportErrors and silently-wrong return values. Six of these qualify as must-fix by the audit prompt's silent-wrong-answer rule. Additionally, spec §9 test 4's universal-jam-at-d=2 landmark is contradicted by the committed chart and the relaxed test at `tests/test_pushfold.py:208` — this needs either a spec amendment or a regeneration. Address the six must-fix items and resolve the spec-amendment-or-regen question for the d=2 jam coverage, then the PR is ready.
