PR 7: River-spot diff vs Brown's MIT solver (external Nash validation) (v0.5.1)

Adds a differential test that compares our Rust HUNL postflop solver
(landed in PR 6 / v0.5.0) against Noam Brown's MIT-licensed
`noambrown/poker_solver` C++ reference solver on a fixed set of river
spots, producing the first external-Nash agreement gate in the
project. PR 6's diff test was an internal Python ↔ Rust parity check
(bit-exact on the tiny river fixture); this PR closes the loop with
an independent oracle, validating that both tiers solve to the same
Nash equilibrium rather than the same implementation. Three-agent
fan-out (A: parity wrapper + fixture + build script; B: river diff
harness + marker + pyproject; C: self-sanity smoke + Brown-free
canonicalization round-trip tests) plus a post-implementation audit
pass against `docs/pr7_prep/audit_prompt_final.md`. Brown's solver is
invoked as a subprocess via its `--dump-strategy` JSON output; no C++
source is copied, no derivative work is produced.

Bumps __version__ to 0.5.1 per semver (PATCH bump). The parity
package (`poker_solver/parity/`) is internal test infrastructure
only — no new CLI surface, no new public API exports, no new runtime
dependencies on the install path. The PR 6 v0.5.0 public contract
(--backend rust + poker_solver._rust.solve_hunl_postflop) is
unchanged. Per docs/pr6_prep/semver_sequencing.md, "no public API
surface change" + "validation-only addition" maps to PATCH, not
MINOR. This commit bundles the v0.5.1 release artifacts with the
implementation so the merge tip is releasable as-is:
- poker_solver/__init__.py: __version__ "0.5.0" -> "0.5.1".
- pyproject.toml [project] version "0.5.0" -> "0.5.1".
- CHANGELOG.md: new [0.5.1] - 2026-05-22 section above [0.5.0],
  noting external-Nash validation via Brown's solver; [Unreleased]
  empty; [0.5.1]: ./ link reference appended.
- README.md: "Current version: 0.5.0" -> "Current version: 0.5.1",
  caption updated with one line on river-diff oracle validation.

Scope (spec §1, §4, §5, §6, §8, §10):
- Parity wrapper module + dataclasses (RiverSpot, BrownStrategy,
  CanonicalAction) and JSON fixture loader with overlap rejection.
- Build script `scripts/build_noambrown.sh` — idempotent
  (`find ... -newer` skip if binary newer than every .cpp/.h),
  out-of-tree under `references/code/noambrown_poker_solver/cpp/build/`,
  soft-fails (exit 0, not 1) when `cmake` or `c++` is unavailable so
  CI on missing-CLT macOS hosts skips cleanly rather than aborting.
- River-spot JSON fixture: 15 spots, schema_version=1, 5 categories ×
  3 spots (dry rainbow, wet rainbow, monotone, paired, broadway-heavy)
  per spec §4 + §12 open decision 2. Each spot validated at load
  for board/range non-overlap, equal effective stacks, whole-BB pot.
- Subprocess driver invoking Brown with EXACTLY:
  `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2 --seed 7
  --iters 2000 --dump-strategy <tmpfile>` — same DCFR triple as our
  Rust solver, identical iteration budget, explicit seed for paranoia
  (Brown default is 7 per cpp/src/main.cpp:36 but spec §11 #1
  mandates explicit pass). Parses the JSON dump file, NOT stdout
  (stdout carries logging only).
- History canonicalization (spec §5 step 5, the load-bearing parity
  surface): Brown stores raises as extra-beyond-call
  (`cpp/src/river_game.cpp:88-93`), we store raises as raise-to-total
  (`poker_solver/hunl.py:391-401`). `canonicalize_brown_history` parses
  Brown's `r<delta>` tokens; `canonicalize_our_history` converts our
  `r<to_total>` -> canonical `r<delta>` using per-player accumulated
  contributions, with reset at each street boundary. All-in `A` ↔
  `b<remaining>` / `r<remaining-to_call>` mapping handles Brown's
  no-special-allin-token convention (`cpp/src/river_game.cpp:63-66`).
- Strategy-matrix adapter: `our_strategy_to_brown_matrix(...)`
  aggregates our per-(hand, infoset) probabilities into Brown's
  `[hand × action]` matrix shape, keyed by canonicalized history.
- 5-layer skipif strategy for CI portability (spec §6 + §9 #3):
  (1) build script soft-fails on missing cmake/c++ -> exit 0;
  (2) `tests/test_river_diff.py` calls `pytest.skip(...)` if the
  Brown binary path doesn't resolve;
  (3) Xcode CLT missing on macOS -> caught by layer (1) soft-fail;
  (4) `-march=native` host mismatch -> out-of-tree per-host build
  prevents stale-cache reuse;
  (5) `@pytest.mark.parity_noambrown` opt-in marker (registered in
  pyproject.toml under [tool.pytest.ini_options].markers) lets
  default `pytest` invocations deselect the diff entirely.

Tolerance (spec §1 + §5 step 6): per-action
`|our_prob - brown_prob| < 5e-3`, per-spot game value
`|our_gv - brown_gv| < 1e-3 * spot.pot`. Tolerance literal verified
identical across fixture, harness, AND self-sanity (no silent
relaxation). 80% history-coverage assertion per spot guards against
accidental tree-truncation on either side.

xdist subprocess safety (spec §9 #8): every subprocess invocation
uses `tempfile.NamedTemporaryFile(suffix=".json", delete=False)` so
two pytest-xdist workers running the same spot in parallel cannot
clobber each other's dump file; `os.unlink` runs in a `finally`
block to clean up even on Brown-failure exception paths. Brown
binary path resolved via `Path(__file__).resolve().parents[2] /
"references" / ...` (repo-anchored, not cwd-anchored — spec §9 #9).

New files:
- poker_solver/parity/__init__.py (~21 LOC): package surface.
- poker_solver/parity/noambrown_wrapper.py (~1,217 LOC / 47 KB):
  dataclasses, JSON loader, binary resolver, subgame JSON writer,
  subprocess driver, history canonicalizer (both directions),
  strategy-matrix reshaper.
- scripts/build_noambrown.sh (~69 LOC, +x): idempotent build with
  soft-fail on missing toolchain.
- tests/data/river_spots.json (~25.8 KB / 15 spots): river fixture.
- tests/test_river_diff.py (~491 LOC): Brown-dependent diff harness
  with skip-on-missing-binary guard + 80% coverage assertion +
  per-action / per-game-value tolerance checks.
- tests/test_river_diff_self_sanity.py (~278 LOC): runs WITHOUT
  Brown's binary; 10-case history canonicalization round-trip
  fixture, 2000-iter exploitability < 0.02 * pot, fixture
  board/range non-overlap, strategy-matrix shape, iterations_override
  respected, find_brown_binary() returns path-or-None.

Modified:
- pyproject.toml: `parity_noambrown` marker registered under
  [tool.pytest.ini_options].markers with deselect hint.
- tests/test_hunl_diff.py (+21 / -6): hardened PR 6 sub-improvement.
  The previous import-fallback path silently skipped the entire
  Python ↔ Rust diff suite when `poker_solver._rust` was stale (e.g.
  after a clean Cargo rebuild without `maturin develop`), masking
  Rust-tier regressions. Replaced with a loud `RuntimeError`
  pointing at `maturin develop --release` so PR 6's diff gate
  cannot silently degrade.

License compliance: Brown's repo is MIT
(verified at references/code/noambrown_poker_solver/LICENSE).
poker_solver/parity/noambrown_wrapper.py carries the spec §8
attribution docstring header naming Brown's repo + license + the
public CLI surface (--algo / --dcfr-alpha / --dcfr-beta /
--dcfr-gamma / --seed / --iters / --dump-strategy) + the JSON
output schema we depend on. Wrapper is original Python — no C++
code copied from Brown. We invoke the compiled binary (not a
derivative work under MIT) and parse its JSON output (public
interface, not internals). No NOTICE file update needed (MIT
doesn't mandate one). No new third-party dependencies: wrapper is
pure Python + stdlib + numpy + existing poker_solver imports;
pyproject.toml [project.dependencies] unchanged.

Out of scope (spec §3): turn/flop diffs (river only, per §1),
abstraction validation (validated externally in PR 4 + PR 8),
solver-internal Python ↔ Rust diff (covered in PR 6),
preflop diffs (deferred to PR 9 + later), perf benchmarks
against Brown (the diff is correctness-only, not speed —
Brown's optimized C++ on river is the spec correctness anchor,
not the perf anchor).

Verification:
- cargo build --release --package cfr_core: clean (PR 6 carry-over).
- scripts/build_noambrown.sh: idempotent on second run; soft-fails
  cleanly on a host with cmake uninstalled.
- pytest tests/test_river_diff.py tests/test_river_diff_self_sanity.py
  -v: smoke (10 Agent C tests) + diff harness pass; diff harness
  skips cleanly when binary absent.
- pytest -m "not slow and not very_slow" --tb=line: full suite
  green (PR 1-6 regression unchanged); test_hunl_diff.py still
  passes under the new RuntimeError gate (stale-.so condition not
  triggered in the CI image).
- ruff check + black --check on PR 7 files: clean.
- mypy --strict on poker_solver/parity/: clean.
- License attribution: spec §8 header present at
  poker_solver/parity/noambrown_wrapper.py:1-N.

Branch: pr-7-noambrown-diff (off integration tip post-PR-6).
6 sibling worktrees synced post-merge per
`feedback_no_concurrent_branch_ops.md` discipline. Audit prompt:
`/Users/ashen/Desktop/poker_solver/docs/pr7_prep/audit_prompt_final.md`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
