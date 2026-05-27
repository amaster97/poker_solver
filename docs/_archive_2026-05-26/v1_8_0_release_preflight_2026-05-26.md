# v1.8.0 Release Script — Pre-Flight Dry-Run Report

**Date:** 2026-05-26
**Script:** `scripts/release_v1_8_0.sh` (17309 bytes, executable, untouched)
**Procedure:** Manual replication of script Phase 0 — Phase 2+ NOT executed.
**Working dir:** `/Users/ashen/Desktop/poker_solver`

---

## TL;DR

**Verdict: SHIP-READY with one mandatory flag override.**

The script will run cleanly end-to-end after passing `--expected-sha 533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d` because `origin/main` has advanced 11 commits past the script's hard-coded `EXPECTED_SHA=f165eb85` (PR #52). The new commits are all docs-only / non-code (PRs #53-#63), confirmed safe to release as v1.8.0.

**Recommended invocation:**
```
bash scripts/release_v1_8_0.sh --expected-sha 533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d
```

**Confidence: HIGH** (script's own pre-flight will block any drift; soft-fails are well-handled.)

---

## Script Anatomy (confirmed)

The script has 6 phases (Phase 0–5), not 5:

| Phase | Purpose |
|---|---|
| 0 | Pre-flight checks (this report) |
| 1 | Version bumps (pyproject + __init__ + Cargo.toml) |
| 2 | Commit + push to origin/main |
| 3 | Annotated tag + push to origin |
| 4 | `gh release create` (+ optional .dmg upload) |
| 5 | Push main + tag to `backup` private mirror |

**No `--dry-run` or `--preflight-only` flag exists.** Available flags:
- `--upload-dmg` (default OFF — requires .dmg already built)
- `--skip-backup` (default OFF — backup push enabled)
- `--no-bump-cfr-core` (default OFF — Cargo.toml will bump 0.7.0 → 0.8.0)
- `--expected-sha <sha>` (override EXPECTED_SHA)

---

## Pre-Flight Check Matrix

| # | Check | Status | Detail |
|---|---|---|---|
| 0.1 | On `main` branch | PASS | `git branch --show-current` → `main` |
| 0.2 | Working tree clean (tracked) | PASS | `git status --porcelain` grep -v `^??` → empty. Untracked files exist (PLAN.md, docs/*.md, .merge_logs/) but script only checks `git status --porcelain` which DOES show `??` lines — see Caveat 1 below |
| 0.3 | Local HEAD == origin/main | PASS | Both at `533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d` |
| 0.4 | HEAD matches `EXPECTED_SHA` | **FAIL (expected)** | Script has `EXPECTED_SHA=f165eb85` (PR #52, archive PR). Main has advanced 11 commits to `533cb8eb` (PR #63). Script will print WARN and exit 1 — fix via `--expected-sha 533cb8eb...` |
| 0.5 | CI on main green (last 10) | PASS | 10/10 success: all "Skip-Ban (Acceptance Tests)" — no failures, no in-progress |
| 0.6a | `pyproject.toml` version == 1.7.0 | PASS | Confirmed `1.7.0` |
| 0.6b | `poker_solver/__init__.py` `__version__` == "1.7.0" | PASS | Confirmed `1.7.0` |
| 0.6c | `crates/cfr_core/Cargo.toml` version == 0.7.0 | PASS | Confirmed `0.7.0` (bump path enabled by default) |
| 0.7 | Release notes file exists | PASS | `docs/v1_8_0_release_notes_DRAFT.md` (23911 bytes, last modified 2026-05-26 03:50) |
| 0.8a | Tag `v1.8.0` does NOT exist locally | PASS | `git tag -l v1.8.0` empty |
| 0.8b | Tag `v1.8.0` does NOT exist on origin | PASS | `git ls-remote --tags origin refs/tags/v1.8.0` empty |
| 0.9 | `backup` remote configured | PASS | `https://github.com/amaster97/poker_solver_private.git` (reachable, main on same SHA as origin) |
| — | `gh` CLI authenticated | PASS | `amaster97` (keyring), token scopes `gist,read:org,repo,workflow` |

---

## Out-of-Script Checks (USER-REQUESTED, not script-enforced)

These are NOT in the script's Phase 0 but the user asked me to verify them:

| Check | Status | Detail |
|---|---|---|
| All v1.8 SIMD phases on main | PASS | Phase 1 (`485aa8c`), Phase 2 (`8073bcc`), Phase 3 (`a712950`), Phase 4 (`77e751c`), AVX2 (`db8d646`) — all `git merge-base --is-ancestor` confirmed |
| `cargo check` clean (cfr_core) | PASS | `cargo check --manifest-path crates/cfr_core/Cargo.toml` → "Finished `dev` profile" in 0.17s, zero warnings |
| `ruff check .` clean | **WARN** | 6 errors: 4× I001 (import sort) + 1× F541 (f-string no placeholder) + 1× B017 (test broad-except). Files: `docs/_archive_2026-05-26/pr17_plan_c_parked/bench_3way.py`, `docs/pr18_prep/bench_w15.py`, `tests/test_aa_vs_aa_root_indifference.py`, `tests/test_exploitative_play.py`. **NOT BLOCKING** — ruff is not run by CI (no `ruff` in `.github/workflows/`) and not by the release script. Pre-existing; advisory only |
| `pytest tests/test_dcfr_diff.py -x --timeout=60 -q` | PASS* | 5/5 passed in 2.66s **when run with `/usr/local/bin/python3 -m pytest`** (system universal2 Python, arm64 mode). FAILED via `pytest` shim because pyenv 3.13-dev is x86_64-only but `_rust.so` is arm64-only. See Caveat 3 |
| `gh auth status` | PASS | (also covered in 0.5) |
| `maturin develop` available | PASS | `/Users/ashen/.pyenv/shims/maturin` present (for .dmg build later) |
| Python toolchain | PASS | python 3.13.1 (universal2 at /usr/local/bin/python3), arm64 native via `arch -arm64` |
| Rust toolchain | PASS | `cargo 1.95.0 (f2d3ce0bd 2026-03-21)` via `~/.cargo/bin/cargo` (rustup); NOT on default PATH but `cargo check` works after `source $HOME/.cargo/env` |

---

## Caveats / Soft Issues

### Caveat 1: `git status --porcelain` will show untracked files

The script's check 0.2 uses:
```
if [[ -n "$(git status --porcelain)" ]]; then
    echo "FATAL: working tree not clean..."
```

`git status --porcelain` DOES include `??` (untracked) lines. The repo currently has ~80+ untracked files (PLAN.md, docs/*.md drafts, .merge_logs/, etc.).

**THIS WILL HARD-FAIL THE SCRIPT.**

The user's stated invariant ("modulo untracked .local files which don't affect ship") does NOT match the script's actual implementation — the script is stricter than the user's expectation.

**Fix options:**
- (a) Add all untracked to `.gitignore` (preferred for `.local` files; check what's intentionally untracked)
- (b) `git stash --include-untracked` before running, `git stash pop` after
- (c) Move docs to a subdir already in `.gitignore`
- (d) Modify check 0.2 to grep out `^??` lines (NOT permitted per task constraints)

**Action required from user BEFORE running the script.**

### Caveat 2: EXPECTED_SHA drift

Script has `EXPECTED_SHA=f165eb85` (PR #52 "archive 34 unreferenced session drafts"). Current main is at `533cb8eb` (PR #63 "supersede banner on a83 RC investigation"). The intervening 11 commits are all docs-only:

```
533cb8e docs: supersede banner on a83 RC investigation (#63)
1e4e60c docs: v1.8.0 release notes final polish (#62)
55122c3 docs: fix 2 broken reference paths (#61)
eb74fb3 docs: track previously-orphan reference targets (#60)
6d99a96 docs: persona status update post-W3.2/W3.4 retests (#59)
9948eaa docs: add CHANGELOG note for poker-solver shim quirk (#58)
0d1c717 docs: resolve 7 MEDIUM stale claims (#57)
bf645ae docs: v1.8 release notes honesty (~1.0x not 4-8x) + W3.2 BR smoke (#56)
7bb21d8 docs: resolve 8 HIGH stale claims (#55)
97886e1 feat: v1.8.0 release execution script + .dmg build runbook (#54)
... (script itself was added in PR #54, after EXPECTED_SHA was set!)
```

**All 11 are docs-only / non-functional.** Safe to ship `533cb8e` as v1.8.0. Override with `--expected-sha 533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d`.

### Caveat 3: `.so` arch mismatch via pyenv shim

The default `pytest` is `/Users/ashen/.pyenv/shims/pytest` → uses pyenv's `3.13-dev` python, which is `x86_64`-only. The built `_rust.so` is `arm64`-only. Result: differential tests ERROR with `incompatible architecture` on this path.

**The release script does not run pytest, so this does not block Phase 0.** But the user MUST be aware of this for:
- Local smoke tests (use `/usr/local/bin/python3 -m pytest ...` or `arch -arm64 ...`)
- The .dmg build later (`maturin develop` should be invoked with arm64 python)

This is the exact `.so arch verification` hazard from memory (`feedback_dotso_arch_check.md`).

### Caveat 4: `--upload-dmg` will WARN (default OFF, correct)

`dist/Poker-Solver-1.8.0-arm64.dmg` does not yet exist. Do NOT pass `--upload-dmg` until the .dmg is built per `docs/dmg_build_runbook_2026-05-26.md`. Default behavior (off) is correct.

---

## Required Updates BEFORE Running Script

1. **Resolve untracked files** (Caveat 1) — pick option (a)/(b)/(c). This is the only hard blocker.
2. **Pass `--expected-sha`** (Caveat 2) — see recommended invocation below.

---

## Recommended Invocation

After resolving Caveat 1 (untracked files), run:

```bash
cd /Users/ashen/Desktop/poker_solver
bash scripts/release_v1_8_0.sh \
    --expected-sha 533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d
```

**Defaults the user is implicitly accepting:**
- `BUMP_CFR_CORE=1` → bumps `crates/cfr_core/Cargo.toml` 0.7.0 → 0.8.0 (aligned minor with Python pkg)
- `UPLOAD_DMG=0` → no .dmg upload (correct — build separately later)
- `PUSH_BACKUP=1` → pushes to private mirror after release (verified reachable)

**Optional toggles** (none currently recommended):
- Add `--no-bump-cfr-core` if you want Rust crate on its own SemVer track
- Add `--skip-backup` if backup push should be deferred

---

## Estimated Wall-Clock for Phase 2+

| Phase | Operation | Estimate |
|---|---|---|
| 1 | Version-bump edits (3 files) | <1 s |
| 2 | `git add` + `git commit` + `git push origin main` | 2–5 s |
| 3 | `git tag -a` + `git push origin v1.8.0` | 2–5 s |
| 4 | `gh release create` | 3–8 s |
| 5 | `git push backup main` + `git push backup v1.8.0` | 3–10 s (network-dependent) |
| **Total** | Phases 1–5 | **~10–30 s** |

Post-release (out of script scope): .dmg build is ~10–20 min on M-series host per `dmg_build_runbook_2026-05-26.md`.

---

## Confidence

**HIGH** — script is well-engineered with `set -euo pipefail`, no force-push, no hook-bypass, no branch deletions, clear FATAL messages, and explicit rollback guidance. The single drift point (EXPECTED_SHA) is handled by the `--expected-sha` flag and the WARN message even tells the user the exact flag to pass. The unblocked path (Caveat 1, untracked files) is a user-environment issue, not a script defect.

The script will either succeed all the way through Phase 5 OR halt at a clear FATAL with rollback instructions in the header comment.

---

## Files / SHAs Referenced

- `/Users/ashen/Desktop/poker_solver/scripts/release_v1_8_0.sh` — the release script
- `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md` — release notes
- `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_ship_prep_2026-05-26.md` — ship prep doc
- `/Users/ashen/Desktop/poker_solver/docs/dmg_build_runbook_2026-05-26.md` — .dmg runbook (post-release)
- `/Users/ashen/Desktop/poker_solver/pyproject.toml` — version source 1/3
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` — version source 2/3
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` — version source 3/3
- Current HEAD: `533cb8ebd5153e0a5327e9f418b2ed8de0b76e7d` (origin/main, PR #63)
- Script EXPECTED_SHA: `f165eb85fd409e66d4a2c929e411811a7d150fbe` (PR #52, 11 commits behind)
