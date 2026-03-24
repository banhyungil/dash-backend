"""사이클 데이터 조회 API."""
import math
import logging
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from config import DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH, DEFAULT_TARGET_RPM, ROLL_DIAMETER_MM, GRAVITY_OFFSET
from repos.cycles_repo import get_months as repo_get_months, get_dates as repo_get_dates, find_by_date, find_one
from services.cached_csv_parser import parse_pulse_cached, parse_vib_cached
from services.rpm_service import process_pulse_compact_to_rpm
from services.session_merger import calculate_continuous_timeline
from services.excel_export import generate_daily_report
from services.vibration_analyzer import analyze_cycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _calc_mpm(rpm: float, roll_dia: float) -> float:
    return round(rpm * math.pi * roll_dia / 1000, 2)


# ---------------------------------------------------------------------------
# 목록 조회 (DB 기반)
# ---------------------------------------------------------------------------

@router.get("/months")
def get_months():
    """적재된 월 목록 조회."""
    rows = repo_get_months()
    # 프론트 호환 형식: [{month, label}, ...]
    return [
        {"month": r["month"], "label": f"20{r['month'][:2]}년 {r['month'][2:]}월"}
        for r in rows
    ]


@router.get("/dates")
def get_dates(month: str = Query(...)):
    """특정 월의 날짜 목록 조회."""
    rows = repo_get_dates(month)
    # 프론트 호환 형식: [{date, label}, ...]
    return [
        {
            "date": r["date"],
            "label": f"{r['date'][:2]}/{r['date'][2:4]}/{r['date'][4:]} ({r['cycle_count']} cycles)",
            "cycle_count": r["cycle_count"],
            "high_vib_events": r["high_vib_events"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 일별 데이터 조회 (DB 집계값 + CSV 배열 데이터)
# ---------------------------------------------------------------------------

def _build_daily_data(month: str, date: str) -> dict:
    """일별 사이클 데이터 빌드 (API + Excel 공용).

    처리 흐름:
      1. DB에서 해당 날짜 사이클 집계값 조회
      2. source_path로 CSV에서 배열 데이터(RPM 타임라인, 가속도 등) 로드
      3. VIB 데이터 매칭
      4. 타임라인 오프셋 계산
    """
    _empty = {"date": date, "device": "all", "settings": {}, "cycles": [], "total_cycles": 0}
    _empty_arrays = {
        "rpm_timeline": [], "rpm_data": [], "mpm_data": [],
        "pulse_timeline": [], "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
        "vib_accel_x": [], "vib_accel_z": [],
    }

    # 1단계: DB에서 집계값 조회
    db_cycles = find_by_date(month, date)
    if not db_cycles:
        return _empty

    valid_cycles = [c for c in db_cycles if c["is_valid"]]

    # 2단계: source_path로 CSV에서 배열 데이터 로드
    result_cycles = []
    _parsed_cache: dict[str, dict] = {}

    for cycle in valid_cycles:
        source_path = cycle.get("source_path")
        if not source_path or not Path(source_path).exists():
            result_cycles.append({**cycle, **_empty_arrays})
            continue

        if source_path not in _parsed_cache:
            _parsed_cache[source_path] = parse_pulse_cached(source_path)
        parsed = _parsed_cache[source_path]

        cycle_index = cycle["cycle_index"]
        if cycle_index >= len(parsed["cycles"]):
            result_cycles.append({**cycle, **_empty_arrays})
            continue

        raw = parsed["cycles"][cycle_index]

        rpm_result = process_pulse_compact_to_rpm(
            raw["pulses"], raw["accel_x"], raw["accel_y"], raw["accel_z"],
            DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH,
        )

        if rpm_result:
            mpm_data = [_calc_mpm(rpm, ROLL_DIAMETER_MM) for rpm in rpm_result["dataRPM"]]
            result_cycles.append({
                **cycle,
                "rpm_timeline": rpm_result["timeLine"],
                "rpm_data": rpm_result["dataRPM"],
                "mpm_data": mpm_data,
                "pulse_timeline": rpm_result.get("rawTimeLine", []),
                "pulse_accel_x": rpm_result.get("rawAccelX", []),
                "pulse_accel_y": rpm_result.get("rawAccelY", []),
                "pulse_accel_z": rpm_result.get("rawAccelZ", []),
                "vib_accel_x": [], "vib_accel_z": [],
            })
        else:
            result_cycles.append({**cycle, **_empty_arrays})

    # 3단계: VIB 데이터 매칭
    _vib_cache: dict[str, dict] = {}
    for cycle in result_cycles:
        source_path = cycle.get("source_path", "")
        if not source_path:
            continue

        vib_path = source_path.replace("PULSE_", "VIB_")
        if vib_path == source_path or not Path(vib_path).exists():
            continue

        if vib_path not in _vib_cache:
            _vib_cache[vib_path] = parse_vib_cached(vib_path)
        parsed_vib = _vib_cache[vib_path]

        cycle_index = cycle["cycle_index"]
        if cycle_index < len(parsed_vib["cycles"]):
            vib_cycle = parsed_vib["cycles"][cycle_index]
            cycle["vib_accel_x"] = vib_cycle["accel_x"]
            cycle["vib_accel_z"] = vib_cycle["accel_z"]

    # 4단계: 중력 보정 (세션별 Z축 오프셋 차감)
    for cycle in result_cycles:
        session = cycle.get("session", "")
        offset = GRAVITY_OFFSET.get(session, {})
        z_off = offset.get("z", 0.0)
        if z_off != 0.0:
            if cycle.get("pulse_accel_z"):
                cycle["pulse_accel_z"] = [v + z_off for v in cycle["pulse_accel_z"]]
            if cycle.get("vib_accel_z"):
                cycle["vib_accel_z"] = [v + z_off for v in cycle["vib_accel_z"]]

    # 5단계: 진동 분석 (축별 stats 추가)
    for cycle in result_cycles:
        cycle.update(analyze_cycle(cycle))

    # 5단계: 타임라인 오프셋 계산
    result_cycles = calculate_continuous_timeline(result_cycles)

    settings = {
        "shaft_dia": DEFAULT_SHAFT_DIA,
        "pattern_width": DEFAULT_PATTERN_WIDTH,
        "target_rpm": DEFAULT_TARGET_RPM,
    }

    return {
        "date": date,
        "device": "all",
        "settings": settings,
        "cycles": result_cycles,
        "total_cycles": len(result_cycles),
    }


@router.get("/cycles/daily")
def get_daily_data(month: str = Query(...), date: str = Query(...)):
    """일별 사이클 데이터 조회."""
    return _build_daily_data(month, date)


@router.get("/cycles/export-excel")
def export_excel(month: str = Query(...), date: str = Query(...)):
    """일일 리포트 Excel 다운로드."""
    data = _build_daily_data(month, date)
    buf = generate_daily_report(data["cycles"], date)
    filename = f"Report_{date}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cycles/detail")
def get_cycle_detail(
    date: str = Query(...),
    session: str = Query(...),
    cycle_index: int = Query(...),
):
    """개별 사이클의 원시 파형 데이터 반환."""
    cycle = find_one(date, session, cycle_index)
    if not cycle:
        return {"error": "cycle not found"}

    source_path = cycle.get("source_path", "")
    result = {
        "date": date,
        "session": session,
        "cycle_index": cycle_index,
        "timestamp": cycle["timestamp"],
        "rpm_mean": cycle["rpm_mean"],
        "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
        "pulse_timeline": [],
        "rpm_timeline": [], "rpm_data": [],
        "vib_accel_x": [], "vib_accel_z": [],
    }

    # PULSE 배열 로드
    if source_path and Path(source_path).exists():
        parsed = parse_pulse_cached(source_path)
        if cycle_index < len(parsed["cycles"]):
            raw = parsed["cycles"][cycle_index]
            rpm_result = process_pulse_compact_to_rpm(
                raw["pulses"], raw["accel_x"], raw["accel_y"], raw["accel_z"],
                DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH,
            )
            if rpm_result:
                result["rpm_timeline"] = rpm_result["timeLine"]
                result["rpm_data"] = rpm_result["dataRPM"]
                result["pulse_timeline"] = rpm_result.get("rawTimeLine", [])
                result["pulse_accel_x"] = rpm_result.get("rawAccelX", [])
                result["pulse_accel_y"] = rpm_result.get("rawAccelY", [])
                result["pulse_accel_z"] = rpm_result.get("rawAccelZ", [])

    # VIB 배열 로드
    if source_path:
        vib_path = source_path.replace("PULSE_", "VIB_")
        if vib_path != source_path and Path(vib_path).exists():
            parsed_vib = parse_vib_cached(vib_path)
            if cycle_index < len(parsed_vib["cycles"]):
                vib_cycle = parsed_vib["cycles"][cycle_index]
                result["vib_accel_x"] = vib_cycle["accel_x"]
                result["vib_accel_z"] = vib_cycle["accel_z"]

    return result
