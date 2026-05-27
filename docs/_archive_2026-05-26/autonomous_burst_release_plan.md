# Autonomous burst release plan

Updated 2026-05-23 — PR 10b folded into scope. Plan now covers three
ships + one re-package, landing v1.2.0 .dmg as the first complete
downloadable artifact since v1.0.0.

## 1. Ship order

Sequential; each leg gates the next.

1. **PR 8 → v1.0.1** (PATCH) — NEON kernels + PCS infra + layout
   primitive. Perf-infra only; no end-user-visible feature. Re-audit
   clears, commit, sync.
2. **PR 9 → v1.1.0** (MINOR) — HUNL preflop (Python + Rust); real-tier
   solving for preflop spots. Additive, no API removal.
3. **PR 10b → v1.2.0** (MINOR) — real-solver UI bindings; replaces the
   mock layer shipped in PR 10a. Depends on PR 9 landing first (UI
   needs the real preflop engine on main). Closes the "GUI doesn't
   actually use the real engine" gap. User-facing capability change.
   MINOR is correct — mirrors v0.6.0 (UI scaffold) being MINOR; no
   breaking public-API change so NOT v2.0.0.
4. **Re-package via PR 11 pipeline → v1.2.0 .dmg** — follow-up, not a
   separate semver bump. Re-run PR 11's .dmg pipeline against v1.2.0
   content (PR 8 + PR 9 + PR 10b cumulative). The v1.2.0 .dmg replaces
   v1.0.0's "PR 7 + mock UI" .dmg on the GitHub release page.

## 2. Per-version cumulative content

| Version  | Adds                                        | User-visible? |
|----------|---------------------------------------------|---------------|
| v1.0.1   | NEON kernels + PCS infra + layout primitive | No (perf)     |
| v1.1.0   | + HUNL preflop (Py + Rust); real preflop    | Yes           |
| v1.2.0   | + Real-solver UI bindings (mock retired)    | Yes           |
| v1.2.0 .dmg | Cumulative — first complete artifact since v1.0.0 | Yes |

## 3. Time estimates per leg

- PR 8 ship — ~30 min (re-audit clears, commit, sync)
- PR 9 ship — ~60 min (patch-fix + commit + sync)
- PR 10b ship — ~3-6 hours (implementer + audit + ship)
- Re-package — 1-2 hours (depends on codesign tier)

**Total burst ETA: ~6-10 hours from now.**

## 4. Gating + risk

- PR 10b cannot start until v1.1.0 is on `origin/main`. The real preflop
  engine is the binding point; mock-swap without it would re-introduce
  the gap PR 10b is meant to close.
- Re-package cannot start until v1.2.0 tag is published. Pipeline
  consumes the tagged tree; no point running it against in-flight code.
- If PR 10b audit returns NEEDS-FIX, the burst stops at v1.1.0; .dmg
  re-package deferred. v1.1.0 alone does not warrant a new .dmg (the
  mock UI would misrepresent the v1.1.0 capability).
