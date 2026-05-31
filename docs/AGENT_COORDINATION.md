# Agent Coordination / Handoff

**Date:** 2026-05-31
**Audience:** any agent or future session picking up work on this repo —
especially the **engine track** (flop/turn/river solver, `poker_solver/chained.py`)
and the **GUI track** (NiceGUI app under `ui/`).

This doc lets you act on the open work **cold**: what's shipped, who owns
what, the concrete asks the GUI track needs from the engine track, the git
coordination rules, and the open issues. Read this first, then the linked
plans.

---

## 1. Current shipped state

`origin/main` and `backup/main` are both at **`42a1ce0`** = the v1.11
release line:

- **v1.11 fast engine** — rayon opt-in, suit-isomorphism, inclusion-exclusion
  terminal eval, preflop restricted-EV, and the bet-size menu (per-street
  menus + lean raise multipliers + flop-no-donk).
- **GUI-audit UI integration** — the full GUI test+fix campaign (all **15**
  original audit issues) is **DONE and browser-verified**. The audit UI was
  reconciled onto the fast engine in one build (the integration merge
  `a9e92ea` is an ancestor of `42a1ce0`; `b551b13` reconcile + `f11f19f`
  test-contract alignment + the merge). RvR flops are tractable on the fast
  engine; the fast binding carries the UI progress/cancel hooks.
- **UI polish + README refresh + version bump** to `1.11.0` (the `42a1ce0`
  tip commit).

Detailed campaign record: `docs/gui_audit/findings.md`. Forward plan +
checklist: `docs/gui_audit/TODO.md`.

---

## 2. Track ownership

Two tracks work in parallel. Keep changes on the side you own; coordinate at
the shared seams below.

### GUI track
- **Owns:** everything under `ui/` — the NiceGUI views, the chain-solve
  walkthrough (`ui/views/chained_tab.py`), the 13×13 preflop charts/matrix,
  the range editor, card graphics (`ui/views/_cards.py`), auto-range
  (`ui/views/_auto_range.py`), the run panel / tiers (`ui/views/run_panel.py`),
  and the UI state model (`ui/state.py`).
- **Plans:** `docs/gui_audit/` (TODO, findings, integration_plan,
  chain_solve_b_plan).

### Engine track
- **Owns:** `crates/cfr_core/` (Rust DCFR core), and the Python solver tier:
  `poker_solver/chained.py`, `poker_solver/blueprint_subgame.py`,
  `poker_solver/range_aggregator.py` (the `solve_range_vs_range_nash` /
  `RangeVsRangeNashResult` engine), and the flop/turn/river solve paths.
- **Plans:** `docs/v1_*`, `docs/rust_optimization_ledger.md`,
  `docs/flop_subgame_*`, `docs/vector_rvr_*`.

### Shared seams (coordinate before changing)
- `poker_solver/chained.py` — both tracks touch it (GUI consumes
  `ChainedSolveResult`; engine owns the solve). **This is the seam for the
  Tier B ask below.**
- The **flop solve path** — `ChainedSolveResult.solve_postflop` →
  `solve_range_vs_range_nash` (`range_aggregator.py`).
- `Spot.to_hunl_config()` and `Spot.to_rvr_call_args()` (`ui/state.py:593` /
  `:709`) — the GUI→engine config boundary.
- `_spot_from_config()` (`ui/views/spot_input.py:1628`) — see the known SPR
  gap in §5.

---

## 3. Coordination ASKS — what the GUI needs from the engine track

### 3a. Chain-solve Tier B (turn/river walkthrough) — PRIMARY ASK

The chain-solve hole-card walkthrough today goes **preflop → flop only**.
Turn/river render a static "pending fast engine" placeholder
(`chained_tab.py` `_render_pending_step`, ~line 1326) with **no compute**.
Tier B extends it to **preflop → flop → turn → river**.

**What the engine already supports (verified):**
- `solve_range_vs_range_nash` (`range_aggregator.py`) already accepts
  `starting_street >= FLOP` and boards of length 4 (turn) or 5 (river); it
  rejects only `PREFLOP`. The test suite drives it directly with
  `starting_street=Street.TURN` / `Street.RIVER`. **The primitive for solving
  a standalone turn/river subgame exists.**

**What is missing (the ask):**
- **Extend `ChainedSolveResult` with `solve_turn()` / `solve_river()`** that
  return the existing `RangeVsRangeNashResult` (same shape as
  `solve_postflop`). Today `solve_postflop` is **flop-only by assertion** —
  it raises `ValueError` for `len(board) != 3`
  ("Phase A only supports flop subgames", `chained.py:335`).
- **A NET-NEW postflop continuation-range derivation.** Today's
  `_derive_continuation_ranges` (`chained.py:842`) is **preflop→flop only**:
  it propagates per-pair reach through the preflop tree and returns `None`
  for fold/all-in terminals. There is **no** flop→turn or turn→river analogue
  that takes a postflop solve + a chosen postflop action and produces the
  next street's continuation ranges + entry board. That derivation is the
  core net-new engine work.
- **Thread pot / contributions engine-side.** Carry the running pot and
  per-player contributions through the chain inside the engine — do **not**
  route them via `_spot_from_config` (which drops postflop SPR/pot, see §5).

**Full detail + the step-by-step plan:**
`docs/gui_audit/chain_solve_tier_b_plan.md` (currently on the unpushed branch
`docs/chain-solve-tier-b-plan` @ `61b48d1`; to be consolidated — see §6).
The shipped Tier A boundary is in `docs/gui_audit/chain_solve_b_plan.md`.

Note: all chain-solve strategy is **class-level**, not combo-level — Tier B
inherits that.

### 3b. Flop interactivity (engine perf, in-flight)

The GUI's flop-RvR interactivity **and** Tier B both ride on the engine
track's **in-flight flop-solver performance work**. A full 100BB flop solve
is currently minutes-scale and **board-chance-tree-bound** (the dominant cost
is the flop chance node's board fan-out, not `top_k`). See
`docs/flop_subgame_perf_measurement_2026-05-28.md` and
`docs/v1_11_postflop_deeper_optimization_research.md`.

Once the perf work lands, the GUI measures **per-street latency** to set the
usable interactive envelope (which streets/depths are tolerable inside the
GUI's solve tiers).

### 3c. Validation gauntlet

A poker-intuition correctness gauntlet (MDF / polarization / set-on-board /
fold-equity sanity on real merged-engine GUI outputs) is the next correctness
axis beyond "it renders". It **needs the engine + real solves**. Plan:
`docs/gui_audit/validation_gauntlet_plan.md` (currently on the unpushed
branch `docs/validation-gauntlet-plan`; see §6).

### 3d. Per-combo EV exposure — the GUI's EV column is structurally empty

The combo inspector shows `EV +0 mBB` for **every** combo because `ev_mbb` is
**hardcoded `0.0`** (`ui/views/range_matrix.py` `_build_combo_rows`, ~L1062:
"Real EV plugs in when ... per-combo EV wired"). It has **never** displayed a
real value — a likely root of the "EVs look degenerate / results just say
fold/call" report (the fold/call *strategy* is real, from `per_class_strategy`;
only the **EV** is stubbed). It **cannot** be fixed GUI-side: no result object
the inspector reaches carries per-combo/class EV — `RangeVsRangeNashResult`
exposes only a scalar `exploitability`, the concrete `SolveResult` only a scalar
`game_value`. The RvR Rust path computes per-hand `node_values` each CFR
iteration (`dcfr_vector.rs`) but discards them; `exploit::compute_restricted_game_value`
(`exploit.rs`) computes the exact per-combo `flat_expected_value(...)[0]` the
inspector wants, then **sums it to a scalar** and returns one `f64`.

**Ask (engine track):** (1) Rust — return the per-combo `value[0]` vector
instead of (or alongside) the scalar; the math already exists in `exploit.rs`,
only the aggregation changes; key it by hole-string like `average_strategy`.
(2) Python — add `per_history_ev` (and/or combo-averaged `per_class_ev`) to
`RangeVsRangeNashResult`, keyed by the same infoset key as `per_history_strategy`.
**Units: chips/hand in the Brown pot-share base (BB units)** — the GUI converts
to mBB (×1000) and confirms the displayed-seat sign. **Caveat:** these are the
dominated-hand EVs that pin at 0 / >pot under-convergence (§5), so they must be
run at convergence-grade iters to be trustworthy. Pairs with §3b (perf) + §3c
(validation).

---

## 4. GIT COORDINATION (important)

- **`origin/main` and `backup/main` are both at `42a1ce0`** (the shipped
  v1.11 line with UI + version + docs).
- **The engine track's LOCAL `main` worktree was last seen at `aa9022d`,
  which is BEHIND `origin/main`.** `aa9022d` is an ancestor of `42a1ce0` (it
  is the GUI-audit sanitize commit; origin added the version bump + doc prune
  on top).

**Rules:**
1. **The engine track must `git pull` (fast-forward) `origin/main` before
   pushing.** `aa9022d → 42a1ce0` is a clean fast-forward.
2. **NEVER force-push `main`.** A force-push from `aa9022d` would clobber the
   shipped UI integration + version bump + docs that only live at `42a1ce0`.
3. **Two sessions sharing one `main` worktree is fragile.** Prefer per-feature
   branches (one branch per change, verified green, then merged) over working
   directly on the shared `main` checkout. This is both a robustness and a
   concurrency rule.

---

## 5. Open items / known issues

- **AA limps 36% at the SB root** in the preflop blueprint. The UI **label is
  correct** — it renders "L" (limp), not a mislabel. Whether **36% is
  GTO-correct** for that spot is a **blueprint-correctness** question for the
  **engine track** to verify against the blueprint projection. (Tracked in
  `docs/gui_audit/TODO.md` as the "AA C36 oddity".)
- **`_spot_from_config` drops postflop SPR / pot.**
  `_spot_from_config` (`spot_input.py:1628`) and `Spot.to_hunl_config()`
  (`state.py:593`) do not carry a hand-built postflop subgame's pot +
  contributions, so a hand-built (not fixture-loaded) postflop spot
  misrepresents SPR. This is a **Tier-A/B threading risk**: Tier B must thread
  pot/contributions engine-side (see §3a), not through this path.
- **3 benign Phase-5 TODOs in `ui/`** — non-blocking cleanups left from the
  Premium-A phase-5 routing work.
- **Postflop EV-convergence (latent):** low exploitability at the production
  solve tiers (Draft 200 / Standard 500 / Tight 1000 default / Library 2000)
  does **not** guarantee non-degenerate per-hand EVs — dominated hands can be
  pinned at 0 / >pot at low iters. Validate combo-inspector EVs after the
  engine merge. See `docs/gui_audit/TODO.md` follow-ups.

---

## 6. Branch inventory (unpushed work, all off the shipped line)

All of the following branch off the shipped `42a1ce0` line and are **not yet
pushed**. They will be **consolidated and pushed together**:

| Branch | Tip | Contents |
|---|---|---|
| `docs/chain-solve-tier-b-plan` | `61b48d1` | Adds `docs/gui_audit/chain_solve_tier_b_plan.md` (the §3a plan). |
| `docs/validation-gauntlet-plan` | (at `42a1ce0` base) | The §3c validation gauntlet plan. |
| `docs/agent-coordination` | (this branch) | This handoff doc + README/TODO pointers. |
| folded-in UI branches | — | The card-graphics / UI-polish / auto-range branches already merged into the shipped line; listed here for provenance. |

When consolidating, fast-forward `origin/main` first (§4), then merge these
docs branches on top — they are docs-only and conflict-free with engine work.
