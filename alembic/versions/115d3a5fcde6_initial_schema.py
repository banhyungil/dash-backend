"""initial schema

Revision ID: 115d3a5fcde6
Revises: 
Create Date: 2026-03-25 17:20:33.124591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '115d3a5fcde6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS t_cycle (
        id              SERIAL PRIMARY KEY,
        timestamp       TEXT NOT NULL,
        date            TEXT NOT NULL,
        month           TEXT NOT NULL,
        device          TEXT NOT NULL,
        device_name     TEXT NOT NULL,
        cycle_index     INTEGER NOT NULL,

        rpm_mean        DOUBLE PRECISION,
        rpm_min         DOUBLE PRECISION,
        rpm_max         DOUBLE PRECISION,
        mpm_mean        DOUBLE PRECISION,
        mpm_min         DOUBLE PRECISION,
        mpm_max         DOUBLE PRECISION,

        duration_ms     DOUBLE PRECISION,
        set_count       INTEGER,
        expected_count  INTEGER,

        max_vib_x       DOUBLE PRECISION,
        max_vib_z       DOUBLE PRECISION,

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
        burst_count     INTEGER DEFAULT 0,
        peak_impact_count INTEGER DEFAULT 0,

        UNIQUE(device, date, cycle_index)
    );

    CREATE INDEX IF NOT EXISTS idx_t_cycle_date ON t_cycle(date);
    CREATE INDEX IF NOT EXISTS idx_t_cycle_month ON t_cycle(month);
    CREATE INDEX IF NOT EXISTS idx_t_cycle_device_name ON t_cycle(device_name);
    CREATE INDEX IF NOT EXISTS idx_t_cycle_timestamp ON t_cycle(timestamp);

    CREATE TABLE IF NOT EXISTS t_pulse_waveform (
        id              SERIAL PRIMARY KEY,
        cycle_id        INTEGER NOT NULL REFERENCES t_cycle(id) ON DELETE CASCADE,
        pulses          BYTEA,
        accel_x         BYTEA,
        accel_y         BYTEA,
        accel_z         BYTEA,
        sample_count    INTEGER,
        UNIQUE(cycle_id)
    );

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
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS t_pulse_waveform CASCADE")
    op.execute("DROP TABLE IF EXISTS t_vib_waveform CASCADE")
    op.execute("DROP TABLE IF EXISTS h_ingested_file CASCADE")
    op.execute("DROP TABLE IF EXISTS t_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS t_cycle CASCADE")
