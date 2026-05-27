# Pytest pyenv arch-mismatch quirk — diagnosis (2026-05-23)

## TL;DR

The shell's `pytest` is a pyenv shim that resolves to a **x86_64-only Python**
(`/Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13`), while the locally
built `poker_solver/_rust.cpython-313-darwin.so` is **arm64-only**. Loading the
.so under that Python raises `ImportError: incompatible architecture (have
'arm64', need 'x86_64')`. The host is an Apple M4 Pro (native arm64) and a
universal `python3.13` exists at `/Library/Frameworks/Python.framework/Versions/3.13/`
that imports the .so and runs the tests cleanly.

Pre-existing environment quirk — not a v1.4.3 regression.

## Reproduction (shared tree, native arm64 shell)

Host:
- `arch` → `arm64`
- `uname -m` → `arm64`
- CPU: Apple M4 Pro

Trigger (passes collection, fails on test setup when fixtures import `_rust`):

```
$ cd /Users/ashen/Desktop/poker_solver
$ pytest tests/test_dcfr_diff.py::test_kuhn_python_rust_infoset_keys_match
...
ImportError: dlopen(/Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so, 0x0002):
  tried: '.../poker_solver/_rust.cpython-313-darwin.so' (mach-o file, but is an
  incompatible architecture (have 'arm64', need 'x86_64')), ...
poker_solver/solver.py:607: ImportError
```

Note: `pytest --collect-only` succeeds because collection imports
`tests/test_dcfr_diff.py` but does not yet enter the `both_results` fixture
that calls `_solve_rust(...)`. The user's executor saw the error on collection
only when a different test path forced the import at import-time.

## Environment inventory

| Path                                                            | Arch                  | Has pytest? |
|-----------------------------------------------------------------|-----------------------|-------------|
| `/Users/ashen/.pyenv/shims/pytest` (bash wrapper, on PATH)      | dispatches to below   | n/a         |
| `/Users/ashen/.pyenv/versions/3.13-dev/bin/python3.13` (active) | **x86_64-only**       | yes (9.0.2) |
| `/Users/ashen/.pyenv/versions/3.11.6/bin/python3.11`            | x86_64-only           | unknown     |
| `/usr/local/bin/python3.13` (python.org universal2)             | universal (arm64+x64) | yes (9.0.3) |
| `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13` (same install) | universal | yes (9.0.3) |
| `poker_solver/_rust.cpython-313-darwin.so`                      | **arm64-only**        | n/a         |

`pyenv version` reports `3.13-dev (set by /Users/ashen/.pyenv/version)`.
`PYENV_VERSION` is unset; pyenv resolves the active interpreter from
`~/.pyenv/version`, so even `arch -arm64 pytest` won't help: the shim's bash
wrapper re-execs the already-x86_64 binary, which has no arm64 slice.

`pyproject.toml` documents the canonical fix at the build layer (comment on
`[tool.maturin]`):

```
# macOS distribution builds MUST target universal2 (arm64 + x86_64 lipo'd)
# so the .so works under both Apple Silicon native Python and x86_64 Python
# (e.g., pyenv-managed; Rosetta). ... developers and CI must pass:
#     maturin {build,develop} --release --target universal2-apple-darwin
```

The current shared-tree `.so` is single-arch arm64 (likely produced by a
recent local `maturin develop` without `--target universal2-apple-darwin`).

## Root cause (one-liner)

`pytest` resolves through a pyenv shim to an x86_64-only Python 3.13-dev,
while the locally built `_rust.*.so` is arm64-only — incompatible arch slices
collide at dlopen time.

## Verified-clean alternative

```
$ /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m pytest \
    /Users/ashen/Desktop/poker_solver/tests/test_dcfr_diff.py::test_kuhn_python_rust_infoset_keys_match \
    --tb=no -q
.                                                                        [100%]
1 passed in 2.56s
```

That Python is arm64-native and matches the .so.

## Fix paths

### Option A — Rebuild .so as universal2 (`maturin develop --release --target universal2-apple-darwin`)

- Pros: matches the documented build contract in `pyproject.toml`; fixes the
  problem for *all* Python interpreters on this machine including the
  x86_64-only pyenv install; aligns shared tree with what the .dmg expects;
  catches a real regression in the local build hygiene.
- Cons: ~3-5 min rebuild; requires `rustup target add x86_64-apple-darwin
  aarch64-apple-darwin` (one-time, may already be installed); touches
  `poker_solver/_rust.cpython-313-darwin.so` (a tracked-but-build-artifact
  file — confirm it isn't pinned by an in-flight agent).

### Option B — Point pytest at the arm64-native python.org Python

Run `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m
pytest ...` instead of bare `pytest`. Or `pyenv shell system` then call
pytest via the system arm64 install. Or alias `pytest` in shell rc.

- Pros: zero rebuild; no file modifications; verified working above.
- Cons: doesn't fix the pyenv 3.13-dev install (still x86_64 on an arm64
  host — a latent foot-gun); every developer invocation must remember to
  use the right interpreter; ship-test scripts that hard-call `pytest` are
  still broken.

### Option C — `ARCHFLAGS="-arch arm64"` in shell env

Irrelevant here. `ARCHFLAGS` affects compile/link of new extensions during
`pip install`; it does **not** change which Python interpreter the shim
launches and cannot retroactively give an x86_64 binary an arm64 slice.

### Option D — Reinstall pyenv 3.13-dev under arm64

`pyenv uninstall 3.13-dev && arch -arm64 pyenv install 3.13-dev` (or pin
to `3.13.1` since `3.13-dev` is now stale anyway).

- Pros: fixes pyenv itself; future `pytest`/`python` from the shim work
  without ceremony.
- Cons: 5-10 min Python rebuild; loses whatever site-packages are currently
  in the 3.13-dev prefix (would need `pip freeze` + reinstall); doesn't
  fix the single-arch .so on its own — if the .so were later x86_64-only
  on an arm64 Python, we'd be back here from the other side.

## Recommendation

**Option A (rebuild .so as universal2).**

Rationale:
1. It is the contract documented in `pyproject.toml` — distribution builds
   *must* be universal2. The current single-arch arm64 .so violates that
   contract and would also fail in CI / .dmg packaging
   (`scripts/build_macos_dmg.sh rejects single-arch .so files at pre-flight`).
2. It fixes the actual root inconsistency (build artifact mismatch),
   not just a workaround for one developer's shell.
3. Once rebuilt, both interpreters work — pyenv shim → x86_64 Python →
   `_rust` (x86_64 slice) loads; python.org universal → arm64 Python →
   `_rust` (arm64 slice) loads.
4. Option B is acceptable as a stopgap until rebuild lands; Option D is
   the right *long-term* hygiene (kill the x86_64 pyenv install on an
   arm64 Mac) but is out of scope for this immediate fix.

Concrete fix command (orchestrator to apply):

```
cd /Users/ashen/Desktop/poker_solver
# Verify rust targets installed (one-time):
rustup target list --installed | grep -E 'x86_64-apple-darwin|aarch64-apple-darwin'
# Rebuild as universal2:
maturin develop --release --target universal2-apple-darwin
```

## Verification command (after applying Option A)

```
# 1. Confirm .so is now universal2:
lipo -info /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so
# Expected: "Architectures in the fat file: ... are: x86_64 arm64"

# 2. Run the failing test through the pyenv shim (the original failure mode):
cd /Users/ashen/Desktop/poker_solver
pytest tests/test_dcfr_diff.py -v
# Expected: 5 passed

# 3. Sanity-check that the arm64 path still works:
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m pytest \
  tests/test_dcfr_diff.py -v
# Expected: 5 passed
```

## Risk to in-flight agents

Option A touches `poker_solver/_rust.cpython-313-darwin.so` in the shared
tree. Per memory and the task brief:

- **PR 23 audit**: doesn't run Rust tests → unaffected.
- **Integration sync agent**: doesn't run Rust tests, only does git
  branch/file operations → unaffected unless the .so is staged/committed.
  Confirm `_rust*.so` is `.gitignore`d (it should be; build artifact).
- **DCFR perf bisect**: uses its own `git worktree` and rebuilds its own
  .so per Hard Rule "no concurrent branch ops" → unaffected.
- **Any agent currently importing `_rust` from the shared tree**: would
  briefly see ImportError mid-rebuild as the .so is replaced. Risk
  window is single-digit seconds (atomic mv after maturin link). If any
  long-lived process has already imported `_rust`, it keeps the old
  mmap'd image — no impact.

Net risk: low. Recommend a quick `ps`/agent inventory before kicking the
rebuild; if no agent is hot-importing `_rust`, fire it.

## Notes / open questions for orchestrator

1. The executor report said "Direct `python -c \"import poker_solver._rust\"`
   succeeds." That is correct *because* bare `python` on this PATH resolves
   to `/usr/local/bin/python` (universal2), not the pyenv shim. So the .so
   is arm64-correct; the failing chain is specifically pyenv-shim →
   x86_64-only Python.
2. `pyenv 3.13-dev` being x86_64 on an arm64 host is itself a latent
   hazard. Worth a follow-up cleanup (Option D) after the immediate
   ship pressure subsides; not blocking.
3. `pyproject.toml` already encodes the universal2 invariant in a comment.
   Consider a pre-commit hook or a `tox`/`nox` wrapper that fails fast
   if `lipo -info poker_solver/_rust*.so` shows only one architecture —
   would have caught this before it bit v1.4.3 ship.
