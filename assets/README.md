# Poker Solver assets

This directory holds visual + branding assets used when packaging the
solver as a macOS `.app` bundle. None of these files are imported by
the Python library — they are only consumed by
`scripts/build_macos_dmg.sh`.

## `poker_solver.icns` — application icon

The `.icns` shipped here is a **single-pixel transparent placeholder**.
The build pipeline (`scripts/build_macos_dmg.sh`) auto-generates it on
first run if missing, so the unsigned-fallback build always works even
on a fresh checkout. Replace it with a real icon as follows.

### Recipe: replace the placeholder with a custom icon

1. Start with a 1024 × 1024 source PNG (transparent background).
2. Generate the iconset:
   ```bash
   mkdir poker_solver.iconset
   sips -z 16   16   src.png --out poker_solver.iconset/icon_16x16.png
   sips -z 32   32   src.png --out poker_solver.iconset/icon_16x16@2x.png
   sips -z 32   32   src.png --out poker_solver.iconset/icon_32x32.png
   sips -z 64   64   src.png --out poker_solver.iconset/icon_32x32@2x.png
   sips -z 128  128  src.png --out poker_solver.iconset/icon_128x128.png
   sips -z 256  256  src.png --out poker_solver.iconset/icon_128x128@2x.png
   sips -z 256  256  src.png --out poker_solver.iconset/icon_256x256.png
   sips -z 512  512  src.png --out poker_solver.iconset/icon_256x256@2x.png
   sips -z 512  512  src.png --out poker_solver.iconset/icon_512x512.png
   cp                       src.png  poker_solver.iconset/icon_512x512@2x.png
   ```
3. Pack into `.icns`:
   ```bash
   iconutil -c icns -o assets/poker_solver.icns poker_solver.iconset
   ```
4. Verify with Preview or `iconutil -c iconset assets/poker_solver.icns`.

Apple's required iconset entries (per their HIG): 16×16, 32×32, 128×128,
256×256, 512×512 — each in `@1x` and `@2x` (Retina) variants.

## Distribution / packaging

### One-time setup (per machine)

```bash
# Python deps (PyInstaller is opt-in to keep the runtime install lean)
pip install -e ".[distribution]"

# Native Rust extension required by the bundle
maturin develop

# Apple side
xcode-select --install
brew install create-dmg
```

### Build the unsigned `.app` + `.dmg` (no Apple Developer enrollment)

```bash
./scripts/build_macos_dmg.sh --skip-signing --skip-notarization
```

Outputs `dist/Poker Solver.app` and `dist/Poker-Solver-<version>-arm64.dmg`.
Open the unsigned `.app` via:

- **Right-click → Open** in Finder (one-time per user), OR
- `xattr -d com.apple.quarantine "dist/Poker Solver.app"` (permanent on this machine).

### Build the signed + notarized `.dmg` (Apple Developer enrollment)

```bash
export APPLE_ID="you@example.com"
export TEAM_ID="ABCDE12345"
export APP_SPECIFIC_PASSWORD="abcd-efgh-ijkl-mnop"   # generated at appleid.apple.com
./scripts/build_macos_dmg.sh --identity "Developer ID Application: Your Name (ABCDE12345)"
```

The app-specific password is never committed; it lives in the user's
keychain or a `.env` (gitignored).

### Empirically-derived `--hidden-import` list

PyInstaller's static analysis misses dynamic-import patterns in
NiceGUI / uvicorn / starlette. The current list in
`scripts/poker_solver.spec` was derived by:

1. Running the build with the minimal list (`nicegui`, `nicegui.elements`,
   `nicegui.functions`).
2. Hitting `ModuleNotFoundError: No module named 'X'` during the
   in-bundle smoke test.
3. Adding `'X'` to `hiddenimports` and rebuilding.

If you add a new dynamic import to the UI layer, repeat the cycle and
update the list.

### Architecture: arm64 only

The bundle targets Apple Silicon (M-series). The `target_arch="arm64"`
line in `scripts/poker_solver.spec` is load-bearing. Intel-Mac support
is explicitly out of scope for v1.0.0.

### DMG size

Empirically ~165 MB after the `--exclude-module` trim
(unittest, idlelib, turtle, tkinter, test, tests, pydoc_data).
Under the 200 MB soft target. If it grows past 200 MB, document the
size in the build output and accept it — a 200 MB DMG download is not
a UX dealbreaker.

## License notes

This project is MIT-licensed. The bundled artifacts carry their own
licenses:

- **PyInstaller** is GPL-with-exception: the exception explicitly
  covers bundled executables produced by PyInstaller, so the `.app` /
  `.dmg` produced here remain MIT-licensed. See
  <https://pyinstaller.org/en/stable/license.html>.
- **NumPy / NiceGUI / uvicorn / starlette / etc.** — BSD/MIT/Apache,
  all compatible.
- **PyO3 / maturin-built `_rust.so`** — MIT, our code.

No AGPL/GPL-without-exception dependencies are bundled.

## Top risk: PyInstaller silently drops `_rust.so`

PyInstaller's AST walker does **not** know that `from poker_solver
import _rust` resolves to `_rust.cpython-313-darwin.so` because PyO3
wires the import at C-API level via `#[pymodule]`. Mitigation
(per PR 11 spec §12.1):

1. `scripts/poker_solver.spec` lists the `.so` explicitly under
   `binaries=`.
2. `scripts/build_macos_dmg.sh` step 4 runs an in-bundle smoke test
   (`Poker Solver.app/Contents/MacOS/Poker Solver --smoke-test`) that
   does `from poker_solver import _rust` and fails the build on import
   error — before notarization or DMG creation.

If the smoke test ever fails, check `dist/smoke_test.log` and confirm
the `binaries=` entry in the spec file is intact.
