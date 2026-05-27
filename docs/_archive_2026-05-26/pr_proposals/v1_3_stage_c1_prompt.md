# v1.3 Stage C1 Implementer Prompt — numpy slab BR walk (pure Python)

**Use when:** the Phase 1 W1.5 turn-subgame exploitability walk is the bottleneck (SIGKILL@900s). Stage C1 is the pure-Python data-structure rewrite from `docs/pr_proposals/v1_3_plan_c_verification.md` §5-6: a 22.4× walk speedup is achievable without leaving Python by swapping `dict[str, list[float]]` for dense `numpy.ndarray` slabs. Stage C2 (Rust port) is deferred to v1.4 if additional perf is needed; C1 ships **as v1.3.1 (PATCH)** because there is no public API change — just faster internals.

---

## Agent Prompt (paste-ready)

You are the implementer for **PR 18 — v1.3 Stage C1: numpy slab BR walk**. This is the fast safety net; pure Python; **no new compiled artifacts; no Rust touches**.

### Worktree setup

```bash
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/pr-18-stage-c1 \
  origin/main -b pr-18-stage-c1-numpy-slabs
```

Operate exclusively inside that worktree. Never branch-switch in the shared tree (MEMORY `[No concurrent branch ops]`).

### Read first (in order)

1. `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_3_plan_c_verification.md` — microbench evidence (22.4× walk-only, 51.9× total in pure Python).
2. `/Users/ashen/Desktop/poker_solver/poker_solver/solver.py` — `_compute_exploitability` and the `_best_response_value` / `_collect_infosets` hot path (lines 190-341 today).
3. `/tmp/plan_c_microbench.py` — the reference numpy pattern that achieved 22.4×. The Pattern B section (`pattern_b_dense_slab`) is the template: `slab.max(axis=1)` + `np.dot(reach, best)`.

### Scope

1. **Rewrite the inner exploitability walk in pure Python with numpy 2D arrays.** Replace `dict[infoset_key_str, list[float]]` with a `numpy.ndarray` of shape `(n_infosets, n_actions)` for strategy and `(n_combos,)` for reach probabilities (per-infoset, per-player as needed).
2. **Strategy slab:** build an `infoset_key_str → row_index` translation map at solve-start; reuse the existing tree numbering where available. Slab dtype `float64` to preserve diff-test tolerances against the existing Python oracle.
3. **Range slab:** dense `numpy.ndarray` of reach weights per combo, replacing per-combo dict storage.
4. **Vectorized BR:** for each `target_player`, compute per-infoset action values across all combos in one numpy op — `action_values = slab.max(axis=action_axis)` followed by `np.dot(reach, best)` — mirroring Pattern B in `/tmp/plan_c_microbench.py:117-126`.
5. **Preserve the existing API.** `exploitability()` and `_compute_exploitability(...)` signatures are unchanged; SolveResult contract is unchanged; only internals are faster. `SolveResult.average_strategy: dict[str, list[float]]` (`solver.py:22`) remains the on-disk format — slab is in-memory pre-compute.
6. **NumPy dep:** already a direct dep (`pyproject.toml:19` — `numpy>=1.24`). No change needed; just verify on the worktree HEAD.

### Acceptance gates (all load-bearing)

- `python -m pytest tests/test_dcfr_diff.py tests/test_kuhn_dcfr.py tests/test_leduc_dcfr.py tests/test_leduc_diff.py -x` — must all pass (Python tier correctness).
- `python -m pytest tests/test_river_diff.py -x` — must pass (Brown's MIT solver parity).
- **Diff test (new):** old `_best_response_value` (kept as oracle, gated behind a flag) vs numpy version — bit-equivalent within `1e-9` BB/hand on all five `v1_3_range_vs_range.md §3` fixtures.
- **Perf gate:** Phase 1 W1.5 (turn subgame with empty `initial_hole_cards`) completes in **< 60 s end-to-end** (currently 900 s SIGKILL).
- All other existing suites stay green (PR 6/7/9 + PR 10b smoke + persona Phase 1-2 passing workflows).

### Honest measurement

- Run W1.5 bench **3×**; report **median** (and min/max).
- Compare: pre-Stage-C1 baseline (current `origin/main`) vs post-Stage-C1 (this PR), same machine identity in `benches/`.
- Commit message and CHANGELOG cite **measured numbers, not extrapolation** (MEMORY `[Don't extrapolate]`).
- If observed walk speedup `< 10×` (microbench predicted 22×), document the gap and root-cause it in the PR report before claiming the perf gate.

### Time budget

- 1-2 days realistic per `v1_3_plan_c_verification.md` §6. If exceeding 3 days: stop, document partial state, escalate to orchestrator.

### Honest framing for CHANGELOG (under `[1.3.1] - YYYY-MM-DD`)

- Pure Python; no compiled artifacts.
- Resolves Phase 1 W1.5 timeout AND v1.3.0 Option B aggregator becomes practically faster.
- Stage C2 (Rust port) deferred to v1.4 if needed.
- License clean: numpy is BSD-3; no AGPL deps.

### Hard rules

- Operate IN the worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-18-stage-c1`.
- Never `git add -A`. Stage specific files.
- DO NOT push or merge — orchestrator ships later.
- DO NOT modify `.gitignore`.
- DO NOT modify the Rust crates — pure Python only.
- "Robust and correct" non-negotiable: any tolerance failure on existing diff tests is STOP-and-report.

### Versioning

- Ship as **v1.3.1 (PATCH)** — no public API change.
- Add `## [1.3.1] - <today>` CHANGELOG entry above `[1.1.0]`.

### Deliverables

- `poker_solver/solver.py` (numpy slab BR internals; preserved oracle path behind a flag for diff-testing).
- `tests/test_exploitability_diff_numpy.py` (new bit-equivalence diff test).
- `CHANGELOG.md` (`[1.3.1]` entry).
- `docs/pr18_prep/pr_report.md` (3-run W1.5 numbers, diff-test max delta across 5 fixtures, gate status).

Report back: median W1.5 wall-clock pre-vs-post, max absolute diff-test delta across all 5 fixtures, and confirmation that all listed test suites pass on the worktree HEAD.
