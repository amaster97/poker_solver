# PR 10a.5 Agent — UI smoke-test conformance pass

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Single-agent execution. Scope is narrow (~150-250 LOC) — fan-out adds coordination cost with no parallelism benefit.
> - Branch `pr-10a5-ui-conformance` in git worktree `/private/tmp/poker_pr10a5`, branched off `integration` tip (PR 10a merge commit `b880032`).
> - Target version: **v0.6.1 PATCH** (no engine changes; UI-only conformance pass).
> - Acceptance gate: smoke-test green-board count rises from **8 / 20** to **20 / 20**.

---

## 5-line summary

**You are the PR 10a.5 single agent.**
**Your scope:** the UI smoke-test conformance pass — fix Agent B's multi-tag `data-marker` drift that broke 5 tests, then wire up the 7 missing markers / constants / methods that are currently `@pytest.mark.xfail`-decorated. PR 10a.5 ships as **v0.6.1 PATCH**.
**Your contract:** ship single-value `data-marker` props at `ui/views/range_matrix.py:735` and `:844`; verify preset markers in `ui/views/spot_input.py` match the 12 fixture IDs from `ui/mock_solver_fixtures.py` exactly; add `cell_rgb_for_action_freqs(fold, call, raise_) -> (r, g, b)` adapter (pure Pio anchors); add `DISPLAY_PALETTE` + `INPUT_PALETTE` module-level constants; wire `blocker-overlay` CSS class, `expl-chart-linear-toggle` marker, `oom-reduce-bet-sizes-button` button, `pushfold-switch-button` button, `progress-eta` marker, and `SolveRunner.compute_eta()` method; remove the 7 `@pytest.mark.xfail` decorators in `tests/test_ui_smoke.py`.
**Your success criteria:** all **20 smoke tests pass** (no `xfail`, no `fail`); ruff clean; black clean; `mypy --strict` clean on the touched ui/* files (matching PR 10a's bar); zero `poker_solver/` diff; zero `pyproject.toml` diff; ALL existing tests still pass.
**File ownership:** you own `ui/views/range_matrix.py`, `ui/views/spot_input.py`, `ui/views/run_panel.py`, `ui/state.py`, `ui/app.py`, plus xfail decorator removal in `tests/test_ui_smoke.py`. You may NOT touch `ui/views/library_browser.py` (PR 11 owns), nor any engine file, fixture file, or `pyproject.toml`.

---

## Strict file ownership

**You own (edit freely; no creation expected):**
- `/Users/ashen/Desktop/poker_solver/ui/views/range_matrix.py` (~80 LOC of edits: marker fix + adapter + constants + blocker class)
- `/Users/ashen/Desktop/poker_solver/ui/views/spot_input.py` (~30 LOC of edits: preset marker cross-check + `INPUT_PALETTE` constant + pushfold toast wire)
- `/Users/ashen/Desktop/poker_solver/ui/views/run_panel.py` (~50 LOC of edits: log-scale toggle marker + OOM remediation button + progress-eta marker)
- `/Users/ashen/Desktop/poker_solver/ui/state.py` (~30 LOC of edits: `SolveRunner.compute_eta()` method)
- `/Users/ashen/Desktop/poker_solver/ui/app.py` (~15 LOC of edits: pushfold toast button wire)
- `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py` (-7 lines: remove the 7 `@pytest.mark.xfail` decorators at lines 452, 498, 531, 580, 620, 659, 683 — NO other edits to this test file)

**You must NOT touch:**
- `ui/views/library_browser.py` — **PR 11 owns**; PR 11 is rewriting this from scratch under the library-mode track. Any edit here is a hard-forbidden scope leak.
- `ui/mock_solver.py` and `ui/mock_solver_fixtures.py` — mock signature locked at v0.6.0 per `release_notes_v0.6.0.md` §1 caveat #2. The 12 fixture IDs are frozen.
- `poker_solver/` (any file) — PR 10a.5 is 100% UI-side. Zero engine diff.
- `crates/` — PR 11 owns (PyInstaller bundling).
- `pyproject.toml` — no pin bumps, no new deps. Any need indicates scope leak; halt for scope review.
- Any test file other than the xfail decorator removal in `tests/test_ui_smoke.py`. NO new smoke tests; the 20-test count is locked.
- `poker_solver/library/` — PR 11 territory (new package).
- `tests/test_library_*.py` — PR 11 territory.

If you discover a mid-implementation spec gap, **do not silently invent behavior**. Stop and write a short note to the orchestrator describing the conflict; halt for scope review.

## Read first (in this order)

1. **The scope freeze (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/pr10a5_conformance_backlog.md`. Internalize §1 (background), §2 (five hard failures F1-F5 — root cause + file:line), §3 (seven xfailed tests X1-X7 — anchors), §4 (recommended scope — six numbered steps), §5 (parallel with PR 11 — file-overlap audit), §6 (out of scope — Q-locks, fixtures, mock signature, engine, version bump beyond v0.6.1 all frozen).
2. **The originating audit:** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/audit_report_10a.md`. Read the **Should-fix** section in full (items #1, #2, #3 are the ones PR 10a.5 closes). Skim Must-fix (already resolved in v0.6.0 follow-up commits) and Looks-good for context.
3. **The smoke-test file:** `/Users/ashen/Desktop/poker_solver/tests/test_ui_smoke.py`. Internalize the 7 xfailed tests (smoke 14-20) — read each test body to understand exactly what marker / constant / behavior it asserts. Lines 452, 498, 531, 580, 620, 659, 683 carry the `@pytest.mark.xfail` decorators; the test bodies tell you what to wire.
4. **The PR 10a release notes:** `/Users/ashen/Desktop/poker_solver/docs/release_notes_v0.6.0.md`. §"Honest caveats" item #5 documents the deferral. Your work resolves this caveat in v0.6.1.
5. **The 12 fixture IDs (authoritative reference for F4):** `/Users/ashen/Desktop/poker_solver/ui/mock_solver_fixtures.py:611-625` (`_FIXTURE_BUILDERS` dict). The preset markers in `ui/views/spot_input.py` MUST match these IDs exactly — verify by direct cross-reference, do not invent.
6. **The PR 10a agent prompts (style reference):** `/Users/ashen/Desktop/poker_solver/docs/pr10_prep/agent_b_prompt.md` (Agent B owned the range matrix originally) — read for context on the multi-tag marker mistake, NOT for code to copy.
7. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim PR 10a + PR 10a.5 entries (if any).

## Default decisions LOCKED (do not deviate)

1. **Marker form: single-value `data-marker` props.** Replace the comma-separated `data-marker=foo,bar-baz` pattern at `ui/views/range_matrix.py:735` and `:844` with two separate `.props("data-marker=...")` chains, or use NiceGUI's `.mark(name)` shorthand which writes a single-value attribute. Verify with `User.find(marker="matrix-cell").elements` returning 169 cells.
2. **Pio RYG anchors: pure values.** `cell_rgb_for_action_freqs(fold, call, raise_)` returns `(r, g, b)` with anchors `(255, 0, 0)` for pure-fold, `(255, 255, 0)` for pure-call, `(0, 255, 0)` for pure-raise. **NOT** the existing `(220, 40, 40)` fade values in `cell_color()`. Leave `cell_color()` unchanged for CSS-string consumers — add the new function alongside.
3. **Palette constants: module-level tuples.** `DISPLAY_PALETTE = ((255, 0, 0), (255, 255, 0), (0, 255, 0))` in `ui/views/range_matrix.py`. `INPUT_PALETTE = ((255, 255, 255), (0, 100, 255))` (white→blue gradient) in `ui/views/spot_input.py`. Smoke 16 also accepts `STRATEGY_PALETTE` / `RANGE_INPUT_PALETTE` as alternate names — pick the primary form and keep consistent.
4. **Blocker overlay: CSS class, not inline style.** Apply `.classes("blocker-overlay")` to matrix cells where `summary.blocked` is truthy. The class name is what smoke 15 asserts; the CSS rule itself can be a one-liner (`opacity: 0.4; background-image: repeating-linear-gradient(...)`) added inline or to a `ui.add_head_html(...)` block.
5. **`pushfold-switch-button` is a STUB toast button.** Per backlog §4 sub-bullet: emit a toast linking to PR 11 push/fold view (no actual view switch in PR 10a.5). Marker is the conformance gate; behavior can be a `ui.notify("Push/fold mode coming in PR 11", type="info")` no-op.
6. **`oom-reduce-bet-sizes-button` is a remediation button.** Surface inside `run_panel._show_error` when `isinstance(runner.error, MemoryError)`. Wire it to a no-op or to a `state.config.bet_sizes_checked` mutation that drops one size — your call. The marker is the conformance gate.
7. **`progress-eta` is a marker on the existing ETA label.** `ui/views/run_panel.py:469` already computes ETA; just `.mark("progress-eta")` the label. Plus `SolveRunner.compute_eta()` exposed as a method returning the same calculation as a `float` (seconds-remaining) for the smoke 20 fast-path test.
8. **xfail decorator removal is the LAST step.** Sequence: implement all wire-ups → run smoke tests → confirm 20 / 20 green → remove the 7 `@pytest.mark.xfail` decorators in the SAME commit. Do not remove decorators before the corresponding wire-up lands.
9. **Version bump: v0.6.1 PATCH.** Do not edit `pyproject.toml` for the version; that bump happens at the commit / tag step downstream (orchestrator handles).
10. **No new third-party dependencies.** Standard library only; no new `pyproject.toml` rows. NumPy / NiceGUI already in deps.
11. **Worktree cwd:** `/private/tmp/poker_pr10a5`. All paths in this prompt are absolute; use them as-is.
12. **No version bump beyond v0.6.1.** If scope creeps beyond ~250 LOC or beyond the listed files, halt and flag a scope review.

## Public API contract (smoke tests depend on these signatures)

**Module-level constants:**
```python
# ui/views/range_matrix.py
DISPLAY_PALETTE: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]] = (
    (255, 0, 0),    # pure-fold anchor
    (255, 255, 0),  # pure-call anchor
    (0, 255, 0),    # pure-raise anchor
)

# ui/views/spot_input.py
INPUT_PALETTE: tuple[tuple[int, int, int], tuple[int, int, int]] = (
    (255, 255, 255),  # zero-weight anchor (white)
    (0, 100, 255),    # full-weight anchor (blue)
)
```

**New function:**
```python
# ui/views/range_matrix.py
def cell_rgb_for_action_freqs(fold: float, call: float, raise_: float) -> tuple[int, int, int]:
    """Pio-convention RYG additive blend.

    fold + call + raise_ should sum to ~1.0 (with tolerance).
    Returns (r, g, b) integers in [0, 255]. Anchors:
      pure-fold  -> (255, 0, 0)
      pure-call  -> (255, 255, 0)
      pure-raise -> (0, 255, 0)
    """
    ...
```

**New method on `SolveRunner` (in `ui/state.py`):**
```python
class SolveRunner:
    def compute_eta(self) -> float | None:
        """Return seconds-remaining estimate, or None if not yet computable.

        Same calculation as the inline ETA at run_panel.py:469. Exposed as a
        method so smoke 20 can assert eta > 0 without driving the UI through
        a full 30-second wait.
        """
        ...
```

**Markers added (smoke-test contract):**

| Marker / class | View file | Test gate |
|---|---|---|
| Per-cell single-value `matrix-cell-{cls}` | `ui/views/range_matrix.py:844` | smoke 1, 6, 7 |
| Per-cell single-value `combo-inspector-row-{combo}` | `ui/views/range_matrix.py:735` | smoke 7 |
| `blocker-overlay` CSS class on blocked cells | `ui/views/range_matrix.py` (`_cell_tag`) | smoke 15 |
| `expl-chart-linear-toggle` marker | `ui/views/run_panel.py:221-224` (Log scale checkbox) | smoke 17 |
| `oom-reduce-bet-sizes-button` marker | `ui/views/run_panel.py:506` (`_show_error`) | smoke 18 |
| `pushfold-switch-button` marker | `ui/app.py:294-302` or `ui/views/spot_input.py:373-380` (≤15 BB toast) | smoke 19 |
| `progress-eta` marker | `ui/views/run_panel.py:469` (ETA label) | smoke 20 |
| Preset markers `preset-{fixture_id}` exact match | `ui/views/spot_input.py` (cross-check vs `ui/mock_solver_fixtures.py:611-625`) | smoke 5 (F4) |

## Critical correctness items

### 1. NiceGUI `User.find(marker=...)` is single-value (the F1-F5 root cause)

NiceGUI's `User.find(marker="matrix-cell")` looks up a single attribute value. The committed code at `range_matrix.py:844` writes `props("data-marker=matrix-cell,matrix-cell-AKs")` as a comma-separated tag list — that's not how NiceGUI's marker lookup works. The fix is two separate `.props("data-marker=...")` chains OR using `.mark(name)` which writes a single-value attribute the test layer can resolve.

Verify after fix:
```python
# In a quick repl test
from nicegui.testing import User
# ...
assert len(user.find(marker="matrix-cell").elements) == 169
assert len(user.find(marker="matrix-cell-AKs").elements) == 1
```

### 2. F4 preset marker cross-check (the spot-input drift)

`ui/views/spot_input.py` emits preset markers per the 12 fixture IDs. Direct-read the canonical list from `ui/mock_solver_fixtures.py:611-625` (`_FIXTURE_BUILDERS` dict keys); confirm `spot_input.py`'s marker emission is byte-identical to these IDs (e.g., `preset-flop-k72r-100bb`, NOT a truncated `preset-flop-k72r`). If they drift, fix `spot_input.py` to match the fixture-side names. Do not rename fixtures.

### 3. Pure Pio anchors vs existing fade values

`cell_color()` at `range_matrix.py:408-410` computes `r = fold*220 + call*220 + raise_*40` — this is the existing fade convention and is **NOT** changed. Add `cell_rgb_for_action_freqs(fold, call, raise_)` as a **separate** function using **pure** Pio anchors (255 / 0 / 0 for red, 255 / 255 / 0 for yellow, 0 / 255 / 0 for green). Smoke 14 asserts a pure-fold cell is `(255, 0, 0) ± 2`. Don't blend the two — keep both functions, smoke 14 only consumes the new one.

### 4. xfail decorator removal sequencing

The seven `@pytest.mark.xfail` decorators at `tests/test_ui_smoke.py:452, 498, 531, 580, 620, 659, 683` carry the reason `"PR 10a.5 conformance pass: missing marker/constant per audit_report_10a.md should-fix N (...)"`. Remove ALL seven decorators (the `@pytest.mark.xfail(reason="...")` line above each test). Do NOT modify test bodies — only the decorator above each test. If any test fails after wire-up + decorator removal, that's a real bug — fix the wire-up, not the test.

### 5. `compute_eta()` smoke-20 fast-path

Smoke 20 (`test_long_solve_eta_appears_after_30s`) needs both the marker on the live ETA label AND a method on `SolveRunner` for the fast-path. Read the smoke 20 body (around `tests/test_ui_smoke.py:683+`) to confirm signature expectations; the method likely takes no args and returns `float | None`. The implementation can re-use the inline calculation at `run_panel.py:469` (factor out into a helper if helpful, but a method on `SolveRunner` is the API gate).

### 6. PR 11 file-overlap discipline

PR 11 is running in parallel on branch `pr-11-library-and-packaging` (in the shared tree `/Users/ashen/Desktop/poker_solver`). PR 11 rewrites `ui/views/library_browser.py` from scratch. **Your edits MUST NOT touch this file.** The merge conflict surface is zero by design — but only if you stay out of library_browser.py. Verify via `git diff --stat HEAD` before commit: that file must not appear in your diff.

### 7. No new tests

PR 10a.5 is a conformance pass, not a feature PR. The 20-smoke-test count is locked. Do not add helper tests, do not add new property tests, do not refactor existing tests beyond decorator removal. If a wire-up reveals a missing assertion, log it as a v0.6.2 follow-up — don't add it to v0.6.1.

## License-aware sourcing

**You may NOT extrapolate from training data.** If you "remember" how NiceGUI's `User.find` works, ground it in the smoke test bodies + the `nicegui.testing` source in the venv. When in doubt, write a small repl probe to verify before committing.

**No new dependencies.** Standard library + already-declared deps only.

**License compliance:** PR 10a.5 adds zero new third-party code. No attribution needed beyond what's already in v0.6.0.

## Quality bar

- **ruff clean:** `ruff check ui/` reports zero issues on touched files.
- **black clean:** `black --check ui/` reports no changes needed.
- **mypy strict-clean** on the touched ui/* files (the PR 10a baseline).
- **All 20 smoke tests pass.** Acceptance gate: `pytest tests/test_ui_smoke.py -v` shows `20 passed, 0 failed, 0 xfail, 0 skipped` (modulo `@pytest.mark.ui` skip if nicegui is not installed in the lint env — green-board with `pip install -e ".[ui]"`).
- **All existing tests still pass.** Run `pytest -x` to confirm.
- **Code size budget:** ~150-250 LOC net change across the five UI files + the test-file decorator removal. Stay within budget; over-runs indicate scope creep.
- **Zero diff outside owned files.** `git diff --stat HEAD` shows ONLY the files in §"Strict file ownership". No `library_browser.py`, no engine, no `pyproject.toml`.

## Verification commands (run before reporting done)

```bash
cd /private/tmp/poker_pr10a5

# 1. Lint + format on touched UI files
ruff check ui/views/range_matrix.py ui/views/spot_input.py ui/views/run_panel.py ui/state.py ui/app.py
black --check ui/views/range_matrix.py ui/views/spot_input.py ui/views/run_panel.py ui/state.py ui/app.py

# 2. Type-check (matches PR 10a baseline)
mypy --strict ui/views/range_matrix.py ui/views/spot_input.py ui/views/run_panel.py ui/state.py ui/app.py

# 3. Smoke tests green-board (the acceptance gate)
pip install -e ".[ui]"
pytest tests/test_ui_smoke.py -v
# Expected: 20 passed, 0 failed, 0 xfail.

# 4. No xfail decorators remain in test_ui_smoke.py
grep -n "^@pytest.mark.xfail" tests/test_ui_smoke.py
# Expected: empty output.

# 5. Marker single-value check (F1-F5)
python -c "
import re
src = open('ui/views/range_matrix.py').read()
# multi-tag pattern should be absent
multi = re.findall(r'data-marker=[a-z0-9-]+,[a-z0-9-]+', src)
assert not multi, f'multi-tag marker pattern still present: {multi}'
print('marker form: single-value OK')
"

# 6. Palette constants exist
python -c "
from ui.views import range_matrix, spot_input
assert hasattr(range_matrix, 'DISPLAY_PALETTE'), 'DISPLAY_PALETTE missing'
assert hasattr(spot_input, 'INPUT_PALETTE'), 'INPUT_PALETTE missing'
assert hasattr(range_matrix, 'cell_rgb_for_action_freqs'), 'cell_rgb_for_action_freqs missing'
r, g, b = range_matrix.cell_rgb_for_action_freqs(1.0, 0.0, 0.0)
assert (r, g, b) == (255, 0, 0), f'pure-fold should be (255,0,0), got ({r},{g},{b})'
r, g, b = range_matrix.cell_rgb_for_action_freqs(0.0, 0.0, 1.0)
assert (r, g, b) == (0, 255, 0), f'pure-raise should be (0,255,0), got ({r},{g},{b})'
print('palette + adapter OK')
"

# 7. SolveRunner.compute_eta exists
python -c "
from ui.state import SolveRunner
assert hasattr(SolveRunner, 'compute_eta'), 'SolveRunner.compute_eta missing'
print('compute_eta OK')
"

# 8. Library_browser.py untouched (PR 11 territory)
git diff --stat HEAD -- ui/views/library_browser.py
# Expected: empty output.

# 9. No engine diff (poker_solver/ frozen)
git diff --stat HEAD -- poker_solver/
# Expected: empty output.

# 10. No pyproject diff
git diff --stat HEAD -- pyproject.toml
# Expected: empty output.

# 11. Full test suite still passes
pytest -x 2>&1 | tail -20
```

If any step fails, fix and re-run before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag** — do not silently invent behavior.

## Reference-first rule

Before any technical claim, citation, or formula, check the local sources:
- The 12 fixture IDs: `ui/mock_solver_fixtures.py:611-625`.
- The xfail decorator anchors: `tests/test_ui_smoke.py` lines 452, 498, 531, 580, 620, 659, 683.
- The multi-tag drift site: `ui/views/range_matrix.py:735, 844`.
- The Pio RYG convention: documented in the smoke 14 test body + `pr10a_spec.md` §7.3.

Never extrapolate from training data when a local authoritative source exists.

## Report back format

When done, write a concise report (≤300 words) covering:

1. **Files modified with line counts.** Confirm net LOC is in the ~150-250 range; flag if over.
2. **Smoke-test result.** Paste `pytest tests/test_ui_smoke.py -v` summary tail. Confirm 20 / 20 green.
3. **F1-F5 marker fix.** Confirm single-value `data-marker` props applied at `range_matrix.py:735` and `:844`. Confirm `User.find(marker="matrix-cell").elements` returns 169 cells (paste the repl probe output).
4. **F4 preset cross-check.** Confirm `spot_input.py` preset markers match the 12 fixture IDs from `mock_solver_fixtures.py:611-625` exactly. List any drift you fixed.
5. **X1-X7 wire-ups.** One line each confirming `cell_rgb_for_action_freqs`, `DISPLAY_PALETTE` / `INPUT_PALETTE`, `blocker-overlay` class, `expl-chart-linear-toggle` marker, `oom-reduce-bet-sizes-button` button, `pushfold-switch-button` button, `progress-eta` marker, `SolveRunner.compute_eta()` are all in place.
6. **xfail decorator removal.** Confirm all 7 decorators removed at lines 452, 498, 531, 580, 620, 659, 683.
7. **Library_browser untouched.** Confirm `git diff --stat HEAD -- ui/views/library_browser.py` is empty.
8. **Zero engine / pyproject diff.** Confirm.
9. **Any spec ambiguity flagged.** The backlog flagged Pio anchor convention as the load-bearing one — confirm or escalate.
10. **Verification command tails.** Paste the final 5 lines of `pytest -x` showing the full suite still green.
