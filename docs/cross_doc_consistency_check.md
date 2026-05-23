# Cross-doc consistency check — PR prep specs

**Date:** 2026-05-22
**Scope:** `docs/prN_prep/prN_spec.md` for N ∈ {3, 3.5, 4, 5, 6, 7, 8, 9, 10, 10a, 10b, 11, 12} + `PLAN.md` + `docs/autonomous_log.md`
**Severity summary:** **None material.** A handful of minor stylistic / phrasing inconsistencies, but every locked decision is consistent across specs. The recent `spec_consistency_review` and the `autonomous_log.md` S-level resolutions appear to have done their job.

---

## Check 1 — Locked decisions consistency

### 1.1 DCFR hyperparameters (α=1.5, β=0, γ=2.0)

| Spec | Cites α=1.5, β=0, γ=2.0 | Notes |
|---|---|---|
| PLAN.md §1 | ✅ explicit | Source of truth |
| PR 3 | n/a | Tree builder; no DCFR knobs |
| PR 3.5 | implicit (uses existing DCFR) | OK |
| PR 4 | n/a | Abstraction only |
| PR 5 §11 #7 | ✅ explicit | "Hyperparameters unchanged" |
| PR 6 §1 | ✅ explicit | "DCFR α=1.5, β=0, γ=2.0" |
| PR 7 §2 + §1 | ✅ explicit | Cites Brown's `cpp/src/trainer.cpp:353-361` defaults |
| PR 8 §1 | ✅ explicit | "non-PCS path preserved bit-for-bit" |
| PR 8 §5 | ⚠️ deviation noted | PCS path switches **β=0 → β=0.5** for sampling-variance reasons; this is a documented intentional deviation, not a contradiction |
| PR 9 §2 | ✅ explicit | "same hyperparameters (α=1.5, β=0, γ=2.0)" |
| PR 12 §2 / §3.2 | ⚠️ deviation noted | 3-handed uses **LCFR (DCFR_{1,1,1})** for early iter, then plain CFR — explicitly Pluribus-derived; not a 2p0s contradiction |

**Result:** consistent. All 2p0s DCFR-using PRs cite the paper defaults; deviations (PR 8 PCS, PR 12 multiplayer) are *justified, documented, and labelled* as such.

### 1.2 Action menu (33 / 75 / 100 / 150 / 200 / AI) + raise caps (preflop 4 / postflop 3)

| Spec | Action menu | Caps |
|---|---|---|
| PLAN.md §1 | ✅ 33/75/100/150/200/AI | ✅ PF 4 / Post 3 |
| PR 3 §"Action encoding" + locked decision | ✅ matches | ✅ matches |
| PR 3.5 §3 | n/a (jam/fold only) | n/a |
| PR 4 | n/a | n/a |
| PR 5 §3.4 / fixture 2 | ⚠️ uses **restricted subset** `(33, 75, 200)` for Fixture 2 | Documented as test-fixture choice, not a menu change |
| PR 6 §4.1.5 | ✅ matches via port | ✅ matches |
| PR 7 §4 | ✅ uses subset per-spot (e.g. `[0.75, 1.5]`) | `max_raises: 3` postflop |
| PR 8 §2 spot 4 | ✅ "5 bet sizes" + AI = full menu | n/a explicit but tree-conformant |
| PR 9 §7.1 | ✅ blueprint uses **coarsened** `(0.75,) + AI, 1-cap`; refinement uses full menu | Documented coarsening for blueprint |
| PR 9 §7.2 | ✅ preflop menu full + 4-cap | matches |
| PR 12 §2 | ✅ "same as PR 3" | matches |

**Result:** consistent. Per-spec subset choices (PR 5 Fixture 2, PR 7 per-spot, PR 9 blueprint) are explicit fixture/blueprint coarsening, not contradictions of the locked menu.

### 1.3 Card abstraction (256 flop / 128 turn / 64 river default)

| Spec | Tiers cited | Match? |
|---|---|---|
| PLAN.md §1 stack-depth table | 256/128/64 default; 128/64/32 at 150-200 BB; 64/32/16 at 200-250 BB | source of truth |
| PR 3 | defers to PR 4 | n/a |
| PR 4 §1 / §3 | ✅ "256 flop / 128 turn / 64 river per side" | matches |
| PR 5 §3.4 | ✅ "PR 4's 256/128/64 abstraction" | matches |
| PR 6 §4.4 | reads PR 4 artifact; no tier embedded | matches |
| PR 8 §2 spot 3 | ✅ "**64/32/16 buckets** (tier-2 from PLAN.md §1)" | Recently fixed per `autonomous_log.md` I7 |
| PR 8 §2 spot 4 | ✅ "256/128/64 buckets" | matches |
| PR 9 §6 table | ✅ matches PLAN.md tier table | tier rows by stack range |
| PR 12 §5.1 | ✅ "default 3p: **128/64/32**" — one tier tighter than HU; explicit | acceptable variant for 3-handed |

**Result:** consistent. PR 8's previous "50/64" shorthand was caught and fixed (I7 in `autonomous_log.md`); current text is canonical.

### 1.4 Push/fold range (2-15 BB precomputed)

| Spec | Boundary | Match? |
|---|---|---|
| PLAN.md §1 stack-depth table | 2-15 BB | source of truth |
| PR 3.5 §3 | ✅ "2, 3, ..., 15 (14 entries)" | matches |
| PR 9 §6 canonical dispatch | ✅ "≤ 15 BB → chart" (hard cliff) | matches |
| PR 5 §6 | ✅ cross-refs PR 9 §6 | matches |
| PR 6 §6.1 | ✅ cross-refs PR 9 §6 | matches |

**Result:** consistent. Dispatch composition has been canonicalized through PR 9 §6 (per `autonomous_log.md` B4 resolution); all downstream specs reference it correctly.

---

## Check 2 — Interface contracts

### 2.1 `HUNLConfig` schema evolution

- PR 3: defines `HUNLConfig` with `bet_size_fractions`, `preflop_raise_cap=4`, `postflop_raise_cap=3`, `force_allin_threshold=1`, `min_bet_bb=1`, `rake_rate=0.0`, `rake_cap=0`, `ante=0`, etc.
- PR 4 §6: adds `abstraction: Optional[AbstractionRef] = None` (NOT `Optional[AbstractionTables]`). Resolution of B2.
- PR 6 §4.1: pre-emptively mirrors `use_pcs: bool = False` in Rust `HUNLConfig`.
- PR 8 §6: explicitly authorizes the `HUNLConfig.use_pcs: bool = False` field extension on Python side.
- PR 9 §5: adds nothing new to `HUNLConfig`; preflop solver reads existing fields.
- PR 12 §4.2: adds `num_players: int = 2`, generalizes `starting_stacks`/`initial_contributions` to tuples. Keeps class name `HUNLConfig` for code stability.

**Result:** consistent. The schema additions across PR 4 / PR 6 / PR 8 / PR 12 are additive with sensible defaults; PR 6 + PR 8 land in either order without migration (per I6 resolution in `autonomous_log.md`).

### 2.2 `AbstractionRef` / `AbstractionTables`

- PR 4 §6: declares `AbstractionRef = (source_path: str, version: str)`; `HUNLConfig.abstraction: Optional[AbstractionRef]`.
- PR 4 §4 Stage 5: `.npz` writer serializes `metadata` as a single nested JSON-encoded dict; string-keyed dict-of-dict indices for board/hand lookup.
- PR 6 §4.4: Rust loader parses the nested JSON metadata dict; canonical board/hand IDs are **strings** (not `u32`). Header note explicitly updated 2026-05-22 per launch-readiness v2.
- PR 6 §6.3: `resolve_abstraction_ref` is the canonical entry point (LRU-cached + version-checked); both Python and Rust sides honor it.

**Result:** consistent. The B1 + B2 + launch-readiness-v2 updates (`autonomous_log.md`) align PR 4 ↔ PR 6 cleanly.

### 2.3 `MemoryReport` shape

- PR 5 §7.2: defines `MemoryReport` with `per_street`, `preflop_lossless_entry`, `abstraction_table_bytes`, `solver_arrays_total_bytes`, `rss_observed_bytes`, `rss_baseline_bytes`, `river_ratio`, `rss_calibration_error`.
- PR 5 §7.6: `psutil` calibration check at 10% tolerance.
- PR 9 §12: explicitly inherits PR 5's 10% `psutil` RSS calibration (per I4 resolution).
- PR 10a §7.3: lists exact `MemoryReport` fields the UI reads — matches PR 5.
- PR 10b §3: adds `on_progress: Callable[[int, float, MemoryReport], None]` kwarg to `solve_hunl_postflop`. Single one-line engine-side change.

**Result:** consistent. `MemoryReport` shape is stable across PRs 5/9/10a/10b.

### 2.4 `HUNLSolveResult` / `PreflopSolveResult` / `MultiwaySolveResult`

- PR 5 §14 #3: locked to subclass form (`HUNLSolveResult(SolveResult)` adds `memory_report`). Resolved per N7 in `autonomous_log.md`.
- PR 9 §4: `PreflopSolveResult` extends `HUNLSolveResult`.
- PR 11 §2.4: uses `SolveResult.average_strategy` access pattern (parent class).
- PR 12 §6.1: `MultiwaySolveResult` extends/wraps `SolveResult`.

**Result:** consistent. Subclass chain holds.

---

## Check 3 — File path references

Spot-checked spec cross-references for stale paths:

| Reference | Path | Exists? |
|---|---|---|
| PR 3 spec cited in PR 4 | `docs/pr3_prep/pr3_spec.md` | ✅ |
| PR 3.5 spec | `docs/pr3_5_prep/pr3_5_spec.md` | ✅ (post-rename) |
| PR 4 / PR 5 / ... / PR 12 | `docs/prN_prep/prN_spec.md` | ✅ all present |
| PR 10 split | `docs/pr10_prep/pr10a_spec.md`, `pr10b_spec.md`, original `pr10_spec.md` | ✅ all present |
| PR 9 references PR 3.5 chart | `poker_solver/charts/pushfold_v1.json` | ✅ committed |
| Multiple specs reference | `references/code/noambrown_poker_solver/...` | ✅ vendored |

**Result:** no stale path references found. The `pr3_5_prep` directory uses underscore-not-dot per the rename convention.

---

## Check 4 — License audit (per-spec citations)

| Repo | License (per PLAN.md §7) | Cited in spec |
|---|---|---|
| `noambrown_poker_solver` | MIT | PR 6 §3 ✅ MIT; PR 7 §2 ✅ MIT cited from LICENSE; PR 8 §3 ✅ MIT vector_eval port |
| `slumbot2019` | MIT | PR 4 §3.3 ✅ MIT; PR 6 §3 ✅ MIT |
| `open_spiel` | Apache 2.0 | PR 6 §3 ✅ Apache 2.0 |
| `postflop-solver` | AGPL v3 | PR 4 §3.3 ✅ AGPL/read-only; PR 5 §7.8 ✅ AGPL/read-only; PR 6 §3 ✅ AGPL/read-only; PR 8 §3 ✅ AGPL/read-only |
| `TexasSolver` | AGPL v3 | PR 6 §3 ✅ AGPL; PR 12 §15 ✅ AGPL/no-copy |
| `shark-2.0` | Unlicensed (all-rights-reserved) | PR 6 §3 ✅ unlicensed/no-study |

**Result:** consistent. Every spec that references an external repo cites the correct license with the correct copy-policy (MIT/Apache 2.0 → portable with attribution; AGPL → read-only inspiration; unlicensed → avoid).

---

## Check 5 — Diff-test tolerances (PR 6/7/8/9 cluster)

| Spec | Per-action tolerance | Per-spot game-value tolerance |
|---|---|---|
| PR 6 §7.1 | **5e-3** (river-only fixture; tighter 1e-3 declared but actual fixture uses 5e-3 per §7.3) | n/a in §7.1 but §7.3 implies pot-relative |
| PR 6 §7.3 rationale | Locks 5e-3 (river) / 5e-3 (flop) | Per-spot via game-value comparison |
| PR 7 §1 | **5e-3** per-action | **1e-3 × base_pot** |
| PR 7 §11.3 | reaffirms 5e-3 + 1e-3 × pot | matches |
| PR 8 §7 Layer C (PCS) | **5e-3** mean per-action; 2e-2 max | n/a (Leduc) |
| PR 8 §7 Layer D | **5e-3** end-to-end | n/a |
| PR 9 §10.4 | **5e-3** per-action + **1e-3 × base_pot** per-spot (reconciled from earlier 1e-4 per I3) | matches |

**Result:** consistent. The PR 6/7/8/9 cluster all use `5e-3` per-action + `1e-3 × base_pot` per-spot game-value, with PR 9's earlier `1e-4` outlier explicitly reconciled per I3 in `autonomous_log.md`.

PR 6 §7.1 nominal "1e-3" for the river-only test is a documented *tighter test* on a single fixture (smaller chance branching), not a separate tolerance band — the broader contract still cluster-matches at 5e-3. This is a minor stylistic wrinkle but not a contradiction.

---

## Findings — minor only (no material issues)

1. **PR 6 §7.1 vs PR 6 §7.3 — river-only tolerance phrasing.** §7.1 says "Test 1 ... within `1e-3`" while §7.3 says "Spec uses **1e-3** for the river-only fixture (tighter), **5e-3** for the flop fixture (looser)." Both consistent internally but the §7 cluster summary in `autonomous_log.md` characterizes it as "5e-3 per-action + 1e-3 × pot" — slight phrasing mismatch (1e-3 per-action river-only test ≠ 1e-3 × pot game value tolerance). **Severity: minor / phrasing only.** The actual test contracts are well-defined.

2. **PR 5 §3.4 Fixture 2 menu `(0.33, 0.75, 2.00)`** is a 3-size subset of the full 6-size locked menu. Documented as a fixture choice for memory profiling. **Severity: none — explicit, intentional, scoped to one test fixture.**

3. **PR 12 `num_players` default.** Locked to `2` for backward compatibility; PR 12 ships behind a flag. PLAN.md §1 lists 3-handed as "Features beyond v1" (post-v1). **Severity: none — explicit and self-consistent.**

4. **PR 9 §10.4 risk-row formerly cited `1e-4` (now `5e-3 / 1e-3 × base_pot`).** Resolution captured in `autonomous_log.md` I3 + header note in PR 9 spec. **Severity: none — already fixed.**

5. **PR 3.5 §4 SC landmark.** Originally stated "100% jam at d=2"; amended to "≥ 80% combo-weighted" + explicit note that 100% is the S-C heuristic, not HU Nash. Captured in `autonomous_log.md` S10. **Severity: none — already fixed and retro-documented.**

---

## Conclusion

**Total inconsistencies found: 0 material; ~5 minor (all already either resolved or explicitly documented as intentional variants).**

The `docs/spec_consistency_review.md` pass plus the `autonomous_log.md` S/B/I-level resolutions appear to have caught every cross-spec contradiction. The locked decisions (DCFR hyperparameters, action menu, raise caps, card abstraction tiers, push/fold range, diff-test tolerance cluster, license audit) are consistent across all 13 spec files reviewed. Interface contracts (`HUNLConfig`, `AbstractionRef`, `MemoryReport`, `HUNLSolveResult` subclass chain) compose cleanly across PRs.

The prep is in solid shape for the orchestrator to launch implementation against. No spec edits required prior to the next implementation wave.

---

**Files reviewed:**
- `/Users/ashen/Desktop/poker_solver/docs/pr3_prep/pr3_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr3_5_prep/pr3_5_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/pr5_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/pr6_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr8_prep/pr8_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr9_prep/pr9_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10b_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`
- `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md`
- `/Users/ashen/Desktop/poker_solver/PLAN.md`
- `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`
