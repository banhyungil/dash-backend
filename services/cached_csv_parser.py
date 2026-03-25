"""Cached CSV parser: transparent caching layer over csv_parser.

Returns columnar format per cycle for efficient downstream processing:
  PULSE: {"timestamps": [str], "cycles": [{"pulses": [int], "accel_x": [float], "accel_y": [float], "accel_z": [float]}, ...]}
  VIB:   {"timestamps": [str], "cycles": [{"accel_x": [float], "accel_z": [float]}, ...]}
"""

import re
from pathlib import Path

from services.csv_parser import parse_pulse_csv, parse_vib_csv
from services.cache_manager import read_parsed_cache, write_parsed_cache


def _extract_cache_key(file_path: Path) -> tuple[str, str, str, str] | None:
    """Extract (month, device, device_name, csv_stem) from a CSV file path.
    Expected path: .../Measured_{YYMM}/Measured/{device_name}/measure/{device}/PULSE_{date}.csv
    """
    parts = file_path.parts
    # Find "Measured_YYMM" part
    for i, part in enumerate(parts):
        if part.startswith("Measured_") and len(part) == 13:  # Measured_YYMM
            month = part.replace("Measured_", "")
            # Expected: parts[i+1]="Measured", parts[i+2]=device_name, parts[i+3]="measure", parts[i+4]=device
            if i + 4 < len(parts):
                device_name = parts[i + 2]
                device = parts[i + 4]
                csv_stem = file_path.stem  # e.g. PULSE_260101
                return month, device, device_name, csv_stem
    return None


def parse_pulse_cached(file_path: str | Path) -> dict:
    """Parse PULSE CSV with caching. Returns columnar format.
    Returns: {"timestamps": [...], "cycles": [{"pulses": [...], "accel_x": [...], ...}, ...]}
    """
    path = Path(file_path)
    if not path.exists():
        return {"timestamps": [], "cycles": []}

    key = _extract_cache_key(path)
    if key:
        cached = read_parsed_cache(*key, path)
        if cached is not None:
            return cached

    # Cache miss: parse and convert to columnar
    raw_cycles = parse_pulse_csv(path)
    result = _pulse_to_columnar(raw_cycles)

    if key:
        write_parsed_cache(*key, path, result)

    return result


def parse_vib_cached(file_path: str | Path) -> dict:
    """Parse VIB CSV with caching. Returns columnar format.
    Returns: {"timestamps": [...], "cycles": [{"accel_x": [...], "accel_z": [...]}, ...]}
    """
    path = Path(file_path)
    if not path.exists():
        return {"timestamps": [], "cycles": []}

    key = _extract_cache_key(path)
    if key:
        cached = read_parsed_cache(*key, path)
        if cached is not None:
            return cached

    raw_cycles = parse_vib_csv(path)
    result = _vib_to_columnar(raw_cycles)

    if key:
        write_parsed_cache(*key, path, result)

    return result


def _pulse_to_columnar(raw_cycles: list[dict]) -> dict:
    """Convert list-of-dicts format to columnar arrays."""
    timestamps = []
    cycles = []
    for cycle in raw_cycles:
        timestamps.append(cycle["timestamp"])
        data = cycle["data"]
        cycles.append({
            "pulses": [item["pulse"] for item in data],
            "accel_x": [item.get("accel_x", 0) for item in data],
            "accel_y": [item.get("accel_y", 0) for item in data],
            "accel_z": [item.get("accel_z", 0) for item in data],
        })
    return {"timestamps": timestamps, "cycles": cycles}


def _vib_to_columnar(raw_cycles: list[dict]) -> dict:
    """Convert list-of-dicts format to columnar arrays."""
    timestamps = []
    cycles = []
    for cycle in raw_cycles:
        timestamps.append(cycle["timestamp"])
        data = cycle["data"]
        cycles.append({
            "accel_x": [item.get("accel_x", 0) for item in data],
            "accel_z": [item.get("accel_z", 0) for item in data],
        })
    return {"timestamps": timestamps, "cycles": cycles}
