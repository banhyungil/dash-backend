"""PostgreSQL database: connection and schema initialization."""
import logging

import psycopg
from psycopg.rows import dict_row

from config import DATABASE_URL

logger = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection[dict]:
    """Get a PostgreSQL connection with dict row factory."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)  # type: ignore[call-overload]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS t_cycle (
    id              SERIAL PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    date            TEXT NOT NULL,
    month           TEXT NOT NULL,
    device          TEXT NOT NULL,
    device_name     TEXT NOT NULL,
    cycle_index     INTEGER NOT NULL,

    -- RPM/MPM aggregates
    rpm_mean        DOUBLE PRECISION,
    rpm_min         DOUBLE PRECISION,
    rpm_max         DOUBLE PRECISION,
    mpm_mean        DOUBLE PRECISION,
    mpm_min         DOUBLE PRECISION,
    mpm_max         DOUBLE PRECISION,

    -- Cycle metadata
    duration_ms     DOUBLE PRECISION,
    set_count       INTEGER,
    expected_count  INTEGER,

    -- Vibration peaks
    max_vib_x       DOUBLE PRECISION,
    max_vib_z       DOUBLE PRECISION,

    -- Vibration stats (ingest 시 계산)
    -- rms / peak
    pulse_x_rms     DOUBLE PRECISION DEFAULT 0,
    pulse_y_rms     DOUBLE PRECISION DEFAULT 0,
    pulse_z_rms     DOUBLE PRECISION DEFAULT 0,
    vib_x_rms       DOUBLE PRECISION DEFAULT 0,
    vib_z_rms       DOUBLE PRECISION DEFAULT 0,
    pulse_x_peak    DOUBLE PRECISION DEFAULT 0,
    pulse_y_peak    DOUBLE PRECISION DEFAULT 0,
    pulse_z_peak    DOUBLE PRECISION DEFAULT 0,
    vib_x_peak      DOUBLE PRECISION DEFAULT 0,
    vib_z_peak      DOUBLE PRECISION DEFAULT 0,
    -- min / max
    pulse_x_min     DOUBLE PRECISION DEFAULT 0,
    pulse_y_min     DOUBLE PRECISION DEFAULT 0,
    pulse_z_min     DOUBLE PRECISION DEFAULT 0,
    vib_x_min       DOUBLE PRECISION DEFAULT 0,
    vib_z_min       DOUBLE PRECISION DEFAULT 0,
    pulse_x_max     DOUBLE PRECISION DEFAULT 0,
    pulse_y_max     DOUBLE PRECISION DEFAULT 0,
    pulse_z_max     DOUBLE PRECISION DEFAULT 0,
    vib_x_max       DOUBLE PRECISION DEFAULT 0,
    vib_z_max       DOUBLE PRECISION DEFAULT 0,
    -- q1 / median / q3
    pulse_x_q1      DOUBLE PRECISION DEFAULT 0,
    pulse_y_q1      DOUBLE PRECISION DEFAULT 0,
    pulse_z_q1      DOUBLE PRECISION DEFAULT 0,
    vib_x_q1        DOUBLE PRECISION DEFAULT 0,
    vib_z_q1        DOUBLE PRECISION DEFAULT 0,
    pulse_x_median  DOUBLE PRECISION DEFAULT 0,
    pulse_y_median  DOUBLE PRECISION DEFAULT 0,
    pulse_z_median  DOUBLE PRECISION DEFAULT 0,
    vib_x_median    DOUBLE PRECISION DEFAULT 0,
    vib_z_median    DOUBLE PRECISION DEFAULT 0,
    pulse_x_q3      DOUBLE PRECISION DEFAULT 0,
    pulse_y_q3      DOUBLE PRECISION DEFAULT 0,
    pulse_z_q3      DOUBLE PRECISION DEFAULT 0,
    vib_x_q3        DOUBLE PRECISION DEFAULT 0,
    vib_z_q3        DOUBLE PRECISION DEFAULT 0,
    -- exceed (threshold 초과 통계)
    pulse_x_exceed_count    INTEGER DEFAULT 0,
    pulse_y_exceed_count    INTEGER DEFAULT 0,
    pulse_z_exceed_count    INTEGER DEFAULT 0,
    vib_x_exceed_count      INTEGER DEFAULT 0,
    vib_z_exceed_count      INTEGER DEFAULT 0,
    pulse_x_exceed_ratio    DOUBLE PRECISION DEFAULT 0,
    pulse_y_exceed_ratio    DOUBLE PRECISION DEFAULT 0,
    pulse_z_exceed_ratio    DOUBLE PRECISION DEFAULT 0,
    vib_x_exceed_ratio      DOUBLE PRECISION DEFAULT 0,
    vib_z_exceed_ratio      DOUBLE PRECISION DEFAULT 0,
    pulse_x_exceed_duration_ms  DOUBLE PRECISION DEFAULT 0,
    pulse_y_exceed_duration_ms  DOUBLE PRECISION DEFAULT 0,
    pulse_z_exceed_duration_ms  DOUBLE PRECISION DEFAULT 0,
    vib_x_exceed_duration_ms    DOUBLE PRECISION DEFAULT 0,
    vib_z_exceed_duration_ms    DOUBLE PRECISION DEFAULT 0,
    -- burst / peak impact
    burst_count     INTEGER DEFAULT 0,
    peak_impact_count INTEGER DEFAULT 0,

    -- Source tracking
    source_path     TEXT,

    UNIQUE(device, date, cycle_index)
);

CREATE INDEX IF NOT EXISTS idx_t_cycle_date ON t_cycle(date);
CREATE INDEX IF NOT EXISTS idx_t_cycle_month ON t_cycle(month);
CREATE INDEX IF NOT EXISTS idx_t_cycle_device_name ON t_cycle(device_name);
CREATE INDEX IF NOT EXISTS idx_t_cycle_timestamp ON t_cycle(timestamp);
CREATE INDEX IF NOT EXISTS idx_t_cycle_source ON t_cycle(source_path);

CREATE TABLE IF NOT EXISTS t_vib_waveform (
    id              SERIAL PRIMARY KEY,
    cycle_id        INTEGER NOT NULL REFERENCES t_cycle(id) ON DELETE CASCADE,
    accel_x         BYTEA,
    accel_z         BYTEA,
    sample_count    INTEGER,
    UNIQUE(cycle_id)
);

CREATE TABLE IF NOT EXISTS h_ingested_file (
    id          SERIAL PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    filename    TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    ingested_at TIMESTAMP NOT NULL DEFAULT NOW(),
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
    ("device_name_map", '{"0013A20041F71B01":"R1","0013A20041F9D466":"R2","0013A20041F98275":"R3","0013A20041F9D4F8":"R4"}', "json", "디바이스→이름 매핑", "device"),
    ("gravity_offset", '{"R1":{"z":-1.0},"R2":{"z":-1.0},"R3":{"z":0.0},"R4":{"z":0.0}}', "json", "중력 보정값", "device"),
    ("rpm_error_bands", '[{"val":10,"label":"stage01","color":"#DDCC00"},{"val":20,"label":"stage02","color":"#FF5E00"},{"val":30,"label":"stage03","color":"#FF0000"}]', "json", "RPM 허용 밴드", "validation"),
    ("vib_threshold", "0.3", "number", "고진동 임계값(g)", "vibration"),
]


def init_db():
    """Initialize database schema and seed default settings."""
    conn = get_connection()
    try:
        conn.execute(SCHEMA_SQL)
        # 초기 설정값 seed (이미 존재하면 무시)
        for row in _DEFAULT_SETTINGS:
            conn.execute(
                "INSERT INTO t_settings (key, value, type, label, category) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
                row,
            )
        conn.commit()
        logger.info("Database initialized (PostgreSQL)")
    finally:
        conn.close()
