# PR 4 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-4-card-abstraction` branch and you have not seen the design discussions. Your job is to audit the PR 4 implementation (card abstraction pipeline — EMD bucketing, Python tier) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-4-card-abstraction` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md` — read this end-to-end before anything else.
- **Implementation log (for context on decisions made during the build, including any mid-stream spec amendments):** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim entries dated on or after PR 4 kickoff.

## Inputs to read (in order)

1. **The spec:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`. Internalize §3 (conceptual architecture), §4 (pipeline stages), §5 (files to create), §6 (files to modify), §7 (design decisions), §10 (critical correctness items via the "Risks" framing), and §12 (open questions). Pay particular attention to the 2026-05-21 amendments at the top regarding `AbstractionRef` and the nested `metadata` dict.
2. **The branch diff:** run `git diff integration...HEAD` while on `pr-4-card-abstraction`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — entries about PR 4 implementation choices, especially deviations.
4. **The actual new / modified files:** at minimum
   - `poker_solver/abstraction/__init__.py`
   - `poker_solver/abstraction/equity_features.py`
   - `poker_solver/abstraction/emd_clustering.py`
   - `poker_solver/abstraction/buckets.py`
   - `poker_solver/abstraction/precompute.py`
   - `poker_solver/hunl.py` (added `abstraction: Optional[AbstractionRef]` field + `infoset_key` branch)
   - `poker_solver/__init__.py` (re-exports)
   - `poker_solver/cli.py` (`precompute-abstraction` subcommand + `--abstraction` flag on `solve`)
   - `tests/test_abstraction_emd.py`
   - `tests/test_abstraction_buckets.py`
   - `tests/test_abstraction_integration.py`
   - any other touched files

Do not run the abstraction builder. Audit the *committed* code.

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct (one-line entry under "Looks good" with file:line evidence) or flag under the appropriate severity bucket.

1. **Suit-isomorphism canonicalization correctness.**
   - `_canonical_board_id(board)` sorts board cards in `(rank, suit)` ascending. Verify this in `buckets.py`.
   - Per spec §4 Stage 4 / Decision 7.6: suit-isomorphism is **explicitly NOT applied** at the lookup layer for v1 — the table is keyed by 22100 ordered-card flop classes (canonicalized by sort only, no suit-permutation reduction). Confirm the impl does not silently reduce to 1755 (which would change semantic behavior).
   - `_canonical_hand_key(hole_cards)` canonicalizes by `(rank, suit)` ascending; produces a key in `[0, 1326)`.
   - **Critical seam:** the canonicalization functions are the load-bearing parity surface for PR 6's Rust port. Verify they are pure functions (no closure over module state) and have docstrings documenting the canonical sort order.

2. **EMD math correctness.**
   - `emd_1d(p, q)` implements the 1-D closed form: `mean(|cumsum(p) - cumsum(q)|)`. Verify (spec §4 Stage 2; Decision 7.2).
   - Histograms are L1-normalized before EMD (spec §4 Stage 2 "edge-case behavior").
   - `batch_emd(points, centroids)` is vectorized via `np.cumsum` once per centroid update + broadcast; not a naive double loop. (Performance; if naive loop, flag should-fix.)
   - Edge cases: identical histograms → 0; opposite-extreme deltas → ~1.0; symmetric in arguments; triangle inequality holds.

3. **K-means seeded reproducibility.**
   - `kmeans_emd(..., seed=42)` is deterministic: same seed + same input → bit-identical assignments and centroids.
   - kmeans++ init uses the seeded `np.random.Generator` (not module-level `np.random`). Spec Decision 7.3.
   - Empty-cluster recovery path exists (re-seed empty cluster from farthest point). Spec §8 Agent A deliverable test 9.
   - Convergence rule: max 200 iterations OR <0.1% of points change assignment. Spec §4 Stage 3.

4. **Monte Carlo flop-feature seeded reproducibility.**
   - Per Decision 7.7, flop features default to Monte Carlo (200k iterations) — exact enumeration is too slow.
   - The MC sampler accepts an explicit `rng: np.random.Generator` (or seed); same seed → bit-identical features.
   - The `--seed` flag in `precompute-abstraction` flows through to MC sampling AND to kmeans++ AND any other RNG.
   - Spec §11 Decision 7.7: river + turn = exact enumeration; flop = MC default. Confirm the impl matches.

5. **Bucket-file (`.npz`) roundtrip integrity.**
   - `save_abstraction(tables, path)` followed by `load_abstraction(path)` produces equal arrays (np.array_equal on every per-street array).
   - Per amended §4 Stage 5 (2026-05-21 amendment): `metadata` is serialized as a **single nested dict** via `json.dumps(metadata).encode()` into a one-element bytes_ array inside the `.npz`. NOT separate top-level NumPy arrays per metadata field. Verify the writer matches this and PR 6's Rust loader contract.
   - `schema_version == 1` check on load; loud `ValueError`/`SchemaError` on mismatch (not silent fall-through).
   - The artifact is loadable via `importlib.resources` OR an explicit Path; not via `__file__` arithmetic.

6. **Preflop lookup path.**
   - `lookup_bucket(tables, board, hole, Street.PREFLOP)` returns `-1` per spec §3.5 / §7.12. Tested.
   - `HUNLPoker.infoset_key` preserves lossless preflop format even when `abstraction is not None`. (Spec §6.)

7. **`HUNLConfig.abstraction` field is `Optional[AbstractionRef]` (NOT `Optional[AbstractionTables]`).**
   - Per the 2026-05-21 spec amendment (resolving consistency-review blocker B2): the field is typed as `Optional[AbstractionRef]`, where `AbstractionRef = (source_path: str, version: str)` is a small dataclass declared alongside `AbstractionTables` in `poker_solver/abstraction/buckets.py`.
   - Callers that need the in-memory bucket tables call `load_abstraction(ref.source_path)` themselves.
   - Verify the dataclass is declared, frozen, and the type annotation on `HUNLConfig` matches. Flag if `HUNLConfig.abstraction: Optional[AbstractionTables]` (the old wrong form).

8. **License attribution headers (CRITICAL).**
   - PR 4 ports architectural patterns from Slumbot's `build_kmeans_buckets.cpp` (MIT — attributable). It must **NOT** copy code from `references/code/postflop-solver` (AGPL).
   - For every new file in `poker_solver/abstraction/`: check the module docstring/header for attribution to Slumbot (MIT, with `MIT — pattern adapted, code derived from scratch` or similar) where appropriate.
   - **Zero AGPL contamination allowed.** Grep the new files for any function name, type name, or distinctive idiom matching `postflop-solver/src/`. If found, flag as **must-fix**.
   - Confirm no comments or docstrings reference postflop-solver / TexasSolver as a code source (only as inspiration / read-only reference).

9. **Strategic-equivalence collapse correctness.**
   - The pipeline collapses 1326 combo-specific infosets per board to 169 hand-class representatives (preflop) or per-bucket equivalents (postflop). Verify the within-class spread guard (spec mentions in PR 3.5 §10 context; in PR 4 the equivalent is bucket-id stability across combos in the same hand class within a board).
   - For abstraction smoke tests: `test_abstraction_collapses_strategically_similar_hands` exists and runs. Spec §8 Agent C test 3.

10. **CLI integration.**
    - `precompute-abstraction` subcommand exposes `--output`, `--bucket-counts`, `--feature-bins`, `--seed`, `--max-iter`, `--street`, `--flop-mode {exact,mc}`, `--mc-iterations` per spec §6.
    - The `--street` flag accepts `{flop,turn,river,all}` and builds only the requested street(s) (checkpoint-and-resume per spec §9 risk mitigation).
    - `solve` subcommand's `--abstraction PATH` loads the artifact (via `load_abstraction`) and attaches it to `HUNLConfig`.
    - The 1 GB hard guard rail (spec §7.6) fires when the built artifact exceeds 1 GB: CLI exits with `ValueError` / `RuntimeError` and an actionable message about reducing bucket counts or adding suit-iso. Test for this exists or is documented.

11. **No new third-party dependencies (Decision 7.4).**
    - Compare `pyproject.toml` on `pr-4-card-abstraction` vs `integration`. `[project.dependencies]` must not gain `scipy`, `scikit-learn`, or any other non-stdlib non-numpy entry.
    - `tqdm` is acceptable per Decision 7.4 (small, MIT). Anything else → must-fix.
    - The `[tool.setuptools.package-data]` / `[tool.maturin] include` entries should NOT bundle the `.npz` artifact in the wheel (the artifact is locally built; spec §10 Decision Q6 + spec §12 Q6).

12. **PR 3 regression: lossless behavior preserved.**
    - When `HUNLConfig.abstraction is None`, `HUNLPoker.infoset_key` returns the lossless PR 3 string format unchanged. Spec §3.5 / §6.
    - All PR 3 tests pass unmodified (97 tests in `tests/test_hunl_core.py`).
    - The `test_pr3_tiny_subgame_still_passes_without_abstraction` integration test exists and passes.

13. **Error handling consistency.**
    - `load_abstraction(path)` raises `ValueError` (NOT `KeyError` / `AssertionError`) on schema-version mismatch, missing array, bad path.
    - `lookup_bucket(..., board_not_in_table)` raises `ValueError` or `KeyError` with a clear caller-facing message (spec §8 Agent B test 10).
    - `lookup_bucket(..., board_overlaps_with_hole)` raises `ValueError` (caller bug, want loud failure; spec §8 Agent B test 12).
    - `AssertionError` reserved for internal unreachable invariants only (PR 3 audit precedent).

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/audit_report.md` with this exact structure:

```markdown
# PR 4 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-4-card-abstraction
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_abstraction_*.py — pass/fail counts; full suite delta]

## Must-fix

[Correctness bugs (wrong canonicalization, EMD math errors, non-deterministic MC/kmeans), license violations (AGPL contamination, missing attribution), schema-breakage (metadata not nested), missing required fields, new third-party deps, regressions in PR 3 lossless path. Each item: file:line + what's wrong + recommended fix.]

[If none: "None found." with one-sentence justification.]

## Should-fix

[Code smell, undocumented behavior, awkward APIs, missing assertions on documented invariants, test holes, performance smells (e.g., non-vectorized batch_emd). Each item: file:line + description + fix.]

## Nice-to-fix

[Style, naming, minor DRY, comment additions. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-13 matching the 13 audit focus areas above. Each item: one-paragraph confirmation with file:line evidence and a concrete check performed.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested, or tested only indirectly. Each item: which spec section + what's missing + suggested test name.]

## License compliance

[Explicit statement: every new file in `poker_solver/abstraction/` has its license posture clear; Slumbot's MIT patterns adopted with attribution; ZERO AGPL contamination from postflop-solver / TexasSolver / shark-2.0. Cite specific module docstrings / grep results.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". Followed by a 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** correctness bugs (wrong canonicalization, broken EMD math, non-deterministic seeded paths, schema violations, missing required JSON / `.npz` fields), license bugs (AGPL contamination), any new third-party runtime dep beyond the spec, regressions in PR 3 lossless behavior. Anything in this bucket blocks the PR.
- **should-fix:** undocumented behavior, awkward error types (`AssertionError` where `ValueError` belongs), missing assertions on documented invariants, test holes, performance smells. Does not block PR.
- **nice-to-fix:** style, naming, comments, minor DRY. Pure polish.

When in doubt: if a downstream user could get a **silently wrong abstraction artifact** from the bug, it's must-fix. If the bug only affects developer experience, it's should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers in must-fix / should-fix items.
- If you find behavior the spec is silent on, file under "Spec coverage gaps" and recommend an explicit decision.
- Do not modify any code. Audit only. Your only write is to `docs/pr4_prep/audit_report.md`.
- If you cannot find a file listed in "Inputs to read", note it in the report and continue auditing what you can.

Begin by reading the spec (especially the 2026-05-21 amendments at the top), then the diff, then the new files. Then write the report.
