"""Repository for t_cycle table CRUD and queries."""
from psycopg.sql import SQL, Identifier, Placeholder
from services import database
from services.settings_service import get_setting


_STAT_AXES = ("pulse_x", "pulse_y", "pulse_z", "vib_x", "vib_z")
_STAT_FIELDS = ("rms", "peak", "min", "max", "q1", "median", "q3",
                "exceed_count", "exceed_ratio", "exceed_duration_ms")
_STAT_COLUMNS = [f"{ax}_{f}" for ax in _STAT_AXES for f in _STAT_FIELDS]

# INSERT 대상 컬럼 순서 (멀티 row VALUES에서 일관된 순서 보장)
_INSERT_COLUMNS = [
    "timestamp", "date", "month", "device", "device_name", "cycle_index",
    "rpm_mean", "rpm_min", "rpm_max",
    "mpm_mean", "mpm_min", "mpm_max",
    "duration_ms", "set_count", "expected_count",
    "max_vib_x", "max_vib_z",
    *_STAT_COLUMNS,
    "burst_count", "peak_impact_count",
]

# 멀티 row VALUES용 SQL 템플릿 (동적으로 row 수만큼 확장)
_COL_LIST = SQL(", ").join(Identifier(c) for c in _INSERT_COLUMNS)
_ONE_ROW = SQL("({})").format(SQL(", ").join(Placeholder() for _ in _INSERT_COLUMNS))


def insert_many(cycles: list[dict], conn=None) -> list[int]:
    """멀티 row VALUES + RETURNING으로 일괄 INSERT.
    conn이 주어지면 커밋하지 않음 (호출자가 관리)."""
    if not cycles:
        return []

    is_own_conn = conn is None
    if is_own_conn:
        conn = database.get_connection()
    try:
        # 멀티 row VALUES 조립
        values_list = SQL(", ").join(_ONE_ROW for _ in cycles)
        query = SQL("INSERT INTO t_cycle ({cols}) VALUES {values} RETURNING id").format(
            cols=_COL_LIST, values=values_list,
        )

        # 파라미터를 flat tuple로 변환 (_INSERT_COLUMNS 순서)
        params: list = []
        for cycle in cycles:
            for col in _INSERT_COLUMNS:
                params.append(cycle.get(col, 0))

        rows = conn.execute(query, params).fetchall()
        ids = [row["id"] for row in rows]

        if is_own_conn:
            conn.commit()
        return ids
    finally:
        if is_own_conn:
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
