# PR 7 Must-Fix Patches — Progress Check

**Date:** 2026-05-22
**In-flight agent:** `ad0383c2d0f95a9a4` (applying M1 + M2 + M3)
**Check type:** Read-only verification

---

## File State (size + mtime)

```
-rw-r--r--  22847  May 22 04:15  docs/pr7_prep/agent_c_prompt.md
-rw-r--r--  48341  May 22 04:15  poker_solver/parity/noambrown_wrapper.py
-rw-r--r--  21217  May 22 04:17  tests/test_river_diff_self_sanity.py
```

All three files touched within a 2-minute window (04:15–04:17), consistent with a coherent M1+M2+M3 patch wave.

---

## M1 — Expand self-sanity tests + drop binary dependency

**Status: LANDED**

- **LOC:** `tests/test_river_diff_self_sanity.py` is now **487 LOC** (was 278; ~+209 lines, +75%).
- **Test count:** **9** `def test_` functions (target was 8+):
  1. `test_each_spot_loads_into_hunl_config`
  2. `test_each_spot_solver_converges`
  3. `test_each_spot_game_value_is_finite`
  4. `test_canonicalize_history_roundtrip`
  5. `test_canonicalize_history_is_idempotent`
  6. `test_strategy_matrix_shape`
  7. `test_no_overlap_in_fixture_ranges`
  8. `test_iterations_override_respected`
  9. `test_brown_binary_finder_returns_path_or_none`
- **Binary-independence:** Docstring (line 4) explicitly states "they do NOT require Brown's C++ binary to be built." No `subprocess` / `run_noam` / direct binary-execution calls in the test file. The binary finder test (#9) is the only one that touches `find_brown_binary` and is designed to handle the Path-or-None return contract on CI without the binary.

---

## M2 — Remove `2**31` sentinel from wrapper

**Status: LANDED**

- `grep -n "2\*\*31" poker_solver/parity/noambrown_wrapper.py` → **exit 1, zero matches**.
- Also checked variant forms (`2 ** 31`, `0x80000000`, `2147483648`, `sentinel`) → **zero matches**.
- Sentinel fully scrubbed from the wrapper.

---

## M3 — Bet-amount convention consistency

**Status: LANDED, conventions aligned**

Wrapper (`noambrown_wrapper.py`) defines:
- Line 67–71: `CanonicalToken = tuple[Literal["f", "c", "b", "r"], int]` — `"b"` carries the **actor's new total contribution**, not chips-added.
- Line 849: `"b<amount>" → ("b", actor_new_total)` — Brown's `amount` is chips on top, but we re-emit as the new total.
- Line 909 / 1029 / 1044: `out.append(("b", new_total))` — confirms total-form.

Prompt (`agent_c_prompt.md`) round-trip cases (lines 177–192):
- `("b500", "b500", (("b", 1000),))` — Brown's `b500` (500 chips added on half-pot of 1000 → new total 1000) canonicalizes to `("b", 1000)`.
- `("b500/c", "b500c", (("b", 1000), ("c", 0)))`
- `("b500/f", "b500f", (("b", 1000), ("f", 0)))`
- `("b500/r500", "b500r1500", (("b", 1000), ("r", 1500)))`
- `("b500/r9000", "b500A", (("b", 1000), ("r", 10000)))`

**Convention used: `("b", 1000)` (total-form)** — matches the wrapper's `actor_new_total` semantics. The prompt's round-trip fixtures are consistent with the wrapper's canonical form. No `("b", 500)` (chips-added form) appears in the prompt; the earlier audit concern (prompt's `("b", 500)` mismatch) has been resolved by adopting total-form `("b", 1000)` throughout the prompt's ten histories.

---

## Verdict

**COMPLETE — ready to commit.**

All three must-fix items from the audit have landed:
- M1: tests expanded from 278 → 487 LOC, 9 tests (target 8+), binary-independent.
- M2: `2**31` sentinel grep returns zero hits.
- M3: prompt's ten round-trip histories use total-form `("b", 1000)`, matching the wrapper's `actor_new_total` canonicalization contract.

Files modified are internally consistent; mtimes cluster tightly suggesting a single coherent patch wave. No remaining patches needed before Agent C launch.
