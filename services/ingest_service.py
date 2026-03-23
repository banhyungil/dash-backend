"""CSV ingestion pipeline: parse CSV → compute RPM/MPM → insert into DB."""
import math
import logging
import re
from pathlib import Path

from config import (
    DEFAULT_SHAFT_DIA, DEFAULT_PATTERN_WIDTH, DEFAULT_TARGET_RPM,
    ROLL_DIAMETER_MM, DEVICE_SESSION_MAP,
)
from services.csv_parser import parse_pulse_csv, parse_vib_csv
from services.rpm_service import process_pulse_compact_to_rpm
from services.expected_filter import is_expected_valid, calculate_expected_pulse_count
from services import database
from repos.cycles_repo import insert_many
from repos.ingested_files_repo import upsert as upsert_ingested_file, exists_by_path

logger = logging.getLogger(__name__)


def _calc_mpm(rpm: float, roll_dia: float) -> float:
    return round(rpm * math.pi * roll_dia / 1000, 2)


def _extract_date_from_filename(filename: str) -> str | None:
    """Extract YYMMDD date from filename like PULSE_260311.csv."""
    m = re.search(r"_(\d{6})\.", filename)
    return m.group(1) if m else None


def _extract_month_from_date(date_str: str) -> str:
    """Extract YYMM from YYMMDD."""
    return date_str[:4]


def scan_folder(folder: str) -> list[dict]:
    """Scan a folder for PULSE/VIB CSV files.
    Returns list of {path, filename, type, size_bytes, estimated_cycles, already_ingested}.
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

        # Estimate cycles by counting newlines (fast, no full read for large files)
        try:
            size = csv_path.stat().st_size
            if size > 10 * 1024 * 1024:  # >10MB: sample first 1MB to estimate
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


def ingest_pulse_file(file_path: str, device: str | None = None,
                      shaft_dia: float = DEFAULT_SHAFT_DIA,
                      pattern_width: float = DEFAULT_PATTERN_WIDTH,
                      conn=None) -> dict:
    """Ingest a single PULSE CSV file into DB.
    Returns {filename, cycles_ingested, cycles_skipped, errors}.
    """
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name
    date_str = _extract_date_from_filename(filename)

    if not date_str:
        return {"filename": filename, "cycles_ingested": 0, "cycles_skipped": 0,
                "errors": [f"Cannot extract date from filename: {filename}"]}

    month = _extract_month_from_date(date_str)

    # Detect device from path if not provided
    if not device:
        # Try to find MAC address in path
        for part in path.parts:
            if part in DEVICE_SESSION_MAP:
                device = part
                break
        if not device:
            device = "unknown"

    session = DEVICE_SESSION_MAP.get(device, device)

    # Parse
    raw_cycles = parse_pulse_csv(path)
    if not raw_cycles:
        return {"filename": filename, "cycles_ingested": 0, "cycles_skipped": 0,
                "errors": ["No cycles parsed"]}

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

            rpm_result = process_pulse_compact_to_rpm(
                pulses, accel_x, accel_y, accel_z, shaft_dia, pattern_width
            )

            if rpm_result is None:
                skipped += 1
                continue

            rpm_mean = rpm_result["rpmMean"]
            valid = is_expected_valid(set_count, rpm_mean, shaft_dia, pattern_width)
            expected_count = calculate_expected_pulse_count(rpm_mean, shaft_dia, pattern_width)

            mpm_mean = _calc_mpm(rpm_mean, ROLL_DIAMETER_MM)
            mpm_min = _calc_mpm(rpm_result["rpmMin"], ROLL_DIAMETER_MM)
            mpm_max = _calc_mpm(rpm_result["rpmMax"], ROLL_DIAMETER_MM)

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
                "max_vib_z": max((abs(v) for v in accel_z), default=0),
                "high_vib_event": 1 if any(abs(v) > 0.3 for v in accel_x + accel_z) else 0,
                "source_path": source,
            })
        except Exception as e:
            errors.append(f"Cycle {i}: {e}")
            skipped += 1

    inserted = insert_many(db_rows, conn=conn)
    upsert_ingested_file(source, filename, "PULSE", inserted, skipped, len(errors), conn=conn)

    logger.info("Ingested %s: %d cycles, %d skipped, %d errors", filename, inserted, skipped, len(errors))

    return {
        "filename": filename,
        "cycles_ingested": inserted,
        "cycles_skipped": skipped,
        "errors": errors,
    }


def ingest_vib_file(file_path: str, device: str | None = None, conn=None) -> dict:
    """Ingest a VIB CSV file — records the file as ingested but doesn't store
    per-sample data in DB (too large). VIB array data is read from CSV on demand."""
    path = Path(file_path)
    source = str(path.resolve())
    filename = path.name

    raw_cycles = parse_vib_csv(path)
    cycle_count = len(raw_cycles)

    upsert_ingested_file(source, filename, "VIB", cycle_count, 0, 0, conn=conn)
    logger.info("Ingested VIB %s: %d cycles (metadata only)", filename, cycle_count)

    return {
        "filename": filename,
        "cycles_ingested": cycle_count,
        "cycles_skipped": 0,
        "errors": [],
    }


def ingest_file(file_path: str, conn=None, **kwargs) -> dict:
    """Ingest a single CSV file (auto-detect PULSE or VIB)."""
    name = Path(file_path).name.upper()
    if name.startswith("PULSE_"):
        return ingest_pulse_file(file_path, conn=conn, **kwargs)
    elif name.startswith("VIB_"):
        return ingest_vib_file(file_path, conn=conn)
    else:
        return {"filename": Path(file_path).name, "cycles_ingested": 0,
                "cycles_skipped": 0, "errors": [f"Unknown file type: {name}"]}


def ingest_files(paths: list[str]) -> dict:
    """Ingest multiple CSV files in a single transaction (batch commit)."""
    conn = database.get_connection()
    total_files = 0
    success_cycles = 0
    skipped_cycles = 0
    failed_lines = 0
    details = []

    try:
        for p in paths:
            result = ingest_file(p, conn=conn)
            details.append(result)
            total_files += 1
            success_cycles += result["cycles_ingested"]
            skipped_cycles += result["cycles_skipped"]
            failed_lines += len(result["errors"])

        conn.commit()
    finally:
        conn.close()

    return {
        "total_files": total_files,
        "success_cycles": success_cycles,
        "skipped_cycles": skipped_cycles,
        "failed_lines": failed_lines,
        "details": details,
    }
