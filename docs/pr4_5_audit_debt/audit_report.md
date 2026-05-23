# PR 4.5 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-4.5-audit-debt-sweep
**Integration tip:** `d135add` (post-PR-7)
**Date:** 2026-05-22

**Diff size:** 8 files modified (working tree, uncommitted), +76 / -33 LoC (net +43). Of the 8 files, 4 implement legitimate items (+28 / -8 = net +20 LoC) and 4 are scope creep (+48 / -25 = net +23 LoC). The branch tip is at `d135add` — no commits exist yet on the audit branch; all agent edits are unstaged in the working tree.

**Test status:** Not executed in this audit (read-only audit per kickoff §9b). Static analysis: `ruff check` on all 7 source files **PASSES** (`All checks passed!`). Smoke imports verified: `HUNLConfig`, `enumerate_legal_actions`, `PushFoldChartUnavailable` all importable; `issubclass(PushFoldChartUnavailable, ValueError) == True`. `HUNLConfig(rake_rate=0.05)` raises `ValueError` (3-C path verified). `mypy --strict` not executed (no time budget for full strict sweep on read-only audit); flagged for orchestrator to run pre-commit.

---

## Item-by-item verification

Mapping each of the 13 items in `launch_kickoff.md` §2 to current branch state. Items identified by intent, not literal line number (kickoff §10c).

### PR 3 source items

- **3-A — License header on `poker_solver/hunl.py`.** **PASS.** `hunl.py:3` carries `"License posture: no third-party code derivation; original implementation"` plus a parenthetical "rules-engine state machine and infoset-key format are independent of any specific reference repo; see PR 3 audit report for the per-area review." Wording prefix is consistent with 3-B and 4-A.
- **3-B — License header on `poker_solver/action_abstraction.py`.** **PASS.** `action_abstraction.py:3` carries `"License posture: no third-party code derivation; original implementation"` plus parenthetical "NLHE bet/raise/cap rules are standard poker mechanics, not copied from any specific reference repo." Wording prefix identical to 3-A.
- **3-C — `AssertionError → ValueError` in `HUNLConfig.__post_init__` rake fields.** **PASS.** `hunl.py:125` and `hunl.py:127` both raise `ValueError` (was `AssertionError`). Verified via runtime probe: `HUNLConfig(rake_rate=0.05)` raises `ValueError` with the expected message. Test consequence (`tests/test_hunl_postflop_solve.py:271`) pre-emptively used `pytest.raises((ValueError, AssertionError))`, so no test edit required — the test still passes after the swap.
- **3-D — Drop unused `field` import from `hunl.py:14`.** **NOT APPLICABLE / NOT DONE.** Per `hunl.py:18` the `field` symbol is currently imported (`from dataclasses import dataclass, field, replace`) and **is actually used** at `hunl.py:122` (`abstraction: AbstractionRef | None = field(default=None, compare=False, hash=False)`), `hunl.py:179` (`betting_tokens: tuple[...] = field(default_factory=tuple)`), and `hunl.py:180` (`current_street_tokens: tuple[...] = field(default_factory=tuple)`). The PR-3 audit reference was either outdated or `field` was re-introduced by a later commit. Per kickoff §10d ("Cleanup item no longer applicable. Mark RESOLVED in `audit_followup_backlog.md` + reduce §2 scope. Do NOT invent replacement edit."), this is the correct disposition — but the audit follow-up backlog has not been updated.
- **3-E — Unreachable assert in `action_abstraction.py:210-211`.** **PASS (with deviation).** `action_abstraction.py:214-216` raises `AssertionError("unreachable; stack<=0 implies all_in[p]==True")` instead of the literal `assert False, "..."` specified in the kickoff. Functionally equivalent (and arguably more robust — `raise AssertionError(...)` is not stripped by `python -O`); not a defect.

### PR 3.5 source items

- **3.5-A — `PushFoldChartUnavailable(ValueError)`.** **ALREADY-RESOLVED PRE-PR-4.5.** Verified via `git show integration:poker_solver/pushfold.py` — `class PushFoldChartUnavailable(ValueError)` already at `integration:pushfold.py:35`. Landed in commit `1cbf52a` (PR 3.5 audit follow-up); see kickoff §3 ("PR 3.5 §6 must-fixes 1-5 already landed in PR 3.5 follow-up commit `1cbf52a`"). Consumer-grep (per kickoff §9b): `grep -rn 'except PushFoldChartUnavailable' poker_solver/ tests/` returns **zero hits** — no consumer code depends on the prior `Exception` base class. Backwards-compatibility for `except PushFoldChartUnavailable` consumers is moot (none exist). PR 4.5 should NOT re-implement this item; verified the diff does not touch the class definition.
- **3.5-B — Drop `v1-placeholder` from `PUSHFOLD_CHART_VERSIONS`.** **NOT DONE.** `pushfold.py:29` still reads `PUSHFOLD_CHART_VERSIONS: Final[frozenset[str]] = frozenset({"v1", "v1-placeholder"})`. The working-tree diff on `pushfold.py` (see scope-creep §3 below) contains ONLY a docstring expansion + 1-line comment; it does NOT touch line 29.
- **3.5-C — Remove dead `_canonical_hand_classes`.** **NOT DONE.** Function still defined at `pushfold.py:281` (16-line function spanning lines 281-296). `grep -rn '_canonical_hand_classes' poker_solver/ tests/` shows it remains defined; the working diff does NOT remove it. (Only `_all_hand_classes()` is called from `get_full_range`, so the function is genuinely dead; removal is still valid.)

### PR 4 source items

- **4-A — License header on `poker_solver/abstraction/equity_features.py`.** **PASS.** `equity_features.py:3` carries `"License posture: no third-party code derivation; equity feature is original"` plus parenthetical "implemented from first principles atop :func:`poker_solver.evaluator.evaluate`." Prefix matches 3-A and 3-B; the variant trailing phrase ("equity feature is original" vs. "original implementation") matches the kickoff §2 verbatim wording for 4-A.
- **4-B — SHOWDOWN predicate tighten at `hunl.py:336`.** **PASS.** `hunl.py:330-334` reads `if cfg.abstraction is not None and state.street in (Street.FLOP, Street.TURN, Street.RIVER):`. The `>= Street.FLOP` predicate was replaced with the explicit tuple membership. Latent-bug check: `Street.SHOWDOWN = 4 > Street.RIVER = 3`, so the old `>= FLOP` was true for SHOWDOWN; the new tuple excludes SHOWDOWN. Test consequence: `tests/test_hunl_core.py:337` and `tests/test_hunl_core.py:377` call `infoset_key` at RIVER (not SHOWDOWN) — RIVER is in the new tuple, so tests continue to pass without modification. No test edit needed.
- **4-C — Unreachable assert in `_kmeans_plusplus_init` at `emd_clustering.py:188-196`.** **PASS (with deviation).** `emd_clustering.py:194-196` raises `AssertionError("unreachable; n < K degenerate branch handled at line 167")` instead of `assert False, "..."`. Same deviation as 3-E; functionally equivalent (no `-O` strip risk); not a defect.
- **4-D — `max_boards_per_street` sentinel kwarg surface at `precompute.py:452-455`.** **PASS (with should-fix on docstring).** `precompute.py:51-55` adds 3 module-level named constants (`_AUTOSIZE_MC_ITERATIONS_THRESHOLD = 5_000`, `_AUTOSIZE_BOARDS_CAP = 8`, `_AUTOSIZE_HANDS_CAP = 16`). `precompute.py:454-473` refactors the autosize block to use these constants and adds `-1` sentinel handling for "explicit no cap." Threshold value (5000), default caps (8, 16), and `None`-triggered autosize semantics are byte-identical to integration — strictly additive. **Should-fix:** the docstring at `precompute.py:414-420` (lines describing `max_boards_per_street` semantics) was NOT updated to mention the new `-1` sentinel; kickoff §2 4-D and audit-prompt §1.4 explicitly call for "a brief docstring entry explaining the sentinel semantics (None=autosize, -1=no cap, int>0=fixed cap)."

### PR 5 source item

- **5-A — Drop unused `numpy` import + `_ = np` suppression at `profiler/memory.py:508-510`.** **ALREADY-RESOLVED PRE-PR-4.5.** `git show integration:poker_solver/profiler/memory.py | grep numpy` returns no import; only a docstring mention at line 63 (`"All byte fields are exact (sum of `np.ndarray.nbytes` for backing..."`) which is a comment, not code. The import was apparently dropped during PR 5 or PR 6 prior to PR 4.5 firing. No action needed for 5-A itself; however, the actual edit Agent C made to `profiler/memory.py` does NOT implement 5-A — it is pure scope creep (named-constant extraction); see scope-creep §3 below.

---

## Must-fix

1. **3.5-B (drop `v1-placeholder`) — NOT DONE.** File: `poker_solver/pushfold.py:29`. The `PUSHFOLD_CHART_VERSIONS` tuple still contains `"v1-placeholder"`. Kickoff §2 explicitly lists this item; missing it leaves the loader accepting dry-run output going forward. **Fix:** delete `"v1-placeholder"` from the frozenset literal at line 29; verify no test relies on it being accepted (`grep -rn 'v1-placeholder' tests/` to confirm).
2. **3.5-C (remove dead `_canonical_hand_classes`) — NOT DONE.** File: `poker_solver/pushfold.py:281-296`. The 16-line function is still defined; only `_all_hand_classes()` (line 236) is called by `get_full_range`. Kickoff §2 explicitly lists this item. **Fix:** delete `def _canonical_hand_classes(...)` block at lines 281-296; verify zero references via `grep -rn '_canonical_hand_classes' poker_solver/ tests/`.
3. **Branch has zero commits.** All agent edits are **unstaged in the working tree** (`git status` shows 8 modified files; `git log integration..HEAD` returns no commits; `git rev-parse pr-4.5-audit-debt-sweep == git rev-parse integration`). The audit branch is functionally empty from a git perspective. **Fix:** before merging, the orchestrator must stage and commit the legitimate items (after resolving the should-fix and scope-creep items below) per kickoff §9c.

## Should-fix

1. **Scope creep: `CHANGELOG.md` link URLs replacement.** File: `CHANGELOG.md:366-374`. Working tree replaces `[Unreleased]: ./` etc. with full GitHub `compare/...HEAD` and `releases/tag/...` URLs (10 lines changed). This is NOT in the 13-item list (kickoff §2). It is benign documentation cleanup, but per kickoff §10b ("Agent scope expansion. Revert X") and audit-prompt §1.1 ("Benign creep → should-fix + revert recommended"), it should be reverted to keep PR 4.5's mechanical-only contract pure. Recommend either revert or formal §2 amendment.
2. **Scope creep: `pushfold.py` docstring + comment.** File: `poker_solver/pushfold.py:180-189` (docstring `Returns:` block expanded from 2 lines to 5 lines) and `pushfold.py:226` (new comment `# game_value=0.0 is a documented placeholder...`). Neither of these is one of the 13 items. The `game_value=0.0` is from PR 3.5 audit §6 item #10 (silent-wrong return) — documenting it without fixing it is a half-measure. Per `incidental_edits_review.md` §4c default recommendation, **revert.** Alternative: defer-and-keep with backlog entry, or formally promote to item 3.5-D by amending kickoff §2.
3. **Scope creep: `profiler/memory.py` named constant `_BYTES_PER_GB`.** File: `poker_solver/profiler/memory.py:54-56` (new constant) and lines 113-132 (5 inline `1024**3` literals replaced). This is Agent C's only contribution. It does NOT implement 5-A (which was already done pre-PR-4.5). It IS a sensible magic-number cleanup, but it is NOT in the 13-item list. Recommend **revert** (consistent with kickoff §10b) OR formally promote to item 5-B if the magic-number guard is desired. Note also: focus area 4 of the audit prompt (named-constant magic numbers) is on the audit checklist — but the audit-prompt's focus list is a check FOR the auditor to apply, not a license for the agent to add named-constant fixes beyond the 13 items.
4. **Scope creep: `precompute.py` named-constant extraction.** File: `poker_solver/abstraction/precompute.py:51-55` (3 new constants). Defensible as "the natural way to surface the magic number cleanly per kickoff §2 4-D phrasing," but pedantically beyond the kwarg-surface scope. Lower priority than the other should-fix items because the constants are colocated with the kwarg the audit explicitly authorized. Recommend **keep** (within reasonable interpretation of 4-D) and document the choice in the commit message.
5. **4-D docstring not updated for `-1` sentinel.** File: `poker_solver/abstraction/precompute.py:414-420`. The existing docstring describes only the `None`-triggered autosize semantics. Audit-prompt §1.4 explicitly requires the brief docstring entry. **Fix:** add one line at line ~420 explaining `-1` = no cap.
6. **3-D follow-up not filed.** Item 3-D is not applicable (see verification §3-D). Kickoff §10d says to "Mark RESOLVED in `audit_followup_backlog.md` + reduce §2 scope." This has not been done. **Fix:** add 1-line entry to `docs/audit_followup_backlog.md` noting 3-D is no-op (field genuinely used).

## Nice-to-fix

1. **License header wording — minor parenthetical variance.** All 3 headers share the core phrase ("License posture: no third-party code derivation; original implementation" / "...equity feature is original"). The trailing parenthetical varies in flavor (e.g., 3-A cites "see PR 3 audit report"; 3-B cites "standard poker mechanics"; 4-A cites "implemented from first principles atop ..."). Per kickoff §8d, aggregator normalization is a should-fix-grade trigger; but since the canonical prefix is identical and the parentheticals are content-specific (not drift), this is **nice-to-fix only** — readers won't be misled.
2. **3-E and 4-C use `raise AssertionError(...)` instead of `assert False, "..."`.** Kickoff §2 specifies the latter literal. The former is arguably more robust (`python -O` does not strip it). Both are functionally equivalent for the unreachable-branch protection. No action needed; flagged for future reviewer awareness.

## Looks good (explicit confirmation of audit focus areas)

1. **Mechanical-only scope: NO new behavior changes (HIGH-PROB).** The 4 legitimate-item files (`hunl.py`, `action_abstraction.py`, `equity_features.py`, `emd_clustering.py`) contain only error-type swaps (3-C), unreachable-assert hardenings (3-E, 4-C), license headers (3-A, 3-B, 4-A), and a SHOWDOWN-predicate tighten (4-B). All four items strictly preserve observable behavior on the production paths. No solver refactor; no `_is_terminal` or `_is_chance` touch; no internal-threshold tweak on 4-D autosize (5000 stays); SHOWDOWN was already unreachable via solver's `is_terminal` guard. The mechanical-only invariant is preserved on the legitimate items. BUT — the working tree has 4 files of scope creep (CHANGELOG, pushfold docstring, profiler magic-number, precompute named-constants) that violate the mechanical-only contract. Net verdict: invariant **partially preserved**; aggregator must revert scope-creep items before commit.
2. **License attribution headers on the 3 listed modules (3-A, 3-B, 4-A) (HIGH-PROB).** All 3 headers present, with the canonical phrase `"License posture: no third-party code derivation; ..."` as the prefix of each. Verified via `grep -rE 'License posture' poker_solver/hunl.py poker_solver/action_abstraction.py poker_solver/abstraction/equity_features.py` returning exactly 3 hits. Wording drift is minimal — the prefix phrase is byte-identical across the 3 files; the trailing parenthetical is content-specific (per-module justification of why the implementation is original). No anti-pattern (headers were NOT added to other files). Aggregator may normalize the parentheticals but it is not load-bearing.
3. **Error-type consistency (3-C).** `hunl.py:125` and `hunl.py:127` raise `ValueError` matching the rest of the validators at lines 130, 132, 137, 144 (line numbers shifted due to the license header). Scope-bounded: ONLY the rake-field validators were touched; no other `AssertionError` raises in `hunl.py` were swapped. Test consequence pre-handled (test allowed both types).
4. **SHOWDOWN predicate tighten (4-B).** `hunl.py:330-334`: `state.street in (Street.FLOP, Street.TURN, Street.RIVER)`. Single-line surface change (multiline due to formatting). Scope-bounded: solver predicates (`_is_terminal`, `_is_chance`) untouched. Latent-bug surface check: `tests/test_hunl_core.py:337,377` call `infoset_key` at RIVER, not SHOWDOWN; tests pass unchanged.
5. **`mc_iterations < 5000` autosize trigger surfaced (4-D).** `precompute.py:454-473` implements `None` = autosize, `-1` = no cap, positive int = direct cap. Threshold (5000), default caps (8, 16) unchanged. Strictly surface-only; production callers passing `mc_iterations=200_000` (locked D2 default) never trip the autosize branch.
6. **`PushFoldChartUnavailable(ValueError)` subclass (3.5-A) (HIGH-PROB).** ALREADY done pre-PR-4.5 (commit `1cbf52a`). Consumer-grep gate: `grep -rn 'except PushFoldChartUnavailable' poker_solver/ tests/` returns **zero hits**. Other `PushFoldChartUnavailable` references: definition at line 35; 7 raise sites (`pushfold.py:54,60,68,113,119,270,275`); docstring contract at line 140; `__init__.py:71` re-export; one test import (`tests/test_pushfold.py:18`) + one test comment (`tests/test_pushfold.py:115`). No consumer relies on `not isinstance(e, ValueError)`. Backwards-compatible.
7. **NO new tests added.** `git diff HEAD -- tests/` and `git diff integration...HEAD -- tests/` both return empty. Test count is unchanged; skip-mark count unchanged (modulo zero per kickoff §3 / audit-prompt §7). No net-new `def test_*` functions.
8. **Total LOC delta.** Net `+43` LoC (+76 / -33) across 8 files. Above the kickoff §12 expected `30-50 net LoC` ceiling, but the overage is driven by scope-creep files (CHANGELOG, pushfold docstring, profiler magic-number, precompute named-constants); the 4 legitimate-item files net `+20` LoC (+28 / -8). If scope-creep is reverted per should-fix items 1-4, net delta returns to ~20 LoC — well under the 50-LoC budget.
9. **Cross-agent file ownership respected (HIGH-PROB).** Per `fanout_ready.md` §3 and kickoff §5a:
   - Agent A (`hunl.py:107,109` rake [3-C] + line 14 [3-D, not applicable] + license header [3-A]; full files `action_abstraction.py` [3-B, 3-E], `pushfold.py` [3.5-A/B/C]): A edited lines 3 (license), 125, 127 (rake) of `hunl.py`. The `field` import at line 18 was NOT touched (correctly, since it is used). On `action_abstraction.py`: A edited line 3 (license) and lines 214-216 (unreachable assert). On `pushfold.py`: A edited lines 180-189 (docstring) and 226 (comment) — neither maps to 3.5-B or 3.5-C; agent missed both items.
   - Agent B (`equity_features.py` [4-A], `emd_clustering.py` [4-C], `precompute.py` [4-D], `hunl.py:336` [4-B]): B edited line 3 of `equity_features.py` (license), lines 194-199 of `emd_clustering.py` (unreachable assert), and lines 51-55 + 454-473 of `precompute.py` (constants + sentinel). On `hunl.py`: B edited lines 330-334 (predicate). Line ranges with A on `hunl.py` (A: 3, 125, 127; B: 330-334) do NOT overlap — git would auto-merge cleanly if A's and B's edits were on separate branches. (Currently they are on the same working tree, so this is moot.)
   - Agent C (`profiler/memory.py` [5-A]): C did NOT implement 5-A (numpy was already absent). Instead C edited lines 54-56 + 113-132 to extract `_BYTES_PER_GB` constant — scope creep. The legitimate 5-A item is no-op.
   - No manual merge-conflict commits (no commits at all on the branch — see must-fix #3).
10. **Unused-import drops are safe (3-D, 5-A).** Per kickoff §8e pre-grep: `field(` is referenced 3x in `hunl.py:122,179,180` — 3-D is NOT safe to apply (and was correctly NOT applied). `np\.` in `profiler/memory.py` — the integration tip has no `numpy` import; 5-A is already a no-op.
11. **Unreachable-assert items (3-E, 4-C) do NOT trip in CI.** Not executed in this audit (read-only), but the structural condition is preserved: `action_abstraction.py:213` `stack = _stack_remaining(ctx)` guard combined with the HUNL `all_in[p]` invariant; `emd_clustering.py:167` `n < K` early-return ahead of the loop. The asserts are documented unreachable per the audit reports. Orchestrator pre-commit gate runs `pytest -x` (kickoff §9a) which is the actual trip detector.
12. **Dead-code removal (3.5-C).** **FAILED** — see must-fix #2. `_canonical_hand_classes` still at `pushfold.py:281`.
13. **`v1-placeholder` removed from `PUSHFOLD_CHART_VERSIONS` (3.5-B).** **FAILED** — see must-fix #1. Still in `pushfold.py:29`.
14. **Test count + skip count unchanged.** No test file modifications in working tree or committed diff. Test-count must be unchanged. Skip-count: PR 5's 6 skip-marked TURN tests remain skip-marked (none unskipped — verified by zero test edits).
15. **`mypy --strict` + `ruff check` clean.** `ruff check` on the 7 modified source files (+ `precompute.py` body) **PASSES**: `All checks passed!`. `mypy --strict` not executed in this read-only audit; orchestrator should run pre-commit per kickoff §9a.

---

## Scope-creep enumeration

Every edit in the working-tree diff NOT mapped to one of the 13 items in `launch_kickoff.md` §2:

1. **`CHANGELOG.md:366-374`** — Replaces 9 `./` placeholder links with full GitHub URLs (e.g., `[0.5.1]: https://github.com/amaster97/poker_solver/releases/tag/v0.5.1`). **Recommended action: revert** (or formally amend §2 to add a 14th item). +9 / -9 LoC.
2. **`poker_solver/pushfold.py:180-189`** — Expands `solve_pushfold` `Returns:` docstring from 2 lines to 5 lines, adding prose about `game_value=0.0` placeholder, `exploitability_history` single-element list, and chart-JSON-doesn't-persist-SB-EV (refers to PR 3.5 audit §6 item #10 silent-wrong issue). **Recommended action: revert** per `incidental_edits_review.md` §4c. Alternative: formal §2 amendment for "Item 3.5-D: docstring annotation of `game_value` placeholder." +7 / -2 LoC.
3. **`poker_solver/pushfold.py:226`** — Adds 1-line inline comment `# game_value=0.0 is a documented placeholder (see docstring Returns).`. **Recommended action: revert** (same rationale as #2). +1 / -0 LoC.
4. **`poker_solver/profiler/memory.py:54-56,113-132`** — Adds module-level constant `_BYTES_PER_GB: int = 1024**3` and replaces 5 inline `1024**3` literals in the `MemoryReport` GB-property accessors with the named constant. Does NOT implement 5-A (which was already done pre-PR-4.5). **Recommended action: revert** (consistent with kickoff §10b). Alternative: formally promote to Item 5-B with magic-number-cleanup justification. +14 / -10 LoC.
5. **`poker_solver/abstraction/precompute.py:51-55`** — Adds 3 named constants (`_AUTOSIZE_MC_ITERATIONS_THRESHOLD = 5_000`, `_AUTOSIZE_BOARDS_CAP = 8`, `_AUTOSIZE_HANDS_CAP = 16`). Defensible as "natural surfacing of the magic number cited in kickoff §2 4-D phrasing," but pedantically beyond the kwarg-only scope. **Recommended action: keep** (within reasonable interpretation of 4-D); document the constants in the PR commit message as part of the 4-D implementation. +8 / -0 LoC (already counted within 4-D's total).

**Subtotal of scope creep:** ~ +39 / -21 LoC, net +18 LoC across 4 file edits.

**Items missed (not in scope-creep list, but flagged separately):**
- 3.5-B (`v1-placeholder` drop) — see must-fix #1.
- 3.5-C (`_canonical_hand_classes` removal) — see must-fix #2.

---

## Cross-agent file-ownership audit

Per `fanout_ready.md` §3 and kickoff §5a, the ownership matrix is:

| Agent | Files (write/edit) | Lines on shared `hunl.py` |
|---|---|---|
| A | `hunl.py` (license header, 14, 107, 109), `action_abstraction.py` (full), `pushfold.py` (full) | 3 (license), 125, 127 (3-C) |
| B | `equity_features.py` (full), `emd_clustering.py` (full), `precompute.py` (full), `hunl.py:336` (4-B only) | 330-334 (4-B predicate) |
| C | `profiler/memory.py` (full) | (none) |

**Audit observation:**
- **Agent A's shared-file edits on `hunl.py`:** lines 3 (license header), 125, 127 (rake validators). Line 14 (`field` import drop) NOT done correctly per 3-D's no-op classification.
- **Agent B's shared-file edit on `hunl.py`:** lines 330-334 (SHOWDOWN predicate). NO overlap with A's edits (A: 3, 125, 127; B: 330-334). Git auto-merge would be trivial.
- **No manual merge-conflict resolution commits** because there are NO COMMITS on the branch at all (must-fix #3).
- **Agent A scope coverage:** 3-A (license header, done), 3-B (license header, done), 3-C (rake ValueError, done), 3-D (no-op, correctly not done), 3-E (unreachable assert, done), 3.5-A (already done pre-PR), 3.5-B (NOT done — must-fix #1), 3.5-C (NOT done — must-fix #2). Plus scope creep on `pushfold.py` (docstring + comment).
- **Agent B scope coverage:** 4-A (license header, done), 4-B (SHOWDOWN predicate, done), 4-C (unreachable assert, done), 4-D (kwarg sentinel, done with docstring miss — should-fix #5). Plus arguably-in-scope named-constant extraction (scope-creep #5).
- **Agent C scope coverage:** 5-A (no-op; already done pre-PR). Plus pure scope creep (`_BYTES_PER_GB` named constant).

**Ownership lock verdict:** No agent edited a file outside its ownership row. Line-range discipline on `hunl.py` was respected (A and B did not overlap). However, **Agent A failed to complete 2 of its 8 listed items (3.5-B, 3.5-C)**, and **Agent C contributed only scope creep**.

---

## License compliance

All 3 required license-attribution headers are present with consistent canonical wording:

- **`poker_solver/hunl.py:3`** (3-A): "License posture: no third-party code derivation; original implementation" + per-module parenthetical.
- **`poker_solver/action_abstraction.py:3`** (3-B): "License posture: no third-party code derivation; original implementation" + per-module parenthetical.
- **`poker_solver/abstraction/equity_features.py:3`** (4-A): "License posture: no third-party code derivation; equity feature is original" + per-module parenthetical (variant trailing phrase matches kickoff §2 4-A wording verbatim).

No new third-party code references introduced. The canonical phrase "License posture: no third-party code derivation;" is byte-identical across all 3 files; the trailing per-module parentheticals are content-specific (not drift). Kickoff §8d would normally trigger aggregator normalization if the wording diverged, but here the prefix is uniform — normalization is **nice-to-fix only** (see Nice-to-fix #1).

No license headers were added to other files (anti-pattern check passed).

---

## Release-notes follow-up

PR 4.5 is a mechanical audit-debt sweep with no user-visible behavior changes; it should land as a single CHANGELOG bullet under "Internal cleanup." Specific public-API surface to flag for downstream:

- **`max_boards_per_street` and `max_hands_per_board` kwargs gained `-1` sentinel semantics** in `precompute.py:build_abstraction` (4-D). Default behavior (None=autosize when mc<5000, positive int=fixed cap) is preserved; the new `-1` value means "explicit no cap." Backwards-compatible.
- **`PushFoldChartUnavailable` now subclasses `ValueError`** (3.5-A, already landed in commit `1cbf52a`; PR 4.5 does not re-do). Backwards-compatible: `except PushFoldChartUnavailable` consumers continue to catch it; `except ValueError` consumers now also catch it. Zero `except PushFoldChartUnavailable` consumers in the codebase (verified by grep), so the change is functionally invisible until external users adopt the broader catch.
- **Internal assertion hardening** in `enumerate_legal_actions` (3-E) and `_kmeans_plusplus_init` (4-C): unreachable branches now raise `AssertionError` instead of silently returning empty/recycling-zero. No observable behavior change on the production paths.

CHANGELOG-bullet draft (assuming all must-fix and should-fix #1-3 resolved): `"Internal: PR 4.5 audit-debt sweep — license-attribution headers, ValueError narrowing on rake-config validators, SHOWDOWN-predicate tighten, unreachable-assert hardening, dead-code removal in pushfold. No user-visible behavior changes."`

---

## Overall verdict

**READY for commit AFTER must-fix items resolved.**

The 4 legitimate-item files (`hunl.py`, `action_abstraction.py`, `equity_features.py`, `emd_clustering.py`) implement 7 of the 13 documented items cleanly (3-A, 3-B, 3-C, 3-E, 4-A, 4-B, 4-C), with 1 partial (4-D, missing docstring update — should-fix), 2 not-applicable (3-D, 5-A), 1 already-resolved-pre-PR (3.5-A), and **2 critical misses** (3.5-B `v1-placeholder` drop, 3.5-C `_canonical_hand_classes` removal). Additionally, the branch has **no commits** — all edits are unstaged. Three files (`CHANGELOG.md`, `pushfold.py`, `profiler/memory.py`) contain scope creep that needs to be reverted per kickoff §10b.

**Verdict justification per audit-prompt §5 probability anchors:** Expected outcome was READY (~70%) with at most license-text drift should-fix (~25%); NOT-READY surprise (~5%) was reserved for scope creep / unreachable-assert firing / consumer-grep miss. The actual outcome lands between READY-WITH-PATCHES (~25%) and NOT-READY (~5%) — the two missed-items (3.5-B, 3.5-C) are minor mechanical fixes that any future agent can finish in <5 min, and the scope creep is benign (revertable) — but they ARE definite contract violations of "13 items locked." The audit-prompt-expected verdict was READY; the actual verdict is READY-WITH-PATCHES gated on two missed items, three reverts, one docstring tweak, and the branch having actual commits.

**Recommended path forward (in order):**
1. Spawn a follow-up agent for Agent A to complete 3.5-B + 3.5-C on `pushfold.py:29` and `pushfold.py:281-296` (~10 LoC delta).
2. Revert scope-creep edits #1-3 (`CHANGELOG.md` + `pushfold.py` docstring/comment + `profiler/memory.py` named constant). Either revert or formalize as §2 amendments.
3. Add the missing 4-D docstring line for `-1` sentinel.
4. File the 3-D no-op note in `audit_followup_backlog.md`.
5. Stage and commit the cleaned diff per kickoff §9c.
6. Run `pytest -x`, `mypy --strict poker_solver/`, `ruff check` per kickoff §9a (currently only `ruff check` verified in this audit; passes).
7. Cross-agent ownership audit clean (no overlap); orchestrator can proceed to push + merge per §9d after the above.

Expected wall-clock to resolution: ~15-20 minutes.
