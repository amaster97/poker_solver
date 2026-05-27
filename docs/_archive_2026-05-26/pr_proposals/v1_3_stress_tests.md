# v1.3.0 — Range-vs-Range Stress Test Plan (Pre-Stage)

**Status:** Pre-stage. Apply when Plan C / Stage C1 lands the
range-vs-range exploitability path (vector-form BR via numpy or Rust).
Original framing referenced Option A + Option B; both superseded after
LEG 5 (see `v1_3_range_vs_range.md` Status header).
**Source:** Phase 1E heuristic table
(`docs/pr13_prep/phase1_extended_results.md`).

---

## Harness

Each scenario runs against **both** Option A
(`solve_hunl_postflop` with `initial_hole_cards=()` via the Rust
exploitability walk) and Option B
(`solve_range_vs_range(..., aggregate="class")`). Parity is a pass
criterion: aggregated frequencies agree within 3 pp absolute per
hand class. Budget < 2 min per run on Apple Silicon, 500 DCFR iters.

---

## Scenarios

### S1 — 100 BB SRP c-bet, dry K-high
**Spot:** BTN open 2.5x, BB call. Flop `As Ks 7h`. BTN to act.
**Heuristic:** dry, high-card-favored boards favor the small bet
(nut advantage preserved; protection demand low).
**Pass:** `bet33` >= 0.55, `bet75` <= 0.20, `check` in [0.20, 0.40].

### S2 — Same SRP, monotone `As 7s 2s`
**Heuristic:** monotone reduces both nut advantage and protection
need; small-bet meta dominates.
**Pass:** `bet33` >= `bet75` by >= 20 pp; `check` >= 0.35. Failure
means the API fix did not resolve W1E.3.

### S3 — 3-bet pot wet board
**Spot:** SB 3x, BB 3-bet 10x, SB call. Flop `4c 5d 6h`. SB to act.
**Heuristic:** wet board + capped SB range vs polarized BB range →
SB checks more (range-protection).
**Pass:** SB `check` >= 0.55; no single bet size > 0.30.

### S4 — River bluff-catcher MDF
**Spot:** Pot 100, stack 50. Villain bets exactly 50 (0.5 pot) into
BB's mixed bluff-catcher range.
**Heuristic:** MDF = pot / (pot + bet) = **66.7%**.
**Pass:** aggregate defend in [0.62, 0.71]. Single-combo W1E.4 hit
100%; 50-pp delta = hard fail.

### S5 — Equity floor sanity
**Spot:** Preflop all-in. AA (12 combos) vs top-50% range by
Sklansky-Chubukov.
**Heuristic:** AA vs top-50% >= **80%** equity.
**Pass:** equity in [0.80, 0.92]. Lightest scenario — failure means
range-iteration plumbing is broken.

### S6 — Triple-barrel polarization
**Spot:** Turn `As Kd 7h 2c`, river `5s` (brick runout). BTN fires
flop and turn, deciding river. Effective stacks ~1 pot.
**Heuristic:** river barrel sizing is **polarized**, not merged;
medium sizes leak EV on brick runouts.
**Pass:** `bet25 > 0.10` AND `bet150+ > 0.10` AND `bet66 < 0.10`.

### S7 — BB defend vs SB minraise
**Spot:** Preflop, SB open 2.0x, BB to act, 100 BB.
**Heuristic:** pot odds 1:3 → MDF ≈ **66.7%**. BB folds ~33%, calls
~50%, 3-bets ~17%.
**Pass:** aggregate (call + 3-bet) across the 1326-combo grid in
[0.62, 0.71]. W2.3 single-combo returned 100% defend on every
playable hand; gates that regression.

### S8 — Suit-aware blocker sensitivity
**Spot:** River `Ah Kh 7h 2c 3d` (flush completed). BB faces 75%
pot. Range includes `AhAd` (nut-flush blocker), `AsAd`, `KsKc`.
**Heuristic:** `AhAd` calls near 100%; `KsKc` lowest; gap > 25 pp.
**Pass:** combo-mode passes the 25-pp gap. Class-mode is expected
to fail (document as known limit in USAGE §5.2); combo-mode failure
invalidates Option B.

---

## Timing budgets and likely failure modes

| ID | Budget | Likely failure |
|----|--------|----------------|
| S1 | 90 s  | A: chance enum too slow |
| S2 | 90 s  | B: monotone sizing regression |
| S3 | 120 s | B: aggregation drops overbet arm |
| S4 | 60 s  | MDF skewed (W1E.4 regression) |
| S5 | 10 s  | Range plumbing broken (smoke) |
| S6 | 120 s | B class-mode: bluff arm under-weighted |
| S7 | 90 s  | A: preflop chance enum prohibitively slow |
| S8 | 120 s | Combo-mode: blocker resolution |

---

## Acceptance gate

To tag v1.3.0: **S1–S7 pass on both Option A and Option B
(`aggregate="class"`)**; **S8 passes on `aggregate="combo"`**, with
class-mode failure documented in USAGE §5.2.

Record measured wall-clocks. Per the no-extrapolation rule, do not
ship on microbenchmark projections.
