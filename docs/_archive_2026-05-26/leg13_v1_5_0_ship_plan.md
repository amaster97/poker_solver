# LEG 13 — v1.5.0 ship plan (PR 23 Rust vector-form CFR / true Nash RvR)

**Date staged:** 2026-05-23 · **Status:** PRE-STAGED — fires when PR 23 audit-clears AND v1.4.2 has shipped to origin.

- **PR 23 worktree:** `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening` on branch `pr-23-rust-dcfr-widening`.
- **Main tree:** `/Users/ashen/Desktop/poker_solver` on `main`, HEAD `89a124b` (v1.4.1 at staging time; **expected to be at v1.4.2 by ship time**).
- **Bump:** **MINOR (1.4.2 → 1.5.0).** New capability — true Nash range-vs-range in the Rust tier. The PyO3 entry is additive (`solve_range_vs_range_rust`), so the public Python surface gains, doesn't break — keeps the bump out of MAJOR.

> Snapshot at staging time: PR 23 has **5 commits** on its branch, all on top of v1.4.0 (`166d2b8`), NOT v1.4.1. The implementer is still iterating (recent commit `8d1c41f` ships the memory profiler per spec §4). SHAs may be rebased/squashed before ship. Treat the table in §2a as load-bearing — re-enumerate at ship time.

---

## 1. Pre-flight checks

Run these from `/Users/ashen/Desktop/poker_solver` BEFORE cherry-picking. All steps assume v1.4.2 has shipped (else swap "v1.4.2" → "v1.4.1" everywhere and add an explicit note in the release).

### 1a. PR 23 worktree state

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening
git branch --show-current                       # expect: pr-23-rust-dcfr-widening
git status --short                              # expect: clean (no M / ?? lines)
git log --oneline v1.4.2..HEAD                  # SHAs to cherry-pick (5 expected at staging)
git rev-list --count v1.4.2..HEAD               # commit count
git diff --stat v1.4.2..HEAD                    # full file surface
git diff --name-only v1.4.2..HEAD               # exact files for sanitization + conflict map
```

**Expected commit list at staging time** (replace at ship time):

| Source SHA | Subject |
|---|---|
| `<PR23_SHA_1>` (was `609a20f` at staging) | PR 23: add Game::hand_count() trait method (default = 1) |
| `<PR23_SHA_2>` (was `235cab2`)            | PR 23: vector-form DCFR module (Brown's trainer.cpp pattern, MIT) |
| `<PR23_SHA_3>` (was `4722eb5`)            | PR 23: PyO3 binding solve_range_vs_range_rust |
| `<PR23_SHA_4>` (was `051a50f`)            | PR 23: differential test (exploitability metric) + hand-list extension |
| `<PR23_SHA_5>` (was `8d1c41f`)            | PR 23: per-street memory profiler (spec §4) |

Q: Does the implementer plan to squash to one commit before audit? If yes, only one SHA is needed in §2.

### 1b. Sanitization scan (per `feedback_public_repo_hygiene`)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening
git diff v1.4.2..HEAD | grep -nE '(/Users/ashen|ashen26@gsb|claude-session|claude_ai_|orchestrator|implementer-agent)' || echo "CLEAN"
grep -rnE '(/Users/ashen|ashen26@gsb|claude-session)' tests/test_range_vs_range_rust_diff.py crates/cfr_core/src/dcfr_vector.rs 2>/dev/null || echo "FILES CLEAN"
git diff --name-only v1.4.2..HEAD | grep -E '^docs/' && echo "DOCS TOUCHED — review" || echo "NO DOCS TOUCHED"
```

If any line matches PII / paths / session IDs: STOP. Either request rewrite from implementer or sanitize before cherry-pick. The MIT attribution to Brown's `trainer.cpp` is REQUIRED and not a PII issue — it's a license requirement (`references/README.md` §2).

### 1c. Tests pass in worktree (mandatory)

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening

# MANDATORY Rust rebuild before any pytest (LEG 11 lesson — stale .so masks fix)
maturin develop --release
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__)"

# PR 23's own tests (load-bearing for true-Nash claim)
pytest -x tests/test_range_vs_range_rust_diff.py -v

# Existing differential tests MUST stay green (scalar path unchanged)
pytest -x tests/test_dcfr_diff.py tests/test_leduc_diff.py tests/test_river_diff.py tests/test_exploit_diff.py -v

# Asymmetric contributions (v1.4.1 — PR 22 work) MUST still pass
pytest -x tests/test_asymmetric_contributions.py -v

# Full Python suite (gate before ship)
pytest -x -m "not slow"

# Rust unit tests
cargo test --all
cargo clippy --all-targets -- -D warnings
```

All seven gates must be green. If `tests/test_asymmetric_contributions.py` is broken (it WAS deleted in the PR 23 worktree at staging — see Risk §B), STOP and request the implementer rebase onto v1.4.2.

Q: At ship time, did the implementer add the Brown apples-to-apples NEW test referenced in task #184? If not, the orchestrator may need a parallel tests-from-spec agent before this gate flips green.

### 1d. Main tree is clean

```bash
cd /Users/ashen/Desktop/poker_solver
git status --short          # expect: only untracked docs/ examples/ scripts/ (known carry-overs); nothing M for tracked
git log --oneline -1        # expect: chore(release): v1.4.2 ... (post v1.4.2 ship)
git rev-parse HEAD          # expect: <v1.4.2_SHA>
git fetch origin
git rev-parse origin/main   # expect: same SHA as HEAD (no drift)
git tag -l v1.4.2           # expect: v1.4.2 exists locally + remote
git ls-remote --tags origin | grep v1.4.2
```

If `git status` shows any `M ` line for tracked files, STOP and investigate. Origin must show v1.4.2 tag and main aligned, else this plan needs to fall back to v1.4.1 baseline (less ideal — PR 23's test marker fix is in v1.4.2).

Q: If v1.4.2 hasn't shipped to origin by ship time, do we (a) ship v1.5.0 from v1.4.1 anyway (and lose the test marker fix), (b) ship v1.4.2 first, or (c) bundle PR 25's test marker fix into v1.5.0 as a "while we're here" cleanup? **Default: (b) ship v1.4.2 first; the marker fix is already cherry-pick-staged.**

---

## 2. Cherry-pick sequence

**Strongly recommend** a fresh ship worktree based on `main` (LEG 11 lesson — isolates `_rust.so` rebuild from the shared tree where other agents may still be running v1.4.x binaries).

### 2a. Create isolated ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver
# Spawn detached-HEAD ship worktree from current main (v1.4.2)
git worktree add /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0 main
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0
git log --oneline -1     # confirm: at v1.4.2 release commit
```

### 2b. Enumerate exact SHAs (run at ship time)

```bash
# From the PR 23 worktree, enumerate the commits to lift
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening
git log --oneline v1.4.2..HEAD
# Capture chronological (oldest-first) for cherry-pick. Replace placeholders below
# with actual SHAs at ship time.
export PR23_SHA_1=<oldest_sha>   # trait method
export PR23_SHA_2=<sha2>         # vector-form DCFR module
export PR23_SHA_3=<sha3>         # PyO3 binding
export PR23_SHA_4=<sha4>         # differential test
export PR23_SHA_5=<newest_sha>   # memory profiler
# Plus any new commits since 2026-05-23 (e.g. Brown apples-to-apples test from task #184)
```

If implementer squashed before audit:
```bash
export PR23_SHA=<single_squashed_sha>
```

### 2c. Cherry-pick into ship worktree

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0

# Multi-commit cherry-pick (oldest first)
git cherry-pick $PR23_SHA_1 $PR23_SHA_2 $PR23_SHA_3 $PR23_SHA_4 $PR23_SHA_5
# OR single squash:
# git cherry-pick $PR23_SHA
```

**Expected conflicts (high probability at staging):**

| File | Reason | Resolution strategy |
|---|---|---|
| `CHANGELOG.md` | PR 23 worktree bumps v1.4.0 → v1.5.0 directly. v1.4.2 has its own block now. | Keep both v1.4.1 + v1.4.2 entries; rewrite the v1.5.0 entry above them per template in §2e. |
| `poker_solver/__init__.py` | PR 23 worktree sets `__version__ = "1.5.0"` against a 1.4.0 base. v1.4.2 already moved this to "1.4.2". | Accept "1.5.0" final. |
| `pyproject.toml` | Same as above. | Accept "1.5.0" final. |
| `poker_solver/hunl.py` | PR 22 (v1.4.1) modified the postflop init branch + asymmetric contributions; PR 23's `hunl.py` diff (`+`/`-` 77 lines at staging) overlaps. | Manual merge — preserve BOTH the asymmetric-contributions logic from v1.4.1 AND PR 23's vector-mode discriminator. Compare against `v1.4.2:poker_solver/hunl.py` and apply PR 23 changes incrementally. |
| `tests/test_asymmetric_contributions.py` | PR 23 worktree DELETES this file (331 lines removed in the diff at staging). | **STOP — this is a CRITICAL regression.** v1.4.1's tests must NOT be deleted. Request implementer rebase onto v1.4.2 before ship. Do NOT cherry-pick blindly. |

If any conflict beyond mechanical (e.g. the `hunl.py` merge requires actual semantic reconciliation), STOP and surface to orchestrator. This is the #1 risk for the v1.5.0 ship.

Q: Does the implementer plan to rebase PR 23 onto v1.4.2 before audit completes? If not, the orchestrator should request that rebase as part of the audit-clear gate. **Default: require rebase; do NOT cherry-pick PR 23 onto v1.4.2 with the asymmetric-contributions test still being deleted.**

### 2d. Mandatory Rust rebuild (LEG 11 lesson — DO NOT SKIP)

PR 23 ships ~984 LOC of new Rust (`crates/cfr_core/src/dcfr_vector.rs`) + trait extension (`game.rs`) + PyO3 entry (`lib.rs`). Stale `_rust.so` will produce false-positive pytest greens AND mask the new entry point entirely (Python will raise `AttributeError` on `_rust.solve_range_vs_range_rust`).

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0
maturin develop --release
python -c "from poker_solver import _rust; print('rust binding OK', _rust.__file__); print(hasattr(_rust, 'solve_range_vs_range_rust'))"
# expect: True

# Smoke that the new entry actually executes (tiny river RvR)
python -c "
import json
from poker_solver import _rust
cfg = {
    'starting_street': 'River',
    'initial_board': ['Ks', '7h', '2d', '4c', 'Jh'],
    'initial_pot': 1000, 'initial_contributions': [500, 500],
    'bet_size_fractions': [1.0], 'include_all_in': False,
    'postflop_raise_cap': 1, 'starting_stack': 9500,
    'initial_hole_cards': [],
}
result = _rust.solve_range_vs_range_rust(json.dumps(cfg), iterations=3)
print('OK', result['backend'], result['iterations'], result['decision_node_count'])
"
```

### 2e. CHANGELOG.md (additive — append above v1.4.2 entry)

Open `/Users/ashen/Desktop/poker_solver/CHANGELOG.md` in the ship worktree. v1.4.2's block is the current top under `## [Unreleased]`. Insert a NEW `## [1.5.0]` block ABOVE the v1.4.2 block. Do NOT touch v1.4.0 / v1.4.1 / v1.4.2 entries.

Drop-in markdown (verified against PR 23 spec §1-2 + §5):

```markdown
## [1.5.0] - 2026-05-23

### Added — True Nash range-vs-range in the Rust tier (PR 23)

- **`solve_range_vs_range_rust` PyO3 entry** (`poker_solver._rust`) — new
  Python-callable that solves true range-vs-range Nash by walking the
  betting tree once and storing per-hand regret / strategy vectors at each
  infoset, matching Brown's reference C++ pattern
  (`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`,
  MIT-licensed, attribution preserved in
  `crates/cfr_core/src/dcfr_vector.rs`).
- **`Game::hand_count()` trait method** (`crates/cfr_core/src/game.rs`) —
  default `fn hand_count(&self) -> usize { 1 }` keeps Kuhn / Leduc /
  fixed-combo HUNL on the scalar path. `HUNLState` overrides when
  `initial_hole_cards.is_empty()` so the chance-enum-at-root path
  dispatches to vector-form DCFR.
- **Per-street memory profiler** (`dcfr_vector.rs` → `VectorMemoryProfile`)
  surfaced via the PyO3 binding's `memory_profile` dict (keys
  `total_bytes`, `infoset_count`, `bytes_by_street`,
  `infoset_count_by_street`). Honest framing — measures actual allocated
  bytes, does not extrapolate.

### Fixed — Brown parity gap (architectural)

- Closes the architectural divergence between
  `solve_range_vs_range` (Option B blueprint aggregator, per-hand 1v1
  Nash averaged across villain reps) and Brown's vector-form CFR. The
  new Rust entry produces a strategy that matches Brown's algorithmic
  shape (single joint Nash over the hand distribution, not an
  arithmetic mean of conditional 1v1 Nashes).
- See `docs/brown_apples_to_apples_2026-05-23.md` for the experimental
  basis (mean TV 0.47 against Brown pre-fix, target ≤ 1e-3 with the
  vector-form entry).

### Honest scope

- **Postflop only in v1.5.0.** Preflop (`starting_street=Preflop` with
  empty hole cards, 1326-hand dimension) deferred to v1.5.1 pending
  empirical memory profile vs the 16 GB ceiling. See PR 23 spec §4 +
  §8 Q2.
- **Python `solve_range_vs_range` (range_aggregator.py) NOT rewired in
  v1.5.0.** The blueprint aggregator stays the default for the
  Python-side API. Task #182 (Python delegate to Rust vector CFR) is
  separately scoped — see "Deferred to v1.5.1" below.
- **UI surface untouched in v1.5.0.** The new Rust tier exists as an
  additive PyO3 entry; no GUI exposure until v1.5.1+ wires it.
  Therefore exempt from `feedback_ui_packaging_sync` per the
  internal-only category.
- Bucketing is not engaged in v1.5.0 — raw 1326-hand dimension is used
  per-infoset on postflop streets. Memory profile in the PR 23 report
  documents the projection; production-scale bucketing (256 / 128 / 64
  per spec §2 card-bucketing wedge) is a v1.5.2 follow-up if memory
  pressure surfaces.
- The Rust binding (`poker_solver/_rust.so`) is rebuilt — wheel
  consumers from v1.4.x must reinstall to pick up `solve_range_vs_range_rust`.

### Tests

- New `tests/test_range_vs_range_rust_diff.py` — Cases A (small RvR
  river-only), B (medium turn-bucketed), C (production-scale river)
  per PR 23 spec §5. Case D (full preflop) skip-gated pending memory
  profile.
- **NEW Brown apples-to-apples acceptance test** (per task #184) using
  the new `solve_range_vs_range_rust` entry. Pre-v1.5.0 this test FAILS
  (the aggregator-vs-Brown TV is 0.47, large); post-v1.5.0 it should
  PASS within float-precision tolerance (≤ 1e-3 per-action probability
  delta vs Brown's binary output). See `docs/brown_apples_to_apples_2026-05-23.md`
  §6c for the test spec.
- Existing differentials (`test_dcfr_diff.py`, `test_leduc_diff.py`,
  `test_river_diff.py`, `test_exploit_diff.py`,
  `test_asymmetric_contributions.py`,
  `test_range_vs_range_aggregator.py`, `test_node_locking.py`)
  all stay green — scalar path unchanged.

### Reverted — PR 25 commit 2 (concrete hole cards in test_river_diff)

- `tests/test_river_diff.py::test_river_parity_vs_brown` restored to
  `initial_hole_cards=()` (the chance-enum-at-root form). PR 25
  commit 2 (`6bf8b9e` on `pr-25-river-parity-test-fix`) had switched
  to concrete hole cards because the Python tier timed out under the
  empty-tuple form. With the Rust vector CFR entry now in place,
  the test routes through the fast Rust path and the empty-tuple
  form is back to being the right semantic shape (range-vs-range
  vs Brown's range-vs-range).
```

### 2f. Version bump (MINOR — 1.4.2 → 1.5.0)

| File | Current (at ship time) | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.4.2"` | `version = "1.5.0"` | Edit the `version = ` line |
| `poker_solver/__init__.py` | `__version__ = "1.4.2"` | `__version__ = "1.5.0"` | Edit |
| `Cargo.toml` (root) | no `version` (workspace) | — | Skip |
| `crates/cfr_core/Cargo.toml` | `version = "0.5.0"` (workspace crate, last bumped pre-v1.0.0) | unchanged | Skip — the crate is internal; bumping it is optional and not done historically (verified at staging — v1.4.1 didn't bump either) |

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0

# Verify locations
grep -n '^version = ' pyproject.toml
grep -n '__version__' poker_solver/__init__.py

# Edit in place (use Edit tool — DO NOT sed)
# pyproject.toml: version = "1.4.2" -> "1.5.0"
# poker_solver/__init__.py: __version__ = "1.4.2" -> "1.5.0"

# Stage + commit release bump
git add CHANGELOG.md pyproject.toml poker_solver/__init__.py
git status --short    # sanity: only CHANGELOG + version files + cherry-pick already committed
git commit -m "chore(release): v1.5.0 — True Nash range-vs-range in Rust tier (MINOR; PR 23 vector-form CFR)"
```

---

## 3. Tag + push sequence

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0

# Annotated tag
git tag -a v1.5.0 -m "v1.5.0: True Nash range-vs-range via Rust vector-form CFR (PR 23)"

# Push main commits + tag
git push origin HEAD:main
git push origin v1.5.0

# Verify
git fetch --tags origin
git tag -l 'v1.5.0'
git ls-remote --tags origin | grep v1.5.0
git log --oneline origin/main -7
```

Q: Is autonomous push authorized per `feedback_pr10a5_autonomous_commit`? PR 23 is a Type-A architectural change (new ~984 LOC Rust module + new trait method + new PyO3 entry). The framework permits audit-cleared PRs to ship end-to-end, but explicit orchestrator OK is recommended for the v1.x → v1.5.0 cutover because of the cascading effects (§8 retest queue). **Default: hold push pending explicit orchestrator OK.**

---

## 4. GitHub release

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0

cat > /tmp/v1.5.0_release_notes.md <<'EOF'
## v1.5.0 — True Nash range-vs-range (MINOR)

**Headline:** PR 23 ports Brown's vector-form CFR algorithm into our Rust tier,
closing the Option B aggregator approximation gap for postflop range-vs-range
subgames. The new `solve_range_vs_range_rust` PyO3 entry walks the betting
tree once and stores per-hand regret / strategy vectors at each infoset —
matching the reference C++ pattern from
`references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`
(MIT-licensed; attribution preserved in `crates/cfr_core/src/dcfr_vector.rs`).

Preflop range-vs-range is deferred to v1.5.1 pending empirical memory
profiling against the 16 GB ceiling.

### What changed

- **New PyO3 entry** `poker_solver._rust.solve_range_vs_range_rust` — JSON
  config in, dict out. Returns `average_strategy: dict[str, list[float]]`,
  `iterations`, `wallclock_seconds`, `decision_node_count`,
  `strategy_entry_count`, `hand_count_per_player`, plus `memory_profile`
  with per-street infoset count + bytes-per-infoset.
- **`Game::hand_count()` trait method** — opt-in vector-form dispatch.
  Existing Kuhn / Leduc / fixed-combo HUNL paths are byte-for-byte
  unchanged on the scalar path.
- **Per-street memory profiler** — measures actual allocated bytes, does
  not extrapolate (per `feedback_no_extrapolate`).

### What this fixes

The Python `solve_range_vs_range` API (`poker_solver.range_aggregator`) is
the Pluribus-blueprint aggregation workaround documented at
`poker_solver/range_aggregator.py:1-32`. It averages per-hand 1v1 Nashes
across villain reps and is **not** a marginal of the joint range Nash. On
polarized hands (AA, KK, 65s) the divergence vs Brown's vector CFR was
empirically mean TV 0.47, max TV 1.00 (see the experimental basis we
prepared while staging this release). PR 23 closes that gap on the Rust
tier; the Python aggregator stays as a fast approximate option.

### Honest scope

- **Postflop only.** Preflop range-vs-range deferred to v1.5.1.
- **Additive API.** Python `solve_range_vs_range` (the aggregator) is
  unchanged; the Rust entry exists alongside as an opt-in path.
- **No UI surface change** in v1.5.0. UI wiring is a v1.5.1+ follow-up.
- **No bucketing** in v1.5.0 — raw 1326-hand dimension postflop. If
  memory pressure surfaces, the v1.5.2 follow-up adds bucketing
  (256 / 128 / 64 per `PLAN.md` §1).
- Existing differentials all stay green — scalar paths unchanged.

### Tests

- `tests/test_range_vs_range_rust_diff.py` covers three differential
  cases (small / medium / production-scale) against the Python ground
  truth.
- The Brown-binary apples-to-apples test gains a new oracle path —
  the new Rust entry should match Brown within float precision.

### Migration

Wheel consumers from v1.4.x must reinstall to pick up the new
`solve_range_vs_range_rust` entry — it lives in the Rust binding
(`poker_solver/_rust.so`) which is rebuilt as part of this release.
EOF

gh release create v1.5.0 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.5.0: True Nash Range-vs-Range" \
  --notes-file /tmp/v1.5.0_release_notes.md

# Verify
gh release view v1.5.0 --repo amaster97/poker_solver | head -10
```

**Sanitization check on release notes:** verify no `/Users/ashen` paths, no PII, no internal planning references. The note above is already clean per the audit at staging — re-verify at ship.

Q: The release notes call out `docs/brown_apples_to_apples_2026-05-23.md` only obliquely ("the experimental basis we prepared while staging this release") to keep the doc reference out of the public release notes. If the orchestrator wants explicit linkage, we can either (a) publish that doc on the public repo first or (b) reword the release notes to drop the reference entirely. **Default: (b) — keep release notes self-contained.**

---

## 5. Retest queue — fire immediately after v1.5.0 ships

Per `feedback_parallel_agents`, spawn ALL of these in parallel one-shot agents. Each writes a short pre/post comparison to `docs/pr13_prep/v1_5_0_<workflow>_retest.md`.

### Tier 1 — Should now PASS (architectural root-cause closed)

| Retest | Spec line / source | Pre-v1.5.0 status | Expected post-v1.5.0 |
|---|---|---|---|
| **Brown apples-to-apples (task #184)** | `docs/brown_apples_to_apples_2026-05-23.md` §6c | mean TV 0.47 vs Brown via aggregator | mean TV ≤ 1e-3 via `solve_range_vs_range_rust` (matches Brown's binary). **This is the load-bearing acceptance gate for v1.5.0.** |
| **W4.3** | `docs/persona_test_results/W4_3_v1_4_0_retest.md` | chance-enum-at-root path failed (Python timeout) | Should PASS — Rust vector CFR makes the empty-hole-cards path tractable |
| **W3.4 retest (re-fire)** | `docs/persona_test_results/W3_4_v1_4_1_retest.md` | Passed in v1.4.1 via asymmetric-contributions fix | Should still PASS — confirm vector CFR doesn't perturb |
| **W2.3 retest (re-fire)** | `docs/persona_test_results/W2_3_v1_4_1_retest.md` | Passed in v1.4.1 via aggregator | Should still PASS — and we can additionally re-run via the new Rust entry as a parity check |
| **W2b.{1,2,5}** | Find current status under `docs/pr13_prep/` (search `phase2b_rvr_results.md`) | reported FAIL in earlier waves; root cause = blueprint vs Nash gap per `brown_apples_to_apples` §4 | Should now PASS via the Rust vector CFR entry |

### Tier 2 — Cost reduction (should be tractable now)

| Retest | Source | Pre status | Expected |
|---|---|---|---|
| **W3.4 long-form retest** | spec line in `persona_acceptance_spec.md` | aggregator-based, ~slow | Faster via Rust vector CFR (target ≤ 1 s on river RvR) |
| **W2.3 long-form retest** | same | same | same |
| **Task #174 DCFR 3.5x slowdown** | follow-up task | reported 3.5x perf regression on some configs | Should close — vector CFR has a different perf profile; bench against v1.4.2 baseline to confirm |

### Spawn signal

READY immediately after `git push origin v1.5.0` returns. Each retest agent is independent — no shared state. Per memory `feedback_min_five_agents`, this wave alone keeps the floor satisfied.

Q: Should the Brown apples-to-apples test (task #184) be the **acceptance gate** for v1.5.0 (block ship if it fails post-build) or be a **post-ship verification** (ship green-build, run as next-wave retest)? **Default: acceptance gate — if it fails in §1c, do not ship.** This is the load-bearing claim of the release.

---

## 6. Cascading PR list

Concrete PRs to spawn after v1.5.0 ships. Some are mechanical (revert + re-test), others are scoped follow-ups.

### Immediate (v1.5.0 day)

1. **PR 25 commit 2 revert in main.** Restore `tests/test_river_diff.py::test_river_parity_vs_brown` to `initial_hole_cards=()`. The PR 25 branch (`pr-25-river-parity-test-fix`) currently has commit `6bf8b9e` ("pass concrete hole cards in _solve_with_our_engine") that the orchestrator wants reverted in v1.5.0 now that Rust can handle it. Strategy: ship the revert as part of the v1.5.0 commit chain (§2c, after the cherry-pick); add it to the CHANGELOG entry's "Reverted" subsection (already done in template §2e). Alternative: ship as a follow-up `v1.5.1-rc` PR if the implementer didn't bundle. **Default: bundle in v1.5.0.**
   - File: `tests/test_river_diff.py:217-243` (the `_solve_with_our_engine` helper).
   - Revert target: PR 25 commit `6bf8b9e` (preserve PR 25 commit 1 `a8f5bf1` — the `@pytest.mark.slow` marker, which is independent).

2. **Task #184 new test.** "Brown apples-to-apples acceptance test using `solve_range_vs_range_rust`." If PR 23 didn't bundle it, the post-ship cascade includes a new test file (likely `tests/test_brown_apples_to_apples_rust.py`) per `docs/brown_apples_to_apples_2026-05-23.md` §6c.
   - Q: Did the implementer of PR 23 add this test? If yes, no separate cascade. If no, spawn tests-from-spec agent.

### v1.5.1 candidates (within 1-2 days)

3. **Task #182 — Python `solve_range_vs_range` delegates to Rust.** Add `use_rust_tier=False` kwarg to `poker_solver/range_aggregator.py:208` (`solve_range_vs_range`). When `True`, route through the new PyO3 entry instead of per-hand aggregation. **Decision: ship as v1.5.1, NOT in v1.5.0.** See §9 below.

4. **Preflop range-vs-range support.** Lift the `starting_street >= Street::Flop` guard in `crates/cfr_core/src/hunl.rs:12-16` for the vector-form path. Gate behind a `--abstract-preflop` flag (suit-iso 169-class reduction) per PR 23 spec §8 Q2 if memory profile shows pressure.

5. **UI surface for true-Nash mode (PR 10b extension).** Add a toggle between "True Nash (Rust vector CFR)" and "Blueprint aggregation (fast)" in the UI. Triggers PR 11 .dmg rebuild per `feedback_ui_packaging_sync`. v1.5.1+ scope.

### v1.5.2 / v1.6.x candidates

6. **Bucketing engagement on postflop streets.** Apply the 256 / 128 / 64 bucket counts to vector-form CFR per PR 23 spec §2. Reduces per-infoset memory from raw 1326 → bucket count. Only needed if production-scale RvR shows memory pressure (per profiler output).

7. **NEON SIMD kernels for vector-form regret update.** PR 23 spec §3 calls out `crates/cfr_core/src/simd.rs` opportunity (Brown's C++ is unvectorized). Defer until profiler shows it as the perf bottleneck.

---

## 7. Risk callouts (concrete)

**A. PR 23 worktree branched off v1.4.0, NOT v1.4.1 / v1.4.2.** At staging time, the worktree's first commit (`609a20f`) sits on top of `166d2b8` (v1.4.0). It has NOT been rebased onto v1.4.1 or v1.4.2 yet. Cherry-picking against the v1.4.2 main will produce conflicts in `CHANGELOG.md`, `poker_solver/__init__.py`, `pyproject.toml`, and **critically** `poker_solver/hunl.py` (PR 22 + PR 23 both touch the postflop init branch). **Mitigation:** require implementer rebase onto v1.4.2 before audit-clear, OR plan for the conflict resolution per the table in §2c.

**B. PR 23 worktree DELETES `tests/test_asymmetric_contributions.py`.** At staging the diff shows `-331` lines on this file. This is a v1.4.1 acceptance test that MUST be preserved. Almost certainly an artifact of branching off v1.4.0 — the file didn't exist in PR 23's base. Cherry-picking blindly would delete it from main. **Mitigation: require rebase onto v1.4.2 before cherry-pick.** Audit gate should explicitly verify the test survives.

**C. Stale `_rust.so` masking the new PyO3 entry.** New `solve_range_vs_range_rust` Python attribute lives in the Rust binding. v1.4.x `_rust.so` will raise `AttributeError` on this name AND mask any new tests that try to call it. **Mitigation: §2d step is non-negotiable.** Smoke command verifies the attribute exists.

**D. `hunl.py` semantic conflict.** PR 22 (v1.4.1) modified the postflop branch of `HUNLPoker.initial_state` for asymmetric contributions. PR 23 adds a vector-mode discriminator to the same surface. The merge must preserve BOTH behaviors — losing either is a silent regression. **Mitigation: explicit code-review step against v1.4.2:poker_solver/hunl.py before resolving the conflict.**

**E. Brown apples-to-apples test as load-bearing acceptance.** Task #184's test is the LOAD-BEARING claim of v1.5.0 ("true Nash range-vs-range"). If the test isn't bundled in PR 23 or doesn't pass post-build, the release notes' headline claim is unfounded. **Mitigation: gate v1.5.0 on the test's existence + green pass.** See §1c Q and §5 Tier 1.

**F. Memory at 16 GB ceiling on full-scale RvR.** Per PR 23 spec §4 + memory profiler output at staging (~138 KB for tiny river RvR; 200-500 infosets at production scale projects to ~100-200 MB). The full preflop case would be at the edge. v1.5.0 is postflop-only specifically to avoid this risk. **Mitigation: postflop scope (release notes already framed this).** v1.5.1 candidate handles preflop after empirical profile.

**G. CHANGELOG conflict zone (LEG 9 + LEG 11 saw this).** v1.4.0, v1.4.1, and v1.4.2 each have their own block. The v1.5.0 entry must be inserted ABOVE all three without disturbing them. Use the Edit tool, not `sed -i`. Post-edit: `grep -c '^## \[1.4.[012]\]' CHANGELOG.md` must return `3`; `grep -c '^## \[1.5.0\]' CHANGELOG.md` must return `1`.

**H. Public repo hygiene on Brown attribution.** `crates/cfr_core/src/dcfr_vector.rs` cites Brown's `trainer.cpp:138-209`. This is REQUIRED (MIT license) and is NOT a hygiene violation. Distinct from PII / session IDs — verify the citation is a file:line reference, not a verbatim absolute path. **Mitigation: §1b sanitization scan explicitly allows MIT-attribution references.**

**I. PR 23 still in flight.** At staging time the implementer has 5 commits; spec §3 + §6 indicate more work may follow (`pr_report.md`, audit gate, possibly task #184 test). SHAs in §2a are placeholders. Re-enumerate at ship time. **Mitigation: §2b explicit re-enumeration step.**

**J. `crates/cfr_core/Cargo.toml` version is at 0.5.0.** PR 23 doesn't bump it at staging. This is consistent with v1.4.0 / v1.4.1 / v1.4.2 history (the crate version is internal and tracks PR milestones, not the user-facing Python package). Skip per §2f.

**K. http.postBuffer.** Per session memory, `git config --global http.postBuffer 524288000` is already set. Push should not stall on the new `_rust.so` blob. If push hangs >60s, kill and retry — do not amend or force.

**L. PR 25 commit 2 revert path.** If the revert is bundled into v1.5.0 (default per §6 item 1), the PR 25 branch becomes partly merged (commit 1) and partly reverted (commit 2 — effectively never lands). Branch cleanup: after v1.5.0 ships, `git branch -d pr-25-river-parity-test-fix` (local only — never `-D` per `feedback_no_concurrent_branch_ops`). Q: Should we keep the branch for historical reference or delete it?

---

## 8. Estimated ship time

Based on LEG 11 (v1.4.1) shipping discipline and scaling for PR 23's larger diff (~1700 LOC vs v1.4.1's ~330 LOC):

| Step | Time |
|---|---|
| Pre-flight (§1) — incl. test suite in worktree | 15-25 min (Rust build + pytest -m "not slow" + new diff tests dominates) |
| Ship worktree creation + cherry-pick (§2a-c) | 5-15 min (more if `hunl.py` conflict requires manual merge) |
| Mandatory Rust rebuild (§2d) | 2-5 min (release build of ~984 LOC new Rust) |
| CHANGELOG + version bump + commit (§2e-f) | 5-8 min (3-block CHANGELOG insert is more involved than LEG 11's 2-block) |
| Tag + push (§3) | 2-3 min |
| GitHub release (§4) | 2-3 min |
| Spawn retest agents (§5) | 3-5 min (5 retests in parallel + Brown task #184 verification) |
| **Total (orchestrator-only)** | **34-64 min** |
| **+ test/build wait** | **15-30 min** |
| **Grand total** | **~50-90 min from PR 23 audit-clear to v1.5.0 live** |

LEG 11 ran ~45 min end-to-end on a single-PR cherry-pick with ~330 LOC. PR 23 is ~5x that diff size + an extra version block + an extra revert (PR 25 commit 2). The 50-90 min range assumes no `hunl.py` conflict resolution; with conflict resolution, add 20-40 min.

**Within-the-hour ship?** Achievable IF (a) PR 23 is rebased onto v1.4.2 BEFORE audit-clear (eliminating the conflict surface), AND (b) the Brown apples-to-apples test (task #184) is bundled in PR 23. If those two preconditions are met, total ship time drops to **30-45 min** — within the user's "ship within an hour" target. If not, plan for ~75-90 min.

Add 30-90 min for the Tier 1 + Tier 2 retests (§5) to return — they run in parallel after ship, NOT on the critical path.

Q: Should we ask the implementer to rebase PR 23 onto v1.4.2 NOW (while still iterating) to derisk the ship? **Default: yes.**

---

## 9. Decision point — task #182 in v1.5.0 OR v1.5.1?

**Question:** Should the Python `solve_range_vs_range` aggregator (in `poker_solver/range_aggregator.py`) be rewired to delegate to the new Rust `solve_range_vs_range_rust` entry as part of v1.5.0?

**Option A — Ship in v1.5.0 (one release).**
- Pro: single release captures the full value (Rust capability + Python API parity).
- Pro: end users get true-Nash RvR via the existing `solve_range_vs_range` call without code changes.
- Con: doubles the v1.5.0 diff surface (range_aggregator.py is ~1000 LOC). More audit, more risk, more conflict potential.
- Con: the Python aggregator's existing tests (`test_range_vs_range_aggregator.py`) become an oracle for the Rust path — possible spurious test churn.
- Con: changes the public API behavior (existing callers get a different result), arguably bumping to MAJOR not MINOR — risky.

**Option B — Defer to v1.5.1 (sequential releases).**
- Pro: v1.5.0 is a clean MINOR (additive PyO3 entry only; no public API behavior change).
- Pro: the Python aggregator stays as the fast approximate fallback (documented in the existing docstring); the Rust entry is the explicit opt-in for true Nash.
- Pro: rapid v1.5.0 ship (within-the-hour achievable); v1.5.1 follows when task #182 lands.
- Con: end users need to know about the new `solve_range_vs_range_rust` entry to get true Nash; the "default" is still blueprint aggregation.
- Con: two releases on consecutive days.

**Recommendation: Option B (defer to v1.5.1).** Reasons:

1. Per PR 23 spec §8 Q3 (default decision authority): "leave the Python aggregator untouched in v1.5.0, ship only the PyO3 binding. v1.5.1 wires it."
2. PR 23 implementer is already at ~1700 LOC of diff; bundling task #182 would push it to ~2700+ LOC — increases audit-cycle time, delays ship.
3. The MINOR bump argument is cleaner with Option B (purely additive). Option A could be argued as MAJOR (behavior change in `solve_range_vs_range`) which would trigger a separate set of comms / migration concerns.
4. Two releases in 24-48 h is consistent with the v1.3.0 → v1.3.1 → v1.3.2 cadence the project has already established.

**Default decision: Option B.** Q: Override?

---

## 10. Hard rules (carry-over from LEG 9 + LEG 11)

- Autonomous push authorized per `feedback_pr10a5_autonomous_commit` for audit-cleared PRs — but per §3 Q above, the orchestrator may want explicit OK for the v1.4.x → v1.5.0 MINOR cutover because of cascading effects.
- DO NOT use `git add -A` or `git add .` in the ship worktree — stage by explicit path.
- DO NOT touch `.gitignore` during ship.
- Cherry-pick conflict beyond mechanical (e.g. semantic `hunl.py` merge) → STOP and report.
- DO NOT skip `maturin develop --release` between cherry-pick and any pytest invocation (Risk §C).
- DO NOT amend prior v1.4.x release commits or CHANGELOG blocks (Risk §G).
- Retest spawn is REQUIRED post-ship because v1.5.0 closes the architectural Brown-parity gap — multiple workflows should now pass that previously failed.
- DO NOT delete the `tests/test_asymmetric_contributions.py` file at any point (Risk §B). It's an active v1.4.1 acceptance test.
- Branch hygiene per `feedback_pr_branch_hygiene` + `feedback_no_concurrent_branch_ops` — work in the dedicated ship worktree; do NOT branch-switch in the shared tree.
- Pre-push sanitization per `feedback_public_repo_hygiene` — re-verify release notes contain no `/Users/ashen` paths, no session IDs, no internal planning references.
- After ship: clean up `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.5.0` per LEG 11 §8 pattern.

---

## 11. Pre-conditions checklist (orchestrator gates)

Before firing this plan, the orchestrator must confirm:

- [ ] v1.4.2 has shipped to origin (tag + main commit aligned). If not, ship v1.4.2 first.
- [ ] PR 23 audit-cleared by a fresh audit agent.
- [ ] PR 23 rebased onto v1.4.2 (RECOMMENDED — eliminates the conflict surface and the `test_asymmetric_contributions.py` deletion bug).
- [ ] PR 23 includes the Brown apples-to-apples test (task #184), OR a parallel tests-from-spec agent has prepared it.
- [ ] Decision on task #182 (Option A vs B) — default Option B if no override.
- [ ] PR 25 commit 2 revert strategy decided (default: bundle in v1.5.0).
- [ ] Explicit orchestrator OK to push v1.5.0 (recommended given MINOR cutover scope).

Once all six are checked, this plan is paste-ready end-to-end.

---

## 12. Open questions summary (consolidated)

For quick orchestrator scan:

| Q | Section | Default | Override needed? |
|---|---|---|---|
| Did implementer squash commits? | §1a | enumerate at ship time | No — re-enumerate |
| Brown apples-to-apples test bundled in PR 23? | §1c | hope yes; spawn parallel agent if not | If not bundled, MUST spawn |
| v1.4.2 shipped to origin by ship time? | §1d | yes (ship v1.4.2 first) | If no, fall back to v1.4.1 baseline + add marker fix |
| PR 23 rebased onto v1.4.2? | §2c, §7A,B,D | request rebase | STRONGLY recommend |
| Bundle PR 25 commit 2 revert in v1.5.0? | §2e, §6.1 | yes (bundle) | Alternative: ship as v1.5.1-rc |
| Release notes link to apples-to-apples doc? | §4 | no (self-contained) | If yes, publish doc first |
| Brown parity test = acceptance gate or post-ship? | §5 Tier 1 | acceptance gate | If post-ship, ship faster but riskier |
| Task #182 in v1.5.0 or v1.5.1? | §9 | v1.5.1 (Option B) | Override to bundle = MAJOR risk |
| Autonomous push or explicit OK? | §3, §10 | explicit OK for MINOR | If full autonomy, ship within-the-hour |

---

## 13. Sanity references

- PR 23 spec: `docs/pr_proposals/v1_5_rust_dcfr_widening.md`
- LEG 11 plan: `docs/leg11_v1_4_1_ship_plan.md` (template)
- LEG 11 report: `docs/leg11_v1_4_1_ship_report.md` (lessons — `maturin develop --release` + isolated ship worktree)
- Brown experimental basis: `docs/brown_apples_to_apples_2026-05-23.md`
- PR 23 worktree current: `/Users/ashen/Desktop/poker_solver_worktrees/pr-23-rust-dcfr-widening` (5 commits at staging, `8d1c41f` tip)
- v1.4.2 ship worktree (pending push to origin): `/Users/ashen/Desktop/poker_solver_worktrees/ship-v1.4.2` (4 commits ahead of v1.4.1, tip `d9094c2`)
- PR 25 branch (for revert reference): `pr-25-river-parity-test-fix`, commit `6bf8b9e` is the target of the v1.5.0 revert
- Reference C++ (load-bearing for PR 23 attribution): `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209` (MIT)

---

**Status: PRE-STAGED. Ready to fire when §11 gates are green.**
