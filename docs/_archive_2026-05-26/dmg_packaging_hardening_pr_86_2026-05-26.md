# PR 86 — .dmg packaging hardening (post-fork-bomb-fix follow-up)

**Date:** 2026-05-26
**Branch:** `pr-86-dmg-packaging-hardening`
**Scope:** items #38–40 of the unresolved-failures list (arch label
accuracy, Info.plist version stamp, ad-hoc signature integrity), excluding
the Apple Developer enrollment work that user has explicitly carried.

---

## Pre-edit ground-truth captures

### Info.plist version stamp on the existing v1.6.0 .app

```
$ defaults read "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/Info.plist" CFBundleShortVersionString
1.6.0
$ defaults read "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/Info.plist" CFBundleVersion
1.6.0
```

Note: `1.6.0` is the CORRECT stamp for the v1.6.0 build that produced
the on-disk `.app` — the spec was already reading `__version__`
dynamically per PR 44's fix. The defect for THIS PR is to make the
read robust against future drift between `pyproject.toml [project]
version` (currently `1.7.0`) and `poker_solver/__init__.py
__version__` (currently `1.7.0`).

### Codesign verify on the existing v1.6.0 .app

```
$ codesign --verify --deep --verbose=4 "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app"
... (long output validating every inner binary) ...
/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app: valid on disk
/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app: satisfies its Designated Requirement

$ codesign -dvvv "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app"
Executable=/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/MacOS/Poker Solver
Identifier=com.poker_solver.app
Format=app bundle with Mach-O thin (arm64)
CodeDirectory v=20400 size=104941 flags=0x2(adhoc) hashes=3273+3 location=embedded
... Signature=adhoc
... TeamIdentifier=not set
... Sealed Resources version=2 rules=13 files=1350
```

**Verdict:** the ad-hoc signature is intact. The Gatekeeper warning the
user sees on a clean Mac is a function of the missing Developer ID
identity, NOT a broken signature.

### Main executable architecture

```
$ lipo -info "/Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/MacOS/Poker Solver"
Non-fat file: /Users/ashen/Desktop/poker_solver/dist/Poker Solver.app/Contents/MacOS/Poker Solver is architecture: arm64
```

Confirms the .app's main Mach-O is arm64-only — the DMG filename
`Poker-Solver-1.6.0-arm64.dmg` is honest.

---

## Per-file edit summary

### `scripts/poker_solver.spec`

1. Replaced the single `__version__`-from-`__init__.py` read with a
   two-source read:
   - `pyproject.toml [project] version` (authoritative).
   - `poker_solver/__init__.py __version__` (cross-check).
   - **Hard-fail with `RuntimeError`** if they disagree, so the build
     refuses to silently stamp an inconsistent Info.plist.
2. Annotated the `target_arch="arm64"` line with a load-bearing comment
   explaining why universal2 is reserved for the Rust `_rust.so` (not
   the bundled Python interpreter).

### `scripts/build_macos_dmg.sh`

1. Changed the version-derivation step to read from `pyproject.toml`
   first (matching the spec's source-of-truth). Falls back to
   user-supplied `--version <X.Y.Z>` if the regex match fails; errors
   out on `0.0.0`.
2. Added **Step 5.5** ("PR 86 hardening: post-sign arch + version +
   codesign verify"). Runs after signing, before notarization. Hard-fails
   the build on:
   - (a) Main executable Mach-O is not arm64 (`lipo -info`).
   - (b) `Info.plist` `CFBundleShortVersionString` or `CFBundleVersion`
     diverges from `APP_VERSION`.
   - (c) `codesign --verify --deep --strict` rejects the `.app` (catches
     stale inner-binary signatures from incremental builds — though
     step 2 already runs a clean `rm -rf build dist`).
3. Refreshed the **Step 11 report** to surface the actual signature
   type (ad-hoc / Developer ID / unsigned / unknown) so the operator
   can verify at a glance which Gatekeeper path applies.
4. Expanded the Gatekeeper-bypass footer to trigger on EITHER
   `--skip-signing` OR ad-hoc-detected signatures, since both leave
   end users facing the same first-launch dialog.

### `USAGE.md`

Updated the §2 Path A blurb that still claimed the `.dmg` was "arm64-only
despite the `universal2` label". The DMG filename has been
`Poker-Solver-<version>-arm64.dmg` since PR 44 (already landed);
PR 86 now also enforces this at build time.

### `docs/dmg_install_guide.md`

1. Added a "Signature is verified intact" paragraph explaining that the
   ad-hoc signature itself is sound — Gatekeeper objects to the absence
   of a Developer ID identity, not to a malformed signature.
2. Added inline `codesign --verify --deep --strict` and
   `codesign -dvv ... | grep -E '^Signature|^TeamIdentifier'`
   one-liners users can run locally to confirm.
3. Extended Option A (right-click → Open) with the
   "menu item greyed out → wait for copy to finish" tip and the
   explicit "Click Open, not Move to Trash" guidance.
4. Added Option C (`xattr -d com.apple.quarantine`) as a third bypass
   route for users who prefer the terminal or want to script the bypass
   into a provisioning workflow.

---

## What this PR does NOT do (deliberately out of scope)

- **No .dmg rebuild.** The on-disk `.app`/`.dmg` are left as-is. The
  rebuild + re-sign + retest is a v1.7.2 release task (separate ticket;
  blocked on Phase 3/4 SIMD landing first).
- **No change to `scripts/pyinstaller_entry.py`.** That file is PR #42's
  territory (already merged); PR 86 only verifies the post-fork-bomb-fix
  behaviour from the OUTSIDE (verify steps run on the produced `.app`,
  not on the entry source).
- **No relaxation of the `.dmg` warnings in `README.md` or `USAGE.md`.**
  Those stay until v1.7.2 ships with `multiprocessing.freeze_support()`
  empirically confirmed in a fresh build.
- **No Apple Developer enrollment work.** Per user's explicit carry —
  PR 86's contribution is to ensure the build-script verification
  catches stale signatures so that WHEN enrollment lands and Developer
  ID signing replaces ad-hoc, drift between the signature and the
  bundle structure is caught at build time.

---

## Acceptance criteria for PR 86 (verifiable without a fresh build)

- [x] `bash -n scripts/build_macos_dmg.sh` parses (shell syntax OK).
- [x] `ast.parse(open('scripts/poker_solver.spec').read())` parses
      (Python syntax OK; PyInstaller's dynamic-symbol injection is
      not exercised by AST validation but the regex hardening is).
- [x] Regex hardening in the spec matches `pyproject.toml`'s
      `version = "1.7.0"` AND ignores `[tool.ruff] target-version =
      "py39"` (verified locally).
- [x] No edits to `scripts/pyinstaller_entry.py` (PR #42 territory).
- [x] No `.dmg` rebuild attempted in this PR.

When v1.7.2 builds run for the first time, Step 5.5 of the build script
will exercise the three new gates (arch / Info.plist / codesign verify)
on the produced `.app`. Any drift between source-of-truth (pyproject.toml)
and the build output will hard-fail the build before the `.dmg` is
wrapped and signed.

---

## References

- `scripts/build_macos_dmg.sh` — build pipeline (now 12 effective steps;
  step 5.5 is the PR 86 addition).
- `scripts/poker_solver.spec` — PyInstaller spec with pyproject/init
  drift check.
- `docs/dmg_install_guide.md` — end-user install guide with verified
  ad-hoc signature explanation.
- `docs/dmg_spawn_loop_rca_2026-05-26.md` — the fork-bomb RCA that
  motivated PR #42; PR 86 is the immediate follow-up.
- PR #42 (commit `728206e`): `multiprocessing.freeze_support()` fix
  (already merged to main).
- PR #44 (legacy, commit `c09abe7` on `pr-44-dmg-packaging-fix`):
  prior PR 44 work that landed the dynamic version read + DMG filename
  rename. PR 86 reinforces those fixes with build-time enforcement.
