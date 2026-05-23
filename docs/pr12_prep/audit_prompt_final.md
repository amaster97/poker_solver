# PR 12 audit agent prompt (FINAL — pre-staged for post-fan-out dispatch)

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.
>
> **Pre-stage anchors (orchestrator-side only — DO NOT include in prompt):**
> - Expected verdict per `audit_preprep.md` §3: READY-WITH-PATCHES (~45%) > NOT-READY (~30%) > clean READY (~15%) > READY-with-stability-must-fix (~10%).
> - Top three pre-flagged risk surfaces (audit MUST touch with file:line evidence): approximate-equilibrium badge unsuppressible (`audit_preprep.md` §1.1), per-pair BR not "exploitability" (§1.2), side-pot math TDA fixtures (§1.3).
> - PR 12 is the LARGEST single PR (6-12 week estimate) AND the ONLY one shipping an explicitly approximate solution concept. **The audit verdict on framing is the audit verdict on PR 12.** Silent "Nash"/"GTO"/"exploitability" claims in 3-handed code paths are correctness bugs, not cosmetic issues.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-12-three-handed-stretch` branch and you have not seen the design discussions. Your job is to audit the PR 12 implementation (3-handed postflop solve — optional / stretch / explicitly approximate) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 12 is **the only PR in the v1 roadmap that ships an explicitly approximate solution concept.** This audit pays special attention to the framing discipline — silent "Nash"/"GTO"/"exploitability" claims in 3-handed code paths are correctness bugs, not cosmetic issues.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-12-three-handed-stretch` (branched from `integration` AFTER ALL of PR 1-11 land on `main` AND v1 is tagged AND user explicitly approves the launch per `fanout_ready.md` §0).
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` — read end-to-end first. §3 (theoretical honesty) is the spec's reason for existing.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 12 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + approximate framing — LOAD-BEARING), §2 (non-goals + no DCFR_{1.5,0,2} for 3p), §3 (theoretical honesty — what CFR proves and doesn't prove for n-player; Gibson IDSD is much weaker than Nash convergence), §4 (game-state changes for N-player; positions LOCKED P0=SB, P1=BB, P2=BTN), §5 (memory + abstraction), §6 (files, including the "≈ approximate" badge in §6.3 that's unsuppressible), §7 (validation strategy — per-pair BR, stability diagnostic, Monker opt-in), §9 (critical correctness items, 10 items), §10 (risks), §11 (effort estimate 6-12 weeks).
2. **The branch diff:** `git diff integration...HEAD` while on `pr-12-three-handed-stretch`. Also `git log integration..HEAD --oneline`.
3. **The autonomous log:** PR 12 entries.
4. **The actual new / modified files:** at minimum
   - `poker_solver/multiway_solver.py`
   - `poker_solver/hunl.py` (generalized to N-player per §4)
   - `poker_solver/action_abstraction.py` (`ActionContext.num_players` plumbing)
   - `poker_solver/solver.py` (3p routing branch)
   - `poker_solver/cli.py` (`--num-players` flag)
   - `poker_solver/__init__.py` (re-exports)
   - `crates/cfr_core/src/multiway.rs`
   - `tests/test_3p_core.py`
   - `tests/test_3p_solve.py`
   - `tests/test_3p_diff.py`
   - `tests/fixtures/multiway_fixtures.py`
   - `ui/views/range_matrix.py` (modified — approximate badge + 3-up display)
   - `ui/views/run_panel.py` (modified — `num_players` toggle + 3-range input + per-pair BR display)
   - `ui/views/library_browser.py` (modified — 3p badge)
   - any other touched files

Do not actually run a 3p solve. Audit the *committed* code + tests.

## Audit focus areas (each MUST be touched in the report with file:line evidence)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity. Pre-flagged HIGH-PROB items (§1.1, §1.2, §1.3 per `audit_preprep.md`) MUST receive paragraph-level discussion even if no defect is found.

1. **"≈ approximate equilibrium" badge present and UNSUPPRESSIBLE on every output surface.** [HIGH-PROB must-fix per `audit_preprep.md` §1.1]
   - Per spec §1 + §6.3 + §9 #10: the badge MUST appear on every UI surface displaying a 3-handed result. Spec §6.3 locks the exact text:
     - Badge: "≈ approximate equilibrium / multi-player; not Nash"
     - Tooltip: "Three-handed solves use Linear CFR on a heavily-abstracted tree. Multi-player CFR has no Nash convergence proof (Brown & Sandholm 2019, Pluribus); the strategy shown is one approximate fixed point among potentially many. Best-response gaps below are per-pair upper bounds, not Nash exploitability."
   - Placement: top of range matrix display panel, top of library row entry, top of CLI stdout result block (3-line text banner with `===` borders).
   - **No CLI / config flag to suppress.** Per §9 #10: "Approximate-equilibrium badge cannot be disabled. ... This is a load-bearing user-experience commitment."
   - **Pre-flagged failure modes** (auditor MUST probe each per `audit_preprep.md` §1.1):
     - (a) **Suppression path slipped in** — grep `poker_solver/cli.py`, `ui/views/*.py`, `multiway_solver.py` for `--suppress-badge`, `--quiet-approximate`, `verbose=False`-conditioned skip. Any match → must-fix.
     - (b) **Surface gap** — JSON serialization paths that don't go through UI rendering layer omit the badge field. Must-fix.
     - (c) **Loose assertion in test** — `test_badge_cannot_be_disabled_via_config` matches substring instead of exact byte-text. Should-fix.
   - **Evidence stub:** `poker_solver/multiway_solver.py:?` — badge constant; UI rendering hooks; CLI stdout block; test assertions.

2. **String-literal audit: NO bare "Nash" / "GTO" / "exploitability" in 3p paths.** [HIGH-PROB must-fix per `audit_preprep.md` §1.2]
   - Per §9 #4 + §15 audit focus: run the exact grep from `fanout_ready.md` §5 line 134:
     ```sh
     grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'
     ```
   - Expected ZERO output. Any unaccompanied bare "exploitability" / "Nash" / "GTO" in 3-handed-relevant code path → **must-fix**.
   - **Pre-flagged failure modes** (auditor MUST probe each):
     - (a) **`MultiwaySolveResult.exploitability: tuple[float, float, float]` "to match HU API"** — most common Agent B violation per `fanout_ready.md` line 137. Must-fix.
     - (b) **Docstring "Nash convergence" without "no" qualifier** — must-fix.
     - (c) **Comment slip** — "Gibson 2013 establishes CFR convergence for n-player games" — OVERCLAIMS; Gibson proves IDSD only; Nash convergence remains open (spec §3.1 line 90). Must-fix.
   - The string `"exploitability"` is a reserved term for the 2p0s metric and we don't reuse it for 3-handed. Spec §1 + §3.4: never claim "Nash" or "GTO" or "optimal" for 3-handed. Only "approximate equilibrium" / "blueprint" / "approximate solution".
   - **Evidence stub:** verbatim grep output included in the report's "Approximate-framing audit" section.

3. **Side-pot math correctness (5 TDA fixtures).** [HIGH-PROB must-fix per `audit_preprep.md` §1.3]
   - Per spec §9 #1 + §10.3 risk + §15 audit focus: "the single hardest correctness item in 3-handed." Pio, postflop-solver, and Slumbot all have public bug reports on side-pot edge cases.
   - `_compute_side_pots(contributions, folded) -> list[SidePot]` helper with 5+ unit-test fixtures (per `fanout_ready.md` §5 lines 142-145):
     1. Equal-stack all-in `[50,50,50]` → main pot 150, no side pots.
     2. Unequal `[50,100,150]` → main 150 + side 100 + P2 returns 50.
     3. Folded `[50,30(F),100]` → folded's 30 to main; eligible={0,2}.
     4. Tie split with remainder by position (SB first postflop).
     5. Odd-chip floor/ceiling vs TDA examples.
   - Each side pot won by the live player with best hand WHO CONTRIBUTED to that pot.
   - **Pre-flagged failure mode (most likely):** Fixture 4 — position semantics under-specified in §9 #1; agent picks wrong tiebreak (dealer button vs SB). Must-fix on ANY of 5 fixture failures; "most likely bug class" per §10.3.
   - **Evidence stub:** `tests/test_3p_core.py:?` — all 5 fixtures + `_compute_side_pots()` impl.

4. **Per-pair BR (NOT "exploitability") — THREE numbers, NOT summed.**
   - Per §7.3 + §9 #3: for each player p, compute `BR_gap_p = v_p^{best}(σ_{-p}) - v_p(σ_p, σ_{-p})`. THREE numbers per solve, one per player.
   - **Label:** "≈ best-response EV upper bound (multi-player; NOT Nash exploitability)" per §7.3 line 419.
   - **DO NOT sum them, do not report a single number, do not call any of these "exploitability".** In 2p0s, sum of BR gaps IS Nash exploitability up to a factor of 2; the same does not hold for n>2.
   - BR walk weights opponents at decision nodes by their joint strategy — not by either individually treated as fixed.
   - Field name: `br_gap`, NOT `exploitability` (most common Agent B violation per `fanout_ready.md` line 137).
   - Tested: synthetic 3p tree where BR-against-joint differs from BR-against-either-individual (§9 #3).
   - **Evidence stub:** `poker_solver/multiway_solver.py:?` — `compute_per_pair_br()` + return type.

5. **Convergence stability diagnostic (3-seed L1 < 0.05).**
   - Per §7.4 + §9 (stability discussion): `StabilityReport` with 3 seeds `(0, 1, 2)`, pairwise L1 distance between strategy pairs.
   - **Fields:** `seeds`, `strategies`, `l1_per_infoset`, `pairwise_max`, `pairwise_mean`.
   - **Soft assertion:** `pairwise_max < 0.05` (5% in L1 per infoset) on the river-only fixture.
   - If it fails, the user is warned that multi-player CFR has no convergence guarantee (per §3.1 #4) and the badge in §6.3 gains an extra line: "⚠ stability degraded".
   - **Determinism:** rerunning same seeds yields same numbers (per `audit_preprep.md` §1.7). Test: `test_stability_diagnostic_is_deterministic`. **Must-fix if `np.random.default_rng()` used without explicit seed threading.**
   - **Evidence stub:** `poker_solver/multiway_solver.py:?` — `run_stability_diagnostic()` + determinism test.

6. **Linear CFR (LCFR, not DCFR_{1.5,0,2}) for 3-handed.**
   - Per §2 + §3.2 + §9 #7: LCFR (DCFR_{1, 1, 1}) for iterations 1..t_cutoff, then plain CFR averaging thereafter.
   - **Default `t_cutoff = T // 2`** per Pluribus's recipe (paper p. 3).
   - **NOT DCFR_{1.5, 0, 2}** for 3-handed: β=0 behavior of truncating negative regret is a 2p0s heuristic; for n-player the conservative choice is LCFR which Pluribus validated.
   - Configurable via `dcfr_kwargs={'lcfr_cutoff': T//2}` per §9 #7.
   - **Pre-flagged failure mode** (auditor MUST probe): Agent copy-pastes PR 7 DCFR pattern → must-fix (overclaims Pluribus's empirical validation).
   - **Evidence stub:** `poker_solver/multiway_solver.py:?` or `crates/cfr_core/src/multiway.rs:?` — averaging loop with LCFR cutoff.

7. **Negative-regret pruning in 95% of iterations.**
   - Per §3.2 + §9 #8: actions with very negative regret are skipped 95% of the time, speeding up convergence ~3×.
   - Pruning threshold C is configurable; default `-300_000` cents per §9 #8 + §12.8 risk.
   - Implementation: `random.random() < 0.95` skip.
   - Tested indirectly via per-iteration wallclock improvement.
   - **Evidence stub:** `crates/cfr_core/src/multiway.rs:?` or `poker_solver/multiway_solver.py:?` — pruning branch.

8. **N-player turn rotation (SB → BB → BTN).**
   - Per §4.1 + §9 #4: positions LOCKED at "P0 = SB (acts first preflop AND postflop), P1 = BB, P2 = BTN."
   - Action turn advances to the **next non-folded, non-all-in player** in post-SB rotation.
   - Street ends when all live players have either matched current `street_aggressor`'s contribution OR are all-in for less.
   - Per §4.3: action turn order implemented for N=2 and N=3 specifically. **`num_players >= 4` raises `NotImplementedError`.**
   - **Evidence stub:** `poker_solver/hunl.py:?` — rotation function for N=3.

9. **Routing in `solver.py`: `num_players >= 4` clear error.**
   - Per §6.2 + §9 #5: routing branch — `config.num_players == 3 and starting_street >= Street.FLOP` → `solve_3p_postflop`. HU path unchanged. `num_players >= 4` → clear `NotImplementedError("PR 12 supports N=2 and N=3 only; 4+ players require a separate solve infrastructure.")`.
   - **`num_players == 3` AND `starting_street == Street.PREFLOP`** → either error (since preflop is explicitly out-of-scope per §2) or routes to a 3p-preflop NotImplemented. Verify either way.
   - **Evidence stub:** `poker_solver/solver.py:?` — routing branch.

10. **3-way showdown evaluation (multi-winner per side pot).**
    - Per §9 #2: when ≥2 live players remain at river end, each player's hand evaluated against 5-card board. Best hand wins each side pot they contributed to.
    - Reuses `poker_solver.evaluator` per-player. New logic: **multi-winner per side pot** path.
    - Tested: 3-way showdown where each player wins a different side pot.
    - **Evidence stub:** `poker_solver/multiway_solver.py:?` — showdown function; `tests/test_3p_core.py:?` — 3-way showdown test.

11. **Regression on N=2 path: all PR 1-11 tests pass.** [Agent A reconciliation lock — must-fix on regression]
    - Per §9 #6 + `audit_preprep.md` §1.5: the N-player generalization is strictly additive on the N=2 path. All PR 3/4/5/6/7/8/9/10/11 tests must pass unchanged.
    - `HUNLConfig.num_players: int = 2` default unchanged.
    - `_post_blinds_2p()` is the existing path; `_post_blinds_3p()` is new. Routing by `num_players`.
    - `folded`/`all_in` fields generalized to `tuple[bool, ...]` length=`num_players` (no field rename).
    - **Pre-flagged failure mode:** Field rename "for clarity" (`folded` → `is_folded`) → cascading break in Agent B/C consumer code. Must-fix.
    - **Evidence stub:** `git diff integration -- poker_solver/hunl.py` — field signatures unchanged; full pytest passes.

12. **MonkerSolver cross-validation is OPT-IN (no bundled data).**
    - Per §7.5 + §12 open decision 3: the test is decorated `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`. Skipped when user has no Monker data.
    - **No bundled data** (license). Format documented; user populates manually.
    - Tolerance: per-infoset L1 < 0.10 (§7.5 line 450).
    - **Pre-flagged failure mode:** Agent commits sample Monker fixture from a forum post (license unknown). Must-fix on bundled data.
    - **Evidence stub:** `tests/test_3p_solve.py:?` — skipif decorator; `git ls-files tests/fixtures/monker/` (expect empty).

13. **Python ↔ Rust differential test for 3p.**
    - Per §6.1 + §14 success criteria: `tests/test_3p_diff.py` (~3 tests). Tiny 3p river subgame (~1k infosets, ~tens of seconds).
    - Tolerance: per spec §14 "differential test passes on the tiny 3p river subgame (Python ↔ Rust strategy **L1 < 1e-6** after 500 iterations on shared inputs)". Note this is tighter than HU diff tolerance (5e-3); the small fixture justifies it.
    - **Anti-pattern:** if the tolerance is silently relaxed (e.g., to 1e-3 or 1e-2), flag must-fix.
    - **Evidence stub:** `tests/test_3p_diff.py:?` — tolerance literal.

14. **CLI `--num-players` flag.**
    - Per §6.2 + §12 open decision 13: `--num-players` flag (default 2). When 3, `--ranges` must accept three comma-separated range strings (e.g., `"AA,KK / AKs+ / 76s+"`).
    - Documented in `--help`. No `solve-3p` subcommand proliferation.
    - **Evidence stub:** `poker_solver/cli.py:?` — flag registration + `--help` text.

15. **License hygiene.**
    - Per §15 audit focus: no code copied from `postflop-solver` or `TexasSolver` (both AGPL) for multi-player logic. Read-only inspiration only.
    - Pluribus paper cited from `references/papers/pluribus_brown_2019_science.pdf` for the LCFR + 95% pruning recipe.
    - Gibson 2013 cited for the regret-minimization-eliminates-dominated-actions theorem (IDSD ONLY; NOT Nash convergence per spec §3.1 line 90).
    - **Pre-flagged failure mode:** Docstring claims "Gibson 2013 establishes CFR convergence for n-player games" — OVERCLAIMS. Must-fix.
    - **Evidence stub:** `poker_solver/multiway_solver.py:?` — module docstring + citation comments.

16. **Iteratively-strict-dominated actions vanish (strongest provable property).**
    - Per §7.2 #3 + §13 Gibson reference: CFR eliminates iteratively strictly dominated actions even in n-player non-zero-sum games. Construct a 3p toy subgame where one action is strictly dominated; solve; assert that action's frequency converges to 0 (within ε).
    - This is the strongest theoretical property we can verify; Gibson 2013 result.
    - **Evidence stub:** `tests/test_3p_solve.py:?` — `test_iteratively_dominated_action_vanishes` or similar.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/audit_report.md` with this exact structure:

```markdown
# PR 12 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-12-three-handed-stretch
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_3p_*.py — pass/fail; cargo test — pass/fail; full suite delta]

## Must-fix

[Badge suppressible / missing on any output surface; bare "Nash"/"GTO"/"exploitability" in 3p code paths; side-pot math wrong on any of 5 fixtures; per-pair BR labeled "exploitability"; LCFR not implemented (using DCFR_{1.5,0,2} for 3p); N>=4 not rejected; 3-way showdown multi-winner logic wrong; regression in N=2 path; license contamination (postflop-solver / TexasSolver code copied); MonkerSolver data bundled; Gibson 2013 overclaim. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Missing stability diagnostic, missing iteratively-dominated-action test, ambiguous badge text, awkward APIs, test holes (e.g., missing side-pot edge case), loose substring badge assertion. Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: Pluribus + Gibson papers cited from `references/papers/`; no code copied from postflop-solver/TexasSolver (both AGPL); no MonkerSolver code/data bundled. Cite specific module docstrings.]

## Approximate-framing audit

[A dedicated section: grep results for "Nash", "GTO", "exploitability" in 3p code paths. List every match. For each: is it in a 3p-relevant path? Is it accompanied by "≈ approximate" / "best-response" / "near-Nash"? Flag any bare matches as must-fix.

Run the exact grep from spec §9 #4:
    grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'

Include the verbatim output here.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** approximate badge suppressible/missing, bare "Nash"/"GTO"/"exploitability" in 3p path (silently overclaims), side-pot math wrong (silently incorrect chip distribution), per-pair BR mislabeled "exploitability", DCFR_{1.5,0,2} used instead of LCFR, regression in N=2 path, license contamination, MonkerSolver data bundled, Gibson 2013 overclaim, stability diagnostic non-deterministic. Blocks PR.
- **should-fix:** missing stability diagnostic threshold soft-assertion, missing iteratively-dominated test, awkward APIs, loose substring badge assertion, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently overclaims solution quality (calling a 3p result "Nash" or "GTO") → must-fix. Performance / UX issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §3 (theoretical honesty), §6.3 (badge), §9 #4 (string-literal audit), §9 #10 (badge unsuppressible).
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr12_prep/audit_report.md`.
- HIGH-PROB risk surfaces (focus areas 1, 2, 3 — and the three sub-probes in each) MUST get paragraph-level discussion even with no defect found.
- For the string-literal audit, run the exact grep from §9 #4: `grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py crates/cfr_core/src/multiway.rs tests/test_3p_*.py ui/views/ poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'`. Include the verbatim output in the Approximate-framing audit section.
- PR 12's deliverable is **not the solver**, it is the **honesty of the framing**. The audit verdict on framing is the audit verdict on PR 12.

Begin by reading the spec (especially §3 theoretical honesty + §6.3 badge spec + §9 critical correctness items), then the diff, then the new files. Then write the report.
