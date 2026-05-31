# GUI Campaign — Living Plan / TODO

Working checklist for the NiceGUI GUI test+fix campaign. **Maintain this continuously** —
check off done, add new items as they surface, and move `[E]` engine-gated items into
active work once the engine lands. This is the forward plan; `findings.md` (same dir) is
the detailed record of what happened. Branch: `fix/gui-audit-message-leaks` (UNMERGED).

**Legend:** `[x]` done · `[~]` in progress · `[ ]` queued · `[E]` engine-gated · `[?]` needs user decision

## ⚠️ VERIFICATION STATUS (as of 2026-05-30, branch tip `2009575`)
- **Test-verified:** full UI suite green except the 2 pre-existing pr24b failures (rejected `SolveTooLargeError` guard; engine-merge-gated). Auto-range 11 / chain-solve 13 / etc. pass. ruff clean.
- **Preview-browser verified (render + awaited-inline):** light mode, no-Python, hamburger, library, toggles, header/blinds, U13 message, F07 bar, U04 route badge, U06 deeper lines, the marquee Concrete solve (tree + mixed strat), P1 board picker, P5 reset, G1/G3 preset ranges, N5 chart label, clean boot of card-graphics + auto-range control + chain-solve walkthrough panel.
- **PENDING a REAL browser (Claude-Preview synthetic clicks can't verify deferred-refresh / tab-switch behaviors):** (1) live preset/reset **repaint** (the `ui.timer` fix — mechanism-correct + test-covered but not real-browser-confirmed); (2) **auto-range Apply** live repaint (same `ui.timer` path); (3) **chain-solve walkthrough interactions** (hole-pick → advance → flop) + the **CHAIN-SOLVE tab layout/isolation** (a render smoke showed Solver content alongside the walkthrough — confirm it's the reused config block vs a tab-isolation issue). → open Chrome + the Claude extension for the definitive pass.

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
- [x] **Chain solve → full vision — Tier A BUILT** *(USER 2026-05-30: build (b), clarify-only (a) REJECTED)*: `chained_tab.py` reworked into a guided hole-card walkthrough — hole-card picker → preflop walkthrough (legal actions + GTO rec bars + 13×13 range) → **guarded** flop (`chained_flop_too_large` → `exceeds_tree_budget` before `solve_postflop`) → termination summary; turn/river = Tier-B "pending engine" scaffold. Honest class-level-limitation banner. 13 chained-tab tests pass. Tier B (turn/river compute) waits on the engine merge. Original target recap:
      - Today it's a preflop→FLOP chain by hand CLASS (class → preflop action line → flop → that class's flop strategy).
      - Target = hole-card-specific, all-street walkthrough/replay.
      - **Buildable now:** the preflop step + the walkthrough UI shell (hole-card input, per-street layout, rec+range panels).
      - `[E]` **turn/river streets need the fast engine** (postflop must be tractable; today it hangs) — graceful "pending engine" until then.
      - STATUS: **design DONE** → full plan recorded at `docs/gui_audit/chain_solve_b_plan.md`. Boundary: `solve_chained` = preflop + flop ONLY (no turn/river), CLASS-level (not combo), and the flop solve can HANG (Tier-A MUST add an `exceeds_tree_budget` guard). **Tier A build (hole-card entry → preflop walkthrough → guarded flop → termination) is NEXT**; turn/river = Tier B scaffold ("pending engine").
- [x] **Auto range generation — BUILT** *(user 2026-05-30)* — `ui/views/_auto_range.py` derives ranges from the preflop blueprint (same lookup/interpolation as the Preflop Chart). "Auto-fill" dropdown + Apply in Spot Input fills the active player's range for the spot's depth. 3 standard lines: BTN open (748 combos @100bb), BB 3-bet vs open (318), BB flat-call vs open (1008). 11 tests pass. (Live-apply repaint uses the `ui.timer` path → shares the real-browser verification status of the refresh fix.)
      - Distinct from what EXISTS: manual type/click input; save/load YOUR ranges (`range-preset` dropdown, e.g. `my_btn_open`); canned example-spot ranges.
      - PARTIALLY covered already: **chain solve auto-derives the postflop continuation ranges from the preflop solve** (`ContinuationRanges`, chained.py:166/226) — so the walkthrough's postflop ranges are auto-generated. The GAP is the STANDALONE "fill this spot's range from the blueprint/position" convenience on the Solver tab.
- [ ] Visual dress-up pass — matrix color gradients, spacing, less "debug grid" feel (non-engine-gated parts only)
- [ ] **Qualitative validation: persona walkthroughs THROUGH the GUI** *(user 2026-05-30; not-now, keep in back of mind)* — take each persona's task from the plan's Part B, run it through the LIVE GUI, and confirm it's actually COMPUTABLE end-to-end. Scope = **single solve per persona only** (NOT research-grade multi-solve chains). `[E]` postflop-solve personas gated on the engine; preflop/light personas testable now.

## DEFERRED — ENGINE-GATED (do WITH the engine; don't build twice)
- **⚙️ ENGINE UPDATE 2026-05-30:** ALL v1.11 engine work is now MERGED to `main` (**f69ec29**) — rayon (`dae26fd`) → suit-iso+IE (`9b33e3e`) → preflop restricted-EV (`e331d62`) → **bet-size menu** (`f69ec29`: per-street menus + lean raise multipliers + flop-no-donk). 141 cargo + full pytest green. Implications for the GUI: (1) **RvR flops are now TRACTABLE** on main's fast engine → the postflop-solve items unblock once merged; (2) the **bet-size menu is now CONCRETE** (per-street + lean 3× raises + flop-no-donk; legacy flat menu kept) → the UI's bet-size config should align to it on merge (the deferred bet-size-UI item is now buildable against a real spec); (3) main's **fast Rust binding STILL lacks UI progress/cancel hooks** (`lib.rs:232`) — so the merge needs the fast binding to gain hooks OR the UI to degrade (indeterminate spinner + coarse cancel). GUI branch is **14 commits behind main**. The merge is now fully engine-ready — it's the gated step (user's call).
- [E] Rich strategy/action display — raise + multiple bet sizes + mixed frequencies (comes with the real RvR engine; current fold/call view is the Concrete/river-degenerate reality)
- [E] Bet-size menu UI + street/tree structure — the engine defines these; UI already reads bet sizes from config so it absorbs the final menu
- [E] RvR-flop tractability — currently hangs in tree-build on this branch's engine
- [E] **MERGE to `main` + private mirror** — gated on engine reconciliation (main's fast IE/vector/suit-iso engine + this branch's UI progress/cancel hooks). *(user gates the merge)*
- [E] **`SolveTooLargeError` guard + 2 pre-existing pr24b test failures.** The guard (`state.py:~1280`, fires for concrete-postflop exceeding the tree budget) is the user-REJECTED "tree too large" patchup ([[feedback_no_patchups]]) — it's still in the branch (present at base `6d5fbdc`, NOT added this session). It pre-empts `test_ui_pr24b.py::test_locked_strategies_threads_through_solve_runner_start` + `::test_force_tree_solve_flag_threads_through_runner` (they exercise large concrete-postflop spots → `SolveTooLargeError`). These 2 failures are **PRE-EXISTING** (fail at `6d5fbdc`), NOT a regression from this session. RESOLUTION = remove the guard once the **fast-engine merge** makes flops tractable (removing it on the old-engine branch now → hangs). Until then the guard stays + these 2 tests fail.

## FOLLOW-UPS / LATENT (documented; fix when convenient)
- [ ] Spot-model SPR gap — `_spot_from_config`/`Spot.to_hunl_config()` drop a postflop subgame's pot+contributions, so a HAND-BUILT (not fixture-loaded) postflop spot misrepresents SPR. P2 sidesteps it for solved-config tree/matrix only.
- [x] Test-isolation flake FIXED — `test_ui_pr24a.py`'s last test left a postflop board in the shared singleton + `test_ui_smoke.py`'s fixture didn't reset it → board-picker inherited a 3-card board → 5-card RIVER. Fix: `reset_state_for_testing()` in smoke's `isolated_state_dir` fixture (mirrors other files). Suite now **order-independent green** (153 passed across natural / reversed / smoke-first / smoke-last; only the 2 pre-existing pr24b fail).
- [?] **POSTFLOP TIER / CONVERGENCE — likely root of the user's "results just say fold/call" complaint.** UI tiers (run_panel.py): Draft=200 / **Standard=500 (default)** / Tight=1000 / Library=2000 iters — set by MEASURED *exploitability* (Q3 LOCKED). BUT [[project_postflop_convergence]] (backend finding): postflop per-hand EVs are DEGENERATE at 100-150 iters (dominated hands pinned 0/>pot), AA/KK only 0.001→0.267 by 1000it, river baseline=100k. So **low exploitability ≠ converged per-hand EVs** → at the default Standard=500 the combo-inspector EVs/strategies are under-converged/degenerate (what the user SAW). RECOMMENDATION (product + backend, NOT a unilateral change since tiers are locked/measured): once on main's fast engine, **raise the postflop default tier** (or split exploitability-tier vs EV-convergence) so per-hand EVs are trustworthy; balance vs Marcus's <30s tolerance. Surface to user.
- [ ] Open-chart `AA` cell read `C36` once (looks off for a standard RFI) — blueprint-data/projection; verify with engine/blueprint review.

## IDEAS / TO-ADD
- _(append new items here as they surface)_
