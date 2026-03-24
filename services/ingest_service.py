"""CSV 적재 파이프라인: CSV 파싱 → RPM/MPM 계산 → DB 저장."""
import math
import logging
import re
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from config import (
    DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH, DEFAULT_TARGET_RPM,
    ROLL_DIAMETER_MM, DEVICE_SESSION_MAP, GRAVITY_OFFSET,
)
from services.csv_parser import parse_pulse_csv, parse_vib_csv
from services.rpm_service import process_pulse_compact_to_rpm
from services.expected_filter import is_expected_valid, calculate_expected_pulse_count
from services.vibration_analyzer import analyze_axis
from services import database
from repos.cycles_repo import insert_many
from repos.ingested_files_repo import upsert as upsert_ingested_file, exists_by_path

logger = logging.getLogger(__name__)

# 병렬 처리 최대 워커 수 (CPU 코어 수와 4 중 작은 값)
_MAX_WORKERS = min(4, os.cpu_count() or 1)

_STATS_KEYS = ("rms", "peak", "min", "max", "q1", "median", "q3",
               "exceed_count", "exceed_ratio", "exceed_duration_ms")


def _flatten_axis_stats(prefix: str, stats: dict | None) -> dict:
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

def _process_pulse_file(file_path: str, device: str | None = None,
                        shaft_dia: float = DEFAULT_SHAFT_DIA,
                        pattern_width: float = DEFAULT_PATTERN_WIDTH) -> dict:
    """PULSE CSV를 파싱하고 RPM/MPM을 계산.
    DB 쓰기는 하지 않음 — 멀티프로세싱에서 안전하게 실행 가능.
    반환: db_rows(DB에 넣을 행 목록) + 메타데이터
    """
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name
    date_str = _extract_date_from_filename(filename)

    if not date_str:
        return {"filename": filename, "db_rows": [], "skipped": 0,
                "errors": [f"파일명에서 날짜 추출 불가: {filename}"],
                "source": source, "file_type": "PULSE"}

    month = _extract_month_from_date(date_str)

    # 경로에서 디바이스 MAC 주소 감지
    if not device:
        for part in path.parts:
            if part in DEVICE_SESSION_MAP:
                device = part
                break
        if not device:
            device = "unknown"

    session = DEVICE_SESSION_MAP.get(device, device)

    # CSV 파싱 (ast.literal_eval로 각 줄 파싱)
    raw_cycles = parse_pulse_csv(path)
    if not raw_cycles:
        return {"filename": filename, "db_rows": [], "skipped": 0,
                "errors": ["파싱된 사이클 없음"], "source": source, "file_type": "PULSE"}

    db_rows = []
    skipped = 0
    errors = []

    for i, cycle in enumerate(raw_cycles):
        try:
            data = cycle["data"]
            pulses = [item["pulse"] for item in data]
            accel_x = [item.get("accel_x", 0) for item in data]
            accel_y = [item.get("accel_y", 0) for item in data]
            accel_z = [item.get("accel_z", 0) for item in data]
            set_count = len(pulses)

            # 펄스 간격 → RPM 변환 + 에지 마스킹
            rpm_result = process_pulse_compact_to_rpm(
                pulses, accel_x, accel_y, accel_z, shaft_dia, pattern_width
            )

            if rpm_result is None:
                skipped += 1
                continue

            rpm_mean = rpm_result["rpmMean"]
            valid = is_expected_valid(set_count, rpm_mean, shaft_dia, pattern_width)
            expected_count = calculate_expected_pulse_count(rpm_mean, shaft_dia, pattern_width)

            # RPM → MPM 변환 (롤러 지름 기준)
            mpm_mean = _calc_mpm(rpm_mean, ROLL_DIAMETER_MM)
            mpm_min = _calc_mpm(rpm_result["rpmMin"], ROLL_DIAMETER_MM)
            mpm_max = _calc_mpm(rpm_result["rpmMax"], ROLL_DIAMETER_MM)

            # 중력 보정 적용
            z_off = GRAVITY_OFFSET.get(session, {}).get("z", 0.0)
            corrected_z = [v + z_off for v in accel_z] if z_off != 0.0 else accel_z

            # PULSE 축별 진동 stats 계산
            px_stats = analyze_axis(accel_x)
            py_stats = analyze_axis(accel_y)
            pz_stats = analyze_axis(corrected_z)

            # VIB stats는 매칭 파일이 있을 때 별도 계산 (아래 _enrich_vib_stats에서)
            db_rows.append({
                "timestamp": cycle["timestamp"],
                "date": date_str,
                "month": month,
                "device": device,
                "session": session,
                "cycle_index": i,
                "rpm_mean": round(rpm_mean, 2),
                "rpm_min": round(rpm_result["rpmMin"], 2),
                "rpm_max": round(rpm_result["rpmMax"], 2),
                "mpm_mean": mpm_mean,
                "mpm_min": mpm_min,
                "mpm_max": mpm_max,
                "duration_ms": round(rpm_result["durationms"], 2),
                "set_count": set_count,
                "expected_count": expected_count,
                "is_valid": 1 if valid else 0,
                "max_vib_x": max((abs(v) for v in accel_x), default=0),
                "max_vib_z": max((abs(v) for v in corrected_z), default=0),
                "high_vib_event": 1 if any(abs(v) > 0.3 for v in accel_x + corrected_z) else 0,
                "source_path": source,
                # Phase 5: PULSE 진동 stats (축별 전체)
                **_flatten_axis_stats("pulse_x", px_stats),
                **_flatten_axis_stats("pulse_y", py_stats),
                **_flatten_axis_stats("pulse_z", pz_stats),
                "burst_count": px_stats["burst_count"] + py_stats["burst_count"] + pz_stats["burst_count"],
                "peak_impact_count": px_stats["peak_impact_count"] + py_stats["peak_impact_count"] + pz_stats["peak_impact_count"],
                # VIB stats — 기본값, _enrich_vib_stats에서 업데이트
                **_flatten_axis_stats("vib_x", None),
                **_flatten_axis_stats("vib_z", None),
            })
        except Exception as e:
            errors.append(f"Cycle {i}: {e}")
            skipped += 1

    return {
        "filename": filename,
        "db_rows": db_rows,
        "skipped": skipped,
        "errors": errors,
        "source": source,
        "file_type": "PULSE",
    }


def _process_vib_file(file_path: str) -> dict:
    """VIB CSV 파싱. 배열 데이터는 DB에 넣지 않고 메타데이터만 반환.
    (VIB 배열은 사이클당 5,000+ 포인트로 DB에 넣기엔 너무 큼)
    """
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name

    raw_cycles = parse_vib_csv(path)

    return {
        "filename": filename,
        "db_rows": [],
        "skipped": 0,
        "errors": [],
        "source": source,
        "file_type": "VIB",
        "vib_cycle_count": len(raw_cycles),
    }


def _enrich_vib_stats(pulse_result: dict):
    """PULSE 결과에 매칭되는 VIB 파일이 있으면 VIB stats를 계산하여 병합."""
    source = pulse_result.get("source", "")
    vib_path = source.replace("PULSE_", "VIB_")
    if vib_path == source or not Path(vib_path).exists():
        return

    try:
        vib_cycles = parse_vib_csv(Path(vib_path))
    except Exception:
        return

    session = None
    for row in pulse_result.get("db_rows", []):
        session = row.get("session")
        break

    z_off = GRAVITY_OFFSET.get(session, {}).get("z", 0.0) if session else 0.0

    for row in pulse_result.get("db_rows", []):
        idx = row["cycle_index"]
        if idx >= len(vib_cycles):
            continue

        vib_data = vib_cycles[idx]["data"]
        vib_x = [item.get("accel_x", 0) for item in vib_data]
        vib_z_raw = [item.get("accel_z", 0) for item in vib_data]
        vib_z = [v + z_off for v in vib_z_raw] if z_off != 0.0 else vib_z_raw

        vx_stats = analyze_axis(vib_x)
        vz_stats = analyze_axis(vib_z)

        row.update(_flatten_axis_stats("vib_x", vx_stats))
        row.update(_flatten_axis_stats("vib_z", vz_stats))
        row["burst_count"] += vx_stats["burst_count"] + vz_stats["burst_count"]
        row["peak_impact_count"] += vx_stats["peak_impact_count"] + vz_stats["peak_impact_count"]


def _process_file(file_path: str) -> dict:
    """단일 파일 처리 (파싱 + 계산). DB 쓰기 없음.
    파일명 접두사로 PULSE/VIB 자동 판별.
    """
    name = Path(file_path).name.upper()
    if name.startswith("PULSE_"):
        result = _process_pulse_file(file_path)
        _enrich_vib_stats(result)
        return result
    elif name.startswith("VIB_"):
        return _process_vib_file(file_path)
    else:
        return {"filename": Path(file_path).name, "db_rows": [], "skipped": 0,
                "errors": [f"알 수 없는 파일 타입: {name}"], "source": file_path,
                "file_type": "UNKNOWN"}


# ---------------------------------------------------------------------------
# 단건 적재 (순차 처리)
# ---------------------------------------------------------------------------

def ingest_file(file_path: str, conn=None) -> dict:
    """단일 CSV 파일 적재 (파싱 → 계산 → DB 저장)."""
    result = _process_file(file_path)
    _write_result_to_db(result, conn)
    return _to_detail(result)


# ---------------------------------------------------------------------------
# 배치 적재 (병렬 파싱 + 단일 DB 커밋)
# ---------------------------------------------------------------------------

def ingest_files(paths: list[str], on_progress: callable = None) -> dict:
    """여러 CSV 파일을 병렬 파싱 후 한 번에 DB 적재.

    Args:
        paths: 적재할 CSV 파일 경로 목록
        on_progress: 파일 하나 완료될 때마다 호출되는 콜백.
                     on_progress(completed_files: int, total_files: int)

    처리 흐름:
      1단계: 파싱 + RPM 계산 (CPU 작업 → ProcessPoolExecutor로 병렬화)
             파일 하나 완료될 때마다 on_progress 콜백 호출
      2단계: 계산 결과를 모아서 DB에 배치 INSERT (단일 트랜잭션, commit 1회)
      3단계: 응답 집계
    """
    total = len(paths)

    def _notify(completed: int):
        if on_progress:
            on_progress(completed, total)

    # 1단계: 병렬 파싱 + 계산
    # 2개 이하일 때는 프로세스 풀 오버헤드가 더 크므로 순차 실행
    results = []
    if total <= 2:
        for i, p in enumerate(paths):
            results.append(_process_file(p))
            _notify(i + 1)
    else:
        completed = 0
        with ProcessPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            # 각 파일을 별도 프로세스에서 파싱+계산 (파일 간 의존성 없음)
            futures = {executor.submit(_process_file, p): p for p in paths}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    p = futures[future]
                    results.append({
                        "filename": Path(p).name, "db_rows": [], "skipped": 0,
                        "errors": [str(e)], "source": p, "file_type": "UNKNOWN",
                    })
                completed += 1
                _notify(completed)

    # 2단계: 배치 DB 저장 (커넥션 1회, 커밋 1회)
    # SQLite는 commit이 가장 비싼 작업(디스크 fsync)이므로 한 번에 묶어야 빠름
    conn = database.get_connection()
    try:
        for result in results:
            _write_result_to_db(result, conn)
        conn.commit()
    finally:
        conn.close()

    # 3단계: 응답 집계
    total_files = len(results)
    success_cycles = 0
    skipped_cycles = 0
    failed_lines = 0
    details = []

    for result in results:
        detail = _to_detail(result)
        details.append(detail)
        success_cycles += detail["cycles_ingested"]
        skipped_cycles += detail["cycles_skipped"]
        failed_lines += len(detail["errors"])

    return {
        "total_files": total_files,
        "success_cycles": success_cycles,
        "skipped_cycles": skipped_cycles,
        "failed_lines": failed_lines,
        "details": details,
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _write_result_to_db(result: dict, conn=None):
    """파싱 결과를 DB에 저장. conn이 주어지면 커밋하지 않음 (호출자가 관리)."""
    if result["file_type"] == "PULSE" and result["db_rows"]:
        inserted = insert_many(result["db_rows"], conn=conn)
        upsert_ingested_file(
            result["source"], result["filename"], "PULSE",
            inserted, result["skipped"], len(result["errors"]), conn=conn
        )
        result["_inserted"] = inserted
    elif result["file_type"] == "VIB":
        vib_count = result.get("vib_cycle_count", 0)
        upsert_ingested_file(
            result["source"], result["filename"], "VIB",
            vib_count, 0, 0, conn=conn
        )
        result["_inserted"] = vib_count
    else:
        result["_inserted"] = 0


def _to_detail(result: dict) -> dict:
    """내부 처리 결과를 API 응답용 형식으로 변환."""
    return {
        "filename": result["filename"],
        "cycles_ingested": result.get("_inserted", len(result["db_rows"])),
        "cycles_skipped": result["skipped"],
        "errors": result["errors"],
    }
