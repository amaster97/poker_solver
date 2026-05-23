# PR spec consistency review

**Specs reviewed:** PR 3, 3.5, 4, 5, 6, 7, 8, 9, 10, 11 + PLAN.md
**Reviewer:** consistency audit agent
**Date:** 2026-05-21

## Findings (severity: blocker / important / nice-to-resolve)

### Blockers (must resolve before PR N implementation can begin)

**B1. PR 6 §4.4 — Rust `AbstractionTables` shape diverges from PR 4 spec.**
- PR 4 §4 Stage 5 declares the `.npz` artifact contains `flop_assignments`, `flop_board_index`, `flop_hand_lookup`, etc., **plus a `metadata` dict** carrying `schema_version`, `bucket_counts`, `feature_bins`, `seed`, `build_timestamp`, `build_duration_sec`, `lossless_streets`.
- PR 6 §4.4 declares the Rust loader produces an `AbstractionTables` with `bucket_counts: [u16; 3]`, `schema_version: u8`, `feature_bins: u16`, `seed: u64` — i.e., PR 6 expects the metadata fields lifted into typed top-level fields rather than a metadata dict.
- This is a real seam: PR 4 writes `metadata` as a nested key inside the `.npz`; PR 6's loader must either parse that nested dict or PR 4 must write the fields as top-level `.npz` arrays. The spec is inconsistent about which side does the un-nesting.
- **Resolution required before PR 6 implementation begins.** Recommendation: PR 4 stays as-spec (single `metadata` dict, simpler authoring), PR 6 spec updated to parse the metadata dict on load.

**B2. PR 4 §5 declares `lookup_bucket` signature uses `tables: AbstractionTables`; PR 6 §4.4 declares the Rust function takes `tables: &AbstractionTables`; PR 4 §6 says "`HUNLConfig` gains an optional field `abstraction: AbstractionTables | None = None`."**
- However, PR 6 §6.3 says: *"PR 6 adds a `source_path: Path | None = None` field [to `AbstractionTables`] so Rust can re-load via the on-disk artifact."*
- PR 4 does not declare `source_path` on `AbstractionTables`. PR 6 adds it, which contradicts the locked PR 4 dataclass spec. Worse, the field is needed because PyO3 only carries the path (not the table object) across the boundary.
- **Resolution required before PR 6 implementation begins.** Recommendation: PR 4 spec amended to include `source_path: Path | None = None` as part of `AbstractionTables` from the start. Cleanly anticipates the Rust port consumer.

**B3. PR 3 § action encoding declares 14 IDs; PR 6 §4.1 says "replicate PR 3 `action_abstraction.py` integer constants (`ACTION_FOLD = 0`, …, `ACTION_ALL_IN = 13`) as `pub const` in `hunl.rs`. Single source of truth: the Python file."** This is consistent. **However**, PR 9 §5 mentions: *"The 4-cap raise rule (preflop 4-cap, postflop 3-cap) is already implemented in `action_abstraction.py`. PR 9 audit confirms a walk through the 4-bet/5-bet ladder hits the cap correctly."* Confirms PR 3's encoding is the source of truth across all downstream specs.
- **Not a blocker — already consistent.** Listed here for completeness.

**B4. PR 3.5 §6 declares `solve(...)` short-circuit: *"if `isinstance(game, HUNLPoker) and eff_stack_bb <= 15: return pushfold.solve_pushfold(...)`"*. PR 5 §6 declares: *"Add a routing branch in `solve()`: if the game is `HUNLPoker` and its config has `starting_street >= Street.FLOP`, route to `hunl_solver.solve_hunl_postflop`."* PR 9 §5 declares the same routing pattern adds a preflop branch.
- The three dispatch branches must compose correctly. Specifically: if a user calls `solve(HUNLPoker(HUNLConfig(starting_stack=1500, starting_street=Street.PREFLOP)))`, which branch wins?
- PR 3.5's branch is on `isinstance(game, HUNLPoker)` AND `eff_stack_bb <= 15`. PR 5's is on `HUNLPoker` AND `starting_street >= Street.FLOP`. PR 9's is `HUNLPoker` AND `starting_street == Street.PREFLOP`.
- Ordering matters: PR 3.5 must short-circuit BEFORE the postflop/preflop branches, otherwise a `starting_street=PREFLOP, starting_stack=1500` config would skip the chart lookup. PR 9 §6 confirms the right ordering (`if eff_stack_bb <= 15: pushfold; elif > 250: error; else: preflop_solver`), but PR 3.5 §6 doesn't enumerate the postflop case and PR 5 doesn't enumerate the push/fold case.
- **Resolution required before PR 9 implementation begins.** PR 9's dispatch logic should be the authoritative reference; PR 3.5's and PR 5's dispatch text should be reconciled to it.

### Important (resolve before PRs N+1 land but PR N can proceed)

**I1. PR 5 §5 + PR 5 §6 specify the Rust port of `solve_hunl_postflop` lands in PR 6. PR 6 §6.3 and §6.4 modify `poker_solver/hunl.py` to add `_serialize_hunl_config` and add `source_path` to `HUNLConfig.abstraction`.** PR 5 §6 explicitly says: *"Not modified: `poker_solver/hunl.py` — unchanged (PR 4 is the last spec that touches it, adding the `abstraction` field)."*
- PR 6 then modifies `hunl.py` for the Rust integration. This contradicts PR 5's "not modified" claim, but as a sequence (PR 4 → PR 5 → PR 6), each PR's modifications are additive and don't conflict.
- **Not load-bearing**, but the language in PR 5 "PR 4 is the last spec that touches it" is incorrect. PR 6 also touches it. Worth a small spec edit so future readers don't get confused.

**I2. PR 4 §"7.6 Storage size estimate" target is "<100 MB" but acknowledges "if the build artifact exceeds 1 GB, the CLI exits with an error".** PR 11 §6.2 says: *"`.icns` placeholder; …`poker_solver/charts/` (PR 3.5 push/fold charts)"* but **doesn't include the abstraction `.npz` in the bundle.** PR 11 §2.4 says library spots are 50-150 KB compressed each. The abstraction artifact (potentially 100-750 MB) is **not** packaged in the `.dmg`, so users must build it locally post-install via `poker-solver precompute-abstraction`.
- PR 9 §6 says: *"The user must supply the appropriate abstraction artifact path for the tier."* Consistent with not bundling.
- **Not a blocker**, but PR 10 §13 #5 and PR 11 §3-§6 don't mention this user-experience issue: after installing the `.dmg`, the user runs the UI, picks a postflop spot, hits "Solve" → it errors because no abstraction artifact exists. PR 11 should at least surface a first-launch warning. Worth a follow-up spec note.

**I3. Differential-test tolerances across PRs 6, 7, 8 are quoted with subtle differences.**
- PR 6 §7.3: river-only subgame → `1e-3`, flop subgame → `5e-3` (matches PR 7's per-action threshold).
- PR 7 §1 and §11 #3: per-action `5e-3`, per-spot game value `1e-3 × base_pot`.
- PR 8 §7 Layer A: SIMD/scalar parity is **bit-exact** (`to_bits()` equality, ULP ≤ 1 allowance only on FMA).
- PR 8 §7 Layer B: layout parity is `1e-12`.
- PR 8 §7 Layer C: PCS convergence is `5e-3` mean, `2e-2` max.
- PR 8 §7 Layer D: Python end-to-end is `5e-3` "no tolerances weaker than the existing Python ↔ Rust diff test."
- PR 9 §10.4: preflop diff is `1e-4` ("the existing diff tolerance from `tests/test_dcfr_diff.py`").
- The `1e-4` claim in PR 9 references `tests/test_dcfr_diff.py` but PR 6's actual tolerance is `1e-3`. PR 9 doesn't match the PR 6 / PR 7 / PR 8 chain.
- **Important to resolve before PR 9 implementation begins.** The PR 9 spec's `1e-4` is tighter than the PR 6 standard; either PR 9 needs to commit to actually being deterministic-enough to hit 1e-4 (which would be a meaningful new claim, since PR 6 explicitly accepts `1e-3` due to HashMap iteration nondeterminism × float ordering), or PR 9 should adopt the PR 6/7/8 tolerance.

**I4. PR 5 §7.6 documents the `psutil` calibration check at 10% tolerance.** PR 11 §3.3 *"Internal `threading.Lock` around writes."* and §4.5 *"All `get` calls from the UI route through `asyncio.to_thread(library.get, spot_id)`."* These are good but PR 9 §12 *"each subgame is solved sequentially (one at a time) with the same memory budget"* implies the memory probe runs per-subgame. PR 9 doesn't restate the 10% tolerance or whether it expects the same accounting accuracy on the larger preflop tree.
- **Not load-bearing**, but PR 9's profiler usage should explicitly inherit the PR 5 calibration check. Small spec edit.

**I5. PR 9 §3.2 says blueprint pass *"includes 50,000 iterations"* and the convergence target is **blueprint exploitability < 0.5 BB/100**. PR 5 §8 fixture 2 specifies "convergence target: exploitability < 0.1 BB" for a single flop spot at 10k iterations. These two convergence targets are wildly different — PR 9's is 5× looser despite a 5× larger iteration budget.**
- The looseness is explained in PR 9 §7.4 (*"the blueprint is intentionally coarse, and the subgame refinement will tighten the postflop exploitability per-subtree"*), but the user reading PR 9 might miss that the *combined* (blueprint+refinement) exploitability is the actual deliverable target. The PR 9 spec doesn't have a "combined exploitability target."
- **Important — resolve before PR 9 implementation begins.** Define the actual end-to-end exploitability target for the full preflop+refinement solve (e.g., "< 0.5 BB/100 on every reached preflop infoset; < 0.1 BB/100 on every refined postflop subgame; < 1 BB/100 on unrefined long-tail subgames").

**I6. PR 8 §5 declares `HUNLConfig.use_pcs: bool = False` as the opt-in flag. PR 3 §"HUNLConfig" enumerates the fields explicitly and does not include `use_pcs`. PR 9 + PR 11 also don't mention adding it.**
- PR 6 §4.1 lists the Rust mirror of `HUNLConfig` fields and also omits `use_pcs`.
- PR 8 implicitly assumes the field gets added to `HUNLConfig`, but no spec explicitly authorizes the schema extension.
- **Important to resolve before PR 8 implementation begins.** PR 8 spec should explicitly call out the `HUNLConfig` schema extension, and PR 6 should pre-emptively include `use_pcs` in the Rust mirror to avoid a future migration.

**I7. PR 5 §3.4 fixture 2 uses `bet_size_fractions=(0.33, 0.75, 2.00)` (3 sizes); PR 8 §2 spot 3 uses *"3 bet sizes, 100 BB, 50/64 buckets"* and spot 4 uses *"5 bet sizes, 100 BB, 256/128/64 buckets"*. PR 7 §4 spots use bet_sizes like `[0.75, 1.5]`.** The exact bet-fraction sets vary across specs; that's fine (each PR picks its own benchmark spots), but PR 8's "50/64 buckets" notation is ambiguous — is that flop=50, turn=64? It doesn't match any documented bucket tier.
- **Cosmetic issue.** PR 8 spec should clarify which bucket configuration "50/64" maps to (or fix to a known tier like "64/32/16").

**I8. PR 11 §6.2 bundle contents include "`poker_solver/charts/` (PR 3.5 push/fold charts)" but PR 3.5 §5 ships the charts under `poker_solver/charts/pushfold_v1.json`. The PR 11 bundle line says `charts/` (the directory), which is correct.** No inconsistency.

**I9. PR 10 §1 says: *"By the time PR 10 lands, the engine has shipped Kuhn (PR 1), Leduc (PR 2), the HUNL tree (PR 3), push/fold charts (PR 3.5), card abstraction (PR 4), the first HUNL postflop solve (PR 5), Rust port (PR 6), Brown parity (PR 7), SIMD/cache-blocking perf (PR 8), and HUNL preflop (PR 9)."* This locks PR 10 to be the **tenth PR in the sequence** (after PR 9). PR 11 §13 #13 says: *"PR 11 starts when PR 10 lands its NiceGUI scaffold."*** Sequence is consistent.
- **Not a blocker.** Confirmed PR 10 must land before PR 11.

**I10. PR 9 §6 says push/fold at ≤15 BB; the boundary is a "hard cliff."** PR 3.5 §3 says: *"`sb_jam` and `bb_call_vs_jam` charts: 2, 3, 4, ..., 15 (14 entries each)"*. The charts cover **exactly** 2-15 BB. PR 9 boundary handoff at "16 BB → solver" leaves no gap.
- **Consistent.** Confirmed at PR 9 §10.3 test `test_preflop_dispatch_pushfold_at_15bb` (1500 cents = 15 BB → chart) + `test_preflop_dispatch_solver_at_16bb` (1600 cents = 16 BB → solver).

### Nice-to-resolve (consistency cleanup; not load-bearing)

**N1. License attribution language varies slightly across PRs.** PR 6 §3 has a detailed module-attribution template; PR 7 §8 has a slightly different template (less elaborate); PR 8 §10 #10 mentions a `simd.rs` attribution but doesn't show the template. All three say the same thing (cite MIT sources, never copy from AGPL) but the templates aren't bit-identical.
- Cleanup: PR 6's template is the most thorough; consider it the canonical form and have PR 7 / PR 8 / PR 9 refer to it rather than restating.

**N2. PR 10 §13 #5 says: *"By the time PR 10 lands, the solver handles both [preflop and postflop]."*** Confirms PR 9 lands before PR 10. PR 9 §17 success criteria doesn't explicitly call out "PR 10 must inherit the new preflop dispatch." Adding a small note would help PR 10 implementors.

**N3. PR 4 §3.5 says preflop infoset keys stay lossless; PR 5 §7.3 documents both lossless and bucketed key formats; PR 6 §4.1 lists both formats for byte-for-byte parity; PR 11 §2.3 uses the canonicalized JSON for spot ID (not the infoset key). **All consistent.** Minor language drift in how each spec describes the formats — could be unified.**

**N4. PR 9 §3.2 introduces the term "subgame" but PR 5 §3.4 calls them "subgames" and "subtrees" interchangeably. PR 11 §2 says "solved spots." PR 10 §3 says "spots." Terminology is technically correct but inconsistent.**
- Cleanup: standardize on "spot" for the user-facing concept and "subgame" for the algorithmic concept.

**N5. PR 4 §10 says: *"PR 11 packaging may bundle a default `abstraction_v1.npz` in the wheel (small enough at ~100 MB after compression)."*** PR 11 §6.2 does **not** bundle the abstraction artifact. So PR 4's hypothesis ("small enough … may bundle") was rejected by PR 11.
- Cleanup: PR 4 §10 should be updated to say "PR 11 explicitly does NOT bundle the abstraction artifact; users must run `precompute-abstraction` post-install."

**N6. PR 8 §11 #2 commits to "PCS as opt-in for v1." PR 9 §14 #10 also defaults to "full-traverse DCFR." Both default to the same choice; reaffirming consistency. No issue.**

**N7. PR 5 §14 #3 flags an open decision: `HUNLSolveResult` as subclass of `SolveResult` vs tuple. The default is "subclass" but the PR 9 + PR 11 specs assume the subclass form (`PreflopSolveResult` extends `HUNLSolveResult` in PR 9). PR 11 §2.4 uses `SolveResult.average_strategy` access pattern. If the decision flips to "tuple," downstream specs break.**
- Cleanup: PR 5 should lock the decision (not leave it open), since PR 9 and PR 11 already depend on it.

### Aligned + clean (explicit confirmations of focus areas where specs agree)

- **File scopes are non-overlapping (verified):**
  - PR 3: `poker_solver/hunl.py`, `poker_solver/action_abstraction.py`
  - PR 3.5: `poker_solver/pushfold.py`, `poker_solver/charts/pushfold_v1.json`, `scripts/generate_pushfold_charts.py`
  - PR 4: `poker_solver/abstraction/*` (5 files), CLI extension
  - PR 5: `poker_solver/hunl_solver.py`, `poker_solver/profiler/*`
  - PR 6: `crates/cfr_core/src/{hunl, hunl_tree, hunl_eval, abstraction, hunl_solver}.rs`
  - PR 7: `tests/data/river_spots.json`, `poker_solver/parity/noambrown_wrapper.py`, `scripts/build_noambrown.sh`
  - PR 8: `crates/cfr_core/src/{simd, layout, pcs}.rs`, `benches/cfr_bench.rs`
  - PR 9: `poker_solver/{preflop_solver, blueprint, subgame_refiner}.py`, `crates/cfr_core/src/{preflop, blueprint, subgame}.rs`
  - PR 10: `ui/*` (new package outside `poker_solver/`)
  - PR 11: `poker_solver/library.py`, `scripts/build_macos_dmg.sh`, packaging
  - **All files cleanly partitioned; no two PRs claim the same file as primary owner.** Cross-PR file modifications (e.g., PR 4 + PR 5 + PR 9 all modify `hunl.py`) are additive and don't conflict.

- **Action IDs consistent.** PR 3 §"Action encoding" defines 14 IDs (`ACTION_FOLD = 0` through `ACTION_ALL_IN = 13`). PR 4, PR 5, PR 6, PR 7 (history canonicalization), PR 8 (no action-ID work), PR 9 (consumes PR 3's action_abstraction), and PR 10 (color blend formula refers to PR 3 action constants) all consistently reference these 14 IDs. PR 6 §4.1 explicitly mandates byte-parity with Python's PR 3 constants. PR 7 §5 step 5 explicitly maps our action tokens to Brown's via a documented translation table.

- **License attributions clean:**
  - PR 3 explicitly inspects existing repos but doesn't port. ✓
  - PR 4 §3.3 says: *"We adopt the *shape* of [slumbot's] pipeline (feature vectors → dedup → k-means → write assignments) without copying the C++."* ✓
  - PR 4 §3.3 explicitly cites `postflop-solver` as **AGPL — Read-only inspiration; never copy code.** ✓
  - PR 5 §7.8 says: *"What we adopt (architecturally): the principle of 'compute total memory by summing every backing buffer.' What we don't adopt: their compressed-vs-uncompressed distinction… and their bunching-aware accounting… No code is copied."* ✓
  - PR 6 §3 has the full license-aware sourcing strategy. ✓
  - PR 7 §8 explicitly cites Brown's repo as MIT and only invokes the binary, no code copy. ✓
  - PR 8 §10 #10 mentions: *"PR 8 cites the NEON-pattern shape (chunks_exact + remainder) from `references/code/postflop-solver/src/utility.rs` — which is AGPL. Mitigation: `simd.rs`'s module docstring says: 'Pattern inspired by postflop-solver's `chunks_exact` tail handling (AGPL — read-only); implementation derived from scratch per Apple's NEON intrinsics docs. No code copied.'"* ✓
  - PR 9 §16: *"License hygiene. Any code copy-pasted from `noambrown_poker_solver` (MIT, OK with attribution) or `postflop-solver` (AGPL, no copy) must be flagged."* ✓
  - PR 11 §12.7: *"PyInstaller is GPL-with-exception (the exception covers bundled apps); audit confirms the exception applies here."* ✓
  - **No spec claims to "port from postflop-solver" or "port from TexasSolver."** All references to AGPL repos are explicitly inspiration-only.

- **Memory budget claims internally consistent.**
  - PLAN.md §1 table: 100 BB tree-builder = 10-14 GB; 150-200 BB tier-tightened = ~8-12 GB; 200-250 BB tier-tightened = ~5-8 GB.
  - PR 5 §14 #1 default `max_memory_gb=14.0` matches the 14 GB upper bound for 100 BB.
  - PR 9 §3.4 hard ceiling at 14 GB at 100 BB; tier-tightening as PLAN.md table.
  - PR 4 §7.6 abstraction artifact <1 GB (separate from solver memory).
  - PR 11 §12.3 DMG size <200 MB (separate from runtime memory).
  - **All consistent.**

- **Abstraction-tier consistency.** PLAN.md §1 locks 256/128/64 at 15-150 BB; 128/64/32 at 150-200 BB; 64/32/16 at 200-250 BB. PR 4 ships 256/128/64 as default. PR 5 §3.4 uses 256/128/64 default. PR 6 reads whatever PR 4's artifact says. PR 9 §6 has the tier-tightening table matching PLAN.md exactly. **Aligned.**

- **Branch ordering assumptions correct.** No spec says "after PR M lands" where M > N.
  - PR 3 (base) → PR 3.5 (depends on PR 3) → PR 4 (depends on PR 3) → PR 5 (depends on PR 3+4) → PR 6 (depends on PR 5) → PR 7 (depends on PR 5+6) → PR 8 (depends on PR 6) → PR 9 (depends on PR 5+6) → PR 10 (depends on PR 9) → PR 11 (depends on PR 10).
  - PR 8 §6 explicitly notes: *"PR 6 (HUNL postflop port to Rust) has not yet landed at PR 8 spec write-time."* and authorizes a graceful split if PR 6's `hunl_solver.rs` doesn't match. **Correctly anticipated dependency.**

- **Test-tolerance drift partial — see Important I3.** Tolerances mostly aligned (5e-3 per-action, 1e-3 per-spot game value across PR 6/7/8). PR 9's `1e-4` is the outlier.

- **Deferred-decision overlap (see Cross-cutting decisions section).**

## Cross-cutting decisions that need user input

Consolidated from all "open decisions" / "decisions deferred to user" / "user-flagged" sections across the 10 specs:

1. **Abstraction artifact suit-isomorphism at river layer.** Spec'd in PR 4 §7.6 and PR 4 §12 Q1: ship without suit-iso for v1 (river layer ~750 MB uncompressed) vs implement suit-iso in PR 4 (~50 MB, +1-2 days). PR 6 mirrors PR 4's decision. **Default: no suit-iso.**

2. **Equity-feature MC vs exact enumeration on flop.** PR 4 §7.7, §12 Q2: MC with 200K iterations introduces ~0.2% noise; exact enumeration is multi-day. **Default: MC.**

3. **Memory budget hard ceiling.** PR 5 §14 #1: 14 GB vs 16 GB. **Default: 14 GB.** PR 9 §12 inherits this. PR 11 doesn't enforce a budget.

4. **Push/fold handoff at 15 BB.** PR 9 §14 #1: hard cliff vs interpolation band. **Default: hard cliff.** PR 3.5 §6 confirms auto-dispatch at ≤15 BB.

5. **Blueprint postflop menu in PR 9.** PR 9 §14 #2: 1 size (0.75-pot) + all-in, 1-cap (default) vs 2 sizes + 1-cap (richer blueprint, ~3× compute). **Default: 1 size.**

6. **PCS as default vs opt-in in PR 8.** PR 8 §11 #2: opt-in for v1 (default false). **Default: opt-in.**

7. **Diff-test tolerance in PR 6 + PR 7 + PR 8.** Multiple specs cite different tolerances (PR 6 = 1e-3, PR 9 = 1e-4). **Needs single canonical answer for cross-PR consistency.** See Important I3.

8. **Scalar vs vector CFR in PR 6.** PR 6 §11 #1: scalar (default) vs vector (Noam Brown style; +1-2 weeks). **Default: scalar.**

9. **Apple Developer enrollment in PR 11.** PR 11 §13 #1: optional ($99/yr for signed distribution; unsigned fallback works). **Default: optional, fall back to unsigned.**

10. **Reach threshold for subgame refinement in PR 9.** PR 9 §14 #4: 1e-3 (default), 1e-4 (more refinement, ~5× compute), 1e-2 (less refinement, faster). **Default: 1e-3.**

11. **Blueprint iteration count in PR 9.** PR 9 §14 #5: 50,000 default; 10,000 (faster, coarser); 200,000 (slower, PR 5-quality). **Default: 50,000.**

12. **Per-subgame refinement iterations in PR 9.** PR 9 §14 #6: 10,000 default. **Default: 10,000.**

13. **Tiny subgame fixture composition in PR 3.** PR 3 §"Decisions deferred" #4: river-only, AhKc vs QdQh, dry board (default) vs alternatives. **Default: river-only fixed-hand fixture.**

14. **River-spot fixture count in PR 7.** PR 7 §12 #2: 10, 15, or 20 spots. **Default: 15.**

15. **`HUNLSolveResult` shape.** PR 5 §14 #3: subclass of `SolveResult` (default) vs tuple. PR 9 + PR 11 assume subclass form. **Decision should be locked, not open. See Nice-to-resolve N7.**

16. **UI theme + port + format defaults in PR 10.** PR 10 §13 has 11 open decisions; defaults are recommended. **Most can be auto-defaulted.**

17. **JSON config marshalling vs PyO3-struct in PR 6.** PR 6 §11 #2: JSON string default. **Default: JSON.**

18. **Bucket file format in PR 4.** PR 4 §7.5: `.npz` default. **Default: `.npz`.**

19. **Compression level in PR 11.** PR 11 §13 #11: gzip level 6 default. **Default: level 6.**

20. **`HUNLConfig.use_pcs` schema field.** PR 8 introduces; PR 6 needs to anticipate. See Important I6.

## Overall verdict

**Needs-cleanup-first.**

PRs 3.5, 4, 5 are ready to launch in sequence after PR 3 lands (no blockers found).

PR 6 has **two blockers** (B1 + B2) that should be resolved by amending the PR 4 spec to add `source_path` to `AbstractionTables` and clarifying how PR 6's loader handles the `metadata` dict. These are 30-minute spec edits, not code changes.

PR 7 is ready (no blockers found; well-aligned with PR 6).

PR 8 has **Important I6** (PR 8 introduces `use_pcs` to `HUNLConfig` without spec authorization). Should be resolved by amending PR 8 spec to call out the schema extension. PR 6 should pre-emptively add the field to its Rust mirror.

PR 9 has **two blockers** (B4: dispatch ordering needs to be authoritative across PR 3.5/5/9) **and Important I3** (PR 9's `1e-4` diff tolerance is tighter than PR 6's `1e-3` without justification). Should be resolved by reconciling PR 3.5 + PR 5 + PR 9 dispatch text to a single authoritative version (PR 9's is correct), and revisiting PR 9's tolerance claim.

PR 10 is ready (no blockers; PR 9 must land first).

PR 11 is ready (no blockers; depends on PR 10 landing first, which is documented in §13 #13).

**Net:** four spec edits unblock the entire sequence:
1. PR 4 spec: add `source_path: Path | None = None` to `AbstractionTables` (unblocks PR 6).
2. PR 4 spec: clarify `.npz` metadata as a single nested dict (unblocks PR 6).
3. PR 9 spec: reconcile dispatch order with PR 3.5 + PR 5 (PR 9's version is canonical).
4. PR 8 spec: authorize `HUNLConfig.use_pcs` schema extension; PR 6 spec adds the field to its Rust mirror.

Plus 2 important issues (I3 tolerance, I5 PR 9 exploitability target) that should be resolved before PR 9 implementation begins but can land after PR 6/7/8.
