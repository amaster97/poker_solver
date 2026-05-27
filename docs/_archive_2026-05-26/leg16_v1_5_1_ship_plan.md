# LEG 16 — v1.5.2 Ship Plan (BUNDLED: PR 33 + PR 34 + PR 35)

> **2026-05-23 RE-KEY NOTICE — slot moved to v1.5.2:** The v1.5.1 slot was claimed by LEG 17 (test rigor + docs honesty bundle: PR 32 + PR 36 + PR 37) per `docs/leg17_v1_4_4_ship_plan.md` §0 Option (a) and `docs/leg17_v1_5_1_ship_report.md`. v1.5.1 shipped 2026-05-23 (tag SHA `3cf70d0d`, release https://github.com/amaster97/poker_solver/releases/tag/v1.5.1). This ship plan's bundle (PR 33 + PR 34 + PR 35) is now targeted for **v1.5.2**. All `v1.5.1` references in this document should be read as `v1.5.2` at fire time: tag name, CHANGELOG header, version bumps in `pyproject.toml`/`poker_solver/__init__.py`/`crates/cfr_core/Cargo.toml`, release notes, GitHub release title. The base SHA for cherry-pick advances from `dc3df6c` (v1.5.0) to `b5777f2` (v1.5.1) — re-audit the conflict matrix (§2.2) against v1.5.1's added files: `tests/_equity_helpers.py`, `tests/conftest.py`, `tests/test_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py`. None of these are touched by PR 33/34/35 per the original audit. Optional: rename this file to `leg16_v1_5_2_ship_plan.md` for clarity.

**Status:** PRE-STAGED (read-only investigation, plan-only). Author: ship-plan agent, 2026-05-23 (updated 2026-05-23 late for expanded scope).
**Authoritative inputs:**
- Task #182 spec (PR 33): `/Users/ashen/Desktop/poker_solver/docs/pr_proposals/v1_5_1_python_rust_delegate.md`
- v1.5.0 ship report (LEG 15): `/Users/ashen/Desktop/poker_solver/docs/leg15_v1_5_0_ship_report.md`
- v1.4.3 ship report (LEG 14, cherry-pick + maturin pattern): `/Users/ashen/Desktop/poker_solver/docs/leg14_v1_4_3_ship_report.md`
- v1.4.2 ship report (LEG 12, .so symlink precedent): `/Users/ashen/Desktop/poker_solver/docs/leg12_v1_4_2_ship_report.md`

**Hard rules in force on this plan doc:**
- This file is READ-ONLY guidance. Ship agent at ship-time executes the steps; this doc does not.
- DO NOT cherry-pick anything, DO NOT push, DO NOT tag during plan authoring.
- PR 35 source SHA is PLACEHOLDER (`<SHA_PR35>`) — implementer is in flight as of plan authoring; PR 33 and PR 34 SHAs are now confirmed.

---

## 0. Scope expansion vs. original plan

The original v1.5.1 plan scoped PR 33 only (Python-only delegate, no Rust rebuild). **This bundle now ships THREE branches.** Rationale: PR 34 + PR 35 fix latent Rust bugs that the v1.5.0 Brown apples-to-apples acceptance test exercises end-to-end; the acceptance test itself is the empirical headline gate that v1.5.0 left FAILED. Bundling all three in v1.5.1 produces a single coherent release whose CHANGELOG can honestly claim "Brown parity verified."

| PR | Branch | SHA | Scope | Worktree |
|---|---|---|---|---|
| 33 | `pr-33-python-delegate` | `29a00c0` | Python auto-delegate (530 LOC, 31/31 tests pass) | `/Users/ashen/Desktop/poker_solver_worktrees/python-delegate` |
| 34 | `pr-34-p0-off-by-one` | `0bafcfac` | Rust off-by-one fix (opponent-branch `reach_opp` sizing in `dcfr_vector.rs`) | `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-p0-off-by-one` |
| 35 | `pr-35-canonicalization` | `<SHA_PR35>` (in flight) | Bundle: test renderer fix + player-index inversion + Rust `max_raises` ALL_IN-at-cap fix (`hunl.rs`) | `/Users/ashen/Desktop/poker_solver_worktrees/pr-35-canonicalization` |

**Implications:**
- Rust source is touched by BOTH PR 34 and PR 35 → maturin rebuild becomes MANDATORY (not symlink reuse).
- Three branches → three cherry-picks; conflict surface to be audited (see §2.2).
- The empirical acceptance test now becomes a hard ship gate (see §4.4).

---

## 1. Pre-flight checks

### 1.1 Branch SHAs (verify at ship time)

```bash
# PR 33 — Python delegate (CONFIRMED at plan time, 2026-05-23 late)
cd /Users/ashen/Desktop/poker_solver_worktrees/python-delegate
git rev-parse HEAD
# expect: 29a00c0cda54156c09cbbc3b17c9a54878e3ef12
git log --oneline dc3df6c..HEAD
# expect single commit:
#   29a00c0  Add Python delegate for initial_hole_cards=() (task #182): routes to Rust vector-form CFR when applicable

# PR 34 — Rust off-by-one (CONFIRMED at plan time)
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-23-p0-off-by-one
git rev-parse HEAD
# expect: 0bafcfac8b7ebca30a031ea779a8b631877b3a89
git log --oneline dc3df6c..HEAD
# expect single commit:
#   0bafcfa  PR 34: Fix off-by-one panic at dcfr_vector.rs:651 (PR 23 P0)

# PR 35 — canonicalization bundle (PLACEHOLDER at plan time)
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-35-canonicalization
git rev-parse HEAD
# at plan time: still dc3df6c (uncommitted in-flight working tree has hunl.rs + test diffs)
# at ship time: expect single commit on top of dc3df6c, recorded as <SHA_PR35>
git status --short
# at ship time: expect clean working tree
```

**Authoring-time state observed (2026-05-23 late):**
- PR 33 worktree HEAD = `29a00c0`, clean working tree. Implementer DONE.
- PR 34 worktree HEAD = `0bafcfac`, clean working tree (only an untracked `references` symlink). Implementer DONE.
- PR 35 worktree HEAD = `dc3df6c` with uncommitted diffs in `crates/cfr_core/src/hunl.rs` + `tests/test_v1_5_brown_apples_to_apples.py`. Implementer IN FLIGHT — DO NOT SHIP until PR 35 lands and the SHA is recorded.

### 1.2 Origin / main state

Verified at plan time:
```
origin/main HEAD = dc3df6c93986029e598e61b333d11ecee3a26bcd
git ls-remote origin v1.5.0 = 544bd0ed3d84405234777b4551b8ce82f488f5fc (annotated tag → dc3df6c)
```

At ship time re-verify with `git ls-remote origin main` — must equal v1.5.0 tip. If main has advanced beyond v1.5.0 unexpectedly, pause and reconcile.

### 1.3 Shared tree state — universal2 .so

Verified at plan time:
```
$ file /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
Mach-O universal binary with 2 architectures: [x86_64] [arm64]
```

**Caveat for v1.5.1:** the shared .so contains v1.5.0's PyO3 surface — it does NOT yet contain the PR 34 `dcfr_vector.rs` fix or the PR 35 `hunl.rs` fix. The ship MUST rebuild via `maturin develop --release --target universal2-apple-darwin` after cherry-picking (see §3). DO NOT symlink the v1.5.0 .so for this ship — that would silently ship the broken Rust path.

### 1.4 Ship worktree base

Create the ship worktree fresh from `origin/main` (= v1.5.0 = `dc3df6c`):
```bash
git fetch origin
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1 \
  -b ship-v1.5.1 origin/main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
git log --oneline -1   # must show dc3df6c
```

---

## 2. Cherry-pick sequence (CODE BEFORE TESTS — Rust fixes first, Python delegate last)

### 2.1 Recommended order

Cherry-pick code-before-tests, smallest-surface-first. The Python delegate (PR 33) lands LAST so it exercises the already-fixed Rust path on the smoke wave:

1. **PR 34 first** (`0bafcfac`) — Rust off-by-one in `dcfr_vector.rs`. Smallest, most contained, no dependency on the other two.
2. **PR 35 second** (`<SHA_PR35>`) — Rust `max_raises` ALL_IN-at-cap fix in `hunl.rs` + test renderer / player-index canonicalization in `tests/test_v1_5_brown_apples_to_apples.py`.
3. **PR 33 third** (`29a00c0`) — Python delegate. Behavior depends on Rust path being correct; lands once §3 maturin rebuild has produced a .so with both Rust fixes.

### 2.2 File-overlap audit (zero expected conflicts)

| File | PR 33 | PR 34 | PR 35 | Conflict? |
|---|---|---|---|---|
| `poker_solver/hunl_solver.py` | MODIFY (+246 LOC) | — | — | NO (only PR 33) |
| `tests/test_python_delegate.py` | NEW (+284 LOC) | — | — | NO (new file) |
| `crates/cfr_core/src/dcfr_vector.rs` | — | MODIFY (+24 / -4 LOC, lines ~338-380) | — | NO (only PR 34) |
| `crates/cfr_core/src/hunl.rs` | — | — | MODIFY (~9 LOC near `enumerate_legal_actions` around line 1130) | NO (only PR 35) |
| `tests/test_v1_5_brown_apples_to_apples.py` | — | — | MODIFY (+39/-7 LOC) | NO (only PR 35) |
| `CHANGELOG.md` / `pyproject.toml` / `poker_solver/__init__.py` | — | — | — | NO (all version-bump in ship commit §5) |

**Different files, different Rust modules (`dcfr_vector.rs` vs `hunl.rs`), different languages.** Zero overlap → all three independent; cherry-picks should apply cleanly in any order.

### 2.3 Cherry-pick commands

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Step 1: PR 34 (Rust off-by-one in dcfr_vector.rs)
git cherry-pick 0bafcfac
# expect: clean apply, zero conflicts
git log --oneline -1   # expect: PR 34 commit on top of dc3df6c

# Step 2: PR 35 (Rust max_raises + test renderer canonicalization)
git cherry-pick <SHA_PR35>
# expect: clean apply, zero conflicts (PR 35 touches hunl.rs, not dcfr_vector.rs)

# Step 3: PR 33 (Python delegate)
git cherry-pick 29a00c0
# expect: clean apply, zero conflicts (PR 33 touches only Python + new test file)

# Verify topology
git log --oneline -5
# expect: <PR33-tip> <PR35-tip> <PR34-tip> dc3df6c <prev>
```

**Conflict-handling escape:** if (against expectation) any cherry-pick conflicts, abort immediately and re-investigate; do NOT manually resolve without orchestrator review. Most likely root cause would be the implementer rebasing onto a non-`dc3df6c` base mid-flight.

---

## 3. Maturin rebuild — MANDATORY for v1.5.1

PR 34 + PR 35 both modify Rust source (`dcfr_vector.rs` and `hunl.rs` respectively). The shared-tree v1.5.0 .so does NOT contain these fixes. **A symlink would silently ship the broken Rust path** — that is the ANTI-pattern for this ship.

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Activate the project venv (same pattern as LEG 12 / LEG 14 maturin builds)
source /Users/ashen/Desktop/poker_solver/.venv/bin/activate   # adjust path if env differs

# Build universal2 (Apple x86_64 + arm64) per pytest_pyenv_arch_quirk_2026-05-23.md
maturin develop --release --target universal2-apple-darwin
# expect: completes in ~60-90 s on M-series, produces a fresh
#         poker_solver/_rust.cpython-313-darwin.so

# Verify architecture
file poker_solver/_rust.cpython-313-darwin.so
# expect: Mach-O universal binary with 2 architectures: [x86_64] [arm64]

# Verify the new entry-points and version
python -c "
from poker_solver import _rust
print('solve_range_vs_range_rust doc:', _rust.solve_range_vs_range_rust.__doc__[:60] if _rust.solve_range_vs_range_rust.__doc__ else 'no doc')
print('compute_exploitability:', hasattr(_rust, 'compute_exploitability'))
"
# expect: doc string non-empty, compute_exploitability True
```

**Rebuild trigger (general policy):** if ANY ship cherry-picks Rust changes (`crates/cfr_core/**` or `pyproject.toml` build-config), the .so MUST be rebuilt. Symlink reuse is ONLY safe when the cherry-picks are Python-only. v1.5.1 violates both PR 34 + PR 35 → MUST rebuild.

---

## 4. Smoke tests + the v1.5.1 ACCEPTANCE GATE

### 4.1 Direct PR 33 smoke tests

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
# Use `python -m pytest` (not bare `pytest`) per pytest_pyenv_arch_quirk_2026-05-23.md
python -m pytest tests/test_python_delegate.py -v
# expect: 5/5 PASS (PR 33 implementer report cites 5 cases; same as the 31/31 in the
#         broader smoke wave with adjacent tests included)
```

Note the test filename is `test_python_delegate.py` (not `test_hunl_solver_delegate.py` as the spec drafted) — the implementer used the simpler name.

### 4.2 Adjacent must-stay-green wave

```bash
python -m pytest \
  tests/test_dcfr_diff.py \
  tests/test_range_vs_range_aggregator.py \
  tests/test_node_locking.py \
  tests/test_exploit_diff.py \
  tests/test_asymmetric_contributions.py \
  tests/test_river_diff_self_sanity.py \
  tests/test_range_vs_range_rust_diff.py \
  -v
# expect: all green
```

If `test_exploit_diff.py` flips on the auto-route (LOW risk per PR 33 spec §5), pin the affected fixture to `backend="python"` and document the pin in the ship commit message.

### 4.3 BIG retest wave — deferred to POST-SHIP per §8

**Change vs original plan:** the W4.3 / W2.3 / W3.4 BIG retests were previously scheduled INSIDE the ship loop, contributing 5-8 min to wall-clock. **Moved to post-ship Wave 1 (§8)** to keep the ship focused on the acceptance gate and shorten median ship time. If a retest verdict regresses, that surfaces in the post-ship wave and creates a follow-up — it does NOT block the v1.5.1 ship since the empirical acceptance test (§4.4) is now the load-bearing gate.

### 4.4 Brown apples-to-apples acceptance test — HARD SHIP GATE

This is THE empirical headline of v1.5.1. v1.5.0 wired the framework but the acceptance test FAILED on both spots (the gap that PR 34 + PR 35 close). **If this test does not pass on both spots after the maturin rebuild, the ship is INVALIDATED.**

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Run the acceptance test with parity_noambrown marker enabled and pytest addopts cleared
# (the conftest typically gates parity_noambrown tests behind a runtime opt-in flag)
python -m pytest tests/test_v1_5_brown_apples_to_apples.py -v \
    -m parity_noambrown -o "addopts="
# expect: 2 PASSED (dry_K72_rainbow + dry_A83_rainbow)
# do NOT accept SKIP at this ship — v1.5.0's SKIP outcome was the failure that v1.5.1 closes
```

**If FAIL:**
- DO NOT version-bump. DO NOT tag. DO NOT push.
- Revert to a clean ship worktree and report which spot failed, with the diff vs Brown reference (the test should emit a per-action TVD or strategy-frequency delta).
- Spawn a debug agent against the failing spot before re-attempting.

**If PASS:** proceed to §5 with confidence that the empirical headline holds.

### 4.5 PR 34 + PR 35 contained regression guards

```bash
# PR 34 asymmetric-range guard (tests that exercise dry_A83_rainbow or similar
# asymmetric hand counts in dcfr_vector.rs)
python -m pytest tests/test_range_vs_range_rust_diff.py tests/test_dcfr_diff.py -v -k asymmetric
# expect: PASS (PR 34 implementer report confirms 49-vs-50 hand counts no longer panic)

# PR 35 max_raises guard — covered inside the acceptance test (§4.4)
# (the `max_raises` ALL_IN-at-cap fix manifests as action-count parity on the
# Brown reference, which the apples-to-apples acceptance test verifies directly)
```

---

## 5. Version bump v1.5.0 → v1.5.1

### 5.1 Files

| File | Change |
|---|---|
| `pyproject.toml` | `version = "1.5.0"` → `"1.5.1"` |
| `poker_solver/__init__.py` | `__version__ = "1.5.0"` → `"1.5.1"` |
| `CHANGELOG.md` | Add `## [1.5.1] - 2026-05-23` entry ABOVE the v1.5.0 entry |

### 5.2 CHANGELOG entry (use verbatim, edit dates / SHAs only)

```markdown
## [1.5.1] - 2026-05-23

### Empirical Brown parity verified

The v1.5.0 Brown apples-to-apples acceptance test now PASSES on both
postflop spots (dry_K72_rainbow + dry_A83_rainbow). v1.5.0 wired the
framework but left the test FAILING; v1.5.1 closes the gap with three
bundled fixes plus the Python auto-delegate so existing callers
transparently route through the verified Rust vector path.

### Fixed (PR 34) — Rust off-by-one in opponent-branch reach propagation

- `crates/cfr_core/src/dcfr_vector.rs`: `VectorDCFR::traverse` opponent
  node branch sized `next_reach` and the inner accumulator loop using
  `opp_hands = hand_count[1 - player]`, but `reach_opp` at this point is
  indexed by the *current* player's hand axis. For symmetric ranges
  (e.g. dry_K72_rainbow 55-vs-55) the swap was invisible; for asymmetric
  ranges (dry_A83_rainbow 49-vs-50) the loop walked past
  `reach_opp.len()` and panicked at the terminal leaf. Mirrors Brown's
  `trainer.cpp:170-173` where `opp_hands = num_hands_[node.player]`.
  Added a `debug_assert!` as a regression guard.

### Fixed (PR 35) — Rust max_raises ALL_IN-at-cap + test canonicalization

- `crates/cfr_core/src/hunl.rs`: `enumerate_legal_actions` was
  unconditionally emitting `ACTION_ALL_IN` even when the raise cap was
  reached, producing a phantom 3rd action (c/f/A) where Brown's
  `river_game.cpp:53-106` enumerates only (c/f) at cap. Gated the
  ACTION_ALL_IN push on `!cap_reached`.
- `tests/test_v1_5_brown_apples_to_apples.py`: fixed test renderer
  player-index inversion that was comparing p0's strategy to Brown's p1
  bucket and vice versa, masking the underlying Rust fixes during
  pre-ship investigation.

### Changed (PR 33) — `solve_hunl_postflop` auto-delegates to Rust vector CFR

- `poker_solver.solve_hunl_postflop(...)` now auto-routes to the Rust
  vector-form CFR (`_rust.solve_range_vs_range_rust`) when
  `config.initial_hole_cards == ()` and the config is postflop and no
  Python-only feature (`locked_strategies`, `target_exploitability`,
  `abstraction`) is requested. Closes the chance-enum-at-root Python
  perf cliff for range-vs-range queries — every existing
  `solve_hunl_postflop(..., initial_hole_cards=())` callsite immediately
  gets the fast Brown-equivalent path with zero caller-side changes.
- Backward-compatible. New `backend` kwarg ("auto" | "python" |
  "rust_vector"), default "auto". `backend="python"` pins the old
  scalar Python DCFR for differential debug / regression bisection;
  `backend="rust_vector"` forces the Rust vector path (raises
  `ValueError` if `initial_hole_cards` is non-empty).
- When a Python-only feature is set under `backend="auto"` AND
  `initial_hole_cards == ()`, the delegate emits a `UserWarning` per
  offender and falls back to the Python path so callers know which
  feature blocked the fast path.
- `HUNLSolveResult.backend` field reports `"rust_vector"` when the
  delegate engaged.

### Added

- New `backend` kwarg on `solve_hunl_postflop`.
- `tests/test_python_delegate.py` (5/5 PASS, 31/31 inclusive of adjacent
  smoke wave per implementer report).
```

### 5.3 Single bundling commit

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1
git add pyproject.toml poker_solver/__init__.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
v1.5.1: Brown apples-to-apples acceptance VERIFIED (PR 33 + PR 34 + PR 35)

v1.5.0 wired the empirical Brown parity framework but left the acceptance
test FAILING. v1.5.1 closes the gap:

- PR 34: Rust off-by-one fix in dcfr_vector.rs opponent-branch reach_opp
  sizing (asymmetric ranges no longer panic, mirrors trainer.cpp:170-173).
- PR 35: Rust max_raises ALL_IN-at-cap fix in hunl.rs + test canonicalization
  (test renderer fix + player-index inversion fix).
- PR 33: Python solve_hunl_postflop auto-delegates to the now-verified
  Rust vector CFR when initial_hole_cards == (). Backward-compatible;
  new backend kwarg ("auto" | "python" | "rust_vector"), default "auto".

Acceptance gate: tests/test_v1_5_brown_apples_to_apples.py PASSES on both
dry_K72_rainbow and dry_A83_rainbow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 6. Tag + push

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Annotated tag
git tag -a v1.5.1 -m "v1.5.1: Brown apples-to-apples verified (PR 33 + PR 34 + PR 35)"

# Push main + tag (origin only — public-OK content per audit below)
git push origin HEAD:main
# expect: fast-forward dc3df6c..<new-tip>  (4 commits: PR 34, PR 35, PR 33, version-bump)

git push origin v1.5.1
# expect: [new tag] v1.5.1 -> v1.5.1

# Verify
git ls-remote --tags origin | grep v1.5.1
# expect: two lines (annotated SHA + commit it points to)
```

**Public-repo hygiene audit (per `feedback_public_repo_hygiene`) before push:**
- CHANGELOG entry: no `/Users/...` paths, no session IDs, no PII, no internal-memory file names. ✓ (verbatim text in §5.2 audited)
- Cherry-picked commits: scan via `git log -p dc3df6c..HEAD` before push — flag any leaked absolute paths or internal doc references. Expected clean (Python source + Rust source + tests).
- Tag message: generic phrasing. ✓

---

## 7. GitHub release

```bash
# Use a /tmp file for the release body to avoid heredoc quoting issues
cat > /tmp/v1.5.1_release_notes.md <<'EOF'
## v1.5.1 — Brown apples-to-apples acceptance VERIFIED (PATCH)

**PATCH-level release.** Public API is unchanged at the signature level
(the new `backend` kwarg is additive with a sensible default). The
empirical headline of v1.5.1 is that the v1.5.0 Brown parity acceptance
test now PASSES on both postflop spots.

### What changed

- **PR 34 (Rust):** off-by-one fix in `dcfr_vector.rs`
  opponent-branch `reach_opp` sizing. Asymmetric ranges no longer
  panic at the terminal leaf. Mirrors Brown's `trainer.cpp:170-173`.
- **PR 35 (Rust + tests):** `max_raises` ALL_IN-at-cap fix in
  `hunl.rs::enumerate_legal_actions` (gate the ACTION_ALL_IN push on
  `!cap_reached` to match Brown's `river_game.cpp:53-106`), plus
  test renderer canonicalization and a player-index inversion fix
  in the acceptance harness.
- **PR 33 (Python):** `solve_hunl_postflop` now transparently
  auto-routes to the Rust vector CFR when `initial_hole_cards == ()`
  and the config is postflop. New `backend` kwarg ("auto" | "python"
  | "rust_vector"), default "auto", opt-out via `backend="python"`.

### What this fixes

- The v1.5.0 Brown apples-to-apples acceptance test (dry_K72_rainbow +
  dry_A83_rainbow) now PASSES end-to-end.
- The chance-enum-at-root Python perf cliff is closed for range-vs-range
  queries through the existing public API surface.

### What did NOT change

- Public API signature of `solve_hunl_postflop` (`backend` is a
  keyword-only additive kwarg with default `"auto"`).
- Existing callers with non-empty `initial_hole_cards` (still scalar
  Python DCFR — vector form requires the chance-enum-at-root config).
- The Rust crate's public C ABI / PyO3 surface — only internal CFR
  semantics changed (off-by-one + max_raises gating).

### Honest framing

v1.5.0 stood up the Brown parity framework but left the acceptance test
FAILED. v1.5.1 is the empirical close: two Rust correctness fixes plus
a Python routing change that wires the public API into the verified
vector path. Semver bump is PATCH (additive kwarg, internal Rust
semantics fix, no public ABI change).
EOF

gh release create v1.5.1 \
  --title "v1.5.1: Brown apples-to-apples verified (PR 33 + PR 34 + PR 35)" \
  --notes-file /tmp/v1.5.1_release_notes.md

# Verify
gh release view v1.5.1 | head -20
```

---

## 8. Cascading retest queue (POST-v1.5.1, fan out in parallel)

Once v1.5.1 ships, fan out the following retest agents (one-shot per `feedback_agent_scheduling`). These were blocked or perf-throttled by the chance-enum-at-root Python path; the verified Rust delegate should unblock them all.

### Wave 1 — direct unblockers (3 agents, parallel)

| Retest | Spec | Expected verdict | Budget |
|---|---|---|---|
| W4.3 Priya parity | `docs/persona_test_results/W4_3_v1_4_0_retest.md` + `tests/test_river_diff.py::test_river_parity_vs_brown` | PASS (was BLOCKED) | <60 s |
| W2.3 Sarah KK-vs-c-bet | `docs/pr_proposals/v1_4_1_retest_W2_3_sarah_kk_vs_cbet_range.md` | PASS (was INCONCLUSIVE-SLOW) | <2 min |
| W3.4 Daniel MDF | `docs/pr_proposals/v1_4_1_retest_W3_4_daniel_mdf.md` | PASS (was INCONCLUSIVE-SLOW) | <2 min |

### Wave 2 — adjacent retests + W2b cohort (parallel after Wave 1 returns)

| Retest | Spec | Why unblocked | Budget |
|---|---|---|---|
| W3.5 literal RvR | `docs/persona_test_results/W3_5_v1_4_1_retest.md` | Same chance-enum-at-root path now via verified Rust vector | <2 min |
| W2.5 preflop literal | `docs/persona_test_results/W2_5_v1_4_1_retest.md` | Smoke-regression confirm; routing-through-solver path | <2 min |
| W2b.1-W2b.N cohort | per cohort spec in `docs/persona_test_results/` | Per-spot drops from minutes to seconds via delegate | per-spec |

### Spawn schedule

Per `feedback_min_five_agents` + `feedback_parallel_agents`: launch all of Wave 1 in parallel (3 agents) immediately post-ship, then Wave 2 (3+ agents) after Wave 1 returns. Aggregate verdicts per wave per `feedback_agent_scheduling`.

---

## 9. Estimated ship wall-clock (bundled)

| Phase | Estimate | Source / Δ vs original |
|---|---|---|
| Pre-flight checks (§1) | 1-2 min | +1 min vs original (3 branches to verify, not 1) |
| Ship worktree setup (§1.4) | 1 min | LEG 14 precedent |
| Cherry-pick PR 34 + PR 35 + PR 33 (§2) | 2-3 min | +1-2 min vs original (3 cherry-picks, not 1) |
| **Maturin rebuild (§3) — MANDATORY** | **2-4 min** | **NEW: ~60-90 s on M-series for universal2 release build, plus verification** |
| Smoke tests (§4.1 + §4.2 + §4.5) | 3-4 min | similar to original |
| **Brown acceptance gate (§4.4) — HARD GATE** | **3-6 min** | **NEW: 2 spots × ~90-180 s each; load-bearing for the ship** |
| Version bump + commit (§5) | 1 min | LEG 14/15 precedent |
| Tag + push (§6) | <1 min | LEG 14/15 precedent |
| GitHub release (§7) | 1 min | LEG 14/15 precedent |
| Cleanup (worktree removal) | 1 min | LEG 14/15 precedent |
| **TOTAL** | **25-40 min** (median ~30 min) | LEG 15: 22 min — bundled scope adds ~10 min for rebuild + acceptance gate |

**Headline:** **25-40 min ship** (vs LEG 15's 22 min). The BIG retest wave moves to post-ship per §8, which keeps the ship focused on the acceptance gate.

---

## 10. Cleanup (post-push)

```bash
# Maturin produces a real .so in the ship worktree (no symlink this ship);
# the worktree-remove cleans it as part of the directory teardown.

# Remove ship worktree
cd /Users/ashen/Desktop/poker_solver
git worktree remove /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.1

# Implementer worktrees cleanup is a separate housekeeping task — leave
# the three feature worktrees (python-delegate, pr-23-p0-off-by-one,
# pr-35-canonicalization) in place per LEG 14/15 pattern: ship cleans
# only its own worktree.

# Local ship-v1.5.1 branch retained per feedback_no_concurrent_branch_ops
# (will resolve on next shared-tree `git pull`)
```

---

## 11. Authorization compliance

Per `feedback_pr10a5_autonomous_commit` (audit-cleared PRs ship end-to-end autonomously):
- PR 33, PR 34, PR 35 must all clear audit before ship (each is a separate prep step; not part of this plan).
- Ship agent has authority to: cherry-pick (all three), maturin rebuild, commit version bump, push main + tag, create GitHub release.
- Ship agent does NOT have authority to: force-push, delete origin branches, override Type C-CRITICAL findings, take major design decisions.

Per `feedback_public_repo_hygiene`:
- Before push, scan cherry-picked diffs for absolute paths / session IDs / internal-memory file names. Expected clean (Python source + Rust source + test files only).
- Tag message and release notes audited verbatim in this plan (§6, §7).

Per `feedback_no_concurrent_branch_ops`:
- Ship operates inside its own `git worktree`; the three implementer worktrees + shared tree remain untouched during ship.

---

## 12. Risk register

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Brown acceptance test (§4.4) FAILS after rebuild | LOW-MED | **HIGH (ship INVALIDATED)** | Abort ship, spawn debug agent against failing spot; do NOT version-bump/tag/push |
| Maturin rebuild fails (toolchain drift, target missing) | LOW | MED (ship pause) | Verify universal2 target installed; fall back to host-arch build only if persona time budget allows; document in ship report |
| Cherry-pick conflict (any of the 3) | LOW | LOW (1-2 min rebase) | Files are non-overlapping per §2.2 audit; if conflict surfaces, abort + investigate (likely root: implementer rebased onto non-`dc3df6c` base) |
| Smoke test regression (e.g. `test_exploit_diff.py` flips on auto-route) | LOW | LOW (1 min pin) | Pin affected fixture to `backend="python"` per PR 33 spec §5 |
| PR 34 fix exposes a SECOND latent bug in `dcfr_vector.rs` | LOW | MED | Acceptance test would catch it; abort ship per row 1 |
| PR 35 in-flight implementer doesn't land in time | MED | LOW (defer ship) | Defer; this plan is pre-staged, not time-locked. PR 33 + PR 34 alone are NOT sufficient — the `max_raises` gating fix is required for acceptance test parity. |
| pytest-pyenv arch quirk re-surfaces | LOW | LOW | Use `python -m pytest` (not bare `pytest`) per `pytest_pyenv_arch_quirk_2026-05-23.md` |
| Universal2 .so size regression vs v1.5.0 | LOW | LOW (cosmetic) | Accept; document in ship report if >5 % larger |

---

## 13. Confidence: will the v1.5.1 acceptance test PASS?

**Confidence: MODERATE-to-HIGH.** Rationale:

1. **PR 34 is necessary** — it fixes a Rust panic on asymmetric ranges (dry_A83_rainbow: 49-vs-50) that v1.5.0 hit at terminal-leaf accumulation. Without PR 34, the acceptance test cannot reach a meaningful comparison on the asymmetric spot at all. Confidence on PR 34 itself: HIGH (small contained fix, matches Brown's `trainer.cpp:170-173` exactly, implementer attached `debug_assert!` guard).

2. **PR 35's max_raises ALL_IN-at-cap fix is necessary** — without it, action-count parity vs Brown is broken at deep-cap nodes (Brown emits c/f, we emit c/f/A). The acceptance test was likely failing on action-distribution divergence even on the symmetric spot. Confidence on PR 35's Rust fix: HIGH (matches Brown's `river_game.cpp:53-106`).

3. **PR 35 also includes test-renderer canonicalization and a player-index inversion fix.** These ensure that any remaining numerical comparison is apples-to-apples (the v1.5.0 test's pre-fix output may have been comparing the wrong player's bucket, masking the Rust bugs as numerical noise). Confidence: HIGH that the in-flight implementer surfaced these as canonicalization issues; MODERATE that they're complete (PR 35 SHA still placeholder at plan time).

4. **Residual uncertainty:** there may exist additional latent Rust correctness bugs (e.g., regret-matching arithmetic in deeper game tree nodes, chance-node weighting) that the acceptance test has not yet exposed because the panic + action-count divergence masked them. PR 34 + PR 35 are necessary but **not provably sufficient** until the test actually runs green on the rebuilt .so.

**Net:** the acceptance test is HIGHLY LIKELY to pass after the bundled fixes, but the empirical confirmation (§4.4) is the load-bearing check. The "MODERATE" hedge accounts for the residual chance of a third latent bug surfacing only post-rebuild.

---

**End of plan. Ship agent: verify PR 35 SHA → execute §1 → §10 in order, write LEG 16 ship report on completion, hand off Wave 1 cascade to the next orchestrator turn.**
