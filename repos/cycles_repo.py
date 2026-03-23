"""Repository for t_cycle table CRUD and queries."""
from services import database


def insert_many(cycles: list[dict]) -> int:
    """Bulk insert cycles. Returns number of inserted rows."""
    if not cycles:
        return 0

    conn = database.get_connection()
    try:
        cursor = conn.executemany("""
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
        """, cycles)
        conn.commit()
        return cursor.rowcount
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
