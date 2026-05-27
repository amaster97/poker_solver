> **STATUS 2026-05-27: SUPERSEDED by PR #78 (convention purge, SHA `37e5be1`).**
> The "two conventions both valid" framing in this doc is RETRACTED. There is exactly ONE
> correct terminal-utility convention (Brown's: winner gets pot + c_loser), and the prior
> "rust" convention was a bug that has been purged. PR #93 (the ablation that prompted this
> reconcile) was closed without merge; its ablation flag is no longer in the codebase.
>
> Post-purge empirical state: v1.5 Brown apples-to-apples PASSES the reframed 4-layer SANITY
> gate on both K72 and A83 fixtures. Per-cell strict max |Δ| residuals (K72 0.852 / A83
> 0.907) reflect genuine Nash multiplicity at deep-cap indifference manifolds; the
> reframed gate is structural+statistical and accepts these.
>
> See: [[brown-convention-adopt]] memory rule; `docs/v1_5_brown_post_purge_numbers_2026-05-27.md`;
> PR #78 merge commit.

# URGENT: A83 status in flux — two empirical findings now contradict the "fully closed" framing

**Created:** 2026-05-26 (post-PR-93-ablation-landing)
**Status:** READ FIRST. A83 33pp deep-cap divergence is NOT settled.
**Branch carrying the new finding (NOT MERGED — for user review):**
`pr-93-terminal-utility-ablation` (commit `986f48d`).
**Results doc on that branch:**
`docs/a83_terminal_utility_ablation_results_2026-05-26.md`.

---

## TL;DR — what changed overnight

The **PR 93 terminal-utility convention ablation** (agent `acebb72f`,
~5+ hour run, completed after the RESUME doc + release notes + morning
checklist were written) returned a verdict that **contradicts** the
arbitrator's algebra and partially contradicts the Nash-multiplicity
framing of PR #68.

**PR 93 verdict:** `CONVENTION-IS-A83-CAUSE`.

- max |Δ| = **12.27pp** on `dry_A83_rainbow` @ 2000 iters.
- max |Δ| = **10.28pp** on `dry_A83_rainbow` @ 8000 iters (persists with more iters).
- max |Δ| = **49.99pp** on `dry_K72_rainbow` @ 2000 and 8000 iters.
- Comparison: **Rust-vs-Rust under the two terminal-utility conventions**, same RNG seed, paired arms.

Pre-registered decision rule from the PR 93 ablation spec: `max |Δ| ≥ 5pp → CONVENTION-IS-A83-CAUSE`.

---

## Why this contradicts the prior framing

### What PR #68 (Nash multiplicity) tested

- Probe: `scripts/a83_nash_multiplicity_probe.py`.
- Controlled variable: **initial regrets** (ε = 1e-9 perturbation).
- Same code, same convention, same seed.
- Verdict: `max |Δ| = 0.998499` on indifference-manifold cells — Nash multiplicity at deep cap.
- Doc: `docs/a83_nash_multiplicity_confirmed_2026-05-26.md`.

### What the arbitrator (NOT-A-BUG) verdict argued

- Doc: `docs/terminal_utility_arbitration_2026-05-26.md`.
- Algebra: at the win-leaf, Brown awards `base_pot + c_loser`; Rust/Python award `c_loser` only. Under seed-split `initial_contributions = (base_pot/2, base_pot/2)`, both arms accumulate the same per-leaf utility plus a **uniform constant offset across all leaves**.
- Claim: the uniform offset is in the **terminal payoff**, so it cancels at the regret-difference step (`r_a - r_avg`) inside DCFR.
- Conclusion: terminal-utility convention is a settled design choice; not a strategy-affecting bug.

### What PR #93 (terminal-utility ablation) tested

- Script: `scripts/a83_terminal_utility_ablation.py`.
- Controlled variable: **terminal-utility convention** (Rust-default vs Brown-style `+base_pot` at winner-take-all leaves), holding initial regrets + seed fixed.
- Verdict: `CONVENTION-IS-A83-CAUSE` — convention alone shifts strategies by 12-50pp.
- Doc: `docs/a83_terminal_utility_ablation_results_2026-05-26.md`.

### The mechanism the arbitrator missed (per PR 93 results doc)

> "While the per-leaf offset IS uniform (+5BB per player at every leaf
> for our fixtures), the regret-update step weights leaves by opp-reach,
> and different actions reach terminals with different total opp-reach,
> so the bonus does NOT cancel across actions."

In other words: the arbitrator's algebra was correct that the
per-leaf offset is **uniform per-leaf**, but the regret update at an
infoset is `Σ_h π_{-i}(h) · u(h, a)` summed over histories `h` leading
to the leaf, weighted by opponent-reach `π_{-i}(h)`. Different
actions `a` reach different sets of terminals with different total
opponent-reach mass, so a uniform per-leaf constant `c` contributes
`c · Σ π_{-i}(h, a)` to each action's regret — and that sum is
**not** identical across actions when the action menu and game tree
are asymmetric (which deep-cap A83 is).

The seed-split equivalence still holds at the per-leaf level (`u_A(h) - u_B(h) = const` for all `h`), but the reach-weighted aggregation at the regret-update step turns the per-leaf constant into an action-dependent offset because the action-conditional reach masses differ.

---

## Reconciliation hypothesis (both could be true simultaneously)

| Probe | Controlled-variable | Result | Likely mechanism |
|---|---|---|---|
| PR #68 (Nash multiplicity) | INIT REGRETS varied; convention + seed fixed | `max \|Δ\| = 0.998499` | Indifference manifold at deep-cap; equilibrium point selected by initial conditions |
| PR #93 (TU ablation) | CONVENTION varied; init regrets + seed fixed | max \|Δ\| = 12-50pp | Reach-weighted aggregation turns per-leaf constant into action-dependent regret offset |

**Both can be real.** They measure different things:
- PR #68 says "given a fixed convention, the equilibrium isn't unique; tiny init perturbations move us within a manifold."
- PR #93 says "the convention itself shifts which equilibrium gets converged to, by 12-50pp on identical seeds."

The 33pp Brown apples-to-apples gap could be a combination — Nash-multiplicity drift on the indifference cells (PR #68) PLUS convention-driven equilibrium selection (PR #93). Relative contributions are not yet decomposed.

The arbitrator's algebra was **insufficient** rather than wrong: it correctly identified the per-leaf constant offset, but the analysis stopped before the regret-update step where opp-reach weighting breaks the cancellation across actions.

---

## What needs user decision

1. **Which framing is canonical for the v1.8.0 release notes "Known issues remaining" entry?**
   - Option A: Nash multiplicity is the dominant explanation (PR #68 framing; current release-notes language).
   - Option B: Terminal-utility convention is the dominant explanation (PR #93 framing).
   - Option C: Both — convention selects an equilibrium region, multiplicity covers the residual within-region drift. (Most honest given current evidence; matches both probe results.)

2. **Does the v1.6.1 hold-lift decision need to be re-opened?**
   - Current state on `origin/main`: HOLD LIFTED, folded into v1.8.0 (via PR #50).
   - The hold-lift rationale was: "33pp gap is design-acceptable Nash non-uniqueness, not a bug."
   - If Option B or C is canonical, the framing changes from "Nash non-uniqueness" to "convention difference + Nash non-uniqueness." This does not necessarily reverse the hold-lift (Brown and Rust still each converge to A valid Nash, and the v1.5 Brown apples-to-apples reframed 4-layer gate still PASSES per Dry-run #10), but the language in `docs/v1_6_1_ship_hold_review_2026-05-26.md` and the v1.8.0 release notes "Known issues remaining" entry was written under Option A and is now premature.
   - User decision: ship v1.8.0 as-is with updated framing, or pause for further investigation?

3. **Should the arbitrator doc (`docs/terminal_utility_arbitration_2026-05-26.md`) be superseded or annotated?**
   - Its algebra is correct at the per-leaf level but did not cover the reach-weighted aggregation. A supersede banner pointing at PR #93 ablation results would close the loop.

4. **Does PR #93 itself merge?**
   - The PR 93 branch carries the new finding + the ablation script + a new convention-toggle flag in `dcfr_vector.rs`. Decision on the branch is held for the user; it has NOT been merged.

---

## What this URGENT doc does NOT do

- It does **not** retract PR #68 or PR #69. PR #68's Nash multiplicity finding remains empirically real (the 1e-9 perturbation result is reproducible). PR #69's ship-blocker hot-patch (silent no-op chance_outcomes path) is unaffected.
- It does **not** invalidate the v1.5 Brown apples-to-apples Dry-run #10 PASS (the reframed 4-layer gate). That gate is structural + statistical, not strict per-action; it passes regardless of which mechanism dominates the 33pp gap.
- It does **not** alter the v1.8 SIMD or `.dmg` fork-bomb fix conclusions; those are independent of A83.

---

## Implication for ship status

- **v1.8.0 release notes "Known issues remaining" entry for A83:** the current language ("EMPIRICALLY CONFIRMED Nash multiplicity is the explanation") is premature. Should be softened to "two empirical mechanisms identified; relative contributions unsettled."
- **v1.6.1 hold-lift decision:** UNDER REVIEW pending user reconciliation. Hold-lift is not auto-reversed but the rationale text in `v1_6_1_ship_hold_review_2026-05-26.md` is now incomplete.
- **Ship sequence (`scripts/release_v1_8_0.sh`):** still operationally ready; whether to invoke depends on user's reconciliation decision.

---

## Pointer set for the morning review

- This doc: `docs/A83_RECONCILE_URGENT_2026-05-26.md` (you are here).
- PR 93 ablation results (NEW): `/Users/ashen/Desktop/poker_solver_worktrees/pr-93-tu-ablation/docs/a83_terminal_utility_ablation_results_2026-05-26.md`.
- PR 93 ablation script (NEW): `/Users/ashen/Desktop/poker_solver_worktrees/pr-93-tu-ablation/scripts/a83_terminal_utility_ablation.py`.
- PR #68 multiplicity confirmation (on main): `docs/a83_nash_multiplicity_confirmed_2026-05-26.md`.
- Arbitrator NOT-A-BUG verdict (on main, possibly stale): `docs/terminal_utility_arbitration_2026-05-26.md`.
- v1.8.0 release notes draft (updated by this PR): `docs/v1_8_0_release_notes_DRAFT.md`.
- v1.6.1 ship-hold review (on main, language now incomplete): `docs/v1_6_1_ship_hold_review_2026-05-26.md`.

---

**Bottom line:** the prior "A83 fully closed" framing on PR #49 RESUME doc + the v1.8.0 release notes draft was **premature**. Two empirical findings now coexist; you have a real (not algebraic) decision to make before the ship sequence runs.
