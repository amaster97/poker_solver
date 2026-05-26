# Terminal-Utility Arbitration — 2026-05-26

**Mode:** ARBITRATION between Position A (the empirical audit at
`docs/terminal_utility_audit_2026-05-26.md` — "convention divergence
exists, behaves like a bug if Brown is the spec") and Position B (the
3rd-pass DCFR validator at `docs/a83_validation_2026-05-26.md` — "DCFR
math is correct; terminal-utility convention is a settled design
choice").

**Trigger:** Position A and Position B reach different framings of the
same empirical fact (Brown awards `base_pot + c_loser` at win-leaves;
Rust/Python award only `c_loser/bb`). Decide whether the Rust/Python
terminal-utility code constitutes a BUG vs. an internally-consistent
convention choice, and whether v1.6.1 / v1.8.0 ship is blocked.

**Mandate:** Resolve the framing contradiction. If "NOT A BUG," document
the mechanism precisely (so a future audit doesn't relitigate it) and
identify any caveat conditions that could break the equivalence.

---

## TL;DR

**VERDICT: NOT A BUG.** Position B is upheld for the Brown
apples-to-apples comparison path AND for all production codepaths
inside the engine + UI. Position A's empirical observation (Brown
includes `base_pot` in winner payoff; Rust/Python do not) is true at
file:line, but the framing of "this causes a strategy bias that doesn't
cancel" missed the seed-split equivalence: when `initial_contributions`
is set to `(base_pot/2, base_pot/2)`, the Rust/Python convention
becomes equivalent to Brown's convention up to a uniform additive
constant per-terminal, which cancels at the regret-delta step.

**Mechanism (precise):**

- Brown's per-terminal value to player P, in chips, is
  `Brown_P(terminal) = win_indicator × (base_pot + c_loser_brown) +
  lose_indicator × (−c_self_brown)` where `c_brown` starts at 0 in the
  Brown subgame (`river_game.cpp:14-15`) and accumulates only this
  street's bets.
- Rust/Python per-terminal value to player P, in chips (after `× bb`
  scaling), is `Rust_P(terminal) = win_indicator × c_loser_rust +
  lose_indicator × (−c_self_rust)` where `c_rust = initial_contribution
  + bet_this_street`. The Rust value is identical to Brown's *if*
  `initial_contribution = base_pot / 2` for both players — because then
  `c_rust = base_pot/2 + bet` and the per-terminal difference becomes:
  - Win-leaf: `Rust = base_pot/2 + bet_loser`, `Brown = base_pot +
    bet_loser` → delta = `+base_pot/2`.
  - Lose-leaf: `Rust = −(base_pot/2 + bet_self)`, `Brown = −bet_self` →
    delta = `+base_pot/2`.
  - Tie-leaf: both `0` in Rust (after split); `(base_pot)/2` in Brown
    (after split) → delta = `+base_pot/2`.
- The delta is the same `+base_pot/2` constant at EVERY terminal,
  regardless of which player wins or loses or ties. A uniform constant
  added to every terminal utility cancels exactly at the
  regret-difference step (`regret_a = util_a − Σ_a' π(a') util_a'` —
  the constant lifts both `util_a` and the mixed average by the same
  amount). Therefore the Nash equilibrium is unchanged.

**Position A's "won-leaf only" observation was correct at the audit
abstraction (it compared zero-contrib Rust to Brown's full payoff). It
becomes a NO-OP once the seed-split is applied at the call site, which
is exactly what `_build_rust_config_for_spot` does in
`tests/test_v1_5_brown_apples_to_apples.py:356`.**

**Caveat (the only failure mode):** the equivalence requires the
seed-split to be applied. If a codepath sets a nonzero `initial_pot`
but `initial_contributions = (0, 0)` (the documented "dead-money
subgame" semantics in `poker_solver/hunl.py:168-176`), the per-terminal
delta vs. Brown is no longer uniform — winner gets `+base_pot` more
under Brown's convention but loser is unaffected. For such a path, the
strategy would be biased toward win-leaves in Brown's solve vs. our
solve. This is mathematically what Position A described.

**Caveat-clearing grep (see §3 below): NO production codepath uses the
dead-money form.** All `(0, 0)` dead-money instantiations are either
(a) test-only negative tests that never reach terminal utility, or (b)
internal Python↔Rust diff fixtures where both tiers use the same
convention (the comparison is mutually consistent regardless of Brown).
The arbitration's verdict (NOT A BUG) is **unconditionally confirmed
for production**. Test-only fixtures with `(0, 0)` semantics document
an intentional "dead-money subgame" model that is internally
consistent and not used in any Brown-comparison gate.

---

## 1. How the contradiction was settled

Position A (`docs/terminal_utility_audit_2026-05-26.md`) correctly
identified that, at the abstraction layer it audited (Rust
`terminal_utility` vs. Brown `vector_eval.cpp`), the formulas differ
by `+base_pot` on the winner side, `0` on the loser side. The audit
documented this as an asymmetric (non-cancelling) constant offset and
concluded that the per-iteration regret-delta has a non-zero bias term
`base_pot × (P_win_a − P_win_s)`.

Position B (`docs/a83_validation_2026-05-26.md`) verified DCFR math
correctness across α/β/γ, regret update, strategy averaging, regret
matching, and reach probability — all PASS — and classified the
terminal-utility convention as a settled spec decision (Track B
SETTLED).

The reconciliation: Position A's audit was performed at the
`terminal_utility` function level WITHOUT considering the upstream
`initial_contributions` seed. Once the seed-split
`initial_contributions=(base_pot/2, base_pot/2)` is taken into account
— which is what every Brown apples-to-apples test call site applies
(`tests/test_v1_5_brown_apples_to_apples.py:356`) — the per-terminal
delta becomes a uniform `+base_pot/2` constant added to BOTH the win
side and the lose side. Constants cancel at the regret-difference step
(this is the trivial CFR identity: regret = util − E[util]; constants
add to both terms and cancel). Therefore the resulting Nash equilibria
are mathematically identical.

The remaining 33pp A83 divergence is NOT explained by terminal-utility
convention. Per matched-config investigation (VERDICT C, 2026-05-25),
both solvers are essentially Nash at the same game value but landed on
different points within an indifference manifold. **Nash multiplicity
remains the leading hypothesis** for the A83 33pp residual. Track A
(regret-init-noise probe in worktree `pr-90-regret-init-noise`) is
still in flight to provide a secondary perturbed-seed two-run
confirmation.

`docs/a83_deep_cap_root_cause_investigation.md` §2 Candidate (d)
describes the terminal-utility divergence as a "convention quirk" that
biases regret-delta by `base_pot × ΔP_win`. That description is
mathematically inconsistent with the seed-split equivalence proven
above — it should be marked as superseded by this arbitration. (Doc
correction is queued as a follow-up task; this arbitration does not
itself amend that doc.)

---

## 2. Mechanism — concrete verification

Subgame entry: `base_pot = 1000`, `bb = 100`, both players seeded with
`initial_contributions[i] = 500`. P0 bets 200, P1 folds. P0 wins.

**Rust `HUNLState::utility` (`crates/cfr_core/src/hunl.rs:485-516`):**
`contributions = [700, 500]` (P0's 500 seed + 200 bet, P1's 500 seed +
0 bet). P1 folded, so `utility = (c_1/bb, -c_1/bb) = (5.0, -5.0)`.
In chips: `(500, -500)`.

**Brown's analogue:** `base_pot = 1000`, Brown's subgame contributions
`(200, 0)` (start at 0 in `river_game.cpp:14-15`; only this street's
chips). P1 folds. Brown awards P0 `pot - contrib_0 = (1000 + 200 + 0)
- 200 = 1000`; P1 gets `-0 = 0`. Brown values in chips: `(1000, 0)`.

**Per-terminal delta:**
- P0: Brown gives `1000`, Rust gives `500` → delta = `+500` for P0.
- P1: Brown gives `0`, Rust gives `-500` → delta = `+500` for P1.

Uniform `+500` (= `+base_pot/2`) shift across both players, at this
terminal. Every other terminal in the subgame has the same uniform
shift (the winner gets `+base_pot/2` more under Brown; the loser gets
`+base_pot/2` more under Brown because Rust pays them `-(base_pot/2
+bet)` while Brown only pays them `-bet`). The shift is GLOBAL across
the subgame's terminal nodes and CANCELS at the regret-delta step.

Verified arithmetically: this matches a constant additive offset to
the entire game tree's leaf values, which has zero effect on the
optimal mixed strategy. The Nash equilibrium is preserved.

---

## 3. Caveat-clearing grep — codepath audit

The seed-split equivalence holds if and only if every codepath that
sets `initial_pot > 0` also sets `initial_contributions` summing to
`initial_pot` (and equal halves for the symmetric case, or matched-
asymmetric for facing-bet subgames).

**Greps executed (2026-05-26):**

```
grep -rn "initial_pot\s*[:=]\s*[1-9]" crates/ poker_solver/ ui/ tests/
grep -rn "HUNLConfig\|initial_pot.*initial_contributions" crates/ poker_solver/ ui/ tests/
```

**Result (by category):**

### 3.1 Production codepaths — ALL CLEAN (seed-split applied)

- `poker_solver/cli.py:124-127` — `initial_pot = 2 * big_blind`,
  contributions implicitly `(bb, bb)` via subsequent construction.
  COMPLIANT.
- `ui/state.py:511-512` — `initial_pot = 2 * bb_blind_cents;
  initial_contributions = (bb_blind_cents, bb_blind_cents)`. COMPLIANT.
- `crates/cfr_core/src/hunl.rs:922-927` (`default_tiny_subgame`) —
  `initial_pot=1000, initial_contributions=[500, 500]`. COMPLIANT.
- `crates/cfr_core/src/hunl.rs:1282-1287` — internal test fixture;
  `initial_pot=200, initial_contributions=[100, 100]`. COMPLIANT.
- `crates/cfr_core/src/exploit.rs:1023-1038, 1130-1144` — internal test
  fixtures; both `initial_pot=1000, initial_contributions=[500, 500]`.
  COMPLIANT.
- `crates/cfr_core/src/dcfr_vector.rs:928, 1028` — both
  `initial_pot=1000, initial_contributions=[500, 500]`. COMPLIANT.
- `crates/cfr_core/examples/rvr_bench.rs:39-40` — same. COMPLIANT.
- `poker_solver/hunl.py:353-354` — `initial_pot=1000,
  initial_contributions=(500, 500)`. COMPLIANT.
- `ui/mock_solver_fixtures.py:301-302, 321-322, ..., 522` — every
  `initial_pot` matched by `initial_contributions` summing to it.
  COMPLIANT.

### 3.2 Brown apples-to-apples test — CLEAN (seed-split applied)

- `tests/test_v1_5_brown_apples_to_apples.py:355-356` —
  `initial_pot=pot, initial_contributions=(pot // 2, pot - pot // 2)`.
  COMPLIANT. This is the ONLY codepath that compares Rust against
  Brown's reference output; it correctly applies the seed-split.

### 3.3 Internal test fixtures with dead-money semantics — NON-COMPARISON

The following fixtures use `initial_contributions=(0, 0)` with
`initial_pot > 0`. They invoke the "dead-money subgame" semantics
documented at `poker_solver/hunl.py:168-176`. They are NOT used in any
Brown apples-to-apples comparison; they are internal Python↔Rust diff
fixtures where both Python and Rust apply the same dead-money
convention (i.e., the comparison is mutually consistent):

- `tests/fixtures/hunl_solve_fixtures.py:111, 130, 150` —
  `flop_dry_config`, `flop_full_menu_config`, `monotone_flop_config`.
  Used by `tests/test_hunl_postflop_solve.py:492` and similar
  consumers. These tests verify Python↔Rust diff at 1e-6 and
  exploitability snapshots; both tiers use the same dead-money
  convention so the diff is mathematically consistent. **NOT a
  Brown-comparison codepath.**
- `tests/test_hunl_core.py:202-203` — `initial_pot=200,
  initial_contributions=(0, 0)`. Tests `force_allin_threshold`'s
  `legal_actions` output; never reaches terminal utility. **NOT a
  terminal-utility-evaluating codepath.**
- `tests/test_asymmetric_contributions.py:77-78` —
  `test_symmetric_dead_money_to_call_is_zero`. Tests dead-money
  semantics intentionally; only checks `to_call`, `cur_player`, etc.;
  never reaches terminal. **Intentional documented behavior.**
- `tests/test_hunl_diff.py:295-305` — `initial_pot=200,
  initial_contributions=(0, 0)`. Negative test that expects
  `ValueError`/`RuntimeError` on board-length validation; raises
  before solve. **NOT a terminal-utility-evaluating codepath.**

None of these paths invalidate the arbitration verdict. The internal
diff tests (3.3, hunl_solve_fixtures) DO exercise terminal utility,
but they compare Python to Rust (same convention on both sides), not
Python/Rust to Brown. The terminal-utility convention divergence is
not relevant to these tests' assertions.

### 3.4 Validator-rejected paths

The Python validator at `poker_solver/hunl.py:168-176` explicitly
rejects `initial_contributions` that don't sum to `initial_pot`
*unless* both are zero. The only ways to land at a terminal-utility
mismatch with Brown's convention are:

1. Use `initial_contributions=(0, 0)` with `initial_pot > 0` (dead-
   money mode). Compliant per validator; used only in tests 3.3.
2. Use matched-sum `initial_contributions` (symmetric or asymmetric).
   Validator-required for the non-zero case. This is the seed-split
   path; all production and Brown-comparison codepaths comply.

### 3.5 Caveat verdict — CLEARED

**No dead-money path exists in any production codepath or any Brown-
comparison gate.** The arbitrator's caveat is satisfied. The
arbitration's "NOT A BUG" verdict is unconditionally confirmed.

The test-only dead-money fixtures are intentionally documented under
the "dead-money subgame" semantic model (per
`poker_solver/hunl.py:168-176`). They exist for Python↔Rust internal
consistency tests and for `force_allin_threshold` /
`legal_actions`-only unit tests. None of them invalidate the
equivalence with Brown for any path that actually compares to Brown.

---

## 4. Cross-references

- `docs/terminal_utility_audit_2026-05-26.md` — Position A (empirical
  audit; correct at the abstraction it audited, but did not include
  the seed-split upstream).
- `docs/a83_validation_2026-05-26.md` — Position B (3rd-pass DCFR
  math validation; classified terminal-utility convention as settled
  design choice).
- `docs/a83_deep_cap_root_cause_investigation.md` — contains a
  description of the terminal-utility "convention quirk" as biasing
  regret-delta by `base_pot × ΔP_win`. This description is
  mathematically inconsistent with the seed-split equivalence proven
  above. **Marked as needing supersede banner** — task #20 follow-up.
- `tests/test_v1_5_brown_apples_to_apples.py:334-361` — the canonical
  Brown comparison codepath; applies the seed-split correctly.
- `poker_solver/hunl.py:168-176` — the validator that enforces the
  sum-match invariant or the (0, 0) dead-money exception.
- `feedback_nash_multiplicity_acceptance.md` — established the
  Nash-multiplicity framing for deep-cap divergence; remains the
  leading hypothesis for the A83 33pp residual after terminal-utility
  convention is exonerated.
- `docs/matched_config_investigation.md` — VERDICT C empirical Nash-
  multiplicity confirmation.

---

## 5. Recommendation

1. **v1.6.1 / v1.8.0 ship is UNBLOCKED** on the terminal-utility
   question. The convention difference is mathematically equivalent
   under the seed-split that every Brown-comparison codepath applies.
2. **`docs/a83_deep_cap_root_cause_investigation.md` needs a supersede
   banner** at §2 Candidate (d) directing readers to this arbitration
   doc for the corrected mechanism. Task #20 follow-up; the user
   approves the banner before it lands.
3. **The 33pp A83 gap cause remains UNKNOWN.** Nash multiplicity is
   still the leading hypothesis (matched-config VERDICT C provides
   empirical evidence). Track A — the regret-init-noise probe in
   worktree `pr-90-regret-init-noise` — is still in flight to provide
   a secondary perturbed-seed two-run confirmation.
4. **No code change required** for v1.6.1, v1.8.0, or any in-flight
   PR. The seed-split is already correctly applied at the only
   call site that needs it (the Brown apples-to-apples test).
