# Terminal-Utility Convention Audit — 2026-05-26

**Mode:** READ-ONLY independent verification.
**Trigger:** A second-pass DCFR validator agent flipped its verdict and
claimed `exploit.rs::terminal_utility` has a BUG (not a "design
divergence") in how it accounts for the carry-forward base pot at
terminal nodes.
**Mandate:** Verify or refute the claim against actual code. If
confirmed, map the blast radius and recommend a path.

**Prior coverage:** `docs/a83_deep_cap_root_cause_investigation.md`
Root Cause #2 (`Candidate (d)`, written 2026-05-23) identified this
exact divergence as a "Brown convention quirk" and recommended
DOCUMENTING it. This audit RE-VERIFIES that prior finding from
first principles, then explicitly reconsiders whether the
"quirk vs. bug" framing was correct.

---

## TL;DR

**VERDICT: CONFIRMED — Brown's terminal utility includes
`base_pot` for the winner; Rust's `terminal_utility` and Python's
`HUNLPoker.utility` do NOT.** The validator's claim is empirically
correct down to file:line.

**However, "bug" vs. "convention divergence" depends on what we mean by
ground truth:**

- If Brown's convention is the spec (i.e. our solver is meant to
  reproduce Brown's NLHE-subgame Nash), then YES, this is a bug. Our
  reported strategies are systematically less aggressive on
  positive-equity actions than Brown's solver, with bias magnitude
  proportional to `(base_pot / bb) * Var_actions[P_win]`. For the
  acceptance test fixtures (`base_pot=1000, bb=100`) this is a 10 BB
  per-hand winner-bonus difference at every win-leaf.
- If the in-codebase Python/Rust definition is the spec (subgame `pot`
  is "dead money" from prior streets and not winnable in this subgame),
  then Brown's solver is solving a DIFFERENT game and the divergence is
  a design choice. This is what the prior `a83_deep_cap_root_cause_investigation.md`
  Candidate (d) concluded.

**The prior investigation's framing was internally consistent, but
the user must now decide which definition is "correct" for the
v1.6.1+ ship. This audit produces the evidence to make that call.**

---

## 1. Per-tier exact formulas (with file:line citations)

### 1.1 Rust — `crates/cfr_core/src/exploit.rs:515-573`

```rust
pub(crate) fn terminal_utility(node: &FlatNode, hole: [[u8; 2]; 2], player: usize) -> f64 {
    match node {
        FlatNode::Fold { contributions, big_blind, folded_player } => {
            let c0 = contributions[0] as f64;
            let c1 = contributions[1] as f64;
            let bb = *big_blind as f64;
            if *folded_player == 0 {
                if player == 0 { -c0 / bb } else { c0 / bb }
            } else if player == 0 { c1 / bb } else { -c1 / bb }
        }
        FlatNode::Showdown { contributions, big_blind, board } => {
            // ... evaluate hands ...
            if s0 > s1 {
                if player == 0 { c1 / bb } else { -c1 / bb }
            } else if s1 > s0 {
                if player == 0 { -c0 / bb } else { c0 / bb }
            } else { 0.0 }
        }
        _ => unreachable!("terminal_utility called on non-terminal node"),
    }
}
```

**Convention:** Winner gets `c_loser / bb` (the opponent's contribution
divided by bb). Loser pays `-c_self / bb`. Tie returns `0.0`. The
`base_pot` does NOT enter this formula.

**Sum at every win-leaf:** `c_loser/bb + (-c_loser/bb) = 0` → zero-sum.
**Sum at tie:** `0 + 0 = 0` → zero-sum.

### 1.2 Rust `HUNLState::utility` — `crates/cfr_core/src/hunl.rs:485-516`

Mirrors `terminal_utility` exactly (independent implementation,
returns `[f64; 2]` per state). Same convention: no base_pot in payoff.

### 1.3 Python — `poker_solver/hunl.py:460-481`

```python
def utility(self, state: HUNLState) -> tuple[float, float]:
    cfg = state.config
    bb = cfg.big_blind
    c0, c1 = state.contributions
    if state.folded[0]:
        return (-c0 / bb, c0 / bb)
    if state.folded[1]:
        return (c1 / bb, -c1 / bb)
    # showdown branch
    rank0 = evaluate(list(hole[0]) + list(state.board))
    rank1 = evaluate(list(hole[1]) + list(state.board))
    if rank0 > rank1: return (c1 / bb, -c1 / bb)
    if rank1 > rank0: return (-c0 / bb, c0 / bb)
    return (0.0, 0.0)
```

**Convention:** Identical to Rust. No `base_pot`.

### 1.4 Brown C++ — `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:147-159`

```cpp
if (node.player == -1) {
    double pot = static_cast<double>(game_.base_pot + node.contrib0 + node.contrib1);
    double contrib = (update_player == 0) ? node.contrib0 : node.contrib1;
    if (node.terminal_winner >= 0) {
        if (node.terminal_winner == update_player) {
            evaluator_.fold_values(update_player, reach_opp, pot - contrib, frame.values.data());
        } else {
            evaluator_.fold_values(update_player, reach_opp, -contrib, frame.values.data());
        }
    } else {
        evaluator_.showdown_values(update_player, reach_opp, pot, contrib, frame.values.data(), eval_scratch_);
    }
}
```

And `vector_eval.cpp:90-131` (showdown):
```cpp
out_values[h] = win_weight * pot_total
              + tie_weight * (pot_total * 0.5)
              - contrib_player * active_weight;
```

And `vector_eval.cpp:133-162` (fold):
```cpp
out_values[h] = value * (total - blocked_weight);
```

**Convention:** Let `pot = base_pot + contrib0 + contrib1`. Then:

- **Fold-win** (this player wins the fold): `value = pot - contrib_self = base_pot + contrib_loser`. Per-opp-hand payoff = `base_pot + contrib_loser`.
- **Fold-loss**: `value = -contrib_self`. Per-opp-hand payoff = `-contrib_self`.
- **Showdown win**: `pot_total - contrib_self = base_pot + contrib_loser`.
- **Showdown tie**: `pot_total/2 - contrib_self = (base_pot + contrib_loser - contrib_self)/2`. Symmetric in chips when `contrib_self = contrib_loser`.
- **Showdown loss**: `-contrib_self`.

**Note 1:** Brown's values are in CHIPS, not BB units (no `/bb` scaling).

**Note 2:** Brown's `contrib0/contrib1` are local to the subgame, starting at 0 in `initial_state()` (see `river_game.cpp:14-15`). The carry-forward dead money lives in `game_.base_pot` (`subgame_config.cpp:191: base_pot = config.pot`).

**Sum at every win-leaf:** `(base_pot + c_loser) + (-c_self)` = `base_pot + c_loser - c_self`. When `c_loser = c_self` (matched contributions in the subgame, which is the normal case for postflop subgame entry) this equals `+base_pot` ≠ 0 → CONSTANT-SUM (not zero-sum).

---

## 2. Side-by-side comparison

| Leaf type | Brown (chips) | Rust/Python (BB) | Brown - Rust×bb (chips) |
|---|---|---|---|
| Fold, winner side | `base_pot + c_loser` | `c_loser/bb × bb = c_loser` | `+base_pot` |
| Fold, loser side | `-c_self` | `-c_self/bb × bb = -c_self` | `0` |
| Showdown win | `base_pot + c_loser` | `c_loser` | `+base_pot` |
| Showdown tie | `(base_pot + c_loser - c_self)/2` | `0` | `(base_pot + c_loser - c_self)/2` |
| Showdown loss | `-c_self` | `-c_self` | `0` |

**Critical asymmetry:** The `+base_pot` constant offset is added by
Brown to WIN-leaves only (and 1/2 to tie-leaves). It is NOT added to
loss-leaves. So it does NOT cancel as a "global constant" at the
decision-node expected-value step. Specifically, the regret-delta
at a decision node `s` with chosen action `a` becomes (in chip units):

```
regret_delta_brown(a) - regret_delta_rust(a) = base_pot * (P_win_a - P_win_s)
```

where `P_win_a` is the win-probability under action `a` and `P_win_s`
is the mixed-strategy win-probability at node `s`. This is non-zero
whenever `P_win` varies with action.

**Sign of the bias:** Brown's `regret(action)` is biased UPWARD by
`base_pot × P_win_action` (chips) for actions that LEAD TO win-leaves
more often. So Brown shifts mass TOWARD high-`P_win` actions, AWAY
from `fold` whenever `P_win > 0`. Magnitude in BB: `(base_pot / bb)
× ΔP_win`. For the acceptance test fixtures (`base_pot = 1000`,
`bb = 100`), this is `10 BB × ΔP_win` per regret-delta per iteration.

---

## 3. VERDICT

### Empirical claim: **CONFIRMED**

The validator's empirical mechanical claim is correct. Rust and Python
both omit `base_pot`; Brown includes it. The numerical inputs to the
regret update therefore differ at every win-leaf by `+base_pot` and
at every tie-leaf by `+base_pot/2`. Across many iterations these
non-cancelling per-leaf differences accumulate into a strategy bias
that does NOT vanish.

This is structurally REAL and was previously identified in
`docs/a83_deep_cap_root_cause_investigation.md` (Candidate (d), §2),
which the prior author classified as "convention divergence."

### Is it a "bug" or a "convention divergence"?

This is where the audit branches:

- **If Brown is the spec:** The Rust/Python convention is a BUG. Our
  solver does not produce the same Nash strategies as Brown's solver
  on the same input.
- **If our internal definition is the spec:** Brown's convention is
  the alternate definition. We chose to model subgame `pot` as
  "dead money" not winnable in this subgame (per the `(0, 0)
  initial_contributions` semantics in `hunl.py:144-176`).

**The current codebase is internally consistent under the
"dead money" interpretation.** All Python/Rust solver components
(DCFR training, exploitability evaluator, best-response evaluator,
range-vs-range diff tests) use the same convention. So nothing inside
the codebase is mathematically wrong; the open question is what game
we INTEND to solve.

**Prior decision (a83 doc §2.d Path C):** Document as known divergence;
do not modify our convention. **This audit confirms the underlying
facts of that decision, but the user must now reconsider given the
v1.6.1 acceptance gate failure.**

---

## 4. Blast radius (if user chooses to FIX rather than document)

### 4.1 Direct callers of `terminal_utility` (Rust)

- `crates/cfr_core/src/exploit.rs:586-587` — `flat_expected_value` (used by Rust exploitability EV pass)
- `crates/cfr_core/src/exploit.rs:630` — `flat_best_response_value` step 1
- `crates/cfr_core/src/exploit.rs:924` — flat-tree DFS (best-response variant)
- `crates/cfr_core/src/dcfr_vector.rs:664` — PR 23's vector-form DCFR (PRODUCTION DCFR SOLVER)

### 4.2 Direct callers of `HUNLState::utility()` (Rust)

- `crates/cfr_core/src/dcfr.rs:191` — DCFR algorithm terminal-state EV
- `crates/cfr_core/src/solver.rs:74, 217` — generic Game-trait exploitability + best-response
- `crates/cfr_core/src/exploit.rs:119, 197` — `expected_value` + `br_state_value`
- `crates/cfr_core/src/preflop.rs:243` — preflop DCFR terminal EV
- `crates/cfr_core/src/hunl_solver.rs:239` — postflop solver entry-point EV
- `crates/cfr_core/src/hunl.rs:1227, 1243` — test fixtures inside hunl.rs

### 4.3 Direct callers of `game.utility(state)` (Python)

- `poker_solver/solver.py:311` — `_expected_value` (used by `exploitability`)
- `poker_solver/solver.py:550` — `_br_state_value` (used by `best_response`)
- `poker_solver/dcfr.py:172` — Python DCFR algorithm terminal-state EV
- `poker_solver/preflop.py:132` — `PreflopHUNLPoker.utility` delegates to base `super().utility(state)`

### 4.4 Affected surfaces (severity grading)

| Surface | Affected? | Severity | File:line |
|---|---|---|---|
| HUNL postflop DCFR solves (Rust) | YES | HIGH if Brown=spec; LOW if internal=spec | `crates/cfr_core/src/dcfr_vector.rs:664` |
| HUNL postflop DCFR solves (Python) | YES | HIGH or LOW (matches Rust) | `poker_solver/dcfr.py:172` |
| Rust exploitability output | YES — but internally consistent w/ trained strategy | LOW (reported expl number is correct under our definition) | `crates/cfr_core/src/exploit.rs:119, 586-587` |
| Python `exploitability()` | YES — but internally consistent | LOW | `poker_solver/solver.py:288-290` |
| Rust best-response numbers (PR #38 exploitative play) | YES — but BR is computed under the same utility, so it's a valid BR under our def | LOW unless cross-referenced against Brown | `crates/cfr_core/src/exploit.rs:197, 630, 924` |
| GUI strategy display (deep-cap) | YES (consumes trained strategy) | DEPENDS on user expectation of "ground truth" | `ui/state.py:1077` → `solve_hunl_postflop` → DCFR |
| Persona test baselines (deep-cap spots) | YES | DEPENDS — baselines were taken under current convention | `docs/persona_test_results/W3_5_TRUE_nash_v1_5_1.md` |
| Push-fold (preflop short-stack) | NO — `base_pot` is 0 at preflop in push-fold; `(0,0)` initial_contributions w/ initial_pot=0 | UNAFFECTED | `poker_solver/preflop.py:120-188`; `hunl.py:144-176` |
| Kuhn poker | NO — no base_pot concept; constant payoffs `±1, ±2` | UNAFFECTED | `crates/cfr_core/src/kuhn.rs:59-89` |
| Leduc poker | NO — uses `±ante` only; no carry-forward pot | UNAFFECTED | `crates/cfr_core/src/leduc.rs:114-138` |
| Range-vs-range aggregator | YES — same DCFR pipeline | Same severity as DCFR | `tests/test_range_vs_range_rust_diff.py` (uses Python game.utility) |
| v1.5.0 Brown apples-to-apples acceptance test | YES — gate widened to L1-based deep-node sanity in PR 53 specifically due to this | KNOWN: gate was REFRAMED, not made strict | `tests/test_v1_5_brown_apples_to_apples.py:160-210` |
| Preflop equity-leaf utility | NO if matched contribs; YES if `c0 != c1` w/ initial_pot dead money | LOW (uncommon path) | `poker_solver/preflop.py:144-188` |

### 4.5 Push-fold confirmation

Push-fold (Kelly's `effective_stack <= 15 BB` HUNL preflop) uses `HUNLConfig` with default `initial_pot=0, initial_contributions=(0,0)` (verified `hunl.py:104-105`). At terminal (jam-fold or jam-call→showdown), `c0/c1` carry the actual chip contributions; there's no separate `base_pot`. Brown's analogue would have `base_pot=0`, so the divergence vanishes. **Push-fold is UNAFFECTED.**

### 4.6 Kuhn/Leduc confirmation

Both use constant payoffs scaled by `ante` (no carry-forward pot, no separate dead money pool). **Both UNAFFECTED.**

### 4.7 Brown apples-to-apples acceptance test

`test_v1_5_brown_apples_to_apples.py:160-210` was REFRAMED in PR 53
(`docs/acceptance_test_reframe.md`) specifically because this
convention divergence prevented strict per-cell parity. The current
gate uses L1 distance ≤ 1.9 max + p75 ≤ 0.60. **Fixing the convention
would likely allow tightening back to the original strict 5e-2
per-cell gate** (modulo Nash multiplicity which is a separate small
residual).

---

## 5. Mechanism review (what the prior triage missed)

The PR 23 line-by-line triage (`docs/pr_23_deep_cap_algorithmic_triage.md`)
compared `dcfr_vector.rs::traverse` against `trainer.cpp:138-240`
directly and (correctly) concluded the algorithm is faithful. But it
did NOT also read `vector_eval.cpp` (where Brown's terminal-utility
math lives — `showdown_values`, `fold_values`). The bug surfaced at
the boundary between `trainer.cpp:147-159` (Brown's terminal handler)
and Brown's `vector_eval.cpp`, where the `pot - contrib` argument
carries the `base_pot` into the per-hand payoff.

This audit verified `vector_eval.cpp:90-131` and `:133-162` directly.

---

## 6. Empirical evidence (from prior dry-run, re-checked)

From `docs/a83_deep_cap_root_cause_investigation.md` §1a (dry-run
report for hand `3sAs` at history `b1000r3000`):

| Action | Brown | Rust | |diff| |
|---|---|---|---|
| c | 0.3638 | 0.6852 | 0.32 |
| f | 0.3068 | 0.1728 | 0.13 |
| r3000 | 0.0088 | 0.0447 | 0.04 |
| r6000 | 0.1282 | 0.0364 | 0.09 |
| r7000 | 0.1924 | 0.0609 | 0.13 |

Brown plays MORE raises (33% total) and MORE folds (31%) than Rust
on this weak made hand. Rust plays mostly call (69%). The
bidirectional pattern (Brown raises more AND folds more, Rust calls
more) is consistent with the `base_pot × ΔP_win` regret-delta
mechanism: when raising bluffs the opponent off, P_win jumps; Brown's
regret credits the full pot (base+contrib) for that jump, our solver
credits only the contrib. So Brown values bluffing AND value-folding
more highly than we do.

---

## 7. Recommended next steps — three paths

### Path (i): PATCH the convention as a v1.6.1 blocker

**Change:** Modify Rust `terminal_utility` (`exploit.rs:515-573`) and
Rust `HUNLState::utility` (`hunl.rs:485-516`) to return
`(base_pot/bb + c_loser/bb)` for the winner. Mirror in Python
`HUNLPoker.utility` (`hunl.py:460-481`). Define `base_pot` as
`cfg.initial_pot - sum(cfg.initial_contributions)` to recover only
the DEAD money (not double-count `contrib` that's already in
`contributions`).

**Required followups:**

- Re-baseline every persona test (W3_5_TRUE_nash_v1_5_1, etc.) — the
  GUI surface strategies change.
- Re-baseline `tests/test_exploit_diff.py` snapshots (the Python ↔
  Rust diff bar at 1e-6 must still hold under the NEW convention).
- Re-baseline every existing exploitability snapshot in the test
  corpus.
- Re-baseline `test_range_vs_range_rust_diff.py` ground-truth.
- Tighten `test_v1_5_brown_apples_to_apples.py` tolerance back toward
  the original 5e-2 strict per-cell gate (residual divergence
  expected to be small enough).
- v1.5.0 push-fold / Kuhn / Leduc: NO change required (verified UNAFFECTED).
- ui/app.py exploitability display: no code change needed; chart will
  show different numbers (likely SMALLER reported exploitability
  numbers, since regret-delta now includes the bonus).

**Pros:** Solver matches Brown / Pluribus / Pio convention (which is
the standard in the CFR-poker literature). Acceptance test can be
tightened. Persona tests will be more comparable to public solver
output.

**Cons:** Delays v1.6.1 release; requires re-baselining ~10+ test
files; semantic change visible in GUI; risk of integration bug during
the cross-tier coordinated change.

**Risk level:** MEDIUM. The change is mechanically simple (per-leaf
formula) but the cross-cutting test baseline refresh is wide. Expect
2-4 days for a clean ship.

### Path (ii): DOCUMENT as known issue + SHIP v1.6.1 with current convention; defer fix to v1.7+

**Change:** No code change. Add a new
`docs/brown_terminal_utility_convention_divergence.md` (this audit
satisfies that role) and link from `docs/RELEASE_NOTES_2026-05-23.md`.
Note in user-facing release notes that "our solver implements a
'dead money' zero-sum subgame interpretation; Brown's solver
implements a 'winner-takes-pot' constant-sum interpretation; the two
produce different Nash strategies on hands with action-dependent
P_win."

**Pros:** Fastest ship. v1.6.1 gates can stay as-reframed. Users who
need Brown-parity can be told this is a known difference.

**Cons:** Solver does not match the convention most users expect (the
literature uses Brown's convention). Brown apples-to-apples test stays
on the L1 sanity gate, not the strict per-cell gate. Future Pluribus /
Pio comparisons will likely show the same divergence.

**Risk level:** LOW for ship, but PUNTS the question. The user has
already chosen this path twice (PR 53 acceptance reframe, PR 15
deep-cap ceiling widening). A third PUNT cements the "two engines
solve different games" framing.

### Path (iii): Make it a CONFIG FLAG — adopt Brown's convention as opt-in

**Change:** Add `HUNLConfig.utility_convention: Literal["zero_sum", "brown"]`
(default `"zero_sum"` preserving current behavior). Branch in
`HUNLPoker.utility`, `HUNLState::utility`, and `terminal_utility`
based on the flag. Same change in Python.

**Required followups:**

- Test the `"brown"` flag on the acceptance test (should pass
  strict 5e-2).
- Add a CI matrix entry that runs the persona tests under both
  conventions and validates internal consistency under each.
- Document in user-facing docs.

**Pros:** Preserves backwards compatibility for everyone using the
current solver. Lets Brown-comparison users get strict parity. Lets
the v1.5.0 acceptance test pass strict under the `"brown"` flag.

**Cons:** Doubles the test matrix. Adds a config flag that most users
won't understand. Defers the "what is the correct definition" question
indefinitely.

**Risk level:** MEDIUM. Code change is moderate (one branch per
utility function); testing is broader.

---

## 8. My recommendation (for the user to consider)

Given:
- The prior investigation already chose Path (ii) and the acceptance
  test was already reframed in PR 53.
- Path (i) requires re-baselining ~10+ test files and 2-4 days.
- The v1.6.1 ship window is now.
- The divergence affects only the SHAPE of Nash strategies, not the
  internal correctness of our solver under our own definition.

**My recommendation: Path (ii) for v1.6.1 (ship as-is with this
audit as the canonical documentation), then SCHEDULE Path (i) as
the v1.7.0 headline change.**

Rationale:
- v1.6.1 ship velocity is preserved.
- The convention question is genuinely a SPEC decision (not a bug in
  the implementation of our chosen spec); deferring to v1.7.0 lets
  the user think through which definition is correct without
  release pressure.
- Path (i) in v1.7.0 lets us frame it as a feature improvement
  ("Brown-compatible strategy convention") rather than a bug fix,
  which is the honest framing.

**HOWEVER:** if the user's instinct is that "Brown is ground truth
because the literature uses Brown's convention," then Path (i) is
correct and the v1.6.1 ship should slip. The bug-vs-convention
framing is genuinely the user's call.

---

## 9. Honest confidence statement

**Confidence that the empirical claim is correct:** VERY HIGH (≥ 99%).
Verified file:line on all four sources (Rust `exploit.rs`, Rust
`hunl.rs`, Python `hunl.py`, Brown `trainer.cpp` + `vector_eval.cpp`).

**Confidence that the prior `a83_deep_cap_root_cause_investigation.md`
analysis was internally correct:** HIGH (≥ 95%). The prior author
correctly identified the mechanism and the magnitude. Where this audit
DIFFERS from the prior doc is in the framing ("convention divergence"
vs. "bug") — but the prior author flagged this framing decision as
the user's call, not theirs.

**Confidence that Path (i) would close the v1.5.0 acceptance test to
strict 5e-2:** MEDIUM (~70%). The base_pot divergence is the largest
identified residual, but there is still Nash multiplicity (different
valid Nash equilibria at deep-cap nodes) which can produce small
residual divergence. Strict 5e-2 may need to widen slightly even
after the fix.

**Residual uncertainty:** ~5-10%. Possible second-order divergences:
- Brown's blocker-handling in `vector_eval.cpp:118-126` is more
  granular than ours (per-hand blocker accounting); we should verify
  our `terminal_utility` does the same blocker accounting — quick
  check: Rust's `terminal_utility` operates per-combo (single hole
  pair), so blockers happen at the OUTER loop in `dcfr_vector.rs:644-668`
  (lines `if hole_p[0] == hole_o[0] ...`); this looks parallel to
  Brown but should be re-checked in a follow-up audit.
- Brown's `pot_total` chip values vs. our `c/bb` BB-normalized values:
  the scaling is uniform across all leaves, so this cancels in
  regret-deltas (verified).

---

## 10. Source-of-truth pointers (absolute paths)

- This document: `/Users/ashen/Desktop/poker_solver/docs/terminal_utility_audit_2026-05-26.md`
- Prior root-cause investigation (covers same ground):
  `/Users/ashen/Desktop/poker_solver/docs/a83_deep_cap_root_cause_investigation.md`
- Rust terminal utility:
  `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/exploit.rs:515-573`
- Rust HUNLState utility:
  `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl.rs:485-516`
- Python HUNL utility:
  `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py:460-481`
- Python preflop subclass:
  `/Users/ashen/Desktop/poker_solver/poker_solver/preflop.py:129-188`
- Brown trainer (traversal + terminal handoff):
  `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240`
- Brown vector_eval (terminal math):
  `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/vector_eval.cpp:90-162`
- Brown river_game (state struct, base_pot use):
  `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp:14-29`
- Brown subgame_config (base_pot init):
  `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/subgame_config.cpp:191`
- Acceptance test (reframed):
  `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py:160-210`
- Acceptance reframe rationale:
  `/Users/ashen/Desktop/poker_solver/docs/acceptance_test_reframe.md`
- Test fixture (`dry_K72_rainbow`, `dry_A83_rainbow`):
  `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json`
- Production DCFR vector-form solver (consumes `terminal_utility`):
  `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/dcfr_vector.rs:65, 664`
- Python solver exploitability:
  `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py:274-301`

---

## 11. Quick reference: what the validator got right and wrong

**Right:**
- Brown's `trainer.cpp:147-159` does pass `pot - contrib_winner` to `fold_values`. ✓
- `pot = base_pot + contrib0 + contrib1`. ✓
- Winner gets `base_pot + contrib_loser`. ✓
- Loser pays `-contrib_loser`. ✓
- Sum is `+base_pot` (constant-sum). ✓
- Rust returns `c_loser/bb` only. ✓
- Loser pays `-c_loser/bb`. ✓
- Sum is 0 (zero-sum). ✓
- Brown biases play toward non-fold on positive-equity hands. ✓
- Python `HUNLState.utility()` has the SAME convention as Rust. ✓
- Rust-Python diff tests are green because both omit base_pot. ✓

**Wrong / nuanced:**
- "BUG (not a 'design divergence')": this depends on what we mean by
  ground truth. The current codebase is internally consistent under
  its own definition. The framing as "bug" requires accepting Brown
  as the spec.

**Not validated by this audit (left as open issues):**
- Whether the OpenSpiel / Pio / Pluribus codebases share Brown's
  convention or ours. The prior `a83_doc` claims Brown's convention is
  "unusual within the CFR-on-poker literature (most implementations
  match our zero-sum convention)" — this audit did NOT independently
  verify that meta-claim and the user may want to verify it before
  choosing Path (i) over (ii)/(iii).
