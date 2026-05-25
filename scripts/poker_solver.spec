# PyInstaller spec for the Poker Solver .app bundle (macOS, arm64).
#
# Reference: https://pyinstaller.org/en/stable/spec-files.html
# Invocation: pyinstaller scripts/poker_solver.spec --noconfirm
#
# Decisions LOCKED (per PR 11 spec / agent_b_prompt.md):
#   - --windowed (BUNDLE = .app on macOS)
#   - --onedir (NOT --onefile; breaks code-signing of inner files)
#   - arm64 only (PLAN.md hardware target = Apple Silicon)
#   - DMG size target < 200 MB → aggressive --exclude-module list
#   - Bundle id: com.poker_solver.app
#
# Top-risk mitigation (spec §12.1): the maturin-built Rust extension
# poker_solver/_rust.cpython-313-darwin.so is NOT discoverable by
# PyInstaller's AST walker (PyO3 wires #[pymodule] at C-API level), so
# we add it explicitly via the `binaries` list below.  The post-build
# smoke-test step in scripts/build_macos_dmg.sh verifies the import
# works inside the bundle BEFORE codesign/notarize/DMG run.
# noqa: this is a PyInstaller spec, not a Python module to be imported.

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# pyright: reportUndefinedVariable=false
# (Analysis, EXE, COLLECT, BUNDLE are injected by PyInstaller's exec'd context.)

block_cipher = None

REPO_ROOT = Path(SPECPATH).parent.resolve()  # noqa: F821  (SPECPATH injected)
ENTRY = str(REPO_ROOT / "scripts" / "pyinstaller_entry.py")
RUST_SO = str(REPO_ROOT / "poker_solver" / "_rust.cpython-313-darwin.so")
CHARTS_DIR = str(REPO_ROOT / "poker_solver" / "charts")
UI_DIR = str(REPO_ROOT / "ui")
ICON_PATH = str(REPO_ROOT / "assets" / "poker_solver.icns")

# PR 44 fix: read __version__ dynamically from poker_solver/__init__.py
# so Info.plist's CFBundleShortVersionString matches the actual package
# version (previously hardcoded to "0.6.0" — stale since v0.7.0).
_version_match = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
    (REPO_ROOT / "poker_solver" / "__init__.py").read_text(),
)
APP_VERSION = _version_match.group(1) if _version_match else "0.0.0"

# PR 44 fix: widen `datas` / `binaries` / `hiddenimports` to capture
# NiceGUI 3.x's static/templates dirs and the runtime submodule tree
# for fastapi/uvicorn/starlette/socketio/engineio.  The hand-listed
# `hiddenimports` block below is insufficient on its own: NiceGUI loads
# `nicegui/static/` (JS/CSS bundles) and `nicegui/templates/` (Jinja) by
# path at runtime, which PyInstaller's static analysis cannot discover.
# `collect_all` pulls in datas + binaries + hiddenimports for each pkg.
datas, binaries, hiddenimports = [], [], []
for pkg in ('nicegui', 'fastapi', 'uvicorn', 'starlette', 'socketio', 'engineio'):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports


a = Analysis(  # noqa: F821
    [ENTRY],
    pathex=[str(REPO_ROOT)],
    binaries=[
        # Top-risk mitigation (spec §12.1): force-include the Rust .so.
        # Tuple is (source_path, destination_subdir_inside_bundle).
        (RUST_SO, "poker_solver"),
    ] + binaries,
    datas=[
        (CHARTS_DIR, "poker_solver/charts"),
        (UI_DIR, "ui"),
    ] + datas,
    hiddenimports=hiddenimports + [
        # NiceGUI does a lot of dynamic imports under nicegui.elements
        # and nicegui.functions that PyInstaller's static analysis misses.
        # The `collect_all` calls above should make most of these
        # redundant, but we keep them as a belt-and-suspenders safety net
        # in case `collect_all` misses something.  See assets/README.md.
        "nicegui",
        "nicegui.elements",
        "nicegui.functions",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "starlette",
        "starlette.routing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Bundle-size trim (spec §12.3).  Each of these is ~5-15 MB.
        "unittest",
        "idlelib",
        "turtle",
        "tkinter",
        "test",
        "tests",
        "pydoc_data",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Poker Solver",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # upx + codesign is fragile on macOS
    console=False,  # --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",  # PLAN.md hardware target
    codesign_identity=None,  # Signing handled out-of-band by sign_and_notarize.py
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Poker Solver",
)

app = BUNDLE(  # noqa: F821
    coll,
    name="Poker Solver.app",
    icon=ICON_PATH,
    bundle_identifier="com.poker_solver.app",
    version=APP_VERSION,
    info_plist={
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
        # Don't show "Poker Solver" in the Dock when launched from CLI
        # for headless smoke tests; uncomment if you want a true
        # background-only mode:
        # "LSUIElement": True,
        "NSPrincipalClass": "NSApplication",
        "NSRequiresAquaSystemAppearance": False,  # Respect dark-mode setting
    },
)
