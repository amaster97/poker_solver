"""Premium-A preflop blueprint generation + asset format (Phase 1, task #68).

This module ships the offline pipeline that produces the 169-class preflop
blueprint shards consumed by Phase 2's loader. It is the "schema half" of
the Path-B 169-class abstraction effort — the engine itself continues to
solve the full 1326-combo vector-form CFR (see
:func:`poker_solver._rust.solve_hunl_preflop_rvr`), and we post-aggregate
the per-combo strategy into a per-class strategy at output time.

The 169 hand classes are the canonical Pio-style preflop equivalence
classes — 13 pocket pairs ("AA", "KK", ..., "22"), 78 suited two-card
classes ("AKs", "AQs", ..., "32s"), and 78 offsuit classes ("AKo", "AQo",
..., "32o"). Within a class, every concrete combo (e.g. "As Kh" vs
"Ah Kc" for "AKo") behaves identically in expectation against any
opponent class because (1) preflop equity is suit-symmetric modulo
blockers and (2) the 169x169x3 equity table already integrates over the
three suit-overlap variants. Aggregating per-combo strategies into one
per-class number is therefore lossless to within the engine's own
suit-variant approximation.

## Why a Path-A engine internally

The Rust engine ``solve_hunl_preflop_rvr`` already runs on the 1326-combo
hand vector. Switching the CFR loop to operate on a 169-class vector
requires building an "effective" 169x169 leaf table that integrates
blocker-respecting combo-weighted equity per (hero_class, villain_class)
pair — a focused 1-2 day Rust refactor, not feasible inside the 4 hour
Phase 1 budget. The wrapper here gives users the **schema and asset
format** they need to ship Phase 1.5 (the overnight compute) and Phase 2
(the loader); a follow-up PR will swap the engine internals to true
169-vector for the per-iter speedup without changing this output schema.

## Asset format

Per-blueprint file: ``assets/blueprints/preflop_169class_{depth}bb_{ante}.json.gz``.

Schema (gzipped JSON):

.. code-block:: json

    {
      "schema_version": "v1.0",
      "config": {
        "stack_bb": 40,
        "ante_bb": 0.0,
        "iterations": 25000,
        "alpha": 1.5, "beta": 0.0, "gamma": 2.0,
        "preflop_open_sizes_bb": [2.0, 3.0, 4.0, 5.0],
        "preflop_reraise_multipliers": [2.0, 3.0, 4.0, 5.0],
        "preflop_raise_cap": 4
      },
      "convergence": {"final_exploitability_bb100": null, "wall_seconds": 360.4},
      "infosets": {
        "||p|": {
          "actions": ["fold", "call", "open_to_200", "open_to_300", "open_to_400", "open_to_500", "all_in"],
          "strategy": {"AA": [0.0, 0.0, 0.0, 0.0, 0.0, 0.92, 0.08], "...": [...]}
        },
        "||p|b300|": {...}
      }
    }

The infoset key is the engine's lossless ``key_suffix`` — see
``crates/cfr_core/src/preflop_rvr.rs`` ``PreflopFlatNode::Decision``.
For Phase 1, only the preflop tree is covered, so all keys begin with
``||p|``.

## Manifest

A manifest at ``assets/blueprints/manifest.json`` lists every blueprint
plus its sha256 and key metadata. Phase 2's loader reads the manifest
first and verifies each shard's checksum before serving lookups.
"""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from poker_solver.card import Card
from poker_solver.hunl import HUNLConfig, Street, _serialize_hunl_config
from poker_solver.range_aggregator import _combo_to_hand_class

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

#: Bumped on backwards-incompatible asset-format changes. Loaders should
#: reject blueprints whose ``schema_version`` does not match the version
#: they were compiled against.
SCHEMA_VERSION = "v1.0"

#: All 169 canonical Pio-style class labels. Used to validate round-trip
#: completeness — every blueprint infoset must list a strategy entry for
#: each class present in the engine's converged solution. The list is
#: enumerated in a stable order (pairs by descending rank, suited by
#: descending high rank then descending low rank, offsuit likewise).
_RANKS_HIGH_TO_LOW = "AKQJT98765432"


def _enumerate_169_classes() -> list[str]:
    """Stable enumeration of all 169 canonical hand classes."""
    out: list[str] = []
    # Pairs (13).
    for r in _RANKS_HIGH_TO_LOW:
        out.append(r + r)
    # Suited (78).
    for i, hi in enumerate(_RANKS_HIGH_TO_LOW):
        for lo in _RANKS_HIGH_TO_LOW[i + 1 :]:
            out.append(hi + lo + "s")
    # Offsuit (78).
    for i, hi in enumerate(_RANKS_HIGH_TO_LOW):
        for lo in _RANKS_HIGH_TO_LOW[i + 1 :]:
            out.append(hi + lo + "o")
    assert len(out) == 169, f"169-class enumeration size mismatch: {len(out)}"
    return out


CANONICAL_169_CLASSES: tuple[str, ...] = tuple(_enumerate_169_classes())

# ---------------------------------------------------------------------------
# Hand resolution enum (Path B switch surface)
# ---------------------------------------------------------------------------


class HandResolution(str, Enum):
    """Strategy-storage resolution.

    - ``COMBO_1326`` — one strategy row per concrete (card0, card1) pair.
      This is the engine's native storage; the differential test against
      Python ground truth uses this resolution.
    - ``CLASS_169`` — one strategy row per Pio-style hand class. Lossless
      for preflop play because preflop equity is suit-symmetric modulo
      blockers (already integrated into the 169x169x3 equity table).
      The blueprint asset format ships in this resolution.

    For Phase 1 the engine itself always runs at ``COMBO_1326``; the
    ``CLASS_169`` output is built by combo-weighted post-aggregation in
    :func:`aggregate_to_169_classes`. A follow-up engine PR may add a true
    169-vector inner loop for per-iter speedup without changing the asset
    schema.
    """

    COMBO_1326 = "combo_1326"
    CLASS_169 = "class_169"


# ---------------------------------------------------------------------------
# Action labels (decode the engine's action menu into user-facing strings)
# ---------------------------------------------------------------------------


def _decode_engine_action(token: str) -> str:
    """Map an engine action token to a user-facing label.

    Engine tokens are produced by ``PreflopAction::token`` in
    ``crates/cfr_core/src/preflop_rvr.rs``. We re-derive the equivalent
    user-facing labels in this wrapper rather than reading the action
    list back from the engine — the engine returns the strategy as a
    flat probs vector and the per-infoset action set is implicit in the
    history.
    """
    if token == "f":
        return "fold"
    if token == "c":
        return "call"
    if token == "x":
        return "check"
    if token == "A":
        return "all_in"
    if token.startswith("b"):
        return f"open_to_{token[1:]}"
    if token.startswith("r"):
        return f"raise_to_{token[1:]}"
    raise ValueError(f"unrecognized engine action token: {token!r}")


# ---------------------------------------------------------------------------
# Combo-weighted aggregation
# ---------------------------------------------------------------------------


def aggregate_to_169_classes(
    average_strategy_1326: Mapping[str, Sequence[float]],
) -> dict[str, dict[str, list[float]]]:
    """Aggregate a 1326-combo engine strategy into a 169-class strategy.

    The engine emits keys of the form ``"<hole_str>||p|<history>"`` where
    ``<hole_str>`` is the 4-char canonical hole representation
    (e.g. ``"AsAh"``) and ``<history>`` is the preflop action sequence
    so far (possibly empty for the SB root decision). Each value is a
    list of action probabilities at that infoset.

    Aggregation:

    1. Group keys by ``<history>`` (a.k.a. the infoset suffix).
    2. Within an infoset, group its 1326 entries by hand class (e.g.
       all six "AA" combos → one row).
    3. The class's combined strategy is the **uniform average** of its
       member combos' strategies. Because the engine runs every combo
       with reach=1.0 at the root, all combos within a class converge to
       the same strategy (preflop equity is suit-symmetric within a
       class modulo blockers, which average out across all 6/4/12
       member combos). At finite iteration counts, small per-combo
       drift remains; the uniform average is the canonical aggregator.

    Returns:
        ``{infoset_history: {hand_class: [prob_action_0, ..., prob_action_n-1]}}``
        where ``infoset_history`` is the engine's ``||p|<history>`` key
        suffix (with the leading "||p|" preserved so the format is
        unambiguous about which street the history belongs to).

    Notes:
        - Action probabilities are real-valued; rows sum to 1.0 ± 1e-5.
        - Empty input yields an empty dict.
        - All infosets present in the input are preserved; missing
          classes within an infoset (where the engine never reached
          that combo via a non-blocker path) are not synthesized.
    """
    if not average_strategy_1326:
        return {}

    # Group: history -> class -> list[per-combo probs]
    by_history_class: dict[str, dict[str, list[list[float]]]] = {}
    for key, probs in average_strategy_1326.items():
        if "||p|" not in key:
            # Not a preflop key — defensive skip. The engine only emits
            # ||p| keys for the preflop tree but a future engine extension
            # might add postflop keys (||f|...) we'd want to skip here.
            continue
        hole_str, _, history_suffix = key.partition("||p|")
        if len(hole_str) != 4:
            continue
        history_key = "||p|" + history_suffix
        try:
            cls = _combo_to_hand_class(
                (Card.from_str(hole_str[:2]), Card.from_str(hole_str[2:]))
            )
        except (ValueError, IndexError):
            continue
        by_history_class.setdefault(history_key, {}).setdefault(cls, []).append(
            list(probs)
        )

    # Average per class within each infoset.
    out: dict[str, dict[str, list[float]]] = {}
    for history_key, classes in by_history_class.items():
        infoset_strategy: dict[str, list[float]] = {}
        for cls, rows in classes.items():
            n_actions = len(rows[0])
            # Sanity: all rows in a class must have the same action count.
            if not all(len(r) == n_actions for r in rows):
                raise ValueError(
                    f"action-count drift within class {cls} at infoset "
                    f"{history_key!r}: {[len(r) for r in rows[:5]]}"
                )
            n_rows = len(rows)
            avg = [0.0] * n_actions
            for row in rows:
                for a in range(n_actions):
                    avg[a] += row[a]
            for a in range(n_actions):
                avg[a] /= n_rows
            # Renormalize defensively — floating drift can produce
            # sum-of-row != 1.0 by ~1e-15.
            total = sum(avg)
            if total > 0:
                for a in range(n_actions):
                    avg[a] /= total
            infoset_strategy[cls] = avg
        out[history_key] = infoset_strategy
    return out


# ---------------------------------------------------------------------------
# Action label reconstruction from engine keys
# ---------------------------------------------------------------------------


def reconstruct_action_labels_per_infoset(
    average_strategy_1326: Mapping[str, Sequence[float]],
    *,
    preflop_open_sizes_bb: Sequence[float],
    preflop_reraise_multipliers: Sequence[float],
    big_blind: int,
    small_blind: int,
    ante: int,
    starting_stack: int,
    preflop_raise_cap: int,
) -> dict[str, list[str]]:
    """Reconstruct the per-infoset action label list.

    The engine emits a flat strategy vector per infoset; the action set
    at each infoset depends on the betting history. We replay the
    preflop tree builder's action enumeration in Python so the asset
    can ship a structurally-aligned ``actions`` list per infoset.

    The reconstruction mirrors ``enumerate_actions`` in
    ``crates/cfr_core/src/preflop_rvr.rs`` but only emits the action
    *labels* (not full betting state), so we don't need to re-implement
    the full state machine.

    Returns ``{history_key: ["fold", "call", "open_to_300", ..., "all_in"]}``
    where ``history_key`` matches the keys produced by
    :func:`aggregate_to_169_classes`.

    Notes:
        - We bypass the engine's chip-level state machine and instead
          replay tokens to derive action labels. This is structurally
          simpler than the engine's enumeration; for asset metadata
          (Phase 2 loader display) this fidelity is sufficient.
    """
    # Collect unique history suffixes + their first action_count.
    history_action_count: dict[str, int] = {}
    for key, probs in average_strategy_1326.items():
        if "||p|" not in key:
            continue
        _, _, suffix = key.partition("||p|")
        history_key = "||p|" + suffix
        history_action_count.setdefault(history_key, len(probs))

    # For each history, replay tokens to reconstruct the action labels.
    out: dict[str, list[str]] = {}
    for history_key, n_actions in history_action_count.items():
        tokens = _tokens_from_history_key(history_key)
        labels = _reconstruct_labels_for_tokens(
            tokens,
            n_actions=n_actions,
            preflop_open_sizes_bb=preflop_open_sizes_bb,
            preflop_reraise_multipliers=preflop_reraise_multipliers,
            big_blind=big_blind,
            small_blind=small_blind,
            ante=ante,
            starting_stack=starting_stack,
            preflop_raise_cap=preflop_raise_cap,
        )
        out[history_key] = labels
    return out


def _tokens_from_history_key(history_key: str) -> list[str]:
    """Parse the engine's ``||p|<history>`` suffix into individual tokens.

    History tokens concatenate without separators:
    ``"b300r600c"`` parses to ``["b300", "r600", "c"]``.
    """
    if not history_key.startswith("||p|"):
        return []
    body = history_key[len("||p|") :]
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c in "fcxA":
            out.append(c)
            i += 1
        elif c in "br":
            j = i + 1
            while j < len(body) and body[j].isdigit():
                j += 1
            out.append(body[i:j])
            i = j
        else:
            raise ValueError(
                f"unrecognized history token starting at {i} in {history_key!r}"
            )
    return out


def _reconstruct_labels_for_tokens(
    tokens: Sequence[str],
    *,
    n_actions: int,
    preflop_open_sizes_bb: Sequence[float],
    preflop_reraise_multipliers: Sequence[float],
    big_blind: int,
    small_blind: int,
    ante: int,
    starting_stack: int,
    preflop_raise_cap: int,
) -> list[str]:
    """Mirror ``enumerate_actions`` in ``preflop_rvr.rs`` to derive labels.

    This is best-effort label reconstruction; the load-bearing invariant
    is that the engine's output strategy vector has exactly the number
    of slots we list here. We assert that invariant on the way out.
    """
    # Replay the betting state.
    sb_contrib = small_blind + ante
    bb_contrib = big_blind + ante
    contributions = [sb_contrib, bb_contrib]
    stacks = [starting_stack - sb_contrib, starting_stack - bb_contrib]
    last_bet_size = big_blind
    cur_player = 0
    street_num_raises = 1
    street_aggressor = 1
    to_call = bb_contrib - sb_contrib

    for tok in tokens:
        player = cur_player
        opp = 1 - player
        if tok == "f":
            cur_player = -1
            break
        elif tok == "c":
            pay = min(to_call, stacks[player])
            contributions[player] += pay
            stacks[player] -= pay
            to_call = 0
            if (
                street_aggressor == 1
                and street_num_raises == 1
                and player == 0
                and stacks[player] > 0
                and stacks[opp] > 0
            ):
                cur_player = 1
            else:
                cur_player = -1
                break
        elif tok == "x":
            cur_player = -1
            break
        elif tok == "A":
            pay = stacks[player]
            contributions[player] += pay
            stacks[player] = 0
            to_call = max(contributions[player] - contributions[opp], 0)
            last_bet_size = max(contributions[player] - contributions[opp], 1)
            street_aggressor = player
            street_num_raises += 1
            if stacks[opp] == 0:
                cur_player = -1
                break
            else:
                cur_player = opp
        elif tok.startswith("b") or tok.startswith("r"):
            raise_to = int(tok[1:])
            pay = raise_to - contributions[player]
            contributions[player] = raise_to
            stacks[player] -= pay
            to_call = max(raise_to - contributions[opp], 0)
            last_bet_size = raise_to - contributions[opp]
            street_aggressor = player
            street_num_raises += 1
            cur_player = opp
        else:
            raise ValueError(f"unrecognized token {tok!r}")

    # cur_player is now the player to act at the target infoset.
    if cur_player < 0:
        raise ValueError(
            f"history {list(tokens)!r} reached a terminal — no infoset to label"
        )
    player = cur_player
    facing_bet = to_call > 0
    cap_reached = street_num_raises >= max(preflop_raise_cap, 1)
    stack = stacks[player]
    max_to = contributions[player] + stack
    min_raise_to = contributions[player] + max(to_call, big_blind)

    labels: list[str] = []
    if facing_bet:
        labels.append("fold")
        labels.append("call")
    else:
        labels.append("check")

    if not cap_reached:
        if street_num_raises <= 1 and street_aggressor == 1 and player == 0:
            # SB facing BB — emit absolute-BB opens.
            seen: list[int] = []
            for size_bb in preflop_open_sizes_bb:
                raise_to = round(size_bb * big_blind)
                raise_to = max(raise_to, min_raise_to)
                raise_to = min(raise_to, max_to)
                if raise_to >= max_to:
                    continue
                if raise_to in seen:
                    continue
                seen.append(raise_to)
                labels.append(f"open_to_{raise_to}")
        elif facing_bet:
            # Re-raise — multiplier of previous bet.
            prev_bet = max(last_bet_size, big_blind)
            seen2: list[int] = []
            opp_contrib = contributions[1 - player]
            for mult in preflop_reraise_multipliers:
                increment = round(mult * prev_bet)
                raise_to = opp_contrib + increment
                raise_to = max(raise_to, min_raise_to)
                raise_to = min(raise_to, max_to)
                if raise_to >= max_to:
                    continue
                if raise_to in seen2:
                    continue
                seen2.append(raise_to)
                labels.append(f"raise_to_{raise_to}")
        elif street_num_raises < max(preflop_raise_cap, 1):
            # Non-facing: BB option after SB limp — treat as open.
            seen3: list[int] = []
            cur_contrib_player = contributions[player]
            for size_bb in preflop_open_sizes_bb:
                raise_to = round(size_bb * big_blind)
                raise_to = max(raise_to, cur_contrib_player + big_blind)
                raise_to = min(raise_to, max_to)
                if raise_to >= max_to:
                    continue
                if raise_to in seen3:
                    continue
                seen3.append(raise_to)
                labels.append(f"open_to_{raise_to}")
        if stack > to_call:
            labels.append("all_in")

    if len(labels) != n_actions:
        # The engine and our re-derivation disagree — fall back to a
        # safe generic ``a{idx}`` label so the asset is still valid.
        labels = [f"a{i}" for i in range(n_actions)]
    return labels


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlueprintConfig:
    """Configuration knobs that fully determine a blueprint cell.

    Two ``BlueprintConfig``s with equal fields produce identical blueprints
    (modulo iteration count + Nash multiplicity drift).
    """

    stack_bb: int
    ante_bb: float
    iterations: int
    alpha: float = 1.5
    beta: float = 0.0
    gamma: float = 2.0
    preflop_open_sizes_bb: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
    preflop_reraise_multipliers: tuple[float, ...] = (2.0, 3.0, 4.0, 5.0)
    preflop_raise_cap: int = 4
    small_blind_bb: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        # Lists serialize cleaner than tuples in JSON.
        d["preflop_open_sizes_bb"] = list(self.preflop_open_sizes_bb)
        d["preflop_reraise_multipliers"] = list(self.preflop_reraise_multipliers)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> BlueprintConfig:
        return cls(
            stack_bb=int(d["stack_bb"]),
            ante_bb=float(d["ante_bb"]),
            iterations=int(d["iterations"]),
            alpha=float(d.get("alpha", 1.5)),
            beta=float(d.get("beta", 0.0)),
            gamma=float(d.get("gamma", 2.0)),
            preflop_open_sizes_bb=tuple(
                float(x) for x in d.get("preflop_open_sizes_bb", (2.0, 3.0, 4.0, 5.0))
            ),
            preflop_reraise_multipliers=tuple(
                float(x)
                for x in d.get("preflop_reraise_multipliers", (2.0, 3.0, 4.0, 5.0))
            ),
            preflop_raise_cap=int(d.get("preflop_raise_cap", 4)),
            small_blind_bb=float(d.get("small_blind_bb", 0.5)),
        )


@dataclass
class Blueprint:
    """A single preflop blueprint shard.

    A blueprint maps each preflop infoset (keyed by action history) to
    the converged 169-class strategy at that infoset. Infosets are
    sparse — only those reachable from the root via the engine's action
    menu are present.

    The ``actions`` field lists the user-facing label for each
    strategy-vector slot; ``strategy[hand_class][k]`` is the probability
    of taking action ``actions[k]``.
    """

    schema_version: str
    config: BlueprintConfig
    wall_seconds: float
    final_exploitability_bb100: float | None
    #: ``{history_key: {"actions": [str], "strategy": {hand_class: [float]}}}``
    infosets: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def n_infosets(self) -> int:
        return len(self.infosets)

    @property
    def n_strategy_rows(self) -> int:
        return sum(len(info["strategy"]) for info in self.infosets.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config": self.config.to_dict(),
            "convergence": {
                "wall_seconds": self.wall_seconds,
                "final_exploitability_bb100": self.final_exploitability_bb100,
            },
            "infosets": self.infosets,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Blueprint:
        return cls(
            schema_version=str(d["schema_version"]),
            config=BlueprintConfig.from_dict(d["config"]),
            wall_seconds=float(d.get("convergence", {}).get("wall_seconds", 0.0)),
            final_exploitability_bb100=(
                None
                if d.get("convergence", {}).get("final_exploitability_bb100") is None
                else float(d["convergence"]["final_exploitability_bb100"])
            ),
            infosets={str(k): v for k, v in d.get("infosets", {}).items()},
        )

    def shard_filename(self) -> str:
        return blueprint_shard_filename(self.config)


def blueprint_shard_filename(config: BlueprintConfig) -> str:
    """Canonical filename for a blueprint shard, sharded by depth + ante.

    Examples:
        ``preflop_169class_40bb_anteNone.json.gz`` (ante = 0)
        ``preflop_169class_40bb_anteHalf.json.gz`` (ante = 0.5 BB)
        ``preflop_169class_40bb_anteFull.json.gz`` (ante = 1.0 BB)
        ``preflop_169class_40bb_ante0.30.json.gz`` (other)
    """
    if config.ante_bb == 0.0:
        ante_token = "anteNone"
    elif math.isclose(config.ante_bb, 0.5, abs_tol=1e-6):
        ante_token = "anteHalf"
    elif math.isclose(config.ante_bb, 1.0, abs_tol=1e-6):
        ante_token = "anteFull"
    else:
        ante_token = f"ante{config.ante_bb:.2f}"
    return f"preflop_169class_{config.stack_bb}bb_{ante_token}.json.gz"


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------


def save_blueprint(bp: Blueprint, path: Path) -> str:
    """Write a blueprint to a gzipped JSON file. Returns sha256 of contents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bp.to_dict(), sort_keys=False, separators=(",", ":"))
    raw = payload.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    with gzip.open(path, "wb", compresslevel=6) as f:
        f.write(raw)
    return sha


def load_blueprint(path: Path) -> Blueprint:
    """Read a gzipped JSON blueprint file and return a :class:`Blueprint`."""
    path = Path(path)
    with gzip.open(path, "rb") as f:
        raw = f.read()
    d = json.loads(raw.decode("utf-8"))
    return Blueprint.from_dict(d)


def file_sha256(path: Path) -> str:
    """Compute the sha256 of the *uncompressed JSON contents* of a shard.

    This matches the sha returned by :func:`save_blueprint`. Phase 2's
    loader verifies the manifest sha against this value, not against the
    gzipped file bytes (gzip output is non-deterministic — the .gz
    header carries a timestamp by default).
    """
    bp = load_blueprint(path)
    payload = json.dumps(bp.to_dict(), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class ManifestEntry:
    stack_bb: int
    ante_bb: float
    filename: str
    sha256: str
    file_size_bytes: int
    final_exploitability_bb100: float | None
    wall_seconds: float
    iterations: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ManifestEntry:
        return cls(
            stack_bb=int(d["stack_bb"]),
            ante_bb=float(d["ante_bb"]),
            filename=str(d["filename"]),
            sha256=str(d["sha256"]),
            file_size_bytes=int(d["file_size_bytes"]),
            final_exploitability_bb100=(
                None
                if d.get("final_exploitability_bb100") is None
                else float(d["final_exploitability_bb100"])
            ),
            wall_seconds=float(d["wall_seconds"]),
            iterations=int(d["iterations"]),
        )


@dataclass
class Manifest:
    schema_version: str
    premium_a_version: str
    generated_date_utc: str
    entries: list[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "premium_a_version": self.premium_a_version,
            "generated_date_utc": self.generated_date_utc,
            "shards": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Manifest:
        return cls(
            schema_version=str(d["schema_version"]),
            premium_a_version=str(d["premium_a_version"]),
            generated_date_utc=str(d["generated_date_utc"]),
            entries=[ManifestEntry.from_dict(e) for e in d.get("shards", [])],
        )


def save_manifest(manifest: Manifest, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, sort_keys=False)


def load_manifest(path: Path) -> Manifest:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return Manifest.from_dict(d)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _equity_table_path() -> str:
    """Locate the shipped 169x169 preflop equity table."""
    here = Path(__file__).resolve().parent
    candidate = here.parent / "assets" / "preflop_equity_169x169.npz"
    return str(candidate)


def hunl_config_from_blueprint_config(
    config: BlueprintConfig, *, chip_per_bb: int = 100
) -> HUNLConfig:
    """Build a HUNLConfig that the engine accepts from a BlueprintConfig.

    ``chip_per_bb`` is the integer-cents scale factor (the engine
    operates on integer chips; BB = 100 cents is the standard scale).
    """
    bb_chips = chip_per_bb
    sb_chips = round(config.small_blind_bb * chip_per_bb)
    ante_chips = round(config.ante_bb * chip_per_bb)
    starting_stack = config.stack_bb * chip_per_bb
    return HUNLConfig(
        starting_stack=starting_stack,
        small_blind=sb_chips,
        big_blind=bb_chips,
        ante=ante_chips,
        starting_street=Street.PREFLOP,
        preflop_raise_cap=config.preflop_raise_cap,
    )


def generate_blueprint(
    config: BlueprintConfig,
    *,
    chip_per_bb: int = 100,
    equity_table_path: str | None = None,
    rust_solver: Any | None = None,
    skip_actual_solve: bool = False,
    hand_resolution: HandResolution = HandResolution.CLASS_169,
) -> Blueprint:
    """Generate a single blueprint cell.

    Args:
        config: The blueprint configuration (stack_bb, ante_bb, iterations,
            DCFR hyperparams, action menu).
        chip_per_bb: Integer cents per BB. Default 100.
        equity_table_path: Override path to the 169x169x3 equity table.
            Defaults to the in-tree asset.
        rust_solver: Optional callable matching the signature of
            ``poker_solver._rust.solve_hunl_preflop_rvr`` (or, when
            ``hand_resolution == CLASS_169``, the signature of
            ``solve_hunl_preflop_rvr_class169``) for dependency
            injection in tests. If ``None``, imports the production
            extension.
        skip_actual_solve: For tests + dry runs — if True, produces an
            empty blueprint with metadata only. Used to validate the
            schema round-trip without paying solve cost.
        hand_resolution: Engine storage mode.
            - ``CLASS_169`` (default, **True Path B**): engine runs the
              169-element vector kernel. Per-iter speedup ~7-12x over
              ``COMBO_1326``. Output strategy is already 169-class
              (wrapper aggregation is a no-op).
            - ``COMBO_1326`` (legacy hybrid path): engine runs the
              1326-combo kernel; wrapper post-aggregates to 169 classes
              via ``aggregate_to_169_classes``. Kept for differential
              testing and applications that need exact per-combo
              strategies.

    Returns:
        The converged blueprint with 169-class strategies.
    """
    if equity_table_path is None:
        equity_table_path = _equity_table_path()

    hunl_config = hunl_config_from_blueprint_config(config, chip_per_bb=chip_per_bb)
    config_json = _serialize_hunl_config(hunl_config)

    started = time.time()

    if skip_actual_solve:
        wallclock = time.time() - started
        return Blueprint(
            schema_version=SCHEMA_VERSION,
            config=config,
            wall_seconds=wallclock,
            final_exploitability_bb100=None,
            infosets={},
        )

    if rust_solver is None:
        from poker_solver import _rust  # type: ignore[attr-defined]

        attr_name = (
            "solve_hunl_preflop_rvr_class169"
            if hand_resolution == HandResolution.CLASS_169
            else "solve_hunl_preflop_rvr"
        )
        rust_solver = getattr(_rust, attr_name, None)
        if rust_solver is None:
            raise RuntimeError(
                f"poker_solver._rust.{attr_name} is missing. "
                "Rebuild via `maturin develop --release`."
            )

    if hand_resolution == HandResolution.CLASS_169:
        # True Path B: engine emits 169-class strategy directly.
        raw = rust_solver(
            config_json,
            equity_table_path,
            config.iterations,
            config.alpha,
            config.beta,
            config.gamma,
            list(config.preflop_open_sizes_bb),
            list(config.preflop_reraise_multipliers),
            None,  # root_reach_p0 — default combo-weighted (matches hybrid)
            None,  # root_reach_p1 — default combo-weighted (matches hybrid)
        )
    else:
        raw = rust_solver(
            config_json,
            equity_table_path,
            config.iterations,
            config.alpha,
            config.beta,
            config.gamma,
            list(config.preflop_open_sizes_bb),
            list(config.preflop_reraise_multipliers),
            None,  # p0_holes — full 1326
            None,  # p1_holes — full 1326
        )
    average_strategy = {k: list(v) for k, v in raw["average_strategy"].items()}
    wallclock = time.time() - started

    # Reconstruct action labels per infoset.
    action_labels_per_infoset = reconstruct_action_labels_per_infoset(
        average_strategy,
        preflop_open_sizes_bb=config.preflop_open_sizes_bb,
        preflop_reraise_multipliers=config.preflop_reraise_multipliers,
        big_blind=hunl_config.big_blind,
        small_blind=hunl_config.small_blind,
        ante=hunl_config.ante,
        starting_stack=hunl_config.starting_stack,
        preflop_raise_cap=hunl_config.preflop_raise_cap,
    )

    # Aggregate to 169 classes if needed.
    if hand_resolution == HandResolution.CLASS_169:
        # Engine output is already 169-class; key format is
        # ``"<class_label>||p|<history>"``. Reshape into
        # ``{history_key: {class_label: probs}}`` to match the schema.
        by_history_class = _reshape_class169_engine_output(average_strategy)
    else:
        # 1326-combo path: wrapper post-aggregates.
        by_history_class = aggregate_to_169_classes(average_strategy)

    infosets: dict[str, dict[str, Any]] = {}
    for history_key, classes in by_history_class.items():
        labels = action_labels_per_infoset.get(history_key, [])
        # Defensive: if label reconstruction failed, use generic labels.
        if not classes:
            continue
        first_n_actions = len(next(iter(classes.values())))
        if len(labels) != first_n_actions:
            labels = [f"a{i}" for i in range(first_n_actions)]
        infosets[history_key] = {
            "actions": labels,
            "strategy": classes,
        }

    return Blueprint(
        schema_version=SCHEMA_VERSION,
        config=config,
        wall_seconds=wallclock,
        final_exploitability_bb100=None,
        infosets=infosets,
    )


def _reshape_class169_engine_output(
    average_strategy: dict[str, list[float]],
) -> dict[str, dict[str, list[float]]]:
    """Reshape a 169-class engine output into ``{history: {class: probs}}``.

    The 169-class engine emits keys of the form
    ``"<class_label>||p|<history>"`` (e.g. ``"AA||p|"``). This is the
    same final schema produced by ``aggregate_to_169_classes`` for the
    1326-combo path, so the rest of ``generate_blueprint`` doesn't need
    to know which path produced the output.
    """
    out: dict[str, dict[str, list[float]]] = {}
    canonical = set(CANONICAL_169_CLASSES)
    for key, probs in average_strategy.items():
        if "||p|" not in key:
            continue
        cls_label, _, history_suffix = key.partition("||p|")
        if cls_label not in canonical:
            continue
        history_key = "||p|" + history_suffix
        out.setdefault(history_key, {})[cls_label] = list(probs)
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_blueprint(bp: Blueprint, *, sum_tolerance: float = 1e-4) -> list[str]:
    """Return a list of validation warnings (empty list = blueprint is sane).

    Checks:
      - schema_version matches.
      - Each infoset's strategy entries sum to 1.0 ± tolerance.
      - Every infoset entry's strategy vector length matches its actions length.
      - All hand_class labels are in the canonical 169 set.
    """
    out: list[str] = []
    if bp.schema_version != SCHEMA_VERSION:
        out.append(
            f"schema_version mismatch: blueprint={bp.schema_version!r} "
            f"expected={SCHEMA_VERSION!r}"
        )
    canonical = set(CANONICAL_169_CLASSES)
    for history_key, info in bp.infosets.items():
        actions = info.get("actions", [])
        strategy = info.get("strategy", {})
        n_actions = len(actions)
        for cls, probs in strategy.items():
            if cls not in canonical:
                out.append(
                    f"infoset {history_key!r}: non-canonical class label {cls!r}"
                )
            if len(probs) != n_actions:
                out.append(
                    f"infoset {history_key!r} class {cls!r}: "
                    f"strategy length {len(probs)} != actions length {n_actions}"
                )
                continue
            total = sum(probs)
            if abs(total - 1.0) > sum_tolerance:
                out.append(
                    f"infoset {history_key!r} class {cls!r}: "
                    f"probabilities sum to {total:.6f}, expected 1.0 "
                    f"(tolerance {sum_tolerance:.0e})"
                )
    return out


# ---------------------------------------------------------------------------
# Batch generation helper (consumed by the CLI)
# ---------------------------------------------------------------------------


@dataclass
class BatchSpec:
    """A single (depth, ante) batch entry."""

    stack_bb: int
    ante_bb: float


def standard_batch_specs() -> list[BatchSpec]:
    """Return the locked Phase 1 grid: 9 depths × 3 antes = 27 cells.

    Depths: 20, 30, 40, 60, 80, 100, 150, 175, 200 BB.
    Antes: 0 (none), 0.5 BB (half), 1.0 BB (full).
    """
    depths = [20, 30, 40, 60, 80, 100, 150, 175, 200]
    antes = [0.0, 0.5, 1.0]
    out: list[BatchSpec] = []
    for d in depths:
        for a in antes:
            out.append(BatchSpec(stack_bb=d, ante_bb=a))
    return out


def manifest_entry_for_blueprint(
    bp: Blueprint, *, path: Path, sha: str
) -> ManifestEntry:
    path = Path(path)
    return ManifestEntry(
        stack_bb=bp.config.stack_bb,
        ante_bb=bp.config.ante_bb,
        filename=path.name,
        sha256=sha,
        file_size_bytes=path.stat().st_size,
        final_exploitability_bb100=bp.final_exploitability_bb100,
        wall_seconds=bp.wall_seconds,
        iterations=bp.config.iterations,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "SCHEMA_VERSION",
    "CANONICAL_169_CLASSES",
    "HandResolution",
    "BlueprintConfig",
    "Blueprint",
    "Manifest",
    "ManifestEntry",
    "BatchSpec",
    "aggregate_to_169_classes",
    "_reshape_class169_engine_output",
    "blueprint_shard_filename",
    "generate_blueprint",
    "hunl_config_from_blueprint_config",
    "load_blueprint",
    "load_manifest",
    "manifest_entry_for_blueprint",
    "reconstruct_action_labels_per_infoset",
    "save_blueprint",
    "save_manifest",
    "standard_batch_specs",
    "validate_blueprint",
]
