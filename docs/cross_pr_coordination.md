# Cross-PR coordination — file-touch matrix + merge order for the PR 8 / PR 9 / PR 10a.5 / PR 10b fan-out

**Date:** 2026-05-22
**Owner:** orchestrator (cross-PR conflict watcher)
**Status:** in-flight; PR 8 + PR 9 + PR 10a.5 are running concurrently in separate worktrees / branches.
**Source artifacts:**
- `docs/pr8_prep/pr8_spec.md` §6 + `agent_{a,b,c}_prompt.md` ownership tables.
- `docs/pr9_prep/pr9_spec.md` §"Public API contract" + `agent_{a,b,c}_prompt.md` ownership.
- `docs/pr10_prep/pr10a5_conformance_backlog.md` §4 + §5 (scope + parallelism).
- `docs/pr10_prep/pr10b_spec.md` (also potentially in flight; included for completeness).

---

## 1. PR shape recap

| PR | Branch | Worktree | Touches (high level) |
|----|--------|----------|----------------------|
| 8 (NEON SIMD + layout + PCS) | `pr-8-simd-perf` | `/Users/ashen/Desktop/poker_solver_worktrees/pr-8-simd` | Rust-heavy: 3 new Rust modules + edits to `dcfr.rs`, `solver.rs`, `hunl_solver.rs`, `lib.rs`, `Cargo.toml`. Python-light: 1-field add on `hunl.py`. |
| 9 (HUNL preflop) | `pr-9-preflop` | `/Users/ashen/Desktop/poker_solver_worktrees/pr-9-preflop` | Python-heavy: 3 new Python modules + edits to `solver.py`, `cli.py`, `__init__.py`, `hunl.py`. Rust: 3 new modules + additive PyO3 bindings in `lib.rs`. |
| 10a.5 (UI conformance) | `pr-10a.5-conformance` | main worktree | UI-only: ~150-250 LOC across `ui/views/*.py`, `ui/state.py`, `ui/app.py`, plus 7 `xfail`-decorator removals in `tests/test_ui_smoke.py`. **Zero engine touches.** |
| 10b (mock→real swap) | `pr-10b-ui-real-solver` (not yet branched) | main (when fired) | Mock swap: edits to `hunl_solver.py` (`on_progress` kwarg), `ui/state.py`, `ui/app.py`, `tests/test_ui_smoke.py`, `README.md`. Deletes `ui/mock_solver.py`. |

---

## 2. Per-PR file-touch enumeration (estimated, from spec + agent prompts)

### PR 8 file touches

**New files (zero conflict potential):**
- `crates/cfr_core/src/simd.rs`
- `crates/cfr_core/src/layout.rs`
- `crates/cfr_core/src/pcs.rs`
- `crates/cfr_core/benches/cfr_bench.rs`
- `crates/cfr_core/benches/simd_microbench.rs`
- `benches/baseline.json`
- `tests/test_simd.rs`
- `tests/test_layout.rs`
- `tests/test_pcs.rs`
- `tests/test_pr8_convergence.py`
- `tests/fixtures/dcfr_kuhn_10k.json`
- `tests/fixtures/dcfr_leduc_10k.json`
- `tests/fixtures/pcs_seed7_first100.json`

**Modified existing files:**
- `crates/cfr_core/src/dcfr.rs` — Agent B (HashMap → FlatInfosetStore, SIMD routing) + Agent C (β-switch only).
- `crates/cfr_core/src/solver.rs` — Agent B (adapter for new infoset store API).
- `crates/cfr_core/src/hunl_solver.rs` — Agent C (PCS at chance nodes, `use_pcs` consumption).
- `crates/cfr_core/src/lib.rs` — Agent A adds `pub mod simd;`, Agent B adds `pub mod layout;`, Agent C adds `pub mod pcs;`.
- `crates/cfr_core/Cargo.toml` — Agent A adds `criterion = "0.5"` (dev-dep); Agent B adds `[[bench]]` entry; Agent C adds `rand = "0.8"` + `rand_chacha = "0.3"` (runtime deps).
- `poker_solver/hunl.py` — Agent C adds **single field**: `use_pcs: bool = False` on `HUNLConfig`.

### PR 9 file touches

**New files (zero conflict potential):**
- `poker_solver/preflop_solver.py`
- `poker_solver/blueprint.py`
- `poker_solver/subgame_refiner.py`
- `crates/cfr_core/src/preflop.rs`
- `crates/cfr_core/src/blueprint.rs`
- `crates/cfr_core/src/subgame.rs`
- `tests/test_hunl_preflop_blueprint.py`
- `tests/test_hunl_preflop_refinement.py`
- `tests/test_hunl_preflop_integration.py`
- `tests/test_preflop_diff.py`
- `tests/fixtures/hunl_preflop_fixtures.py`

**Modified existing files:**
- `poker_solver/solver.py` — Agent A adds preflop dispatch branch + >250 BB ValueError after PR 3.5's push/fold branch.
- `poker_solver/cli.py` — Agent A adds `--hunl-mode preflop` (with `full` as deprecated synonym) + 6 new flags (`--stacks`, `--ante`, `--blueprint-iterations`, `--refine-iterations`, `--reach-threshold`, `--abstraction`, `--max-memory-gb`).
- `poker_solver/__init__.py` — Agent A re-exports `solve_hunl_preflop`, `PreflopSolveResult`, `BlueprintResult`, `build_blueprint`, plus Agent B's `refine_subgame`, `SubgameKey`, `SubgameRefinementResult`.
- `poker_solver/hunl.py` — Agent A adds `_enumerate_preflop_hole_outcomes_canonical()` method + opt-in `chance_strategy: Literal["full", "canonical_classes"] = "full"` kwarg (or per-config attribute).
- `crates/cfr_core/src/lib.rs` — Agent C adds three `#[pyfunction]` bindings (`solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`) + matching `m.add_function(...)` in `#[pymodule]` block. **STRICTLY ADDITIVE** per Agent C prompt §"File ownership" + line 32.

**NOT touched by PR 9 (explicit prohibition per agent prompts):**
- `Cargo.toml` (per Agent C prompt line 38: "no new Rust deps for PR 9").
- `pyproject.toml` (per spec §"Files to modify" line 181: "no new third-party deps").
- `poker_solver/dcfr.py` (frozen per Agent A prompt line 31).
- `poker_solver/hunl_solver.py` (PR 5 frozen per Agent A prompt line 32).
- `crates/cfr_core/src/{dcfr,solver,hunl_solver,hunl,hunl_tree,hunl_eval,abstraction}.rs` (Agent C touches lib.rs only, no other existing Rust file).

### PR 10a.5 file touches

**Modified existing files (UI-only):**
- `ui/views/range_matrix.py` — marker enumeration fixes + `cell_rgb_for_action_freqs` adapter + `DISPLAY_PALETTE` + `blocker-overlay` class.
- `ui/views/spot_input.py` — preset marker ID alignment + `INPUT_PALETTE`.
- `ui/views/run_panel.py` — `expl-chart-linear-toggle` marker + `oom-reduce-bet-sizes-button` + `progress-eta` marker.
- `ui/views/tree_browser.py` — marker drift fixes (already shown in current diff).
- `ui/state.py` — `SolveRunner.compute_eta()` method add.
- `ui/app.py` — `pushfold-switch-button` toast wire at ≤15 BB warning.
- `tests/test_ui_smoke.py` — remove 7 `@pytest.mark.xfail` decorators.

**NOT touched:** `poker_solver/`, `crates/`, `pyproject.toml`, `Cargo.toml`, `CHANGELOG.md` (deferred — only README + release notes update for v0.6.1).

### PR 10b file touches (when fired)

- `poker_solver/hunl_solver.py` — add `on_progress` kwarg.
- `ui/state.py` — replace mock import with dispatch wrapper.
- `ui/app.py` — Q7 banner → chip downgrade.
- `ui/mock_solver.py` — **DELETED**.
- `ui/mock_solver_fixtures.py` — **DELETED** (if present).
- `tests/test_ui_smoke.py` — delete 5 mock-specific tests; add 2 real-solve tests.
- `README.md` — `## UI (mock)` → `## UI`.

---

## 3. Cross-PR conflict matrix

Legend: `X` = both PRs touch the file (potential merge conflict); `add-only` = PR adds-only edits, conflict resolution is mechanical concatenation; `disjoint` = no overlap in lines touched; `—` = neither PR touches.

| File | PR 8 | PR 9 | PR 10a.5 | PR 10b | Risk |
|------|------|------|----------|--------|------|
| `crates/cfr_core/src/lib.rs` | **X** (Agent A: 1 line `pub mod simd;`; Agent B: 1 line `pub mod layout;`; Agent C: 1 line `pub mod pcs;`) | **X** (Agent C: 3 `#[pyfunction]` exports + 3 `m.add_function(...)` lines) | — | — | **MEDIUM** (both add-only; conflict only if both append to identical regions of `#[pymodule]` block) |
| `crates/cfr_core/Cargo.toml` | **X** (Agent A: `criterion`; Agent C: `rand`, `rand_chacha`) | — | — | — | **LOW** (PR 8 only; PR 9 explicitly does not touch) |
| `poker_solver/hunl.py` | **X** (PR 8 Agent C: single field `use_pcs: bool = False` on `HUNLConfig`) | **X** (PR 9 Agent A: new `_enumerate_preflop_hole_outcomes_canonical()` method + opt-in `chance_strategy` kwarg) | — | — | **HIGH** (both modify the same file; both touch `HUNLConfig`-adjacent code; semantic-merge required — see §5) |
| `poker_solver/__init__.py` | — | **X** (PR 9 Agent A: 4-7 new re-exports) | — | — | **LOW** (PR 9 only) |
| `poker_solver/solver.py` | — | **X** (PR 9 Agent A: dispatch branch + >250 BB ValueError) | — | — | **LOW** (PR 9 only) |
| `poker_solver/cli.py` | — | **X** (PR 9 Agent A: 7 new flags + mode dispatch) | — | — | **LOW** (PR 9 only) |
| `poker_solver/hunl_solver.py` | — | — | — | **X** (PR 10b: `on_progress` kwarg) | **LOW** (PR 10b not yet in flight) |
| `crates/cfr_core/src/dcfr.rs` | **X** (PR 8 Agent B: HashMap → FlatInfosetStore; Agent C: β-switch) | — | — | — | **LOW** (PR 8 only) |
| `crates/cfr_core/src/solver.rs` | **X** (PR 8 Agent B: adapter) | — | — | — | **LOW** (PR 8 only) |
| `crates/cfr_core/src/hunl_solver.rs` | **X** (PR 8 Agent C: PCS at chance nodes) | — | — | — | **LOW** (PR 8 only) |
| `pyproject.toml` | — | — | — | — | **NONE** (no PR touches; per PR 8 spec line 282 + PR 9 spec line 181) |
| `CHANGELOG.md` | append entry post-merge | append entry post-merge | append entry post-merge | append entry post-merge | **LOW** (all append-only to `[Unreleased]` section; serialized by merge order) |
| `tests/test_ui_smoke.py` | — | — | **X** (PR 10a.5: remove 7 xfail decorators) | **X** (PR 10b: delete 5 / add 2 tests) | **HIGH** if 10a.5 + 10b run concurrently — but 10b is gated behind PR 9 merge, so likely sequential. Same-file editing across the two would conflict. |
| `tests/test_hunl_postflop_solve.py` | — | — | — | possibly `on_progress` test add | **NONE** (no in-flight PR touches) |
| `ui/views/*.py` | — | — | **X** (PR 10a.5: ~150 LOC across 3 view files) | — (forbidden per PR 10b §3) | **NONE** (PR 10b explicitly forbidden from touching `ui/views/*.py`) |
| `ui/state.py` | — | — | **X** (PR 10a.5: `compute_eta`) | **X** (PR 10b: dispatch wrapper) | **MEDIUM** if 10a.5 + 10b concurrent (different functions; mechanical merge but same file) |
| `ui/app.py` | — | — | **X** (PR 10a.5: pushfold toast wire) | **X** (PR 10b: banner → chip) | **MEDIUM** if 10a.5 + 10b concurrent (different surfaces; mechanical merge but same file) |
| New test files (`test_simd.rs`, `test_layout.rs`, `test_pcs.rs`, `test_hunl_preflop_*.py`, `test_preflop_diff.py`) | PR 8 owns 3 Rust + 1 Python | PR 9 owns 4 Python + 1 fixture | — | — | **NONE** (disjoint file names) |
| New Rust modules (`simd.rs`, `layout.rs`, `pcs.rs`, `preflop.rs`, `blueprint.rs`, `subgame.rs`) | PR 8 owns 3 | PR 9 owns 3 | — | — | **NONE** (disjoint file names) |
| New Python modules (`preflop_solver.py`, `blueprint.py`, `subgame_refiner.py`) | — | PR 9 owns 3 | — | — | **NONE** |

---

## 4. Top 3 conflict-risk files

Ranked by probability × severity:

### 4.1 `poker_solver/hunl.py` (HIGH)
- **PR 8 Agent C** adds `use_pcs: bool = False` field on `HUNLConfig` dataclass (~line 76-130 region per Agent C prompt line 53).
- **PR 9 Agent A** adds new generator method `_enumerate_preflop_hole_outcomes_canonical()` AND `chance_strategy: Literal["full", "canonical_classes"] = "full"` kwarg/attribute on `HUNLConfig` (per spec §5 + Agent A prompt line 27).
- **Both edits are additive but to the same dataclass** — git's three-way merge may succeed or may produce a conflict depending on whether either edit lands adjacent text. If conflict: trivial to resolve (concat both new fields), but the merger MUST be aware of both edits to not drop one.
- **Mitigation:** PR 8 merges first; PR 9 rebases on top of integration with PR 8 landed. Agent C of PR 9 (test author) verifies `pytest tests/test_hunl_core.py` is still green AND that the `use_pcs` field is preserved.

### 4.2 `crates/cfr_core/src/lib.rs` (MEDIUM)
- **PR 8 Agents A/B/C** each add ONE `pub mod X;` line to the top-of-file module declarations region (lines 18-25 currently); they may also each add `m.add_function(wrap_pyfunction!(...), m)?` lines inside the `#[pymodule] fn _rust(...)` block at line 175-182.
- **PR 9 Agent C** adds three `#[pyfunction]` annotated function definitions in the middle of the file AND three `m.add_function(wrap_pyfunction!(solve_hunl_preflop_rust, m)?)?;` etc. lines in the `#[pymodule]` block — same lines 175-182 region.
- **Both PRs append to the same `#[pymodule]` block** — git will likely auto-merge but if either PR also reorders existing entries or both PRs' edits adjacent to the closing `Ok(())`, manual resolution needed.
- **Mitigation:** Both PRs are explicitly additive (PR 8 Agent A prompt + PR 9 Agent C prompt line 32). Merge order: PR 8 first (smaller diff in lib.rs — 3 mod lines + 0 new pyfunctions in the canonical path; the actual SIMD/layout/PCS are not exposed to Python). PR 9 rebases and re-applies its 3 additive pyfunction registrations.

### 4.3 `crates/cfr_core/Cargo.toml` (LOW-MEDIUM)
- **PR 8 Agent A** adds `criterion = "0.5"` to `[dev-dependencies]`.
- **PR 8 Agent C** adds `rand = "0.8"` + `rand_chacha = "0.3"` to `[dependencies]`.
- **PR 8 Agent B** adds `[[bench]]` entries (`name = "cfr_bench"`, `harness = false`).
- **PR 9 does NOT touch Cargo.toml** (Agent C prompt line 38 explicit prohibition).
- **Net:** intra-PR-8 coordination only; PR 9 is disjoint. Not a cross-PR risk; flagged here only because three agents within PR 8 are all editing the same file.

**Honorable mentions (lower risk):**
- `ui/state.py` and `ui/app.py` — both PR 10a.5 and PR 10b touch these. Mitigated by PR 10b being gated behind PR 9 merge, so they likely serialize.
- `CHANGELOG.md` — every PR appends to `[Unreleased]`. Always serialized by merge order; never a true conflict.

---

## 5. Merge order recommendation

**Recommended order:** `PR 10a.5 → PR 8 → PR 9 → PR 10b`

**Rationale:**

1. **PR 10a.5 first (smallest scope, zero engine touches).** UI-only diff; landing it removes the 12-item v0.6.0 follow-up debt and unblocks any future UI work. Zero conflict surface with PR 8 or PR 9. Land it on `integration` ASAP to clean the slate.

2. **PR 8 second.** PR 8 is a Rust-heavy refactor (HashMap → FlatInfosetStore, NEON SIMD, PCS) plus a single-field schema add (`use_pcs: bool = False`) on `HUNLConfig`. The diff is large but self-contained — the only Python-side touch is one field on one dataclass. Landing PR 8 before PR 9 means PR 9's Rust port (`preflop.rs`, `blueprint.rs`, `subgame.rs`) gets to import the new `FlatInfosetStore` + PCS modules natively if useful, OR explicitly opts out — but either way the surface is locked when PR 9 starts integrating against it.

3. **PR 9 third.** PR 9 rebases on integration-with-PR-8-merged. The rebase will need:
   - **`poker_solver/hunl.py`:** confirm `use_pcs: bool = False` field landed by PR 8 is preserved; Agent A's `_enumerate_preflop_hole_outcomes_canonical()` is additive and disjoint. Trivial.
   - **`crates/cfr_core/src/lib.rs`:** confirm PR 8's `pub mod simd; pub mod layout; pub mod pcs;` declarations are preserved; Agent C's three new `#[pyfunction]` exports are additive in the `#[pymodule]` block. Trivial.
   - **`crates/cfr_core/Cargo.toml`:** PR 9 does not touch; PR 8's new deps are preserved.
   - **NEW Rust modules:** PR 9's `preflop.rs`, `blueprint.rs`, `subgame.rs` are net-new — no rebase conflict.
4. **PR 10b last.** Requires both PR 9 (preflop solver + `on_progress` kwarg) and PR 10a (UI scaffold) to be on integration. PR 10a is already merged; PR 9 merge satisfies the second dep. PR 10b then runs single-agent (per its kickoff §3 — no fan-out needed). Conflicts with PR 10a.5 on `ui/state.py` + `ui/app.py` are mitigated by the order (PR 10a.5 lands first, PR 10b sees the updated file and edits different functions/regions).

**Reverse-order fallback** (if PR 9 lands first for some reason): PR 8 rebases against PR 9's `lib.rs` additions (more risky because PR 8 also touches `lib.rs` for module decls) and `hunl.py` (more risky because PR 9 added a generator method, possibly adjacent to where PR 8 adds the field). The forward order is preferred.

---

## 6. Specific guidance for each implementer agent (cross-PR)

### For PR 8 Agent C (the only agent that touches `hunl.py`)
- **DO:** add the single line `use_pcs: bool = False` to `HUNLConfig` dataclass.
- **DO:** preserve the lossless `infoset_key` method (lines ~309-318) bit-for-bit.
- **DO NOT:** touch any other field, method, or import in `hunl.py` — leave room for PR 9's additive `_enumerate_preflop_hole_outcomes_canonical()` method to land downstream.
- **DO NOT:** reorder fields in `HUNLConfig` — keep PR 8's field at the END of the dataclass so PR 9's additions (which may add a `chance_strategy` attribute) land at a stable position.

### For PR 9 Agent A (the only agent that touches `hunl.py` and `__init__.py` for PR 9)
- **DO:** add the `_enumerate_preflop_hole_outcomes_canonical()` generator method.
- **DO:** add the opt-in `chance_strategy` kwarg/attribute per spec §5.
- **DO NOT:** modify, reorder, or remove the existing `HUNLConfig` fields. **Specifically: if `use_pcs: bool = False` is present after rebase (landed by PR 8 first), do NOT touch it.** Append your additions AFTER `use_pcs`.
- **DO NOT:** modify the existing `_enumerate_preflop_hole_outcomes()` (the 1.6M-combo generator); preserve unchanged behavior for non-opt-in callers.

### For PR 9 Agent C (the only agent that touches `lib.rs` for PR 9)
- **DO:** add three additive `#[pyfunction]` definitions for `solve_hunl_preflop_rust`, `build_blueprint_rust`, `refine_subgame_rust`.
- **DO:** add three matching `m.add_function(wrap_pyfunction!(...), m)?` lines at the **end** of the `#[pymodule] fn _rust(...)` block (after the existing `m.add_function(wrap_pyfunction!(solve_hunl_postflop, m)?)?;` and after PR 8's PCS / SIMD additions if any).
- **DO NOT:** modify existing PyO3 bindings (`solve_kuhn`, `solve_leduc`, `solve_hunl_postflop`).
- **DO NOT:** modify the existing `pub mod` declarations at the top — PR 8 will add `pub mod simd; pub mod layout; pub mod pcs;` there; your edits stay below.
- **DO NOT:** touch `Cargo.toml` (per Agent C prompt line 38).

### For PR 8 Agent A (the only agent that touches `Cargo.toml`)
- **DO:** add `criterion = "0.5"` under `[dev-dependencies]`.
- **DO:** coordinate with Agent C (PR 8) for the `rand` + `rand_chacha` runtime deps — these go under `[dependencies]`, not `[dev-dependencies]`. Different sections; no conflict.
- **DO NOT:** modify `pyproject.toml` (PR 8 spec line 282 explicit no-change requirement).

### For PR 10a.5 implementer
- **DO:** focus on `ui/views/*.py`, `ui/state.py`, `ui/app.py`, `tests/test_ui_smoke.py` only.
- **DO:** remove the 7 `@pytest.mark.xfail` decorators after the four wire-ups land.
- **DO NOT:** touch `poker_solver/`, `crates/`, `pyproject.toml`, `Cargo.toml`, `README.md` (out of scope per `pr10a5_conformance_backlog.md` §6).
- **DO NOT:** modify any markers in PR 10a-frozen surfaces (Q1-Q6 locks). Only the 5 failing markers + 7 xfail-blocking wire-ups land.

---

## 7. Verification commands (for orchestrator post-merge sanity)

After each PR merges, the orchestrator should run a sanity grep to confirm cross-PR edits did not collide:

```sh
cd /Users/ashen/Desktop/poker_solver

# After PR 8 lands on integration:
grep -nE "use_pcs|pub mod simd|pub mod layout|pub mod pcs" crates/cfr_core/src/lib.rs
grep -n "use_pcs: bool" poker_solver/hunl.py
# Expect: 3 mod declarations + 1 Python field.

# After PR 9 lands on integration (PR 8 already there):
grep -nE "use_pcs|chance_strategy|_enumerate_preflop_hole_outcomes_canonical" poker_solver/hunl.py
# Expect: PR 8's use_pcs preserved + PR 9's two additions present.
grep -nE "solve_hunl_preflop_rust|build_blueprint_rust|refine_subgame_rust|pub mod simd|pub mod layout|pub mod pcs" crates/cfr_core/src/lib.rs
# Expect: 3 PR 8 mods + 3 PR 9 PyO3 functions present.

# Existing test surface confirmation:
pytest tests/test_hunl_core.py tests/test_hunl_tree.py -x
# Expect: all green (PR 3 lossless behavior preserved by both PRs' hunl.py edits).
```

---

## 8. Risk surface summary

**HIGH-risk file (1):** `poker_solver/hunl.py` — both PR 8 and PR 9 modify the same file, both touch `HUNLConfig`. Mitigation: merge order PR 8 → PR 9; PR 9 implementer aware of PR 8's `use_pcs` field landing first.

**MEDIUM-risk files (3):** `crates/cfr_core/src/lib.rs` (PR 8 + PR 9 both add to `#[pymodule]` block); `ui/state.py` and `ui/app.py` (PR 10a.5 + PR 10b both edit, but order serializes via PR 10b's gating). All resolvable via git auto-merge in the forward order.

**LOW-risk files:** `Cargo.toml` (PR 8 only), `__init__.py` (PR 9 only), `tests/test_ui_smoke.py` (PR 10a.5 + PR 10b — same-file but ordered).

**ZERO-conflict files:** all NEW Rust modules, all NEW Python modules, all NEW test files, all NEW fixtures.

**No re-scoping needed** — no PR is rewriting the same function that another PR is rewriting. The risk surface is limited to additive edits on shared files, which are mechanical to merge in the recommended forward order.
