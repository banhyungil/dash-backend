"""SQLite database: connection and schema initialization."""
import sqlite3
import logging

from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS t_cycle (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    date            TEXT NOT NULL,
    month           TEXT NOT NULL,
    device          TEXT NOT NULL,
    session         TEXT NOT NULL,
    cycle_index     INTEGER NOT NULL,

    -- RPM/MPM aggregates
    rpm_mean        REAL,
    rpm_min         REAL,
    rpm_max         REAL,
    mpm_mean        REAL,
    mpm_min         REAL,
    mpm_max         REAL,

    -- Cycle metadata
    duration_ms     REAL,
    set_count       INTEGER,
    expected_count  INTEGER,
    is_valid        INTEGER DEFAULT 1,

    -- Vibration events
    max_vib_x       REAL,
    max_vib_z       REAL,
    high_vib_event  INTEGER DEFAULT 0,

    -- Source tracking
    source_path     TEXT,

    UNIQUE(device, date, cycle_index)
);

CREATE INDEX IF NOT EXISTS idx_t_cycle_date ON t_cycle(date);
CREATE INDEX IF NOT EXISTS idx_t_cycle_month ON t_cycle(month);
CREATE INDEX IF NOT EXISTS idx_t_cycle_session ON t_cycle(session);
CREATE INDEX IF NOT EXISTS idx_t_cycle_timestamp ON t_cycle(timestamp);
CREATE INDEX IF NOT EXISTS idx_t_cycle_source ON t_cycle(source_path);

CREATE TABLE IF NOT EXISTS h_ingested_file (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL UNIQUE,
    filename    TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    cycles_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);
"""


def init_db():
    """Initialize database schema."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()
