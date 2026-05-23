# PR 7 audit pre-prep — anticipated findings & pre-patches

**Status:** Pre-PR-7 reference. Read this BEFORE the audit agent fires post-implementation.
**Date:** 2026-05-22
**Scope:** Forecast the seven highest-probability audit findings, document pre-patches that can land before the audit, and set an expected verdict.

This doc complements `launch_readiness.md` (which audits the prompts) and `audit_prompt.md` (which is the audit agent's brief). It runs read-only — no source files touched.

---

## 1. Likely audit findings

Numbered to match the seven user-flagged risk surfaces. Each: probability, severity-band the audit will likely assign, evidence anchor, and mitigation status.

### 1.1 Brown binary subprocess invocation correctness — **MEDIUM probability / should-fix band**

**Risk:** `noambrown_wrapper.py` shells out to `river_solver_optimized` via `subprocess.run`. Three failure modes the audit will probe:
- (a) **Argument quoting** — bet-sizes list passed as `--bet-sizes 0.5,1` (comma-joined string), not as separate args. `cpp/src/main.cpp` parses one comma-list arg; passing as Python list would shell-quote it wrong.
- (b) **stdout vs JSON-file** — `--dump-strategy /tmp/...json` writes strategy file; stdout carries logging. Wrapper must parse the JSON file path, NOT `result.stdout`.
- (c) **Subprocess timeout** — 2000 iters on a river spot is ~30-90 s on M-series silicon. Default `subprocess.run` has no timeout (good); audit will flag if a too-tight `timeout=` is set, or none and it hangs CI.

**Audit probability:** the auditor will inspect `noambrown_wrapper.py:run_brown_solver()` and verify all three. If `result.stdout` is parsed as JSON the audit will mark must-fix.

### 1.2 DCFR flag invocation accuracy — **LOW probability / must-fix band IF wrong**

**Risk:** Exact flag string `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7 --iters 2000`. Common slip-ups:
- `--dcfr-beta 0.5` instead of `0` (audit anchor: `audit_prompt.md:63` — "especially β=0, not 0.5").
- `--dcfr-gamma 2.0` (float string) — Brown's CLI parses ints; passing `"2.0"` would fail-parse and silently fall to default γ=2 (lucky). The audit will still flag the type-mismatch as a smell.
- `--seed 7` missing — Brown's default is 7 per `cpp/src/main.cpp:36`, so behavior matches, but spec §11 #1 mandates explicit pass for paranoia.

**Status:** Flags pre-verified in `launch_readiness.md` Check 2 (READY) and `fanout_ready.md` line 5. Pre-stage clean.

### 1.3 Raise canonicalization round-trip — **HIGH probability / must-fix band if buggy**

**Risk:** The load-bearing parity surface. `canonicalize_our_history` must convert `r<to_total>` → `r<delta>` using accumulated per-player contribution state. Failure modes:
- **State reset between streets** — preflop/flop/turn contributions must reset at street boundaries. Drop-state-on-street bug → all river spots mis-canonicalize (silently passes parity but compares wrong infosets).
- **Aggressor-tracking ambiguity** — `delta = to_total - prev_aggressor_contrib`. If "prev aggressor" is misidentified after a check-raise sequence, deltas drift.
- **Hand-built round-trip identity** — `canonicalize_our_history(canonicalize_brown_history(h)) == h` for the 10 cases in `agent_c_prompt.md:162-191`. Agent C's prompt flags case 8 (`b500/r9000 ↔ b500A`) as needing Agent A verification (`launch_readiness.md` residual #2).

**Audit probability:** auditor will quote `audit_prompt.md:47-54` and check both directions of the round-trip against the 10-case fixture in `test_noambrown_self_sanity.py`.

### 1.4 xdist subprocess collision on `/tmp/spot_<id>.json` — **MEDIUM probability / must-fix band**

**Risk:** Spec §9 #8 already calls this out. If Agent A names the dump file `/tmp/spot_<spot_id>.json` (deterministic), two xdist workers running the same spot simultaneously will clobber. Even with distinct spot IDs, retry-on-failure can collide.

**Required:** `tempfile.NamedTemporaryFile(suffix=".json", delete=False)` per call; `os.unlink` in `finally`. Audit anchor: `audit_prompt.md:95-97` ("subprocess invocations use `tempfile.NamedTemporaryFile` per call (NOT a shared `/tmp/spot_<id>.json`)").

**Pre-patch candidate:** add a smoke test in `test_noambrown_self_sanity.py` that calls `run_brown_solver()` twice in succession (under monkey-patched binary) and asserts no two calls share a path. Currently spec §10 Agent C lists 8 tests; this would be a 9th. Defer to PR 7 unless we expand the spec.

### 1.5 Tolerance numbers (5e-3 / 1e-3 × pot) — **LOW probability / must-fix if relaxed**

**Risk:** Per-action `5e-3`, per-spot game value `1e-3 × pot`. Audit anchor: `audit_prompt.md:79-81`. Common drift: silently bumping to `1e-2` to make a flaky spot pass.

**Status:** `launch_readiness.md` Check 3 confirms READY across all six docs. Pre-stage clean. Audit will check fixture, harness, and self-sanity tests — all three must use 5e-3 / 1e-3.

### 1.6 License compliance — **LOW probability / must-fix if violated**

**Risk:** MIT permits the wrapper + binary invocation. Failure modes:
- Any verbatim copy of `cpp/src/*.cpp` algorithm into Python (would be a derivative work under MIT, requires attribution; under AGPL would taint the repo).
- Missing attribution docstring in `poker_solver/parity/noambrown_wrapper.py` (spec §8 mandates).
- Bundling the binary in the wheel (the spec doesn't ship the binary; only the build script).

**Status:** `launch_readiness.md` Check 5 confirms READY. Wrapper depends only on Brown's public CLI surface + JSON output schema. Audit anchor: `audit_prompt.md:88-93`.

### 1.7 macOS Xcode CLT / `-march=native` portability — **MEDIUM probability / should-fix band**

**Risk:** `cpp/CMakeLists.txt` uses `-O3 -march=native -ffast-math` (non-MSVC branch). Two slips:
- (a) **CI runs on Linux x86_64** — `-march=native` produces a binary that won't run on M-series Macs and vice versa. The build script regenerates per-host (out-of-tree), so this is fine PROVIDED the script doesn't cache a binary across host transitions.
- (b) **Xcode CLT missing** — `xcode-select --install` not run → `cmake` finds `c++` but compile fails on `<filesystem>` or similar. Soft-fail path (`exit 0`) must catch this and skip-cleanly, not abort.

**Status:** Spec §6 mandates soft-fail; `launch_readiness.md` Check 6 confirms three-layer skip strategy. Audit will verify the build script `set -e` does not pre-empt the soft-fail branch.

---

## 2. Pre-patches that could land BEFORE PR 7 audit

Pre-stage is already strong (`launch_readiness.md` is READY-WITH-PATCHES, P1 patch applied per `fanout_ready.md:5`). The two candidate pre-patches below would tighten the audit surface further; both touch spec/prompt docs only, not source files.

### Pre-patch A: harden `agent_a_prompt.md` subprocess section — **optional, low cost**

Add an explicit subsection in `agent_a_prompt.md` covering:
1. `--bet-sizes` as comma-joined string (not list).
2. Parse `--dump-strategy` output file, NOT stdout.
3. `subprocess.run(..., timeout=None)` (or document the chosen timeout with rationale).
4. `tempfile.NamedTemporaryFile(suffix=".json", delete=False)` for dump path.

**Why defer:** Agent A's existing prompt is detailed (already covers item 4 via `audit_prompt.md:95-97`). Adding more would inflate the prompt for diminishing return. The audit catches these regardless.

### Pre-patch B: add 9th self-sanity test for `/tmp` collision — **optional, low cost**

Extend `agent_c_prompt.md` test list with `test_run_brown_solver_unique_dump_paths` that mocks the binary and asserts two concurrent calls use distinct paths.

**Why defer:** `audit_prompt.md:95-97` already mandates the audit check the source-code shape directly. A unit test would be redundant.

**Recommendation:** Neither pre-patch is required. The pre-stage is sufficient. If launching with extra paranoia, apply Pre-patch B (single test) for belt-and-suspenders coverage.

---

## 3. Expected audit verdict given current prep quality

**Forecast: READY for commit AFTER must-fix items resolved** (per `audit_prompt.md:170` verdict taxonomy).

Rationale:
- The six gates in `launch_readiness.md` are READY (one was patched). Spec/prompt surface is clean.
- The 15 audit focus areas in `audit_prompt.md` map to well-documented surfaces with anchored implementations.
- Most-likely must-fix findings are 1.3 (raise canonicalization edge cases — particularly case 8 of the round-trip fixture) and 1.4 (xdist collision IF Agent A picks a deterministic dump path).
- Likely should-fix findings: 1.1 (subprocess argument quoting / timeout) and 1.7 (build script soft-fail edge cases on missing Xcode CLT).
- Low-probability findings (1.2, 1.5, 1.6) are pre-verified READY.

**Expected severity counts at audit:** 0-2 must-fix (most likely 1, on raise canonicalization edge case or `/tmp` collision); 2-4 should-fix; 3-6 nice-to-fix.

**P(clean READY-no-patches verdict):** ~30%.
**P(READY-with-must-fix verdict):** ~55%.
**P(NOT-READY verdict):** ~15% (only if Agent A botches raise canonicalization state machine).

---

## 4. Sequencing: when this doc fires

**Trigger:** This file becomes the audit-prep reference the moment PR 7 audit agent is dispatched per `fanout_ready.md` §6.

**Read order at audit time:**
1. `audit_prompt.md` (the audit brief — primary input).
2. This file (anticipated findings — calibrate expectations).
3. `launch_readiness.md` (proves the pre-stage gates passed).
4. `audit_report.md` (the audit agent's output — compare against §1 forecasts here).

**Post-audit action:**
- If audit finds <=2 must-fix items matching §1.3/1.4 forecast → apply patches per audit, re-test, commit.
- If audit finds must-fix items NOT in §1 → those are blind spots; root-cause and update this doc for future PRs.
- If audit reports NOT-READY → halt, escalate to user, do not merge.

**This doc is reference-only.** Do NOT modify source files based on §1 forecasts before the audit runs — the audit is what catches the actual bugs. Use this only to (a) prime expectations and (b) accelerate post-audit triage.

---

## Anchors

- Audit brief: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt.md`
- Launch readiness: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/launch_readiness.md`
- Fan-out shortlist: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/fanout_ready.md`
- Spec: `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`
- Brown source: `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/`
