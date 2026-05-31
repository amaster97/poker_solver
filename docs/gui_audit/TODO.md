# GUI Campaign — Living Plan / TODO

Working checklist for the NiceGUI GUI test+fix campaign. **Maintain this continuously** —
check off done, add new items as they surface, and move `[E]` engine-gated items into
active work once the engine lands. This is the forward plan; `findings.md` (same dir) is
the detailed record of what happened. Branch: `fix/gui-audit-message-leaks` (UNMERGED).

**Legend:** `[x]` done · `[~]` in progress · `[ ]` queued · `[E]` engine-gated · `[?]` needs user decision

---

## DONE — committed (`6d5fbdc` → `1703de8` → `e0fe65a`); 102 UI tests green
- [x] Light mode legible (#1 complaint)
- [x] Hide Python/engine toggle; no engine names anywhere in UI
- [x] Hamburger menu (Replay onboarding / About)
- [x] LIBRARY dialog + Close button (N3)
- [x] MATRIX/STRING + suited-offsuit/exact-suit input toggles + affordance help text
- [x] Header pencil + stack-depth + Blinds&ante editing
- [x] Clean "already running" message (no traceback / method-name leak)
- [x] Progress bar + live iteration counter + ETA
- [x] Preflop route badge — "Blueprint · 100BB" / "Interpolated · 67BB ← 60+80"
- [x] Preflop deeper lines — 78-line selector; grid switches strategy per line
- [x] 13×13 preflop grid populated (real R/C/F per cell)
- [x] G1 — example flop/turn spots load deterministic ~55-226-combo ranges (no inherit)
- [x] G2 — ui.timer no longer raises "parent slot deleted" on teardown
- [x] G3 — matrix + range editor repaint on preset load
- [x] N2 / N2-RESET — status chip recomputes from result; clear_results invalidates prior solve
- [x] W2 — clear_results cancels+reaps an in-flight worker (no concurrent-solver hazard)
- [x] W1 — production postflop forced to Range-vs-range (gated to postflop streets only)
- [x] U14 — sanitized user-facing internal refs ("PR NN" / engine names) in toasts/labels
- [x] N5 — preflop chart subtitle no longer stale
- [x] P1 — board card picker rank-mirror fixed ("As" places As, not 2s)
- [x] P5 — RESET SPOT clears the board chips
- [x] P2 — decision-tree node selection drives the range matrix (uses solved config)
- [x] P3 — matrix grid + combo inspector + header share one seat resolver (no "0 combos" mismatch)
- [x] Decision: **Concrete = dev-only** (`POKER_SOLVER_DEV_CONCRETE`); prod postflop = RvR

## IN PROGRESS
- [x] **Card graphics** — suit symbols ♠♥♦♣ + 4-color, theme-aware (`_cards.py`), on header spot label + combo inspector + board chips. Render verified (colored, both themes via `var(--ps-text)` + mid-tones). Chip strip made declarative (cleaner; fixes the awaited-handler path; test added).
  - **Live preset/reset REFRESH (was a real regression, fix applied, live-verify PENDING a real browser):** the W3-followup's sync-on_click used fire-and-forget `background_tasks.create(refresh)` — a DETACHED task with no client/slot context — so a LIVE preset/reset click updated the data + header but did NOT repaint the **matrix OR the chips OR the range-editor fraction** (only reload did). Bigger than the chip strip; the awaited-handler tests passed and HID it. FIX applied: `_schedule_spot_views_refresh` uses `ui.timer(0.01, …, once=True)` (runs in `parent_slot` / live client context + awaits `client.connected()`), keeping mutations sync (smoke #2/#4 still pass). Full UI suite 105 green; new tests drive the real button + assert the timer-in-slot mechanism (fail pre-fix). **CAVEAT (honest):** could NOT conclusively confirm the live repaint via the Claude-Preview browser — its synthetic eval-clicks reliably show *awaited-inline* refreshes (P2/P3 tree-nav, the earlier 226) but NOT the *deferred ui.timer* repaint (matrix/chips still read stale on eval-click; likely `await client.connected()` not resolving for the preview client). **NEEDS a real-browser confirmation** (Chrome). (This is also why P5 "RESET clears board" earlier was a false pass.)

## QUEUED — non-blocking, build when appropriate
- [~] **Chain solve → full vision** *(USER 2026-05-30: build (b), the clarify-only option (a) was REJECTED as not useful)*: input specific hole cards, walk **preflop → river (termination)**, showing at each street "what I did / can do + GTO rec + the range."
      - Today it's a preflop→FLOP chain by hand CLASS (class → preflop action line → flop → that class's flop strategy).
      - Target = hole-card-specific, all-street walkthrough/replay.
      - **Buildable now:** the preflop step + the walkthrough UI shell (hole-card input, per-street layout, rec+range panels).
      - `[E]` **turn/river streets need the fast engine** (postflop must be tractable; today it hangs) — graceful "pending engine" until then.
      - STATUS: **design DONE** → full plan recorded at `docs/gui_audit/chain_solve_b_plan.md`. Boundary: `solve_chained` = preflop + flop ONLY (no turn/river), CLASS-level (not combo), and the flop solve can HANG (Tier-A MUST add an `exceeds_tree_budget` guard). **Tier A build (hole-card entry → preflop walkthrough → guarded flop → termination) is NEXT**; turn/river = Tier B scaffold ("pending engine").
- [ ] **Auto range generation** *(user 2026-05-30 — "we should have auto range generation, not just manual spot input")* — fill a player's range slot from the **preflop blueprint** for a chosen position/depth/line (e.g. "BTN open @ 100bb", "BB defend vs 2.5bb open"), so you don't hand-build ranges for every postflop spot. Blueprint-backed → **engine-LIGHT, buildable now** (the data is what the Preflop Chart already shows; just needs a UI to project it into a range slot).
      - Distinct from what EXISTS: manual type/click input; save/load YOUR ranges (`range-preset` dropdown, e.g. `my_btn_open`); canned example-spot ranges.
      - PARTIALLY covered already: **chain solve auto-derives the postflop continuation ranges from the preflop solve** (`ContinuationRanges`, chained.py:166/226) — so the walkthrough's postflop ranges are auto-generated. The GAP is the STANDALONE "fill this spot's range from the blueprint/position" convenience on the Solver tab.
- [ ] Visual dress-up pass — matrix color gradients, spacing, less "debug grid" feel (non-engine-gated parts only)
- [ ] **Qualitative validation: persona walkthroughs THROUGH the GUI** *(user 2026-05-30; not-now, keep in back of mind)* — take each persona's task from the plan's Part B, run it through the LIVE GUI, and confirm it's actually COMPUTABLE end-to-end. Scope = **single solve per persona only** (NOT research-grade multi-solve chains). `[E]` postflop-solve personas gated on the engine; preflop/light personas testable now.

## DEFERRED — ENGINE-GATED (do WITH the engine; don't build twice)
- [E] Rich strategy/action display — raise + multiple bet sizes + mixed frequencies (comes with the real RvR engine; current fold/call view is the Concrete/river-degenerate reality)
- [E] Bet-size menu UI + street/tree structure — the engine defines these; UI already reads bet sizes from config so it absorbs the final menu
- [E] RvR-flop tractability — currently hangs in tree-build on this branch's engine
- [E] **MERGE to `main` + private mirror** — gated on engine reconciliation (main's fast IE/vector/suit-iso engine + this branch's UI progress/cancel hooks). *(user gates the merge)*

## FOLLOW-UPS / LATENT (documented; fix when convenient)
- [ ] Spot-model SPR gap — `_spot_from_config`/`Spot.to_hunl_config()` drop a postflop subgame's pot+contributions, so a HAND-BUILT (not fixture-loaded) postflop spot misrepresents SPR. P2 sidesteps it for solved-config tree/matrix only.
- [ ] Test-isolation flake — global `_state_singleton` leaks `current_spot` across test files (`test_board_picker_accepts_three_cards`, order-dependent; green in stable order). Fixtures should `reset_state_for_testing()`.
- [ ] Open-chart `AA` cell read `C36` once (looks off for a standard RFI) — blueprint-data/projection; verify with engine/blueprint review.

## IDEAS / TO-ADD
- _(append new items here as they surface)_
