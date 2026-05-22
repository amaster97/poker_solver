-- PR 11 library schema (single-user, single-machine SQLite cache).
-- Loaded via Library.open() with executescript(); every CREATE is
-- IF NOT EXISTS so re-running on an existing DB is a no-op.
--
-- The journal_mode pragma is *not* persistent across connections in
-- WAL mode; Library.open() also sets it programmatically. The PRAGMA
-- here is documentation + first-connection convenience.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS spots (
    id                  TEXT PRIMARY KEY,
    spot_json           BLOB NOT NULL,
    strategy_gz         BLOB NOT NULL,
    game_value          REAL NOT NULL,
    exploitability      REAL NOT NULL,
    iterations          INTEGER NOT NULL,
    abstraction_tier    TEXT NOT NULL,
    solver_version      TEXT NOT NULL,
    schema_version      INTEGER NOT NULL,
    created_at          INTEGER NOT NULL,
    board_signature     TEXT NOT NULL,
    stack_bb            INTEGER NOT NULL,
    bet_menu_hash       TEXT NOT NULL,
    street              TEXT NOT NULL,
    label               TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_spots_board    ON spots(board_signature);
CREATE INDEX IF NOT EXISTS idx_spots_street   ON spots(street);
CREATE INDEX IF NOT EXISTS idx_spots_stack    ON spots(stack_bb);
CREATE INDEX IF NOT EXISTS idx_spots_created  ON spots(created_at);
CREATE INDEX IF NOT EXISTS idx_spots_solver   ON spots(solver_version);

CREATE TABLE IF NOT EXISTS spots_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
