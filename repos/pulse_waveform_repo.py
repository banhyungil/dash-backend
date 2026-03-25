"""Repository for t_pulse_waveform table — PULSE 원시 파형 BYTEA 저장/조회."""
import struct
from services import database


def insert(cycle_id: int, pulses: list[int], accel_x: list[float],
           accel_y: list[float], accel_z: list[float], conn=None) -> None:
    """PULSE 원시 배열을 BYTEA로 변환하여 저장."""
    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    try:
        p_bytes = struct.pack(f"{len(pulses)}i", *pulses)
        x_bytes = struct.pack(f"{len(accel_x)}d", *accel_x)
        y_bytes = struct.pack(f"{len(accel_y)}d", *accel_y)
        z_bytes = struct.pack(f"{len(accel_z)}d", *accel_z)
        conn.execute(
            """INSERT INTO t_pulse_waveform (cycle_id, pulses, accel_x, accel_y, accel_z, sample_count)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (cycle_id) DO UPDATE SET
                   pulses = EXCLUDED.pulses,
                   accel_x = EXCLUDED.accel_x,
                   accel_y = EXCLUDED.accel_y,
                   accel_z = EXCLUDED.accel_z,
                   sample_count = EXCLUDED.sample_count""",
            (cycle_id, p_bytes, x_bytes, y_bytes, z_bytes, len(pulses)),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def find_by_cycle_id(cycle_id: int) -> dict | None:
    """cycle_id로 PULSE 파형 조회. 배열로 디코딩하여 반환."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT pulses, accel_x, accel_y, accel_z, sample_count FROM t_pulse_waveform WHERE cycle_id = %s",
            (cycle_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "pulses": _bytes_to_ints(row["pulses"]),
            "accel_x": _bytes_to_floats(row["accel_x"]),
            "accel_y": _bytes_to_floats(row["accel_y"]),
            "accel_z": _bytes_to_floats(row["accel_z"]),
            "sample_count": row["sample_count"],
        }
    finally:
        conn.close()


def _bytes_to_ints(data: bytes | memoryview | None) -> list[int]:
    """BYTEA → int 배열 디코딩."""
    if not data:
        return []
    b = bytes(data) if isinstance(data, memoryview) else data
    count = len(b) // 4  # int = 4 bytes
    return list(struct.unpack(f"{count}i", b))


def _bytes_to_floats(data: bytes | memoryview | None) -> list[float]:
    """BYTEA → float 배열 디코딩."""
    if not data:
        return []
    b = bytes(data) if isinstance(data, memoryview) else data
    count = len(b) // 8  # double = 8 bytes
    return list(struct.unpack(f"{count}d", b))
