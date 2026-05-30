"""Rung-2 postflop-EV table builder (Stage 1 PoC).

Replaces the rung-1 all-in *equity* leaf of the preflop blueprint with a
*postflop-EV* leaf. Today `build_equity_leaf_payoff` in
`crates/cfr_core/src/preflop_rvr.rs` (the Stage-2 swap point, around line 719)
values "going to the flop" as a single ALL-IN equity showdown read from
`assets/preflop_equity_169x169.npz` (169x169x3 win-equity suit variants). That
ignores postflop playability, position, and equity realization: suited
connectors and pocket pairs *over*-realize (sets, draws, pressure) while offsuit
broadways *under*-realize out of position. The rung-2 upgrade replaces the
equity scalar with a POSTFLOP-EV scalar per (hero_class, villain_class) computed
OFFLINE by actually SOLVING postflop subgames range-vs-range over representative
flops -- the same offline-amortization model as the equity table (solve once,
cache an `.npz`, load at runtime; zero runtime hot-path change). Mirrors
`preflop_equity::build_full_equity_table_parallel` + `save_equity_table`, but the
per-cell value is a postflop solve instead of a closed-form equity enumeration.

How the EV scalar is obtained (real binding surface)
----------------------------------------------------
The Rust postflop solver `poker_solver._rust.solve_range_vs_range_rust` (wrapped
by `poker_solver.range_aggregator.solve_range_vs_range_nash`) emits only the
average strategy. We recover hero's range-vs-range EV over ONLY the solved hands
via `_rust.compute_restricted_game_value` (added alongside this script): an
EV-only walk over the disjoint cross-product of hero/villain hole lists, NO
best-response passes. Its result dict is `{"game_value"}` = the expected value to
P0 under the supplied (Nash) profile -- hero's postflop EV in BB units, in the
ABSOLUTE pot-share base (a position-/equity-symmetric matchup -> pot/2;
QQ-vs-QQ on a flop -> pot/2, and `game_value(h,v) + game_value(v,h) == pot`).

Why NOT `compute_exploitability` (the bug this PR fixes)
-------------------------------------------------------
`compute_exploitability` on an `initial_hole_cards = ()` config takes the
chance-enum-root path, which enumerates ALL ~1.27M board-feasible flop combos
UNIFORMLY. The solved class-vs-class strategy only covers a few combos, so every
other combo falls back to the uniform strategy -- diluting hero's EV toward
pot/2 for EVERY cell. `compute_restricted_game_value` walks ONLY the solved
hands, recovering the true per-class EV.

Chip-base alignment for the sanity diff
---------------------------------------
`game_value` is the pot-share base. The rung-1 all-in equity in the SAME base is
`equity_share = eq * pot_bb` (eq=0.5 -> pot/2, matching QQ/QQ). The diff
`ev - equity_share` is then the equity-realization gap the upgrade captures.

NOTE on the equity-table layout: `preflop_equity_169x169.npz` stores
`equity[i,j,v]` as THREE SUIT-VARIANT orientations of hero WIN-EQUITY (each
channel is a full win-equity already in [0,1]; a win+1/2*tie rewrite does NOT
apply -- there is no separate tie channel, verified empirically: AA/KK reads
~0.81 across all three channels and AA/KK[ch0] + KK/AA[ch0] ~ 1.0). We use
variant 0 (the representative orientation; variant choice shifts equity <~1 pt).

STAGE 1 is a bounded PoC: a SMALL flop set at ONE pot/SPR bucket, modest
iterations, shallow stack. It builds + validates + documents the pipeline. It
does NOT wire the hot-path leaf swap (Stage 2, behind a `CFR_PREFLOP_EV_TABLE`
flag).

Run:
    python -u scripts/build_postflop_ev_table.py            # build + validate
    python -u scripts/build_postflop_ev_table.py --validate-only PATH.npz

Output: assets/preflop_postflop_ev_169x169_poc.npz
    ev:            (169,169) float64  postflop-EV scalar (hero pot-share EV, BB)
    equity_share:  (169,169) float64  all-in equity in the same pot-share base
    meta_*:        0-d scalars (pot, stack, sb, bb, n_flops, iterations)
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from poker_solver.card import Card, card_to_int  # noqa: E402
from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config  # noqa: E402
from poker_solver.range_aggregator import (  # noqa: E402
    _enumerate_combos,
    solve_range_vs_range_nash,
)

try:
    import poker_solver._rust as _rust  # noqa: E402
except ImportError:  # pragma: no cover
    _rust = None  # type: ignore[assignment]

NUM_CLASSES = 169
RANKS = "23456789TJQKA"

# Representative flop set, spanning textures. Kept SMALL (5 flops) per Stage-1
# scope. (name, "Rs Rs Rs").
POC_FLOPS: list[tuple[str, str]] = [
    ("dry_rainbow", "Kc 7h 2d"),
    ("wet_two_tone", "Th 9h 6s"),
    ("paired", "8c 8d 3h"),
    ("ace_high_dry", "Ac 8d 3s"),
    ("monotone_mid", "Jh 8h 4h"),
]

# ONE pot/SPR bucket. Chips are in cents (BB = 100c). Shallow stack keeps the
# postflop betting trees small/fast (this runs concurrently with another build
# -- stay memory-frugal). 6 BB pot split 300/300; 22 BB behind per player.
SB = 50
BB = 100
POC_POT = 600
POC_CONTRIB = (300, 300)
POC_STACK = 2500
POC_ITERS = 150
POC_BET_FRACTIONS = (0.5, 1.0)

# High-to-low rank order, mirroring `preflop_equity::RANKS_HIGH_TO_LOW`.
_R_HI2LO = [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]


def _decode(class_idx: int) -> tuple[int, int, bool]:
    """169-class index -> (rank_hi, rank_lo, suited). Mirrors the Rust
    `preflop_equity::class_decode` (pairs, then suited, then offsuit)."""
    if class_idx < 13:
        r = _R_HI2LO[class_idx]
        return r, r, False
    suited = class_idx < 13 + 78
    idx = class_idx - 13 if suited else class_idx - 13 - 78
    for a in range(12):
        row_len = 12 - a
        if idx < row_len:
            return _R_HI2LO[a], _R_HI2LO[a + 1 + idx], suited
        idx -= row_len
    raise ValueError(f"pair_idx out of bounds for class {class_idx}")


def _class_index(rank_hi: int, rank_lo: int, suited: bool) -> int:
    """(rank_hi, rank_lo, suited) -> 169-class index. Mirrors the Rust
    `preflop_equity::class_index`."""
    pos_hi = _R_HI2LO.index(rank_hi)
    pos_lo = _R_HI2LO.index(rank_lo)
    if rank_hi == rank_lo:
        return pos_hi
    a, b = (pos_hi, pos_lo) if pos_hi < pos_lo else (pos_lo, pos_hi)
    pair_idx = a * 12 - (a * (a - 1)) // 2 + (b - a - 1)
    return (13 if suited else 13 + 78) + pair_idx


def _hand_class_label(idx: int) -> str:
    """169-class index -> Pio-style label ('AA','AKs','72o')."""
    hi, lo, suited = _decode(idx)
    rh, rl = RANKS[hi - 2], RANKS[lo - 2]
    if hi == lo:
        return rh + rl
    return f"{rh}{rl}{'s' if suited else 'o'}"


def _build_config(board_str: str) -> HUNLConfig:
    board = tuple(Card.from_str(c) for c in board_str.split())
    return HUNLConfig(
        small_blind=SB,
        big_blind=BB,
        starting_stack=POC_STACK,
        starting_street=Street.FLOP,
        initial_board=board,
        initial_pot=POC_POT,
        initial_contributions=POC_CONTRIB,
        bet_size_fractions=POC_BET_FRACTIONS,
    )


def _restricted_holes(label: str, board_ints: set[int]) -> list[list[int]]:
    """Expand a hand-class label to its board-feasible hole pairs as
    `[c0, c1]` u8-int lists (the wire format `compute_restricted_game_value`
    expects), filtering out any combo using a board card."""
    holes: list[list[int]] = []
    for c0, c1 in _enumerate_combos(label):
        i0, i1 = card_to_int(c0), card_to_int(c1)
        if i0 in board_ints or i1 in board_ints:
            continue
        holes.append([i0, i1])
    return holes


def _cell_postflop_ev(cfg: HUNLConfig, cfg_json: str, board_ints: set[int],
                      hero_label: str, villain_label: str,
                      iters: int) -> float | None:
    """Solve one (hero_class)-vs-(villain_class) flop subgame and return hero's
    postflop EV in BB (`game_value`, pot-share base) over ONLY the solved hands,
    or None if the spot has no board-feasible combo on either side.

    Orientation: the solve uses `hero_player=0`, so hero combos are p0 and
    villain combos are p1; `compute_restricted_game_value` returns P0 (= hero)
    EV. We rebuild the SAME p0/p1 hole lists from the class labels (filtering
    board collisions) and restrict the EV walk to that cross-product -- the fix
    for the chance-enum-root uniform-dilution bug."""
    try:
        res = solve_range_vs_range_nash(
            cfg, [hero_label], [villain_label], iterations=iters,
            hero_player=0, compute_exploitability_at_end=False,
        )
    except ValueError:
        return None
    if not res.per_history_strategy:
        return None
    p0 = _restricted_holes(hero_label, board_ints)
    p1 = _restricted_holes(villain_label, board_ints)
    if not p0 or not p1:
        return None
    out = _rust.compute_restricted_game_value(cfg_json, res.per_history_strategy, p0, p1)
    return float(out["game_value"])


def build_postflop_ev_table(
    flops: list[tuple[str, str]],
    iters: int,
    classes: list[int] | None,
    progress: bool = True,
) -> np.ndarray:
    """Build the 169x169 postflop-EV table.

    For each (hero_class, villain_class) cell, solve the postflop subgame on
    every flop and average the per-flop EV (uniform across flops on which the
    spot is feasible). Returns a (169,169) float64 array of hero pot-share EV;
    cells outside `classes` (or with no feasible flop) stay NaN.
    """
    if _rust is None:
        raise RuntimeError("poker_solver._rust not built; run: maturin develop --release")
    rows = classes if classes is not None else list(range(NUM_CLASSES))
    table = np.full((NUM_CLASSES, NUM_CLASSES), np.nan, dtype=np.float64)

    flop_cfgs: list[tuple[HUNLConfig, str, set[int]]] = []
    for _name, board_str in flops:
        cfg = _build_config(board_str)
        cfg_json = _serialize_hunl_config(
            dataclasses.replace(cfg, initial_hole_cards=())
        )
        board_ints = {card_to_int(c) for c in cfg.initial_board}
        flop_cfgs.append((cfg, cfg_json, board_ints))
    labels = {i: _hand_class_label(i) for i in set(rows)}

    total = len(rows) * len(rows)
    done = 0
    t0 = time.perf_counter()
    for i in rows:
        for j in rows:
            evs: list[float] = []
            for cfg, cfg_json, board_ints in flop_cfgs:
                ev = _cell_postflop_ev(cfg, cfg_json, board_ints,
                                       labels[i], labels[j], iters)
                if ev is not None:
                    evs.append(ev)
            table[i, j] = float(np.mean(evs)) if evs else np.nan
            done += 1
            if progress and done % max(1, total // 10) == 0:
                dt = time.perf_counter() - t0
                sys.stdout.write(
                    f"  build {done}/{total} ({100.0 * done / total:.0f}%) {dt:.0f}s\n"
                )
                sys.stdout.flush()
    return table


def equity_share_table(pot_bb: float) -> np.ndarray:
    """All-in equity in the pot-share base (`eq * pot`), the same base as the
    postflop-EV scalar. The npz stores THREE SUIT-VARIANT orientations of hero
    WIN-EQUITY (NOT win/tie/loss -- there is no separate tie channel; each
    channel is already a full win-equity in [0,1]). We use variant 0 (the
    representative orientation; variant choice shifts equity <~1 pt). NaN
    entries (geometrically impossible class pairs) propagate."""
    d = np.load(os.path.join(os.path.dirname(__file__), "..", "assets",
                             "preflop_equity_169x169.npz"))
    eq = d["equity"][:, :, 0]
    return eq * pot_bb


def save_ev_table(path: str, ev: np.ndarray, equity_share: np.ndarray,
                  n_flops: int, iters: int) -> None:
    """Save the postflop-EV table to an `.npz`, mirroring
    `preflop_equity::save_equity_table`'s named-array layout plus metadata."""
    np.savez(
        path,
        ev=ev,
        equity_share=equity_share,
        meta_pot=np.float64(POC_POT),
        meta_stack=np.float64(POC_STACK),
        meta_sb=np.float64(SB),
        meta_bb=np.float64(BB),
        meta_n_flops=np.float64(n_flops),
        meta_iterations=np.float64(iters),
    )


def validate(path: str) -> int:
    """PoC validation gate. Returns 0 on PASS, nonzero on failure.

    (a) table loads, shape (169,169), computed cells finite;
    (b) SANITY: a position-/equity-symmetric self-matchup (QQ vs QQ) has
        postflop EV ~ pot/2, and the EV is pot-sum-consistent
        (ev[i,j] + ev[j,i] ~ pot);
    (c) DOMINANCE: a known playability/dominance matchup -- AA vs 72o -- must
        have hero EV clearly ABOVE pot/2 (a real solve favours the crusher; a
        degenerate uniform-dilution table would read ~pot/2 here too);
    (d) SUBSTANTIVE SPREAD: the computed-cell EV spread must be large
        (> 0.25 BB), not the near-constant dilution a chance-enum-root walk
        produces.

    HARD-FAILs (exit 2) on a degenerate/placeholder core: a real rung-2 table
    MUST vary substantively by matchup and must reward dominance, so a
    shape+finiteness check alone (or a tiny `spread > 1e-3`) would silently
    bless a constant/diluted table (a silent-no-op).
    """
    d = np.load(path, allow_pickle=False)
    ev = d["ev"]
    share = d["equity_share"]
    pot_bb = float(d["meta_pot"]) / float(d["meta_bb"])
    print(f"loaded {path}")
    print(f"  ev.shape={ev.shape}  equity_share.shape={share.shape}  "
          f"pot={float(d['meta_pot'])}c ({pot_bb:.1f} BB) "
          f"stack={float(d['meta_stack'])}c iters={int(d['meta_iterations'])} "
          f"flops={int(d['meta_n_flops'])}")

    if ev.shape != (NUM_CLASSES, NUM_CLASSES):
        print(f"FAIL: ev shape {ev.shape} != (169,169)")
        return 1
    computed = ~np.isnan(ev)
    n = int(computed.sum())
    print(f"  computed cells: {n}")
    if n == 0:
        print("FAIL: no cells computed")
        return 1
    if not np.isfinite(ev[computed]).all():
        print("FAIL: non-finite values among computed cells")
        return 1

    qq = _class_index(12, 12, False)

    def row(name: str, h: int, v: int) -> None:
        e = share[h, v]
        p = ev[h, v]
        print(f"  {name:>11} | equity_share={e:7.3f}  postflop_ev={p:7.3f}  "
              f"realization_gap={p - e:+7.3f}")

    print("\n-- sanity: equity-symmetric self-matchup (expect postflop_ev ~ pot/2) --")
    qq_self = float(ev[qq, qq])
    print(f"  QQ vs QQ postflop_ev = {qq_self:.4f}  (pot/2 = {pot_bb / 2:.4f})")
    sym_ok = abs(qq_self - pot_bb / 2) < 0.05

    print("\n-- pot-sum check: ev[i,j] + ev[j,i] ~ pot on off-diagonal cells --")
    pairs = [(_class_index(14, 14, False), _class_index(13, 13, False)),  # AA/KK
             (_class_index(5, 4, True), _class_index(14, 11, False))]     # 76s/AJo
    sum_ok = True
    for a, b in pairs:
        if np.isnan(ev[a, b]) or np.isnan(ev[b, a]):
            continue
        s = float(ev[a, b] + ev[b, a])
        print(f"  ev[{_hand_class_label(a)},{_hand_class_label(b)}]={ev[a, b]:.4f}"
              f"  ev[reverse]={ev[b, a]:.4f}  sum={s:.4f}")
        sum_ok = sum_ok and abs(s - pot_bb) < 0.1

    print("\n-- dominance: AA vs 72o (expect postflop_ev clearly ABOVE pot/2) --")
    aa = _class_index(14, 14, False)
    s72o = _class_index(7, 2, False)
    row("AA vs 72o", aa, s72o)
    aa_72o = ev[aa, s72o]
    dom_ok = (not np.isnan(aa_72o)) and float(aa_72o) > pot_bb / 2 + 0.5
    if np.isnan(aa_72o):
        print("  (AA vs 72o not computed -- include both classes in the PoC subset)")

    print("\n-- premium vs premium (expect postflop_ev ~ ballpark of equity share) --")
    row("AA vs KK", _class_index(14, 14, False), _class_index(13, 13, False))
    row("KK vs QQ", _class_index(13, 13, False), _class_index(12, 12, False))

    print("\n-- playability-sensitive (expect equity share vs postflop_ev DIVERGE) --")
    row("76s vs AJo", _class_index(5, 4, True), _class_index(14, 11, False))
    row("54s vs KQo", _class_index(3, 2, True), _class_index(13, 12, False))
    row("T9s vs AQo", _class_index(8, 7, True), _class_index(14, 12, False))

    spread = float(ev[computed].max() - ev[computed].min())
    print(f"\n  postflop_ev spread over computed cells = {spread:.6f}")
    spread_ok = spread > 0.25

    if not spread_ok:
        print(f"FAIL (degenerate): postflop_ev spread {spread:.4f} <= 0.25 BB. "
              "A real rung-2 table varies substantively by matchup; this looks "
              "like the uniform chance-enum-root dilution (every cell ~ pot/2).")
        return 2
    if not dom_ok:
        print(f"FAIL (degenerate): AA vs 72o postflop_ev {float(aa_72o):.4f} is "
              f"not clearly above pot/2 {pot_bb / 2:.4f}. A real solve rewards a "
              "dominating hand; a diluted table reads ~pot/2 everywhere.")
        return 2
    if not sym_ok:
        print(f"FAIL: symmetric self-matchup EV {qq_self:.4f} not ~ pot/2 "
              f"{pot_bb / 2:.4f} (broken symmetry).")
        return 1
    if not sum_ok:
        print("FAIL: pot-sum residual too large (broken P0/P1 EV symmetry).")
        return 1

    print("\nPASS: shape/finiteness OK, symmetric self-matchup ~ pot/2, "
          "pot-sum consistent, AA-vs-72o dominance rewarded, and postflop_ev "
          "varies substantively by matchup.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build/validate the rung-2 postflop-EV table (Stage 1 PoC).")
    ap.add_argument("--out", default=None, help="output .npz path")
    ap.add_argument("--validate-only", default=None, metavar="NPZ",
                    help="skip build; validate an existing table")
    ap.add_argument("--full", action="store_true",
                    help="compute all 169x169 cells (slow); default is a bounded PoC subset")
    ap.add_argument("--i-understand-this-is-slow", action="store_true",
                    help="required confirmation for --full (169^2 x 5 solves)")
    ap.add_argument("--iters", type=int, default=POC_ITERS)
    args = ap.parse_args()

    if args.validate_only:
        sys.exit(validate(args.validate_only))

    if args.full and not args.i_understand_this_is_slow:
        print("REFUSING --full without --i-understand-this-is-slow: a full "
              "169x169 build is 28,561 cells x 5 flops = ~142,805 postflop "
              "solves and can take hours. Re-run with both flags if you really "
              "mean it.", file=sys.stderr)
        sys.exit(1)

    if _rust is None:
        print("poker_solver._rust not built; run: maturin develop --release",
              file=sys.stderr)
        sys.exit(1)

    out = args.out or os.path.join(
        os.path.dirname(__file__), "..", "assets",
        "preflop_postflop_ev_169x169_poc.npz",
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)

    classes: list[int] | None
    if args.full:
        classes = None
    else:
        # Bounded PoC subset: premiums, broadways, suited connectors, offsuit.
        wanted = [
            _class_index(14, 14, False), _class_index(13, 13, False),
            _class_index(12, 12, False),                              # AA KK QQ
            _class_index(14, 13, True), _class_index(14, 13, False),  # AKs AKo
            _class_index(5, 4, True), _class_index(3, 2, True),
            _class_index(8, 7, True),                                 # 76s 54s T9s
            _class_index(14, 11, False), _class_index(13, 12, False),
            _class_index(14, 12, False),                              # AJo KQo AQo
            _class_index(7, 2, False),                                # 72o
        ]
        classes = sorted(set(wanted))

    pot_bb = POC_POT / BB
    print(f"building postflop-EV table: {len(POC_FLOPS)} flops, "
          f"pot={POC_POT}c ({pot_bb:.1f} BB) stack={POC_STACK}c "
          f"iters={args.iters} bets={POC_BET_FRACTIONS}")
    print(f"  classes: {'all 169' if classes is None else len(classes)}")
    sys.stdout.flush()

    t0 = time.perf_counter()
    ev = build_postflop_ev_table(POC_FLOPS, args.iters, classes)
    share = equity_share_table(pot_bb)
    save_ev_table(out, ev, share, len(POC_FLOPS), args.iters)
    print(f"wrote {out} in {time.perf_counter() - t0:.0f}s")

    sys.exit(validate(out))


if __name__ == "__main__":
    main()
