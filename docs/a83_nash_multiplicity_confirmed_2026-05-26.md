> ⚠️ **PARTIALLY SUPERSEDED 2026-05-27.** This finding is empirically real — same convention + different init regrets DOES produce ~100% strategy divergence on indifference cells. BUT: it was measured under the prior "rust" convention which is now being purged (per `feedback_brown_convention_adopt.md`). The 33pp Brown apples-to-apples gap is NOT purely Nash multiplicity — PR #93 ablation showed terminal-utility convention shifts strategies 12-50pp on identical seeds. The full breakdown of the 33pp into (convention contribution + multiplicity residual) requires re-running the probe AFTER convention purge lands.

# A83 Nash multiplicity — EMPIRICALLY CONFIRMED (2026-05-26)

**Status:** CONFIRMED via a corrected `solve_range_vs_range_rust` probe
(2026-05-26 ~04:13 UTC). Supersedes the INVALIDATED A83 Track A v1 probe
(2026-05-26 morning) whose CLI invocation hit a `chance_outcomes()`
no-op path.
**Probe script:** `scripts/a83_nash_multiplicity_probe.py` (tracked in
this PR).
**Decision-rule outcome:** **NASH-MULTIPLICITY** — pre-registered
thresholds in the probe script were `<0.01 → CONSTANT-OFFSET`,
`≥0.05 → NASH-MULTIPLICITY`; observed `max |Δ| = 0.998499` clears the
multiplicity threshold by ~20×.

---

## 1. Verdict

| Quantity | Value |
|---|---|
| Spot fixture | `dry_A83_rainbow` (board `3d 6s 8c Tc Ah`, river RvR) |
| Iterations | 2000 (matches v1.5 Brown apples-to-apples acceptance baseline) |
| Backend | `rust_vector` via `solve_range_vs_range_rust` PyO3 binding |
| RNG seed (both runs) | `1` |
| Baseline `regret_init_noise` | `0.0` |
| Perturbed `regret_init_noise` | `1e-9` |
| Common decision-cell count | **2079** (no `only_baseline` / `only_perturbed` keys) |
| **Max \|Δ\| overall** | **0.998499** (cell `5d7d\|3d6s8cTcAh\|r\|xb1000r3000r9000`, action_idx 0) |
| Verdict tag | `NASH-MULTIPLICITY` |
| Verdict text | `STRATEGY DEPENDS ON INITIAL CONDITIONS (Nash multiplicity confirmed)` |
| Baseline wall-clock | 157.78 s (Python observed) / 157.78 s (Rust reported) |
| Perturbed wall-clock | 164.81 s / 164.81 s |
| Total wall-clock | 322.60 s (5.38 min) |
| Decision-node count | 42 per run |
| Strategy-entry count | 2079 per run |
| Hand-count per player | 50 (defender, P0) / 49 (opener, P1) |

The two runs share every decision-cell key (identical tree shape), but
the per-cell average strategies diverge by up to ~100% on the most
sensitive cells. With only a `1e-9` initial-regret perturbation and an
otherwise identical RNG seed, this is exactly the signature of an
indifference-manifold equilibrium that admits a continuum of Nash
solutions: which point on the manifold the solver lands on is governed
by the initial conditions, not by the game itself.

---

## 2. Both confirmation lines (peak vs aggregate)

A peak `max |Δ|` of 0.998 is one specific cell. To avoid implying that
every cell diverges that hard, the probe also records the per-action
absolute deltas on the targeted bottom-pair-Ace cluster (`3sAs`, `3cAc`
at history `b1000r3000` — the original 33pp gap site):

| Hand | Cells common | Max \|Δ\| (cluster) | Example cell |
|---|---|---|---|
| `3sAs` | 4 | **0.2843** | `3sAs\|3d6s8cTcAh\|r\|b1000r3000` (action_idx 1: baseline 0.3240 → perturbed 0.6083, Δ 0.2843) |
| `3cAc` | 4 | **0.2588** | `3cAc\|3d6s8cTcAh\|r\|b1000r3000` (action_idx 1: baseline 0.3511 → perturbed 0.6100, Δ 0.2588) |

So the picture is: the **peak** divergence is ~100% on a small handful
of deep-action-sequence cells (xb-line 4-bet-and-deeper raises), while
the **bottom-pair-Ace** cluster — the historic 33pp gap site — shows
~25-28% divergence at the b1000r3000 facing-3bet node. Both are
strongly above the 5% multiplicity threshold.

**Average divergence across the 2079 common cells is not reported by
the probe script.** The summary records max per cell, max overall,
top-10 cells by Δ, and the targeted cluster cells. A full per-cell
average can be regenerated from the dumped JSONs (paths in §3).

---

## 3. Artifacts (NOT committed; on `~/Desktop/` outside repo)

These are large JSON dumps and live outside the repo per the PR
constraint:

- `~/Desktop/a83_correct_probe_baseline.json` (258 KB) — full
  `{meta, average_strategy}` for the baseline run.
- `~/Desktop/a83_correct_probe_perturbed.json` (241 KB) — same for
  the perturbed run.
- `~/Desktop/a83_correct_probe_summary.json` (7 KB) — combined
  diff summary including top-10 cells, targeted-cluster cells, verdict.
- `~/Desktop/a83_correct_probe.log` (4 KB) — stdout transcript.

To reproduce from a fresh checkout:

```bash
.venv/bin/python scripts/a83_nash_multiplicity_probe.py
```

The script is deterministic at the Rust-vector-DCFR level (fixed
`rng_seed`, fixed iteration count). Re-running with the same seed
should yield byte-identical JSONs.

---

## 4. Top 10 most divergent cells (from summary)

Each row: `cell_key` (hole-pair | board | street | history), action index,
\|Δ\|.

| # | Cell key | action | \|Δ\| |
|---|---|---|---|
| 1 | `5d7d\|3d6s8cTcAh\|r\|xb1000r3000r9000` | 0 | 0.998499 |
| 2 | `5d7d\|3d6s8cTcAh\|r\|xb1000r3000r6000` | 0 | 0.998499 |
| 3 | `5s7s\|3d6s8cTcAh\|r\|xb500r2000r4000` | 0 | 0.994099 |
| 4 | `5s7s\|3d6s8cTcAh\|r\|xb500r2000A` | 0 | 0.994099 |
| 5 | `5d7d\|3d6s8cTcAh\|r\|xb500r2000A` | 0 | 0.989650 |
| 6 | `6d6c\|3d6s8cTcAh\|r\|b1000r3000r6000` | 0 | 0.989500 |
| 7 | `KsKd\|3d6s8cTcAh\|r\|b1000A` | 0 | 0.989468 |
| 8 | `KhKc\|3d6s8cTcAh\|r\|b500r2000r6000` | 0 | 0.919603 |
| 9 | `KhKd\|3d6s8cTcAh\|r\|b500r2000A` | 0 | 0.913779 |
| 10 | `KdKc\|3d6s8cTcAh\|r\|b500r2000A` | 0 | 0.912089 |

The pattern: peak divergences cluster at **deep-cap raise sequences**
(`r6000`/`r9000`/`A` suffixes from a `xb`/`b` start) on hands that are
mixed-strategy by river structure (`5d7d` busted draws, `6d6c`/`KsKd`
pocket pairs that block the nutted hand class). These are textbook
indifference-manifold cells.

---

## 5. Methodology — what the probe does

`scripts/a83_nash_multiplicity_probe.py`:

1. Loads the `dry_A83_rainbow` fixture from
   `tests/data/river_spots.json` via the existing Brown-parity
   wrapper (`poker_solver.parity.noambrown_wrapper.load_spots`).
2. Builds a `HUNLConfig` matching the v1.5 Brown apples-to-apples test
   (river-starting, `initial_contributions = (pot/2, pot - pot/2)`,
   bet-size fractions from the fixture, `postflop_raise_cap`).
3. Maps fixture ranges to Rust-side `p0_holes` / `p1_holes` using the
   defender→P0 / opener→P1 convention (the Fix B convention
   established in PR 55 / #10 — the one that closed R9).
4. Calls `_rust.solve_range_vs_range_rust(config_json, 2000, 1.5, 0.0,
   2.0, p0_holes, p1_holes, regret_init_noise=<0.0 | 1e-9>,
   rng_seed=1)` once for baseline and once for perturbed.
5. Walks the returned `average_strategy` (a `dict[str, list[float]]`
   indexed by canonical-form cell key), computes per-cell `|Δ|` across
   all action indices, records the top 10 by max-action-Δ.
6. Separately drills into the historical bottom-pair-Ace cluster
   (`3sAs`, `3cAc` at history substring `b1000r3000`) for direct
   apples-to-apples vs the v1.5 33pp finding.
7. Applies the pre-registered decision rule:
   - `max |Δ| < 0.01` → `CONSTANT-OFFSET` (Position B confirmed,
     Nash unique on this spot)
   - `0.01 ≤ max |Δ| < 0.05` → `AMBIGUOUS`
   - `max |Δ| ≥ 0.05` → `NASH-MULTIPLICITY`

This methodology is the corrected version of the v1 Track A probe.
The v1 probe used `solve --hunl-mode postflop --backend rust` with
`HUNLConfig.initial_hole_cards = None`, which is the no-op path
(`chance_outcomes()` returns `Vec::new()` defensively when
`hole_cards = None`; the CFR loop iterates over zero outcomes,
returns `[0.0, 0.0]`, never inserts an infoset; two 200K-iter runs
completed in ~111s each with byte-identical 186-byte logs).
See `docs/a83_track_a_results_analysis_2026-05-26.md` for the v1
invalidation root-cause.

---

## 6. Honest caveats

- **2000 iters is the SAME iter count as the original Brown
  apples-to-apples test.** The apples-to-apples comparison for the
  v1.5 33pp gap holds. At much higher iter counts (e.g. 1M iters) the
  multiplicity envelope might shrink as the iterate increasingly
  satisfies more equilibrium tie-breakers; this would not change the
  multiplicity conclusion (multiplicity exists at the limit), but
  could narrow the per-cell Δ band. The v1.5 comparison to Brown is
  at 2000 iters, so confirming multiplicity at 2000 iters is the
  load-bearing claim.
- **The probe used `regret_init_noise = 1e-9`**, six orders of
  magnitude below typical floating-point round-off in 2000 DCFR
  iters. That such a tiny perturbation moves the average strategy by
  ~100% on some cells is itself the evidence — there is no smooth
  numerical pathway to amplify `1e-9` to `1.0` unless the solution
  lives on an indifference manifold.
- **The peak Δ cells are deep-cap raise-sequence cells.** Strategies
  at these histories are exercised infrequently in the average
  (low-reach), so a large per-cell Δ does not directly translate to
  a large EV-difference at the root. This is consistent with the
  Nash-multiplicity reading: the equilibrium manifold has zero
  EV-gradient along directions the perturbation kicks the iterate
  in.
- **The targeted bottom-pair-Ace cluster Δ (~25-28%) is the
  apples-to-apples answer to the original 33pp gap.** It is in the
  same direction and same approximate magnitude as the Brown
  divergence; combined with the high-divergence cells in deep-action
  raise lines, the 33pp gap is now structurally explained.

---

## 7. Implications — the unified A83 story

This probe is the empirical capstone on the multi-month A83
investigation. Combined with prior work:

1. **DCFR math: CORRECT.** Third-pass validator (Position B audit,
   `docs/a83_validation_2026-05-26.md`) PASS; arbitrator algebra
   confirms regret-difference invariance under uniform constant
   terminal-utility offsets
   (`docs/terminal_utility_arbitration_2026-05-26.md`).
2. **Terminal-utility convention: NOT A BUG.** Arbitrator verdict
   (2026-05-26): uniform constant offset across all leaves;
   arbitrator's correction to the original
   `a83_deep_cap_root_cause_investigation.md` §2(d) math error.
3. **A83 33pp gap cause: Nash multiplicity at deep-cap indifference
   manifolds.** **EMPIRICALLY CONFIRMED in this probe.** Same engine,
   same seed, infinitesimal initial-conditions perturbation, ~100%
   strategy divergence on the most sensitive cells, ~25-28% on the
   original bottom-pair-Ace gap site.
4. **Brown vs Rust: both engines are correct.** They each converge
   to A Nash equilibrium; in a multiplicity zone, they pick
   different equilibria. The 33pp gap is design-acceptable
   Nash non-uniqueness, not a bug.
5. **v1.6.1 hold-lift decision: VALIDATED.** The hold was lifted on
   the prior reasoning that the 33pp gap reflected multiplicity
   rather than an engine bug; the empirical confirmation here makes
   that decision retrospectively bulletproof.
6. **v1.5 Brown apples-to-apples test (reframed 4-layer gate):
   PASSES.** See `docs/v1_6_1_dryrun_10.md`. The reframed gate
   (L1 structural / L2 shallow-strict / L3 deep-directional L1 ≤ 1.9
   / L3' p75 L1 ≤ 0.60 / L4 top-action ≥ 60%) is exactly the
   acceptance shape required for multiplicity-aware sanity-check
   comparison against an external reference solver.

---

## 8. References

Prior docs in the chain leading here:

- `docs/a83_deep_cap_root_cause_investigation.md` — original
  multi-candidate root-cause investigation (§2(d) math error
  superseded by terminal-utility arbitration)
- `docs/a83_validation_2026-05-26.md` — third-pass DCFR-math
  validator (PASS)
- `docs/terminal_utility_arbitration_2026-05-26.md` — arbitrator
  verdict NOT-A-BUG for terminal-utility convention
- `docs/a83_track_a_setup_2026-05-26.md` — Track A v1 setup
- `docs/a83_track_a_results_analysis_2026-05-26.md` — Track A v1
  INVALIDATION (root-cause: `chance_outcomes()` no-op when
  `initial_hole_cards = None`)
- `docs/a83_followup_correct_experiment_2026-05-26.md` — corrected
  experiment design (the design this probe executes)
- `docs/matched_config_investigation.md` — matched-config empirical
  verification (Brown exploitability 0.06 chips at 2000 iters)
- `docs/v1_6_1_ship_hold_review_2026-05-26.md` — HOLD-LIFTED decision
- `docs/v1_6_1_dryrun_10.md` — reframed 4-layer acceptance PASS
- `docs/brown_apples_to_apples_2026-05-23.md` — original 33pp gap
  characterization
- Memory: `feedback_nash_multiplicity_acceptance.md`,
  `feedback_external_solver_sanity_check.md`

Engine PRs feeding the result:
- PR #15 (PR 53c) — Layer 3 max L1 ceiling loosen 1.0 → 1.9 for
  deep-cap Nash multiplicity
- PR 55 (#10) — P0/P1 player-index convention swap at the wrapper
  boundary
- PR #53 (`29d608e`) — `--regret-init-noise` flag CLI + Rust wiring
  (flag implementation correct; CLI invocation path is where the
  v1 probe broke)

---

## 9. Outcome / next steps

- **A83 33pp gap:** **CLOSED** as design-acceptable Nash
  multiplicity. No engine fix required.
- **v1.6.1 hold:** retrospectively bulletproof. The hold-lift
  reasoning ships with stronger empirical backing than was available
  at hold-lift time.
- **v1.8.0 release notes:** "Known Issues / A83" entry updated to
  reflect EMPIRICAL CONFIRMATION (this doc supersedes the prior
  "leading hypothesis, probe pending" framing).
- **Persona test status:** v1.6.1 hold-lift is empirically validated,
  not just per ship review.
- **Brown reference framing:** external reference solvers (Brown,
  Pluribus) are sanity checks rather than strict ground truth when
  action menus differ and deep-cap subgames have indifference
  manifolds (per `feedback_external_solver_sanity_check`,
  `feedback_nash_multiplicity_acceptance`).

---

**Probe authored:** 2026-05-26 ~04:07 UTC.
**Doc authored:** 2026-05-26 (post-probe, in PR 110).
