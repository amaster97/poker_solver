# v1.5.0 Coverage Gap Diagnosis (dry_K72_rainbow, 53.3% < 80%)

**Date:** 2026-05-23
**Subject:** Determine root cause of the `tests/test_v1_5_brown_apples_to_apples.py::test_v1_5_brown_apples_to_apples_parity[dry_K72_rainbow]` coverage failure (53.3% < 80% floor).
**Mode:** READ-ONLY (transient `/tmp/` scripts only; no source modifications).
**Time used:** ~25 min.

---

## TL;DR — Verdict: **CANONICALIZATION-BUG (test bug)**

The 53.3% coverage failure is **100% caused by a renderer bug** in the test
file's `_rust_history_substr_for_canonical` function
(`tests/test_v1_5_brown_apples_to_apples.py:321-384`). Rust's vector-form
CFR explores all 30 of Brown's canonical histories — they just get emitted
under a different wire-token name for paths that reach the effective
stack ceiling (all-in).

* Brown emits all-in tokens as `b<remaining>` / `r<extra>` with the literal
  chip amount (e.g. `b9500` for an opening jam; `r8750` for a raise-to-all-in
  facing `b750`).
* Rust emits all-in tokens as the single character `A` regardless of the
  amount (per `crates/cfr_core/src/hunl.rs:703-712`, the `ACTION_ALL_IN`
  branch unconditionally produces `token = "A"`).
* The test's renderer at `tests/test_v1_5_brown_apples_to_apples.py:376-383`
  always emits `b<chips_added>` / `r<amt>` for canonical `("b", amt)` /
  `("r", amt)` tokens, never `A` — so every Brown all-in history
  fails to match its Rust counterpart.

**Patching the renderer to emit `A` when the canonical amount equals the
stack ceiling restores coverage to 30/30 = 100.0%** (empirically verified —
see §3 below).

---

## 1. Reproduction data

Both engines were rerun at the same iterations (2000), DCFR params
(α=1.5, β=0, γ=2), seed=7, on the exact `dry_K72_rainbow` spot from
`tests/data/river_spots.json`.

| | Brown | Rust |
|---|---|---|
| Histories emitted | **30** | **32** (16 with `A` token) |
| Coverage (test renderer) | — | **16/30 = 53.3%** |
| Coverage (after patch) | — | **30/30 = 100.0%** |
| Stack ceiling at root | 9500 chips remaining | 9500 chips remaining |
| Effective contribution ceiling | 10000 chips (= pot/2 + stack) | 10000 chips |

Raw dumps preserved at:
- `/tmp/brown_histories.txt` — Brown's 30 history strings (per-player union, sorted)
- `/tmp/rust_histories.txt` — Rust's 32 history substrings (per-player union, sorted)
- `/tmp/coverage_diff.txt` — side-by-side comparison with canonical + status per row

---

## 2. Per-history table

Status: `MATCH_BOTH` / `MATCH_P0` / `MATCH_P1` = Rust has the substring under
at least one player bucket; `MISS` = Rust has no entry under the rendered
substring for either player.

All 14 MISS rows below correspond exactly to histories that end in (or pass
through) a raise/bet to the full stack — i.e. an all-in. Brown encodes the
explicit chip amount; Rust encodes `A`.

| Brown history | Canonical (kind, amount) | Test renderer output | Rust actually has | Status |
|---|---|---|---|---|
| `root` | `()` | `""` | `""` | MATCH_BOTH |
| `b750` | `(('b', 1250),)` | `b750` | `b750` | MATCH_P0 |
| `b1500` | `(('b', 2000),)` | `b1500` | `b1500` | MATCH_P0 |
| **`b9500`** | `(('b', 10000),)` | **`b9500`** | **`A`** | **MISS** |
| `b750/r1875` | `..r3125` | `b750r3125` | `b750r3125` | MATCH_BOTH |
| `b750/r3750` | `..r5000` | `b750r5000` | `b750r5000` | MATCH_BOTH |
| **`b750/r8750`** | `..r10000` | **`b750r10000`** | **`b750A`** | **MISS** |
| `b1500/r3000` | `..r5000` | `b1500r5000` | `b1500r5000` | MATCH_BOTH |
| `b1500/r6000` | `..r8000` | `b1500r8000` | `b1500r8000` | MATCH_BOTH |
| **`b1500/r8000`** | `..r10000` | **`b1500r10000`** | **`b1500A`** | **MISS** |
| `b750/r1875/r4688` | `..r7813` | `b750r3125r7813` | `b750r3125r7813` | MATCH_P0 |
| **`b750/r1875/r6875`** | `..r10000` | **`b750r3125r10000`** | **`b750r3125A`** | **MISS** |
| **`b750/r3750/r5000`** | `..r10000` | **`b750r5000r10000`** | **`b750r5000A`** | **MISS** |
| **`b1500/r3000/r5000`** | `..r10000` | **`b1500r5000r10000`** | **`b1500r5000A`** | **MISS** |
| **`b1500/r6000/r2000`** | `..r10000` | **`b1500r8000r10000`** | **`b1500r8000A`** | **MISS** |
| `c` | `(('c', 0),)` | `x` | `x` | MATCH_P0 |
| `c/b750` | `..b1250` | `xb750` | `xb750` | MATCH_BOTH |
| `c/b1500` | `..b2000` | `xb1500` | `xb1500` | MATCH_BOTH |
| **`c/b9500`** | `..b10000` | **`xb9500`** | **`xA`** | **MISS** |
| `c/b750/r1875` | `..r3125` | `xb750r3125` | `xb750r3125` | MATCH_P0 |
| `c/b750/r3750` | `..r5000` | `xb750r5000` | `xb750r5000` | MATCH_P0 |
| **`c/b750/r8750`** | `..r10000` | **`xb750r10000`** | **`xb750A`** | **MISS** |
| `c/b1500/r3000` | `..r5000` | `xb1500r5000` | `xb1500r5000` | MATCH_P0 |
| `c/b1500/r6000` | `..r8000` | `xb1500r8000` | `xb1500r8000` | MATCH_P0 |
| **`c/b1500/r8000`** | `..r10000` | **`xb1500r10000`** | **`xb1500A`** | **MISS** |
| `c/b750/r1875/r4688` | `..r7813` | `xb750r3125r7813` | `xb750r3125r7813` | MATCH_BOTH |
| **`c/b750/r1875/r6875`** | `..r10000` | **`xb750r3125r10000`** | **`xb750r3125A`** | **MISS** |
| **`c/b750/r3750/r5000`** | `..r10000` | **`xb750r5000r10000`** | **`xb750r5000A`** | **MISS** |
| **`c/b1500/r3000/r5000`** | `..r10000` | **`xb1500r5000r10000`** | **`xb1500r5000A`** | **MISS** |
| **`c/b1500/r6000/r2000`** | `..r10000` | **`xb1500r8000r10000`** | **`xb1500r8000A`** | **MISS** |

**Categorization:** all 14 MISS rows have canonical amount **10000 chips**
(= the effective contribution ceiling = `pot/2 + stack` = 500 + 9500).
Brown encodes the chip delta; Rust encodes `A`. No miss is from a
non-all-in path.

---

## 3. Empirical fix verification

A patched renderer (`/tmp/verify_a_fix.py`) that emits `A` when the
canonical amount equals the stack ceiling (10000 here) was tested:

```python
def _rust_history_substr_with_a_fix(canonical_history, stack_ceiling=10000):
    contrib = [500, 500]; actor = 1; tokens = []
    for kind, amt in canonical_history:
        if kind == "c":
            ... (unchanged)
        elif kind == "f":
            tokens.append("f"); break
        elif kind == "b":
            if amt == stack_ceiling:
                tokens.append("A")          # NEW
            else:
                tokens.append(f"b{amt - contrib[actor]}")
            contrib[actor] = amt; actor = 1 - actor
        elif kind == "r":
            if amt == stack_ceiling:
                tokens.append("A")          # NEW
            else:
                tokens.append(f"r{amt}")
            contrib[actor] = amt; actor = 1 - actor
    return "".join(tokens)
```

Result:

```
After A-token patch: 30/30 = 100.0%
```

Every Brown history now resolves to a Rust substring that exists in
Rust's `_build_rust_strategy_lookup` output. Verified at
`/tmp/verify_a_fix.py`.

---

## 4. Root cause file:line specifics

### 4a. The bug

**File:** `tests/test_v1_5_brown_apples_to_apples.py`
**Function:** `_rust_history_substr_for_canonical`
**Lines:** 321-384

The function maps canonical history tokens to Rust's hunl history
substring format. For `("b", amt)` (line 376) and `("r", amt)` (line 380)
it always emits `b<chips_added>` / `r<amt>`. It never inspects whether
`amt` equals the stack ceiling, so it never emits `A`.

### 4b. Why Brown and Rust disagree on the wire token

* **Brown's wire format** (`references/code/noambrown_poker_solver/cpp/src/river_game.cpp:53-65, 98-99`):
  All bets (including the all-in) are emitted as `b<amount>`, where the
  all-in is just one more entry in the bet-amounts list (literally
  `amounts.push_back(remaining)`). Brown does NOT have a separate all-in
  token; an all-in just means "the bet amount happened to equal
  `remaining`".
* **Rust's wire format** (`crates/cfr_core/src/hunl.rs:703-712`):
  The `ACTION_ALL_IN` action (id 13) is emitted unconditionally when
  `include_all_in` is true, and the resulting token is always the
  literal string `"A"` regardless of the chip amount. Bet/raise actions
  whose computed amount would exceed remaining stack are PRUNED from the
  enumeration (`enumerate_bets` at `hunl.rs:1069`, `enumerate_raises`
  at `hunl.rs:1091`), so a `b<stack>` token can never appear from the
  bet/raise enumeration path — only via `ACTION_ALL_IN` → `"A"`.

The canonicalization layer in `noambrown_wrapper.py` correctly resolves
both forms to the same `("b" | "r", amt)` canonical token. The bug is
SOLELY in the test-side renderer that converts canonical back to
Rust's wire format: it lacks the `amt == stack_ceiling → "A"` branch
that `noambrown_wrapper.py:_walk_our_tokens` has on the symmetric side
(lines 1017-1033) but the test does not import / reuse.

### 4c. Why this is purely a test bug, not a Rust engine bug

* All 30 Brown histories map cleanly onto a Rust substring after the
  fix (no leftover MISSes).
* Rust's 32 emitted history substrings (vs Brown's 30) is also
  explained: Rust enumerates the all-in action unconditionally even
  when the bet/raise enumeration provides an equivalent path
  (`hunl.rs:1133-1135`). For some paths Brown's amount-dedup at
  `river_game.cpp:67/102` collapses two amounts; Rust keeps them
  separate because `ACTION_ALL_IN` is appended outside the dedup
  loop. The 2 extra Rust paths are `b750r3125r7813A` paths (a
  4-bet-jam from both player perspectives), which Brown emits only
  twice while Rust emits four ways. This is benign (extra coverage,
  not missing coverage).
* The strategy values at every Brown history have a corresponding
  Rust strategy row at the patched substring; the test would then
  drop into the per-(hand, action) tolerance check.

---

## 5. Recommended fix

### Primary fix (the 53.3% → 100% coverage restoration)

**Single edit** in `tests/test_v1_5_brown_apples_to_apples.py:321-384`:
add an `amt == stack_ceiling → "A"` branch to both the `("b", amt)`
and `("r", amt)` cases. The stack ceiling is `pot // 2 + stack` per
the spot — for dry_K72_rainbow this is `500 + 9500 = 10000`; for
dry_A83_rainbow same.

A more elegant implementation would re-use the existing
`canonicalize_our_history` logic in `poker_solver/parity/noambrown_wrapper.py`
in reverse — i.e., walk canonical tokens against the same state machine
that `_walk_our_tokens` (lines 982-1057) uses, but emit our wire tokens
including `A`. The `noambrown_wrapper` module already has the symmetric
function on the canonical→Brown direction (`canonicalize_brown_history`),
just not yet on the canonical→ours direction. Adding it there
centralizes the rendering rules and ensures both halves of the diff
harness use one shape.

### Fix scope estimate

**LOC:** ~10-15 lines of code (1-2 added branches in the existing
renderer + a parametrization for `stack_ceiling`).

**Time:** 0.5 day. The fix itself is mechanical; verification requires
re-running the acceptance test (already takes ~5 min wall-clock on this
hardware) and checking that coverage moves to 100%.

**Risk:** Low. The patch only adds a new fallthrough branch to the
existing renderer; it does not change behavior for non-all-in paths.

---

## 6. Downstream caveats (issues that surface AFTER the coverage gate passes)

These are NOT in scope for the 53.3% coverage failure but will block
the per-action tolerance assertion when coverage hits ≥ 80%:

### 6a. Player-index inversion in the test's per-action check

The test at `tests/test_v1_5_brown_apples_to_apples.py:514-524` reads
`brown_dump.players[player]` and queries `rust_lookup.get((player, history_substr))`
with the SAME `player` index. This is wrong: Brown's P0 is IP (first
actor on river) and Rust's P0 is OOP (per `poker_solver/hunl.py:286-289`).
The mapping is **Brown P0 ↔ Rust P1**. The test's coverage check at
lines 497-502 papers over this with an "either player" disjunction, but
the per-action check would compare Brown's IP strategy against Rust's
OOP strategy. The fix is `rust_player = 1 - player` (1-line change).

Empirical evidence at `/tmp/check_per_action.py`: at `root` Brown's P0
(IP) shows `c=0.26, b750=0.34, b1500=0.40, b9500=0` while the test
looks up Rust's `(P=0, "")` and finds `[1.0, 0, 0, 0]` (which is Rust's
P0 = OOP — uniform-zero on bets because it's a hand at the wrong
infoset). After the player-flip Rust's P1 at `""` should show a
betting strategy comparable to Brown's P0 at `root`.

### 6b. Rust's `ACTION_ALL_IN` ignores `max_raises` cap

`crates/cfr_core/src/hunl.rs:1122-1135`: when `cap_reached` (i.e.
`street_num_raises >= max_raises`), Rust skips the bet/raise enumeration
BUT still appends `ACTION_ALL_IN` (line 1134 — unconditional under
`include_all_in`). Brown's tree at `river_game.cpp:76-78` returns just
`c, f` when at cap. So Rust has an extra `A` action at deep-cap nodes
that Brown does not.

Impact: at facing-bet nodes that have reached the raise cap, Rust's
action count = 3 (c, f, A) while Brown's = 2 (c, f). The per-action
assertion at `tests/test_v1_5_brown_apples_to_apples.py:540-545` already
guards `len(rust_row) != n_actions` as an action-count mismatch; this
will fire on every deep-cap node.

Fix scope: either (a) fix Rust to honor `max_raises` for
`ACTION_ALL_IN` too (~5 LOC in `enumerate_legal_actions`), or
(b) tolerate the extra `A` action in the test by truncating Rust rows
to Brown's action count at deep-cap nodes (~10 LOC in the test). Option
(a) is the principled fix — Brown's semantics are correct (after
`max_raises` raises, no more aggressive action is legal); Rust's
unconditional all-in is a behavioral bug.

### 6c. dry_A83_rainbow panic (already documented)

A separate Rust-side bug at `crates/cfr_core/src/dcfr_vector.rs:651`
(`index out of bounds: the len is 49 but the index is 49`) blocks the
second parametrized case. Out of scope here; documented in
`docs/v1_5_0_brown_acceptance_result.md` §3b.

---

## 7. Provenance / scripts

Transient diagnostic scripts (created and used in `/tmp/`; can be deleted):

* `/tmp/diff_coverage.py` — dumps Brown + Rust histories and computes the
  side-by-side diff.
* `/tmp/verify_a_fix.py` — patches the renderer with the `A` branch and
  reruns coverage (proves 30/30 = 100%).
* `/tmp/check_per_action.py` — sanity-checks per-action mean strategy
  at a few histories.
* `/tmp/check_action_parity.py` — fuller per-action printout with the
  patched renderer, used to surface the player-index inversion and the
  `max_raises` quirk.

Raw outputs:

* `/tmp/brown_histories.txt` — Brown's 30 histories (sorted).
* `/tmp/rust_histories.txt` — Rust's 32 history substrings (sorted).
* `/tmp/coverage_diff.txt` — annotated comparison (one row per Brown
  history).

No source-tree modifications were made (READ-ONLY mode honored).

---

## 8. Source-of-truth pointers

* Failing test: `/Users/ashen/Desktop/poker_solver/tests/test_v1_5_brown_apples_to_apples.py`
* Renderer (buggy): `tests/test_v1_5_brown_apples_to_apples.py:321-384`
* Brown wire format: `references/code/noambrown_poker_solver/cpp/src/main.cpp:176-194` (`action_token`) and `river_game.cpp:53-106` (`legal_actions`)
* Rust wire format: `crates/cfr_core/src/hunl.rs:683-742` (`apply_player`'s token emission) and `hunl.rs:1105-1139` (`enumerate_legal_actions`)
* Canonicalization (Brown side): `poker_solver/parity/noambrown_wrapper.py:874-929` (`_walk_brown_tokens`)
* Canonicalization (our side, reused): `poker_solver/parity/noambrown_wrapper.py:982-1057` (`_walk_our_tokens` — already has the symmetric `"A" → ("b" | "r", remaining_total)` logic at lines 1017-1033; the test's renderer needs the INVERSE of this).
