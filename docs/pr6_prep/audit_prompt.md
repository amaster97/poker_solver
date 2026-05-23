# PR 6 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-6-rust-hunl-port` branch and you have not seen the design discussions. Your job is to audit the PR 6 implementation (Rust port of the HUNL postflop solver) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-6-rust-hunl-port` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md` — read end-to-end. Note the 2026-05-21 amendments (metadata un-nesting on load, `AbstractionRef`, `use_pcs` pre-mirror, 1e-3/5e-3 tolerance cluster) AND the 2026-05-22 amendments (real on-disk format: string-keyed dict-of-dict + JSON `metadata` blob, NOT `HandLookup` + top-level scalars; `resolve_abstraction_ref()` is canonical; PR 9 §6 dispatch ordering invariant for `_solve_rust`).
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 6 entries.

## Inputs to read (in order)

1. **The spec:** internalize §3 (license sourcing strategy — this is a HARD audit gate), §4 (files to create — particularly §4.1 Rust `HUNLConfig` mirror, §4.4 abstraction loader, §4.5 solver entrypoint), §5 (PyO3 surface), §6 (Python tier integration, especially §6.3 `AbstractionRef`), §7 (differential test scope + tolerance rationale), §9 (critical correctness items — 15 items), §10 (risks).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-6-rust-hunl-port`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 6 entries.
4. **The actual new / modified files:** at minimum
   - `crates/cfr_core/src/hunl.rs`
   - `crates/cfr_core/src/hunl_tree.rs`
   - `crates/cfr_core/src/hunl_eval.rs`
   - `crates/cfr_core/src/abstraction.rs`
   - `crates/cfr_core/src/hunl_solver.rs`
   - `crates/cfr_core/src/lib.rs` (PyO3 bindings extended)
   - `crates/cfr_core/Cargo.toml` (`ndarray-npy` added)
   - `poker_solver/solver.py` (HUNL Rust branch in `_solve_rust`)
   - `poker_solver/hunl.py` (`_serialize_hunl_config` added)
   - `poker_solver/cli.py` (`--backend rust` on postflop solve)
   - `tests/test_hunl_diff.py`
   - `crates/cfr_core/tests/test_hunl_rust.rs`
   - any other touched files

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **License hygiene — ZERO AGPL contamination (CRITICAL).**
   - Per spec §3 license table: AGPL repos (`postflop-solver`, `TexasSolver`) are **read-only inspiration** — never copy code, function bodies, or distinctive type names.
   - `shark-2.0` is **unlicensed** — treat as all-rights-reserved. **No study, no inspection, no patterns**.
   - For every new `.rs` file in `crates/cfr_core/src/hunl_*` and `abstraction.rs`: verify a module-level docstring per the template in spec §3:
     - References Python source (`poker_solver/hunl.py` etc.) as truth.
     - Names MIT/Apache sources (`noambrown_poker_solver`, `open_spiel`, `slumbot2019`) where patterns are adapted, with explicit "MIT — pattern adapted" framing.
     - Explicit "NEVER copy from postflop-solver / TexasSolver" line.
   - Grep new files for any function name, type name, or distinctive idiom from `references/code/postflop-solver/src/` and `references/code/TexasSolver/`. Distinctive AGPL names to grep: `bunching`, `valid_indices`, `isomorphism_swap`, `add_lines`, `flatten_action_tree`, `compute_subgame_solver`. Found → **must-fix**.
   - No code copied verbatim from `shark-2.0`. Grep prohibited.

2. **MIT/Apache attribution headers present on adapted patterns.**
   - `hunl.rs`: noambrown `river_game.h/.cpp` (MIT) for Tree/TreeNode/Action shape. Attributed.
   - `hunl_eval.rs`: noambrown `cards.h/.cpp` (MIT) and/or slumbot `hand_value_tree.cpp` (MIT). Attributed.
   - `abstraction.rs`: `ndarray-npy` (MIT/Apache 2.0 dual). Dep declared in `Cargo.toml`. License audit script (if present) confirms.

3. **Bucket-file (.npz) Rust↔Python byte-roundtrip parity.**
   - Per spec §4.4 (2026-05-22 amendment) + PR 4's committed `poker_solver/abstraction/buckets.py`: the `.npz` stores per-street `*_board_index` and `*_hand_index` as **JSON-encoded `dict[str, int]` / `dict[str, dict[str, int]]`** inside one-element bytes arrays, NOT as `Vec<u32>` top-level numpy arrays. `metadata` is similarly a single JSON-encoded dict inside a one-element bytes array. Rust uses `serde_json::from_slice` on each.
   - Rust `AbstractionTables` shape: `HashMap<String, u32>` board indices, `HashMap<String, HashMap<String, u32>>` hand indices, plus a typed `metadata: AbstractionMetadata` struct populated from the parsed `metadata` JSON (containing `schema_version`, `version`, `bucket_counts`, `feature_bins`, `seed`). Plus `source_path: PathBuf` populated by the loader (not on disk).
   - Canonical board / hand keys are **strings** (sorted-by-(rank, suit) joined card-strings produced by the suit-iso canonicalizer), NOT `u32`.
   - If the audit finds top-level `Vec<u32>` board-index fields, a `HandLookup` packed struct, or top-level `bucket_counts`/`schema_version`/`feature_bins`/`seed` fields on `AbstractionTables`, flag as **must-fix** — the loader cannot parse the on-disk file.
   - Schema-version check: `schema_version == 1` else loud error with "rebuild abstraction via `poker-solver precompute-abstraction`".
   - **`test_abstraction_canonicalization_matches_python`** runs 10K random (board, hole) inputs through both Python and Rust canonicalization → same **string** keys. Spec §4.4 + §9 #2.
   - **`test_abstraction_lookup_bucket_matches_python`** runs 10K random inputs → identical bucket IDs.

4. **Integer-chip arithmetic in Rust (NO `f64` chip values).**
   - Per spec §9 #3 + §4.1: `HUNLState::contributions`, `stacks`, `to_call` are all `i32` cents.
   - Float crossings (pot-fraction multiplications) round IMMEDIATELY back to `i32`. No `f64` chip accumulators anywhere.
   - **Banker's rounding parity:** Python's `round()` rounds-half-to-even; Rust's `f64::round()` rounds-half-away-from-zero. Per spec §9 #3 + §10: use `(x + 0.5).floor() as i32` for positive-integer rounding to match Python. Verify in `compute_bet_amount` / `compute_raise_to`. A wrong rounding mode silently diverges from Python.

5. **Diff test passes within 5e-3 / 1e-3 tolerance cluster.**
   - Per spec §7.3 (reaffirmed in the 2026-05-21 amendments as canonical across PR 6/7/8/9): river-only subgame **1e-3** per-action; flop subgame **5e-3** per-action.
   - `test_hunl_river_subgame_diff_python_vs_rust` at 1000 iterations: `|python_strategy - rust_strategy| < 1e-3` per (infoset, action), with `1e-6` absolute floor.
   - `test_hunl_flop_dry_3size_diff_python_vs_rust_tiny_abstraction` at 200 iterations: tolerance **5e-3**.
   - **Anti-pattern check:** if the test tolerance is silently looser than spec (e.g., 1e-2 or 5e-2 to make the test pass), flag as must-fix.

6. **No NEON intrinsics / no `std::arch::aarch64`.**
   - Per spec §9 #10: PR 6 is "readable + slow-but-correct first." All NEON SIMD is deferred to PR 8.
   - Grep new `.rs` files for `std::arch`, `aarch64`, `vfma`, `vld1`, `vaddq_f64`. None should be present.

7. **`unsafe` discipline.**
   - PR 6 should have **zero `unsafe`** outside PyO3 boilerplate (since no SIMD). If `unsafe` is present anywhere except boilerplate, it must have a `// SAFETY: ...` comment per spec §9 #11 / PR 8 §3 convention.

8. **`HUNLConfig.use_pcs: bool` field declared correctly.**
   - Per the 2026-05-21 spec amendment (B2/B6 + consistency review I6): the Rust `HUNLConfig` (§4.1) **pre-emptively** includes `use_pcs: bool` (default `false`) to avoid schema-migration churn when PR 8 lands.
   - Verify the field is present, defaults to `false`, and is plumbed through `_serialize_hunl_config` on the Python side.
   - PR 6 does NOT implement the PCS code path — only the field. PR 8 implements PCS.

9. **`HUNLConfig.abstraction` carries `AbstractionRef`, not the in-memory `AbstractionTables`; and `_solve_rust` uses the canonical `resolve_abstraction_ref()` resolver.**
   - Per spec §6.3 (B2 resolution): PR 4 declares `AbstractionRef = (source_path: str, version: str)`; PR 6 consumes only `(source_path, version)` across the PyO3 boundary. Rust loads the `.npz` independently via `load_abstraction(path)` Rust-side.
   - **NEVER serializes the full bucket table over PyO3** (up to 750 MB across FFI — unacceptable).
   - Loader checks `AbstractionTables.metadata.version == config.abstraction.version` and errors on mismatch.
   - **Python-side `_solve_rust` MUST call `resolve_abstraction_ref(cfg.abstraction)` rather than reach into `cfg.abstraction.source_path` directly.** The resolver is `@lru_cache(maxsize=4)`-decorated in `poker_solver/abstraction/buckets.py` and raises on metadata-version mismatch. Bypassing it skips the cache + the version check. If `_solve_rust` (in `poker_solver/solver.py`) reads `game.config.abstraction.source_path` without going through `resolve_abstraction_ref`, flag as **must-fix**.

10. **PR 9 §6 canonical dispatch ordering — HUNL postflop Rust branch composes AFTER push/fold short-circuit.**
    - Per spec §6.1 (2026-05-22 amendment): when wiring the Rust HUNL solve path into Python `solver.solve()` / `_solve_rust`, the new HUNL postflop branch must compose **AFTER** the PR 3.5 push/fold short-circuit (PR 9 §6 is canonical). Canonical ordering, head-to-tail:
      1. push/fold short-circuit (PR 3.5; routes ≤15-BB HUNL preflop to the chart fast path)
      2. HUNL postflop Rust branch (PR 6 — `backend == "rust"` + `isinstance(game, HUNLPoker)` + postflop)
      3. HUNL postflop Python fallback (PR 5)
      4. HUNL preflop branch (PR 9 — not implemented in PR 6; `NotImplementedError`)
      5. Kuhn/Leduc branches (PR 1/2 — unchanged)
    - If the audit finds the HUNL Rust elif inserted **before** the push/fold check (in `_solve_rust`), flag as **must-fix** — low-stack postflop solves silently bypass the chart fast path.

11. **PyO3 GIL handling.**
    - Per spec §5 + §9 #11 + §10: `solve_hunl_postflop` wraps the DCFR loop in `py.allow_threads(|| { … })`. Otherwise multi-call scenarios (UI + solver threads) deadlock.
    - The PyO3 function signature in `lib.rs` releases the GIL. Tested implicitly by `test_hunl_rust_deterministic_with_seed` running two threaded solves.

12. **Byte-for-byte infoset key parity.**
    - Per spec §9 #1: Rust's `format!` output matches Python's `f""` output character-for-character for both lossless and bucketed forms.
    - `test_hunl_infoset_key_lossless_format` + `test_hunl_infoset_key_bucketed_format` run 100 random states per format.
    - Card sort order matches Python's; integer formatting matches.

13. **`_solve_rust` Python-side branch.**
    - `solver.py::_solve_rust` appends an HUNL branch per spec §6.1:
      - Preflop → `NotImplementedError("HUNL preflop port lands in PR 9. Use --hunl-mode postflop.")`
      - Postflop → calls `_rust.solve_hunl_postflop(config_json, abstraction_path, ...)`, then **Python recomputes exploitability + game_value** from the Rust-returned strategy (same pattern as Kuhn/Leduc per `_solve_rust:295`).
    - Pattern: Rust returns strategy + iterations + wallclock; Python computes the rest. Avoids cross-tier float drift in those values.

14. **Showdown ties / utility split 50/50.**
    - Per spec §9 #6: Python returns `(0.0, 0.0)` on tie; Rust must too. `Strength` equality must trip the tie path in `HUNLState::utility`.
    - Tested via `test_hunl_strength_eval_handles_ties` (§8.3 #10).

15. **No new dependencies beyond `ndarray-npy`.**
    - Compare `Cargo.toml` on `pr-6` vs `integration`. New dep: only `ndarray-npy = "0.9"` (MIT/Apache 2.0 dual). Anything else → must-fix.
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

**Test status:** [pytest tests/test_hunl_diff.py — pass/fail; `cargo test --all` — pass/fail; full suite delta]

## Must-fix

[License contamination (any AGPL function-body / type-name match), missing MIT attribution headers, `f64` chip values, banker's rounding wrong, diff-test tolerance silently loosened, NEON intrinsics present (deferred to PR 8), `unsafe` without SAFETY comments, `HUNLConfig.use_pcs` missing, `AbstractionRef` not used (or `resolve_abstraction_ref()` bypassed), PyO3 GIL not released, new third-party deps, **Rust `AbstractionTables` shape doesn't match the committed PR 4 on-disk layout** (e.g., top-level `Vec<u32>` board indices or `HandLookup` packed struct instead of `HashMap<String, u32>` + JSON-parsed dicts), **HUNL Rust branch in `_solve_rust` inserted before the push/fold short-circuit** (violates PR 9 §6 canonical dispatch ordering). Each: file:line + what + fix.]

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

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** correctness bugs (`f64` chip values, banker-rounding wrong, infoset key drift), license violations (AGPL contamination, missing attribution), test scope erosion (diff tolerance silently loose), `unsafe` without SAFETY comments, missing GIL release, missing `use_pcs` field, Rust `AbstractionTables` shape diverges from committed PR 4 on-disk layout, `resolve_abstraction_ref()` bypassed in `_solve_rust`, HUNL Rust elif inserted before the PR 3.5 push/fold short-circuit (violates PR 9 §6 canonical ordering), regressions in PR 1-5. Blocks PR.
- **should-fix:** undocumented behavior, awkward APIs, missing assertions, test holes. Doesn't block.
- **nice-to-fix:** style, clippy, comments. Pure polish.

When in doubt: any silently-divergent behavior between Python and Rust → must-fix. Developer-experience issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers.
- Spec-silent behavior → "Spec coverage gaps" with explicit-decision recommendation.
- Do not modify code. Audit only. Your only write is to `docs/pr6_prep/audit_report.md`.
- For license check, you can use `grep -rEi 'bunching|valid_indices|isomorphism_swap|flatten_action_tree' crates/cfr_core/src/` and similar.

Begin by reading the spec (especially the 2026-05-21 + 2026-05-22 amendments at the top about metadata un-nesting / **on-disk format reality** / `AbstractionRef` / `use_pcs` pre-mirror / dispatch ordering invariant), then §3 (license posture), then **read `poker_solver/abstraction/buckets.py` (`save_abstraction` + `load_abstraction`) to ground-truth the on-disk shape Rust must match**, then the diff, then the new files. Then write the report.
