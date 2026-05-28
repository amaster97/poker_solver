# Premium-A Blueprint — External GTO Reference Inventory

**Phase:** Premium-A Phase 7 (diff-test seed)
**Date:** 2026-05-28
**Parent subplan:** `docs/premium_a_blueprint_subplan.md`
**Parent issue:** Premium-A blueprint subplan / Premium-A Phase 7 (#68)
**Tolerance budget (user-decided, subplan §8 Q3 option b):** L1 per hand class ≤ 0.05 at 100 BB

---

## 1. Purpose

When Premium-A generates 27 blueprints (8 stack depths × ante configurations
per the matrix in the subplan §2 Phase 1 / §8 Q1–Q2 — count adjusts based on
final depth × ante × convention selection), each blueprint needs an
**independent diff-test** against external GTO references before it can be
trusted as a production strategy.

Per memory rule [`feedback_reference_first`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_references.md):
**check `references/` first; do not guess; do not scrape new data without user authorization.**

This inventory documents what is **already on disk** that can serve as a
reference, and (more importantly) **what is not** — so Phase 7's diff-test
authors do not waste time looking for data that does not exist locally.

Per memory rule [`feedback_external_solver_sanity_check`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_external_solver_sanity_check.md):
external GTO references are **sanity checks**, **not strict ground truth**.
Divergence on deep-cap depths (200 BB) is acceptable per
[`feedback_nash_multiplicity_acceptance`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_nash_multiplicity_acceptance.md).

---

## 2. What is on disk today

### 2.1 Papers (algorithmic context; no strategy data)

Location: `references/papers/`

| Paper | Reference content | Strategy data? |
|---|---|---|
| `pluribus_brown_2019_science.pdf` | 6-player NLHE blueprint architecture (MCCFR + LCFR-then-stop-discounting + 95%-iter negative-regret pruning); compressed to ≤128 GB | **No.** Aggregate frequencies in figures; no per-class data tables. |
| `libratus_brown_2017_science.pdf` + `..._supplement.pdf` | HUNL blueprint architecture (ES-MCCFR with regret-based pruning); abstraction details | **No.** Architecture and aggregate metrics only. |
| `depth_limited_brown_2018.pdf` | Modicum depth-limited solving recipe; HUNL bet menu `[0.5x, 1x]` early then `[1x, all-in]` | **No.** |
| `dcfr_brown_2019.pdf` | DCFR `(α,β,γ)` defaults — `(1.5, 0, 2)` Brown standard | **No.** |
| `rebel_brown_2020.pdf` | Neural-net + PBS-guided real-time solving | **No.** |
| `cfrplus_tammelin_2014.pdf` | CFR+ recipe | **No.** |
| `deep_cfr_brown_2018.pdf` | Network-replaced regret table | **No.** |
| `gibson_2013_regret_minimization.pdf` | Multiway CFR honesty | **No.** |
| `zinkevich_2008_cfr_nips.pdf` | Original CFR | **No.** |
| `gto_poker_survey_2024.pdf` | Survey / context | **No.** |
| `hyperparam_schedules_2024.pdf` | HS-DCFR schedules | **No.** |

**Gap:** None of the foundational papers in `references/papers/` publish
per-hand-class HU preflop strategy tables that we could load as a fixture.
Pluribus is 6-player; Libratus describes architecture, not the blueprint
contents.

### 2.2 OSS solver source repos (algorithmic patterns; can generate references)

Location: `references/code/` (gitignored — re-cloned via `scripts/setup_references.sh`)

| Repo | License | Can generate HU preflop blueprint? | Already cached output? |
|---|---|---|---|
| `noambrown_poker_solver/` | MIT | **River-only** subgame solver — does **not** solve preflop. | No. |
| `slumbot2019/` | MIT | Yes — has `show_preflop_strategy.cpp` + `show_preflop_reach_probs.cpp` utilities, but only after a blueprint training run. Production blueprint not shipped. | No solved-strategy artifacts in repo. |
| `open_spiel/` | Apache 2.0 | Kuhn / Leduc only via `algorithms/cfr.cc`. **Not** HU NLHE preflop. Useful as Kuhn/Leduc oracle, **not** as HU preflop reference. | No. |
| `postflop-solver/` | AGPL (read-only) | **Postflop only** — does not handle preflop. | No, and copying would relicense. |
| `TexasSolver/` | AGPL + commercial | Postflop solver. PioSolver-aligned output schema in `resources/outputs/outputs_strategy.json`. Not preflop. | No preflop fixtures. |
| `shark-2.0/` | Unlicensed | C++20 full-tree solver. Could in theory generate; but read-only inspiration policy (`references/README.md` §2). | No solved artifacts in repo. |

**Gap:** No OSS solver in `references/code/` ships with a precomputed HU preflop
blueprint. Slumbot has the tooling but the trained data lives behind a
separate (~weeks-long) ACPC training pipeline. The closest accessible
oracle for diff-testing is **our own existing river-vector parity wrapper
against `noambrown_poker_solver`** (`poker_solver/parity/noambrown_wrapper.py`),
which is **river-only** and therefore does NOT help Phase 7's preflop diff-test.

### 2.3 Blog notes (operational context; no strategy data)

Location: `references/blog/`

| File | Reference content | Per-class data? |
|---|---|---|
| `gtow_ai_benchmarks.md` | GTOW vs Pio / vs Slumbot win rates | No. |
| `gtow_how_solvers_work.md` | Nash Distance thresholds (<1% pot = converged + mixed, <0.5% = professional, GTOW targets 0.1–0.3%); operational intuition | No. |
| `gtow_multiway_preflop_launch.md` | Fast Mode vs Classic Mode | No. |
| `gtow_quirks_multiway_nash.md` | Multiplayer Nash anomalies | No. |
| `piosolver_technical_details.md` | Pio system + tree-size memory profile | No. |

**Gap:** No GTO Wizard, PioSolver, or Pluribus chart dumps in `blog/`. The
blog notes describe **how** these solvers work, not **what** they output for
specific spots.

### 2.4 Manual downloads

Location: `references/manual_downloads/`

**Empty.** This is the directory the user would populate if they manually
ship a GTOW / Pio / Snowie chart export. As of 2026-05-28 it contains nothing.

### 2.5 Packaged charts (heuristics; not authoritative)

Location: `poker_solver/charts/` (this is **product code**, not `references/`)

| File | Stack | Source | Authoritative? |
|---|---|---|---|
| `pushfold_v1.json` | 2–15 BB | **Our own solver** (`scripts/generate_pushfold_charts.py`, 4000 iters DCFR, final exploitability 0.0001 bb/100) | Internal self-generated; **NOT** an external reference |
| `chart_100bb_sb_open.json` | 100 BB | "Conservative HU SB-open default (~80%). Published heuristic — no authoritative source citation." (per file's `_source` field) | **NO** — explicit non-authoritative provenance |
| `chart_100bb_bb_defend.json` | 100 BB | "Approx MDF (1 − 1/odds) target. Treat as a starting point." | **NO** |
| `chart_100bb_btn_3bet.json` | 100 BB | "Linear-plus-blockers 3-bet range. No authoritative citation; conservative published heuristic." | **NO** |
| `chart_30bb_sb_jam.json` | 30 BB | "Short-stack HU SB-jam approximation. No authoritative citation; conservative published heuristic." | **NO** |

These files are **range strings** (which hands are *in* a range), not
strategy distributions (per-hand frequency mix over actions). They cannot
populate a Phase 7 fixture by themselves — they are too coarse.

### 2.6 Empirical comparison artifacts (most relevant to Phase 7)

Location: `docs/preflop_100bb_chart_validation_2026-05-28.md` (v1) and
`docs/preflop_100bb_chart_validation_v2_2026-05-28.md` (v2)

These two empirical-comparison docs are the **most useful artifacts** for
seeding a Phase 7 fixture today. They record per-cell solver-vs-chart
comparisons for 37 cells across 3 decision contexts (SB RFI, BB vs SB
2.5 BB open, SB vs BB 3-bet to 8.5 BB) at 100 BB HU.

**Caveats:**
1. The "published chart" the docs compare against was supplied by the user
   in the chart-validation work — **its provenance is not labeled in the
   doc**. The doc treats it as a user-supplied reference, not a fully
   citable third-party source. Phase 7's fixture must mark this honestly.
2. The comparison uses **dominant action labels** (`raise` / `call` /
   `fold`), not full per-action distributions. The fixture format below
   accommodates both.
3. The comparison was run against the **2.5 BB open + 5.5/5.95/8.5 BB 3-bet
   + 20.5/22.3/32.5 BB 4-bet** action menu — which is the **chart's**
   menu, not the Premium-A blueprint's standard menu. Apples-to-apples
   only at this specific action set.

These cells are the **only on-disk record of solver-vs-published-chart
comparison** at HU 100 BB preflop. They are seeded into the fixtures below
under the `user_supplied_chart_2026-05-28` source label.

---

## 3. Gap analysis — what we DO NOT have

| Reference would be useful for | Source we don't have | Possible acquisition path | Licensing? |
|---|---|---|---|
| 20 BB HU preflop chart (≈Pluribus jam region transition) | Pluribus paper or a published heuristic | Manual user transcription, then ship to `references/manual_downloads/` | Pluribus is paper-only — no chart dumps. Heuristic charts may be OK. |
| 30/40 BB HU preflop chart | GTOW / Snowie / Pio MTT charts | Manual user transcription | Commercial — see §5 licensing |
| 60 BB HU preflop chart | GTOW / Pio | Manual user transcription | Commercial |
| 80 BB HU preflop chart | GTOW / Pio | Manual user transcription | Commercial |
| 100 BB HU preflop chart (full 169 classes) | GTOW / Pio / Snowie at canonical 2.5x or 3x open | Manual user transcription — the `docs/preflop_100bb_chart_validation_*.md` partial data is the closest seed | Commercial |
| 150 BB HU preflop chart | GTOW deep-cap | Manual user transcription | Commercial |
| 200 BB HU preflop chart | GTOW deep-cap (acknowledged ambiguous per `feedback_nash_multiplicity_acceptance`) | Manual user transcription | Commercial; deep-cap is non-binding per Phase 7 spec |
| Ante variants (12.5% / 25% straddle) | If Premium-A Phase 1 Q1 ships ante matrix | Manual transcription | Commercial |
| PioSolver side-by-side dump | Pio is a paid product | User must run Pio side-by-side and dump output | Strict commercial license |
| Slumbot trained blueprint | Slumbot author's blueprint | Not publicly available; only the source is MIT-licensed (not the trained data) | Source MIT; trained data not released |

**Phase 7 should NOT block on populating these gaps.** Per the subplan
§2 Phase 7 acceptance criteria, the diff-test runs against
**whatever references are available**, treating gaps as documented and
unfilled — not as a release blocker. The chart-validation docs already
show that even one partial reference at 100 BB yields high-signal
divergence flags.

---

## 4. Fixture format and contents

Fixtures land at `tests/fixtures/blueprint_refs/`. Each file is a single
named reference, machine-readable JSON, with the schema:

```json
{
  "fixture_version": "1.0",
  "source": "<citation string>",
  "source_kind": "user_supplied | published_chart | solver_dump | heuristic",
  "shippable_in_repo": true|false,
  "license_notes": "<one-line summary>",
  "date_scraped": "YYYY-MM-DD",
  "date_added_to_repo": "YYYY-MM-DD",
  "config": {
    "stack_depth_bb": 100,
    "ante_bb": 0.0,
    "small_blind_bb": 0.5,
    "big_blind_bb": 1.0,
    "open_size_bb": 2.5,
    "three_bet_size_bb": 8.5,
    "four_bet_size_bb": 22.3,
    "action_menu_notes": "<one-line>"
  },
  "spots": {
    "<spot_id>": {
      "context": "SB_RFI | BB_vs_SB_RFI | SB_vs_BB_3bet | ...",
      "action_sequence": "<engine action history token, e.g. ||p|>",
      "actions": ["fold", "call", "raise_2.5bb", "all_in"],
      "expected_strategy": {
        "AA": [0.0, 0.0, 1.0, 0.0],
        "KK": [0.0, 0.0, 1.0, 0.0],
        "...": [...]
      },
      "expected_dominant_action": {
        "AA": "raise_2.5bb",
        "KK": "raise_2.5bb",
        "...": "..."
      },
      "notes": "<per-spot caveats — e.g., chart prohibits limp, sizing mismatch>"
    }
  },
  "nash_multiplicity_notes": [
    "<one-line caveats per memory rule feedback_nash_multiplicity_acceptance>"
  ]
}
```

**Why both `expected_strategy` (full distribution) and
`expected_dominant_action`:**
- Some references publish only "this hand is in this range" (dominant
  action only — e.g., the existing `chart_100bb_sb_open.json`).
- Other references publish full mixed-strategy distributions (GTOW Premium
  exports, when transcribed).
- A diff-test consumer that has only the dominant-action data can still
  run a "top-action agreement" gate (memory rule:
  `feedback_label_vs_semantics`). A consumer with full strategy data
  computes per-class L1.

### 4.1 Fixtures shipped in this PR

Two fixtures land in `tests/fixtures/blueprint_refs/`:

1. **`hu_100bb_user_supplied_chart_2026-05-28.json`** — 37 cells across
   3 contexts, sourced from the chart-validation docs. Marked as
   user-supplied (provenance not labeled in the validation doc) +
   shippable (no commercial-license data). Includes the explicit
   Nash-multiplicity caveats for A5s / A2s suited-ace bluff cells, JTs
   / 76s call-vs-fold cells, KQs over-aggress cells, and the SB-limp
   structural difference.

2. **`hu_pushfold_self_2_to_15bb_v1.json`** — self-generated reference
   from `poker_solver/charts/pushfold_v1.json`. Final exploitability
   0.0001 bb/100 across 14 stack depths × 169 classes × 2 positions.
   **This is internal self-reference, not external** — it serves as a
   *consistency check* (the new Premium-A blueprint should reproduce
   the pushfold result at 2–15 BB to within < 0.01 L1 because pushfold
   is a Nash-pure region). Labeled as `source_kind: solver_dump` so
   it does not get conflated with an external chart.

### 4.2 Fixtures explicitly NOT shipped

| Hypothetical fixture | Why not |
|---|---|
| GTO Wizard 100 BB HU chart | Not in `references/` today; user has not authorized commercial-data ingestion. Requires manual user transcription + licensing review per §5. |
| PioSolver 100 BB HU dump | Not in `references/`; requires user to run Pio and supply the export. |
| Pluribus blueprint dump | Not in `references/`; paper is architecture-only, blueprint binary not publicly released. |
| Snowie HU 100 BB chart | Not in `references/`; commercial. |
| 30/40/60/80/150/200 BB charts | Not in `references/` at any source. Phase 1.5 generates these depths; comparison against externals is gated on user-supplied transcription. |

---

## 5. Licensing / shippability flags

| Source kind | Shippable in this repo? | Notes |
|---|---|---|
| User-supplied chart with unclear provenance | **Conditional yes** | Marked `source_kind: user_supplied`. The user controls whether to retain or remove. Phase 7's diff-test treats this as one-of-many sanity references, not a gate. |
| Our own self-generated pushfold solve | **Yes** | Internal artifact; MIT-licensed with the rest of the repo. |
| GTO Wizard scrape | **NO** without explicit licensing review | GTOW is a paid SaaS with explicit terms-of-service. Even a "fair-use comparison" snapshot raises legal exposure. Per task constraints: "For commercial-solver scrapes (GTO Wizard etc): document that those references are NOT shippable without licensing review." |
| PioSolver dump | **NO** without explicit licensing review | Pio output is the user's per-license-key output; redistribution is restricted by Pio's EULA. Even if the user dumps locally, putting it in this repo may violate Pio's redistribution clause. |
| Snowie / Monker dump | **NO** without explicit licensing review | Same as Pio. |
| Brown / Pluribus paper figures | **Yes for citation, NO for raw transcription** | Paper figures can be cited; transcribing them into machine-readable fixtures is arguably a derivative work. Cite the paper; do not redistribute figure data as a fixture. |
| Slumbot trained blueprint | **NOT AVAILABLE** | The author has not released the trained binary. The source code is MIT-licensed but does not include the trained blueprint. |

**Recommended policy for Phase 7:**
1. Ship only the two fixtures above in this PR (user-supplied + self-pushfold).
2. If the user later supplies a GTOW / Pio chart, do **NOT** auto-add to
   `references/manual_downloads/`. Per task constraint: *"The user
   controls what gets added to `references/`."*
3. The diff-test code (`tests/test_blueprint_diff_vs_external.py`, not
   in this PR — that's Phase 7's main deliverable) loads fixtures
   opportunistically: if a fixture is absent (e.g., the user has not
   transcribed GTOW), the test SKIPs that comparison with an explicit
   message rather than hard-failing. Per memory rule
   [`feedback_silent_skip_hazard`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_silent_skip_hazard.md):
   the skip message must be load-bearing visible, not silent.

---

## 6. Recommended Phase 7 workflow (consumer-facing)

When Phase 7 ships its diff-test (`tests/test_blueprint_diff_vs_external.py`,
not in this PR):

1. Load every fixture in `tests/fixtures/blueprint_refs/*.json`.
2. For each fixture, match its `config.stack_depth_bb` against an available
   Premium-A blueprint shard. If the depth is not in the Premium-A depth
   set, skip with an explicit message.
3. For each spot in the fixture, find the matching `action_sequence` in
   the blueprint. If absent (e.g., chart used a 10 BB 3-bet but blueprint
   only has 8.5 / 11 BB), record as "menu mismatch — no apples-to-apples
   row" and continue.
4. Compute per-class L1 = `sum(|blueprint[hand][a] - reference[hand][a]| for a in actions)`.
5. Report median L1, p95 L1, top-10 outliers with cell + suspected cause.
6. Apply the L1 ≤ 0.05 tolerance (user-decided, subplan §8 Q3 option b):
   - **PASS** if median per-class L1 ≤ 0.05 at 100 BB.
   - **PARTIAL** if median per-class L1 ≤ 0.10 at 100 BB but > 0.05.
   - **FAIL** if median per-class L1 > 0.10 at 100 BB.
   - Deep-cap (200 BB) is informational only per memory rule
     [`feedback_nash_multiplicity_acceptance`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_nash_multiplicity_acceptance.md).

The seed fixture
`hu_100bb_user_supplied_chart_2026-05-28.json` is already at this 100 BB
depth — Phase 7's first PASS/PARTIAL/FAIL report can be generated against
it the day Phase 1.5 completes.

---

## 7. Memory-rule applicability checklist

- [`feedback_references`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_references.md)
  — checked `references/` first; documented what is there and what is not.
- [`feedback_research_first_failure_protocol`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_research_first_failure_protocol.md)
  — researched papers, OSS solvers, blogs, products before declaring gaps.
- [`feedback_external_solver_sanity_check`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_external_solver_sanity_check.md)
  — framed all external references as sanity checks, not ground truth.
- [`feedback_nash_multiplicity_acceptance`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_nash_multiplicity_acceptance.md)
  — flagged deep-cap (200 BB) divergence as informational only; per-cell
  strict gate is non-falsifiable.
- [`feedback_silent_skip_hazard`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_silent_skip_hazard.md)
  — Phase 7 SKIPs must be load-bearing visible, not silent.
- [`feedback_public_repo_hygiene`](file:///Users/ashen/.claude/projects/-Users-ashen-Desktop-poker-solver/memory/feedback_public_repo_hygiene.md)
  — explicit shippability flags per source kind; commercial-solver scrapes
  flagged as NOT shippable without licensing review.

---

## 8. Open questions surfaced

1. **Provenance of the user-supplied chart.** The chart-validation docs
   (`docs/preflop_100bb_chart_validation_*.md`) do not label the source
   of the "published chart" they compare against. If the user can supply
   a citation (e.g., GTOW Premium snapshot from date X, JL chart from
   page Y of a published book), the fixture should be updated with the
   citation and the `source_kind` re-evaluated. If the chart is from a
   commercial product, the fixture may need to be removed from the
   public repo per §5 licensing.

2. **Whether to attempt GTOW transcription.** GTOW publicly displays its
   "free tier" charts in-app. Manual transcription (looking at the chart
   on screen and typing numbers into a JSON file) is **arguably** fair
   use as long as the volume is small. The task constraint says: *"DO
   NOT fetch URLs without user authorization."* The user has not
   authorized GTOW scraping; the user has not authorized GTOW manual
   transcription either. **Recommendation:** ask the user explicitly
   before transcribing.

3. **Whether to commit `assets/preflop_equity_169x169.npz` solve output
   as a "self-reference" fixture.** This binary asset already ships in
   the repo for production solver use. Generating a `Phase 1.5 dry-run
   on 100 BB at 1000 iters` and shipping that result as a self-reference
   fixture would let Phase 7 detect regressions in the *engine itself*
   (not against externals) — distinct from the diff-test goal but
   useful for catching engine drift. **Out of scope for Phase 7 per the
   subplan**, but flagged here.

---

## 9. References

- `docs/premium_a_blueprint_subplan.md` — parent subplan
- `docs/preflop_100bb_chart_validation_2026-05-28.md` — v1 comparison (37 cells)
- `docs/preflop_100bb_chart_validation_v2_2026-05-28.md` — v2 comparison (limp-collapsed)
- `references/README.md` — license audit + topic index for `references/`
- `tests/fixtures/blueprint_refs/*.json` — fixtures seeded by this PR
- Memory rules listed in §7 above
