# Chain-Solve (b) — Hole-Card Walkthrough: Implementation Plan

User-chosen feature (2026-05-30): rebuild the "Chain solve" tab from a class-level matrix
browser into a **guided hole-card walkthrough** — "I have X/Y cards; walk preflop → river
(termination), showing at each street what I did / can do + the GTO rec + the range."

Evidence-based design (read of `poker_solver/chained.py`, `ui/views/chained_tab.py`,
`ui/views/preflop_chart.py`, `ui/state.py`). **Split into Tier A (build now) / Tier B (engine-gated).**

## Hard boundary — what `solve_chained`/`ChainedSolveResult` actually supports
- **Preflop: full.** `_solve_preflop_range` → `preflop_result.per_class_strategy` ({class: {action: prob}}); deeper lines in `per_history_strategy` (chained.py:644). Fast (solved at solve time).
- **Flop: lazy, only.** `ChainedSolveResult.solve_postflop` ASSERTS `len(board)==3` and raises otherwise (chained.py:335-339 "Phase A only supports flop subgames"). Calls `solve_range_vs_range_nash`.
- **No turn/river chaining.** No flop→turn→river. → turn/river = Tier B.
- **All data is CLASS-level, not combo-level.** AhKh → AKs for ALL strategy lookups (preflop AND flop). Board interaction (AhKh flush on a heart board) is NOT in the class-level flop strategy. Per-combo lands "Phase B" (chained.py:1024-1028). **Surface this honestly in the UI — don't imply combo-exact.**
- **Flop solve can HANG.** The chained flop `solve_range_vs_range_nash` is O(hands² × nodes), synchronous on the UI thread (chained_tab.py:862-864), and is NOT covered by the `exceeds_tree_budget` guard (state.py:1230-1242 excludes `solver_mode=="chained"`). A wide-range flop pick hangs the tab today. **MANDATORY Tier-A mitigation: add an `exceeds_tree_budget` guard before `solve_postflop`.**

## UI flow (walkthrough state machine; transient state on the runner, like `_chained_selected_*`)
- **Screen 0 — hole-card entry + config:** existing config block + a NEW 2-card hero hole-card picker (adapt the board picker, cap 2). "Start" → `solve_chained` (existing dispatch) → `hero_class = classify_combo(c0,c1)` (state.py:210).
- **Screen 1 — preflop decision(s):** for each hero decision node on the chosen line: legal actions (walk `HUNLPoker`), GTO rec freqs `result.query(hero_class, board=None)` (rendered as the existing bars), the range as a 13×13 painted via `project_preflop` (hero class highlighted). User picks an action → advance tokens until a flop-reaching terminal (key in `continuation_ranges`) or fold (terminate).
- **Screen 2 — flop (Tier A, guarded):** board picker (3 cards) → tractability guard → `result.query(hero_class, seq, board)` → flop rec + range (`project_postflop`). Route badge via `RouteInfo`.
- **Screen 3+ — turn/river (Tier B):** placeholder panels "pending fast engine — solve flop to continue." No compute.
- **Termination:** summary strip of the walked path (per street: action taken, rec, GTO delta).
- **Nav:** stepper/breadcrumb (Preflop→Flop→Turn→River) + back/forward (preflop cheap; flop uses the LRU cache chained.py:341).

## Reuse map (reuse the LIGHT chained/preflop-chart projections; do NOT reuse tree_browser/range_matrix)
- preflop per-class + matrix: `project_preflop`, `_render_grid/_render_cell`, `aggregate_actions`, `cell_color_css` (chained_tab/preflop_chart).
- deeper lines: `per_history_strategy` + `preflop_line_label`.
- freq bars: `_render_postflop_panel` bar block (chained_tab.py:907).
- flop rec+range: `query(...)`, `project_postflop`, `classify_action`.
- picker grid: board-picker pattern (extract a shared `_card_grid(...)`).
- hole→class: `classify_combo` (state.py:210).
- **DO NOT reuse `tree_browser`/`range_matrix`** — they are combo-level and keyed on `runner.result`/`_solved_config`; the chained path leaves `runner.result=None` (populates `chained_result`), so that machinery doesn't apply. (Biggest tempting-but-wrong reuse.)

## File plan (rework chained_tab.py IN PLACE — keep `tab-chained`/`chained-tab-*` markers + `render(state, on_solve)` signature)
- `chained_tab.py`: KEEP projection/aggregation helpers + re-exported primitives block (Smoke 7). ADD walkthrough state accessors (`_wt_street/_wt_tokens/_wt_hero_combo/_wt_picked`), hole-card picker, stepper, per-street panel, preflop decision walker, flop guard. REPLACE the flat action-sequence dropdown (`_render_action_selector`) with the stepper → **removes `chained-tab-action-select` marker** (update Smoke 4).
- `ui/state.py` / `SolveRunner`: new transient attrs via setattr (like `_chained_selected_*`); optional `chained_flop_too_large(...)` helper reusing `exceeds_tree_budget`.
- `ui/app.py`: capture hero hole-card combo at solve time; existing polling-tick refresh reused.
- Extract shared `_card_grid(state, selected, cap, on_toggle, marker_prefix)`.
- Build order: (1) state + stepper shell w/ placeholders → (2) hole-card picker→class → (3) preflop screen → (4) flop screen (guarded) → (5) Tier-B placeholders + termination → (6) tests.

## Tier A (now) vs Tier B (engine-gated)
- **A:** hole-card entry→class; stepper/breadcrumb/back-forward; preflop walkthrough (multi-decision, legal actions, class-level rec, range matrix, action picking); **flop step GATED by `exceeds_tree_budget`** (tractable→solve+show; too-wide→"narrow ranges" message, no hang); fold-line termination summary.
- **B (scaffold "pending engine", no compute):** turn/river streets; per-combo board-aware flop strategy (note class-level limit); async/off-thread flop solve hook.

## Test plan (`nicegui.testing.User`, extend `tests/test_ui_chained_tab.py`; mocked solve_chained)
- Keep passing: Smoke 1/2/5/6/7. CHANGE: Smoke 3 (assert hole-card capture), Smoke 4 (rework: hole-card pick→advance→flop pick→solve_postflop fired; `chained-tab-action-select` removed).
- ADD: hole-card→class; preflop rec for hero class; advance-to-flop; flop guard blocks wide range (no solve_postflop); turn/river pending-placeholder (no compute).
- New markers: `chained-tab-stepper`, `-hole-picker`, `-hole-cell-{card}`, `-step-{preflop|flop|turn|river}`, `-legal-action-{label}`, `-pending-engine`.

## Risks / open questions
1. **Flop hang** (highest) — guard is MANDATORY in Tier A. (Open: retrofit the guard to the existing tab too?)
2. **Class- not combo-level** — surface honestly; combo-exact is Phase B.
3. **Preflop multi-decision legality** — need a forward "what can hero do at this node" enumerator (token-walk logic exists: `_last_token`/`_walk_pair_reach`). Open: let user pick villain actions, or auto-advance villain?
4. **Marker churn** — removing `chained-tab-action-select` breaks Smoke 4 as written; update same PR.
5. **All-in/fold terminals** excluded from `continuation_ranges` (chained.py:862) — terminate gracefully.
6. **Hero seat** — respect `spot.hero_player` when enumerating hero decision nodes.

Critical files: `ui/views/chained_tab.py`, `poker_solver/chained.py`, `ui/state.py`, `ui/app.py`, `tests/test_ui_chained_tab.py`.
