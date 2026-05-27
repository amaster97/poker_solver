# v1.5.0 Release Notes — Honest-Acceptance Edit

**Date:** 2026-05-23
**Task:** Edit the v1.5.0 GitHub release notes to be transparent about the
failing Brown apples-to-apples acceptance test, while preserving the original
algorithmic / performance framing.
**Method:** `gh release edit v1.5.0 --notes-file <revised>` (preserves
attached binaries / .dmg download artifacts; no delete-and-recreate).
**Authorization:** User-explicit edit authorization (per task framing).
**Release URL:** https://github.com/amaster97/poker_solver/releases/tag/v1.5.0

---

## 1. Before → After summary

### Sections preserved (verbatim or near-verbatim)

- **Headline** — "True Nash range-vs-range via Brown's vector-form CFR" and
  the opening paragraph describing the v1.4.x Option-B → v1.5.0 vector-form
  CFR architectural transition. (Accurate per PR 23 algorithmic verification.)
- **`Added` section** — all five bullets retained; the acceptance-test bullet
  is annotated with a "Currently fails on both spots — see Known issues" tag
  rather than rewritten.
- **Performance** — "~72x faster than the Python aggregator" bullet retained;
  this is a measured number unrelated to the acceptance gates.
- **Unchanged** — scalar-diff byte-identicality and public API surface claims
  retained; these were not under dispute.
- **Caveats and v1.5.x roadmap** — preserved as-is.
- **License** — preserved as-is.

### New section inserted (top of notes, immediately after the headline)

A `## ⚠️ Known issues (resolved in v1.5.1)` block that:

1. States the acceptance test does not pass on either spot.
2. Names the `dry_K72_rainbow` 53.3% history-coverage failure as a test-side
   canonicalization mismatch (Rust `A` all-in token vs Brown chip-amount
   token), explicitly affirms the underlying PR 23 algorithm matches Brown's
   `cpp/src/trainer.cpp:138-209`, and notes the fix lands in v1.5.1 (PR 35).
3. Names the `dry_A83_rainbow` Rust off-by-one panic in
   `crates/cfr_core/src/dcfr_vector.rs` reach-propagation loop as a
   bound-mismatch bug fixed on the development branch (PR 34), shipping in
   v1.5.1.
4. Caveats that the Brown apples-to-apples parity claim is **unverified**
   until v1.5.1 ships, but preserves the two intact claims for v1.5.0:
   (a) algorithmic correctness vs Brown's source, (b) <= 0.05 BB
   exploitability vs the Python `dcfr.py` reference on the Case A spot.
5. Clarifies that the previously circulated DCFR "100x slowdown" was a
   measurement artifact, not a real regression.

### Existing acceptance-test bullet annotated

The bullet under `Added` describing the acceptance test now ends with:

> **Currently fails on both spots — see Known issues above. Fix shipping in v1.5.1.**

This avoids stranding a confident "ships clean" claim inside a feature list
while the top-of-notes block flags the real status.

---

## 2. Verification

`gh release view v1.5.0 --json body | jq -r '.body' | head -40` post-edit
returns the revised content, with the `Known issues` block appearing
immediately after the opening paragraph. The headline, Added / Performance /
Unchanged / Caveats / License sections are all preserved. Release URL
unchanged. Download artifacts (`.dmg`, source tarballs) untouched because
the edit used `gh release edit --notes-file`, not delete-and-recreate.

---

## 3. Items worth flagging from the original notes

- **No empirical-acceptance claim was in the original notes.** The original
  release-notes text never said "Brown parity verified" — it described the
  acceptance test as opt-in via the `parity_noambrown` marker and noted it
  "gracefully skips when Brown's binary has not been built locally." That
  hedging was prescient: it meant the original notes did not actively assert
  a falsehood, but it also obscured that the test fails when actually run.
  The new Known-issues block makes the failing-on-run reality explicit.
- **No PII or local paths in the original notes** — the audit pre-edit
  surfaced zero `Users/ashen/...` strings, session IDs, or personal info.
  The revised notes preserve this hygiene (audited pre-publish: clean).
- **Performance claim is single-machine** — the "~72x faster than the Python
  aggregator on a medium 10x10 RvR river spot" claim is honest and includes
  the "honest single-machine comparison on macOS arm64" qualifier. No edit
  needed.

---

## 4. Cleanup

- Removed `/tmp/v1.5.0_notes_current.md` and `/tmp/v1.5.0_notes_revised.md`
  after the edit landed and was verified via `gh release view`.

---

## 5. Source-of-truth pointers

- Acceptance result: `docs/v1_5_0_brown_acceptance_result.md`
- v1.5.1 ship plan: `docs/leg16_v1_5_1_ship_plan.md`
- Algorithmic verification source: `references/code/noambrown_poker_solver/cpp/src/trainer.cpp:138-209`
- Panic site (pre-fix): `crates/cfr_core/src/dcfr_vector.rs` reach-propagation loop
- Release URL: https://github.com/amaster97/poker_solver/releases/tag/v1.5.0
