-- h_ingested_file definition

CREATE TABLE h_ingested_file (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL UNIQUE,
    filename    TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    cycles_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);


-- t_cycle definition

CREATE TABLE t_cycle (
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

    -- Source tracking
    source_path     TEXT,

    UNIQUE(device, date, cycle_index)
);

CREATE INDEX idx_t_cycle_date ON t_cycle(date);
CREATE INDEX idx_t_cycle_month ON t_cycle(month);
CREATE INDEX idx_t_cycle_session ON t_cycle(session);
CREATE INDEX idx_t_cycle_timestamp ON t_cycle(timestamp);
CREATE INDEX idx_t_cycle_source ON t_cycle(source_path);