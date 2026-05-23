# PR 7 must-fix patches — verification checklist

**Context:** Patches agent `ad0383c2d0f95a9a4` is applying three must-fix changes flagged in `audit_report.md`:

- **M1** — expand `tests/test_river_diff_self_sanity.py` from 4 binary-dependent tests to 8+ binary-independent tests, including the 10-case canonicalizer round-trip.
- **M2** — drop the `2**31 - 1` sentinel from `_state_for_default_river_pot` in `poker_solver/parity/noambrown_wrapper.py`; use real fixture defaults (pot=1000, stack=9500) so the all-in canonical amount is `10000`, not `2147483647`.
- **M3** — reconcile `docs/pr7_prep/agent_c_prompt.md` §6 (Test 4 expected values) with the wrapper's actual convention. If the wrapper now emits `("r", 10000)` for `b500A`, the prompt's case 10 expected tuple must match; if the wrapper's convention shifted, both sides must agree.

The orchestrator will run this checklist between patch-land and the commit-pipeline re-fire. **Do not execute any code from this doc directly** — it is a checklist for the verification + commit agents to follow.

---

## 1. M1 verification — `test_river_diff_self_sanity.py`

**Goal:** 8+ binary-independent tests, with the 10-case round-trip locked in.

**Checks (in order):**

1. **Test count.** Open `/Users/ashen/Desktop/poker_solver/tests/test_river_diff_self_sanity.py` and count `def test_` definitions. Must be `>= 8`. The current file ships 4 (`test_brown_binary_help_flag_succeeds`, `test_brown_binary_runs_trivial_dcfr_in_out`, `test_brown_binary_exploitability_finite_at_smoke_iters`, `test_brown_binary_seed_determinism`) and they all guard on `_require_brown_binary()` — those four are binary-DEPENDENT and may legitimately remain as skip-guarded tests, but the new tests must NOT call `_require_brown_binary` and must NOT shell out via `subprocess`.

2. **Binary independence.** `grep -n "subprocess\|_require_brown_binary\|BROWN_BINARY" tests/test_river_diff_self_sanity.py`. Every match must be inside one of the original four `test_brown_binary_*` functions OR inside the `_require_brown_binary` helper. New tests (the 4+ that were added by M1) must have ZERO such references.

3. **10-case canonicalizer round-trip is present.** `grep -n "canonicalize_brown_history\|canonicalize_our_history\|test_canonicalize" tests/test_river_diff_self_sanity.py`. Must find a test function whose body contains a list of 10 hand-built `(brown_form, our_form, expected_canonical)` tuples mirroring `docs/pr7_prep/agent_c_prompt.md` §Test 4 lines 169-193. Specifically the case-10 expected tuple must be `(("b", 1000), ("r", 10000))` (NOT the sentinel `2147483647`).

4. **Pytest dry collection.** `pytest tests/test_river_diff_self_sanity.py --collect-only -q` must list `>= 8` test ids and exit 0. (Collection only — does not execute, so does not depend on Brown binary.)

5. **Pytest run without Brown binary.** Verify that `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` is absent (or temporarily rename it for the check), then run `pytest tests/test_river_diff_self_sanity.py -v`. Expected: the original four `test_brown_binary_*` tests SKIP cleanly with the directive message; the new tests (`>= 4` of them) PASS. Total: 0 fail, 0 error.

6. **Pytest run WITH Brown binary (if available).** Run `pytest tests/test_river_diff_self_sanity.py -v` with the binary present. Expected: all 8+ tests pass; no skips.

**Largest residual risk:** M1's new tests might import the canonicalizer with the wrong starting state (e.g., synthesize their own `_HistoryState` via private API rather than calling the public `canonicalize_*_history` with default args). If so, expected tuples may pass against the test's local state but disagree with what the production diff path emits. Check that the 10-case test calls ONLY the public API (`canonicalize_brown_history`, `canonicalize_our_history`) with default kwargs.

---

## 2. M2 verification — `_state_for_default_river_pot`

**Goal:** synthetic default state matches fixture (pot=1000, stack=9500), NOT the unbounded `2**31 - 1` sentinel.

**Checks:**

1. **No sentinel literal remains.** `grep -n "2\*\*31\|2147483647\|sys.maxsize\|SENTINEL_STACK" poker_solver/parity/noambrown_wrapper.py`. Must return zero matches.

2. **Function signature accepts realistic defaults.** Read `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` around line 806 and confirm `_state_for_default_river_pot(initial_pot: int, initial_stack: int = 9500) -> _HistoryState` — `initial_stack` default = `9500`, not absent and not a sentinel.

3. **State construction is correct.** Inside the function body: `half = initial_pot // 2`; `stack=half + initial_stack`; `actor=1`; `contrib0 = contrib1 = half`. (See lines 826-832.)

4. **Callers pass through correctly.** `grep -n "_state_for_default_river_pot" poker_solver/parity/noambrown_wrapper.py`. Each caller (currently lines 869 and 969) must pass `initial_pot` and `initial_stack` (not just `initial_pot`).

5. **Semantic test (manual trace, no execution).** With `state.stack = 500 + 9500 = 10000`:
   - `canonicalize_our_history("b500A")` walks: `b500` → P1 raises to total 1000, then `A` (all-in token); since `to_call > 0` after b500, `A` canonicalizes to `("r", min(stack_ceiling, opponent_total + stack_remaining))` = `("r", 10000)`. Final tuple: `(("b", 1000), ("r", 10000))`.
   - Without M2 (sentinel `2**31 - 1`), this would emit `("r", 2147483647)`. M2's job is to make 10000 the correct value.

**Largest residual risk:** M2 might patch `_state_for_default_river_pot` but leave a stale sentinel in `canonicalize_brown_history` / `canonicalize_our_history` default args or in `_walk_*_tokens`. The `grep -n` in check 1 must cover the entire wrapper file, not just the helper.

---

## 3. M3 verification — prompt vs wrapper convention alignment

**Goal:** `docs/pr7_prep/agent_c_prompt.md` §6 / Test 4 expected values, the canonicalizer in the wrapper, AND `test_river_diff_self_sanity.py` Test 4 all agree on the same `("r", to_total)` values.

**Checks:**

1. **Read prompt Test 4 expected tuples.** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/agent_c_prompt.md` lines 169-193. Note the 10 expected canonical tuples — specifically cases 8 (`b500/r500` ↔ `b500r1500` → `(("b", 1000), ("r", 1500))`), case 9 (`b9500` ↔ `A` → `(("b", 10000),)`), and case 10 (`b500/r9000` ↔ `b500A` → `(("b", 1000), ("r", 10000))`).

2. **Read wrapper convention.** In `noambrown_wrapper.py` `_walk_brown_tokens` and the our-side equivalent, confirm the comment block at lines 846-854 matches: Brown's `b<amount>` → `("b", actor_contrib + amount)`; Brown's `r<extra>` → `("r", max(c0, c1) + extra)`.

3. **Three-way agreement.** The prompt's expected values, the wrapper's emitted values, and the self-sanity test's hand-built expectations MUST be byte-identical for all 10 cases. If any one of the three was changed by the patch, the other two must be updated to match.

4. **Note on direction of fix.** Per the M3 task, the orchestrator decides whether the wrapper conforms to the prompt OR the prompt conforms to the wrapper. The audit recommended updating the prompt to match the wrapper's convention (it's already correct). Confirm the patch took the documented direction.

5. **No drift in `test_river_diff_self_sanity.py`.** The 10-case list in the self-sanity test MUST be the same 10 tuples as in the prompt. Diff them mentally — if any tuple differs, flag for re-patch.

**Largest residual risk:** The "raise after b500" semantics for `A` (all-in raise) — case 10 — depends on whether the wrapper interprets `A` as raise-to-stack-ceiling or as raise-by-remaining-chips. If the wrapper's logic at the `A` token branch uses `state.contrib[actor] + remaining_stack` versus `state.stack` directly, the expected value differs. Verify the math in the wrapper for the `A` token specifically (most likely location: `_walk_our_tokens` or similar near the canonicalizer).

---

## 4. Post-patch full-suite verification

Run after M1+M2+M3 all verify clean per §1-3 above.

**Commands (orchestrator runs sequentially):**

1. `pytest tests/test_river_diff*.py -v --tb=line` — both `test_river_diff.py` (Agent B's heavyweight diff) and `test_river_diff_self_sanity.py` (M1-expanded) must pass. The heavyweight diff may skip if Brown binary is absent; that's fine.

2. `pytest -m "not slow and not very_slow"` — full quick-gate suite. Must show 138+ tests passing, 0 fail, 0 error.

3. `ruff check poker_solver tests scripts` — must exit 0.

4. `black --check poker_solver tests scripts` — must exit 0.

5. `python -c "from poker_solver.parity.noambrown_wrapper import canonicalize_our_history; print(canonicalize_our_history('b500A'))"` — must print `(('b', 1000), ('r', 10000))`. Quick smoke; do NOT include in the test suite.

**Stop-the-line conditions:**
- Any single test failure → halt, re-spawn patches agent with the specific failure pasted in.
- Any ruff/black violation → halt; trivial to fix, but fix in the patches branch not main.
- The semantic smoke (`canonicalize_our_history('b500A')`) returns anything other than `(('b', 1000), ('r', 10000))` → M2 was not actually applied; halt.

---

## 5. Sequencing

The patches agent will apply M1, M2, M3 as a single atomic commit (per audit recommendation in `audit_report.md`). The orchestrator's job:

1. **Wait** for patches agent to report COMPLETE.
2. **Run §1, §2, §3 checks in parallel** (three separate verification agents — they are independent reads).
3. **Aggregate** — all three must report PASS.
4. **Run §4** — single verification agent for the full-suite gate.
5. **On clean §4:** re-fire the commit-pipeline agent (`docs/pr7_prep/commit_pipeline_readiness.md` describes the pipeline). The commit pipeline will produce the final PR 7 commit using `docs/pr7_prep/commit_message_draft.md`.
6. **On any §1-§4 failure:** loop back to patches agent with the specific failure message; do NOT proceed to commit pipeline.

**Largest single residual risk across all M1-M3 + post-patch:** the 10-case canonicalizer round-trip. If even one of the 10 hand-built expected tuples is wrong (e.g., the `A`-token case in case 10 because of off-by-one stack-ceiling math), the test passes when run against the buggy wrapper and locks in the bug — then the heavyweight diff test against Brown's binary fails at runtime with no clean trace back to the canonicalizer. Mitigation: §3 check 5 (three-way agreement between prompt, wrapper, and self-sanity test) is the only place this is caught before binary-on-binary diff time.
