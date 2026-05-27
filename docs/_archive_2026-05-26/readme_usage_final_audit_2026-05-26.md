# README.md + USAGE.md — Final user-facing audit (2026-05-26)

**Scope:** end-state coherence audit after ~10 PRs touching these files
tonight. Lens: a fresh user landing on the repo with no prior context.

**Method:** read both files end-to-end; cross-reference linked docs, PR
numbers, code symbols (`SolveResult.backend`, `solve_range_vs_range_*`,
`HUNLConfig` invariants), CHANGELOG version history, and CLI argparse
choices. **Read-only.** No file modifications applied.

**Overall verdict:** **Mostly coherent for first-time users**, with one
high-impact internal contradiction (Brown deep-cap status), two
**stale-version** claims in USAGE.md, and one **broken code example**
in README.md (`result.backend == "pushfold"` is wrong by code).
Recommended fixes are all surgical edits, no structural rewrite needed.

---

## Per-section coherence verdict

### README.md

| Section | Verdict | Notes |
|---|---|---|
| Title + opening paragraph | **PASS** | Clear feature surface; goalpost stated honestly. |
| Status block (L12–30) | **PASS** | v1.7.0-tagged / v1.8.0-pending framing is consistent with CHANGELOG `[1.8.0] - Unreleased` header. .dmg fork-bomb status is prominent here. |
| `.dmg` install section (L32–44) | **PASS** | Critical warning at the top; redirects to source install. Doc link `dmg_spawn_loop_rca_2026-05-26.md` exists. |
| Install (from source) (L46–74) | **PASS** | Rust install + `pip install -e .` chain is consistent. Quoted forms `".[dev]"` / `".[ui]"` are zsh-safe. |
| Quick start (L76–127) | **PARTIAL** | One stale claim: `result.backend == "pushfold"` (L126) — actual value is `"pushfold_chart"` per `pushfold.py:232`. USAGE §3a L109 correctly says `"pushfold_chart"`. **README is wrong; USAGE is right.** |
| Python API (L128–188) | **PARTIAL** | Tone is good; node-locking caveat about preflop `NotImplementedError` (L143-144) is consistent with USAGE §7. **But the `solve_range_vs_range_rust` description (L181–184) directly contradicts Known issues §1 below** — see contradictions below. |
| UI (L190–200) | **PARTIAL** | "As of v1.2.0 the UI drives the real solver" (L199) — this contradicts USAGE §4 which still calls the UI **mock mode** (`v1.0.0`). One or the other is stale. |
| Architecture (L202–213) | **PASS** | Test paths verified to exist on disk (`tests/test_dcfr_diff.py` etc.). DEVELOPER.md cross-ref exists. |
| Development (L216–231) | **PASS** | `scripts/check_pr.sh` exists; commands consistent. |
| Known issues (L233–289) | **PARTIAL** | .dmg fork-bomb item: PASS. **A83 deep-cap item (L249–269) declares the issue RESOLVED**, which contradicts the Python API description (L181–184) that still presents the 33-pp divergence as live. Fractional frequencies + CLI subcommand caveats + batch-solve quoting: all consistent and current. **Missing: `pyenv` arch hazard + `poker-solver` shim quirk** (called out in your prompt; verified absent from both files' Known issues sections — see below). |
| References (L291–302) | **PASS** | `references/` is gitignored as stated; `scripts/setup_references.sh` exists. |
| Notation + License (L304–315) | **PASS** | No issues. |

### USAGE.md

| Section | Verdict | Notes |
|---|---|---|
| Header + baseline (L1–14) | **PASS** | Honest framing of "Document baseline: v1.0.0; layered updates through v1.7.0". |
| §1 What this is (L17–35) | **PASS** | Tone is honest; scope-vs-PioSolver claim is hedged correctly. |
| §2 Installing on macOS (L38–73) | **PARTIAL** | (a) `.dmg` warning is consistent with README. (b) USAGE L69 uses **unquoted** `pip install -e .[ui]` which zsh will glob-expand into a no-match error; README uses quoted `".[ui]"` correctly. (c) References "PR 86" (L56) for the `lipo -info` check — PR 86 exists in `scripts/build_macos_dmg.sh` (verified), but it's far ahead of the README's PR 50–56 range, which is fine — just noting consistency was preserved. |
| §3 What you can do today (L76–155) | **PASS** | Pushfold (`pushfold_chart` backend label is correct here), river subgame, equity examples all use commands that match `poker_solver/cli.py` argparse. |
| §4 UI (currently mock mode) (L158–181) | **STALE** | This section claims the UI is **mock mode** (banner across the top, click Solve = fixture data, "expected with v1.1"). **This contradicts README L199** which says "As of v1.2.0 the UI drives the real solver." CHANGELOG shows v1.1.0 (preflop) and v1.2.0 (later) both shipped. Whichever is right, USAGE has the older claim and is stale relative to README. |
| §5.1 Direct full-range solve (L200–283) | **PASS** | Honest perf caveat is well-stated and consistent with §7b. |
| §5.2 Aggregator (v1.3.0+) (L284–399) | **PASS** | Hero-player semantics consistent with `range_aggregator.py` (`result.position` field verified). |
| §5.3 Node-locking (v1.4.0) (L401–434) | **PASS** | API example matches `solve_hunl_postflop` signature. |
| §5.4 Asymmetric contributions (v1.4.1) (L436–474) | **PASS** | Invariants statement matches `hunl.py` validation. |
| §5.5 Range utilities (L476–483) | **PASS** | `Range.diff` semantic consistent with PR history. |
| §5.6 Aggregator vs. true-Nash (v1.7.0+) (L485–584) | **PASS** | Both APIs exist (`solve_range_vs_range` and `solve_range_vs_range_nash`, both exported from `poker_solver/__init__.py`). W1.2 / W2.1 / W3.5 worked examples are honest about caveats. |
| §6 Library mode (L587–617) | **PASS** | `SpotDescription` + `Library.open` API matches `poker_solver/library.py`. |
| §7 Known limitations (L620–645) | **STALE** | "Full preflop is shipping in v1.1.0" (L625) — v1.1.0 already shipped per CHANGELOG L790. Fixed-hole-cards preflop is in (`solve_hunl_preflop` is exported); full-tree preflop is still NotImplementedError. Wording reads like a forward-looking promise but should be retrospective. Same for "Wait for PR 10b (expected v1.1)" on UI mock-mode if README's "real solver as of v1.2.0" claim is the source of truth. |
| §7a Ergonomic subcommands (L648–712) | **PASS** | CLI flags + fixture paths match `poker_solver/cli.py`. Parity caveat about `scripts/build_noambrown.sh` and exit-2 hint is precise. |
| §7b Known perf cliffs (L714–755) | **PASS** | "v1.4.2" stamp on the `initial_hole_cards=()` cliff is dated but not wrong (the cliff is still present in v1.7.x). |
| §8 What's coming (L759–773) | **STALE** | Same v1.1.0 / PR 9 forward-looking framing as §7. PR 9 has already landed (per `solve_hunl_preflop` in `__init__.py` and CHANGELOG L790-885). PR 10b status depends on README §UI being correct. |
| §9 Getting help (L777–782) | **PASS** | No issues. |

---

## Internal contradictions (BLOCKING — surface to user)

### C1. **README Python API vs README Known issues — A83 deep-cap status (HIGH IMPACT)**

- **README L177–184** (Python API, describing `solve_range_vs_range_rust`):
  > "empirical acceptance against Brown's binary still diverges on
  > deep-cap facing-raise spots (33-pp on bottom-pair-Ace cells in the
  > A83 spot at `b1000r3000`); shallow-cap behavior matches — see Known
  > issues."

- **README L249–269** (Known issues — A83 item):
  > "Deep-cap RvR acceptance vs Brown: Nash-multiplicity on indifference
  > manifold (**resolved**); v1.6.1 ship HOLD lifted. **Investigation
  > closed.** The v1.5 Brown acceptance test PASSES under the reframed
  > 4-layer gate ... The residual 33-pp deep-cap divergence is
  > acceptable per the Nash-multiplicity acceptance framework."

**Verdict:** the Python-API paragraph reads to a fresh user as "this
API is broken on deep-cap." The Known-issues paragraph reads as "the
test passes; divergence is accepted as Nash-multiplicity." Both are
talking about the **same 33-pp divergence**, but one frames it as a
live defect and the other frames it as accepted-and-expected.

**Recommended fix (NOT auto-applied):** edit L181–184 to match the
Known-issues framing — e.g., replace "*still diverges*" with "*diverges
within an accepted Nash-multiplicity margin; the v1.5 Brown acceptance
test PASSES under the reframed 4-layer gate. See Known issues.*" This
is the framing the rest of the doc (and `docs/v1_5_brown_current_state_2026-05-26.md`)
endorses.

### C2. **README UI vs USAGE §4 UI — mock vs. real (MEDIUM IMPACT)**

- **README L197–200**: "As of v1.2.0 the UI drives the real solver. The
  packaged `.dmg` GUI does not currently work — see Known issues. **Use
  the CLI / Python API for now.**"
- **USAGE L158, L171–177**: "## 4. The UI (currently mock mode)" + "All
  the visuals, frequencies, and EV numbers are placeholders for UI
  development. A banner across the top makes this explicit. ... a
  future PR swaps in the real solver, expected with v1.1."

**Verdict:** the two docs disagree on whether the UI currently drives a
real solver. README says **yes (since v1.2.0)** but redirects to CLI;
USAGE says **no, still mock mode**.

**Recommended fix:** decide which is true. If real-solver-since-v1.2.0
is correct (which the CHANGELOG v1.2.0 entry supports — it documents
real-solver swap-in), USAGE §4 needs a wholesale update: drop the
"currently mock mode" header, drop the banner-across-top language,
update §7 / §8 forward-looking PR-10b references. If the UI is still
mock-mode in practice, README L199 needs to retract the v1.2.0 claim.

---

## Stale claims

### S1. **README L126 — wrong backend string literal**

`result.backend == "pushfold"` — actual code value is `"pushfold_chart"`
(verified in `poker_solver/pushfold.py:232`). USAGE §3a L109 has the
correct string. A user copy-pasting the README check would get
`False`-positives forever.

**Fix:** change to `result.backend == "pushfold_chart"`. **Trivial,
safe to auto-apply.**

### S2. **USAGE §7 + §8 — forward-looking PR 9 / v1.1.0 framing is stale**

- L625: "full preflop is shipping in v1.1.0" — v1.1.0 shipped 2026-05-23
  per CHANGELOG.
- L762–763: "PR 9 — full HUNL preflop solve. Replaces the
  `NotImplementedError` above 15 BB. Shipping in v1.1.0." — `solve_hunl_preflop`
  is exported from `poker_solver/__init__.py` (line 80). Fixed-hole-card
  preflop ships; full-tree preflop is still NotImplementedError.
- L766: "PR 10b — real solver bindings in the UI. ... ~1 week, lands
  after PR 9."

**Fix:** retroactivize all three. Per the CHANGELOG v1.1.0 entry,
preflop subgame solve **with fixed hole cards** is in; full-tree
preflop deferred. PR 10b status depends on resolving C2 above.

### S3. **USAGE L69 — zsh-incompatible install command**

`pip install -e .[ui]` (no quotes) — zsh will try to glob-expand the
brackets and fail with `no matches found`. README uses the quoted form
correctly (`pip install -e ".[ui]"`).

**Fix:** add quotes. Trivial.

### S4. **USAGE L241–242 — rake field caveat dated v1.0.0**

L241: "`rake_rate` / `rake_cap` — must remain `0.0` / `0` in v1.0.0;
non-zero values raise `ValueError` (rake lands in PR 9)."

`poker_solver/hunl.py:140` still raises the same ValueError citing "PR
9 (rake lands in PR 9)". So the **field invariant is still accurate**,
but the v1.0.0 stamp + PR 9 reference is stale (rake **did not** land
in PR 9; PR 9 was preflop). This is a documentation lag, not a code
bug.

**Fix:** drop the v1.0.0 / PR 9 framing and just state the current
invariant — "must be `0.0` / `0`; rake support not yet implemented."

---

## Missing items (per prompt expectation)

### M1. **`pyenv` arch hazard — NOT in either file's Known issues**

The prompt expects this hazard documented. `feedback_dotso_arch_check.md`
identifies it as a recurring tooling quirk (`pyenv` shim resolves to an
x86_64 interpreter, which silently `SKIP`s tests that can't load the
arm64 `.so`). It's covered in
`docs/changelog_release_notes_consistency_2026-05-26.md` §8 as a
"PARTIAL PASS — pyenv arch hazard: FAIL (NOT in either file's v1.8.0
known issues)". This audit confirms: neither README.md nor USAGE.md
mentions `pyenv` or the silent-skip hazard.

**Fix:** add to README Known issues — small bullet pointing out that
on macOS with pyenv, you may need `python -m pytest ...` rather than
the bare `pytest` shim, and `python -c "import poker_solver._rust"`
should succeed before running diff tests.

### M2. **`poker-solver` shim quirk — NOT in either file's Known issues**

The CHANGELOG v1.8.0 section (L43-58) documents the shim quirk in
detail. Neither README nor USAGE surfaces this for a fresh user
installing from source. The user prompt explicitly calls this out.

**Fix:** add a Known-issues bullet to README pointing at the same
workarounds the CHANGELOG documents (`./.venv/bin/poker-solver ...`
or `python -m poker_solver.cli ...`), with a link to
`docs/poker_solver_shim_fix_2026-05-26.md`.

---

## Cross-reference verification

All linked docs exist on disk:

- `docs/v1_7_1_tag_decision_2026-05-26.md` — exists.
- `docs/dmg_spawn_loop_rca_2026-05-26.md` — exists.
- `docs/dmg_install_guide.md` — exists.
- `docs/v1_5_brown_current_state_2026-05-26.md` — exists.
- `docs/a83_validation_2026-05-26.md` — exists.
- `docs/v1_6_1_ship_hold_review_2026-05-26.md` — exists.
- `docs/a83_deep_cap_root_cause_investigation.md` — exists.
- `docs/aggregator_vs_true_nash_explainer.md` — exists.
- `CHANGELOG.md`, `DEVELOPER.md`, `CONTRIBUTING.md`, `LICENSE` — exist.
- All `tests/test_*_diff.py` cited in README L208-209 — exist.
- `scripts/check_pr.sh`, `scripts/setup_references.sh`,
  `scripts/build_noambrown.sh`, `scripts/build_macos_dmg.sh`,
  `scripts/pyinstaller_entry.py` — all exist.
- `scripts/pyinstaller_entry.py` confirmed to call `mp.freeze_support()`
  (line 27 — matches the README L36–37 and CHANGELOG L27–42 claim).

**No broken cross-references found.**

---

## CLI examples — would-they-work check

Verified against `poker_solver/cli.py` argparse (`sv.add_argument
--hunl-mode choices=("tiny_subgame", "postflop", "full")` at L1110):

- README L78–98 Quick start equity + solve commands: **all flags exist**
  and match argparse choices. PASS.
- README L108–114 postflop example: flags `--game hunl --hunl-mode
  postflop --board --stacks --bet-sizes --iterations --backend` all
  exist. PASS.
- README L119–123 Python pushfold example: `get_pushfold_strategy` and
  `get_full_range` both exported from `poker_solver/__init__.py`. PASS.
- USAGE §3 CLI examples: same surface, PASS.
- USAGE §7a `pushfold` / `river` / `parity` subcommand flags: all
  documented flags match `cli.py` argparse for the three subcommands.
  PASS.

**No broken CLI examples.** The one literal-string issue (S1 above) is
not a CLI invocation, it's a Python `result.backend` comparison.

---

## Summary of recommended fixes (in priority order)

| # | Severity | Item | Action | Trivial to auto-apply? |
|---|---|---|---|---|
| C1 | HIGH | README A83 deep-cap divergence framing contradicts Known issues | Re-word L181–184 to match the "resolved within Nash-multiplicity margin" framing | NO — needs user sign-off on wording |
| C2 | MEDIUM | README "UI drives real solver" vs USAGE "UI is mock mode" | Decide which is current truth, update the loser | NO — needs user to confirm which is right |
| S1 | LOW | README L126 `result.backend == "pushfold"` should be `"pushfold_chart"` | One-character fix (add `_chart`) | YES |
| S2 | LOW | USAGE §7 + §8 stale "v1.1.0 / PR 9 shipping" framing | Retroactivize past-tense | NO — fixing depends on UI status decision |
| S3 | LOW | USAGE L69 unquoted `pip install -e .[ui]` (zsh-hostile) | Add quotes | YES |
| S4 | LOW | USAGE L241–242 v1.0.0 / PR 9 rake stamp is stale | Drop the version stamp, state current invariant | YES (low risk) |
| M1 | MEDIUM | `pyenv` arch hazard missing from README Known issues | Add bullet | NO — needs user to draft canonical wording |
| M2 | MEDIUM | `poker-solver` shim quirk missing from README Known issues | Add bullet | NO — needs user to draft canonical wording |

**Net assessment:** the docs are in materially-better shape than the
prompt's "after ~10 PRs touching these files tonight" framing might
suggest. The two HIGH/MEDIUM contradictions (C1 + C2) are the
load-bearing ones to resolve before sign-on. The three trivial fixes
(S1, S3, S4) could be batched into one small follow-up PR. The two
missing items (M1, M2) are gaps the user already flagged in
`docs/changelog_release_notes_consistency_2026-05-26.md` §8, so the
expectation is set.

**No findings warrant a doc-quality block on v1.8.0 ship**; all are
addressable in a single short polish pass.
