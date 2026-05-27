# EV-of-Action Invariance Sanity Gauntlet — Design Doc

**Date:** 2026-05-27
**Status:** DESIGN ONLY — no implementation in this doc.
**Replaces (proposed):** strict per-cell strategy-probability comparison vs Brown's binary as a load-bearing acceptance gate.
**Supplements:** PR 53's 4-layer reframed gate (`docs/acceptance_test_reframe.md`).

---

## 0. TL;DR

Strict per-cell `|σ_ours(I, a) − σ_brown(I, a)| ≤ ε` is non-falsifiable on deep-cap HUNL because Nash is non-unique (indifference manifolds). But the EV of each action at each infoset *is* unique across all Nash equilibria of a constant-sum game (Nash invariance). So compare **EV(I, a)**, not **σ(I, a)** — this is a real cross-solver check that's blind to which Nash each solver picked, but catches game-definition bugs, terminal-utility bugs, and unconverged solvers head-on.

---

## 1. Mathematical foundation

**Setup.** HUNL subgames under the canonical Brown convention (winner takes the whole pot including dead money; loser eats their subgame contribution; see `feedback_brown_convention_adopt.md`) are **constant-sum**: at every leaf `u_0(z) + u_1(z) = base_pot/bb`, a fixed constant of the game. The constant can be absorbed by subtracting `base_pot/2` per player, giving an equivalent zero-sum game with the same Nash set.

**Nash invariance theorem (von Neumann minimax; restated as Theorem 2 in Brown 2019 *"Deep Counterfactual Regret Minimization,"* and standard in any extensive-form game theory text, e.g., Shoham & Leyton-Brown ch. 5):** For a 2-player zero-sum (or constant-sum) game, the following are unique across **all** Nash equilibria σ* of the game:

1. The **game value** `V* = E_{z~σ*}[u_0(z)]` (a single scalar per player; pair sums to the constant).
2. The **value of every reachable infoset** `V_i(I) = E[u_i | I, σ*]` (assuming both players play σ* from I onward; reachability defined w.r.t. the opponent's σ* and chance).
3. The **EV of every action at every reachable infoset** `Q_i(I, a) = E[u_i | I, take a, then σ* thereafter]`.

(Strategy probabilities σ*(I, a) are **NOT** unique — that's exactly the Nash multiplicity we already documented in `feedback_nash_multiplicity_acceptance.md`.)

**Corollary used by the gauntlet.** If `a ∈ support(σ*(I))` for some Nash σ*, then `Q_i(I, a) = V_i(I)` (every action a Nash actually plays must achieve the value of the infoset — otherwise it wouldn't be a best response). If `a` is dominated, `Q_i(I, a) < V_i(I)`. Either way, `Q_i(I, a)` is a single number determined by the game alone, not by which σ* you chose.

**Formulas (carrying the canonical convention).**

```
V_i(I)     = max_a Q_i(I, a)                              (i is to act at I)
Q_i(I, a)  = E_{h ~ P(·|I)} [
               E_{z | take a from h, σ* thereafter} [ u_i(z) ]
             ]
u_i(z)     = pot_total(z) − contrib_subgame_i(z)          if i wins z
           = − contrib_subgame_i(z)                       if i loses z
           = pot_total(z)/2 − contrib_subgame_i(z)        if tie
```

**Falsifiable assertion.** For any two correctly-implemented solvers σ*_A and σ*_B of the *same* game, `Q_i(I, a; σ*_A) = Q_i(I, a; σ*_B)` for every (I, a). Disagreement at the EV level means either (i) the two solvers are solving different games, (ii) at least one solver has a regret-update / utility / terminal bug, or (iii) at least one solver hasn't converged.

---

## 2. Methodology spec

### 2.1 Fixture selection

Phase 1 — minimum viable suite (this design):

- `dry_A83_rainbow` at 2000 DCFR iters (the canonical multiplicity fixture; root-history depth-0 must agree exactly per `reframed-gate-masks-bugs`).

Phase 2 — extended suite (post Phase 1 green, open question Q2):

- `K72`, `Q52`, plus one or two clean low-depth fixtures (e.g., a flop spot ≤ 6 nodes deep) to control for "EV invariance gauntlet itself is buggy" cases.

### 2.2 Pipeline (per fixture)

1. **Solve via Rust DCFR** at the iteration count specified by the fixture spec → dump `σ*_ours: dict[infoset_id → action → prob]` and (importantly) the full subgame tree.
2. **Solve via Brown's `cpp/trainer.cpp`** at matched config (same fixture spec, same iter count if achievable, otherwise document the difference) → dump `σ*_brown: dict[infoset_id → action → prob]`.
3. **Canonicalize action-menu intersection.** EV-of-action only well-defined where both solvers offered the action. Build `actions(I) = actions_ours(I) ∩ actions_brown(I)`; cells outside intersection are EXCLUDED from EV comparison and reported separately as "menu-only divergence" (per `feedback_external_solver_sanity_check.md`).
4. **Compute action EVs.**
   - For each `I, a ∈ actions(I)`: compute `Q_ours(I, a) = EV_i(I, a, σ*_ours)` and `Q_brown(I, a) = EV_i(I, a, σ*_brown)` by walking the same subgame tree from (I, a) under each strategy. Player i is the player to act at I (always well-defined).
   - Both EVs computed in units of BB (chips/big-blind).
5. **Aggregate.**
   - Per-cell delta: `Δ(I, a) = | Q_ours(I, a) − Q_brown(I, a) |`.
   - Max delta: `Δ_max = max_{I, a} Δ(I, a)`.
   - 75th percentile, 95th percentile reported alongside max for noise-sensitivity intuition.
   - Layer-disaggregated: report `Δ_max` separately for depth ≤ 2 (shallow) vs depth ≥ 3 (deep) per `reframed-gate-masks-bugs` — the shallow layer is load-bearing.

### 2.3 Decision rule

Default tolerances (subject to open question Q1):

| Layer            | Scope                     | Tolerance | Failure interpretation                                           |
| ---------------- | ------------------------- | --------- | ---------------------------------------------------------------- |
| Shallow-strict   | depth ≤ 2, all (I, a)     | 0.10 BB   | Engine bug at root; game definition mismatch; convention bug     |
| Deep             | depth ≥ 3, all (I, a)     | 0.10 BB   | DCFR convergence issue; regret-update bug; abstraction artifact  |
| Permissive       | noisy / low-iter fixtures | 0.50 BB   | Used only when fixture iter count too low for tight conv         |

**PASS:** `Δ_max ≤ tolerance` on BOTH layers → both solvers solved the same game, both converged to some valid Nash, no algorithmic bug.

**FAIL:** `Δ_max > tolerance` on either layer → at least one solver is wrong (or the game definitions differ). Triage:

- Shallow failure → root-history engine disagreement; check terminal utility convention, action enumeration at root, infoset bucketing.
- Deep-only failure → convergence; rerun with higher iters before declaring bug.
- Both-layer failure → likely game-definition mismatch (e.g., one solver under the legacy "rust" convention, the other under canonical Brown).

---

## 3. Why this is better than strategy-prob diff

| Failure mode                                | σ-prob strict gate                       | EV-invariance gauntlet                       |
| ------------------------------------------- | ---------------------------------------- | -------------------------------------------- |
| Convention bug (e.g., legacy "rust" leak)   | catches it (changes σ)                   | **catches it directly** (changes u, hence Q) |
| DCFR regret-update bug                      | catches it eventually                    | **catches it earlier** (σ off → Q off)       |
| Unconverged solver                          | catches it as "noisy σ"                  | **catches it as elevated Δ_max**             |
| Nash multiplicity at deep cap (NOT a bug)   | **FALSE POSITIVE** (gate fails)          | PASS (Q is invariant)                        |
| Action-menu differences (intentional)       | requires intersection-only comparison    | requires intersection-only comparison (same) |
| Card-abstraction differences                | FALSE POSITIVE                           | PASS if both abstractions converge to ε-Nash |

**Bottom line.** σ-prob diff is non-falsifiable on indifference manifolds — it cannot tell a real bug apart from "Brown landed at a different point on the same manifold we landed on." EV diff is non-trivial *only* when there's a real algorithmic / game-definition issue. False positives drop to ~0, true positives stay intact.

**Connection to canonical convention.** This gauntlet is the empirical lever that locks in the canonical Brown terminal-utility convention (`feedback_brown_convention_adopt.md`). Under the legacy "rust" convention, our `u_i(z)` differed from Brown's, so even with matched σ* the Q values would disagree by a constant per leaf — easily detectable by EV-Δ. Under the canonical convention, agreement should drop to numerical noise.

---

## 4. Implementation sketch (structure only)

**Location:** new module `tests/test_ev_invariance.py` (alongside `test_v1_5_brown_apples_to_apples.py`).

**Components:**

```
tests/test_ev_invariance.py
├── load_brown_strategy_dump(fixture_id) → dict[infoset_id → action → prob]
│   (parser for Brown's serialized strategy output; reuse from
│    test_v1_5_brown_apples_to_apples.py if a parser already exists)
│
├── solve_ours(fixture_id, iters) → (strategy_dict, subgame_tree)
│   (thin wrapper over the existing Rust DCFR entrypoint)
│
├── canonicalize_action_intersection(σ_ours, σ_brown)
│     → dict[infoset_id → list[action]]
│
├── compute_action_ev(strategy, infoset_id, action, subgame_tree)
│     → float (BB)
│   (recursive tree walk: take action a from I, then play `strategy`
│    at every subsequent decision node; expectation over chance and
│    opponent moves; leaf returns u_i(z) per canonical convention)
│
├── aggregate_deltas(σ_ours, σ_brown, intersection, tree)
│     → dict {layer → (Δ_max, Δ_p75, Δ_p95, n_cells)}
│
└── test_ev_invariance_<fixture> for each fixture in suite
       solves both, computes Δs, asserts layer-disaggregated tolerances
```

**Performance note.** `compute_action_ev` walks the full subtree per cell — naively O(cells × |tree|). Memoize per-infoset value with `V_i(I) = Σ_a σ_strategy(I, a) · Q_i(I, a)` and compute bottom-up so total work is O(|tree|) per strategy. Two strategies → 2·O(|tree|).

**Fixture compatibility.** Reuses the same Brown dumps used by `test_v1_5_brown_apples_to_apples.py`; no new Brown solver invocation needed for the shared suite.

**Tolerance constants.** Hoist `EV_TOL_STRICT = 0.10`, `EV_TOL_PERMISSIVE = 0.50` to `tests/conftest.py` so future fixtures can pick the band by parameter.

**Hard-fail discipline (per `feedback_silent_skip_hazard.md`).** No `pytest.skip()` on missing Brown dumps. If a dump is missing, the test must `pytest.fail()` with a clear error: "EV invariance gauntlet requires Brown dump for <fixture>; rebuild via scripts/build_brown_dumps.sh."

---

## 5. What this gauntlet DOES test

- Same **game definition**: terminal utility (canonical convention), action set at every node, deal randomness, infoset bucketing.
- **Both solvers converged** to a Nash (any Nash; multiplicity is fine).
- **No regret-update bugs**: a regret bug would distort σ → distort Q.
- **No utility-computation bugs**: a u_i bug would change Q at the leaf and propagate up.
- **No infoset bucketing bugs** at the boundary (mismatched buckets show up as Q mismatches on the boundary infosets).

---

## 6. What this gauntlet does NOT test

- **Specific strategy probabilities.** Mixed-strategy frequencies at deep-cap indifference points can differ arbitrarily within the manifold and the gauntlet PASSES — that's the whole point.
- **Convergence speed.** A solver that takes 100k iters vs 2000 iters will look identical at the EV level once both converge. To test convergence rate, use exploitability vs iters separately.
- **Per-iteration behavior.** Mid-run snapshots, regret accumulation patterns, action-frequency-vs-iter curves — out of scope.
- **Action-menu coverage.** If Rust offers `b75` and Brown doesn't, the gauntlet excludes that cell from comparison (intersection-only). Coverage is reported but doesn't enter the pass/fail decision.

This is consistent with `external-solver-sanity-check` (Brown = sanity check on strategy) AND with `brown-convention-adopt` (Brown = canonical reference on game definition + strict ground truth on EV).

---

## 7. Open questions for the user

**Q1. Tolerance band.** Three options:

- (a) **0.1 BB strict** across all layers — assumes both solvers converged tightly. Pro: catches small regressions. Con: false positives if either solver is under-iterated.
- (b) **0.5 BB permissive** — accommodates lower iter counts. Pro: fewer flake. Con: might mask a real 0.2 BB convention bug.
- (c) **BB-of-pot relative**, e.g., `Δ_max ≤ 0.01 · pot_size_bb`. Pro: scale-invariant; catches "0.1 BB on a 5 BB pot" (significant) while permitting "0.5 BB on a 200 BB pot" (noise). Con: more complex to communicate.

Default proposal: (a) strict (0.1 BB) on shallow layer + (c) BB-of-pot relative on deep layer with floor 0.1 BB. User to confirm.

**Q2. Multi-fixture extension.** Phase 1 ships `dry_A83_rainbow` alone. Phase 2 candidates: `K72`, `Q52`, plus one clean low-depth fixture (e.g., a flop turn-card-pair node, 4 actions deep) as a sanity-check on the gauntlet itself. Add all in Phase 2, or staged?

**Q3. Replace or supplement the 4-layer reframed gate?**

- **Supplement** (default proposal): keep PR 53's 4-layer gate (coverage, shallow-strict on σ, directional, structural) and add the EV gauntlet as a new orthogonal axis. Pro: layered defense; existing CI semantics unchanged. Con: more tests to maintain.
- **Replace deep-layer of σ gate**: drop Layer 3 (deep-permissive σ direction/percentile) in favor of EV-invariance; keep Layers 1, 2, 4. Pro: EV-invariance is strictly more principled than σ percentile at depth. Con: bigger change; needs migration plan.

User to choose. If user is undecided, default to **supplement** — additive changes are lower risk.

---

## 8. Cross-references

- `feedback_brown_convention_adopt.md` — canonical terminal utility convention (the rule this gauntlet operationalizes). Brown remains canonical for game-definition + EV ground truth.
- `feedback_external_solver_sanity_check.md` — Brown is sanity-check for strategy, not strict ground truth. This gauntlet replaces the strict-σ direction with strict-EV.
- `feedback_nash_multiplicity_acceptance.md` — explains *why* strict-σ at deep-cap is non-falsifiable; EV-invariance is the principled answer.
- `feedback_reframed_gate_masks_bugs.md` — load-bearing shallow-strict layer. EV gauntlet inherits this principle: layer-disaggregated reporting, no aggregate-only verdicts.
- `feedback_silent_skip_hazard.md` — no skips on missing fixtures; hard-fail with actionable error.
- `feedback_independent_verification.md` — EV gauntlet is itself an independent diff-test of the σ gate's verdict; if σ gate says PASS but EV gauntlet says FAIL, EV gauntlet wins.
- `docs/acceptance_test_reframe.md` — PR 53's 4-layer gate, which this design supplements (Q3).

**Reference:** Brown 2019, *"Deep Counterfactual Regret Minimization,"* Theorem 2 (Nash invariance of best-response value); von Neumann 1928, *"Zur Theorie der Gesellschaftsspiele,"* minimax theorem; Shoham & Leyton-Brown, *Multiagent Systems*, ch. 5 (uniqueness of Nash value in 2p zero-sum).

---

## 9. Non-goals for this design doc

- No code. Implementation is a separate PR after user signoff on Q1-Q3.
- No fixture rebuilding. Phase 1 uses existing Brown dumps.
- No discussion of multi-player extension. Nash invariance of EV is a 2-player constant-sum result; n≥3 needs a different framing entirely.
- No exploitability benchmarking. That's a separate axis (convergence-rate), not an EV-invariance check.
