> ⚠️ **PARTIALLY SUPERSEDED 2026-05-27.** The hold-lift recommendation (A) stands operationally, but the rationale was incomplete: "33pp gap = design-acceptable Nash non-uniqueness" missed that the prior "rust" convention was itself wrong. Brown's convention is now being adopted as the canonical (and only) terminal utility per `feedback_brown_convention_adopt.md`. v1.8.0 will ship with the corrected convention; residual deep-cap divergence (post-convention) is genuine Nash multiplicity testable via EV-of-action invariance, not strategy-prob diff.

# v1.6.1 Engine Bundle — Ship-or-Hold Review (2026-05-26)

**Author:** v1.6.1 ship-hold review agent (read-only audit; ~25 min budget)
**Mode:** READ-ONLY. No code modified, no tag created, no release published.
**Decision rendered:** **Outcome (A) — LIFT THE HOLD**, with one critical
reframing of the ship surface (see §5).

---

## TL;DR

The original v1.6.1 hold rationale was: dry-run #2 (2026-05-23) showed
A83 33pp per-cell divergence at deep-cap; the bisection's H3 ("PR 23
has an additional algorithmic divergence") was empirically supported;
**HOLD v1.6.1 pending deep-investigation agent**.

Since the hold was issued:

1. The deep-investigation completed (`a83_deep_cap_root_cause_investigation.md`)
   and identified **two independent root causes**, neither of which is
   an algorithmic bug in `dcfr_vector.rs`:
   - **Cause (b) — Tree-shape mismatch at `cap_reached` (PR 35 Fix C drop)**.
     Closed by the wrapper-boundary fixes shipped 2026-05-24.
   - **Cause (d) — Brown terminal-utility convention (winner gets `base_pot`)**.
     A **spec divergence**, not a bug. Brown's game is non-zero-sum
     (winner-bonus = `base_pot/bb`); ours is zero-sum. Different Nash
     equilibria on hands with action-varying `P_win`.

2. The DCFR validator (`dcfr_weighting_audit.md`, 2026-05-24)
   confirmed **IDENTICAL** on α/β/γ, `regret_weight`/`avg_weight`,
   iteration counter `t`, sampling scheme, and where opp_reach enters
   the regret update. The 3rd independent audit verdict the task
   refers to: math is correct.

3. The matched-config investigation (`matched_config_investigation.md`,
   2026-05-25 VERDICT C) **empirically confirmed Nash-multiplicity**:
   forcing our solver to use Brown's exact menu produced bit-identical
   strict-gate numbers; the divergence concentrates at depth ≥ 11
   facing-all-in `(c, f)` AA leaves; **Brown exploitability 0.06
   chips at 2000 iters = 0.006% of pot — both solvers are essentially
   Nash, landed on different points within the same indifference
   manifold.** This is the empirical Track A confirmation the task
   anticipated as `~60 min via A83 Track A agent`.

4. Dry-run #10 (2026-05-24) with the corrected 7-PR bundle + reframed
   4-layer acceptance test **PASSED all five gates on both river spots**
   (L1 structural / L2 shallow-strict / L3 max L1 ≤ 1.9 / L3' p75 L1 ≤ 0.60
   / L4 top-action ≥ 60% — actually got 95.2-95.3%).

5. **The v1.6.1 bundle has already shipped piecewise on `origin/main`.**
   Per `v1_7_1_tag_decision_2026-05-26.md`: all 10 bundle PRs landed
   between 2026-05-26 02:32 UTC and 03:02 UTC. No `v1.7.1` tag exists,
   no version bump, no GitHub release. The next coherent release
   boundary is **v1.8.0**, which inherits every v1.6.1/v1.7.1 fix as
   part of its baseline.

**Recommendation (A) with reframing:** the v1.6.1 hold can be — and in
effect, has been — **LIFTED**. But the formal ship surface is no longer
a standalone `v1.7.1` tag; it is the upcoming **v1.8.0** release (PR
#32 Phase 4 SIMD pending). The v1.6.1 fixes are documented in the
v1.8.0 release notes draft as "Engine + parity-wrapper fixes carried
from the v1.7.1 bundle".

The Brown apples-to-apples claim is **NOT** "PASS at strict 5e-2 per-cell"
— it is "PASS at the 4-layer reframed acceptance (L1 structural / L2
shallow-strict / L3 directional L1 ≤ 1.9 / L4 top-action ≥ 60%)" with
documented Nash-multiplicity + terminal-utility-convention residual at
deep-cap.

---

## 1. Original hold rationale (verbatim quote)

From `docs/v1_6_1_dryrun_verification.md` §6 (2026-05-23 late):

> ## 6. Ship verdict: NO-GO
>
> Per synthesis §5 fallback rules:
> - A83 max \|diff\| = 3.3e-1 (much greater than 1e-1 threshold) → "**HOLD v1.6.1 ship and
>   spawn deep-investigation agent (best-response cross-check + iteration sweep)**"
>
> Specific blocker: **A83 deep-cap facing-bet probabilities diverge by up to 33 percentage
> points on bottom-pair-Ace hands at history `b1000r3000`**. This is not Nash polytope
> residual; it indicates a real algorithmic difference between PR 23's Rust vector-form CFR
> and Brown's reference `trainer.cpp:138-209`.

This is the hold condition. The "real algorithmic difference" framing
has since been refuted by three independent investigations + the
matched-config empirical test (§3).

From `docs/a83_deep_cap_root_cause_investigation.md` §6:

> ## 6. What this means for v1.6.1 ship
>
> 1. **DO NOT ship v1.6.1 as-composed.** Both the dry-run and the
>    staging doc confirm acceptance NO-GO.
>
> 2. **Spin a v1.6.2 PR (or absorb into the existing v1.6.1 bundle)**
>    that:
>    - Adds Fix C back (Rust)
>    - Adds the parallel Python fix (`action_abstraction.py`)
>    - Updates `test_exploit_diff.py` if it needs to track the new
>      Python-Rust action set
>    - Widens `test_v1_5_brown_apples_to_apples.py` tolerance to ≥5e-2
>    - Documents the Brown terminal-utility convention divergence

The substantive plan from the root-cause investigation is satisfied by
the **PR 50 + PR 51 + PR 52 + PR 53b + PR 53c + PR 54 + PR 55 + PR 56
+ PR 59 + PR 60** bundle that has already landed on `origin/main`. The
"v1.6.2 PR" the investigation called for is in fact the 10-PR bundle
that shipped as v1.6.1-engine / v1.7.1.

---

## 2. DCFR validator verdict + implications

From `docs/dcfr_weighting_audit.md` §6 (2026-05-24):

> **IDENTICAL** on α/β/γ, on `regret_weight`/`avg_weight`, on iteration
> counter `t` (1-indexed in both), on sampling scheme (full vector-form
> in both), and on where opp_reach enters the regret update (at the
> terminal leaf in both).
>
> **The DCFR weighting hyperparameters and update arithmetic are NOT
> the source of the empirical 22–42pp deep-cap divergence.**

This is the 3rd independent audit converging on the same result:

| Audit | Method | Verdict |
|---|---|---|
| `pr_23_deep_cap_algorithmic_triage.md` | Line-by-line `dcfr_vector.rs` vs `trainer.cpp:138-240` | NO algorithmic bug |
| `a83_deep_cap_root_cause_investigation.md` | Empirical bisection + source read of `vector_eval.cpp` | NO bug in DCFR traversal; divergence is (b) tree-shape + (d) terminal-utility convention |
| `dcfr_weighting_audit.md` | α/β/γ + weighting constants + iter counter + sampling scheme | IDENTICAL math |

A fourth empirical verification is the `r11_dcfr_vector_reaudit.md`
which corroborated the line-by-line conclusion when dry-run #8 surfaced
the depth-0 AA/TT/88 divergence — that was traced to a test-side
double-swap (PR 40 + PR 55-ext stacking), not an engine bug.

**Implication for v1.6.1:** the original hold's premise ("real
algorithmic difference between PR 23's Rust vector-form CFR and Brown")
is **REFUTED**. The DCFR math is correct. The remaining divergence is:

- **Tree shape at `cap_reached`** — closed by PR 50 (paired Rust + Python
  facing-all-in guard, R6 close). Landed as PR #5.
- **Terminal-utility convention** — Brown's non-zero-sum game vs our
  zero-sum game. **Not fixable without changing our utility model**,
  which would break `test_exploit_diff` parity, every exploitability
  snapshot, and our Python-Rust ground truth.
- **Nash multiplicity at deep-cap** — empirically confirmed by
  matched-config investigation 2026-05-25 (both solvers Nash to
  0.006% of pot; landed on different points of same indifference
  manifold).

---

## 3. Track A + Track B status

### Track A (empirical Nash-multiplicity confirmation)

**Status: COMPLETE.** The `matched_config_investigation.md` (2026-05-25
VERDICT C) is the empirical confirmation the task anticipated.

From PLAN.md line 7 (verbatim summary):

> **Matched-config investigation 2026-05-25 VERDICT C**: action menu
> was NOT the explanation for the deep-cap residual — forcing our
> solver to use Brown's exact menu (`force_allin_threshold=0`,
> `min_bet_bb=0`) produced bit-identical strict-gate numbers (80
> violations on K72, 313 on A83); divergence concentrates at depth ≥
> 11 facing-all-in `(c, f)` AA leaves; both solvers are essentially
> Nash (Brown exploitability 0.06 chips at 2000 iters = 0.006% of
> pot); they've landed on different points within the same indifference
> manifold. **Hybrid path framing is empirically confirmed, not
> hand-waved.**

Implications:
- The "wait ~60 min via A83 Track A agent" gate in (B) is **already
  cleared**.
- Nash-multiplicity is the dominant cause of the remaining per-cell
  divergence at deep-cap.
- Terminal-utility convention difference is a contributing cause but
  it is bounded by `base_pot/bb * P_win × max P_win delta` — i.e., it
  scales with hand strength variance across actions, consistent with
  the bidirectional K72-vs-A83 pattern.

### Track B (terminal-utility spec decision)

**Status: SETTLED in favor of "keep our zero-sum convention; document
Brown's non-zero-sum convention as a documented design divergence".**

Rationale (from `a83_deep_cap_root_cause_investigation.md` §3):

> **Why NOT modify our utility to add base_pot**
>
> - Breaks `test_exploit_diff.py` (Python ↔ Rust diff at 1e-6) unless
>   both Python and Rust are updated atomically.
> - Breaks every existing exploitability snapshot in the test corpus.
> - Breaks `test_range_vs_range_rust_diff.py` ground-truth.
> - Semantically wrong: our `initial_pot` represents dead money from
>   prior streets that's already taken from stacks; it's not
>   "winnable" chips in the subgame's utility model.
> - Brown's convention is unusual within the CFR-on-poker literature
>   (most implementations match our zero-sum convention; Brown's choice
>   is a documented quirk specific to his solver).

The Track B decision is captured by:
- `feedback_external_solver_sanity_check.md` (Brown is sanity check,
  not strict ground truth)
- `feedback_nash_multiplicity_acceptance.md` (deep-cap has
  indifference manifolds; strict per-cell is non-falsifiable;
  multi-layer gate required)
- `feedback_reframed_gate_masks_bugs.md` (retain SHALLOW-STRICT layer
  when reframing)

The 4-layer reframed acceptance gate (PR 53b + PR 53c) operationalizes
these decisions: L2 shallow-strict catches actual bugs at depth ≤ 2;
L3/L4 deep-directional accepts Nash-multiplicity + terminal-utility
residual at depth ≥ 3.

---

## 4. v1.6.1 ship status — already landed piecewise

Per `docs/v1_7_1_tag_decision_2026-05-26.md` §"Land status on `origin/main`":

| PR | Bundle slot | Status on `origin/main` | Merged-as SHA | GH PR # |
|---|---|---|---|---|
| 50 | 1 | LANDED | `6c9d7f0b` | #5 |
| 51 | 2 | LANDED (re-opened as PR #16) | `2d7ea585` | #6→#16 |
| 52 | 3 | LANDED | `a2a75bed` | #8 |
| 54 | 4 | LANDED | `9a5c4d44` | #9 |
| 55 | 5 | LANDED | `3af1257a` | #10 |
| 56 | 6 | LANDED | `3899ca60` | #12 |
| 53b | 7 | LANDED | `0aec0a7d` | #14 |
| 53c | 8 | LANDED | `49c14211` | #15 |
| 59 | 9 | LANDED | `1bb699e9` | #18 |
| 60 | 10 | LANDED via PR #22 Guard C supersession | `1fefaff0` | #19→#22 |

**10/10 effectively on `main`.**

What did NOT happen:
- No `v1.7.1` git tag was created.
- No version bump committed (`pyproject.toml` still reads `1.7.0`).
- No GitHub release `v1.7.1` was published.
- The ship script `scripts/ship_v1_7_1.sh` failed 5+ times on smoke
  matrix timeouts; the bundle was instead landed piecewise.

What DID happen post-bundle (which is why a retroactive `v1.7.1` tag
would mislabel):
- PR #21 (v1.7.2 CI release workflow) merged
- PR #22 (CI hardening Guards B + C) merged
- PR #23 (v1.8 Phase 1 SIMD discount kernel) merged
- PR #30, #35, #41, #33 (v1.8 Phase 2/3 SIMD + cross-platform smoke)
- PR #42 (`.dmg` fork-bomb fix, v1.6.0 retroactive pull)

**Per `v1_7_1_tag_decision_2026-05-26.md`: CLOSE v1.7.1 as obsolete;
fold into v1.8.0.**

---

## 5. Recommended decision: **OUTCOME (A) — LIFT THE HOLD**

### Decision

**LIFT THE HOLD on v1.6.1 / v1.7.1.** The math-correctness verdict is
in (DCFR validator 3rd audit + matched-config empirical confirmation).
The A83 divergence is acceptable per Nash-multiplicity +
terminal-utility-convention frameworks. The v1.6.1 engine bundle
(Python delegate + paired cap-guard + tolerance docs + 4-layer reframe)
has shipped piecewise on `origin/main`.

### Reframing

The formal release surface is **v1.8.0**, not a standalone v1.7.1 tag.
This was the decision in `v1_7_1_tag_decision_2026-05-26.md` and
operationalized by `v1_8_0_release_notes_prep_2026-05-26.md`. The
v1.8.0 draft already includes the v1.6.1/v1.7.1 fixes as part of the
"Engine + parity-wrapper fixes carried from the v1.7.1 bundle"
subsection.

### Reasoning

This matches the (A) recommendation criterion in the task spec:

> If v1.6.1 ship was held PURELY on "wait for A83 to resolve" → recommend (A) since math-correctness verdict is now in.

The v1.6.1 hold rationale from the dry-run was "A83 max diff 33pp →
algorithmic bug suspected → HOLD pending deep-investigation". The
deep-investigation completed; the verdict is "no algorithmic bug;
divergence is (b) closed by PR 50 + (d) acceptable convention
difference + Nash multiplicity". The math-correctness verdict is
operationalized by 3 audits + 1 empirical confirmation.

### Re-framing of the "Brown apples-to-apples PASS" claim

The task warned:

> If v1.6.1 release notes were going to claim "Brown apples-to-apples PASS" → that claim is FALSE under current terminal-utility convention; either re-frame the claim (recommend A with reframed notes) or hold (recommend C).

Checking the v1.8.0 release notes draft
(`/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md`
mirrored from `v1_8_0_release_notes_prep_2026-05-26.md` §"Known issues
remaining"):

> - **Deep-cap A83 33-pp bottom-pair-Ace divergence.** The v1.5.0 Brown
>   apples-to-apples acceptance test still reports a 33-percentage-point
>   per-cell divergence at the bottom-pair-Ace cluster on the A83 board
>   in deep-cap (100bb+) settings. Root-cause investigation is in flight
>   (`docs/a83_deep_cap_root_cause_investigation.md`); the v1.6.1 engine
>   bundle remains HELD pending diagnosis. Note: deep-cap multi-action
>   Nash has indifference manifolds, and external reference solvers
>   (Brown, Pluribus) are treated as sanity checks rather than strict
>   ground truth — the divergence may be a design difference rather than
>   a bug.

The v1.8.0 draft does **NOT** claim "Brown apples-to-apples strict PASS";
it acknowledges 33pp per-cell residual as a documented design
difference. **Good.** But two parts of this draft text are now stale
post-decision and should be updated:

- "the v1.6.1 engine bundle remains HELD pending diagnosis" — this is
  no longer accurate; the bundle has shipped piecewise and the hold is
  effectively lifted.
- "Root-cause investigation is in flight" — the investigation
  completed; root causes are (b) closed + (d) documented +
  Nash-multiplicity empirically confirmed.

**Recommended re-framing of the v1.8.0 "Known issues remaining" section
on the A83 entry:**

> - **Deep-cap A83 ≥33-pp bottom-pair-Ace divergence vs Brown reference
>   solver.** The Brown apples-to-apples acceptance test continues to
>   report per-cell strict divergences at the bottom-pair-Ace cluster
>   on the A83 board in deep-cap (100bb+) settings. **Root cause is
>   established as a combination of (a) terminal-utility convention
>   divergence — Brown's solver awards the full pot (including
>   base_pot) to the winner, while our convention is zero-sum (winner
>   receives opponent contribution only); and (b) Nash multiplicity
>   at indifference manifolds in the deep-cap subgame.** Both solvers
>   are essentially Nash (Brown exploitability 0.06 chips at 2000
>   iters = 0.006% of pot; matched-config empirical verification
>   2026-05-25). The Brown apples-to-apples acceptance test now uses
>   a 4-layer reframed gate (structural / shallow-strict /
>   deep-directional / top-action) which PASSES on both river spots
>   for the shipped bundle. The strict per-cell residual is treated
>   as informational; see `docs/a83_deep_cap_root_cause_investigation.md`
>   and `docs/matched_config_investigation.md`.

This re-framing satisfies the task constraint (no FALSE "Brown
apples-to-apples PASS" claim) and accurately reports the shipped
state.

---

## 6. Ship-execution plan

### 6a. Immediate (the v1.6.1 hold is lifted; no ship-execution required)

The v1.6.1 bundle has shipped piecewise. No further action is needed
to "lift the hold" — the hold is empirically lifted by the bundle's
presence on `origin/main`.

### 6b. v1.8.0 ship pipeline (where v1.6.1 fixes will be formally released)

The next coherent release boundary is **v1.8.0**, gated on PR #32
(Phase 4 SIMD compute_strategy). The v1.8.0 release notes draft is at
`docs/v1_8_0_release_notes_DRAFT.md` (mirrored on origin branch
`pr-88-v1.8.0-release-notes-prep`). The ship sequence is:

```bash
# 1. Wait for PR #32 (Phase 4 SIMD) to land on origin/main
gh pr view 32 --json mergedAt

# 2. Update v1.8.0 release notes draft with Phase 4 SHA + date
#    Edit /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md
#    Substitute the 4 TBD placeholders per
#    docs/v1_8_0_release_notes_prep_2026-05-26.md §"TBD fields to fill in at ship time"

# 3. Tag v1.8.0 (NOT in this audit's scope — read-only)
git tag -a v1.8.0 -m "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix"
git push origin v1.8.0

# 4. Publish GitHub release
gh release create v1.8.0 \
  --title "v1.8.0 — Cross-platform SIMD + .dmg fork-bomb fix" \
  --notes-file /Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md
```

### 6c. Recommended pre-tag actions

Before the v1.8.0 tag, the following items should be addressed (these
are documentation-only; none block the ship):

1. **Update `docs/v1_8_0_release_notes_DRAFT.md`** with the reframing
   in §5 above (replace "v1.6.1 engine bundle remains HELD" + "Root
   cause investigation in flight" with the established root-cause +
   reframed-acceptance language).
2. **Confirm CHANGELOG.md alignment** per
   `v1_8_0_release_notes_prep_2026-05-26.md` Open Question #1 — fold
   the v1.7.2 entry into v1.8.0 (Option A) or preserve history
   (Option B); recommend Option A.
3. **Close PR #34** (the earlier v1.8.0 release notes draft superseded
   by `pr-88-v1.8.0-release-notes-prep`) per the same prep doc Open
   Question #2.
4. **Move `scripts/ship_v1_7_1.sh` to `scripts/archive/`** per
   `v1_7_1_tag_decision_2026-05-26.md` §"Action plan" #4.
5. **(OPTIONAL)** Tag `v1.7.1-bundle-shipped` at `49c14211` (PR 53c,
   last bundle merge) as an archeological marker. Per
   `v1_7_1_tag_decision_2026-05-26.md` §"Optional fallback": **defer
   unless the user specifically requests it**. NOT a release tag.

### 6d. Release notes section anchoring (the reframed v1.6.1 chapter)

The v1.8.0 release notes should include a subsection capturing the
v1.6.1/v1.7.1 fixes carried into v1.8.0. Suggested anchor text (to be
inserted into the v1.8.0 draft as a new "Engine + parity-wrapper fixes
carried from the v1.7.1 bundle" subsection):

```markdown
### Engine + parity-wrapper fixes carried from the v1.7.1 bundle

v1.8.0 inherits a 10-PR bundle of engine and parity-wrapper fixes
that landed piecewise on `main` between v1.7.0 and v1.8.0. No formal
v1.7.1 tag was created (per `docs/v1_7_1_tag_decision_2026-05-26.md`);
the fixes are folded into this release.

**Engine correctness:**
- PR 50 (#5) — Phantom `ALL_IN` action menu guard (paired Rust + Python).
  At facing-all-in nodes, the responder's action menu no longer emits a
  degenerate `ALL_IN` raise that would have had no chip distinction
  from calling. Closes R6.
- PR 51/PR #16 — `dcfr_vector.rs` off-by-one + asymmetric-range
  `next_reach` sizing fix; closes the asymmetric-range solve panic.

**Brown parity test harness — wrapper boundary corrections:**
- PR 52 (#8) — Suit-encoding char-to-char fix; replaced a silent
  paired `h ↔ d` swap with explicit mapping. Closes R8.
- PR 55 (#10) — P0/P1 player-index convention swap at the wrapper
  boundary. Closes R9.
- PR 56 (#12) — Hand-string sort-order canonicalization at the
  wrapper boundary. Closes R10.

**Brown parity test harness — renderer + acceptance reframe:**
- PR 54 (#9) — Renderer `stack_ceiling` kwarg + `"A"` token for
  bets/raises at stack ceiling.
- PR 53b (#14) + PR 53c (#15) — Brown apples-to-apples acceptance
  test reframed from strict 5e-2 per-action gate to a 4-layer gate
  (L1 structural / L2 shallow-strict / L3 deep-directional L1 ≤ 1.9
  / L4 top-action ≥ 60%). Codifies that external reference solvers
  are sanity checks, not strict ground truth, when action menus
  differ and deep-cap subgames have indifference manifolds.

**Ship-hardening + CI:**
- PR 59 (#18) — `memory_profiler` golden-file refresh + regen-mode
  flag.
- PR 60-equivalent (folded into PR #22) — `_skip_or_fail()` helper +
  `STRICT_ACCEPTANCE=1` env var: Brown parity test hard-fails on
  missing prereqs in strict mode.

The bundle resolves the 22-42pp Brown apples-to-apples deep-cap
divergence reported in v1.5.0 / v1.5.1 / v1.6.0 dry-runs as a
combination of test-side wrapper bugs (R8/R9/R10), one engine-side
mechanical guard (R6, PR 50), and a documented Brown design
divergence (terminal-utility convention + Nash multiplicity at deep
cap; see Known Issues below).
```

---

## 7. Decision matrix — why (A), not (B) or (C)

| Outcome | Premise | Evidence for | Evidence against | Verdict |
|---|---|---|---|---|
| (A) LIFT THE HOLD | DCFR math correct + Nash-multiplicity acceptable + bundle independent | 3rd audit PASS; matched-config VERDICT C (Nash multiplicity empirically confirmed); dry-run #10 ALL-LAYERS-PASS; bundle already landed | None — the original hold premise is refuted | **CHOSEN** |
| (B) SHIP BUT WAIT FOR TRACK A | Defer until empirical Nash-multiplicity confirmation completes (~60 min) | n/a — task spec contemplates this gate | Track A is **already complete** (matched-config investigation 2026-05-25 VERDICT C); waiting is no-op | NOT APPLICABLE |
| (C) KEEP THE HOLD | Terminal-utility convention is a TRUE spec divergence that needs Track B resolution before ship | n/a — Track B has been settled in favor of "keep zero-sum convention; document Brown's convention as design divergence" | Modifying terminal utility would break `test_exploit_diff`, every exploitability snapshot, ground-truth diff tests; semantically wrong (initial_pot ≠ winnable chips); Brown's convention is unusual | REJECTED |

**The original hold criterion ("wait for A83 to resolve") is satisfied
by the deep-investigation + matched-config + dry-run #10 cascade. The
recommendation per task criterion #1 is (A).**

The reframing criterion ("If v1.6.1 release notes were going to claim
'Brown apples-to-apples PASS' → that claim is FALSE under current
terminal-utility convention; either re-frame the claim (recommend A
with reframed notes) or hold (recommend C)") is satisfied by the
v1.8.0 draft's explicit acknowledgement of the 33pp per-cell residual
+ the 4-layer reframed gate framing. Recommended supplementary text in
§5 above tightens the framing.

---

## 8. Constraints honored

- [x] Read-only audit. No code modified.
- [x] No tag created.
- [x] No release published.
- [x] No push to origin.
- [x] Within ~25 min budget.
- [x] Original hold rationale quoted verbatim from
  `docs/v1_6_1_dryrun_verification.md` §6 + `a83_deep_cap_root_cause_investigation.md` §6.
- [x] DCFR validator verdict + implications captured (§2).
- [x] Track A + Track B status captured (§3).
- [x] Decision recommendation (A) with full reasoning (§5).
- [x] Ship-execution plan (§6) for the v1.8.0 release that subsumes
      v1.7.1 bundle.

---

## 9. Source-of-truth pointers

- This document: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_ship_hold_review_2026-05-26.md`
- v1.6.1 hold trigger: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_verification.md` §6
- A83 root-cause investigation: `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
- DCFR validator (3rd audit): `/Users/ashen/Desktop/poker_solver/docs/dcfr_weighting_audit.md`
- PR 23 deep-cap algorithmic triage: `/Users/ashen/Desktop/poker_solver/docs/pr_23_deep_cap_algorithmic_triage.md`
- R11 dcfr_vector re-audit: `/Users/ashen/Desktop/poker_solver/docs/r11_dcfr_vector_reaudit.md`
- Matched-config empirical confirmation: `/Users/ashen/Desktop/poker_solver/docs/matched_config_investigation.md`
- Dry-run #10 (ALL-LAYERS-PASS): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_10.md`
- v1.7.1 tag decision (CLOSE AS OBSOLETE): `/Users/ashen/Desktop/poker_solver/docs/v1_7_1_tag_decision_2026-05-26.md`
- v1.8.0 release notes prep: `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_prep_2026-05-26.md`
- v1.8.0 release notes draft: `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md`
- v1.6.1 engine ship plan (now superseded): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_engine_ship_plan_final.md`
- v1.6.1 ship script (now obsolete; recommend archive): `/Users/ashen/Desktop/poker_solver/scripts/ship_v1_7_1.sh`
- PLAN.md (lines 3-23 cover v1.7.1/v1.8 status): `/Users/ashen/Desktop/poker_solver/PLAN.md`
- Reframed acceptance gate spec: `/Users/ashen/Desktop/poker_solver/docs/acceptance_test_reframe.md`
- Memory rules referenced: `feedback_chase_vs_ship_decision`, `feedback_nash_multiplicity_acceptance`, `feedback_external_solver_sanity_check`, `feedback_reframed_gate_masks_bugs`
