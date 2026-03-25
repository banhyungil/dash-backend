"""Repository for t_cycle table CRUD and queries."""
from services import database
from services.settings_service import get_setting


_STAT_AXES = ("pulse_x", "pulse_y", "pulse_z", "vib_x", "vib_z")
_STAT_FIELDS = ("rms", "peak", "min", "max", "q1", "median", "q3",
                "exceed_count", "exceed_ratio", "exceed_duration_ms")
_STAT_COLUMNS = [f"{ax}_{f}" for ax in _STAT_AXES for f in _STAT_FIELDS]

_INSERT_SQL = """
    INSERT INTO t_cycle (
        timestamp, date, month, device, device_name, cycle_index,
        rpm_mean, rpm_min, rpm_max,
        mpm_mean, mpm_min, mpm_max,
        duration_ms, set_count, expected_count,
        max_vib_x, max_vib_z,
        {stat_cols},
        burst_count, peak_impact_count
    ) VALUES (
        %(timestamp)s, %(date)s, %(month)s, %(device)s, %(device_name)s, %(cycle_index)s,
        %(rpm_mean)s, %(rpm_min)s, %(rpm_max)s,
        %(mpm_mean)s, %(mpm_min)s, %(mpm_max)s,
        %(duration_ms)s, %(set_count)s, %(expected_count)s,
        %(max_vib_x)s, %(max_vib_z)s,
        {stat_params},
        %(burst_count)s, %(peak_impact_count)s
    )
    ON CONFLICT (device, date, cycle_index) DO UPDATE SET
        timestamp = EXCLUDED.timestamp,
        device_name = EXCLUDED.device_name,
        rpm_mean = EXCLUDED.rpm_mean, rpm_min = EXCLUDED.rpm_min, rpm_max = EXCLUDED.rpm_max,
        mpm_mean = EXCLUDED.mpm_mean, mpm_min = EXCLUDED.mpm_min, mpm_max = EXCLUDED.mpm_max,
        duration_ms = EXCLUDED.duration_ms, set_count = EXCLUDED.set_count,
        expected_count = EXCLUDED.expected_count,
        max_vib_x = EXCLUDED.max_vib_x, max_vib_z = EXCLUDED.max_vib_z,
        burst_count = EXCLUDED.burst_count, peak_impact_count = EXCLUDED.peak_impact_count
    RETURNING id
""".format(
    stat_cols=", ".join(_STAT_COLUMNS),
    stat_params=", ".join(f"%({c})s" for c in _STAT_COLUMNS),
)


def insert_many(cycles: list[dict], conn=None) -> list[int]:
    """Bulk insert cycles. Returns list of inserted/upserted row ids.
    If conn is provided, does NOT commit (caller manages tx)."""
    if not cycles:
        return []

    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    try:
        ids = []
        for cycle in cycles:
            row = conn.execute(_INSERT_SQL, cycle).fetchone()  # type: ignore[arg-type]
            if row:
                ids.append(row["id"])
        if own_conn:
            conn.commit()
        return ids
    finally:
        if own_conn:
            conn.close()


def get_months() -> list[dict]:
    """적재된 월 목록 조회."""
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT month,
                   COUNT(DISTINCT date) AS date_count,
                   COUNT(*) AS cycle_count
            FROM t_cycle
            GROUP BY month
            ORDER BY month
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_dates(month: str) -> list[dict]:
    """특정 월의 날짜 목록 조회."""
    threshold = get_setting("vib_threshold")
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT date,
                   COUNT(*) AS cycle_count,
                   SUM(CASE WHEN max_vib_x > %s OR max_vib_z > %s THEN 1 ELSE 0 END) AS high_vib_events
            FROM t_cycle
            WHERE month = %s
            GROUP BY date
            ORDER BY date
        """, (threshold, threshold, month)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_by_date(month: str, date: str) -> list[dict]:
    """특정 날짜의 사이클 집계값 조회."""
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT id, timestamp, date, month, device, device_name, cycle_index,
                   rpm_mean, rpm_min, rpm_max,
                   mpm_mean, mpm_min, mpm_max,
                   duration_ms, set_count, expected_count,
                   max_vib_x, max_vib_z,
                   {stat_cols},
                   burst_count, peak_impact_count
            FROM t_cycle
            WHERE month = %s AND date = %s
            ORDER BY timestamp
        """.format(stat_cols=", ".join(_STAT_COLUMNS)), (month, date)).fetchall()  # type: ignore[arg-type]
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_one(date: str, device_name: str, cycle_index: int) -> dict | None:
    """특정 사이클 1건 조회."""
    conn = database.get_connection()
    try:
        row = conn.execute("""
            SELECT id, timestamp, date, month, device, device_name, cycle_index,
                   rpm_mean, rpm_min, rpm_max,
                   mpm_mean, mpm_min, mpm_max,
                   duration_ms, set_count, expected_count,
                   max_vib_x, max_vib_z
            FROM t_cycle
            WHERE date = %s AND device_name = %s AND cycle_index = %s
        """, (date, device_name, cycle_index)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_monthly_summary() -> dict:
    """Get ingestion status summary by month."""
    threshold = get_setting("vib_threshold")
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT
                month,
                COUNT(DISTINCT date) AS date_count,
                COUNT(*) AS total_cycles,
                SUM(CASE WHEN max_vib_x > %s OR max_vib_z > %s THEN 1 ELSE 0 END) AS high_vib_events
            FROM t_cycle
            GROUP BY month
            ORDER BY month
        """, (threshold, threshold)).fetchall()

        months = [dict(row) for row in rows]
        total_dates = sum(m["date_count"] for m in months)
        total_cycles = sum(m["total_cycles"] for m in months)

        return {
            "months": months,
            "total_dates": total_dates,
            "total_cycles": total_cycles,
        }
    finally:
        conn.close()
