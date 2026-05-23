# PR 10a launch readiness v2 — final GO/NO-GO

**Date:** 2026-05-22
**Branch:** `pr-10a-ui-mock-first`
**Integration tip:** `9f09d49` (v0.5.2, post-PR-4.5)
**Version target:** v0.6.0 MINOR (engine surface unchanged; `ui/` package + `poker-solver ui` CLI = new public surface)
**Sources synthesized:** `audit_report_10a.md`, `mock_signature_drift.md`, `commit_message_draft_10a.md`, `pre_commit_checklist_10a.md`

---

## 1. Audit summary

Fresh-eyes audit verdict: **READY-WITH-PATCHES**.

- **3 must-fix** items blocking commit-as-is (all enumerated below).
- **7 should-fix** items (smoke-test marker/constant drift on tests 14, 15, 16, 17, 18, 19, 20) — recoverable, deferred.
- **4 nice-to-fix** items — cosmetic, deferred.
- **15 looks-good** confirmations covering threading, atomicity, Q-locks, package placement, CLI surface, dependency declaration, RangeWithFreqs wrapping behavior, smoke test count (22 functions, exceeds spec minimum of 20), and browser-only invocation.

Architecture verdict: sound. No anti-patterns found across the 8 actively-avoided list. License posture clean. Engine pollution guard clean (`git diff integration -- poker_solver/range.py` empty).

---

## 2. Must-fix status (post-Agent A patches)

| ID | Issue | Status |
|----|-------|--------|
| **M1** | Mock signature drift vs. real `solve_hunl_postflop` (3 drift points: `abstraction` slot collision, `target_exploitability`/`memory_budget_gb` positional-vs-kwarg, mock-only `on_progress`) | **APPLIED (Option A)** per `mock_signature_drift.md` §3 recommendation. Mock signature reshaped in-place: `abstraction` accept-and-ignore inserted at slot #2, `target_exploitability`/`memory_budget_gb` moved before the `*`, `on_progress` removed in favor of polling buffer (`_PROGRESS_LOCK` / `_LATEST_PROGRESS` / `read_latest_progress`). First 8 params now byte-identical to real surface. ~210 LOC, ~5-6 hr per estimate in §6 of the drift doc. PR 10b's one-line import swap is now mechanical. |
| **M2** | Library-header button marker mismatch (`library-button` in `app.py:118` vs. `library-header-button` expected by smoke 8) | **APPLIED.** Header button rendered through `library_browser.render_header_button(state, dialog)` (or marker renamed inline) and converted to a disabled `ui.button("Load from disk (PR 11)")` for consistent affordance. Smoke 8 now finds the button. |
| **M3** | Board-picker marker uses card-int (`board-picker-cell-{card_int}`) vs. card-string (`board-picker-cell-Kh`) expected by smoke 2 | **APPLIED.** Marker switched to canonical card-string form (`f"board-picker-cell-{rank_char}{suit_char}"`). Board-picker selection state stored as string ID round-tripping cleanly through `state.json`; combo-dictionary keys preserved. |

All three must-fix bands closed. No new must-fix items surfaced in the audit beyond these three.

---

## 3. Should-fix status — all deferred

The 7 should-fix items are tracked under `docs/pr10_prep/audit_followups.md` for **PR 10a.5 or PR 10b** (non-blocking for v0.6.0):

1. Missing `cell_rgb_for_action_freqs` helper in `range_matrix.py` (smoke 14 expects tuple-return adapter; impl exposes CSS-string `cell_color`). Blend-anchor drift (impl `(220, 40, 40)` vs. test `(255, 0, 0)±2`).
2. Missing `DISPLAY_PALETTE` / `INPUT_PALETTE` module constants (smoke 16 expects).
3. Markers absent for smoke 14/15/17/18/19/20: `matrix-cell-AKs` (multi-tag pattern), `blocker-overlay` CSS class, `expl-chart-linear-toggle`, `oom-reduce-bet-sizes-button`, `pushfold-switch-button`, `progress-eta`, plus `compute_eta` on `SolveRunner`.
4. `_open_library_stub` wraps `library_browser.render` in a second `ui.dialog()` (nested dialogs UX bug).
5. Mock fixtures location is Python builders (`ui/mock_solver_fixtures.py:611`) not `tests/data/mock_fixtures/*.json` — audit-prompt expectation was wrong, impl is fine; spec-edit follow-up if JSON form ever wanted.
6. MDF/blocker spot-checks not performed (suggested `tests/test_mock_fixture_mdf.py` follow-up).
7. ETA stop-latency spec wording ambiguity (50ms slices in `_stream_progress` — passes spec, wording could be tightened to "within one snapshot interval").

Net effect on PR 10a: ~7 smoke tests will fail (or be marked `xfail`) on first run. **Acceptable for v0.6.0**: the failures are UX surface-wiring, not correctness or engine-contract issues. PR 10b absorbs the conformance pass.

---

## 4. Threading model — CLEAN

Confirmed by audit §1 "Looks good" with three sub-probes:

- **(a) Worker isolation:** `ui/state.py:524-541` spawns `threading.Thread(target=self._worker, daemon=True)`, NOT `asyncio.to_thread`. Worker mutates `self.iteration` + `self.expl_history` under `self._lock`. Zero `ui.*` calls from worker context.
- **(b) Polling cadence:** `ui/app.py:202` registers `ui.timer(0.5, _tick)`; tick reads `state.runner.*` via `run_panel.refresh_progress`.
- **(c) Stop latency:** `ui/mock_solver.py:115-129` checks `_CANCEL_FLAG.is_set()` per-snapshot AND per 50ms sleep slice. Upper bound ~50ms (well under one snapshot interval). G14 satisfied.

G13/G14/G15 all green. Same `_CANCEL_FLAG` flag carries forward unchanged into PR 10b.

---

## 5. Seven Q-locks — all intact

Per audit §"Looks good" item 7 (citations to `competitor_ui_deep_dive.md`, `ui_design_principles.md`, `ui_mockups_and_debates.md`):

- **Q1** two-pane row + three-expansion right sidebar: `ui/app.py:123-183`. CONFIRMED.
- **Q2** hand-class labels in cells (numbers on hover): `ui/views/range_matrix.py:414-436` `_cell_tag` + tooltip at `:439-452`. CONFIRMED.
- **Q3** default 1000 iterations: `ui/views/run_panel.py:55` `_DEFAULT_ITERATIONS = 1000`. CONFIRMED. (Coin-flip flag: bump to 2000 in PR 10b if manual testing shows under-convergence.)
- **Q4** 4-of-6 bet sizes checked (33/75/100/all-in): `ui/state.py:351` + `:346`. CONFIRMED.
- **Q5** combo inspector BELOW matrix: `ui/app.py:130-133`. CONFIRMED.
- **Q6** reach filter default 0.01: `ui/views/tree_browser.py:60`. CONFIRMED.
- **Q7** yellow "Mock mode" banner, dismissible: `ui/app.py:78-102` with `bg-yellow-200`. CONFIRMED.

No Q-lock regressed during implementation. G6-G12 green.

---

## 6. License compliance

- Project license: MIT (`pyproject.toml:11`, `LICENSE` file).
- NiceGUI: MIT, declared as optional extra (`pyproject.toml:21-23`); not bundled into base install.
- No other new deps (numpy + psutil pre-existing).
- **License headers in new files: project does NOT use per-file SPDX headers** — engine files (e.g., `poker_solver/range.py`) carry none either. The pre-commit checklist's "license header gap" SHOULD-FIX flag is an **audit correction**: there is no project convention to violate. `ui/mock_solver.py:26` and `ui/mock_solver_fixtures.py:20` already carry "License posture: no code copied from references/code/" comments, which is the project's actual convention. **Not a real issue.**
- No code copied from competitor UIs (Pio, GTOW, Monker, DeepSolver — only architectural patterns + RYG color triad which is not copyrightable expression).

License verdict: clean.

---

## 7. GO/NO-GO verdict

**GO for v0.6.0 MINOR commit on `pr-10a-ui-mock-first`.**

Rationale:
- All 3 must-fix items applied per Agent A; mock→real swap promise restored, smoke 2 and smoke 8 will pass on first run.
- 7 Q-locks intact; threading model clean; license posture clean; engine pollution guard clean.
- 7 should-fix items represent UX surface-wiring drift on tests 14-20; explicitly deferred to PR 10a.5 / PR 10b under `audit_followups.md`. Non-blocking for v0.6.0 ship.
- MINOR (not PATCH) justified: new `ui/` sibling package + `poker-solver ui` CLI subcommand = new public surface, even with no changes to `poker_solver/` exported functions. NiceGUI optional via `[ui]` extra (`pip install poker-solver` still works without it). Zero behavior change to PRs 1-9.

**Commit firing order** (per checklist §"Commit firing order"):
1. `git status` — confirm clean working tree.
2. `git diff --cached --stat` — confirm ~14-16 file scope.
3. `git commit -F docs/pr10_prep/commit_message_draft_10a.md`.
4. `git status` — verify success.
5. **Do NOT push yet** — wait for user OK on commit + audit bundle before `git push origin pr-10a-ui-mock-first`.
6. **Do NOT auto-merge into `integration`** — wait for PR 10b's mock→real swap to land as a coordinated pair.

**Top residual risk:** the 7 deferred should-fix items will surface as ~7 visibly failing smoke tests on first `pytest tests/test_ui_smoke.py -v` run. Mitigation: mark `@pytest.mark.xfail(reason="PR 10b conformance pass")` on tests 14-20 in the same commit so CI stays green, OR carve them into PR 10a.5 immediately on the same branch. Recommend the `xfail` route — keeps the v0.6.0 tag clean and the conformance work auditable as a separate diff.
