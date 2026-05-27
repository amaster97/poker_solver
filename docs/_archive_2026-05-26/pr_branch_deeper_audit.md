# PR Branch Deeper Audit — leaked-content sweep on `origin/pr-*`

**Date:** 2026-05-23
**Scope:** Every PR branch on `origin` — exhaustive scan for session-narrative
artifacts, PII, secrets, absolute paths, agent / session UUIDs, and stale
top-level docs that escaped the cutover cleanup landed on `origin/main`
(commit `6e12b41`).
**Method:** `git ls-tree -r origin/<branch>` + `git grep` against tracked
content. No working-tree checkouts performed; all reads are read-only against
origin refs.

---

## Summary

| Branch | Files leaked | Severity | Action |
|---|---|---|---|
| `pr-3-hunl-tree` | none | CLEAN | none |
| `pr-3.5-pushfold` | none | CLEAN | none |
| `pr-4-card-abstraction` | none | CLEAN | none |
| `pr-4.5-audit-debt-sweep` | `STATUS.md` | MEDIUM | remove |
| `pr-5-hunl-postflop-solve` | none | CLEAN | none |
| `pr-6-rust-hunl-port` | none | CLEAN | none |
| `pr-7-noambrown-diff` | `STATUS.md` | MEDIUM | remove |
| `pr-10a-ui-mock-first` | `STATUS.md` | MEDIUM | remove |
| `pr-11-library-and-packaging` | `STATUS.md`, `SESSION_END_FINAL.md` | MEDIUM | remove |

**No NEW findings beyond the 4 known leaks.** The deeper sweep confirms the
earlier scan was complete: the contamination is bounded to 4 branches and 5
file objects.

---

## Per-branch detail

### `pr-3-hunl-tree` — CLEAN
- Root .md: `README.md` only.
- No session-pattern files. No `.docx`. No `/Users/ashen` paths. No personal
  emails. No UUIDs. 41 tracked files total.
- Older branch — pre-dates CHANGELOG / CONTRIBUTING introduction. Not a defect.

### `pr-3.5-pushfold` — CLEAN
- Root .md: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`. All allowlisted.
- 51 files. No session artifacts. No PII.

### `pr-4-card-abstraction` — CLEAN
- Root .md: README / CHANGELOG / CONTRIBUTING. 59 files. No findings.

### `pr-4.5-audit-debt-sweep` — MEDIUM
- **Leak:** `STATUS.md` — SHA `222d7aaa024ee3c8bcdf002b07c8c4f23ded0b42`.
- Content: session-status table (PR ship status, integration tip SHAs,
  upcoming-decision matrix, "next-session priorities"). Dated 2026-05-22.
- No PII, no secrets, no absolute paths in content.
- Severity MEDIUM: not actively harmful but reveals internal planning state
  inconsistent with public-channel norms. Identical blob to `pr-10a` STATUS.

### `pr-5-hunl-postflop-solve` — CLEAN
- 66 files. No findings.

### `pr-6-rust-hunl-port` — CLEAN
- 74 files. No findings.

### `pr-7-noambrown-diff` — MEDIUM
- **Leak:** `STATUS.md` — SHA `2f1c1a442a2aa5987c21e72883f55597e16c4bb9`.
- Same shape as pr-4.5 STATUS but earlier snapshot (PR 7 "in flight" not yet
  shipped).
- No PII, no secrets, no absolute paths in content.

### `pr-10a-ui-mock-first` — MEDIUM
- **Leak:** `STATUS.md` — SHA `222d7aaa024ee3c8bcdf002b07c8c4f23ded0b42`
  (byte-identical to pr-4.5 leak).
- No PII, no secrets.

### `pr-11-library-and-packaging` — MEDIUM
- **Leak 1:** `STATUS.md` — SHA `c6be6d69f26d92f207520636bd3ccd707bf0ee5e`.
  Most-detailed of the four: announces "v1.0.0 GA HIT", lists tags,
  decision-awaiting matrix.
- **Leak 2:** `SESSION_END_FINAL.md` — SHA `607f2bf7e7454264e8b8ee9ffb31311a4d6754a7`.
  "Sleep well" sign-off; references internal docs (`SESSION_END_REPORT.md`,
  `wake_up_brief_*.md`, `V1_GA_MILESTONE_HIT.md`) that do **not** exist on
  this branch — purely a narrative artifact.
- No PII, no secrets, no absolute paths.
- `assets/README.md` is legitimate packaging documentation (verified). The
  "email" matches found via regex (`icon_16x16@2x.png` etc.) are filename
  false positives, not real addresses.

---

## Categorical findings

### HIGH severity (PII / secrets / agent IDs / session UUIDs)
**None.** Across all 9 branches:
- 0 occurrences of `/Users/ashen` in any tracked file (md/py/rs/toml/txt).
- 0 occurrences of `ashen26@gsb.columbia.edu`.
- 0 non-allowlisted email addresses (only `noreply@anthropic.com` in
  Co-Authored-By trailers and `amaster1997@gmail.com` as commit author —
  both expected).
- 0 UUIDs / session IDs in tracked content.

### MEDIUM severity (session-narrative files)
5 file objects across 4 branches (table above). All are content-clean of
identity / secrets, but expose internal planning vocabulary and are
inconsistent with the cleanup landed on `origin/main` (`6e12b41`). Remove.

### LOW severity (stale-but-not-misleading docs)
None. The allowlisted root .md files (README / CHANGELOG / CONTRIBUTING) on
each PR branch are appropriate to that PR's scope and are not session
artifacts.

### Office files / lock files
0 `.docx` files. 0 `~$*` Office lock files. 0 `claude_outputs_reference.*`
artifacts on any PR branch.

### `.github/` templates
ISSUE / PR templates present on PR branches that landed after the templates
were added — all legitimate, no concerns.

---

## Recommendation

Run `scripts/cleanup_pr_branches.sh` (paired with this audit) in `--execute`
mode to remove the 5 leaked file objects across the 4 affected branches. Force
push with lease to `origin` and mirror to `backup`. Re-verify with
`git ls-remote origin refs/heads/pr-*` afterwards.
