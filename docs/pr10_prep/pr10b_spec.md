# PR 10b spec — swap the mock solver for the real PR 9 solver

## 0. Why this PR exists

PR 10a (`docs/pr10_prep/pr10a_spec.md`) shipped the NiceGUI UI scaffold
against `ui/mock_solver.py` — a mock that returns realistic
`HUNLSolveResult` instances for a curated set of fixture spots. The UI was
designed so that **every consumer-side type already matches the real
solver's surface**: `HUNLSolveResult`, `MemoryReport`, `StreetMemoryEntry`,
`HUNLConfig`, `Range`, `Combo`. The mock was a single file
(`ui/mock_solver.py`, ~400 lines) that exposed exactly one entrypoint
(`mock_solve`), imported from exactly one callsite (`ui/state.py`).

PR 10b deletes the mock module and points the import at the real solver.
That's the entire PR. It lands **after PR 9 (HUNL preflop) and PR 10a (UI
scaffold) both land** because the UI needs the union of postflop + preflop
to cover the spots its preset dropdown advertises.

**The UI structure is FROZEN at PR 10a** with **one design reframe locked
2026-05-22 (post-PR-10a, pre-PR-10b)**: the original PR 10a Q3 ("default
1000 iters") is reframed as a **target-exploitability slider with iter
count as a safety ceiling** (see §0.1 below). All other seven design
decisions locked in `pr10a_spec.md` §0.1 (Q1 two-pane; Q2 cell labels;
Q4 4-of-6 bet sizes; Q5 below-matrix inspector; Q6 reach filter 0.01;
Q7 yellow Mock mode banner) carry forward unchanged. The visible UI
differences between PR 10a and PR 10b are exactly two:

1. **Q3 reframe** — iteration-count number input becomes an
   exploitability-target slider (4 named tiers) with the iter input
   demoted to an "advanced safety cap" under an expansion panel.
2. **Q7 downgrade** — the yellow "Mock mode" banner shrinks to a subtle
   `(mock)` chip in the header, and the chip disappears entirely once a
   real solve completes successfully.

No other UX, layout, or marker contract changes.

Estimated effort: **1–2 days** (Q3 reframe adds ~30 minutes of UI work
on top of the original 1-day mock→real swap; the slider→target_exploitability
mapping is a small dict lookup).

## 0.1 Q3 reframe — exploitability slider (locked 2026-05-22)

**Status:** locked in `PLAN.md` §1 "Solver UI control" row (2026-05-22
synthesis after PR 10a manual-testing exposed that "1000 iters" is the
wrong abstraction to expose to end users; what they actually want is a
convergence quality target).

**Decision:** the user-facing primary control is a **target-exploitability
slider** with 4 named tiers. Iteration count becomes a **safety ceiling
(max 2000)** demoted into an "Advanced" expansion that is collapsed by
default.

### 0.1.1 Four tiers

| Tier | Target exploitability | Use case |
|---|---|---|
| **Draft** | 1.0% pot (≈10 mBB/pot) | quick first-look; "is this roughly the shape?" |
| **Standard** | 0.5% pot (≈5 mBB/pot) | default; tournament study / cash-game prep |
| **Tight** | 0.25% pot (≈2.5 mBB/pot) | publication-quality solves |
| **Library** | 0.1% pot (≈1 mBB/pot) | gold-standard archived solves; the slow path |

Slider implementation: NiceGUI `ui.slider` with 4 discrete steps, label
shown above as "Solve quality: {tier_name} ({target}% pot)". The numeric
target value is the slider's internal state; the tier name is cosmetic.

### 0.1.2 Iteration count as safety cap

Iteration count is **NOT** the user's primary lever. It is a safety
ceiling that protects against runaway wall-clock when the target
exploitability is unreachable on a given spot (e.g., too-thin
abstraction, numerical floor, malformed config).

- **Max safety cap: 2000 iterations** (matches Brown's MIT reference
  solver default; cited in `PLAN.md` §1 and
  `references/code/noambrown_poker_solver/` — Brown's default solve
  count is 2000 for the river benchmarks PR 7 diff-tested against).
- The iter input lives under an "Advanced" `ui.expansion` panel inside
  the run panel; collapsed by default. Power users can override the
  ceiling per-solve.
- When iter cap fires before target is reached, the status badge reads
  "Stopped (iter cap)" with the partial strategy preserved and a
  tooltip explaining the cap acts as a safety, not a quality, knob.

### 0.1.3 Numeric defaults: deferred to post-measurement calibration

**The four tier values above (1.0% / 0.5% / 0.25% / 0.1% pot) are
placeholder anchors, not final lockins.** They are based on:

- Industry convention from `references/blog/gtow_how_solvers_work.md`
  (GTO Wizard's published convergence bands).
- Noam Brown's reference solver default (2000 iters target).
- The mBB/pot scale used by PioSolver's "exploitability shown" panel.

**Calibration pass (planned, post-PR-10b-merge):** once PR 10b wires
the real DCFR into the UI, run a measurement pass on the 12 fixture
spots from PR 10a §7.4 + a small sample of preflop configs from PR 9.
Record wall-clock and observed exploitability at iter counts
{100, 250, 500, 1000, 2000}. Set each tier's numeric default so that:

- **Draft** completes in <30 s on a 100 BB flop (single-spot eye-test
  speed).
- **Standard** completes in <2 min on a 100 BB flop.
- **Tight** completes in <10 min on a 100 BB flop.
- **Library** is the slowest tier — completes in <30 min OR hits the
  2000-iter safety cap, whichever fires first.

The calibration pass produces a one-page PR (`pr-10c-tier-calibration`,
not yet specced) updating only the four numeric anchors in `ui/state.py`
+ `ui/views/run_panel.py`. PR 10b ships with the placeholders documented
above and a TODO comment at each constant.

**Open question (TBD post-measurement):** Does Library mode justify a
relaxed safety cap (e.g., 5000 iters) given its "gold standard" framing?
Decided at the calibration pass; PR 10b ships with the 2000 cap uniformly
across tiers.

### 0.1.4 How the UI displays exploitability live during solve

DCFR exposes per-iteration exploitability via `log_every`'s snapshot
points (PR 5's `solve_hunl_postflop` already does this for the history
list; PR 10b's added `on_progress` callback streams them live).

- **Live status display (new):** below the slider, render a status line:
  `Solve quality target: {tier} ({target} mBB/pot). Live: {current} mBB/pot
  ({pct_to_target}%).` The "Live" value updates each `on_progress` fire
  (typically every 100 iters per `log_every=100` default).
- **Visual feedback:**
  - Progress bar fill = `1 - (current / start_expl)` clipped to [0, 1].
  - When `current <= target`, the bar turns green and the status badge
    reads "Reached target" → solver exits the DCFR loop early via the
    existing `target_exploitability` early-stop kwarg (PR 5 already
    threads this through `_run_with_probe`).
  - When `iter == iter_cap` and `current > target`, badge reads
    "Stopped (iter cap)" with the live value visible in red.
- **No new chart widget** — the existing log-scale exploitability chart
  from PR 10a §4.3 stays; only the status line above it changes from
  "Iter X / Y" to the target-aware framing above. The iter counter is
  preserved (it's still useful diagnostically, just no longer the
  primary metric).

### 0.1.5 Marker contract additions

PR 10b adds three new marker contracts that PR 11 introspection / future
test suites can rely on:

- `solve-quality-slider` — the `ui.slider` element.
- `solve-quality-tier-label` — the cosmetic tier-name display above the
  slider.
- `solve-quality-status-line` — the live "{tier} ({target}). Live:
  {current} ({pct})" status line below the slider.

The existing `mock-mode-banner` marker is replaced by `mock-mode-chip`
(the Q7 downgrade); no other PR 10a marker contracts change.

## 1. Goal

Replace `ui/mock_solver.py`'s `mock_solve` with the real solver dispatch.
After PR 10b lands, the user can:

- Open `poker-solver ui`.
- Configure any spot the engine accepts (preflop, postflop, push/fold).
- **Pick a solve-quality tier** (Draft / Standard / Tight / Library) via
  the new exploitability slider (§0.1) — iter count is now a safety cap,
  not the primary lever.
- Click **Solve** and watch the **actual DCFR loop converge** in real
  wall-clock with real exploitability decay.
- See the live exploitability status line update toward the chosen tier's
  target each `log_every` tick; solver exits early when target reached.
- See the **real `MemoryReport`** in the memory panel.
- Toggle Python / Rust backends and observe the speedup (Rust path lands
  in PR 6, by then merged via integration branch).
- Trust every number on the screen as ground-truth solver output.

The mock's "(mock)" overlay disappears. The fixture preset dropdown
remains — its entries now load real-spot configurations and trigger real
solves.

## 2. Scope

**Inside scope:**

- Delete `ui/mock_solver.py` and `ui/mock_solver_fixtures.py` (if it was
  split out).
- Change the single import in `ui/state.py` from
  `from ui.mock_solver import mock_solve as _solve_postflop_impl` to a
  thin dispatch wrapper that picks the right real solver based on
  `HUNLConfig.starting_street`:
  - `PREFLOP` → PR 9's preflop solver (signature to be specified in
    `docs/pr9_prep/pr9_spec.md`).
  - `FLOP` / `TURN` / `RIVER` → `poker_solver.hunl_solver.solve_hunl_postflop`.
  - The push/fold short-circuit lives inside `poker_solver.solver.solve`;
    we route through that.
- **Add the progress-callback kwarg to `solve_hunl_postflop`.** The mock
  exposed `mock_progress_callback`; the real solver needs an
  `on_progress: Callable[[int, float, MemoryReport], None] | None = None`
  kwarg threaded into `hunl_solver._run_with_probe`. This is the **one
  engine-side change PR 10b makes**.
- **Q3 reframe (§0.1):** Replace the iteration-count number input in
  `ui/views/run_panel.py` with a 4-step `ui.slider` (Draft / Standard /
  Tight / Library). Map the tier to `target_exploitability` (which PR 5's
  `solve_hunl_postflop` already accepts) at solve dispatch time in
  `ui/state.py`. Demote the iter-count input into an "Advanced" expansion
  panel with max=2000 enforced. Add the live status line below the slider
  per §0.1.4. Mark each tier's placeholder numeric default with
  `# TODO(pr-10c-calibration): tune post-measurement` per §0.1.3.
- Update the smoke tests:
  - Delete the 5 PR 10a mock-specific tests
    (`test_mock_solve_*`, `test_ui_never_imports_mock_specific_symbols`).
  - The 8 original smoke tests still pass — they target the UI, not the
    solver implementation. **Exception:** any retained smoke test that
    asserts the iter-input element exists at top level of the run panel
    must be updated to find it inside the new Advanced expansion (a
    single-line locator change; not a structural test rewrite).
  - Add 3 tests:
    - `test_real_solve_completes_river_subgame` — runs the PR 3
      `default_tiny_subgame` end-to-end through the UI and verifies the
      matrix renders the actual solver output (not a fixture).
    - `test_real_solve_progress_callback_fires` — see §6 add list.
    - `test_quality_slider_maps_to_target_exploitability` — new; asserts
      slider position N corresponds to the documented target value
      (Draft=10 mBB/pot, Standard=5, Tight=2.5, Library=1).
- Update `README.md`: change section header from `## UI (mock)` to `## UI`
  and remove the PR 10a "mock mode" paragraph. The Q7 banner downgrade
  to a `(mock)` chip is internal-only (visible only on the first launch
  before any real solve completes); the README no longer markets it.
- Update `USAGE.md` §4 (the UI section): replace the placeholder
  "iterations, bet-size menu, target-exploitability mode" framing with
  the slider-first framing (Draft/Standard/Tight/Library tiers). Note
  that numeric defaults are placeholders pending the PR 10c calibration
  pass.
- Update the UI's preset dropdown to load **real** configs that exercise
  each of the 12 fixture spot categories from PR 10a — the configs are
  the same; only the solver path differs.

**Outside scope:**

- Library mode (PR 11).
- Native packaging (PR 11).
- Any UI restructuring; the views are final after PR 10a.
- Any new solver math; we consume what PR 9 ships.

## 3. The engine-side change

PR 5's `solve_hunl_postflop` already supports `log_every` for
exploitability history snapshots, but it does **not** call back to the
caller during the solve. PR 10b adds:

```python
# poker_solver/hunl_solver.py — diff

def solve_hunl_postflop(
    config: HUNLConfig,
    abstraction: AbstractionTables | None = None,
    iterations: int = _DEFAULT_ITERATIONS,
    target_exploitability: float | None = None,
    memory_budget_gb: float = _DEFAULT_MEMORY_BUDGET_GB,
    *,
    log_every: int | None = None,
    seed: int | None = None,
    dcfr_kwargs: dict[str, Any] | None = None,
+   on_progress: Callable[[int, float, MemoryReport], None] | None = None,
) -> HUNLSolveResult:
    ...
```

And the threading point:

```python
# _run_with_probe — diff

while done < iterations:
    step = min(chunk_size, iterations - done)
    solver.solve(step)
    done += step
    final_report = probe.snapshot()
    if final_report.total_gb > memory_budget_gb:
        raise MemoryError(...)
    if log_every is not None:
        expl = exploitability(game, solver.average_strategy())
        history.append(expl)
+       if on_progress is not None:
+           on_progress(done, expl, final_report)
        if target_exploitability is not None and expl <= target_exploitability:
            break
```

PR 9's preflop solver should ship the same kwarg with the same signature
(its spec calls this out as a derived requirement from `pr10b_spec.md`).

The callback fires on the worker thread (`ui/state.py::SolveRunner`'s
worker, per `pr10_spec.md` §6). The UI side polls `SolveRunner.expl_history`
via its `ui.timer(0.5, ...)` as before — the callback's only job is to push
the new `(iter, expl, report)` tuple into the runner's protected state.

## 4. The UI-side change

The whole change is a few-line diff in `ui/state.py`:

```python
# ui/state.py — diff

-from ui.mock_solver import mock_solve as _solve_postflop_impl
+from poker_solver.hunl_solver import solve_hunl_postflop
+from poker_solver.preflop_solver import solve_hunl_preflop  # PR 9
+from poker_solver.hunl import Street
+
+# Q3 reframe (§0.1.1): solve-quality tier → target_exploitability mapping.
+# Numeric defaults are PLACEHOLDERS pending the PR 10c calibration pass
+# (see §0.1.3); update in lockstep with run_panel.py's slider labels.
+SOLVE_QUALITY_TIERS = {
+    "draft":    10.0,   # 1.0% pot  TODO(pr-10c-calibration)
+    "standard": 5.0,    # 0.5% pot  TODO(pr-10c-calibration)
+    "tight":    2.5,    # 0.25% pot TODO(pr-10c-calibration)
+    "library":  1.0,    # 0.1% pot  TODO(pr-10c-calibration)
+}
+ITER_SAFETY_CAP = 2000  # matches Brown's MIT reference solver default.
+
+def _solve_postflop_impl(config, iterations, *, on_progress=None,
+                          target_exploitability=None, **kwargs):
+    """Dispatch to the real solver based on starting street.
+
+    Push/fold short-stack mode is handled inside `poker_solver.solver.solve`
+    via the existing PREFLOP+is_pushfold_mode short-circuit; we route
+    explicit preflop configs through the preflop solver and postflop
+    configs through the postflop solver.
+
+    `iterations` here is the **safety cap** (max 2000 per Q3 reframe);
+    `target_exploitability` is the **primary lever** translated from the
+    slider tier upstream in SolveRunner.start.
+    """
+    iterations = min(iterations, ITER_SAFETY_CAP)
+    if config.starting_street == Street.PREFLOP:
+        return solve_hunl_preflop(config, iterations=iterations,
+                                  target_exploitability=target_exploitability,
+                                  on_progress=on_progress, **kwargs)
+    return solve_hunl_postflop(config, iterations=iterations,
+                               target_exploitability=target_exploitability,
+                               on_progress=on_progress, **kwargs)
```

Three lines deleted (the mock import + the `mock_*` kwargs threading
through `SolveRunner.start`); ~30 lines added (the dispatch wrapper +
imports + the SOLVE_QUALITY_TIERS dict + the safety-cap clamp). The
`SolveRunner.start` method gains a `quality_tier: str = "standard"` kwarg
that it translates into `target_exploitability=SOLVE_QUALITY_TIERS[tier]`
before calling `_solve_postflop_impl`. The slider element in
`ui/views/run_panel.py` is the **only** new structural UI element; the
matrix / tree / inspector / chart all remain pixel-identical to PR 10a.

## 5. Delete list

These files are removed in PR 10b:

- `ui/mock_solver.py`
- `ui/mock_solver_fixtures.py` (if PR 10a created it)

These tests are removed from `tests/test_ui_smoke.py`:

- `test_mock_solve_returns_real_hunl_solve_result`
- `test_mock_solve_streams_progress_callbacks`
- `test_mock_solve_failure_oom_raises_memory_error_with_partial_report`
- `test_mock_solve_failure_cancelled_returns_partial_result`
- `test_ui_never_imports_mock_specific_symbols`

## 6. Add list

- `test_real_solve_completes_river_subgame` (smoke test #14):
  - Loads the PR 3 `default_tiny_subgame` preset.
  - Sets quality tier to "draft" (the fastest tier; expected wall-clock
    <2 s on the tiny river subgame).
  - Clicks Solve; waits for `SolveRunner.status == 'done'`.
  - Asserts `SolveRunner.result.average_strategy` is non-empty.
  - Asserts the matrix renders 169 cells with at least one non-grey cell.
  - Asserts `SolveRunner.result.exploitability_history[-1] <= 10.0` (the
    draft tier target).

- `test_real_solve_progress_callback_fires` (smoke test #15):
  - Mocks `on_progress` and asserts it fires at least once during a
    quality-tier="standard" solve. Uses the default `log_every=100`.
  - Asserts the live status line below the slider updates with each fire.

- `test_quality_slider_maps_to_target_exploitability` (smoke test #16):
  - Programmatically sets the slider to each of the 4 tiers (draft /
    standard / tight / library).
  - Asserts the dispatch into `_solve_postflop_impl` carries the
    expected `target_exploitability` per `SOLVE_QUALITY_TIERS`
    (10.0 / 5.0 / 2.5 / 1.0 mBB/pot).
  - Asserts the iter safety cap clamps to 2000 even if the Advanced
    expansion's iter input is set higher.

- `test_iter_cap_fires_when_target_unreachable` (smoke test #17):
  - Builds a degenerate config where the target is unreachable in
    2000 iters (e.g., set library tier on a fresh wet-flop spot with
    minimal abstraction).
  - Asserts solver exits with `status == 'stopped (iter cap)'` rather
    than running forever.
  - Asserts the partial strategy is preserved in the matrix.

The other 8 original smoke tests from `pr10_spec.md` §10 Agent C remain
unchanged in spirit — they test the UI's structural behavior, not the
solver. Locator update needed: any test that grabs the iter-count input
must look inside the new Advanced expansion (one-line change per test;
expected to affect at most 1–2 of the original 8).

## 7. Acceptance criteria

PR 10b is mergeable when:

1. All ~12 smoke tests pass (8 original + 4 new; 5 mock-tests deleted).
2. `poker-solver ui` launches and solves the PR 3 `default_tiny_subgame`
   end-to-end with real DCFR output rendered in the matrix, via the new
   solve-quality slider (set to Draft for the smoke).
3. All 12 fixture preset configurations from PR 10a, when loaded and
   solved with real DCFR on the Standard tier, produce matrices that
   pass a poker-player eye test (the user, in PR review, validates this
   against intuition).
4. The Python/Rust backend toggle works for spots the Rust backend
   supports (per PR 6 / PR 7 / PR 8 status at PR 10b merge time).
5. `ui/mock_solver.py` is deleted (grep returns nothing).
6. `scripts/check_pr.sh` passes.
7. The progress callback wired into `solve_hunl_postflop` does not break
   any existing PR 5 / PR 6 / PR 7 tests (the kwarg defaults to None;
   existing callers pass nothing).
8. The solve-quality slider is the **primary** control in the run panel,
   visible without scrolling or expanding. Iter-count input is **only**
   reachable via the "Advanced" expansion, and is hard-clamped at 2000.
9. The live exploitability status line below the slider updates during
   solve (each `on_progress` fire); when target is reached the badge
   turns green and the DCFR loop exits early via the existing
   `target_exploitability` mechanism (no new engine code).
10. The four tier placeholders (Draft=10, Standard=5, Tight=2.5,
    Library=1 mBB/pot) each carry a `TODO(pr-10c-calibration)` comment
    in source (`ui/state.py` SOLVE_QUALITY_TIERS dict + the matching
    label dict in `ui/views/run_panel.py`).

## 8. Risks

1. **PR 9 preflop solver signature drift.** If `solve_hunl_preflop` ships
   with a signature that differs from `solve_hunl_postflop`'s in ways the
   UI didn't anticipate (e.g., extra mandatory kwargs), the dispatch
   wrapper grows. Mitigation: PR 9's spec consistency review checks
   alignment with `solve_hunl_postflop`'s signature; PR 10b spec is
   advisory input to PR 9.

2. **Real DCFR is much slower than the mock's `mock_latency_ms`.** PR
   10a's UI was tested with mock latencies up to 5 min. A real 100 BB
   flop solve at 50_000 iterations may take 5–15 min (per PLAN.md §1 perf
   table). UI is designed for this — the progress callback + 500 ms
   timer poll handle arbitrarily long solves — but the first PR 10b user
   experience might surprise testers. Mitigation: the README's "Quick
   tour" section recommends starting with `default_tiny_subgame` (a
   river-only subgame, expected <2 s) for first-time use.

3. **Real `MemoryReport` numbers may not match the mock's plausible
   ranges.** The mock fabricated ~2 GB flop / ~1 GB turn / ~0.5 GB river
   for a 100 BB spot. If real numbers diverge (e.g., 8 GB flop with
   default abstraction), the UI's memory panel layout (designed for
   2 GB numbers) may overflow. Mitigation: the memory panel uses
   responsive number formatting (`f"{report.total_gb:.2f} GB"`) and
   accepts any reasonable range; no fixed-width assumption.

4. **Tree-browser performance with real trees.** The mock built a small
   curated tree per fixture (~50 nodes max). Real trees can have 10^4–
   10^6 infosets. PR 10a's tree adapter is lazy + caps visible nodes at
   2000 per `pr10_spec.md` §8.5, so this is expected to work — but
   regression risk exists. Mitigation: the smoke tests include
   `test_tree_visible_nodes_under_cap` from the original spec.

5. **Slider tier defaults are placeholders, not measured.** Per §0.1.3
   the four tier values are anchored to industry convention but have
   NOT been calibrated against real DCFR convergence curves on this
   solver. First-day PR 10b user experience may show "Draft" taking
   longer than 30 s on a wet flop, or "Library" hitting the iter cap
   without converging. Mitigation: the PR 10c calibration pass is
   pre-specced (§0.1.3) and runs immediately post-merge. Until then,
   tier names are honest labels; numeric values are best-effort
   anchors. This is the **dominant new risk** PR 10b introduces beyond
   the original PR 10b risk surface.

6. **Slider semantic mismatch with end-user mental model.** Users
   trained on Pio/GTOW may search for an "iterations" knob and not
   immediately discover the slider. Mitigation: keep iter input in
   Advanced expansion (discoverable but not primary); tooltip on
   slider reads "Solve quality — higher tiers solve longer but
   produce strategies closer to Nash." USAGE.md §4 (updated in this
   PR) explains the slider semantics in plain language.

## 9. Test plan checklist

- [ ] `pytest tests/test_ui_smoke.py -v` passes (12 tests).
- [ ] Launch `poker-solver ui`. Pick `river_tiny_subgame` preset. Leave
      slider at **Standard**. Click Solve. Observe matrix renders, tree
      populates, expl chart shows decay, and the live status line below
      the slider counts down toward the target.
- [ ] Repeat for `flop_k72r_100bb` on **Draft** tier (fastest); confirm
      pause + resume + stop all behave correctly. Switch to **Tight**
      tier and re-solve; confirm wall-clock noticeably longer.
- [ ] Drag slider to **Library** tier on a degenerate config (e.g.,
      `flop_t87s_100bb` with custom narrow ranges). Confirm the iter
      safety cap fires at 2000 with status "Stopped (iter cap)" and
      partial strategy preserved.
- [ ] Open the "Advanced" expansion. Confirm iter-count input is there,
      defaulted to 2000, and editing it above 2000 is clamped on solve.
- [ ] Pick a config with `starting_street=PREFLOP` (via the spot input,
      not preset). Click Solve. Confirm it routes through the preflop
      solver (status bar shows "Backend: python", iteration count
      reasonable for a preflop tree). Confirm tier slider still works.
- [ ] Configure a config that exceeds 14 GB memory budget. Click Solve.
      Observe the `MemoryError` is caught and the UI shows the partial
      `MemoryReport` (not a stack trace).
- [ ] Verify each of the 4 tier defaults in `ui/state.py::SOLVE_QUALITY_TIERS`
      carries a `# TODO(pr-10c-calibration)` comment (grep).
- [ ] Run `scripts/check_pr.sh`; expect green.

## 10. Reference appendix

- `pr10a_spec.md` (the PR this one finishes).
- `pr10_spec.md` (the original long-form spec; all UI design intent
  carries forward).
- `/Users/ashen/Desktop/poker_solver/poker_solver/hunl_solver.py`
  (`solve_hunl_postflop` — PR 5; PR 10b adds the `on_progress` kwarg).
- `docs/pr9_prep/pr9_spec.md` (PR 9 preflop solver — must expose
  `on_progress` kwarg per §3 of this spec).
- PLAN.md §1 (UI + locked architecture decisions).
