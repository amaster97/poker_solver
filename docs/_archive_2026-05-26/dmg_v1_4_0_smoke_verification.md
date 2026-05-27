# DMG v1.4.0 Smoke Verification

**Date:** 2026-05-23
**Asset:** `Poker-Solver-1.4.0-universal2.dmg`
**Source:** `gh release download v1.4.0 --pattern '*.dmg'`
**Test host:** Darwin 24.6.0 (macOS, Apple silicon)
**Test scope:** Download, mount, structure, codesign, notarization, arch, non-interactive smoke launch
**Hard constraint:** No GUI launch (would hang agent); no modification of DMG or shared tree.

---

## 1. Download

| Item | Value |
|---|---|
| Filename | `Poker-Solver-1.4.0-universal2.dmg` |
| Size | 14,420,130 bytes (~14.42 MB) |
| SHA-256 | `800b30f739e731b76cf04e3c5556c578a8ce87130ff93a2664d0b74dcbd082ce` |
| Download path | `/tmp/poker_solver_dmg_test/Poker-Solver-1.4.0-universal2.dmg` |
| Download status | OK |

## 2. Mount

| Item | Value |
|---|---|
| Command | `hdiutil attach …` |
| Mount point | `/Volumes/Poker Solver` |
| Device | `/dev/disk4s1` (Apple_HFS) |
| Image integrity | All segments CRC32-verified by hdiutil |
| Mount status | OK |

## 3. .app bundle structure

`/Volumes/Poker Solver/` contents:
- `Applications` → symlink to `/Applications` (standard drag-to-install setup) — OK
- `Poker Solver.app/` (note: space in name, not `Poker-Solver.app`)
- `.DS_Store` (cosmetic)

`Poker Solver.app/Contents/`:
- `Info.plist`
- `MacOS/Poker Solver` (executable, 4.6 MB)
- `Frameworks/` (Python framework + numpy + psutil + bundled libs)
- `Resources/` (poker_solver, ui, base_library.zip, Python framework, etc.)
- `_CodeSignature/`

`Info.plist` key entries:
- `CFBundleIdentifier`: `com.poker_solver.app`
- `CFBundleExecutable`: `Poker Solver`
- `CFBundleShortVersionString`: **`0.6.0`** (NOT `1.4.0` — version stamp drift)
- `CFBundleVersion`: `0.6.0`

**Structure verdict:** Bundle layout is well-formed. Version string mismatch is a release-hygiene concern but not a functional break.

## 4. Code signing

`codesign -dvvv` output (key fields):
- `Identifier`: `com.poker_solver.app`
- `Format`: **`app bundle with Mach-O thin (arm64)`** (NOT universal)
- `Signature`: **`adhoc`**
- `TeamIdentifier`: not set
- `Sealed Resources`: version 2, rules 13, files 133 (intact)
- `CDHash` (sha256): `1be091c4b2662189967409aa2353db55857d07f2`

**Codesign verdict:** Ad-hoc signed only. No Developer ID. No team identifier. Self-consistent (resource seal valid), but not distribution-grade.

## 5. Notarization / Gatekeeper

- `spctl --assess --verbose=4 --type execute`: **`rejected`** (exit 3)
- `xcrun stapler validate`: **`Poker Solver.app does not have a ticket stapled to it`**

**Gatekeeper verdict:** REJECTED. The app is neither notarized nor stapled. On a clean machine, double-click launch will be blocked by Gatekeeper with "cannot be opened because the developer cannot be verified" / "Apple could not verify…". User must right-click → Open, or use System Settings → Privacy & Security → "Open Anyway".

## 6. Architecture

- `file …/Poker Solver`: `Mach-O 64-bit executable arm64`
- `lipo -info …/Poker Solver`: `Non-fat file: … is architecture: arm64`

**Architecture verdict:** **arm64-only.** The asset filename `…-universal2.dmg` is **misleading** — this is NOT a universal2 binary. Intel Mac users will be unable to run it. (Per PLAN.md scope this may be intentional / acceptable, but the filename should not advertise universal2.)

## 7. Smoke launch (non-interactive)

Invoked the bundled executable directly with `--version` and again with no args, both inside a 3–4 second background timeout (to avoid GUI hang).

Both runs failed identically with:

```
Traceback (most recent call last):
  File "pyinstaller_entry.py", line 61, in <module>
  File "pyinstaller_entry.py", line 56, in main
  File "ui/app.py", line 362, in launch
    from nicegui import ui
ModuleNotFoundError: No module named 'nicegui'
[PYI-XXXXX:ERROR] Failed to execute script 'pyinstaller_entry' due to unhandled exception: No module named 'nicegui'
```

Confirming the module is genuinely absent from the bundle:
- `find "/Volumes/Poker Solver/Poker Solver.app/" -iname "*nicegui*"` → **no matches**

**Smoke verdict:** **BUNDLE CANNOT LAUNCH.** `nicegui` (the GUI framework the app depends on) is missing from the PyInstaller bundle. The crash happens before any UI is presented, on every invocation, regardless of args. This is a P0 packaging defect, not a Gatekeeper / signing issue.

Secondary observation: the entry point `pyinstaller_entry.main()` jumps straight into `ui/app.py:launch()` without any CLI arg parsing — so `--version` and `--help` do nothing; there is no non-GUI mode wired into the binary at all.

## 8. Unmount

- `hdiutil detach "/Volumes/Poker Solver/"` initially returned "Resource busy" (likely from in-flight `find`).
- Retried with `-force`: ejected cleanly.
- Final state: volume unmounted, DMG file preserved at `/tmp/poker_solver_dmg_test/`.

---

## Net verdict

**DMG-NEEDS-FIX**

The installer mounts cleanly and the bundle is structurally well-formed, BUT:

1. **Hard blocker (P0):** Binary crashes immediately on every launch with `ModuleNotFoundError: No module named 'nicegui'`. End users cannot use this build at all.
2. **Distribution blocker (P1):** Ad-hoc signed, not notarized — Gatekeeper rejects on first launch. End users must manually right-click → Open or use System Settings escape hatch.
3. **Asset-mislabel (P2):** Filename says `universal2`, binary is `arm64`-only. Intel users cannot run it even if blockers 1 and 2 were fixed.
4. **Version stamp drift (P3):** `Info.plist` `CFBundleShortVersionString = 0.6.0` while release tag is `v1.4.0`. Cosmetic / release-hygiene only.

## Recommended actions

| Priority | Action |
|---|---|
| P0 | Re-spec PyInstaller `.spec` to include `nicegui` (likely as `hiddenimports = ['nicegui']` plus its data files via `collect_data_files('nicegui')` / `collect_all('nicegui')`). Re-build, re-test on a clean account. |
| P0 | After P0 fix, re-run this same protocol to confirm the binary actually starts (or at least exits cleanly on `--version`). |
| P1 | Either: (a) procure Developer ID + notarize for distribution; OR (b) ship as-is with explicit README warning (see below). |
| P2 | Either rebuild as a true universal2 binary, OR rename the asset to `Poker-Solver-1.4.0-arm64.dmg` to stop advertising what isn't delivered. |
| P3 | Bump `Info.plist` `CFBundleShortVersionString` / `CFBundleVersion` to match the release tag in the build pipeline. |

## Recommended README warning (interim, if shipping as-is post-P0-fix)

```
## macOS install notes

This build is ad-hoc signed and not notarized by Apple. On first launch macOS
Gatekeeper will block it with a "cannot be opened because the developer cannot
be verified" message.

To open it the first time:
  1. In Finder, right-click "Poker Solver.app" → Open
  2. Click "Open" in the dialog
  -- or --
  System Settings → Privacy & Security → scroll to bottom →
  "Poker Solver was blocked…" → click "Open Anyway"

This build is Apple-silicon (arm64) only. Intel Macs are not supported by this
asset.
```
