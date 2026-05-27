# PR Final Polish Re-audit — 2026-05-23

Independent read-only review of the 3 open PRs for typos, broken markdown, and factual inaccuracies that a reviewer might notice.

## Scope

- PR #2: `pr-48-usage-v1-7-0-semantics` — `docs(usage): v1.7.0 aggregator-vs-Nash + class-label semantics`
- PR #3: `pr-44-dmg-packaging-fix` — `fix(packaging): v1.4.0 .dmg nicegui bundle + arch + version`
- PR #4: `pr-49-readme-broken-ref-cleanup` — `docs(readme): fix broken cross-ref to internal-only smoke doc`

## Methodology

For each PR:
1. Pulled title + body via `gh pr view <N> --json title,body`
2. Verified title format (length ≤70 chars, active voice, `type(scope):` prefix)
3. Scanned body for markdown breakage (unbalanced backticks, dangling code fences)
4. Spell-checked + grammar-checked
5. Verified factual claims (file:line refs, section anchors) against the PR branch state on `origin`
6. Verified link targets exist on `origin/main` (where the PR will land)

---

## PR #2 — `pr-48-usage-v1-7-0-semantics`

### Title
`docs(usage): v1.7.0 aggregator-vs-Nash + class-label semantics` (62 chars, active voice, scope prefix)
- **No issues.**

### Body claim verification

| Claim | Status |
|-------|--------|
| `USAGE.md §5.6` exists post-PR | OK (USAGE.md:482 `### 5.6 Aggregator vs. true-Nash range-vs-range (v1.7.0+)`) |
| `USAGE.md §7a` is rewritten as "Ergonomic subcommands (v1.7.0+)" | OK (USAGE.md:640 matches) |
| CLI subcommand line refs: `pushfold:581, river:643, parity:781` | OK (on PR branch: `_cmd_pushfold:581`, `_cmd_river:643`, `_cmd_parity:781`) |
| `solve_range_vs_range_nash` is a pure class-mean projection (max delta `0.00000000`) | Plausible; framed defensively. Diff-test history is real (PR 6). Not verifiable from PR metadata alone. |
| Markdown rendering | Clean. 26 backticks (balanced even count). No orphan tags. |

### Issues found
- **None (HIGH or LOW).**

### Edits applied
- **None.**

---

## PR #3 — `pr-44-dmg-packaging-fix`

### Title
`fix(packaging): v1.4.0 .dmg nicegui bundle + arch + version` (59 chars, active voice, scope prefix)
- **No issues.**

### Body claim verification

| Claim | Status |
|-------|--------|
| `pyproject.toml [distribution]` includes `nicegui>=3.0,<4.0` | OK (`pyproject.toml:30` matches: `distribution = ["pyinstaller>=6.0", "nicegui>=3.0,<4.0"]`) |
| `collect_all` widened to `nicegui + fastapi + uvicorn + starlette + socketio + engineio` | OK (`scripts/poker_solver.spec:60` iterates exactly that 6-pkg tuple) |
| Dynamic `APP_VERSION` from `poker_solver/__init__.py::__version__`, replaces `version="0.6.0"` | OK (spec.py:42-45, comment confirms previous hardcode) |
| `target_arch="arm64"` retained | OK (spec.py:131) |
| `DMG_NAME` renamed `-universal2.dmg` → `-arm64.dmg` | OK (`build_macos_dmg.sh:123`) |
| Pre-flight `python -c "import nicegui"` check | OK (`build_macos_dmg.sh:154`) |
| .dmg size 14 MB → 45 MB (3.2x growth) | Corroborated in `docs/STATUS_2026-05-23_v1_7_0_shipped.md`, `docs/pr44_dmg_fix_spec.md` |
| Markdown rendering | Clean. 60 backticks (balanced). `\$99/year` properly escaped. |

### Issues found
- **None (HIGH or LOW).**

### Edits applied
- **None.**

---

## PR #4 — `pr-49-readme-broken-ref-cleanup`

### Title
`docs(readme): fix broken cross-ref to internal-only smoke doc` (61 chars, active voice, scope prefix)

### Body claim verification

| Claim | Status |
|-------|--------|
| Stale link to `docs/dmg_v1_4_0_smoke_verification.md` (internal-only) removed from README | OK (diff confirms) |
| Replaced with pointer to `docs/dmg_install_guide.md` | OK (exists on `origin/main`) |
| Second broken ref to `docs/v1_6_1_dryrun_verification.md` also removed | OK (diff confirms) |
| Markdown rendering | Clean (no code blocks; plain prose). |

### Issues found
- **LOW (1)**: Title says "smoke doc" (singular) and "cross-ref" (singular), but body documents removal of **two** broken refs (smoke doc + dryrun verification doc). The title's focus on the most prominent fix is defensible — but slightly imprecise. A more accurate title would be e.g. `docs(readme): remove broken cross-refs to internal-only verification docs` (the commit message on the branch already says this).

### Edits applied
- **None** (LOW severity; user can decide whether to retitle in the merge UI; the body fully discloses the second ref).

---

## Aggregate

| Severity | Count | Fixed | Left for user |
|----------|-------|-------|---------------|
| HIGH | 0 | 0 | 0 |
| LOW | 1 | 0 | 1 |

**Total issues: 1 (LOW).**

### LOW issues left for user

1. PR #4 title under-counts the fix scope (says singular "cross-ref" / "smoke doc", body discloses 2 refs cleaned up). Defensible as-is; user can retitle to e.g. `docs(readme): remove broken cross-refs to internal-only verification docs` if they want title↔body to match the commit-msg phrasing exactly.

## Verdict

**POLISHED with one cosmetic LOW remaining on PR #4 title.**

All file:line refs, section anchors, link targets, and markdown rendering verified clean. No HIGH-severity issues. No edits applied.
