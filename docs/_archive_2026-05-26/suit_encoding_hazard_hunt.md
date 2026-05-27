# Suit-encoding-style hazard hunt (cross-system index aliasing)

**Date**: 2026-05-24
**Scope**: hunt for hazards where two systems with different indexings share
common character labels (so the bug is invisible at the `chr` level but
silently mismaps when the integer index from system A is fed into system B).
**Status**: READ-ONLY audit; no code modified.

## Background

The P1 broader-audit was triggered by the discovery of a suit-encoding bug
in `poker_solver/parity/noambrown_wrapper.py`: our `Card.suit` (indexed
against `"shdc"`, so 0=s, 1=h, 2=d, 3=c) was being used directly into
`_BROWN_SUIT_CHARS = "cdhs"` (indexed 0=c, 1=d, 2=h, 3=s). Same chars,
DIFFERENT indexing — so `_BROWN_SUIT_CHARS[card.suit]` produces clubs when
we hold spades.

This audit enumerates other cross-system index-vs-index seams in the
codebase to spot the same class of hazard.

## Systems indexed in this codebase

| System | Suit ordering | Rank ordering | Card int | Action ids | Player ids |
| --- | --- | --- | --- | --- | --- |
| Ours (Python `poker_solver`) | `"shdc"` (s=0, h=1, d=2, c=3) | `"23456789TJQKA"` (2-A → 0-12, but stored as rank=2..14) | `rank*4 + suit`, range [8,59] | `ACTION_FOLD=0..ACTION_ALL_IN=13` (see `poker_solver/action_abstraction.py:18-31`) | `P0=0`, `P1=1`; on river OPEN our `cur_player=1` (P1=OOP first to act) |
| Ours (Rust `crates/cfr_core`) | `"shdc"` (matches Python) | `"23456789TJQKA"` (matches Python) | `rank*4 + suit` or `(rank<<2)\|suit` (matches Python) | matches Python | matches Python |
| Brown (`noambrown_poker_solver` cpp) | `"cdhs"` (c=0, d=1, h=2, s=3) — `cards.cpp:8-9` | `"23456789TJQKA"` (rank index 0..12) | `suit*13 + rank` — `cards.cpp:19-28` | char-based tokens (`c`/`f`/`b`/`r`) | `player=0` acts first on river — `river_game.cpp:10` |

The hazard class: any seam that uses an integer index from system A as if
it were the same-meaning integer in system B.

## Candidate sites

### Site 1 — `noambrown_wrapper._card_to_brown_str` (KNOWN BUG)

`poker_solver/parity/noambrown_wrapper.py:193-197`

```python
def _card_to_brown_str(card: Card) -> str:
    rank_char = _BROWN_RANK_CHARS[card.rank - 2]
    suit_char = _BROWN_SUIT_CHARS[card.suit]
    return rank_char + suit_char
```

- **Pattern**: index-vs-char across two systems
- **Our system** `card.suit ∈ {0,1,2,3}` = `"shdc"`
- **Brown** `_BROWN_SUIT_CHARS = "cdhs"` indexed 0-3
- **Verdict**: **BUG** (already known) — `_BROWN_SUIT_CHARS[card.suit]` maps our
  index through Brown's char table, swapping suits.
- **Fix**: `suit_char = "shdc"[card.suit]` (no need for the Brown table; Brown
  reads the literal char). Or: `suit_char = _BROWN_SUIT_CHARS[(("shdc".index(("shdc")[card.suit]) is irrelevant)]` — simpler: just use `"shdc"[card.suit]` directly since the chars are literally the same; Brown parses the char.

### Site 2 — `noambrown_wrapper._brown_card_id` (KNOWN BUG, same flavor)

`poker_solver/parity/noambrown_wrapper.py:200-209`

```python
def _brown_card_id(card: Card) -> int:
    rank_char = _BROWN_RANK_CHARS[card.rank - 2]
    suit_char = _BROWN_SUIT_CHARS[card.suit]
    return _BROWN_SUIT_INDEX[suit_char] * 13 + _BROWN_RANK_INDEX[rank_char]
```

- **Pattern**: same as Site 1 — `_BROWN_SUIT_CHARS[card.suit]` is the
  mis-indexed lookup.
- **Verdict**: **BUG** (already known)
- **Fix**: `suit_char = "shdc"[card.suit]` (or compute Brown's id directly:
  `Brown's_suit_int = _BROWN_SUIT_INDEX["shdc"[card.suit]]`; then
  `Brown's_suit_int * 13 + (card.rank - 2)`).

### Site 3 — Player-index convention mismatch on river-open (`our_strategy_to_brown_matrix` + callers)

`poker_solver/parity/noambrown_wrapper.py:802` + `1124-1156`,
`tests/test_river_diff.py:399-411`, `tests/test_v1_5_brown_apples_to_apples.py:515-521`

- **Pattern**: player-index vs player-index across our and Brown's
  conventions.
- **Our system** (`poker_solver/hunl.py:425-429`, `parity/noambrown_wrapper.py:802`):
  symmetric river-open → `cur_player = 1` (P1 = OOP = first to act on river).
- **Brown** (`references/code/noambrown_poker_solver/cpp/src/river_game.cpp:10`):
  initial `player = 0` (P0 = first to act on river).
- **Consequence**: Brown's `players[0]` (Brown's first-actor = OOP) corresponds
  to our **P1**, not our **P0**. The diff loops at:
  - `test_river_diff.py:400-405` (compares `brown_dump.players[player].profile`
    with `our_matrix[history].get(player)` for `player ∈ {0,1}`)
  - `test_v1_5_brown_apples_to_apples.py:515-521` (compares
    `brown_dump.players[player]` with `rust_lookup.get((player, history_substr))`)

  use the same integer `player` on both sides. Our `our_matrix` /
  `rust_lookup` are keyed by our-internal player (0 if hole ∈ p0 range,
  1 if hole ∈ p1 range). The fixtures send `spot.ranges[0]` to Brown's
  `players[0]` slot, so on Brown's side P0 (their first-actor) ends up
  carrying our P0's range — but in our solver, our P0 is NOT first-to-act
  on the river. Both sides act in their own native convention; the diff
  compares "our P0's strategy when P0 is the in-position player" against
  "Brown's player 0's strategy when player 0 is OOP". That's an
  apples-to-oranges comparison.
- **Verdict**: **NEEDS-VERIFICATION** (likely BUG). The diff harness assumes
  Brown's `players[0]` and our `hands_p0`-membership are the same player. With
  the same range in both slots, the diff still finds plenty of overlap
  (lots of pairs / same hands), but the per-cell action probabilities
  belong to different players' strategies. Within the current
  `PER_ACTION_TOL = 5e-3` tolerance and on near-symmetric fixtures, this
  could silently pass. Spots with markedly asymmetric ranges (e.g.
  `monotone_AKs7s`, `monotone_TJ5h`) should be re-checked.
- **Fix path**: either (a) swap the player axis when writing the Brown
  config so that Brown's `players[0]` carries our P1's range and
  `players[1]` carries our P0's range; or (b) swap on the read side in
  `our_strategy_to_brown_matrix` / the diff loop. (a) is cleaner.
- **Cross-check with downstream bug**: even if Site 3 turns out to be a
  no-op (i.e. Brown internally permutes to its own convention regardless),
  the suit-encoding bug in Sites 1-2 turns range hand-strings into Brown's
  wrong-suit hands; any "missing hand" in `rust_rows.get(hand_str)` is
  silently skipped at `test_v1_5_brown_apples_to_apples.py:534-538`,
  hiding the failure.

### Site 4 — Hole-string encoding compared across Brown / Rust (`_combo_to_hole_string` + Brown's `hand_str`)

`tests/test_v1_5_brown_apples_to_apples.py:290-318` and `:531-539`

- **Pattern**: char-vs-char comparison after each side independently emits
  a string from its own native indexing.
- **Our system** emits via `suits = "shdc"` indexed by `card.suit` (correct
  for our system).
- **Brown's `brown_hands[hand_idx]`** comes from Brown's dump; Brown's
  internal int → char mapping is `"cdhs"` indexed by Brown's `suit*13 +
  rank` encoding. But Brown's *emitted string* uses literal chars c/d/h/s.
- **Verdict**: **OK in isolation** — both sides emit the same physical-card
  chars. However, the upstream Sites 1-2 bug means the *physical cards
  Brown received* are wrong-suit, so `brown_hands` contains Brown's hand
  strings for the wrong-suit cards (e.g. an intended "AsKs" arrives at
  Brown as "AcKc", and that's what shows up in `brown_hands`). Then
  `rust_rows.get("AcKc")` silently returns None (Rust solved for "AsKs"),
  and the diff is silently skipped — masking the entire spot.
- **Recommendation**: once Sites 1-2 are fixed, this comparison is
  semantically valid. Re-run the parity tests; expect them to fail loudly
  on any genuine divergence (instead of silently passing on missing keys).
  Consider tightening `if rust_row is None: continue` to record-and-fail
  so missing entries are visible.

### Site 5 — Cross-tier card encoding (Python ↔ Rust)

`poker_solver/card.py:117-119` (`card_to_int = rank*4 + suit`),
`crates/cfr_core/src/hunl.rs:149-150` (`card_to_int(rank, suit) = rank*4 + suit`),
`crates/cfr_core/src/preflop.rs:545-547` (`(rank << 2) \| suit`)

- **Pattern**: same-formula integer encoding shared between Python and
  Rust.
- **Our system (Python)** and **our system (Rust)** both use suit indexing
  `"shdc"` and the formula `rank*4 + suit`.
- **Verdict**: **OK** — Python and Rust share one convention.

### Site 6 — Action IDs Python ↔ Rust

`poker_solver/action_abstraction.py:18-31` and
`crates/cfr_core/src/hunl.rs:98-111`

- **Pattern**: per-action integer constant shared between Python and Rust.
- **Both systems** define `ACTION_FOLD=0`, `ACTION_CHECK=1`, …,
  `ACTION_ALL_IN=13` identically.
- **Verdict**: **OK** — verbatim mirror; no Brown counterpart (Brown uses
  char tokens, not ints, in its dump).

### Site 7 — Suit permutation table Python ↔ Rust

`poker_solver/abstraction/equity_features.py:43-45` and
`crates/cfr_core/src/abstraction.rs:45-70`

- **Pattern**: 24-entry suit-permutation lookup table shared between
  Python and Rust.
- **Both systems** use `itertools.permutations((0,1,2,3))` order; Rust
  hardcodes the same 24 rows.
- **Verdict**: **OK** — same convention end-to-end (tested at
  `abstraction.rs:463-468`).

### Site 8 — Hand-class label keys (`"AA"`, `"KK"`, …)

`poker_solver/pushfold.py:236-237`, `poker_solver/range_aggregator.py:439-486`,
chart JSONs (`poker_solver/charts/*.json`)

- **Pattern**: 169-element key set, but string-keyed throughout.
- **Verdict**: **OK** — no integer indexing crosses systems; the only int
  cross-walk is `_combo_count(hand_class)`-style functions that compute
  internal-only.

### Site 9 — Card serialization in `library.py` (`[c.rank, c.suit]` → JSON → `Card(int(r), int(s))`)

`poker_solver/library.py:188`, `:192`, `:350`, `:357`, `:384`, `:388-389`

- **Pattern**: round-trip serialization within one system.
- **Verdict**: **OK** — write and read use the same convention.

### Site 10 — Card encoding `card_to_int` ↔ `int_to_card`

`poker_solver/card.py:117-124`, mirrored in Rust by `rank_of`, `suit_of`
(`crates/cfr_core/src/abstraction.rs:82-90`, `hunl.rs:153-161`)

- **Pattern**: bit-shift inverse.
- **Verdict**: **OK** — internally consistent (Python: `rank*4 + suit` ↔
  `(rank // 4, rank % 4)`; Rust: `c >> 2` / `c & 3`).

### Site 11 — Leduc / Kuhn action ids

`poker_solver/games.py:178-189` (cites `open_spiel`'s fold=0/call=1/raise=2),
`crates/cfr_core/src/leduc.rs`, `crates/cfr_core/src/kuhn.rs`

- **Pattern**: action-id convention documented as `open_spiel`-compatible.
- **Verdict**: **OK** — no runtime cross-system seam (no diff against
  open_spiel binary in this repo; these are pure-Python / pure-Rust
  self-contained games).

### Site 12 — Brown ↔ ours: range hand-string parsing back into our `Combo`

`poker_solver/parity/noambrown_wrapper.py:230-247` (`_parse_combo`)

- **Pattern**: parses a 4-char hand string ("AhKd") via `parse_card`.
- **Verdict**: **OK** — `parse_card` is char-based (`poker_solver/card.py:41-49`),
  reads literal chars and uses `SUIT_VALUE` to assign our int. No
  cross-system index.

## Summary

| Verdict | Count |
| --- | --- |
| **BUG** | 2 (sites 1 + 2, both pre-existing and known) |
| **NEEDS-VERIFICATION** | 1 (site 3 — player-index convention mismatch) |
| **OK** | 9 (sites 4-12) |

## Recommended priorities

1. **Fix sites 1-2 first** (the original known bug) and re-run
   `test_river_diff` / `test_v1_5_brown_apples_to_apples`. Expect previously
   silent failures to surface — including any genuine site-3 mismatch.
2. **Investigate site 3** by manually solving a small asymmetric spot
   (e.g. P0 nuts-only, P1 air-only) on both engines and inspecting whether
   `brown_dump.players[0]` matches our P0 or our P1.
3. **Harden site 4 / test infra**: change `if rust_row is None: continue`
   to record-and-fail (or at least counter the missing keys) so the next
   silent skip stands out instead of disappearing in the noise.
