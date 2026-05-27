# LEG 6 — v1.3.1 ship plan (PR 19 + PR 20 bundle)

**Date:** 2026-05-23 (post-LEG 5) · **Status:** PRE-STAGED — fires when BOTH PR 19 + PR 20 gates clear.
**Worktree:** `/tmp/leg6-v1.3.1` (off `integration`).
**Pre-state:** integration `e22044d` · main `58b1ebd` (v1.3.0) · PR 19 SHA `973ba62` · PR 20 SHA TBD.

---

## 1. Cherry-pick order

1. **PR 19** (`973ba62`) — `ui/views/run_panel.py`, `ui/state.py`, `tests/test_ui_smoke.py`.
2. **PR 20** (`<pr20-sha>`) — `poker_solver/range_aggregator.py`, `tests/test_range_vs_range_aggregator.py`, `USAGE.md`, `CHANGELOG.md`, `pyproject.toml`, `poker_solver/__init__.py`.

Per integration sequencing strategy §3, PR 19 + PR 20 are pairwise disjoint — no textual overlap.

---

## 2. Ship sequence (paste-ready)

```bash
# 1. Worktree off integration
cd ~
git -C /Users/ashen/Desktop/poker_solver worktree add /tmp/leg6-v1.3.1 integration
cd /tmp/leg6-v1.3.1

# 2. Verify clean (expect: integration / e22044d)
git status && git rev-parse --abbrev-ref HEAD && git log -1 --oneline

# 3-4. Cherry-pick PR 19 then PR 20 (conflict => STOP + report)
git cherry-pick 973ba62
git cherry-pick <PR20_SHA>

# 5. Detect whether PR 20 included CHANGELOG + version bump
grep -E "^## \[1\.3\.1\]" CHANGELOG.md && echo "CHANGELOG present"
grep -E '^version = "1\.3\.1"' pyproject.toml && echo "pyproject bumped"
grep -E '__version__ = "1\.3\.1"' poker_solver/__init__.py && echo "__init__ bumped"

# 6a. If PR 20 did NOT include them: edit per §3 template, then:
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
git commit -m "chore(release): v1.3.1 — hero_player + v0.6.2 polish"

# 6b. If PR 20 included WRONG framing (claims S1 fix): rewrite per §3 then:
git add CHANGELOG.md && git commit -m "docs(changelog): honest framing — S4 fix only, S1 unresolved"

# 7-8. Tag + push integration to backup (private)
git tag -a v1.3.1 -m "v1.3.1 — hero_player + v0.6.2 polish"
git push backup integration && git push backup v1.3.1

# 9. Update main via LEG 1/2/3/5 worktree pattern off origin/main
cd ~
git -C /Users/ashen/Desktop/poker_solver fetch origin main
git -C /Users/ashen/Desktop/poker_solver worktree add /tmp/leg6-main origin/main -b main-leg6
cd /tmp/leg6-main
git cherry-pick 973ba62
git cherry-pick <PR20_SHA>
git cherry-pick <RELEASE_COMMIT_SHA>   # only if release was a separate commit
git push origin main-leg6:main && git push backup main-leg6:main

# 10-11. Push tag + create GitHub release (origin = public)
git push origin v1.3.1
gh release create v1.3.1 --repo amaster97/poker_solver \
  --title "v1.3.1 — hero_player + v0.6.2 polish" \
  --notes "PATCH. (a) hero_player parameter for defender position queries + position field (Option B stress test S4); (b) v0.6.2 PR 10a.5 polish (bet-size pruning clamp + ETA cleanup). Does NOT fix S1 (blueprint aggregator limit; requires Plan C / Option A)."

# 12. Worktree cleanup
cd ~
git -C /Users/ashen/Desktop/poker_solver worktree remove /tmp/leg6-v1.3.1
git -C /Users/ashen/Desktop/poker_solver worktree remove /tmp/leg6-main
git -C /Users/ashen/Desktop/poker_solver branch -D main-leg6 2>/dev/null || true

# 13. Verification (6-check)
cd /Users/ashen/Desktop/poker_solver && git fetch --all --tags
git log --oneline integration -3
git log --oneline origin/main -3
git tag -l 'v1.3.1'
git ls-remote --tags origin | grep v1.3.1
git ls-remote --tags backup | grep v1.3.1
gh release view v1.3.1 --repo amaster97/poker_solver | head -5
```

---

## 3. CHANGELOG v1.3.1 template (honest framing — use if PR 20 missing or claimed S1 fix)

```
## [1.3.1] - 2026-05-23

### Added — hero_player parameter for `solve_range_vs_range`
- Optional `hero_player: int = 0` (default preserves v1.3.0; backward compatible).
- Defender queries (`hero_player=1`) extract correct per-action frequencies instead of mirroring aggressor.
- New `position: str` field on `RangeVsRangeResult` (`"aggressor"` / `"defender"`).
- New test: `test_hero_player_1_defender_extraction` (BB-defends-vs-BTN-3bet).

### Fixed (v0.6.2 — PR 10a.5 items 2 + 3)
- `ui/views/run_panel.py`: clamp `bet_sizes_checked` pruning at min 1 size (could prune to zero).
- `ui/state.py`: delete dead `SolveRunner.compute_eta()`; refactor smoke 20 to exercise live `run_panel._compute_eta()`.

### Honest scope
- Resolves **S4** (defender MDF queries returning aggressor frequencies).
- Does **NOT** resolve **S1** (AA/KK checking K-high under heuristic FAIL) — fundamental to Option B per `range_aggregator.py:19-32`; per-hand solves are 1v1 Nash, not 1-vs-range. Plan C / Option A required.
- `USAGE.md` §5.2 caveats expanded.
```

---

## 4. Hard rules

- Autonomous push authorized — no user OK needed for normal pushes.
- DO NOT touch shared tree `/Users/ashen/Desktop/poker_solver` during the ship.
- Never `git add -A`; stage by explicit path. DO NOT modify `.gitignore`.
- Cherry-pick conflict: STOP + report (unexpected per integration sequencing §3).
- PR 20 with WRONG CHANGELOG framing (S1 claimed fixed): rewrite at Step 6b; flag in post-ship report.

## 5. Open dependencies

- **PR 20 must land first** — PR 19 is ready (`973ba62`); bundle ships together, not staggered.
- PR 20 acceptance: hero_player wired, `position` field on result, new test green, full suite green, no API break (default `hero_player=0`).
- Cherry-pick order reverses cleanly if PR 20 lands stale (disjoint file sets).

## 6. Post-ship

- Prune `PLAN.md` + memory of v1.3.1 markers; record LEG 6 in session log.
- PR 15/17/21 need no rebase — disjoint from PR 19/20 per integration sequencing §2.
