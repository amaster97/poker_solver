# `poker-solver` CLI shim diagnostic — 2026-05-26

**Symptom:** Running `poker-solver` from any shell (any cwd) produces

```
Traceback (most recent call last):
  File "/Users/ashen/.pyenv/versions/3.13-dev/bin/poker-solver", line 3, in <module>
    from poker_solver.cli import main
ModuleNotFoundError: No module named 'poker_solver'
```

Surfaced by W3.2 smoke (agent `a1e4f66`) and earlier by Agent B's user-doc
verification. Reproduces reliably as of 2026-05-26.

`python -m poker_solver.cli ...` from within
`/Users/ashen/Desktop/poker_solver` works fine. The project's `.venv/bin/poker-solver`
also works fine. Only the **PATH-resolved** `poker-solver` (via pyenv shim) is broken.

---

## Root cause

Two stacked causes; either alone would break the PATH shim:

### Cause 1 — Stale editable-install `.pth` pointing at deleted worktree

`which poker-solver` → `/Users/ashen/.pyenv/shims/poker-solver`
(a `pyenv` shim, `bash`, exec's `pyenv exec poker-solver`).

`pyenv which poker-solver` → `/Users/ashen/.pyenv/versions/3.13-dev/bin/poker-solver`
(installed by `pip install -e` against the **3.13-dev** Python).

The shim's shebang is `#!/Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13`
and its body is `from poker_solver.cli import main`. That Python's
`site-packages` has an editable-install pointer:

```
$ cat /Users/ashen/.pyenv/versions/3.13-dev/lib/python3.13/site-packages/poker_solver.pth
/private/tmp/v1.8-phase3-57404
$ ls /private/tmp/v1.8-phase3-57404
ls: /private/tmp/v1.8-phase3-57404: No such file or directory
```

That `/private/tmp/v1.8-phase3-57404` directory was deleted (it was an
ephemeral worktree from a v1.8 phase-3 burst). The `.pth` is now a
dangling reference — `pip` still believes `poker_solver` is installed
(`pip show poker_solver` reports `Editable project location:
/private/tmp/v1.8-phase3-57404`, version 1.7.0), but the actual source
tree is gone, so `import poker_solver` cannot resolve.

This is exactly Agent B's earlier finding: editable installs done from
short-lived worktrees leave dangling `.pth` files in the host Python.

### Cause 2 — Architecture mismatch (would block even if `.pth` were fixed)

```
$ file /Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13
... Mach-O 64-bit executable x86_64

$ file /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
... Mach-O 64-bit dynamically linked shared library arm64
```

Even if the `.pth` were redirected to `/Users/ashen/Desktop/poker_solver`,
the pure-Python part would import successfully, but
`poker_solver._rust` (the Rust hand evaluator) is an **arm64-only** `.so`
and the 3.13-dev pyenv Python is **x86_64**. The import would `dlopen`-fail
on any code path that touches `_rust` (which is most of the CLI).

`.venv/bin/python` is a universal binary (x86_64 + arm64) and, when invoked
on Apple Silicon, runs as arm64, so it loads the `.so` cleanly. That's why
the `.venv` shim works.

### Why both Pythons "find" `poker_solver` in the user's `pyenv which` check

If you `cd` into `/Users/ashen/Desktop/poker_solver` and run

```
/Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13 -c "import poker_solver; print(poker_solver.__file__)"
```

it prints `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` —
not because the editable install works, but because `python -c` adds the
**current directory** to `sys.path` implicitly. The pyenv-shim
`poker-solver` script is invoked from PATH (not as `-c`), so it does NOT
get the cwd on `sys.path`, and the broken `.pth` is the only resolution
path — which fails. Diagnosing by `cd /` first reproduces the failure
unambiguously.

---

## Workaround for users TODAY

Two equally good options, both already validated:

### Option A — use `.venv` shim explicitly

```bash
~/Desktop/poker_solver/.venv/bin/poker-solver --help        # works
~/Desktop/poker_solver/.venv/bin/poker-solver equity --hero AsAh --villain KsKh
```

### Option B — use `python -m` from project root

```bash
cd ~/Desktop/poker_solver
python -m poker_solver.cli --help                            # works
python -m poker_solver.cli equity ...
```

This works because the `.venv` is auto-activated by the user's shell when
they `cd` into the project directory (per the user's reported workflow),
so `python` resolves to `.venv/bin/python`.

**Recommended for documentation:** Option B is the canonical pattern most
users will use; Option A is the answer for users who want a one-liner that
works from any cwd without activating the `.venv`.

---

## Recommended permanent fix

This is an **environmental** issue, not a code issue. The user's
`/Users/ashen/.pyenv/versions/3.13-dev` Python has a stale editable
install. Two clean paths to fix:

### Option F1 — Uninstall the stale editable install from 3.13-dev (preferred)

```bash
/Users/ashen/.pyenv/versions/3.13-dev/bin/pip uninstall poker_solver
pyenv rehash
```

After this, `which poker-solver` will resolve to (presumably)
`/Users/ashen/.pyenv/shims/poker-solver` only if some OTHER pyenv version
also has it; if not, the shim disappears entirely and the user must invoke
`poker-solver` via the `.venv` (Option A above) or `python -m`
(Option B above). This is fine — there is no good reason to have a
global `poker-solver` on PATH when the project ships its own `.venv`.

**Why this is safe:** it touches only the pyenv-managed 3.13-dev Python's
site-packages (removing a broken entry); it does NOT modify pyenv config,
shell config, or any user-owned dotfile. Reversible at any time by
`pip install -e ~/Desktop/poker_solver` from the same Python.

### Option F2 — Re-install editable from project root in 3.13-dev

```bash
cd /Users/ashen/Desktop/poker_solver
/Users/ashen/.pyenv/versions/3.13-dev/bin/pip install -e .
pyenv rehash
```

This would refresh the `.pth` to point at
`/Users/ashen/Desktop/poker_solver` (live). BUT the architecture mismatch
(Cause 2) would still bite: the Rust `.so` is arm64-only and 3.13-dev is
x86_64. Result: `import poker_solver` would succeed but
`from poker_solver._rust import ...` would fail with a `dlopen` arch error.

**Not recommended** unless the user separately builds an x86_64 `.so` for
3.13-dev, which is more work than F1.

### What I did NOT do (per task constraints)

- DID NOT run `pip install -e` against 3.13-dev — Stage-3 autonomy
  forbids broad pyenv changes
- DID NOT modify `pyproject.toml` or any `entry_points`
- DID `pyenv rehash` (no-op fix — verified it does not help here, since
  the underlying `.pth` is the broken layer, not the shim mapping)

---

## CHANGELOG / release-note recommendation

**Recommend: ADD a v1.8.0 changelog note** under "Known issues" or
"Installation notes". Suggested wording:

> ### Known issue — `poker-solver` PATH shim from stale editable install
>
> If `poker-solver` on PATH fails with
> `ModuleNotFoundError: No module named 'poker_solver'`, the source of the
> shim is likely a `pip install -e` done from a now-deleted temporary
> worktree (common pattern during dev). To fix, either:
>
> - Invoke the project's bundled shim:
>   `./.venv/bin/poker-solver ...` (from project root)
> - Use the module entry point:
>   `python -m poker_solver.cli ...` (with `.venv` activated)
> - Or clean up the stale editable install:
>   `pip uninstall poker_solver` in the broken Python, then
>   `pip install -e .` from the project root.
>
> This affects only PATH-resolved invocations; in-`.venv` use and tests
> are unaffected.

This issue is **not** v1.8.0-regression-induced; it predates the release
boundary (the stale `.pth` references a v1.8-phase3 worktree from a few
days ago). It's a user-environment quirk that surfaced via W3.2 smoke and
Agent B's verification — worth documenting so future users / CI smoke
runs don't lose time on the same wild-goose chase.

---

## Verification summary

| Invocation | Result |
|---|---|
| `poker-solver --help` (PATH, pyenv shim) | **FAIL** — `ModuleNotFoundError` |
| `python -m poker_solver.cli --help` (from project root, `.venv` active) | **PASS** |
| `~/Desktop/poker_solver/.venv/bin/poker-solver --help` | **PASS** |
| `pyenv rehash` then re-test PATH shim | **FAIL** (no change) |

Root cause stack: stale `.pth` → `/private/tmp/v1.8-phase3-57404` (deleted)
+ arch mismatch (x86_64 Python vs arm64 `_rust.so`).

Permanent fix is environmental (Option F1 above); recommended action for
v1.8.0 is a CHANGELOG note pointing users at the two working invocations.
