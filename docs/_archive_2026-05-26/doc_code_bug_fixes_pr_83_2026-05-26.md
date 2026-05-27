# PR #83 (GitHub PR #44): doc code-bug fixes report

**Date:** 2026-05-26
**Source verification:** [`docs/usage_path_verification_user_docs_2026-05-26.md`](usage_path_verification_user_docs_2026-05-26.md) (Agent B)
**PR URL:** https://github.com/amaster97/poker_solver/pull/44
**Branch:** `pr-83-doc-code-bug-fixes`
**Worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-83-doc-code-bugs`

## Scope

Surgical fixes to three executable-code bugs plus one stale CLI claim in user-facing docs. **Files touched (committed):** `README.md`, `USAGE.md`. **Files NOT touched** (coordination with in-flight PRs): pyproject, scripts, Rust code, USAGE header, CHANGELOG, FINAL_PRE_SIGNON_AUDIT, README L14 version header.

The proposed README draft (`docs/README_proposed_update_2026-05-23.md`) carries the same Range/iters bugs but lives only on the private `integration` branch (commit `3475ca9` "private-only" accumulator). Left to be patched on the private mirror when next touched — not part of this public-main PR per public-repo hygiene.

## Fixes applied

### Fix 1: `Range("AA, KK, AKs")` → `parse_range(...)` (README.md L132)

**Before:**
```python
hero, villain = Range("AA, KK, AKs"), Range("QQ-99, AKo")
agg = solve_range_vs_range(template_config, hero, villain, iterations=200)
```

**After:**
```python
hero, villain = parse_range("AA, KK, AKs"), parse_range("QQ-99, AKo")
agg = solve_range_vs_range(template_config, hero, villain, iterations=200)
```

(Also updated the top-of-block import to expose `parse_range` instead of `Range`/`HUNLPoker`/`solve`; added an inline comment about list-of-combo-strings as an alternative.)

**Root cause:** `Range` is `@dataclass(combos: list[Combo])`. Passing a string makes `combos` hold the string; iteration yields chars; `solve_range_vs_range` calls `_combo_to_hand_class` on a 1-char string → `ValueError`.

**Verification:**
```
$ PYTHONPATH=/Users/ashen/Desktop/poker_solver python -c "from poker_solver import parse_range; r = parse_range('AA,KK,AKs'); print('combos=', len(r.combos))"
combos= 16
```

### Fix 2: `iters=200` → `iterations=200` (README.md L150)

**Before:**
```python
vec = solve_range_vs_range_rust(template_json, iters=200,
                                alpha=1.5, beta=0.0, gamma=2.0,
                                p0_holes=p0_combos, p1_holes=p1_combos)
```

**After:**
```python
vec = solve_range_vs_range_rust(template_json, iterations=200,
                                alpha=1.5, beta=0.0, gamma=2.0,
                                p0_holes=p0_combos, p1_holes=p1_combos)
```

**Verification:**
```
# iterations= accepted past kwarg parse (engine ValueError on minimal config is expected behavior):
$ PYTHONPATH=/Users/ashen/Desktop/poker_solver python -c "from poker_solver._rust import solve_range_vs_range_rust; solve_range_vs_range_rust('{}', iterations=1, alpha=1.5, beta=0.0, gamma=2.0, p0_holes=[], p1_holes=[])"
ValueError: preflop range-vs-range is deferred to v1.5.1 per spec §8 Q2; use starting_street >= Flop for v1.5.0

# iters= still triggers the documented TypeError, confirming our fix corrects a real bug:
$ PYTHONPATH=/Users/ashen/Desktop/poker_solver python -c "from poker_solver._rust import solve_range_vs_range_rust; solve_range_vs_range_rust('{}', iters=1, alpha=1.5, beta=0.0, gamma=2.0, p0_holes=[], p1_holes=[])"
TypeError: solve_range_vs_range_rust() got an unexpected keyword argument 'iters'
```

### Fix 3: `--hero AhKh` → `--hero AdQd` (USAGE.md L669)

**Before:**
```bash
poker-solver river --board "As 7c 2d Kh 5s" --hero AhKh \
    --villain-range "QQ,JJ,AKs" --iters 200
```

**After:**
```bash
poker-solver river --board "As 7c 2d Kh 5s" --hero AdQd \
    --villain-range "QQ,JJ,AKs" --iters 200
```

Plus inline note: *"(Hero cards must not overlap any board card — e.g. `--hero AhKh` on this board would error because `Kh` is on the board.)"*

**Verification:**
```
$ PYTHONPATH=/Users/ashen/Desktop/poker_solver python -m poker_solver.cli river \
    --board "As 7c 2d Kh 5s" --hero AdQd --villain-range "QQ,JJ,AKs" --iters 5
Board:        As 7c 2d Kh 5s
Hero:         Ad Qd
Villain range: QQ,JJ,AKs (10 combos after card removal)
Iterations:   5

Hero first-decision aggregate (average over villain combos):
  action_0    0.117778
  action_1    0.882222

Mean game value (BB, P0 perspective): +11.254228
```

### Fix 4: stale "CLI ergonomic gaps" Known-issues entry (README.md L257-260, now L257-263)

**Before:**
> **CLI ergonomic gaps.** Push/fold has no dedicated `poker-solver pushfold` subcommand — use the library API in Quick start. River hero-vs-range and parity-check CLI subcommands are also not wired; drop to the Python API in the meantime.

**After:**
> **CLI subcommand caveats (v1.7.0).** `poker-solver pushfold`, `poker-solver river`, and `poker-solver parity` all ship in v1.7.0 (see USAGE §7a for flags and examples). Caveats: `parity` requires Brown's binary built via `scripts/build_noambrown.sh` and exits 2 with a hint if it is missing; `river` and `parity` are slow at high `--iters` (the documented `parity --iters 2000` runs several minutes — start with smaller values to smoke-test).

**Verification:**
```
$ PYTHONPATH=/Users/ashen/Desktop/poker_solver python -m poker_solver.cli --help | grep -E "pushfold|river|parity"
    pushfold            Look up a short-stack push/fold chart cell.
    river               Solve a river spot with fixed hero cards vs a villain range.
    parity              Diff our river solve vs Noam Brown's binary on a fixture spot.
```

### Fix 5: README L121 node-locking example unrunnable (README.md L121)

**Before:**
```python
locked = {"<infoset_key>": [0.6, 0.4]}
r = solve(HUNLPoker(HUNLConfig(starting_stack=10000)),
          iterations=2000, locked_strategies=locked)
```

`HUNLConfig(starting_stack=10000)` with no `starting_street` defaults to preflop full-tree, which raises `NotImplementedError` above 15 BB (USAGE §7 known limitation). The placeholder `<infoset_key>` is silently no-op'd even if the solve ran.

**After:**
```python
board = tuple(Card.from_str(c) for c in ("As", "7c", "2d", "Kh", "5s"))
cfg = HUNLConfig(
    starting_stack=10_000, starting_street=Street.RIVER,
    initial_board=board, initial_pot=1_000,
    initial_contributions=(500, 500),
)
locked = {"<infoset_key>": [1.0, 0.0, 0.0, 0.0]}  # 100% fold at that node
r = solve_hunl_postflop(cfg, iterations=500, locked_strategies=locked)
```

Plus inline comment pointing readers at `result.strategy.keys()` for real key discovery, USAGE §5.3, and `tests/test_node_locking.py` for canonical key format.

**Verification (transitive):** Agent B's report shows USAGE §5.3 PASS at 100 iters with identical config + lock dict shape — `game_value=+5.0027` in 1.2s. README L121 now mirrors that exact pattern.

## What's NOT in the PR

- **`docs/README_proposed_update_2026-05-23.md`** — carries identical Range/iters bugs but the file is private-only (only exists on `integration` branch). Per public-repo hygiene + the "private-only" framing of commit `3475ca9`, not included in this public-main PR. Recommendation: apply the same Range/iters/node-locking edits when the draft is next touched on the private mirror.
- **README L14 status header** — owned by PR #79.
- **USAGE header, CHANGELOG, FINAL_PRE_SIGNON_AUDIT, etc.** — owned by PR #81.
- **Rust SIMD code** — owned by PR #33.
- **pyproject.toml / scripts / lint files** — out of scope per task.

## Commit

```
f488581 docs: fix executable code bugs in README + USAGE (3 bugs + stale CLI gap claim)
 README.md | (+19, -8)
 USAGE.md  | (+4,  -1)
 2 files changed, 32 insertions(+), 13 deletions(-)
```

## CI

PR #44 opened MERGEABLE. All checks green:
- `bundle-dry-run`: PASS (4s)
- `check` (×2): PASS (4s each)

## Merge

**MERGED** at `2026-05-26T06:16:28Z` as `a6b89f70f163503b6d7dac9668a744cef20a08c0` (squash). Branch `pr-83-doc-code-bug-fixes` deleted from origin and locally; worktree removed. `origin/main` HEAD is now the squash-merge commit.

## Follow-up

- Private mirror (`integration` branch): apply the same Range/iters/node-locking edits to `docs/README_proposed_update_2026-05-23.md` next time it's touched.

