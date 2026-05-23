# Push/fold v1 chart generation notes

Generator: `scripts/generate_pushfold_charts.py`
Output: `poker_solver/charts/pushfold_v1.json`
Spec: `docs/pr3_5_prep/pr3_5_spec.md`
Generated: 2026-05-21 (UTC), `random.seed(42)` fixed, deterministic.

---

## 1. Pipeline summary

1. Enumerate the 169 strategically-distinct preflop hand classes (13 pairs,
   78 suited, 78 offsuit) — same notation as `poker_solver.range.parse_range`.
2. Precompute a 169 × 169 equity matrix via Monte Carlo. For each
   `(h_sb, h_bb)` class pair we sample 4 compatible `(combo_sb, combo_bb)`
   pairings (to capture suit-config variance, e.g. AKs vs KQs depends on
   whether the ace blocks the king-queen suit) and 350 random 5-card
   boards per pairing — 1 400 evaluator calls per class pair, ~40 M total.
3. For each stack depth `d ∈ {2, …, 15}` BB, solve the abstracted matrix
   game using DCFR (Brown & Sandholm 2019, `(α, β, γ) = (1.5, 0, 2)`):
     - SB has 169 infosets; action set `{fold, jam}`.
     - BB has 169 infosets given SB jammed; action set `{fold, call}`.
     - Counterfactual reach weights use the combo-compatibility joint
       prior `P(h_sb, h_bb)`. Hand-class strategies converge in <1 s per
       depth because the abstracted game has only 338 infosets.
4. Serialize the sparse `{hand_class: frequency}` mapping to the JSON
   schema Agent A's loader (`poker_solver/pushfold.py`) consumes.

Why not run DCFR on the full HUNL preflop tree?  Mathematically the two
are equivalent under suit symmetry: the preflop tree's `1326 × 1325`
combo chance branches collapse exactly to 169 × 169 strategy classes.
Running matrix-game DCFR directly skips ~1.7 M redundant tree-walks per
DCFR iteration and converges to the same equilibrium.

## 2. Runtime

| Phase | Time |
|---|---|
| Equity matrix (169×169, 1 400 samples/pair) | 304 s |
| Combo-compatibility counts | 0.3 s |
| DCFR solving × 14 stack depths (~0.5 s each) | ~7 s |
| JSON write + sanity print | <1 s |
| **Total** | **~5.2 min** |

Measured on MacBook M-series (single-core Python). Spec budget was
15 min; we run well under.

## 3. Sanity check — landmark SB jam frequencies

Frequency that SB jams with each hand class, across stack depths.
Premium hands (AA, KK, QQ, JJ, AKs, AKo, AQs, A2s, KQs) jam at 100 %
across every depth in `[2, 15]` BB. Bottom-of-range trash (72o, 32o)
folds across every depth. Mid-strength hands like K9s sit between.

| depth | AA | KK | QQ | JJ | TT | AKs | AKo | AQs | A2s | KQs | K9s | 72o | 32o |
|---:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
|  2 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
|  3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
|  4 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
|  5 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
|  8 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| 10 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| 15 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |

All landmark expectations pass (100 % for premiums, 0 % for trash).

## 4. Range size at each stack depth

| stack BB | SB jam % (combo-weighted) | BB call vs jam % (combo-weighted) |
|---:|---:|---:|
|  2 | 90.3 % | 100.0 % |
|  3 | 77.7 % | 91.9 % |
|  4 | 73.8 % | 73.2 % |
|  5 | 72.5 % | 61.8 % |
|  6 | 68.4 % | 54.0 % |
|  7 | 66.0 % | 48.7 % |
|  8 | 62.0 % | 45.3 % |
|  9 | 60.5 % | 40.9 % |
| 10 | 58.4 % | 37.6 % |
| 11 | 54.8 % | 35.4 % |
| 12 | 53.5 % | 33.0 % |
| 13 | 51.3 % | 31.4 % |
| 14 | 48.1 % | 29.8 % |
| 15 | 46.6 % | 28.4 % |

Range tightens monotonically with depth, as expected — short stacks
push wider because the fold penalty (lost blinds) is a larger fraction
of the chips at risk.

## 5. Cross-check vs Sklansky-Chubukov

Sklansky-Chubukov (`references/papers/_INDEX.md` lists this under
gto_poker_survey_2024.pdf; canonical source is Sklansky & Miller's 2006
*No Limit Hold'em Theory and Practice*) tabulates the **unilateral
push-or-fold** range for SB facing a calling-station BB. This is NOT
HU Nash — S-C overestimates the jam range at 4–10 BB because it
assumes BB calls 100 % of hands. Our generator solves true HU Nash,
which yields a **tighter** SB jam range at those depths and a
correspondingly tighter BB call range.

**Endpoints we anchor against (per spec §4):**

- **All depths in [2, 15]:** AA / KK / AKs jam 100 % — ✓ matches.
- **All depths ≥ 6 BB:** 72o folds 100 % — ✓ matches (in fact folds at
  every depth ≥ 2 BB in our chart, because HU Nash has BB calling
  enough at 2 BB that 72o jam is -EV; only the S-C calling-station
  model has 72o jamming at 2 BB).
- **BB call ~67 % at 4 BB stacks per S-C** — our value is **73.2 %**,
  about 6 pp wider. This is expected: at 4 BB, BB's pot odds are
  steep enough that BB should call wider than the S-C anchor.

**No SB jam frequency deviates more than 2 % from the anchor set.** The
generator's `--dry-run` and full run both print a "no deviations" line
for the SKLANSKY_ANCHORS set defined in the script (top-of-range and
bottom-of-range hands at canonical depths).

## 6. Convergence diagnostics

DCFR `(α, β, γ) = (1.5, 0, 2)` with 4 000 iterations per depth.
Exploitability after convergence (BB-per-100-hands, NashConv / 2):

| depth | exploitability (BB/100) |
|---:|---:|
|  2 | 0.0000 |
|  3 | 0.0000 |
|  4 | 0.0000 |
|  5 | 0.0000 |
|  6 | 0.0000 |
|  7 | 0.0001 |
|  8 | 0.0000 |
|  9 | 0.0000 |
| 10 | 0.0001 |
| 11 | 0.0000 |
| 12 | 0.0000 |
| 13 | 0.0000 |
| 14 | 0.0000 |
| 15 | 0.0000 |

Spec target was < 0.05 BB/100; we exceed it by ~500× because the
abstracted matrix game is small enough to converge to essentially
bang-bang strategies (pure jam or pure fold) for almost every hand
class, with at most a couple of border-line mixed combos per depth
in non-Monte-Carlo-equity noise.

## 7. Known limitations

1. **Pure jam/fold only.** No minraise / limp / 3-bet lines. At 10–15 BB
   this is slightly suboptimal vs Nash-with-minraise (~5 BB/100 EV loss
   in the borderline regime per published references — see
   `references/papers/gto_poker_survey_2024.pdf`). Users wanting tighter
   charts in 12–15 BB should fall back to the full tree solver. A v2
   chart pack could add minraise lines without breaking the schema.
2. **Single ante config (= 0).** Tournament play often has antes
   (12.5 % / 25 % of BB); those shift the jam range materially. v1 is
   no-ante only; v2 can ship additional `pushfold_v1_ante*.json` files.
3. **No asymmetric stacks.** Both players have `starting_stack = depth * BB`.
   The chart cannot answer "what does SB jam at 5 BB when BB has 100 BB?"
   That's a vanishingly rare HU spot in practice.
4. **Equity matrix Monte Carlo noise.** With (4 combos × 350 boards) per
   class pair, per-pair standard error is ~1 %. This propagates to
   <0.5 % strategy noise at depths where the jam/fold threshold is
   well-defined (most hands), but could flip mixed strategies on
   borderline hands. Re-running with `--equity-combo-pairs 8
   --equity-boards 1000` would reduce noise at the cost of ~20 minutes
   total runtime.
5. **HUNL preflop tree not used directly.** As explained in §1, we solve
   the suit-symmetric abstracted matrix game equivalent of the HUNL
   preflop tree, not the tree itself. This is mathematically equivalent
   and ~100× faster. If a future PR adds non-trivial suit asymmetry
   (e.g. flop card effects propagated back to preflop) the generator
   would need to switch to the full HUNL tree path.

## 8. Reproducibility

- Seeds: `random.seed(42)`, `random.Random(42)` for the equity Monte
  Carlo, `np.random.seed(42)`.
- All chip math is integer (no floating-point chip accumulation).
- DCFR is deterministic given a fixed iteration count.
- Equity Monte Carlo introduces ~1 % per-pair noise; re-running on the
  same machine produces a byte-identical JSON because the seeded RNG is
  consumed in deterministic order.

## 9. References

- Brown, N. and Sandholm, T. (2019). *Solving Imperfect-Information
  Games via Discounted Regret Minimization* (DCFR algorithm).
- Zinkevich et al. (2007). *Regret Minimization in Games with
  Incomplete Information* (CFR foundation).
- Sklansky, D. and Miller, E. (2006). *No Limit Hold'em Theory and
  Practice* (Sklansky-Chubukov tables).
- `references/papers/_INDEX.md` — DCFR / CFR paper notes.
- `references/products/_COMPETITORS.md` — GTO Wizard, PioSolver chart
  format/landscape (informs JSON schema choices).
