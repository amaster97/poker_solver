# .venv Shadow Audit — 2026-05-23

## TL;DR

**Verdict: NO-SHADOW (with metadata staleness)**

The retest watchdog's shadow concern is **not real for import resolution**. The maturin build into `.venv` registered an **editable** install pointing at `/private/tmp/w23-retest-scaled` — a worktree that no longer exists. Python's import machinery silently falls back to the cwd source (`/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` at v1.6.0). However, the `dist-info` metadata still **claims** v1.7.0, which can mislead version-sniffing tools (`pip show`, `importlib.metadata.version`).

## 1. Shared tree state

- Branch: **`main`**
- HEAD: **`ca8c7af`** — "docs: bump README version reference v1.5.1 → v1.6.0"
- Status: behind `origin/main` by 6 commits, can be fast-forwarded
- Working tree: USAGE.md modified, many untracked docs/ files (planning artifacts)
- Source `__version__`: **v1.6.0**

The shared tree is NOT at origin/main's v1.7.0 — it's 6 commits behind. So the watchdog's framing of "main-tree v1.6.0 source" is accurate for the local working copy.

## 2. .venv state

- Python: 3.13
- Install marker: **editable** (`Editable project location: /private/tmp/w23-retest-scaled`)
- Recorded version: **v1.7.0** (in `poker_solver-1.7.0.dist-info/METADATA`)
- Files installed:
  - `poker_solver.pth` — contains the single line `/private/tmp/w23-retest-scaled`
  - `poker_solver-1.7.0.dist-info/` — METADATA, RECORD, direct_url.json (`{"editable": true, "url": "file:///private/tmp/w23-retest-scaled"}`)
  - `../../../bin/poker-solver` — entry-point shim
- **No copied source files** under site-packages (no `poker_solver/` package directory, no `_rust*.so`)

The pointed-to worktree `/private/tmp/w23-retest-scaled` **does not exist** (`ls` returns "No such file or directory"). The `.pth` redirect is broken.

## 3. Import resolution test

```
.venv/bin/python -c "import poker_solver; print(poker_solver.__version__); print(poker_solver.__file__)"
VERSION: 1.6.0
FILE: /Users/ashen/Desktop/poker_solver/poker_solver/__init__.py

python -c "import poker_solver; print(poker_solver.__version__); print(poker_solver.__file__)"
VERSION: 1.6.0
FILE: /Users/ashen/Desktop/poker_solver/poker_solver/__init__.py
```

Both interpreters resolve to the shared-tree source at v1.6.0. The broken `.pth` does not block import; Python's path-finder skips the dead path and proceeds to the next candidate (cwd, which is the shared tree).

## 4. Shadow diagnosis

The classic shadow scenario requires:
1. Source at version X under cwd
2. Installed copy at version Y ≠ X under site-packages
3. Import picks up Y

**Condition 2 is not met**: no source files exist in site-packages — only the `.pth` pointer and dist-info metadata. The editable install was always "transparent" by design (`.pth` → live source tree). Now that the target is missing, the redirect is a no-op.

**However**, there is a secondary issue: `pip show poker_solver` reports v1.7.0 and `importlib.metadata.version('poker_solver')` will too (these read dist-info, not `__version__`). Any tooling that uses package metadata as the source of truth would observe v1.7.0 while the runtime code is v1.6.0. This is a metadata-vs-runtime drift, not an import shadow.

## 5. Stale /tmp venvs

`find /tmp /private/tmp -maxdepth 4 -type d -name ".venv"` and `find /tmp /private/tmp -maxdepth 5 -name "poker_solver-*.dist-info"` both returned empty. The `/private/tmp/w23-retest-scaled` worktree (and its venv) was already cleaned up; only the dangling .pth pointer in the shared `.venv` remains.

## 6. Recommended action

**Priority: LOW** — the broken `.pth` is currently inert (no shadowing). Two options:

- **Option A (recommended, conservative)**: `.venv/bin/pip uninstall poker_solver` to remove the stale metadata + broken `.pth`. Restores clean no-install state; `import poker_solver` continues to work via cwd. Eliminates pip-show v1.7.0 lie.
- **Option B (active dev)**: `.venv/bin/pip install -e /Users/ashen/Desktop/poker_solver` to repoint the editable install at the shared tree. Metadata would still report v1.7.0 until `pyproject.toml`/`Cargo.toml` version bumps land (and shared tree is at v1.6.0, so the metadata would correctly read v1.6.0 if reinstalled from this tree).
- **Option C (no-op)**: Leave as-is. Safe for `import poker_solver` workflows but `pip show` / `importlib.metadata` will lie.

Since the shared tree is 6 commits behind origin and a `git pull --ff-only` is pending anyway, the natural next step is: fast-forward main → reinstall editable from shared tree → metadata + runtime aligned.

**READ-ONLY constraint honored**: no modifications made during this audit.
