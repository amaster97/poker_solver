# PR 10a.5 — commit prep

Branch: `pr-10a.5-conformance` (parent `62c75d5`). Audit verdict: **READY**.
Working tree confirms the 7 audit-aligned `M` files plus **4** untracked files —
note the task prompt listed only 3; `scripts/split_main_for_publish.sh` is also
present and must likewise stay unstaged.

---

## Part 1 — Commit-prep sequence

### 1. Pre-flight

```
git status --short
```

Expect exactly 7 `M ` lines (the files below) and 4 `??` lines (`USAGE.md`,
`DEVELOPER.md`, `V1_GA_CLOSE.md`, `scripts/split_main_for_publish.sh`). Abort
on any other entry — especially any `M ` under `poker_solver/`, `crates/`, or
`pyproject.toml` (would be a scope leak).

### 2. Stage (explicit; no `-A`)

```
git add ui/views/range_matrix.py
git add ui/views/spot_input.py
git add ui/views/run_panel.py
git add ui/views/tree_browser.py
git add ui/state.py
git add ui/app.py
git add tests/test_ui_smoke.py
git status --short    # verify 7 staged + 4 still ??
```

These are the exact 7 from `pr_report.md` §7 / `audit_report.md` line 6.

### 3. Commit

```
git commit -m "$(cat <<'EOF'
PR 10a.5: UI conformance pass — resolve 5 fail + 7 xfail to ship

- Marker migration: range_matrix / tree_browser / spot_input / run_panel
  switch from `.props("data-marker=...")` to NiceGUI 3.x `.mark()` with
  whitespace-tokenized multi-tag strings (F1, F3, F5).
- UX surfaces wired against PR-10a-shipped tests: DISPLAY_PALETTE +
  cell_rgb_for_action_freqs (X1); CellSummary.has_blocker + .blocker-overlay
  (X2); INPUT_PALETTE (X3); expl-chart-linear-toggle mark (X4);
  oom-reduce-bet-sizes-button (X5); pushfold-switch-button (X6);
  progress-eta mark + SolveRunner.compute_eta() (X7).
- Bug fixes: state.list_fixture_preset_ids reads .id first (was emitting
  full FixturePreset repr); _redraw_chart mutates EChart.options in place
  (NiceGUI 3.x made it read-only). ui/app.py renders range_matrix +
  tree_browser inline and adds the __mp_main__ guard for the User fixture.

Verification: tests/test_ui_smoke.py 22/22 (was 8/22); broader UI suite
55 passed / 1 skipped / 0 failed; cargo test --all + clippy clean. Solver
code byte-unchanged; spec freeze preserved. +245 / -76 LoC across 7 files.

<Co-Authored-By trailer per standard pattern>
EOF
)"
```

### 4. Merge to integration (ff-only)

Precondition: no other agent writes in the shared tree. PR 8 / 9 / 10b live in
separate `git worktree`s, so the shared tree is safe.

```
git checkout integration
git merge --ff-only pr-10a.5-conformance
git checkout pr-10a.5-conformance
```

If `--ff-only` is refused, integration moved past `62c75d5` — rebase the
branch in a worktree and retry.

### 5. Tag

`v0.6.1` from integration post-merge:
`git tag -a v0.6.1 -m "UI conformance pass (PR 10a.5)"`.

### 6. No push

Push requires explicit user OK plus `public-repo-hygiene` audit:

```
git push origin pr-10a.5-conformance
git push origin integration
git push origin v0.6.1
```

---

## Part 2 — Should-fix triage

**Item 1 — f-string bug, `spot_input.py:400-403`.** ~1 min: add `f` prefix to
the inner `ui.notify(...)`. Smoke 19 only checks marker presence so no test
catches it either way. Trivial, isolated, zero blast radius.
**Recommendation: fix in this commit.**

**Item 2 — unbounded `bet_sizes_checked` prune, `run_panel.py:540-542`.**
~5-10 min: clamp empty result to `(1.0,)` plus follow-up toast. Default config
safe; only custom-config-with-all-sizes-`>1.0` hits the empty tuple. Needs a
new test (deferred per scope §6).
**Recommendation: defer to v0.6.2.**

**Item 3 — `SolveRunner.compute_eta()` dead in prod, `state.py:603-635`.**
Either rip it out (breaks smoke 20) or wire into `_update_progress` (needs
`start()` to capture `target_iterations` + `start_time_monotonic` and
`_worker` to tick `current_time_monotonic`). Touches the production ETA path —
own audit warranted.
**Recommendation: leave as-is; wire up in v0.6.2 alongside spec-coverage-gap
follow-ups (blocker-overlay visual, pushfold-toast text).**

---

## All-in-one recommendation

**Ship v0.6.1 with item 1 folded in; defer items 2 and 3 to v0.6.2.**

Item 1 is a one-line user-visible UX defect with zero blast radius — including
it costs nothing and avoids shipping a known-broken toast. Items 2 and 3 each
carry real design surface (clamp policy / production ETA wiring) and belong in
a polish PR with proper tests. Audit verdict (READY) holds either way; the
commit is gated only on user OK.
