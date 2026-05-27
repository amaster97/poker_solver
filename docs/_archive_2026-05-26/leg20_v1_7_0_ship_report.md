# Leg 20 — v1.7.0 Ship Report (Watchdog Salvage)

**Date:** 2026-05-23
**Status:** SHIPPED
**Mode:** Watchdog recovery from stalled prior agent (a4fa1fe929dde28dc)

---

## Diagnosis

**Row 3 of decision matrix** — Worktree existed but no pytest/cargo/maturin process active. Prior ship agent had died silently after making substantial progress.

**Salvage opportunity discovered:**
- Worktree `/private/tmp/ship-v1.7.0-fresh-78934` had:
  - Cherry-picks of PR 43 + PR 39 applied (HEAD at `4f42a5a`)
  - Version bumps staged but uncommitted (pyproject 1.7.0, __init__ 1.7.0, cfr_core 0.7.0, Cargo.lock regen, CHANGELOG entry)
  - Pre-built `target/release/libcfr_core.dylib` artifacts
- v1.7.0 tag did NOT exist on origin
- Latest GitHub release was v1.6.0

**Root cause of prior agent's stall:** worktree's `_rust.cpython-313-darwin.so` was x86_64-only (cross-compile artifact), but host is arm64 → pytest skipped 12/12 nash tests with `_rust.solve_range_vs_range_rust missing`, leaving the agent stuck in indefinite buffered pytest retries.

## Action Taken

Chose **salvage path** (not full RESPAWN) since substantive work was complete:

1. Copied universal arm64+x86_64 `_rust.so` from main workspace into worktree → nash tests immediately ran
2. Ran targeted smoke tests:
   - `cargo test --lib --release`: **50/50 passed**
   - `tests/test_range_vs_range_nash.py`: **12/12 passed** (13.05s)
   - `tests/test_cli_subcommands.py`: **6 passed / 1 skipped** (env-skip)
3. PII grep on diff: clean (no ashen26/columbia/gsb/session paths)
4. Committed staged version bumps
5. Rebased onto fresh origin/main (resolved Cargo.lock conflict — cfr_core 0.7.0 wins, regenerated cleanly)
6. Retagged v1.7.0 on rebased HEAD
7. Pushed: `git push origin HEAD:main` and `git push origin v1.7.0`
8. Created GitHub release with extracted CHANGELOG notes
9. Pruned dead worktree

## Outcomes

- **v1.7.0 SHIPPED: Y**
- **origin/main HEAD:** `3843ce7` (v1.7.0: aggregator->vector wiring + CLI subcommands)
- **Tag:** `v1.7.0` → commit `3843ce7`
- **Release URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.7.0

## Anomalies

1. **Architecture-mismatched .so as silent stall cause** — when pytest skips due to missing binding, the test suite appears to "hang" in buffered output without actually progressing. Worth noting for future ship sequences: check `file poker_solver/_rust.*.so` matches `uname -m` before launching pytest.
2. **Rebase required mid-ship** — origin/main moved during prior agent's stall (commits `bf6f966` Cargo.lock regen + `433ccfd` .dmg docs landed). Resolved cleanly; cfr_core 0.7.0 propagated via `cargo build` regen.
3. **Tag SHA changed on rebase** — annotated tag was retagged after rebase; pre-rebase tag never pushed, so no force-push needed.
