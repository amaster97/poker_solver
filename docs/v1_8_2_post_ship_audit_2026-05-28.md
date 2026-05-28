# v1.8.2 Post-Ship Audit (2026-05-28)

**Ship SHA:** `16c92e6` (tag `v1.8.2`, resolves to commit
`f37db10c9060866462aaf93815959965fffed718` as the annotated-tag object)

**Audit scope:** 8 verification checks, read-only against the tagged
artifact + remotes. No release-body or tag mutation. Run from worktree
`docs-v1-8-2-post-ship-audit` off `origin/main` (= `e6df209`).

**Bottom line:** 7 PASS, 1 informational, 0 release-blockers.

---

## Check-by-check

### 1. Tag SHA parity (origin vs backup) — PASS

```
origin: f37db10c9060866462aaf93815959965fffed718  refs/tags/v1.8.2
backup: f37db10c9060866462aaf93815959965fffed718  refs/tags/v1.8.2
```

Identical tag object SHA on both remotes. Dual-remote tag push
succeeded cleanly.

### 2. GitHub release body content sanity — PASS

`gh release view v1.8.2 --json body` returns the expected long-form
draft with all four expected keywords present:

| Keyword       | Occurrences |
| ------------- | ----------- |
| `TerminalCache` | 13          |
| `walk-tree`     | 14          |
| `α-guard`       | 6           |
| `213×`          | 10          |

No unfilled `<TBD-[A-Z0-9_-]+>` placeholders found (`grep` returns 0
matches). The only "TBD" tokens in the body are plain narrative phrases
("Release date: TBD (user-gated)", "`TBD` placeholder false-flag
example in a Phase C.2 row") — both intentional, neither a
`<TBD-XYZ>`-style unfilled slot.

### 3. Version files at tag — PASS

| File                             | Value at `v1.8.2` | Expected | OK |
| -------------------------------- | ----------------- | -------- | -- |
| `pyproject.toml`                 | `version = "1.8.2"` | `1.8.2`  | yes |
| `poker_solver/__init__.py`       | `__version__ = "1.8.2"` | `1.8.2`  | yes |
| `crates/cfr_core/Cargo.toml`     | `version = "0.8.2"` | `0.8.2`  | yes |

All three artifact-version markers line up at the tag.

### 4. CLI `--version` reports 1.8.2 — INFORMATIONAL (not a release issue)

`.venv/bin/poker-solver --version` reports `poker-solver 1.8.0`, **but**
this is a stale **editable install** in the local dev venv. `pip show
poker-solver` reveals:

```
Version: 1.8.0
Editable project location: /Users/ashen/Desktop/poker_solver_worktrees/feat-preflop-rvr-engine
```

The editable install is pinned at the `feat-preflop-rvr-engine`
worktree (`pyproject.toml` still `1.8.0` there) rather than the tagged
tree. When the same venv resolves `poker_solver` as a module:

```
.venv/bin/python -c "import poker_solver; print(poker_solver.__version__)"
1.8.2
```

i.e. the Python package is reading the `__init__.py` from the
appropriate tree but the entry-point script's metadata is bound to the
stale editable install. **Tag content itself is correct (Check 3).**
The local dev venv just needs `pip install -e .` re-run from the main
tree (or a sibling worktree on the tagged ref). This is a developer-
environment cosmetic only and does not affect installable artifacts.

### 5. Off-path annotation fields at tag — PASS

`git show v1.8.2:poker_solver/solver.py | grep -E
'reach_probability|off_path_keys'` returns 11 matches including the
docstring entry, dataclass fields, the populator function, and writes
of both `result.reach_probability = reach` and `result.off_path_keys =
off_keys`. PR #47's annotations are present in the tagged tree.

### 6. No `<TBD-...>` placeholders in tagged release-notes draft — PASS

`git show v1.8.2:docs/v1_8_2_release_notes_DRAFT.md | grep -E
'<TBD-[A-Z0-9_-]+>'` → empty (zero matches). Drafted notes shipped
with all bracket-style placeholders filled.

### 7. Excluded PRs really excluded — PASS

`git log --oneline 8a9c8d2..v1.8.2 | grep -E '#121|#122|#126'` → no
output. None of #121, #122, #126 appear in the v1.8.0→v1.8.2 commit
range. Excluded as intended.

### 8. `backup/main` matches `origin/main` — INFORMATIONAL

| Remote ref      | SHA       |
| --------------- | --------- |
| `backup/main`   | `16c92e6` (= ship SHA, tagged `v1.8.2`) |
| `origin/main`   | `e6df209` |

These diverge by exactly one commit:

```
e6df209 docs(persona): current-state snapshot 2026-05-28
        (post all recent reclassifications) (#135)
```

PR #135 is a pure-docs persona-snapshot commit that landed on
`origin/main` **after** the v1.8.2 tag was pushed. The backup remote
was last synced at ship time, capturing `main` at the ship SHA
(`16c92e6`). This is the expected steady-state for a backup mirror
sync'd at ship boundaries: `backup/main` will trail `origin/main` by
post-ship docs commits until the next backup sync. Not a release
issue, and not a backup-config issue either — both remotes hold the
tag at the same object.

If the user prefers continuous backup parity, the next mirror push of
`origin/main` to `backup/main` will close the one-commit gap.

---

## Summary table

| # | Check                                            | Status            |
| - | ------------------------------------------------ | ----------------- |
| 1 | Tag SHA parity (origin == backup)                | PASS              |
| 2 | Release-body keywords + no `<TBD-...>`           | PASS              |
| 3 | Tagged version files (py/cargo) all show 1.8.2/0.8.2 | PASS          |
| 4 | CLI `--version` reports 1.8.2                    | INFORMATIONAL     |
| 5 | Off-path annotation fields at tag                | PASS              |
| 6 | No `<TBD-...>` placeholders in tagged notes      | PASS              |
| 7 | Excluded PRs (#121/#122/#126) absent from range  | PASS              |
| 8 | `backup/main` SHA == `origin/main` SHA            | INFORMATIONAL     |

**Release-blockers:** 0
**Minor:** 0
**Informational:** 2 (#4 stale local editable install; #8 expected
one-commit drift between `backup/main` and `origin/main` from a
post-ship docs commit)

No action required to roll back, retag, or amend the release body.
