"""Repository for t_settings table."""
import json
from typing import Any
from services import database


def get_all() -> list[dict]:
    """전체 설정 조회."""
    conn = database.get_connection()
    try:
        rows = conn.execute("SELECT key, value, type, label, category FROM t_settings ORDER BY category, key").fetchall()
        return [_parse_row(dict(r)) for r in rows]
    finally:
        conn.close()


def get(key: str, default: Any = None) -> Any:
    """단일 설정값 조회. type에 따라 자동 변환."""
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT value, type FROM t_settings WHERE key = %s", (key,)).fetchone()
        if not row:
            return default
        return _cast(row["value"], row["type"])
    finally:
        conn.close()


def set(key: str, value: Any) -> None:
    """설정값 업데이트."""
    conn = database.get_connection()
    try:
        str_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        conn.execute("UPDATE t_settings SET value = %s WHERE key = %s", (str_value, key))
        conn.commit()
    finally:
        conn.close()


def reset_all() -> None:
    """모든 설정을 초기값으로 리셋."""
    conn = database.get_connection()
    try:
        conn.execute("DELETE FROM t_settings")
        for row in database._DEFAULT_SETTINGS:
            conn.execute(
                "INSERT INTO t_settings (key, value, type, label, category) VALUES (%s, %s, %s, %s, %s)",
                row,
            )
        conn.commit()
    finally:
        conn.close()


def _cast(value: str, type_: str) -> Any:
    """type 필드에 따라 문자열을 적절한 타입으로 변환."""
    if type_ == "number":
        return float(value) if "." in value else int(value)
    if type_ == "json":
        return json.loads(value)
    return value


def _parse_row(row: dict) -> dict:
    """DB row를 프론트 응답 형식으로 변환."""
    row["value"] = _cast(row["value"], row["type"])
    return row
