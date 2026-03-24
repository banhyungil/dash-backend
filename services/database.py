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

    -- Vibration events
    max_vib_x       REAL,
    max_vib_z       REAL,
    high_vib_event  INTEGER DEFAULT 0,

    -- Vibration stats (Phase 5: ingest 시 계산)
    -- rms / peak
    pulse_x_rms     REAL DEFAULT 0,
    pulse_y_rms     REAL DEFAULT 0,
    pulse_z_rms     REAL DEFAULT 0,
    vib_x_rms       REAL DEFAULT 0,
    vib_z_rms       REAL DEFAULT 0,
    pulse_x_peak    REAL DEFAULT 0,
    pulse_y_peak    REAL DEFAULT 0,
    pulse_z_peak    REAL DEFAULT 0,
    vib_x_peak      REAL DEFAULT 0,
    vib_z_peak      REAL DEFAULT 0,
    -- min / max
    pulse_x_min     REAL DEFAULT 0,
    pulse_y_min     REAL DEFAULT 0,
    pulse_z_min     REAL DEFAULT 0,
    vib_x_min       REAL DEFAULT 0,
    vib_z_min       REAL DEFAULT 0,
    pulse_x_max     REAL DEFAULT 0,
    pulse_y_max     REAL DEFAULT 0,
    pulse_z_max     REAL DEFAULT 0,
    vib_x_max       REAL DEFAULT 0,
    vib_z_max       REAL DEFAULT 0,
    -- q1 / median / q3
    pulse_x_q1      REAL DEFAULT 0,
    pulse_y_q1      REAL DEFAULT 0,
    pulse_z_q1      REAL DEFAULT 0,
    vib_x_q1        REAL DEFAULT 0,
    vib_z_q1        REAL DEFAULT 0,
    pulse_x_median  REAL DEFAULT 0,
    pulse_y_median  REAL DEFAULT 0,
    pulse_z_median  REAL DEFAULT 0,
    vib_x_median    REAL DEFAULT 0,
    vib_z_median    REAL DEFAULT 0,
    pulse_x_q3      REAL DEFAULT 0,
    pulse_y_q3      REAL DEFAULT 0,
    pulse_z_q3      REAL DEFAULT 0,
    vib_x_q3        REAL DEFAULT 0,
    vib_z_q3        REAL DEFAULT 0,
    -- exceed (threshold 초과 통계)
    pulse_x_exceed_count    INTEGER DEFAULT 0,
    pulse_y_exceed_count    INTEGER DEFAULT 0,
    pulse_z_exceed_count    INTEGER DEFAULT 0,
    vib_x_exceed_count      INTEGER DEFAULT 0,
    vib_z_exceed_count      INTEGER DEFAULT 0,
    pulse_x_exceed_ratio    REAL DEFAULT 0,
    pulse_y_exceed_ratio    REAL DEFAULT 0,
    pulse_z_exceed_ratio    REAL DEFAULT 0,
    vib_x_exceed_ratio      REAL DEFAULT 0,
    vib_z_exceed_ratio      REAL DEFAULT 0,
    pulse_x_exceed_duration_ms  REAL DEFAULT 0,
    pulse_y_exceed_duration_ms  REAL DEFAULT 0,
    pulse_z_exceed_duration_ms  REAL DEFAULT 0,
    vib_x_exceed_duration_ms    REAL DEFAULT 0,
    vib_z_exceed_duration_ms    REAL DEFAULT 0,
    -- burst / peak impact
    burst_count     INTEGER DEFAULT 0,
    peak_impact_count INTEGER DEFAULT 0,

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

CREATE TABLE IF NOT EXISTS t_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'string',
    label       TEXT,
    category    TEXT
);
"""

# 설정 초기값 (config.py 하드코딩 → DB 이관)
_DEFAULT_SETTINGS = [
    ("shaft_dia", "50", "number", "축 지름 (mm)", "equipment"),
    ("pattern_width", "10", "number", "패턴 폭 (mm)", "equipment"),
    ("target_rpm", "100", "number", "목표 RPM", "equipment"),
    ("roll_diameter", "140", "number", "롤러 지름 (mm)", "equipment"),
    ("expected_tolerance", "0.1", "number", "유효 판정 허용 오차", "validation"),
    ("device_session_map", '{"0013A20041F71B01":"R1","0013A20041F9D466":"R2","0013A20041F98275":"R3","0013A20041F9D4F8":"R4"}', "json", "디바이스→세션 매핑", "device"),
    ("gravity_offset", '{"R1":{"z":-1.0},"R2":{"z":-1.0},"R3":{"z":0.0},"R4":{"z":0.0}}', "json", "중력 보정값", "device"),
    ("rpm_error_bands", '[{"val":10,"label":"stage01","color":"#DDCC00"},{"val":20,"label":"stage02","color":"#FF5E00"},{"val":30,"label":"stage03","color":"#FF0000"}]', "json", "RPM 허용 밴드", "validation"),
]


def init_db():
    """Initialize database schema and seed default settings."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        # 초기 설정값 seed (이미 존재하면 무시)
        conn.executemany(
            "INSERT OR IGNORE INTO t_settings (key, value, type, label, category) VALUES (?, ?, ?, ?, ?)",
            _DEFAULT_SETTINGS,
        )
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()
