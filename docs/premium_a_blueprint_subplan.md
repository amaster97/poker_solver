# Premium-A — HU 1326-Combo Preflop Blueprint + Realtime Postflop Subgame Solver

**Subplan owner:** orchestrator (acshen)
**Created:** 2026-05-28
**Status:** DRAFT — open questions need resolution before Phase 1 dispatch
**Tracking issue / parent PR:** TBD (open after Open Questions are resolved)

---

## 1. Goal & success criteria

### Goal
Ship a *premium* HU (heads-up no-limit) decision engine where:
1. **Preflop lookups are instant** for the standard play envelope — solved from a precomputed full 1326-combo blueprint at 7-8 stack depths.
2. **Postflop play is realtime** (≤30 s for a held-line decision) via subgame solving anchored on the blueprint's preflop continuation ranges.
3. **Custom assumptions and out-of-envelope spots** transparently fall back to the existing slow live-solve path (10-20 min wall).
4. **Stack-depth interpolation** delivers a usable strategy for any depth in `[20, 200] BB`, not just the 7-8 sampled depths.
5. **The user always knows** whether a result came from the blueprint (instant), a subgame solve (seconds), or a live solve (minutes) — UI transparency is non-negotiable.

### Success criteria (must all hold to ship)

| # | Criterion | Measurement | Gate |
|---|-----------|-------------|------|
| 1 | Blueprint generated at 7-8 standard depths, 50K iters each | `solve_hunl_preflop_rvr` finishes for each (depth, ante-config) cell; per-cell exploitability finite | Phase 1.5 deliverable |
| 2 | Asset bundles into the `.dmg` without breaking the current size budget | `du -sh dist/Poker-Solver-X.Y.Z-arm64.dmg` ≤ ~400 MB target (current 1.8.0 = 50 MB; +300 MB asset = ~350 MB) | Phase 2 deliverable |
| 3 | Blueprint lookup is sub-100ms for any (hand, stack_depth, action-sequence) tuple | Microbenchmark in `tests/test_blueprint_lookup.py` | Phase 2 deliverable |
| 4 | Stack-depth interpolation produces a strategy within X% L1 of the two bracketing anchor depths on a smoke fixture | New `tests/test_blueprint_interpolation.py` | Phase 3 deliverable |
| 5 | Postflop subgame solve completes ≤30 s wall on Sarah's W2.3 (deep-stack turn KK vs c-bet) fixture | Persona retest after Phase 4 | Phase 4 deliverable |
| 6 | `solver.solve(spot)` routing API picks blueprint vs subgame vs live correctly for at least the 10 representative spots from `tests/test_chained_orchestrator.py` | New `tests/test_routing.py` | Phase 5 deliverable |
| 7 | PR #147 (13×13 chart widget) consumes blueprint data and renders all 169 classes for at least 3 depth slices | UI smoke + screenshot | Phase 6 deliverable |
| 8 | Diff-test against ≥2 external reference dumps (Brown Pluribus / GTO Wizard scrape / Pio side-by-side) within agreed tolerance | Phase 7 report | Phase 7 deliverable |
| 9 | README + USAGE updated; user-facing "what is blueprint mode?" doc shipped | Phase 8 PR | Phase 8 deliverable |

---

## 2. Phase breakdown

> Conventions: each phase lists a **name**, **deliverable**, **agent prompt**, **wall-time estimate** (eng + compute), and **dependencies**. Agent prompts are ready-to-spawn drop-ins for a Claude SDK agent. All work occurs in per-PR feature branches per branch-ops discipline (memory rule: feedback_branch_ops). All paths absolute.

### Phase 0 — Prerequisite: cs-bug fix lands (task #67 / PR #159)

**Status:** Separate agent already dispatched. **DO NOT START PHASE 1 until merged.**

**Deliverable:** `crates/cfr_core/src/preflop_rvr.rs` `PreflopRvrState::initial` and `crates/cfr_core/src/hunl.rs` `HUNLState::initial_preflop` honor `config.initial_contributions` instead of hardcoding `[SB, BB]`. Regression test asserts a nonzero-initial-contribs config produces a non-degenerate Nash.

**Why this MUST land first:** if the blueprint is generated against the buggy initial state, every depth + every action-sequence in the asset bakes the bug, and the entire 15-20 h overnight compute is wasted. This is an HARD prerequisite — confirm PR #159 is merged on `main` before Phase 1.5 compute starts.

**Wall-time estimate:** in flight, expected <1 day eng.

**Dependencies:** none.

---

### Phase 1 — Blueprint generation pipeline (script + asset format design)

**Deliverable:**
- `scripts/generate_premium_a_blueprint.py` — top-level driver that loops over `(stack_depth, ante_config)`, calls `_rust.solve_hunl_preflop_rvr` with `iterations=50000`, captures the strategy tensor, and serializes to disk.
- Asset format finalized (see § 5 — recommended: **sharded gzipped JSON, one file per stack depth, plus a manifest**).
- Per-shard validation step (exploitability finite, all 1326 combos covered, strategy sums to 1.0 per infoset within `1e-6`).
- Dry-run on 1 depth (100 BB) at 1K iters to validate the pipeline end-to-end before Phase 1.5 commits to the 15-20 h burn.

**Agent prompt:**
> Phase 1 of the Premium-A blueprint subplan (`docs/premium_a_blueprint_subplan.md`). Build the offline blueprint-generation pipeline. Prereq: PR #159 is merged on `main` — confirm before starting. Create `scripts/generate_premium_a_blueprint.py` that takes `--stack-depths 20,30,40,60,80,100,150,200`, `--iterations 50000`, `--output-dir assets/blueprint_v1/`, and for each depth: (a) builds `HUNLConfig(starting_stack=depth*100)` chip-per-BB (SB=50, BB=100, ante=0), (b) calls `_rust.solve_hunl_preflop_rvr(config, initial_hole_cards=None, iterations=iterations)`, (c) serializes to `blueprint_<depth>bb.json.gz` per § 5 of the subplan. Write a manifest `manifest.json` at the asset-bundle root listing `(depth, sha256, file_size, exploitability, n_infosets, n_actions, generation_iters, generation_wall_s)`. Add a `--dry-run` mode that runs depth=100, iters=1000 only (validate end-to-end in <10 min). Write `tests/test_blueprint_generation_pipeline.py` covering: (i) format round-trip (serialize → deserialize → strategy identical), (ii) manifest schema validation, (iii) per-shard invariants (per-infoset probabilities sum to 1.0 ± 1e-6, all 1326 combos present, no NaN). Do NOT trigger the actual 50K-iter compute — that's Phase 1.5. Just make `--dry-run` green and a single 100BB / 1K-iter shard produce a valid file. PR title: `feat(blueprint): Premium-A generation pipeline + asset format`. Land into a feature branch off `main` after PR #159 is in.

**Wall-time estimate:** 2-3 h eng (pipeline + format + tests + dry-run), 0 compute.

**Dependencies:** Phase 0 (PR #159 merged).

---

### Phase 1.5 — Actual overnight blueprint compute

**Deliverable:** 7-8 `.json.gz` shards + `manifest.json` committed to `assets/blueprint_v1/`, OR (if shard size exceeds size budget) released as a separate GitHub release asset that the `.dmg` build step downloads. (Decision: § 6 + Open Question #2.)

**Agent prompt:** *Do not spawn a Claude agent for this. Run on user's terminal via the Phase 1 script. Claude agents have a 25-45 min wall-clock cap (memory rule: feedback_agent_execution_timeout) — a 15-20 h overnight compute WILL be killed silently. The orchestrator should:*
> Hand off to user: "Phase 1.5 of Premium-A is a 15-20 h overnight compute. Run on your terminal as: `python scripts/generate_premium_a_blueprint.py --stack-depths 20,30,40,60,80,100,150,200 --iterations 50000 --output-dir assets/blueprint_v1/ 2>&1 | tee blueprint_gen.log &`. Monitor periodically. Phase 2 unblocks when the manifest exists and every shard is non-empty."

**Wall-time estimate:** 15-20 h compute (user's terminal, NOT an agent), 0 eng.

**Dependencies:** Phase 1.

---

### Phase 2 — Blueprint loader API + asset packaging

**Deliverable:**
- `poker_solver/blueprint.py` — Python loader: `Blueprint.load(asset_dir)`, `Blueprint.lookup(hand, stack_depth, action_seq)` returns action distribution. Falls back to Rust loader only if the Python loader's lookup is slower than 100 ms (likely overkill; defer Rust unless benchmark says otherwise).
- `__init__.py` re-exports `Blueprint`.
- DMG build (`scripts/build_macos_dmg.sh` + `poker_solver.spec`) bundles the asset bundle from `assets/blueprint_v1/`.
- `tests/test_blueprint_lookup.py` — microbench (target <100 ms p99), correctness vs known fixture from Phase 1's dry-run, manifest sha256 verification.

**Agent prompt:**
> Phase 2 of `docs/premium_a_blueprint_subplan.md`. Implement `poker_solver/blueprint.py` per the spec in the subplan § 2 Phase 2. The class must support: `Blueprint.load(asset_dir: Path)` (validates manifest + sha256 each shard), `Blueprint.lookup(hand: Tuple[int,int], stack_depth: int, action_seq: List[Action]) -> Dict[Action, float]` (returns the strategy distribution at that infoset; raises `KeyError` if the depth is not in the manifest — DO NOT silently interpolate here, interpolation is Phase 3). Add `Blueprint.available_depths() -> List[int]`. Wire into `__init__.py`. Update `scripts/build_macos_dmg.sh` and `scripts/poker_solver.spec` so the asset bundle ships in the .dmg under `<bundle>/Resources/blueprint_v1/`. Add `tests/test_blueprint_lookup.py`: (i) load → lookup round-trip on the Phase 1 dry-run 100BB shard, (ii) microbenchmark — 1000 lookups p99 < 100 ms, (iii) manifest sha256 mismatch raises clean error, (iv) `available_depths` returns the manifest's depth list. Verify .dmg builds locally and bundle size ≤ current_1.8.0_dmg_size + ~300 MB. PR title: `feat(blueprint): loader API + .dmg packaging`. Land into a feature branch.

**Wall-time estimate:** 3-4 h eng, 0 compute.

**Dependencies:** Phase 1.5 (or a Phase 1 dry-run shard for stub testing — but ship gate is Phase 1.5).

---

### Phase 3 — Stack-depth interpolation logic

**Deliverable:**
- `poker_solver/blueprint_interpolation.py` — given a target depth not in the manifest, pick the two bracketing anchor depths and produce an interpolated strategy.
- **Recommended algorithm:** per-infoset *log-odds linear interpolation* (interpolate `log(p / (1-p))` per action then re-softmax) — preserves probability simplex, smoother than raw linear in p, and behaves correctly across action-set boundaries where one anchor's distribution has a strictly-positive probability and the other has zero.
- Optional follow-up (not blocking): per-infoset DCFR warm-start from the interpolated strategy (one-pass Phase B) — explicitly out of scope for Phase 3, callable later from Phase 5's live-solve fallback.
- `tests/test_blueprint_interpolation.py`: depth between two anchors round-trips ≤ X% L1 vs both anchors; depth below 20 BB clamps to 20 BB (with warning); depth above 200 BB clamps to 200 BB.

**Agent prompt:**
> Phase 3 of `docs/premium_a_blueprint_subplan.md`. Implement `poker_solver/blueprint_interpolation.py` with `interpolate_strategy(blueprint: Blueprint, hand, target_depth: int, action_seq) -> Dict[Action, float]`. Use log-odds linear interpolation per § 2 Phase 3 of the subplan: for the two bracketing anchor depths `d_lo, d_hi`, fetch action distributions `p_lo, p_hi`, compute `w = (target_depth - d_lo) / (d_hi - d_lo)`, then for each action `a` in the union of supports: `logit_a = (1-w) * logit(p_lo[a]) + w * logit(p_hi[a])` (treat missing actions as `p = 1e-9` to avoid `-inf`), then softmax across actions. Add `Blueprint.lookup_interpolated(...)` that calls into this module. Edge cases: target_depth ≤ min(depths) → clamp + emit `BlueprintInterpolationWarning`; target_depth ≥ max(depths) → same; target_depth ∈ depths → exact lookup (no interpolation). Tests in `tests/test_blueprint_interpolation.py`: (i) `target_depth=70`, anchors are 60 + 80 — interpolated AA-jam-prob is between the two anchor probs, (ii) L1 between interpolated and bracketing anchors < expected_drift (set drift empirically from Phase 1.5 data — placeholder 0.15 until calibrated), (iii) below-min and above-max clamp + warn, (iv) on-anchor depth = exact lookup. PR title: `feat(blueprint): stack-depth interpolation (log-odds linear)`.

**Wall-time estimate:** 2-3 h eng, 0 compute.

**Dependencies:** Phase 2 (loader API stable).

---

### Phase 4 — Realtime postflop subgame solving wiring

**Deliverable:** verify (and patch if needed) that the existing postflop subgame solver consumes the blueprint's continuation ranges as the range prior. Mostly already shipped:
- PR #114 (TerminalCache) — vector-RvR perf
- PR #139 (BR-walk caching) — exploitability checks
- PR #121 (chained orchestrator) — `ChainedSolveResult.solve_postflop(action_seq, board)` lazy postflop entry point

What this phase actually does:
- Replace `chained.py`'s Route-A blueprint-aggregation with a direct call to `Blueprint.lookup_interpolated(...)` (per PR #121's own follow-up note: "swap from Route A blueprint aggregation to vector engine" — Premium-A is the natural target).
- Verify Sarah's W2.3 (deep-stack turn KK vs c-bet) completes ≤30 s post-blueprint anchoring.
- `tests/test_postflop_subgame_anchored.py`: subgame solve on a held W2.3 fixture finishes in <30 s wall and the strategy at the root node is finite, simplex-valid.

**Agent prompt:**
> Phase 4 of `docs/premium_a_blueprint_subplan.md`. Wire the postflop subgame solver onto the Premium-A blueprint. Modify `poker_solver/chained.py`: replace the Route-A `_solve_preflop_range` blueprint-aggregation call with a direct `Blueprint.lookup_interpolated(...)` call (preserve the function signature; this is the single-function swap PR #121's body anticipated). Then trace the data flow: blueprint strategy → continuation ranges per `(hero_class, villain_class)` pair → postflop subgame solver's range prior. Validate on Sarah's W2.3 fixture (deep-stack turn KK vs c-bet, 200BB, Qs7h2d5c, 3-bet pot, SPR≈5.5). Write `tests/test_postflop_subgame_anchored.py`: (i) end-to-end blueprint → subgame solve completes in <30 s wall, (ii) range prior into postflop is well-formed (sums to 1.0 over hero combos, etc.), (iii) the resulting postflop strategy is finite + simplex-valid. If W2.3 still breaches the 30 s gate, escalate as a separate perf PR — don't try to fix it in this phase. PR title: `feat(blueprint): postflop subgame anchored on Premium-A blueprint`.

**Wall-time estimate:** 3-4 h eng, ~5-15 min compute for W2.3 validation. ⚠ if W2.3 still fails the 30 s gate, escalate as a separate perf task before Phase 5 — but Phase 4 itself ships as long as the data flow is correct and a smaller fixture passes.

**Dependencies:** Phase 3 (interpolation in place).

---

### Phase 5 — Top-level routing layer (`solver.solve(spot)`)

**Deliverable:**
- `poker_solver/routing.py` — `Solver.solve(spot: SpotInput) -> SolveResult` decides between:
  1. **Blueprint lookup** (no custom range, depth in `[20, 200]` BB, action sequence prefix matches a blueprint infoset) — returns instantly.
  2. **Postflop subgame solve** (street > preflop, blueprint covers the preflop history) — returns in seconds.
  3. **Live full-tree solve** (custom range / out-of-envelope depth / nonstandard ante / B10 fractional intensities) — returns in minutes.
- The `SolveResult` exposes `source: Literal["blueprint", "subgame", "live"]` so UI / CLI can be transparent.
- `tests/test_routing.py` — at least 10 representative spots from `tests/test_chained_orchestrator.py` route to the expected source.

**Agent prompt:**
> Phase 5 of `docs/premium_a_blueprint_subplan.md`. Build the top-level routing API. Create `poker_solver/routing.py` with class `Solver` and method `solve(spot: SpotInput) -> SolveResult`. The routing decision tree is in subplan § 2 Phase 5: (1) if `spot.custom_range` set OR `spot.intensity_per_combo` set OR `spot.ante` outside the blueprint's ante set OR `spot.depth` outside `[20, 200]` BB → live solve via existing `solve_hunl_preflop` / `solve_range_vs_range_nash`. (2) else if `spot.street == preflop` and action sequence is reachable from blueprint root → instant blueprint lookup (with interpolation). (3) else if `spot.street > preflop` and the preflop history is reachable from blueprint root → postflop subgame solve anchored on blueprint (Phase 4). `SolveResult` carries `source: str`, `strategy: dict`, `wall_time_s: float`, `metadata: dict`. Update `__init__.py` to re-export. Add `tests/test_routing.py` with the 10 reference spots from `tests/test_chained_orchestrator.py`, asserting each routes to expected source. PR title: `feat(routing): top-level Solver.solve() dispatch (blueprint / subgame / live)`.

**Wall-time estimate:** 4-5 h eng, ~5 min compute (routing-test smoke).

**Dependencies:** Phase 4.

---

### Phase 6 — UI integration (PR #147 + PR #148)

**Deliverable:**
- `ui/views/preflop_chart.py` (PR #147 widget) consumes `Blueprint` directly via `Blueprint.lookup_interpolated(...)` to render all 169 classes at a chosen depth.
- New "Blueprint vs Custom" toggle in the run panel (`ui/views/run_panel.py`).
- Source badge in the result pane — visible "BLUEPRINT (instant) / SUBGAME (5-30 s) / LIVE (10-20 min)" indicator. Non-skippable transparency.
- PR #148 chained tab (`ui/views/chained_tab.py`) honors the routing dispatch from Phase 5.
- Spot-input pre-validation: if user picks a custom range or out-of-envelope depth, the UI warns "this will take 10-20 min — proceed?" before the live solve fires (memory rule: feedback_persona_time_budgets — Marcus's <30s tolerance gates user-facing features).

**Agent prompt:**
> Phase 6 of `docs/premium_a_blueprint_subplan.md`. Integrate Premium-A into the UI. (1) `ui/views/preflop_chart.py`: replace any mock data with `Blueprint.lookup_interpolated(...)` calls. Add a "Stack depth" combo box / slider showing all 8 anchor depths + arbitrary integer input (interpolation kicks in for non-anchor). Render all 169 classes in the 13×13 grid. (2) `ui/views/run_panel.py`: add a "Blueprint vs Custom" toggle — Blueprint is the default; Custom unlocks the existing per-combo intensity editor (B10 PR #158). (3) `ui/views/chained_tab.py` (PR #148): route every solve through `Solver.solve(spot)` from Phase 5; display the `source` badge prominently. (4) Add a UI confirmation modal when the routing dispatch returns `source="live"` — "This solve will take ~10-20 min on your machine. Proceed?" with Cancel default. Update `ui/state.py` if needed for any new state fields. Add UI smoke tests in `tests/test_ui_blueprint_integration.py` covering: chart renders for at least 3 depths (60, 67, 80 — the middle one exercises interpolation), source badge updates after each solve, custom-range modal appears for the live path. PR title: `feat(ui): Premium-A blueprint integration + source-transparency badge`.

**Wall-time estimate:** 5-6 h eng, ~10 min compute for UI smoke.

**Dependencies:** Phase 5 (routing API stable).

---

### Phase 7 — Diff-test validation against external references

**Deliverable:**
- `tests/test_blueprint_diff_vs_external.py` — compares blueprint strategies against at least 2 external dumps:
  - **Brown / Pluribus** preflop ranges (if accessible — check `references/` for cached dumps)
  - **GTO Wizard** scrapes (if accessible)
  - **PioSolver** side-by-side (manual user run)
- Per-hand-class L1 distance report; histogram of divergence; per-spot drill-down for outliers.
- Acceptance: median per-class L1 ≤ tolerance (TBD — see Open Question #3); document any classes that exceed and the suspected cause (deep-cap Nash multiplicity, action menu differences, etc.).
- Per the memory rules (`feedback_external_solver_sanity_check`, `feedback_nash_multiplicity_acceptance`): external solvers are SANITY checks, not strict ground truth — divergence on deep-cap (200 BB) is expected and acceptable if explained.

**Agent prompt:**
> Phase 7 of `docs/premium_a_blueprint_subplan.md`. Diff-test the Premium-A blueprint against external references. (1) Check `references/` for any cached Brown/Pluribus/GTO Wizard preflop dumps; document what's available. (2) Write `tests/test_blueprint_diff_vs_external.py` that loads each available reference, normalizes its action representation to the blueprint's action set, and computes per-class L1 distance for the 100 BB depth (most common public reference depth). (3) Produce a divergence report at `docs/premium_a_diff_test_2026-MM-DD.md` with: median L1, p95 L1, top 10 outlier classes + suspected cause (action menu difference / Nash multiplicity / abstraction mismatch). (4) Per memory rules `feedback_external_solver_sanity_check` and `feedback_nash_multiplicity_acceptance`, do NOT hard-fail on deep-cap divergence; treat 200 BB as informational only. The 100 BB and 60 BB gates are the binding ones. PR title: `test(blueprint): diff-test vs external reference solvers`. Auto-merge OK.

**Wall-time estimate:** 4-6 h eng, ~30 min compute for the diff runs.

**Dependencies:** Phase 1.5 (blueprint exists), Phase 6 (so the diff-test mirrors what users see).

---

### Phase 8 — Documentation

**Deliverable:**
- `README.md` updated — Premium-A section + "blueprint vs custom" decision tree for users.
- `USAGE.md` updated — `Solver.solve(spot)` API surface + how to choose between modes.
- `docs/blueprint_user_guide.md` — new doc, plain-English explainer for the user persona: what blueprint mode is, what the depths mean, what interpolation does, when to use Custom.
- `CHANGELOG.md` entry for the next version (v1.9.0 or v2.0.0 — see Open Question #5).

**Agent prompt:**
> Phase 8 of `docs/premium_a_blueprint_subplan.md`. Documentation pass. (1) Update `README.md` — add a "Premium-A blueprint mode" section near the top describing what's instant vs what takes seconds vs what takes minutes. Refer to `docs/blueprint_user_guide.md` for the deep dive. (2) Update `USAGE.md` — document the `Solver.solve(spot)` API surface with examples for each of the 3 routing branches. (3) Create `docs/blueprint_user_guide.md` — plain-English explainer for the user persona (Columbia GSB MBA, Python-strong, wants to *use* the tool not just build it — memory rule `user_role`). Cover: what's in the blueprint (depths × ante configs × 1326 combos), why depth interpolation works, when the live solve fires, how to read the source badge in the UI. (4) Append a CHANGELOG entry for the upcoming release. Do NOT decide the version number — leave it as `vX.Y.Z` and the orchestrator will fill in after Open Question #5 is resolved. PR title: `docs: Premium-A blueprint user guide + README/USAGE refresh`. Auto-merge OK.

**Wall-time estimate:** 2-3 h eng, 0 compute.

**Dependencies:** Phase 6 (UI is what we're documenting).

---

## 3. Dependency graph

```
                  Phase 0 (PR #159 cs-bug fix)
                              |
                              v
              +---------------+
              |
              v
       Phase 1 (pipeline + format design)
              |
              v
       Phase 1.5 (overnight 15-20 h compute on user terminal)
              |
              +--------------------------------+
              |                                |
              v                                v
       Phase 2 (loader + .dmg)          Phase 7 (diff-test) — can start
              |                          as soon as 100BB shard exists
              v
       Phase 3 (interpolation)
              |
              v
       Phase 4 (postflop subgame anchored)
              |
              v
       Phase 5 (routing API)
              |
              v
       Phase 6 (UI integration) <----- Phase 7 feeds back here if any
              |                        outlier needs UI disclosure
              v
       Phase 8 (docs)
              |
              v
        [SHIP v1.9.0 or v2.0.0]
```

**Critical path:** Phase 0 → 1 → 1.5 → 2 → 3 → 4 → 5 → 6 → 8. **Off-critical:** Phase 7 (diff-test) can run in parallel with Phase 4-6 once Phase 1.5 lands.

**Parallel opportunity (per memory rule `feedback_parallel_agents`):** Phase 1 + Phase 7's reference-dump survey can both start as soon as Phase 0 lands. Phase 2 (loader) + Phase 3 (interpolation) can be split across two agents in the same wave once Phase 1.5 lands. Phase 5 (routing) + Phase 6 (UI) overlap is possible if the routing API surface is frozen first.

---

## 4. UI / UX considerations

### Core principle: transparency over speed
The user should always know *what kind of result* they're looking at. Three sources, three visible states.

### The three solve modes (UI-facing)

| Source | UI label | Time budget | When it fires |
|--------|----------|-------------|---------------|
| `blueprint` | "Blueprint (instant)" | <100 ms | Standard HU spot, depth in `[20, 200]` BB, no custom range |
| `subgame` | "Realtime postflop (5-30 s)" | 5-30 s | Postflop spot, blueprint covers preflop history |
| `live` | "Custom live solve (10-20 min)" | 10-20 min | Custom range / out-of-envelope depth / nonstandard ante / B10 per-combo intensity |

### UI elements

1. **Source badge** (Phase 6) — top-right of every result pane. Color-coded: green = blueprint, blue = subgame, orange = live. Tooltip explains *why* this mode fired.
2. **Blueprint vs Custom toggle** (Phase 6) — in the spot-input panel. Default: Blueprint. Switching to Custom unlocks the existing per-combo intensity editor (B10 PR #158).
3. **Live-solve confirmation modal** (Phase 6) — when the dispatcher chooses `live`, ask "This solve will take ~10-20 min. Proceed?" with Cancel default. Honors memory rule `feedback_persona_time_budgets` — Marcus's <30 s tolerance gate.
4. **Stack-depth picker** (Phase 6) — combo box of the 8 anchor depths + a free-form integer input. If the user types a non-anchor (e.g., 67 BB), the chart renders interpolated; a small "interpolated from 60/80 BB" subtitle is shown for transparency.
5. **Chart widget** (Phase 6) — PR #147's 13×13 grid renders all 169 classes from `Blueprint.lookup_interpolated(...)`. No mock data after Phase 6.
6. **Chained tab** (Phase 6) — PR #148's chained orchestrator tab routes every solve through `Solver.solve(spot)`. Source badge surfaces per-stage (Stage 1 preflop = blueprint, Stage 3 postflop = subgame).

### What this does NOT change
- The existing CLI surface (`python -m poker_solver.cli ...`) keeps backward compatibility — the routing API is additive.
- Persona tests still run against the slow-solve path for fidelity (memory rule `feedback_post_ship_persona_retest`). The Premium-A path is an *acceleration*, not a replacement.

---

## 5. Storage format decision

### Recommendation: **sharded gzipped JSON, one file per stack depth, plus a manifest**

```
assets/blueprint_v1/
├── manifest.json                       # ~2 KB
├── blueprint_20bb.json.gz              # ~30-50 MB
├── blueprint_30bb.json.gz
├── blueprint_40bb.json.gz
├── blueprint_60bb.json.gz
├── blueprint_80bb.json.gz
├── blueprint_100bb.json.gz
├── blueprint_150bb.json.gz
└── blueprint_200bb.json.gz             # ~30-50 MB
```

### Justification

| Option | Pro | Con | Verdict |
|--------|-----|-----|---------|
| **Sharded gzipped JSON** | Human-inspectable in transit; gzip ratio is excellent on the sparse-ish strategy tensors; one file per depth = parallel load + per-depth integrity check; aligns with existing `poker_solver/charts/*.json` convention | Larger on disk vs binary (~2× a tight binary format) | **CHOOSE** |
| Single monolithic JSON | Simplest loader | One bad write = whole asset dead; 300 MB+ single file is awkward; no parallel load | reject |
| Binary (msgpack / npz / custom) | Smallest on disk (~150 MB total); fastest load | Opaque; non-debuggable; needs custom reader on every consumer (including Rust if we go that way); breaks the `poker_solver/charts/*.json` convention; first binary asset (`preflop_equity_169x169.npz`) needed PR #122-grade justification | reject for v1; reconsider if v1 hits a size or load-time wall |
| Sharded msgpack | Best of binary + sharded | Still opaque; needs msgpack dep on Rust + Python | reject for v1 |
| Per-depth Parquet | Columnar = fast slice queries | Heavyweight dep; overkill for this data shape | reject |

### Schema (per shard)

```json
{
  "schema_version": "1.0",
  "stack_depth_bb": 100,
  "sb_chips": 50,
  "bb_chips": 100,
  "ante_chips": 0,
  "starting_stack_chips": 10000,
  "iterations": 50000,
  "exploitability_bb": 0.0023,
  "n_infosets": 206,
  "infosets": {
    "<action_sequence_token>": {
      "actions": ["fold", "call", "raise_2.5x", "raise_3x", "all_in"],
      "strategy": {
        "AA": [0.0, 0.05, 0.0, 0.3, 0.65],
        "KK": [...],
        ...
      }
    },
    ...
  }
}
```

### Compression hypothesis (justify the ~300 MB total)

- 1326 combos × ~200 infosets × ~5 actions × 4 bytes (float32) = ~5 MB raw per depth
- JSON adds ~5× overhead (keys, brackets, whitespace) = ~25 MB raw JSON per depth
- gzip on JSON typically hits ~3-5× compression on sparse numeric data = ~5-10 MB per depth
- Across 8 depths × ~5-10 MB = ~40-80 MB

**The "~300 MB asset" in the user's brief is a conservative envelope.** Actual asset size after Phase 1.5 may be much smaller. If it's <100 MB, ship inline in the .dmg with no special handling. If it's >300 MB, see § 6.

### Manifest schema

```json
{
  "schema_version": "1.0",
  "premium_a_version": "v1",
  "generation_date_utc": "2026-MM-DDTHH:MM:SSZ",
  "generation_iters_per_depth": 50000,
  "shards": [
    {
      "depth_bb": 20,
      "filename": "blueprint_20bb.json.gz",
      "sha256": "deadbeef...",
      "file_size_bytes": 38291847,
      "exploitability_bb": 0.0019,
      "generation_wall_s": 6342.0
    },
    ...
  ]
}
```

---

## 6. Asset packaging — fitting into the .dmg

### Current size budget

| Artifact | Size |
|----------|------|
| `Poker-Solver-1.6.0-arm64.dmg` | 47.5 MB |
| `Poker-Solver-1.8.0-arm64.dmg` | 50.1 MB |
| Headroom (typical AppStore upload ceiling: 500 MB-2 GB) | huge |

### Path A — inline in the .dmg (recommended if asset ≤ 200 MB)
`scripts/build_macos_dmg.sh` + `scripts/poker_solver.spec` already vendor `assets/`. Add `assets/blueprint_v1/` to the PyInstaller `datas` list. New .dmg size ≈ 50 MB (current) + asset size. At ≤200 MB asset, the .dmg ends at ≤250 MB — well within any reasonable distribution constraint.

### Path B — GitHub release asset (recommended if asset > 300 MB)
Ship the .dmg lean (50 MB). On first launch, the app fetches `blueprint_v1.tar.gz` from the GitHub release, verifies sha256 against the manifest embedded in the .dmg, and unpacks to `~/Library/Application Support/Poker Solver/blueprint_v1/`. Requires:
- A bootstrap UI flow on first run ("Downloading blueprint data — ~150 MB, ~1 min on broadband. This is the data that lets your solver give instant answers.")
- A re-fetch path in case the local copy is corrupted (sha256 mismatch).

### Decision rule (Phase 1.5 deliverable triggers this)

| Phase 1.5 final asset size | Path |
|----------------------------|------|
| ≤ 200 MB | Path A (inline) |
| 200-300 MB | Path A (inline), with size warning in release notes |
| > 300 MB | Path B (GitHub release asset + first-run download) |

---

## 7. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|-----------|
| R1 | PR #159 (cs-bug) doesn't merge in time / regresses | Med | **Critical** — wastes 15-20 h compute | Hard gate: Phase 1.5 cannot start until PR #159 is on `main` AND a regression test asserts `initial_contributions != [SB, BB]` is honored |
| R2 | 50K iters on 200 BB depth doesn't converge to usable exploitability | Med | High — could need 100K+ iters → 30-40 h compute | Run a 100 BB / 50K iter pilot first; check exploitability trajectory; recalibrate iter count if needed |
| R3 | Asset size exceeds 300 MB after Phase 1.5 | Low | Med — forces Path B (download flow) | Path B is already designed; not a ship blocker, just additional eng cost in Phase 2 |
| R4 | Log-odds interpolation produces visible artifacts at action-set boundaries | Med | Med | Phase 3 includes drift tests; if artifacts appear, fallback to per-class equity-weighted bilinear or DCFR warm-start refinement |
| R5 | Postflop subgame solve still >30 s on W2.3 even with blueprint anchoring | Med | High — fails persona-test gate | Phase 4 explicitly hands W2.3 perf to a separate task if it breaches; Premium-A ships on smaller-fixture validation |
| R6 | External diff-test (Phase 7) shows large divergence at 200 BB depth | High | Low — memory rule `feedback_nash_multiplicity_acceptance` says deep-cap divergence is acceptable | Phase 7 acceptance criterion explicitly excludes 200 BB from binding gate; document divergence + ship |
| R7 | UI confirmation modal annoys experienced users who know what live solve costs | Low | Low | Phase 6 adds an "always proceed" preference toggle (per-session) |
| R8 | Blueprint shipped, but a user runs a spot at depth=15 BB or depth=250 BB | Med | Low | Phase 3 clamps + warns; Phase 5 routes to live solve for out-of-envelope; both already in scope |
| R9 | Mid-Phase 4 we discover `chained.py`'s Route-A blueprint-aggregation contract doesn't cleanly accept a real 1326-combo strategy (e.g., it expects 169-class aggregated input) | Med | Med | Phase 4 agent prompt makes this an explicit verification step; if mismatch, the swap becomes a 2-PR job (adapter PR first, then the Phase 4 swap) — adds ~1 day eng but doesn't reroute the critical path |
| R10 | Agent execution timeout silently kills a long-running phase agent (memory rule `feedback_agent_execution_timeout`) | High for Phase 1.5; Low for Phase 1/2/3/4/5/6/7/8 | Critical for Phase 1.5 | Phase 1.5 explicitly runs on user terminal, not as an agent; all other phases are <6 h eng and fit the agent budget |
| R11 | PR-naming collision in release notes (memory rule `feedback_pr_naming_collision`) | Low | Low | Cite by `commit <SHA>` and `GitHub PR #N (<title>)` in release notes |

---

## 8. Open questions for user (top 5)

Phase 1 cannot start until these are answered.

### Q1. Ante configuration matrix — single config or multi-config?
**Default:** SB=50, BB=100, ante=0 (chip-per-BB, no ante). This matches the existing fixtures and is the standard HU online format.

**Alternatives that double or triple the compute:**
- (a) Add `ante=12.5` (12.5% ante, common in live cash) → 2× compute
- (b) Add `ante=25` (25% straddle equivalent) → 3× compute
- (c) Single config only → as-is

**Recommendation:** Single config (no ante) for v1. Ship the ante matrix as Premium-A v2 if the persona tests show ante variants are needed.

**Decision needed:** Yes / No on ante matrix in v1.

---

### Q2. Exact depth set — 7 or 8 depths? Which depths?
**User's brief said:** "7-8 standard depths: 20, 30, 40, 60, 80, 100, 150, 200 BB".

**Options:**
- (a) All 8 as proposed (20, 30, 40, 60, 80, 100, 150, 200 BB) — ~15-20 h compute
- (b) Drop 150 BB (rare in practice) → 7 depths, ~13-18 h compute
- (c) Add 50 BB (common in MTT) → 9 depths, ~17-22 h compute
- (d) Skip 200 BB if R6 (deep-cap multiplicity) is too noisy → 7 depths, ~12-17 h compute

**Recommendation:** Start with all 8 (option a). Skip 200 BB only if the 100 BB pilot shows convergence issues that imply 200 BB will be unconverged at 50K iters.

**Decision needed:** Final depth list.

---

### Q3. External diff-test tolerance — what's "close enough"?
Phase 7 needs a binding tolerance. Per memory rule `feedback_external_solver_sanity_check`, external solvers are sanity checks not strict ground truth.

**Options:**
- (a) Median per-class L1 ≤ 0.10 at 100 BB (lenient — accepts that our action menu may differ from Pio's)
- (b) Median per-class L1 ≤ 0.05 at 100 BB (moderate — flags real semantic divergence)
- (c) Median per-class L1 ≤ 0.02 at 100 BB (strict — basically requires action-menu parity)

**Recommendation:** (a) for v1 ship; tighten in v2 once we know the typical drift.

**Decision needed:** Tolerance value.

---

### Q4. Asset packaging path A vs B — defer to Phase 1.5 outcome, or pre-commit?
The auto-rule in § 6 says ≤200 MB → Path A, >300 MB → Path B. The actual size is unknown until Phase 1.5 finishes.

**Options:**
- (a) Defer — let Phase 2 dynamically pick based on Phase 1.5 output size
- (b) Pre-commit to Path A (inline) — simpler eng, may produce a 350+ MB .dmg
- (c) Pre-commit to Path B (download) — more eng, smaller .dmg

**Recommendation:** (a) — defer.

**Decision needed:** Defer (a) or pre-commit?

---

### Q5. Release version — v1.9.0 or v2.0.0?
Premium-A is a major capability addition (instant blueprint lookup is a marquee feature, source-transparency UI is user-facing, and the .dmg ships a new asset bundle that may need a first-run download).

**Options:**
- (a) v1.9.0 — additive, backward-compat
- (b) v2.0.0 — frame it as a generational jump

**Recommendation:** v2.0.0 if the asset bundle exceeds 200 MB (user-visible behavior change at first run); v1.9.0 otherwise.

**Decision needed:** Version number — and confirm whether the upcoming release should land as a single "Premium-A" release or be split across two (v1.9.0 = engine + asset; v1.9.1 = UI).

---

## 9. Total wall-time estimate

| Phase | Engineering | Compute | Critical-path? |
|-------|-------------|---------|----------------|
| Phase 0 (PR #159) | in flight (~1 d) | 0 | yes |
| Phase 1 (pipeline) | 2-3 h | 0 | yes |
| Phase 1.5 (overnight) | 0 | **15-20 h** | yes |
| Phase 2 (loader) | 3-4 h | 0 | yes |
| Phase 3 (interpolation) | 2-3 h | 0 | yes |
| Phase 4 (subgame anchored) | 3-4 h | <0.5 h | yes |
| Phase 5 (routing) | 4-5 h | <0.1 h | yes |
| Phase 6 (UI) | 5-6 h | <0.2 h | yes |
| Phase 7 (diff-test) | 4-6 h | <0.5 h | no — off-critical |
| Phase 8 (docs) | 2-3 h | 0 | yes |
| **Critical path total** | **~22-28 h eng** + **15-20 h compute** | | |
| **Calendar estimate** | **5-7 calendar days** at single-orchestrator pace with the user's autonomous-burst floor=4 (memory rule `feedback_parallel_agents`) | | |

**Calendar caveat:** the 15-20 h overnight compute (Phase 1.5) is contiguous and runs on the user's terminal — eng phases can stack densely around it, so the wall-clock is dominated by the overnight burn plus the 22-28 h of engineering spread across ~2-3 working days using parallel agents.

---

## 10. Memory-rule applicability checklist

- `feedback_branch_ops` — every phase ships a per-PR feature branch off `main`. ✓
- `feedback_parallel_agents` — Phase 2+3 + Phase 5+6 + Phase 7 (parallel to 4-6) can all fan out. ✓
- `feedback_reference_first` — Phase 7 explicitly checks `references/` for cached external solver dumps. ✓
- `feedback_agent_execution_timeout` — Phase 1.5 runs on user terminal, NOT as an agent. ✓
- `feedback_silent_noop_hazard` — Phase 1 dry-run is a HARD `--iterations 10` smoke before the 50K production burn. ✓
- `feedback_silent_skip_hazard` — all tests use HARD-FAIL semantics (no `pytest.skip()` in load-bearing assertions). ✓
- `feedback_persona_time_budgets` — Phase 6 includes the live-solve confirmation modal (Marcus's <30 s gate). ✓
- `feedback_independent_verification` — Phase 7 is an independent diff-test before sign-off. ✓
- `feedback_external_solver_sanity_check` — Phase 7 treats external dumps as sanity, not ground truth, and excludes 200 BB from binding gate. ✓
- `feedback_post_ship_persona_retest` — after Phase 6 ships, retest Sarah W2.1 / W2.3 / Marcus's <30 s spots at production scale. ✓
- `feedback_ui_packaging_sync` — Phase 6 (UI) updates PR 10b UI + Phase 2 triggers PR 11 .dmg rebuild. ✓
- `feedback_continuous_pruning` — after each phase ships, prune PLAN.md + archive refuted claims. ✓
- `feedback_label_vs_semantics` — Phase 4's verification step explicitly checks Route A's contract before the swap. ✓

---

## 11. Sign-off

Subplan is **DRAFT** until Open Questions § 8 are answered. Once resolved, this doc is the source of truth for Premium-A. Phase agents are spawned per § 2's agent prompts; the orchestrator dispatches per § 3's dependency graph.

End of subplan.
