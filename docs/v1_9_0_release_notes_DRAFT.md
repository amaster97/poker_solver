# poker-solver v1.9.0 — Premium-A shipping milestone: 27 preflop blueprints + 169-class engine + realtime postflop subgame (major engine + UX release)

**Status: DRAFT (compile-since-v1.8.3). Compiled 2026-05-28 from the
post-v1.8.3 main branch tip. Audit pending; auto-merge OK after
audit-clear.**

**Baseline commit on `origin/main`:** `8a358b5` (v1.8.3 tag context).
**Compilation tip:** `f0fc879` (PR [#184][pr184], 2026-05-28 — persona
status snapshot 17/0/0/0 post-PR-170 W2.3 strict-PASS).
**Release date:** TBD (user-gated; release notes are user-facing).
**Tag:** `v1.9.0` (to be created at ship time).
Final tag SHA will be set at `git tag` time.

---

## Headline

**v1.9.0 — Premium-A ships: instant 27-cell preflop blueprint lookup +
true 169-class engine (178-448× preflop solve speedup) + realtime
postflop subgame solving (turn + river) + W2.3 strict-PASS via
vector-form BR walk + persona table 17/0/0/0.**

This is the **Premium-A shipping milestone**. Three user-visible
capabilities land together:

1. **Instant preflop chart lookup (27 precomputed blueprints).** A
   bundled asset of 27 precomputed 169-class Nash-equilibrium preflop
   strategy shards (9 stack depths × 3 ante configs, ~21 MB
   compressed) gives sub-millisecond preflop-decision lookup at
   runtime. Stack-depth interpolation handles non-anchor depths
   (e.g. 67 BB) without a fresh solve. Doc:
   `docs/blueprint_user_guide.md`, `docs/blueprint_developer_guide.md`.

2. **Realtime postflop subgame solving (turn + river).** Postflop
   subgames anchored on the blueprint solve in seconds-to-~30s for
   turn and river. The blueprint range is expanded 169 → 1326 per
   street and the postflop is live-solved per combo via the existing
   vector-form CFR backend. **Flop subgame ships as
   blueprint-only** in v1.9.0 (no live refinement); the live-solve
   flop path OOMs under the current implementation. v1.10 addresses
   this (task #70 — see "Known limits").

3. **W2.3 Sarah deep-stack turn RvR — PARTIAL → strict-PASS.** The
   long-standing W2.3 BLOCKED/PARTIAL row reached strict-PASS via
   PR [#170][pr170] (vector-form BR walk), dropping the W2.3
   fixture wall from >5 minutes to **~25 s** — well inside Sarah's
   10-minute gate. Persona table: **17/0/0/0** (was 14/2/1/0 at
   v1.8.x).

The release also folds in the CS-bug fix (PR [#165][pr165] —
`State::initial` honors `config.initial_contributions`), the B10
per-combo frequency feature train (PRs [#149][pr149], [#154][pr154],
[#158][pr158], [#160][pr160]) which closed Sarah W2.2, and the
DCFR optimization ledger (`docs/rust_optimization_ledger.md`)
documenting empirical speedups for PRs [#114][pr114], [#139][pr139],
[#150][pr150], [#157][pr157], [#162][pr162], [#170][pr170], and
[#171][pr171].

---

## Major features

### 1. Preflop blueprint asset bundle (27 shards) — PR [#171][pr171] + asset commit `1783bef`

**True 169-class engine (PR [#171][pr171], merge SHA `a7a23ff`)** is
the unblock that made the blueprint compute pipeline practical:
internal strategy storage and DCFR update now operate directly on
the 169-class abstraction (not on the underlying 1326 combos with
a post-hoc collapse). The 169-class abstraction is **lossless for
preflop** modulo numerical noise (hybrid 1326→169 output vs True
Path B 169-class output: L1 = 0.0000 across 6,084 cells at 15 BB /
1000 iters).

**Asset bundle (asset commit `1783bef`):**

| Dimension     | Coverage                                              |
|---------------|-------------------------------------------------------|
| Stack depths  | 20, 30, 40, 60, 80, 100, 150, 175, 200 BB             |
| Ante configs  | `none` (0 BB), `half` (0.5 BB), `full` (1.0 BB)       |
| Hand classes  | All 169 Pio-style preflop classes per cell            |
| Action menu   | `fold`, `call`, open 2-5 BB, 3/4/5-bet ladder, all-in |
| Raise cap     | 4 raises per preflop street                           |
| Iterations    | 25,000 DCFR per cell (Brown & Sandholm 2019 hyperparams) |
| Total size    | ~21 MB compressed (gzipped JSON shards + manifest)    |
| Shard count   | 27 (= 9 × 3)                                          |

Each shard ships with a per-shard sha256 in `assets/blueprints/manifest.json`.

**Compute wall (M-series silicon):** 38.5 minutes for all 27 shards
end-to-end (compared to a pre-PR-#171 projection of 17-40 hours on
the hybrid path). See `docs/rust_optimization_ledger.md` §7 for the
empirical speedup table.

User guide: `docs/blueprint_user_guide.md`.
Developer guide: `docs/blueprint_developer_guide.md`.

### 2. Blueprint loader API — PR [#174][pr174] (merge SHA `509f07d`)

New `poker_solver.blueprint` module:

- `BlueprintLoader.from_dir(path)` — lazy-load constructor; reads
  `manifest.json` and validates per-shard sha256 on first access.
- `BlueprintLoader.lookup(stack_bb, ante, hand_class, action_history)`
  — direct strategy lookup. **~865k lookups/sec** measured on M4 Pro
  (PR body benchmark).
- `BlueprintLoader.actions(stack_bb, ante)` — action-menu introspection
  for the cell.
- `BlueprintLoader.available_depths()` — anchor depths shipped in the
  bundle (returns `[20, 30, 40, 60, 80, 100, 150, 175, 200]`).
- Lazy shard load with in-process cache (each shard parsed at most
  once per `BlueprintLoader` instance).

The loader is the supported public API; downstream consumers
(GUI, CLI, postflop subgame solver) all route through it.

### 3. Stack-depth interpolation — PR [#173][pr173] (merge SHA `cb177c7`)

`poker_solver.blueprint_interp.interpolate_strategy(depth_bb, ...)`
returns a strategy for any depth in `[20, 200]` BB by convex linear
blend of the two bracketing anchor strategies. For a depth between
two anchors `(d_lo, d_hi)`, the returned strategy is
`(1 - t) * strategy_lo + t * strategy_hi` with `t = (depth - d_lo) /
(d_hi - d_lo)`. Result stays on the probability simplex (both inputs
are probability vectors, `t ∈ [0, 1]`); the function normalizes to
absorb any floating-point drift. A `method="nearest"` alternative
snaps to the nearest anchor.

### 4. Postflop subgame wiring + range expansion — PR [#177][pr177] (merge SHA `18b9bcf`)

`poker_solver.blueprint_subgame.solve_postflop_from_blueprint(...)`
chains the blueprint preflop history into a postflop live-solve:

1. Look up the preflop strategy at each player's reach-vector hand
   class via the blueprint loader.
2. Expand the 169-class blueprint reach into a 1326-combo reach by
   per-combo weighting (suit-symmetric expansion within each class).
3. Live-solve the postflop street (turn or river) with the expanded
   1326-combo reaches as priors via the existing
   `solve_range_vs_range_nash` vector-form CFR backend.

The expansion step is what makes the blueprint-anchored postflop
work: 169-class is lossless for preflop strategy, but postflop
needs per-combo blocker bookkeeping, so we must restore the 1326
representation at the preflop/postflop boundary.

A small follow-up fix (PR [#182][pr182], merge SHA `2aedb4b`)
normalizes `b`/`r` token equivalence at the preflop boundary so
blueprint histories using either notation route to the same shard
entry.

### 5. Top-level solver router — PR [#181][pr181] (merge SHA `03842b0`)

`poker_solver.solver_router.SolverRouter` is the v1.9.0
front-door for "solve this request, whatever street/depth/range it
is." Given a `SolveRequest`, the router picks one of four backends:

| Backend | When chosen |
|---|---|
| `lookup` | Preflop, anchor depth (∈ shipped 9), anchor ante (∈ shipped 3), blueprint hit on the action history |
| `interp` | Preflop, non-anchor depth (20-200 BB), anchor ante, blueprint hit on both bracket depths |
| `live` | Preflop with non-standard ante, depth outside the bundle envelope, or an action history not in the blueprint |
| `postflop-subgame` | Postflop (turn / river); chains via `solve_postflop_from_blueprint` (see §4) |

Production callers do not need to dispatch by hand; the router
encapsulates the decision per-request. The four backend strings are
also exposed on the `SolveResult` (`result.backend`) for
introspection.

### 6. UI integration: blueprint badges on chart + chained tab — PR [#178][pr178] (merge SHA `5df601b`)

GUI wiring:

- The **13×13 chart widget** displays a "blueprint" vs "live"
  source badge in the cell tooltip. When the chart depth + ante
  align with a shipped shard, the cells are instant lookups from the
  blueprint; off-anchor depths show "interpolated" badging and call
  through to the interpolation path; out-of-envelope cells show
  "live" and trigger a fresh solve.

- The **chained tab** (postflop subgame UI) shows the blueprint
  preflop range source per player (blueprint / interpolated / live),
  and surfaces the active postflop backend (turn live-solve vs flop
  blueprint-only) at the top of the result panel.

Live flop subgame from the chained tab is **deferred to v1.10**
(see "Known limits" below — the live flop path OOMs under the
current implementation; v1.10's task #70 addresses this).

### 7. Vector-form BR walk + W2.3 strict-PASS — PR [#170][pr170] (merge SHA `188489b`) + PR [#184][pr184] (`f0fc879`)

The vector-form BR walk applies PR #114's vector-form pattern
(originally for the forward walk) to the **best-response walk** in
`exploit.rs`. Instead of looping per combo and walking the tree,
the walk vectorizes across the combo dimension: at each tree node,
one batched op operates on the full combo vector.

**Bench result (W2.3 fixture):** per-combo 202.43 s → vector
**32.30 s** (=6.27×). On the 8-class W2.3 retest fixture used to
gate the strict-PASS reclassification, the wall is **~25.18 s** —
inside Sarah's 600 s (10-min) gate by a factor of ~24×.

**Dual-path** during transition: `BrWalkMode::PerCombo` (canonical
reference, unchanged) and `BrWalkMode::Vector` (opt-in). 10 diff
tests in `exploit::tests::vector_matches_per_combo_*` confirm
bit-identical agreement (1e-12 EV / 1e-9 exploitability) across
fixture matrix (Kuhn, Leduc, 8-class river, W2.3 turn, mixed
strategies).

PR [#184][pr184] (merge SHA `f0fc879`) records the persona
reclassification: **W2.3 PARTIAL → strict-PASS**, persona table
**17/0/0/0**.

### 8. B10 per-combo frequency feature train — PRs [#149][pr149], [#154][pr154], [#158][pr158], [#160][pr160]

Sarah W2.2 (`Range.diff` per-combo frequencies) was PARTIAL since
v1.7.x because `Range` had set-membership semantics but no
per-combo weight API. The B10 train added it:

- **PR [#149][pr149]** (`40ac87a`) — Phase A: `Range` per-combo
  fractional weights. `Range` now stores a `dict[Combo, float]`
  internally; `range["AKs"] = 0.6` is supported.
- **PR [#154][pr154]** (`11e3f01`) — Phase B: aggregator + solver
  weight propagation. The vector-form CFR backend respects per-combo
  weights in the prior reach distribution.
- **PR [#158][pr158]** (`1839ee1`) — Phase C: per-combo intensity
  editor in the GUI range builder.
- **PR [#160][pr160]** (`a1c1546`) — Phase D: W2.2 `Range.diff`
  empirical verification + persona reclassification.

**W2.2: PARTIAL → PASS** via this train, captured in the persona
snapshot at `docs/persona_status_2026-05-28-late.md`.

### 9. CS-bug fix: preflop `State::initial` honors `config.initial_contributions` — PR [#165][pr165] (merge SHA `43ed53e`)

A long-standing preflop engine bug where `State::initial` (the entry
point for fresh preflop subgames) failed to read
`config.initial_contributions` correctly — instead always starting
from `(0, 0)` contributions even when the config declared a
non-trivial ante or already-posted blind. This caused subtle
preflop-RvR strategy drift on configs with `initial_contributions`
≠ `(0.5, 1.0)` (the small-blind / big-blind default).

PR [#165][pr165] tightens `State::initial` to read
`config.initial_contributions` directly. Downstream impact:

- Preflop solves with non-default `initial_contributions` (e.g. ante
  configs, straddle scenarios) now produce strategies consistent
  with the declared chip state.
- The default `(0.5, 1.0)` path is **unchanged** at the bit level
  (the default values were already correct under the old code path).
- The blueprint compute pipeline (PR [#171][pr171], §1 above) reads
  the corrected `State::initial` — the shipped 27 blueprints already
  reflect the fix.

Scope investigation: `docs/preflop_cs_bug_scope_audit.md` (per
PR #161, `63264dd`) confirmed the bug was preflop-only; postflop
subgame paths construct `State` differently and were never affected.

---

## Performance improvements (Rust optimization ledger)

The `docs/rust_optimization_ledger.md` (committed in `92684b3` /
`07095fc`) records empirical speedups for each major Rust core
optimization landed in the v1.8 → v1.9 train. Full details in the
ledger; headline numbers:

| PR | Optimization | Speedup | Workload |
|---|---|---|---|
| [#114][pr114] | Vector-form forward walk + TerminalCache | **213×** | River RvR, 1326-combo |
| [#139][pr139] | BR-walk terminal-leaf cache | ~2× standalone | River + W2.3 unblock from kill |
| [#150][pr150] | Board-isomorphism cache | ~3-5× on multi-board batches | 1755 iso-distinct / 22100 total |
| [#157][pr157] | Opp-major layout + AXPY interchange | **6.5× wall / 10.4× kernel** | Full-tree preflop RvR |
| [#162][pr162] | BR-walk non-terminal cache + fused walk | ~2.5× | River chance-enum |
| [#170][pr170] | Vector-form BR walk | **6.27×** | W2.3 turn fixture |
| [#171][pr171] | **True 169-class abstraction engine** | **178× / 406× / 448×** | Preflop solve at 15 / 40 / 100 BB |

**Compounding:** for the "generate Premium-A 27 preflop blueprints at
25k iters" workload, the cumulative speedup over vanilla CFR (1326
combo, unoptimized) is **~80,000×** (weeks → 38.5 minutes on
M-series). See ledger §"Compounding analysis".

---

## Known limitations — disclosed honestly

These are **NOT** resolved in v1.9.0 and remain open for future
work. The release ships with them documented.

### Live flop subgame solve OOMs (deferred to v1.10)

v1.9.0 ships with **flop = blueprint-only** (no live refinement).
The live flop subgame path under the current implementation OOMs at
~2.3 GB RSS within 5 minutes wall on a representative flop fixture
(J7o A♦8♥9♦, 40 BB, 169-class). Root cause is allocator pressure in
the recursive `traverse()` in `crates/cfr_core/src/dcfr_vector.rs`
(four-to-six `Vec<f64>` allocated per node visit, totaling ~10-20 GB
transient allocation per iteration) combined with chance-tree
explosion at flop depth (~5000-30000 decision nodes for typical
raise-cap=3 + 2-bet-size action menus).

**Live turn and river work fine.** Turn live-solve completes in
~5-60 s depending on top_k; river in <1 s for typical loads.

**v1.10 task #70 addresses this.** The research plan is documented
at `docs/v1_10_postflop_optimization_plan.md`; the implementation
order is (a) thread-local arena pool, (b) vector-form turn forward
walk, (c) vector-form flop forward walk, (d) opt-in rayon
multi-threading across turn-card chance branches. Target: **flop
top_k=169 in <120 s wall, RSS ≤ 1 GB** (vs current OOM).

### `top_k_per_side` is a speed knob, not a correctness flag

The `top_k_per_side` parameter on
`solve_postflop_from_blueprint(...)` truncates each player's range
to the top-K hand classes by reach mass before live-solving the
postflop. **Production default is no filter** (full 169-class →
1326-combo expansion). Custom workloads may set `top_k_per_side` to
a smaller value (4 / 15 / 50) to trade quality for wall time on
flop / large-tree spots — see
`docs/v1_10_postflop_optimization_plan.md` §5.1 for the perf
matrix.

Setting `top_k_per_side` below 169 introduces a strategic loss vs
the full 169-class solve; it is **not** a Nash-preserving
abstraction. Use only when wall time is the dominant constraint.

### "Realtime postflop subgame solving" claim — precise scope

The "realtime postflop subgame solving" capability in v1.9.0 is
**turn + river only**. The full flop live-solve is v1.10 (above).
Marketing / FAQ / user-facing surfaces should cite "realtime turn
+ river" and qualify flop as "blueprint-only in v1.9.0; live flop
in v1.10."

### Carry-overs from v1.8.x

The following pre-existing known issues carry into v1.9.0
unchanged:

- **A83 deep-cap Brown apples-to-apples residual (Nash multiplicity).**
  Post-purge v1.5 Brown apples-to-apples PASSES on both K72 + A83
  spots under the reframed 4-layer SANITY gate; strict-per-cell |Δ|
  values (K72 0.852, A83 0.907) reflect Nash multiplicity at deep-cap
  indifference manifolds, not a bug.
- **Apple Silicon arch hazard** (dev-environment) — pyenv's x86_64
  Python can't load the arm64 `_rust.so`; use `.venv/bin/python`.
  See `CONTRIBUTING.md`.
- **`poker-solver` PATH shim quirk** (dev-environment) — if the shim
  fails with `ModuleNotFoundError`, use `./.venv/bin/poker-solver
  ...` or `python -m poker_solver.cli ...`.
- **`.app` / `.dmg` notarization** — v1.9.0 `.dmg` is still
  ad-hoc-signed (same as v1.6.0 / v1.8.x). Apple Developer
  enrollment is a user carry-item.

---

## Migration / upgrade notes

### Public API additions (additive)

- **`poker_solver.blueprint.BlueprintLoader`** — new module + class.
  Methods: `from_dir`, `lookup`, `actions`, `available_depths`.
- **`poker_solver.blueprint_interp.interpolate_strategy`** — new
  module + function. Accepts `method="convex"` (default) or
  `method="nearest"`.
- **`poker_solver.blueprint_subgame.solve_postflop_from_blueprint`**
  — new module + function. Optional `top_k_per_side` parameter
  (default: no truncation).
- **`poker_solver.solver_router.SolverRouter`** — new module + class.
  `route(request)` returns a `SolveResult` with a `backend` field
  (`"lookup"` / `"interp"` / `"live"` / `"postflop-subgame"`).
- **`SolveResult.backend`** — new field on the existing
  `SolveResult` dataclass exposing which path produced the result.
  Existing callers that don't read `backend` are unaffected.

### CFR engine: bit-identical to v1.8.3 on non-blueprint paths

- **Bit-identity:** v1.9.0's per-combo CFR path (postflop subgame,
  range-vs-range Nash on river / turn, etc.) is bit-identical to
  v1.8.3 modulo PR [#165][pr165] (`State::initial` correctly reads
  `initial_contributions`). Configs using the default
  `initial_contributions = (0.5, 1.0)` see no per-combo strategy
  drift; configs with non-default `initial_contributions` (custom
  antes, straddle setups) will see a corrected output relative to
  v1.8.3.
- **169-class engine path:** new in v1.9.0 (PR [#171][pr171]). The
  blueprint generation pipeline uses this. The 169-class output is
  lossless vs the 1326-combo path for preflop within numerical
  noise (L1 = 0.0000 across 6,084 cells at 15 BB / 1000 iters).
- **Vector-form BR walk (PR [#170][pr170]):** opt-in via
  `BrWalkMode::Vector` parameter. Default remains `PerCombo`
  (canonical). Both paths produce bit-identical EV (1e-12) and
  exploitability (1e-9) across the 10-fixture diff matrix.

### Version bumps

- `crates/cfr_core` version: `0.8.3 → 0.9.0`.
- `pyproject.toml [project] version`: `1.8.3 → 1.9.0`.
- `poker_solver/__init__.py __version__`: `1.8.3 → 1.9.0`.

### Asset bundle (new in v1.9.0)

- `assets/blueprints/` — 27 gzipped JSON shards + `manifest.json`,
  ~21 MB compressed total. **Required** for blueprint lookup /
  interpolation / postflop-subgame paths. The .dmg ships the
  bundle; source installs pick it up from `git pull`.

### From v1.8.3 source install

```bash
git pull
git lfs pull   # if blueprint shards are LFS-tracked in your clone
pip install -e .
maturin develop --release
```

`maturin develop --release` is **required** because v1.9.0 includes
new Rust engine surface (PR [#171][pr171] 169-class engine,
PR [#170][pr170] vector-form BR walk). A pure `pip install -e .`
will not rebuild the `_rust.so`.

### From the v1.8.x `.dmg`

1. Delete the existing `Poker Solver.app` bundle (Finder → drag to
   Trash).
2. Download the v1.9.0 `.dmg` from the GitHub Release page (when
   published).
3. Drag-install as usual. The 27 blueprint shards (~21 MB) are
   bundled inside the `.app`.

---

## Verification

Run the new tests yourself:

```bash
# 169-class engine diff vs hybrid (1326-combo)
pytest tests/test_true_path_b_diff.py -v

# Blueprint loader + interpolation + postflop subgame wiring
pytest tests/test_blueprint_loader.py \
       tests/test_blueprint_interp.py \
       tests/test_blueprint_subgame.py -v

# Top-level solver router
pytest tests/test_solver_router.py -v

# Vector-form BR walk bit-identity (10-fixture diff matrix)
cargo test -p cfr_core --release vector_matches_per_combo
```

Sample blueprint lookup:

```python
from poker_solver.blueprint import BlueprintLoader

loader = BlueprintLoader.from_dir("assets/blueprints/")
strategy = loader.lookup(
    stack_bb=100, ante="none",
    hand_class="AKs", action_history="",  # root (SB to act)
)
print(strategy)  # {"fold": 0.0, "call": 0.05, "open_2": 0.0, ..., "all_in": 0.0}
```

Sample postflop subgame from blueprint:

```python
from poker_solver.blueprint_subgame import solve_postflop_from_blueprint

result = solve_postflop_from_blueprint(
    stack_bb=100, ante="none",
    preflop_history="r3-c",   # SB raises to 3 BB, BB calls
    board="As 7c 2d",         # flop
    street="turn",
    turn_card="Kh",
    iterations=200,
)
print(result.backend)  # "postflop-subgame"
```

---

## Full PR list

All PRs that ship in v1.9.0, in merge order since v1.8.3 tag context.
Compiled 2026-05-28; tip `f0fc879`.

**Premium-A blueprint feature train (PR #68 epic):**

- [#171][pr171] `a7a23ff` — `feat(engine): true 169-class abstraction mode (Premium-A Phase 1.5 unblock, #68)`
- [#173][pr173] `cb177c7` — `feat(blueprint): stack-depth interpolation module (Phase 3, #68)`
- [#174][pr174] `509f07d` — `feat(blueprint): loader API + manifest discovery + lazy load (Phase 2, #68)`
- [#177][pr177] `18b9bcf` — `feat(blueprint): postflop subgame wiring + range expansion (Phase 4, #68)`
- [#178][pr178] `5df601b` — `feat(ui): wire blueprint into chart widget + chained tab (Phase 6, #68)`
- [#181][pr181] `03842b0` — `feat(blueprint): top-level solver router (lookup / interp / live / postflop) (Phase 5, #68)`
- [#182][pr182] `2aedb4b` — `fix(blueprint_subgame): normalize b/r token equivalence at preflop boundary`
- Asset commit `1783bef` — `chore(blueprints): ship 27 preflop blueprint shards (21 MB) + manifest`

**Engine / perf:**

- [#165][pr165] `43ed53e` — `fix(engine): preflop State::initial honors config.initial_contributions (#67)`
- [#170][pr170] `188489b` — `feat(engine): vector-form BR walk (W2.3 strict-PASS, opt-in)`

**B10 per-combo frequency train (PR #60 epic):**

- [#149][pr149] `40ac87a` — `feat(range): per-combo fractional weights (B10 Phase A core, #60)`
- [#154][pr154] `11e3f01` — `feat(range): aggregator + solver weight propagation (B10 Phase B, #60)`
- [#158][pr158] `1839ee1` — `feat(ui): per-combo intensity editor (B10 Phase C, #60)`
- [#160][pr160] `a1c1546` — `feat(persona): W2.2 Sarah Range.diff per-combo verification (B10 Phase D, #60)`

**Docs / persona / status:**

- [#184][pr184] `f0fc879` — `docs: persona status snapshot 17/0/0/0 post-PR-170 (W2.3 strict-PASS)`
- `92684b3` / `07095fc` — `docs: rust optimization ledger with empirical speedups (PR #114-#171)`
- `da38888` — `docs: v1.10 postflop optimization plan (research agent output)`

---

## Acknowledgments

This release closes the Premium-A blueprint shipping milestone, which
required:

- The **true 169-class engine** (PR [#171][pr171]) — the unblock that
  made the 27-blueprint compute pipeline run in 38.5 minutes
  instead of the projected 17-40 hours. Cumulative ~80,000× over
  vanilla CFR.
- The **blueprint loader / interpolation / subgame / router**
  Premium-A phase chain (PRs [#173][pr173] / [#174][pr174] /
  [#177][pr177] / [#181][pr181] / [#178][pr178]) — five clean
  per-phase landings driving end-to-end Premium-A capability.
- The **vector-form BR walk** (PR [#170][pr170]) — the final
  layer of the W2.3 strict-PASS unblock chain, on top of PR #114
  (TerminalCache), PR #139 (BR-walk terminal cache), and PR #162
  (BR-walk non-terminal cache + fused walk).
- The **B10 per-combo frequency feature train** (PRs [#149][pr149] /
  [#154][pr154] / [#158][pr158] / [#160][pr160]) — closing W2.2
  Sarah Range.diff.
- The **CS-bug fix** (PR [#165][pr165]) — tightening
  `State::initial` to honor `initial_contributions`; bit-clean on
  the default path, correctness fix on non-default configs.

Thanks to the persona-test framework for empirically anchoring the
strict-PASS milestones (W2.2 + W2.3 → 17/0/0/0) and to the
DCFR optimization ledger work for documenting the empirical
speedups that made the Premium-A compute budget practical.

---

## What's next

- **v1.10 — live flop subgame solve (task #70).** Research plan at
  `docs/v1_10_postflop_optimization_plan.md`. Target: flop top_k=169
  in <120 s wall, RSS ≤ 1 GB. Implementation order: arena → vector
  turn → vector flop → opt-in rayon. ~3-4 weeks engineering.
- **v1.11 candidates** (deferred from v1.10 research): board-iso
  caching at chance nodes, sparse range representation, PGO,
  BLAS-backed kernels, f32 migration.
- **v2.0:** 6-max engine (~3-month project; outside the current
  HUNL scope ledger).

---

[pr114]: https://github.com/amaster97/poker_solver/pull/114
[pr139]: https://github.com/amaster97/poker_solver/pull/139
[pr149]: https://github.com/amaster97/poker_solver/pull/149
[pr150]: https://github.com/amaster97/poker_solver/pull/150
[pr154]: https://github.com/amaster97/poker_solver/pull/154
[pr157]: https://github.com/amaster97/poker_solver/pull/157
[pr158]: https://github.com/amaster97/poker_solver/pull/158
[pr160]: https://github.com/amaster97/poker_solver/pull/160
[pr162]: https://github.com/amaster97/poker_solver/pull/162
[pr165]: https://github.com/amaster97/poker_solver/pull/165
[pr170]: https://github.com/amaster97/poker_solver/pull/170
[pr171]: https://github.com/amaster97/poker_solver/pull/171
[pr173]: https://github.com/amaster97/poker_solver/pull/173
[pr174]: https://github.com/amaster97/poker_solver/pull/174
[pr177]: https://github.com/amaster97/poker_solver/pull/177
[pr178]: https://github.com/amaster97/poker_solver/pull/178
[pr181]: https://github.com/amaster97/poker_solver/pull/181
[pr182]: https://github.com/amaster97/poker_solver/pull/182
[pr184]: https://github.com/amaster97/poker_solver/pull/184
