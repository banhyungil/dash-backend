"""사이클 데이터 조회 API."""
import math
import logging
from pathlib import Path
from fastapi import APIRouter, Query

from config import DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH, DEFAULT_TARGET_RPM, ROLL_DIAMETER_MM
from repos.cycles_repo import get_months as repo_get_months, get_dates as repo_get_dates, find_by_date
from services.cached_csv_parser import parse_pulse_cached, parse_vib_cached
from services.rpm_service import process_pulse_compact_to_rpm
from services.session_merger import calculate_continuous_timeline

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
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 일별 데이터 조회 (DB 집계값 + CSV 배열 데이터)
# ---------------------------------------------------------------------------

@router.get("/cycles/daily")
def get_daily_data(
    month: str = Query(...),
    date: str = Query(...),
):
    """일별 사이클 데이터 조회.

    처리 흐름:
      1. DB에서 해당 날짜 사이클 집계값 조회
      2. source_path로 CSV에서 배열 데이터(RPM 타임라인, 가속도 등) 로드
      3. VIB 데이터 매칭
      4. 타임라인 오프셋 계산
    """
    # 1단계: DB에서 집계값 조회
    db_cycles = find_by_date(month, date)
    if not db_cycles:
        return {"date": date, "device": "all", "settings": {}, "cycles": [], "total_cycles": 0}

    # 유효 사이클만 필터링
    valid_cycles = [c for c in db_cycles if c["is_valid"]]

    # 2단계: source_path로 CSV에서 배열 데이터 로드
    result_cycles = []
    # source_path별로 캐싱하여 같은 파일을 여러 번 파싱하지 않음
    _parsed_cache: dict[str, dict] = {}

    for cycle in valid_cycles:
        source_path = cycle.get("source_path")
        if not source_path or not Path(source_path).exists():
            # source_path가 없으면 집계값만 반환 (배열 없음)
            result_cycles.append({
                **cycle,
                "rpm_timeline": [], "rpm_data": [],
                "mpm_data": [],
                "pulse_timeline": [], "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
                "vib_accel_x": [], "vib_accel_z": [],
            })
            continue

        # CSV 파싱 (캐시)
        if source_path not in _parsed_cache:
            _parsed_cache[source_path] = parse_pulse_cached(source_path)
        parsed = _parsed_cache[source_path]

        cycle_index = cycle["cycle_index"]

        # cycle_index 범위 확인
        if cycle_index >= len(parsed["cycles"]):
            result_cycles.append({
                **cycle,
                "rpm_timeline": [], "rpm_data": [],
                "mpm_data": [],
                "pulse_timeline": [], "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
                "vib_accel_x": [], "vib_accel_z": [],
            })
            continue

        raw = parsed["cycles"][cycle_index]

        # RPM 계산 → 배열 데이터 생성
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
            result_cycles.append({
                **cycle,
                "rpm_timeline": [], "rpm_data": [],
                "mpm_data": [],
                "pulse_timeline": [], "pulse_accel_x": [], "pulse_accel_y": [], "pulse_accel_z": [],
                "vib_accel_x": [], "vib_accel_z": [],
            })

    # 3단계: VIB 데이터 매칭
    # source_path에서 PULSE → VIB 경로 변환하여 VIB 데이터 로드
    _vib_cache: dict[str, dict] = {}
    for cycle in result_cycles:
        source_path = cycle.get("source_path", "")
        if not source_path:
            continue

        # PULSE_YYMMDD.csv → VIB_YYMMDD.csv
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

    # 4단계: 타임라인 오프셋 계산
    result_cycles = calculate_continuous_timeline(result_cycles)

    # 설정값 (첫 번째 사이클의 디바이스 기준)
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
