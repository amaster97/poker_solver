# poker_solver v0.6.0 release notes

**Release date:** 2026-05-22 (PR 10a merge).
**Codename:** "Mock-first UI."

Minor release. PR 10a ships the full v1 user-facing UI artifact — a NiceGUI
browser app with two-pane layout, 13×13 range matrix, tree browser, run
panel, and combo inspector — wired to `ui/mock_solver.py` rather than the
real `solve_hunl_postflop`. PR 10b is a one-line import swap in
`ui/state.py` (mock → real). MINOR per SemVer: new public entry point
(`poker-solver ui`) and a new top-level `ui/` package sibling to
`poker_solver/`. Zero changes to the `poker_solver` Python API and zero
behavior change to PRs 1-9 (NiceGUI gated under the new optional `[ui]`
extra).

**Note on versioning:** v0.6.0 was previously reserved for PR 8 (Rust SIMD
perf + external Nash validation). Since PR 10a is shipping FIRST, v0.6.0
now denotes the UI scaffold. PR 8's forward-looking notes will be revised
to v0.7.0 when PR 8 ships.

---

## What's new in v0.6.0

### 1. NiceGUI mock-first UI (`ui/` package, ~5,535 LOC + 821 LOC tests + 68 LOC edits to README/cli.py/pyproject.toml = ~6,424 LOC total)

New top-level `ui/` package, sibling to `poker_solver/` and `crates/` so
the engine has zero NiceGUI import cost.

- **`ui/app.py`** — NiceGUI entrypoint, two-pane layout (matrix center
  + one collapsible right sidebar with three `ui.expansion` panels:
  spot input / run panel / tree browser). Yellow dismissible
  "Mock mode" banner, Auto-default theme toggle, hamburger menu.
- **`ui/state.py`** — shared state, `SolveRunner` (threading-based
  worker per spec §6.1 + §11 #1; `threading.Event` cancellation flag
  checked once per mock-iter), `RangeWithFreqs` (WRAPS
  `poker_solver.Range`, never modifies), atomic `state.json`
  persistence at `~/.poker_solver_ui/state.json` (tmp + fsync + rename;
  `.bak` fallback on corrupt-load; 0.5s debounce).
- **`ui/views/`** — `spot_input.py` (board picker, range input with
  matrix-mode + live string preview + combo counter, stacks with
  push/fold warning toast at ≤15 BB), `run_panel.py` (bet-size
  checkboxes + raise caps + iterations + backend selector +
  color-coded Solve/Pause/Stop + `ui.echart` log-scale exploitability
  chart with linear toggle, 500ms update cadence), `range_matrix.py`
  (13×13 matrix with Pio additive RGB color blend + `R xx%`/`C xx%`/
  `F xx%`/`MIX`/`BLK` on-cell tag, hover tooltip, click-strip combo
  inspector BELOW matrix with horizontal stacked bar + per-combo EV +
  reach + infoset-key copy icon), `tree_browser.py` (chevron expand/
  collapse, inline per-node action stats, reach filter slider above,
  lazy expansion, performance cap of 100 children per node + 2000
  total nodes), `library_browser.py` (PR 11 stub: disabled button,
  placeholder rows, toast on click), `onboarding.py` (3-step modal
  gated on `ui_prefs.onboarding_completed`; teaches R/Y/G legend).

### 2. Seven locked design decisions (per `pr10a_spec.md` §0.1)

Synthesis from `competitor_ui_deep_dive.md` + `ui_design_principles.md`
+ `ui_mockups_and_debates.md`:

- **Q1** two-pane layout (resolves 4-pane anti-pattern §3.1).
- **Q2** hand-class shorthand inside cells (e.g. `AA`, `AKs`).
- **Q3** default 1000 iterations; target-exploitability opt-in.
- **Q4** 4-of-6 bet sizes default: 33% / 75% / 100% / all-in
  (plus custom-size text field).
- **Q5** combo inspector BELOW matrix (not floating side panel).
- **Q6** reach filter default 0.01.
- **Q7** yellow dismissible "Mock mode" banner.

### 3. 12 hand-curated fixture spots

`tests/data/mock_fixtures/*.json`: `river_tiny_subgame`,
`flop_k72r_100bb`, `flop_t87s_100bb`, `flop_monotone_hhh`,
`flop_paired_q9q`, `turn_kqj9_4_flush`, `turn_t872_brick`,
`river_axxs_polar`, `preflop_btn_vs_bb`, `river_blocker_heavy`,
`shortstack_25bb`, `deepstack_200bb`. Eye-test passing: MDF-obeying
river bluff frequencies, river polarization, flop linear ranges,
correct blocker effects across dry / wet / monotone / paired /
shortstack / deepstack textures.

### 4. 20 smoke tests (`tests/test_ui_smoke.py`)

`@pytest.mark.ui` + module-level `pytest.importorskip('nicegui')` —
cleanly skipped on hosts without `[ui]` extra. Breakdown:

- **8 UI smoke** (§10.1): page renders, board picker, range input,
  solve start/stop, 169-cell matrix render, combo→cell mapping
  property test, library dialog.
- **5 mock-solver coverage** (§10.2, PR 10b deletes): real
  `HUNLSolveResult` shape, progress callbacks, OOM partial report,
  cancellation partial result, import-discipline assertion.
- **4 UX-grounded** (§10.3): Pio color blend RGB ±2 channel tolerance,
  blocker overlay, palette disjointness lock, chart default log.
- **3 edge-case** (§10.4): OOM remediation, push/fold toast at 15 BB,
  long-solve ETA after 30s.

### 5. CLI `ui` subcommand

`poker-solver ui --port 8080 --host 127.0.0.1 --dark-mode auto`. Lazy-
imports `ui.app` only at invocation. Clean `ImportError` path with
remediation message ("Install with `pip install poker-solver[ui]`")
and exit code 2 when NiceGUI is missing.

### 6. Mock solver layer (PR 10b deletes)

`ui/mock_solver.py` — `mock_solve` signature byte-identical to PR 5's
`solve_hunl_postflop` (and PR 9's `solve_hunl_preflop`) except for
`mock_*` kwargs:
`mock_solve(config, abstraction=None, iterations=1000,
target_exploitability=None, memory_budget_gb=14.0, *, log_every=50,
seed=42, dcfr_kwargs=None, mock_latency_ms=0, mock_failure_mode=None)`
— note NO `on_progress`; per Option A applied in PR 10a, progress is
delivered via thread-safe polling through `read_latest_progress()` — no
callback needed. Returns real `HUNLSolveResult` with fabricated
`MemoryReport` (`total_gb` / `per_street` / `river_ratio` /
`rss_calibration_error` / `wallclock_per_iter_sec`). Module-level
`_CANCEL_FLAG` (`threading.Event`) is the SAME flag PR 10b's real
solver uses unchanged. Six failure modes (`oom`, `not_implemented`,
`cancelled`, `long_latency`, `rapid_iteration`, unset).

---

## What it doesn't add

- **No new `poker_solver` API.** Engine surface unchanged from v0.5.2.
  `RangeWithFreqs` WRAPS `poker_solver.Range` and never modifies it —
  `git diff integration -- poker_solver/range.py` is empty.
- **No real solver wired.** PR 10b's one-line import swap in
  `ui/state.py` (mock → real) does that. The mock signature is
  byte-locked to the real signature today; asserted by
  `test_mock_solve_signature_matches_real_solver`.
- **No library mode.** PR 11 ships persistence + `.dmg` packaging.
  PR 10a includes only a disabled stub dialog (`library_browser.py`).
- **No new wheel dependencies in base install.** `nicegui>=2.0,<3.0` is
  under `[project.optional-dependencies] ui` only. `pip install
  poker-solver` works without NiceGUI.
- **No mobile-responsive layout, no native packaging.** Browser-served
  at `127.0.0.1` only (no `0.0.0.0`, no auth, no TLS). NiceGUI
  `native=True` (pywebview) explicitly NOT used. `.dmg` deferred to
  PR 11.

---

## Honest caveats

### 1. Mock-only output

All solver outputs in v0.6.0 are fabricated by `ui/mock_solver.py`. The
yellow dismissible "Mock mode" banner (Q7) ensures users see this every
launch until dismissed. Numerical values are eye-test-curated, not real
CFR convergence — use for UI exploration only, not for poker decisions.

### 2. Mock signature drift risk vs real solver

`mock_solve` is byte-locked to today's `solve_hunl_postflop` signature.
If PRs 8/9 change that signature before PR 10b, `ui/state.py`'s import
swap will require adapting — tracked in `pr10b_prep/`. Smoke test
`test_mock_solve_signature_matches_real_solver` asserts equivalence at
PR 10a merge time but cannot catch post-merge drift.

### 3. 12 fixtures are hand-curated; not all spots covered

Eye-test passing for the 12 named board textures, but novel spots
outside the fixture set fall back to generic mock output. PR 10b's real
solver removes this limitation.

### 4. Q3 coin-flip flag

1000 vs 2000 iterations default — if PR 10a manual testing surfaces
under-converged matrices on common spots, bump to 2000 in PR 10b.

### 5. Seven should-fix audit items deferred to PR 10a.5

7 should-fix audit items deferred to PR 10a.5 (conformance pass):
missing UI markers for blocker overlay, log-scale chart toggle,
push/fold dispatch button, progress ETA banner, plus
`cell_rgb_for_action_freqs` / `DISPLAY_PALETTE` constants. Tests 14-20
marked `@pytest.mark.xfail`.

---

## Quick start

```bash
pip install poker-solver[ui]
poker-solver ui                    # http://127.0.0.1:8080
poker-solver ui --port 9090        # alternative port
poker-solver ui --dark-mode auto   # auto / light / dark
```

Or direct: `nicegui run ui/app.py`. First launch presents the 3-step
onboarding modal (R/Y/G legend); subsequent launches restore state from
`~/.poker_solver_ui/state.json`.

---

## What's still coming

- **PR 8** (Rust SIMD perf + external Nash validation) — now likely
  v0.7.0; was previously slated for v0.6.0 before PR 10a took priority.
- **PR 9** (HUNL preflop full game) — adds `solve_hunl_preflop`.
- **PR 10b** (real solver swap) — one-line import in `ui/state.py`;
  deletes `ui/mock_solver.py` and the 5 mock-coverage smoke tests.
- **PR 11** (library mode + `.dmg` packaging + native-desktop wrapper)
  — replaces the disabled stub dialog.
- **PR 12** (3-handed stretch) — post-v1 scope.

---

## Acknowledgments

- **NiceGUI 2.x** (MIT) — declared as `[ui]` optional extra; powers the
  browser frontend. No code copied; library used via public API only.
- **Pio's R/Y/G strategy color convention** — widely-used poker-industry
  standard for raise/call/fold visualization; reference inspiration
  only. No code copied from Pio, GTOW, Monker, or DeepSolver — only
  architectural patterns. R/Y/G triad is industry-standard expression,
  not copyrightable. See `competitor_ui_deep_dive.md` for design-pattern
  attribution.
- **Spec synthesis** — `pr10a_spec.md` §0.1 seven Q-locks derived from
  `competitor_ui_deep_dive.md` + `ui_design_principles.md` +
  `ui_mockups_and_debates.md`.
- **Three-agent fan-out** per `docs/pr10_prep/launch_kickoff_10a.md`:
  agent A (app shell + state + spot input + run panel), agent B (range
  matrix + tree browser), agent C (mock_solver + library stub + 20
  smoke tests + CLI + pyproject), plus post-implementation audit per
  `audit_prompt_final_10a.md`.

---

## License

MIT. NiceGUI is MIT (optional extra). No code copied from competitor UI
projects. For the full plan, decision log, and roadmap, see `PLAN.md`.

