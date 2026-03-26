"""Repository for t_vib_waveform table — VIB 파형 BYTEA 저장/조회."""
import struct
from services import database


def insert(cycle_id: int, accel_x_arr: list[float], accel_z_arr: list[float], conn=None) -> None:
    """VIB 파형을 BYTEA로 변환하여 저장 (단건)."""
    is_own_conn = conn is None
    if is_own_conn:
        conn = database.get_connection()
    try:
        x_bytes = struct.pack(f"{len(accel_x_arr)}d", *accel_x_arr)
        z_bytes = struct.pack(f"{len(accel_z_arr)}d", *accel_z_arr)
        conn.execute(
            """INSERT INTO t_vib_waveform (cycle_id, accel_x, accel_z, sample_count)
               VALUES (%s, %s, %s, %s)""",
            (cycle_id, x_bytes, z_bytes, len(accel_x_arr)),
        )
        if is_own_conn:
            conn.commit()
    finally:
        if is_own_conn:
            conn.close()


def insert_many_copy(rows: list[tuple[int, list[float], list[float]]], conn=None) -> None:
    """COPY 프로토콜로 VIB 파형 일괄 저장. conn이 주어지면 커밋하지 않음."""
    if not rows:
        return
    is_own_conn = conn is None
    if is_own_conn:
        conn = database.get_connection()
    try:
        with conn.cursor().copy(
            "COPY t_vib_waveform (cycle_id, accel_x, accel_z, sample_count) FROM STDIN"
        ) as copy:
            for cycle_id, accel_x_arr, accel_z_arr in rows:
                x_bytes = struct.pack(f"{len(accel_x_arr)}d", *accel_x_arr)
                z_bytes = struct.pack(f"{len(accel_z_arr)}d", *accel_z_arr)
                copy.write_row((cycle_id, x_bytes, z_bytes, len(accel_x_arr)))
        if is_own_conn:
            conn.commit()
    finally:
        if is_own_conn:
            conn.close()


def find_by_cycle_id(cycle_id: int) -> dict | None:
    """cycle_id로 VIB 파형 조회. float 배열로 디코딩하여 반환."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT accel_x, accel_z, sample_count FROM t_vib_waveform WHERE cycle_id = %s",
            (cycle_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "accel_x": _bytes_to_floats(row["accel_x"]),
            "accel_z": _bytes_to_floats(row["accel_z"]),
            "sample_count": row["sample_count"],
        }
    finally:
        conn.close()


def _bytes_to_floats(data: bytes | memoryview | None) -> list[float]:
    """BYTEA → float 배열 디코딩."""
    if not data:
        return []
    b = bytes(data) if isinstance(data, memoryview) else data
    # //: 정수 나눗셈
    count = len(b) // 8  # double = 8 bytes
    return list(struct.unpack(f"{count}d", b))
