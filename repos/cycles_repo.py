"""Repository for t_cycle table CRUD and queries."""
from services import database


_INSERT_SQL = """
    INSERT OR REPLACE INTO t_cycle (
        timestamp, date, month, device, session, cycle_index,
        rpm_mean, rpm_min, rpm_max,
        mpm_mean, mpm_min, mpm_max,
        duration_ms, set_count, expected_count, is_valid,
        max_vib_x, max_vib_z, high_vib_event,
        source_path
    ) VALUES (
        :timestamp, :date, :month, :device, :session, :cycle_index,
        :rpm_mean, :rpm_min, :rpm_max,
        :mpm_mean, :mpm_min, :mpm_max,
        :duration_ms, :set_count, :expected_count, :is_valid,
        :max_vib_x, :max_vib_z, :high_vib_event,
        :source_path
    )
"""


def insert_many(cycles: list[dict], conn=None) -> int:
    """Bulk insert cycles. If conn is provided, does NOT commit (caller manages tx)."""
    if not cycles:
        return 0

    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    try:
        cursor = conn.executemany(_INSERT_SQL, cycles)
        if own_conn:
            conn.commit()
        return cursor.rowcount
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
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT date,
                   COUNT(*) AS cycle_count,
                   SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) AS valid_count
            FROM t_cycle
            WHERE month = ?
            GROUP BY date
            ORDER BY date
        """, (month,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_by_date(month: str, date: str) -> list[dict]:
    """특정 날짜의 사이클 집계값 조회."""
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT timestamp, date, month, device, session, cycle_index,
                   rpm_mean, rpm_min, rpm_max,
                   mpm_mean, mpm_min, mpm_max,
                   duration_ms, set_count, expected_count, is_valid,
                   max_vib_x, max_vib_z, high_vib_event,
                   source_path
            FROM t_cycle
            WHERE month = ? AND date = ?
            ORDER BY timestamp
        """, (month, date)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_monthly_summary() -> dict:
    """Get ingestion status summary by month."""
    conn = database.get_connection()
    try:
        rows = conn.execute("""
            SELECT
                month,
                COUNT(DISTINCT date) AS date_count,
                COUNT(*) AS total_cycles,
                SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END) AS valid_cycles,
                SUM(CASE WHEN high_vib_event = 1 THEN 1 ELSE 0 END) AS high_vib_events
            FROM t_cycle
            GROUP BY month
            ORDER BY month
        """).fetchall()

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
