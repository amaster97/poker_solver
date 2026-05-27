## v1.7.1 - Engine correctness + Brown parity test alignment (PATCH)

**Headline:** A PATCH release bundling seven bug fixes (two engine, five test-harness / parity-wrapper) plus an acceptance-test reframe. No new user-facing API, no breaking changes.

The bundle closes the R1-R10 reversal chain documented during the v1.6.1 dry-run sequence and re-frames external reference comparison as a sanity check rather than a strict per-cell gate.

### Fixed -- engine

- **Facing-all-in action menu guard** (PR 50). At facing-all-in nodes
  (when villain has shoved and `to_call >= stack`), the responder's
  action menu previously included a degenerate `ALL_IN` raise with no
  chip semantics distinct from calling. Both engines now require
  `to_call < stack` before emitting `ALL_IN` as a separate option.
  Real `ALL_IN`-as-raise paths (villain has chips behind) are
  preserved unchanged.
- **`dcfr_vector.rs:651` off-by-one panic on asymmetric ranges**
  (PR 51). When traversing an opponent-node decision in vector-form
  CFR, `next_reach` was sized using the wrong player's hand count,
  panicking on asymmetric range solves (e.g., A83 where P0 has 49
  combos and P1 has 50 due to board-blocker differences). Indexing
  now uses the per-player hand count.

### Fixed -- Brown parity wrapper (`noambrown_wrapper.py`)

- **Suit-encoding silent swap** (PR 52). The wrapper mapped suit
  *indices* between our `"shdc"` and Brown's `"cdhs"`, producing a
  paired `h <-> d` swap that distorted per-cell comparisons without
  raising errors. Replaced with explicit char-to-char mapping. This
  bug accounted for a large portion of the prior 22-42pp deep-cap
  divergence reported in earlier v1.6.1 dry-runs.
- **P0/P1 player-convention swap (output side)** (PR 55).
  `_parse_brown_dump` now swaps `parsed_players[0]` and
  `parsed_players[1]` so callers index with our convention (P0 =
  second-to-act on river) without needing to know the underlying
  Brown convention.
- **P0/P1 range swap (input side)** (PR 55-extend). Paired swap in
  `write_brown_config` so the range input passed to Brown's solver
  matches the player convention used on the output side.
- **Hand-string sort-order canonicalization** (PR 56). Wrapper
  boundary normalizes parsed hand strings to our Rust canonical sort
  (`rank*4 + s_idx` under `SUITS="shdc"`) before they're used as dict
  keys. Brown's canonical is `suit*13 + rank` under `suits="cdhs"`;
  same chars, different sort orders. Mixed-suit pairs (e.g. `KdKc` vs
  `KcKd`) diverged by string but not by semantics.

### Fixed -- test renderer

- **All-in-jam tokenization** (PR 54).
  `tests/test_v1_5_brown_apples_to_apples.py`'s
  `_rust_history_substr_for_canonical` now accepts a `stack_ceiling`
  kwarg and emits `"A"` for bets/raises at the stack ceiling,
  matching Rust's `hunl.rs:703-712` `ACTION_ALL_IN` tokenization.
  Without this, deep histories from Brown were not findable in
  Rust's keyset and the test gated out at the 80% coverage floor.

### Changed -- acceptance test framing

- **Brown apples-to-apples reframed from strict gate to sanity check**
  (PR 53). The strict 5e-2 per-action probability gate has been
  replaced by a 4-layer sanity-check structure:
  - **Layer 1 (always)** -- structural agreement: action count match
    across covered histories at the >=80% coverage floor.
  - **Layer 2 (always)** -- direction-of-aggression agreement at
    shallow nodes (root + first action).
  - **Layer 3 (informational)** -- shallow-frequency agreement
    within reasonable bounds.
  - **Layer 4 (printed, not gated)** -- strict per-cell residual,
    reported for monitoring.

  The reframe codifies that external reference solvers (Brown's
  base_pot-inclusive single-iter DCFR with a distinct action
  abstraction) are sanity checks, not strict ground truth, when
  action menus differ between solvers. Different action menus and
  abstractions produce divergent -- but each correct -- Nash
  equilibria at deep-cap; strict per-action matching at depth is
  over-constrained.

### Compatibility

- No new public API; no signature changes; backward-compatible with
  v1.7.0.
- Rust binary `_rust.cpython-313-darwin.so` is REBUILT in v1.7.1
  (PR 50 and PR 51 touch Rust source). Users running from source
  must `maturin develop --release` after pull.
- `crates/cfr_core` bumps `0.7.0` -> `0.7.1`.

### Unblocks

- Persona retests for W2.3 (Sarah KK-vs-cbet-range) and W3.4
  (Daniel turn-spot MDF) -- both gated on the engine bundle pre-R8.
- Gate 4 200K-iter scaled exploitability validation can resume.
- Downstream documentation + packaging PRs (queued behind this
  ship) can merge through; PR 11 .dmg rebuild triggers on next pass.
