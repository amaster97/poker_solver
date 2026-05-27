# v-final .dmg Packaging Recipe (post-v1.7.1)

**Purpose:** rebuild the user-facing `.dmg` for the v1.7.1 ship. v1.6.0 is the last attached `.dmg`; v1.7.0 was engine-only. v1.7.1 must refresh the downloadable.

**Authoritative scripts:** `scripts/build_macos_dmg.sh` (11-step pipeline), `scripts/sign_and_notarize.py` (signing + notarytool wrapper). PR 44 packaging fix is on `pr-44-dmg-packaging-fix` @ `c09abe7` (verified 2026-05-23, 45 MB DMG, in-bundle `--smoke-test` PASS). **Merge PR 44 to `main` before invoking this recipe** if not already done.

This document does **not** execute a build; it is the operator runbook.

---

## 1. Prerequisites

- [ ] v1.7.1 tag exists on `main`: `git -C /Users/ashen/Desktop/poker_solver tag | grep v1.7.1`
- [ ] PR 44 commit `c09abe7` is in `main`'s history: `git log main --oneline | grep c09abe7`
- [ ] `poker_solver/__init__.py` `__version__ = "1.7.1"` (the build script reads this for the DMG filename + Info.plist stamp).
- [ ] Build venv has `pip install -e '.[distribution]'` (pulls PyInstaller + NiceGUI + FastAPI + uvicorn).
- [ ] Xcode CLT installed: `xcode-select -p`.
- [ ] `brew install create-dmg`.
- [ ] **Apple Dev cert** (user responsibility — see §8 for unsigned fallback).
- [ ] `xcrun notarytool` credentials available if signing: `APPLE_ID`, `TEAM_ID`, `APP_SPECIFIC_PASSWORD` env vars (app-specific password from appleid.apple.com).

## 2. Pre-flight verification

```bash
cd /Users/ashen/Desktop/poker_solver

# 2a. .so arch check (per feedback_dotso_arch_check.md — single-arch silently SKIPs/hangs)
file poker_solver/_rust.cpython-313-darwin.so
# Expected: "Mach-O universal binary with 2 architectures: [x86_64 ...] [arm64 ...]"
# If single-arch: maturin develop --release --target universal2-apple-darwin

# 2b. cargo build clean (Rust crate compiles)
cargo build --release --manifest-path rust/Cargo.toml

# 2c. Python tier import smoke (catches missing deps before PyInstaller burns 1-3 min)
python -c "import poker_solver, poker_solver._rust, nicegui, fastapi, uvicorn; print('imports OK')"

# 2d. PyInstaller spec valid (dry-run parses the spec)
pyinstaller scripts/poker_solver.spec --noconfirm --distpath /tmp/dryrun_dist --workpath /tmp/dryrun_build && rm -rf /tmp/dryrun_dist /tmp/dryrun_build
```

All four must pass before proceeding.

## 3. Build steps

**Signed path (Apple Dev enrolled):**
```bash
export APPLE_ID="..." TEAM_ID="..." APP_SPECIFIC_PASSWORD="..."
bash scripts/build_macos_dmg.sh
```

**Unsigned fallback (no Apple Dev enrollment):**
```bash
bash scripts/build_macos_dmg.sh --skip-signing --skip-notarization
```

Output: `dist/Poker-Solver-1.7.1-arm64.dmg` (filename auto-derived from `__version__`).

Expected size: ~45 MB (anything <30 MB is suspect — PR 44 fix mandates NiceGUI bundled).

## 4. Notarization (user-only step; documented, NOT executed by agent)

The build script already invokes notarytool when `--skip-notarization` is NOT passed. Manual override:
```bash
# Submit
xcrun notarytool submit dist/Poker-Solver-1.7.1-arm64.dmg \
  --apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$APP_SPECIFIC_PASSWORD" --wait

# Staple
xcrun stapler staple dist/Poker-Solver-1.7.1-arm64.dmg
xcrun stapler validate dist/Poker-Solver-1.7.1-arm64.dmg   # expect "worked"
```

Failure log: `dist/notarization_failure.log` (captured by `sign_and_notarize.py`).

## 5. GitHub release attachment

```bash
gh release upload v1.7.1 dist/Poker-Solver-1.7.1-arm64.dmg --repo <owner>/<repo>
# If v1.7.1 release doesn't exist yet:
gh release create v1.7.1 --title "v1.7.1" --notes-file docs/release_notes_v1.7.1.md \
  dist/Poker-Solver-1.7.1-arm64.dmg
```

## 6. SHA256 capture for release notes

```bash
shasum -a 256 dist/Poker-Solver-1.7.1-arm64.dmg
```
Paste output into the v1.7.1 release notes under a "Download verification" section.

## 7. Smoke test on a fresh Mac

On a Mac that has NOT had the dev tree on it (or after `xattr -d com.apple.quarantine` reset):
1. Download the `.dmg` from the GitHub release.
2. Double-click → drag `Poker Solver.app` to `Applications`.
3. Launch from `Applications/`.
4. **Signed path:** must NOT show "unidentified developer" Gatekeeper prompt.
5. **Unsigned path:** Gatekeeper warning expected; right-click → Open (one-time bypass).
6. NiceGUI must serve on `http://127.0.0.1:8080` within ~5 s.
7. Run `--smoke-test` from terminal: `"/Applications/Poker Solver.app/Contents/MacOS/Poker Solver" --smoke-test` → expect `[smoke] PASS` exit 0.

## 8. Apple Developer enrollment — open question

**Status: OPEN.** It is not confirmed whether the user is enrolled in the Apple Developer Program ($99/yr).

Trade-off:
- **Enrolled + signed + notarized:** `.dmg` opens cleanly; no Gatekeeper friction. Apple notarization adds 1-15 min wall time per submission.
- **Not enrolled / unsigned:** `.dmg` ships with `--skip-signing --skip-notarization`. End users see "unidentified developer" warning on first launch and must right-click → Open or `xattr -d com.apple.quarantine`. README must document the bypass (already covered in `docs/dmg_install_guide.md`).

**Recommendation:** ship v1.7.1 unsigned if enrollment is not in place — the bypass is documented and the alternative is to block a deliverable on a $99 + 24-48h enrollment cycle. Capture in release notes that signing is deferred.

## 9. Universal2 fix verification

Per task #152 history (single-arch `.so` regression risk). After the .app is built but before notarization:
```bash
APP="dist/Poker Solver.app"
# 9a. Main executable arch
lipo -info "$APP/Contents/MacOS/Poker Solver"
# Expected (current spec, line 104 target_arch="arm64"): "architecture: arm64"

# 9b. _rust.so inside the bundle — MUST be universal2 (the .app's PyInstaller Python
# may be arm64-only, but _rust.so itself must remain universal2 for the source-tree
# pre-flight to pass on subsequent rebuilds; spec §12.1).
find "$APP" -name "_rust*.so" -exec file {} \;
# Expected: "Mach-O universal binary ... [x86_64] [arm64]"
```

If `9b` shows single-arch, the source-tree `_rust.so` was overwritten between pre-flight and PyInstaller (e.g., `maturin develop` without `--target universal2-apple-darwin`). Rebuild universal2 and re-run from §3.

---

## Post-recipe

- Update `PLAN.md`: mark "v1.7.1 .dmg attached" alongside the v1.7.1 ship row.
- Update `docs/dmg_install_guide.md` if the bypass instructions changed.
- If unsigned: post a note in the release that signing is planned for v-final once Dev enrollment lands.
