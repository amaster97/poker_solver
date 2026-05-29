"""v1.11 Lever-A assessment — blueprint reach sparsity + sparse-prune correctness.

Answers two questions before committing engineering to sparse/lazy infoset storage:

  (2) NOTICEABLE IMPROVEMENT?  How concentrated is the blueprint-derived
      continuation reach? Memory/compute for the postflop solve scales with
      COMBO WIDTH. If only a small fraction of the ~1300 combos carry reach,
      sparse storage wins by ~(total_combos / active_combos).

  (1) WON'T BREAK CORRECTNESS/CONVERGENCE?  Does dropping near-zero-reach
      classes change the high-reach classes' strategy or the game value?
      We solve the SAME postflop spot two ways — full range vs reach-pruned
      range — and diff the shared classes' strategies + exploitability.
      (Theory: a combo's contribution to opponent regret / EV is weighted by
      its reach; reach=0 => provably inert; reach<eps => O(eps) bounded.)

Run on RIVER (cheap, completes within budget) so the correctness diff itself
does not OOM. The sparsity profile is solve-free.
"""

from __future__ import annotations

import sys

from poker_solver.blueprint import (
    BlueprintConfig,
    HandResolution,
    generate_blueprint,
    hunl_config_from_blueprint_config,
)
from poker_solver.blueprint_subgame import (
    derive_continuation_ranges_from_blueprint,
    solve_postflop_from_blueprint,
)
from poker_solver.card import Card

PREFLOP_SEQ = ("b300", "c")
FLOP = [Card.from_str(x) for x in ("Ad", "8h", "9d")]
TURN = Card.from_str("2c")
RIVER = Card.from_str("3s")


def combos_in_class(label: str) -> int:
    """169-class -> number of concrete combos. Pair=6, suited=4, offsuit=12."""
    if len(label) == 2 and label[0] == label[1]:
        return 6
    if label.endswith("s"):
        return 4
    if label.endswith("o"):
        return 12
    # Defensive: unknown label shape -> count as 12 (max) so we never
    # UNDER-state the full width.
    return 12


def profile(name: str, reach: dict) -> None:
    tot = sum(reach.values())
    items = sorted(reach.items(), key=lambda kv: -kv[1])
    n_classes = len(items)
    total_combos = sum(combos_in_class(c) for c, _ in items)
    print(f"\n  --- {name}: {n_classes} classes present, {total_combos} combos, total reach mass={tot:.4g} ---")
    print(f"  {'threshold':>10} | {'classes':>8} | {'combos':>7} | {'% reach mass':>12}")
    for thr in (0.0, 1e-12, 1e-9, 1e-6, 1e-3, 1e-2):
        active_classes = [c for c, w in items if w > thr]
        active_combos = sum(combos_in_class(c) for c in active_classes)
        mass = (sum(w for c, w in items if w > thr) / tot) if tot > 0 else 0.0
        print(f"  {thr:>10.0e} | {len(active_classes):>8} | {active_combos:>7} | {mass*100:>11.2f}%")
    # Compression ratio at the eps=1e-6 working threshold (combo level).
    active_combos_1e6 = sum(combos_in_class(c) for c, w in items if w > 1e-6)
    if active_combos_1e6 > 0:
        print(f"  >>> combo-width compression at reach>1e-6: {total_combos} -> {active_combos_1e6} "
              f"= {total_combos/active_combos_1e6:.1f}x potential memory/compute reduction")
    # Mass-capture concentration.
    cum = 0.0
    k99 = k999 = None
    for i, (_c, w) in enumerate(items, 1):
        cum += (w / tot) if tot > 0 else 0
        if k99 is None and cum >= 0.99:
            k99 = i
        if k999 is None and cum >= 0.999:
            k999 = i
    print(f"  >>> {k99} classes capture 99% of reach; {k999} capture 99.9% (of {n_classes})")


def main() -> int:
    cfg = BlueprintConfig(
        stack_bb=40, ante_bb=0.0, iterations=1500,
        preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
        preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
        preflop_raise_cap=4, small_blind_bb=0.5,
        alpha=1.5, beta=0.0, gamma=2.0,
    )
    print("[sparsity] generating 40 BB blueprint...", flush=True)
    bp = generate_blueprint(cfg, hand_resolution=HandResolution.CLASS_169)
    tmpl = hunl_config_from_blueprint_config(cfg)
    cont = derive_continuation_ranges_from_blueprint(
        bp, config_template=tmpl, action_sequence=PREFLOP_SEQ, hero_player=0
    )

    print("\n========== (2) SPARSITY PROFILE (J7o b300c line, 40 BB) ==========")
    profile("HERO", cont.hero)
    profile("VILLAIN", cont.villain)

    # ---- (1) Correctness: full vs reach-pruned solve on RIVER (light) ----
    print("\n========== (1) SPARSE-PRUNE CORRECTNESS DIFF (river, iters=200) ==========")
    eps = 1e-6
    hero_keep = [c for c, w in cont.hero.items() if w > eps]
    vill_keep = [c for c, w in cont.villain.items() if w > eps]
    print(f"  full hero={len(cont.hero)} villain={len(cont.villain)}; "
          f"pruned(reach>{eps:.0e}) hero={len(hero_keep)} villain={len(vill_keep)}", flush=True)

    def solve(hero_classes, villain_classes, tag):
        print(f"  solving river [{tag}]...", flush=True)
        return solve_postflop_from_blueprint(
            bp, config_template=tmpl, action_sequence=PREFLOP_SEQ,
            board=(FLOP[0], FLOP[1], FLOP[2], TURN, RIVER),
            hero_player=0, iterations=200,
            hero_classes=hero_classes, villain_classes=villain_classes,
            compute_exploitability_at_end=True,
        )

    full = solve(None, None, "full range")
    pruned = solve(hero_keep, vill_keep, f"pruned reach>{eps:.0e}")

    fs = dict(full.postflop.per_class_strategy)
    ps = dict(pruned.postflop.per_class_strategy)
    shared = set(fs) & set(ps)
    max_strat_diff = 0.0
    worst = None
    for k in shared:
        a, b = fs[k], ps[k]
        if isinstance(a, dict):
            for act in set(a) | set(b):
                d = abs(float(a.get(act, 0.0)) - float(b.get(act, 0.0)))
                if d > max_strat_diff:
                    max_strat_diff, worst = d, (k, act)
        else:
            for x, y in zip(a, b):
                d = abs(float(x) - float(y))
                if d > max_strat_diff:
                    max_strat_diff, worst = d, (k, None)
    expl_full = float(full.postflop.exploitability)
    expl_pruned = float(pruned.postflop.exploitability)
    print(f"\n  shared classes compared: {len(shared)}")
    print(f"  MAX strategy diff (full vs pruned): {max_strat_diff:.3e} at {worst}")
    print(f"  exploitability full   = {expl_full:.6e}")
    print(f"  exploitability pruned = {expl_pruned:.6e}")
    print(f"  exploitability |diff| = {abs(expl_full-expl_pruned):.3e}")
    verdict = "BIT-CLEAN (<1e-9)" if max_strat_diff < 1e-9 else (
        "eps-BOUNDED (matches pruning theory)" if max_strat_diff < 1e-3 else "INVESTIGATE")
    print(f"\n  CORRECTNESS VERDICT: max_strat_diff={max_strat_diff:.2e} -> {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
