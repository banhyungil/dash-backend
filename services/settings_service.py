"""DB 설정 조회 서비스. t_settings 테이블에서 값을 읽고, 실패 시 fallback 반환."""

_FALLBACK = {
    "shaft_dia": 50,
    "pattern_width": 10,
    "target_rpm": 100,
    "roll_diameter": 140,
    "expected_tolerance": 0.1,
    "device_session_map": {
        "0013A20041F71B01": "R1",
        "0013A20041F9D466": "R2",
        "0013A20041F98275": "R3",
        "0013A20041F9D4F8": "R4",
    },
    "gravity_offset": {
        "R1": {"z": -1.0},
        "R2": {"z": -1.0},
        "R3": {"z": 0.0},
        "R4": {"z": 0.0},
    },
}


def get_setting(key: str):
    """DB에서 설정값 조회. DB 접근 실패 시 fallback 반환."""
    try:
        from repos.settings_repo import get
        val = get(key)
        if val is not None:
            return val
    except Exception:
        pass
    return _FALLBACK.get(key)
