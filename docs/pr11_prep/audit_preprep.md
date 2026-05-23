# PR 11 audit pre-prep — anticipated findings & pre-patches

**Status:** Pre-PR-11 reference. Read this BEFORE the audit agent fires post-implementation.
**Date:** 2026-05-22
**Scope:** Forecast the six highest-probability audit findings for PR 11 (library + macOS packaging), document pre-patches that can land before the audit, and set an expected verdict.

This doc complements `fanout_ready.md` (fire-when-PR-10-lands shortlist), `launch_kickoff.md` (full pipeline), `launch_readiness.md` (8/8 PASS verdict), and `audit_prompt.md` (the audit agent's 15-focus-area brief). It runs read-only — no source files touched.

---

## 1. Likely audit findings

Numbered to match the six user-flagged risk surfaces. Each: probability, severity-band the audit will likely assign, evidence anchor, and mitigation status.

### 1.1 PyInstaller `--add-binary` for `_rust.cpython-313-darwin.so` — **HIGH probability / must-fix band if absent**

**Risk:** THE load-bearing risk per `pr11_spec.md` §12.1, `launch_readiness.md` Check 1, and `fanout_ready.md` §5. PyInstaller's AST walker does NOT find `_rust.cpython-313-darwin.so` because PyO3 wires the import at C-API level (not via `import` statements PyInstaller can statically discover). Without explicit `--add-binary`, the bundled `.app` launches successfully then crashes on the first call into Rust — the worst-case user-experience failure mode (install succeeds, app appears to start, then dies on first solve). Three failure modes the audit will probe:
- (a) **`--add-binary` missing** — `scripts/build_macos_dmg.sh` PyInstaller invocation lacks the flag. Per `audit_prompt.md` focus area 4 (lines 68-72): auditor will intentionally omit `--add-binary` and assert the smoke catches it.
- (b) **In-bundle smoke test missing** — after PyInstaller produces the `.app`, the build script must run `python -c "from poker_solver import _rust; print(_rust)"` against the bundled python and fail the build on import error. Per spec §6.3 + §12.1 mitigation #2.
- (c) **`--add-binary` syntax wrong** — colon-separated `src:dest`. The dest path is the relative `.app` bundle location (`poker_solver`), not absolute. A typo or wrong dest path bundles the `.so` to the wrong location → silent import failure.

**Audit probability:** auditor reads `scripts/build_macos_dmg.sh`. If `--add-binary` is absent → must-fix (no other code change blocks PR more decisively). If smoke step is absent → should-fix (the `.app` may still work but failure surfaces post-install). Per `fanout_ready.md` line 122.

### 1.2 Code-signing chain optionality (signed + unsigned paths independent) — **MEDIUM probability / must-fix band if broken**

**Risk:** Per `pr11_spec.md` §6.7 + §11 #6 + `audit_prompt.md` focus area 8. The user runs without Apple Developer credentials, so `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` MUST produce a working unsigned `.app` + `.dmg`. Failure modes:
- (a) **Hard dependency on signing** — the script `set -e`s on a missing `Developer ID Application` cert or `$APPLE_ID` env var, even with skip flags. User gets a confusing error instead of a working unsigned build.
- (b) **`--skip-signing` flag not threaded through** — the script accepts the flag but `sign_and_notarize.py` is invoked unconditionally and dies.
- (c) **Committed credentials** — per spec §6.4 + §6.5 + `audit_prompt.md` focus area 6 (lines 79-85). Auditor will grep new files for `Developer ID Application: [A-Z]`, email patterns, password-like strings, team IDs. ANY hit → must-fix (security blocker).

**Audit probability:** auditor will run `./scripts/build_macos_dmg.sh --skip-signing --skip-notarization` and verify it produces a working unsigned `.app`. If it dies on missing credentials → must-fix. If credentials are committed → must-fix (security blocker, separate from functional).

### 1.3 DMG notarization (arm64-only commitment + `codesign --deep` walk) — **MEDIUM probability / should-fix band**

**Risk:** Per `pr11_spec.md` §6.4 + §11 + `audit_prompt.md` focus areas 5+11. Two distinct sub-risks:
- (a) **Universal2 leakage** — `arm64-only` is the locked target (PLAN.md "MacBook-only, 16 GB Apple Silicon"; spec §1.2 non-goal). DMG filename must be `Poker-Solver-${VERSION}-arm64.dmg`. If PyInstaller is invoked without arch flag, it may produce a universal2 binary (depending on host setup) → larger DMG + violates arm64-only commitment.
- (b) **`codesign --deep` unreliability** — Apple's `--deep` flag claims to walk PyInstaller bundles but is documented-unreliable. `scripts/sign_and_notarize.py` MUST do an explicit `find Contents -name "*.dylib" -o -name "*.so"` walk, sign each inner binary individually with the Developer ID + Hardened Runtime, then sign the outer `.app`. Missing the inside-out walk → notarization may pass but Gatekeeper or runtime-attached verification fails at user launch.

**Audit probability:** auditor will read `scripts/sign_and_notarize.py` for the explicit walk. If only `codesign --deep` is used → should-fix (Apple's tooling is best-effort, not guaranteed). If arm64 isn't explicitly set in PyInstaller args → should-fix (host default may save the day but committing relies on luck).

### 1.4 SQLite WAL mode — **LOW probability / must-fix band if absent**

**Risk:** Per `pr11_spec.md` §2.2 + `launch_readiness.md` Check 2 + `audit_prompt.md` focus area 1 (lines 45-49). `PRAGMA journal_mode = WAL` is the load-bearing concurrency setting: multiple readers can read while one writer writes — required for the UI library browser concurrent with `batch_solve` writes. Failure modes:
- (a) **PRAGMA missing** — default journal mode is `DELETE` (rollback journal). Concurrent reader during write → `database is locked` error. Per spec §2.2 line 77.
- (b) **PRAGMA set on wrong connection** — must be set on every `Library.open()` (per `agent_a_prompt.md` line 51), not just the first connection. SQLite WAL is per-database-file persistent once set, but defensive re-set ensures safety.
- (c) **Foreign keys OFF** — `PRAGMA foreign_keys = ON` is a separate pragma; required for schema integrity if the schema uses foreign keys.

**Audit probability:** auditor will grep `library_schema.sql` and `library.py` for `journal_mode = WAL`. Pre-stage is READY per `launch_readiness.md` Check 2; this finding is unlikely unless Agent A regresses.

### 1.5 gzip-6 compression on strategy blobs (bit-exact roundtrip) — **LOW probability / must-fix band if `np.allclose` used**

**Risk:** Per `pr11_spec.md` §2.4 + `launch_readiness.md` Check 4 + `audit_prompt.md` focus area 3 (lines 62-66). `gzip.compress(json_bytes, compresslevel=6)` (default level). The bit-exact contract is critical: `gzip` → `gunzip` → JSON parse → values comparing `==` to source (NOT `np.allclose`). Failure modes:
- (a) **Anti-pattern: `np.allclose` in roundtrip test** — passes tests but silently allows precision drift. Per audit focus area 3 explicit anti-pattern check (line 66): "if the roundtrip test uses `np.allclose` instead of `np.array_equal`, flag." Auditor will grep the test file.
- (b) **Wrong compresslevel** — level=9 is slower with marginal gain; level=1 is faster with significant size cost. Spec locks level=6 (default). Drift → should-fix.
- (c) **JSON serialization not deterministic** — `json.dumps(..., sort_keys=True, separators=(",", ":"))` is the locked form (per `pr11_spec.md` §2.3 for spot ID; gzip blob should follow same discipline). Non-deterministic dict ordering → non-reproducible compressed bytes.

**Audit probability:** auditor will read `tests/test_library.py::test_library_compression_preserves_bit_exact_strategy`. If `np.allclose` appears → must-fix (silent precision loss is a strategy display corruption vector). Pre-stage is READY per `launch_readiness.md` Check 4.

### 1.6 Schema migration loud-error path — **LOW probability / must-fix band if silent**

**Risk:** Per `pr11_spec.md` §11 #8 + `audit_prompt.md` focus area 10 (lines 101-104). `schema_version` mismatch must raise `LibrarySchemaError` (hard error) — silent migration risks corrupting a user's library. By contrast, `solver_version` mismatch is a soft `UserWarning` (different concern: the strategies were computed by a different solver build, but the schema layout is unchanged). Failure modes:
- (a) **Silent migration on schema-version mismatch** — opening an old library with `library_version=1` from a `library_version=2` codebase silently uses defaults. User loses data without warning.
- (b) **`solver_version` mismatch hard-errors** — too aggressive; should be a warning per spec.
- (c) **`LibrarySchemaError` not in `__init__.py`** — exception isn't importable from `poker_solver`. UI can't catch it cleanly.

**Audit probability:** auditor will run `tests/test_library.py::test_library_schema_version_mismatch_errors` (per `audit_prompt.md` line 104). If the test passes but Agent A's implementation uses a warning instead → must-fix.

---

## 2. Pre-patches that could land BEFORE PR 11 audit

Pre-stage is already strong (`launch_readiness.md` verdict READY, 8/8 PASS; `fanout_ready.md` confirms top-risk mitigation in §5). The candidate pre-patches below would tighten the audit surface further; all touch spec/prompt docs only, not source files (per the read-only constraint).

### Pre-patch A: harden Agent B's PyInstaller smoke step — **optional, low cost**

Add an explicit subsection in `agent_b_prompt.md` for `scripts/build_macos_dmg.sh` covering:
1. `--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"` (exact string).
2. Post-PyInstaller smoke step: run bundled python with `from poker_solver import _rust`; fail build on ImportError.
3. Explicit arm64 arch flag if needed.
4. Document the failure mode in the build-script header comment.

**Why defer:** `fanout_ready.md` §5 already restates this as Agent B's "critical path". Adding more would inflate the prompt for diminishing return.

### Pre-patch B: add Apple-credentials grep to audit checklist — **optional, low cost**

Already present in `audit_prompt.md` lines 84-85 + line 187. No pre-patch needed; the audit's grep covers this.

**Why defer:** Already in audit_prompt.md.

### Pre-patch C: confirm `np.array_equal` (not `np.allclose`) in Agent C's test stub — **optional, low cost**

Spot-check `agent_c_prompt.md`'s template for `test_library_compression_preserves_bit_exact_strategy`. If the template suggests `np.allclose`, flip to `np.array_equal` pre-emptively.

**Why defer:** `launch_readiness.md` Check 4 confirms `np.array_equal` is locked across all four anchors (spec §11 #4, `agent_a_prompt.md` line 299, `audit_prompt.md` focus area 3 line 66, test spec §9 #11).

**Recommendation:** None of the pre-patches are required. The pre-stage is sufficient (8/8 PASS in `launch_readiness.md`). If launching with extra paranoia, none of A/B/C move the needle.

---

## 3. Expected audit verdict given current prep quality

**Forecast: READY for commit AFTER must-fix items resolved** (per `audit_prompt.md` line 170 verdict taxonomy).

Rationale:
- `launch_readiness.md` is READY (8/8 PASS).
- 15 audit focus areas in `audit_prompt.md` map to well-documented surfaces with anchored spec sections.
- Most-likely must-fix findings are 1.1 (PyInstaller `--add-binary` for `_rust.so` missing OR in-bundle smoke absent) and 1.2 (committed Apple credentials OR `--skip-signing` path broken). 1.1 is the highest-impact surface in the entire PR.
- Likely should-fix findings: 1.3 (inside-out signing walk incomplete) and 1.3 (universal2 leakage if arm64 isn't explicit).
- Low-probability findings (1.4 WAL, 1.5 gzip-6, 1.6 schema-version) are pre-verified READY in `launch_readiness.md`.

**Expected severity counts at audit:** 0-2 must-fix (most likely 1, on PyInstaller `--add-binary` or unsigned-fallback path); 2-4 should-fix; 3-6 nice-to-fix.

**P(clean READY-no-patches verdict):** ~30%.
**P(READY-with-must-fix verdict):** ~55%.
**P(NOT-READY verdict):** ~15% (only if Agent B omits `--add-binary` AND the in-bundle smoke step both — but `fanout_ready.md` §5 reminds Agent B of the three-part defense at launch time).

---

## 4. Sequencing: when this doc fires

**Trigger:** This file becomes the audit-prep reference the moment PR 11 audit agent is dispatched per `fanout_ready.md` §6.

**Read order at audit time:**
1. `audit_prompt.md` (the audit brief — primary input).
2. This file (anticipated findings — calibrate expectations).
3. `launch_readiness.md` (proves the pre-stage 8/8 gates passed).
4. `audit_report.md` (the audit agent's output — compare against §1 forecasts here).

**Post-audit action:**
- If audit finds <=2 must-fix items matching §1.1/1.2 forecast → apply patches per audit, re-test, commit.
- If audit finds must-fix items NOT in §1 → those are blind spots; root-cause and update this doc for PR 12+.
- If audit reports NOT-READY → halt, escalate to user, do not merge. Special attention: NOT-READY on §1.1 means the `.app` will crash on user's first solve, even though install succeeded.

**This doc is reference-only.** Do NOT modify source files based on §1 forecasts before the audit runs — the audit is what catches the actual bugs. Use this only to (a) prime expectations and (b) accelerate post-audit triage.

---

## Anchors

- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/audit_prompt.md`
- Launch readiness: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_readiness.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/fanout_ready.md`
- Launch kickoff: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/launch_kickoff.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr11_prep/pr11_spec.md`
- Top-risk surface: spec §6.3 + §12.1 (PyInstaller `--add-binary`)
- Locked defaults D1-D13: spec §13
