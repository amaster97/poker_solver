# PR 7 pre-commit checklist

**Status:** Gate before staging the PR 7 commit on `pr-7-noambrown-diff`.
**Date:** 2026-05-22
**Scope:** Local verification — run each gate, mark PASS/FAIL, fix any FAIL before staging.

Audit prompt: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt_final.md`
Pre-audit risk forecast: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_preprep.md`

---

## 1. Build gates

### 1.1 Rust build (PR 6 carry-over, must still pass)
```
cargo build --release --package cfr_core
```
- [ ] PASS — clean compile, no warnings.
- FAIL action: if Rust tier regressed, halt PR 7. PR 7 has no Rust source changes; a Rust failure means an integration-branch issue, not a PR 7 issue.

### 1.2 Rust clippy + tests (defense-in-depth)
```
cargo clippy --package cfr_core --all-targets -- -D warnings
cargo test --package cfr_core --all-targets
```
- [ ] clippy clean
- [ ] 12/12 Rust tests pass (no PR 7 additions; gating PR 6 regression)

### 1.3 Brown's C++ solver build (PR 7 native)
```
bash scripts/build_noambrown.sh
```
- [ ] PASS — produces `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` (~206 KB Mach-O arm64 on M-series).
- [ ] Second invocation is idempotent (no rebuild — `find ... -newer` short-circuits).
- [ ] On a host without `cmake` or `c++`: soft-fails with informative message + `exit 0`. **NOT** `exit 1`. Verify by temporarily uninstalling / PATH-masking cmake.

---

## 2. Test gates

### 2.1 PR 7 self-sanity smoke (must pass WITHOUT Brown binary)
```
pytest tests/test_river_diff_self_sanity.py -v
```
- [ ] 8+ tests pass (per spec §10 Agent C scope)
- [ ] No test attempts a Brown subprocess invocation
- [ ] 10-case history canonicalization round-trip fixture passes (per `agent_c_prompt.md:162-191`)
- [ ] Case 8 (`b500/r9000 ↔ b500A` all-in round-trip) PASSES — high-probability bug surface per `audit_preprep.md §1.3`

### 2.2 PR 7 diff harness (skip-clean if binary missing; pass if binary present)
```
pytest tests/test_river_diff.py -v
```
- [ ] If Brown binary present: 15 spots × diff assertion all pass within tolerance.
- [ ] If Brown binary absent: clean `pytest.skip("Brown's river_solver_optimized not built; run scripts/build_noambrown.sh")` at module or test scope. NO `FileNotFoundError`, NO `subprocess.CalledProcessError`.
- [ ] Per-action tolerance literal in harness == `5e-3` (NOT `1e-2`, NOT `5e-2` — silent relaxation is must-fix per audit prompt area 6).
- [ ] Per-spot game-value tolerance == `1e-3 * spot.pot`.
- [ ] 80% history-coverage assertion present and active (audit area 11).

### 2.3 Combined PR 7 module run
```
pytest tests/test_river_diff.py tests/test_river_diff_self_sanity.py -v
```
- [ ] PASS — both modules green.

### 2.4 Full regression — no PR 1-6 breakage
```
pytest -m "not slow and not very_slow" --tb=line
```
- [ ] All pass / skip; no failures.
- [ ] Kuhn + Leduc tiers unchanged.
- [ ] HUNL Python tier (PR 5) unchanged.
- [ ] HUNL Rust tier (PR 6) unchanged.
- [ ] `tests/test_hunl_diff.py` passes under the new loud-RuntimeError gate. (Stale `_rust.so` would trigger the new RuntimeError — that path should not fire in a clean tree.)

### 2.5 xdist parallel safety check
```
pytest tests/test_river_diff.py -n 4   # if pytest-xdist installed
```
- [ ] No `/tmp` file collision (verify each subprocess call uses `tempfile.NamedTemporaryFile`).
- [ ] If xdist not installed: skip this gate, but spot-check `noambrown_wrapper.py` for `NamedTemporaryFile(suffix=".json", delete=False)` + `os.unlink` in `finally` (audit area 9).

---

## 3. Static analysis gates

### 3.1 ruff
```
ruff check poker_solver/parity/ tests/test_river_diff*.py
```
- [ ] PASS — no errors.

### 3.2 black
```
black --check poker_solver/parity/ tests/test_river_diff*.py
```
- [ ] PASS — formatting clean.

### 3.3 mypy strict
```
mypy --strict poker_solver/parity/
```
- [ ] PASS on PR 7 files. Per spec §10 Agent A: wrapper is type-hinted + mypy --strict clean.

### 3.4 License audit (no AGPL drift)
```
bash scripts/check_pr.sh   # if PR-audit script exists
```
- [ ] No new AGPL/GPL deps. PR 7 adds zero runtime deps.
- [ ] No verbatim copy of Brown's C++ in `poker_solver/parity/noambrown_wrapper.py`. Manual scan of `cpp/src/river_game.cpp` ↔ wrapper: must be re-implementation, not transcription.

---

## 4. License + attribution verification (audit area 8)

- [ ] `references/code/noambrown_poker_solver/LICENSE` is MIT (verify file, not just spec claim).
- [ ] `poker_solver/parity/noambrown_wrapper.py:1-N` carries spec §8 attribution docstring header naming:
  - [ ] Brown's repo name + URL
  - [ ] MIT license declaration
  - [ ] Public CLI surface depended upon (`--algo dcfr`, `--dcfr-alpha`, `--dcfr-beta`, `--dcfr-gamma`, `--seed`, `--iters`, `--dump-strategy`)
  - [ ] JSON output schema we parse
- [ ] No NOTICE file required (MIT doesn't mandate). Confirm no NOTICE update was made.
- [ ] Brown binary is NOT bundled in the wheel — verify `pyproject.toml` does NOT include `references/code/...` in package_data or include patterns.

---

## 5. Version + release artifact gates

### 5.1 Version bump (PATCH: 0.5.0 -> 0.5.1)

**Rationale:** PR 7 adds NO new public API surface. `poker_solver/parity/` is internal test infrastructure (no CLI flag, no `__init__.py` export added to the top-level `poker_solver` package, no new wheel-exposed entry point). The PR 6 v0.5.0 contract (`--backend rust` + `poker_solver._rust.solve_hunl_postflop`) is unchanged. Per docs/pr6_prep/semver_sequencing.md: "no public API surface change" + "validation-only addition" → PATCH bump, NOT MINOR. PR 2 / PR 3 / PR 5 / PR 6 each added new CLI flags or new top-level exports → MINOR. PR 7 does not.

- [ ] `poker_solver/__init__.py`: `__version__ = "0.5.1"` (was `"0.5.0"`).
- [ ] `pyproject.toml`: `[project] version = "0.5.1"` (was `"0.5.0"`).
- [ ] `CHANGELOG.md`: new `[0.5.1] - 2026-05-22` section above `[0.5.0]`, summarizing the external-Nash validation gate.
- [ ] `CHANGELOG.md`: `[Unreleased]` block emptied (PR 7 entry moved into `[0.5.1]`).
- [ ] `CHANGELOG.md`: `[0.5.1]: ./` link reference appended at the bottom in sort order.
- [ ] `README.md`: "Current version: 0.5.1" + one-line caption on Brown-diff oracle validation.

### 5.2 No unintended file changes
```
git diff --stat integration...HEAD
```
- [ ] Expected diff: ~8 files, ~2,076 LOC new + ~22 diff lines (per `agent_progress_check.md §4`).
- [ ] No accidental edits to `poker_solver/_rust*.so`, `Cargo.lock` (Rust binary artifacts).
- [ ] No accidental edits outside the parity wrapper + tests + fixture + build script + version-bump triplet.

---

## 6. Audit-driven gates (cross-check `audit_prompt_final.md`)

For each of the 15 audit focus areas, the audit report must mark either "Looks good" or surface a finding. Pre-commit, spot-check the three HIGH-PROB surfaces:

- [ ] **Area 2 (raise canonicalization round-trip):** `canonicalize_brown_history` + `canonicalize_our_history` both produce `tuple[(action_kind, amount), ...]`; 10-case round-trip fixture in `test_river_diff_self_sanity.py` passes. Verify state reset between streets.
- [ ] **Area 9 (subprocess + xdist):** `--bet-sizes` joined as comma string (NOT list); parses `--dump-strategy` JSON file (NOT stdout); `tempfile.NamedTemporaryFile` per call; `os.unlink` in `finally`; Brown binary path anchored via `Path(__file__).resolve().parents[2]`.
- [ ] **Area 1 (build script soft-fail):** `set -e` does not pre-empt the soft-fail branch; `exit 0` on missing cmake/c++.

---

## 7. Post-merge follow-up (after PR 7 lands on integration)

- [ ] 6-branch worktree sync: every sibling worktree fast-forwards `integration` per `feedback_no_concurrent_branch_ops.md` (never branch-switch in the shared working tree mid-write).
- [ ] PLAN.md pruned: PR 7 line moved from "in flight" → "merged"; any PR 7 forecast surfaces from `audit_preprep.md` that turned out empty are archived per `feedback_continuous_pruning.md`.
- [ ] `docs/pr7_prep/audit_report.md` archived to `docs/archive/pr7_audit_report.md` after the verdict is captured in PLAN.md.
- [ ] PR 8 fan-out prep begins (slumbot lookup table + SIMD + cache-blocking — spec §3 of PR 6 commit message defers these here).

---

## 8. Constraints

- **DO NOT commit yet.** This checklist is gate-only.
- **DO NOT skip hooks** (`--no-verify`) under any condition (per global rules).
- **DO NOT amend the previous commit** — PR 7 is a new commit on its own feature branch.
- Reference audit prompt by path in the commit message body (already done).

When all gates above are PASS, proceed to stage + commit per `commit_message_draft.md`.
