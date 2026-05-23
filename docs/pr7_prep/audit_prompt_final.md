# PR 7 audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~55%) > clean READY (~30%) > NOT-READY (~15%).
> - Top three pre-flagged risk surfaces (audit MUST touch with file:line evidence): raise canonicalization round-trip (`audit_preprep.md` §1.3), xdist `/tmp` subprocess collision (§1.4), Brown binary subprocess invocation correctness (§1.1).
> - 5-layer skipif strategy: (1) build script soft-fail on missing `cmake`/`c++`, (2) test harness `pytest.skip()` on missing binary, (3) Xcode CLT missing → soft-fail catches, (4) `-march=native` host-mismatch → out-of-tree rebuild, (5) `@pytest.mark.parity_noambrown` opt-in marker.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-7-noambrown-diff` branch and you have not seen the design discussions. Your job is to audit the PR 7 implementation (river-spot differential test against Noam Brown's MIT-licensed `noambrown/poker_solver`) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-7-noambrown-diff` (branched from `integration`; name verified via `fanout_ready.md:51` + `audit_prompt.md:14`).
- **Brown binary canonical path:** `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` (post-P1-patch; 206136 bytes Mach-O arm64 as of 2026-05-22).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md` — read end-to-end first.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 7 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + tolerance), §2 (DCFR same params rationale), §3 (non-goals), §4 (fixture format + 15-spot list), §5 (diff harness — step 5 history canonicalization), §6 (build script idempotency + soft-fail), §8 (license + attribution), §9 (risks — esp #1 raise encoding, #8 xdist tmpfile, #9 path anchoring), §11 (critical correctness), §12 (open decisions).
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
   - `.gitignore` (or `references/code/.gitignore`) excluding Brown's `build/` output
   - any other touched files

Do not run Brown's solver. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.3, §1.4, §1.1 per `audit_preprep.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **Build script idempotency + soft-fail on missing C++ compiler.** [layer 1 of 5-skipif]
   - Per spec §6: `scripts/build_noambrown.sh` is **idempotent** — skips rebuild if binary is newer than every `.cpp`/`.h` source. Verify the `find ... -newer` logic.
   - **Soft-fails** when `cmake` or `c++` is unavailable: prints informative message, `exit 0` (NOT `exit 1`). Per §6 + §9 #3.
   - Build is **out-of-tree** under `references/code/noambrown_poker_solver/cpp/build/`; that directory is gitignored.
   - Uses Brown's `cpp/CMakeLists.txt` (Release default, `-O3 -march=native -ffast-math` for non-MSVC).
   - **Evidence stub:** `scripts/build_noambrown.sh:?` — confirm `set -e` does NOT pre-empt soft-fail branch (per `audit_preprep.md` §1.7).

2. **Raise-encoding canonicalization (Brown's extra-beyond-call ↔ ours raise-to).** [HIGH-PROB must-fix per `audit_preprep.md` §1.3]
   - Per spec §5 step 5 + §9 #1: **load-bearing** parity surface. A bug here produces spurious diff failures.
   - Brown stores raises as **extra-beyond-call** (`cpp/src/river_game.cpp:88-93`, `cpp/src/main.cpp:193-194`).
   - We store raises as **raise-to-total** (`poker_solver/hunl.py:391-401`).
   - `canonicalize_brown_history(token)` parses Brown's `r<delta>` correctly.
   - `canonicalize_our_history(history)` converts our `r<to_total>` → canonical `r<delta>` where `delta = to_total - prev_aggressor_contrib`.
   - Both functions return the same canonical tuple shape: `tuple[(action_kind, amount), ...]`.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - **State reset between streets** — preflop/flop/turn contributions reset at street boundaries.
     - **Aggressor-tracking ambiguity** — `delta = to_total - prev_aggressor_contrib` after check-raise sequences.
     - **Case 8 round-trip** — `b500/r9000 ↔ b500A` per `agent_c_prompt.md:162-191` test fixture.
   - **Evidence stubs:** `poker_solver/parity/noambrown_wrapper.py:?` (both canonicalizers); `tests/test_noambrown_self_sanity.py:?` (10-case round-trip fixture).

3. **All-in token mapping (`A` ↔ `b<amt>` / `r<amt>`).**
   - Per spec §5 step 5: our `A` (all-in) token maps to Brown's `b<remaining>` (if no bet to call) or `r<remaining-to_call>` (if facing a bet — using Brown's extra-beyond-call semantics).
   - Brown has no special "all-in" token; emits the bet/raise amount (`cpp/src/river_game.cpp:63-66, 98-100`).
   - Verify the all-in canonicalization branch produces the right shape.
   - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:?` — all-in branch in `canonicalize_our_history`.

4. **DCFR flag invocation correctness.** [pre-verified clean per `audit_preprep.md` §1.2]
   - Per spec §5 step 3: invokes Brown's binary with **EXACTLY**: `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7 --iters 2000 --dump-strategy /tmp/...`.
   - **Verify especially:** β=0 (NOT 0.5), γ=2 (NOT 2.0 — int parse, not float), `--seed 7` explicitly passed (Brown default per `cpp/src/main.cpp:36` but spec §11 #1 mandates explicit).
   - Iteration count = 2000 per spec §1 + §5 step 2 (Brown's default per `cpp/src/main.cpp:31`).
   - Spec §12 open decision 5 lets a fixture spot override via `iterations_override`.
   - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:?` — `run_brown_solver()` argv construction.

5. **Fixture file schema integrity.**
   - `tests/data/river_spots.json` has exactly **15 spots** (per §4 + §12 open decision 2 default).
   - `schema_version == 1`.
   - Each spot: 5 board cards (river complete), per-player explicit hand list + weights, integer pot, integer stack, `bet_sizes` as pot fractions in (0, 5], `include_all_in: bool`, `max_raises: int`.
   - **No range overlaps with board** (spec §9 #7 — `load_spots` validates and rejects at load).
   - **Equal effective stacks** asserted (spec §9 #2 — `stacks[0] == stacks[1]`).
   - **Whole-BB pot+stack values** (`pot % big_blind == 0`).
   - File size < 100 KB hard ceiling.
   - **5 categories × 3 spots**: dry rainbow, wet rainbow, monotone, paired, broadway-heavy (per §4 table).
   - **Evidence stub:** `tests/data/river_spots.json:?` — count entries, verify schema_version.

6. **Tolerance threshold matches spec.** [pre-verified clean per `audit_preprep.md` §1.5]
   - Per spec §1 + §5 step 6: per-action `|our_prob - brown_prob| < 5e-3`, per-spot `|our_game_value - brown_game_value| < 1e-3 * spot.pot`.
   - **Anti-pattern:** silent relaxation to `1e-2` or `5e-2` → must-fix.
   - Audit must check tolerance literal in **fixture, harness, AND self-sanity** — all three must use `5e-3` / `1e-3`.
   - Spec §12 open decision 1 defaults to 5e-3; any relaxation must be documented.
   - **Evidence stubs:** `tests/test_noambrown_river_parity.py:?`, `tests/data/river_spots.json:?`, `tests/test_noambrown_self_sanity.py:?`.

7. **Skip-cleanly-when-binary-missing path.** [layer 2 of 5-skipif]
   - Per spec §5 step 7 + §9 #3: when `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` does not exist, `tests/test_noambrown_river_parity.py` calls `pytest.skip("Brown's river_solver_optimized not built; run scripts/build_noambrown.sh")`.
   - Does NOT raise `FileNotFoundError`, `subprocess.CalledProcessError`, or other hard error.
   - The Agent C tests (`test_noambrown_self_sanity.py`) **don't** require the binary — they run unconditionally.
   - **Evidence stub:** `tests/test_noambrown_river_parity.py:?` — skip guard at module or test scope.

8. **License + attribution.** [pre-verified clean per `audit_preprep.md` §1.6]
   - Per spec §8: Brown's repo is **MIT** (verified at `references/code/noambrown_poker_solver/LICENSE`).
   - Wrapper module `poker_solver/parity/noambrown_wrapper.py` has the spec §8 attribution docstring header, naming Brown's repo + license + the public CLI surface we depend on.
   - **No code copied from Brown's C++.** Wrapper is original Python.
   - We **invoke the binary** (not a derivative work) and **parse JSON output** (public interface).
   - No NOTICE file update needed (MIT doesn't mandate one).
   - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:1-?` — module docstring.

9. **Subprocess + xdist safety.** [HIGH-PROB must-fix per `audit_preprep.md` §1.4 + §1.1]
   - Per spec §9 #8: subprocess invocations use **`tempfile.NamedTemporaryFile(suffix=".json", delete=False)`** per call (NOT a shared `/tmp/spot_<id>.json`). Race-condition-safe under pytest-xdist parallel runs.
   - **`os.unlink` in `finally`** — verify cleanup on exception path.
   - Per spec §9 #9: Brown binary path resolved via `Path(__file__).resolve().parents[2] / "references" / ...` (anchored to repo root, not cwd).
   - **Pre-flagged subprocess failure modes** (auditor MUST probe each per `audit_preprep.md` §1.1):
     - (a) `--bet-sizes` passed as **comma-joined string** `"0.5,1"`, NOT as separate args or Python list. Brown's `cpp/src/main.cpp` parses one comma-list arg.
     - (b) Wrapper parses the `--dump-strategy <PATH>` **JSON file**, NOT `result.stdout` (stdout is logging only).
     - (c) **`subprocess.run(..., timeout=...)`** — verify no overly-tight timeout (2000 iters ≈ 30-90s on M-series); document chosen value with rationale or set `timeout=None`.
   - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:?` — `run_brown_solver()` body.

10. **Strategy-matrix adapter.**
    - Per spec §9 #5: `our_strategy_to_brown_matrix(result, hands, infoset_keys)` aggregates our per-(hand, infoset) probabilities into Brown's `[hand × action]` matrix shape, keyed by canonicalized history.
    - Tested standalone in `test_noambrown_self_sanity.py::test_strategy_matrix_shape` (spec §10 Agent C deliverable #5).
    - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:?` + `tests/test_noambrown_self_sanity.py:?`.

11. **80% history-coverage assertion.**
    - Per spec §10 Agent B "Per-spot assertion": at least **80%** of Brown's canonical histories appear in our canonicalized result. Catches accidental tree-truncation on either side.
    - Verify this assertion is present in `test_noambrown_river_parity.py`.
    - **Evidence stub:** `tests/test_noambrown_river_parity.py:?`.

12. **Pytest marker registered.** [layer 5 of 5-skipif]
    - Per spec §10 Agent B + §12 open decision 6: `@pytest.mark.parity_noambrown` declared in `pyproject.toml` under `[tool.pytest.ini_options].markers`.
    - Spec §12 #6 prefers reuse over new markers if a `parity` / `external` marker exists; confirm no duplicate.
    - **Evidence stub:** `pyproject.toml:?` — markers section.

13. **Pot/stack units consistency.**
    - Per spec §9 #2 + §12 open decision 4: Brown's pot/stack are integer chips; ours are integer cents with `big_blind=100` cents per BB. Wrapper writes `big_blind=100` in Brown's subgame JSON so units align. Convention: `pot=1000, stack=9500, big_blind=100` → 10 BB pot, 95 BB stack.
    - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py:?` — subgame JSON construction.

14. **No new third-party dependencies.**
    - `poker_solver/parity/noambrown_wrapper.py` is pure Python + stdlib + numpy + existing `poker_solver` imports. Per spec §10 Agent A "Type-hinted; mypy --strict clean. Pure Python + standard library + numpy + the existing poker_solver imports. No new dependencies."
    - `pyproject.toml` `[project.dependencies]` unchanged.
    - **Evidence stub:** `poker_solver/parity/noambrown_wrapper.py` imports section + `pyproject.toml` dependencies block.

15. **Self-sanity test scope (Agent C).** [layers 3-4 of 5-skipif covered by Agent C's runs-without-binary contract]
    - `test_noambrown_self_sanity.py` runs without Brown's binary. Verify **8 tests** per spec §10 Agent C:
      - Spot loads into `HUNLConfig(starting_street=Street.RIVER, ...)` cleanly.
      - 2000-iter solve has `exploitability < 0.02 * pot`.
      - `result.game_value` finite + bounded.
      - History canonicalization roundtrip (10 cases per `agent_c_prompt.md:162-191`).
      - Strategy matrix shape correct.
      - No board/hand overlap in fixture.
      - `iterations_override` respected.
      - `find_brown_binary()` returns path-or-None (no exception).
    - **Evidence stub:** `tests/test_noambrown_self_sanity.py:?` — count test functions.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_report.md` with this exact structure:

```markdown
# PR 7 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-7-noambrown-diff
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_noambrown_*.py — pass/fail (note skip count if no compiler); full suite delta]

## Must-fix

[Build script not idempotent / not soft-failing; raise-encoding canonicalization wrong; all-in mapping wrong; DCFR flags wrong; missing skip path for missing binary; AGPL or non-MIT contamination; tolerance silently relaxed; new third-party dep; xdist `/tmp` collision; subprocess stdout-parsed-as-JSON. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, undocumented behavior, missing 80%-coverage assertion, fixture file violations, test holes, subprocess timeout missing/too tight, build script soft-fail edge cases on missing Xcode CLT. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-15 matching the 15 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: Brown's MIT license respected; wrapper depends only on Brown's public CLI + JSON output schema; no C++ code copied. Cite spec §8 attribution header in the wrapper.]

## Release-notes follow-up

[Note for v0.5.1 / v0.6.0: Brown diff validation landed in PR 7. If PR 7 added new public API (parity package), call out in release notes; otherwise v0.5.0 notes stand as-is. See `audit_preprep.md` post-audit triage.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** build script broken (hard-fails on missing compiler), wrong raise-encoding (silently mis-canonicalizes), wrong all-in mapping, wrong DCFR flags, missing skip path on missing binary, license contamination (any code copy), tolerance silently relaxed, fixture file with board/range overlap, xdist `/tmp` collision (shared dump path), subprocess parses `result.stdout` as JSON instead of dump file. Blocks PR.
- **should-fix:** missing 80%-coverage assertion, missing self-sanity test, ambiguous error messages, awkward APIs, subprocess timeout missing or too tight, `-march=native` host-mismatch caching, build script soft-fail edge cases. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that produces silently-wrong diff results (spurious matches, spurious failures) → must-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr7_prep/audit_report.md`.
- The Brown binary may or may not be built when you audit — that's expected. Check the skip-path is correct, not that the diff test actually runs.
- HIGH-PROB risk surfaces (focus areas 2, 9 — and the three sub-probes in 9) MUST get paragraph-level discussion even with no defect found.

Begin by reading the spec, then the diff, then the new files. Then write the report.
