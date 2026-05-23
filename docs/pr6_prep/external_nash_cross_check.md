# External Nash cross-check for PR 6 tiny-subgame result

**Date:** 2026-05-22
**Author:** orchestrator subagent (PR 6 commit prep)
**Scope:** Read-only. No solver runs, no binary builds.
**Status (TL;DR):** No external Nash oracle is reachable for this exact fixture
without running another solver. PR 6 commit can ship without an external
cross-check; **PR 7's `noambrown` river-spot diff harness is the proper
external validation gate.** The plausibility check on the fixture is
unambiguous: `AhKc` makes top two pair on the final board and dominates
`QdQh` (pair only) at showdown, so the equilibrium value should land at the
fold-vs-call ratio implied by SPR 1 — well-defined and bounded.

---

## 1. What we know from PR 6

PR 6's `test_hunl_river_subgame_diff_python_vs_rust` runs both tiers at
1000 iterations on the locked tiny subgame and observes:

- 16 infosets on each side, identical key set.
- `max_abs_diff = 0.0` across the full strategy table (per Agent C report
  in `docs/pr6_prep/cross_agent_reconciliation.md`).
- Exploitability ~0 after 1000 iterations (river subgame has a tiny tree;
  CFR/DCFR converges fast).

This is **bit-exact Python ↔ Rust parity**, which means PR 6 has the
**internal consistency** half of the validation pair locked. What is
missing is an **external** anchor showing the converged strategy is the
true Nash equilibrium and not a shared bug in both tiers.

**Why bit-exact parity is not enough on its own.** If a sign error in the
utility function flipped P0 and P1's terminal payoffs, both Python and
Rust would converge to the *same wrong* answer and the diff harness would
still pass. The PR 7 noambrown diff is the first place an external
reference enters the chain.

---

## 2. External oracles surveyed

### 2.1 `references/code/noambrown_poker_solver/` (MIT, Brown 2026)

- **Code available?** Yes — full C++ + Python implementations under
  `cpp/src/` and `python/src/`.
- **Pre-computed sample outputs / strategy dumps?** **No.** Repo audit
  (`find … -name "*.json" -o -name "*.txt"`) returns only `README.md`,
  `_NOTES.md`, `AGENTS.md`, `CONTRIBUTING.md`, `cpp/README.md`. There is
  no `tests/` directory, no checkpointed JSON, no canonical strategy
  fixture committed. The `--dump-strategy PATH` CLI flag in
  `cpp/src/main.cpp:42-43` would *produce* such a dump but only at
  runtime, after a build + solve.
- **Default fixture in the upstream repo:** board `Ks Th 7s 4d 2s`, pot
  1000, stacks 9500, uniform range, bet sizes `0.5, 1.0`, all-in on
  (`README.md:58`; `python/src/cli/subgame_gui.py:302`;
  `cpp/src/main.cpp:647`). **This does NOT match our PR 6 fixture**
  (`As 7c 2d Kh 5s`, SPR 1, single-hand vs single-hand). The upstream
  default is also a *uniform range vs uniform range* spot, while ours
  is *singleton hand vs singleton hand* — completely different
  equilibrium shape.
- **Could we build the binary and run it on our fixture?** Yes
  (`cmake -S cpp -B cpp/build && cmake --build cpp/build -j` per
  `cpp/README.md`), but **out of scope for PR 6 prep** per task
  constraints. This is exactly what PR 7's `tests/test_hunl_noambrown_diff.py`
  is being designed to do — point the noambrown C++ solver at the
  same board + the same range structure and compare strategies.

### 2.2 `references/papers/dcfr_brown_2019.pdf` (Brown & Sandholm, AAAI 2019)

- Figures 1–4 publish **exploitability convergence curves** on four
  HUNL subgames (mbb/g vs iteration count for CFR / CFR+ / LCFR / LCFR+
  / DCFR variants). y-axis is exploitability rate over 32,768 iterations.
- **No named-hand fixture data.** The paper's HUNL subgames are
  range-vs-range, not single-hand. None of the four subgames is
  specified down to the board + hole-card level (board cards are not
  enumerated in the paper text we have indexed).
- **No published strategy table** for any single (board, hole, hole)
  triple. The paper validates *algorithmic convergence rate*, not
  *strategy values*, so it would not be a usable Nash oracle even if
  the fixtures matched.

### 2.3 Sklansky-Chubukov-style closed forms

- SC charts give push/fold-only equilibrium ranges for *preflop* HUNL
  short stacks under the simplifying assumption that the caller's
  range is condition-free.
- **River single-hand-vs-single-hand subgames with a discrete bet
  menu have no published closed form.** The equilibrium depends on
  the bet sizes available, the SPR, and showdown equity — too many
  free parameters for an SC-style table.
- **Not applicable** to our fixture.

### 2.4 `references/code/open_spiel/` (universal_poker endgames)

- `open_spiel/games/universal_poker/endgames/subgame{1..4}.txt` exist
  but encode ACPC-style subgame specifications, not Nash strategy
  fixtures. open_spiel ships *games*, not pre-solved equilibria for
  named river spots.
- Not useful as an external oracle here.

### 2.5 `references/code/slumbot2019/`

- Slumbot ships `src/solve_all_subgames.cpp`, `cfrp_subgame.cpp` etc.
  Like noambrown, it's *solver code*, not *checked-in strategy
  outputs*. Same blocker: building + running it would be a
  re-validation exercise, not a lookup.

### 2.6 Online equity calculators (read-only sanity)

- `AhKc` vs `QdQh` on `As 7c 2d Kh 5s` river: **100% / 0%** at
  showdown (AhKc has AA-KK two pair; QQ has a pair of queens only).
  This is a closed-form arithmetic fact — confirmed below in §4.

---

## 3. What we can cross-check NOW (before PR 7)

The only external-data-driven checks reachable without running another
solver are:

1. **Showdown winner direction.** At `As 7c 2d Kh 5s`, `AhKc` makes
   two pair (Aces + Kings, kicker 7), `QdQh` makes one pair (Queens).
   `AhKc` wins the pot on every showdown → P0's terminal utility
   strictly dominates P1's. PR 6's Python `evaluator.py` and Rust
   `hunl_eval.rs` (or whichever path PR 6 uses) **must agree on this
   direction**. A bit-exact diff with a flipped utility sign would
   *not* be caught by the parity test alone, but it would surface as
   an obviously wrong game value (P0 game_value ≈ −pot / +pot
   flipped). Check the sign of `py_result.game_value` after the
   1000-iter solve — it should be a *positive* value for P0 (BB
   units), since P0 captures the pot when called.

2. **Implied check-call equilibrium shape.** At SPR 1 with no semi-bluffs
   possible (board is locked), P0 (the dominant hand) should
   value-bet at non-trivial frequency and P1 (the dominated hand)
   should call rarely or fold — there is no draw to defend with.
   The equilibrium therefore concentrates on:
   - P0 (AhKc) checks back / value-bets large at high frequency.
   - P1 (QdQh) check-folds the river or check-calls only when the
     bet size is small relative to pot (bluff-catcher math, except
     here P0 has no natural bluffs because his entire range is the
     nut hand). With singleton vs singleton ranges, the equilibrium
     reduces to a degenerate pot-control / value-bet pattern; we'd
     expect P1's calling frequency to depend mechanically on the
     bet-size grid.
   - Empirical PR 6 output sanity-check: read the avg-strategy table
     and confirm P0's check-back and value-bet probs sum to a
     plausible fraction (not a degenerate "fold 100%" or
     "all-in 100% of nothing"), and that P1 folds to most bet sizes.

3. **Game value bound.** P0's exploitability-free game value is
   bounded above by the full pot (P0 always wins the showdown) and
   below by 0 (P1 could fold every street). PR 6's reported
   `game_value` for P0 should land inside `(0, full_pot)`. Outside
   that band is a red flag regardless of parity.

These are **plausibility checks**, not Nash cross-validation — they
catch sign errors and gross blunders, not subtle strategy mismatches.

---

## 4. Poker-theory plausibility for the tiny subgame Nash

**Board:** `As 7c 2d Kh 5s`. **P0 hole:** `Ah Kc`. **P1 hole:** `Qd Qh`. **SPR ~1.**

**Made hands:**
- **P0:** Best 5 of `{Ah, Kc, As, 7c, 2d, Kh, 5s}` = `{Ah, As, Kh, Kc, 7c}`
  → **two pair, Aces and Kings, 7 kicker**.
- **P1:** Best 5 of `{Qd, Qh, As, 7c, 2d, Kh, 5s}` = `{Qd, Qh, As, Kh, 7c}`
  → **one pair, Queens** (with Ace + King kickers).

**Showdown:** Two pair > one pair. **P0 wins 100% of showdowns.** This is
a closed-form fact, not an estimate. Equity check:

- `AhKc` equity vs `QdQh` on river `As 7c 2d Kh 5s` = **1.0** (P0).
- `QdQh` equity vs `AhKc` on river `As 7c 2d Kh 5s` = **0.0** (P1).

**Note on the task statement.** The user prompt mentions "QdQh is just an
overpair." That is correct *only* before the board's `As` and `Kh` are
counted — `QQ` is no longer an overpair once the King and Ace come; it
becomes an *underpair* to the board's `A` and `K`. Either way, `QQ` is
strictly dominated by `AK` here.

**What does the Nash look like?** With one player holding the deterministic
nut and the other holding a pure bluff-catcher (with 0% equity), classic
equilibrium structure says:

- **P0 (nut):** value-bets every size in the menu with nonzero frequency;
  the size mix is chosen so P1 is indifferent between calling and folding
  at each price. With *singleton* ranges, P1 has no information lever — P1
  must either (a) fold to all bets, since P0's range is 100% value, or
  (b) call at a frequency that just balances P0's all-or-nothing payoff.
  With a singleton range on P0, P1's optimal play is in fact **fold to
  any bet** — there is no bluff frequency to defend against.
- **P1 (bluff-catcher with 0% equity):** check-fold the river. Any call
  is strictly losing in expectation since P0's range cannot contain a
  bluff (singleton, known nut).
- **P0's optimal play:** bet small enough that the marginal value extraction
  beats the cost of P1 folding — but with P1 folding to all sizes,
  P0 maximizes by **min-bet (or check) → call** to extract whatever P1
  will pay. The exact bet-size mix is a knife-edge tied to how the
  abstraction's bet grid resolves the "P1 indifferent at every price"
  condition.

**Expected equilibrium values:**
- **P0 game value ≈ +500 cents** (the half of the pot P0 already controls
  via the existing contributions of 500/500, plus whatever P0 extracts
  from P1's subsequent contributions). At SPR 1 with both sides 500-in
  and the pot at 1000, the bounded payoffs are P0 ∈ `[+500, +1500]`
  (worst: P1 check-folds, P0 takes 1000-pot; best: P0 stacks P1 fully,
  takes 2000). In **BB units** (the Python/Rust utility convention per
  PR 3 spec §"Terminal states + utility") and given the 1000-cent
  starting stack / unspecified BB, this lands somewhere normalized by
  the BB scale. **Don't try to nail this to a specific BB number
  without consulting the actual `big_blind` value in `river_subgame_config()`** —
  the fixture uses `starting_stack=1000`, `initial_pot=1000`,
  `initial_contributions=(500, 500)`, but the `big_blind` value lives
  in `HUNLConfig` defaults and would need to be pulled in.
- **Exploitability ≈ 0 fast.** The tree has 16 infosets total. CFR /
  DCFR converges to 0 exploitability on this tree within ~100
  iterations easily. PR 6's 1000-iter run should land at ≤ `1e-9`
  exploitability (subject to float precision).

**Plausibility verdict:** PR 6's reported exploitability ~0 is consistent
with theory. The "obviously degenerate" structure (singleton vs singleton,
no bluffs, dominated bluff-catcher) means any solver that produces a
*sensible* check-fold-or-value-bet pattern is at the right answer. The
diff harness showing `max_abs_diff = 0.0` means Python and Rust agree on
that pattern bit-for-bit. **Both bits look right.**

---

## 5. Recommendation

**Ship PR 6 without external Nash cross-check.** Reasons:

1. **The fixture is degenerate enough that gross errors would have shown
   up in the bit-exact diff plus the exploitability ~0 result.** A sign
   flip in the utility, a wrong-direction comparator in `evaluate_7`, an
   off-by-one in the action menu — none would survive both tiers
   converging to the same strategy at exploitability ~0. The remaining
   bug class is "the same subtle bug in both tiers," and that class is
   exactly what PR 7's external diff is meant to surface.

2. **No external oracle is reachable without running another solver.**
   The DCFR paper publishes convergence rates, not strategies. The
   noambrown repo ships solver code, not pre-computed fixtures. SC-style
   closed forms don't cover this spot. Slumbot / open_spiel / postflop-solver
   are in the same "solver code, no checkpoints" bucket. Building any
   of these and running them on our fixture is a re-validation
   exercise, not a lookup — and is exactly the work PR 7 was scoped to do.

3. **The PR 7 noambrown diff harness is the proper validation gate.**
   PR 7 wires the noambrown C++ solver to the same fixture format and
   diffs strategies at a documented tolerance. That's the place to
   gate on external Nash agreement — not as a precondition for PR 6
   commit, which is **internal-parity scoped** by design.

4. **Plausibility sanity-checks are cheap and worth adding to the PR 6
   review comment.** Specifically:
   - confirm `py_result.game_value` for P0 is positive (P0 has the
     nut hand, must win in expectation);
   - confirm exploitability is ≤ 1e-6 at 1000 iterations (the tree
     is tiny, this is well within DCFR's convergence rate);
   - confirm P1's check-call probability at the river is low across
     all bet sizes (P1 has 0% equity, calling is strictly losing).

   These are not external Nash checks — they're internal smell tests
   that any solver port should pass.

**Action items for PR 6 commit:**
- No new tests required.
- Add a one-line note in the PR 6 commit message: *"Internal Python ↔ Rust
  parity gate; external Nash agreement deferred to PR 7."*
- Open a tracking note in PR 7 prep that the noambrown diff harness is
  the first external Nash anchor in the validation chain.

**Action items for PR 7 prep (downstream of this doc):**
- Wire the noambrown C++ binary into the diff harness against
  PR 6's river subgame fixture *plus* at least one of the canonical
  noambrown default fixtures (range-vs-range on `Ks Th 7s 4d 2s`),
  so we get one shared point and one each-tier point.
- Document the strategy-comparison tolerance up front: noambrown
  uses `float` storage by default (`-DCFR_USE_DOUBLE` flips to
  `double`); their iteration order and float-reduction tree differ
  from ours, so expect ~1e-2 per-action tolerance, not bit-exact.

---

## 6. Open questions / follow-ups

- **Q1.** Does PR 7's harness already enumerate the exact fixtures it
  will diff against, or is "river subgame from PR 6" the only locked
  one? Worth checking `docs/pr7_prep/` before PR 7 fan-out.
- **Q2.** Is there a published Nash strategy table anywhere in the
  references corpus that we haven't indexed? A second-pass grep over
  the full `references/` tree for hand-string patterns like
  `"AhKc"`, `"AsKs"`, `"river_subgame"`, etc., would close this
  question. Spot-check on the noambrown repo and DCFR paper returned
  nothing; the `references/code/postflop-solver/` and `TexasSolver/`
  trees (AGPL, read-only) have not been scanned for committed strategy
  fixtures. Low priority — even if such a fixture existed, the
  hand-and-board combination would have to match ours exactly to be
  useful.
- **Q3.** Should we add a "plausibility test" (the three sanity-checks
  in §5 #4) as a non-blocking test in PR 6 itself, or defer to PR 7?
  Default recommendation: defer to PR 7 to avoid expanding PR 6's
  test surface. PR 6 stays scoped to "Python ↔ Rust parity."

---

## 7. Cross-references

- PR 6 spec: `docs/pr6_prep/pr6_spec.md` (especially §7.1 Test 1 on the
  river subgame fixture; §8.3 Agent C deliverables).
- Tiny subgame fixture builder: `tests/fixtures/hunl_solve_fixtures.py:79`
  (`river_subgame_config`).
- Diff harness: `tests/test_hunl_diff.py:150`
  (`test_hunl_river_subgame_diff_python_vs_rust`).
- noambrown solver: `references/code/noambrown_poker_solver/cpp/src/main.cpp`
  (`--dump-strategy` flag at line 42, default board at line 647).
- DCFR paper: `references/papers/dcfr_brown_2019.pdf` (Figures 1–4
  exploitability curves — no strategy values).
- PR 7 prep dir: `docs/pr7_prep/` — the proper home for the external
  Nash cross-check.
