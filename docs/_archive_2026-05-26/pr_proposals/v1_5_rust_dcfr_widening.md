# PR 23 Spec — Rust DCFR widening for true range-vs-range Nash (v1.5.0)

**Status:** spec-only, read-only investigation. Author: spec agent (2026-05-23). Orchestrator approves and spawns implementer separately.

**Goal:** Lift the Rust production tier so it can solve true range-vs-range Nash from empty `initial_hole_cards = ()` (i.e. chance-enum-at-root path). Today this path exists only in the Python tier (`poker_solver/dcfr.py`) and is wrapped by `solve_range_vs_range` in `poker_solver/range_aggregator.py` (which is itself a Pluribus-blueprint aggregation workaround, not a true Nash solve — see Python file docstring lines 1–32). The Rust tier currently rejects this config because its `Game` trait packs chance actions into `u8`.

**Headline finding:** the right fix is **NOT** a `u8 → u16` widening — it is an **architectural change to vector-form CFR**, matching how Brown's reference C++ solver does it (`references/code/noambrown_poker_solver/cpp/src/trainer.cpp`). Brown does NOT enumerate hole-card deals as chance-tree children. He stores `hand_count × action_count` regret / strategy vectors per infoset and walks the betting tree once, vectorizing over hands at each node. PR 15's flat-tree exploitability walk (`crates/cfr_core/src/exploit.rs:11-53`) already established the same pattern in our Rust tier for the read-only walk; this PR extends the precedent to the write-side DCFR training loop.

The naive `u8 → u16` widening fixes the type but does NOT make the algorithm tractable — the resulting tree at 1326-way root fan-out × board chance × betting subtree fan-out is operationally infeasible on the 16 GB M-series budget (back-of-envelope below). See §2 + §4.

---

## 1. Problem statement (concrete code citations)

The `Game` trait at `crates/cfr_core/src/game.rs:44` types chance outcomes as `Vec<(u8, f64)>`. `u8` covers 0..=255 distinct action ids; for a chance node that enumerates hole-card pairs, the natural domain is `C(52,2) = 1326` (single-player hole) or `C(52,2) × C(50,2) = 1,070,190` (both players' holes simultaneously), which overflows.

Specific citations:

- **`crates/cfr_core/src/game.rs:44`** — `fn chance_outcomes(&self) -> Vec<(u8, f64)>;` (the load-bearing limit)
- **`crates/cfr_core/src/game.rs:47`** — `fn legal_actions(&self) -> Vec<u8>;` (same domain; betting actions fit in u8 fine, so this is only widened if we choose to unify action types)
- **`crates/cfr_core/src/game.rs:50`** — `fn apply(&self, action: u8) -> Self;` (consumer of the action id; must match whatever width we pick)
- **`crates/cfr_core/src/hunl.rs:12-16`** — The `HUNL` module explicitly documents the limit and the workaround:

  > Scope (PR 6): postflop only. Preflop chance outcomes (packed hole-card 32-bit ints) do not fit in the `Game` trait's `u8` action type, and the preflop port is PR 9. `HUNLState::initial` therefore requires `starting_street >= Street::Flop`. The chance action for board cards is a single `u8` card id (`card_to_int` form, [8, 59]).

- **`crates/cfr_core/src/dcfr.rs:197`** — The DCFR chance-node branch consumes the typed pair: `for (action, prob) in state.chance_outcomes() { ... state.apply(action) ... }`. The recursion itself is type-clean; the issue is the upstream domain.
- **`crates/cfr_core/src/hunl_tree.rs:52,72,79`** — The flat tree stores `chance_outcomes: Vec<(u8, f64)>` and `chance_action: Option<u8>`. Tree-builder structs would also need to widen (or stop storing chance enumerations at root entirely under the vector-form approach).

For comparison the Python tier's `chance_outcomes` returns `list[tuple[Action, float]]` (`poker_solver/hunl.py:310`); `_enumerate_preflop_hole_outcomes` is defined at `poker_solver/hunl.py:601` and returns 1326 tuples — no width limit because Python ints are unbounded.

---

## 2. Proposed change

### Two paths considered

**Path A — Type widening only (`u8 → u16`).** Mechanical Cargo-clippy-driven rename across `game.rs`, all `Game` impls (`kuhn.rs`, `leduc.rs`, `hunl.rs`, `preflop.rs`), `hunl_tree.rs`, `dcfr.rs:197-204`, `exploit.rs`. Action type becomes `u16`. After widening, the `chance_outcomes` for `initial_hole_cards = ()` can return 1326 entries (and the chance-then-chance pattern for both players' holes can in principle return ~1M, though see §4). This is what the user's prompt hypothesized.

**Path B — Vector-form CFR (Brown's C++ pattern).** Stop modeling hole-card deals as chance children. Instead, build the betting tree once (no hole-card chance at the root) and at each player infoset store a `hand_count × action_count` regret/strategy table, vectorizing over hands during traversal. This is the architecture in `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` (the `Trainer::traverse` function). See specifically:

- `trainer.cpp:165-181` — opponent node: loop over actions, then inside each action loop over `opp_hands` to scale reach by per-hand strategy.
- `trainer.cpp:184-209` — own player node: same shape with `update_hands` rows of action values; node value is `Σ_a strategy[h,a] * action_value[a,h]`.
- `trainer.h:43` — infoset stores `hand_count`, not enumerated chance children.

Brown's tree (`river_game.h:19-26`) has `TreeNode` with `player`, `terminal_winner`, contribs, `action_count`, `next` — **no `chance_outcomes` field at the betting layer.** Hands are a global vector (`hands[2]`) attached to the game, not branched into the tree.

### Recommendation: **Path B (vector-form CFR).**

Reasons:

1. **Memory + perf scaling**: Path A puts a 1326-fan-out node at the root with every betting subtree replicated 1326×. Even with shared subtree structure, the *infoset count* explodes because keys are parameterized by hole-cards (`hunl.py:355-358` shows the Python-tier key embeds hole cards explicitly). Path B keeps the infoset count bounded by the betting tree and stores per-hand regret as a contiguous `Vec<f64>` of length `hand_count × action_count` — exactly Brown's layout (`trainer.cpp:74-77`).

2. **Precedent in our codebase**: PR 15's `flat_tree_exploit` (`crates/cfr_core/src/exploit.rs:673-727`) already does vector-form on the read side (BR + EV walks). It precomputes `combos`, builds the betting tree once via `BettingTree::build_from`, and iterates combos against the flat tree at line 702. PR 23 extends the same shape to the write side (regret + strategy updates during DCFR).

3. **Differential-test cleanliness**: Path A would also need infoset key changes (current Python keys embed hole cards: `hunl.py:355-358`). Path B keeps infoset keys betting-only and stores hands as a vector dimension, which mirrors the Pythonic intent cleanly enough that we can keep `solve_range_vs_range` in `range_aggregator.py` as the ground truth without restructuring.

### Type widening still needed (minor)

Even in Path B, we widen `u8 → u16` in two places where the natural domain exceeds 256:

- Board-card-chance over 52 cards stays in `u8` (52 < 256). No change.
- Hand-index — but this lives on the infoset side as `Vec<f64>` indexed by hand position; never enters the `Game` trait. No change.

Net **`Game` trait change is zero** under Path B. The widening is a contained Path-A-bounded prerequisite ONLY if we decide to also model preflop hole-pair sampling as a non-vector chance node (which we should not — see §8 open questions).

### Card-bucketing wedge (load-bearing for production scale)

Even with vector-form, the raw 1326-hand dimension per player infoset is a lot. The `bucket_counts: tuple[int, int, int] = (256, 128, 64)` for (flop, turn, river) from §1 of `PLAN.md:29` give us a much smaller equivalence-class dimension once we use abstraction. With bucketing engaged on postflop streets:

- Flop infoset hand-dim = 256 (down from 1326)
- Turn = 128
- River = 64

Preflop is the unbucketed exception (`PLAN.md:29-30` cites flop/turn/river only). For preflop range-vs-range we accept the full 1326 dimension because preflop is the lossless path per Decision 7.12 (`poker_solver/hunl.py:336-337` references this). Memory analysis in §4 quantifies feasibility.

---

## 3. Files touched (anticipated diff surface)

| File | One-line reason |
|---|---|
| `crates/cfr_core/src/game.rs` | NEW optional trait method `hand_count()` defaulted to 1; opt-in vector-form. Existing `u8` chance_outcomes signature stays for Kuhn / Leduc / board-card-only paths. |
| `crates/cfr_core/src/dcfr.rs` | New branch in `cfr()` (around line 195) for vector-form: when `state.hand_count() > 1`, dispatch to vector-form traversal. Existing scalar path untouched for Kuhn / Leduc. New `cfr_vector()` mirrors Brown's `Trainer::traverse` (`trainer.cpp:138-209`). InfosetData widened to optionally store `Vec<f64>` of length `hand_count × num_actions`. |
| `crates/cfr_core/src/hunl.rs` | Lift the postflop-only restriction in `HUNLState::initial` (drop the `starting_street >= Street::Flop` guard). Add a `vector_mode: bool` discriminator on the state so the DCFR dispatcher knows which path to take. |
| `crates/cfr_core/src/hunl_tree.rs` | Refactor `BettingTree` to NOT enumerate hole-card chance at root when `initial_hole_cards = ()`. (Board-card chance enumeration still uses u8 chance children — these stay in range.) |
| `crates/cfr_core/src/exploit.rs` | Re-use existing `flat_tree_exploit` machinery; tweak BR pass to consume vector-form strategy output. |
| `crates/cfr_core/src/simd.rs` | SIMD kernels for vector-form regret update — same NEON shape as scalar `update_regret_sum` but lane-mapped across hands (Brown's `trainer.cpp:191-208` is unvectorized; we can do better). |
| `crates/cfr_core/src/lib.rs` | New PyO3 entry `solve_range_vs_range_rust(config, iters) -> dict[str, list[list[f64]]]` returning per-infoset, per-hand action probabilities. Strategy dict shape mirrors Python tier exactly. |
| `poker_solver/range_aggregator.py` | OPTIONAL — add a `use_rust_tier=False` flag to `solve_range_vs_range` that, when True, calls the new PyO3 entry and skips the per-combo aggregation. **Out of scope if implementer is over budget** — Python side can stay unchanged and be wired in a v1.5.1 patch. |
| `tests/test_range_vs_range_rust_diff.py` | NEW differential test file. Three test cases per §5 below. |
| `crates/cfr_core/tests/hunl_state_unit.rs` | Lift postflop-only assertions; add vector-form construction unit tests. |
| `CHANGELOG.md` | Entry under "v1.5.0". |
| `docs/pr_proposals/v1_5_rust_dcfr_widening.md` | This spec — already exists; mark IMPLEMENTED post-merge. |

Roughly **~600–900 LOC of new Rust** plus 80–150 LOC of tests. Existing Kuhn / Leduc / single-combo HUNL paths should compile and pass unchanged because the new code path is opt-in via `hand_count() > 1`.

---

## 4. Memory + perf back-of-envelope (16 GB M-series ceiling)

Per-infoset memory for vector-form:

```
infoset_bytes = hand_count × num_actions × 2 × 8       (regret + strategy_sum, f64)
              + hand_count × 4                          (last_discount_iter, u32, per-hand)
```

For postflop with bucketed hands and `num_actions ≤ 14` (`hunl.rs:111`):

| Street | hand_count | num_actions | bytes / infoset |
|---|---|---|---|
| Flop (bucketed) | 256 | 14 | 256 × 14 × 16 = 57 KB |
| Turn (bucketed) | 128 | 14 | 128 × 14 × 16 = 28 KB |
| River (bucketed) | 64 | 14 | 64 × 14 × 16 = 14 KB |
| Preflop (lossless) | 1326 | 14 | 1326 × 14 × 16 = 297 KB |

Total infoset count for a 100 BB HUNL tree with 5 bet sizes is the unknown — but `PLAN.md:37` lists default 100 BB memory as **10–14 GB** in the current scalar tier, and that memory is dominated by per-infoset regret/strategy. Vector-form REPLACES the 1326-way root fan-out (which would explode infoset count) with per-infoset hand vectors; net memory should be **comparable or smaller** than the current per-combo aggregator approach.

**Concrete check (river-only spot, 2 bet sizes, river-bucketed):**

- Betting infosets in a river spot with 2 bet sizes ≈ 200–500 (rough, from PR 7 + PR 8 size profiles). Let's use 500.
- Per infoset: 14 KB (river row above).
- Total: ~7 MB. **Trivial.**

**Concrete check (full preflop, lossless 1326 hands, 4-bet-cap):**

- Preflop infoset count for 4-bet-cap tree ≈ unknown without profiling — `PLAN.md:97` flags PR 9 as in-flight with 10–30 min target wall-clock (`PLAN.md:53`). Let's bound: if 50K preflop infosets, then 50,000 × 297 KB = **14.8 GB**. **At the edge of 16 GB.**

  Mitigation: preflop infoset count is much smaller than postflop in practice (preflop has only ~169 hand classes by suit-iso). If the implementer can extend the existing suit-isomorphism reduction (`poker_solver/abstraction/`, PR 4) to collapse preflop hands to ~169 equivalence classes, the budget drops to **3 GB**.

**Recommendation:** ship Path B with bucketing engaged on flop/turn/river per the locked plan. Preflop full-1326 lossless is a stretch goal for v1.5.0; if profiling shows OOM, gate full preflop behind an `--abstract-preflop` flag that collapses to suit-iso (169 classes). See §8 open questions Q3.

**Perf back-of-envelope:** Brown's `trainer.cpp:191-208` is O(hand_count × action_count) per node visit. For river-bucketed (64 × 14 ≈ 900 ops/node) it should be 5–10× faster than the current 1326-combo-loop in `range_aggregator.py` (`poker_solver/range_aggregator.py:208`+) which calls a full single-combo subgame solver per Pio class.

**Honest caveat (per memory `feedback_no_extrapolate.md`):** these numbers are back-of-envelope. The implementer MUST add a per-street memory profiler at the end of PR 23, matching PR 5's profiler pattern (`PLAN.md:29-30` "PR 5 ships a per-street memory profiler"). If measured memory diverges >2× from the estimates above on a representative spot, escalate to orchestrator before merge.

---

## 5. Differential testing strategy

Python `solve_range_vs_range` in `poker_solver/range_aggregator.py:208` IS the ground truth as the user's prompt states — modulo the caveat that it's a **Pluribus-blueprint aggregation, not a true Nash** (per docstring lines 1–32 of that file). To test true Nash output of the Rust tier, we have two parallel oracles:

1. **Python DCFR with `initial_hole_cards = ()`** — invoke `dcfr.py`'s `_cfr` recursion directly on the empty-hole-cards config; this is the *true* range-vs-range Nash from the Python tier (slow but correct). Reference shape: `poker_solver/dcfr.py:177` walks `chance_outcomes` over the 1326-element list.
2. **`solve_range_vs_range` aggregator** — the existing API, used for sanity-check; should agree with Path 1 within a documented gap (the blueprint vs Nash gap noted in `range_aggregator.py:19-31`).

### Test cases

**Case A — Small RvR (river-only, ~5 vs 5 combos).** Custom range with 5 explicit hole combos per player. River board fixed (e.g. `Ah Kd 7s 2c 9h`). Single bet size (1.0× pot). Both Rust tier and Python tier should reach Nash within < 0.5% pot exploitability after ~500 iters. **Tolerance: per-action probabilities agree within 1e-3** (same tolerance as existing diff tests in `tests/test_dcfr_diff.py`). Wall-clock target: < 10 sec.

**Case B — Medium RvR (turn, ~50 vs 50 combos, bucketed).** Turn spot with EMD-bucketed hands per `PLAN.md:29` 128-bucket policy. 2 bet sizes (0.75, 1.5). Both ranges weighted (mix of suited / pair / offsuit). Exploitability target 0.5% pot after 2000 iters. **Tolerance: 5e-3** on per-bucket action probabilities (slightly looser than Case A because bucketing introduces order-of-summation differences). Wall-clock target: < 5 min.

**Case C — Production-scale (full postflop range vs range, river spot, 1326-ish hands collapsed to river buckets).** Run the full HUNL config with `initial_hole_cards = ()` and standard Sklansky-like ranges. Exploitability target 1% pot. Compare against `solve_range_vs_range` aggregator and document the Nash-vs-blueprint gap. **Pass criterion: Rust output exploitability ≤ Python `dcfr.py` baseline + 10%**. Wall-clock target: < 30 min (matches `PLAN.md:53` HUNL postflop standard target).

**Case D — Full preflop, 1326×1326 (lossless, no bucketing).** Only if memory permits per §4 analysis. Otherwise gate behind suit-iso reduction and re-attempt as Case D'. Skip if OOM at construction time and flag for v1.5.1 follow-up.

Tests live in `tests/test_range_vs_range_rust_diff.py` (new file). Mark Case C with `@pytest.mark.slow timeout(3600)` per `PLAN.md:192`; mark Case D with `@pytest.mark.very_slow timeout(0)`.

Sanity-check oracles:

- Kuhn diff (`tests/test_dcfr_diff.py`) and Leduc diff (`tests/test_leduc_diff.py`) MUST still pass — they exercise the scalar code path which is unchanged.
- Existing river diff (`tests/test_river_diff.py`) MUST still pass — it uses fixed `initial_hole_cards`, so it also exercises the scalar path.
- Existing exploit diff (`tests/test_exploit_diff.py`) MUST still pass — `exploit.rs` flat-tree path is the precedent for vector-form so its contract should not regress.

---

## 6. PR sequencing — paste-ready agent prompts

### 6.1 Implementer agent prompt

```
You are implementing PR 23 (Rust DCFR widening, v1.5.0 candidate).

READ FIRST:
1. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_rust_dcfr_widening.md (this spec, end-to-end)
2. /Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp (lines 138-209 — the load-bearing reference for vector-form CFR; MIT licensed, OK to port verbatim with attribution per references/README.md license audit)
3. /Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs (lines 670-727 — the in-codebase precedent for flat-tree + per-combo iteration)
4. /Users/ashen/Desktop/poker_solver/poker_solver/dcfr.py (the Python ground-truth; structural mirror for behavior parity)

WORK:
1. Create feature branch `pr-23-rust-dcfr-widening` from current main HEAD.
2. Implement Path B (vector-form CFR) per §2 of the spec. Files to touch listed in §3.
3. Reference comment in dcfr.rs: cite Brown's trainer.cpp by file:line and the DCFR paper (Brown & Sandholm 2019) per the existing file-header convention.
4. Add `hand_count()` to the Game trait with default `fn hand_count(&self) -> usize { 1 }`. Override in HUNLState when `initial_hole_cards.is_empty()`.
5. In dcfr.rs `cfr()`, branch on `state.hand_count() > 1`: dispatch to new `cfr_vector()` (mirroring Brown's `Trainer::traverse`). Scalar path stays exactly as today for Kuhn / Leduc / fixed-combo HUNL.
6. Memory profiler: add `crates/cfr_core/src/dcfr_profile.rs` matching PR 5's profiler interface (poker_solver/profiling/ — find the Python counterpart). Print per-street infoset count + bytes-per-infoset at end of solve.
7. PyO3 binding `solve_range_vs_range_rust` in lib.rs — return shape must match the Python-tier dict-of-dicts.

CONSTRAINTS:
- DO NOT modify scalar Kuhn / Leduc / fixed-combo HUNL behavior. Confirm via `cargo test --all` between every commit.
- DO NOT copy verbatim from postflop-solver (AGPL) — see references/README.md §2.
- Brown's MIT solver is OK to port verbatim with attribution.
- Maintain integer-cent discipline per hunl.rs:18-25.
- Every numeric tolerance call MUST cite the Python source-of-truth file:line.

DONE WHEN:
- `cargo test --all` green.
- `cargo clippy --all-targets -- -D warnings` clean.
- `pytest tests/ -x` green including the three new diff cases A, B, C.
- `scripts/check_pr.sh` green (full battery per PLAN.md §4).
- `pr_report.md` written with per-case wall-clock + memory numbers.
- Hand off to audit agent.

IF YOU GET STUCK:
- If memory analysis (§4) shows OOM on a feasible config, STOP and surface to orchestrator. Do NOT attempt the suit-iso preflop reduction inside this PR — that's v1.5.1.
- If Brown's vector-form pattern conflicts with our infoset_key scheme, STOP and surface; do not unilaterally redesign keys.
```

### 6.2 Tests-from-spec agent prompt

```
You are writing the differential test file for PR 23 (Rust DCFR widening).

READ FIRST:
1. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_rust_dcfr_widening.md §5
2. /Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py (existing scalar diff test — pattern reference)
3. /Users/ashen/Desktop/poker_solver/tests/test_range_vs_range_aggregator.py (the existing aggregator test; sanity reference but NOT the ground truth for true Nash)
4. /Users/ashen/Desktop/poker_solver/poker_solver/range_aggregator.py docstring (lines 1-32) — understand the blueprint-vs-Nash gap before writing case C.

WORK:
1. Create `tests/test_range_vs_range_rust_diff.py`.
2. Implement Cases A, B, C per spec §5. Skip Case D pending the implementer's memory profile (gate behind a `pytest.mark.skip` with a TODO citing v1.5.1).
3. Each test:
   - Construct HUNLConfig with the listed parameters
   - Run Python tier (dcfr.py with initial_hole_cards=()) → strategy_py
   - Run Rust tier (new PyO3 entry from implementer) → strategy_rs
   - Assert per-infoset, per-hand probabilities within tolerance (1e-3 / 5e-3 / +10% expl gap per §5)
4. Time-budget the tests with `@pytest.mark.slow` (Case B, C) and `@pytest.mark.very_slow` (Case D when reactivated).
5. Add a positive case from the existing aggregator: build an `RvRResult` from the new Rust path and assert structural equivalence to `solve_range_vs_range` output shape (per `RangeVsRangeResult` definition in `range_aggregator.py:161`).

DONE WHEN:
- Tests run (initially failing or skipping cleanly).
- After implementer lands their patch, all three cases pass per tolerance.
- Wall-clock budgets respected (< 10 s / < 5 min / < 30 min).

IF YOU GET STUCK:
- Tolerance disputes → surface to orchestrator; do not loosen tolerance unilaterally.
- Implementer hasn't shipped the PyO3 entry yet → write the test against the planned interface from spec §3 and mark `pytest.xfail` with a comment until the implementer lands.
```

### 6.3 Audit agent prompt

```
You are auditing PR 23 (Rust DCFR widening, v1.5.0 candidate). You have NO prior context on this PR.

READ FIRST (in this order):
1. /Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_rust_dcfr_widening.md (the spec — what the PR was supposed to do)
2. The PR's `pr_report.md` (what the implementer claims to have done)
3. The diff (`git diff main...pr-23-rust-dcfr-widening`)
4. /Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp (the reference solver — read lines 138-209 to verify the port is faithful)

CHECK:
1. **Spec adherence**: does the diff match §2 (Path B vector-form)? Or did the implementer revert to Path A (mere u8 → u16 widening)?
2. **Scalar paths unchanged**: Kuhn / Leduc / fixed-combo HUNL infosets in dcfr.rs unchanged? Run `git diff` against scalar code paths and verify byte-for-byte parity in the unchanged branches.
3. **Reference attribution**: every block ported from Brown's trainer.cpp cites it by file:line in a Rust comment per the references/README.md §2 license terms (MIT requires notice).
4. **AGPL safety**: zero verbatim or close-paraphrase copying from references/code/postflop-solver or references/code/TexasSolver. Spot-check 5 functions against both AGPL sources.
5. **Integer-cent discipline**: every chip operation in the new vector-form code uses i32 cents per hunl.rs:18-25. No `as f64 -> i32` round-trips except inside `compute_bet_amount`.
6. **Differential test coverage**: §5 cases A, B, C all present and passing. Tolerances match spec.
7. **Memory profile**: implementer added per-street profiler per spec §4 final paragraph. Numbers within 2× of the back-of-envelope estimates.
8. **Tier parity**: existing tests (`test_dcfr_diff.py`, `test_leduc_diff.py`, `test_river_diff.py`, `test_exploit_diff.py`) all green.
9. **Clippy + ruff + mypy** clean.

OUTPUT:
Write `/Users/ashen/Desktop/poker_solver/audit_report_pr23.md` with sections:
- Must-fix (blocks merge)
- Should-fix (merge with follow-up)
- Nice-to-fix (defer)
- Looks-good (highlights worth keeping)

PER MEMORY `feedback_persona_test_rectification.md`, classify each finding as Type A / B / C-CRITICAL / C-USEFUL / C-NICE / D.

DO NOT modify code. Read-only audit.
```

---

## 7. Estimated ship complexity

**HIGH.**

Honest reasons (no extrapolation per memory `feedback_no_extrapolate.md`):

- This is an architectural change, not a type widening. The new `cfr_vector` traversal mirrors a non-trivial 70-line C++ function (`trainer.cpp:138-209`) with NEON SIMD opportunities our existing simd.rs scalar kernels do not cover.
- Memory budget on full preflop (Case D) is at the 16 GB edge per §4 — a misestimate by 2× means OOM. PR 5's profiler discipline must be replicated.
- The `Game` trait gets an optional method; that's a breaking change for any out-of-crate consumers. Acceptable because no out-of-crate consumers exist today.
- Three independent agents must coordinate (implementer + tests + audit) — same complexity as PR 6 (HUNL postflop port), which `PLAN.md:93` shipped as a 24×-speedup milestone but took multi-day cycle time.

Compared to ship-complexity reference points in the repo:
- LOW = PR 4.5 (audit-debt mechanical sweep).
- MEDIUM = PR 8 (NEON SIMD on existing scalar kernels) — algorithm structure unchanged, just lane mapping.
- HIGH = PR 6 (Python → Rust port of HUNL, multi-day, multiple audit rounds).

PR 23 is closer to PR 6 in scope than PR 8.

Calendar: **3–5 days end-to-end** with the standard 5-agent parallel discipline (implementer + tests-from-spec + audit + memory-profiler + diff-orchestrator) — but this is the estimate to revisit after the memory profile lands, NOT a commitment.

---

## 8. Open questions for orchestrator (decide before implementer starts)

**Q1 — Path A vs Path B decision authority.** The spec recommends Path B (vector-form). Path A (u8 → u16) is a 1-day fix that DOES NOT make the problem tractable per §4, but it would let `crates/cfr_core/src/game.rs:44` represent the 1326-deal domain literally. Confirm Path B before implementer starts; if you (orchestrator) want Path A only as a stepping-stone, that's a separate decision that should be explicit. **Default if no decision: Path B.**

**Q2 — Preflop scope in v1.5.0.** Case D (full preflop 1326×1326) is at the 16 GB memory edge per §4. Options:
- (a) Ship v1.5.0 with postflop-only RvR; defer preflop to v1.5.1 behind a suit-iso flag.
- (b) Block v1.5.0 until preflop also ships; longer timeline.
- (c) Ship v1.5.0 with preflop gated behind `--abstract-preflop` flag (suit-iso 169-class reduction).

**Default if no decision: (a)** — ships value sooner; v1.5.1 follow-up handles preflop with empirical memory data.

**Q3 — Wire `solve_range_vs_range` to use the new Rust tier?** §3 lists this as optional. If yes, the Python `range_aggregator.py:208` gains a `use_rust_tier=False` kwarg. If no, the new Rust tier exists alongside but isn't called from Python until v1.5.1. **Default if no decision: leave the Python aggregator untouched in v1.5.0**, ship only the PyO3 binding. v1.5.1 wires it.

**Q4 — UI surfacing.** Per memory `feedback_ui_packaging_sync.md`, user-facing feature PRs must update PR 10b UI + trigger PR 11 .dmg rebuild. PR 23 is borderline: the new Rust tier IS user-facing (true Nash RvR vs blueprint) but the existing aggregator UI surface (post-PR 10b) does not distinguish them today. Question: does v1.5.0 include a UI toggle ("True Nash" vs "Blueprint aggregation") or does the Rust tier silently replace the aggregator wherever feasible? **Default if no decision: silent replacement only when `use_rust_tier=True` (per Q3 default, that's never in v1.5.0, so UI is untouched in v1.5.0)**. This makes v1.5.0 internal-only per `feedback_ui_packaging_sync.md` exemption.

**Q5 — Audit chain.** Per `PLAN.md:58`, PR 3+ requires a fresh general-purpose audit agent. Confirm the audit prompt in §6.3 above is acceptable, or if you want to swap in the `review` skill / `security-review` skill instead.

---

## 9. Readiness verdict

**READY for orchestrator decision on Q1–Q5 → spawn implementer.**

The spec is internally consistent and the architectural direction (Path B, vector-form) is grounded in:
- Existing in-codebase precedent (`exploit.rs` flat-tree).
- Brown's reference C++ pattern (`trainer.cpp`).
- The locked `PLAN.md` bucketing decision (`PLAN.md:29`) which makes per-infoset memory tractable.

Implementer should NOT start until Q1, Q2 are resolved (Path A vs B, preflop scope). Q3, Q4, Q5 can be resolved during implementation if orchestrator prefers.

---

## 10. References

- `crates/cfr_core/src/game.rs:44` — the `u8` chance-outcome typing
- `crates/cfr_core/src/dcfr.rs:189-205` — chance-node branch in DCFR traversal
- `crates/cfr_core/src/hunl.rs:12-16` — postflop-only restriction with explicit u8 commentary
- `crates/cfr_core/src/exploit.rs:11-53` — in-codebase precedent for vector-form (read side)
- `crates/cfr_core/src/exploit.rs:670-727` — `flat_tree_exploit` implementation
- `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` — Brown's vector-form CFR (load-bearing reference)
- `references/code/noambrown_poker_solver/cpp/src/river_game.h:19-26` — Brown's `TreeNode` (no chance children at root)
- `references/code/noambrown_poker_solver/cpp/src/trainer.h:43` — per-infoset `hand_count`
- `poker_solver/dcfr.py:177` — Python tier's chance-outcomes walk (ground truth)
- `poker_solver/hunl.py:310-315, 601` — Python tier's chance-outcome enumeration including `_enumerate_preflop_hole_outcomes`
- `poker_solver/range_aggregator.py:1-32` — blueprint-vs-Nash gap disclosure (the existing workaround)
- `PLAN.md:29` — bucket counts (256 / 128 / 64) — load-bearing for §4 memory analysis
- `PLAN.md:37, 53` — current 100 BB memory + HUNL postflop wall-clock targets
- `PLAN.md:97` — PR 9 preflop status
- `references/README.md` §2 — license audit for verbatim copying (Brown MIT OK; postflop-solver AGPL forbidden)
- `references/papers/dcfr_brown_2019.pdf` — DCFR algorithm reference (cite in code comments)
