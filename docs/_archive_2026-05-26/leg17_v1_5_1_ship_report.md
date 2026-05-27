# LEG 17 — v1.5.1 Ship Report (PATCH bundle: PR 32 + PR 36 + PR 37)

**Ship date:** 2026-05-23
**Plan:** `docs/leg17_v1_4_4_ship_plan.md` (legacy slug; authoritative v1.5.1 plan)
**Bump:** PATCH (1.5.0 → 1.5.1)
**Outcome:** SHIPPED successfully. Zero conflicts, all smoke tests green.

---

## 1. Release artifacts

| Artifact | Value |
|---|---|
| Tag name | `v1.5.1` |
| Tag SHA (annotated) | `3cf70d0dfa28fca4cd8b213c27fb616f0dc936fa` |
| Tag points to commit | `b5777f22f99ee3b912822c0fb30d771dd03954df` (release bump) |
| Release URL | https://github.com/amaster97/poker_solver/releases/tag/v1.5.1 |
| Previous release | v1.5.0 (`dc3df6c`) |
| Commits on origin/main delta | 4 (3 cherry-picks + 1 release bump) |

### Commit chain on `origin/main` (top → bottom)

```
b5777f2 v1.5.1: test rigor + docs honesty (engine bundle deferred to v1.5.2)
8b8d181 Honest docs: PR 7 '<10s/spot' claim was aspirational, never validated (PR 32)
5145674 PR 36: profiler test rigor (closed-form toy + calibration + golden-file + structure invariant)
87e0b9a PR 37: equity test-helper for rigorous persona acceptance criteria
dc3df6c v1.5.0: vector-form CFR + Brown apples-to-apples acceptance  ← v1.5.0
```

---

## 2. Execution timeline

| Step | Wall-clock |
|---|---|
| Pre-flight (verify origin/main + 3 branch SHAs + shared tree state) | ~1 min |
| Ship worktree create + .so symlink | ~30 sec |
| 3 cherry-picks (PR 37 → PR 36 → PR 32) | ~30 sec |
| Smoke tests (91 passed, 5 skipped) | ~2 min |
| Version bump + CHANGELOG edit + commit | ~1 min |
| Tag + push main + push tag | ~30 sec |
| GitHub release create | ~15 sec |
| LEG 16 plan re-key + cleanup | ~1 min |
| **Total wall-clock** | **~7 min** (well under 25 min budget) |

---

## 3. Cherry-pick verification

All 3 cherry-picks landed with ZERO conflicts (as predicted by the conflict matrix in `leg17_v1_4_4_ship_plan.md` §3 — disjoint file sets).

| PR | Source SHA | New commit SHA | Files changed |
|---|---|---|---|
| PR 37 | `0f1c2636` | `87e0b9a` | 3 files (+297): `tests/_equity_helpers.py`, `tests/conftest.py`, `tests/test_equity_helpers.py` |
| PR 36 | `1850709a` | `5145674` | 1 file (+525/-9): `tests/test_memory_profiler.py` |
| PR 32 | `f7e55ca5` | `8b8d181` | 1 file (+9/-2): `tests/test_river_diff_self_sanity.py` |

**Base-mismatch flag (PR 32) resolved:** PR 32 was authored on `eea3a8b` (v1.4.3), but `tests/test_river_diff_self_sanity.py` was byte-identical between `eea3a8b` and `dc3df6c` (v1.5.0). Cherry-pick replayed cleanly with no merge conflict.

---

## 4. Smoke test results

Headline smoke set (per user prompt, expanded):

```
tests/test_equity_helpers.py            9 passed  (new in v1.5.1; PR 37)
tests/test_memory_profiler.py           6 passed + 1 skipped  (4 new in v1.5.1; PR 36)
tests/test_range.py                     22 passed
tests/test_dcfr_diff.py                 5 passed
tests/test_exploit_diff.py              5 passed
tests/test_range_vs_range_aggregator.py 20 passed
tests/test_node_locking.py              22 passed + 2 skipped
                                        --------------------------------
TOTAL                                   91 passed, 5 skipped in 116.09s
```

No regressions vs. v1.5.0 baseline. PR 37 adds 9 new tests, PR 36 adds 4 new tests = +13 net new test coverage as expected.

Note: used `python -m pytest` (per LEG 14 follow-up) to bypass the pyenv arm64/x86_64 shim quirk; all Rust-backed tests (`test_dcfr_diff.py`, `test_node_locking.py` rust subset, `test_exploit_diff.py`) passed.

---

## 5. Version bump verification

| File | Before | After |
|---|---|---|
| `pyproject.toml` | `version = "1.5.0"` | `version = "1.5.1"` |
| `poker_solver/__init__.py` | `__version__ = "1.5.0"` | `__version__ = "1.5.1"` |
| `crates/cfr_core/Cargo.toml` | `version = "0.5.0"` | (unchanged — crate version tracks independently per workspace convention; not bumped at PATCH) |

CHANGELOG.md: prepended `## [1.5.1] - 2026-05-23` section ABOVE `## [1.5.0]` without touching v1.5.0 or v1.4.x blocks. Verified: `grep -c '^## \[1.5.0\]' = 1` and `grep -c '^## \[1.5.1\]' = 1`.

---

## 6. Honest framing in CHANGELOG + release notes

Both the CHANGELOG entry and GitHub release notes explicitly document:

- v1.5.1 is a PATCH: no engine changes, no source-code changes, no behavior changes
- v1.5.0 `_rust.cpython-313-darwin.so` is reused byte-identically (no Rust rebuild needed)
- **v1.5.0 acceptance-test status is unchanged** — the per-action divergence on the Brown apples-to-apples test is NOT addressed by v1.5.1
- Engine bundle (PR 33 + PR 34 + PR 35) is **deferred to v1.5.2** pending diagnosis

Public-OK audit: release notes contain no `/Users/ashen/...` paths, no session IDs, no PII, no orchestrator/implementer references.

---

## 7. LEG 16 re-key — DONE

`docs/leg16_v1_5_1_ship_plan.md` now carries a top-banner re-key notice flagging the slot shift to v1.5.2 and the new base SHA (`b5777f2`) for the engine bundle's cherry-picks. The original file content is preserved (per "add header note; don't delete the old file" guidance from the user prompt). Original filename retained — rename to `leg16_v1_5_2_ship_plan.md` is optional and deferred to LEG 16 fire time.

Re-audit note: PR 33/34/35 touched files are disjoint from v1.5.1's added/changed files (`tests/_equity_helpers.py`, `tests/conftest.py`, `tests/test_equity_helpers.py`, `tests/test_memory_profiler.py`, `tests/test_river_diff_self_sanity.py`, `CHANGELOG.md`, `pyproject.toml`, `poker_solver/__init__.py`). No cherry-pick conflict expected when LEG 16 fires onto v1.5.1's HEAD.

---

## 8. Cleanup status

- `_rust.cpython-313-darwin.so` symlink removed from ship worktree before `git worktree remove`.
- `ship-v1.5.1` worktree removed cleanly.
- `ship-v1.5.1` branch retained (not deleted; awaits orchestrator decision per memory rule against `-D`).

---

## 9. Unexpected complexity

**None.** This was the cleanest ship in the LEG 11-17 sequence:

- Zero cherry-pick conflicts (disjoint file matrix held)
- Zero smoke-test failures
- Zero version-bump complications
- Zero release-notes sanitization findings
- Total wall-clock under 7 minutes (vs. 25 min budget; vs. LEG 14 baseline of ~15 min for 4 PRs)
- Symlink-and-reuse pattern (LEG 12 / LEG 14) worked first try; Rust binding loaded immediately

LEG 14's pyenv shim arch quirk did NOT recur — using `python -m pytest` was sufficient to bypass it (the workaround is now well-established).

---

## 10. Next steps

1. **v1.5.2 ship (LEG 16):** engine bundle (PR 33 + PR 34 + PR 35) remains held pending per-action divergence diagnosis on the v1.5.0 Brown apples-to-apples acceptance test. Re-keyed plan banner is in place at `docs/leg16_v1_5_1_ship_plan.md`.
2. **PLAN.md cleanup:** prune any v1.5.1 / v1.4.4 routing notes that are now resolved; archive references to the slot collision.
3. **No persona retest triggered:** per `feedback_ui_packaging_sync`, v1.5.1 is internal-only (tests + docs); no UI or persona-facing surface changes, no PR 11 .dmg rebuild needed.

---

**Authorization confirmation:** Per `feedback_pr10a5_autonomous_commit` + user's explicit OK in the LEG 17 prompt: PR 32, PR 36, PR 37 all audit-cleared; autonomous end-to-end ship (commit + push + tag + release) was within scope. No exception conditions triggered (no force-push, no origin branch deletion, no Type C-CRITICAL findings during ship, no major design decisions deferred).
