"""Run the 6 preflop ratio experiments at 100 BB.

Each experiment varies open size AND reraise multiplier menus together,
crossed with ante on/off. Output is a markdown comparison report.

Engine: ``_rust.solve_hunl_preflop_rvr_class169`` (True Path B fast engine).
Iters: 2500 each. Wall time per experiment: ~0.5-2s.
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path

from poker_solver.blueprint import (
    CANONICAL_169_CLASSES,
    BlueprintConfig,
    HandResolution,
    generate_blueprint,
)

# ---------------------------------------------------------------------------
# 169-class combo weights (for combo-weighted aggregation across classes).
# ---------------------------------------------------------------------------


def _class_weight(label: str) -> int:
    """Number of concrete (suit-aware) combos that map to this class."""
    if len(label) == 2:  # pair, e.g. "AA"
        return 6
    suffix = label[-1]
    if suffix == "s":
        return 4
    if suffix == "o":
        return 12
    raise ValueError(f"unrecognized class label: {label!r}")


COMBO_WEIGHTS: dict[str, int] = {c: _class_weight(c) for c in CANONICAL_169_CLASSES}
TOTAL_COMBOS = sum(COMBO_WEIGHTS.values())
assert TOTAL_COMBOS == 1326

# A short spot-check list of 15 hands spanning premium/middling/trash, all
# 3 categories (pair, suited, offsuit).
SPOT_CHECK_HANDS = [
    "AA", "KK", "QQ", "TT", "55", "22",
    "AKs", "AQs", "T9s", "65s",
    "AKo", "KQo", "Q9o", "J8o", "72o",
]

# Premium suited connector / offsuit / weak set for the spot table also OK.


# ---------------------------------------------------------------------------
# Experiment specs.
# ---------------------------------------------------------------------------


def experiments() -> list[dict]:
    """Return the 6 experiment configs."""
    base = dict(
        stack_bb=100,
        iterations=2500,
        preflop_raise_cap=4,
        small_blind_bb=0.5,
    )
    return [
        {"name": "E1", "label": "no-ante open=2.5",
         "ante_bb": 0.0, "opens": (2.5,), "rerais": (2.5,)},
        {"name": "E2", "label": "no-ante open=5.0",
         "ante_bb": 0.0, "opens": (5.0,), "rerais": (5.0,)},
        {"name": "E3", "label": "no-ante both",
         "ante_bb": 0.0, "opens": (2.5, 5.0), "rerais": (2.5, 5.0)},
        {"name": "E4", "label": "ante open=2.5",
         "ante_bb": 1.0, "opens": (2.5,), "rerais": (2.5,)},
        {"name": "E5", "label": "ante open=5.0",
         "ante_bb": 1.0, "opens": (5.0,), "rerais": (5.0,)},
        {"name": "E6", "label": "ante both",
         "ante_bb": 1.0, "opens": (2.5, 5.0), "rerais": (2.5, 5.0)},
    ] if base else []  # keep typing happy


def build_config(spec: dict) -> BlueprintConfig:
    return BlueprintConfig(
        stack_bb=100,
        ante_bb=spec["ante_bb"],
        iterations=2500,
        preflop_open_sizes_bb=spec["opens"],
        preflop_reraise_multipliers=spec["rerais"],
        preflop_raise_cap=4,
        small_blind_bb=0.5,
    )


# ---------------------------------------------------------------------------
# Strategy aggregation helpers.
# ---------------------------------------------------------------------------


def aggregate_action_categories_at_infoset(
    actions: list[str], strategy: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    """Map each hand class's strategy vector into category mass.

    Categories returned:
        SB root: ``fold``, ``limp`` (=call), ``raise`` (sum of all opens incl all_in)
        BB facing SB open: ``fold``, ``call``, ``threebet`` (sum of raise_to_* + all_in)

    Also returns per-action-label mass under the key ``raw``.
    """
    out: dict[str, dict[str, float]] = {}
    for cls, probs in strategy.items():
        if len(probs) != len(actions):
            continue
        # Categorize: fold-like, call-like, raise-like (any open/raise/all_in).
        fold = 0.0
        call_or_check = 0.0
        raise_mass = 0.0
        per_label: dict[str, float] = {}
        for label, p in zip(actions, probs):
            per_label[label] = p
            if label == "fold":
                fold += p
            elif label in ("call", "check"):
                call_or_check += p
            elif label == "all_in" or label.startswith("open_to_") or label.startswith("raise_to_"):
                raise_mass += p
            else:
                # unknown — bucket into raise to be safe
                raise_mass += p
        out[cls] = {
            "fold": fold,
            "call": call_or_check,
            "raise": raise_mass,
            "raw": per_label,
        }
    return out


def combo_weighted_aggregate(per_class: dict[str, dict[str, float]],
                              keys: list[str]) -> dict[str, float]:
    """Aggregate per-class category mass into a single average across classes,
    weighted by combo count (so the answer is in 1326-combo space).

    ``keys`` lists which fields to average (e.g. ``["fold", "call", "raise"]``).
    """
    totals = {k: 0.0 for k in keys}
    weight_total = 0.0
    for cls, w in COMBO_WEIGHTS.items():
        if cls not in per_class:
            continue
        weight_total += w
        for k in keys:
            totals[k] += per_class[cls].get(k, 0.0) * w
    if weight_total <= 0:
        return {k: 0.0 for k in keys}
    return {k: totals[k] / weight_total for k in keys}


# ---------------------------------------------------------------------------
# Per-experiment analysis.
# ---------------------------------------------------------------------------


def analyze(bp_infosets: dict, opens: tuple, rerais: tuple,
            ante_bb: float, name: str) -> dict:
    """Extract SB-root and BB-vs-open aggregates and per-size breakdown."""
    root_key = "||p|"
    if root_key not in bp_infosets:
        raise RuntimeError(f"{name}: root infoset ||p| missing from blueprint")

    root = bp_infosets[root_key]
    root_actions = root["actions"]
    root_strategy = root["strategy"]
    root_categories = aggregate_action_categories_at_infoset(root_actions, root_strategy)
    sb_agg = combo_weighted_aggregate(root_categories, ["fold", "call", "raise"])

    # Per-open-size raise mass at SB root (for 2-size configs).
    # ``open_to_<X>`` actions: tally each separately.
    per_open_size_mass: dict[str, float] = {}
    for cls, w in COMBO_WEIGHTS.items():
        if cls not in root_categories:
            continue
        raw = root_categories[cls]["raw"]
        for label, p in raw.items():
            if label.startswith("open_to_") or label == "all_in":
                per_open_size_mass.setdefault(label, 0.0)
                per_open_size_mass[label] += p * w
    per_open_size_mass = {k: v / TOTAL_COMBOS for k, v in per_open_size_mass.items()}

    # Now for each SB open size, find the BB-facing-open infoset and aggregate.
    # The history key after SB opens to X is "||p|b<X>".
    # X = round(open_size_bb * 100) chips at chip_per_bb=100.
    bb_facing: dict[float, dict] = {}
    for open_bb in opens:
        x_chips = round(open_bb * 100)
        bb_key = f"||p|b{x_chips}"
        if bb_key not in bp_infosets:
            # Maybe engine didn't reach this history (shouldn't happen with 169-class)
            continue
        bb_info = bp_infosets[bb_key]
        bb_actions = bb_info["actions"]
        bb_strategy = bb_info["strategy"]
        bb_categories = aggregate_action_categories_at_infoset(bb_actions, bb_strategy)
        bb_agg = combo_weighted_aggregate(bb_categories, ["fold", "call", "raise"])

        # Per-3bet-size breakdown for this open.
        per_3bet_mass: dict[str, float] = {}
        for cls, w in COMBO_WEIGHTS.items():
            if cls not in bb_categories:
                continue
            raw = bb_categories[cls]["raw"]
            for label, p in raw.items():
                if label.startswith("raise_to_") or label == "all_in":
                    per_3bet_mass.setdefault(label, 0.0)
                    per_3bet_mass[label] += p * w
        per_3bet_mass = {k: v / TOTAL_COMBOS for k, v in per_3bet_mass.items()}

        bb_facing[open_bb] = {
            "agg": bb_agg,
            "per_3bet_label_mass": per_3bet_mass,
            "actions": bb_actions,
        }

    # Spot-check table: for each of 15 hands, dominant action at SB root + BB
    # (vs the smallest open size we have, which is the most common case).
    smallest_open = min(opens)
    smallest_open_x = round(smallest_open * 100)
    bb_key_small = f"||p|b{smallest_open_x}"
    bb_info_small = bp_infosets.get(bb_key_small, None)

    spot_rows: dict[str, dict[str, str]] = {}
    for hand in SPOT_CHECK_HANDS:
        if hand not in root_strategy:
            spot_rows[hand] = {"sb": "?", "bb": "?"}
            continue

        sb_cat = root_categories[hand]
        sb_dom = max(["fold", "call", "raise"], key=lambda k: sb_cat[k])
        sb_label_map = {"fold": "FOLD", "call": "LIMP", "raise": "RAISE"}
        sb_str = sb_label_map[sb_dom]

        bb_str = "?"
        if bb_info_small is not None:
            bb_strategy = bb_info_small["strategy"]
            bb_actions = bb_info_small["actions"]
            if hand in bb_strategy:
                bb_cats = aggregate_action_categories_at_infoset(bb_actions, bb_strategy)
                bb_cat = bb_cats[hand]
                bb_dom = max(["fold", "call", "raise"], key=lambda k: bb_cat[k])
                bb_label_map = {"fold": "FOLD", "call": "CALL", "raise": "3BET"}
                bb_str = bb_label_map[bb_dom]
        spot_rows[hand] = {"sb": sb_str, "bb": bb_str}

    return {
        "name": name,
        "ante_bb": ante_bb,
        "opens": opens,
        "sb_root": sb_agg,
        "per_open_size_mass": per_open_size_mass,
        "bb_facing": bb_facing,
        "spot": spot_rows,
        "n_infosets": len(bp_infosets),
    }


# ---------------------------------------------------------------------------
# Markdown rendering.
# ---------------------------------------------------------------------------


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def render_markdown(results: list[dict], wall_per: dict[str, float],
                     wall_total: float) -> str:
    """Render the comparison markdown."""
    by_name = {r["name"]: r for r in results}

    lines: list[str] = []
    lines.append("# Preflop 6-Experiment Ratio Comparison (2026-05-28)")
    lines.append("")
    lines.append("**Scope:** 6 preflop solves at 100 BB, raise cap = 4, 2500 iters each, "
                 "True Path B 169-class fast engine "
                 "(`_rust.solve_hunl_preflop_rvr_class169`).")
    lines.append("")
    lines.append("**Per-experiment menus:** open sizes (bb) and reraise multipliers "
                 "scale together — they share the same number in each config so the "
                 "ratio between bet level and raise increment is the experimental axis.")
    lines.append("")

    # Wall-time table.
    lines.append("## Wall time")
    lines.append("")
    lines.append("| Exp | Wall (s) | Menu | Ante |")
    lines.append("|-----|----------|------|------|")
    for r in results:
        wt = wall_per[r["name"]]
        opens_str = "/".join(f"{o}" for o in r["opens"])
        ante_str = f"{r['ante_bb']}bb" if r["ante_bb"] > 0 else "none"
        lines.append(f"| {r['name']} | {wt:.2f} | opens={opens_str} rerais={opens_str} | {ante_str} |")
    lines.append(f"| **total** | **{wall_total:.2f}** | | |")
    lines.append("")

    # --- Table 1: aggregates ---
    lines.append("## Table 1 — aggregates (combo-weighted across 1326 starting hands)")
    lines.append("")
    lines.append("```")
    lines.append("                  E1         E2         E3         E4         E5         E6")
    lines.append("                  no-ante    no-ante    no-ante    ante       ante       ante")
    lines.append("                  open=2.5   open=5.0   both       open=2.5   open=5.0   both")

    def row(label: str, key_path: tuple, sub_key: str) -> str:
        cells = []
        for name in ("E1", "E2", "E3", "E4", "E5", "E6"):
            r = by_name[name]
            d = r
            for kp in key_path:
                d = d[kp]
            v = d.get(sub_key, 0.0)
            cells.append(pct(v))
        return f"{label:<18}" + "  ".join(f"{c:>8}" for c in cells)

    lines.append(row("SB RFI fold",    ("sb_root",), "fold"))
    lines.append(row("SB RFI limp",    ("sb_root",), "call"))
    lines.append(row("SB RFI raise+",  ("sb_root",), "raise"))
    lines.append("")
    # BB stats: weighted average across the open sizes the SB actually used.
    # Use combo-weighted BB facing the SMALLEST open (most informative single
    # number), then we'll also show BB-vs-each-open in Table 2.
    bb_rows = []
    for name in ("E1", "E2", "E3", "E4", "E5", "E6"):
        r = by_name[name]
        # Weight BB aggregates by the SB's mass into each open.
        # P(open_to_X) at root → weight for the BB-vs-X infoset.
        total_w = 0.0
        accum = {"fold": 0.0, "call": 0.0, "raise": 0.0}
        for open_bb, bb_data in r["bb_facing"].items():
            x_chips = round(open_bb * 100)
            label = f"open_to_{x_chips}"
            w = r["per_open_size_mass"].get(label, 0.0)
            total_w += w
            for k in accum:
                accum[k] += bb_data["agg"][k] * w
        if total_w > 0:
            for k in accum:
                accum[k] /= total_w
        bb_rows.append(accum)
    lines.append(f"{'BB fold':<18}" + "  ".join(f"{pct(b['fold']):>8}" for b in bb_rows))
    lines.append(f"{'BB call':<18}" + "  ".join(f"{pct(b['call']):>8}" for b in bb_rows))
    lines.append(f"{'BB 3-bet+':<18}" + "  ".join(f"{pct(b['raise']):>8}" for b in bb_rows))
    lines.append("```")
    lines.append("")
    lines.append("*BB row is conditional on SB opening — averaged across the open "
                 "sizes weighted by how often SB chose each one.*")
    lines.append("")

    # --- Table 2: per-size breakdown for E3, E6 ---
    lines.append("## Engine convention note (matters for Table 2 labels)")
    lines.append("")
    lines.append("`bet_to = current_bet + multiplier × prev_bet` where "
                 "`prev_bet = max(last_bet_size, big_blind)` and `last_bet_size` is the "
                 "PREVIOUS raise INCREMENT, not the absolute bet. With ante=1bb, the BB "
                 "blind contribution is 2bb (= 1bb blind + 1bb ante), so SB's "
                 "open-to-2.5bb raises by 0.5bb (clamped to BB floor = 1bb), making the "
                 "BB's 3-bet increment SMALLER than in the no-ante case. This is why E6's "
                 "BB-facing-2.5bb-open 3-bet sizes (e.g. `raise_to_500` = 5.0bb) "
                 "differ from E3's (e.g. `raise_to_625` = 6.25bb).")
    lines.append("")
    lines.append("## Table 2 — size breakdown for the two-size configs (E3, E6)")
    lines.append("")
    lines.append("```")
    lines.append("                                       E3 (no ante)   E6 (ante)")

    for size_bb in (2.5, 5.0):
        x = round(size_bb * 100)
        label = f"open_to_{x}"
        e3_v = by_name["E3"]["per_open_size_mass"].get(label, 0.0)
        e6_v = by_name["E6"]["per_open_size_mass"].get(label, 0.0)
        lines.append(f"SB open {size_bb}bb mass               {pct(e3_v):>10}     {pct(e6_v):>10}")
    lines.append("")

    # BB 3-bet sizes vs each SB open size.
    # Engine convention: prev_bet = max(last_bet_size, big_blind); the ante
    # changes the BB pre-open contribution, which changes the SB's raise
    # increment. So no-ante and ante experiments emit DIFFERENT raise_to_*
    # labels for the same nominal multiplier. We extract labels from each
    # experiment's actual action list rather than predicting them.
    for sb_open in (2.5, 5.0):
        sb_x = round(sb_open * 100)
        lines.append(f"BB 3-bet+ vs SB's {sb_open}bb open")
        e3_bb = by_name["E3"]["bb_facing"].get(sb_open, None)
        e6_bb = by_name["E6"]["bb_facing"].get(sb_open, None)
        # Show every raise_to_* and all_in label the engine emitted.
        seen_labels: list[str] = []
        for bb_data in (e3_bb, e6_bb):
            if bb_data is None:
                continue
            for label in bb_data["actions"]:
                if (label.startswith("raise_to_") or label == "all_in") and label not in seen_labels:
                    seen_labels.append(label)
        for label in seen_labels:
            e3_v = 0.0 if e3_bb is None else e3_bb["per_3bet_label_mass"].get(label, 0.0)
            e6_v = 0.0 if e6_bb is None else e6_bb["per_3bet_label_mass"].get(label, 0.0)
            if label.startswith("raise_to_"):
                chips = int(label.split("_")[-1])
                disp = f"3-bet to {chips/100:.2f}bb ({label})"
            else:
                disp = "all-in"
            lines.append(f"  {disp:<38}  {pct(e3_v):>8}    {pct(e6_v):>8}")
        lines.append("")

    lines.append("```")
    lines.append("")

    # --- Spot-check table ---
    lines.append("## Spot-check table — dominant action by hand × experiment")
    lines.append("")
    lines.append("SB-row format: dominant action at the SB-RFI infoset "
                 "(`FOLD` / `LIMP` / `RAISE`). "
                 "BB-row format: dominant action at the BB-facing-smallest-open infoset "
                 "(`FOLD` / `CALL` / `3BET`).")
    lines.append("")
    lines.append("| Hand | E1 SB | E1 BB | E2 SB | E2 BB | E3 SB | E3 BB | E4 SB | E4 BB | E5 SB | E5 BB | E6 SB | E6 BB |")
    lines.append("|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|")
    for hand in SPOT_CHECK_HANDS:
        row = [f"`{hand}`"]
        for name in ("E1", "E2", "E3", "E4", "E5", "E6"):
            spot = by_name[name]["spot"][hand]
            row.append(spot["sb"])
            row.append(spot["bb"])
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


def main() -> None:
    specs = experiments()
    results: list[dict] = []
    wall_per: dict[str, float] = {}
    total_t0 = time.time()
    for spec in specs:
        cfg = build_config(spec)
        t0 = time.time()
        bp = generate_blueprint(cfg, hand_resolution=HandResolution.CLASS_169)
        wt = time.time() - t0
        wall_per[spec["name"]] = wt
        analysis = analyze(bp.infosets, spec["opens"], spec["rerais"],
                            spec["ante_bb"], spec["name"])
        results.append(analysis)
        print(f"{spec['name']} ({spec['label']}): {wt:.2f}s, "
              f"n_infosets={analysis['n_infosets']}, "
              f"SB fold={pct(analysis['sb_root']['fold'])}, "
              f"SB raise={pct(analysis['sb_root']['raise'])}")
    total_wt = time.time() - total_t0

    # Render markdown.
    md = render_markdown(results, wall_per, total_wt)

    # Append observations (computed on the fly).
    obs = []
    obs.append("## Observations\n")

    sb_folds = {r["name"]: r["sb_root"]["fold"] for r in results}
    sb_raises = {r["name"]: r["sb_root"]["raise"] for r in results}

    # Helper: BB fold from the bb_rows computation above. Re-compute.
    bb_folds: dict[str, float] = {}
    bb_raises: dict[str, float] = {}
    for r in results:
        total_w = 0.0
        accum = {"fold": 0.0, "raise": 0.0}
        for open_bb, bb_data in r["bb_facing"].items():
            x_chips = round(open_bb * 100)
            label = f"open_to_{x_chips}"
            w = r["per_open_size_mass"].get(label, 0.0)
            total_w += w
            for k in accum:
                accum[k] += bb_data["agg"][k] * w
        if total_w > 0:
            for k in accum:
                accum[k] /= total_w
        bb_folds[r["name"]] = accum["fold"]
        bb_raises[r["name"]] = accum["raise"]

    # Ante effect at fixed menu (E1→E4, E2→E5, E3→E6).
    ante_sb_delta_fold = [
        sb_folds["E4"] - sb_folds["E1"],
        sb_folds["E5"] - sb_folds["E2"],
        sb_folds["E6"] - sb_folds["E3"],
    ]
    ante_bb_delta_fold = [
        bb_folds["E4"] - bb_folds["E1"],
        bb_folds["E5"] - bb_folds["E2"],
        bb_folds["E6"] - bb_folds["E3"],
    ]
    obs.append("**Ante effect (pot-odds prediction: ante widens defense).** ")
    obs.append(f"At fixed menu, ante shifts SB-RFI fold by "
               f"{ante_sb_delta_fold[0]*100:+.1f}/{ante_sb_delta_fold[1]*100:+.1f}"
               f"/{ante_sb_delta_fold[2]*100:+.1f} pp (E4-E1, E5-E2, E6-E3) and "
               f"BB-facing-open fold by "
               f"{ante_bb_delta_fold[0]*100:+.1f}/{ante_bb_delta_fold[1]*100:+.1f}"
               f"/{ante_bb_delta_fold[2]*100:+.1f} pp. ")
    obs.append("Negative SB-fold delta = wider RFI when ante is present, consistent with "
               "pot-odds prediction.\n\n")

    # Menu freedom effect (E1 → E3 = add 5bb option; E2 → E3 = add 2.5bb option).
    obs.append("**Menu freedom (1 size → 2 sizes).** ")
    e1_e3_raise_delta = sb_raises["E3"] - sb_raises["E1"]
    e2_e3_raise_delta = sb_raises["E3"] - sb_raises["E2"]
    e4_e6_raise_delta = sb_raises["E6"] - sb_raises["E4"]
    e5_e6_raise_delta = sb_raises["E6"] - sb_raises["E5"]
    obs.append(f"SB total RAISE mass changes by E1→E3={e1_e3_raise_delta*100:+.1f}pp, "
               f"E2→E3={e2_e3_raise_delta*100:+.1f}pp, "
               f"E4→E6={e4_e6_raise_delta*100:+.1f}pp, "
               f"E5→E6={e5_e6_raise_delta*100:+.1f}pp. ")
    obs.append("If menu freedom merely splits existing raise mass across sizes, totals "
               "should stay close to a same-ante 1-size baseline; large changes would "
               "indicate the optimal raise-frequency itself moves when the strategy can "
               "mix sizes.\n\n")

    # Tightest / widest equilibrium.
    tightest = max(sb_folds, key=lambda k: sb_folds[k])
    widest = min(sb_folds, key=lambda k: sb_folds[k])
    obs.append(f"**Tightest SB equilibrium:** {tightest} (SB fold "
               f"{pct(sb_folds[tightest])}). ")
    obs.append(f"**Widest SB equilibrium:** {widest} (SB fold "
               f"{pct(sb_folds[widest])}).\n\n")

    # Symmetry: when SB plays wider, does BB also play wider?
    pairs = [(r["name"], sb_folds[r["name"]], bb_folds[r["name"]]) for r in results]
    # Correlation between SB fold and BB fold.
    n = len(pairs)
    mx = sum(p[1] for p in pairs) / n
    my = sum(p[2] for p in pairs) / n
    num = sum((p[1] - mx) * (p[2] - my) for p in pairs)
    dx = (sum((p[1] - mx) ** 2 for p in pairs)) ** 0.5
    dy = (sum((p[2] - my) ** 2 for p in pairs)) ** 0.5
    corr = num / (dx * dy) if dx > 0 and dy > 0 else 0.0
    obs.append(f"**SB/BB symmetry.** Pearson correlation between SB-RFI fold and "
               f"BB-vs-open fold across the 6 experiments: r={corr:+.2f}. ")
    obs.append("Positive r → when SB plays tighter (folds more), BB also plays tighter "
               "(folds more) — i.e. both players co-tighten when stack-to-pot is "
               "deeper relative to the bet size. Negative r → asymmetric.\n\n")

    # Caveats.
    obs.append("**Caveats.** 100bb-stack deep-cap solves have known Nash indifference "
               "manifolds (see project memory `feedback_nash_multiplicity_acceptance.md`); "
               "any single 2500-iter strategy is one realization on the manifold, not a "
               "unique equilibrium. Aggregate fold/raise rates are robust across "
               "realizations; per-class spot-check actions (especially close-to-indifferent "
               "hands like 22, 65s, T9s) may differ run-to-run within the same equilibrium "
               "class. The deltas BETWEEN experiments are still meaningful because the menu "
               "or ante change is the dominant signal compared to within-equilibrium drift.\n")

    md += "\n" + "".join(obs) + "\n"

    # Single-line summary for the report.
    summary_line = (
        f"\n## One-line summary\n\n"
        f"Wall: total {total_wt:.2f}s; "
        f"SB fold by exp E1-E6: "
        f"{pct(sb_folds['E1'])} / {pct(sb_folds['E2'])} / {pct(sb_folds['E3'])} / "
        f"{pct(sb_folds['E4'])} / {pct(sb_folds['E5'])} / {pct(sb_folds['E6'])}; "
        f"BB fold by exp E1-E6: "
        f"{pct(bb_folds['E1'])} / {pct(bb_folds['E2'])} / {pct(bb_folds['E3'])} / "
        f"{pct(bb_folds['E4'])} / {pct(bb_folds['E5'])} / {pct(bb_folds['E6'])}.\n"
    )
    md += summary_line

    # Write the markdown.
    out_path = Path(__file__).resolve().parent.parent / "docs" / "preflop_6_experiment_ratio_comparison_2026-05-28.md"
    out_path.write_text(md)
    print(f"\nWrote {out_path} ({len(md)} chars)")

    # Stash a JSON sidecar for downstream automation/auditing.
    side = {
        "wall_per": wall_per,
        "wall_total": total_wt,
        "sb_root_fold": sb_folds,
        "sb_root_raise": sb_raises,
        "bb_fold": bb_folds,
        "bb_raise": bb_raises,
        "per_open_size_mass": {r["name"]: r["per_open_size_mass"] for r in results},
        "iterations": 2500,
        "engine": "_rust.solve_hunl_preflop_rvr_class169",
    }
    side_path = out_path.with_suffix(".json")
    side_path.write_text(json.dumps(side, indent=2, sort_keys=True))
    print(f"Wrote {side_path}")


if __name__ == "__main__":
    main()
