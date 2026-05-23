# PR 10a audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** `pr-10a-ui-mock-first`
**Integration tip:** `9f09d49` (v0.5.2, post-PR-4.5)
**Diff size:** 12 ui/ files (5,463 LOC) + `tests/test_ui_smoke.py` (792 LOC) + edits to `README.md`, `poker_solver/cli.py`, `pyproject.toml`. Total ~6,255 new LOC.

**Test status:** Not run inside the audit env (nicegui not installed). Static review only. Several smoke tests rely on markers / module-level constants that DO NOT EXIST in the implementation as committed (see Must-fix #2 and Should-fix #1, #2) — those tests will fail on first execution against the current branch.

---

## Must-fix

### 1. Mock signature drift breaks PR 10b's one-line swap (HIGH-PROB per `audit_preprep_10a.md` §1.5; full diagnosis in `docs/pr10_prep/mock_signature_drift.md`)

**Files:** `ui/mock_solver.py:334-347`, `ui/state.py:663-672`
**Spec violated:** `pr10a_spec.md` §7.1 ("byte-identical first 8 parameters" claim)

The mock's signature is NOT byte-identical to the real `solve_hunl_postflop` (`poker_solver/hunl_solver.py:85-95`):

| Slot | Real (`hunl_solver.py:85-95`) | Mock (`mock_solver.py:334-347`) | Drift |
|------|-------------------------------|---------------------------------|-------|
| pos #2 | `abstraction: AbstractionTables \| None` | `iterations: int` | **slot collision** |
| pos #3 | `iterations: int` | (kwarg-only after `*`) | order skew |
| pos #4 | `target_exploitability: float \| None` | (kwarg-only after `*`) | order skew |
| pos #5 | `memory_budget_gb: float` | (kwarg-only after `*`) | order skew |
| kwarg | (no `on_progress` exists) | `on_progress: Callable[...]` | **mock-only param** |

After the PR 10b swap (`ui/state.py:619-625`), `state.py:663-672` calls
```python
_solve_postflop_impl(config, iterations, log_every=..., memory_budget_gb=..., target_exploitability=..., seed=..., dcfr_kwargs=..., on_progress=on_progress, ...)
```
Against the real solver this:
- passes `iterations` (an int) in the `abstraction` slot (silent type error → `_validate_abstraction()` will explode);
- passes `on_progress=on_progress` as an unknown kwarg → `TypeError: solve_hunl_postflop() got an unexpected keyword argument 'on_progress'`.

The mock-first design's central promise (one-line import swap) is **violated by the code as committed**. Recommended remediation: Option A in `mock_signature_drift.md` (patch mock to match real; move to polling-based progress). ~210 LOC, ~5-6 hr.

Smoke-test 9 (`tests/test_ui_smoke.py:296`) passes `mock_solve(config, iterations=100, mock_latency_ms=0)` keyword-only so the drift doesn't surface until 10b — but smoke 10 (`tests/test_ui_smoke.py:330-336`) and the worker call all flow through the import-swap site and will all break in one line of `pr10b_spec.md` execution. **This is the most consequential finding in the audit.**

### 2. Library header button marker mismatch — smoke 8 cannot find the button

**Files:** `ui/app.py:114-118`, `tests/test_ui_smoke.py:258`
**Spec violated:** `pr10a_spec.md` §10.1 item 8

`ui/app.py:118` emits `.mark("library-button")` in the header. The matching smoke test (`test_ui_smoke.py:258`) calls `user.find(marker="library-header-button")`. `ui/views/library_browser.py:124` defines `render_header_button` that DOES mark `library-header-button`, but `ui/app.py` never calls it — instead it builds its own button at line 114-118 with the wrong marker. Smoke test 8 will get an empty `.elements` list and fail.

Fix: rename `ui/app.py:118` marker to `library-header-button` OR call `library_browser.render_header_button(state, dialog)` from app.py instead of the inline button.

### 3. Board-picker marker uses card-int but smoke 2 expects card-string

**Files:** `ui/views/spot_input.py:133`, `tests/test_ui_smoke.py:107-109`
**Spec violated:** `pr10a_spec.md` §10.1 item 2

`spot_input.py:133` renders `.mark(f"board-picker-cell-{card_int}")` (e.g., `board-picker-cell-50` for some integer card encoding). Smoke 2 (`test_ui_smoke.py:107-109`) calls `user.find(marker="board-picker-cell-Kh")` (string form). `Kh` will never resolve to whatever `card_int` is. Test cannot click any board card → board never gets 3 cards → assertion at `:113` (`len(state.current_spot.board) == 3`) fails.

Fix: change `spot_input.py:133` to use canonical card-string (e.g., `f"board-picker-cell-{rank_char}{suit_char}"`) OR have the spec/test agree on integer encoding. The string form is the more readable choice and matches the test's intent.

---

## Should-fix

### 1. Missing `cell_rgb_for_action_freqs` helper — smoke 14 fails

**File expected at:** `ui/views/range_matrix.py` (per `tests/test_ui_smoke.py:443-447`)

Smoke 14 (`test_range_matrix_color_blend_matches_pio_convention`) explicitly checks
```python
getattr(range_matrix, "cell_rgb_for_action_freqs", None)
```
and asserts non-None with a hard error message ("must expose cell_rgb_for_action_freqs..."). The committed `range_matrix.py` exposes `cell_color(summary: CellSummary)` (line 396-411) instead, returning a CSS string. Smoke 14 will fail at line 444. Fix: add a thin adapter `cell_rgb_for_action_freqs(fold, call, raise_)` that returns a `(r, g, b)` tuple from the same blend formula.

Note: the blend formula in `cell_color` (line 408-410: r = fold*220 + call*220 + raise_*40) does NOT match the smoke 14 expected formula (r = fold*255 + call*255 + raise_*0). Smoke 14 asserts a pure-fold cell is `(255, 0, 0) ± 2`; the committed code returns `(220, 40, 40)` — off by 35 / 40. The smoke test and impl agree on the principle (Pio RYG additive blend) but disagree on the anchor values. Spec §7.3 lists the smoke-test anchors; impl is the drifter.

### 2. Missing `DISPLAY_PALETTE` / `INPUT_PALETTE` module constants — smoke 16 fails

**File expected at:** `ui/views/range_matrix.py`, `ui/views/spot_input.py`
**Test:** `tests/test_ui_smoke.py:509-538`

Smoke 16 (`test_input_matrix_palette_disjoint_from_display_palette`) does `getattr(display_matrix, "DISPLAY_PALETTE", None) or getattr(display_matrix, "STRATEGY_PALETTE", None)` and asserts non-None; neither symbol is exported by `range_matrix.py`. Same for `INPUT_PALETTE` / `RANGE_INPUT_PALETTE` in `spot_input.py`. Both halves of the test will fail with the test's own AssertionError ("must expose DISPLAY_PALETTE..."). Fix: expose two module-level palette constants (the existing per-cell formula can be derived from a 3-tuple constant in each module).

### 3. Smoke 14 / 15 / 17 / 18 / 19 / 20 depend on markers not present in views

**Files:** `ui/views/range_matrix.py`, `ui/views/run_panel.py`, `ui/views/spot_input.py`

Static grep confirms the following test-required markers are **not** present anywhere in the committed `ui/` tree:
- `matrix-cell-AKs` (used by smoke 15, line 483) — range_matrix emits `matrix-cell-{cls}` markers via the `data-marker` props string at line 844, but as a comma-separated tag list inside `props("data-marker=matrix-cell,matrix-cell-AKs")`. NiceGUI's `User.find(marker=...)` requires a single mark; this multi-tag pattern won't match. Verify with a quick smoke run before claiming green.
- `blocker-overlay` CSS class (smoke 15 line 489) — no occurrence in `range_matrix.py`.
- `expl-chart-linear-toggle` (smoke 17 line 555) — `run_panel.py` builds an unmarked `ui.checkbox("Log scale", ...)` at line 221-224.
- `oom-reduce-bet-sizes-button` (smoke 18 line 606) — no OOM-failure-mode notification renderer exists.
- `pushfold-switch-button` (smoke 19 line 626) — no push/fold toast button exists.
- `progress-eta` (smoke 20 line 691) — `run_panel.py` does compute an ETA (line 469) but never marks the label.
- `compute_eta` method on `SolveRunner` (smoke 20 line 656) — `SolveRunner` doesn't expose this.

These are all UX-grounded test additions (spec §10.3 + §10.4) that need view-side wiring to pass. Either add the markers + handlers, or mark these tests `@pytest.mark.xfail` with a PR 10b/11 follow-up. **Total: 7 tests likely failing.**

### 4. `_open_library_stub` builds a NEW dialog when `render_header_button` is absent

**File:** `ui/app.py:243-267`

`_open_library_stub` lazily tries `library_browser.show_modal` or `render`. `render` is the right export (lines 252-261), but `app.py:258-261` re-wraps its return value in *another* `ui.dialog()`. `library_browser.render` (line 74) already returns a `ui.dialog().mark("library-dialog")`. Result: nested dialogs. Smoke 8 may still pass (`library-dialog` mark is present somewhere) but the UX is broken: the Close button at app.py:260 closes the outer wrapper, leaving the inner one open.

Fix: in `_open_library_stub`, `library_browser.render(get_state()).open()` directly; drop the outer `ui.dialog(): ui.card()` wrapper.

### 5. Mock fixtures location drift

**Files:** `ui/mock_solver_fixtures.py` (656 LOC) — fixtures live HERE, not at `tests/data/mock_fixtures/*.json` per audit prompt §3 line 45

The 12 fixtures are hand-coded as Python builders in `ui/mock_solver_fixtures.py:611` (`_FIXTURE_BUILDERS`), exposed via `fixture_ids()`, `build_fixture()`. Audit-prompt expectation of `tests/data/mock_fixtures/*.json` was wrong; the impl uses Python builders which is fine (more flexible for `HUNLConfig` construction). Spec lines 614, 657-670 talk about 12 fixtures without prescribing JSON. **Looks-good** in retrospect — the prompt's path expectation drifted, not the impl. Flagged here for spec-edit follow-up if JSON form is wanted.

### 6. MDF/blocker spot-checks not performed

The audit prompt asks for MDF sanity (focus area 6) on river bluff frequencies. I read `ui/mock_solver_fixtures.py:285-280` (river fixture at line 285) and the fixture-builder functions are too dense to verify MDF compliance via static read — they construct strategy dicts mechanically. Suggested follow-up: add a `tests/test_mock_fixture_mdf.py` that loads each river/turn fixture, sums bluff frequency vs value frequency per bet-size, and asserts `bluff_freq <= bet/(1+bet) * value_freq`. Mark `@pytest.mark.ui` to inherit the skip behavior.

### 7. ETA polling uses 50ms sleep slices inside `_stream_progress` — stop latency upper bound = 50ms not "1 iter"

**File:** `ui/mock_solver.py:120-128`

The stop-button-latency spec (§11 #3) says halt within ONE iter. Mock impl sleeps in 50ms slices and checks `_CANCEL_FLAG` between slices. For `mock_latency_ms=30_000` and `_DEFAULT_SNAPSHOTS=20`, per-snapshot wall is 1500ms, sliced into 30 × 50ms checks — stop latency upper bound is ~50ms (well under 1 snapshot). **Verdict: passes — but the spec text "within one iteration" is ambiguous; better wording would be "within one snapshot interval (≤50ms in practice)".** Should-fix is spec-side, not code-side.

---

## Nice-to-fix

- `ui/app.py:78-102` mock banner is dismissed by hiding the row inline (`.visible = False`). A page refresh after dismissal will rebuild it (because `mock_banner_dismissed` IS persisted at line 93-94). UX OK; minor inconsistency between "dismiss inline" and "persist for next page load" but they don't conflict.
- `ui/app.py:188-202` `_tick` swallows all exceptions per-handler with `noqa: BLE001`. Defensible (timer must not die) but logs to a logger that may not be configured by NiceGUI's startup; consider routing to NiceGUI's own logger so users see why the chart isn't updating.
- `ui/state.py:266-323` `RangeWithFreqs` accesses `self.base_range._combo_set` (line 277, 288) — leaks `Range`'s private attribute. Should use the public `combos` property or `in` operator on a `RangeView` instead. Cosmetic-only because `_combo_set` is the actual storage; a `Range.__contains__` overload would clean this up without engine changes.
- `ui/mock_solver.py:434` `mock_failure_mode == "cancelled"` simulates cancellation by `cancel_at_fraction=0.4`. This is correctly returning a partial — but doesn't set `_CANCEL_FLAG`, so the smoke 5 test path (which DOES set `_CANCEL_FLAG`) and this mode are different code paths. Worth a comment noting the distinction.

---

## Looks good (explicit confirmation of audit focus areas)

**1. UI threading correctness (worker thread + `ui.timer` polling).** Confirmed clean. `ui/state.py:524-541` spawns a `threading.Thread(target=self._worker, daemon=True)` — not `asyncio.to_thread`. `ui/app.py:202` registers `ui.timer(0.5, _tick)` and the tick handler reads `state.runner.*` via `run_panel.refresh_progress(state)`. The worker's `on_progress` closure at `ui/state.py:632-654` modifies `self.iteration` + `self.expl_history` under `self._lock` — no NiceGUI calls from worker context. The mock at `ui/mock_solver.py:154` only calls the caller-supplied `on_progress` callback (not any `ui.*` APIs). **Sub-probe (a) clean; (b) clean; (c) clean — 50ms stop latency in mock loop.**

**2. Stop button cancellation flag.** `ui/state.py:564-581` `stop()` sets both `self._stop_event` and (lazily-imported) `ui.mock_solver._CANCEL_FLAG`. `ui/mock_solver.py:115-129` checks `_CANCEL_FLAG.is_set()` per-snapshot AND per 50ms sleep slice. Smoke 5 + extra `test_cancel_flag_halts_mock_solve` cover this.

**3. Matrix aggregator off-by-one.** `ui/state.py:118-141` `enumerate_hand_classes()` returns 169 entries with the canonical convention (row 0=A, diagonal=pairs, above-diagonal=suited, below=offsuit). `ui/state.py:144-186` `enumerate_combos` returns 6/4/12 combos per pair/suited/offsuit. `ui/state.py:189-198` `classify_combo` is the inverse. Smoke 7 (`test_combo_to_cell_mapping_no_off_by_one`, line 203) asserts the property test + total combo count == 1326. Static review: passes.

**4. State.json atomicity.** `ui/state.py:826-836` `_maybe_flush_state` writes to `.json.tmp`, calls `fh.flush() + os.fsync(fh.fileno())`, then `tmp.replace(_STATE_FILE)`. Debounced via `_STATE_DEBOUNCE_SEC = 0.5` (line 730) + a save lock. Corrupt-load fallback at `ui/state.py:775-782`: on JSON decode failure, backs up to `state.json.bak` then proceeds with defaults. **Sub-probes (a), (b), (c) all clean.**

**5. Mock interface contract.** **NOT CLEAN — see Must-fix #1.** Drift on `abstraction` position, `target_exploitability` / `memory_budget_gb` kwarg-vs-positional, and `on_progress` mock-only param. `RangeWithFreqs` (`ui/state.py:246-323`) correctly WRAPS `poker_solver.Range` — `git diff integration -- poker_solver/range.py` is empty per direct check.

**6. 12 mock fixture spots.** `ui/mock_solver_fixtures.py` exposes 12 builders via `_FIXTURE_BUILDERS` (line 611-625). Names match spec exactly per `test_all_12_fixtures_load` (line 708, expected IDs at line 717-730). Smoke 15 expects the `flop_k72r_100bb` fixture to surface a `blocker-overlay` class on AKs cell — see Should-fix #3 for the class-missing finding. MDF math not statically verifiable — see Should-fix #6.

**7. Seven design Q-locks.** Q1: `ui/app.py:123-183` two-pane row + three-expansion right sidebar — confirmed. Q2: `ui/views/range_matrix.py:414-436` `_cell_tag` shows class label + 2-letter+pct, tooltip at line 439-452 — confirmed. Q3: `ui/views/run_panel.py:55` `_DEFAULT_ITERATIONS = 1000` — confirmed. Q4: `ui/state.py:351` `bet_sizes_checked: tuple[float, ...] = (0.33, 0.75, 1.0)` + `include_all_in: bool = True` (line 346) → 4-of-6 checked — confirmed. Q5: `ui/app.py:130-133` combo-inspector slot placed BELOW matrix in same column — confirmed. Q6: `ui/views/tree_browser.py:60` `_DEFAULT_MIN_REACH: float = 0.01` — confirmed. Q7: `ui/app.py:78-102` yellow banner with `bg-yellow-200` + dismiss button — confirmed.

**8. NiceGUI dependency as optional extra.** `pyproject.toml:21-23` declares `[project.optional-dependencies] ui = ["nicegui>=2.0,<3.0"]`. NOT in base `dependencies`. `pyproject.toml:40-44` declares the `ui` pytest marker. Confirmed.

**9. CLI `ui` subcommand.** `poker_solver/cli.py:322-340` registers `_cmd_ui`; the function `from ui.app import launch` is inside the function body (lazy import). On `ImportError`, prints the required string + returns `2`. Subcommand registered at `cli.py:527`. Confirmed.

**10. Browser-served only.** `ui/app.py:373-383` calls `ui.run(host=host, port=try_port, dark=dark, reload=False, show=True, title="poker-solver")`. `native=True` is NOT used. Default `host="127.0.0.1"` (line 350). No `pywebview` import anywhere. Confirmed.

**11. `RangeWithFreqs` wraps Range.** `ui/state.py:246-323` defines `RangeWithFreqs` as a wrapping dataclass over `base_range: Range` + `frequencies: dict[Combo, float]`. `git diff integration -- poker_solver/range.py` is empty. Confirmed (minor private-attr access flagged as nice-to-fix).

**12. No new tests in `poker_solver/` test surface.** `git status` shows `tests/test_ui_smoke.py` as the only new test. No modifications to existing PR 1-9 test files. Confirmed.

**13. Library viewer stub.** `ui/views/library_browser.py:43-55` defines `_STUB_ROWS` with three faked entries. Load + Delete buttons disabled (`.props("disable")`, line 104-106). Stub row click emits `ui.notify("PR 11 — load from disk is not yet wired", ...)` (line 95-99). **However: marker drift on library-header-button — see Must-fix #2.**

**14. Smoke test count.** `tests/test_ui_smoke.py` declares 22 test functions across 4 sections (8 + 5 + 4 + 3 + 2 "extra"). Spec §10 prescribes 8 smoke + extra coverage; impl exceeds the minimum. Each test marked `@pytest.mark.ui` via `pytestmark` (line 36); `pytest.importorskip("nicegui")` at line 31 ensures clean skip. Confirmed (test failures flagged in Must-fix and Should-fix items don't bear on count).

**15. `ui/` outside `poker_solver/`.** `ls /Users/ashen/Desktop/poker_solver/` shows `ui/` as a sibling of `poker_solver/`, `crates/`, `tests/`. Confirmed.

---

## Spec coverage gaps (missing tests)

- **§6.4 push/fold dispatch at <=15BB:** `ui/app.py:294-302` and `ui/views/spot_input.py:373-380` show the warning toast — but neither emits the `pushfold-switch-button` marker the smoke 19 test expects. Suggested: add the button to the warning toast, wire it to switch the view to a push/fold mode (or no-op for PR 10a with a "PR 11" toast).
- **§6.5 OOM remediation:** `ui/state.py:680-686` captures the MemoryError into `runner.error` + `runner.partial_report`, but no view surfaces the "Reduce bet sizes" button. Suggested: add the surface to `run_panel._show_error` (line 506).
- **§7.3 chart log-Y default + linear toggle:** the `Log scale` checkbox at `run_panel.py:221-224` doesn't carry the `expl-chart-linear-toggle` marker. One-line fix.
- **§4.4 blocker overlay:** smoke 15 asks for a `blocker-overlay` CSS class on blocked cells. `range_matrix._cell_tag` returns `"BLK"` (line 423), `cell_color` returns the faded-grey sentinel (line 407), but no element-level class signaling "blocker". Add a CSS class via `.classes("blocker-overlay")` when `summary.blocked`.

---

## License compliance

- **Project license:** MIT (`pyproject.toml:11`, `LICENSE` file).
- **NiceGUI:** MIT — declared as an OPTIONAL extra (`pyproject.toml:21-23`); not bundled.
- **Other new deps:** none beyond `nicegui`. `numpy` already in base deps. `psutil` already in base deps via PR 5.
- **License headers in new files:** This project doesn't use per-file SPDX headers (engine files like `poker_solver/range.py` have none either). `ui/mock_solver.py:26` and `ui/mock_solver_fixtures.py:20` carry "License posture: no code copied from references/code/" comments. Other ui files do not — consistent with project convention.
- **No code from competitor UIs:** mock fixtures are hand-crafted (per `ui/mock_solver_fixtures.py` docstring); RYG color convention is widely used in poker software (not copyrightable expression).
- **Verdict:** clean.

---

## Overall verdict

**READY for commit AFTER must-fix items resolved.**

The architecture is sound: threading, atomicity, Q-locks, package placement, dependency declaration, CLI surface — all clean. But three concrete blockers prevent commit-as-is:

1. **Mock signature drift (Must-fix #1)** — the central design promise of "one-line PR 10b swap" is FALSE for the code as committed; recommended Option A patch is ~210 LOC / 5-6 hr (separate followup commit on the same branch, per `mock_signature_drift.md` §5).
2. **Library-button marker drift (Must-fix #2)** — smoke 8 will fail; one-line fix.
3. **Board-picker marker uses card-int (Must-fix #3)** — smoke 2 will fail; one-line fix.

The should-fix items (smoke 14/15/16/17/18/19/20 marker/constant drift, ~7 tests failing) are recoverable but represent real spec gaps. Recommendation: tackle Must-fix #1 in a single follow-up commit on this branch; tackle Must-fix #2-3 + Should-fix #1-3 in a "view-marker conformance" commit; mark smoke 17-20 `xfail` with explicit PR 11 follow-up if the OOM remediation + push/fold dispatch views are out of scope for PR 10a. After both follow-up commits, the audit verdict transitions to READY.
