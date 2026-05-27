# README + Quickstart Audit — Post v1.8.0 Ship (2026-05-27)

**Scope:** end-to-end verification of every install, import, and "run a
basic solve" path a new user can hit from the public README + USAGE.md
on v1.8.0 production code.

**Methodology:** every CLI snippet, Python import, and example file was
executed on the active `.venv` (`/Users/ashen/Desktop/poker_solver/.venv/bin/python`).
No snippet was inspected without being run. Time-boxed: hangs >60s
flagged as HIGH.

**Snippets executed:** 14 verified out of 17 total.
- Skipped: 2 long-running flop/turn examples documented as multi-minute
  (README postflop + USAGE §5.2 turn-aggregator at full iters).
- Failed: 4 (see CRITICAL / HIGH findings below).

---

## Findings

### CRITICAL (blocks new-user onboarding)

**C1. README + USAGE node-locking snippets hang indefinitely (>18 min CPU-100%).**

- **Where:** README.md lines 148-155 ("Node locking" Python API example);
  USAGE.md §5.3 lines 414-428 (`locked_strategies` example).
- **What:** Both snippets build a `HUNLConfig` *without*
  `initial_hole_cards=`, then call `solve_hunl_postflop(cfg, iterations=500,
  locked_strategies=...)`. Because `initial_hole_cards` defaults to `()`,
  the engine enumerates the full ~1.3M-pair lossless chance tree at root,
  then does the post-solve Python-side exploitability walk — which is
  exactly the path USAGE §5.1 / §7b warn is "NOT practical for interactive
  analysis."
- **Empirical:** test process pinned at 100% CPU for 18+ minutes with zero
  output. Adding `initial_hole_cards=((Ah, Kc), (Qd, Qh))` makes the
  identical snippet complete in <1s with 207 infosets.
- **Severity:** A new user copy-pasting either snippet sees a hang and
  concludes the tool is broken. This is the single highest-impact drift
  vs reality.
- **Fix:** add `initial_hole_cards=((Card.from_str("Ah"), Card.from_str("Kc")),
  (Card.from_str("Qd"), Card.from_str("Qh")))` to both snippets, with a
  one-liner comment explaining the `()` (full range) caveat.

**C2. README quick start `--hunl-mode postflop --backend rust` errors immediately.**

- **Where:** README.md lines 108-114.
- **Output of running as-documented:** `error: --hunl-mode postflop
  --backend rust currently has no way to specify fixed hole cards, which
  the Rust scalar solver requires (without them, the root becomes a chance
  node and the solve returns an empty strategy). For range-vs-range Nash
  on a postflop board, use the Python API poker_solver.solve_range_vs_range_nash(...)
  instead. Use --backend python for the reference postflop path.`
- **Severity:** Same "tool looks broken" surface — except this one is a
  hard-fail with an actually-useful error message. Still drift.
- **Fix:** either change `--backend rust` → `--backend python` in the
  example, or add a note "see USAGE §5.6 for the Rust path."

---

### HIGH (silent surprise; quick to fix)

**H1. Status block is stale — "v1.7.0 latest tagged release; v1.8.0 tag pending."**

- **Where:** README.md lines 14-22.
- **Reality:** v1.8.0 was tagged at 2026-05-27T09:18Z (9 hours before
  audit). `poker_solver.__version__ == "1.8.0"`.
- **Fix:** bump "Latest tagged release" to v1.8.0; remove "Next release:
  v1.8.0 ... tag pending" sentence.

**H2. README claims "no dedicated pushfold CLI subcommand" — but it shipped in v1.7.0.**

- **Where:** README.md line 116 ("Short-stack push/fold is invoked through
  the library (no dedicated CLI subcommand — see Known issues)").
- **Reality:** `poker-solver pushfold --stack 10 --position sb_jam --hand AKs`
  works (returns `AKs sb_jam 10BB: 1.000000`); documented in USAGE §7a.
- **Fix:** point users to the `pushfold` subcommand and keep the Python
  API example as the library-mode complement.

**H3. CHANGELOG header says "1.8.0 - Unreleased".**

- **Where:** CHANGELOG.md line 16.
- **Reality:** tagged + GitHub Release published.
- **Fix:** substitute release date in the header.

**H4. USAGE.md title says "v1.7.x"; document baseline note in lines 9-12
references v1.7.0 only.**

- **Where:** USAGE.md lines 1-12.
- **Reality:** v1.8.0 is current; no v1.8-specific user-facing API
  changes, but the version label drifts.
- **Fix:** rev title + baseline note to v1.8.0.

**H5. `.dmg` lifecycle: README warns "DO NOT use until v1.8.0" — but
v1.8.0 release has 0 assets (empty `gh release view v1.8.0 --json
assets`).**

- **Where:** README.md lines 28-44, 240-253; USAGE.md lines 40-59.
- **Reality:** local `dist/Poker-Solver-1.8.0-arm64.dmg` exists (50 MB,
  built 2026-05-27 05:48) but has NOT been uploaded to the GitHub Release.
- **Severity:** new user reads "v1.8.0 fixes the .dmg" → expects to find
  it on the v1.8.0 release page → finds nothing. Dead end.
- **Action:** non-doc — separate work (DMG upload). Listed here for user
  visibility; not auto-fixed.

**H6. CLI has no `--version` flag.**

- **Where:** convention; not currently documented.
- **Reality:** `poker-solver --version` exits 2 with usage error. To get
  the version a user must do `python -c "import poker_solver;
  print(poker_solver.__version__)"`.
- **Severity:** debugging friction; ten-second add to argparse.
- **Action:** code change (small CLI addition); not in this docs PR. File
  separately or include in next patch ship.

---

### MEDIUM (suboptimal but works)

**M1. USAGE.md §1 still says "v1.0.0 ... 2026-05-22 ... is the first
end-user-shippable artifact."**

- **Where:** USAGE.md lines 33-35.
- **Status:** historical claim, true at the time. After 7 minor versions
  this paragraph is stale framing; v1.8.0 is the current shippable
  artifact.

**M2. USAGE.md §5.6 "Worked examples" lines 522-554 — runs Nash with
`iterations=500` on hero × villain of 5×4 combos. Empirically takes
~5+ minutes on Rust (extrapolation from §7b: river is sub-second per
combo, 20 combos × 500 iters → minutes).**

- **Risk:** another snippet-as-written that may exceed user patience.
- **Suggested:** drop to `iterations=100` or hero/villain of 2×2 for the
  worked example.

**M3. USAGE.md §6 library mode CLI: shows `poker-solver library export
<spot_id> ./my_spot.json` but `poker-solver library list --table` on a
fresh DB returns 0 rows — no example of *populating* the library is
given before the export.**

- **Fix:** add `poker-solver batch-solve --input examples/tiny_csv.csv`
  before the `list --table` line.

---

### LOW (cosmetic)

**L1. README §"References" line 314: "live under `references/` (gitignored;
not redistributed)" — verified accurate.** No fix.

**L2. README §"Known issues" line 281 cross-references "USAGE §7a" without
linking to USAGE.md anchor.** Minor; markdown anchors aren't standard
across renderers.

---

## Verification table (snippets actually run)

| # | Source | Snippet | Outcome |
|---|---|---|---|
| 1 | README §"Quick start" | `poker-solver equity AhKh QdQc --board 2h7h9d` | OK (60 ms, exact) |
| 2 | README §"Quick start" | `poker-solver equity "AA,KK,AKs" QdQc` | OK (250k iter MC) |
| 3 | README §"Quick start" | `poker-solver equity ... -n 1000000 --seed 0` | OK (deterministic) |
| 4 | README §"Quick start" | `poker-solver solve --game kuhn --iterations 50000 --backend python` | OK |
| 5 | README §"Quick start" | `poker-solver solve --game leduc --iterations 5000 --backend rust` | OK |
| 6 | README §"Quick start" | `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500` | OK |
| 7 | README §"Quick start" | tiny_subgame --backend rust --iterations 1000 | OK |
| 8 | README §"Quick start" | `--hunl-mode postflop ... --backend rust` | **FAIL (C2)** |
| 9 | README §"Quick start" | `get_pushfold_strategy(...)` + `get_full_range(...)` | OK |
| 10 | README §"Python API" | aggregator `solve_range_vs_range(cfg, hero, villain, iterations=200)` | OK |
| 11 | README §"Python API" | node-locking via `solve_hunl_postflop(cfg, iterations=500, locked_strategies=...)` | **FAIL (C1) — hangs** |
| 12 | README §"Python API" | `from poker_solver._rust import solve_range_vs_range_rust` | OK |
| 13 | USAGE §3a | pushfold one-liners | OK |
| 14 | USAGE §3b | tiny_subgame both backends | OK (covered by 6 + 7) |
| 15 | USAGE §5.3 | node-locking | **FAIL (C1) — hangs** |
| 16 | USAGE §5.4 | asymmetric contributions (fixed cards) | OK |
| 17 | USAGE §5.6 | `solve_range_vs_range_nash` import + small call | importable; call slow (skipped at full size) |
| 18 | USAGE §6 | Library mode put + get | OK |
| 19 | USAGE §7a | pushfold, river, parity (parity exits 2 with hint as documented) | OK |
| 20 | examples/range_vs_range_river.py | `python examples/range_vs_range_river.py` | OK (8 ms, full output) |

Link verification: all 15 doc cross-refs in README + USAGE resolve. No
links into the archived `docs/_archive_2026-05-26/` directory in any
user-facing doc.

---

## Decision

**Auto-fix in this PR (docs-only, no semantic risk):**
- C1 — node-locking snippets (README + USAGE) get `initial_hole_cards`
  added.
- C2 — README quickstart postflop CLI: switch `--backend rust` → `--backend python`.
- H1 — Status block bumped to v1.8.0.
- H2 — pushfold subcommand surfaced in README §"Quick start".
- H3 — CHANGELOG header gets release date.
- H4 — USAGE.md title + baseline bumped to v1.8.0.

**Deferred (not in this PR):**
- H5 — `.dmg` upload to GH Release (release-ops, not docs).
- H6 — `--version` flag (small code change, separate ship).
- M1/M2/M3 — listed for next docs pass.

PR title: `fix(docs): README/quickstart drift after v1.8.0 ship`
