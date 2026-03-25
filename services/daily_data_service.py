"""일별 사이클 데이터 빌드 서비스."""
import math
from pathlib import Path

from services.settings_service import get_setting
from repos.cycles_repo import find_by_date, find_one
from services.cached_csv_parser import parse_pulse_cached, parse_vib_cached
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
    """일별 사이클 데이터 빌드 (API + Excel 공용).

    처리 흐름:
      1. DB에서 해당 날짜 사이클 집계값 조회
      2. source_path로 CSV에서 배열 데이터(RPM 타임라인, 가속도 등) 로드
      3. VIB 데이터 매칭
      4. 중력 보정
      5. DB stats → 프론트 응답 형식 변환
      6. 타임라인 오프셋 계산
    """
    empty = {"date": date, "device": "all", "settings": {}, "cycles": [], "total_cycles": 0}

    # DB에서 해당 날짜의 사이클 집계값 조회 (rpm_mean, mpm_mean 등)
    db_cycles = find_by_date(month, date)
    if not db_cycles:
        return empty

    shaft_dia = get_setting("shaft_dia")
    pattern_width = get_setting("pattern_width")
    roll_diameter = get_setting("roll_diameter")
    gravity_offset = get_setting("gravity_offset")

    # source_path 기반으로 원본 CSV에서 배열 데이터 로드 (RPM 타임라인, 가속도 파형)
    result_cycles = _load_pulse_arrays(db_cycles, shaft_dia, pattern_width, roll_diameter)
    # PULSE_*.csv → VIB_*.csv 경로 변환으로 VIB 가속도 배열 매칭
    _load_vib_arrays(result_cycles)
    # R1/R2는 Z축에서 1g 차감 (센서 장착 방향에 의한 중력 성분 제거)
    _apply_gravity_correction(result_cycles, gravity_offset)
    # DB에 저장된 rms/peak/burst 값을 프론트 응답 형식(stats_pulse_x 등)으로 변환
    _attach_stats(result_cycles)
    # 사이클 간 연속 타임라인 오프셋 계산 (차트 X축 연속 배치용)
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


def build_cycle_detail(date: str, device_name: str, cycle_index: int) -> dict | None:
    """개별 사이클의 원시 파형 데이터 반환."""
    cycle = find_one(date, device_name, cycle_index)
    if not cycle:
        return None

    shaft_dia = get_setting("shaft_dia")
    pattern_width = get_setting("pattern_width")

    source_path = cycle.get("source_path", "")
    result = {
        "date": date,
        "device_name": device_name,
        "cycle_index": cycle_index,
        "timestamp": cycle["timestamp"],
        "rpm_mean": cycle["rpm_mean"],
        "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
        "pulse_timeline": [],
        "rpm_timeline": [], "rpm_data": [],
        "vib_accel_x": [], "vib_accel_z": [],
    }

    if source_path and Path(source_path).exists():
        parsed = parse_pulse_cached(source_path)
        if cycle_index < len(parsed["cycles"]):
            raw = parsed["cycles"][cycle_index]
            rpm_result = process_pulse_compact_to_rpm(
                raw["pulses"], raw["accel_x"], raw["accel_y"], raw["accel_z"],
                shaft_dia, pattern_width,
            )
            if rpm_result:
                result["rpm_timeline"] = rpm_result["timeLine"]
                result["rpm_data"] = rpm_result["dataRPM"]
                result["pulse_timeline"] = rpm_result.get("rawTimeLine", [])
                result["pulse_accel_x"] = rpm_result.get("rawAccelX", [])
                result["pulse_accel_y"] = rpm_result.get("rawAccelY", [])
                result["pulse_accel_z"] = rpm_result.get("rawAccelZ", [])

    if source_path:
        vib_path = source_path.replace("PULSE_", "VIB_")
        if vib_path != source_path and Path(vib_path).exists():
            parsed_vib = parse_vib_cached(vib_path)
            if cycle_index < len(parsed_vib["cycles"]):
                vib_cycle = parsed_vib["cycles"][cycle_index]
                result["vib_accel_x"] = vib_cycle["accel_x"]
                result["vib_accel_z"] = vib_cycle["accel_z"]

    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _load_pulse_arrays(cycles: list[dict], shaft_dia: float, pattern_width: float, roll_diameter: float) -> list[dict]:
    """source_path로 CSV에서 RPM/가속도 배열 데이터 로드."""
    result = []
    cache: dict[str, dict] = {}

    for cycle in cycles:
        source_path = cycle.get("source_path")
        if not source_path or not Path(source_path).exists():
            result.append({**cycle, **_EMPTY_ARRAYS})
            continue

        if source_path not in cache:
            cache[source_path] = parse_pulse_cached(source_path)
        parsed = cache[source_path]

        idx = cycle["cycle_index"]
        if idx >= len(parsed["cycles"]):
            result.append({**cycle, **_EMPTY_ARRAYS})
            continue

        raw = parsed["cycles"][idx]
        rpm_result = process_pulse_compact_to_rpm(
            raw["pulses"], raw["accel_x"], raw["accel_y"], raw["accel_z"],
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
    """PULSE → VIB 경로 변환으로 VIB 가속도 배열 로드."""
    cache: dict[str, dict] = {}
    for cycle in cycles:
        source_path = cycle.get("source_path", "")
        if not source_path:
            continue

        vib_path = source_path.replace("PULSE_", "VIB_")
        if vib_path == source_path or not Path(vib_path).exists():
            continue

        if vib_path not in cache:
            cache[vib_path] = parse_vib_cached(vib_path)

        idx = cycle["cycle_index"]
        if idx < len(cache[vib_path]["cycles"]):
            vib_cycle = cache[vib_path]["cycles"][idx]
            cycle["vib_accel_x"] = vib_cycle["accel_x"]
            cycle["vib_accel_z"] = vib_cycle["accel_z"]


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
