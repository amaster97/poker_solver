# PR 7 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** `pr-7-noambrown-diff` (working tree, uncommitted; integration tip `6c438b8`)
**Diff size:** 2 modified (`pyproject.toml`, `tests/test_hunl_diff.py`) + 6 new (`poker_solver/parity/__init__.py`, `poker_solver/parity/noambrown_wrapper.py`, `scripts/build_noambrown.sh`, `tests/data/river_spots.json`, `tests/test_river_diff.py`, `tests/test_river_diff_self_sanity.py`) = +2112 / -6 LoC (per `git stash show stash@{0}` line counts).

**Test status:** Not executed (audit-only). Binary may or may not be built; collection-time defensive imports + per-test skip guards keep collection green either way.

---

## Must-fix

### M1. Agent C's self-sanity module is the WRONG module — it does not satisfy spec §10 Agent C deliverables.

**File:** `tests/test_river_diff_self_sanity.py:1-278`

The committed self-sanity file is a **binary-required smoke test** with only **4 tests** that all call `_require_brown_binary()` (line 53–60) and skip if the binary is missing. Spec §10 Agent C is explicit (and `audit_prompt_final.md:147-156` re-states): the self-sanity module must

> "run without Brown's binary … 8 tests …"

and enumerates them:
1. `test_each_spot_loads_into_hunl_config`
2. `test_each_spot_solver_converges` (2000 iters, expl < 0.02 × pot)
3. `test_each_spot_game_value_is_finite`
4. `test_canonicalize_history_roundtrip` (10 hand-built cases per `agent_c_prompt.md:162-191`)
5. `test_strategy_matrix_shape`
6. `test_no_overlap_in_fixture_ranges`
7. `test_iterations_override_respected`
8. `test_brown_binary_finder_returns_path_or_none`

**Zero of the 8 spec-mandated tests are present.** The actual tests committed are: `test_brown_binary_help_flag_succeeds`, `test_brown_binary_runs_trivial_dcfr_in_out`, `test_brown_binary_exploitability_finite_at_smoke_iters`, `test_brown_binary_seed_determinism`. These are useful Brown-side smoke tests but they belong somewhere else (or alongside) Agent C's deliverable — they cannot substitute.

**Why must-fix:** the 10-case round-trip test in spec §10 #4 / `agent_c_prompt.md:162-191` is the only thing that would have caught the case-8 round-trip defect surfaced under M2 below. Without that test, every silent canonicalization regression in PR 7+ ships unchallenged. Agent C is also "layers 3-4 of the 5-layer skipif strategy" per `audit_prompt_final.md:8`; replacing it with a Brown-required smoke test collapses two skipif layers.

**Fix:** rewrite `tests/test_river_diff_self_sanity.py` to implement the 8 spec-listed tests against Agent A's wrapper module, with NO `_require_brown_binary()` gate. Move the existing 4 smoke tests to a separate `tests/test_river_diff_brown_smoke.py` (or fold into Agent B's `test_river_diff.py` under a `parity_noambrown` marker — they're already binary-gated).

---

### M2. Hand-built all-in round-trip diverges under default state helper (case 8 of agent_c_prompt round-trip fixture).

**File:** `poker_solver/parity/noambrown_wrapper.py:806-824` (`_state_for_default_river_pot`) + `:1000-1017` (`A` branch in `_walk_our_tokens`).

The default-state helper sets `stack = 2**31 - 1` (a sentinel; line 821) so the all-in branch (line 1004: `new_total = state.stack`) emits `("r", 2147483647)` (or `("b", 2147483647)`) — but Brown's same history emits `("r", actual_total)`. The two canonicalizers disagree by orders of magnitude in any hand-built history that contains an `A` token.

Concrete failure for case 8 (`"b500/r9000"` ↔ `"b500A"` per `agent_c_prompt.md:175-176`) using `_state_for_default_river_pot(initial_pot=1000)`:

- `canonicalize_brown_history("b500/r9000")` → `(("b", 1000), ("r", 10000))`
- `canonicalize_our_history("b500A")` → `(("b", 1000), ("r", 2147483647))`

These do NOT match, so the round-trip identity test mandated by spec §10 Agent C #4 (which `agent_c_prompt.md:162-191` will assert) will fail. The harness path itself (which always supplies `spot=` to canonicalizers — see `noambrown_wrapper.py:1117`) uses `_state_for_history` which sets `stack = half + spot.stack`, so the actual diff test runs correctly. The bug is in the default-state helper only.

**Why must-fix:** silently mis-canonicalizes any hand-built all-in case the moment Agent C's round-trip test (M1) is implemented. Without M1's test, the bug is latent. Together they form one defect.

**Fix:** either (a) require callers of the canonicalizers to supply a `RiverSpot` (or at least a `stack` arg) when histories may contain `A`, raising `ValueError` if `state.stack` is the sentinel and an `A` is parsed; or (b) accept an `initial_stack: int | None` kwarg on both canonicalizers and propagate to `_state_for_default_river_pot`. The agent_c round-trip fixture would then pass `initial_pot=1000, initial_stack=9500` for cases 8–10.

---

### M3. Spec-mandated canonical amount disagrees with `agent_c_prompt.md` test fixture for cases 5–10.

**File:** `poker_solver/parity/noambrown_wrapper.py:36-39, 832-857, 919-948` (canonicalizer docstrings + dispatch).

Wrapper's canonical form encodes amounts as **post-initial-contribution to-total** (i.e. includes the base-pot half each side has contributed). Example: with pot=1000, `b500` (Brown) and `b500` (ours) both canonicalize to `("b", 1000)`, **not** `("b", 500)` as `agent_c_prompt.md:165-173` expects (the prompt's expected values are 500-based, treating amount as chips-added).

The wrapper is **self-consistent**: both Brown and our canonicalizer feed the same state machine with the same initial-pot-half-each starting state, so round-trip identity holds for non-all-in tokens. But `agent_c_prompt.md:170-191` lists hand-coded expected values that assume amounts are net-of-base-pot.

**Why must-fix:** Agent C's spec-mandated round-trip test (M1) imports the agent_c_prompt's `test_cases` list verbatim. As written it will fail on cases 5–10 even though the canonicalizer is internally correct. Either the prompt is wrong, or the canonicalizer's convention drifts from spec §5 step 5 (which only specifies the raise transform, not the absolute base).

**Fix:** resolve the spec ambiguity, then either (a) update `agent_c_prompt.md:165-191` expected values to match the wrapper's convention (`("b", 1000)`, `("b", 500)` → `("r", 9500)` becomes `("b", 1000)`, `("b", 500)` → `("r", 10000)`), or (b) change the canonicalizer to subtract `initial_pot // 2` from each amount before emitting (and update the wrapper docstring). Recommend (a) — fewer code changes, and the to-total-in-chip-accounting form is what the harness's diff actually compares.

---

## Should-fix

### S1. Test filenames diverge from spec.

`tests/test_river_diff.py` and `tests/test_river_diff_self_sanity.py` should be `tests/test_noambrown_river_parity.py` and `tests/test_noambrown_self_sanity.py` per spec §7 Files-to-create table and `audit_prompt_final.md:33-37`. Internal docstrings already reference `test_noambrown_river_parity.py` (e.g. `tests/test_river_diff_self_sanity.py:5`). Cosmetic but breaks grep-by-spec.

**Fix:** rename both files. No code changes required.

---

### S2. `run_brown_solver` uses `tempfile.mkdtemp` instead of `NamedTemporaryFile`.

**File:** `poker_solver/parity/noambrown_wrapper.py:574`

Spec §9 risk #8 and `audit_prompt_final.md:113` mandate `tempfile.NamedTemporaryFile(suffix=".json", delete=False)`; the wrapper instead uses `tempfile.mkdtemp(prefix=f"noambrown_{spot.id}_")` (line 574). Functionally equivalent for xdist collision safety (both produce unique paths), but the spec deviation is unflagged and there is no comment justifying the substitution.

`audit_prompt_final.md:115-116` adds: "**`os.unlink` in `finally`** — verify cleanup on exception path." The wrapper uses `shutil.rmtree(workdir, ignore_errors=True)` (line 640) inside `finally` (line 634) — also functionally equivalent. No actual collision risk.

**Fix:** add an inline comment at line 574 documenting the substitution (e.g. "spec §9 #8 spec says `NamedTemporaryFile`; we use `mkdtemp` to scope both config + dump under one cleanable directory"). Optionally switch to `NamedTemporaryFile` literal compliance.

---

### S3. Wrapper's `_DEFAULT_BROWN_SEED = 7`, but smoke test in self-sanity uses `SMOKE_SEED = 42`.

**File:** `tests/test_river_diff_self_sanity.py:50` vs `poker_solver/parity/noambrown_wrapper.py:161`

Spec §11 #1 mandates `--seed 7` "for paranoia" because that's Brown's default. The harness (`tests/test_river_diff.py:66`) uses `BROWN_SEED: int = 7`, but `test_river_diff_self_sanity.py:50` uses `SMOKE_SEED: int = 42`. Internally consistent (each file picks one); but the smoke test won't exercise the seed-7 codepath that the parity test relies on.

**Fix:** align `SMOKE_SEED` to 7 so the determinism smoke test exercises the same RNG state Agent B's diff uses. Optional but tightens the chain.

---

### S4. `iterations_run` is vacuously equal to `iters` (does not actually verify Brown ran the requested count).

**File:** `tests/test_river_diff.py:358-362` + `poker_solver/parity/noambrown_wrapper.py:644-650`

`brown_dump.iterations_run` is set in `_parse_brown_dump(iterations_run=int(iterations), ...)` (line 646) — from the passed-in arg, NOT from anything Brown emits. So the harness's `assert brown_dump.iterations_run == iters` (test_river_diff.py:359) is structurally always true. If Brown's binary silently runs fewer iters (e.g. a `--iters` parse failure falling back to default 2000), the test won't notice.

**Fix:** parse Brown's stdout "Discounted CFR: iters=N" marker (Brown emits this — see `tests/test_river_diff_self_sanity.py:170-176`'s `"Discounted CFR: iters=N Exploitability (chips): ..."`) and populate `iterations_run` from the parsed N. Add a `_ITERS_RE` regex alongside `_EXPL_RE`.

---

### S5. Build script soft-fail surface: `set -e` interacts with `find ... | grep -q .`

**File:** `scripts/build_noambrown.sh:19, 37-44`

The script has `set -euo pipefail` (line 19). The idempotency probe (line 37) uses `find ... -newer "$BIN" -print -quit | grep -q .`. Under `set -e`, if grep finds NO match (empty newer set), the exit code is 1 and the script would abort — except the construct is inside an `if` branch, which immunizes the exit code. `audit_preprep.md §1.7` pre-flagged this as a risk; the actual code handles it correctly because the `find | grep` is the test-condition of `if`, not a bare command. Looks correct.

**However**, line 39 has the same pattern checking `CMakeLists.txt`: `if find "$SRC/CMakeLists.txt" -newer "$BIN" -print -quit 2>/dev/null | grep -q .;`. If `$SRC/CMakeLists.txt` does not exist, `find` produces stderr (suppressed) AND exits non-zero; under `set -e` inside `if`, still safe. Looks correct.

The deeper concern: Brown's CMakeLists.txt does not actually use `<filesystem>` (a common Xcode CLT pain point) — confirmed by `references/code/noambrown_poker_solver/cpp/CMakeLists.txt`. So the soft-fail-on-missing-Xcode-CLT scenario per `audit_preprep.md §1.7 (b)` would manifest as a `cmake --build` failure, not a missing-compiler failure, and the script would `exit 1` not `exit 0`. That's a defect for genuine Xcode-CLT-missing hosts.

**Fix:** wrap `cmake --build "$BUILD" -j` in an explicit `if ! cmake --build ...; then echo "compile failed (likely missing Xcode CLT or stdlib header)"; exit 0; fi`. Soft-fail on compile errors too. Audit prompt §1 of focus area 1 explicitly enumerates "Xcode CLT missing → soft-fail catches" as layer 3 of the 5-layer skipif strategy.

---

### S6. Self-sanity smoke tests overlap with `test_brown_binary_buildable` in `test_river_diff.py`.

**File:** `tests/test_river_diff_self_sanity.py:63-87` vs `tests/test_river_diff.py:459-491`

Both test that the binary exists and runs. Spec §10 Agent C is explicit: self-sanity tests "run without Brown's binary." The committed self-sanity file requires the binary, duplicating what Agent B's infra test already does. Should fold into Agent B's module (already binary-gated under `parity_noambrown`).

**Fix:** see M1.

---

### S7. `our_strategy_to_brown_matrix` silently drops unrecognized infoset keys.

**File:** `poker_solver/parity/noambrown_wrapper.py:1095-1115`

If `key.split("|")` does not produce 4 parts (line 1097-1100), the entry is silently skipped. Same for unrecognized holes (line 1112-1116). In a well-formed river fixture these branches should be unreachable; if they fire silently, diff coverage drops and the 80% gate may not trigger.

**Fix:** add a `warnings.warn(...)` (or an opt-in `strict=True` kwarg) when entries are skipped, so silent coverage loss surfaces. Currently the only signal is the 80%-coverage assertion in Agent B's test — which is downstream and harder to diagnose.

---

### S8. Wrapper does not validate `iterations_override` upper bound or `bet_sizes` lower bound.

**File:** `poker_solver/parity/noambrown_wrapper.py:332-374`

`bet_sizes` is validated as `0.0 < fv <= 5.0` (line 345) — open interval at 0 is correct (spec §4: `"bet_sizes as pot fractions in (0, 5]"`). `iterations_override` is validated as `>= 1` (line 369) — but no upper cap; a fixture spec'ing 10**9 iters would be accepted and presumably hang. Risk #6 of spec §9 anticipates per-spot overrides up to ~10000. A 100k cap would be safer.

**Fix:** add an upper bound on `iterations_override`, e.g. 200_000. Cosmetic — the timeout will catch it eventually, but loudly-rejected-at-load beats subprocess.TimeoutExpired-3-hours-into-CI.

---

## Nice-to-fix

### N1. `RiverSpot._board_note` field referenced in spec §4 example is not in the dataclass.

The spec §4 fixture example contains a placeholder `_board_note`; the fixture file omits it (correct) and the dataclass doesn't require it. Spec is the source of truth — the example is illustrative only. No action needed.

### N2. `_parse_combo` permits invalid hand strings to surface a 4-char-only error before card-level validation.

**File:** `poker_solver/parity/noambrown_wrapper.py:236-239`

Returns a 4-char error message that doesn't show what was tried. For an obvious malformed string like `"Ax2y"` the error is fine; for `"AhKxQc"` (6 chars) it just says "must be 4 chars." Polish.

### N3. Comment at `noambrown_wrapper.py:781` says "stack here is the per-player effective stack at street start (i.e. not yet decremented)"; in practice `state.stack` is initialized to `half + spot.stack` per `_state_for_history()` (line 800) which is "total ceiling," not "effective stack at street start." Wording slip.

### N4. `_HistoryState.actor_remaining()` is defined but never called (line 776-781).

Dead helper; can drop or wire into all-in delta validation.

### N5. Many integer-conversion sites use `int(spot.pot)` even though `spot.pot` is already `int` per dataclass. Defensive but redundant.

### N6. `tests/test_river_diff.py:329-333` has a slightly confusing skip path on sentinel `None`: it calls `_require_wrapper()` + `_require_fixture()` then `pytest.skip(...)` with a different reason. Either of the first two `skip`s would short-circuit; the final `skip` is unreachable when wrapper+fixture are present (in which case the sentinel is `None` because `load_spots` failed silently, which the docstring of `_collect_spots` allows). Either tighten the comment or restructure.

---

## Looks good (explicit confirmation of audit focus areas)

1. **Build script idempotency + soft-fail.** `scripts/build_noambrown.sh:19, 36-44, 49-58` — `find ... -newer "$BIN" -print -quit | grep -q .` correctly handles "no source newer than binary" (returns false → `else` branch → no-op). Soft-fail on missing cmake / `c++`/`g++`/`clang++` (line 54: triple-tool check across macOS+Linux). `exit 0` on missing tools, not `exit 1`. Build is out-of-tree under `$SRC/build`. `set -euo pipefail` does NOT pre-empt the soft-fail branch because each `command -v ... || { echo; exit 0; }` short-circuits before `set -e` can fire on the failed lookup. References' `build/` is gitignored at `references/code/.gitignore:26,30` AND at repo-root `.gitignore:46` (which excludes the entire `references/` tree). Verified `set -e` does not break the soft-fail. See S5 for the gap on Xcode-CLT-missing compile failure.

2. **Raise-encoding canonicalization (HIGH-PROB, paragraph-level discussion mandated).** `poker_solver/parity/noambrown_wrapper.py:884-916` (Brown side) and `:1018-1037` (ours side). **Brown direction:** `r<extra>` token → `new_total = max(c0,c1) + extra`, which precisely inverts Brown's emission at `cpp/src/main.cpp:192-194` (`raise_amount = delta - to_call`, where `delta = child_contrib - actor_contrib` and `to_call = max(...) - actor_contrib`, hence `raise_amount = child_contrib - max(...)` and inverting gives `child_contrib = max(...) + raise_amount`). Mathematically sound. **Our direction:** `r<to_total>` token → `new_total = int(m.group(1))` — emits literally. **State reset between streets:** the wrapper only handles single-street river subgames (per PR 7 spec §3 non-goals) and tolerates leading `/` separators (lines 977-980) for empty prior streets. Multi-street state reset is out of scope for PR 7, but the canonicalizer does not validate that the input is river-only — a multi-street history would silently mis-aggregate contributions across the boundary. Future-proofing concern, not a PR 7 defect. **Aggressor tracking:** Brown's `r<extra>` is opponent-anchored (`max(c0,c1) + extra`), so check-raise sequences work correctly: after `c/c` actor flips correctly (lines 879, 996) and after a raise the next `r` reads the new max. **Case 8 round-trip:** see M2 — fails in the default-state helper, passes when a spot is supplied. The harness-side path always supplies a spot (`canonicalize_our_history(history_substr, spot=spot)` at line 1117), so production diff runs are unaffected by the latent bug.

3. **All-in token mapping.** `poker_solver/parity/noambrown_wrapper.py:1000-1017` — `A` branch checks `to_call = state.to_call()` and emits `("b", remaining)` if `to_call == 0` else `("r", remaining)`. Matches spec §5 step 5 mapping rules. The branch uses `new_total = state.stack` (line 1004), which is correct when `state.stack` is set to `half + spot.stack` (per `_state_for_history`, line 800). Latent bug when `state.stack` is the sentinel — see M2.

4. **DCFR flag invocation correctness.** `poker_solver/parity/noambrown_wrapper.py:580-598` — argv constructs `["--algo", "dcfr", "--iters", str(int(iterations)), "--dcfr-alpha", "1.5", "--dcfr-beta", "0.0", "--dcfr-gamma", "2.0", "--seed", str(int(seed))]`. β passed as `"0.0"` (not `"0.5"` — correct). γ passed as `"2.0"` — `audit_preprep.md §1.2` flagged that Brown's CLI parses these as floats not ints (verified at `cpp/src/main.cpp:594-596`: `opts.dcfr_gamma = std::stod(argv[++i])`), so `"2.0"` parses correctly. Seed=7 explicitly passed via `_DEFAULT_BROWN_SEED = 7` (line 161); spec §11 #1 paranoia satisfied. Iterations default = 2000 (line 165); spec §5 step 2 satisfied. Per-spot override threaded via `spot.iterations_override` in Agent B's test (`tests/test_river_diff.py:338`).

5. **Fixture file schema integrity.** `tests/data/river_spots.json:1-19` — exactly 15 spots (counted: `dry_K72_rainbow`, `dry_A83_rainbow`, `dry_Q52_mixed`, `wet_T98_5h2h`, `wet_JT9_4h3s`, `wet_876_5d2h`, `monotone_AKs7s`, `monotone_TJ5h`, `monotone_QJ94s`, `paired_AA7`, `paired_K77`, `paired_JTT`, `broadway_AKQJ2`, `broadway_KQJT4`, `broadway_ATJQK`). `schema_version: 1` (line 2). All 15 have `pot: 1000`, `stack: 9500`, `max_raises: 3`, `include_all_in: true`. Bet sizes are pot fractions in (0, 5]: range from `0.5` to `1.5`. Categories cover all 5 of dry/wet/monotone/paired/broadway, each with exactly 3 spots. Range sizes appear to be 30+ per side (counted ≥45 for spot 1; loader enforces ≥30 at `noambrown_wrapper.py:431`). Board overlap check enforced at `noambrown_wrapper.py:415-419`. Equal-stack assertion is implicit from the single `stack` field. Whole-BB pot+stack: `1000 % 100 == 0` ✓, `9500 % 100 == 0` ✓. File size 25,830 bytes < 100 KB ceiling.

6. **Tolerance threshold.** `tests/test_river_diff.py:60-61` — `PER_ACTION_TOL: float = 5e-3`, `PER_GAME_VALUE_REL_TOL: float = 1e-3`. Both used in production assertions (lines 410, 442). No silent loosening. Self-sanity file (`test_river_diff_self_sanity.py`) has no tolerance literal because it does not perform any cross-engine comparison — correct.

7. **Skip-cleanly-when-binary-missing path.** `tests/test_river_diff.py:188-197` (`_require_brown_binary`) emits `pytest.skip(...)` with informative message + build-script hint. The 5-layer skipif strategy is documented in lines 25-38 and exercised correctly. `find_brown_binary()` returns `Path | None` and never raises (`noambrown_wrapper.py:457-488`). Layer A (defensive imports) at lines 85-127 keeps collection green even if the wrapper module fails to import.

8. **License + attribution.** `references/code/noambrown_poker_solver/LICENSE:1` confirmed `MIT License Copyright (c) 2025 Noam Brown`. Wrapper docstring at `poker_solver/parity/noambrown_wrapper.py:1-14` carries the spec §8 attribution header verbatim (URL, license, repo name, "no source code from that repo is copied here"). Pure-invoke-via-subprocess model; the wrapper depends only on (a) Brown's CLI flag surface, (b) Brown's JSON output schema, (c) Brown's subgame config JSON schema — all public interface. No C++ code copy. The package init at `poker_solver/parity/__init__.py:1-22` mirrors the convention. Cross-checked: no Brown algorithm logic appears in the canonicalizer (it operates only on the action-token stream, not Brown's tree-construction algorithm). Compliant.

9. **Subprocess + xdist safety (HIGH-PROB, paragraph-level mandated).** `poker_solver/parity/noambrown_wrapper.py:574` uses `tempfile.mkdtemp(prefix=f"noambrown_{spot.id}_")` — per-call unique directory; xdist parallel runs on the same spot never collide because `mkdtemp` adds a random suffix. Cleanup via `shutil.rmtree(workdir, ignore_errors=True)` at line 640 is inside `finally` (line 634), so it runs on exception. Spec §9 #8 prescribes `NamedTemporaryFile` — see S2 for the literal-deviation note; behavior is equivalent. **Sub-probe (a) `--bet-sizes` quoting:** the wrapper does NOT pass `--bet-sizes` at all (line 580-598 argv); instead, bet sizes go into the subgame config JSON (`write_brown_config:520-535`). Brown reads `bet_sizes` from config at `cpp/src/subgame_config.cpp:381-383`. CLI override is `--bet-sizes` and is unused by the wrapper. Avoiding the CLI flag means the wrapper sidesteps the comma-joined-string question entirely. Audit-prompt risk §9.a does not apply because the surface is bypassed. **Sub-probe (b) stdout vs JSON file:** `dump_path = workdir / "strategy.json"` (line 577); `subprocess.run(..., check=True, capture_output=True)` (line 600); `json.load(open(dump_path))` (lines 613-614) — strategy parsed from FILE, stdout salvaged only for forward-compat exploitability + game-value scraping (lines 620-633). Not parsed-as-JSON. Correct per spec §9 #8 (b). **Sub-probe (c) timeout:** `_DEFAULT_TIMEOUT_SEC = 600.0` (line 169); test harness uses `BROWN_TIMEOUT_SEC: float = 600.0` (line 75). 2000 iters on a typical M-series machine ≈ 30-90 s per `audit_preprep.md §1.1 (c)`; 600 s is a paranoid ceiling, NOT too tight. Spec §5 runtime budget is ~30s/spot; 600s leaves 10× headroom. Per-spot `@pytest.mark.timeout(int(BROWN_TIMEOUT_SEC) + 60)` (line 306) gates the test itself. Compliant. **Path anchoring (spec §9 #9):** `find_brown_binary()` at line 469 uses `Path(__file__).resolve().parents[2]` — anchored to repo root via `parity → poker_solver → repo`. Compliant.

10. **Strategy-matrix adapter.** `poker_solver/parity/noambrown_wrapper.py:1048-1144` (`our_strategy_to_brown_matrix`) — walks `result.average_strategy`, parses `infoset_key.split("|")` into `(hole, board, street, history)`, maps hole back to player via membership in `hand_index_p0/p1`, canonicalizes the history substring, and materializes per-(canonical_history, player) numpy arrays of shape `(num_hands, num_actions)`. The harness wires this to Brown's matrix shape at `tests/test_river_diff.py:364-373`. Internal action-count consistency check at line 1133-1138 raises on inconsistent infoset shapes. Hands-not-in-strategy default to zero rows (line 1140). See S7 for the silent-drop concern.

11. **80% history-coverage assertion.** `tests/test_river_diff.py:378-391` — `coverage = len(shared) / max(len(brown_keys), 1)`; `pytest.fail(...)` if `coverage < COVERAGE_FLOOR` (= `0.80` at line 71). Brown's keys are unioned across both player profiles (lines 378-380); ours come from the canonical-history dict (line 381). Shows first 5 missing keys on failure for diagnostics. Per spec §10 Agent B.

12. **Pytest marker registered.** `pyproject.toml:42` registers `parity_noambrown` with description matching spec §10 Agent B + §12 #6. No duplicate of `parity` / `external` markers (existing markers at lines 40-41 are `slow` and `very_slow`). Decorator at `tests/test_river_diff.py:305, 457`. Compliant.

13. **Pot/stack units consistency.** `tests/test_river_diff.py:440` hard-codes `big_blind = 100` for the chip-to-BB conversion of `our_result.game_value` (which is in BB-units per PR 5). Spec §12 open decision 4 prescribes `pot=1000, stack=9500, big_blind=100`; fixture line 4 uses exactly that. The wrapper's subgame JSON writer at `noambrown_wrapper.py:520-535` writes `pot` and `stack` as integer chips — Brown reads them as integers per `cpp/src/river_game.h:36-38`. Units align.

14. **No new third-party dependencies.** `poker_solver/parity/noambrown_wrapper.py:42-56` imports only stdlib (`contextlib`, `json`, `re`, `subprocess`, `tempfile`, `dataclasses`, `pathlib`, `typing`), numpy, and `poker_solver.card` / `poker_solver.solver`. `pyproject.toml:19` dependencies unchanged (`["numpy>=1.24", "psutil>=5.9"]`). Compliant.

15. **Self-sanity test scope (Agent C).** See M1 — the committed file does NOT match the spec. The 8 spec-mandated tests are absent. Status: **defect**, not "looks good." (Re-stating for the section's enumeration completeness.)

---

## Spec coverage gaps (missing tests)

- **Spec §5 step 5 (raise canonicalization round-trip):** spec §10 Agent C #4 mandates `test_canonicalize_history_roundtrip` with 10 hand-built cases. **Not implemented.** Required test name: `test_canonicalize_history_roundtrip` in `tests/test_river_diff_self_sanity.py` (or `test_noambrown_self_sanity.py` per S1).
- **Spec §10 Agent C #1 (config loading):** `test_each_spot_loads_into_hunl_config`. **Not implemented.**
- **Spec §10 Agent C #2 (convergence at 2000 iters):** `test_each_spot_solver_converges` (expl < 0.02 × pot). **Not implemented.**
- **Spec §10 Agent C #3 (game value finite + bounded):** `test_each_spot_game_value_is_finite`. **Not implemented.**
- **Spec §10 Agent C #5 (strategy matrix shape):** `test_strategy_matrix_shape`. **Not implemented.**
- **Spec §10 Agent C #6 (fixture range-board overlap):** `test_no_overlap_in_fixture_ranges`. **Not implemented.** (Implicitly covered by `load_spots`-time validation, but no explicit fixture-correctness gate.)
- **Spec §10 Agent C #7 (`iterations_override` respected):** `test_iterations_override_respected`. **Not implemented.**
- **Spec §10 Agent C #8 (`find_brown_binary` no-raise contract):** `test_brown_binary_finder_returns_path_or_none`. **Not implemented.**
- **Spec §5 step 7 + §9 #3 (binary-missing skip):** Agent B's `test_brown_binary_buildable` (lines 459-491) covers the skip path on missing toolchain. Spec also wants `test_river_parity_vs_brown` to skip cleanly when binary missing — line 188-197 in the same file is correct. **Covered.**
- **Wrapper `iterations_run` faithful reporting:** see S4. No test ensures Brown actually ran the requested iter count.

---

## License compliance

Brown's `noambrown/poker_solver` is **MIT-licensed** (`references/code/noambrown_poker_solver/LICENSE:1` — `Copyright (c) 2025 Noam Brown`). PR 7's relationship to Brown's repo is invoke-only:

- **Subprocess invocation only.** `poker_solver/parity/noambrown_wrapper.py:600` calls `subprocess.run([str(binary), ...])`; the binary is treated as an external program. Not a derivative work under MIT.
- **JSON output parsing.** The wrapper parses the file written by Brown's `--dump-strategy` flag (`noambrown_wrapper.py:613-614`). Public interface; not licensed code.
- **No C++ source copied.** The canonicalizer at lines 833-1040 implements an original Python state machine that operates on Brown's wire-format tokens. The algorithm is general (token-stream → state-tracked tuple), not a port of Brown's tree-construction in `cpp/src/river_game.cpp`. No verbatim or paraphrased reproduction of Brown's source.
- **Attribution header.** Spec §8's attribution docstring is present verbatim at `poker_solver/parity/noambrown_wrapper.py:1-14` — names the repo, URL, license, copyright holder, and the public interfaces depended upon. Compliant.
- **No NOTICE file required.** MIT does not mandate a NOTICE file. None added or needed.
- **Wheel does not bundle Brown's binary.** `pyproject.toml [tool.maturin]` includes only `poker_solver/charts/*.json` (line 34). Brown's binary is built in-place under `references/code/noambrown_poker_solver/cpp/build/` (a gitignored, runtime-only location).

**Verdict: license-clean.** No remediation required.

---

## Release-notes follow-up

PR 7 adds a public submodule `poker_solver.parity` exposing `RiverSpot`, `BrownStrategyDump`, `canonicalize_brown_history`, `canonicalize_our_history`, `find_brown_binary`, `load_spots`, `our_strategy_to_brown_matrix`, `run_brown_solver`, `write_brown_config` (per `__all__` at `noambrown_wrapper.py:1198-1213`). This is a new public API surface for v0.5.1 / v0.6.0 release notes:

> **PR 7 (river-spot parity vs Noam Brown):** Added `poker_solver.parity.noambrown_wrapper` for invoking Brown's MIT-licensed `river_solver_optimized` C++ binary and canonicalizing histories across the two encodings. Tests opt-in via `pytest -m parity_noambrown` and require running `bash scripts/build_noambrown.sh` to build Brown's binary; tests skip cleanly when the binary is missing.

No backward-incompatible changes elsewhere. `tests/test_hunl_diff.py:60-70` was hardened (silent skip on stale `_rust.so` → loud `RuntimeError`); this is a tighter contract on PR 6's surface, not a new feature. Release notes can mention as a follow-up to PR 6.5 / "PR 6 audit followup §3."

---

## Overall verdict

**READY for commit AFTER must-fix items resolved.**

The infrastructure (build script, wrapper, fixture, parity harness, marker) is sound and the load-bearing canonicalizer is correct on the production path (where a `RiverSpot` is always supplied). License compliance is clean. The xdist subprocess safety is correct (mkdtemp is equivalent to NamedTemporaryFile for collision purposes). Tolerance is locked at 5e-3 / 1e-3 with no silent relaxation. Agent A and B deliverables match spec.

The blocking defects are concentrated in Agent C's deliverable: the wrong tests were committed (binary-required smoke tests instead of the 8 binary-independent self-sanity tests the spec mandates), which both fails to satisfy spec §10 Agent C #1-#8 AND leaves the latent default-state-helper bug (M2) untested. Fixing M1 (rewrite Agent C's self-sanity module) will surface M2 and force resolution of M3 (canonicalizer convention mismatch with `agent_c_prompt.md:165-191`). Once those three are settled the PR is ready.
