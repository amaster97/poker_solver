# Leduc Pytest Timeout Fix Recipe (pre-staged, NOT yet applied)

**Status:** PRE-STAGED. Apply only if the PR 6 commit pipeline (`ac4cbd26406524339`) halts at the pytest gate with `commit_blocked.md` citing Leduc timeouts.

**Scope:** 3 test files, 0 production code. No `pyproject.toml` edits.

---

## 1. Diagnosis

The Leduc failures from `check_pr_dry_run.md` (Step 6) are **NOT a PR 6 regression**:

- All 51 HUNL tests pass; the failures are confined to `test_leduc_*` modules that PR 6 does not touch.
- Independent timing on this machine: Python Leduc DCFR solve at **200 iters ~= 14s** -> linear extrapolation: 800 iters ~= 56s, 2000 iters ~= 140s.
- The host is **x86_64 Python 3.13.1 under Rosetta on darwin-arm64** (per Step 5 of dry-run, which required `rustup target add x86_64-apple-darwin`). Python interpreter is running emulated; the Leduc Python backend is single-threaded pure-Python tree walks. This is the dominant cost driver.
- The Rust Leduc backend is fast (100 iters in ~0.9s); only the **Python baseline leg** of differential / fixture tests exceeds the timeout.
- Verdict: **genuinely slow, not a regression.** A timeout bump is the correct surgical fix.

---

## 2. Recommended Fix Verdict

**Bump timeouts** (option A in dry-run report) for these three files. Rationale:

- The Leduc Python<->Rust diff and Python-baseline intuition tests are **PR 6's primary cross-checks** that the Rust port behaves correctly on a non-trivial game. Marking them `@pytest.mark.slow` removes them from the default fast suite and from `check_pr.sh`, weakening PR 6's validation envelope. Bad trade for what's effectively a "Rosetta Python is slow" problem.
- Bumping to 300s preserves CI signal at the cost of one slow-but-passing module.
- The monotone-trend test is genuinely cheap by Leduc standards (~70s observed); it just barely overshoots the global 90s cap. A scoped per-test bump fixes it cleanly.

**Alternative (mark slow)** is documented in section 5 in case the orchestrator prefers it.

---

## 3. Recipe (exact edits)

### File 1: `tests/test_leduc_diff.py`

**Change:** Bump the per-test timeout constant from 180s to 300s.

**Line 38** currently reads:
```python
_LEDUC_DIFF_TIMEOUT = 180
```

**Replace with:**
```python
_LEDUC_DIFF_TIMEOUT = 300
```

No decorator changes — every test in the file already has `@pytest.mark.timeout(_LEDUC_DIFF_TIMEOUT)` (lines 56, 69, 82, 90, 100). The comment block at lines 34-37 should also be updated to reflect the observed Python baseline cost; suggested replacement:

**Lines 34-37** currently:
```python
# pytest-timeout doesn't apply to module-scoped fixtures by default; bumping
# the timeout per-test gives the shared fixture's first-touch setup (Python
# Leduc DCFR + Rust DCFR @ 2k iters + cold Rust binding load) ample headroom
# above pytest's 90s default. Observed ~30-60s on cold venvs.
```

**Replace with:**
```python
# pytest-timeout doesn't apply to module-scoped fixtures by default; bumping
# the timeout per-test gives the shared fixture's first-touch setup (Python
# Leduc DCFR + Rust DCFR @ 2k iters + cold Rust binding load) ample headroom
# above pytest's 90s default. Observed ~140s on x86_64 Python under Rosetta
# (Python baseline leg dominates; Rust leg is ~18s).
```

### File 2: `tests/test_leduc_intuition.py`

**Change:** Introduce a module-level timeout constant and decorate every test that uses the `leduc_strategy` fixture, mirroring the pattern in `test_leduc_diff.py`.

**Insert after line 25** (`LEDUC_ITERATIONS = 800`):
```python

# pytest-timeout doesn't apply to module-scoped fixtures by default. The
# fixture runs one 800-iter Python Leduc DCFR solve (~55s nominal, ~100s
# on x86_64 Python under Rosetta). Bump per-test cap above pytest's 90s
# default so the fixture's first-touch setup fits.
_LEDUC_INTUITION_TIMEOUT = 180
```

**Then add `@pytest.mark.timeout(_LEDUC_INTUITION_TIMEOUT)` above each of these 6 test defs:**

- Line 56: `def test_king_never_folds_to_first_bet(leduc_strategy):`
- Line 75: `def test_jack_never_raises_round1_when_facing_raise(leduc_strategy):`
- Line 94: `def test_pair_with_public_card_value_betting(leduc_strategy):`
- Line 116: `def test_underpair_caution(leduc_strategy):`
- Line 138: `def test_strategy_mass_sums_to_one(leduc_strategy):`
- Line 151: `def test_strategy_is_well_defined_on_all_reachable_infosets(leduc_strategy):`

Do **NOT** decorate `test_action_id_layout_matches_assertion_indices` (line 172) — it doesn't touch the fixture and runs in <1ms.

### File 3: `tests/test_leduc_dcfr.py`

**Change:** Add a per-test timeout to `test_leduc_exploitability_monotone_trend` only. Three sequential Python solves at 100/300/600 iters ~= 70-130s on this machine.

**Insert above line 35** (currently `def test_leduc_exploitability_monotone_trend():`):
```python
@pytest.mark.timeout(300)
```

Resulting block becomes:
```python
@pytest.mark.timeout(300)
def test_leduc_exploitability_monotone_trend():
    game = LeducPoker()
    ...
```

Do **NOT** decorate any other tests in this file — they share the `leduc_run` module fixture which runs a single 600-iter Python solve (~45s nominal, ~85s on Rosetta) and they each finish well inside the 90s default after the fixture warms.

If `test_leduc_converges_below_threshold` / `test_leduc_strategy_table_size` / `test_leduc_game_value_close_to_known` / `test_leduc_strong_hand_seldom_folds` (lines 16, 20, 28, 48) also error at fixture setup on retry, **add the same `@pytest.mark.timeout(180)` decorator above each one**. Treat this as a follow-up patch, not the initial fix.

---

## 4. Sequencing

**Orchestrator workflow:**

1. Let the in-flight commit pipeline (`ac4cbd26406524339`) run to the pytest gate.
2. If pytest passes (e.g. machine ran cooler this time, or some other agent already bumped timeouts), **discard this recipe** — no action needed.
3. If pytest halts and produces `commit_blocked.md` citing the same 1 fail + 11 errors enumerated in `check_pr_dry_run.md` Step 6, apply this recipe verbatim:
   - Spawn a single agent with this file as input; instruct it to edit only the three files above; no other changes.
   - Re-run `scripts/check_pr.sh` (or just the pytest gate) to confirm green.
4. If pytest fails with a **different** signature (e.g. a HUNL test newly red, or a Leduc test fails with an assertion rather than a timeout), **do NOT apply this recipe** — that's a real regression and the recipe is the wrong tool.
5. After successful re-run, commit the timeout bumps as part of the PR 6 commit (or as a tiny separate "ops/test-timeouts" commit if PR 6 hygiene prefers it isolated).

**Do not apply pre-emptively.** The dry-run cost was 12 minutes and the in-flight pipeline may already include other Leduc-affecting changes from a parallel agent; we want one clean signal from the pipeline before patching.

---

## 5. Alternative: Mark as `@pytest.mark.slow`

If the orchestrator decides the Leduc Python baselines belong in the slow tier:

**Pros:**
- Keeps `check_pr.sh` fast-suite runtime tight (currently ~12min, would drop ~10min by skipping the Leduc Python baselines).
- Matches the pattern already established for hour-scale precompute jobs.

**Cons:**
- `test_leduc_python_rust_strategy_agreement` / `..._game_value_agreement` / `..._exploitability_agreement` are PR 6's **primary differential gates** for the Rust port on Leduc. Skipping them by default means the next regression in the Rust DCFR engine slips through `check_pr.sh` unless reviewer manually runs `pytest -m slow`.
- The Leduc intuition tests are likewise the only behavioral sanity checks on the Python tier; demoting them weakens the safety net.

**Mechanics if chosen:** add `pytestmark = pytest.mark.slow` at module scope in each of `test_leduc_diff.py` and `test_leduc_intuition.py`, and `@pytest.mark.slow` above `test_leduc_exploitability_monotone_trend`. No timeout changes needed.

**Recommendation:** prefer the timeout bump (section 3). Re-evaluate after PR 7+ if the suite gets slower; at that point converting to `slow` becomes more attractive.
