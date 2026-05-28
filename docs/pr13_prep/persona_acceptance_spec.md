# PR 13 — Persona-Driven User Acceptance Spec

**Status:** spec only (no implementation prompts yet). Owns the gating gauntlet that decides whether the solver is genuinely "done" from a user's perspective, separate from the engineering checks (`pr_report.md`, `audit_report.md`, differential tests) that gate each PR.

**Why this exists.** The engineering battery proves the algorithm is correct on small games and bit-exact against Brown's MIT reference on river spots. It does not prove that a real poker player can sit down with the solver and answer the questions they actually have. PR 13 walks four representative personas through their real workflows, end to end, and logs every gap — "feature shipped but USAGE.md doesn't mention it," "feature missing entirely," "feature returns implausible output." A workflow the engineering battery considers green can still be a P0 user-acceptance fail; that is the failure mode this PR exists to catch.

**Scope.** Twenty-three workflows across five personas: Marcus / Sarah / Daniel × 5 + Priya × 3 = the original 18, plus five Premium-A workflows (Wendy × 5) authored 2026-05-28 to cover the blueprint feature shipped via PRs #173 / #174 / #177 / #181 (task #68 Phases 2-5) and the B10 per-combo range trail (PRs #149 / #154 / #158). Each workflow has an outcome category (`WORKS` / `WORKS-BUT-DOCS-CONFUSING` / `DOESN'T-WORK` / `BUG`), a heuristic-based sanity check on the output, and a wall-clock budget anchored to the recalibrated rubric.

**Time-budget calibration.** Wall-clock targets and the kill-switch policy for every workflow below are governed by `docs/pr13_prep/persona_time_budgets.md` — that is the authoritative source. Single-spot interactive solves target 1–5 min (Pio-class); any single-spot workflow exceeding 30 min is a kill-switch event, not an accepted budget. No "hours overnight" framing in acceptance tests; batch workflows live in `scripts/batch_solve.py`, not in the persona harness. The harness lives in `tests/test_persona_acceptance.py` (PR 13 deliverable); workflows today's code cannot satisfy are marked `xfail` and become PR 9 / future-roadmap tickets.

---

## 1. Personas

**Marcus — casual recreational player.** Plays $0.25/$0.50 HU online on weekends; ~5 hr/week play, ~30 min/week study. Comfortable in a terminal because he uses it at work, but does not write Python. Installs the `.dmg` and expects the CLI to answer concrete post-mortem questions — "was that jam right?" or "should I have called the river?". Does not read docs; if a workflow takes more than two CLI invocations he gives up and goes to GTO Wizard mobile. Sessions are short and bursty: answers in seconds, not minutes.

**Sarah — serious amateur, aspiring pro.** Plays $1/$2 to $5/$10 HU online; ~30 hr/week play, ~10 hr/week study. Writes Python comfortably and treats the solver as both a CLI tool and a library — imports `poker_solver` into Jupyter notebooks to build her own range charts and compare them to her hand histories. Cares about end-to-end reproducibility: same config, same seed, same answer. Heavy user of preflop range charts; expects the solver to give her a full HU 100 BB SRP tree, not just push/fold. Tolerates 15-minute solves; does not tolerate output that disagrees with industry-standard heuristics without an explanation.

**Daniel — pro / coach.** Plays $10/$20+ HU; ~8 hr/week play, ~20 hr/week coaching and study. PioSolver is his daily driver and he is evaluating `poker_solver` as a free, MIT-licensed alternative for his students. Expects fine-grained controls: node locking, custom starting ranges per player, exploitability targets in % pot, mixed-strategy decomposition. Highest bar of the four — a feature is acceptable only if he can recommend it to a paying student without caveats. Missing node-locking is a P0 fail in his book.

**Priya — researcher / developer.** CS PhD; building tools on top of the solver (GTO-deviation detector for hand histories, tournament simulator for academic experiments, custom limp-or-fold variant). Lives in Python, reads Rust as needed, cares about API stability and scriptability. Wants the Python tier to be a clean library (typed, importable, reproducible) and the Rust tier to be a black-box performance backend selectable via flag. Does not need the UI.

**Wendy — weekend grinder (Premium-A consumer).** Plays $0.50/$1 to $2/$5 HU online; ~12 hr/week play, ~4 hr/week study split across the desktop UI and quick CLI checks. Treats the solver as a "GTO Wizard for Mac" — opens the .dmg, picks a chart, expects an answer in under 100 ms. Doesn't care whether the answer came from a blueprint lookup, an interpolation, or a live solve, but DOES expect the UI to say which (the "blueprint" / "interpolated" / "live" badge). Two of her sessions per week need a postflop continuation; she expects the chained tab to anchor preflop on the blueprint and live-solve the flop subgame in 5-30 s. Switches between tournament (ante) and cash (no-ante) formats; expects the chart to materially shift when she toggles. Heavy customizer: occasionally edits a 3-bet range cell in the B10 per-combo editor and expects the result to reflect HER range, not the blueprint baseline.

---

## 2. Workflow catalog (Marcus / Sarah / Daniel × 5 + Priya × 3 + Wendy × 5 = 23)

### Marcus

**W1.1: "I jammed 88 from SB at 9 BB; was that right?"** — Confirm a short-stack push via CLI. `--help` shows no `pushfold` subcommand; USAGE.md §3a documents `get_pushfold_strategy(9, 'sb_jam', '88')`. <50 ms lookup; expected ~1.0 jam (Sklansky-Chubukov, *Tournament Poker for Advanced Players* — 88 jams through ~13 BB HU SB). `WORKS-BUT-DOCS-CONFUSING`. Fix: ship `poker-solver pushfold` CLI wrapper OR USAGE.md §3a callout. Severity: medium.

**W1.2: "Villain bet pot on river. I have JJ on As Tc 5d Jh 8s. Was calling right?"** — Mid-stakes river call. `default_tiny_subgame()` hard-codes a different fixture; `--hunl-mode postflop` accepts `--board`/`--stacks` but not `--hero` / `--villain` / `--starting-ranges`. Workflow blocked. Expected call freq ≈ 1.0 (MDF vs pot = 50%; JJ well above median). `DOESN'T-WORK` — the single most common spot a rec player wants to check. Fix: `poker-solver river --board "As Tc 5d Jh 8s" --hero "JhJd" --villain-range "QQ+,AKs,A5s,T9s" --bet pot`. Severity: high.

> **Note (2026-05-23 late — `docs/poker_spots_audit_CORRECTED_2026-05-23.md` Spot 8 + `docs/poker_spots_reverification_2026-05-23.md` Spot 8 + `docs/pr13_prep/persona_verdict_revision_history.md`):** the v1.4.1 retest config (`starting_stack=1500`, `initial_contributions=(1500, 500)`) puts villain already all-in (0 chips behind), reducing hero's legal action set to `[fold, call, all_in]` — no room for an intermediate raise. This config CANNOT validate the spec's broader reraise dynamic ("set of jacks vs polarized bet → value-jam to extract from worse sets, accept going broke vs AA-set"). The W1.2 retest verdict was revised PASS → PARTIAL on 2026-05-23 late. To properly close the engine half, re-run with DEEPER STACKS (e.g. `starting_stack=20000` = 200 BB) plus proportional contributions to make `[raise_2x, raise_3x, all_in]` legal, and use PR 37's `tests/_equity_helpers.py` for rigorous per-combo equity assertion. Also: the spec phrasing "MDF vs pot = 50%" is the MDF range-level heuristic; the per-combo 1v1 engine uses pot odds (33.3% required equity = 1000 / 3000 here). JJ raw equity vs the listed villain range is 93.3% (loses only to AA = 3/45 combos), so strict Nash defend ≈ 100%.

**W1.3: "Quick equity check: AKs vs JJ on As Tc 5d?"** — `poker-solver equity AhKh JhJd --board "As Tc 5d"` (USAGE.md §3c). ~60 ms exact enumeration over 990 turn-river combos. Expected AKs ≈ 27%, JJ ≈ 73% (Pio/pokerstove community standard for TPTK vs A-blocked overpair). `WORKS`. Fix: none. Severity: n/a.

**W1.4: "I want to study the standard 100 BB SRP"** — Browse the standard HU 100 BB SRP preflop tree. `--hunl-mode full` raises `NotImplementedError` (`cli.py:146-149`); push/fold tops out at 15 BB. Post-PR-9: 10–30 min, 169-cell chart. Heuristic: SB opens ~80–85%, BB defends ~70% via calls + 3-bets (industry standard). `DOESN'T-WORK` — PR 9 is the explicit blocker. Fix: ship PR 9. Severity: high.

**W1.5: "Why did the solver say to fold 76s preflop at 10 BB?"** — Sanity-check a charted decision. `get_pushfold_strategy(10, 'sb_jam', '76s')` returns a frequency; no EV decomposition. Expected ~1.0 jam (76s has ~38% equity vs wide; jams are +EV at 10 BB except vs tight Nash). `WORKS-BUT-DOCS-CONFUSING` if chart agrees with intuition; `BUG` candidate if not. Fix: add `return_ev=True` keyword returning `(freq, ev_jam_bb, ev_fold_bb)`. Severity: low.

### Sarah

**W2.1: "Generate the full HU 100 BB preflop range chart"** — Post-PR-9: `solve(HUNLPoker(HUNLConfig(starting_stack=10_000)), iterations=200_000, backend="rust")` and pivot `result.average_strategy` into a 13×13 matrix. 10–30 min on Rust tier; expect SB open ~80–85%, BB 3-bet ~12–18% (industry standard). `DOESN'T-WORK` today — PR 9 blocker. Severity: high.

**W2.2: "Compare my BB 3-bet range vs GTO 3-bet range; where am I leaking?"** — Diff Sarah's hand-history range vs the GTO baseline. `Range` supports `parse_range("AA,KK-TT,AKs+")` but no `range.diff(other)`. Seconds post-PR-9; expect a leak list ("KQo: you 3-bet 0%, GTO 25%"). Common leaks: under-3-betting KQo/AJo, over-3-betting low pairs. `DOESN'T-WORK` today. Fix: PR 9 + `range.diff(other) -> Range` utility. Severity: medium.

**W2.3: "Solve KK on Q-high flop vs villain's c-bet range"** — Flop subgame with custom starting ranges. `solve_hunl_postflop(config, hero_range=..., villain_range=...)` does not exist; ranges are baked in only via `initial_hole_cards` (one combo per player). 5–15 min on standard flop, Rust tier. Heuristic: KK on Q-high is near-100% defend with mixed raises vs bluff-heavy c-bets. `DOESN'T-WORK` — P0 gap affecting three of four personas. Fix: extend `HUNLConfig` with `hero_range: Range | None` and `villain_range: Range | None`; thread through `hunl_solver.py` and the Rust tier. Severity: high.

**W2.4: "Verify the batch-solve CSV schema works on a 3-spot 'standard 3-bet pot' library"** — `poker-solver batch-solve --input spots.csv` exists (`cli.py:855-864`), delegates to `scripts/batch_solve.py`. USAGE.md §5 documents library mode but not CSV schema. Acceptance test exercises a 3-row CSV (one solve per row at standard accuracy) — exits within Sarah's session budget (<15 min total, per `persona_time_budgets.md §2`); per-spot must complete in 1–5 min Pio-class, kill-switch at 30 min. Expect 3 rows in `~/.poker_solver/library.db` with exploitability < 0.5% pot. `WORKS-BUT-DOCS-CONFUSING` if `scripts/batch_solve.py` is wired and schema documented; confirm during PR 13. Fix: USAGE.md §5a "batch mode" with CSV schema. Severity: medium.

**W2.5: "What does 30 BB SRP look like preflop?"** — Sub-100 BB preflop study. `--hunl-mode full --stacks 30` raises `NotImplementedError` regardless of depth; push/fold tops out at 15 BB. 10–30 min post-PR-9. Heuristic: 30 BB SRP — SB opens ~70% (tighter than 100 BB), 4-bet jams enter BB defense. `DOESN'T-WORK`. Fix: PR 9. Severity: high.

### Daniel

**W3.1: "If villain never bluffs the river, re-solve my decision"** — Node-lock villain's river bluff frequency to 0. PLAN.md §1 lists node-locking under "Features beyond v1." No `node_lock(infoset, action, freq)` API in either tier; no UI control. Feature absent. Heuristic: "no-bluff" exploit ⇒ hero pure-folds bluff-catchers; MDF doesn't apply because villain is not balanced. `DOESN'T-WORK`. Fix: standalone post-v1 PR (v1.3 candidate). Severity: high (Daniel's #1 missing feature).

**W3.2: "Compare GTO frequencies vs my opponent's actual frequencies on river bets"** — Load opponent's empirical frequency, compute exploitative response. Depends on (a) range-vs-range solver (W2.3) and (b) best-response API. `solver.py` exposes a private `_best_response_value` used for exploitability computation; not public, doesn't accept "fix this strategy at arbitrary infosets." Heuristic: villain's actual bluff freq below MDF ⇒ hero overfolds; above ⇒ overcalls. `DOESN'T-WORK`. Fix: expose `best_response(game, fixed_strategy, player)` as public API. Severity: high.

**W3.3: "Build a merged-strategy range (50% raise / 50% call) and see what GTO does against it"** — Simulate range merging, find the maximally exploitative GTO response. Depends on node-locking at scale (W3.1 blocker). Heuristic: vs a merged range, hero gets thinner value with strong hands and bluffs less. `DOESN'T-WORK`. Fix: downstream of W3.1. Severity: medium.

**W3.4: "MDF check: BB should defend ≥ MDF vs half-pot c-bet; verify"** — Numerical heuristic sanity check. Post-W2.3: solve a half-pot flop c-bet with standard 100 BB SRP ranges; sum BB's call+raise frequency. 5–15 min. Expected: BB defends ~67% (MDF = 1 − 0.5 / 1.5). Heuristic: Sklansky *Theory of Poker*; PioSolver coaching (`references/products/piosolver_technical_details.md`). `WORKS-BUT-DOCS-CONFUSING` if W2.3 lands; `DOESN'T-WORK` today. Fix: ship `test_mdf_bb_vs_half_pot_cbet` asserting BB defended ∈ [MDF, 0.85]. Severity: medium.

**W3.5: "Polarization sanity: on a monotone board, expected polarized betting range"** — On a monotone flop (e.g. `Ah 7h 2h`), the solver should output a polarized betting range (top set + flush + bluffs; no medium-strength bets). Post-W2.3, 5–15 min. Heuristic: monotone polarization is GTOW canon (`gtow_how_solvers_work.md`, `gtow_quirks_multiway_nash.md`). `DOESN'T-WORK` today (W2.3 blocker). Fix: ship a polarization gauntlet test post-W2.3. Severity: medium.

> **Note (2026-05-23 late — `docs/poker_spots_audit_CORRECTED_2026-05-23.md` Spot 3 + `docs/poker_spots_reverification_2026-05-23.md` Spot 3 + `docs/pr13_prep/persona_verdict_revision_history.md`):** range-vs-range (RvR) polarization is ONLY testable post-PR-23 (chance-enum perf cliff fix). The v1.4.1 W3.5 retest used a per-combo perfect-info proxy ("AA bets vs known-air villain combo, checks vs known-flush villain combo") — that proxy is the trivial best response and is a WEAK SUBSTITUTE for range-level Nash polarization. Under per-combo perfect info, bluff frequency and bet-sizing polarization are FUNDAMENTALLY UNOBSERVABLE; the visible "value-side" pattern is a tautology of the test setup, not Nash evidence. The W3.5 retest verdict was revised PASS → TEST-DESIGN-FAIL (~ BLOCKED) on 2026-05-23 late. Correct test path: `solve_range_vs_range` on a monotone flop with a polarized aggressor range + bluff-catcher defender range, gated on PR 23 fix. User intuition (validated): on a monotone Ts 8s 6s 4c 2d, range-Nash AA should be ~80-95% CHECK, NEVER large bets, and FOLD to large bets/raises.

### Priya

Priya is the API consumer / researcher persona; her three representative workflows exercise library shape, extensibility, and parity respectively. Per `persona_time_budgets.md §4` and the no-looped-query rule, these are *single representative* invocations — not N=1000 loops, not overnight batch — and each cites the per-spot Pio-class budget (1–5 min standard accuracy, 30 min kill switch).

**W4.1: "Programmatic build + parse a result into pandas"** — Call `solve_hunl_postflop` once on a representative config, store `HUNLSolveResult.average_strategy` as a row, confirm `Library.put(spot, result)` round-trips. Single spot at standard accuracy (per Section 1 cell): <5 min Pio-class, kill switch at 30 min. Expect a `DataFrame` row with exploitability < 0.5% pot and a deterministic SHA256 spot ID. `WORKS-BUT-DOCS-CONFUSING` — pieces exist; no documented "20-line script" recipe. Fix: USAGE.md §5b or DEVELOPER.md §11 worked example. Severity: low.

**W4.2: "Add a custom 'limp-or-fold' mode for play vs short stacks"** — Extend the action abstraction to a 2-action menu. `ActionAbstractionConfig(include_all_in=False, bet_size_fractions=())` covers part of it; "limp" is a preflop SB-CALL handled by `_apply_player`'s SB-call branch. DEVELOPER.md §5 documents adding a new *game*, not an action-menu variant. Acceptance test exercises one limp-or-fold solve at standard accuracy: <5 min Pio-class, kill switch at 30 min. Heuristic: limp-or-fold equilibrium is mostly determined by BB's iso-raising frequency. `WORKS-BUT-DOCS-CONFUSING` — hooks exist; docs don't connect them. Fix: DEVELOPER.md §5a "extending the action abstraction." Severity: low.

**W4.3: "Diff our solver vs Brown's noambrown on a novel river spot"** — Extend the PR 7 diff test to a user-supplied spot. `tests/test_river_diff.py` does this on the canonical fixture; Priya wants to feed her own. Harness is test-coupled; no public `cross_validate(config, against="noambrown")` API. One representative novel-spot diff at standard accuracy: <5 min per side, <15 min total (Priya session budget per Section 2). Expect agreement to 1e-4. `WORKS-BUT-DOCS-CONFUSING` — machinery in `tests/`, not a library function. Fix: expose `poker_solver.parity.diff_vs_noambrown(config) -> DiffReport`. Severity: low.

### Wendy (Premium-A consumer)

Wendy's five workflows exercise the blueprint feature shipped via task #68 Phases 2-5 (PRs #173 / #174 / #177 / #181) plus the B10 per-combo range trail (PRs #149 / #154 / #158). Per the Premium-A subplan and `docs/blueprint_user_guide.md` the blueprint ships **27 cells = 9 stack depths × 3 ante configurations** (20, 30, 40, 60, 80, 100, 150, 175, 200 BB × `none` / `half` / `full`); off-grid depths interpolate convexly between flanks; off-blueprint inputs (custom range, non-canonical menu, non-standard ante) route to the live-solve fallback. The harness lives in `tests/test_w5_premium_a_personas.py`; the persona is gated by `tolerance_marcus_class` (Wendy inherits Marcus's <100 ms interactive tolerance per `persona_time_budgets.md §1` — her clock budget tracks Marcus's because the blueprint is supposed to FEEL instant).

**W5.1: "Pull the 100 BB no-ante preflop chart in under 100 ms with a 'blueprint' badge"** — GUI / `SolverRouter.solve(stack_bb=100, ante='none', hand='AKs', action_history='')`. Expected: `result.route == 'blueprint_lookup'`, `result.confidence == 'exact'`, warm-cache lookup wall **< 100 ms** (cold-cache first lookup < 200 ms acceptable; subsequent same-shard lookups < 1 ms on M-series silicon). Strategy vector sums to 1.0 ± 1e-9 (probability simplex). At least 10 of the 169 cells (e.g. `AA`, `KK`, `QQ`, `AKs`, `AKo`, `72o`, `JJ`, `TT`, `99`, `88`) return non-empty strategies. **Enabled by:** PR #174 (BlueprintLoader, `feat(blueprint): loader API + manifest discovery + lazy load (Phase 2, #68)`). `WORKS`. Severity: n/a (validates intended Premium-A consumer experience).

**W5.2: "Pull a chart at 67 BB (off-grid) with an 'interpolated' badge"** — GUI → `SolverRouter.solve(stack_bb=67, ante='none', hand='AA', action_history='')`. Expected: `result.route == 'interpolated'`, `result.confidence == 'interpolated'`, `result.meta['depths'] == (60, 80)`, wall **< 100 ms** (loads two flanking shards + per-cell linear blend; the shards may already be warm from prior W5.1 lookups). Strategy must be the convex blend of the 60 / 80 BB strategies at `t = 0.35` (= (67 − 60) / (80 − 60)): each entry equals `0.65 * v60[i] + 0.35 * v80[i]` up to ULP renormalization (1e-9 tolerance). Sums to 1.0 ± 1e-9 per the convex-combination-stays-on-simplex invariant. **Enabled by:** PR #173 (interpolation module, `feat(blueprint): stack-depth interpolation module (Phase 3, #68)`) + PR #181 (router dispatch, `feat(blueprint): top-level solver router (lookup / interp / live / postflop) (Phase 5, #68)`). `WORKS`. Severity: n/a.

**W5.3: "Chain a preflop blueprint with a postflop subgame on Q♠7♥2♦"** — GUI chained tab → `SolverRouter.solve(stack_bb=100, ante='none', action_history='b300c', board=(Qs, 7h, 2d))`. Expected: `result.route == 'postflop_subgame'`, `result.confidence == 'live_solved'`. The pipeline must (a) lookup a preflop blueprint to derive continuation ranges, (b) expand the 169-class strategy to 1326 per-combo weights filtering board collisions, (c) live-solve the flop subgame via `solve_range_vs_range_nash`. Both stage badges populated: `wall_time_lookup_s` populated (blueprint instant) AND `wall_time_solve_s` > 0 (live solve happened). **Enabled by:** PR #177 (postflop subgame wiring, `feat(blueprint): postflop subgame wiring + range expansion (Phase 4, #68)`) + PR #182 (b/r token normalization fix, `fix(blueprint_subgame): normalize b/r token equivalence at preflop boundary`) + PR #181 (router dispatch). `WORKS` on the wiring contract; the **production-scale fixture** (shipped 169-class blueprint at 100 BB, full b300c line, Qs7h2d flop) currently OOMs at every credible class-filter setting per `docs/flop_subgame_perf_measurement_2026-05-28.md` — the v1.10 optimization roadmap (`docs/v1_10_postflop_optimization_plan.md`) is the path to a production-scale W5.3 PASS. Until v1.10 lands, the persona acceptance test exercises a **synthetic 2-class smoke fixture** (mirroring `test_solve_postflop_from_blueprint_end_to_end_flop` in `tests/test_blueprint_subgame_wiring.py`) — sufficient to verify the lookup / expand / solve wiring, not the shipped-blueprint production scale. Severity: n/a (wiring contract); follow-up: retarget at the shipped blueprint once v1.10 perf work lands.

**W5.4: "Edit my 3-bet range (B10) and force a custom live solve, not the blueprint baseline"** — Wendy edits a per-combo cell in the B10 intensity editor (PR #158) → `SolverRouter.solve(..., range_override=Range)`. Expected: `result.route == 'custom_live_solve'`, `result.confidence == 'live_solved'` — the router **must NOT** serve the blueprint when a `range_override` is provided (the blueprint format is class-uniform and cannot represent per-combo variation; serving it would silently lose Wendy's custom edit). The decision-route check (`_decide_route`) returns `'custom_live_solve'` even at an exact blueprint depth (100 BB) and exact ante (`none`). **Enabled by:** PR #181 (`SolverRouter._decide_route` rule 2: range_override forces live solve) + B10 Phase A/B/C (PRs #149/#154/#158, per-combo Range data model). `WORKS`. Severity: n/a.

**W5.5: "Switch between cash (no-ante) and tournament (half / full ante) formats at 40 BB; results must materially shift"** — GUI ante toggle → `SolverRouter.solve(stack_bb=40, ante=<ante>, hand=<hand>, action_history='')` for each of `{'none', 'half', 'full'}` and a representative hand pair (one wide marginal hand like `72o`, one premium like `AA`). Expected: at least one of the three ante configurations produces a measurably different strategy from the others (L1 distance > 0.05 across the 7-action vector) for the marginal hand — antes shift pot odds, so the equilibrium MUST shift; serving the same strategy for all three would indicate the ante dimension wasn't actually wired through. All three route to `'blueprint_lookup'` (40 BB / all three antes are exact shards). No errors raised on any of the three calls. **Enabled by:** the 27-shard `assets/blueprints/` bundle (chore commit `1783bef`, `chore(blueprints): ship 27 preflop blueprint shards (21 MB) + manifest`) + PR #174 (loader handles all 3 ante tokens via `normalize_ante`). `WORKS`. Severity: n/a.

---

## 3. Heuristics reference table

| Heuristic | Formula / threshold | Source |
|---|---|---|
| Minimum Defense Frequency (MDF) | `MDF = 1 − bet_size / (bet_size + pot)` | Sklansky, *Theory of Poker*; PioSolver coaching (`references/products/piosolver_technical_details.md`). |
| Bluff-to-value ratio (river) | `b/v ≈ bet_size / (bet_size + pot)` for villain to balance | Janda, *Applications of NLHE*; GTOW blog. |
| Polarization on monotone boards | aggressor's range splits into nut-suited + busted-suited bluffs; medium-strength hands check | `references/blog/gtow_how_solvers_work.md`. |
| SB open frequency, HU 100 BB | ~80–85% | GTO Wizard published HU 100 BB charts. |
| BB 3-bet frequency, HU 100 BB | ~12–18% | Same. |
| Short-stack jam threshold (HU SB) | ~all pocket pairs + Ax + Kx jam at ≤10 BB | Sklansky-Chubukov, *Tournament Poker for Advanced Players*. |
| Convergence target (exploitability % pot) | Standard <0.5%; GTO Wizard 0.1–0.3% | `references/blog/gtow_how_solvers_work.md`. |
| HU equity (AKs vs JJ on A-high flop) | ~27% / 73% | Pokerstove community standard. |

Citations are intentionally to publicly readable sources (no paid GTOW Premium URLs).

---

## 4. Verification framework

For each workflow:

1. **Wall-clock budget.** Anchored to `persona_time_budgets.md` (authoritative rubric). Per-spot at standard accuracy: push/fold lookup <500 ms; equity HvH <1 s; equity range-vs-range MC 250k <30 s; single-spot fixed-cards subgame <30 s; range-vs-range medium (10×10) <2 min; single subgame Pio-parity 1–5 min standard / 10–30 min tight; full preflop chart <30 min. **Kill-switch:** any single-spot workflow exceeding 30 min terminates the test and triggers a perf-bug investigation (30 min is the upper bound, never a target). Session totals follow `persona_time_budgets.md §2` per persona context.
2. **Intuitive correctness check.** Each workflow has a heuristic + tolerance band in §2. Output outside the band is a `BUG` candidate; pre-band review with a poker-domain reader before filing.
3. **Outcome logging.** `tests/test_persona_acceptance.py` emits one record per workflow into `docs/pr13_prep/run_<vX.Y.Z>.jsonl`:
   ```json
   {"workflow": "W1.1", "persona": "Marcus", "category": "WORKS-BUT-DOCS-CONFUSING",
    "wall_clock_ms": 47, "expected_band": "freq in [0.95, 1.0]",
    "observed": 1.0, "notes": "..."}
   ```
4. **Aggregated report.** `scripts/persona_report.py` reads the JSONL and prints a per-persona pass / partial / fail summary. Goal: ≥ 16 / 18 `WORKS` to declare v1.X "user-acceptable."

---

## 5. Recurring schedule

- **First run:** immediately after PR 9 (HUNL preflop) lands — version target **v1.2.0**. PR 9 is the largest single unblocker (4 of 20 workflows depend on it).
- **Recurring:** every minor version bump (vX.Y.0). Patch releases skip unless explicitly touching a workflow surface.
- **Memory rule to enforce:** add MEMORY.md entry `[Persona acceptance recurring](feedback_persona_acceptance.md)` listing workflow IDs, wall-clock budgets, and the trigger ("on every vX.Y.0 release branch, before tagging, run `pytest tests/test_persona_acceptance.py -m persona` and require ≥ 16 / 18 WORKS").
- **Pre-release hook.** Add a step to `scripts/build_macos_dmg.sh` that runs the persona harness with `-m 'persona and not slow'` and fails the build if any non-slow workflow regresses from `WORKS` to a worse category.

---

## 6. Cross-cutting findings (synthesis)

- **Top P0 gaps for v1.2.0:** (a) range-vs-range solver inputs (W2.3, W3.4, W3.5 all blocked); (b) node-locking (W3.1, W3.3 blocked); (c) preflop solver beyond push/fold (W1.4, W2.1, W2.2, W2.5 blocked — PR 9 covers this); (d) a `pushfold` CLI subcommand and a "river spot vs villain range" CLI surface (W1.1, W1.2).
- **Strong existing surface:** equity (W1.3), push/fold lookup (W1.1 modulo discoverability), seed determinism (W4.3), library persistence (W4.1 modulo recipe docs).
- **Documentation debt:** USAGE.md does not document the `batch-solve` CSV schema (W2.4), API-level library round-trip recipe (W4.1), or `parity` test internals (W4.3).
- **Node-locking is the single feature most aligned with Daniel's persona;** without it the pro/coach persona fails 3 / 5 workflows. Recommended: scope node-locking as a self-contained future PR — it does not require new card-abstraction work, only a constraint layer on the regret-matching step.

---

## 7. Audit-trail addendum (2026-05-23 late) — W2b cohort and W2.2 retest methodology

This section captures revisions to the persona testing methodology, separate from the workflow catalog above. Source documents: `docs/poker_spots_audit_CORRECTED_2026-05-23.md`, `docs/poker_spots_reverification_2026-05-23.md`, `docs/pr13_prep/persona_verdict_revision_history.md`.

**W2.2 line (W2.2 = Sarah's BB 3-bet range diff):** no change to the spec line above — corrections to W2.2 were already propagated in PR 29.

**W2b cohort (W2b.1, W2b.2, W2b.5 — internal Phase 2b testing nomenclature, not in the §2 catalog):** the Phase 2b retest methodology had FLAWS that did not surface a code bug but did mis-frame what the tests demonstrated. Specifically:
- **W2b.2 "flat sizing between bet_33 and bet_75 = Nash indifference"** was the WRONG framing. Villain's range contains QQ-trips, AQs-two-pair, KQs-flush — these crush KK and would NEVER fold to a bet. The flat sizing reflects KK essentially NEVER betting at all (because betting into the QQ/AQs/KQs portion is large -EV), with the 10⁻⁷ residual being DCFR convergence noise where neither size is favored because both are dominated by checking. Solver behavior CORRECT; rationale needed revision (now propagated to `docs/pr13_prep/v1_3_2_phase2b_audit.md` Audit Target #2).
- **Per-combo perfect-info subgames do NOT measure range-level Nash.** The W2b.5 "AA crushes underpair" observation is per-combo true (AA = 100% equity vs all four underpair classes), but the aggregator's "check=0.904, all_in=0.096, bet_75 ≈ 0" output reflects perfect-info 1v1 collapse, not range-Nash polarization or sizing strategy. The Phase 2b "EV(bet) = pot, independent of s" framing was math-correct under the dead-money convention but per-combo only — range-level Nash with a mixed villain range would produce different dynamics.

**Solver code correctness was confirmed in every audited Phase 2b spot;** the corrections are purely test-methodology / rationale. See `docs/pr13_prep/v1_3_2_phase2b_audit.md` for the per-target framing corrections.
