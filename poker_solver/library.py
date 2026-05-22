"""Local SQLite-backed library of solved poker spots (PR 11).

The library turns the per-spot solver (PR 5) into a "solve once, browse
forever" workflow: solved spots are persisted with a deterministic
``spot_id`` (sha256 of the canonicalized spot description) so the same
configuration on any machine resolves to the same row. The on-disk
shape is documented in ``library_schema.sql``.

Design highlights (per ``docs/pr11_prep/pr11_spec.md``):

- **Single-user, single-machine.** No cloud, no network. Path defaults
  to ``~/.poker_solver/library.db`` (overridable via
  ``$POKER_SOLVER_LIBRARY_PATH`` or an explicit ``path=`` argument).
- **SQLite WAL mode** for one-writer / many-reader concurrency. Writes
  serialize through an in-process ``threading.Lock`` per ``Library``
  instance; reads piggyback on WAL's snapshot isolation.
- **Strategies stored gzip-compressed** (``compresslevel=6``) on a JSON
  serialization with no whitespace; the deserialization roundtrip is
  bit-exact for IEEE-754 doubles.
- **Canonical spot ID** is the sha256 hex of a canonicalized JSON
  serialization of the description (sorted board cards, sorted bet-size
  fractions, sorted JSON keys). Solver hyperparameters (α/β/γ) are
  excluded: they are locked per PLAN.md.
- **Stdlib only.** ``sqlite3``, ``gzip``, ``hashlib``, ``json``,
  ``dataclasses``, ``pathlib``, ``threading``, ``warnings`` — no new
  runtime dependencies. NumPy is tolerated for ``np.ndarray`` strategy
  values (converted via ``.tolist()``) but never imported.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import json
import os
import sqlite3
import threading
import time
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poker_solver.hunl import HUNLConfig, Street

if TYPE_CHECKING:
    from poker_solver.solver import SolveResult


_SCHEMA_VERSION = 1
_SCHEMA_FILE = Path(__file__).with_name("library_schema.sql")
_DEFAULT_DB_PATH = Path.home() / ".poker_solver" / "library.db"
_ENV_VAR = "POKER_SOLVER_LIBRARY_PATH"

_STREET_NAMES: dict[int, str] = {
    int(Street.PREFLOP): "preflop",
    int(Street.FLOP): "flop",
    int(Street.TURN): "turn",
    int(Street.RIVER): "river",
    int(Street.SHOWDOWN): "showdown",
}


# ---------- Dataclasses ----------


@dataclass(frozen=True)
class SpotDescription:
    """Identity of a solvable spot.

    Wraps a ``HUNLConfig`` plus optional initial ranges and a free-form
    user label. Two ``SpotDescription`` values that are semantically
    equivalent (board card order, bet-size order, range hand order)
    produce the same ``spot_id`` (see ``_compute_spot_id``).
    """

    config: HUNLConfig
    initial_ranges: tuple[tuple[str, str], ...] | None = None
    label: str = ""

    def spot_id(self) -> str:
        """Compute the deterministic sha256 spot ID per spec §2.3."""
        return _compute_spot_id(self)


@dataclass(frozen=True)
class SpotMetadata:
    """Lightweight row projection (no strategy blob). Returned by Library.list."""

    spot_id: str
    label: str
    street: str
    board_signature: str
    stack_bb: int
    game_value: float
    exploitability: float
    iterations: int
    abstraction_tier: str
    solver_version: str
    created_at: int


@dataclass(frozen=True)
class LibraryFilter:
    """AND-combined filter for ``Library.list``."""

    board_pattern: str | None = None
    street: str | None = None
    stack_bb_min: int | None = None
    stack_bb_max: int | None = None
    solver_version: str | None = None
    created_after: int | None = None
    label_pattern: str | None = None


@dataclass(frozen=True)
class LibraryStats:
    total_count: int
    total_size_bytes: int
    by_street: dict[str, int]
    by_solver_version: dict[str, int]
    oldest_created_at: int | None
    newest_created_at: int | None


# ---------- Exceptions ----------


class LibraryError(Exception):
    """Base exception for the library module."""


class LibraryDuplicateError(LibraryError):
    """``Library.put`` saw an existing ``spot_id`` and ``overwrite=False``."""


class LibrarySchemaError(LibraryError):
    """On-disk ``schema_version`` exceeds what this code supports."""


# ---------- Path resolution ----------


def _resolve_library_path(explicit: Path | None) -> Path:
    """Resolve the DB path per the documented precedence.

    Order: explicit ``path=`` arg > ``$POKER_SOLVER_LIBRARY_PATH`` env var
    > ``~/.poker_solver/library.db``. (The CLI flag is applied at the
    caller level and arrives here via the ``explicit`` argument.)
    """
    if explicit is not None:
        return Path(explicit).expanduser()
    env = os.environ.get(_ENV_VAR)
    if env:
        return Path(env).expanduser()
    return _DEFAULT_DB_PATH


# ---------- Spot ID canonicalization ----------


def _canonicalize_spot(spot: SpotDescription) -> dict[str, Any]:
    """Build the canonical dict that goes into ``spot_id``.

    Canonicalization rules (must match spec §2.3 + the prompt's locked
    defaults; Agent C's determinism tests rely on this exact behavior):

    1. Board cards sorted ascending by ``(rank, suit)`` — the same
       convention as ``HUNLPoker.infoset_key``.
    2. Stack values are already integer cents in ``HUNLConfig``.
    3. ``bet_size_fractions`` sorted ascending; serialized as floats.
    4. ``initial_ranges`` (if present) sorted lexicographically with
       each hand's cards in ascending order. ``None`` and an empty tuple
       canonicalize to ``None`` (semantically equivalent).
    5. ``ante`` and ``rake`` (rake_rate + rake_cap) are always included.
    6. Solver hyperparameters (α/β/γ) are deliberately excluded — they
       are locked at α=1.5, β=0, γ=2.0 per PLAN.md. If exposed later as
       per-solve knobs, bump ``schema_version`` and include them.
    7. The ``abstraction`` field of ``HUNLConfig`` (which is excluded
       from compare/hash on the config itself, per consistency review
       v2 NEW-1) is also excluded from the spot ID. The bucket tables
       are a runtime adjunct, not a game-rule field.
    """
    cfg = spot.config

    sorted_board = sorted(cfg.initial_board, key=lambda c: (c.rank, c.suit))
    board_serial = [[c.rank, c.suit] for c in sorted_board]
    initial_hole_serial: list[list[list[int]]] | None
    if cfg.initial_hole_cards:
        initial_hole_serial = [
            sorted([[c.rank, c.suit] for c in pair]) for pair in cfg.initial_hole_cards
        ]
    else:
        initial_hole_serial = None
    sorted_bet_fracs = sorted(float(x) for x in cfg.bet_size_fractions)

    ranges_serial: list[list[str]] | None
    if not spot.initial_ranges:
        ranges_serial = None
    else:
        ranges_serial = sorted(
            [_canonicalize_hand(h), w] for h, w in spot.initial_ranges
        )

    canonical: dict[str, Any] = {
        "starting_stack": int(cfg.starting_stack),
        "small_blind": int(cfg.small_blind),
        "big_blind": int(cfg.big_blind),
        "ante": int(cfg.ante),
        "starting_street": int(cfg.starting_street),
        "initial_board": board_serial,
        "initial_pot": int(cfg.initial_pot),
        "initial_contributions": [
            int(cfg.initial_contributions[0]),
            int(cfg.initial_contributions[1]),
        ],
        "initial_hole_cards": initial_hole_serial,
        "preflop_raise_cap": int(cfg.preflop_raise_cap),
        "postflop_raise_cap": int(cfg.postflop_raise_cap),
        "bet_size_fractions": sorted_bet_fracs,
        "include_all_in": bool(cfg.include_all_in),
        "force_allin_threshold": int(cfg.force_allin_threshold),
        "min_bet_bb": int(cfg.min_bet_bb),
        "rake_rate": float(cfg.rake_rate),
        "rake_cap": int(cfg.rake_cap),
        "initial_ranges": ranges_serial,
        # ``label`` is intentionally EXCLUDED — spec §2.3 rules 1-7 omit it.
        # A re-label is a rename, not a different spot.
    }
    return canonical


def _canonicalize_hand(hand: str) -> str:
    """Sort a 4-character hole-hand spec so ``KhAh`` and ``AhKh`` match.

    Falls back to the original string for any input that isn't a clean
    two-card spec — the canonical form is best-effort and primarily a
    hedge against trivial reorder, not a full parser.
    """
    s = hand.strip()
    if len(s) != 4:
        return s
    try:
        first, second = s[0:2], s[2:4]
        return "".join(sorted([first, second]))
    except (IndexError, ValueError):
        return s


def _compute_spot_id(spot: SpotDescription) -> str:
    """Return sha256 hex of canonicalized JSON. See ``_canonicalize_spot``.

    Properties (verified by Agent C's tests in spec §9):
    - Same description, two different machines → same ID.
    - Reordered board / bet sizes / ranges → same ID.
    - One-card-different board → different ID.
    - 1-BB stack difference → different ID.
    """
    canonical = _canonicalize_spot(spot)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


# ---------- Strategy serialization ----------


def _strategy_to_jsonable(
    strategy: dict[str, Any],
) -> dict[str, list[float]]:
    """Convert numpy / generic-sequence strategy values to plain float lists."""
    out: dict[str, list[float]] = {}
    for key, probs in strategy.items():
        tolist = getattr(probs, "tolist", None)
        converted = tolist() if callable(tolist) else list(probs)
        out[key] = [float(p) for p in converted]
    return out


def _serialize_strategy(strategy: dict[str, Any]) -> bytes:
    """JSON-serialize then gzip with level 6 (spec §2.4)."""
    jsonable = _strategy_to_jsonable(strategy)
    raw = json.dumps(jsonable, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def _deserialize_strategy(blob: bytes) -> dict[str, list[float]]:
    """Reverse of ``_serialize_strategy``. Roundtrip is bit-exact."""
    raw = gzip.decompress(blob)
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("decoded strategy blob is not a JSON object")
    out: dict[str, list[float]] = {}
    for k, v in obj.items():
        if not isinstance(v, list):
            raise ValueError(f"strategy value for {k!r} is not a list")
        out[str(k)] = [float(p) for p in v]
    return out


# ---------- Result <-> dict ----------


def _result_to_dict(result: SolveResult) -> dict[str, Any]:
    """Project a ``SolveResult`` (or any subclass) to a plain dict."""
    history = list(getattr(result, "exploitability_history", []) or [])
    payload: dict[str, Any] = {
        "average_strategy": _strategy_to_jsonable(result.average_strategy),
        "game_value": float(getattr(result, "game_value", 0.0)),
        "exploitability_history": [float(x) for x in history],
        "iterations": int(getattr(result, "iterations", 0)),
        "backend": str(getattr(result, "backend", "python")),
    }
    return payload


def _dict_to_result(payload: dict[str, Any]) -> SolveResult:
    """Inverse of ``_result_to_dict``. Imports ``SolveResult`` lazily."""
    from poker_solver.solver import SolveResult

    return SolveResult(
        average_strategy={
            str(k): [float(p) for p in v]
            for k, v in payload.get("average_strategy", {}).items()
        },
        exploitability_history=[
            float(x) for x in payload.get("exploitability_history", [])
        ],
        game_value=float(payload.get("game_value", 0.0)),
        iterations=int(payload.get("iterations", 0)),
        backend=str(payload.get("backend", "python")),
    )


# ---------- SpotDescription <-> dict ----------


def _spot_to_dict(spot: SpotDescription) -> dict[str, Any]:
    """Portable JSON view of a SpotDescription (for export / spot_json)."""
    cfg = spot.config
    return {
        "config": {
            "starting_stack": int(cfg.starting_stack),
            "small_blind": int(cfg.small_blind),
            "big_blind": int(cfg.big_blind),
            "ante": int(cfg.ante),
            "starting_street": int(cfg.starting_street),
            "initial_board": [[c.rank, c.suit] for c in cfg.initial_board],
            "initial_pot": int(cfg.initial_pot),
            "initial_contributions": [
                int(cfg.initial_contributions[0]),
                int(cfg.initial_contributions[1]),
            ],
            "initial_hole_cards": (
                [[[c.rank, c.suit] for c in pair] for pair in cfg.initial_hole_cards]
                if cfg.initial_hole_cards
                else None
            ),
            "preflop_raise_cap": int(cfg.preflop_raise_cap),
            "postflop_raise_cap": int(cfg.postflop_raise_cap),
            "bet_size_fractions": [float(x) for x in cfg.bet_size_fractions],
            "include_all_in": bool(cfg.include_all_in),
            "force_allin_threshold": int(cfg.force_allin_threshold),
            "min_bet_bb": int(cfg.min_bet_bb),
            "rake_rate": float(cfg.rake_rate),
            "rake_cap": int(cfg.rake_cap),
        },
        "initial_ranges": (
            [list(pair) for pair in spot.initial_ranges]
            if spot.initial_ranges
            else None
        ),
        "label": spot.label,
    }


def _dict_to_spot(payload: dict[str, Any]) -> SpotDescription:
    """Inverse of ``_spot_to_dict``."""
    from poker_solver.card import Card

    cfg_d = payload["config"]
    board = tuple(Card(int(r), int(s)) for r, s in cfg_d.get("initial_board", []))
    raw_hole = cfg_d.get("initial_hole_cards")
    if raw_hole:
        hole_pairs = tuple(
            (Card(int(p[0][0]), int(p[0][1])), Card(int(p[1][0]), int(p[1][1])))
            for p in raw_hole
        )
        # mypy: this is exactly the shape `HUNLConfig.initial_hole_cards` expects.
        initial_hole_cards: Any = hole_pairs
    else:
        initial_hole_cards = ()
    config = HUNLConfig(
        starting_stack=int(cfg_d["starting_stack"]),
        small_blind=int(cfg_d["small_blind"]),
        big_blind=int(cfg_d["big_blind"]),
        ante=int(cfg_d.get("ante", 0)),
        starting_street=Street(int(cfg_d["starting_street"])),
        initial_board=board,
        initial_pot=int(cfg_d.get("initial_pot", 0)),
        initial_contributions=(
            int(cfg_d["initial_contributions"][0]),
            int(cfg_d["initial_contributions"][1]),
        ),
        initial_hole_cards=initial_hole_cards,
        preflop_raise_cap=int(cfg_d.get("preflop_raise_cap", 4)),
        postflop_raise_cap=int(cfg_d.get("postflop_raise_cap", 3)),
        bet_size_fractions=tuple(float(x) for x in cfg_d.get("bet_size_fractions", ())),
        include_all_in=bool(cfg_d.get("include_all_in", True)),
        force_allin_threshold=int(cfg_d.get("force_allin_threshold", 1)),
        min_bet_bb=int(cfg_d.get("min_bet_bb", 1)),
        rake_rate=float(cfg_d.get("rake_rate", 0.0)),
        rake_cap=int(cfg_d.get("rake_cap", 0)),
    )
    raw_ranges = payload.get("initial_ranges")
    ranges: tuple[tuple[str, str], ...] | None = (
        tuple((str(a), str(b)) for a, b in raw_ranges) if raw_ranges else None
    )
    return SpotDescription(
        config=config, initial_ranges=ranges, label=str(payload.get("label", ""))
    )


# ---------- Helpers for row metadata ----------


def _street_name(street: Street) -> str:
    return _STREET_NAMES.get(int(street), str(street.name).lower())


def _board_signature(cfg: HUNLConfig) -> str:
    sorted_board = sorted(cfg.initial_board, key=lambda c: (c.rank, c.suit))
    return "".join(str(c) for c in sorted_board)


def _bet_menu_hash(cfg: HUNLConfig) -> str:
    sorted_fracs = sorted(float(x) for x in cfg.bet_size_fractions)
    payload = json.dumps(
        {
            "bet_size_fractions": sorted_fracs,
            "include_all_in": bool(cfg.include_all_in),
            "preflop_raise_cap": int(cfg.preflop_raise_cap),
            "postflop_raise_cap": int(cfg.postflop_raise_cap),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _abstraction_tier(cfg: HUNLConfig) -> str:
    if cfg.abstraction is None:
        return "lossless"
    return f"abstraction:{cfg.abstraction.version}"


def _current_solver_version() -> str:
    from poker_solver import __version__ as v

    return str(v)


# ---------- Library class ----------


class Library:
    """Local on-disk cache of solved poker spots.

    Use as a context manager (``with Library.open() as lib:``) for
    automatic close. Writes are serialized via an in-process lock;
    reads do not block.
    """

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        # Constructor is package-private; clients use ``Library.open``.
        self._path: Path = path
        self._conn: sqlite3.Connection | None = connection
        self._write_lock: threading.Lock = threading.Lock()

    @classmethod
    def open(cls, path: Path | None = None) -> Library:
        """Open (creating if missing) the SQLite database."""
        resolved = _resolve_library_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        # `isolation_level=None` lets us drive transactions explicitly with
        # BEGIN / COMMIT; SQLite's autocommit-by-default conflicts with
        # WAL-mode multi-statement writes.
        conn = sqlite3.connect(
            str(resolved),
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        schema_sql = _SCHEMA_FILE.read_text()
        conn.executescript(schema_sql)
        lib = cls(resolved, conn)
        lib._init_meta_or_check()
        return lib

    def _init_meta_or_check(self) -> None:
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT value FROM spots_meta WHERE key = 'library_version'"
        ).fetchone()
        if row is None:
            now = int(time.time())
            version = _current_solver_version()
            with self._write_lock:
                self._conn.execute("BEGIN")
                try:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO spots_meta(key, value) VALUES (?, ?)",
                        ("library_version", str(_SCHEMA_VERSION)),
                    )
                    self._conn.execute(
                        "INSERT OR REPLACE INTO spots_meta(key, value) VALUES (?, ?)",
                        ("created_by", version),
                    )
                    self._conn.execute(
                        "INSERT OR REPLACE INTO spots_meta(key, value) VALUES (?, ?)",
                        ("created_at", str(now)),
                    )
                    self._conn.execute("COMMIT")
                except Exception:
                    self._conn.execute("ROLLBACK")
                    raise
            return
        on_disk = int(row["value"])
        if on_disk > _SCHEMA_VERSION:
            raise LibrarySchemaError(
                f"library at {self._path} was created by a newer poker_solver "
                f"(schema_version={on_disk}); this code knows "
                f"schema_version={_SCHEMA_VERSION}. Upgrade poker_solver to "
                "read this library."
            )

    # ---- public API ----

    def put(
        self,
        spot: SpotDescription,
        result: SolveResult,
        *,
        overwrite: bool = False,
    ) -> str:
        """Persist a solved spot. Returns the spot_id (sha256 hex)."""
        assert self._conn is not None
        spot_id = _compute_spot_id(spot)
        cfg = spot.config

        spot_dict = _spot_to_dict(spot)
        spot_json = json.dumps(spot_dict, separators=(",", ":")).encode("utf-8")
        strategy_gz = _serialize_strategy(result.average_strategy)
        game_value = float(getattr(result, "game_value", 0.0))
        history = list(getattr(result, "exploitability_history", []) or [])
        exploitability = float(history[-1]) if history else float("nan")
        iterations = int(getattr(result, "iterations", 0))
        abstraction_tier = _abstraction_tier(cfg)
        solver_version = _current_solver_version()
        created_at = int(time.time())
        board_signature = _board_signature(cfg)
        stack_bb = int(cfg.starting_stack // cfg.big_blind)
        bet_menu_hash = _bet_menu_hash(cfg)
        street = _street_name(cfg.starting_street)

        with self._write_lock:
            self._conn.execute("BEGIN")
            try:
                existing = self._conn.execute(
                    "SELECT id FROM spots WHERE id = ?", (spot_id,)
                ).fetchone()
                if existing is not None and not overwrite:
                    self._conn.execute("ROLLBACK")
                    raise LibraryDuplicateError(
                        f"spot_id {spot_id} already exists; pass overwrite=True"
                    )
                if existing is not None:
                    self._conn.execute("DELETE FROM spots WHERE id = ?", (spot_id,))
                self._conn.execute(
                    """
                    INSERT INTO spots(
                        id, spot_json, strategy_gz, game_value, exploitability,
                        iterations, abstraction_tier, solver_version,
                        schema_version, created_at, board_signature, stack_bb,
                        bet_menu_hash, street, label
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        spot_id,
                        spot_json,
                        strategy_gz,
                        game_value,
                        exploitability,
                        iterations,
                        abstraction_tier,
                        solver_version,
                        _SCHEMA_VERSION,
                        created_at,
                        board_signature,
                        stack_bb,
                        bet_menu_hash,
                        street,
                        spot.label,
                    ),
                )
                self._conn.execute("COMMIT")
            except Exception:
                # Best-effort rollback; the BEGIN may already be closed by
                # an earlier ROLLBACK (the duplicate-error path).
                with contextlib.suppress(sqlite3.OperationalError):
                    self._conn.execute("ROLLBACK")
                raise
        return spot_id

    def get(self, spot: SpotDescription | str) -> SolveResult | None:
        """Retrieve a SolveResult by spot description or raw spot_id hex."""
        assert self._conn is not None
        spot_id = spot if isinstance(spot, str) else _compute_spot_id(spot)
        row = self._conn.execute(
            """
            SELECT strategy_gz, game_value, exploitability, iterations,
                   solver_version
              FROM spots WHERE id = ?
            """,
            (spot_id,),
        ).fetchone()
        if row is None:
            return None
        current = _current_solver_version()
        stored_version = str(row["solver_version"])
        if stored_version != current:
            warnings.warn(
                f"loaded spot was solved by solver_version {stored_version}; "
                f"current is {current}; strategy is still mathematically valid",
                UserWarning,
                stacklevel=2,
            )
        average_strategy = _deserialize_strategy(bytes(row["strategy_gz"]))
        from poker_solver.solver import SolveResult

        return SolveResult(
            average_strategy=average_strategy,
            exploitability_history=(
                [float(row["exploitability"])]
                if row["exploitability"] == row["exploitability"]  # NaN-safe
                else []
            ),
            game_value=float(row["game_value"]),
            iterations=int(row["iterations"]),
            backend="library",
        )

    def list(
        self,
        filter: LibraryFilter | None = None,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[SpotMetadata]:
        """List spots matching ``filter`` (most-recent first)."""
        assert self._conn is not None
        f = filter or LibraryFilter()
        clauses: list[str] = []
        params: list[Any] = []
        if f.street is not None:
            clauses.append("street = ?")
            params.append(f.street)
        if f.stack_bb_min is not None:
            clauses.append("stack_bb >= ?")
            params.append(int(f.stack_bb_min))
        if f.stack_bb_max is not None:
            clauses.append("stack_bb <= ?")
            params.append(int(f.stack_bb_max))
        if f.solver_version is not None:
            clauses.append("solver_version = ?")
            params.append(f.solver_version)
        if f.created_after is not None:
            clauses.append("created_at >= ?")
            params.append(int(f.created_after))
        if f.board_pattern is not None:
            clauses.append("board_signature REGEXP ?")
            params.append(f.board_pattern)
        if f.label_pattern is not None:
            clauses.append("label REGEXP ?")
            params.append(f.label_pattern)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        # SQLite ships without a default REGEXP — install a per-connection
        # function so the index-friendly path stays in pure Python.
        if "REGEXP" in where:
            self._conn.create_function("REGEXP", 2, _regex_match)
        sql = (
            "SELECT id, label, street, board_signature, stack_bb, game_value, "
            "       exploitability, iterations, abstraction_tier, solver_version, "
            "       created_at"
            f"  FROM spots{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([int(limit), int(offset)])
        rows = self._conn.execute(sql, params).fetchall()
        return [
            SpotMetadata(
                spot_id=str(r["id"]),
                label=str(r["label"]),
                street=str(r["street"]),
                board_signature=str(r["board_signature"]),
                stack_bb=int(r["stack_bb"]),
                game_value=float(r["game_value"]),
                exploitability=float(r["exploitability"]),
                iterations=int(r["iterations"]),
                abstraction_tier=str(r["abstraction_tier"]),
                solver_version=str(r["solver_version"]),
                created_at=int(r["created_at"]),
            )
            for r in rows
        ]

    def export(self, spot_id: str, path: Path) -> None:
        """Write a portable single-spot JSON file (uncompressed)."""
        assert self._conn is not None
        row = self._conn.execute(
            """
            SELECT spot_json, strategy_gz, game_value, exploitability, iterations,
                   abstraction_tier, solver_version, schema_version, created_at,
                   board_signature, stack_bb, street, label
              FROM spots WHERE id = ?
            """,
            (spot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(spot_id)
        spot_dict = json.loads(bytes(row["spot_json"]).decode("utf-8"))
        strategy = _deserialize_strategy(bytes(row["strategy_gz"]))
        exploitability = float(row["exploitability"])
        history = [exploitability] if exploitability == exploitability else []
        payload = {
            "spot_description": spot_dict,
            "solve_result": {
                "average_strategy": strategy,
                "game_value": float(row["game_value"]),
                "exploitability_history": history,
                "iterations": int(row["iterations"]),
                "backend": "library",
            },
            "metadata": {
                "spot_id": spot_id,
                "solver_version": str(row["solver_version"]),
                "schema_version": int(row["schema_version"]),
                "created_at": int(row["created_at"]),
                "abstraction_tier": str(row["abstraction_tier"]),
                "board_signature": str(row["board_signature"]),
                "stack_bb": int(row["stack_bb"]),
                "street": str(row["street"]),
                "label": str(row["label"]),
            },
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))

    def import_(self, path: Path, *, overwrite: bool = False) -> str:
        """Import a JSON file produced by ``export``. Returns the new spot_id."""
        try:
            text = Path(path).read_text()
            payload = json.loads(text)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"could not load {path}: {e}") from e
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: expected a JSON object at top level")
        for key in ("spot_description", "solve_result", "metadata"):
            if key not in payload:
                raise ValueError(f"{path}: missing required key {key!r}")
        spot = _dict_to_spot(payload["spot_description"])
        result = _dict_to_result(payload["solve_result"])
        recomputed = _compute_spot_id(spot)
        claimed = str(payload["metadata"].get("spot_id", ""))
        if claimed and claimed != recomputed:
            warnings.warn(
                f"imported spot_id {claimed} mismatches recomputed {recomputed}; "
                "source canonicalization may differ from this version",
                UserWarning,
                stacklevel=2,
            )
        return self.put(spot, result, overwrite=overwrite)

    def delete(self, spot_id: str) -> None:
        """Delete by id. Raises KeyError if not found."""
        assert self._conn is not None
        with self._write_lock:
            self._conn.execute("BEGIN")
            try:
                cur = self._conn.execute("DELETE FROM spots WHERE id = ?", (spot_id,))
                if cur.rowcount == 0:
                    self._conn.execute("ROLLBACK")
                    raise KeyError(spot_id)
                self._conn.execute("COMMIT")
            except Exception:
                with contextlib.suppress(sqlite3.OperationalError):
                    self._conn.execute("ROLLBACK")
                raise

    def stats(self) -> LibraryStats:
        """Aggregate counts, sizes, and per-street / per-version breakdown."""
        assert self._conn is not None
        total_row = self._conn.execute(
            "SELECT COUNT(*) AS n, "
            "       COALESCE(SUM(LENGTH(strategy_gz) + LENGTH(spot_json)), 0) AS sz, "
            "       MIN(created_at) AS oldest, MAX(created_at) AS newest "
            "  FROM spots"
        ).fetchone()
        by_street: dict[str, int] = {}
        for r in self._conn.execute(
            "SELECT street, COUNT(*) AS n FROM spots GROUP BY street"
        ):
            by_street[str(r["street"])] = int(r["n"])
        by_solver: dict[str, int] = {}
        for r in self._conn.execute(
            "SELECT solver_version, COUNT(*) AS n FROM spots GROUP BY solver_version"
        ):
            by_solver[str(r["solver_version"])] = int(r["n"])
        return LibraryStats(
            total_count=int(total_row["n"]),
            total_size_bytes=int(total_row["sz"]),
            by_street=by_street,
            by_solver_version=by_solver,
            oldest_created_at=(
                int(total_row["oldest"]) if total_row["oldest"] is not None else None
            ),
            newest_created_at=(
                int(total_row["newest"]) if total_row["newest"] is not None else None
            ),
        )

    def close(self) -> None:
        """Close the SQLite connection. Idempotent."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Library:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------- Small helpers ----------


def _regex_match(pattern: str, value: str) -> bool:
    """REGEXP UDF for SQLite (Python's ``re`` semantics, .search())."""
    if value is None:
        return False
    import re

    try:
        return re.search(pattern, value) is not None
    except re.error:
        return False


# Public re-exports tested by Agent C.
__all__ = [
    "Library",
    "LibraryDuplicateError",
    "LibraryError",
    "LibraryFilter",
    "LibrarySchemaError",
    "LibraryStats",
    "SpotDescription",
    "SpotMetadata",
    "_compute_spot_id",
    "_resolve_library_path",
]


# ``replace`` is imported for clients that want to clone descriptions
# (e.g. relabel a SpotDescription without rebuilding the whole config).
# Exposed at module scope so type-checkers can see the dataclass helper.
_ = replace
