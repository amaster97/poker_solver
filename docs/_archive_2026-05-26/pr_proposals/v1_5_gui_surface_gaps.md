# v1.5 — GUI Surface Gaps for v1.3.0+ Engine Features (PR 24 candidate)

**Status:** Spec only (read-only investigation). No code modifications.
**Author:** orchestrator-spawned gap-analysis agent
**Date:** 2026-05-23
**Scope:** Inventory the GUI shipped through PR 10b and identify all engine features (v1.3.0 through v1.4.1) that have no UI surface today; propose per-gap closure plans; recommend 24a/24b sub-PR split; map gaps to the 18 persona workflows.

---

## 1. Current UI inventory

### 1.1 File tree

`/Users/ashen/Desktop/poker_solver/ui/`:

| File | Lines | One-line description |
|------|-------|----------------------|
| `ui/__init__.py` | small | Package marker; re-exports `launch()` for `poker-solver ui` CLI entry. |
| `ui/app.py:60-205` | 403 | `build_page()` composes header + 2-pane layout (matrix center + sidebar expansion panels) and registers the 500 ms polling timer. |
| `ui/state.py:332-487` (Spot), `ui/state.py:1117-1357` (AppState) | 1358 | `AppState`, `Spot`, `RangeWithFreqs`, `SolveSession`, `SolveRunner`; the only file that imports `poker_solver.solver` / `mock_solver`. |
| `ui/mock_solver.py`, `ui/mock_solver_fixtures.py` | 21,733 + 21,430 | PR 10a hand-crafted fixtures + dispatch; PR 10b adds the real-solver path under the same import surface. |
| `ui/views/__init__.py` | 9 | Re-exports view modules. |
| `ui/views/onboarding.py` | 140 | 3-step onboarding modal shown when `state.prefs.onboarding_completed` is False. |
| `ui/views/spot_input.py:46-77` | 583 | Spot input panel: board picker (4×13), per-player range matrix INPUT (white→blue) + string-input toggle, stack/blinds/ante inputs, preset dropdown. |
| `ui/views/run_panel.py:60-260` | 574 | Run panel: bet-size checkboxes, raise caps, iterations input, **target-exploitability toggle** (single number, not tiered), backend toggle (Python/Rust), Solve/Pause/Stop, live `ui.echart` exploitability curve, progress readouts. |
| `ui/views/range_matrix.py:1-961` | 961 | 13×13 strategy DISPLAY (RYG palette per Pio convention) + combo inspector strip. Pure render — no input affordances. |
| `ui/views/tree_browser.py` | 684 | Decision-tree browser (collapsible action tree under the matrix). |
| `ui/views/library_browser.py:114-282` | 325 | Library list/load/delete dialog wired to `poker_solver.library.Library`. |

### 1.2 Main entry confirmed

`ui/app.py:60-205` is the page builder. The two-pane layout is locked per `pr10a_spec.md` §0.1 Q1: matrix region center, 3-section sidebar right (Spot Input open, Run Panel + Decision Tree collapsed). No top-level menu surfaces a "range-vs-range" mode or a "node-lock editor."

`ui/views/spot_input.py:202-209` exposes player tabs `P0 (SB / BTN)` and `P1 (BB)` — both ranges are editable; no hero / villain semantics surfaced; no `hero_player` selector.

`ui/views/run_panel.py:139-170` has a single target-exploitability input (one number, mBB/pot), **not** a tiered slider with Draft/Standard/Tight/Library labels.

---

## 2. Engine-feature × UI-surface matrix

| Engine feature | Shipped | UI surface today | Gap |
|---|---|---|---|
| HU postflop solve (concrete-vs-concrete) | v0.5.0 (Rust), v1.0.0 GA | Solve button (`run_panel.py:184-189`), routes through `Spot.to_hunl_config()` at `state.py:381-453` which picks point-pair hole cards (`state.py:455-487`). | None. |
| Range editor (per-player 13×13 input) | n/a (built into PR 10a) | `spot_input.py:248-263` — 13×13 matrix with cycle 1.0 → 0.5 → 0.25 → 0.0; string-input alternative at `spot_input.py:266-291`. | **Partial**: only 4 discrete frequency steps; no per-hand frequency input; no preset library (UTG open, BB defend, etc.); no suit-aware sub-selection. |
| Range-vs-range solve (`solve_range_vs_range`) | v1.3.0 (Plan C Stage C1) — `poker_solver/range_aggregator.py:208` | **NONE.** No "RvR mode" toggle; no aggregator output panel; the matrix display renders point-pair Nash only. | **CRITICAL gap.** |
| `hero_player` parameter | v1.3.1 — `range_aggregator.py:217` (defaults to 0) | **NONE.** Range editor uses P0/P1 labels (`spot_input.py:202-209`); UI has no concept of which seat is "hero" for output framing. | **High gap.** Required for MDF/defender workflows. |
| Rust exploitability walk (Option A) | v1.3.2 | **Indirect** — backend toggle at `run_panel.py:174-178` exposes Python/Rust; the chart displays whatever `runner.expl_history` contains (`run_panel.py:298-302`). | **Labeling gap.** UI does not distinguish "true Nash exploitability (Rust BR)" vs "blueprint aggregator approximation"; chart legend says only "Exploitability (mBB/pot)" at `run_panel.py:427`. |
| Node-locking (`locked_strategies`) | v1.4.0 — `solver.py:36` | **NONE.** No locked-strategy editor; no per-infoset distribution input; no "lock action" affordance in the tree browser. | **CRITICAL gap.** |
| Asymmetric `initial_contributions` (facing-bet input) | v1.4.1 (in flight, design at `docs/pr_proposals/v1_4_asymmetric_contributions.md`) | **NONE.** `Spot.to_hunl_config()` at `state.py:436-437` hardcodes `initial_contributions = (bb_blind_cents, bb_blind_cents)` symmetrically for postflop and ignores any "villain bet X" input. | **CRITICAL gap.** Blocks 3 of 4 facing-bet workflows (W1.2 / W2.3 / W3.4). |
| Exploitability slider (4 tiers Draft/Standard/Tight/Library) | v0.6.0 spec / `PLAN.md` §1 | **Partial** — single numeric input at `run_panel.py:156-162` ("Target expl (mBB/pot)", default 0.5). No tier presets, no labels. | **High gap.** PLAN.md §1 contract not met. |
| Numeric tier defaults (post-PR-10b measurement pass) | TBD per `PLAN.md` §1 + §11 B4 | **No measurement pass found.** Searched `docs/` for any `measurement_pass`, `tier_defaults`, or post-PR-10b convergence study — none exists (only `docs/comprehensive_review_2026-05-23.md` and `docs/pr8_prep/pr_report.md` mention "exploitability tier" in passing, neither contains measurements). | **Blocker for slider PR.** See §5. |

---

## 3. Gap closure plan — per feature

### 3.1 Range editor enhancement (low-priority polish; existing 4-step works)

**Current:** `spot_input.py:330-362` `_cycle_cell_frequency` rotates 1.0 → 0.5 → 0.25 → 0.0 → 1.0 on cell click. White-to-blue color encodes aggregate frequency (`spot_input.py:307-327`). String-input alternative at `spot_input.py:266-291` accepts Pio-style range strings.

**Proposed enhancements:**

| Add | Where | Widget |
|-----|-------|--------|
| Per-hand frequency slider (0-100%) | New right-click handler on `spot_input.py:248` cell | `ui.dialog` containing `ui.slider(0, 100)` + `ui.number` + 1326-combo grid (4×4 suit matrix per hand class for suit-aware setting) |
| Range presets dropdown | New `_render_preset_dropdown` in `spot_input.py` | `ui.select` populated from `poker_solver/charts/` JSON files; selection writes `RangeWithFreqs.from_string(preset)` to `state.current_spot.ranges[player]` |
| Hero/villain swap button | `spot_input.py:202` (player tabs) | `ui.button("Swap hero ↔ villain")` calls a helper that swaps `state.current_spot.ranges[0]` and `[1]`; also writes a new `state.current_spot.hero_player: int` field (see §3.4) |
| Preset library (UTG open, BB defend etc.) | `poker_solver/charts/` (engine side) + dropdown above | JSON files: `chart_100bb_sb_open.json`, `chart_100bb_bb_defend.json`, etc. Use `poker_solver/charts/` (already present per repo root listing). |

**Engine binding:** `RangeWithFreqs` (`ui/state.py:252-330`) already supports per-combo frequency mutation via `set_frequency(combo, freq)`; only the UI affordance is missing. Presets call `RangeWithFreqs.from_string(...)` with the standard Pio syntax.

**Test plan:** Use NiceGUI's `User` test fixture (already in `tests/test_ui_smoke.py`). Smokes:
- Click cell, open frequency dialog, set 0.42, assert `state.current_spot.ranges[player].frequency_of(combo) == 0.42`.
- Load preset, assert range counter matches the expected combo count (e.g. SB open ~80%).
- Hero swap toggles `state.current_spot.hero_player`.

### 3.2 Range-vs-range solve (CRITICAL)

**Current:** `Spot.to_hunl_config()` at `state.py:381-453` picks point-pair hole cards (`state.py:455-487`). The solve runs a concrete-vs-concrete subgame; the matrix display renders only that one Nash solution.

**Proposed:**

**Files to modify:**
- `ui/views/run_panel.py` — add an "RvR mode" toggle near `run_panel.py:174` (backend toggle).
- `ui/views/spot_input.py` — when RvR mode is on, suppress the "point-pair fallback" warning at `state.py:474-487` and route through `solve_range_vs_range` instead of `solve`.
- `ui/state.py` — add `Spot.rvr_mode: bool = False` field; add a new `Spot.to_rvr_call_args() -> tuple[HUNLConfig, list[HandClass], list[HandClass]]` method that extracts hand-class lists from `self.ranges[0]` and `self.ranges[1]`.
- `ui/state.py:_on_solve` (and the worker thread) — branch on `state.current_spot.rvr_mode` to call `poker_solver.solve_range_vs_range(config, hero_range, villain_range, hero_player=spot.hero_player, ...)` vs `solve(game, ...)`.

**UI widget choice:**
- `ui.toggle(["Concrete", "Range-vs-range"])` next to backend toggle.
- `ui.tooltip` on RvR option: "Slower aggregator pass; honest framing — see Plan C Stage C1."
- When RvR active, the `range_matrix.py` DISPLAY pane re-renders against `RangeVsRangeResult.per_class_frequencies` (output of `solve_range_vs_range`); add a tab strip "P0 (aggressor) | P1 (defender)" in the matrix region.

**Engine binding:**
- Call site: `poker_solver/range_aggregator.py:208` `solve_range_vs_range(config_template, hero_range, villain_range, iterations=200, *, backend="rust", hero_player=spot.hero_player, on_progress=callback)`.
- Output: `RangeVsRangeResult.per_class_frequencies: dict[HandClass, list[float]]` feeds the matrix display.

**Test plan:**
- Smoke: toggle RvR on, click Solve, assert the worker calls `solve_range_vs_range` (not `solve`). Mock the aggregator.
- Acceptance: solve a small RvR spot (≤30 s wall-clock per `persona_acceptance_spec.md` §94 "range-vs-range medium <2 min" budget), assert the matrix renders a 169-cell strategy.
- Persona retest W2.3 (Sarah KK on Q-high), W3.4 (Daniel MDF), W3.5 (polarization).

### 3.3 `hero_player` selector (v1.3.1)

**Current:** `spot_input.py:202-209` uses P0/P1 labels with no "hero" semantics. The `range_aggregator.py:217` parameter defaults to 0; UI cannot set it to 1.

**Proposed:**

**File to modify:** `ui/views/spot_input.py` between line 209 (tab strip) and 210 (tab panels). Add a `ui.toggle(["P0", "P1"], value="P0")` labeled "Hero seat:" with a tooltip "Affects which side is shown as Hero in the matrix display and which `hero_player` is passed to the range aggregator (matters for MDF/defender queries)."

**State field:** Add `Spot.hero_player: int = 0` (mirrors `range_aggregator.py:217` default).

**Engine binding:** `solve_range_vs_range(..., hero_player=spot.hero_player, ...)`. For concrete-vs-concrete solves the parameter does not exist on `solve()`, but the matrix display in `range_matrix.py` should swap rows P0/P1 based on `spot.hero_player` so the user sees Hero's strategy on the front tab.

**Test plan:** Set hero_player=1, run an RvR solve, assert `RangeVsRangeResult.position == "defender"` (per `range_aggregator.py:183-186`).

### 3.4 UI label for "true Nash" vs "blueprint" exploitability (v1.3.2 Option A)

**Current:** Chart title at `run_panel.py:427` is hardcoded `"Exploitability (mBB/pot)"`. The Rust exploitability walk landed in v1.3.2 so the chart values are now true Nash for concrete-vs-concrete; for RvR mode (§3.2) the values are aggregator approximations.

**Proposed:**

**File to modify:** `ui/views/run_panel.py:_chart_options` (line 417-451). Pass a `quality_label: str` argument; render as the subtitle (`echarts` `subtext` field).

**Quality label mapping:**
- Concrete-vs-concrete + Rust backend: `"true Nash (Rust best-response walk, v1.3.2)"`
- Concrete-vs-concrete + Python backend: `"true Nash (Python best-response walk, slow)"`
- RvR mode (any backend): `"blueprint approximation (Pluribus-style aggregator, v1.3.0; not Nash)"`

**Engine binding:** Read `state.current_spot.rvr_mode` + `state.current_solve.backend` at chart-redraw time (`run_panel.py:316-317`). No engine call change.

**Test plan:** Smoke — toggle RvR on, assert chart subtext contains "blueprint approximation."

### 3.5 Node-locking editor (CRITICAL, v1.4.0)

**Current:** No UI surface. `poker_solver/solver.py:36` accepts `locked_strategies: Mapping[str, Sequence[float]] | None = None`.

**Proposed:**

**Files to add/modify:**
- New file `ui/views/node_lock_editor.py` — a `ui.dialog`-hosted editor.
- `ui/views/tree_browser.py` — add a "Lock this node" right-click menu item on each tree node row.
- `ui/state.py` — add `Spot.locked_strategies: dict[str, list[float]] = field(default_factory=dict)` field; persist in state.json.
- `ui/state.py:SolveRunner.start(...)` — pass `locked_strategies=spot.locked_strategies` to `solve(...)` (`state.py:567-606` already has the kwarg threading scaffold; add the dict).

**UI widget choice:**
- Right-click on tree node → `ui.dialog` opens.
- Dialog contents: label "Lock infoset `{key}` to fixed strategy"; one `ui.slider(0, 100, value=initial)` per legal action (read from current avg strategy); a "must sum to 100%" validator; Save / Cancel buttons.
- Locked nodes get a yellow padlock icon in the tree (`tree_browser.py` cell render). Hover shows the locked distribution.
- A "Locked strategies" expansion in the run panel lists all locks with per-lock unlock buttons.

**Engine binding:**
- Pass `locked_strategies=spot.locked_strategies` to `solve(...)` per `solver.py:36`.
- v1.4.0 push/fold guard (`solver.py:74-86`) raises ValueError if locks are set on a ≤15 BB preflop spot; UI must surface this as `ui.notify(..., type='negative')` with a "Use tree-builder mode" remediation (which `solver.py:75` exposes via `force_tree_solve`).

**Test plan:**
- Smoke: open lock editor, set river bluff freq to 0, run solve, assert `result.average_strategy[locked_key] == [0.0, ...]` bit-identically per `solver.py:60-61` semantics.
- Persona retest W3.1 (Daniel "villain never bluffs rivers"), W3.3 (merged-strategy response).
- Edge case: lock + ≤15 BB preflop → assert UI shows the ValueError as a notify with remediation button.

### 3.6 Asymmetric `initial_contributions` (facing-bet input) (CRITICAL, v1.4.1)

**Current:** `Spot.to_hunl_config()` at `state.py:436-437` hardcodes `initial_contributions = (bb_blind_cents, bb_blind_cents)` symmetrically. No "villain bet X chips" input.

**Proposed:**

**Files to modify:**
- `ui/state.py:Spot` — add `pot_so_far_bb: float = 0.0` and `villain_bet_bb: float = 0.0` fields.
- `ui/state.py:Spot.to_hunl_config()` (lines 425-437) — when `villain_bet_bb > 0`, set `initial_contributions = (pot_half + villain_bet, pot_half)` and `initial_pot = pot_so_far + villain_bet`, so the engine sees `to_call = villain_bet_bb * 100`.
- `ui/views/spot_input.py:_render_blinds_section` (line 438-483) — add a new "Facing bet" expansion below the blinds:
  - `ui.number("Pot so far (BB)")`
  - `ui.number("Villain's bet (BB)")`
  - `ui.toggle(["P0 faces bet", "P1 faces bet"])` (matches `hero_player`/seat logic; engine assumes the lower-contribution side acts first per `v1_4_asymmetric_contributions.md` §2 Fix A).
  - Validation: `villain_bet_bb` must be ≤ effective stack of the bettor.

**UI widget choice:**
- `ui.expansion("Facing bet (postflop subgame)", icon="trending_up", value=False)`; collapsed by default since the common case is "no facing bet."

**Engine binding:**
- Computed `initial_contributions` passes through `HUNLConfig.initial_contributions` per `hunl.py:105-148`. v1.4.1 (in flight) will honor the asymmetric value per `v1_4_asymmetric_contributions.md` Fix A.

**Test plan:**
- Set villain_bet_bb=0.5 (half-pot), assert `HUNLConfig.initial_contributions == (150, 100)` (cents) for a 1 BB pot baseline.
- Persona retest W1.2 (Marcus JJ vs pot bet), W2.3 (Sarah KK vs c-bet), W3.4 (Daniel MDF).
- Edge case: villain_bet_bb > stack → ValueError surfaced as `ui.notify`.

### 3.7 Exploitability slider with 4 tiers (Draft/Standard/Tight/Library)

**Current:** Single `ui.number(label="Target expl (mBB/pot)", value=0.5, ...)` at `run_panel.py:156-162`. No tiers; no labels.

**Proposed:**

**File to modify:** `ui/views/run_panel.py:139-170` (iterations + target-expl block).

**UI widget choice:**
- Replace the single number with `ui.toggle(["Draft", "Standard", "Tight", "Library"], value="Standard")`.
- Below the toggle, show a read-only `ui.label(f"Target: {tier_target_mBB} mBB/pot")` that reflects the selected tier.
- Keep `ui.number(label="Custom...")` as an opt-in override (advanced users; collapsed under an `ui.expansion`).

**Tier defaults:** **MEASUREMENT REQUIRED** — see §5.

**Engine binding:** Same as today — pass `target_exploitability=tier_target_mBB / 1000.0` to `SolveRunner.start` (`state.py:567-606`).

**Test plan:**
- Click "Draft", assert internal `state.current_solve.target_exploitability` matches the Draft tier.
- Snapshot a 4-element matrix of (tier × persona) wall-clock budgets; assert "Standard" lands within the Marcus 1-5 min Pio-class budget (per `persona_time_budgets.md`).

---

## 4. Range editor specifics (largest single design item if §3.1 is upgraded)

**Reference points from `references/products/`:**

- GTO Wizard uses a 13×13 grid with hand-class labels in the upper-left of each cell; per-hand suit-aware sub-grid opens on click for fine-grain editing; a left-side action-strip lists presets ("UTG open", "BB defend vs 3-bet", etc.).
- PioSolver uses the same 13×13 with right-click → per-hand frequency slider; suit selection exposed in a 4×4 sub-grid per click; per-action color band (R/C/F) renders on the right edge of each cell.
- Both products store presets as plain-text Pio-syntax ranges, which round-trip through `poker_solver/range.py:parse_range()` (`ui/views/spot_input.py:266` already uses this for the string-input alternative).

**Proposed widget design (NiceGUI):**

**Layout:**
```
+---------------------------------------+
| [Preset ▼] [Hero seat: P0 P1] [+ ⟲]   |
+---------------------------------------+
| 13×13 grid (existing,                 |
| spot_input.py:248-263)                |
+---------------------------------------+
| String mode / Matrix mode toggle      |
| (existing, spot_input.py:222-225)     |
+---------------------------------------+
| Click cell → 4×4 suit sub-grid +      |
| ui.slider(0, 100) for frequency       |
| (NEW dialog)                          |
+---------------------------------------+
```

**Click-to-select (NEW dialog):**
- Single click on `spot_input.py:248-263` cell → cycle (existing behavior, preserved).
- Long-press (`btn.on('long-press', ...)`) or right-click (`btn.on('contextmenu', ...)`) → open `ui.dialog` containing:
  - 4×4 suit sub-grid (e.g. for "AKo": 4 hearts × 4 spades = 12 combos shown).
  - Per-combo `ui.slider(0, 100)` row.
  - "Set all" `ui.slider` that propagates to the 12 combo sliders.
  - Save/Cancel.

**Frequency input (0-100% per hand):**
- The dialog above provides 0-100% sliders; the existing cycle gesture (`spot_input.py:330-362`) stays for fast 4-step adjustment.

**Save/load presets:**
- Engine side: ship `poker_solver/charts/chart_*.json` files (the `charts/` dir already exists per repo root listing — `/Users/ashen/Desktop/poker_solver/poker_solver/charts/`). Each file: `{"name": "UTG open 100bb", "format": "pio_range_string", "data": "AA,KK,..."}`.
- UI side: `ui.select` dropdown populated from `glob.glob("poker_solver/charts/chart_*.json")`. On selection, parse via `RangeWithFreqs.from_string(...)` and assign to `state.current_spot.ranges[hero_player]`.
- New "Save current as preset" button writes the active range to a user-chartdir (`~/.poker_solver/charts/`) via `RangeWithFreqs.to_string()` (`ui/state.py:283-291`).

**Connection to `poker_solver/range.py`:**
- Round-trip is already proven via `spot_input.py:266-291` string-input mode using `RangeWithFreqs.from_string` (`ui/state.py:296`) / `RangeWithFreqs.to_string` (`ui/state.py:283`).
- The new dialog calls `rw.set_frequency(combo, freq)` per combo (existing API at `ui/state.py:269-280`).

---

## 5. Exploitability slider tier numeric defaults — measurement protocol

**Search result:** **No post-PR-10b measurement pass exists in `docs/`.** Searched for `measurement_pass`, `tier_default`, `tier defaults`, `convergence curve`, `tier.*measurement` — no hits beyond `comprehensive_review_2026-05-23.md` and `docs/pr8_prep/pr_report.md`, neither of which contains numeric tier measurements. `PLAN.md` §11 B4 lists this as a burst-exit-criterion blocker still labeled TBD.

**Proposed measurement protocol** (one paragraph; orchestrator can spawn as a separate agent):

> Spawn a measurement agent that runs the Rust-backend solver against the 12 PR 10a preset fixtures (`ui/mock_solver_fixtures.py:202-523`) at 4 iteration ceilings — 200 / 500 / 1000 / 2000 — and logs the converged exploitability (mBB/pot) and wall-clock at each ceiling. Build a 12-row × 4-column matrix. For each tier, pick the **median** exploitability that 90% of the fixtures hit within their persona budget: Draft = median expl at 200 iters (Marcus 1-min target), Standard = median at 500 iters (Sarah/Daniel 5-min target), Tight = median at 1000 iters (Daniel deep-dive 15-min target), Library = median at 2000 iters (Priya batch, 30-min kill-switch). Cross-validate against external references: `postflop-solver` default 0.5% pot, GTOW Library tier 0.1-0.3%, Shark target 0.1%, Brown MIT reference solver 2000 iters as convergence proxy (cited in `PLAN.md` §1). Output: a 4-line table written to `docs/pr_proposals/v1_5_slider_tier_defaults_measured.md` that the UI imports as constants. Wall-clock budget for the measurement pass: ≤2 hours.

**Blocker note:** PR 24 (this proposal) **cannot ship the slider with measured tier defaults until the measurement agent runs.** If 24a wants to ship the slider widget, it must either (a) ship with stub defaults (1% / 0.5% / 0.25% / 0.1% from `PLAN.md` §1 industry-standard guesses) and label them as "preliminary" in the tooltip, OR (b) defer the slider to 24b after the measurement agent completes. Recommend **(a)** so the slider widget lands with 24a, with a 24b follow-up swapping in measured defaults.

---

## 6. PR sub-sequencing (24a / 24b recommendation)

**Total gap count: 7** (range editor enhancement, RvR, hero_player, "true Nash" vs "blueprint" label, node-locking, asymmetric contributions, tiered slider).

Recommend **two sub-PRs** (the user-facing scope is large enough to warrant the split for review hygiene + dual-channel sync overhead). One package each below is roughly even in code + smoke-test surface; the dependency edges are clean.

### PR 24a — RvR + hero_player + slider + UI labels

Scope:
- §3.2 Range-vs-range solve mode (toggle + worker route + matrix output binding).
- §3.3 `hero_player` selector (single toggle; threads through RvR).
- §3.4 "true Nash" vs "blueprint" chart subtitle.
- §3.7 Exploitability slider with 4 tiers (ships with stub defaults per §5).

Rationale:
- All four close v1.3.0–v1.3.2 gaps. No new engine surface required; the engine code shipped 2026-05-23.
- All four are read-from-state additions to existing panels (run_panel.py + spot_input.py + range_matrix.py); no new dialogs.
- Persona retest gain: W2.3 (Sarah), W3.4 + W3.5 (Daniel) become testable end-to-end.

Estimated UI smoke-test additions: 6.

### PR 24b — Node-locking + asymmetric contributions + range editor polish

Scope:
- §3.5 Node-locking editor (new dialog + tree-browser integration; new state field).
- §3.6 Asymmetric `initial_contributions` (new spot fields + facing-bet input expansion).
- §3.1 Range editor polish (per-hand frequency dialog + preset library).
- §5 follow-up: swap in measured slider defaults from §3.7.

Rationale:
- §3.5 + §3.6 close v1.4.0–v1.4.1 gaps; both need new dialogs and tree-browser changes.
- §3.6 depends on v1.4.1 engine work landing first (currently in flight per spec); 24b waits on v1.4.1 merge.
- §3.1 polish is independent but bundled here because the dialog scaffolding overlaps with §3.5.

Estimated UI smoke-test additions: 9.

**Alternative: single PR 24.** Reject — total scope is ~15 smoke-test additions and ~600 lines of UI code touching 5 files; review burden + integration push window favors the split.

---

## 7. Persona workflow coverage — 18 workflows

Per `docs/pr13_prep/persona_acceptance_spec.md`, 18 workflows across 4 personas (Marcus / Sarah / Daniel × 5, Priya × 3). Mapping each to required UI surface and 24a/24b coverage:

| Workflow | Persona | One-line gap | UI surface required | 24a | 24b | Open? |
|---|---|---|---|---|---|---|
| W1.1 jam 88 at 9 BB | Marcus | CLI lookup, no UI needed | None | — | — | No |
| W1.2 JJ vs pot river bet | Marcus | Facing-bet input | §3.6 | | x | No |
| W1.3 equity check AKs vs JJ | Marcus | Equity tool already CLI | None | — | — | No |
| W1.4 100 BB SRP preflop chart | Marcus | PR 9 preflop solver | (PR 9, not PR 24) | — | — | Blocked outside 24 |
| W1.5 76s fold at 10 BB EV | Marcus | EV decomp on chart | (Not UI; engine return_ev) | — | — | Outside 24 |
| W2.1 Full 100 BB chart | Sarah | PR 9 + UI matrix display | (PR 9 + existing display) | — | — | Outside 24 |
| W2.2 Range diff vs GTO | Sarah | Range diff tool | None (not in PR 24 scope; engine API) | — | — | Outside 24 |
| W2.3 KK on Q-high vs c-bet range | Sarah | RvR + facing-bet | §3.2 + §3.6 | x | x | No |
| W2.4 Batch-solve CSV | Sarah | CLI/scripts; UI optional | None | — | — | Outside 24 |
| W2.5 30 BB SRP preflop | Sarah | PR 9 preflop | (PR 9) | — | — | Outside 24 |
| W3.1 Villain never bluffs river | Daniel | Node-locking | §3.5 | | x | No |
| W3.2 GTO vs villain frequencies | Daniel | Node-locking + RvR | §3.2 + §3.5 | partial | x | No |
| W3.3 Merged-strategy response | Daniel | Node-locking | §3.5 | | x | No |
| W3.4 MDF check BB vs half-pot c-bet | Daniel | RvR + facing-bet + hero_player=1 | §3.2 + §3.3 + §3.6 | partial | x | No |
| W3.5 Polarization on monotone | Daniel | RvR | §3.2 | x | | No |
| W4.1 Library round-trip (Python) | Priya | Library API (PR 11 shipped) | None | — | — | Already works |
| W4.2 Limp-or-fold custom mode | Priya | Engine extensibility docs | None | — | — | Outside 24 |
| W4.3 noambrown diff API | Priya | Parity API exposure | None | — | — | Outside 24 |

**Persona coverage by PR:**

| | 24a alone | 24a + 24b | 24b alone |
|---|---|---|---|
| Workflows fully unblocked (UI side) | 1 (W3.5) | 6 (W1.2, W2.3, W3.1, W3.3, W3.4, W3.5) | 5 (W1.2, W2.3, W3.1, W3.3, W3.4 — needs RvR from 24a) |
| Workflows partially unblocked | 2 (W2.3 RvR side, W3.4 RvR+hero side) | — | — |

24a alone closes 1 of the 18 workflows from a UI angle; 24b is needed for the remaining 5 facing-bet / node-locking workflows. **Recommend shipping 24a → 24b sequentially** with no Marcus / Sarah / Daniel session retest until both land (saves one persona pass).

---

## 8. Open questions / orchestrator decisions

1. **Slider tier defaults.** §5 measurement pass is a hard blocker for §3.7 final numbers. Recommend spawn a measurement agent in parallel with 24a; 24a ships stub defaults from `PLAN.md` §1 industry-standard guesses (1% / 0.5% / 0.25% / 0.1% pot) with "preliminary" tooltip. 24b swaps in measured values.
2. **v1.4.1 merge ordering.** §3.6 depends on the asymmetric_contributions engine PR (v1.4.1 in flight) landing first. 24b must merge **after** v1.4.1; orchestrator should sequence accordingly.
3. **Range editor polish scope.** §3.1 expansion (per-hand suit-aware dialog) is a UX polish, not a feature gap. Could defer to a post-24b PR if 24b is large. Recommend bundling into 24b since dialog scaffolding overlaps with §3.5.
4. **Tree-browser node-lock integration.** §3.5 adds a right-click menu to `tree_browser.py`. Verify NiceGUI 3.x supports `btn.on('contextmenu', ...)`; if not, fall back to a small `[Lock]` button per row.
5. **`hero_player` semantics in concrete-vs-concrete solves.** §3.3 says swap matrix display rows. Confirm whether the existing matrix display already does this (suspect not; `range_matrix.py:_snapshot_player` reads from engine state, not `spot.hero_player`).
6. **Push/fold + node-locking interaction.** §3.5 must surface the `solver.py:74-86` ValueError for ≤15 BB preflop. Verify UX message + `force_tree_solve` escape hatch are wired through `SolveRunner.start`.

---

## 9. Hard rules compliance

- READ-ONLY investigation: confirmed; no UI code modified.
- No implementer spawned: confirmed.
- Every UI claim cited with `file_path:line_number`: confirmed.
- NiceGUI guidance: no in-repo NiceGUI references found (`grep -rn "nicegui" references/` returns no hits); proposed widget choices use the conservative subset already used by `ui/views/*.py` (`ui.toggle`, `ui.dialog`, `ui.slider`, `ui.number`, `ui.expansion`, `ui.select`).
