# LEG 9 — v1.4.0 ship plan (PR 21 node-locking + PR 22 asymmetric-contributions bundle)

**Date:** 2026-05-23 · **Status:** PRE-STAGED — fires when BOTH PR 21 + PR 22 audit-clear.
**Worktree:** `/tmp/leg9-v1.4.0` (off `integration`).
**Pre-state:** integration TBD (post v1.3.2 LEG 7) · main TBD · PR 21 SHA TBD on `pr-21-node-locking` · PR 22 SHA TBD (implementer not yet spawned).

---

## 1. Sequencing — BUNDLE vs STAGGER

**Recommendation: BUNDLE as v1.4.0** when both PRs gate-clear simultaneously. Otherwise ship whichever lands first as v1.4.0; the other → v1.4.1.

Bundle rationale: together they cover Daniel W3.1-W3.4 ("Daniel persona unlock"). Single .dmg, single CHANGELOG, single Phase 3 retest. Staggering forces two persona re-runs per integration sequencing §6.5.

Stagger fallback: PR 21 ETA 3-5 days (active worktree); PR 22 implementer not yet spawned (2.5-3.5 days). If PR 21 audits clean while PR 22 mid-flight, ship PR 21 alone.

---

## 2. Cherry-pick sequence (bundle)

```bash
# 1. Worktree off integration
cd ~ && git -C /Users/ashen/Desktop/poker_solver worktree add /tmp/leg9-v1.4.0 integration
cd /tmp/leg9-v1.4.0
git status && git log -1 --oneline   # verify integration tip post-v1.3.2

# 2. Cherry-pick PR 22 FIRST (smaller scope; touches initial_state only)
git cherry-pick <PR22_SHA>

# 3. Cherry-pick PR 21 SECOND (touches dcfr loop + solver.py)
git cherry-pick <PR21_SHA>

# 4. Smoke tests — Daniel workflows + diff tests + full suite
pytest -x tests/test_asymmetric_contributions.py tests/test_node_locking.py tests/test_node_locking_diff.py
pytest -x -m "not slow"
cargo test --all
maturin develop --release && python -c "from poker_solver import solve; print('rust binding OK')"

# 5. CHANGELOG v1.4.0 (per §4) + version bump 1.3.2 -> 1.4.0
${EDITOR:-vim} CHANGELOG.md pyproject.toml poker_solver/__init__.py
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
git commit -m "chore(release): v1.4.0 — node-locking + asymmetric-contributions"

# 6. Tag + push integration to backup (private)
git tag -a v1.4.0 -m "v1.4.0 — Daniel persona unlock (node-locking + facing-bet)"
git push backup integration && git push backup v1.4.0

# 7. Update main via standard LEG pattern
cd ~ && git -C /Users/ashen/Desktop/poker_solver fetch origin main
git -C /Users/ashen/Desktop/poker_solver worktree add /tmp/leg9-main origin/main -b main-leg9
cd /tmp/leg9-main
git cherry-pick <PR22_SHA> && git cherry-pick <PR21_SHA> && git cherry-pick <RELEASE_COMMIT_SHA>
git push origin main-leg9:main && git push backup main-leg9:main

# 8. Push tag + GitHub release Latest
git push origin v1.4.0
gh release create v1.4.0 --repo amaster97/poker_solver --latest \
  --title "v1.4.0 — Node-locking + facing-bet subgames" \
  --notes-file /tmp/leg9-v1.4.0/CHANGELOG_v1.4.0_excerpt.md

# 9. Cleanup + 6-check
cd ~ && git -C /Users/ashen/Desktop/poker_solver worktree remove /tmp/leg9-v1.4.0
git -C /Users/ashen/Desktop/poker_solver worktree remove /tmp/leg9-main
git -C /Users/ashen/Desktop/poker_solver branch -D main-leg9 2>/dev/null || true
cd /Users/ashen/Desktop/poker_solver && git fetch --all --tags
git log --oneline integration -4 && git log --oneline origin/main -4
git tag -l 'v1.4.0' && git ls-remote --tags origin | grep v1.4.0
gh release view v1.4.0 --repo amaster97/poker_solver | head -5
```

---

## 3. Conflict resolution

Per integration sequencing §3, PR 21 vs PR 22 is **unlikely** — files are disjoint:

- **PR 21**: `poker_solver/{dcfr.py,solver.py,hunl_solver.py,range_aggregator.py}` + `crates/cfr_core/src/{dcfr.rs,hunl_solver.rs,lib.rs}` + new tests.
- **PR 22**: `poker_solver/hunl.py` only (`initial_state` + `HUNLConfig.__post_init__`) + new test.

PR 22 first (smaller blast radius). Conflict at step 3: preserve BOTH — `locked_strategies` is additive to `initial_state` fix. STOP + report if non-mechanical.

---

## 4. CHANGELOG v1.4.0 (HONEST framing)

```
## [1.4.0] - 2026-05-23

### Added — Node-locking (PR 21)
- `locked_strategies: dict[str, list[float]] | None` kwarg on `solve()`,
  `solve_hunl_postflop()`, `solve_hunl_preflop()`.
- Per-infoset lock: regret + strategy_sum updates skipped at locked nodes;
  children still update against the lock.
- Hand-class expansion in `range_aggregator.py` (`"AA": [0.0, 1.0]`).
- <10% overhead; bit-identical to v1.3.x when lock dict empty.

### Fixed — Asymmetric initial contributions (PR 22)
- `HUNLPoker.initial_state` honors `cfg.initial_contributions` postflop
  (was hardcoded `to_call=0`, `cur_player=1`).
- `HUNLConfig.__post_init__` raises `ValueError` on negative / over-stack
  contributions (previously segfaulted in Rust backend).

### Persona — Daniel unlock
- W3.1 villain-never-bluffs · W3.2 GTO-vs-actual · W3.3 merged range
  · W3.4 MDF half-pot (executable via facing-bet construction).

### Honest scope
- BUNDLED for Daniel W3.1-W3.4 ship.
- GUI deferred to v1.4.1 (JSON textbox only in v1.4.0).
- Heavy-lock convergence may be softer than two-sided Nash (spec R1).
- W3.5 tree visualizer remains GUI-only, out of scope.
```

---

## 5. Post-ship retest (test→fix→retest)

Spawn retest agent after verification:

- **W3.1** — lock villain river-bet → 0; assert hero fold frequency monotone-tighter than unlocked.
- **W3.2** — GTO vs locked-villain; assert EV delta sign matches leak direction.
- **W3.3** — merged range via `solve_range_vs_range` + `locked_classes`.
- **W3.4** — `initial_contributions=(1000, 500)`; assert BB defense in [55%, 80%].
- **Phase 2b** W2b.1 / W2b.2 / W2b.5 — Plan C true-Nash may improve them (verify; don't extrapolate).
- Record in `docs/pr13_prep/v1_4_0_retest.md` (HONEST pre/post per workflow).

---

## 6. LEG 10 follow-up (.dmg)

Rebuild `Poker-Solver-1.4.0-universal2.dmg` per `docs/pr11_prep/leg8_repackage_v1_3_2.md`. Smoke test: one locked solve + one facing-bet solve to confirm `_rust.so` is v1.4.0.

---

## 7. Hard rules

- Autonomous push authorized.
- DO NOT touch shared tree during ship; stage by explicit path; no `git add -A`; no `.gitignore` edits.
- Cherry-pick conflict beyond mechanical → STOP + report.
- Persona Phase 3 re-run REQUIRED after MINOR (integration sequencing §6.5).
- PR 22 still mid-flight at gate time: ship PR 21 alone as v1.4.0; PR 22 → v1.4.1.
