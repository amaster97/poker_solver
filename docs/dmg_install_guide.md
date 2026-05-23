# macOS .dmg Install Guide (v1.6.0)

Step-by-step instructions for installing and first-launching the v1.6.0
`.dmg` build of Poker Solver on macOS. The .dmg is **adhoc-signed**
(no Apple Developer enrollment), so Gatekeeper will block the first
launch unless you use one of the bypass options below.

## Download

- **GitHub release URL:**
  <https://github.com/amaster97/poker_solver/releases/tag/v1.6.0>
- **File:** `Poker-Solver-1.6.0-arm64.dmg` (45 MB, Apple silicon only)
- **SHA256:**
  `0443e8f0b49f56ab2819d753a39a50b68bcf25907dabc3423256995215136a95`

## Verify download (optional)

```bash
shasum -a 256 ~/Downloads/Poker-Solver-1.6.0-arm64.dmg
# Compare the printed hex against the SHA256 above. Strings must match exactly.
```

## Install

1. Open the `.dmg` by double-clicking it in Finder.
2. Drag the `Poker Solver.app` icon to your `Applications` folder.
3. Eject (unmount) the .dmg from Finder's sidebar.

## First launch (Gatekeeper bypass)

The .dmg is adhoc-signed (no Apple Developer ID, no Apple notarization),
so on a clean Mac Gatekeeper will refuse to launch it on the first try
with a message like *"App can't be opened because Apple cannot check it
for malicious software"*. You only need to bypass once — macOS remembers
the decision for subsequent launches.

### Option A — right-click → Open (recommended)

1. Open Finder and navigate to `Applications`.
2. **Right-click** (or Control-click) `Poker Solver.app`.
3. Choose **Open** from the context menu.
4. A dialog appears warning that Apple can't verify the developer.
   Click **Open**.
5. The app launches and the bypass is remembered.

### Option B — System Settings → Privacy & Security

1. Try launching the app once normally (double-click). Dismiss the
   Gatekeeper warning.
2. Open **System Settings** → **Privacy & Security**.
3. Scroll to the **Security** section. You should see a message similar
   to *"Poker Solver was blocked from use because it is not from an
   identified developer."*
4. Click **Open Anyway** next to that message.
5. Re-launch `Poker Solver.app`; confirm the prompt once more.

## What it does

- Launches a local NiceGUI web app at `http://127.0.0.1:8080`.
- Your default browser auto-opens to that URL.
- Same equity / solver engine as the Python CLI tier
  (`pip install -e .`).
- Closing the browser tab does **not** stop the app — quit it from the
  Dock or via `Cmd+Q` in the app's menu.

## Known limitations

- **Apple silicon (arm64) only.** Intel Macs cannot run this .dmg.
  Use the source install (`pip install -e .`) instead — see the
  README's "Install (from source)" section.
- **Adhoc-signed, not notarized.** macOS 14+ may display additional
  warnings on first launch. Bypass with Option A or B above.
- **v1.6.0 feature set only.** Newer features merged after v1.6.0 are
  available only via source install:
  - v1.7.0 vector-form range-vs-range API (aggregator → vector wiring)
  - v1.7.0 CLI subcommands (push/fold, range-vs-range)
  - Subsequent engine work shipped on `main`
  Rebuild the .dmg from a newer tag once those features GA.

## Troubleshooting

| Symptom | Action |
|---|---|
| "App can't be opened because Apple cannot check it for malicious software" | Use Option A (right-click → Open) or Option B (System Settings). |
| App opens but crashes immediately | Fall back to `pip install -e .` from source and file an issue with the crash log. |
| Browser doesn't auto-open | Navigate to <http://127.0.0.1:8080> manually. |
| Port 8080 already in use | Quit the conflicting process or run the source install with a different `--port`. |
| "You can't open the application because PowerPC applications are no longer supported" / "bad CPU type" | You're on an Intel Mac. Use the source install — this .dmg is arm64-only. |

## Future: notarized .dmg

The current .dmg is adhoc-signed because the project owner has not yet
enrolled in the Apple Developer Program. Once enrollment is complete
($99/year), the existing build script supports a notarized path with
no source changes:

- `scripts/build_macos_dmg.sh` already accepts a `--sign-with-developer-id`
  flag (and the matching notarization toggles) — see the script's
  argument parser for the exact invocation.
- Notarization adds roughly 5–10 minutes to the build (Apple's
  `notarytool` upload + staple round-trip).
- For end users, a notarized .dmg removes the right-click → Open dance
  entirely. Gatekeeper accepts it on first launch.
- Notarization is also a hard requirement if Poker Solver is ever
  distributed outside the GitHub release page (e.g., direct downloads
  from a project website, or via auto-update channels).

Until enrollment lands, the adhoc-signed .dmg above plus these
bypass instructions are the supported install path for the GUI tier.
The from-source CLI install (`pip install -e .`) remains the
recommended path for everything else.

## Related documents

- [`../CHANGELOG.md`](../CHANGELOG.md) — v1.6.0 release notes including
  the packaging fixes that produced this .dmg.
