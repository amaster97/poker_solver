# poker_solver v0.5.1 release notes (RELEASED)

**Release date:** 2026-05-22
**Codename:** "External Nash anchor"
**PR 7:** `83d7b9c` — integration merge `d135add`

Patch release. Adds the first external-Nash validation gate by wiring
Noam Brown's MIT-licensed C++ solver (`noambrown/poker_solver`) into a
river-spot diff harness against PR 6's Rust HUNL postflop tier. PR 6
shipped bit-exact Python ↔ Rust internal parity; this release closes
the validation chain by confirming both tiers solve to the **same Nash
equilibrium** as an independent oracle, not just to the same
implementation.

Internal test infrastructure only. No new public API, no new CLI flags,
no new wheel dependencies. The v0.5.0 public contract
(`--backend rust`, `poker_solver._rust.solve_hunl_postflop`) is
unchanged. Per `docs/pr6_prep/semver_sequencing.md`, "no public API
surface change" + "validation-only addition" maps to PATCH.

---

## What's new in v0.5.1

### 1. External Nash validation harness (PR 7)

First third-party Nash agreement gate in the project.

- **`poker_solver/parity/` package** — internal wrapper around Brown's
  compiled binary. Dataclasses (`RiverSpot`, `BrownStrategy`,
  `CanonicalAction`), JSON fixture loader with board/range overlap
  rejection, subprocess driver invoking Brown with explicit DCFR
  triple (α=1.5, β=0, γ=2) matching our Rust solver, history
  canonicalization in both directions (Brown's extra-beyond-call
  `r<delta>` ↔ our raise-to-total `r<to_total>`), and a strategy-matrix
  adapter reshaping our per-(hand, infoset) probabilities into Brown's
  `[hand × action]` matrix.
- **15-spot river fixture** at `tests/data/river_spots.json`,
  schema_version=1. 5 categories × 3 spots: dry rainbow, wet rainbow,
  monotone, paired, broadway-heavy. Each spot validated at load for
  board/range non-overlap, equal effective stacks, whole-BB pot.
- **`scripts/build_noambrown.sh`** — idempotent out-of-tree build
  (skips if binary newer than every `.cpp`/`.h`), soft-fails (exit 0)
  on missing `cmake` / `c++` so CI on toolchain-less hosts skips
  cleanly rather than aborting.
- **5-layer CI portability:** build soft-fail → harness `pytest.skip`
  on missing binary → out-of-tree per-host build (no `-march=native`
  stale-cache reuse) → opt-in `@pytest.mark.parity_noambrown` marker.
  Default `pytest` invocations deselect the diff entirely.

### 2. Loud `RuntimeError` on stale `_rust.so` (PR 6 hardening)

`tests/test_hunl_diff.py` previously silently skipped the entire
Python ↔ Rust diff suite when `poker_solver._rust` was stale (e.g.
after a clean Cargo rebuild without `maturin develop`), masking
Rust-tier regressions. Replaced with a loud `RuntimeError` pointing
at `maturin develop --release`. PR 6's internal-parity gate can no
longer silently degrade.

### 3. Tests

- **`tests/test_river_diff.py`** (~491 LOC) — Brown-dependent diff
  harness. 80% history-coverage assertion per spot, per-action
  tolerance `|our_prob - brown_prob| < 5e-3`, per-spot game value
  `|our_gv - brown_gv| < 1e-3 * spot.pot`. Skips cleanly when binary
  absent.
- **`tests/test_river_diff_self_sanity.py`** (~278 LOC) — runs
  WITHOUT Brown's binary. 10-case history canonicalization round-trip
  fixture, 2000-iter exploitability < 0.02 × pot, fixture
  board/range non-overlap, strategy-matrix shape,
  `iterations_override` respected, `find_brown_binary()` returns
  path-or-None.

---

## What it doesn't add

- **No new public API.** `poker_solver/parity/` is internal test
  infrastructure; nothing is re-exported from `poker_solver.__init__`.
- **No new CLI flags.** `solve` subcommand surface is unchanged from
  v0.5.0.
- **No new wheel dependencies.** Wrapper is pure Python + stdlib +
  numpy + existing `poker_solver` imports;
  `pyproject.toml [project.dependencies]` unchanged.
- **No abstraction changes.** PR 4 artifacts are still the input;
  PR 7 only validates the river-tier solve.

---

## Honest caveats

### 1. Requires Brown's binary built locally

`scripts/build_noambrown.sh` clones-and-builds out-of-tree under
`references/code/noambrown_poker_solver/cpp/build/`. The diff harness
calls `pytest.skip(...)` if the binary doesn't resolve, so a missing
build is non-fatal — but it means the external-Nash gate doesn't
actually run on hosts without `cmake` + a C++17 toolchain.
Instructions in README.

### 2. Apple Silicon arm64 only; x86_64 untested

Build script and harness were developed and verified on Apple M4 Pro
(macOS, arm64). The `-march=native` flag is per-host so the binary
won't cross-pollute build caches, but Linux x86_64 and Windows hosts
are not part of the verification chain for v0.5.1. PR 8+ will
broaden host coverage.

### 3. Tolerance: 5e-3 per-action, 1e-3 game value

The diff is not bit-exact (Brown's C++ uses different float reduction
order, different RNG path, different tree-build internals). The
gate is `|our_prob - brown_prob| < 5e-3` per action and
`|our_gv - brown_gv| < 1e-3 * spot.pot` per spot, with an 80%
history-coverage assertion guarding against accidental tree
truncation on either side. Tighter tolerances are out of scope —
the 5e-3 threshold is the Nash-agreement standard, not a bit-exact
one.

### 4. River only

Turn and flop diffs are out of scope per PR 7 spec §1. PR 6's
internal Python ↔ Rust parity covers the full HUNL postflop tree;
the external oracle gate only anchors the river tier for v0.5.1.

---

## Acknowledgments

- **Noam Brown** (`noambrown/poker_solver`, MIT) — external solver
  used as the Nash oracle. Invoked as a subprocess via its
  `--dump-strategy` JSON output; no C++ source copied, no derivative
  work produced. License header at
  `poker_solver/parity/noambrown_wrapper.py:1-N` per spec §8.
- **Reference-first verification discipline** — Brown's
  `cpp/src/river_game.cpp:63-66` (no-special-allin-token) and
  `:88-93` (extra-beyond-call raise convention) were read directly
  before writing the canonicalizer. The history-canonicalization
  layer is the load-bearing parity surface; nothing was guessed.

---

## License

MIT. Brown's repo is MIT (verified at
`references/code/noambrown_poker_solver/LICENSE`). No AGPL-licensed
code is copied into this repository.

For the full plan, decision log, and roadmap, see `PLAN.md`.
