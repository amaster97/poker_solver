# Mock-Mode Disclosure Audit — v1.8.0 Public-Facing Docs (2026-05-27)

**Trigger:** `docs/dmg_v1_8_0_user_smoke_2026-05-27.md` finding that the
bundled GUI in the v1.8.0 `.dmg` is in MOCK MODE (clicking **Solve**
produces hand-crafted fixtures, not real solver output). The in-app
yellow banner discloses this verbatim. **Question:** is mock mode
also disclosed in the docs a new downloader reads BEFORE installing?

## Verdict: PARTIAL — 2 of 5 locations PASS pre-fix; remediation PR adds disclosure to 2 of the 3 failing locations; 1 location flagged for user (GitHub release body).

## Per-location result

| # | Location | Pre-fix verdict | Detail |
|---|---|---|---|
| 1 | `docs/v1_8_0_release_notes_DRAFT.md` | **FAIL → FIXED** | No mock-mode mention in the release notes draft. The draft talks about the `.dmg` fork-bomb fix (§2) but says nothing about what users will see when they click **Solve**. Disclosure block added immediately after the §2 fork-bomb section as part of this PR. |
| 2 | GitHub release body (`gh release view v1.8.0`) | **FAIL — FLAGGED** | Release body mirrors the draft and is silent on mock mode. **Per user constraint, this PR does NOT amend the public release body** — user wants to eyeball before any edit. **Recommendation:** carry the same disclosure into the GitHub release body for v1.8.0 (either as a `gh release edit` after user review, or fold into a v1.8.0.1 docs ship). |
| 3 | `README.md` | **PASS** | Lines 199-205 explicitly state: *"The UI is currently in mock mode — clicking **Solve** returns hand-crafted fixture data, not real solver output (PR 10a scaffold; real solver bindings land in PR 10b). A yellow banner across the top makes this explicit. … Use the CLI / Python API for real strategies today."* Disclosure is conspicuous and accurate. |
| 4 | `docs/dmg_install_guide.md` | **FAIL → FIXED** | Pre-fix "What it does" claimed *"Same equity / solver engine as the Python CLI tier"*, which is **actively misleading** for v1.8.0 because the bundled GUI runs against fixtures, not the real engine. Disclosure block added; the stale claim was removed from the "What it does" bullet list. |
| 5 | `USAGE.md` | **PASS** | §4 ("The UI (currently mock mode)") lines 158-180 explicitly: *"When you click **Solve**, the results panel is populated from a fixture, not from a real solve."* Plus a recap at line 622. |

## Summary count

- **Locations checked:** 5
- **PASS pre-fix:** 2 (README, USAGE)
- **FAIL pre-fix:** 3 (release notes draft, GitHub release body, dmg install guide)
- **FIXED in this PR:** 2 (release notes draft, dmg install guide)
- **FLAGGED for user decision:** 1 (GitHub release body — explicit user constraint to not amend without review)

## Disclosure block used

```
**GUI is in MOCK MODE.** The bundled GUI in this release exposes the
full workflow (Solve / Pause / Stop / Library / Iterations) but solve
outputs are hand-crafted fixtures, not live DCFR computations. A
yellow banner at the top of the app reads verbatim: "Mock mode: solver
outputs are hand-crafted fixtures (PR 10a). Switches to real solver in
PR 10b." Real-solver wiring lands in a future PR (10b). For real
solver outputs, use the Python API or CLI per `docs/USAGE.md`.
```

This is a per-location adapted variant of the template specified in the
audit request. The `dmg_install_guide.md` instance has additional
context about the GUI tier vs source install (since the install guide
is the first thing a `.dmg` downloader reads). The release notes draft
instance is anchored to the existing `.dmg` fork-bomb section in §2.

## Open questions from `docs/dmg_v1_8_0_user_smoke_2026-05-27.md`

The smoke doc surfaces 4 open questions; **the user should answer Q1
first** since it directly determines whether the disclosure language
above is correct:

1. **(BLOCKING) Is PR 10b's real-solver wiring landed on `main` yet?**
   If yes, the bundled GUI in the v1.8.0 `.dmg` should NOT be in mock
   mode — and the banner text "Switches to real solver in PR 10b" is
   stale. The disclosure language in this PR assumes PR 10b is NOT
   merged (matches what the in-app banner says). Confirm before
   amending the GitHub release body.
2. **(Secondary) Should we ship a `v1.8.0.1` docs-only with a README.txt
   inside the `.dmg` root?** The smoke doc flagged that there is no
   first-run cue inside the disk image itself — a downloader sees only
   the `.app` + an `Applications` symlink. A one-line `README.txt`
   ("Drag to Applications; first launch opens http://127.0.0.1:8080;
   solve outputs are mock fixtures in v1.8.0 — see docs/dmg_install_guide.md")
   would close the largest UX gap. Not in scope for this PR
   (this PR is markdown-only; bundling a `.txt` requires a `.dmg`
   re-build).

Q3 (port-fallback bug in `ui/app.py`) and Q4 (should the bundled
binary accept CLI args) are non-blocking follow-ups; defer to
post-v1.8.0.

## What this PR does NOT do

- Does **not** amend the public GitHub release body (per explicit user
  constraint).
- Does **not** modify the `.dmg`, the in-app banner, or any production
  code. Pure docs-add.
- Does **not** re-classify the v1.8.0 ship verdict. The .dmg user smoke
  test already verdict'd PARTIAL → "ship to users WITH the install
  guide's caveats"; this PR brings the release notes + install guide
  into line with that caveat.

## Risk classification

**Low-risk docs-add.** Three markdown files touched (this audit +
release notes draft + dmg install guide). No code, no test, no .dmg.
Disclosure language matches what the in-app banner and `README.md` /
`USAGE.md` already say. Suitable for autonomous merge per
`feedback_pr10a5_autonomous_commit.md` (audit-clear docs ship), with
the explicit exception of the GitHub release body, which is held for
user review.
