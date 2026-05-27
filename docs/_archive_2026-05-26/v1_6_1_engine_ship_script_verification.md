# v1.6.1-engine Ship Script — Dry-Run Verification Report

**Date:** 2026-05-23
**Script under test:** `/Users/ashen/Desktop/poker_solver/scripts/ship_v1_6_1_engine.sh` (340 lines)
**Path D doc:** `/Users/ashen/Desktop/poker_solver/docs/v1_6_1_path_d_decision.md`
**Method:** Worktree-isolated simulation; no commit / no tag / no push.
**Simulation worktree:** `/tmp/v1_6_1_ship_simulation_86433` (removed after run).

---

## Verdict

**SCRIPT READY-TO-EXECUTE.** All 4 cherry-picks clean, xfail edit lands correctly, cargo + critical regression gates green.

---

## Phase 1 — SHA verification

All 4 SHAs referenced in the script match the current local branch tips exactly:

| Branch | Expected | Resolved | Status |
|---|---|---|---|
| `pr-46-dcfr-panic-fix` | `cd56761` | `cd56761f867815cb69f48e9d3bf815e9c28539e0` | OK |
| `pr-33-python-delegate` | `29a00c0` | `29a00c0cda54156c09cbbc3b17c9a54878e3ef12` | OK |
| `pr-35c-paired-fix` | `63c9432` | `63c94320306fa68f19b21c0c4f46dc4dc6bb9eb8` | OK |
| `pr-40-acceptance-test-fix` | `c058e97` | `c058e97409a7bd327a02c54daa648b52a69824f9` | OK |

Origin/main HEAD at base of simulation: `bf6f966` (`chore: regenerate Cargo.lock for cfr_core 0.6.0`).
Local `main` is at `ca8c7af`; the script correctly bases the ship worktree on `origin/main`, not local `main`.

---

## Phase 2 — Cherry-pick simulation

Performed in `/tmp/v1_6_1_ship_simulation_86433` based on `origin/main`. Conflict count: **0**.

| Order | PR | SHA | Result | Resulting HEAD | Files changed |
|---|---|---|---|---|---|
| 1 | PR 46 (panic fix) | `cd56761` | CLEAN | `a3e82a8` | 1 file (+34/-4) |
| 2 | PR 33 (Python delegate) | `29a00c0` | CLEAN | `1194c2c` | 2 files (+530/-1); creates `tests/test_python_delegate.py` |
| 3 | PR 35c (paired ALL_IN cap) | `63c9432` | CLEAN | `73ab329` | 3 files (+18/-3) |
| 4 | PR 40 (acceptance test plumbing) | `c058e97` | CLEAN | `50a56fc` | 1 file (+104/-17) |

The script comment at lines 62-66 predicting "PR 40 expected conflict at PER_ACTION_TOL line... should be CLEAN" matches reality: PR 40 cherry-picked without conflict.

---

## Phase 3 — xfail edit verification

**Insertion-point search.** The needle (`@pytest.mark.parametrize("spot_id", COVERED_SPOT_IDS)\ndef test_v1_5_brown_apples_to_apples_parity(spot_id: str) -> None:`) was found exactly once in `tests/test_v1_5_brown_apples_to_apples.py` at lines 482-483 in the post-cherry-pick tree.

> The script's banner comment at lines 100-104 references lines 422-426 — this is a stale comment from before PR 40 was rebased. The script uses **string-based** replacement (`text.replace(needle, replacement, 1)`), NOT line-number editing, so the off-by-line comment is cosmetic and does NOT affect execution.

**Edit application.** Ran the script's exact Python block (lines 113-136) against the simulation file:
- `PYTHON_EXIT=0`
- `ast.parse(...)` re-parse: `OK`
- Decorator placed between `@parametrize` and `def`:
  ```
  482: @pytest.mark.parametrize("spot_id", COVERED_SPOT_IDS)
  483: @pytest.mark.xfail(strict=False, reason=(
  484:     "v1.6.1 Path D: ... See docs/a83_deep_cap_root_cause_investigation.md."
  485: ))
  486: def test_v1_5_brown_apples_to_apples_parity(spot_id: str) -> None:
  ```
- xfail edit: **APPLIED CORRECTLY.**

---

## Phase 4 — Version-bump source markers (pre-execution sanity)

All anchor strings present in the post-cherry-pick worktree before any version bump:

| File | Expected anchor | Found? |
|---|---|---|
| `pyproject.toml` | `version = "1.6.0"` | YES (single occurrence) |
| `poker_solver/__init__.py` | `__version__ = "1.6.0"` | YES |
| `crates/cfr_core/Cargo.toml` | `version = "0.6.0"` | YES |
| `CHANGELOG.md` | `## [1.6.0]` marker | YES (line 16) |

Script phases 4 and 5 should all succeed; the version-bump and CHANGELOG-insert Python blocks would each find their anchors.

---

## Phase 6 — Smoke matrix results

Executed inside an isolated `.venv` created in the simulation worktree (so the user's global `poker_solver` install is untouched).

| Step | Result | Detail |
|---|---|---|
| `cargo build --release` | **PASS** | `Finished release profile [optimized] target(s) in 7.72s` |
| `cargo test --lib --release` | **PASS** | 50 passed; 0 failed; 0 ignored; 25.91s |
| `maturin develop --release` | **PASS** | Built wheel; installed `poker_solver-1.6.0` editable in venv; 7.20s |
| `pytest tests/test_exploit_diff.py` | **PASS 5/5** | All 5 tests green in 51.71s (critical Python-Rust diff gate at 1e-6) |
| `pytest tests/test_python_delegate.py` | **PASS 5/5** | All 5 tests green in 110.28s (PR 33 delegate verification) |

Broad pytest sweep (`pytest -x -m "not slow and not very_slow"`) was deliberately skipped per task instructions — only the explicit critical regression gates were run.

---

## Issues identified

**None blocking.** One cosmetic note:

1. Lines 100-104 of the script reference test-file lines `422-426` for the xfail insertion context, but the actual post-cherry-pick lines are `482-486`. This is purely a banner-comment staleness; the script uses string match so the wrong line numbers in the banner do not change behavior. Not worth blocking the ship to fix — recommended to update the comment opportunistically.

---

## Cleanup

- Simulation worktree at `/tmp/v1_6_1_ship_simulation_86433` removed via `git worktree remove --force`.
- `git worktree list` confirms no leaked simulation worktrees.
- No commits / tags / pushes created.

---

## Pre-execution checklist for the user

Per the script's own header (lines 23-31) — these are USER preconditions, NOT verifiable from this dry-run:

- [ ] User explicitly approved Path D on session sign-on
- [ ] No other agent currently pushing to main concurrently
- [x] Dry-run mental walk-through of this script complete (THIS REPORT)
- [x] CHANGELOG body in §5 matches actual ship composition (verified PR 33 + 46 + 35c + 40 wording)
- [x] No leaked `/tmp/ship-v1.6.1-engine-*` worktrees (none present)
- [ ] `gh CLI` authenticated for `amaster97/poker_solver` (`gh auth status`)
- [ ] HTTPS+osxkeychain creds present

---

## Recommendation

**USER CAN INVOKE** `bash scripts/ship_v1_6_1_engine.sh` once they confirm the unchecked checklist items above (gh auth + no concurrent main-pushers + explicit Path D approval). The script is mechanically sound; all phases have been independently verified against the actual repo state.
