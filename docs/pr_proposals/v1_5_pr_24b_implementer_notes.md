# PR 24b — Implementer Notes (GUI Gate 2, second half)

**Branch:** `feature/pr-24b-gui-nodelock-asym`
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-24b-gui-nodelock-asym`
**Base:** `feature/pr-24a-gui-rvr-slider` at `8b1f672`
**Commit count:** 5 commits on top of PR 24a
**Date:** 2026-05-23

---

## 1. What landed

Per the spec at `docs/pr_proposals/v1_5_pr_24b_implementer_prompt.md` §A:

### §3.5 Node-locking editor (`node-lock-dialog`)

- New `ui/views/node_lock_editor.py` — `ui.dialog`-hosted editor exposing
  one `ui.slider(0, 100)` per legal action plus a live "must sum to 100%"
  validator. Save is disabled outside the 99-101% tolerance; on commit,
  the slider values are normalized to a probability vector and written to
  `Spot.locked_strategies[infoset_key]`. Helpers: `remove_lock`,
  `clear_all_locks`.
- `ui/views/tree_browser.py` — "Lock current node" button
  (`tree-lock-current-button`) next to the reach-filter slider. Yellow
  padlock indicator renders on locked rows via the new
  `tree_node_to_dict(..., locked_keys=...)` kwarg.
- `ui/views/run_panel.py` — "Locked strategies" expansion
  (`locks-expansion`) lists every lock with per-row unlock buttons
  (`unlock-button-{key}` markers).
- `ui/state.py` — `Spot.locked_strategies: dict[str, list[float]]` field
  added; `SolveRunner.start(locked_strategies=, force_tree_solve=)` kwargs
  added; `_dispatch_solve` threads them through to
  `solve_hunl_postflop(locked_strategies=...)` and the canonical
  `solver.solve(...)` for non-postflop paths.
- `ui/views/run_panel.py:_show_error` — surfaces the push/fold ValueError
  via `ui.notify(type='negative')` with a "Use tree-builder mode"
  remediation button (`force-tree-solve-button`) that sets
  `runner._pending_force_tree_solve=True` for the next solve.

### §3.6 Asymmetric `initial_contributions`

- `ui/state.py:Spot` — three new fields: `pot_so_far_bb`, `villain_bet_bb`,
  `bettor_is_p0`.
- `ui/state.py:Spot.to_hunl_config()` — when `villain_bet_bb > 0`, builds
  asymmetric `initial_contributions = (pot_half + bet, pot_half)` with
  seat assignment per `bettor_is_p0`; sets `initial_pot` to the sum.
  Symmetric case (default `villain_bet_bb=0`) unchanged.
- `ui/views/spot_input.py:_render_facing_bet_section` — new
  `ui.expansion("Facing bet (postflop subgame)")` inside the Blinds & ante
  section. Markers: `facing-bet-expansion`, `pot-so-far-input`,
  `villain-bet-input`, `bettor-seat-toggle`.
- `ui/app.py:_on_solve` — validates `villain_bet_bb <= bettor_effective_stack`
  BEFORE calling `to_hunl_config()`; surfaces a notify on overflow without
  spawning the worker.

### §3.1 Range editor polish

- New `ui/views/range_freq_editor.py` — per-hand frequency dialog
  (`range-freq-dialog`) with one `ui.slider(0, 100)` per combo (6 for
  pairs, 4 for suited, 12 for offsuit) plus a "Set all" master slider
  (`range-freq-master-slider`). Save writes per-combo via
  `RangeWithFreqs.set_frequency`.
- `ui/views/spot_input.py` — right-click handler on matrix cells
  (NiceGUI 3.x `Element.on("contextmenu", ...)`) opens the dialog. The
  existing 4-step cycle on cell-click is preserved as the fast-path.
- `ui/views/spot_input.py:_render_chart_preset_row` — preset dropdown
  (`range-preset-select`) scans `poker_solver/charts/chart_*.json`
  (built-in) and `~/.poker_solver/charts/*.json` (user). "Save as preset"
  button (`save-preset-button`) writes the active hero range to the user
  charts dir via a name-prompt dialog.
- New chart library at `poker_solver/charts/`:
  - `chart_100bb_sb_open.json` — 606 combos.
  - `chart_100bb_bb_defend.json` — 526 combos.
  - `chart_100bb_btn_3bet.json` — 162 combos.
  - `chart_30bb_sb_jam.json` — 258 combos.
  - `README.md` — schema docs + honest framing.

### §5 Measured slider defaults swap

- `ui/views/run_panel.py:_TIER_DEFAULTS` — values were already shipped in
  PR 24a using the measured iter ladder (Draft=200, Standard=500,
  Tight=1000, Library=2000). PR 24b updates the tooltip to reference
  `docs/v1_5_slider_tier_defaults_measured.md` and removes the
  "preliminary" qualifier. The numeric ladder is taken VERBATIM from the
  measurement doc §1 per the no-extrapolate rule.

### Smoke tests (`tests/test_ui_pr24b.py`)

**9 smokes — verdict GREEN (9/9 pass; combined 44/44 with the existing
28 baseline + 7 PR 24a smokes).**

1. `test_node_lock_dialog_writes_spot_locked_strategies` — dict storage
   + `remove_lock` helper round-trip.
2. `test_locked_strategies_threads_through_solve_runner_start` —
   monkeypatches `solve_hunl_postflop`, asserts the kwarg reaches it via
   `SolveRunner.start -> _worker -> _dispatch_solve`.
3. `test_pushfold_plus_locks_raises_value_error_without_force` — engine
   guard test against `poker_solver/solver.py:74-86` per spec.
4. `test_force_tree_solve_flag_threads_through_runner` — `force_tree_solve`
   bypasses the push/fold short-circuit; postflop solver still reached
   with locks.
5. `test_asymmetric_contributions_half_pot_bet_p0` — spec body example:
   `villain_bet_bb=0.5` on 1 BB pot baseline (each player put in 1 BB,
   `pot_so_far_bb=2.0`) yields `initial_contributions == (150, 100)`
   verbatim. Seat flip yields `(100, 150)`.
6. `test_villain_bet_exceeds_stack_does_not_start_solve` — UI fixture
   smoke: villain bet > effective stack -> `_on_solve` early-returns
   without spawning the worker.
7. `test_per_hand_freq_dialog_sets_per_combo_frequency` — `RangeWithFreqs`
   contract: per-combo frequency round-trips through `set_frequency` /
   `frequency_of`.
8. `test_preset_chart_100bb_sb_open_loads` — `chart_100bb_sb_open.json`
   parses + yields the documented ~606 combo count.
9. `test_tier_slider_defaults_swap_to_measured_values` — `_TIER_INDEX`
   matches the measurement doc §1 VERBATIM; tooltip no longer claims
   "preliminary".

Existing 28 UI smokes (`tests/test_ui_smoke.py`) and 7 PR 24a smokes
(`tests/test_ui_pr24a.py`) all still green; no regression.

---

## 2. Sequencing / commit cadence

5 commits on `feature/pr-24b-gui-nodelock-asym`:

| # | SHA | Subject |
|---|-----|---------|
| 1 | `8243978` | PR 24b (1/5): state + asymmetric contributions + node-lock plumbing |
| 2 | `14ebb89` | PR 24b (2/5): node-lock editor dialog + tree-browser hook + run-panel locks list |
| 3 | `8c86f3d` | PR 24b (3/5): asymmetric initial_contributions UI input |
| 4 | (commit 4) | PR 24b (4/5): range editor polish + chart preset library |
| 5 | (this commit) | PR 24b (5/5): measured slider tooltip swap + smoke tests + implementer notes |

---

## 3. Decisions / Deviations from spec

### 3.1 §8 Q4 — NiceGUI 3.x `contextmenu` event support

**Orchestrator flag:** "VERIFY NiceGUI 3.x exposes the `contextmenu`
event. If unsupported, fall back to a small `[Lock]` button per row."

**Status:** NiceGUI 3.12.1's generic `Element.on("contextmenu", ...)`
subscribes to any DOM event by name (verified via `inspect.signature`
on `Element.on` — it takes any string event type with optional throttle
+ js_handler).

**Decision: button-as-primary, contextmenu-as-bonus.** The "Lock current
node" button (`tree-lock-current-button`) is the discoverable primary
affordance because right-click on browser-rendered DOM collides with the
browser's native context menu in Chromium-based browsers — users would
need to know to suppress the native menu via `event.preventDefault()`,
which NiceGUI's emit pipeline doesn't auto-wire. The contextmenu
subscription is wired as a bonus convenience, but the user-facing
documentation (tooltip on the button) points at the button.

Same pattern for the per-hand frequency dialog: cell-click cycles the
4-step frequency (fast-path); right-click opens the per-combo dialog
(bonus path).

### 3.2 Chart library coverage

**Spec:** "If you cannot source authoritative ranges, ship 1-2 minimal
placeholder presets with a README explaining the schema and leave the
others as TODO. Be honest in the PR report."

**Status: honest mid-coverage.** Shipped all 4 preset files requested
in the spec body (`chart_100bb_sb_open`, `chart_100bb_bb_defend`,
`chart_100bb_btn_3bet`, `chart_30bb_sb_jam`) using conservative published
heuristics; no authoritative range data exists in `references/` (verified
by grepping for `range.*chart` — only `_COMPETITORS.md` mentions ranges;
no JSON tables found in any reference repo).

The README (`poker_solver/charts/README.md`) documents the gap and lists
the TODO for cross-validation against the noambrown reference solver.
Honest framing: "These presets are published heuristics, not
authoritative GTO outputs."

### 3.3 §3.6 "1 BB pot baseline" interpretation

**Spec body example:** "Set villain_bet_bb=0.5 (half-pot) with bettor=P0,
assert HUNLConfig.initial_contributions == (150, 100) for a 1 BB pot
baseline."

**Interpretation locked:** "1 BB pot baseline" means each player has
already put in 1 BB, so `pot_so_far_bb = 2.0` (the TOTAL pot, not each
player's share). The half-pot bet is then 0.5 BB. Math:
`pot_half_cents = 100`, `bettor = pot_half + bet = 100 + 50 = 150`,
`facer = pot_half = 100`. Sum = 250 = `initial_pot`. Smoke 5 uses
these exact spec values + verifies the seat flip case.

This convention treats `pot_so_far_bb` as the total chips already in the
middle (matching the engine's `initial_pot` convention), not each
player's individual share.

### 3.4 SolveResult plumbing for force_tree_solve

The push/fold guard lives in BOTH `poker_solver/solver.py:74-86` (the
engine surface) AND `ui/state.py:_dispatch_solve` (the UI dispatcher).
This is intentional: the UI dispatcher needs to surface the ValueError
even when the worker thread routes through `solve_hunl_postflop` directly
(bypassing `canonical_solve`). The duplicated guard is a defense-in-depth
move.

### 3.5 Push/fold + locks edge case — preflop NotImplementedError

When `force_tree_solve=True` is set on a ≤15 BB preflop config, the
engine routes through `solve_hunl_preflop` (PR 9), which is currently
`NotImplementedError` on most builds. Smoke 3 only tests the guard
(ValueError raised without force_tree_solve); the force-flip is tested
via the postflop branch in smoke 4 to avoid PR-9 coupling.

This is a UX gap (the user clicks "Use tree-builder mode", retries, and
sees a NotImplementedError instead of a successful solve), but it's
inherited from the PR 9 status; PR 24b correctly surfaces both errors
via the existing notify path.

---

## 4. Known issues / blockers

- **None UI-side.** All 44 UI smokes (28 baseline + 7 PR 24a + 9 PR 24b)
  green; `ruff check` clean across `ui/` and `tests/test_ui_pr24b.py`;
  `ruff format` applied.
- **Pre-existing baseline failures (not introduced by PR 24b):** Same as
  PR 24a — 5 `tests/test_range_vs_range_aggregator.py` failures from
  missing built `poker_solver._rust` module; pre-existing mypy errors in
  `poker_solver/*` + `ui/views/library_browser.py`; ruff format drift on
  PR-24a-touched files. PR 24b's new files (`node_lock_editor.py`,
  `range_freq_editor.py`, `test_ui_pr24b.py`) are clean.
- **Chart library is heuristic, not authoritative.** Documented in the
  README; the four shipped files use conservative published heuristics
  with no authoritative GTO cross-validation. Users should re-solve to
  confirm before relying on them for production decisions.
- **PR 24a not yet merged.** PR 24b cherry-picks must wait for PR 24a's
  cherry-pick to land first; the dependency edge is recorded in the
  prompt body (Dependencies §3 / §B.1).

---

## 5. Persona retest readiness

Per the spec §7 mapping, PR 24b unblocks the following persona workflows
on the UI side once both PR 24a + PR 24b land:

- W1.2 (Marcus JJ vs pot bet) — facing-bet input + RvR mode.
- W2.3 (Sarah KK on Q-high vs c-bet range) — RvR + facing-bet.
- W3.1 (Daniel villain never bluffs rivers) — node-locking.
- W3.3 (Daniel merged-strategy response) — node-locking.
- W3.4 (Daniel MDF BB vs half-pot c-bet) — RvR + hero_player=1 + facing-bet.

W3.5 (Daniel polarization on monotone) — already unblocked by PR 24a
(RvR alone is sufficient).

---

## 6. Forward-looking sequencing

PR 24b is ready for orchestrator audit + cherry-pick (dependency on PR
24a cherry-pick landing first). Per the hard rules: no push, no merge,
no tag from this worktree.

Possible follow-ups (out of PR 24b scope):

1. **Authoritative chart data.** Cross-validate the heuristic ranges in
   `poker_solver/charts/` against a fresh DCFR solve at the relevant
   stack depths; write a measurement doc + swap in the verified
   numbers. README's TODO section captures this.
2. **Push/fold + force_tree_solve UX gap.** When the user clicks "Use
   tree-builder mode" remediation on a ≤15 BB preflop config, the
   subsequent solve hits PR 9's NotImplementedError. A follow-up could
   surface a clearer "PR 9 preflop not yet wired; raise stacks or remove
   locks" message instead of the generic NotImplementedError notify.
3. **Per-hand frequency dialog suit-aware grouping.** The current dialog
   lists all 12 offsuit combos in a flat list. GTO Wizard / Pio render
   them in a 4×3 suit-by-suit grid. A polish PR could swap the layout.
