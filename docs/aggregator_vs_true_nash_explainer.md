# Aggregator vs. True Nash: Two Different Range-vs-Range Code Paths

**Audience:** anyone reading a range-vs-range result who wants to know
*which question the number actually answers*.

## TL;DR

`poker_solver` ships two functions whose names suggest they answer the same
question — "what is the Nash strategy for hero's range vs villain's range?"
— but they actually answer **different** questions:

| Function | Question it actually answers |
|---|---|
| `solve_range_vs_range` (Python, `poker_solver/range_aggregator.py:211`) | "For each (hero combo, villain combo) pair, what does perfect-info Nash say? Then pool across the range." |
| `solve_range_vs_range_rust` (Rust PyO3, `crates/cfr_core/src/lib.rs:428`) | "What is the joint imperfect-info Nash equilibrium of hero's range vs villain's range?" |

The first is the **Pluribus-style blueprint aggregator**. The second is the
**vector-form CFR** that mirrors Brown's reference C++ trainer at
`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-240`
structurally (three independent code reviews concur; empirical parity
verified on shallow-cap spots, currently under investigation for a
deep-cap facing-raise divergence — see Example 3).

Treating their outputs as interchangeable has caused real test-verdict drift
in this project. This doc exists so you don't make that mistake.

## What the AGGREGATOR (`solve_range_vs_range`) does

Reading the function (`poker_solver/range_aggregator.py:225-301`):

1. Enumerate concrete combos in hero's range (`AA` → 6, `AKs` → 4,
   `AKo` → 12).
2. For each (hero combo, villain combo) pair, run a **perfect-information
   1v1 Nash solve** through the standard `solve()`. Both players know each
   other's exact hole cards in that subgame.
3. Aggregate hero's first-decision action frequencies, weighted by combo
   count.

The module's own docstring (`range_aggregator.py:1-32`) names this what
it is: a "blueprint-aggregation workaround," not a Nash range-vs-range
solve.

**Strengths.** Fast. Robust on monotone / draw-heavy boards where the
vector path approaches its memory edge. Per-combo correctness is
meaningful as a sanity check on the underlying `solve()`.

**Weaknesses.** It is **not** Nash for the range. Each subgame "sees"
villain's exact hole cards, so hero plays the full-information best
response — never bluff-catches off range composition, never produces
range-driven bet-size polarization, never mixes to hide information.
The aggregate looks like a mixed strategy but is really a histogram of
"what fraction of villain representatives hero beats in the full-info
subgame."

## What VECTOR-FORM CFR (`solve_range_vs_range_rust`) does

Reading `crates/cfr_core/src/dcfr_vector.rs:1-54` and the PyO3 surface in
`crates/cfr_core/src/lib.rs:389-503`:

- Each player infoset stores a `hand_count × action_count` regret /
  strategy-sum table. Hands are a vector dimension *inside* each infoset.
- The betting tree is walked **once per iteration** — no hole-card chance
  enum at the root.
- Opponent-node traversal scales opponent reach per-hand by their
  strategy and recurses; own-node traversal collects per-(action, hand)
  action values and updates `regret[h, a] += opp_reach × (action_value[a, h]
  − node_value[h])`. Structural port of Brown's `Trainer::traverse` at
  `trainer.cpp:138-240`.
- Output: a single joint Nash where hero's strategy at each infoset can
  genuinely mix across actions, conditioned on the full range.

**Strengths.** True Nash. Real bluff-catching frequencies, real polarized
bet-sizing, mixes for the right information-theoretic reasons.

**Weaknesses.** More memory-intensive — preflop full-1326 is currently
deferred (`dcfr_vector.rs:49-50, 755`). Some monotone/wet configurations
approach the 16 GB spec envelope.

## Concrete examples

### Example 1 — AA on a monotone board

**Aggregator output.** AA's range-context aggregate on a monotone flop is
`~32% check, ~68% bet`.

**What is actually measured.** The "68%" decomposes into "AA pure-bets
vs every villain class it beats (9 of 14 reps ≈ 64%); pure-checks vs
every class that beats or chops (5 of 14 reps)." That is **basket
selection**, not range Nash polarization. True Nash on a monotone flop
should have AA mostly checking (~80-95%) — betting heavy into a board
where villain's range has flushes is dominated.

### Example 2 — JJ facing a pot-sized river bet

**Aggregator output.** JJ folds **7.69%** on a deep-stack river, stable
to 1e-9 across 500 / 1000 / 2500 / 5000 iterations.

**What is actually measured.** 7.69% is **deterministic**, not
convergence noise — it equals `3/39`, the fraction of villain reps that
were AA. In each AA-vs-JJ subgame full-info Nash correctly folds JJ
(0% equity vs a set of aces on a static runout). The aggregator pools
that AA-rep fold into the range-level frequency. True Nash with
imperfect-info would defend 100% — calling beats folding by a large
positive EV against the unknown-villain distribution.

### Example 3 — vector-form: structural match, deep-cap empirical gap

Three independent code reviews concur that `dcfr_vector.rs` matches
Brown's `cpp/src/trainer.cpp:138-240` **structurally**: iteration loop,
DCFR weights, regret matching, average strategy, and per-iteration
discount all match line-by-line. The only documented intentional
difference is scale-only reach normalization (Brown sums to 1.0; Rust
uses 1.0 per hand), which is scale-invariant under regret matching.

PR 40 confirmed three test-side encoding artifacts that contributed
to the original 22-42pp acceptance-test signal: action-axis column
ordering (Brown emits `[c, f, r_low, r_med, r_jam]`; Rust emits
`[f, c, r_low, r_med, A]` after sorting on action ID, so positional
indexing mis-aligned the columns); range-to-player-slot inversion
(Brown's P0 opens river, this engine's P1 opens river); and
hand-string suit-order normalization (`cdhs` vs `shdc`).

**However, a v1.6.1-bundle dry-run (PR 33+34+35-A+B+40 composed)
empirically re-confirms a residual algorithmic divergence at deep-cap
facing-raise that the structural reviews did not surface.** On A83 at
`b1000r3000`, bottom-pair-Ace cells (3sAs, 3cAc) call ~0.69 in Rust
vs ~0.36 in Brown — 33-pp delta, max |diff| 0.33. K72 max |diff| is
~0.07. Action-axis permutation IS applied; the gap is semantic.

Shallow-cap and river single-shot paths empirically match Brown; the
gap is isolated to deep-cap facing-raise. The structural reviews
verified CODE matches Brown's algorithm; they did not verify the
algorithm produces Brown's empirical OUTPUT at this scenario — a
label-vs-semantics gap (`MEMORY.md::feedback_label_vs_semantics`).
Investigation in flight: best-response cross-check, iteration sweep
500/1000/2000/4000/8000, and side-by-side re-read of
`dcfr_vector.rs::traverse` vs `trainer.cpp:138-240` on the
facing-raise path. Full report: `docs/v1_6_1_dryrun_verification.md`.

## When to use which

**Use `solve_range_vs_range` (aggregator) when:**
- You want a fast Pluribus-blueprint-quality answer.
- The board is monotone / wet and the vector path is near its memory ceiling.
- You are sanity-checking per-combo correctness of `solve()`.
- You want a 13×13 matrix for a UI and have already labelled it as a
  blueprint approximation.

**Use `solve_range_vs_range_rust` (vector form) when:**
- You want true Nash for Brown parity comparison.
- The question is about **bluff-catching frequencies** (e.g., "should JJ
  ever fold facing pot odds with 93% equity?").
- The question is about **inducing strategies** or **polarized
  bet-sizing** driven by range composition.
- You are validating an imperfect-information Nash hypothesis (mixed
  checks with strong hands, polarized small/all-in splits, etc.).

## Implications for interpreting outputs

1. A per-combo PASS from the aggregator does **not** imply a range-level
   PASS.
2. Questions about *range polarization*, *bluff-catching*, and
   *inducing* require the vector form. The aggregator structurally
   cannot answer them — even at infinite iterations.
3. Aggregator numbers like "7.7% fold" or "68% bet" are deterministic
   artifacts of the aggregation rule, not Nash mixed frequencies.
   Misreading them produces false-positive verdicts ("AA polarizes")
   or false-negative solver-bug reports ("convergence noise").
4. Match the tool to the question: aggregator for per-combo sanity,
   vector form for range-level Nash.

## One wrinkle

The aggregator is **not just an approximation of the vector form** —
it solves a structurally different mathematical object. Each per-hand
subgame is a full-info 2-player Nash that converges to the Nash of
*that 1v1 problem*. The vector form solves the joint imperfect-info
Nash of the *range game*. So:

- The two can diverge by arbitrarily large amounts on hands where
  range composition matters (bluff-catchers, polarized sizing).
- They agree closely where the value-vs-air dynamic dominates
  (premium pairs vs underpairs on dry boards), since the full-info
  answer and the range-Nash answer coincide there.
- Iterating the aggregator longer cannot close the gap; only switching
  to the vector form can.

This is why "aggregator gives 7.7% fold" and "true Nash gives 0% fold"
are both correct outputs of correctly-functioning code paths — they
answer different questions.

When in doubt: read the function name, then read this doc.
