# PR 6 audit agent prompt (FINAL — staged 2026-05-22 post-Agent-A/B)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself. This file is the customized successor to `docs/pr6_prep/audit_prompt.md` — it folds in what Agents A + B actually shipped (5 spec amendments, bit-exact parity claim, license attribution headers) so the audit focuses on the real surface, not the pre-launch prediction.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-6-rust-hunl-port` branch and you have not seen the design discussions or the agent reports. Your job is to audit the PR 6 implementation (Rust port of the HUNL postflop solver) against the spec **as amended during the agent run**, and report findings in a structured Markdown report.

Treat the spec (including the in-flight amendments documented in §"Spec amendments to re-verify" below) as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-6-rust-hunl-port` (branched from `integration`; note the suffix is `-port`, NOT `-postflop`)
- **Working-tree state:** Agents A + B wrote into the working tree but did NOT commit yet. The audit must inspect uncommitted files (`git status` will show modified + untracked). The reconciliation step landed changes; verify they are coherent before the eventual commit.
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md` — read end-to-end. Note both rounds of amendments (the 2026-05-21 cluster: metadata un-nesting on load, `AbstractionRef`, `use_pcs` pre-mirror, 1e-3/5e-3 tolerance cluster; AND the 2026-05-22 amendments: real on-disk format = string-keyed dict-of-dict + JSON `metadata` blob, NOT `HandLookup` + top-level scalars; `resolve_abstraction_ref()` is canonical; PR 9 §6 dispatch ordering invariant for `_solve_rust`).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 6 entries.
- **Agent prompts (read for context on what was asked):** `docs/pr6_prep/agent_a_prompt.md`, `docs/pr6_prep/agent_b_prompt.md`, `docs/pr6_prep/agent_c_prompt.md`.

## Inputs to read (in order)

1. **The spec** (in particular §3 license sourcing — HARD audit gate, §4.1 Rust `HUNLConfig` mirror, §4.4 abstraction loader, §4.5 solver entrypoint, §5 PyO3 surface, §6 Python integration including §6.3 `AbstractionRef`, §7 differential test scope + tolerance rationale, §9 critical-correctness items, §10 risks).
2. **`poker_solver/abstraction/buckets.py`** (`save_abstraction` + `load_abstraction` + `resolve_abstraction_ref`) — ground-truth the on-disk shape Rust must match.
3. **The branch diff:** `git diff integration -- crates/ poker_solver/ tests/ Cargo.lock pyproject.toml CHANGELOG.md` while on `pr-6-rust-hunl-port`. Also `git log integration..HEAD --oneline` (may be empty if uncommitted).
4. **The actual new / modified files** (verified present 2026-05-22):
   - **New Rust modules:** `crates/cfr_core/src/hunl.rs`, `crates/cfr_core/src/hunl_tree.rs`, `crates/cfr_core/src/hunl_eval.rs`, `crates/cfr_core/src/abstraction.rs`, `crates/cfr_core/src/hunl_solver.rs`
   - **Modified Rust:** `crates/cfr_core/src/lib.rs` (PyO3 binding extended), `crates/cfr_core/Cargo.toml` (`ndarray-npy = "0.9"` added)
   - **New Rust tests:** `crates/cfr_core/tests/test_hunl_rust.rs`, `crates/cfr_core/tests/hunl_state_unit.rs`
   - **Modified Python:** `poker_solver/solver.py` (HUNL Rust branch in `_solve_rust`), `poker_solver/hunl.py` (`_serialize_hunl_config`), `poker_solver/cli.py` (`--backend rust` plumbing), `poker_solver/__init__.py`
   - **New Python test:** `tests/test_hunl_diff.py`
   - `pyproject.toml`, `Cargo.lock`, `CHANGELOG.md`

## Spec amendments to re-verify (CUSTOMIZED for what Agents A + B actually shipped)

Agents A + B applied **5 spec amendments** during the run. Each one is a known divergence from the original spec; the audit must explicitly re-verify each landed correctly in the merged code, not just in one agent's branch.

1. **`HUNLConfig` shape drift — `use_pcs: bool` field pre-mirror.**
   - Per spec §4.1 (post-2026-05-21 amendment), Rust `HUNLConfig` includes `use_pcs: bool` (default `false`) so PR 8 has no schema migration. Verify the field exists in `crates/cfr_core/src/hunl.rs::HUNLConfig` (around line 202), defaults to `false`, AND is plumbed through `_serialize_hunl_config` in `poker_solver/hunl.py` (around line 640).
   - PR 6 does NOT implement the PCS code path. If the audit finds PCS logic in `hunl_solver.rs` or branches keyed on `use_pcs`, flag as **should-fix** (scope creep into PR 8).
   - If `use_pcs` is missing from either side, flag as **must-fix** (spec amendment not honored).

2. **`action_context` visibility — `pub fn` vs `pub(crate)`.**
   - Confirmed present at `crates/cfr_core/src/hunl.rs:347` as `pub fn action_context(...)`. The pre-drafted spec said `pub(crate)`. The widened visibility is intentional (Agent B's `hunl_solver.rs` consumes it from the same crate, but tests in `crates/cfr_core/tests/hunl_state_unit.rs` need crate-external access). Verify the widening did not leak `ActionContext` into the PyO3 surface (it should NOT appear in `crates/cfr_core/src/lib.rs`'s `#[pyfunction]` signatures or be exported to Python).
   - If `ActionContext` is leaked over PyO3 → **must-fix** (Python tier never sees raw action-context).

3. **`lib` crate-type set to `["cdylib", "rlib"]`.**
   - Per the pre-launch readiness review, the crate must produce BOTH `cdylib` (for the PyO3 `_rust` extension) AND `rlib` (so the new `crates/cfr_core/tests/test_hunl_rust.rs` integration test can `use cfr_core::*`). Verify `crates/cfr_core/Cargo.toml` line 16 reads `crate-type = ["cdylib", "rlib"]`.
   - If only `cdylib`, integration tests fail to link → **must-fix**.

4. **On-disk `.npz` format = string-keyed dict-of-dict + JSON `metadata`.**
   - Re-confirm against `poker_solver/abstraction/buckets.py::save_abstraction`: each `{flop,turn,river}_board_index` and `{flop,turn,river}_hand_index` is a one-element bytes array containing `json.dumps(d, sort_keys=True, separators=(',',':')).encode()`. `metadata` is similarly one JSON-encoded dict. NO top-level `Vec<u32>` arrays, NO `HandLookup` packed struct.
   - Rust loader (`crates/cfr_core/src/abstraction.rs`): verify it parses each via `serde_json::from_slice` and produces `HashMap<String, u32>` (board) + `HashMap<String, HashMap<String, u32>>` (hand). Verify `AbstractionMetadata` is a typed struct populated from the JSON-decoded `metadata` blob (containing `schema_version`, `version`, `bucket_counts`, `feature_bins`, `seed`), NOT top-level fields on `AbstractionTables`.
   - If the audit finds `Vec<u32>` board indices or `HandLookup` → **must-fix** (loader cannot parse the on-disk file written by PR 4).

5. **PR 9 §6 dispatch ordering invariant (canonical, post-2026-05-22 amendment).**
   - Verify `poker_solver/solver.py` `solve()` and `_solve_rust()` compose the HUNL Rust elif **AFTER** the PR 3.5 push/fold short-circuit, head-to-tail:
     1. push/fold short-circuit (PR 3.5; ≤15-BB HUNL preflop → chart fast path)
     2. HUNL postflop Rust branch (PR 6 — `backend == "rust"` + `isinstance(game, HUNLPoker)` + postflop)
     3. HUNL postflop Python fallback (PR 5)
     4. HUNL preflop branch (PR 9 — `NotImplementedError` in PR 6)
     5. Kuhn/Leduc branches (PR 1/2 — unchanged)
   - Verified in `solver.py` lines 55-65 (comment block + `is_pushfold_mode` short-circuit at line 67-74, then Rust branch at line 80). Re-check that no later edit inverted the order.
   - If the Rust elif appears before the push/fold check → **must-fix** (low-stack postflop solves silently bypass the chart fast path).

## Cross-agent claims to spot-check (CUSTOMIZED)

Agent A and Agent B reported these high-confidence claims. The audit's job is to spot-check, NOT trust:

A. **Bit-exact parity at 1000 iterations** (river subgame). Agent A reported `|python_strategy - rust_strategy| < 1e-6` (well inside the 1e-3 spec tolerance) on the river fixture at 1000 iters. **Re-run** `pytest tests/test_hunl_diff.py::test_hunl_river_subgame_diff_python_vs_rust -xvs` and confirm:
   - The test actually runs (not skipped via the defensive-import guards at the top of `test_hunl_diff.py`).
   - Per-action max abs diff is reported in the test output.
   - Tolerance literal in the test source equals `1e-3` (NOT silently loosened).
   - If the test SKIPS because `_rust.solve_hunl_postflop` is missing → **must-fix** (the entire PR 6 deliverable depends on this binding).

B. **License attribution headers verbatim per Agent B's report** on `abstraction.rs` and `hunl_solver.rs`. The header template per spec §3 requires: (1) Python source named as truth, (2) MIT/Apache sources named where patterns adapted, (3) explicit "NEVER copy from postflop-solver / TexasSolver" line. Verify headers exist on:
   - `crates/cfr_core/src/abstraction.rs` (lines 1-25 — confirmed: `buckets.py` MIT for semantics, `ndarray-npy` MIT/Apache, slumbot2019 MIT for pattern, AGPL exclusion line at 16-17).
   - `crates/cfr_core/src/hunl_solver.rs` (lines 1-22 — confirmed: `hunl_solver.py` MIT, `dcfr.rs` MIT-adapted noambrown trainer.cpp, AGPL exclusion).
   - Also re-verify the same 3-clause structure on `hunl.rs`, `hunl_tree.rs`, `hunl_eval.rs`.
   - If any new `.rs` file lacks all 3 clauses → **must-fix**.

C. **24 inline tests + 19 integration tests pass** (Agent B's report). Verify counts via `grep -c '#\[test\]' crates/cfr_core/src/hunl*.rs crates/cfr_core/src/abstraction.rs crates/cfr_core/tests/*.rs` AND by running `cargo test --package cfr_core 2>&1 | grep "test result"`. Expected: ~43 passing (24 inline + 19 integration). If counts diverge → **should-fix** (test inventory drifted from the report, may indicate forgotten tests).

## Remaining audit focus areas (all 15 from the original template — unchanged)

For each focus area below, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **License hygiene — ZERO AGPL contamination (CRITICAL).**
   - Per spec §3 license table: AGPL repos (`postflop-solver`, `TexasSolver`) are **read-only inspiration** — never copy code, function bodies, or distinctive type names.
   - `shark-2.0` is **unlicensed** — treat as all-rights-reserved. **No study, no inspection, no patterns**.
   - Grep new files for any function name, type name, or distinctive idiom from `references/code/postflop-solver/src/` and `references/code/TexasSolver/`. Distinctive AGPL names to grep: `bunching`, `valid_indices`, `isomorphism_swap`, `add_lines`, `flatten_action_tree`, `compute_subgame_solver`. Found → **must-fix**.
   - Command: `grep -rEi 'bunching|valid_indices|isomorphism_swap|flatten_action_tree|compute_subgame_solver|add_lines' crates/cfr_core/src/`. Should return zero hits.

2. **MIT/Apache attribution headers present on adapted patterns.** (Cross-listed with cross-agent claim B above.)
   - `hunl.rs`: noambrown `river_game.h/.cpp` (MIT) for Tree/TreeNode/Action shape.
   - `hunl_eval.rs`: noambrown `cards.h/.cpp` (MIT) and/or slumbot `hand_value_tree.cpp` (MIT).
   - `abstraction.rs`: `ndarray-npy` (MIT/Apache 2.0 dual). Dep declared in `Cargo.toml`.

3. **Bucket-file (.npz) Rust↔Python byte-roundtrip parity.** (Cross-listed with spec amendment #4.)
   - Schema-version check: `schema_version == 1` else loud error with "rebuild abstraction via `poker-solver precompute-abstraction`".
   - **`test_abstraction_canonicalization_matches_python`** runs 10K random (board, hole) inputs through both Python and Rust canonicalization → same **string** keys.
   - **`test_abstraction_lookup_bucket_matches_python`** runs 10K random inputs → identical bucket IDs.

4. **Integer-chip arithmetic in Rust (NO `f64` chip values).**
   - Per spec §9 #3 + §4.1: `HUNLState::contributions`, `stacks`, `to_call` are all `i32` cents. (Confirmed in module docstring of `hunl.rs` lines 17-24.)
   - Float crossings (pot-fraction multiplications) round IMMEDIATELY back to `i32`. No `f64` chip accumulators anywhere.
   - **Banker's rounding parity:** Python's `round()` rounds-half-to-even; Rust's `f64::round()` rounds-half-away-from-zero. Per spec §9 #3 + §10: use `(x + 0.5).floor() as i32` for positive-integer rounding to match Python. Verify in `compute_bet_amount` / `compute_raise_to` (around `hunl.rs:891` / `:906`). A wrong rounding mode silently diverges from Python.

5. **Diff test passes within 5e-3 / 1e-3 tolerance cluster.**
   - Per spec §7.3: river-only subgame **1e-3** per-action; flop subgame **5e-3** per-action.
   - `test_hunl_river_subgame_diff_python_vs_rust` at 1000 iterations.
   - `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` at 200 iterations.
   - **Anti-pattern check:** if the test tolerance is silently looser than spec (e.g., 1e-2 or 5e-2 to make the test pass), flag as must-fix. (Cross-listed with cross-agent claim A.)

6. **No NEON intrinsics / no `std::arch::aarch64`.**
   - Per spec §9 #10: PR 6 is "readable + slow-but-correct first." All NEON SIMD deferred to PR 8.
   - Grep new `.rs` files for `std::arch`, `aarch64`, `vfma`, `vld1`, `vaddq_f64`. None should be present.

7. **`unsafe` discipline.**
   - PR 6 should have **zero `unsafe`** outside PyO3 boilerplate (no SIMD yet). If `unsafe` is present anywhere except boilerplate, it must have a `// SAFETY: ...` comment per spec §9 #11.

8. **`HUNLConfig.use_pcs: bool` field declared correctly.** (Cross-listed with spec amendment #1.)

9. **`HUNLConfig.abstraction` carries `AbstractionRef`, not in-memory `AbstractionTables`; `_solve_rust` uses `resolve_abstraction_ref()`.**
   - Per spec §6.3: PR 4 declares `AbstractionRef = (source_path: str, version: str)`; PR 6 consumes only `(source_path, version)` across the PyO3 boundary. Rust loads the `.npz` independently via `load_abstraction(path)` Rust-side.
   - **NEVER serializes the full bucket table over PyO3** (up to 750 MB across FFI — unacceptable).
   - **Python-side `_solve_rust` MUST call `resolve_abstraction_ref(cfg.abstraction)` rather than reach into `cfg.abstraction.source_path` directly.** Verified present at `solver.py:366-378` (`from poker_solver.abstraction.buckets import resolve_abstraction_ref` → `tables = resolve_abstraction_ref(game.config.abstraction)` → `abstraction_path = str(tables.source_path)`). Re-confirm no path bypasses this.
   - If `_solve_rust` reads `game.config.abstraction.source_path` directly anywhere → **must-fix** (skips LRU cache + version check).

10. **PR 9 §6 canonical dispatch ordering.** (Cross-listed with spec amendment #5.)

11. **PyO3 GIL handling.**
    - Per spec §5 + §9 #11 + §10: `solve_hunl_postflop` wraps the DCFR loop in `py.allow_threads(|| { … })`. Otherwise multi-call scenarios (UI + solver threads) deadlock.
    - Verify in `crates/cfr_core/src/lib.rs` around the new HUNL `#[pyfunction]`. Tested implicitly by `test_hunl_rust_deterministic_with_seed` running two threaded solves (see `tests/test_hunl_diff.py:332`).

12. **Byte-for-byte infoset key parity.**
    - Per spec §9 #1: Rust's `format!` output matches Python's `f""` output character-for-character for both lossless and bucketed forms.
    - `test_hunl_infoset_key_lossless_format` + `test_hunl_infoset_key_bucketed_format` run 100 random states per format.

13. **`_solve_rust` Python-side branch.**
    - `solver.py::_solve_rust` appends an HUNL branch per spec §6.1:
      - Preflop → `NotImplementedError("HUNL preflop port lands in PR 9. Use --hunl-mode postflop.")`
      - Postflop → calls `_rust.solve_hunl_postflop(config_json, abstraction_path, ...)`, then **Python recomputes exploitability + game_value** from the Rust-returned strategy (same pattern as Kuhn/Leduc).

14. **Showdown ties / utility split 50/50.**
    - Per spec §9 #6: Python returns `(0.0, 0.0)` on tie; Rust must too. `Strength` equality must trip the tie path in `HUNLState::utility`.

15. **No new dependencies beyond `ndarray-npy`.**
    - Compare `Cargo.toml` on `pr-6` vs `integration`. New dep: only `ndarray-npy = "0.9"` (MIT/Apache 2.0 dual). Confirmed at `crates/cfr_core/Cargo.toml:31`. Anything else → must-fix.
    - `pyproject.toml`: no new Python deps.

16. **Existing tests still pass.**
    - PR 1 (Kuhn diff), PR 2 (Leduc diff), PR 3 (HUNL core), PR 4 (abstraction), PR 5 (HUNL postflop Python) tests all pass.
    - `cargo test --all` passes in <2 minutes.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` with this exact structure:

```markdown
# PR 6 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-6-rust-hunl-port
**Diff size:** [N modified + M new files = ±X LoC total; Rust LoC + Python LoC delta]

**Test status:** [pytest tests/test_hunl_diff.py — pass/fail with per-action diff numbers from the river + flop tests; `cargo test --all` — pass/fail with #tests run; full suite delta vs integration]

## Spec amendments re-verified

[5 amendments from §"Spec amendments to re-verify" above. Each: PASS/FAIL + file:line evidence.]

## Cross-agent claims spot-checked

[3 claims (A/B/C) from §"Cross-agent claims to spot-check". Each: CONFIRMED/REFUTED + evidence.]

## Must-fix

[License contamination (AGPL function-body / type-name match), missing MIT attribution headers, `f64` chip values, banker's rounding wrong, diff-test tolerance silently loosened, NEON intrinsics present (deferred to PR 8), `unsafe` without SAFETY comments, `HUNLConfig.use_pcs` missing, `AbstractionRef` not used (or `resolve_abstraction_ref()` bypassed), PyO3 GIL not released, new third-party deps, Rust `AbstractionTables` shape doesn't match the committed PR 4 on-disk layout, HUNL Rust branch in `_solve_rust` inserted before the push/fold short-circuit. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Code smell, undocumented behavior, awkward APIs, missing assertions, test holes. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, clippy lints, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement per spec §3: every new `.rs` file has its attribution docstring; ZERO function-body / type-name matches against `postflop-solver`, `TexasSolver`, `shark-2.0`. Cite specific docstrings + grep evidence.]

## Overall verdict

[One of: "READY for commit", "READY-WITH-PATCHES (must-fix items resolved before commit)", or "NOT READY — see must-fix". 2-3 sentence justification. **Expected verdict given the 5 spec amendments + cross-agent open issues: READY-WITH-PATCHES at worst. NOT-READY would be a surprise.**]
```

## Severity rules (unchanged from template)

- **must-fix:** correctness bugs (`f64` chip values, banker-rounding wrong, infoset key drift), license violations (AGPL contamination, missing attribution), test scope erosion (diff tolerance silently loose), `unsafe` without SAFETY comments, missing GIL release, missing `use_pcs` field, Rust `AbstractionTables` shape diverges from committed PR 4 on-disk layout, `resolve_abstraction_ref()` bypassed in `_solve_rust`, HUNL Rust elif inserted before the PR 3.5 push/fold short-circuit (violates PR 9 §6 canonical ordering), regressions in PR 1-5. Blocks PR.
- **should-fix:** undocumented behavior, awkward APIs, missing assertions, test holes, scope creep (e.g., PCS logic landed in PR 6). Doesn't block.
- **nice-to-fix:** style, clippy, comments. Pure polish.

When in doubt: any silently-divergent behavior between Python and Rust → must-fix. Developer-experience issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps" with explicit-decision recommendation.
- Do not modify code. Audit only. Your only write is to `docs/pr6_prep/audit_report.md`.
- The branch may be **uncommitted** at audit time (working-tree changes only). Use `git diff integration` (no `..HEAD` needed) to inspect — that reads the working tree directly.

Begin by reading the spec (especially the 2026-05-21 + 2026-05-22 amendments at the top about metadata un-nesting / on-disk format reality / `AbstractionRef` / `use_pcs` pre-mirror / dispatch ordering invariant), then §3 (license posture), then **`poker_solver/abstraction/buckets.py` (`save_abstraction` + `load_abstraction` + `resolve_abstraction_ref`)** to ground-truth the on-disk shape Rust must match, then the working-tree diff, then the new files. Then write the report.

**Expected verdict given the 5 spec amendments + 2 cross-agent open issues: READY-WITH-PATCHES at worst. NOT-READY would be a surprise and warrants escalation back to the orchestrator before writing the report.**
