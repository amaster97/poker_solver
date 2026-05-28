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
# PR #69 audit fix: the preflop blueprint shards + 169x169 equity table
# live under assets/ and MUST be bundled so the .app boots in
# "blueprint-backed" mode. Omitting them silently degrades the app to
# "live solve only" — every preflop query falls through to a 5-30s solve
# instead of the <100 ms blueprint lookup, and the chained tab loses its
# postflop continuation-range derivation path entirely.
BLUEPRINTS_DIR = str(REPO_ROOT / "assets" / "blueprints")
EQUITY_NPZ = str(REPO_ROOT / "assets" / "preflop_equity_169x169.npz")
ICON_PATH = str(REPO_ROOT / "assets" / "poker_solver.icns")

# PR 44 fix: read __version__ dynamically from poker_solver/__init__.py
# so Info.plist's CFBundleShortVersionString matches the actual package
# version (previously hardcoded to "0.6.0" — stale since v0.7.0).
#
# PR 86 hardening: pyproject.toml `[project] version` is the authoritative
# source. Read it first; cross-check against poker_solver/__init__.py
# `__version__`; fail loud on mismatch so we never ship a .dmg whose
# Info.plist stamp drifts from the pyproject.toml release tag.
_pyproject_text = (REPO_ROOT / "pyproject.toml").read_text()
# Match the FIRST top-level `version = "x.y.z"` in pyproject.toml. The
# `(?m)^version\s*=` anchor is intentionally strict so it does NOT match
# the [tool.ruff] section's `target-version = "py39"` line.
_pyproject_match = re.search(
    r'(?m)^version\s*=\s*[\'"]([^\'"]+)[\'"]',
    _pyproject_text,
)
_init_match = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
    (REPO_ROOT / "poker_solver" / "__init__.py").read_text(),
)
_pyproject_version = _pyproject_match.group(1) if _pyproject_match else None
_init_version = _init_match.group(1) if _init_match else None
if _pyproject_version is None:
    raise RuntimeError(
        "scripts/poker_solver.spec: pyproject.toml has no top-level "
        "`version = \"x.y.z\"` line; refusing to stamp Info.plist with "
        "a guess. Check pyproject.toml [project] section."
    )
if _init_version is not None and _init_version != _pyproject_version:
    raise RuntimeError(
        f"scripts/poker_solver.spec: version drift between pyproject.toml "
        f"({_pyproject_version}) and poker_solver/__init__.py "
        f"({_init_version}). Bring them back in sync before building the "
        f".dmg — Info.plist stamp would otherwise mislead end users."
    )
APP_VERSION = _pyproject_version

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
        # PR #69 audit fix: bundle preflop blueprint shards + 169-class
        # equity table so the .app launches in blueprint-backed mode.
        # The destination subdirs mirror the source-tree layout so that
        # ``from poker_solver.blueprint_loader import default_assets_dir``
        # (which resolves ``Path(__file__).resolve().parents[1] / "assets"``
        # at install time and ``sys._MEIPASS / "assets"`` at frozen time)
        # finds them. See ``scripts/build_macos_dmg.sh`` smoke test.
        (BLUEPRINTS_DIR, "assets/blueprints"),
        (EQUITY_NPZ, "assets"),
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
    # PR 86 hardening: arm64-only is the SHIPPED arch. The "universal2"
    # nomenclature elsewhere in the repo refers ONLY to the maturin-built
    # _rust.so (which IS universal2 for source-tree pip-install on x86_64
    # Python under Rosetta).  The PyInstaller-bundled Python interpreter
    # inside the .app is arm64-only by design (PLAN.md hardware target).
    # The DMG filename `Poker-Solver-<version>-arm64.dmg` is authoritative;
    # any doc that still says the .app is "universal2" is stale.
    target_arch="arm64",  # PLAN.md hardware target — DO NOT change to universal2 without rebuilding all Python wheel deps.
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
