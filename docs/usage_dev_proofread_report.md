# USAGE.md + DEVELOPER.md pre-publish proofread report

Date: 2026-05-23. Scope: editorial + accuracy second pass against the
codebase. Edits applied surgically via the Edit tool; suggestions
flagged below.

## USAGE.md (1138 words)

### Issues fixed inline

- **SHOULD-FIX (factual) — line 107.** `tests/test_noambrown_diff.py`
  does not exist; the actual file is `tests/test_river_diff.py`. Fixed.

### Issues flagged (no edit)

- **NICE-TO-FIX — line 24.** `noambrown/poker_solver (MIT)` — the
  upstream is in fact at `github.com/noambrown/poker_solver`; consider
  a direct GitHub link in v1.1 for users skimming for external
  validation.
- **NICE-TO-FIX — line 88.** The CLI bash example uses a `\` line
  continuation inside `python -c "..."` with a literal semicolon. It
  works but is awkward for copy/paste on some shells. Optional: split
  into two `-c` blocks or move to a `.py` file in `examples/` and
  reference it. Voice-preserving so left as-is.
- **NICE-TO-FIX — line 132.** Says MC is "0.1% SE per hand"; the
  in-code help string uses the same `~0.1%% SE` phrasing
  (`cli.py:617`). Aligned, not a defect.

### NO-ISSUES

- All Python imports (`get_pushfold_strategy`, `get_full_range`,
  `Library`, `default_tiny_subgame`, `solve`, `HUNLPoker`,
  `SpotDescription`) resolve via `poker_solver/__init__.py`.
- `--hunl-mode tiny_subgame`, `--backend rust`, `--iterations`, CLI
  output strings (`Game value`, `Exploitability (final)`, `Average
  strategy`, `Iterations` header) all match `poker_solver/cli.py`.
- Default fixture board `As7c2dKh5s` with `AhKc vs QdQh` matches
  `default_tiny_subgame()` in `poker_solver/hunl.py:184`.
- Backend string `"pushfold_chart"` matches `pushfold.py:232`.
- Library defaults (`~/.poker_solver/library.db`,
  `$POKER_SOLVER_LIBRARY_PATH`, spot ids = sha256) match
  `library.py:53,69,468+`.
- 0 PII / agent IDs / session UUIDs / hardware identifiers.
- Casing of HUNL / NiceGUI / PioSolver / DCFR consistent throughout.

## DEVELOPER.md (1685 words)

### Issues fixed inline

- **SHOULD-FIX (factual) — line 79.** `Click-based CLI` was wrong;
  `poker_solver/cli.py` uses `argparse`. Fixed to `argparse-based CLI`.
- **SHOULD-FIX (factual) — line 182.** Check battery listed `ruff
  format --check` but `scripts/check_pr.sh` calls `black --check`
  (also matches `CONTRIBUTING.md:95`). Fixed.
- **SHOULD-FIX (factual) — line 233-234.** Same `ruff format` -> `black`
  drift in the conventions section. Fixed.

### Issues flagged (no edit)

- **NICE-TO-FIX — line 33.** "asserts strategy agreement to ~1e-4 per
  action probability" is order-of-magnitude correct for Kuhn/Leduc/DCFR
  diff tests (`STRATEGY_ATOL = 1e-4`) but HUNL diff uses 1e-3 (river)
  and 5e-3 (flop). Could be tightened to "1e-4 on Kuhn/Leduc, 1e-3 on
  HUNL river" — but the loose phrasing is intentional and defensible.
- **NICE-TO-FIX — line 99.** "Python 3.9+ (developed on 3.13)" — same
  copy as `CONTRIBUTING.md:29`, accurate.
- **NICE-TO-FIX — line 117.** `cargo test --all --manifest-path
  crates/cfr_core/Cargo.toml` works but is redundant when running from
  the repo root (workspace `Cargo.toml` exists). `check_pr.sh` uses
  the shorter `cargo test --all`. Either form is fine; left for voice
  consistency with `CONTRIBUTING.md`.
- **NICE-TO-FIX — line 171.** "Leduc ... ~288 infosets" — the test
  suite asserts exactly 288 (`test_leduc_dcfr.py:25`). The `~` could
  be dropped, but it scans naturally as written.

### NO-ISSUES

- All file paths under `poker_solver/`, `crates/cfr_core/src/`,
  `tests/`, `scripts/`, `docs/`, `references/` exist as referenced.
- DCFR equation block matches `poker_solver/dcfr.py:13-15` verbatim.
- DCFR defaults `(1.5, 0.0, 2.0)` match `dcfr.py:55-57`.
- Kuhn Nash value `-1/18` matches `games.py:134`.
- License table matches `references/README.md:22-32`.
- `Game` protocol methods (`num_players`, `initial_state`, etc.) match
  `games.py:31+`.
- 14-action abstraction with raise caps matches
  `action_abstraction.py:7,63-64`.
- Bucket counts `(256, 128, 64)` match
  `abstraction/precompute.py:386`.
- 0 PII / agent IDs / session UUIDs / hardware identifiers.
- Casing of HUNL / DCFR / NiceGUI consistent throughout.

## Tally

- Edits applied: **4** (USAGE.md: 1; DEVELOPER.md: 3).
- Issues flagged (no edit): **8** (USAGE.md: 3; DEVELOPER.md: 4, plus
  meta).
- Blockers: **0**.

## Verdict

**READY-TO-PUBLISH**
