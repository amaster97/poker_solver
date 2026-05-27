# PR 44 .dmg Rebuild Report

**Date:** 2026-05-23
**Branch:** `pr-44-dmg-packaging-fix` @ `c09abe7c9667f38f123686bf326dbdbdcb28fa00`
**Operator:** rebuild + smoke-test agent

---

## 1. Build result

**SUCCESS.** PyInstaller + create-dmg completed cleanly with `--skip-signing --skip-notarization`.

- Output DMG: `/Users/ashen/Desktop/poker_solver/dist/Poker-Solver-1.6.0-arm64.dmg`
- DMG size: **45 MB** (vs v1.4.0's broken 14 MB — 3.2x growth proves NiceGUI is actually bundled)
- .app size: **123 MB** (in spec range 80-150 MB)
- Build log: `/tmp/dmg_build_pr44.log` (245 lines, no errors)
- Build time: ~20 s analysis + ~3 s create-dmg

Pre-flight blockers cleared during rebuild (NOT PR 44 changes; pre-existing env issues):

1. PyInstaller not installed in any reachable Python — installed `pyinstaller>=6.0` into a fresh `/tmp/pr44_venv` via `pip install -e '.[distribution]'`. This validated the `[distribution]` extra now pulls in NiceGUI (`Successfully installed ... nicegui-3.12.1 fastapi-0.136.3 uvicorn-0.47.0 starlette-1.1.0 python-socketio-5.16.2 python-engineio-4.13.2 ...`).
2. `_rust.cpython-313-darwin.so` was single-arch arm64 (from the prior maturin editable build). Pre-flight in `scripts/build_macos_dmg.sh` lines 173-178 (unchanged by PR 44) mandates universal2. Rebuilt via `maturin develop --release --target universal2-apple-darwin`; new .so verified `Mach-O universal binary [x86_64] [arm64]`.

## 2. Smoke test (mounted DMG)

`hdiutil attach dist/Poker-Solver-1.6.0-arm64.dmg` → mounted at `/Volumes/Poker Solver/`.

| Check | Command | Result |
|---|---|---|
| Bundle structure | `ls "/Volumes/Poker Solver/Poker Solver.app/Contents/"` | `Frameworks, Info.plist, MacOS, Resources, _CodeSignature` — OK |
| **In-bundle smoke test (PR 44 critical gate)** | `"/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test` | **`[smoke] poker_solver._rust imported OK ... PASS` exit 0** |
| Default launch (no flags) | `"/Volumes/Poker Solver/Poker Solver.app/Contents/MacOS/Poker Solver"` | **`NiceGUI ready to go on http://127.0.0.1:8080`** — NiceGUI loads + serves. **No ModuleNotFoundError.** This is the headline PR 44 fix. |
| `nicegui` bundled | `find ... -name nicegui -type d` | `/Volumes/.../Contents/Resources/nicegui` — OK |
| `fastapi` bundled | `find ... -name fastapi -type d` | `/Volumes/.../Contents/Resources/fastapi` — OK |
| `uvicorn` bundled | `find ... -name uvicorn -type d` | `/Volumes/.../Contents/Resources/uvicorn` — OK |
| Binary arch | `lipo -info ".../Poker Solver"` | `architecture: arm64` (matches DMG filename) |
| Info.plist version | `plutil -p ".../Info.plist"` | `CFBundleShortVersionString = "1.6.0"` (matches `poker_solver/__init__.py`'s `__version__ = "1.6.0"`) — dynamic version stamping confirmed |

NB: there is no `--help` / `--version` flag in `scripts/pyinstaller_entry.py` — only `--smoke-test` and default-launch-NiceGUI. The brief's `--help` / `--version` smoke checks were not applicable to this entry shim; the existing `--smoke-test` covers the equivalent gate.

`hdiutil detach -force /Volumes/Poker\ Solver` → `disk4 ejected`. Mount cleanup confirmed.

## 3. PR 44 acceptance criteria status (per spec §3)

1. **Binary launches without `ModuleNotFoundError`.** PASS — NiceGUI ready msg on default launch + `--smoke-test` exits 0.
2. **`find` locates nicegui in bundle.** PASS — `Contents/Resources/nicegui`.
3. **DMG mounts, .app structure intact.** PASS — `hdiutil attach` + structure walk.
4. **`lipo -info` matches filename claim.** PASS — DMG named `-arm64.dmg`, binary is `arm64` single-arch.
5. **`Info.plist` version matches tag.** PASS — `1.6.0` matches `__version__` (no git tag exists yet; tag check deferred to ship).
6. **Bundle size 80-150 MB.** PASS — 123 MB (.app), 45 MB (.dmg compressed).
7. **Signed + notarized.** N/A — out of scope (no Apple Developer enrollment), `--skip-signing --skip-notarization` per runbook.

## 4. Verdict

**PR 44 FIX VERIFIED.** All acceptance criteria within scope pass. The v1.4.0 root cause (`ModuleNotFoundError: nicegui`) is fully resolved. The arch label drift and version stamp drift are both corrected on disk and reflected in the produced .app.

## 5. What's next

- **Gate 5 queue:** PR 44 ready for full persona acceptance / Gate 5 readout. Recommend running the existing `docs/dmg_v1_4_0_smoke_verification.md` 8-step protocol against `dist/Poker-Solver-1.6.0-arm64.dmg` for parity with the v1.4.0 failure baseline.
- **Pre-flight script gap (NOT a PR 44 regression):** `scripts/build_macos_dmg.sh` lines 173-178 still mandate a universal2 `_rust.so` even though the spec's `target_arch="arm64"` strips the x86_64 slice during COLLECT. The x86_64 slice survives only as a developer test-time crutch (the W1.4 mitigation comment is correct: it's for x86_64 pyenv ↔ arm64 .so import-time crashes during dev tests). This is consistent with the spec doc's "internally consistent" framing but adds a hidden setup tax (maturin universal2 rebuild required even though the .app discards x86_64). Suggest a follow-up to either (a) relax the pre-flight to arm64-only when `target_arch=arm64` is set, or (b) keep universal2 _rust.so but document the dependency in `assets/README.md`. Out of scope for PR 44 verification.
- **Apple signing/notarization** remains user-blocked pending Developer Program enrollment ($99/yr). Spec §1 P0 #2 unchanged.
- **Push:** branch is local-only as instructed. Do NOT push without explicit authorization per public repo hygiene rules.
