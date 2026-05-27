# v1.8.0 Final Ship-Readiness Verification — 2026-05-26

**Re-verification context:** Initial pre-flight was run by agent `a9bd75f`
before PR #68 (A83 multiplicity confirmation) and PR #69 (ship-blocker
hot-patch) merged. This re-verification covers state of `origin/main`
AFTER those two PRs landed.

**`origin/main` HEAD SHA at re-verify time:** `b401f6c87a18734cdf50883f642d11b98f9688c6`

---

## Item-by-item results

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Current `origin/main` SHA | PASS | `b401f6c87a18734cdf50883f642d11b98f9688c6` (PR #68 head); use as `--expected-sha` |
| 2 | `cargo check` cfr_core clean | PASS | `Checking cfr_core v0.7.0 ... Finished dev profile [unoptimized + debuginfo] target(s) in 0.79s`; no warnings/errors (cargo at `~/.cargo/bin/cargo` 1.95.0) |
| 3 | `python -c "from poker_solver._rust import solve_hunl_postflop"` | PASS | Output: `OK` |
| 4 | v1.8 SIMD phases all present | PASS | Phase 1 = `485aa8c` (#23); Phase 2 = `8073bcc` (#41); Phase 3 = `a712950` (#33); Phase 4 = `77e751c` (#32); AVX2 = `db8d646` (#35); all present on `origin/main` |
| 5 | Ship-blocker hot-patch (PR #69, `98fb503`) on main | PASS | `git log origin/main --oneline \| grep 98fb503` → `98fb503 fix(solver): hard-fail scalar HUNL postflop without initial_hole_cards (v1.8 ship-blocker) (#69)` |
| 6 | A83 multiplicity doc (PR #68) on main | PASS | `git ls-tree origin/main docs/a83_nash_multiplicity_confirmed_2026-05-26.md` → `100644 blob 09ca2376...` (289 lines, added in commit `b401f6c`). Note: NOT yet in local working tree (local main is 1 commit behind origin) |
| 7 | Release notes draft has A83 multiplicity + ~1.0× SIMD honesty | PASS | `origin/main` copy: contains `"NOT-A-BUG (Nash multiplicity EMPIRICALLY CONFIRMED)"` + `max \|Δ\| = 0.998499` + `~1.0×` SIMD measured-on-M4-Pro language. Local copy is stale (pre-#68) but release script reads from working tree at release time; user must `git pull --ff-only origin main` before running script (script enforces this in Phase 0.3) |
| 8 | Release script executable + version sync | PASS | `scripts/release_v1_8_0.sh` mode 100755 (executable); `pyproject.toml` = 1.7.0, `poker_solver/__init__.py __version__` = "1.7.0", `crates/cfr_core/Cargo.toml` = "0.7.0"; script bumps to 1.8.0 / 0.8.0 |
| 9 | PR #69 hard-fail smoke test | PASS | CLI `solve --game hunl --hunl-mode postflop --backend rust --board "As 7c 2d Kh 5s" --stacks 100 --iterations 10` → `error: --hunl-mode postflop --backend rust currently has no way to specify fixed hole cards, which the Rust scalar solver requires (without them, the root becomes a chance node and the solve returns an empty strategy). For range-vs-range Nash on a postflop board, use the Python API poker_solver.solve_range_vs_range_nash(config, hero_range, villain_range, ...) instead. Use --backend python for the reference postflop path.` (HARD-FAIL with informative message confirmed) |
| 10 | v1.5 Brown acceptance smoke | PASS | `2 passed, 1 warning in 274.31s (0:04:34)` |

---

## Recommended release script invocation

```bash
cd /Users/ashen/Desktop/poker_solver
git pull --ff-only origin main          # fast-forward local main to b401f6c
bash scripts/release_v1_8_0.sh --expected-sha b401f6c87a18734cdf50883f642d11b98f9688c6
```

The script's hardcoded `EXPECTED_SHA=f165eb85fd409e66d4a2c929e411811a7d150fbe`
is now stale (that was origin/main at script-write time, before PRs
#43, #46, #38, #48, #36, #47, #51, #53, #52, #50, #55, #56, #57, #58,
#59, #60, #61, #62, #63, #64, #65, #66, #67, #69, #68 merged). User
MUST override via `--expected-sha b401f6c87a18734cdf50883f642d11b98f9688c6`
or the script will abort at Phase 0.4.

Also note: local working tree is currently 1 commit behind `origin/main`
(missing PR #68). The script's Phase 0.3 check (`LOCAL_SHA != REMOTE_SHA`)
will abort until `git pull --ff-only origin main` is run.

---

## Overall verdict: **GO**

All 10 pre-flight items PASS. The v1.8.0 release is ship-ready against
`origin/main` HEAD `b401f6c`. User actions required before running
release script:

1. `git pull --ff-only origin main` (fast-forward local main from
   `f165eb8` to `b401f6c`; brings PR #68's A83 multiplicity doc +
   updated release notes into working tree).
2. Pass `--expected-sha b401f6c87a18734cdf50883f642d11b98f9688c6` when
   invoking `scripts/release_v1_8_0.sh` to satisfy Phase 0.4.

No ship-blockers identified.

---

## Notes on items not strictly verified by smoke

- **CI green check (script Phase 0.5):** not run as part of this
  verification — the script itself will gate on `gh run list --branch main
  --limit 10`. If recent CI on origin/main is red, the script will abort.
- **`backup` remote configured (script Phase 0.9):** not verified here;
  user can pre-check via `git remote get-url backup` or pass `--skip-backup`.
- **`.dmg` upload (script Phase 4):** off by default; user opts in via
  `--upload-dmg` after building per
  `docs/dmg_build_runbook_2026-05-26.md`. Not blocking for the tag/release.
