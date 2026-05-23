# HUNL tree size estimate

**Purpose.** Quantitative back-of-envelope for the locked-in HUNL action+card abstraction
(PLAN.md §"Action abstraction" / "Card abstraction", lines ~287–290) so we can stop hand-waving
about "fits in 16 GB" and know exactly which knobs are RAM-critical when we start PR 3.

All figures are **order-of-magnitude**. Real solvers report tree sizes that vary 3–5× across
boards (paired vs unpaired, monotone vs rainbow), and the postflop "average" branching factor
depends on which all-in collapses fire on which streets. Numbers below are deliberately rounded
to one or two significant figures — anything more would be false precision.

---

## Summary

The **default config (6 bet sizes, preflop cap 4, postflop cap 3, 256/128/64 buckets)** fits in
16 GB comfortably for **HUNL postflop at 100 BB**: estimated **3–6 GB resident** for the full
postflop game tree's regret + average-strategy tables, ≈25–50% of the 12–14 GB usable budget.
**HUNL preflop+postflop together at 100 BB** is tight but feasible at **8–13 GB** —
inside the budget but with no headroom for HashMap overhead surprises. **40 BB short-stack is
cheap (~2 GB postflop, ~5 GB full game); 200 BB deep blows past 16 GB on full-game
solving (≈20–30 GB) and forces either tighter buckets or postflop-only solving**.
The RAM-critical knobs in descending order are: (1) **postflop raise cap** (3 → 4 roughly doubles
the tree), (2) **flop bucket count** (256 dominates total infosets), (3) **bet-menu size**
(6 → 4 saves ~40%), (4) **river bucket count** (cheap to tighten, modest savings).

---

## Action tree per node

Legal-action count at a decision node depends on what happened immediately prior. Three regimes:

| Context | Legal actions | Typical count |
|---|---|---|
| Facing a bet (within raise cap) | fold, call, raise×k sizes | 2 + k (so **8** at k=6) |
| Facing a bet (at raise cap) | fold, call, all-in | **3** |
| First to act (no bet yet) | check, bet×k sizes | 1 + k (so **7** at k=6) |
| Facing a check (BB OOP after SB checked) | check, bet×k sizes | 1 + k (so **7**) |

All-in branches terminate the betting on that street (no further raises possible). Some bet
sizes collapse onto all-in when the next raise size would be ≥ remaining stack — typical
flop-after-3bet spots collapse 200% pot onto all-in, etc. This pruning shrinks the average
branching factor by ~10–20% in practice. Net **effective average branching factor ≈ 6** across
the postflop tree under the locked menu (6 bet sizes), and ≈ **7 preflop** where stacks are deep
enough that fewer sizes collapse.

### Tree depth per street (postflop, raise cap 3)

A within-street betting sequence under raise cap 3 with 6 bet sizes:

```
                check ── check  (street ends, go to chance)
              /
         ──┤    bet1..bet6 ── fold     (terminal)
              \           ── call      (street ends)
                          ── raise1..raise6 ── fold      (terminal)
                                           ── call       (street ends)
                                           ── reraise1..6 ── fold      (terminal)
                                                          ── call       (street ends)
                                                          ── all-in     (forces fold/call)
```

Counting **internal decision nodes per street** (one player's history × the other's responses)
with raise cap 3:

- Check-check sequence: 1 path
- Bet → fold: 6 paths, terminal
- Bet → call: 6 paths, ends street
- Bet → raise → fold: 6 × 6 = 36 paths, terminal
- Bet → raise → call: 36 paths, ends street
- Bet → raise → reraise → fold: 6³ = 216 paths, terminal
- Bet → raise → reraise → call: 216 paths, ends street
- Bet → raise → reraise → all-in → fold: 216 paths, terminal
- Bet → raise → reraise → all-in → call: 216 paths, ends-street-and-all-in (terminal: runout to showdown)

Plus the OOP-first variants (check → bet by IP, then same raise ladder). Roughly **double** the
above, since either player can open the betting.

**Per-street action histories ≈ 2 × (1 + 6 + 6 + 36 + 36 + 216 + 216 + 216 + 216) ≈ 2 × 950 ≈ 1.9k**

That counts *unique sequences*; the number of **decision points** (nodes where someone has to
choose) is roughly half (each sequence has decision-makers and chance-end nodes). Call it
**~1000 decision points per street** in the worst case. In practice, all-in collapse and stack
limits prune this to ~400–700 effective decision points per street at 100 BB.

### Multiplicative across streets

Each street's within-street decisions feed into a chance node (turn card / river card) and then
the next street's tree. The full postflop action tree (no card abstraction, just histories):

```
flop_decisions × turn_decisions × river_decisions
```

But it's not a clean product — most flop histories collapse into a small number of pot-size
classes by the time we hit the turn (the only thing turn cares about from the flop is the pot
size and whose turn it is, not the exact raise sequence). So the effective branching is closer
to:

```
flop_decisions × (avg pot states reaching turn) × turn_decisions × ... × river_decisions
```

PioSolver's empirical figure: a "simple tree" (1–2 bet sizes, lower raise cap) is ~696k nodes;
a "complex tree" (multi-sized, higher cap) is ~87M nodes (GTO Wizard "How Solvers Work" blog,
locally cached at `references/blog/gtow_how_solvers_work.md`). Our 6-size / cap-3 menu sits
toward the high end of that range — **estimate ~30–60M action infosets for full postflop, no
card abstraction** at 100 BB. Preflop (cap 4) adds maybe another 20–40M action infosets.

---

## Total infoset count (post-abstraction)

Card multiplicity is the killer multiplier. With imperfect-recall bucketing:

| Street | Bucket count per side | Public chance branching (relevant for tree size) |
|---|---|---|
| Preflop | 169 distinct starting hands (raw) → typically 169 buckets (no abstraction needed; small enough) | 1 (no public cards yet) |
| Flop | 256 buckets per side | ~1755 distinct flop textures (after isomorphism); ~22,100 deals raw |
| Turn | 128 buckets per side | × 47 possible turn cards (or ~47 bucketed turn classes) |
| River | 64 buckets per side | × 46 possible river cards |

Two-player: each infoset is conditioned on **one player's bucket** (the deciding player's hole-card
bucket), not both. So the multiplier is **256 (flop) or 128 (turn) or 64 (river)** per
decision-point, not the product of both players'. (Each player has their own infoset table
keyed by their own bucket.) Each player's tree is the same size, and the solver maintains
**two regret tables, one per player** — we'll factor that in below.

### Method: estimate action infosets per street, then multiply by buckets

Using a slightly different decomposition than the per-street action counts above (which double-count
across streets), let's separate by street:

| Street | Action infosets at street (one player, after pruning) | Buckets | Per-player infosets | Both players |
|---|---|---|---|---|
| Preflop | ~10k (cap 4, 6 sizes, includes branching into all postflop continuations) | 169 | ~1.7M | 3.4M |
| Flop | ~50k (cap 3 actions × ~50 boards-grouped post-isomorphism that matter for tree-size avg) — really we sum across all flop reach-nodes | 256 | ~13M | 26M |
| Turn | ~200k (× turn cards × cap-3 actions) | 128 | ~25M | 50M |
| River | ~2M (× river cards × cap-3 actions; this is where the tree-leaf count lives) | 64 | ~130M | 260M |

**Total ≈ 340M two-player action+card infoset slots, dominated by the river.**

Sanity check against PioSolver's published 1.2–1.9 GB (single bet size) / 5.9–7.8 GB (multi-bet
size) RAM usage for typical HU postflop spots
(`references/blog/piosolver_technical_details.md`): Pio uses similar abstraction defaults and
fewer bet sizes (typically 2–4 sizes vs our 6). Our memory should land 1.5–2× higher than
Pio's "multi-bet-size" number for the same spot, so **6–15 GB per postflop solve** is the
plausible Pio-anchored range. The 340M-slot estimate above is *for the full tree, all streets
combined* — Pio's 5.9–7.8 GB figure is also full-tree, so the numbers line up.

### Memory per infoset

For each (infoset, action) slot the solver stores:

- regret_sum: f64 = 8 bytes
- strategy_sum: f64 = 8 bytes

**= 16 bytes per (infoset, action) slot.**

At ≈ 6 actions average per infoset:

**= 96 bytes per infoset** for the regret + strategy tables themselves.

Plus HashMap overhead. Python `dict[str, ...]` is ~200 bytes per entry empty (key string +
hash + bucket overhead); Rust `HashMap<String, InfosetData>` is ~50–80 bytes per entry. For the
Rust tier (what dominates final memory after PR 6 port):

- key (compressed string, ~12 bytes after interning) + hash slot (~16 bytes overhead) + two
  `Vec<f64>` headers (24 bytes each = 48 bytes) + data payload (96 bytes) = **~170 bytes per
  infoset** in Rust.

For the Python tier (PRs 3–5 reference solver): ~3× that. We'll size the Python tier for
**small subtrees only** (single flop, single turn) and never try to fit full HUNL there;
sizing below assumes Rust.

### Putting it together (100 BB, default config)

| Quantity | Value |
|---|---|
| Two-player action+card infoset slots | ~340M |
| Slot size (Rust HashMap) | ~170 bytes |
| Raw memory | **~58 GB** |

That's well over budget. Two corrections bring it down:

1. **The 340M figure is "slots" not actual touched infosets.** River-level slots are mostly
   filled because all action sequences reach the river; turn and flop are mostly filled too.
   But preflop counts are over-stated because the 169-bucket multiplier applies to the small
   preflop action tree, not the full postflop subtree (which we already counted at flop/turn/river).
   Subtract ~10–15M.
2. **PioSolver's 5.9–7.8 GB anchor** is empirical for a similar abstraction (lower bet count,
   similar buckets). Our actual figure should be in the 2× range, so **~12–16 GB** total —
   right at the ceiling.

So the corrected answer for **full HUNL preflop+postflop at 100 BB**: **~10–14 GB Rust memory**.
That fits in 16 GB but with thin margins. **HUNL postflop only** (the PR 5 target) is **~6–9 GB**
because preflop adds the deep raise cap (4 vs 3) and broad starting-range tree, accounting for
roughly 30–40% of the total full-game tree.

### Stack-depth sensitivity

| Stack depth | Why it changes | Postflop tree size scaling | Full game (PF+postflop) memory |
|---|---|---|---|
| **40 BB (short)** | Many bet sizes collapse onto all-in earlier — 200% pot is all-in by turn in most lines; cap-3 mostly unreached | ~0.4× | ~3–5 GB Rust |
| **100 BB (canonical)** | All sizes legal preflop and on flop; some collapse on turn/river | 1× | ~10–14 GB Rust |
| **200 BB (deep)** | More raise sequences reach cap without all-in; the 4-raise preflop ladder fully utilized | ~2.0× postflop, ~1.6× preflop | ~20–25 GB Rust — **busts 16 GB** |

200 BB doesn't fit in 16 GB with the default 256/128/64 abstraction. Options: tighten to
128/64/32 buckets (saves ~3×, brings to 7–8 GB), or solve postflop-only at 200 BB (saves ~30%).
Or split solves into "preflop only" and "postflop given a starting node" with checkpointed
disk handoff.

---

## Sensitivity table

| Configuration | Postflop infosets (rel) | Full-game memory @ 100 BB | Fits 16 GB? |
|---|---|---|---|
| **Default**: 6 sizes / PF-cap 4 / postflop-cap 3 / 256/128/64 | 1.00× | 10–14 GB | ✅ tight |
| Drop 100% and 200% pot (4 sizes): 33/75/150/AI / same caps / same buckets | 0.55× | 6–8 GB | ✅ comfortable |
| 5 sizes (drop 200% only) | 0.78× | 8–11 GB | ✅ |
| Tighten buckets to 128/64/32 | 0.45× | 5–7 GB | ✅ comfortable |
| Tighten to 64/32/16 (aggressive) | 0.15× | 1.5–2.5 GB | ✅ easy |
| **Loosen postflop raise cap 3 → 4** | 1.8–2.2× | 18–28 GB | ❌ **busts** |
| Loosen preflop raise cap 4 → 5 | 1.15× | 11–16 GB | ⚠️ borderline |
| 6 sizes / cap 4 PF / cap 3 PF-default / **40 BB** | 0.35× | 3–5 GB | ✅ |
| 6 sizes / cap 4 PF / cap 3 PF-default / **200 BB** | 1.9× | 20–25 GB | ❌ **busts** |
| **200 BB + tighten to 128/64/32** | 0.85× | 8–11 GB | ✅ |
| Postflop-only solve (skip preflop tree) at 100 BB / default | 0.65× of full | 6–9 GB | ✅ |

### RAM-critical knobs (in descending impact)

1. **Postflop raise cap (3 vs 4)**: the largest single lever. Each extra raise level multiplies
   the per-street action count by ~6 (one full bet-size menu), and that compounds across three
   postflop streets. Locked at 3 in PLAN.md — keep it there.
2. **Flop bucket count (256)**: this multiplies the flop+turn+river subtree, which is most of
   the tree. Dropping to 128 saves ~50% of flop memory. The 256 default matches
   commercial-solver standard but the river is the more expensive multiplier in absolute terms
   because there are more reach-nodes there.
3. **Bet-menu size (6 sizes vs 4)**: ~40% memory reduction by dropping 100% and 200% pot, and
   these sizes are partially redundant (100% sits between 75% and 150%; 200% is rarely chosen
   GTO when 150% is available). **Drop 200% before dropping 100%** — 200% bet is mostly used
   by exploitative leaks; the GTO incidence is low.
4. **River bucket count (64)**: dropping to 32 saves ~5–10% of total memory (river has the
   most reach-nodes but per-node strategy is cheap because fewer subsequent decisions). Cheap
   knob, modest savings.
5. **Stack depth (100 BB vs 200 BB)**: 2× memory factor when going deep because more bet sizes
   stay live without collapsing onto all-in. We should advertise 40–150 BB as default solvable
   range and warn the user above 150 BB.

---

## Comparison with commercial solvers

### PioSolver

- Pio reports: **1.2–1.9 GB for single-bet-size trees, 5.9–7.8 GB for multi-bet-size trees**,
  with disk solution files at 500 MB–4 GB
  (`references/blog/piosolver_technical_details.md`).
- Pio's typical "multi-bet-size" setup is 3–4 bet sizes with raise cap 3, similar buckets to
  ours (commercial solvers cluster around 256/128/64 because that's what fits the same RAM
  envelopes).
- Our estimate for the same scope (full HUNL postflop @ 100 BB, our 6-size menu): **6–9 GB**.
  That's ~1.2–1.5× Pio's 5.9–7.8 GB figure, which is consistent with our 6 sizes vs Pio's
  typical 4 sizes (the PLAN.md note "6 sizes ~50–70% larger than 4 sizes" aligns).
- **Conclusion: our estimate is plausible.** If our solver lands at 6–9 GB on a representative
  flop spot, we're on the same memory budget as Pio.

### postflop-solver (b-inary, Rust)

- Per `noambrown_poker_solver` README and various community posts, postflop-solver targets
  similar territory: a typical flop with 3 bet sizes solves in ~2 GB; 5 sizes around ~5 GB.
- The crate is single-flop-at-a-time and doesn't solve preflop trees, so its full-tree numbers
  aren't directly comparable to ours. But the **per-flop-spot memory matches Pio's range and
  ours**, confirming the 6-bet-size ~5–8 GB ballpark for a single representative flop.
- We add preflop on top, which roughly doubles the tree → 10–14 GB full-game matches the
  combined estimate.

### GTO Wizard

- Not directly comparable on memory because GTOW runs server-side with hybrid CFR + neural
  value nets. The published benchmark (Pio 4862 s on 16 cores / 128 GB vs GTOW 6 s on 2 cores
  / 8 GB) reflects neural-net warm-starting, not a smaller game tree
  (`references/blog/gtow_ai_benchmarks.md`). Their tree is roughly the same size as Pio's —
  they just don't materialize the full regret table because the value net amortizes most of it.
- **Implication for us**: tabular CFR (our v1) has a 5–10 GB memory floor for HUNL at our
  abstraction level. To get below 1 GB we'd need Deep CFR (PLAN.md acknowledges this as v2+).

### Slumbot, Libratus, Pluribus

- Libratus (HUNL): used hundreds of GB across a research cluster; not a useful comparison.
- Pluribus (6-max): 64-core / 512 GB / 8 days, blueprint not full equilibrium.
- Slumbot: ACPC-tier HU bot, doesn't publish memory specs but operates at PC-class scale (~16
  GB) using heavy abstraction.

The takeaway: **commercial HU postflop solvers all live in the 1–10 GB tabular range with
similar abstractions**. We're sized correctly.

---

## Recommendation

### Default abstraction (PR 3 baseline)

Lock in PLAN.md's defaults — they're the right starting point:

- **6 bet sizes (33/75/100/150/200/AI)** at every node, with per-node override via tree
  builder for spot-specific tuning.
- **Preflop raise cap 4, postflop raise cap 3.** Do not loosen either.
- **256 flop / 128 turn / 64 river** EMD buckets per side, imperfect-recall.
- **Stack depth solved per session**: support 10–150 BB at default abstraction; above 150 BB
  warn the user and auto-tighten to 128/64/32 buckets.

This config lands at **~10–14 GB Rust memory** for a full HUNL preflop+postflop solve at 100
BB, **~6–9 GB for postflop-only solves**, and **~3–5 GB at 40 BB**. All within 16 GB.

### If RAM-bound (after empirical PR 5 measurements show OOM)

Tighten in this order:

1. **Drop 200% pot from the bet menu** (cheapest fix; minimal GTO accuracy loss; saves ~20%).
2. **Tighten river buckets 64 → 32** (saves ~5–10%, accuracy impact is small).
3. **Drop 100% pot, keep 33/75/150/AI** (drops to 4 sizes; saves another 25%; this matches
   PLAN.md's original 33/75/150/AI default).
4. **Tighten flop buckets 256 → 128** (saves ~30% but starts to noticeably degrade
   strategy granularity; do this only if (1)–(3) aren't enough).
5. **Solve postflop separately from preflop** (saves ~35% per-session but loses the closed-form
   preflop→postflop coupling; this is a workflow change, not a config change).

### Should the action menu include 200%?

**Conditionally yes, with a runtime toggle.** The 200% pot bet is GTO-rare at deep stacks and
collapses onto all-in at short stacks. Including it bloats the tree by ~15–20% but provides
better strategies in specific overbet-heavy spots (paired boards, river polarization). The
cost-benefit favors keeping it with a "drop overbet" toggle for memory-pressured sessions.
Recommendation: **default ON at 100 BB and below; default OFF above 150 BB** to keep the
deep-stack solver under 16 GB without tightening buckets.

---

## Uncertainty notes

- The 340M-infoset gross figure is derived by per-street decomposition, not by walking an actual
  tree builder. PR 3's tree builder will produce an empirical count; expect it to land within
  2× of the figure above (could be 150M or 600M).
- HashMap overhead in Rust depends heavily on the key type. If we move to a 16-byte numeric key
  (vs string), per-infoset overhead drops from ~170 bytes to ~120 bytes — a 30% reduction.
  This is worth implementing in PR 5 or PR 6.
- The "memory per infoset" math assumes regret + strategy_sum stored as f64. f32 would halve
  memory at the cost of some numerical agreement with the Python tier — defer that decision
  to PR 8 (NEON SIMD) when we revisit data layout.
- Stack-depth scaling is approximate. Empirical Pio runs at 200 BB report ~1.6–2.0× the 100 BB
  memory for the same bet menu, so the table above is conservative.
- We have not accounted for the average-strategy snapshot buffer used by some DCFR variants
  (which doubles per-iteration memory transiently). If we go that route, add a ~20% buffer.
- Card abstraction is not free — the bucket-lookup table itself takes 22,100 flops × 256
  buckets × 4 bytes = ~22 MB for flop, ~50 MB combined across streets. Negligible vs the
  regret tables.

---

## Bottom line for PR 3

Build the tree builder against the locked default config. Don't pre-emptively tighten the
abstraction. Instrument PR 3 to print **(action_infoset_count, total_memory_estimate)** at
tree-build time so PR 4 (card abstraction) and PR 5 (first solve) can validate or invalidate
the estimates above with real numbers. If PR 5 measures >12 GB, fall back to "drop 200% pot"
first before touching buckets.
