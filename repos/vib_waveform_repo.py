"""Repository for t_vib_waveform table — VIB 파형 BYTEA 저장/조회."""
import struct
from services import database


def insert(cycle_id: int, accel_x: list[float], accel_z: list[float], conn=None) -> None:
    """VIB 파형을 BYTEA로 변환하여 저장."""
    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    try:
        x_bytes = struct.pack(f"{len(accel_x)}d", *accel_x)
        z_bytes = struct.pack(f"{len(accel_z)}d", *accel_z)
        conn.execute(
            """INSERT INTO t_vib_waveform (cycle_id, accel_x, accel_z, sample_count)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (cycle_id) DO UPDATE SET
                   accel_x = EXCLUDED.accel_x,
                   accel_z = EXCLUDED.accel_z,
                   sample_count = EXCLUDED.sample_count""",
            (cycle_id, x_bytes, z_bytes, len(accel_x)),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
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
    count = len(b) // 8  # double = 8 bytes
    return list(struct.unpack(f"{count}d", b))
