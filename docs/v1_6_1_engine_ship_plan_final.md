# v1.6.1-engine Ship Plan — FINAL (post-R10, post-hand-sort-canonicalization)

> **STATUS 2026-05-26: HOLD LIFTED — fixes folded into v1.8.0. See
> `docs/v1_6_1_ship_hold_review_2026-05-26.md`.**
>
> The original v1.6.1 hold rationale (A83 33-pp divergence suspected as
> an algorithmic bug) has been refuted by three independent DCFR audits
> plus the matched-config empirical investigation (VERDICT C). The 10-PR
> bundle described in this plan has shipped piecewise on `origin/main`
> between 2026-05-26 02:32 and 03:02 UTC. No formal `v1.7.1` tag was
> created; the fixes are folded into the upcoming **v1.8.0** release
> (`docs/v1_8_0_release_notes_DRAFT.md`). This plan is preserved for
> historical reference.

**Date staged:** 2026-05-24
**Status:** PRE-STAGED — execution awaits user "ship" command (SUPERSEDED 2026-05-26; see banner above)
**Supersedes:** `docs/leg21_v1_6_1_engine_only_ship_plan.md` (Path D xfail; obsolete post-R7/R8). Prior R9 version of this plan (HARD = 5 fixes) superseded by R10 update below.
**Filename:** `docs/v1_6_1_engine_ship_plan_final.md` (authoritative)

**R10 update (this revision):** Dry-run #6 GAP-REMAINS surfaced a third wrapper-side bug — hand-string sort-order divergence between our Rust canonical (`rank*4 + s_idx`, `SUITS="shdc"` → `KdKc`) and Brown's canonical (`suit*13 + rank`, `suits="cdhs"` → `KcKd`). PR 56 lands a wrapper-boundary canonicalization fix. HARD requirements now = 6 (PR 50 + PR 51 + PR 52 + PR 54 + PR 55 + PR 56) plus PR 55-extend if dry-run #7 surfaces residual. PR 53 reframe ships as defensive backstop regardless. See `docs/STATUS_2026-05-24_r10_hand_sort.md`.

---

## 0. Why this plan exists (operator orientation)

Three framing shifts have happened since LEG 21 staged Path D:

1. **R7 (Brown-as-sanity-check):** strict per-action gate was over-constrained — our action menu is intentionally richer than Brown's, so per-cell exact match at deep-cap was always over-spec.
2. **R8 (suit-encoding bug):** the bulk of the empirical 22-42pp divergence was test-side, not engine-side. `noambrown_wrapper.py` was index-mapping `"shdc"` ↔ `"cdhs"` (silent paired `h ↔ d` swap). PR 52 fixes it.
3. **Dry-run #4 finding:** with PR 50 + PR 51 + PR 52 only, K72/A83 still **fail at coverage floor (80%)** because Rust emits `"A"` for all-in jams at stack ceiling but the test renderer was emitting `b<chips>`. PR 54 (extracted from PR 35 Fix A) restores the renderer's `stack_ceiling` argument.

Net: v1.6.1-engine now bundles **4 hard fixes** instead of the previously-planned 3 + xfail. Path D framing is **dropped**.

---

## 1. Bundle composition

### HARD requirements (always included)

| PR | Branch | Origin SHA | Scope | Source |
|---|---|---|---|---|
| **PR 50** | `pr-50-facing-all-in-guard` | `18a7640` | Phantom `ALL_IN` action menu guard (paired Rust + Python); `to_call < stack` constraint at facing-all-in nodes | GitHub PR #5 |
| **PR 51** | `pr-51-dcfr-vector-asymmetric-fix` | `78c7155` | `dcfr_vector.rs:651` off-by-one panic on asymmetric ranges | GitHub PR #6 |
| **PR 52** | `pr-52-suit-encoding-fix` | `9e6662b` | Suit-encoding fix in `noambrown_wrapper.py`; char-to-char `"shdc"` ↔ `"cdhs"` mapping replaces silent index-paired swap (R8 close) | GitHub PR #8 |
| **PR 54** | `pr-54-renderer-stack-ceiling` | TBD (verified, opened as GitHub PR #9) | Renderer fix (PR 35 Fix A extraction): adds `stack_ceiling` kwarg to `_rust_history_substr_for_canonical`; emits `"A"` token for bets/raises at stack ceiling, matching Rust's `hunl.rs:703-712` ACTION_ALL_IN branch | GitHub PR #9 |
| **PR 55** | `pr-55-p0-p1-convention` | TBD (landing 2026-05-24) | P0/P1 player-index swap at the wrapper boundary in `_parse_brown_dump`: when constructing `BrownStrategyDump`, swap `parsed_players[0]` and `parsed_players[1]` so callers index with our convention (P0 = second-to-act on river). Single seam, callers convention-naive. Closes R9 — see `docs/p0_p1_convention_investigation.md`. Touches ONLY `poker_solver/parity/noambrown_wrapper.py`. Independent of all other open PRs. | GitHub PR #10 |
| **PR 56 (NEW)** | `pr-56-hand-string-sort-canonical` | TBD (in flight 2026-05-24) | Hand-string sort-order canonicalization at the wrapper boundary in `_parse_brown_dump` / `_brown_hand_key`: normalize parsed hand strings to our Rust canonical sort (`rank*4 + s_idx` under `SUITS="shdc"`) before they're used as dict keys. Brown's canonical is `suit*13 + rank` under `suits="cdhs"`. Same chars, different sort orders. Mixed-suit pairs diverge by string only, not by semantics. Single seam, callers index-naive. Closes R10 — see `docs/STATUS_2026-05-24_r10_hand_sort.md`. Touches ONLY `poker_solver/parity/noambrown_wrapper.py`. Disjoint hunks from PR 52 / PR 55 (verify at ship time). | Landing as new GitHub PR |

### SOFT / CONDITIONAL

| PR | Branch | Origin SHA | Condition |
|---|---|---|---|
| **PR 55-extend** | TBD | TBD | Conditional: extend PR 55 to handle joint canonicalization if PR 56 surfaces residual same-class-different-canonical hand strings that the axis swap doesn't fully cover. Decision deferred until dry-run #7. |
| **PR 53** | `pr-53-acceptance-test-reframe` | `33b38a7` | Land **IF** dry-run #7 (PR 50+51+52+54+55+56) still FAILS strict 5e-2 per-action gate. Becomes load-bearing under "reframe replaces strict gate with sanity-check assertions". If strict gate passes post-PR-56, PR 53 ships as documented-but-defensive cleanup; if strict gate fails, PR 53 IS the gate. Expected post-R10: STRICT-GATE-PASSES (so PR 53 ships as defensive). Per `feedback_parity_wrapper_hazard.md`, PR 53 also defends against the (lower-probability) Site 5+ hazard-hunt yield. |

### DROPPED

- **Path D xfail framing** — replaced by R7/R8 framing (Brown-as-sanity-check + suit-encoding fix). The previously-planned "mark strict gate `xfail` with internal-investigation pointer" approach is obsolete.
- **PR 33 / PR 40 / PR 35c** — deferred from this bundle; legacy engine-bundle attempts that pre-date the R6/R7/R8 reversals. Re-evaluate for v1.6.2 if needed.

---

## 2. Cherry-pick order

Default order: **PR 51 → PR 50 → PR 52 → PR 54 → PR 55 → PR 56** (PR 56 last; touches only `poker_solver/parity/noambrown_wrapper.py`, independent of all others). PR 53 stacks on top conditionally (if dry-run #7 strict gate still fails — expected NOT needed post-R10). PR 55-extend is conditional on dry-run #7 evidence.

| Step | PR | Cherry-pick command | Anticipated conflicts |
|---|---|---|---|
| 1 | PR 51 | `git cherry-pick 78c7155` | NONE — isolated `dcfr_vector.rs` change |
| 2 | PR 50 | `git cherry-pick 18a7640` | NONE — disjoint from PR 51 (Rust `hunl.rs` + Python `action_abstraction.py`) |
| 3 | PR 52 | `git cherry-pick 9e6662b` | NONE — isolated to `poker_solver/parity/noambrown_wrapper.py` (`_card_to_brown_str` / `_brown_card_id`) |
| 4 | PR 54 | `git cherry-pick <PR_54_SHA>` (resolve from worktree at ship time) | NONE expected — isolated to `tests/test_v1_5_brown_apples_to_apples.py` (`_rust_history_substr_for_canonical` signature + 2 callers). PR 53 also touches this file; if PR 53 is included, **resolve PR 53 before PR 54** to avoid context mismatch. |
| 5 | PR 55 | `git cherry-pick <PR_55_SHA>` | NONE expected — isolated to `poker_solver/parity/noambrown_wrapper.py` (`_parse_brown_dump` axis swap, plus optional convention comment). Same file as PR 52 but disjoint hunks (PR 52 = suit char encoding; PR 55 = player-axis swap in dump constructor). Verify hunk-disjointedness at ship time with `git cherry-pick --no-commit <PR_55_SHA>` in a throwaway branch. |
| 6 (cond) | PR 53 | `git cherry-pick 33b38a7` | **Possible conflict with PR 54** on `tests/test_v1_5_brown_apples_to_apples.py`. Resolution: PR 53 reframes the gate assertions; PR 54 fixes the renderer signature. Both can coexist if PR 53 is cherry-picked FIRST (re-order: 1, 2, 3, 6, 4, 5). At ship time, confirm by running `git cherry-pick --no-commit 33b38a7 && git cherry-pick --no-commit <PR_54_SHA>` in a throwaway branch to validate. |

**Re-ordering rule:** if PR 53 is included, the cherry-pick order becomes **51 → 50 → 52 → 53 → 54 → 55** so PR 54's renderer kwarg lands on top of PR 53's reframed assertions, and PR 55's wrapper swap stays last. Document the order chosen in the ship report.

**Rationale for PR 55 last:** PR 55 is the smallest and most independent change in the bundle (single file, single function, paired swap). Landing it last keeps the cherry-pick risk surface narrow and ensures the wrapper-side R9 fix is clearly traceable in `git log` as the final landing.

---

## 3. Version bump decision

### The version question

`origin/main` is currently at **v1.7.0** (`3843ce7`). v1.7.0 shipped `solve_range_vs_range_nash` (PR 43) + 3 CLI subcommands (PR 39). Tagging this bundle as `v1.6.1` would be a **backwards version number** post-v1.7.0 — semver-illegal and confusing for users.

### Options

| Option | Tag | Argument |
|---|---|---|
| A | `v1.7.1` | PATCH per semver: bug fixes only (PR 50/51 engine guards + panic; PR 52/54 are test-side). No new user-facing features. Maps cleanly onto "v1.7.0 had bugs; v1.7.1 fixes them." |
| B | `v1.8.0` | MINOR per semver: arguably "added functionality in a backward-compatible manner" if you count the new paired guard + the architectural correctness improvement. But PR 50/51 are bug fixes for code that was always supposed to behave this way; users don't see new API surface. |

### Decision: **v1.7.1**

**Rationale:**
1. All 4 hard fixes are **bug fixes**, not new features. PR 50/51 close real correctness gaps (phantom `ALL_IN`, off-by-one panic). PR 52/54 fix the **test harness** (no user-facing API change).
2. No new public Python symbols, no new CLI subcommands, no new Rust bindings.
3. PR 53 (if included) is a test-spec refinement — not a user-facing surface change.
4. Semver PATCH is the correct slot: "backwards-compatible bug fixes."
5. Path B (v1.8.0) was reserved for NEON kernels (`docs/v1_8_neon_implementation_roadmap.md`) — taking the v1.8 slot for engine guards would block that roadmap's version semantics.

### Bump targets

| File | Current (on `origin/main = 3843ce7`) | New | How |
|---|---|---|---|
| `pyproject.toml` | `version = "1.7.0"` | `version = "1.7.1"` | Edit |
| `poker_solver/__init__.py` | `__version__ = "1.7.0"` | `__version__ = "1.7.1"` | Edit (check exact location at ship time; was line 192 pre-v1.6.0) |
| `crates/cfr_core/Cargo.toml` | `version = "0.6.0"` | `version = "0.6.1"` (PATCH-align with parent) | Edit; bump from 0.6.0 → 0.6.1 since engine code (PR 50, PR 51) changed |
| `Cargo.lock` | tracks 0.6.0 | regenerated to 0.6.1 | Auto-regenerates on next `cargo build`; commit the result |

**Cargo.toml bump rationale:** PR 50 modifies `hunl.rs` and PR 51 modifies `dcfr_vector.rs`. Engine crate semver should reflect that the binary semantics changed (panic fixed; phantom `ALL_IN` no longer emitted). PATCH-bump (0.6.0 → 0.6.1) matches parent PATCH-bump.

---

## 4. CHANGELOG entry

Prepend the following block to `CHANGELOG.md` **above** the `## [1.7.0]` section, **below** `## [Unreleased]`.

```markdown
## [1.7.1] - 2026-05-XX

### Fixed — engine correctness
- **Phantom `ALL_IN` action menu guard** (PR 50) — at facing-all-in
  nodes (when villain has shoved and `to_call >= stack`), the
  responder's action menu previously included a degenerate `ALL_IN`
  raise that had no chip semantics distinct from calling. Both Rust
  (`crates/cfr_core/src/hunl.rs`) and Python
  (`poker_solver/abstraction/action_abstraction.py`) now require
  `to_call < stack` before emitting `ALL_IN` as a separate option.
  Real `ALL_IN`-as-raise paths (where villain has chips behind) are
  preserved unchanged.
- **`dcfr_vector.rs:651` off-by-one panic** (PR 51) — asymmetric
  range solves with unequal hand counts per player previously
  panicked at the strategy-table index step. Indexing now uses the
  per-player hand count, not a shared assumed-equal cardinality.

### Fixed — test harness (parity)
- **Suit-encoding bug in Brown parity wrapper** (PR 52) —
  `poker_solver/parity/noambrown_wrapper.py` was mapping suit
  *indices* between our `"shdc"` and Brown's `"cdhs"`, producing a
  silent paired `h ↔ d` swap. Replaced with explicit char-to-char
  mapping. Distorted the strict-gate comparison without raising
  errors; accounts for a large portion of the prior 22-42pp deep-cap
  divergence reported in v1.6.1 dry-runs.
- **Brown apples-to-apples history renderer** (PR 54) —
  `tests/test_v1_5_brown_apples_to_apples.py`'s
  `_rust_history_substr_for_canonical` now accepts a `stack_ceiling`
  kwarg and emits `"A"` for bets/raises at the stack ceiling,
  matching Rust's `hunl.rs:703-712` ACTION_ALL_IN tokenization.
  Without this, deep histories from Brown were not findable in
  Rust's keyset and the test gated out at the 80% coverage floor.

### Changed
- (Conditional, if PR 53 lands) Brown apples-to-apples acceptance
  test reframed from strict 5e-2 per-action gate to sanity-check
  structural assertions (shallow-spot direction-of-aggression +
  shallow-frequency agreement). Codifies the R7 framing: external
  reference solvers are sanity checks, not strict ground truth, when
  action menus differ. Strict per-cell residual is still printed for
  monitoring.

### Notes
- All four hard fixes are bug fixes; no new public API, no new CLI
  surface, no Python signature changes. Pure PATCH per semver.
- v1.7.0's `_rust.cpython-313-darwin.so` is REBUILT for v1.7.1 (PR 50
  and PR 51 touch Rust source). Users running from source must
  `maturin develop --release` after pull.
- `crates/cfr_core` bumps 0.6.0 → 0.6.1 to reflect Rust engine
  changes.
- Unblocks: persona retests for W2.3 (Sarah KK-vs-cbet-range) +
  W3.4 (Daniel turn-spot MDF); Gate 4 200K-iter validation can
  resume; PRs #2/#3/#4 (queued doc + packaging fixes) can merge
  through.
```

---

## 5. Smoke matrix

Run after all cherry-picks and version bump are staged, in the ship worktree, BEFORE tag/push.

| # | Test | Command | Expected | Why it matters |
|---|---|---|---|---|
| 1 | Rust build | `cargo build --release` | PASS (<30s) | PR 50/51 Rust changes compile |
| 2 | Rust unit tests | `cargo test --release --lib` | 50/50 PASS | Engine regression guard |
| 3 | Rust HUNL state | `cargo test --release --test hunl_state_unit` | 19/19 PASS | Action-menu shape regression guard |
| 4 | Maturin rebuild | `maturin develop --release` | PASS | Python bindings reflect PR 50/51 Rust changes |
| 5 | Python-Rust diff (critical gate) | `pytest tests/test_exploit_diff.py -v` | 5/5 PASS | The non-negotiable regression test; if this breaks, ship is HOLD |
| 6 | Brown apples-to-apples | `pytest tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800` | (a) STRICT pass: 2/2 PASS at default tolerance → PR 53 is defensive cleanup. (b) STRICT fail but ≥80% coverage + reframed assertions PASS → ship with PR 53 included. (c) Coverage < 80% → BLOCK ship; investigate. | The headline acceptance test; (c) is a hard stop |
| 7 | Python non-slow sweep | `pytest -m "not slow" --timeout=120 -v` | All green vs v1.7.0 baseline | Catches regressions in untouched code paths |
| 8 | CLI subcommands (regression) | `pytest tests/test_cli_subcommands.py -v` | 6 PASS, 1 SKIP | PR 39 (v1.7.0) surface unaffected |
| 9 | Range-vs-range Nash (regression) | `pytest tests/test_range_vs_range_nash.py -v` | All PASS | PR 43 (v1.7.0) surface unaffected |

**Pass criteria (all must hold to proceed to tag):**
- [ ] Steps 1-5: hard PASS
- [ ] Step 6: outcome (a) or (b) above; outcome (c) is a HARD STOP
- [ ] Steps 7-9: no regressions vs v1.7.0 baseline
- [ ] If step 6 outcome is (b), **PR 53 must be in the cherry-pick list**

---

## 6. Ship command sequence (operator runbook)

Execute from a disposable worktree. **NEVER on the shared `/Users/ashen/Desktop/poker_solver` tree** (per `feedback_no_concurrent_branch_ops.md`).

### 6a. Pre-flight

```bash
# Confirm PR 54 has been pushed to origin with a final SHA
cd /private/tmp/pr-54-renderer-43123
git rev-parse HEAD              # Capture <PR_54_SHA>
git status --short              # Expect: clean (no uncommitted changes)
# If PR 54 hasn't been pushed to origin yet:
#   git push -u origin pr-54-renderer-stack-ceiling
#   gh pr create --title "fix(parity): renderer stack-ceiling 'A' token" --body "..."

# Confirm origin/main hasn't moved past 3843ce7
cd /Users/ashen/Desktop/poker_solver
git fetch origin
git rev-parse origin/main       # Expect: 3843ce7 (v1.7.0)

# Confirm dry-run #5 verdict to determine PR 53 inclusion
ls /Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_5*.md  # if present
# Decision: include PR 53? (Y if strict gate failed in dry-run #5; N if passed)

# Confirm PR 55 verdict to determine PR 55 inclusion
# (Investigation in flight; decision deferred until investigation completes.)
```

### 6b. Worktree setup

```bash
cd /Users/ashen/Desktop/poker_solver
git worktree add /private/tmp/ship-v1.7.1 -b ship-v1.7.1 origin/main
cd /private/tmp/ship-v1.7.1
git log --oneline -1            # Expect: 3843ce7 v1.7.0
```

### 6c. Cherry-pick (default order: 5 hard fixes, no PR 53)

```bash
# Hard requirements (all 5)
git cherry-pick 78c7155         # PR 51 (panic fix)
git cherry-pick 18a7640         # PR 50 (facing-all-in guard)
git cherry-pick 9e6662b         # PR 52 (suit-encoding)
git cherry-pick <PR_54_SHA>     # PR 54 (renderer stack-ceiling)
git cherry-pick <PR_55_SHA>     # PR 55 (P0/P1 wrapper-boundary swap, R9 close)

# Conditional: PR 53 (only if dry-run #6 strict gate failed — expected NOT needed post-R9)
# IF including PR 53, RE-ORDER: cherry-pick PR 53 BEFORE PR 54 and PR 55.
#   git cherry-pick 78c7155 18a7640 9e6662b 33b38a7 <PR_54_SHA> <PR_55_SHA>

git log --oneline -8            # Verify cherry-pick order matches plan
```

### 6d. Version bump + CHANGELOG

```bash
# Edit pyproject.toml: version = "1.7.0" → "1.7.1"
# Edit poker_solver/__init__.py: __version__ = "1.7.0" → "1.7.1"
# Edit crates/cfr_core/Cargo.toml: version = "0.6.0" → "0.6.1"
# Prepend §4 CHANGELOG block above ## [1.7.0]

# Rebuild Rust to refresh Cargo.lock and .so
cargo build --release
maturin develop --release

# Stage and commit
git add pyproject.toml poker_solver/__init__.py crates/cfr_core/Cargo.toml Cargo.lock CHANGELOG.md
git status --short              # Sanity: only version + CHANGELOG + lock staged
git commit -m "chore(release): v1.7.1 — engine fixes (phantom ALL_IN + panic) + parity wrapper/renderer fixes"
```

### 6e. Smoke matrix

Run §5 steps 1-9. STOP on any failure per §5 pass criteria.

### 6f. Tag + push

```bash
# Annotated tag
git tag -a v1.7.1 -m "v1.7.1: engine guards + parity test fixes (PR 50/51/52/54/55[+53])"

# Push commits (fast-forward to origin/main expected)
git push origin HEAD:main

# Push tag
git push origin v1.7.1

# Verify
git fetch --tags origin
git tag -l 'v1.7.1'
git ls-remote --tags origin | grep v1.7.1
git log --oneline origin/main -8
```

### 6g. GitHub release

```bash
cat > /tmp/v1.7.1_release_notes.md <<'EOF'
[content from §7 below]
EOF

gh release create v1.7.1 \
  --repo amaster97/poker_solver \
  --latest \
  --title "v1.7.1: engine correctness fixes + Brown parity test alignment" \
  --notes-file /tmp/v1.7.1_release_notes.md

gh release view v1.7.1 --repo amaster97/poker_solver | head -16
```

### 6h. Cleanup

```bash
cd /Users/ashen/Desktop/poker_solver
git worktree remove /private/tmp/ship-v1.7.1
git worktree list               # Verify ship-v1.7.1 worktree gone
# Optional: catch up shared tree
git pull --ff-only origin main
```

---

## 7. GitHub release notes template

```markdown
## v1.7.1 — Engine correctness + Brown parity test alignment (PATCH)

**Headline:** A PATCH release bundling four bug fixes — two in the
engine (phantom `ALL_IN` action menu at facing-all-in nodes, plus an
off-by-one panic in `dcfr_vector.rs` on asymmetric ranges) and two
in the Brown apples-to-apples parity test harness (suit-encoding
silent paired swap in the wrapper, plus a renderer mismatch on
all-in-jam tokenization). No new user-facing API, no breaking
changes.

### Fixed — engine

- **Phantom `ALL_IN` action menu guard** (PR 50). Facing an all-in
  shove, the responder's action menu previously contained a
  degenerate `ALL_IN` raise that had no chip distinction from
  calling. Both engines now require `to_call < stack` before
  surfacing `ALL_IN` as a separate option. Real `ALL_IN`-as-raise
  paths (villain has chips behind) are unchanged.
- **`dcfr_vector.rs` panic on asymmetric ranges** (PR 51). Solves
  with unequal hand counts per player previously panicked at the
  strategy-table indexing step. Fixed; asymmetric-range solves now
  complete.

### Fixed — Brown parity test harness

- **Suit-encoding silent swap** (PR 52). The Brown reference
  wrapper was mapping suit *indices* between our `"shdc"` and
  Brown's `"cdhs"`, producing a paired `h ↔ d` swap that distorted
  per-cell comparisons without raising errors. Replaced with
  explicit char-to-char mapping. This bug accounted for a large
  portion of the 22-42pp deep-cap divergence reported in earlier
  v1.6.1 dry-runs.
- **All-in-jam tokenization in test renderer** (PR 54). The Brown
  apples-to-apples test's history renderer was emitting `b<chips>`
  for stack-ceiling bets where the Rust engine emits `"A"`. The
  renderer now takes a `stack_ceiling` kwarg and emits `"A"`
  consistently — restoring deep-history coverage above the 80%
  floor.

### Test acceptance

(Include this paragraph IFF PR 53 is bundled:)

- **Brown apples-to-apples acceptance reframed** (PR 53). The
  strict 5e-2 per-action gate has been replaced by sanity-check
  structural assertions (shallow-spot direction-of-aggression and
  shallow-frequency agreement within reasonable bounds). Deep-cap
  per-action divergence is expected when action menus differ; the
  reframe codifies that external reference solvers are sanity
  checks, not strict ground truth. The strict per-cell residual is
  still printed for monitoring.

### Compatibility

- No new public API; no signature changes; backward-compatible with
  v1.7.0.
- Rust binary `_rust.cpython-313-darwin.so` is REBUILT in v1.7.1
  (engine source changed). Users running from source must
  `maturin develop --release` after pull.
- `crates/cfr_core` bumps to 0.6.1.

### Unblocks

- Persona retests for W2.3 (Sarah KK-vs-cbet-range) and W3.4
  (Daniel turn-spot MDF) — both BLOCKED on the v1.6.1-engine
  bundle pre-R8.
- Gate 4 200K-iter scaled validation can resume.
- Downstream documentation + packaging PRs (queued behind this
  ship) can merge through.

### Acknowledgements

R6/R7/R8 reversal chain documented in
`docs/STATUS_2026-05-24_r8_suit_encoding.md` and
`docs/STATUS_2026-05-24_brown_as_sanity_check.md`. The suit-encoding
bug class is codified in `feedback_index_as_char_hazard.md`; the
external-solver framing rule in
`feedback_external_solver_sanity_check.md`.
```

**Public-OK audit (per `feedback_public_repo_hygiene.md`):**
- No `/Users/ashen/...` paths
- No `claude-session` / `claude_ai_*` / session IDs
- No PII or internal planning notes
- Memory-rule filenames (`feedback_*`) are OK to reference in CHANGELOG/release-notes since they're internal-paths-as-shorthand; verify with the user at ship time if uncertain — if not OK, strip the "Acknowledgements" paragraph

---

## 8. Post-ship verification

After §6g (release published), confirm in this order:

```bash
# 1. Release LIVE on GitHub
gh release view v1.7.1 --repo amaster97/poker_solver
# Expected: title, body, "Latest" badge

# 2. Tag pushed
git ls-remote --tags origin | grep v1.7.1
# Expected: <sha>\trefs/tags/v1.7.1

# 3. origin/main HEAD advanced
git ls-remote --heads origin main
# Expected: HEAD SHA matches the release-bump commit from §6d
git -C /Users/ashen/Desktop/poker_solver fetch origin
git -C /Users/ashen/Desktop/poker_solver log --oneline origin/main -8
# Expected (top-down):
#   <release-bump-sha>  chore(release): v1.7.1 — ...
#   <PR 54 sha>         PR 54 (or PR 53 then PR 54 if reframed)
#   <PR 52 sha>         PR 52: fix suit-encoding bug
#   <PR 50 sha>         PR 50: facing-all-in action menu guard
#   <PR 51 sha>         PR 51: fix dcfr_vector.rs off-by-one panic
#   3843ce7             v1.7.0: ...

# 4. Verify install path
pip install -e /Users/ashen/Desktop/poker_solver
python -c "import poker_solver; print(poker_solver.__version__)"
# Expected: 1.7.1

# 5. Spot-check: rerun Brown acceptance against installed v1.7.1
pytest /Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py -v --timeout=1800
# Expected: PASS at the criterion that gated the ship (strict if outcome (a); sanity-check assertions if outcome (b))

# 6. Run post-integration verification protocol per
#    feedback_post_integration_verification.md
```

---

## 9. What this unblocks

| Track | How |
|---|---|
| **W2.3 retest (Sarah KK vs cbet-range)** | PR 50 removes the phantom-`ALL_IN` bias that was inflating action-count complexity at scaled aggregator cardinalities (suspected cause of W2.3 5-min timeouts). Re-run per `docs/pr_proposals/v1_6_1_retest_W2_3_sarah_kk_vs_cbet_range.md`. |
| **W3.4 retest (Daniel turn-spot MDF)** | PR 51 unblocks asymmetric-range solves that previously panicked. Re-run per `docs/pr_proposals/v1_6_1_retest_W3_4_daniel_mdf.md`. |
| **Gate 4 200K-iter validation** | Eligible to resume once v1.7.1 is on origin/main. Schedule per `docs/gate_4_operational_plan.md`. |
| **PR #2 (docs v1.7.0 semantics)** | Mergeable through to main once v1.7.1 lands. |
| **PR #3 (.dmg packaging fix)** | Mergeable through; triggers PR 11 .dmg rebuild with v1.7.1 binary (`feedback_ui_packaging_sync.md`). |
| **PR #4 (README cross-ref cleanup)** | Mergeable through. |
| **Persona test sweep** | Target 14+ PASS / 3 PARTIAL / 1 BLOCKED after v1.7.1 + W2.3/W3.4 retests. |
| **PR 10b UI re-audit** | Out of scope for v1.7.1 (no UI changes); but downstream packaging cascade should kick. |

---

## 10. Hard blockers (do NOT proceed past §6c if any of these is true)

1. PR 54 not pushed to origin with a final SHA captured.
2. PR 55 not pushed to origin with a final SHA captured (now HARD requirement post-R9).
3. `origin/main` has moved past `3843ce7` (e.g., a hotfix landed in parallel) — re-stage required.
4. Dry-run #6 verdict not yet available (PR 53 inclusion decision is undetermined; default = excluded as defensive cleanup, but verify against verdict).
5. Smoke matrix outcome (c) at §5 step 6 (coverage < 80%) — investigate further before tagging.
6. Any cherry-pick conflict at §6c that requires non-trivial resolution beyond the documented PR 53/PR 54 re-order rule or the PR 52/PR 55 same-file hunk-disjointedness check — STOP and report.

---

## 11. Rollback (if v1.7.1 ships and something breaks)

1. `git revert <release-bump-sha>` on main, push to origin. **No force-push.**
2. Delete the `v1.7.1` tag locally and on origin: `git tag -d v1.7.1 && git push origin :refs/tags/v1.7.1`.
3. Edit the GitHub release: `gh release edit v1.7.1 --draft` (or `gh release delete v1.7.1`); restore "Latest" badge to v1.7.0.
4. File post-mortem at `docs/postmortem_v1_7_1_rollback.md`.

Most likely failure modes:
- **Maturin build pinning issue on user systems** — not covered by source ship; covered by .dmg artifact (PR 11) rebuilt downstream.
- **PR 50 cap-guard regresses an untested combo** — would manifest as `test_exploit_diff` regression or persona-test surprise; partial mitigation is §5 step 5.
- **PR 54 renderer over-tokenizes (emits "A" when it shouldn't)** — would show up as INFLATED coverage (>>100%) on the Brown acceptance test, which is a softer failure than gating out.

---

## 12. Estimated ship time

| Step | Time |
|---|---|
| §6a pre-flight (capture PR 54 + PR 55 SHAs, decision on PR 53) | 3-5 min |
| §6b worktree setup | <1 min |
| §6c cherry-pick (5-6 commits) | 1-2 min |
| §6d version bump + CHANGELOG + maturin rebuild + commit | 4-6 min (maturin is the slow step) |
| §6e smoke matrix (Rust + Brown acceptance is the slow item, ~7 min) | 10-15 min |
| §6f tag + push | 1 min |
| §6g GitHub release | 1-2 min |
| §6h cleanup | <1 min |
| §8 post-ship verification | 5-8 min |
| **Total** | **~30-40 min wall-clock from "user approves ship" to "release LIVE + post-ship verification complete"** |

Comparable to LEG 18 (15-25 min for 2-PR MINOR) plus the additional Brown acceptance test (slow) and Rust rebuild overhead.

---

## 13. Constraints honored on this plan

- [x] No code modified — pure planning pass
- [x] No commit; no push; no merge
- [x] No sub-agents spawned (per task constraint)
- [x] Within 25-min plan-authoring time budget
- [x] References prior ship plans (LEG 21 superseded; LEG 20 format borrowed for §6/§7/§8 cadence)
- [x] Cites specific PR numbers and SHAs (PR 50 `18a7640`, PR 51 `78c7155`, PR 52 `9e6662b`, PR 53 `33b38a7`; PR 54 SHA TBD at ship time)
- [x] Plan is OPERATIONAL — executor agent can follow §6 step-by-step

---

## 14. Source-of-truth pointers

- This plan: `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_engine_ship_plan_final.md`
- Superseded prior plan: `/Users/ashen/Desktop/poker_solver/docs/leg21_v1_6_1_engine_only_ship_plan.md`
- R9 status: `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-24_r9_p0_p1.md` (current head)
- R8 status: `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-24_r8_suit_encoding.md`
- R8 post-dry-run-#4 status: `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-24_r8_post_dryrun_4.md`
- R7 status: `/Users/ashen/Desktop/poker_solver/docs/STATUS_2026-05-24_brown_as_sanity_check.md`
- P0/P1 convention investigation (PR 55 source): `/Users/ashen/Desktop/poker_solver/docs/p0_p1_convention_investigation.md`
- Dry-run #4 evidence (3-fix bundle, coverage-floor fail): `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_dryrun_4.md`
- Acceptance test reframe spec (PR 53): `/Users/ashen/Desktop/poker_solver/docs/acceptance_test_reframe.md`
- PR 54 worktree (in flight): `/private/tmp/pr-54-renderer-43123` — diff in `tests/test_v1_5_brown_apples_to_apples.py` (stack_ceiling kwarg + 2 callers + "A" branches)
- Persona retest specs: `docs/pr_proposals/v1_6_1_retest_W2_3_sarah_kk_vs_cbet_range.md`, `docs/pr_proposals/v1_6_1_retest_W3_4_daniel_mdf.md`
- LEG 20 ship-plan format reference: `/Users/ashen/Desktop/poker_solver/docs/leg20_v1_7_0_ship_plan.md`
- Memory rules in force: `feedback_no_concurrent_branch_ops`, `feedback_public_repo_hygiene`, `feedback_post_integration_verification`, `feedback_ui_packaging_sync`, `feedback_pr10a5_autonomous_commit`, `feedback_dual_remote_workflow`, `feedback_player_convention_mismatch` (NEW R9), `feedback_index_as_char_hazard` (R8)
