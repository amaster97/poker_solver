# Off-path handling (preflop + postflop)

This is the reference for the solver's **off-path detection and cleaning** —
the read-layer that hides CFR's untrained "phantom" strategies so charts, the
API, the CLI, and chained solves never surface a meaningless action at a node
a hand never actually reaches.

- **Preflop API:** `poker_solver/preflop_offpath.py`
- **Postflop API:** `poker_solver/postflop_offpath.py`
- **Read-layer accessors:** `RangeVsRangeNashResult.per_history_strategy_view`
  (`poker_solver/range_aggregator.py`), `strategy_table`
  (`poker_solver/preflop_offpath.py`)
- **CLI:** the `chained` subcommand (`poker_solver/cli.py`), opt-out via
  `--raw-offpath`
- **GUI:** the preflop chart (`ui/views/preflop_chart.py`) greys off-path cells

---

## The problem

CFR (and DCFR) assigns a strategy to **every** decision node in the game tree,
including nodes a hand reaches with ≈ 0 probability. Regret at an unreached
node is never trained, so the stored "strategy" there is leftover noise — not a
recommendation. Dumping it verbatim produces confusing output:

- **Preflop.** On a 4-bet line `||p|b200r400r1000`, the engine still stores a
  strategy row for `82s` and `A3o` — hands that folded (or flat-called and
  closed the action) long before the 4-bet. The chart would otherwise show
  "`82s` raises 100% facing a 4-bet," which is meaningless: `82s` is never in
  range there.
- **Postflop.** A combo that **folded the flop** still has a strategy row
  stored at river nodes (the engine materializes the full tree). Reading it
  back shows "this hand bets the river" for a hand that is gone — pure noise.

Off-path handling detects these nodes and, on the read layer, overwrites them
to a pure fold so consumers see a clean, on-path-only strategy.

---

## Detection rules

A hand/combo is off-path at a node when **either** rule fires:

1. **Reach rule.** Its normalized reach across the node's hands/combos is below
   the threshold (**0.5%** of the total reach mass at that node).
2. **Dominance rule.** It is *dominantly blocked* (≥ **99%**) at one of the
   **displayed/hero player's own** ancestor decision nodes on the line. Only
   the acting player's own decisions gate their reach; the opponent's actions
   *define* the line but do not enter the product.

Both signals come from a **single walk** per hand/combo. The walk is
**FAIL-SAFE**: if it can't be fully computed for *any* hand on a line (a prior
node missing, e.g. a partial live snapshot, or a token that can't be resolved),
**nothing** is marked off-path for that line — the read layer never invents a
fold from incomplete data.

### Preflop specifics — size-agnostic reach

Reach is computed by walking the displayed player's own ancestor decisions and
multiplying in their continuing-action probabilities. At a **bet/raise**
ancestor the walk credits the hand's **total aggression mass** (summed over
*every* bet/raise size label at that node), **not** just the single size the
line happened to take.

This is a deliberate fix. Blueprint raise nodes offer multiple sizes (e.g. the
BB's 3-bet menu at `||p|b300` is `r600 / r700 / r900`). A premium like **AA**
3-bets ~98% but puts almost all of that on one size (say `r900`, with
P(`r700`) ≈ 0.006). Reading only the single matched size returned ~0 reach and
**falsely greyed AA** on a sibling-size line. Crediting total aggression mass
fixes this: a hand that raised by *any* size took the aggressive action and is
in this branch. Call/limp (`c`) and all-in (`A`) stay exact — they are single,
unambiguous actions.

### Postflop specifics — per-combo, board-aware, street-by-street

The postflop solver emits a per-`(history, concrete-combo)` strategy, so
detection is **per combo**:

- **Reach** = `hero_range_weight[combo] × Π P_continue` over the hero's own
  ancestor decisions. Same size-agnostic principle as preflop (a hero bet/raise
  ancestor credits total aggression mass over all sizes).
- **Board-aware.** A combo whose hole card is on the board has reach 0 and is
  off-path (a blocked combo can't be in range).
- **Street-by-street.** `folded` and `all_in` carry **across** streets (a hand
  that folded the flop is gone for good). The passive closes
  (`checked_closed` / `called_closed`) are scoped **strictly within a street** —
  a check that closed the flop legitimately continues to the turn; it only
  off-paths a *later same-street* hero decision.

---

## Reason taxonomy

Both modules expose a reason-aware variant (`mark_off_path_with_reason`) that
returns `None` for on-path hands or one of the codes below. When several could
apply at the same ancestor, per-node priority is
`folded > all_in > checked_closed > called_closed`, and any dominant block
always outranks the generic low-reach rule.

| Reason | Meaning | Carries across streets? |
|---|---|---|
| `folded` | Fold ≥ 99% at an ancestor — every deeper action is off-path. | Yes |
| `all_in` | All-in ≥ 99% at an ancestor — no voluntary action after committing the stack, so it carries onto every deeper line. | Yes |
| `checked_closed` (postflop only) | A check that closed the street's betting at an ancestor, where the line then has the hero act again **on the same street** ("supposed to check 100% here, but the line has us acting again — treat as a fold"). | No (within-street) |
| `called_closed` | A flat-call that closed the action at an ancestor where the line then continues with further aggression — it can't face the later re-raise (the preflop A3o/K3s case: BB flat-calls the open 100%, off-path on the 4-bet line). | Preflop: at the call ancestor; postflop: within-street |
| `low_reach` | Generic: normalized reach below 0.5% with no single dominating ancestor (also the reason for board-blocked postflop combos). | — |

> **Why `all_in` matters.** Before the all-in rule, only fold was checked, so an
> all-in-dominant hand was wrongly left in-range on a size-raise continuation.
> All-in mass is read from the exact all-in label and is **never** summed into
> the bet/raise aggregation.

---

## Default-on behavior

Off-path cleaning is **on by default** everywhere a human or downstream tool
reads a strategy back out:

- **GUI preflop chart** (`ui/views/preflop_chart.py`) — off-path cells render
  greyed with an em-dash (`—`), faded, and a **reason-aware tooltip**:

  | Reason | Tooltip |
  |---|---|
  | `all_in` | `<hand> — not in range on this line (already all-in earlier)` |
  | `folded` | `<hand> — not in range on this line (folded earlier on this line)` |
  | `called_closed` | `<hand> — not in range on this line (called & closed action earlier)` |
  | `low_reach` / other | `<hand> — not in range on this line (doesn't reach this line; reach ≈ 0%)` |

- **Preflop API** — `strategy_table(average_strategy)` returns the cleaned
  per-line table (`clean=True` by default).
- **Postflop API** — `RangeVsRangeNashResult.per_history_strategy_view()`
  returns the cleaned per-history view (`clean=True` by default).
- **CLI** — the `chained` subcommand's JSON output is off-path-cleaned by
  default.
- **Chained solves** — each per-street postflop subgame is a
  `RangeVsRangeNashResult`, so it inherits the default-on
  `per_history_strategy_view` accessor.

**Cleaned** means each off-path row is overwritten to a pure fold: the preflop
fold label is forced to 1.0 (everything else 0.0); the postflop row's index 0
(the passive/give-up action) is forced to 1.0 (rest 0.0).

### Postflop GUI coverage — current state

To set expectations precisely:

- The **data layer** (postflop API / CLI / chained solves) cleans off-path by
  **default**.
- The **postflop tree browser** is already **reach-filtered** (node-aggregate),
  so it does not surface unreachable nodes.
- The **postflop range-matrix GUI does *not* yet grey off-path cells** — the
  per-combo greying the preflop chart has is not wired into the postflop
  matrix. Read the cleaned data via the API/CLI for now.

---

## Raw escape hatches

The raw engine output is available whenever you need it (diffing, debugging,
exploitability checks):

| Layer | Raw opt-out |
|---|---|
| Preflop API | `strategy_table(average_strategy, clean=False)` |
| Postflop API | `result.per_history_strategy_view(clean=False)` |
| CLI (`chained`) | `--raw-offpath` |

---

## Invariant: the raw engine output is never mutated

This is the central safety property. The cleaning functions
(`clean_off_path`, `strategy_table`, `per_history_strategy_view`) all operate on
a **freshly built / deep-copied** structure and **never** touch the raw engine
output:

- `RangeVsRangeNashResult.per_history_strategy` (the attribute) is never
  mutated, regardless of `clean`.
- The raw preflop `average_strategy` mapping passed into `strategy_table` is
  never mutated.

The raw strategy stays the **source of truth** consumed by exploitability
computation, blueprint generation, and differential tests — those read the
untrained-but-complete strategy directly. Off-path cleaning is a *read-layer
presentation* concern, not an engine change.

---

## Convergence caveat

Off-path detection keys on near-deterministic dominance (≥ 99% fold/all-in/
passive-close) and a small reach threshold. On **low-iteration live solves**,
near-indifferent hands at the deepest nodes have not fully separated, so the
detector can **over-grey** a hand that is genuinely close to a boundary. This is
**under-convergence, not a bug** — run more iterations and it cleans up.
Production blueprints (solved at 25,000 DCFR iterations) are clean. If you see
unexpected greying on a quick live solve, re-check at higher iterations before
suspecting the off-path logic.

---

## Examples

### Preflop — cleaned strategy table

```python
from poker_solver.preflop_offpath import strategy_table

# rust_out is the result of a preflop range-vs-range solve.
average_strategy = rust_out["average_strategy"]

# Cleaned by default: off-path entries (folded / all-in / called-closed /
# low-reach) are overwritten to a pure fold.
table = strategy_table(average_strategy)            # clean=True
# table[line][hand_class][action_label] -> probability
# e.g. table["||p|b200r400r1000"]["82s"] == {"fold": 1.0, ...}

# Raw projection — keep the untrained off-path noise intact:
raw = strategy_table(average_strategy, clean=False)
```

### Postflop — cleaned per-history view

```python
from poker_solver.range_aggregator import solve_range_vs_range_nash

result = solve_range_vs_range_nash(cfg, hero_range, villain_range,
                                   iterations=500, hero_player=1)

# Cleaned by default. Hero is OOP when the solve reports the defender seat;
# pass hero_is_oop explicitly to match your seat convention.
view = result.per_history_strategy_view(hero_is_oop=(result.position == "defender"))
# view[infoset_key] -> positional probability list, off-path rows folded
# (index 0 == 1.0). Board-blocked combos and folded/all-in/closed lines
# are removed.

# Raw rows (a per-row copy of the unmutated attribute):
raw = result.per_history_strategy_view(clean=False)

# The raw attribute itself is always available and never mutated:
result.per_history_strategy  # source of truth for exploitability / diff-tests
```

### CLI — clean (default) vs raw

```bash
# Default: chained JSON output is off-path-cleaned (folded / all-in /
# closed lines and board-blocked combos are overwritten to fold).
poker-solver chained --hero-range "AA,KK,AKs" --villain-range "QQ,JJ,AKs" \
    --board "Ad 8h 9d" --lazy-postflop > chained_clean.json

# Opt out: emit the RAW postflop per_history_strategy (every combo at every
# node, off-path rows included).
poker-solver chained --hero-range "AA,KK,AKs" --villain-range "QQ,JJ,AKs" \
    --board "Ad 8h 9d" --lazy-postflop --raw-offpath > chained_raw.json
```

---

## Related

- `USAGE.md` §5.7 documents an older, complementary reach-annotation feature
  (`SolveResult.off_path_keys` / `reach_probability`) on the scalar postflop
  solve path — a *set of unreachable infoset keys*, not the per-line/per-combo
  fold-cleaning described here.
- `docs/AGENT_COORDINATION.md` §3e tracks the (now low-priority, optional)
  engine-side "bake off-path→fold into blueprint generation" ask — superseded
  for read-time purposes by the read-layer cleaning described here.
