# Card removal / blocker investigation

## TL;DR

Our codebase is **mostly clean** on card removal at the scalar-CFR / equity-tier
level. The two paths that drive product output today (the HUNL game tree in
`hunl.py` and the pushfold chart generator in `scripts/generate_pushfold_charts.py`)
both account for card removal correctly: `hunl.py` enumerates board chance with
explicit deck-minus-held exclusion, and the pushfold generator weights the 169x169
matrix game by `compat[i,j]` (the count of disjoint combo pairings). The Monte
Carlo equity engine in `equity.py` also excludes hole cards from the deck before
each sample. The user's flag on `generate_pushfold_charts.py:88` (Sklansky-Chubukov)
is a comment-only artefact: SC is invoked as a **sanity-check anchor**, not as the
source of frequencies, and the script's docstring (lines 93-96) explicitly
disclaims SC as a non-Nash unilateral upper bound. **Recommendation: continue
as is** with one nice-to-fix in the chart generator's per-pair sampling.

## What is card removal and why it matters

In Hold'em, the deck is finite (52 cards) and shared. When P0 holds AsKh and the
board shows 2c7d9s, only 47 unseen cards remain for P1 — so any opponent hand
that would require As, Kh, 2c, 7d, or 9s is impossible. Two consequences:

1. **Range re-weighting.** If P1's strategic range is "JJ+, AK", and P0 holds
   AsKh, then P0 blocks half the AK combos (the two suited AK + 4 of 12 offsuit
   AK) and `1/6` of AA. P1's posterior conditional on P0 holding AsKh is not
   the original combo-uniform range — it is the range with blocked combos
   removed and remaining combos re-normalized.
2. **Equity computation.** EV under a range must integrate over compatible
   `(hero_combo, villain_combo, board)` triples. Ignoring removal biases equity
   estimates in proportion to how strongly hero's hand and villain's range
   share ranks/suits. The bias is largest for premium-vs-premium spots (AKo
   vs JJ+/AK reduces villain to ~14 combos from a face-value 18) and for
   monotone boards (one-suiter spots).

A solver that fails to apply card removal therefore (a) trains regrets against
mis-weighted opponent ranges, (b) under- or over-estimates fold equity at
terminal nodes by the blocked weight, and (c) violates the Bayes-consistency
that makes CFR-style averages converge to a Nash equilibrium. Brown's
postflop-solver and Pluribus / Libratus both build their entire vector-CFR
machinery around a `valid_indices` mask precisely because the bias is too
large to ignore in real HUNL postflop.

## Status of each of our components

### Component-by-component verdict

| Component                          | Card removal handled? | Risk            | Fix needed |
|------------------------------------|-----------------------|-----------------|------------|
| `equity.py` MC + enum              | Yes                   | None            | None       |
| `hunl.py` board chance node        | Yes                   | None            | None       |
| `hunl.py` preflop hole chance      | Yes                   | None            | None       |
| `dcfr.py` reach probabilities      | N/A (scalar-CFR over an already-removal-aware tree) | None | None |
| `pushfold` chart loader            | N/A (lookup only)     | None            | None       |
| `generate_pushfold_charts.py`      | Yes (via `compat`)    | Minor MC bias   | Nice-to-fix |
| `games.py` Kuhn                    | Yes                   | None            | None       |
| `games.py` Leduc                   | Yes                   | None            | None       |

### `poker_solver/equity.py` — verdict: clean

Evidence:
- Line 88 builds `deck = full_deck()`.
- Lines 92-98 (enumeration path): collect all hole cards into `used`, then
  `remaining = [c for c in deck if c not in used]`. Enumeration iterates
  `itertools.combinations(remaining, cards_needed)` (line 200), so every
  runout drawn is automatically disjoint from board and both hole pairs.
- Lines 108-129 (MC path): same pattern, with `used` extended by each sampled
  combo. Range sampling routes through `Range.sample_excluding(used, rng)`
  (`range.py:47`) which rejects any combo whose two cards intersect `used`;
  if rejection fails after 10 random tries it does a full scan (line 59-64).
- Lines 124-126 also explicitly reject concrete hands that conflict with
  already-used cards.
- `_validate_concrete` (line 173) raises on overlap before any sampling
  starts, so caller bugs surface loudly.

**Verdict: card removal handled at both deck-level and range-level.** Two
hands holding the same Ace would raise `ValueError` (line 183) and a board
sharing a card with a hole would do the same.

### `poker_solver/hunl.py` — chance nodes: clean

The HUNL tree has three kinds of chance nodes; all three exclude held cards
from the outcome space.

**Board chance node** (`_board_card_outcomes`, lines 541-553):

```python
held: set[Card] = set()
if state.hole_cards:
    held.update(state.hole_cards[0])
    held.update(state.hole_cards[1])
held.update(state.board)
remaining = [Card(r, s) for r in range(2, 15) for s in range(4)
             if Card(r, s) not in held]
...
p = 1.0 / len(remaining)
return [(card_to_int(c), p) for c in remaining]
```

This is the canonical pattern: build the held set, subtract from a fresh
full deck, uniform-weight the remainder. Both hole cards (when concrete) and
all dealt board cards are excluded. Flop/turn/river deals each enumerate the
correct 50/49/48/47/46-card subspace.

**Preflop hole-card chance node** (`_enumerate_preflop_hole_outcomes`, lines
556-573):

The four nested loops over `(i, j, k, m)` with `k not in (i,j)` and
`m not in (i,j)` and `j > i`, `m > k` enumerate exactly the
`C(52,2) * C(50,2) = 1,624,350` non-conflicting (P0, P1) hole-pair
combinations. Each is assigned uniform probability `1/total`. **No combo with
shared cards is emitted, and probabilities are correctly the joint prior over
disjoint pairs.**

Note: this preflop chance node is enumerated but never walked in production —
running DCFR over 1.6M chance outcomes from the root would be infeasible.
In practice the preflop tree is either (a) entered via `initial_hole_cards`
in a subgame config (a single concrete hole pair, no preflop chance branch)
or (b) routed to the pushfold lookup path via `solver.solve`
(`solver.py:48-51`). The enumeration is still correct.

**Run-out chance nodes (all-in / showdown deals)** use the same
`_board_card_outcomes` codepath (`_apply_chance`, lines 428-440), so the
same exclusion logic applies.

### `poker_solver/dcfr.py` — reach probabilities: clean (scalar-CFR)

DCFR is a **scalar-CFR implementation**: every infoset stores a single
strategy / regret vector, and tree walks compute one expected-value pass per
information set. There is no per-hand vector of opponent reach (which is
where `valid_indices` would matter in a vector-CFR solver).

Why this is correct **given our tree**:
- The infoset key `infoset_key(state, player)` in `hunl.py:309-318` includes
  the player's hole cards (line 311 sorts and stringifies them). So the
  infoset is conditioned on the specific hole pair.
- The chance node enumerates only valid (non-conflicting) opponent hole pairs
  and weights them uniformly. The `reach[-1]` chance reach (`dcfr.py:113-115`)
  therefore correctly tracks `P(this opponent hand AND this board | our hand)`.
- Counterfactual reach at a player infoset (`dcfr.py:139-145`) multiplies
  opponents' strategy reach and chance reach. Since chance reach is itself
  card-removal-aware, the regret update is unbiased.

The trade-off: scalar-CFR is correct but enumerates the entire tree per
iteration (no `O(|range|)` speedup the way Brown's vector evaluator gives).
For Kuhn/Leduc that's fine. For HUNL that's prohibitively expensive at the
preflop root, which is exactly why production HUNL solvers move to vector-CFR
(see `references/code/postflop-solver/src/game/evaluation.rs:14-150`). We're
not running full-tree HUNL DCFR in production yet — we route to pushfold
charts for short stacks and to subgames (single concrete hole pair) for
postflop play. So the scalar-CFR design is consistent with current usage.

If/when we expand to deeper-tree HUNL, we will need to migrate to vector-CFR
with `valid_indices`. That is a much larger architecture change and is
flagged in `simplify` / next-PR notes, not in this report.

### `poker_solver/pushfold.py` — verdict: lookup only

`pushfold.py` is a static-data accessor: it loads `charts/pushfold_v1.json`
(line 39-51) and returns `(hand_class -> frequency)` mappings. It does not
itself compute anything strategic, and it does not need to handle card
removal. The frequencies it returns are *unconditional* per-hand jam
frequencies; the chart generator is responsible for having computed them
correctly with card-removal-aware combinatorics.

### `scripts/generate_pushfold_charts.py` — verdict: handled (with one MC nit)

**The headline question.** The chart generator builds a matrix game where SB
chooses jam/fold and BB chooses call/fold, with 169 hand-class infosets per
side. Card removal enters in three places:

1. **`_build_compat_count` (lines 191-208).** For each pair `(i, j)` of hand
   classes, count the number of `(combo_a, combo_b)` pairings where the four
   cards are distinct. This is `compat[i,j]`. AA-vs-AA correctly evaluates to
   0 because there are only 4 aces total. AA-vs-AKs gives 6 * 4 * (probability
   we don't both want the same Ace) etc.

2. **Joint hand prior (`solve_pushfold_for_depth`, lines 371-382).** The
   solver builds `joint = compat / sum(compat)` and derives the marginals
   `p_sb`, `p_bb`, conditionals `p_bb_given_sb`, `p_sb_given_bb`. **The DCFR
   updates (lines 419, 442, 475, 477) are all weighted by these card-removal-
   aware priors, never by uniform-combo priors.** AA-vs-AA never contributes
   to an EV because `compat[i,i] == 0` for AA, so the row drops out of the
   marginal entirely.

3. **Equity matrix entries (lines 220-247).** `_exact_equity_pair` excludes
   both players' hole cards from the deck (line 230-233) before sampling
   boards — same pattern as `equity.py`. Combo sampling
   (lines 286-308) explicitly rejects `combo_b` that shares any card with
   `combo_a`, with a fallback to full-scan if the random sampler fails.

Sklansky-Chubukov is referenced only as a sanity-check anchor in
`SKLANSKY_ANCHORS` (line 98), and the docstring at lines 93-96 explicitly
states "Sklansky-Chubukov is *not* HU Nash; it overestimates jam frequency
at the 4-10 BB depths because it assumes a calling-station BB. We only assert
the well-defined endpoints..." The frequencies in the chart are computed by
DCFR with the `compat`-weighted joint, not lifted from SC tables. The
comment-side reference is benign.

**The one nice-to-fix.** Per-class-pair MC samples (line 286) draw
`EQUITY_COMBO_PAIRS_PER_CLASS_PAIR = 4` random `(combo_a, combo_b)` pairings.
For class pairs with many possible combo configurations (e.g. AKo-vs-72o has
12 * 12 = 144 pairings with most disjoint), 4 samples leaves a small bias if
suit-block effects are uneven across the unsampled configurations. The
docstring at line 70-73 estimates per-pair standard error around 1%; for
pure-jam-fold decisions where most cells are well-separated this is
negligible, but borderline hands (around 0.5 jam frequency at marginal
depths) could shift by ~1-2% of frequency. This is a Monte Carlo precision
question, not a card-removal bug. **Severity: nice-to-fix.**

### `poker_solver/games.py` Kuhn — verdict: clean

`chance_outcomes` (line 112-116):
```python
dealt = set(state.cards)
remaining = [c for c in _KUHN_DECK if c not in dealt]
p = 1.0 / len(remaining)
return [(c, p) for c in remaining]
```

3-card deck, each player gets one card, no replacement. After P1 gets card
`c1`, P2's chance node enumerates the 2 cards not in `{c1}`. Standard.

### `poker_solver/games.py` Leduc — verdict: clean

`chance_outcomes` (line 238-246):
```python
dealt = list(state.private_cards)
if state.public_card is not None:
    dealt.append(state.public_card)
remaining = list(_LEDUC_DECK)
for card in dealt:
    remaining.remove(card)
```

6-card deck (`(11,11,12,12,13,13)`, two suits of J/Q/K). `list.remove` peels
off one instance per dealt card, so if P1 holds a J the second J remains in
the deck. Public-card chance node enumerates the 4 remaining cards. This
matches open_spiel's `LeducState::ChanceOutcomes`
(`references/code/open_spiel/open_spiel/games/leduc_poker/leduc_poker.cc:546-571`):
both implementations iterate over the deck, skipping cards already dealt.

## Reference patterns (what the canonical solvers do)

### Noam Brown's poker_solver (`references/code/noambrown_poker_solver/`)

The canonical "vector evaluator + MCCFR with card-removal-aware sampling"
pattern. Two pieces worth citing in detail:

**`cpp/src/river_game.cpp:213-251` — `build_hands`.** For each hand in the
range, line 232-237 checks whether any board card collides with either of
the hand's hole cards and skips the hand if so. This pre-filters the
range-vs-board card removal up front.

**`cpp/src/vector_eval.cpp:32-78` — `build_cache`.** For every player-hand
index `h`, builds three lists `blocked_less[h]`, `blocked_equal[h]`,
`blocked_greater[h]` containing opponent-hand indices that share a card with
`player_hands[h]`. At showdown
(`vector_eval.cpp:90-131`), the per-hand value is computed by first taking the
prefix-sum over *all* opponent weights (which assumes no card removal) and
*then* subtracting the blocked opponent weights from win/tie/lose totals
(lines 118-126). Same pattern at fold nodes (`vector_eval.cpp:133-162`):
total opponent weight minus blocked weight. This is the textbook "card
removal via masking" trick.

**`cpp/src/mccfr.cpp:141-183` — `build_sampling_cache`.** The hand-pair
sampler explicitly excludes P1 hands that share a card with each P0 hand
(line 159-162), and weights P0 sampling by the *valid* P1 mass (line 173:
`p0_weights[i] * total`). So Monte Carlo iterations naturally see hand
pairings in proportion to their actual joint prior under card removal —
exactly what our chart generator does via `compat`.

### postflop-solver (`references/code/postflop-solver/src/`, AGPL)

Read for understanding only. The relevant primitives:

- **`card.rs:106-181` — `valid_indices`.** For each `(board_subset, player)`
  pair, builds a `Vec<u16>` of opponent-range hand indices whose cards do not
  collide with the board. Indexed at evaluation time by
  `valid_indices_flop / _turn / _river`.

- **`game/evaluation.rs:49-150` — terminal-node evaluation.** Iterates over
  `valid_indices[player]` and `valid_indices[opponent]` rather than the raw
  range, then uses inclusion-exclusion (lines 86-90):
  `cfreach = cfreach_sum + cfreach_same - cfreach_minus[c1] - cfreach_minus[c2]`
  to subtract opponent weight blocked by each player-hand's cards. This is
  the vector-CFR formulation of the same correction noambrown's cpp does
  with prefix sums plus explicit blocked lists.

### open_spiel Leduc (`references/code/open_spiel/.../leduc_poker.cc`)

Already cited above: `ChanceOutcomes()` at line 546-571 iterates over the
deck and emits each remaining (non-`kInvalidCard`) card with uniform
probability, exactly mirroring our `games.py:238-246`.

## Literature consensus

- **Zinkevich et al. 2008 (CFR foundational paper),
  `references/papers/zinkevich_2008_cfr_nips.pdf:85-105`.** Defines chance as
  a special player `c` with a probability measure `f_c(·|h)` over the action
  set at each chance history. The paper itself does not prescribe a specific
  formula for `f_c`; the obligation is on the game definition to ensure
  `f_c(·|h)` correctly models the remaining-deck distribution. Our
  implementations all satisfy this contract.

- **Brown & Sandholm 2019 (DCFR), `references/papers/dcfr_brown_2019.pdf`.**
  Inherits Zinkevich's framework (the paper does not specialize chance
  handling for poker beyond CFR's general definition). DCFR's discounting
  schedule is orthogonal to card removal — what matters is that the CFR
  walk it accelerates is itself unbiased, which requires correct chance
  probabilities at each node.

- **Brown 2019 Pluribus, `references/papers/pluribus_brown_2019_science.pdf:361-368`.**
  "Pluribus uses an optimized vector-based form of Linear CFR (38) that
  samples only chance events (such as board cards)." External-sampling
  MCCFR + vector evaluator (`vector_eval.cpp` pattern) is the production
  recipe; per-hand opponent weights *are* the carrier of card-removal
  information at terminal nodes. The supplement also notes (line 1122-1123
  in our copy of the science paper)... actually that citation was to ReBeL
  ↓ — Pluribus's supplement isn't on disk; we cite the science.org main paper
  only.

- **ReBeL, `references/papers/rebel_brown_2020.pdf:1122-1123`.** "Network
  input is a probability distribution over pairs of cards for each player,
  as well as all public board cards." Pair-of-cards-level distributions are
  exactly the vector representation that makes card-removal correctness
  efficient.

- **Kept-out-of-scope: bunching effect.** `postflop-solver/src/bunching.rs`
  references the multi-way bunching effect (folded-player card biases). Not
  relevant for two-player HUNL because no third player has folded; flagged
  here only because the user mentioned it.

## Specific findings + recommended fixes

### Finding 1 — `_build_compat_count` is O(169^2 * 12 * 12) and slow on first run

**Severity: nice-to-fix.** Lines 191-208 of `generate_pushfold_charts.py` do
a quadruple loop (169 * 169 * 6-12 * 6-12) for combo-compatibility counting.
On reasonable hardware this is ~7s; not a correctness issue. The exact same
counts could be derived in closed form from the rank-vs-rank overlap pattern,
but the current code is clear and fast enough.

**Recommendation:** leave it. No fix needed unless we re-run on a slow
machine or move the matrix to a hot path.

### Finding 2 — Per-pair MC samples in equity matrix are coarse

**Severity: nice-to-fix.** Per-class-pair we sample 4 combo pairings *
350 boards (`EQUITY_COMBO_PAIRS_PER_CLASS_PAIR=4`,
`EQUITY_BOARDS_PER_COMBO_PAIR=350`, lines 74-75). For class pairs with many
suit configurations (e.g. AKo-vs-KQo, ~144 disjoint combo pairings), 4
samples may under-cover the tail. The docstring at lines 70-73 estimates ~1%
standard error, which is acceptable for pure jam/fold decisions but could
shift borderline hands by ~1-2% of frequency at marginal depths.

**Recommended fix:** bump `EQUITY_COMBO_PAIRS_PER_CLASS_PAIR` to 8-12 for
the final v2 production run (the docstring trade-off table holds linearly).
Cost: matrix build goes from ~7 min to ~15-20 min, one-time. **Effort:
one-line constant bump + a regeneration run.**

### Finding 3 — No vector-CFR yet (architectural, not a bug)

**Severity: nice-to-fix (long term).** Our `dcfr.py` is scalar-CFR; full-tree
HUNL DCFR is infeasible at the preflop root because we'd need to enumerate
~1.6M hole pairs per iteration. The current product avoids this by routing
short stacks to pushfold lookup and postflop subgames to single-hole-pair
trees. Both are correct for what they do.

**Recommended fix:** when we expand to deeper trees or non-trivial preflop
ranges, migrate to vector-CFR with `valid_indices` (postflop-solver pattern)
or with explicit `blocked_*` lists (noambrown pattern). This is a major
architecture change — multi-PR effort. **Not a blocker for current work.**

### Finding 4 — Sklansky-Chubukov comment at chart generator line 88

**Severity: nothing to fix.** The user flagged
`scripts/generate_pushfold_charts.py:88` because the comment block (lines
88-125) references Sklansky-Chubukov. Reading the entire block (especially
lines 93-96) shows SC is invoked only as a sanity-check anchor for
"endpoints we know must be 1.0 or 0.0," with an explicit disclaimer that SC
is non-Nash. The actual frequencies come from DCFR over the
`compat`-weighted matrix game, which *does* handle card removal correctly.
**No code change needed.** Consider tightening the comment to lead with
"SC is used here only as a sanity anchor; see `solve_pushfold_for_depth`
for the Nash computation" if a future reader is likely to be misled.

## Recommendation

**Continue as is.** Our card-removal handling is consistent with the
canonical references (noambrown vector evaluator, postflop-solver
`valid_indices`, open_spiel chance enumeration) and consistent with the
Zinkevich CFR framework's contract on chance probabilities. The user's flag
on `generate_pushfold_charts.py:88` is a comment-only artefact — the chart
generator's frequencies are not derived from Sklansky-Chubukov.

Optional, deferrable improvements (none gating any current PR):

1. **(nice-to-fix)** Bump `EQUITY_COMBO_PAIRS_PER_CLASS_PAIR` from 4 to 8-12
   for the next chart regeneration; absorbs ~10-15 min of additional matrix
   build time for ~2x reduction in per-pair MC error.
2. **(nice-to-fix, multi-PR)** When the roadmap reaches full-tree HUNL DCFR
   (beyond pushfold + concrete-hole subgames), migrate to vector-CFR with
   `valid_indices` masking, following the postflop-solver evaluation pattern.
3. **(cosmetic)** Tighten the SC comment block at
   `scripts/generate_pushfold_charts.py:88-125` to make it unambiguous that
   SC is invoked as a sanity anchor and not as a frequency source.

No must-fix or should-fix items identified.
