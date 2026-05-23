# PR 4 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-4-card-abstraction
**Commit:** 6565b84 (branched from `integration` at fd0a2c7)
**Diff size:** 11 files changed (5 new under `poker_solver/abstraction/`, 3 modified, 3 new test files) = +3038 / -3 LoC. New `poker_solver/abstraction/*` totals 1872 LoC.

**Test status:** `pytest tests/test_abstraction_*.py` → **35 passed, 1 xfailed** (intentional soft-sanity test, per spec §8 Agent C #3). `pytest tests/test_hunl_core.py` (PR 3 regression) → **19 passed**. `mypy --strict poker_solver/abstraction/` → **clean (0 issues, 5 files)**.

---

## Must-fix

**None found.** No correctness bugs, no AGPL contamination, no schema-breakage, no new third-party runtime deps, no PR 3 regression. Spec amendments (D1 suit-iso, D2 MC@200K, B1 nested metadata, B2 `AbstractionRef`) are all correctly implemented.

---

## Should-fix

1. **`equity_features.py` lacks an explicit Slumbot/MIT attribution header** — `equity_features.py:1–22` cites locked decisions D1/D2 but has no license-posture statement. The file does not derive from Slumbot patterns (it implements the equity-distribution feature from first principles using existing `poker_solver.evaluator.evaluate`), so this is technically correct — but for consistency with the three sibling modules in the package (which all carry "MIT — pattern adapted" lines), a one-line header noting "no third-party code derivation; equity feature is original" would close the audit loop. Fix: add to the module docstring near lines 1–22.

2. **`HUNLPoker.infoset_key` triggers bucketed branch for `Street.SHOWDOWN`** — `hunl.py:326` gates on `state.street >= Street.FLOP`, and the `Street` IntEnum has `SHOWDOWN = 4` which satisfies `>= FLOP`. In practice the solver never calls `infoset_key` at SHOWDOWN (`solver.py:158, 240` guard with `is_terminal`), so this is a latent issue, not a live bug. Fix: tighten the predicate to `Street.FLOP <= state.street <= Street.RIVER` (or equivalently `state.street in (FLOP, TURN, RIVER)`). The `lookup_bucket` callee already defensively raises `ValueError` for SHOWDOWN (`buckets.py:210`), so the underlying safety net exists — the predicate just shouldn't take that path.

3. **`lookup_bucket` raises `ValueError` on uncovered canonical board key with message "build-side coverage bug"** — `buckets.py:233, 239, 245`. This is correct error type (per spec §8 Agent B test 10) but the message is developer-facing and would surface in production if someone solves on a board the abstraction's truncation skipped. Production builds enumerate all canonical boards so this is unreachable; the smoke-test autosize path (lines 452–455) skips coverage. The error message could mention the user-facing remedy ("rebuild abstraction with full enumeration; see `precompute-abstraction --max-boards` or remove the cap"). Fix: clearer caller guidance.

4. **`save_abstraction` is not bit-byte-deterministic across runs because `metadata['build_timestamp']` is embedded** — `precompute.py:551`. Two builds with the same seed produce identical assignments but the `.npz` differs by ~1 byte from the timestamp's seconds field. The spec is silent on byte-deterministic disk output; the existing tests verify array equality and metadata-modulo-timestamp equality (`test_build_abstraction_seed_reproducibility` at `tests/test_abstraction_integration.py:200`). If byte-deterministic disk artifacts are desired downstream (e.g., for content-addressable caching), the timestamp should be moved out of the seeded path or exposed as `--build-timestamp` override. Fix: documented limitation or env-overridable.

5. **`_kmeans_plusplus_init` empty-cluster fallback at line 188–196 (`buckets.py emd_clustering.py:184–196`) sets `chosen_idx[c] = chosen_idx[0]` if every point is selected** — duplicates an existing centroid index. The fallback could instead use the unselected-set rng draw at line 196. The current path is unreachable in practice (every point being selected means `n == c < K`, but the `n < K` branch at line 167 already handled that case). Fix: replace `chosen_idx[c] = chosen_idx[0]` with `# unreachable` assert.

6. **`compute_river_features` accepts a `seed` arg that the docstring says is "unused on river"** (`equity_features.py:329, 338`) but the implementation still constructs an rng tree (`_compute_features_for_street` calls `parent_rng = np.random.default_rng(seed)` then spawns child rngs per row). This is wasted work; on the river the rng is never drawn. Fix: short-circuit the spawn loop on river (or document the cost as negligible).

7. **`build_abstraction`'s autosize trigger threshold (`mc_iterations < 5_000`) is implicit magic** — `precompute.py:452–455`. The threshold is a smoke-test heuristic that has worked in tests but isn't a stable contract. A user who legitimately wants a real-but-fast build at `mc_iterations=4_000` would unexpectedly hit the 8-board cap. Fix: surface `max_boards_per_street=None` as a sentinel for "use the autosize heuristic" and `max_boards_per_street=-1` as "no cap" — or simply require the caller to be explicit.

---

## Nice-to-fix

1. **`buckets.py:151–186` `_canonicalize` and `_apply_suit_perm_to_hand` are not named per spec §5 (`_canonical_board_id` and `_canonical_hand_key` were the spec names)**. Functional equivalence holds — the canonical key is a string instead of an int — and the docstrings document the format. The mismatch is purely a naming-convention nit. Fix: rename, or just note in module docstring.

2. **`emd_clustering.py:265` dtype boundary comment "uint8 fits K up to 256" is slightly imprecise** — uint8 fits assignments in [0, 256) which max at 255 → K can be exactly 256 (since assignments are < K = 256). The comment "K up to 256" is correct given the strict-less-than convention but readers might misread. Fix: clarify "K <= 256 (assignments in [0, 256))".

3. **`canonicalize_for_suit_iso` returns a `(str, int)` tuple but the spec calls for a packed-integer hash** — `equity_features.py:443–510`. The string approach is fine (and clearly documented) but a packed int would be faster to hash and would more closely match PR 6's PyO3 boundary expectations. Fix: deferred to PR 6.

4. **`hunl.py:111` `abstraction` field uses `field(default=None, compare=False, hash=False)` but the wrapping `@dataclass(frozen=True, eq=True)` would benefit from a comment that `compare=False` is required because `AbstractionRef.source_path` is a runtime-attribution string** (build-config equality should not depend on absolute path). Fix: extend the existing comment block.

5. **`emd_clustering.py:181–183` `dists * dists` could be `np.square(dists)` for clarity** — purely cosmetic.

6. **`precompute.py:285` "computing equity features (N hands)..." line uses bare `print`** — spec D7.4 prefers print over tqdm, but a `_progress(msg)` helper that consolidates the formatting would be cleaner.

---

## Looks good (explicit confirmation of audit focus areas)

1. **Suit-isomorphism canonicalization correctness.** `equity_features.py:443–510` `canonicalize_for_suit_iso` correctly enumerates all 24 suit permutations and picks the lexicographically-minimal `(rank, perm[suit])` sorted-tuple representation. Verified empirically (`As Ks Qs` and `Ah Kh Qh` canonicalize to `r12s0_r13s0_r14s0`); functions are pure (no module-state closure), well-docstrings'd, and explicit about D1 inclusion. The hand permutation is applied via `_apply_suit_perm_to_hand` at `buckets.py:170–186` using the same `_SUIT_PERMUTATIONS` table that build-time used, ensuring round-trip identity.

2. **EMD math correctness.** `emd_clustering.py:29–53` `emd_1d` implements `mean(|cumsum(p) - cumsum(q)|)` correctly. Verified: `emd_1d(p, p) == 0`, symmetric, triangle inequality (`test_emd_triangle_inequality`), and the opposite-extremes test correctly expects `(H-1)/H` rather than 1.0 (the `mean` normalization). Edge case for L1-normalization: histograms are guaranteed L1-normalized at construction (`equity_features.py:247–252`); `_l1_normalize_rows` at `emd_clustering.py:121–137` re-normalizes centroids. `batch_emd` (`emd_clustering.py:56–99`) is vectorized via single-pass `cumsum` + broadcast + chunked to keep the (N, K, H) tensor under 1 GB.

3. **K-means seeded reproducibility.** `emd_clustering.py:219–337` `kmeans_emd` accepts `seed=42` default. All randomness flows through `rng = np.random.default_rng(seed)` (`emd_clustering.py:267`) and into `_kmeans_plusplus_init` only — no module-level `np.random` reads. Empty-cluster recovery at `emd_clustering.py:296–307` re-seeds from the farthest point (deterministic; no fresh randomness). Convergence at `emd_clustering.py:330–331` enforces `it >= 1 AND changed_frac < change_tolerance`. Test `test_kmeans_reproducible_with_seed` (PASS) confirms.

4. **Monte Carlo flop-feature seeded reproducibility.** `equity_features.py:164–252` `equity_distribution` accepts `rng: np.random.Generator | None`. `_flop_runout_iter_mc` at lines 136–161 draws exclusively from `rng.integers`. `_compute_features_for_street` (lines 255–311) constructs `parent_rng = np.random.default_rng(seed)` then spawns deterministic per-row child rngs via `rng.spawn(1)` — this provides row-stable bit-identical features regardless of iteration order. Test `test_build_abstraction_seed_reproducibility` (PASS) confirms. Default mc_iterations=200_000 per D2.

5. **Bucket-file (`.npz`) roundtrip integrity.** `buckets.py:262–315` `save_abstraction` uses `np.savez_compressed` with explicit kwargs (deterministic key order). `metadata` is serialized via `json.dumps(meta, sort_keys=True, separators=(',', ':')).encode('utf-8')` into a single `uint8` bytes-array (per B1 amendment). `load_abstraction` (lines 322–388) checks `schema_version == 1` and raises `ValueError` ("artifact schema v{schema}; loader expects schema v{SCHEMA_VERSION}; rebuild or upgrade") on mismatch. Test `test_save_load_schema_version_check` corrupts the field and confirms (PASS).

6. **Preflop lookup path.** `buckets.py:208–209` `lookup_bucket(..., Street.PREFLOP)` returns `-1` short-circuit. `hunl.py:326` `state.street >= Street.FLOP` predicate keeps preflop on the lossless path. Test `test_lookup_bucket_returns_minus_one_for_preflop` (PASS).

7. **`HUNLConfig.abstraction` field is `Optional[AbstractionRef]` (NOT `Optional[AbstractionTables]`).** `hunl.py:111` declares `abstraction: AbstractionRef | None = field(default=None, compare=False, hash=False)` with `AbstractionRef` imported under `TYPE_CHECKING` to break the import cycle (`hunl.py:43–47`). Verified at runtime: `dataclasses.fields(HUNLConfig)` shows `type='AbstractionRef | None'`. `AbstractionRef` is declared frozen at `buckets.py:84–95`.

8. **License attribution headers.** All three abstraction modules that derive architectural patterns from Slumbot carry an MIT/Slumbot attribution: `emd_clustering.py:1–16` ("Pattern from references/code/slumbot2019/src/kmeans.cpp::SeedPlusPlus, MIT; no code copied"), `buckets.py:21–22` and `precompute.py:15–16` ("Pattern inspired (architecturally) by slumbot2019's build_kmeans_buckets.cpp (MIT)"). **Zero AGPL contamination:** `grep -rn "postflop-solver|postflop_solver|TexasSolver|AGPL|wasm_postflop|holdem-solver" poker_solver/abstraction/` returns no hits in code; the only file mentioning postflop-solver is `docs/pr4_prep/postflop_solver_emd_patterns.md` (the read-only study doc, properly labeled "NO code is copied verbatim"). The doc itself confirms postflop-solver does not implement EMD/abstraction, so there's nothing to mis-port. (See "should-fix #1" for `equity_features.py` attribution header consistency.)

9. **Strategic-equivalence collapse correctness.** `canonicalize_for_suit_iso` correctly collapses suit-isomorphic boards (verified). The `test_abstraction_collapses_strategically_similar_hands` test (`test_abstraction_integration.py:121–144`) exists, is marked `xfail` per spec ("soft sanity check"), and demonstrates intent. The within-board hand permutation under the board's chosen suit-perm guarantees bucket-id stability across suit-equivalent (board, hand) combos.

10. **CLI integration.** `cli.py:111–158` `_cmd_precompute_abstraction` exposes `--output`, `--bucket-counts`, `--feature-bins`, `--seed`, `--max-iter`, `--street {flop,turn,river,all}`, `--flop-mode {exact,mc}`, `--mc-iterations`, plus an additional `--max-boards` (tests/smoke knob, properly defaulted to `None`). `solve --abstraction PATH` (lines 257–264) loads the artifact via `load_abstraction(path)` and attaches an `AbstractionRef(source_path=str(path.resolve()), version=...)` to `HUNLConfig`. The 1 GB guard rail fires at `precompute.py:534–539` with `ValueError("artifact would be ~X GB, exceeds size_guard_gb={size_guard_gb}; consider reducing bucket_counts or skipping a street")`. CLI smoke test `test_cli_precompute_abstraction_smoke` and `test_cli_solve_with_abstraction_loads_file` PASS.

11. **No new third-party dependencies (Decision 7.4).** `pyproject.toml` `[project.dependencies]` on `pr-4-card-abstraction` shows `numpy>=1.24` only (vs `integration` at same — no new deps in the PR 4 commit itself). `grep "scipy|sklearn|scikit|tqdm" poker_solver/abstraction/` shows only mentions inside docstrings ("Pure NumPy, no scipy / sklearn / scikit-learn"). Zero imports of those packages. `[tool.maturin] include` is unchanged (`charts/*.json` only) — no `.npz` bundled. (Note: pyproject.toml on the current working tree has gained `psutil>=5.9`, but this was a separate post-PR-4 amendment per system reminder, not part of commit 6565b84 — confirmed via `git show 6565b84:pyproject.toml`.)

12. **PR 3 regression: lossless behavior preserved.** `hunl.py:347–355` lossless branch is verbatim PR 3 format. Test `test_pr3_tiny_subgame_still_passes_without_abstraction` PASSES with `cfg.abstraction is None` assertion + lossless-key format check. `pytest tests/test_hunl_core.py` → 19 passed (unmodified PR 3 suite).

13. **Error handling consistency.** `load_abstraction` raises `ValueError` on schema mismatch (`buckets.py:355–359`), missing array (`buckets.py:347–350`), malformed metadata (`buckets.py:352–353, 363, 372`). `lookup_bucket` raises `ValueError` on board+hand conflict (`buckets.py:144–148`), wrong board size for street (`buckets.py:135–139`), uncovered canonical key (`buckets.py:232–246`), SHOWDOWN street (`buckets.py:211`). No `AssertionError` reserved for callable invariants. Tests `test_lookup_bucket_raises_on_blocker` and `test_lookup_bucket_raises_on_wrong_board_size` PASS.

---

## Spec coverage gaps (missing tests)

1. **No test for the 1 GB size-guard fire path.** Spec §7.6 + §10 Risk: "if the build artifact exceeds 1 GB, the CLI exits with an error." `precompute.py:534–539` implements the check via `size_bytes / 1e9 > size_guard_gb`, but no test exercises the failure path. Suggested test: `test_build_abstraction_fires_size_guard_at_1gb` — construct a fake oversized table or set `size_guard_gb=0.0001` and assert `ValueError` with "exceeds" in the message.

2. **No test for `--flop-mode exact` path on the CLI.** Spec §7.7 Decision 7.7 makes `mc` the default and exposes `--flop-mode exact` as an override. The integration tests use `flop_mode="mc"` exclusively. Suggested test: `test_cli_precompute_abstraction_flop_mode_exact` — call CLI with `--flop-mode exact --street flop --max-boards 2 --feature-bins 5` (keep it bounded), assert exit 0 and a sane artifact.

3. **No test confirming `infoset_key` returns the bucketed form ONLY at postflop (and lossless at preflop) within the same solve.** Spec §3.5 / §6 are clear that preflop is always lossless even with an abstraction set. The existing tests pin a river-only subgame which is uniformly postflop. Suggested test: `test_infoset_key_lossless_at_preflop_when_abstraction_set` — instantiate a `HUNLConfig(..., starting_street=Street.PREFLOP, abstraction=ref)`, walk to a preflop infoset, assert the key matches the lossless format.

4. **No test on byte-bit roundtrip when `AbstractionRef.version` does NOT match `metadata['version']`.** `buckets.py:107–112` correctly raises `ValueError` on the mismatch via `resolve_abstraction_ref`. Suggested test: `test_resolve_abstraction_ref_version_mismatch_raises` — build at version="A", construct `AbstractionRef(source_path=path, version="B")`, expect `ValueError`. (The LRU cache makes this subtle to test cleanly; spec coverage gap.)

5. **No test exercising the `required_boards` / `required_hands` autosize-truncation override surface.** `precompute.py:114–143` adds these knobs to force-include test fixture boards/hands; the integration tests rely on them (`_build_tiny_river_only`) but no isolated test verifies the contract that required entries are always present in the output regardless of `max_boards_per_street`. Suggested test: `test_build_abstraction_required_boards_always_present` — pass a specific `required_boards=[X]` with `max_boards_per_street=1`, assert `X` is in the output's `board_index`.

6. **No test for the `_kmeans_plusplus_init` "all points coincide" degenerate path.** `emd_clustering.py:186–196` has a fallback when `sq_dists.sum() <= 0` (all remaining points coincide with selected centroids). Suggested test: `test_kmeans_plusplus_init_handles_degenerate_features` — pass `features = np.tile(p, (10, 1))` (10 copies of same histogram) with K=4, assert no crash and 4 centroids returned.

---

## License compliance

**ZERO AGPL contamination confirmed.** `grep -rn "postflop-solver|postflop_solver|TexasSolver|AGPL|wasm_postflop|holdem-solver" poker_solver/abstraction/` yields no hits in code; the only mentions in the repo are in `docs/pr4_prep/postflop_solver_emd_patterns.md` (a read-only study doc that explicitly declares "NO code is copied verbatim" at line 4), and that doc confirms `postflop-solver` does not implement EMD/abstraction (line 16: *"The solver does not perform any abstraction."*), so there is no pattern to mis-port.

**Slumbot (MIT) attribution properly cited:**
- `emd_clustering.py:11` — "Architectural pattern from `references/code/slumbot2019/src/kmeans.cpp::SeedPlusPlus`, MIT; no code copied)"
- `emd_clustering.py:153–154` — second attribution inside `_kmeans_plusplus_init` docstring
- `buckets.py:21–22` — "Pattern inspired (architecturally) by slumbot2019's bucket-write pipeline (MIT). Reference: references/code/slumbot2019/src/build_kmeans_buckets.cpp"
- `precompute.py:15–16` — same MIT attribution for the orchestrator pipeline

`equity_features.py` lacks an explicit attribution line, but the file does not derive from Slumbot patterns (it implements the equity-distribution feature using `poker_solver.evaluator.evaluate`, which is original code). Flagged as should-fix #1 for consistency, not a license violation.

---

## Overall verdict

**READY for commit.** No must-fix items. The implementation is correct on all 13 audit focus areas; suit-iso (D1), MC-200K (D2), `AbstractionRef`-on-HUNLConfig (B2 amendment), and nested-metadata-JSON-in-.npz (B1 amendment) are all faithfully implemented and tested. PR 3 lossless regression suite passes unchanged. License posture is clean (Slumbot MIT cited, AGPL absent). The 7 should-fix items are quality-of-life polish (attribution header consistency, predicate tightening for SHOWDOWN, error-message clarity, byte-determinism documentation, magic-threshold disambiguation) — none gate the PR. The 6 spec coverage gaps are testing-completeness suggestions; the corresponding code paths are correct, just under-tested. Recommended next: address the 4 highest-priority should-fix items (#1 attribution header, #2 SHOWDOWN predicate, #5 dead-code branch in kmeans++, #7 autosize threshold doc) before PR 5 lands, in a small follow-up commit.
