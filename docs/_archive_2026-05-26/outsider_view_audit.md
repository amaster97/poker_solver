# Outside-Observer Audit — `github.com/amaster97/poker_solver`

**Date:** 2026-05-23
**Lens:** A developer landing cold on the repo, no prior context. Would
they consider this a credible OSS poker solver project worth a
`pip install -e .`?
**Method:** Read-only via `gh` CLI + GitHub API. No content modified.

---

## 1. First impression (30-second scan)

A developer hitting `github.com/amaster97/poker_solver` sees:

- **Repo description (top of page):** "Texas Hold'em equity solver in
  pure Python: hand evaluator, Monte Carlo equity, range parser, CLI."
  — **STALE.** This was written for the v0.x / v1.0 era and undersells
  the project by an order of magnitude: no mention of Rust tier, HUNL
  solver, GUI, push/fold charts, or range-vs-range Nash. A reader who
  skims only the description would never guess this is a Pio-class
  HUNL solver.
- **Latest release pill:** `v1.7.0` (2026-05-23) — fresh, today's date.
- **License pill:** MIT. Load-bearing per the project's licensing
  story; signals "safe to derive from."
- **Language pill:** Python (primary). Repo size 3,005 KB.
- **No homepage URL set.** No repo topics set. Default GitHub
  presentation; nothing to mistake for a polish push.
- **Stars / forks / watchers: 0 / 0 / 0.** Repo is 3 days old
  (created 2026-05-20). This is fine for the soft-launch posture the
  user is going for — no social signal, but also nothing to
  *explain away*.

**Activity signal:** The Insights → Commits view (or `gh api commits`)
shows ~8 commits in the last 24h with descriptive messages (PR-scoped,
not "wip" / "fix" / "stuff"). Recent commits include README refresh,
.dmg attachment, version-pointer updates, v1.7.0 ship — clearly
under active development, not abandonware.

**30-second verdict:** Repo looks active and serious, but the
description undersells the project. A skimmer would not realize this
is a HUNL solver with a GUI; they'd see "equity solver in pure Python"
and bounce.

---

## 2. README quick scan (the load-bearing entry surface)

**First sentence (after H1):** "A Texas Hold'em equity calculator and
GTO solver, written in Python with a Rust performance tier." — Strong
opener. Front-loads what the project IS in one sentence.

**Front-loaded sections in order:**

1. Title + 1-paragraph description (with the "PioSolver-class HU local
   solving on a MacBook" goalpost stated openly — credible because
   it's framed as the goalpost, not a current claim).
2. Status (versions, licenses, platforms, working install path).
3. Install (from source) — Rust toolchain + `pip install -e .` in 6
   lines. Includes the standalone-cargo path for benchmark users.
4. Quick start (8 working CLI invocations covering equity, Kuhn,
   Leduc, HUNL, postflop). Good coverage; clearly real.
5. Python API (with explicit divergence warning about aggregator vs.
   vector-form CFR — honest about what each entry point does).
6. UI, Architecture, Development, **Known issues** (3 paragraphs,
   explicit + honest), References, Notation, License.

**Honesty signals:** The Known issues section openly states:
- The `.dmg` installer doesn't work on a clean Mac
- The v1.5.0 Brown acceptance test currently FAILS at deep-cap spots
- `Range` fractional frequencies aren't supported yet
- Several CLI ergonomic gaps (push/fold has no subcommand on this
  README — note: v1.7.0 release notes say PR 39 ADDED these
  subcommands, so the README is one revision behind the release)
- CLI batch-solve perf cliff at root chance-enumeration

This is the right posture — flaws stated up front, not buried in
issues.

**Broken cross-refs (verified):**
- `docs/dmg_v1_4_0_smoke_verification.md` — **404 on GitHub.**
  Cited from Known issues. Doc exists on local disk but is not
  pushed to public origin (likely intentional — it contains private
  smoke-test artifacts).
- `docs/v1_6_1_dryrun_verification.md` — **404 on GitHub.** Cited
  from Known issues. Same root cause: internal-only.

Both are addressed by **open PR #4** (`docs(readme): fix broken
cross-ref to internal-only smoke doc`). The PR title is clean and
the body explains the root cause (internal-only docs on private
mirror). Until PR #4 merges, a developer clicking these two links
from the README hits a GitHub 404 page.

**Cross-refs that do resolve on GitHub:**
- `CHANGELOG.md`, `CONTRIBUTING.md`, `DEVELOPER.md`, `LICENSE`,
  `USAGE.md` — all present at repo root.
- `docs/dmg_install_guide.md` and
  `docs/aggregator_vs_true_nash_explainer.md` — both present (good).

**README version drift:** The README says "Latest tagged release:
v1.6.0" and references v1.7.0 as "in flight". v1.7.0 was actually
**published 2026-05-23T23:06Z** (a few hours before this audit). So
the README itself is one version behind reality. Not a credibility
killer — but worth a 5-min fix to bump the version reference.

---

## 3. Releases page

`gh release list --limit 5` returns:

| Tag | Title | Date |
|---|---|---|
| v1.7.0 (Latest) | aggregator→vector wiring + CLI subcommands | 2026-05-23 |
| v1.6.0 | GUI Gate 2 (range editor, RvR, node-locking, asymmetric, slider tiers) | 2026-05-23 |
| v1.5.1 | Test rigor + docs honesty (engine fixes deferred to v1.5.2) | 2026-05-23 |
| v1.5.0 | True Nash range-vs-range | 2026-05-23 |
| v1.4.3 | Validation hardening + Range.diff + docs refresh | 2026-05-23 |

**Five releases in a single day.** A serious developer would
read this in one of two ways: (a) "active development, soft-launch
day, fine"; (b) "are these actually meaningful releases or
version-spam?". The release notes do reflect substantive work, but
the visual pattern is noisy.

**v1.6.0 release notes:** Clean. Lists 6 new GUI features, install
instructions, attached `.dmg` (Apple silicon arm64-only, adhoc-signed,
with explicit Gatekeeper-bypass instructions), Known issues called
out (.dmg experimental; v1.5.0 deep-cap acceptance failure; Range
fractional-frequency missing). `Poker-Solver-1.6.0-arm64.dmg` IS
attached as a release asset — verified.

**v1.7.0 release notes:** Lists the two PRs (43 aggregator→vector
API; 39 CLI subcommands). Test results stated honestly (50/50 + 12/12
+ 6/6). Includes a "Post-release validation findings" section that
documents the class-label vs. combo-level Nash semantics nuance
discovered after release — the framing is **honest** (initial retest
suggested wrapper bug; subsequent diff-test confirmed no bug, but
clarifies how class-expansion works). This is exactly the
research-first failure protocol the user is committed to.

**One concern about v1.7.0 notes:** The post-release section explicitly
points users at "USAGE.md section 5.6" for the full guidance.
**USAGE.md does not yet contain a §5.6** — it's at the v1.4.x
baseline. PR #2 (`docs(usage): v1.7.0 aggregator-vs-Nash +
class-label semantics`) is the in-flight fix. Until PR #2 merges, a
reader who follows the §5.6 pointer from the release notes will land
in USAGE.md and not find the cited section. This is a real broken
forward-reference.

---

## 4. Open issues + PRs

**Open issues: 0.** Repo description says `has_issues: true` so the
tab is available, just empty. For a 3-day-old repo this is expected;
no negative signal.

**Open PRs: 3.** All three are quality:

| # | Title | Branch | Quality |
|---|---|---|---|
| 4 | `docs(readme): fix broken cross-ref to internal-only smoke doc` | pr-49-readme-broken-ref-cleanup | Clean conventional-commits title; body explains root cause |
| 3 | `fix(packaging): v1.4.0 .dmg nicegui bundle + arch + version` | pr-44-dmg-packaging-fix | Excellent — 3 coordinated fixes, verification list, scope-control |
| 2 | `docs(usage): v1.7.0 aggregator-vs-Nash + class-label semantics` | pr-48-usage-v1-7-0-semantics | Strong — context paragraph explains the wrapper-bug walkback honestly |

A developer browsing PRs would see well-formed, fully-documented work
in flight. No abandoned drafts, no "wip" branches, no merge conflicts
visible from the list view. This is a positive credibility signal.

PR base branches are all `main`. PR head branches use the project's
`pr-<n>-<slug>` convention — easy to navigate.

---

## 5. Activity signal

`gh api commits` returns very recent activity (latest commit 2026-05-23
~23:04Z, ~2 hours before this audit ran). Commit messages are
substantive multi-paragraph PR commits explaining the why:

- `v1.7.0: aggregator→vector wiring (PR 43) + CLI subcommands (PR 39)`
- `PR 39: CLI ergonomics subcommands (pushfold, river, parity)`
- `PR 43 / v1.7.0: tests for solve_range_vs_range_nash (12 cases)`
- `PR 43 / v1.7.0: add solve_range_vs_range_nash (vector-form CFR entry)`
- `docs: add macOS .dmg install guide + README pointer`
- `chore: regenerate Cargo.lock for cfr_core 0.6.0`
- `docs: bump README version reference v1.5.1 → v1.6.0`
- `docs: refresh README to v1.5.x + aggregator explainer + CHANGELOG fix`

These read like real engineering history. No `wip` / `fixes` / `more`
stubs. Co-authorship is `Claude Opus 4.7 (1M context)` — explicit
about AI-pair-programming.

---

## 6. Code structure

Top-level layout (verified via `gh api contents`):

```
.github/                  CI config (workflows present)
.gitignore
CHANGELOG.md              Released changelog, Keep-a-Changelog format
CONTRIBUTING.md           PR-flow contract referenced from README
Cargo.lock + Cargo.toml   Rust workspace root
DEVELOPER.md              Architecture deep-dive referenced from README
LICENSE                   MIT
README.md                 Entry surface
USAGE.md                  End-user guide (currently v1.4.x baseline)
assets/                   Static assets (images / UI artifacts)
crates/                   Rust workspace
docs/                     Public docs (.md)
examples/                 Example scripts
poker_solver/             Python package
pyproject.toml            Python build config (PEP 621)
scripts/                  Build / setup scripts
tests/                    Python test suite
ui/                       NiceGUI app
```

This is a textbook two-tier Python+Rust hybrid layout. Anyone who has
worked with `maturin` projects will instantly recognize it. No
unexpected top-level cruft (no `node_modules`, no `.DS_Store` checked
in, no `.idea`). The presence of `examples/`, `docs/`, and `tests/`
all at top level signals a project that is genuinely meant to be used,
not just demo'd.

---

## 7. Comparison to OSS competitors

Per `docs/oss_competitor_comparison_2026-05-23.md` §3, the field looks
like this from an outsider's POV:

| Competitor | License | First-impression read |
|---|---|---|
| `noambrown/poker_solver` | MIT | "Authoritative Brown reference, but river-only, suspended in 2026-01" |
| `b-inary/postflop-solver` | AGPL | "Strong Rust solver — but AGPL is copyleft-poison for downstream commercial use; last commit Oct 2023" |
| `bupticybee/TexasSolver` | AGPL | "Polished Qt GUI but AGPL + heavy C++" |
| `24parida/shark-2.0` | Unlicensed | "Most recent (2026-04-12) but unlicensed → effectively unusable for derivatives" |
| `EricGJackson/slumbot2019` | MIT | "Most algorithmically deep — but CLI-only, C++, no Python, last commit 2023-09" |
| `deepmind/open_spiel` | Apache 2.0 | "Framework, not a poker solver" |

**Our positioning to an outsider:** "The only MIT-licensed two-tier
(Python + Rust) HUNL solver shipping with a modern GUI, two
range-vs-range entry points (per-combo aggregator + joint vector-form
Nash), node locking, and a Kuhn/Leduc diff-tested correctness chain."

That's a real niche, and the repo does demonstrate it. But a developer
landing cold won't know about the niche; they need the **repo
description and README opener** to convey it. The current description
("Texas Hold'em equity solver in pure Python: hand evaluator, Monte
Carlo equity, range parser, CLI.") undersells the niche — it sounds
like one of dozens of equity calculators on PyPI. The README opener
("A Texas Hold'em equity calculator and GTO solver, written in Python
with a Rust performance tier") is much better and accurate.

---

## 8. Red flags

In priority order (most concerning first):

1. **Repo description is stale and undersells the project by ~10x.**
   "Texas Hold'em equity solver in pure Python: hand evaluator, Monte
   Carlo equity, range parser, CLI." — written for the v0.x era. No
   mention of Rust tier, HUNL, GUI, push/fold, range Nash. Most
   developers who Google for "open source poker solver" will see this
   in search results and bounce.

2. **Two broken README cross-refs (404 on GitHub).**
   `docs/dmg_v1_4_0_smoke_verification.md` and
   `docs/v1_6_1_dryrun_verification.md` both 404. Cited from the
   load-bearing Known-issues section. **PR #4 is open and fixes
   this** — but it hasn't merged yet. A developer clicking either
   link from the README right now hits a GitHub 404.

3. **USAGE.md is at v1.4.x baseline; v1.7.0 release notes point to a
   §5.6 that doesn't yet exist.** A reader following the post-release
   v1.7.0 guidance "see USAGE.md section 5.6" will land in USAGE.md
   and not find §5.6. **PR #2 is open and adds it** — but until
   merged, the forward-reference is broken.

4. **USAGE.md contradicts README on install path.** USAGE.md §2 says
   ".dmg (recommended for non-developers)" — but the v1.6.0 release
   notes and README both say source-install is the recommended path
   and the .dmg is experimental. A reader who hits USAGE.md first
   gets a different story.

5. **USAGE.md timeline is stale.** USAGE.md §8 says "PR 9 ships in
   v1.1.0" / "3-handed postflop is post-v1 stretch goal." The repo is
   at v1.7.0 with full preflop solver shipped. USAGE.md reads like a
   pre-launch document.

6. **README "latest version" reference lags reality by 1 tag.** Says
   v1.6.0; actual latest is v1.7.0. Minor — README has v1.7.0 in
   flight wording so a reader can infer.

7. **5 releases shipped in 1 day.** Visually noisy on the Releases
   page. None individually problematic; release notes are substantive.
   But the pattern looks rushed to a cold reader who doesn't know it's
   a deliberate soft-launch day.

8. **No homepage URL set, no GitHub topics.** Two free polish wins;
   topics would make the repo discoverable via topic-search
   (`poker-solver`, `cfr`, `gto`, `texas-holdem`, `nash-equilibrium`,
   `rust-python`, etc.). Homepage URL → could just point at the repo
   description doc or the README itself.

**Not red flags (already clean):**
- No typos found in skimmed text
- No accidentally-pushed secrets / `.env` / credentials
- No accidentally-pushed private docs (private artifacts are
  appropriately filtered, but two stale README references remain —
  see #2)
- License is correctly MIT (matches the project's licensing story)
- Architecture summary is accurate (two-tier Python+Rust with
  differential testing chain — this is real)
- All cited dependencies exist and are pinned to real versions

---

## 9. Recommendations (ordered by impact)

### A. High-impact 5-min fixes

These can ship in a single commit without risk to v1.7.0:

1. **Update the repo description.** A 350-char rewrite that conveys
   the real scope. Candidate:
   > "MIT-licensed HUNL Hold'em GTO solver: Python core + Rust DCFR
   > tier (PyO3), exact + Monte Carlo equity, range-vs-range Nash
   > (aggregator + vector-form CFR), push/fold charts for 2-15 BB,
   > Kuhn/Leduc closed-form solvers, node locking. NiceGUI desktop
   > app. macOS arm64 + Linux source build."
   (≈340 chars; conveys the niche.)

2. **Merge PR #4 (broken README cross-refs).** Already audit-cleared
   per PR title; ship it. Removes the two GitHub 404s from the
   load-bearing Known-issues section.

3. **Add GitHub topics.** Suggested:
   `poker`, `texas-holdem`, `gto`, `cfr`, `nash-equilibrium`,
   `solver`, `python`, `rust`, `pyo3`, `monte-carlo`.

4. **Set the homepage URL** to the GitHub repo or a doc page.
   Even pointing back at `github.com/amaster97/poker_solver` is
   better than empty.

### B. High-impact 1-hour fixes

5. **Merge PR #2 (USAGE.md v1.7.0 update).** Closes the
   "USAGE.md §5.6 doesn't exist" forward-reference from the v1.7.0
   release notes.

6. **One pass of USAGE.md to align with README on install
   recommendations.** Specifically the §2 ".dmg recommended for
   non-developers" line should soften to "experimental — source
   install via pip install -e . is the recommended path; .dmg is
   available for evaluation." This is a 3-line edit.

7. **USAGE.md §8 "what's coming" section.** The "PR 9 ships in
   v1.1.0" / "3-handed postflop post-v1" content is stale (PR 9
   shipped long ago; v1.7.0 is current). Either remove the section
   or rewrite to "Looking ahead to v1.8 / v2" with current candidates.

### C. Polish items for v1.8 / v2

8. **Merge PR #3 (.dmg packaging fix).** Lets the Known-issues
   `.dmg doesn't work` block come out of the README. Note: this is
   audit-cleared per the PR body's verification checklist; the
   blocker is just Gate 5 attachment of the rebuilt artifact.

9. **README "Quick start" should mention the new `pushfold` / `river`
   / `parity` CLI subcommands from v1.7.0.** Right now the README
   says "Push/fold has no dedicated CLI subcommand — use the library
   API" but v1.7.0 just added the subcommand. This is the same drift
   as #6 above; just needs a Quick-start example refresh on the next
   doc pass.

10. **Consider a single "v1.7.0" badge or pinned issue** to orient
    new readers ("Welcome — current release is v1.7.0; see
    CHANGELOG.md for trajectory"). Not required.

### D. Things to leave alone (already good)

- **Don't add a flashy hero image / GIF.** User explicitly wants
  credible not flashy. The current README looks like a serious OSS
  project; adding marketing chrome would weaken that signal.
- **Don't restructure the top-level layout.** Current `poker_solver/`
  + `crates/` + `tests/` + `docs/` + `examples/` + `scripts/` + `ui/`
  is exactly what a `maturin` + Python developer expects.
- **Don't hide the Known issues.** The current explicit Known-issues
  section is a credibility signal — it tells a developer the
  maintainer is honest about flaws. Burying it in `docs/` would
  weaken that.
- **Don't squash the 5 releases into one.** Each has a substantive
  changelog entry; the visual noise is the price of honest
  versioning.
- **Don't add a CI badge spam row.** The repo doesn't need 8
  green-shield badges. A single CI status badge would be fine if one
  isn't already present; more than that is GitHub-marketing noise
  and the user said they don't want flashy.

---

## 10. Final verdict

**NEEDS-POLISH** (high-impact 5-min fixes, then SHARE-READY).

A serious developer landing cold today would:
- **Find the install instructions clear and runnable** (`pip install -e .`
  with Rust toolchain note is exactly what a PyO3 developer expects).
- **Trust the architecture** (two-tier Python+Rust with differential
  testing chain is openly explained in README + DEVELOPER.md).
- **Respect the honesty** (Known issues stated up front; release notes
  acknowledge open investigations and recent walkbacks).
- **Hit two GitHub 404s** if they click into the most prominent
  Known-issues references — this is the only real first-impression
  bruise that an outsider would notice.
- **Maybe bounce from the search-result page** if they're filtering
  by description, because the description says "equity solver in pure
  Python" and a HUNL-solver searcher would skip over that.

After the four 5-min fixes (description rewrite, PR #4 merge, topics,
homepage URL), the repo is **credible and runnable** for a developer
to try `pip install -e .` and reasonably expect things to work.

After the two follow-on USAGE.md fixes (PR #2 merge + the install-path
softening), the documentation surface is internally consistent.

There are no structural issues with how the repo presents. The
"NEEDS-MAJOR-WORK" verdict would only apply if (a) the build were
broken, (b) the architecture were a fiction, or (c) the project had no
license — none of those are the case here.

The user said: "we don't need to be flashy about the release / announce,
just a solid github repo that's clearly followable and usable" and
"i am more concerned not of some flashy words but that the code itself
will run and give expected results." Against that standard:

- **Followable:** Yes, after the README cross-refs and USAGE.md
  catch up to v1.7.0. The conceptual chain (README → CHANGELOG →
  USAGE.md → docs/aggregator_vs_true_nash_explainer.md → DEVELOPER.md)
  is sound; the v1.4.x-vintage USAGE.md is the weakest link today.
- **Usable:** Yes, via `pip install -e .` from source. The `.dmg` is
  honestly flagged as experimental.
- **Code runs and gives expected results:** The release notes
  explicitly cite 50/50 + 12/12 + 6/6 passing tests on v1.7.0. A
  developer cloning today and running `pytest` should see green;
  acceptance against Brown's binary is openly noted as failing at
  deep-cap spots (Known issues). That's an honest picture.

Final: **NEEDS-POLISH (4 high-impact 5-min fixes), then SHARE-READY.**
