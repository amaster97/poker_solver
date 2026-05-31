# Validation Gauntlet Plan — Poker-Intuition + EV-Convergence + Persona-Through-GUI

**Status:** DESIGN ONLY (no solves, no code changes in this doc). Written to be executed
COLD by another agent the moment the engine track's flop-perf work lands.

**Purpose.** Once the fast engine (suit-iso + inclusion-exclusion terminal eval + lean
raise menu) makes real range-vs-range (RvR) flop solves tractable through the GUI, we need
a correctness axis *beyond "it renders"*. This gauntlet is three batteries:

1. **Poker-intuition checks** — does the equilibrium obey known GTO properties (MDF,
   bluff-to-value, polarization, set-on-board, blockers, position)?
2. **EV-convergence validation** — are the per-hand EVs the GUI surfaces *non-degenerate*
   at the production iteration tiers, or are they under-converged 0/>pot artifacts?
3. **Persona-through-GUI** — can each persona's real task be computed END-TO-END through
   the live GUI, in their time budget? (The user named this "the best qualitative test.")

This doc is self-contained: exact spots, expected GTO properties, pass/fail criteria, and
commands. It assumes the reader has never seen this codebase.

---

## 0. Prerequisites — what must be true before running

This gauntlet is **engine-gated**. Do NOT start until ALL of these hold:

- [ ] The fast engine is merged to `main` and built into the venv the GUI runs from. The
      v1.11 engine work (rayon → suit-iso + IE terminal eval → lean raise menu) was
      reconciled with the GUI's progress/cancel hooks and shipped at `a9e92ea`
      (see `docs/gui_audit/TODO.md` "RESOLVED — ENGINE INTEGRATION"). Confirm the GUI rides
      the fast binding, not the mock solver.
- [ ] A real RvR flop solve at the **Tight** tier (1000 iters; see §2) completes through the
      GUI in a time that does not blow the persona budgets (§4). If it still hangs/OOMs, the
      flop-perf work is NOT done — STOP and report the gate is not met.
- [ ] The `.so` Rust extension matches the host arch (`file .venv/lib/.../poker_solver/_rust*.so`
      → `arm64` on Apple Silicon). An x86_64-on-arm64 `.so` silently degrades — verify first.
- [ ] **One known gap (verify current state):** the GUI combo inspector's per-combo EV is
      hardcoded to `0.0` (`ui/views/range_matrix.py`, `_build_combo_rows`,
      field `ev_mbb=0.0` with comment "Real EV plugs in when Agent A wires per-combo EV").
      The EV-convergence battery (§3) therefore CANNOT read per-hand EVs from the combo
      inspector until that wiring lands. §3 specifies the engine-level fallback
      (`_rust.compute_restricted_game_value`) so the battery is runnable regardless; if the
      inspector EV has since been wired, also validate THROUGH the inspector.

### How to launch the GUI (read-only context)

```
# from the repo root, with the venv active and the fast .so built:
poker-solver ui                 # or: python -m poker_solver.cli ui --port 8080
# launcher: ui/app.py:launch(port=8080, host="127.0.0.1"); auto-tries 8081..8090 if busy.
```

GUI surfaces that produce the outputs this gauntlet reads:
- `ui/views/spot_input.py` — build the spot (board, ranges, stacks, bet menu).
- `ui/views/run_panel.py` — pick the iteration tier + run; shows exploitability readout.
- `ui/views/range_matrix.py` — 13×13 grid + **combo inspector strip** (per-combo
  fold/call/raise bars, reach, infoset key; EV pending wiring).
- `ui/views/tree_browser.py` — decision-tree node selection (drives which infoset the
  matrix/inspector show).
- `ui/views/preflop_chart.py` — preflop blueprint chart + route badge.
- `ui/views/chained_tab.py` — preflop→flop hole-card walkthrough (Tier A).

**Discipline (close idle resources).** Kill the GUI server and close browser tabs when a
battery finishes or goes idle. Bound heavy solves with a ~12 GB RSS ceiling and a live
monitor; plan against ~16 GB effective. Never leave servers/solves/tabs accumulating.

---

## 1. Battery A — Poker-Intuition Checks

Style follows the `poker-validator` subagent (`~/.claude/agents/poker-validator.md`): each
check states the SPOT to set up in the GUI, the EXPECTED GTO PROPERTY, and a PASS/FAIL
criterion *in poker terms*. On FAIL, explain WHY in poker terms + a hypothesis (missing
action size? coarse abstraction? regret/utility bug? under-convergence?), not just a number.

**Heuristic sources** (publicly readable; cite, don't guess — see
`docs/pr13_prep/persona_acceptance_spec.md` §3 heuristics table and the references dir):
Sklansky *Theory of Poker* (MDF), Janda *Applications of NLHE* (bluff-to-value), GTO Wizard
blog `references/blog/gtow_how_solvers_work.md` (polarization), Pio coaching
`references/products/piosolver_technical_details.md`.

**Convergence caveat threaded through ALL of A.** Per
`project_postflop_convergence`, postflop per-hand EVs and even some frequencies are
DEGENERATE below ~1000 iters. Run every Battery-A spot at **Tight (1000)** minimum, and for
any check that looks like a FAIL, re-run at a higher tier (Library 2000, then a manual
4000–10000) before declaring a bug. A "fail" that disappears at higher iters is
under-convergence, not a solver bug.

### A1 — Minimum Defense Frequency (MDF)

- **Spot:** River, single dry board with no possible draws, e.g. board `Ks 8d 3c 2h 7s`
  (rainbow, no straight/flush). Aggressor (hero, P0) bets; defender (P1) faces it.
  Stacks set so a clean half-pot and a clean pot bet are both legal.
  Aggressor range = a balanced betting range; defender = a wide bluff-catching range
  (e.g. `99-22, AJ-AT, KQ-KT, QJ` — pairs and marginal made hands).
- **Set up in GUI:** spot_input → river street, place the 5 board cards, set hero and
  villain ranges (use the MATRIX or STRING input). Enable bet sizes 50% and 100% in the bet
  menu. Solve at Tight.
- **Expected GTO property:** defender defends (call + raise) at frequency
  `MDF = pot / (pot + bet) = 1 − bet/(bet+pot)`.
  - vs half-pot bet → MDF ≈ **67%** defended.
  - vs pot-sized bet → MDF ≈ **50%** defended.
- **Read from GUI:** select the defender's decision node in the tree browser; in the combo
  inspector sum the (call + raise) reach-weighted frequency across the defender's range
  (the inspector shows fold/call/raise bars per combo + reach). Range-aggregate is also in
  the matrix's range_aggregate readout.
- **PASS:** total defend frequency within **±5%** of theoretical MDF (per poker-validator).
- **FAIL → poker reading:** "Defender over-folds to half-pot on a dry board: defends 52% vs
  MDF 67% → aggressor can profitably bet any two cards." Hypotheses: bet menu missing the
  size the equilibrium wants (e.g. no 33%); terminal-utility/regret bug under-valuing
  bluff-catches; under-convergence (re-check at 2000+).

### A2 — Fold equity / bluff-to-value ratio (river)

- **Spot:** same dry river as A1. Inspect the AGGRESSOR's betting range composition.
- **Expected GTO property:** at the bet size used, aggressor's bluff-to-value ratio
  ≈ `bet/(bet+pot)` (Janda). vs pot bet → ~33% of the betting range is bluffs (2:1
  value:bluff); vs half-pot → ~25% bluffs (3:1).
- **Read from GUI:** in the aggressor's combo inspector, classify each betting combo as
  value (top pair+ / made hands that beat the defender's calling range) vs bluff (air /
  missed draws), reach-weighted; take the bluff fraction of the total bet frequency.
- **PASS:** bluff fraction within ±5% (absolute) of `bet/(bet+pot)`.
- **FAIL → poker reading:** "Aggressor bets pot with only 15% bluffs (vs ~33% GTO) → range
  is under-bluffed; defender can over-fold and exploit." Hypotheses: missing all-in or
  larger size pulling bluffs elsewhere; blocker effects (see A5) if the deviation is small;
  under-convergence.

### A3 — Range polarization on scary boards

- **Spot:** Monotone flop `Ah 7h 2h` (three hearts). Aggressor has a 100 BB SRP-style range;
  defender a calling range. Enable a large size (≥100%, plus all-in) in the bet menu.
- **Expected GTO property** (GTOW canon): on a monotone board the aggressor's BETTING range
  is POLARIZED — nut-suited hands (made/big flushes, sets) + busted-suited *bluffs* — while
  medium-strength hands (one-pair, no heart) CHECK. Specifically per the user's validated
  intuition (`persona_acceptance_spec.md` §W3.5 note): range-Nash AA *without a heart*
  should be ~80–95% CHECK on a monotone board, NEVER large-bet, and FOLD to large
  bets/raises.
- **Read from GUI:** aggressor combo inspector. Bucket combos: (a) flushes/sets, (b)
  medium one-pair no-flush (incl. AA no heart), (c) air/busted. Look at bet vs check
  frequency per bucket.
- **PASS:** value buckets (a) + air (c) carry the large bet; medium bucket (b) is
  predominantly CHECK (AA-no-heart ≥ ~80% check); large bets do not contain a wide swath of
  medium-strength hands.
- **FAIL → poker reading:** "AA-no-heart bets 100% pot on the monotone flop → solver isn't
  polarizing; it's value-betting a hand that's crushed by the calling range's flushes."
  Hypotheses: the RvR aggregator's per-combo collapse (use the true-Nash vector path, not
  the Pluribus-blueprint aggregator — see `solve_range_vs_range_nash` vs
  `solve_range_vs_range`); under-convergence; bet menu lacking the polarizing size.
  **CRITICAL:** verify you are reading the true-Nash path (`backend == "rust_vector"`), not
  the per-combo perfect-info proxy that the `persona_acceptance_spec.md` §W3.5 note warns
  produces a TAUTOLOGICAL "value-side" pattern.

### A4 — Set / nut advantage never folds

- **Spot:** Any flop where hero can flop a set, e.g. board `Qs 7h 2d`, hero range includes
  `77, 22`. Standard SRP line, 100 BB.
- **Expected GTO property** (poker-validator gauntlet item 4): on standard lines, a set or
  better folds < **5%** of the time. Top set on a dry board essentially never folds.
- **Read from GUI:** combo inspector for the set combos (e.g. `7h7s` on `Qs 7h 2d`); read
  the fold frequency.
- **PASS:** set fold frequency < 5% across the line (facing reasonable sizing).
- **FAIL → poker reading:** "Solver folds bottom set `22` to a half-pot turn bet 18% of the
  time → either a bucketing bug merges `22` with a worse class, or the EV of `22` is
  under-converged (pinned near 0; see §3)." Hypotheses: card-abstraction collision;
  under-convergence (re-check at 2000+); terminal-eval bug.

### A5 — Blocker effects (bluff selection)

- **Spot:** River where a flush completes, e.g. board `Ah Kh 7h 4c 2d`. Aggressor decides
  which busted hands to bluff with.
- **Expected GTO property:** the aggressor preferentially bluffs hands that BLOCK the
  defender's calls / unblock its folds — i.e. holding the `Qh`/`Jh` (blocks nut-ish flushes)
  is bluffed MORE than a busted hand with no heart. Two otherwise-equivalent air hands should
  differ in bluff frequency by the blocker.
- **Read from GUI:** combo inspector; compare bet frequency of a busted hand WITH a key
  blocker vs WITHOUT (same made-hand strength = none).
- **PASS:** blocker hands are bluffed at materially higher frequency than non-blockers
  (direction correct; the magnitude is solver-specific but the ORDERING must hold).
- **FAIL → poker reading:** "Solver bluffs `9h2c` (holds a heart, blocks flushes) LESS than
  `9c2c` (no heart) → blocker logic inverted or hands are being bucketed away from their
  card-removal effect." Hypotheses: suit-isomorphism collapse losing the blocker (verify the
  suit-iso path preserves board-relevant suits); under-convergence flattening the
  distinction (re-check higher iters — blocker effects are second-order and need more
  convergence than gross MDF).

### A6 — Position / aggression sanity

- **Spot:** 100 BB SRP, in-position (IP) aggressor vs out-of-position (OOP) defender, on a
  neutral flop `9s 6d 2c`.
- **Expected GTO property:** IP c-bets at a meaningful frequency on a dry board (IP realizes
  equity better; small-size, high-frequency c-bet is canon). OOP checks its range to the IP
  player. Aggressor's overall aggression > defender's at this node.
- **Read from GUI:** range_aggregate bet frequency for the IP node vs the OOP node.
- **PASS:** IP c-bet frequency clearly exceeds OOP donk/lead frequency; IP bets a non-trivial
  fraction of range on the dry board. (Note: the current bet-size design is flop-no-donk for
  the OOP player per `project_betsize_raise_tree` — so OOP lead may be structurally absent;
  confirm against the configured menu before calling a deviation a bug.)
- **FAIL → poker reading:** "IP checks back 95% on a dry 9-high flop → solver isn't
  capturing the IP equity-realization edge." Hypotheses: bet menu config; under-convergence;
  contributions/SPR misrepresented in a hand-built spot (see the known SPR gap below).

### Battery-A reporting

Produce a summary table (Check | Spot | Expected | Observed | PASS/FAIL | poker-reading +
hypothesis), exactly in the `poker-validator` output format. Be honest — "this looks subtly
wrong" beats a false "all green." Cross-reference each heuristic to its source. For any FAIL,
record the iteration tier and whether it survived a higher-iter re-solve.

---

## 2. Iteration tiers (shared context for A and B)

From `ui/views/run_panel.py` (`_TIER_DEFAULTS`, measured by exploitability):

| Tier     | Iters | Target (mBB/pot) | Notes |
|----------|-------|------------------|-------|
| Draft    | 200   | 10.0 (1% pot)    | median 0.0036% pot reached on 15 fixtures |
| Standard | 500   | 5.0 (0.5% pot)   | median 0.0002% pot |
| **Tight**| **1000** | 2.5 (0.25% pot) | **`_DEFAULT_TIER`** — the GUI default |
| Library  | 2000  | 1.0 (0.1% pot)   | median 0.000004% pot |

**The trap (`project_postflop_convergence`):** these tiers are calibrated by *exploitability*
(a range-level aggregate). **Low exploitability ≠ converged per-hand EVs.** Per-hand EVs for
dominated hands stay degenerate far longer than exploitability suggests. So the
EV-convergence battery (§3) must NOT trust the exploitability readout as proof that the combo
inspector's per-hand EVs are sane.

---

## 3. Battery B — EV-Convergence Validation

**Goal.** Verify the per-hand EVs the GUI surfaces are NON-DEGENERATE at the production tier
(Tight=1000), and confirm they STABILIZE rather than drift, by re-solving at higher iters.
This is the root of the user's "results just say fold/call / EVs look wrong" complaint.

**Why this battery exists (`project_postflop_convergence`, empirically confirmed
2026-05-30, board `Kc 7h 2d`, pot 6 BB):**
- AA-vs-KK hero EV: **0.001** at 100 iters → **0.267** at 1000 iters (under-converged hands
  pin near 0 — equity unrealized because the hand plays near-pure check/fold and never
  reaches showdown).
- AA-vs-72o: −0.000 → **0.667** at 1000 iters.
- KK-vs-QQ: **6.002** at 100 iters — **above the entire 6 BB pot, which is impossible** —
  → 6.0000 at higher iters (off-equilibrium chip donation in the Brown pot-share base).

So an extreme EV (≈0, or ≥ pot) is an **under-convergence artifact, not a bug** — ALWAYS
re-check at higher iters before flagging.

### B.1 — Cells to check

Dominated / extreme hands are the diagnostic, because they're the slowest to converge:
- **Overpairs vs underpairs:** AA, KK, QQ on a low dry board (e.g. `Kc 7h 2d` or `9s 6d 2c`).
- **Made hand vs air:** a strong made hand vs a busted range (AA-vs-72o style).
- **A bluff-catcher facing pot odds:** the "JJ with 93% equity, should it fold?" cell from
  the `solve_range_vs_range_nash` docstring — a marginal call.

### B.2 — Method (two layers; run both)

**Layer 1 — through the GUI combo inspector (PREFERRED, gated on EV wiring).**
1. Set up the spot in `spot_input` (board, hero/villain ranges, stacks). Solve at **Tight**.
2. In the tree browser select the relevant decision node; open the combo inspector
   (`range_matrix.py`) and read the per-combo `ev_mbb` for the B.1 cells.
3. **GATE:** if `ev_mbb` reads exactly 0.0 for ALL combos, the inspector EV is not yet
   wired (it is hardcoded `0.0` at the time of writing — see §0). In that case Layer 1 is
   blocked; record that the EV-surfacing wiring is a prerequisite and run Layer 2 instead.

**Layer 2 — at the engine level (ALWAYS runnable; this is how the memory numbers were
obtained).**
1. Solve the spot via `solve_range_vs_range_nash(config_template, hero_range, villain_range,
   iterations=N, hero_player=0)` → `RangeVsRangeNashResult` with `.per_history_strategy`
   (`{infoset_key: [probs]}`), `.exploitability`, `.backend == "rust_vector"`.
2. Recover per-hand hero EV with `_rust.compute_restricted_game_value(config_json,
   strategy, p0_holes, p1_holes)` — returns `{"game_value": float}` = P0's on-policy EV in
   the Brown pot-share base, BB units, over ONLY the supplied hole-pair cross-product. Supply
   hero combos as `p0_holes`, villain combos as `p1_holes`. (Use this, NOT
   `compute_exploitability`, which enumerates ~1.27M flop combos uniformly and dilutes every
   cell toward pot/2.)
3. Repeat at iters ∈ {100, 1000, 2000, 4000} and tabulate EV vs iters per cell.

### B.3 — Pass/Fail criteria

For each B.1 cell:
- **Non-degenerate at Tight (1000):** the EV is NOT pinned at ≈0 (within ~1e-3) AND NOT
  ≥ the pot size. A dominated overpair should show a positive, plausible fraction of pot
  (the memory's AA-vs-KK landed at 0.267 BB on a 6 BB pot at 1000 iters — sane).
- **Stabilizes:** EV at 2000 and 4000 iters differs from the 1000-iter value by a small
  margin (the memory shows AA-vs-KK 0.267→ stable, KK-vs-QQ 6.002→6.0000). Define
  STABLE = |EV(4000) − EV(2000)| ≤ 0.02 BB (or ≤ 1% of pot, whichever is larger). Movement
  larger than that means 1000 iters is NOT enough for THAT cell — flag the tier as
  insufficient for per-hand EV display.
- **Conservation (sanity):** no hero EV exceeds the total pot; no EV is negative beyond the
  amount the hero can lose (its subgame contribution). A value > pot at 1000 iters that
  collapses into range by 2000 confirms under-convergence (expected), not a bug.

### B.4 — Decision output

- If EVs are non-degenerate and stable at Tight=1000 → the production tier is adequate for
  per-hand EV display; close `docs/gui_audit/TODO.md` "Postflop EV-convergence validation."
- If dominated-hand EVs need >1000 iters to stabilize → recommend either (a) a separate
  higher "EV-grade" tier for the combo inspector distinct from the exploitability tier, or
  (b) a UI caveat that per-hand EVs at Draft/Standard are indicative only. Surface to the
  user (this is the `TODO.md` FOLLOW-UP "split exploitability-tier vs EV-convergence?"
  question) — balanced against Marcus's <30 s tolerance (§4): a 4000-iter EV-grade solve
  must still fit the budget or it's not shippable as a default.

---

## 4. Battery C — Persona-Through-GUI (the qualitative test)

**Goal (the user's named "best qualitative test").** Take each persona's representative task
and run it END-TO-END THROUGH THE LIVE GUI for a **single solve** — confirm it is actually
COMPUTABLE on the merged fast engine, and times within the persona's tolerance. Scope =
single solve per persona (NOT research-grade multi-solve chains).

**Personas + tasks** (full catalog: `docs/pr13_prep/persona_acceptance_spec.md` §1–2;
harness for the programmatic versions: `tests/test_w5_premium_a_personas.py`). The five
personas: **Marcus** (casual rec), **Sarah** (serious amateur, Python), **Daniel** (pro/coach,
PioSolver daily driver), **Priya** (researcher/dev), **Wendy** (Premium-A / "GTO Wizard for
Mac" consumer).

**Time budgets** (`docs/pr13_prep/persona_time_budgets.md`; Marcus gates the user-facing
features): single-spot interactive solve target 1–5 min (Pio-class); **Marcus tolerance
< 30 s** for a casual post-mortem; **Wendy < 100 ms** for a blueprint chart lookup (inherits
Marcus's "feels instant"); kill-switch at 30 min for any single spot.

### C — Per-persona GUI walkthrough

For each, the steps are: (1) open the relevant GUI tab, (2) input the spot, (3) solve a
SINGLE spot, (4) confirm it returns a plausible answer (cross-check against the
heuristic), (5) record wall-clock vs the budget.

| ID | Persona | GUI task (single solve) | Computable? gate | Time budget | Heuristic to sanity-check the answer |
|----|---------|--------------------------|------------------|-------------|--------------------------------------|
| C-M | Marcus | "Was my river call right?" — postflop tab, place a river board, hero hand + a villain range, villain bets pot, read hero's call EV/frequency. | Postflop RvR river solve returns through GUI. | **< 30 s** | A strong made hand vs a pot bet defends near 100% (pot odds 33%); MDF for the range. |
| C-S | Sarah | "Solve KK on a Q-high flop vs villain c-bet range" — postflop tab, flop `Qs 7h 2d`, hero `KK`, villain bluff-heavy c-bet range. | Flop RvR solve returns; 13×13 + combo inspector populate. | ≤ 5 min (tolerates 15 min) | KK on Q-high near-100% defend with mixed raises vs bluff-heavy c-bets (A4-style). |
| C-D | Daniel | "MDF check: BB defends ≥ MDF vs half-pot c-bet" — flop SRP, half-pot c-bet; sum BB defend frequency. (Node-locking is his #1 ask — if the `node_lock_editor.py` UI is wired, also lock villain bluff freq=0 and confirm hero pure-folds bluff-catchers.) | Flop RvR solve + (optional) node-lock returns. | ≤ 5 min | BB defends ~67% vs half-pot (= MDF; ties to A1). With villain bluffs locked to 0 → hero pure-folds bluff-catchers (MDF doesn't apply, villain unbalanced). |
| C-P | Priya | "Programmatic single solve + read result shape" — primarily library, but via GUI confirm a postflop solve produces a result the matrix/inspector render (proxy for the API result being well-formed). | Solve returns a structured, finite result. | ≤ 5 min | Result is finite, simplex-valid per infoset, deterministic for a fixed seed/config. |
| C-W1 | Wendy | "Pull the 100 BB no-ante preflop chart" — preflop chart tab, 100 BB, no ante; read AKs. | Blueprint lookup. | **< 100 ms** (warm) | `blueprint_lookup` route, "blueprint" badge, 169 cells populate, strategy sums to 1.0. |
| C-W2 | Wendy | "Pull a 67 BB (off-grid) chart" — preflop chart, 67 BB. | Interpolated lookup. | < 100 ms | `interpolated` route + "interpolated · 60↔80" badge; blend = 0.65·v60 + 0.35·v80. |
| C-W3 | Wendy | "Chain preflop → flop subgame on `Qs 7h 2d`" — chained tab, hole cards, walk preflop→flop. | **Flop subgame computes** (was the engine gate). | 5–30 s | `postflop_subgame` route, both lookup + live-solve badges populated; flop strategy simplex-valid. |
| C-W4 | Wendy | "Edit my 3-bet range, force a custom live solve" — B10 per-combo editor, override a cell, solve. | `custom_live_solve` (not blueprint). | ≤ 5 min | Route = `custom_live_solve`; result reflects HER range, not the blueprint baseline. |
| C-W5 | Wendy | "Toggle cash↔tournament ante at 40 BB" — preflop chart, switch none/half/full ante. | Blueprint lookups, 3 antes. | < 100 ms each | Strategy materially shifts (L1 > 0.05 across the 7-action vector for a marginal hand like 72o). |

**Computability gate.** For each row, the binary question is: *did the GUI produce the
result without hanging, OOMing, or erroring, within the budget?* Record PASS (computed +
plausible + in-budget), SLOW (computed + plausible but over budget — a perf finding), or
FAIL (errored / hung / implausible). The postflop rows (C-M, C-S, C-D, C-W3, C-W4) were the
ENGINE-GATED ones; they are the whole point of running this AFTER the flop-perf work lands.
The preflop/blueprint rows (C-W1/2/5, C-P shape) were already runnable and serve as a
regression check.

**Cross-reference to the programmatic harness.** The Wendy rows mirror
`tests/test_w5_premium_a_personas.py` (W5.1–W5.5). That harness asserts the ROUTING and
SHAPE at the library layer; Battery C is the GUI-end-to-end complement (same spots, but
driven through the live UI and timed against the human budget). W5.3 in the harness uses a
synthetic 2-class smoke fixture because the production-scale flop solve was intractable —
**C-W3 is the test that the PRODUCTION-scale chain now computes through the GUI on the fast
engine.** If C-W3 still can't run the shipped 169-class blueprint flop at a credible filter,
the flop-perf gate is NOT met (§0).

### C — Reporting

Per-persona table: Persona | Task | Route/result | Wall-clock | Budget | PASS/SLOW/FAIL |
plausibility note. Goal mirrors `persona_acceptance_spec.md` §4: a persona task that
computes + answers plausibly + in-budget = WORKS. Surface any SLOW row as a perf follow-up
(it gates the user-facing feature per the Marcus budget rule).

---

## 5. What's needed to run it (dependency summary)

1. **The merged fast engine in the GUI build.** Suit-iso + IE terminal eval + lean raise
   menu, reconciled with GUI progress/cancel hooks (shipped `a9e92ea`). Confirm the GUI uses
   the fast `_rust` binding, not `ui/mock_solver.py`.
2. **Real solves, not mocks.** Disable/verify-absent any mock-mode path; the gauntlet is
   meaningless against the mock solver.
3. **A tractable spot envelope.** The flop-perf work must make the Battery-A/B/C-postflop
   spots solve at Tight within budget. Document the envelope you actually used (board
   texture, range widths in combos, stack depth, bet menu = number of sizes × raise cap).
   `project_betsize_raise_tree`: the RAISE menu × cap is the dominant per-street tree
   multiplier — keep raises lean (flat 3× multiplier, flop-no-donk) to stay in budget.
   `feedback_postflop_memory_wall`: full-range flop is memory-bound by board combinatorics
   (~6.7 GB+ at 40 BB top_k=4); bound with a ~12 GB RSS ceiling + live monitor.
4. **The flop-perf dependency is THE gate.** Everything postflop in this gauntlet (A1–A6, B,
   C-M/S/D/W3/W4) depends on the engine track's flop-perf work landing such that a Tight RvR
   flop solve completes in-budget. If it doesn't, STOP and report the gate is unmet — do not
   "pass" the gauntlet against a hung/approximated solve (`feedback_no_patchups`).
5. **(For Battery B Layer 1 only) the combo-inspector EV wiring** (`ev_mbb` currently
   hardcoded `0.0`). Layer 2 (`compute_restricted_game_value`) makes B runnable without it,
   but full GUI validation needs the wiring.

---

## 6. Open questions / risks

- **Q1 — Combo-inspector EV not wired.** Per-combo `ev_mbb` is `0.0` in
  `range_matrix.py`. Until wired, Battery B can only validate EVs at the engine level
  (Layer 2), not "as the user sees them." Decide: wire the EV first, or accept Layer-2-only
  validation for now? (Recommend wiring it — the user's complaint is specifically about EVs
  the GUI shows.)
- **Q2 — Exploitability tier vs EV-convergence tier.** `project_postflop_convergence`: low
  exploitability ≠ converged per-hand EVs. If B shows dominated-hand EVs need >1000 iters,
  the combo inspector may need its own "EV-grade" tier (or a caveat). This trades directly
  against Marcus's <30 s budget — a higher EV tier may not fit. User decision needed
  (already flagged in `docs/gui_audit/TODO.md`).
- **Q3 — RvR aggregator vs true-Nash path.** Battery A (esp. A3 polarization) is only
  meaningful on the TRUE-Nash vector path (`solve_range_vs_range_nash`, `backend ==
  "rust_vector"`), NOT the Pluribus-blueprint aggregator (`solve_range_vs_range`) and NOT
  the per-combo perfect-info proxy (which gives a TAUTOLOGICAL value-side pattern — see
  `persona_acceptance_spec.md` §W3.5 note). Risk: silently reading the wrong path and
  declaring a false PASS. Mitigation: assert the backend on every Battery-A read.
- **Q4 — Hand-built spot SPR gap.** `docs/gui_audit/TODO.md` FOLLOW-UP: a HAND-BUILT
  postflop spot drops pot+contributions in `_spot_from_config`/`Spot.to_hunl_config()`, so
  SPR can be misrepresented; fixture-loaded / solved-config tree-and-matrix sidesteps it.
  Risk: a spot built by clicking in the GUI may have wrong SPR → MDF/polarization off for a
  non-solver reason. Mitigation: prefer fixture-loaded spots, or verify SPR before trusting
  a hand-built spot's frequencies.
- **Q5 — Suit-isomorphism and blockers (A5).** The suit-iso optimization collapses suits;
  verify it preserves board-relevant suits so blocker effects (A5) remain observable. Risk:
  a suit-iso collapse erases the very blocker the check looks for. Mitigation: A5 itself is
  the test — if blocker ordering is gone, suspect the suit-iso path first.
- **Q6 — Convergence false-fails.** Any Battery-A "fail" might be under-convergence, not a
  bug (`project_postflop_convergence`, `feedback_empirical_over_audit`). Protocol: never
  declare a solver bug from a single tier — re-solve at 2000, then 4000+, and only flag a
  bug if the deviation PERSISTS. Conversely, don't accept a "pass" that only holds because
  everything is flattened toward pot/2 at low iters.
- **Q7 — Node-locking UI maturity (Daniel, C-D).** `ui/views/node_lock_editor.py` exists;
  confirm it's wired to the live solve before relying on the lock arm of C-D. If not wired,
  run C-D's MDF arm only and record node-locking as still-pending.

---

## 7. Cross-references

- `~/.claude/agents/poker-validator.md` — the intuition-gauntlet output style + checks 1–6
  (MDF, fold equity, polarization, set-never-folds, no-junk-bluff-catch, Kuhn/Leduc).
- `~/.claude/agents/poker-cfr-validator.md` — DCFR math correctness (α=1.5, β=0, γ=2.0); use
  if a Battery-A fail implicates the regret/strategy math rather than poker-level behavior.
- `~/.claude/agents/pr-check-runner.md` — the between-PR engineering battery (tests/lint/
  types/diff/perf); orthogonal to this gauntlet but cite for "engineering-green ≠
  user-acceptable."
- `docs/ev_invariance_sanity_gauntlet_design_2026-05-27.md` + `tests/test_ev_invariance_gauntlet.py`
  — the EV-of-action invariance check vs Brown (cross-solver, Nash-invariant). Related to
  Battery B but distinct: that gauntlet compares EV ACROSS solvers; Battery B checks EV
  CONVERGENCE within ours across iters.
- `tests/test_leduc_intuition.py` — existing poker-intuition heuristic test on Leduc; the
  closest existing analog to Battery A (smaller game, closed-formish).
- `docs/pr13_prep/persona_acceptance_spec.md` — the 23-workflow persona catalog (Battery C
  source) + the heuristics reference table (Battery A sources) + the W3.5 polarization
  methodology note.
- `docs/pr13_prep/persona_time_budgets.md` — authoritative time budgets (Marcus < 30 s gate).
- `tests/test_w5_premium_a_personas.py` — programmatic Wendy W5.1–W5.5 (Battery C-Wendy rows'
  library-layer complement).
- `docs/gui_audit/TODO.md` — the "OTHER ASPECTS" list this gauntlet operationalizes
  (poker-intuition gauntlet, EV-convergence validation, persona-through-GUI), plus the SPR
  gap and tier/convergence FOLLOW-UP.
- MEMORY: `project_postflop_convergence` (the degenerate-EV finding + empirical numbers),
  `project_betsize_raise_tree` (tree-size levers), `feedback_postflop_memory_wall` (flop
  memory wall), `feedback_no_patchups` (no approximated "pass"), `feedback_empirical_over_audit`
  (keep digging when empirical fails an audit-clean path).

---

## 8. Non-goals for this design doc

- No solves, no benchmarks, no code changes (this is the design only).
- No multi-solve research chains (Battery C is single-solve per persona).
- No cross-solver Brown parity (that's the EV-invariance gauntlet, already shipped).
- No claim that the gauntlet is runnable TODAY — it is engine-gated on the flop-perf work.
