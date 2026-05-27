# v1.6.0 GitHub Release — Final State Verification (2026-05-26)

**Verifier:** Read-only `gh release view` snapshot
**Scope:** Confirm tonight's safety actions (warning text + .dmg asset pull) still in place
**Verdict:** **OK — no regressions detected**

---

## 1. State Snapshot

| Field | Value |
|---|---|
| Release name | `v1.6.0: GUI Gate 2 (range editor, RvR, node-locking, asymmetric, slider tiers)` |
| Asset count | **0** |
| Assets | `[]` (empty) |
| Release URL | https://github.com/amaster97/poker_solver/releases/tag/v1.6.0 |
| URL reachable / public | YES (gh CLI returns URL without auth-restricted error) |

### Release body — first 500 chars (verbatim)

```
> ⚠️ **CRITICAL — v1.6.0 `.dmg` is BROKEN. Do NOT launch from Finder.**
>
> The `.app` bundle has a multiprocessing fork-bomb: launching from
> Finder causes uncontrolled process spawning that can freeze your Mac.
> Root cause is a missing `multiprocessing.freeze_support()` call in
> `scripts/pyinstaller_entry.py`. The patch is in flight on
> [PR #42](https://github.com/amaster97/poker_solver/pull/42); a
> repackaged `.dmg` will ship in v1.7.2.
>
> **Until v1.7.2, install from source instead:**
```

---

## 2. Regression Check (each of the 5 required gates)

| # | Check | Required | Observed | Pass |
|---|---|---|---|---|
| 1 | Release exists + has body/assets fields readable | YES | YES (gh returned all three) | OK |
| 2 | CRITICAL warning at TOP of release notes | Body must start with "⚠️ **CRITICAL — v1.6.0 `.dmg` is BROKEN**" or similar | Body literally starts with `> ⚠️ **CRITICAL — v1.6.0 \`.dmg\` is BROKEN. Do NOT launch from Finder.**` | OK |
| 3 | `.dmg` asset pulled | `assets` array must NOT contain `Poker-Solver-1.6.0-arm64.dmg` | `assets: []` (asset_count=0, entire array empty) | OK |
| 4 | Warning's PR link references PR #42 (freeze_support fix) | Must link `pull/42` | Body contains `[PR #42](https://github.com/amaster97/poker_solver/pull/42)` | OK |
| 5 | Release URL reachable + public | `gh release view --json url` returns URL | Returns `https://github.com/amaster97/poker_solver/releases/tag/v1.6.0` | OK |

**Additional consistency checks (not in spec, but verified):**

- Known-issues section also reframes the .dmg as `CRITICAL — DO NOT LAUNCH` (was previously "experimental"). Consistent with top-of-notes warning.
- Source-install path (`pip install -e .`) explicitly named as the only safe route until v1.7.2.
- RCA doc referenced: `docs/dmg_spawn_loop_rca_2026-05-26.md` on branch `pr-78-dmg-freeze-support-fix`.

---

## 3. Regressions Detected

**NONE.**

- Warning text: present, at top, verbatim with critical phrasing.
- Asset removal: confirmed (asset_count=0, no `.dmg` files attached).
- PR #42 link: present and well-formed.
- Release: public + reachable.

---

## 4. Verdict

**OK** — All 5 verification gates pass. Tonight's safety actions (warning insertion + `.dmg` asset removal) are intact on the public GitHub release. No remediation needed.

**Constraint honored:** read-only verification (only `gh release view --json` calls; no `gh release edit`, `gh release upload`, or `gh release delete-asset` invocations).
