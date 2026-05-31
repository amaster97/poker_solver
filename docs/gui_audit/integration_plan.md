# Engine↔GUI Integration Plan (GUI-audit UI onto main's v1.11 fast engine)

Evidence-based plan (agent-produced 2026-05-30). Execute on an ISOLATED branch; safe to discard.

## Key facts (changed the strategy)
- **`main` LOCAL tip = `60591a3`** ("bet-size menu downstream remap — GUI controls, labels, library cache-key, CLI flags") on top of f69ec29. So the bet-size GUI downstream is ALREADY on main — `feat/ds-gui`/`feat/betsize-downstream` are landed (their worktree edits are byte-identical to `60591a3`). **No coordination needed; branch from main.**
- **`origin/main` is STALE (`2c13977`)** — the whole v1.11 engine + bet-size is LOCAL-ONLY, UNPUSHED. Integration is against LOCAL main; pushing is a separate concern.
- **Marquee RvR path needs NO hook work:** GUI default postflop = `solver_mode="true_nash"` → `_run_true_nash_rvr_path` → `solve_range_vs_range_nash` (vector-form CFR), which only fires on_progress at start/end + never honored mid-cancel. It exists on main with a compatible sig + the v1.11 perf (rayon/suit-iso/IE). So **RvR flop runs FAST on main with zero engine work.** The hooks gap only affects the DEV-GATED concrete path.
- Merge base of main & `fix/gui-audit-message-leaks` = `14673e3` (v1.10.0). GUI branch built on OLD engine; main has the v1.11 `crates/`.

## (1) Merge mechanics
Branch from main; do NOT merge f00666f directly (its `crates/` are the old tree). Either replay the GUI branch's UI-only commits dropping the engine commit `7568de4` (`feat(engine): Rust postflop hooks`), OR `git merge f00666f` then resolve engine-file conflicts to MAIN's side. Engine files MUST end exactly = main's: verify `git diff main -- crates/ poker_solver/hunl_solver.py poker_solver/solver.py poker_solver/hunl.py` is EMPTY on the integration branch.

**Conflict surface + resolution (5 UNION files — both branches edited):**
| File | main side (`60591a3`) | GUI side (`f00666f`) | Resolve |
|---|---|---|---|
| `ui/state.py` `Spot` | per-street `flop/turn/river_bet_fractions`, `raise_size_xs=(3.0,)`, wired into `to_hunl_config` | `rvr_mode`, `solver_mode="true_nash"`, `hero_player`, `locked_strategies`, `to_rvr_call_args`, SolveRunner RvR/chained/auto-range | **UNION** both field sets + both `to_hunl_config` bodies |
| `ui/state.py` `SolveRunner._dispatch_solve` | (no Rust-hook dispatch) | calls `solve_hunl_postflop_rust(...)` (does NOT exist on main) | **REWRITE** per §2 |
| `poker_solver/library.py` | `_canonicalize_spot`+`_bet_menu_hash`+schema v2 (per-street + raise_size_xs) | older | **take main's** + reapply GUI-only deltas |
| `ui/views/run_panel.py` | per-street bet-size controls + raise input | tier slider, RvR subtitle, STOP, theme | **UNION** |
| `ui/views/spot_input.py` | per-street bet-size UI | board picker, card graphics, auto-range, preset/reset refresh | **UNION** |
| `ui/app.py` | per-street control wiring | `_on_solve` RvR-force + dev-gate + chained dispatch | **UNION** (GUI dominates `_on_solve`; keep main's per-street Spot population) |
- GUI-only NEW files (`ui/views/_cards.py`, `_auto_range.py`, the chained_tab walkthrough, `tests/test_ui_auto_range.py`/`_clear_results.py`/`_node_matrix_p2p3.py`/`_preset_load_refresh.py`, etc.) → take GUI's wholesale.
- **Deleted-test trap:** the GUI branch DELETES engine-era tests main keeps (`test_bet_menu_diff.py`, `test_v1_10_3_flop_diff.py`, `test_ui_c_bet_sizes.py` — the last is ADDED by `60591a3`). Do NOT let GUI's deletions remove main's bet-size tests; keep main's.

## (2) Engine-call reconciliation — `SolveRunner._dispatch_solve` HUNL-postflop branch (Option A degrade)
Today it calls `solve_hunl_postflop_rust(..., on_progress, should_stop)` + `rust_postflop_available()` — NEITHER exists on main. Rewrite the postflop branch to route through main's FAST hookless binding via the canonical dispatcher:
```python
from poker_solver.solver import solve as canonical_solve
return canonical_solve(game, iterations, backend="rust",
    locked_strategies=locked_strategies, force_tree_solve=force_tree_solve,
    target_exploitability=target_exploitability, seed=seed)  # NO on_progress/should_stop
```
(→ `solver._solve_rust` → `_rust.solve_hunl_postflop` FAST + `_compute_exploitability_rust`.) UX degrade (UI-side only): progress = indeterminate spinner ("solving…", set status running + target_iterations, the post-return block appends the final exploitability point); cancel = coarse thread-abandon (set `_stop_event`, status "stopped", discard the daemon's result). **This branch is reached ONLY when the dev-gate is ON** (prod forces rvr_mode=True). `_run_true_nash_rvr_path` / `_run_chained_path` / legacy `_run_rvr_path` need **NO change** (their sigs match main). Do NOT add Rust hooks (Option B) for the first integration.

## (3) Guard removal + tier raise
- **Remove `SolveTooLargeError`** + `estimate_postflop_tree_cost` + `exceeds_tree_budget` + the chained-flop wrapper + the raise site in `SolveRunner.start` (all GUI-branch-only; main has none). Flops are tractable on the fast engine. (No test references the guard symbols — the 2 pr24b reds are bet-size-shape-sensitive, see below.)
- **Raise postflop tier:** `run_panel.py` `_DEFAULT_TIER = "Standard"` (500) → **"Tight"** (1000) per the convergence finding (per-hand EVs degenerate below ~1000it). Fast engine keeps 1000 iters under Marcus's <30s. If a marquee flop overruns, make it a postflop-only override.

## (4) Build (per build-env)
`git worktree add <worktrees>/gui-integration integration/<branch>` then:
`export PATH="$HOME/.cargo/bin:$PATH"; VIRTUAL_ENV=<repo-root>/.venv PATH="$HOME/.cargo/bin:$PATH" <repo-root>/.venv/bin/maturin develop --release` (no crates change → `.so` bit-identical to main's; could even copy main's `.so` as a shortcut, but a clean build is the gate).

## (5) Test gates
1. **Marquee RvR flop FAST + non-degenerate** (the headline): default postflop spot (rvr_mode=True, true_nash, Tight=1000) routes to `solve_range_vs_range_nash`, returns <30s, per-combo strategies non-uniform / EVs differ.
2. **Full UI suite** (incl. all GUI-branch-only test files); fix the **2 `test_ui_pr24b.py` reds** empirically (run `-v`, update expected `to_hunl_config` shapes to main's per-street output, poker-justified — mirrors `60591a3`'s pattern for 5 other tests).
3. **Engine tests intact** (must match main exactly — engine untouched): the v1.10 canonical diff, vector-rayon diff, hunl core, etc. + `cargo test -p cfr_core`.
4. ruff + mypy clean.

## (6) Risks / safe-vs-coordinate
- Safe-solo: the Option-A degrade, guard removal, tier raise, UNION merge, build (no crates change).
- Care: the 2 pr24b reds (identify empirically, poker-justify the new asserts); the deleted-test trap; `origin/main` stale (integration is local-main only — DO NOT push to origin without confirming the engine push first).
- The "hooks gap" is cosmetic for the path users hit (marquee RvR), real only for the dev-gated concrete path.
