# poker-solver v1.8.3 — CLI range queries default to true Nash + Sarah W2.4 PARTIAL → PASS

**Status: DRAFT (compile-since-v1.8.2). Compiled 2026-05-28 from the
post-v1.8.2 main branch.**

**Baseline commit on `origin/main`:** `16c92e6` (v1.8.2 tag, 2026-05-28).
**Compilation tip:** `14b09b0` (PR #140, 2026-05-28).
**Release date:** TBD (user-gated; release notes are user-facing).
**Tag:** `v1.8.3` (to be created at ship time).
Final tag SHA will be set at `git tag` time.

**Hold for user review.** This is a draft anticipating the next ship. The
contents reflect what has landed on `main` after `16c92e6`. PRs currently
OPEN at compilation time (PR [#139][pr139] BR-walk caching, PR [#126][pr126]
UI True Nash default toggle, PR [#121][pr121] chained orchestrator Phase A,
PR [#122][pr122] full-tree preflop RvR Phase A) are listed in the
**"Conditional adds"** section below — they fold into v1.8.3 only if they
merge before ship.

---

## Headline

**v1.8.3 — CLI range queries default to true Nash + Sarah W2.4 (batch-solve)
PARTIAL → PASS.**

Two user-visible items land in this release:

1. **CLI true-Nash default for range queries.** `poker-solver river` and
   `poker-solver subgame` now dispatch multi-combo villain ranges through
   `solve_range_vs_range_nash` (vector-form CFR, joint imperfect-info Nash)
   by default. The prior per-combo blueprint loop is preserved behind a new
   opt-in `--legacy-blueprint` flag. Sample wall: 3-combo villain, river,
   50 iters: **~0.46 s default vs ~1.70 s legacy** (the post-PR-#114
   TerminalCache makes true Nash competitive with — and usually faster
   than — the loop, and it is mathematically correct as a joint solve
   rather than 1v1 averages). See "CLI" §1.
2. **Sarah W2.4 (batch-solve) PARTIAL → PASS.** The post-PR-#133
   verification under the new `batch-solve --backend rust` CLI surface
   completes 3/3 fixture rows in **2.01 s wall** (per-row 0.58–0.68 s),
   well inside Sarah's 5-min session gate (149× safety margin). Bottom-line
   persona counts: PASS 13 → **14**, PARTIAL 3 → **2**, BLOCKED 1, FAIL 0
   (Sarah: 1/5 PASS → 2/5 PASS). See "Persona milestones" §2.

The release also folds in the v1.8.2 post-ship audit (PR [#138][pr138];
8 checks, 6 PASS / 2 INFORMATIONAL / 0 release-blockers), the held-PR
backlog snapshot (PR [#137][pr137]), and the 2026-05-28 current-state
persona snapshot (PR [#135][pr135]).

---

## Highlights

### 1. CLI — range queries default to true Nash; `--legacy-blueprint` for opt-in fast mode (PR [#136][pr136])

**Merge SHA:** `5a6dd08`.

Refactors `_run_subgame_solve` (the shared core for the `river` and
`subgame` subcommands) to dispatch multi-combo villain ranges through
`range_aggregator.solve_range_vs_range_nash` (vector-form CFR — true joint
imperfect-info Nash) instead of the per-combo blueprint-shape loop.

**Why now.** Post-PR-#114 TerminalCache (~213× river speedup), the
true-Nash path is competitive with — often faster than — the loop, and it
is mathematically correct (joint range-vs-range solve, not per-combo 1v1
averages). The default flip is the user-visible payoff of the v1.8.2
TerminalCache work.

**Dispatch table:**

| Input | Default behavior | `--legacy-blueprint` opt-in |
|---|---|---|
| Single-combo villain range | Diagnostic fixed-hand path (`solve_hunl_postflop`, legacy `action_N` positional keys) | (no effect — single-combo never used the loop) |
| Multi-combo villain range | `solve_range_vs_range_nash` (true Nash; engine action labels `check`/`bet_75`/`fold`/...) | Per-combo blueprint loop (backward-compat opt-in) |
| Presentation modes (`--walk-tree`/`--node`/`--format=json|csv`) | Per-combo loop unconditionally (tree-walk formatters require a full `SolveResult` per villain combo) | (already routes through the loop) |

**Bench (3-combo villain `QcQh,JcJh,JcJd`, river, 50 iters):**

| Mode | Wall time |
|---|---|
| Default (true Nash) | **~0.46 s** (Rust solve ~15 ms + Python overhead) |
| `--legacy-blueprint` | **~1.70 s** |

**Test plan PASS:**

- All existing CLI tests pass: 7 `test_cli_subgame.py` + 7
  `test_cli_subcommands.py` + 7 `test_cli_walk_tree.py` (incl.
  backward-compat structural assertion).
- 9 new tests in `tests/test_cli_range_default_true_nash.py` covering
  both `river` and `subgame` paths.

**Migration impact:** existing scripts that compared against the
per-combo blueprint output will see engine action labels
(`check`/`bet_75`/`fold`/...) instead of the legacy `action_N` positional
keys. Pin the legacy behavior with `--legacy-blueprint` to retain the
pre-v1.8.3 output. See "Migration / breaking changes" below.

### 2. Persona — Sarah W2.4 PARTIAL → PASS via PR #133 batch-solve Rust backend (PR [#140][pr140])

**Merge SHA:** `14b09b0`.

PR [#135][pr135] landed the 2026-05-28 persona snapshot but did not verify
W2.4 against the new `batch-solve --backend rust` CLI surface that
PR #133 added (PR #133 itself shipped pre-v1.8.2). PR #140 amends the
snapshot with an empirical retest.

**W2.4 fixture:** 3-row river CSV (`scripts_retest/w2_4_test_spots.csv`,
iter=100) — the same fixture used to declare W2.4 PARTIAL pre-PR-#133.

**Result:** `poker-solver batch-solve --backend rust --input <fixture>`
completes **3/3 OK in 2.01 s wall** (per-row 0.58–0.68 s). Sarah's 5-min
session gate hit with **149× safety margin**.

**Reclassification:** W2.4 PARTIAL → **PASS**.

**Bottom-line persona counts (snapshot at HEAD `14b09b0`):**

| Verdict | Pre-PR-#140 | Post-PR-#140 | Delta |
|---|---|---|---|
| **PASS**    | 13 | **14** | +1 |
| **PARTIAL** |  3 | **2**  | −1 |
| **BLOCKED** |  1 | 1      | =  |
| **FAIL**    |  0 | 0      | =  |

Sarah: 1/5 PASS → **2/5 PASS** (W2.4 closed; W2.1, W2.2 remain PARTIAL;
W2.3 BLOCKED).

**Build caveat called out in the per-workflow row.** The PR #140
verification rebuilds the `_rust.so` from current source via
`maturin develop --release`. The shipped v1.8.0 `.dmg` wheel (May 23
build, pre-PR #16) hard-fails on the W2.4 fixture with
`index out of bounds: the len is 65 but the index is 70` at
`dcfr_vector.rs:651` — the asymmetric-range hand-count panic that
PR #16 already fixed at the source layer. **The next `.dmg` rebuild needs
to ship a source-current `.so` so the end-user W2.4 path mirrors the
buildable-from-source PASS state recorded here.**

Verification artifact:
`/tmp/persona_retests/w2_4_post133_rust_rebuilt.json`. PR #133's own test
suite (`tests/test_cli_batch_solve_rust.py`) also passes end-to-end
(4/4) on the rebuilt `.so`.

### 3. Persona — current-state snapshot 2026-05-28 (PR [#135][pr135])

**Merge SHA:** `e6df209`.

Empirical snapshot taken at main HEAD `261fb7e` after multiple
persona-affecting PRs landed on 2026-05-27 (PR #125 W1.5 `return_ev`,
PR #128 W4.2 amendment, PR #129 off-path annotation, PR #130 W3.5
amendment, PR #114 TerminalCache, PR #94 + PR #120 earlier retests).

**Net delta from the prior snapshot (post-PR #128 + #130):**

- PASS:    12 → **13** (+1: W1.5 via PR #125)
- PARTIAL:  4 → **3** (−1: W1.5 moved up)
- BLOCKED:  1 →  1 (=)
- FAIL:     0 →  0 (=)

**Single reclassification on 2026-05-28 (pre-PR #140):** W1.5 Marcus
push/fold sanity (76s @ 10 BB) PARTIAL → PASS via PR #125 (`return_ev=True`
keyword shipped; the Type C-NICE structural blocker is closed). Empirical
measurement:
`get_pushfold_strategy(10, 'sb_jam', '76s', return_ev=True) -> {'strategy': 1.0, 'ev_bb': -0.207}`
(0.16 s wall, well under Marcus 30s budget).

All other expected effects (PR #128 W4.2, PR #130 W3.5) were already
absorbed into the prior baseline. PR #129 off-path annotation surface
verified on `SolveResult` (8/8 tests pass); does not flip a persona
because dependent workflows were already PASS. PR #114 vector-RvR perf
gain alone is not enough to unblock W2.3 turn fixture (>20 min) — W2.3
retest skipped per task constraint (>5 min budget). PR #50 / #139
BR-walk caching is in flight (see "Conditional adds" below).

No unexpected reclassifications, no regressions.

### 4. Held PRs snapshot (PR [#137][pr137])

**Merge SHA:** `c4843d5`.

Captures a 2026-05-28 snapshot of the four major HELD PRs awaiting user
merge decision, with per-PR scope, lines/files, test coverage, hold
rationale, merge recommendation, and downstream blockers:

- PR [#121][pr121] — chained orchestrator Phase A.
- PR [#122][pr122] — full-tree preflop RvR engine (Phase A).
- PR [#126][pr126] — True Nash UI default flip.
- PR [#20][pr20]  — cross-platform CI matrix.

All four are HELD per the project memory rule that major new features
require explicit user merge approval. If any merge before v1.8.3 ships,
they roll into the "Conditional adds" section below; otherwise they
defer to v1.8.3+.

### 5. v1.8.2 post-ship audit (PR [#138][pr138])

**Merge SHA:** `d74e5f3`.

Runs the 8 post-ship verification checks against the v1.8.2 tag
(ship SHA `16c92e6`, tag object `f37db10c906...`) and records the result
in `docs/v1_8_2_post_ship_audit_2026-05-28.md`.

**Result:** 6 PASS, 2 INFORMATIONAL, 0 release-blockers.

| Check | Verdict |
|---|---|
| Tag SHA parity (origin == backup) | PASS |
| Release-body keywords + no `<TBD-...>` placeholders | PASS |
| Tagged version files (1.8.2 / 0.8.2) | PASS |
| CLI `--version` reports 1.8.2 | INFORMATIONAL (stale local editable install pointing at a feature worktree; not a release issue — module import returns 1.8.2) |
| Off-path annotation fields in `solver.py` at tag | PASS |
| No `<TBD-...>` placeholders in tagged release-notes draft | PASS |
| Excluded PRs (#121/#122/#126) absent from v1.8.0..v1.8.2 range | PASS |
| `backup/main` vs `origin/main` | INFORMATIONAL (one-commit drift from post-ship PR #135 docs persona snapshot; tags still match) |

No follow-up release-blocker discovered.

---

## Conditional adds (PRs OPEN at compilation time)

The following PRs are OPEN against `origin/main` as of compilation
(2026-05-28). **If they merge before v1.8.3 ships, the highlights and
PR list should be updated accordingly.** Otherwise they defer to
v1.8.3+ / v1.9.

### PR [#139][pr139] — BR-walk caching (W2.3 unblock candidate)

**Headref:** `perf/br-walk-terminal-cache-task50`. **Status:** OPEN.

Applies PR #114's `TerminalCache` pattern to the best-response walk in
`exploit.rs`. Pre-caches `Strength` values per terminal leaf;
`cached_terminal_utility` is a bit-exact replacement for the per-combo
`evaluate_7` calls.

**Bench numbers from PR description:**

- `cargo test -p cfr_core --lib --release`: **58 passed in 2.83 s** (was
  ~110 s pre-cache; `flat_tree_chance_enum_river_completes` alone took
  60+ s).
- Bit-identical parity test `cached_matches_uncached_terminal_value`:
  **PASSES.**
- Python diff tests: `test_exploit_diff` (5/5),
  `test_range_vs_range_rust_diff` (4/4 + 1 slow skip),
  `test_exploitative_play` (5/5) — **14 PASS / 1 skipped.**

**Why this unblocks W2.3.** Solve-phase wall-clock already dropped from
>1200 s kill → 16.6 s via PR #114 on the 8-class symmetric turn fixture,
but **best-response walk** (exploitability computation) was the
remaining wall. PR #139 caches the BR-walk terminals so the remaining
wall is removed. If merged: W2.3 BLOCKED → PASS expected (subject to
empirical retest at production scale per memory rule
`feedback_post_ship_persona_retest.md`).

**If merged before ship:** elevate to "Engine perf §1", move W2.3 to
"Personas unblocked", drop W2.3 from "Known issues remaining".

### PR [#126][pr126] — UI True Nash RvR mode toggle (default flipped)

**Headref:** `feat/ui-true-nash-rvr-toggle-task61-v2`. **Status:** OPEN
(HELD per project memory rule; major UI feature).

Adds a True-Nash-vs-blueprint solver-mode selector to the GUI
range-vs-range run panel. **Default is `solver_mode = "true_nash"`**
(flipped from `"blueprint"` on 2026-05-27 per the post-PR-#114 bench
data). Blueprint remains opt-in via the inverted-label checkbox ("Use
Pluribus blueprint (legacy, faster on tiny river)") for the narrow case
where it still wins on tiny river spots.

**Empirical bench (3-class hero, 3-class villain, K72r board):**

- Turn: True Nash **~27× faster** than blueprint.
- Flop: blueprint impractical (>27 min CPU); true-Nash feasible.
- River: post-PR-#114 True Nash is **~213× faster** (interactive).

**If merged before ship:** add a UI-side §2 mirror of the PR #136 CLI
default flip. The user-visible framing becomes "CLI **and** GUI default
to true Nash for range queries", which is a cleaner story than "CLI
only".

### PR [#121][pr121] / [#122][pr122] — chained orchestrator + full-tree preflop RvR (Phase A)

**Status:** OPEN (HELD per project memory rule; major new features).

If either lands before v1.8.3, W2.1 (Sarah preflop chart) moves from
PARTIAL to a re-evaluable state. Both are HELD pending user merge
approval; recommend deferring to v1.9 unless the user explicitly
elevates.

### Persona sanity-check audit (in flight)

A deeper persona sanity-check audit (separate worktree
`audit-persona-pass-sanity-check`) was spawned around v1.8.2 compilation
time. If it lands before ship, fold a "Quality §6 — persona sanity
audit" subsection summarizing the verdict + any reclassifications.

---

## Known issues remaining

The following are **NOT** resolved in v1.8.3 and remain open for future
work:

### A83 deep-cap Brown apples-to-apples residual (unchanged from v1.8.0)

Post-purge v1.5 Brown apples-to-apples PASSES on both K72 + A83 spots
under the reframed 4-layer SANITY gate; strict-per-cell |Δ| values
(K72 0.852, A83 0.907) reflect Nash multiplicity at deep-cap
indifference manifolds. The EV(action) invariance gauntlet (PR #98,
shipped in v1.8.2) is the canonical sanity check for the residual. No
delta in v1.8.3.

### Persona table — PARTIAL / BLOCKED rows remaining

- **W2.1 (Sarah preflop chart)** — `solve_hunl_preflop` raises
  `ValueError`: requires `initial_hole_cards` (subgame mode only).
  Full-tree preflop "intractable without hand-class abstraction —
  reserved for post-v1 follow-up." The Phase A engine work for this is
  on PR [#122][pr122] (full-tree preflop RvR engine) and PR [#121][pr121]
  (chained orchestrator), both HELD per project memory rule (see
  "Conditional adds" above).
- **W2.2 (Sarah `Range.diff` per-combo frequencies)** — `Range.diff()`
  set-membership returns 56 combos (works); no per-combo frequency
  methods. **B10** (Range fractional refactor) blocker, tracked
  separately.
- **W2.3 (Sarah deep-stack turn RvR)** — solve-phase >72× faster post
  PR-#114 (16.6 s on the 8-class symmetric turn fixture, down from
  >1200 s kill), but best-response walk (exploitability compute) is a
  separate perf wall. **Unblock candidate: PR [#139][pr139] (OPEN at
  compilation; see "Conditional adds" above).** If PR #139 merges
  before ship, W2.3 moves to "Personas unblocked".

### Engine / build carry-overs (unchanged from v1.8.0)

- **Apple Silicon arch hazard** (dev-environment, pre-existing) —
  pyenv's x86_64 Python can't load the arm64 `_rust.so`; use
  `.venv/bin/python`. See `CONTRIBUTING.md`.
- **`poker-solver` PATH shim quirk** (dev-environment, pre-existing) —
  if the shim fails with `ModuleNotFoundError`, use
  `./.venv/bin/poker-solver ...` or `python -m poker_solver.cli ...`.
- **`Range` fractional frequencies** — spec landed in PR #36; full
  implementation tracked separately (B10).
- **`.app` / `.dmg` notarization** — v1.8.3 `.dmg` is still ad-hoc-signed
  (same as v1.6.0 / v1.8.0 / v1.8.2). Apple Developer enrollment is a
  user carry-item.
- **`.dmg` `.so` source-currency** — the v1.8.0 shipped `.dmg`'s `.so`
  is pre-PR-#16 and panics on asymmetric W2.4 ranges (see PR #140
  caveat). **A v1.8.3 `.dmg` rebuild from source-current state is
  required** to ensure the end-user W2.4 path mirrors the
  buildable-from-source PASS recorded in PR #140.

---

## Migration / breaking changes

### CLI range queries now default to true Nash

**Pre-v1.8.3:** `poker-solver river ...` and `poker-solver subgame ...`
with a multi-combo villain range dispatched through the per-combo
blueprint loop. Output used legacy `action_N` positional keys.

**v1.8.3:** the default now dispatches through
`solve_range_vs_range_nash` (vector-form CFR — true joint
imperfect-info Nash). Output uses engine action labels
(`check`/`bet_75`/`fold`/...).

**Restore the legacy behavior** with the new `--legacy-blueprint` flag:

```bash
poker-solver river --board "As 7c 2d Kh 5s" --hero AhKh \
    --villain-range "QQ,JJ,AKs" --iters 200 \
    --legacy-blueprint
```

The default is recommended; `--legacy-blueprint` is provided for:

- backward compatibility with pre-2026-05-28 scripts that compare exact
  output strings.
- fast 13×13 approximate displays on dry boards where the per-combo
  loop still wins on raw wall time.

Presentation modes (`--walk-tree`, `--node`, `--format=json|csv`)
unconditionally route through the per-combo loop regardless of the
flag, because tree-walk formatters require a full `SolveResult` per
villain combo.

### Python API additions

None. v1.8.3 is CLI + persona-doc only.

### CLI surface additions (additive)

- `poker-solver river --legacy-blueprint` (new flag; default omitted →
  true Nash; legacy invocation with the flag → blueprint loop).
- `poker-solver subgame --legacy-blueprint` (same).

No flags removed. No legacy invocations broken (provided callers add
`--legacy-blueprint` to retain pre-v1.8.3 output shape).

---

## Upgrade path

### From v1.8.2 source install

```bash
git pull
pip install -e .
maturin develop --release
```

No Rust ABI change in v1.8.3 (PR #136 is Python-only), so a fresh
`maturin develop --release` is **not strictly required** unless a
conditional add (PR #139) lands; rebuilding is cheap and recommended
for hygiene.

### From the v1.8.2 `.dmg`

1. Delete the existing `Poker Solver.app` bundle (Finder → drag to
   Trash).
2. Download the v1.8.3 `.dmg` from the GitHub Release page (when
   published).
3. Drag-install as usual.

**Important:** the v1.8.3 `.dmg` rebuild must ship a source-current
`.so` to close the W2.4 end-user path (see "Known issues" / PR #140
build caveat).

---

## Compatibility

- **CFR algorithm:** bit-identical to v1.8.2 on Kuhn / Leduc / HUNL
  postflop subgame (no convention change). Range-vs-range default path
  changes from per-combo loop to joint Nash — strategy probabilities
  for multi-combo ranges will **not** match v1.8.2 output bit-for-bit;
  use `--legacy-blueprint` to pin the prior behavior.
- **Public Python API:** unchanged. `range_aggregator.solve_range_vs_range`
  (blueprint) and `range_aggregator.solve_range_vs_range_nash` (true
  Nash) are both still exported; PR #136 only changes CLI default
  dispatch.
- **Min Python:** unchanged from v1.8.2.
- **Min Rust toolchain:** stable, unchanged from v1.8.2.
- **`crates/cfr_core` version bump:** 0.8.2 → 0.8.3.
- **`pyproject.toml [project] version`:** 1.8.2 → 1.8.3.
- **`poker_solver/__init__.py __version__`:** 1.8.2 → 1.8.3.

---

## Verification

Run the new tests yourself:

```bash
# CLI true-Nash default + --legacy-blueprint opt-in
pytest tests/test_cli_range_default_true_nash.py -v

# Existing CLI surface (regression guard)
pytest tests/test_cli_subgame.py tests/test_cli_walk_tree.py \
       tests/test_cli_subcommands.py -v

# W2.4 batch-solve Rust backend (verification fixture)
pytest tests/test_cli_batch_solve_rust.py -v
```

Sample 3-combo true-Nash vs `--legacy-blueprint` bench:

```bash
# Default (true Nash)
time poker-solver river \
    --board "As 7c 2d Kh 5s" --hero AhKh \
    --villain-range "QcQh,JcJh,JcJd" --iters 50

# Legacy blueprint loop
time poker-solver river \
    --board "As 7c 2d Kh 5s" --hero AhKh \
    --villain-range "QcQh,JcJh,JcJd" --iters 50 \
    --legacy-blueprint
```

---

## Full PR list

All PRs that ship in v1.8.3, in merge order since v1.8.2 (`16c92e6`).
Compiled 2026-05-28 from main HEAD `14b09b0`.

**CLI surface (load-bearing user-visible):**

- [#136][pr136] `5a6dd08` — feat(cli): default range queries to true
  Nash; `--legacy-blueprint` for opt-in fast mode.

**Persona milestones:**

- [#140][pr140] `14b09b0` — docs(persona): verify W2.4 post-PR-#133
  (batch-solve Rust backend) — PARTIAL → PASS.
- [#135][pr135] `e6df209` — docs(persona): current-state snapshot
  2026-05-28 (post all 2026-05-27 reclassifications).

**Quality / housekeeping:**

- [#138][pr138] `d74e5f3` — docs: v1.8.2 post-ship audit (8 checks,
  6 PASS / 2 INFORMATIONAL / 0 release-blockers).
- [#137][pr137] `c4843d5` — docs: summary of held PRs awaiting user
  merge decision.

**Conditional adds (OPEN at compilation; fold in if merged before ship):**

- [#139][pr139] `<TBD-SHA>` — perf: cache terminal-leaf strengths in
  best-response walk (W2.3 unblock, #50). Bench: 58 cargo tests **110 s
  → 2.83 s**.
- [#126][pr126] `<TBD-SHA>` — feat(ui): True Nash RvR mode toggle
  (post-PR-#114 perf unlock, #61). Default flipped to `"true_nash"`.
- [#121][pr121] `<TBD-SHA>` — feat: preflop chained orchestrator
  Phase A (#31).
- [#122][pr122] `<TBD-SHA>` — feat: full-tree preflop RvR engine
  (#32 Phase A).

If any of these flip to MERGED before v1.8.3 ships, the user decides
whether to roll them into this release or defer to v1.9 / v1.8.4.

---

## Acknowledgments

This release closes:

- The CLI true-Nash default flip blocked by the pre-PR-#114 vector-RvR
  perf wall (PR #136). The v1.8.2 TerminalCache is what made this
  default change competitive on wall time.
- The Sarah W2.4 batch-solve PARTIAL (PR #140), gated on the
  PR #133 `batch-solve --backend rust` CLI surface.
- The v1.8.2 post-ship audit backlog (PR #138).
- The held-PR backlog snapshot for user merge decisions (PR #137).

Thanks to the persona-test framework (Sarah W2.4) for empirically
anchoring the CLI default flip's perf claim, and to the post-PR-#114
TerminalCache work (v1.8.2) for unlocking the true-Nash default.

---

## What's next

- **v1.8.4 candidates** (if held PRs land separately): PR #139 BR-walk
  caching (W2.3 unblock); PR #126 UI True Nash default flip.
- **v1.9 candidate:** full-tree preflop solver (chained orchestrator
  PR #121 + RvR engine PR #122 Phase A → Phase B caching + parallel),
  unblocks W2.1 (Sarah preflop chart).
- **v2.0:** EMD bucketing for flop interactive viability (the W2.3 /
  W3.4 / W2.1 / W2.4 lever once best-response caching lands).

---

[pr20]: https://github.com/amaster97/poker_solver/pull/20
[pr121]: https://github.com/amaster97/poker_solver/pull/121
[pr122]: https://github.com/amaster97/poker_solver/pull/122
[pr126]: https://github.com/amaster97/poker_solver/pull/126
[pr135]: https://github.com/amaster97/poker_solver/pull/135
[pr136]: https://github.com/amaster97/poker_solver/pull/136
[pr137]: https://github.com/amaster97/poker_solver/pull/137
[pr138]: https://github.com/amaster97/poker_solver/pull/138
[pr139]: https://github.com/amaster97/poker_solver/pull/139
[pr140]: https://github.com/amaster97/poker_solver/pull/140
