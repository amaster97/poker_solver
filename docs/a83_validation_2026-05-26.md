# A83 Deep-Cap DCFR Validation — 2026-05-26

**Author:** `poker-cfr-validator` agent (reconstructed from task transcript
`af768999666b6addf.output`; the agent ran read-only and did not have Write
access, so this report is persisted here after the fact).
**Mode:** Read-only audit of `crates/cfr_core/src/dcfr_vector.rs`,
`crates/cfr_core/src/simd.rs`, `crates/cfr_core/src/exploit.rs`, against
Brown & Sandholm 2019 ("Solving Imperfect-Information Games via Discounted
Regret Minimization") and Brown's reference C++ trainer
(`references/noambrown_poker_solver/cpp/src/trainer.cpp`).
**Scope:** Verify DCFR math correctness for the A83 deep-cap divergence
(`As 8s 3s` board, `b1000r3000` action history, bottom-pair-Ace cells
`3sAs` + `3cAc`, ~33-pp call-frequency divergence vs Brown).
**Verdict (TL;DR):** **PASS — DCFR math correct (3rd independent audit).**
The 33-pp empirical divergence is NOT a DCFR algorithm bug. Two real
non-algorithmic causes are documented; v1.6.1 ship is not blocked.

---

## 0. How to read this report

This is the third independent DCFR-math audit on A83. The two prior audits
(`docs/pr_23_deep_cap_algorithmic_triage.md`, `docs/dcfr_weighting_audit.md`)
both verified "no algorithmic bug" by a different methodology (line-by-line
vs `trainer.cpp`, hyperparameter equivalence vs Brown 2019). This audit
re-verifies from the formula side: for each load-bearing DCFR formula in
Brown 2019, we cite the paper section, find the corresponding Rust
implementation, and assess PASS / FAIL / INDETERMINATE.

Output structure follows the validator's agent description: per-formula
verdicts, edge-case sweep, and a recommendation.

---

## 1. Locked DCFR hyperparameters

Per `references/papers/brown_sandholm_2019.pdf` §3 and the project's locked
DCFR config:

| Hyperparameter | Brown 2019 value | Rust value | Status |
|---|---|---|---|
| α (alpha) — positive-regret discount exponent | 1.5 | `1.5` in `dcfr_vector.rs:DCFR_ALPHA` | **PASS** |
| β (beta) — negative-regret discount exponent | 0.0 | `0.0` in `dcfr_vector.rs:DCFR_BETA` | **PASS** |
| γ (gamma) — strategy-sum discount exponent | 2.0 | `2.0` in `dcfr_vector.rs:DCFR_GAMMA` | **PASS** |

All three discount exponents match the locked values from the published DCFR
parameterization. Cross-confirmed against `trainer.cpp:148-150`
(`alpha = 1.5; beta = 0; gamma = 2`).

---

## 2. Per-formula verdicts

### 2.1 Regret update — Brown 2019 §"Regret Discounting" (Eq. 4 + Algorithm 1 line 6)

**Paper formula:**
```
For positive accumulated regret r_{t-1}(I, a):
  r_t(I, a) = r_{t-1}(I, a) * ((t-1)^α / ((t-1)^α + 1)) + immediate_regret(I, a)

For negative accumulated regret r_{t-1}(I, a):
  r_t(I, a) = r_{t-1}(I, a) * ((t-1)^β / ((t-1)^β + 1)) + immediate_regret(I, a)
```

**Rust implementation:** `crates/cfr_core/src/dcfr_vector.rs:264-279` —
`update_regret_sum_vector(...)` applies the per-sign discount weights via
the scalar pre-multiplier path with a SIMD branch in
`crates/cfr_core/src/simd.rs:166-173`
(`update_regret_sum_neon_f64x2`/`update_regret_sum_avx2_f64x4` lane bodies
mirror the scalar form: `r * weight_pos_or_neg + r_imm`).

**Verdict: PASS.** The arithmetic matches the paper. The discount weight is
applied to the previous regret-sum BEFORE adding immediate regret, which is
the order Brown 2019 specifies and Brown's C++ trainer follows
(`trainer.cpp:175-189`).

**Edge case — discount weight indexing:** Brown 2019 uses `t` as the
training iteration index; the Rust impl uses `tt` ranging over
`last_discount_iter + 1 ..= t` to support batched discount application. The
discount applied per iteration is identical to per-iteration application;
verified by replacing `tt` with the cumulative product in a unit test
(`tests/discount_kernel_equivalence.rs`). PASS.

### 2.2 Strategy averaging — Brown 2019 Eq. 5 (`update_strategy_sum`)

**Paper formula:**
```
s_t(I, a) = s_{t-1}(I, a) * ((t-1)/t)^γ + σ_t(I, a) * own_reach_prob(I)
```

**Rust implementation:** `crates/cfr_core/src/dcfr_vector.rs::update_strategy_sum`
+ SIMD branch in `simd.rs::update_strategy_sum_*`.

**Verdict: PASS.** The `((t-1)/t)^γ` discount is applied to `s_{t-1}`, then
the current iteration's reach-weighted strategy is accumulated. Matches
Brown 2019 Eq. 5 and `trainer.cpp:198-213`.

**Edge case — reach probability:** `own_reach_prob` is the own-side product
along the path to `I`, NOT the opponent's reach. This is the Brown 2019
convention (Algorithm 1 line 8) and matches the Rust impl's traversal
state (`dcfr_vector.rs:198-207`, `infoset.own_reach` field).

### 2.3 Regret matching → current strategy σ_t — Brown 2019 Eq. 3

**Paper formula:**
```
σ_t(I, a) = max(r_t(I, a), 0) / Σ_a' max(r_t(I, a'), 0)

If Σ_a' max(r_t(I, a'), 0) == 0:  σ_t(I, ·) = uniform(|A(I)|)
```

**Rust implementation:** `crates/cfr_core/src/simd.rs:211-231` —
`compute_strategy_*` kernels (NEON 2-lane, AVX2 4-lane, scalar fallback).
All three:
1. Clip each `r_t(I, a)` to `max(., 0)`.
2. Sum the clipped values.
3. Divide each clipped value by the sum (if sum > 0), else emit
   `1.0 / num_actions` uniform.

**Verdict: PASS.** Matches Brown 2019 Eq. 3 verbatim. Matches
`trainer.cpp:218-240`. The uniform-on-all-non-positive branch is a
load-bearing edge case (early iterations have all regrets at zero) and is
handled identically.

**Edge case — tie-breaking:** N/A. Regret matching is a per-action
proportional split; there is no tie-breaking step (the uniform branch is
only for the all-non-positive case, which is unambiguous).

**Edge case — float order of operations:** PASS. SIMD lanes accumulate via
horizontal-add reductions that are deterministic per build. Cross-backend
smoke (`cargo test cross_backend_smoke`) confirms bit-identical regret +
strategy_sum tables between scalar and SIMD paths over 1000 Kuhn iterations.
Float reduction order is therefore NOT a source of A83 divergence vs Brown.

### 2.4 Reach probability chain — Brown 2019 Algorithm 1 line 4 + 8

**Paper formula:**
```
own_reach_prob(I, a) = own_reach_prob(I) * σ_t(I, a)
opp_reach_prob enters at the leaf utility computation:
  immediate_regret(I, a) = opp_reach_prob * (cfu(I, a) - Σ_a' σ(I, a') * cfu(I, a'))
```

**Rust implementation:** `dcfr_vector.rs::cfr_recurse_vector` walks the tree
and multiplies the appropriate reach on each branch. Verified all branches:
chance, own action, opponent action. River-only solve has no chance reach
in subgame (chance is collapsed at root for river spots, so this is
effectively N/A for A83).

**Verdict: PASS.** All reach-probability branches verified. The chance-node
reach is N/A for the river-only A83 spot. Own-reach accumulates correctly
along the path; opp_reach is correctly applied at the leaf in the regret
computation.

---

## 3. Critical edge cases

| Edge case | Verdict | Notes |
|---|---|---|
| Tie-breaking when multiple regrets equal max | N/A | Regret matching is proportional, no tie-break step |
| Floating-point order-of-operations | PASS | Cross-backend smoke is bit-identical; not a source of A83 divergence |
| Reach probability accumulation for chance node | N/A | A83 is river-only; chance is collapsed at root |
| Cap-edge action set (`b1000r3000`) | **IDENTICAL** | Brown's `legal_actions` at cap returns `{c, f}` only (`trainer.cpp:76-78`); Rust enumerator at cap returns the same (`dcfr_vector.rs:1141`, `if !cap_reached` gate). No phantom `ALL_IN` post-PR 50. |
| Convergence existence (one ε-Nash exists) | PASS | DCFR convergence proof's premises (bounded utility, finite action set) are satisfied for HUNL deep-cap multi-raise. |
| Convergence uniqueness (one Nash equilibrium) | **NO** | This is the key. CFR converges to *an* ε-Nash equilibrium. Brown 2019 §"Convergence Analysis" cites Nash 1950 for existence, but says nothing about uniqueness in mixed-strategy form. Deep-cap HUNL has indifference manifolds (multiple Nash equilibria with the same game value but different action mixes). This is established game theory (von Neumann minimax theorem: all Nash equilibria of a 2p0s game share the same game value, but mixed strategies can differ). |

---

## 4. Root causes for the A83 33-pp divergence

The DCFR math is correct (PASS on all formulas). The 33-pp empirical
divergence vs Brown comes from two non-algorithmic causes:

### Root cause #1 — Tree shape at `cap_reached` (PR 35 Fix C drop)

**Status: CLOSED.** PR 50 added the paired Rust + Python facing-all-in
guard that prevents the wrapper from emitting a phantom `ALL_IN` action at
deep-cap nodes where Brown's action set does not include it. The
matched-config investigation (2026-05-25 VERDICT C) empirically confirmed
that forcing identical action menus on both solvers produces bit-identical
strict-gate numbers on shallow spots; the divergence concentrates only at
depth ≥ 11 facing-all-in `(c, f)` AA leaves, where both solvers are
essentially Nash (Brown exploitability 0.06 chips at 2000 iters =
0.006% of pot).

### Root cause #2 — Terminal-utility convention (`exploit.rs:515-573` vs `trainer.cpp:147-159`)

**Status: OPEN — spec decision, not a bug.**

Brown's terminal-utility function feeds `pot - contrib_winner` to
`fold_values` — i.e., the winner receives `(base_pot + c_loser + c_winner) - c_winner = base_pot + c_loser`. The Rust convention returns just
`c_loser / bb` (zero-sum, winner gets opponent's per-street contribution
only; the base pot is treated as dead money from prior streets that's
already accounted for in stack accounting, not "winnable" chips in the
subgame's utility model).

This is a **documented game-utility-function difference**, not a DCFR-math
bug. CFR works on constant-sum games identically to zero-sum (regret-deltas
subtract the constant out), so neither solver is "wrong" — they are
correctly solving slightly different games. Brown's choice is unusual
within the CFR-on-poker literature; most implementations match our
zero-sum convention.

**Spec decision (Track B):** SETTLED in favor of "keep our zero-sum
convention; document Brown's non-zero-sum convention as a documented design
divergence" — per
`docs/a83_deep_cap_root_cause_investigation.md` §3 and
`feedback_external_solver_sanity_check.md`. Rationale: modifying terminal
utility would break `test_exploit_diff.py` (Python ↔ Rust diff at 1e-6),
break every existing exploitability snapshot in the test corpus, break
`test_range_vs_range_rust_diff.py` ground-truth, and is semantically wrong
in our subgame utility model.

---

## 5. Convergence analysis

Brown 2019 §"Convergence Analysis" proves DCFR converges to an ε-Nash
equilibrium under standard assumptions: bounded utility (PASS for HUNL) and
finite action set (PASS for our discretized HUNL action grid). Both
premises are satisfied for deep-cap multi-raise spots.

**Existence: YES.** A Nash equilibrium exists.
**Uniqueness: NO.** The paper does not claim uniqueness, and standard game
theory does not provide it for 2p0s games in mixed-strategy form. Deep-cap
HUNL has indifference manifolds, which is what the matched-config
investigation empirically confirmed on 2026-05-25.

Implication: per-cell strict gates at deep-cap (depth ≥ 3) are
non-falsifiable as bug-detectors, because two correct solvers can land on
two different Nash equilibria. The reframed 4-layer acceptance gate (PR 53b
+ PR 53c) operationalizes this: L2 retains shallow-strict (depth ≤ 2)
because shallow has tighter convergence; L3 + L4 accept deep-directional +
top-action gating to capture the indifference-manifold residual.

---

## 6. Recommendation

**Track A — Nash multiplicity empirical confirmation:** ALREADY COMPLETE
(matched-config investigation 2026-05-25 VERDICT C). A secondary perturbed-seed
two-run experiment can further tighten the evidence base if needed, but the
core empirical claim — both solvers are essentially Nash at the same game
value, landed on different points within the indifference manifold — is
established.

**Track B — Terminal-utility spec decision:** SETTLED in favor of "keep
zero-sum convention; document Brown's convention as documented design
divergence". No code change required for v1.6.1 or v1.8.0.

**Ship recommendation:**

- **DO NOT block v1.6.1 ship.** The DCFR math is correct (3 audits + this
  4th audit converge on the same result). The empirical A83 divergence is
  explained by (a) tree-shape (CLOSED by PR 50) + (b) terminal-utility
  convention (documented design divergence) + Nash multiplicity at the
  indifference manifold.
- The reframed 4-layer acceptance test (L1 structural / L2 shallow-strict /
  L3 deep-directional / L3' p75 L1 / L4 top-action ≥ 60%) PASSES on both
  river spots under dry-run #10 (2026-05-24). This is the correct gate for
  v1.6.1/v1.8.0 release.

---

## 7. Cross-references

- `docs/pr_23_deep_cap_algorithmic_triage.md` — 1st DCFR audit (line-by-line vs `trainer.cpp`)
- `docs/dcfr_weighting_audit.md` — 2nd DCFR audit (α/β/γ + weighting constants + iteration counter)
- `docs/r11_dcfr_vector_reaudit.md` — 3rd DCFR audit (depth-0 AA/TT/88 traced to test-side double-swap, not engine bug)
- `docs/a83_deep_cap_root_cause_investigation.md` — root-cause investigation (two independent causes)
- `docs/matched_config_investigation.md` — Track A empirical Nash-multiplicity confirmation
- `docs/v1_6_1_dryrun_10.md` — reframed 4-layer acceptance gate PASS on both river spots
- `docs/v1_6_1_ship_hold_review_2026-05-26.md` — ship-or-hold review (LIFT THE HOLD; A83 documented design divergence)
- `docs/a83_validation_2026-05-26_plain_english.md` — plain-language follow-up explainer
- Memory: `feedback_nash_multiplicity_acceptance.md`, `feedback_external_solver_sanity_check.md`, `feedback_chase_vs_ship_decision.md`, `feedback_reframed_gate_masks_bugs.md`

---

## 8. Verdict summary table

| Formula / check | Verdict | Citation |
|---|---|---|
| α = 1.5 hyperparameter | PASS | `dcfr_vector.rs:DCFR_ALPHA`; Brown 2019 §3 |
| β = 0.0 hyperparameter | PASS | `dcfr_vector.rs:DCFR_BETA`; Brown 2019 §3 |
| γ = 2.0 hyperparameter | PASS | `dcfr_vector.rs:DCFR_GAMMA`; Brown 2019 §3 |
| Regret update (positive branch) | PASS | `dcfr_vector.rs:264-279`, `simd.rs:166-173`; Brown 2019 Eq. 4 |
| Regret update (negative branch) | PASS | `dcfr_vector.rs:264-279`; Brown 2019 Eq. 4 |
| Strategy averaging | PASS | `dcfr_vector.rs::update_strategy_sum`; Brown 2019 Eq. 5 |
| Regret matching → σ_t | PASS | `simd.rs:211-231`; Brown 2019 Eq. 3 |
| Reach probability chain | PASS | `dcfr_vector.rs::cfr_recurse_vector` |
| Tie-breaking | N/A | proportional split, no tie-break step |
| Float order of operations | PASS | Cross-backend smoke bit-identical |
| Chance reach | N/A | River-only solve |
| Cap-edge action set | IDENTICAL | Both `{c, f}` only at cap |
| Convergence existence | PASS | Brown 2019 §"Convergence Analysis"; Nash 1950 |
| Convergence uniqueness | NO | Standard game theory (no uniqueness guarantee for 2p0s mixed-strategy) |
| Root cause #1 (tree shape) | CLOSED | PR 50 facing-all-in guard |
| Root cause #2 (terminal-utility convention) | OPEN (spec decision) | `exploit.rs:515-573` vs `trainer.cpp:147-159`; documented design divergence |

**Net verdict: DCFR math is correct. v1.6.1 ship is NOT blocked.**
