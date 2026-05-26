# .dmg LAST Build Runbook

Built on: 2026-05-26 (overnight session)
For version: **1.7.0** (read from `pyproject.toml`)
Target arch: **arm64 only** (universal2 claim removed per PR #47, but see WARNING below)
HEAD commit at prep: `f165eb8` (origin/main clean, ahead 0 / behind 0)

---

## Pre-build sanity (PASS = ready, WARN = action required)

- [x] **PR #42 freeze_support fix:** PASS
  - `scripts/pyinstaller_entry.py:26` has `mp.freeze_support()` at module level
  - Verified by: `grep -A 2 'freeze_support' scripts/pyinstaller_entry.py` -> outputs `mp.freeze_support()`
  - Commit: `728206e fix(dmg): add multiprocessing.freeze_support() to PyInstaller entry + warn users (#42)`

- [x] **PR #47 spec hardening:** PASS
  - `scripts/poker_solver.spec:51` reads version from `pyproject.toml` via regex `(?m)^version\s*=\s*[\'"]([^\'"]+)[\'"]`
  - Spec also performs drift check against `poker_solver/__init__.py __version__` (lines 66-72)
  - `scripts/build_macos_dmg.sh:113-118` also reads version from `pyproject.toml`
  - **Step 5.5** (build script lines 295-353) implements PR #47 post-sign verification:
    - (a) `lipo -info` on `Contents/MacOS/Poker Solver` -> must report arm64
    - (b) `defaults read .../Info.plist CFBundleShortVersionString` -> must equal `APP_VERSION`
    - (c) `defaults read .../Info.plist CFBundleVersion` -> must equal `APP_VERSION`
    - (d) `codesign --verify --deep --strict` on the .app -> must succeed (skipped only when `--skip-signing`)
  - Commit: `5ead08f fix(dmg): arch label + version stamp accuracy (post-fork-bomb-fix follow-up) (#47)`

- [x] **All v1.8 SIMD phases on main:** PASS
  - Phase 1: `485aa8c PR 61: v1.8 Phase 1 — cross-platform SIMD discount kernel (#23)`
  - Phase 2: `8073bcc PR 63b: v1.8 Phase 2 — update_regret_sum SIMD (replaces auto-closed #26) (#41)`
  - Phase 3: `a712950 feat(cfr_core): v1.8 Phase 3 — update_strategy_sum SIMD (#33)`
  - Phase 4: `77e751c feat(cfr_core): v1.8 Phase 4 — compute_strategy SIMD (#32)`
  - AVX2: `db8d646 PR 68: v1.8 — AVX2 runtime-detect path for x86_64 hosts (#35)`
  - All 5 commits reachable from HEAD via `git log --oneline | grep -E '(Phase [1-4]|AVX2)'`

- [x] **Version sync:** PASS (Python tree)
  - `pyproject.toml` `[project] version = "1.7.0"`
  - `poker_solver/__init__.py:196` `__version__ = "1.7.0"`
  - `crates/cfr_core/Cargo.toml:3` `version = "0.7.0"` (Rust crate version is NOT required to match the Python distribution version; it's an independent SemVer track per Rust convention. The spec drift check (spec lines 66-72) only compares pyproject vs __init__.)

- [x] **maturin available:** PASS — `maturin 1.13.3` at `/Users/ashen/.pyenv/shims/maturin`

- [x] **rustc + cargo available:** PASS
  - `rustc 1.95.0 (59807616e 2026-04-14)`
  - `cargo 1.95.0 (f2d3ce0bd 2026-03-21)`
  - Both at `~/.cargo/bin/{rustc,cargo}` (NOT on default `$PATH` in fresh shells — see "Shell prep" below)
  - Targets installed: `aarch64-apple-darwin`, `x86_64-apple-darwin` (both required for `universal2-apple-darwin`)

- [x] **Python toolchain available:** PASS
  - `python 3.13.1` (matches spec's `cpython-313` requirement)
  - `PyInstaller 6.20.0`
  - `nicegui 3.12.1` importable
  - `poker_solver 1.7.0` importable

- [x] **create-dmg available:** PASS — `create-dmg 1.2.3` at `/usr/local/bin/create-dmg`

- [x] **build_macos_dmg.sh syntax clean:** PASS — `bash -n scripts/build_macos_dmg.sh` exits 0

- [x] **Build artifacts present:** PASS
  - `scripts/build_macos_dmg.sh` (21178 bytes, exec)
  - `scripts/poker_solver.spec` (7794 bytes)
  - `scripts/entitlements.plist` (1618 bytes)
  - `scripts/sign_and_notarize.py` (12306 bytes)

---

## WARNINGS / pre-build actions required

### WARN 1: `_rust.so` arch mismatch — REBUILD REQUIRED

The build script's preflight (Step 1, lines 175-190) **requires** `poker_solver/_rust.cpython-313-darwin.so` to be a `universal2` Mach-O (arm64 + x86_64 slices). The current `.so` in the source tree is **arm64-only**:

```
$ file poker_solver/_rust.cpython-313-darwin.so
poker_solver/_rust.cpython-313-darwin.so: Mach-O 64-bit dynamically linked shared library arm64
```

If you run `sh scripts/build_macos_dmg.sh` as-is, Step 1 will FAIL with:
```
$RUST_SO is single-arch:
  Mach-O 64-bit dynamically linked shared library arm64
Rebuild with: maturin develop --release --target universal2-apple-darwin
```

**Rationale for the universal2 requirement (per spec lines 161-166):** the spec file makes the `.app` itself arm64-only (`target_arch="arm64"`), but the source-tree `.so` is universal2 so x86_64 Python users doing `pip install -e .` can still import. The preflight enforces the source-tree universal2 invariant separately from the .app's arm64 stamp.

**Fix:** before running the build, run:
```bash
cd /Users/ashen/Desktop/poker_solver
maturin develop --release --target universal2-apple-darwin
file poker_solver/_rust.cpython-313-darwin.so   # expect: universal binary with 2 architectures: arm64, x86_64
```
Both rust targets are already installed (`aarch64-apple-darwin`, `x86_64-apple-darwin`), so this should just work.

### WARN 2: No code-signing identity, no Apple notarize credentials

`security find-identity -v -p codesigning` returns `0 valid identities found`. Environment vars `APPLE_ID`, `TEAM_ID`, `APP_SPECIFIC_PASSWORD` are NOT set.

If you run the build with default flags, Step 1 preflight (lines 204-208) will FAIL with:
```
Notarization requires APPLE_ID + TEAM_ID + APP_SPECIFIC_PASSWORD (env or flags).
Use --skip-notarization to build unsigned.
```

The existing v1.6.0 .dmg shipped with `Signature=adhoc` (verified via `codesign -dvv`), so the established pattern is ad-hoc + skip-notarize. **Recommended:** pass `--skip-notarization`, and either pass `--skip-signing` (no signature at all) or `--identity "-"` (ad-hoc, matches v1.6.0 precedent).

---

## Shell prep (run once in the build terminal)

`rustup`/`cargo` is not on the default `$PATH`. Source the cargo env first:
```bash
. "$HOME/.cargo/env"
rustc --version    # confirm: rustc 1.95.0 ...
```

---

## Build command (paste this into Terminal)

**Recommended (ad-hoc signed, no notarize) — matches v1.6.0 pattern:**
```bash
cd /Users/ashen/Desktop/poker_solver
. "$HOME/.cargo/env"
maturin develop --release --target universal2-apple-darwin
TS=$(date +%Y%m%d_%H%M%S)
sh scripts/build_macos_dmg.sh \
    --identity "-" \
    --skip-notarization \
    2>&1 | tee /tmp/dmg_build_${TS}.log
```

**Alternative (fully unsigned, fastest):**
```bash
cd /Users/ashen/Desktop/poker_solver
. "$HOME/.cargo/env"
maturin develop --release --target universal2-apple-darwin
TS=$(date +%Y%m%d_%H%M%S)
sh scripts/build_macos_dmg.sh \
    --skip-signing \
    --skip-notarization \
    2>&1 | tee /tmp/dmg_build_${TS}.log
```

Notes:
- `maturin develop` step is the workaround for WARN 1 above. It takes ~30-60s and only needs to run once (subsequent runs reuse cached cargo artifacts).
- `--skip-signing` skips Step 5 (sign) AND Step 9 (sign DMG); the Step 5.5 codesign-verify will be skipped too (the script gates it on signing being on — see line 336 `[[ $SKIP_SIGNING -eq 1 ]]`).
- Adding `--identity "-"` keeps the inside-out ad-hoc walk and Step 5.5 verify path active (recommended; produces a more realistic build).

Expected duration: 5-10 min on M-series (PyInstaller dominates).

---

## Post-build verification (automatic)

The script's Step 5.5 (per PR #47) auto-verifies on every signed build:
- `lipo -info Contents/MacOS/Poker Solver` -> must include `arm64`
- `defaults read Info.plist CFBundleShortVersionString` -> must equal `1.7.0`
- `defaults read Info.plist CFBundleVersion` -> must equal `1.7.0`
- `codesign --verify --deep --strict` -> must exit 0

Step 4 (`/11` banner) also runs an **in-bundle import smoke test** that imports `poker_solver._rust` from inside the freshly built `.app` before signing. If the bundle's _rust.so is missing or broken, the build fails there with `[smoke] FAIL: cannot import poker_solver._rust`.

If `--skip-signing` is passed, Step 5.5 is largely bypassed (only the lipo arch + plist version checks run; codesign verify is skipped). For the recommended `--identity "-"` flow, ALL of Step 5.5 runs.

---

## After build — inspect, do NOT launch

**DO:**
- Confirm `/Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.7.0-arm64.dmg` exists and is non-trivial size (expect ~45-50 MB based on v1.6.0 = 47 MB).
- Confirm `dist/Poker Solver.app/` was built (inside-the-DMG copy of the .app).
- Run the **terminal smoke test** (bypasses NiceGUI, just imports the Rust ext) — there are two ways:

  **Option A (from staged .app, no mount):**
  ```bash
  "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test
  ```

  **Option B (from mounted DMG — requires the user to attach the DMG via `hdiutil`):**
  ```bash
  hdiutil attach "/Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.7.0-arm64.dmg" -nobrowse
  "/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test
  hdiutil detach "/Volumes/Poker Solver"
  ```

  Expected output (per `scripts/pyinstaller_entry.py:38-46`):
  ```
  [smoke] poker_solver._rust imported OK: <module 'poker_solver._rust' from '...'>
  [smoke] _rust public symbols: N found
  ```

**DO NOT:**
- DO NOT double-click the .dmg or launch the .app via Finder yet — full launch is gated on user OK (this is what crashed the Mac before; per `feedback_dotso_arch_check` and the fork-bomb that PR #42 fixed).
- DO NOT `git push` the .dmg or attach it to a GitHub release without user confirmation.
- DO NOT modify any source files; this runbook is read-only verification.

---

## Quick rollback if anything looks wrong

If the build fails or produces unexpected output:
1. Capture the full log: `/tmp/dmg_build_<TS>.log`
2. The build script always cleans `build/` + `dist/` at Step 2, so a failed build leaves no half-baked artifacts on origin/main.
3. Source tree is untouched (no source modifications happen during build).
4. Report log path + last 50 lines to user; do not re-run.

---

## Prerequisites at a glance

| Prereq                                | Status        | Source                                 |
| ------------------------------------- | ------------- | -------------------------------------- |
| PR #42 freeze_support landed          | PASS          | `scripts/pyinstaller_entry.py:26`      |
| PR #47 spec + script hardening landed | PASS          | commit `5ead08f`, build script L295-353|
| v1.8 SIMD Phases 1-4 + AVX2 on main   | PASS (5 of 5) | git log greps above                    |
| pyproject == __init__ == 1.7.0        | PASS          | `pyproject.toml:3`, `__init__.py:196`  |
| maturin 1.13.x                        | PASS (1.13.3) | shim                                   |
| rustc/cargo 1.95.x                    | PASS          | `~/.cargo/bin` (needs `. cargo/env`)   |
| python 3.13                           | PASS (3.13.1) |                                        |
| PyInstaller 6.x                       | PASS (6.20.0) |                                        |
| nicegui importable                    | PASS (3.12.1) |                                        |
| create-dmg                            | PASS (1.2.3)  | `/usr/local/bin/create-dmg`            |
| Bash script syntax                    | PASS          | `bash -n` clean                        |
| `_rust.so` is universal2              | **FAIL**      | currently arm64-only; run maturin step |
| Codesign identity present             | **ABSENT**    | use `--identity "-"` or `--skip-signing`|
| Apple notarize creds set              | **ABSENT**    | pass `--skip-notarization`             |

---

## End-of-runbook quick reference

One-paste sequence (assumes user has read WARN 1 + 2 above):
```bash
cd /Users/ashen/Desktop/poker_solver
. "$HOME/.cargo/env"
maturin develop --release --target universal2-apple-darwin
sh scripts/build_macos_dmg.sh --identity "-" --skip-notarization 2>&1 | tee "/tmp/dmg_build_$(date +%Y%m%d_%H%M%S).log"
"/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test
ls -lh /Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.7.0-arm64.dmg
```

That's it. If smoke test prints `[smoke] poker_solver._rust imported OK`, the build is ready for the user's final go/no-go on the GUI launch.
