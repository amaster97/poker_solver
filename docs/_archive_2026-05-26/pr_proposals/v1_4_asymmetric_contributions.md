# v1.4 Proposal — Asymmetric Initial Contributions (Facing-Bet Subgames)

**Status:** Design doc / not yet implemented
**Discovered by:** v1.3.1 S4 re-test (`docs/pr13_prep/v1_3_1_s4_retest.md`)
**Author:** orchestrator
**Date:** 2026-05-23

---

## 1. Problem Statement

`HUNLPoker.initial_state` does not honor asymmetric `initial_contributions` for postflop subgames. The postflop branch at `poker_solver/hunl.py:260-282` reads `contributions = cfg.initial_contributions` (line 260) but hardcodes `to_call=0` (line 277) and `cur_player=1` (line 267) regardless of whether one player has more chips in. Passing `initial_contributions=(1000, 500)` to model "P0 bet half-pot, P1 faces the c-bet" produces an engine state where both players see `to_call=0` and P1 is treated as opening, not defending.

As a SECONDARY issue, certain asymmetric configs (`(1000, 500)` plus a full DCFR solve, per the S4 re-test) **segfault** rather than raising a Python-level error. Type-B engine robustness gap independent of the main feature.

**Persona impact (Pio-parity blocker).** Three persona workflows are structurally unsolvable until this is fixed:

- **W3.4 (Daniel)** — MDF check: BB defends >= 66.7% vs half-pot c-bet. Defender-facing-bet is the entire workflow.
- **W2.3 (Sarah)** — "KK on Q-high flop vs villain's c-bet range." Requires facing a c-bet.
- **W1.2 (Marcus)** — "Villain bet pot on river. JJ on As Tc 5d Jh 8s. Was calling right?" Bluff-catcher MDF.

Count: **3 of the documented persona workflows are blocked** by this single engine limitation. The S4 re-test classified it as "a v1.4+ feature, not a v1.3.1 regression"; this proposal makes it concrete.

## 2. Design

### Fix A — Honor `initial_contributions` in `HUNLPoker.initial_state`

Replace the hardcoded postflop branch (`hunl.py:260-282`) with derivation:

- `to_call = max(contributions) - min(contributions)` (currently hardcoded 0 at line 277).
- `cur_player` = the player with the lower contribution (i.e., the player facing the bet) when `to_call > 0`. Today line 267 sets `cur_player = 1` unconditionally. With asymmetric contributions the facing-bet player is `0` if `contributions[0] < contributions[1]`, else `1`.
- `street_aggressor` should be the player with the higher contribution when `to_call > 0` (today line 275 hardcodes `-1`).
- Symmetric `(500, 500)` continues to yield `to_call=0`, `cur_player=1`, `street_aggressor=-1` — i.e., the existing tests stay unchanged.

Affected only postflop subgame construction. Preflop branch (lines 234-259) already derives `to_call` correctly from blinds and remains untouched.

Estimate: **1-2 days** including unit tests.

### Fix B — Graceful Error on Invalid Configs

Extend `HUNLConfig.__post_init__` (lines 124-149) to catch the configurations that today crash the Rust backend:

- Negative contributions.
- A contribution exceeding `starting_stack` (player would start with negative behind).
- Asymmetric contributions where the "facing-bet" player has zero stack behind (already all-in by construction with chips still owed — nonsensical).

Raise `ValueError` with a message naming the offending field. Goal is **graceful error, not segfault.**

Estimate: **0.5 days.**

## 3. Test Plan

Add `tests/test_asymmetric_contributions.py`:

1. **Symmetric baseline (regression).** `(500, 500)` -> `to_call=0`, `cur_player=1`. Confirms no existing test breaks.
2. **P1 faces bet.** `(1000, 500)` -> `to_call=500`, `cur_player=1`, `street_aggressor=0`.
3. **P0 faces bet (probe / 3-bet pot).** `(500, 1000)` -> `to_call=500`, `cur_player=0`, `street_aggressor=1`.
4. **Invalid: negative.** `(-100, 500)` -> `ValueError`, not segfault.
5. **Invalid: exceeds stack.** Contribution > `starting_stack` -> `ValueError`.
6. **Phase 2b W3.4 re-test (post-Fix A).** BB-defends-vs-half-pot-c-bet should now yield defense in `[55%, 80%]`. Pre-fix this returns the opening strategy from the S4 re-test (`fold=0.000, call=0.000`).

## 4. Acceptance Gates

- W3.4 MDF check produces defense in `[55%, 80%]` (was structurally impossible before).
- W2.3 "KK on Q-high vs c-bet range" yields a sensible mixed fold/call/raise strategy.
- W1.2 bluff-catcher MDF produces non-degenerate call frequency.
- No segfaults on any reasonable input (including the invalid configs above).
- Diff tests vs v1.3.x stay green for **symmetric** baselines (tiny subgame, S1-S3 spots).
- All existing tests pass.

## 5. Versioning

- **v1.4.0** if bundled with node-locking (combined MINOR release; both target Daniel persona).
- **v1.3.3 PATCH** if shipped standalone (no API change; just enables previously-blocked workflows).
- **Recommendation: v1.4.0 bundled.** Node-locking and facing-bet subgames are the two hard prerequisites for Daniel's defender workflows; coupling avoids a half-shipped persona.

## 6. Effort Estimate

| Item       | Days     |
|------------|----------|
| Fix A      | 1.0-2.0  |
| Fix B      | 0.5      |
| Diff tests | 0.5      |
| Audit      | 0.5      |
| **Total**  | **2.5-3.5** |

## 7. Risks

- **Float / int precision.** `to_call` becomes a computed value rather than a constant. Diff tests on symmetric baselines catch any drift through the solver pipeline.
- **Latent engine bugs.** Making `initial_state` aware of asymmetric contributions may surface other postflop assumptions hardcoded around `to_call=0` at construction. The segfault is one example; expect 0-2 more during Fix A implementation.
- **Compatibility.** All existing fixtures (e.g., `default_tiny_subgame`, line 184) use symmetric `(500, 500)`. New derivation must preserve their exact engine states — locked by the regression test in Section 3 case 1.
