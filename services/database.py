"""PostgreSQL database: connection and schema initialization."""
import logging

import psycopg
from psycopg.rows import dict_row

from config import DATABASE_URL

logger = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection[dict]:
    """Get a PostgreSQL connection with dict row factory."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)  # type: ignore[call-overload]


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


def seed_settings():
    """Seed default settings if not already present."""
    conn = get_connection()
    try:
        for row in _DEFAULT_SETTINGS:
            conn.execute(
                "INSERT INTO t_settings (key, value, type, label, category) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
                row,
            )
        conn.commit()
        logger.info("Default settings seeded")
    finally:
        conn.close()
