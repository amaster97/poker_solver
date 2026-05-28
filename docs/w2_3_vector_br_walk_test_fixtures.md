# Vector-form BR walk test fixture matrix (W2.3, #66 follow-up)

**Status:** DESIGN — fixture spec for the in-flight vector-form best-response (BR)
walk refactor inside `crates/cfr_core/src/exploit.rs`. Implementation agent `a2` is
spinning up the vector path alongside the canonical per-combo walk. This document
specifies the fixture matrix that the implementer should use to **diff-test** the
new vector path against the canonical reference.

**Scope.** This is a design doc only — no Rust, no test code. The matrix below
defines fixture inputs + expected behavior + tolerances so that:

1. `a2` knows exactly which fixtures must produce bit-identical output;
2. independent validation can re-run the matrix without reading `a2`'s diff
   (per memory rule `feedback_independent_verification` — independent diff-test
   before verdicts trigger release; the hard-FAIL outcome is the hypothesis,
   not the conclusion, until an unrelated reviewer reproduces it);
3. reviewers have a single ground-truth list to crosscheck against the
   implementation PR's test additions.

**Equivalence contract** (W2.3 strict-PASS closure criterion):

| Quantity | Tolerance | Rationale |
|---|---|---|
| Exploitability (BB/hand) | `1e-9` | Mirrors `flat_tree_matches_recursive_aggregate_on_river` strict-equality clause in `exploit.rs` |
| Per-player game value (BB/hand) | `1e-12` | Float reordering bound — vector ops should preserve DFS-sum order |
| Per-combo BR action choice | exact integer | argmax must agree node-for-node |
| Per-infoset BR EV | `1e-12` | Same as game value |

Any fixture that fails these bounds is a HARD-FAIL — the refactor regressed.

**Reference path** (canonical, single source of truth):
`compute_exploitability_and_value` (line 78, `exploit.rs`) →
`flat_tree_exploit` (line 1003) → `flat_collect_br_fused` /
`flat_br_value_unweighted` (lines 1160+ and 1263+ post-PR #162).

**Refactor surface** (what `a2` is changing):
Replace the per-combo loop in `flat_collect_br_fused` with a **vector-form pass**
that hoists the combo iteration inside the recursion (one walk down the tree,
operating on all combos as a slice/SIMD vector at each node). Bit-identical
output required.

---

## Fixture conventions

- **ID** — `F<category>.<seq>`. Stable across the document.
- **Config** — `HUNLConfig(...)` (Rust struct) or `KuhnPoker()` / `LeducPoker()`
  (Python game class) per category. All BB amounts in chips with BB=100 unless
  noted (so `starting_stack=20_000` means 200 BB).
- **Strategy seed** — what gets passed as the `strategy: HashMap<String, Vec<f64>>`:
  - `EMPTY` — `{}`, exercises the uniform-fallback path inside `DecisionStrategyTable.probs`.
  - `SOLVED(iter=N, backend=X)` — output of `solve(game, iterations=N, backend=X)`'s
    `.average_strategy`, converted to `{k: list(v) for k,v in ...}`.
  - `HAND_CRAFTED(...)` — explicit dict described in the fixture.
- **Expected** — qualitative invariants the vector walk MUST preserve. These are
  REFERENCE-DERIVED — i.e., they must hold on the canonical per-combo walk first,
  and the vector walk's job is to reproduce them within tolerance.
- **Wall (canonical)** — measured or budgeted wall-clock for the per-combo BR walk
  on an M-series Mac. Budget figures (no leading measurement) flagged with `[B]`.

---

## Category 1 — Canonical small games (smoke)

### F1.1 — Kuhn poker baseline

| Field | Value |
|---|---|
| Category | canonical small games |
| Config | `KuhnPoker()` |
| Iter | 1000 |
| Strategy seed | `SOLVED(iter=1000, backend="python")` |
| Expected | exploitability < 5e-3 (known Kuhn convergence band at 1k iter); `"13|"` BET prob > 0.6; `"12|"` BET prob < 0.1; vector ↔ canonical BR EV match within 1e-12 per infoset |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~0.05 s `[B]` |

### F1.2 — Kuhn poker converged

| Field | Value |
|---|---|
| Category | canonical small games |
| Config | `KuhnPoker()` |
| Iter | 50000 |
| Strategy seed | `SOLVED(iter=50000, backend="python")` |
| Expected | exploitability < 5e-3 (matches `test_kuhn_exploitability_below_threshold`); `game_value` ≈ `kuhn_nash_value()` ± 5e-3; algebraic Nash constraint `alpha + 1/3 ≈ p1_call_Q` (cf. `test_kuhn_bluff_calling_nash_relationship`) preserved |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~1.0 s `[B]` |

### F1.3 — Leduc poker baseline

| Field | Value |
|---|---|
| Category | canonical small games |
| Config | `LeducPoker()` |
| Iter | 1000 |
| Strategy seed | `SOLVED(iter=1000, backend="python")` |
| Expected | exploitability < 0.1 BB at 1k iter; multi-round (preflop + flop) BR walk produces the same EV as canonical; vector path must traverse both rounds in same order |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~0.5 s `[B]` |

### F1.4 — Leduc poker converged

| Field | Value |
|---|---|
| Category | canonical small games |
| Config | `LeducPoker()` |
| Iter | 100000 |
| Strategy seed | `SOLVED(iter=100000, backend="python")` |
| Expected | exploitability < 5e-3; matches `tests/test_leduc_dcfr.py` invariants; multi-round BR fixed-point iteration count identical between vector and canonical |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~10 s `[B]` |

### F1.5 — Tiny pushfold

| Field | Value |
|---|---|
| Category | canonical small games |
| Config | `solve_pushfold(stack_bb=10, big_blind=1, small_blind=0.5)` → underlying HUNLConfig (preflop only, no raises beyond shove/call/fold) |
| Iter | 5000 |
| Strategy seed | `SOLVED(iter=5000, backend="python")` |
| Expected | exploitability < 1e-4 (pushfold is essentially closed-form); AA → 100% push; 32o → 100% fold; vector and canonical agree on action-mass per hand class within 1e-12 |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~0.1 s `[B]` |

---

## Category 2 — HUNL river chance-enum

All fixtures: `starting_street=Street.RIVER`, `initial_pot=1000`,
`initial_contributions=[500,500]`, BB=100, `starting_stack=1000`,
`bet_size_fractions=[0.5, 1.0]`, `postflop_raise_cap=3`,
`initial_hole_cards=None` (chance-enum-at-root path → `flat_tree_exploit`).

`HAND_CLASSES_3 = ["AA", "KK", "QQ"]`,
`HAND_CLASSES_8 = HAND_CLASSES_3 + ["JJ", "AKs", "AKo", "AQs", "AQo"]`,
`HAND_CLASSES_169` = full 169-class grid.

### F2.1 — 3-class river dry (K72)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `K♣ 7♦ 2♥` + turn `T♠` + river `4♣` → `Kc 7d 2h Ts 4c` |
| Strategy seed | `SOLVED(iter=10, backend="rust")` over `HAND_CLASSES_3` |
| Expected | low exploitability after 10 iter (small tree); AA → near-100% value-bet on river; bit-identical exploitability vector ↔ canonical |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F2.2 — 3-class river wet (Js8c6h)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `J♠ 8♣ 6♥` + turn `4♦` + river `2♠` → `Js 8c 6h 4d 2s` |
| Strategy seed | `SOLVED(iter=10, backend="rust")` over `HAND_CLASSES_3` |
| Expected | similar shape to F2.1; wet board → more thin value-bet mixing in BR action |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F2.3 — 3-class river paired (KKx)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `K♣ K♦ 7♥` + turn `2♠` + river `5♦` → `Kc Kd 7h 2s 5d` |
| Strategy seed | `SOLVED(iter=10, backend="rust")` over `HAND_CLASSES_3` |
| Expected | board pairs interact with combo blockers; AA must NOT fold on river; vector walk's combo-vector slicing must respect blocker exclusions (no double-counting Kc/Kd) |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F2.4 — 8-class river dry (K72)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Kc 7d 2h Ts 4c` |
| Strategy seed | `SOLVED(iter=100, backend="rust")` over `HAND_CLASSES_8` |
| Expected | medium-scale check; vector path's per-class throughput should hit ≥2× canonical; bit-identical exploitability output |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

### F2.5 — 8-class river wet (Js8c6h)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Js 8c 6h 4d 2s` |
| Strategy seed | `SOLVED(iter=100, backend="rust")` over `HAND_CLASSES_8` |
| Expected | as F2.4 plus heavier-mixing infosets on wet runout |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

### F2.6 — 8-class river paired (KKx)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Kc Kd 7h 2s 5d` |
| Strategy seed | `SOLVED(iter=100, backend="rust")` over `HAND_CLASSES_8` |
| Expected | blockers are dense (board uses both Kings); vector walk's hole-index mask must filter every combo that conflicts |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

### F2.7 — 169-class river dry (K72)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Kc 7d 2h Ts 4c` |
| Strategy seed | `SOLVED(iter=500, backend="rust")` over `HAND_CLASSES_169` |
| Expected | full-scale gate; vector walk must match canonical on **every** infoset's BR action (any single argmax disagreement = HARD-FAIL); wall-clock target: ≤30 % of canonical |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~3 min `[B]` |

### F2.8 — 169-class river wet (Js8c6h)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Js 8c 6h 4d 2s` |
| Strategy seed | `SOLVED(iter=500, backend="rust")` over `HAND_CLASSES_169` |
| Expected | as F2.7 — full grid; the most diverse mixing infosets surface here |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~3 min `[B]` |

### F2.9 — 169-class river paired (KKx)

| Field | Value |
|---|---|
| Category | river chance-enum |
| Board | `Kc Kd 7h 2s 5d` |
| Strategy seed | `SOLVED(iter=500, backend="rust")` over `HAND_CLASSES_169` |
| Expected | hardest blocker fixture in this group; KK combos blocked by board; AKo/AKs reduced; vector slice mask must zero out 100 % of conflicting combos |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~3 min `[B]` |

---

## Category 3 — HUNL turn (where W2.3 lives)

All fixtures: `starting_street=Street.TURN`, `initial_pot=1000`,
`initial_contributions=[500,500]`, BB=100, `bet_size_fractions=[0.5, 1.0]`,
`postflop_raise_cap=3`, `initial_hole_cards=None`,
`compute_exploitability_at_end=True`. Hand classes
`HAND_CLASSES_8` unless noted.

The W2.3 canonical fixture (F3.1) is taken from
`scripts_retest/w2_1_w2_3_post_5pr_retest.py`: turn `Q♠ 7♥ 2♦ 5♣`, 200 BB,
8-class. The other variants probe sensitivity along the two axes the vector
refactor is most likely to perturb: **turn-card texture** and **stack depth**.

### F3.1 — W2.3 reference (Qs 7h 2d 5c, 200 BB, 8-class, iter=100)

| Field | Value |
|---|---|
| Category | turn (W2.3 reference) |
| Board | `Q♠ 7♥ 2♦ 5♣` |
| Starting stack | 20000 (200 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | this is the W2.3 strict-PASS gate; exploitability must match canonical to within 1e-9 BB; AA/KK should not fold on turn; turn → river chance enumeration (45 unseen cards) handled per combo |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~12 min `[B]` (pre-vector; the gate vector should bring < 60 s) |

### F3.2 — Turn boat-completing (Qs 7h 2d 5h → swap to 5h, Qs paired with…)

Actually: vary turn card to `5h` (paired with the river-target). Use
board `Qs 7h 2d 5h`. The 5h opens flush-draw chops with 8c6h pattern when the
river falls — exercises a different distribution of terminal showdown classes.

| Field | Value |
|---|---|
| Category | turn variant |
| Board | `Q♠ 7♥ 2♦ 5♥` |
| Starting stack | 20000 (200 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | flush-draw classes mix bet/check; AA still strong but down-weighted vs flush completion; vector walk must reproduce canonical mixing fractions |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~12 min `[B]` |

### F3.3 — Turn straight texture (9d turn)

Vary turn to `9d` on `Qs 7h 2d` → board `Qs 7h 2d 9d`. The 9d adds gutshot
JT and 86 combos, plus 2-card flush draw on diamonds. Different straight/flush
mass than the reference.

| Field | Value |
|---|---|
| Category | turn variant |
| Board | `Q♠ 7♥ 2♦ 9♦` |
| Starting stack | 20000 (200 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | more interactive turn — JTs/JTo/T9s in the mix should not fold to small bets; vector ↔ canonical on every class's action mass |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~12 min `[B]` |

### F3.4 — Stack depth 50 BB (W2.3 board)

| Field | Value |
|---|---|
| Category | turn — stack depth variant |
| Board | `Q♠ 7♥ 2♦ 5♣` |
| Starting stack | 5000 (50 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | shallower → more pot-committed lines; action depths shorter; vector walk's tree-size must match canonical exactly (different stack = different terminal layout) |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~8 min `[B]` |

### F3.5 — Stack depth 100 BB (W2.3 board)

| Field | Value |
|---|---|
| Category | turn — stack depth variant |
| Board | `Q♠ 7♥ 2♦ 5♣` |
| Starting stack | 10000 (100 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | the most common pro-poker stack depth; benchmark sanity case |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~10 min `[B]` |

### F3.6 — Stack depth 200 BB (== F3.1 cross-check)

This is a sanity duplicate of F3.1 — included so the matrix has a continuous
50/100/200 BB sweep. Implementer may collapse if they want (notes: F3.1 ≡ F3.6).

| Field | Value |
|---|---|
| Category | turn — stack depth variant |
| Board | `Q♠ 7♥ 2♦ 5♣` |
| Starting stack | 20000 (200 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | identical to F3.1; redundancy intentional |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~12 min `[B]` |

---

## Category 4 — HUNL flop

All fixtures: `starting_street=Street.FLOP`, `initial_pot=200`,
`initial_contributions=[100,100]`, BB=100, `bet_size_fractions=[0.5, 1.0]`,
`postflop_raise_cap=3`, `initial_hole_cards=None`, 100 BB, 8 hand classes,
iter=50. Smaller iter than turn to bound wall time at this scale (flop has
both turn and river chance nodes downstream).

### F4.1 — Standard flop (Qh7c2d)

| Field | Value |
|---|---|
| Category | flop |
| Board | `Q♥ 7♣ 2♦` |
| Starting stack | 10000 (100 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 50 |
| Strategy seed | `SOLVED(iter=50, backend="rust")` |
| Expected | classic dry-ish board; AA/KK/QQ → near-100 % defend (matches Sarah's persona spec for KK on Q-high); vector ↔ canonical exact on aggregate exploit |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~6 min `[B]` |

### F4.2 — Wet flop (JsTs9h)

| Field | Value |
|---|---|
| Category | flop |
| Board | `J♠ T♠ 9♥` |
| Starting stack | 10000 (100 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 50 |
| Strategy seed | `SOLVED(iter=50, backend="rust")` |
| Expected | flush-draw + straight-draw heavy; deep tree with frequent mixing; vector walk's combo-vector index must respect blockers (JsTs9h removes both ♠ and the JT9 ranks from the deck for opponent) |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~7 min `[B]` |

### F4.3 — Static flop (Kc7s2d)

| Field | Value |
|---|---|
| Category | flop |
| Board | `K♣ 7♠ 2♦` |
| Starting stack | 10000 (100 BB) |
| Hand classes | `HAND_CLASSES_8` |
| Iter | 50 |
| Strategy seed | `SOLVED(iter=50, backend="rust")` |
| Expected | bot-friendly static board (no draws); near-pure-strategy decision trees; vector ↔ canonical must match even when most action masses are 0 or 1 (no numerical-mixing slack to hide drift) |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~6 min `[B]` |

---

## Category 5 — Edge cases

### F5.1 — All-in preflop (effectively terminal)

| Field | Value |
|---|---|
| Category | edge |
| Config | HUNLConfig: `starting_street=Street.PREFLOP`, `starting_stack=1000`, BB=100, `initial_pot=300`, `initial_contributions=[1000,1000]` (already all-in), `initial_hole_cards=None`, `bet_size_fractions=[1.0]`, `preflop_raise_cap=4` |
| Iter | 1 |
| Strategy seed | `EMPTY` |
| Expected | tree collapses to a single chance node (preflop → flop → turn → river runout); BR walk is essentially a chance-enum sum; vector and canonical both produce the same EV (mean over all-in equities) |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~30 s `[B]` |

### F5.2 — Pure-strategy infosets (no mixing)

| Field | Value |
|---|---|
| Category | edge |
| Config | F2.1 (3-class river dry, K72) |
| Iter | n/a |
| Strategy seed | `HAND_CRAFTED`: for every infoset key in the tree, set action probs to `[1.0, 0.0, ..., 0.0]` (always fold/check, depending on first legal action). I.e., the trivial degenerate policy. |
| Expected | every BR decision is also trivially argmax (the single non-zero action); no mixing → no float-cancellation; vector and canonical must produce **bit-identical** exploit (single-action policies have zero floating-point rounding from the strategy weights) |
| Tolerance | **bit-identical** (`.to_bits()` equality), no float tolerance |
| Wall (canonical) | ~1 s `[B]` |

### F5.3 — Heavily mixed infosets (50/50 across 4+ actions)

| Field | Value |
|---|---|
| Category | edge |
| Config | F2.4 (8-class river dry, K72) |
| Iter | n/a |
| Strategy seed | `HAND_CRAFTED`: for every infoset key in the tree, set action probs to uniform `[1/n_actions; n_actions]`. With `bet_size_fractions=[0.5,1.0]` + `postflop_raise_cap=3`, decision infosets have 4–6 actions → max-entropy strategy. |
| Expected | most error-prone configuration: every action carries non-negligible mass, so vector-form floating-point cancellation is at its worst. Vector walk's per-action accumulation must preserve canonical's DFS sum order. |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

### F5.4 — Adversarial near-degenerate (near-100 % fold)

| Field | Value |
|---|---|
| Category | edge — numerical bounds |
| Config | F2.4 (8-class river dry, K72) |
| Iter | n/a |
| Strategy seed | `HAND_CRAFTED`: for every infoset key, set action probs to `[1.0 - 1e-13, 1e-13/(n-1), 1e-13/(n-1), ...]` (FOLD ≈ 1, all other actions ≈ 1e-13). Probabilities still sum to 1.0 within float epsilon. |
| Expected | stresses vector-form ops at the numerical floor: products of probabilities collapse to ~`1e-13^depth` quickly. Canonical and vector must agree on the final exploit value within tolerance even when intermediate values underflow. |
| Tolerance | 1e-9 exploitability, **1e-9 EV** (loosened from 1e-12 — underflow expected; bit-identical not achievable) |
| Wall (canonical) | ~15 s `[B]` |

### F5.5 — Empty action history (root only)

| Field | Value |
|---|---|
| Category | edge |
| Config | F2.1 (3-class river dry) but with `bet_size_fractions=[]` and `postflop_raise_cap=0` → only check/check available at root → immediate showdown |
| Iter | n/a |
| Strategy seed | `EMPTY` |
| Expected | tree has 1 decision node → 1 showdown leaf per combo; BR walk is trivial; vector and canonical produce bit-identical exploit (no mixing, no recursion depth) |
| Tolerance | **bit-identical** |
| Wall (canonical) | < 0.5 s `[B]` |

### F5.6 — Maximum action depth (preflop_raise_cap=4, all raises)

| Field | Value |
|---|---|
| Category | edge |
| Config | HUNLConfig: `starting_street=Street.PREFLOP`, `starting_stack=20000` (200 BB), BB=100, `initial_pot=150`, `initial_contributions=[50,100]`, `initial_hole_cards=None`, `bet_size_fractions=[1.0, 2.0]`, `preflop_raise_cap=4`, `postflop_raise_cap=4`, `include_all_in=true`, classes `["AA"]` |
| Iter | 10 |
| Strategy seed | `SOLVED(iter=10, backend="rust")` |
| Expected | deepest action tree the engine supports; BR fixed-point iteration on multi-round game; vector walk must traverse same depth as canonical and converge in same number of iterations |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~30 s `[B]` |

---

## Category 6 — Numerical stress

### F6.1 — iter=1 (single update, diff vs fresh strategy)

| Field | Value |
|---|---|
| Category | numerical |
| Config | F2.1 (3-class river dry) |
| Iter | 1 |
| Strategy seed | `SOLVED(iter=1, backend="rust")` |
| Expected | strategy is essentially uniform + one tiny CFR update; mixing fractions are far from 0/1; vector ↔ canonical exact within tolerance |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F6.2 — iter=50000 (fully converged)

| Field | Value |
|---|---|
| Category | numerical |
| Config | F2.1 (3-class river dry) |
| Iter | 50000 |
| Strategy seed | `SOLVED(iter=50000, backend="rust")` |
| Expected | converged strategy → most infoset action probs are extremal (near 0 or near 1); few interior-point mixing — different rounding profile than F5.3. Vector must reproduce. Exploitability should be < 0.01 BB. |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~20 s (10 s solve + 2 s walk × ~5 from running it both ways) `[B]` |

### F6.3 — iter=10 mid-iter snapshot

| Field | Value |
|---|---|
| Category | numerical |
| Config | F2.1 (3-class river dry) |
| Iter | 10 |
| Strategy seed | `SOLVED(iter=10, backend="rust")` |
| Expected | early-CFR strategy with active mixing; vector ↔ canonical exact |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F6.4 — iter=100 mid-iter snapshot

| Field | Value |
|---|---|
| Category | numerical |
| Config | F2.1 (3-class river dry) |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust")` |
| Expected | mid-CFR — interesting drift regime |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~2 s `[B]` |

### F6.5 — iter=1000 mid-iter snapshot

| Field | Value |
|---|---|
| Category | numerical |
| Config | F2.1 (3-class river dry) |
| Iter | 1000 |
| Strategy seed | `SOLVED(iter=1000, backend="rust")` |
| Expected | strategy approaching stability |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~3 s `[B]` |

### F6.6 — DCFR canonical weighting α=1.5, β=0, γ=2

| Field | Value |
|---|---|
| Category | numerical — weighting |
| Config | F2.4 (8-class river dry) with DCFR params `alpha=1.5, beta=0.0, gamma=2.0` (canonical Brown DCFR) |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust", dcfr_alpha=1.5, dcfr_beta=0.0, dcfr_gamma=2.0)` |
| Expected | the canonical Brown DCFR weighting — production default; vector ↔ canonical exact |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

### F6.7 — DCFR α=0, β=0, γ=2 (PR #74 fixed weighting)

| Field | Value |
|---|---|
| Category | numerical — weighting |
| Config | F2.4 (8-class river dry) with DCFR params `alpha=0.0, beta=0.0, gamma=2.0` |
| Iter | 100 |
| Strategy seed | `SOLVED(iter=100, backend="rust", dcfr_alpha=0.0, dcfr_beta=0.0, dcfr_gamma=2.0)` |
| Expected | non-default but supported weighting (PR #74 fixed a guard around α=0); the BR walk is downstream of the weighting choice but the produced strategy is different shape → exercises the vector walk on a different infoset distribution. |
| Tolerance | 1e-9 exploitability, 1e-12 EV |
| Wall (canonical) | ~15 s `[B]` |

---

## Summary table — all 30 fixtures

| ID | Category | Iter | Hand classes | Board / config | Wall (canonical) |
|---|---|---|---|---|---|
| F1.1 | small game | 1k | Kuhn 3 | KuhnPoker() | 0.05 s |
| F1.2 | small game | 50k | Kuhn 3 | KuhnPoker() | 1.0 s |
| F1.3 | small game | 1k | Leduc 6 | LeducPoker() | 0.5 s |
| F1.4 | small game | 100k | Leduc 6 | LeducPoker() | 10 s |
| F1.5 | small game | 5k | pushfold | 10 BB pushfold | 0.1 s |
| F2.1 | river enum | 10 | 3 | Kc 7d 2h Ts 4c | 2 s |
| F2.2 | river enum | 10 | 3 | Js 8c 6h 4d 2s | 2 s |
| F2.3 | river enum | 10 | 3 | Kc Kd 7h 2s 5d | 2 s |
| F2.4 | river enum | 100 | 8 | Kc 7d 2h Ts 4c | 15 s |
| F2.5 | river enum | 100 | 8 | Js 8c 6h 4d 2s | 15 s |
| F2.6 | river enum | 100 | 8 | Kc Kd 7h 2s 5d | 15 s |
| F2.7 | river enum | 500 | 169 | Kc 7d 2h Ts 4c | ~3 min |
| F2.8 | river enum | 500 | 169 | Js 8c 6h 4d 2s | ~3 min |
| F2.9 | river enum | 500 | 169 | Kc Kd 7h 2s 5d | ~3 min |
| F3.1 | turn (W2.3) | 100 | 8 | Qs 7h 2d 5c, 200 BB | ~12 min |
| F3.2 | turn variant | 100 | 8 | Qs 7h 2d 5h, 200 BB | ~12 min |
| F3.3 | turn variant | 100 | 8 | Qs 7h 2d 9d, 200 BB | ~12 min |
| F3.4 | turn (50 BB) | 100 | 8 | Qs 7h 2d 5c, 50 BB | ~8 min |
| F3.5 | turn (100 BB) | 100 | 8 | Qs 7h 2d 5c, 100 BB | ~10 min |
| F3.6 | turn (200 BB) | 100 | 8 | Qs 7h 2d 5c, 200 BB | ~12 min |
| F4.1 | flop | 50 | 8 | Qh 7c 2d, 100 BB | ~6 min |
| F4.2 | flop | 50 | 8 | Js Ts 9h, 100 BB | ~7 min |
| F4.3 | flop | 50 | 8 | Kc 7s 2d, 100 BB | ~6 min |
| F5.1 | edge | 1 | enum | all-in preflop | ~30 s |
| F5.2 | edge | n/a | 3 | pure-strategy infosets | ~1 s |
| F5.3 | edge | n/a | 8 | uniform mixing | ~15 s |
| F5.4 | edge | n/a | 8 | near-100 % fold | ~15 s |
| F5.5 | edge | n/a | 3 | root only (no actions) | < 0.5 s |
| F5.6 | edge | 10 | 1 | preflop cap=4, AA only | ~30 s |
| F6.1 | numerical | 1 | 3 | iter=1 | ~2 s |
| F6.2 | numerical | 50k | 3 | iter=50000 | ~20 s |
| F6.3 | numerical | 10 | 3 | iter=10 | ~2 s |
| F6.4 | numerical | 100 | 3 | iter=100 | ~2 s |
| F6.5 | numerical | 1k | 3 | iter=1000 | ~3 s |
| F6.6 | numerical | 100 | 8 | DCFR 1.5/0/2 | ~15 s |
| F6.7 | numerical | 100 | 8 | DCFR 0/0/2 | ~15 s |

**Total fixtures: 36** (above the 25-minimum target).

**Estimated total wall time if all run sequentially** (canonical walk only,
adding both seed-solve and BR-walk passes where applicable):

- Category 1: ~12 s
- Category 2: ~9.1 min (3 × 169-class fixtures dominate at ~3 min each)
- Category 3: ~66 min (6 turn fixtures × ~11 min avg)
- Category 4: ~19 min
- Category 5: ~1.3 min
- Category 6: ~70 s

**Grand total: ~98 minutes wall-clock for one canonical pass over all 36
fixtures.** The vector-form walk is expected to bring this under 30 min in
aggregate (the turn fixtures account for two-thirds of the canonical budget
and are the largest single-pass speedups the refactor targets).

For diff-test purposes the implementer should expect ~2× this number if both
canonical and vector are run head-to-head — call it **~3.5 hours** for the full
matrix. This is impractical for per-PR CI; see **kill-switch** below for the
subset that must run on every commit.

---

## Per-fixture test script template (Python pseudocode)

Each fixture follows the same diff harness. Below is a single template; the
implementer instantiates one test per fixture ID by substituting `<config>`,
`<seed>`, `<iter>`, `<tol_expl>`, `<tol_ev>`.

```python
# tests/test_vector_br_walk_diff.py — template (one test per fixture)

import importlib
import time
import pytest

from poker_solver import HUNLConfig, HUNLPoker, Street, parse_board, solve
from poker_solver.hunl import _serialize_hunl_config

_rust = importlib.import_module("poker_solver._rust")
_canonical_walk = _rust.compute_exploitability  # existing per-combo walk
_vector_walk = _rust.compute_exploitability_vector  # new vector path

def _make_config_<fixture_id>():
    # Substitute per fixture — board, stack, hole-card mode, etc.
    board = parse_board("<board_str>")
    return HUNLConfig(
        starting_stack=<stack>,
        big_blind=100,
        starting_street=Street.<STREET>,
        initial_board=tuple(board),
        initial_pot=<pot>,
        initial_contributions=(<c0>, <c1>),
        initial_hole_cards=<hole_or_None>,
        bet_size_fractions=<fractions>,
        postflop_raise_cap=<cap>,
    )

def _seed_strategy_<fixture_id>(cfg) -> dict:
    # Substitute per fixture seed mode (EMPTY / SOLVED / HAND_CRAFTED).
    game = HUNLPoker(cfg)
    result = solve(game, iterations=<iter>, backend="<backend>")
    return {k: list(v) for k, v in result.average_strategy.items()}

@pytest.mark.parametrize("fixture_id", ["<fixture_id>"])
def test_vector_matches_canonical_<fixture_id>(fixture_id):
    cfg = _make_config_<fixture_id>()
    strategy = _seed_strategy_<fixture_id>(cfg)
    cfg_json = _serialize_hunl_config(cfg)

    # Canonical walk (reference).
    t0 = time.perf_counter()
    can_out = _canonical_walk(cfg_json, strategy)
    can_elapsed = time.perf_counter() - t0

    # Vector walk (under test).
    t1 = time.perf_counter()
    vec_out = _vector_walk(cfg_json, strategy)
    vec_elapsed = time.perf_counter() - t1

    # Equivalence assertions — substitute tolerances per fixture.
    assert abs(can_out["exploitability"] - vec_out["exploitability"]) <= <tol_expl>, (
        f"<{fixture_id}> exploit drift: "
        f"canonical={can_out['exploitability']:.15f} "
        f"vector={vec_out['exploitability']:.15f} "
        f"delta={can_out['exploitability'] - vec_out['exploitability']:.3e}"
    )
    assert abs(can_out["game_value"] - vec_out["game_value"]) <= <tol_ev>, (
        f"<{fixture_id}> EV drift: "
        f"canonical={can_out['game_value']:.15f} "
        f"vector={vec_out['game_value']:.15f} "
        f"delta={can_out['game_value'] - vec_out['game_value']:.3e}"
    )
    # Optional perf assertion (kill-switch fixtures only).
    # assert vec_elapsed < can_elapsed, (
    #     f"<{fixture_id}> vector path slower than canonical: "
    #     f"vec={vec_elapsed:.2f}s can={can_elapsed:.2f}s"
    # )
```

For bit-identical fixtures (F5.2, F5.5) replace the float compare with:

```python
import struct
def _bits(x: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", x))[0]
assert _bits(can_out["exploitability"]) == _bits(vec_out["exploitability"])
```

---

## Kill-switch criterion — minimum fixtures that MUST pass before merge

The full 36-fixture matrix takes hours to run head-to-head. For per-commit CI
and for the merge gate, the following **8 fixtures form the kill-switch**:

| ID | Reason it's load-bearing |
|---|---|
| **F1.1** Kuhn baseline | sanity smoke; if this fails the vector walk is fundamentally broken |
| **F1.3** Leduc baseline | first multi-round (preflop + flop) coverage — proves vector walk handles BR fixed-point iteration |
| **F2.4** 8-class river dry | the workhorse 8-class river — closest to W2.3 in algorithmic shape, cheap enough to gate every commit |
| **F3.1** W2.3 reference (Qs 7h 2d 5c, 200 BB) | THE strict-PASS target — non-negotiable |
| **F4.1** Standard flop (Qh7c2d) | covers flop chance node + multi-street BR walk; matches Sarah's persona |
| **F5.2** Pure-strategy edge | bit-identical gate — catches argmax/order bugs that float tolerance hides |
| **F5.3** Heavily mixed edge | catches DFS-sum reordering — the most likely source of vector ↔ canonical drift |
| **F6.7** DCFR α=0 weighting | guards against PR #74-style weighting regressions on the BR walk path |

**Merge gate:** all 8 kill-switch fixtures must pass within their stated
tolerances. Any single failure HARD-FAILS the merge per the engine-code-change
protocol.

**Pre-merge soak** (recommended, off-CI): run the full 36-fixture matrix once
on a dedicated machine before the v1.8.3+ ship that includes the vector walk.
Budget ~4 hours including overhead. Per memory rule
`feedback_independent_verification`, this soak should be executed by a
**different agent / reviewer** than the one writing the vector walk, with
their own re-derivation of the canonical-walk reference values.

**Estimated kill-switch wall time:** F1.1 (0.05 s) + F1.3 (0.5 s) + F2.4 (15 s)
+ F3.1 (12 min) + F4.1 (6 min) + F5.2 (1 s) + F5.3 (15 s) + F6.7 (15 s) ≈
**~18.5 minutes** for one canonical pass, **~37 minutes** for both walks head-
to-head. This is the production CI budget for the merge gate.

---

## Notes for implementer `a2`

1. **Canonical reference is `flat_collect_br_fused`** (line 1160+, post-PR #162).
   The vector walk replaces the per-combo loop inside this function — every
   other call shape (input strategy dict, output `ExploitOutput`) must stay
   identical.
2. **HashMap iteration order** in the BR step is the only known float-
   reordering source (per `_EXPL_TOL` note in `tests/test_exploit_diff.py`).
   The vector walk must preserve canonical's iteration order — if you sort
   the infoset keys, sort canonical's too, otherwise the diff test threshold
   will need to widen and that's a regression in the equivalence contract.
3. **Bit-identical tier** is required for F5.2 and F5.5 (pure-strategy /
   trivial trees). If you can't produce bit-identical output on those, the
   vector implementation has reordered something a float-tolerant test misses.
4. **The 169-class fixtures (F2.7–F2.9)** are the highest-risk because they
   exercise the full hole-card combo grid the production GUI uses. Run these
   before claiming W2.3 strict-PASS — the 8-class fixtures (F2.4–F2.6 / F3.x)
   are necessary but not sufficient.
5. Independent re-derivation per memory rule `feedback_independent_verification`:
   the matrix above is the **hypothesis**; the actual reference values come from
   the canonical walk running on your branch. Don't trust hardcoded expected
   numbers — derive them every run.

---

## Cross-references

- W2.3 strict-PASS persona context: `docs/persona_status_2026-05-28-evening.md` (current, 17/0/0/0 post-PR-170); `docs/persona_status_2026-05-28-late.md` (prior, 16/1/0/0 with W2.3 still PARTIAL)
- Prior BR-walk perf PRs: PR #139 (terminal cache), PR #162 (non-terminal cache)
- Open PR for W2.3 unblock: GitHub PR #162 (`feat/br-walk-non-terminal-cache-task66`)
- Reference Rust source: `crates/cfr_core/src/exploit.rs` lines 1003–1350
- Reference Python source: `poker_solver/solver.py:_best_response_value`
- Existing diff harness: `tests/test_exploit_diff.py`
- Independent-verification protocol: memory rule `feedback_independent_verification`
