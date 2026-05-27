# Cross-verification: CHANGELOG.md vs v1_8_0_release_notes_DRAFT.md
**Date:** 2026-05-26
**Scope:** Mutual consistency check on v1.8.0 key claims
**Mode:** READ-ONLY (no auto-apply of fixes)

## Sources

- `/Users/ashen/Desktop/poker_solver/CHANGELOG.md` — v1.8.0 entry at lines 16-58 (~43 lines total for the new release section)
- `/Users/ashen/Desktop/poker_solver/docs/v1_8_0_release_notes_DRAFT.md` — full 554-line draft

## Headline finding

The two documents are **directionally consistent on the items they both cover**, but the CHANGELOG.md v1.8.0 entry is dramatically thinner than the release notes draft. The CHANGELOG explicitly defers to the draft (line 22-23: "See `docs/v1_8_0_release_notes_DRAFT.md` for the full forthcoming entry") so much of the draft's content is unmentioned in the CHANGELOG. This means several items will register as INFO (one-side-only) rather than FAIL. No direct contradictions found on items both files cover.

## Per-item check

### 1. v1.8.0 SIMD perf claim (measured ~1.0x, not 4-8x)

**Verdict: PASS (with caveat — CHANGELOG silent on the bare number, but consistent where it speaks)**

- **Release notes DRAFT** (lines 38-47, 87-90, 282-289, 522-525): Explicitly states "measured wall-clock impact on Apple Silicon (M4 Pro, aarch64) is within noise (~1.0x)", attributes to LLVM `-O3` autovec covering small-slice case, explicitly notes the projected 4-8x did NOT materialize, and that the W3.4 unblock was via fixture-repurposing NOT v1.8 SIMD perf gain.
- **CHANGELOG.md** v1.8.0 entry (lines 16-58): Says only "the cross-platform SIMD work" is folded in; no perf number quoted in the v1.8.0 section.
- **CHANGELOG.md** v1.5.0 "Deferred to v1.5.1+" section (lines 219-225): Explicitly references the v1.8 measured ~1.0x figure: "SIMD kernels for vector-shape arithmetic (subsequently wired in v1.8; empirical bench measured ~1.0x on Apple Silicon for the vector-form CFR workload — LLVM autovec at `-O3` already covered the small-slice case, and the bottleneck is per-iter scalar work outside the SIMD inner loops. Primary value is portability + a stable hand-written floor. See `docs/v1_8_simd_perf_benchmark_2026-05-26.md`.)."

Both files cite the **same benchmark doc** (`docs/v1_8_simd_perf_benchmark_2026-05-26.md`), use the **same 1.0x measured figure**, attribute to the **same root cause** (LLVM autovec at `-O3`), and **agree the primary value is portability**. No disagreement found.

### 2. .dmg fork-bomb status (PR #42 / 728206e + chance-node validation PR #69 / 98fb503)

**Verdict: PARTIAL PASS — PR #42 fully agrees; PR #69 / 98fb503 chance-node validation NOT FOUND in EITHER file**

- **PR #42 / 728206e** — both files agree:
  - Release notes DRAFT lines 102-105, 484, 217-225: PR #42 (`728206e`) adds `multiprocessing.freeze_support()` guard to PyInstaller entry point.
  - CHANGELOG lines 27-43, 40-42: Identical claim, same commit hash `728206e`, same root cause (`multiprocessing.freeze_support()` missing).
- **PR #69 / 98fb503 chance-node validation ship-blocker** — `grep` for `PR #69`, `98fb503`, "chance-node validation" in **both** files returns ZERO hits. Neither document mentions PR #69 as a ship-blocker. The user's prompt asserts this is a load-bearing fix; if so, **both files need to be updated**.

### 3. v1.6.1 status (HOLD LIFTED, fixes folded into v1.8.0)

**Verdict: PASS**

- **Release notes DRAFT** lines 160-165: "v1.6.1 ship hold has been lifted per `docs/v1_6_1_ship_hold_review_2026-05-26.md`."
- **CHANGELOG.md** v1.7.0 status (lines 75-78): "v1.6.1 engine bundle: **HOLD lifted** per `docs/v1_6_1_ship_hold_review_2026-05-26.md`. Bundle has shipped piecewise on `origin/main` (PR 50, 51, 52, 54, 55, 56, 53b, 53c) and is folded into v1.8.0."
- **CHANGELOG.md** v1.8.0 lead (lines 18-19): "folds in the v1.6.1 engine bundle (shipped piecewise on `main`)".

Both reference the same review doc, the same piecewise-on-main mechanism, the same HOLD LIFTED status. Aligned.

### 4. v1.7.1 status (CLOSED-AS-OBSOLETE, landed piecewise)

**Verdict: PASS**

- **Release notes DRAFT** lines 161-163: "No formal `v1.7.1` tag was created (per `docs/v1_7_1_tag_decision_2026-05-26.md`); the fixes are folded into this release."
- **Release notes DRAFT** lines 5-9: "engine + parity fixes from the v1.7.1 bundle and v1.7.2 (.dmg fork-bomb fix + CI hardening) are folded into v1.8.0".
- **CHANGELOG.md** lines 20-22: "Per `docs/v1_7_1_tag_decision_2026-05-26.md`, neither v1.7.1 nor v1.7.2 will be tagged; v1.8.0 is the next clean release boundary."

Both cite the same decision doc, same outcome (not tagged, folded forward). Neither uses the literal phrase "CLOSED-AS-OBSOLETE" but the semantic meaning matches. Aligned.

### 5. A83 33pp gap status (Nash multiplicity EMPIRICALLY CONFIRMED via PR #68)

**Verdict: FAIL on "EMPIRICALLY CONFIRMED" — both files explicitly say the opposite**

- **Release notes DRAFT** lines 310-360 ("Known issues remaining"): States Nash-multiplicity component is **"LEADING HYPOTHESIS, empirical probe PENDING"** and "**NOT YET empirically confirmed**". Details the original A83 Track A perturbed-seed probe was INVALIDATED (no-op path due to `chance_outcomes()` empty when `initial_hole_cards = None`). A corrected probe via `solve_range_vs_range_nash` is **queued**, not done.
- **CHANGELOG.md** v1.8.0 entry: Does NOT mention A83 at all directly. The CHANGELOG defers entirely to the draft for engine-acceptance details.
- **No mention of PR #68** in either file (`grep "PR #68"` returns zero hits).

This is the **most important disagreement** vs the user's prompt: the user asserts PR #68 EMPIRICALLY CONFIRMED Nash multiplicity, but the release notes draft explicitly says the probe is PENDING / NOT YET CONFIRMED and that the prior probe was INVALIDATED. The CHANGELOG is silent on it (defers to draft, so it inherits the draft's "PENDING" framing).

**If PR #68 actually did empirically confirm Nash multiplicity**, the release notes DRAFT lines 310-360 are stale and would need to be updated to reflect the confirmation. If PR #68 did NOT confirm it, then the user's prompt has an erroneous assertion. **The draft as-written is internally consistent with the CHANGELOG (both treat A83 Nash multiplicity as unconfirmed); neither file references PR #68.**

### 6. Cleanup / lint / mypy (PR #43 + PR #46)

**Verdict: INFO (release notes mention; CHANGELOG does NOT in the v1.8.0 entry)**

- **Release notes DRAFT** lines 122-136 ("§3. Lint / format / deps green-up"): Explicitly describes **PR #43** (`cfc6bc5`) green-up: `cargo clippy` clean, `ruff check` clean, `ruff format` clean, `black` removed in favor of `ruff format`, `rich>=13.0` added as explicit runtime dep.
- **Release notes DRAFT** lines 240-243: Mentions **PR #46** — "`mypy` resolves 7 substantive type errors (post-cleanup follow-up)".
- **CHANGELOG.md** v1.8.0 entry: **No mention of PR #43 or PR #46.** The CHANGELOG v1.8.0 section only covers (1) the v1.8.0 framing paragraph, (2) the .dmg fork-bomb fix (PR #42), and (3) the shim known-issue. The lint/mypy cleanup is silent.

This is a documented one-side-only INFO, not a disagreement — but a noteworthy CHANGELOG gap if a clean CHANGELOG record of v1.8.0 cleanup is desired.

### 7. Persona count (10 PASS / 4 PARTIAL / 2 BLOCKED / 1 FAIL)

**Verdict: FAIL — release notes draft says 9/5/2/1, NOT 10/4/2/1**

- **Release notes DRAFT** lines 265-275 ("§8. Persona test status"):

  | Verdict | Count |
  |---|---|
  | PASS | **9** |
  | PARTIAL | 5 |
  | BLOCKED | 2 |
  | FAIL | 1 |

  Note the draft also flags W2.3 as PENDING and explicitly says "Final tally will be 9 or 10 PASS / 1 or 2 BLOCKED depending on the wall-clock measurement."

- **CHANGELOG.md** v1.8.0 entry: Persona count is NOT mentioned in CHANGELOG.

User prompt asserts the target is 10/4/2/1. The draft is at 9/5/2/1 (one fewer PASS, one more PARTIAL). The draft itself says this could flip to 10 PASS / 1 BLOCKED **if** the W2.3 retest passes. This may be a "snapshot taken before W2.3 came back" situation.

**Discrepancy types:**
- PASS: 9 (draft) vs 10 (prompt) → off by 1
- PARTIAL: 5 (draft) vs 4 (prompt) → off by 1
- BLOCKED: 2 (draft) vs 2 (prompt) → MATCH
- FAIL: 1 (draft) vs 1 (prompt) → MATCH

This looks like a one-workflow swing (most likely the W2.3 retest landing, which would flip W2.3 BLOCKED→PASS and... that would give 10 PASS / 5 PARTIAL / 1 BLOCKED / 1 FAIL — which doesn't match the prompt's 10/4/2/1 either). A 4 PARTIAL count would require another PARTIAL→PASS reclassification beyond W2.3 (e.g., a W2.x or W3.3 promotion). Without source data, the safe interpretation is: **the draft persona counts are stale relative to the prompt's 10/4/2/1 expectation**, OR **the prompt's expectation is incorrect**. Recommend retest snapshot review before publish.

### 8. Known issues list (pyenv arch hazard + poker-solver shim quirk)

**Verdict: PARTIAL PASS — `poker-solver` shim quirk: PASS; pyenv arch hazard: FAIL (NOT in either file's v1.8.0 known issues)**

- **`poker-solver` shim quirk** — both files mention this:
  - Release notes DRAFT lines 386-396 ("Known issues remaining"): Full description with both workarounds (`./.venv/bin/poker-solver ...` and `python -m poker_solver.cli ...`), cleanup instructions (`pip uninstall poker_solver`), points to `docs/poker_solver_shim_fix_2026-05-26.md`, notes it's pre-existing dev-environment quirk.
  - CHANGELOG lines 45-58 ("Known issues / Installation notes"): Same two workarounds (identical ordering), same cleanup instruction, same doc reference, same "pre-existing dev-environment quirk (not a v1.8 regression)" framing. The release notes draft explicitly notes "The CHANGELOG carries the same workaround text under v1.8.0 known issues (PR #58)" confirming this was intentionally mirrored.

- **pyenv arch hazard** — neither file's v1.8.0 known issues mentions it directly:
  - `grep "pyenv"` in release notes DRAFT: 0 hits.
  - `grep "pyenv"` in CHANGELOG.md: 1 hit at line 671 (v1.2.1 "incompatible architecture" historical fix), but NOT in the v1.8.0 known-issues list.
  - The release notes DRAFT v1.8.0 known issues lists 4 items (A83 deep-cap divergence, Gate 4 200K validation, shim quirk, fractional frequencies, notarization) — no pyenv arch hazard item.

If pyenv arch hazard is meant to be a v1.8.0 known issue (per `feedback_dotso_arch_check.md`), it is **missing from both documents** and needs to be added to both for consistency with the prompt's expectation.

## Overall verdict

**Mostly consistent where both files speak, but with three significant gaps and discrepancies vs the prompt's expectations:**

| # | Item | Verdict |
|---|---|---|
| 1 | SIMD ~1.0x speedup | **PASS** |
| 2a | .dmg fork-bomb PR #42 / 728206e | **PASS** |
| 2b | PR #69 / 98fb503 chance-node validation ship-blocker | **FAIL — not in either file** |
| 3 | v1.6.1 HOLD LIFTED / folded into v1.8.0 | **PASS** |
| 4 | v1.7.1 not tagged / piecewise / folded forward | **PASS** (semantic match; not "CLOSED-AS-OBSOLETE" verbatim) |
| 5 | A83 Nash multiplicity EMPIRICALLY CONFIRMED (PR #68) | **FAIL — draft says NOT YET CONFIRMED, neither references PR #68** |
| 6 | PR #43 (clippy/ruff/black-removal) + PR #46 (mypy) | **INFO — draft has both; CHANGELOG v1.8.0 has neither** |
| 7 | Persona count 10 / 4 / 2 / 1 | **FAIL — draft says 9 / 5 / 2 / 1; +1 PASS/-1 PARTIAL gap** |
| 8a | Shim quirk known issue | **PASS** |
| 8b | pyenv arch hazard known issue | **FAIL — not in either file** |

**Pure mutual-consistency verdict (CHANGELOG vs release notes draft, ignoring prompt expectations):**

No direct contradictions found between the two files. The CHANGELOG v1.8.0 section is a brief stub (~43 lines) that defers explicitly to the draft. The draft is the authoritative source. Where the CHANGELOG does speak (.dmg fix, v1.6.1/v1.7.1/v1.7.2 status, shim quirk), it matches the draft exactly — same commit hashes, same doc references, same root-cause framing.

**Where the prompt's expected claims diverge from both files** (PR #68 / Nash multiplicity confirmed, PR #69 / 98fb503 chance-node validation, persona 10/4/2/1, pyenv hazard), this likely reflects either: (a) the prompt's snapshot is more recent than both documents (i.e., both files need updates), or (b) the prompt's expectations are aspirational / based on a stale planning doc. Recommend verifying with the user before changing either file.

## Proposed fixes (NOT auto-applied)

For each disagreement, the recommended side to update:

| Issue | Recommended fix |
|---|---|
| PR #69 / 98fb503 chance-node validation absent | **VERIFY first** that PR #69 exists and was merged with this scope. If yes, add to both the release notes DRAFT (highlight 2 or new highlight) AND the CHANGELOG v1.8.0 entry as a paired ship-blocker fix alongside PR #42. If no, the prompt's expectation is wrong. |
| A83 Nash multiplicity (PR #68) confirmation status | **VERIFY first** whether PR #68 actually empirically confirmed Nash multiplicity (the draft explicitly says the empirical probe is PENDING and the prior Track A probe was INVALIDATED). If PR #68 closed this empirically: update DRAFT lines 310-360 (the "leading hypothesis, empirical probe PENDING" framing); ensure CHANGELOG references this resolution. If not: prompt expectation is wrong; leave both files as-is. |
| Persona count 10/4/2/1 vs draft's 9/5/2/1 | **VERIFY first** with `docs/persona_test_status_2026-05-26.md` (the canonical persona-status source the draft cites). If the canonical source has moved to 10/4/2/1: update DRAFT lines 265-275 to match; CHANGELOG v1.8.0 entry could optionally inherit a summary line. If canonical source is still at 9/5/2/1: prompt expectation is stale. The draft is internally self-consistent: it says 9/5/2/1 currently with W2.3 PENDING, and projects 9 or 10 PASS / 1 or 2 BLOCKED post-retest. |
| Cleanup/lint/mypy (PR #43 + PR #46) absent from CHANGELOG | Update the **CHANGELOG v1.8.0 entry** to include a brief "### Cleanup / lint / mypy / deps green-up (PRs #43, #46)" subsection summarizing PR #43 (clippy/ruff/black-removal/rich added) and PR #46 (mypy 7-bug fix). The draft already documents these; CHANGELOG should mirror. |
| pyenv arch hazard not in v1.8.0 known issues | **VERIFY first** whether this hazard manifested in v1.8.0 testing (universal2 .so was the v1.2.1 fix). If still relevant in v1.8.0 (e.g., per `feedback_dotso_arch_check.md`), add a known-issue bullet to BOTH the release notes DRAFT and the CHANGELOG v1.8.0 known-issues section. If no longer relevant, ignore the prompt expectation. |

**Where the docs already agree (items 1, 2a, 3, 4, 8a):** no changes needed.
