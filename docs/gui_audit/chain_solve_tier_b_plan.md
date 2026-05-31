# Chain-Solve Tier B — Turn/River Walkthrough: Implementation Plan

Extends the chain-solve hole-card walkthrough (`docs/gui_audit/chain_solve_b_plan.md`,
shipped Tier A) from **preflop → flop** to **preflop → flop → turn → river**.

Design only. Evidence-based read of `ui/views/chained_tab.py`, `ui/state.py`,
`poker_solver/chained.py`, `poker_solver/range_aggregator.py`, `poker_solver/hunl.py`
at shipped `a9e92ea`. **No engine/UI code is changed by this doc.** The engine track
owns `poker_solver/chained.py` and the postflop solver; Sections 3 + 6 are the
**coordination ask** for that track.

---

## 0. Current state (what Tier A actually shipped)

The walkthrough is a stepper state machine over `solve_chained` (`ChainedSolveResult`).
Transient state lives on `SolveRunner` as `_wt_*` attrs, accessed via the helpers in
`chained_tab.py`:

| attr | type | meaning |
|---|---|---|
| `_wt_hero_combo` | `(Card, Card) \| None` | hero's two hole cards |
| `_wt_tokens` | `tuple[str, ...]` | preflop action tokens walked so far |
| `_wt_step` | `"preflop"\|"flop"\|"turn"\|"river"\|"done"` | current street |
| `_wt_flop` | `list[Card]` | the 3 flop cards |

Render dispatch (`_render_right_pane`, lines 740-750):

- `preflop` → `_render_preflop_step` — legal-action walk, class-level rec bars
  (`result.query(hero_cls, board=None)`), 13×13 matrix; advance tokens until a
  flop-reaching terminal (`tokens in result.continuation_ranges`) or fold.
- `flop` → `_render_flop_step` — 3-card board picker → `result.query(hero_cls, tokens,
  board_tuple)` (lazily fires `solve_postflop` → `solve_range_vs_range_nash` on
  `starting_street=FLOP`) → flop rec bars + route badge.
- `turn` / `river` → **`_render_pending_step`** — a static "pending fast engine"
  placeholder, **no compute** (chained_tab.py:1326). This is the wall Tier B removes.
- `done` → `_render_termination` — fold/preflop-end summary.

The flop step ends with a hard-coded line — *"Turn / river are not yet chained on this
engine"* (chained_tab.py:1313) — and a `Turn (pending) ->` button that only flips
`_wt_step` to `"turn"` (no solve). Tier B replaces both the pending placeholder and that
banner with real turn/river steps.

### What the engine supports today (the hard boundary)

- **`ChainedSolveResult.solve_postflop` is flop-only by assertion.** It raises
  `ValueError` for `len(board) != 3` — *"Phase A only supports flop subgames"*
  (chained.py:335-339). There is **no flop→turn or turn→river chaining** in
  `chained.py`, and no derivation helper that turns a postflop solve + a chosen
  postflop action into the next street's continuation ranges. (`_derive_continuation_ranges`
  exists only for the **preflop→flop** frontier; grep confirms no postflop analogue.)
- **The underlying vector solver already supports turn + river boards.**
  `solve_range_vs_range_nash` accepts any `starting_street >= FLOP` (it rejects only
  `PREFLOP`, range_aggregator.py:1066) and any `initial_board` of length 4 (turn) or 5
  (river) — `_TURN_SUBGAME` / `_RIVER_SUBGAME` fixtures across the test suite drive it
  with `starting_street=Street.TURN`/`Street.RIVER` directly. So **the engine primitive
  for solving a standalone turn or river subgame already exists**; what is missing is the
  *chaining glue* that derives the turn-entry (and river-entry) ranges + pot from the
  prior street's solve + the chosen action.
- **All strategy is CLASS-level, not combo-level** (chained.py:1024-1028 passes sorted
  class keys, uniform combo weighting). `AhKh` is solved as `AKs`; board interaction
  (a flush draw on a two-heart flop) is NOT modeled. This limitation carries forward
  unchanged to turn/river — see Section 5.

### The standalone subgame contract (what an engine call needs)

`_run_postflop_subgame` (chained.py:990-1038) is the template. To solve a postflop street
the engine builds a `HUNLConfig` via `replace(config_template, ...)` and calls
`solve_range_vs_range_nash`:

```
postflop_cfg = replace(
    config_template,
    starting_street = Street.FLOP,            # → TURN (board len 4) / RIVER (board len 5)
    initial_board   = tuple(board),           # 3 / 4 / 5 cards
    initial_pot     = pot_chips,              # grown each street
    initial_contributions = (pot//2, pot//2), # matched/symmetric threading
    initial_hole_cards = (),
)
solve_range_vs_range_nash(
    postflop_cfg,
    hero_range = sorted(continuation.hero.keys()),     # class labels
    villain_range = sorted(continuation.villain.keys()),
    iterations = postflop_iterations,
    hero_player = hero_player,
    compute_exploitability_at_end = False,
)
```

`Street` maps board length → street (hunl.py:68-87: `FLOP=1`/3 cards, `TURN=2`/+1,
`RIVER=3`/+1). So a turn subgame is exactly the flop call with `starting_street=TURN`,
a 4-card board, the grown pot, and the **post-flop-action continuation ranges**. The only
genuinely new thing Tier B needs is **deriving those post-action ranges + grown pot** —
the rest is the same call with a longer board.

---

## 1. UI extension (turn + river steps)

Mirror the existing flop step (`_render_flop_step`) as closely as possible — same panel
shape, same card-picker, same rec bars, same route badge. The walkthrough already lists
`turn`/`river` in `_WT_STREETS` and the stepper already renders chips for them, so the UI
surface is mostly *promoting the disabled placeholders to live steps*.

### 1.1 New render functions

- **`_render_turn_step(state, refresh_after_change)`** — replaces the `turn` branch
  (currently `_render_pending_step`). Structure copied from `_render_flop_step`:
  1. **Flop-action sub-step (new):** before a turn card can be dealt, the hero (and
     villain) must have *acted on the flop*. The flop rec is already shown; Tier B adds a
     **flop-action picker** — the legal flop actions for hero's class + a villain-action
     picker (same pattern as the preflop `_legal_action_options` / `_pick` buttons, but
     reading the *postflop* legal-action set from a flop `HUNLPoker` walk, not the preflop
     game). The chosen flop-action token(s) append to a new `_wt_flop_tokens` tuple.
  2. **Turn card picker:** `_card_grid(..., cap=1, marker_prefix="chained-tab-turn-cell")`
     — exclude hole cards + the 3 flop cards (extend the existing `_toggle_flop`
     collision check). Stored in a new `_wt_turn` (`list[Card]`, len 0/1).
  3. **Turn strategy panel:** once a turn card is picked, call the engine's turn-chaining
     entry (Section 3) and render hero's class-level turn rec via the existing
     `_render_freq_bars`. Header mirrors `chained-tab-flop-header`: *"{class} on
     {flop+turn board} after {preflop line} / {flop action}"* using `board_html` +
     `format_action_sequence`.
  4. **Advance:** a `Deal the river ->` button (live, not pending) that records the
     turn action token(s) into `_wt_turn_tokens` and flips `_wt_step` to `"river"`.

- **`_render_river_step(state, refresh_after_change)`** — replaces the `river` branch.
  Identical shape to the turn step, one street deeper:
  1. **Turn-action sub-step** (pick hero/villain turn actions → `_wt_turn_tokens`).
  2. **River card picker** (`cap=1`, `marker_prefix="chained-tab-river-cell"`, exclude
     hole + 4 board cards) → `_wt_river` (`list[Card]`).
  3. **River strategy panel** (class-level river rec bars; board is now 5 cards).
  4. **Terminal:** the river is the last street — no "deal next"; instead a
     `See hand summary ->` button → `_wt_step = "done"`. `_render_termination` is
     extended (Section 1.3) to show the full preflop→river line.

### 1.2 New `_wt_*` state (transient, on `SolveRunner`, same pattern as Tier A)

Add accessor pairs mirroring `_wt_flop`/`_set_wt_flop`:

| attr | type | meaning |
|---|---|---|
| `_wt_flop_tokens` | `tuple[str, ...]` | postflop action tokens taken on the flop |
| `_wt_turn` | `list[Card]` | the 1 turn card |
| `_wt_turn_tokens` | `tuple[str, ...]` | action tokens taken on the turn |
| `_wt_river` | `list[Card]` | the 1 river card |

These are **GUI-orchestration state only** — they describe the chosen line; the engine
consumes them to build each subgame (Section 3). No engine state is mutated.

### 1.3 Stepper, pickers, summary (reuse, do NOT rebuild)

- **Stepper (`_render_stepper`):** today `reached_flop` is the only gate; `turn`/`river`
  chips are always `disable`d (lines 967-993). Extend the reachability logic:
  `reached_turn = _wt_step in ("turn","river","done") and len(_wt_flop)==3 and bool(_wt_flop_tokens)`;
  `reached_river = ... and len(_wt_turn)==1 and bool(_wt_turn_tokens)`. Gate each chip's
  `opacity`/`disable` + the `_go` rewind handler (turn rewind clears `_wt_turn*`/`_wt_river`;
  river rewind clears `_wt_river`). Keep the existing `chained-tab-step-{street}` markers.
- **Card pickers:** reuse `_card_grid` verbatim with `cap=1` and new marker prefixes
  (`chained-tab-turn-cell-{card}`, `chained-tab-river-cell-{card}`). The collision guard
  in the `on_toggle` closure must exclude hole cards **and all earlier board cards**
  (flop for the turn picker; flop+turn for the river picker) — extend the existing
  `_toggle_flop` pattern.
- **Action pickers:** reuse the preflop `_legal_action_options` + `_pick` button pattern
  (lines 1142-1152), but walked against a **postflop** `HUNLPoker` (built like
  `_build_walk_game` but `starting_street=FLOP/TURN`, `initial_board` = the dealt board,
  `initial_pot`/`initial_contributions` threaded from the prior street). Tokens reuse the
  same `_last_token`/`token_label` alphabet (`x`/`b{N}`/`r{N}`/`c`/`f`/`A`).
- **Rec bars:** reuse `_render_freq_bars` (street-agnostic; already used preflop + flop).
- **Route badge:** set `runner.chained_postflop_route_info` to a `RouteInfo(LIVE, ...)`
  with a per-street confidence string (e.g. `"live turn subgame"`), same as the flop step
  (chained_tab.py:1286-1292). Optionally add per-street badges, but one rolling postflop
  badge is sufficient and avoids new markers.
- **Termination (`_render_termination`):** extend to print the full chained line — preflop
  tokens, flop board + flop action, turn card + turn action, river card — and the per-street
  recs walked. Reuse `format_action_sequence` + `board_html`.

### 1.4 New ElementFilter markers (for smoke tests)

```
chained-tab-turn-picker            turn card picker container
chained-tab-turn-cell-{card}       per-card turn picker button
chained-tab-river-picker           river card picker container
chained-tab-river-cell-{card}      per-card river picker button
chained-tab-turn-header            "{cls} on {board} after {line}" (turn)
chained-tab-river-header           same (river)
chained-tab-legal-action-deal_river   advance button (turn → river)
chained-tab-legal-action-summary      advance button (river → done)  [exists]
```

Retire `chained-tab-pending-engine` (the placeholder marker) and the
*"Turn / river are not yet chained"* banner once both steps are live. Update the
module docstring's marker list + the smoke-test asserts in the same PR.

---

## 2. Data flow / chaining

The walkthrough threads a growing **line** (action history) + **board** + **continuation
ranges** + **pot/contributions** forward, street by street. The critical correctness rule
(carried from Tier A): **thread pot/contributions explicitly through the chain — never
reconstruct the spot via `_spot_from_config`** (see Risk R1).

```
preflop solve (solve_chained)
   └─ continuation_ranges[preflop_tokens] = ContinuationRanges{hero, villain, pot_chips}
        │  (already derived by _derive_continuation_ranges)
        ▼
flop subgame  (board = _wt_flop, len 3)
   solve_range_vs_range_nash(starting_street=FLOP, board, pot=pot_chips, ranges=cont.hero/villain)
   user picks _wt_flop_tokens (hero + villain flop actions)
        │  → NEW: derive turn-entry {hero, villain} ranges + grown pot
        ▼
turn subgame  (board = _wt_flop + _wt_turn, len 4)
   solve_range_vs_range_nash(starting_street=TURN, board, pot=pot_after_flop, ranges=turn-entry)
   user picks _wt_turn_tokens
        │  → NEW: derive river-entry {hero, villain} ranges + grown pot
        ▼
river subgame (board = _wt_flop + _wt_turn + _wt_river, len 5)
   solve_range_vs_range_nash(starting_street=RIVER, board, pot=pot_after_turn, ranges=river-entry)
   → river rec → done
```

### 2.1 What threads through each hop

- **Board:** monotonic append. Flop (3) → +turn (4) → +river (5). The GUI owns the cards
  (`_wt_flop`/`_wt_turn`/`_wt_river`); the engine receives `tuple(board)`.
- **Line / action history:** `(_wt_tokens, _wt_flop_tokens, _wt_turn_tokens)` — the
  preflop line plus the chosen postflop actions per street. The engine needs the *postflop*
  action tokens to (a) identify which decision-tree node the next street starts from and
  (b) grow the pot.
- **Continuation ranges (narrowed by prior streets):** each postflop solve produces a
  `per_history_strategy`; given a chosen action at the street's decision node, the
  surviving hands + their reach weights define the next street's entry ranges. **This
  reach-propagation does not exist for postflop today** — it is the core engine ask
  (Section 3). At class granularity, the entry range may simply be "the same class set,
  re-weighted (or unchanged) by the action taken," but the *pot* and *board* must still
  advance.
- **Pot / contributions / SPR:** the pot grows by the chosen postflop action's chips.
  `_run_postflop_subgame` currently splits the pot symmetrically (`(pot//2, pot//2)`,
  chained.py:1012-1013) — fine for a check-through line, but a **bet/call on the flop
  changes the pot for the turn**, and a bet that is *not yet called* makes contributions
  *asymmetric*. The engine must compute the post-action pot + contributions (the
  `HUNLState.contributions` after applying the flop action tokens, exactly as
  `_derive_continuation_ranges` reads `terminal_state.contributions`, chained.py:903) and
  thread them into the turn config. SPR correctness depends entirely on this — a dropped
  or symmetric-assumed pot understates/overstates SPR and silently corrupts the turn/river
  strategy.

### 2.2 Why not `_spot_from_config`

`_spot_from_config` (spot_input.py:1628) rebuilds a `Spot` from a `HUNLConfig` but **drops
`initial_pot` and `initial_contributions`** — it carries only board, stacks, blinds, ante,
bet sizes, ranges (lines 1641-1686). A turn/river subgame routed through a `Spot`
round-trip would therefore lose the accumulated pot and fall back to `to_hunl_config`'s
**2×BB token pot** (state.py:670-671) — wrong SPR, wrong strategy. The chained path already
sidesteps this by threading `pot_chips` in `ContinuationRanges` straight into `replace()`.
**Tier B must keep that discipline:** the turn/river pot comes from the prior street's
post-action `HUNLState.contributions`, threaded engine-side, **not** from any `Spot`.

---

## 3. Engine-call contract — the coordination ask for the engine track

> **This section is the ask for the engine track** (they own `chained.py` + the postflop
> solver). The GUI cannot chain turn/river without one of the two options below. Preferred:
> **Option A** (engine owns chaining; GUI stays a thin renderer).

### Option A (preferred) — extend `ChainedSolveResult` with street-chaining methods

Add postflop-continuation derivation + per-street solve entry points so the GUI passes a
*line* and gets back a per-street solve, with the engine owning all pot/range threading.

Desired signatures (illustrative — engine track owns the final shape):

```python
class ChainedSolveResult:
    def solve_turn(
        self,
        preflop_seq: PreflopActionSequence,
        flop_board: BoardTuple,        # len 3
        flop_actions: tuple[str, ...], # postflop tokens taken on the flop
        turn_card: Card,
    ) -> RangeVsRangeNashResult:
        """Solve the turn subgame: derive turn-entry {hero,villain} ranges +
        grown pot from the cached flop solve + flop_actions, build a
        starting_street=TURN config (board = flop_board + turn_card, len 4),
        and call solve_range_vs_range_nash. Cache by
        (preflop_seq, canonical(flop_board), flop_actions, turn_card)."""

    def solve_river(
        self,
        preflop_seq, flop_board, flop_actions,
        turn_card, turn_actions: tuple[str, ...],
        river_card: Card,
    ) -> RangeVsRangeNashResult:
        """Same, one street deeper. board len 5, starting_street=RIVER."""
```

- **Return:** the existing `RangeVsRangeNashResult` (the GUI already projects
  `per_class_strategy` via `result.query` / `project_postflop`; no new return type needed).
- **Caching:** extend the LRU `postflop_cache` key from `(action_sequence, canonical_board)`
  to also carry the postflop action history + the new street card(s), so suit-iso boards
  still collapse but distinct lines/run-outs don't collide.
- **New internal helper (the real work):** a `_derive_postflop_continuation(prev_result,
  prev_board, actions, hero_player) -> (hero_ranges, villain_ranges, pot_chips,
  contributions)` analogous to `_derive_continuation_ranges` but propagating reach through
  the **postflop** `per_history_strategy` and reading the post-action
  `HUNLState.contributions` for the grown pot. **This is the piece that does not exist
  today.** At class granularity it may degenerate to "carry the class set forward,
  advance pot/board," but the pot/contributions threading is mandatory.
- **`query(...)` extension:** optionally let `query(hero_cls, line, board)` accept a 4- or
  5-card board + the postflop action history and dispatch to `solve_turn`/`solve_river`,
  so the GUI render path stays the single `result.query(...)` call it is today.

### Option B (fallback) — GUI orchestrates per-street subgame solves

If the engine track defers Option A, the GUI calls `solve_range_vs_range_nash` directly per
street (the primitive already supports turn/river boards). But then the **GUI** must own
the continuation-range + pot derivation that Option A keeps engine-side — duplicating the
reach-propagation + contribution-threading logic in `chained_tab.py`. This is **strongly
dispreferred**: it pushes solver-domain correctness (SPR/pot threading, reach propagation,
suit-iso caching) into the view layer and risks divergence from `chained.py`'s own
derivation. If chosen, the GUI must still read post-action `HUNLState.contributions` (build
a postflop `HUNLPoker`, walk the chosen tokens, read `state.contributions`) and must NOT
route through `_spot_from_config`.

**Recommendation:** Option A. The GUI change then reduces to: new pickers, new `_wt_*`
state, new render branches, and swapping the `_render_pending_step` calls for
`result.solve_turn(...)` / `result.solve_river(...)` behind the existing `result.query`
façade.

---

## 4. Performance dependency

**Tier B rides on the engine track's in-flight flop-solver perf work.** Chaining three
streets of live solves multiplies the per-street cost, and the per-street cost is currently
the bottleneck:

- The flop subgame is `solve_range_vs_range_nash`, **synchronous on the UI thread**
  (chained_tab.py renders it inline in `_render_flop_step`), cost `O(hand_count² ×
  decision_nodes)` per iteration. The engine's own docstring warns **"Flop and turn may
  still be slow"** (range_aggregator.py:1013-1016) — the `TerminalCache` helps the river
  most (constant board) but flop/turn retain the chance-branching + O(N²) hand-pair shape.
- Memory note (MEMORY): a **100BB full-range flop is memory-bound and minutes-scale**;
  full-range flop is ~6.7GB+ and only abstraction/depth-limiting bends it.
- Tier B compounds this: a flop solve **and** a turn solve **and** a river solve, each
  fired interactively as the user deals cards. Even if each is "interactive" alone, the
  user experiences them in sequence; a multi-minute flop solve makes the whole walkthrough
  unusable.

**Quantification is required before shipping** (per the "don't extrapolate" rule — do not
claim a chained latency from single-street numbers): once the engine track lands its flop
perf work, **measure** per-street wall time for the chained turn + river solves at
representative widths and instrument each street, rather than extrapolating from the flop
number.

**Usable envelope (to validate empirically, not assume):**

- **Range width** is the dominant lever (O(N²) hands). Narrow class lists (the walkthrough's
  default `"AA, KK, QQ, AKs, AKo"` ≈ 5 classes) chain comfortably; full ~169-class ranges
  do not until the perf work lands.
- **Stack depth:** shallow/mid (≤ ~40BB) keeps the betting tree (and the raise sub-tree —
  the dominant per-street multiplier, ~6^cap) bounded; 100BB-full is the memory wall.
- **Iterations:** the chained postflop default is 500 (state.py:2568). Note that
  postflop subgames need convergence-grade iters for non-degenerate dominated-hand EVs
  (MEMORY: postflop convergence); chaining at low iters per street risks compounding
  under-convergence. The turn/river iteration budget should be a tunable, surfaced like the
  preflop-iters input.

**Mitigations to design in (not block on):**

- **Async/off-thread postflop solves** + the existing progress/cancel hooks, so a
  long turn/river solve doesn't freeze the tab (Tier A's flop solve is synchronous;
  Tier B should not stack three synchronous solves on the UI thread). This is also called
  out as a Tier-B item in the chain-solve "b" plan.
- **Per-street caching** (the engine's LRU `postflop_cache`, extended per Section 3) so
  re-walking a line is O(1).
- **Width guard / guidance** in the UI (narrow-ranges hint) if a street's solve would be
  intractable — consistent with the "no refusal/patchup" rule, this is *guidance*, not a
  hard refusal: the solve still runs once the engine can handle it.

---

## 5. Honesty / scope

Keep the existing **class-level only** banner (chained_tab.py:472-479) accurate and visible
on the turn/river steps too. Tier B does **not** change the granularity.

**What Tier B models:**
- The full preflop → flop → turn → river decision chain at **class granularity** (RvR).
- Per-street GTO recs for the hero's *class* given the dealt board + the chosen line.
- Correct pot/SPR growth across streets (via engine-threaded contributions — Section 2).

**What Tier B does NOT model:**
- **Per-combo board-aware strategy.** `AhKh` is still treated as `AKs`; a flush draw on a
  two-heart board, a specific blocker, a backdoor — none are reflected. The class-level
  banner must stay on every street. (Per-combo board-aware play remains a later engine.)
- **Asymmetric stacks** (`to_hunl_config` collapses to P0's stack, state.py:612-617) — out
  of scope, inherited.
- **Rake** (`solve_chained` rejects non-zero rake, chained.py:481-485) — inherited.
- **All-in / fold lines past the flop:** preflop all-in / fold terminals are already
  excluded from `continuation_ranges` (chained.py:863-869, collapse to equity). The
  postflop chaining must terminate gracefully on a postflop fold or all-in run-out (no
  further street to walk) — route to `_render_termination`, not a crashed solve.

The Tier A honesty banner wording stays; add a short per-street note on the turn/river
panels reaffirming class-level (reuse the existing italic-fainter style).

---

## 6. Open questions / risks for the engine track

- **R1 — Pot/SPR threading (highest correctness risk).** The turn/river pot + contributions
  must come from the prior street's post-action `HUNLState.contributions`, threaded
  engine-side. **Do NOT reconstruct via `_spot_from_config`** (drops pot/contributions →
  2×BB token pot → wrong SPR). `_run_postflop_subgame`'s current **symmetric** `(pot//2,
  pot//2)` split (chained.py:1012-1013) is only correct for matched (checked/called) lines;
  a bet-not-yet-called line is **asymmetric** and must be threaded as such (the engine
  already supports asymmetric `initial_contributions`, hunl.py:165-186). **Engine ask:**
  confirm the post-action contribution derivation and the asymmetric-pot path for chained
  turn/river.

- **R2 — Postflop continuation-range derivation does not exist.** There is a
  `_derive_continuation_ranges` for **preflop→flop** only. Chaining flop→turn→river needs
  the postflop analogue (reach propagation through `per_history_strategy` given a chosen
  postflop action). **Engine ask:** own this in `chained.py` (Option A). At class
  granularity, define whether the entry range is the carried class set (re-weighted or
  unchanged) — and how a fold/all-in postflop action terminates the chain.

- **R3 — Performance / convergence.** Will a chained flop+turn+river be interactive at the
  walkthrough's default widths once the flop perf work lands? Needs **measured** per-street
  latency at representative widths (not extrapolated). What iteration budget per street
  balances convergence (dominated-hand EVs) against latency? Should postflop solves run
  off-thread with progress/cancel?

- **R4 — Caching key.** Extending `postflop_cache` to carry the postflop action history +
  street cards (Section 3) — does suit-iso board collapse still hold once the board is 4/5
  cards with a chosen run-out? Confirm the canonical-board key (`_canonicalize_board`)
  behaves for turn/river boards.

- **R5 — Villain action handling on postflop streets.** Tier A's preflop walk lets the user
  pick villain actions to advance. For postflop, does the walkthrough let the user pick
  villain's flop/turn action, or auto-advance villain by its modal strategy? (Mirrors the
  Tier A open question #3, now per-street.) Affects which decision node the next street
  starts from and thus the derived continuation ranges.

- **R6 — Marker / test churn.** Retiring `chained-tab-pending-engine` + the "not yet
  chained" banner breaks the smoke tests that assert them; update the module docstring +
  `tests/test_ui_chained_tab.py` in the same PR (mirror the Tier A Smoke-4 rework).

---

## 7. Build order (when the engine ask lands)

1. **Engine (track-owned, gating):** Option A methods (`solve_turn`/`solve_river`) +
   `_derive_postflop_continuation` + pot/contribution threading (R1, R2) + cache key (R4).
2. **GUI state:** add `_wt_flop_tokens`/`_wt_turn`/`_wt_turn_tokens`/`_wt_river` accessors.
3. **GUI turn step:** flop-action picker → turn card picker → `result.solve_turn(...)` →
   rec bars → `Deal the river ->`.
4. **GUI river step:** turn-action picker → river card picker → `result.solve_river(...)`
   → rec bars → `See hand summary ->`.
5. **Stepper + termination:** extend reachability gating + the full-line summary.
6. **Honesty:** carry the class-level banner onto turn/river panels.
7. **Tests:** extend `tests/test_ui_chained_tab.py` (turn/river pickers, advance, solve
   fired, class-level note present); retire pending-placeholder asserts.
8. **Perf:** measure + instrument per-street chained latency at default widths (R3);
   add off-thread + cancel if needed.

Critical files: `ui/views/chained_tab.py`, `poker_solver/chained.py` (engine-owned),
`poker_solver/range_aggregator.py` (solver primitive), `ui/state.py`,
`tests/test_ui_chained_tab.py`. Reference: `docs/gui_audit/chain_solve_b_plan.md` (Tier A).
