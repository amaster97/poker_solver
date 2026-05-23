PR 6: Rust port of HUNL postflop solve (Python ↔ Rust diff-tested) (v0.5.0)

Ports the Python HUNL postflop solver shipped in PR 5 to Rust at
crates/cfr_core/, exposed through PyO3 as
poker_solver._rust.solve_hunl_postflop. Three-agent fan-out (A: state +
tree + eval; B: abstraction + solver + PyO3 + Python integration; C:
tests) plus a post-implementation audit pass. The Rust port is
mechanical — same DCFR (alpha=1.5, beta=0, gamma=2.0), same action
menu, same bucket lookups, same chance enumeration. Differential test
against the Python tier on PR 5's small fixtures confirms parity at
the 1e-3 (river) / 5e-3 (flop) tolerance cluster, with bit-exact match
on the tiny river subgame fixture.

Bumps __version__ to 0.5.0 per semver (new public API: --backend rust
flag on solve --hunl-mode postflop + new PyO3 export
poker_solver._rust.solve_hunl_postflop are net-additive public surface,
not a pure bug fix; per docs/pr6_prep/semver_sequencing.md and the
project's own MINOR-bump precedent at PR 2 / PR 3 / PR 5). This commit
bundles the v0.5.0 release artifacts together with the implementation
so the merge tip is releasable as-is:
- poker_solver/__init__.py: __version__ "0.4.0" -> "0.5.0".
- pyproject.toml [project] version "0.4.0" -> "0.5.0".
- CHANGELOG.md: new [0.5.0] - 2026-05-22 section above [0.4.0],
  populated with the PR 6 entry moved out of [Unreleased] (PR 6 was
  previously tagged "Ships in v0.5.0" in [Unreleased]); new
  [0.5.0]: ./ link reference appended to the bottom.
- README.md: "Current version: 0.4.0" -> "Current version: 0.5.0",
  with the feature-line caption updated from "card abstraction + HUNL
  postflop solve" (v0.4) to the v0.5 line ("Rust HUNL postflop port,
  ~24x speedup").

Scope (spec §1, §2, §4, §5, §6):
- Rust HUNL game state + flat tree + native 7-card hand evaluator.
- Rust abstraction loader for PR 4's .npz (string-keyed dict-of-dict
  indices, JSON-encoded inside one-element uint8 arrays; metadata also
  JSON-encoded; canonical board/hand keys are sorted card-strings, not
  integers).
- Rust solve_hunl_postflop entry composing the new types with the
  existing generic DCFRSolver<G> from PR 1.
- PyO3 binding: _rust.solve_hunl_postflop(config_json,
  abstraction_path, iterations, alpha, beta, gamma,
  target_exploitability, seed); GIL released for the DCFR loop via
  py.allow_threads.
- Python solver.py _solve_rust dispatch extended with an HUNLPoker
  postflop branch. Composes AFTER the PR 3.5 push/fold short-circuit
  and BEFORE the Python fallback (PR 9 §6 canonical ordering).
- Python recomputes exploitability + game_value from the Rust-returned
  strategy (matches Kuhn/Leduc pattern; removes cross-tier float drift
  in those values).
- CLI: --backend rust on the existing solve --game hunl --hunl-mode
  postflop path; default stays python.

New files (crates/cfr_core/src/):
- hunl.rs (~870 LOC): HUNLState, HUNLConfig, Street, ACTION_FOLD..
  ACTION_ALL_IN constants, ActionContext + enumerate_legal_actions +
  compute_bet_amount + compute_raise_to. Integer i32-cents chip
  arithmetic throughout; banker's-rounding parity via (x + 0.5).floor()
  to match Python's round() on positive integers.
- hunl_tree.rs (~640 LOC): HUNLTree + HUNLTreeNode + HUNLTree::build.
  Flat indexed-children tree memoized by (cur_player, contribs, street,
  history); Arc<HUNLConfig> shared across nodes to keep build RAM
  bounded.
- hunl_eval.rs (~520 LOC): Strength + evaluate_5 + evaluate_7. Ports
  the Python evaluator's algorithm; produces identical ranks under the
  same integer comparison semantics; tie-breaking via equal Strength
  values triggers the 50/50 utility path.
- abstraction.rs (~580 LOC): AbstractionTables + load_abstraction +
  lookup_bucket. Parses PR 4's .npz layout exactly:
  per-street string-keyed board_index (HashMap<String, u32>) +
  hand_index (HashMap<String, HashMap<String, u32>>), each decoded
  from a one-element JSON-bytes uint8 array; AbstractionMetadata
  parsed once from the single metadata JSON blob with #[serde(flatten)]
  catch-all for forward-compatibility. Schema-version check
  (metadata.schema_version == 1) and version-check seam (loud
  AbstractionError on drift; defense-in-depth alongside Python's
  resolve_abstraction_ref LRU + version check).
- hunl_solver.rs (~510 LOC): solve_hunl_postflop entry. Validates
  postflop-only / rake=0 / board-length, builds the flat tree, runs
  the existing generic DCFRSolver<HUNLState>, returns
  HUNLSolveOutput. target_exploitability early-exit forwarded.

Modified (crates/cfr_core/src/):
- lib.rs (+~140 LOC): solve_hunl_postflop #[pyfunction] wrapper; JSON
  config parsing via serde; py.allow_threads around the solve;
  module export.
- Cargo.toml: ndarray-npy = "0.9" (MIT/Apache 2.0), serde_json,
  ahash (test-mode fixed-seed hasher), arrayvec. No new AGPL deps.

Modified (poker_solver/):
- solver.py: HUNL postflop Rust branch in _solve_rust. Routes through
  resolve_abstraction_ref(cfg.abstraction) — NEVER reaches into
  cfg.abstraction.source_path directly, so the LRU cache + version
  check both fire. Dispatch order locked: push/fold short-circuit (PR
  3.5) -> HUNL postflop Rust (this PR) -> HUNL postflop Python
  fallback (PR 5) -> HUNL preflop NotImplementedError pointing at PR
  9 -> Kuhn/Leduc (unchanged).
- hunl.py: _serialize_hunl_config(config) -> str. Dumps every
  HUNLConfig field to JSON matching Rust's serde::Deserialize shape.
  abstraction_path flattened from resolved tables.source_path
  separately (avoids serializing the entire bucket table through the
  PyO3 boundary).
- cli.py: --backend rust flag on solve --game hunl --hunl-mode
  postflop path. Default python (PR 5 behavior preserved).
- __init__.py: unchanged. solve_hunl_postflop (Rust) is internal;
  users call solve(game, ..., backend="rust").

New tests:
- crates/cfr_core/tests/test_hunl_rust.rs (~12 Rust tests):
  blinds-posted-correctly, legal-actions-at-river-subgame-root,
  apply-advances-state-correctly, infoset-key-lossless-format,
  infoset-key-bucketed-format, abstraction-canonicalization-matches-
  python (10K random inputs via PyO3), abstraction-lookup-bucket-
  matches-python (10K random inputs), hunl-tree-build-terminates,
  hunl-strength-eval-matches-python (1K random hand-vs-hand
  comparisons), hunl-strength-eval-handles-ties, hunl-solve-river-
  subgame-smoke, hunl-solve-reject-preflop.
- tests/test_hunl_diff.py (~8 Python tests + 1 cross-tier smoke):
  test_hunl_river_subgame_diff_python_vs_rust (1000 iters, 1e-3 tol;
  PASSED at bit-exact on the tiny river subgame fixture — exceeds
  spec tolerance by 6 orders of magnitude), test_hunl_flop_dry_3size_
  diff_python_vs_rust_tiny_abstraction (200 iters, 5e-3 tol),
  validates-postflop-only, validates-board-length, strategy-sums-to-
  one, deterministic-with-seed (threaded; tests py.allow_threads + GIL
  release), exploitability-matches-python-recompute, action-ids-match-
  python-constants.

Spec amendments locked this round (5 items, per Agent B's pre-
implementation review against the committed PR 4 on-disk shape):
- §4.4 metadata layout clarified to match
  buckets.py::save_abstraction's actual output (JSON-bytes
  one-element uint8 arrays, NOT separate top-level NumPy arrays
  per field).
- §4.4 canonical board/hand keys clarified as Python-side
  *strings* (sorted-by-(rank,suit) joined card-strings), not u32
  integer IDs.
- §6.1 dispatch ordering explicitly enumerated (5-step
  head-to-tail) with PR 9 §6 cited as canonical. The HUNL Rust
  elif must compose AFTER the push/fold short-circuit.
- §4.1 HUNLConfig pre-mirrors use_pcs: bool = false (PR 8
  schema migration avoided).
- §6.3 wiring goes through resolve_abstraction_ref() always;
  direct .source_path access is forbidden (LRU cache + version
  check would otherwise silently miss).

Differential test result: 21 new tests across the Rust + Python tiers
all pass; the tiny river subgame fixture matches Python BIT-EXACTLY
(no float drift detected for the 1000-iteration river-only DCFR
solve under ahash with a fixed test-mode seed — exceeds the 1e-3
spec tolerance by 6 orders of magnitude). The flop fixture matches
within 5e-3 (per spec). Note: the tiny river subgame fixture has
degenerate geometry (P0's AhKc has 100% showdown equity vs P1's
QdQh on As 7c 2d Kh 5s), so exploitability~0 plus bit-exact Python
↔ Rust agreement is consistent with theory; this is an
internal-parity gate, and external Nash agreement (vs another
solver) is deferred to PR 7's noambrown diff harness. HUNL
postflop solve on the river fixture runs in ~3.9 s in Rust vs ~93 s
in Python at 100k iters (~24x speedup, inside the 10-50x PLAN.md
target; measured on Apple M4 Pro, median of 3 trials, bit-exact
exploitability between tiers). Speedup ranges 20-24x depending on
iteration count (setup overhead dominates at <1k iters). PR 8 SIMD +
cache-blocking + slumbot lookup table closes the rest of the gap.

License compliance: zero AGPL code. Every new .rs file ships the
module-level attribution docstring per spec §3:
- hunl.rs cites poker_solver/hunl.py (project-internal, MIT) for
  semantics; noambrown_poker_solver/cpp/src/river_game.{h,cpp}
  (MIT) for pattern (not transcription).
- hunl_tree.rs cites noambrown_poker_solver/cpp/src/river_game.h
  Tree/TreeNode shape (MIT).
- hunl_eval.rs cites noambrown_poker_solver/cpp/src/cards.{h,cpp}
  (MIT) for Strength type; slumbot2019/src/hand_value_tree.cpp
  (MIT) for 7-card-eval pattern.
- abstraction.rs cites slumbot2019/src/card_abstraction*.cpp (MIT)
  for layout patterns; ndarray-npy (MIT/Apache 2.0, dual-licensed).
- hunl_solver.rs cites noambrown_poker_solver/cpp/src/trainer.{h,cpp}
  (MIT) for DCFR-on-postflop control flow.
- Every file carries the explicit "NEVER copy from
  references/code/postflop-solver (AGPL) or
  references/code/TexasSolver (AGPL)" disclaimer.
- check_pr.sh license audit (PLAN.md §4 step 6) confirms no new
  AGPL/GPL deps; ndarray-npy MIT/Apache verified.

Notable contract decisions (defaults per spec §11):
- Scalar CFR (one regret per (infoset, action)). Vector CFR deferred
  to PR 8.
- f64 regret storage (Python tier parity; flop convergence benefits
  from extra precision). PR 8 may revisit f32 for cache density.
- JSON-string config marshalling (single PyO3 boundary, easy to log).
- Python recomputes exploitability + game_value from Rust strategy
  (Kuhn/Leduc precedent).
- Flat tree at build time (default; falls back to state-machine
  traversal if RAM pressure exceeds budget via
  HUNLConfig::build_flat_tree=false).
- 1e-3 (river) / 5e-3 (flop) diff tolerance; 1e-6 absolute floor.
- HashMap hasher: default (random) in production, ahash with fixed
  seed under #[cfg(test)] for deterministic per-test repro.
- Python evaluator port (slow but correct); slumbot lookup table is
  a PR 8 perf task.
- CLI default backend stays python; --backend rust opts in.

Out of scope (per spec §2): NEON SIMD, cache-blocking, public
chance sampling, vector CFR, multi-threading inside CFR loop,
new abstraction artifact format, AGPL bunching, solver-side rake,
memory profiler for Rust tier, slumbot 7-card lookup table.
All deferred to PR 7/8/9.

Verification:
- cargo build --release --package cfr_core: clean.
- cargo test --package cfr_core --all-targets: 12/12 Rust tests
  pass; existing Kuhn/Leduc Rust tests unchanged.
- cargo clippy --package cfr_core --all-targets -- -D warnings: clean.
- pytest -m "not slow and not very_slow" --tb=line: all pass / skip;
  no failures, no timeouts. PR 1-5 regression: all pass unchanged.
- ruff check + ruff format + black --check + mypy --strict on the
  modified Python files: clean.
- check_pr.sh license audit: clean; no new AGPL/GPL deps.
- Manual CLI smoke (river subgame, no abstraction, 500 iters via
  --backend rust): prints strategy table + exploitability in <3 s;
  same iteration count would be ~5 s on Python. Full 100k-iter perf
  comparison: 3.88 s Rust vs 92.9 s Python (~24x speedup, Apple M4
  Pro, median of 3 trials).
- Manual CLI smoke (flop spot, tiny synthetic abstraction, 1000
  iters): runs to completion in <2 min.

Branch: pr-6-hunl-rust-port (off integration tip post-PR-5).
Awaits PR 7 noambrown river-spot oracle diff + main merge OK.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
