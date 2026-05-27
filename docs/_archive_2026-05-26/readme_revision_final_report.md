# README Revision Final Report — 2026-05-23

Pass over `docs/README_proposed_update_2026-05-23.md` to fold in the
.dmg DMG-NEEDS-FIX empirical verdict, lead with the working source
install, verify all CLI commands against `poker_solver/cli.py`, and
trim to the ~250-line cap.

## (a) Sections changed

| Section | Change |
|---|---|
| **Header wrapper (lines 1-19)** | Rewrote the "why this draft exists" preamble to cite the two empirical verdicts that landed today (.dmg launch failure; v1.5.0 acceptance pending test-side fixes). Removed stale "tone target" stanza and the historical "RE-REVISED" lineage notes. |
| **Tagline (top of README)** | Trimmed from ~22-line trajectory paragraph to a single ~9-line capability summary. Dropped the v1.0.0 → v1.5.1 ship-by-ship recitation (CHANGELOG carries that history). |
| **Status** | Replaced. Six bullets covering version, license, platforms, Python floor (3.9+ per `pyproject.toml`, not 3.11+), working install path, and the explicit ".dmg = experimental" demotion. Removed the v1.4.0 .dmg "latest installer" framing entirely. |
| **Features** | Removed as a standalone section. The capability list is now compressed into the tagline. Per-feature paragraphs were redundant with the Quick start and Known issues. |
| **Install (renamed from Installation)** | Now leads with `pip install -e .` from source. Added explicit `cargo build --release --manifest-path crates/cfr_core/Cargo.toml` for users who want the Rust crate without Python wrapper. Dropped the v1.4.0 .dmg pointer from this section (relocated to Known issues). |
| **Quick start** | Verified every CLI command against `poker_solver/cli.py`. Added the postflop `--hunl-mode postflop --board "..." --stacks N --bet-sizes "..."` example (real, well-supported flag set). Moved the push/fold lookup to the Python API since there is no `pushfold` CLI subcommand. Cut the abstraction precompute one-liner (still real, but not Quick-start tier — power users will find it in USAGE.md). |
| **Python API** | Slimmed from ~45 lines to ~25. Cut the equity / Kuhn examples (duplicate of CLI snippets above). Kept node locking, aggregator, vector-form patterns — the API-only entry points. Folded the "aggregator vs vector form" subsection in here as a 14-line distillation rather than a separate top-level section. |
| **UI** | Kept as a short 4-line section. Added the **explicit warning** that the packaged `.dmg` GUI does not currently work and to use CLI / Python API today. |
| **Architecture (brief)** | Tightened from ~14 lines to ~10. Kept the load-bearing facts (two-tier, DCFR defaults, diff-test files) and pointed at `DEVELOPER.md` for the rest. |
| **Development** | Kept lint / test / pre-PR commands verbatim. Removed the paragraph on per-PR branch / audit policy (that's in CONTRIBUTING.md; the README pointer is enough). |
| **Known issues (renamed from Known limitations)** | Reordered with the .dmg issue first (highest-impact for new users). Each bullet states the user-visible symptom, the root cause, and the fix path. Six bullets total: .dmg, v1.5.0 acceptance failure, Range fractional frequency, CLI ergonomic gaps, chance-enum-at-root perf, CSV batch-solve quoting. |
| **References** | Compressed `setup_references.sh` to a one-line inline instruction. Dropped paper subtitles to save lines. |
| **Notation, License** | Light trim of redundant wording. |
| **Sections REMOVED entirely** | "Trajectory" paragraph (moved to CHANGELOG reference); "Features" detail block; "Contributing" prose (one line in Development); per-feature `tests/test_*.py` filename callouts (a CHANGELOG / test-tree concern, not README); the closing "Notes on the draft" review-meta block. |
| **Sections that did NOT exist before and were ADDED** | None — kept the structure but rebalanced what's in each section. |

## (b) Line count

| | Lines |
|---|---|
| Starting draft (full file) | 519 |
| Final draft (full file) | 279 |
| Final embedded README (content inside the ````markdown … ```` fence, including the two fence lines) | 255 |
| Final embedded README (content only, fence markers excluded) | 253 |

Hit the user's ~250-line cap. ~46% reduction.

## (c) CLI commands — verification against `poker_solver/cli.py`

All CLI commands cited in the final draft were verified against
`poker_solver/cli.py` and resolve to a real subparser + handler:

- `poker-solver equity HAND [HAND ...] [--board ...] [-n ...] [--seed ...]` — verified at `cli.py:600-629`.
- `poker-solver solve --game {kuhn,leduc,hunl} [--hunl-mode {tiny_subgame,postflop,full}] [--board ...] [--stacks N] [--bet-sizes ...] [--iterations N] [--backend {python,rust}] [--target-exploitability ...] [--log-every N] [--max-memory-gb ...] [--abstraction ...] [--seed ...]` — verified at `cli.py:631-731`.
- `poker-solver ui [--port N] [--host ...] [--dark-mode ...]` — verified at `cli.py:777-793`.

CLI commands that do NOT exist and that I therefore did NOT mention
(but flagged as gaps in Known issues per the user's guidance):

- `poker-solver pushfold` — not implemented; flagged in Known issues; Python API used in Quick start instead.
- `poker-solver river` — not implemented; flagged.
- `poker-solver parity` — not implemented; flagged.

Python API surface verified against the `poker_solver` package
`__init__.py` exports implied by `cli.py` imports (`equity`, `solve`,
`HUNLConfig`, `HUNLPoker`, `Range`, `parse_board`, `parse_hand`,
`KuhnPoker`, `LeducPoker`, `default_tiny_subgame`, `get_pushfold_strategy`,
`get_full_range`, `solve_range_vs_range`, `solve_hunl_postflop`,
`solve_hunl_preflop`). `solve_range_vs_range_rust` lives on
`poker_solver._rust` per the established import pattern; the README
shows that exact import path.

**No CLI command was cited that I could not verify.** No human-review
flags.

## (d) Tension between honesty and invitingness — how resolved

Three tensions, each with the resolution I picked:

1. **".dmg installer in Known issues" vs "this looks broken"** — Leading
   with a broken-installer disclosure can read like "this whole project
   is shaky." Resolved by: (a) keeping the tagline upbeat and
   capability-focused; (b) putting the working install path (`pip
   install -e .`) right after Status, before the user encounters any
   bad news; (c) framing the Known issues bullet as "does not currently
   work, packaging-fix PR queued, use the source install above" — i.e.
   it's a known fix-in-flight, not a fundamental problem.

2. **"v1.5.0 acceptance test FAILS" vs "three reviews confirm
   correctness"** — Saying acceptance fails as the headline reads as a
   broken solver; burying it reads as dishonest. Resolved by putting
   both clauses in the same bullet, in that order: state the failure
   first (capital-letter FAILS to signal severity), immediately give
   the diagnosis (three test-side encoding artifacts), then cite the
   three independent code reviews confirming algorithmic correctness,
   then state the expected post-fix outcome, and finally retain the
   10-15% residual caveat the user explicitly requested. The user's
   guidance "more concerned that the code itself will run and give
   expected results" is honored — the bullet leaves no doubt that this
   is a test-side issue, not a solver issue, while still flagging
   residual uncertainty.

3. **Capability breadth vs "not flashy"** — The system does in fact
   ship a lot (push/fold, postflop, preflop, RvR aggregator + vector,
   node locking, library mode, EMD bucketing, NiceGUI). The earlier
   draft enumerated each as a bullet — invited but felt boastful.
   Resolved by compressing into one informational tagline paragraph,
   then letting the Quick start commands prove the breadth concretely.
   A reader who can run `poker-solver solve --game hunl --hunl-mode
   postflop ...` and see real output is more reassured than a reader
   who reads a feature checklist.

## Files modified

- `/Users/ashen/Desktop/poker_solver/docs/README_proposed_update_2026-05-23.md` (519 → 279 lines).
- `/Users/ashen/Desktop/poker_solver/docs/readme_revision_final_report.md` (this report; new).

## Files NOT modified

- `/Users/ashen/Desktop/poker_solver/README.md` — per the draft's own
  "Status: DRAFT for user review. Do NOT apply directly to `README.md`
  until reviewed" disclaimer, the production README remains untouched.
  User reviews the draft, then applies the markdown-fenced content as
  the new `README.md` body.
