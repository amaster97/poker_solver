# v1.7.2 CI Hardening — Pre-Merge Audit

Date: 2026-05-25
Auditor: Independent pre-merge audit agent
Scope: PRs #20, #21, #22 (auto-merge agent is about to merge)
Mode: READ-ONLY (no PR touched, no merges)

## PR #20 (cross-platform CI matrix)

- **Title**: `feat(ci): cross-platform CI matrix for v1.8 prep`
- **Branch**: `pr-64-cross-platform-ci-matrix`
- **Files** (2, +92/-0):
  - `.github/workflows/ci.yml` (new, 63 lines)
  - `.github/workflows/lint.yml` (new, 29 lines)
- **Touches solver kernels?** No — CI config only.
- **Hardcoded paths**: none. Grep for `/Users/ashen/` → empty.
- **New deps**: none in `Cargo.toml` / `pyproject.toml`. CI installs only `maturin`, `ruff`, `black` (dev/CI-side).
- **PII** (`sk-`, `ghp_`, `sk-ant-`, session UUIDs): none.
- **YAML lint**: both files parse. Required fields (`name`, `on`, `jobs`) present. Action versions current (`actions/checkout@v4`, `actions/setup-python@v5`, `dtolnay/rust-toolchain@stable`).
- **Matrix sanity**: macos-14 (arm64/NEON), macos-13 (x86_64/SSE+AVX), ubuntu-22.04 (x86_64). Two commented-out entries (ubuntu-22.04-arm, windows-2022) properly gated. `fail-fast: false` set, `timeout-minutes: 30` set.
- **Silent skip risk**: `pytest -k simd` job will collect zero tests at merge time (no v1.8 SIMD tests on `main`). pytest exits non-zero on "no tests collected" by default, which is correct behaviour — it surfaces as a CI failure rather than a silent green.
- **Live CI state**: 4 of 5 status checks FAILED on the PR head commit (`rust` lint, `python` lint, macos-14 test, ubuntu-22.04 test). This is consistent with first-time clippy/ruff/black enforcement against a codebase not previously formatted to those tools, plus `-k simd` matching nothing.

**Verdict: SOFT-FLAG**

**Notes**: Workflow YAML is structurally clean and free of secrets/PII/hardcoded paths, but the live CI on the PR head is red across 4 of 5 jobs. The auto-merge agent must decide whether to (a) merge red with a known-friction acknowledgement (acceptable: this is infrastructure prep for v1.8), or (b) require lint cleanup before merge. Recommend a follow-up issue tracking "first-pass clippy/ruff/black baseline" so the red status doesn't become normalised noise. The `-k simd` job will need a placeholder test or `--allow-no-tests`-style guard to avoid permanent red.

---

## PR #21 (CI release workflow)

- **Title**: `feat(ci): v1.7.2 CI-driven release workflow`
- **Branch**: `pr-62-v1.7.2-ci-ship-workflow`
- **Files** (3, +184/-0):
  - `.github/workflows/release.yml` (new, 74 lines)
  - `.github/workflows/ship_dry_run.yml` (new, 28 lines)
  - `docs/RELEASE.md` (new, 82 lines)
- **Touches solver kernels?** No — CI config + docs only.
- **Hardcoded paths**: none. Grep for `/Users/ashen/` → empty.
- **New deps**: none in `Cargo.toml` / `pyproject.toml`. CI installs `maturin` only.
- **PII**: none.
- **YAML lint**: both files parse. Required fields present, action versions current. `permissions: contents: write` correctly scoped to release job for tag + release creation. `GITHUB_TOKEN` referenced via standard `${{ secrets.GITHUB_TOKEN }}`, no PATs.
- **Referenced files verified to exist on local `main`**:
  - `scripts/build_noambrown.sh` exists
  - `tests/test_exploit_diff.py` exists
  - `tests/test_v1_5_brown_apples_to_apples.py` exists
  - `CHANGELOG.md` exists
- **Trigger semantics**: `on: push: branches: ['ship/v*']` — fires only on `ship/v*` branch push, won't fire on `main` PR merges. Safe.
- **Silent skip risk**: release.yml exports `POKER_SOLVER_REQUIRE_BROWN_PARITY=1`. This sets the Brown-parity gate, but does NOT set `STRICT_ACCEPTANCE=1` — and PR #22 wires the `_skip_or_fail()` helper to gate ONLY on `STRICT_ACCEPTANCE`. After PR #22 merges, the release workflow will still silently skip if Brown prereqs are missing. See "Recommended merge order" below.

**Verdict: SOFT-FLAG**

**Notes**: Clean workflow with no secrets/PII/hardcoded paths and trigger semantics that won't accidentally fire. The one wrinkle is the env-var mismatch between PR #21 (`POKER_SOLVER_REQUIRE_BROWN_PARITY=1`) and PR #22 (`STRICT_ACCEPTANCE=1`). After both merge, the release workflow's smoke matrix won't trigger Guard C's hard-fail mode. Recommend a follow-up to add `STRICT_ACCEPTANCE: '1'` to the release.yml env block.

---

## PR #22 (Hardening Guards B + C)

- **Title**: `feat(ci): ship-hardening Guards B + C (golden regen + skip ban)`
- **Branch**: `pr-65-ship-hardening-guards-b-c`
- **Files** (5, +102/-7):
  - `.github/workflows/golden_check.yml` (new, 33 lines)
  - `.github/workflows/skip_ban.yml` (new, 42 lines)
  - `pyproject.toml` (+1 marker registration)
  - `tests/test_memory_profiler.py` (+1 marker decoration)
  - `tests/test_v1_5_brown_apples_to_apples.py` (+18/-7: `_skip_or_fail` helper + 5 skip-site migrations)
- **Touches solver kernels?** No — tests + CI + marker registration. `test_memory_profiler.py` change is a `@pytest.mark.golden` decorator only, no test logic edited.
- **Hardcoded paths**: none. Grep for `/Users/ashen/` → empty.
- **New deps**: none. `pyproject.toml` change is a marker entry in the `[tool.pytest.ini_options].markers` list, not a dependency.
- **PII**: none.
- **YAML lint**: both files parse. Skip-ban grep uses POSIX shell regex (portable on ubuntu-22.04 runner).
- **Silent skip audit (CRITICAL per `feedback_silent_skip_hazard.md`)**:
  - Grep on `test_v1_5_brown_apples_to_apples.py` after PR #22 applied: 2 `pytest.skip(` matches.
    - Line 113: docstring of `_skip_or_fail` — false positive (just text).
    - Line 124: the sole gated call inside `_skip_or_fail`, properly tagged `# noqa: skip-ban` and gated on `STRICT_ACCEPTANCE` env var.
  - All 5 pre-existing bare `pytest.skip()` sites in `_require_preconditions` and `_require_brown_binary` are migrated to `_skip_or_fail()`.
  - Skip-ban workflow grep allows `_skip_or_fail` and `# noqa: skip-ban` — both legitimate exceptions match the actual code.
  - **No new `@pytest.mark.skipif` decorators or `#[ignore]` Rust attributes added.**
- **Golden-check workflow**: detects golden file changes via filename regex (`test_.*golden|golden.*test|snapshot.*test|expected_.*\.json`), requires `[regen-goldens]` tag in any commit message in the PR delta. Logic is sound.

**Verdict: CLEAN**

**Notes**: All five bare `pytest.skip()` sites in the load-bearing acceptance test are correctly migrated. The sole remaining `pytest.skip()` is inside `_skip_or_fail` itself, properly gated and tagged. No silent-skip hazard introduced. `STRICT_ACCEPTANCE=1` gate is the right contract per `feedback_silent_skip_hazard.md` and `feedback_reframed_gate_masks_bugs.md` — but PR #21's release.yml does NOT set this env var (see PR #21 notes).

---

## Recommended merge order

1. **PR #22 first** — introduces `_skip_or_fail()` helper, marker registration, and the skip-ban/golden-check workflows. Lowest-risk, fully self-contained, CLEAN verdict.
2. **PR #21 second** — release.yml + ship_dry_run.yml. Once PR #22 is in, the release workflow's smoke matrix calls into the migrated acceptance tests. A small follow-up (add `STRICT_ACCEPTANCE: '1'` to the release.yml env block) is recommended but not blocking.
3. **PR #20 last** — cross-platform CI matrix. The 4-of-5 red CI on the PR head is expected friction (first-time clippy/ruff/black baseline + `-k simd` matches nothing on `main`). Merging red is acceptable for v1.8 prep infrastructure, but a follow-up issue should track lint cleanup.

**Rationale**: ordering minimises the window where PR #21's release workflow runs against the un-migrated (pre-#22) acceptance test — the migration is a behaviour-neutral default-skip rewrite, but landing the helper before the workflow that depends on it is the cleaner sequence.

---

## Summary

| PR | Verdict | Files | LOC | Touches kernels? | PII | Hardcoded paths |
|----|---------|-------|-----|------------------|-----|-----------------|
| #20 | SOFT-FLAG | 2 | +92/-0 | No | None | None |
| #21 | SOFT-FLAG | 3 | +184/-0 | No | None | None |
| #22 | CLEAN | 5 | +102/-7 | No | None | None |

**No HARD-FLAGs.** Auto-merge agent is clear to proceed. Two SOFT-FLAGs noted for follow-up: (i) PR #20 first-pass lint baseline + `-k simd` no-tests guard, (ii) PR #21 `STRICT_ACCEPTANCE=1` env var on release.yml to fully activate Guard C in the release pipeline.
