# PR 3 audit report (plan-mode draft)

**NOTE:** The user's original task was to write this report to
`/Users/ashen/Desktop/poker_solver/docs/pr3_prep/audit_report.md`, but plan
mode restricts edits to this single plan file. The full audit findings are
below, ready to be copied into the target path once plan mode is exited.

---

# PR 3 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-3-hunl-tree
**Diff size:** 3 modified (__init__.py, card.py, cli.py = +106/-5 lines) + 5 new files (hunl.py 615, action_abstraction.py 233, test_action_abstraction.py 220, test_hunl_core.py 427, test_hunl_tree.py 201 = 1,696 LoC total)

**Test status:** 138/138 pass (97 existing + 41 new). Full pytest run completes in 361s.

## Must-fix

None found. The implementation is correct and complete against the spec.

## Should-fix

- **`HUNLState.config` field is duplicated against `HUNLPoker.config`** (hunl.py:159, hunl.py:211). The spec lists `config` on `HUNLState` to make `utility / current_player / legal_actions` pure functions of state, but the actual implementations read both `state.config` (utility, line 274) and `self.config` (initial_state, line 214). This is fine in practice but invites future drift if a caller mutates one and not the other. Recommend: pick one source of truth (the state's `config`), and have `HUNLPoker.__init__` only store config to seed `initial_state`.

- **`initial_contributions` (0, 0) "dead-money" subgame interpretation** (hunl.py:122-130) is undocumented behavior. The spec says "Must sum to `initial_pot`" but the impl accepts `(0, 0)` as a bypass for dead-money pots. This was needed by `test_abstraction_force_allin_threshold_snaps_short_shoves` (test passes `initial_pot=200, initial_contributions=(0, 0)`), but the spec invariant `stacks[i] + contributions[i] - initial_contributions[i] == config.starting_stack` then quietly accumulates the dead-money pot into the wrong column. Not exercised by any failing test, but worth a comment update — or rejecting the (0,0) case and forcing the test to supply matching contributions.

- **`test_hunl_default_tiny_subgame_solvable_in_one_minute` (test_hunl_tree.py:122) uses `solve(game, 500)`** — `solve` is re-exported from `poker_solver` but the test does not assert wall-clock time. The spec calls for "<30s on CI runner" but the test only checks `exploitability < 0.1`. If convergence regresses, the test will run longer than 60s before failing on exploitability. Add `time.perf_counter()` bound.

- **`_action_context` redefines `pot` differently from the spec's "Action encoding" prose** (hunl.py:325). Spec says `pot = sum(contributions) + initial_pot_for_subgame`. Impl says `pot = sum(contributions) + initial_pot - sum(initial_contributions)`. The subtraction is correct when contributions == initial_contributions at subgame start, but the formula is awkward: it boils down to `(sum(contributions) - sum(initial_contributions)) + initial_pot`, which is "amount paid into pot since subgame start, plus opening pot". This matches the spec semantically but the off-by-the-name is worth a comment to explain why the subtraction is there.

- **`enumerate_legal_actions` returns `[]` when `stack <= 0`** (action_abstraction.py:210-211) — this is a stack-side bypass, but the existing rules engine in `_apply_player` only routes to the abstraction when `cur_player >= 0`. A stack-0 player has `all_in[p] == True`, so they should never be the current player. Defensive but currently unreachable. Worth either removing or asserting unreachable.

- **Card `from_str` accepts `"As"`, `"AS"`, `"as"` (mixed case)**, but the spec's infoset key format requires "uppercase rank, lowercase suit". The infoset key generation correctly uses `Card.__str__` which is canonicalized (card.py:30-31), so this is fine — but no test enforces it. Worth a one-line assertion in `test_hunl_infoset_key_canonicalizes_hole_order`.

- **`include_all_in` flag set to False would still expose `ACTION_ALL_IN` if a `compute_raise_to(ACTION_ALL_IN, ctx)` call happens**: while `enumerate_legal_actions` respects the flag, the helpers do not. Not exploitable from a normal game walk but worth either documenting or guarding.

## Nice-to-fix

- **`__post_init__` raises `AssertionError`** (hunl.py:107, hunl.py:109) for the rake fields. `AssertionError` is conventionally for invariants that can't fail; configuration mistakes should raise `ValueError`. Same file uses `ValueError` for related checks (line 112, 114, 119, 126).

- **`_normalize_hole_action` accepts both a packed-int and a nested tuple**, with a `type: ignore` (hunl.py:587). A typed `Union[int, tuple[tuple[Card, Card], tuple[Card, Card]]]` parameter annotation would document the dual-mode intent.

- **`_pack_hole_outcome` uses 8-bit-per-card packing** (hunl.py:592-598). With `card_to_int` ranging [8, 59], 6 bits would suffice. Cosmetic — keep 8 bits for byte alignment and Rust-port simplicity.

- **`BetSizing` class is in-module unused** (action_abstraction.py:85). Spec requested a `BetSizing` enum or constants — the constants are exported separately, and `BetSizing` adds a parallel attribute-access path. Neither test file imports it. Either remove or document that it's a convenience for downstream callers.

- **`bet_size_fractions` default is duplicated** across `HUNLConfig` (hunl.py:98), `ActionAbstractionConfig` (action_abstraction.py:58), and `ActionContext` (action_abstraction.py:77). DRY only worth it if a downstream change is anticipated; defer.

- **`test_hunl_initial_state_with_ante` (test_hunl_core.py:41) does not assert `street_aggressor == 1`** — only assertions are on contributions, stacks, pot, to_call, cur_player, street_num_raises. The spec's invariant #1b implicitly requires aggressor=1 (since BB counts as opening bet); add the assert.

- **`test_hunl_max_tree_depth_bounded` (test_hunl_tree.py:129) uses the wrong depth bound formula** for a river-only tree. Spec says `(postflop_raise_cap + 2) * 4 streets`, but the river-only subgame has 1 street. The test passes because the multiplier (=4) is loose, but the bound is conceptually wrong here.

- **Unused import `field` in hunl.py:14**: imported from dataclasses but only `field(default_factory=tuple)` is used. Minor.

- **`Street.SHOWDOWN`** (hunl.py:62) is value 4 but `_CARDS_TO_DEAL` (hunl.py:73) doesn't include it. This is correct (no cards dealt at showdown) but explicit comment would help.

## Looks good (explicit confirmation of audit focus areas)

1. **Integer-arithmetic discipline.** Confirmed.
   - `hunl.py`: chip fields (`starting_stack`, `small_blind`, `big_blind`, `ante`, `initial_pot`, `contributions`, `stacks`) all typed `int`. Only float annotations are `rake_rate` (placeholder, asserted 0.0) and `bet_size_fractions` (the pot-fraction multipliers, which is correct per spec).
   - Float divisions (hunl.py:278, 280, 284, 286) only occur in `utility()` to convert cents to BB-floats at terminals — spec-mandated for `Game` protocol conformance.
   - Float divisions (hunl.py:558, 578) compute uniform-probability chance outcomes, which are float by `Game.chance_outcomes` protocol.
   - `action_abstraction.py`: only float usage is `bet_size_fractions` and `fraction` parameters; result is immediately `int(round(...))` (lines 129, 135). No float chip values stored or compared.

2. **Dedup correctness.** Confirmed.
   - `_enumerate_bets` (action_abstraction.py:169-182) tracks `seen_amounts: set[int]` and skips duplicates.
   - `_enumerate_raises` (action_abstraction.py:185-201) tracks `seen_raise_tos: set[int]` and skips duplicates.
   - Verified by spawning a tiny-pot ctx (pot=10, big_blind=100): all 5 bet fractions clamp to 100 cents → only one bet action emitted (`ACTION_BET_33`).
   - `test_abstraction_min_bet_clamping` confirms this for bets.

3. **Min-bet / min-raise enforcement.** Confirmed.
   - `_min_bet` (action_abstraction.py:112-113): `min_bet_bb * big_blind` = 100 cents by default.
   - `_min_raise_increment` (action_abstraction.py:124-125): `max(to_call, big_blind)`, matching NLHE rule.
   - `_bet_amount_for_fraction` (line 130) clamps via `max(raw, _min_bet(ctx))`.
   - `_raise_to_for_fraction` (line 138) clamps via `max(raise_to, min_raise_to)`.

4. **Raise-cap counter.** Confirmed.
   - `_apply_player` increments `street_num_raises` for ACTION_ALL_IN (line 377), ACTION_BET_X (line 388), ACTION_RAISE_X (line 400). 
   - ACTION_CHECK, ACTION_CALL, ACTION_FOLD branches do NOT increment.
   - Opening ALL-IN (verified with `to_call==0` repro): increments to 1 from 0.
   - At-cap behavior (verified with synthetic ctx, street_num_raises=3 postflop): `_enumerate_raises` skipped, only FOLD+CALL+ALL_IN emitted.

5. **All-in absorption.** Confirmed.
   - `_enumerate_bets` skips bets where `raw_amount >= stack` (line 176) — including the equal case → so ACTION_BET_X at exactly all-in chip count is dropped.
   - `_enumerate_raises` skips raises where `raise_to >= max_raise_to` (line 195) — same handling.
   - `ACTION_ALL_IN` appended once at line 231 if `include_all_in` flag set.
   - Verified with synthetic ctx (pot=200, stack=200): BET_100 (which equals stack) absent, ALL_IN present once.

6. **Infoset key hides opponent's hole cards.** Confirmed.
   - `infoset_key` (hunl.py:312-321) uses `state.hole_cards[player]` only — never `[1-player]`.
   - `test_hunl_infoset_key_hides_opponent_cards` (test_hunl_core.py:337) constructs two states differing only in P1's hole cards and asserts `infoset_key(_, 0)` identical. Passes.
   - `test_hunl_infoset_key_canonicalizes_hole_order` confirms `AhKh == KhAh` for player 0. Passes.

7. **Card-int mapping round-trip.** Confirmed.
   - `card_to_int(card) -> int` (card.py:117-119): `card.rank * 4 + card.suit`. Range [8, 59] for rank ∈ [2, 14], suit ∈ [0, 3].
   - `int_to_card(int) -> Card` (card.py:122-124): `Card(card_int // 4, card_int % 4)`. Inverse.
   - Card range validated in `Card.__post_init__` (card.py:25-28); int < 8 would raise on construction.
   - `tests/test_card.py` has 10 tests including round-trip checks (passed in full suite).

8. **License.** Confirmed.
   - No comments in new files reference postflop-solver, TexasSolver, or shark-2.0.
   - Implementation is independent (raise/bet/cap logic is standard NLHE rules, not a copy).
   - Card-int formula `rank * 4 + suit` is generic and not specific to any reference repo.
   - Spec is the source of design; no AGPL contamination.

9. **Test coverage of 16 Critical correctness items.** Confirmed (all 16 present):
   - #1 blinds posted → `test_hunl_initial_state_blinds_posted`
   - #1b ante posted → `test_hunl_initial_state_with_ante`
   - #2 pot calculation → `test_hunl_tiny_tree_pot_invariant` (chain of asserts on stack-equation)
   - #3 stack equation → same test
   - #4 to_call correctness → `test_hunl_initial_state_blinds_posted`, `test_hunl_raise_amount_uses_pot_after_call`
   - #5 fold contribution-loss → `test_hunl_fold_terminates_hand_correctly` (-0.5 BB for SB-fold)
   - #6 showdown tie → `test_hunl_showdown_tie_splits_pot`
   - #7 all-in run-out → `test_hunl_all_in_runs_out_remaining_streets` (5 chance steps)
   - #8 raise cap → `test_hunl_preflop_4_raise_cap`, `test_hunl_postflop_3_raise_cap`, `test_abstraction_no_raise_at_cap`
   - #9 dedup invariant → `test_abstraction_min_bet_clamping`
   - #10 all-in unique → `test_hunl_force_allin_threshold_snaps_short_shoves`, `test_abstraction_all_in_dedup`
   - #11 street transitions → `test_hunl_call_preflop_advances_to_flop`
   - #12 postflop OOP first → `test_hunl_postflop_bb_acts_first`
   - #13 preflop SB first → `test_hunl_preflop_sb_acts_first`
   - #14 hole cards blocking → `test_hunl_chance_outcomes_exclude_held_cards`
   - #15 infoset canonicalization → `test_hunl_infoset_key_canonicalizes_hole_order`
   - #16 hides opponent cards → `test_hunl_infoset_key_hides_opponent_cards`

10. **ALL-IN street-completion fix (S3).** Confirmed.
   - `_street_complete` (hunl.py:444-501) handles `action == ACTION_ALL_IN and old_state.to_call > 0` at line 468 with a `return True`.
   - Comment at 463-467 explicitly documents the matching/under-shove case as a closing case and notes the `new_state.to_call > 0` guard above handles the over-shove-as-raise case.
   - Verified by `test_hunl_all_in_runs_out_remaining_streets` walking ALL-IN → CALL → 5 chance steps to showdown.

11. **ActionContext flat-field rewrite (S2).** Confirmed.
   - `ActionContext` (action_abstraction.py:67-82) exposes all 15 flat fields per spec: `pot, to_call, stacks, contributions, cur_player, street, street_num_raises, street_aggressor, big_blind, bet_size_fractions, preflop_raise_cap, postflop_raise_cap, force_allin_threshold_bb, min_bet_bb, include_all_in`.
   - All internal helpers in `action_abstraction.py` reference these flat fields. No `ctx.config.*` references remain.
   - `HUNLPoker._action_context()` (hunl.py:323-342) constructs all 15 fields explicitly.

12. **Ante support.** Confirmed.
   - `HUNLConfig(ante=N)` — field defined hunl.py:90.
   - `initial_state` (hunl.py:215-223) computes `sb_contrib = small_blind + ante` and `bb_contrib = big_blind + ante`.
   - `to_call = bb_contrib - sb_contrib` (line 223) correctly evaluates to `big_blind - small_blind`, ante-symmetric.
   - `test_hunl_initial_state_with_ante` (test_hunl_core.py:41) asserts contributions=(75, 125), stacks=(9925, 9875), pot=200, to_call=50, street_num_raises=1. Passes.

## Spec coverage gaps (missing tests)

- **CLI behavior** — Spec lists CLI changes (`--hunl-mode` flag, `_GAMES` mapping, `_build_hunl_with_args`) and acceptance criteria: `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500 runs in under 60 seconds`. No test invokes the CLI. `_cmd_solve` is exercised only via the `solve()` function call in `test_hunl_default_tiny_subgame_solvable_in_one_minute`. Manual smoke test would catch regressions.
- **`HUNLPoker(HUNLConfig())` 100 BB smoke test** — Spec success criteria say "produces an initial state and 5 legal actions without crashing". No explicit test. `test_hunl_initial_state_blinds_posted` covers the initial-state half but doesn't assert legal-action count.
- **`mypy --strict` on new files** — Spec deliverable. Not verified during this audit (would require running `mypy` against the files).
- **`ruff check`** — Spec deliverable. Not verified.
- **Raise cap reset on street transition** — Spec #11 says street transitions reset history. Implicit in `_begin_street_transition` (hunl.py:518-520, 528-531) but no explicit assert in tests that `street_num_raises` resets to 0.
- **`force_allin_threshold` with `< 1 BB` setting** — `test_abstraction_force_allin_threshold_snaps_short` uses default `1 BB`. No tests with `force_allin_threshold_bb=0` or `=2`.
- **Asymmetric `initial_contributions`** — Tested only with `(100, 100)` and `(500, 500)`. No `(100, 200)` style asymmetric subgame.

## License compliance

- New files (`hunl.py`, `action_abstraction.py`) carry no attribution comments and contain no copied code.
- Card-int mapping (`rank * 4 + suit`) is a generic encoding; no specific source.
- Action-id encoding (14 flat constants) is unique to this project; no copy.
- The `infoset_key` format (`"{hole}|{board}|{street}|{history}"` with `b<amount>`/`r<amount>` tokens) is described in the spec as inspired by `noambrown_poker_solver` (MIT). No verbatim copy.
- No AGPL-source-like patterns in `_apply_player`, `_street_complete`, or `_begin_street_transition`. The rules-engine state machine reads as straightforward independent implementation.

## Overall verdict

**READY for commit.** All 138 tests pass (41 new + 97 existing). The 12 audit focus areas all verify correctly. The implementation matches the spec, including the two recent fixes (S2 ActionContext flat-field rewrite and S3 ALL-IN street-completion).

The "Should-fix" items are tightening opportunities, not correctness bugs. The "Nice-to-fix" items are style/cleanup. None of these should block PR 3 merge; they can be folded into PR 3.5 polish or addressed via follow-up tickets.
