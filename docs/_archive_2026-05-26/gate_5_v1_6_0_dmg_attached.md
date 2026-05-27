# Gate 5 partial close — v1.6.0 .dmg attached to GitHub release

**Date**: 2026-05-23
**Status**: PARTIAL CLOSE (v1.6.0 milestone)

## Artifact details

- **File**: `Poker-Solver-1.6.0-arm64.dmg`
- **Size**: 45 MB (47,536,469 bytes)
- **SHA256**: `0443e8f0b49f56ab2819d753a39a50b68bcf25907dabc3423256995215136a95`
- **Arch**: arm64 (Apple silicon)
- **Version**: 1.6.0 (Info.plist)
- **Signing**: adhoc (no Apple Developer enrollment)

## Verification chain

| Check | Result |
| --- | --- |
| `ls -lh` size | 45 MB ✓ |
| `shasum -a 256` | `0443e8f0...136a95` ✓ |
| `hdiutil verify` | "checksum ... is VALID" ✓ |
| `hdiutil attach` | mounted at `/Volumes/Poker Solver` ✓ |
| `--smoke-test` | `_rust imported OK`, 6 public symbols ✓ |
| `hdiutil detach` | "disk4 ejected" ✓ |

Smoke test stdout:
```
[smoke] poker_solver._rust imported OK: <module 'poker_solver._rust' from '/Volumes/Poker Solver/Poker Solver.app/Contents/Frameworks/poker_solver/_rust.cpython-313-darwin.so'>
[smoke] _rust public symbols: 6 found
```

Note: binary name inside the .app is `Poker Solver` (with space), not `poker-solver`; rebuild report's command path needs that correction for future runs.

## GitHub release

- **Release URL**: https://github.com/amaster97/poker_solver/releases/tag/v1.6.0
- **Asset URL**: https://github.com/amaster97/poker_solver/releases/download/v1.6.0/Poker-Solver-1.6.0-arm64.dmg
- **Asset SHA256 (server-reported digest)**: `sha256:0443e8f0b49f56ab2819d753a39a50b68bcf25907dabc3423256995215136a95` (matches local — upload integrity OK)
- **Asset size on server**: 47,536,469 bytes (matches local)
- **Uploaded at**: 2026-05-23T22:14:04Z
- **Asset state**: `uploaded`

## Release-notes diff

Appended new `### macOS installer` section between the `### Install` source-install block and `### Known issues`. The block calls out arm64-only, adhoc-signing implications, and first-launch instructions.

## Anomalies

- **Minor**: rebuild report referenced binary as `poker-solver` but actual binary inside the .app is `Poker Solver` (with space). Did not block this gate — discovered via `ls`, corrected smoke command.
- No other anomalies.

## Gate 5 verdict

**PARTIAL CLOSE** — v1.6.0 milestone achieved:
- ✓ .dmg artifact built, verified, and smoke-tested
- ✓ .dmg attached to GitHub v1.6.0 release with server-side digest match
- ✓ Release notes updated with installer instructions

Full Gate 5 close requires v1.7.0+ .dmg too (aggregator->vector wiring release). This documents the v1.6.0 milestone within the staged close.
