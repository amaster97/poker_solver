# PR 10a implementation challenges — pre-stage thought experiment

**Status:** Pre-fire reference. Read this BEFORE Agents A/B/C dispatch.
**Date:** 2026-05-22
**Scope:** Enumerate the 7 specific implementation hazards Agents A/B/C will hit
during PR 10a. Per-challenge: spec anchor, expected difficulty (1-5),
recommended approach, fallback. Then cross-challenge dependencies, agent
order-of-attack, and the 2-3 challenges most likely to trip a NOT-READY audit.

Read-only. No source files touched. Companion to `audit_preprep_10a.md`.

---

## 1. Per-challenge analysis

### Challenge 1: NiceGUI 2.x async/threading mismatch

**Spec lookup:** `pr10a_spec.md` §7.5 (cancellation contract; `_CANCEL_FLAG` as
`threading.Event`); `audit_preprep_10a.md` §1.1 (HIGH probability must-fix).
NiceGUI runs on asyncio; solver work is synchronous CPU-bound; bridge is a
worker thread + `ui.timer(0.5, update_ui)` polling.

**Difficulty: 5/5.** Highest-risk surface in PR 10a. Three traps stacked:
(a) Agent A may reach for `asyncio.to_thread` (looks idiomatic, breaks
under NumPy GIL release); (b) worker thread accidentally touches `ui.*`
primitive (silent "element not bound to client" race); (c) stop-button
latency exceeds one mock-iteration if `_CANCEL_FLAG` is checked at the
wrong scope.

**Recommended approach:** `threading.Thread` for the solver worker.
Worker writes ONLY to a shared `SolveRunner` dataclass — no `ui.*` calls.
A single `ui.timer(0.5, update_ui)` on the main asyncio loop reads
`SolveRunner` and re-renders matrix / chart / status. Cancel flag checked
once per snapshot inside `mock_solve()` — same flag PR 10b reuses verbatim
(spec §7.5). Worker exceptions captured in `SolveRunner.error: Exception |
None`, surfaced by the timer.

**Fallback:** If `ui.timer` polling causes jank at 500 ms, drop to 250 ms
and coalesce matrix re-renders. If GIL-blocking is visible (timer skips
firing), switch matrix re-render from re-mount to in-place style mutation
via `ui.element.update()`.

### Challenge 2: `state.json` atomicity under concurrent UI events

**Spec lookup:** `pr10a_spec.md` §2.4 ("Splitter resizability: Yes, persisted
in `~/.poker_solver_ui/state.json`"), §12 risk 6 (onboarding modal coupling);
`audit_preprep_10a.md` §1.2 (MEDIUM probability should-fix). State file
captures panel widths, theme override, recent spots, onboarding-completed
flag. UI events (splitter drag, theme toggle, spot edit) all mutate.

**Difficulty: 2/5.** Pure infrastructure, well-trodden pattern. Risk is
laziness — direct `open(path, 'w').write(json.dumps(...))` is the obvious-
but-wrong implementation.

**Recommended approach:** `tempfile.NamedTemporaryFile(dir=parent)` →
`json.dump(...)` → `f.flush()` + `os.fsync(f.fileno())` → `os.rename(tmp,
target)`. Wrap in `_atomic_write_json(path, data)` helper in
`ui/state.py`. Debounce saves via a single `ui.timer(0.5, _flush_if_dirty)`
checking a `_dirty: bool` flag. Corrupt-load path: on JSONDecodeError, copy
to `state.json.bak`, log a warning toast, fall back to defaults.

**Fallback:** If `os.rename` semantics flake on Windows (per NiceGUI
desktop install path), use `os.replace` (cross-platform atomic). If the
debounce timer is awkward in NiceGUI's per-client context, attach the
dirty flag to the global `app.storage.general` instead of per-client.

### Challenge 3: Mock fidelity calibration (12 fixture spots)

**Spec lookup:** `pr10a_spec.md` §7.4 (12 fixtures with poker-eye-test
acceptance criteria); `audit_preprep_10a.md` §1.3 (MEDIUM should-fix; MDF
caps, polarization, blocker effects). Hand-crafted by Agent C — must look
solver-shaped under inspection.

**Difficulty: 4/5.** Bulk of Agent C's work. Trap is that "realistic" is
under-specified: MDF caps are mechanical (bluff_freq <= B/(1+B)), but
polarization curves and blocker effects need poker-judgment calls per spot.
12 spots × 1326 combos × 5-6 actions = ~80K freq values to fabricate.

**Recommended approach:** Procedural generation per fixture: assign each
combo a `(class, equity_bucket)` label, map bucket → action-distribution
template, jitter ±5% for realism, enforce MDF cap as a post-hoc clamp.
Three templates: dry-flop linear, wet-flop balanced, river polarized.
Six fixtures share each template; per-spot blocker overrides applied last
(slashed-diagonal cells). Use the PR 5 `solve_hunl_postflop` on the
`river_tiny_subgame` spot ONCE during fixture authoring (offline, in a
notebook) to seed realistic distributions for the river-class fixtures —
not at runtime (would defeat the mock).

**Fallback:** If procedural templates look obviously fake on eyeball, run
the real PR 5 solver on 3-4 representative spots at low iterations (~200)
offline and embed the output as a frozen JSON blob. Caveat: tags the
fixture as "pre-computed" in metadata so PR 10b smoke-test reviewers know
they're regenerable.

### Challenge 4: Range matrix click semantics (13×13 + combo cardinality)

**Spec lookup:** `pr10a_spec.md` §4.2 (range input matrix: cycle 1.0 →
0.5 → 0.25 → 0.0, shift-click for freq slider, live string preview),
§4.4 (display matrix: hover-tooltip + click → combo inspector strip),
test #7 `test_combo_to_cell_mapping_no_off_by_one`. Cell layout: pairs
on diagonal (13 cells, 6 combos each), suited above-diagonal (78 cells,
4 combos each), offsuit below-diagonal (78 cells, 12 combos each).
Total 1326 combos.

**Difficulty: 3/5.** Mechanical but high silent-corruption risk. Agent B
must get `(row, col)` ↔ `(rank_high, rank_low, suitedness)` mapping right
or every downstream rendering is silently wrong. Click semantics differ
between input matrix (paint mode, cycles freq) and display matrix
(inspects). Same widget shape, opposite interaction.

**Recommended approach:** Single source of truth in
`ui/views/range_matrix.py`: a `_combo_to_cell(combo) -> (row, col)` and
`_cell_to_combos(row, col) -> list[Combo]` pair, exercised by test #7.
Two `RangeMatrix` widget variants share the cell-coordinate code but
differ in `on_click` handler — input variant calls
`state.range_p0.cycle_freq(combo)`, display variant calls
`state.set_inspected_cell(row, col)`. Live string preview computed lazily
on `state.range_p0.changed` callback.

**Fallback:** If shift-click + freq slider feels fragile (NiceGUI shift-
modifier API quirks), simplify to right-click-opens-freq-slider in
PR 10a; ship full shift-click in PR 10b polish.

### Challenge 5: Cancellation propagation (Solve → Pause → Stop)

**Spec lookup:** `pr10a_spec.md` §6.2 (cancel preserves partial strategy;
non-destructive), §7.5 (`_CANCEL_FLAG` semantics — same flag as real
solver), §4.3 (three buttons: Solve / Pause / Stop, color-coded
green/yellow/red, status word reflects state). Test #5 asserts stop halts
within one simulated iteration.

**Difficulty: 3/5.** Conceptually simple, multi-state edge-case heavy.
Pause is the awkward middle state — solver thread sleeps but worker is
alive; resume must continue from same iter index. Stop is terminal but
must preserve partial result. Solve-after-stop with same config continues;
solve-after-stop with changed config starts fresh.

**Recommended approach:** `SolveRunner` exposes `start()` /
`pause()` / `resume()` / `stop()`. Two `threading.Event`s: `_cancel`
(terminal) and `_paused` (sleeps the worker loop via
`_paused.wait()`). Status enum: `idle / running / paused / stopped / done
/ error`. Resume = `_paused.clear()`. Re-solve detection: hash the
`HUNLConfig` before submit; if hash unchanged AND prior status ==
`stopped`, pass `resume_from_iter=prev_iter` to `mock_solve`; else fresh
solve.

**Fallback:** If pause/resume timing is bug-prone (worker missing the
wake-up edge), defer Pause to PR 10b and ship only Stop + Solve in PR 10a.
Spec §4.3 allows this — only Stop is strictly tested (test #5).

### Challenge 6: Library viewer stub vs PR 11 collision

**Spec lookup:** `pr10a_spec.md` §4.6 (library stub: list view, 3 faked
rows, Filter field, Load/Delete buttons, "PR 11: persistence not yet
wired" banner); test #8 `test_library_dialog_opens`; Adopted pattern #12
(resumable solves via on-disk checkpoint — PR 11 ships persistence).

**Difficulty: 2/5.** Stub is intentionally thin. Trap is over-engineering:
Agent C might wire faked rows to a JSON shim "to make PR 11 easier," which
actually constrains PR 11's persistence schema choices.

**Recommended approach:** Library dialog is a `ui.dialog` with three
hardcoded `LibraryEntry` namedtuples (NOT loaded from disk; NOT wired to
state.json). Buttons are no-op stubs that `ui.notify("PR 11 will wire
this", type='warning')`. Banner text is the spec's exact string. PR 11's
persistence schema is left fully open — Agent C ships zero opinions on
serialization format.

**Fallback:** If the test #8 dialog-opens assertion requires real
interaction, add the minimum: dialog opens via header button, three rows
render, both action buttons exist and are clickable (even if no-op).
That's the entire surface.

### Challenge 7: Dark mode + theme detection (Auto / Light / Dark)

**Spec lookup:** `pr10a_spec.md` §2.4 ("Default theme: Auto (system
preference) with manual override toggle"); Q7-locked banner separately.
Theme toggle in header right cluster (§4.1). Persisted in `state.json`.

**Difficulty: 2/5.** NiceGUI 2.x has `ui.dark_mode()` which can be set
True/False/None (None=auto). Trap is the three-way state: explicit-light,
explicit-dark, auto (follow `prefers-color-scheme`). Browser preference
detection is read-only from the page — server must defer to client JS.

**Recommended approach:** Three-state toggle in header (Light / Auto /
Dark). Persisted as `state.ui_prefs.theme: Literal['light', 'auto',
'dark']`. On page-load: if `'auto'`, attach a `ui.add_head_html` snippet
listening to `prefers-color-scheme` media query and dispatching a custom
event that flips `ui.dark_mode` server-side. Quasar's primary blue
palette adapts via CSS variables — no per-component dark overrides.

**Fallback:** If browser-detection plumbing is brittle, ship Light/Dark
two-state in PR 10a, defer Auto to PR 10b. Spec §2.4 lock will need a
note added; weakly-held lock per the principle table.

---

## 2. Cross-challenge dependencies

| Challenge | Depends on | Reason |
|---|---|---|
| 1 (Threading) | — | Foundational; nothing depends on it being late |
| 2 (state.json atomicity) | 7 (theme), 5 (last-spot) | State writes carry theme + cancellation state |
| 3 (Mock fidelity) | — | Independent of UI; Agent C in parallel |
| 4 (Matrix clicks) | 1 (state hookup) | Click handlers write to `SolveRunner.config` |
| 5 (Cancellation) | 1 (threading) | Same `threading.Event` pattern |
| 6 (Library stub) | — | Independent; smallest surface |
| 7 (Dark mode) | 2 (state.json) | Persistence depends on atomic-write helper |

**Graph shape:** 1 is the trunk (5 depends directly; 4 depends via state);
2 is a second trunk (7 depends; both feed acceptance criterion 11).
3 and 6 are independent leaves.

---

## 3. Order-of-attack recommendation for agents

**Wave 1 (parallel, start of PR 10a fan-out):**
- **Agent A:** Challenge 1 (threading scaffold + `SolveRunner` dataclass).
  This is the gating dependency for 4 + 5 + most of the UI.
- **Agent C:** Challenge 3 (mock fixtures) and Challenge 6 (library stub).
  Both are independent of the UI thread model; Agent C should not wait
  on Agent A.
- **Agent B:** Challenge 4 (matrix cell-coordinate code) — can start the
  mapping logic before A's `SolveRunner` lands; click handlers stub-call
  a placeholder that A wires later.

**Wave 2 (after Wave 1 lands):**
- **Agent A:** Challenge 2 (state.json atomicity) + Challenge 7 (dark mode)
  — both depend on threading scaffold landing first so save/load doesn't
  race with worker writes.
- **Agent A:** Challenge 5 (cancellation propagation) — extends the
  threading scaffold from Wave 1.

**Wave 3 (integration):**
- **Agent B:** Wire matrix click handlers to Agent A's `SolveRunner.config`
  setters.
- **All:** Smoke-test the 20 acceptance tests in `tests/test_ui_smoke.py`.

---

## 4. NOT-READY audit risks (top 2-3)

Per `audit_preprep_10a.md` §3, P(NOT-READY) ~15%. The risks below are the
specific paths to that outcome.

### Risk A — Challenge 1 (Threading) catastrophic: **highest NOT-READY risk**

If Agent A reaches for `asyncio.to_thread` AND lets the worker call
`ui.notify` directly, the audit's stop-button test will deadlock or
segfault. This is the single most-cited NOT-READY trigger in
`audit_preprep_10a.md` §3. Once threading model is wrong, every
subsequent UI test fails non-deterministically. Detection: audit greps
`ui/mock_solver.py` for any `ui.*` reference; if found → NOT-READY.

### Risk B — Challenge 3 (Mock fidelity) MDF violation: **secondary NOT-READY risk**

If Agent C's procedural templates emit any river fixture with bluff_freq
> MDF cap (e.g., bet75% with >43% bluff frequency on naked-air combos),
the audit's eye-test fails. Less catastrophic than Risk A — single
fixture re-author is a should-fix patch — but if multiple fixtures fail
the eye test, the audit will report "fixture suite not solver-shaped" and
that's a should-fix-cluster verdict potentially escalating to NOT-READY
if 4+ fixtures violate (`audit_preprep_10a.md` §1.3 last sentence).

### Risk C — Challenge 4 (Matrix off-by-one): **tertiary but silent**

If `_combo_to_cell` has a row/col swap on offsuit (below-diagonal)
combos, the entire range matrix is silently mirrored. Test #7 should
catch this — but if the test is written against the buggy mapping (Agent
B authoring both), it tautologically passes. Audit will manually verify
against a known fixture (`flop_k72r_100bb` — AKs in row 0, col 1;
AhKh blocked). If mirrored → must-fix that retroactively invalidates
all matrix screenshots in PR review; NOT-READY if the bug is structural
(both input AND display matrices wrong, not just one).

---

## 5. Summary

Top 3 hardest challenges (rank by difficulty): **1 (Threading, 5/5)**,
**3 (Mock fidelity, 4/5)**, **4 (Matrix clicks, 3/5)** tied with **5
(Cancellation, 3/5)**.

Top 2 NOT-READY audit risks: **Risk A (threading model wrong)** and
**Risk B (MDF violations on river fixtures)**.

Pre-stage mitigation already in place: `agent_a_prompt.md` threading
checklist, `audit_prompt.md` focus areas 1+2 + 3, `pr10a_spec.md`
§7.5 cancellation contract pinned to `threading.Event`. No additional
pre-patches recommended (per `audit_preprep_10a.md` §2). Fire when
PR 5 lands.
