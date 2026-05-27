# Mock-Mode Disclosure Audit — v1.8.0 Public-Facing Docs (2026-05-27)

> **STATUS: SUPERSEDED by PR #103.** The premise of this audit ("the
> bundled GUI is in mock mode") was wrong. PR #103 proves the in-app
> yellow banner was **unconditionally stale**: real-solver bindings
> shipped at v1.2.0 (commits `033cff3` / `890b96f` / `363b2bb`) and
> `SolveRunner._dispatch_solve` (`ui/state.py:908+`) has been routing
> to `poker_solver.solver.solve()` for every production invocation
> since. The mock path (`ui/state.py:967-981`, formerly `1340-1399`)
> only fires when `mock_latency_ms` or `mock_failure_mode` is
> explicitly set — **unreachable from the UI**. Disclosure additions
> originally planned by this PR have been reverted; only this audit
> doc is retained, as a record of what was checked.

## Original trigger

`docs/dmg_v1_8_0_user_smoke_2026-05-27.md` saw the yellow banner ("Mock
mode: solver outputs are hand-crafted fixtures (PR 10a). Switches to
real solver in PR 10b.") and concluded the bundled GUI was in mock
mode. The smoke doc asked: is mock mode also disclosed in the docs a
new downloader reads BEFORE installing?

That question is now moot. The banner was wrong; there is no mock mode
to disclose.

## What this audit originally checked (kept for diagnostic value)

The 5-location audit was run before PR #103 falsified the premise.
Per-location result, with PR #103 reconciliation appended:

| # | Location | Pre-PR-#103 verdict | Post-PR-#103 status |
|---|---|---|---|
| 1 | `docs/v1_8_0_release_notes_DRAFT.md` | FAIL (no mock-mode mention) | **N/A — there is no mock mode; original FAIL is void. Disclosure block added by this PR has been reverted.** |
| 2 | GitHub release body (`gh release view v1.8.0`) | FAIL (silent on mock mode) | **N/A — same as #1. No release-body edit needed. Flag is dropped.** |
| 3 | `README.md` | PASS (lines 199-205 explicitly state mock mode) | **README contains stale claim** — same root cause as the banner. Tracked separately; not in scope for this PR. |
| 4 | `docs/dmg_install_guide.md` | FAIL (claimed "same engine as CLI") | **The "same equity / solver engine as the Python CLI tier" claim was actually CORRECT** — `_dispatch_solve` routes both tiers through `poker_solver.solver.solve()`. Disclosure block added by this PR has been reverted; the install guide is now restored to its pre-PR state. |
| 5 | `USAGE.md` | PASS (§4 explicitly described mock mode) | **USAGE.md §4 contains stale claim** — same as README. Tracked separately. |

## Why the original verdict was wrong

The audit trusted the in-app banner ("Mock mode: solver outputs are
hand-crafted fixtures (PR 10a)") as ground truth and back-propagated
that claim into the docs surface. PR #103 inverted the direction of
investigation: it read the actual dispatch code first and found the
mock path is gated behind explicit smoke-test fault-injection
parameters that the UI never sets. The banner survived because no test
asserted on its semantic correctness — only on its DOM presence.

This is a **label-vs-semantics** miss (per
`feedback_label_vs_semantics.md`): the banner's existence was treated
as evidence of mock mode, instead of verifying the actual code path
the **Solve** button hits.

## Reconciliation in this PR

Per Option B in the reconciliation plan:

- **Reverted:** disclosure additions in
  `docs/v1_8_0_release_notes_DRAFT.md` and
  `docs/dmg_install_guide.md`.
- **Kept:** this audit doc, rewritten to reflect PR #103's findings.
- **Out of scope:** removing the stale wording from `README.md` and
  `USAGE.md` §4. Those are tracked alongside PR #103's banner removal
  (or a follow-up doc-sweep PR) so the in-app, README, and USAGE
  references all flip together.
- **Out of scope:** the GitHub release body for v1.8.0 was never
  amended. It correctly does not mention mock mode and needs no edit.

## Open follow-ups

1. **`README.md` lines 199-205** still claim *"The UI is currently in
   mock mode — clicking **Solve** returns hand-crafted fixture
   data."* Stale; should be removed in a follow-up. Track with
   PR #103.
2. **`USAGE.md` §4** ("The UI (currently mock mode)") and the line-622
   recap. Stale; same follow-up.
3. **`docs/dmg_v1_8_0_user_smoke_2026-05-27.md`** smoke verdict is
   based on a wrong premise; revisit whether the v1.8.0 .dmg user
   smoke result needs to be upgraded from PARTIAL to PASS once the
   stale banner is removed and the user can verify a real solve
   result via the GUI.

## What this PR does NOT do

- Does **not** modify product code, the `.dmg`, or the in-app banner
  (PR #103 owns the banner fix).
- Does **not** amend the public GitHub release body. The release body
  is correct as-is on mock-mode questions.
- Does **not** edit `README.md` or `USAGE.md`. Those edits ride with
  the banner-removal PR for a coherent flip.

## Risk classification

**Low-risk docs-only retraction.** This PR now touches one markdown
file (this audit, rewritten). The two product-facing docs are
restored to their pre-PR state. No code, no test, no .dmg. Suitable
for review alongside PR #103 — merge order should be: PR #103
(banner + product-code fix) first, then this audit (already aligned
with that fix). Or merge in either order; the two are independent
once the disclosure additions are reverted.
