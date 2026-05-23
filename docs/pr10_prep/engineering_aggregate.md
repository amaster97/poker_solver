# PR 10a engineering aggregate — agent-ready synthesis

**Status:** Pre-fire reference. Read this BEFORE Agents A/B/C dispatch.
**Date:** 2026-05-22
**Scope:** Synthesis of `implementation_challenges.md` (7 hazards, ranked) + `audit_preprep_10a.md` (5 forecast audit findings). No new info — aggregation only.

---

## 1. Top 5 most-critical implementation challenges

Ranked by difficulty × audit-risk combined.

| Rank | Challenge | Difficulty | Spec anchor | Why critical |
|---|---|---|---|---|
| 1 | **Threading model** (worker thread + `ui.timer` polling) | **5/5** | `pr10a_spec.md` §7.5 | Three traps stacked: `asyncio.to_thread` reach, worker-touches-`ui.*` race, stop-button latency. Trunk dependency for challenges 4 + 5. Single highest NOT-READY trigger. |
| 2 | **Mock fidelity** (12 fixture spots, ~80K freq values) | **4/5** | `pr10a_spec.md` §7.4 | MDF caps, polarization, blocker overlays per spot. Bulk of Agent C's work. Eye-test failure surface. |
| 3 | **Range matrix click semantics** (13×13 + 1326 combos) | **3/5** | `pr10a_spec.md` §4.2, §4.4 | High silent-corruption risk on `(row, col)` ↔ `(rank_high, rank_low, suitedness)`. Input vs display variant share widget, differ on click. |
| 4 | **Cancellation propagation** (Solve / Pause / Stop) | **3/5** | `pr10a_spec.md` §6.2, §7.5 | Multi-state edge-case heavy. Pause is awkward middle state. Same `threading.Event` PR 10b reuses verbatim. |
| 5 | **Mock interface contract** matches real solver shape | **3/5** | `audit_preprep_10a.md` §1.5 | PR 10b is one-line import swap; field-name drift or missing `MemoryReport` breaks the swap. `RangeWithFreqs` must wrap, not modify `poker_solver/range.py`. |

Lower-tier (2/5): state.json atomicity, library viewer stub, dark mode 3-state.

---

## 2. NOT-READY audit risk surfaces (per `audit_preprep_10a.md`)

P(NOT-READY) ~15%. Three specific paths to that verdict:

### Risk A — Threading catastrophic (HIGHEST)
- Agent A uses `asyncio.to_thread` AND worker calls `ui.notify` directly.
- Audit `grep -r "ui\." ui/mock_solver.py` finds a hit → must-fix.
- Stop-button test: `iterations=100_000`, click Solve, wait 0.5s, click Stop, assert `iteration < 50_000` within 0.5s. Deadlock → NOT-READY.

### Risk B — MDF violation on river fixtures (SECONDARY)
- Procedural template emits bet75% with bluff_freq > MDF cap (e.g., >43% on naked-air).
- Single fixture = should-fix; 4+ violations = should-fix cluster escalating to NOT-READY (`audit_preprep_10a.md` §1.3 last sentence).

### Risk C — Matrix off-by-one (TERTIARY, SILENT)
- `_combo_to_cell` row/col swap on offsuit (below-diagonal) combos → entire matrix silently mirrored.
- Test #7 catches if Agent B did not author both code + test (tautological pass risk).
- Audit manually verifies against `flop_k72r_100bb` (AKs at row 0, col 1; AhKh blocked).
- Structural bug (both input + display matrices wrong) → NOT-READY.

### Other forecast must-fix surfaces (audit §1.1, §1.5)
- Worker thread writes UI directly (must-fix).
- Polling timer missing (must-fix).
- Mock returns `{"strategy": ...}` instead of `HUNLSolveResult` (must-fix).
- `poker_solver/range.py` modified (must-fix; `git diff integration -- poker_solver/range.py` must be empty).

---

## 3. Recommended order-of-attack

### Wave 1 (parallel, start of fan-out)
- **Agent A → Challenge 1 (state/threading scaffold).** Builds `SolveRunner` dataclass, `threading.Thread` worker, `ui.timer(0.5, update_ui)` poller. Trunk dep for waves 2+3.
- **Agent C → Challenge 3 + Challenge 6 (mock + library stub) in parallel.** Independent of Agent A's thread model. Procedural template per fixture, MDF clamp post-hoc, three hardcoded `LibraryEntry` namedtuples.
- **Agent B → Challenge 4 (matrix cell-coordinate code).** Can author `_combo_to_cell` / `_cell_to_combos` before A's `SolveRunner` lands; click handler is a placeholder A wires later.

### Wave 2 (after Wave 1)
- **Agent A → Challenge 2 + Challenge 7 (state.json + dark mode).** Both depend on threading scaffold so save/load doesn't race with worker writes.
- **Agent A → Challenge 5 (cancellation).** Extends Wave 1 threading scaffold with `_cancel` + `_paused` Events.

### Wave 3 (integration)
- **Agent B** wires matrix click handlers into Agent A's `SolveRunner.config` setters.
- **All** smoke-test the 20 acceptance tests in `tests/test_ui_smoke.py`.

**Order rationale:** A first (state) → C parallel (mock + library) → B late (matrix integration) is exactly the doc's prescription. C is fully independent so does not gate on A; B does pre-work but cannot integrate until A lands.

---

## 4. Threading model decision tree

```
Q: Does the work block the asyncio loop?
├── No  → async def + await directly on loop (e.g. file IO via aiofiles)
└── Yes → CPU-bound / NumPy / solver?
         ├── Yes (PR 10a mock_solve, PR 10b real solver)
         │   → threading.Thread, NOT asyncio.to_thread
         │   → worker writes ONLY to SolveRunner dataclass
         │   → ui.timer(0.5, update_ui) polls + re-renders
         │   → _cancel: threading.Event (NOT asyncio.Event)
         │   → _paused: threading.Event (worker calls _paused.wait())
         │
         └── No (short-lived IO, rare)
             → asyncio.to_thread is OK here, but document why
```

**Key invariants:**
- Worker thread NEVER calls `ui.*` anything. Period.
- All UI mutation happens on the asyncio loop, driven by the polling timer.
- `_CANCEL_FLAG = threading.Event` per spec §7.5 — same flag PR 10b reuses verbatim.
- Fallback if 500ms jank: drop to 250ms + coalesce matrix re-renders. If GIL-blocking visible: switch re-render from re-mount to in-place style mutation via `ui.element.update()`.

---

## 5. Mitigation strategies per challenge

| # | Challenge | Primary mitigation | Fallback |
|---|---|---|---|
| 1 | Threading | `threading.Thread` + `SolveRunner` dataclass + single `ui.timer(0.5)` poller. Worker writes only to dataclass; exceptions captured in `SolveRunner.error`. | Drop polling to 250ms; coalesce re-renders; in-place `ui.element.update()` if GIL-blocking. |
| 2 | state.json atomicity | `tempfile.NamedTemporaryFile(dir=parent)` → `json.dump` → `f.flush()` + `os.fsync` → `os.rename`. Wrap in `_atomic_write_json` helper. Debounce via `ui.timer(0.5, _flush_if_dirty)`. Corrupt load → `state.json.bak` + warning toast + defaults. | `os.replace` if Windows POSIX-rename flakes. Attach dirty flag to `app.storage.general` if per-client awkward. |
| 3 | Mock fidelity | Procedural per fixture: `(class, equity_bucket)` → action-distribution template, ±5% jitter, MDF clamp post-hoc. Three templates: dry-flop linear, wet-flop balanced, river polarized. River fixtures seeded offline via PR 5 solver in a notebook. | Run real PR 5 solver at ~200 iters on 3-4 spots offline, freeze as JSON, tag as "pre-computed". |
| 4 | Matrix clicks | Single source of truth in `ui/views/range_matrix.py`: `_combo_to_cell` + `_cell_to_combos` pair, exercised by test #7. Two `RangeMatrix` variants share coords, differ in `on_click`. Live string preview lazy on `state.range_p0.changed`. | If shift-click feels fragile: ship right-click-opens-freq-slider in 10a, full shift-click in 10b. |
| 5 | Cancellation | `SolveRunner.start() / pause() / resume() / stop()`. Two `threading.Event`s. Status enum: `idle/running/paused/stopped/done/error`. Re-solve detect: hash `HUNLConfig`; if unchanged + prior `stopped` → `resume_from_iter=prev_iter`. | If pause/resume bug-prone: defer Pause to 10b; ship Solve + Stop only (only test #5 strictly requires Stop). |
| 6 | Library stub | Three hardcoded `LibraryEntry` namedtuples in `ui.dialog`. Buttons no-op → `ui.notify("PR 11 will wire this", type='warning')`. Banner exact spec string. Zero opinions on serialization. | Minimum: dialog opens via header button, three rows render, both action buttons exist and are clickable. |
| 7 | Dark mode 3-state | Three-state toggle in header (Light / Auto / Dark) persisted as `state.ui_prefs.theme`. On `'auto'`: `ui.add_head_html` snippet listens to `prefers-color-scheme` media query, dispatches event flipping `ui.dark_mode` server-side. Quasar adapts via CSS variables. | Light/Dark two-state in 10a, defer Auto to 10b. Weakly-held lock note. |
| (audit 1.5) | Mock contract | Mock returns real `HUNLSolveResult` instance with all required fields (`MemoryReport`, `StreetMemoryEntry`, progress callbacks). Verify with `python -c "from poker_solver.hunl_solver import HUNLSolveResult; ... assert isinstance(r, HUNLSolveResult)"`. | None — this is a single-line audit assertion; either passes or must-fix patch. |

---

## 6. Anchors

- Source synthesis inputs:
  - `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/implementation_challenges.md`
  - `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_preprep_10a.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_spec.md`
- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_prompt.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/fanout_ready_10a.md`
- Launch kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/launch_kickoff_10a.md`
- Polish report: `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a_polish_report.md`
