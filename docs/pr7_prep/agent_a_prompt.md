# PR 7 Agent A — build wrapper + spot fixtures + Brown invocation module

> **Orchestrator note:** copy the entire text below (between the `---` markers) and pass it as the `prompt=...` arg to a fresh `Agent(...)` invocation. Do not include this header in the prompt itself.

---

## 5-line summary

**You are PR 7 Agent A.**
**Your scope:** the build-script + fixture + subprocess-wrapper trio that lets PR 7 invoke Noam Brown's `river_solver_optimized` C++ binary on a curated set of 15 river spots and parse its JSON output into a Python representation our diff harness can compare against.
**Your contract:** ship `scripts/build_noambrown.sh`, `tests/data/river_spots.json` (15 spots), `poker_solver/parity/__init__.py`, and `poker_solver/parity/noambrown_wrapper.py`; export `load_spots`, `find_brown_binary`, `write_brown_config`, `run_brown_solver`, `canonicalize_brown_history`, `canonicalize_our_history`, `our_strategy_to_brown_matrix`, plus the `RiverSpot` / `BrownStrategyDump` / `BrownPlayerProfile` / `BrownInfosetEntry` / `CanonicalHistory` dataclasses; Agent B's diff harness and Agent C's smoke tests consume these surfaces.
**Your success criteria:** ruff clean, black clean, `mypy --strict` clean on `noambrown_wrapper.py`; the build script is idempotent + soft-fails on missing toolchain; the 15 fixture spots load without overlap-with-board errors; `canonicalize_our_history(canonicalize_brown_history(h))` is identity for ten hand-built histories; raise encoding canonicalization (our `r<to_total>` ↔ Brown's `r<extra-beyond-call>`) is correct; ALL 138+ existing tests still pass.
**File ownership:** you own `scripts/build_noambrown.sh`, `tests/data/river_spots.json`, `poker_solver/parity/__init__.py`, `poker_solver/parity/noambrown_wrapper.py`. You may NOT touch any test file, `poker_solver/hunl.py`, `poker_solver/solver.py`, or `pyproject.toml` (Agent B owns the marker registration there).

---

## Strict file ownership

**You own (write + create freely):**
- `/Users/ashen/Desktop/poker_solver/scripts/build_noambrown.sh` (new file)
- `/Users/ashen/Desktop/poker_solver/tests/data/river_spots.json` (new file; create `tests/data/` if missing)
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/__init__.py` (new file; minimal re-exports)
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` (new file; the main module)

**You may surgically modify:**
- `/Users/ashen/Desktop/poker_solver/.gitignore` — add `references/code/noambrown_poker_solver/cpp/build/` if not already gitignored. (Brown's repo has its own `.gitignore`; verify and only add to the root if Brown's doesn't already cover it.)
- `/Users/ashen/Desktop/poker_solver/references/README.md` — append one line noting Brown's repo is now a runtime dep of PR 7's parity test (not just a read-only reference). Append-only; do not rewrite.

**You must NOT touch:**
- `poker_solver/hunl.py`, `poker_solver/solver.py`, `poker_solver/dcfr.py`, `poker_solver/abstraction/*` — frozen for PR 7.
- `poker_solver/__init__.py` — no re-export needed; tests import directly from `poker_solver.parity.noambrown_wrapper`.
- `pyproject.toml` — Agent B registers `pytest.mark.parity_noambrown`. No new third-party deps. (Brown's binary is invoked via subprocess; we don't need a C++ binding lib.)
- Any test file — Agent B owns `tests/test_noambrown_river_parity.py`; Agent C owns `tests/test_noambrown_self_sanity.py`.
- Any file inside `references/code/noambrown_poker_solver/` — you BUILD from it (out-of-tree under `cpp/build/`), you do NOT modify it. The vendored source is read-only.

If you discover an awkward signature or a contract gap mid-implementation, **do not silently change the spec'd interface**. Stop and write a short note to the orchestrator describing the conflict; the orchestrator reconciles across agents.

## Read first (in this order)

1. **The canonical spec (source of truth):** `/Users/ashen/Desktop/poker_solver/docs/pr7_prep/pr7_spec.md`. Internalize §1 (goal + tolerance), §2 (why Brown's repo is the right gate), §3 (what PR 7 does NOT do), §4 (fixture design — 15 spots, schema, ranges, file size budget), §5 step 5 (history canonicalization — load-bearing), §6 (build script design + idempotency rules), §7 (files to create — your row is Agent A), §8 (MIT attribution), §9 risks 1, 2, 3, 5, 7 (your responsibility), §11 #1, #2, #4 (your responsibility), §12 (open decisions — defaults locked below).
2. **Spec consistency review:** `/Users/ashen/Desktop/poker_solver/docs/spec_consistency_review.md`. Especially I3 (tolerance: PR 6 + PR 7 + PR 8 standardize on `5e-3` per-action, `1e-3 × pot` per game value), I7 (bet-size sets vary per PR — Brown invocation honors `spot.bet_sizes`), N1 (license attribution template — PR 6's is canonical; copy that shape into your module docstring), the PR 7 row of "ready" status (no blockers).
3. **The PLAN (locked decisions):** `/Users/ashen/Desktop/poker_solver/PLAN.md`. §1 "DCFR α=1.5, β=0, γ=2.0" — these are the exact flags you pass to Brown's binary. §1 "Raise caps: postflop 3" — your fixture `max_raises` value. §4 "River-only HUNL spots → diff vs `noambrown/poker_solver`" — confirms PR 7 is the river parity gate. §6 license audit — Brown's repo is MIT (OK to invoke + parse output; no code copy).
4. **The autonomous log:** `/Users/ashen/Desktop/poker_solver/docs/autonomous_log.md`. Skim for PR 7 entries.
5. **Brown's binary source (read-only):**
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/main.cpp` — CLI flag parsing (lines 579-640), action-token encoding `action_token()` (lines 176-195), strategy JSON output `write_strategy_json()` (lines 222-290). **Critical reads:** lines 176-194 show Brown stores raises as **extra-beyond-call** (`raise_amount = delta - to_call`), while our `hunl.py` line 400 stores raise as **to_total** (`token = f"r{new_contrib}"`). Lines 182-186 show Brown emits `c` for both check-as-no-action and call (no distinct "x" token). Lines 222-290 show the JSON schema: `{"players":[{"hands":[...],"weights":[...],"profile":{"key":{"actions":[...],"strategy":[[per-hand-row],...]}}}]}`.
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/subgame_config.h` and `cpp/src/subgame_config.cpp` (lines 1-22 of `.h` and 303-388 of `.cpp`) — the subgame JSON config schema. Your `write_brown_config()` writes this format.
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.h` — `RiverGame` shape: HU (2 players, `std::array<..., 2>`); single `stack int`; `hand_weights` per player.
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/river_game.cpp` — board/hand filtering at construction (`213-251`); how raise amounts are computed when a bet/all-in collides (`63-66, 98-100`).
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/src/trainer.cpp:353-361` — DCFR algorithm branch with α/β/γ application. Confirms the algorithm we invoke is byte-equivalent to ours.
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/cpp/CMakeLists.txt` — build configuration. Single target `river_solver_optimized`. Default `Release`. Compile flags `-O3 -DNDEBUG -march=native -ffast-math -funroll-loops` (non-MSVC).
   - `/Users/ashen/Desktop/poker_solver/references/code/noambrown_poker_solver/LICENSE` — MIT, Copyright (c) 2025 Noam Brown.
6. **Our action-encoding surface (do NOT modify; read to understand the canonicalization mapping):**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/hunl.py` lines 309-401: `infoset_key()` format `f"{player_hole}|{board}|{street_token}|{history}"` and action token emission. Key facts: bet token = `f"b{amount}"` (line 388), raise token = `f"r{new_contrib}"` where `new_contrib` is the TOTAL contributed-to (line 400), all-in token = `"A"` (line 377), call = `"c"`, check = `"x"`, fold = `"f"`. **Brown does NOT have a distinct `x` token; you map both `c` and `x` to Brown's `c`.** **Brown does NOT have a distinct `A` token; you map `A` to `b<remaining>` (opening all-in) or `r<remaining_after_call>` (all-in-as-raise) depending on the `to_call` context at that action.**
   - `/Users/ashen/Desktop/poker_solver/poker_solver/action_abstraction.py` — read-only reference for action IDs and bet/raise computation.
7. **Reference style — PR 5 Agent A prompt pre-draft:** `/Users/ashen/Desktop/poker_solver/docs/pr5_prep/agent_a_prompt.md`. Same shape and tone.

## Default decisions LOCKED (do not deviate)

These defaults are from PR 7 spec §12 + the orchestrator brief. The user has authorized autonomous mode; these defaults are LOCKED unless the user redirects before launch:

1. **Brown's binary path (canonical):** `references/code/noambrown_poker_solver/cpp/build/river_solver_optimized` (the spec §1/§5/§6 wording inconsistently mentions both `cpp/build/` and `build/`; the canonical path is **`cpp/build/`** because `cpp/CMakeLists.txt` is the build root and `cmake -S references/code/noambrown_poker_solver/cpp -B references/code/noambrown_poker_solver/cpp/build` places artifacts there). Document this in `find_brown_binary()`.
2. **DCFR algorithm flags (locked):** `--algo dcfr --dcfr-alpha 1.5 --dcfr-beta 0 --dcfr-gamma 2`. These match PLAN.md and Brown's `cpp/src/trainer.cpp:353-361`. Do NOT expose these as wrapper parameters.
3. **Default iterations: 2000** (matches Brown's `main.cpp:31` default; PR 7 spec §5 step 2 and §12 #5). Wrapper exposes `iterations: int = 2000`; per-spot override via `RiverSpot.iterations_override`.
4. **Seed: 7** (Brown's `main.cpp:36` default). Pass `--seed 7` explicitly for paranoia. PR 7 spec §11 #1.
5. **Pot/stack units: integer chips** (PR 7 spec §12 #4). Fixture uses `pot=1000, stack=9500` (10 BB pot, 95 BB stack at the implicit `big_blind=100` chip convention). Our `HUNLConfig.big_blind=100` cents per BB makes the two scales match 1:1.
6. **15 spots** (PR 7 spec §12 #2 default). Five categories × 3 spots: dry rainbow, wet rainbow, monotone, paired, broadway-heavy.
7. **Range size: 30–60 combos per side** (PR 7 spec §12 #9). Each side includes made hands + bluff candidates; total ≥30 combos.
8. **Bet sizes per spot:** `[0.75, 1.5]` for most spots (PR 7 spec §4 example); some may use `[0.5, 1.0]` or `[1.0]` for compact subtrees. Each spot encodes its own `bet_sizes` field. `include_all_in: true`, `max_raises: 3` (matches PLAN.md postflop cap).
9. **Schema version: 1** (PR 7 spec §4). Bumping is a future-PR concern.
10. **Soft-fail on missing toolchain** (PR 7 spec §6 + §12 #3). `build_noambrown.sh` exits 0 (NOT 1) when cmake or c++ is missing. The diff harness later handles the missing-binary case via `pytest.skip`.
11. **`poker_solver/parity/` is the canonical home for future cross-references** (PR 7 spec §12 #7). Reserve namespace for `slumbot_wrapper.py`, `open_spiel_wrapper.py`, etc. Document in `__init__.py`'s docstring.
12. **No new third-party dependencies.** Standard library only: `subprocess`, `json`, `tempfile`, `pathlib`, `dataclasses`, `typing`, `re`. (NumPy is already a project dep; you may use it for the `our_strategy_to_brown_matrix` adapter.)

## Public API contract (signatures Agent B + Agent C depend on)

Export the following from `poker_solver/parity/noambrown_wrapper.py`. **Signature drift breaks Agent B's `tests/test_noambrown_river_parity.py` and Agent C's `tests/test_noambrown_self_sanity.py`.** Type hints required (mypy --strict).

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

import numpy as np

from poker_solver.card import Card
from poker_solver.solver import SolveResult


# ============================================================================
# Dataclasses
# ============================================================================

Combo = tuple[Card, Card]  # type alias


@dataclass(frozen=True)
class RiverSpot:
    """A single river-spot fixture parsed from tests/data/river_spots.json.

    Schema version 1. Hand-authored, no random seeds in construction.
    """
    id: str
    description: str
    board: tuple[Card, ...]  # all 5 river cards
    pot: int                  # integer chips
    stack: int                # integer chips, per player (symmetric)
    bet_sizes: tuple[float, ...]
    include_all_in: bool
    max_raises: int
    ranges: tuple[
        tuple[tuple[Combo, float], ...],  # player 0 (hand, weight) pairs
        tuple[tuple[Combo, float], ...],  # player 1
    ]
    iterations_override: Optional[int]  # None → use default (2000)


@dataclass(frozen=True)
class BrownInfosetEntry:
    """One infoset row from Brown's strategy dump.

    actions: per-action token list, e.g. ("b500", "c", "f").
    strategy: per-hand × per-action probability matrix; shape (num_hands, num_actions).
              Brown stores it as list[list[float]]; we keep tuple-of-tuple for hashability
              and let consumers convert to np.ndarray if needed.
    """
    actions: tuple[str, ...]
    strategy: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class BrownPlayerProfile:
    hands: tuple[str, ...]                       # e.g. ("AhKh", "QdQc", ...)
    weights: tuple[float, ...]
    profile: dict[str, BrownInfosetEntry]        # key = "/"-joined history (e.g. "root", "b500/c")


@dataclass(frozen=True)
class BrownStrategyDump:
    """Parsed output from Brown's --dump-strategy JSON."""
    players: tuple[BrownPlayerProfile, BrownPlayerProfile]
    game_value_p0: Optional[float]  # if parseable from stdout; else None
    game_value_p1: Optional[float]
    iterations_run: int


# A "canonical history" is a tuple of (action_kind, amount) pairs.
# action_kind ∈ {"f", "c", "b", "r"}. For "f" and "c", amount is 0.
# For "b" and "r", amount is the (canonicalized) chip integer.
# Brown's encoding (raise = extra-beyond-call) is normalized to our encoding
# (raise = to_total) inside canonicalize_brown_history(), so equal play
# produces equal canonical tuples.
CanonicalHistory = tuple[tuple[Literal["f", "c", "b", "r"], int], ...]


# ============================================================================
# Public functions
# ============================================================================

def load_spots(path: Path) -> list[RiverSpot]:
    """Load + validate river_spots.json.

    Validation (raises ValueError with the spot id + line context):
    - schema_version == 1.
    - Exactly 2 players per spot.
    - len(board) == 5 (river has all 5 cards).
    - All board cards unique.
    - Every hand in every range: 2 cards, both distinct, no overlap with board.
    - All weights > 0.
    - bet_sizes is a tuple of floats in (0, 5].
    - pot > 0, stack > 0, integers.
    - max_raises >= 1.
    - At least 30 combos per side (per PR 7 §4 range design rule).
    """
    ...


def find_brown_binary() -> Optional[Path]:
    """Resolve Brown's binary path.

    Looks at `<repo_root>/references/code/noambrown_poker_solver/cpp/build/river_solver_optimized`.
    Returns the Path if the file exists AND is executable; otherwise None.

    Repo root is resolved via Path(__file__).resolve().parents[2] (parity → poker_solver → repo root).
    No exceptions; never crashes.
    """
    ...


def write_brown_config(spot: RiverSpot, path: Path) -> None:
    """Emit a JSON file in Brown's subgame schema (cpp/src/subgame_config.h:7-22).

    Format (verified against cpp/src/subgame_config.cpp:303-388):
    {
        "board": ["Ks", "7h", "2d", "4c", "Jh"],
        "pot": 1000,
        "stack": 9500,
        "bet_sizes": [0.75, 1.5],
        "include_all_in": true,
        "max_raises": 3,
        "players": [
            {"hands": ["AhKh", ...], "weights": [1.0, ...]},
            {"hands": ["QdQc", ...], "weights": [1.0, ...]}
        ]
    }

    Card-to-string convention: rank ∈ "23456789TJQKA" + suit ∈ "cdhs" (lowercase).
    Verify against Brown's cards.cpp parsing.
    """
    ...


def run_brown_solver(
    spot: RiverSpot,
    binary: Path,
    iterations: int = 2000,
    seed: int = 7,
    timeout_sec: float = 600.0,
) -> BrownStrategyDump:
    """Subprocess-invoke Brown's binary and parse the --dump-strategy output.

    Constructs argv:
        [str(binary),
         "--config", <tempfile path>,
         "--algo", "dcfr",
         "--iters", str(iterations),
         "--dcfr-alpha", "1.5",
         "--dcfr-beta", "0",
         "--dcfr-gamma", "2",
         "--seed", str(seed),
         "--dump-strategy", <tempfile path 2>]

    Uses tempfile.NamedTemporaryFile (or per-call mkdtemp) so pytest-xdist
    parallel runs don't collide (PR 7 §9 risk 8).

    Parses stdout for "game_value_p0" / "game_value_p1" lines if present.
    Returns BrownStrategyDump.

    Raises:
        subprocess.CalledProcessError on non-zero exit.
        subprocess.TimeoutExpired on timeout.
        FileNotFoundError if binary path doesn't exist.
    """
    ...


def canonicalize_brown_history(token_str: str) -> CanonicalHistory:
    """Parse Brown's history string (e.g. "root", "b500", "b500/c", "b500/r1000/c")
    into our canonical (action_kind, amount) tuple form.

    Brown's encoding (cpp/src/main.cpp:176-195):
    - "c"             → ("c", 0)
    - "f"             → ("f", 0)
    - "b<amount>"     → ("b", amount)   — bet amount in chips (extra-beyond-pot baseline)
    - "r<extra>"      → ("r", new_total) — Brown stores RAISE = EXTRA-BEYOND-CALL,
                                            but we normalize to RAISE-TO-TOTAL
                                            (so it matches our canonicalize_our_history).
                                            The new_total = previous_aggressor_total + to_call + extra.
                                            We accumulate state while walking tokens left-to-right.

    "root" → ()  (empty tuple, the root infoset).

    State accumulation: walk tokens, track each player's cumulative contribution
    starting from spot.pot/2 each (matching Brown's RiverGame construction).
    The to_call at each step = max(contrib0, contrib1) - min(contrib0, contrib1).
    For "r<extra>": the actor's new contribution = max(contrib0, contrib1) + extra.

    Returns the canonical tuple. Pure function. Deterministic.
    """
    ...


def canonicalize_our_history(history_str: str, initial_pot: int = 1000) -> CanonicalHistory:
    """Parse our hunl.py infoset key's history substring (after the third '|')
    into the same canonical form as canonicalize_brown_history.

    Our encoding (poker_solver/hunl.py:343-401):
    - "c"             → ("c", 0)
    - "x"             → ("c", 0)   — check ≡ call(0); Brown treats both as "c"
    - "f"             → ("f", 0)
    - "b<amount>"     → ("b", amount)   — same convention as Brown
    - "r<to_total>"   → ("r", to_total) — already in to-total form; no transformation
    - "A"             → ("b", remaining_stack)  if to_call == 0 at that moment
                        OR ("r", remaining_total) if to_call > 0
                        (i.e., we re-emit all-in as the bet/raise amount Brown would have).
                        Requires state-tracking to know which case.

    The history substring is the part AFTER the third "|" in our infoset_key.
    Initial street prefix uses "/" separator between streets (street_tokens are joined
    via "/"); WITHIN a street, tokens are concatenated without separator (per
    hunl.py:317 `"/".join("".join(tokens) for tokens in all_streets)`).

    Returns the canonical tuple. State-tracking required to resolve "A". For
    PR 7 (river-only), only the within-river current_street_tokens are present;
    the prior-streets segments are empty (river-start fixtures with no prior
    betting).

    Pure function once state-tracking is encapsulated. Deterministic.
    """
    ...


def our_strategy_to_brown_matrix(
    result: SolveResult,
    hands_p0: tuple[Combo, ...],
    hands_p1: tuple[Combo, ...],
    spot: RiverSpot,
) -> dict[str, dict[int, np.ndarray]]:
    """Flatten our per-(hand, infoset) strategies into Brown's matrix shape.

    Walk result.average_strategy, parse each infoset key into (player, hand, canonical_history),
    and group into a nested dict:
        out[canonical_history_str][player_index] = np.ndarray of shape (num_hands, num_actions)

    where canonical_history_str = the brown-style "/"-joined token string for that infoset.

    Used by Agent B's diff harness to look up "our distribution at this Brown-style
    infoset key, for this hand index".

    Hands NOT present in the spot.ranges are silently dropped (the solver iterated
    over the explicit range; off-range hands produce no infoset entries).

    Returns: dict keyed by canonical_history_str → dict keyed by player int (0 or 1)
             → np.ndarray (num_hands, num_actions).
    """
    ...
```

**Internal helpers (you choose, but document them):**
- `_card_to_brown_str(card: Card) -> str` — emit `"Ah"`-style; Brown uses lowercase suit.
- `_brown_str_to_card(s: str) -> Card` — inverse.
- `_state_for_history(spot: RiverSpot) -> dict` — initial bookkeeping for canonicalization (per-player contributions starting at `spot.pot // 2`).

## Cross-agent contracts (Agent B and Agent C depend on these)

**Module exports (Agent B will import):**
```python
from poker_solver.parity.noambrown_wrapper import (
    RiverSpot, BrownStrategyDump, BrownPlayerProfile, BrownInfosetEntry,
    CanonicalHistory,
    load_spots, find_brown_binary, write_brown_config, run_brown_solver,
    canonicalize_brown_history, canonicalize_our_history,
    our_strategy_to_brown_matrix,
)
```

**Fixture file path (Agent B + Agent C will load from):**
- `tests/data/river_spots.json` — accessed via `Path(__file__).resolve().parent.parent / "data" / "river_spots.json"` from test files.

**Schema invariant Agent B relies on:**
- `RiverSpot.ranges[i]` is `tuple[tuple[Combo, float], ...]` (immutable, hashable). Agent B parametrizes pytest tests by spot.id.

**Behavior guarantee for `canonicalize_brown_history(canonicalize_our_history(h))` round-trip:**
- For any well-formed river-only history (where our solver and Brown's solver took the same action sequence), the two canonicalizers must produce the **same** `CanonicalHistory` tuple. Agent C's `test_canonicalize_history_roundtrip` asserts this on ten hand-built histories.

## Critical correctness items

### 1. Raise encoding canonicalization (the load-bearing piece)

PR 7 spec §9 risk #1: Brown stores raises as **extra-beyond-call** (`cpp/src/river_game.cpp:88-93`, `cpp/src/main.cpp:193-194`); we store as **raise-to-total** (`poker_solver/hunl.py:391-401`). A bug here produces spurious diff failures.

**Both `canonicalize_*_history` functions normalize to the same form (raise-to-total).** Walk the tokens left-to-right with state (per-player contributions). For Brown's `r<extra>`:
- `actor_new_total = max(c0, c1) + extra`
- Emit `("r", actor_new_total)`.

For our `r<to_total>`:
- Emit `("r", to_total)` directly.

**Write parametric unit tests inline** (in the module-level docstring or a `if __name__ == "__main__":` block — NOT a separate test file; that's Agent C's territory). Round-trip ten hand-built histories. PR 7 spec §9 mitigation explicitly requires this.

### 2. ALL-IN token mapping

Brown does not have a special "all-in" token; it just emits the bet/raise amount (`cpp/src/river_game.cpp:63-66, 98-100`). Our `"A"` token (`poker_solver/hunl.py:377`) must be re-emitted as either:
- `("b", remaining_stack)` if `to_call == 0` at the moment of action (an opening all-in jam).
- `("r", actor_new_total)` if `to_call > 0` (all-in-as-raise; `actor_new_total = previous_max + remaining_after_call`).

Requires state-tracking inside `canonicalize_our_history`. Document the case-split clearly. PR 7 spec §5 step 5 sub-bullet 5.

### 3. Check ≡ call (no distinct `x`)

Brown emits `c` for both check and call (`cpp/src/main.cpp:182-186`). We emit `x` for check and `c` for call (`poker_solver/hunl.py:359, 367`). Both `x` and `c` map to `("c", 0)` in canonical form. Trivial but easy to forget.

### 4. Range-overlap-with-board filter

PR 7 spec §9 risk #7: hands containing a board card must be rejected by `load_spots`. Brown silently filters (`cpp/src/river_game.cpp:228-240`); we must explicitly reject with a clear error pointing at the offending spot id + hand. Don't silently filter — silent filtering masks fixture bugs.

### 5. Card-string convention

Brown's `cpp/src/cards.cpp` parses cards as `"<rank><suit>"` where rank ∈ `"23456789TJQKA"` and suit ∈ `"cdhs"` (verify in `cpp/src/cards.cpp` if needed). Our `Card.from_str()` expects the same; double-check. The fixture file uses lowercase suit (`"Ks"`, `"7h"` etc.) which matches both.

### 6. Subprocess hygiene (pytest-xdist safe)

Per PR 7 §9 risk #8: use `tempfile.NamedTemporaryFile(delete=False)` or `tempfile.mkdtemp()` per call; clean up in a `finally` block. Don't write to fixed `/tmp/spot_*.json` paths — that races under xdist.

### 7. Build script idempotency

`scripts/build_noambrown.sh`:
- If `cpp/build/river_solver_optimized` exists AND no `.cpp`/`.h` is newer → exit 0 with "up-to-date" message.
- If toolchain missing (`cmake` or `c++` not in PATH) → exit 0 with informative message.
- Otherwise → cmake configure + build in `cpp/build/`.
- Build invocation: `cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release && cmake --build "$BUILD" -j`.
- `set -euo pipefail` at top; explicit `chmod +x` not needed (created by `cmake`).

Use `bash` shebang explicitly (`#!/usr/bin/env bash`) so it works on macOS where `/bin/sh` is dash-compatible. Mark executable with `chmod +x` after writing (script self-bootstrap).

### 8. Fixture file content (you author 15 spots)

PR 7 spec §4 table:

| Category | Spots (board examples) |
|---|---|
| Dry rainbow | `Ks 7h 2d 4c Jh`, `Ah 8c 3d Tc 6s`, `Qh 5s 2c 9d 4h` |
| Wet rainbow | `Ts 9h 8d 5c 2h`, `Jh Tc 9d 4h 3s`, `8s 7h 6c 5d 2h` |
| Monotone | `As Ks 7s 4s 2c`, `Th 8h 5h 3h Jd`, `Qs Js 9s 4s 2h` |
| Paired | `Ah Ad 7c 4h 2s`, `Ks 7h 7d 4c 2h`, `Jh Tc Tc 5d 3s` |
| Broadway-heavy | `Ah Kh Qd Jc 2s`, `Ks Qc Jh Ts 4d`, `As Th Jc Qh Kd` |

Note: the spec mentions some boards like `"Jh Tc Tc 5d 3s"` (paired row) — verify uniqueness; if it's actually meant to be `"Jh Td Tc 5d 3s"`, fix and note in the report. Author each spot with:
- Boards: 5 cards, all distinct.
- Ranges: 30-60 combos per side, polarized OOP (P1) and condensed IP (P0). Recipe: 25% PFR vs 35% defend.
- Pot: 1000 (10 BB at `big_blind=100`).
- Stack: 9500 (95 BB behind).
- Bet sizes: `[0.75, 1.5]` for most spots; vary to test bet-set sensitivity on 2-3 spots.
- `include_all_in: true`, `max_raises: 3`.
- `iterations_override: null` (use default 2000).

File size budget: ~22 KB. Hard ceiling 100 KB.

### 9. MIT attribution (your module docstring)

Per PR 7 spec §8, the file header of `noambrown_wrapper.py` must include:

```python
"""Wrapper around Noam Brown's river_solver_optimized for differential testing.

This file invokes (via subprocess) and parses output from
`noambrown/poker_solver` (https://github.com/noambrown/poker_solver, MIT
Licensed, Copyright (c) 2025 Noam Brown). No source code from that repo
is copied here; this wrapper depends only on the public CLI flags and
JSON output format documented in:

  - references/code/noambrown_poker_solver/cpp/src/main.cpp (CLI flags)
  - references/code/noambrown_poker_solver/cpp/src/main.cpp:222-290 (output schema)
  - references/code/noambrown_poker_solver/LICENSE (MIT terms)

License of the wrapper itself: MIT (same as this project).
"""
```

PR 7 §8 explicitly mandates this exact-ish wording.

### 10. No code copied from Brown

You may DEPEND on Brown's CLI surface (`--algo`, `--iters`, `--dcfr-alpha/beta/gamma`, `--dump-strategy`, `--config`) and his JSON output schema — these are public interface, not licensed code. You may NOT copy from `cpp/src/*.cpp` files. If you find yourself wanting to "port the action_token function", stop — that's a copy; instead, document the semantics in `canonicalize_brown_history`'s docstring and implement from scratch.

## License-aware sourcing

**You may port architecturally (not code-copy) from MIT/Apache sources:**
- `references/code/noambrown_poker_solver/` (**MIT**) — read-only architectural inspiration. You invoke the binary; you do not copy source.
- `references/code/slumbot2019/` (**MIT**) — not directly relevant to PR 7, but available for future parity-wrapper patterns.

**You may NOT copy from AGPL sources:**
- `references/code/postflop-solver/`, `references/code/TexasSolver/` — **AGPL v3**. Not relevant to PR 7 either way.

**You may NOT extrapolate from training data.** If you "remember" how to invoke a CFR binary or parse a strategy dump, ground it in Brown's `main.cpp` and the local references. When in doubt, prefer the spec's stated approach.

If you copy a non-trivial code snippet (more than ~5 LOC) from an MIT-licensed source, add an attribution comment. For PR 7 the answer is: don't copy. The wrapper is original code reading a public schema.

## Quality bar

- **ruff clean:** `ruff check scripts/build_noambrown.sh poker_solver/parity/` reports zero issues. (For the bash script, this means: clean shellcheck-style if shellcheck is installed; otherwise ruff doesn't lint bash.)
- **black clean:** `black --check poker_solver/parity/` reports no changes needed.
- **mypy strict-clean on new code:** `mypy --strict poker_solver/parity/noambrown_wrapper.py poker_solver/parity/__init__.py` reports zero errors.
- **JSON fixture is valid:** `python -m json.tool tests/data/river_spots.json > /dev/null` exits 0.
- **Schema invariants hold:** every spot has 5 board cards, all distinct; every range has ≥30 combos; no hand overlaps with board.
- **Build script idempotency:** running `scripts/build_noambrown.sh` twice with no source changes only invokes cmake once (the second invocation prints "up-to-date" and exits 0).
- **Build script soft-fails:** running on a system without `cmake` exits 0 (NOT 1) with an informative message.
- **All 138+ existing tests still pass.** Your work is purely additive; no existing test should break. Run `pytest -x` to confirm.
- **Code size budget:** ~600-900 LOC for `noambrown_wrapper.py`; ~80 LOC for `build_noambrown.sh`; ~22 KB for `river_spots.json`. Stay within budget.

## Reference-first rule

Before any technical claim, citation, or formula, check the local references. Never extrapolate from training data when a local authoritative source exists. The reference index is `/Users/ashen/Desktop/poker_solver/references/README.md`.

If a fact is needed (e.g., "Brown emits `c` for both check and call"), cite `cpp/src/main.cpp:182-186`. If you need to know Brown's CLI flag set, cite `cpp/src/main.cpp:579-640` (or the usage block at `cpp/src/main.cpp:48-55`).

## Verification commands (run before reporting done)

```bash
cd /Users/ashen/Desktop/poker_solver

# 1. Lint + format
ruff check poker_solver/parity/
black --check poker_solver/parity/

# 2. Type-check
mypy --strict poker_solver/parity/noambrown_wrapper.py poker_solver/parity/__init__.py

# 3. JSON fixture validity
python -m json.tool tests/data/river_spots.json > /dev/null && echo "JSON valid"

# 4. Fixture loads cleanly + invariants hold
python -c "
from pathlib import Path
from poker_solver.parity.noambrown_wrapper import load_spots
spots = load_spots(Path('tests/data/river_spots.json'))
assert len(spots) == 15, f'expected 15 spots, got {len(spots)}'
for s in spots:
    assert len(s.board) == 5, f'{s.id}: board has {len(s.board)} cards, expected 5'
    assert len(set(s.board)) == 5, f'{s.id}: duplicate board cards'
    assert len(s.ranges[0]) >= 30, f'{s.id}: P0 range too small ({len(s.ranges[0])})'
    assert len(s.ranges[1]) >= 30, f'{s.id}: P1 range too small ({len(s.ranges[1])})'
    board_set = set(s.board)
    for player_range in s.ranges:
        for combo, _ in player_range:
            assert combo[0] not in board_set and combo[1] not in board_set, \
                f'{s.id}: hand {combo} overlaps board'
            assert combo[0] != combo[1], f'{s.id}: hand {combo} has duplicate cards'
print(f'fixture OK: {len(spots)} spots, ranges + board invariants hold')
"

# 5. Build script idempotency (first run — may build if toolchain present)
bash scripts/build_noambrown.sh
# 6. Build script idempotency (second run — must be no-op)
bash scripts/build_noambrown.sh 2>&1 | grep -i "up-to-date\|already" && echo "idempotency OK" || echo "WARN: second run did not detect up-to-date"

# 7. find_brown_binary returns Path or None
python -c "
from poker_solver.parity.noambrown_wrapper import find_brown_binary
b = find_brown_binary()
assert b is None or b.exists(), 'find_brown_binary lied'
print(f'binary: {b}')
"

# 8. Canonicalize round-trip on ten hand-built histories
python -c "
from poker_solver.parity.noambrown_wrapper import (
    canonicalize_brown_history, canonicalize_our_history,
)
# Brown-side hand-builds (river start; first action by P0):
brown_cases = [
    ('root', ()),
    ('c', (('c', 0),)),
    ('c/c', (('c', 0), ('c', 0))),
    ('b500', (('b', 500),)),
    ('b500/c', (('b', 500), ('c', 0))),
    ('b500/f', (('b', 500), ('f', 0))),
    # raise-extra=1000 after a bet=500: Brown stores 'r1000', actor's new total = 500 (bet) + 500 (call) + 1000 (extra) = 1500-ish; depends on pot start
    # We test the simpler ones first; spec'd 10 cases follow same shape
]
for token, expected in brown_cases:
    out = canonicalize_brown_history(token)
    assert out == expected, f'Brown {token!r}: got {out}, expected {expected}'
print('brown canonicalization OK')
"

# 9. Full test suite must still pass
pytest -x 2>&1 | tail -20
```

If any step fails, fix the issue before reporting done. If a smoke test reveals a spec ambiguity, **stop and flag it** — do not silently work around it.

## Report back format

When done, write a concise report (≤300 words) covering:

1. Files created with line counts (and the `river_spots.json` byte size).
2. Any spec amendment you made or contract drift you flagged (and why). Specifically:
   - Did you find any board with duplicate cards in PR 7 spec §4's listed spots (e.g., the paired `Jh Tc Tc 5d 3s` entry)?
   - Did the canonical binary path `cpp/build/` need clarification?
   - Did Brown's CLI accept the exact flags we documented (`--dcfr-beta 0` vs `--dcfr-beta 0.0`)?
3. Verification command output (paste tails).
4. Any open question you couldn't resolve from the spec / PLAN / autonomous log — flag for human review.
5. License attributions you added (module docstring + any cited file refs).
6. Confirmation that the build script soft-fails on a system without cmake (test on your dev box by temporarily masking `cmake` via `PATH=/usr/bin:/bin command ...` if you have one).
