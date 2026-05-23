# PR 11 launch-readiness verification (v2 — post-PR-10a landing)

**Date:** 2026-05-22
**Reviewer:** orchestrator verification agent (read-only)
**Predecessor:** `launch_readiness.md` (READY, 8/8 spec checks); this v2 supersedes by confirming the integration-side pre-flight is now satisfied.
**Verdict:** **READY**

---

## 1. Five required verification items

### V1 — Branch name canonical (PASS)

- `launch_kickoff.md` §2 line 82 + §"Branch:" line 7: `pr-11-library-and-packaging`.
- `fanout_ready.md` §2 line 58: same literal, branch created from `integration` not `main` (per PLAN.md §1 per-PR branches rule).
- `audit_prompt_final.md` line 21: branch-under-audit name matches; hard-coded so cross-references in audit's `git diff integration...HEAD` resolve.
- Drift fix from prior pass is preserved; no prompts reference an alternate spelling.

### V2 — Pre-flight: PR 10a on integration (PASS — confirmed live)

- `git log --oneline integration -5` shows tip `b880032 Integration: merge PR 10a (UI mock-first scaffold + xfail followup, v0.6.0)`.
- `git rev-parse integration` = `b880032c728466759984746ce68fc7d58852ae34` — matches task brief's stated hash.
- PR 10a library stub present at `ui/views/library_browser.py` — confirmed via `test -f` (the file PR 11's UI integration sub-task extends into a real loader per `pr11_spec.md` §4.1).
- `poker_solver/_rust.cpython-313-darwin.so` present locally (pre-flight 1e in `fanout_ready.md`) — Agent B's PyInstaller smoke step has the binary to bundle.
- Tip hash should be captured to `/tmp/integration_pre_pr_11.hash` immediately before branch creation per `launch_kickoff.md` §1e.
- Note (non-blocking): orchestrator-side working tree is on `pr-10a-ui-mock-first` with an unstaged edit to `tests/test_ui_smoke.py`. The fan-out itself runs after a checkout to `integration` (per `launch_kickoff.md` §2); the local edit must be committed/stashed/discarded before branching, or it'll travel onto the new branch. Resolve before firing.

### V3 — Three-agent fan-out scope clear (PASS)

- Ownership table in `fanout_ready.md` §3 lines 89-93 and `launch_kickoff.md` §3 lines 124-128 are identical and explicit:
  - Agent A → `poker_solver/library.py` + `library_schema.sql` + `__init__.py` re-exports + `cli.py` library subcommands. Forbidden: any packaging script, any test, any UI file, `dcfr.py`, `hunl_solver.py`, profiler.
  - Agent B → `scripts/build_macos_dmg.sh` + `sign_and_notarize.py` + `entitlements.plist` + `poker_solver.spec` (optional) + `assets/poker_solver.icns` + `assets/README.md`. Surgical edit to `pyproject.toml` only under `[project.optional-dependencies] distribution`. Forbidden: library, tests, CLI, UI.
  - Agent C → `tests/test_library.py` + `tests/test_library_cli.py` + `tests/test_library_ui_integration.py` (stub) + `scripts/batch_solve.py` + `examples/tiny_csv.csv`. Surgical edit to `scripts/check_pr.sh`. Forbidden: any non-test, non-batch-solve file.
- Zero file overlap between agents; all three launch in the SAME tool-call wave per `launch_kickoff.md` §3 / `fanout_ready.md` §3 (`run_in_background: true` for each).

### V4 — `--add-binary` for `_rust.cpython-313-darwin.so` explicit (PASS)

- `launch_kickoff.md` §4a + §8.1 (top-risk recap) + `fanout_ready.md` §5 all restate the literal: `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"`.
- `audit_prompt_final.md` focus area 1 lines 55-62: HIGHEST-IMPACT must-fix with three sub-probes (flag missing, smoke-test missing, syntax wrong). Mandatory paragraph-level audit discussion even if no defect.
- Three-part defense recap: (1) explicit flag, (2) post-PyInstaller in-bundle headless smoke step (`from poker_solver import _rust`), (3) documented failure mode. Mitigation per spec §6.3 + §12.1.
- `_rust.cpython-313-darwin.so` confirmed present at `poker_solver/_rust.cpython-313-darwin.so` — Agent B has a real binary to ingest.

### V5 — Apple Developer opt-in / signed + unsigned paths (PASS)

- `launch_kickoff.md` §4b lists the three failure modes for the optional-credentials path: skip-flags still calling `codesign`, missing `xcrun` pre-check, accidental hard-coupling of `--skip-notarization` to `--skip-signing`.
- `audit_prompt_final.md` focus area 2 lines 64-70: `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` MUST produce a working unsigned `.app` + `.dmg` with zero Apple env vars. Hard dependency on signing → must-fix.
- `fanout_ready.md` §3 locked-defaults paragraph (line 95): "D13.1 Apple Developer optional (`--skip-signing --skip-notarization` produces a working unsigned `.app` + documented Gatekeeper bypass)".
- Credentials policy: `audit_prompt_final.md` focus area 8 lines 120-128 mandates a grep sweep for `Developer ID Application`, email patterns, password-like strings, team IDs — ANY hit is a must-fix security blocker. `entitlements.plist` allowed (entitlement keys only, no credentials).
- Right-click "Open" / `xattr -d com.apple.quarantine` Gatekeeper-bypass docs land in `assets/README.md` (Agent B owns).

---

## 2. Residual findings

**One non-blocking item:** orchestrator-side working tree is on `pr-10a-ui-mock-first` with an unstaged edit to `tests/test_ui_smoke.py`. Resolve (commit/stash/discard per intent) and `git checkout integration && git pull --ff-only origin integration` before running the `git checkout -b pr-11-library-and-packaging` line. This is the standard `launch_kickoff.md` §1c/§2 pre-flight and is mechanical, not a spec defect.

The eight spec-side checks from v1 (`launch_readiness.md` §1) remain PASS — none of them depend on integration-side state and the PR 10a landing did not perturb the locked defaults D1-D13 (SQLite WAL, SHA-256 spot ID, gzip-6, arm64-only, `--onedir`, explicit save, Apple Developer optional).

---

## 3. Verdict

**READY.** All five v2 verification items pass with explicit evidence. PR 10a is live on integration at `b880032`. Branch name, fan-out scope, top-risk mitigation, and Apple Developer optionality are locked, consistent across `launch_kickoff.md` + `fanout_ready.md` + `audit_prompt_final.md`, and ready to fire after the one mechanical pre-branch cleanup (working-tree state, V2 residual). No patches required.
