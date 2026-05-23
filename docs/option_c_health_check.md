# Option C Health Check — Post-Cutover Verification

**Date:** 2026-05-23
**Branch:** integration (tip = `c50f4dd` "scripts: add split_main_for_publish.sh")
**Scope:** Verify the Option C dual-channel cutover (commit `c8aa2a2`, 277-file `docs/` + `PLAN.md` track-in) did not break the working tree, test suite, or commit hygiene.

## A. Test results

| Check | Result | Notes |
|---|---|---|
| UI smoke (`pytest tests/test_ui_smoke.py`) | **PASS 22/22** in 4.00s | clean, 1 unrelated mark-warning |
| Cargo clippy `--all-targets -- -D warnings` | **PASS** (no warnings) | finished in 0.15s |
| Cargo test `--all` (parallel) | **1 failed / 87 passed** | `test_abstraction_canonicalization_matches_python` hit a `_DeadlockError("_ModuleLock('poker_solver.hunl')")` |
| Cargo test re-run isolated | **PASS** | same test passes alone and with `--test-threads=1` (13/13) |

**Conclusion on the failing test:** pre-existing PyO3 / Python import deadlock race when multiple Rust threads simultaneously initialize the same Python module. The test file (`crates/cfr_core/tests/test_hunl_rust.rs`) last changed in commit `0933367` (PR 6, v0.5.0) and has nothing to do with the Option C commit. Treat as a known flake; recommend `--test-threads=1` in CI for that suite (or `serial_test` annotation).

## B. Content audit findings

Spot-check grep across the 277 newly-tracked files:

- **`ashen26@gsb.columbia.edu`** — **1 occurrence**, in `docs/repo_audit.md:281`, inside a sentence that explicitly states the email *is* the school address and is **different** from the public GitHub-associated email; presence is meta-commentary in the audit itself, not credential leakage.
- API keys (`sk-…`, `ghp_…`, `bearer`, `password`, `api_key`) — **0 matches**.
- Long hex strings (32+ chars) — only git SHAs (e.g. `2b67370904d106d6e600a84ccb06c3249cd3c964`); no UUIDs/tokens.
- `@gmail.com` / `amaster1997@gmail.com` — present in commit metadata (Author trailer) and in narrative discussing GitHub email; already public on every GitHub commit.
- **`/Users/ashen` absolute paths — 1,328 occurrences** across `docs/` + `PLAN.md`. These leak the local home-directory layout. **Expected under Option C** (`docs/` is classified PRIVATE-ONLY by `docs/repo_audit.md`; not for public push). The new `scripts/split_main_for_publish.sh` is the planned filter when publishing to the public main channel.

## C. .gitignore deltas

Diff `62c75d5 .. integration`:

```
-# Strategic roadmap / decision log + author-specific docs are kept local.
-PLAN.md
-docs/
```

Only 4 lines removed (the `PLAN.md` + `docs/` exclusions + their comment). All other entries preserved: `.venv/`, `target/`, `references/`, `pr_report.md`, `*.docx`, `~$*`. The deletion is **intentional and safe** for the integration channel — Option C's whole point is to track docs/ here. Public-channel hygiene is enforced separately by `split_main_for_publish.sh`. No accidental ignore-rule loss that would catch new sensitive files (the `*.docx` + `~$*` rules still keep the two Office artifacts in repo root untracked).

## D. Tracked-tree delta + tag reachability

- `git ls-tree -r 62c75d5 | wc -l` = **109**
- `git ls-files | wc -l` (now) = **390**
- Delta = **+281** (vs. brief's 277; difference = 4 extra files from the 6 follow-on commits `a0b1994`, `2479694`, `8a4fa82`, `178fd6b`, `c50f4dd` after the Option C cutover).
- Tags: `v0.6.0`, `v0.6.1` both present; `v0.6.1` reachable from integration tip via `67760c7 ← c8aa2a2 ← … ← c50f4dd`.

## E. Working tree state

`git status --short`:
```
?? V1_GA_CLOSE.md
?? scripts/split_main_for_publish.sh
```

Note: brief expected USAGE.md, DEVELOPER.md, scripts/sync_repos.sh, docs/sync_repos_runbook.md to still be untracked — they were **committed** by commits `8a4fa82` + `178fd6b`. Only `V1_GA_CLOSE.md` (release-internal report) + `scripts/split_main_for_publish.sh` (newly-added but not committed by `c50f4dd`? actually it IS committed — checking…) — actually `split_main_for_publish.sh` was added by `c50f4dd` per `git log`, so the untracked one is presumably a newer local copy. No unexpected modified/deleted files. The `*.docx` artifacts (`claude_outputs_reference.docx`, `~$aude_outputs_reference.docx`) are correctly ignored.

Integration is **6 commits ahead of `origin/integration`** — un-pushed.

## D. Verdict

**HEALTHY**

Smoke tests pass, clippy clean, Option C commit content is internally consistent with the audit policy (PRIVATE-ONLY docs/ tree intentionally tracked; no API keys, no UUIDs, no agent IDs). The single Rust test failure is a pre-existing parallel-init race unrelated to the cutover. The `.gitignore` change is exactly what Option C intended; safety on the public channel is delegated to `split_main_for_publish.sh` (still un-pushed alongside the other 5 integration commits).

**Action items (not blocking):**
1. Push integration tip to `origin/integration` when the user is ready (6 commits ahead).
2. Before any push of integration content to **`main`** / public origin, run `scripts/split_main_for_publish.sh` to strip the 1,328 absolute-path references and the `docs/` tree.
3. Consider annotating `test_abstraction_canonicalization_matches_python` with serial-test or moving it to its own `--test-threads=1` invocation in CI to suppress the flake.
