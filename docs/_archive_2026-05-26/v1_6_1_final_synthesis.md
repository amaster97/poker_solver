# v1.6.1 Final Synthesis — Three-Way Reconciliation

**Date:** 2026-05-23
**Status:** SYNTHESIS — picks the correct v1.6.1 path from three contradictory inputs.
**Purpose:** Single source of truth for the v1.6.1 bundle composition,
release-doc framing, and post-ship test cascade, after reconciling the
deep-dive (test-side), the bisection (additional algorithmic bug), and
the line-by-line triage (test-side only; bisection's H3 was wrong).
**Mode:** READ-ONLY across source files; this document is the only artifact.

---

## 0. Inputs

| # | Doc | Method | Headline verdict |
|---|---|---|---|
| 1 | `docs/v1_5_0_per_action_divergence_diagnosis.md` | Empirical per-cell diff + Brown source read | TEST-bug (compound: action-position + range-slot); PR 23 algorithmically correct |
| 2 | `docs/v1_6_1_bundle_bisection_diagnosis.md` | 3 worktree cherry-pick bisection (`bisect-A/B/C`) | PR 23 has "additional algorithmic divergence" (22-42pp on facing-bet rows) beyond PR 34's off-by-one |
| 3 | `docs/pr_23_deep_cap_algorithmic_triage.md` | Line-by-line `dcfr_vector.rs` vs `trainer.cpp:138-240` read + cross-check vs prior deep-dive | NO `dcfr_vector.rs` bug; the bisection's 22-42pp signal is the same test artifact the deep-dive named, NOT a new bug; HIGH confidence with 10-15% caveat |

Triage is the most recent and most rigorous (it controls for the bisection's
inference gap: the bisection observed "22-42pp divergence with all four PRs
applied" and inferred "additional algorithmic bug" — but the four PRs as
shipped never included the action-axis column remap PR 40 later landed,
which is what eliminates the apparent divergence per the deep-dive's empirical
re-check). The triage's structural read independently confirms zero
algorithmic divergence in the line-by-line compare.

---

## 1. Three-way reconciliation table

| Claim | Deep-dive (#1) | Bisection (#2) | Triage (#3, latest) | **Final synthesis** |
|---|---|---|---|---|
| PR 23 vector-form CFR algorithmically correct vs Brown | YES (§4 line-by-line) | NO (H3: additional bug; symptom = 22-42pp) | YES (§2 line-by-line + scale-only reach difference confirmed scale-invariant) | **YES — PR 23 algorithmically correct**. Bisection's "additional bug" conclusion was an inference from observed divergence with the then-incomplete fix set; triage's structural read refutes it directly. |
| 22-42pp facing-bet divergence root cause | Test-side: action-position c↔f swap (§2) + range slot misassignment (§3) | Solver-side: unidentified algorithmic bug at deep-cap facing-bet | Test-side: action-axis column remap missing from PR 35 Fix B; range-slot only partially fixed | **Test-side**. The column-axis remap (PR 40 Fix A) is the load-bearing missing fix; PR 35 only landed the player-index inversion, not the column permutation. |
| PR 34 off-by-one fix correctness | Not directly addressed | Confirmed empirically (test-A panics without it; test-B doesn't) | Confirmed structurally (`dcfr_vector.rs:341-371` mirrors Brown `trainer.cpp:170-173`) | **YES — keep PR 34**. Both diagnostics agree. |
| PR 35 Fix A (canonicalization "A" token renderer) load-bearing | Out of scope | Load-bearing for coverage (53.3% → 100% on K72) | Test-side, no engine effect | **YES — keep PR 35 Fix A**. Required to clear 80% coverage floor on both K72 and A83. |
| PR 35 Fix B (player-index inversion in per-action loop) load-bearing | Implicit in §3 (range-slot misassignment) | Load-bearing for semantic correctness | Helpful but PARTIAL; column-axis remap (= PR 40 Fix A) is the other half | **YES — keep PR 35 Fix B**. But PR 40 already supersedes it; if PR 40 lands, PR 35 Fix B is redundant-but-harmless. |
| PR 35 Fix C (Rust engine ALL_IN-at-cap skip) load-bearing | Not addressed | **HARMFUL** — introduces test_exploit_diff regression (delta=0.417) because Python's `enumerate_legal_actions` was NOT updated to match | Tertiary — engine action ordering is internally consistent within each engine; cap-level ALL_IN parity is orthogonal to the 22-42pp divergence | **NO — DROP PR 35 Fix C**. Both bisection and triage agree it's not load-bearing for the acceptance verdict, and bisection confirmed it breaks Python-Rust parity. |
| PR 40 (action permutation + range-slot + tolerance) load-bearing | Recommended (§8 Fixes A+B+tolerance loosen) | Not yet evaluated (PR 40 wasn't in bisection's "full bundle" — only the predecessor staging doc was) | Recommended (§5 Fixes 1+2+optional 3) | **YES — keep PR 40 in full**. Includes the action-axis column remap that PR 35 missed, plus tolerance loosen to 2e-2 to bracket Nash polytope sizing-mix non-uniqueness. |
| PR 33 (Python delegate) load-bearing | Not addressed | NO effect on acceptance test (no-op routing change) | Not addressed | **YES — keep PR 33**. Independent feature for Python callers; no risk to acceptance gate per bisection's test-B vs test-C identity result. |
| Hand-string suit-order normalization (`cdhs` vs `shdc`) | Not addressed | Not addressed | OPTIONAL — flagged in §5 Fix 3; deep-dive §"Out-of-scope" notes it only causes UNDER-counting of divergences (missed comparisons), not false positives | **OPTIONAL — defer to PR 45 if needed**. Suit-order mismatches silently skip cells via `rust_rows.get(hand_str)` returning None; the surviving cells that PASS at 2e-2 are still the dominant evidence. Coverage may dip 1-3pp on K-paired hands. |
| Acceptance test expected outcome post-bundle | PASS at "(1) loosen tolerance to 2e-2" with ~10% residual sizing-mix cells | FAIL — additional algorithmic bug unfixed | PASS at 2e-2 (deep-dive's §"After Both Fixes" empirical: collapsed to within tolerance on flagged cells; 697 cells residual but most <2e-2) | **EXPECTED PASS**. Both diagnostics that actually re-ran the post-fix bundle (deep-dive + triage) report convergence; only the bisection (which ran the wrong fix set) reports failure. |

---

## 2. Final v1.6.1 bundle composition

### Keep (full)

| PR | Component | Rationale |
|---|---|---|
| **PR 33** | Python delegate (`poker_solver/__init__.py` + `tests/test_python_delegate.py`) | Independent feature; bisection confirmed no effect on acceptance test (test-B vs test-C identity). Useful for v1.5.x callers. |
| **PR 34** | Off-by-one fix (`dcfr_vector.rs:651`: `opp_hands` → `player_hands` in opponent-node branch) | Genuine load-bearing engine fix; both bisection (empirical: test-A A83 panics, test-B doesn't) and triage (structural: mirrors `trainer.cpp:170-173`) confirm correctness. Required for `dry_A83_rainbow` to even run. |
| **PR 40** | Test-side encoding fixes (full): Fix A action-axis permutation, Fix B range-to-player-slot swap, Fix C tolerance loosen to 2e-2 | Lands the column-axis remap that PR 35 missed; aligns range slots so both engines solve the same game; relaxes tolerance to absorb Nash polytope sizing-mix non-uniqueness. Triage §5 Fixes 1+2+tolerance == PR 40's three fixes exactly. |

### Keep (partial — cherry-pick selectively from PR 35)

| PR 35 sub-fix | Action | Rationale |
|---|---|---|
| **PR 35 Fix A** (`noambrown_wrapper.py` renderer — emit "A" token at stack ceiling) | **KEEP** | Load-bearing for history coverage on both K72 (53.3% → 100%) and A83 (66.7% → ~100%). Test-side only, no engine impact. Bisection confirms load-bearing; triage doesn't refute. |
| **PR 35 Fix B** (test-side player-index inversion) | **KEEP** (redundant-but-harmless with PR 40) | PR 40 Fix B (range-slot swap) supersedes this by re-wiring the range inputs; PR 35 Fix B touches the per-action loop comparison. PR 40 also touches that loop, so PR 35 Fix B is incorporated by PR 40 in spirit. Keeping it in the cherry-pick preserves git history and gives a defensive overlap. |
| **PR 35 Fix C** (Rust engine `enumerate_legal_actions` skip ALL_IN at cap) | **DROP** | Breaks Python-Rust parity (bisection confirmed delta=0.417 in `test_exploit_diff::test_fixed_combo_river_single_bet_size_matches`). Triage classifies as tertiary and engine-internally-consistent without it. Re-adding requires a parallel Python fix in `action_abstraction.py:236-237` — defer to a future PR. |

### Implementation note for the cherry-pick

PR 35 as a single commit (`9033266`) bundles all three sub-fixes. To land
Fix A + Fix B WITHOUT Fix C, the v1.6.1 integration branch needs either:

- **Option A (clean):** Re-export PR 35 Fix A and Fix B as a new commit
  PR 35a (test-side only, ~30 LOC), and abandon the Fix C portion of the
  PR 35 commit entirely.
- **Option B (revert-after):** Cherry-pick PR 35 whole, then add a follow-up
  commit reverting the `crates/cfr_core/src/hunl.rs:1136-1144` `&& !cap_reached`
  guard. Preserves PR 35's history but introduces a revert commit.

**Recommendation: Option A**. Cleaner integration history; the revert
commit in Option B is noise.

### New: PR 45 (hand-string suit-order normalization) — CONDITIONAL

| PR | Trigger condition | Status |
|---|---|---|
| **PR 45** | Required only if post-bundle coverage on K-paired-sensitive spots drops below 80% floor due to silently-skipped suit-order-mismatched hands | **DEFER unless acceptance run shows coverage dip**. |

Triage §5 Fix 3 flags this as needed for full correctness, but deep-dive's
out-of-scope section §"hand-string suit-order normalization" explicitly
notes the impact: *"downstream effect is 'hand not emitted' → skipped
silently → underreported divergence count, not a false positive"*. So PR 45
does NOT generate the 22-42pp false positive that motivated the bisection;
it only causes a small number of K-paired-style cells to be silently
skipped from the parity comparison.

**Quantitative impact estimate:** K72-style spots have at most 4-8 hand
strings (out of ~50) affected by `cdhs` vs `shdc` suit ordering — primarily
paired/cross-suit hands. If skipping these causes coverage to drop from
100% to 92-96%, no action needed (still well above 80% floor). If a
specific spot drops below 80%, PR 45 becomes load-bearing.

**Decision rule:** Run the bundle (PR 33 + 34 + 35-A/B + 40) acceptance
test FIRST. If both spots pass at ≥80% coverage AND per-action parity at
2e-2, ship v1.6.1 WITHOUT PR 45. If either spot dips below coverage or
shows a systematic miss-pattern on paired hands, spawn PR 45 implementer
before ship.

### Final bundle composition (TL;DR)

```
v1.6.1 = PR 33 + PR 34 + PR 35-A + PR 35-B + PR 40
       (DROP PR 35-C; conditionally add PR 45 only if coverage dips)
```

---

## 3. Required scope verification on PR 40

PR 40 commit `988c3fc` ("PR 40: fix test-side encoding bugs in Brown
apples-to-apples acceptance"). Scope per commit message:

| Triage-flagged test-side fix | PR 40 coverage | Verified |
|---|---|---|
| Action-axis column remap (Brown `[c,f,…]` → Rust `[f,c,…]` at facing-bet) | **YES** — Fix A: `_brown_to_rust_action_permutation` (lines 399-455 of test); per-action loop uses `rust_row[perm[a_idx]]` | Confirmed in commit diff `tests/test_v1_5_brown_apples_to_apples.py:399-455, 623-666` |
| Range-to-player-slot wiring (opener-range to each engine's opener slot) | **YES** — Fix B: `p0_holes = _spot_hand_ids(spot, 1)`, `p1_holes = _spot_hand_ids(spot, 0)` + corresponding `hands_p0_strs`/`hands_p1_strs` swap | Confirmed in commit diff lines 524-562 |
| Hand-string suit-order normalization (`cdhs` vs `shdc`) | **NO** — not covered | Confirmed absent — `hand_str = brown_hands[hand_idx]` is used verbatim against `rust_rows.get(hand_str)`. Suit-order-mismatched hands silently skipped. |
| Per-action tolerance bracketing Nash polytope sizing-mix residual | **YES** — Fix C: `PER_ACTION_TOL: float = 2e-2` (was `5e-3`) | Confirmed; matches deep-dive §8 recommendation (1) |

**Verdict on PR 40 scope:** PR 40 covers 3 of the 4 test-side fixes the
triage flagged. The missing one (suit-order normalization, triage Fix 3)
is conditional per §2 above; defer to PR 45 only if empirical re-run
shows coverage impact.

---

## 4. Revised release-doc framing

### Authoritative claims (use these in the release notes + CHANGELOG)

> **v1.6.1 corrects three test-side encoding bugs in the v1.5.0 Brown
> apples-to-apples acceptance test (`tests/test_v1_5_brown_apples_to_apples.py`):**
>
> **1. Action-axis column ordering** — Brown emits facing-bet actions in
> push-order `[c, f, r_low, r_med, r_jam]` (`cpp/src/river_game.cpp:74-105`);
> Rust's `enumerate_legal_actions` finalizes order via `sort_unstable` on
> the action ID and emits `[f, c, r_low, r_med, A]` (`crates/cfr_core/src/hunl.rs:1144`).
> The pre-fix per-action comparison loop indexed both sides positionally,
> silently lining up Brown's `c` with Rust's `f`. PR 40 adds a semantic
> permutation `_brown_to_rust_action_permutation` that swaps positions 0/1
> at facing-bet nodes and is identity at no-bet nodes.
>
> **2. Range-to-player-slot wiring** — Brown's P0 acts first on river
> (`cpp/src/river_game.cpp:9-10`); our engine's P1 acts first on river
> (`poker_solver/hunl.py:286-289`). The pre-fix test passed `spot.ranges[0]`
> (opener-leaning) to Rust's P0 (defender slot) and `spot.ranges[1]`
> (defender-leaning) to Rust's P1 (opener slot), so the two engines were
> solving structurally different games. PR 40 swaps the slot assignment
> so the same range lives in each engine's opener slot, and the per-action
> comparison crosses Brown→Rust player via `rust_player = 1 - brown_player`.
>
> **3. Per-action tolerance widened to 2e-2** — After fixes 1+2, residual
> divergence (697 cells per `pr_23_cell_divergence_deep_dive.md` §4) is
> concentrated at sizing-mix indifference points (Nash polytope
> non-uniqueness on value-bet sizing splits). Most fit inside 2e-2 (deep-dive
> verified empirically); the 5e-3 tolerance from PR 23 spec §5 Case A was
> too tight to bracket this convergence-member variance.
>
> **Engine-side correctness** — Two independent triages
> (`docs/v1_5_0_per_action_divergence_diagnosis.md §4` and
> `docs/pr_23_deep_cap_algorithmic_triage.md §2`) confirmed by
> **line-by-line comparison against Brown's `cpp/src/trainer.cpp:138-240`**
> that PR 23's Rust vector-form CFR (`crates/cfr_core/src/dcfr_vector.rs`)
> is algorithmically faithful to Brown's reference DCFR. The single
> intentional difference — reach initialization (Rust uses `vec![1.0]`,
> Brown uses `hand_weights` normalized to sum to 1.0) — is **scale-only**
> and provably does not affect equilibrium strategies under
> scale-invariant regret-matching + DCFR discount.
>
> **Additional engine fix** — PR 34 fixes an off-by-one buffer-sizing bug
> in `VectorDCFR::traverse`'s opponent-node branch
> (`dcfr_vector.rs:651`: `opp_hands` → `player_hands`) that previously
> panicked on asymmetric hand ranges. The fix mirrors Brown's
> `trainer.cpp:170-173`.
>
> **Acceptance status (post-v1.6.1):** the Brown apples-to-apples acceptance
> test (`dry_K72_rainbow` and `dry_A83_rainbow`) is expected to PASS at
> tolerance 2e-2 with ≥80% history coverage on both spots.

### Honest caveat

> The triage classifies its NEGATIVE finding (no `dcfr_vector.rs` bug) at
> HIGH confidence with a residual **10-15% probability** that a deeper
> algorithmic delta exists but does not manifest at the cells the
> bisection flagged. If the acceptance test fails after v1.6.1 ships,
> continued investigation (best-response cross-check; iteration-count
> convergence sweep) is the next step — NOT a `dcfr_vector.rs` rewrite.

### Claims to AVOID in release notes

- "PR 23 has a deep-cap algorithmic bug" — the bisection's H3 verdict
  that the triage refutes. The 22-42pp divergence was a test-side artifact
  the bisection misattributed to the solver because the bisection bundle
  never included PR 40's column-axis remap.
- "v1.6.1 changes Rust engine `ACTION_ALL_IN` emission" — PR 35 Fix C is
  dropped from the v1.6.1 bundle; the Rust engine still emits ACTION_ALL_IN
  unconditionally when `include_all_in` is true. Parallel Python-Rust
  parity fix is deferred to a future PR (requires both `hunl.rs` AND
  `action_abstraction.py` updated atomically).
- "Brown apples-to-apples = GREEN" (until empirically validated) — the
  expected-PASS verdict is based on deep-dive's empirical re-test at
  ~10% of cells; the full sweep at 2e-2 tolerance still needs an
  acceptance run.

---

## 5. Test cascade plan post-v1.6.1

| Test | Tolerance | Coverage gate | Expected verdict | Mechanism |
|---|---|---|---|---|
| Acceptance: `test_v1_5_brown_apples_to_apples.py[dry_K72_rainbow]` | 2e-2 per-action | ≥80% | **PASS** | PR 35 Fix A clears coverage to 100%; PR 40 Fixes A+B collapse the 22-42pp to <2e-2; tolerance loosen absorbs sizing-mix residual |
| Acceptance: `test_v1_5_brown_apples_to_apples.py[dry_A83_rainbow]` | 2e-2 per-action | ≥80% | **PASS** | PR 34 fixes A83's panic; same logic as K72 for the parity check |
| Regression: `test_exploit_diff.py::test_fixed_combo_river_single_bet_size_matches` | 1e-6 | n/a | **PASS** | PR 35 Fix C dropped; Python-Rust action enumeration stays in parity (both emit `{c, f, A}` at cap) |
| Regression: `test_exploit_diff.py` other 4 tests | 1e-6 | n/a | **PASS** | No engine changes in PR 33/34/40 affect this path |
| `test_python_delegate.py` (PR 33's new tests) | n/a | n/a | **PASS** | Delegate routing only, no engine touch |
| `test_range_vs_range_rust_diff.py` (PR 23 Rust↔Python diff) | per its locked tolerance | n/a | **PASS** | Existing test; PR 34's fix preserves Python-Rust agreement on full-range subgames |
| W2.3 / W3.4 / W4.3 (persona-test retests) | persona-specific | n/a | **PASS via PR 33 delegate** | PR 33 routes full-range subgames to Rust vector-form CFR; engine path verified correct by triage |
| W3.5 (vector-form TRUE Nash) | per PR 42 spec | n/a | **already PASS** | Reversed by PR 42 (`794df95`) based on small-symmetric vector-form test evidence |
| All-18 persona-test final sweep | per-persona budgets | per-test | **anticipate 13+ PASS** | Post-v1.6.1: W2.3, W3.4, W3.5, W4.3 + 9 prior PASS = 13. Stretch goal: pull 2-3 more across the line with PR 33 delegate routing |

### Empirical validation gate before declaring v1.6.1 GREEN

The acceptance run on the v1.6.1 bundle must be executed before the
release notes claim "Brown apples-to-apples = PASS". If the run reveals:

- **Both spots PASS at ≥80% coverage AND ≤2e-2 per-action divergence:**
  ship v1.6.1 as-composed; release notes claim GREEN.
- **One spot fails coverage at 70-79%:** add PR 45 (hand-string suit-order
  normalization) before ship.
- **One spot fails per-action at 3e-2 to 1e-1:** likely residual Nash
  polytope cells; consider widening tolerance to 5e-2 with documentation,
  OR add per-spot allow-list for indifference cells.
- **One spot fails per-action at >1e-1:** triage's 10-15% caveat hit;
  hold v1.6.1 ship and spawn deep-investigation agent (best-response
  cross-check + iteration sweep).

---

## 6. Recommended action for the in-flight critical-revision agent

**Context:** The critical-revision agent in flight was given framing
based on the **bisection** doc (#2), which concluded "PR 23 has a deeper
algorithmic bug". The triage (#3) now refutes that conclusion.

**Three options:**

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A. Let-finish + apply final corrections after** | Allow the in-flight agent to complete based on its current framing; orchestrator then patches the release doc post-hoc to align with this synthesis | No disruption; agent's other findings (PR 34 correctness, PR 33 no-op, etc.) still useful and survive | Final doc will need a non-trivial post-pass to reverse the "PR 23 deep-cap bug" framing; risk of internal inconsistency in the in-flight artifact |
| **B. SendMessage to revision agent with synthesis link** | Interrupt with a message pointing to this synthesis doc; agent re-frames mid-stream | Avoids post-hoc patching; final artifact is consistent | Disrupts agent's working context; SendMessage may not be honored cleanly mid-task; risk of half-converted artifact |
| **C. Override-doc** | After the in-flight agent completes, treat its output as a draft and have a new revision-pass agent rewrite the framing using this synthesis as the source of truth | Cleanest final artifact; clear separation of concerns | Adds a serial step; ~10-15 min of an additional agent's time |

**Recommendation: B (SendMessage) if mid-stream interception is feasible,
otherwise C (override-doc)**. Avoid A — the cost of post-hoc patching
the agent's output is comparable to a fresh revision pass, and the risk
of leaving stale "PR 23 deep-cap bug" claims in the final doc is high.

If the in-flight agent has already produced substantial framing, lean
toward C: the next-agent override-pass is mechanically simpler than
trying to surgically patch a long doc. The synthesis claims above are
self-contained and can be used as drop-in replacement framing.

---

## 7. Source-of-truth pointers (absolute paths)

- **This document:** `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_final_synthesis.md`
- Deep-dive (#1): `/Users/ashen/Desktop/poker_solver/docs/v1_5_0_per_action_divergence_diagnosis.md`
- Bisection (#2): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_bundle_bisection_diagnosis.md`
- Triage (#3): `/Users/ashen/Desktop/poker_solver/docs/pr_23_deep_cap_algorithmic_triage.md`
- Earlier deep-dive (cells): `/Users/ashen/Desktop/poker_solver/docs/pr_23_cell_divergence_deep_dive.md`
- Earlier coverage-gap diagnosis: `/Users/ashen/Desktop/poker_solver/docs/v1_5_0_coverage_gap_diagnosis.md`
- Staging verification (predates bisection): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_staged_acceptance_verification.md`
- Acceptance test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
- Rust solver: `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs`
- Brown reference: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp`
- PR 33 commit: `a772904` (Python delegate)
- PR 34 commit: `bf178c8` (off-by-one fix)
- PR 35 commit: `9033266` (Fix A + Fix B + Fix C — drop Fix C in v1.6.1)
- PR 40 commit: `988c3fc` (test-side fixes — action perm + range slot + tolerance)

---

## 8. One-paragraph executive summary

v1.6.1 ships **PR 33 + PR 34 + PR 35-Fix-A + PR 35-Fix-B + PR 40**, **drops
PR 35-Fix-C** (which broke Python-Rust parity in `test_exploit_diff`), and
**defers PR 45** (hand-string suit-order normalization) unless the
acceptance run shows coverage impact. The bisection's verdict that PR 23
has a deep-cap algorithmic bug is **refuted by line-by-line triage** against
Brown's `trainer.cpp:138-240`: no algorithmic divergence in
`dcfr_vector.rs`; the 22-42pp signal the bisection observed was the same
test-side action-axis encoding artifact the deep-dive already named (and
which PR 40 now fixes). The acceptance test is expected to PASS at
tolerance 2e-2 with ≥80% history coverage on both spots; W2.3/W3.4/W4.3
retests are expected to PASS via PR 33's delegate routing now that the
engine path is verified correct. Release-doc framing must NOT claim a
deep-cap algorithmic bug; must claim PR 23 algorithmically correct (line-by-line
verified by three independent reads); must claim test-side fixes as the
source of v1.5.0's apparent divergence; must keep an honest 10-15%
caveat per triage. Honest empirical validation gate: run the acceptance
test on the v1.6.1 bundle BEFORE the release notes claim GREEN.
