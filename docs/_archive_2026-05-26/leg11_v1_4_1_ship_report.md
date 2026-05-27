# LEG 11 — v1.4.1 ship report

**Date shipped:** 2026-05-23
**Plan:** `docs/leg11_v1_4_1_ship_plan.md`
**Source PR:** PR 22 (asymmetric initial contributions) on branch
`pr-22-asymmetric-contributions` in worktree
`/Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric` at SHA `1a72b20`.

---

## 1. Ship outcome

| Field | Value |
|---|---|
| **Tag** | `v1.4.1` |
| **Tag object SHA** | `7628998d5c291f773002c63c9ad64fa22c63159b` |
| **Commit SHA (origin/main)** | `89a124b91271ad9da8467a5e0f5181b6b4c1e616` |
| **Release URL** | https://github.com/amaster97/poker_solver/releases/tag/v1.4.1 |
| **Release type** | PATCH (1.4.0 -> 1.4.1) |
| **Pushed at** | 2026-05-23 (release published 09:19:08 UTC) |
| **Bump rationale** | Bug fix (Fix A) + robustness guard (Fix B) + bundled engine fix (over-shove refund); no public API change |

---

## 2. Cherry-pick log

Cherry-picked into a fresh detached-HEAD worktree
(`/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.1`) based on `main`
at `166d2b8` (v1.4.0), to isolate the `_rust.so` rebuild from the shared
working tree where other agents were live-using v1.4.0 binaries.

| Source SHA (PR 22) | Cherry-picked SHA (on main) | Subject |
|---|---|---|
| `9e574fb` | `ceff9bb` | PR 22: asymmetric initial-contributions for facing-bet subgames (v1.4.1) |
| `1a72b20` | `89a124b` | PR 22 follow-up: route hole-deal to facing-bet player |

No conflicts. PR 22 touched `poker_solver/hunl.py`, `crates/cfr_core/src/hunl.rs`,
`poker_solver/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, and new file
`tests/test_asymmetric_contributions.py` — disjoint from v1.4.0's node-locking
surface (`dcfr.py`, `solver.py`, `hunl_solver.py`, etc.).

CHANGELOG.md preserved a single `## [1.4.0]` entry; the `## [1.4.1]` block
appeared at line 16, the `## [1.4.0]` block at line 67. No edits to the
v1.4.0 block.

---

## 3. Build + smoke-test log

Rust binding rebuilt in the ship worktree (NOT in the shared tree):

```
maturin develop --release
  Compiling cfr_core v0.5.0 (/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.1/crates/cfr_core)
  Finished `release` profile [optimized] target(s) in 8.10s
  Built wheel for CPython 3.13 ... poker_solver-1.4.1-cp313-cp313-macosx_11_0_arm64.whl
  Installed poker_solver-1.4.1
```

Version verification: `python -c "import poker_solver; print(poker_solver.__version__)"`
prints `1.4.1`. Rust binding path resolves to the ship worktree's local
`_rust.cpython-313-darwin.so` — confirming isolation from the shared tree.

Test results in ship worktree:

| Test suite | Result |
|---|---|
| `tests/test_asymmetric_contributions.py` | **14/14 PASS** (0.52s) |
| `tests/test_dcfr_diff.py` + `tests/test_exploit_diff.py` + `tests/test_range_vs_range_aggregator.py` + `tests/test_node_locking.py` | **50/50 PASS** (119.03s) |

---

## 4. Aggregator-asymmetric smoke verdict

**PASS.** The aggregator (`solve_range_vs_range`) threads
`initial_contributions` through to per-hand solves correctly. Verified by
patching `HUNLPoker.initial_state` to log state on each aggregator-driven
solve:

```
[trace #1] n_hole_cards=2, to_call=200, cur=1, contrib=(600, 400), cfg.ic=(600, 400)
[trace #2] n_hole_cards=2, to_call=200, cur=1, contrib=(600, 400), cfg.ic=(600, 400)
[trace #3] n_hole_cards=2, to_call=200, cur=1, contrib=(600, 400), cfg.ic=(600, 400)
[trace #4] n_hole_cards=2, to_call=200, cur=1, contrib=(600, 400), cfg.ic=(600, 400)
```

Inspection of `poker_solver/range_aggregator.py:609` confirms the
mechanism: the aggregator uses `replace(config_template, initial_hole_cards=hole_cards)`
to build per-hand `sub_config`. Only `initial_hole_cards` is overridden;
`initial_contributions` flows through unchanged from `config_template`.
No silent drop of asymmetric contributions observed. No follow-up PR
needed for the aggregator on this axis.

---

## 5. Push log

```
git push origin HEAD:main
  To https://github.com/amaster97/poker_solver.git
     166d2b8..89a124b  HEAD -> main

git push origin v1.4.1
  To https://github.com/amaster97/poker_solver.git
   * [new tag]         v1.4.1 -> v1.4.1

git ls-remote origin v1.4.1
  7628998d5c291f773002c63c9ad64fa22c63159b refs/tags/v1.4.1
```

---

## 6. GitHub release

- **URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.4.1
- **Title:** "v1.4.1: Asymmetric Contributions"
- **Marked Latest:** YES (gh `--latest`)
- **Notes content:** Public-OK per `feedback_public_repo_hygiene.md` —
  no PII, no `/Users/ashen/...` paths, no session IDs, no agent IDs, no
  emails. Honest framing on scope: PATCH; symmetric callers unchanged;
  Rust `.so` rebuilt; heavy-lock + asymmetric interaction not separately
  exercised.

---

## 7. Retest queue — ready to fire

Per LEG 11 plan §5, three persona retests are ready for spawn now that
v1.4.1 is live. Each is a facing-bet workflow that was structurally
blocked pre-v1.4.1.

| Retest | Persona | Spec line | Expected post-fix |
|---|---|---|---|
| **W3.4 — MDF half-pot c-bet** | Daniel | `persona_acceptance_spec.md` line 59 | BB defended in [55%, 80%] (MDF target ~66.7%). Pre-fix returned opening strategy with `fold=0, call=0`. |
| **W2.3 — KK on Q-high vs c-bet range** | Sarah | line 45 | Mixed fold/call/raise strategy with sensible call frequency on KK. Pre-fix: aggregator with asymmetric contributions returned engine state with `to_call=0`. |
| **W1.2 — JJ on As Tc 5d Jh 8s vs pot** | Marcus | line 31 | Non-degenerate call frequency, MDF heuristic (~50%) bluff-catch. Pre-fix: workflow blocked entirely. |

Additional optional retests:

- **W3.5 polarization** (monotone flop) — line 61. Now executable end-
  to-end since the facing-bet construction is fixed; assert polarized
  betting range on `Ah 7h 2h`.
- **v1.4.0 Daniel retest re-fire** — `docs/pr13_prep/v1_4_0_daniel_retest.md`
  re-run with v1.4.1 build to confirm node-locking + asymmetric
  contributions don't interact pathologically.

**Spawn signal:** READY. All three retests independent — fan-out in
parallel per `feedback_parallel_agents.md`.

---

## 8. Cleanup

- Ship worktree `ship-v1.4.1` removed after the ship completed.
- Shared tree at `/Users/ashen/Desktop/poker_solver` will pick up the
  new `origin/main` + `v1.4.1` tag on its next `git fetch` operation.
- The shared tree's local `main` branch ref is stale (still at `166d2b8`).
  When the user / next agent runs in the shared tree, a `git fetch origin && git pull --ff-only`
  on main brings it forward to `89a124b`.
- Shared tree's `_rust.so` is still the v1.4.0 build — preserved
  intentionally so other agents in flight (slider measurement, river
  parity investigation, W4 retests) keep using the stable v1.4.0
  binary they started with. After their work completes, the next
  full-tree `maturin develop --release` will pick up v1.4.1.

---

## 9. Risk callouts hit/missed

| Plan risk | Outcome |
|---|---|
| A. PR 22 touches `solver.py`? | NO (as predicted). No conflict. |
| B. Rust `_rust.so` rebuild gate | RESPECTED. Rebuilt in isolated worktree before any pytest. |
| C. CHANGELOG conflict zone | NO conflict. v1.4.1 block above v1.4.0 block; single v1.4.0 entry preserved. |
| D. Worktree path naming | Used correct path `/Users/ashen/Desktop/poker_solver_worktrees/pr-22-asymmetric`. |
| E. Implementer status | At ship time PR 22 had two commits (`9e574fb`, `1a72b20`); both cherry-picked. |
| F. Symmetric regression | All existing regression suites pass. |
| G. Stale `.so` masking Fix A | MITIGATED — isolated ship worktree, fresh `maturin develop --release`. |
| H. `http.postBuffer` | Push succeeded without buffer issue. |
| I. `crates/cfr_core/Cargo.toml` version | `version = "0.5.0"` — workspace crate version unchanged (no per-crate bump needed). |
| J. Push hygiene | All sanitization gates green. |

---

## 10. Authorization trace

Per `feedback_pr10a5_autonomous_commit.md` 2026-05-23 expansion: audit-
cleared PRs ship end-to-end autonomously (commit + merge + integration
push + main push to origin). PR 22 was audit-cleared (14/14 new tests,
13/13 cargo, clippy + ruff clean). No force-push, no branch deletion,
no Type C-CRITICAL findings, no major design decisions. Ship executed
within authorization envelope.
