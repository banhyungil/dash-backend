"""일별 사이클 데이터 빌드 서비스."""
import math

from services.settings_service import get_setting
from repos.cycles_repo import find_by_date, find_one
from repos.pulse_waveform_repo import find_by_cycle_id as find_pulse_waveform
from repos.vib_waveform_repo import find_by_cycle_id as find_vib_waveform
from services.rpm_service import process_pulse_compact_to_rpm
from services.session_merger import calculate_continuous_timeline


def _calc_mpm(rpm: float, roll_dia: float) -> float:
    return round(rpm * math.pi * roll_dia / 1000, 2)


_EMPTY_ARRAYS = {
    "rpm_timeline": [], "rpm_data": [], "mpm_data": [],
    "pulse_timeline": [], "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
    "vib_accel_x": [], "vib_accel_z": [],
}


def build_daily_data(month: str, date: str) -> dict:
    """일별 사이클 집계 데이터 빌드 (stats만, 파형 없음).

    처리 흐름:
      1. DB에서 해당 날짜 사이클 집계값 조회
      2. DB stats → 프론트 응답 형식 변환
      3. 타임라인 오프셋 계산
    """
    empty = {"date": date, "device": "all", "settings": {}, "cycles": [], "total_cycles": 0}

    db_cycles = find_by_date(month, date)
    if not db_cycles:
        return empty

    shaft_dia = get_setting("shaft_dia")
    pattern_width = get_setting("pattern_width")

    result_cycles = list(db_cycles)
    _attach_stats(result_cycles)
    result_cycles = calculate_continuous_timeline(result_cycles)

    return {
        "date": date,
        "device": "all",
        "settings": {
            "shaft_dia": shaft_dia,
            "pattern_width": pattern_width,
            "target_rpm": get_setting("target_rpm"),
        },
        "cycles": result_cycles,
        "total_cycles": len(result_cycles),
    }


def build_daily_waveforms(month: str, date: str) -> dict:
    """일별 전체 사이클의 원시 파형 데이터 반환 (VibrationChart용).

    처리 흐름:
      1. DB에서 해당 날짜 사이클 조회
      2. cycle id로 PULSE/VIB 파형 로드
      3. 중력 보정
    """
    db_cycles = find_by_date(month, date)
    if not db_cycles:
        return {"cycles": []}

    shaft_dia = get_setting("shaft_dia")
    pattern_width = get_setting("pattern_width")
    roll_diameter = get_setting("roll_diameter")
    gravity_offset = get_setting("gravity_offset")

    result_cycles = _load_pulse_arrays(db_cycles, shaft_dia, pattern_width, roll_diameter)
    _load_vib_arrays(result_cycles)
    _apply_gravity_correction(result_cycles, gravity_offset)

    return {"cycles": result_cycles}


def build_cycle_detail(date: str, device_name: str, cycle_index: int) -> dict | None:
    """개별 사이클의 집계값 반환 (파형은 /daily/waveforms에서 별도 조회)."""
    cycle = find_one(date, device_name, cycle_index)
    if not cycle:
        return None

    return {
        "date": date,
        "device_name": device_name,
        "cycle_index": cycle_index,
        "timestamp": cycle["timestamp"],
        "rpm_mean": cycle["rpm_mean"],
        "rpm_min": cycle["rpm_min"],
        "rpm_max": cycle["rpm_max"],
        "mpm_mean": cycle["mpm_mean"],
        "duration_ms": cycle["duration_ms"],
        "set_count": cycle["set_count"],
        "expected_count": cycle["expected_count"],
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _load_pulse_arrays(cycles: list[dict], shaft_dia: float, pattern_width: float, roll_diameter: float) -> list[dict]:
    """cycle id로 DB에서 RPM/가속도 배열 데이터 로드."""
    result = []

    for cycle in cycles:
        cycle_id = cycle.get("id")
        if not cycle_id:
            result.append({**cycle, **_EMPTY_ARRAYS})
            continue

        pw = find_pulse_waveform(cycle_id)
        if not pw:
            result.append({**cycle, **_EMPTY_ARRAYS})
            continue

        rpm_result = process_pulse_compact_to_rpm(
            pw["pulses"], pw["accel_x"], pw["accel_y"], pw["accel_z"],
            shaft_dia, pattern_width,
        )

        if rpm_result:
            result.append({
                **cycle,
                "rpm_timeline": rpm_result["timeLine"],
                "rpm_data": rpm_result["dataRPM"],
                "mpm_data": [_calc_mpm(r, roll_diameter) for r in rpm_result["dataRPM"]],
                "pulse_timeline": rpm_result.get("rawTimeLine", []),
                "pulse_accel_x": rpm_result.get("rawAccelX", []),
                "pulse_accel_y": rpm_result.get("rawAccelY", []),
                "pulse_accel_z": rpm_result.get("rawAccelZ", []),
                "vib_accel_x": [], "vib_accel_z": [],
            })
        else:
            result.append({**cycle, **_EMPTY_ARRAYS})

    return result


def _load_vib_arrays(cycles: list[dict]):
    """cycle id로 DB에서 VIB 가속도 배열 로드."""
    for cycle in cycles:
        cycle_id = cycle.get("id")
        if not cycle_id:
            continue

        vw = find_vib_waveform(cycle_id)
        if not vw:
            continue

        cycle["vib_accel_x"] = vw["accel_x"]
        cycle["vib_accel_z"] = vw["accel_z"]


def _apply_gravity_correction(cycles: list[dict], gravity_offset: dict):
    """디바이스명별 Z축 중력 보정."""
    for cycle in cycles:
        z_off = gravity_offset.get(cycle.get("device_name", ""), {}).get("z", 0.0)
        if z_off != 0.0:
            if cycle.get("pulse_accel_z"):
                cycle["pulse_accel_z"] = [v + z_off for v in cycle["pulse_accel_z"]]
            if cycle.get("vib_accel_z"):
                cycle["vib_accel_z"] = [v + z_off for v in cycle["vib_accel_z"]]


_STAT_FIELDS = ("rms", "peak", "min", "max", "q1", "median", "q3",
                "exceed_count", "exceed_ratio", "exceed_duration_ms")


def _build_axis_stats(c: dict, prefix: str, burst: int = 0, impact: int = 0) -> dict:
    """DB 컬럼(prefix_rms, prefix_peak 등)을 AxisStats dict로 변환."""
    stats = {k: c.get(f"{prefix}_{k}", 0) for k in _STAT_FIELDS}
    stats["burst_count"] = burst
    stats["peak_impact_count"] = impact
    return stats


def _attach_stats(cycles: list[dict]):
    """DB에 저장된 stats를 프론트 응답 형식(stats_*)으로 변환."""
    for c in cycles:
        c["stats_pulse_x"] = _build_axis_stats(c, "pulse_x", c.get("burst_count", 0), c.get("peak_impact_count", 0))
        c["stats_pulse_y"] = _build_axis_stats(c, "pulse_y")
        c["stats_pulse_z"] = _build_axis_stats(c, "pulse_z")
        c["stats_vib_x"] = _build_axis_stats(c, "vib_x")
        c["stats_vib_z"] = _build_axis_stats(c, "vib_z")
