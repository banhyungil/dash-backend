"""CSV 적재 파이프라인: CSV 파싱 → RPM/MPM 계산 → DB 저장."""
import math
import logging
import re
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from services.settings_service import get_setting
from services.csv_parser import parse_pulse_csv, parse_vib_csv
from services.rpm_service import process_pulse_compact_to_rpm
from services.expected_filter import calculate_expected_pulse_count
from services.vibration_analyzer import analyze_axis
from services import database
from repos.cycles_repo import insert_many
from repos.ingested_files_repo import upsert as upsert_ingested_file, exists_by_path
from repos.pulse_waveform_repo import insert_many_copy as copy_pulse_waveforms
from repos.vib_waveform_repo import insert_many_copy as copy_vib_waveforms

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TypedDict 정의
# ---------------------------------------------------------------------------


class AxisStats(TypedDict):
    """축별 통계 — analyze_axis() 반환값. PULSE/VIB 공통."""
    rms: float
    peak: float
    min: float
    max: float
    q1: float
    median: float
    q3: float
    exceed_count: int
    exceed_ratio: float
    exceed_duration_ms: float
    burst_count: int
    peak_impact_count: int


class PulseRawCycle(TypedDict):
    """PULSE CSV 사이클 1개 — RPM/MPM + PULSE 3축 stats + 원시 파형."""
    timestamp: str
    date: str
    month: str
    device: str | None
    device_name: str
    cycle_index: int
    rpm_mean: float
    rpm_min: float
    rpm_max: float
    mpm_mean: float
    mpm_min: float
    mpm_max: float
    duration_ms: float
    set_count: int
    expected_count: int
    pulse_x_stats: AxisStats
    pulse_y_stats: AxisStats
    pulse_z_stats: AxisStats
    raw_pulses: list[int]
    raw_accel_x_arr: list[float]
    raw_accel_y_arr: list[float]
    raw_accel_z_arr: list[float]


class PulseResult(TypedDict):
    """PULSE 파일 처리 결과."""
    filename: str
    source: str
    cycles: list[PulseRawCycle]
    skipped: int
    errors: list[str]


class VibRawCycle(TypedDict):
    """VIB CSV 사이클 1개 — VIB 2축 stats + 원시 파형."""
    cycle_index: int
    accel_x_arr: list[float]
    accel_z_arr: list[float]
    vib_x_stats: AxisStats
    vib_z_stats: AxisStats


class VibResult(TypedDict):
    """VIB 파일 처리 결과."""
    filename: str
    source: str
    cycles: list[VibRawCycle]
    skipped: int
    errors: list[str]


class MergedCycle(TypedDict):
    """_merge_pulse_vib() 결과 — PULSE + VIB 합산. _write_to_db() 입력."""
    timestamp: str
    date: str
    month: str
    device: str | None
    device_name: str
    cycle_index: int
    rpm_mean: float
    rpm_min: float
    rpm_max: float
    mpm_mean: float
    mpm_min: float
    mpm_max: float
    duration_ms: float
    set_count: int
    expected_count: int
    pulse_x_stats: AxisStats
    pulse_y_stats: AxisStats
    pulse_z_stats: AxisStats
    vib_x_stats: AxisStats
    vib_z_stats: AxisStats
    max_vib_x: float
    max_vib_z: float
    burst_count: int
    peak_impact_count: int
    raw_pulses: list[int]
    raw_accel_x_arr: list[float]
    raw_accel_y_arr: list[float]
    raw_accel_z_arr: list[float]
    vib_accel_x_arr: list[float]
    vib_accel_z_arr: list[float]


class IngestDetail(TypedDict):
    """API 응답용 파일별 적재 결과."""
    filename: str
    cycles_ingested: int
    cycles_skipped: int
    errors: list[str]


class IngestBatchResult(TypedDict):
    """API 응답용 배치 적재 결과."""
    total_files: int
    success_cycles: int
    skipped_cycles: int
    failed_lines: int
    details: list[IngestDetail]


# ---------------------------------------------------------------------------
# 상수 / 헬퍼
# ---------------------------------------------------------------------------

# 병렬 처리 최대 워커 수 (CPU 코어 수와 4 중 작은 값)
_MAX_WORKERS = min(4, os.cpu_count() or 1)

_STATS_KEYS = ("rms", "peak", "min", "max", "q1", "median", "q3",
               "exceed_count", "exceed_ratio", "exceed_duration_ms")


def _flatten_axis_stats(prefix: str, stats: AxisStats | None) -> dict[str, float | int]:
    """analyze_axis() 결과를 '{prefix}_{key}' 형태의 flat dict로 변환."""
    if stats is None:
        return {f"{prefix}_{k}": 0 for k in _STATS_KEYS}
    return {f"{prefix}_{k}": stats.get(k, 0) for k in _STATS_KEYS}


def _calc_mpm(rpm: float, roll_dia: float) -> float:
    """RPM을 MPM(미터/분)으로 변환."""
    return round(rpm * math.pi * roll_dia / 1000, 2)


def _extract_date_from_filename(filename: str) -> str | None:
    """파일명에서 YYMMDD 날짜 추출. 예: PULSE_260311.csv → '260311'"""
    m = re.search(r"_(\d{6})\.", filename)
    return m.group(1) if m else None


def _extract_month_from_date(date_str: str) -> str:
    """YYMMDD에서 YYMM 추출. 예: '260311' → '2603'"""
    return date_str[:4]


# ---------------------------------------------------------------------------
# 폴더 스캔
# ---------------------------------------------------------------------------

def scan_folder(folder: str) -> list[dict]:
    """지정 폴더에서 PULSE/VIB CSV 파일 목록을 반환.
    각 파일의 경로, 타입, 크기, 예상 사이클 수, 적재 여부를 포함.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        return []

    results = []
    # recursive glob, 해당 폴더 포함 모든 하위폴더를 glob으로 재귀적으로 탐색
    for csv_path in sorted(folder_path.rglob("*.csv")):
        name = csv_path.name.upper()
        if not (name.startswith("PULSE_") or name.startswith("VIB_")):
            continue

        file_type = "PULSE" if name.startswith("PULSE_") else "VIB"
        source = str(csv_path.resolve())

        # 사이클 수 추정: 10MB 초과 파일은 첫 1MB 샘플링, 이하는 전체 줄 수 카운트
        try:
            size = csv_path.stat().st_size
            if size > 10 * 1024 * 1024:
                with open(csv_path, "rb") as f:
                    chunk = f.read(1024 * 1024)
                    lines_in_chunk = chunk.count(b'\n')
                    estimated = int(lines_in_chunk * (size / len(chunk)))
            else:
                with open(csv_path, "rb") as f:
                    estimated = sum(1 for _ in f)
        except Exception:
            estimated = 0

        results.append({
            "path": source,
            "filename": csv_path.name,
            "type": file_type,
            "size_bytes": csv_path.stat().st_size,
            "estimated_cycles": estimated,
            "already_ingested": exists_by_path(source),
        })

    return results


# ---------------------------------------------------------------------------
# 파싱 + 계산 (CPU 작업, 워커 프로세스에서 실행)
# ---------------------------------------------------------------------------

def _process_pulse(file_path: str, device: str | None = None,
                    shaft_dia: float | None = None,
                    pattern_width: float | None = None) -> PulseResult:
    """PULSE CSV를 파싱하고 RPM/MPM을 계산. VIB 로직 없음.

    처리 흐름:
      1. 설정값 로드 (shaft_dia, pattern_width, roll_diameter 등)
      2. 파일명에서 날짜/월 추출, 경로에서 디바이스 MAC 감지
      3. CSV 파싱 → 사이클 배열 획득
      4. 사이클별: RPM/MPM 계산, Z축 중력 보정, PULSE 3축 stats 계산
    """
    # --- 1) 설정값 로드 ---
    if shaft_dia is None:
        shaft_dia = float(get_setting("shaft_dia"))
    if pattern_width is None:
        pattern_width = float(get_setting("pattern_width"))
    roll_diameter = get_setting("roll_diameter")
    device_name_map = get_setting("device_name_map")
    gravity_offset = get_setting("gravity_offset")

    # --- 2) 파일 메타 추출 ---
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name
    date_str = _extract_date_from_filename(filename)

    if not date_str:
        return PulseResult(filename=filename, source=source, cycles=[],
                           skipped=0, errors=[f"파일명에서 날짜 추출 불가: {filename}"])

    month = _extract_month_from_date(date_str)

    # 파일 경로에서 디바이스 MAC 주소 감지
    if not device:
        for part in path.parts:
            if part in device_name_map:
                device = part
                break
        if not device:
            device = "unknown"

    device_name = device_name_map.get(device, device)

    # --- 3) CSV 파싱 ---
    raw_cycles = parse_pulse_csv(path)
    if not raw_cycles:
        return PulseResult(filename=filename, source=source, cycles=[],
                           skipped=0, errors=["파싱된 사이클 없음"])

    cycles: list[PulseRawCycle] = []
    skipped = 0
    errors: list[str] = []

    # --- 4) 사이클별 처리 ---
    for i, cycle in enumerate(raw_cycles):
        try:
            data = cycle["data"]
            pulses = [item["pulse"] for item in data]
            accel_x_arr = [item.get("accel_x", 0) for item in data]
            accel_y_arr = [item.get("accel_y", 0) for item in data]
            accel_z_arr = [item.get("accel_z", 0) for item in data]
            set_count = len(pulses)

            # RPM 계산
            rpm_result = process_pulse_compact_to_rpm(
                pulses, accel_x_arr, accel_y_arr, accel_z_arr, shaft_dia, pattern_width
            )
            if rpm_result is None:
                skipped += 1
                continue

            rpm_mean = rpm_result["rpmMean"]
            expected_count = calculate_expected_pulse_count(rpm_mean, shaft_dia, pattern_width)

            # MPM 변환
            mpm_mean = _calc_mpm(rpm_mean, roll_diameter)
            mpm_min = _calc_mpm(rpm_result["rpmMin"], roll_diameter)
            mpm_max = _calc_mpm(rpm_result["rpmMax"], roll_diameter)

            # Z축 중력 보정
            z_off = gravity_offset.get(device_name, {}).get("z", 0.0)
            corrected_z_arr = [v + z_off for v in accel_z_arr] if z_off != 0.0 else accel_z_arr

            # PULSE 3축 stats
            px_stats: AxisStats = analyze_axis(accel_x_arr)
            py_stats: AxisStats = analyze_axis(accel_y_arr)
            pz_stats: AxisStats = analyze_axis(corrected_z_arr)

            cycles.append(PulseRawCycle(
                timestamp=cycle["timestamp"],
                date=date_str,
                month=month,
                device=device,
                device_name=device_name,
                cycle_index=i,
                rpm_mean=round(rpm_mean, 2),
                rpm_min=round(rpm_result["rpmMin"], 2),
                rpm_max=round(rpm_result["rpmMax"], 2),
                mpm_mean=mpm_mean,
                mpm_min=mpm_min,
                mpm_max=mpm_max,
                duration_ms=round(rpm_result["durationms"], 2),
                set_count=set_count,
                expected_count=expected_count,
                pulse_x_stats=px_stats,
                pulse_y_stats=py_stats,
                pulse_z_stats=pz_stats,
                raw_pulses=pulses,
                raw_accel_x_arr=accel_x_arr,
                raw_accel_y_arr=accel_y_arr,
                raw_accel_z_arr=corrected_z_arr,
            ))
        except Exception as e:
            errors.append(f"Cycle {i}: {e}")
            skipped += 1

    return PulseResult(filename=filename, source=source, cycles=cycles,
                       skipped=skipped, errors=errors)


def _process_vib(file_path: str) -> VibResult:
    """VIB CSV 파싱 + 축별 stats 계산."""
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name

    # 중력 보정용 설정
    device_name_map = get_setting("device_name_map")
    gravity_offset = get_setting("gravity_offset")

    # 경로에서 디바이스명 추출
    device = "unknown"
    for part in path.parts:
        if part in device_name_map:
            device = part
            break
    device_name = device_name_map.get(device, device)
    z_off = gravity_offset.get(device_name, {}).get("z", 0.0)

    raw_cycles = parse_vib_csv(path)

    cycles: list[VibRawCycle] = []
    for i, vc in enumerate(raw_cycles):
        vib_data = vc["data"]
        vib_x_arr = [item.get("accel_x", 0) for item in vib_data]
        vib_z_raw_arr = [item.get("accel_z", 0) for item in vib_data]
        vib_z_arr = [v + z_off for v in vib_z_raw_arr] if z_off != 0.0 else vib_z_raw_arr

        vx_stats: AxisStats = analyze_axis(vib_x_arr)
        vz_stats: AxisStats = analyze_axis(vib_z_arr)

        cycles.append(VibRawCycle(
            cycle_index=i,
            accel_x_arr=vib_x_arr,
            accel_z_arr=vib_z_arr,
            vib_x_stats=vx_stats,
            vib_z_stats=vz_stats,
        ))

    return VibResult(filename=filename, source=source, cycles=cycles,
                     skipped=0, errors=[])


def _merge_pulse_vib(pulse_result: PulseResult,
                     vib_result: VibResult | None) -> list[MergedCycle]:
    """PULSE + VIB를 cycle_index로 매칭하여 MergedCycle 리스트 반환."""
    _empty_axis = AxisStats(
        rms=0, peak=0, min=0, max=0,
        q1=0, median=0, q3=0,
        exceed_count=0, exceed_ratio=0, exceed_duration_ms=0,
        burst_count=0, peak_impact_count=0,
    )

    # VIB cycle을 index로 빠르게 조회
    vib_by_index: dict[int, VibRawCycle] = {}
    if vib_result:
        for vc in vib_result["cycles"]:
            vib_by_index[vc["cycle_index"]] = vc

    merged: list[MergedCycle] = []
    for pc in pulse_result["cycles"]:
        vc = vib_by_index.get(pc["cycle_index"])

        if vc:
            vib_x_stats = vc["vib_x_stats"]
            vib_z_stats = vc["vib_z_stats"]
            vib_accel_x_arr = vc["accel_x_arr"]
            vib_accel_z_arr = vc["accel_z_arr"]
            max_vib_x = max((abs(v) for v in vib_accel_x_arr), default=0)
            max_vib_z = max((abs(v) for v in vib_accel_z_arr), default=0)
        else:
            vib_x_stats = _empty_axis
            vib_z_stats = _empty_axis
            vib_accel_x_arr = []
            vib_accel_z_arr = []
            max_vib_x = 0.0
            max_vib_z = 0.0

        # 5축 합산 (pulse_x + pulse_y + pulse_z + vib_x + vib_z)
        all_stats = (pc["pulse_x_stats"], pc["pulse_y_stats"], pc["pulse_z_stats"],
                     vib_x_stats, vib_z_stats)
        burst_count = sum(s["burst_count"] for s in all_stats)
        peak_impact_count = sum(s["peak_impact_count"] for s in all_stats)

        merged.append(MergedCycle(
            timestamp=pc["timestamp"],
            date=pc["date"],
            month=pc["month"],
            device=pc["device"],
            device_name=pc["device_name"],
            cycle_index=pc["cycle_index"],
            rpm_mean=pc["rpm_mean"],
            rpm_min=pc["rpm_min"],
            rpm_max=pc["rpm_max"],
            mpm_mean=pc["mpm_mean"],
            mpm_min=pc["mpm_min"],
            mpm_max=pc["mpm_max"],
            duration_ms=pc["duration_ms"],
            set_count=pc["set_count"],
            expected_count=pc["expected_count"],
            pulse_x_stats=pc["pulse_x_stats"],
            pulse_y_stats=pc["pulse_y_stats"],
            pulse_z_stats=pc["pulse_z_stats"],
            vib_x_stats=vib_x_stats,
            vib_z_stats=vib_z_stats,
            max_vib_x=max_vib_x,
            max_vib_z=max_vib_z,
            burst_count=burst_count,
            peak_impact_count=peak_impact_count,
            raw_pulses=pc["raw_pulses"],
            raw_accel_x_arr=pc["raw_accel_x_arr"],
            raw_accel_y_arr=pc["raw_accel_y_arr"],
            raw_accel_z_arr=pc["raw_accel_z_arr"],
            vib_accel_x_arr=vib_accel_x_arr,
            vib_accel_z_arr=vib_accel_z_arr,
        ))

    return merged


def _process_file(file_path: str) -> tuple[list[MergedCycle], PulseResult | VibResult]:
    """단일 파일 처리 (파싱 + 계산). DB 쓰기 없음.
    PULSE 파일이면 VIB 파일도 찾아서 merge.
    반환: (merged_cycles, 원본 result)
    """
    path = Path(file_path)
    name = path.name.upper()
    if name.startswith("PULSE_"):
        pulse_result = _process_pulse(file_path)
        # PULSE 경로에서 VIB 경로 유도 (PULSE_250920.csv → VIB_250920.csv)
        vib_file_path = str(path.parent / path.name.replace("PULSE_", "VIB_"))
        vib_result: VibResult | None = None
        if Path(vib_file_path).exists():
            vib_result = _process_vib(vib_file_path)
        merged = _merge_pulse_vib(pulse_result, vib_result)
        return merged, pulse_result
    elif name.startswith("VIB_"):
        vib_result = _process_vib(file_path)
        return [], vib_result
    else:
        empty_result = PulseResult(
            filename=Path(file_path).name, source=file_path,
            cycles=[], skipped=0, errors=[f"알 수 없는 파일 타입: {name}"])
        return [], empty_result


# ---------------------------------------------------------------------------
# 단건 적재 (순차 처리)
# ---------------------------------------------------------------------------

def ingest_file(file_path: str, conn=None) -> IngestDetail:
    """단일 CSV 파일 적재 (파싱 → 계산 → DB 저장)."""
    source = str(Path(file_path).resolve())
    if exists_by_path(source):
        return IngestDetail(filename=Path(file_path).name,
                            cycles_ingested=0, cycles_skipped=0,
                            errors=["이미 적재된 파일"])
    merged, result = _process_file(file_path)
    inserted_count = _write_to_db(merged, result, conn)
    return _to_detail(result, inserted_count)


# ---------------------------------------------------------------------------
# 배치 적재 (병렬 파싱 + 단일 DB 커밋)
# ---------------------------------------------------------------------------

def ingest_files(paths: list[str], on_progress: Callable | None = None) -> IngestBatchResult:
    """여러 CSV 파일을 병렬 파싱 후 한 번에 DB 적재.

    처리 흐름:
      1단계: 파싱 + RPM 계산 (CPU 작업 → ProcessPoolExecutor로 병렬화)
      2단계: 계산 결과를 모아서 DB에 배치 INSERT (단일 트랜잭션, commit 1회)
      3단계: 응답 집계
    """
    total = len(paths)

    def _notify(completed: int):
        if on_progress:
            on_progress(completed, total)

    # 0단계: 이미 적재된 파일 필터링
    new_paths: list[str] = []
    skipped_details: list[IngestDetail] = []
    for p in paths:
        source = str(Path(p).resolve())
        if exists_by_path(source):
            skipped_details.append(IngestDetail(
                filename=Path(p).name, cycles_ingested=0,
                cycles_skipped=0, errors=["이미 적재된 파일"]))
        else:
            new_paths.append(p)

    # 1단계: 병렬 파싱 + 계산
    processed: list[tuple[list[MergedCycle], PulseResult | VibResult]] = []
    if len(new_paths) <= 2:
        for i, p in enumerate(new_paths):
            processed.append(_process_file(p))
            _notify(i + 1)
    else:
        completed = 0
        with ProcessPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(_process_file, p): p for p in new_paths}
            for future in as_completed(futures):
                try:
                    processed.append(future.result())
                except Exception as e:
                    p = futures[future]
                    empty = PulseResult(
                        filename=Path(p).name, source=p,
                        cycles=[], skipped=0, errors=[str(e)])
                    processed.append(([], empty))
                completed += 1
                _notify(completed)

    # 2단계: 배치 DB 저장 (커넥션 1회, 커밋 1회)
    conn = database.get_connection()
    try:
        inserted_counts: list[int] = []
        for merged, result in processed:
            inserted_counts.append(_write_to_db(merged, result, conn))
        conn.commit()
    finally:
        conn.close()

    # 3단계: 응답 집계
    success_cycles = 0
    skipped_cycles = 0
    failed_lines = 0
    details: list[IngestDetail] = list(skipped_details)

    for (_, result), inserted_count in zip(processed, inserted_counts):
        detail = _to_detail(result, inserted_count)
        details.append(detail)
        success_cycles += detail["cycles_ingested"]
        skipped_cycles += detail["cycles_skipped"]
        failed_lines += len(detail["errors"])

    return IngestBatchResult(
        total_files=len(processed) + len(skipped_details),
        success_cycles=success_cycles,
        skipped_cycles=skipped_cycles,
        failed_lines=failed_lines,
        details=details,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _flatten_merged_cycle(mc: MergedCycle) -> dict:
    """MergedCycle의 중첩 AxisStats를 flat dict로 변환하여 DB INSERT용 row 반환."""
    row: dict = {}
    # 스칼라 필드 복사 (raw/stats 제외)
    for key in ("timestamp", "date", "month", "device", "device_name",
                "cycle_index", "rpm_mean", "rpm_min", "rpm_max",
                "mpm_mean", "mpm_min", "mpm_max", "duration_ms",
                "set_count", "expected_count", "max_vib_x", "max_vib_z",
                "burst_count", "peak_impact_count"):
        row[key] = mc[key]  # type: ignore[literal-required]
    # AxisStats → flat
    row.update(_flatten_axis_stats("pulse_x", mc["pulse_x_stats"]))
    row.update(_flatten_axis_stats("pulse_y", mc["pulse_y_stats"]))
    row.update(_flatten_axis_stats("pulse_z", mc["pulse_z_stats"]))
    row.update(_flatten_axis_stats("vib_x", mc["vib_x_stats"]))
    row.update(_flatten_axis_stats("vib_z", mc["vib_z_stats"]))
    return row


def _write_to_db(merged: list[MergedCycle],
                 result: PulseResult | VibResult,
                 conn=None) -> int:
    """파싱 결과를 DB에 저장. conn이 주어지면 커밋하지 않음 (호출자가 관리).

    흐름:
      1. t_cycle: 멀티 row VALUES + RETURNING id
      2. t_pulse_waveform: COPY
      3. t_vib_waveform: COPY
    반환: 삽입된 cycle 수.
    """
    if merged:
        # 1) t_cycle 일괄 INSERT → id 목록 확보
        db_rows = [_flatten_merged_cycle(mc) for mc in merged]
        ids = insert_many(db_rows, conn=conn)

        # 2) cycle_id ↔ MergedCycle 매핑 → waveform COPY용 데이터 조립
        pulse_waveform_rows: list[tuple[int, list[int], list[float], list[float], list[float]]] = []
        vib_waveform_rows: list[tuple[int, list[float], list[float]]] = []

        for cycle_id, mc in zip(ids, merged):
            pulse_waveform_rows.append((
                cycle_id, mc["raw_pulses"], mc["raw_accel_x_arr"],
                mc["raw_accel_y_arr"], mc["raw_accel_z_arr"],
            ))
            if mc["vib_accel_x_arr"]:
                vib_waveform_rows.append((
                    cycle_id, mc["vib_accel_x_arr"], mc["vib_accel_z_arr"],
                ))

        # 3) waveform COPY
        copy_pulse_waveforms(pulse_waveform_rows, conn=conn)
        copy_vib_waveforms(vib_waveform_rows, conn=conn)

        inserted_count = len(ids)
        upsert_ingested_file(
            result["source"], result["filename"], "PULSE",
            inserted_count, result["skipped"], len(result["errors"]), conn=conn
        )
        return inserted_count

    # VIB 단독 파일 처리
    if isinstance(result, dict) and result.get("cycles"):
        vib_count = len(result["cycles"])
        upsert_ingested_file(
            result["source"], result["filename"], "VIB",
            vib_count, 0, 0, conn=conn
        )
        return vib_count

    return 0


def _to_detail(result: PulseResult | VibResult, inserted_count: int) -> IngestDetail:
    """내부 처리 결과를 API 응답용 형식으로 변환."""
    return IngestDetail(
        filename=result["filename"],
        cycles_ingested=inserted_count,
        cycles_skipped=result["skipped"],
        errors=result["errors"],
    )
