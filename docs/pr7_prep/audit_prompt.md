# PR 7 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-7-noambrown-diff` branch and you have not seen the design discussions. Your job is to audit the PR 7 implementation (river-spot differential test against Noam Brown's MIT-licensed `noambrown/poker_solver`) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-7-noambrown-diff` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 7 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + tolerance), §2 (why this matters — DCFR same params), §3 (non-goals), §4 (fixture file format + spot list), §5 (diff harness — particularly step 5 history canonicalization), §6 (build script idempotency), §8 (license + attribution), §9 (risks), §11 (critical correctness items), §12 (open decisions).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-7-noambrown-diff`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 7 entries.
4. **The actual new / modified files:** at minimum
   - `scripts/build_noambrown.sh`
   - `tests/data/river_spots.json`
   - `poker_solver/parity/__init__.py`
   - `poker_solver/parity/noambrown_wrapper.py`
   - `tests/test_noambrown_river_parity.py`
   - `tests/test_noambrown_self_sanity.py`
   - `pyproject.toml` (pytest marker `parity_noambrown` added)
   - `.gitignore` (or `references/code/.gitignore`) updated to exclude Brown's `build/` output
   - any other touched files

Do not run Brown's solver. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **Build script idempotency + soft-fail on missing C++ compiler.**
   - Per spec §6: `scripts/build_noambrown.sh` is **idempotent** — skips rebuild if binary is newer than every `.cpp`/`.h` source. Verify the `find ... -newer` logic.
   - **Soft-fails** when `cmake` or `c++` is unavailable: prints informative message, `exit 0` (NOT `exit 1`). Per §6 + §9 #3.
   - Test harness checks for missing binary and `pytest.skip(...)` cleanly — does NOT fail (per §5 step 7 + §11 #4).
   - Build is **out-of-tree** under `references/code/noambrown_poker_solver/cpp/build/`; that directory is gitignored.
   - Uses Brown's `cpp/CMakeLists.txt` (Release default, `-O3 -march=native -ffast-math` for non-MSVC).

2. **Raise-encoding canonicalization (Brown's extra-beyond-call ↔ ours raise-to).**
   - Per spec §5 step 5 + §9 #1: this is the **load-bearing** parity surface. A bug here produces spurious diff failures.
   - Brown stores raises as **extra-beyond-call** (`cpp/src/river_game.cpp:88-93`, `cpp/src/main.cpp:193-194`).
   - We store raises as **raise-to-total** (`poker_solver/hunl.py:391-401`).
   - `canonicalize_brown_history(token)` parses Brown's `r<delta>` correctly.
   - `canonicalize_our_history(history)` converts our `r<to_total>` → canonical `r<delta>` where `delta = to_total - prev_aggressor_contrib`.
   - Both functions return the same canonical tuple shape: `tuple[(action_kind, amount), ...]`.
   - Round-trip parity test exists: `canonicalize_our_history(canonicalize_brown_history(our_history))` is identity for hand-built histories (spec §10 Agent C deliverable #4 in `test_noambrown_self_sanity.py`).

3. **All-in token mapping (`A` ↔ `b<amt>` / `r<amt>`).**
   - Per spec §5 step 5: our `A` (all-in) token maps to Brown's `b<remaining>` (if no bet to call) or `r<remaining-to_call>` (if facing a bet — using Brown's extra-beyond-call semantics).
   - Brown has no special "all-in" token; it just emits the bet/raise amount (`cpp/src/river_game.cpp:63-66, 98-100`).
   - Verify the all-in canonicalization branch produces the right shape.
   - A bug here means all-in actions never match between engines → diff fails on every spot that goes all-in.

4. **DCFR flag invocation correct.**
   - Per spec §5 step 3: invokes Brown's binary with `--algo dcfr --iters 2000 --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --dump-strategy /tmp/...`. Verify these EXACTLY (especially β=0, not 0.5; γ=2, not 2.0).
   - **Also passes `--seed 7`** for paranoia per §11 #1 (Brown's default seed is 7 per `cpp/src/main.cpp:36`).
   - Iteration count = 2000 per spec §1 + §5 step 2 (Brown's default per `cpp/src/main.cpp:31`).
   - Spec §12 open decision 5 lets a fixture spot override via `iterations_override` — confirm this is plumbed through.

5. **Fixture file schema integrity.**
   - `tests/data/river_spots.json` has exactly 15 spots (per §4 + §12 open decision 2 default).
   - `schema_version == 1`.
   - Each spot has 5 board cards (river complete; the `board_river` field per §4 example), per-player explicit hand list + weights, integer pot, integer stack, `bet_sizes` as pot fractions in (0, 5], `include_all_in: bool`, `max_raises: int`.
   - **No range overlaps with board** (spec §9 #7 — `load_spots` validates and rejects at load time).
   - **Equal effective stacks** asserted (spec §9 #2 — `stacks[0] == stacks[1]`).
   - **Whole-BB pot+stack values** (`pot % big_blind == 0`).
   - File size < 100 KB hard ceiling.
   - 5 categories × 3 spots: dry rainbow, wet rainbow, monotone, paired, broadway-heavy (per §4 table).

6. **Tolerance threshold matches spec.**
   - Per spec §1 + §5 step 6: per-action `|our_prob - brown_prob| < 5e-3`, per-spot `|our_game_value - brown_game_value| < 1e-3 * spot.pot`.
   - **Anti-pattern:** if the test silently relaxes to 1e-2 or 5e-2, flag as must-fix.
   - Spec §12 open decision 1 defaults to 5e-3; any relaxation must be documented.

7. **Skip-cleanly-when-binary-missing path.**
   - Per spec §5 step 7 + §9 #3: when `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` does not exist, `tests/test_noambrown_river_parity.py` calls `pytest.skip("Brown's river_solver_optimized not built; run scripts/build_noambrown.sh")`.
   - Does NOT raise `FileNotFoundError`, `subprocess.CalledProcessError`, or other hard error.
   - The Agent C tests (`test_noambrown_self_sanity.py`) **don't** require the binary — they run unconditionally.

8. **License + attribution.**
   - Per spec §8: Brown's repo is MIT (verified at `references/code/noambrown_poker_solver/LICENSE`).
   - The wrapper module `poker_solver/parity/noambrown_wrapper.py` has the spec §8 attribution docstring header (or equivalent), naming Brown's repo + license + the public CLI surface we depend on.
   - **No code copied from Brown's C++.** Our wrapper is original Python.
   - We **invoke the binary** (not a derivative work) and **parse JSON output** (public interface).
   - No NOTICE file update needed (MIT doesn't mandate one).

9. **Subprocess + xdist safety.**
   - Per spec §9 #8: subprocess invocations use `tempfile.NamedTemporaryFile` per call (NOT a shared `/tmp/spot_<id>.json`). Race-condition-safe under pytest-xdist parallel runs.
   - Per spec §9 #9: Brown binary path resolved via `Path(__file__).resolve().parents[2] / "references" / ...` (anchored to repo root, not cwd).

10. **Strategy-matrix adapter.**
    - Per spec §9 #5: `our_strategy_to_brown_matrix(result, hands, infoset_keys)` aggregates our per-(hand, infoset) probabilities into Brown's `[hand × action]` matrix shape, keyed by canonicalized history.
    - Tested standalone in `test_noambrown_self_sanity.py::test_strategy_matrix_shape` (spec §10 Agent C deliverable #5).

11. **80% history-coverage assertion.**
    - Per spec §10 Agent B "Per-spot assertion": at least **80%** of Brown's canonical histories appear in our canonicalized result. Catches accidental tree-truncation on either side.
    - Verify this assertion is present in `test_noambrown_river_parity.py`.

12. **Pytest marker registered.**
    - Per spec §10 Agent B + §12 open decision 6: `@pytest.mark.parity_noambrown` declared in `pyproject.toml` under `[tool.pytest.ini_options].markers`.
    - Spec §12 #6 prefers reuse over new markers if a `parity` / `external` marker exists; confirm no duplicate.

13. **Pot/stack units consistency.**
    - Per spec §9 #2 + §12 open decision 4: Brown's pot/stack are integer chips; ours are integer cents with `big_blind=100` cents per BB. The wrapper writes `big_blind=100` in Brown's subgame JSON so the units align. Convention: `pot=1000, stack=9500, big_blind=100` → 10 BB pot, 95 BB stack.

14. **No new third-party dependencies.**
    - `poker_solver/parity/noambrown_wrapper.py` is pure Python + stdlib + numpy + existing `poker_solver` imports. Per spec §10 Agent A "Type-hinted; mypy --strict clean. Pure Python + standard library + numpy + the existing poker_solver imports. No new dependencies."
    - `pyproject.toml` `[project.dependencies]` unchanged.

15. **Self-sanity test scope (Agent C).**
    - `test_noambrown_self_sanity.py` runs without Brown's binary. Verify 8 tests per spec §10 Agent C (test 1-8):
      - Spot loads into `HUNLConfig(starting_street=Street.RIVER, ...)` cleanly.
      - 2000-iter solve has `exploitability < 0.02 * pot`.
      - `result.game_value` finite + bounded.
      - History canonicalization roundtrip.
      - Strategy matrix shape correct.
      - No board/hand overlap in fixture.
      - `iterations_override` respected.
      - `find_brown_binary()` returns path-or-None (no exception).

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_report.md` with this exact structure:

```markdown
# PR 7 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-7-noambrown-diff
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_noambrown_*.py — pass/fail (note skip count if no compiler); full suite delta]

## Must-fix

[Build script not idempotent / not soft-failing; raise-encoding canonicalization wrong; all-in mapping wrong; DCFR flags wrong; missing skip path for missing binary; AGPL or non-MIT contamination; tolerance silently relaxed; new third-party dep. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, undocumented behavior, missing 80%-coverage assertion, fixture file violations (overlap, bad units), test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-15 matching the 15 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: Brown's MIT license respected; wrapper depends only on Brown's public CLI + JSON output schema; no C++ code copied. Cite spec §8 attribution header in the wrapper.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** build script broken (hard-fails on missing compiler), wrong raise-encoding (silently mis-canonicalizes), wrong all-in mapping, wrong DCFR flags, missing skip path on missing binary, license contamination (any code copy), tolerance silently relaxed, fixture file with board/range overlap. Blocks PR.
- **should-fix:** missing 80%-coverage assertion, missing self-sanity test, ambiguous error messages, awkward APIs. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that produces silently-wrong diff results (spurious matches, spurious failures) → must-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr7_prep/audit_report.md`.
- The Brown binary will NOT be built when you audit — that's expected. Check the skip-path is correct, not that the diff test actually runs.

Begin by reading the spec, then the diff, then the new files. Then write the report.
