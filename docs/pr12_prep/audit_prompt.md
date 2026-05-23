# PR 12 audit agent prompt

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh general-purpose `Agent(...)` invocation. Do not include this header in the prompt itself.

---

You are a **fresh code reviewer with NO implementation context**. You did not write any of the code on the `pr-12-three-handed-stretch` branch and you have not seen the design discussions. Your job is to audit the PR 12 implementation (3-handed postflop solve — optional / stretch / explicitly approximate) against the spec and report findings in a structured Markdown report.

Treat the spec as the source of truth. Do not make assumptions about behavior not specified there; if you find unspecified behavior, flag it.

PR 12 is **the only PR in the v1 roadmap that ships an explicitly approximate solution concept.** This audit pays special attention to the framing discipline — silent "Nash"/"GTO"/"exploitability" claims in 3-handed code paths are correctness bugs, not cosmetic issues.

## Repository context

- **Repo root:** `/Users/ashen/Desktop/poker_solver`
- **Branch under audit:** `pr-12-three-handed-stretch` (branched from `integration`)
- **Spec:** `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/pr12_spec.md` — read end-to-end first. §3 (theoretical honesty) is the spec's reason for existing; everything below references it.
- **Implementation log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md` — skim PR 12 entries.

## Inputs to read (in order)

1. **The spec:** internalize §1 (goal + approximate framing — LOAD-BEARING), §2 (non-goals), §3 (theoretical honesty — what CFR proves and doesn't prove for n-player), §4 (game-state changes for N-player), §5 (memory + abstraction), §6 (files, including the "≈ approximate" badge in §6.3 that's unsuppressible), §7 (validation strategy), §9 (critical correctness items, 10 items), §10 (risks), §11 (estimated effort — 6–12 weeks).
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

## Audit focus areas (each MUST be touched in the report)

For each focus area, either confirm correct ("Looks good" with file:line evidence) or flag under the appropriate severity.

1. **"≈ approximate equilibrium" badge present and UNSUPPRESSIBLE on every output surface.**
   - Per spec §1 + §6.3 + §9 #10: the badge MUST appear on every UI surface displaying a 3-handed result. Spec §6.3 locks the exact text:
     - Badge: "≈ approximate equilibrium / multi-player; not Nash"
     - Tooltip: "Three-handed solves use Linear CFR on a heavily-abstracted tree. Multi-player CFR has no Nash convergence proof (Brown & Sandholm 2019, Pluribus); the strategy shown is one approximate fixed point among potentially many. Best-response gaps below are per-pair upper bounds, not Nash exploitability."
   - Placement: top of range matrix display panel, top of library row entry, top of CLI stdout result block (3-line text banner with `===` borders).
   - **No CLI / config flag to suppress.** Per §9 #10: "Approximate-equilibrium badge cannot be disabled. ... This is a load-bearing user-experience commitment."
   - Tested: verify each output surface emits the badge.

2. **String-literal audit: NO bare "Nash" / "GTO" / "exploitability" in 3p paths.**
   - Per §9 #4 + §15 audit focus: `grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py ui/views/library_browser.py | grep -v 'best-response\|approximate\|≈\|near-Nash'` should yield only commented references to historical papers.
   - Any unaccompanied bare "exploitability" / "Nash" / "GTO" in 3-handed-relevant code path → **must-fix**.
   - Spec §1 + §3.4: never claim "Nash" or "GTO" or "optimal" for 3-handed. Only "approximate equilibrium" / "blueprint" / "approximate solution".
   - The string `"exploitability"` is a reserved term for the 2p0s metric and we don't reuse it for 3-handed.

3. **Side-pot math correctness.**
   - Per §9 #1 + §10.3 risk + §15 audit focus: this is "the single hardest correctness item in 3-handed." Pio, postflop-solver, and Slumbot all have public bug reports on side-pot edge cases.
   - `_compute_side_pots(contributions, folded) -> list[SidePot]` helper with 5+ unit-test fixtures:
     - 3-way all-in at equal stacks → one main pot, no side pots.
     - 3-way all-in at unequal stacks → one main + one side pot.
     - 3-way: two all-in at different stacks, one folded → main pot only.
     - Tie at showdown across a side pot → pot split among tied contributors.
     - Floor/ceiling correctness on odd-chip splits.
   - Each side pot won by the live player with best hand WHO CONTRIBUTED to that pot.

4. **Per-pair BR (NOT "exploitability").**
   - Per §7.3 + §9 #3: for each player p, compute `BR_gap_p = v_p^{best}(σ_{-p}) - v_p(σ_p, σ_{-p})`. THREE numbers per solve, one per player.
   - **Label:** "≈ best-response EV upper bound (multi-player; NOT Nash exploitability)".
   - **DO NOT sum them, do not report a single number, do not call any of these "exploitability".** In 2p0s, sum of BR gaps IS Nash exploitability up to a factor of 2; the same does not hold for n>2.
   - BR walk weights opponents at decision nodes by their joint strategy — not by either individually treated as fixed.
   - Tested: synthetic 3p tree where BR-against-joint differs from BR-against-either-individual (§9 #3).

5. **Convergence stability diagnostic (3-seed L1 < 0.05).**
   - Per §7.4 + §9 (stability discussion): `StabilityReport` with 3 seeds `(0, 1, 2)`, pairwise L1 distance between strategy pairs.
   - **Soft assertion:** `pairwise_max < 0.05` (5% in L1 per infoset) on the river-only fixture.
   - If it fails, the user is warned that multi-player CFR has no convergence guarantee (per §3.1 #4) and the badge in §6.3 gains an extra line: "⚠ stability degraded".
   - Stability diagnostic itself must be deterministic — running it twice with same seeds produces same numbers.

6. **Linear CFR (LCFR, not DCFR_{1.5,0,2}) for 3-handed.**
   - Per §2 + §3.2 + §9 #7: LCFR (DCFR_{1, 1, 1}) for iterations 1..t_cutoff, then plain CFR averaging thereafter.
   - **Default `t_cutoff = T // 2`** per Pluribus's recipe (paper p. 3).
   - **NOT DCFR_{1.5, 0, 2}** for 3-handed: β=0 behavior of truncating negative regret is a 2p0s heuristic; for n-player the conservative choice is LCFR which Pluribus validated.
   - Configurable via `dcfr_kwargs={'lcfr_cutoff': T//2}` per §9 #7.

7. **Negative-regret pruning in 95% of iterations.**
   - Per §3.2 + §9 #8: actions with very negative regret are skipped 95% of the time, speeding up convergence ~3×.
   - Pruning threshold C is configurable; default `-300_000` cents per §9 #8 + §12.8 risk.
   - Tested indirectly via per-iteration wallclock improvement.

8. **N-player turn rotation (SB → BB → BTN).**
   - Per §4.1 + §9 #4 + §15 audit focus: position semantics LOCKED at "P0 = SB (acts first preflop AND postflop), P1 = BB, P2 = BTN."
   - Action turn advances to the **next non-folded, non-all-in player** in post-SB rotation.
   - Street ends when all live players have either matched current `street_aggressor`'s contribution OR are all-in for less.
   - Per §4.3: action turn order implemented for N=2 and N=3 specifically. **`num_players >= 4` raises `NotImplementedError`.**

9. **Routing in `solver.py`: `num_players >= 4` clear error.**
   - Per §6.2 + §9 #5: routing branch — `config.num_players == 3 and starting_street >= Street.FLOP` → `solve_3p_postflop`. HU path unchanged. `num_players >= 4` → clear `NotImplementedError("PR 12 supports N=2 and N=3 only; 4+ players require a separate solve infrastructure.")`.
   - **`num_players == 3` AND `starting_street == Street.PREFLOP`** → either error (since preflop is explicitly out-of-scope per §2) or routes to a 3p-preflop NotImplemented. Verify either way.

10. **3-way showdown evaluation.**
    - Per §9 #2: when ≥2 live players remain at river end, each player's hand evaluated against 5-card board. Best hand wins each side pot they contributed to.
    - Reuses `poker_solver.evaluator` per-player. New logic: **multi-winner per side pot** path.
    - Tested: 3-way showdown where each player wins a different side pot.

11. **Regression on N=2 path: all PR 1-11 tests pass.**
    - Per §9 #6 + §15 audit focus: the N-player generalization is strictly additive on the N=2 path. All PR 3/4/5/6/7/8/9/10/11 tests must pass unchanged.
    - `HUNLConfig.num_players: int = 2` default unchanged.
    - `_post_blinds_2p()` is the existing path; `_post_blinds_3p()` is new. Routing by `num_players`.

12. **MonkerSolver cross-validation is OPT-IN.**
    - Per §7.5 + §12 open decision 3: the test is decorated `@pytest.mark.skipif(not Path('tests/fixtures/monker/').exists())`. Skipped when user has no Monker data.
    - **No bundled data** (license). Format documented; user populates manually.
    - Verify the path exists in the test file and is correctly conditional.

13. **Python ↔ Rust differential test for 3p.**
    - Per §6.1 + §14 success criteria: `tests/test_3p_diff.py` (~3 tests). Tiny 3p river subgame (~1k infosets, ~tens of seconds).
    - Tolerance: per spec §14 "differential test passes on the tiny 3p river subgame (Python ↔ Rust strategy **L1 < 1e-6** after 500 iterations on shared inputs)". Note this is tighter than HU diff tolerance (5e-3); the small fixture justifies it.
    - Anti-pattern: if the tolerance is silently relaxed, flag.

14. **CLI `--num-players` flag.**
    - Per §6.2 + §12 open decision 13: `--num-players` flag (default 2). When 3, `--ranges` must accept three comma-separated range strings (e.g., `"AA,KK / AKs+ / 76s+"`).
    - Documented in `--help`. No `solve-3p` subcommand proliferation.

15. **License hygiene.**
    - Per §15 audit focus: no code copied from `postflop-solver` or `TexasSolver` (both AGPL) for multi-player logic. Read-only inspiration only.
    - Pluribus paper cited from `references/papers/pluribus_brown_2019_science.pdf` for the LCFR + 95% pruning recipe.
    - Gibson 2013 cited for the regret-minimization-eliminates-dominated-actions theorem.

16. **Iteratively-strict-dominated actions vanish.**
    - Per §7.2 #3 + §13 Gibson reference: CFR eliminates iteratively strictly dominated actions even in n-player non-zero-sum games. Construct a 3p toy subgame where one action is strictly dominated; solve; assert that action's frequency converges to 0 (within ε).
    - This is the strongest theoretical property we can verify.

## Output format

Write your report to `/Users/ashen/Desktop/poker_solver/docs/pr12_prep/audit_report.md` with this exact structure:

```markdown
# PR 12 audit report

**Reviewer:** fresh audit agent (no implementation context)
**Branch:** pr-12-three-handed-stretch
**Diff size:** [N modified + M new files = ±X LoC total]

**Test status:** [pytest tests/test_3p_*.py — pass/fail; cargo test — pass/fail; full suite delta]

## Must-fix

[Badge suppressible / missing on any output surface; bare "Nash"/"GTO"/"exploitability" in 3p code paths; side-pot math wrong; per-pair BR labeled "exploitability"; LCFR not implemented (using DCFR_{1.5,0,2} for 3p); N>=4 not rejected; 3-way showdown multi-winner logic wrong; regression in N=2 path; license contamination. Each: file:line + what + fix.]

[If none: "None found." + justification.]

## Should-fix

[Missing stability diagnostic, missing iteratively-dominated-action test, ambiguous badge text, awkward APIs, test holes (e.g., missing side-pot edge case). Each: file:line + description + fix.]

## Nice-to-fix

[Style, naming, comments. Cosmetic.]

## Looks good (explicit confirmation of audit focus areas)

[Numbered list 1-16 matching the 16 audit focus areas above. Each: one-paragraph confirmation with file:line evidence.]

## Spec coverage gaps (missing tests)

[Spec items implemented but not tested. Each: section reference + what's missing + suggested test name.]

## License compliance

[Explicit statement: Pluribus + Gibson papers cited from `references/papers/`; no code copied from postflop-solver/TexasSolver (both AGPL); no MonkerSolver code/data bundled. Cite specific module docstrings.]

## Approximate-framing audit

[A dedicated section: grep results for "Nash", "GTO", "exploitability" in 3p code paths. List every match. For each: is it in a 3p-relevant path? Is it accompanied by "≈ approximate" / "best-response" / "near-Nash"? Flag any bare matches as must-fix.]

## Overall verdict

[One of: "READY for commit", "READY for commit AFTER must-fix items resolved", or "NOT READY — see must-fix". 2-3 sentence justification.]
```

## Severity rules

- **must-fix:** approximate badge suppressible/missing, bare "Nash"/"GTO"/"exploitability" in 3p path (silently overclaims), side-pot math wrong (silently incorrect chip distribution), per-pair BR mislabeled "exploitability", DCFR_{1.5,0,2} used instead of LCFR, regression in N=2 path. Blocks PR.
- **should-fix:** missing stability diagnostic, missing iteratively-dominated test, awkward APIs, test holes. Doesn't block.
- **nice-to-fix:** style, comments. Pure polish.

When in doubt: anything that silently overclaims solution quality (calling a 3p result "Nash" or "GTO") → must-fix. Performance / UX issues → should-fix.

## Procedural notes

- Cite **file paths and line numbers** for every finding.
- Quote spec section numbers, especially §3 (theoretical honesty), §6.3 (badge), §9 #4 (string-literal audit), §9 #10 (badge unsuppressible).
- Spec-silent behavior → "Spec coverage gaps".
- Do not modify code. Audit only. Your only write is to `docs/pr12_prep/audit_report.md`.
- For the string-literal audit, run the exact grep from §9 #4: `grep -ri 'exploitability\|nash\|GTO' poker_solver/multiway_solver.py ui/views/library_browser.py poker_solver/cli.py | grep -v 'best-response\|approximate\|≈\|near-Nash'`. Include the verbatim output in the Approximate-framing audit section.

Begin by reading the spec (especially §3 theoretical honesty + §6.3 badge spec + §9 critical correctness items), then the diff, then the new files. Then write the report.
