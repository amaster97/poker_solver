# PR 11 launch-readiness verification

**Date:** 2026-05-22
**Reviewer:** orchestrator verification agent (read-only)
**Verdict:** **READY**
**Scope under review:** PR 11 spec + Agent A/B/C prompts + audit prompt — alignment with PR 9 (preflop) and PR 10 (UI scaffold + solver swap) post-landing.

---

## 1. Eight required checks

### Check 1 — PyInstaller `--add-binary` for `_rust.cpython-313-darwin.so` (PASS)

- `pr11_spec.md` §6.3 line 357: explicit `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` in canonical PyInstaller invocation.
- `pr11_spec.md` §12.1 (the spec's top risk): "PyInstaller may fail to bundle the Rust extension" — calls `--add-binary` "the load-bearing flag" and requires a smoke-test step that runs `from poker_solver import _rust` inside the bundle.
- `agent_b_prompt.md` lines 64-76 ("Top risk to flag prominently") restate the requirement plus three required mitigations: (1) explicit `--add-binary`, (2) in-bundle smoke-test step before codesign, (3) documented failure mode.
- `agent_b_prompt.md` line 202: same flag inside the canonical invocation.
- `audit_prompt.md` focus area 4 (lines 68-72): the auditor must verify `--add-binary` AND the smoke-test step exists; the audit agent will intentionally omit `--add-binary` and assert the smoke test catches it.

### Check 2 — Library SQLite WAL mode (PASS)

- `pr11_spec.md` §2.2 line 43: `PRAGMA journal_mode = WAL` baked into `library_schema.sql`.
- `pr11_spec.md` §2.2 line 77: "WAL mode is the load-bearing concurrency setting: multiple readers can read while one writer writes."
- `agent_a_prompt.md` line 51 (locked default): "SQLite mode: WAL ... one writer, many readers. Set on every `Library.open()`. Foreign keys ON."
- `agent_a_prompt.md` line 311 (critical correctness item 3): WAL + write-mutex pattern specified.
- `audit_prompt.md` focus area 1: WAL verification required.

### Check 3 — Spot ID is deterministic (SHA-256 of canonicalized spot JSON) (PASS)

- `pr11_spec.md` §2.3 line 81: `sha256(canonicalized_spot_json).hexdigest()` with 7 canonicalization rules (board sorting, int-cent stacks, bet-menu sort, etc.).
- `pr11_spec.md` §2.3 rule 7: `json.dumps(..., sort_keys=True, separators=(",", ":"))` — deterministic byte serialization.
- `pr11_spec.md` §11 critical items 1+2: cross-machine determinism + difference-on-meaningful-change explicitly locked.
- `agent_a_prompt.md` lines 272-287 (critical correctness item 1): same 7 rules restated; α/β/γ hyperparameters explicitly EXCLUDED (locked at α=1.5, β=0, γ=2.0).
- `audit_prompt.md` focus area 2 (lines 50-60): full canonicalization rule set restated.

### Check 4 — Compression is gzip on strategy blobs (PASS)

- `pr11_spec.md` §2.4 line 101: `gzip.compress(json_bytes, compresslevel=6)` (gzip default).
- `pr11_spec.md` §2.4 line 103: "Bit-exact roundtrip required — the float values must compare `==` after roundtrip."
- `agent_a_prompt.md` line 52: gzip `compresslevel=6` locked; lines 291-307 (critical correctness item 2) detail the bit-exact contract.
- `audit_prompt.md` focus area 3 (lines 62-66): anti-pattern check ("if the roundtrip test uses `np.allclose` instead of `np.array_equal`, flag — that's NOT bit-exact, just float-close").

### Check 5 — Apple Developer optional path documented (PASS)

- `pr11_spec.md` §6.7 (lines 464-476): full unsigned fallback workflow — `--skip-signing --skip-notarization` + two bypass methods (right-click "Open" / `xattr -d com.apple.quarantine`).
- `pr11_spec.md` §13 decision 1: "Apple Developer enrollment. Default: optional."
- `pr11_spec.md` §12.2: explicit statement that PR 11 is shippable without the $99/yr cost.
- `agent_b_prompt.md` line 56: locked default "OPTIONAL"; lines 286-296: full unsigned fallback spec.
- `audit_prompt.md` focus area 8 (lines 91-95): unsigned-fallback functional verification required.

### Check 6 — arm64-only build target (PASS, matches PLAN.md)

- `PLAN.md` line 15: "Compute: **MacBook-only.** 16 GB Apple Silicon. No cloud spend." Confirms hardware target.
- `pr11_spec.md` §1.2 non-goal (line 20): "No universal2 (x86_64 + arm64) binary. arm64-only matches PLAN.md's stated hardware."
- `pr11_spec.md` §6.6 line 449 (DMG filename pattern): `Poker-Solver-${VERSION}-arm64.dmg`.
- `pr11_spec.md` §13 decision 6: "Bundle architecture target. Default: arm64 only."
- `agent_b_prompt.md` line 54: "Bundle architecture: arm64 only. No universal2."
- `audit_prompt.md` focus area 5: arm64-only verification required.

### Check 7 — No new external service dependencies (PASS)

- `pr11_spec.md` §1.2 (non-goals): no cloud library, no multi-user, no auto-population scheduler, no neural-warmstart consumption.
- `pr11_spec.md` §8 line 506: explicit "No new runtime dependencies (SQLite, gzip, hashlib, json are stdlib)." PyInstaller goes under `[project.optional-dependencies] distribution` only — never installed by default.
- `pr11_spec.md` §11 critical item 10: "No new runtime dependencies."
- `agent_a_prompt.md` line 56: "No new runtime dependencies. Stdlib only."
- `audit_prompt.md` focus area 7: verifies `[project.dependencies]` unchanged.
- Apple Notarization is the only external service touched and is gated behind the OPTIONAL signed path; the unsigned fallback eliminates it entirely. No auth providers, no cloud, no telemetry.

### Check 8 — Library API surface compatible with PR 10a/10b's UI library viewer expectations (PASS)

- **PR 10b is pure solver-swap.** Confirmed by reading `docs/pr10_prep/pr10b_spec.md` end-to-end: it deletes `ui/mock_solver.py`, replaces with real `solve_hunl_postflop` / `solve_hunl_preflop` dispatch in `ui/state.py`, and adds `on_progress` callback. **No call to `Library.put/get/list` anywhere in PR 10b.**
- **PR 10a leaves a stub** at `ui/views/library_browser.py` (per `docs/pr10_prep/pr10_spec.md` §3.5): static dialog, disabled "Load from disk" button, three faked rows. The stub's only contract on PR 11 is the "grows a real loader; everything else is unchanged" wiring point.
- **PR 11 extends, doesn't break, the stub.** `pr11_spec.md` §4.1 grows the stub into a real browser: filter form + sortable `SpotMetadata` table + per-row Load/Export/Delete + footer `LibraryStats`. The `Library.list()` / `Library.get()` / `Library.put()` signatures defined in `pr11_spec.md` §3.1 are PR 11's own surface — PR 10 did NOT pre-commit to a Library API, so there is no risk of signature drift between PRs.
- `agent_a_prompt.md` §"Public API contract" (lines 62-235) locks the `Library.open/put/get/list/export/import_/delete/stats/close` signatures.
- `pr11_spec.md` §4.4: the spec explicitly notes "the library browser ships with a text-summary fallback, and the range matrix is a PR 11.5 polish item if PR 10's interface is unstable" — i.e., the design hedges against PR 10 component churn.
- `audit_prompt.md` focus area 14 (lines 119-124): asserts the stub → loader transition; references `asyncio.to_thread` (per spec §4.5) for non-blocking gzip decompress.

---

## 2. Residual findings

**None blocking.** Two minor items worth noting:

1. **PR 10b's `on_progress` callback is not referenced by PR 11.** PR 11 stores `SolveResult` after the solve completes; it does NOT subscribe to progress callbacks. This is correct — `Library.put` is a post-solve write — but worth confirming the saved spot's `iterations` / `exploitability_history` fields capture the final state (they do; spec §2.2 schema has `iterations` and `exploitability` columns, the latter being `exploitability_history[-1]`).

2. **PR 9 preflop integration is one-line.** `pr11_spec.md` §2.3 rule 4 mentions "initial-ranges (PR 9 preflop), serialized as a sorted hand-list with each hand's canonical form." `agent_a_prompt.md` §"Public API contract" line 84 already has `initial_ranges: tuple[tuple[str, str], ...] | None` on `SpotDescription`. PR 9 lands first; the canonicalization rule handles preflop spots transparently.

---

## 3. PR 10b ↔ PR 11 API compatibility (explicit confirmation)

**PR 10b does NOT call `Library.put` / `Library.get` / `Library.list`.** PR 10b's scope (per `pr10b_spec.md`) is strictly the mock → real solver swap. The library viewer remains a PR 10a stub until PR 11 grows it into a real loader. Therefore there is no API contract between PR 10b and PR 11 to verify — the contract is between PR 11's Agent A (library module) and PR 11's own UI integration (`pr11_spec.md` §4). Both live inside PR 11.

The audit prompt's focus area 14 explicitly frames the transition as "PR 10 left a stub ... PR 11 grows it into a real loader" — which is the correct framing.

---

## 4. Verdict

**READY.** All eight checks pass with explicit evidence in `pr11_spec.md`, the three agent prompts, and `audit_prompt.md`. No patches required. The pre-drafted prompts remain aligned with PR 9 (preflop) landing first and PR 10 (UI scaffold + solver swap) landing second; PR 11 is purely additive on top of both.
